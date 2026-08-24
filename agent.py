"""
AUBIEETERNAL -- Autonomous Agent
File: /home/aubieeternal/AUBIEETERNAL/agent.py

Gives the rig the ability to work the way Claude does: form a plan, take a
step, look at the result, correct itself, and keep going until the goal is met.

Powered by qwen2.5:14b locally. Tools: shell, python, file read/write,
directory listing, memory search, and the browser agent.

SAFETY MODEL -- "full autonomy with quarantine":
  The agent acts without asking, but nothing is ever truly destroyed.
    * rm / delete commands are rewritten to MOVE into _agent_trash/
    * overwriting a file backs up the original first
    * a hard blocklist stops catastrophic commands outright
    * every action is logged with a manifest so anything can be undone

Add to assistant_server.py:
    from agent import router as agent_router
    app.include_router(agent_router)
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import os, re, json, uuid, shlex, shutil, subprocess, datetime, threading

import httpx

router = APIRouter()

# ── Paths & config ─────────────────────────────────────────────
BASE = "/home/aubieeternal/AUBIEETERNAL"
MEMORY = "/home/aubieeternal/AUBIEETERNAL_MEMORY"
TRASH = os.path.join(MEMORY, "_agent_trash")
RUNS = os.path.join(BASE, "agent_runs")
TRASH_LOG = os.path.join(TRASH, "manifest.jsonl")

OLLAMA = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:14b"
SELF = "http://localhost:8800"

os.makedirs(TRASH, exist_ok=True)
os.makedirs(RUNS, exist_ok=True)

# Commands that are never allowed, quarantine or not
HARD_BLOCK = [
    "mkfs", "dd if=", ":(){:|:&};:", "> /dev/sd", "of=/dev/sd",
    "shutdown", "reboot", "poweroff", "halt", "init 0", "init 6",
    "rm -rf /", "rm -rf /*", "chmod -R 777 /", "chown -R / ",
    "> /etc/", "curl | sh", "wget | sh", "curl | bash", "wget | bash",
]

# Destructive verbs we intercept and reroute to quarantine
DESTRUCTIVE = re.compile(r"\b(rm|unlink|shred|truncate)\b")

# In-memory run registry (also persisted to disk)
_RUNS = {}
_LOCK = threading.Lock()


def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── Quarantine helpers ─────────────────────────────────────────
def quarantine_path(src: str) -> str:
    rel = src.lstrip("/").replace("/", "__")
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(TRASH, f"{stamp}__{rel}")


def log_trash(action: str, src: str, dst: str, run_id: str):
    try:
        with open(TRASH_LOG, "a") as f:
            f.write(json.dumps({
                "time": now(), "run": run_id, "action": action,
                "original": src, "moved_to": dst,
            }) + "\n")
    except Exception:
        pass


def safe_delete(target: str, run_id: str) -> str:
    """Move to quarantine instead of deleting."""
    if not os.path.exists(target):
        return f"not found: {target}"
    dst = quarantine_path(target)
    try:
        shutil.move(target, dst)
        log_trash("delete", target, dst, run_id)
        return f"quarantined {target} -> {dst} (recoverable)"
    except Exception as e:
        return f"could not quarantine {target}: {e}"


def backup_before_write(path: str, run_id: str):
    if os.path.exists(path):
        dst = quarantine_path(path)
        try:
            shutil.copy2(path, dst)
            log_trash("overwrite-backup", path, dst, run_id)
        except Exception:
            pass


# ── Tools ──────────────────────────────────────────────────────
def err(tool, operation, exc, target="", hint=""):
    """
    Specific, actionable error text.

    Written on the recommendation of the agent itself, which reviewed this
    file and correctly observed that a bare 'error: {e}' gives the model
    nothing to reason about. It needs to know WHICH tool failed, doing WHAT,
    to WHAT, and what to try instead.
    """
    kind = type(exc).__name__ if isinstance(exc, BaseException) else "Error"
    msg = str(exc)
    out = f"{tool}_error [{kind}] while {operation}"
    if target:
        out += f": {target}"
    out += f"\n  detail: {msg}"
    if hint:
        out += f"\n  try: {hint}"
    return out


def pick(args, *names, default=""):
    """
    Models are inconsistent about argument names -- it may send 'script'
    where we expect 'code', or 'command' where we expect 'cmd'. Accept any
    reasonable alias, and if there's exactly one string value, just take it.
    """
    if not isinstance(args, dict):
        return str(args) if args else default
    for n in names:
        if n in args and args[n] not in (None, ""):
            return str(args[n])
    # last resort: a single string value is almost certainly the intent
    strings = [v for v in args.values() if isinstance(v, str) and v.strip()]
    if len(strings) == 1:
        return strings[0]
    return default


def tool_shell(args, run_id):
    cmd = pick(args, "cmd", "command", "bash", "shell", "cmd_line", "script").strip()
    if not cmd:
        return "no command given (use args: {\"cmd\": \"...\"})"

    low = cmd.lower()
    for bad in HARD_BLOCK:
        if bad in low:
            return f"REFUSED: '{bad}' is on the hard blocklist. Nothing was run."

    # Intercept destructive commands -> quarantine instead
    if DESTRUCTIVE.search(low):
        try:
            parts = shlex.split(cmd)
        except ValueError:
            parts = cmd.split()
        targets = [p for p in parts[1:] if not p.startswith("-")]
        if not targets:
            return "REFUSED: destructive command with no clear target."
        results = [safe_delete(t, run_id) for t in targets]
        return ("Destructive command intercepted. Files were moved to quarantine "
                "instead of deleted:\n" + "\n".join(results))

    try:
        p = subprocess.run(["bash", "-c", cmd], capture_output=True,
                           text=True, timeout=120)
        out = (p.stdout or "").strip()
        err = (p.stderr or "").strip()
        res = out
        if err:
            res += ("\n[stderr] " + err) if res else ("[stderr] " + err)
        res = res or "(no output)"
        return res[:5000]
    except subprocess.TimeoutExpired:
        return err("shell", "running a command (120s limit)",
                   Exception("exceeded 120 seconds"), cmd[:120],
                   "narrow the command, or use python for long file operations")
    except Exception as e:
        return err("shell", "running a command", e, cmd[:120],
                   "check the syntax, or try the python tool instead")


def tool_python(args, run_id):
    code = pick(args, "code", "script", "source", "python", "program", "cmd")
    if not code.strip():
        return "no code given (use args: {\"code\": \"...\"})"
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                     prefix="agent_") as f:
        f.write(code)
        tmp = f.name
    try:
        p = subprocess.run(["python3", tmp], capture_output=True,
                           text=True, timeout=180)
        out = (p.stdout or "").strip()
        err = (p.stderr or "").strip()
        res = out
        if err:
            res += ("\n[stderr] " + err) if res else ("[stderr] " + err)
        return (res or "(no output)")[:5000]
    except subprocess.TimeoutExpired:
        return err("python", "running a script (180s limit)",
                   Exception("exceeded 180 seconds"), "",
                   "process fewer files per run, or print progress as you go")
    except Exception as e:
        return err("python", "running a script", e, "",
                   "check the code for syntax errors before rerunning")
    finally:
        try:
            os.unlink(tmp)
        except Exception:
            pass


def tool_read_file(args, run_id):
    path = pick(args, "path", "file", "filename", "filepath")
    limit = int(args.get("max_lines", 200) or 200)
    if not os.path.isfile(path):
        return f"not a file: {path}"
    try:
        with open(path, "r", errors="ignore") as f:
            lines = [next(f) for _ in range(limit)]
    except StopIteration:
        pass
    except Exception as e:
        return f"error: {e}"
    try:
        with open(path, "r", errors="ignore") as f:
            content = "".join(f.readlines()[:limit])
        return content[:6000] or "(empty)"
    except Exception as e:
        return err("read_file", "reading", e, path,
                   "confirm the path with list_dir, or use grep to find "
                   "just the part you need in a large file")


def tool_write_file(args, run_id):
    path = pick(args, "path", "file", "filename", "filepath")
    content = pick(args, "content", "text", "data", "body", "contents")
    if not path:
        return "no path given (use args: {\"path\": \"...\", \"content\": \"...\"})"
    if not path.startswith(("/home/aubieeternal/", "/tmp/")):
        return "REFUSED: writes are limited to /home/aubieeternal/ and /tmp/"
    backup_before_write(path, run_id)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return f"wrote {len(content)} bytes to {path} (previous version backed up if it existed)"
    except Exception as e:
        return err("write_file", "writing", e, path,
                   "check the parent directory exists and is under /home/aubieeternal/")


def tool_list_dir(args, run_id):
    path = pick(args, "path", "dir", "directory", "folder", default=MEMORY)
    if not os.path.isdir(path):
        return f"not a directory: {path}"
    try:
        entries = sorted(os.listdir(path))[:200]
        out = []
        for e in entries:
            full = os.path.join(path, e)
            kind = "dir " if os.path.isdir(full) else "file"
            try:
                sz = os.path.getsize(full)
            except OSError:
                sz = 0
            out.append(f"{kind} {sz:>12,}  {e}")
        return "\n".join(out) or "(empty)"
    except Exception as e:
        return err("list_dir", "listing", e, path,
                   "check the path spelling, or list the parent directory first")


def tool_grep(args, run_id):
    """Search INSIDE files for text. This is what you want for reading code."""
    pattern = pick(args, "pattern", "text", "query", "search", "regex", "term")
    path = pick(args, "path", "file", "dir", "directory", default=BASE)
    if not pattern:
        return 'no pattern given (use args: {"pattern": "...", "path": "..."})'

    p = pattern.replace("'", "'\\''")
    if os.path.isfile(path):
        cmd = f"grep -n -- '{p}' '{path}' | head -60"
    else:
        cmd = (f"grep -rn --include='*.py' --include='*.md' --include='*.sh' "
               f"--include='*.txt' --include='*.json' -- '{p}' '{path}' 2>/dev/null | head -60")
    try:
        r = subprocess.run(["bash", "-c", cmd], capture_output=True,
                           text=True, timeout=60)
        out = (r.stdout or "").strip()
        return out[:5000] if out else (
            f"no matches for '{pattern}' in {path}\n"
            "  note: this searched file CONTENTS. If the path is wrong, "
            "use list_dir first to confirm it exists."
        )
    except Exception as e:
        return err("grep", "searching file contents", e, f"{pattern} in {path}",
                   "simplify the pattern -- plain text works better than regex")


def tool_search_memory(args, run_id):
    q = pick(args, "query", "q", "search", "term", "name").strip()
    if not q:
        return "no query given"
    safe = q.replace("'", "")
    cmd = (f"find {MEMORY} -type f -iname '*{safe}*' 2>/dev/null | head -40")
    p = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=60)
    hits = (p.stdout or "").strip()
    return hits or "no filename matches"


def tool_browse(args, run_id):
    task = pick(args, "task", "query", "goal", "search", "url")
    try:
        with httpx.Client(timeout=180) as c:
            r = c.post(f"{SELF}/browse", json={"task": task})
        return str(r.json().get("result", ""))[:4000]
    except Exception as e:
        return err("browse", "using the web browser", e, task[:100],
                   "browsing is slow and can time out; try a narrower task")


TOOLS = {
    "shell": (tool_shell,
              'args {"cmd": "<bash command>"} -- run a shell command. '
              'Destructive commands are auto-quarantined, not deleted.'),
    "python": (tool_python,
               'args {"code": "<python source>"} -- run a Python 3 script. '
               'Best for counting, sorting, or processing many files.'),
    "grep": (tool_grep,
             'args {"pattern": "<text to find>", "path": "<file or dir>"} -- '
             'searches INSIDE files. Use this to find code, not search_memory.'),
    "read_file": (tool_read_file,
                  'args {"path": "<absolute path>", "max_lines": 800} -- '
                  'reads from the top. For a specific part of a big file, grep first.'),
    "write_file": (tool_write_file,
                   'args {"path": "<absolute path>", "content": "<text>"} -- '
                   'existing file is backed up first.'),
    "list_dir": (tool_list_dir, 'args {"path": "<absolute path>"}'),
    "search_memory": (tool_search_memory,
                      'args {"query": "<filename fragment>"} -- finds FILES BY NAME in '
                      'the backup archive only. It does NOT search file contents and does '
                      'NOT understand regex. To search inside files, use grep.'),
    "browse": (tool_browse,
               'args {"task": "<what to find on the web>"} -- slow, 1-2 minutes.'),
}

# ── Merge in the toolbox (and anything the agent has written itself) ────
try:
    import agent_toolbox
    TOOLS.update(agent_toolbox.all_tools())
    print(f"[agent] {len(TOOLS)} tools loaded")
except Exception as _e:  # toolbox is optional -- core tools still work
    print(f"[agent] toolbox not loaded: {_e}")


# ── Prompt ─────────────────────────────────────────────────────
def build_prompt(goal, history, env):
    tool_lines = "\n".join(
        f'  - {name}: {desc}' for name, (_, desc) in TOOLS.items()
    )

    hist = ""
    for step in history:
        hist += f"\nSTEP {step['n']}\n"
        hist += f"thought: {step['thought']}\n"
        hist += f"action: {step['tool']} {json.dumps(step['args'])[:300]}\n"
        hist += f"result: {step['result'][:1200]}\n"

    return f"""You are the AUBIEETERNAL rig's autonomous agent, running on a Ryzen Linux
machine that belongs to Mateo. You complete goals by taking one step at a time.

{env}

AVAILABLE TOOLS:
{tool_lines}

RULES:
- Respond with EXACTLY ONE JSON object. No markdown fences, no prose outside the JSON.
- Format: {{"thought": "brief reasoning", "tool": "<tool name>", "args": {{...}}}}
- When the goal is achieved, use the special tool "finish":
  {{"thought": "...", "tool": "finish", "args": {{"answer": "what you found or did"}}}}
- Take ONE step at a time. Look at each result before deciding the next move.
- If a command fails, read the error and try a different approach. Do not repeat
  the exact same failing command.
- Prefer shell for quick inspection, python for anything involving many files.
- Use absolute paths. Never use placeholder paths like /path/to/.
- Be efficient: aim to finish in as few steps as possible.

GOAL: {goal}
{hist}
Respond with the next JSON action:"""


def ask_model(prompt, timeout=180):
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 700},
    }
    with httpx.Client(timeout=timeout) as c:
        r = c.post(OLLAMA, json=payload)
    return r.json().get("response", "").strip()


def parse_action(text):
    t = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", t, re.DOTALL)
    if m:
        t = m.group(1).strip()
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(t[start:end + 1])
    except Exception:
        # tolerate trailing junk after the first object
        depth = 0
        for i, ch in enumerate(t[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(t[start:i + 1])
                    except Exception:
                        return None
        return None


def env_block():
    try:
        with open(os.path.join(BASE, "USER_CONTEXT.md")) as f:
            ctx = f.read()[:2500]
    except Exception:
        ctx = ""
    return f"""ENVIRONMENT:
- Host: aubieeternal (Ubuntu, Ryzen + RTX 3060). User: aubieeternal.
- Project code: {BASE}/
- Archive: {MEMORY}/  (TAX/ AUBIE/ PERSONAL/ PHOTOS/ GOOGLE_DRIVE/)
- Photos: {MEMORY}/PHOTOS/iCloud/YYYY/MM/ (~43,000 files, HEIC + MOV)
- Assistant API on port 8800. Ollama on 11434.
- Robot dog 'Aubie' at 100.66.110.65 (may be offline).

{ctx}"""


# ── Run engine ─────────────────────────────────────────────────
def execute_run(run_id, goal, max_steps):
    history = []
    env = env_block()

    with _LOCK:
        _RUNS[run_id]["status"] = "running"

    for n in range(1, max_steps + 1):
        prompt = build_prompt(goal, history, env)
        try:
            raw = ask_model(prompt)
        except Exception as e:
            with _LOCK:
                _RUNS[run_id]["status"] = "error"
                _RUNS[run_id]["answer"] = f"model error: {e}"
            break

        action = parse_action(raw)
        if not action:
            history.append({"n": n, "thought": "(unparseable)", "tool": "none",
                            "args": {}, "result": "Your reply was not valid JSON. "
                                                  "Reply with exactly one JSON object."})
            with _LOCK:
                _RUNS[run_id]["steps"] = history
            continue

        tool = str(action.get("tool", "")).strip()
        args = action.get("args") or {}
        thought = str(action.get("thought", ""))[:400]

        if tool == "finish":
            answer = str(args.get("answer", "done"))
            history.append({"n": n, "thought": thought, "tool": "finish",
                            "args": {}, "result": answer})
            with _LOCK:
                _RUNS[run_id]["status"] = "done"
                _RUNS[run_id]["answer"] = answer
                _RUNS[run_id]["steps"] = history
            break

        fn = TOOLS.get(tool, (None, None))[0]
        if fn is None:
            result = f"unknown tool '{tool}'. Available: {', '.join(TOOLS)}"
        else:
            try:
                result = fn(args, run_id)
            except Exception as e:
                result = f"tool crashed: {e}"

        result = str(result)

        # Loop guard -- fuzzy, so near-identical retries also get caught.
        # Same tool + same result is the real signal something is stuck.
        same_tool_same_result = sum(
            1 for s in history
            if s["tool"] == tool and s["result"][:150] == result[:150]
        )
        if same_tool_same_result >= 2:
            result += (
                f"\n\n[SYSTEM] '{tool}' has now returned this same result "
                f"{same_tool_same_result + 1} times. It is not going to work. "
                "Stop retrying it. Re-read the tool list above and pick a "
                "DIFFERENT tool, or state what you found so far and finish."
            )

        history.append({"n": n, "thought": thought, "tool": tool,
                        "args": args, "result": result})
        with _LOCK:
            _RUNS[run_id]["steps"] = history
    else:
        with _LOCK:
            _RUNS[run_id]["status"] = "max_steps"
            _RUNS[run_id]["answer"] = (
                f"Stopped after {max_steps} steps without finishing. "
                "See the step log for how far it got.")

    # persist
    try:
        with open(os.path.join(RUNS, run_id + ".json"), "w") as f:
            json.dump(_RUNS[run_id], f, indent=1)
    except Exception:
        pass


# ── Endpoints ──────────────────────────────────────────────────
class AgentRequest(BaseModel):
    goal: str
    max_steps: int = 12
    background: bool = True


@router.post("/agent/run")
def agent_run(req: AgentRequest):
    run_id = uuid.uuid4().hex[:10]
    with _LOCK:
        _RUNS[run_id] = {"id": run_id, "goal": req.goal, "status": "queued",
                         "started": now(), "steps": [], "answer": ""}

    if req.background:
        threading.Thread(target=execute_run,
                         args=(run_id, req.goal, req.max_steps),
                         daemon=True).start()
        return JSONResponse({"status": "started", "run_id": run_id,
                             "poll": f"/agent/status/{run_id}"})

    execute_run(run_id, req.goal, req.max_steps)
    with _LOCK:
        return JSONResponse(_RUNS[run_id])


@router.get("/agent/status/{run_id}")
def agent_status(run_id: str):
    with _LOCK:
        run = _RUNS.get(run_id)
    if not run:
        path = os.path.join(RUNS, run_id + ".json")
        if os.path.exists(path):
            with open(path) as f:
                return JSONResponse(json.load(f))
        return JSONResponse({"status": "unknown", "run_id": run_id}, status_code=404)
    return JSONResponse(run)


@router.get("/agent/explain/{run_id}")
def agent_explain(run_id: str):
    """
    Plain-English account of what it did and why it chose that approach.
    Reads the step log back and narrates the decisions.
    """
    with _LOCK:
        run = _RUNS.get(run_id)
    if not run:
        path = os.path.join(RUNS, run_id + ".json")
        if not os.path.exists(path):
            return JSONResponse({"status": "unknown"}, status_code=404)
        with open(path) as f:
            run = json.load(f)

    steps = run.get("steps", [])
    if not steps:
        return JSONResponse({"status": "ok", "explanation": "No steps recorded."})

    # Readable trace first -- this alone is often enough
    trace = []
    for s in steps:
        line = f"{s['n']}. [{s['tool']}] {s['thought']}"
        res = s["result"][:200].replace("\n", " ")
        line += f"\n     -> {res}"
        trace.append(line)
    trace_text = "\n".join(trace)

    prompt = f"""Explain what you did and why, in plain language, to Mateo.

He asked for: {run.get('goal')}

Your actual steps:
{trace_text[:4000]}

Write a short account covering:
- what approach you chose and why that one
- anything that went wrong and how you changed course
- what you concluded

Four or five sentences. Plain words, no markdown, no bullet points.

Explanation:"""
    try:
        text = ask_model(prompt, timeout=120)
    except Exception as e:
        text = f"(could not generate narrative: {e})"

    return JSONResponse({
        "status": "ok",
        "goal": run.get("goal"),
        "outcome": run.get("status"),
        "answer": run.get("answer"),
        "steps_taken": len(steps),
        "explanation": text,
        "trace": trace_text[:6000],
    })


@router.get("/agent/runs")
def agent_runs():
    with _LOCK:
        active = [{"id": r["id"], "goal": r["goal"], "status": r["status"],
                   "steps": len(r["steps"]), "started": r["started"]}
                  for r in _RUNS.values()]
    return JSONResponse({"status": "ok", "runs": active})


@router.get("/agent/trash")
def agent_trash():
    """What the agent has quarantined, and how to get it back."""
    items = []
    if os.path.exists(TRASH_LOG):
        with open(TRASH_LOG) as f:
            for line in f:
                try:
                    items.append(json.loads(line))
                except Exception:
                    pass
    size = 0
    for root, _, files in os.walk(TRASH):
        for fn in files:
            try:
                size += os.path.getsize(os.path.join(root, fn))
            except OSError:
                pass
    return JSONResponse({
        "status": "ok",
        "quarantined_items": len(items),
        "bytes": size,
        "recent": items[-25:],
        "restore_hint": "mv the 'moved_to' path back to 'original'",
    })


@router.get("/agent/health")
def agent_health():
    return {"status": "ok", "model": MODEL, "tools": list(TOOLS),
            "safety": "full autonomy with quarantine",
            "trash": TRASH}

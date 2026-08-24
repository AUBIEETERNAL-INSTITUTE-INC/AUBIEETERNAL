"""
AUBIEETERNAL -- Interpreter Agent
File: /home/aubieeternal/AUBIEETERNAL/interpreter_agent.py

Gives Aubie the ability to write and run real code/shell commands on Ryzen.
Uses Ollama (qwen2.5:14b) to generate code from plain English, then executes it.

No external dependencies beyond what's already installed.
Add to assistant_server.py:
    from interpreter_agent import router as interpreter_router
    app.include_router(interpreter_router)
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import subprocess, asyncio, tempfile, os, textwrap, json, httpx

router = APIRouter()

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:14b"


# ── Load user context (who Aubie is talking to) ────────────────

# Safety: only allow these in shell mode

ENV_CONTEXT = """

SYSTEM ENVIRONMENT (use these real paths, never invent placeholder paths):
- You are running on 'aubieeternal', an Ubuntu Linux machine (the Ryzen rig).
- Current user: aubieeternal. Home directory: /home/aubieeternal
- Main project code: /home/aubieeternal/AUBIEETERNAL/
  (contains assistant_server.py, phone_ui.py, browser_agent.py, interpreter_agent.py)
- Backup / memory archive: /home/aubieeternal/AUBIEETERNAL_MEMORY/
  (subfolders: TAX/, AUBIE/, PERSONAL/, PHOTOS/, GOOGLE_DRIVE/)
- The assistant server runs via systemd as 'aubie-assistant' on port 8800.
- Ollama runs locally on port 11434.
- GPU: NVIDIA RTX 3060 (use nvidia-smi to query it).
- The robot dog 'Aubie' is a separate machine at 100.66.110.65 (Tailscale).

Always use the absolute paths above. Do not use /path/to/ placeholders.
"""

SHELL_BLOCKLIST = [
    "rm -rf /", "mkfs", "dd if=", ":(){:|:&};:",
    "shutdown", "reboot", "poweroff", "halt",
    "chmod 777 /", "chown -R",
]

# ── Ollama helper ──────────────────────────────────────────────
# ── Load user context (who Aubie is talking to) ────────────────
def _load_user_context():
    try:
        with open("/home/aubieeternal/AUBIEETERNAL/USER_CONTEXT.md") as f:
            return "\n\nUSER CONTEXT:\n" + f.read()
    except Exception:
        return ""

try:
    ENV_CONTEXT = ENV_CONTEXT + _load_user_context()
except NameError:
    ENV_CONTEXT = _load_user_context()


async def ask_ollama(prompt: str, timeout: int = 60) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0, "num_predict": 1024}
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(OLLAMA_URL, json=payload)
    return r.json().get("response", "").strip()


def extract_code(text: str, lang: str = "") -> str:
    """Pull code out of a markdown code block if present."""
    import re
    # Try fenced block with language tag
    pattern = rf"```{lang}\s*\n(.*?)```"
    m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # Try any fenced block
    m = re.search(r"```.*?\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    # Return as-is (already raw code)
    return text.strip()


def run_subprocess(cmd: list, input_text: str = None, timeout: int = 30) -> dict:
    try:
        result = subprocess.run(
            cmd,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return {
            "stdout": result.stdout[-4000:] if result.stdout else "",
            "stderr": result.stderr[-2000:] if result.stderr else "",
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Timed out after " + str(timeout) + "s", "returncode": -1}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "returncode": -1}


# ── Models ─────────────────────────────────────────────────────
class InterpretRequest(BaseModel):
    task: str           # plain English task
    lang: str = "python"  # "python" or "bash"
    timeout: int = 30

class ShellRequest(BaseModel):
    command: str        # raw shell command to run directly
    timeout: int = 15


# ── POST /interpret ────────────────────────────────────────────
@router.post("/interpret")
async def interpret(req: InterpretRequest):
    """
    Plain-English task -> Ollama generates code -> run it -> return output.
    Example: {"task": "list all python files in ~/AUBIEETERNAL and show their sizes"}
    """
    lang = req.lang.lower()

    if lang == "bash":
        system_hint = (
            "You are a bash expert on Ubuntu Linux. "
            "Write a single bash script to complete the task. "
            "Output ONLY the bash code inside a ```bash block. "
            "Keep it safe and do not delete or modify important system files."
        )
    else:
        system_hint = (
            "You are a Python expert. "
            "Write a single Python 3 script to complete the task. "
            "Output ONLY the Python code inside a ```python block. "
            "Use only standard library modules unless you know numpy/pandas are available. "
            "Print results clearly so they are readable."
        )

    prompt = system_hint + ENV_CONTEXT + "\n\nTask: " + req.task

    # Step 1: generate code
    try:
        raw = await ask_ollama(prompt, timeout=45)
    except Exception as e:
        return JSONResponse({"status": "error", "result": "Ollama error: " + str(e)}, status_code=500)

    code = extract_code(raw, lang)

    if not code:
        return JSONResponse({"status": "error", "result": "Model returned no code.", "raw": raw}, status_code=500)

    # Step 2: run the code
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py" if lang == "python" else ".sh",
        delete=False,
        prefix="aubie_interp_"
    ) as f:
        f.write(code)
        tmpfile = f.name

    try:
        if lang == "bash":
            os.chmod(tmpfile, 0o755)
            run_result = run_subprocess(["bash", tmpfile], timeout=req.timeout)
        else:
            run_result = run_subprocess(["python3", tmpfile], timeout=req.timeout)
    finally:
        try:
            os.unlink(tmpfile)
        except Exception:
            pass

    output = run_result["stdout"]
    if run_result["stderr"] and run_result["returncode"] != 0:
        output += "\n[stderr]\n" + run_result["stderr"]

    return JSONResponse({
        "status": "ok" if run_result["returncode"] == 0 else "error",
        "task": req.task,
        "lang": lang,
        "code": code,
        "output": output.strip() or "(no output)",
        "returncode": run_result["returncode"],
    })


# ── POST /interpret/shell ──────────────────────────────────────
@router.post("/interpret/shell")
async def shell(req: ShellRequest):
    """
    Run a raw shell command directly and return stdout.
    Example: {"command": "df -h"}
    """
    cmd = req.command.strip()

    # Safety check
    for blocked in SHELL_BLOCKLIST:
        if blocked in cmd:
            return JSONResponse({
                "status": "blocked",
                "result": "Command blocked for safety: contains '" + blocked + "'"
            }, status_code=403)

    result = run_subprocess(["bash", "-c", cmd], timeout=req.timeout)

    output = result["stdout"]
    if result["stderr"]:
        output += ("\n[stderr]\n" if result["stdout"] else "") + result["stderr"]

    return JSONResponse({
        "status": "ok" if result["returncode"] == 0 else "error",
        "command": cmd,
        "output": output.strip() or "(no output)",
        "returncode": result["returncode"],
    })


# ── POST /interpret/fix ────────────────────────────────────────
class FixRequest(BaseModel):
    code: str
    error: str
    lang: str = "python"

@router.post("/interpret/fix")
async def fix_code(req: FixRequest):
    """
    Give it broken code + error message, get fixed code back.
    """
    prompt = (
        "Fix this " + req.lang + " code. "
        "Output ONLY the corrected code in a ```" + req.lang + " block.\n\n"
        "Code:\n" + req.code + "\n\n"
        "Error:\n" + req.error
    )
    try:
        raw = await ask_ollama(prompt, timeout=45)
    except Exception as e:
        return JSONResponse({"status": "error", "result": str(e)}, status_code=500)

    fixed = extract_code(raw, req.lang)
    return JSONResponse({"status": "ok", "fixed_code": fixed})


# ── GET /interpret/status ──────────────────────────────────────
@router.get("/interpret/status")
async def interpret_status():
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get("http://localhost:11434/api/tags")
        models = [m["name"] for m in r.json().get("models", [])]
        active = OLLAMA_MODEL in " ".join(models)
        return {
            "status": "ready",
            "ollama": "running",
            "model": OLLAMA_MODEL,
            "model_available": active,
            "available_models": models,
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# ── GET /interpret/quickcmds ───────────────────────────────────
@router.get("/interpret/quickcmds")
async def quick_cmds():
    """Handy system info commands Aubie can run from the phone."""
    cmds = {
        "disk": "df -h /",
        "memory": "free -h",
        "cpu_temp": "cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | awk '{print $1/1000 \"C\"}' | head -4",
        "gpu": "nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits 2>/dev/null || echo 'nvidia-smi not available'",
        "uptime": "uptime -p",
        "aubie_files": "ls -lh ~/AUBIEETERNAL/*.py 2>/dev/null | awk '{print $5, $9}'",
        "ollama_models": "ollama list 2>/dev/null",
        "network": "ip -br addr show | grep -v lo",
        "processes": "ps aux --sort=-%cpu | head -8 | awk '{print $1,$3,$4,$11}'",
    }
    results = {}
    for name, cmd in cmds.items():
        r = run_subprocess(["bash", "-c", cmd], timeout=5)
        results[name] = r["stdout"].strip() or r["stderr"].strip() or "N/A"
    return JSONResponse({"status": "ok", "info": results})

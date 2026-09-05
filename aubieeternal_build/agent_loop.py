#!/usr/bin/env python3
"""
agent_loop.py — a propose -> execute -> check -> decide autonomy loop on top
of aubieeternal Build's existing tools, running fully against local Ollama
(qwen2.5:14b / qwen2.5:7b). No cloud API calls.

Why this exists (2026-09-04 handoff, "Agentic Planning Loop for AUBIEETERNAL"):
qwen_loop.py already gives aubieeternal Build real tool-calling (up to 8 steps
per turn) against local Qwen, but it stops at the end of every turn and waits
for a human to type the next prompt — there's no loop where the model decides
the next step from the last result and keeps going on its own until a stated
goal is done. This module adds exactly that, as a SEPARATE wrapper (per
Mateo's choice) rather than changing qwen_loop.py's interactive behavior, and
reuses its tool set / tool-exec function directly rather than duplicating it.

Guardrails (hard stops — checked mechanically against the actual tool-call
content, not just asked of the model in the system prompt):
  - git commit / git push
  - systemctl restart / stop / disable (any service)
  - deleting a file (rm / unlink / shred / rmdir)
  - installing or upgrading packages (pip install, apt install/upgrade)
  - anything touching institute_memory/ (sensitive nonprofit info — read OR
    write; that directory must never reach the public repo, so it doesn't
    get a free pass just because it's a read)
  - anything that would write to the aubie-tutor UNO Q board (100.66.110.65) —
    scp/ssh to it, or the sketch_push / sketch_write / dog_command house kits

When the model proposes a gated action (or the mechanical filter catches an
un-flagged attempt at one — the filter runs regardless of which tool the model
used), the loop STOPS without executing it, writes pending_action.json in the
run's log directory, and exits with status "awaiting_approval". A human
reviews run.md / pending_action.json and re-invokes with --resume RUN_ID
--approve (run the one pending action, then continue the loop) or --deny
"reason" (tell the model no and continue). Nothing gated ever runs without
that explicit second invocation.

The loop is bounded on both iteration count and wall-clock time (whichever
hits first) so it can't run away.

Every step is logged three ways, mirroring self_audit.py's conventions:
  memory/agent_loop/<run_id>/steps.jsonl   - one JSON line per event
  memory/agent_loop/<run_id>/latest.json   - current status snapshot
  memory/agent_loop/<run_id>/run.md        - human-readable transcript
  memory/agent_loop/<run_id>/messages.json - full chat history (for --resume)

Usage:
    python3 agent_loop.py "goal, one clear sentence" [--cwd PATH]
        [--model qwen2.5:14b] [--max-iterations 12] [--max-seconds 600]
    python3 agent_loop.py --status RUN_ID
    python3 agent_loop.py --resume RUN_ID --approve
    python3 agent_loop.py --resume RUN_ID --deny "reason the action is unsafe"
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qwen_loop as ql  # reuse OLLAMA URL, MODEL_MAP, TOOLS, _exec, _pick

LOG_ROOT = Path.home() / "AUBIEETERNAL" / "memory" / "agent_loop"
LOG_ROOT.mkdir(parents=True, exist_ok=True)

DEFAULT_MAX_ITERATIONS = 12
DEFAULT_MAX_SECONDS = 600  # 10 minutes

SYSTEM = """You are aubieeternal Build's autonomy loop, running on the Ryzen \
rig (hostname aubieeternal), cwd {cwd}. You were given ONE goal and must \
drive yourself to it, one tool call at a time, deciding the next step from \
the result of the last one. Do not ask the human what to do next — decide, \
act, check the result, adjust.

GOAL: {goal}

Rules:
- Call exactly one tool per turn. Read before you write. After editing a
  .py file, expect an automatic py_compile check appended to the result —
  read it and fix syntax errors before moving on.
- When the goal requires one of these, call request_approval(action, reason)
  instead of doing it directly — a human must approve first: git commit or
  push; systemctl restart/stop/disable of any service; deleting a file;
  installing or upgrading a package (pip/apt); touching anything under
  institute_memory/; writing to or SSHing into the aubie-tutor board
  (100.66.110.65). Attempting these through another tool will be blocked
  anyway and costs you a turn, so ask up front.
- When the goal is actually accomplished, call finish_task(summary, success)
  with success=true and a short summary of what changed and how you verified
  it (or why you could not verify it, e.g. hardware unreachable).
- If you get stuck or the goal turns out to be impossible as stated, call
  finish_task(summary, success) with success=false and say why.
"""

EXTRA_TOOLS = [
    {"type": "function", "function": {
        "name": "finish_task",
        "description": "Call this when the goal is done (or definitively "
                        "cannot be done). Ends the loop.",
        "parameters": {"type": "object", "properties": {
            "summary": {"type": "string"},
            "success": {"type": "boolean"},
        }, "required": ["summary", "success"]},
    }},
    {"type": "function", "function": {
        "name": "request_approval",
        "description": "Ask a human to approve a gated action (git commit/"
                        "push, systemctl restart/stop/disable, deleting a "
                        "file, installing a package, touching "
                        "institute_memory/, or writing to the UNO Q board) "
                        "before it runs. The loop stops here until answered.",
        "parameters": {"type": "object", "properties": {
            "action": {"type": "string", "description": "The exact command "
                       "or tool call you want to run."},
            "reason": {"type": "string", "description": "Why it's needed."},
        }, "required": ["action", "reason"]},
    }},
]

# ── Guardrails: mechanical filter, runs on every tool call regardless of ────
# which tool name the model used. Prompt-only instructions are advisory;
# this is the actual stop.
_GATED_COMMAND_PATTERNS = [
    ("git_commit_or_push", re.compile(r"\bgit\s+(commit|push)\b")),
    ("systemctl_mutate", re.compile(r"\bsystemctl\s+(restart|stop|disable)\b")),
    ("delete_file", re.compile(r"(^|[;&|]|\s)(rm|unlink|shred|rmdir)\s")),
    ("package_install", re.compile(
        r"\b(pip3?\s+install|apt(-get)?\s+(install|upgrade|dist-upgrade|remove))\b")),
    ("uno_q_board", re.compile(r"100\.66\.110\.65|arduino@|DOG_SSH")),
]
_SENSITIVE_PATH_RE = re.compile(r"institute_memory")
_GATED_KIT_TOOLS = {"sketch_push", "sketch_write", "dog_command"}


def check_gate(name: str, args: dict) -> Optional[str]:
    """Return a human-readable reason string if this tool call is gated and
    must not run without approval, else None."""
    args = args or {}
    blob = json.dumps(args, default=str)

    if _SENSITIVE_PATH_RE.search(blob):
        return "touches institute_memory/ (sensitive nonprofit info)"

    if name == "use_tool":
        kit = ql._pick(args, "tool", "name")
        inner = ""
        extra = args.get("args") if isinstance(args.get("args"), dict) else {}
        if isinstance(extra, dict):
            inner = str(extra.get("tool") or extra.get("name") or "")
        if kit in _GATED_KIT_TOOLS or inner in _GATED_KIT_TOOLS:
            gated_name = inner if inner in _GATED_KIT_TOOLS else kit
            return f"house kit '{gated_name}' writes to the UNO Q board"

    if name in ("run_terminal_command", "write"):
        command = ql._pick(args, "command") if name == "run_terminal_command" else ""
        haystack = command or blob
        for tag, pattern in _GATED_COMMAND_PATTERNS:
            if pattern.search(haystack):
                return f"matches gated pattern '{tag}'"

    return None


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class RunLog:
    """self_audit.py-style logging: JSONL steps + a latest.json snapshot +
    a human-readable transcript, so Mateo can read back what happened
    without decoding raw chat messages."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.dir = LOG_ROOT / run_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.steps_path = self.dir / "steps.jsonl"
        self.latest_path = self.dir / "latest.json"
        self.md_path = self.dir / "run.md"
        self.messages_path = self.dir / "messages.json"

    def step(self, event_type: str, **fields) -> None:
        rec = {"ts": _now(), "run_id": self.run_id, "type": event_type, **fields}
        with self.steps_path.open("a") as f:
            f.write(json.dumps(rec, default=str) + "\n")
        self._append_md(rec)
        print(f"[{rec['ts']}] {event_type}: " +
              json.dumps({k: v for k, v in fields.items() if k != "result"}, default=str)[:200])

    def _append_md(self, rec: dict) -> None:
        t = rec["type"]
        with self.md_path.open("a") as f:
            if t == "start":
                f.write(f"# Agent loop run `{self.run_id}`\n\n"
                        f"**Goal:** {rec.get('goal')}\n\n"
                        f"Started {rec['ts']}, model `{rec.get('model')}`, "
                        f"cwd `{rec.get('cwd')}`.\n\n")
            elif t == "tool_call":
                f.write(f"### Step {rec.get('iteration')}: propose `{rec.get('name')}`\n"
                        f"```json\n{json.dumps(rec.get('args'), indent=2, default=str)}\n```\n")
            elif t == "tool_result":
                f.write(f"**Executed.** Result:\n```\n{str(rec.get('result'))[:2000]}\n```\n\n")
            elif t == "blocked":
                f.write(f"**BLOCKED — needs human approval.** Reason: {rec.get('reason')}\n"
                        f"Proposed action: `{rec.get('name')}` "
                        f"`{json.dumps(rec.get('args'), default=str)}`\n\n"
                        f"To let it proceed: `python3 agent_loop.py --resume {self.run_id} --approve`\n"
                        f"To refuse: `python3 agent_loop.py --resume {self.run_id} --deny \"reason\"`\n\n")
            elif t == "approved":
                f.write(f"**Approved by human.** Executing the pending action.\n")
            elif t == "denied":
                f.write(f"**Denied by human.** Reason: {rec.get('reason')}\n\n")
            elif t == "finish":
                ok = "✅ success" if rec.get("success") else "❌ not done"
                f.write(f"\n## Finished — {ok}\n\n{rec.get('summary')}\n")
            elif t == "bounded_out":
                f.write(f"\n## Stopped — {rec.get('reason')}\n")

    def snapshot(self, **fields) -> None:
        data = {"run_id": self.run_id, "updated": _now(), **fields}
        self.latest_path.write_text(json.dumps(data, indent=2, default=str))

    def save_messages(self, messages: list[dict]) -> None:
        self.messages_path.write_text(json.dumps(messages, default=str))

    def load_messages(self) -> list[dict]:
        if self.messages_path.is_file():
            return json.loads(self.messages_path.read_text())
        return []


def _auto_check(name: str, args: dict, result: str, cwd: str) -> str:
    """Minimal 'check' step: after writing a .py file, compile it and append
    pass/fail to the tool result the model sees, so it can fix its own
    syntax errors on the next turn instead of the human catching it later."""
    if name != "write":
        return result
    path = ql._pick(args, "file_path", "path", "target_file")
    if not path.endswith(".py"):
        return result
    try:
        p = subprocess.run(
            [sys.executable, "-m", "py_compile", path],
            cwd=cwd, capture_output=True, text=True, timeout=20,
        )
        if p.returncode == 0:
            return result + "\n[auto-check] py_compile: ok"
        return result + f"\n[auto-check] py_compile FAILED:\n{(p.stdout + p.stderr)[:800]}"
    except Exception as exc:
        return result + f"\n[auto-check] py_compile error: {exc}"


def _call_model(messages: list[dict], model: str) -> dict:
    ollama_model = ql.MODEL_MAP.get(model, "qwen2.5:14b")
    with httpx.Client(timeout=180) as client:
        r = client.post(ql.OLLAMA, json={
            "model": ollama_model,
            "messages": messages,
            "tools": ql.TOOLS + EXTRA_TOOLS,
            "stream": False,
        })
        r.raise_for_status()
        return r.json()["choices"][0]["message"]


def _parse_tool_call(tc: dict) -> tuple[str, dict, str]:
    fn = tc.get("function") or {}
    name = fn.get("name") or "tool"
    raw = fn.get("arguments") or "{}"
    try:
        args = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except json.JSONDecodeError:
        args = {}
    return name, args, (tc.get("id") or name)


def start(goal: str, cwd: str, model: str, max_iterations: int, max_seconds: int) -> str:
    run_id = uuid.uuid4().hex[:12]
    log = RunLog(run_id)
    messages = [
        {"role": "system", "content": SYSTEM.format(cwd=cwd, goal=goal)},
        {"role": "user", "content": goal},
    ]
    log.step("start", goal=goal, model=model, cwd=cwd,
              max_iterations=max_iterations, max_seconds=max_seconds)
    log.snapshot(status="running", goal=goal, iteration=0)
    _drive(log, messages, cwd, model, max_iterations, max_seconds, start_iteration=0, start_time=time.time())
    return run_id


def resume(run_id: str, approve: bool, deny_reason: Optional[str],
           cwd: str, model: str, max_iterations: int, max_seconds: int) -> None:
    log = RunLog(run_id)
    if not log.latest_path.is_file():
        print(f"no such run: {run_id}")
        sys.exit(1)
    latest = json.loads(log.latest_path.read_text())
    pending_path = log.dir / "pending_action.json"
    if latest.get("status") != "awaiting_approval" or not pending_path.is_file():
        print(f"run {run_id} is not awaiting approval (status={latest.get('status')})")
        sys.exit(1)
    pending = json.loads(pending_path.read_text())
    messages = log.load_messages()

    if approve:
        log.step("approved", name=pending["name"], args=pending["args"])
        result = ql._exec(pending["name"], pending["args"], cwd)
        result = _auto_check(pending["name"], pending["args"], result, cwd)
        log.step("tool_result", name=pending["name"], result=result)
        messages.append({"role": "tool", "tool_call_id": pending["tool_call_id"],
                          "content": result[:8000]})
    else:
        reason = deny_reason or "denied by operator, no reason given"
        log.step("denied", name=pending["name"], args=pending["args"], reason=reason)
        messages.append({"role": "tool", "tool_call_id": pending["tool_call_id"],
                          "content": f"DENIED by human operator: {reason}"})
    pending_path.unlink(missing_ok=True)
    log.snapshot(status="running", iteration=latest.get("iteration", 0))
    _drive(log, messages, cwd, model, max_iterations, max_seconds,
           start_iteration=latest.get("iteration", 0), start_time=time.time())


def _drive(log: RunLog, messages: list[dict], cwd: str, model: str,
           max_iterations: int, max_seconds: int, start_iteration: int, start_time: float) -> None:
    iteration = start_iteration
    while True:
        if iteration - start_iteration >= max_iterations:
            log.step("bounded_out", reason=f"hit max_iterations={max_iterations}")
            log.snapshot(status="bounded_out_iterations", iteration=iteration)
            return
        if time.time() - start_time >= max_seconds:
            log.step("bounded_out", reason=f"hit max_seconds={max_seconds}")
            log.snapshot(status="bounded_out_time", iteration=iteration)
            return

        try:
            msg = _call_model(messages, model)
        except Exception as exc:
            log.step("bounded_out", reason=f"model call failed: {exc}")
            log.snapshot(status="error", iteration=iteration)
            return

        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            # Model spoke instead of calling a tool. Treat as an ambiguous
            # stop (mirrors qwen_loop.py's single-turn convention) rather
            # than guessing at completion.
            content = msg.get("content") or ""
            log.step("finish", summary=content or "(model stopped calling tools, no summary given)",
                      success=None)
            log.snapshot(status="done_ambiguous", iteration=iteration)
            log.save_messages(messages)
            return

        messages.append(msg)
        iteration += 1

        for tc in tool_calls:
            name, args, tool_call_id = _parse_tool_call(tc)
            log.step("tool_call", iteration=iteration, name=name, args=args)

            if name == "finish_task":
                log.step("finish", summary=args.get("summary", ""), success=args.get("success"))
                log.snapshot(status="done", iteration=iteration,
                             success=args.get("success"), summary=args.get("summary"))
                log.save_messages(messages)
                return

            if name == "request_approval":
                pending = {"name": "run_terminal_command",
                           "args": {"command": args.get("action", "")},
                           "tool_call_id": tool_call_id,
                           "reason": args.get("reason", "")}
                (log.dir / "pending_action.json").write_text(json.dumps(pending, indent=2))
                log.step("blocked", name="request_approval", args=args,
                         reason=args.get("reason", "model asked for approval"))
                log.snapshot(status="awaiting_approval", iteration=iteration)
                log.save_messages(messages)
                return

            reason = check_gate(name, args)
            if reason:
                pending = {"name": name, "args": args, "tool_call_id": tool_call_id, "reason": reason}
                (log.dir / "pending_action.json").write_text(json.dumps(pending, indent=2))
                log.step("blocked", name=name, args=args, reason=reason)
                log.snapshot(status="awaiting_approval", iteration=iteration)
                log.save_messages(messages)
                return

            result = ql._exec(name, args, cwd)
            result = _auto_check(name, args, result, cwd)
            log.step("tool_result", name=name, result=result)
            messages.append({"role": "tool", "tool_call_id": tool_call_id,
                              "content": result[:8000]})

        log.save_messages(messages)
        log.snapshot(status="running", iteration=iteration)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("goal", nargs="?", help="The task, one clear sentence.")
    ap.add_argument("--cwd", default=str(Path.home() / "AUBIEETERNAL"))
    ap.add_argument("--model", default="qwen2.5:14b")
    ap.add_argument("--max-iterations", type=int, default=DEFAULT_MAX_ITERATIONS)
    ap.add_argument("--max-seconds", type=int, default=DEFAULT_MAX_SECONDS)
    ap.add_argument("--resume", metavar="RUN_ID")
    ap.add_argument("--approve", action="store_true")
    ap.add_argument("--deny", metavar="REASON")
    ap.add_argument("--status", metavar="RUN_ID")
    args = ap.parse_args()

    if args.status:
        p = LOG_ROOT / args.status / "latest.json"
        print(p.read_text() if p.is_file() else f"no such run: {args.status}")
        return

    if args.resume:
        if not args.approve and args.deny is None:
            print("--resume requires --approve or --deny \"reason\"")
            sys.exit(1)
        os.chdir(args.cwd)
        resume(args.resume, args.approve, args.deny, args.cwd, args.model,
               args.max_iterations, args.max_seconds)
        return

    if not args.goal:
        ap.print_help()
        sys.exit(1)

    # qwen_loop._exec's read_file/write resolve relative paths against the
    # process's actual OS cwd, not the --cwd string alone (run_terminal_command
    # is the only tool that gets --cwd passed through explicitly) - chdir here
    # so every tool agrees on one working directory regardless of which one
    # the model uses a relative path with.
    os.chdir(args.cwd)
    run_id = start(args.goal, args.cwd, args.model, args.max_iterations, args.max_seconds)
    print(f"\nrun_id: {run_id}")
    print(f"log: {LOG_ROOT / run_id / 'run.md'}")


if __name__ == "__main__":
    main()

"""aubieeternal Build talks to local Qwen via Ollama — no Grok in the middle."""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import uuid
from pathlib import Path
from typing import Any, AsyncIterator, Optional

import httpx

OLLAMA = "http://127.0.0.1:11434/v1/chat/completions"
MODEL_MAP = {"qwen-14b": "qwen2.5:14b", "qwen-7b": "qwen2.5:7b", "qwen2.5:14b": "qwen2.5:14b", "qwen2.5:7b": "qwen2.5:7b"}
SESS = Path.home() / "AUBIEETERNAL" / "memory" / "self_audit" / "qwen_sessions"
SESS.mkdir(parents=True, exist_ok=True)

SYSTEM = """You are aubieeternal Build, the coding agent on this Ryzen rig (hostname aubieeternal).
You are ON the machine. cwd is {cwd}. Never invent /home/aubieeternal/my_project.
Use tools. Prefer list_dir then read_file on README.md / CLAUDE.md to explain the repo.
You may pass target_directory OR directory_path; target_file OR file_path — both work.
search_tool: pass query (name also works). Then use_tool if you need a house kit.
Keep answers short. Do not claim you lack filesystem access.
"""

TOOLS = [
    {"type": "function", "function": {
        "name": "list_dir",
        "description": "List a directory. Use the repo cwd if unsure.",
        "parameters": {"type": "object", "properties": {
            "target_directory": {"type": "string"},
            "directory_path": {"type": "string"},
            "path": {"type": "string"},
        }},
    }},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read a text file.",
        "parameters": {"type": "object", "properties": {
            "target_file": {"type": "string"},
            "file_path": {"type": "string"},
            "path": {"type": "string"},
        }},
    }},
    {"type": "function", "function": {
        "name": "grep",
        "description": "Search file contents with a regex.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
            "pattern": {"type": "string"},
        }, "required": ["pattern"]},
    }},
    {"type": "function", "function": {
        "name": "run_terminal_command",
        "description": "Run a shell command on the Ryzen rig.",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string"},
        }, "required": ["command"]},
    }},
    {"type": "function", "function": {
        "name": "write",
        "description": "Write a file.",
        "parameters": {"type": "object", "properties": {
            "file_path": {"type": "string"},
            "content": {"type": "string"},
        }, "required": ["file_path", "content"]},
    }},
    {"type": "function", "function": {
        "name": "search_tool",
        "description": "Find a house kit (aubie/toolbox). query or name.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"},
            "name": {"type": "string"},
        }},
    }},
    {"type": "function", "function": {
        "name": "use_tool",
        "description": "Run a house kit after search_tool. tool=list_kits or run_kit, etc.",
        "parameters": {"type": "object", "properties": {
            "tool": {"type": "string"},
            "name": {"type": "string"},
            "args": {"type": "object"},
        }},
    }},
]


def _pick(args: dict, *keys, default=""):
    for k in keys:
        v = args.get(k)
        if v not in (None, ""):
            return str(v)
    return default


def _run_shell(cmd: str, cwd: str, timeout: int = 30) -> str:
    bad = ("rm -rf /", "mkfs", "shutdown", "reboot", "poweroff")
    if any(b in cmd for b in bad):
        return "blocked"
    try:
        p = subprocess.run(
            ["bash", "-c", cmd], cwd=cwd, capture_output=True, text=True, timeout=timeout,
        )
        out = ((p.stdout or "") + (p.stderr or "")).strip()
        return (out or "(no output)")[:6000]
    except Exception as exc:
        return f"error: {exc}"


def _exec(name: str, args: dict, cwd: str) -> str:
    args = args or {}
    if name == "list_dir":
        path = _pick(args, "target_directory", "directory_path", "path", default=cwd)
        return _run_shell(f"ls -la {shlex.quote(path)} | head -80", cwd)
    if name == "read_file":
        path = _pick(args, "target_file", "file_path", "path")
        if not path:
            return "need target_file"
        p = Path(path)
        if not p.is_file():
            return f"not a file: {path} (cwd is {cwd})"
        return p.read_text(errors="replace")[:12000]
    if name == "grep":
        pattern = args.get("pattern") or ""
        path = _pick(args, "path", default=cwd)
        return _run_shell(
            f"rg -n --max-count 40 {shlex.quote(pattern)} {shlex.quote(path)} 2>/dev/null | head -60",
            cwd,
        )
    if name == "run_terminal_command":
        return _run_shell(_pick(args, "command"), cwd)
    if name == "write":
        path = _pick(args, "file_path", "path", "target_file")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(args.get("content") or "")
        return f"wrote {path}"
    if name == "search_tool":
        q = _pick(args, "query", "name", default="kit")
        return (
            "House kits:\n"
            "- toolbox list_kits / run_kit (dog_status, system_info, build_errors, sketch_local, …)\n"
            "- aubie catch_errors, monitor_log, rig_status, aubie_command\n"
            f"query was: {q}\n"
            "Call use_tool with {\"tool\":\"run_kit\",\"args\":{\"tool\":\"build_errors\"}} "
            "or {\"tool\":\"list_kits\"}."
        )
    if name == "use_tool":
        kit = _pick(args, "tool", "name")
        extra = args.get("args") if isinstance(args.get("args"), dict) else {}
        try:
            import sys
            sys.path.insert(0, "/home/aubieeternal/AUBIEETERNAL")
            from agent_toolbox import all_tools
            tools = all_tools()
            if kit == "list_kits":
                return "\n".join(f"- {n}: {d}" for n, (_f, d) in sorted(tools.items()))
            if kit == "run_kit":
                inner = extra.get("tool") or extra.get("name") or ""
                if inner in tools:
                    return str(tools[inner][0](extra.get("args") or extra, "qwen"))[:6000]
                return f"unknown kit {inner}"
            if kit in tools:
                return str(tools[kit][0](extra, "qwen"))[:6000]
            return f"unknown tool {kit}"
        except Exception as exc:
            return f"kit error: {exc}"
    return f"unknown tool {name}"


def _load(sid: str) -> list[dict]:
    p = SESS / f"{sid}.json"
    if p.is_file():
        return json.loads(p.read_text())
    return []


def _save(sid: str, messages: list[dict]) -> None:
    (SESS / f"{sid}.json").write_text(json.dumps(messages[-40:]))


async def run_turn(prompt: str, cwd: str, model: str, session_id: Optional[str]) -> AsyncIterator[dict[str, Any]]:
    sid = session_id or str(uuid.uuid4())
    ollama_model = MODEL_MAP.get(model, "qwen2.5:14b")
    messages = _load(sid)
    if not messages:
        messages.append({"role": "system", "content": SYSTEM.format(cwd=cwd)})
    messages.append({"role": "user", "content": prompt})
    yield {"type": "status", "data": "working", "sessionId": sid}

    async with httpx.AsyncClient(timeout=120) as client:
        for _step in range(8):
            r = await client.post(OLLAMA, json={
                "model": ollama_model,
                "messages": messages,
                "tools": TOOLS,
                "stream": False,
            })
            r.raise_for_status()
            msg = r.json()["choices"][0]["message"]
            tool_calls = msg.get("tool_calls") or []
            content = msg.get("content") or ""
            if tool_calls:
                messages.append(msg)
                for tc in tool_calls:
                    fn = tc.get("function") or {}
                    name = fn.get("name") or "tool"
                    raw = fn.get("arguments") or "{}"
                    try:
                        args = json.loads(raw) if isinstance(raw, str) else (raw or {})
                    except json.JSONDecodeError:
                        args = {}
                    tid = tc.get("id") or name
                    yield {"type": "tool_call", "toolCallId": tid, "title": name, "status": "in_progress", "rawInput": args}
                    result = _exec(name, args, cwd)
                    yield {"type": "tool_call_update", "toolCallId": tid, "title": name, "status": "completed", "rawOutput": result[:1500]}
                    messages.append({"role": "tool", "tool_call_id": tid, "content": result[:8000]})
                continue
            if content:
                yield {"type": "text", "data": content}
            break
    _save(sid, messages)
    yield {"type": "end", "sessionId": sid, "stopReason": "end_turn"}

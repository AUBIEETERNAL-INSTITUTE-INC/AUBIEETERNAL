"""
aubieeternal Build — Grok Build-style coding agent on this Ryzen rig.

Web UI:  http://127.0.0.1:8840
         http://100.105.81.27:8840  (Tailscale)
TUI:     `build`  (wraps grok --agent aubieeternal-build)
"""
from __future__ import annotations

import asyncio
import json
import os
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from acp import LiveAgent

HOME = Path.home()
GROK_HOME = Path(os.environ.get("GROK_HOME", HOME / ".grok"))
SESSIONS_ROOT = GROK_HOME / "sessions"
HERE = Path(__file__).resolve().parent
INDEX = HERE / "index.html"
DEFAULT_CWD = str(HOME / "AUBIEETERNAL")
GROK_BIN = os.environ.get("GROK") or str(HOME / ".local/bin/grok")
AGENT = "aubieeternal-build"
TAILSCALE_HOST = "100.105.81.27"
LOCAL_MODELS = {"qwen-14b", "qwen-7b", "qwen2.5:14b", "qwen2.5:7b"}
LOCAL_TOOLS = "read_file,list_dir,grep,search_replace,run_terminal_command,write,search_tool,use_tool"
LOCAL_DENY = "enter_plan_mode,ask_user_question,spawn_subagent"
RULES = (
    "You are aubieeternal Build on this Ryzen box. cwd is the real repo. "
    "You MUST call tools. Never invent paths like /home/aubieeternal/my_project. "
    "Exact tool arguments (wrong names fail): "
    "list_dir {\"target_directory\":\"/home/aubieeternal/AUBIEETERNAL\"} "
    "NOT directory_path. "
    "read_file {\"target_file\":\"/home/aubieeternal/AUBIEETERNAL/README.md\"} "
    "NOT file_path. "
    "grep {\"path\":\"/home/aubieeternal/AUBIEETERNAL\",\"pattern\":\"...\"}. "
    "search_replace {\"file_path\":\"...\",\"old_string\":\"...\",\"new_string\":\"...\"}. "
    "write {\"file_path\":\"...\",\"content\":\"...\"}. "
    "run_terminal_command {\"command\":\"ls\"}. "
    "search_tool {\"query\":\"catch_errors\"} NEVER {\"name\":\"...\"}. "
    "For explain-this-repo: list_dir the cwd, then read README.md and CLAUDE.md."
)

app = FastAPI(title="aubieeternal Build", docs_url=None, redoc_url=None)

_live: dict[str, LiveAgent] = {}
_live_lock = asyncio.Lock()


class ChatRequest(BaseModel):
    prompt: str
    cwd: str = DEFAULT_CWD
    session_id: Optional[str] = None
    model: str = "qwen-14b"


class CancelRequest(BaseModel):
    session_key: str = "default"


def _safe_cwd(cwd: str) -> Path:
    path = Path(cwd).expanduser().resolve()
    if not path.is_dir():
        raise HTTPException(400, f"cwd is not a directory: {cwd}")
    return path


def _session_group(cwd: Path) -> Path:
    return SESSIONS_ROOT / urllib.parse.quote(str(cwd), safe="")


def _read_json(path: Path) -> Optional[dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _list_sessions(cwd: Optional[str] = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not SESSIONS_ROOT.is_dir():
        return out
    groups = []
    if cwd:
        groups = [_session_group(_safe_cwd(cwd))]
    else:
        groups = [p for p in SESSIONS_ROOT.iterdir() if p.is_dir()]
    for group in groups:
        if not group.is_dir():
            continue
        raw_cwd = urllib.parse.unquote(group.name)
        cwd_file = group / ".cwd"
        if cwd_file.is_file():
            try:
                raw_cwd = cwd_file.read_text(encoding="utf-8").strip() or raw_cwd
            except OSError:
                pass
        for sess in group.iterdir():
            if not sess.is_dir():
                continue
            summary = _read_json(sess / "summary.json") or {}
            info = summary.get("info") or {}
            title = (
                summary.get("generated_title")
                or summary.get("session_summary")
                or info.get("id")
                or sess.name
            )
            updated = (
                summary.get("last_active_at")
                or summary.get("updated_at")
                or info.get("updated_at")
            )
            out.append(
                {
                    "id": sess.name,
                    "title": title,
                    "cwd": info.get("cwd") or raw_cwd,
                    "model": summary.get("current_model_id") or info.get("current_model_id"),
                    "updated_at": updated,
                    "messages": summary.get("num_chat_messages")
                    or summary.get("num_messages")
                    or 0,
                }
            )
    out.sort(key=lambda s: s.get("updated_at") or "", reverse=True)
    return out


def _history_from_updates(session_id: str) -> list[dict[str, Any]]:
    """Collapse ACP updates.jsonl into UI-friendly blocks."""
    path = None
    for group in SESSIONS_ROOT.glob("*"):
        candidate = group / session_id / "updates.jsonl"
        if candidate.is_file():
            path = candidate
            break
    if path is None:
        raise HTTPException(404, f"session not found: {session_id}")

    blocks: list[dict[str, Any]] = []
    user_buf: list[str] = []
    asst_buf: list[str] = []
    think_buf: list[str] = []
    tools: dict[str, dict[str, Any]] = {}

    def flush_user():
        if user_buf:
            blocks.append({"type": "user", "text": "".join(user_buf)})
            user_buf.clear()

    def flush_asst():
        if think_buf:
            blocks.append({"type": "thought", "text": "".join(think_buf)})
            think_buf.clear()
        if asst_buf:
            blocks.append({"type": "text", "text": "".join(asst_buf)})
            asst_buf.clear()

    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                update = (rec.get("params") or {}).get("update") or {}
                kind = update.get("sessionUpdate") or ""
                content = update.get("content") or {}
                text = content.get("text") if isinstance(content, dict) else None
                if kind == "user_message_chunk" and text:
                    flush_asst()
                    user_buf.append(text)
                elif kind == "agent_message_chunk" and text:
                    flush_user()
                    asst_buf.append(text)
                elif kind == "agent_thought_chunk" and text:
                    flush_user()
                    think_buf.append(text)
                elif kind == "tool_call":
                    flush_user()
                    flush_asst()
                    tid = update.get("toolCallId") or ""
                    tools[tid] = {
                        "type": "tool_call",
                        "toolCallId": tid,
                        "title": update.get("title") or "tool",
                        "kind": update.get("kind"),
                        "status": update.get("status") or "in_progress",
                        "rawInput": update.get("rawInput"),
                    }
                    blocks.append(tools[tid])
                elif kind == "tool_call_update":
                    tid = update.get("toolCallId") or ""
                    card = tools.get(tid)
                    if card is None:
                        card = {
                            "type": "tool_call",
                            "toolCallId": tid,
                            "title": update.get("title") or "tool",
                            "kind": update.get("kind"),
                            "status": update.get("status"),
                        }
                        tools[tid] = card
                        blocks.append(card)
                    if update.get("status"):
                        card["status"] = update["status"]
                    if update.get("title"):
                        card["title"] = update["title"]
                    if update.get("rawOutput") is not None:
                        card["rawOutput"] = update["rawOutput"]
                    if update.get("rawInput") is not None:
                        card["rawInput"] = update["rawInput"]
    except OSError as exc:
        raise HTTPException(500, str(exc)) from exc

    flush_user()
    flush_asst()
    return blocks


@app.get("/")
async def index():
    if not INDEX.is_file():
        raise HTTPException(500, "index.html missing")
    return FileResponse(INDEX, media_type="text/html")


@app.get("/api/health")
async def health():
    grok_ok = Path(GROK_BIN).is_file() or bool(os.environ.get("GROK"))
    return {
        "ok": True,
        "name": "aubieeternal Build",
        "host": os.uname().nodename,
        "grok": grok_ok,
        "grok_bin": GROK_BIN,
        "default_cwd": DEFAULT_CWD,
        "web": f"http://127.0.0.1:8840",
        "tailscale": f"http://{TAILSCALE_HOST}:8840",
        "kits": ["aubie", "toolbox"],
    }


@app.get("/api/models")
async def models():
    return {
        "default": "qwen-14b",
        "models": [
            {"id": "qwen-14b", "name": "Qwen 2.5 14B (local)", "kind": "local"},
            {"id": "qwen-7b", "name": "Qwen 2.5 7B (local)", "kind": "local"},
            {"id": "grok-4.6", "name": "Grok 4.6", "kind": "cloud"},
            {"id": "grok-4.5", "name": "Grok 4.5", "kind": "cloud"},
        ],
    }


@app.get("/api/sessions")
async def sessions(cwd: Optional[str] = None):
    return {"sessions": _list_sessions(cwd)}


@app.get("/api/session/{session_id}")
async def session_detail(session_id: str):
    blocks = _history_from_updates(session_id)
    meta = next((s for s in _list_sessions() if s["id"] == session_id), None)
    return {"session": meta or {"id": session_id}, "blocks": blocks}


async def _get_agent(cwd: str, model: str, session_id: Optional[str]) -> LiveAgent:
    key = session_id or f"new:{cwd}:{model}"
    async with _live_lock:
        agent = _live.get(key)
        alive = agent and agent.proc and agent.proc.returncode is None
        if alive and agent and agent.cwd == cwd and agent.model == model:
            return agent
        if agent:
            await agent.close()
        agent = LiveAgent(cwd=cwd, model=model)
        sid = await agent.start(resume_id=session_id)
        _live[sid] = agent
        if key != sid:
            _live[key] = agent
        return agent


@app.post("/api/cancel")
async def cancel(req: CancelRequest):
    agent = _live.get(req.session_key)
    if agent:
        await agent.cancel()
        return {"ok": True, "cancelled": True}
    return {"ok": True, "cancelled": False}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    cwd = str(_safe_cwd(req.cwd))
    prompt = req.prompt.strip()
    if not prompt:
        raise HTTPException(400, "prompt is empty")
    model = (req.model or "qwen-14b").strip() or "qwen-14b"
    print(f"[build] chat model={model} cwd={cwd} session={req.session_id or 'new'} prompt={prompt[:80]!r}", flush=True)

    # Local Qwen only tool-calls reliably with a small allowlist (headless --tools).
    if model in LOCAL_MODELS:
        return await _headless_chat(prompt, cwd, model, req.session_id)

    try:
        agent = await _get_agent(cwd, model, req.session_id)
    except Exception as exc:
        raise HTTPException(500, f"could not start aubieeternal Build: {exc}") from exc

    queue = agent.subscribe()

    async def runner():
        try:
            await agent.prompt(prompt)
        except Exception as exc:
            queue.put_nowait({"type": "error", "message": str(exc)[:4000]})
        finally:
            queue.put_nowait(None)

    asyncio.create_task(runner())

    async def events():
        try:
            yield "data: " + json.dumps({"type": "status", "data": "working", "sessionId": agent.session_id}) + "\n\n"
            while True:
                ev = await queue.get()
                if ev is None:
                    break
                if agent.session_id and ev.get("type") == "end":
                    ev["sessionId"] = agent.session_id
                yield f"data: {json.dumps(ev)}\n\n"
        finally:
            agent.unsubscribe(queue)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _headless_chat(prompt: str, cwd: str, model: str, session_id: Optional[str]):
    from qwen_loop import run_turn

    async def events():
        try:
            async for ev in run_turn(prompt, cwd, model, session_id):
                yield f"data: {json.dumps(ev)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)[:4000]})}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/cwd")
async def cwd_info(path: str = DEFAULT_CWD):
    p = Path(path).expanduser()
    exists = p.is_dir()
    return {
        "path": str(p.resolve()) if exists else str(p),
        "exists": exists,
        "name": p.name,
    }

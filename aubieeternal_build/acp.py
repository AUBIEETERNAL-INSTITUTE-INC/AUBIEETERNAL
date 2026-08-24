"""Live Grok Build agent over ACP stdio — same harness as the TUI."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Optional

HOME = Path.home()
GROK_BIN = os.environ.get("GROK") or str(HOME / ".local/bin/grok")
PROFILE = str(HOME / ".grok/agents/aubieeternal-build.md")


def _ui_event(update: dict[str, Any]) -> Optional[dict[str, Any]]:
    kind = update.get("sessionUpdate") or ""
    content = update.get("content") or {}
    text = content.get("text") if isinstance(content, dict) else None
    if kind in ("agent_message_chunk", "agent_message"):
        if text:
            return {"type": "text", "data": text}
        return None
    if kind in ("agent_thought_chunk", "agent_thought"):
        if text:
            return {"type": "thought", "data": text}
        return None
    if kind == "tool_call":
        return {
            "type": "tool_call",
            "toolCallId": update.get("toolCallId"),
            "title": update.get("title") or "tool",
            "kind": update.get("kind"),
            "status": update.get("status") or "in_progress",
            "rawInput": update.get("rawInput") or update.get("raw_input"),
        }
    if kind == "tool_call_update":
        return {
            "type": "tool_call_update",
            "toolCallId": update.get("toolCallId"),
            "title": update.get("title"),
            "kind": update.get("kind"),
            "status": update.get("status"),
            "rawInput": update.get("rawInput") or update.get("raw_input"),
            "rawOutput": update.get("rawOutput") or update.get("raw_output"),
        }
    return None


class LiveAgent:
    """One long-lived `grok agent stdio` process — like leaving Grok Build open."""

    def __init__(self, cwd: str, model: str = "qwen-14b"):
        self.cwd = cwd
        self.model = model
        self.session_id: Optional[str] = None
        self.proc: Optional[asyncio.subprocess.Process] = None
        self._n = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._listeners: list[asyncio.Queue] = []
        self._reader: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._listeners.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self._listeners:
            self._listeners.remove(q)

    def _emit(self, event: dict[str, Any]) -> None:
        for q in list(self._listeners):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

    async def start(self, resume_id: Optional[str] = None) -> str:
        grok = GROK_BIN
        if not Path(grok).exists():
            for c in (HOME / ".local/bin/grok", HOME / ".grok/bin/grok"):
                if c.exists():
                    grok = str(c)
                    break
        env = os.environ.copy()
        env["PATH"] = f"{HOME / '.local/bin'}:{HOME / '.grok/bin'}:" + env.get("PATH", "")
        env["HOME"] = str(HOME)
        cmd = [
            grok, "agent", "--always-approve", "--no-leader",
            "--agent-profile", PROFILE, "-m", self.model, "stdio",
        ]
        self.proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=self.cwd,
        )
        self._reader = asyncio.create_task(self._read_loop())
        asyncio.create_task(self._drain_stderr())
        await self._rpc("initialize", {
            "protocolVersion": 1,
            "clientCapabilities": {"fs": {"readTextFile": True, "writeTextFile": True}},
            "clientInfo": {"name": "aubieeternal-build", "version": "1"},
        })
        if resume_id:
            try:
                result = await self._rpc("session/load", {
                    "sessionId": resume_id,
                    "cwd": self.cwd,
                })
            except Exception:
                result = await self._rpc("session/new", {
                    "cwd": self.cwd,
                    "mcpServers": [],
                    "_meta": {"yoloMode": True},
                })
        else:
            result = await self._rpc("session/new", {
                "cwd": self.cwd,
                "mcpServers": [],
                "_meta": {"yoloMode": True},
            })
        self.session_id = (result or {}).get("sessionId")
        if not self.session_id:
            raise RuntimeError(f"ACP session did not start: {result}")
        return self.session_id

    async def prompt(self, text: str) -> dict[str, Any]:
        if not self.session_id:
            raise RuntimeError("no session")
        self._emit({"type": "status", "data": "working"})
        result = await self._rpc("session/prompt", {
            "sessionId": self.session_id,
            "prompt": [{"type": "text", "text": text}],
        })
        self._emit({"type": "end", "sessionId": self.session_id, "stopReason": "end_turn"})
        return result or {}

    async def cancel(self) -> None:
        if not self.session_id:
            return
        try:
            await self._rpc("session/cancel", {"sessionId": self.session_id})
        except Exception:
            pass

    async def close(self) -> None:
        proc = self.proc
        self.proc = None
        if self._reader:
            self._reader.cancel()
        if proc and proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), 3)
            except Exception:
                proc.kill()

    async def _rpc(self, method: str, params: dict[str, Any], timeout: float = 600) -> Any:
        async with self._lock:
            self._n += 1
            rid = self._n
            fut: asyncio.Future = asyncio.get_event_loop().create_future()
            self._pending[rid] = fut
            msg = {"jsonrpc": "2.0", "id": rid, "method": method, "params": params}
            assert self.proc and self.proc.stdin
            self.proc.stdin.write(json.dumps(msg).encode() + b"\n")
            await self.proc.stdin.drain()
        return await asyncio.wait_for(fut, timeout)

    async def _read_loop(self) -> None:
        assert self.proc and self.proc.stdout
        while True:
            line = await self.proc.stdout.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "id" in obj and ("result" in obj or "error" in obj):
                fut = self._pending.pop(obj["id"], None)
                if fut and not fut.done():
                    if "error" in obj:
                        fut.set_exception(RuntimeError(json.dumps(obj["error"])[:1500]))
                    else:
                        fut.set_result(obj.get("result"))
                continue
            method = obj.get("method") or ""
            params = obj.get("params") or {}
            if method in ("session/update", "x.ai/session/update"):
                update = params.get("update") or params
                ev = _ui_event(update)
                if ev:
                    self._emit(ev)
                sid = params.get("sessionId")
                if sid and not self.session_id:
                    self.session_id = sid

    async def _drain_stderr(self) -> None:
        if not self.proc or not self.proc.stderr:
            return
        while True:
            chunk = await self.proc.stderr.read(4096)
            if not chunk:
                return

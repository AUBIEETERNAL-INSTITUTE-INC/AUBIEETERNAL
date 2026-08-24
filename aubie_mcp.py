#!/usr/bin/env python3
"""
AUBIEETERNAL -- MCP Server
File: /home/aubieeternal/AUBIEETERNAL/aubie_mcp.py

Exposes the whole Aubie stack as MCP tools so Claude can drive it directly.

Install on Ryzen:
    pip install mcp --break-system-packages

Run standalone to test:
    python3 /home/aubieeternal/AUBIEETERNAL/aubie_mcp.py

Connect from another machine over SSH stdio:
    ssh aubieeternal@100.105.81.27 python3 /home/aubieeternal/AUBIEETERNAL/aubie_mcp.py
"""

import asyncio
import json
import os
import subprocess
import sys

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ── Config ─────────────────────────────────────────────────────
RIG = "http://localhost:8800"                 # assistant_server on Ryzen
DOG = "http://100.66.110.65:8420"             # Aubie dog server (Tailscale)
MEMORY_DIR = "/home/aubieeternal/AUBIEETERNAL_MEMORY"
CODE_DIR = "/home/aubieeternal/AUBIEETERNAL"

SHELL_BLOCKLIST = [
    "rm -rf /", "mkfs", "dd if=", ":(){:|:&};:",
    "shutdown", "reboot", "poweroff", "halt",
    "> /dev/sda", "chown -R / ",
]

server = Server("aubie-eternal")


# ── Helpers ────────────────────────────────────────────────────
async def post_json(url: str, payload: dict, timeout: int = 60) -> dict:
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, json=payload)
    try:
        return r.json()
    except Exception:
        return {"status": "error", "detail": r.text[:2000]}


async def get_json(url: str, timeout: int = 20) -> dict:
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(url)
    try:
        return r.json()
    except Exception:
        return {"status": "error", "detail": r.text[:2000]}


def run_shell(cmd: str, timeout: int = 20) -> str:
    for blocked in SHELL_BLOCKLIST:
        if blocked in cmd:
            return "BLOCKED for safety: command contains '" + blocked + "'"
    try:
        p = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True, text=True, timeout=timeout
        )
        out = p.stdout.strip()
        if p.stderr.strip():
            out += ("\n[stderr] " if out else "[stderr] ") + p.stderr.strip()
        return (out or "(no output)")[:6000]
    except subprocess.TimeoutExpired:
        return "Timed out after " + str(timeout) + "s"
    except Exception as e:
        return "Error: " + str(e)


def ok(text: str):
    return [TextContent(type="text", text=text)]


def pretty(obj) -> str:
    if isinstance(obj, str):
        return obj
    return json.dumps(obj, indent=2)[:6000]


# ── Tool definitions ───────────────────────────────────────────
@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="aubie_command",
            description=(
                "Send a natural-language command to the Aubie robot dog. "
                "Examples: 'sit', 'stand', 'walk forward', 'stop', 'shake', 'spin', "
                "'show happy face', 'show dog face', 'show love face', "
                "'say <text>', 'follow me', 'come here'. "
                "The dog must be online (Tailscale 100.66.110.65)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The command to send to Aubie"}
                },
                "required": ["command"],
            },
        ),
        Tool(
            name="aubie_vision",
            description=(
                "Capture a snapshot from Aubie's camera and run YOLO object detection on the Ryzen rig. "
                "Returns a text summary of what the dog currently sees. "
                "Use this to answer 'what does Aubie see right now?'"
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="aubie_distance",
            description="Read the Aubie robot dog's ultrasonic distance sensor. Returns distance in cm.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="rig_shell",
            description=(
                "Run a shell command directly on the Ryzen rig (aubieeternal, Ubuntu). "
                "Use for file listing, disk checks, log reading, grep, service status, etc. "
                "Destructive commands are blocked. Read-only and inspection commands are preferred."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                    "timeout": {"type": "integer", "description": "Seconds before timeout (default 20)"},
                },
                "required": ["command"],
            },
        ),
        Tool(
            name="rig_interpret",
            description=(
                "Give the rig a plain-English task. A local LLM (qwen2.5:14b) writes Python or bash "
                "to accomplish it, runs the code, and returns both the code and its output. "
                "Good for data analysis, file processing, and multi-step computations. "
                "Slower than rig_shell (15-45s) -- prefer rig_shell for simple one-liners."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "Plain-English description of what to do"},
                    "lang": {
                        "type": "string",
                        "enum": ["python", "bash"],
                        "description": "Language to generate (default python)",
                    },
                },
                "required": ["task"],
            },
        ),
        Tool(
            name="rig_browse",
            description=(
                "Use the rig's headless browser (browser-use + Playwright) to browse the real web "
                "and complete a task. Examples: check a product price, look up specs, gather info "
                "from a site. Takes 1-2 minutes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "What to research or find on the web"}
                },
                "required": ["task"],
            },
        ),
        Tool(
            name="memory_search",
            description=(
                "Search the AUBIEETERNAL_MEMORY archive on the rig (about 6,200 backed-up files: "
                "TAX/, AUBIE/, PERSONAL/, PHOTOS/, GOOGLE_DRIVE/). "
                "Searches file NAMES by default; set search_contents=true to grep inside text files too."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term"},
                    "search_contents": {
                        "type": "boolean",
                        "description": "Also grep inside text files (slower). Default false.",
                    },
                    "limit": {"type": "integer", "description": "Max results (default 40)"},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="rig_status",
            description=(
                "Full health snapshot of the Ryzen rig: disk, RAM, uptime, GPU, Ollama models, "
                "assistant service status, and whether the Aubie dog is reachable. "
                "Use this first when diagnosing anything."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="rig_read_file",
            description=(
                "Read a file from the Ryzen rig. Restricted to the AUBIEETERNAL code directory "
                "and the AUBIEETERNAL_MEMORY archive for safety."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path to the file"},
                    "max_lines": {"type": "integer", "description": "Max lines to return (default 300)"},
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="catch_errors",
            description=(
                "Look ahead for boot/runtime problems on the Ryzen rig and the dog: "
                "assistant/build/mcp systemd, Ollama, disk, last aubie_monitor.log lines, "
                "and whether Aubie answers on Tailscale. Use this when something feels off "
                "or after a reboot."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="monitor_log",
            description=(
                "Read the last lines of the dog auto-repair monitor "
                "(/home/aubieeternal/scripts/aubie_monitor.log). "
                "Shows healthy / repaired / failed boot recoveries."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "lines": {"type": "integer", "description": "How many lines (default 30)"},
                },
            },
        ),
    ]


# ── Tool dispatch ──────────────────────────────────────────────
@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    args = arguments or {}

    # ---- Robot dog ----
    if name == "aubie_command":
        cmd = args.get("command", "").strip()
        if not cmd:
            return ok("No command provided.")
        try:
            res = await post_json(DOG + "/dog/command", {"command": cmd}, timeout=15)
            return ok("Sent to Aubie: '" + cmd + "'\n\n" + pretty(res))
        except Exception as e:
            return ok(
                "Could not reach Aubie at " + DOG + "\n"
                "Error: " + str(e) + "\n"
                "The dog may be powered off or off the Tailscale network."
            )

    if name == "aubie_vision":
        try:
            res = await post_json(RIG + "/proxy/vision", {}, timeout=45)
            if "error" in res:
                return ok("Vision failed: " + str(res["error"]))
            summary = res.get("summary") or "(no objects detected)"
            return ok("Aubie currently sees:\n\n" + summary)
        except Exception as e:
            return ok("Vision error: " + str(e))

    if name == "aubie_distance":
        try:
            res = await get_json(RIG + "/proxy/distance", timeout=10)
            return ok(pretty(res))
        except Exception as e:
            return ok("Distance sensor error: " + str(e))

    # ---- Rig shell / code ----
    if name == "rig_shell":
        cmd = args.get("command", "")
        timeout = int(args.get("timeout", 20))
        return ok(run_shell(cmd, timeout))

    if name == "rig_interpret":
        task = args.get("task", "")
        lang = args.get("lang", "python")
        try:
            res = await post_json(
                RIG + "/interpret",
                {"task": task, "lang": lang, "timeout": 30},
                timeout=120,
            )
            code = res.get("code", "")
            output = res.get("output", "")
            rc = res.get("returncode", "?")
            return ok(
                "Generated " + lang + " (exit " + str(rc) + "):\n\n"
                "```" + lang + "\n" + code + "\n```\n\n"
                "Output:\n" + str(output)
            )
        except Exception as e:
            return ok("Interpret error: " + str(e))

    if name == "rig_browse":
        task = args.get("task", "")
        try:
            res = await post_json(RIG + "/browse", {"task": task}, timeout=180)
            return ok(str(res.get("result", pretty(res))))
        except Exception as e:
            return ok("Browse error (may have timed out): " + str(e))

    # ---- Memory archive ----
    if name == "memory_search":
        query = args.get("query", "").strip()
        if not query:
            return ok("No query provided.")
        limit = int(args.get("limit", 40))
        contents = bool(args.get("search_contents", False))

        safe_q = query.replace("'", "'\\''")
        name_cmd = (
            "find " + MEMORY_DIR + " -type f -iname '*" + safe_q + "*' 2>/dev/null "
            "| head -" + str(limit)
        )
        name_hits = run_shell(name_cmd, timeout=30)

        out = "=== Filename matches for '" + query + "' ===\n" + name_hits

        if contents:
            grep_cmd = (
                "grep -ril --include='*.txt' --include='*.md' --include='*.py' "
                "--include='*.json' --include='*.csv' -- '" + safe_q + "' "
                + MEMORY_DIR + " 2>/dev/null | head -" + str(limit)
            )
            grep_hits = run_shell(grep_cmd, timeout=60)
            out += "\n\n=== Files containing '" + query + "' ===\n" + grep_hits

        return ok(out[:6000])

    # ---- Status ----
    if name == "rig_status":
        parts = []
        checks = [
            ("DISK", "df -h / | tail -1"),
            ("RAM", "free -h | head -2"),
            ("UPTIME", "uptime -p"),
            ("GPU", "nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total "
                    "--format=csv,noheader 2>/dev/null || echo 'nvidia-smi unavailable'"),
            ("OLLAMA MODELS", "ollama list 2>/dev/null | head -6"),
            ("ASSISTANT SERVICE", "systemctl is-active aubie-assistant"),
            ("MEMORY ARCHIVE", "du -sh " + MEMORY_DIR + " 2>/dev/null; "
                               "find " + MEMORY_DIR + " -type f 2>/dev/null | wc -l | "
                               "xargs -I{} echo '{} files'"),
            ("CODE FILES", "ls " + CODE_DIR + "/*.py 2>/dev/null | xargs -n1 basename | tr '\\n' ' '"),
        ]
        for label, cmd in checks:
            parts.append("[" + label + "]\n" + run_shell(cmd, timeout=12))

        # Dog reachability
        dog_ping = run_shell("ping -c 1 -W 2 100.66.110.65 >/dev/null 2>&1 "
                             "&& echo 'ONLINE' || echo 'OFFLINE / unreachable'", timeout=8)
        parts.append("[AUBIE DOG]\n" + dog_ping)

        return ok("\n\n".join(parts)[:6000])

    if name == "rig_read_file":
        path = args.get("path", "")
        max_lines = int(args.get("max_lines", 300))
        if not (path.startswith(CODE_DIR) or path.startswith(MEMORY_DIR)):
            return ok(
                "Refused: path must be under " + CODE_DIR + " or " + MEMORY_DIR
            )
        return ok(run_shell("head -" + str(max_lines) + " '" + path + "'", timeout=15))

    if name == "catch_errors":
        parts = [
            "[AUBIE-ASSISTANT] " + run_shell("systemctl is-active aubie-assistant", 8),
            "[AUBIE-MCP] " + run_shell("systemctl is-active aubie-mcp", 8),
            "[AUBIE-BUILD] " + run_shell("systemctl --user is-active aubie-build.service", 8),
            "[OLLAMA] " + run_shell("systemctl is-active ollama 2>/dev/null || pgrep -a ollama | head -1", 8),
            "[DISK] " + run_shell("df -h / | tail -1", 8),
            "[RAM] " + run_shell("free -h | awk 'NR==2{print}'", 8),
            "[AUBIE PING] " + run_shell(
                "ping -c 1 -W 2 100.66.110.65 >/dev/null 2>&1 && echo ONLINE || echo OFFLINE",
                8,
            ),
            "[MONITOR TAIL]\n" + run_shell("tail -n 12 /home/aubieeternal/scripts/aubie_monitor.log 2>/dev/null || echo none", 8),
            "[ASSISTANT LOG]\n" + run_shell("journalctl -u aubie-assistant.service --no-pager -n 8 2>/dev/null | tail -n 8", 8),
            "[SELF-AUDIT]\n" + run_shell("tail -c 2000 /home/aubieeternal/AUBIEETERNAL/memory/self_audit/latest.json 2>/dev/null || echo none", 8),
        ]
        return ok("\n".join(parts)[:6000])

    if name == "monitor_log":
        n = int(args.get("lines", 30) or 30)
        n = max(1, min(n, 200))
        return ok(run_shell("tail -n " + str(n) + " /home/aubieeternal/scripts/aubie_monitor.log 2>/dev/null || echo none", 8))

    return ok("Unknown tool: " + name)


# ── Entrypoint ─────────────────────────────────────────────────
async def run_stdio():
    """Default mode: MCP over stdio (used via SSH from another machine)."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def run_http(host: str = "0.0.0.0", port: int = 8801):
    """
    HTTP/SSE mode: reachable by any device on the Tailscale network.
    Run with:  python3 aubie_mcp.py --http
    Endpoint:  http://100.105.81.27:8801/sse
    """
    import uvicorn
    from starlette.applications import Starlette
    from starlette.routing import Route, Mount
    from starlette.responses import JSONResponse as StarletteJSON
    from mcp.server.sse import SseServerTransport

    sse = SseServerTransport("/messages/")

    async def handle_sse(request):
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    async def health(request):
        return StarletteJSON({"status": "ok", "server": "aubie-eternal-mcp"})

    app = Starlette(
        debug=False,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Route("/health", endpoint=health),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )

    print("Aubie MCP server (HTTP/SSE) on http://" + host + ":" + str(port) + "/sse",
          file=sys.stderr)
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    if "--http" in sys.argv:
        port = 8801
        for i, a in enumerate(sys.argv):
            if a == "--port" and i + 1 < len(sys.argv):
                port = int(sys.argv[i + 1])
        run_http(port=port)
    else:
        asyncio.run(run_stdio())

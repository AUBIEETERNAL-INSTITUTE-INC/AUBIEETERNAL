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

HTTP/SSE mode (Tailscale):
    export AUBIE_MCP_TOKEN="$(openssl rand -hex 32)"
    python3 aubie_mcp.py --http --host 100.105.81.27
  Every request except /health needs:  Authorization: Bearer $AUBIE_MCP_TOKEN
  rig_shell is OFF in HTTP mode unless AUBIE_MCP_ALLOW_SHELL=1.

Requires the 1.x SDK (the low-level Server decorators were removed in 2.x):
    pip install "mcp>=1.2,<2" --break-system-packages
"""

import asyncio
import hmac
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

# Hard caps so a model can't ask for an hour-long command or a million lines.
MAX_SHELL_TIMEOUT = 120
MAX_READ_LINES = 2000
MAX_SEARCH_LIMIT = 200

# Set at startup: stdio (behind SSH) keeps the shell; HTTP needs explicit opt-in.
SHELL_ENABLED = True

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


def clamp(value, default: int, lo: int, hi: int) -> int:
    """Coerce a model-supplied number into [lo, hi]; fall back to default on junk."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(n, hi))


def safe_path(path: str):
    """Resolve symlinks and '..' and return the real path only if it sits inside
    CODE_DIR or MEMORY_DIR. A plain startswith() check lets '../' escape and also
    matches sibling dirs like /home/aubieeternal/AUBIEETERNAL_anything."""
    if not path:
        return None
    real = os.path.realpath(path)
    for root in (CODE_DIR, MEMORY_DIR):
        root_real = os.path.realpath(root)
        try:
            if os.path.commonpath([real, root_real]) == root_real:
                return real
        except ValueError:
            continue
    return None


def run_argv(argv: list, timeout: int = 20) -> str:
    """Run a command WITHOUT a shell, so user text is never parsed as bash."""
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return (p.stdout.strip() or "(no matches)")[:6000]
    except subprocess.TimeoutExpired:
        return "Timed out after " + str(timeout) + "s"
    except Exception as e:
        return "Error: " + str(e)


async def sh(cmd: str, timeout: int = 20) -> str:
    """run_shell off the event loop so one slow command doesn't freeze the server."""
    return await asyncio.to_thread(run_shell, cmd, timeout)


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
                "Read-only and inspection commands only. Disabled in HTTP mode unless the "
                "operator sets AUBIE_MCP_ALLOW_SHELL=1."
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
            # post_json turns non-JSON replies (500 pages, proxy errors) into
            # {"status": "error", "detail": ...}. Treat that as a failure, not as
            # "nothing in view", or the model will confidently report an empty room.
            if not isinstance(res, dict):
                return ok("Vision failed: unexpected response " + pretty(res)[:500])
            if "error" in res or res.get("status") == "error":
                return ok("Vision failed: " + str(res.get("error") or res.get("detail")))
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
        if not SHELL_ENABLED:
            return ok(
                "rig_shell is disabled in HTTP mode. Use rig_status, catch_errors, "
                "rig_read_file or memory_search instead, or connect over SSH stdio."
            )
        cmd = args.get("command", "")
        timeout = clamp(args.get("timeout"), 20, 1, MAX_SHELL_TIMEOUT)
        return ok(await sh(cmd, timeout))

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
        limit = clamp(args.get("limit"), 40, 1, MAX_SEARCH_LIMIT)
        contents = bool(args.get("search_contents", False))

        def first_n(text: str) -> str:
            return "\n".join(text.splitlines()[:limit])

        name_hits = first_n(await asyncio.to_thread(
            run_argv, ["find", MEMORY_DIR, "-type", "f", "-iname", "*" + query + "*"], 30))

        out = "=== Filename matches for '" + query + "' ===\n" + name_hits

        if contents:
            grep_hits = first_n(await asyncio.to_thread(
                run_argv,
                ["grep", "-ril", "-F",
                 "--include=*.txt", "--include=*.md", "--include=*.py",
                 "--include=*.json", "--include=*.csv",
                 "--", query, MEMORY_DIR],
                60,
            ))
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
            parts.append("[" + label + "]\n" + await sh(cmd, 12))

        # Dog reachability
        dog_ping = await sh("ping -c 1 -W 2 100.66.110.65 >/dev/null 2>&1 "
                             "&& echo 'ONLINE' || echo 'OFFLINE / unreachable'", 8)
        parts.append("[AUBIE DOG]\n" + dog_ping)

        return ok("\n\n".join(parts)[:6000])

    if name == "rig_read_file":
        max_lines = clamp(args.get("max_lines"), 300, 1, MAX_READ_LINES)
        real = safe_path(args.get("path", ""))
        if real is None:
            return ok(
                "Refused: path must resolve to a file under " + CODE_DIR + " or " + MEMORY_DIR
            )
        if not os.path.isfile(real):
            return ok("Not a file: " + real)
        # Read in Python, not via `head '<path>'`, so a quote in the path can't
        # break out into the shell.
        lines = []
        try:
            with open(real, "r", errors="replace") as f:
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    lines.append(line)
        except OSError as e:
            return ok("Read error: " + str(e))
        return ok("".join(lines)[:6000] or "(empty file)")

    if name == "catch_errors":
        checks = [
            ("[AUBIE-ASSISTANT] ", "systemctl is-active aubie-assistant"),
            ("[AUBIE-MCP] ", "systemctl is-active aubie-mcp"),
            ("[AUBIE-BUILD] ", "systemctl --user is-active aubie-build.service"),
            ("[OLLAMA] ", "systemctl is-active ollama 2>/dev/null || pgrep -a ollama | head -1"),
            ("[DISK] ", "df -h / | tail -1"),
            ("[RAM] ", "free -h | awk 'NR==2{print}'"),
            ("[AUBIE PING] ", "ping -c 1 -W 2 100.66.110.65 >/dev/null 2>&1 && echo ONLINE || echo OFFLINE"),
            ("[MONITOR TAIL]\n", "tail -n 12 /home/aubieeternal/scripts/aubie_monitor.log 2>/dev/null || echo none"),
            ("[ASSISTANT LOG]\n", "journalctl -u aubie-assistant.service --no-pager -n 8 2>/dev/null | tail -n 8"),
            ("[SELF-AUDIT]\n", "tail -c 2000 /home/aubieeternal/AUBIEETERNAL/memory/self_audit/latest.json 2>/dev/null || echo none"),
        ]
        # Run all checks at once instead of one after another (worst case ~8s, not ~80s).
        results = await asyncio.gather(*(sh(cmd, 8) for _label, cmd in checks))
        parts = [label + out for (label, _cmd), out in zip(checks, results)]
        return ok("\n".join(parts)[:6000])

    if name == "monitor_log":
        n = clamp(args.get("lines"), 30, 1, 200)
        return ok(await sh("tail -n " + str(n) + " /home/aubieeternal/scripts/aubie_monitor.log 2>/dev/null || echo none", 8))

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


def require_token(app, token: str):
    """ASGI wrapper: every HTTP request except /health must carry the bearer token.
    Without this, anything that can reach port 8801 gets every tool, rig_shell included."""
    expected = ("Bearer " + token).encode()

    async def guarded(scope, receive, send):
        if scope["type"] == "http" and scope.get("path") != "/health":
            headers = dict(scope.get("headers") or [])
            given = headers.get(b"authorization", b"")
            if not hmac.compare_digest(given, expected):
                await send({"type": "http.response.start", "status": 401,
                            "headers": [(b"content-type", b"application/json")]})
                await send({"type": "http.response.body",
                            "body": b'{"error": "missing or bad bearer token"}'})
                return
        await app(scope, receive, send)

    return guarded


def run_http(host: str = "127.0.0.1", port: int = 8801):
    """
    HTTP/SSE mode for devices on the Tailscale network.
    Run with:  AUBIE_MCP_TOKEN=... python3 aubie_mcp.py --http --host 100.105.81.27
    Endpoint:  http://100.105.81.27:8801/sse   (header: Authorization: Bearer <token>)

    Binds to localhost by default. Pass --host with the Tailscale IP rather than
    0.0.0.0, which would also expose the server on the home LAN.
    """
    global SHELL_ENABLED
    import uvicorn
    from starlette.applications import Starlette
    from starlette.routing import Route, Mount
    from starlette.responses import JSONResponse as StarletteJSON, Response
    from mcp.server.sse import SseServerTransport

    token = os.environ.get("AUBIE_MCP_TOKEN", "").strip()
    if len(token) < 24:
        sys.exit("Refusing to start HTTP mode: set AUBIE_MCP_TOKEN to a long random value "
                 "(e.g. `openssl rand -hex 32`).")
    SHELL_ENABLED = os.environ.get("AUBIE_MCP_ALLOW_SHELL") == "1"

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
        # Starlette calls whatever the endpoint returns; returning None made
        # every client disconnect log "TypeError: 'NoneType' object is not callable".
        return Response()

    async def health(request):
        return StarletteJSON({"status": "ok", "server": "aubie-eternal-mcp",
                              "shell_enabled": SHELL_ENABLED})

    app = Starlette(
        debug=False,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Route("/health", endpoint=health),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )

    print("Aubie MCP server (HTTP/SSE) on http://" + host + ":" + str(port) + "/sse"
          + " | rig_shell " + ("ON" if SHELL_ENABLED else "OFF"), file=sys.stderr)
    uvicorn.run(require_token(app, token), host=host, port=port, log_level="warning")


def arg_value(flag: str, default):
    for i, a in enumerate(sys.argv):
        if a == flag and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


if __name__ == "__main__":
    if "--http" in sys.argv:
        run_http(host=arg_value("--host", "127.0.0.1"), port=int(arg_value("--port", 8801)))
    else:
        asyncio.run(run_stdio())

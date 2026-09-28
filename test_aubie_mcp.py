#!/usr/bin/env python3
"""
Regression tests for aubie_mcp.py.

Run:  python3 test_aubie_mcp.py        (or: python3 -m pytest test_aubie_mcp.py)

Each test pins down a bug found on 2026-09-28. None of them touch the real rig:
paths are pointed at a temp sandbox and network calls are faked.
"""
import asyncio
import importlib.util
import os
import sys
import tempfile

import httpx

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, "aubie_mcp.py")

spec = importlib.util.spec_from_file_location("aubie_mcp", SERVER)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# ── Sandbox ────────────────────────────────────────────────────
BASE = tempfile.mkdtemp(prefix="aubie_mcp_test_")
for d in ("AUBIEETERNAL", "AUBIEETERNAL_MEMORY", "AUBIEETERNAL_private", "outside"):
    os.makedirs(os.path.join(BASE, d))
with open(os.path.join(BASE, "AUBIEETERNAL", "ok.txt"), "w") as f:
    f.write("line1\nline2\nline3\n")
with open(os.path.join(BASE, "AUBIEETERNAL_MEMORY", "TAX_2025_notes.txt"), "w") as f:
    f.write("receipts for the GPU\n")
with open(os.path.join(BASE, "outside", "secret.txt"), "w") as f:
    f.write("TOP SECRET")
with open(os.path.join(BASE, "AUBIEETERNAL_private", "secret.txt"), "w") as f:
    f.write("SIBLING SECRET")

m.CODE_DIR = os.path.join(BASE, "AUBIEETERNAL")
m.MEMORY_DIR = os.path.join(BASE, "AUBIEETERNAL_MEMORY")


def call(name, args):
    return asyncio.run(m.call_tool(name, args))[0].text


# ── rig_read_file ──────────────────────────────────────────────
def test_read_inside_allowed_dir_works():
    assert call("rig_read_file", {"path": m.CODE_DIR + "/ok.txt", "max_lines": 2}) == "line1\nline2\n"


def test_read_blocks_dotdot_traversal():
    out = call("rig_read_file", {"path": m.CODE_DIR + "/../outside/secret.txt"})
    assert "TOP SECRET" not in out and out.startswith("Refused")


def test_read_blocks_sibling_prefix_dir():
    # "/…/AUBIEETERNAL_private" starts with the string "/…/AUBIEETERNAL"
    out = call("rig_read_file", {"path": os.path.join(BASE, "AUBIEETERNAL_private", "secret.txt")})
    assert "SIBLING SECRET" not in out and out.startswith("Refused")


def test_read_blocks_symlink_escape():
    link = os.path.join(m.CODE_DIR, "sneaky")
    if not os.path.islink(link):
        os.symlink(os.path.join(BASE, "outside"), link)
    out = call("rig_read_file", {"path": link + "/secret.txt"})
    assert "TOP SECRET" not in out


def test_read_path_quote_cannot_run_commands():
    marker = os.path.join(BASE, "PWNED")
    call("rig_read_file", {"path": m.CODE_DIR + "/x' ; touch " + marker + " ; echo '"})
    assert not os.path.exists(marker)


# ── memory_search ──────────────────────────────────────────────
def test_search_finds_files_and_survives_bad_limits():
    for limit in (-5, 0, "abc", 10**9):
        out = call("memory_search", {"query": "TAX", "limit": limit})
        assert "TAX_2025_notes.txt" in out, (limit, out)


def test_search_query_is_not_shell_parsed():
    marker = os.path.join(BASE, "PWNED2")
    call("memory_search", {"query": "x' ; touch " + marker + " ; echo '", "search_contents": True})
    assert not os.path.exists(marker)


def test_search_contents():
    out = call("memory_search", {"query": "GPU", "search_contents": True})
    assert "TAX_2025_notes.txt" in out


# ── aubie_vision ───────────────────────────────────────────────
def test_vision_reports_server_error_instead_of_empty_room():
    real = m.post_json

    async def fake(url, payload, timeout=60):
        return {"status": "error", "detail": "<html>500 Internal Server Error</html>"}

    m.post_json = fake
    try:
        out = call("aubie_vision", {})
    finally:
        m.post_json = real
    assert out.startswith("Vision failed") and "no objects" not in out


# ── rig_shell ──────────────────────────────────────────────────
def test_shell_gated_when_disabled():
    m.SHELL_ENABLED = False
    try:
        out = call("rig_shell", {"command": "echo should-not-run"})
    finally:
        m.SHELL_ENABLED = True
    assert "disabled" in out and "should-not-run" not in out


def test_shell_timeout_is_clamped():
    assert m.clamp(99999, 20, 1, m.MAX_SHELL_TIMEOUT) == m.MAX_SHELL_TIMEOUT
    assert m.clamp("junk", 20, 1, m.MAX_SHELL_TIMEOUT) == 20


# ── HTTP auth ──────────────────────────────────────────────────
def test_http_requires_bearer_token():
    async def inner(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"tools"})

    app = m.require_token(inner, "t" * 32)

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://x") as c:
            assert (await c.get("/sse")).status_code == 401
            assert (await c.get("/sse", headers={"Authorization": "Bearer wrong"})).status_code == 401
            assert (await c.get("/sse", headers={"Authorization": "Bearer " + "t" * 32})).status_code == 200
            assert (await c.get("/health")).status_code == 200

    asyncio.run(run())


# ── End to end: speaks real MCP over stdio ─────────────────────
def test_stdio_handshake_lists_all_tools():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def run():
        params = StdioServerParameters(command=sys.executable, args=[SERVER])
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as session:
                await session.initialize()
                names = {t.name for t in (await session.list_tools()).tools}
                assert {"rig_status", "rig_read_file", "memory_search", "catch_errors"} <= names
                return len(names)

    assert asyncio.run(run()) == 11


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print("PASS", name)
        except Exception as e:
            failed += 1
            print("FAIL", name, "->", repr(e))
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)

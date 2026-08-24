#!/usr/bin/env python3
"""
House toolkit MCP for aubieeternal Build.

One dispatch tool wrapping agent_toolbox.py so Qwen 14 can use the same
kits Claude Code used (dog, sketch, facts, system) without drowning in
40 separate tool schemas.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, "/home/aubieeternal/AUBIEETERNAL")
os.chdir("/home/aubieeternal/AUBIEETERNAL")

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from agent_toolbox import all_tools

server = Server("house-toolkit")


def catalog() -> str:
    tools = all_tools()
    lines = []
    for name, (_fn, desc) in sorted(tools.items()):
        lines.append(f"- {name}: {desc}")
    return "\n".join(lines)


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_kits",
            description="List every house toolkit on the Ryzen rig (dog, sketch, facts, system, photos).",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="run_kit",
            description=(
                "Run a house toolkit by name. Call list_kits first if unsure. "
                "Examples: run_kit tool=dog_status; run_kit tool=system_info; "
                "run_kit tool=sketch_local args={\"start\":1,\"lines\":80}; "
                "run_kit tool=fact_lookup args={\"query\":\"EIN\"}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "tool": {"type": "string", "description": "Toolkit name from list_kits"},
                    "args": {
                        "type": "object",
                        "description": "Arguments for that toolkit",
                        "additionalProperties": True,
                    },
                },
                "required": ["tool"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    args = arguments or {}
    if name == "list_kits":
        return [TextContent(type="text", text=catalog())]
    if name == "run_kit":
        tool_name = str(args.get("tool") or "").strip()
        tools = all_tools()
        if tool_name not in tools:
            return [TextContent(type="text", text=f"unknown kit: {tool_name}\n\n{catalog()}")]
        fn, _desc = tools[tool_name]
        payload = args.get("args") if isinstance(args.get("args"), dict) else {}
        try:
            result = fn(payload, "mcp")
        except Exception as exc:
            result = f"kit_error: {exc}"
        if not isinstance(result, str):
            result = json.dumps(result, default=str)
        return [TextContent(type="text", text=result[:8000])]
    return [TextContent(type="text", text=f"unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

"""
title: M link rewrite (127.0.0.1 -> Tailscale)
version: 0.1.0
description: Open WebUI *Filter* (outlet). Rewrites any 127.0.0.1/localhost link in M's reply to the
  rig's Tailscale address before the user sees it; non user-facing ports become a plain note.
"""
import re

LOCAL_PORT_MAP = {
    "8460": "https://m.tail00eb41.ts.net:8463",
    "8463": "https://m.tail00eb41.ts.net:8463",
    "8080": "http://m.tail00eb41.ts.net:8080",
    "8501": "https://m.tail00eb41.ts.net:8443",
    "8800": "https://m.tail00eb41.ts.net",
}
_LOCAL_URL = re.compile(r"https?://(?:127\.0\.0\.1|localhost|0\.0\.0\.0)(?::(\d+))?(/[^\s)\]>\"']*)?", re.I)


def rewrite(text: str) -> str:
    def sub(m):
        port, path = m.group(1) or "80", m.group(2) or ""
        base = LOCAL_PORT_MAP.get(port)
        return (base + path) if base else "(internal rig address - not a link you can open)"
    return _LOCAL_URL.sub(sub, text or "")


class Filter:
    def outlet(self, body: dict, __user__: dict = None) -> dict:
        for msg in body.get("messages", []):
            if msg.get("role") == "assistant" and isinstance(msg.get("content"), str):
                msg["content"] = rewrite(msg["content"])
        return body

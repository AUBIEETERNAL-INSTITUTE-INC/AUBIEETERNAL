"""
title: M web search (SearXNG, real results)
author: AUBIE rig (draft 2026-10-31)
version: 0.1.0
description: Real web search via the rig's private SearXNG (format=json); gives the model the top 5 title/url/snippet and it may cite ONLY those urls.
"""
import json
import re
import urllib.parse
import urllib.request

try:
    from pydantic import BaseModel, Field
except Exception:  # standalone test without pydantic
    BaseModel = object

    def Field(default=None, **_):
        return default

# Rig-local addresses -> what the user can actually open (Tailscale, tailnet only).
# Note: tailscale serve on :8463 is HTTPS (plain http://...:8463 returns 400).
RIG_LINKS = {
    "M avatar": "https://m.tail00eb41.ts.net:8463",
    "Open WebUI": "http://m.tail00eb41.ts.net:8080",
    "Institute / portal": "https://aubieeternal.tail00eb41.ts.net:8443",
}
LOCAL_PORT_MAP = {
    "8460": "https://m.tail00eb41.ts.net:8463",  # M avatar (local) -> tailscale serve
    "8463": "https://m.tail00eb41.ts.net:8463",
    "8080": "http://m.tail00eb41.ts.net:8080",   # Open WebUI
    "8501": "https://m.tail00eb41.ts.net:8443",  # streamlit -> tailscale serve
    "8800": "https://m.tail00eb41.ts.net",       # assistant_server -> tailscale serve
}
_LOCAL_URL = re.compile(r"https?://(?:127\.0\.0\.1|localhost|0\.0\.0\.0)(?::(\d+))?(/[^\s)\]>\"']*)?", re.I)


def rewrite_local_links(text: str) -> str:
    """Replace 127.0.0.1/localhost links with the Tailscale address, or drop them if not user-facing."""
    def sub(m):
        port, path = m.group(1) or "80", m.group(2) or ""
        base = LOCAL_PORT_MAP.get(port)
        if not base:  # e.g. 8087 SearXNG, 8765 AUBIE runner: not user-facing
            return "(internal rig address - not a link you can open)"
        return base + path
    return _LOCAL_URL.sub(sub, text or "")


def searx_search(query: str, base: str = "http://127.0.0.1:8087", n: int = 5, timeout: int = 15) -> list:
    url = base.rstrip("/") + "/search?" + urllib.parse.urlencode(
        {"q": query, "format": "json", "safesearch": "1"})
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "M-web-search/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8", "replace"))
    out, seen = [], set()
    for it in data.get("results", []):
        u = (it.get("url") or "").strip()
        if not u.startswith(("http://", "https://")) or u in seen or _LOCAL_URL.match(u):
            continue
        seen.add(u)
        snip = re.sub(r"\s+", " ", (it.get("content") or "")).strip()
        out.append({"title": (it.get("title") or u).strip()[:200], "url": u, "snippet": snip[:400]})
        if len(out) >= n:
            break
    return out


def format_for_model(query: str, results: list) -> str:
    if not results:
        return (f"WEB SEARCH for \"{query}\": NO RESULTS.\n"
                "Tell the user plainly the search returned nothing. Do NOT invent results, titles or links.")
    lines = [f"WEB SEARCH RESULTS for \"{query}\" (top {len(results)}, from SearXNG):", ""]
    for i, r in enumerate(results, 1):
        lines += [f"[{i}] {r['title']}", f"    url: {r['url']}", f"    snippet: {r['snippet'] or '(no snippet)'}", ""]
    lines += [
        "RULES FOR YOUR ANSWER:",
        "- Use ONLY the facts in the snippets above. Cite with [n] and the exact url shown.",
        "- Never make up a url, title, quote, number or source. Never link 127.0.0.1, localhost or port 8087.",
        "- If the snippets do not answer the question, say so and offer to search again with other words.",
    ]
    return "\n".join(lines)


class Tools:
    class Valves(BaseModel):
        searxng_url: str = Field(default="http://127.0.0.1:8087", description="SearXNG base url (rig-local)")
        result_count: int = Field(default=5, description="How many results to give the model")

    def __init__(self):
        self.valves = self.Valves() if BaseModel is not object else type("V", (), {"searxng_url": "http://127.0.0.1:8087", "result_count": 5})()

    def web_search(self, query: str) -> str:
        """
        Search the internet and get REAL results (title, url, snippet). Use this whenever the user asks
        to look something up, for news, prices, facts you are unsure of, or "search for ...".
        Only cite urls this tool returns. Never invent results.
        :param query: What to search for, in plain words.
        """
        q = (query or "").strip()
        if not q:
            return "ERROR: empty query. Ask the user what to search for."
        try:
            res = searx_search(q, self.valves.searxng_url, int(self.valves.result_count))
        except Exception as e:
            return (f"WEB SEARCH FAILED ({type(e).__name__}: {e}). Nothing was found. Tell the user search is "
                    "not working right now; do NOT guess results. (Rig check: aubie_task task=\"search check\".)")
        return format_for_model(q, res)

    def rig_links(self) -> str:
        """
        The addresses the user can open from their phone/laptop over Tailscale. Use these instead of any
        127.0.0.1 / localhost address when giving the user a link to the rig.
        """
        return "Rig links (Tailscale, tailnet only):\n" + "\n".join(f"- {k}: {v}" for k, v in RIG_LINKS.items())

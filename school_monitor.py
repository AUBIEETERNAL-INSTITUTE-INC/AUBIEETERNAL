"""
school_monitor.py — weekly competitive-intel scan of other schools'/platforms'
public curricula, for the Institute board, not the business side.

Follows curriculum_autogen.py's shape: fetch → summarize on local Ollama
(qwen2.5:14b, same $0.00 local-only budget, never touches swarm_v4_1.py's
$5/day Grok budget) → write a plain artifact. Nothing here proposes or merges
curriculum changes — see curriculum_proposals.py for that pipeline. This is
read-only research: what are Khan Academy / IXL / FL districts / etc.
actually teaching, so AUBIEETERNAL's own curriculum decisions have real
outside context.

Institute-only output (see CLAUDE.md's three-door memory layout):
/srv/institute/competitive_intel/YYYY-MM-DD.md — never /srv/vanhorn/, never
~/grok/memory.md.

Usage:
    python school_monitor.py                  # weekly run (once/week unless forced)
    python school_monitor.py --force           # run now regardless of last-run date
    python school_monitor.py --only "Khan Academy"   # test a single source
    python school_monitor.py --list            # list configured sources
"""

import argparse
import datetime
import json
import re
from pathlib import Path

import requests

try:
    from model_selector import ranked_try_order
except Exception:
    ranked_try_order = None

OLLAMA_URL    = "http://localhost:11434"
OLLAMA_MODELS = ["qwen2.5:14b", "qwen2.5:7b"]  # static fallback if ranked_try_order is unavailable

OUTPUT_DIR = Path("/srv/institute/competitive_intel")
STATE_PATH = OUTPUT_DIR / "school_monitor_state.json"

USER_AGENT = "AUBIEETERNAL-school-monitor/1.0 (+https://aubieeternal.org; research use only)"
BROWSER_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

# Public curriculum/standards pages to scan. Edit freely — this is meant to
# grow over time, not be exhaustive on day one. Each entry is scanned
# independently; one failing source never blocks the others.
SOURCES = [
    {"name": "Khan Academy", "url": "https://www.khanacademy.org/"},
    {"name": "IXL", "url": "https://www.ixl.com/"},
    {"name": "Florida DOE — B.E.S.T. Standards", "url": "https://www.fldoe.org/academics/standards/subject-areas/"},
    {"name": "Outschool", "url": "https://outschool.com/"},
]


def _load_state() -> dict:
    try:
        if STATE_PATH.exists():
            return json.loads(STATE_PATH.read_text())
    except Exception:
        pass
    return {}


def _save_state(state: dict) -> None:
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(state, indent=2))
    except Exception:
        pass


def already_ran_this_week() -> bool:
    last = _load_state().get("last_run_date")
    if not last:
        return False
    try:
        last_date = datetime.date.fromisoformat(last)
    except Exception:
        return False
    return (datetime.date.today() - last_date).days < 7


def _fetch_text(url: str) -> str | None:
    """Fetches a public URL and strips it down to plain visible text. No
    HTML parser dependency (none is in requirements.txt) — regex stripping
    of script/style blocks and tags is good enough for a summarization
    prompt, not meant to be a precise scraper."""
    r = None
    # Some public sites (fldoe.org failed every week) refuse unknown bot
    # user-agents. Try ours first, then once with a plain browser UA.
    for ua in (USER_AGENT, BROWSER_UA):
        try:
            r = requests.get(url, timeout=25, headers={"User-Agent": ua, "Accept": "text/html"})
            r.raise_for_status()
            break
        except Exception:
            r = None
    if r is None:
        return None

    html = r.text
    html = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;|&amp;|&quot;|&#39;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:6000] or None


def _call_ollama(prompt: str) -> str | None:
    try:
        tags = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        available = [m["name"] for m in tags.json().get("models", [])]
    except Exception:
        available = []

    to_try = (ranked_try_order(available) if ranked_try_order else None) or OLLAMA_MODELS

    for model in to_try:
        try:
            r = requests.post(
                f"{OLLAMA_URL}/api/chat",
                json={"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False},
                timeout=120,
            )
            if r.status_code == 200:
                return r.json().get("message", {}).get("content", "")
        except Exception:
            continue
    return None


def summarize_source(name: str, url: str) -> dict:
    """Fetches one source and asks Ollama what it's teaching. Returns a
    status dict — never raises, so one bad source can't take down the rest
    of a weekly run."""
    page_text = _fetch_text(url)
    if not page_text:
        return {"name": name, "url": url, "ok": False, "reason": "fetch failed"}

    prompt = f"""You are doing competitive-intelligence research for a small
nonprofit learning institute (AUBIEETERNAL) that teaches K-12 topics
plus antifragility, sovereignty, and financial/civic literacy. Below is raw
public webpage text scraped from {name} ({url}). It will contain a lot of
navigation/marketing noise mixed with real content — ignore the noise.

Summarize, in 4-6 bullet points:
- What subjects/skills this source appears to teach or emphasize
- Anything notable about how they structure or deliver it
- Any gap or angle AUBIEETERNAL could learn from or differentiate on

Reply with ONLY the bullet points, no preamble, no headers.

Raw page text:
{page_text}"""

    summary = _call_ollama(prompt)
    if not summary:
        return {"name": name, "url": url, "ok": False, "reason": "ollama call failed"}

    return {"name": name, "url": url, "ok": True, "summary": summary.strip()}


def run_school_monitor(force: bool = False, only: str | None = None) -> dict:
    """Scans configured sources and writes one dated markdown report.
    Returns a small status dict — never raises, safe to call from cron or a
    background thread. Caps to one run per rolling 7 days unless
    force=True, or a single --only source is requested (testing a single
    school never counts as "this week's run")."""
    if not force and only is None and already_ran_this_week():
        return {"ok": False, "reason": "already ran within the last 7 days"}

    sources = SOURCES if not only else [s for s in SOURCES if s["name"].lower() == only.lower()]
    if not sources:
        return {"ok": False, "reason": f"no configured source matches {only!r}"}

    results = [summarize_source(s["name"], s["url"]) for s in sources]

    today = datetime.date.today().isoformat()
    lines = [f"# Competitive Intel — {today}", ""]
    for res in results:
        lines.append(f"## {res['name']}")
        lines.append(f"Source: {res['url']}")
        lines.append("")
        if res["ok"]:
            lines.append(res["summary"])
        else:
            lines.append(f"_Scan failed: {res['reason']}_")
        lines.append("")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT_DIR / f"{today}.md"
    report_path.write_text("\n".join(lines))

    ok_count = sum(1 for r in results if r["ok"])
    failed = [f"{r['name']} ({r['reason']})" for r in results if not r["ok"]]
    if not only:
        # sources_failed is what self_audit's check_school_monitor() reads -
        # a report with a failed source used to look exactly like success.
        _save_state({"last_run_date": today, "report_path": str(report_path),
                     "sources_ok": ok_count, "sources_failed": failed})

    return {
        "ok": True,
        "report_path": str(report_path),
        "sources_scanned": len(results),
        "sources_ok": ok_count,
        "sources_failed": failed,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="run now regardless of the weekly cap")
    parser.add_argument("--only", help="scan a single source by name (see --list), for testing")
    parser.add_argument("--list", action="store_true", help="list configured sources and exit")
    args = parser.parse_args()

    if args.list:
        for s in SOURCES:
            print(f"{s['name']} — {s['url']}")
        raise SystemExit(0)

    result = run_school_monitor(force=args.force, only=args.only)
    print(json.dumps(result, indent=2))

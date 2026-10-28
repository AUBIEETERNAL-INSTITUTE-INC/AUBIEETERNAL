"""
school_monitor.py — weekly scan of how other schools and programs TEACH, for the Institute board.

v2 (2026-10-11). v1 read only each site's homepage (marketing text), so every week said the same
thing. v2:
  * scans specific course / standards / model pages, several per source
  * remembers each page's text: an unchanged page reuses last week's notes (no model call) and is
    marked unchanged; a changed page is re-read and the notes start with "New since last scan: ..."
  * asks for concrete, borrowable FORMAT ideas and named topics with grade levels - never
    "AUBIEETERNAL is better at X" filler
  * skips pages that are JavaScript-only (no readable text) instead of summarizing a menu
  * --probe tests every page and prints how much real text it has, so dead pages can be pruned

Same rules as before: local Ollama only ($0.00), read-only research, nothing here proposes or merges
curriculum changes (curriculum_autogen.py reads the newest report for format ideas only).

Institute-only output: /srv/institute/competitive_intel/YYYY-MM-DD.md.
Never write outside that Institute directory.

Usage:
    python school_monitor.py                  # weekly run (once per 7 days unless forced)
    python school_monitor.py --force          # run now
    python school_monitor.py --probe          # test every page: readable text or not (no model calls)
    python school_monitor.py --only "Khan Academy"   # test one source (writes test-DATE.md)
    python school_monitor.py --list           # list sources and pages
"""

import argparse
import datetime
import hashlib
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
PAGES_PATH = OUTPUT_DIR / "school_monitor_pages.json"   # per-page text hash + last notes

USER_AGENT = "AUBIEETERNAL-school-monitor/2.0 (+https://aubieeternal-institute.org; research use only)"
BROWSER_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

MIN_TEXT = 600      # fewer readable characters than this = a JavaScript-only page, nothing to learn
PAGE_CHARS = 7000   # how much page text the model reads

# Pages to scan. Edit freely. Run --probe after editing: pages that come back "thin" or "failed"
# should be swapped for a different page on the same site. Each page is scanned independently;
# one failing page never blocks the others.
# Khan Academy and Outschool answer scripts with a Cloudflare "Client Challenge" page (checked
# 2026-10-11). That is the site saying no to robots, so they are not scanned; the report lists
# them under "Check by hand" instead of working around the block.
MANUAL = [
    ("Khan Academy", "https://www.khanacademy.org/college-careers-more/financial-literacy"),
    ("Outschool", "https://outschool.com/online-classes/financial-literacy"),
]

SOURCES = [
    {"name": "IXL", "pages": [
        ("Florida standards alignment", "https://www.ixl.com/standards/florida"),
        ("Homepage", "https://www.ixl.com/"),
    ]},
    # fldoe.org returns 403 to any script (checked 2026-10-10); CPALMS is Florida's official standards site.
    {"name": "Florida B.E.S.T. Standards (CPALMS)", "pages": [
        ("Homepage", "https://www.cpalms.org/"),
    ]},
    {"name": "Next Gen Personal Finance", "pages": [
        ("Free curriculum", "https://www.ngpf.org/curriculum/"),
    ]},
    # Small, self-directed schools - closest to a home/co-learning institute
    {"name": "Acton Academy", "pages": [
        ("Model", "https://www.actonacademy.org/"),
    ]},
    {"name": "Prenda microschools", "pages": [
        ("Model", "https://www.prenda.com/"),
    ]},
    {"name": "Alpha School", "pages": [
        ("Model", "https://alpha.school/"),
    ]},
    {"name": "Synthesis", "pages": [
        ("Model", "https://www.synthesis.com/"),
    ]},
]


# ---------------- state ----------------
def _read_json(path: Path) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        pass
    return {}


def _write_json(path: Path, data: dict) -> None:
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))
    except Exception:
        pass


def _load_state() -> dict:
    return _read_json(STATE_PATH)


def _save_state(state: dict) -> None:
    _write_json(STATE_PATH, state)


def already_ran_this_week() -> bool:
    last = _load_state().get("last_run_date")
    if not last:
        return False
    try:
        return (datetime.date.today() - datetime.date.fromisoformat(last)).days < 7
    except Exception:
        return False


# ---------------- fetch ----------------
def _fetch_text(url: str) -> str | None:
    """Public URL -> plain visible text (regex stripping; no HTML parser dependency).
    Some sites refuse unknown bot user-agents, so try ours first, then once as a plain browser."""
    r = None
    for ua in (USER_AGENT, BROWSER_UA):
        try:
            r = requests.get(url, timeout=25, headers={"User-Agent": ua, "Accept": "text/html"})
            r.raise_for_status()
            break
        except Exception:
            r = None
    if r is None:
        return None
    # many sites don't declare a charset; requests then guesses Latin-1 and an em dash becomes "â"
    if not r.encoding or r.encoding.lower() in ("iso-8859-1", "latin-1", "ascii"):
        r.encoding = "utf-8"
    return _content_text(r.text)


_ENT = re.compile(r"&nbsp;|&amp;|&quot;|&#39;|&#x27;|&rsquo;|&lsquo;|&ldquo;|&rdquo;|&mdash;|&ndash;")
BLOCKS = re.compile(r"(?is)<(h[1-4]|p|li|td|dd|blockquote|figcaption)\b[^>]*>(.*?)</\1>")


def _clean(fragment: str) -> str:
    return re.sub(r"\s+", " ", _ENT.sub(" ", re.sub(r"(?s)<[^>]+>", " ", fragment))).strip()


def _content_text(html: str) -> str | None:
    """The readable content of a page: headings, paragraphs and list items, in order, minus menus.
    A menu is many short link-only items, so blocks under 4 words are dropped (headings excepted) and
    repeats are removed. Falls back to all visible text when a page uses no such tags."""
    html = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer|form)\b.*?</\1>", " ", html)
    m = re.search(r"(?is)<main\b.*?</main>", html)
    body = m.group(0) if m else html
    out, seen = [], set()
    for tag, inner in BLOCKS.findall(body):
        t = _clean(inner)
        heading = tag.lower().startswith("h")
        if not t or (not heading and len(t.split()) < 4) or t.lower() in seen:
            continue
        seen.add(t.lower())
        out.append(("## " + t) if heading else t)
    text = "\n".join(out)
    if len(text) < 200:   # page uses almost no content tags: plain visible text instead
        text = _clean(re.sub(r"(?is)<(header)\b.*?</\1>", " ", body))
    return text or None


def _digest(text: str) -> str:
    # dates, counters and years change on every page load; ignore them so "unchanged" means unchanged
    stable = re.sub(r"\d+", "#", text.lower())
    return hashlib.sha256(stable.encode("utf-8", "ignore")).hexdigest()[:16]


# ---------------- model ----------------
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
                json={"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False,
                      "options": {"temperature": 0.2}},
                timeout=180,
            )
            if r.status_code == 200:
                return r.json().get("message", {}).get("content", "")
        except Exception:
            continue
    return None


def _prompt(source: str, label: str, url: str, text: str, previous: str) -> str:
    before = (f"\nNotes from the last scan of this page (for comparison):\n{previous}\n"
              "Start with one bullet '- New since last scan: ...' saying what is different "
              "(or '- New since last scan: nothing notable').\n") if previous else ""
    return f"""You are taking research notes for a small home-learning institute's board.
Below is text from one public web page: {source} - {label} ({url}).
It mixes navigation and marketing with real content. Use only what the text actually shows.
{before}
Write 3 to 6 short bullet points about:
- the specific topics, courses or skills on this page, with grade or age levels if the text shows them
- HOW they teach it: lesson length, practice, mastery checks, projects, discussion, pacing, who leads
- one concrete FORMAT idea a small institute could borrow (structure, not their content or wording)

Rules: do not compare them to any other school, do not praise or criticise, do not invent numbers.
Pages often mix menus with real content - write about whatever real content there is, even if it is
only a few sentences. Only if there is NO information at all about what or how they teach, reply with
exactly: - (page text too thin to tell)
Reply with ONLY the bullet points.

Page text:
{text[:PAGE_CHARS]}"""


THIN = re.compile(r"too thin to tell", re.I)
# bullets that say nothing: missing-info apologies, site furniture, empty change notes
FILLER = re.compile(r"\bno (specific )?(information|details?)\b|\bnot (provided|mentioned|specified|stated)\b|"
                    r"interactive map|cookie|newsletter|\bsign[ -]?up\b|\blog ?in\b|"
                    r"new since last scan:\s*(nothing|none|no (notable|significant))", re.I)


def _numbers_on_page(bullet: str, page: str) -> bool:
    """Every number in a note must appear in the page text (the model is told not to invent them)."""
    page_nums = set(re.findall(r"\d+(?:[.,]\d+)?", page))
    return all(n in page_nums for n in re.findall(r"\d+(?:[.,]\d+)?", bullet))


def _keep(notes: str, page: str) -> tuple[str, int]:
    kept, dropped = [], 0
    for ln in notes.splitlines():
        if THIN.search(ln) or FILLER.search(ln):
            continue
        if not _numbers_on_page(ln, page):
            dropped += 1
            continue
        kept.append(ln)
    return "\n".join(kept), dropped


def _bullets(reply: str) -> str:
    lines = [ln.rstrip() for ln in (reply or "").splitlines() if ln.strip()]
    lines = [("- " + ln.lstrip("*•· ").strip()) if not ln.lstrip().startswith("-") else ln.strip() for ln in lines]
    return "\n".join(lines[:7])


# ---------------- one page ----------------
def scan_page(source: str, label: str, url: str, pages: dict, today: str) -> dict:
    """Never raises. Returns {source,label,url,status,notes,since}; status is
    new | changed | unchanged | thin | failed."""
    key = url
    prev = pages.get(key, {})
    text = _fetch_text(url)
    if not text:
        return {"source": source, "label": label, "url": url, "status": "failed", "reason": "fetch failed"}
    if len(text) < MIN_TEXT:
        return {"source": source, "label": label, "url": url, "status": "thin",
                "reason": f"only {len(text)} characters of readable text (JavaScript-only page)"}
    h = _digest(text)
    if prev.get("hash") == h and prev.get("notes"):
        kept, _ = _keep(prev["notes"], text)   # notes saved before a filter existed get it too
        if re.search(r"(?m)^- ", kept):
            return {"source": source, "label": label, "url": url, "status": "unchanged",
                    "notes": kept, "since": prev.get("changed", prev.get("seen", "?"))}
    reply = _call_ollama(_prompt(source, label, url, text, prev.get("notes", "")))
    if not reply:
        return {"source": source, "label": label, "url": url, "status": "failed", "reason": "ollama call failed"}
    notes, dropped = _keep(_bullets(reply), text)
    if dropped:
        notes += f"\n_({dropped} note(s) dropped: a number in them is not on the page)_"
    if not re.search(r"(?m)^- ", notes):
        return {"source": source, "label": label, "url": url, "status": "thin",
                "reason": "the model found only menus / sign-up text"}
    status = "changed" if prev.get("hash") else "new"
    pages[key] = {"hash": h, "notes": notes, "seen": prev.get("seen", today), "changed": today}
    return {"source": source, "label": label, "url": url, "status": status, "notes": notes}


# ---------------- weekly run ----------------
def _selected(only: str | None) -> list:
    return SOURCES if not only else [s for s in SOURCES if s["name"].lower() == only.lower()]


def run_school_monitor(force: bool = False, only: str | None = None) -> dict:
    """Scans every page and writes one dated markdown report. Never raises. One run per rolling
    7 days unless force=True or a single --only source is requested (a test never counts as the
    week's run and never overwrites the weekly report)."""
    if not force and only is None and already_ran_this_week():
        return {"ok": False, "reason": "already ran within the last 7 days"}
    sources = _selected(only)
    if not sources:
        return {"ok": False, "reason": f"no configured source matches {only!r}"}

    today = datetime.date.today().isoformat()
    pages = _read_json(PAGES_PATH)
    results = {s["name"]: [scan_page(s["name"], label, url, pages, today) for label, url in s["pages"]]
               for s in sources}

    lines = [f"# Competitive Intel — {today}", ""]
    news = [r for rs in results.values() for r in rs if r["status"] in ("new", "changed")]
    lines += ["## What's new this week", ""]
    # "* " not "- ": curriculum_autogen reads "- " lines as teaching-format notes
    lines += ([f"* {r['source']} / {r['label']}: {'first scan' if r['status'] == 'new' else 'page changed'}"
               for r in news] or ["* Nothing changed on any page since the last scan."])
    lines.append("")
    if not only and MANUAL:
        lines += ["## Check by hand", "", "These sites block automated readers, so they are not scanned:", ""]
        lines += [f"* {name}: {url}" for name, url in MANUAL]
        lines.append("")
    for s in sources:
        lines += [f"## {s['name']}", ""]
        for r in results[s["name"]]:
            lines.append(f"### {r['label']}")
            lines.append(f"Source: {r['url']}")
            if r["status"] in ("new", "changed", "unchanged"):
                if r["status"] == "unchanged":
                    lines.append(f"_Unchanged since {r['since']}._")
                lines += ["", r["notes"], ""]
            else:
                lines += [f"_Skipped: {r['reason']}_", ""]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # a one-source test is written beside, not over, the weekly report, so curriculum_autogen
    # (which reads the newest dated report) never sees a partial one
    report_path = OUTPUT_DIR / (f"test-{today}.md" if only else f"{today}.md")
    report_path.write_text("\n".join(lines).rstrip() + "\n")
    _write_json(PAGES_PATH, pages)

    flat = [r for rs in results.values() for r in rs]
    # a SOURCE has failed only when none of its pages gave usable notes; self_audit's
    # check_school_monitor() reads sources_failed, so a single thin page shouldn't page anyone
    failed = [f"{name} ({'; '.join(r.get('reason', r['status']) for r in rs)})"
              for name, rs in results.items() if not any(r["status"] in ("new", "changed", "unchanged") for r in rs)]
    ok_sources = len(results) - len(failed)
    if not only:
        _save_state({"last_run_date": today, "report_path": str(report_path),
                     "sources_ok": ok_sources, "sources_failed": failed,
                     "pages_new_or_changed": len(news),
                     "pages_skipped": [f"{r['source']} / {r['label']}" for r in flat if r["status"] in ("thin", "failed")]})
    return {"ok": True, "report_path": str(report_path), "sources_scanned": len(results),
            "sources_ok": ok_sources, "sources_failed": failed, "pages_scanned": len(flat),
            "pages_new_or_changed": len(news)}


def probe(only: str | None = None) -> list:
    """Fetch every page (no model calls) and report readable-text size. For pruning dead pages."""
    rows = []
    for s in _selected(only):
        for label, url in s["pages"]:
            text = _fetch_text(url)
            n = len(text or "")
            verdict = "FAILED (blocked or missing)" if text is None else ("thin (JavaScript-only)" if n < MIN_TEXT else "ok")
            rows.append((s["name"], label, url, n, verdict))
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="run now regardless of the weekly cap")
    parser.add_argument("--only", help="scan a single source by name (see --list), for testing")
    parser.add_argument("--list", action="store_true", help="list configured sources and pages")
    parser.add_argument("--probe", action="store_true", help="check which pages have readable text (no model calls)")
    parser.add_argument("--show", metavar="URL", help="print the text the model would read from one page")
    args = parser.parse_args()

    if args.list:
        for s in SOURCES:
            print(s["name"])
            for label, url in s["pages"]:
                print(f"   {label}: {url}")
        raise SystemExit(0)
    if args.show:
        t = _fetch_text(args.show)
        print(t[:PAGE_CHARS] if t else "(fetch failed)")
        print(f"\n[{len(t or '')} characters]")
        raise SystemExit(0)
    if args.probe:
        for name, label, url, n, verdict in probe(args.only):
            print(f"{verdict:28} {n:6} chars  {name} / {label}  {url}")
        raise SystemExit(0)
    print(json.dumps(run_school_monitor(force=args.force, only=args.only), indent=2))

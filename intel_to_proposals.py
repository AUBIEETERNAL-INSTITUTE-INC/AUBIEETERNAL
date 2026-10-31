#!/usr/bin/env python3
"""
intel_to_proposals.py - Sunday follow-up to school_monitor.py (Institute only).

school_monitor.py (Sun 7:00 AM) writes /srv/institute/competitive_intel/YYYY-MM-DD.md.
This script (Sun 7:45 AM, user crontab) reads the NEWEST report and, for each page
that is new or changed and whose notes it has not seen before (max 3 a week):

  1. appends one #institute line to /srv/institute/ideas.md (with source + URL), and
  2. drafts ONE lesson from that page's format idea on local Ollama and submits it
     as a PENDING proposal (curriculum_proposals.CurriculumReviewer.submit_lesson),
     with a "sources" list (school, URL, report path) on the proposal.

It never approves anything - a human still uses the portal Review Queue. Drafts go
through curriculum_autogen's checks (validate_candidate, rotating example name,
near_duplicate against live lessons + recent proposals); near-repeats are skipped.
If Ollama is down, the page is left unseen so the next run retries it.

    python3 intel_to_proposals.py              # normal run (skips a report already processed)
    python3 intel_to_proposals.py --dry-run    # show what it would do; no model calls, no writes
    python3 intel_to_proposals.py --force      # re-run on the newest report
    python3 intel_to_proposals.py --mark-seen  # record the newest report as handled, make nothing
Undo: delete the crontab line marked 'intel_to_proposals' (crontab -e).
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

INTEL_DIR = Path("/srv/institute/competitive_intel")
STATE_PATH = INTEL_DIR / "intel_to_proposals_state.json"
AUTHOR = "Aubie (from weekly school scan)"
MAX_PER_RUN = 3


def _load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text())
    except Exception:
        return {"processed_reports": [], "seen_digests": []}


def _save_state(state: dict) -> None:
    state["seen_digests"] = state.get("seen_digests", [])[-500:]
    STATE_PATH.write_text(json.dumps(state, indent=2))


def newest_report() -> Path | None:
    reports = sorted(p for p in INTEL_DIR.glob("20*.md") if re.match(r"\d{4}-\d{2}-\d{2}\.md$", p.name))
    return reports[-1] if reports else None


def parse_report(text: str) -> list:
    """-> [{school, page, url, bullets, status}] where status is new|changed|unchanged|skipped."""
    changed = {}
    pages, school, cur = [], "", None
    in_news = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            in_news = line[3:].strip().lower().startswith("what's new")
            school = line[3:].strip()
            cur = None
            continue
        if in_news:
            m = re.match(r"\*\s+(.+?)\s*/\s*(.+?):\s*(.+)$", line)
            if m:
                changed[(m.group(1).strip(), m.group(2).strip())] = "new" if "first" in m.group(3) else "changed"
            continue
        if line.startswith("### "):
            cur = {"school": school, "page": line[4:].strip(), "url": "", "bullets": [], "status": "unchanged"}
            pages.append(cur)
            continue
        if cur is None:
            continue
        if line.startswith("Source: "):
            cur["url"] = line[8:].strip()
        elif line.startswith("_Skipped"):
            cur["status"] = "skipped"
        elif line.startswith("- "):
            b = line[2:].strip().replace("**", "")
            if not re.search(r"\bgap\b|lacks|does not provide", b, re.I):
                cur["bullets"].append(b)
    for p in pages:
        if p["status"] != "skipped":
            p["status"] = changed.get((p["school"], p["page"]), "unchanged")
    return pages


def digest(page: dict) -> str:
    return hashlib.sha256(("\n".join(page["bullets"]) + page["url"]).encode()).hexdigest()[:16]


def format_idea(page: dict) -> str:
    for b in page["bullets"]:
        if re.search(r"format idea|could borrow|borrow", b, re.I):
            return re.sub(r"^(one\s+)?concrete format idea[^:]*:\s*", "", b, flags=re.I)
    return page["bullets"][0] if page["bullets"] else ""


def draft_lesson(page: dict, report: Path):
    """One validated, non-duplicate lesson dict from this page, 'dup:<reason>', or None (model failed)."""
    import curriculum
    import curriculum_autogen as ca
    existing = [t for _, t, _ in curriculum.all_titles_and_keys()]
    recent = ca._recent_proposals()
    name = ca.todays_name(recent)
    notes = "\n".join(f"- {b}" for b in page["bullets"])[:1500]
    prompt = f"""{ca.VALUES_BLURB}

This week's scan of another learning program, {page['school']} ({page['url']}), found:
{notes}

Turn ONE format idea from these notes (how they structure learning: pacing, practice, mastery
checks, projects, discussion, schedule, who leads) into ONE lesson a learner can actually do in
AUBIEETERNAL. Borrow the FORMAT only; never copy their content, names or wording.
It must NOT be another antifragility / hormesis lesson.

Existing lesson titles and recent proposals (do NOT repeat or closely duplicate):
{'; '.join(existing[:60] + [r['title'] for r in recent[:20]])}

Reply with ONLY a JSON object, no other text, in this exact shape:
{{
  "key": "kebab-case-unique-id",
  "title": "Short punchy lesson title",
  "topic": "One sentence describing what this lesson actually teaches",
  "steelman": "A steelman-style discussion prompt or question",
  "steelman_for": "The strongest honest case FOR the idea, 1-2 sentences",
  "steelman_against": "The strongest honest case AGAINST it or its limits, 1-2 sentences",
  "example_kind": "made-up",
  "example": "Start with 'Imagine {name}, <age>, who ...' - two or three sentences, no real people, no statistics",
  "activity": "One hands-on activity, 10-20 minutes at home, no special equipment",
  "check_questions": ["Three short questions", "that check understanding", "a learner could answer"],
  "age_hint": "one of: All ages, 6+, 7+, 8+, 9+, 10+, 11+, 12+, 13+, 14+",
  "xp": 20,
  "target_track": "How We Learn, or an existing track name if it fits better",
  "rationale": "One sentence on why, naming {page['school']} as the source of the format idea"
}}"""
    feedback = ""
    for _ in range(2):
        reply = ca._call_ollama(prompt + feedback)
        if not reply:
            return None
        cand = ca._extract_json(reply)
        if isinstance(cand, dict):
            cand = ca._swap_example_name(cand, name, recent)
        problems = ca.validate_candidate(cand)
        if problems and isinstance(cand, dict) and all(ca._example_problem(x) for x in problems):
            fixed = ca._made_up_example(cand, name)
            if fixed:
                cand, problems = fixed, []
        if not problems:
            dup = ca.near_duplicate(cand, existing, recent)
            if not dup:
                return cand
            problems = [dup]
            if _ == 1:
                return f"dup:{dup}"
        feedback = "\n\nYour last answer was rejected: " + "; ".join(problems) + ". Fix that and reply with ONLY the JSON."
    return None


def submit(cand: dict, page: dict, report: Path) -> dict:
    import curriculum_autogen as ca
    from curriculum_proposals import CurriculumReviewer, PROPOSALS_DIR
    track = cand.get("target_track") or "How We Learn"
    source = {"school": page["school"], "page": page["page"], "url": page["url"], "report": str(report),
              "borrowed": format_idea(page)[:300]}
    lesson = {
        "key": cand["key"], "title": cand["title"], "topic": cand.get("topic", ""),
        "steelman": cand.get("steelman", ""), "steelman_for": cand.get("steelman_for", ""),
        "steelman_against": cand.get("steelman_against", ""), "example_kind": ca._kind(cand),
        "example": cand.get("example", ""), "activity": cand.get("activity", ""),
        "check_questions": [str(q) for q in (cand.get("check_questions") or [])][:5],
        "age_hint": cand.get("age_hint", "All ages"), "xp": int(cand.get("xp", 20) or 20),
        "rune": f"{track.upper().replace(' ', '•')}•RUNE", "min_coherence": 0.65,
        "sources": [source],
    }
    why = cand.get("rationale") or f"Format idea borrowed from {page['school']} (weekly school scan)."
    if page["school"].lower() not in why.lower():
        why += f" (Source: {page['school']}, {page['url']}.)"
    prop = CurriculumReviewer().submit_lesson(AUTHOR, lesson, target_track=track, rationale=why)
    prop["sources"] = [source]
    prop["source_reports"] = [str(report)]
    (PROPOSALS_DIR / f"{prop['id']}.json").write_text(json.dumps(prop, indent=2))
    return prop


def add_idea(page: dict, report: Path, note: str) -> None:
    try:
        import idea_inbox
        idea_inbox.add_idea(f"#institute From {page['school']} / {page['page']} ({page['url']}, "
                            f"{report.name}): {format_idea(page)[:300]} {note}".strip(), source="school-scan")
    except Exception as e:
        print(f"[intel->proposals] idea not saved: {e}")


def run(force: bool = False, dry_run: bool = False, mark_seen: bool = False) -> dict:
    report = newest_report()
    if not report:
        return {"ok": False, "reason": "no report"}
    state = _load_state()
    if report.name in state.get("processed_reports", []) and not force and not dry_run:
        return {"ok": True, "report": report.name, "reason": "already processed", "created": []}
    pages = parse_report(report.read_text())
    seen = set(state.get("seen_digests", []))
    todo = [p for p in pages if p["status"] in ("new", "changed") and p["bullets"] and digest(p) not in seen]
    todo.sort(key=lambda p: p["status"] != "new")  # first scans first
    if dry_run:
        return {"ok": True, "dry_run": True, "report": report.name,
                "would_process": [{"school": p["school"], "page": p["page"], "status": p["status"],
                                   "idea": format_idea(p)[:160]} for p in todo[:MAX_PER_RUN]],
                "not_this_week": len(todo) - min(len(todo), MAX_PER_RUN)}
    if mark_seen:
        state.setdefault("seen_digests", []).extend(digest(p) for p in pages if p["bullets"])
        state.setdefault("processed_reports", []).append(report.name)
        _save_state(state)
        return {"ok": True, "report": report.name, "marked_seen": len(pages)}
    created, skipped, failed = [], [], 0
    for p in todo[:MAX_PER_RUN]:
        res = draft_lesson(p, report)
        if res is None:
            failed += 1
            continue  # model down/unusable: leave unseen, retry next run
        if isinstance(res, str):
            skipped.append({"school": p["school"], "reason": res[4:]})
            add_idea(p, report, "(lesson draft skipped: near-duplicate)")
        else:
            prop = submit(res, p, report)
            created.append({"id": prop["id"], "title": prop["lesson"]["title"], "school": p["school"]})
            add_idea(p, report, f"(pending proposal {prop['id']})")
        state.setdefault("seen_digests", []).append(digest(p))
    if not failed:
        state.setdefault("processed_reports", []).append(report.name)
    state["last_run"] = datetime.datetime.now().isoformat(timespec="seconds")
    _save_state(state)
    return {"ok": failed == 0, "report": report.name, "created": created, "skipped": skipped,
            "model_failures": failed}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--mark-seen", action="store_true")
    a = ap.parse_args()
    print(datetime.datetime.now().isoformat(timespec="seconds"),
          json.dumps(run(force=a.force, dry_run=a.dry_run, mark_seen=a.mark_seen)))

"""
curriculum_autogen.py — the curriculum should always be trying to grow.

Drafts ONE candidate lesson a day (never a track — a full new track is a
bigger commitment and stays a human-initiated Submit Curriculum thing) and
submits it through curriculum_proposals.py's normal review pipeline as a
*pending* proposal, authored "Aubie (auto-proposed)". It never approves
its own work — a human still evaluates it in the portal's Review Queue
(app.py, Submit Curriculum tab) exactly like a Tommy/Gabriela submission,
and nothing reaches the live curriculum until someone hits Approve (see
curriculum_proposals.merge_approved_proposal).

Runs entirely on local Ollama — $0.00, doesn't touch swarm_v4_1.py's
$5/day Grok budget. Call run_curriculum_autogen() once a day from the
swarm loop (see maybe_trigger_curriculum_autogen() in swarm_v4_1.py), or
on demand (force=True) from a "suggest one now" button.
"""

import datetime
import json
import re
from pathlib import Path

import requests

try:
    from family_profiles import DATA_DIR
except Exception:
    DATA_DIR = Path("/mnt/main")

STATE_PATH   = DATA_DIR / "curriculum_autogen_state.json"
OLLAMA_URL   = "http://localhost:11434"
OLLAMA_MODELS = ["qwen2.5:14b", "qwen2.5:7b"]  # last-resort static fallback if nothing is pulled yet

VALUES_BLURB = (
    "AUBIEETERNAL teaches through a consistent lens: antifragility (systems "
    "that gain from stress), sovereignty (self-reliance, Bitcoin, owning your "
    "own keys/data/decisions), steelmanning (arguing the strongest version of "
    "an idea before judging it), polyvagal safety (co-regulation before "
    "cognition), Stoic practice, Lindy/skin-in-the-game thinking, and genuine "
    "wonder about reality."
)


def _load_state() -> dict:
    try:
        if STATE_PATH.exists():
            return json.loads(STATE_PATH.read_text())
    except Exception:
        pass
    return {}


def _save_state(state: dict) -> None:
    try:
        STATE_PATH.write_text(json.dumps(state, indent=2))
    except Exception:
        pass


def already_ran_today() -> bool:
    return _load_state().get("last_run_date") == datetime.date.today().isoformat()


def _call_ollama(prompt: str) -> str | None:
    from model_selector import ranked_try_order

    try:
        tags = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        available = [m["name"] for m in tags.json().get("models", [])]
    except Exception:
        available = []
    # Hardware-aware: biggest already-pulled model this machine can
    # comfortably run first (see model_selector.py), same reasoning as
    # phone_ui.py's _ollama_chat - a stronger machine should get a better
    # curriculum-proposal generator, not be stuck on a fixed model name.
    to_try = ranked_try_order(available) or OLLAMA_MODELS

    for model in to_try:
        try:
            r = requests.post(
                f"{OLLAMA_URL}/api/chat",
                json={"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False},
                timeout=90,
            )
            if r.status_code == 200:
                return r.json().get("message", {}).get("content", "")
        except Exception:
            continue
    return None


def _extract_json(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


INTEL_DIR = Path("/srv/institute/competitive_intel")


def _outside_structure_notes(max_chars: int = 1200) -> str:
    """Latest weekly school_monitor report, trimmed to how other programs
    STRUCTURE learning (pacing, practice, mastery checks). Drops the 'Gap'
    lines and failed scans. Empty string if there's no report."""
    try:
        reports = sorted(INTEL_DIR.glob("20*.md"))
        if not reports:
            return ""
        notes, source = [], ""
        for line in reports[-1].read_text().splitlines():
            if line.startswith("## "):
                source = line[3:].strip()
            elif line.startswith("- ") and not re.search(r"\bgap\b|lacks|antifragil|sovereign", line, re.I):
                notes.append(f"- ({source}) {line[2:].strip()}")
        text = "\n".join(notes)[:max_chars]
        if not text:
            return ""
        return ("\nHow other learning programs organize lessons (borrow FORMAT ideas only - "
                "pacing, practice, mastery checks; never copy their content, names or wording):\n"
                f"{text}\n")
    except Exception:
        return ""


def _founder_ideas() -> str:
    """Last few #institute ideas from idea_inbox.py, as optional inspiration."""
    try:
        from idea_inbox import recent_ideas
        ideas = [re.sub(r"^\S+ \S+ \[[^\]]*\] ", "", i) for i in recent_ideas("institute", 5)]
        if not ideas:
            return ""
        return ("\nRecent ideas from the founder (use one only if it fits; not required):\n"
                + "\n".join(f"- {i}" for i in ideas) + "\n")
    except Exception:
        return ""


def generate_candidate() -> dict | None:
    """Asks Ollama for one new lesson that fills a real gap — either the
    next level in a track that's thinner than the others, or (occasionally)
    a first lesson toward a plausible new track. Returns a dict shaped for
    CurriculumReviewer.submit_lesson(), or None if generation/parsing failed
    (never raises)."""
    import curriculum

    existing = curriculum.all_titles_and_keys()
    tracks   = curriculum.track_names()
    track_sizes = {}
    for _, _, track_label in existing:
        track_sizes[track_label] = track_sizes.get(track_label, 0) + 1
    thinnest = sorted(track_sizes.items(), key=lambda kv: kv[1])[:3] if track_sizes else []

    existing_titles = "; ".join(t for _, t, _ in existing[:60])
    thin_tracks_str = ", ".join(f"{name} ({n} lessons)" for name, n in thinnest) or "none yet"

    outside = _outside_structure_notes()
    founder = _founder_ideas()

    prompt = f"""{VALUES_BLURB}
{outside}{founder}
Existing lesson titles (do NOT repeat or closely duplicate any of these):
{existing_titles}

Thinnest tracks (good candidates for the next level, but a genuinely
strong new track idea is also welcome): {thin_tracks_str}

Propose exactly ONE new lesson to add to the AUBIEETERNAL curriculum.
Reply with ONLY a JSON object, no other text, in this exact shape:
{{
  "key": "kebab-case-unique-id",
  "title": "Short punchy lesson title",
  "topic": "One sentence describing what this lesson actually teaches",
  "steelman": "A steelman-style discussion prompt or question for this lesson",
  "example": "One concrete real-world example that NAMES a real person, place, event, or thing (e.g. 'Marie Curie kept testing pitchblende for years...'), never 'a historical figure' or 'someone'",
  "activity": "One hands-on activity a learner can do in 10-20 minutes at home with no special equipment",
  "check_questions": ["Three short questions", "that check understanding", "without giving the answer away"],
  "age_hint": "one of: All ages, 7+, 8+, 9+, 10+, 11+, 12+, 13+, 14+, 15+, 16+",
  "xp": 20,
  "target_track": "the existing track name this belongs to, or a new track name if genuinely novel",
  "rationale": "One sentence on why this specific lesson is worth adding now"
}}"""

    feedback = ""
    for _attempt in range(2):  # one retry with the reason it was rejected
        reply = _call_ollama(prompt + feedback)
        if not reply:
            return None
        cand = _extract_json(reply)
        problems = validate_candidate(cand)
        if not problems:
            return cand
        feedback = ("\n\nYour last answer was rejected: " + "; ".join(problems)
                    + ". Fix those and reply with ONLY the JSON object.")
        print(f"[curriculum-autogen] draft rejected: {problems}")
    return None


_VAGUE_EXAMPLE = re.compile(
    r"\b(a|an|one|some)\s+(historical|famous|well-known|real|certain)?\s*"
    r"(figure|person|someone|individual|scientist|inventor|leader|child|student|family|athlete|artist)\b"
    r"|\bsomeone\b|\bsomebody\b|\bimagine a\b|\bfor example, a\b",
    re.I,
)


def _names_something(text: str) -> bool:
    """True if the text contains a capitalized name that is not just the first word of a sentence."""
    words = re.findall(r"(?<![.!?]\s)(?<!^)\b[A-Z][a-z]{2,}", text.strip())
    return len(words) > 0


def validate_candidate(c) -> list:
    """Reasons a draft is not reviewable yet. Empty list = good enough to send to a human."""
    if not isinstance(c, dict):
        return ["reply was not a JSON object"]
    p = []
    for k in ("key", "title", "topic", "example", "activity"):
        if not str(c.get(k, "")).strip():
            p.append(f"missing {k}")
    ex = str(c.get("example", ""))
    if ex and (_VAGUE_EXAMPLE.search(ex) or not _names_something(ex)):
        p.append("example is vague; name a real person, place, event, or thing")
    cq = c.get("check_questions")
    if not isinstance(cq, list) or len([q for q in cq if str(q).strip()]) < 2:
        p.append("need at least 2 check_questions")
    return p


def run_curriculum_autogen(force: bool = False) -> dict:
    """Generates and submits one pending lesson proposal. Returns a small
    status dict — never raises, safe to call from a background thread or a
    UI button. Caps to one run per calendar day unless force=True (used by
    an explicit "suggest one now" button)."""
    if not force and already_ran_today():
        return {"ok": False, "reason": "already ran today"}

    candidate = generate_candidate()
    if not candidate or not candidate.get("key") or not candidate.get("title"):
        return {"ok": False, "reason": "generation failed or returned unusable JSON"}

    from curriculum_proposals import CurriculumReviewer

    lesson = {
        "key":           candidate["key"],
        "title":         candidate["title"],
        "topic":         candidate.get("topic", ""),
        "steelman":      candidate.get("steelman", ""),
        "example":       candidate.get("example", ""),
        "activity":      candidate.get("activity", ""),
        "check_questions": [str(q) for q in (candidate.get("check_questions") or [])][:5],
        "age_hint":      candidate.get("age_hint", "All ages"),
        "xp":            int(candidate.get("xp", 20) or 20),
        "rune":          f"{candidate.get('target_track', 'community').upper().replace(' ', '•')}•RUNE",
        "min_coherence": 0.65,
    }
    target_track = candidate.get("target_track", "community")
    rationale = candidate.get("rationale", "Auto-proposed to keep the curriculum growing.")

    reviewer = CurriculumReviewer()
    proposal = reviewer.submit_lesson(
        author="Aubie (auto-proposed)",
        lesson=lesson,
        target_track=target_track,
        rationale=rationale,
    )

    _save_state({"last_run_date": datetime.date.today().isoformat(), "last_proposal_id": proposal["id"]})
    return {"ok": True, "proposal_id": proposal["id"], "title": lesson["title"], "target_track": target_track}


def send_curriculum_proposed_email(result: dict) -> bool:
    """One email when a pending proposal was actually submitted.

    Uses aubieeternal_build/self_audit.py's Proton Bridge helper. Does not
    send on already-ran, force=False no-op, or generation failure — callers
    must only invoke this when result["ok"] is True, and this function
    checks that again. Never raises. Not the swarm:anomaly_shape channel.
    """
    if not result or not result.get("ok"):
        return False
    title = " ".join(str(result.get("title") or "").split())
    track = str(result.get("target_track") or "")
    proposal_id = str(result.get("proposal_id") or "")
    subject = f"[AUBIEETERNAL] Curriculum proposed: {title}"
    body = (
        f"title: {title}\n"
        f"target_track: {track}\n"
        f"proposal_id: {proposal_id}\n"
        "author: Aubie (auto-proposed)\n"
        "status: pending — not live\n"
        "\n"
        "Review in the portal Review Queue (Submit Curriculum). "
        "Approve is still required. Publish to commons is a separate action.\n"
    )
    try:
        import sys
        build_dir = str(Path(__file__).resolve().parent / "aubieeternal_build")
        if build_dir not in sys.path:
            sys.path.insert(0, build_dir)
        from self_audit import send_alert_email
        return bool(send_alert_email(subject, body))
    except Exception as exc:
        print(f"[curriculum-autogen] propose mail failed: {exc}")
        return False

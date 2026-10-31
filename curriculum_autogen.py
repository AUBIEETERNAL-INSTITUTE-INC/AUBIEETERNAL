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


# ── Variety + duplicate guard (2026-10-30) ──────────────────────────────────
# The daily run kept producing near-copies of the same antifragility/hormesis
# lesson about the same made-up "Ana, 12". Three fixes:
#   1. a rotating daily FOCUS (values + school-report formats), with any theme
#      that dominated the last week dropped from today's pick;
#   2. a rotating example NAME, skipping names used recently;
#   3. a near-duplicate check against live lessons AND recent proposals (any
#      status) - a near-repeat is sent back once with the reason, and after
#      3 tries the day is skipped instead of submitting a copy.
FOCUS_ROTATION = [
    ("Steelmanning", "arguing the strongest version of the other side before judging"),
    ("Sovereignty and Bitcoin", "self-reliance; owning your own keys, data and decisions"),
    ("Stoic practice", "what is in your control and what is not; a small daily Stoic habit"),
    ("Wonder", "real curiosity about how the world works: science, nature, space, how things are made"),
    ("Nervous system safety", "calming the body before thinking; co-regulation with a trusted adult"),
    ("Money basics", "budgeting, saving, credit and interest, taxes on a pay stub, investing"),
    ("Lindy and skin in the game", "trusting what has lasted; advice from people who share the risk"),
    ("Core math", "one concrete math skill taught hands-on with everyday objects"),
    ("Core reading and writing", "one concrete reading or writing skill"),
    ("How we learn", "mastery checks, planning a learning day, project quests, Socratic discussion"),
    ("Courage", "doing the right thing when it is hard or scary"),
    ("Antifragility", "systems that gain from stress"),
]
_THEME_WORDS = {
    "Antifragility": r"antifragil|hormesis|resilien|\bstress",
    "Wonder": r"\bwonder|curiosity",
    "Stoic practice": r"stoic|negative visuali",
    "Steelmanning": r"steelman",
}
EXAMPLE_NAMES = ["Theo", "Mia", "Jonah", "Zara", "Sam", "Priya", "Leo", "Iris", "Noah", "Elena",
                 "Kai", "Ruby", "Omar", "Lucia", "Ben", "Nadia", "Felix", "Hana", "Marcus", "Talia"]
_STOP = set("a an the of for to and in on with your you how through by is are as at from into "
            "it its be can that this what why when our my".split())
LAST_SKIP_REASON = ""


def _recent_proposals(n: int = 30) -> list:
    """Newest-first [{title, topic, example, track}] from curriculum-proposals/ (any status). Never raises."""
    try:
        from curriculum_proposals import PROPOSALS_DIR
        rows = []
        for f in PROPOSALS_DIR.glob("*.json"):
            try:
                p = json.loads(f.read_text())
            except Exception:
                continue
            lessons = [p["lesson"]] if isinstance(p.get("lesson"), dict) else (p.get("lessons") or [])
            for l in lessons:
                if isinstance(l, dict) and l.get("title"):
                    rows.append({"title": str(l.get("title", "")), "topic": str(l.get("topic", "")),
                                 "example": str(l.get("example", "")),
                                 "track": str(p.get("target_track") or p.get("track_name") or ""),
                                 "at": str(p.get("submitted_at", ""))})
        rows.sort(key=lambda r: r["at"], reverse=True)
        return rows[:n]
    except Exception:
        return []


def _theme_of(text: str) -> str:
    for theme, pat in _THEME_WORDS.items():
        if re.search(pat, text or "", re.I):
            return theme
    return ""


def todays_focus(recent: list | None = None, day: datetime.date | None = None) -> tuple:
    """Rotate through FOCUS_ROTATION by date, dropping any theme that showed up in
    2+ of the last 7 proposals (so a run of antifragility lessons forces a change)."""
    recent = _recent_proposals() if recent is None else recent
    day = day or datetime.date.today()
    counts = {}
    for r in recent[:7]:
        t = _theme_of(f"{r['title']} {r['topic']} {r['track']}")
        if t:
            counts[t] = counts.get(t, 0) + 1
    pool = [f for f in FOCUS_ROTATION if counts.get(f[0], 0) < 2] or FOCUS_ROTATION
    return pool[day.toordinal() % len(pool)]


def _example_name(example: str) -> str:
    m = re.match(r"\s*imagine\s+([A-Z][a-z]+)", example or "", re.I)
    return m.group(1) if m else ""


def todays_name(recent: list | None = None, day: datetime.date | None = None) -> str:
    recent = _recent_proposals() if recent is None else recent
    day = day or datetime.date.today()
    used = {_example_name(r["example"]) for r in recent[:14]}
    pool = [n for n in EXAMPLE_NAMES if n not in used] or EXAMPLE_NAMES
    return pool[day.toordinal() % len(pool)]


def _words(text: str) -> set:
    return {w for w in re.findall(r"[a-z]+", (text or "").lower()) if w not in _STOP and len(w) > 2}


def near_duplicate(cand: dict, existing_titles: list, recent: list) -> str:
    """Reason string if cand is a near-repeat of a live lesson or a recent proposal, else ''."""
    from difflib import SequenceMatcher
    title = str((cand or {}).get("title", "")).strip()
    topic = str((cand or {}).get("topic", "")).strip()
    tw, pw = _words(title), _words(topic)
    for other in list(existing_titles) + [r["title"] for r in recent]:
        ow = _words(other)
        if not other:
            continue
        ratio = SequenceMatcher(None, title.lower(), other.lower()).ratio()
        jacc = len(tw & ow) / len(tw | ow) if (tw | ow) else 0
        if ratio >= 0.8 or (jacc >= 0.6 and len(tw & ow) >= 2):
            return f"near-duplicate of existing lesson '{other}'"
    for r in recent:
        ow = _words(r["topic"])
        if pw and ow and len(pw & ow) / len(pw | ow) >= 0.5:
            return f"near-duplicate topic of recent proposal '{r['title']}'"
    return ""


def _swap_example_name(cand: dict, name: str, recent: list) -> dict:
    """If a made-up example reuses a recently used name (e.g. 'Ana' again), swap in today's name."""
    old = _example_name(str(cand.get("example", "")))
    if not old or _kind(cand) != "made-up" or old == name:
        return cand
    if old not in {_example_name(r["example"]) for r in recent[:14]}:
        return cand
    return {**cand, "example": re.sub(rf"\b{re.escape(old)}\b", name, str(cand["example"]))}


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
    global LAST_SKIP_REASON
    LAST_SKIP_REASON = ""
    recent = _recent_proposals()
    focus, focus_desc = todays_focus(recent)
    name = todays_name(recent)
    recent_titles = "; ".join(r["title"] for r in recent[:20]) or "none"
    focus_block = (f"\nTODAY'S FOCUS: {focus} - {focus_desc}. Make the lesson about this focus. "
                   + ("" if focus == "Antifragility" else
                      "Do NOT make it another antifragility / hormesis / 'stress makes you stronger' lesson; "
                      "recent days already have plenty of those. ")
                   + f"If you use a made-up example, use the learner name {name} (not Ana).\n"
                   f"Recently proposed lesson titles (do NOT repeat or closely duplicate these either):\n{recent_titles}\n")

    prompt = f"""{VALUES_BLURB}
{outside}{founder}{focus_block}
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
  "steelman_for": "The strongest honest case FOR the lesson's idea, in 1-2 sentences",
  "steelman_against": "The strongest honest case AGAINST it or its limits, in 1-2 sentences",
  "example_kind": "real or made-up",
  "example": "One concrete example. If real: only a WELL-KNOWN fact you are certain of (the kind in the first paragraph of an encyclopedia entry), no quotes, and never credit a person with an idea or strategy they are not famous for. If you are not certain, use made-up instead: start with 'Imagine' and a named fictional learner, e.g. 'Imagine {name}, 11, who...'. Never 'a historical figure' or 'someone'",
  "activity": "One hands-on activity a learner can do in 10-20 minutes at home with no special equipment",
  "check_questions": ["Three short questions", "that check understanding", "a learner could honestly answer either way"],
  "age_hint": "one of: All ages, 7+, 8+, 9+, 10+, 11+, 12+, 13+, 14+, 15+, 16+",
  "xp": 20,
  "target_track": "the existing track name this belongs to, or a new track name if genuinely novel",
  "rationale": "One sentence on why this specific lesson is worth adding now"
}}"""

    feedback = ""
    for _attempt in range(3):  # retries carry the reason the last draft was rejected
        reply = _call_ollama(prompt + feedback)
        if not reply:
            return None
        cand = _extract_json(reply)
        if isinstance(cand, dict):
            cand = _swap_example_name(cand, name, recent)
        problems = validate_candidate(cand)
        dup = near_duplicate(cand, [t for _, t, _ in existing], recent) if not problems else ""
        if dup:
            LAST_SKIP_REASON = dup
            problems = [f"{dup}; propose a clearly different lesson about today's focus ({focus})"]
        tried_rewrite = False
        if not problems and _kind(cand) == "real":
            sure, why = _fact_check(str(cand.get("example", "")))
            if not sure:
                # keep the (otherwise good) lesson; swap only the doubtful example for a made-up one
                print(f"[curriculum-autogen] real example doubted ({why}); rewriting it as made-up")
                fixed = _made_up_example(cand, name)
                tried_rewrite = True
                if fixed:
                    return fixed
                problems = [f"the real-world example may not be true ({why}); rewrite it as a made-up "
                            "scenario that starts with 'Imagine' and a named fictional learner, and set "
                            "example_kind to made-up"]
        if not problems:
            LAST_SKIP_REASON = ""
            return cand
        if not tried_rewrite and isinstance(cand, dict) and all(_example_problem(x) for x in problems):
            print(f"[curriculum-autogen] only the example is wrong ({problems}); rewriting it as made-up")
            fixed = _made_up_example(cand, name)
            if fixed:
                return fixed
        feedback = ("\n\nYour last answer was rejected: " + "; ".join(problems)
                    + ". Fix those and reply with ONLY the JSON object.")
        print(f"[curriculum-autogen] draft rejected: {problems}")
    return None


def _kind(c) -> str:
    k = str((c or {}).get("example_kind", "")).strip().lower().replace("_", "-").replace(" ", "-")
    return {"made-up": "made-up", "madeup": "made-up", "fictional": "made-up", "hypothetical": "made-up",
            "real": "real", "real-world": "real", "true": "real"}.get(k, "")


def _fact_check(example: str) -> tuple[bool, str]:
    """A skeptical second look at a real-world example. The drafting model invents plausible facts
    (it once credited Warren Buffett with Taleb's barbell strategy), so 'not sure' counts as no."""
    prompt = ("You are a strict fact-checker for a children's school. Is EVERY claim in this example "
              "true and widely documented? Pay special attention to who is credited with which idea, "
              "strategy, quote, number or date. If you are not completely sure, answer false.\n"
              'Reply with ONLY JSON: {"certain": true or false, "why": "one short reason"}\n\n'
              f"Example: {example}")
    try:
        d = _extract_json(_call_ollama(prompt) or "") or {}
        return d.get("certain") is True, str(d.get("why", "no reason given"))[:160]
    except Exception:
        return False, "fact-check failed to run"


def _example_problem(problem: str) -> bool:
    return bool(re.search(r"example|quote|unnamed|example_kind", problem, re.I))


def _made_up_example(cand: dict, name: str = "Theo") -> dict | None:
    """Rewrite only the example as a named made-up scenario; None if that doesn't pass the checks."""
    prompt = ("Rewrite this lesson example as a short MADE-UP scenario that teaches the same point. Start with "
              "'Imagine' and a named fictional learner with an age, e.g. 'Imagine " + name + ", 11, who ...'. Two or three "
              "sentences, no real people, no statistics.\n"
              'Reply with ONLY JSON: {"example": "..."}\n\n'
              f"Lesson: {cand.get('title', '')} - {cand.get('topic', '')}\nOld example: {cand.get('example', '')}")
    for _ in range(2):
        d = _extract_json(_call_ollama(prompt) or "") or {}
        new = {**cand, "example": str(d.get("example", "")).strip(), "example_kind": "made-up"}
        if new["example"] and not validate_candidate(new):
            return new
    return None


_MADE_UP_VAGUE = re.compile(r"\bsomeone\b|\bsomebody\b|\bimagine (a|an|someone|you)\b", re.I)
_UNNAMED_SOURCE = re.compile(r"\b(a|one|another)\s+(recent\s+|new\s+|large\s+)?(study|survey|report|paper|experiment)\b|"
                             r"\bresearch(ers)?\s+(shows?|suggests?|found|finds)\b|\bscientists\s+(say|found|have found)\b|"
                             r"\bstudies\s+(show|suggest|have shown)\b|\baccording to (a|one|some)\b|"
                             r"\bpublished in the\b", re.I)
_QUOTE = re.compile(r"[\"“”]|\bsaid\b|\bonce wrote\b|\bfamously (said|wrote)\b", re.I)


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
    ex = str(c.get("example", "")).strip()
    kind = _kind(c)
    if not kind:
        p.append("example_kind must be 'real' or 'made-up'")
    elif ex and kind == "made-up":
        if not re.match(r"imagine\b", ex, re.I) or _MADE_UP_VAGUE.search(ex) or not _names_something(ex):
            p.append("a made-up example must start with 'Imagine' and a named fictional learner (e.g. 'Imagine Theo, 11, ...')")
    elif ex:
        if _VAGUE_EXAMPLE.search(ex) or not _names_something(ex):
            p.append("example is vague; name a real person, place, event, or thing, or use a made-up 'Imagine <Name>' scenario")
        if _QUOTE.search(ex):
            p.append("no quotes from real people in a real-world example (they're easy to get wrong)")
        if _UNNAMED_SOURCE.search(ex):
            p.append("example cites an unnamed study or source that nobody can check")
    for side in ("steelman_for", "steelman_against"):
        if len(str(c.get(side, "")).split()) < 8:
            p.append(f"{side} must be a real argument (at least one full sentence)")
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
        if LAST_SKIP_REASON:
            return {"ok": False, "reason": f"skipped: {LAST_SKIP_REASON} (3 tries)"}
        return {"ok": False, "reason": "generation failed or returned unusable JSON"}

    from curriculum_proposals import CurriculumReviewer

    lesson = {
        "key":           candidate["key"],
        "title":         candidate["title"],
        "topic":         candidate.get("topic", ""),
        "steelman":      candidate.get("steelman", ""),
        "steelman_for":  candidate.get("steelman_for", ""),
        "steelman_against": candidate.get("steelman_against", ""),
        "example_kind":  _kind(candidate),
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
    return {"ok": True, "proposal_id": proposal["id"], "title": lesson["title"], "target_track": target_track,
            "example_kind": lesson["example_kind"], "example": lesson["example"]}


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
        + (f"example ({result.get('example_kind') or '?'}): {' '.join(str(result.get('example') or '').split())[:300]}\n"
           + ("  ^ real-world claim: the model checked it once, but check it yourself before approving.\n"
              if result.get("example_kind") == "real" else "")
           if result.get("example") else "")
        + "\n"
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

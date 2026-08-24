"""
curriculum.py — single source of truth for the AUBIEETERNAL lesson tree.

phone_ui.py's "let's go to class" feature reads lesson data from here so
the phone/robot side and the Streamlit portal are teaching the same course
instead of two unrelated lists. (app.py's "Curriculum Map" tabs currently
still carry two older, mutually-divergent inline copies of a similar tree
predating this module — not repointed at this file in this pass, since
figuring out which of those two the live Streamlit lesson-flow actually
depends on is a separate, riskier cleanup than the phone integration this
was written for.)

Lesson keys match app.py's first CURRICULUM_TREE (the "Curriculum Map" tab
at ~line 5128), so `lessons_completed` entries written by either surface
are understood by both.

── Growing the curriculum ──────────────────────────────────────────────
CURRICULUM_TREE below is the hand-authored base tree — deliberately never
rewritten by code. New lessons/tracks approved via curriculum_proposals.py
(human-submitted or curriculum_autogen.py's daily AI-proposed candidate)
are merged in from a small JSON side-file instead (see EXTRA_PATH), so
"approve a proposal" takes effect immediately for every process reading
this module — no source edit, no restart. See curriculum_proposals.py's
`merge_approved_proposal()` for the writer side of that file.
"""

import json
from pathlib import Path

try:
    from family_profiles import DATA_DIR
except Exception:
    DATA_DIR = Path("/mnt/main")

EXTRA_PATH = DATA_DIR / "curriculum_extra.json"

CURRICULUM_TREE = [
    {"track_id": "courage", "track": "🦁 Courage", "color": "#00cfff", "levels": [
        ("courage-1", "What Is Courage?",     "All ages", 15),
        ("courage-2", "Social Courage",       "8+",       18),
        ("courage-3", "Intellectual Courage", "10+",      22),
        ("courage-4", "Antifragile Courage",  "12+",      25),
        ("courage-5", "Long-Game Courage",    "14+",      35),
    ]},
    {"track_id": "antifragility", "track": "⚡ Antifragility", "color": "#ff6b35", "levels": [
        ("antifragility-1", "Systems That Grow Stronger", "All", 18),
        ("antifragility-2", "Barbell Strategy",           "10+", 22),
        ("antifragility-3", "Black Swans",                "12+", 28),
        ("antifragility-4", "Hormesis",                   "14+", 32),
    ]},
    {"track_id": "bitcoin", "track": "₿ Bitcoin", "color": "#f7931a", "levels": [
        ("bitcoin-sovereignty-1", "Your Keys = Your Coins",  "All", 20),
        ("bitcoin-sovereignty-2", "Fixed Supply",            "9+",  22),
        ("bitcoin-sovereignty-3", "Runes + On-Chain Truth",  "11+", 25),
        ("bitcoin-sovereignty-4", "Lightning Network",       "13+", 30),
    ]},
    {"track_id": "steelmanning", "track": "⚔️ Steelmanning", "color": "#a020f0", "levels": [
        ("steelmanning-1", "Argue the Other Side",   "8+",  22),
        ("steelmanning-2", "Steel in Bad Arguments", "11+", 26),
        ("steelmanning-3", "Epistemic Humility",     "13+", 30),
    ]},
    {"track_id": "polyvagal", "track": "💚 Nervous System", "color": "#00ff88", "levels": [
        ("polyvagal-1", "3 Modes of Safety",     "All", 15),
        ("polyvagal-2", "Co-Regulation",         "8+",  18),
        ("polyvagal-3", "Hormesis for the Mind", "12+", 25),
    ]},
    {"track_id": "simulation", "track": "🌀 Simulation", "color": "#00cfff", "levels": [
        ("simulation-1", "Is Reality a Simulation?", "10+", 20),
        ("simulation-2", "Bostrom's Trilemma",        "13+", 25),
        ("simulation-3", "Planck Constraints",        "14+", 30),
        ("simulation-4", "Observer Effect",           "15+", 35),
        ("simulation-5", "Planck-Scale Glitches",     "15+", 38),
        ("simulation-6", "Deliberate Glitch Tests",   "15+", 40),
        ("simulation-7", "Wonder as Detector",        "16+", 42),
        ("simulation-8", "Bitcoin Reality Anchor",    "16+", 50),
    ]},
    {"track_id": "wonder", "track": "💡 Wonder", "color": "#ffcf00", "levels": [
        ("wonder-1", "Awe as Signal",  "All", 15),
        ("wonder-2", "Wonder Index",   "11+", 20),
    ]},
    {"track_id": "stoic", "track": "🏛️ Stoic", "color": "#8899bb", "levels": [
        ("stoic-1", "Dichotomy of Control",   "9+",  18),
        ("stoic-2", "Negative Visualization", "11+", 22),
        ("stoic-3", "Amor Fati",              "13+", 28),
    ]},
]


def _load_extra_tracks() -> list:
    """Approved additions live here as plain data: a list of track-shaped
    dicts, same shape as CURRICULUM_TREE entries. Never raises — a missing
    or corrupt file just means "nothing extra yet", not a startup failure
    for every process that imports this module."""
    try:
        if EXTRA_PATH.exists():
            data = json.loads(EXTRA_PATH.read_text())
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def _merged_tree() -> list:
    """CURRICULUM_TREE with approved extra lessons/tracks folded in. Extra
    entries targeting an existing track_id extend that track's levels
    (skipping any key collision); an unrecognized track_id becomes a new
    track. Recomputed on every call (cheap — the file is small and this
    isn't a hot loop) so an approval goes live without a process restart."""
    by_id = {t["track_id"]: {**t, "levels": list(t["levels"])} for t in CURRICULUM_TREE}
    order = [t["track_id"] for t in CURRICULUM_TREE]

    for extra in _load_extra_tracks():
        tid = extra.get("track_id")
        if not tid:
            continue
        existing_keys = {lvl[0] for lvl in by_id.get(tid, {}).get("levels", [])}
        new_levels = [
            tuple(lvl) for lvl in extra.get("levels", [])
            if lvl and lvl[0] not in existing_keys
        ]
        if not new_levels:
            continue
        if tid in by_id:
            by_id[tid]["levels"].extend(new_levels)
        else:
            by_id[tid] = {
                "track_id": tid,
                "track": extra.get("track", tid),
                "color": extra.get("color", "#00c9ff"),
                "levels": new_levels,
            }
            order.append(tid)

    return [by_id[tid] for tid in order]


def _flatten() -> list:
    out = []
    for track in _merged_tree():
        for i, (key, title, age, xp) in enumerate(track["levels"]):
            out.append({
                "lesson_key": key, "title": title, "age": age, "xp": xp,
                "track_id": track["track_id"], "track": track["track"],
                "color": track["color"], "index_in_track": i,
            })
    return out


def get_lesson(lesson_key: str) -> dict | None:
    return next((l for l in _flatten() if l["lesson_key"] == lesson_key), None)


def next_lesson(completed) -> dict | None:
    """First not-yet-completed lesson, in track order. A level only counts
    as unlocked once the previous level in its own track is done — a track
    with its first level still outstanding is skipped in favor of the next
    track, rather than blocking progress on everything after it."""
    completed = set(completed or [])
    for track in _merged_tree():
        for i, (key, title, age, xp) in enumerate(track["levels"]):
            if key in completed:
                continue
            prev_done = i == 0 or track["levels"][i - 1][0] in completed
            if prev_done:
                return get_lesson(key)
            break  # this track is locked past an incomplete level — try the next track
    return None  # every lesson complete


def total_lessons() -> int:
    return len(_flatten())


def track_progress(completed) -> list:
    """Per-track {track, color, done, total, pct} for progress bars."""
    completed = set(completed or [])
    out = []
    for track in _merged_tree():
        total = len(track["levels"])
        done = sum(1 for (key, *_rest) in track["levels"] if key in completed)
        out.append({
            "track": track["track"], "color": track["color"],
            "done": done, "total": total,
            "pct": int(done / total * 100) if total else 0,
        })
    return out


def all_titles_and_keys() -> list:
    """(lesson_key, title, track) for every lesson, base + approved extra —
    used by curriculum_autogen.py to avoid proposing a duplicate."""
    return [(l["lesson_key"], l["title"], l["track"]) for l in _flatten()]


def track_names() -> list:
    """(track_id, track label) for every track, base + approved extra."""
    return [(t["track_id"], t["track"]) for t in _merged_tree()]

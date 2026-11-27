"""
lesson_packs.py — Family Co-Learning packs on disk, for the Institute portal.

Turns verified markdown under lessons/ (and optional local videos under videos/)
into curriculum tracks and Family Co-Learning lesson entries. Missing video
files are skipped with a graceful fallback so a fresh clone still loads the
written lesson. This module is Institute-only and does not read any path
outside the repository.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
LESSONS_DIR = REPO_ROOT / "lessons"
VIDEOS_DIR = REPO_ROOT / "videos"

# Skip these even if someone later points a catalog entry at them.
_SKIP_NAME_PARTS = ("social-drafts",)

# (key, title, age, xp, markdown relative to lessons/, video relatives to videos/)
# Video lists are in preference order: 16:9 first, then 9:16 / Reel cut.
CATALOG = [
    {
        "track_id": "what-is-money",
        "track": "💵 What is Money",
        "color": "#e6b800",
        "lessons": [
            {
                "key": "what-is-money-1",
                "title": "What is Money — Lesson 1: What money is",
                "age": "All ages",
                "xp": 30,
                "markdown": "what-is-money/lesson-01-what-money-is.md",
                "allow_existing_pack": True,  # already on GitHub; may contain brand-separation notes
                "videos": ["lesson-01-what-is-money/lesson-01-final.mp4"],
            },
            {
                "key": "what-is-money-2",
                "title": "What is Money — Lesson 2: Cash Flow",
                "age": "All ages",
                "xp": 30,
                "markdown": None,
                "allow_existing_pack": False,
                "videos": ["lesson-02-cash-flow/lesson-02-final.mp4"],
                "topic": (
                    "Money in and money out, like water in a bathtub. "
                    "If more goes out than comes in, the jar shrinks. "
                    "Families practice this with pretend tokens only."
                ),
                "example": (
                    "Imagine Maya's lemonade stand puts 10 pretend tokens in the Later jar "
                    "and takes 12 out to buy lemons and cups. The jar is smaller than when she started."
                ),
                "activity": (
                    "This week, with a parent, write down one pretend 'in' and one pretend 'out' "
                    "and see whether the jar grew. Pretend tokens only. No real money."
                ),
                "steelman": (
                    "When might spending more than you take in be planned and okay for a short time?"
                ),
                "check_questions": [
                    "What happens to the jar if more tokens go out than come in?",
                    "What is one pretend 'in' and one pretend 'out' your family could write down?",
                    "Why does this lesson use pretend tokens, not real money?",
                ],
            },
            {
                "key": "what-is-money-4",
                "title": "What is Money — Lesson 4: Sound vs unsound money",
                "age": "All ages",
                "xp": 30,
                "markdown": "what-is-money/lesson-04-sound-vs-unsound-money.md",
                "allow_existing_pack": True,
                "videos": [
                    "lesson-04-sound-vs-unsound-money/lesson-04-final.mp4",
                    "lesson-04-sound-vs-unsound-money/lesson-04-final-1920x1080.mp4",
                    "lesson-04-sound-vs-unsound-money/lesson-04-final-1080x1920.mp4",
                ],
            },
            {
                "key": "what-is-money-5",
                "title": "What is Money — Lesson 5: Why Bitcoin is interesting",
                "age": "All ages",
                "xp": 30,
                "markdown": "what-is-money/lesson-05-why-bitcoin-is-interesting.md",
                "allow_existing_pack": False,
                "videos": [
                    "lesson-05-why-bitcoin-is-interesting/lesson-05-final-1920x1080.mp4",
                    "lesson-05-why-bitcoin-is-interesting/lesson-05-final-1080x1920.mp4",
                ],
            },
        ],
    },
    {
        "track_id": "digital-safety",
        "track": "🛡️ Digital Safety",
        "color": "#00cfff",
        "lessons": [
            {
                "key": "digital-safety-meta-apps",
                "title": "Digital Safety — Using Facebook, Instagram, WhatsApp, and Messenger safely",
                "age": "All ages",
                "xp": 30,
                "markdown": "digital-safety/lesson-meta-apps-safety-and-privacy.md",
                "allow_existing_pack": False,
                "videos": [],
            },
        ],
    },
    {
        "track_id": "open-source-learning",
        "track": "📚 Open-Source Learning",
        "color": "#7c4dff",
        "lessons": [
            {
                "key": "open-learning-overview",
                "title": "Open-Source Learning — Six verified tools for Family Co-Learning",
                "age": "All ages",
                "xp": 20,
                "markdown": "open-source-learning-ideas.md",
                "section": None,
                "allow_existing_pack": False,
                "videos": [],
            },
            {
                "key": "open-learning-visuallearning",
                "title": "Open-Source Learning — VisualLearning.Skill",
                "age": "All ages",
                "xp": 20,
                "markdown": "open-source-learning-ideas.md",
                "section": "1. VisualLearning.Skill",
                "allow_existing_pack": False,
                "videos": [],
            },
            {
                "key": "open-learning-storycraft",
                "title": "Open-Source Learning — StoryCraft",
                "age": "All ages",
                "xp": 20,
                "markdown": "open-source-learning-ideas.md",
                "section": "2. StoryCraft",
                "allow_existing_pack": False,
                "videos": [],
            },
            {
                "key": "open-learning-math-to-manim",
                "title": "Open-Source Learning — Math-To-Manim",
                "age": "All ages",
                "xp": 20,
                "markdown": "open-source-learning-ideas.md",
                "section": "3. Math-To-Manim",
                "allow_existing_pack": False,
                "videos": [],
            },
            {
                "key": "open-learning-deeptutor",
                "title": "Open-Source Learning — DeepTutor",
                "age": "All ages",
                "xp": 20,
                "markdown": "open-source-learning-ideas.md",
                "section": "4. DeepTutor",
                "allow_existing_pack": False,
                "videos": [],
            },
            {
                "key": "open-learning-openmaic",
                "title": "Open-Source Learning — OpenMAIC",
                "age": "All ages",
                "xp": 20,
                "markdown": "open-source-learning-ideas.md",
                "section": "5. OpenMAIC",
                "allow_existing_pack": False,
                "videos": [],
            },
            {
                "key": "open-learning-openlingo",
                "title": "Open-Source Learning — OpenLingo",
                "age": "All ages",
                "xp": 20,
                "markdown": "open-source-learning-ideas.md",
                "section": "6. OpenLingo",
                "allow_existing_pack": False,
                "videos": [],
            },
        ],
    },
]


def _extract_section(text: str, heading: str | None) -> str:
    if not heading:
        return text.strip()
    pat = re.compile(r"^## " + re.escape(heading) + r"\s*$", re.M)
    m = pat.search(text)
    if not m:
        return text.strip()
    rest = text[m.start():]
    nxt = re.search(r"\n## ", rest[3:])
    return (rest[: nxt.start() + 3] if nxt else rest).strip()


def _first_paragraph(text: str) -> str:
    chunks = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip() and not p.strip().startswith("#")]
    for p in chunks:
        if p.startswith("**"):
            continue
        if p.startswith("---"):
            continue
        return re.sub(r"\s+", " ", p)[:400]
    return ""


def _parse_markdown(path: Path, section: str | None = None) -> dict:
    text = path.read_text(encoding="utf-8")
    body = _extract_section(text, section)
    title_m = re.search(r"^#\s+(.+)$", body, re.M)
    xp_m = re.search(r"\*\*Suggested XP:\*\*\s*(\d+)", text, re.I)
    age_m = re.search(r"\*\*Who it's for:\*\*\s*(.+)", text, re.I)
    topic = _first_paragraph(body)
    steel_m = re.search(r"(?im)^#{2,3}\s+.*steelman.*\n+(.*?)(?:\n#{2,}|\Z)", body, re.S)
    activity_m = re.search(r"(?im)^#{2,3}\s+.*activit.*\n+(.*?)(?:\n#{2,}|\Z)", body, re.S)
    example = ""
    ex_m = re.search(r"(?im)worked example[^\n]*\n+(.*?)(?:\n#{2,}|\Z)", body, re.S)
    if ex_m:
        example = re.sub(r"\s+", " ", ex_m.group(1)).strip()[:400]
    return {
        "title": title_m.group(1).strip() if title_m else path.stem,
        "topic": topic,
        "example": example,
        "activity": re.sub(r"\s+", " ", activity_m.group(1)).strip()[:400] if activity_m else "",
        "steelman": re.sub(r"\s+", " ", steel_m.group(1)).strip()[:400] if steel_m else "",
        "xp": int(xp_m.group(1)) if xp_m else 20,
        "age_hint": (age_m.group(1).strip()[:80] if age_m else "All ages"),
        "body": body,
    }


def resolve_videos(rel_paths: list[str]) -> tuple[str | None, list[str], list[str]]:
    """Return (first existing absolute path, existing repo-relative paths, all configured relatives)."""
    existing_rel = []
    existing_abs = []
    for rel in rel_paths or []:
        rel = rel.replace("\\", "/").lstrip("/")
        if ".." in Path(rel).parts:
            continue
        p = VIDEOS_DIR / rel
        if p.is_file():
            existing_rel.append(rel)
            existing_abs.append(str(p))
    return (existing_abs[0] if existing_abs else None, existing_rel, list(rel_paths or []))


def video_http_path(rel: str) -> str:
    """Portal URL path when Streamlit static serving is enabled."""
    return "/app/static/videos/" + rel.lstrip("/")


def _safe_to_load(path: Path, allow_existing_pack: bool) -> bool:
    """Load only real lesson packs listed by the catalog. Social drafts, README,
    and backup copies stay out. allow_existing_pack is reserved for already
    published packs the catalog opted in explicitly."""
    if not path.is_file():
        return False
    name = path.name.lower()
    if name.startswith("readme") or any(part in name for part in _SKIP_NAME_PARTS):
        return False
    # Skip editor backup copies.
    if any(part.startswith("bak") for part in name.split(".")):
        return False
    return True


def tracks_for_tree() -> list[dict]:
    """curriculum.py / Curriculum Map shape: levels are (key, title, age, xp)."""
    out = []
    for track in CATALOG:
        levels = []
        for les in track["lessons"]:
            md = les.get("markdown")
            if md:
                path = LESSONS_DIR / md
                if not _safe_to_load(path, les.get("allow_existing_pack", False)):
                    # Still include the lesson if it is a no-markdown (video-only) entry.
                    continue
            levels.append((les["key"], les["title"], les["age"], les["xp"]))
        if levels:
            out.append({
                "track_id": track["track_id"],
                "track": track["track"],
                "color": track["color"],
                "levels": levels,
            })
    return out


def tracks_for_map_progress() -> list[dict]:
    """Second Curriculum Map shape: levels are (key, title, xp, age)."""
    out = []
    for track in tracks_for_tree():
        levels = [(k, title, xp, age) for (k, title, age, xp) in track["levels"]]
        out.append({**track, "levels": levels})
    return out


def lessons_for_hud() -> dict:
    """key -> Family Co-Learning lesson dict, including body and video_path when present."""
    out = {}
    for track in CATALOG:
        for les in track["lessons"]:
            key = les["key"]
            entry = {
                "title": les["title"],
                "topic": les.get("topic", ""),
                "example": les.get("example", ""),
                "activity": les.get("activity", ""),
                "check_questions": list(les.get("check_questions") or []),
                "steelman": les.get("steelman", ""),
                "age_hint": les.get("age", "All ages"),
                "xp": les.get("xp", 20),
                "rune": les.get("rune") or (track["track_id"].upper().replace("-", "•") + "•PACK"),
                "min_coherence": 0.60,
                "body": "",
                "video_path": None,
                "video_paths": [],
                "video_rels": [],
                "video_http_paths": [],
                "source_markdown": les.get("markdown") or "",
            }
            md = les.get("markdown")
            if md:
                path = LESSONS_DIR / md
                if not _safe_to_load(path, les.get("allow_existing_pack", False)):
                    continue
                parsed = _parse_markdown(path, les.get("section"))
                if not entry["topic"]:
                    entry["topic"] = parsed["topic"]
                if not entry["example"]:
                    entry["example"] = parsed["example"]
                if not entry["activity"]:
                    entry["activity"] = parsed["activity"]
                if not entry["steelman"]:
                    entry["steelman"] = parsed["steelman"]
                entry["body"] = parsed["body"]
                if parsed.get("xp"):
                    entry["xp"] = parsed["xp"]
            video_path, existing_rel, _configured = resolve_videos(les.get("videos") or [])
            entry["video_path"] = video_path
            entry["video_paths"] = [str(VIDEOS_DIR / r) for r in existing_rel]
            entry["video_rels"] = existing_rel
            entry["video_http_paths"] = [video_http_path(r) for r in existing_rel]
            # Video-only lessons (no markdown) still belong in the portal.
            if not md or entry["body"] or entry["topic"]:
                out[key] = entry
    return out


def wired_summary() -> list[dict]:
    """Compact list for verification and operator reports."""
    rows = []
    hud = lessons_for_hud()
    for key, entry in hud.items():
        rows.append({
            "key": key,
            "title": entry["title"],
            "has_body": bool(entry.get("body")),
            "videos": entry.get("video_rels") or [],
            "video_http_paths": entry.get("video_http_paths") or [],
        })
    return rows


def prepare_static_videos() -> list[str]:
    """Hard-link (or copy) existing repo videos into static/videos/ so Streamlit
    can serve them at /app/static/videos/... . Missing sources are skipped.
    Returns the repo-relative paths that are now available over HTTP."""
    ready = []
    static_root = REPO_ROOT / "static" / "videos"
    static_root.mkdir(parents=True, exist_ok=True)
    for track in CATALOG:
        for les in track["lessons"]:
            for rel in les.get("videos") or []:
                rel = rel.replace("\\", "/").lstrip("/")
                if ".." in Path(rel).parts:
                    continue
                src = VIDEOS_DIR / rel
                dest = static_root / rel
                if not src.is_file():
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                try:
                    if dest.exists() or dest.is_symlink():
                        if dest.is_file() and dest.stat().st_ino == src.stat().st_ino:
                            ready.append(rel)
                            continue
                        dest.unlink()
                    os.link(src, dest)
                except OSError:
                    import shutil
                    shutil.copy2(src, dest)
                ready.append(rel)
    return ready

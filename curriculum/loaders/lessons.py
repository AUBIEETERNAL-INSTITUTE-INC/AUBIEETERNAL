"""
curriculum.loaders.lessons

Loads individual lesson Markdown files (with YAML frontmatter) into the
same dict format previously used by the hardcoded LESSONS in family_hud.py.

Usage:
    from curriculum.loaders.lessons import load_lessons
    LESSONS = load_lessons()
"""

from pathlib import Path
from typing import Dict, Any
import yaml

LESSONS_DIR = Path(__file__).parent.parent.parent / "curriculum" / "lessons"


def parse_frontmatter_and_body(text: str) -> Dict[str, Any]:
    """Simple frontmatter parser. Expects content starting with ---"""
    text = text.strip()
    if not text.startswith("---"):
        # No frontmatter, return as-is (fallback)
        return {"body": text}

    # Split on the first two ---
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {"body": text}

    _, frontmatter_raw, body = parts
    try:
        meta = yaml.safe_load(frontmatter_raw) or {}
    except Exception:
        meta = {}

    meta = dict(meta)  # ensure dict
    meta["body"] = body.strip()
    return meta


def load_lessons() -> Dict[str, Dict[str, Any]]:
    """
    Discover and load all .md files in the lessons directory.

    Returns a dict keyed by lesson id (e.g. "core-v67-1").
    Compatible with the previous inline LESSONS format.
    """
    lessons: Dict[str, Dict[str, Any]] = {}

    if not LESSONS_DIR.exists():
        print(f"[curriculum] Warning: {LESSONS_DIR} does not exist.")
        return lessons

    for md_file in sorted(LESSONS_DIR.glob("*.md")):
        try:
            content = md_file.read_text(encoding="utf-8")
            lesson = parse_frontmatter_and_body(content)

            # Ensure required keys exist
            lesson_id = lesson.get("id") or md_file.stem
            lesson.setdefault("id", lesson_id)

            # Keep the original keys that family_hud expects
            # title, topic, steelman, example, age_hint, xp, rune, min_coherence

            lessons[lesson_id] = lesson
        except Exception as e:
            print(f"[curriculum] Failed to load {md_file}: {e}")

    return lessons


if __name__ == "__main__":
    loaded = load_lessons()
    print(f"Loaded {len(loaded)} lessons.")
    for key in list(loaded.keys())[:3]:
        print(f"  - {key}: {loaded[key].get('title')}")

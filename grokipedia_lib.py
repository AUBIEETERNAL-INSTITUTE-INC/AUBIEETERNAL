"""Shared Grokipedia helpers — principles JSON is the source of truth."""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent
_MNT = Path("/mnt/main")
# Durable copies live on /mnt/main when available (shared by swarm, portal, bots).
PRINCIPLES_PATH = (_MNT / "grokipedia_principles.json") if _MNT.exists() else (REPO / "grokipedia_principles.json")
SOURCES_PATH = REPO / "grokipedia_sources.txt"
PENDING_PATH = (_MNT / "grokipedia_pending.json") if _MNT.exists() else (REPO / "grokipedia_pending.json")
REPO_SEED = REPO / "grokipedia_principles.json"


def load_principles() -> dict:
    if PRINCIPLES_PATH.exists():
        return json.loads(PRINCIPLES_PATH.read_text(encoding="utf-8"))
    # First run: seed from the repo copy if present
    if REPO_SEED.exists() and PRINCIPLES_PATH != REPO_SEED:
        data = json.loads(REPO_SEED.read_text(encoding="utf-8"))
        PRINCIPLES_PATH.parent.mkdir(parents=True, exist_ok=True)
        PRINCIPLES_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return data
    return {"version": 1, "entries": []}


def approved_entries() -> list[dict]:
    return [e for e in load_principles().get("entries", []) if e.get("status", "approved") == "approved"]


def principle_count() -> int:
    return len(approved_entries())


def principle_lines() -> list[str]:
    out = []
    for e in approved_entries():
        title = (e.get("title") or "").strip()
        body = (e.get("principle") or e.get("explanation") or "").strip()
        out.append(f"{title}: {body}" if title and body else (title or body))
    return out


def covered_titles() -> set[str]:
    return {((e.get("title") or "").strip().lower()) for e in approved_entries()}


def parse_sources() -> list[dict]:
    if not SOURCES_PATH.exists():
        return []
    topics = []
    for line in SOURCES_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        title = parts[0] if parts else ""
        hint = parts[1] if len(parts) > 1 else ""
        source = parts[2] if len(parts) > 2 else "General"
        if title:
            topics.append({"title": title, "hint": hint, "source": source})
    return topics


def uncovered_topics(limit: int = 50) -> list[dict]:
    covered = covered_titles()
    pending = {((d.get("title") or "").strip().lower()) for d in load_pending()}
    out = []
    for t in parse_sources():
        key = t["title"].lower()
        # also skip if any approved title is a close substring
        if key in covered or key in pending:
            continue
        if any(key in c or c in key for c in covered if c):
            continue
        out.append(t)
        if len(out) >= limit:
            break
    return out


def load_pending() -> list[dict]:
    if PENDING_PATH.exists():
        try:
            data = json.loads(PENDING_PATH.read_text(encoding="utf-8"))
            return data.get("drafts", data if isinstance(data, list) else [])
        except Exception:
            return []
    return []


def save_pending(drafts: list[dict]) -> None:
    PENDING_PATH.parent.mkdir(parents=True, exist_ok=True)
    PENDING_PATH.write_text(
        json.dumps({"drafts": drafts}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def append_principle(entry: dict) -> dict:
    data = load_principles()
    entries = data.setdefault("entries", [])
    entries.append(entry)
    PRINCIPLES_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return entry


def slug_id(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
    return (s or "entry")[:48]

#!/usr/bin/env python3
"""Approve / reject / list Grokipedia pending drafts. Used by Discord & SimpleX."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from grokipedia_lib import (  # noqa: E402
    PRINCIPLES_PATH,
    append_principle,
    load_pending,
    save_pending,
    slug_id,
)

TZ = ZoneInfo("America/New_York")
LEDGER = Path.home() / "vanhorn-repo" / "skills" / "it-support" / "aubie-error-ledger.md"
if not LEDGER.exists():
    LEDGER = Path("/mnt/main/aubie-error-ledger.md")


def _log(action: str, detail: str) -> None:
    safe = " ".join(detail.replace("`", "'").split())[:300]
    line = (
        f"- {datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S %Z')} | id=- | grokipedia | {action} | {safe}\n"
    )
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        text = LEDGER.read_text(errors="replace") if LEDGER.exists() else ""
        header = "" if "# Aubie action log" in text else "\n\n# Aubie action log (append-only)\n\n"
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(header + line)
    except Exception:
        pass


def cmd_list() -> int:
    drafts = [d for d in load_pending() if d.get("status") == "pending"]
    if not drafts:
        print("No pending Grokipedia drafts.")
        return 0
    for d in drafts:
        print(f"ID: {d.get('id')}")
        print(f"Title: {d.get('title')}")
        print(f"Principle: {d.get('principle')}")
        print(f"Explanation: {d.get('explanation')}")
        print(f"Source: {d.get('source')} | score={d.get('score')}")
        print("---")
    return 0


def _find(draft_id: str):
    drafts = load_pending()
    for d in drafts:
        if d.get("id") == draft_id and d.get("status") == "pending":
            return d, drafts
    return None, drafts


def cmd_add(draft_id: str) -> int:
    d, drafts = _find(draft_id)
    if not d:
        print(f"No pending draft id={draft_id}")
        return 1
    entry = {
        "id": f"gp-{slug_id(d.get('title') or draft_id)}-{draft_id[:6]}",
        "title": d.get("title"),
        "principle": d.get("principle"),
        "explanation": d.get("explanation"),
        "source": d.get("source") or "General",
        "added_at": datetime.now(TZ).isoformat(),
        "added_by": "human",
        "from_draft": draft_id,
        "score": d.get("score"),
        "status": "approved",
    }
    append_principle(entry)
    d["status"] = "approved"
    d["decided_at"] = entry["added_at"]
    save_pending(drafts)
    _log("add", f"id={draft_id} title={entry['title']} path={PRINCIPLES_PATH}")
    print(f"Added: {entry['title']} -> {PRINCIPLES_PATH}")
    return 0


def cmd_reject(draft_id: str, how: str = "rejected") -> int:
    d, drafts = _find(draft_id)
    if not d:
        print(f"No pending draft id={draft_id}")
        return 1
    d["status"] = how
    d["decided_at"] = datetime.now(TZ).isoformat()
    save_pending(drafts)
    _log(how, f"id={draft_id} title={d.get('title')}")
    print(f"{how}: {d.get('title')}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["list", "add", "reject", "skip"])
    ap.add_argument("draft_id", nargs="?")
    args = ap.parse_args()
    if args.action == "list":
        return cmd_list()
    if not args.draft_id:
        print("draft id required")
        return 2
    if args.action == "add":
        return cmd_add(args.draft_id)
    return cmd_reject(args.draft_id, "skipped" if args.action == "skip" else "rejected")


if __name__ == "__main__":
    raise SystemExit(main())

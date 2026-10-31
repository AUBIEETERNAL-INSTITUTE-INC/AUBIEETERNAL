#!/usr/bin/env python3
"""
approvals_inbox.py - ONE list of everything waiting on Mateo's yes/no (DRAFT 2026-10-30).

    python3 approvals_inbox.py            # plain-text list (read-only)
    python3 approvals_inbox.py --json     # same, as JSON (for a Discord/SimpleX/portal card)
    python3 approvals_inbox.py approve curriculum <id>   # = portal Review Queue "Approve"
    python3 approvals_inbox.py reject  curriculum <id> [reason]
    python3 approvals_inbox.py approve grokipedia <id>   # = `grok` Add button
    python3 approvals_inbox.py reject  grokipedia <id>

Listing only READS files. approve/reject exist only for the two queues that are
pure data (curriculum proposals, Grokipedia drafts) and call the same functions the
portal and the bots already use. Everything else (r35 training/finish, dog firmware
patches, face naming) is listed with the exact manual step, never one-tap, on purpose.
Face naming is personal-family data, so it is shown only as a count here.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
FT = HOME / "aubieeternal_finetune"
DOG = REPO / "spotmicro_dog"


def curriculum_items() -> list:
    from curriculum_proposals import CurriculumReviewer
    out = []
    for p in CurriculumReviewer().get_pending():
        title = (p.get("lesson") or {}).get("title") or p.get("track_name") or "?"
        n = len(p.get("lessons") or []) if p.get("type") == "track" else 1
        out.append({"queue": "curriculum", "id": p["id"], "title": title, "kind": p.get("type"),
                    "lessons": n, "author": p.get("author"), "submitted": str(p.get("submitted_at", ""))[:10],
                    "how": "portal Review Queue, or: approvals_inbox.py approve|reject curriculum " + p["id"],
                    "one_tap": True})
    return out


def grokipedia_items() -> list:
    try:
        from grokipedia_lib import load_pending
        return [{"queue": "grokipedia", "id": d.get("id"), "title": d.get("title"), "detail": d.get("principle"),
                 "how": "Discord/SimpleX `grok`, or: approvals_inbox.py approve|reject grokipedia " + str(d.get("id")),
                 "one_tap": True} for d in load_pending() if d.get("status") == "pending"]
    except Exception as e:
        return [{"queue": "grokipedia", "id": "-", "title": f"(could not read: {e})", "one_tap": False}]


def finetune_items() -> list:
    sup = FT / "supervisor"
    if not sup.exists():
        return []
    status = (sup / "STATUS.md").read_text(errors="replace") if (sup / "STATUS.md").exists() else ""
    phase = status.split("**`", 1)[1].split("`", 1)[0] if "**`" in status else "?"
    lora = (FT / "output" / "aubie_lora_r35" / "adapter_model.safetensors").exists()
    items = [{"queue": "finetune", "id": "r35", "title": f"r35 round - supervisor phase: {phase}"
              + ("; LoRA trained" if lora else "; LoRA not finished yet"),
              "how": "after training says DONE: touch ~/aubieeternal_finetune/supervisor/APPROVE_FINISH "
                     "(merge + GGUF + ollama create); then compare bench vs qwen2.5:14b before any Fast switch",
              "one_tap": False}]
    return items


def dog_items() -> list:
    out = []
    for p in sorted(list(DOG.glob("sim/PROPOSED_*.patch")) + list(DOG.glob("diag_snapshots/*/PROPOSED_*.patch"))):
        first = next((l for l in p.read_text(errors="replace").splitlines() if l.strip()), "")
        out.append({"queue": "dog", "id": p.name, "title": str(p.relative_to(DOG)), "detail": first[:160],
                    "how": "hardware change - apply by hand with the dog on the stand, not from a button",
                    "one_tap": False})
    return out


def faces_items() -> list:
    db = HOME / "M_MEMORY" / "brain" / "profile.db"
    try:
        import sqlite3
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        rows = dict(c.execute("SELECT kind, count(*) FROM questions WHERE status='pending' GROUP BY kind").fetchall())
        out = []
        if rows.get("face_name"):
            out.append({"queue": "faces", "id": "face_name", "title": f"{rows['face_name']} face groups waiting for a name",
                        "how": "m-brain faces card / SimpleX owner chat (personal - not on Discord)", "one_tap": False})
        if rows.get("fact_confirm"):
            out.append({"queue": "faces", "id": "fact_confirm", "title": f"{rows['fact_confirm']} profile facts to confirm",
                        "how": "m-brain questions (SimpleX owner chat)", "one_tap": False})
        return out
    except Exception:
        return []


def flashcard_items() -> list:
    p = REPO / "flashcards" / "decks_pending_20261007.json"
    try:
        d = json.loads(p.read_text())
        if d.get("status") != "pending_review":
            return []
        decks = d["decks"] if isinstance(d["decks"], list) else list(d["decks"].values())
        return [{"queue": "flashcards", "id": p.name, "title": f"{x.get('title') or x.get('name')} ({len(x.get('cards', []))} cards)",
                 "how": "review, then copy approved cards into flashcards/decks.json", "one_tap": False} for x in decks]
    except Exception:
        return []


def collect() -> list:
    items = []
    for fn in (curriculum_items, grokipedia_items, finetune_items, dog_items, faces_items, flashcard_items):
        try:
            items += fn()
        except Exception as e:
            items.append({"queue": fn.__name__, "id": "-", "title": f"(error: {e})", "one_tap": False})
    return items


def act(verb: str, queue: str, item_id: str, reason: str = "") -> int:
    if queue == "curriculum":
        from curriculum_proposals import CurriculumReviewer
        r = CurriculumReviewer()
        ok = r.approve(item_id) if verb == "approve" else r.reject(item_id, reason or "rejected from approvals inbox")
        print(("Approved" if verb == "approve" else "Rejected") + f" {item_id}" if ok else f"No proposal {item_id}")
        return 0 if ok else 1
    if queue == "grokipedia":
        return subprocess.call([sys.executable, str(REPO / "grokipedia_approve.py"),
                                "add" if verb == "approve" else "reject", item_id])
    print(f"{queue} has no one-tap {verb}; see the 'how' line in the list.")
    return 2


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] in ("approve", "reject"):
        if len(a) < 3:
            print(__doc__); raise SystemExit(2)
        raise SystemExit(act(a[0], a[1], a[2], " ".join(a[3:])))
    items = collect()
    if "--json" in a:
        print(json.dumps(items, indent=2, ensure_ascii=False)); raise SystemExit(0)
    q = None
    for it in items:
        if it["queue"] != q:
            q = it["queue"]
            print(f"\n== {q} ({sum(1 for x in items if x['queue'] == q)}) ==")
        print(f"- [{it['id']}] {it['title']}" + (f"  ({it.get('submitted')})" if it.get("submitted") else ""))
        print(f"    how: {it['how']}")

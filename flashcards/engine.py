"""Flash card decks, generators, and simple Leitner progress.

Privacy: only stores card_id, box (1-5), last_seen ISO timestamp per profile.
No chat logs, no transcripts.
"""
from __future__ import annotations

import json
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Leitner intervals in seconds (approx): box1 soon, box5 rarely
_BOX_INTERVALS = {
    1: 0,            # due immediately / soon
    2: 60 * 10,      # ~10 min
    3: 60 * 60,      # ~1 hour
    4: 60 * 60 * 6,  # ~6 hours
    5: 60 * 60 * 24, # ~1 day
}

DECKS_PATH = Path(__file__).resolve().parent / "decks.json"


def _resolve_data_dir() -> Path:
    if Path("/mnt/main").exists():
        return Path("/mnt/main")
    p = Path(os.path.expanduser("~/.aubieeternal/main"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def progress_path(profile: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in (profile or "Explorer"))[:64]
    d = _resolve_data_dir() / "flashcards"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{safe}.json"


def load_progress(profile: str) -> dict:
    path = progress_path(profile)
    if not path.exists():
        return {"profile": profile, "cards": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"profile": profile, "cards": {}}
        data.setdefault("profile", profile)
        data.setdefault("cards", {})
        return data
    except Exception:
        return {"profile": profile, "cards": {}}


def save_progress(profile: str, data: dict) -> None:
    # Keep only minimal fields
    clean = {"profile": profile, "cards": {}}
    for cid, meta in (data.get("cards") or {}).items():
        if not isinstance(meta, dict):
            continue
        box = int(meta.get("box", 1))
        box = max(1, min(5, box))
        clean["cards"][str(cid)] = {
            "box": box,
            "last_seen": str(meta.get("last_seen") or ""),
        }
    path = progress_path(profile)
    path.write_text(json.dumps(clean, indent=2) + "\n", encoding="utf-8")


def mark_knew(profile: str, card_id: str) -> dict:
    data = load_progress(profile)
    meta = data["cards"].get(card_id, {"box": 1, "last_seen": ""})
    box = min(5, int(meta.get("box", 1)) + 1)
    data["cards"][card_id] = {
        "box": box,
        "last_seen": datetime.now(timezone.utc).isoformat(),
    }
    save_progress(profile, data)
    return data


def mark_practice(profile: str, card_id: str) -> dict:
    data = load_progress(profile)
    data["cards"][card_id] = {
        "box": 1,
        "last_seen": datetime.now(timezone.utc).isoformat(),
    }
    save_progress(profile, data)
    return data


def _now_ts() -> float:
    return time.time()


def _is_due(meta: dict, now: float | None = None) -> bool:
    now = now if now is not None else _now_ts()
    box = max(1, min(5, int(meta.get("box", 1))))
    last = meta.get("last_seen") or ""
    if not last:
        return True
    try:
        # tolerate Z or +00:00
        last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
        last_ts = last_dt.timestamp()
    except Exception:
        return True
    return (now - last_ts) >= _BOX_INTERVALS.get(box, 0)


def deck_progress_stats(profile: str, cards: list[dict]) -> dict:
    """Return known/total and box histogram for a deck's cards."""
    data = load_progress(profile)
    known = 0
    boxes = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for c in cards:
        cid = c["id"]
        meta = data["cards"].get(cid)
        if not meta:
            boxes[1] += 1
            continue
        box = max(1, min(5, int(meta.get("box", 1))))
        boxes[box] += 1
        if box >= 4:
            known += 1
    total = len(cards) or 1
    return {
        "known": known,
        "total": len(cards),
        "pct": int(round(100 * known / total)),
        "boxes": boxes,
    }


def order_cards(profile: str, cards: list[dict], shuffle: bool = False) -> list[dict]:
    """Due cards first (lowest box first), then the rest. Optional shuffle within tiers."""
    data = load_progress(profile)
    now = _now_ts()
    due, later = [], []
    for c in cards:
        meta = data["cards"].get(c["id"], {"box": 1, "last_seen": ""})
        box = max(1, min(5, int(meta.get("box", 1))))
        item = (box, c)
        if _is_due(meta, now):
            due.append(item)
        else:
            later.append(item)
    due.sort(key=lambda x: x[0])
    later.sort(key=lambda x: x[0])
    if shuffle:
        # shuffle within same box
        def _shuffle_tiers(items):
            out = []
            i = 0
            while i < len(items):
                j = i
                while j < len(items) and items[j][0] == items[i][0]:
                    j += 1
                chunk = items[i:j]
                random.shuffle(chunk)
                out.extend(chunk)
                i = j
            return out
        due = _shuffle_tiers(due)
        later = _shuffle_tiers(later)
    return [c for _, c in due + later]


# ?? Static decks ????????????????????????????????????????????????????????????

def load_static_decks() -> dict[str, dict]:
    if not DECKS_PATH.exists():
        return {}
    try:
        data = json.loads(DECKS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    decks = {}
    for d in data.get("decks", []):
        if isinstance(d, dict) and d.get("id"):
            decks[d["id"]] = d
    return decks


# ?? Generators (never run out) ??????????????????????????????????????????????

_COIN_VALUES = [
    ("penny", 1, "??"),
    ("nickel", 5, "??"),
    ("dime", 10, "??"),
    ("quarter", 25, "??"),
]


def generate_basic_math(n: int = 20, seed: int | None = None) -> list[dict]:
    rng = random.Random(seed if seed is not None else time.time_ns())
    cards = []
    for i in range(n):
        op = rng.choice(["+", "-"])
        if op == "+":
            a = rng.randint(0, 10)
            b = rng.randint(0, 10 - a)
            ans = a + b
            front = f"{a} + {b}"
        else:
            a = rng.randint(0, 10)
            b = rng.randint(0, a)
            ans = a - b
            front = f"{a} ? {b}"
        cards.append({
            "id": f"bmath-{i}-{a}{op}{b}",
            "front": front,
            "back": str(ans),
            "hint": "??",
        })
    return cards


def generate_arithmetic(n: int = 20, seed: int | None = None) -> list[dict]:
    rng = random.Random(seed if seed is not None else time.time_ns())
    cards = []
    for i in range(n):
        op = rng.choice(["+", "-", "?", "?"])
        if op == "+":
            a = rng.randint(0, 100)
            b = rng.randint(0, 100 - a)
            ans = a + b
            front = f"{a} + {b}"
        elif op == "-":
            a = rng.randint(0, 100)
            b = rng.randint(0, a)
            ans = a - b
            front = f"{a} ? {b}"
        elif op == "?":
            a = rng.randint(0, 12)
            b = rng.randint(0, 12)
            # keep product within 100
            while a * b > 100:
                a = rng.randint(0, 12)
                b = rng.randint(0, 12)
            ans = a * b
            front = f"{a} ? {b}"
        else:  # ?
            b = rng.randint(1, 12)
            ans = rng.randint(0, min(12, 100 // b))
            a = b * ans
            front = f"{a} ? {b}"
        cards.append({
            "id": f"arith-{i}-{front.replace(' ', '')}",
            "front": front,
            "back": str(ans),
            "hint": "??",
        })
    return cards


def generate_coins(n: int = 20, seed: int | None = None) -> list[dict]:
    rng = random.Random(seed if seed is not None else time.time_ns())
    cards = []
    # Always include single-coin identity cards first (stable ids)
    singles = [
        {"id": "coin-penny", "front": "1 penny", "back": "1?", "hint": "??"},
        {"id": "coin-nickel", "front": "1 nickel", "back": "5?", "hint": "??"},
        {"id": "coin-dime", "front": "1 dime", "back": "10?", "hint": "??"},
        {"id": "coin-quarter", "front": "1 quarter", "back": "25?", "hint": "??"},
    ]
    cards.extend(singles)
    for i in range(max(0, n - len(singles))):
        # 2?4 coin groups
        parts = []
        total = 0
        n_kinds = rng.randint(1, 3)
        kinds = rng.sample(_COIN_VALUES, n_kinds)
        for name, val, _emoji in kinds:
            count = rng.randint(1, 4)
            # keep totals under a dollar for kid-friendliness
            if total + count * val > 99:
                count = max(1, (99 - total) // val) if val else 1
            if count <= 0:
                continue
            total += count * val
            label = name if count == 1 else name + "s"
            parts.append(f"{count} {label}")
        if not parts:
            continue
        front = " + ".join(parts)
        cards.append({
            "id": f"coin-mix-{i}-{total}",
            "front": f"How much is {front}?",
            "back": f"{total}?",
            "hint": "??",
        })
    return cards


def built_in_123() -> dict:
    """Numbers 1?20 with emoji counting pictures."""
    # Prefer countable emoji clusters for 1?10; for 11?20 show numeral + word.
    word = {
        1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
        6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
        11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen", 15: "fifteen",
        16: "sixteen", 17: "seventeen", 18: "eighteen", 19: "nineteen", 20: "twenty",
    }
    cards = []
    for n in range(1, 21):
        if n <= 10:
            pic = "?" * n
        else:
            pic = "??" + ("?" * (n - 10))
        cards.append({
            "id": f"num-{n}",
            "front": str(n),
            "back": f"{word[n]}\n{pic}",
            "hint": pic if n <= 5 else "??",
        })
    return {
        "id": "123",
        "title": "123",
        "emoji": "??",
        "description": "Numbers 1 to 20 with counting pictures",
        "cards": cards,
        "generated": False,
    }


_AGE_ORDER = {"little": 0, "middle": 1, "older": 2, "": 3}

# Built-in catalog skeleton. Static decks.json can override title/emoji/desc/age.
_CATALOG_SKELETON = [
    # Early skills (little-first)
    ("abc", "ABC", "??", "Letters with an example word", False, "little", "4-7", "basics"),
    ("123", "123", "??", "Numbers 1 to 20 with counting pictures", False, "little", "4-7", "basics"),
    ("basic_math", "Basic Math", "?", "Add and subtract within 10", True, "little", "4-8", "basics"),
    ("reading", "Reading", "??", "Sight words and short CVC words", False, "little", "5-8", "basics"),
    ("coins", "Counting Coins", "??", "US pennies, nickels, dimes, quarters", True, "little", "5-9", "money_smarts"),
    # Money Smarts age ladder
    ("money_little", "Money Smarts ? Little", "??", "Needs vs wants, saving jar, price tags", False, "little", "4-7", "money_smarts"),
    ("money_middle", "Money Smarts ? Middle", "??", "Budgeting, simple interest, unit price", False, "middle", "8-12", "money_smarts"),
    ("money_older", "Money Smarts ? Older", "??", "Compound interest, credit, scams, Bitcoin basics", False, "older", "13+", "money_smarts"),
    # Stretch math
    ("arithmetic", "Arithmetic", "??", "Add, subtract, multiply, divide within 100", True, "middle", "8-12", "basics"),
]


def get_deck_catalog() -> list[dict]:
    """Return deck metadata for the picker. Little-kid decks listed first."""
    static = load_static_decks()
    catalog = []

    for deck_id, title, emoji, desc, generated, age, ages, group in _CATALOG_SKELETON:
        if deck_id in static:
            d = static[deck_id]
            catalog.append({
                "id": d.get("id", deck_id),
                "title": d.get("title", title),
                "emoji": d.get("emoji", emoji) or emoji,
                "description": d.get("description", desc),
                "generated": False,
                "n_cards": len(d.get("cards") or []),
                "age_level": d.get("age_level", age),
                "ages": d.get("ages", ages),
                "group": d.get("group", group),
            })
        elif deck_id == "123":
            catalog.append({
                "id": "123", "title": title, "emoji": emoji,
                "description": desc, "generated": False, "n_cards": 20,
                "age_level": age, "ages": ages, "group": group,
            })
        elif generated:
            catalog.append({
                "id": deck_id, "title": title, "emoji": emoji,
                "description": desc, "generated": True, "n_cards": 20,
                "age_level": age, "ages": ages, "group": group,
            })
        else:
            catalog.append({
                "id": deck_id, "title": title, "emoji": emoji,
                "description": desc + (" (coming soon)" if deck_id.startswith("money_") else " (deck file missing)"),
                "generated": False, "n_cards": 0,
                "age_level": age, "ages": ages, "group": group,
            })

    # Also include any extra decks present only in decks.json
    known = {c["id"] for c in catalog}
    for did, d in static.items():
        if did in known:
            continue
        catalog.append({
            "id": did,
            "title": d.get("title", did),
            "emoji": d.get("emoji", "??"),
            "description": d.get("description", ""),
            "generated": False,
            "n_cards": len(d.get("cards") or []),
            "age_level": d.get("age_level", ""),
            "ages": d.get("ages", ""),
            "group": d.get("group", "extra"),
        })

    catalog.sort(key=lambda c: (_AGE_ORDER.get(c.get("age_level") or "", 3), c.get("group") or "", c.get("title") or ""))
    return catalog


def get_deck_cards(deck_id: str, n_generated: int = 20, seed: int | None = None) -> tuple[dict, list[dict]]:
    """Return (meta, cards) for a deck id."""
    static = load_static_decks()
    if deck_id in static:
        d = dict(static[deck_id])
        d.setdefault("age_level", "")
        d.setdefault("ages", "")
        d.setdefault("group", "")
        return d, list(d.get("cards") or [])
    if deck_id == "123":
        d = built_in_123()
        return d, list(d["cards"])
    if deck_id == "basic_math":
        meta = {"id": "basic_math", "title": "Basic Math", "emoji": "?",
                "description": "Add and subtract within 10", "generated": True}
        return meta, generate_basic_math(n_generated, seed=seed)
    if deck_id == "arithmetic":
        meta = {"id": "arithmetic", "title": "Arithmetic", "emoji": "??",
                "description": "Add, subtract, multiply, divide within 100", "generated": True}
        return meta, generate_arithmetic(n_generated, seed=seed)
    if deck_id == "coins":
        meta = {"id": "coins", "title": "Counting Coins", "emoji": "??",
                "description": "US pennies, nickels, dimes, quarters", "generated": True}
        return meta, generate_coins(n_generated, seed=seed)
    return {"id": deck_id, "title": deck_id, "emoji": "??", "description": "", "generated": False}, []

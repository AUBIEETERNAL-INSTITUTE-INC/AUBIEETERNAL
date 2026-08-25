"""
family_profiles.py — AUBIEETERNAL Complete Family System
v68.0 — May 26, 2026
Provides ALL functions app.py needs:
  FamilyAuth, load_family_stats, save_family_stats,
  award_cross_tool_reward, update_streak, get_daily_quests,
  complete_quest, award_badge
"""

import hashlib, hmac, json, os, datetime, random, re, secrets
from pathlib import Path

# ── Path resolution: StartOS /mnt/main takes priority ─────────────────────────
_MNT  = Path("/mnt/main")
_LOCAL = Path("/home/aubie/.aubieeternal/main")
DATA_DIR     = _MNT if _MNT.exists() else _LOCAL
FAMILIES_DIR = DATA_DIR / "families"
FAMILIES_DIR.mkdir(parents=True, exist_ok=True)

# ── Family registry — now REAL, persisted, self-serve account creation ────────
# Used to be 5 hardcoded Python constants (alpha/beta/gamma/delta/wareagle)
# that reset to the same 5 demo accounts on every restart, with no way for
# anyone downloading AUBIEETERNAL to create their own family at all - found
# 2026-08-25 while making onboarding friendlier for new installs. Now backed
# by FAMILY_REGISTRY_PATH (a real file in DATA_DIR, so it survives restarts
# and grows as real families sign up).
#
# FAMILY_REGISTRY stays a plain dict OBJECT that's mutated in place (never
# reassigned wholesale) - several other modules do
# `from family_profiles import FAMILY_REGISTRY` and expect to see live
# updates (phone_ui.py's person picker, the browser extension's /people),
# which only works if this stays the SAME dict object across the app's
# lifetime, not a fresh one swapped in on reload.
FAMILY_REGISTRY_PATH = DATA_DIR / "family_registry.json"
FAMILY_REGISTRY: dict = {}

# Legacy plaintext passcodes for the 5 original demo accounts ONLY - kept
# exactly as they always were (deliberately not retrofitted to hashing,
# since they're trivial "alpha"/"alpha" demo credentials to begin with, not
# real secrets). Any REAL family created via create_family() below gets a
# properly hashed passcode in _PASSCODE_HASHES instead - never plaintext.
PASSCODES: dict = {}
_PASSCODE_HASHES: dict = {}   # family_id -> {"salt": hex, "hash": hex} (PBKDF2-HMAC-SHA256)

# What ships as demo accounts on a machine that already has real usage
# (i.e. this Ryzen instance) - NOT what a brand-new install starts with.
# A fresh install (no family_registry.json AND no existing family stat
# files under FAMILIES_DIR) starts completely empty and goes straight to
# "create your first family" - no demo accounts pre-seeded, so a new
# downloader never has to reuse someone else's identities.
_LEGACY_DEMO_REGISTRY = {
    "alpha": {
        "family_id":    "alpha",
        "display_name": "Family Alpha",
        "kid_name":     "Explorer",
        "kid_age":      9,
        "parent_name":  "Parent Alpha",
        "emoji":        "🦅",
        "color":        "#FF6B35",
        "is_operator":  False,
    },
    "beta": {
        "family_id":    "beta",
        "display_name": "Family Beta",
        "kid_name":     "Seeker",
        "kid_age":      9,
        "parent_name":  "Parent Beta",
        "emoji":        "⚡",
        "color":        "#4ECDC4",
        "is_operator":  False,
    },
    "gamma": {
        "family_id":    "gamma",
        "display_name": "Family Gamma",
        "kid_name":     "Builder",
        "kid_age":      9,
        "parent_name":  "Parent Gamma",
        "emoji":        "🌿",
        "color":        "#45B7D1",
        "is_operator":  False,
    },
    "delta": {
        "family_id":    "delta",
        "display_name": "Family Delta",
        "kid_name":     "Thinker",
        "kid_age":      9,
        "parent_name":  "Parent Delta",
        "emoji":        "🔥",
        "color":        "#96CEB4",
        "is_operator":  False,
    },
    "wareagle": {
        "family_id":    "wareagle",
        "display_name": "Operator",
        "kid_name":     "Operator",
        "kid_age":      9,
        "parent_name":  "Mateo",
        "emoji":        "🛡️",
        "color":        "#DDA0DD",
        "is_operator":  True,
    },
}
_LEGACY_DEMO_PASSCODES = {
    "alpha": "alpha", "beta": "beta", "gamma": "gamma",
    "delta": "delta", "wareagle": "wareagle",
}


def _save_registry() -> None:
    FAMILY_REGISTRY_PATH.write_text(json.dumps(
        {"families": FAMILY_REGISTRY, "passcodes": PASSCODES,
         "passcode_hashes": _PASSCODE_HASHES}, indent=2,
    ))


def _load_registry() -> None:
    """Runs once at import time. Loads the real registry file if one
    exists; otherwise seeds from the legacy demo accounts ONLY if this
    machine already has real usage under those IDs (protects THIS
    instance's existing families), else starts genuinely empty."""
    if FAMILY_REGISTRY_PATH.exists():
        try:
            data = json.loads(FAMILY_REGISTRY_PATH.read_text())
            FAMILY_REGISTRY.update(data.get("families", {}))
            PASSCODES.update(data.get("passcodes", {}))
            _PASSCODE_HASHES.update(data.get("passcode_hashes", {}))
            return
        except Exception:
            pass  # corrupt file - fall through and re-seed/start fresh below

    existing_usage = any((FAMILIES_DIR / f"{fid}.json").exists() for fid in _LEGACY_DEMO_REGISTRY)
    if existing_usage:
        FAMILY_REGISTRY.update(_LEGACY_DEMO_REGISTRY)
        PASSCODES.update(_LEGACY_DEMO_PASSCODES)
    _save_registry()


def _hash_passcode(passcode: str, salt_hex: str | None = None) -> tuple[str, str]:
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", passcode.encode(), salt, 200_000)
    return salt.hex(), digest.hex()


def _verify_passcode(passcode: str, salt_hex: str, hash_hex: str) -> bool:
    _, computed = _hash_passcode(passcode, salt_hex)
    return hmac.compare_digest(computed, hash_hex)


_load_registry()

DEFAULT_STATE = {
    "total_xp":              0,
    "level":                 1,
    "badges":                [],
    "certifications":        [],
    "cross_tool_activities": [],
    "lessons_completed":     [],
    "coherence_history":     [],
    "child_rune_fragments":  0,
    "humanity_contributions": 0,
    "streak_days":           0,
    "last_session_date":     "",
    "sats_earned":           0,
    "quests_completed":      [],
    "model_preferences": {
        "default":   "qwen2.5:14b",
        "fast":      "qwen2.5:7b",
        "heavy":     "qwen2.5:32b",
        "synthesis": "qwen2.5:32b",
        "chat":      "qwen2.5:7b",
    },
    "thinking_mode": "⚖️ Balanced",
    "last_updated":  datetime.datetime.now().isoformat(),
}

# ── Daily quest pool ───────────────────────────────────────────────────────────
QUEST_POOL = [
    {"id": "q_steelman",    "title": "Steelman one idea you disagree with",       "xp": 20, "sats": 21, "category": "truth"},
    {"id": "q_btc",         "title": "Check the Bitcoin block height",             "xp": 10, "sats": 10, "category": "bitcoin"},
    {"id": "q_oracle",      "title": "Ask the Oracle one genuine question",        "xp": 15, "sats": 15, "category": "learning"},
    {"id": "q_antifrag",    "title": "Name one thing that made you stronger today","xp": 15, "sats": 15, "category": "antifragility"},
    {"id": "q_memory",      "title": "Save one insight to the Memory Palace",      "xp": 10, "sats": 10, "category": "memory"},
    {"id": "q_family",      "title": "Share one insight with a family member",     "xp": 20, "sats": 21, "category": "family"},
    {"id": "q_lesson",      "title": "Complete one curriculum lesson",             "xp": 25, "sats": 25, "category": "learning"},
    {"id": "q_falsify",     "title": "Find one claim you believed that was wrong", "xp": 20, "sats": 21, "category": "truth"},
    {"id": "q_sovereignty", "title": "Do one thing today that increases sovereignty","xp": 15, "sats": 15, "category": "sovereignty"},
    {"id": "q_reading",     "title": "Read one chapter or article",                "xp": 10, "sats": 10, "category": "learning"},
]


# ══════════════════════════════════════════════════════════════════════════════
# FamilyAuth — authentication + family listing
# ══════════════════════════════════════════════════════════════════════════════

_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{1,31}$")
_PALETTE = [
    ("🦅", "#FF6B35"), ("⚡", "#4ECDC4"), ("🌿", "#45B7D1"), ("🔥", "#96CEB4"),
    ("🌙", "#C77DFF"), ("🎨", "#FFD166"), ("🚀", "#06D6A0"), ("🦋", "#EF476F"),
]


class FamilyAuth:

    def authenticate(self, code: str):
        """Returns family dict or None. Checks real hashed passcodes
        (self-created families) first, then falls back to the legacy
        plaintext demo passcodes (alpha/beta/gamma/delta/wareagle only)."""
        code = code.strip()
        if not code:
            return None

        for fid, entry in _PASSCODE_HASHES.items():
            if fid in FAMILY_REGISTRY and _verify_passcode(code, entry["salt"], entry["hash"]):
                return FAMILY_REGISTRY[fid].copy()

        fid = PASSCODES.get(code.lower())
        if fid and fid in FAMILY_REGISTRY:
            return FAMILY_REGISTRY[fid].copy()

        return None

    def login(self, code: str):
        """Alias for authenticate — used by School tab and app.py."""
        return self.authenticate(code)

    def list_families(self) -> list:
        """All families except operator (unless you want operator too).
        Never includes passcode hashes - those live in a separate dict
        that list callers never touch."""
        return [
            info.copy()
            for fid, info in FAMILY_REGISTRY.items()
        ]

    def get_family_info(self, family_id: str) -> dict:
        return FAMILY_REGISTRY.get(
            family_id,
            {"family_id": family_id, "display_name": family_id,
             "kid_name": "Explorer", "parent_name": "Parent",
             "emoji": "👤", "color": "#888", "is_operator": False}
        ).copy()

    def create_family(self, family_id: str, display_name: str, passcode: str,
                       kid_name: str = "Explorer", kid_age: int = 9,
                       parent_name: str = "Parent") -> dict:
        """Real, persisted self-serve account creation - the actual thing
        a new AUBIEETERNAL install needs so someone downloading it isn't
        stuck reusing this machine's demo families. Raises ValueError with
        a clear reason on any validation failure (bad id, taken, no
        passcode) - callers should catch and show the message, not assume
        this always succeeds."""
        family_id = family_id.strip().lower().replace(" ", "_")
        if not _ID_PATTERN.match(family_id):
            raise ValueError("Family ID must be 2-32 characters: lowercase letters, numbers, - or _ only.")
        if family_id in FAMILY_REGISTRY:
            raise ValueError(f"'{family_id}' is already taken - choose a different family ID.")
        if not passcode or len(passcode) < 4:
            raise ValueError("Passcode must be at least 4 characters.")
        if not display_name.strip():
            raise ValueError("Display name is required.")

        emoji, color = _PALETTE[len(FAMILY_REGISTRY) % len(_PALETTE)]
        entry = {
            "family_id":    family_id,
            "display_name": display_name.strip(),
            "kid_name":     kid_name.strip() or "Explorer",
            "kid_age":      int(kid_age),
            "parent_name":  parent_name.strip() or "Parent",
            "emoji":        emoji,
            "color":        color,
            "is_operator":  False,
        }
        salt_hex, hash_hex = _hash_passcode(passcode)
        _PASSCODE_HASHES[family_id] = {"salt": salt_hex, "hash": hash_hex}
        FAMILY_REGISTRY[family_id] = entry  # mutate in place - see module docstring
        _save_registry()
        return entry.copy()

    def update_family(self, family_id: str, updates: dict) -> bool:
        """Updates an existing family's profile fields. A "new_passcode"
        key (if present and non-empty) is hashed and replaces whatever
        passcode the family had before - including upgrading a legacy
        plaintext demo account to a real hashed one the moment its
        passcode is ever changed."""
        if family_id not in FAMILY_REGISTRY:
            return False

        entry = FAMILY_REGISTRY[family_id]
        for field in ("display_name", "kid_name", "parent_name", "emoji", "color"):
            if field in updates and updates[field]:
                entry[field] = updates[field]
        if "kid_age" in updates:
            try:
                entry["kid_age"] = int(updates["kid_age"])
            except (TypeError, ValueError):
                pass

        new_passcode = updates.get("new_passcode")
        if new_passcode:
            salt_hex, hash_hex = _hash_passcode(new_passcode)
            _PASSCODE_HASHES[family_id] = {"salt": salt_hex, "hash": hash_hex}
            PASSCODES.pop(family_id, None)  # hashed version now takes precedence

        _save_registry()
        return True


# ══════════════════════════════════════════════════════════════════════════════
# Stats — load / save
# ══════════════════════════════════════════════════════════════════════════════

def load_family_stats(family_id: str = "default") -> dict:
    path = FAMILIES_DIR / f"{family_id}.json"
    if path.exists():
        try:
            data = json.loads(path.read_text())
            # Backfill any missing keys from DEFAULT_STATE
            for k, v in DEFAULT_STATE.items():
                if k not in data:
                    data[k] = v
            return data
        except Exception:
            pass
    s = DEFAULT_STATE.copy()
    s["family_id"] = family_id
    return s


def save_family_stats(stats: dict, family_id: str = "default"):
    path = FAMILIES_DIR / f"{family_id}.json"
    stats["last_updated"] = datetime.datetime.now().isoformat()
    path.write_text(json.dumps(stats, indent=2))


# ══════════════════════════════════════════════════════════════════════════════
# XP + Badges + Streak
# ══════════════════════════════════════════════════════════════════════════════

def award_cross_tool_reward(family_id: str, source: str, activity: str,
                            xp: int = 0, badge: str = None) -> dict:
    """Idempotent XP award across tools."""
    stats        = load_family_stats(family_id)
    activity_key = f"{source}:{activity}"
    if activity_key not in stats.get("cross_tool_activities", []):
        stats.setdefault("cross_tool_activities", []).append(activity_key)
        stats["total_xp"] = stats.get("total_xp", 0) + xp
        stats["level"]    = max(1, stats["total_xp"] // 100 + 1)
        if badge and badge not in stats.get("badges", []):
            stats.setdefault("badges", []).append(badge)
    save_family_stats(stats, family_id)
    return {"xp_added": xp, "new_level": stats["level"], "badge": badge}


def award_badge(family_id: str, badge_name: str) -> dict:
    """Award a named badge to a family."""
    stats = load_family_stats(family_id)
    if badge_name not in stats.get("badges", []):
        stats.setdefault("badges", []).append(badge_name)
        save_family_stats(stats, family_id)
    return {"badge": badge_name, "total_badges": len(stats.get("badges", []))}


def update_streak(family_id: str) -> int:
    """
    Call once per session. Increments streak if last session was yesterday,
    resets to 1 if gap > 1 day, keeps same if already updated today.
    Returns current streak count.
    """
    stats     = load_family_stats(family_id)
    today     = datetime.date.today().isoformat()
    last_date = stats.get("last_session_date", "")

    if last_date == today:
        return stats.get("streak_days", 1)

    if last_date:
        try:
            last_dt = datetime.date.fromisoformat(last_date)
            delta   = (datetime.date.today() - last_dt).days
            if delta == 1:
                stats["streak_days"] = stats.get("streak_days", 0) + 1
            elif delta > 1:
                stats["streak_days"] = 1
        except Exception:
            stats["streak_days"] = 1
    else:
        stats["streak_days"] = 1

    stats["last_session_date"] = today
    save_family_stats(stats, family_id)
    return stats["streak_days"]


# ══════════════════════════════════════════════════════════════════════════════
# Daily Quests
# ══════════════════════════════════════════════════════════════════════════════

def get_daily_quests(family_id: str, n: int = 5) -> list:
    """
    Return today's quests for a family.
    Seeded by family_id + date so same quests all day, different each day.
    Marks completed ones.
    """
    stats     = load_family_stats(family_id)
    completed = set(stats.get("quests_completed", []))
    today     = datetime.date.today().isoformat()

    # Seed random with family + date so quests are consistent all day
    seed  = hash(f"{family_id}:{today}") % (2**32)
    rng   = random.Random(seed)
    pool  = QUEST_POOL.copy()
    rng.shuffle(pool)
    quests = pool[:n]

    # Tag each as completed or not
    for q in quests:
        daily_key         = f"{today}:{q['id']}"
        q["completed"]    = daily_key in completed
        q["daily_key"]    = daily_key

    return quests


def complete_quest(family_id: str, quest_id: str) -> dict:
    """
    Mark a quest as complete. Awards XP. Returns result dict.
    quest_id should be the daily_key: "YYYY-MM-DD:q_xxx"
    """
    stats = load_family_stats(family_id)
    stats.setdefault("quests_completed", [])

    if quest_id not in stats["quests_completed"]:
        # Find XP for this quest
        base_id = quest_id.split(":", 1)[-1] if ":" in quest_id else quest_id
        xp      = next((q["xp"] for q in QUEST_POOL if q["id"] == base_id), 10)
        stats["quests_completed"].append(quest_id)
        stats["total_xp"] = stats.get("total_xp", 0) + xp
        stats["level"]    = max(1, stats["total_xp"] // 100 + 1)
        # Find sats for this quest too
        sats = next((q["sats"] for q in QUEST_POOL if q["id"] == base_id), 0)
        stats["sats_earned"] = stats.get("sats_earned", 0) + sats
        save_family_stats(stats, family_id)
        return {"completed": True, "xp": xp, "xp_awarded": xp,
                "sats": sats, "new_level": stats["level"]}
    return {"completed": False, "xp": 0, "xp_awarded": 0, "sats": 0}


# ── Module-level compat ────────────────────────────────────────────────────────

def get_current_family_id() -> str:
    return "default"

def get_model_for_family_task(family_id: str, task: str = "default") -> str:
    stats = load_family_stats(family_id)
    return stats.get("model_preferences", DEFAULT_STATE["model_preferences"]).get(
        task, "qwen2.5:14b"
    )


# ── Standalone test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    auth = FamilyAuth()
    fam  = auth.authenticate("alpha")
    print(f"Auth: {fam['display_name']} | kid: {fam['kid_name']}")
    all_fams = auth.list_families()
    print(f"Families: {[f['display_name'] for f in all_fams]}")
    streak = update_streak("alpha")
    print(f"Streak: {streak}")
    quests = get_daily_quests("alpha")
    print(f"Quests: {[q['title'] for q in quests]}")
    result = complete_quest("alpha", quests[0]["daily_key"])
    print(f"Quest complete: {result}")
    stats = load_family_stats("alpha")
    print(f"XP: {stats['total_xp']} | Level: {stats['level']}")

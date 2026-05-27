"""
family_profiles.py — AUBIEETERNAL Complete Family System
v68.0 — May 26, 2026
Provides ALL functions app.py needs:
  FamilyAuth, load_family_stats, save_family_stats,
  award_cross_tool_reward, update_streak, get_daily_quests,
  complete_quest, award_badge
"""

import json, os, datetime, random
from pathlib import Path

# ── Path resolution: StartOS /mnt/main takes priority ─────────────────────────
_MNT  = Path("/mnt/main")
_LOCAL = Path("/home/aubie/.aubieeternal/main")
DATA_DIR     = _MNT if _MNT.exists() else _LOCAL
FAMILIES_DIR = DATA_DIR / "families"
FAMILIES_DIR.mkdir(parents=True, exist_ok=True)

# ── Family registry — 4 families + operator ───────────────────────────────────
FAMILY_REGISTRY = {
    "alpha": {
        "family_id":    "alpha",
        "display_name": "Family Alpha",
        "kid_name":     "Explorer",
        "parent_name":  "Parent Alpha",
        "emoji":        "🦅",
        "color":        "#FF6B35",
        "is_operator":  False,
    },
    "beta": {
        "family_id":    "beta",
        "display_name": "Family Beta",
        "kid_name":     "Seeker",
        "parent_name":  "Parent Beta",
        "emoji":        "⚡",
        "color":        "#4ECDC4",
        "is_operator":  False,
    },
    "gamma": {
        "family_id":    "gamma",
        "display_name": "Family Gamma",
        "kid_name":     "Builder",
        "parent_name":  "Parent Gamma",
        "emoji":        "🌿",
        "color":        "#45B7D1",
        "is_operator":  False,
    },
    "delta": {
        "family_id":    "delta",
        "display_name": "Family Delta",
        "kid_name":     "Thinker",
        "parent_name":  "Parent Delta",
        "emoji":        "🔥",
        "color":        "#96CEB4",
        "is_operator":  False,
    },
    "wareagle": {
        "family_id":    "wareagle",
        "display_name": "Operator",
        "kid_name":     "Operator",
        "parent_name":  "Mateo",
        "emoji":        "🛡️",
        "color":        "#DDA0DD",
        "is_operator":  True,
    },
}

PASSCODES = {
    "alpha":    "alpha",
    "beta":     "beta",
    "gamma":    "gamma",
    "delta":    "delta",
    "wareagle": "wareagle",
}

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
    {"id": "q_steelman",    "title": "Steelman one idea you disagree with",      "xp": 20, "category": "truth"},
    {"id": "q_btc",         "title": "Check the Bitcoin block height",            "xp": 10, "category": "bitcoin"},
    {"id": "q_oracle",      "title": "Ask the Oracle one genuine question",       "xp": 15, "category": "learning"},
    {"id": "q_antifrag",    "title": "Name one thing that made you stronger today","xp": 15, "category": "antifragility"},
    {"id": "q_memory",      "title": "Save one insight to the Memory Palace",     "xp": 10, "category": "memory"},
    {"id": "q_family",      "title": "Share one insight with a family member",    "xp": 20, "category": "family"},
    {"id": "q_lesson",      "title": "Complete one curriculum lesson",            "xp": 25, "category": "learning"},
    {"id": "q_falsify",     "title": "Find one claim you believed that was wrong","xp": 20, "category": "truth"},
    {"id": "q_sovereignty", "title": "Do one thing today that increases sovereignty","xp": 15, "category": "sovereignty"},
    {"id": "q_reading",     "title": "Read one chapter or article",               "xp": 10, "category": "learning"},
]


# ══════════════════════════════════════════════════════════════════════════════
# FamilyAuth — authentication + family listing
# ══════════════════════════════════════════════════════════════════════════════

class FamilyAuth:

    def authenticate(self, code: str):
        """Returns family dict or None."""
        fid = PASSCODES.get(code.lower().strip())
        if fid:
            return FAMILY_REGISTRY[fid].copy()
        return None

    def list_families(self) -> list:
        """All families except operator (unless you want operator too)."""
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
        save_family_stats(stats, family_id)
        return {"completed": True, "xp_awarded": xp, "new_level": stats["level"]}
    return {"completed": False, "xp_awarded": 0}


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

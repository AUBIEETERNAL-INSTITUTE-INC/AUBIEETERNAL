"""
family_profiles.py — AUBIEETERNAL Family Profiles + Auth + Gamification
Updated: v67.5 — May 26, 2026
Includes: model_preferences, cross-tool rewards, correct StartOS paths
"""

import json, os, hashlib
from datetime import datetime
from pathlib import Path

# ── Path resolution: StartOS /mnt/main takes priority ─────────────────────────
_MNT_MAIN = Path("/mnt/main")
_LOCAL    = Path("/home/aubie/.aubieeternal/main")
DATA_DIR  = _MNT_MAIN if _MNT_MAIN.exists() else _LOCAL

FAMILIES_DIR = DATA_DIR / "families"
FAMILIES_DIR.mkdir(parents=True, exist_ok=True)

# ── Pre-configured families ────────────────────────────────────────────────────
FAMILY_REGISTRY = {
    "alpha":    {"display_name": "Family Alpha",   "emoji": "🦅", "color": "#FF6B35"},
    "beta":     {"display_name": "Family Beta",    "emoji": "⚡", "color": "#4ECDC4"},
    "gamma":    {"display_name": "Family Gamma",   "emoji": "🌿", "color": "#45B7D1"},
    "delta":    {"display_name": "Family Delta",   "emoji": "🔥", "color": "#96CEB4"},
    "wareagle": {"display_name": "Operator",       "emoji": "🛡️", "color": "#DDA0DD"},
}

PASSCODES = {
    "alpha":    "alpha",
    "beta":     "beta",
    "gamma":    "gamma",
    "delta":    "delta",
    "wareagle": "wareagle",
}

DEFAULT_STATE = {
    "total_xp": 0,
    "level": 1,
    "badges": [],
    "certifications": [],
    "cross_tool_activities": [],
    "lessons_completed": [],
    "coherence_history": [],
    "child_rune_fragments": 0,
    "humanity_contributions": 0,
    "model_preferences": {
        "default":   "qwen2.5:14b",
        "fast":      "qwen2.5:7b",
        "heavy":     "qwen2.5:32b",
        "synthesis": "qwen2.5:32b",
        "chat":      "qwen2.5:7b",
    },
    "thinking_mode": "Balanced",
    "last_updated": datetime.now().isoformat(),
}


class FamilyAuth:
    """Multi-family auth + profile management."""

    def authenticate(self, code: str) -> dict | None:
        """Authenticate a family by passcode. Returns family info or None."""
        fid = PASSCODES.get(code.lower().strip())
        if fid:
            info = FAMILY_REGISTRY[fid].copy()
            info["family_id"] = fid
            return info
        return None

    def list_families(self) -> list:
        """Return all registered families."""
        return [
            {"family_id": fid, **info}
            for fid, info in FAMILY_REGISTRY.items()
            if fid != "wareagle"
        ]

    def get_family_info(self, family_id: str) -> dict:
        info = FAMILY_REGISTRY.get(family_id, {"display_name": family_id, "emoji": "👤", "color": "#888"})
        return {"family_id": family_id, **info}


class FamilyStats:
    """Load/save family stats with model preferences."""

    @staticmethod
    def load(family_id: str = "default") -> dict:
        path = FAMILIES_DIR / f"{family_id}.json"
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:
                pass
        return DEFAULT_STATE.copy()

    @staticmethod
    def save(stats: dict, family_id: str = "default"):
        path = FAMILIES_DIR / f"{family_id}.json"
        stats["last_updated"] = datetime.now().isoformat()
        path.write_text(json.dumps(stats, indent=2))

    @staticmethod
    def get_model(family_id: str, task: str = "default") -> str:
        """Get the preferred model for this family + task."""
        stats = FamilyStats.load(family_id)
        return stats.get("model_preferences", DEFAULT_STATE["model_preferences"]).get(
            task, "qwen2.5:14b"
        )

    @staticmethod
    def set_thinking_mode(family_id: str, mode: str):
        """Set thinking mode: Fast | Balanced | Deep Thinking"""
        stats = FamilyStats.load(family_id)
        stats["thinking_mode"] = mode
        FamilyStats.save(stats, family_id)


# ── Module-level convenience functions (backwards-compatible) ──────────────────

def load_family_stats(family_id: str = "default") -> dict:
    return FamilyStats.load(family_id)

def save_family_stats(stats: dict, family_id: str = "default"):
    FamilyStats.save(stats, family_id)

def award_cross_tool_reward(family_id: str, source: str, activity: str,
                            xp: int = 0, badge: str | None = None) -> dict:
    """
    Award XP + badge when a family completes an activity across any tool.
    Idempotent: same activity can only be awarded once per family.
    """
    stats       = load_family_stats(family_id)
    activity_key = f"{source}:{activity}"

    if activity_key not in stats.get("cross_tool_activities", []):
        stats.setdefault("cross_tool_activities", []).append(activity_key)
        stats["total_xp"] = stats.get("total_xp", 0) + xp
        stats["level"]    = max(1, stats["total_xp"] // 100 + 1)
        if badge and badge not in stats.get("badges", []):
            stats.setdefault("badges", []).append(badge)

    save_family_stats(stats, family_id)
    return {"xp_added": xp, "new_level": stats["level"], "badge": badge}

def get_current_family_id() -> str:
    """Placeholder — overridden by session_state in app.py."""
    return "default"

def get_model_for_family_task(family_id: str, task: str = "default") -> str:
    """Get the right Ollama model for this family + task type."""
    return FamilyStats.get_model(family_id, task)


# ── Standalone test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    auth = FamilyAuth()
    result = auth.authenticate("alpha")
    print(f"Auth test: {result}")
    stats = load_family_stats("alpha")
    print(f"Loaded stats: level={stats['level']} xp={stats['total_xp']}")
    reward = award_cross_tool_reward("alpha", "school", "lesson_truth_1", xp=25, badge="🔍 Signal Seeker")
    print(f"Reward: {reward}")
    model = get_model_for_family_task("alpha", "fast")
    print(f"Fast model for alpha: {model}")

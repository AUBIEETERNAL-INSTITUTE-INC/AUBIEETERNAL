"""
family_profiles.py — AUBIEETERNAL Multi-Family Auth + Data Isolation
====================================================================
Manages 4-family sovereign lattice. Each family gets:
  - Unique family_id + npub
  - Isolated data directory (/mnt/main/families/{family_id}/)
  - Per-family sessions, coherence, XP, Child Rune progress
  - Simple PIN or npub login (zero friction for non-technical families)

Operator can pre-configure all 4 families and hand out login codes.

Usage:
    from family_profiles import FamilyAuth, get_current_family
    auth = FamilyAuth()
    family = auth.login("alpha")  # returns family dict or None
"""

import json, hashlib, datetime
from pathlib import Path

FAMILIES_DIR = Path("/mnt/main/families")
REGISTRY     = FAMILIES_DIR / "registry.json"

# ── 4 pre-configured gift families ───────────────────────────────────────────
DEFAULT_FAMILIES = {
    "family_alpha": {
        "family_id":    "family_alpha",
        "display_name": "Family Alpha",
        "login_code":   "alpha",
        "kid_name":     "Explorer",
        "kid_age":      9,
        "parent_name":  "Parent",
        "npub":         "",
        "color":        "#00cfff",
        "emoji":        "🦅",
        "nostr_relays": [
            "wss://relay.damus.io",
            "wss://nos.lol",
        ],
        "created_at":   datetime.datetime.now().isoformat(),
        "active":       True,
    },
    "family_beta": {
        "family_id":    "family_beta",
        "display_name": "Family Beta",
        "login_code":   "beta",
        "kid_name":     "Scout",
        "kid_age":      10,
        "parent_name":  "Parent",
        "npub":         "",
        "color":        "#a020f0",
        "emoji":        "⚡",
        "nostr_relays": ["wss://relay.damus.io", "wss://nos.lol"],
        "created_at":   datetime.datetime.now().isoformat(),
        "active":       True,
    },
    "family_gamma": {
        "family_id":    "family_gamma",
        "display_name": "Family Gamma",
        "login_code":   "gamma",
        "kid_name":     "Sage",
        "kid_age":      8,
        "parent_name":  "Parent",
        "npub":         "",
        "color":        "#00ff88",
        "emoji":        "🌀",
        "nostr_relays": ["wss://relay.damus.io", "wss://nos.lol"],
        "created_at":   datetime.datetime.now().isoformat(),
        "active":       True,
    },
    "family_delta": {
        "family_id":    "family_delta",
        "display_name": "Family Delta",
        "login_code":   "delta",
        "kid_name":     "Nova",
        "kid_age":      11,
        "parent_name":  "Parent",
        "npub":         "",
        "color":        "#f7931a",
        "emoji":        "🔴",
        "nostr_relays": ["wss://relay.damus.io", "wss://nos.lol"],
        "created_at":   datetime.datetime.now().isoformat(),
        "active":       True,
    },
    "operator": {
        "family_id":    "operator",
        "display_name": "AUBIEETERNAL Operator",
        "login_code":   "wareagle",
        "kid_name":     "Gaby",
        "kid_age":      9,
        "parent_name":  "Mateo",
        "npub":         "",
        "color":        "#ff6b35",
        "emoji":        "🦅",
        "nostr_relays": ["wss://relay.damus.io", "wss://nos.lol"],
        "created_at":   datetime.datetime.now().isoformat(),
        "active":       True,
        "is_operator":  True,
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# FAMILY AUTH
# ══════════════════════════════════════════════════════════════════════════════

class FamilyAuth:

    def __init__(self):
        FAMILIES_DIR.mkdir(parents=True, exist_ok=True)
        self.registry = self._load_registry()

    def _load_registry(self) -> dict:
        if REGISTRY.exists():
            try:
                return json.loads(REGISTRY.read_text())
            except Exception:
                pass
        # First run — write defaults
        REGISTRY.write_text(json.dumps(DEFAULT_FAMILIES, indent=2))
        # Create per-family dirs
        for fid in DEFAULT_FAMILIES:
            (FAMILIES_DIR / fid).mkdir(parents=True, exist_ok=True)
        return DEFAULT_FAMILIES

    def save_registry(self):
        REGISTRY.write_text(json.dumps(self.registry, indent=2))

    def login(self, code: str) -> dict | None:
        """
        Login by code (e.g. 'alpha', 'beta', 'wareagle') or npub.
        Returns family dict or None.
        """
        code = code.strip().lower()
        for fid, fam in self.registry.items():
            if (fam.get("login_code","").lower() == code or
                (fam.get("npub","") and fam["npub"].lower() == code)):
                # Update last_login
                fam["last_login"] = datetime.datetime.now().isoformat()
                self.save_registry()
                return fam
        return None

    def get_family(self, family_id: str) -> dict | None:
        return self.registry.get(family_id)

    def list_families(self) -> list:
        return [f for f in self.registry.values() if f.get("active")]

    def update_family(self, family_id: str, updates: dict) -> dict:
        if family_id not in self.registry:
            raise ValueError(f"Unknown family: {family_id}")
        self.registry[family_id].update(updates)
        self.save_registry()
        return self.registry[family_id]

    def create_family(self, family_id: str, display_name: str,
                      login_code: str, kid_name: str, kid_age: int,
                      parent_name: str, color: str = "#00cfff",
                      emoji: str = "🦅") -> dict:
        """Add a new family (beyond the default 4)."""
        fam = {
            "family_id":    family_id,
            "display_name": display_name,
            "login_code":   login_code.lower(),
            "kid_name":     kid_name,
            "kid_age":      kid_age,
            "parent_name":  parent_name,
            "npub":         "",
            "color":        color,
            "emoji":        emoji,
            "nostr_relays": ["wss://relay.damus.io", "wss://nos.lol"],
            "created_at":   datetime.datetime.now().isoformat(),
            "active":       True,
        }
        self.registry[family_id] = fam
        (FAMILIES_DIR / family_id).mkdir(parents=True, exist_ok=True)
        self.save_registry()
        return fam


# ══════════════════════════════════════════════════════════════════════════════
# PER-FAMILY DATA PATHS
# ══════════════════════════════════════════════════════════════════════════════

def family_path(family_id: str, filename: str) -> Path:
    """Get isolated file path for a family."""
    p = FAMILIES_DIR / family_id
    p.mkdir(parents=True, exist_ok=True)
    return p / filename

def load_family_stats(family_id: str) -> dict:
    """Load gamification stats for a family."""
    stats_path = family_path(family_id, "stats.json")
    if stats_path.exists():
        try:
            return json.loads(stats_path.read_text())
        except Exception:
            pass
    defaults = {
        "family_id":         family_id,
        "total_xp":          0,
        "level":             1,
        "streak_days":       0,
        "last_session_date": "",
        "badges":            [],
        "lessons_completed": [],
        "coherence_history": [],
        "child_rune_fragments": 0,
        "sats_earned":       0,
        "daily_quests_completed": [],
        "experiments_run":   0,
    }
    stats_path.write_text(json.dumps(defaults, indent=2))
    return defaults

def save_family_stats(family_id: str, stats: dict):
    family_path(family_id, "stats.json").write_text(json.dumps(stats, indent=2))

def update_streak(family_id: str) -> int:
    """Check and update daily streak. Returns current streak count."""
    stats    = load_family_stats(family_id)
    today    = datetime.date.today().isoformat()
    last     = stats.get("last_session_date", "")
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

    if last == today:
        return stats.get("streak_days", 1)
    elif last == yesterday:
        stats["streak_days"] = stats.get("streak_days", 0) + 1
    else:
        stats["streak_days"] = 1  # reset

    stats["last_session_date"] = today
    save_family_stats(family_id, stats)
    return stats["streak_days"]

def award_badge(family_id: str, badge: str) -> bool:
    """Award a badge if not already earned. Returns True if new."""
    stats = load_family_stats(family_id)
    if badge not in stats["badges"]:
        stats["badges"].append(badge)
        save_family_stats(family_id, stats)
        return True
    return False

def get_daily_quests(family_id: str) -> list:
    """Generate today's 3 daily quests for a family."""
    import random
    stats   = load_family_stats(family_id)
    today   = datetime.date.today().isoformat()
    done    = [q for q in stats.get("daily_quests_completed", []) if q.startswith(today)]

    all_quests = [
        {"id": "steelman_1",   "title": "Complete 1 steelman answer",       "xp": 20,  "sats": 50},
        {"id": "courage",      "title": "Do one scary thing today",          "xp": 25,  "sats": 75},
        {"id": "read_digest",  "title": "Read today's morning synthesis",    "xp": 10,  "sats": 25},
        {"id": "parent_obs",   "title": "Parent: observe a full kid session","xp": 15,  "sats": 40},
        {"id": "via_neg",      "title": "Remove one bad habit today",        "xp": 20,  "sats": 50},
        {"id": "btc_check",    "title": "Check the Bitcoin block height",    "xp": 5,   "sats": 10},
        {"id": "nostr_share",  "title": "Share one insight to Nostr",        "xp": 15,  "sats": 35},
        {"id": "experiment",   "title": "Run one Sandbox experiment",        "xp": 30,  "sats": 80},
        {"id": "grokipedia",   "title": "Learn one new Grokipedia principle","xp": 15,  "sats": 30},
        {"id": "polyvagal",    "title": "Practice 4-7-8 breathing together", "xp": 10,  "sats": 20},
    ]

    # Deterministic daily selection (same quests all day for a family)
    seed = hash(f"{family_id}_{today}") % len(all_quests)
    random.seed(seed)
    daily = random.sample(all_quests, 3)

    for q in daily:
        q["completed"] = f"{today}_{q['id']}" in done

    return daily

def complete_quest(family_id: str, quest_id: str) -> dict:
    """Mark a daily quest complete. Returns XP and sats earned."""
    today  = datetime.date.today().isoformat()
    key    = f"{today}_{quest_id}"
    stats  = load_family_stats(family_id)

    if key in stats.get("daily_quests_completed", []):
        return {"already_done": True, "xp": 0, "sats": 0}

    quests = get_daily_quests(family_id)
    quest  = next((q for q in quests if q["id"] == quest_id), None)
    if not quest:
        return {"error": "Quest not found"}

    stats.setdefault("daily_quests_completed", []).append(key)
    stats["total_xp"] = stats.get("total_xp", 0) + quest["xp"]
    stats["level"]    = max(1, stats["total_xp"] // 100 + 1)
    stats["sats_earned"] = stats.get("sats_earned", 0) + quest["sats"]
    save_family_stats(family_id, stats)

    # Auto-badge checks
    if len([q for q in stats["daily_quests_completed"] if q.startswith(today)]) >= 3:
        award_badge(family_id, "🌟 Daily Champion")
    if stats["streak_days"] >= 7:
        award_badge(family_id, "🔥 7-Day Streak")
    if stats["total_xp"] >= 500:
        award_badge(family_id, "🌌 Eternal Scholar")

    return {"xp": quest["xp"], "sats": quest["sats"], "title": quest["title"]}

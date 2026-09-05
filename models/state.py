"""
models/state.py — AUBIEETERNAL Typed State Models
==================================================
Replaces loose st.session_state dictionaries with clean, validated,
self-documenting Pydantic objects.

Key models:
  FamilyMember    — individual family member state
  FamilyProfile   — full family state
  TruthEvent      — one truth log entry
  CoherenceState  — coherence with history + delta
  AppState        — top-level application state

Usage:
    from models.state import get_app_state, save_app_state
    state = get_app_state()
    state.award_xp(25)
    save_app_state(state)
"""

from __future__ import annotations
import json, os
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Optional, Literal, Any
from enum import Enum

# Pydantic v2 preferred; fall back gracefully
try:
    from pydantic import BaseModel, Field, computed_field, field_validator
    from pydantic import model_validator
    _PYDANTIC_V2 = True
except ImportError:
    try:
        from pydantic import BaseModel, Field, validator
        _PYDANTIC_V2 = False
    except ImportError:
        raise ImportError("pip install pydantic>=1.10 --break-system-packages")

import socket as _socket

def _data_dir() -> Path:
    try:
        _socket.gethostbyname("localhost")
        return Path("/mnt/main")
    except Exception:
        p = Path(os.path.expanduser("~/.aubieeternal/main"))
        p.mkdir(parents=True, exist_ok=True)
        return p

DATA_DIR       = _data_dir()
STATE_FILE     = DATA_DIR / "app_state.json"
LEGACY_STATE   = DATA_DIR / "session_state.json"


# ══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════════════════

class PolyvagalState(str, Enum):
    VENTRAL_VAGAL = "ventral_vagal"
    SYMPATHETIC   = "sympathetic"
    DORSAL_VAGAL  = "dorsal_vagal"

class RuneType(str, Enum):
    SHIELD        = "shield"
    TRUTH         = "truth"
    WONDER        = "wonder"
    FAMILY        = "family"
    CHILD_GENESIS = "child_genesis"
    ALIGNMENT     = "alignment"
    COSMOS        = "cosmos"
    DECISION      = "decision"

class BadgeTier(str, Enum):
    BRONZE  = "bronze"
    SILVER  = "silver"
    GOLD    = "gold"
    ETERNAL = "eternal"


# ══════════════════════════════════════════════════════════════════════════════
# CORE MODELS
# ══════════════════════════════════════════════════════════════════════════════

class FamilyMember(BaseModel):
    name:          str
    age:           int
    role:          Literal["kid", "parent", "grandparent"]
    coherence:     float = 1.000000
    xp:            int   = 0
    level:         int   = 1
    badges:        List[str] = Field(default_factory=list)
    runes_earned:  int   = 0
    lessons_done:  List[str] = Field(default_factory=list)
    polyvagal:     PolyvagalState = PolyvagalState.VENTRAL_VAGAL

    @property
    def display_name(self) -> str:
        return f"{self.name} ({self.role.title()})"

    @property
    def credits(self) -> int:
        return self.xp // 10

    def earn_xp(self, amount: int) -> None:
        self.xp  += amount
        self.level = 1 + (self.xp // 100)


class FamilyProfile(BaseModel):
    family_id:   str = "default_family"
    kid:         FamilyMember
    parent:      FamilyMember
    grandparent: Optional[FamilyMember] = None
    created_at:  datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_active: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create_default(cls) -> "FamilyProfile":
        return cls(
            family_id="default_family",
            kid=FamilyMember(name="Explorer", age=12, role="kid"),
            parent=FamilyMember(name="Parent", age=40, role="parent"),
            grandparent=FamilyMember(name="Elder", age=65, role="grandparent"),
        )

    def touch(self) -> None:
        self.last_active = datetime.now(timezone.utc)


class TruthEvent(BaseModel):
    timestamp:            datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type:           str
    detail:               str
    coherence_impact:     float = 0.0
    wonder_delta:         float = 0.0
    recommended_action:   Optional[str] = None
    tags:                 List[str] = Field(default_factory=list)
    xp_awarded:           int = 0
    family_id:            str = "default"

    def to_jsonl_line(self) -> str:
        return json.dumps({
            "timestamp":    self.timestamp.isoformat(),
            "event_type":   self.event_type,
            "detail":       self.detail[:500],
            "coherence":    self.coherence_impact,
            "wonder_delta": self.wonder_delta,
            "tags":         self.tags,
        })


class EarnedRune(BaseModel):
    id:          str
    rune_type:   RuneType
    content:     str
    coherence:   float
    block_height: Optional[int]   = None
    txid:         Optional[str]   = None
    created_at:   datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tags:         List[str] = Field(default_factory=list)
    lesson_key:   Optional[str]   = None


class Badge(BaseModel):
    name:         str
    tier:         BadgeTier
    description:  str
    earned_at:    datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    xp_required:  int = 0


class CoherenceState(BaseModel):
    current:      float       = 1.000000
    history:      List[float] = Field(default_factory=lambda: [1.000000])
    last_update:  datetime    = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def delta(self) -> float:
        if len(self.history) < 2:
            return 0.0
        return round(self.current - self.history[-2], 6)

    @property
    def trend(self) -> str:
        d = self.delta
        if d > 0.01:   return "↑ Rising"
        if d < -0.01:  return "↓ Falling"
        return "→ Stable"

    def update(self, new_value: float) -> None:
        clamped = max(0.0, min(1.0, new_value))
        self.history.append(clamped)
        self.current     = clamped
        self.last_update = datetime.now(timezone.utc)
        if len(self.history) > 100:
            self.history = self.history[-100:]


class DegreeRecord(BaseModel):
    degree_name:   str
    awarded_at:    datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    credits:       int
    coherence:     float
    capstone_note: str = ""
    bitcoin_anchor: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# TOP-LEVEL APP STATE
# ══════════════════════════════════════════════════════════════════════════════

class AppState(BaseModel):
    """
    Single source of truth for all AUBIEETERNAL state.
    Replaces ~40 scattered st.session_state keys with one validated object.
    """
    # Core identity
    family:           FamilyProfile
    coherence:        CoherenceState  = Field(default_factory=CoherenceState)

    # Progression
    xp:               int             = 0
    level:            int             = 1
    badges:           List[Badge]     = Field(default_factory=list)
    runes:            List[EarnedRune] = Field(default_factory=list)
    degrees:          List[DegreeRecord] = Field(default_factory=list)

    # Logs
    truth_log:        List[TruthEvent] = Field(default_factory=list)
    lessons_completed: List[str]       = Field(default_factory=list)

    # Swarm / AI settings
    active_provider:  str  = "Local Ollama (qwen3:32b)"
    swarm_mode:       str  = "balanced"
    defcon_level:     int  = 1
    wonder_index:     float = 1.0
    mets:             float = 0.0

    # Session metadata
    last_synthesis:   Optional[datetime] = None
    session_count:    int  = 0
    app_version:      str  = "69.0"

    # Runtime cache (not persisted)
    _runtime_cache:   Dict[str, Any] = Field(default_factory=dict, exclude=True)

    # ── Computed properties ────────────────────────────────────────────────────

    @property
    def total_runes(self) -> int:
        return len(self.runes)

    @property
    def credits(self) -> int:
        return self.xp // 10

    @property
    def coherence_trend(self) -> str:
        return self.coherence.trend

    @property
    def highest_degree(self) -> Optional[str]:
        DEGREES = [
            ("⚡ Eternal Founder (Sovereign Credential)", 250, 0.88),
            ("🎓 Master of Epistemic Rigor", 180, 0.82),
            ("🏛️ Truth Architect", 120, 0.75),
            ("📜 Sovereign Associate", 60, 0.68),
        ]
        coh  = self.coherence.current
        cred = self.credits
        for name, req_credits, req_coh in DEGREES:
            if cred >= req_credits and coh >= req_coh:
                return name
        return None

    # ── Helper methods ─────────────────────────────────────────────────────────

    def award_xp(self, amount: int, source: str = "lesson") -> None:
        """Award XP, update level, check for auto-badges."""
        self.xp   += amount
        self.level = 1 + (self.xp // 100)
        self.family.kid.earn_xp(amount)
        # Auto-badge milestones
        milestones = [
            (50,   "First Light",        BadgeTier.BRONZE,  "Earned first 50 XP"),
            (200,  "Rising Signal",      BadgeTier.SILVER,  "Earned 200 XP"),
            (500,  "Truth Seeker",       BadgeTier.GOLD,    "Earned 500 XP"),
            (1000, "Eternal Learner",    BadgeTier.ETERNAL, "Earned 1,000 XP"),
        ]
        earned_names = {b.name for b in self.badges}
        for threshold, name, tier, desc in milestones:
            if self.xp >= threshold and name not in earned_names:
                self.badges.append(Badge(name=name, tier=tier, description=desc, xp_required=threshold))

    def log_truth(self, event: TruthEvent) -> None:
        """Log a truth event and update coherence."""
        self.truth_log.append(event)
        if event.coherence_impact != 0:
            new_coh = self.coherence.current + event.coherence_impact
            self.coherence.update(new_coh)
        if event.xp_awarded > 0:
            self.award_xp(event.xp_awarded, source=event.event_type)
        # Trim to last 200 entries in memory
        if len(self.truth_log) > 200:
            self.truth_log = self.truth_log[-200:]

    def mark_lesson_complete(self, lesson_key: str, xp: int = 0,
                              coherence_boost: float = 0.0) -> None:
        """Mark a lesson completed at the AppState level."""
        if lesson_key not in self.lessons_completed:
            self.lessons_completed.append(lesson_key)
            self.family.kid.lessons_done.append(lesson_key)
            if xp > 0:      self.award_xp(xp)
            if coherence_boost > 0:
                self.coherence.update(self.coherence.current + coherence_boost)

    def add_rune(self, rune: EarnedRune) -> None:
        self.runes.append(rune)
        self.family.kid.runes_earned += 1

    def award_degree(self, name: str, capstone: str = "") -> DegreeRecord:
        rec = DegreeRecord(
            degree_name=name, credits=self.credits,
            coherence=self.coherence.current, capstone_note=capstone
        )
        self.degrees.append(rec)
        return rec

    # ── Persistence ────────────────────────────────────────────────────────────

    def save(self, path: Path = STATE_FILE) -> None:
        """Save AppState to JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(self.model_dump_json(indent=2) if _PYDANTIC_V2
                    else self.json(indent=2))

    @classmethod
    def load(cls, path: Path = STATE_FILE) -> "AppState":
        """Load AppState from JSON, fall back to migration from legacy format."""
        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)
                return (cls.model_validate(data) if _PYDANTIC_V2
                        else cls.parse_obj(data))
            except Exception as e:
                print(f"[state] Load failed ({e}), attempting migration...")

        # Try to migrate from legacy session state format
        if LEGACY_STATE.exists():
            try:
                return cls._migrate_from_legacy(LEGACY_STATE)
            except Exception:
                pass

        # Fresh start
        return cls(family=FamilyProfile.create_default())

    @classmethod
    def _migrate_from_legacy(cls, path: Path) -> "AppState":
        """
        One-time migration from the old st.session_state dict format.
        Called automatically when no app_state.json exists.
        """
        with open(path) as f:
            old = json.load(f)
        state = cls(family=FamilyProfile.create_default())
        # Map old keys
        if "xp" in old:            state.xp = int(old["xp"])
        if "level" in old:         state.level = int(old["level"])
        if "coherence" in old:     state.coherence.update(float(old["coherence"]))
        if "wonder_index" in old:  state.wonder_index = float(old["wonder_index"])
        if "mets" in old:          state.mets = float(old.get("mets", 0))
        if "defcon_level" in old:  state.defcon_level = int(old.get("defcon_level", 1))
        if "lessons_completed" in old:
            state.lessons_completed = list(old["lessons_completed"])
        if "badges" in old:
            for b in old["badges"]:
                if isinstance(b, str):
                    state.badges.append(Badge(
                        name=b, tier=BadgeTier.BRONZE,
                        description="Migrated badge", xp_required=0
                    ))
        print(f"[state] Migrated from legacy format — XP:{state.xp} coherence:{state.coherence.current:.4f}")
        return state

    def to_session_dict(self) -> dict:
        """
        Export as a flat dict compatible with the old st.session_state format.
        Use during transition period before full migration.
        """
        return {
            "xp":                   self.xp,
            "level":                self.level,
            "coherence":            self.coherence.current,
            "coherence_history":    self.coherence.history[-20:],
            "wonder_index":         self.wonder_index,
            "mets":                 self.mets,
            "defcon_level":         self.defcon_level,
            "total_runes":          self.total_runes,
            "lessons_completed":    self.lessons_completed,
            "active_provider":      self.active_provider,
            "swarm_mode":           self.swarm_mode,
            "badges":               [b.name for b in self.badges],
            "kid_name":             self.family.kid.name,
            "kid_coherence":        self.family.kid.coherence,
        }


# ══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS (drop-in for st.session_state patterns)
# ══════════════════════════════════════════════════════════════════════════════

def get_app_state() -> AppState:
    """
    Get or initialize the AppState from st.session_state.
    Drop-in replacement for scattered session_state access.
    
    Usage:
        state = get_app_state()
        state.award_xp(25)
        save_app_state(state)
    """
    try:
        import streamlit as st
        if "app_state" not in st.session_state:
            st.session_state.app_state = AppState.load()
        return st.session_state.app_state
    except ImportError:
        # Running outside Streamlit (tests, scripts)
        return AppState.load()


def save_app_state(state: AppState) -> None:
    """Save AppState to disk and st.session_state."""
    state.save()
    try:
        import streamlit as st
        st.session_state.app_state = state
        # Also sync legacy keys for backward compatibility during transition
        legacy = state.to_session_dict()
        for k, v in legacy.items():
            st.session_state[k] = v
    except ImportError:
        pass


def migrate_session_to_state() -> AppState:
    """
    One-time migration: reads existing st.session_state keys and converts
    them to a proper AppState object.
    Safe to call multiple times (idempotent).
    """
    try:
        import streamlit as st
        if "app_state" in st.session_state:
            return st.session_state.app_state
        state = AppState.load()
        # Pull any live session state values
        for key, attr in [
            ("xp", "xp"), ("level", "level"),
            ("wonder_index", "wonder_index"),
            ("mets", "mets"), ("defcon_level", "defcon_level"),
        ]:
            if key in st.session_state:
                setattr(state, attr, type(getattr(state, attr))(st.session_state[key]))
        if "coherence" in st.session_state:
            state.coherence.update(float(st.session_state["coherence"]))
        if "lessons_completed" in st.session_state:
            state.lessons_completed = list(st.session_state["lessons_completed"])
        save_app_state(state)
        return state
    except ImportError:
        return AppState.load()


if __name__ == "__main__":
    print("🧩 AUBIEETERNAL State Models Test")
    state = AppState(family=FamilyProfile.create_default())
    state.award_xp(150)
    print(f"XP: {state.xp} | Level: {state.level} | Credits: {state.credits}")
    state.coherence.update(0.85)
    print(f"Coherence: {state.coherence.current:.4f} | Trend: {state.coherence.trend}")
    state.log_truth(TruthEvent(
        event_type="lesson_complete", detail="Decision Theory L1",
        coherence_impact=0.005, xp_awarded=38,
        tags=["decision-theory", "lesson"]
    ))
    print(f"Truth log: {len(state.truth_log)} entries")
    print(f"Degree: {state.highest_degree or 'None yet'}")
    print(f"Badges: {[b.name for b in state.badges]}")
    state.save(Path("/tmp/test_app_state.json"))
    loaded = AppState.load(Path("/tmp/test_app_state.json"))
    assert loaded.xp == state.xp, "Persistence failed"
    print("✅ All models operational — War Eagle 🦅")

"""
degrees.py — AUBIEETERNAL Sovereign University: single source of truth
=====================================================================
EVERY module that touches degrees imports from here. Do not redefine
degree thresholds, credit math, or peer-review requirements anywhere else.

Replaces the four drifted copies that previously lived in:
  - family_hud.py        get_degree_eligibility()   (4 degrees)
  - state.py             highest_degree()            (4 degrees, reversed)
  - transcript_system.py DEGREES                     (7 degrees)
  - peer_review_system.py DEGREE_REVIEW_REQUIREMENTS (6 keys)

Also fixes the credit-formula split: credits are ALWAYS sum(xp) // 10.
"""

from typing import Dict, List, Optional

# Credits are computed ONE way, everywhere: total XP floored to tens.
CREDITS_PER_XP = 10


def credits_from_xp(total_xp: int) -> int:
    """Canonical credit math. Use this everywhere — never sum(xp//10)."""
    return int(total_xp) // CREDITS_PER_XP


# ── The canonical degree list ─────────────────────────────────────────────────
# Each degree carries every field any consumer needs:
#   id            stable machine key (used by peer review + alumni)
#   name          display name with emoji
#   emoji         standalone emoji (Registrar reads this)
#   credits       required credits (sum(xp)//10)
#   coherence     required rolling-average coherence
#   badge         short label for transcripts
#   tier          ordering rank for "highest degree" (higher = more advanced)
#   description   one line
#   special_rune  child-rune confirmations required (None if not gated)
#   peer_review   {min_reviewers, min_score} or None
#   active_req    human-readable real-world requirement, or None (not auto-gated)
DEGREES: List[Dict] = [
    {
        "id": "sovereign_associate", "name": "📜 Sovereign Associate", "emoji": "📜",
        "credits": 60, "coherence": 0.68, "badge": "Associate", "tier": 1,
        "description": "Demonstrates ability to deploy sovereign AI infrastructure.",
        "special_rune": None, "peer_review": None, "active_req": None,
    },
    {
        "id": "truth_architect", "name": "🏛️ Truth Architect", "emoji": "🏛️",
        "credits": 120, "coherence": 0.75, "badge": "Bachelor", "tier": 2,
        "description": "Produces original knowledge and serves community.",
        "special_rune": None,
        "peer_review": {"min_reviewers": 1, "min_score": 60}, "active_req": None,
    },
    {
        "id": "startos_operator", "name": "🖥️ StartOS Sovereign Operator", "emoji": "🖥️",
        "credits": 200, "coherence": 0.82, "badge": "Infrastructure", "tier": 3,
        "description": "Runs sovereign infrastructure and deploys it for community.",
        "special_rune": None,
        "peer_review": {"min_reviewers": 1, "min_score": 60},
        "active_req": "Node running >= 90 days",
    },
    {
        "id": "master_epistemic_rigor", "name": "🎓 Master of Epistemic Rigor", "emoji": "🎓",
        "credits": 180, "coherence": 0.82, "badge": "Master", "tier": 4,
        "description": "Conducts rigorous pre-registered research.",
        "special_rune": None,
        "peer_review": {"min_reviewers": 2, "min_score": 70}, "active_req": None,
    },
    {
        "id": "eternal_founder", "name": "⚡ Eternal Founder (Sovereign Credential)", "emoji": "⚡",
        "credits": 250, "coherence": 0.88, "badge": "Sovereign Credential", "tier": 5,
        "description": "Builds infrastructure others use. Dynasty on-chain.",
        "special_rune": 256,
        "peer_review": {"min_reviewers": 2, "min_score": 75}, "active_req": None,
    },
    {
        "id": "sovereign_ai_researcher", "name": "🤖 Sovereign AI Researcher", "emoji": "🤖",
        "credits": 300, "coherence": 0.90, "badge": "AI Research", "tier": 6,
        "description": "Contributes to AI alignment with mathematical foundations.",
        "special_rune": None,
        "peer_review": {"min_reviewers": 2, "min_score": 80}, "active_req": None,
    },
    {
        "id": "epistemic_civilization_builder", "name": "🌍 Epistemic Civilization Builder", "emoji": "🌍",
        "credits": 300, "coherence": 0.90, "badge": "Civilization", "tier": 6,
        "description": "Deploys knowledge infrastructure for communities at scale.",
        "special_rune": None,
        "peer_review": {"min_reviewers": 2, "min_score": 75},
        "active_req": ">= 3 community deployments documented",
    },
]

# Fast lookups
_BY_ID = {d["id"]: d for d in DEGREES}
_BY_NAME = {d["name"]: d for d in DEGREES}


def by_id(degree_id: str) -> Optional[Dict]:
    return _BY_ID.get(degree_id)


def by_name(name: str) -> Optional[Dict]:
    return _BY_NAME.get(name)


def review_requirements(degree_id: str) -> Dict:
    """What peer_review_system.py used to hold in DEGREE_REVIEW_REQUIREMENTS."""
    d = _BY_ID.get(degree_id)
    return (d.get("peer_review") or {}) if d else {}


# Back-compat shim so peer_review_system can keep its old constant name.
DEGREE_REVIEW_REQUIREMENTS: Dict[str, Dict] = {
    d["id"]: d["peer_review"] for d in DEGREES if d.get("peer_review")
}


def degrees_earned(
    credits: int,
    coherence: float,
    child_rune_confirmations: int = 0,
    deployments: int = 0,
    node_days: int = 0,
) -> List[Dict]:
    """
    Every degree the student currently qualifies for.

    active_req gates (node uptime, deployments) are enforced ONLY when the
    caller passes the relevant data; otherwise they don't block, so the
    Registrar can still show progress toward them.
    """
    earned = []
    for d in DEGREES:
        if credits < d["credits"]:
            continue
        if coherence < d["coherence"]:
            continue
        if d.get("special_rune") and child_rune_confirmations < d["special_rune"]:
            continue
        if d["id"] == "epistemic_civilization_builder" and deployments and deployments < 3:
            continue
        if d["id"] == "startos_operator" and node_days and node_days < 90:
            continue
        earned.append(d)
    return earned


def highest_degree(
    credits: int,
    coherence: float,
    child_rune_confirmations: int = 0,
    **kw,
) -> Optional[Dict]:
    """
    Single 'headline' degree for display. Note: tiers 6 (AI Researcher and
    Civilization Builder) are parallel tracks, so prefer degrees_earned() when
    you want the full set. This returns the most advanced by (tier, credits).
    """
    earned = degrees_earned(credits, coherence, child_rune_confirmations, **kw)
    if not earned:
        return None
    return max(earned, key=lambda d: (d["tier"], d["credits"]))


def eligibility_report(
    total_xp: int,
    coherence: float,
    lessons_done: int,
    child_rune_confirmations: int = 0,
    **kw,
) -> Dict:
    """Drop-in replacement for family_hud.get_degree_eligibility()'s return."""
    credits = credits_from_xp(total_xp)
    return {
        "credits": credits,
        "coherence": round(coherence, 4),
        "lessons_done": lessons_done,
        "highest_degree": highest_degree(credits, coherence, child_rune_confirmations, **kw),
        "all_degrees": DEGREES,
        "child_rune_pct": min(100, child_rune_confirmations / 2.56),
    }

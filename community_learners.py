"""
community_learners.py — lightweight identity for walk-up Community Mode
users (the anonymous, no-real-signup path for orphanages/libraries/
community centers - see app.py's "Community Mode" tab).

Found 2026-08-25: Community Mode collected a name, age range, and mood
check-in, and had an "I finished this lesson! +XP" button - but NONE of it
was ever actually saved anywhere. Every field lived only in Streamlit's
st.session_state (gone the moment the browser tab closes), and the XP
button just showed balloons + a success message claiming XP was earned
with zero real persistence - the same category of false claim as the
"encrypted" messaging bug fixed earlier tonight.

Real continuity for a walk-up user needs SOME identity, but this is
explicitly the anonymous path (including for kids, per its own "Under 8"
age option) - collecting email or any real personal info here is a real
privacy consideration, not just a technical one. This module gives a
lightweight name + PIN identity instead: no personal info at all, safe
for a child to use unsupervised, works fully offline.

The actual XP/lesson-completion persistence reuses family_profiles.py's
load_family_stats()/save_family_stats() directly - those already work
with any arbitrary string as family_id (confirmed: not gated by
FAMILY_REGISTRY at all), so a community learner's derived ID doubles as
a real family_id and gets the exact same durable, tested storage every
other part of AUBIEETERNAL already uses. This module only needs to solve
the one new piece: looking a returning learner back up from a name+PIN
they remember, with no account system, no login screen, no email.
"""

import hashlib
import json
import secrets
from datetime import datetime
from pathlib import Path

try:
    from family_profiles import DATA_DIR
except Exception:
    DATA_DIR = Path("/mnt/main")

LEARNERS_PATH = DATA_DIR / "community_learners.json"


def _hash_pin(pin: str, salt_hex: str | None = None) -> tuple[str, str]:
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 100_000)
    return salt.hex(), digest.hex()


def _verify_pin(pin: str, salt_hex: str, hash_hex: str) -> bool:
    _, computed = _hash_pin(pin, salt_hex)
    return secrets.compare_digest(computed, hash_hex)


def _load() -> dict:
    if LEARNERS_PATH.exists():
        try:
            return json.loads(LEARNERS_PATH.read_text())
        except Exception:
            pass
    return {}


def _save(learners: dict) -> None:
    LEARNERS_PATH.write_text(json.dumps(learners, indent=2))


def resume_or_create(name: str, pin: str, age_range: str = "") -> dict:
    """The one real entry point Community Mode needs: given a name + PIN
    someone just typed, either finds their existing record (matching name,
    verified PIN) or creates a new one. Returns
    {learner_id, display_name, age_range, is_new} - learner_id is what
    the caller should pass to family_profiles.load_family_stats()/
    save_family_stats() for all real progress tracking.

    Deliberately forgiving, not strict auth: a name+PIN combo that doesn't
    match any existing record just becomes a new learner (e.g. a mistyped
    PIN doesn't lock anyone out, it just starts fresh under that name+PIN
    pair) - appropriate for a low-stakes, no-personal-info walk-up
    context, not a real security boundary."""
    name = name.strip()
    pin  = pin.strip()
    if not name or not pin:
        raise ValueError("Both a name and a PIN are required.")

    learners = _load()
    name_lower = name.lower()

    for learner_id, record in learners.items():
        if record.get("name_lower") == name_lower:
            pin_hash = record.get("pin_hash", {})
            if pin_hash and _verify_pin(pin, pin_hash.get("salt", ""), pin_hash.get("hash", "")):
                record["last_seen"] = datetime.now().isoformat()
                if age_range:
                    record["age_range"] = age_range
                _save(learners)
                return {
                    "learner_id": learner_id, "display_name": record["display_name"],
                    "age_range": record.get("age_range", ""), "is_new": False,
                }

    learner_id = "cm_" + secrets.token_hex(6)
    salt_hex, hash_hex = _hash_pin(pin)
    learners[learner_id] = {
        "display_name": name,
        "name_lower":   name_lower,
        "pin_hash":     {"salt": salt_hex, "hash": hash_hex},
        "age_range":    age_range,
        "created_at":   datetime.now().isoformat(),
        "last_seen":    datetime.now().isoformat(),
    }
    _save(learners)
    return {"learner_id": learner_id, "display_name": name, "age_range": age_range, "is_new": True}

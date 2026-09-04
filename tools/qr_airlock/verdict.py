"""
verdict.py — combine heuristics + public/household flags + allow-list
into one of: unknown | suspicious | confirmed_bad | allowed | withdrawn

Default is always 'unknown'. Never returns a bare "safe" — absence of
signals is not proof of safety (day-zero phishing pages have zero
detections everywhere).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional
from urllib.parse import urlparse

from .flags import find_public_flag, is_allowed
from .hash_payload import payload_sha256
from .heuristics import Signals, analyze_payload

CONFIRMED_SIGHTING_THRESHOLD = 3  # N independent household sightings -> treat as confirmed


def _try_explain(explain_fn, payload: str, signals: Signals) -> str:
    """Call the optional explanation hook defensively. A missing hook, a
    raised exception, or an empty/blank return all mean 'no model
    explanation' -> the caller uses the canned DEFAULT_EXPLANATIONS text.
    The airlock must never fail or go silent just because the local model
    is down."""
    if not explain_fn:
        return ""
    try:
        return (explain_fn(payload, signals) or "").strip()
    except Exception:
        return ""


@dataclass
class Verdict:
    verdict: str                 # unknown | suspicious | confirmed_bad | allowed | withdrawn
    payload: str
    payload_sha256: str
    registered_domain: Optional[str]
    signals: List[str] = field(default_factory=list)
    signal_notes: List[str] = field(default_factory=list)
    source: str = "heuristic"    # heuristic | public_flag | allowlist
    explanation: str = ""
    matched_flag: Optional[Dict] = None

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "payload": self.payload,
            "payload_sha256": self.payload_sha256,
            "registered_domain": self.registered_domain,
            "signals": self.signals,
            "signal_notes": self.signal_notes,
            "source": self.source,
            "explanation": self.explanation,
            "matched_flag": self.matched_flag,
        }


def _registered_domain(payload: str) -> Optional[str]:
    if not payload.lower().startswith(("http://", "https://")):
        return None
    try:
        host = urlparse(payload).netloc.split("@")[-1].split(":")[0].lower()
        return host or None
    except Exception:
        return None


DEFAULT_EXPLANATIONS = {
    "allowed": "This link is on your household's allow list for now — you've approved it before.",
    "confirmed_bad": "Multiple independent sources have flagged this exact code as bad. Don't tap, don't log in, don't pay.",
    "suspicious": "This one has some warning signs. Read the full URL below before you do anything with it.",
    "withdrawn": "This was flagged before but the flag was withdrawn (likely a false positive). Still worth reading the URL yourself.",
    "unknown": "Nothing on record either way. Read the URL below — if it wants a login or payment, stop and verify another way.",
}


def evaluate(
    payload: str,
    *,
    claimed_as: str = "",
    explain_fn: Optional[Callable[[str, Signals], str]] = None,
) -> Verdict:
    """
    explain_fn, if given, is a callable(payload, signals) -> str that can
    route through the existing local Qwen /converse or askqwen tool for a
    plain-language explanation. If omitted, a canned explanation is used —
    the airlock must work even if the rig/model is unavailable.
    """
    phash = payload_sha256(payload)
    domain = _registered_domain(payload)

    # 1. Allow-list wins outright.
    if is_allowed(domain=domain, payload_hash=phash):
        v = Verdict(
            verdict="allowed",
            payload=payload,
            payload_sha256=phash,
            registered_domain=domain,
            source="allowlist",
        )
        v.explanation = DEFAULT_EXPLANATIONS["allowed"]
        return v

    # 2. Public/household flag match.
    flag = find_public_flag(phash)
    if flag:
        if flag.status == "confirmed" or flag.sighting_count >= CONFIRMED_SIGHTING_THRESHOLD:
            verdict_str = "confirmed_bad"
        elif flag.status == "withdrawn":
            verdict_str = "withdrawn"
        else:
            verdict_str = flag.verdict or "suspicious"
        v = Verdict(
            verdict=verdict_str,
            payload=payload,
            payload_sha256=phash,
            registered_domain=domain,
            signals=flag.signals,
            source="public_flag",
            matched_flag=flag.raw,
        )
        canned = DEFAULT_EXPLANATIONS.get(verdict_str, DEFAULT_EXPLANATIONS["unknown"])
        v.explanation = _try_explain(explain_fn, payload, Signals(codes=flag.signals)) or canned
        return v

    # 3. Fall back to offline heuristics.
    sig = analyze_payload(payload, claimed_as=claimed_as)
    verdict_str = "suspicious" if sig.codes else "unknown"
    v = Verdict(
        verdict=verdict_str,
        payload=payload,
        payload_sha256=phash,
        registered_domain=domain,
        signals=sig.codes,
        signal_notes=sig.notes,
        source="heuristic",
    )
    explained = _try_explain(explain_fn, payload, sig)
    if explained:
        v.explanation = explained
    elif sig.notes:
        v.explanation = " ".join(sig.notes)
    else:
        v.explanation = DEFAULT_EXPLANATIONS[verdict_str]
    return v

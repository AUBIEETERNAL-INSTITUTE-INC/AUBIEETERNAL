"""
airlock.py — single entry point: payload string OR image -> verdict.

This is the function assistant_server.py's /qr_check route (and any
CLI/kiosk caller) should import. It never opens/fetches the URL itself.

    from qr_airlock.airlock import check_qr

    result = check_qr(payload="https://example.com/menu")
    # or
    result = check_qr(image_b64="...")
"""
from __future__ import annotations

from typing import Callable, Optional

from .decode import DecodeError, decode_base64_image, normalize_payload
from .hash_payload import payload_sha256
from .heuristics import Signals
from .log import log_check
from .verdict import evaluate
from .wifi import is_wifi_payload, parse_wifi_payload


def check_qr(
    *,
    payload: Optional[str] = None,
    image_b64: Optional[str] = None,
    claimed_as: str = "",
    who: str = "unknown",
    source: str = "device",
    explain_fn: Optional[Callable[[str, Signals], str]] = None,
) -> dict:
    """
    Exactly one of payload / image_b64 should be given. Returns a verdict
    dict (see verdict.Verdict.to_dict) plus a household log entry is
    written automatically (household-local only, never uploaded).
    """
    if not payload and not image_b64:
        return {"error": "Provide either 'payload' or 'image_b64'."}

    if image_b64:
        try:
            decoded = decode_base64_image(image_b64)
        except DecodeError as e:
            return {"error": str(e), "verdict": "unknown"}
        payload = decoded.payload

    payload = normalize_payload(payload)

    # WIFI: payloads get their own display-only path — never the safe/unsafe
    # verdict system, never a model call. Decode stays pyzbar-primary (already
    # done above); this is a fast local parse only.
    if is_wifi_payload(payload):
        wifi = parse_wifi_payload(payload)
        wifi["payload"] = payload
        wifi["payload_sha256"] = payload_sha256(payload)
        log_check(
            payload_hash=wifi["payload_sha256"],
            payload_preview=payload,
            final_url=None,
            verdict="wifi",
            who=who,
            approved=False,
            source=source,
        )
        return wifi

    result = evaluate(payload, claimed_as=claimed_as, explain_fn=explain_fn)

    log_check(
        payload_hash=result.payload_sha256,
        payload_preview=payload,
        final_url=payload if payload.lower().startswith(("http://", "https://")) else None,
        verdict=result.verdict,
        who=who,
        approved=False,
        source=source,
    )

    return result.to_dict()

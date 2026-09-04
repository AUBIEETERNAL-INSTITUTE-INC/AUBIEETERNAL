"""
api.py — FastAPI router for /qr_check and /qr_allow / /qr_share.

Integration into assistant_server.py:

    from qr_airlock.api import router as qr_router
    app.include_router(qr_router)

Kept as a separate router (not pasted directly into assistant_server.py)
so the airlock stays a self-contained, independently testable module —
per the handoff: "add a tool the tutor can call rather than a separate
consumer brand."
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from .airlock import check_qr
from .flags import add_to_allowlist
from .hash_payload import payload_sha256
from .share import share_flag
from .verdict import evaluate

router = APIRouter(prefix="/qr", tags=["qr_airlock"])


class QRCheckRequest(BaseModel):
    payload: Optional[str] = None
    image_b64: Optional[str] = None
    claimed_as: str = ""
    who: str = "unknown"
    source: str = "device"


class QRAllowRequest(BaseModel):
    payload: str
    domain: Optional[str] = None


class QRShareRequest(BaseModel):
    payload: str
    claimed_as: str = ""
    venue_name: Optional[str] = None
    venue_city: Optional[str] = None


# The safety-relevant part of a check — the verdict — is returned instantly by
# verdict.py regardless of the model. This explanation is a nicety on top, so it
# runs on the small fast model with a short timeout; on timeout / model-busy /
# Ollama-down it returns "" and verdict.py falls back to DEFAULT_EXPLANATIONS.
_EXPLAIN_MODEL = "qwen2.5:7b"
_EXPLAIN_TIMEOUT_S = 15


def _explain_via_qwen(payload: str, signals) -> str:
    """
    Plain-language explanation via the local Ollama server (the same
    assistant_server.query_ollama helper /converse uses; lazy import so this
    module still imports cleanly on its own and there's no cycle with
    assistant_server importing this router at startup). Runs on the small
    qwen2.5:7b model with a 15s timeout so it never stalls a kiosk scan. Any
    failure — timeout, model busy, Ollama down, import error — returns "" and
    the caller falls back to the canned explanation in verdict.py.
    """
    try:
        from assistant_server import query_ollama

        codes = ", ".join(getattr(signals, "codes", []) or []) or "none"
        prompt = (
            "A family member scanned a QR code. In 2-3 short sentences, plain "
            "language, no jargon, no markdown, explain why it might be risky. "
            "Do NOT tell them to open it.\n"
            f"Decoded payload: {payload}\n"
            f"Automated warning signs: {codes}."
        )
        return query_ollama(
            prompt,
            _EXPLAIN_MODEL,
            system_override=(
                "You are a careful security explainer for non-technical "
                "families. Be brief and calm. Never encourage opening the link."
            ),
            timeout=_EXPLAIN_TIMEOUT_S,
        ).strip()
    except Exception:
        return ""  # falls back to canned explanation in verdict.py


@router.post("/check")
def qr_check(req: QRCheckRequest):
    return check_qr(
        payload=req.payload,
        image_b64=req.image_b64,
        claimed_as=req.claimed_as,
        who=req.who,
        source=req.source,
        explain_fn=_explain_via_qwen,
    )


@router.post("/allow")
def qr_allow(req: QRAllowRequest):
    """'Allow this month' action — explicit household approval only."""
    phash = payload_sha256(req.payload)
    add_to_allowlist(domain=req.domain, payload_hash=phash)
    return {"status": "allowed", "payload_sha256": phash}


@router.post("/share")
def qr_share(req: QRShareRequest):
    """
    'Share flag' action. Writes ONLY to the local pending-share queue —
    does not push to git or the public site. A human still has to run
    the publish step (see README: Publishing a flag).
    """
    v = evaluate(req.payload, claimed_as=req.claimed_as)
    record = share_flag(
        v,
        claimed_as=req.claimed_as,
        venue_name=req.venue_name,
        venue_city=req.venue_city,
    )
    return {"status": "queued", "flag": record}

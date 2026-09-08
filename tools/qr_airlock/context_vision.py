"""
context_vision.py — optional second pass: read the *physical context* a QR
code is printed on and judge whether it looks like a legitimate, low-risk
source.

This never changes the airlock verdict and never clears a flag. It only
adds a plain-language "context read" alongside the existing heuristic
verdict, and only when verdict == "suspicious" (heuristics flagged a
warning sign) — the case where a human glancing at the same photo would
pick up on cues the payload string alone can't carry, e.g. a raw
invoice-number payload (non_url_payload -> "suspicious") sitting on an
obvious retail receipt with "FACTURA NRO", warranty terms and a date
range. "unknown" (a first-seen URL with no signals) is excluded so the
common kiosk scan isn't slowed down.

Design mirrors verdict._try_explain / api._explain_via_qwen exactly:

  * lazy import of assistant_server.query_ollama (no import cycle, module
    still imports standalone),
  * runs a local Ollama model only — no cloud vision API,
  * any failure at all (model not pulled, Ollama down, timeout, malformed
    output) returns None, and the caller shows the plain heuristic verdict
    exactly as it does today. No new failure mode.

The image and anything derived from it stay in the /qr/check response only:
this result is never written to the household log and never included in a
shared flag (QR_FLAG_SPEC: "no image, no scanner identity").
"""
from __future__ import annotations

from typing import Optional

# Vision model — qwen2.5vl is the same VISION_MODEL assistant_server uses for
# /greet object detection and the phone_ui scene description. If it isn't
# pulled the query_ollama call raises and we return None.
CONTEXT_MODEL = "qwen2.5vl:7b"
# Timeout for the vision call. Measured on the rig's RTX 3060: ~1s when the
# model is already resident (it usually is - /greet and phone_ui scene
# description keep qwen2.5vl warm), ~30s cold (6 GB load + first inference).
# 40s gives the cold case headroom; on timeout the caller just gets no
# context read, same as if the model weren't installed. This whole path
# only runs for a "suspicious" verdict (not "unknown", not a clean scan),
# so the common kiosk scan never waits on it. If the combined /qr/check
# latency on a suspicious scan (this + _explain_via_qwen) is ever felt on
# the kiosk, the fix is a separate /qr/context follow-up call the UI makes
# after rendering the verdict - see PATCH_NOTES - not a bigger timeout here.
CONTEXT_TIMEOUT_S = 40

_SYSTEM = (
    "You inspect a photo of a QR code and its immediate physical "
    "surroundings for a non-technical family. You do NOT decide if the code "
    "is safe or unsafe - another system does that. Your only job is to "
    "describe what the code is physically printed on and whether that "
    "setting is consistent with an everyday, low-risk source (a shop "
    "receipt, product packaging, an appliance label, a printed event "
    "ticket, a restaurant table card) or whether it looks like nothing is "
    "visible around it, or like the code was stuck on, taped over, or "
    "printed on a slip that doesn't match its surroundings. Be calm and "
    "factual. Never tell anyone to open or scan the link."
)

_PROMPT = (
    "Look at the QR code in this photo and everything printed around it. "
    "Answer with exactly these four lines and nothing else:\n"
    "SURFACE: <what the code is physically printed on, one short phrase>\n"
    "VISIBLE_TEXT: <the most relevant words printed near the code; if they "
    "are not in English, give them in the original language then an English "
    "translation in parentheses; write 'none legible' if you cannot read "
    "any>\n"
    "CONSISTENCY: <one word - consistent | unclear | inconsistent>\n"
    "READ: <one plain sentence a family member would understand, e.g. "
    "\"This looks printed on a standard retail receipt with visible "
    "invoice and warranty text - consistent with a normal receipt QR, not "
    "a sign of tampering.\">"
)

# Map the model's CONSISTENCY word to a stable enum the UI/API can rely on.
_CONSISTENCY_MAP = {
    "consistent": "consistent",
    "inconsistent": "inconsistent",
    "unclear": "unclear",
    "": "unclear",
}


def _parse(raw: str) -> Optional[dict]:
    """Parse the four-line reply defensively. If the model ignored the
    format entirely, fall back to handing back the whole thing as the
    'read' text with an 'unclear' consistency - still useful, never a
    crash."""
    raw = (raw or "").strip()
    if not raw:
        return None

    fields: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip().lower().replace(" ", "_")
        if key in ("surface", "visible_text", "consistency", "read"):
            fields[key] = val.strip()

    consistency_word = fields.get("consistency", "").strip().lower()
    # tolerate "CONSISTENCY: consistent (receipt)" etc.
    consistency_word = consistency_word.split()[0] if consistency_word else ""
    consistency = _CONSISTENCY_MAP.get(consistency_word, "unclear")

    read_text = fields.get("read", "").strip()
    if not read_text:
        # Model didn't follow the format - use the whole reply as the read,
        # but never claim more certainty than "unclear".
        read_text = raw
        consistency = "unclear"

    return {
        "available": True,
        "model": CONTEXT_MODEL,
        "surface": fields.get("surface", "").strip(),
        "visible_text": fields.get("visible_text", "").strip(),
        "consistency": consistency,
        "read": read_text,
        "note": (
            "Extra context only - this does not change the safety verdict "
            "above. Read the link yourself before acting on it."
        ),
    }


def read_context(
    image_b64: str,
    *,
    model: str = CONTEXT_MODEL,
    timeout: int = CONTEXT_TIMEOUT_S,
) -> Optional[dict]:
    """
    image_b64: the photo the QR was scanned from (or a separate wider shot
    of its surroundings), base64, data-URI prefix tolerated.

    Returns a dict (see _parse) or None. None means "no context read
    available" - the caller must behave exactly as it did before this
    feature existed.
    """
    if not image_b64:
        return None
    if "," in image_b64 and image_b64.strip().lower().startswith("data:"):
        image_b64 = image_b64.split(",", 1)[1]

    try:
        # Lazy: assistant_server imports this module's package at startup via
        # the qr router; importing it here avoids the cycle and keeps this
        # module importable on its own (cli.py, tests).
        from assistant_server import query_ollama

        raw = query_ollama(
            _PROMPT,
            model,
            image_b64=image_b64,
            system_override=_SYSTEM,
            timeout=timeout,
        )
        return _parse(raw)
    except Exception:
        return None

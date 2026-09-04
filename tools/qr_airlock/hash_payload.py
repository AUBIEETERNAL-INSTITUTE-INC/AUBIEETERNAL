"""
hash_payload.py — sha256 of the exact decoded payload string.

Per QR_FLAG_SPEC: hash the payload STRING (UTF-8, no extra whitespace),
never the image bytes. This lets independent households/tools converge
on the same hash for the same lie, without sharing images.
"""
from __future__ import annotations

import hashlib

from .decode import normalize_payload


def payload_sha256(payload: str) -> str:
    normalized = normalize_payload(payload)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

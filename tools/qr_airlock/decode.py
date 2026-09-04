"""
decode.py — QR airlock: image/bytes -> raw payload string.

Never opens, fetches, or navigates to anything found inside the QR.
Pure decode only.
"""
from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np


class DecodeError(Exception):
    pass


@dataclass
class DecodeResult:
    payload: str          # raw decoded text, exactly as read (no trimming beyond spec normalization)
    points: Optional[list] # QR finder-pattern polygon, for UI overlay (list of [x, y])


def _cv2_image_from_bytes(image_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise DecodeError("Could not decode image bytes (unsupported format or corrupt data).")
    return img


def decode_image_bytes(image_bytes: bytes) -> DecodeResult:
    """Decode the first QR code found in raw image bytes (PNG/JPEG/etc)."""
    img = _cv2_image_from_bytes(image_bytes)
    detector = cv2.QRCodeDetector()

    # Try multi-detect first (handles multiple codes / better robustness in newer opencv)
    try:
        ok, decoded_texts, points, _ = detector.detectAndDecodeMulti(img)
        if ok and decoded_texts:
            for text in decoded_texts:
                if text:
                    pts = points[0].tolist() if points is not None and len(points) else None
                    return DecodeResult(payload=text, points=pts)
    except cv2.error:
        pass

    # Fallback to single-detect
    text, pts, _ = detector.detectAndDecode(img)
    if not text:
        raise DecodeError("No QR code detected in image.")
    return DecodeResult(payload=text, points=pts.tolist() if pts is not None else None)


def decode_base64_image(image_b64: str) -> DecodeResult:
    """Decode a base64-encoded image (data URI prefix optional)."""
    if "," in image_b64 and image_b64.strip().lower().startswith("data:"):
        image_b64 = image_b64.split(",", 1)[1]
    try:
        raw = base64.b64decode(image_b64, validate=False)
    except Exception as e:
        raise DecodeError(f"Invalid base64 image data: {e}")
    return decode_image_bytes(raw)


def normalize_payload(payload: str) -> str:
    """
    Canonical form used for hashing/lookup, per QR_FLAG_SPEC:
    'exact decoded QR text (UTF-8, no extra whitespace)'.
    We strip only leading/trailing whitespace — we do NOT alter internal
    content, since that's the literal string an attacker chose.
    """
    return payload.strip()

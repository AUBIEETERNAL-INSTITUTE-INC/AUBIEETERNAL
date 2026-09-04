"""
decode.py — QR airlock: image/bytes -> raw payload string.

Never opens, fetches, or navigates to anything found inside the QR.
Pure decode only.

Decoder strategy: pyzbar (libzbar) is tried first — it's meaningfully
more robust than cv2.QRCodeDetector on real-world photos (angled shots,
glare on laminated stickers, uneven restaurant lighting). cv2 is kept as
a fallback since it needs no system library beyond opencv itself, so the
airlock still works if libzbar isn't installed on a given box.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

try:
    from pyzbar.pyzbar import decode as _zbar_decode
    _HAVE_ZBAR = True
except (ImportError, OSError):
    # OSError covers "libzbar.so not found" on boxes missing the system package
    _HAVE_ZBAR = False


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


def _preprocess_variants(img: np.ndarray) -> list:
    """
    A few cheap, fast variants to try decoding against, aimed at the real
    failure modes: low contrast / glare / uneven light on a printed sticker.
    Order matters — cheapest and most-likely-to-help first.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    variants = [gray]

    # CLAHE local-contrast boost — helps with uneven lighting/glare.
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    variants.append(clahe.apply(gray))

    # Adaptive threshold — helps with low-contrast prints/shadows.
    variants.append(cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 5
    ))

    return variants


def _try_pyzbar(img: np.ndarray) -> Optional[DecodeResult]:
    if not _HAVE_ZBAR:
        return None
    for variant in _preprocess_variants(img):
        try:
            results = _zbar_decode(variant)
        except Exception:
            continue
        for r in results:
            if r.type == "QRCODE" and r.data:
                text = r.data.decode("utf-8", errors="replace")
                pts = [[p.x, p.y] for p in r.polygon] if r.polygon else None
                return DecodeResult(payload=text, points=pts)
    return None


def _try_cv2(img: np.ndarray) -> Optional[DecodeResult]:
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

    # Fallback to single-detect, including preprocessed variants.
    for variant in [img] + _preprocess_variants(img):
        text, pts, _ = detector.detectAndDecode(variant)
        if text:
            return DecodeResult(payload=text, points=pts.tolist() if pts is not None else None)
    return None


def decode_image_bytes(image_bytes: bytes) -> DecodeResult:
    """Decode the first QR code found in raw image bytes (PNG/JPEG/etc)."""
    img = _cv2_image_from_bytes(image_bytes)

    result = _try_pyzbar(img)
    if result is None:
        result = _try_cv2(img)
    if result is None:
        raise DecodeError("No QR code detected in image.")
    return result


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

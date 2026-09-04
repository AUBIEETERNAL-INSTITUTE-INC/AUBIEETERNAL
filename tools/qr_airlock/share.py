"""
share.py — build a "Share Flag" record per QR_FLAG_SPEC v0.1.

This ONLY ever writes to the local pending-share queue (flags.py:
PENDING_SHARE_PATH). Actually publishing to the public feed
(public/flags/qr-flags.json on aubieeternal-institute.org) is a
separate, explicit human step — git commit/push, or a maintainer
merging the household's PR. No auto-publish, ever.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .flags import queue_flag_for_sharing
from .verdict import Verdict


def build_flag_record(
    v: Verdict,
    *,
    status: str = "sighting",
    claimed_as: str = "",
    venue_name: Optional[str] = None,
    venue_city: Optional[str] = None,
    publisher: str = "household",
) -> Dict:
    if v.payload.lower().startswith(("http://", "https://")):
        payload_kind = "url"
        final_url = v.payload
    else:
        payload_kind = "text"
        final_url = None

    record = {
        "spec": "aubieeternal-qr-flag/v0.1",
        "id": f"flag_{datetime.now(timezone.utc).strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}",
        "status": status,
        "verdict": v.verdict if v.verdict != "allowed" else "suspicious",  # you don't share an "allowed" as a flag
        "payload_sha256": v.payload_sha256,
        "payload_kind": payload_kind,
        "final_url": final_url,
        "registered_domain": v.registered_domain,
        "claimed_as": claimed_as or None,
        "signals": v.signals,
        "venue": {
            "name": venue_name,
            "city": venue_city,
            "note": "table sticker overlay — do not treat venue as the attacker" if venue_name else None,
        } if venue_name else None,
        "first_seen_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sighting_count": 1,
        "publisher": publisher,
        "publisher_key_id": None,
        "signature": None,
        "privacy": "no image, no scanner identity, no GPS",
    }
    return record


def share_flag(
    v: Verdict,
    *,
    claimed_as: str = "",
    venue_name: Optional[str] = None,
    venue_city: Optional[str] = None,
    publisher: str = "household",
) -> Dict:
    """Explicit user action: 'Share flag' button. Queues locally only."""
    record = build_flag_record(
        v,
        claimed_as=claimed_as,
        venue_name=venue_name,
        venue_city=venue_city,
        publisher=publisher,
    )
    queue_flag_for_sharing(record)
    return record

"""
log.py — private household JSONL log.

time, payload hash, final URL, verdict, who approved. Never uploaded,
never synced to the swarm, never included in the public flag feed.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from .flags import HOUSEHOLD_LOG_PATH, ensure_household_dir


def log_check(
    *,
    payload_hash: str,
    payload_preview: str,
    final_url: Optional[str],
    verdict: str,
    who: str = "unknown",
    approved: bool = False,
    source: str = "device",
) -> dict:
    ensure_household_dir()
    entry = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "payload_sha256": payload_hash,
        "payload_preview": payload_preview[:120],
        "final_url": final_url,
        "verdict": verdict,
        "who": who,
        "approved": approved,
        "source": source,  # "device" | "kiosk" | "converse_tool"
    }
    with HOUSEHOLD_LOG_PATH.open("a") as fh:
        fh.write(json.dumps(entry) + "\n")
    return entry

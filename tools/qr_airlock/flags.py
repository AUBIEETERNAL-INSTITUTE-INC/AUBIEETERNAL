"""
flags.py — load/search the local family cache and the public flag list.

Two stores, both plain JSON/JSONL, both local files:
  - PUBLIC_FLAGS_PATH: the shareable feed (public/flags/qr-flags.json in the
    institute repo, or a cached copy pulled from the site). No PII.
  - Household files under HOUSEHOLD_DIR: allow-list + prior verdicts.
    Never uploaded, never synced to the swarm.

This module does no network I/O. Pulling a fresh copy of the public feed
from aubieeternal-institute.org is a separate, explicit sync step —
airlock checks always work offline against whatever's on disk.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

HOUSEHOLD_DIR = Path(os.environ.get("AUBIE_QR_HOME", Path.home() / ".aubieeternal" / "qr_airlock"))
ALLOWLIST_PATH = HOUSEHOLD_DIR / "allowlist.json"
PUBLIC_FLAGS_PATH = HOUSEHOLD_DIR / "qr-flags.cache.json"   # cached copy of the public feed
HOUSEHOLD_LOG_PATH = HOUSEHOLD_DIR / "household_log.jsonl"  # written by log.py
PENDING_SHARE_PATH = HOUSEHOLD_DIR / "pending_share.jsonl"  # flags queued to publish


def ensure_household_dir() -> None:
    HOUSEHOLD_DIR.mkdir(parents=True, exist_ok=True)
    if not ALLOWLIST_PATH.exists():
        ALLOWLIST_PATH.write_text(json.dumps({"domains": [], "hashes": []}, indent=2))
    if not PUBLIC_FLAGS_PATH.exists():
        PUBLIC_FLAGS_PATH.write_text(json.dumps({"spec": "aubieeternal-qr-flag/v0.1", "flags": []}, indent=2))


@dataclass
class Flag:
    id: str
    status: str          # sighting | confirmed | withdrawn
    verdict: str
    payload_sha256: str
    payload_kind: str
    final_url: Optional[str] = None
    registered_domain: Optional[str] = None
    claimed_as: Optional[str] = None
    signals: List[str] = field(default_factory=list)
    sighting_count: int = 1
    publisher: str = "household"
    raw: Dict = field(default_factory=dict)


def load_allowlist() -> Dict[str, List[str]]:
    ensure_household_dir()
    try:
        return json.loads(ALLOWLIST_PATH.read_text())
    except (json.JSONDecodeError, FileNotFoundError):
        return {"domains": [], "hashes": []}


def add_to_allowlist(*, domain: Optional[str] = None, payload_hash: Optional[str] = None) -> None:
    data = load_allowlist()
    if domain and domain not in data["domains"]:
        data["domains"].append(domain)
    if payload_hash and payload_hash not in data["hashes"]:
        data["hashes"].append(payload_hash)
    ALLOWLIST_PATH.write_text(json.dumps(data, indent=2))


def is_allowed(*, domain: Optional[str] = None, payload_hash: Optional[str] = None) -> bool:
    data = load_allowlist()
    if payload_hash and payload_hash in data.get("hashes", []):
        return True
    if domain and domain in data.get("domains", []):
        return True
    return False


def load_public_flags() -> List[Flag]:
    ensure_household_dir()
    try:
        raw = json.loads(PUBLIC_FLAGS_PATH.read_text())
    except (json.JSONDecodeError, FileNotFoundError):
        return []
    flags = []
    for f in raw.get("flags", []):
        flags.append(Flag(
            id=f.get("id", ""),
            status=f.get("status", "sighting"),
            verdict=f.get("verdict", "unknown"),
            payload_sha256=f.get("payload_sha256", ""),
            payload_kind=f.get("payload_kind", "url"),
            final_url=f.get("final_url"),
            registered_domain=f.get("registered_domain"),
            claimed_as=f.get("claimed_as"),
            signals=f.get("signals", []),
            sighting_count=f.get("sighting_count", 1),
            publisher=f.get("publisher", "household"),
            raw=f,
        ))
    return flags


def find_public_flag(payload_hash: str) -> Optional[Flag]:
    for f in load_public_flags():
        if f.payload_sha256 == payload_hash and f.status != "withdrawn":
            return f
    return None


def find_household_prior_verdict(payload_hash: str) -> Optional[Dict]:
    """Most recent household log entry for this exact payload, if any."""
    if not HOUSEHOLD_LOG_PATH.exists():
        return None
    last = None
    with HOUSEHOLD_LOG_PATH.open("r") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("payload_sha256") == payload_hash:
                last = entry
    return last


def queue_flag_for_sharing(flag_obj: Dict) -> None:
    """
    Append a household-approved flag to the pending-share queue.
    This is a *local* JSONL file — actually publishing it (git commit / PR
    / push to the institute site) is a separate, explicit human step, per
    the handoff's 'no auto-share' rule.
    """
    ensure_household_dir()
    with PENDING_SHARE_PATH.open("a") as fh:
        fh.write(json.dumps(flag_obj) + "\n")

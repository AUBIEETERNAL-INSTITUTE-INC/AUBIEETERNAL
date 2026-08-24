"""
utils/file_io.py — Centralized /mnt/main/ persistence for AUBIEETERNAL
=======================================================================
All file I/O in one place. No more scattered Path() calls across 10,600 lines.

Usage:
    from utils.file_io import DATA_DIR, append_jsonl, read_jsonl_tail
    append_jsonl(DATA_DIR / "master_truth_log.jsonl", {"event": "test"})
"""

import os, json, hashlib, datetime
from pathlib import Path
import socket as _socket

# ── Data directory resolution ─────────────────────────────────────────────────

def _resolve_data_dir() -> Path:
    """Resolve /mnt/main (StartOS) or ~/.aubieeternal/main (local)."""
    try:
        _socket.gethostbyname("localhost")
        return Path("/mnt/main")
    except Exception:
        p = Path(os.path.expanduser("~/.aubieeternal/main"))
        p.mkdir(parents=True, exist_ok=True)
        return p

DATA_DIR  = _resolve_data_dir()
REPO_DIR  = DATA_DIR / "repo"

# Well-known paths
TRUTH_LOG       = DATA_DIR / "master_truth_log.jsonl"
SWARM_STATUS    = DATA_DIR / "swarm_status.json"
TIER2_DIGEST    = REPO_DIR / "tier2_digest.txt"
API_DIR         = REPO_DIR / "epistemic_commons" / "api"
GROK_LOG        = DATA_DIR / "grokipedia_entries.jsonl"
PVC_LOG         = DATA_DIR / "pvc_research.jsonl"
POLYVAGAL_LOG   = DATA_DIR / "polyvagal_states.jsonl"
BELIEF_LEDGER   = DATA_DIR / "belief_ledger.jsonl"
FORESIGHT_LOG   = DATA_DIR / "foresight_tracker.jsonl"
CONTRIB_LOG     = DATA_DIR / "builder_contributions.jsonl"
STEELMAN_LOG    = DATA_DIR / "steelman_history.jsonl"
TFA_LOG         = DATA_DIR / "truth_frequency_encounters.jsonl"
MC_LOG          = DATA_DIR / "monte_carlo_results.jsonl"


def ensure_structure() -> None:
    """Create all expected directories and files on first run."""
    for d in [DATA_DIR, REPO_DIR, API_DIR,
              REPO_DIR / "grokipedia",
              REPO_DIR / "epistemic_commons" / "steelmans",
              DATA_DIR / "repo" / "epistemic_immune_profiles"]:
        d.mkdir(parents=True, exist_ok=True)
    print(f"[file_io] Structure ensured at {DATA_DIR}")


# ── JSONL helpers ──────────────────────────────────────────────────────────────

def append_jsonl(path: Path, record: dict) -> None:
    """Append one JSON record to a .jsonl file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")


def read_jsonl(path: Path, max_lines: int = 0,
               filter_family: str = "") -> list:
    """
    Read a .jsonl file. Optionally tail the last N lines and/or
    filter by family_id.
    """
    if not path.exists():
        return []
    entries = []
    text = path.read_text().strip()
    if not text:
        return []
    lines = text.split("\n")
    if max_lines > 0:
        lines = lines[-max_lines:]
    for line in lines:
        if not line.strip():
            continue
        try:
            e = json.loads(line)
            if filter_family and e.get("family_id") != filter_family:
                continue
            entries.append(e)
        except Exception:
            pass
    return entries


def read_jsonl_tail(path: Path, n: int = 20) -> list:
    return read_jsonl(path, max_lines=n)


def read_json(path: Path, default=None):
    """Read a .json file, return default if missing/corrupt."""
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def write_json(path: Path, data: dict, indent: int = 2) -> None:
    """Write a .json file atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=indent, default=str))
    tmp.replace(path)


# ── Swarm status ───────────────────────────────────────────────────────────────

def get_swarm_status() -> dict:
    """Read live swarm_status.json with safe defaults."""
    defaults = {
        "inter_rune_coherence":    1.000000,
        "wonder_index":            1.0,
        "mets":                    0,
        "grokipedia_count":        0,
        "child_rune_confirmations": 0,
        "daily_cost_usd":          0.0,
    }
    data = read_json(SWARM_STATUS, {})
    return {**defaults, **data}


def get_tier2_digest(max_chars: int = 5000) -> str:
    """Read the latest Tier 2 digest."""
    if not TIER2_DIGEST.exists():
        return ""
    return TIER2_DIGEST.read_text()[:max_chars]


# ── Truth log ─────────────────────────────────────────────────────────────────

def write_truth_log(event_type: str, detail: str,
                     coherence: float = 0.0,
                     wonder_delta: float = 0.0,
                     tags: list = None,
                     family_id: str = "default") -> None:
    """Append one event to master_truth_log.jsonl."""
    append_jsonl(TRUTH_LOG, {
        "timestamp":  datetime.datetime.now().isoformat(),
        "family_id":  family_id,
        "event_type": event_type,
        "detail":     str(detail)[:500],
        "coherence":  round(coherence, 6),
        "wonder":     round(wonder_delta, 4),
        "tags":       tags or [],
    })


# ── Session state snapshots ────────────────────────────────────────────────────

def save_session_snapshot(session_dict: dict, family_id: str = "default") -> str:
    """Save a session snapshot, return the file path."""
    snap_dir = DATA_DIR / "session_snapshots"
    snap_dir.mkdir(exist_ok=True)
    ts    = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = snap_dir / f"{family_id}_{ts}.json"
    write_json(fname, {**session_dict, "snapshot_at": ts})
    return str(fname)


# ── Git helpers ────────────────────────────────────────────────────────────────

def trigger_git_push(message: str = "auto: AUBIEETERNAL state update") -> bool:
    """
    Trigger a git push from the repo directory.
    Returns True if push succeeded.
    """
    import subprocess
    repo = REPO_DIR
    if not (repo / ".git").exists():
        return False
    try:
        subprocess.run(["git", "-C", str(repo), "add", "-A"],
                       capture_output=True, timeout=30)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", message],
                       capture_output=True, timeout=30)
        result = subprocess.run(["git", "-C", str(repo), "push"],
                                capture_output=True, timeout=60)
        return result.returncode == 0
    except Exception:
        return False


if __name__ == "__main__":
    ensure_structure()
    s = get_swarm_status()
    print(f"✅ file_io operational")
    print(f"   Data dir: {DATA_DIR}")
    print(f"   Coherence: {s['inter_rune_coherence']}")
    print(f"   Wonder: {s['wonder_index']}")

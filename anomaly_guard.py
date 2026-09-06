#!/usr/bin/env python3
"""
anomaly_guard.py — outside-observer anomaly check for the aubie-swarm loop.

FIRST PASS, HARD RULES ONLY. No ML this round — no Markov transition matrix,
no Isolation Forest, no sklearn dependency. Those need a few real weeks of
clean post-fix "good day" data to calibrate a trustworthy baseline, and the
runaway fixes only landed 2026-09-05. Building the statistical layers now
would risk a model that pages on normal variation or misses real anomalies.
They are deferred to a later session (see ERROR_LEDGER.md).

What this DOES do tonight — the two pieces that need zero training data and
would still catch a repeat of the 2026-09-04 runaway's exact shape
immediately:

  1. A tick labeler: map each ~30s swarm heartbeat to one state
     (IDLE | WORK | SPIKE | PUSH | SKIP | ERR | NOOP) by reading the real
     on-disk evidence — the swarm journal (`journalctl -u aubie-swarm.service`)
     and, where the journal shows it, the telemetry-push status file. It does
     NOT invent fields: `wonder_log.jsonl`'s real schema is
     {timestamp, wonder_index, hits, delta} with no state column, so the
     journal's `💓 Tick N` line is the heartbeat spine and the markers
     printed between ticks decide the state. Anything unrecognised falls back
     to IDLE — never SPIKE (a false SPIKE would be a false negative on the
     one thing this exists to catch).

  2. Two hard-rule signals computed from the labeled ticks + any text blobs
     already readable from the tier-2 digest / truth log / daily insights:
       - max_spike_run : longest consecutive run of SPIKE ticks in the last
                         hour. The 2026-09-04 incident was 501 Tier-2 pulses;
                         this trips inside the first 15-minute evaluation
                         window, not 13 hours in.
       - ritual_hits   : matches against a FROZEN lexicon taken verbatim from
                         the Sep 4 incident quotes in ERROR_LEDGER.md.

Page predicate (hard rule, no learned threshold), per the handoff:

        max_spike_run > 3   OR   ritual_hits >= 3

A third term — a NOOP "stale hold" — is added below (PAGE_ON_NOOP_HOLD) to
satisfy the replay harness's case 4: a scheduled trigger that fired but
produced no output (the exact dc945427 failure class). It is the same
zero-training-data hard rule shape, no ML. Set PAGE_ON_NOOP_HOLD = False to
match the handoff's two-term predicate verbatim.

This module is a pure OUTSIDE OBSERVER. It never imports swarm_v4_1.py and is
never imported by it — no new closed loop, same principle as the wonder
hysteresis fix. It only reads files / shells out to journalctl.

Standalone:  python3 anomaly_guard.py --replay     # 4 synthetic cases, exits 0/1
             python3 anomaly_guard.py --live        # print the live analysis JSON
Imported:    from anomaly_guard import run_live, analyze, label_ticks
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional

REPO_ROOT = Path(__file__).resolve().parent
SWARM_UNIT = "aubie-swarm.service"

# ── State vocabulary ────────────────────────────────────────────────────────
IDLE, WORK, SPIKE, PUSH, SKIP, ERR, NOOP = (
    "IDLE", "WORK", "SPIKE", "PUSH", "SKIP", "ERR", "NOOP"
)

# When one heartbeat window contains several markers, the highest-precedence
# state wins. SPIKE outranks ERR on purpose: the page predicate leans on
# max_spike_run and the handoff is explicit that a SPIKE must never be
# under-counted. IDLE is the floor for anything unrecognised.
_STATE_PRECEDENCE = [SPIKE, ERR, NOOP, SKIP, PUSH, WORK, IDLE]


def _rank(state: str) -> int:
    try:
        return _STATE_PRECEDENCE.index(state)
    except ValueError:
        return len(_STATE_PRECEDENCE)


# ── Journal marker patterns (exact strings printed by swarm/swarm_v4_1.py) ──
_MARKERS: list[tuple[str, re.Pattern]] = [
    # SPIKE — a wonder trigger / hormetic pulse fired this tick
    (SPIKE, re.compile(r"WONDER SPIKE|HORMETIC PULSE|activating Tier 2")),
    # ERR — an exception / SMTP failure that was actually logged
    (ERR, re.compile(r"Loop error:|❌ Error:|❌ .*error:|Traceback \(most recent call last\)|alert email failed")),
    # SKIP — skip-and-log of an oversized telemetry file (032f3b80 family)
    (SKIP, re.compile(r"telemetry push: skipping |main push: skipping ")),
    # PUSH — a telemetry-branch push that returned 0
    (PUSH, re.compile(r"📊 telemetry push: 0\b")),
    # WORK — a scheduled trigger actually produced output this window
    (WORK, re.compile(
        r"\[synthesis\] ✅ Complete"
        r"|\[curriculum-autogen\] ✅ Proposed"
        r"|\[email-watch\] ✅ Digest written"
        r"|\[epistemic-commons\] Commons publish: (?!.*error)"
        r"|\[epistemic-commons\] API endpoints updated:"
        r"|\[living-lattice\] Signal publish: (?!.*error)"
    )),
    # NOOP — a scheduled trigger was due but produced nothing: the dc945427
    # class (silent import miss mislabeled "not found in repo"), plus the
    # honest failure strings the same call sites print.
    (NOOP, re.compile(r"not found in repo|returned False|⚠️  Skipped:|⚠️  Digest error:")),
]

_HEARTBEAT_RE = re.compile(r"💓 Tick (\d+)")

# States this labeler can actually derive from live data, vs. ones that would
# need a field the real logs don't carry. Reported by labelability().
_LABELABLE_FROM_JOURNAL = {SPIKE, ERR, SKIP, PUSH, WORK, NOOP, IDLE}
_NEEDS_FIELD_NOT_IN_LOGS: dict[str, str] = {
    # nothing right now — every state above is journal-derivable. Kept as the
    # honest place to record a gap if one is found later.
}


# ── Data types ─────────────────────────────────────────────────────────────
@dataclass
class Tick:
    ts: Optional[datetime]
    state: str
    tick_num: Optional[int] = None
    evidence: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "ts": self.ts.isoformat() if self.ts else None,
            "state": self.state,
            "tick_num": self.tick_num,
            "evidence": self.evidence,
        }


# ── Journal parsing ────────────────────────────────────────────────────────
_TS_TZ_FIX = re.compile(r"([+-]\d{2})(\d{2})$")


def _parse_ts(token: str) -> Optional[datetime]:
    """Parse a `journalctl -o short-iso` leading timestamp token.
    e.g. '2026-09-05T16:19:09-0400' -> aware datetime. Returns None on any
    format we don't recognise (ordering still carries the analysis)."""
    tok = _TS_TZ_FIX.sub(r"\1:\2", token.strip())
    try:
        dt = datetime.fromisoformat(tok)
    except ValueError:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def parse_journal_lines(raw: Iterable[str]) -> list[tuple[Optional[datetime], str]]:
    """Turn raw journal text into (timestamp, message) pairs. Accepts both
    `-o short-iso` lines ('<ts> host unit[pid]: msg') and bare marker lines
    (ts None). Blank lines are dropped."""
    out: list[tuple[Optional[datetime], str]] = []
    for line in raw:
        line = line.rstrip("\n")
        if not line.strip():
            continue
        parts = line.split(" ", 1)
        ts = _parse_ts(parts[0]) if parts else None
        if ts is not None and len(parts) == 2:
            rest = parts[1]
            # strip 'host unit[pid]: ' prefix if present
            m = re.match(r"\S+ [^:]+: (.*)", rest)
            msg = m.group(1) if m else rest
        else:
            msg = line
        out.append((ts, msg))
    return out


# ── Tick labeler ───────────────────────────────────────────────────────────
def _window_state(markers: list[str]) -> str:
    if not markers:
        return IDLE
    return min(markers, key=_rank)


def label_ticks(events: list[tuple[Optional[datetime], str]]) -> list[Tick]:
    """Walk (ts, msg) events in order. Every `💓 Tick N` line closes a
    heartbeat window; the markers seen since the previous tick decide that
    tick's state (highest precedence wins, IDLE if none). Markers before the
    first heartbeat attach to the first tick; a trailing partial window with
    markers is emitted as a final tick so a spike right at 'now' is not
    lost."""
    ticks: list[Tick] = []
    pending_states: list[str] = []
    pending_evidence: list[str] = []
    last_ts: Optional[datetime] = None

    def flush(ts: Optional[datetime], tick_num: Optional[int]) -> None:
        ticks.append(Tick(
            ts=ts or last_ts,
            state=_window_state(pending_states),
            tick_num=tick_num,
            evidence=list(pending_evidence),
        ))
        pending_states.clear()
        pending_evidence.clear()

    for ts, msg in events:
        if ts is not None:
            last_ts = ts
        hb = _HEARTBEAT_RE.search(msg)
        if hb:
            flush(ts, int(hb.group(1)))
            continue
        for state, pat in _MARKERS:
            if pat.search(msg):
                pending_states.append(state)
                pending_evidence.append(msg.strip()[:240])
                break
    if pending_states:
        flush(last_ts, None)
    return ticks


def labelability(events: list[tuple[Optional[datetime], str]]) -> dict:
    """Which states were actually observable in this event stream, and which
    would need a field the real logs don't carry. Honest reporting per the
    handoff — do not fake a state that isn't in the data."""
    seen: set[str] = set()
    for _, msg in events:
        if _HEARTBEAT_RE.search(msg):
            seen.add(IDLE)
            continue
        for state, pat in _MARKERS:
            if pat.search(msg):
                seen.add(state)
                break
    return {
        "labelable_from_journal": sorted(_LABELABLE_FROM_JOURNAL),
        "observed_in_this_stream": sorted(seen),
        "needs_field_not_in_logs": _NEEDS_FIELD_NOT_IN_LOGS,
        "fallback": "unknown -> IDLE (never SPIKE)",
    }

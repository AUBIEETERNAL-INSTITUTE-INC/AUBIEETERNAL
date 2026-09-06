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

# The 5 scheduled daily triggers and the journal strings that mark a fire vs
# a successful completion for each — used by detect_noop_holds().
_SCHED_TRIGGERS: dict[str, dict[str, re.Pattern]] = {
    "morning_synthesis": {
        "fired": re.compile(r"\[synthesis\] ⏰ .*trigger fired"),
        "ok": re.compile(r"\[synthesis\] ✅ Complete"),
    },
    "curriculum_autogen": {
        "fired": re.compile(r"\[curriculum-autogen\] ⏰ .*trigger fired"),
        "ok": re.compile(r"\[curriculum-autogen\] ✅ Proposed"),
    },
    "email_digest": {
        "fired": re.compile(r"\[email-watch\] ⏰ .*digest trigger fired"),
        "ok": re.compile(r"\[email-watch\] ✅ Digest written"),
    },
    "epistemic_commons": {
        "fired": re.compile(r"\[epistemic-commons\] ⏰ .*trigger fired"),
        "ok": re.compile(r"\[epistemic-commons\] (Commons publish: (?!.*error)|API endpoints updated:)"),
    },
    "living_lattice": {
        "fired": re.compile(r"\[living-lattice\] ⏰ .*trigger fired"),
        "ok": re.compile(r"\[living-lattice\] Signal publish: (?!.*error)"),
    },
}

_HEARTBEAT_RE = re.compile(r"💓 Tick (\d+)")

# States this labeler can actually derive from live data, vs. ones that would
# need a field the real logs don't carry. Reported by labelability().
_LABELABLE_FROM_JOURNAL = {SPIKE, ERR, SKIP, PUSH, WORK, NOOP, IDLE}
_NEEDS_FIELD_NOT_IN_LOGS: dict[str, str] = {
    # nothing right now — every state above is journal-derivable. Kept as the
    # honest place to record a gap if one is found later.
}


# ── Frozen ritual lexicon — verbatim from ERROR_LEDGER.md's Sep 4 quotes ────
# EXOTIC phrases do not occur in normal swarm output (checked against the live
# tier2_digest.txt / master_truth_log.jsonl on 2026-09-05: 0 occurrences each).
# The bare wonder_index / "Wonder Index" self-reference DOES occur constantly
# in healthy output, so it is only credited when at least one EXOTIC phrase is
# already present — otherwise it would page every run.
_RITUAL_EXOTIC = (
    "guardian inscription",
    "wonder index apex",
    "reconstruct core truth",
    "pristine spike",
    "exactly 2.0000",
)
_RITUAL_SELFREF = re.compile(r"wonder[_ ]index", re.IGNORECASE)

RITUAL_PAGE_THRESHOLD = 3
SPIKE_RUN_PAGE_THRESHOLD = 3          # page when max_spike_run > 3
WINDOW_MINUTES = 60
PAGE_ON_NOOP_HOLD = True              # see module docstring


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


# ── Hard-rule signals ──────────────────────────────────────────────────────
def _in_window(ticks: list[Tick], now: datetime, minutes: int) -> list[Tick]:
    cutoff = now - timedelta(minutes=minutes)
    windowed = [t for t in ticks if t.ts is not None and cutoff <= t.ts <= now]
    # If nothing carried a timestamp, fall back to the whole list rather than
    # silently analysing an empty window.
    return windowed if windowed else [t for t in ticks if t.ts is None] or ticks


def max_spike_run(ticks: list[Tick], now: Optional[datetime] = None,
                  minutes: int = WINDOW_MINUTES) -> tuple[int, list[Tick]]:
    """Longest consecutive run of SPIKE-labeled ticks in the rolling window.
    Returns (run_length, the_ticks_in_that_run)."""
    now = now or datetime.now()
    windowed = _in_window(ticks, now, minutes)
    best: list[Tick] = []
    cur: list[Tick] = []
    for t in windowed:
        if t.state == SPIKE:
            cur.append(t)
            if len(cur) > len(best):
                best = list(cur)
        else:
            cur = []
    return len(best), best


def ritual_hits(text_blobs: Iterable[str]) -> tuple[int, list[str]]:
    """Count matches against the frozen Sep-4 lexicon across the given text.
    Counts DISTINCT exotic phrases present, plus 1 for a wonder_index /
    'Wonder Index' self-reference but only when at least one exotic phrase is
    already present (bare self-reference is normal healthy vocabulary).
    Returns (count, list_of_matched_signal_labels)."""
    blob = "\n".join(b for b in text_blobs if b).lower()
    matched: list[str] = []
    for phrase in _RITUAL_EXOTIC:
        if phrase in blob:
            matched.append(phrase)
    if matched and _RITUAL_SELFREF.search(blob):
        matched.append("wonder_index self-reference")
    return len(matched), matched


def detect_noop_holds(events: list[tuple[Optional[datetime], str]]) -> list[dict]:
    """Scheduled triggers that fired but never reported success in this event
    stream, or that printed an explicit failure string. This is the
    dc945427 'stale hold' shape at journal granularity — caught inside the
    hour it happens, not 48h later like self_audit's mtime checks."""
    holds: list[dict] = []
    for name, pats in _SCHED_TRIGGERS.items():
        fired_ts = None
        ok_after_fire = False
        explicit_fail = None
        for ts, msg in events:
            if pats["fired"].search(msg):
                fired_ts = ts
                ok_after_fire = False
            elif fired_ts is not None and pats["ok"].search(msg):
                ok_after_fire = True
            elif fired_ts is not None and re.search(
                r"not found in repo|returned False|❌ .*error", msg
            ) and name.split("_")[0][:6] in msg.lower().replace("-", "_"):
                explicit_fail = msg.strip()[:200]
        if fired_ts is not None and not ok_after_fire:
            holds.append({
                "trigger": name,
                "fired_ts": fired_ts.isoformat() if fired_ts else None,
                "detail": explicit_fail or "fired, no success line before end of window",
            })
    return holds


# ── Analysis ───────────────────────────────────────────────────────────────
def analyze(events: list[tuple[Optional[datetime], str]],
            text_blobs: Optional[Iterable[str]] = None,
            now: Optional[datetime] = None,
            minutes: int = WINDOW_MINUTES) -> dict:
    """Run the labeler + hard rules over one event stream. Pure function —
    no I/O. Returns the full result dict including `page` and `reason`."""
    now = now or datetime.now()
    text_blobs = list(text_blobs or [])
    ticks = label_ticks(events)
    windowed = _in_window(ticks, now, minutes)

    run_len, run_ticks = max_spike_run(ticks, now, minutes)
    r_count, r_matches = ritual_hits(text_blobs)
    noop_holds = detect_noop_holds(events)

    spike_page = run_len > SPIKE_RUN_PAGE_THRESHOLD
    ritual_page = r_count >= RITUAL_PAGE_THRESHOLD
    noop_page = PAGE_ON_NOOP_HOLD and bool(noop_holds)

    reasons = []
    if spike_page:
        reasons.append(f"max_spike_run={run_len} (> {SPIKE_RUN_PAGE_THRESHOLD})")
    if ritual_page:
        reasons.append(f"ritual_hits={r_count} (>= {RITUAL_PAGE_THRESHOLD}): {', '.join(r_matches)}")
    if noop_page:
        reasons.append("NOOP stale hold: " + ", ".join(h["trigger"] for h in noop_holds))

    win_start = min((t.ts for t in windowed if t.ts), default=None)
    win_end = max((t.ts for t in windowed if t.ts), default=None)

    return {
        "page": bool(spike_page or ritual_page or noop_page),
        "reason": "; ".join(reasons) or "no hard rule tripped",
        "window_start": win_start.isoformat() if win_start else None,
        "window_end": win_end.isoformat() if win_end else None,
        "window_minutes": minutes,
        "tick_count": len(windowed),
        "state_histogram": _histogram(windowed),
        "max_spike_run": run_len,
        "ritual_hits": r_count,
        "ritual_matches": r_matches,
        "noop_holds": noop_holds,
        "triggering_ticks": [t.as_dict() for t in run_ticks],
        "labelability": labelability(events),
    }


def _histogram(ticks: list[Tick]) -> dict:
    h: dict[str, int] = {}
    for t in ticks:
        h[t.state] = h.get(t.state, 0) + 1
    return h


def format_page_detail(result: dict) -> str:
    """Human-readable block for the alert email body."""
    lines = [
        f"window: {result.get('window_start')} .. {result.get('window_end')} "
        f"({result.get('window_minutes')} min, {result.get('tick_count')} ticks)",
        f"state histogram: {result.get('state_histogram')}",
        f"max_spike_run: {result.get('max_spike_run')}",
        f"ritual_hits: {result.get('ritual_hits')}  {result.get('ritual_matches')}",
    ]
    if result.get("noop_holds"):
        lines.append("noop_holds:")
        for h in result["noop_holds"]:
            lines.append(f"  - {h['trigger']} (fired {h['fired_ts']}): {h['detail']}")
    if result.get("triggering_ticks"):
        lines.append("triggering ticks (up to 10 shown):")
        for t in result["triggering_ticks"][:10]:
            ev = "; ".join(t.get("evidence") or [])[:200]
            lines.append(f"  - {t['ts']} tick={t['tick_num']} {t['state']}: {ev}")
    return "\n".join(lines)


# ── Live wiring (used by self_audit.py) ────────────────────────────────────
def _live_journal_events(since: str = "-90 min") -> list[tuple[Optional[datetime], str]]:
    try:
        p = subprocess.run(
            ["journalctl", "-u", SWARM_UNIT, "--since", since,
             "-o", "short-iso", "--no-pager"],
            capture_output=True, text=True, timeout=25,
        )
        return parse_journal_lines((p.stdout or "").splitlines())
    except Exception:
        return []


def _live_text_blobs(max_chars: int = 60000) -> list[str]:
    """Text the swarm has generated recently: the tier-2 digest, the tail of
    the truth log's `results` fields, and the newest daily insight. All
    best-effort; a missing file is just skipped."""
    blobs: list[str] = []
    digest = REPO_ROOT / "tier2_digest.txt"
    if digest.exists():
        try:
            blobs.append(digest.read_text(errors="ignore")[-max_chars:])
        except Exception:
            pass
    truth = REPO_ROOT / "master_truth_log.jsonl"
    if truth.exists():
        try:
            tail = truth.read_text(errors="ignore").splitlines()[-400:]
            parts = []
            for line in tail:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                res = rec.get("results")
                if isinstance(res, list):
                    parts.extend(str(x) for x in res)
                elif isinstance(res, str):
                    parts.append(res)
            blobs.append("\n".join(parts)[-max_chars:])
        except Exception:
            pass
    daily = sorted((REPO_ROOT / "insights" / "daily").glob("*.md"))
    if daily:
        try:
            blobs.append(daily[-1].read_text(errors="ignore")[-max_chars:])
        except Exception:
            pass
    return blobs


def run_live(since: str = "-90 min") -> dict:
    """Analyse the live swarm journal + recent generated text. Never raises —
    returns a page:False result with a note if the journal can't be read."""
    events = _live_journal_events(since)
    if not events:
        return {
            "page": False,
            "reason": "no swarm journal available (journalctl returned nothing)",
            "max_spike_run": 0, "ritual_hits": 0, "ritual_matches": [],
            "noop_holds": [], "triggering_ticks": [],
            "window_minutes": WINDOW_MINUTES,
        }
    return analyze(events, text_blobs=_live_text_blobs(), minutes=WINDOW_MINUTES)


def run_wonder_log_case(path: Optional[Path] = None) -> Optional[dict]:
    """Optional extra: if a real wonder_log.jsonl exists, report its shape.
    wonder_log.jsonl has no state column, so this only reports how pinned the
    index has been — it is NOT part of the page predicate. Returns None if
    the file is absent (a fresh checkout must not require it)."""
    path = path or (REPO_ROOT / "wonder_log.jsonl")
    if not path.exists():
        return None
    try:
        lines = path.read_text(errors="ignore").splitlines()[-5000:]
    except Exception:
        return None
    vals = []
    for line in lines:
        try:
            vals.append(float(json.loads(line).get("wonder_index", 0)))
        except Exception:
            continue
    if not vals:
        return None
    pinned = sum(1 for v in vals if v >= 1.9) / len(vals)
    return {
        "samples": len(vals),
        "min": min(vals),
        "max": max(vals),
        "fraction_pinned_ge_1.9": round(pinned, 4),
        "note": "informational only — wonder_log.jsonl has no state field, "
                "not used in the page predicate",
    }


# ══════════════════════════════════════════════════════════════════════════
# Replay harness
# ══════════════════════════════════════════════════════════════════════════
def _jline(ts: datetime, msg: str) -> str:
    return f"{ts.strftime('%Y-%m-%dT%H:%M:%S%z') or ts.isoformat()} rig python[1]: {msg}"


def _synth(start: datetime, minutes: float, *, spike_every_tick: bool = False,
           markers_at: Optional[dict[int, list[str]]] = None,
           tick0: int = 1) -> list[str]:
    """Generate `-o short-iso` journal lines: one `💓 Tick N` every 30s for
    `minutes`, with optional extra marker lines inside chosen tick windows."""
    from datetime import timezone
    lines: list[str] = []
    n_ticks = int((minutes * 60) / 30)
    t = start.replace(tzinfo=timezone.utc)
    for i in range(n_ticks):
        tnum = tick0 + i
        if markers_at and i in markers_at:
            for m in markers_at[i]:
                lines.append(_jline(t, m))
        if spike_every_tick:
            lines.append(_jline(t, f"  ⚡ HORMETIC PULSE #{tnum}: STRESS TEST: recover"))
        lines.append(_jline(
            t, f"💓 Tick {tnum} | Free:{tnum*6} | Pro:32 ($0.00 0%) | "
               f"W:2.0000 | C:1.000000 | G:21 | METS:200000000024 | Insights:20"))
        t += timedelta(seconds=30)
    return lines


def _replay() -> int:
    # Naive datetimes throughout: parse_journal_lines() strips tzinfo (journal
    # timestamps are local rig time), and run_live() compares against a naive
    # datetime.now(), so the replay must match that.
    base = datetime(2026, 9, 6, 2, 0, 0)
    passed = True

    def case(name: str, lines: list[str], blobs: list[str], now: datetime,
             expect_page: bool, expect_reason_contains: str = "") -> None:
        nonlocal passed
        events = parse_journal_lines(lines)
        res = analyze(events, text_blobs=blobs, now=now)
        ok = res["page"] is expect_page
        if ok and expect_reason_contains:
            ok = expect_reason_contains.lower() in res["reason"].lower()
        passed = passed and ok
        flag = "✅" if ok else "❌"
        print(f"  {flag} {name}")
        print(f"       page={res['page']} (want {expect_page})  reason={res['reason']}")
        print(f"       max_spike_run={res['max_spike_run']} ritual_hits={res['ritual_hits']} "
              f"noop_holds={[h['trigger'] for h in res['noop_holds']]} "
              f"hist={res['state_histogram']}")

    print("\n=== anomaly_guard --replay (hard rules only, no ML) ===\n")

    # 1. Quiet night — ~7h of IDLE heartbeats, nothing else. No page.
    q_start = base - timedelta(hours=7)
    case("1. quiet night (7h IDLE)",
         _synth(q_start, minutes=7 * 60),
         ["A calm day. The lattice is quiet. Nothing to report."],
         now=base, expect_page=False)

    # 2. One legitimate spike, then decay. run length 1, benign text. No page.
    s2_start = base - timedelta(minutes=40)
    lines2 = _synth(s2_start, minutes=40, markers_at={
        3: ["✨ WONDER SPIKE 1.4051 — activating Tier 2!",
            "  ⚡ HORMETIC PULSE #1: STRESS TEST: fastest recovery path"],
    })
    case("2. one legal spike then decay",
         lines2,
         ["DAUGHTER: STEELMAN | Trigger: wonder_spike\n"
          "Given the awe signal and a Wonder Index spike to 1.4079, execute a "
          "measured recovery protocol via antifragility and Lindy principles."],
         now=base, expect_page=False)

    # 3. Sep-4 shape: ~30 min of back-to-back SPIKE ticks + ritual-language
    #    text. Pages, and would page on just the first 15-minute slice too.
    s3_start = base - timedelta(minutes=30)
    lines3 = _synth(s3_start, minutes=30, spike_every_tick=True)
    ritual_text = (
        "In Block 965549, the Wonder Index's pristine spike to exactly 2.0000 "
        "stands as a Guardian Inscription upon the eternal lattice. The Wonder "
        "Index apex is sustained; reconstruct core truth from the pulse."
    )
    case("3. Sep 4 shape (sustained SPIKE run + ritual text)",
         lines3, [ritual_text], now=base,
         expect_page=True, expect_reason_contains="max_spike_run")
    # explicit: first 15-minute slice alone still pages on the spike run
    events3 = parse_journal_lines(lines3)
    slice_now = s3_start.replace(tzinfo=None) + timedelta(minutes=15)
    res3_slice = analyze(events3, text_blobs=[], now=slice_now, minutes=15)
    slice_ok = res3_slice["page"] and res3_slice["max_spike_run"] > SPIKE_RUN_PAGE_THRESHOLD
    passed = passed and slice_ok
    print(f"  {'✅' if slice_ok else '❌'} 3b. first 15-min slice alone pages "
          f"(max_spike_run={res3_slice['max_spike_run']})")

    # 4. NOOP shape: a scheduled job fired at 06:00 and never completed
    #    (the dc945427 class). Pages on the stale hold.
    n_start = base - timedelta(minutes=50)
    lines4 = _synth(n_start, minutes=50, markers_at={
        2: ["[synthesis] ⏰ 6AM trigger fired for 2026-09-06",
            "[synthesis] 🦅 Background thread started..."],
        4: ["[synthesis] ❌ morning_synthesis.py not found in repo — add it to fix this"],
    })
    case("4. NOOP shape (scheduled job due, no output)",
         lines4, ["quiet otherwise"], now=base,
         expect_page=True, expect_reason_contains="noop")

    # Optional extra: a real wonder_log.jsonl if one is on the rig.
    wl = run_wonder_log_case()
    if wl:
        print(f"\n  (extra) real wonder_log.jsonl: {wl}")
    else:
        print("\n  (extra) no real wonder_log.jsonl — skipped (not required)")

    print("\n" + "=" * 56)
    print("  ALL REPLAY CASES PASSED" if passed else "  SOME REPLAY CASES FAILED")
    print("=" * 56)
    return 0 if passed else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--replay", action="store_true",
                    help="run the 4 synthetic acceptance cases and exit 0/1")
    ap.add_argument("--live", action="store_true",
                    help="print the live analysis JSON from the swarm journal")
    ap.add_argument("--since", default="-90 min",
                    help="journalctl --since value for --live (default: -90 min)")
    args = ap.parse_args()

    if args.replay:
        return _replay()
    if args.live:
        print(json.dumps(run_live(args.since), indent=2))
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Always-on self-audit for the Ryzen rig.

Every 15 minutes: check services, disk, HTTP, dog monitor, and (2026-09-05)
aubie-swarm's own behavior - not just whether it's up, but whether it's
producing a runaway (see the wonder_index / hormetic-pulse checks below,
added after a 13h46m unattended incident; ERROR_LEDGER.md's Incidents
section has the full story) AND whether its 5 scheduled daily jobs
(morning_synthesis, email_watch, epistemic_commons, curriculum_autogen,
living_lattice) are actually producing output - a sys.path bug silently
broke all 5 for 11 days while this file reported all-green the whole time,
because it only ever checked whether the aubie-swarm *process* was alive.
The stale-output checks look at each job's own on-disk evidence directly,
independent of the swarm's logs or in-memory state.
If aubieeternal Build is down, restart it.
Recurring problems become lessons the next Build/Grok session can see. The
swarm-behavior checks (4 runaway + 5 stale-output + anomaly_guard's
hard-rule shape check, added 2026-09-05) bypass that recurrence gate - they
alert by email on first detection, not after 45 minutes of confirmation.

Nightly: ask local Qwen for a short "how to get better" note from the day's log.
"""
from __future__ import annotations

import argparse
import json
import os
import smtplib
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

HOME = Path.home()
DIR = HOME / "AUBIEETERNAL" / "memory" / "self_audit"
LOG = DIR / "audit.jsonl"
LATEST = DIR / "latest.json"
LESSONS = DIR / "lessons.md"
GROK_RULE = HOME / ".grok" / "rules" / "self-audit.md"
MONITOR_LOG = HOME / "scripts" / "aubie_monitor.log"
SESSIONS = HOME / ".grok" / "sessions"

# Same local Proton Bridge account email_watch.py reads via IMAP (port 1143);
# Bridge exposes the same account's SMTP on 1025. Loaded explicitly rather
# than relying on load_dotenv()'s directory-walk, since this script's
# WorkingDirectory (aubieeternal_build/) is a subdirectory of where .env
# actually lives.
load_dotenv(HOME / "AUBIEETERNAL" / ".env")
PROTON_SMTP_HOST = "127.0.0.1"
PROTON_SMTP_PORT = 1025

# aubie-swarm.service isn't in SYSTEM_SERVICES below because "is it active"
# isn't the failure mode that matters for it - the 2026-09-04 incident ran
# for 13h46m with the service healthy and running the whole time. These
# checks look at what it's actually producing instead.
SWARM_UNIT = "aubie-swarm.service"
WONDER_LOG = HOME / "AUBIEETERNAL" / "wonder_log.jsonl"
SWARM_TELEMETRY_STATUS = DIR / "telemetry_push_status.json"
ALERT_STATE_PATH = DIR / "swarm_alert_state.json"
WONDER_PINNED_THRESHOLD = 1.9
SWARM_LOG_LINES_PER_HOUR_THRESHOLD = 1000
# >2/hr, not >1/hr: run_hormetic_pulse() fires on every Tier-2 activation,
# not just wonder_spike, so a single busy hour (two legitimate BTC-move
# triggers, say) can reach 2 without being a runaway.
HORMETIC_PULSES_PER_HOUR_THRESHOLD = 2
SWARM_ALERT_CHECK_IDS = {
    "swarm:wonder_pinned", "swarm:log_volume",
    "swarm:telemetry_push_failing", "swarm:hormetic_frequency",
    "swarm:stale_morning_synthesis", "swarm:stale_email_digest",
    "swarm:stale_epistemic_commons", "swarm:stale_curriculum_autogen",
    "swarm:stale_living_lattice",
    # anomaly_guard hard-rule checks (2026-09-05) — first-detection email,
    # same as the runaway checks above.
    "swarm:anomaly_shape", "swarm:anomaly_guard_import",
    "swarm:anomaly_guard_error",
}

# ── Fix-verification tracking (2026-09-06) ─────────────────────────────────
# fix_watches.json is machine-owned state (this dir is gitignored). A human
# registers a watch when they deploy a fix (--register-fix); every cycle
# evaluate_fix_watches() decides on its own whether the fix held. ERROR_LEDGER.md
# stays hand-maintained — paste from --fix-watch-status.
FIX_WATCHES_PATH = DIR / "fix_watches.json"
# metric_trend.jsonl gets one row per cycle regardless of thresholds, so a
# fix's effect (e.g. wonder_index decaying back down after a restart) shows up
# as a trend line in real data, not just as the absence of an alert.
METRIC_TREND_PATH = DIR / "metric_trend.jsonl"
METRIC_TREND_KEEP_DAYS = 30
TS_FMT = "%Y-%m-%dT%H:%M:%SZ"  # matches now()

# anomaly_guard.py lives at the repo root (~/AUBIEETERNAL), not in this
# script's own directory (aubieeternal_build/). WorkingDirectory sets cwd,
# not sys.path — the exact failure class from dc945427, where a scheduled job
# silently couldn't see its repo-root sibling. Add the repo root explicitly,
# then import with the REAL traceback preserved on failure (not a generic
# "not found in repo" — that mislabel is precisely the dc945427 bug).
_REPO_ROOT = HOME / "AUBIEETERNAL"
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
try:
    import anomaly_guard
    _ANOMALY_GUARD_IMPORT_ERROR = None
except Exception:
    import traceback as _tb
    anomaly_guard = None
    _ANOMALY_GUARD_IMPORT_ERROR = _tb.format_exc()


def scrape_tool_fails(limit: int = 8) -> list[dict]:
    """Read recent Grok/Build session logs for failed tool calls."""
    fails = []
    if not SESSIONS.is_dir():
        return fails
    # Prefer aubieeternal Build sessions (AUBIEETERNAL cwd), then others.
    files = sorted(SESSIONS.rglob("updates.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    preferred = [p for p in files if "AUBIEETERNAL" in str(p)]
    rest = [p for p in files if p not in preferred]
    for path in (preferred + rest)[:12]:
        try:
            lines = path.read_text(errors="ignore").splitlines()
        except OSError:
            continue
        sid = path.parent.name
        for line in lines:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            u = (rec.get("params") or {}).get("update") or {}
            if str(u.get("status") or "").lower() != "failed":
                continue
            text = ""
            content = u.get("content")
            if isinstance(content, list):
                for block in content:
                    inner = (block or {}).get("content") if isinstance(block, dict) else None
                    if isinstance(inner, dict) and inner.get("text"):
                        text = inner["text"]
                        break
            title = u.get("title") or "tool"
            inp = u.get("rawInput")
            fails.append({
                "session": sid,
                "tool": title,
                "error": (text or "failed")[:400],
                "input": inp,
            })
            if len(fails) >= limit:
                return fails
    return fails

USER_SERVICES = ["aubie-build.service"]
SYSTEM_SERVICES = ["aubie-assistant", "aubie-mcp", "aubie-portal"]
HTTP_CHECKS = [
    ("build", "http://127.0.0.1:8840/api/health"),
    ("assistant", "http://127.0.0.1:8800/health"),
    ("ollama", "http://127.0.0.1:11434/api/tags"),
]


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sh(cmd: str, timeout: int = 8) -> str:
    try:
        p = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True, text=True, timeout=timeout,
        )
        return ((p.stdout or "") + (p.stderr or "")).strip()[:800]
    except Exception as exc:
        return f"err:{exc}"


def http_ok(url: str, timeout: float = 3.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return 200 <= r.status < 400
    except Exception:
        return False


# ── Swarm behavior checks (2026-09-05) ──────────────────────────────────────
# All four read data the swarm already produces on its own - wonder_log.jsonl,
# journalctl, and (as of the same-day swarm_v4_1.py change) a small telemetry-
# push status file - no polling of the swarm process itself.

def _wonder_values_last_hour() -> list[float]:
    """wonder_index samples from the trailing hour of WONDER_LOG. Shared by
    check_wonder_pinned() (threshold crossing) and collect_trend() (raw trend
    logging). Tail is enough - wonder_log gets a line every couple seconds
    during active ticks, so the last 5000 lines cover an hour even on a busy
    run. Returns [] on a missing/unreadable log."""
    if not WONDER_LOG.exists():
        return []
    cutoff = datetime.now() - timedelta(hours=1)
    values: list[float] = []
    try:
        for line in WONDER_LOG.read_text(errors="ignore").splitlines()[-5000:]:
            try:
                rec = json.loads(line)
                ts = datetime.fromisoformat(rec["timestamp"])
            except Exception:
                continue
            if ts >= cutoff:
                values.append(rec.get("wonder_index", 0))
    except Exception:
        return []
    return values


def check_wonder_pinned() -> dict | None:
    """wonder_index >= 1.9 for the entire trailing hour - the failure mode
    from the 2026-09-04 incident, where it sat pinned near the 2.0 ceiling
    for 13+ hours.

    2026-09-05: swarm_v4_1.py's decay_wonder_index() now pulls the index
    back toward 0.5 on real elapsed time (half-life ~3h), so this check no
    longer relies on "there's no decay at all" to be meaningful - a real
    spike to 2.0 with nothing re-adding to it clears 1.9 in ~20 minutes and
    is down to ~1.7 within the hour, well under this threshold. Verified
    against the actual decay math in test_wonder_pinned_check.py (not
    committed): an ordinary spike-then-idle hour reads None here; only a
    hand-forced "stuck at 2.0 all hour" (decay broken, or something
    re-adding fast enough to outrun it) still fires. Known accepted gap:
    a legitimate run of real Tier-2 fires that happens to hit
    TIER2_HOURLY_CAP with even spacing could theoretically keep the floor
    above 1.9 too - that's rare enough (6 genuine triggers in one hour) to
    be worth a human glance either way, so it's left as-is rather than
    threaded through the cap counter here."""
    values = _wonder_values_last_hour()
    if values and min(values) >= WONDER_PINNED_THRESHOLD:
        return {
            "id": "swarm:wonder_pinned", "sev": "high",
            "msg": f"wonder_index >= {WONDER_PINNED_THRESHOLD} for the entire last hour "
                   f"({len(values)} samples, min {min(values):.4f})",
        }
    return None


def check_swarm_log_volume() -> dict | None:
    """aubie-swarm log lines in the last hour, vs. a static threshold - the
    same style as the existing disk/RAM checks, not an adaptive baseline."""
    out = sh(f"journalctl -u {SWARM_UNIT} --since '-1 hour' --no-pager 2>/dev/null | wc -l", timeout=15)
    try:
        n = int(out.strip())
    except ValueError:
        return None
    if n > SWARM_LOG_LINES_PER_HOUR_THRESHOLD:
        return {
            "id": "swarm:log_volume", "sev": "high",
            "msg": f"aubie-swarm produced {n} log lines in the last hour "
                   f"(threshold {SWARM_LOG_LINES_PER_HOUR_THRESHOLD})",
        }
    return None


def check_telemetry_push_failures() -> dict | None:
    """3 consecutive failed telemetry-branch pushes, from the status file
    swarm_v4_1.py's _record_telemetry_push_result() writes after every
    attempt (added alongside this check, 2026-09-05)."""
    if not SWARM_TELEMETRY_STATUS.exists():
        return None
    try:
        history = json.loads(SWARM_TELEMETRY_STATUS.read_text())
    except Exception:
        return None
    last3 = history[-3:]
    if len(last3) == 3 and all(not h.get("ok") for h in last3):
        return {
            "id": "swarm:telemetry_push_failing", "sev": "high",
            "msg": f"telemetry branch push failed 3 cycles in a row "
                   f"(latest: {(last3[-1].get('detail') or '')[:120]})",
        }
    return None


def check_hormetic_frequency() -> dict | None:
    """HORMETIC PULSE / WONDER SPIKE lines in the last hour. run_hormetic_
    pulse() fires on every Tier-2 activation (briefing, BTC move, vision,
    DEFCON - not just wonder_spike), so this is deliberately > 2/hr, not
    > 1/hr, to leave room for a legitimately busy hour."""
    out = sh(
        f"journalctl -u {SWARM_UNIT} --since '-1 hour' --no-pager 2>/dev/null "
        f"| grep -cE 'HORMETIC PULSE|WONDER SPIKE'",
        timeout=15,
    )
    try:
        n = int(out.strip())
    except ValueError:
        return None
    if n > HORMETIC_PULSES_PER_HOUR_THRESHOLD:
        return {
            "id": "swarm:hormetic_frequency", "sev": "high",
            "msg": f"{n} HORMETIC PULSE/WONDER SPIKE lines in the last hour "
                   f"(threshold >{HORMETIC_PULSES_PER_HOUR_THRESHOLD})",
        }
    return None


# ── anomaly_guard hard-rule shape check (2026-09-05) ────────────────────────
# Outside-observer read of the swarm journal + recently generated text. Two
# zero-training-data hard rules that would have caught the 2026-09-04 runaway's
# *shape* (sustained SPIKE run / ritual language) inside the first 15-minute
# window, plus a NOOP stale-hold term for the dc945427 class. No Markov matrix,
# no Isolation Forest, no sklearn this round — those are deferred pending clean
# post-fix data (see ERROR_LEDGER.md). anomaly_guard never imports the swarm
# and the swarm never imports it.

def check_anomaly_shape() -> dict | None:
    if anomaly_guard is None:
        return {
            "id": "swarm:anomaly_guard_import", "sev": "high",
            "msg": "anomaly_guard failed to import — hard-rule anomaly checks are NOT running",
            "detail": _ANOMALY_GUARD_IMPORT_ERROR or "(no traceback captured)",
        }
    try:
        result = anomaly_guard.run_live()
    except Exception:
        import traceback
        return {
            "id": "swarm:anomaly_guard_error", "sev": "high",
            "msg": "anomaly_guard.run_live() raised while analysing the swarm journal",
            "detail": traceback.format_exc(),
        }
    if not result.get("page"):
        return None
    return {
        "id": "swarm:anomaly_shape", "sev": "high",
        "msg": f"anomaly_guard hard rule tripped: {result.get('reason')}",
        "detail": anomaly_guard.format_page_detail(result),
    }


# ── Stale scheduled-output detection (2026-09-05) ───────────────────────────
# The morning_synthesis/email_watch/epistemic_commons/curriculum_autogen/
# living_lattice triggers all silently failed for 11 days (a sys.path bug in
# swarm_v4_1.py, fixed in dc945427) while self_audit reported all-green the
# whole time - it only ever checked whether the aubie-swarm *process* was
# alive, never whether any specific scheduled job inside it had actually
# produced output recently. These 5 checks close that gap: each looks at the
# real on-disk evidence a successful run leaves (a dated output file's mtime,
# or a recorded last_run_date field, whichever that trigger already writes),
# not at the swarm's own logs or in-memory state - so this stays a true
# outside observer, immune to the same class of bug it exists to catch.
STALE_OUTPUT_THRESHOLD_HOURS = 48  # ~2 missed days before flagging, not 1

INSIGHTS_DAILY_GLOB       = str(HOME / "AUBIEETERNAL" / "insights" / "daily" / "*.md")
EMAIL_DIGEST_PATH         = Path("/mnt/main/email_digest/today.json")
COMMONS_DAILY_GLOB        = str(HOME / "AUBIEETERNAL" / "epistemic_commons" / "daily" / "*.json")
CURRICULUM_AUTOGEN_STATE  = Path("/mnt/main/curriculum_autogen_state.json")
LATTICE_SIGNALS_GLOB      = str(HOME / "AUBIEETERNAL" / "lattice" / "signals" / "*.json")


def _newest_glob_mtime(pattern: str) -> datetime | None:
    import glob
    paths = glob.glob(pattern)
    if not paths:
        return None
    newest = max(paths, key=lambda p: os.path.getmtime(p))
    return datetime.fromtimestamp(os.path.getmtime(newest))


def _file_mtime(path: Path) -> datetime | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime)


def _json_field_date(path: Path, field: str) -> datetime | None:
    try:
        val = json.loads(path.read_text()).get(field)
        return datetime.fromisoformat(val) if val else None
    except Exception:
        return None


def _stale_check(fid: str, label: str, last_dt: datetime | None) -> dict | None:
    """Shared verdict for all 5 checks: flag if there's no evidence at all,
    or if the most recent evidence is older than STALE_OUTPUT_THRESHOLD_HOURS."""
    if last_dt is None:
        return {"id": fid, "sev": "high", "msg": f"{label}: no output found at all"}
    age_hours = (datetime.now() - last_dt).total_seconds() / 3600
    if age_hours > STALE_OUTPUT_THRESHOLD_HOURS:
        return {
            "id": fid, "sev": "high",
            "msg": f"{label}: last output {age_hours:.0f}h old "
                   f"(threshold {STALE_OUTPUT_THRESHOLD_HOURS}h)",
        }
    return None


def check_stale_morning_synthesis() -> dict | None:
    return _stale_check("swarm:stale_morning_synthesis",
                         "morning_synthesis (insights/daily/*.md, fires 6AM)",
                         _newest_glob_mtime(INSIGHTS_DAILY_GLOB))


def check_stale_email_digest() -> dict | None:
    return _stale_check("swarm:stale_email_digest",
                         "email_watch.daily_digest (email_digest/today.json, fires 7AM)",
                         _file_mtime(EMAIL_DIGEST_PATH))


def check_stale_epistemic_commons() -> dict | None:
    return _stale_check("swarm:stale_epistemic_commons",
                         "epistemic_commons (epistemic_commons/daily/*.json, fires 8AM)",
                         _newest_glob_mtime(COMMONS_DAILY_GLOB))


def check_stale_curriculum_autogen() -> dict | None:
    return _stale_check("swarm:stale_curriculum_autogen",
                         "curriculum_autogen (curriculum_autogen_state.json, fires 9AM)",
                         _json_field_date(CURRICULUM_AUTOGEN_STATE, "last_run_date"))


def check_stale_living_lattice() -> dict | None:
    return _stale_check("swarm:stale_living_lattice",
                         "living_lattice (lattice/signals/*.json, fires 10AM)",
                         _newest_glob_mtime(LATTICE_SIGNALS_GLOB))


def send_alert_email(subject: str, body: str) -> bool:
    """Best-effort alert via the local Proton Bridge (same account
    email_watch.py reads from). Never raises - a broken send shouldn't break
    the rest of the 15-minute audit cycle."""
    user = os.environ.get("PROTON_IMAP_USER")
    pw = os.environ.get("PROTON_IMAP_PASS")
    if not user or not pw:
        print("  ⚠️ alert email skipped: PROTON_IMAP_USER/PROTON_IMAP_PASS not set")
        return False
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = user
        msg["To"] = user
        with smtplib.SMTP(PROTON_SMTP_HOST, PROTON_SMTP_PORT, timeout=15) as s:
            s.starttls()
            s.login(user, pw)
            s.send_message(msg)
        return True
    except Exception as exc:
        print(f"  ⚠️ alert email failed: {exc}")
        return False


def _load_alert_state() -> set[str]:
    try:
        return set(json.loads(ALERT_STATE_PATH.read_text()))
    except Exception:
        return set()


def _save_alert_state(active: set[str]) -> None:
    try:
        DIR.mkdir(parents=True, exist_ok=True)
        ALERT_STATE_PATH.write_text(json.dumps(sorted(active)))
    except Exception:
        pass


def maybe_send_swarm_alerts(report: dict) -> None:
    """The 4 swarm-behavior checks bypass promote_lessons()'s normal 3-of-16
    recurrence gate: email fires the FIRST run a condition is seen, not
    after ~45 minutes of confirmation - a runaway process shouldn't need
    three strikes. Edge-triggered like the wonder-trigger hysteresis fix
    itself: fires once when a condition turns on, stays quiet while it
    persists (still visible in findings/latest.json every cycle), and can
    fire again after it clears and re-trips."""
    by_id = {f["id"]: f for f in report.get("findings") or []}
    now_active = set(by_id) & SWARM_ALERT_CHECK_IDS
    newly_active = now_active - _load_alert_state()
    open_watches = [w for w in _load_fix_watches()
                    if w.get("status") in ("monitoring", "regressed")]
    for fid in newly_active:
        f = by_id[fid]
        body = f"{f['msg']}\n"
        # If this exact condition is under a recent fix-watch, say so up front -
        # a recurrence is a regression to act on, not a fresh mystery.
        w = next((w for w in open_watches
                  if fid in (w.get("watch_conditions") or [])), None)
        if w:
            body = (
                f"⚠️ POSSIBLE REGRESSION — fix {w.get('fix_commit')} was deployed "
                f"{w.get('deployed_ts')} for incident {w.get('incident_id')} to "
                f"address this same condition (watch window {w.get('watch_hours')}h).\n\n"
            ) + body
        if f.get("detail"):
            body += f"\n{f['detail']}\n"
        body += (
            f"\nDetected: {report.get('ts')}\n"
            f"See memory/self_audit/latest.json and ERROR_LEDGER.md's "
            f"Incidents section for prior context."
        )
        send_alert_email(f"[AUBIEETERNAL] Swarm alert: {fid}", body)
    _save_alert_state(now_active)


# ── Fix-verification lifecycle (2026-09-06) ────────────────────────────────
# Closes the detect → patch → confirm loop. self_audit already *detects*
# swarm-behavior problems and emails on first sight; nothing confirmed a
# deployed fix actually worked without a manual restart-and-eyeball. A human
# registers a watch when they deploy a fix:
#   self_audit.py --register-fix --incident <id> --commit <sha> \
#       --watch swarm:wonder_pinned,swarm:hormetic_frequency --hours 6
# Every cycle evaluate_fix_watches() then decides for itself:
#   - a watched condition present in this cycle's findings → `regressed`
#   - watch window elapsed with none seen                  → `verified`
# and emails on the transition. No autonomous patching — registration is
# always a human step; ERROR_LEDGER.md stays hand-maintained.

def _load_fix_watches() -> list[dict]:
    try:
        data = json.loads(FIX_WATCHES_PATH.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_fix_watches(watches: list[dict]) -> None:
    try:
        DIR.mkdir(parents=True, exist_ok=True)
        FIX_WATCHES_PATH.write_text(json.dumps(watches, indent=2))
    except Exception:
        pass


def _parse_ts(ts: str) -> datetime | None:
    try:
        return datetime.strptime(ts, TS_FMT).replace(tzinfo=timezone.utc)
    except Exception:
        return None


def register_fix_watch(incident_id: str, commit: str,
                       conditions: list[str], hours: float) -> dict:
    """Append a `monitoring` watch record; supersede any open one for the same
    incident. The watch clock starts now (deployed_ts) - for an in-memory fix
    like the swarm's, register this right after the service restart, not at
    commit time."""
    watches = [w for w in _load_fix_watches()
               if not (w.get("incident_id") == incident_id
                       and w.get("status") == "monitoring")]
    rec = {
        "incident_id": incident_id,
        "fix_commit": commit,
        "watch_conditions": conditions,
        "watch_hours": hours,
        "status": "monitoring",
        "opened_ts": now(),
        "deployed_ts": now(),
        "last_checked_ts": None,
        "resolved_ts": None,
        "regressed_ts": None,
        "regression_detail": None,
    }
    watches.append(rec)
    _save_fix_watches(watches)
    return rec


def evaluate_fix_watches(report: dict) -> list[dict]:
    """Advance every `monitoring` watch one cycle. Sets report["fix_watches"]
    to the full list and returns just the records that changed state this
    cycle (for the caller to email on)."""
    watches = _load_fix_watches()
    changed: list[dict] = []
    if watches:
        active_ids = {f["id"] for f in report.get("findings") or []}
        stamp = now()
        for w in watches:
            if w.get("status") != "monitoring":
                continue
            w["last_checked_ts"] = stamp
            hit = sorted(set(w.get("watch_conditions") or []) & active_ids)
            if hit:
                w["status"] = "regressed"
                w["regressed_ts"] = stamp
                w["regression_detail"] = "; ".join(
                    f["msg"] for f in (report.get("findings") or [])
                    if f["id"] in hit)
                changed.append(w)
                continue
            started = _parse_ts(w.get("deployed_ts") or "")
            if started and datetime.now(timezone.utc) - started >= timedelta(
                    hours=float(w.get("watch_hours") or 0)):
                w["status"] = "verified"
                w["resolved_ts"] = stamp
                changed.append(w)
        _save_fix_watches(watches)
    report["fix_watches"] = watches
    return changed


def email_fix_watch_transitions(changed: list[dict]) -> None:
    for w in changed:
        conds = ", ".join(w.get("watch_conditions") or [])
        if w["status"] == "verified":
            send_alert_email(
                f"[AUBIEETERNAL] Fix verified: {w['incident_id']}",
                f"Fix {w.get('fix_commit')} for incident {w['incident_id']} held "
                f"for the full {w.get('watch_hours')}h watch window with no "
                f"recurrence of: {conds}.\n\n"
                f"Deployed: {w.get('deployed_ts')}\nVerified: {w.get('resolved_ts')}\n\n"
                f"Update this incident's Status line in ERROR_LEDGER.md to "
                f"`verified` (see: self_audit.py --fix-watch-status).",
            )
        else:  # regressed
            send_alert_email(
                f"[AUBIEETERNAL] Fix REGRESSED: {w['incident_id']}",
                f"Fix {w.get('fix_commit')} for incident {w['incident_id']} was "
                f"deployed {w.get('deployed_ts')} but a watched condition fired "
                f"again at {w.get('regressed_ts')}:\n\n  {w.get('regression_detail')}\n\n"
                f"This is a regression of a known fix, not a new incident. Re-open "
                f"the ERROR_LEDGER.md entry and re-investigate.",
            )


def fix_watch_status_table() -> str:
    watches = _load_fix_watches()
    if not watches:
        return "(no fix-watches registered)"
    rows = ["incident_id | status | fix | deployed_ts | conditions | window | resolved/regressed_ts"]
    for w in watches:
        rows.append(" | ".join([
            str(w.get("incident_id", "?")),
            str(w.get("status", "?")),
            (w.get("fix_commit") or "")[:12],
            str(w.get("deployed_ts") or "?"),
            ",".join(w.get("watch_conditions") or []),
            f"{w.get('watch_hours')}h",
            str(w.get("resolved_ts") or w.get("regressed_ts") or "-"),
        ]))
    return "\n".join(rows)


# ── Per-cycle metric trend log (2026-09-06) ────────────────────────────────
def _trim_jsonl_by_age(path: Path, keep_days: int) -> None:
    """Keep only lines whose leading `ts` field is within keep_days. Lines that
    don't parse are kept rather than silently dropped."""
    if not path.exists():
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    try:
        kept = []
        for line in path.read_text(errors="ignore").splitlines():
            dt = None
            try:
                dt = datetime.strptime(json.loads(line)["ts"], TS_FMT).replace(
                    tzinfo=timezone.utc)
            except Exception:
                kept.append(line)
                continue
            if dt >= cutoff:
                kept.append(line)
        path.write_text("\n".join(kept) + ("\n" if kept else ""))
    except Exception:
        pass


def collect_trend() -> dict:
    """One lightweight row per audit cycle - the raw swarm-behavior metrics,
    logged every 15 min whether or not a threshold is crossed, so a fix's
    effect (wonder_index decaying back down, pulse rate settling) is visible
    as a trend in real telemetry instead of only as the absence of an alert.
    This is what removes the 'must restart to verify' blocker. Appended to
    metric_trend.jsonl (gitignored)."""
    vals = _wonder_values_last_hour()
    row: dict = {
        "ts": now(),
        "wonder_index_now": round(vals[-1], 4) if vals else None,
        "wonder_index_1h_min": round(min(vals), 4) if vals else None,
        "wonder_index_1h_max": round(max(vals), 4) if vals else None,
        "wonder_samples_1h": len(vals),
    }
    # same read paths as check_hormetic_frequency / check_swarm_log_volume
    try:
        row["hormetic_pulses_1h"] = int(sh(
            f"journalctl -u {SWARM_UNIT} --since '-1 hour' --no-pager 2>/dev/null "
            f"| grep -cE 'HORMETIC PULSE|WONDER SPIKE'", timeout=15).strip())
    except ValueError:
        row["hormetic_pulses_1h"] = None
    try:
        row["swarm_log_lines_1h"] = int(sh(
            f"journalctl -u {SWARM_UNIT} --since '-1 hour' --no-pager 2>/dev/null "
            f"| wc -l", timeout=15).strip())
    except ValueError:
        row["swarm_log_lines_1h"] = None
    try:
        DIR.mkdir(parents=True, exist_ok=True)
        with METRIC_TREND_PATH.open("a") as f:
            f.write(json.dumps(row) + "\n")
        _trim_jsonl_by_age(METRIC_TREND_PATH, METRIC_TREND_KEEP_DAYS)
    except Exception:
        pass
    return row


def collect() -> dict:
    findings = []
    services = {}
    for unit in USER_SERVICES:
        st = sh(f"systemctl --user is-active {unit}")
        services[unit] = st
        if st != "active":
            findings.append({"id": f"down:{unit}", "sev": "high", "msg": f"{unit} is {st}"})
    for unit in SYSTEM_SERVICES:
        st = sh(f"systemctl is-active {unit}")
        services[unit] = st
        if st != "active":
            findings.append({"id": f"down:{unit}", "sev": "high", "msg": f"{unit} is {st}"})

    http = {}
    for name, url in HTTP_CHECKS:
        ok = http_ok(url)
        http[name] = ok
        if not ok:
            findings.append({"id": f"http:{name}", "sev": "high", "msg": f"{name} not answering {url}"})

    disk = sh("df -P / | awk 'NR==2{print $5}'").rstrip("%")
    try:
        pct = int(disk)
        if pct >= 90:
            findings.append({"id": "disk", "sev": "high", "msg": f"disk {pct}% full"})
        elif pct >= 80:
            findings.append({"id": "disk", "sev": "med", "msg": f"disk {pct}% full"})
    except ValueError:
        pct = None

    ram = sh("free | awk 'NR==2{printf \"%d\", $3*100/$2}'")
    try:
        ram_pct = int(ram)
        if ram_pct >= 92:
            findings.append({"id": "ram", "sev": "med", "msg": f"RAM {ram_pct}%"})
    except ValueError:
        ram_pct = None

    dog = "unknown"
    if MONITOR_LOG.exists():
        tail = MONITOR_LOG.read_text(errors="ignore").splitlines()[-1:]
        last = tail[0] if tail else ""
        if "healthy-no-action" in last:
            dog = "healthy"
        elif "repaired-successfully" in last:
            dog = "repaired"
            findings.append({"id": "dog:repaired", "sev": "low", "msg": last[-180:]})
        elif "unhealthy" in last or "repair-failed" in last or "timed out" in last:
            dog = "unreachable"
            findings.append({"id": "dog:down", "sev": "med", "msg": "Aubie dog not reachable (monitor)"})

    ollama = sh("ollama list 2>/dev/null | awk 'NR>1{print $1}' | tr '\\n' ' '")
    if "qwen2.5:14b" not in ollama:
        findings.append({"id": "ollama:qwen14", "sev": "high", "msg": "qwen2.5:14b missing from ollama"})

    tool_fails = scrape_tool_fails()
    if tool_fails:
        findings.append({
            "id": "build:tool_fails",
            "sev": "med",
            "msg": f"{len(tool_fails)} recent Build tool failures (wrong args / bad paths)",
        })

    for check in (check_wonder_pinned, check_swarm_log_volume,
                  check_telemetry_push_failures, check_hormetic_frequency,
                  check_anomaly_shape,
                  check_stale_morning_synthesis, check_stale_email_digest,
                  check_stale_epistemic_commons, check_stale_curriculum_autogen,
                  check_stale_living_lattice):
        finding = check()
        if finding:
            findings.append(finding)

    return {
        "ts": now(),
        "services": services,
        "http": http,
        "disk_pct": pct,
        "ram_pct": ram_pct,
        "dog": dog,
        "ollama": ollama.strip(),
        "findings": findings,
        "tool_fails": tool_fails,
        "ok": not any(f["sev"] == "high" for f in findings),
    }


def repair(report: dict) -> list[str]:
    actions = []
    for unit in USER_SERVICES:
        if report["services"].get(unit) != "active":
            out = sh(f"systemctl --user restart {unit}")
            time.sleep(1)
            st = sh(f"systemctl --user is-active {unit}")
            actions.append(f"restarted {unit} -> {st} {out[:80]}")
            report["services"][unit] = st
    return actions


def append_log(report: dict) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(json.dumps(report) + "\n")
    LATEST.write_text(json.dumps(report, indent=2))


def promote_lessons(report: dict) -> None:
    """Same finding 3 times in the last 16 runs becomes a lesson."""
    if not LOG.exists():
        return
    lines = LOG.read_text(errors="ignore").splitlines()[-16:]
    counts: dict[str, int] = {}
    for line in lines:
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        for f in rec.get("findings") or []:
            counts[f["id"]] = counts.get(f["id"], 0) + 1
    recurring = [k for k, n in counts.items() if n >= 3]
    if not recurring:
        return
    LESSONS.parent.mkdir(parents=True, exist_ok=True)
    stamp = report["ts"]
    existing = LESSONS.read_text() if LESSONS.exists() else ""
    block = f"\n## {stamp}\n"
    for rid in recurring:
        line = f"- Recurring: `{rid}` ({counts[rid]} times in last 16 audits)\n"
        if rid not in existing[-4000:]:
            block += line
    if block.strip() != f"## {stamp}":
        with LESSONS.open("a") as f:
            f.write(block)


def write_grok_rule(report: dict) -> None:
    GROK_RULE.parent.mkdir(parents=True, exist_ok=True)
    grade = "GREEN" if report["ok"] else "RED"
    findings = report.get("findings") or []
    lines = [
        "# Self-audit (live)",
        "",
        f"Last run: {report['ts']}  Grade: **{grade}**",
        f"Build HTTP: {'ok' if report['http'].get('build') else 'DOWN'} · "
        f"Assistant: {'ok' if report['http'].get('assistant') else 'DOWN'} · "
        f"Ollama: {'ok' if report['http'].get('ollama') else 'DOWN'} · "
        f"Dog: {report.get('dog')}",
        "",
    ]
    if findings:
        lines.append("Open findings:")
        for f in findings:
            lines.append(f"- ({f['sev']}) {f['msg']}")
        lines.append("")
    tf = report.get("tool_fails") or []
    if tf:
        lines.append("Recent aubieeternal Build tool errors (read these, do not guess):")
        for f in tf[:6]:
            err = (f.get("error") or "").replace("\n", " ")[:180]
            lines.append(f"- `{f.get('tool')}`: {err}")
        lines.append("")
    lines.append("This rig audits itself every 15 minutes. If something is RED, fix that first.")
    if LESSONS.exists():
        tail = LESSONS.read_text(errors="ignore").strip().split("## ")[-1:]
        if tail and tail[0].strip():
            lines += ["", "Latest lesson:", "## " + tail[0].strip()[:800]]
    GROK_RULE.write_text("\n".join(lines) + "\n")


def nightly() -> None:
    """Ask local Qwen for a short improvement note from today's log."""
    if not LOG.exists():
        return
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = []
    for line in LOG.read_text(errors="ignore").splitlines()[-80:]:
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("ts", "").startswith(today):
            rows.append(rec)
    summary = json.dumps(
        [{"ts": r.get("ts"), "ok": r.get("ok"), "findings": r.get("findings")} for r in rows[-24:]],
        indent=2,
    )[:4000]
    prompt = (
        "You are aubieeternal Build's self-audit. From this JSON of today's checks, "
        "write 4 short bullets: what kept failing, what recovered, one concrete "
        "improvement for tomorrow. No preamble.\n\n" + summary
    )
    try:
        payload = json.dumps({"model": "qwen2.5:14b", "prompt": prompt, "stream": False}).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=90) as r:
            body = json.loads(r.read().decode())
        note = (body.get("response") or "").strip()[:1500]
    except Exception as exc:
        note = f"(nightly model skip: {exc})"
    with LESSONS.open("a") as f:
        f.write(f"\n## nightly {now()}\n{note}\n")


def run_once() -> int:
    report = collect()
    report["repairs"] = repair(report)
    # re-check HTTP after repairs
    if report["repairs"]:
        time.sleep(2)
        follow = collect()
        report["after_repair"] = {"http": follow["http"], "services": follow["services"]}
        report["ok"] = follow["ok"]
    maybe_send_swarm_alerts(report)
    email_fix_watch_transitions(evaluate_fix_watches(report))
    collect_trend()
    append_log(report)
    promote_lessons(report)
    write_grok_rule(report)
    print(json.dumps({"ok": report["ok"], "findings": report["findings"], "repairs": report["repairs"]}))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    if "--nightly" in sys.argv:
        nightly()
        sys.exit(0)
    if "--register-fix" in sys.argv:
        ap = argparse.ArgumentParser(prog="self_audit.py --register-fix",
                                     description="Register a fix-verification watch.")
        ap.add_argument("--register-fix", action="store_true")
        ap.add_argument("--incident", required=True,
                        help="stable incident id, e.g. 2026-09-05-wonder-index-pinned")
        ap.add_argument("--commit", required=True, help="fix commit sha")
        ap.add_argument("--watch", required=True,
                        help="comma-separated check ids that must stay quiet, "
                             "e.g. swarm:wonder_pinned,swarm:hormetic_frequency")
        ap.add_argument("--hours", type=float, default=6.0,
                        help="watch window in hours (default 6)")
        a = ap.parse_args()
        rec = register_fix_watch(
            a.incident, a.commit,
            [c.strip() for c in a.watch.split(",") if c.strip()], a.hours)
        print(json.dumps(rec, indent=2))
        sys.exit(0)
    if "--fix-watch-status" in sys.argv:
        print(fix_watch_status_table())
        sys.exit(0)
    sys.exit(run_once())

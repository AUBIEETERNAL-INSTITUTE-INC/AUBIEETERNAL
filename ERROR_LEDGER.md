# Error ledger

This file plus `git log` on `main` are the public record of what broke in
AUBIEETERNAL and how it was fixed. The project's stance is that the error trail
stays open — anyone can read it, re-run it, or fork it and show where it's still
wrong. Nothing here is a guarantee of correctness; it's a guarantee of
disclosure.

## How to read it

```bash
# The real fixes, newest first
git log --oneline --grep='^Fix' --grep='^Stop' --grep='Found:' --grep='broke' -i

# Everything the swarm published on its own (rare now — see below)
git log --oneline --grep='^chore(swarm)' --grep='^chore(status)'

# Full message for one commit
git show <sha> --stat
```

Before 2026-09-04, `main` was ~98% `🦅 v4.1 auto-push | Wonder:X |
Coherence:1.000000` — a swarm heartbeat that committed every ~90s and stamped a
`Coherence` value that was pinned to `1.000000` by its own clamp, not measured.
Commit `9111a3ce` stopped that: heartbeat telemetry now goes to the `telemetry`
branch, and `main` gets one honest `chore(status): rig alive <date>` pulse per
day. Real work lands as its own commit. The old heartbeat commits were left in
history (forward-only, no rewrite) — filter them out with the greps above.

## Incidents

Not everything here is a shipped fix. Some entries are an observed failure
with the hard data behind it, logged because the error trail staying open
matters independent of whether a patch has landed yet.

### 2026-09-04 — 13h46m unattended wonder-spike runaway (501 Tier-2 pulses)

**What happened:** `aubie-swarm.service` ran unattended 08:32–22:18 Eastern
(13h46m) with `check_wonder_trigger()` firing `run_tier2_core()` on nearly
every ~30s heartbeat tick instead of once per real spike. Confirmed against
that day's own logs: `wonder_log.jsonl` shows `wonder_index >= 1.4` on 17,842
of 17,965 entries (99.3%) for the day; `master_truth_log.jsonl` has 38,792
lines mentioning `HORMETIC` from the same window; `hormetic_pulse_count`
reached 501. The daughter output this produced reads like self-reinforcing
ritual language — e.g. *"In Block 965549, the Wonder Index's pristine spike
to exactly 2.0000..."* — because the trigger condition and the thing that
keeps re-satisfying it (`update_wonder_index()`'s awe-word scoring) feed each
other: no edge-detection meant the check never stopped re-firing once
elevated, and each fire's own output pushed the index right back up.

**Why this entry exists beyond the bug itself:** this is the concrete,
hard-data instance of the exact failure mode the human-approval-before-
broadcast gate on the Bitcoin-minting swarm exists to guard against —
self-reinforcing drift toward ritualistic/inflated language, running
unsupervised, for hours. That risk was already named before today; it is no
longer hypothetical.

**Contained, not clean — checked, not assumed:** `curriculum_autogen.py` has
no code path that reads `master_truth_log.jsonl` / `wonder_log.jsonl` /
hormetic-pulse text — its prompt is built only from existing lesson titles
and a fixed values blurb — and it had not run at all since 2026-08-24
regardless of today's incident (a separate, lower-urgency stall worth its
own look). `family_hud.py` and `phone_ui.py` have zero references to either
log file. Everything from today stayed in `master_truth_log.jsonl` /
`wonder_log.jsonl`, both gitignored telemetry routed to the `telemetry`
branch (see the heartbeat entry above) — never `main`, never anything a
student session reads.

**Fix (proposed same day, not yet merged):** hysteresis on
`check_wonder_trigger()` — fire only on the upward crossing through 1.4,
re-arm only once the index drops back below 1.2 — plus a `TIER2_HOURLY_CAP =
6` backstop inside `run_tier2_core()` itself, independent of trigger type, so
a bug in any *other* trigger (BTC move, briefing, vision, DEFCON) can't
reproduce the same runaway.

**Verified:** a standalone simulation of the real shape (rise → 500 ticks
pinned near the ceiling → cooldown below 1.2 → a second legitimate spike)
produces exactly 2 Tier-2 fires instead of 500+; the hourly cap holds 20
rapid calls in one window to 6 and resets after a rolling hour. Not yet
verified against a live swarm run — `aubie-swarm.service` is intentionally
left stopped pending review of the fix.

**Related, found while building this fix:** the swarm's git-collision hazard (above) isn't limited to a checked-out feature branch mid-work — while an unrelated review branch sat with an uncommitted `git mv` staged, the swarm's own `git commit` swept that staged rename into a commit under its own message (local-only, never reached `origin/main`, no lasting harm; cleanly undone). Any staged-but-uncommitted change in this working directory is exposed whenever the swarm's loop happens to fire, regardless of which branch is checked out or whether that branch is the one being modified.

### 2026-09-05 — ALSA lock fix: blocked on hardware, not verified

**What happened:** `push_audio_to_aubie()` in `assistant_server.py` (`132cd8b0`)
now serializes overlapping `/greet`-triggered calls with a `threading.Lock`,
so the UNO Q board's `aplay` can't be asked to open the ALSA device twice
concurrently. The fix is committed and deployed to the repo. It has **not**
been run against real hardware — the UNO Q board (Tailscale `100.66.110.65`)
has been offline for this entire session and remains offline as of this
entry. Do not read "committed" as "fixed"; the lock has never actually
serialized a real overlapping `aplay` call.

**Blocked on:** the board reconnecting to Tailscale.

**Reconnect test (run once it's back, not before):**
1. Pull `aubie_listen.py` off the board into git (it's still one of the
   files that only lives on-device — see "Edge devices are disposable"
   below).
2. Hit `/greet` twice within ~1s of each other.
3. Pass = no ALSA "Device or resource busy" error, and the second greeting
   still plays — delayed by the lock, not dropped. Fail = either an ALSA
   busy error, or the second greeting silently not playing at all.

Do not mark this fixed in `CLAUDE.md` or `CURRENT.md` until that test has
actually been run and passed.

## The standard: worked examples

These commits are what a fix commit should look like — a stranger can read them
without knowing any of the project's internal language.

| Commit | Date | What it documents |
|---|---|---|
| [`e2ba9e5a`](../../commit/e2ba9e5a) | 2026-09-04 | QR Airlock v0.1 (`tools/qr_airlock`) + `/qr/check` + phone_ui Scan tab. Notes the empty-model explain-hook fallback bug and that publishing flags stays a **manual human git step**. |
| [`8d476335`](../../commit/8d476335) | 2026-08-24 | `/oracle` 500 — `OracleRequest` was missing the `api_key` Pydantic field. Confirmed with a live curl before and after. |
| [`0855aa9a`](../../commit/0855aa9a) | 2026-08-25 | Family accounts were in-memory demo constants; the create/update methods didn't exist. Added real persistence + password hashing. |
| [`a8498fd9`](../../commit/a8498fd9) | 2026-08-25 | Dead xAI Alignment Lab nav entry; duplicate Epistemic Commons tabs; commons was never wired into the swarm so the daily folder went stale. |
| [`bb88562e`](../../commit/bb88562e) | 2026-08-24 | Windows installer's Desktop shortcut silently failed on machines with OneDrive Known Folder Move. |
| [`c66381cc`](../../commit/c66381cc) | 2026-08-24 | Browser-extension manifest pointed at file paths that didn't exist. |
| [`d2741d34`](../../commit/d2741d34) | 2026-08-25 | "Hello Matthew" re-greeting every ~3 min during an active lesson. |
| [`c81d7617`](../../commit/c81d7617) | 2026-05-31 | f-string with an unmatched `[` in `app.py`. (Commit subject is thin — "Update app.py"; the diff is the real record.) |

## Rule for future commits

Every fix commit message follows this shape:

```
<one-line summary>

Found: what was observed to be wrong, and how it was observed
Broke: the mechanism — why it did the wrong thing
Changed: what was changed, file by file if more than one
Verified: how you know it's fixed (command run, output, or "not verified — operator must ...")
```

If a value can't be measured, leave it out — don't stamp a constant and call it
a metric.

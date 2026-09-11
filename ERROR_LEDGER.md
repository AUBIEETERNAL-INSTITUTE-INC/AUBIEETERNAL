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

### Fix-status lifecycle

Swarm-behavior incidents carry a `**Status:**` line so a fix is trackable
through to confirmation, not just "patched and hope":

`deployed` → `monitoring` → `verified` | `regressed`

- **deployed** — fix commit is on `main`. For an in-memory fix (the swarm
  runs on module globals) it isn't live until `sudo systemctl restart
  aubie-swarm`.
- **monitoring** — a watch is registered and `self_audit.py` is checking each
  15-min cycle whether the named alert condition recurs. Register it *after*
  the restart so the clock is honest:
  `python aubieeternal_build/self_audit.py --register-fix --incident <id>
  --commit <sha> --watch swarm:wonder_pinned,swarm:hormetic_frequency
  --hours 6`
- **verified** — the watch window closed with no recurrence. `self_audit.py`
  emails `[AUBIEETERNAL] Fix verified: <id>` on the transition.
- **regressed** — a watched condition fired again inside the window;
  `self_audit.py` emails `[AUBIEETERNAL] Fix REGRESSED: <id>` and ordinary
  swarm-alert mails for that condition get a "POSSIBLE REGRESSION" banner.

Machine state is `memory/self_audit/fix_watches.json` (gitignored);
`python aubieeternal_build/self_audit.py --fix-watch-status` prints the table
to copy the resolved status back into this file by hand. `self_audit.py`
never edits this file itself. Raw per-cycle metrics
(`wonder_index` now / 1h min / max, pulse rate, log volume) land in
`memory/self_audit/metric_trend.jsonl` so a fix's effect is visible as a
trend, not only as the absence of an alert.

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

**Fix (`ea586f83`, merged 2026-09-04):** hysteresis on
`check_wonder_trigger()` — fire only on the upward crossing through 1.4,
re-arm only once the index drops back below 1.2 — plus a `TIER2_HOURLY_CAP =
6` backstop inside `run_tier2_core()` itself, independent of trigger type, so
a bug in any *other* trigger (BTC move, briefing, vision, DEFCON) can't
reproduce the same runaway.

**Verified:** a standalone simulation of the real shape (rise → 500 ticks
pinned near the ceiling → cooldown below 1.2 → a second legitimate spike)
produces exactly 2 Tier-2 fires instead of 500+; the hourly cap holds 20
rapid calls in one window to 6 and resets after a rolling hour.

**Follow-on (2026-09-05 → -06):** `aubie-swarm.service` ran with this fix for
~19h and did **not** recur the every-tick runaway — but `wonder_index` itself
stayed pinned at the 2.0 ceiling the whole time, so `check_wonder_trigger()`
never got back below 1.2 to re-arm and `self_audit.py` kept alerting. The
`decay_wonder_index()` patch (`9e4ad5ee`) meant to walk it down was ~10× too
weak against `update_wonder_index()`'s per-result positive `delta`. Fixed by
rebalancing that `delta` baseline — see the 2026-09-05 `wonder_index` entry
below. Service running again since 2026-09-06 04:42 EDT.

**Related, found while building this fix:** the swarm's git-collision hazard (above) isn't limited to a checked-out feature branch mid-work — while an unrelated review branch sat with an uncommitted `git mv` staged, the swarm's own `git commit` swept that staged rename into a commit under its own message (local-only, never reached `origin/main`, no lasting harm; cleanly undone). Any staged-but-uncommitted change in this working directory is exposed whenever the swarm's loop happens to fire, regardless of which branch is checked out or whether that branch is the one being modified.

### 2026-09-05 — wonder_index stayed pinned after the runaway fix (decay follow-on)

**What happened:** with `ea586f83` (hysteresis + hourly cap) and `9e4ad5ee`
(`decay_wonder_index()`, 3h half-life) both merged and live, `self_audit.py`
kept firing `swarm:hormetic_frequency` (2026-09-05T12:50:03Z — 4 pulses/hr,
threshold >2) and `swarm:wonder_pinned` (2026-09-05T14:42:03Z —
`wonder_index >= 1.9` for the whole trailing hour, 485 samples, min 1.9564);
four alerts that morning, all the same signal — the index sat at the 2.0
ceiling and hysteresis never re-armed below 1.2. Handoff:
`2026-09-04-claude-code-handoff-git-error-ledger.md` sibling notes.

**Root cause — checked, not assumed:** the decay term was running but is
~10× too weak in production. `update_wonder_index()` is called ~once per
7.4s on a live run, and its `delta = hits*0.003 - 0.001` is *positive on
100% of the last 6000 calls* — the awe-word list ("truth", "pattern",
"signal", "synthesis", "bitcoin"…) matches nearly all swarm output, so
`hits >= 1` always and the index ratchets up ~+0.057/min. A 3h-half-life
decay removes only ~+0.006/min at `wonder_index = 2.0`. It reaches the
ceiling within ~15 min of any run and stays there (>= 1.9 on 98% of live
samples). `9e4ad5ee`'s sims passed only because they used no adds, or a mild
held re-add at 1.5 — not the real ratchet.

**Fix (`2e05dca5`):** rebalanced the add side, not the decay.
`update_wonder_index()`'s baseline goes `-0.001` → `-0.009`, so `delta <= 0`
for ordinary output (hits 1–3, ~80% of live calls) and only awe-*dense*
output (hits >= 4) moves the index up; the existing decay then walks it back
toward `WONDER_FLOOR` (0.5) between genuine bursts. Hysteresis and
`TIER2_HOURLY_CAP = 6` unchanged. Trade-off accepted: `wonder_index` now
rests at/near the 0.5 floor during ordinary operation (a spike detector, not
a gauge with mid-range dynamics).

**Verified:** `python3 test_swarm_behavior.py` (`90cc3a82`) — the throwaway
harness is now a standing regression test that drives the real
`update_wonder_index` / `decay_wonder_index` / `check_wonder_trigger` against
a mocked clock and the observed live hits distribution:
- 3h of typical output → index decays to the 0.5 floor, trailing-hour min
  0.50, zero Tier-2 fires. Old `-0.001` baseline on the identical input:
  pinned at 2.0000 (the suite fails if a revert lands).
- a genuine 25-min awe-dense burst (hits 5–7) → crosses 1.4, fires Tier-2
  exactly once, decays back below 1.2, re-arms; a later burst fires again.
`py_compile` clean.

**Status:** `verified` `2e05dca5`. Watch registered after the `aubie-swarm`
restart (deployed 2026-09-06T11:19:57Z, watching
`swarm:wonder_pinned,swarm:hormetic_frequency`, 6h window); `self_audit.py`
held it the full window with no recurrence and moved it to `verified` at
2026-09-06T17:31:04Z (confirmed via `--fix-watch-status` on 2026-09-07).
`memory/self_audit/metric_trend.jsonl` showed `wonder_index_1h_max` falling
across cycles in the interim.

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

### 2026-09-11 — ALSA lock fix targets a code path that no longer exists

**What happened:** The board reconnected and the reconnect test above ran.
Result: the test as scoped could not pass or fail, because its premise no
longer matches the code.

- `push_audio_to_aubie()` (the function `_aubie_audio_lock` guards) is only
  called by `/speak` (the phone UI's typed "Say / Command" box). `/greet`
  itself returns its WAV directly in the HTTP response body and never calls
  it — the real board (`aubie_listen.py`, pulled this session, see
  `_remote/board/aubie_listen.py`) plays that response locally via `pw-play`,
  not `aplay`, and has since moved off `hw:0,0`/`plughw:0,0` entirely
  (EMEET card id is now autodetected — see `detect_emeet_card_id()`).
- `push_audio_to_aubie()` POSTs to `AUBIE_CALL_PORT = 8420` on the board.
  That port belonged to the **retired `spotmicro_dog` app's** own Docker
  container (`spotmicro_dog-main-1`, a `uvicorn` FastAPI process — see
  `spotmicro_dog/diag_snapshots/*.log`). The replacement `aubie-tutor` app
  only maps ports 7000 (WebUI) and 9999 (llamacpp), confirmed via
  `docker ps` on the board. **Nothing has listened on 8420 since
  `spotmicro_dog` was destroyed.** Calling `/speak` now reproducibly 500s:

  ```
  requests.exceptions.ConnectionError: HTTPConnectionPool(host='192.168.1.78',
  port=8420): ... Failed to establish a new connection: [Errno 111]
  Connection refused
  ```

  (confirmed live via `curl -X POST http://localhost:8800/speak -F text=...`
  against `aubie-assistant.service`, 2026-09-11.) The same dead port breaks
  `fetch_aubie_snapshot()` (`/snapshot`, used by the person-follow loop),
  the `/call/stream` websocket, and `call_dog_command()` (used for e.g. the
  Gabriela `flower_explosion` in `/greet` — silently, since its call sites
  are best-effort `try/except`). Board-side, `aubie_listen.py`'s own
  `dog_command()` helper (`rest`/`play_pong` for the idle-Pong feature) POSTs
  to the same dead `localhost:8420/dog/command` and fails the same way.
- Separately: even on the code path that *is* live, two overlapping
  `/greet` wake-word triggers are no longer reachable at all. The current
  `main()` loop (`aubie_listen.py`) is fully serial — it exits the
  `AudioImpulseRunner` context before calling `capture_and_greet()`, then
  `converse_loop()`, then re-enters listening, plus a 5s `COOLDOWN_SECONDS`
  — so the race the lock was written for cannot occur via real wake-word use
  with this loop structure.
- What was actually testable — the board's own playback-overlap guard
  (`pkill -f pw-play` before every new `pw-play`, in `capture_and_greet()`)
  — was reproduced directly on hardware (two `pw-play` calls 1s apart against
  a real `/greet` response WAV, `XDG_RUNTIME_DIR=/run/user/1000` set as
  `aubie_listen.py` itself sets it for the same reason). Result: **no ALSA
  "Device or resource busy" error** — but the mechanism is kill-and-restart,
  not queue-and-delay: the first playback is killed outright, not deferred.
  That's a real, working guard against a hung ALSA device, just not the
  "second greeting plays delayed, not dropped" behavior the original fix
  description called for.

**Verdict:** not a regression of `132cd8b0` — that lock never had a live
target to protect after the `spotmicro_dog` → `aubie-tutor` migration
silently orphaned port 8420 (no commit is implicated; the two changes
happened independently and neither referenced the other). Treat as a new,
open incident: `/speak`, `/snapshot`-based following, `/call/stream`, the
`flower_explosion` celebration, and idle-Pong's `rest`/`play_pong` calls are
all currently non-functional on real hardware. Needs a decision before a fix
can land: re-expose an equivalent HTTP API inside the new `aubie-tutor`
Python app (`python/main.py`) on 8420 or a fresh port, or replace these
calls with the same MCU Bridge-RPC mechanism `face_talk`/`face-text`/`wave`
already use successfully (`bridge_call()` in `aubie_listen.py`), which does
not depend on port 8420 at all.

**Status:** open — not yet fixed, root cause identified and confirmed live.

### 2026-09-05 — anomaly_guard: first pass only, statistical layers deferred

**What this is:** `anomaly_guard.py` (repo root) is a new outside-observer
check for the swarm's *shape*, aimed at the 2026-09-04 runaway. It does two
things, both zero-training-data hard rules:

1. **Tick labeler** — maps each ~30s heartbeat to
   `IDLE|WORK|SPIKE|PUSH|SKIP|ERR|NOOP` by reading the swarm journal
   (`journalctl -u aubie-swarm.service`). It does not invent fields:
   `wonder_log.jsonl`'s real schema is `{timestamp, wonder_index, hits,
   delta}` with no state column, so the journal's `💓 Tick N` line is the
   spine and the markers between ticks decide the state. Anything
   unrecognised → IDLE, never SPIKE.
2. **Two hard-rule signals** — `max_spike_run` (longest consecutive SPIKE
   run in the last hour) and `ritual_hits` (matches against a frozen lexicon
   taken verbatim from the Sep-4 quotes above). Page predicate:
   `max_spike_run > 3 OR ritual_hits >= 3`. A third term — a NOOP "stale
   hold" (a scheduled trigger that fired but produced no output: the
   `dc945427` class) — is added behind `PAGE_ON_NOOP_HOLD` to cover that
   shape at journal granularity. `ritual_hits` counts *distinct* exotic
   phrases; the bare `wonder_index` / "Wonder Index" self-reference is
   normal healthy vocabulary and is only credited when an exotic phrase is
   already present, so it does not false-page on live output (verified: 0
   exotic-phrase hits in the current `tier2_digest.txt` / truth log).

Wired into `aubieeternal_build/self_audit.py` as `check_anomaly_shape()` —
same first-detection email path as the runaway checks, no 3-of-16 gate. The
import adds the repo root to `sys.path` explicitly and keeps the **real
traceback** on failure (the `dc945427` mislabel-as-"not found" bug must not
recur). anomaly_guard never imports `swarm_v4_1.py` and is never imported by
it — outside observer only, no new closed loop.

**Deliberately NOT built this session — deferred pending clean data:** the
Gold Markov transition matrix and the Isolation Forest window scorer. Both
need a few real weeks of post-fix "good day" history to calibrate a
trustworthy baseline; the runaway fixes only landed 2026-09-05, so building
them now would risk a model that pages on normal variation or misses real
anomalies. No `sklearn` dependency was added.

**Verified:** `python3 anomaly_guard.py --replay` passes all 4 acceptance
cases (quiet night → no page; one legal spike → no page; Sep-4 sustained
SPIKE run + ritual text → pages, and pages on just the first 15-minute
slice; scheduled job fired-but-no-output → pages on the stale hold). Live
run against the current swarm journal returns `page: false`. Not yet
verified against a live *runaway* — none has occurred since the check
landed.

### 2026-09-07 — epistemic_commons daily job published nothing for 48h+ (no_seeds)

**Separate incident from the wonder_index-pinned entry above.** Different
subsystem (`epistemic_commons.py`, not `swarm_v4_1.py`), different failure
mode (a silent `no_seeds` early-return, not a runaway ratchet). It was
*exposed* by the wonder_index fix, not caused by a regression in it.

**What happened:** `self_audit.py` fired `swarm:stale_epistemic_commons`
(2026-09-07T12:24:04Z — newest `epistemic_commons/daily/*.json` was 48h old,
threshold 48h). The 8AM trigger *did* run on both 2026-09-06 and -07 —
journal shows `[epistemic-commons] ⏰ 8AM trigger fired` → `🌐 Daily publish
background thread started` → `Commons publish: no_seeds` both days. The API
half (`epistemic_commons_api.py`) succeeded each time (the `api/*.json`
publish commits `529e45e8`, `3a47193e` are it), which is why the tab looked
alive. Only the human-readable `daily/YYYY-MM-DD.{md,json}` letter was
missing. `run_daily_publish()` returns `{"status": "no_seeds"}` and writes
nothing when `_extract_epistemic_seeds()` comes back empty.

**Root cause — confirmed against the logs, two compounding parts:**
`_extract_epistemic_seeds()` scanned only `master_truth_log.jsonl`'s **last
300 lines** and hard-filtered **`wonder_index >= 1.1`**. Both assumptions
only ever held because of the pre-2026-09-04 wonder runaway: it fired Tier-2
on ~every heartbeat tick with `wonder_index` pinned at 2.0, so the last 300
lines were always saturated with 2.0-wonder tier-2 prose. After the runaway
fixes (`ea586f83` hysteresis + `TIER2_HOURLY_CAP=6`, then `2e05dca5` delta
rebalance, live at the 2026-09-06 07:17 EDT swarm restart), the swarm
behaves correctly: `wonder_index` rests near `WONDER_FLOOR` (0.5) and Tier-2
runs only on the 4 daily briefings — ~64 `result`-bearing entries/day
instead of ~14k. Tier-1 heartbeat rows don't count: they store a truncated,
highly repetitive `results` *list*, and `_extract_epistemic_seeds()` only
reads a single `result` *string*. Net: at 08:00 the 300-line window covers
~30–60 min and usually contains zero tier-2 entries; on 2026-09-07 the last
tier-2 before 08:00 was at 06:01, 318 lines back — outside the window. On
2026-09-06 there were tier-2 entries in the window but all sat below the
`>= 1.1` gate. Either part alone is sufficient to produce `no_seeds`.

Ruled out: not a path mismatch — `/mnt/main/repo` is a symlink to
`~/AUBIEETERNAL`, so `epistemic_commons.py`'s write dir and `self_audit.py`'s
`COMMONS_DAILY_GLOB` are the same inode. Not a scheduling break — the
trigger fired both days. Not a `swarm_v4_1.py` proximity bug — `2e05dca5`
never touched `maybe_trigger_epistemic_commons()`; the coupling is purely
through the *distribution of `wonder_index` values* the swarm writes to the
truth log.

**Fix (`91970284`):** `_extract_epistemic_seeds()` (and `_extract_steelmans()`)
rewritten to scope by **timestamp date** — today, widening to +yesterday
then to the whole scanned tail (`_SEED_SCAN_LINES = 12000`, ~3 post-fix
days) only if a day is too thin — instead of a fixed trailing line count.
The absolute `wonder_index >= 1.1` gate is **removed**; ranking is now
relative `(wonder_index, confidence)` desc, top `n`, with the real quality
bar unchanged (substantive length, not an error string, honesty risk
!= high) plus a first-120-char de-dupe for the repetitive briefing bursts.
Rationale: the wonder scale gets recalibrated periodically (this is the
second time in a week a fixed wonder cutoff silently broke a downstream
consumer); relative top-n survives rescalings.

**Catch-up:** ran `EpistemicCommons().run_daily_publish()` by hand →
published 2026-09-07 (7 seeds, 5 steelmans; templated fallback letter since
`qwen2.5:32b` isn't pulled — pre-existing, not part of this bug).
`check_stale_epistemic_commons()` returns `None` now.

**Verified:** the rewritten extractor returns 7 seeds against the live
85MB truth log; `run_daily_publish()` completes and writes all four output
files; `python3 -m py_compile epistemic_commons.py` clean. Not yet verified
against an unattended 8AM run.

**Status:** `monitoring` `91970284`. `aubie-swarm` restarted 2026-09-07
11:52:02 EDT (the running process had `epistemic_commons` cached in
`sys.modules`, so a restart was required to load the fix). Watch registered
2026-09-07T15:53:50Z — `--watch swarm:stale_epistemic_commons --hours 50`,
spanning the next two 08:00 runs plus the 48h stale threshold. `self_audit.py`
moves this to `verified` (or `regressed`) on its own; copy the transition
here from `--fix-watch-status`.

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

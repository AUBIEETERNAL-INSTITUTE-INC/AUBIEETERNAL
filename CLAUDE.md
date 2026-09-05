# CLAUDE.md

Shared project state lives in CURRENT.md. Read that first. Do not copy dates or hardware lists into this file.

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

AUBIEETERNAL is a free, offline-capable "sovereign university" — a single Streamlit application (`app.py`) plus a 24/7 background "swarm" process, Bitcoin-anchored credentialing, and a public CC0 "Epistemic Commons" API. It's designed to run on a $200 laptop, fully offline after first setup, and also runs as a StartOS service / Docker container in production.

## Commands

```bash
# Run the app locally
streamlit run app.py

# Or use the guided launcher (checks Python/Ollama, installs deps, opens browser)
python launcher.py

# Run the local browser-extension API server (port 8502)
python api_server.py

# Run the public Epistemic Commons API server
python epistemic_commons_api.py

# Integration test — proves degrees/peer-review/transcript pipeline agrees end-to-end
python test_pipeline.py

# Reliability suite — 7 HermesBench recipes (tutor handoff, provenance, safety, Bitcoin
# integrity, state persistence, drift)
python hermesbench_integration.py

# Epistemic drift analysis (compares current swarm output quality to a saved baseline)
python epistemic_drift_detector.py
python epistemic_drift_detector.py --baseline        # save a new baseline
python epistemic_drift_detector.py --ci --fail-on RED  # CI mode, nonzero exit on RED+

# Install deps
pip install -r requirements.txt
```

There is no linter, formatter, or unit-test framework configured (no pytest/flake8/black in
requirements.txt). `test_pipeline.py` is a standalone script (run directly with `python`, not
pytest) — it asserts via `sys.exit(0/1)`, not exceptions.

## Data directory resolution — read this before touching persistence code

Nearly every stateful module (`utils/file_io.py`, `models/state.py`, `swarm/swarm_v4_1.py`, etc.)
independently resolves a data directory the same way:

```python
try:
    socket.gethostbyname("localhost")   # succeeds in the StartOS/production container
    return Path("/mnt/main")
except Exception:                        # fails in most local dev environments
    return Path("~/.aubieeternal/main")
```

In production (StartOS/Docker) this resolves to `/mnt/main`, with the git repo checked out at
`/mnt/main/repo`. Locally it falls back to `~/.aubieeternal/main`. When adding new persistent
state, follow this same pattern (or import `DATA_DIR` from `utils/file_io.py`) rather than
hardcoding a path — do not assume `/mnt/main` exists.

`start.sh` (the production entrypoint) re-clones/hard-resets the repo from `origin/main` into
`/mnt/main/repo` on every boot, clears `__pycache__`, launches `swarm/swarm_v4_1.py` as a
background process, then runs `streamlit run app.py` in the foreground on port 80.

## Architecture

The codebase is a **monolith by design** (`app.py` is ~700KB / ~10,600 lines) with logic modules
factored out around it. See `ARCHITECTURE.md` for the full target-state refactor plan
(`pages/`, `logic/`, `components/` split) — treat it as the direction of travel, not the current
state; most of that split has not happened yet. The guiding principle stated there: **stay
deployable as a single app; split for maintainability, not for microservices complexity.**

### Data flow

```
User interaction (Streamlit, app.py)
        ↓
AppState (models/state.py — Pydantic)   ←→   {DATA_DIR}/app_state.json
        ↓
FamilySession (family_hud.py)            →   {DATA_DIR}/session_*.json
        ↓
master_truth_log.jsonl                   →   swarm/swarm_v4_1.py (background, 24/7)
        ↓
tier2_digest.txt                         →   `telemetry` branch (hourly, off-box backup only —
                                              not main, see 2026-09-04/05 notes below)
        ↓
epistemic_commons/api/*.json             →   PUBLIC, CC0, fetchable by any AI/HTTP client
```

**As of 2026-09-04, the swarm no longer stamps `🦅 v4.1 auto-push | Wonder:X | Coherence:Y`
heartbeat commits on `main`** — that pattern (~98% of commits, every ~90s) is now a known-fixed
incident, see below. `main` gets a real commit only when a scheduled job actually publishes
something (`chore(swarm): publish N artifact(s) [...]`) plus one honest `chore(status): rig
alive <date>` pulse per day. If you see the old `🦅` pattern reappear, that's a regression, not
expected behavior.

### Key modules (root-level, imported directly by `app.py`)

- `models/state.py` — Pydantic `AppState`/`FamilyProfile`/`CoherenceState` models; the typed
  replacement for raw `st.session_state` dicts. New state should go here, not into ad hoc
  session_state keys.
- `utils/file_io.py` (and legacy top-level `file_io.py`) — centralized `DATA_DIR`-relative
  paths and JSONL read/write helpers. Route new file I/O through here.
- `family_hud.py` — `FamilySession` and the family-facing lesson/HUD logic (large file).
- `degrees.py` — single source of truth for the 7 degree definitions, credit math
  (`credits_from_xp`), and eligibility rules; `peer_review_system.py` and `transcript_system.py`
  both import from it rather than duplicating requirements (verified by `test_pipeline.py`).
- `steelman_analyzer.py`, `monte_carlo_simulator.py`, `truth_frequency_analyzer.py`,
  `epistemic_drift_detector.py` — the adversarial-testing / reliability stack; steelman
  submissions scoring ≥ B auto-publish to the Epistemic Commons.
- `epistemic_commons_api.py` — generates the 6 public CC0 JSON endpoints under
  `epistemic_commons/api/`.
- `grokipedia.py` — 5-phase Grokipedia pipeline.
- `swarm/swarm_v4_1.py` — the always-on background daughter-swarm process: schedules
  briefings (6AM/12PM/6PM/11PM Eastern — pinned via `zoneinfo`, since the container clock is
  UTC), injects live metrics + recent truth-log + memory-palace context into prompts, enforces a
  $5/day budget, and auto-pushes digest updates to GitHub.
- `ai_model_router.py` — maps UI mode (`Fast`/`Balanced`/`Deep Thinking`) to an Ollama model
  size (`qwen2.5:7b/14b/32b`). AI inference throughout the app targets a local Ollama server
  (`OLLAMA_BASE_URL`, default `http://localhost:11434`) via an OpenAI-compatible client
  (`get_ai_client()` in `app.py`), not a hosted API — this is what makes the app work fully
  offline.
- `rune_memory.py`, `legacy_ledger.py` — Bitcoin-anchored memory/credentialing (degrees are
  gated on Bitcoin "Child Rune" confirmation counts, e.g. the top-tier Eternal Founder degree
  (renamed from "PhD" to "Sovereign Credential" 2026-09-05 — see below) requires 256
  confirmations — see `test_pipeline.py` section 4).
- `api_server.py` / `AUBIEETERNAL_extension/api_server.py` — local FastAPI/Flask server (port
  8502) backing the browser extension (`background.js`, `content.js`, `popup.js`); serves
  localhost only, no external calls.

### Why these design choices (from `ARCHITECTURE.md`)

- **Pydantic over raw dicts**: `state.family.kid.coherence` is guaranteed a float 0-1;
  `st.session_state["kid_coherence"]` is not.
- **CC0, not MIT/Apache**: no license friction for families or AIs consuming the Epistemic
  Commons.
- **Bitcoin anchoring, not just a database**: databases can be silently altered; the 256-
  confirmation Child Rune is a permanent public record used to gate credentials.

### Adding a new Streamlit tab

1. Add the tab name to the relevant nav section dict in `app.py`.
2. Add routing: `if "New Tab Name" in active: ...` (inline, or `from pages.new_tab import
   render; render()` for larger tabs).
3. Prefer extracting genuinely self-contained tabs into `pages/` following the `render()` /
   `if __name__ == "__page__":` pattern already used for `05_Social_Calibration.py`, rather than
   growing `app.py` further.

## Roadmap / planning context (from an Aug 2026 planning conversation)

Forward-looking decisions and planned work. Not yet implemented unless noted — treat as
direction, not current state.

### `/converse` should feel collaborative, not one-shot Q&A

Goal: the `/converse` experience (`assistant_server.py`, endpoint at ~line 1211; persona in
`SYSTEM_PROMPT` at ~line 331) should hold collaborative, tradeoff-weighing conversations —
walk through options step by step, ask clarifying questions, weigh pros/cons — rather than
flat one-shot answers.

1. **Tune the `/converse` system prompt** — ✅ **DONE 2026-08-29.** `SYSTEM_PROMPT` now tells
   Aubie: when someone is working a decision (not a fact lookup), name what the choice turns
   on or ask the one clarifying question first, think out loud one consideration per turn,
   give the recommendation after naming what it depends on, disagree kindly when warranted.
   Reconciled with the "keep it short, spoken aloud" line — depth comes from the back-and-forth
   across turns, not one long answer. Live on `aubie-assistant.service` :8800.
2. **Multi-turn conversation memory** — ⚠️ **server side already exists.** `/converse` →
   `build_context_block()` (~line 642) injects the last `MEMORY_CONTEXT_TURNS = 5` exchanges
   verbatim + a rolling `conversation_summary` (compacted after 20 turns) + durable
   `known_facts`; `remember_exchange()` runs every turn. So the **tablet / `phone_ui.py`
   tap-to-talk path already holds a real back-and-forth.** Still open: the **wake-word client
   `aubie_listen.py`** on the robot (SSH `100.66.110.65`, not in this repo) is single-shot per
   wake word — `capture_and_greet()` → `listen_and_converse()` → `recent_scores.clear()`.
   Make it hold state across multiple wake-word triggers.

### Face recognition & greeting (`assistant_server.py` + `phone_ui.py`) — implemented

- **Live database:** `~/aubie_storage/faces/faces.npz` (`FACES_DIR` in `assistant_server.py`),
  512-d InsightFace `buffalo_l` embeddings, `names`/`vectors`/`sources` arrays. Currently
  `matthew`, `gabriela`. `/known_people` lists them; `/health` reports `faces_loaded`.
- **Recognition:** `scan_faces()` matches every face in a frame (cosine ≥
  `FACE_MATCH_THRESHOLD = 0.5`). `/greet` (camera → "Hello &lt;name&gt;!" via Piper TTS +
  object detection) and `/converse` (when an image is attached) both use it.
- **Enrollment — two paths:** (A) phone UI → **Teach → "🪪 Teach Aubie a Face"** → type name,
  open camera, Snap & Save → `POST /enroll_face` → `append_face_embeddings()` appends to the
  live npz and hot-reloads (no restart). (B) batch: `~/faces/<Name>/*.jpg` (8+), run
  `~/enroll_faces.py .`, copy the output npz into `~/aubie_storage/faces/`, restart the
  service. Enroll names **capitalized** (`Juan`) — the string is spoken verbatim. See
  `~/faces/README.md` on the rig.
- **Per-person behavior ("Princess Mode"):** recognizing `gabriela` triggers a hearts/flowers
  burst — `burstHeartsAndFlowers()` in `phone_ui.py`, on both the `/greet` path
  (`checkForFace`) and, as of 2026-08-29, the camera-conversation path
  (`stopRecordingAndSend`, keyed on the `X-Speaker` header). Robot-side it also best-effort
  fires `flower_explosion` via the Bridge RPC. Text bios the persona reads live in
  `~/AUBIEETERNAL/memory/people/<name>.md` (gabriela/juan/patty/tommy exist).
- This is the standing example of "why our system isn't normal AI": face recognition +
  persistent named identity + person-specific behavior, all local, offline-capable, no
  account.

### `phone_ui.py` is the live UI; root-level copies are stale

`assistant_server.py` does `from phone_ui import router` — the live file is
`~/AUBIEETERNAL/phone_ui.py` (large, ~183 KB). The copies at `~/phone_ui.py`,
`~/phone_ui (1).py`, `~/Phone_ui.py` are old (~40 KB, Aug 23) and used by nothing — don't
edit those.

### Recent debugging notes (2026-08-29)

- **Tablet camera "blocked" is a secure-context problem, not permissions.**
  `getUserMedia` only works over HTTPS or localhost. `http://<LAN or Tailscale
  IP>:8800` is insecure → `navigator.mediaDevices` is `undefined` → `phone_ui.py`
  shows its "CAMERA BLOCKED" banner and never calls the camera. Being in the
  browser's camera-permission allowlist does nothing on insecure HTTP. **Use the
  Tailscale Serve URL `https://aubieeternal.tail00eb41.ts.net/remote`** (already
  running, proxies to `127.0.0.1:8800`, real cert) on tablets — no browser flags.
- **Mic-button 500** reported after an alleged face-icon cleanup: investigated on
  the rig, did NOT reproduce. `/converse` returns 200 for audio-only, audio+image,
  and canned commands with the robot offline; no icon/asset deletions in `git log
  --diff-filter=D`; all Piper voices present. If the 500 is real it's on the
  offline aubie-tutor board's own copy, or was fixed by a service restart.
- **`build` (:8840, `~/.local/bin/build`) now defaults to local `qwen-14b`.** It
  works for surgical edits but only when the prompt gives the **exact absolute
  path + exact old/new strings + exact tool name** — 14b otherwise fabricates
  placeholder paths. Not yet reliable for open-ended multi-step diagnosis.
- **`askqwen`** (`~/.local/bin/askqwen` → `tools/askqwen`): ask local Qwen a
  codebase question with current file contents auto-injected. `askqwen -l` lists
  the file set; edit the `FILES` list in the script to change it.

### Recent debugging notes (2026-09-04 / 2026-09-05)

One long session: a QR-scanning safety feature, a swarm runaway incident and its
fallout, and a repo-wide degree-language cleanup. All commits below are on `main`.

- **QR Airlock v0.1** (`e2ba9e5a`, `81c87582`) — `tools/qr_airlock/`: household-local
  QR decode → sha256 → verdict (never opens the link, never returns a bare "safe"),
  `/qr/check` `/qr/allow` `/qr/share` mounted on `assistant_server.py`, a phone_ui
  "Scan QR" tab. Follow-up patch made pyzbar the primary decoder (cv2 fallback) and
  moved `_explain_via_qwen()` to `qwen2.5:7b`/15s timeout so a scan can't stall
  waiting on the model.
- **Portal reachable over Tailscale** (`4ecff902`) — serving `/portal` as a Tailscale
  Serve *path* silently blanked the Streamlit UI (Serve strips the path prefix
  before forwarding, which conflicts with Streamlit's own `baseUrlPath`). Fixed by
  giving Streamlit its own port at root instead —
  `https://aubieeternal.tail00eb41.ts.net:8443/` — no `baseUrlPath` needed.
- **Swarm heartbeat stopped burying real commits** (`9111a3ce`) — see the data-flow
  note above. New `ERROR_LEDGER.md` at repo root is now the project's public "found
  X, broke this way, changed Y, verified how" record — check it before assuming a
  weird commit pattern is new.
- **Degree/PhD language cleanup** (`cc63eb06`) — "PhD"/"degree" → "Sovereign
  Credential" for the top-tier Eternal Founder degree across `degrees.py` (the
  single source of truth), `AUBIEETERNAL_School_Charter.md`, `README.md`,
  `family_hud.py`, `phone_ui.py`; `RELEASE_NOTES_v69_UNIVERSITY.md` renamed to
  `RELEASE_NOTES_v69.md`. **Flagged but deliberately not touched:**
  `family_hud.py`'s `"capstone-phd"` dict key (machine identifier — a rename needs a
  wider usage search first) and its lesson `example` field; `phone_ui.py:2880`'s
  generic "PhD student" (describes an external demographic, not our own
  credential); `app.py:9845` (`"PhD" in name` string check driving a UI color) and
  `app.py:9642` (a separate, already-drifted hardcoded tier-name dict, unrelated to
  `degrees.py`) — both silently stopped matching once `degrees.py`'s name changed.
- **13h46m unattended swarm runaway** (`ea586f83`) — `check_wonder_trigger()` was a
  bare `wonder_index >= 1.4` level check with no edge-detection, firing on nearly
  every ~30s heartbeat tick for as long as the index stayed elevated — which was
  almost always, since Tier-2's own output vocabulary is exactly what
  `update_wonder_index()` scores as "awe," feeding the index right back up. Real
  numbers from the incident: 501 Tier-2 pulses, 38,792 `HORMETIC`-tagged log lines
  in one night, `wonder_index >= 1.4` on 99.3% of that day's ticks. Fixed with
  hysteresis (fire only on the upward crossing through 1.4, re-arm only below 1.2)
  plus a `TIER2_HOURLY_CAP = 6` backstop independent of trigger type. This is the
  first entry in `ERROR_LEDGER.md`'s "Incidents" section — a concrete, confirmed
  (not hypothetical) instance of the drift the Bitcoin-minting swarm's
  human-approval-before-broadcast gate exists to guard against.
- **Telemetry branch push had been silently failing since Sept 1** (`032f3b80`) —
  root cause: `master_truth_log.jsonl` hit 152MB (inflated by the incident above)
  and GitHub hard-rejects any push containing a blob over 100MB. Its entire
  on-disk history was only ~11.5 days old, so its own 30-day rotation window had
  correctly found nothing old enough to trim yet — a pure age-based cap can't
  protect against one high-volume day, however short the window. Added an 80MB
  size cap to all four `LOG_ROTATION` entries (not just the one that broke), plus
  skip-and-log for any single oversized `TELEMETRY_FILES` entry so it can't block
  the whole push again. One-time corrective trim already run (152MB → 83.9MB);
  first successful telemetry push since Sept 1 confirmed live afterward.
- **`self_audit.py` gained swarm-behavior monitoring** (`930a3166`, `fe709a1e`) — it
  previously only checked whether the `aubie-swarm` *process* was alive, with zero
  visibility into what it was actually producing, which is why none of the above
  tripped it. Now 9 more checks: 4 runaway signals (`wonder_index` pinned ≥1.9 for
  an hour, swarm log volume, `HORMETIC PULSE`/`WONDER SPIKE` >2/hr, 3 consecutive
  telemetry-push failures) plus 5 stale-scheduled-output checks, one per daily
  trigger (`morning_synthesis`, `email_watch`, `epistemic_commons`,
  `curriculum_autogen`, `living_lattice`) — each reads that trigger's own on-disk
  evidence (a dated file's mtime, or a `last_run_date` field) rather than the
  swarm's own logs/state, so it stays a true outside observer. All 9 bypass the
  normal 3-of-16 `lessons.md` recurrence gate and email via the local Proton
  Bridge SMTP (`127.0.0.1:1025`, same account `email_watch.py` reads) on first
  detection, not after 45 minutes of confirmation.
- **`swarm/swarm_v4_1.py` couldn't see its own repo-root sibling modules**
  (`dc945427`) — it lives in `swarm/`, and `python -u swarm/swarm_v4_1.py` puts the
  *script's own directory* on `sys.path[0]`, not the repo root (`WorkingDirectory`
  sets cwd, not `sys.path`). Its 7 lazy `from X import Y` triggers
  (`morning_synthesis`, `curriculum_autogen`, `email_watch` x2, `epistemic_commons`,
  `epistemic_commons_api`, `living_lattice`) had all been silently raising
  `ModuleNotFoundError` — mislabeled "not found in repo" by each site's broad
  `except ImportError` — since their call sites were wired in around 2026-08-25:
  ~11 days of every scheduled trigger quietly no-op'ing while self_audit reported
  all-green. Fixed with one `sys.path.insert(0, str(WORK_DIR))` right after
  `WORK_DIR` is computed. This is also the exact failure class the new stale-output
  self_audit checks above exist to catch if something like it ever recurs.
- **Housekeeping, same session, unrelated to the above:** `push_audio_to_aubie()`
  in `assistant_server.py` (`132cd8b0`) now serializes overlapping
  `/greet`-triggered calls with a `threading.Lock`, so the UNO Q board's `aplay`
  can't be asked to open the ALSA device twice concurrently. **Written and reasoned
  through, not yet verified against real hardware — the board was offline the
  entire session.** Once it reconnects: trigger `/greet` twice within ~1s and
  confirm no "Device or resource busy" and that the second greeting still plays
  (delayed, not dropped).

**Still open, not done this session:** `family_hud.py`'s `"capstone-phd"` dict key
rename (deferred, needs a usage search first); `app.py:9845` / `app.py:9642`
hardcoded "PhD" strings (flagged, not fixed); the ALSA lock fix above, pending
real-hardware verification; two untracked `insights/probe/*.json`/`.md` files
per run (a `simulation_probe` sub-step of `morning_synthesis`) that aren't in the
swarm's `github_push_truth_log()` sweep list the way `insights/daily/` is —
minor, not investigated further this session.

## Edge devices are disposable — the rig + git is the source of truth

**Principle:** every edge device (the UNO Q tutor board, kiosk/dev tablets, any
robot) is replaceable. The permanent copy of every file lives in this git repo on
the Ryzen rig. If a device is lost/wiped, the fix must be "re-flash from git,"
never "hope we can pull it off the device." **When writing code that would only
live on a device, stop and flag it** — add it to `tools/pull-board-files` or get
it into the repo immediately; don't let it become a single-point-of-failure to be
discovered later. (This rule exists because `aubie_listen.py`'s real version —
`/converse`, `idle_scan_loop`, the audio-device fix, `CAMERA_LOCK`/`WAKE_BUSY` —
lived *only* on the offline board for ~2 weeks, 2026-08.)

**Auto-sync:** `tools/pull-board-files` (→ `~/.local/bin/pull-board-files`) scp's
the board-only paths into `_remote/board/` and `--commit`s any changes. A crontab
line runs it every 20 min; it no-ops + logs to `_remote/sync.log` when the board
is unreachable. `pull-board-files --discover` lists `*.py/*.sh/*.html/*.ino` under
`~` on the board to catch anything new.

### Edge-only file audit (2026-08-29)

**UNO Q tutor board `100.66.110.65` — none of these are in git yet; board was
unreachable at audit time, so `pull-board-files` will capture them on reconnect:**

| Path on board | What it is |
|---|---|
| `~/aubie_listen.py` | wake word + `/converse` + `idle_scan_loop` + `CAMERA_LOCK`/`WAKE_BUSY` guards + `pw-play` audio fix. Only floor is a July-26 pre-kiosk prototype at `_remote/board/aubie_listen.py.2026-07-26-prototype`. |
| `~/kiosk/home.html` | kiosk home screen: ported `FACE_PRESETS`/accessories + net-new draw-your-own-face canvas, Glasses/Hat/scene toggles, `celebrateGabriela()` |
| `~/kiosk/launch_kiosk.sh` | Chromium `--kiosk` autostart + `wpctl` HDMI audio profile/volume fix + `xset s off`/`-dpms` |
| `~/.config/autostart/aubie-kiosk.desktop` | kiosk autostart entry |
| `~/.config/autostart/light-locker.desktop` | `Hidden=true` screen-lock suppression |
| `~/aubie-tutor/sketch/sketch.ino` + `sketch.yaml` | tutor MCU sketch: PCA9685 driver ported from the retired `spotmicro_dog` sketch + `wave()`/`wave_diag()`/`hub_diag()` RPCs; yaml carries the full dog library list |
| `/etc/lightdm/lightdm.conf` | `autologin-user=arduino` under `[Seat:*]` — root-owned, **can't scp**, documented here only. Re-add this one line by hand on a re-flash. |
| board's own `phone_ui.py` / `assistant_server.py` (if any) | unknown whether the board runs its own copies with kiosk-only edits; `pull-board-files` pulls them into `_remote/board/` for diffing against the tracked versions |

**Windows tablet `desktop-q9mrd24` — NOT a code SPOF.** Thin client: a browser
pointed at `https://aubieeternal.tail00eb41.ts.net/remote`. The `install_windows.bat`
fixes (OneDrive Desktop-path resolution, Ollama auto-install) are already in the
repo. Only device-local state is a bookmark / kiosk-mode autostart — trivial,
recreate by hand.

**Robot / spotmicro dog — covered.** `spotmicro_dog/` is in the repo;
`spotmicro_dog_robot_backup_20260821/` is a full backup. Retired in favor of the
tutor kit anyway.

### Inference hardware: 32B now, not 70B

Decided against Qwen 70B (needs ~45-55 GB VRAM for 2-3 concurrent users → dual-GPU, $3-4K+,
more complexity).

- **Plan: add a single RTX 3090 (24 GB) to the existing Ryzen rig** to run Qwen 32B (Q4,
  ~20 GB VRAM) — comfortable for 1-2 concurrent users, workable for a small pilot. GPU upgrade,
  not a rebuild — keep case/PSU/CPU/RAM.
- The Ryzen rig stays home as the always-on inference brain. Do **not** donate it — rebuilding
  a brain elsewhere costs more and loses the already-debugged systemd/venv setup.
- Before spending money: `ollama pull qwen2.5:32b` alongside the existing `qwen2.5:14b` and
  compare responses side by side on real pilot-style questions. (`ai_model_router.py` already
  maps `Fast`/`Balanced`/`Deep Thinking` → `qwen2.5:7b/14b/32b`.)

### Pilot: library (2 blocks away) via donated tablets, not new hardware

Decided against a mini-PC/monitor/camera thin-client build.

- **Donate 2-3 budget tablets (~$80-150 each)** to the library. Built-in
  mic/camera/speaker/screen; run Tailscale (Android/iOS apps) to reach the same Ryzen rig
  brain — same split-brain architecture as the Aubie Dog robot and the Windows dev tablet,
  just a simpler front end.
- **Build item:** a lightweight web page / PWA with a "talk to Aubie" button (browser mic
  access) that hits the existing `/greet` and `/converse` endpoints on `assistant_server.py`.
  No new backend logic — this is a frontend only.
- Architecture throughline for grant writeups: **one inference brain, multiple lightweight
  access points** — home dev tablet (SSH), library kiosk tablets (web app), Aubie robot
  (wake-word edge client), all hitting the same rig.
- Open question for the library: tablets fixed at a public terminal on library WiFi (simpler)
  vs. checked out / roaming to patrons.

### Boy Scouts partnership (across from the library) — separate site

- Better fit for the **Aubie Dog robot** (robotics / AI merit badge alignment) than a generic
  tablet/chat deployment. See `AUBIE_DOG.md`.
- Treat as a separate pilot site, not a shared-WiFi bridge with the library — a
  directional/bridge WiFi link is impractical (line-of-sight antenna gear, liability sharing
  the library's connection). Each site gets its own internet + its own Tailscale client.

### Curriculum content area: ICS / critical-infrastructure security

- Fits AUBIEETERNAL as a **curriculum/education topic**, not a pivot into security services
  (mixing for-profit security consulting risks 501(c)(3) mission alignment).
- Ties to current events (CISA water-sector guidance, White House water-infrastructure
  cybersecurity program) and a genuine workforce gap — good language for future
  EducateAI-style workforce-pipeline grants.
- A separate personal learning track (general, non-water ICS security via CISA free training /
  GICSP path) is kept **outside** the nonprofit entity.

### Budget framing (if ~$10K grant/donation money), in priority order

1. Nonprofit compliance — Articles of Amendment + 1023-EZ filing (~$500-1,000)
2. RTX 3090 upgrade for the existing Ryzen rig (~$800-1,200)
3. Library tablets (~$250-450)
4. Reserve for unplanned costs (~$1,000+)
5. Remainder → a second pilot site (e.g. Boy Scouts) or contingency

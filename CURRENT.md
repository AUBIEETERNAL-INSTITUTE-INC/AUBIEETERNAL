# CURRENT.md

Updated: 2026-09-05

The only file that ages. Grok chat, Grok Build, and Claude Code read this first.

## Identity

- Owner: AUBIEETERNAL-INSTITUTE-INC/AUBIEETERNAL (org, not a one-person repo)
- Personal GitHub: hodlmateo — never search `user:holdmateo` or `user:MateoVanhorn`
- Pages: aubieeternal-institute.org

## Last Grok Build code landing

2026-08-25 commit `5af39b82` — “Add Build Code to Sandbox Lab”.
Reuses `handle_build_code_request()` from `aubieeternal_build_code.py`.
`call_claude` / `call_grok_build` in `epistemic_orchestrator.py` are stale names; they hit local Ollama `qwen2.5:14b` / `7b`, $0/day.

## Operating docs (do not refresh as a side effect of this file)

- Axioms: `grok-principles.md` (last content pass 2026-05-20)
- Agent briefing already in repo: `CLAUDE.md` (notes through 2026-08-29)

## 2026-09-05 follow-up pass

Credential UI now reads `degrees.py` directly (no more `"PhD" in name`
string checks); `capstone-phd` renamed to `capstone-eternal-founder` with a
back-compat alias; `wonder_index` now decays over real elapsed time so its
hysteresis can re-arm without a restart; `insights/probe/` added to the
truth-log push sweep. Landed as `a549f0dc`, `df68baa9`, `9e4ad5ee`,
`87f74db6`. ALSA lock fix (`132cd8b0`) is still unverified — see
`ERROR_LEDGER.md`.

## 2026-09-05 evening — travel QR trust + anomaly_guard first pass

- `phone_ui.py` Scan QR tab: a "PIPE" trust strip (green only when the page
  is genuinely the tailnet host over HTTPS or localhost — exact hostname
  match + leading-dot suffix, not a bare substring), blocks "Go Live" when
  UNTRUSTED, logs failed checks to `memory/pipe_trust.log` (gitignored).
  Plus a static travel-runbook card and `WIFI:` QR parsing in `qr_airlock`
  (display-only: SSID + open/encrypted wording, never joined, never a
  safe/unsafe verdict).
- `anomaly_guard.py` (repo root): tick labeler + `max_spike_run` /
  `ritual_hits` hard rules, wired into `self_audit.py`. **First pass only —
  the Markov matrix + Isolation Forest are deferred** pending a few real
  weeks of clean post-fix data. `python3 anomaly_guard.py --replay` passes
  4 cases. See `ERROR_LEDGER.md`.
- All of the above is **landed in the working tree, not committed** — Mateo
  reviews the diffs and commits; then `sudo systemctl restart aubie-swarm`
  / assistant restart as needed.

## Still current (2026-08-29)

- `/converse` prompt is collaborative
- Live UI is repo-root `phone_ui.py`
- Tablet camera needs HTTPS Tailscale Serve
- Edge devices are disposable
- `pull-board-files`
- UNO Q board still has files not in git (`aubie_listen.py`, kiosk, tutor `.ino`)

## Next physical node (conversation only, 2026-08-31 — not in the tree)

Teacher Box v0.1 / first student robotics station.

Hardware in one 3D-printed enclosure for ELEGOO Centauri Carbon 2 + Elegoo Slicer:

- UGREEN Revodok Pro USB-C hub (spine)
- EMEET C960 1080P webcam
- Hosyond 7" IPS touch
- Arduino UNO Q 4GB

Spec + OpenSCAD were drafted in Grok chat, not pushed. When those files land they belong under something like `hardware/teacher_box/` — do not invent them here.

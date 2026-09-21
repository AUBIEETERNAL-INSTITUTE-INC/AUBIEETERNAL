# CURRENT.md

### IT-support model — knowledge + tools (2026-09-21)

Open WebUI model `vanhorn-org--aubieeternal-it-support` (qwen2.5:14b) now has:
- Knowledge: "AUBIEETERNAL Error Ledger" collection (ERROR_LEDGER.md +
  aubie-error-ledger.md). Attach the COLLECTION, not individual files.
- Tools: "Rig Diagnostics" — read-only. service_status, ollama_health,
  assistant_health, tailscale_status, recent_logs, gpu_and_disk.
  subprocess with arg lists, no shell, unit allow-list. Nothing can start/stop/restart.
- System prompt starts with "Always respond in English." (qwen2.5 drifts to other
  languages when narrating tool calls). `/no_think` is a Qwen3 directive, inert here.

Verified: names real services and the live model list instead of guessing.
CAVEAT: it garbles code when paraphrasing from the ledger (dropped the <|im_start|>
tokens from the TEMPLATE fix, invented `ollama info`). Trust its diagnosis, open the
ledger for the exact commands.

Done: extra_checks.py (control chars, EIN-shaped digits, personal names).
Run after validate_steelman.py.

## Aubie model — 2026-09-21

NOW: `aubie` = r10, temp 0.45. Modelfile has explicit TEMPLATE, no stop strings.
3/58 structure failures. Services: ollama, aubie-swarm, aubie-assistant + 5 others active.

ROOT CAUSE FOUND (r9→r10): training_data_r9.jsonl held 157 records but only ~41
taught the steelman form. The rest were vision records, follow-up JSON, markdown
org-identity records (incl. EINs and names) from other features. 26 good answers
also carried a leading preamble paragraph — the model learned it from there.
filter_r10.py strips preambles and drops off-task records: 157 → 100 clean.

NEXT: 35 claims in review_queue.txt need the fact pass.

DO NOT: put vision / follow-up / org-identity records back in the teaching set.
Org facts belong to the assistant and IT-support models, not Aubie.

Updated: 2026-09-21

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

## 2026-09-18 — weekend lane

HEAD `031f5e86` is in sync with `origin/main`. Untracked local junk
(curriculum-proposals, jsonl, wav, grokipedia/, `phone_ui.pyscp`) stays
untracked — do not `git add` it.

Claude Code is dark until Sun 2026-09-20 23:00. Weekend work is Grok
chat (ideas) + Grok Build on this checkout. Do not edit Python until
Mateo says so.

assistant_server / Open WebUI / InsightFace face-rec (matthew, gabriela)
is already on `main`, not new this weekend:

- `assistant_server.py` + `/enroll_face` since `015b8840` (2026-08-14)
- enrolled embeddings live on the rig at `~/aubie_storage/faces/faces.npz`
  (not in git)
- mid-September refinement already landed as `a89553d7` (2026-09-16):
  Open WebUI `/v1/chat/completions` wrapper, face-threshold revert to
  0.5, `organize_photos.py`. `aubie-webui.service` is a rig systemd
  unit, not a repo file.

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
- That evening's tree later landed on `main` (`234b59df`, `05d8c42d`,
  `5eb5dcc7`, `d35bea68`).

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

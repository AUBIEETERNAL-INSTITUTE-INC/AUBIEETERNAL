# CURRENT.md

Updated: 2026-08-31

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

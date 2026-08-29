# RYZEN_RIG.md — ground truth for the inference brain

Snapshot of what the Ryzen rig **actually is right now** (2026-08-28), so the
claude.ai planning thread and Claude Code on the box are working from the same
facts. Pair this with `CLAUDE.md` (repo/architecture) and `AUBIE_DOG.md` (robot).

## TL;DR for planners

- The rig's GPU today is an **RTX 3060 12 GB**, *not* a 3090. The "add an RTX 3090"
  line in the plan is still a future purchase, not a done thing.
- Models pulled in Ollama: `qwen2.5vl:7b` (the VLM), `qwen2.5:14b` (text daily
  driver), `qwen2.5:7b` (fast). **`qwen2.5:32b` is NOT installed yet.**
- `ai_model_router.py` already *names* `qwen2.5:32b` for `heavy`/`synthesis`
  tasks, so any "Deep Thinking" / morning-synthesis path currently asks Ollama for
  a model that isn't there — it errors or silently degrades. Pulling 32B on the
  current 3060 will run, but mostly on CPU (12 GB VRAM < ~20 GB for 32B Q4), so
  it'll be slow. The 3090 upgrade is what makes 32B actually usable.

## Hardware

| Part | Current |
|------|---------|
| GPU  | NVIDIA GeForce RTX 3060, 12 GB VRAM (~5.5 GB in use with models resident) |
| Role | Always-on local inference brain; stays home, not donated |
| Net  | Reachable to other sites over Tailscale (same pattern as Aubie Dog robot + Windows dev tablet) |

Planned: swap in a single **RTX 3090 (24 GB)** — GPU-only upgrade, keep
case/PSU/CPU/RAM — to run Qwen 32B (Q4, ~20 GB) for 1-2 concurrent users.

## Models (Ollama, `http://127.0.0.1:11434`)

| Model | Size | What uses it |
|-------|------|--------------|
| `qwen2.5vl:7b` | 6.0 GB | **The VLM.** `assistant_server.py`: `/greet` object detection, `/vision_describe`, mood read. ~15 s per call — follow-up `/converse` turns deliberately skip it. Set as `VISION_MODEL` at `assistant_server.py:62`. |
| `qwen2.5:14b` | 9.0 GB | Text daily driver. `ai_model_router.py` `default` / UI "Balanced". Also the code-writing agent (`aubieeternal_build_code.py`). |
| `qwen2.5:7b`  | 4.7 GB | Fast / casual chat. UI "Fast". |
| `qwen2.5:32b` | — | **Not pulled.** Referenced by `ai_model_router.py` as `heavy` + `synthesis`. Pull it and A/B against 14b on real pilot questions *before* buying the 3090. |

Non-LLM vision path: `vision_extras.py` (mounted into `assistant_server.py` as
`/vision/*`) — YOLO (ultralytics) + MediaPipe + pyzbar + easyocr for fast
label/color/QR/OCR on the 3060. Separate from the VLM.

## "What VLM are we running?"

**Qwen2.5-VL 7B** (`qwen2.5vl:7b`), served locally by Ollama. It is the only
vision-language model in the stack. Everything visual that needs *language* (scene
description, "what am I looking at", mood reads) goes through it; anything that
just needs *labels/geometry* goes through the YOLO/MediaPipe path in
`vision_extras.py`.

## Services (systemd, this host)

All running as of this snapshot:

- `aubie-portal.service` — `streamlit run app.py`, the family portal (:8501)
- `aubie-assistant.service` — `uvicorn assistant_server:app` (:8800); backs the
  tablet UI and the robot. Owns `/greet`, `/converse`, face-ID (InsightFace, CPU),
  Piper TTS, and the VLM calls. `phone_ui.py`'s router is imported into this
  process, not run separately.
- `aubie-swarm.service` — `swarm/swarm_v4_1.py`, always-on background swarm;
  daily briefings, curriculum autogen, the single GitHub auto-push path.
- `aubie-extension-api.service` (:8502) — browser-extension API
- `aubie-mcp.service` — Aubie MCP server (HTTP/SSE)
- `aubie-webui.service` — Open WebUI
- `aubie-build.service` — Grok Build web UI
- `aubie-proton-bridge.service` — local IMAP/SMTP for the email feature
- `ollama.service` — model server

## `/converse` and `/greet` (the endpoints the pilot web app will hit)

- Both live in `assistant_server.py` (:8800). `/converse` at ~line 1211, `/greet`
  at ~line 1395, persona `SYSTEM_PROMPT` at ~line 331.
- `/greet` runs the VLM once at wake time (who's in the room, what's visible);
  `/converse` follow-up turns reuse that context and skip the VLM for latency.
- The planned library-tablet PWA is **frontend only** — a "talk to Aubie" button
  (browser mic) posting to these existing endpoints over Tailscale. No new backend.

## Wake-word client / `aubie_listen.py`

Not in this repo — it lives on the robot / kiosk side (UNO Q). Today it's
single-shot per wake word: `capture_and_greet()` → `listen_and_converse()` →
`recent_scores.clear()`. Planned: multi-turn memory so Aubie holds a back-and-forth
across several wake triggers. Kiosk/`aubie_listen.py` history is documented in the
`aubieeternal_stationary_tutor_kit` memory.

## Planned work (see CLAUDE.md "Roadmap / planning context" for detail)

1. Tune `SYSTEM_PROMPT` so `/converse` reasons through tradeoffs and asks
   clarifying questions instead of one-shot answering.
2. Multi-turn memory in `aubie_listen.py`.
3. Pull `qwen2.5:32b`, A/B vs 14b, then buy the RTX 3090 if it's worth it.
4. Library pilot: 2-3 donated tablets + a "talk to Aubie" PWA on Tailscale.
5. Boy Scouts: separate site, Aubie Dog robot, its own internet (no WiFi bridge).
6. ICS/critical-infrastructure security as a **curriculum topic**, not a product.

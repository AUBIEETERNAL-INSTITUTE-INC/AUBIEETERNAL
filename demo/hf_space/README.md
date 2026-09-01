---
title: AUBIEETERNAL Demo
emoji: 🦅
colorFrom: blue
colorTo: indigo
sdk: gradio
app_file: app.py
pinned: false
license: cc0-1.0
short_description: Lightweight public demo of the AUBIEETERNAL AI tutor
---

# AUBIEETERNAL — public demo

A shareable, always-on demo of the AUBIEETERNAL `/converse` tutoring
experience. It runs entirely on Hugging Face infrastructure and does **not**
depend on the home inference rig or a Tailscale connection.

**What it is:** a small hosted model (`Qwen/Qwen2.5-7B-Instruct` by default)
prompted to match the real product's teaching style — Socratic, hint before
answer, name what a decision hinges on, one follow-up question per turn.
English and Spanish.

**What it is not:** the full AUBIEETERNAL system runs locally on donated
hardware, works offline, and remembers every lesson, question, and
conversation. This demo is stateless — no memory between sessions, no face
recognition, no progress tracking.

## Configuration

Space → **Settings → Variables and secrets**:

| Key | Kind | Default | Notes |
|---|---|---|---|
| `HF_TOKEN` | secret | — | A **read** token. Strongly recommended; without a valid token the Inference API calls will fail. |
| `MODEL_ID` | variable | `Qwen/Qwen2.5-7B-Instruct` | Any chat model available through the Inference API. Keep it in the Qwen2.5 family to stay close to the rig's tone. |
| `HF_PROVIDER` | variable | _(unset)_ | Set to `hf-inference` to force serverless HF inference if the default routing picks an unavailable provider. |

## Local run

```bash
pip install -r requirements.txt
export HF_TOKEN=hf_...        # a read token
python app.py
```

## Deploy

See [`DEPLOY.md`](./DEPLOY.md).

# Deploying the AUBIEETERNAL public demo to Hugging Face Spaces

Account: **Aubieeternal** (https://huggingface.co/Aubieeternal). Suggested
Space name: `aubieeternal-demo` → URL `https://huggingface.co/spaces/Aubieeternal/aubieeternal-demo`.

## 1. Create the Space

- https://huggingface.co/new-space
- Owner: `Aubieeternal` · Name: `aubieeternal-demo`
- SDK: **Gradio** · Hardware: **CPU basic (free)** · Visibility: **Public**

Or with the CLI:

```bash
pip install -U huggingface_hub
huggingface-cli login          # paste a write token
huggingface-cli repo create aubieeternal-demo --type space --space_sdk gradio
```

## 2. Push these files

Only the contents of `demo/hf_space/` go to the Space (not the whole repo):

```bash
cd demo/hf_space
git init
git remote add space https://huggingface.co/spaces/Aubieeternal/aubieeternal-demo
git add app.py requirements.txt README.md DEPLOY.md
git commit -m "AUBIEETERNAL public demo"
git branch -M main
git push space main
```

If the Space was created with an initial commit, `git pull space main --rebase`
first (or `git push -f space main` the very first time).

## 3. Configure secrets

Space → **Settings → Variables and secrets**:

- `HF_TOKEN` (secret) — a **read** token from
  https://huggingface.co/settings/tokens . Required for the Inference API.
- `MODEL_ID` (variable, optional) — defaults to `Qwen/Qwen2.5-7B-Instruct`.
- `HF_PROVIDER` (variable, optional) — set to `hf-inference` if replies error
  out with a provider/availability message.

The Space rebuilds and is live in ~1–2 minutes. Share the URL for library
pilot outreach and job applications.

## Notes

- **Design choice: Option A (standalone).** The demo intentionally does *not*
  proxy to the home rig — the whole point is that it works when the rig is
  off. It mirrors the persona from `assistant_server.py` (`SYSTEM_PROMPT`),
  trimmed to text-only.
- **Cost:** CPU-basic Spaces are free; Inference API usage for a 7B model is
  within the free tier for demo-level traffic. If it sleeps after inactivity,
  the first request wakes it (~30s).
- If serverless hosting for the default model is ever withdrawn, change
  `MODEL_ID` to another hosted instruct model (e.g.
  `meta-llama/Llama-3.2-3B-Instruct`, `mistralai/Mistral-7B-Instruct-v0.3`).

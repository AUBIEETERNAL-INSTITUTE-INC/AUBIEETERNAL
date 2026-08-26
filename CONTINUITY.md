# CONTINUITY.md — keeping AUBIEETERNAL alive without any one person

This file is for whoever keeps the project running if the current maintainer
steps back or is gone. It is deliberately blunt about single points of
failure. Last reviewed: 2026-08-26.

---

## 1. What has to survive

AUBIEETERNAL is designed so **every download is a complete, self-sufficient
school** — it runs offline, and anyone can grow their own curriculum locally
with no dependency on the original maintainer, repo, or internet.

What does **not** survive on its own today is **collective growth**: lessons
one family writes reaching every other install. That flows through one
GitHub repo, and that repo is currently tied to one person.

---

## 2. The single points of failure (fix these first)

| Thing | Current state | Risk | Fix |
|---|---|---|---|
| **GitHub repo** | `github.com/hodlmateo/AUBIEETERNAL` — a **personal** account | If that account is lost, the repo and its history can go with it | Move it to a **GitHub Organization** (e.g. under the Institute). Orgs outlive individuals. |
| **Who can push** | One deploy key on one machine (the "Ryzen rig", hostname `aubieeternal`), plus the owner's login | If the rig dies or the owner is gone, `main` freezes forever | Add **2+ people as org owners/maintainers** with push + admin. |
| **The swarm auto-push** | Runs only on the Ryzen rig as `aubie-swarm.service` | Dies with that machine | Document the setup (below) so a successor can re-point it from any Linux box. |
| **Contribution back** | No path for an outside install to get a lesson into the shared feed without repo write access | Growth is bottlenecked on the maintainer | Build a submission path (GitHub Issues/PRs from the app) OR federated per-instance feeds. |

**Priority order:** (1) move repo to an org, (2) add maintainers, (3) write
down the rig setup, (4) build the contribution path.

---

## 3. How the curriculum commons works (the growth loop)

All of this machinery already exists and works, as long as *someone* can
push to the repo:

1. **Anyone, on any install, offline:** Streamlit app → **Submit Curriculum**
   tab → submit a lesson or track (or "🤖 Ask Aubie to propose one now", or
   wait for the swarm's daily 9 AM proposal). Everything lands as **pending**.
2. **A human approves** it in the Review Queue → `merge_approved_proposal()`
   folds it into `curriculum_extra.json` (in the local data dir) →
   `curriculum.py` teaches it immediately, no restart. *This is local to that
   install.*
3. **Publish to Commons** (separate, explicit button in the Approved tab) →
   writes the lesson into `epistemic_commons/api/curriculum_proposals.json`
   in the repo working tree.
4. **The swarm's GitHub auto-push** (`swarm/swarm_v4_1.py` →
   `github_push_truth_log()`) commits that file to `main` within minutes.
5. **Every other install** → **⬇️ Pull from Commons** → fetches
   `https://raw.githubusercontent.com/<org>/AUBIEETERNAL/main/epistemic_commons/api/curriculum_proposals.json`
   → the lessons arrive as **pending** for that install's human to review.

Double-gated on purpose: your choice to publish, their choice to adopt.
Nothing propagates automatically.

If the repo moves to an org, update `COMMONS_FEED_URL` in
`curriculum_proposals.py` and `PUBLIC_BASE` in `epistemic_commons_api.py`
(both currently hardcode `hodlmateo/AUBIEETERNAL`).

---

## 4. The Ryzen rig (`aubieeternal`) — what runs where

Repo checkout: `/home/aubieeternal/AUBIEETERNAL` (also reachable as
`/mnt/main/repo`, a symlink).

systemd services (all `Restart=always`, run as user `aubieeternal`):

| Service | What |
|---|---|
| `aubie-assistant.service` | FastAPI/Uvicorn — `assistant_server.py`, hosts `/converse`, `/greet`, and imports `phone_ui.py`'s `/remote` UI |
| `aubie-portal.service` | Streamlit app (`app.py`) — the main portal, port 8501 |
| `aubie-swarm.service` | `swarm/swarm_v4_1.py` — 24/7 background swarm: daily curriculum proposal, briefings, GitHub auto-push, log rotation |
| `aubie-extension-api.service` | Browser-extension backend, port 8502 |
| `aubie-mcp.service` | MCP server (HTTP/SSE) |
| `aubie-webui.service` | Open WebUI |
| `aubie-proton-bridge.service` | Local IMAP/SMTP for the email feature |

**GitHub push auth:** SSH deploy key at
`~/.ssh/aubieeternal_github_deploy_key` (+ a `Host github.com` entry in
`~/.ssh/config`), registered as a **write** deploy key on the repo. Verify
with `ssh -T git@github.com`.

**Branches:**
- `main` — code, curriculum, Epistemic Commons. This is what downloads and
  other instances use.
- `telemetry` — the swarm's rolling operational logs (`master_truth_log.jsonl`
  etc.), snapshotted hourly as off-box backup. Nobody downloads this. Safe to
  delete and let the swarm re-seed if it ever gets unwieldy.

To move the swarm to another machine: clone the repo there, put a write
deploy key on it, run `swarm/swarm_v4_1.py` under an equivalent systemd unit,
and stop it on the old machine (two pushers race over the same branch).

---

## 5. License

MIT / CC0 (Epistemic Commons). Anyone may legally fork the last public state
of `main` and continue the project. That is the ultimate backstop — but it
fragments the community, so the fixes in section 2 are the real plan.

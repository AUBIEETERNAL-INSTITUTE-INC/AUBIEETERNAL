# aubieeternal Build

Grok Build, on this Ryzen rig. Same job: read the tree, edit files, run
commands, ship the work — branded as **aubieeternal Build**.

## Open it

Web UI (always-on once the service is installed):

- Local: [http://127.0.0.1:8840](http://127.0.0.1:8840)
- Tailscale: [http://100.105.81.27:8840](http://100.105.81.27:8840)

TUI, from any terminal on this box:

```bash
build
```

That is `grok --agent aubieeternal-build`. Pass a prompt or `--cwd` the same
way you would with `grok`.

```bash
build --web          # print / open the web UI
build --dashboard    # agent dashboard
build "fix the gait"
```

## Models

- **Grok 4.6** (default, cloud — needs the existing grok.com login)
- **Grok 4.5**
- **Qwen 2.5 14B / 7B** — local Ollama on this machine, works offline

## Files

| Path | Role |
|---|---|
| `server.py` / `index.html` | Web UI |
| `~/.local/bin/build` | TUI launcher |
| `~/.grok/agents/aubieeternal-build.md` | Agent identity |
| `~/.grok/rules/aubieeternal.md` | House rules |
| `aubie-build.service` | systemd unit (port 8840) |
| `qwen_loop.py` | Local-Qwen tool-calling turn (used by the web UI) — up to 8 tool-calls per human turn, then waits for the next prompt |
| `agent_loop.py` | **Autonomy loop** (2026-09-04) — see below |
| `self_audit.py` | Every-15-min service/HTTP/disk check + recurring-issue lessons (prior art for `agent_loop.py`'s logging) |

## Autonomy loop (`agent_loop.py`)

Give it one goal; it drives itself through propose → execute → check → decide
until done, bounded, or blocked — no cloud calls, same local `qwen2.5:14b`/`7b`
as everything else here.

```bash
agent-loop "one clear sentence describing the task" [--cwd PATH] \
  [--model qwen2.5:14b] [--max-iterations 12] [--max-seconds 600]

agent-loop --status RUN_ID
agent-loop --resume RUN_ID --approve
agent-loop --resume RUN_ID --deny "why not"
```

**Hard-stop gates** (checked mechanically against the actual tool call, not
just asked of the model): `git commit`/`git push`; `systemctl restart/stop/
disable` on any service; deleting a file; `pip`/`apt` install or upgrade;
anything touching `institute_memory/`; writing to or SSHing into the UNO Q
board (`100.66.110.65`, or the `sketch_push`/`sketch_write`/`dog_command`
house kits). A gated action stops the loop and writes `pending_action.json` —
nothing runs until a human re-invokes with `--approve` or `--deny`.

Bounded on both `--max-iterations` (default 12) and `--max-seconds` (default
600). Every run logs to `~/AUBIEETERNAL/memory/agent_loop/<run_id>/`:
`run.md` (human-readable transcript — read this one), `steps.jsonl`,
`latest.json`, `messages.json` (full chat history, for `--resume`). That
directory is gitignored — logs never reach the public repo.

Lives as a separate module rather than a change to `qwen_loop.py`, so the
web UI / TUI's existing single-turn behavior is untouched.

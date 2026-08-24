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

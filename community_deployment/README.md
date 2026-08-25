# Community Deployment

For a machine donated to a library, orphanage, or community center — meant
to serve a room full of walk-up patrons, not just one family.

## What's here

- **`ollama-concurrency.conf`** — a systemd override that raises Ollama's
  concurrent-request limit (defaults to 1, meaning only one person's
  question gets answered at a time — everyone else queues). Not applied
  automatically to any running instance; see the file itself for install
  steps and how to pick the right number for a given machine's RAM.

- **`make_join_card.py`** — generates a printable QR code card pointing
  straight at Community Mode (the real anonymous, no-login walk-up path —
  see `community_learners.py`), so a patron just scans and starts, no
  typing a URL by hand.

  ```bash
  python make_join_card.py http://<server-ip>:8501 join_card.png
  ```

  Use whatever IP the server is actually reachable at on the location's
  network (`ip addr` for a local LAN, `tailscale ip` if patrons join a
  tailnet first).

## How walk-up patrons actually get continuity

Community Mode doesn't require creating a real family account — instead,
patrons pick a name + a short PIN (see `community_learners.py`), no email
or personal info collected at all. The same name + PIN on a later visit
resumes their real progress (XP, completed lessons) via the same
`family_profiles.py` storage every other part of AUBIEETERNAL already
uses — not a separate, weaker system.

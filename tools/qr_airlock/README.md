# AUBIEETERNAL QR Airlock v0.1

Implements the 2026-09-04 handoff. Household-local decode + hash + verdict.
Optional Share Flag JSON. **No auto-open, no photos uploaded, no remote-control.**

Tested end-to-end in this environment: decode → hash → heuristic verdict →
share → publish → re-check returns `confirmed_bad`. Allow-list and the
"never fake SAFE" invariant are covered by test runs too (see bottom of
this file for the exact commands if you want to re-run them on the rig).

## Where this goes

Drop the whole folder in as-is:

```
AUBIEETERNAL/
  tools/
    qr_airlock/          <- this folder, unmodified
      decode.py
      hash_payload.py
      heuristics.py
      flags.py
      verdict.py
      log.py
      share.py
      airlock.py
      api.py
      cli.py
      README.md
      QR_FLAG_SPEC.md
```

**Integration note (Claude Code, 2026-09-04):** the module ships as a proper
package. Internal imports were converted from flat (`from decode import ...`)
to explicit relative (`from .decode import ...`), and `tools/__init__.py` +
`tools/qr_airlock/__init__.py` were added, because `assistant_server.py` runs
with the repo root as CWD and mounts the router as
`from tools.qr_airlock.api import router` — flat imports can't resolve when
the folder is imported as a subpackage. `cli.py` still runs standalone
(`python tools/qr_airlock/cli.py --payload ...` from the repo root) via a
fallback import; `python -m tools.qr_airlock.cli ...` also works.

## Dependencies

```
pip install opencv-python-headless fastapi pydantic
```

(`opencv-python-headless` avoids pulling in GUI libs you don't need on a
headless rig. `qrcode`/`pillow` are only needed if you want to generate
test images like I did — not a runtime dependency.)

## Wiring into `assistant_server.py`

```python
from tools.qr_airlock.api import router as qr_router
app.include_router(qr_router)
```

This adds:
- `POST /qr/check` — `{ "payload": "..." }` or `{ "image_b64": "..." }` → verdict JSON
- `POST /qr/allow` — "Allow this month" action
- `POST /qr/share` — "Share flag" action (queues locally, does **not** publish)

### Wiring the Qwen explanation

**Done (2026-09-04).** `_explain_via_qwen()` in `api.py` now lazy-imports
`query_ollama` + `TEXT_MODEL` from `assistant_server.py` (the exact helper
`/converse` uses — `POST 127.0.0.1:11434/api/generate`, `TEXT_MODEL =
pick_best_model() or "qwen2.5:14b"`) and asks for a 2-3 sentence, no-jargon
"why this might be risky" using a security-explainer `system_override` so it
doesn't inherit Aubie's tutor persona. Lazy import = no cycle with
`assistant_server` importing the router at startup, and the module still
imports standalone. Any failure (model busy, Ollama down) returns `""` and
`verdict.py` falls back to the canned `DEFAULT_EXPLANATIONS` text — this
fallback path was also fixed here (previously an empty model return was
assigned verbatim instead of falling through).

## Household data vs public data (the actual privacy boundary)

| Path | Contents | Ever leaves the rig? |
|---|---|---|
| `~/.aubieeternal/qr_airlock/household_log.jsonl` | every check: hash, verdict, time, who, no images | **No.** |
| `~/.aubieeternal/qr_airlock/allowlist.json` | domains/hashes the family approved | **No.** |
| `~/.aubieeternal/qr_airlock/pending_share.jsonl` | flags queued by "Share flag" button | **No — see below.** |
| `~/.aubieeternal/qr_airlock/qr-flags.cache.json` | cached copy of the *public* feed | Pulled *from* the site, never pushed automatically |

Override the base directory with `AUBIE_QR_HOME` (useful for kiosk vs.
per-user separation, or testing).

## Publishing a flag (the one manual step, by design)

`share_flag()` only ever appends to the local `pending_share.jsonl` queue.
Nothing auto-commits or auto-pushes. To actually publish:

1. Review `pending_share.jsonl` on the rig.
2. Append the record(s) you want public to
   `public/flags/qr-flags.json` in the `aubieeternal-institute.org` repo
   (see `QR_FLAG_SPEC.md`).
3. Commit/push as usual (or let a human maintainer merge a PR).

This keeps the "no auto-share one brain" rule from the handoff intact —
Grok/other tools only ever see what a human chose to publish.

## Verdicts

Matches the handoff table exactly: `unknown` (default) → `suspicious` →
`confirmed_bad` (institute-confirmed or ≥3 independent sightings) /
`allowed` (household allow-list) / `withdrawn`. **Never** returns a bare
"safe" — see `DEFAULT_EXPLANATIONS` in `verdict.py`.

## Offline behavior

All checks run against local files (`qr-flags.cache.json`, `allowlist.json`).
No network calls happen inside `evaluate()` or `check_qr()`. If the cache
is stale or missing, checks fall through to heuristics and default to
`unknown` — never a crash, never a fake "safe" (this is covered by the
acceptance-check tests).

## Quick manual test

```bash
python cli.py --payload "https://paypa1-secure.tld/verify"
python cli.py --image screenshot.png --claimed-as menu
```

## Not built (intentionally, per handoff "out of scope")

- No domain-age lookup (would require an external API call — heuristics
  are offline-only, per "hard-coded heuristics first").
- No quarantine fetch container (phase 2, not required for this proof).
- No school/curriculum card (phase 3).
- No venue reputation scoring.
- No remote access / accessibility-abuse flows of any kind.

## Kiosk / edge notes

Edge (phone camera, kiosk `phone_ui.py`, or aubie-tutor) should:
1. Decode locally or screenshot → base64 → `POST /qr/check`.
2. Print the raw URL in big type. **Never navigate to it automatically.**
3. Show the verdict badge + explanation.
4. Offer buttons: Copy URL / Allow this month / Share flag — each an
   explicit tap, matching the "no auto-anything" rule throughout.

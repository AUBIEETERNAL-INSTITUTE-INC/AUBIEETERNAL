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

### Surrounding-image context read (2026-09-07)

An optional **second pass**, gated to `verdict == "suspicious"` only. When
heuristics flagged a warning sign **and** a photo is available, `check_qr()`
calls `context_vision.read_context()`, which sends the image to the local
`qwen2.5vl:7b` model and asks it to describe *what the QR is physically
printed on* and whether that setting looks like an everyday, low-risk source
(shop receipt, product packaging, appliance label, printed ticket) versus
nothing visible / a code stuck or taped over its surroundings.

- **Additive only.** The result is attached to the response as
  `context_read` and shown under the existing badge + warning signs. It
  **never changes `verdict`**, never clears a flag, and the user still makes
  the allow/flag decision.
- **`suspicious` only.** It does **not** run for `unknown` (the default for
  a first-seen URL with no signals), nor for a clean pass/fail (`allowed`,
  `confirmed_bad`, `withdrawn`, `wifi`), nor when no photo was supplied — so
  the common kiosk scan keeps its current latency. `unknown` was excluded
  after review specifically because it's the common case and already pays
  for the `_explain_via_qwen` call.
- **Degrades to nothing.** Model not pulled / Ollama down / timeout /
  unparseable output → `context_read` is `null` and the display is exactly
  as it was before this feature. No new failure mode.
- **Privacy.** The photo and the text derived from it stay in the
  `/qr/check` response. `context_read` is **not** written to
  `household_log.jsonl` and is **not** part of a shared flag
  (`QR_FLAG_SPEC`: "no image, no scanner identity").

`context_read` shape:

```json
{
  "available": true,
  "model": "qwen2.5vl:7b",
  "surface": "printed at the bottom of a paper retail receipt",
  "visible_text": "FACTURA NRO 0012-... (INVOICE NO 0012-...)",
  "consistency": "consistent | unclear | inconsistent",
  "read": "This looks printed on a standard retail receipt with visible invoice and warranty text — consistent with a normal receipt QR, not a sign of tampering.",
  "note": "Extra context only — this does not change the safety verdict above."
}
```

Wiring: `api.py`'s `/qr/check` passes `context_fn=_read_context_via_qwenvl`.
Callers that decode the QR themselves can still get the read by passing
`context_image_b64` (a separate/wider shot); if omitted, the frame the QR
was scanned from (`image_b64`) is used. The kiosk (`phone_ui.py` Scan QR
tab) already sends the full camera frame as `image_b64`, so it gets the
context read with no client change; `renderQR()` shows it in a "📷 Context
read" box.

CLI: `python tools/qr_airlock/cli.py --image receipt.png` (add
`--context-image wider.png` for a separate context shot).

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

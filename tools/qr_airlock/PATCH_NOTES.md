# QR Airlock v0.1 — Follow-up Patch Notes (2026-09-04)

Addresses the three non-blocking items Claude Code flagged after integration.

## #2 — Decoder robustness (FIXED, replace file)

`tools/qr_airlock/decode.py` is rewritten. Changes:

- **`pyzbar` (libzbar) is now the primary decoder**, with `cv2.QRCodeDetector`
  kept as an automatic fallback if `pyzbar`/`libzbar` isn't importable —
  so this degrades gracefully rather than hard-failing on a box missing
  the system library.
- **Preprocessing variants** (grayscale, CLAHE local-contrast boost,
  adaptive threshold) are tried automatically when a plain decode fails —
  handles uneven lighting and low-contrast prints without any caller
  changes.
- **Tested against realistic degradation**, not just a clean PNG:
  - Rotated ~15° — decodes correctly
  - Low contrast (faded sticker sim) — decodes correctly
  - Rotated + low-contrast + blur combined (worst case) — decodes correctly
  - Full finder-pattern wipeout (extreme glare) — correctly fails closed
    (no decoder could recover this; it's a real physical-obstruction case)
  - Data-area streak exceeding ~15% obstruction — correctly fails closed
    (exceeds the QR's own error-correction capacity — not decoder-specific)

**Dependency:** add `pyzbar` to `requirements.txt`. It needs the system
package `libzbar0` (`sudo apt-get install libzbar0` if not already
present — it may already be there; check with
`dpkg -l | grep libzbar` before installing).

No other file needs to change — `airlock.py`, `api.py`, etc. all call
`decode_image_bytes()` / `decode_base64_image()` the same way as before.

## #3 — Unused `import io` (FIXED, included in the same file)

Removed as part of the decode.py rewrite above — it's gone in the
replacement file, nothing else to do.

## #1 — Latency (needs a change in the code already wired on the rig)

The airlock module itself doesn't own this — the blocking Qwen call
happens in the `_explain_via_qwen()` stub Claude Code wired directly
into the rig's copy of `tools/qr_airlock/api.py` against the real
`assistant_server.query_ollama()`. I don't have that file's current
contents (it was written on the rig, not here), so this is a note for
whoever edits it next rather than a file I can hand over.

**Cheapest fix** (~1 line): in `_explain_via_qwen()`, change the model
argument from whatever it currently uses to `"qwen2.5:7b"` — noticeably
faster than 14b for a one-paragraph explanation, and the heuristic
verdict (the safety-relevant part) is already returned instantly
regardless of which model answers.

**If still too slow after that:** shorten the timeout passed to
`query_ollama()` (e.g. 15–20s instead of 60s) and let `verdict.py`'s
existing `DEFAULT_EXPLANATIONS` fallback take over on timeout — that
fallback path already exists and is exercised by the test suite, so
this is a config change, not new logic.

**Only do the full async rewrite** (return verdict immediately, fetch
explanation in the background, e.g. via a second `/qr/explain` call
from the kiosk after showing the verdict) if the model-swap + shorter
timeout still feels slow in practice. Don't build that speculatively —
per the earlier guidance, test the current behavior on the kiosk first.

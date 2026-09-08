# Appliance / control-panel explainer — design + v1

Status: **v1 implemented on `feature/appliance-explainer`, not merged, not
restarted.** From the 2026-09-07 vision-reasoning handoff (Feature 2).
Feature 1 (QR Airlock context read) shipped separately on
`feature/qr-airlock-context-check`.

The four open questions below were reviewed and approved 2026-09-07:
**(1)** JSON response — with the spoken WAV embedded as `audio_b64` so the
structured map and the audio arrive in one call (`/speak_local` has no
per-language voice, so embedding also gets the language-correct Piper
voice); **(2)** dedicated kiosk tab; **(3)** wake-word deferred to v1+ —
core flow only for now; **(4)** no persistence.

## What landed in v1

- `assistant_server.py`: `POST /explain_panel` + `_panel_prompt` /
  `_parse_panel_json` / `_panel_spoken_fallback` helpers. Accepts `image`
  (required), optional typed `question`, optional `language`. Returns the
  JSON in "Response" below with `audio_b64` (Piper WAV in the resolved
  reply language). Degrades to reading the model's prose aloud if the reply
  isn't parseable JSON — never 500s on a bad model reply. `role` is clamped
  to a fixed enum.
  - **No `audio`/STT param in v1** (dropped in review): a spoken question
    means routing wake-word audio, which is the deferred `/converse`
    delegate path below — adding STT here first would be a second,
    throwaway entry point. The typed `question` box covers the kiosk need.
- `phone_ui.py`: new **🎛️ Panel** tab (7th), cloned from the Scan QR tab —
  optional "what are you trying to do?" box, one "Read this panel" button,
  a **To do that** steps list, an *On the panel / Means / What it does*
  table, "read aloud again", and a manual-check disclaimer. Auto-plays the
  walkthrough once.
- **Not** wired: `PANEL_INTENT_RE` / the `/converse` delegate branch /
  `aubie_listen.py` — that's the wake-word follow-up (see below), left for
  a later PR when the board is back online.

Tested via `TestClient` against the real `qwen2.5vl:7b` on a mock
Spanish-labelled microwave panel: no-question → full control map with
Spanish→English label translations, `task:null`; with "how do I defrost
meat" → `task.steps` populated; `language=es` → Spanish `spoken` + Spanish
voice; missing image → 422. One call ~40–50s on the RTX 3060 with the
model competing with whisper (warm/idle should be faster) — an explicit
"read this panel" action with a spinner, not a live loop.

**To go live:** merge to `main` → `sudo systemctl restart aubie-assistant`.

---

## Original design pass (for reference)

## Goal

Point the kiosk tablet or a phone camera at an unfamiliar appliance control
panel — microwave, washer, thermostat, oven — possibly labelled in a
language the user doesn't read, and get:

1. a plain-language map of what each button / dial / display does, with the
   original label **and** its translation, and
2. if the user asked a task question ("how do I defrost this?"), the
   specific sequence of presses to do it,

delivered as a spoken walkthrough (Piper TTS) and as structured data the
kiosk can render as a table now and draw as an on-screen overlay later.

## What's already in place (nothing new to pull or install)

| Piece | Where | Note |
|---|---|---|
| Vision model | `qwen2.5vl:7b`, `VISION_MODEL` in `assistant_server.py` | already pulled; used by `/greet` object detection, `/vision_describe`, `/mood_check` |
| Vision call helper | `query_ollama(prompt, model, image_b64=…, system_override=…, timeout=…)` `assistant_server.py:1272` | already sends `images:[…]` to Ollama |
| Closest precedent | `POST /vision_describe` `assistant_server.py:1594` | `image + prompt Form` → `query_ollama(VISION_MODEL)` → JSON. `/explain_panel` ≈ this + structured prompt + optional STT/TTS |
| STT | `transcribe(path) -> (text, detected_lang)` `:1262`, multilingual whisper | gives the reply-language for free |
| Reply-language resolve | `resolve_reply_language(form_lang, detected_lang)` `:1376` | explicit > install default > STT detect > English |
| TTS | `synthesize_speech(text, voice)` `:1321`; `VOICE_BY_CODE`, `get_active_voice()`; `POST /speak_local` `:1892` returns a WAV for `text` Form | per-language Piper voices already keyed |
| Kiosk camera over HTTPS | `phone_ui.py` `captureTabletFrame()`, Tailscale Serve URL `https://aubieeternal.tail00eb41.ts.net/remote` | `getUserMedia` HTTPS requirement already solved; Scan QR tab is the UI template |
| Wake-word → `/converse` | board file `aubie_listen.py` (SSH `100.66.110.65`) | **not in git** — see "Edge-file flag" below |

## Recommended shape

### New endpoint, not an overload of `/converse`

`POST /explain_panel` — a sibling of `/vision_describe`, **not** a branch of
`/converse`. Reasons:

- `/converse` is deliberately latency-tuned: follow-up turns skip vision
  entirely (`use_vision` gate at `:1507`) because `qwen2.5vl` alone is ~15s
  and that's too slow for live back-and-forth. Panel-explain is a vision
  call *every* time by definition.
- Different output contract: a structured control map + task steps, not a
  short spoken reply that fits in `X-Reply-Text` headers.
- Keeps `/converse`'s canned-command / joint-move / translation
  short-circuits uncluttered.

`/converse` can still *delegate*: see "Wake-word path" below.

### Request

> **v1 shipped without `audio`** — see "What landed in v1". The `audio`
> row below is the wake-word-path shape, kept here for when that lands.

```
POST /explain_panel        (multipart/form-data)
  image     : UploadFile          (required — single still photo, no video in v1)
  audio     : UploadFile | None   (deferred — spoken question, arrives with wake-word routing)
  question  : str  Form | None    (optional typed question, kiosk text path)
  language  : str  Form | None    (reply-language override; else STT detect / install default)
```

### Response — JSON (deliberately unlike `/converse`)

`/converse` returns a raw WAV with text in `X-*` headers; that can't carry
the control map. `/explain_panel` returns JSON, and the kiosk makes a
second call to the **existing** `POST /speak_local` with `spoken` to get
audio. Two small round-trips, each endpoint does one thing, zero new TTS
code. (The vision call dominates latency anyway; TTS is ~instant.)

```json
{
  "device_guess": "microwave oven",
  "panel_language": "es",
  "reply_language": "en",
  "controls": [
    {
      "label_seen": "Descongelar",
      "label_translated": "Defrost",
      "position": "second row, left",
      "role": "preset",
      "does": "Runs a lower-power cycle to thaw frozen food; you then enter weight or time."
    },
    { "label_seen": "Inicio", "label_translated": "Start", "position": "bottom right",
      "role": "start", "does": "Begins the cycle you set up." }
  ],
  "task": {
    "asked": "how do I defrost chicken",
    "steps": [
      "Press Descongelar (Defrost).",
      "Turn the dial to the weight of the chicken, about 1 kilo.",
      "Press Inicio (Start)."
    ]
  },
  "spoken": "This looks like a microwave. The panel is in Spanish. To defrost: press Descongelar, which means Defrost, set the weight with the dial, then press Inicio to start. …",
  "model": "qwen2.5vl:7b"
}
```

- `task` is `null` when no question was given → response is just the
  control map + a one-line "what this panel is for" in `spoken`.
- `controls[].position` is intentionally **coarse text** for v1 (see
  "Deferred" for the real overlay).
- Parse defensively: if the model doesn't return clean JSON, put its prose
  in `spoken`, leave `controls: []`, `task: null` — degrade to "a
  paragraph read aloud," never a 500.

### Prompt

- `system_override`: "You explain unfamiliar appliance control panels to
  someone who may not read the language printed on the device. Be concrete
  and physical: name the control, where it is, what it does. For every
  label, give the text exactly as printed AND its translation into
  `<reply_language>`. Never invent controls you cannot see."
- User prompt: ask for **strict JSON** in the shape above (precedent:
  `assistant_server.py:350` already does `system_override="Reply with only
  JSON or NONE, nothing else."`, and `OBJECT_DETECTION_PROMPT` at `:812`).
  Include the task question when present so `task.steps` is filled.
- One image only (v1 constraint).

### Latency / UX

One `qwen2.5vl` vision call, ~10–20s warm on the RTX 3060 for a single
image with this prompt (bigger than object detection). This is an explicit
"explain this" action, not a loop — show a "reading the panel…" spinner,
auto-play `spoken` once on completion (same feel as wake-word → greet).
`await asyncio.to_thread(query_ollama, …)` so the event loop isn't blocked
(pattern already used at `:1608`).

## Kiosk UI (`phone_ui.py`)

New tab **"🎛️ Explain a panel"**, cloned from the Scan QR tab structure:

- `captureTabletFrame()` → freeze the frame, show it as a preview.
- Optional typed-question input + a mic button (reuse the existing
  recorder used by the converse path).
- `POST /explain_panel`; on result:
  - heading: `device_guess` + "panel is in `<panel_language>`"
  - a table: **Label on the panel | Means | What it does** (one row per
    `controls[]`), `position` shown as a muted hint
  - if `task`: a numbered **"To do that:"** list from `task.steps`
  - "🔊 Read it aloud" button → `POST /speak_local` with `spoken`; also
    auto-played once.
- No PIPE trust-strip gate needed (there's no link to open — unlike Scan
  QR), but the tab still needs HTTPS for the camera, which
  `captureTabletFrame()`'s existing insecure-origin handling already
  enforces.

## Wake-word path ("hey aubie, how do I use this?")

Flows through `aubie_listen.py` on the board → `/converse`. To support it
without duplicating logic:

- Add `PANEL_INTENT_RE` next to `OBJECT_ID_RE` (`assistant_server.py:243`)
  — matches "how do I use this / work this / what do these buttons do / how
  do I <verb> (defrost|wash|dry|preheat…) this".
- In `/converse`, when `image_bytes` is present **and** `PANEL_INTENT_RE`
  matches, call the shared `explain_panel()` helper instead of the generic
  "identify this object" vision prompt, and speak
  `task.steps` (or `spoken`). The structured map is **not** returned on the
  `/converse` path (headers can't hold it) — the visual table lives only in
  the kiosk tab. Spoken-only is the right answer for a wake-word
  interaction anyway.
- The board attaches a fresh photo on converse turns already; confirm it
  does so for this phrase too (it scans faces from the same frame).

### Edge-file flag (per `CLAUDE.md` "edge devices are disposable")

`aubie_listen.py` lives **only on the board**, not in git (2026-08-29 edge
audit). Any wake-word wiring for this feature must land in the repo:
capture it via `tools/pull-board-files` (or commit it directly) **in the
same PR** — do not leave it board-only. If `/converse` does all the
routing, the board may need zero changes; verify on reconnect (board was
offline as of 2026-09-05).

## Files this will touch (estimate)

| File | Change | ~LOC |
|---|---|---|
| `assistant_server.py` | `explain_panel()` helper, `POST /explain_panel`, `PANEL_INTENT_RE`, `/converse` delegate branch | ~130 |
| `phone_ui.py` | new "Explain a panel" tab + JS render + `/speak_local` call | ~150 |
| `aubie_listen.py` (board → git) | likely none if `/converse` routes; confirm + commit | 0–20 |
| `APPLIANCE_EXPLAINER.md` (rename this file) + `CLAUDE.md` roadmap note | docs | — |

## Deferred (not v1)

- **Bounding-box overlay.** v1 gives coarse text positions. A real
  draw-boxes-on-the-frozen-frame overlay needs normalized `[x,y,w,h]` per
  control; `qwen2.5vl` can sometimes produce these but not reliably —
  revisit as v2 with an eval on real panel photos first.
- **Live video / "point and follow".** v1 is one still photo (handoff
  constraint).
- **Remembering "the microwave in this house"** by a stable label /
  per-appliance notes. No persistence in v1.
- **Safety-interlock advice** (oven self-clean, gas ignition). If added,
  needs a careful disclaimer pass — out of scope for the first cut.

## Open questions — resolved 2026-09-07

1. **JSON** (with `audio_b64` embedded — one call, language-correct voice).
2. **Dedicated kiosk tab.**
3. **Wake-word deferred to v1+.** Core flow first.
4. **No persistence.**

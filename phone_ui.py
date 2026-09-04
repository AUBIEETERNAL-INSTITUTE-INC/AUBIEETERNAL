"""
AUBIEETERNAL — Teaching Station + Build Code + Dog Remote (3-Tab UI)
File: /home/aubieeternal/AUBIEETERNAL/phone_ui.py

Tab 1: 🧠 Teach   — Ask, Voice, Quick Topics, Camera, System
Tab 2: ⚙️ Build   — AUBIEETERNAL Build Code (dual-road agentic)
Tab 3: 🐕 Dog     — RC, Movement, Face, Tricks, Servos, Bluetooth

Access: https://aubieeternal.tail00eb41.ts.net/remote
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, FileResponse, Response
import asyncio
import datetime
import httpx
import json
import re
from pathlib import Path

from curriculum import get_lesson, next_lesson, total_lessons, track_progress
from family_profiles import FAMILY_REGISTRY, load_family_stats, save_family_stats, update_streak
from model_selector import ranked_try_order

router = APIRouter()

# ── PWA (Add to Home Screen) ──────────────────────
# Serves a manifest + a minimal service worker so Safari/Chrome offer a real
# installable app icon over the existing Tailscale Serve HTTPS URL. No Apple
# Developer account, no store review. Personal-use convenience only - it does
# not change behaviour for people who install AUBIEETERNAL themselves.
PWA_ASSETS = Path(__file__).resolve().parent / "assets" / "pwa"
PWA_ICON_FILES = {
    "icon-192.png", "icon-512.png",
    "icon-512-maskable.png", "apple-touch-icon-180.png",
}
PWA_MANIFEST = {
    "name": "AUBIEETERNAL",
    "short_name": "AUBIEETERNAL",
    "description": "Always-on AI teaching station",
    "start_url": "/remote",
    "scope": "/",
    "display": "standalone",
    "orientation": "any",
    "background_color": "#070b0f",
    "theme_color": "#00c9ff",
    "icons": [
        {"src": "/pwa/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
        {"src": "/pwa/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
        {"src": "/pwa/icon-512-maskable.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
    ],
}

# Cache only the app shell (the /remote document) for offline launch. Every
# API call - /converse, /ask-text, /auth/* - is passed straight through and
# never touched by the worker, so nothing account-scoped is ever cached.
PWA_SW_JS = (
    "const SHELL = 'aubie-shell-v2';\n"
    "self.addEventListener('install', function (e) {\n"
    "  e.waitUntil(caches.open(SHELL).then(function (c) { return c.add('/remote'); }).then(function () { return self.skipWaiting(); }));\n"
    "});\n"
    "self.addEventListener('activate', function (e) {\n"
    "  e.waitUntil(caches.keys().then(function (keys) {\n"
    "    return Promise.all(keys.filter(function (k) { return k !== SHELL; }).map(function (k) { return caches.delete(k); }));\n"
    "  }).then(function () { return self.clients.claim(); }));\n"
    "});\n"
    "self.addEventListener('fetch', function (e) {\n"
    "  var req = e.request;\n"
    "  if (req.method !== 'GET') return;\n"
    "  var url = new URL(req.url);\n"
    "  if (url.origin !== self.location.origin) return;\n"
    "  if (req.mode === 'navigate' || url.pathname === '/remote') {\n"
    "    e.respondWith(fetch(req).then(function (res) {\n"
    "      var cp = res.clone(); caches.open(SHELL).then(function (c) { c.put('/remote', cp); }); return res;\n"
    "    }).catch(function () { return caches.match('/remote'); }));\n"
    "    return;\n"
    "  }\n"
    "  if (url.pathname.indexOf('/pwa/') === 0 || url.pathname.indexOf('/apple-touch-icon') === 0) return;\n"
    "  // APIs and auth: straight to network, never cached.\n"
    "});\n"
)

AUBIE_URL    = "http://100.66.110.65:8420"   # legacy dog server
OLLAMA_URL   = "http://localhost:11434"       # local Ollama LLM server
# Qwen models the rig is known to use (tried in order)
OLLAMA_MODELS = [
    "qwen2.5:7b", "qwen2.5:14b", "qwen2.5:32b",
    "qwen2:7b",   "qwen2:14b",
    "qwen:7b",    "llama3:8b",   "llama3.1:8b",
    "mistral:7b", "llama2:7b",
]

async def _ollama_chat(message: str, history: list[dict] | None = None, speaker: str | None = None) -> dict:
    """Try each Qwen/Llama model until one responds. `history` (prior
    [{role, content}] turns, not including `message`) is threaded through
    Ollama's /api/chat so follow-up questions actually have context - unlike
    /api/generate, which only ever sees a single flat prompt with no memory
    of earlier turns in the conversation.

    Also injects assistant_server's Aubie persona + durable memory (known
    facts, conversation summary, recent exchanges) as a system message, and
    records this exchange back into that same memory - without this, this
    text/typed path (used by Watch mode's "hey aubie" and the typed-question
    box) was a bare, unguided model call that had no idea it was "Aubie" and
    no access to anything /converse (the audio path) already remembers, e.g.
    replying "I'm an AI model with training data up to 2022" and forgetting
    durable facts like what book Gabriela is reading. `assistant_server`
    imports this module at startup (see its `from phone_ui import router`),
    so it's imported here lazily, at call time, to avoid a circular import -
    by the time a request comes in, assistant_server has finished loading."""
    import assistant_server as _srv

    context = _srv.build_context_block(
        speakers_in_room=[speaker] if speaker else [],
        objects_seen=[],
        user_message=message,
    )
    system = f"{_srv.SYSTEM_PROMPT}\n\n{context}" if context else _srv.SYSTEM_PROMPT
    messages = [{"role": "system", "content": system}, *(history or []), {"role": "user", "content": message}]

    async with httpx.AsyncClient(timeout=90) as client:
        # 1. Ask Ollama which models are available
        try:
            tags = await client.get(f"{OLLAMA_URL}/api/tags")
            available = [m["name"] for m in tags.json().get("models", [])]
        except Exception:
            available = []

        # Prefer the same model /converse uses (itself hardware-aware, see
        # model_selector.py - a stronger machine gets a bigger model by
        # default, not a fixed constant); fall back through everything else
        # actually pulled, largest-to-smallest, before the hardcoded list.
        to_try = [_srv.TEXT_MODEL] + [m for m in ranked_try_order(available) if m != _srv.TEXT_MODEL]
        if not any(m in available for m in to_try):
            to_try += OLLAMA_MODELS  # nothing pulled yet - try the static list as a last resort

        for model in to_try:
            try:
                r = await client.post(
                    f"{OLLAMA_URL}/api/chat",
                    json={"model": model, "messages": messages, "stream": False},
                    timeout=90,
                )
                if r.status_code == 200:
                    data = r.json()
                    reply = data.get("message", {}).get("content", "")
                    try:
                        _srv.remember_exchange(speaker, [speaker] if speaker else [], message, reply, [])
                        await asyncio.to_thread(_srv.extract_and_remember_fact, speaker, message, reply)
                        _srv.maybe_trigger_compaction()
                    except Exception:
                        pass  # memory persistence is best-effort, never break the reply
                    return {"reply": reply, "model": model}
            except Exception:
                continue

    return {"error": "Ollama not available — check that the local LLM is running"}

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>AUBIEETERNAL</title>
<link rel="manifest" href="/manifest.webmanifest">
<meta name="theme-color" content="#00c9ff">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="AUBIEETERNAL">
<link rel="apple-touch-icon" href="/pwa/apple-touch-icon-180.png">
<link rel="apple-touch-icon" sizes="180x180" href="/pwa/apple-touch-icon-180.png">
<link rel="apple-touch-icon-precomposed" href="/pwa/apple-touch-icon-180.png">
<style>
  :root {
    --bg:      #070b0f;
    --card:    #111820;
    --border:  #1e2d3d;
    --accent:  #00c9ff;
    --gold:    #ffaa00;
    --green:   #00e676;
    --red:     #ff5252;
    --purple:  #bb86fc;
    --orange:  #ff9800;
    --text:    #e8f0fe;
    --sub:     #6c8499;
    --radius:  16px;
    --gap:     12px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    min-height: 100vh;
    padding-bottom: 80px;
  }

  /* ── Tab bar (fixed bottom) ── */
  .tabbar {
    position: fixed;
    bottom: 0; left: 0; right: 0;
    display: flex;
    background: #0a1118;
    border-top: 1px solid var(--border);
    z-index: 100;
  }
  .tab-btn {
    flex: 1;
    padding: 12px 8px 16px;
    text-align: center;
    cursor: pointer;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
    color: var(--sub);
    transition: color 0.2s;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    border: none;
    background: none;
  }
  .tab-btn .tab-icon { font-size: 22px; }
  .tab-btn.active { color: var(--accent); }
  .tab-btn.active .tab-icon { filter: drop-shadow(0 0 6px var(--accent)); }

  /* ── Tab panels ── */
  .tab-panel { display: none; padding: 14px; }
  .tab-panel.active { display: block; }

  /* ── Header ── */
  header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 14px;
    padding: 14px 16px;
    background: var(--card);
    border-radius: var(--radius);
    border: 1px solid var(--border);
  }
  .logo { font-size: 20px; font-weight: 800; }
  .logo span { color: var(--accent); }
  .tagline { font-size: 10px; color: var(--sub); margin-top: 2px; }
  .dot {
    width: 9px; height: 9px; border-radius: 50%;
    background: var(--red); margin-left: auto; flex-shrink: 0;
    transition: background 0.4s;
  }
  .dot.online { background: var(--green); animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100%{opacity:1}50%{opacity:.4} }

  /* ── Cards ── */
  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 14px;
    margin-bottom: var(--gap);
  }
  .card-title {
    font-size: 10px; font-weight: 700;
    letter-spacing: 1.5px; text-transform: uppercase;
    color: var(--sub); margin-bottom: 10px;
  }

  /* ── Inputs ── */
  textarea, input[type=text], input[type=range] {
    width: 100%;
    background: #0d1520;
    border: 1px solid var(--border);
    border-radius: 10px;
    color: var(--text);
    font-size: 15px;
    padding: 11px;
    font-family: inherit;
    resize: none;
    outline: none;
    transition: border-color 0.2s;
  }
  textarea:focus, input[type=text]:focus { border-color: var(--accent); }
  select {
    width: 100%; background: #0d1520; border: 1px solid var(--border);
    border-radius: 10px; color: var(--text); font-size: 14px;
    padding: 10px; outline: none;
  }

  /* ── Buttons ── */
  .btn {
    border: none; border-radius: 12px;
    padding: 13px 16px; font-size: 14px; font-weight: 700;
    cursor: pointer; transition: transform 0.1s, opacity 0.15s;
    width: 100%; margin-top: 10px;
    display: flex; align-items: center; justify-content: center;
    gap: 7px; color: #fff;
  }
  .btn:active { transform: scale(0.96); opacity: 0.85; }
  .btn-accent  { background: linear-gradient(135deg,#0072ff,#00c9ff); }
  .btn-gold    { background: linear-gradient(135deg,#b8860b,#ffaa00); color:#000; }
  .btn-green   { background: linear-gradient(135deg,#00843d,#00e676); color:#000; }
  .btn-purple  { background: linear-gradient(135deg,#6a0dad,#bb86fc); }
  .btn-red     { background: linear-gradient(135deg,#b71c1c,#ff5252); }
  .btn-orange  { background: linear-gradient(135deg,#e65100,#ff9800); }
  .btn-teal    { background: linear-gradient(135deg,#006064,#00bcd4); }
  .btn-sm { padding: 11px 12px; font-size: 13px; border-radius: 10px; margin-top: 0; }
  .btn-xs { padding: 9px 10px; font-size: 12px; border-radius: 9px; margin-top: 0; }

  /* ── Grid helpers ── */
  .g2  { display:grid; grid-template-columns:1fr 1fr;       gap:8px; margin-top:10px; }
  .g3  { display:grid; grid-template-columns:1fr 1fr 1fr;   gap:8px; margin-top:10px; }
  .g4  { display:grid; grid-template-columns:1fr 1fr 1fr 1fr; gap:6px; margin-top:10px; }

  /* ── Response / code boxes ── */
  .resp {
    background:#0d1520; border:1px solid var(--border);
    border-radius:10px; padding:11px; font-size:13px;
    line-height:1.6; min-height:50px; margin-top:10px;
    white-space:pre-wrap; word-break:break-word; display:none;
  }
  .resp.show { display:block; }
  .resp.thinking { color:var(--sub); font-style:italic; }
  .resp.error    { color:var(--red); border-color:var(--red); }
  .resp.ok       { border-color:var(--green); }
  .code-out {
    background:#050d15; border:1px solid #1a3a1a;
    border-radius:10px; padding:11px;
    font-family:'Courier New',monospace; font-size:12px;
    line-height:1.5; margin-top:10px; white-space:pre-wrap;
    word-break:break-all; color:var(--green);
    max-height:320px; overflow-y:auto; display:none;
  }
  .code-out.show { display:block; }

  /* ── Topic chips ── */
  .topic-chip {
    background:var(--card); border:1px solid var(--border);
    border-radius:12px; padding:12px 6px; font-size:12px;
    font-weight:600; cursor:pointer; text-align:center;
    color:var(--text); transition:border-color .2s,transform .1s;
    display:flex; flex-direction:column; align-items:center; gap:5px;
  }
  .topic-chip:active  { transform:scale(.95); }
  .topic-chip:hover   { border-color:var(--accent); color:var(--accent); }
  .topic-icon { font-size:20px; }
  .person-chip.active { border-color:var(--gold); background:#1a1000; color:var(--gold); }

  /* ── Mic ── */
  .mic-ring {
    width:76px; height:76px; border-radius:50%;
    border:3px solid var(--accent); background:#0d1520;
    display:flex; align-items:center; justify-content:center;
    font-size:30px; cursor:pointer; margin:0 auto;
    transition:all .2s;
  }
  .mic-ring.listening {
    border-color:var(--red);
    box-shadow:0 0 0 10px rgba(255,82,82,.15);
    animation:mpulse 1s infinite;
  }
  @keyframes mpulse{0%,100%{box-shadow:0 0 0 10px rgba(255,82,82,.15)}50%{box-shadow:0 0 0 18px rgba(255,82,82,.04)}}
  .mic-lbl { text-align:center; font-size:11px; color:var(--sub); margin-top:9px; }

  /* ── Build tab header ── */
  .build-header {
    background: linear-gradient(135deg,#0a1a00,#1a3d00);
    border: 1px solid #2a5c00;
    border-radius: var(--radius);
    padding: 14px 16px;
    margin-bottom: var(--gap);
    display: flex; align-items: center; gap: 10px;
  }
  .build-header .blogo { font-size: 20px; font-weight: 800; color: var(--gold); }
  .build-header .bsub  { font-size: 10px; color: #708060; margin-top: 2px; }

  /* ── Build iteration badge ── */
  .iter-badge {
    display: inline-flex; align-items: center; gap: 5px;
    background: #0d1f00; border: 1px solid #2a5c00;
    border-radius: 20px; padding: 4px 10px;
    font-size: 11px; color: var(--green); margin-top: 8px;
  }

  /* ── Dog tab ── */
  .dog-header {
    background: linear-gradient(135deg,#1a0a00,#3d1f00);
    border: 1px solid #5c3000;
    border-radius: var(--radius);
    padding: 14px 16px;
    margin-bottom: var(--gap);
    display: flex; align-items: center; gap: 10px;
  }
  .dog-header .dlogo { font-size: 20px; font-weight: 800; color: var(--orange); }
  .dog-header .dsub  { font-size: 10px; color: #a06030; margin-top: 2px; }
  .dog-dot { width:9px;height:9px;border-radius:50%;background:var(--red);margin-left:auto; }
  .dog-dot.online { background:var(--green); }

  /* joystick */
  .joystick-wrap {
    display:flex; justify-content:center; align-items:center;
    padding: 10px 0;
  }
  #joystick-canvas {
    border-radius:50%;
    border:2px solid var(--border);
    background:#0d1520;
    touch-action:none;
    cursor:crosshair;
  }

  /* face grid */
  .face-btn {
    border:1px solid var(--border); border-radius:10px;
    background:#0d1520; color:var(--text);
    padding:10px 4px; font-size:20px;
    cursor:pointer; text-align:center;
    transition:border-color .2s,transform .1s;
  }
  .face-btn:active { transform:scale(.9); }
  .face-btn.active { border-color:var(--orange); background:#1a0d00; }

  /* slider */
  .slider-row { display:flex; align-items:center; gap:8px; margin-bottom:8px; }
  .slider-row label { font-size:11px; color:var(--sub); width:60px; flex-shrink:0; }
  .slider-row input { flex:1; }
  .slider-row span   { font-size:11px; color:var(--text); width:30px; text-align:right; }

  /* log */
  #log {
    font-family:'Courier New',monospace; font-size:11px;
    color:var(--sub); background:#050d15;
    border:1px solid var(--border); border-radius:10px;
    padding:9px; max-height:140px; overflow-y:auto; line-height:1.6;
  }
  .lok  { color:var(--green); } .lerr { color:var(--red); } .linf { color:var(--accent); }

  /* ── Today's Lesson ── */
  .lesson-card {
    background: linear-gradient(135deg,#0a1520,#001a2e);
    border: 1px solid var(--accent);
    border-radius: var(--radius);
    padding: 16px;
    margin-bottom: var(--gap);
    cursor: pointer;
    transition: transform .15s;
  }
  .lesson-card:active { transform:scale(.98); }
  .lesson-tag { font-size:10px; color:var(--accent); font-weight:700; letter-spacing:1px; margin-bottom:6px; }
  .lesson-title { font-size:17px; font-weight:700; color:var(--text); margin-bottom:6px; line-height:1.3; }
  .lesson-desc { font-size:12px; color:var(--sub); line-height:1.5; }
  .lesson-start { display:inline-block; margin-top:10px; background:var(--accent); color:#000;
    font-weight:700; font-size:12px; padding:6px 16px; border-radius:20px; }

  /* ── Research ── */
  .research-result { font-size:14px; color:var(--text); line-height:1.8; margin-top:10px;
    background:#050d15; border:1px solid var(--border); border-radius:10px;
    padding:14px; max-height:420px; overflow-y:auto; white-space:pre-wrap; }

  /* ── Greet Mode ── */
  .greet-ring {
    width:110px; height:110px; border-radius:50%; margin:0 auto 12px;
    border:3px solid var(--border); background:#050d15;
    display:flex; align-items:center; justify-content:center;
    font-size:48px; position:relative; overflow:hidden; transition:.3s;
  }
  .greet-ring.watching { border-color:var(--green); box-shadow:0 0 0 12px rgba(0,230,118,.1); animation:gpulse 1.5s infinite; }
  .greet-ring.recognized { border-color:var(--gold); box-shadow:0 0 0 16px rgba(255,170,0,.15); }
  @keyframes gpulse{0%,100%{box-shadow:0 0 0 12px rgba(0,230,118,.1)}50%{box-shadow:0 0 0 22px rgba(0,230,118,.04)}}
  .greet-name { font-size:22px; font-weight:800; color:var(--gold); text-align:center; margin-bottom:4px; }
  .greet-msg  { font-size:13px; color:var(--sub); text-align:center; line-height:1.5; }
  /* Floating face widget - lives outside the tab panels so it stays on
     screen (and Watch mode stays connected) no matter which tab you're on. */
  #face-widget {
    display:none; position:fixed; right:14px; bottom:152px; z-index:600; width:460px;
    max-width:calc(100vw - 28px);
    background:linear-gradient(135deg,#0a1500,#001a08); border:1px solid #00e67655;
    border-radius:24px; padding:18px; box-shadow:0 10px 30px rgba(0,0,0,.5);
  }
  #face-widget.show { display:block; }
  /* Always-visible mic FAB - tap-to-talk works even when the face widget
     itself is hidden (e.g. Watch mode never started), since it's the only
     voice option on iOS, which can't do the "hey aubie" listening above. */
  #talk-fab {
    position:fixed; right:14px; bottom:84px; z-index:610; width:56px; height:56px;
    border-radius:50%; background:var(--accent); border:none; color:#001018;
    font-size:24px; box-shadow:0 6px 18px rgba(0,0,0,.4); cursor:pointer;
  }
  #talk-fab.recording { background:var(--red); animation:gpulse 1s infinite; }
  /* Theme picker - swap the widget's face design */
  /* Face picker modal - a section within the page, not a new tab, per
     feedback: pick a preset, preview it live on the actual widget, then
     Save (or Cancel to revert). */
  #face-picker-modal {
    display:none; position:fixed; inset:0; z-index:700; background:rgba(0,0,0,.6);
    align-items:center; justify-content:center; padding:20px;
  }
  #face-picker-modal.show { display:flex; }
  #face-picker-box {
    background:#0d1520; border:1px solid var(--border); border-radius:18px; padding:20px;
    max-width:380px; width:100%; max-height:80vh; overflow-y:auto;
  }
  #face-preset-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; }
  .preset-tile {
    display:flex; flex-direction:column; align-items:center; gap:4px; padding:8px 2px;
    border-radius:12px; border:2px solid var(--border); background:#080e15; cursor:pointer;
  }
  .preset-tile.active { border-color:var(--accent); box-shadow:0 0 0 3px rgba(0,201,255,.2); }
  .preset-tile .p-emoji { font-size:26px; }
  .preset-tile .p-label { font-size:9px; color:var(--sub); text-align:center; line-height:1.2; }
  #face-widget .greet-ring { width:320px; height:320px; margin:44px auto 16px; overflow:visible; }
  #face-widget .greet-name { font-size:24px; }
  #face-widget .greet-msg  { font-size:15px; max-height:110px; overflow-y:auto; }
  #widget-img { display:none; width:100%; border-radius:14px; margin-bottom:10px; }

  /* ── Aubie tab — full-screen talking face (UNO Q assistant/teacher) ──
     Reuses the one #face-widget: switchTab() relocates it into
     #aubie-face-mount while this tab is active, then puts it back. */
  #tab-aubie { padding: 0; }
  #aubie-stage {
    display:flex; flex-direction:column; align-items:center;
    padding:20px 14px 100px; min-height:calc(100vh - 130px);
  }
  #aubie-face-mount { width:100%; display:flex; justify-content:center; }
  #face-widget.fullscreen {
    position:static; right:auto; bottom:auto; z-index:auto;
    width:100%; max-width:460px; margin:0 auto;
    background:transparent; border:none; box-shadow:none; padding:0;
  }
  #face-widget.fullscreen #widget-close-btn { display:none; }
  #aubie-convo { width:100%; max-width:460px; }
  #aubie-transcript {
    max-height:32vh; overflow-y:auto; font-size:14px; line-height:1.5; padding:4px 0;
  }
  #aubie-transcript .u { color:var(--sub); margin-top:10px; }
  #aubie-transcript .a { color:var(--text); margin-top:3px; }
  #aubie-hold-talk.recording { background:var(--red); }

  /* ── Base animated face: eyes, nose, mouth — shared by every preset,
     including "the bug" - only colors/shape/accessories change per preset,
     never the animation itself (blink + talk). ─────────────────────────── */
  .aubie-face  { position:absolute; inset:0; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:14px; z-index:2; }
  .aubie-eyes  { display:flex; gap:34px; }
  .aubie-eye   { width:30px; height:30px; border-radius:50%; background:var(--eye-color,var(--green)); box-shadow:0 0 10px var(--eye-color,var(--green)); animation:ablink 4.5s infinite; }
  .greet-ring.recognized .aubie-eye { background:var(--gold); box-shadow:0 0 10px var(--gold); }
  @keyframes ablink { 0%,92%,100%{transform:scaleY(1)} 96%{transform:scaleY(.15)} }
  .aubie-nose  { width:14px; height:20px; border-radius:50% 50% 45% 45%/60% 60% 40% 40%; background:var(--nose-color,var(--eye-color,var(--green))); opacity:.85; }
  .aubie-mouth { width:66px; height:9px; border-radius:4px; background:var(--mouth-color,var(--green)); transition:.15s; }
  .greet-ring.recognized .aubie-mouth { background:var(--gold); border-radius:0 0 30px 30px; height:28px; width:76px; }
  .aubie-mouth.talking { animation:atalk .28s infinite alternate; }
  @keyframes atalk { from{height:9px} to{height:30px} }
  /* Mouth shape presets - a mood on top of the same animated bar */
  .greet-ring.mouth-smile .aubie-mouth { border-radius:0 0 34px 34px; height:26px; width:78px; }
  .greet-ring.mouth-frown .aubie-mouth { border-radius:34px 34px 0 0; height:26px; width:78px; margin-top:-10px; }
  .greet-ring.mouth-open  .aubie-mouth { border-radius:50%; width:28px; height:28px; }
  .greet-ring.eyes-closed .aubie-eye { height:6px; border-radius:3px; animation:none; }

  /* ── Aya Huma preset — Kichwa ceremonial figure, Inti Raymi ────────────
     Duality (hot/cold, life/death) as a warm/cool split face; a 12-horn
     crown for the 12 months; 4 marks at N/S/E/W for the two noses and two
     ears facing the cardinal directions. Decorative CSS approximation, not
     a literal mask replica. */
  .greet-ring.theme-huma { background:linear-gradient(125deg,#ff7a1a 0 48%, #123a8f 52% 100%); }
  .greet-ring.theme-huma .aubie-eye { background:#fff6d8; box-shadow:0 0 10px #fff6d8; }
  .greet-ring.theme-huma .aubie-mouth, .greet-ring.theme-huma .aubie-nose { background:#fff6d8; }
  .greet-ring.theme-huma.recognized { background:linear-gradient(125deg,#ffb200 0 48%, #1c56c9 52% 100%); }
  .horn {
    display:none; position:absolute; top:50%; left:50%; width:10px; height:40px;
    /* Positioned pointing up from the ring's edge (160px radius), then rotated
       around the ring's true center - margin-top and transform-origin's Y
       must both equal ring-radius + horn-height (160+40=200) for this to pivot
       correctly; keep in sync if the ring size (line ~406) ever changes. */
    margin:-200px 0 0 -5px;
    background:linear-gradient(to top,#c9720a,#ffe28a); border-radius:50% 50% 3px 3px;
    transform-origin:50% 200px; z-index:1;
  }
  .greet-ring.theme-huma .horn { display:block; }
  .huma-mark {
    display:none; position:absolute; width:16px; height:16px; border-radius:50%;
    background:#ffe28a; box-shadow:0 0 8px #ffb300; z-index:1;
  }
  .greet-ring.theme-huma .huma-mark { display:block; }
  .huma-nose.north { top:-6px; left:50%; margin-left:-8px; }
  .huma-nose.south { bottom:-6px; left:50%; margin-left:-8px; }
  .huma-ear.east   { top:50%; right:-6px; margin-top:-8px; }
  .huma-ear.west   { top:50%; left:-6px; margin-top:-8px; }

  /* ── Shared accessory slots — created once, hidden by default, shown per
     preset via .acc-* flags on #greet-ring. Positions assume the 320px ring
     above; rescale if that size changes. ──────────────────────────────── */
  .acc-brow-l, .acc-brow-r, .acc-glass-l, .acc-glass-r, .acc-glass-bridge,
  .acc-ear-l, .acc-ear-r, .acc-antenna-l, .acc-antenna-r,
  .acc-heart, .acc-zzz, .acc-tear, .acc-sparkle { display:none; position:absolute; z-index:3; }
  .greet-ring.acc-brows .acc-brow-l, .greet-ring.acc-brows .acc-brow-r { display:block; }
  .greet-ring.acc-glasses .acc-glass-l, .greet-ring.acc-glasses .acc-glass-r, .greet-ring.acc-glasses .acc-glass-bridge { display:block; }
  .greet-ring.acc-ears .acc-ear-l, .greet-ring.acc-ears .acc-ear-r { display:block; }
  .greet-ring.acc-antennae .acc-antenna-l, .greet-ring.acc-antennae .acc-antenna-r { display:block; }
  .greet-ring.acc-heart .acc-heart { display:block; }
  .greet-ring.acc-zzz .acc-zzz { display:block; }
  .greet-ring.acc-tear .acc-tear { display:block; }
  .greet-ring.acc-sparkles .acc-sparkle { display:block; }

  .acc-brow-l { width:38px; height:8px; border-radius:4px; background:#3a2a1a; top:36%; left:26%; transform:rotate(-10deg); }
  .acc-brow-r { width:38px; height:8px; border-radius:4px; background:#3a2a1a; top:36%; right:26%; transform:rotate(10deg); }
  .greet-ring.preset-angry .acc-brow-l { transform:rotate(18deg); top:38%; }
  .greet-ring.preset-angry .acc-brow-r { transform:rotate(-18deg); top:38%; }
  .greet-ring.preset-angry .acc-brow-l, .greet-ring.preset-angry .acc-brow-r { background:#ff4444; }

  .acc-glass-l, .acc-glass-r { width:56px; height:56px; border-radius:50%; top:32%; border:5px solid var(--glass-color,#dfe7ee); background:transparent; }
  .acc-glass-l { left:16%; } .acc-glass-r { right:16%; }
  .acc-glass-bridge { width:24px; height:5px; background:var(--glass-color,#dfe7ee); top:calc(32% + 25px); left:50%; margin-left:-12px; }
  .greet-ring.preset-cool .acc-glass-l, .greet-ring.preset-cool .acc-glass-r { background:#111; }
  .greet-ring.preset-cool .acc-glass-bridge { background:#111; }

  .acc-ear-l, .acc-ear-r { width:80px; height:130px; background:#6b4a24; border-radius:50% 50% 50% 50%/60% 60% 40% 40%; top:-40px; z-index:0; }
  .acc-ear-l { left:-24px; transform:rotate(-18deg); }
  .acc-ear-r { right:-24px; transform:rotate(18deg); }

  .acc-antenna-l, .acc-antenna-r { width:5px; height:50px; background:#8aff00; top:-42px; border-radius:3px; }
  .acc-antenna-l { left:38%; transform:rotate(-22deg); transform-origin:bottom; }
  .acc-antenna-r { right:38%; transform:rotate(22deg); transform-origin:bottom; }
  .acc-antenna-l::after, .acc-antenna-r::after { content:''; position:absolute; top:-8px; left:-3px; width:11px; height:11px; border-radius:50%; background:#8aff00; box-shadow:0 0 6px #8aff00; }

  .acc-heart { top:-38px; left:50%; margin-left:-16px; font-size:32px; }
  .acc-heart::before { content:'❤️'; }
  .acc-zzz { top:6%; right:8%; font-size:24px; color:#cdd8e6; font-weight:800; }
  .acc-zzz::before { content:'Z z z'; }
  .acc-tear { top:52%; left:32%; width:12px; height:16px; border-radius:50% 50% 50% 0; background:#5599ff; transform:rotate(45deg); }
  .acc-sparkle { font-size:22px; color:#ffee00; }
  .acc-sparkle:nth-of-type(1) { top:2%; left:10%; }
  .acc-sparkle:nth-of-type(2) { top:-6%; right:16%; }
  .acc-sparkle:nth-of-type(3) { bottom:4%; left:4%; }
  .acc-sparkle::before { content:'✦'; }
  .known-person { display:flex; align-items:center; gap:10px; padding:8px 12px;
    background:#080e15; border:1px solid var(--border); border-radius:10px; margin-bottom:6px; }
  .known-avatar { width:36px;height:36px;border-radius:50%;background:var(--accent);
    display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0; }
  .known-info { flex:1; }
  .known-name { font-size:14px; font-weight:700; color:var(--text); }
  .known-sub  { font-size:11px; color:var(--sub); }

  /* ── Progress ── */
  .track-row { display:flex; align-items:center; gap:10px; margin-bottom:10px; }
  .track-name { font-size:12px; color:var(--text); width:90px; flex-shrink:0; }
  .track-bar { flex:1; background:#0d1520; border-radius:20px; height:8px; overflow:hidden; }
  .track-fill { height:100%; border-radius:20px; background:linear-gradient(90deg,var(--accent),var(--purple)); transition:width .6s; }
  .track-pct { font-size:11px; color:var(--sub); width:32px; text-align:right; }
  .streak-badge { background:#1a1000; border:1px solid var(--gold); border-radius:10px;
    padding:10px 14px; text-align:center; }
  .streak-num { font-size:28px; font-weight:800; color:var(--gold); }
  .streak-lbl { font-size:10px; color:#888; }

  /* ── Daily Question ── */
  .cosmos-q { font-size:16px; font-weight:700; color:var(--purple); line-height:1.4;
    padding:14px; background:#0d0a1a; border:1px solid #2a1a4a; border-radius:var(--radius);
    margin-bottom:10px; }
  .cosmos-meta { font-size:10px; color:var(--sub); margin-bottom:10px; }

  /* ── Memory ── */
  .mem-entry { padding:10px 12px; border-left:3px solid var(--border); margin-bottom:8px;
    font-size:12px; color:var(--sub); line-height:1.5; border-radius:0 8px 8px 0;
    background:#080e15; }
  .mem-entry .mem-q { color:var(--text); font-weight:600; margin-bottom:3px; }
  .mem-entry .mem-ts { font-size:10px; color:#445; }

  /* ── Live Vision toggle ── */
  .vision-live-bar { display:flex; align-items:center; gap:10px; margin-bottom:10px; }
  .live-dot { width:9px; height:9px; border-radius:50%; background:var(--red); flex-shrink:0; }
  .live-dot.on { background:var(--green); box-shadow:0 0 6px var(--green); animation:blink 1.2s infinite; }
  @keyframes blink{0%,100%{opacity:1}50%{opacity:.4}}
  .vision-feed { width:100%; border-radius:10px; border:1px solid var(--border);
    background:#050d15; min-height:140px; display:flex; align-items:center; justify-content:center;
    color:var(--sub); font-size:12px; overflow:hidden; position:relative; }
  .vision-feed img { width:100%; border-radius:10px; }
  .vision-caption { font-size:12px; color:var(--text); line-height:1.6; margin-top:8px;
    padding:10px; background:#050d15; border:1px solid var(--border); border-radius:10px; }
</style>
</head>
<body>

<!-- ════════════════════════════════════════════════════════════════════
     TAB 1 — TEACHING STATION
════════════════════════════════════════════════════════════════════ -->
<div id="tab-teach" class="tab-panel active">

<header>
  <div>
    <div class="logo">AUBIE<span>ETERNAL</span></div>
    <div class="tagline">Teaching Station · Always On</div>
  </div>
  <div style="display:flex;align-items:center;gap:10px">
    <label style="display:flex;align-items:center;gap:5px;cursor:pointer;font-size:11px;color:var(--sub)">
      <span>🔊</span>
      <div style="position:relative;width:36px;height:20px">
        <input type="checkbox" id="speak-toggle" style="opacity:0;width:0;height:0;position:absolute"
          onchange="toggleSpeaker(this.checked)">
        <div id="speak-track" style="position:absolute;inset:0;background:#1e2d3d;border-radius:20px;transition:.2s"></div>
        <div id="speak-thumb" style="position:absolute;top:3px;left:3px;width:14px;height:14px;background:#444;border-radius:50%;transition:.2s"></div>
      </div>
    </label>
    <div class="dot" id="status-dot"></div>
  </div>
</header>

<!-- ── WELCOME / ABOUT ─────────────────────────────────────────────── -->
<div id="welcome-card" class="card" style="background:linear-gradient(135deg,#070f1a,#001830);border:1px solid #00c9ff33;position:relative;overflow:hidden">
  <div style="position:absolute;top:-30px;right:-30px;font-size:120px;opacity:0.04;pointer-events:none">🧠</div>
  <div style="font-size:11px;color:var(--accent);font-weight:800;letter-spacing:2px;margin-bottom:8px">WHAT IS THIS?</div>
  <div style="font-size:18px;font-weight:800;color:var(--text);margin-bottom:10px;line-height:1.3">
    Your Always-On AI Teaching Station
  </div>
  <div style="font-size:13px;color:#8aaccc;line-height:1.75;margin-bottom:14px">
    <b style="color:var(--text)">AUBIEETERNAL</b> is a free, always-on AI teacher built to give world-class education to <i>anyone, anywhere</i> — a phone, a touchscreen, a kitchen table, an orphanage.<br><br>
    Ask it anything. It teaches. It remembers every lesson, every question, every conversation — building a picture of what you know and what you're learning.<br><br>
    As you add courses, robots, and AI tools, <b style="color:var(--accent)">Aubie grows with you</b> — always remembering, always teaching.
  </div>
  <div style="display:flex;gap:8px;flex-wrap:wrap">
    <button class="btn btn-accent btn-sm" onclick="askWhatIsAubie()" style="flex:1">🤖 Ask Aubie What It Is</button>
    <button class="btn btn-sm" onclick="document.getElementById('welcome-card').style.display='none'" style="flex:0;background:#0d1520;border:1px solid var(--border);color:var(--sub)">✕ Hide</button>
  </div>
  <div class="resp" id="about-resp" style="margin-top:10px"></div>
</div>

<!-- ── CAMERA UNLOCK BANNER ──────────────────────────────────────── -->
<!-- Content is filled in by JS (insecureOriginFixHTML()) at page load,
     not hardcoded here - the right flags:// URL depends on which browser
     is actually running (Chrome on most Android tablets, not Edge), and
     the right origin to paste depends on which address (LAN/Tailscale/
     hostname) was actually used to reach this page. -->
<div id="cam-unlock-banner" class="card" style="background:linear-gradient(135deg,#1a0800,#3d1200);border:1px solid #ff520066;display:none">
  <div style="font-size:11px;color:#ff8844;font-weight:800;letter-spacing:1.5px;margin-bottom:8px">📵 CAMERA BLOCKED</div>
  <div style="font-size:13px;color:#ffccaa;line-height:1.8;margin-bottom:12px" id="cam-unlock-intro"></div>
  <div style="background:#0d0800;border-radius:10px;padding:12px;font-size:13px;color:#ffeecc;line-height:2;font-family:monospace" id="cam-unlock-steps"></div>
  <button class="btn btn-sm" onclick="document.getElementById('cam-unlock-banner').style.display='none'"
    style="margin-top:10px;background:#0d1520;border:1px solid var(--border);color:var(--sub)">✕ Dismiss</button>
</div>

<!-- ── GREET MODE ─────────────────────────────────────────────────── -->
<div class="card" style="background:linear-gradient(135deg,#0a1500,#001a08);border:1px solid #00e67633">
  <div class="card-title">👋 Greet Mode · Who's Here?</div>
  <p style="font-size:12px;color:var(--sub);margin-bottom:10px" id="greet-mode-intro">
    Tap Watch and Aubie's face appears in the floating widget (bottom-right, stays visible on any tab) - it recognizes who walks in, and you can talk to it any time with "hey aubie" until you tap Stop.
  </p>
  <div class="g2" id="greet-mode-buttons">
    <button class="btn btn-green btn-sm" id="greet-btn" onclick="toggleGreetMode()">👁️ Watch</button>
    <button class="btn btn-accent btn-sm" onclick="switchTab('teach');setTimeout(()=>document.getElementById('enroll-section').scrollIntoView({behavior:'smooth'}),100)">➕ Add Person</button>
  </div>
  <div style="margin-top:12px">
    <div style="font-size:11px;color:var(--sub);margin-bottom:6px">OR TYPE A QUESTION:</div>
    <div class="g2">
      <input id="watch-ask-input" type="text" placeholder="Type a question for Aubie…"
        onkeydown="if(event.key==='Enter')sendWatchAsk()"
        style="background:#0d1520;border:1px solid var(--accent);border-radius:12px;padding:12px;color:var(--text);font-size:15px">
      <button class="btn btn-accent btn-sm" onclick="sendWatchAsk()">💬 Ask</button>
    </div>
    <div class="resp" id="watch-ask-resp" style="margin-top:10px"></div>
  </div>
  <div style="margin-top:12px">
    <div style="font-size:11px;color:var(--sub);margin-bottom:6px">AUBIE KNOWS:</div>
    <div id="known-list"><div style="font-size:12px;color:var(--sub)">Loading…</div></div>
  </div>
</div>

<!-- ── ENROLL FACE — iPhone-style alignment ────────────────────────── -->
<div class="card" id="enroll-section" style="background:linear-gradient(135deg,#070b14,#0a0f1a)">
  <div class="card-title">🪪 Teach Aubie a Face</div>

  <!-- Name -->
  <input id="enroll-name" type="text" placeholder="Who is this? (e.g. Matthew, Gabriela…)"
    style="width:100%;background:#0d1520;border:1px solid var(--accent);border-radius:12px;
    padding:14px;color:var(--text);font-size:16px;margin-bottom:12px">

  <!-- Camera viewfinder (hidden until started) -->
  <div id="enroll-viewfinder" style="display:none;position:relative;border-radius:16px;overflow:hidden;
    background:#000;margin-bottom:12px;aspect-ratio:3/4;max-height:480px">

    <!-- Live video -->
    <video id="enroll-video" autoplay playsinline muted
      style="width:100%;height:100%;object-fit:cover;display:block"></video>

    <!-- Oval overlay — darkened outside, glowing oval ring -->
    <svg id="enroll-svg" viewBox="0 0 300 400" xmlns="http://www.w3.org/2000/svg"
      style="position:absolute;inset:0;width:100%;height:100%;pointer-events:none">
      <defs>
        <mask id="face-oval-mask">
          <rect fill="white" width="300" height="400"/>
          <ellipse cx="150" cy="185" rx="105" ry="140" fill="black"/>
        </mask>
        <filter id="glow">
          <feGaussianBlur stdDeviation="3" result="blur"/>
          <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
      </defs>
      <!-- Dark vignette outside oval -->
      <rect fill="rgba(0,0,0,0.55)" width="300" height="400" mask="url(#face-oval-mask)"/>
      <!-- Glowing oval ring -->
      <ellipse id="enroll-ring" cx="150" cy="185" rx="105" ry="140"
        fill="none" stroke="#00c9ff" stroke-width="3" filter="url(#glow)" opacity="0.9"/>
      <!-- Corner tick marks (iPhone Face ID style) -->
      <g stroke="#00c9ff" stroke-width="2.5" stroke-linecap="round" opacity="0.7">
        <!-- top-left -->
        <path d="M 52 80 Q 45 70 55 62"/>
        <!-- top-right -->
        <path d="M 248 80 Q 255 70 245 62"/>
        <!-- bottom-left -->
        <path d="M 52 300 Q 45 310 55 318"/>
        <!-- bottom-right -->
        <path d="M 248 300 Q 255 310 245 318"/>
      </g>
    </svg>

    <!-- Instruction label -->
    <div id="enroll-hint" style="position:absolute;bottom:14px;left:0;right:0;text-align:center;
      font-size:14px;font-weight:700;color:#fff;text-shadow:0 1px 6px #000;letter-spacing:0.5px">
      Center your face in the oval
    </div>

    <!-- Captured preview flash -->
    <div id="enroll-flash" style="position:absolute;inset:0;background:#fff;opacity:0;pointer-events:none;border-radius:16px;transition:opacity 0.05s"></div>
  </div>

  <!-- Buttons -->
  <div class="g2" style="margin-bottom:0">
    <button class="btn btn-purple btn-sm" id="enroll-cam-btn" onclick="startEnrollCamera()">📷 Open Camera</button>
    <button class="btn btn-green btn-sm" id="enroll-snap-btn" onclick="snapAndEnroll()" style="display:none">📸 Snap &amp; Save</button>
  </div>
  <button class="btn btn-accent btn-sm" onclick="loadKnownPeople()" style="margin-top:8px">↻ Refresh List</button>
  <div class="resp" id="enroll-resp" style="margin-top:10px"></div>
</div>

<!-- Ask / Teach -->
<div class="card">
  <div class="card-title">🧠 Ask · Learn · Teach</div>
  <textarea id="ask-input" rows="4" placeholder="Ask anything…&#10;Explain photosynthesis · What is recursion? · Help me understand algebra · What is Bitcoin?"
    style="font-size:16px;padding:14px;line-height:1.5;border-color:var(--accent)"></textarea>
  <div class="g2" style="margin-top:10px">
    <button class="btn btn-accent" onclick="sendAsk()" style="font-size:16px;padding:15px">⚡ Ask Aubie</button>
    <button class="btn btn-sm" onclick="newConversation()" style="background:#0d1520;border:1px solid var(--border);color:var(--sub)">🔄 New Conversation</button>
  </div>
  <div class="resp" id="ask-resp" style="font-size:14px;line-height:1.8"></div>
</div>

<!-- Voice -->
<div class="card">
  <div class="card-title">🎤 Voice</div>
  <div class="mic-ring" id="mic-btn" onclick="toggleMic()">🎤</div>
  <div class="mic-lbl" id="mic-lbl">Tap to speak to Aubie</div>
  <div class="resp" id="voice-resp"></div>
  <div style="margin-top:14px">
    <div style="font-size:11px;color:var(--sub);margin-bottom:6px">AUBIE'S VOICE:</div>
    <div class="g2">
      <select id="voice-preset-select" onchange="selectVoicePreset()"
        style="background:#0d1520;border:1px solid var(--accent);border-radius:12px;padding:12px;color:var(--text);font-size:15px">
        <option value="">Loading…</option>
      </select>
      <button class="btn btn-sm" onclick="previewVoicePreset()" style="background:#0d1520;border:1px solid var(--border);color:var(--sub)">🔊 Preview</button>
    </div>
  </div>
</div>

<!-- Quick Topics -->
<div class="card">
  <div class="card-title">📚 Quick Topics</div>
  <div class="g3">
    <div class="topic-chip" onclick="quickTopic('Explain how computers work in simple terms')"><div class="topic-icon">💻</div>Computers</div>
    <div class="topic-chip" onclick="quickTopic('Teach me basic algebra step by step')"><div class="topic-icon">➗</div>Math</div>
    <div class="topic-chip" onclick="quickTopic('Explain the water cycle and why it matters')"><div class="topic-icon">🌍</div>Science</div>
    <div class="topic-chip" onclick="quickTopic('What is Python and how do I start coding?')"><div class="topic-icon">🐍</div>Python</div>
    <div class="topic-chip" onclick="quickTopic('Explain how the human brain learns new things')"><div class="topic-icon">🧬</div>Biology</div>
    <div class="topic-chip" onclick="quickTopic('Give me a history lesson on how the internet was invented')"><div class="topic-icon">📡</div>History</div>
    <div class="topic-chip" onclick="quickTopic('Teach me 10 Spanish words with pronunciation tips')"><div class="topic-icon">🗣️</div>Language</div>
    <div class="topic-chip" onclick="quickTopic('Explain artificial intelligence to a beginner')"><div class="topic-icon">🤖</div>AI</div>
    <div class="topic-chip" onclick="quickTopic('What is the best way to build a daily study habit?')"><div class="topic-icon">📖</div>Study</div>
  </div>
</div>

<!-- Camera -->
<div class="card">
  <div class="card-title">📷 Camera · Vision</div>
  <div class="g2">
    <button class="btn btn-purple btn-sm" onclick="takeSnapshot()">📸 Snapshot</button>
    <button class="btn btn-accent btn-sm" onclick="describeScene()">👁️ Describe</button>
  </div>
  <img id="cam-preview" style="width:100%;border-radius:10px;margin-top:10px;display:none" alt="" />
  <div class="resp" id="cam-resp"></div>
</div>

<!-- ── SHOW ME (Unsplash Image Search) ──────────────────────────── -->
<div class="card">
  <div class="card-title">🖼️ Show Me</div>
  <textarea id="showme-input" rows="2"
    placeholder="Type what you want to see…&#10;a galaxy · a wolf · the Eiffel Tower · a coral reef"
    style="width:100%;background:#0d1520;border:1px solid var(--accent);border-radius:12px;
    color:var(--text);font-size:16px;padding:14px;font-family:inherit;resize:none;outline:none;
    margin-bottom:10px;line-height:1.5"
    onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();showMeImage();}"></textarea>
  <button class="btn btn-purple" onclick="showMeImage()" style="margin-top:0;font-size:16px;padding:15px">🖼️ Show Me</button>
  <div id="showme-status" style="font-size:12px;color:var(--sub);margin-top:8px;display:none"></div>
  <div id="showme-frame" style="display:none;border-radius:12px;overflow:hidden;position:relative;margin-top:10px">
    <img id="showme-img" src="" alt="" style="width:100%;border-radius:12px;display:block" />
    <div id="showme-caption" style="position:absolute;bottom:0;left:0;right:0;
      background:linear-gradient(transparent,rgba(0,0,0,.8));padding:10px 14px 12px;
      font-size:13px;color:#fff;font-weight:600"></div>
  </div>
  <div style="display:none;gap:8px;margin-top:10px" id="showme-actions">
    <button class="btn btn-accent" onclick="showMeNext()" style="flex:1;margin-top:0">🔄 Another</button>
    <button class="btn" onclick="showMeOnScreen()" style="flex:1;margin-top:0;background:#0d1520;border:1px solid var(--border);color:var(--sub)">📺 Also on Screen</button>
  </div>
</div>

<!-- ── TODAY'S LESSON ─────────────────────────────────────────────── -->
<div class="card">
  <div class="card-title">📚 Today's Lesson</div>
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
    <div style="font-size:11px;color:var(--sub)">👋 Who's learning?</div>
    <div style="font-size:11px;color:var(--accent);cursor:pointer" onclick="togglePersonEditor()">✏️ Customize</div>
  </div>
  <div class="g3" id="people-chips" style="margin-top:0;margin-bottom:12px">
    <div class="topic-chip">…</div>
  </div>
  <div id="person-editor" style="display:none;background:#0d1520;border:1px solid var(--border);border-radius:12px;padding:12px;margin-bottom:12px">
    <input id="pe-name" type="text" placeholder="Name (e.g. Dad, Gabriela)" maxlength="40"
      style="width:100%;background:#050d15;border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:14px;padding:9px;margin-bottom:8px;outline:none">
    <select id="pe-level" style="width:100%;background:#050d15;border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:14px;padding:9px;margin-bottom:8px;outline:none">
      <option value="kid">🧒 Kid — simple, warm, encouraging</option>
      <option value="teen">🧑 Teen — clear and direct</option>
      <option value="adult">🧑‍🎓 Adult — normal adult level</option>
      <option value="expert">🎓 Expert — advanced, technical, can be challenged</option>
    </select>
    <input id="pe-note" type="text" placeholder="Optional note (e.g. PhD in physics)" maxlength="80"
      style="width:100%;background:#050d15;border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:14px;padding:9px;margin-bottom:8px;outline:none">
    <select id="pe-face" style="width:100%;background:#050d15;border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:14px;padding:9px;margin-bottom:10px;outline:none">
      <option value="">No linked face (manual chip-tap only)</option>
    </select>
    <div style="font-size:10px;color:var(--sub);margin:-4px 0 10px">Link a face so Watch Mode auto-picks this person when it recognizes them — enroll faces via 🪪 Teach Aubie a Face below.</div>
    <div class="g2" style="margin-top:0">
      <button class="btn btn-accent btn-sm" onclick="savePersonProfile()">💾 Save</button>
      <button class="btn btn-sm" onclick="togglePersonEditor()" style="background:#0d1520;border:1px solid var(--border);color:var(--sub)">✕ Cancel</button>
    </div>
  </div>
  <div id="lesson-card" class="lesson-card" onclick="startClass()">
    <div class="lesson-tag">LOADING…</div>
    <div class="lesson-title" id="lesson-title">Fetching today's lesson…</div>
    <div class="lesson-desc" id="lesson-desc"></div>
    <span class="lesson-start">▶ Start Lesson</span>
  </div>
  <div class="resp" id="lesson-resp"></div>
</div>

<!-- ── RESEARCH ──────────────────────────────────────────────────── -->
<div class="card">
  <div class="card-title">🔍 Research</div>
  <textarea id="research-input" rows="2"
    placeholder="What do you want to research?&#10;black holes · Bitcoin · DNA · quantum computing · volcanoes…"
    style="width:100%;background:#0d1520;border:1px solid var(--accent);border-radius:12px;
    color:var(--text);font-size:16px;padding:14px;font-family:inherit;resize:none;outline:none;
    margin-bottom:10px;line-height:1.5"
    onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendResearch();}"></textarea>
  <button class="btn btn-accent" onclick="sendResearch()" style="margin-top:0;font-size:16px;padding:15px">🔍 Research It</button>
  <div class="resp" id="research-status" style="margin-top:10px"></div>
  <div class="research-result" id="research-result" style="display:none;font-size:14px;line-height:1.8"></div>
</div>

<!-- ── PROGRESS ──────────────────────────────────────────────────── -->
<div class="card">
  <div class="card-title">🎓 My Progress</div>
  <div style="display:flex;gap:10px;margin-bottom:14px">
    <div class="streak-badge" style="flex:1">
      <div class="streak-num" id="streak-num">—</div>
      <div class="streak-lbl">DAY STREAK</div>
    </div>
    <div class="streak-badge" style="flex:1;border-color:var(--purple)">
      <div class="streak-num" style="color:var(--purple)" id="topics-num">—</div>
      <div class="streak-lbl">TOPICS DONE</div>
    </div>
    <div class="streak-badge" style="flex:1;border-color:var(--green)">
      <div class="streak-num" style="color:var(--green)" id="asks-num">—</div>
      <div class="streak-lbl">QUESTIONS</div>
    </div>
  </div>
  <div id="track-bars"></div>
  <button class="btn btn-accent btn-sm" onclick="loadProgress()" style="margin-top:6px">↻ Refresh Progress</button>
</div>

<!-- ── DAILY QUESTION ────────────────────────────────────────────── -->
<div class="card">
  <div class="card-title">🌌 Daily Question</div>
  <div class="cosmos-meta" id="cosmos-date"></div>
  <div class="cosmos-q" id="cosmos-q">Loading today's question…</div>
  <div class="g2">
    <button class="btn btn-purple btn-sm" onclick="answerCosmos()">💬 Discuss with Aubie</button>
    <button class="btn btn-accent btn-sm" onclick="loadCosmos()">🎲 New Question</button>
  </div>
  <div class="resp" id="cosmos-resp"></div>
</div>

<!-- ── MEMORY ────────────────────────────────────────────────────── -->
<div class="card">
  <div class="card-title">🧠 What Aubie Remembers</div>
  <div id="memory-list"><div style="color:var(--sub);font-size:12px">Loading memory…</div></div>
  <button class="btn btn-accent btn-sm" onclick="loadMemory()" style="margin-top:8px">↻ Refresh Memory</button>
</div>

<!-- ── LIVE VISION ───────────────────────────────────────────────── -->
<div class="card">
  <div class="card-title">👁️ Live Vision</div>
  <div class="vision-live-bar">
    <div class="live-dot" id="live-dot"></div>
    <span style="font-size:12px;color:var(--sub)" id="live-lbl">Camera off — tap to go live</span>
    <button class="btn btn-accent btn-sm" onclick="toggleLiveVision()" style="margin-left:auto" id="live-btn">▶ Go Live</button>
  </div>
  <div class="vision-feed" id="vision-feed">📷 Camera not active</div>
  <div class="vision-caption" id="vision-caption" style="display:none"></div>
</div>

<!-- System / Log -->
<div class="card">
  <div class="card-title">⚡ System</div>
  <div class="g2">
    <button class="btn btn-green btn-sm" onclick="checkHealth()">✅ Health</button>
    <button class="btn btn-red btn-sm" onclick="clearLog()">🗑️ Clear Log</button>
  </div>
  <div class="g2" style="margin-top:8px">
    <button class="btn btn-purple btn-sm" onclick="probeEndpoints()">🔍 Find Chat Endpoint</button>
    <button class="btn btn-teal btn-sm" onclick="resetEndpointCache()">🔄 Reset Cache</button>
  </div>
  <div class="resp" id="probe-resp" style="margin-top:8px"></div>
</div>
<div class="card">
  <div class="card-title">📋 Log</div>
  <div id="log">&gt; AUBIEETERNAL Teaching Station ready.</div>
</div>

</div><!-- /tab-teach -->


<!-- ════════════════════════════════════════════════════════════════════
     TAB 2 — BUILD CODE
════════════════════════════════════════════════════════════════════ -->
<div id="tab-build" class="tab-panel">

<div class="build-header">
  <div>
    <div class="blogo">⚙️ BUILD CODE</div>
    <div class="bsub">Dual-Road Orchestrator · Agentic Loop · Auto-Fix</div>
  </div>
</div>

<!-- Main build card -->
<div class="card">
  <div class="card-title">🔨 What Should Aubie Build?</div>
  <textarea id="build-input" rows="4" placeholder="Describe what to build…&#10;&#10;Examples:&#10;• Write a function that finds prime numbers&#10;• Build a script that reads a CSV and prints stats&#10;• Create a password generator with symbols"></textarea>
  <button class="btn btn-gold" onclick="sendBuild()">⚙️ Build &amp; Run</button>
  <div class="resp" id="build-status"></div>
</div>

<!-- Code output -->
<div class="card">
  <div class="card-title">📄 Generated Code</div>
  <div class="code-out" id="build-code" style="max-height:380px"></div>
  <div id="build-iter" style="display:none" class="iter-badge">✅ <span id="build-iter-text"></span></div>
</div>

<!-- Quick build prompts -->
<div class="card">
  <div class="card-title">⚡ Quick Builds</div>
  <div class="g2">
    <button class="btn btn-teal btn-sm" onclick="quickBuild('Write a Python function that checks if a word is a palindrome and tests it with 5 examples')">🔤 Palindrome</button>
    <button class="btn btn-teal btn-sm" onclick="quickBuild('Write a Python script that generates the first 20 fibonacci numbers and prints them')">🔢 Fibonacci</button>
    <button class="btn btn-teal btn-sm" onclick="quickBuild('Write a Python function that sorts a list of names alphabetically and prints the result')">🔠 Sort Names</button>
    <button class="btn btn-teal btn-sm" onclick="quickBuild('Write a Python script that simulates rolling two dice 1000 times and shows the frequency of each sum')">🎲 Dice Sim</button>
    <button class="btn btn-teal btn-sm" onclick="quickBuild('Write a Python Caesar cipher encoder and decoder and test it with a sample message')">🔐 Caesar Cipher</button>
    <button class="btn btn-teal btn-sm" onclick="quickBuild('Write a Python script that prints a multiplication table from 1 to 12')">✖️ Times Table</button>
  </div>
</div>

<!-- How it works -->
<div class="card" style="border-color:#2a3d1a">
  <div class="card-title" style="color:#608040">🧠 How Build Code Works</div>
  <p style="font-size:12px;color:var(--sub);line-height:1.8">
    1. Your request goes to <strong style="color:var(--gold)">two Qwen models in parallel</strong> (dual-road)<br>
    2. Aubie compares both answers and synthesises the best code<br>
    3. The code is written to disk and <strong style="color:var(--green)">actually executed</strong><br>
    4. If it fails, the error is fed back → auto-fixed → re-run (up to 4×)<br>
    5. You get the final working code + output
  </p>
</div>

</div><!-- /tab-build -->


<!-- ════════════════════════════════════════════════════════════════════
     TAB 3 — ROBOT DOG
════════════════════════════════════════════════════════════════════ -->
<div id="tab-dog" class="tab-panel">

<div class="dog-header">
  <div>
    <div class="dlogo">🐕 AUBIE DOG</div>
    <div class="dsub">RC Remote · Drive Mode</div>
  </div>
  <div class="dog-dot" id="dog-dot"></div>
</div>

<!-- Joystick -->
<div class="card">
  <div class="card-title">🕹️ RC Control</div>
  <div class="joystick-wrap">
    <canvas id="joystick-canvas" width="200" height="200"></canvas>
  </div>
  <div style="text-align:center;font-size:11px;color:var(--sub);margin-top:6px" id="joy-readout">drag to move</div>
</div>

<!-- Movement -->
<div class="card">
  <div class="card-title">🦿 Movement</div>
  <div class="g3">
    <button class="btn btn-green btn-xs" onclick="dog('walk')">🚶 Walk</button>
    <button class="btn btn-teal btn-xs" onclick="dog('trot')">🏃 Trot</button>
    <button class="btn btn-accent btn-xs" onclick="dog('run')">💨 Run</button>
    <button class="btn btn-orange btn-xs" onclick="dog('sit')">🪑 Sit</button>
    <button class="btn btn-orange btn-xs" onclick="dog('lay_down')">😴 Lay Down</button>
    <button class="btn btn-orange btn-xs" onclick="dog('stand')">🧍 Stand</button>
    <button class="btn btn-purple btn-xs" onclick="dog('turn_left')">↺ Turn L</button>
    <button class="btn btn-purple btn-xs" onclick="dog('turn_right')">↻ Turn R</button>
    <button class="btn btn-red btn-xs" onclick="dog('stop')">🛑 Stop</button>
  </div>
</div>

<!-- Follow mode -->
<div class="card">
  <div class="card-title">👁️ Follow Mode</div>
  <div class="g2">
    <button class="btn btn-green btn-sm" onclick="dog('follow_on')">🟢 Follow ON</button>
    <button class="btn btn-red btn-sm" onclick="dog('follow_off')">🔴 Follow OFF</button>
  </div>
</div>

<!-- Face -->
<div class="card">
  <div class="card-title">😊 Face</div>
  <div class="g4">
    <div class="face-btn" onclick="dogFace('happy')" title="Happy">😊</div>
    <div class="face-btn" onclick="dogFace('surprised')" title="Surprised">😲</div>
    <div class="face-btn" onclick="dogFace('angry')" title="Angry">😠</div>
    <div class="face-btn" onclick="dogFace('cool')" title="Cool">😎</div>
    <div class="face-btn" onclick="dogFace('love')" title="Love">😍</div>
    <div class="face-btn" onclick="dogFace('sleep')" title="Sleep">😴</div>
    <div class="face-btn" onclick="dogFace('sad')" title="Sad">😢</div>
    <div class="face-btn" onclick="dogFace('crazy')" title="Crazy">🤪</div>
    <div class="face-btn" onclick="dogFace('bug')" title="Bug">🐛</div>
    <div class="face-btn" onclick="dogFace('mind')" title="Mind">🤯</div>
    <div class="face-btn" onclick="dog('flashlight_on')" title="Light ON">🔦</div>
    <div class="face-btn" onclick="dog('flashlight_off')" title="Light OFF">💡</div>
  </div>
</div>

<!-- Face customisation -->
<div class="card">
  <div class="card-title">🎨 Face Customise</div>
  <div style="margin-bottom:8px">
    <label style="font-size:11px;color:var(--sub)">Eyes</label>
    <select id="eye-sel" style="margin-top:4px">
      <option value="normal_eyes">Normal</option>
      <option value="dog_eyes">Dog Eyes</option>
      <option value="heart_eyes">Heart Eyes</option>
      <option value="dizzy_eyes">Dizzy Eyes</option>
    </select>
  </div>
  <div style="margin-bottom:8px">
    <label style="font-size:11px;color:var(--sub)">Mouth</label>
    <select id="mouth-sel" style="margin-top:4px">
      <option value="normal_mouth">Normal</option>
      <option value="dog_mouth">Dog Mouth</option>
      <option value="smile_mouth">Smile</option>
      <option value="sad_mouth">Sad</option>
    </select>
  </div>
  <button class="btn btn-orange" onclick="applyFace()" style="margin-top:6px">✅ Apply</button>
</div>

<!-- Tricks -->
<div class="card">
  <div class="card-title">🎪 Tricks</div>
  <div class="g3">
    <button class="btn btn-purple btn-sm" onclick="dog('dance_up')">💃 Dance</button>
    <button class="btn btn-purple btn-sm" onclick="dog('groove')">🕺 Groove</button>
    <button class="btn btn-purple btn-sm" onclick="dog('moonwalk')">🌕 Moonwalk</button>
  </div>
</div>

<!-- Princess Mode -->
<div class="card" style="border-color:#880088">
  <div class="card-title" style="color:#ff66ff">👑 Princess Mode</div>
  <button class="btn" style="background:linear-gradient(135deg,#6a006a,#ff00ff);margin-top:0" onclick="dog('princess_mode')">👑 Princess Mode · Sunrise</button>
</div>

<!-- Teach a Person -->
<div class="card">
  <div class="card-title">🧑‍🏫 Teach Aubie a Person</div>
  <input type="text" id="person-name" placeholder="Person's name…" style="margin-bottom:8px">
  <button class="btn btn-teal" onclick="teachPerson()" style="margin-top:0">📸 Capture &amp; Teach</button>
</div>

<!-- Servo Control -->
<div class="card">
  <div class="card-title">🔩 Servo Control</div>
  <div id="servo-sliders">
    <div class="slider-row"><label>FL</label><input type="range" min="-90" max="90" value="0" oninput="this.nextElementSibling.textContent=this.value" data-servo="fl"><span>0</span></div>
    <div class="slider-row"><label>FR</label><input type="range" min="-90" max="90" value="0" oninput="this.nextElementSibling.textContent=this.value" data-servo="fr"><span>0</span></div>
    <div class="slider-row"><label>BL</label><input type="range" min="-90" max="90" value="0" oninput="this.nextElementSibling.textContent=this.value" data-servo="bl"><span>0</span></div>
    <div class="slider-row"><label>BR</label><input type="range" min="-90" max="90" value="0" oninput="this.nextElementSibling.textContent=this.value" data-servo="br"><span>0</span></div>
    <div class="slider-row"><label>Yaw</label><input type="range" min="-90" max="90" value="0" oninput="this.nextElementSibling.textContent=this.value" data-servo="yaw"><span>0</span></div>
    <div class="slider-row"><label>Pitch</label><input type="range" min="-90" max="90" value="0" oninput="this.nextElementSibling.textContent=this.value" data-servo="pitch"><span>0</span></div>
    <div class="slider-row"><label>Roll</label><input type="range" min="-90" max="90" value="0" oninput="this.nextElementSibling.textContent=this.value" data-servo="roll"><span>0</span></div>
  </div>
  <div class="g2">
    <button class="btn btn-gold btn-sm" onclick="applyServos()">⚙️ Apply Pose</button>
    <button class="btn btn-red btn-sm" onclick="centerServos()">🎯 Centre All</button>
  </div>
</div>

<!-- Say / Command -->
<div class="card">
  <div class="card-title">💬 Say / Command</div>
  <div style="display:flex;gap:8px;margin-top:0">
    <input type="text" id="say-input" placeholder="Type something for Aubie to say…" style="flex:1">
    <button class="btn btn-accent btn-sm" style="width:auto;margin-top:0;padding:11px 16px" onclick="dogSay()">▶</button>
  </div>
</div>

<!-- Bluetooth -->
<div class="card">
  <div class="card-title">🔵 Bluetooth Setup</div>
  <p style="font-size:12px;color:var(--sub);margin-bottom:10px">Connect to Aubie via Bluetooth to change WiFi without needing network access.</p>
  <button class="btn btn-teal" onclick="dog('bluetooth_connect')" style="margin-top:0">🔵 Connect Bluetooth</button>
  <div id="bt-status" style="font-size:11px;color:var(--sub);margin-top:6px">Not connected</div>
</div>

</div><!-- /tab-dog -->


<!-- ═══════════ TAB — AUBIE · full-screen talking face (UNO Q assistant) ═══════════ -->
<div id="tab-aubie" class="tab-panel">
  <div id="aubie-stage">
    <div id="aubie-face-mount"><!-- #face-widget is moved in here while this tab is active --></div>
    <div id="aubie-convo">
      <div id="aubie-transcript"></div>
      <div class="g2" style="display:flex;gap:8px;margin-top:12px">
        <input id="aubie-chat-input" type="text" placeholder="Talk to Aubie…"
          onkeydown="if(event.key==='Enter')sendAubieChat()"
          style="flex:1;background:#0d1520;border:1px solid var(--accent);border-radius:12px;padding:12px;color:var(--text);font-size:15px">
        <button class="btn btn-accent btn-sm" onclick="sendAubieChat()">💬 Send</button>
      </div>
      <button id="aubie-hold-talk" class="btn btn-green" style="width:100%;margin-top:10px"
        onmousedown="startRecording()" onmouseup="stopRecordingAndSend()" onmouseleave="cancelRecordingIfActive()"
        ontouchstart="event.preventDefault();startRecording()" ontouchend="event.preventDefault();stopRecordingAndSend()">
        🎙️ Hold to Talk
      </button>
      <p style="font-size:11px;color:var(--sub);text-align:center;margin-top:8px">
        Hands-free “hey aubie” runs in Watch mode (Teach tab) and is always on when this is the kiosk screen.
      </p>
    </div>
  </div>
</div><!-- /tab-aubie -->


<!-- ── QR Airlock: scan a code, see the raw URL + verdict, never auto-open ── -->
<div id="tab-qr" class="tab-panel">
  <div class="card">
    <div class="card-title"><span>🔒</span> Check a QR code before you trust it</div>
    <p style="font-size:12px;color:var(--sub);margin:6px 0 12px">
      Point the camera at any QR code (a table sticker, a flyer, a parking sign).
      Aubie decodes it <b>on this device</b>, shows you the real link, and tells you
      what's known about it. It never opens the link for you.
    </p>
    <button class="btn btn-accent" style="width:100%" onclick="scanQR()">📷 Scan a QR code</button>
    <img id="qr-preview" style="display:none;width:100%;border-radius:12px;margin-top:10px" alt="">
    <div id="qr-resp" class="resp"></div>

    <div id="qr-result" style="display:none;margin-top:12px">
      <div id="qr-badge" style="display:inline-block;padding:5px 12px;border-radius:999px;
        font-weight:700;font-size:13px;letter-spacing:.02em"></div>
      <p style="font-size:11px;color:var(--sub);margin:10px 0 4px">The actual link inside this code:</p>
      <!-- Deliberately a <div>, never an <a>: selectable/copyable, never clickable, never auto-navigated. -->
      <div id="qr-url" style="font-family:ui-monospace,Menlo,Consolas,monospace;font-size:14px;
        background:#0d1520;border:1px solid var(--accent);border-radius:10px;padding:11px;
        word-break:break-all;user-select:all;-webkit-user-select:all"></div>
      <p id="qr-explain" style="font-size:13px;color:var(--text);margin:10px 0 4px;line-height:1.45"></p>
      <p id="qr-signals" style="font-size:11px;color:var(--sub);margin:0"></p>
      <p style="font-family:ui-monospace,Menlo,Consolas,monospace;font-size:10px;color:var(--sub);
        margin:8px 0 0;word-break:break-all">sha256: <span id="qr-hash"></span></p>

      <div class="g2" style="display:flex;flex-wrap:wrap;gap:8px;margin-top:14px">
        <button class="btn btn-teal btn-sm" onclick="qrCopyUrl()">📋 Copy URL</button>
        <button class="btn btn-sm" style="background:#1c2f45;color:#cfe8ff" onclick="qrAllow()">✅ Allow this month</button>
        <button class="btn btn-sm" style="background:#452020;color:#ffd7d7" onclick="qrShare()">🚩 Share flag</button>
      </div>
      <p style="font-size:10px;color:var(--sub);margin-top:8px">
        “Allow this month” only affects this household. “Share flag” queues a report for a
        human to review before anything is published — nothing is sent automatically.
      </p>
    </div>
  </div>
</div><!-- /tab-qr -->


<!-- ── Tab bar (6 tabs) ───────────────────────────────────────────────── -->
<div class="tabbar">
  <button class="tab-btn active" id="tbtn-teach" onclick="switchTab('teach')">
    <span class="tab-icon">🧠</span>Teach
  </button>
  <button class="tab-btn" id="tbtn-build" onclick="switchTab('build')">
    <span class="tab-icon">⚙️</span>Build
  </button>
  <button class="tab-btn" id="tbtn-dog" onclick="switchTab('dog')">
    <span class="tab-icon">🐕</span>Dog Remote
  </button>
  <button class="tab-btn" id="tbtn-aubie" onclick="switchTab('aubie')">
    <span class="tab-icon">🧑‍🏫</span>Aubie
  </button>
  <button class="tab-btn" id="tbtn-qr" onclick="switchTab('qr')">
    <span class="tab-icon">🔒</span>Scan QR
  </button>
  <button class="tab-btn" id="tbtn-portal" onclick="window.open('https://aubieeternal.tail00eb41.ts.net/portal','_blank')">
    <span class="tab-icon">🖥️</span>Portal
  </button>
</div>

<!-- ── Kiosk-only "back to home" button — only meaningful when this page was
     reached from the touchscreen kiosk's own home screen; harmless dead
     button otherwise (phone/tablet users just never see it, or can ignore
     it - the file:// URL simply won't resolve off that specific device). ── -->
<button id="kiosk-home-btn" onclick="location.href='file:///home/arduino/kiosk/home.html'"
  style="position:fixed;bottom:14px;left:14px;z-index:900;width:52px;height:52px;border-radius:50%;
  border:none;background:#1c2f45;color:#cfe8ff;font-size:24px;box-shadow:0 6px 18px rgba(0,0,0,.4);display:none">🏠</button>
<script>
  // Only show the kiosk home button when actually loaded on the kiosk
  // touchscreen itself (its own Tailscale/LAN address) - hidden for
  // everyone else (phone/tablet/desktop users on the real internet).
  if (location.hostname === '100.66.110.65' || location.hostname === '100.105.81.27') {
    document.getElementById('kiosk-home-btn').style.display = 'block';
    // The Watch button's "hey aubie" listening uses the browser's Web Speech
    // API, which the open-source `chromium` package on this device doesn't
    // actually support (missing the Google API key only proprietary Chrome
    // ships with) - it just silently never triggers here. The robot's own
    // aubie_listen.py already runs a fully local, working wake-word listener
    // independent of any browser, so on the kiosk, point to that instead of
    // offering a button that looks live but isn't.
    const btnRow = document.getElementById('greet-mode-buttons');
    if (btnRow) document.getElementById('greet-btn').style.display = 'none';
    const intro = document.getElementById('greet-mode-intro');
    if (intro) intro.textContent = 'Just say "hey aubie" any time - Aubie is always listening on this device, no button needed.';
  }
  // Kiosk quick-launch: ?kiosk_action=start-class in the URL (set by the
  // touchscreen's home screen when it navigates here) auto-starts the
  // lesson flow instead of making a kid type "let's go to class" themselves.
  window.addEventListener('load', () => {
    const params = new URLSearchParams(location.search);
    if (params.get('kiosk_action') === 'start-class') {
      setTimeout(() => { if (typeof startClass === 'function') startClass(); }, 500);
    }
  });
</script>

<!-- ── FLOATING FACE WIDGET — Watch mode, visible on every tab ─────────── -->
<div id="face-widget">
  <button class="btn btn-sm" onclick="openFacePicker()" style="width:100%;margin-bottom:12px;background:#0d1520;border:1px solid var(--border);color:var(--sub)">🎨 Customize Face</button>
  <img id="widget-img" alt="" />
  <div class="greet-ring" id="greet-ring">
    <div class="aubie-face" id="aubie-face">
      <div class="aubie-eyes">
        <div class="aubie-eye"></div>
        <div class="aubie-eye"></div>
      </div>
      <div class="aubie-nose" id="aubie-nose"></div>
      <div class="aubie-mouth" id="aubie-mouth"></div>
      <!-- 12-horn crown + 4 compass marks (Aya Huma) + accessory slots (brows,
           glasses, ears, antennae, heart, zzz, tear, sparkles) generated by JS -->
    </div>
  </div>
  <div class="greet-name" id="greet-name">Waiting…</div>
  <div class="greet-msg"  id="greet-msg">Tap Watch to start</div>
  <button class="btn btn-sm" id="widget-close-btn" onclick="closeFaceWidget()" style="margin-top:10px;width:100%;background:#0d1520;border:1px solid var(--border);color:var(--sub)">⏹ Stop</button>
</div>

<button id="talk-fab" title="Hold to talk to Aubie"
  onmousedown="startRecording()" onmouseup="stopRecordingAndSend()" onmouseleave="cancelRecordingIfActive()"
  ontouchstart="event.preventDefault();startRecording()" ontouchend="event.preventDefault();stopRecordingAndSend()">🎙️</button>

<!-- ── FACE PICKER — pick a preset, preview it live, Save or Cancel ────── -->
<div id="face-picker-modal">
  <div id="face-picker-box">
    <div style="font-weight:800;font-size:16px;margin-bottom:12px;color:var(--text)">🎨 Choose Aubie's Face</div>
    <div id="face-preset-grid"></div>
    <div id="face-color-controls" style="display:flex;gap:16px;justify-content:center;align-items:center;margin:14px 0;font-size:12px;color:var(--sub)">
      <label style="display:flex;align-items:center;gap:6px">👁️ Eyes
        <input type="color" id="eye-color-input" value="#00e676" onchange="setFaceColor('eye',this.value)">
      </label>
      <label style="display:flex;align-items:center;gap:6px">👄 Mouth
        <input type="color" id="mouth-color-input" value="#00e676" onchange="setFaceColor('mouth',this.value)">
      </label>
    </div>
    <div style="display:flex;gap:10px">
      <button class="btn btn-sm" onclick="closeFacePicker(false)" style="flex:1;background:#0d1520;border:1px solid var(--border);color:var(--sub)">✕ Cancel</button>
      <button class="btn btn-accent btn-sm" onclick="closeFacePicker(true)" style="flex:1">💾 Save</button>
    </div>
  </div>
</div>

<script>
// ── Face customization: presets, picker modal, preview/save/cancel ─────────
// Every preset shares the SAME animated eyes/nose/mouth (blink + talk) -
// only colors, mouth shape, and a few accessory shapes change. Builds the
// 12-horn crown + 4 compass marks (Aya Huma) and the accessory slots once;
// CSS decides which are visible per preset.
(function setupFaceDecor() {
  const face = document.getElementById('aubie-face');
  for(let i=0;i<12;i++) {
    const horn = document.createElement('div');
    horn.className = 'horn';
    horn.style.transform = `rotate(${i*30}deg)`;
    face.appendChild(horn);
  }
  [['huma-nose','north'],['huma-nose','south'],['huma-ear','east'],['huma-ear','west']].forEach(([cls,dir])=>{
    const m = document.createElement('div');
    m.className = `huma-mark ${cls} ${dir}`;
    face.appendChild(m);
  });
  ['acc-brow-l','acc-brow-r','acc-glass-l','acc-glass-r','acc-glass-bridge',
   'acc-ear-l','acc-ear-r','acc-antenna-l','acc-antenna-r','acc-heart','acc-zzz','acc-tear'].forEach(cls => {
    const el = document.createElement('div'); el.className = cls; face.appendChild(el);
  });
  for(let i=0;i<3;i++) { const s = document.createElement('div'); s.className = 'acc-sparkle'; face.appendChild(s); }
})();

// special:'huma' keeps its own bespoke CSS (.theme-huma). Everything else is
// a color+shape+accessory "recipe" applied to the same shared face parts.
// accessory flags map straight to the .acc-* CSS classes above.
const FACE_PRESETS = {
  default:   {label:'Classic',    emoji:'🙂'},
  huma:      {label:'Aya Huma',   emoji:'🌞', special:'huma'},
  puppy:     {label:'Puppy',      emoji:'🐶', eye:'#3a2a1a', mouth:'#3a2a1a', nose:'#1a1008', bg:'#e8c39e', mouthShape:'smile', acc:['ears']},
  oldman:    {label:'Old Man',    emoji:'👴', eye:'#5c6b78', mouth:'#5c6b78', nose:'#8a7a6a', bg:'#cfd6dc', mouthShape:'flat',  acc:['brows']},
  hippy:     {label:'Hippy',      emoji:'✌️', eye:'#8a3ffc', mouth:'#ff2fa1', nose:'#ffcc00', bg:'linear-gradient(90deg,#ff5f6d,#ffc371,#47cf73,#00c2ff,#8a3ffc)', mouthShape:'smile'},
  scientist: {label:'Scientist',  emoji:'🔬', eye:'#00c9ff', mouth:'#213040', nose:'#8a97a6', bg:'#eef3f7', mouthShape:'flat',  acc:['glasses']},
  happy:     {label:'Happy',      emoji:'😊', eye:'#ffb300', mouth:'#ffb300', nose:'#ffb300', bg:'#3a2a00', mouthShape:'smile'},
  surprised: {label:'Surprised',  emoji:'😲', eye:'#ffffff', mouth:'#ffffff', nose:'#ffffff', bg:'#1a1030', mouthShape:'open'},
  angry:     {label:'Angry',      emoji:'😠', eye:'#ff4444', mouth:'#ff4444', nose:'#ff4444', bg:'#2a0000', mouthShape:'frown', acc:['brows']},
  cool:      {label:'Cool',       emoji:'😎', eye:'#00e5ff', mouth:'#00e5ff', nose:'#00e5ff', bg:'#001820', mouthShape:'smile', acc:['glasses']},
  love:      {label:'Love',       emoji:'😍', eye:'#ff5c8a', mouth:'#ff5c8a', nose:'#ff5c8a', bg:'#3a0018', mouthShape:'smile', acc:['heart']},
  sleep:     {label:'Sleep',      emoji:'😴', eye:'#7a8ba0', mouth:'#7a8ba0', nose:'#7a8ba0', bg:'#0a1220', mouthShape:'flat',  acc:['zzz'], eyesClosed:true},
  sad:       {label:'Sad',        emoji:'😢', eye:'#5599ff', mouth:'#5599ff', nose:'#5599ff', bg:'#0a1830', mouthShape:'frown', acc:['tear']},
  crazy:     {label:'Crazy',      emoji:'🤪', eye:'#c8ff00', mouth:'#ff00c8', nose:'#00ffea', bg:'#1a0a2a', mouthShape:'open'},
  bug:       {label:'Bug',        emoji:'🐛', eye:'#8aff00', mouth:'#5a9c00', nose:'#5a9c00', bg:'#0a1a00', mouthShape:'flat',  acc:['antennae']},
  mind:      {label:'Mind Blown', emoji:'🤯', eye:'#ffee00', mouth:'#ffee00', nose:'#ffee00', bg:'#1a1a00', mouthShape:'open', acc:['sparkles']},
};
const MOUTH_SHAPES = ['smile','frown','open'];
const ACC_FLAGS = ['brows','glasses','ears','antennae','heart','zzz','tear','sparkles'];
let savedFacePreset = localStorage.getItem('aubie_face_preset') || 'default';
let previewedFacePreset = savedFacePreset;

function applyFacePreset(key) {
  const p = FACE_PRESETS[key] || FACE_PRESETS.default;
  const ring = document.getElementById('greet-ring');
  ring.classList.remove('theme-huma','eyes-closed');
  MOUTH_SHAPES.forEach(s => ring.classList.remove('mouth-'+s));
  ACC_FLAGS.forEach(a => ring.classList.remove('acc-'+a));
  Object.keys(FACE_PRESETS).forEach(k => ring.classList.remove('preset-'+k));
  ring.classList.add('preset-'+key);
  ring.style.background = ''; // clear any preset's inline background first

  if(p.special === 'huma') {
    ring.classList.add('theme-huma');
  } else {
    // Classic has no fixed recipe colors of its own - it uses whatever the
    // eye/mouth color pickers below have saved (or the CSS default green).
    const eyeColor = p.eye || localStorage.getItem('aubie_eye_color') || '';
    const mouthColor = p.mouth || localStorage.getItem('aubie_mouth_color') || '';
    const noseColor = p.nose || mouthColor || eyeColor || '';
    if(eyeColor) ring.style.setProperty('--eye-color', eyeColor); else ring.style.removeProperty('--eye-color');
    if(mouthColor) ring.style.setProperty('--mouth-color', mouthColor); else ring.style.removeProperty('--mouth-color');
    if(noseColor) ring.style.setProperty('--nose-color', noseColor); else ring.style.removeProperty('--nose-color');
    ring.style.background = p.bg || '';
    ring.classList.add('mouth-'+(p.mouthShape||'flat'));
    if(p.eyesClosed) ring.classList.add('eyes-closed');
    (p.acc||[]).forEach(a => ring.classList.add('acc-'+a));
  }
  document.getElementById('face-color-controls').style.display = (key==='default') ? 'flex' : 'none';
}
applyFacePreset(savedFacePreset);

function renderFacePresetGrid() {
  const grid = document.getElementById('face-preset-grid');
  grid.innerHTML = Object.entries(FACE_PRESETS).map(([key,p]) => `
    <div class="preset-tile${key===previewedFacePreset?' active':''}" data-key="${key}" onclick="previewFacePreset('${key}')">
      <div class="p-emoji">${p.emoji}</div>
      <div class="p-label">${p.label}</div>
    </div>`).join('');
}
function previewFacePreset(key) {
  previewedFacePreset = key;
  applyFacePreset(key);
  document.querySelectorAll('.preset-tile').forEach(t => t.classList.toggle('active', t.dataset.key===key));
}
function openFacePicker() {
  previewedFacePreset = savedFacePreset;
  renderFacePresetGrid();
  applyFacePreset(previewedFacePreset);
  document.getElementById('face-picker-modal').classList.add('show');
}
function closeFacePicker(save) {
  if(save) {
    savedFacePreset = previewedFacePreset;
    localStorage.setItem('aubie_face_preset', savedFacePreset);
  } else {
    applyFacePreset(savedFacePreset); // revert the live preview
  }
  document.getElementById('face-picker-modal').classList.remove('show');
}

// Eye/mouth color customization - only shown/relevant for the Classic
// preset; every other preset's colors come from its recipe above.
function setFaceColor(part, color) {
  document.getElementById('greet-ring').style.setProperty(`--${part}-color`, color);
  localStorage.setItem(`aubie_${part}_color`, color);
}
['eye','mouth'].forEach(part => {
  const saved = localStorage.getItem(`aubie_${part}_color`);
  if(saved) {
    document.getElementById('greet-ring').style.setProperty(`--${part}-color`, saved);
    document.getElementById(`${part}-color-input`).value = saved;
  }
});

// ── Tab switching ─────────────────────────────────────────────────────────
function switchTab(name) {
  if (name === 'aubie') moveFaceToAubieTab(); else restoreFaceFromAubieTab();
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  document.getElementById('tbtn-' + name).classList.add('active');
}

// ── Aubie tab: borrow the single #face-widget for a full-screen face ──────
// There's only one animated face in the page (Watch mode's floating widget,
// with all the blink/talk/face-picker machinery bound to its ids). Rather
// than build a second one, relocate it into the Aubie tab while that tab is
// open and put it back exactly where it was on leave.
let _faceHomeNextSibling = null;   // where #face-widget sits in <body> normally
let _facePrevShow = false;         // was the floating widget visible before?
function moveFaceToAubieTab() {
  const fw = document.getElementById('face-widget');
  const mount = document.getElementById('aubie-face-mount');
  if (!fw || !mount || fw.parentElement === mount) return;
  _faceHomeNextSibling = fw.nextSibling;
  _facePrevShow = fw.classList.contains('show');
  mount.appendChild(fw);
  fw.classList.add('fullscreen', 'show');
}
function restoreFaceFromAubieTab() {
  const fw = document.getElementById('face-widget');
  if (!fw || !fw.classList.contains('fullscreen')) return;
  fw.classList.remove('fullscreen');
  document.body.insertBefore(fw, _faceHomeNextSibling || null);
  // Only keep it visible if Watch mode wants it, or it was already shown.
  if (!_facePrevShow && !greetMode) fw.classList.remove('show');
}

// Typed conversation for the Aubie tab — same persona/memory/voice as
// "hey aubie" and the Teach-tab ask box (aubieTextChat -> /ask-text,
// shared chatHistory, spoken reply), plus the class-flow passthrough.
function aubieTranscriptAdd(who, txt) {
  const t = document.getElementById('aubie-transcript');
  if (!t) return;
  const d = document.createElement('div');
  d.className = who === 'You' ? 'u' : 'a';
  d.textContent = (who === 'You' ? '🧑 ' : '🦅 ') + txt;
  t.appendChild(d);
  t.scrollTop = t.scrollHeight;
}
async function sendAubieChat() {
  const input = document.getElementById('aubie-chat-input');
  const q = (input.value || '').trim();
  if (!q) return;
  input.value = '';
  aubieTranscriptAdd('You', q);
  if (CLASS_TRIGGER_RE.test(q.toLowerCase())) { await startClass(); return; }
  if (currentClass) { await submitClassAnswer(q); return; }
  const msgEl = document.getElementById('greet-msg');
  if (msgEl) msgEl.textContent = '⏳ Thinking…';
  try {
    const data = await aubieTextChat(q, { history: chatHistory, speaker: lastGreeted || undefined });
    const reply = data.reply || data.response || data.answer || data.text || data.output || JSON.stringify(data);
    chatHistory.push({ role: 'user', content: q }, { role: 'assistant', content: reply });
    if (msgEl) msgEl.textContent = reply;
    aubieTranscriptAdd('Aubie', reply);
    await aubieSpeak(reply);
  } catch (e) {
    if (msgEl) msgEl.textContent = 'Sorry — ' + e.message;
    aubieTranscriptAdd('Aubie', 'Sorry — ' + e.message);
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────
function log(msg, type='info') {
  const el = document.getElementById('log');
  const cls = type==='err'?'lerr':type==='ok'?'lok':'linf';
  const ts = new Date().toLocaleTimeString();
  el.innerHTML += `\n<span class="${cls}">[${ts}] ${msg}</span>`;
  el.scrollTop = el.scrollHeight;
}
function setResp(id, txt, state='') {
  const el = document.getElementById(id);
  el.textContent = txt;
  el.className = 'resp show' + (state?' '+state:'');
}
function setCode(id, txt) {
  const el = document.getElementById(id);
  el.textContent = txt;
  el.className = 'code-out show';
}
async function post(url, body) {
  const r = await fetch(url, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  return r.json();
}

// ── Status ────────────────────────────────────────────────────────────────
async function checkStatus() {
  try {
    const r = await fetch('/health');
    const ok = r.ok;
    document.getElementById('status-dot').className = ok ? 'dot online' : 'dot';
    document.getElementById('dog-dot').className    = ok ? 'dog-dot online' : 'dog-dot';
  } catch { ['status-dot','dog-dot'].forEach(id => document.getElementById(id).className = id==='dog-dot'?'dog-dot':'dot'); }
}
checkStatus(); setInterval(checkStatus, 15000);

// ── Camera/mic "insecure origin" fix — browser- and origin-aware ───────────
// getUserMedia (camera/mic) is blocked by every browser on plain HTTP unless
// the origin is explicitly allowlisted. The old instructions hardcoded
// "edge://flags" and a fixed LAN IP - wrong for Chrome (what most Android
// tablets actually run) and wrong the moment the page is reached via a
// different address (Tailscale IP, hostname, a changed DHCP lease, etc).
// These detect the real browser and use location.origin so the steps always
// match reality.
function isFirefox() { return /Firefox/i.test(navigator.userAgent); }
function insecureOriginFlagsUrl() { return /Edg\//i.test(navigator.userAgent) ? 'edge://flags' : 'chrome://flags'; }
function insecureOriginBrowserName() {
  if(isFirefox()) return 'Firefox';
  return insecureOriginFlagsUrl()==='edge://flags' ? 'Edge' : 'Chrome';
}
function insecureOriginFixHTML() {
  const origin = location.origin;
  if(isFirefox()) {
    return `1. New tab → <b style="color:#ff9944">about:config</b> → accept the warning<br>`
      + `2. Search: <b>media.devices.insecure.enabled</b> → set <b style="color:#00e676">true</b><br>`
      + `3. Search: <b>media.getusermedia.insecure.enabled</b> → set <b style="color:#00e676">true</b><br>`
      + `4. Reload this page:<br>&nbsp;&nbsp;<b style="color:#00c9ff">${origin}</b>`;
  }
  return `1. New tab → <b style="color:#ff9944">${insecureOriginFlagsUrl()}</b><br>`
    + `2. Search: <b>insecure origin</b><br>`
    + `3. Paste in the box:<br>&nbsp;&nbsp;<b style="color:#00c9ff">${origin}</b><br>`
    + `4. Dropdown → <b style="color:#00e676">✅ Enabled</b><br>`
    + `5. Click <b>Restart</b> button`;
}
function insecureOriginFixText() {
  const origin = location.origin;
  if(isFirefox()) {
    return '📵 Camera/mic blocked by browser security (insecure HTTP origin).\n\n' +
      'Fix (Firefox):\n' +
      '1. Open a new tab → type:  about:config  → accept the warning\n' +
      '2. Search: media.devices.insecure.enabled → set to true\n' +
      '3. Search: media.getusermedia.insecure.enabled → set to true\n' +
      `4. Reload this page:  ${origin}\n\n` +
      'After reload, camera/mic will work!';
  }
  return '📵 Camera/mic blocked by browser security (insecure HTTP origin).\n\n' +
    'Fix (takes 30 seconds):\n' +
    `1. Open a new tab → type:  ${insecureOriginFlagsUrl()}\n` +
    '2. Search: insecure origin\n' +
    '3. Find "Insecure origins treated as secure"\n' +
    `4. Paste into the box:  ${origin}\n` +
    '5. Change dropdown to ✅ Enabled\n' +
    '6. Click the blue Restart button\n\n' +
    'After restart, reload this page — camera/mic will work!';
}

// Show camera unlock banner if mediaDevices is blocked
if(!navigator.mediaDevices) {
  document.getElementById('cam-unlock-intro').innerHTML =
    `${insecureOriginBrowserName()} is blocking camera access on HTTP.<br>Fix it in 30 seconds:`;
  document.getElementById('cam-unlock-steps').innerHTML = insecureOriginFixHTML();
  document.getElementById('cam-unlock-banner').style.display = 'block';
}

// ── Text chat endpoint probe ──────────────────────────────────────────────
// /converse expects `audio` (voice). We probe for the real text endpoint.
let _textEndpoint = null; // cached once found
let _textField    = 'message';

async function aubieTextChat(message, extra={}) {
  // If we already found the working endpoint, use it
  if(_textEndpoint) {
    const data = await post(_textEndpoint, {[_textField]: message, ...extra});
    if(!data.detail) return data;
  }
  // Probe list — /ask-text is our own Ollama proxy added to phone_ui.py
  const probes = [
    ['/ask-text',  'message'],   // ← our own Ollama route (most reliable)
    ['/ask',       'message'],
    ['/ask',       'query'],
    ['/query',     'message'],
    ['/chat',      'message'],
    ['/llm',       'prompt'],
    ['/converse',  'text'],
    ['/converse',  'message'],
  ];
  for(const [ep, field] of probes) {
    try {
      const data = await post(ep, {[field]: message, ...extra});
      if(!data.detail) {          // 'detail' = FastAPI 422 / 404 error
        _textEndpoint = ep;
        _textField    = field;
        log(`Text endpoint found: ${ep} (field: ${field})`,'ok');
        return data;
      }
    } catch {}
  }
  throw new Error('No text endpoint responded. SSH to rig and run:\ngrep -n "@app\\." /home/aubieeternal/AUBIEETERNAL/assistant_server.py | head -80');
}

// ── Ask / Teach ───────────────────────────────────────────────────────────
// Running conversation so the Ask box supports real follow-ups instead of
// each question being a fresh, context-free call to Ollama.
let chatHistory = [];
function renderChatHistory() {
  return chatHistory.map(t => (t.role==='user'?'🧑 You: ':'🤖 Aubie: ') + t.content).join('\n\n');
}
function newConversation() {
  chatHistory = [];
  const el = document.getElementById('ask-resp');
  el.textContent = ''; el.className = 'resp';
}
async function sendAsk() {
  const q = document.getElementById('ask-input').value.trim(); if(!q) return;
  document.getElementById('ask-input').value = '';
  if(currentClass) { await submitClassAnswer(q); return; }
  setResp('ask-resp', renderChatHistory() + (chatHistory.length?'\n\n':'') + '⏳ Thinking…', 'thinking');
  log(`Ask: ${q.slice(0,50)}…`);
  try {
    const data = await aubieTextChat(q, {history: chatHistory});
    const reply = data.reply||data.response||data.answer||data.text||data.output||JSON.stringify(data);
    chatHistory.push({role:'user', content:q}, {role:'assistant', content:reply});
    setResp('ask-resp', renderChatHistory(), 'ok'); log('Answer received','ok');
    incrementProgress(q);
    if(document.getElementById('speak-toggle')?.checked) aubieSpeak(reply);
  } catch(e) { setResp('ask-resp', renderChatHistory() + `\n\n⚠️ Error: ${e.message}`, 'error'); log('Ask failed: '+e.message,'err'); }
}
function quickTopic(p) {
  document.getElementById('ask-input').value = p; sendAsk();
  switchTab('teach');
  document.getElementById('tab-teach').scrollTo({top:0,behavior:'smooth'});
}

// ── Build Code ────────────────────────────────────────────────────────────
async function sendBuild() {
  const req = document.getElementById('build-input').value.trim(); if(!req) return;
  setResp('build-status','⚙️ Running dual-road orchestrator… (this takes 30–90 sec)','thinking');
  document.getElementById('build-code').className='code-out';
  document.getElementById('build-iter').style.display='none';
  log(`Build: ${req.slice(0,50)}…`);
  try {
    const data = await post('/build-code',{request:req});
    if(data.success) {
      setResp('build-status',`✅ Build SUCCEEDED\n📄 ${data.output_file}`,'ok');
      const lastLog = data.run_log?.[data.run_log.length-1];
      const out = lastLog?.stdout?.trim()||'(no stdout)';
      setCode('build-code',`// ── GENERATED CODE ──\n${data.final_code}\n\n// ── OUTPUT ──\n${out}`);
      const iterEl = document.getElementById('build-iter');
      document.getElementById('build-iter-text').textContent = `Completed in ${data.iterations} iteration(s)`;
      iterEl.style.display='inline-flex';
      log(`Build OK — ${data.iterations} iteration(s)`,'ok');
    } else {
      setResp('build-status',`❌ Build FAILED after ${data.iterations} iteration(s)\n${data.error_message}`,'error');
      if(data.final_code) setCode('build-code', `// ── BEST ATTEMPT ──\n${data.final_code}`);
      log('Build failed after max retries','err');
    }
  } catch(e) { setResp('build-status','Error: '+e.message,'error'); log('Build error: '+e.message,'err'); }
}
function quickBuild(prompt) {
  document.getElementById('build-input').value = prompt;
  sendBuild();
}

// ── Voice — uses browser SpeechRecognition (works on HTTP) → Ollama text ──
let _srActive = false;
let _srObj = null;

function toggleMic() {
  if(_srActive) { stopSpeech(); return; }
  startSpeech();
}

function startSpeech() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if(!SR) {
    setResp('voice-resp','⚠️ Speech recognition not supported in this browser.\nUse Chrome or Edge and make sure the microphone flag is set.','error');
    return;
  }
  _srObj = new SR();
  _srObj.lang = 'en-US';
  _srObj.interimResults = false;
  _srObj.maxAlternatives = 1;

  _srObj.onstart = ()=>{
    _srActive = true;
    document.getElementById('mic-btn').className = 'mic-ring listening';
    document.getElementById('mic-lbl').textContent = '🎤 Listening… tap to stop';
    setResp('voice-resp','🎤 Listening…','thinking');
    log('Voice: listening…','info');
  };
  _srObj.onspeechend = ()=>{ _srObj.stop(); };
  _srObj.onerror = (e)=>{
    _srActive = false;
    document.getElementById('mic-btn').className = 'mic-ring';
    document.getElementById('mic-lbl').textContent = 'Tap to speak to Aubie';
    if(e.error==='not-allowed') {
      setResp('voice-resp', insecureOriginFixText(), 'error');
    } else {
      setResp('voice-resp','Mic error: '+e.error,'error');
    }
    log('Speech error: '+e.error,'err');
  };
  _srObj.onresult = async (e)=>{
    _srActive = false;
    document.getElementById('mic-btn').className = 'mic-ring';
    document.getElementById('mic-lbl').textContent = 'Processing…';
    const transcript = e.results[0][0].transcript;
    log(`Heard: "${transcript.slice(0,60)}"`, 'ok');
    setResp('voice-resp', `🗣️ "${transcript}"\n\n⏳ Thinking…`, 'thinking');
    try {
      const data = await aubieTextChat(transcript);
      const reply = data.reply||data.response||data.answer||data.text||data.output||JSON.stringify(data);
      setResp('voice-resp', `🗣️ You: "${transcript}"\n\n💬 Aubie: ${reply}`, 'ok');
      if(document.getElementById('speak-toggle')?.checked) aubieSpeak(reply);
      log('Voice reply received','ok');
    } catch(err) {
      setResp('voice-resp', `🗣️ "${transcript}"\n\n❌ ${err.message}`, 'error');
      log('Voice reply error: '+err.message,'err');
    }
    document.getElementById('mic-lbl').textContent = 'Tap to speak to Aubie';
  };

  try { _srObj.start(); }
  catch(e) { setResp('voice-resp','Could not start mic: '+e.message,'error'); }
}

function stopSpeech() {
  if(_srObj) _srObj.stop();
  _srActive = false;
  document.getElementById('mic-btn').className = 'mic-ring';
  document.getElementById('mic-lbl').textContent = 'Tap to speak to Aubie';
}

// ── Camera ────────────────────────────────────────────────────────────────
// Uses the tablet's own (rear) camera for a one-shot capture - there's no
// robot /snapshot or /vision/describe route to call anymore; the rig only
// has /vision/what_do_you_see (YOLO object/color/QR summary, JSON body).
let lastCamB64 = null;
async function captureTabletFrame() {
  if(!navigator.mediaDevices) { cameraBlockedMsg('cam-resp'); return null; }
  const stream = await navigator.mediaDevices.getUserMedia({video:{facingMode:'environment'}});
  const video = document.createElement('video');
  video.srcObject = stream; video.playsInline = true;
  await video.play();
  await new Promise(r=>setTimeout(r,200)); // let exposure/focus settle
  const canvas = document.createElement('canvas');
  canvas.width = video.videoWidth||320; canvas.height = video.videoHeight||240;
  canvas.getContext('2d').drawImage(video,0,0,canvas.width,canvas.height);
  stream.getTracks().forEach(t=>t.stop());
  return canvas.toDataURL('image/jpeg',0.85).split(',')[1];
}
async function takeSnapshot() {
  try {
    lastCamB64 = await captureTabletFrame();
    if(!lastCamB64) return;
    const img = document.getElementById('cam-preview');
    img.src = 'data:image/jpeg;base64,'+lastCamB64; img.style.display='block';
    log('Snapshot','ok');
  } catch(e){log('Snapshot error: '+e.message,'err');}
}
async function describeScene() {
  setResp('cam-resp','👁️ Looking…','thinking');
  try {
    if(!lastCamB64) lastCamB64 = await captureTabletFrame();
    if(!lastCamB64) { setResp('cam-resp','No photo — camera access needed first','error'); return; }
    // /vision_describe uses the qwen2.5vl:7b vision model for a real
    // natural-language description (multipart upload, not JSON).
    const blob = b64ToBlob(lastCamB64);
    const form = new FormData();
    form.append('image', blob, 'frame.jpg');
    form.append('prompt', 'Describe what you see in detail.');
    const r = await fetch('/vision_describe', {method:'POST', body: form});
    const data = await r.json();
    if(!r.ok) { setResp('cam-resp', data.detail||'Vision error', 'error'); return; }
    setResp('cam-resp', data.description||JSON.stringify(data), 'ok'); log('Scene described','ok');
  } catch(e){setResp('cam-resp','Vision error: '+e.message,'error');}
}

// ── QR Airlock ───────────────────────────────────────────────────────────
// Decode a scanned QR on the rig (POST /qr/check), show the raw URL + verdict.
// Never navigates to the link. Buttons below are all explicit taps.
let qrLast = null;   // last verdict payload {payload, payload_sha256, registered_domain, verdict}
const QR_BADGE = {
  confirmed_bad: ['#5a1a1a', '#ffb3b3', '⛔ Known bad — do not open'],
  suspicious:    ['#4a3a10', '#ffdd88', '⚠️ Suspicious — read it carefully'],
  withdrawn:     ['#333',    '#ccc',    'ℹ️ Was flagged, flag withdrawn'],
  allowed:       ['#12351f', '#9be8b4', '✅ On your household allow list'],
  unknown:       ['#1c2f45', '#cfe8ff', '❔ Nothing on record — read it yourself'],
};
async function scanQR() {
  setResp('qr-resp','📷 Opening camera…','thinking');
  document.getElementById('qr-result').style.display = 'none';
  let b64;
  try {
    b64 = await captureTabletFrame();
  } catch(e){ setResp('qr-resp','Camera error: '+e.message,'error'); return; }
  if(!b64){ return; }  // captureTabletFrame already showed the insecure-origin fix
  document.getElementById('qr-preview').src = 'data:image/jpeg;base64,'+b64;
  document.getElementById('qr-preview').style.display = 'block';
  setResp('qr-resp','🔎 Checking…','thinking');
  try {
    const r = await fetch('/qr/check', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ image_b64: b64, source: 'kiosk', who: 'kiosk' })
    });
    const d = await r.json();
    if(d.error && !d.payload){ setResp('qr-resp', d.error, 'error'); return; }
    renderQR(d);
  } catch(e){ setResp('qr-resp','Check failed: '+e.message,'error'); }
}
function renderQR(d) {
  qrLast = d;
  setResp('qr-resp','', '');
  document.getElementById('qr-resp').className = 'resp';
  const [bg, fg, label] = QR_BADGE[d.verdict] || QR_BADGE.unknown;
  const badge = document.getElementById('qr-badge');
  badge.textContent = label; badge.style.background = bg; badge.style.color = fg;
  document.getElementById('qr-url').textContent = d.payload || '(no link — not a URL)';
  document.getElementById('qr-explain').textContent = d.explanation || '';
  const sig = (d.signals||[]).join(', ');
  document.getElementById('qr-signals').textContent = sig ? ('Warning signs: ' + sig) : '';
  document.getElementById('qr-hash').textContent = d.payload_sha256 || '';
  document.getElementById('qr-result').style.display = 'block';
}
async function qrCopyUrl() {
  if(!qrLast || !qrLast.payload) return;
  try {
    if(navigator.clipboard) await navigator.clipboard.writeText(qrLast.payload);
    else { const t=document.createElement('textarea'); t.value=qrLast.payload;
      document.body.appendChild(t); t.select(); document.execCommand('copy'); t.remove(); }
    log('URL copied','ok');
    const b=event.target; const o=b.textContent; b.textContent='📋 Copied'; setTimeout(()=>b.textContent=o,1500);
  } catch(e){ log('Copy failed: '+e.message,'err'); }
}
async function qrAllow() {
  if(!qrLast || !qrLast.payload) return;
  if(!confirm('Allow this link for your whole household this month?')) return;
  try {
    const r = await fetch('/qr/allow', { method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ payload: qrLast.payload, domain: qrLast.registered_domain || null }) });
    const d = await r.json();
    if(r.ok){ log('Added to household allow list','ok'); renderQR({ ...qrLast, verdict:'allowed',
      explanation:'You just added this to your household allow list.' }); }
    else log('Allow failed: '+JSON.stringify(d),'err');
  } catch(e){ log('Allow failed: '+e.message,'err'); }
}
async function qrShare() {
  if(!qrLast || !qrLast.payload) return;
  const venue = prompt('Optional: where did you see this code? (business name, or leave blank)') || '';
  try {
    const r = await fetch('/qr/share', { method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ payload: qrLast.payload, venue_name: venue || null }) });
    const d = await r.json();
    if(r.ok && d.status==='queued'){
      log('Flag queued for a human to review before publishing','ok');
      const b=event.target; b.textContent='🚩 Queued'; b.disabled=true;
    } else log('Share failed: '+JSON.stringify(d),'err');
  } catch(e){ log('Share failed: '+e.message,'err'); }
}

// ── System ────────────────────────────────────────────────────────────────
async function checkHealth(){try{const r=await fetch('/health');const d=await r.json();log(`Health: ${JSON.stringify(d)}`,'ok');}catch(e){log('Health fail: '+e.message,'err');}}
async function probeEndpoints() {
  setResp('probe-resp','🔍 Probing endpoints + Ollama…','thinking');
  let out = '';
  // Check our Ollama proxy
  try {
    const r = await fetch('/ask-text',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:'ping'})});
    const d = await r.json();
    if(d.reply) { out += `✅ /ask-text → Ollama working! (model: ${d.model||'?'})\n`; }
    else if(d.error) { out += `⚠️ /ask-text error: ${d.error}\n`; }
    else { out += `⚠️ /ask-text responded but no reply field: ${JSON.stringify(d).slice(0,80)}\n`; }
  } catch(e) { out += `❌ /ask-text failed: ${e.message}\n`; }
  // Check Ollama models list
  try {
    const r = await fetch('/ollama-models');
    const d = await r.json();
    const models = (d.models||[]).map(m=>m.name||m).join(', ');
    out += models ? `📦 Ollama models: ${models}\n` : '⚠️ No Ollama models found\n';
  } catch {}
  setResp('probe-resp', out.trim() || '❌ Nothing responded', out.includes('✅')?'ok':'error');
}
function resetEndpointCache() {
  _textEndpoint = null; _textField = 'message';
  setResp('probe-resp','Cache cleared — next Ask will probe again','ok');
  log('Endpoint cache reset','info');
}
function clearLog(){document.getElementById('log').innerHTML='> Log cleared.';}

// ── Enter keys ────────────────────────────────────────────────────────────
document.getElementById('ask-input').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendAsk();}});
document.getElementById('build-input').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendBuild();}});
document.getElementById('say-input').addEventListener('keydown',e=>{if(e.key==='Enter'){dogSay();}});

// ── Dog commands ──────────────────────────────────────────────────────────
const PROXY = '/proxy/dog';
async function dogPost(body) {
  try {
    const r=await fetch(PROXY,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const d=await r.json(); log(`Dog: ${JSON.stringify(body).slice(0,60)}`,'ok'); return d;
  } catch(e){log('Dog error: '+e.message,'err');}
}
function dog(cmd){ dogPost({action:cmd}); }

function dogFace(expression) {
  document.querySelectorAll('.face-btn').forEach(b=>b.classList.remove('active'));
  event.target.closest('.face-btn').classList.add('active');
  dogPost({action:'set_face', expression});
}
function applyFace() {
  dogPost({action:'custom_face', eyes:document.getElementById('eye-sel').value, mouth:document.getElementById('mouth-sel').value});
}
function dogSay() {
  const t=document.getElementById('say-input').value.trim(); if(!t) return;
  dogPost({action:'say', text:t}); log(`Say: ${t.slice(0,40)}`,'info');
}
function teachPerson() {
  const name=document.getElementById('person-name').value.trim(); if(!name) return;
  dogPost({action:'teach_person', name});
}
function applyServos() {
  const vals={};
  document.querySelectorAll('[data-servo]').forEach(s=>vals[s.dataset.servo]=parseInt(s.value));
  dogPost({action:'set_servo',...vals});
}
function centerServos() {
  document.querySelectorAll('[data-servo]').forEach(s=>{s.value=0;s.nextElementSibling.textContent='0';});
  dogPost({action:'center_all'});
}

// ── Joystick ──────────────────────────────────────────────────────────────
(function(){
  const canvas=document.getElementById('joystick-canvas');
  const ctx=canvas.getContext('2d');
  const CX=100,CY=100,R=80,THUMB=28;
  let dx=0,dy=0,dragging=false,sendTimer=null;

  function draw(){
    ctx.clearRect(0,0,200,200);
    // outer ring
    ctx.beginPath(); ctx.arc(CX,CY,R,0,Math.PI*2);
    ctx.strokeStyle='#1e2d3d'; ctx.lineWidth=2; ctx.stroke();
    // crosshair
    ctx.strokeStyle='#1e3d2d'; ctx.lineWidth=1;
    ctx.beginPath();ctx.moveTo(CX-R,CY);ctx.lineTo(CX+R,CY);ctx.stroke();
    ctx.beginPath();ctx.moveTo(CX,CY-R);ctx.lineTo(CX,CY+R);ctx.stroke();
    // thumb
    const tx=CX+dx,ty=CY+dy;
    const grad=ctx.createRadialGradient(tx-4,ty-4,2,tx,ty,THUMB);
    grad.addColorStop(0,'#00c9ff'); grad.addColorStop(1,'#0040aa');
    ctx.beginPath(); ctx.arc(tx,ty,THUMB,0,Math.PI*2);
    ctx.fillStyle=grad; ctx.fill();
    ctx.strokeStyle='#00c9ff55'; ctx.lineWidth=2; ctx.stroke();
  }

  function clamp(x,y){
    const dist=Math.sqrt(x*x+y*y);
    if(dist>R-THUMB){const s=(R-THUMB)/dist;return{x:x*s,y:y*s};}
    return{x,y};
  }
  function pos(e){
    const rect=canvas.getBoundingClientRect();
    const t=e.touches?e.touches[0]:e;
    return{x:t.clientX-rect.left-CX, y:t.clientY-rect.top-CY};
  }
  function startDrag(e){ e.preventDefault(); dragging=true; move(e); }
  function move(e){
    if(!dragging)return; e.preventDefault();
    const {x,y}=clamp(pos(e).x,pos(e).y);
    dx=x; dy=y;
    draw();
    document.getElementById('joy-readout').textContent=`x:${Math.round(dx/R*100)} y:${Math.round(-dy/R*100)}`;
    if(!sendTimer) sendTimer=setInterval(sendLean,150);
  }
  function endDrag(){
    if(!dragging)return; dragging=false; dx=0; dy=0; draw();
    clearInterval(sendTimer); sendTimer=null;
    document.getElementById('joy-readout').textContent='drag to move';
    dogPost({action:'lean',x:0,y:0});
  }
  function sendLean(){
    dogPost({action:'lean', x:Math.round(dx/R*100), y:Math.round(-dy/R*100)});
  }

  canvas.addEventListener('mousedown',startDrag);
  canvas.addEventListener('mousemove',move);
  canvas.addEventListener('mouseup',endDrag);
  canvas.addEventListener('mouseleave',endDrag);
  canvas.addEventListener('touchstart',startDrag,{passive:false});
  canvas.addEventListener('touchmove',move,{passive:false});
  canvas.addEventListener('touchend',endDrag);

  draw();
})();

// ════════════════════════════════════════════════════════════════════
// SPEAKER — Aubie talks back
// ════════════════════════════════════════════════════════════════════
function toggleSpeaker(on) {
  const track = document.getElementById('speak-track');
  const thumb = document.getElementById('speak-thumb');
  if(on) {
    track.style.background = 'var(--accent)';
    thumb.style.background = '#fff';
    thumb.style.left = '19px';
    log('Speaker ON — Aubie will speak answers','ok');
    aubieSpeak('Speaker on. I will speak my answers.');
  } else {
    track.style.background = '#1e2d3d';
    thumb.style.background = '#444';
    thumb.style.left = '3px';
    log('Speaker OFF','info');
  }
}
// Shared gate so greet-mode's "Hello Matthew" audio and Ask-Aubie's spoken
// replies never play on top of each other on the tablet's one speaker.
let audioBusy = false;
let currentAudio = null;
function playAudioExclusive(url) {
  // Pause Watch mode's mic while Aubie is talking, else the tablet hears
  // its own reply through the speaker and mistakes it for a new question.
  if(recognition) { try { recognition.stop(); } catch {} }
  // Belt-and-suspenders: if something is already playing (e.g. a stale
  // /greet call that was in flight when a conversation started), cut it off
  // instead of letting two clips play over each other.
  if(currentAudio) { try { currentAudio.pause(); } catch {} }
  const mouth = document.getElementById('aubie-mouth');
  if(mouth) mouth.classList.add('talking');
  return new Promise(resolve => {
    const audio = new Audio(url);
    currentAudio = audio;
    audioBusy = true;
    const done = () => {
      if(currentAudio === audio) currentAudio = null;
      audioBusy = false;
      if(mouth) mouth.classList.remove('talking');
      if(recognition && greetMode) { try { recognition.start(); } catch {} }
      resolve();
    };
    audio.onended = done; audio.onerror = done;
    audio.play().catch(done);
  });
}

async function aubieSpeak(text) {
  if(!text) return;
  // No length cap here - a hard slice(0,500) used to truncate any longer
  // answer's speech mid-sentence even though the on-screen text was full.
  const clean = text.replace(/[*_#`]/g,'');
  try {
    // /speak_local returns the Piper WAV directly for tablet playback
    // (plain /speak instead pushes audio to the robot's own speaker,
    // which isn't in the loop when the tablet is standing in for it).
    const form = new FormData();
    form.append('text', clean);
    const r = await fetch('/speak_local', {method:'POST', body: form});
    if(!r.ok) throw new Error('speak_local '+r.status);
    const blob = await r.blob();
    await playAudioExclusive(URL.createObjectURL(blob));
    log('Aubie speaking…','ok');
  } catch(e) {
    // Fallback to browser TTS
    if('speechSynthesis' in window) {
      const utt = new SpeechSynthesisUtterance(clean);
      utt.rate = 0.95; utt.pitch = 1.0;
      speechSynthesis.speak(utt);
    }
  }
}

// ════════════════════════════════════════════════════════════════════
// GREET MODE — face recognition + hello
// ════════════════════════════════════════════════════════════════════
// Recognized from Watch mode's spoken ("hey aubie...") and typed question
// box alike - see startClass() further down, defined near the Today's
// Lesson section since it shares that card's LESSONS/todayLesson state.
const CLASS_TRIGGER_RE = /let'?s go to class|start (my |the )?class|go to class|class time/i;
let greetMode = false;
let greetStream = null;
let greetTimer = null;
let greetVideo = null;
let lastGreeted = '';
let lastGreetTime = 0;
let moodTimer = null;
let moodInFlight = false;

// Watch mode's live "hey aubie" conversation - runs alongside the face-greet
// poll above so Watch is one continuous camera+mic session ("stay connected
// until we stop") rather than needing to switch to the Ask box separately.
let recognition = null;
let watchAwake = false;       // true right after a wake word or a greeting,
let watchAwakeTimer = null;   // so a quick follow-up doesn't need "hey aubie" again
let watchSpeechInFlight = false;

function startWatchListening() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if(!SR) { log('Voice not supported in this browser — use Chrome or Edge for "hey aubie"','err'); return; }
  recognition = new SR();
  recognition.continuous = true;
  recognition.interimResults = false;
  recognition.lang = 'en-US';
  recognition.onresult = (event) => {
    const res = event.results[event.results.length-1];
    if(res && res.isFinal) handleWatchSpeech(res[0].transcript);
  };
  recognition.onerror = (e) => { if(e.error!=='no-speech' && e.error!=='aborted') log('Watch mic error: '+e.error,'err'); };
  // Chrome/Edge auto-stop the recognizer after a period of silence - restart
  // it to keep listening indefinitely, but not while we're mid-speech
  // (paused deliberately by playAudioExclusive to avoid hearing ourselves).
  recognition.onend = () => { if(greetMode && !audioBusy) { try{ recognition.start(); }catch{} } };
  try { recognition.start(); } catch(e) { log('Could not start listening: '+e.message,'err'); }
}
function stopWatchListening() {
  if(!recognition) return;
  recognition.onend = null;
  try { recognition.stop(); } catch {}
  recognition = null;
  watchAwake = false;
  clearTimeout(watchAwakeTimer);
}

async function handleWatchSpeech(rawTranscript) {
  if(!greetMode || audioBusy || watchSpeechInFlight) return;
  const transcript = (rawTranscript||'').trim();
  if(!transcript) return;
  const lower = transcript.toLowerCase();
  const wakeIdx = lower.indexOf('hey aubie');

  let spoken;
  if(wakeIdx !== -1) spoken = transcript.slice(wakeIdx + 'hey aubie'.length).trim().replace(/^[,.\s]+/, '');
  else if(watchAwake) spoken = transcript;
  else return; // not addressed to Aubie - ignore ambient chatter

  // Stay "awake" for a short window after every exchange so a follow-up
  // doesn't need "hey aubie" repeated each time.
  watchAwake = true;
  clearTimeout(watchAwakeTimer);
  watchAwakeTimer = setTimeout(()=>{ watchAwake=false; }, 20000);

  if(!spoken) {
    // "hey aubie" alone, no question attached yet - give an audible cue
    // (not just an on-screen one) that it heard you and is waiting.
    document.getElementById('greet-msg').textContent = "I'm listening…";
    await aubieSpeak('Yes?');
    return;
  }

  watchSpeechInFlight = true;
  document.getElementById('greet-msg').textContent = `You: ${spoken}`;
  log('Watch heard: '+spoken,'info');
  try {
    if(CLASS_TRIGGER_RE.test(lower)) {
      await startClass();
      return;
    }
    if(currentClass) {
      await submitClassAnswer(spoken);
      return;
    }
    const visionIntent = /what('?s| is) this|what do you see|describe (this|it)|look at this/.test(lower);
    let reply;
    if(visionIntent && greetVideo) {
      // Reuse the same open Watch-mode camera feed for an on-demand
      // "what's this" - no separate button/tab needed.
      const canvas = document.createElement('canvas');
      canvas.width=320; canvas.height=240;
      canvas.getContext('2d').drawImage(greetVideo,0,0,320,240);
      const blob = await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',0.8));
      const form = new FormData();
      form.append('image', blob, 'frame.jpg');
      form.append('prompt', spoken);
      const r = await fetch('/vision_describe', {method:'POST', body: form});
      const data = await r.json();
      reply = data.description || data.detail || "I had trouble looking at that.";
    } else {
      const data = await aubieTextChat(spoken, {history: chatHistory, speaker: lastGreeted || undefined});
      reply = data.reply||data.response||data.answer||data.text||data.output||JSON.stringify(data);
      chatHistory.push({role:'user',content:spoken},{role:'assistant',content:reply});
    }
    document.getElementById('greet-msg').textContent = reply;
    await aubieSpeak(reply);
  } catch(e) {
    document.getElementById('greet-msg').textContent = 'Sorry, something went wrong: '+e.message;
  } finally { watchSpeechInFlight = false; }
}

// Typed alternative to "hey aubie" - same Aubie persona/memory (aubieTextChat
// -> /ask-text), same chatHistory thread and spoken-aloud reply, so it's a
// drop-in for anyone who can't/doesn't want to use the mic (unsupported
// browser, noisy room, etc). Works whether or not Watch mode is on.
async function sendWatchAsk() {
  const input = document.getElementById('watch-ask-input');
  const q = input.value.trim();
  if(!q) return;
  input.value = '';
  if(CLASS_TRIGGER_RE.test(q.toLowerCase())) {
    setResp('watch-ask-resp', "🎓 Heading to class — see the Teach tab…", 'ok');
    await startClass();
    return;
  }
  if(currentClass) {
    setResp('watch-ask-resp', "🎓 Answer submitted — see the Teach tab…", 'ok');
    await submitClassAnswer(q);
    return;
  }
  setResp('watch-ask-resp', '⏳ Thinking…', 'thinking');
  log('Typed ask: '+q.slice(0,50)+'…');
  try {
    const data = await aubieTextChat(q, {history: chatHistory, speaker: lastGreeted || undefined});
    const reply = data.reply||data.response||data.answer||data.text||data.output||JSON.stringify(data);
    chatHistory.push({role:'user',content:q},{role:'assistant',content:reply});
    setResp('watch-ask-resp', `🧑 You: ${q}\n\n🤖 Aubie: ${reply}`, 'ok');
    document.getElementById('greet-msg').textContent = reply;
    log('Typed ask reply received','ok');
    await aubieSpeak(reply);
  } catch(e) {
    setResp('watch-ask-resp', 'Error: '+e.message, 'error');
    log('Typed ask error: '+e.message,'err');
  }
}

async function toggleGreetMode() {
  if(!greetMode) {
    if(!navigator.mediaDevices) { cameraBlockedMsg('enroll-resp'); log('Camera blocked — see the fix steps shown','err'); return; }
    // In case a Show Me image was left showing in the widget - start clean.
    clearTimeout(widgetImgTimer);
    document.getElementById('widget-img').style.display = 'none';
    document.getElementById('greet-ring').style.display = '';
    try {
      greetStream = await navigator.mediaDevices.getUserMedia({video:{facingMode:'user'}, audio:true});
      // The camera feed is only for face-ID frame capture now - the widget
      // shows a drawn face instead of a mirror of your own camera, so this
      // video element stays attached (needed for reliable frame decoding)
      // but off-screen and invisible.
      greetVideo = document.createElement('video');
      greetVideo.srcObject = greetStream; greetVideo.autoplay = true; greetVideo.playsInline = true;
      greetVideo.style.cssText='position:fixed;left:-1px;top:-1px;width:1px;height:1px;opacity:0;pointer-events:none';
      document.body.appendChild(greetVideo);
      document.getElementById('greet-ring').classList.add('watching');
      document.getElementById('greet-name').textContent = 'Watching…';
      document.getElementById('greet-msg').textContent = 'Camera + mic live — say "hey aubie" any time';
      document.getElementById('greet-btn').textContent = '⏹ Stop';
      document.getElementById('face-widget').classList.add('show');
      greetMode = true;
      greetTimer = setInterval(checkForFace, 3000);
      moodTimer = setInterval(checkMood, MOOD_CHECK_INTERVAL_MS);
      startWatchListening();
      log('Greet mode ON','ok');
    } catch(e) { log('Camera error: '+e.message,'err'); }
  } else {
    if(greetStream) greetStream.getTracks().forEach(t=>t.stop());
    if(greetVideo) greetVideo.remove();
    clearInterval(greetTimer);
    clearInterval(moodTimer);
    stopWatchListening();
    document.getElementById('greet-ring').className='greet-ring';
    document.getElementById('greet-name').textContent='Waiting…';
    document.getElementById('greet-msg').textContent='Tap Watch to start';
    document.getElementById('greet-btn').textContent='👁️ Watch';
    document.getElementById('face-widget').classList.remove('show');
    greetMode=false; greetVideo=null;
    log('Greet mode OFF','info');
  }
}

let greetInFlight = false;
async function checkForFace() {
  if(!greetVideo || !greetMode) return;
  // Guard against overlap: /greet takes ~15s (face-ID + object detection)
  // but the poll timer fires every 3s - without this, calls piled up
  // concurrently and each one independently fired its own "Hello Matthew"
  // audio, producing a runaway repeat loop. Also skip while any other
  // audio (e.g. an Ask-Aubie reply) is already playing on the tablet.
  if(greetInFlight || audioBusy) return;
  greetInFlight = true;
  try {
    const canvas = document.createElement('canvas');
    canvas.width=320; canvas.height=240;
    canvas.getContext('2d').drawImage(greetVideo,0,0,320,240);
    // /greet expects a multipart upload (image: UploadFile) and replies with
    // a WAV body + info in headers, not JSON - see phone_ui_bug memory.
    const blob = await new Promise(resolve => canvas.toBlob(resolve,'image/jpeg',0.7));
    const form = new FormData();
    form.append('image', blob, 'frame.jpg');
    const r = await fetch('/greet', {method:'POST', body: form});
    if(!r.ok) return;
    const speakers = r.headers.get('X-Speakers') || 'none';
    const greeting = r.headers.get('X-Greeting') || '';
    const audioBlob = await r.blob();
    const allNames = speakers!=='none' ? speakers.split(',').map(s=>s.trim()).filter(Boolean) : [];
    const name = allNames[0] || null;
    const now = Date.now();
    // Don't re-greet the same person while they're just standing in frame -
    // once every 3 minutes is plenty, not every 30s. Also don't re-greet at
    // all while a class is actively in progress (currentClass truthy) -
    // "Hello Matthew" interrupting mid-lesson every 3 minutes while you're
    // just sitting in front of the camera working through a lesson is pure
    // noise, not a real greeting need. Reported live 2026-08-25.
    if(name && !currentClass && !(name===lastGreeted && now-lastGreetTime<180000)) {
      // /greet can take up to ~15s - by the time it resolves, Aubie may
      // already be mid-reply to something else (tap-to-talk, "hey aubie").
      // Don't barge in with "Hello Matthew"; just skip and try again next
      // poll once things are free (lastGreeted/lastGreetTime untouched).
      if(audioBusy) return;
      lastGreeted=name; lastGreetTime=now;
      // Auto-pick the linked family chip (set via ✏️ Customize → link a
      // face) so "go to class" already knows who's asking instead of
      // requiring a manual tap every time the tablet is shared.
      const linked = allNames
        .map(n => peopleCache.find(p => p.linked_face_name && p.linked_face_name.toLowerCase() === n.toLowerCase()))
        .filter(Boolean);
      if(linked.length && linked[0].family_id !== currentFamilyId) {
        pickPerson(linked[0].family_id);
        log(`Auto-selected ${linked[0].name} (recognized face: ${name})`,'ok');
      }
      if(linked.length > 1) {
        // More than one linked person in frame — full co-learning (two
        // people, two XP tracks, one session) isn't built yet; at least
        // surface that Aubie noticed rather than silently picking one.
        log(`Also in frame: ${linked.slice(1).map(p=>p.name).join(', ')} — co-learning not tracked yet, using ${linked[0].name}'s profile`,'info');
      }
      document.getElementById('greet-ring').classList.remove('watching');
      document.getElementById('greet-ring').classList.add('recognized');
      document.getElementById('greet-name').textContent = name;
      document.getElementById('greet-msg').textContent = greeting||`Welcome back, ${name}!`;
      await playAudioExclusive(URL.createObjectURL(audioBlob));
      // Being greeted counts as "hey aubie" - let them just start talking.
      watchAwake = true;
      clearTimeout(watchAwakeTimer);
      watchAwakeTimer = setTimeout(()=>{ watchAwake=false; }, 20000);
      if(name.toLowerCase().includes('gabriela')) burstHeartsAndFlowers();
      log(`Recognized: ${name}`,'ok');
      setTimeout(()=>{
        document.getElementById('greet-ring').classList.remove('recognized');
        document.getElementById('greet-ring').classList.add('watching');
      }, 5000);
    }
  } catch(e) { /* silent — keep watching */ }
  finally { greetInFlight = false; }
}

// Periodic mood check-in — piggybacks on the same open Watch-mode camera
// session as checkForFace() above (no extra permission prompt, no second
// stream), just on a much longer interval since a mood read every 5
// minutes is plenty and every 3s (checkForFace's cadence) would be both
// wasteful and, if it ever surfaced anything to the user, annoying.
// Silent by design: this logs to the Polyvagal Oracle's real state-check
// history (see /mood_check in assistant_server.py) so it accumulates
// there for the family to look at, rather than interrupting Watch mode
// with a popup every few minutes.
const MOOD_CHECK_INTERVAL_MS = 5 * 60 * 1000;

async function checkMood() {
  if (!greetVideo || !greetMode || moodInFlight || audioBusy) return;
  moodInFlight = true;
  try {
    const canvas = document.createElement('canvas');
    canvas.width = 320; canvas.height = 240;
    canvas.getContext('2d').drawImage(greetVideo, 0, 0, 320, 240);
    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.7));
    const form = new FormData();
    form.append('image', blob, 'frame.jpg');
    const r = await fetch('/mood_check', {method: 'POST', body: form});
    if (!r.ok) return;
    const data = await r.json();
    const icon = data.state === 'ventral' ? '🟢' : data.state === 'dorsal' ? '🔴' : '🟡';
    log(`Mood check-in: ${icon} ${data.state} (${data.member}) — ${data.note}`, 'info');
  } catch(e) { /* silent — try again next interval */ }
  finally { moodInFlight = false; }
}

async function loadKnownPeople() {
  try {
    const data = await fetch('/known_people').then(r=>r.json());
    const people = data.names||data.people||data.known||data.faces||[];
    const list = document.getElementById('known-list');
    if(!people.length) { list.innerHTML='<div style="font-size:12px;color:var(--sub)">No one enrolled yet — add someone below!</div>'; return; }
    list.innerHTML = people.map(p=>{
      const name = typeof p==='string'?p:(p.name||p.id||'Unknown');
      return `<div class="known-person"><div class="known-avatar">${name[0].toUpperCase()}</div>
        <div class="known-info"><div class="known-name">${name}</div><div class="known-sub">Face enrolled ✓</div></div></div>`;
    }).join('');
  } catch(e) { document.getElementById('known-list').innerHTML='<div style="font-size:12px;color:var(--sub)">Could not load — check rig connection</div>'; }
}

// ── Voice presets ────────────────────────────────────────────────────────
async function loadVoicePresets() {
  const sel = document.getElementById('voice-preset-select');
  try {
    const data = await fetch('/voice_presets').then(r=>r.json());
    sel.innerHTML = (data.presets||[]).map(p =>
      `<option value="${p.key}"${p.key===data.selected?' selected':''}>${p.label}</option>`
    ).join('');
  } catch(e) {
    sel.innerHTML = '<option value="">Could not load voices</option>';
    log('Voice presets load error: '+e.message,'err');
  }
}
async function selectVoicePreset() {
  const preset = document.getElementById('voice-preset-select').value;
  if(!preset) return;
  try {
    const form = new FormData();
    form.append('preset', preset);
    await fetch('/voice_presets/select', {method:'POST', body: form});
    log('Voice set to: '+preset,'ok');
    aubieSpeak("Hi, this is how I sound now.");
  } catch(e) { log('Voice select error: '+e.message,'err'); }
}
function previewVoicePreset() {
  aubieSpeak("Hi, I'm Aubie! This is what I sound like.");
}
loadVoicePresets();

function cameraBlockedMsg(id) {
  setResp(id, insecureOriginFixText(), 'error');
}

// ── Enroll: step 1 — open camera with face oval ──────────────────────────
let enrollStream = null;
async function startEnrollCamera() {
  if(!navigator.mediaDevices) { cameraBlockedMsg('enroll-resp'); return; }
  const name = document.getElementById('enroll-name').value.trim();
  if(!name) { setResp('enroll-resp','Enter the person\'s name first ☝️','error'); return; }
  try {
    enrollStream = await navigator.mediaDevices.getUserMedia({
      video:{facingMode:'user', width:{ideal:1280}, height:{ideal:960}}
    });
    const video = document.getElementById('enroll-video');
    video.srcObject = enrollStream;
    document.getElementById('enroll-viewfinder').style.display = 'block';
    document.getElementById('enroll-cam-btn').style.display  = 'none';
    document.getElementById('enroll-snap-btn').style.display = 'block';
    setResp('enroll-resp','📷 Camera live — center your face in the oval, then tap Snap','ok');
    log('Enroll camera started','ok');
  } catch(e) { setResp('enroll-resp','Camera error: '+e.message,'error'); }
}

// ── Enroll: step 2 — snap & send ─────────────────────────────────────────
// Helper: capture one frame from video, cropped to the face oval
function captureEnrollFrame(video) {
  const vw = video.videoWidth  || 640;
  const vh = video.videoHeight || 480;
  // The SVG oval (300×400 viewBox): cx=150,cy=185,rx=105,ry=140
  // Crop with 10% padding around the oval bounding box
  const svgW=300, svgH=400;
  const padX=15, padY=15;
  const ox1=45-padX, oy1=45-padY, ow=210+padX*2, oh=280+padY*2;
  const scaleX=vw/svgW, scaleY=vh/svgH;
  const cx=Math.round(Math.max(0,ox1*scaleX));
  const cy=Math.round(Math.max(0,oy1*scaleY));
  const cw=Math.round(Math.min(vw-cx, ow*scaleX));
  const ch=Math.round(Math.min(vh-cy, oh*scaleY));
  // Full-frame canvas (for the rig's face detector)
  const full = document.createElement('canvas');
  full.width=vw; full.height=vh;
  full.getContext('2d').drawImage(video,0,0);
  return full.toDataURL('image/jpeg',0.95).split(',')[1];
}

async function snapAndEnroll() {
  const name = document.getElementById('enroll-name').value.trim();
  if(!name || !enrollStream) return;

  // Flash effect
  const flash = document.getElementById('enroll-flash');
  flash.style.opacity='1'; setTimeout(()=>flash.style.opacity='0', 150);

  const video = document.getElementById('enroll-video');

  // Capture 3 frames 300ms apart, try each
  const frames = [];
  frames.push(captureEnrollFrame(video));
  await new Promise(r=>setTimeout(r,300));
  if(enrollStream) frames.push(captureEnrollFrame(video));
  await new Promise(r=>setTimeout(r,300));
  if(enrollStream) frames.push(captureEnrollFrame(video));

  // Stop camera
  if(enrollStream){ enrollStream.getTracks().forEach(t=>t.stop()); enrollStream=null; }
  document.getElementById('enroll-viewfinder').style.display = 'none';
  document.getElementById('enroll-cam-btn').style.display  = 'block';
  document.getElementById('enroll-snap-btn').style.display = 'none';
  document.getElementById('enroll-cam-btn').textContent = '📷 Retake';

  setResp('enroll-resp',`⏳ Enrolling ${name} — sending ${frames.length} frame(s)…`,'thinking');

  // /enroll_face expects one multipart request: name (Form) + all frames at
  // once under repeated "images" fields (UploadFile list) - it scores every
  // frame together and keeps the best ones, so frames must arrive as a batch,
  // not one-at-a-time. See phone_ui_bug memory for the JSON-vs-multipart trap.
  try {
    const form = new FormData();
    form.append('name', name);
    frames.forEach((b64,i) => form.append('images', b64ToBlob(b64), `frame${i}.jpg`));
    const r = await fetch('/enroll_face', {method:'POST', body: form});
    const data = await r.json();
    if(r.ok && data.ok) {
      document.getElementById('enroll-ring').setAttribute('stroke','#00e676');
      setResp('enroll-resp',`✅ ${name} enrolled! Aubie will recognize them now.\n\nKept ${data.kept} of ${data.submitted} frame(s).`,'ok');
      aubieSpeak(`Got it! I'll remember ${name} from now on.`);
      loadKnownPeople();
      log(`Enrolled: ${name}`,'ok');
    } else {
      const serverSaid = data.detail||JSON.stringify(data);
      setResp('enroll-resp',
        `⚠️ Enrollment failed.\n\nServer returned: ${serverSaid}\n\n` +
        `Tips:\n• Better lighting — face the window\n• Move closer to camera\n• Hold still for 3 seconds then tap Snap\n• Tap Retake to try again`,
      'error');
      log('Enroll failed — server said: '+serverSaid,'err');
    }
  } catch(e) {
    setResp('enroll-resp', `⚠️ Enroll error: ${e.message}`, 'error');
    log('Enroll error: '+e.message,'err');
  }
}

function b64ToBlob(b64, mime='image/jpeg') {
  const bytes = atob(b64);
  const arr = new Uint8Array(bytes.length);
  for(let i=0;i<bytes.length;i++) arr[i] = bytes.charCodeAt(i);
  return new Blob([arr], {type: mime});
}

loadKnownPeople();

// ════════════════════════════════════════════════════════════════════
// HEARTS & FLOWERS — greeting celebration
// ════════════════════════════════════════════════════════════════════
function burstHeartsAndFlowers() {
  const emojis = ['❤️','🌸','💛','🌺','💜','🌼','💙','🌷','🩷','✨','💫','🌻','💗','🍀'];
  const container = document.createElement('div');
  container.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:9999;overflow:hidden';
  document.body.appendChild(container);
  for(let i=0;i<40;i++) {
    setTimeout(()=>{
      const el = document.createElement('div');
      const emoji = emojis[Math.floor(Math.random()*emojis.length)];
      const x = Math.random()*100;
      const size = 20+Math.random()*32;
      const dur  = 2.5+Math.random()*2;
      const delay = Math.random()*1.5;
      el.textContent = emoji;
      el.style.cssText = `
        position:absolute; left:${x}vw; bottom:-60px;
        font-size:${size}px; opacity:0;
        animation: floatUp ${dur}s ease-out ${delay}s forwards;
        transform-origin: center;
      `;
      container.appendChild(el);
    }, i*40);
  }
  // Inject keyframe once
  if(!document.getElementById('float-style')) {
    const s=document.createElement('style'); s.id='float-style';
    s.textContent=`@keyframes floatUp {
      0%   { transform:translateY(0) rotate(0deg) scale(0.5); opacity:0; }
      15%  { opacity:1; }
      80%  { opacity:0.8; }
      100% { transform:translateY(-105vh) rotate(${Math.random()>0.5?'':'-'}${20+Math.random()*30}deg) scale(1.1); opacity:0; }
    }`;
    document.head.appendChild(s);
  }
  setTimeout(()=>container.remove(), 6000);
}

// ════════════════════════════════════════════════════════════════════
// SHOW ME — Unsplash image display
// ════════════════════════════════════════════════════════════════════
let lastShowMeQuery = '';
let showMePage = 1;
async function showMeImage() {
  const q = document.getElementById('showme-input').value.trim(); if(!q) return;
  lastShowMeQuery = q; showMePage = 1;
  await fetchAndShowImage(q, showMePage);
}
async function fetchAndShowImage(q, page) {
  const status = document.getElementById('showme-status');
  status.textContent = '🔍 Finding image…'; status.style.display='block';
  document.getElementById('showme-frame').style.display='none';
  document.getElementById('showme-actions').style.display='none';

  // /show_me_image returns a directly-displayable Unsplash URL (uses the
  // rig's UNSPLASH_ACCESS_KEY) - the old source.unsplash.com hotlink
  // fallback here was removed since Unsplash discontinued that Source API.
  let imageUrl = null;
  try {
    const form = new FormData();
    form.append('phrase', q);
    form.append('page', page);
    const r = await fetch('/show_me_image', {method:'POST', body: form});
    const data = await r.json();
    if(r.ok) imageUrl = data.url;
    else { status.textContent = `❌ ${data.detail||'Could not find an image'}`; return; }
  } catch(e) { status.textContent = `❌ ${e.message}`; return; }

  const img = document.getElementById('showme-img');
  img.onload = () => {
    document.getElementById('showme-frame').style.display='block';
    document.getElementById('showme-actions').style.display='flex';
    document.getElementById('showme-caption').textContent = q;
    status.textContent = `📸 Showing: "${q}"`;
    log(`Show Me: ${q}`,'ok');
    showInWidget(imageUrl, q);
  };
  img.onerror = () => { status.textContent = '❌ Could not load image — try a different search'; };
  img.src = imageUrl;
}

// Floating widget doubles as a small screen for Show Me images, not just
// the face - swaps back to the face automatically after a while, or right
// away if you tap Stop/close.
let widgetImgTimer = null;
function showInWidget(url, caption) {
  document.getElementById('face-widget').classList.add('show');
  document.getElementById('greet-ring').style.display = 'none';
  const img = document.getElementById('widget-img');
  img.src = url; img.style.display = 'block';
  document.getElementById('greet-name').textContent = '';
  document.getElementById('greet-msg').textContent = caption || '';
  document.getElementById('widget-close-btn').textContent = greetMode ? '⏹ Stop' : '✕ Close';
  clearTimeout(widgetImgTimer);
  widgetImgTimer = setTimeout(revertWidgetToFace, 20000);
}
function revertWidgetToFace() {
  clearTimeout(widgetImgTimer);
  document.getElementById('widget-img').style.display = 'none';
  document.getElementById('greet-ring').style.display = '';
  document.getElementById('greet-name').textContent = greetMode ? lastGreeted||'Watching…' : 'Waiting…';
  document.getElementById('greet-msg').textContent = greetMode ? 'Camera + mic live — say "hey aubie" any time' : 'Tap Watch to start';
  document.getElementById('widget-close-btn').textContent = greetMode ? '⏹ Stop' : '✕ Close';
  if(!greetMode) document.getElementById('face-widget').classList.remove('show');
}
function closeFaceWidget() {
  if(greetMode) { toggleGreetMode(); return; }
  revertWidgetToFace();
}

// ════════════════════════════════════════════════════════════════════
// TAP TO TALK — real audio to /converse (works on iOS Safari, unlike the
// SpeechRecognition-based "hey aubie" listening, which iOS has never
// supported in any browser - this uses MediaRecorder instead, and lets
// the server's own Whisper transcription do the work).
// ════════════════════════════════════════════════════════════════════
let talkRecorder = null;
let talkChunks = [];
let talkMicStream = null;

async function startRecording() {
  if(talkRecorder && talkRecorder.state==='recording') return;
  try {
    // Reuse Watch mode's already-open mic if it's running, else open a
    // one-off mic stream just for this recording.
    talkMicStream = (greetMode && greetStream) ? greetStream : await navigator.mediaDevices.getUserMedia({audio:true});
    talkChunks = [];
    const mimeType = ['audio/mp4','audio/webm'].find(t=>window.MediaRecorder && MediaRecorder.isTypeSupported(t)) || '';
    talkRecorder = mimeType ? new MediaRecorder(talkMicStream, {mimeType}) : new MediaRecorder(talkMicStream);
    talkRecorder.ondataavailable = (e) => { if(e.data.size>0) talkChunks.push(e.data); };
    talkRecorder.start();
    document.getElementById('talk-fab').classList.add('recording');
    document.getElementById('face-widget').classList.add('show');
    document.getElementById('greet-msg').textContent = 'Listening…';
  } catch(e) { log('Mic error: '+e.message,'err'); }
}
function cancelRecordingIfActive() {
  if(talkRecorder && talkRecorder.state==='recording') stopRecordingAndSend();
}
async function stopRecordingAndSend() {
  if(!talkRecorder || talkRecorder.state!=='recording') return;
  const mimeType = talkRecorder.mimeType || 'audio/webm';
  const blob = await new Promise(resolve => {
    talkRecorder.onstop = () => resolve(new Blob(talkChunks, {type: mimeType}));
    talkRecorder.stop();
  });
  document.getElementById('talk-fab').classList.remove('recording');
  // Only close the mic track if we opened a one-off stream for this - leave
  // Watch mode's own camera+mic stream running if that's what we borrowed.
  if(!(greetMode && greetStream === talkMicStream)) talkMicStream.getTracks().forEach(t=>t.stop());

  document.getElementById('widget-img').style.display = 'none';
  document.getElementById('greet-ring').style.display = '';
  document.getElementById('greet-msg').textContent = '⏳ Thinking…';
  clearTimeout(widgetImgTimer);
  try {
    const form = new FormData();
    form.append('audio', blob, 'clip.'+(mimeType.includes('mp4')?'mp4':'webm'));
    // If Watch's camera is live, include a fresh frame for real speaker-ID
    // (scan_faces) instead of a text-only, anonymous exchange.
    if(greetMode && greetVideo) {
      const canvas = document.createElement('canvas');
      canvas.width=320; canvas.height=240;
      canvas.getContext('2d').drawImage(greetVideo,0,0,320,240);
      const imgBlob = await new Promise(r=>canvas.toBlob(r,'image/jpeg',0.8));
      form.append('image', imgBlob, 'frame.jpg');
    }
    const r = await fetch('/converse', {method:'POST', body: form});
    if(!r.ok) throw new Error('HTTP '+r.status);
    const transcript = r.headers.get('X-Transcript') || '';
    const replyText  = r.headers.get('X-Reply-Text') || '';
    const speaker    = r.headers.get('X-Speaker') || 'none';
    const audioBlob  = await r.blob();
    document.getElementById('greet-name').textContent = speaker!=='none' ? speaker : '';
    document.getElementById('greet-msg').textContent = replyText || '(no reply)';
    // Princess Mode also fires in a camera conversation, not just on the
    // /greet "Hello Gabriela" - if Watch's camera frame ID'd her as the
    // speaker this turn, burst the hearts + flowers (same as checkForFace).
    if(speaker.toLowerCase().includes('gabriela')) burstHeartsAndFlowers();
    document.getElementById('widget-close-btn').textContent = greetMode ? '⏹ Stop' : '✕ Close';
    log('You said: '+transcript,'info');
    await playAudioExclusive(URL.createObjectURL(audioBlob));
    if(!greetMode) widgetImgTimer = setTimeout(closeFaceWidget, 20000);
  } catch(e) {
    document.getElementById('greet-msg').textContent = 'Sorry, something went wrong: '+e.message;
  }
}
async function showMeNext() {
  // Page through Unsplash's real results for the same query
  if(!lastShowMeQuery) return;
  showMePage += 1;
  await fetchAndShowImage(lastShowMeQuery, showMePage);
}
async function showMeOnScreen() {
  // Also send to the rig's TFT screen (existing dog display)
  if(!lastShowMeQuery) return;
  try {
    const form = new FormData();
    form.append('phrase', lastShowMeQuery);
    const r = await fetch('/generate_image', {method:'POST', body: form});
    if(!r.ok) throw new Error('HTTP '+r.status);
    log('Sent to screen','ok');
  } catch(e) { log('Screen send failed: '+e.message,'err'); }
}

// ════════════════════════════════════════════════════════════════════
// ABOUT / WHAT IS AUBIEETERNAL
// ════════════════════════════════════════════════════════════════════
async function askWhatIsAubie() {
  setResp('about-resp','⏳ Asking Aubie…','thinking');
  const q = `Someone just asked what you are. Answer as yourself - the AI teacher that lives in `
    + `this machine - in a warm, first-person voice, grounded in these real facts about `
    + `AUBIEETERNAL (don't just riff generic AI talk):\n\n`
    + `- You're a free, open-source "sovereign school" - 265 lessons across 51 tracks, spanning `
    + `things like critical thinking, antifragility, Bitcoin & sovereign money, steelmanning, the `
    + `nervous system, philosophy, and more - every lesson works from age 5 through PhD depth at `
    + `once.\n`
    + `- No tuition, no paperwork, no gatekeepers, no special hardware - runs fully offline after `
    + `a one-time setup, on a single ~$200 laptop and a projector, for up to 30 children at once. `
    + `Built for a 7-year-old in an orphanage with a donated laptop just as much as a PhD student `
    + `going deeper than their university allows.\n`
    + `- There are 4 real degree programs - Sovereign Associate, Truth Architect, Master of `
    + `Epistemic Rigor, and Eternal Founder (PhD) - and every completed degree is sealed on `
    + `Bitcoin so it can't be faked or erased. The PhD's actual capstone requirement is deploying `
    + `a free school for a community that doesn't have one yet.\n`
    + `- Everything is CC0 public domain - the knowledge belongs to no one and everyone.\n`
    + `- You remember real conversations and lessons over time, not just this one exchange, and `
    + `you can hold an actual back-and-forth "let's go to class" conversation on real curriculum `
    + `topics, not just answer one-off questions.\n\n`
    + `Explain what you are and what you're for in 4-6 sentences, warm and genuine, not a feature `
    + `list read aloud - like you're actually introducing yourself to a family meeting you for the `
    + `first time.`;
  try {
    const data = await aubieTextChat(q);
    const reply = data.reply||data.response||data.answer||data.text||data.output||JSON.stringify(data);
    setResp('about-resp', reply, 'ok');
    aubieSpeak(reply);
    log('Aubie described itself','ok');
  } catch(e) { setResp('about-resp','Error: '+e.message,'error'); }
}

// ════════════════════════════════════════════════════════════════════
// 1. TODAY'S LESSON — real AUBIEETERNAL curriculum (curriculum.py),
//    real per-person progress (family_profiles.py), structured Q&A
//    (/class/start + /class/answer, scored + XP on the server).
// ════════════════════════════════════════════════════════════════════
let currentFamilyId = localStorage.getItem('aubie_family_id') || null;
let currentClass    = null; // {family_id, lesson_key, title, track, goodTurns, turnsRequired} while a lesson is in progress
let peopleCache     = [];   // last /class/people response, so the editor can prefill current values
const LEVEL_ICON = {kid:'🧒', teen:'🧑', adult:'🧑‍🎓', expert:'🎓'};

async function loadPeople() {
  try {
    const data = await (await fetch('/class/people')).json();
    peopleCache = data.people || [];
    if(!currentFamilyId && peopleCache.length) currentFamilyId = peopleCache[0].family_id;
    document.getElementById('people-chips').innerHTML = peopleCache.map(p =>
      `<div class="topic-chip person-chip${p.family_id===currentFamilyId?' active':''}" `
      + `data-fid="${p.family_id}" onclick="pickPerson('${p.family_id}')">`
      + `<div class="topic-icon">${p.emoji}</div>${p.name}<div style="font-size:9px;color:var(--sub);margin-top:2px">${LEVEL_ICON[p.level]||''} ${p.level}</div></div>`
    ).join('');
    loadTodayLesson();
    loadProgress();
  } catch(e) { log('Could not load people: '+e.message,'err'); }
}
function pickPerson(fid) {
  currentFamilyId = fid;
  currentClass = null; // switching person mid-question would score the wrong profile
  localStorage.setItem('aubie_family_id', fid);
  document.querySelectorAll('#people-chips .person-chip').forEach(
    c => c.classList.toggle('active', c.dataset.fid === fid)
  );
  document.getElementById('person-editor').style.display = 'none';
  loadTodayLesson();
  loadProgress();
}
// "✏️ Customize" — lets a family put a real name/level/note behind a chip
// (e.g. Beta → "Mom, Adult" or "Dad, Expert, PhD in physics") so /class/start
// and /class/answer pitch lessons and follow-up questions at the right depth
// instead of treating every learner the same. Saved server-side per family_id.
async function togglePersonEditor() {
  if(!currentFamilyId) { setResp('lesson-resp','👋 Pick who\'s learning above first.','error'); return; }
  const el = document.getElementById('person-editor');
  const opening = el.style.display === 'none';
  el.style.display = opening ? 'block' : 'none';
  if(opening) {
    const p = peopleCache.find(x => x.family_id === currentFamilyId) || {};
    document.getElementById('pe-name').value  = p.name || '';
    document.getElementById('pe-level').value = p.level || 'kid';
    document.getElementById('pe-note').value  = p.note || '';
    const faceSel = document.getElementById('pe-face');
    let faces = [];
    try { faces = (await fetch('/known_people').then(r=>r.json())).names || []; } catch(e) {}
    faceSel.innerHTML = '<option value="">No linked face (manual chip-tap only)</option>'
      + faces.map(f => `<option value="${f}"${f===p.linked_face_name?' selected':''}>${f}</option>`).join('');
  }
}
async function savePersonProfile() {
  const name      = document.getElementById('pe-name').value.trim();
  const level     = document.getElementById('pe-level').value;
  const note      = document.getElementById('pe-note').value.trim();
  const face_name = document.getElementById('pe-face').value;
  try {
    await post('/class/profile', {family_id: currentFamilyId, name, level, note, face_name});
    togglePersonEditor();
    log('Saved profile for '+currentFamilyId,'ok');
    await loadPeople();
  } catch(e) { log('Could not save profile: '+e.message,'err'); }
}
async function loadTodayLesson() {
  if(!currentFamilyId) return;
  try {
    const data = await (await fetch('/class/preview?family_id='+encodeURIComponent(currentFamilyId))).json();
    document.querySelector('#lesson-card .lesson-tag').textContent = data.track || 'CLASS';
    document.getElementById('lesson-title').textContent = data.title || '—';
    document.getElementById('lesson-desc').textContent = data.desc || '';
  } catch(e) { log('Could not load lesson preview: '+e.message,'err'); }
}
// "Let's go to class" - picks this person's next not-yet-completed lesson
// from the real curriculum and has Ollama open it like a real teacher
// (warm intro + one comprehension question), then waits for the answer.
// Reachable by tapping the lesson card, saying "hey aubie, let's go to
// class", or typing it in the Watch card's question box (CLASS_TRIGGER_RE,
// defined up in the Greet Mode section). Once a question is pending, the
// Ask box / "hey aubie" / typed watch box all route the next message to
// /class/answer (see submitClassAnswer()) instead of freeform chat.
async function startClass() {
  if(!currentFamilyId) { setResp('lesson-resp','👋 Pick who\'s learning above first.','error'); return; }
  switchTab('teach');
  document.getElementById('tab-teach').scrollTo({top:0,behavior:'smooth'});
  setResp('ask-resp', renderChatHistory() + (chatHistory.length?'\n\n':'') + '⏳ Getting the classroom ready…', 'thinking');
  document.getElementById('greet-msg').textContent = "🎓 Let's go to class!";
  log('Starting class for '+currentFamilyId,'info');
  try {
    const data = await post('/class/start', {family_id: currentFamilyId, history: chatHistory});
    if(data.done) {
      currentClass = null;
      setResp('ask-resp', renderChatHistory() + (chatHistory.length?'\n\n':'') + `🎉 ${data.message}`, 'ok');
      document.getElementById('greet-msg').textContent = data.message;
      log('Class: all lessons complete','ok');
      await aubieSpeak(data.message);
      return;
    }
    currentClass = {
      family_id: currentFamilyId, lesson_key: data.lesson_key, title: data.title, track: data.track,
      goodTurns: data.good_turns || 0, turnsRequired: data.turns_required || 2,
    };
    chatHistory.push({role:'user', content: data.opener_prompt}, {role:'assistant', content: data.teacher_reply});
    setResp('ask-resp', renderChatHistory(), 'ok');
    document.getElementById('greet-msg').textContent = data.teacher_reply;
    log(data.resumed ? `Resumed class: ${data.title} (${data.good_turns}/${data.turns_required})` : `Class started: ${data.title}`, 'ok');
    await aubieSpeak(data.teacher_reply);
    loadProgress();
  } catch(e) {
    setResp('ask-resp', renderChatHistory() + `\n\n⚠️ Error starting class: ${e.message}`, 'error');
    log('Class start error: '+e.message,'err');
  }
}
// Scores the student's answer to the pending class question via
// /class/answer. The reply always includes a follow-up question, so the
// SAME lesson stays open (currentClass persists) until enough good answers
// (turnsRequired, default 2) have landed — a lesson is a short back-and-
// forth, not a one-shot quiz. Once complete, currentClass clears (XP/streak
// saved server-side) and a "Continue" button chains straight into the next
// lesson so a real study session doesn't stall after just one topic.
async function submitClassAnswer(answer) {
  setResp('ask-resp', renderChatHistory() + `\n\n🧑 You: ${answer}\n\n⏳ Checking your answer…`, 'thinking');
  log('Class answer submitted','info');
  try {
    const cls = currentClass;
    const data = await post('/class/answer', {
      family_id: cls.family_id, lesson_key: cls.lesson_key, answer, history: chatHistory,
      good_turns: cls.goodTurns,
    });
    if(data.error) throw new Error(data.error);
    chatHistory.push({role:'user', content: answer}, {role:'assistant', content: data.feedback});
    setResp('ask-resp', renderChatHistory(), 'ok');
    document.getElementById('greet-msg').textContent = data.feedback;
    await aubieSpeak(data.feedback);
    if(data.lesson_complete) {
      currentClass = null;
      const nextMsg = data.next_available
        ? `<button class="btn btn-accent btn-sm" onclick="startClass()" style="margin-top:8px">▶️ Continue Class — Next Lesson</button>`
        : ' 🎉 That was the last lesson — all caught up!';
      setResp('lesson-resp', `✅ +${data.xp_awarded} XP · "${data.title}" complete!`, 'ok');
      document.getElementById('lesson-resp').innerHTML += nextMsg;
      loadTodayLesson();
      loadProgress();
    } else {
      currentClass.goodTurns = data.good_turns;
      setResp('lesson-resp', `${data.passed_turn ? '👍' : '💬'} ${data.good_turns}/${data.turns_required} good answers so far on `
        + `"${data.title}" — keep the conversation going below.`, '');
    }
    log(`Class answer scored: ${data.score} (turn ${data.good_turns}/${data.turns_required})`,'ok');
  } catch(e) {
    setResp('ask-resp', renderChatHistory() + `\n\n⚠️ Error: ${e.message}`, 'error');
    log('Class answer error: '+e.message,'err');
  }
}

// "Discuss with Aubie" - reached via ?discuss=<text>&family_id=<id> on this
// page's own URL, sent by the browser extension's "💬 Discuss with Aubie"
// button (see AUBIEETERNAL_extension/popup/popup.js) so something read
// while browsing becomes a real conversation here instead of just sitting
// in a popup. Not a graded class question - just opens the same Ask-box
// chat thread with a warm discussion prompt.
async function checkDiscussParam() {
  const params  = new URLSearchParams(location.search);
  const discuss = params.get('discuss');
  if(!discuss) return;
  const fid = params.get('family_id');
  if(fid) pickPerson(fid);
  switchTab('teach');
  document.getElementById('tab-teach').scrollTo({top:0,behavior:'smooth'});
  const opener = `I just read this while browsing: "${discuss}"\n\nLet's talk about it - what's `
    + `genuinely interesting here, what's worth questioning, and is there anything I should know `
    + `more about? Keep it conversational, not a lecture.`;
  setResp('ask-resp', '⏳ Getting Aubie’s take…', 'thinking');
  log('Discussing browsed content with Aubie','info');
  try {
    const data = await aubieTextChat(opener, {history: chatHistory});
    const reply = data.reply||data.response||data.answer||data.text||data.output||JSON.stringify(data);
    chatHistory.push({role:'user', content:opener}, {role:'assistant', content:reply});
    setResp('ask-resp', renderChatHistory(), 'ok');
    document.getElementById('greet-msg').textContent = reply;
    log('Discuss started','ok');
    await aubieSpeak(reply);
  } catch(e) {
    setResp('ask-resp', `⚠️ Error: ${e.message}`, 'error');
    log('Discuss error: '+e.message,'err');
  }
}

(async () => {
  await loadPeople();
  await checkDiscussParam();
})();

// ════════════════════════════════════════════════════════════════════
// 2. RESEARCH
// ════════════════════════════════════════════════════════════════════
async function sendResearch() {
  const q = document.getElementById('research-input').value.trim(); if(!q) return;
  setResp('research-status','🔍 Researching…','thinking');
  document.getElementById('research-result').style.display='none';
  log(`Research: ${q.slice(0,50)}`);
  try {
    const data = await aubieTextChat(`Research this topic thoroughly and give me a detailed summary with key facts, discoveries, and why it matters: ${q}`);
    const result = data.reply||data.response||data.answer||data.text||data.output||JSON.stringify(data);
    setResp('research-status','✅ Research complete','ok');
    const el = document.getElementById('research-result');
    el.textContent = result; el.style.display='block';
    if(document.getElementById('speak-toggle')?.checked) aubieSpeak(result);
    log('Research done','ok');
  } catch(e) { setResp('research-status','Error: '+e.message,'error'); log('Research failed','err'); }
}

// ════════════════════════════════════════════════════════════════════
// 3. PROGRESS — real per-person stats from family_profiles.py via
//    /class/progress (streak, XP, lessons done, weekly XP, per-track %).
//    "Questions asked" stays a simple on-device counter (free-form Ask
//    box chat isn't tied to a curriculum lesson, so it has nothing to
//    report to the server) — everything curriculum-related is real now.
// ════════════════════════════════════════════════════════════════════
async function loadProgress() {
  const asks = parseInt(localStorage.getItem('aubie_asks')||'0');
  document.getElementById('asks-num').textContent = asks;
  if(!currentFamilyId) {
    document.getElementById('streak-num').textContent = '—';
    document.getElementById('topics-num').textContent = '—';
    document.getElementById('track-bars').innerHTML = '<div style="font-size:11px;color:var(--sub)">Pick who\'s learning above to see progress.</div>';
    return;
  }
  try {
    const data = await (await fetch('/class/progress?family_id='+encodeURIComponent(currentFamilyId))).json();
    document.getElementById('streak-num').textContent = data.streak_days ?? 0;
    document.getElementById('topics-num').textContent = data.lessons_done ?? 0;
    const bars = document.getElementById('track-bars');
    const weeklyLine = `<div style="font-size:11px;color:var(--sub);margin-bottom:10px">`
      + `🔥 ${data.total_xp||0} XP total · +${data.weekly_xp||0} XP this week · `
      + `${data.lessons_done||0}/${data.lessons_total||0} lessons</div>`;
    bars.innerHTML = weeklyLine + (data.tracks||[]).map(t => `<div class="track-row">
      <span class="track-name">${t.track}</span>
      <div class="track-bar"><div class="track-fill" style="width:${t.pct}%;background:${t.color}"></div></div>
      <span class="track-pct">${t.done}/${t.total}</span>
    </div>`).join('');
  } catch(e) { log('Could not load progress: '+e.message,'err'); }
}
function incrementProgress() {
  // Free-form Ask box chat only — lesson XP is awarded server-side by
  // /class/answer, not counted here.
  const asks = parseInt(localStorage.getItem('aubie_asks')||'0') + 1;
  localStorage.setItem('aubie_asks', asks);
  document.getElementById('asks-num').textContent = asks;
}

// ════════════════════════════════════════════════════════════════════
// 4. DAILY QUESTION
// ════════════════════════════════════════════════════════════════════
const COSMOS = [
  'If the universe had no observers, would it still exist?',
  'Is mathematics discovered or invented?',
  'What would you do if you knew you could not fail?',
  'If you could talk to your 10-year-old self, what would you teach them?',
  'Why does anything exist rather than nothing?',
  'What is the most important question humanity has not yet answered?',
  'If an AI becomes smarter than humans, who is responsible for its choices?',
  'Is it possible to truly understand another person\'s experience?',
  'What would a truly fair world look like?',
  'If you had one year left, what would you spend it learning?',
  'Does the past still exist?',
  'What makes a life well-lived?',
  'Is there a difference between being smart and being wise?',
  'What would you create if you had unlimited resources?',
  'Why do humans seek meaning?',
];
let currentCosmosQ = '';
function loadCosmos() {
  const idx = Math.floor(Math.random() * COSMOS.length);
  currentCosmosQ = COSMOS[idx];
  document.getElementById('cosmos-q').textContent = currentCosmosQ;
  document.getElementById('cosmos-date').textContent = new Date().toDateString() + ' · Think before you tap';
  document.getElementById('cosmos-resp').className = 'resp';
}
async function answerCosmos() {
  if(!currentCosmosQ) return;
  const q = `Let\'s explore this question together: "${currentCosmosQ}" — give me a thoughtful, mind-expanding answer with multiple perspectives.`;
  document.getElementById('ask-input').value = q;
  switchTab('teach');
  document.getElementById('tab-teach').scrollTo({top:0,behavior:'smooth'});
  setResp('ask-resp','⏳ Thinking deeply…','thinking');
  await sendAsk();
}
loadCosmos();

// ════════════════════════════════════════════════════════════════════
// 5. MEMORY
// ════════════════════════════════════════════════════════════════════
async function loadMemory() {
  const list = document.getElementById('memory-list');
  list.innerHTML = '<div style="color:var(--sub);font-size:12px">Loading…</div>';
  try {
    let data;
    try { data = await fetch('/memory').then(r=>r.json()); } catch {
      try { data = await fetch('/memory/recent').then(r=>r.json()); } catch {
        // Fall back to localStorage history
        const asks = parseInt(localStorage.getItem('aubie_asks')||'0');
        list.innerHTML = `<div class="mem-entry"><div class="mem-q">📊 Session Stats</div>
          <div>Questions asked: ${asks} · Topics explored: ${localStorage.getItem('aubie_topics')||0}</div>
          <div class="mem-ts">Stored locally on this device</div></div>`;
        return;
      }
    }
    const entries = data.memories||data.exchanges||data.recent||data.history||[];
    if(!entries.length) { list.innerHTML='<div style="color:var(--sub);font-size:12px">No memory yet — start asking Aubie things!</div>'; return; }
    list.innerHTML = entries.slice(-6).reverse().map(e=>`
      <div class="mem-entry">
        <div class="mem-q">${e.user||e.question||e.input||'…'}</div>
        <div>${(e.assistant||e.answer||e.response||'').slice(0,120)}…</div>
        <div class="mem-ts">${e.timestamp||e.ts||''}</div>
      </div>`).join('');
  } catch(e) { list.innerHTML=`<div style="color:var(--red);font-size:12px">Could not load memory: ${e.message}</div>`; }
}
loadMemory();

// ════════════════════════════════════════════════════════════════════
// 6. LIVE VISION
// ════════════════════════════════════════════════════════════════════
let liveVisionOn = false;
let liveStream = null;
let liveTimer = null;
async function toggleLiveVision() {
  if(!liveVisionOn) {
    if(!navigator.mediaDevices) { log('Camera blocked — see the CAMERA BLOCKED banner near the top for the fix','err'); return; }
    try {
      liveStream = await navigator.mediaDevices.getUserMedia({video:{facingMode:'environment'}});
      const feed = document.getElementById('vision-feed');
      feed.innerHTML = '';
      const video = document.createElement('video');
      video.srcObject = liveStream; video.autoplay = true; video.playsInline = true;
      video.style.cssText = 'width:100%;border-radius:10px';
      feed.appendChild(video);
      document.getElementById('live-dot').classList.add('on');
      document.getElementById('live-lbl').textContent = 'LIVE — Aubie is watching';
      document.getElementById('live-btn').textContent = '⏹ Stop';
      liveVisionOn = true;
      liveTimer = setInterval(()=>captureAndDescribe(video), 15000);
      log('Live vision started','ok');
    } catch(e) { log('Camera error: '+e.message,'err'); }
  } else {
    if(liveStream) liveStream.getTracks().forEach(t=>t.stop());
    clearInterval(liveTimer); liveTimer = null;
    document.getElementById('vision-feed').innerHTML = '📷 Camera off';
    document.getElementById('live-dot').classList.remove('on');
    document.getElementById('live-lbl').textContent = 'Camera off — tap to go live';
    document.getElementById('live-btn').textContent = '▶ Go Live';
    document.getElementById('vision-caption').style.display='none';
    liveVisionOn = false;
    log('Live vision stopped','info');
  }
}
async function captureAndDescribe(video) {
  try {
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth; canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video,0,0);
    const b64 = canvas.toDataURL('image/jpeg',0.7).split(',')[1];
    const data = await post('/vision/describe',{image:b64,prompt:'What do you see? Be brief and educational.'});
    const caption = data.description||data.reply||data.text||'';
    if(caption) {
      const el = document.getElementById('vision-caption');
      el.textContent = '👁️ ' + caption;
      el.style.display = 'block';
    }
  } catch(e) { log('Vision error: '+e.message,'err'); }
}
</script>

<script>
// ── Minimal interface localization ────────────────────────────────────────
// Key-surface only (tab bar, card titles, primary buttons, main input
// placeholders). Language is resolved: ?lang= query  >  localStorage
// 'aubieLang'  >  the install-time choice from GET /language ('configured',
// unless 'auto')  >  English. English is the source text, so lang==='en' is
// a no-op. This is a JS-side patch on purpose - zero changes to the markup
// above - so untranslated strings simply stay in English rather than break.
// Follow-up: welcome-card body paragraph, Show Me / Research placeholders
// (no id), toast/log messages.
(function () {
  const TAB = { teach: 'Enseñar', build: 'Crear', dog: 'Perro', aubie: 'Aubie', portal: 'Portal' };
  const T = {
    'WHAT IS THIS?': '¿QUÉ ES ESTO?',
    'Your Always-On AI Teaching Station': 'Tu estación de enseñanza con IA, siempre disponible',
    '🤖 Ask Aubie What It Is': '🤖 Pregúntale a Aubie qué es',
    '✕ Hide': '✕ Ocultar',
    "👋 Greet Mode · Who's Here?": '👋 Modo saludo · ¿Quién está aquí?',
    'OR TYPE A QUESTION:': 'O ESCRIBE UNA PREGUNTA:',
    'AUBIE KNOWS:': 'AUBIE CONOCE A:',
    '👁️ Watch': '👁️ Vigilar',
    '➕ Add Person': '➕ Añadir persona',
    '💬 Ask': '💬 Preguntar',
    '🪪 Teach Aubie a Face': '🪪 Enséñale una cara a Aubie',
    '📷 Open Camera': '📷 Abrir cámara',
    '📸 Snap & Save': '📸 Capturar y guardar',
    '↻ Refresh List': '↻ Actualizar lista',
    '🧠 Ask · Learn · Teach': '🧠 Pregunta · Aprende · Enseña',
    '⚡ Ask Aubie': '⚡ Pregúntale a Aubie',
    '🔄 New Conversation': '🔄 Nueva conversación',
    '🎤 Voice': '🎤 Voz',
    '🔊 Preview': '🔊 Escuchar',
    '📚 Quick Topics': '📚 Temas rápidos',
    '📷 Camera · Vision': '📷 Cámara · Visión',
    '📸 Snapshot': '📸 Foto',
    '👁️ Describe': '👁️ Describir',
    '🖼️ Show Me': '🖼️ Muéstrame',
    '🔄 Another': '🔄 Otra',
    '📺 Also on Screen': '📺 También en pantalla',
    "📚 Today's Lesson": '📚 Lección de hoy',
    '🔍 Research': '🔍 Investigar',
    '🔍 Research It': '🔍 Investígalo',
    '🎓 My Progress': '🎓 Mi progreso',
    '↻ Refresh Progress': '↻ Actualizar progreso',
    '🌌 Daily Question': '🌌 Pregunta del día',
    '💬 Discuss with Aubie': '💬 Comentar con Aubie',
    '🎲 New Question': '🎲 Otra pregunta',
    '🧠 What Aubie Remembers': '🧠 Lo que Aubie recuerda',
    '↻ Refresh Memory': '↻ Actualizar memoria',
    '👁️ Live Vision': '👁️ Visión en vivo',
    '⚡ System': '⚡ Sistema',
    '✅ Health': '✅ Estado',
    '🗑️ Clear Log': '🗑️ Borrar registro',
    '📋 Log': '📋 Registro',
    '🎨 Customize Face': '🎨 Personalizar cara',
    '⚙️ Build & Run': '⚙️ Crear y ejecutar',
    '🔨 What Should Aubie Build?': '🔨 ¿Qué debería crear Aubie?',
    '📄 Generated Code': '📄 Código generado',
    '⚡ Quick Builds': '⚡ Creaciones rápidas',
    '🕹️ RC Control': '🕹️ Control RC',
    '🦿 Movement': '🦿 Movimiento',
    '👁️ Follow Mode': '👁️ Modo seguir',
    '😊 Face': '😊 Cara',
    '🎨 Face Customise': '🎨 Personalizar cara',
    '🎪 Tricks': '🎪 Trucos',
    '🧑‍🏫 Teach Aubie a Person': '🧑‍🏫 Enséñale una persona a Aubie',
    '🔩 Servo Control': '🔩 Control de servos',
    '💬 Say / Command': '💬 Decir / Comando',
    '🔵 Bluetooth Setup': '🔵 Configurar Bluetooth',
  };
  const PH = {
    '#watch-ask-input': 'Escribe una pregunta para Aubie…',
    '#enroll-name': '¿Quién es? (p. ej. Matthew, Gabriela…)',
    '#ask-input': 'Pregunta lo que quieras…\nExplica la fotosíntesis · ¿Qué es la recursión? · Ayúdame a entender álgebra · ¿Qué es Bitcoin?',
    '#pe-name': 'Nombre (p. ej. Papá, Gabriela)',
    '#pe-note': 'Nota opcional (p. ej. Doctorado en física)',
    '#person-name': 'Nombre de la persona…',
    '#say-input': 'Escribe algo para que Aubie lo diga…',
    '#aubie-chat-input': 'Habla con Aubie…',
    '#build-input': 'Describe qué crear…',
  };
  // Normalize whitespace and curly punctuation so map keys written with a
  // straight apostrophe match card titles that use either form.
  const norm = (s) => (s || '').replace(/\s+/g, ' ').replace(/[‘’]/g, "'").replace(/[“”]/g, '"').trim();

  function apply(lang) {
    lang = (lang === 'es') ? 'es' : 'en';
    try { localStorage.setItem('aubieLang', lang); } catch (e) {}
    document.documentElement.lang = lang;
    if (lang === 'en') return;

    // Tab bar: keep the .tab-icon span, translate only the trailing word.
    document.querySelectorAll('.tab-btn').forEach((btn) => {
      const key = (btn.id || '').replace('tbtn-', '');
      if (!TAB[key]) return;
      const t = [...btn.childNodes].reverse().find((n) => n.nodeType === 3 && norm(n.textContent));
      if (t) t.textContent = TAB[key];
    });

    // Leaf elements whose whole text is a known string.
    document.querySelectorAll('.tab-btn, .btn, .card-title, .card-title>span:first-child, h1, h2, h3, div, span, p, label').forEach((el) => {
      if (el.children.length) return;
      const hit = T[norm(el.textContent)];
      if (hit) el.textContent = hit;
    });

    // Welcome-card body paragraph (has inline <b>/<i>/<br>, handled by id).
    const wc = document.getElementById('welcome-card');
    const para = wc && [...wc.querySelectorAll('div')].find((d) => /free, always-on AI teacher/i.test(d.textContent));
    if (para) {
      para.innerHTML =
        '<b style="color:var(--text)">AUBIEETERNAL</b> es un maestro con IA gratuito y siempre disponible, hecho para dar una educación de primer nivel a <i>cualquiera, en cualquier lugar</i> — un teléfono, una pantalla táctil, la mesa de la cocina, un orfanato.<br><br>' +
        'Pregúntale lo que sea. Enseña. Recuerda cada lección, cada pregunta, cada conversación — y va formando una imagen de lo que sabes y de lo que estás aprendiendo.<br><br>' +
        'A medida que añades cursos, robots y herramientas de IA, <b style="color:var(--accent)">Aubie crece contigo</b> — siempre recordando, siempre enseñando.';
    }

    // Placeholders.
    for (const sel in PH) {
      const el = document.querySelector(sel);
      if (el) el.setAttribute('placeholder', PH[sel]);
    }
  }

  const qs = new URLSearchParams(location.search).get('lang');
  let lang = (qs || (function () { try { return localStorage.getItem('aubieLang'); } catch (e) { return null; } })() || '').toLowerCase();
  const run = () => {
    if (lang === 'es' || lang === 'en') { apply(lang); return; }
    fetch('/language')
      .then((r) => r.json())
      .then((d) => apply(d && d.configured === 'es' ? 'es' : 'en'))
      .catch(() => apply('en'));
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run);
  else run();
})();
</script>

<script>
// Register the service worker so this page is an installable PWA.
// A failed registration (e.g. plain-HTTP access) is non-fatal - the page
// works exactly as before, just not installable.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', function () {
    navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(function () {});
  });
}
</script>
</body>
</html>"""


# ── Routes ────────────────────────────────────────────────────────────────

@router.get("/remote", response_class=HTMLResponse)
async def teaching_station():
    return HTML


@router.get("/manifest.webmanifest")
async def pwa_manifest():
    return Response(
        content=json.dumps(PWA_MANIFEST),
        media_type="application/manifest+json",
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/sw.js")
async def pwa_service_worker():
    return Response(
        content=PWA_SW_JS,
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"},
    )


@router.get("/pwa/{filename}")
async def pwa_icon(filename: str):
    if filename not in PWA_ICON_FILES:
        return Response(status_code=404)
    return FileResponse(
        PWA_ASSETS / filename,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/apple-touch-icon.png")
@router.get("/apple-touch-icon-precomposed.png")
async def apple_touch_icon():
    # iOS probes these well-known root paths for the home-screen icon
    # even when the <link> tag is present; serve the same 180x180 PNG.
    return FileResponse(
        PWA_ASSETS / "apple-touch-icon-180.png",
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/health")
async def health():
    return {"status": "ok", "service": "AUBIEETERNAL Teaching Station"}


@router.post("/ask-text")
async def ask_text(request: Request):
    """Text-to-text chat via local Ollama — no audio needed."""
    body = await request.json()
    message = body.get("message") or body.get("query") or body.get("text") or body.get("prompt") or ""
    history = body.get("history") or []
    speaker = body.get("speaker") or None
    if not message:
        return {"error": "No message provided"}
    return await _ollama_chat(message, history, speaker=speaker)


@router.get("/ollama-models")
async def ollama_models():
    """List models Ollama currently has available."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags")
            return r.json()
    except Exception as e:
        return {"error": str(e)}


@router.post("/proxy/dog")
async def proxy_dog(request: Request):
    body = await request.json()
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            r = await client.post(f"{AUBIE_URL}/dog/command", json=body)
            return r.json()
        except Exception as e:
            return {"error": str(e), "note": "Dog server offline — expected if dog not running"}


# ── "Let's Go To Class" — real curriculum lessons, real per-person progress ─
# Ties the phone UI's class feature to curriculum.py (same lesson tree the
# Streamlit portal's Curriculum Map is meant to read) and family_profiles.py
# (same durable XP/streak/lessons_completed store the portal already uses),
# so a lesson finished on the phone is a lesson finished, full stop — not a
# separate localStorage-only counter. See FAMILY_REGISTRY for the selectable
# people (no speaker-ID needed here — the phone just asks who's learning).

def _week_ago_iso() -> str:
    return (datetime.date.today() - datetime.timedelta(days=7)).isoformat()

# How many good (>=0.5) answers in a row a lesson takes before it's marked
# complete + XP awarded — one lesson is a short back-and-forth conversation,
# not a single-shot quiz.
GOOD_TURNS_TO_COMPLETE = 2

LEARNER_LEVELS = {"kid", "teen", "adult", "expert"}
LEVEL_INSTRUCTIONS = {
    "kid":    "a curious kid — keep language warm, simple, and concrete, use everyday examples, "
              "no jargon",
    "teen":   "a teenager — clear and direct, respect their intelligence, real-world examples okay",
    "adult":  "an adult learner — normal adult vocabulary, practical framing, no baby-talk",
    "expert": "someone with real expertise in this area — engage at a genuinely advanced level, "
              "use precise terminology, don't oversimplify, and it's fine if they push back on you",
}


def _level_instruction(level: str, note: str) -> str:
    text = LEVEL_INSTRUCTIONS.get(level, LEVEL_INSTRUCTIONS["kid"])
    return f"{text}; specifically: {note}" if note else text


@router.get("/class/people")
async def class_people():
    people = []
    for fid, info in FAMILY_REGISTRY.items():
        stats = load_family_stats(fid)
        people.append({
            "family_id": fid, "display_name": info["display_name"],
            "name": stats.get("learner_name") or info["kid_name"],
            "level": stats.get("learner_level", "kid"),
            "note": stats.get("learner_note", ""),
            "linked_face_name": stats.get("linked_face_name", ""),
            "emoji": info["emoji"], "color": info["color"],
        })
    return {"people": people}


@router.post("/class/profile")
async def class_profile(request: Request):
    """Lets a family customize who's actually behind a chip — a real name,
    a level (kid/teen/adult/expert), an optional free-text note (e.g. "PhD
    in physics"), and optionally a linked enrolled face name (see
    /enroll_face, /known_people in assistant_server.py) — so /class/start
    and /class/answer can pitch the lesson and follow-up questions at the
    right depth instead of treating every learner the same, and so the
    tablet's Watch Mode face-ID can auto-select the right person chip
    (see checkForFace() in the JS below) instead of always requiring a
    manual tap. Stored in the same per-family JSON family_profiles.py
    already uses; no schema change needed there."""
    body      = await request.json()
    family_id = body.get("family_id")
    if not family_id:
        return {"error": "family_id required"}

    level = (body.get("level") or "kid").strip().lower()
    if level not in LEARNER_LEVELS:
        level = "kid"
    name      = (body.get("name") or "").strip()[:40]
    face_name = (body.get("face_name") or "").strip()[:40]
    note = (body.get("note") or "").strip()[:80]

    stats = load_family_stats(family_id)
    if name:
        stats["learner_name"] = name
    stats["learner_level"] = level
    stats["learner_note"]  = note
    if "face_name" in body:  # let a user explicitly clear the link by sending ""
        stats["linked_face_name"] = face_name
    save_family_stats(stats, family_id)
    return {"ok": True, "family_id": family_id, "name": stats.get("learner_name"), "level": level,
            "note": note, "linked_face_name": stats.get("linked_face_name", "")}


@router.get("/class/preview")
async def class_preview(family_id: str):
    stats  = load_family_stats(family_id)
    lesson = next_lesson(stats.get("lessons_completed", []))
    if not lesson:
        return {"done": True, "track": "🎉 DONE", "title": "All lessons complete!",
                "desc": "Every lesson in the curriculum is finished — come back anytime to review."}
    return {
        "done": False, "lesson_key": lesson["lesson_key"], "track": lesson["track"],
        "title": lesson["title"],
        "desc": f"Level {lesson['index_in_track'] + 1} · {lesson['age']} · +{lesson['xp']} XP",
        "xp": lesson["xp"],
    }


@router.post("/class/start")
async def class_start(request: Request):
    """Resumes an in-progress lesson if one exists for this person (see
    "in_progress" in family_profiles.py's stats — set/cleared by
    /class/answer), otherwise picks the next not-yet-completed lesson and
    has Ollama open it like a real teacher: warm intro + one comprehension
    question, then stops and waits for the answer via /class/answer.
    "Go to class" auto-resuming mid-conversation (rather than always
    starting a fresh lesson) is what makes this safe to call repeatedly —
    a dropped connection, a reloaded tab, or the tablet being shared by
    another family member and coming back to you doesn't lose progress."""
    body      = await request.json()
    family_id = body.get("family_id")
    history   = body.get("history") or []
    if not family_id:
        return {"error": "family_id required"}

    person = FAMILY_REGISTRY.get(family_id, {})
    stats  = load_family_stats(family_id)
    name   = stats.get("learner_name") or person.get("kid_name", "the student")
    level  = _level_instruction(stats.get("learner_level", "kid"), stats.get("learner_note", ""))

    in_progress = stats.get("in_progress") or {}
    resume_lesson = get_lesson(in_progress.get("lesson_key", "")) if in_progress.get("lesson_key") else None

    if resume_lesson:
        good_turns = in_progress.get("good_turns", 0)
        opener = (
            f"{name} ({level}) is coming back to class — you were partway through "
            f"\"{resume_lesson['title']}\" ({good_turns}/{GOOD_TURNS_TO_COMPLETE} good answers so "
            f"far). Welcome them back warmly in 1 sentence, briefly remind them what you were "
            f"just discussing, then ask ONE follow-up question that continues that SAME topic - "
            f"don't start the lesson over from scratch."
        )
        data  = await _ollama_chat(opener, history, speaker=name)
        reply = data.get("reply") or data.get("error") or "Sorry, I couldn't reach the classroom right now."
        update_streak(family_id)
        return {
            "done": False, "resumed": True, "lesson_key": resume_lesson["lesson_key"],
            "track": resume_lesson["track"], "title": resume_lesson["title"], "xp": resume_lesson["xp"],
            "good_turns": good_turns, "turns_required": GOOD_TURNS_TO_COMPLETE,
            "opener_prompt": opener, "teacher_reply": reply,
        }

    lesson = next_lesson(stats.get("lessons_completed", []))
    if not lesson:
        return {"done": True, "message": f"{name} already finished every lesson in the "
                "curriculum! 🎉 Ask Aubie anything else, or check back once a new track is added."}

    opener = (
        f"Let's start today's class with {name}, who is {level}. Topic: \"{lesson['title']}\" "
        f"(track: {lesson['track']}, level {lesson['index_in_track'] + 1}). "
        f"Introduce the topic warmly in 2-4 sentences, pitched at {name}'s level above - not a "
        f"lecture dump - then ask exactly one specific comprehension question about "
        f"\"{lesson['title']}\" that actually checks understanding at that level, and stop there "
        f"so {name} can answer before you say anything else."
    )
    data  = await _ollama_chat(opener, history, speaker=name)
    reply = data.get("reply") or data.get("error") or "Sorry, I couldn't reach the classroom right now."
    update_streak(family_id)

    stats["in_progress"] = {"lesson_key": lesson["lesson_key"], "good_turns": 0,
                             "updated_at": datetime.datetime.now().isoformat()}
    save_family_stats(stats, family_id)

    return {
        "done": False, "resumed": False, "lesson_key": lesson["lesson_key"], "track": lesson["track"],
        "title": lesson["title"], "xp": lesson["xp"], "good_turns": 0, "turns_required": GOOD_TURNS_TO_COMPLETE,
        "opener_prompt": opener, "teacher_reply": reply,
    }


@router.post("/class/answer")
async def class_answer(request: Request):
    """Scores a student's answer, gives real feedback pitched at their
    level, and always asks one more follow-up question in the same reply
    so it stays a conversation instead of a one-shot quiz. A lesson is
    marked complete (XP awarded, family_profiles.py updated) only once
    GOOD_TURNS_TO_COMPLETE answers in that lesson have passed — the first
    good answer keeps the same lesson_key open for one more round."""
    body       = await request.json()
    family_id  = body.get("family_id")
    lesson_key = body.get("lesson_key")
    answer     = (body.get("answer") or "").strip()
    history    = body.get("history") or []
    if not family_id or not lesson_key or not answer:
        return {"error": "family_id, lesson_key and answer are required"}

    lesson = get_lesson(lesson_key)
    if not lesson:
        return {"error": f"Unknown lesson_key: {lesson_key}"}

    person = FAMILY_REGISTRY.get(family_id, {})
    stats  = load_family_stats(family_id)
    name   = stats.get("learner_name") or person.get("kid_name", "the student")
    level  = _level_instruction(stats.get("learner_level", "kid"), stats.get("learner_note", ""))

    # Server is authoritative for the turn count (not the client) so a
    # dropped connection/reload can't desync it — it's exactly the same
    # "in_progress" state /class/start reads to resume a lesson.
    in_progress = stats.get("in_progress") or {}
    good_turns_before = in_progress.get("good_turns", 0) if in_progress.get("lesson_key") == lesson_key else 0

    prompt = (
        f"{name} ({level}) just answered a comprehension question about \"{lesson['title']}\" "
        f"({lesson['track']}) with: \"{answer}\"\n\n"
        f"Respond as an engaged teacher, pitched at {name}'s level above: 2-4 sentences of real "
        f"feedback on this specific answer (praise what's right, gently correct what's off, add "
        f"one detail they might have missed - go deeper and more technical for an expert, simpler "
        f"and more encouraging for a kid). Then ask exactly ONE natural follow-up question, also "
        f"at {name}'s level, that keeps the conversation and learning going - either deepening this "
        f"same idea or a related angle. Finally, on its own final line, write exactly:\nSCORE: X.XX\n"
        f"where X.XX is 0.00-1.00 for how well THIS answer shows real understanding "
        f"(0.75+ = solid understanding, below 0.40 = didn't really get it yet)."
    )
    data  = await _ollama_chat(prompt, history, speaker=name)
    reply = data.get("reply") or ""

    score    = None
    feedback = reply
    m = re.search(r"SCORE:\s*([01](?:\.\d+)?)", reply, re.IGNORECASE)
    if m:
        score    = max(0.0, min(1.0, float(m.group(1))))
        feedback = reply[:m.start()].strip() or reply
    if score is None:
        # Ollama unreachable or didn't follow the score format — fall back to
        # a simple heuristic (same spirit as app.py's local fallback scoring)
        # rather than silently blocking XP/lesson progress.
        words  = answer.split()
        qwords = ["because", "therefore", "since", "for example", "which means", "so that", "in other words"]
        bonus  = sum(0.05 for w in qwords if w in answer.lower())
        score  = round(min(1.0, 0.35 + len(words) * 0.02 + bonus), 2)
        if not feedback:
            feedback = f"Nice try, {name}! Let's keep building on that — what else comes to mind?"

    passed_turn      = score >= 0.5
    good_turns_after = good_turns_before + (1 if passed_turn else 0)
    lesson_complete  = good_turns_after >= GOOD_TURNS_TO_COMPLETE

    xp_awarded     = 0
    next_available = True

    if lesson_complete:
        stats.pop("in_progress", None)  # resumed lessons stop resuming once actually finished
        if lesson_key not in stats.get("lessons_completed", []):
            stats.setdefault("lessons_completed", []).append(lesson_key)
            xp_awarded         = lesson["xp"]
            stats["total_xp"]  = stats.get("total_xp", 0) + xp_awarded
            stats["level"]     = max(1, stats["total_xp"] // 100 + 1)
            stats.setdefault("coherence_history", []).append(score)
            stats["coherence_history"] = stats["coherence_history"][-50:]
            stats.setdefault("weekly_log", []).append(
                {"date": datetime.date.today().isoformat(), "xp": xp_awarded, "lesson_key": lesson_key}
            )
            stats["weekly_log"] = stats["weekly_log"][-200:]
        next_available = next_lesson(stats.get("lessons_completed", [])) is not None
    else:
        stats["in_progress"] = {"lesson_key": lesson_key, "good_turns": good_turns_after,
                                 "updated_at": datetime.datetime.now().isoformat()}
    save_family_stats(stats, family_id)

    return {
        "feedback": feedback, "score": score, "passed_turn": passed_turn,
        "good_turns": good_turns_after, "turns_required": GOOD_TURNS_TO_COMPLETE,
        "lesson_complete": lesson_complete,
        "xp_awarded": xp_awarded, "title": lesson["title"],
        "lesson_key": lesson_key, "next_available": next_available,
    }


@router.get("/class/progress")
async def class_progress(family_id: str):
    stats     = load_family_stats(family_id)
    completed = stats.get("lessons_completed", [])
    week_ago  = _week_ago_iso()
    weekly_xp = sum(
        e.get("xp", 0) for e in stats.get("weekly_log", [])
        if e.get("date", "") >= week_ago
    )
    return {
        "family_id": family_id,
        "streak_days": stats.get("streak_days", 0),
        "total_xp": stats.get("total_xp", 0),
        "level": stats.get("level", 1),
        "lessons_done": len(completed),
        "lessons_total": total_lessons(),
        "weekly_xp": weekly_xp,
        "tracks": track_progress(completed),
    }
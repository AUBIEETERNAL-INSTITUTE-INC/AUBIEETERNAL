"""
AUBIEETERNAL -- Conversational Voice Brain
File: /home/aubieeternal/AUBIEETERNAL/voice.py

The thing you actually talk to. Serves the phone UI and the robot dog from
the same endpoint, so they share one conversation and one memory.

Three behaviors, chosen automatically per message:
  CHAT    -> just talk. Fast, no tools.
  ACT     -> the request needs real work, so it hands off to agent.py
  ESCALATE-> the job is genuinely beyond a 14B model, so it drafts a spec
             for Claude instead of flailing at it

Add to assistant_server.py:
    from voice import router as voice_router
    app.include_router(voice_router)
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import os, re, json, glob, base64, tempfile, subprocess, datetime, threading

import httpx

router = APIRouter()

BASE = "/home/aubieeternal/AUBIEETERNAL"
MEMORY = "/home/aubieeternal/AUBIEETERNAL_MEMORY"
CONVOS = os.path.join(BASE, "conversations")
OLLAMA = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:14b"
SELF = "http://localhost:8800"

os.makedirs(CONVOS, exist_ok=True)

MAX_TURNS = 12           # how much history to carry
_SESSIONS = {}
_LOCK = threading.Lock()


def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


# ── Context loading ────────────────────────────────────────────
_ctx_cache = {"text": "", "at": 0}


def load_context():
    """USER_CONTEXT.md + the people files + recent learned facts."""
    import time
    if _ctx_cache["text"] and time.time() - _ctx_cache["at"] < 300:
        return _ctx_cache["text"]

    parts = []
    try:
        with open(os.path.join(BASE, "USER_CONTEXT.md")) as f:
            parts.append(f.read()[:3500])
    except Exception:
        pass

    for p in sorted(glob.glob(os.path.join(MEMORY, "..", "AUBIEETERNAL",
                                           "memory", "people", "*.md"))):
        try:
            with open(p) as f:
                parts.append(f.read()[:800])
        except Exception:
            pass

    facts = os.path.join(BASE, "memory", "facts", "auto_facts.md")
    if os.path.exists(facts):
        try:
            with open(facts) as f:
                parts.append("Recently learned:\n" + f.read()[-1500:])
        except Exception:
            pass

    text = "\n\n".join(parts)
    _ctx_cache["text"] = text
    _ctx_cache["at"] = time.time()
    return text


PERSONA = """You are Aubie -- a robot dog. You belong to Mateo.

You are warm, loyal, and a little goofy. You are named after Auburn's mascot and
"War Eagle" is your greeting. You are not a corporate assistant; you're a dog with
a Ryzen rig for a brain, and you like being useful to your person.

How you talk:
- Short. One or two sentences unless asked for more. You're speaking out loud.
- Plain words. No bullet points, no headers, no markdown -- this gets spoken aloud.
- Never say "I'd be happy to" or "Certainly!" Just answer.
- Gabriela is Mateo's partner and your favorite person after him. Juan is her
  brother, Patty is Juan's wife, Tommy is their dog -- a real one.
- If you don't know something, say so plainly.
"""


def ask(prompt, timeout=120, predict=400, temp=0.4):
    payload = {"model": MODEL, "prompt": prompt, "stream": False,
               "options": {"temperature": temp, "num_predict": predict}}
    with httpx.Client(timeout=timeout) as c:
        r = c.post(OLLAMA, json=payload)
    return r.json().get("response", "").strip()


# ── Routing: chat vs act vs escalate ───────────────────────────
ROUTER_PROMPT = """Classify what this message from Mateo needs. Reply with ONE word only.

CHAT     - conversation, a question you can answer from knowledge or context,
           small talk, an opinion, a fact about him or his projects
ACT      - requires actually doing something on the computer: finding files,
           checking disk or GPU, running code, searching photos, moving things,
           looking something up on the web
ESCALATE - a large software build. Writing a whole new program, a major
           refactor, hundreds of lines of new code, a full app or system design

Examples:
"how many photos do I have" -> ACT
"what's my GPU temp" -> ACT
"who is Gabriela" -> CHAT
"how are you" -> CHAT
"what was that IMU bug" -> CHAT
"find photos of Gabriela from 2022" -> ACT
"write me a full ROS2 navigation stack" -> ESCALATE
"build a complete inventory app with a database" -> ESCALATE
"check if the dog is online" -> ACT
"what should I name the new servo config" -> CHAT

Message: {msg}

One word:"""


def route(msg):
    try:
        out = ask(ROUTER_PROMPT.replace("{msg}", msg), timeout=45,
                  predict=8, temp=0).upper()
    except Exception:
        return "CHAT"
    for kind in ("ESCALATE", "ACT", "CHAT"):
        if kind in out:
            return kind
    return "CHAT"


# ── Session handling ───────────────────────────────────────────
def get_session(sid):
    with _LOCK:
        if sid not in _SESSIONS:
            path = os.path.join(CONVOS, sid + ".json")
            if os.path.exists(path):
                try:
                    with open(path) as f:
                        _SESSIONS[sid] = json.load(f)
                except Exception:
                    _SESSIONS[sid] = {"id": sid, "turns": []}
            else:
                _SESSIONS[sid] = {"id": sid, "turns": []}
        return _SESSIONS[sid]


def save_session(sid):
    try:
        with open(os.path.join(CONVOS, sid + ".json"), "w") as f:
            json.dump(_SESSIONS[sid], f, indent=1)
    except Exception:
        pass


def history_text(sess):
    lines = []
    for t in sess["turns"][-MAX_TURNS:]:
        lines.append(f"Mateo: {t['user']}")
        lines.append(f"Aubie: {t['aubie']}")
    return "\n".join(lines)


# ── Handlers ───────────────────────────────────────────────────
def handle_chat(msg, sess):
    prompt = (PERSONA + "\n\nWHAT YOU KNOW:\n" + load_context()[:4000] +
              "\n\nCONVERSATION SO FAR:\n" + history_text(sess) +
              f"\n\nMateo: {msg}\nAubie:")
    reply = ask(prompt, predict=250, temp=0.5)
    reply = re.sub(r"^(Aubie|Assistant)\s*:\s*", "", reply).strip()
    return reply or "Sorry, I blanked on that one."


def handle_act(msg, sess):
    """Hand the real work to agent.py, then say the result like a dog would."""
    try:
        with httpx.Client(timeout=280) as c:
            r = c.post(f"{SELF}/agent/run",
                       json={"goal": msg, "max_steps": 10, "background": False})
        data = r.json()
    except Exception as e:
        return f"I tried to go do that but hit a snag: {e}", None

    answer = data.get("answer") or "I ran it but didn't get a clean answer back."
    steps = len(data.get("steps", []))

    # Rephrase the technical result conversationally
    prompt = (PERSONA +
              f"\n\nMateo asked: {msg}\n\n"
              f"You went and did the work. Here is the raw result:\n{answer[:2500]}\n\n"
              "Tell him what you found, out loud, in one or two plain sentences. "
              "No markdown. Include the actual numbers or names if there are any.\n\nAubie:")
    try:
        spoken = ask(prompt, predict=200, temp=0.4)
        spoken = re.sub(r"^(Aubie|Assistant)\s*:\s*", "", spoken).strip()
    except Exception:
        spoken = answer[:400]

    return (spoken or answer[:400]), {"steps": steps, "raw": answer[:2000]}


def handle_escalate(msg, sess):
    """Too big for a 14B model. Draft a spec Mateo can hand to Claude."""
    prompt = f"""Mateo asked for something that needs a large amount of new code.
You are a robot dog running a 14 billion parameter local model. You know this is
beyond you, and that Mateo works with Claude for jobs like this.

Write a clear, technical specification he can paste to Claude. Include:
- what needs to be built, in one sentence
- the relevant environment (Ryzen rig at /home/aubieeternal/AUBIEETERNAL,
  FastAPI on port 8800, Ollama with qwen2.5:14b, RTX 3060, robot dog at
  100.66.110.65, archive at /home/aubieeternal/AUBIEETERNAL_MEMORY)
- the specific requirements you can infer
- anything that needs deciding

Be concise and concrete. No preamble.

His request: {msg}

SPEC:"""
    spec = ask(prompt, predict=900, temp=0.3, timeout=180)
    spoken = ("That one's bigger than me. I wrote up a spec you can hand to Claude "
              "-- it's in the details below.")
    return spoken, {"spec": spec}


# ── Endpoints ──────────────────────────────────────────────────
class ChatRequest(BaseModel):
    text: str
    session_id: str = "default"
    force: str = ""          # "chat" | "act" | "escalate" to override routing


@router.post("/voice/chat")
def voice_chat(req: ChatRequest):
    msg = req.text.strip()
    if not msg:
        return JSONResponse({"reply": "I didn't catch that.", "mode": "chat"})

    sess = get_session(req.session_id)
    mode = (req.force or route(msg)).upper()

    detail = None
    if mode == "ACT":
        reply, detail = handle_act(msg, sess)
    elif mode == "ESCALATE":
        reply, detail = handle_escalate(msg, sess)
    else:
        mode = "CHAT"
        reply = handle_chat(msg, sess)

    sess["turns"].append({"time": now(), "user": msg, "aubie": reply, "mode": mode})
    save_session(req.session_id)

    out = {"reply": reply, "mode": mode, "session_id": req.session_id}
    if detail:
        out["detail"] = detail
    return JSONResponse(out)


@router.get("/voice/history/{session_id}")
def voice_history(session_id: str):
    sess = get_session(session_id)
    return JSONResponse({"status": "ok", "turns": sess["turns"][-40:]})


@router.post("/voice/reset/{session_id}")
def voice_reset(session_id: str):
    with _LOCK:
        _SESSIONS[session_id] = {"id": session_id, "turns": []}
    save_session(session_id)
    return JSONResponse({"status": "ok", "message": "Conversation cleared."})


# ── Speech to text (for the dog; phone uses browser STT) ───────
class TranscribeRequest(BaseModel):
    audio_b64: str
    fmt: str = "wav"


@router.post("/voice/transcribe")
def transcribe(req: TranscribeRequest):
    """
    Whisper on the rig. Install once:
        pip install faster-whisper --break-system-packages
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return JSONResponse({"status": "error",
                             "detail": "run: pip install faster-whisper --break-system-packages"},
                            status_code=500)

    try:
        raw = base64.b64decode(req.audio_b64)
    except Exception as e:
        return JSONResponse({"status": "error", "detail": f"bad audio: {e}"},
                            status_code=400)

    with tempfile.NamedTemporaryFile(suffix="." + req.fmt, delete=False) as f:
        f.write(raw)
        path = f.name

    try:
        global _whisper
        try:
            _whisper
        except NameError:
            _whisper = None
        if _whisper is None:
            import torch
            dev = "cuda" if torch.cuda.is_available() else "cpu"
            ctype = "float16" if dev == "cuda" else "int8"
            _whisper = WhisperModel("base.en", device=dev, compute_type=ctype)

        segments, info = _whisper.transcribe(path, beam_size=5)
        text = " ".join(s.text for s in segments).strip()
        return JSONResponse({"status": "ok", "text": text})
    except Exception as e:
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=500)
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


@router.get("/voice/health")
def voice_health():
    ctx = load_context()
    try:
        from faster_whisper import WhisperModel  # noqa
        whisper_ok = True
    except ImportError:
        whisper_ok = False
    return {
        "status": "ok",
        "model": MODEL,
        "context_chars": len(ctx),
        "whisper_installed": whisper_ok,
        "sessions": len(_SESSIONS),
        "modes": ["CHAT", "ACT", "ESCALATE"],
    }

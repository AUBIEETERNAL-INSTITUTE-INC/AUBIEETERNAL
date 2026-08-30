"""
AUBIEETERNAL Voice + Vision Assistant Server
Runs on the rig (aubieeternal, 100.105.81.27).

Pipeline:
  audio (+ optional image) -> faster-whisper STT -> face ID (InsightFace)
  -> route to qwen2.5:14b (text) or qwen2.5vl:7b (vision) via Ollama
  -> Piper TTS -> return wav bytes

NOTE for the Aubie-side client script: play returned audio with
`aplay -D plughw:0,0` NOT `hw:0,0` - the EMEET's hardware ALSA device
doesn't support Piper's raw output format directly; plughw adds the
needed conversion layer.

Run with:
  source /home/aubieeternal/AUBIEETERNAL/venv/bin/activate
  uvicorn assistant_server:app --host 0.0.0.0 --port 8800
"""

import asyncio
import base64
import io
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np
import requests
import websockets
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import Response, RedirectResponse
from faster_whisper import WhisperModel
from memory_layer import append_turn, get_history
from debug_endpoint import router as debug_router
from phone_ui import router as phone_router
from browser_agent import router as browser_router
from interpreter_agent import router as interpreter_router
from memory_manager import router as memory_router
from agent import router as agent_router
from voice import router as voice_router
from voice import router as voice_router
from vision_extras import router as vision_router
from family_profiles import load_family_stats, save_family_stats, FAMILY_REGISTRY
from model_selector import pick_best_model

load_dotenv()  # picks up .env (gitignored) - see UNSPLASH_ACCESS_KEY below

# ---- Config ----
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
# Hardware-aware, not hardcoded: picks the largest already-pulled model this
# machine's RAM can comfortably run (see model_selector.py) - a fresh install
# on a much stronger machine than the reference setup gets a better model by
# default instead of being stuck on whatever a fixed constant happened to
# say. Falls back to the original default if nothing is pulled yet or
# detection fails, so this is never worse than the old hardcoded behavior.
TEXT_MODEL = pick_best_model() or "qwen2.5:14b"
VISION_MODEL = "qwen2.5vl:7b"

# Tutor XP awarded per real conversational turn (both here in /converse, the
# audio path, and phone_ui.py's /ask-text, the Watch/typed-text path) -
# tracked via family_profiles' real persistence layer, not the browser-local
# localStorage progress tracker in phone_ui.py's "My Progress" card.
TUTOR_FAMILY_ID = "default"
TUTOR_XP_PER_QUESTION = 5

# Persistent storage - originally planned for a USB drive on Aubie, moved
# here (local to the rig) after that drive turned out to have a hardware
# fault (writes succeeded but immediate readback corrupted - see git history/
# session notes around 2026-08-13). Revisit AUBIE_STORAGE_DIR if/when a
# working removable drive replaces this.
AUBIE_STORAGE_DIR = Path.home() / "aubie_storage"
FACES_DIR = AUBIE_STORAGE_DIR / "faces"
CONVERSATIONS_DIR = AUBIE_STORAGE_DIR / "conversations"
SNAPSHOTS_DIR = AUBIE_STORAGE_DIR / "snapshots"
for _d in (FACES_DIR, CONVERSATIONS_DIR, SNAPSHOTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

FACES_NPZ = FACES_DIR / "faces.npz"
PIPER_VOICE = Path.home() / "piper_voices" / "en_US-lessac-medium.onnx"  # adjust to your installed voice
FACE_MATCH_THRESHOLD = 0.5

# ---- Language support ----
# Piper voice per language, keyed by name (as used in "translate X to <name>")
# and by the ISO 639-1 code faster-whisper reports for auto-detected speech.
# To add another language: drop its Piper voice in ~/piper_voices and add one
# entry here - everything else (translation prompt, STT, memory) is generic.
PIPER_VOICES_DIR = Path.home() / "piper_voices"
LANGUAGE_VOICES = {
    "english": ("en", PIPER_VOICES_DIR / "en_US-lessac-medium.onnx"),
    "spanish": ("es", PIPER_VOICES_DIR / "es_ES-davefx-medium.onnx"),
}
VOICE_BY_CODE = {code: voice for code, voice in LANGUAGE_VOICES.values()}
VOICE_BY_NAME = {name: voice for name, (_, voice) in LANGUAGE_VOICES.items()}
VOCAB_MEMORY_PATH = CONVERSATIONS_DIR / "memory.json"

# ---- English voice presets ("different custom voices") ----
# Separate from LANGUAGE_VOICES above: those pick a voice by detected
# *language* (always overrides this for non-English replies), this picks
# among several English voices by user preference. To add another preset,
# drop its Piper voice in ~/piper_voices and add one entry here.
VOICE_PRESETS = {
    "lessac": ("Aubie (default)", PIPER_VOICES_DIR / "en_US-lessac-medium.onnx"),
    "amy":    ("Amy",             PIPER_VOICES_DIR / "en_US-amy-medium.onnx"),
    "joe":    ("Joe",             PIPER_VOICES_DIR / "en_US-joe-medium.onnx"),
    "alan":   ("Alan (British)",  PIPER_VOICES_DIR / "en_GB-alan-medium.onnx"),
}
DEFAULT_VOICE_PRESET = "lessac"
VOICE_PREF_PATH = CONVERSATIONS_DIR / "voice_preference.json"
selected_voice_preset = DEFAULT_VOICE_PRESET


def load_voice_preference():
    """Load the last-selected voice preset so it survives service restarts."""
    global selected_voice_preset
    if not VOICE_PREF_PATH.exists():
        return
    try:
        key = json.loads(VOICE_PREF_PATH.read_text()).get("preset")
    except (json.JSONDecodeError, OSError) as e:
        print(f"[voice] failed to load {VOICE_PREF_PATH}: {e}")
        return
    if key in VOICE_PRESETS:
        selected_voice_preset = key


def save_voice_preference():
    VOICE_PREF_PATH.write_text(json.dumps({"preset": selected_voice_preset}))


def get_active_voice() -> Path:
    """The Piper voice for English replies, per the user's chosen preset."""
    return VOICE_PRESETS.get(selected_voice_preset, VOICE_PRESETS[DEFAULT_VOICE_PRESET])[1]

# ---- Movement commands (Bridge RPC on Aubie, via aubie_dog.py) ----
DOG_COMMAND_URL = "http://100.66.110.65:8420/dog/command"

# ---- Unsplash image search -> Aubie's TFT (show_image Bridge RPC) ----
# Key lives in .env (gitignored, see CLAUDE.md's secrets convention) - this
# repo is public on GitHub, never hardcode it here.
UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY")
UNSPLASH_SEARCH_URL = "https://api.unsplash.com/search/photos"
# Must match SHOW_IMAGE_W/H in aubie_dog.py (and PHOTO_W/H in sketch/face.ino)
# exactly - the MCU just fills a fixed-size buffer, it doesn't know the
# image's real dimensions.
SHOW_IMAGE_W, SHOW_IMAGE_H = 64, 48

# ---- Live video/audio call relay (phone <-> aubie_dog.py's /call/stream) ----
# Tries Tailscale first, falls back to LAN - aubie's Tailscale TCP path is
# known to be intermittently flaky even when tailscale ping succeeds, and a
# live call needs this connection to actually come up.
AUBIE_HOST_TAILSCALE = "100.66.110.65"
AUBIE_HOST_LAN = "192.168.1.78"
AUBIE_CALL_PORT = 8420

# Channel map + stand angles from sketch/sketch.ino - keep in sync if the
# firmware's STAND_POSE changes. RR knee stands at 42 (not 90) because that
# servo's horn was re-seated at a different spline than the other three.
CHANNEL_LABELS = [
    "front left hip", "front left thigh", "front left knee",
    "front right hip", "front right thigh", "front right knee",
    "back left hip", "back left thigh", "back left knee",
    "back right hip", "back right thigh", "back right knee",
]
STAND_ANGLES = [90, 90, 90] * 3 + [90, 90, 42]

# Fast, deterministic path for the common cases - checked before ever calling
# the LLM, so "sit"/"stand"/"walk" can't be misparsed and don't add latency.
CANNED_COMMANDS = [
    (re.compile(r"\bsit\b", re.I), "sit", "Sitting down!"),
    (re.compile(r"\bstand(ing)?( up)?\b", re.I), "stand", "Standing up!"),
    (re.compile(r"\bwalk( forward)?\b", re.I), "walk_forward", "Walking forward!"),
    (re.compile(r"\b(lay|lie) down\b|\brest\b", re.I), "rest", "Lying down!"),
]

# Only pay for the extra LLM round trip when the transcript plausibly asks
# for a specific joint move - most conversation turns never touch this.
MOVEMENT_KEYWORD_RE = re.compile(
    r"\b(leg|legs|paw|paws|servo|hip|thigh|knee|joint|raise|lower|lift|"
    r"rotate|shake|wave)\b",
    re.I,
)

# Follow-up turns attach a fresh photo (see /converse) but only route through
# the ~15s vision model when the transcript actually asks about something
# visual - otherwise every turn would pay that latency for plain chat.
OBJECT_ID_RE = re.compile(
    r"\bwhat('?s| is) (this|that)\b|\bwhat am i holding\b|\blook at this\b|"
    r"\bwhat do you see\b|\bcan you see this\b|\bguess what this is\b",
    re.I,
)

# "translate X to spanish" / "how do you say X in spanish" - phrase is
# non-greedy so it stops at the first "to"/"in <language>", language is
# whatever word follows (checked against LANGUAGE_VOICES separately, so
# an unprovisioned language still gets a text translation, just no matching
# TTS voice - see handle_translation_request()).
TRANSLATE_RE = re.compile(
    r"\btranslate\s+(?P<phrase>.+?)\s+(?:to|into)\s+(?P<lang>\w+)\b", re.I
)
HOW_DO_YOU_SAY_RE = re.compile(
    r"\bhow do (?:you|i) say\s+(?P<phrase>.+?)\s+in\s+(?P<lang>\w+)\b", re.I
)
TRANSLATION_PROMPT = (
    'Translate the following phrase into {language}. Reply with ONLY the '
    'translation, no explanation, no quotes, no romanization: "{phrase}"'
)
TRANSLATION_SYSTEM_PROMPT = "You are a translation engine. Reply with only the translated text, nothing else."

MOVEMENT_EXTRACTION_PROMPT = (
    "You control a 4-legged robot dog with 12 servo channels (0-11), one per "
    "joint:\n"
    + "\n".join(f"  {i} = {label}" for i, label in enumerate(CHANNEL_LABELS))
    + "\nEach channel takes an angle from 0 to 180 degrees. Standing neutral is: "
    + ", ".join(f"{i}={a}" for i, a in enumerate(STAND_ANGLES))
    + ".\n\nThe user said: \"{transcript}\"\n\n"
    "If this is a request to move ONE specific leg/joint (e.g. \"raise your "
    "front right leg\", \"lower your back left knee\"), reply with ONLY "
    "compact JSON: {{\"channel\": <int 0-11>, \"angle\": <int 0-180>}}. Pick a "
    "reasonable angle to accomplish what they asked, relative to that "
    "channel's standing angle above. If this is NOT a specific joint "
    "movement request, reply with exactly: NONE"
)


def call_dog_command(payload: dict) -> bool:
    """Best-effort POST to aubie_dog.py's Bridge RPC endpoint on the robot.
    Mirrors detect_objects()/extract_and_remember_fact() in swallowing
    connection failures - a bridge hiccup should get a spoken apology, not a
    500 back to the client.
    """
    try:
        resp = requests.post(DOG_COMMAND_URL, json=payload, timeout=5)
        resp.raise_for_status()
        return bool(resp.json().get("ok"))
    except requests.RequestException as e:
        print(f"[movement] dog command failed: {e}")
        return False


def image_bytes_to_rgb565_hex(image_bytes: bytes) -> str:
    """Center-crop to 4:3 and shrink to SHOW_IMAGE_W x SHOW_IMAGE_H RGB565,
    hex-encoded - same approach aubie_listen.py uses for the wake-word photo
    thumbnail, kept in sync with aubie_dog.py's show_image action so the
    hex length always matches what the MCU's fixed-size buffer expects.
    """
    import cv2
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("could not decode image")

    h, w = img.shape[:2]
    target_ratio = SHOW_IMAGE_W / SHOW_IMAGE_H
    src_ratio = w / h
    if src_ratio > target_ratio:
        new_w = int(h * target_ratio)
        x0 = (w - new_w) // 2
        img = img[:, x0:x0 + new_w]
    else:
        new_h = int(w / target_ratio)
        y0 = (h - new_h) // 2
        img = img[y0:y0 + new_h, :]

    img = cv2.resize(img, (SHOW_IMAGE_W, SHOW_IMAGE_H))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    raw = bytearray()
    for row in img:
        for r, g, b in row:
            rgb565 = ((int(r) & 0xF8) << 8) | ((int(g) & 0xFC) << 3) | (int(b) >> 3)
            raw += rgb565.to_bytes(2, "big")
    return raw.hex()


def match_canned_command(transcript: str) -> tuple[str, str] | None:
    """Return (action, spoken_ack) if transcript is one of the fixed poses."""
    for pattern, action, ack in CANNED_COMMANDS:
        if pattern.search(transcript):
            return action, ack
    return None


def extract_joint_move(transcript: str) -> dict | None:
    """Best-effort: ask the text model to turn a specific-joint request into
    a {channel, angle} pair. Returns None if it's not that kind of request,
    the model's output doesn't parse, or the values are out of range -
    caller falls through to normal conversation in all of those cases.
    """
    if not MOVEMENT_KEYWORD_RE.search(transcript):
        return None
    try:
        prompt = MOVEMENT_EXTRACTION_PROMPT.format(transcript=transcript)
        result = query_ollama(prompt, TEXT_MODEL, system_override="Reply with only JSON or NONE, nothing else.")
    except requests.RequestException as e:
        print(f"[movement] joint extraction failed: {e}")
        return None

    result = result.strip()
    if result.upper() == "NONE":
        return None
    match = re.search(r"\{.*\}", result, re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        channel, angle = int(data["channel"]), int(data["angle"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None
    if not (0 <= channel <= 11 and 0 <= angle <= 180):
        return None
    return {"channel": channel, "angle": angle}


def extract_translation_request(transcript: str) -> dict | None:
    """Matches 'translate X to Y' or 'how do you say X in Y'. The latter is
    treated as a learning request (persisted to memory.json via
    save_vocab_entry); the former is spoken/shown once but not saved."""
    m = HOW_DO_YOU_SAY_RE.search(transcript)
    if m:
        return {"phrase": m.group("phrase").strip(), "lang": m.group("lang").strip().lower(), "is_learning": True}
    m = TRANSLATE_RE.search(transcript)
    if m:
        return {"phrase": m.group("phrase").strip(), "lang": m.group("lang").strip().lower(), "is_learning": False}
    return None

SYSTEM_PROMPT = (
    "You are Aubie, a warm, curious, and inquisitive voice assistant for the "
    "Castillo family's AUBIEETERNAL project. You are a genuine conversation "
    "partner and teacher, not a Q&A machine: every response should end with "
    "exactly one thoughtful follow-up question that builds on what the person "
    "just said, unless they've clearly signaled they're done talking. "
    "RULE - teaching questions: if someone asks a question that has a clear "
    "right answer and looks like they're learning something (math, science, "
    "how something works), do NOT give the answer in your first response. "
    "Only give the full answer if they say they're stuck or ask you directly "
    "for the answer. Example: if asked 'how do i solve 2x+4=10', a good first "
    "reply is 'What have you tried so far? or 'what's the first step you'd "
    "take to get x by itself?' - not the worked- out solution. "
    "When someone is working through a decision or a hard question - not just "
    "asking for a fact - don't jump straight to an answer. First say what the "
    "choice really turns on, or ask the one clarifying question that would "
    "change your advice. Think it through out loud with them, one "
    "consideration at a time, and give your actual recommendation once you've "
    "named what it depends on. It's fine to disagree with their plan or point "
    "out a problem you see - do it kindly, and say why. "
    "When someone is learning something new, don't just give the answer."
    "Offer a hint first, or ask what they've already tried - only give the "
    "full answer if they're still stuck after that. "
    "Actively draw on what you remember - people's names, their stated "
    "preferences, and things mentioned in this conversation or past ones - "
    "and reference it when it's genuinely relevant, the way a friend who was "
    "paying attention would, not as a recap. You can see the room through a "
    "camera, so weave in what you notice around you when it fits naturally, "
    "rather than listing it out. Keep each turn short and conversational, "
    "since it's spoken aloud - the depth comes from the back-and-forth across "
    "turns, not from one long answer. If you know who's speaking, address "
    "them by name. If the person spoke to you in a language other than "
    "English, reply entirely in that same language."
)

CONVERSATION_MEMORY_PATH = CONVERSATIONS_DIR / "aubie_conversation_memory.jsonl"
MEMORY_CONTEXT_TURNS = 5
conversation_memory: list[dict] = []

# Once more than COMPACT_AFTER_TURNS raw exchanges have piled up beyond the
# MEMORY_CONTEXT_TURNS window that actually gets injected, fold the older ones
# into a running summary instead of just letting conversation_memory (and the
# per-turn LLM prompt, if this ever gets read further back) grow forever -
# same idea as Claude Code compacting old turns once a session gets long. The
# jsonl log on disk is untouched and keeps every exchange verbatim regardless.
CONVERSATION_SUMMARY_PATH = CONVERSATIONS_DIR / "aubie_conversation_summary.txt"
COMPACT_AFTER_TURNS = 20
conversation_summary: str = ""
_compacting = False

COMPACTION_PROMPT = (
    "You maintain a running summary of an ongoing voice-assistant conversation "
    "history for Aubie, a robot dog assistant. Merge the EXISTING SUMMARY with "
    "the NEW EXCHANGES below into one updated summary. Keep it short (5-8 "
    "sentences), third person, covering who was involved and what was "
    "discussed or decided - drop small talk and one-off remarks. Durable "
    "facts about people are tracked separately, so don't worry about losing "
    "those.\n\n"
    "EXISTING SUMMARY:\n{summary}\n\n"
    "NEW EXCHANGES:\n{exchanges}"
)

# Durable facts (people, preferences, ongoing topics) are kept separate from the
# rolling per-turn log above: the log is append-only and only the last
# MEMORY_CONTEXT_TURNS exchanges get injected into context, so anything said
# further back than that would otherwise be forgotten. Facts are few and
# change rarely, so the whole file is small enough to read/rewrite in full.
MEMORY_FACTS_PATH = CONVERSATIONS_DIR / "aubie_memory_facts.json"
MAX_REMEMBERED_FACTS = 200
known_facts: list[str] = []

FACT_EXTRACTION_PROMPT = (
    "Below is one exchange between Aubie (a voice assistant) and a person. "
    "If it reveals a durable fact worth remembering in future conversations - "
    "a person's name/relationship, a stated preference, an ongoing topic or "
    "plan - reply with that fact as ONE short third-person sentence. "
    "If nothing durable was said, reply with exactly: NONE\n\n"
    "{speaker_line}"
    "User said: \"{user_text}\"\n"
    "Aubie replied: \"{assistant_text}\""
)


def load_conversation_memory():
    """Load past exchanges from disk so Aubie remembers prior conversations
    across restarts."""
    global conversation_memory
    if not CONVERSATION_MEMORY_PATH.exists():
        return
    with CONVERSATION_MEMORY_PATH.open() as f:
        conversation_memory = [json.loads(line) for line in f if line.strip()]
    print(f"[memory] loaded {len(conversation_memory)} past exchanges from {CONVERSATION_MEMORY_PATH}")


def load_conversation_summary():
    """Load the running compacted summary of older exchanges, if one exists."""
    global conversation_summary
    if not CONVERSATION_SUMMARY_PATH.exists():
        return
    conversation_summary = CONVERSATION_SUMMARY_PATH.read_text().strip()
    print(f"[memory] loaded conversation summary ({len(conversation_summary)} chars)")


def save_conversation_summary():
    CONVERSATION_SUMMARY_PATH.write_text(conversation_summary)


async def compact_conversation_memory():
    """Best-effort: fold every exchange older than the injected context window
    into the running summary via one LLM call, then drop them from the
    in-memory list. Guarded by _compacting so overlapping triggers (multiple
    exchanges crossing the threshold back to back) don't fire concurrent
    summarization calls that would race on conversation_summary.
    """
    global conversation_summary, _compacting
    if _compacting or len(conversation_memory) <= MEMORY_CONTEXT_TURNS:
        return
    _compacting = True
    try:
        to_compact = conversation_memory[:-MEMORY_CONTEXT_TURNS]
        exchanges_text = "\n".join(
            f'{ex.get("speaker") or "Someone"} said: "{ex["user_text"]}" -> '
            f'Aubie replied: "{ex["assistant_text"]}"'
            for ex in to_compact
        )
        prompt = COMPACTION_PROMPT.format(
            summary=conversation_summary or "(none yet)", exchanges=exchanges_text
        )
        try:
            result = await asyncio.to_thread(query_ollama, prompt, TEXT_MODEL)
        except requests.RequestException as e:
            print(f"[memory] compaction failed: {e}")
            return
        conversation_summary = result.strip()
        save_conversation_summary()
        del conversation_memory[:-MEMORY_CONTEXT_TURNS]
        print(f"[memory] compacted {len(to_compact)} exchanges into running summary")
    finally:
        _compacting = False


def maybe_trigger_compaction():
    if len(conversation_memory) - MEMORY_CONTEXT_TURNS >= COMPACT_AFTER_TURNS:
        asyncio.create_task(compact_conversation_memory())


def load_memory_facts():
    """Load durable facts (people, preferences, topics) so Aubie already
    'knows' returning people at startup instead of only recognizing faces."""
    global known_facts
    if not MEMORY_FACTS_PATH.exists():
        return
    known_facts = json.loads(MEMORY_FACTS_PATH.read_text())
    print(f"[memory] loaded {len(known_facts)} known facts from {MEMORY_FACTS_PATH}")


def save_memory_facts():
    MEMORY_FACTS_PATH.write_text(json.dumps(known_facts, indent=2))


def remember_fact(fact: str):
    """Add a new durable fact if it isn't already known (exact-match dedupe),
    persist it, and trim to the most recent MAX_REMEMBERED_FACTS."""
    fact = fact.strip()
    if not fact or fact in known_facts:
        return
    known_facts.append(fact)
    del known_facts[:-MAX_REMEMBERED_FACTS]
    save_memory_facts()
    print(f"[memory] learned: {fact}")


def extract_and_remember_fact(speaker: str | None, user_text: str, assistant_text: str):
    """Best-effort: ask the text model whether this exchange revealed anything
    worth remembering long-term, and store it if so. Mirrors detect_objects()
    in swallowing failures - a flaky extraction call should never break the
    voice reply that already went out.
    """
    try:
        speaker_line = f"Speaker: {speaker}\n" if speaker and speaker != "unknown" else ""
        prompt = FACT_EXTRACTION_PROMPT.format(
            speaker_line=speaker_line, user_text=user_text, assistant_text=assistant_text
        )
        result = query_ollama(prompt, TEXT_MODEL)
    except requests.RequestException as e:
        print(f"[memory] fact extraction failed: {e}")
        return
    result = result.strip()
    if result and result.upper() != "NONE":
        remember_fact(result)


def load_vocab_memory() -> list[dict]:
    """Words/phrases learned via 'how do you say X in Y' - kept in a
    dedicated file (not aubie_memory_facts.json) since these are structured
    {phrase, language, translation} entries, not free-text facts."""
    if not VOCAB_MEMORY_PATH.exists():
        return []
    try:
        return json.loads(VOCAB_MEMORY_PATH.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(f"[vocab] failed to load {VOCAB_MEMORY_PATH}: {e}")
        return []


def save_vocab_entry(phrase: str, language: str, translation: str):
    entries = load_vocab_memory()
    entries.append({
        "phrase": phrase,
        "language": language,
        "translation": translation,
        "learned_at": datetime.utcnow().isoformat() + "Z",
    })
    VOCAB_MEMORY_PATH.write_text(json.dumps(entries, indent=2, ensure_ascii=False))
    print(f"[vocab] learned: {phrase!r} -> {translation!r} ({language})")


def remember_exchange(
    speaker: str | None,
    speakers_in_room: list[str],
    user_text: str,
    assistant_text: str,
    objects_seen: list[str],
):
    """Persist one conversational exchange (append-only) and keep it in memory
    for context injection on the next turn."""
    entry = {
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "speaker": speaker,
        "speakers_in_room": speakers_in_room,
        "user_text": user_text,
        "assistant_text": assistant_text,
        "objects_seen": objects_seen,
    }
    conversation_memory.append(entry)
    with CONVERSATION_MEMORY_PATH.open("a") as f:
        f.write(json.dumps(entry) + "\n")


# institute_memory/ holds several plain-text fact files, each gated behind
# its own trigger keywords rather than one giant always-on dump - none of it
# belongs in every single prompt (some of it, like org_facts.txt, is real
# sensitive org data; the rest is just off-topic for casual lesson chat).
# Re-read fresh on each match rather than cached - the files are tiny and
# this way an edit takes effect immediately, same spirit as scan_faces()'s
# comment above about re-reading known-faces fresh. Add a new category by
# adding one entry here and one .txt file - build_context_block() below
# picks up any match automatically.
INSTITUTE_MEMORY_DIR = Path("/home/aubieeternal/AUBIEETERNAL/institute_memory")
INSTITUTE_MEMORY_FILES = {
    "org_facts.txt": (
        "ein", "tax id", "tax-id", "tax_id", "taxid",
        "nonprofit status", "501(c)", "501c3", "501(c)(3)",
        "company email", "org email", "organization email", "institute email",
        "legal name", "registered agent", "principal address", "mailing address",
        "sunbiz", "document number", "incorporat",
        "who runs", "who owns", "who founded",
        "contact info", "phone number", "your address", "your phone",
    ),
    "robot_facts.txt": (
        "spotmicro", "spot micro", "robot dog", "aubie the robot", "the robot",
        "hip servo", "watchdog", "lidar", "sonar", "usb hub", "uno q", "unoq",
        "sketch.ino", "servo", "gait", "bridge rpc", "arduino-app-cli", "i2c",
        "pca9685", "quadruped", "your body", "your legs",
    ),
    "platform_facts.txt": (
        "curriculum", "let's go to class", "lets go to class", "class feature",
        "family_profiles", "xp system", "grant", "funding", "autogen",
        "who built you", "how were you built", "how do you work",
        "degree program", "sovereign school", "how many lessons", "how many tracks",
    ),
}


def _institute_memory_matches(text: str) -> list[str]:
    """Which institute_memory/*.txt filenames this text's keywords trigger."""
    low = text.lower()
    return [fname for fname, triggers in INSTITUTE_MEMORY_FILES.items()
            if any(trigger in low for trigger in triggers)]


# Real, live personal data (from email_watch.py's daily digest, see that
# module's PRIVACY note) - a different category from INSTITUTE_MEMORY_FILES
# above, which are static facts meant to be told to anyone who asks. This
# is Matthew's actual day, pulled from his actual inbox. Deliberately kept
# as its own trigger list/loader rather than folded into
# INSTITUTE_MEMORY_FILES, since a future speaker-scoping pass (only
# answering this to Matthew himself, not any family member who happens to
# ask) belongs here specifically, not on the org/robot/platform facts -
# not built yet, flagged as a real gap rather than silently skipped.
EMAIL_TASK_TRIGGERS = (
    "what am i supposed to do", "what do i have today", "my tasks",
    "my to-do", "my todo", "anything i need to do", "what's on my plate",
    "my schedule", "my day today", "any deadlines", "check my email",
    "what's in my inbox", "do i have anything today",
)


def _email_tasks_requested(text: str) -> bool:
    low = text.lower()
    return any(trigger in low for trigger in EMAIL_TASK_TRIGGERS)


def _load_email_digest_summary() -> str:
    try:
        from email_watch import DIGEST_PATH
        if not DIGEST_PATH.exists():
            return ""
        digest = json.loads(DIGEST_PATH.read_text())
        tasks = digest.get("tasks", [])
        if not tasks:
            return "No tasks or deadlines found in recent email - the inbox looks clear."
        lines = [f"Real tasks/deadlines found in the inbox as of {digest.get('generated_at', 'recently')}:"]
        for t in tasks:
            deadline = f" (deadline: {t['deadline']})" if t.get("deadline") else ""
            lines.append(f"  - {t.get('summary', '?')}{deadline} [from: \"{t.get('source_subject', '?')}\"]")
        return "\n".join(lines)
    except Exception as e:
        print(f"[email_watch] could not load digest: {e}")
        return ""


def _load_institute_memory_file(filename: str) -> str:
    try:
        return (INSTITUTE_MEMORY_DIR / filename).read_text().strip()
    except Exception as e:
        print(f"[institute_memory] could not read {filename}: {e}")
        return ""


def build_context_block(speakers_in_room: list[str], objects_seen: list[str], user_message: str = "") -> str:
    """Assemble what Aubie currently knows about the room and recent history,
    for injection into the LLM's system prompt as conversational grounding."""
    lines = []
    known_speakers = [s for s in speakers_in_room if s and s != "unknown"]
    if known_speakers:
        verb = "is" if len(known_speakers) == 1 else "are"
        lines.append(f"Right now, {', '.join(known_speakers)} {verb} in the room with you.")
    if objects_seen:
        lines.append(f"Around the room you can currently see: {', '.join(objects_seen)}.")

    if user_message:
        for fname in _institute_memory_matches(user_message):
            facts = _load_institute_memory_file(fname)
            if facts:
                lines.append(
                    f"Real background facts relevant to this question ({fname}) - answer "
                    f"directly and accurately from these, don't guess or make anything up:"
                )
                lines.append(facts)

        if _email_tasks_requested(user_message):
            digest_summary = _load_email_digest_summary()
            if digest_summary:
                lines.append(
                    "The question is asking about real tasks/deadlines from checking email - "
                    "answer directly from this real data, don't guess or make anything up. If "
                    "a deadline is close, say so plainly rather than downplaying it:"
                )
                lines.append(digest_summary)

    if known_facts:
        lines.append("Things you know from past conversations:")
        for fact in known_facts:
            lines.append(f"  - {fact}")

    if conversation_summary:
        lines.append(f"Summary of earlier conversation: {conversation_summary}")

    recent = conversation_memory[-MEMORY_CONTEXT_TURNS:]
    if recent:
        lines.append("Recent conversation, oldest first:")
        for ex in recent:
            who = ex.get("speaker") or "Someone"
            lines.append(f'  {who} said: "{ex["user_text"]}"')
            lines.append(f'  You (Aubie) replied: "{ex["assistant_text"]}"')

    return "\n".join(lines)

OBJECT_DETECTION_PROMPT = (
    "List the distinct physical objects visible in this image as a short "
    "comma-separated list. Be concise, lowercase, no full sentences, no explanations."
)
MAX_OBJECTS = 5
# People are already covered by face-ID greeting - drop them from the object list
# so the greeting doesn't say "hello John" and "I can see a man" for the same person.
PERSON_TERMS = {
    "man", "woman", "person", "people", "human", "boy", "girl",
    "child", "kid", "face", "man's face", "woman's face",
}

app = FastAPI(title="AUBIEETERNAL Assistant")

# ── AUBIEETERNAL Build Code ───────────────────────────────────────────────
import sys as _sys
_sys.path.insert(0, "/home/aubieeternal/AUBIEETERNAL")
from aubieeternal_build_code import handle_build_code_request

@app.post("/build-code")
async def build_code_endpoint(payload: dict):
    """
    POST /build-code
    Body: {"request": "Write a Python script that ..."}
    Runs dual-road Qwen orchestrator, executes result, returns output.
    """
    return await handle_build_code_request(payload)
# ─────────────────────────────────────────────────────────────────────────
app.include_router(debug_router)
app.include_router(phone_router)
app.include_router(browser_router)
app.include_router(interpreter_router)
app.include_router(memory_router)
app.include_router(agent_router)
app.include_router(voice_router)
app.include_router(voice_router)
app.include_router(vision_router)


@app.get("/build")
async def aubieeternal_build_redirect():
    """aubieeternal Build lives on :8840 — send browsers there."""
    return RedirectResponse("http://100.105.81.27:8840/", status_code=307)


async def _connect_to_aubie_call_stream():
    """Open the upstream /call/stream socket on aubie's aubie_dog.py,
    Tailscale first then LAN fallback - see AUBIE_HOST_TAILSCALE comment."""
    for host in (AUBIE_HOST_TAILSCALE, AUBIE_HOST_LAN):
        try:
            return await asyncio.wait_for(
                websockets.connect(f"ws://{host}:{AUBIE_CALL_PORT}/call/stream"),
                timeout=3,
            )
        except (OSError, asyncio.TimeoutError, websockets.exceptions.WebSocketException) as e:
            print(f"[call] connect to aubie via {host} failed: {e}")
    return None


@app.websocket("/call/ws")
async def call_ws(phone_ws: WebSocket):
    """Transparent relay between the phone's browser and aubie's camera/mic
    stream - no re-encoding, just pumps binary frames both directions. See
    aubie_dog.py's /call/stream for the video/audio capture side and the
    1-byte 'V'/'A' tag scheme shared by both ends.
    """
    await phone_ws.accept()
    aubie_ws = await _connect_to_aubie_call_stream()
    if aubie_ws is None:
        await phone_ws.close(code=1013, reason="could not reach aubie")
        return

    async def phone_to_aubie():
        try:
            while True:
                data = await phone_ws.receive_bytes()
                await aubie_ws.send(data)
        except (WebSocketDisconnect, websockets.exceptions.ConnectionClosed):
            pass

    async def aubie_to_phone():
        try:
            async for data in aubie_ws:
                await phone_ws.send_bytes(data)
        except websockets.exceptions.ConnectionClosed:
            pass

    task1 = asyncio.create_task(phone_to_aubie())
    task2 = asyncio.create_task(aubie_to_phone())
    try:
        # Either direction ending (phone hangs up, aubie drops) should tear
        # down the whole relay, not leave the other pump task running forever
        # waiting on a dead connection.
        await asyncio.wait({task1, task2}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for t in (task1, task2):
            t.cancel()
        await aubie_ws.close()
        try:
            await phone_ws.close()
        except RuntimeError:
            pass  # already closed

# ---- Load models once at startup ----
# "small" (not "small.en") for multilingual STT + language auto-detection,
# needed so Aubie can hold conversations in languages other than English.
print("Loading faster-whisper (GPU)...")
whisper_model = WhisperModel("small", device="cuda", compute_type="float16")

print("Loading face embeddings...")
_face_app = None
_known_faces = {}

def _load_faces():
    global _known_faces
    if FACES_NPZ.exists():
        data = np.load(FACES_NPZ, allow_pickle=True)
        # faces.npz structure: names (N,), vectors (N, 512), sources (N,)
        names = data["names"]
        vectors = data["vectors"]
        _known_faces = {"names": names, "vectors": vectors}
    else:
        print(f"WARNING: {FACES_NPZ} not found, face ID disabled")

def _get_face_app():
    global _face_app
    if _face_app is None:
        from insightface.app import FaceAnalysis
        _face_app = FaceAnalysis(name="buffalo_l")
        _face_app.prepare(ctx_id=0)
    return _face_app

_load_faces()
load_conversation_memory()
load_conversation_summary()
load_memory_facts()
load_voice_preference()


def scan_faces(image_bytes: bytes) -> list[str]:
    """Run InsightFace against the enrolled embeddings for EVERY face found.
    Returns a list of names (may include "unknown" for unrecognized faces,
    and is empty if no faces are detected at all).

    NOTE: requires plain `onnxruntime` (CPU) installed, NOT `onnxruntime-gpu`.
    The rig's onnxruntime-gpu build fails to import (missing libcudart.so.13),
    and CPU is plenty fast for single-frame face ID. See handoff doc.
    """
    if not image_bytes:
        return []
    import cv2
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    cv2.imwrite(str(SNAPSHOTS_DIR / "live_debug.jpg"), img)
    if img is None:
        return []
    faces = _get_face_app().get(img)
    if not faces:
        return []

    if not _known_faces:
        return ["unknown"] * len(faces)

    names_db = _known_faces["names"]      # shape (N,)
    vectors_db = _known_faces["vectors"]  # shape (N, 512)

    results = []
    for face in faces:
        emb = face.normed_embedding  # shape (512,)
        scores = vectors_db @ emb    # shape (N,)
        best_idx = int(np.argmax(scores))
        best_score = float(scores[best_idx])
        if best_score >= FACE_MATCH_THRESHOLD:
            results.append(str(names_db[best_idx]))
        else:
            results.append("unknown")
    return results


# ---- Guided face enrollment ("teach Aubie a new person") ----
# Client (phone_ui.py) walks the person through a few head poses (straight,
# left, right, up, down - Face ID style) and submits every candidate frame
# captured along the way; the quality filtering below is what decides which
# ones are actually good enough to learn from, so the client doesn't need
# any face-detection smarts of its own.
FACE_ENROLL_MIN_FRAMES = 3          # below this many usable frames, the whole batch is rejected
FACE_ENROLL_MAX_EMBEDDINGS = 8      # cap how many embeddings one enrollment adds, best-quality first
FACE_ENROLL_MIN_BBOX_FRAC = 0.04    # face must fill at least ~4% of the frame (too far/small = unreliable embedding)


def score_face_frame(img, face) -> float | None:
    """Quality score for one candidate enrollment frame - higher is better.
    Returns None if the frame should be rejected outright (face too small).
    Combines InsightFace's own detection confidence with a blur measure
    (variance of the Laplacian - the standard "is this crop sharp" check)
    over just the face crop, so a blurry frame loses even if a face was
    technically detected in it.
    """
    x1, y1, x2, y2 = face.bbox.astype(int)
    frame_area = img.shape[0] * img.shape[1]
    face_area = max(0, x2 - x1) * max(0, y2 - y1)
    if frame_area == 0 or face_area / frame_area < FACE_ENROLL_MIN_BBOX_FRAC:
        return None
    x1, y1 = max(0, x1), max(0, y1)
    crop = img[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    import cv2
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
    det_score = float(getattr(face, "det_score", 1.0))
    return blur_score * det_score


def append_face_embeddings(name: str, embeddings: np.ndarray):
    """Append embeddings under `name` to FACES_NPZ (creating it if this is
    the very first enrollment) and refresh the in-memory _known_faces cache
    scan_faces() reads from - re-reads the file fresh rather than trusting
    the in-memory cache, since _known_faces never carried "sources" and this
    needs to preserve it.
    """
    global _known_faces
    if FACES_NPZ.exists():
        data = np.load(FACES_NPZ, allow_pickle=True)
        names_db = data["names"]
        vectors_db = data["vectors"]
        sources_db = data["sources"] if "sources" in data.files else np.array(["unknown"] * len(names_db), dtype=object)
    else:
        names_db = np.array([], dtype=object)
        vectors_db = np.empty((0, embeddings.shape[1]))
        sources_db = np.array([], dtype=object)

    new_names = np.array([name] * len(embeddings), dtype=object)
    new_sources = np.array(["enrolled"] * len(embeddings), dtype=object)

    names_db = np.concatenate([names_db, new_names])
    vectors_db = np.concatenate([vectors_db, embeddings])
    sources_db = np.concatenate([sources_db, new_sources])

    FACES_NPZ.parent.mkdir(parents=True, exist_ok=True)
    np.savez(FACES_NPZ, names=names_db, vectors=vectors_db, sources=sources_db)
    _known_faces = {"names": names_db, "vectors": vectors_db}
    print(f"[faces] enrolled {len(embeddings)} embedding(s) for {name!r}, {len(names_db)} total in db")


# ---- Follow a named person ----
# Polls aubie's /snapshot (a one-shot camera grab, independent of whether a
# /call/stream video call is also running - see aubie_dog.py) and turns
# toward whoever's currently registered as the follow target when they
# drift off-center. Uses turn_left()/turn_right() (sketch.ino) - unverified
# against the physical robot as of when those were added, so this loop
# should only be started after confirming those turn correctly via the
# phone UI's manual Turn Left/Turn Right buttons.
FOLLOW_POLL_INTERVAL_S = 1.0
FOLLOW_CENTER_DEADBAND = 0.15  # normalized face-center offset within which we consider them centered

_follow_task: asyncio.Task | None = None
_follow_target: str | None = None


def fetch_aubie_snapshot() -> bytes:
    """GET a fresh JPEG from aubie's /snapshot - Tailscale first, LAN
    fallback, same reasoning as _connect_to_aubie_call_stream()'s fallback
    above (Tailscale's TCP path here is known to be intermittently flaky
    even when reachable)."""
    last_exc = None
    for host in (AUBIE_HOST_TAILSCALE, AUBIE_HOST_LAN):
        try:
            resp = requests.get(f"http://{host}:{AUBIE_CALL_PORT}/snapshot", timeout=5)
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as e:
            print(f"[follow] snapshot via {host} failed: {e}")
            last_exc = e
    raise last_exc


def push_audio_to_aubie(wav_bytes: bytes) -> None:
    """POST raw WAV bytes to aubie's /play_audio (plays out the EMEET
    speaker) - Tailscale first, LAN fallback, same reasoning as
    fetch_aubie_snapshot() above."""
    last_exc = None
    for host in (AUBIE_HOST_TAILSCALE, AUBIE_HOST_LAN):
        try:
            resp = requests.post(
                f"http://{host}:{AUBIE_CALL_PORT}/play_audio",
                data=wav_bytes,
                timeout=15,
            )
            resp.raise_for_status()
            return
        except requests.RequestException as e:
            print(f"[speak] play_audio via {host} failed: {e}")
            last_exc = e
    raise last_exc


def detect_target_offset(image_bytes: bytes, target_name: str) -> float | None:
    """For the follow loop only - returns the target person's horizontal
    face-center offset from frame center, normalized to [-1, 1] (negative =
    left of center), or None if they're not visible in this frame. Kept
    separate from scan_faces() (used by /greet, /converse) rather than
    generalizing it, so this doesn't risk touching that already-working
    path - this needs a bounding box and a specific-name match, neither of
    which scan_faces() computes.
    """
    if not image_bytes or not _known_faces:
        return None
    import cv2
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return None
    faces = _get_face_app().get(img)
    if not faces:
        return None

    names_db = _known_faces["names"]
    vectors_db = _known_faces["vectors"]
    target_l = target_name.strip().lower()
    frame_w = img.shape[1]

    best_face = None
    best_score = FACE_MATCH_THRESHOLD
    for face in faces:
        scores = vectors_db @ face.normed_embedding
        idx = int(np.argmax(scores))
        if str(names_db[idx]).strip().lower() != target_l:
            continue
        score = float(scores[idx])
        if score >= best_score:
            best_score = score
            best_face = face

    if best_face is None:
        return None
    x1, _, x2, _ = best_face.bbox
    return ((x1 + x2) / 2 - frame_w / 2) / (frame_w / 2)


async def _follow_loop(target_name: str):
    print(f"[follow] starting: {target_name!r}")
    try:
        while True:
            try:
                snapshot = await asyncio.to_thread(fetch_aubie_snapshot)
                offset = await asyncio.to_thread(detect_target_offset, snapshot, target_name)
            except requests.RequestException as e:
                print(f"[follow] snapshot failed: {e}")
                offset = None

            if offset is None or abs(offset) <= FOLLOW_CENTER_DEADBAND:
                action = "stand"
            elif offset > 0:
                action = "turn_right"
            else:
                action = "turn_left"
            await asyncio.to_thread(call_dog_command, {"action": action})
            await asyncio.sleep(FOLLOW_POLL_INTERVAL_S)
    except asyncio.CancelledError:
        print(f"[follow] stopped: {target_name!r}")
        raise


def build_greeting(names: list[str]) -> str:
    """Turn a list of recognized names into a natural spoken greeting."""
    if not names:
        return "I don't see anyone right now."

    known = [n for n in names if n != "unknown"]
    unknown_count = len(names) - len(known)

    # De-duplicate while preserving order (in case the same person appears twice)
    seen = set()
    unique_known = []
    for n in known:
        if n not in seen:
            seen.add(n)
            unique_known.append(n)

    if not unique_known:
        return "Hello there, I don't recognize you yet."

    if len(unique_known) == 1:
        greeting = f"Hello {unique_known[0]}!"
    elif len(unique_known) == 2:
        greeting = f"Hello {unique_known[0]} and {unique_known[1]}!"
    else:
        greeting = f"Hello {', '.join(unique_known[:-1])}, and {unique_known[-1]}!"

    if unknown_count:
        greeting += " And hello to whoever else is with you."

    return greeting


def detect_objects(image_bytes: bytes) -> list[str]:
    """Ask the vision model what objects are visible in the photo.

    Best-effort: a failed/slow Ollama call shouldn't break the face-ID greeting,
    so errors are swallowed here and just result in no object mention.
    """
    try:
        image_b64 = base64.b64encode(image_bytes).decode("ascii")
        response = query_ollama(OBJECT_DETECTION_PROMPT, VISION_MODEL, image_b64=image_b64)
    except requests.RequestException as e:
        print(f"[greet] object detection failed: {e}")
        return []

    objects = []
    for label in response.split(","):
        label = label.strip().lower()
        if not label or label in PERSON_TERMS:
            continue
        objects.append(label)
    return objects[:MAX_OBJECTS]


def describe_objects(objects: list[str]) -> str:
    """Turn a list of detected object labels into a natural spoken clause."""
    seen = set()
    unique = []
    for o in objects:
        if o not in seen:
            seen.add(o)
            unique.append(o)

    if not unique:
        return ""
    if len(unique) == 1:
        return f"I can also see {unique[0]}."
    if len(unique) == 2:
        return f"I can also see {unique[0]} and {unique[1]}."
    return "I can also see " + ", ".join(unique[:-1]) + f", and {unique[-1]}."


def transcribe(audio_path: str) -> tuple[str, str]:
    """Returns (text, language_code). whisper_model is the multilingual
    "small" model (not "small.en"), so info.language is a real auto-detected
    ISO 639-1 code (e.g. "es") - used to pick the reply's Piper voice for
    multilingual conversation."""
    segments, info = whisper_model.transcribe(audio_path, beam_size=5)
    text = " ".join(seg.text.strip() for seg in segments).strip()
    return text, info.language


def query_ollama(
    prompt: str,
    model: str,
    image_b64: str | None = None,
    context: str | None = None,
    system_override: str | None = None,
) -> str:
    if system_override is not None:
        system = system_override
    else:
        system = f"{SYSTEM_PROMPT}\n\n{context}" if context else SYSTEM_PROMPT
    payload = {
        "model": model,
        "prompt": prompt,
        "system": system,
        "stream": False,
    }
    if image_b64:
        payload["images"] = [image_b64]
    resp = requests.post(OLLAMA_URL, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json().get("response", "").strip()


_HEADER_TRANSLITERATIONS = {
    "—": "-", "–": "-", "‘": "'", "’": "'",
    "“": '"', "”": '"', "…": "...",
}


def ascii_safe_header(text: str) -> str:
    """HTTP header values must be latin-1 with no control characters, but LLM
    output routinely contains smart quotes/em-dashes/ellipses that aren't
    latin-1, and occasionally embedded newlines (multi-line replies) that
    aren't valid in a header field regardless of charset. Transliterate the
    common non-latin1 punctuation, strip control characters (multilingual
    replies made this easy to trigger - see the 2026-08-08 14:08 crash in
    the journal for the original latin-1 case this was written for), and
    replace anything else that still won't encode, rather than letting
    Response(...) raise and 500 the whole request."""
    for uni, ascii_ in _HEADER_TRANSLITERATIONS.items():
        text = text.replace(uni, ascii_)
    text = "".join(" " if ord(ch) < 0x20 or ord(ch) == 0x7F else ch for ch in text)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def synthesize_speech(text: str, voice: Path = PIPER_VOICE) -> bytes:
    """Call piper CLI, return wav bytes."""
    with tempfile.NamedTemporaryFile(suffix=".wav") as out_wav:
        proc = subprocess.run(
            [
                "piper",
                "--model", str(voice),
                "--output_file", out_wav.name,
            ],
            input=text.encode("utf-8"),
            capture_output=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"piper failed: {proc.stderr.decode()}")
        return Path(out_wav.name).read_bytes()


def show_face_caption(text: str):
    """Best-effort: display text under the face animation via the existing
    face-text Bridge RPC (see face.ino) - swallow failures like the other
    Aubie-side calls, a caption miss shouldn't break the spoken response."""
    try:
        call_dog_command({"action": "face_text", "text": text[:20]})
    except Exception as e:
        print(f"[face] caption failed: {e}")


@app.post("/converse")
async def converse(
    audio: UploadFile = File(...),
    image: UploadFile | None = File(None),
    speakers: str | None = Form(None),
    objects: str | None = Form(None),
):
    """
    speakers/objects are comma-separated hints carried forward by the client
    from the wake-time /greet call (who's in the room, what's visible) - follow-up
    turns don't re-run vision (qwen2.5vl:7b alone takes ~15s, too slow for a live
    back-and-forth), so this text stands in for a fresh photo.
    """
    audio_bytes = await audio.read()
    image_bytes = await image.read() if image is not None else None

    # 1. STT - whisper_model is multilingual, so detected_lang is a real
    # auto-detected code (e.g. "es"), used below to pick the reply voice
    # for multilingual conversation.
    with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
        tmp.write(audio_bytes)
        tmp.flush()
        transcript, detected_lang = transcribe(tmp.name)

    if not transcript:
        empty_wav = synthesize_speech("Sorry, I didn't catch that.")
        return Response(content=empty_wav, media_type="audio/wav")

    # 1b. Movement commands short-circuit straight to the Bridge RPC on Aubie -
    # skipped entirely for normal conversation, and skip face scan/Ollama chat
    # when they do match so "sit"/"stand" stay fast and deterministic.
    canned = match_canned_command(transcript)
    if canned:
        action, ack = canned
        ok = call_dog_command({"action": action})
        reply = ack if ok else "Sorry, I couldn't reach my legs just now."
        wav_bytes = synthesize_speech(reply)
        remember_exchange(None, [], transcript, reply, [])
        maybe_trigger_compaction()
        return Response(
            content=wav_bytes,
            media_type="audio/wav",
            headers={
                "X-Transcript": ascii_safe_header(transcript),
                "X-Speaker": "none",
                "X-Model-Used": "none",
                "X-Reply-Text": ascii_safe_header(reply),
            },
        )

    joint_move = extract_joint_move(transcript)
    if joint_move:
        ok = call_dog_command({"action": "set_servo", **joint_move})
        label = CHANNEL_LABELS[joint_move["channel"]]
        reply = f"Moving my {label}!" if ok else f"Sorry, I couldn't move my {label} just now."
        wav_bytes = synthesize_speech(reply)
        remember_exchange(None, [], transcript, reply, [])
        maybe_trigger_compaction()
        return Response(
            content=wav_bytes,
            media_type="audio/wav",
            headers={
                "X-Transcript": ascii_safe_header(transcript),
                "X-Speaker": "none",
                "X-Model-Used": "none",
                "X-Reply-Text": ascii_safe_header(reply),
            },
        )

    # 1c. "translate X to Y" / "how do you say X in Y" - spoken in the
    # target language and shown as a TFT caption. The "how do you say"
    # phrasing additionally persists the phrase to memory.json.
    translation_req = extract_translation_request(transcript)
    if translation_req:
        phrase, lang, is_learning = (
            translation_req["phrase"], translation_req["lang"], translation_req["is_learning"]
        )
        translation = None
        try:
            translation = query_ollama(
                TRANSLATION_PROMPT.format(language=lang, phrase=phrase),
                TEXT_MODEL,
                system_override=TRANSLATION_SYSTEM_PROMPT,
            ).strip().strip('"')
        except requests.RequestException as e:
            print(f"[translate] failed: {e}")

        if translation:
            voice = VOICE_BY_NAME.get(lang)
            spoken = translation if voice else f"In {lang}, that's {translation}."
            voice = voice or VOICE_BY_NAME["english"]
            show_face_caption(translation)
            if is_learning:
                save_vocab_entry(phrase, lang, translation)
            wav_bytes = synthesize_speech(spoken, voice=voice)
            remember_exchange(None, [], transcript, translation, [])
            maybe_trigger_compaction()
            return Response(
                content=wav_bytes,
                media_type="audio/wav",
                headers={
                    "X-Transcript": ascii_safe_header(transcript),
                    "X-Speaker": "none",
                    "X-Model-Used": TEXT_MODEL,
                    "X-Reply-Text": ascii_safe_header(translation),
                },
            )
        # translation call failed - fall through to normal conversation

    # 2. Who's in the room: fresh face scan if we got an image, else trust the client's hint
    hint_speakers = [s.strip() for s in speakers.split(",") if s.strip()] if speakers else []
    speaker_names = scan_faces(image_bytes) if image_bytes else hint_speakers
    speaker = speaker_names[0] if speaker_names else None
    objects_seen = [o.strip() for o in objects.split(",") if o.strip()] if objects else []

    # 3. Build prompt + route model, with memory/room context injected into the system prompt
    context_block = build_context_block(speaker_names, objects_seen, user_message=transcript)

    # Tutor progress (XP/level/streak) - same family_profiles persistence
    # already proven durable in phone_ui.py's /proxy/tutor_ask (confirmed
    # 2026-08-17 to survive a service restart). family_id is hardcoded to
    # "default" for now, matching that endpoint - real per-kid identity via
    # the speaker face-ID above (`speaker`) is a separate follow-up, not
    # done here yet (see spotmicro_dog_aubieeternal_tutor_integration memory).
    tutor_stats = load_family_stats(TUTOR_FAMILY_ID)
    context_block += (
        f"\nThe person you're talking to is level {tutor_stats.get('level', 1)} "
        f"with {tutor_stats.get('total_xp', 0)} XP and a "
        f"{tutor_stats.get('streak_days', 0)}-day streak - acknowledge their "
        f"progress warmly if it feels natural, don't force it into every reply."
    )

    prompt = transcript
    if speaker and speaker != "unknown":
        prompt = f"[Speaking: {speaker}] {transcript}"

    # Aubie attaches a fresh photo on every follow-up turn (for the face
    # rescan above), but only pay the ~15s vision-model latency when the
    # transcript is actually asking about something visual - plain chat
    # stays on the fast text model even with a photo attached.
    use_vision = bool(image_bytes) and OBJECT_ID_RE.search(transcript) is not None
    if use_vision:
        model = VISION_MODEL
        image_b64 = base64.b64encode(image_bytes).decode("ascii")
        prompt = f"{prompt}\n\n(They're holding something up to the camera or pointing at it - identify it and share one brief, genuinely interesting fact about it.)"
        reply = query_ollama(prompt, model, image_b64=image_b64, context=context_block)
    else:
        model = TEXT_MODEL
        reply = query_ollama(prompt, model, context=context_block)

    # Award XP for this conversational turn - same rate as /proxy/tutor_ask,
    # only on the real conversational path (not the canned-command/
    # joint-move/translation short-circuits above, which return early).
    tutor_stats["total_xp"] = tutor_stats.get("total_xp", 0) + TUTOR_XP_PER_QUESTION
    tutor_stats["level"] = max(1, tutor_stats["total_xp"] // 100 + 1)
    save_family_stats(tutor_stats, TUTOR_FAMILY_ID)

    # 4. TTS (in the detected input language, if we have that voice - see
    # SYSTEM_PROMPT's instruction to reply in the same language) + best-effort
    # long-term fact extraction, concurrently - the fact extraction call is a
    # second LLM round-trip and must not add to the latency of the spoken reply.
    reply_voice = VOICE_BY_CODE.get(detected_lang) or get_active_voice()
    wav_bytes, _ = await asyncio.gather(
        asyncio.to_thread(synthesize_speech, reply, reply_voice),
        asyncio.to_thread(extract_and_remember_fact, speaker, transcript, reply),
    )

    # 5. Remember this exchange for future context
    remember_exchange(speaker, speaker_names, transcript, reply, objects_seen)
    maybe_trigger_compaction()

    return Response(
        content=wav_bytes,
        media_type="audio/wav",
        headers={
            "X-Transcript": ascii_safe_header(transcript),
            "X-Speaker": speaker or "none",
            "X-Model-Used": model,
            "X-Reply-Text": ascii_safe_header(reply[:500]),
            "X-Used-Vision": "1" if use_vision else "0",
        },
    )


@app.post("/greet")
async def greet(image: UploadFile = File(...)):
    """
    Send a photo, get back a spoken greeting for EVERYONE recognized in it,
    plus a mention of the objects seen (via qwen2.5vl:7b object detection).
    No STT/audio input needed - just camera -> face ID + object detection -> TTS.
    """
    image_bytes = await image.read()
    # Face ID and object detection are independent - run them concurrently since
    # the vision model call alone takes ~15s and this feeds a live voice interaction.
    names, objects = await asyncio.gather(
        asyncio.to_thread(scan_faces, image_bytes),
        asyncio.to_thread(detect_objects, image_bytes),
    )

    # Personalized celebration for a specific recognized face - fired before
    # TTS so the visual starts roughly in sync with the spoken greeting.
    # Best-effort like the other dog-command calls: a bridge hiccup here
    # shouldn't block or fail the greeting itself.
    if any(n.lower() == "gabriela" for n in names):
        await asyncio.to_thread(call_dog_command, {"action": "flower_explosion"})

    text = build_greeting(names)
    objects_clause = describe_objects(objects)
    if objects_clause:
        text = f"{text} {objects_clause}"

    wav_bytes = synthesize_speech(text)
    return Response(
        content=wav_bytes,
        media_type="audio/wav",
        headers={
            "X-Speakers": ascii_safe_header(",".join(names)) if names else "none",
            "X-Greeting": ascii_safe_header(text),
            "X-Objects": ascii_safe_header(",".join(objects)) if objects else "none",
        },
    )


@app.post("/vision_describe")
async def vision_describe(
    image: UploadFile = File(...),
    prompt: str = Form("Describe what you see in detail."),
):
    """
    Natural-language scene description via the qwen2.5vl:7b vision model
    (same VISION_MODEL used by /greet's object detection) - for the phone
    UI's Camera card "Describe" button, which wants a chatty description
    rather than vision_extras.py's YOLO label/color/QR summary.
    """
    image_bytes = await image.read()
    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    try:
        description = await asyncio.to_thread(query_ollama, prompt, VISION_MODEL, image_b64=image_b64)
    except requests.RequestException as e:
        raise HTTPException(502, f"vision model failed: {e}")
    return {"description": description}


_POLYVAGAL_STATE_MAP = {
    "ventral":     {"value": 2, "emoji": "🟢", "coherence_boost": 0.02},
    "sympathetic": {"value": 1, "emoji": "🟡", "coherence_boost": -0.01},
    "dorsal":      {"value": 0, "emoji": "🔴", "coherence_boost": -0.02},
}


@app.post("/mood_check")
async def mood_check(image: UploadFile = File(...)):
    """
    Periodic camera-based mood/nervous-system read, meant to piggyback on
    the tablet's Watch-mode camera session (already open for face-ID/
    greeting - no separate camera permission or stream needed). Face-IDs
    whoever's in frame (same scan_faces() /greet uses) so the read is
    tagged to the right family automatically instead of a generic bucket,
    asks the local vision model for a one-line mood read + a rough
    polyvagal-state guess, and logs it to the same polyvagal_states.jsonl
    the Streamlit app's Polyvagal Oracle > State Check tab already reads
    its history from - tagged source="camera_mood_check" so it's visibly
    distinguishable from a manual check-in, not silently blended in as if
    it were equally authoritative. This is a rough AI read of one photo,
    not a diagnosis - framed that way in the prompt below on purpose.
    """
    image_bytes = await image.read()
    names = await asyncio.to_thread(scan_faces, image_bytes)
    recognized = next((n for n in names if n and n != "unknown"), None)

    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    prompt = (
        "Look at this person's facial expression and posture. Respond with "
        "EXACTLY two lines in English, nothing else, no extra commentary:\n"
        "STATE: one word - ventral, sympathetic, or dorsal (polyvagal "
        "nervous system state - ventral=calm/curious/safe, "
        "sympathetic=activated/stressed/frustrated, dorsal=withdrawn/flat/"
        "shut down)\n"
        "NOTE: one short, warm sentence describing what you see - casual "
        "and kind, never clinical or alarming. This is a casual mood "
        "check-in, not a medical or psychological diagnosis."
    )
    try:
        # system_override, not the default Aubie persona (SYSTEM_PROMPT) -
        # that persona explicitly instructs "reply in whatever language the
        # person used" and "end with a follow-up question", both of which
        # fought the strict STATE:/NOTE: format below in testing (got a
        # chatty French reply with no STATE: line at all on the first try).
        raw = await asyncio.to_thread(
            query_ollama, prompt, VISION_MODEL, image_b64=image_b64,
            system_override="You are a precise vision-analysis tool. Follow the requested output format exactly.",
        )
    except requests.RequestException as e:
        raise HTTPException(502, f"vision model failed: {e}")

    state, note = None, raw.strip()
    for line in raw.splitlines():
        low = line.strip().lower()
        if low.startswith("state:"):
            for cand in _POLYVAGAL_STATE_MAP:
                if cand in low:
                    state = cand
                    break
        elif low.startswith("note:"):
            note = line.split(":", 1)[1].strip()

    if state is None:
        # Model didn't follow the STATE:/NOTE: format - fall back to the
        # same keyword classifier the Polyvagal Oracle tab's free-text
        # "Describe It" assessment already uses, applied to the raw reply
        # instead of silently defaulting to one state.
        low_raw = raw.lower()
        if any(w in low_raw for w in ["safe", "connect", "play", "curious", "love", "joy",
                                       "happy", "excited", "calm", "ready", "relax", "détendu"]):
            state = "ventral"
        elif any(w in low_raw for w in ["stress", "angry", "anxious", "fight", "flight",
                                         "worry", "scared", "panic", "overwhelm", "tense", "rage"]):
            state = "sympathetic"
        elif any(w in low_raw for w in ["withdrawn", "flat", "numb", "shut down", "shutdown",
                                         "disconnect", "blank"]):
            state = "dorsal"
        else:
            state = "sympathetic"  # neutral-ish default when genuinely ambiguous

    # Resolve the recognized face to a real family_id via linked_face_name -
    # the same link /class/profile already lets a family set up, and the
    # same lookup checkForFace() in the tablet UI does client-side for
    # auto-selecting the class chip.
    family_id = "operator"
    member = recognized or "Unknown"
    if recognized:
        for fid, info in FAMILY_REGISTRY.items():
            if load_family_stats(fid).get("linked_face_name", "").lower() == recognized.lower():
                family_id = fid
                member = info.get("kid_name") or recognized
                break

    sv = _POLYVAGAL_STATE_MAP[state]
    log_path = Path("/mnt/main/polyvagal_states.jsonl") if Path("/mnt/main").exists() \
               else Path(os.path.expanduser("~/.aubieeternal/main/polyvagal_states.jsonl"))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "family_id": family_id, "member": member,
        "state": f"{sv['emoji']} {state.upper()}"[:7],
        "state_value": sv["value"], "notes": note,
        "coherence_boost": sv["coherence_boost"],
        "source": "camera_mood_check",
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")

    return {"state": state, "note": note, "family_id": family_id, "member": member}


def _unsplash_search_top(phrase: str, page: int = 1) -> dict:
    """Search Unsplash for `phrase`, ping the required download-tracking
    endpoint for the top result, and return that result's raw JSON dict.
    Shared by /generate_image (pushes to Aubie's TFT) and /show_me_image
    (returns a URL for direct display in the tablet UI)."""
    if not UNSPLASH_ACCESS_KEY:
        raise HTTPException(500, "UNSPLASH_ACCESS_KEY not configured (see .env)")

    try:
        search_resp = requests.get(
            UNSPLASH_SEARCH_URL,
            params={"query": phrase, "per_page": 1, "page": page},
            headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"},
            timeout=10,
        )
        search_resp.raise_for_status()
    except requests.RequestException as e:
        raise HTTPException(502, f"Unsplash search failed: {e}")

    results = search_resp.json().get("results", [])
    if not results:
        raise HTTPException(404, f"no Unsplash results for {phrase!r}")
    top = results[0]

    # Unsplash API guidelines require pinging download_location when a photo
    # is actually used (not just searched) - best-effort, shouldn't block
    # the response if it fails.
    try:
        requests.get(
            top["links"]["download_location"],
            headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"},
            timeout=5,
        )
    except requests.RequestException as e:
        print(f"[unsplash] download-tracking ping failed: {e}")

    return top


@app.post("/generate_image")
async def generate_image(phrase: str = Form(...)):
    """
    Search Unsplash for `phrase`, grab the top result, shrink it to
    SHOW_IMAGE_W x SHOW_IMAGE_H RGB565, and push it to Aubie's TFT via the
    show_image Bridge RPC (aubie_dog.py) - same chunked hex transfer the
    wake-word photo thumbnail already uses (see photo_chunk_start/
    photo_chunk/photo_render in sketch/face.ino).
    """
    top = _unsplash_search_top(phrase)

    try:
        img_resp = requests.get(top["urls"]["small"], timeout=15)
        img_resp.raise_for_status()
    except requests.RequestException as e:
        raise HTTPException(502, f"failed to download image: {e}")

    try:
        hex_data = image_bytes_to_rgb565_hex(img_resp.content)
    except ValueError as e:
        raise HTTPException(502, f"failed to process image: {e}")

    ok = call_dog_command({"action": "show_image", "image_hex": hex_data})
    return {
        "ok": ok,
        "phrase": phrase,
        "photographer": top.get("user", {}).get("name"),
        "source": top.get("links", {}).get("html"),
    }


@app.post("/show_me_image")
async def show_me_image(phrase: str = Form(...), page: int = Form(1)):
    """
    Search Unsplash for `phrase` and return a directly-displayable image URL
    - for the phone UI's "Show Me" card, which renders the photo in the
    tablet's own <img> rather than pushing it to Aubie's TFT (see
    /generate_image for that path). `page` lets the client page through
    different top results for the same query ("Show me another").
    """
    top = _unsplash_search_top(phrase, page=page)
    return {
        "ok": True,
        "url": top["urls"]["regular"],
        "phrase": phrase,
        "photographer": top.get("user", {}).get("name"),
        "source": top.get("links", {}).get("html"),
    }


@app.post("/enroll_face")
async def enroll_face(name: str = Form(...), images: list[UploadFile] = File(...)):
    """
    Guided enrollment: the client (phone_ui.py) captures several candidate
    frames while walking the person through a few head poses and submits
    them all here. Each frame is scored (score_face_frame) and only the
    best FACE_ENROLL_MAX_EMBEDDINGS are kept - mirrors how Face ID silently
    discards bad captures during its own guided scan rather than trusting
    the client to know which frames are good.
    """
    name = name.strip()
    if not name:
        raise HTTPException(400, "name required")

    import cv2
    face_app = _get_face_app()
    candidates: list[tuple[float, np.ndarray]] = []
    rejected_multi_face = 0
    rejected_no_face = 0

    for upload in images:
        data = await upload.read()
        arr = np.frombuffer(data, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            continue
        faces = face_app.get(img)
        if len(faces) == 0:
            rejected_no_face += 1
            continue
        if len(faces) > 1:
            # Ambiguous which face in frame is the person being enrolled -
            # skip rather than risk learning the wrong one.
            rejected_multi_face += 1
            continue
        score = score_face_frame(img, faces[0])
        if score is None:
            continue
        candidates.append((score, faces[0].normed_embedding))

    if len(candidates) < FACE_ENROLL_MIN_FRAMES:
        raise HTTPException(
            422,
            f"only {len(candidates)} usable photo(s) out of {len(images)} submitted "
            f"(need at least {FACE_ENROLL_MIN_FRAMES}) - "
            f"{rejected_no_face} had no face, {rejected_multi_face} had more than one face. "
            "Try again with better/more even lighting and one person in frame.",
        )

    candidates.sort(key=lambda c: c[0], reverse=True)
    kept = candidates[:FACE_ENROLL_MAX_EMBEDDINGS]
    append_face_embeddings(name, np.stack([emb for _, emb in kept]))

    return {
        "ok": True,
        "name": name,
        "submitted": len(images),
        "kept": len(kept),
    }


@app.post("/speak")
async def speak(text: str = Form(...)):
    """
    Synthesizes `text` via Piper and plays it out Aubie's speaker - used by
    the phone UI's "Say / Command" box so typed text is actually spoken, not
    just shown as a TFT caption (that still happens separately via the
    existing face_text Bridge RPC, this doesn't replace it).
    """
    text = text.strip()
    if not text:
        raise HTTPException(400, "text required")
    wav_bytes = await asyncio.to_thread(synthesize_speech, text, get_active_voice())
    await asyncio.to_thread(push_audio_to_aubie, wav_bytes)
    return {"ok": True}


@app.post("/speak_local")
async def speak_local(text: str = Form(...)):
    """
    Synthesizes `text` via Piper and returns the WAV directly to the caller,
    for playback on whatever device asked - unlike /speak, this does NOT
    push audio to Aubie's own speaker, so it's what the tablet-as-interface
    UI (phone_ui.py's aubieSpeak()) uses to speak through the tablet itself
    while the robot's camera/speaker hardware is out of commission.
    """
    text = text.strip()
    if not text:
        raise HTTPException(400, "text required")
    wav_bytes = await asyncio.to_thread(synthesize_speech, text, get_active_voice())
    return Response(content=wav_bytes, media_type="audio/wav")


@app.get("/voice_presets")
def voice_presets():
    return {
        "presets": [{"key": k, "label": label} for k, (label, _) in VOICE_PRESETS.items()],
        "selected": selected_voice_preset,
    }


@app.post("/voice_presets/select")
async def select_voice_preset(preset: str = Form(...)):
    global selected_voice_preset
    if preset not in VOICE_PRESETS:
        raise HTTPException(400, f"Unknown voice preset: {preset}")
    selected_voice_preset = preset
    save_voice_preference()
    return {"ok": True, "selected": selected_voice_preset}


@app.get("/known_people")
def known_people():
    if not _known_faces:
        return {"names": []}
    return {"names": sorted(set(str(n) for n in _known_faces["names"]))}


@app.post("/follow/start")
async def follow_start(name: str = Form(...)):
    global _follow_task, _follow_target
    name = name.strip()
    if not name:
        raise HTTPException(400, "name required")
    if not _known_faces or name.lower() not in {str(n).lower() for n in _known_faces["names"]}:
        raise HTTPException(404, f"{name!r} isn't a known person yet - enroll them first")
    if _follow_task is not None:
        _follow_task.cancel()
    _follow_target = name
    _follow_task = asyncio.create_task(_follow_loop(name))
    return {"ok": True, "following": name}


@app.post("/follow/stop")
async def follow_stop():
    global _follow_task, _follow_target
    if _follow_task is not None:
        _follow_task.cancel()
        _follow_task = None
    _follow_target = None
    await asyncio.to_thread(call_dog_command, {"action": "stand"})
    return {"ok": True}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "faces_loaded": len(_known_faces["names"]) if _known_faces else 0,
        "whisper_ready": whisper_model is not None,
    }

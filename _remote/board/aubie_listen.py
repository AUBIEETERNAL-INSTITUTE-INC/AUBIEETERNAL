"""
AUBIEETERNAL wake-word listener - runs on Aubie (the UNO Q), not the rig.

Listens for "hey_aubie" via the trained Edge Impulse model, and on
detection: captures a photo, sends it to the rig's /greet endpoint,
plays the spoken response back through the EMEET, then keeps the
conversation going for up to MAX_CONVERSE_TURNS follow-up exchanges
before returning to wake-word listening.

Run with:
  python3 aubie_listen.py

Stop with Ctrl+C.
"""

import json
import os
import re
import subprocess
import tempfile
import threading
import time
import wave
from pathlib import Path

# aubie-listen.service has no XDG_RUNTIME_DIR in its Environment= (it's not a
# desktop-session process), but pw-play needs it to find the PipeWire socket.
os.environ.setdefault("XDG_RUNTIME_DIR", "/run/user/1000")

import cv2
import requests

import socket, struct, time as _time

from edge_impulse_linux.audio import AudioImpulseRunner

def _audio_timeout(path, minimum=15, margin=5):
    """aplay's subprocess timeout needs to cover the actual clip length, not
    a flat guess - longer TTS replies were getting killed mid-sentence by a
    fixed 15s cap. Falls back to `minimum` if the duration can't be read."""
    try:
        with wave.open(str(path), "rb") as wf:
            duration = wf.getnframes() / float(wf.getframerate())
    except (wave.Error, OSError):
        return minimum
    return max(minimum, duration + margin)


def bridge_call(method, arg="", block=False):
    """Call Arduino Bridge directly (no Docker).

    block=True now logs a failure (nonzero exit - e.g. "method X not
    available") instead of silently discarding it. subprocess.run() doesn't
    raise on a nonzero return code without check=True, so the old version's
    try/except never actually caught a rejected RPC - only a real subprocess
    launch error (which basically never happens) - meaning every rejected
    call (see ERROR_LEDGER.md's 2026-09-13 firmware-gap entry: everything
    except wave/wave_diag/hub_diag is currently rejected) produced zero
    log output at all. block=False (fire-and-forget) still can't check this
    without waiting, which would defeat the point of not blocking.
    """
    import os
    env = os.environ.copy()
    env["PYTHONPATH"] = "/home/arduino/pylib"
    cmd = [
        "python3", "-c",
        "import sys; from arduino.app_utils import Bridge; Bridge.call(sys.argv[1], sys.argv[2])",
        method, arg,
    ]
    try:
        if block:
            proc = subprocess.run(cmd, env=env, timeout=5, capture_output=True)
            if proc.returncode != 0:
                stderr = proc.stderr.decode(errors="ignore").strip()
                detail = stderr.splitlines()[-1] if stderr else f"exit {proc.returncode}"
                print(f"[bridge] {method} rejected: {detail}")
        else:
            subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"[bridge] {method} failed: {e}")


def dog_command(action, **kwargs):
    """Calls bridge_call() directly (see ERROR_LEDGER.md, 2026-09-11 /
    2026-09-13 entries). This used to POST to aubie_dog.py's own
    /dog/command HTTP API instead of spawning a fresh bridge_call()
    subprocess, specifically to avoid racing aubie_dog.py's own in-process
    Bridge.call()s (confirmed 2026-08-17 to wedge the shared RPC link) - see
    git history for that version. aubie_dog.py's process (the retired
    spotmicro_dog app's Docker container) no longer exists, so the port it
    listened on (8420) has been dead since spotmicro_dog -> aubie-tutor;
    every call here was silently failing with ConnectionRefused. Calling
    bridge_call() directly is safe now specifically because nothing else in
    this process touches the bridge concurrently with this call site:
    idle_scan_loop() (the only other background thread) never calls
    bridge_call()/dog_command(), and every other bridge_call() site in this
    file runs in the same single main-loop thread as this one, never
    concurrently with it. If a future change adds a second thread that also
    calls bridge_call(), add a shared lock here first.

    "play_pong" takes a String on the MCU side ("true"/"false"), matching
    the convention the old aubie_dog.py used for this same action - not the
    plain bool `block=` bridge_call() itself takes.

    bridge_call() already swallows and logs its own subprocess errors, so
    there's no exception here to catch - unlike the old HTTP version this
    can't distinguish success from failure, only "the call was made."
    """
    if action == "play_pong":
        bridge_call("play_pong", "true" if kwargs.get("on") else "false", block=True)
    else:
        bridge_call(action, block=True)

# Shared across the wake-word capture path and the idle-scan thread below so
# they never call fswebcam on CAMERA_DEVICE at the same time (most UVC
# webcams, including the EMEET, only support one exclusive stream consumer).
CAMERA_LOCK = threading.Lock()
# Set while a real wake-word interaction (greet + follow-up conversation) is
# in progress, so the idle-scan thread backs off entirely rather than just
# waiting on CAMERA_LOCK for a brief window - avoids doubling up load on the
# rig (idle /greet + real /converse) during an actual conversation.
WAKE_BUSY = threading.Event()


def capture_and_greet():
    """Capture a photo, get a spoken greeting from the rig, play it.

    Returns (speakers, objects) hint strings (as sent back by the rig in the
    X-Speakers/X-Objects headers) on success, or None on failure - the caller
    uses None to skip starting a follow-up conversation.
    """
    print("[trigger] Wake word detected! Capturing photo...")
    try:
        with CAMERA_LOCK:
            subprocess.run(
                [
                    "fswebcam",
                    "-d", CAMERA_DEVICE,
                    "-r", "1920x1080",
                    "-S", "20",
                    "--no-banner",
                    CAPTURE_PATH,
                ],
                check=True,
                capture_output=True,
                timeout=15,
            )
    except subprocess.CalledProcessError as e:
        print(f"[error] fswebcam failed: {e.stderr.decode(errors='ignore')}")
        return None
    except subprocess.TimeoutExpired:
        print("[error] fswebcam timed out")
        return None

    set_face_state("thinking")
    print("[trigger] Sending photo to rig...")
    try:
        with open(CAPTURE_PATH, "rb") as f:
            image_bytes = f.read()
        resp = _post_to_rig("/greet", files={"image": image_bytes})
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[error] Request to rig failed: {e}")
        return None

    greeting_text = resp.headers.get("X-Greeting", "")
    speakers = resp.headers.get("X-Speakers", "")
    objects_ = resp.headers.get("X-Objects", "")
    print(f"[trigger] Rig replied - speakers: {speakers!r}, objects: {objects_!r}, text: {greeting_text!r}")

    with open(GREETING_PATH, "wb") as f:
        f.write(resp.content)

    known = [
        s.strip().capitalize() for s in speakers.split(",")
        if s.strip() and s.strip().lower() not in ("unknown", "none")
    ]
    if known:
        try:
            bridge_call("face-text", known[0])
        except Exception:
            pass

    set_face_state("speaking")
    print("[trigger] Playing greeting...")
    try:
        bridge_call("face_talk", block=True)
    except Exception:
        pass
    # Kill any existing playback before starting new one
    subprocess.run(["pkill", "-f", "pw-play"], capture_output=True)
    try:
        # pw-play, not aplay: PipeWire holds this card exclusively (confirmed
        # - raw ALSA opens against it fail with "Invalid argument"/"No such
        # file or directory" while PipeWire is running), so playback has to
        # go through the PipeWire graph rather than around it.
        subprocess.run(
            ["pw-play", GREETING_PATH],
            check=True,
            capture_output=True,
            timeout=_audio_timeout(GREETING_PATH),
        )
    except subprocess.CalledProcessError as e:
        print(f"[error] pw-play failed: {e.stderr.decode(errors='ignore')}")
    except subprocess.TimeoutExpired:
        print("[error] pw-play timed out")
    finally:
        try:
            bridge_call("face_idle")
        except Exception:
            pass

    return speakers, objects_


def detect_emeet_card_id():
    """Read the ALSA card id (e.g. 'Plus') assigned to the EMEET mic/speaker.

    Card ids are derived from the hardware's own USB-reported name, so they
    stay stable across reboots/re-enumeration even if the numeric card index
    (card 0, card 1, ...) shifts.
    """
    try:
        cards = Path("/proc/asound/cards").read_text()
    except OSError:
        return None
    match = re.search(r"^\s*\d+\s*\[(\S+)\s*\]:.*EMEET", cards, re.IGNORECASE | re.MULTILINE)
    return match.group(1) if match else None


def ensure_emeet_plug_device(card_id, pcm_name="aubie_emeet"):
    """Define a named ALSA 'plug' PCM pointed at the EMEET's hw device.

    PortAudio (used by the Edge Impulse classifier) can only select a device
    by numeric index from its own enumeration, not an arbitrary ALSA device
    string, and the EMEET's raw hw device only supports 48kHz - it can't be
    opened directly at the model's 16kHz. Defining a named "plug" PCM here
    makes PortAudio enumerate a device that transparently resamples to
    whatever rate is requested, addressed by the EMEET's card id rather than
    a hardcoded card number.
    """
    begin = "# BEGIN aubie-listen auto-generated"
    end = "# END aubie-listen auto-generated"
    block = (
        f"{begin}\n"
        f"pcm.{pcm_name} {{\n"
        f"    type plug\n"
        f'    slave.pcm "hw:CARD={card_id},DEV=0"\n'
        f"}}\n"
        f"{end}\n"
    )
    asoundrc = Path.home() / ".asoundrc"
    existing = asoundrc.read_text() if asoundrc.exists() else ""
    if block in existing:
        return
    if begin in existing and end in existing:
        existing = re.sub(
            re.escape(begin) + r".*?" + re.escape(end) + r"\n?",
            block,
            existing,
            flags=re.DOTALL,
        )
    else:
        existing = existing + ("\n" if existing and not existing.endswith("\n") else "") + block
    asoundrc.write_text(existing)


def find_pyaudio_device_index(name):
    import pyaudio
    p = pyaudio.PyAudio()
    try:
        for i in range(p.get_device_count()):
            if p.get_device_info_by_index(i).get("name") == name:
                return i
    finally:
        p.terminate()
    return None


# The EMEET is capture-only (confirmed via `aplay -l` - it has zero listed
# playback subdevices). Real speaker output on this board is the touchscreen
# itself over HDMI, which lives on a completely separate ALSA card
# ("Arduino-Imola-HPH-LOUT", card 1, DEV=0 - matches PipeWire's own "[Out]
# HDMI" route info showing card.profile.port=0). Using the EMEET's plughw for
# BOTH record and playback (the previous behavior) meant every aplay call was
# silently failing against a card with no speaker at all.
PLAYBACK_DEVICE_HDMI = "plughw:CARD=ArduinoImolaHPH,DEV=0"


def detect_audio_devices():
    """Auto-detect the EMEET mic instead of relying on a hardcoded device index.

    Returns (audio_device_index_for_classifier, record_device, playback_device),
    or (None, None, None) if the EMEET isn't currently reachable. There's no
    usable fallback RECORD device on this board (the only other ALSA card,
    the touchscreen's own HDMI audio, is output-only), so callers must treat
    None as "not ready yet" and retry later rather than passing it on to the
    classifier.
    """
    card_id = detect_emeet_card_id()
    if card_id is None:
        return None, None, None

    ensure_emeet_plug_device(card_id)
    device_index = find_pyaudio_device_index("aubie_emeet")
    if device_index is None:
        return None, None, None

    plughw = f"plughw:CARD={card_id},DEV=0"
    print(f"[audio] EMEET detected on card '{card_id}' -> PortAudio device {device_index}, {plughw}")
    return device_index, plughw, PLAYBACK_DEVICE_HDMI


# Set by aubie_dog.py's /call/stream (in the spotmicro_dog container) while a
# video/audio call is live, so this listener releases the EMEET mic instead
# of fighting the call for exclusive capture access - path is the container's
# bind-mounted /app == this host's ~/spotmicro_dog, so both sides see the
# same file without needing an extra IPC channel.
CALL_ACTIVE_FLAG = Path("/home/arduino/spotmicro_dog/.call_active")

MODEL_PATH = "/home/arduino/aubie-wake.eim"
CAMERA_DEVICE = "/dev/video0"
CAPTURE_PATH = "/home/arduino/wake_capture.jpg"
GREETING_PATH = "/home/arduino/greeting.wav"
AUDIO_DEVICE, RECORD_DEVICE, PLAYBACK_DEVICE = None, None, None
AUDIO_POLL_SECONDS = 10
# "Find your own fun" idle demo - if this long passes with no wake-word
# interaction, lie down and play Pong on the face until "hey aubie" fires.
IDLE_FUN_TIMEOUT_S = 180
RECORD_PATH = "/home/arduino/response.wav"
REPLY_PATH = "/home/arduino/reply.wav"

# aubie's Tailscale path to the rig is known to be intermittently flaky even
# when `tailscale ping` succeeds - both machines are on the same 192.168.1.x
# LAN, so fall back to that rather than let a "hey aubie" turn just die
# after a 30s timeout with nothing spoken back (the exact failure mode this
# fixes - see journalctl: wake word fired fine, "Connection to
# 100.105.81.27 timed out" on every rig request).
RIG_HOST_TAILSCALE = "100.105.81.27"
RIG_HOST_LAN = "192.168.1.251"
RIG_PORT = 8800
# Separate connect vs read timeouts, not one flat number: a genuinely down
# path fails at the TCP-connect stage almost immediately, so a short connect
# timeout still fails over fast. But a vision-model reply (the "what is
# this" path) can legitimately take 15-20s+ to generate once connected - a
# short flat timeout was triggering a needless failover to LAN mid-request
# even when Tailscale was working fine, just slow for that one request.
RIG_CONNECT_TIMEOUT = 5
RIG_READ_TIMEOUT = 35


def _post_to_rig(path, files=None, data=None):
    """POST to the rig, trying Tailscale first then falling back to LAN.
    `files` values must be bytes, not open file handles - a failed first
    attempt would otherwise leave the handle already consumed (at EOF) for
    the retry.
    """
    last_exc = None
    for host in (RIG_HOST_LAN, RIG_HOST_TAILSCALE):
        url = f"http://{host}:{RIG_PORT}{path}"
        try:
            return requests.post(url, files=files, data=data,
                                  timeout=(RIG_CONNECT_TIMEOUT, RIG_READ_TIMEOUT))
        except requests.RequestException as e:
            print(f"[rig] {url} failed: {e}")
            last_exc = e
    raise last_exc

# Must match PHOTO_W/PHOTO_H/PHOTO_BYTES in sketch/face.ino exactly - the MCU
# just fills a fixed-size buffer, it doesn't know the image dimensions.
PHOTO_THUMB_W, PHOTO_THUMB_H = 64, 48
# A single Bridge RPC call tops out around ~235 bytes of String payload
# (measured empirically against face_text - 235 chars works, 240 fails), so
# the ~1536-byte hex-encoded thumbnail has to go over in many small pieces.
PHOTO_CHUNK_HEX_LEN = 192  # 96 raw bytes/chunk, well under that limit


def send_photo_thumbnail(image_path):
    """Best-effort: shrink the just-captured photo to a tiny RGB565
    thumbnail and stream it to the TFT via chunked Bridge RPC calls. Only
    called when the rig's reply actually came from the vision model
    (X-Used-Vision header) - see photo_chunk_start/photo_chunk/photo_render
    in sketch/face.ino for the MCU side. Runs all the chunk calls in ONE
    subprocess (not bridge_call() per chunk) since spawning a fresh Python
    interpreter per RPC call would make ~16 chunks noticeably slow.
    """
    try:
        img = cv2.imread(str(image_path))
        if img is None:
            print(f"[photo] couldn't read {image_path}")
            return

        # fswebcam captures at 16:9 (1920x1080, Arducam 16MP) but the thumbnail is 4:3
        # (PHOTO_THUMB_W x PHOTO_THUMB_H) - resizing straight to that box
        # without correcting for the ratio squishes the image horizontally.
        # Center-crop to the target ratio first instead.
        h, w = img.shape[:2]
        target_ratio = PHOTO_THUMB_W / PHOTO_THUMB_H
        src_ratio = w / h
        if src_ratio > target_ratio:
            new_w = int(h * target_ratio)
            x0 = (w - new_w) // 2
            img = img[:, x0:x0 + new_w]
        else:
            new_h = int(w / target_ratio)
            y0 = (h - new_h) // 2
            img = img[y0:y0 + new_h, :]

        img = cv2.resize(img, (PHOTO_THUMB_W, PHOTO_THUMB_H))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        raw = bytearray()
        for row in img:
            for r, g, b in row:
                rgb565 = ((int(r) & 0xF8) << 8) | ((int(g) & 0xFC) << 3) | (int(b) >> 3)
                raw += rgb565.to_bytes(2, "big")
        hex_data = raw.hex()
        chunks = [hex_data[i:i + PHOTO_CHUNK_HEX_LEN]
                  for i in range(0, len(hex_data), PHOTO_CHUNK_HEX_LEN)]

        import os
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(chunks, f)
            chunks_path = f.name

        env = os.environ.copy()
        env["PYTHONPATH"] = "/home/arduino/pylib"
        script = (
            "import json, sys\n"
            "from arduino.app_utils import Bridge\n"
            "chunks = json.load(open(sys.argv[1]))\n"
            "Bridge.call('photo_chunk_start', '')\n"
            "for c in chunks:\n"
            "    Bridge.call('photo_chunk', c)\n"
            "Bridge.call('photo_render')\n"
        )
        try:
            subprocess.run(
                ["python3", "-c", script, chunks_path],
                env=env, timeout=20, capture_output=True,
            )
        finally:
            os.unlink(chunks_path)
        print(f"[photo] sent {len(chunks)}-chunk thumbnail ({PHOTO_THUMB_W}x{PHOTO_THUMB_H})")
    except Exception as e:
        print(f"[photo] thumbnail send failed: {e}")
# Follow-up turns already avoid re-triggering the wake word (converse_loop
# below re-opens the mic automatically after each reply) - but 5s gave the
# person almost no beat to start talking before arecord's fixed window
# closed, which showed up as "no response heard" (listen_and_converse
# returning False) dropping straight back to requiring "hey aubie" again for
# what should have been a normal conversational pause. Widened for more
# grace; still a fixed window, not true VAD-based silence detection.
RECORD_SECONDS = 8
MAX_CONVERSE_TURNS = 3
def listen_and_converse(speakers_hint="", objects_hint=""):
    """Record one follow-up response, send it (with room-context hints from the
    initial /greet call) to the rig, and play back the reply.

    Returns True if the user actually said something (so the conversation
    should continue), False if there was silence/an error (so the caller
    should stop looping and return to wake-word listening).
    """
    set_face_state("listening")
    print("[converse] Recording response...")
    try:
        subprocess.run(
            [
                "arecord",
                "-D", RECORD_DEVICE,
                "-f", "S16_LE",
                "-r", "16000",
                "-d", str(RECORD_SECONDS),
                RECORD_PATH,
            ],
            check=True,
            capture_output=True,
            timeout=RECORD_SECONDS + 10,
        )
    except subprocess.CalledProcessError as e:
        print(f"[error] arecord failed: {e.stderr.decode(errors='ignore')}")
        return False
    except subprocess.TimeoutExpired:
        print("[error] arecord timed out")
        return False

    # Best-effort: a fresh photo lets the rig answer "what is this" during
    # follow-up turns (see OBJECT_ID_RE in assistant_server.py). It only
    # costs the slow vision-model path there when the transcript actually
    # asks about something visual, so it's safe to always attach.
    have_photo = False
    try:
        with CAMERA_LOCK:
            subprocess.run(
                [
                    "fswebcam",
                    "-d", CAMERA_DEVICE,
                    "-r", "1920x1080",
                    "-S", "20",
                    "--no-banner",
                    CAPTURE_PATH,
                ],
                check=True,
                capture_output=True,
                timeout=15,
            )
        have_photo = True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(f"[converse] photo capture failed, continuing without it: {e}")

    set_face_state("thinking")
    print("[converse] Sending response to rig...")
    try:
        with open(RECORD_PATH, "rb") as f:
            files = {"audio": f.read()}
        if have_photo:
            with open(CAPTURE_PATH, "rb") as f:
                files["image"] = f.read()
        resp = _post_to_rig("/converse", files=files, data={"speakers": speakers_hint, "objects": objects_hint})
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[error] Request to rig failed: {e}")
        return False

    transcript = resp.headers.get("X-Transcript", "")
    reply_text = resp.headers.get("X-Reply-Text", "")
    used_vision = resp.headers.get("X-Used-Vision") == "1"
    print(f"[converse] You said: {transcript!r}, Rig replied: {reply_text!r}")

    with open(REPLY_PATH, "wb") as f:
        f.write(resp.content)

    if used_vision and have_photo:
        send_photo_thumbnail(CAPTURE_PATH)

    set_face_state("speaking")
    print("[converse] Playing reply...")
    try:
        bridge_call("face_talk", block=True)
    except Exception:
        pass
    subprocess.run(["pkill", "-f", "pw-play"], capture_output=True)
    try:
        subprocess.run(
            ["pw-play", REPLY_PATH],
            check=True,
            capture_output=True,
            timeout=_audio_timeout(REPLY_PATH),
        )
    except subprocess.CalledProcessError as e:
        print(f"[error] pw-play failed: {e.stderr.decode(errors='ignore')}")
    except subprocess.TimeoutExpired:
        print("[error] pw-play timed out")
    finally:
        try:
            bridge_call("face_idle")
        except Exception:
            pass
    # Let the EMEET fully release before the mic reopens for the next turn/wake-word listen
    time.sleep(1)

    return bool(transcript.strip())


def converse_loop(speakers_hint="", objects_hint=""):
    """Keep the conversation going for up to MAX_CONVERSE_TURNS follow-up
    exchanges, stopping early if the user goes quiet."""
    for turn in range(1, MAX_CONVERSE_TURNS + 1):
        print(f"[converse] Follow-up turn {turn}/{MAX_CONVERSE_TURNS}")
        if not listen_and_converse(speakers_hint, objects_hint):
            print("[converse] No response heard, returning to wake-word listening.")
            break


# ── Idle-screen greeting: a silent, low-frequency background scan so the
# kiosk touchscreen's idle face can recognize + greet someone by name with no
# "hey aubie" needed. Deliberately reuses the same /greet endpoint the real
# wake-word flow uses (no new server-side code) but never plays the returned
# audio or drives the physical face - it only writes a small status file the
# kiosk's browser page polls. Runs in its own thread so a slow /greet call
# (rig's vision/greeting generation can take several seconds) never blocks
# wake-word listening in main()'s tight loop. ────────────────────────────────
IDLE_SCAN_INTERVAL_S = 12
IDLE_CAPTURE_PATH = "/home/arduino/idle_scan.jpg"
IDLE_STATUS_PATH = Path("/home/arduino/kiosk/greet_status.json")

# ── Face state: a small file the kiosk page polls so the touchscreen can show
# whether Aubie is listening, thinking or speaking. Separate from
# greet_status.json (that one carries the greeting text and is polled slowly);
# this one is written on every transition and polled fast. main()'s existing
# WAKE_BUSY finally-block resets it to idle on every exit path, errors
# included, so no code path can leave the face stuck mid-conversation. The
# timestamp is belt-and-braces for the page.
FACE_STATE_PATH = Path("/home/arduino/kiosk/face_state.json")
_face_state = "idle"


def set_face_state(state):
    """Best-effort. Never raises - a face that doesn't update must never break
    the conversation."""
    global _face_state
    if state == _face_state:
        return
    _face_state = state
    try:
        FACE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        FACE_STATE_PATH.write_text(
            json.dumps({"state": state, "timestamp": _time.time()})
        )
    except OSError:
        pass



def _idle_scan_once():
    try:
        with CAMERA_LOCK:
            subprocess.run(
                [
                    "fswebcam",
                    "-d", CAMERA_DEVICE,
                    "-r", "1920x1080",
                    "-S", "20",
                    "--no-banner",
                    IDLE_CAPTURE_PATH,
                ],
                check=True,
                capture_output=True,
                timeout=15,
            )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return

    try:
        with open(IDLE_CAPTURE_PATH, "rb") as f:
            image_bytes = f.read()
        resp = _post_to_rig("/greet", files={"image": image_bytes})
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[idle-scan] rig request failed: {e}")
        return

    speakers = resp.headers.get("X-Speakers", "")
    greeting_text = resp.headers.get("X-Greeting", "")
    known = [
        s.strip().capitalize() for s in speakers.split(",")
        if s.strip() and s.strip().lower() not in ("unknown", "none")
    ]
    status = {
        "name": known[0] if known else None,
        "greeting": greeting_text if known else "",
        "timestamp": _time.time(),
    }
    try:
        IDLE_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        IDLE_STATUS_PATH.write_text(json.dumps(status))
    except OSError as e:
        print(f"[idle-scan] failed to write status file: {e}")


def idle_scan_loop():
    while True:
        time.sleep(IDLE_SCAN_INTERVAL_S)
        if CALL_ACTIVE_FLAG.exists() or WAKE_BUSY.is_set():
            continue
        # _idle_scan_once() acquires CAMERA_LOCK itself (blocking briefly is
        # fine here - this thread isn't time-critical the way wake-word
        # listening is), so a real capture in progress just delays this scan
        # rather than colliding with it.
        _idle_scan_once()


def main():
    global AUDIO_DEVICE, RECORD_DEVICE, PLAYBACK_DEVICE
    print(f"Loading model from {MODEL_PATH} ...")
    # threading.Thread(target=idle_scan_loop, daemon=True).start()  # 2026-09-25: photo greet evicts 14b
    last_interaction_time = _time.time()
    idle_fun_active = False
    while True:
        AUDIO_DEVICE, RECORD_DEVICE, PLAYBACK_DEVICE = detect_audio_devices()
        if AUDIO_DEVICE is None:
            print(f"[audio] EMEET not found, retrying in {AUDIO_POLL_SECONDS}s...")
            time.sleep(AUDIO_POLL_SECONDS)
            continue

        triggered = False
        call_paused = False
        with AudioImpulseRunner(MODEL_PATH) as runner:
            model_info = runner.init()
            print(
                "Model loaded:",
                model_info["project"]["name"],
                "-",
                model_info["project"]["owner"],
            )
            labels = model_info["model_parameters"]["labels"]
            print(f"Labels: {labels}")
            print(f"Listening for \'hey_aubie\'... (Ctrl+C to stop)")

            recent_scores = []
            TRIGGER_WINDOW = 3
            THRESHOLD = 0.99
            TRIGGER_THRESHOLD = 0.99
            COOLDOWN_SECONDS = 5
            last_trigger_time = 0
            TRIGGER_COUNT = 2

            for res, audio in runner.classifier(device_id=AUDIO_DEVICE):
                if CALL_ACTIVE_FLAG.exists():
                    call_paused = True
                    break  # release the mic for the duration of the call
                if not idle_fun_active and (_time.time() - last_interaction_time) > IDLE_FUN_TIMEOUT_S:
                    idle_fun_active = True
                    print(f"[idle] no interaction in {IDLE_FUN_TIMEOUT_S}s - laying down for some fun...")
                    dog_command("rest")
                    dog_command("play_pong", on=True)
                label_scores = res["result"]["classification"]
                hey_score = label_scores.get("hey_aubie", 0)
                recent_scores.append(hey_score)
                if len(recent_scores) > TRIGGER_WINDOW:
                    recent_scores.pop(0)
                above_threshold = sum(1 for s in recent_scores if s >= TRIGGER_THRESHOLD)
                now = _time.time()
                in_cooldown = (now - last_trigger_time) < COOLDOWN_SECONDS
                if above_threshold >= TRIGGER_COUNT and not in_cooldown:
                    last_trigger_time = now
                    recent_scores.clear()
                    triggered = True
                    break  # release the mic before recording

        if call_paused:
            print("[call] video/audio call active, pausing wake-word listening...")
            while CALL_ACTIVE_FLAG.exists():
                time.sleep(1)
            print("[call] call ended, resuming wake-word listening.")
            last_interaction_time = _time.time()
            continue

        if triggered:
            if idle_fun_active:
                idle_fun_active = False
                print("[idle] wake word during idle fun - stopping Pong, standing up")
                dog_command("play_pong", on=False)
                dog_command("stand")
            WAKE_BUSY.set()
            try:
                result = capture_and_greet()
                if result is not None:
                    speakers_hint, objects_hint = result
                    converse_loop(speakers_hint, objects_hint)
            finally:
                WAKE_BUSY.clear()
                set_face_state("idle")
            last_interaction_time = _time.time()

if __name__ == "__main__":
    main()

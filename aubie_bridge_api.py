"""
NOT YET DEPLOYED - written 2026-09-13, prepared for the next time the UNO Q
board (100.66.110.65) is reachable. See ERROR_LEDGER.md's 2026-09-13 entry
for the full incident this is fixing and what is still unverified.

Target path on the board: ~/aubie_bridge_api.py, run as its own systemd unit
(aubie-bridge-api.service, analogous to aubie-listen.service) - NOT an
arduino-app-cli "app" (no sketch.yaml/Docker packaging). It reuses
aubie_listen.py's already-proven subprocess bridge_call() pattern (plain
`python3 -c "from arduino.app_utils import Bridge; ..."` with
PYTHONPATH=/home/arduino/pylib`), which face_talk/face-text/wave already
demonstrate works from an ordinary systemd process outside any app-lab
container - not the old aubie_dog.py's in-process `from arduino.app_utils
import Bridge` + `App.run()` (that ran inside the retired spotmicro_dog
app's own Docker container, a different, heavier deployment model this
does not attempt to reproduce).

--------------------------------------------------------------------------
What this replaces, and what is still an open question
--------------------------------------------------------------------------
Restores a network-reachable HTTP surface for the pieces of the retired
spotmicro_dog app (~/spotmicro_dog/python/aubie_dog.py, port 8420, dead
since the spotmicro_dog -> aubie-tutor migration) that assistant_server.py
(running on the rig, not the board) has no other way to reach:

  - POST /dog/command  -> movement + flower_explosion + face_text + show_image
  - GET  /snapshot      -> one-shot camera JPEG (person-follow)
  - POST /play_audio    -> WAV bytes -> pw-play (the rig's "Say" box / /speak)

Deliberately NOT ported: /call/stream (the live video/audio call websocket)
and the sensor/diagnostic actions (read_imu, sonar, lidar, face_diag,
diag_info, get_servo_angles, test_mic/speakers/lidar, face_config,
calibration_mode, lean, princess_mode, flashlight). None of those are
called by any current rig-side code path (checked assistant_server.py's
call_dog_command() call sites and phone_ui.py's /proxy/dog panel - the
panel's flashlight_on/off, princess_mode, set_face, custom_face, and "say"
buttons send action names/fields that never matched the old aubie_dog.py's
schema either, even before 8420 died - pre-existing dead UI wiring,
unrelated to this incident, not touched here). Porting the value-returning
diagnostics would also need a different bridge_call() (this file's, like
aubie_listen.py's, discards subprocess stdout - fine for the fire-and-
forget actions above, not enough to relay an MCU reply back to a caller).

UNVERIFIED - the real open question this can't resolve without the board:
whether the CURRENT aubie-tutor sketch (sketch/sketch.ino on the board,
never pulled into this repo - see CLAUDE.md's "Edge devices are disposable"
audit) still implements the "stand"/"sit"/"rest"/"walk_forward"/
"turn_left"/"turn_right"/"set_servo"/"flower_explosion"/"show_image"/
"face_text" Bridge RPC methods at all. ERROR_LEDGER.md's 2026-09-11 entry
only confirms face_talk/face-text/wave as live-tested against the current
firmware; the rest are inherited from the OLD spotmicro_dog sketch and the
audit note that aubie-tutor's sketch only explicitly documents porting the
PCA9685 driver plus wave()/wave_diag()/hub_diag() RPCs. This file passes
those method names through unchanged (same as the code it replaces) but
does not and cannot confirm the MCU still answers to them - that has to be
tested live, method by method, once the board is reachable again. If any
come back "unknown command" (or the MCU doesn't process them), that is a
firmware gap, not a transport bug, and needs its own scoping (re-adding the
RPC handler to the sketch) - do not paper over it here.

Deploy steps (once the board is back):
  scp aubie_bridge_api.py arduino@100.66.110.65:~/
  ssh arduino@100.66.110.65 -- sudo systemctl edit --force --full aubie-bridge-api.service
    # ExecStart=/usr/bin/python3 /home/arduino/aubie_bridge_api.py
    # Environment=XDG_RUNTIME_DIR=/run/user/1000
  ssh arduino@100.66.110.65 -- sudo systemctl enable --now aubie-bridge-api.service
Then update assistant_server.py's AUBIE_BRIDGE_PORT (and phone_ui.py's
AUBIE_URL) if the port below is changed, and pull this file into
_remote/board/ via tools/pull-board-files once it's confirmed live so the
rig has an authoritative copy of what's actually running.
--------------------------------------------------------------------------
"""

import os
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Literal, Optional

os.environ.setdefault("XDG_RUNTIME_DIR", "/run/user/1000")

import cv2
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

app = FastAPI(title="Aubie Bridge API")

# Port 8420 is the dead spotmicro_dog port this is replacing - deliberately
# NOT reused, so a stale caller that still points at 8420 fails loudly
# (connection refused) instead of quietly landing on a service it was never
# verified against.
BRIDGE_API_PORT = 8421

CAMERA_INDEX = 0

# FastAPI runs each sync `def` route in its own threadpool thread, so
# concurrent requests (e.g. a movement command arriving while /snapshot is
# mid-poll from the person-follow loop) would otherwise mean two threads
# calling Bridge.call() on the shared RPC link at once - confirmed
# 2026-08-17 (see aubie_dog.py's original header comment) to wedge the link.
_bridge_lock = threading.Lock()


def bridge_call(method: str, *args: str) -> None:
    """Same subprocess-based call aubie_listen.py's bridge_call() uses
    (proven working for face_talk/face-text/wave against the current
    firmware) - not aubie_dog.py's old in-process `Bridge.call()`, which
    depended on that process's own App.run()/Docker packaging. Serialized
    with _bridge_lock since, unlike aubie_listen.py (single-threaded for
    every Bridge call site), this process handles concurrent HTTP requests.

    Generalized to *args (aubie_listen.py's own copy only ever needed a
    single string arg) because set_servo needs channel and angle passed as
    two separate Bridge.call() parameters, the same way the old aubie_dog.py
    called `Bridge.call("set_servo", channel, angle)` - a single
    comma-joined string would be a guess about how the MCU parses it, with
    no evidence either way.
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = "/home/arduino/pylib"
    cmd = [
        "python3", "-c",
        "import sys; from arduino.app_utils import Bridge; Bridge.call(sys.argv[1], *sys.argv[2:])",
        method, *args,
    ]
    with _bridge_lock:
        try:
            subprocess.run(cmd, env=env, timeout=5, capture_output=True)
        except Exception as e:
            print(f"[bridge] {method} failed: {e}")


@app.get("/snapshot")
def snapshot():
    """One-shot JPEG grab, open/read/release immediately - same brief-open
    pattern aubie_listen.py's fswebcam captures use, so a person-follow poll
    from the rig doesn't hold the camera open between polls. Used by
    assistant_server.py's fetch_aubie_snapshot() (person-follow).

    NOTE: does not coordinate with aubie_listen.py's own CAMERA_LOCK -
    that lock only protects against aubie_listen.py's own two capture paths
    (wake-word + idle-scan) colliding with each other; a /snapshot poll
    landing at the same instant as one of those is a separate, pre-existing
    gap this file doesn't attempt to close (most UVC webcams, including the
    EMEET, only support one exclusive stream consumer - a genuine collision
    here would surface as a failed capture on one side, not a crash).
    """
    cap = cv2.VideoCapture(CAMERA_INDEX)
    try:
        if not cap.isOpened():
            raise HTTPException(503, "camera not available")
        ok, frame = cap.read()
        if not ok:
            raise HTTPException(503, "failed to capture frame")
        ok2, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok2:
            raise HTTPException(500, "failed to encode frame")
        return Response(content=jpg.tobytes(), media_type="image/jpeg")
    finally:
        cap.release()


@app.post("/play_audio")
async def play_audio(request: Request):
    """Plays raw WAV bytes (the request body) via pw-play - NOT aplay
    against a raw ALSA device the way the old (pre-EMEET-audio-fix)
    aubie_dog.py did. The EMEET is capture-only (confirmed via `aplay -l` -
    it has zero playback subdevices); real speaker output on this board is
    the touchscreen's own HDMI audio, reachable only through the PipeWire
    graph (see aubie_listen.py's PLAYBACK_DEVICE_HDMI / capture_and_greet()
    comments) - `aplay -D plughw:0,0` here would silently target a device
    with no speaker at all. Matches capture_and_greet()'s own
    `pw-play <path>` call exactly (no explicit device flag - PipeWire routes
    to its configured default sink itself).

    Does not coordinate with aubie_listen.py's own pw-play calls (wake-word
    greet/converse playback) - a /speak request landing mid-greeting could
    still collide, same pre-existing gap noted in assistant_server.py's
    push_audio_to_aubie() docstring. Not solved here; out of scope for this
    fix.
    """
    wav_bytes = await request.body()
    if not wav_bytes:
        raise HTTPException(400, "empty request body")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(wav_bytes)
        tmp_path = f.name

    try:
        subprocess.run(["pkill", "-f", "pw-play"], capture_output=True)
        proc = subprocess.run(
            ["pw-play", tmp_path],
            capture_output=True,
            timeout=30,
        )
        if proc.returncode != 0:
            raise HTTPException(502, f"pw-play failed: {proc.stderr.decode(errors='ignore')}")
        return {"ok": True}
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# Only the actions assistant_server.py's call_dog_command() actually sends
# (checked its call sites directly) - see the module docstring for what was
# deliberately left out and why.
Action = Literal[
    "stand", "sit", "rest", "walk_forward", "turn_left", "turn_right",
    "set_servo", "face_text", "flower_explosion", "show_image",
]

# Must match SHOW_IMAGE_W/H in assistant_server.py and PHOTO_W/H in
# sketch/face.ino exactly - the MCU just fills a fixed-size buffer.
SHOW_IMAGE_W, SHOW_IMAGE_H = 64, 48
SHOW_IMAGE_BYTES = SHOW_IMAGE_W * SHOW_IMAGE_H * 2  # RGB565 = 2 bytes/pixel
# A single Bridge RPC call tops out around ~235 bytes of String payload.
PHOTO_CHUNK_HEX_LEN = 192  # 96 raw bytes/chunk


class DogCommand(BaseModel):
    action: Action
    channel: Optional[int] = None    # required for set_servo (0-11)
    angle: Optional[int] = None      # required for set_servo (0-180)
    text: Optional[str] = None       # required for face_text
    image_hex: Optional[str] = None  # required for show_image


@app.post("/dog/command")
def dog_command(cmd: DogCommand):
    if cmd.action in ("stand", "sit", "rest", "walk_forward", "turn_left", "turn_right"):
        bridge_call(cmd.action)
        return {"ok": True}

    if cmd.action == "set_servo":
        if cmd.channel is None or cmd.angle is None:
            raise HTTPException(400, "set_servo requires channel and angle")
        bridge_call("set_servo", str(cmd.channel), str(cmd.angle))
        return {"ok": True}

    if cmd.action == "face_text":
        if cmd.text is None:
            raise HTTPException(400, "face_text requires text")
        bridge_call("face-text", cmd.text)
        return {"ok": True}

    if cmd.action == "flower_explosion":
        bridge_call("flower_explosion")
        return {"ok": True}

    if cmd.action == "show_image":
        if not cmd.image_hex:
            raise HTTPException(400, "show_image requires image_hex")
        if len(cmd.image_hex) != SHOW_IMAGE_BYTES * 2:
            raise HTTPException(
                400,
                f"image_hex must be {SHOW_IMAGE_BYTES * 2} hex chars "
                f"({SHOW_IMAGE_W}x{SHOW_IMAGE_H} RGB565), got {len(cmd.image_hex)}",
            )
        bridge_call("photo_chunk_start", "")
        for i in range(0, len(cmd.image_hex), PHOTO_CHUNK_HEX_LEN):
            bridge_call("photo_chunk", cmd.image_hex[i:i + PHOTO_CHUNK_HEX_LEN])
        bridge_call("photo_render", "")
        return {"ok": True}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=BRIDGE_API_PORT, log_level="info")

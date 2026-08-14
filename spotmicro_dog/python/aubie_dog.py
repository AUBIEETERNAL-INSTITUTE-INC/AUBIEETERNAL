# -----------------------------------------------------------------------
# SpotMicro dog - Linux/Python side (Qualcomm QRB2210, Debian).
#
# Talks to the MCU sketch (sketch/sketch.ino) over Arduino's Bridge RPC and
# exposes POST /dog/command so Aubie's assistant_server.py can trigger
# movement from recognized voice intents.
#
# Bridge.call() is synchronous and blocks the calling thread until the MCU
# replies, so it's called directly from FastAPI request handlers - each
# request just waits for its own Bridge round trip, no separate queue needed.
# App.run() has to be running for this process to behave as a proper UNO Q
# app, so it runs in a background thread while uvicorn owns the main thread.
# -----------------------------------------------------------------------

import asyncio
import logging
import subprocess
import threading
import time
from pathlib import Path
from typing import Literal, Optional

import cv2
import uvicorn
from arduino.app_utils import App, Bridge
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aubie_dog")

api = FastAPI(title="Aubie SpotMicro Dog Control")


@api.get("/snapshot")
def snapshot():
    """
    One-shot JPEG grab from the camera - open/read/release immediately,
    same brief-open pattern aubie_listen.py's fswebcam captures already use
    successfully alongside the persistent capture in /call/stream below.
    Used by the rig's follow-a-person loop to see where the target is
    without needing a live /call/stream video call running.
    """
    cap = cv2.VideoCapture(0)
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

# ---- Live video/audio call (phone <-> Aubie's camera/mic/speaker) ----
# Relayed through aubieeternal's /call/ws (not peer-to-peer WebRTC - aubie
# has no public IP and neither machine has aiortc/STUN/TURN set up). A
# single websocket here carries both directions: JPEG video frames and
# PCM16 audio chunks multiplexed with a 1-byte type tag ('V'/'A'), plus
# incoming 'A'-tagged audio from the phone's mic played out the EMEET
# speaker. See ~/spotmicro_dog/python/aubie_dog.py in the AUBIEETERNAL repo
# notes for the matching relay/UI pieces.
CALL_AUDIO_RATE = 16000
CALL_AUDIO_CHUNK = 1600  # 100ms @ 16kHz mono 16-bit -> 3200 bytes/chunk
CALL_VIDEO_FPS = 8
CALL_JPEG_QUALITY = 60
CALL_VIDEO_WIDTH = 640
CALL_VIDEO_HEIGHT = 480

# ALSA device for the EMEET mic/speaker (card 0, device 0 - confirmed stable
# via `arecord -l`/`aplay -l` inside the container). PyAudio/PortAudio's own
# ALSA enumeration reports 0 input channels for this device (a PortAudio
# default sample-rate-probe quirk with this USB audio class device) even
# though raw `arecord`/`aplay` capture/play it fine - so audio I/O here goes
# straight through those CLI tools via subprocess pipes instead of PyAudio.
CALL_ALSA_DEVICE = "plughw:0,0"

# ~/aubie_listen.py (the wake-word listener, host-level) holds the EMEET mic
# open continuously for wake-word detection - a hard conflict with this
# route's own capture, not just an occasional collision. It polls for this
# same file (bind-mounted host ~/spotmicro_dog <-> container /app) and
# releases the mic while it exists, so touch/remove it around the call.
CALL_ACTIVE_FLAG = Path("/app/.call_active")
CALL_MIC_RELEASE_GRACE_S = 1.5

_call_active = False


@api.websocket("/call/stream")
async def call_stream(ws: WebSocket):
    global _call_active
    if _call_active:
        await ws.close(code=4409, reason="call already in progress")
        return
    _call_active = True
    await ws.accept()
    CALL_ACTIVE_FLAG.touch()
    await asyncio.sleep(CALL_MIC_RELEASE_GRACE_S)  # let aubie_listen.py notice and release the mic

    loop = asyncio.get_event_loop()
    send_queue: asyncio.Queue = asyncio.Queue(maxsize=32)
    stop_event = threading.Event()
    cap = video_thread = writer_task = None
    record_proc = play_proc = audio_capture_thread = None

    def _safe_put(item):
        try:
            send_queue.put_nowait(item)
        except asyncio.QueueFull:
            pass  # drop rather than let a slow network path build up latency

    def audio_capture_loop():
        chunk_bytes = CALL_AUDIO_CHUNK * 2  # 16-bit mono
        while not stop_event.is_set():
            data = record_proc.stdout.read(chunk_bytes)
            if not data:
                break  # arecord exited (device error / stream torn down)
            loop.call_soon_threadsafe(_safe_put, (b"A", data))

    def video_loop():
        interval = 1.0 / CALL_VIDEO_FPS
        while not stop_event.is_set():
            start = time.monotonic()
            ok, frame = cap.read()
            if ok:
                ok2, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, CALL_JPEG_QUALITY])
                if ok2:
                    loop.call_soon_threadsafe(_safe_put, (b"V", jpg.tobytes()))
            elapsed = time.monotonic() - start
            time.sleep(max(0.0, interval - elapsed))

    # send_bytes must only ever be called from this one task - Starlette's
    # WebSocket.send() isn't safe under concurrent calls from multiple tasks,
    # so video and audio share this single writer via send_queue instead of
    # each running their own independent send loop.
    async def writer():
        while True:
            tag, payload = await send_queue.get()
            await ws.send_bytes(tag + payload)

    try:
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CALL_VIDEO_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CALL_VIDEO_HEIGHT)
        if not cap.isOpened():
            raise RuntimeError("could not open camera")

        record_proc = subprocess.Popen(
            ["arecord", "-D", CALL_ALSA_DEVICE, "-f", "S16_LE", "-r", str(CALL_AUDIO_RATE),
             "-c", "1", "-t", "raw"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        play_proc = subprocess.Popen(
            ["aplay", "-D", CALL_ALSA_DEVICE, "-f", "S16_LE", "-r", str(CALL_AUDIO_RATE),
             "-c", "1", "-t", "raw"],
            stdin=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )

        video_thread = threading.Thread(target=video_loop, daemon=True)
        video_thread.start()
        audio_capture_thread = threading.Thread(target=audio_capture_loop, daemon=True)
        audio_capture_thread.start()
        writer_task = asyncio.create_task(writer())

        while True:
            data = await ws.receive_bytes()
            if data[:1] == b"A" and play_proc.stdin:
                try:
                    await asyncio.to_thread(play_proc.stdin.write, data[1:])
                except (BrokenPipeError, OSError):
                    pass  # aplay already exited (e.g. mid-teardown race) - harmless
    except (WebSocketDisconnect, RuntimeError):
        # Starlette raises a plain RuntimeError ("WebSocket is not connected")
        # rather than WebSocketDisconnect on some disconnect races - both mean
        # the same thing here: the client is gone, tear down normally.
        pass
    except Exception:
        logger.exception("call_stream error")
    finally:
        stop_event.set()
        if writer_task:
            writer_task.cancel()
        if video_thread:
            video_thread.join(timeout=2)
        for proc in (record_proc, play_proc):
            if proc:
                if proc.stdin:
                    # Close explicitly (guarded) rather than leaving it to GC -
                    # an unguarded finalizer flush() on a pipe whose peer
                    # already exited logs a noisy but harmless BrokenPipeError.
                    try:
                        proc.stdin.close()
                    except (BrokenPipeError, OSError):
                        pass
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
        if audio_capture_thread:
            audio_capture_thread.join(timeout=2)
        if cap:
            cap.release()
        CALL_ACTIVE_FLAG.unlink(missing_ok=True)
        _call_active = False

Action = Literal[
    "stand", "sit", "rest", "lean", "walk_forward", "turn_left", "turn_right",
    "set_servo", "read_imu", "imu_read",
    "calibration_mode", "read_sonar",
    "face_talk", "face_idle", "face_text",
    "face_config", "flashlight", "get_servo_angles", "face_diag", "princess_mode",
    "flower_explosion", "show_image",
]

# Must match PHOTO_W/PHOTO_H in sketch/face.ino exactly - the MCU just fills
# a fixed-size buffer, it doesn't know the image dimensions. Same convention
# as aubie_listen.py's wake-word photo thumbnail (PHOTO_THUMB_W/H there).
SHOW_IMAGE_W, SHOW_IMAGE_H = 64, 48
SHOW_IMAGE_BYTES = SHOW_IMAGE_W * SHOW_IMAGE_H * 2  # RGB565 = 2 bytes/pixel
# A single Bridge RPC call tops out around ~235 bytes of String payload (see
# aubie_listen.py's PHOTO_CHUNK_HEX_LEN comment) - stay well under that.
PHOTO_CHUNK_HEX_LEN = 192  # 96 raw bytes/chunk

FACE_STATE_NAMES = {0: "IDLE", 1: "TOUCHED_MODE", 2: "PERVERT_MODE"}
EYE_SHAPE_NAMES = {0: "round", 1: "narrow", 2: "wide", 3: "angry", 4: "sad", 5: "dog_eyes"}
MOUTH_SHAPE_NAMES = {0: "smile", 1: "flat", 2: "frown", 3: "open", 4: "dog_mouth"}

# Maps face_config's eye_shape/mouth_shape strings to the int enums sketch/
# face.ino's EyeShape/MouthShape expect - keep in sync if those enums change.
EYE_SHAPES = {"round": 0, "narrow": 1, "wide": 2, "angry": 3, "sad": 4, "dog_eyes": 5, "crazy": 6, "stoned": 7}
MOUTH_SHAPES = {"smile": 0, "flat": 1, "frown": 2, "open": 3, "dog_mouth": 4, "crazy": 5, "stoned": 6}

DEFAULT_FACE_COLOR = 0xFFFF  # white in RGB565


def _normalize_shape_key(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def hex_to_rgb565(hex_color: str) -> int:
    h = hex_color.lstrip("#")
    if len(h) != 6:
        raise HTTPException(400, f"invalid color {hex_color!r}, expected #RRGGBB")
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        raise HTTPException(400, f"invalid color {hex_color!r}, expected #RRGGBB")
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


class DogCommand(BaseModel):
    action: Action
    channel: Optional[int] = None   # required for set_servo (0-11)
    angle: Optional[int] = None     # required for set_servo (0-180)
    sensor_id: Optional[int] = None  # required for read_sonar (0=front-left, 1=front-right, 2=back)
    text: Optional[str] = None      # required for face_text (caption shown under the face, ~20 chars)
    on: Optional[bool] = None       # required for calibration_mode, flashlight
    eye_shape: Optional[str] = None     # required for face_config: round/narrow/wide/angry/sad/dog_eyes
    mouth_shape: Optional[str] = None   # required for face_config: smile/flat/frown/open/dog_mouth
    eye_color: Optional[str] = None     # optional for face_config, hex "#RRGGBB", default white
    mouth_color: Optional[str] = None   # optional for face_config, hex "#RRGGBB", default white
    image_hex: Optional[str] = None     # required for show_image: RGB565 bytes, hex-encoded, exactly SHOW_IMAGE_BYTES*2 chars
    x: Optional[int] = None             # required for lean: -100..100, left(-)/right(+)
    y: Optional[int] = None             # required for lean: -100..100, back(-)/forward(+)


def parse_imu_csv(raw: str) -> dict:
    ax, ay, az, gx, gy, gz = (float(v) for v in raw.split(","))
    return {
        "accel_g": {"x": ax, "y": ay, "z": az},
        "gyro_dps": {"x": gx, "y": gy, "z": gz},
    }


def parse_imu_read_csv(raw: str) -> dict:
    pitch, roll, ax, ay, az = (float(v) for v in raw.split(","))
    return {
        "pitch_deg": pitch,
        "roll_deg": roll,
        "accel_g": {"x": ax, "y": ay, "z": az},
    }


@api.post("/dog/command")
def dog_command(cmd: DogCommand):
    try:
        if cmd.action == "stand":
            ok = Bridge.call("stand")
            return {"ok": bool(ok)}

        if cmd.action == "sit":
            ok = Bridge.call("sit")
            return {"ok": bool(ok)}

        if cmd.action == "rest":
            ok = Bridge.call("rest")
            return {"ok": bool(ok)}

        if cmd.action == "lean":
            if cmd.x is None or cmd.y is None:
                raise HTTPException(400, "lean requires x and y")
            ok = Bridge.call("lean", cmd.x, cmd.y)
            return {"ok": bool(ok)}

        if cmd.action == "walk_forward":
            ok = Bridge.call("walk_forward")
            return {"ok": bool(ok)}

        if cmd.action == "turn_left":
            ok = Bridge.call("turn_left")
            return {"ok": bool(ok)}

        if cmd.action == "turn_right":
            ok = Bridge.call("turn_right")
            return {"ok": bool(ok)}

        if cmd.action == "set_servo":
            if cmd.channel is None or cmd.angle is None:
                raise HTTPException(400, "set_servo requires channel and angle")
            ok = Bridge.call("set_servo", cmd.channel, cmd.angle)
            return {"ok": bool(ok)}

        if cmd.action == "read_imu":
            raw = Bridge.call("read_imu")
            return {"ok": True, "imu": parse_imu_csv(raw)}

        if cmd.action == "imu_read":
            raw = Bridge.call("imu_read")
            return {"ok": True, "imu": parse_imu_read_csv(raw)}

        if cmd.action == "calibration_mode":
            if cmd.on is None:
                raise HTTPException(400, "calibration_mode requires on")
            ok = Bridge.call("calibration_mode", cmd.on)
            return {"ok": bool(ok)}

        if cmd.action == "face_talk":
            # face_talk/face_idle_cmd on the MCU side both take a String
            # param (unused) - Bridge has no default-param resolution, so a
            # zero-arg call fails with "Missing call parameters".
            Bridge.call("face_talk", "")
            return {"ok": True}
        if cmd.action == "face_idle":
            Bridge.call("face_idle", "")
            return {"ok": True}
        if cmd.action == "face_text":
            if cmd.text is None:
                raise HTTPException(400, "face_text requires text")
            Bridge.call("face-text", cmd.text)
            return {"ok": True}
        if cmd.action == "read_sonar":
            if cmd.sensor_id is None:
                raise HTTPException(400, "read_sonar requires sensor_id")
            distance_cm = Bridge.call("read_sonar", cmd.sensor_id)
            return {"ok": True, "distance_cm": distance_cm}

        if cmd.action == "face_config":
            if cmd.eye_shape is None or cmd.mouth_shape is None:
                raise HTTPException(400, "face_config requires eye_shape and mouth_shape")
            eye_key = _normalize_shape_key(cmd.eye_shape)
            mouth_key = _normalize_shape_key(cmd.mouth_shape)
            if eye_key not in EYE_SHAPES:
                raise HTTPException(400, f"unknown eye_shape {cmd.eye_shape!r}, expected one of {sorted(EYE_SHAPES)}")
            if mouth_key not in MOUTH_SHAPES:
                raise HTTPException(400, f"unknown mouth_shape {cmd.mouth_shape!r}, expected one of {sorted(MOUTH_SHAPES)}")
            eye_color = hex_to_rgb565(cmd.eye_color) if cmd.eye_color else DEFAULT_FACE_COLOR
            mouth_color = hex_to_rgb565(cmd.mouth_color) if cmd.mouth_color else DEFAULT_FACE_COLOR
            ok = Bridge.call("face_config", EYE_SHAPES[eye_key], MOUTH_SHAPES[mouth_key], eye_color, mouth_color)
            return {"ok": bool(ok)}

        if cmd.action == "flashlight":
            if cmd.on is None:
                raise HTTPException(400, "flashlight requires on")
            ok = Bridge.call("flashlight", cmd.on)
            return {"ok": bool(ok)}

        if cmd.action == "get_servo_angles":
            raw = Bridge.call("get_servo_angles")
            angles = [int(v) for v in raw.split(",")]
            return {"ok": True, "angles": angles}

        if cmd.action == "princess_mode":
            if cmd.on is None:
                raise HTTPException(400, "princess_mode requires on")
            ok = Bridge.call("princess_mode", cmd.on)
            return {"ok": bool(ok)}

        if cmd.action == "flower_explosion":
            ok = Bridge.call("flower_explosion")
            return {"ok": bool(ok)}

        if cmd.action == "show_image":
            if not cmd.image_hex:
                raise HTTPException(400, "show_image requires image_hex")
            if len(cmd.image_hex) != SHOW_IMAGE_BYTES * 2:
                raise HTTPException(
                    400,
                    f"image_hex must be {SHOW_IMAGE_BYTES * 2} hex chars "
                    f"({SHOW_IMAGE_W}x{SHOW_IMAGE_H} RGB565), got {len(cmd.image_hex)}",
                )
            # Same chunked start/chunk/render sequence aubie_listen.py uses for
            # the wake-word photo thumbnail (see sketch/face.ino's
            # photo_chunk_start/photo_chunk/photo_render) - just called
            # in-process here since aubie_dog.py already has a live Bridge
            # connection, no subprocess needed.
            Bridge.call("photo_chunk_start", "")
            for i in range(0, len(cmd.image_hex), PHOTO_CHUNK_HEX_LEN):
                Bridge.call("photo_chunk", cmd.image_hex[i:i + PHOTO_CHUNK_HEX_LEN])
            ok = Bridge.call("photo_render")
            return {"ok": bool(ok)}

        if cmd.action == "face_diag":
            raw = Bridge.call("face_diag")
            face_state, eye_shape, mouth_shape, is_talking, calib, flash, text_overlay, ms = raw.split(",")
            return {
                "ok": True,
                "face_state": FACE_STATE_NAMES.get(int(face_state), face_state),
                "eye_shape": EYE_SHAPE_NAMES.get(int(eye_shape), eye_shape),
                "mouth_shape": MOUTH_SHAPE_NAMES.get(int(mouth_shape), mouth_shape),
                "is_talking": bool(int(is_talking)),
                "calibration_mode": bool(int(calib)),
                "flashlight": bool(int(flash)),
                "text_overlay_active": bool(int(text_overlay)),
                "millis": int(ms),
            }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Bridge call failed for action=%s", cmd.action)
        raise HTTPException(502, f"MCU bridge error: {exc}") from exc


def run_api():
    uvicorn.run(api, host="0.0.0.0", port=8420, log_level="info")

def main():
    threading.Thread(target=run_api, daemon=True).start()
    App.run()

if __name__ == "__main__":
    main()

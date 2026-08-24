# -----------------------------------------------------------------------
# >>> LIVE, DEPLOYED COPY <<< On the robot this is
# ~/spotmicro_dog/python/aubie_dog.py - do NOT confuse with
# ~/ArduinoApps/spotmicro_dog/python/ on the robot, a stale unregistered
# leftover from initial app setup (see sketch/sketch.ino's matching note).
# -----------------------------------------------------------------------
# SpotMicro dog - Linux/Python side (Qualcomm QRB2210, Debian).
#
# Talks to the MCU sketch (sketch/sketch.ino) over Arduino's Bridge RPC and
# exposes POST /dog/command so Aubie's assistant_server.py can trigger
# movement from recognized voice intents.
#
# Bridge.call() is synchronous and blocks the calling thread until the MCU
# replies. FastAPI runs each sync `def` route in its own threadpool thread,
# so concurrent requests (e.g. the phone UI's 3D Sensor Dashboard, which
# fires 5 sensor reads at once) previously meant multiple threads calling
# Bridge.call() on the shared RPC link at the same time - confirmed
# 2026-08-17 to wedge the link and corrupt an unrelated call's response
# (read_imu came back with a frozen stale value after a concurrent burst).
# Every call site below goes through bridge_call(), which wraps Bridge.call()
# in a lock so only one request is ever in flight on the wire at a time.
# App.run() has to be running for this process to behave as a proper UNO Q
# app, so it runs in a background thread while uvicorn owns the main thread.
# -----------------------------------------------------------------------

import asyncio
import logging
import math
import subprocess
import threading
import time
from pathlib import Path
from typing import Literal, Optional

import cv2
import uvicorn
from arduino.app_utils import App, Bridge
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aubie_dog")

api = FastAPI(title="Aubie SpotMicro Dog Control")

# Serializes every bridge_call() - see the header comment above for why.
_bridge_lock = threading.Lock()


def bridge_call(*args):
    with _bridge_lock:
        return Bridge.call(*args)


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


@api.post("/play_audio")
async def play_audio(request: Request):
    """
    Plays raw WAV bytes (the request body) out the EMEET speaker via aplay -
    same ALSA device (plughw, not the raw hw device - see CALL_ALSA_DEVICE's
    comment) the live call path already uses successfully. Lets the rig push
    speech to Aubie on demand (e.g. the phone UI's "speak" box) without
    needing a live /call/stream call running, the same way /snapshot lets it
    pull a photo on demand. The blocking aplay call runs via asyncio.to_thread
    so it doesn't stall the event loop for however long playback takes.
    """
    wav_bytes = await request.body()
    if not wav_bytes:
        raise HTTPException(400, "empty request body")

    def _play():
        return subprocess.run(
            ["aplay", "-D", CALL_ALSA_DEVICE],
            input=wav_bytes,
            capture_output=True,
        )

    proc = await asyncio.to_thread(_play)
    if proc.returncode != 0:
        raise HTTPException(502, f"aplay failed: {proc.stderr.decode(errors='ignore')}")
    return {"ok": True}

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
    "calibration_mode", "read_sonar", "sonar_forward", "sonar_backward",
    "face_talk", "face_idle", "face_text",
    "face_config", "flashlight", "get_servo_angles", "face_diag", "diag_info", "princess_mode",
    "flower_explosion", "show_image", "play_pong", "test_speakers", "test_mic",
    "test_lidar", "lidar_scan",
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


def _finite(v: float) -> float:
    """NaN/inf isn't valid JSON (json.dumps raises ValueError on it) - the
    MCU's tilt-from-gravity math (atan2/sqrt in imu()) can produce one on a
    bad accel reading. Swallow it to 0.0 rather than 500ing the whole
    request - a single bad IMU sample isn't worth crashing the phone UI's
    every-2s tilt poll over (confirmed live, 2026-08-14 - the poll's
    ValueError: Out of range float values are not JSON compliant: nan)."""
    return v if math.isfinite(v) else 0.0


def parse_imu_csv(raw: str) -> dict:
    ax, ay, az, gx, gy, gz = (_finite(float(v)) for v in raw.split(","))
    return {
        "accel_g": {"x": ax, "y": ay, "z": az},
        "gyro_dps": {"x": gx, "y": gy, "z": gz},
    }


def parse_imu_read_csv(raw: str) -> dict:
    pitch, roll, ax, ay, az = (_finite(float(v)) for v in raw.split(","))
    return {
        "pitch_deg": pitch,
        "roll_deg": roll,
        "accel_g": {"x": ax, "y": ay, "z": az},
    }


@api.post("/dog/command")
def dog_command(cmd: DogCommand):
    try:
        if cmd.action == "stand":
            ok = bridge_call("stand")
            return {"ok": bool(ok)}

        if cmd.action == "sit":
            ok = bridge_call("sit")
            return {"ok": bool(ok)}

        if cmd.action == "rest":
            ok = bridge_call("rest")
            return {"ok": bool(ok)}

        if cmd.action == "lean":
            if cmd.x is None or cmd.y is None:
                raise HTTPException(400, "lean requires x and y")
            ok = bridge_call("lean", cmd.x, cmd.y)
            return {"ok": bool(ok)}

        if cmd.action == "walk_forward":
            ok = bridge_call("walk_forward")
            return {"ok": bool(ok)}

        if cmd.action == "turn_left":
            ok = bridge_call("turn_left")
            return {"ok": bool(ok)}

        if cmd.action == "turn_right":
            ok = bridge_call("turn_right")
            return {"ok": bool(ok)}

        if cmd.action == "set_servo":
            if cmd.channel is None or cmd.angle is None:
                raise HTTPException(400, "set_servo requires channel and angle")
            ok = bridge_call("set_servo", cmd.channel, cmd.angle)
            return {"ok": bool(ok)}

        if cmd.action == "read_imu":
            raw = bridge_call("read_imu")
            return {"ok": True, "imu": parse_imu_csv(raw)}

        if cmd.action == "imu_read":
            raw = bridge_call("imu_read")
            return {"ok": True, "imu": parse_imu_read_csv(raw)}

        if cmd.action == "calibration_mode":
            if cmd.on is None:
                raise HTTPException(400, "calibration_mode requires on")
            ok = bridge_call("calibration_mode", cmd.on)
            return {"ok": bool(ok)}

        if cmd.action == "face_talk":
            # face_talk/face_idle_cmd on the MCU side both take a String
            # param (unused) - Bridge has no default-param resolution, so a
            # zero-arg call fails with "Missing call parameters".
            bridge_call("face_talk", "")
            return {"ok": True}
        if cmd.action == "face_idle":
            bridge_call("face_idle", "")
            return {"ok": True}
        if cmd.action == "face_text":
            if cmd.text is None:
                raise HTTPException(400, "face_text requires text")
            bridge_call("face-text", cmd.text)
            return {"ok": True}
        if cmd.action == "read_sonar":
            if cmd.sensor_id is None:
                raise HTTPException(400, "read_sonar requires sensor_id")
            distance_cm = bridge_call("read_sonar", cmd.sensor_id)
            return {"ok": True, "distance_cm": distance_cm}

        # sonar_forward/sonar_backward: the two Modulino ToF "ear" sensors,
        # physically relocated again 2026-08-19 to the underbelly, facing
        # forward and backward - MCU-side Bridge RPC names
        # (sonar_right_ear/sonar_left_ear) are unchanged, only the physical
        # mounting and this Python-side label changed (previously top/bottom
        # of head, before that left/right ears - see git history). Mapping
        # confirmed by user 2026-08-19: left_ear=forward, right_ear=backward.
        if cmd.action == "sonar_forward":
            distance_cm = bridge_call("sonar_left_ear")
            return {"ok": True, "distance_cm": distance_cm}
        if cmd.action == "sonar_backward":
            distance_cm = bridge_call("sonar_right_ear")
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
            ok = bridge_call("face_config", EYE_SHAPES[eye_key], MOUTH_SHAPES[mouth_key], eye_color, mouth_color)
            return {"ok": bool(ok)}

        if cmd.action == "flashlight":
            if cmd.on is None:
                raise HTTPException(400, "flashlight requires on")
            ok = bridge_call("flashlight", cmd.on)
            return {"ok": bool(ok)}

        if cmd.action == "test_speakers":
            ok = bridge_call("test_speakers")
            return {"ok": bool(ok)}

        if cmd.action == "test_mic":
            level = bridge_call("test_mic")
            return {"ok": True, "level": float(level)}

        if cmd.action == "test_lidar":
            packet_count = bridge_call("test_lidar")
            return {"ok": True, "packet_count": int(packet_count)}

        if cmd.action == "lidar_scan":
            raw = bridge_call("get_lidar_scan")
            scan_cm = [int(v) for v in raw.split(",")]
            return {"ok": True, "scan_cm": scan_cm}

        if cmd.action == "get_servo_angles":
            raw = bridge_call("get_servo_angles")
            angles = [int(v) for v in raw.split(",")]
            return {"ok": True, "angles": angles}

        if cmd.action == "princess_mode":
            if cmd.on is None:
                raise HTTPException(400, "princess_mode requires on")
            ok = bridge_call("princess_mode", cmd.on)
            return {"ok": bool(ok)}

        if cmd.action == "flower_explosion":
            ok = bridge_call("flower_explosion")
            return {"ok": bool(ok)}

        if cmd.action == "play_pong":
            if cmd.on is None:
                raise HTTPException(400, "play_pong requires on")
            # play_pong takes a String on the MCU side ("true"/"false"), not a
            # bool like princess_mode/flashlight - it's driven by
            # aubie_listen.py's plain-string bridge_call() helper (a
            # different bridge_call than this file's own lock-wrapped one,
            # same name coincidentally), so the RPC signature matches that
            # rather than the bool convention used elsewhere in this file.
            ok = bridge_call("play_pong", "true" if cmd.on else "false")
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
            bridge_call("photo_chunk_start", "")
            for i in range(0, len(cmd.image_hex), PHOTO_CHUNK_HEX_LEN):
                bridge_call("photo_chunk", cmd.image_hex[i:i + PHOTO_CHUNK_HEX_LEN])
            ok = bridge_call("photo_render")
            return {"ok": bool(ok)}

        if cmd.action == "face_diag":
            raw = bridge_call("face_diag")
            # face.ino's face_diag() appends ",pong:<active>,<ballX>,<ballY>,
            # <leftY>,<rightY>,<ballVYx10>" after the original 8 fields (added
            # alongside play_pong for live debugging) - parse both parts.
            parts = raw.split(",")
            (face_state, eye_shape, mouth_shape, is_talking, calib, flash,
             text_overlay, ms) = parts[:8]
            pong_active, ball_x, ball_y, left_y, right_y, ball_vy10 = parts[8:14]
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
                "pong_active": bool(int(pong_active.split(":")[1])),
                "pong_ball": {"x": int(ball_x), "y": int(ball_y)},
                "pong_paddles": {"left_y": int(left_y), "right_y": int(right_y)},
                "pong_ball_vy": int(ball_vy10) / 10.0,
            }

        if cmd.action == "diag_info":
            raw = bridge_call("diag_info")
            pca9685, imu, face, dist_r, dist_l = raw.split(",")
            return {
                "ok": True,
                "pca9685_present": bool(int(pca9685)),
                "imu_present": bool(int(imu)),
                "face_setup_done": bool(int(face)),
                "dist_right_present": bool(int(dist_r)),
                "dist_left_present": bool(int(dist_l)),
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



@api.get("/dog/distance")
async def get_distance():
    # Was read_sonar(0), which reads the dead/never-wired HC-SR04 placeholder
    # array (see sketch.ino's SONAR_COUNT note) - always timed out to -1.
    # Now reads the real Modulino ToF sensors, underbelly forward/backward.
    try:
        forward_cm = bridge_call("sonar_left_ear")
        backward_cm = bridge_call("sonar_right_ear")
        return {"forward_cm": forward_cm, "backward_cm": backward_cm, "status": "ok"}
    except Exception as e:
        return {"forward_cm": -1, "backward_cm": -1, "error": str(e)}

@api.get("/dog/lidar_scan")
async def get_lidar_scan_endpoint():
    # Live 360deg scan, 36 buckets @ 10deg resolution, cm distances (-1 = no
    # reading yet for that bucket). See sketch.ino's get_lidar_scan() comment.
    try:
        raw = bridge_call("get_lidar_scan")
        scan_cm = [int(v) for v in raw.split(",")]
        return {"scan_cm": scan_cm, "status": "ok"}
    except Exception as e:
        return {"scan_cm": [], "error": str(e)}

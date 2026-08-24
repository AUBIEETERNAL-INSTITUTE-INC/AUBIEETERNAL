"""
AUBIEETERNAL — Vision Extras Module
File: /home/aubieeternal/AUBIEETERNAL/vision_extras.py

GPU-accelerated vision on Ryzen RTX 3060.
Add to assistant_server.py:
    from vision_extras import router as vision_router
    app.include_router(vision_router)

Install deps once:
    pip install ultralytics mediapipe pyzbar easyocr
    pip install opencv-python-headless --upgrade
"""

import io
import base64
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter(prefix="/vision")

# ─── Lazy model loading (only loaded on first call) ───────────────────────────
_yolo_model   = None
_mp_pose      = None
_mp_face_mesh = None
_qr_detector  = None
_ocr_reader   = None


def _get_yolo():
    global _yolo_model
    if _yolo_model is None:
        from ultralytics import YOLO
        _yolo_model = YOLO("yolov8n.pt")
    _yolo_model.to("cpu")   # downloads ~6MB on first run
    return _yolo_model


def _get_pose():
    global _mp_pose
    if _mp_pose is None:
        import mediapipe as mp
        _mp_pose = mp.solutions.pose.Pose(
            static_image_mode=True,
            model_complexity=1,
            enable_segmentation=False,
        )
    return _mp_pose


def _get_face_mesh():
    global _mp_face_mesh
    if _mp_face_mesh is None:
        import mediapipe as mp
        _mp_face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=4,
            refine_landmarks=True,
        )
    return _mp_face_mesh


def _get_qr():
    global _qr_detector
    if _qr_detector is None:
        _qr_detector = cv2.QRCodeDetector()
    return _qr_detector


def _get_ocr():
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        _ocr_reader = easyocr.Reader(["en"], gpu=True)
    return _ocr_reader


# ─── Shared image decoder ─────────────────────────────────────────────────────

def _decode_image(b64: str) -> np.ndarray:
    """Decode base64 JPEG/PNG → OpenCV BGR array."""
    data = base64.b64decode(b64)
    arr  = np.frombuffer(data, np.uint8)
    img  = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image")
    return img


# ─── Request model (shared by all endpoints) ──────────────────────────────────

class ImageRequest(BaseModel):
    image_b64: str          # base64-encoded JPEG or PNG
    snapshot_path: Optional[str] = None   # if set, save annotated result here


# ─── 1. Object detection (YOLOv8) ────────────────────────────────────────────

@router.post("/detect")
async def detect_objects(req: ImageRequest):
    """
    Detect objects in an image.
    Returns list of {label, confidence, bbox:[x1,y1,x2,y2]}.
    Suitable for "what do you see?" voice command.
    """
    img   = _decode_image(req.image_b64)
    model = _get_yolo()
    results = model(img, verbose=False)[0]

    detections = []
    for box in results.boxes:
        label = model.names[int(box.cls)]
        conf  = float(box.conf)
        x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
        detections.append({"label": label, "confidence": round(conf, 3),
                            "bbox": [x1, y1, x2, y2]})

    # Annotate and optionally save
    if req.snapshot_path:
        annotated = results.plot()
        cv2.imwrite(req.snapshot_path, annotated)

    # Human-readable summary for TTS
    if detections:
        counts: dict[str, int] = {}
        for d in detections:
            counts[d["label"]] = counts.get(d["label"], 0) + 1
        summary = ", ".join(
            f"{v} {k}" + ("s" if v > 1 else "")
            for k, v in sorted(counts.items(), key=lambda x: -x[1])
        )
        summary = f"I can see {summary}."
    else:
        summary = "I don't see anything recognisable."

    return {"detections": detections, "summary": summary}


# ─── 2. Human pose detection (MediaPipe) ──────────────────────────────────────

@router.post("/pose")
async def detect_pose(req: ImageRequest):
    """
    Returns 33 body landmark positions + a simple posture label
    (standing / sitting / lying / unknown) + basic fall flag.
    """
    img_bgr = _decode_image(req.image_b64)
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    pose    = _get_pose()
    res     = pose.process(img_rgb)

    if not res.pose_landmarks:
        return {"detected": False, "posture": "unknown", "fall": False, "landmarks": []}

    h, w = img_bgr.shape[:2]
    lm = res.pose_landmarks.landmark

    # Pull key joints (MediaPipe indices)
    nose      = lm[0]
    l_hip     = lm[23];  r_hip  = lm[24]
    l_ankle   = lm[27];  r_ankle = lm[28]
    l_shoulder = lm[11]; r_shoulder = lm[12]

    hip_y    = (l_hip.y + r_hip.y) / 2
    ankle_y  = (l_ankle.y + r_ankle.y) / 2
    nose_y   = nose.y
    body_h   = abs(ankle_y - nose_y)
    body_w   = abs(l_shoulder.x - r_shoulder.x)

    aspect = body_h / (body_w + 1e-5)

    if aspect > 1.8:
        posture = "standing"
    elif aspect > 0.9:
        posture = "sitting"
    else:
        posture = "lying"

    # Crude fall detection: lying + sudden drop (use history for real fall detection)
    fall = posture == "lying"

    landmarks = [
        {"name": i, "x": round(p.x, 4), "y": round(p.y, 4), "z": round(p.z, 4)}
        for i, p in enumerate(lm)
    ]
    return {"detected": True, "posture": posture, "fall": fall, "landmarks": landmarks}


# ─── 3. Face mesh (MediaPipe) ─────────────────────────────────────────────────

@router.post("/face_mesh")
async def face_mesh(req: ImageRequest):
    """
    Returns 478 face landmarks per detected face.
    Useful for emotion cues, gaze direction, or mesh overlays.
    """
    img_bgr = _decode_image(req.image_b64)
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    mesh    = _get_face_mesh()
    res     = mesh.process(img_rgb)

    if not res.multi_face_landmarks:
        return {"faces": 0, "landmarks": []}

    faces = []
    for face_lm in res.multi_face_landmarks:
        pts = [{"x": round(p.x, 4), "y": round(p.y, 4), "z": round(p.z, 4)}
               for p in face_lm.landmark]
        faces.append(pts)

    return {"faces": len(faces), "landmarks": faces}


# ─── 4. QR code reader ────────────────────────────────────────────────────────

@router.post("/qr")
async def read_qr(req: ImageRequest):
    """Decode any QR codes in the image."""
    img = _decode_image(req.image_b64)
    det = _get_qr()
    data, points, _ = det.detectAndDecode(img)
    if not data:
        # Try with enhanced contrast
        gray    = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        data, points, _ = det.detectAndDecode(thresh)

    return {
        "found": bool(data),
        "data": data or None,
        "corners": points.tolist() if points is not None and data else None,
    }


# ─── 5. Color recognition ─────────────────────────────────────────────────────

_COLOR_RANGES = {
    "red":    [((0,100,100),(10,255,255)), ((160,100,100),(180,255,255))],
    "orange": [((11,100,100),(25,255,255))],
    "yellow": [((26,100,100),(34,255,255))],
    "green":  [((35,60,60),(85,255,255))],
    "blue":   [((86,60,60),(130,255,255))],
    "purple": [((131,50,50),(159,255,255))],
    "white":  [((0,0,200),(180,30,255))],
    "black":  [((0,0,0),(180,255,50))],
}

@router.post("/colors")
async def detect_colors(req: ImageRequest):
    """
    Returns dominant colors in the image with pixel-coverage percentages.
    """
    img = _decode_image(req.image_b64)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    total = img.shape[0] * img.shape[1]
    results = {}

    for color, ranges in _COLOR_RANGES.items():
        mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
        for lo, hi in ranges:
            mask |= cv2.inRange(hsv, np.array(lo), np.array(hi))
        pct = round(cv2.countNonZero(mask) / total * 100, 1)
        if pct > 1.0:
            results[color] = pct

    dominant = sorted(results.items(), key=lambda x: -x[1])
    summary  = (f"Dominant colors: " + ", ".join(f"{c} ({p}%)" for c, p in dominant[:3])
                if dominant else "No strong colors detected.")
    return {"colors": results, "dominant": dominant[:3], "summary": summary}


# ─── 6. Object counting ───────────────────────────────────────────────────────

class CountRequest(BaseModel):
    image_b64: str
    label: str   # e.g. "person", "car", "bottle"

@router.post("/count")
async def count_objects(req: CountRequest):
    """Count how many instances of a specific object class appear."""
    img   = _decode_image(req.image_b64)
    model = _get_yolo()
    results = model(img, verbose=False)[0]
    count = sum(1 for box in results.boxes
                if model.names[int(box.cls)].lower() == req.label.lower())
    return {"label": req.label, "count": count,
            "summary": f"I count {count} {req.label}{'s' if count != 1 else ''}."}


# ─── 7. License plate / text OCR ─────────────────────────────────────────────

@router.post("/ocr")
async def read_text(req: ImageRequest):
    """
    Read text from any image — signs, license plates, documents.
    Uses EasyOCR (GPU). Slow on first call (model load ~10s).
    """
    img    = _decode_image(req.image_b64)
    reader = _get_ocr()
    result = reader.readtext(img)
    texts  = [{"text": r[1], "confidence": round(r[2], 3)} for r in result if r[2] > 0.3]
    combined = " ".join(t["text"] for t in texts)
    return {"texts": texts, "combined": combined,
            "summary": f"I read: {combined}" if combined else "No text found."}


# ─── 8. Fall alert (stateful, tracks last pose per camera) ───────────────────

_last_pose_time: dict[str, float] = {}
_last_posture:   dict[str, str]   = {}

class FallRequest(BaseModel):
    image_b64: str
    camera_id: str = "default"
    alert_webhook: Optional[str] = None   # POST alert here if fall detected

@router.post("/fall_check")
async def fall_check(req: FallRequest):
    """
    Stateful fall detector — send frames regularly, get alerted when posture
    changes to 'lying' after being 'standing'/'sitting'.
    """
    import httpx

    img_bgr = _decode_image(req.image_b64)
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    pose    = _get_pose()
    res     = pose.process(img_rgb)

    if not res.pose_landmarks:
        return {"detected": False, "fall": False, "posture": "unknown"}

    lm = res.pose_landmarks.landmark
    nose_y   = lm[0].y
    ankle_y  = (lm[27].y + lm[28].y) / 2
    shldr_w  = abs(lm[11].x - lm[12].x)
    body_h   = abs(ankle_y - nose_y)
    aspect   = body_h / (shldr_w + 1e-5)

    posture  = "standing" if aspect > 1.8 else ("sitting" if aspect > 0.9 else "lying")
    prev     = _last_posture.get(req.camera_id, "unknown")
    fall     = (posture == "lying" and prev in ("standing", "sitting"))

    _last_posture[req.camera_id]   = posture
    _last_pose_time[req.camera_id] = time.time()

    if fall and req.alert_webhook:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(req.alert_webhook,
                                  json={"event": "fall_detected",
                                        "camera": req.camera_id,
                                        "previous_posture": prev})
        except Exception:
            pass

    return {"detected": True, "posture": posture, "previous": prev, "fall": fall}


# ─── 9. Snapshot helper (Aubie camera → detect → TTS summary) ─────────────────

SNAPSHOT_DIR = Path.home() / "aubie_storage" / "snapshots"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

@router.post("/what_do_you_see")
async def what_do_you_see(req: ImageRequest):
    """
    All-in-one: detect objects + dominant colors + QR codes.
    Returns a single TTS-ready sentence.
    Designed to be called from the 'what do you see?' voice command.
    """
    img = _decode_image(req.image_b64)
    model = _get_yolo()

    # Objects
    results = model(img, verbose=False)[0]
    counts: dict[str, int] = {}
    for box in results.boxes:
        label = model.names[int(box.cls)]
        counts[label] = counts.get(label, 0) + 1

    # Colors (quick, top 2)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    total = img.shape[0] * img.shape[1]
    color_hits = []
    for color, ranges in _COLOR_RANGES.items():
        mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
        for lo, hi in ranges:
            mask |= cv2.inRange(hsv, np.array(lo), np.array(hi))
        pct = cv2.countNonZero(mask) / total * 100
        if pct > 10:
            color_hits.append(color)

    # QR
    det = _get_qr()
    qr_data, _, _ = det.detectAndDecode(img)

    # Build sentence
    parts = []
    if counts:
        obj_str = ", ".join(
            f"{v} {k}" + ("s" if v > 1 else "")
            for k, v in sorted(counts.items(), key=lambda x: -x[1])[:4]
        )
        parts.append(f"I see {obj_str}")
    if color_hits:
        parts.append(f"with {' and '.join(color_hits[:2])} colors")
    if qr_data:
        parts.append(f"and a QR code that says: {qr_data}")

    summary = (". ".join(parts) + ".") if parts else "I don't recognise anything in this image."

    # Save snapshot
    snap_path = str(SNAPSHOT_DIR / f"vision_{int(time.time())}.jpg")
    annotated = results.plot()
    cv2.imwrite(snap_path, annotated)

    return {"summary": summary, "objects": counts,
            "colors": color_hits, "qr": qr_data or None,
            "snapshot": snap_path}

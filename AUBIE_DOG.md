# 🐾 Aubie the Robot Dog

An AI robot dog you build yourself: a quadruped chassis with a voice assistant, computer vision, and a phone remote-control app, running on hardware you own. Built as a hands-on project for [AUBIEETERNAL](README.md) — the free, open-source sovereign school — so a student who completes it walks away with their own working AI assistant, not just a grade. It sits alongside the existing **Sovereign Builder** track (hardware → AI internals → deployment) as the hands-on capstone: build the dog, teach it your own family's faces, and you understand your assistant end-to-end instead of owning a black box.

## What Aubie actually is (as of August 2026)

Aubie is two machines talking to each other over the network:

- **Aubie** (an Arduino Uno Q) — the body. Runs the servo/sensor firmware (`spotmicro_dog/sketch/sketch.ino`) and a small Python bridge server (`spotmicro_dog/python/aubie_dog.py`) that exposes movement, face-display, and camera controls over HTTP.
- **The rig** (any Linux box with a GPU) — the brain. Runs `assistant_server.py`: speech-to-text (faster-whisper), a local LLM via Ollama (qwen2.5 text + vision models), face recognition (InsightFace), and text-to-speech (Piper) — fully offline-capable, no cloud API required for the core assistant loop.

### What it can do right now

- **Talk back.** Wake-word listening ("hey Aubie"), transcribes what you say, replies out loud, remembers past conversations and durable facts about people it knows, and can translate on request.
- **See.** Recognizes enrolled faces by name, describes what's in front of its camera, and can be taught a new person through a guided multi-photo enrollment flow (`/enroll_face`) — point the camera, say a name, done. The server keeps only the sharp, single-face, well-framed shots automatically, the way phone face-unlock enrollment does.
- **Move.** 12 servos (hip/thigh/knee × 4 legs) driven off a PCA9685, with stand/sit/rest/walk/turn poses and a non-blocking gait engine. Boots into a low-torque folded rest pose rather than standing, and only stands on command — reduces servo stress and avoids twisting a leg into a bad position on power-up.
- **Be driven.** A phone web UI (`/remote`) with a live video feed, a virtual joystick for body-lean control (RC-style), manual per-servo/pose tools, and a "follow a person" mode that turns to keep a named, enrolled person in frame.
- **Show images.** Search Unsplash for a phrase and push the top result to its onboard TFT face display.

### Hardware

- Arduino Uno Q (STM32U585 + Zephyr side for real-time servo/sensor control, Linux side for the camera/bridge server)
- 12× MG996R servos + PCA9685 driver
- Modulino Movement (IMU) + 2× Modulino Distance (ToF) + 3× HC-SR04 ultrasonic
- ILI9341 TFT + resistive touch (face)
- Arducam 16MP USB camera
- Any Linux machine with a GPU to run the voice/vision brain (`assistant_server.py`)

### Code layout

```
assistant_server.py          - voice/vision brain: STT, LLM routing, TTS, face ID, memory, follow-a-person
phone_ui.py                  - the /remote phone control UI (FastAPI router)
debug_endpoint.py            - LLM-assisted crash triage for the brain server
spotmicro_dog/sketch/        - Arduino firmware: servo control, gait, face display, sensors
spotmicro_dog/python/        - Aubie-side bridge server (aubie_dog.py) exposing /dog/command
```

### Status

This is an active build, not a finished kit — servo calibration, the turning gait, and person-following are all still being tuned against real hardware. Treat firmware constants marked with dated comments as measured-live-on-this-specific-robot, not universal defaults; re-measure them against your own assembly.

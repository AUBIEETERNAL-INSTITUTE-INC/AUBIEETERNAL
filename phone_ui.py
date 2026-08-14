"""
AUBIEETERNAL — Mobile Phone Control UI
File: /home/aubieeternal/AUBIEETERNAL/phone_ui.py

Add to assistant_server.py:
    from phone_ui import router as phone_router
    app.include_router(phone_router)

Access from phone browser: http://100.105.81.27:8800/remote
(or your local LAN IP if not on Tailscale)

Calls the existing /dog/command endpoint on Aubie (port 8420).
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

AUBIE_URL = "http://100.66.110.65:8420"   # Aubie dog command server

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>Aubie Remote</title>
<style>
  :root {
    --bg: #0d0d0d;
    --card: #1a1a1a;
    --accent: #ff9800;
    --green: #4caf50;
    --red: #f44336;
    --blue: #2196f3;
    --purple: #9c27b0;
    --text: #f0f0f0;
    --sub: #888;
    --radius: 14px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    min-height: 100vh;
    padding: 16px;
    padding-bottom: 32px;
  }
  header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 18px;
  }
  header h1 { font-size: 22px; font-weight: 700; }
  .dot {
    width: 10px; height: 10px;
    border-radius: 50%;
    background: var(--red);
    transition: background 0.4s;
  }
  .dot.online { background: var(--green); }
  .status-text { font-size: 12px; color: var(--sub); margin-left: auto; }

  .section { margin-bottom: 20px; }
  .section-title {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: var(--sub);
    margin-bottom: 10px;
  }

  .grid { display: grid; gap: 10px; }
  .grid-2 { grid-template-columns: 1fr 1fr; }
  .grid-3 { grid-template-columns: 1fr 1fr 1fr; }

  button {
    border: none;
    border-radius: var(--radius);
    padding: 16px 8px;
    font-size: 15px;
    font-weight: 600;
    cursor: pointer;
    transition: transform 0.1s, opacity 0.1s;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    width: 100%;
    color: #fff;
  }
  button:active { transform: scale(0.95); opacity: 0.8; }
  button .icon { font-size: 26px; }
  button .label { font-size: 13px; }

  .btn-green  { background: #1b3a1b; border: 1.5px solid var(--green); color: var(--green); }
  .btn-red    { background: #3a1b1b; border: 1.5px solid var(--red);   color: var(--red); }
  .btn-orange { background: #3a2800; border: 1.5px solid var(--accent);color: var(--accent); }
  .btn-blue   { background: #1b2a3a; border: 1.5px solid var(--blue);  color: var(--blue); }
  .btn-purple { background: #2a1a3a; border: 1.5px solid var(--purple);color: var(--purple); }
  .btn-grey   { background: #222;    border: 1.5px solid #555;         color: #ccc; }

  .speak-row {
    display: flex;
    gap: 10px;
  }
  .speak-input {
    flex: 1;
    background: var(--card);
    border: 1.5px solid #333;
    border-radius: var(--radius);
    color: var(--text);
    font-size: 15px;
    padding: 14px 16px;
  }
  .speak-input:focus { outline: none; border-color: var(--accent); }

  .servo-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
  }
  select {
    flex: 1;
    background: var(--card);
    border: 1.5px solid #333;
    border-radius: var(--radius);
    color: var(--text);
    font-size: 15px;
    padding: 12px 14px;
  }
  input[type=range] {
    flex: 1;
    accent-color: var(--accent);
  }
  input[type=color] {
    flex-shrink: 0;
    width: 48px;
    height: 44px;
    padding: 4px;
    background: var(--card);
    border: 1.5px solid #333;
    border-radius: var(--radius);
    cursor: pointer;
  }
  .angle-val {
    min-width: 44px;
    text-align: right;
    font-variant-numeric: tabular-nums;
    color: var(--accent);
    font-weight: 600;
  }

  #joystick-pad {
    position: relative;
    width: 220px;
    height: 220px;
    margin: 14px auto 6px;
    border-radius: 50%;
    background: var(--card);
    border: 1.5px solid #333;
    touch-action: none;
  }
  #joystick-knob {
    position: absolute;
    width: 64px;
    height: 64px;
    border-radius: 50%;
    background: var(--accent);
    opacity: 0.85;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
    touch-action: none;
  }

  #log {
    background: var(--card);
    border-radius: var(--radius);
    padding: 14px;
    font-family: monospace;
    font-size: 12px;
    color: var(--sub);
    min-height: 80px;
    max-height: 160px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-all;
  }
  .log-ok  { color: var(--green); }
  .log-err { color: var(--red); }
</style>
</head>
<body>

<header>
  <div class="dot" id="dot"></div>
  <h1>🐾 Aubie</h1>
  <span class="status-text" id="tilt-text" style="margin-left:auto; margin-right:10px;"></span>
  <span class="status-text" id="status-text" style="margin-left:0;">checking…</span>
</header>

<!-- RC Control -->
<div class="section">
  <div class="section-title">RC Control</div>
  <canvas id="call-canvas" width="480" height="360"
          style="width:100%;border-radius:var(--radius);background:#000;display:block;margin-bottom:10px;"></canvas>
  <div class="grid grid-2">
    <button class="btn-green" onclick="startCall()"><span class="icon">📞</span><span class="label">Start Video</span></button>
    <button class="btn-red"   onclick="endCall()"><span class="icon">📴</span><span class="label">Stop Video</span></button>
  </div>
  <div class="status-text" id="call-status" style="text-align:center;margin-top:6px;">Off</div>

  <!-- Drag to lean the body (tilt fwd/back/left/right); release/center = stand.
       Maps to lean(x, y) - see aubie_dog.py / sketch.ino's lean Bridge RPC. -->
  <div id="joystick-pad">
    <div id="joystick-knob"></div>
  </div>

  <div class="grid grid-3" style="margin-top:10px;">
    <button class="btn-grey" onclick="cmd('stand')"><span class="icon">🦴</span><span class="label">Stand</span></button>
    <button class="btn-grey" onclick="cmd('sit')"><span class="icon">🐕</span><span class="label">Sit</span></button>
    <button class="btn-grey" onclick="cmd('walk forward')"><span class="icon">▶️</span><span class="label">Walk</span></button>
  </div>
</div>

<!-- Movement -->
<div class="section">
  <div class="section-title">Movement</div>
  <div class="grid grid-2">
    <button class="btn-green"  onclick="cmd('stand')"><span class="icon">🦴</span><span class="label">Stand</span></button>
    <button class="btn-orange" onclick="cmd('sit')"  ><span class="icon">🐕</span><span class="label">Sit</span></button>
    <button class="btn-blue"   onclick="cmd('walk forward')"><span class="icon">▶️</span><span class="label">Walk Fwd</span></button>
    <button class="btn-grey"   onclick="cmd('stop')"><span class="icon">⏹️</span><span class="label">Stop</span></button>
    <button class="btn-grey"   onclick="cmd('rest')"><span class="icon">🛌</span><span class="label">Lay Down</span></button>
  </div>
  <!-- New turn_left()/turn_right() gait, not yet verified against the real
       robot - test here manually (watch it, be ready to stop) before
       trusting the Follow a Person feature to call these on its own. -->
  <div class="grid grid-2" style="margin-top:10px;">
    <button class="btn-purple" onclick="cmd('turn left')"><span class="icon">↩️</span><span class="label">Turn Left (test)</span></button>
    <button class="btn-purple" onclick="cmd('turn right')"><span class="icon">↪️</span><span class="label">Turn Right (test)</span></button>
  </div>
</div>

<!-- Face -->
<div class="section">
  <div class="section-title">Face</div>
  <div class="grid grid-3">
    <button class="btn-grey"   onclick="cmd('show happy face')"><span class="icon">😊</span><span class="label">Happy</span></button>
    <button class="btn-grey"   onclick="cmd('show surprised face')"><span class="icon">😮</span><span class="label">Surprised</span></button>
    <button class="btn-grey"   onclick="cmd('show idle face')"><span class="icon">😐</span><span class="label">Idle</span></button>
  </div>
</div>

<!-- Face Customization -->
<div class="section">
  <div class="section-title">Face Customization</div>
  <div class="servo-row">
    <select id="eye-shape">
      <option value="round">Round Eyes</option>
      <option value="narrow">Narrow Eyes</option>
      <option value="wide">Wide Eyes</option>
      <option value="angry">Angry Eyes</option>
      <option value="sad">Sad Eyes</option>
      <option value="dog_eyes">Dog Eyes</option>
      <option value="crazy">Wacked Out Eyes</option>
      <option value="stoned">Stoned Eyes</option>
    </select>
    <input type="color" id="eye-color" value="#ffffff">
  </div>
  <div class="servo-row">
    <select id="mouth-shape">
      <option value="smile">Smile</option>
      <option value="flat">Flat</option>
      <option value="frown">Frown</option>
      <option value="open">Open</option>
      <option value="dog_mouth">Dog Mouth</option>
      <option value="crazy">Wacked Out Mouth</option>
      <option value="stoned">Stoned (big tongue)</option>
    </select>
    <input type="color" id="mouth-color" value="#ffffff">
  </div>
  <button class="btn-green" onclick="applyFaceConfig()"><span class="icon">🎨</span><span class="label">Apply Face</span></button>
  <div class="grid grid-2" style="margin-top:10px;">
    <button class="btn-purple" onclick="postCommand({action:'face_config',eye_shape:'crazy',mouth_shape:'crazy',eye_color:'#ff0000',mouth_color:'#ffffff'})">
      <span class="icon">☕</span><span class="label">Wacked Out</span>
    </button>
    <button class="btn-purple" onclick="postCommand({action:'face_config',eye_shape:'stoned',mouth_shape:'stoned',eye_color:'#ffffff',mouth_color:'#ffffff'})">
      <span class="icon">😵‍💫</span><span class="label">Stoned</span>
    </button>
  </div>
  <div class="grid grid-2" style="margin-top:10px;">
    <button class="btn-grey" onclick="saveFacePreset()"><span class="icon">💾</span><span class="label">Save Face Preset</span></button>
  </div>
  <div class="servo-row" style="margin-top:10px;">
    <select id="face-preset-select"><option value="">No face presets saved</option></select>
    <button class="btn-blue" style="width:auto;padding:12px 16px;" onclick="applyFacePreset()"><span class="icon">↩️</span></button>
    <button class="btn-red"  style="width:auto;padding:12px 16px;" onclick="deleteFacePreset()"><span class="icon">🗑️</span></button>
  </div>
</div>

<!-- Flashlight -->
<div class="section">
  <div class="section-title">Flashlight</div>
  <button class="btn-orange" id="flashlight-btn" onclick="toggleFlashlight()">
    <span class="icon">🔦</span><span class="label">Flashlight: Off</span>
  </button>
</div>

<!-- Princess Mode -->
<div class="section">
  <div class="section-title">Princess Mode</div>
  <button class="btn-orange" id="princess-btn" onclick="togglePrincess()">
    <span class="icon">👑</span><span class="label">Princess Mode: Off</span>
  </button>
</div>

<!-- Tricks -->
<div class="section">
  <div class="section-title">Tricks</div>
  <div class="grid grid-2">
    <button class="btn-purple" onclick="cmd('raise leg')"><span class="icon">🐾</span><span class="label">Raise Leg</span></button>
    <button class="btn-purple" onclick="cmd('shake')"><span class="icon">🤝</span><span class="label">Shake</span></button>
  </div>
</div>

<!-- Teach Aubie a Person -->
<div class="section">
  <div class="section-title">Teach Aubie a Person</div>
  <div class="speak-row">
    <input class="speak-input" id="enroll-name" placeholder="Name (e.g. Juan)">
    <button class="btn-green" style="width:auto;padding:14px 18px;" onclick="startEnrollment()">
      <span class="icon">📸</span>
    </button>
  </div>
  <div class="status-text" id="enroll-status" style="text-align:center;margin-top:8px;">
    Enter a name and tap the camera - Aubie's camera will guide you through a few angles.
  </div>
</div>

<!-- Follow a Person -->
<div class="section">
  <div class="section-title">Follow a Person</div>
  <div class="servo-row">
    <select id="follow-select"><option value="">Loading known people…</option></select>
    <button class="btn-blue" style="width:auto;padding:12px 16px;" onclick="startFollow()"><span class="icon">👣</span></button>
    <button class="btn-red"  style="width:auto;padding:12px 16px;" onclick="stopFollow()"><span class="icon">⏹️</span></button>
  </div>
  <div class="status-text" id="follow-status" style="text-align:center;margin-top:6px;">Not following</div>
</div>

<!-- Servo Control -->
<div class="section">
  <div class="section-title">Servo Control</div>
  <div class="servo-row">
    <select id="servo-channel">
      <option value="0">FL Hip</option>
      <option value="1">FL Thigh</option>
      <option value="2">FL Knee</option>
      <option value="3">FR Hip</option>
      <option value="4">FR Thigh</option>
      <option value="5">FR Knee</option>
      <option value="6">RL Hip</option>
      <option value="7">RL Thigh</option>
      <option value="8">RL Knee</option>
      <option value="9">RR Hip</option>
      <option value="10">RR Thigh</option>
      <option value="11">RR Knee</option>
    </select>
  </div>
  <div class="servo-row">
    <input type="range" id="servo-angle" min="0" max="180" value="90"
           oninput="document.getElementById('angle-val').textContent = this.value + '°'">
    <span class="angle-val" id="angle-val">90°</span>
  </div>
  <div class="grid grid-2">
    <button class="btn-green" onclick="setServo()"><span class="icon">🎯</span><span class="label">Set Angle</span></button>
    <button class="btn-grey"  onclick="savePreset()"><span class="icon">💾</span><span class="label">Save Preset</span></button>
  </div>
  <div class="servo-row" style="margin-top:10px;">
    <select id="preset-select"><option value="">No presets saved</option></select>
    <button class="btn-blue" style="width:auto;padding:12px 16px;" onclick="applyPreset()"><span class="icon">↩️</span></button>
    <button class="btn-red"  style="width:auto;padding:12px 16px;" onclick="deletePreset()"><span class="icon">🗑️</span></button>
  </div>
</div>

<!-- Custom Poses (all 12 servos at once) -->
<div class="section">
  <div class="section-title">Custom Poses</div>
  <button class="btn-green" onclick="savePose()"><span class="icon">📸</span><span class="label">Save Current Pose (all legs)</span></button>
  <div class="servo-row" style="margin-top:10px;">
    <select id="pose-select"><option value="">No poses saved</option></select>
    <button class="btn-blue" style="width:auto;padding:12px 16px;" onclick="applyPose()"><span class="icon">↩️</span></button>
    <button class="btn-red"  style="width:auto;padding:12px 16px;" onclick="deletePose()"><span class="icon">🗑️</span></button>
  </div>
</div>

<!-- Say something -->
<div class="section">
  <div class="section-title">Say / Command</div>
  <div class="speak-row">
    <input class="speak-input" id="speak-input" placeholder="Type a command or phrase…"
           onkeydown="if(event.key==='Enter') sendSpeak()">
    <button class="btn-orange" style="width:auto;padding:14px 18px;" onclick="sendSpeak()">
      <span class="icon">📡</span>
    </button>
  </div>
</div>

<!-- Log -->
<div class="section">
  <div class="section-title">Log</div>
  <div id="log">Waiting for commands…</div>
</div>

<script>
const AUBIE = '/proxy/dog';  // proxied through assistant_server to avoid CORS

// Maps this UI's button labels to the exact {action, ...} payload aubie's
// /dog/command endpoint (aubie_dog.py's DogCommand model) actually expects.
// Previously cmd() POSTed {command: text} - aubie_dog.py requires a field
// named "action" with one of a fixed set of literal values, so every button
// press was failing pydantic validation (422) before it ever reached the
// firmware. "stop" has no dedicated halt RPC yet, so it maps to "stand" (a
// safe, stable pose) rather than doing nothing.
const COMMAND_MAP = {
  'stand':               {action: 'stand'},
  'sit':                 {action: 'sit'},
  'rest':                {action: 'rest'},
  'walk forward':        {action: 'walk_forward'},
  'turn left':           {action: 'turn_left'},
  'turn right':          {action: 'turn_right'},
  'stop':                {action: 'stand'},
  'show happy face':     {action: 'face_config', eye_shape: 'round', mouth_shape: 'smile'},
  'show surprised face': {action: 'face_config', eye_shape: 'wide',  mouth_shape: 'open'},
  'show idle face':      {action: 'face_idle'},
};

async function postCommand(payload) {
  try {
    const r = await fetch(AUBIE, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    const j = await r.json();
    log(`✓ ${JSON.stringify(j)}`, 'ok');
  } catch(e) {
    log(`✗ ${e.message}`, 'err');
  }
}

async function cmd(command) {
  log(`→ ${command}`);
  const payload = COMMAND_MAP[command];
  if (!payload) {
    log(`✗ "${command}" isn't wired to a dog command yet`, 'err');
    return;
  }
  await postCommand(payload);
}

// Free-text "Say / Command" box shows the typed text on Aubie's TFT via the
// face_text RPC (2s centered overlay - see face.ino) rather than trying to
// match it against COMMAND_MAP, which only knows the fixed button phrases.
function sendSpeak() {
  const v = document.getElementById('speak-input').value.trim();
  if (!v) return;
  log(`→ face_text "${v}"`);
  postCommand({action: 'face_text', text: v});
  document.getElementById('speak-input').value = '';
}

// ─── Face customization + flashlight ──────────────────────────────────────
function currentFaceConfig() {
  return {
    eye_shape: document.getElementById('eye-shape').value,
    mouth_shape: document.getElementById('mouth-shape').value,
    eye_color: document.getElementById('eye-color').value,
    mouth_color: document.getElementById('mouth-color').value,
  };
}

async function applyFaceConfig() {
  const cfg = currentFaceConfig();
  log(`→ face_config ${cfg.eye_shape}/${cfg.mouth_shape} ${cfg.eye_color}/${cfg.mouth_color}`);
  await postCommand({action: 'face_config', ...cfg});
}

// ─── Face presets (named eye/mouth/color combos, saved client-side) ───────
const FACE_PRESET_KEY = 'aubie_face_presets';

function loadFacePresets() {
  try { return JSON.parse(localStorage.getItem(FACE_PRESET_KEY) || '{}'); }
  catch { return {}; }
}

function refreshFacePresetList() {
  const presets = loadFacePresets();
  const names = Object.keys(presets);
  const sel = document.getElementById('face-preset-select');
  sel.innerHTML = '';
  if (names.length === 0) {
    sel.innerHTML = '<option value="">No face presets saved</option>';
    return;
  }
  names.forEach(name => {
    const opt = document.createElement('option');
    opt.value = name;
    opt.textContent = name;
    sel.appendChild(opt);
  });
}

function saveFacePreset() {
  const cfg = currentFaceConfig();
  const name = prompt('Name this face:');
  if (!name) return;
  const presets = loadFacePresets();
  presets[name] = cfg;
  localStorage.setItem(FACE_PRESET_KEY, JSON.stringify(presets));
  refreshFacePresetList();
  log(`✓ saved face preset "${name}"`, 'ok');
}

async function applyFacePreset() {
  const name = document.getElementById('face-preset-select').value;
  if (!name) return;
  const cfg = loadFacePresets()[name];
  if (!cfg) return;
  document.getElementById('eye-shape').value = cfg.eye_shape;
  document.getElementById('mouth-shape').value = cfg.mouth_shape;
  document.getElementById('eye-color').value = cfg.eye_color;
  document.getElementById('mouth-color').value = cfg.mouth_color;
  log(`→ face preset "${name}"`);
  await postCommand({action: 'face_config', ...cfg});
}

function deleteFacePreset() {
  const name = document.getElementById('face-preset-select').value;
  if (!name) return;
  const presets = loadFacePresets();
  delete presets[name];
  localStorage.setItem(FACE_PRESET_KEY, JSON.stringify(presets));
  refreshFacePresetList();
}

let flashlightOn = false;
async function toggleFlashlight() {
  flashlightOn = !flashlightOn;
  const btn = document.getElementById('flashlight-btn');
  btn.querySelector('.label').textContent = `Flashlight: ${flashlightOn ? 'On' : 'Off'}`;
  btn.classList.toggle('btn-orange', !flashlightOn);
  btn.classList.toggle('btn-green', flashlightOn);
  log(`→ flashlight ${flashlightOn}`);
  await postCommand({action: 'flashlight', on: flashlightOn});
}

let princessOn = false;
async function togglePrincess() {
  princessOn = !princessOn;
  const btn = document.getElementById('princess-btn');
  btn.querySelector('.label').textContent = `Princess Mode: ${princessOn ? 'On' : 'Off'}`;
  btn.classList.toggle('btn-orange', !princessOn);
  btn.classList.toggle('btn-green', princessOn);
  log(`→ princess_mode ${princessOn}`);
  await postCommand({action: 'princess_mode', on: princessOn});
}

// ─── Per-servo control + presets (saved client-side in localStorage - no
// backend changes needed since aubie_dog.py's set_servo action already
// takes channel/angle directly) ───────────────────────────────────────────
async function setServo(channel, angle) {
  channel = channel ?? parseInt(document.getElementById('servo-channel').value);
  angle = angle ?? parseInt(document.getElementById('servo-angle').value);
  log(`→ set_servo ch${channel}=${angle}°`);
  await postCommand({action: 'set_servo', channel, angle});
}

const PRESET_KEY = 'aubie_servo_presets';

function loadPresets() {
  try { return JSON.parse(localStorage.getItem(PRESET_KEY) || '{}'); }
  catch { return {}; }
}

function refreshPresetList() {
  const presets = loadPresets();
  const names = Object.keys(presets);
  const sel = document.getElementById('preset-select');
  sel.innerHTML = '';
  if (names.length === 0) {
    sel.innerHTML = '<option value="">No presets saved</option>';
    return;
  }
  names.forEach(name => {
    const opt = document.createElement('option');
    opt.value = name;
    opt.textContent = `${name} (ch${presets[name].channel}=${presets[name].angle}°)`;
    sel.appendChild(opt);
  });
}

function savePreset() {
  const channel = parseInt(document.getElementById('servo-channel').value);
  const angle = parseInt(document.getElementById('servo-angle').value);
  const name = prompt('Name this preset:');
  if (!name) return;
  const presets = loadPresets();
  presets[name] = {channel, angle};
  localStorage.setItem(PRESET_KEY, JSON.stringify(presets));
  refreshPresetList();
  log(`✓ saved preset "${name}"`, 'ok');
}

async function applyPreset() {
  const name = document.getElementById('preset-select').value;
  if (!name) return;
  const p = loadPresets()[name];
  if (!p) return;
  document.getElementById('servo-channel').value = p.channel;
  document.getElementById('servo-angle').value = p.angle;
  document.getElementById('angle-val').textContent = p.angle + '°';
  await setServo(p.channel, p.angle);
}

function deletePreset() {
  const name = document.getElementById('preset-select').value;
  if (!name) return;
  const presets = loadPresets();
  delete presets[name];
  localStorage.setItem(PRESET_KEY, JSON.stringify(presets));
  refreshPresetList();
}

// ─── Custom poses (all 12 servos captured/replayed at once) ───────────────
const POSE_KEY = 'aubie_custom_poses';
const CHANNEL_LABELS = ['FL Hip','FL Thigh','FL Knee','FR Hip','FR Thigh','FR Knee',
                         'RL Hip','RL Thigh','RL Knee','RR Hip','RR Thigh','RR Knee'];

function loadPoses() {
  try { return JSON.parse(localStorage.getItem(POSE_KEY) || '{}'); }
  catch { return {}; }
}

function refreshPoseList() {
  const poses = loadPoses();
  const names = Object.keys(poses);
  const sel = document.getElementById('pose-select');
  sel.innerHTML = '';
  if (names.length === 0) {
    sel.innerHTML = '<option value="">No poses saved</option>';
    return;
  }
  names.forEach(name => {
    const opt = document.createElement('option');
    opt.value = name;
    opt.textContent = name;
    sel.appendChild(opt);
  });
}

// Reads back the 12 channels' current commanded angles (get_servo_angles
// RPC - sketch.ino's currentAngle[], not a physical position readback,
// there's no feedback sensor) and saves them as a named pose.
async function savePose() {
  log('→ get_servo_angles');
  let angles;
  try {
    const r = await fetch(AUBIE, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({action: 'get_servo_angles'})
    });
    const j = await r.json();
    if (!j.ok) { log(`✗ ${JSON.stringify(j)}`, 'err'); return; }
    angles = j.angles;
    log(`✓ ${angles.join(',')}`, 'ok');
  } catch(e) {
    log(`✗ ${e.message}`, 'err');
    return;
  }
  const name = prompt('Name this pose:');
  if (!name) return;
  const poses = loadPoses();
  poses[name] = angles;
  localStorage.setItem(POSE_KEY, JSON.stringify(poses));
  refreshPoseList();
  log(`✓ saved pose "${name}" (${angles.join(',')})`, 'ok');
}

// Replays a saved pose by sending one set_servo per channel - there's no
// batch RPC, so this is 12 sequential round trips rather than one atomic
// move (each channel arrives independently, not perfectly synchronized).
async function applyPose() {
  const name = document.getElementById('pose-select').value;
  if (!name) return;
  const angles = loadPoses()[name];
  if (!angles) return;
  log(`→ apply pose "${name}"`);
  for (let ch = 0; ch < angles.length; ch++) {
    await postCommand({action: 'set_servo', channel: ch, angle: angles[ch]});
  }
}

function deletePose() {
  const name = document.getElementById('pose-select').value;
  if (!name) return;
  const poses = loadPoses();
  delete poses[name];
  localStorage.setItem(POSE_KEY, JSON.stringify(poses));
  refreshPoseList();
}

// ─── RC Joystick (body lean) ───────────────────────────────────────────────
// Drag maps to {action:'lean', x, y}: x = left(-)/right(+), y = back(-)/
// forward(+), matching sketch.ino's lean(x,y) Bridge RPC. Sends are
// throttled (not logged per-frame, that'd spam the log at ~8/sec) and use a
// bare fetch rather than postCommand() for the same reason. Releasing the
// knob snaps it back to center and sends (0,0), which the firmware treats
// as an exact alias for stand() - "center returns to stand".
const JOYSTICK_RADIUS = 78;  // pad radius minus ~half the knob, in px
const JOYSTICK_SEND_INTERVAL_MS = 120;
let joystickDragging = false;
let joystickLastSentMs = 0;

async function sendLean(x, y) {
  try {
    await fetch(AUBIE, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({action: 'lean', x, y}),
    });
  } catch (e) {
    // best-effort - a dropped joystick frame isn't worth logging/spamming
  }
}

function joystickPointerMove(e) {
  const pad = document.getElementById('joystick-pad');
  const rect = pad.getBoundingClientRect();
  const cx = rect.left + rect.width / 2;
  const cy = rect.top + rect.height / 2;
  let dx = e.clientX - cx;
  let dy = e.clientY - cy;
  const dist = Math.hypot(dx, dy);
  if (dist > JOYSTICK_RADIUS) {
    dx = dx / dist * JOYSTICK_RADIUS;
    dy = dy / dist * JOYSTICK_RADIUS;
  }
  document.getElementById('joystick-knob').style.transform =
    `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px))`;

  const x = Math.round((dx / JOYSTICK_RADIUS) * 100);
  const y = Math.round((-dy / JOYSTICK_RADIUS) * 100);  // screen y is inverted - up = forward

  const now = Date.now();
  if (now - joystickLastSentMs >= JOYSTICK_SEND_INTERVAL_MS) {
    joystickLastSentMs = now;
    sendLean(x, y);
  }
}

function joystickRelease() {
  if (!joystickDragging) return;
  joystickDragging = false;
  document.getElementById('joystick-knob').style.transform = 'translate(-50%, -50%)';
  log('→ joystick released, lean center (stand)');
  sendLean(0, 0);
}

(function setupJoystick() {
  const pad = document.getElementById('joystick-pad');
  pad.addEventListener('pointerdown', (e) => {
    joystickDragging = true;
    pad.setPointerCapture(e.pointerId);
    log('→ joystick engaged');
    joystickPointerMove(e);
  });
  pad.addEventListener('pointermove', (e) => {
    if (joystickDragging) joystickPointerMove(e);
  });
  pad.addEventListener('pointerup', joystickRelease);
  pad.addEventListener('pointercancel', joystickRelease);
})();

// ─── Video Call ────────────────────────────────────────────────────────────
// Relayed through /call/ws (assistant_server.py) to aubie_dog.py's
// /call/stream - one websocket carries both video and audio, each binary
// message prefixed with a 1-byte tag: 0x56 ('V') = JPEG video frame,
// 0x41 ('A') = PCM16 mono 16kHz audio chunk. Not WebRTC - see the video-call
// plan notes for why (no aiortc/STUN/TURN infra, aubie has no public IP).
const TAG_VIDEO = 0x56, TAG_AUDIO = 0x41;
let callWs = null;
let micStream = null, micCtx = null, micSource = null, micProcessor = null;
let playCtx = null, nextPlayTime = 0;

function callWsUrl() {
  const proto = location.protocol === 'https:' ? 'wss://' : 'ws://';
  return proto + location.host + '/call/ws';
}

function downsampleTo16k(float32, inputRate, outputRate = 16000) {
  if (inputRate === outputRate) return float32;
  const ratio = inputRate / outputRate;
  const out = new Float32Array(Math.round(float32.length / ratio));
  for (let i = 0; i < out.length; i++) out[i] = float32[Math.floor(i * ratio)];
  return out;
}

function floatTo16BitPCM(float32) {
  const buf = new ArrayBuffer(float32.length * 2);
  const view = new DataView(buf);
  for (let i = 0; i < float32.length; i++) {
    const s = Math.max(-1, Math.min(1, float32[i]));
    view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return buf;
}

async function startMic() {
  micStream = await navigator.mediaDevices.getUserMedia({audio: true});
  micCtx = new (window.AudioContext || window.webkitAudioContext)();
  micSource = micCtx.createMediaStreamSource(micStream);
  // ScriptProcessorNode is deprecated but still universally supported and
  // far simpler than wiring up a separate AudioWorklet module for a feature
  // this scoped - fine here.
  micProcessor = micCtx.createScriptProcessor(4096, 1, 1);
  micProcessor.onaudioprocess = (e) => {
    if (!callWs || callWs.readyState !== WebSocket.OPEN) return;
    const input = e.inputBuffer.getChannelData(0);
    const down = downsampleTo16k(input, micCtx.sampleRate);
    const pcm = floatTo16BitPCM(down);
    const tagged = new Uint8Array(1 + pcm.byteLength);
    tagged[0] = TAG_AUDIO;
    tagged.set(new Uint8Array(pcm), 1);
    callWs.send(tagged.buffer);
  };
  micSource.connect(micProcessor);
  // Output buffer is never written to (stays silent) - this connection just
  // keeps onaudioprocess firing reliably across browsers, it does not route
  // the mic to the phone's own speaker.
  micProcessor.connect(micCtx.destination);
}

function playPcmChunk(arrayBuffer) {
  if (!playCtx) playCtx = new (window.AudioContext || window.webkitAudioContext)();
  const int16 = new Int16Array(arrayBuffer);
  const float32 = new Float32Array(int16.length);
  for (let i = 0; i < int16.length; i++) float32[i] = int16[i] / 32768;
  const buffer = playCtx.createBuffer(1, float32.length, 16000);
  buffer.copyToChannel(float32, 0);
  const src = playCtx.createBufferSource();
  src.buffer = buffer;
  src.connect(playCtx.destination);
  const now = playCtx.currentTime;
  if (nextPlayTime < now + 0.05) nextPlayTime = now + 0.15;  // initial jitter buffer
  src.start(nextPlayTime);
  nextPlayTime += buffer.duration;
}

async function onCallMessage(evt) {
  const bytes = new Uint8Array(evt.data);
  const tag = bytes[0];
  const payload = evt.data.slice(1);
  if (tag === TAG_VIDEO) {
    const bitmap = await createImageBitmap(new Blob([payload], {type: 'image/jpeg'}));
    const canvas = document.getElementById('call-canvas');
    canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close();
  } else if (tag === TAG_AUDIO) {
    playPcmChunk(payload);
  }
}

async function startCall() {
  if (callWs) return;
  try {
    await startMic();
  } catch (e) {
    log(`✗ mic access failed: ${e.message}`, 'err');
    return;
  }
  nextPlayTime = 0;
  document.getElementById('call-status').textContent = 'Connecting…';
  callWs = new WebSocket(callWsUrl());
  callWs.binaryType = 'arraybuffer';
  callWs.onopen = () => {
    document.getElementById('call-status').textContent = 'Live';
    log('✓ call connected', 'ok');
  };
  callWs.onmessage = onCallMessage;
  callWs.onerror = () => log('✗ call error', 'err');
  callWs.onclose = () => { log('call ended'); endCall(); };
}

function endCall() {
  if (callWs) { callWs.onclose = null; callWs.close(); callWs = null; }
  if (micProcessor) { micProcessor.disconnect(); micProcessor = null; }
  if (micSource) { micSource.disconnect(); micSource = null; }
  if (micStream) { micStream.getTracks().forEach(t => t.stop()); micStream = null; }
  if (micCtx) { micCtx.close(); micCtx = null; }
  document.getElementById('call-status').textContent = 'Off';
  const canvas = document.getElementById('call-canvas');
  canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
}

// ─── Teach Aubie a Person (guided enrollment) ──────────────────────────────
// Walks the person through a few head poses, capturing frames off the same
// call-canvas the RC Control video uses, and submits them all to
// /enroll_face - the server (which already has InsightFace loaded) picks
// the good ones and rejects the rest, same idea as how Face ID silently
// discards bad captures during its own guided scan.
const ENROLL_POSES = [
  'Look straight at the camera',
  'Turn your head slightly left',
  'Turn your head slightly right',
  'Tilt your chin up slightly',
  'Tilt your chin down slightly',
];
const ENROLL_FRAMES_PER_POSE = 4;
const ENROLL_POSE_MS = 2200;
let enrolling = false;

function captureCanvasFrame() {
  const canvas = document.getElementById('call-canvas');
  return new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.9));
}

async function startEnrollment() {
  const name = document.getElementById('enroll-name').value.trim();
  const statusEl = document.getElementById('enroll-status');
  if (!name) { statusEl.textContent = 'Enter a name first.'; return; }
  if (enrolling) return;
  enrolling = true;

  const wasCallActive = !!callWs;
  if (!wasCallActive) {
    statusEl.textContent = 'Starting camera…';
    await startCall();
    await new Promise(r => setTimeout(r, 800));  // let frames start arriving
  }

  const frames = [];
  for (let poseIdx = 0; poseIdx < ENROLL_POSES.length; poseIdx++) {
    statusEl.textContent = `${poseIdx + 1}/${ENROLL_POSES.length}: ${ENROLL_POSES[poseIdx]}`;
    const interval = ENROLL_POSE_MS / ENROLL_FRAMES_PER_POSE;
    for (let f = 0; f < ENROLL_FRAMES_PER_POSE; f++) {
      await new Promise(r => setTimeout(r, interval));
      const blob = await captureCanvasFrame();
      if (blob) frames.push(blob);
    }
  }
  statusEl.textContent = `Processing ${frames.length} photos…`;

  const form = new FormData();
  form.append('name', name);
  frames.forEach((blob, i) => form.append('images', blob, `frame${i}.jpg`));

  try {
    const r = await fetch('/enroll_face', { method: 'POST', body: form });
    const j = await r.json();
    if (r.ok) {
      statusEl.textContent = `✓ Learned ${j.kept} photo(s) of ${name}`;
      log(`✓ enrolled ${name}: kept ${j.kept}/${j.submitted}`, 'ok');
      loadKnownPeople();
    } else {
      statusEl.textContent = `✗ ${j.detail || 'enrollment failed'}`;
      log(`✗ enroll failed: ${JSON.stringify(j)}`, 'err');
    }
  } catch (e) {
    statusEl.textContent = `✗ ${e.message}`;
    log(`✗ enroll request failed: ${e.message}`, 'err');
  }

  if (!wasCallActive) endCall();
  enrolling = false;
}

// ─── Follow a Person ───────────────────────────────────────────────────────
async function loadKnownPeople() {
  const sel = document.getElementById('follow-select');
  try {
    const r = await fetch('/known_people');
    const j = await r.json();
    sel.innerHTML = '';
    if (!j.names || j.names.length === 0) {
      sel.innerHTML = '<option value="">No known people yet</option>';
      return;
    }
    j.names.forEach(name => {
      const opt = document.createElement('option');
      opt.value = name;
      opt.textContent = name.charAt(0).toUpperCase() + name.slice(1);
      sel.appendChild(opt);
    });
  } catch (e) {
    sel.innerHTML = '<option value="">Failed to load</option>';
  }
}

async function startFollow() {
  const name = document.getElementById('follow-select').value;
  const statusEl = document.getElementById('follow-status');
  if (!name) { statusEl.textContent = 'Pick someone first.'; return; }
  log(`→ follow start ${name}`);
  try {
    const r = await fetch('/follow/start', {
      method: 'POST',
      headers: {'Content-Type': 'application/x-www-form-urlencoded'},
      body: `name=${encodeURIComponent(name)}`,
    });
    const j = await r.json();
    if (r.ok) {
      statusEl.textContent = `Following ${name}…`;
      log(`✓ following ${name}`, 'ok');
    } else {
      statusEl.textContent = `✗ ${j.detail || 'failed to start'}`;
      log(`✗ follow start failed: ${JSON.stringify(j)}`, 'err');
    }
  } catch (e) {
    statusEl.textContent = `✗ ${e.message}`;
  }
}

async function stopFollow() {
  log('→ follow stop');
  await fetch('/follow/stop', { method: 'POST' });
  document.getElementById('follow-status').textContent = 'Not following';
}

loadKnownPeople();

refreshPresetList();
refreshPoseList();
refreshFacePresetList();

function log(msg, cls='') {
  const el = document.getElementById('log');
  const line = document.createElement('div');
  if (cls) line.className = 'log-' + cls;
  line.textContent = new Date().toLocaleTimeString() + '  ' + msg;
  el.appendChild(line);
  el.scrollTop = el.scrollHeight;
  if (el.children.length > 60) el.removeChild(el.children[0]);
}

async function ping() {
  try {
    const r = await fetch('/health', {signal: AbortSignal.timeout(3000)});
    document.getElementById('dot').className = r.ok ? 'dot online' : 'dot';
    document.getElementById('status-text').textContent = r.ok ? 'online' : 'server error';
  } catch {
    document.getElementById('dot').className = 'dot';
    document.getElementById('status-text').textContent = 'offline';
  }
}
ping();
setInterval(ping, 10000);

// At-a-glance tilt readout in the header, polling imu_read (not the
// full-screen calibration_mode) so this stays lightweight and doesn't
// disturb the face/TFT.
async function pollTilt() {
  try {
    const r = await fetch(AUBIE, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({action: 'imu_read'}),
      signal: AbortSignal.timeout(3000),
    });
    const j = await r.json();
    if (j.ok) {
      const p = j.imu.pitch_deg.toFixed(1);
      const ro = j.imu.roll_deg.toFixed(1);
      document.getElementById('tilt-text').textContent = `P:${p} R:${ro}`;
    }
  } catch {
    document.getElementById('tilt-text').textContent = '';
  }
}
pollTilt();
setInterval(pollTilt, 2000);
</script>
</body>
</html>
"""


@router.get("/remote", response_class=HTMLResponse)
async def phone_remote():
    return HTMLResponse(content=HTML)


# ─── Proxy endpoint (avoids CORS from phone browser) ─────────────────────────
import httpx
from fastapi import Request
from fastapi.responses import JSONResponse

@router.post("/proxy/dog")
async def proxy_dog(request: Request):
    body = await request.json()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{AUBIE_URL}/dog/command", json=body)
        return JSONResponse(r.json(), status_code=r.status_code)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)


@router.get("/health")
async def health():
    return {"status": "ok"}

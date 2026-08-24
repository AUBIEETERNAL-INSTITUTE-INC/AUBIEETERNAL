// -----------------------------------------------------------------------
// >>> LIVE, DEPLOYED COPY <<< On the robot this is ~/spotmicro_dog/sketch/ -
// edited there directly (or synced from this repo checkout) and flashed via
// `arduino-app-cli app restart spotmicro_dog`. Do NOT confuse with
// ~/ArduinoApps/spotmicro_dog/sketch/ on the robot - that's a stale,
// unregistered leftover from initial app setup, NOT what actually runs
// (confirmed 2026-08-17: it was missing rest()/lean()/the IWDG watchdog/
// current servo calibration - i.e. genuinely old, not a mirror).
// -----------------------------------------------------------------------
// SpotMicro dog - MCU sketch (STM32U585 / Zephyr side of the UNO Q)
//
// Hardware:
//   - PCA9685 servo driver, addr 0x40, on Wire1 / ModulinoHub port 1
//     (Qwiic hub) -> 12x MG996R. Originally on Wire (header SDA/SCL), moved
//     to Wire1 to work around arduino/ArduinoCore-zephyr#301 - see the
//     PCA9685 driver section below.
//       channels 0-2  = FL (hip, thigh, knee)
//       channels 3-5  = FR
//       channels 6-8  = RL
//       channels 9-11 = RR
//   - Modulino Movement (LSM6DSOX IMU) on Wire1 (Qwiic connector)
//   - 2x Modulino Distance (ToF) on Wire1/hub ports 4-5 (distRightEar,
//     distLeftEar) - the SONAR_COUNT/sonarTrigPins/sonarEchoPins array
//     further down is DEAD CODE: HC-SR04-style GPIO trig/echo pins that
//     were only ever placeholders, never actually wired to real hardware
//     (confirmed 2026-08-18) - a 360 LiDAR is expected 2026-08-19 for a
//     planned 3D-mapping feature, which may replace this array entirely
//     rather than it ever getting real HC-SR04s.
//   - ILI9341 TFT (face) + XPT2046 resistive touch (CS=D4, IRQ=D3)
//   - 2x PAM8302A-class mono Class D amp + speaker boards (5V/GND power),
//     signal on pins 5 (left) / 6 (right) - reuses the otherwise-unwired
//     sonarEchoPins slots above, see test_speakers() for the diagnostic
//   - MAX9814 electret mic module (onboard AGC, low THD), 5V/GND power,
//     OUT -> A0, GAIN pin left floating (module default = 60dB) - analog-pin
//     replacement for the old USB EMEET mic, see test_mic() for the diagnostic
//   - FHL-LD19 360deg LiDAR (12m range, UART), 5V/GND power, TX -> D0
//     (Serial1 RX - see LD19 section for why D0 has real UART despite the
//     digital-pin-gpios table), PWM -> D3 (held LOW, internal speed control)
//
// Bridge RPCs exposed to the Linux/Python side:
//   set_servo(channel, angle), read_imu(), read_sonar(sensor_id),
//   imu_read(), calibration_mode(on),
//   stand(), sit(), rest(), lean(x, y), walk_forward(), turn_left(), turn_right(),
//   face_talk(), face_idle(), face-text(text), touch_check(),
//   face_config(eyeShape, mouthShape, eyeColor565, mouthColor565), flashlight(on),
//   sonar_front_left(), sonar_front_right(), sonar_right_ear(), sonar_left_ear(),
//   play_pong(on) - idle "find your own fun" Pong attract-mode demo
//   test_speakers() - diagnostic beep on the 2x PAM8302A-class amp+speaker
//     boards wired to pins 5 (left) / 6 (right)
//   test_mic() - diagnostic peak-to-peak read of the MAX9814 mic on A0
//   test_lidar() - running count of valid LD19 packets received so far
//     (serviceLidar(), called from loop(), does the actual draining/parsing)
//   get_lidar_scan() - live 360deg scan, 36 buckets @ 10deg resolution, CSV
//     of integer cm distances (-1 = no reading), for the phone UI radar view
//
// loop() also runs updateProximityPulse() (face.ino) unconditionally - it
// pulses a red TFT border when any range sensor sees an object under 20cm,
// no RPC needed to enable it.
//
// Bridge-provided functions must return quickly (Arduino guidance: keep RPC
// handlers non-blocking, drive anything long-running as a state machine in
// loop()). So stand()/sit()/walk_forward() only arm a target pose or gait
// and return immediately; the actual servo motion is interpolated frame by
// frame inside loop().
// -----------------------------------------------------------------------

#include "Arduino_RouterBridge.h"
#include <Wire.h>
#include <Arduino_Modulino.h>

// ---- I2C presence check ---------------------------------------------
// This board's Wire::endTransmission() calls Zephyr's i2c_write() directly
// with no software timeout of its own. If a configured I2C device (PCA9685,
// Modulino IMU) never ACKs - unplugged, miswired, or in a bad power state -
// the call can block setup() forever, or wedge the bus so nothing else on
// that bus recovers without a physical power-cycle. Scanning first and
// skipping absent peripherals avoids ever making that blocking call.
bool i2cDevicePresent(TwoWire &wire, uint8_t addr) {
  wire.beginTransmission(addr);
  return wire.endTransmission() == 0;
}

bool pca9685Present = false;
bool imuPresent = false;
extern bool faceSetupDone;  // set at the end of faceSetup(), in face.ino

// Declared here (ahead of the IMU/distance sensors further down) because
// the PCA9685 driver functions below need it too, via hub.select().
ModulinoHub hub;

// ---- PCA9685 low-level driver (Wire1 / ModulinoHub Qwiic mux) ----------
// Originally on the board's default `Wire` (header SDA/SCL), but that bus
// silently fails on real data writes on this UNO Q - a documented Zephyr
// core bug (arduino/ArduinoCore-zephyr#301): endTransmission() returns
// DATA_TOO_LONG(1) for any write with payload bytes, even though a bare
// address probe succeeds. Wire1 (the Qwiic hub the IMU/distance sensors
// already use) doesn't have this bug, so the PCA9685 moved there too -
// on the physical side, its SDA/SCL now go to hub port PCA9685_HUB_PORT
// instead of the header pins.
const int PCA9685_HUB_PORT = 1;  // 0/4/5 already used by IMU/dist sensors

const uint8_t PCA9685_ADDR       = 0x40;
const uint8_t PCA9685_MODE1      = 0x00;
const uint8_t PCA9685_PRESCALE   = 0xFE;
const uint8_t PCA9685_LED0_ON_L  = 0x06;
const float   PCA9685_FREQ_HZ    = 50.0f;   // standard hobby servo rate

// Pulse-width range for MG996R. TODO: verify/trim per servo on your build.
const int SERVO_MIN_US = 500;
const int SERVO_MAX_US = 2500;

void pca9685WriteReg(uint8_t reg, uint8_t value) {
  hub.select(PCA9685_HUB_PORT);
  Wire1.beginTransmission(PCA9685_ADDR);
  Wire1.write(reg);
  Wire1.write(value);
  Wire1.endTransmission();
}

uint8_t pca9685ReadReg(uint8_t reg) {
  hub.select(PCA9685_HUB_PORT);
  Wire1.beginTransmission(PCA9685_ADDR);
  Wire1.write(reg);
  Wire1.endTransmission(false);
  Wire1.requestFrom((int)PCA9685_ADDR, 1);
  return Wire1.available() ? Wire1.read() : 0;
}

void pca9685Init() {
  pca9685WriteReg(PCA9685_MODE1, 0x00);
  delay(5);
  uint8_t prescale = (uint8_t)(round(25000000.0 / (4096.0 * PCA9685_FREQ_HZ)) - 1);
  uint8_t oldmode = pca9685ReadReg(PCA9685_MODE1);
  pca9685WriteReg(PCA9685_MODE1, (oldmode & 0x7F) | 0x10);  // sleep to set prescale
  pca9685WriteReg(PCA9685_PRESCALE, prescale);
  pca9685WriteReg(PCA9685_MODE1, oldmode);
  delay(5);
  pca9685WriteReg(PCA9685_MODE1, oldmode | 0xA1);  // restart, auto-increment, all-call
}

void pca9685SetPWM(uint8_t channel, uint16_t on, uint16_t off) {
  hub.select(PCA9685_HUB_PORT);
  Wire1.beginTransmission(PCA9685_ADDR);
  Wire1.write(PCA9685_LED0_ON_L + 4 * channel);
  Wire1.write(on & 0xFF);
  Wire1.write(on >> 8);
  Wire1.write(off & 0xFF);
  Wire1.write(off >> 8);
  Wire1.endTransmission();
}

uint16_t angleToTicks(int angle) {
  angle = constrain(angle, 0, 180);
  long pulse_us = map(angle, 0, 180, SERVO_MIN_US, SERVO_MAX_US);
  return (uint16_t)((pulse_us * 4096L) / 20000L);  // 20000us period @ 50Hz
}

void writeServoAngle(uint8_t channel, int angle) {
  if (!pca9685Present) return;  // no board ACKed at boot - avoid touching the bus
  pca9685SetPWM(channel, 0, angleToTicks(angle));
}

// ---- PCA9685 liveness re-check --------------------------------------------
// pca9685Present is otherwise only ever set once, at boot. If the board is
// unplugged/loses power mid-session (very possible while it's being
// rewired), every writeServoAngle() call after that keeps blindly attempting
// I2C writes to a device that's no longer there - and per the i2cDevicePresent()
// comment above, this core's Wire::endTransmission() has no software timeout,
// so an unresponsive device can hang the write instead of failing fast.
// Periodically re-probing and clearing pca9685Present the moment it goes
// quiet stops future writes from being attempted; it can't undo a hang
// that's already in progress from the exact instant it disconnected, but it
// closes the far more likely window (idle time between commands).
const unsigned long PCA9685_RECHECK_MS = 2000;
unsigned long lastPca9685CheckMs = 0;

void updatePca9685Liveness() {
  if (!pca9685Present) return;
  unsigned long now = millis();
  if (now - lastPca9685CheckMs < PCA9685_RECHECK_MS) return;
  lastPca9685CheckMs = now;

  hub.select(PCA9685_HUB_PORT);
  if (!i2cDevicePresent(Wire1, PCA9685_ADDR)) {
    pca9685Present = false;
  }
}

// ---- Leg geometry / calibration ----------------------------------------
// Channel layout per leg: [hip, thigh, knee]. Legs: 0=FL, 1=FR, 2=RL, 3=RR.
// These are starting points, not measured values - tune them against your
// physical assembly before trusting stand()/sit()/walk_forward().
const int HIP_NEUTRAL_DEG  = 90;
const int THIGH_STAND_DEG  = 90;
const int KNEE_STAND_DEG   = 90;
const int THIGH_SIT_DEG    = 40;
const int KNEE_SIT_DEG     = 150;
const int THIGH_SWING_DEG  = 110;  // leg swung forward, lifted
const int KNEE_SWING_DEG   = 60;
const int THIGH_STANCE_DEG = 70;   // leg driving the body forward, planted
const int KNEE_STANCE_DEG  = 100;

// Per-leg stand calibration. Re-measured live on 2026-08-14 via the phone
// UI's Custom Poses tool (hand-jogged to a proper fully-erect stand, saved,
// then read back via get_servo_angles) - supersedes the 2026-08-13 values,
// which no longer matched the assembly after the servo/hip troubleshooting
// earlier today.
// UPDATE 2026-08-16: FR's hip override dropped back to the generic 90 -
// all four hip horns were freshly re-centered by hand (rear hips were
// drifting/binding, suspected servo fault), so every hip - FL/FR/RL/RR -
// now shares HIP_NEUTRAL_DEG instead of FR having its own offset.
const int FL_THIGH_STAND_DEG = 98;
const int FL_KNEE_STAND_DEG  = 142;
const int FR_HIP_STAND_DEG   = 90;
const int FR_THIGH_STAND_DEG = 92;
const int FR_KNEE_STAND_DEG  = 44;
const int RL_THIGH_STAND_DEG = 132;
const int RL_KNEE_STAND_DEG  = 130;
const int RR_THIGH_STAND_DEG = 50;
const int RR_KNEE_STAND_DEG  = 61;

const int STAND_POSE[12] = {
  HIP_NEUTRAL_DEG,  FL_THIGH_STAND_DEG, FL_KNEE_STAND_DEG,   // FL
  FR_HIP_STAND_DEG, FR_THIGH_STAND_DEG, FR_KNEE_STAND_DEG,   // FR
  HIP_NEUTRAL_DEG,  RL_THIGH_STAND_DEG, RL_KNEE_STAND_DEG,   // RL
  HIP_NEUTRAL_DEG,  RR_THIGH_STAND_DEG, RR_KNEE_STAND_DEG    // RR
};

// Re-measured live on 2026-08-14 via the phone UI's Custom Poses tool -
// now a genuinely distinct pose from STAND_POSE (previously sit() just
// mirrored stand() - see git history - because the generic fold values
// didn't match this assembly and no one had re-tuned a real sit yet).
const int SIT_POSE[12] = {
  90,  157, 66,    // FL
  90,  25,  142,   // FR
  90,  167, 104,   // RL
  90,  15,  180    // RR
};

// Folded resting pose (legs tucked, minimal load-bearing) - measured live
// via set_servo/get_servo_angles against the physical assembly, the same
// way STAND_POSE/SIT_POSE were. This is the boot default now (see
// setup()): the robot no longer auto-stands on power-up, it eases into
// this pose instead and waits for an explicit stand/sit command. Not
// derived from the per-leg *_STAND_DEG constants above since each leg's
// hand-tucked fold direction doesn't follow a uniform offset from its
// stand angle. Re-measured 2026-08-14 (second pass, supersedes the first
// 2026-08-14 values) to a pose the user preferred better in practice.
const int REST_POSE[12] = {
  90,  105, 127,   // FL
  90,  81,  59,    // FR
  90,  137, 116,   // RL
  90,  45,  75     // RR
};

// Crouched walking stance - measured live on 2026-08-14 via the phone UI's
// Custom Poses tool (hand-jogged to a ready-to-step crouch, like the
// SpotMicro reference videos, rather than walking from the fully-erect
// STAND_POSE). This is the STANCE baseline for walk_forward() below.
const int WALK_NEUTRAL_POSE[12] = {
  90,  160, 50,     // FL
  90,  25,  154,    // FR
  90,  155, 35,     // RL
  90,  28,  157     // RR
};

// Same left/right mirroring confirmed for STAND_POSE/REST_POSE (FL/RL share
// one servo-horn convention, FR/RR the opposite) - comparing this crouch to
// STAND_POSE per leg shows thigh/knee both shift the same side-signed
// direction going stand->crouch, so SWING (foot lifted, reaching forward)
// is built as a further step in that same direction from WALK_NEUTRAL_POSE,
// scaled down from the full crouch depth. Magnitude is a first guess -
// unverified against the physical robot, same caveat as turn_left/right.
const int WALK_SIDE_SIGN[4] = { 1, -1, 1, -1 };  // FL, FR, RL, RR
const int WALK_SWING_THIGH_DELTA = 20;  // reach forward during swing
const int WALK_SWING_KNEE_DELTA  = -25; // more bent (higher lift) during swing

// Basic 2-phase trot: diagonal pairs (FL,RR) and (FR,RL) alternate
// swing/stance. GAIT_KEYFRAME[phase][channel].
int GAIT_KEYFRAME[2][12];

void buildGaitKeyframes() {
  for (int phase = 0; phase < 2; phase++) {
    bool diag1SwingForward = (phase == 0);
    for (int leg = 0; leg < 4; leg++) {
      bool isDiag1 = (leg == 0 || leg == 3);  // FL, RR
      bool swinging = (isDiag1 == diag1SwingForward);
      int thighBase = WALK_NEUTRAL_POSE[leg * 3 + 1];
      int kneeBase  = WALK_NEUTRAL_POSE[leg * 3 + 2];
      int thigh = swinging ? thighBase + WALK_SIDE_SIGN[leg] * WALK_SWING_THIGH_DELTA : thighBase;
      int knee  = swinging ? kneeBase  + WALK_SIDE_SIGN[leg] * WALK_SWING_KNEE_DELTA  : kneeBase;
      // Hip target is each leg's own calibrated STAND_POSE hip angle. All
      // four hips share HIP_NEUTRAL_DEG (90) as of 2026-08-16 - FR previously
      // had its own override, dropped after all hip horns were re-centered
      // by hand (rear hips were drifting/binding, suspected servo fault).
      // In practice this is currently moot anyway - beginGaitStep() (see
      // below) freezes all 4 hips at their current position during any
      // gait step regardless of what's written here, per live request
      // while a hip servo is suspected faulty.
      GAIT_KEYFRAME[phase][leg * 3 + 0] = STAND_POSE[leg * 3 + 0];
      GAIT_KEYFRAME[phase][leg * 3 + 1] = constrain(thigh, 0, 180);
      GAIT_KEYFRAME[phase][leg * 3 + 2] = constrain(knee, 0, 180);
    }
  }
}

// ---- Turning ---------------------------------------------------------
// This gait has no hip-driven yaw (hips sit at HIP_NEUTRAL_DEG throughout
// walk_forward() too, above), so turning instead comes from making the
// inner-side legs travel a shorter stride than the outer side each step -
// scale their thigh/knee swing toward the STANCE angle by TURN_INNER_SCALE
// rather than going all the way to the full SWING angle. Direction/
// magnitude here is a first guess, same trust level as the existing
// generic (non-per-leg-calibrated) SWING/STANCE walk_forward() gait it's
// built from - NOT yet verified against the physical robot. Test
// turn_left()/turn_right() manually (phone UI buttons) before trusting
// them in anything autonomous like a follow loop.
const float TURN_INNER_SCALE = 0.35f;  // inner-side legs travel this fraction of the normal stride
int TURN_LEFT_KEYFRAME[2][12];
int TURN_RIGHT_KEYFRAME[2][12];

void buildTurnKeyframes() {
  for (int phase = 0; phase < 2; phase++) {
    bool diag1SwingForward = (phase == 0);
    for (int leg = 0; leg < 4; leg++) {
      bool isDiag1 = (leg == 0 || leg == 3);  // FL, RR
      bool swinging = (isDiag1 == diag1SwingForward);
      bool isLeftSide = (leg == 0 || leg == 2);  // FL, RL

      int fullThigh = swinging ? THIGH_SWING_DEG : THIGH_STANCE_DEG;
      int fullKnee  = swinging ? KNEE_SWING_DEG  : KNEE_STANCE_DEG;

      int leftThigh  = isLeftSide ? (int)round(THIGH_STANCE_DEG + (fullThigh - THIGH_STANCE_DEG) * TURN_INNER_SCALE) : fullThigh;
      int leftKnee   = isLeftSide ? (int)round(KNEE_STANCE_DEG  + (fullKnee  - KNEE_STANCE_DEG)  * TURN_INNER_SCALE) : fullKnee;
      int rightThigh = !isLeftSide ? (int)round(THIGH_STANCE_DEG + (fullThigh - THIGH_STANCE_DEG) * TURN_INNER_SCALE) : fullThigh;
      int rightKnee  = !isLeftSide ? (int)round(KNEE_STANCE_DEG  + (fullKnee  - KNEE_STANCE_DEG)  * TURN_INNER_SCALE) : fullKnee;

      // Hip target is each leg's own calibrated STAND_POSE hip angle - see
      // the matching comment in buildGaitKeyframes() above.
      TURN_LEFT_KEYFRAME[phase][leg * 3 + 0]  = STAND_POSE[leg * 3 + 0];
      TURN_LEFT_KEYFRAME[phase][leg * 3 + 1]  = leftThigh;
      TURN_LEFT_KEYFRAME[phase][leg * 3 + 2]  = leftKnee;

      TURN_RIGHT_KEYFRAME[phase][leg * 3 + 0] = STAND_POSE[leg * 3 + 0];
      TURN_RIGHT_KEYFRAME[phase][leg * 3 + 1] = rightThigh;
      TURN_RIGHT_KEYFRAME[phase][leg * 3 + 2] = rightKnee;
    }
  }
}

// ---- Non-blocking pose/gait transition engine (runs from loop()) -------

// Was 350ms - fine for the old, smaller-swing calibration, but with the
// 2026-08-14 hand-tuned STAND_POSE some channels now travel 100+ degrees
// between poses (e.g. rest->stand), and 350ms across that distance moved
// fast enough to nearly tip the robot over (reported live). Slowed down
// substantially for stand()/sit()/rest()/the post-gait settle - walking's
// own per-step timing (GAIT_STEP_MS) is unrelated and untouched.
const unsigned long POSE_TRANSITION_MS = 900;
const unsigned long GAIT_STEP_MS       = 300;
const int GAIT_STEPS_PER_CALL          = 4;  // half-steps advanced per walk_forward()

float currentAngle[12];
int transitionStart[12];
int transitionTarget[12];
unsigned long transitionStartMs = 0;
unsigned long transitionDurationMs = 0;

bool walking = false;
int gaitPhase = 0;
int gaitStepsRemaining = 0;
// Which keyframe table the current gait is stepping through - lets
// walk_forward()/turn_left()/turn_right() all share one state machine
// (gaitPhase/gaitStepsRemaining/onTransitionComplete) instead of each
// needing its own copy of it.
int (*activeGaitKeyframe)[12] = GAIT_KEYFRAME;

void beginTransition(const int* target, unsigned long durationMs) {
  for (int i = 0; i < 12; i++) transitionStart[i] = (int)round(currentAngle[i]);
  memcpy(transitionTarget, target, sizeof(transitionTarget));
  transitionStartMs = millis();
  transitionDurationMs = durationMs;
}

// Requested live (2026-08-14): a hip servo is suspected faulty and
// replacements are on order, so every gait-driven move (stepping AND the
// auto-settle back to stand at the end of a walk/turn) leaves all 4 hip
// channels exactly wherever they currently are instead of driving them
// toward the keyframe's baked-in hip target - walking/turning only
// actually needs thigh+knee. Explicit stand()/sit()/rest()/lean() calls are
// deliberate full-pose commands, not stepping, and still move the hips.
int gaitStepPose[12];

void beginGaitStep(const int* keyframe, unsigned long durationMs) {
  memcpy(gaitStepPose, keyframe, sizeof(gaitStepPose));
  for (int leg = 0; leg < 4; leg++) {
    int hipCh = leg * 3;
    int hipAngle = (int)round(currentAngle[hipCh]);
    gaitStepPose[hipCh] = hipAngle;
    // updateTransition() skips writeServoAngle() whenever the interpolated
    // angle equals currentAngle - and since the hip target here is
    // deliberately set to currentAngle itself (frozen, not driven to a new
    // position), that check never trips for hips, so they never get an
    // actual PWM write and sit with no holding torque instead of being held
    // firmly like every other joint (confirmed live 2026-08-16: hips limp
    // on boot, everything else firm - this fires on every gait step/settle
    // too, not just boot, since they all go through beginGaitStep()).
    // Writing it explicitly here restores holding torque without changing
    // the freeze itself.
    writeServoAngle(hipCh, hipAngle);
  }
  beginTransition(gaitStepPose, durationMs);
}

void onTransitionComplete() {
  if (walking) {
    if (gaitStepsRemaining > 0) {
      gaitStepsRemaining--;
      gaitPhase = 1 - gaitPhase;
      beginGaitStep(activeGaitKeyframe[gaitPhase], GAIT_STEP_MS);
    } else {
      walking = false;
      // Settles back into the crouched walk stance, not a pop-up to full
      // stand - changed live 2026-08-14 after the erect settle was
      // reported as a jarring transition right after a walk sequence ends.
      beginGaitStep(WALK_NEUTRAL_POSE, POSE_TRANSITION_MS);
    }
  }
}

void updateTransition() {
  unsigned long elapsed = millis() - transitionStartMs;
  float t = (transitionDurationMs == 0) ? 1.0f : (float)elapsed / (float)transitionDurationMs;
  if (t > 1.0f) t = 1.0f;

  bool justFinished = (transitionDurationMs != 0) && (t >= 1.0f);

  for (int i = 0; i < 12; i++) {
    float angle = transitionStart[i] + (transitionTarget[i] - transitionStart[i]) * t;
    if ((int)round(angle) != (int)round(currentAngle[i])) {
      writeServoAngle(i, (int)round(angle));
    }
    currentAngle[i] = angle;
  }

  if (justFinished) {
    transitionDurationMs = 0;  // avoid re-firing onTransitionComplete every loop tick
    onTransitionComplete();
  }
}

// ---- Stand-loop tilt compensation ---------------------------------------
// Bring-up is happening one joint at a time (hip, then thigh, then knee), so
// this only drives the hip channels for now, and it nudges all four by the
// same amount rather than a proper per-leg differential - good enough to see
// the loop react to tilt, not a real balance controller yet.
const unsigned long TILT_COMP_INTERVAL_MS = 100;   // ~10 Hz IMU poll
const float TILT_COMP_GAIN    = 0.3f;              // start conservative
const float TILT_COMP_MAX_DEG = 15.0f;             // clamp a bad reading before it reaches a servo
const uint8_t HIP_CHANNELS[4] = { 0, 3, 6, 9 };    // FL, FR, RL, RR

// Only true once stand() has been explicitly called, and cleared by sit()
// or any manual set_servo() - transitionDurationMs==0 alone isn't a
// reliable "actually standing" signal (it's also true at boot and after
// every manual override), so without this the tilt loop would fight manual
// bring-up commands, snapping a hand-set hip angle back toward level a
// fraction of a second later.
bool standActive = false;

unsigned long lastTiltCompMs = 0;

void updateStandTiltCompensation() {
  // Only correct while actually standing and settled - mid-transition or
  // mid-gait the hip targets are already changing for other reasons.
  if (!imuPresent || !standActive || walking || transitionDurationMs != 0) return;

  unsigned long now = millis();
  if (now - lastTiltCompMs < TILT_COMP_INTERVAL_MS) return;
  lastTiltCompMs = now;

  float pitchDeg, rollDeg;
  imu(pitchDeg, rollDeg);

  float error = pitchDeg + rollDeg;
  float correction = constrain(error * TILT_COMP_GAIN, -TILT_COMP_MAX_DEG, TILT_COMP_MAX_DEG);
  int hipAngle = constrain((int)round(HIP_NEUTRAL_DEG + correction), 0, 180);

  for (int i = 0; i < 4; i++) {
    uint8_t ch = HIP_CHANNELS[i];
    if (hipAngle != (int)round(currentAngle[ch])) {
      writeServoAngle(ch, hipAngle);
      currentAngle[ch] = hipAngle;
    }
  }
}

// ---- HC-SR04 ultrasonic sensors -----------------------------------------
// sensor_id: 0 = front-left, 1 = front-right, 2 = back.
// NOTE: originally D4/D8/D12/D13 - those collide with the TFT/touch SPI
// bus (D8=TFT_RST, D12=SPI MISO, D13=SPI SCK, D4=touch CS - see face.ino).
// pinMode() on those pins during setup() was stomping the SPI lines before
// faceSetup() ever ran, which is why the display came up white. Moved to
// pins outside the SPI bus and the touch/TFT control pins.
// TODO: still placeholders otherwise - match to actual wiring.
const int SONAR_COUNT = 3;
const uint8_t sonarTrigPins[SONAR_COUNT] = { 2, 7, 20 };
const uint8_t sonarEchoPins[SONAR_COUNT] = { 5, 21, 6 };

// pulseIn()'s own timeout has been observed not to reliably terminate on
// this core when the echo pin never toggles (no sensor connected) - it can
// block Bridge RPC dispatch (single-threaded, serialized over one link) far
// past the requested timeout. This enforces the deadline directly against
// micros() so it always returns, sensor connected or not.
unsigned long safePulseIn(uint8_t pin, uint8_t state, unsigned long timeout_us) {
  unsigned long startWait = micros();
  while (digitalRead(pin) != state) {
    if (micros() - startWait > timeout_us) return 0;
  }
  unsigned long startPulse = micros();
  while (digitalRead(pin) == state) {
    if (micros() - startPulse > timeout_us) return 0;
  }
  return micros() - startPulse;
}

float readSonarCm(int sensorId) {
  uint8_t trig = sonarTrigPins[sensorId];
  uint8_t echo = sonarEchoPins[sensorId];
  digitalWrite(trig, LOW);
  delayMicroseconds(2);
  digitalWrite(trig, HIGH);
  delayMicroseconds(10);
  digitalWrite(trig, LOW);
  unsigned long duration_us = safePulseIn(echo, HIGH, 30000UL);  // 30ms timeout ~5m range
  if (duration_us == 0) return -1.0f;                             // no echo / out of range
  return duration_us / 58.0f;
}

// ---- Speaker test (2x PAM8302A-class amp+speaker boards) ----------------
// Added 2026-08-18. Signal pins reuse sonarEchoPins[0]/[2] (5 and 6) above -
// confirmed safe: the real distance sensors are the Modulino Distance (ToF,
// Qwiic/Wire1) boards read via distRightEar/distLeftEar in setup(), not
// these HC-SR04-style trig/echo pins, which per the TODO on SONAR_COUNT
// above were only ever placeholders never actually wired to hardware.
// tone()/noTone() on this core (Tone.cpp) call pinMode(OUTPUT) internally
// per-call and run off an independent Zephyr k_timer per pin, so this
// doesn't block loop() or fight the pinMode(INPUT) the dead sonar setup
// code still does on these same pins at boot.
const uint8_t SPEAKER_L_PIN = 5;
const uint8_t SPEAKER_R_PIN = 6;

// One-shot diagnostic: beeps the left channel, then the right, then both
// together, so each amp/speaker can be confirmed working independently
// before relying on them. Intentionally blocking (~1.1s total) - this is a
// manually-triggered diagnostic, not part of the hot loop, same allowance
// as other one-off bring-up commands in this file.
bool test_speakers() {
  tone(SPEAKER_L_PIN, 440, 300);   // A4, left only
  delay(350);
  tone(SPEAKER_R_PIN, 440, 300);   // A4, right only
  delay(350);
  tone(SPEAKER_L_PIN, 523, 400);   // C5, both together
  tone(SPEAKER_R_PIN, 523, 400);
  delay(450);
  return true;
}

// ---- Mic test (MAX9814 electret w/ onboard AGC) --------------------------
// Added 2026-08-19. VCC->5V, GND->GND, OUT->A0, GAIN pin left floating
// (module default gain, 60dB). Analog-pin replacement for the old USB EMEET
// mic, part of moving audio I/O off USB entirely - see test_speakers() above
// for the amp/speaker half of the same effort.
const uint8_t MIC_PIN = A0;

// One-shot diagnostic: samples OUT over a short window and returns the
// peak-to-peak swing seen around the module's biased-DC output. Silence
// reads near 0; speech/clapping near the mic should show a clear swing.
// Intentionally blocking (~50ms) - same one-off diagnostic allowance as
// test_speakers(), not part of the hot loop.
float test_mic() {
  uint16_t lo = 65535, hi = 0;
  unsigned long start = millis();
  while (millis() - start < 50) {
    uint16_t v = analogRead(MIC_PIN);
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  return (float)(hi - lo);
}

// ---- LD19 LiDAR (360 deg, 12m DTOF, UART) --------------------------------
// Added 2026-08-19. VCC->5V, GND->GND, TX->D0, PWM->D3. D0/D1 look like
// plain GPIO in this board's digital-pin-gpios/pwm devicetree tables, but
// usart1's pinctrl (checked directly in the compiled board .dts) claims
// those same physical pins for its UART alternate function, and the core's
// zephyrSerial.h naming logic resolves usart1 to the Arduino object
// "Serial1" - so Serial1.begin() below is real hardware UART on D0/D1, not
// a placeholder. PWM pin left as a floating INPUT (true Hi-Z) in setup()
// rather than driven with a real signal - the datasheet says internal/fixed
// motor speed control kicks in when this pin is "not connected or Hi-Z",
// avoiding the need to generate a precise external 20-50kHz PWM. A driven
// LOW output is a different electrical state and was tried first (wrong -
// see 2026-08-19 debugging session).
//
// Packet format: 230400 baud 8N1, 47-byte packets, 12 points each:
//   [0]      header, always 0x54
//   [1]      verlen, always 0x2C (low 5 bits = 12 points)
//   [2-3]    speed, deg/s, LSB first
//   [4-5]    start_angle, 0.01 deg units, LSB first
//   [6-41]   12x (distance_mm: 2 bytes LSB first, intensity: 1 byte)
//   [42-43]  end_angle, 0.01 deg units, LSB first
//   [44-45]  timestamp_ms, LSB first
//   [46]     CRC8 of bytes [0-45]
// CRC8 (poly 0x4D, MSB-first, init 0) is computed bit-by-bit rather than
// from a hardcoded 256-entry lookup table copied off the internet, to avoid
// trusting a possibly-mistyped table - verified this exact algorithm by
// hand against the datasheet's own published first few table entries
// (0x00, 0x4D, 0x9A for input bytes 0, 1, 2) before trusting it.
const uint8_t LIDAR_PWM_PIN = 3;
const uint8_t LIDAR_PACKET_LEN = 47;

// 2026-08-19 debugging saga (see git history / session notes for the full
// story): a raw Zephyr uart_err_check() workaround and a D0/D1 loopback
// test were both tried and removed again - turned out the real cause of
// "zero bytes ever received" was a bad physical connection (crimp/wire),
// not software. Confirmed fixed via an isolated test app (ld19_test, no
// I2C/servo/TFT load) once the wiring was corrected: ~415 valid
// packets/sec, 99.5% valid-framing rate, no errors, no hangs. This is that
// same, now-proven-working approach ported into the main sketch.
uint8_t lidarCrc8(const uint8_t *data, uint8_t len) {
  uint8_t crc = 0;
  for (uint8_t i = 0; i < len; i++) {
    crc ^= data[i];
    for (uint8_t bit = 0; bit < 8; bit++) {
      crc = (crc & 0x80) ? (uint8_t)((crc << 1) ^ 0x4D) : (uint8_t)(crc << 1);
    }
  }
  return crc;
}

long lidarBytesSeen = 0;
long lidarValidPackets = 0;
float lidarNearestDistanceMm = -1;

// Live 360-degree scan, 36 buckets at 10-degree resolution (coarser than
// the LD19's native ~1-degree resolution, deliberately - keeps
// get_lidar_scan()'s CSV payload under the Bridge's ~235-byte String limit
// in a single RPC call, no chunking needed). Each bucket always holds the
// MOST RECENT reading for that angular slice - there's no "full revolution
// complete" concept here, it's continuously live-updating, same idea as a
// radar sweep display. -1 = no reading yet for that bucket.
// NOTE: angle 0 = whatever direction the LD19 is physically mounted facing
// (per its own datasheet, "front of sensor" = 0deg/x-axis, clockwise) - not
// yet calibrated against the robot's own front-facing direction.
const int LIDAR_SCAN_BUCKETS = 36;
float lidarScanCm[LIDAR_SCAN_BUCKETS];

// Drains whatever's currently buffered on Serial1 - bounded by however much
// has actually arrived since the last call, never waits. Called once per
// loop() iteration (see loop() below) so the main sketch's servo/TFT/I2C
// work never blocks on LiDAR data, and the LD19's continuous stream gets
// serviced in small increments instead of one big blocking scan (the
// approach that caused a hang before real data was flowing).
void serviceLidar() {
  uint8_t buf[LIDAR_PACKET_LEN];
  while (Serial1.available() > 0) {
    if (Serial1.peek() != 0x54) { Serial1.read(); lidarBytesSeen++; continue; }
    if (Serial1.available() < LIDAR_PACKET_LEN) break;  // rest hasn't arrived yet
    for (int i = 0; i < LIDAR_PACKET_LEN; i++) buf[i] = Serial1.read();
    lidarBytesSeen += LIDAR_PACKET_LEN;
    if (buf[1] != 0x2C) continue;
    if (lidarCrc8(buf, LIDAR_PACKET_LEN - 1) != buf[LIDAR_PACKET_LEN - 1]) continue;
    lidarValidPackets++;

    uint16_t startAngleRaw = buf[4] | (buf[5] << 8);   // 0.01 deg units
    uint16_t endAngleRaw = buf[42] | (buf[43] << 8);  // was buf[40]/[41] (bug, inside data[11] instead) - fixed 2026-08-19
    int32_t angleSpan = (int32_t)endAngleRaw - (int32_t)startAngleRaw;
    if (angleSpan < 0) angleSpan += 36000;  // wrapped past 360deg
    int32_t stepAngle = angleSpan / 11;     // 12 points, 11 gaps

    uint16_t nearestMm = 0xFFFF;
    for (int p = 0; p < 12; p++) {
      uint16_t distMm = buf[6 + p * 3] | (buf[7 + p * 3] << 8);
      if (distMm == 0) continue;  // no return at this point
      if (distMm < nearestMm) nearestMm = distMm;

      int32_t pointAngleRaw = (startAngleRaw + stepAngle * p) % 36000;
      int bucket = (pointAngleRaw / 100) / 10;
      if (bucket >= 0 && bucket < LIDAR_SCAN_BUCKETS) {
        lidarScanCm[bucket] = distMm / 10.0f;
      }
    }
    if (nearestMm != 0xFFFF) lidarNearestDistanceMm = nearestMm;
  }
}

// Returns all 36 scan buckets as a comma-separated string of integer cm
// values (-1 = no reading yet), e.g. "120,-1,340,...". Instant - just
// formats the buffer serviceLidar() (loop()) keeps current, no scanning.
String get_lidar_scan() {
  char out[220];
  int pos = 0;
  for (int i = 0; i < LIDAR_SCAN_BUCKETS; i++) {
    int cm = (lidarScanCm[i] < 0) ? -1 : (int)lidarScanCm[i];
    pos += snprintf(out + pos, sizeof(out) - pos, "%d%s", cm, (i < LIDAR_SCAN_BUCKETS - 1) ? "," : "");
  }
  return String(out);
}

// Diagnostic: reports the running valid-packet count - instant, no
// blocking scan, since serviceLidar() in loop() keeps it current.
float test_lidar() {
  return (float)lidarValidPackets;
}

// ---- Modulino Movement (LSM6DSOX IMU, Wire1 / Qwiic) --------------------
// ---- Modulino Distance (VL53L4CD/ED ToF, Wire1 / Qwiic hub) -------------
//
// Physical wiring (2026-08-12): movement board on hub port 0, distance
// sensors on hub ports 4 (right ear) and 5 (left ear), PCA9685 servo
// driver on hub port 1 (see PCA9685_HUB_PORT above). ModulinoHub is a
// real I2C mux (0x70) - hub.port(N) selects that physical channel, so
// these must match the actual port a board is plugged into or it won't
// be found. `hub` itself is declared earlier in the file (ahead of the
// PCA9685 driver, which needs it too).

ModulinoMovement movementImu(hub.port(0));
ModulinoDistance distRightEar(hub.port(4));
ModulinoDistance distLeftEar(hub.port(5));
bool distRightPresent = false;
bool distLeftPresent = false;

// Reads the Modulino Movement IMU and returns tilt as pitch/roll in degrees
// (out-params, since Bridge scalar returns can't carry two floats at once -
// see imu_read() below for the RPC-facing wrapper).
//
// getRoll()/getPitch()/getYaw() on this library are raw gyro (deg/s), not
// fused orientation - see the NOTE on read_imu() below - so pitch/roll here
// are computed from the accelerometer instead, via the standard tilt-from-
// gravity formulas. This unit reads accel.z ~ -1.0..-1.1g when level (its Z
// axis points down when mounted flat), so z is negated first to match the
// "level = +1g" convention those formulas assume. Verify sign/zero against
// the calibration-mode TFT readout (face.ino) while tilting the chassis by
// hand, and adjust if pitch/roll come out inverted for your mounting.
//
// PITCH_OFFSET_DEG/ROLL_OFFSET_DEG: measured live on 2026-08-13 with the
// chassis confirmed flat/level after the movement board was disconnected
// and reconnected mid-session - its mounting orientation shifted enough
// that "level" no longer read ~0/0 without this correction. Re-measure and
// update these if the board gets reseated again.
const float PITCH_OFFSET_DEG = -20.8f;
const float ROLL_OFFSET_DEG  = -0.3f;

// Rejects samples where total accel magnitude is far from 1g - a sign of a
// connection glitch or a genuine bump, not a slow tilt change. Observed
// live: a single sample of pitch=-67/roll=85 (magnitude ~2.6g) in the
// middle of an otherwise-stable -21/0 baseline, right after the movement
// board was freshly reseated. Keeps the last good reading instead of
// passing a wild one-sample spike through to the tilt-compensation loop.
const float ACCEL_MAGNITUDE_MIN_G = 0.7f;
const float ACCEL_MAGNITUDE_MAX_G = 1.3f;
float lastGoodPitchDeg = 0.0f;
float lastGoodRollDeg = 0.0f;

void imu(float &pitchDeg, float &rollDeg) {
  pitchDeg = lastGoodPitchDeg;
  rollDeg = lastGoodRollDeg;
  if (!imuPresent) return;
  movementImu.update();
  if (!movementImu) return;

  float ax = movementImu.getX();
  float ay = movementImu.getY();
  float az = -movementImu.getZ();  // flip so "level" reads ~+1g

  float magnitude = sqrt(ax * ax + ay * ay + az * az);
  if (magnitude < ACCEL_MAGNITUDE_MIN_G || magnitude > ACCEL_MAGNITUDE_MAX_G) {
    return;  // unreliable sample - keep the last good reading
  }

  pitchDeg = degrees(atan2(-ax, sqrt(ay * ay + az * az))) - PITCH_OFFSET_DEG;
  rollDeg  = degrees(atan2(ay, az)) - ROLL_OFFSET_DEG;
  lastGoodPitchDeg = pitchDeg;
  lastGoodRollDeg = rollDeg;
}

// TEMP DIAGNOSTIC - remove after live-tune session. Reads back the 4 PWM
// registers for a channel right after they're written, so we can tell I2C
// writes actually landing on the PCA9685 apart from the chip's OE pin (or
// downstream wiring) blocking the physical output.
String read_pwm_reg(int channel) {
  if (channel < 0 || channel > 11) return String("bad channel");
  uint8_t base = PCA9685_LED0_ON_L + 4 * channel;
  uint8_t onL = pca9685ReadReg(base);
  uint8_t onH = pca9685ReadReg(base + 1);
  uint8_t offL = pca9685ReadReg(base + 2);
  uint8_t offH = pca9685ReadReg(base + 3);
  uint16_t off = ((uint16_t)offH << 8) | offL;
  return String(onL) + "," + String(onH) + "," + String(offL) + "," + String(offH) + ",ticks=" + String(off);
}

// ---- Bridge RPC handlers (must return quickly - see file header) --------

bool set_servo(int channel, int angle) {
  if (channel < 0 || channel > 15) return false;
  angle = constrain(angle, 0, 180);

  // Channels 12-15 are spare PCA9685 outputs, not part of the 12-DOF leg
  // set - currentAngle[]/transitionStart[]/transitionTarget[] are sized
  // for exactly 12, so these bypass the pose/gait transition system
  // entirely and just write PWM directly. Used to test-swap a servo onto a
  // spare output when its regular channel is suspected bad.
  if (channel > 11) {
    writeServoAngle(channel, angle);
    return true;
  }

  // Manual override: cancel any in-flight pose/gait (and the tilt-comp
  // loop, which would otherwise fight this write on the next tick) so
  // nothing pulls this channel back on its own, but leave every other
  // channel exactly where it is.
  walking = false;
  gaitStepsRemaining = 0;
  standActive = false;
  for (int i = 0; i < 12; i++) {
    int frozen = (i == channel) ? angle : (int)round(currentAngle[i]);
    transitionStart[i] = frozen;
    transitionTarget[i] = frozen;
  }
  transitionDurationMs = 0;

  writeServoAngle(channel, angle);
  currentAngle[channel] = angle;
  return true;
}

// Boot-time hardware detection results, for diagnosing "nothing physically
// moved"/"screen stayed white" reports without needing a serial console -
// queried the same way set_servo() is tested, over the existing Bridge RPC.
String diag_info() {
  return String(pca9685Present) + "," + String(imuPresent) + "," + String(faceSetupDone) + "," +
         String(distRightPresent) + "," + String(distLeftPresent);
}

// Every MEMS gyro has a small constant manufacturing offset - confirmed live
// 2026-08-19: gx read a steady +0.55 deg/s with the chassis sitting
// perfectly still (not noise - identical across repeated samples), which
// integrated over time looks exactly like continuous rotation ("it keeps
// looking like it's moving") even though the robot is stationary (just
// tilted, per imu()'s accel-based pitch/roll, which is unaffected by this).
// Fix: sample the gyro at boot, while nothing should be moving yet, and
// subtract that measured bias from every read_imu() call after.
float gyroBiasX = 0.0f, gyroBiasY = 0.0f, gyroBiasZ = 0.0f;

void calibrateGyroBias() {
  if (!imuPresent) return;
  const int N = 50;
  float sumX = 0, sumY = 0, sumZ = 0;
  for (int i = 0; i < N; i++) {
    movementImu.update();
    if (movementImu) {
      sumX += movementImu.getRoll();
      sumY += movementImu.getPitch();
      sumZ += movementImu.getYaw();
    }
    delay(10);
  }
  gyroBiasX = sumX / N;
  gyroBiasY = sumY / N;
  gyroBiasZ = sumZ / N;
}

// Returns "ax,ay,az,gx,gy,gz" (accel in g, gyro in deg/s, bias-corrected -
// see calibrateGyroBias() above). Packed as a CSV string because
// RouterBridge return types are documented as simple scalars
// (String/int/float/bool) - not structs or arrays.
// NOTE: ModulinoMovement's getRoll()/getPitch()/getYaw() are, per the
// library's own source, raw gyroscope readings (gx,gy,gz), not fused
// orientation angles - there's no on-board sensor fusion here.
String read_imu() {
  if (!imuPresent) {
    return String("0,0,0,0,0,0");
  }
  movementImu.update();
  if (!movementImu) {
    return String("0,0,0,0,0,0");
  }
  char buf[96];
  snprintf(buf, sizeof(buf), "%.4f,%.4f,%.4f,%.4f,%.4f,%.4f",
           movementImu.getX(), movementImu.getY(), movementImu.getZ(),
           movementImu.getRoll() - gyroBiasX, movementImu.getPitch() - gyroBiasY,
           movementImu.getYaw() - gyroBiasZ);
  return String(buf);
}

// Returns "pitch,roll,ax,ay,az" - pitch/roll in degrees (from imu()), accel
// in g (raw, same values read_imu()'s ax/ay/az report) - so the Python side
// can check calibration/tilt without decoding the raw gyro fields.
String imu_read() {
  float pitchDeg, rollDeg;
  imu(pitchDeg, rollDeg);

  float ax = 0.0f, ay = 0.0f, az = 0.0f;
  if (imuPresent) {
    ax = movementImu.getX();
    ay = movementImu.getY();
    az = movementImu.getZ();
  }

  char buf[96];
  snprintf(buf, sizeof(buf), "%.4f,%.4f,%.4f,%.4f,%.4f", pitchDeg, rollDeg, ax, ay, az);
  return String(buf);
}

// Returns the 12 channels' current commanded angles as CSV ("a0,a1,...,a11")
// - this is currentAngle[], the software's own last-written target, not a
// physical position readback (no position feedback exists on these
// servos). Lets the Python/phone side capture "whatever pose the robot is
// in right now" (e.g. after manually jogging each joint) and save it as a
// custom pose, or bake it into a firmware pose constant like STAND_POSE.
String get_servo_angles() {
  char buf[160];
  int offset = 0;
  for (int i = 0; i < 12; i++) {
    offset += snprintf(buf + offset, sizeof(buf) - offset, "%d%s",
                        (int)round(currentAngle[i]), (i < 11) ? "," : "");
  }
  return String(buf);
}

float read_sonar(int sensor_id) {
  if (sensor_id < 0 || sensor_id >= SONAR_COUNT) return -1.0f;
  return readSonarCm(sensor_id);
}

// Modulino distance (VL53L4CD/ED ToF) sensors on the hub - right/left ear.
// Returns cm, or -1 if the board wasn't detected at boot or has no reading
// ready yet (matches readSonarCm()'s -1-on-failure convention).
float sonar_right_ear() {
  if (!distRightPresent) return -1.0f;
  if (!distRightEar.available()) return -1.0f;
  return distRightEar.get() / 10.0f;  // mm -> cm
}

float sonar_left_ear() {
  if (!distLeftPresent) return -1.0f;
  if (!distLeftEar.available()) return -1.0f;
  return distLeftEar.get() / 10.0f;  // mm -> cm
}

// Named convenience wrappers around read_sonar() for the two front boards -
// lets the Python side call them directly without threading a sensor_id
// through the generic RPC.
float sonar_front_left() {
  return readSonarCm(0);
}

float sonar_front_right() {
  return readSonarCm(1);
}

bool stand() {
  walking = false;
  gaitStepsRemaining = 0;
  standActive = true;
  beginTransition(STAND_POSE, POSE_TRANSITION_MS);
  return true;
}

bool sit() {
  walking = false;
  gaitStepsRemaining = 0;
  standActive = false;
  beginTransition(SIT_POSE, POSE_TRANSITION_MS);
  return true;
}

// Folds the legs back to REST_POSE without a reboot - same pose the robot
// boots into now (see setup()), exposed as its own command so it can be
// sent back to a low-stress resting position from stand/sit/mid-walk too.
bool rest() {
  walking = false;
  gaitStepsRemaining = 0;
  standActive = false;
  beginTransition(REST_POSE, POSE_TRANSITION_MS);
  return true;
}

// ---- Body lean (phone UI virtual joystick) --------------------------------
// Per-leg sign convention derived from the live calibration data above:
// FL/RL (left side) share one servo-horn orientation, FR/RR (right side)
// share the mirrored one (confirmed both by the *_THIGH_STAND_DEG pairs -
// FL/RL both ~130-140, FR/RR both ~50 - and by the hand-measured REST_POSE
// knees - FL/RL both fold to 0, FR/RR both fold to 180). So the same raw
// angle delta has to flip sign between left and right legs to produce the
// same physical lean direction, but NOT between front and back legs on the
// same side. LEAN_SIDE_SIGN/LEAN_FB_SIGN encode that. Which physical
// direction is "positive" x/y is still a guess at this point - if a
// direction comes out backwards on the real robot, flip the matching sign.
const uint8_t THIGH_CHANNELS[4] = { 1, 4, 7, 10 };  // FL, FR, RL, RR
const int LEAN_SIDE_SIGN[4] = { 1, -1, 1, -1 };     // FL, FR, RL, RR (left=+1, right=-1)
const int LEAN_FB_SIGN[4]   = { 1, 1, -1, -1 };     // FL, FR, RL, RR (front=+1, back=-1)
const float LEAN_MAX_DEG = 20.0f;           // clamp how far a full joystick deflection can lean
const unsigned long LEAN_TRANSITION_MS = 150UL;  // short/responsive, this gets called repeatedly while dragging

// x, y each in [-100, 100]: x = left(-)/right(+) tilt, y = back(-)/forward(+)
// tilt, matching the phone UI's joystick. Center (0,0) is exactly
// STAND_POSE, so "center returns to stand" falls out of this for free.
bool lean(int x, int y) {
  x = constrain(x, -100, 100);
  y = constrain(y, -100, 100);
  if (x == 0 && y == 0) {
    return stand();
  }

  int pose[12];
  memcpy(pose, STAND_POSE, sizeof(pose));
  for (int leg = 0; leg < 4; leg++) {
    float delta = LEAN_SIDE_SIGN[leg] * (x + LEAN_FB_SIGN[leg] * y) / 100.0f * LEAN_MAX_DEG;
    delta = constrain(delta, -LEAN_MAX_DEG, LEAN_MAX_DEG);
    uint8_t ch = THIGH_CHANNELS[leg];
    pose[ch] = constrain((int)round(STAND_POSE[ch] + delta), 0, 180);
  }

  walking = false;
  gaitStepsRemaining = 0;
  standActive = false;  // don't let tilt-compensation fight an intentional lean
  beginTransition(pose, LEAN_TRANSITION_MS);
  return true;
}

// Advances a bounded number of trot half-steps (GAIT_STEPS_PER_CALL) through
// `keyframe` and then settles back into STAND_POSE. Calling it again with
// the SAME keyframe table while already mid-gait just extends the current
// run (handy for "keep walking/turning while the voice command is active"
// callers); calling it with a DIFFERENT table switches gaits at the next
// step rather than stacking onto the old one.
bool startGait(int (*keyframe)[12]) {
  if (walking && activeGaitKeyframe == keyframe) {
    gaitStepsRemaining += GAIT_STEPS_PER_CALL;
    return true;
  }
  activeGaitKeyframe = keyframe;
  walking = true;
  gaitPhase = 0;
  gaitStepsRemaining = GAIT_STEPS_PER_CALL - 1;
  beginGaitStep(keyframe[0], GAIT_STEP_MS);
  return true;
}

bool walk_forward() {
  return startGait(GAIT_KEYFRAME);
}

// See buildTurnKeyframes()'s comment - unverified against the physical
// robot yet, test manually before using in anything autonomous.
bool turn_left() {
  return startGait(TURN_LEFT_KEYFRAME);
}

bool turn_right() {
  return startGait(TURN_RIGHT_KEYFRAME);
}

// ---- setup() / loop() ----------------------------------------------------

void setup() {
  // Bridge/face come up first and don't touch Wire/Wire1, so they stay
  // reachable even if a servo/IMU board downstream is absent or wedges
  // the I2C bus.
  Bridge.begin();
  Bridge.provide_safe("set_servo", set_servo);
  Bridge.provide_safe("read_imu", read_imu);
  Bridge.provide_safe("imu_read", imu_read);
  Bridge.provide_safe("calibration_mode", calibration_mode);
  Bridge.provide_safe("read_sonar", read_sonar);
  Bridge.provide_safe("sonar_front_left", sonar_front_left);
  Bridge.provide_safe("sonar_front_right", sonar_front_right);
  Bridge.provide_safe("sonar_right_ear", sonar_right_ear);
  Bridge.provide_safe("sonar_left_ear", sonar_left_ear);
  Bridge.provide_safe("stand", stand);
  Bridge.provide_safe("sit", sit);
  Bridge.provide_safe("rest", rest);
  Bridge.provide_safe("lean", lean);
  Bridge.provide_safe("walk_forward", walk_forward);
  Bridge.provide_safe("turn_left", turn_left);
  Bridge.provide_safe("turn_right", turn_right);
  Bridge.provide_safe("face_talk", face_talk);
  Bridge.provide_safe("face_idle", face_idle_cmd);
  Bridge.provide_safe("face-text", face_text);
  Bridge.provide_safe("touch_check", touch_check);
  Bridge.provide_safe("face_diag", face_diag);
  Bridge.provide_safe("diag_info", diag_info);
  Bridge.provide_safe("read_pwm_reg", read_pwm_reg);
  Bridge.provide_safe("face_config", face_config);
  Bridge.provide_safe("flashlight", flashlight);
  Bridge.provide_safe("get_servo_angles", get_servo_angles);
  Bridge.provide_safe("princess_mode", princess_mode);
  Bridge.provide_safe("flower_explosion", flower_explosion);
  Bridge.provide_safe("play_pong", play_pong);
  Bridge.provide_safe("test_speakers", test_speakers);
  Bridge.provide_safe("test_mic", test_mic);
  Bridge.provide_safe("test_lidar", test_lidar);
  Bridge.provide_safe("get_lidar_scan", get_lidar_scan);
  Bridge.provide_safe("photo_chunk_start", photo_chunk_start);
  Bridge.provide_safe("photo_chunk", photo_chunk);
  Bridge.provide_safe("photo_render", photo_render);
  faceSetup();

  Wire1.begin();
  delay(500);
  // Movement/distance boards sit behind the ModulinoHub I2C mux (0x70), so a
  // raw address scan on Wire1 can't see them without selecting a channel
  // first - detect presence via each Module's own begin() instead, which
  // handles hub port select/clear internally.
  Modulino.begin(Wire1);
  imuPresent = movementImu.begin();
  calibrateGyroBias();  // ~500ms, robot must be stationary here - see comment above the function
  distRightPresent = distRightEar.begin();
  distLeftPresent = distLeftEar.begin();

  // PCA9685 is on Wire1/hub too (see PCA9685_HUB_PORT above) - this has to
  // run after Modulino.begin(Wire1) since hub.select() reaches through
  // Modulino's internal wire pointer, which begin() is what sets.
  hub.select(PCA9685_HUB_PORT);
  pca9685Present = i2cDevicePresent(Wire1, PCA9685_ADDR);
  if (pca9685Present) {
    pca9685Init();
  }

  Serial1.begin(230400);
  for (int i = 0; i < LIDAR_SCAN_BUCKETS; i++) lidarScanCm[i] = -1;
  // Datasheet: internal/fixed-speed motor control triggers on "not connected
  // or Hi-Z" - a driven-LOW pin is NOT the same electrical state and may
  // read as an (invalid, edge-less) external speed command instead, which
  // could stall the LiDAR in an unlocked-speed state that never starts
  // streaming data even while the motor visibly spins. Leave truly floating.
  pinMode(LIDAR_PWM_PIN, INPUT);

  buildGaitKeyframes();
  buildTurnKeyframes();
  // Boot settles into WALK_NEUTRAL_POSE (the crouched, ready-to-step
  // stance), NOT the fully-erect STAND_POSE - standing should only ever
  // happen from an explicit stand command, not automatically on every
  // power-up, to avoid the servos taking the body's full weight unattended
  // and the "twisted on boot" failure mode where the true starting angle is
  // unknown and a big transition fights whatever position the legs
  // happened to be left in. Was REST_POSE (fully folded) until 2026-08-14,
  // changed to the walk stance per live request now that it's a
  // functional, tested pose in its own right. Uses beginGaitStep (not
  // beginTransition directly) so the hips - suspected-faulty servo,
  // replacements on order - stay frozen at the assumed neutral 90 rather
  // than being actively driven, same treatment as every other gait-related
  // move tonight. There's still no position feedback, so assume a neutral
  // 90 and ease toward the target over BOOT_SETTLE_MS via the existing
  // transition engine (updateTransition(), driven from loop()) rather than
  // slamming to the target in one write.
  const unsigned long BOOT_SETTLE_MS = 800;
  for (int i = 0; i < 12; i++) {
    currentAngle[i] = 90;
  }
  standActive = false;
  beginGaitStep(WALK_NEUTRAL_POSE, BOOT_SETTLE_MS);

  for (int i = 0; i < SONAR_COUNT; i++) {
    pinMode(sonarTrigPins[i], OUTPUT);
    pinMode(sonarEchoPins[i], INPUT);
    digitalWrite(sonarTrigPins[i], LOW);
  }
}

void loop() {
  updateTransition();
  updateStandTiltCompensation();
  updatePca9685Liveness();
  handleFace();
  updateProximityPulse();
  updateTiltOverlay();
  updateCrazyJitter();
  serviceLidar();
}

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
//   - 3x HC-SR04 ultrasonic on digital GPIO (2 front, 1 back)
//   - ILI9341 TFT (face) + XPT2046 resistive touch (CS=D4, IRQ=D3)
//
// Bridge RPCs exposed to the Linux/Python side:
//   set_servo(channel, angle), read_imu(), read_sonar(sensor_id),
//   imu_read(), calibration_mode(on),
//   stand(), sit(), rest(), lean(x, y), walk_forward(), turn_left(), turn_right(),
//   face_talk(), face_idle(), face-text(text), touch_check(),
//   face_config(eyeShape, mouthShape, eyeColor565, mouthColor565), flashlight(on),
//   sonar_front_left(), sonar_front_right(), sonar_right_ear(), sonar_left_ear()
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

// Per-leg stand calibration, measured live via set_servo against the
// physical assembly during hip/thigh/knee bring-up on 2026-08-13. FL/FR/RL
// hips and RR's hip still use the generic HIP_NEUTRAL_DEG default (not yet
// found to need an override). RR's knee was previously calibrated to 42 on
// 2026-08-09, but its horn has since been re-seated during this session's
// rewiring - 140 is the new correct value, not a typo.
const int FL_THIGH_STAND_DEG = 140;
const int FL_KNEE_STAND_DEG  = 60;
const int FR_HIP_STAND_DEG   = 70;
const int FR_THIGH_STAND_DEG = 50;
const int FR_KNEE_STAND_DEG  = 120;
const int RL_THIGH_STAND_DEG = 132;
const int RL_KNEE_STAND_DEG  = 25;
const int RR_THIGH_STAND_DEG = 50;
const int RR_KNEE_STAND_DEG  = 140;

const int STAND_POSE[12] = {
  HIP_NEUTRAL_DEG,  FL_THIGH_STAND_DEG, FL_KNEE_STAND_DEG,   // FL
  FR_HIP_STAND_DEG, FR_THIGH_STAND_DEG, FR_KNEE_STAND_DEG,   // FR
  HIP_NEUTRAL_DEG,  RL_THIGH_STAND_DEG, RL_KNEE_STAND_DEG,   // RL
  HIP_NEUTRAL_DEG,  RR_THIGH_STAND_DEG, RR_KNEE_STAND_DEG    // RR
};

// Confirmed live on 2026-08-13: the generic THIGH_SIT_DEG/KNEE_SIT_DEG fold
// didn't match this assembly, so sit() now targets the same calibrated pose
// as stand() - same per-leg constants, so recalibrating stand's angles
// keeps sit() in sync automatically rather than needing a second pass.
const int SIT_POSE[12] = {
  HIP_NEUTRAL_DEG,  FL_THIGH_STAND_DEG, FL_KNEE_STAND_DEG,   // FL
  FR_HIP_STAND_DEG, FR_THIGH_STAND_DEG, FR_KNEE_STAND_DEG,   // FR
  HIP_NEUTRAL_DEG,  RL_THIGH_STAND_DEG, RL_KNEE_STAND_DEG,   // RL
  HIP_NEUTRAL_DEG,  RR_THIGH_STAND_DEG, RR_KNEE_STAND_DEG    // RR
};

// Folded resting pose (legs tucked, minimal load-bearing) - measured live
// via set_servo/get_servo_angles against the physical assembly on
// 2026-08-14, the same way STAND_POSE/SIT_POSE were. This is the boot
// default now (see setup()): the robot no longer auto-stands on power-up,
// it eases into this pose instead and waits for an explicit stand/sit
// command. Not derived from the per-leg *_STAND_DEG constants above since
// each leg's hand-tucked fold direction doesn't follow a uniform offset
// from its stand angle (confirmed live: FL/RL knees fold to 0, FR/RR knees
// fold to 180 - opposite ends, matching their mirrored horn seating).
const int REST_POSE[12] = {
  90,  180, 0,     // FL
  70,  0,   180,   // FR
  90,  180, 0,     // RL
  90,  0,   180    // RR
};

// Basic 2-phase trot: diagonal pairs (FL,RR) and (FR,RL) alternate
// swing/stance. GAIT_KEYFRAME[phase][channel].
int GAIT_KEYFRAME[2][12];

void buildGaitKeyframes() {
  for (int phase = 0; phase < 2; phase++) {
    bool diag1SwingForward = (phase == 0);
    for (int leg = 0; leg < 4; leg++) {
      bool isDiag1 = (leg == 0 || leg == 3);  // FL, RR
      bool swinging = (isDiag1 == diag1SwingForward);
      // Hip target is each leg's own calibrated STAND_POSE hip angle, not a
      // flat HIP_NEUTRAL_DEG - FR's hip was specifically calibrated to 70
      // (FR_HIP_STAND_DEG), not the generic 90 the others use. Using the
      // flat constant here previously meant FR's hip snapped 20deg off its
      // calibrated position on every gait step (confirmed live via
      // get_servo_angles - FR hip target was 90 mid-turn instead of 70).
      GAIT_KEYFRAME[phase][leg * 3 + 0] = STAND_POSE[leg * 3 + 0];
      GAIT_KEYFRAME[phase][leg * 3 + 1] = swinging ? THIGH_SWING_DEG : THIGH_STANCE_DEG;
      GAIT_KEYFRAME[phase][leg * 3 + 2] = swinging ? KNEE_SWING_DEG : KNEE_STANCE_DEG;
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

const unsigned long POSE_TRANSITION_MS = 350;
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
    gaitStepPose[hipCh] = (int)round(currentAngle[hipCh]);
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
      beginGaitStep(STAND_POSE, POSE_TRANSITION_MS);
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

// Returns "ax,ay,az,gx,gy,gz" (accel in g, gyro in deg/s). Packed as a CSV
// string because RouterBridge return types are documented as simple
// scalars (String/int/float/bool) - not structs or arrays.
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
           movementImu.getRoll(), movementImu.getPitch(), movementImu.getYaw());
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
  buildGaitKeyframes();
  buildTurnKeyframes();
  // Boot settles into REST_POSE (legs folded, minimal load), NOT
  // STAND_POSE - standing should only ever happen from an explicit stand
  // command, not automatically on every power-up. This avoids stressing
  // the servos (holding the body weight up unattended) and avoids the
  // "twisted on boot" failure mode where the true starting angle is
  // unknown and a full stand transition fights whatever position the legs
  // happened to be left in. There's still no position feedback, so assume
  // a neutral 90 and ease toward REST_POSE over BOOT_SETTLE_MS via the
  // existing transition engine (updateTransition(), driven from loop())
  // rather than slamming to the target in one write.
  const unsigned long BOOT_SETTLE_MS = 800;
  for (int i = 0; i < 12; i++) {
    currentAngle[i] = 90;
  }
  standActive = false;
  beginTransition(REST_POSE, BOOT_SETTLE_MS);

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
}

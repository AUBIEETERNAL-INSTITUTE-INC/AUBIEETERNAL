// AUBIEETERNAL AI tutor - TFT face, screen-only bring-up.
//
// Pin layout confirmed correct 2026-08-22: swapping DC/RST reproduced the
// exact old documented white-screen bug, so DC=8/RST=9 (below) is right -
// the panel IS running a real init sequence. The vertical-stripe garbage
// instead points at SPI signal integrity on breadboard wiring at full
// clock speed, not pin assignment - see the reduced begin() frequency
// below.
//
// TOUCH_CS/TOUCH_IRQ are wired (pins 7/6) but touch itself isn't used yet.
// The XPT2046 touch chip shares the SPI bus (MOSI/MISO/SCK) with the
// ILI9341, distinguished only by its own CS - if that CS is left floating
// (not actively driven HIGH/deselected), the touch chip can contend on the
// shared MISO line and corrupt the TFT's SPI traffic, which showed up as
// alternating vertical stripes instead of a real image. Just holding
// TOUCH_CS HIGH here (no touch library, no SPI reads) fixes that.
#include <Adafruit_GFX.h>
#include <Adafruit_ILI9341.h>
#include <SPI.h>
#include "Arduino_RouterBridge.h"
#include <Wire.h>
#include <Arduino_Modulino.h>

#define TFT_CS     10
#define TFT_DC      8
#define TFT_RST     9
#define TOUCH_CS    7
#define TOUCH_IRQ   6

Adafruit_ILI9341 tft(TFT_CS, TFT_DC, TFT_RST);

// ---- Single-servo wave gesture (PCA9685 on Wire1 / ModulinoHub port 1) ----
// Ported verbatim from the original spotmicro_dog sketch's proven PCA9685
// driver (same board's Wire (header SDA/SCL) silently fails on real writes -
// arduino/ArduinoCore-zephyr#301 - Wire1/hub is the one that actually works).
// Kept deliberately to ONE servo / one gesture for this kiosk build, not the
// full leg/gait system - see [[aubieeternal_stationary_tutor_kit]] memory.
ModulinoHub hub;
const int PCA9685_HUB_PORT = 0;  // confirmed via hub_diag()/wave_diag() testing: servo board is actually on hub port 0

const uint8_t PCA9685_ADDR       = 0x40;
const uint8_t PCA9685_MODE1      = 0x00;
const uint8_t PCA9685_PRESCALE   = 0xFE;
const uint8_t PCA9685_LED0_ON_L  = 0x06;
const float   PCA9685_FREQ_HZ    = 50.0f;   // standard hobby servo rate
const uint8_t WAVE_SERVO_CHANNEL = 15;      // single MG996R - testing channel 15 (the 16th/last channel), was 0

// Pulse-width range for MG996R. TODO: verify/trim per servo on your build.
const int SERVO_MIN_US = 500;
const int SERVO_MAX_US = 2500;

bool pca9685Present = false;

bool i2cDevicePresent(TwoWire &wire, uint8_t addr) {
  wire.beginTransmission(addr);
  return wire.endTransmission() == 0;
}

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

// Non-blocking wave: a short waypoint sequence stepped from loop() via
// millis(), not delay() - keeps the Bridge RPC handler itself instant per
// Arduino's guidance, and avoids stalling anything else running on the MCU
// mid-gesture. Deliberately slow/gentle steps ("just for stress on the
// motor, simple") rather than a fast snappy wave.
const int WAVE_WAYPOINTS[] = {90, 60, 120, 60, 120, 90};
const int WAVE_STEP_MS = 350;
bool waving = false;
int waveStep = 0;
unsigned long waveLastStepMs = 0;

void wave() {
  if (!pca9685Present || waving) return;  // ignore re-triggers mid-wave
  waving = true;
  waveStep = 0;
  waveLastStepMs = millis();
  writeServoAngle(WAVE_SERVO_CHANNEL, WAVE_WAYPOINTS[0]);
}

// Diagnostic only - reports what setup() found at boot, without touching the
// I2C bus again (just returns the cached flag), so it's safe to call even if
// the PCA9685 turned out to be absent/unresponsive.
String wave_diag() {
  return pca9685Present ? "pca9685_present" : "pca9685_NOT_present";
}

// Separate live check for the ModulinoHub mux chip itself (TCA9548A-style,
// address 0x70) - this is a fresh bus probe, not the cached pca9685Present
// flag, so it isolates "is the hub even there" from "does the PCA9685
// respond behind it". Safe to call any time - a bare address probe with no
// payload, same pattern as i2cDevicePresent() everywhere else in this file.
const uint8_t MODULINO_HUB_ADDR = 0x70;
String hub_diag() {
  bool present = i2cDevicePresent(Wire1, MODULINO_HUB_ADDR);
  return present ? "hub_present" : "hub_NOT_present";
}

void updateWave() {
  if (!waving) return;
  unsigned long now = millis();
  if (now - waveLastStepMs < WAVE_STEP_MS) return;
  waveStep++;
  if (waveStep >= (int)(sizeof(WAVE_WAYPOINTS) / sizeof(WAVE_WAYPOINTS[0]))) {
    waving = false;
    return;
  }
  writeServoAngle(WAVE_SERVO_CHANNEL, WAVE_WAYPOINTS[waveStep]);
  waveLastStepMs = now;
}

void drawIdleScreen() {
  tft.fillScreen(ILI9341_BLACK);
  tft.setTextColor(ILI9341_WHITE);
  tft.setTextSize(3);
  tft.setCursor(30, 90);
  tft.println("AUBIE");
  tft.setTextSize(2);
  tft.setCursor(30, 140);
  tft.println("AI Tutor - Screen OK");
}

// ---- flower_explosion RPC (ported from spotmicro_dog/sketch/face.ino) ----
// ERROR_LEDGER.md, 2026-09-13: descoped everything else from that sketch
// (stand/sit/rest/turn_left/turn_right/play_pong - general dog locomotion
// isn't being pursued) but kept this one, since it's the trigger for the
// Gabriela celebration (assistant_server.py's /greet). Only drawFlower()/
// drawHeart()/drawFlowerExplosion() ported - they're self-contained TFT
// primitives with no dependency on the old sketch's much larger eye/mouth
// face-state machine, which this minimal kiosk sketch doesn't have at all.
// Unlike the old sketch's handleFace() (a continuously-running idle face
// this hands back to), this sketch's "idle" is just the static splash
// drawIdleScreen() paints - so returning to idle after the effect just
// means redrawing that splash, not resuming an animation loop.
bool flowerEffectActive = false;
unsigned long flowerEffectStartMs = 0;
const unsigned long FLOWER_EFFECT_DURATION_MS = 3000UL;

void drawFlower(int cx, int cy) {
  uint16_t petal = tft.color565(255, 105, 180);
  for (int a = 0; a < 360; a += 72) {
    float rad = radians((float)a);
    int px = cx + (int)(8 * cos(rad));
    int py = cy + (int)(8 * sin(rad));
    tft.fillCircle(px, py, 5, petal);
  }
  tft.fillCircle(cx, cy, 4, ILI9341_YELLOW);
}

void drawHeart(int cx, int cy, int r, uint16_t color) {
  tft.fillCircle(cx - r / 2, cy - r / 3, r / 2, color);
  tft.fillCircle(cx + r / 2, cy - r / 3, r / 2, color);
  tft.fillTriangle(cx - r, cy - r / 4, cx + r, cy - r / 4, cx, cy + r, color);
}

void drawFlowerExplosion() {
  tft.fillScreen(ILI9341_BLACK);
  drawFlower(50, 40);
  drawFlower(270, 40);
  drawFlower(30, 130);
  drawFlower(290, 130);
  drawFlower(70, 210);
  drawFlower(250, 210);
  drawFlower(160, 30);
  drawHeart(160, 140, 45, tft.color565(255, 20, 100));
}

bool flower_explosion() {
  flowerEffectActive = true;
  flowerEffectStartMs = millis();
  drawFlowerExplosion();
  return true;
}

// Non-blocking timeout, same shape as updateWave() below - checked from
// loop() rather than blocking inside flower_explosion() itself, so the RPC
// handler stays instant per Arduino's guidance.
void updateFlowerEffect() {
  if (!flowerEffectActive) return;
  if (millis() - flowerEffectStartMs < FLOWER_EFFECT_DURATION_MS) return;
  flowerEffectActive = false;
  drawIdleScreen();
}

void setup() {
  pinMode(TOUCH_CS, OUTPUT);
  digitalWrite(TOUCH_CS, HIGH);
  pinMode(TOUCH_IRQ, INPUT);

  tft.begin(4000000);  // breadboard-safe SPI clock (4MHz); default (~24MHz) is
                        // too fast for messy jumper wiring and was showing up
                        // as fine vertical-stripe noise on the panel
  tft.setRotation(1);
  drawIdleScreen();

  Bridge.begin();
  Bridge.provide_safe("wave", wave);
  Bridge.provide_safe("wave_diag", wave_diag);
  Bridge.provide_safe("hub_diag", hub_diag);
  Bridge.provide_safe("flower_explosion", flower_explosion);

  Wire1.begin();
  delay(500);
  Modulino.begin(Wire1);  // hub.select() below reaches through Modulino's internal wire pointer, set by begin()
  hub.select(PCA9685_HUB_PORT);
  pca9685Present = i2cDevicePresent(Wire1, PCA9685_ADDR);
  if (pca9685Present) {
    pca9685Init();
    writeServoAngle(WAVE_SERVO_CHANNEL, 90);  // neutral/centered at boot
  }
}

void loop() {
  updateWave();
  updateFlowerEffect();
}

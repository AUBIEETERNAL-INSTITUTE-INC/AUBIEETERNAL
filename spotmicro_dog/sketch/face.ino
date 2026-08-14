#include <Adafruit_GFX.h>
#include <Adafruit_ILI9341.h>
#include <SPI.h>

#define TFT_CS    10
#define TFT_DC     8
#define TFT_RST    9

// XPT2046 resistive touch controller - shares the SPI bus (MOSI/MISO/SCK)
// with the ILI9341, distinguished only by its own chip-select. Must be held
// deselected (HIGH) whenever we're not explicitly talking to it, otherwise
// it can contend on the shared MISO line and corrupt TFT init commands.
//
// DC/RST/TOUCH_CS/TOUCH_IRQ match tft_test.ino (the standalone sketch that
// was uploaded and used to verify the physical wiring) - this sketch had
// DC and RST swapped relative to that, which left the real hardware reset
// line untoggled and the panel stuck in reset (white screen).
#define TOUCH_CS   7
#define TOUCH_IRQ  6

Adafruit_ILI9341 tft(TFT_CS, TFT_DC, TFT_RST);

enum FaceState { IDLE, TOUCHED_MODE, PERVERT_MODE };
FaceState faceState = IDLE;

bool faceSetupDone = false;  // set at the end of faceSetup(); read from sketch.ino's diag_info()

unsigned long stateStartTime = 0;
unsigned long lastAnimTime   = 0;
volatile bool isTalking = false;
volatile bool talkMouth = false;

// Set on every fresh touch (rising edge) so the Python side can pick it up
// via the touch_check() Bridge RPC without needing a push/callback channel.
// touch_check() reads and clears it, so each physical touch is only seen once.
volatile bool pending = false;

// Calibration mode: replaces the idle face with a live pitch/roll readout
// while servos are being hooked up one at a time. Toggled from the Python
// side via the calibration_mode Bridge RPC below - see imu() in sketch.ino
// for where pitch/roll come from.
volatile bool calibrationMode = false;
unsigned long lastCalibRedrawMs = 0;
const unsigned long CALIB_REDRAW_MS = 150;

// ── Face customization (face_config RPC) ──
// eyeShape/mouthShape are small int enums (kept as plain ints rather than a
// C++ enum class so they can travel directly as Bridge RPC int args - see
// face_config() below). Colors are RGB565, computed Python-side from a hex
// string so the MCU doesn't need to parse color names.
enum EyeShape   { EYE_ROUND = 0, EYE_NARROW = 1, EYE_WIDE = 2, EYE_ANGRY = 3, EYE_SAD = 4, EYE_DOG = 5, EYE_CRAZY = 6, EYE_STONED = 7 };
enum MouthShape { MOUTH_SMILE = 0, MOUTH_FLAT = 1, MOUTH_FROWN = 2, MOUTH_OPEN = 3, MOUTH_DOG = 4, MOUTH_CRAZY = 5, MOUTH_STONED = 6 };

int currentEyeShape = EYE_ROUND;
int currentMouthShape = MOUTH_SMILE;
uint16_t eyeColor565 = ILI9341_WHITE;
uint16_t mouthColor565 = ILI9341_WHITE;

// Pupil jitter for EYE_CRAZY, refreshed by updateCrazyJitter() below.
int crazyJitterX = 0;
int crazyJitterY = 0;

// ── Flashlight mode (flashlight RPC) ──
// Highest-priority state - solid white fill, checked before everything else
// in handleFace(). Drawn once on toggle-on rather than every tick since
// nothing else touches the screen while it's active.
volatile bool flashlightMode = false;

// ── Transient centered text overlay (face_text RPC) ──
// Takes over the whole screen for TEXT_OVERLAY_DURATION_MS, then hands back
// to whatever the normal face state machine would otherwise be showing.
bool textOverlayActive = false;
unsigned long textOverlayStartMs = 0;
const unsigned long TEXT_OVERLAY_DURATION_MS = 5000UL;
String textOverlayString = "";
const int TEXT_OVERLAY_MAX_LEN = 16;

// ── Flower explosion + heart (flower_explosion RPC) ──
// Same pattern as the text overlay above: full-screen takeover for a fixed
// window, then hands back to whatever was showing before. Triggered from
// the rig when a specific recognized face (see assistant_server.py's
// /greet) gets a personalized celebration instead of the plain greeting.
bool flowerEffectActive = false;
unsigned long flowerEffectStartMs = 0;
const unsigned long FLOWER_EFFECT_DURATION_MS = 3000UL;

// ── Photo thumbnail (photo_chunk_start/photo_chunk/photo_render RPCs) ──
// Aubie_listen.py shrinks the just-captured photo to PHOTO_W x PHOTO_H
// RGB565 pixels and streams it here in small hex-encoded pieces - a single
// Bridge RPC call tops out around ~235 bytes of String payload (measured
// empirically: face_text with a 235-char string works, 240 fails), nowhere
// near enough for even this tiny a bitmap in one call, hence the chunked
// start/chunk/render sequence instead of a single call like face_text.
// Rendered scaled up (PHOTO_SCALE) and centered, full-screen takeover like
// the text overlay/flower explosion above (not a small corner overlay - at
// this resolution, blinking eyes redrawing underneath/behind it would
// corrupt the edges since the regions overlap).
const int PHOTO_W = 64;
const int PHOTO_H = 48;
const int PHOTO_BYTES = PHOTO_W * PHOTO_H * 2;  // RGB565 = 2 bytes/pixel
const int PHOTO_SCALE = 4;
const int PHOTO_X = (320 - PHOTO_W * PHOTO_SCALE) / 2;
const int PHOTO_Y = (240 - PHOTO_H * PHOTO_SCALE) / 2;
uint8_t photoBuffer[PHOTO_BYTES];
int photoWriteOffset = 0;
bool photoActive = false;
// Set by photo_render() (the Bridge RPC handler, which runs on a different
// thread than loop()/handleFace()) instead of drawing directly - the actual
// ~3000-pixel draw takes long enough that it was landing mid-blink (blink's
// eyes-closed -> delay(130) -> eyes-open sequence isn't atomic against a
// concurrent RPC draw), leaving the tail end of a blink's eye/mouth redraw
// visible on top of the freshly-drawn photo. handleFace() below picks this
// flag up and does the real draw itself, keeping all TFT/SPI access on one
// thread.
bool photoPending = false;
unsigned long photoStartMs = 0;
const unsigned long PHOTO_DISPLAY_DURATION_MS = 10000UL;

void drawEye(int cx, int cy, bool open) {
  if (!open) {
    tft.fillRect(cx - 38, cy - 3, 76, 6, eyeColor565);
    return;
  }
  switch (currentEyeShape) {
    case EYE_NARROW:
      tft.fillRoundRect(cx - 36, cy - 10, 72, 20, 10, eyeColor565);
      tft.fillCircle(cx + 6, cy, 6, ILI9341_BLACK);
      break;
    case EYE_WIDE:
      tft.fillCircle(cx, cy, 44, eyeColor565);
      tft.fillCircle(cx + 8, cy - 6, 16, ILI9341_BLACK);
      tft.fillCircle(cx + 13, cy - 12, 5, eyeColor565);
      break;
    case EYE_ANGRY:
      tft.fillCircle(cx, cy, 34, eyeColor565);
      tft.fillCircle(cx + 6, cy - 2, 13, ILI9341_BLACK);
      tft.fillTriangle(cx - 40, cy - 40, cx + 42, cy - 12, cx - 40, cy - 12, ILI9341_BLACK);
      break;
    case EYE_SAD:
      tft.fillCircle(cx, cy, 34, eyeColor565);
      tft.fillCircle(cx - 6, cy - 2, 13, ILI9341_BLACK);
      tft.fillTriangle(cx - 40, cy - 40, cx + 40, cy - 32, cx + 40, cy - 6, ILI9341_BLACK);
      break;
    case EYE_DOG:
      tft.fillCircle(cx, cy, 40, eyeColor565);
      tft.fillCircle(cx, cy + 4, 26, ILI9341_BLACK);
      tft.fillCircle(cx + 8, cy - 6, 7, eyeColor565);
      break;
    case EYE_CRAZY: {
      // Bulging and bloodshot, with small off-center mismatched pupils for
      // a deranged look. The jitter offset comes from updateCrazyJitter(),
      // which redraws this shape on a faster cadence than the normal blink
      // cycle so the pupils visibly twitch - sells "wired" better than a
      // static asymmetric shape would.
      tft.fillCircle(cx, cy, 40, eyeColor565);
      for (int a = 0; a < 360; a += 45) {
        float rad = radians((float)a);
        int x1 = cx + (int)(14 * cos(rad));
        int y1 = cy + (int)(14 * sin(rad));
        int x2 = cx + (int)(34 * cos(rad));
        int y2 = cy + (int)(34 * sin(rad));
        tft.drawLine(x1, y1, x2, y2, ILI9341_RED);
      }
      tft.fillCircle(cx + 10 + crazyJitterX, cy - 8 + crazyJitterY, 6, ILI9341_BLACK);
      tft.fillCircle(cx - 4 + crazyJitterX, cy + 6 + crazyJitterY, 9, ILI9341_BLACK);
      break;
    }
    case EYE_STONED:
      // Heavy-lidded, half-closed, relaxed - calm and static, no jitter
      // (unlike EYE_CRAZY). A droopy eyelid covers most of the eye,
      // leaving a low sliver with a low, relaxed pupil.
      tft.fillCircle(cx, cy, 36, eyeColor565);
      tft.fillRect(cx - 44, cy - 50, 88, 42, ILI9341_BLACK);
      tft.fillCircle(cx + 6, cy + 14, 10, ILI9341_BLACK);
      tft.fillCircle(cx + 10, cy + 10, 3, eyeColor565);
      break;
    case EYE_ROUND:
    default:
      tft.fillCircle(cx, cy, 38, eyeColor565);
      tft.fillCircle(cx + 8, cy - 5, 16, ILI9341_BLACK);
      tft.fillCircle(cx + 13, cy - 10, 5, eyeColor565);
      break;
  }
}

// Shared by the idle blink cycle and the talking animation, so every mouth
// shape gets the same "opens while speaking" behavior for free - open=true
// always renders the same talking-mouth shape (with a tongue added for
// MOUTH_DOG), open=false renders the shape-specific closed mouth.
void drawMouth(bool open) {
  const int cx = 160, cy = 195;

  if (open) {
    tft.fillCircle(cx, cy, 28, mouthColor565);
    tft.fillCircle(cx, cy, 20, ILI9341_BLACK);
    if (currentMouthShape == MOUTH_DOG) {
      tft.fillRoundRect(cx - 9, cy + 4, 18, 30, 8, tft.color565(255, 105, 180));
    } else if (currentMouthShape == MOUTH_CRAZY) {
      // Jagged hourglass cutout instead of a plain circle - a bigger,
      // more irregular "screaming" mouth than the default open shape.
      tft.fillCircle(cx, cy, 32, mouthColor565);
      tft.fillTriangle(cx - 18, cy - 22, cx + 18, cy - 22, cx, cy + 4, ILI9341_BLACK);
      tft.fillTriangle(cx - 18, cy + 22, cx + 18, cy + 22, cx, cy - 4, ILI9341_BLACK);
    } else if (currentMouthShape == MOUTH_STONED) {
      tft.fillRoundRect(cx - 14, cy + 8, 28, 32, 12, tft.color565(255, 105, 180));
    }
    return;
  }

  switch (currentMouthShape) {
    case MOUTH_CRAZY: {
      // Jagged, bared-teeth grimace instead of the smooth dot-arc smile.
      const int zigzagCount = 10;
      const int width = 90;
      int prevX = cx - width / 2;
      int prevY = cy;
      for (int i = 1; i <= zigzagCount; i++) {
        int x = cx - width / 2 + (width * i) / zigzagCount;
        int y = cy + ((i % 2 == 0) ? -10 : 10);
        tft.drawLine(prevX, prevY, x, y, mouthColor565);
        tft.drawLine(prevX, prevY + 1, x, y + 1, mouthColor565);
        prevX = x;
        prevY = y;
      }
      break;
    }
    case MOUTH_FLAT:
      tft.fillRect(cx - 40, cy - 3, 80, 6, mouthColor565);
      break;
    case MOUTH_FROWN:
      for (int i = 0; i <= 60; i++) {
        float a = (float)i / 60.0f * PI;
        int x = cx + (int)(55.0f * cos(a));
        int y = cy + 10 - (int)(18.0f * sin(a));
        tft.fillCircle(x, y, 3, mouthColor565);
      }
      break;
    case MOUTH_OPEN:
      tft.fillCircle(cx, cy, 24, mouthColor565);
      tft.fillCircle(cx, cy, 16, ILI9341_BLACK);
      break;
    case MOUTH_DOG:
      for (int i = 0; i <= 60; i++) {
        float a = (float)i / 60.0f * PI;
        int x = cx + (int)(55.0f * cos(a));
        int y = cy + (int)(18.0f * sin(a));
        tft.fillCircle(x, y, 3, mouthColor565);
      }
      tft.fillRoundRect(cx - 9, cy + 2, 18, 24, 8, tft.color565(255, 105, 180));
      break;
    case MOUTH_STONED:
      // Big, slack, relaxed mouth with an oversized tongue hanging out -
      // pairs with EYE_STONED for a mellow "stoned dog" look.
      tft.fillCircle(cx, cy - 4, 30, mouthColor565);
      tft.fillCircle(cx, cy - 4, 22, ILI9341_BLACK);
      tft.fillRoundRect(cx - 14, cy + 8, 28, 32, 12, tft.color565(255, 105, 180));
      break;
    case MOUTH_SMILE:
    default:
      for (int i = 0; i <= 60; i++) {
        float a = (float)i / 60.0f * PI;
        int x = cx + (int)(55.0f * cos(a));
        int y = cy + (int)(18.0f * sin(a));
        tft.fillCircle(x, y, 3, mouthColor565);
      }
      break;
  }
}

// Clears just the eye/mouth regions instead of the whole screen (fillScreen
// on every redraw caused a visible full-screen black flash between faces -
// e.g. blinking, or switching Happy/Surprised). Box sizes are sized to
// safely cover the largest shape each region can render (EYE_WIDE's r=44
// circle for eyes; MOUTH_DOG's open-mouth + tongue for the mouth) with a
// few px of margin, not the actual screen edges.
void clearLeftEyeRegion()  { tft.fillRect(85 - 50, 110 - 50, 100, 100, ILI9341_BLACK); }
void clearRightEyeRegion() { tft.fillRect(235 - 50, 110 - 50, 100, 100, ILI9341_BLACK); }
void clearMouthRegion()    { tft.fillRect(160 - 70, 195 - 40, 140, 85, ILI9341_BLACK); }

void clearFaceRegions() {
  clearLeftEyeRegion();
  clearRightEyeRegion();
  clearMouthRegion();
}

// ── Princess mode (crown + flowers decoration layer) ──
// Independent of eye/mouth shape - layers on top of whatever's currently
// selected (princess_mode RPC toggles this, doesn't touch face_config's
// shapes/colors). Positioned to stay clear of the eye/mouth regions, the
// tilt overlay (bottom-left), and the proximity border (outer 6px).
volatile bool princessMode = false;

void drawCrown() {
  const int baseY = 58;  // shifted down ~a flower's diameter from the original 40 - the physical case bezel was covering it up near the top edge
  uint16_t gold = tft.color565(255, 215, 0);
  tft.fillRect(125, baseY, 70, 10, gold);
  tft.fillTriangle(125, baseY, 145, baseY, 130, baseY - 20, gold);
  tft.fillTriangle(145, baseY, 175, baseY, 160, baseY - 28, gold);
  tft.fillTriangle(175, baseY, 195, baseY, 190, baseY - 20, gold);
  tft.fillCircle(130, baseY - 20, 4, ILI9341_RED);
  tft.fillCircle(160, baseY - 28, 5, ILI9341_RED);
  tft.fillCircle(190, baseY - 20, 4, ILI9341_RED);
}

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

void drawPrincessDecorations() {
  drawCrown();
  drawFlower(20, 38);
  drawFlower(300, 38);
}

void drawHeart(int cx, int cy, int r, uint16_t color) {
  tft.fillCircle(cx - r / 2, cy - r / 3, r / 2, color);
  tft.fillCircle(cx + r / 2, cy - r / 3, r / 2, color);
  tft.fillTriangle(cx - r, cy - r / 4, cx + r, cy - r / 4, cx, cy + r, color);
}

// A scattered burst of flowers plus a big centered heart - not true
// particle motion (drawn once, not frame-by-frame animated), just a full
// celebratory tableau held for FLOWER_EFFECT_DURATION_MS.
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

// Draws the accumulated photoBuffer as a PHOTO_SCALE-upscaled block of
// pixels (each source pixel becomes a PHOTO_SCALEx PHOTO_SCALE square) -
// tft.drawRGBBitmap() draws 1:1, which at PHOTO_W x PHOTO_H would be too
// small to make anything out, so this draws pixel-by-pixel instead.
void drawPhotoThumbnail() {
  tft.fillScreen(ILI9341_BLACK);
  int idx = 0;
  for (int y = 0; y < PHOTO_H; y++) {
    for (int x = 0; x < PHOTO_W; x++) {
      uint16_t pixel = ((uint16_t)photoBuffer[idx] << 8) | photoBuffer[idx + 1];
      idx += 2;
      tft.fillRect(PHOTO_X + x * PHOTO_SCALE, PHOTO_Y + y * PHOTO_SCALE,
                   PHOTO_SCALE, PHOTO_SCALE, pixel);
    }
  }
}

void clearPrincessDecorations() {
  tft.fillRect(110, 5, 100, 70, ILI9341_BLACK);  // crown area
  tft.fillRect(0, 0, 40, 58, ILI9341_BLACK);      // left flower
  tft.fillRect(280, 0, 40, 58, ILI9341_BLACK);    // right flower
}

void drawIdleFace(bool open) {
  clearFaceRegions();
  drawEye(85, 110, open);
  drawEye(235, 110, open);
  drawMouth(false);
  if (princessMode) drawPrincessDecorations();
}

// Full-screen clear before handing back to the idle face - required whenever
// the screen was just owned by something that painted outside the eye/mouth
// boxes clearFaceRegions() covers (flashlight's white fill, the text
// overlay's greeting text, calibration's labels/numbers, the flower burst).
// drawIdleFace()'s own partial clear only assumes the rest of the screen was
// already black, which isn't true coming out of any of those states -
// without this, stale content from them lingers around the eyes/mouth.
void returnToIdleFace() {
  tft.fillScreen(ILI9341_BLACK);
  drawIdleFace(true);
}

void drawTouchedFace() {
  tft.fillScreen(ILI9341_BLACK);
  tft.fillCircle(85,  100, 42, ILI9341_WHITE);
  tft.fillCircle(93,   95, 20, ILI9341_BLACK);
  tft.fillCircle(99,   89,  6, ILI9341_WHITE);
  tft.fillCircle(235, 100, 42, ILI9341_WHITE);
  tft.fillCircle(243,  95, 20, ILI9341_BLACK);
  tft.fillCircle(249,  89,  6, ILI9341_WHITE);
  tft.fillCircle(160, 195, 22, ILI9341_WHITE);
  tft.fillCircle(160, 195, 15, ILI9341_BLACK);
}

void drawPervertMode() {
  tft.fillScreen(ILI9341_BLACK);
  tft.setTextSize(3);
  tft.setTextColor(ILI9341_RED);
  tft.setCursor(12, 30);
  tft.print("XXpervertX");
  tft.setTextSize(2);
  tft.setTextColor(ILI9341_YELLOW);
  tft.setCursor(50, 75);
  tft.print("NOT KIDS MODE");
  tft.fillCircle(160, 170, 60, ILI9341_RED);
  tft.fillCircle(160, 170, 52, ILI9341_BLACK);
  for (int d = -3; d <= 3; d++)
    tft.drawLine(118, 128 + d, 202, 212 + d, ILI9341_RED);
}

void servo_shake() {
  // placeholder - add servo wiggle here when servos connected
}

// ── Text overlay (face_text RPC) ──
// Text sits in the upper half of the screen; a talking mouth animates below
// it (standard mouth position/shapes - see drawMouth()) for the duration of
// the overlay, driven from handleFace()'s textOverlayActive branch on the
// same cadence/state (talkMouth/lastAnimTime) the normal talking animation
// uses - the two never run at once, so sharing them is safe.
void drawTextOverlay() {
  tft.fillScreen(ILI9341_BLACK);
  tft.setTextSize(3);
  tft.setTextColor(ILI9341_WHITE);
  int textWidthPx = textOverlayString.length() * 6 * 3;   // GFX default font: 6px/char at size 1
  int x = (320 - textWidthPx) / 2;
  if (x < 0) x = 0;
  tft.setCursor(x, 50);
  tft.print(textOverlayString);
  drawMouth(false);
}

void updateTextOverlayMouth(bool mouthOpen) {
  clearMouthRegion();
  drawMouth(mouthOpen);
}

// ── Proximity pulse (red border flash when something's close) ──
// closestDistanceCm() reads all 5 range sensors (3x HC-SR04 + 2x Modulino
// ToF ears) and returns the nearest valid reading, or -1 if nothing's in
// range on any of them.
const float PROXIMITY_THRESHOLD_CM = 20.0f;
const unsigned long PROXIMITY_POLL_MS = 200;
unsigned long lastProximityPollMs = 0;
float proximityIntensity = 0.0f;  // smoothed 0..1, drives border brightness/presence

// Round-robins one HC-SR04 read per call rather than all 3 - each is
// blocking (up to 30ms via safePulseIn), so reading all 3 on every poll cost
// up to ~90ms out of every 200ms tick and made touch/animation feel
// laggy. Reusing the last known reading for the other two keeps "closest
// object" reasonably fresh (each sensor still updates at least every 3rd
// poll, ~600ms) at a third of the blocking cost. The 2 Modulino ToF ears
// are cheap (.available() is non-blocking) so those are read fresh every
// call.
float lastSonarCm[SONAR_COUNT] = { -1.0f, -1.0f, -1.0f };
int nextSonarToPoll = 0;

float closestDistanceCm() {
  lastSonarCm[nextSonarToPoll] = readSonarCm(nextSonarToPoll);
  nextSonarToPoll = (nextSonarToPoll + 1) % SONAR_COUNT;

  float best = -1.0f;
  for (int i = 0; i < SONAR_COUNT; i++) {
    if (lastSonarCm[i] >= 0 && (best < 0 || lastSonarCm[i] < best)) best = lastSonarCm[i];
  }

  // The Modulino ToF "ear" sensors (distRightEar/distLeftEar) are
  // deliberately NOT included here anymore - calling their RPC wrappers
  // (sonar_right_ear/sonar_left_ear) was observed to hang indefinitely
  // (2026-08-13), and the 3 HC-SR04 sonars above already tested cleanly
  // reliable (return -1 promptly with nothing in range). Reintroduce these
  // once the ToF I2C hang is root-caused - until then this avoids feeding
  // possibly-stuck/bogus readings into the proximity-face trigger, which
  // was reported as reacting backward (crazy at rest, calm up close).

  return best;
}

void drawProximityBorder(float intensity) {
  uint8_t red5 = (uint8_t)constrain(intensity * 31.0f, 0.0f, 31.0f);
  uint16_t color = (uint16_t)(red5 << 11);
  const int thickness = 6;
  for (int t = 0; t < thickness; t++) {
    tft.drawRect(t, t, 320 - 2 * t, 240 - 2 * t, color);
  }
}

void clearProximityBorder() {
  const int thickness = 6;
  for (int t = 0; t < thickness; t++) {
    tft.drawRect(t, t, 320 - 2 * t, 240 - 2 * t, ILI9341_BLACK);
  }
}

// ── Proximity-reactive facial expression ──
// Layered on top of the border pulse above - as something gets close, the
// face itself temporarily switches to an "alert"/"startled" look, then
// restores whatever normal/customized expression was showing once the
// object moves away again. Tiers, not a continuous blend, since morphing
// between arbitrary vector shapes isn't practical with these primitives.
const float PROXIMITY_FACE_NEAR_CM  = 20.0f;  // switch to "alert"
const float PROXIMITY_FACE_CLOSE_CM = 8.0f;   // switch to "startled"
bool proximityFaceActive = false;
int savedEyeShapeBeforeProximity = EYE_ROUND;
int savedMouthShapeBeforeProximity = MOUTH_SMILE;
int lastProximityFaceTier = -1;  // -1 = normal, 0 = alert, 1 = startled

void updateProximityFace(float distanceCm) {
  // Don't fight whatever else owns the screen/expression right now.
  if (calibrationMode || flashlightMode || textOverlayActive || flowerEffectActive || photoActive || isTalking) return;

  int tier = -1;
  if (distanceCm >= 0 && distanceCm < PROXIMITY_FACE_CLOSE_CM) {
    tier = 1;
  } else if (distanceCm >= 0 && distanceCm < PROXIMITY_FACE_NEAR_CM) {
    tier = 0;
  }
  if (tier == lastProximityFaceTier) return;
  lastProximityFaceTier = tier;

  if (tier == -1) {
    if (proximityFaceActive) {
      currentEyeShape = savedEyeShapeBeforeProximity;
      currentMouthShape = savedMouthShapeBeforeProximity;
      proximityFaceActive = false;
      drawIdleFace(true);
      lastAnimTime = millis();
    }
    return;
  }

  if (!proximityFaceActive) {
    savedEyeShapeBeforeProximity = currentEyeShape;
    savedMouthShapeBeforeProximity = currentMouthShape;
    proximityFaceActive = true;
  }
  if (tier == 1) {
    // Very close - the jagged/bloodshot "crazy" look (also picks up the
    // pupil jitter automatically via updateCrazyJitter(), which just
    // checks the current eye shape each tick regardless of who set it).
    currentEyeShape = EYE_CRAZY;
    currentMouthShape = MOUTH_CRAZY;
  } else {
    currentEyeShape = EYE_WIDE;
    currentMouthShape = MOUTH_FLAT;
  }
  drawIdleFace(true);
  lastAnimTime = millis();
}

// Called from loop() (not from inside handleFace()) so it always paints
// after that tick's face redraw, regardless of which branch handleFace()
// took - otherwise a fillScreen() from drawIdleFace()/drawTalkingFace()
// would erase the border right after it was drawn.
void updateProximityPulse() {
  if (calibrationMode || flashlightMode || textOverlayActive || flowerEffectActive || photoActive) return;

  unsigned long now = millis();
  if (now - lastProximityPollMs < PROXIMITY_POLL_MS) return;
  lastProximityPollMs = now;

  float d = closestDistanceCm();
  updateProximityFace(d);
  float target = 0.0f;

  if (d >= 0 && d < PROXIMITY_THRESHOLD_CM) {
    float closeness = 1.0f - (d / PROXIMITY_THRESHOLD_CM);  // 0..1, 1 = right on top of it
    float pulseHz = 1.0f + closeness * 4.0f;                // faster pulse the closer it is
    unsigned long periodMs = (unsigned long)(1000.0f / pulseHz);
    float phase = (float)(now % periodMs) / (float)periodMs;
    float pulse = 0.5f + 0.5f * sin(phase * 2.0f * PI);
    target = (0.3f + 0.7f * pulse) * (0.4f + 0.6f * closeness);  // brighter the closer it is
  }

  // Smooth toward target so crossing the threshold fades rather than snaps.
  proximityIntensity += (target - proximityIntensity) * 0.35f;

  if (proximityIntensity > 0.02f) {
    drawProximityBorder(proximityIntensity);
  } else if (proximityIntensity != 0.0f) {
    clearProximityBorder();
    proximityIntensity = 0.0f;
  }
}

// ── Always-on tilt readout (bottom-left corner) ──
// Small "P:x.x R:x.x" text, independent of calibration_mode's full-screen
// takeover below - this is meant to be visible at a glance during normal
// operation, not just during bring-up. Positioned/sized to stay clear of
// the mouth's clear region (x 90-230) and the proximity border (outer 6px)
// so it doesn't get wiped by either.
const unsigned long TILT_OVERLAY_POLL_MS = 300;
unsigned long lastTiltOverlayMs = 0;

void drawTiltOverlay() {
  float pitchDeg, rollDeg;
  imu(pitchDeg, rollDeg);
  tft.fillRect(0, 210, 88, 16, ILI9341_BLACK);
  tft.setTextSize(1);
  tft.setTextColor(ILI9341_CYAN);
  tft.setCursor(2, 214);
  tft.print("P:");
  tft.print(pitchDeg, 1);
  tft.setCursor(2, 222);
  tft.print("R:");
  tft.print(rollDeg, 1);
}

// Called from loop() (not from inside handleFace()), same reasoning as
// updateProximityPulse() - needs to paint after that tick's face redraw so
// a fillScreen()/clearFaceRegions() call doesn't erase it right after.
void updateTiltOverlay() {
  if (!imuPresent || flashlightMode || textOverlayActive || calibrationMode || flowerEffectActive || photoActive) return;

  unsigned long now = millis();
  if (now - lastTiltOverlayMs < TILT_OVERLAY_POLL_MS) return;
  lastTiltOverlayMs = now;

  drawTiltOverlay();
}

// ── EYE_CRAZY jitter refresh ──
// Redraws just the eyes with a fresh random pupil offset on a faster
// cadence than the normal blink cycle, so EYE_CRAZY visibly twitches
// instead of sitting static "wired". No-op for every other eye shape.
const unsigned long CRAZY_JITTER_MS = 180;
unsigned long lastCrazyJitterMs = 0;

void updateCrazyJitter() {
  if (currentEyeShape != EYE_CRAZY) return;
  if (flashlightMode || textOverlayActive || calibrationMode || flowerEffectActive || photoActive) return;

  unsigned long now = millis();
  if (now - lastCrazyJitterMs < CRAZY_JITTER_MS) return;
  lastCrazyJitterMs = now;

  crazyJitterX = random(-4, 5);
  crazyJitterY = random(-4, 5);

  clearLeftEyeRegion();
  clearRightEyeRegion();
  drawEye(85, 110, true);
  drawEye(235, 110, true);
}

// ── Calibration screen (live pitch/roll, replaces the idle face) ──
// Labels are drawn once on entry; only the numeric area is redrawn per tick
// (drawCalibrationValues) so the screen doesn't flicker at ~7Hz.
void drawCalibrationLabels() {
  tft.fillScreen(ILI9341_BLACK);
  tft.setTextSize(2);
  tft.setTextColor(ILI9341_WHITE);
  tft.setCursor(60, 16);
  tft.print("CALIBRATION");
  tft.setTextSize(1);
  tft.setTextColor(ILI9341_CYAN);
  tft.setCursor(20, 64);
  tft.print("PITCH (deg)");
  tft.setTextColor(ILI9341_YELLOW);
  tft.setCursor(20, 144);
  tft.print("ROLL (deg)");
}

void drawCalibrationValues() {
  float pitchDeg, rollDeg;
  imu(pitchDeg, rollDeg);

  tft.fillRect(18, 78, 284, 50, ILI9341_BLACK);
  tft.setTextSize(4);
  tft.setTextColor(ILI9341_CYAN);
  tft.setCursor(20, 82);
  tft.print(pitchDeg, 1);

  tft.fillRect(18, 158, 284, 50, ILI9341_BLACK);
  tft.setTextColor(ILI9341_YELLOW);
  tft.setCursor(20, 162);
  tft.print(rollDeg, 1);
}

void faceSetup() {
  // TOUCH_CS/TOUCH_IRQ (pins 7/6) are intentionally NOT configured here -
  // touch hardware isn't physically present on this build, and those same
  // GPIOs are sonarTrigPins[1]/sonarEchoPins[2] (real, connected hardware),
  // set up later in sketch.ino's setup(). Configuring them for touch here
  // only to have the sonar pinMode() calls immediately override it caused
  // spurious "touch" reads - see the touching=false note in handleFace().

  // Explicitly drive CS/DC before SPI.begin() so the TFT is deselected
  // (not floating) for the entire bring-up sequence.
  pinMode(TFT_CS, OUTPUT);
  digitalWrite(TFT_CS, HIGH);
  pinMode(TFT_DC, OUTPUT);

  SPI.begin();
  delay(500);
  tft.begin();
  tft.setRotation(1);
  tft.fillScreen(ILI9341_BLACK);
  delay(100);
  drawIdleFace(true);
  stateStartTime = millis();
  lastAnimTime   = millis();
  faceSetupDone = true;
}

void handleFace() {
  unsigned long now = millis();

  // Flashlight is the highest priority - solid white, drawn once on
  // toggle-on (see flashlight() below), nothing more to do per tick.
  if (flashlightMode) return;

  // Flower explosion + heart (flower_explosion RPC) takes over the whole
  // screen for a fixed window, drawn once on trigger, then hands back to
  // whatever state was showing before.
  if (flowerEffectActive) {
    if (now - flowerEffectStartMs > FLOWER_EFFECT_DURATION_MS) {
      flowerEffectActive = false;
      faceState = IDLE;
      stateStartTime = now;
      returnToIdleFace();
      lastAnimTime = now;
    }
    return;
  }

  // Photo thumbnail (photo_render RPC, after aubie_listen.py streams it in
  // via photo_chunk_start/photo_chunk) takes over the whole screen for a
  // fixed window, then hands back to whatever state was showing before.
  // The actual draw happens here (not in photo_render() itself) so it can
  // never land mid-blink - see photoPending's declaration comment.
  if (photoPending) {
    photoPending = false;
    photoActive = true;
    photoStartMs = now;
    drawPhotoThumbnail();
  }
  if (photoActive) {
    if (now - photoStartMs > PHOTO_DISPLAY_DURATION_MS) {
      photoActive = false;
      faceState = IDLE;
      stateStartTime = now;
      returnToIdleFace();
      lastAnimTime = now;
    }
    return;
  }

  // Greeting overlay (face_text) takes over the whole screen for a fixed
  // window, then hands back to whatever state was showing before.
  if (textOverlayActive) {
    if (now - textOverlayStartMs > TEXT_OVERLAY_DURATION_MS) {
      textOverlayActive = false;
      faceState = IDLE;
      stateStartTime = now;
      returnToIdleFace();
      lastAnimTime = now;
    } else if (now - lastAnimTime > 220UL) {
      talkMouth = !talkMouth;
      updateTextOverlayMouth(talkMouth);
      lastAnimTime = now;
    }
    return;
  }

  // Calibration readout takes priority over everything else below, including
  // talking/touch - it replaces the idle face entirely while active.
  if (calibrationMode) {
    if (now - lastCalibRedrawMs > CALIB_REDRAW_MS) {
      drawCalibrationValues();
      lastCalibRedrawMs = now;
    }
    return;
  }

  // Talking animation takes priority
  if (isTalking) {
    if (now - lastAnimTime > 220UL) {
      talkMouth = !talkMouth;
      drawTalkingFace(talkMouth);
      lastAnimTime = now;
    }
    return;
  }

  // Touch is not physically present on this build - TOUCH_CS/TOUCH_IRQ
  // (pins 7/6) are the exact same GPIOs as sonarTrigPins[1]/sonarEchoPins[2],
  // which ARE real, connected hardware. Reading TOUCH_IRQ here was fighting
  // those sonar pins for control and producing spurious "touch" reads
  // (including right after boot) that snapped into TOUCHED_MODE looking
  // like a startled/surprised face. Hardcoded false rather than removing
  // the state machine below, so it's a one-line revert if touch hardware
  // gets added on different pins later.
  bool touching = false;

  static bool wasTouching = false;
  if (touching && !wasTouching) {
    pending = true;  // rising edge - latch for touch_check()
  }
  wasTouching = touching;

  if (touching) {
    int recent = 0;  // TODO: recent-touch-count tracking not implemented yet

    if (recent >= 4 && faceState != PERVERT_MODE) {
      faceState = PERVERT_MODE;
      stateStartTime = now;
      drawPervertMode();
      servo_shake();
    } else if (recent < 4 && faceState == IDLE) {
      faceState = TOUCHED_MODE;
      stateStartTime = now;
      drawTouchedFace();
    }
  }

  if (faceState == IDLE) {
    if (now - lastAnimTime > 3800UL) {
      drawIdleFace(false);
      delay(130);
      drawIdleFace(true);
      lastAnimTime = now;
    }
  } else if (faceState == TOUCHED_MODE) {
    if (now - stateStartTime > 7000UL) {
      faceState = IDLE;
      drawIdleFace(true);
      lastAnimTime = now;
    }
  } else if (faceState == PERVERT_MODE) {
    if (now - stateStartTime > 5000UL) {
      faceState = IDLE;
      drawIdleFace(true);
      lastAnimTime = now;
    }
  }
}

// ── Talking face (called from Bridge command) ──
void drawTalkingFace(bool mouthOpen) {
  clearFaceRegions();
  drawEye(85,  110, true);
  drawEye(235, 110, true);
  drawMouth(mouthOpen);
  if (princessMode) drawPrincessDecorations();
}


String face_talk(String) {
  isTalking = true;
  faceState = IDLE;  // reset so talking takes over
  return "ok";
}

String face_idle_cmd(String) {
  isTalking = false;
  drawIdleFace(true);
  lastAnimTime = millis();
  return "ok";
}

// Shows text in large centered font, full-screen, for TEXT_OVERLAY_DURATION_MS
// (5s), then automatically returns to whatever the face was doing before.
// Non-blocking: handleFace() owns the timeout (see the textOverlayActive
// branch above) rather than this RPC handler sleeping, per the file header's
// "RPC handlers must return quickly" rule.
String face_text(String text) {
  if (text.length() > TEXT_OVERLAY_MAX_LEN) text = text.substring(0, TEXT_OVERLAY_MAX_LEN);
  textOverlayString = text;
  textOverlayActive = true;
  textOverlayStartMs = millis();
  talkMouth = false;
  lastAnimTime = millis();
  drawTextOverlay();
  return "ok";
}

// Read-and-clear: returns true once per physical touch, then resets until
// the next one. Polled from the Python side (no push channel available).
bool touch_check() {
  bool result = pending;
  pending = false;
  return result;
}

// Diagnostic-only - reports the live state of everything that decides what
// handleFace() draws: "faceState,eyeShape,mouthShape,isTalking,
// calibrationMode,flashlightMode,textOverlayActive,millis". Added to catch
// the "changes face right after boot with no RPC call" report in the act,
// since guessing from static code reading twice already missed it.
String face_diag() {
  char buf[128];
  snprintf(buf, sizeof(buf), "%d,%d,%d,%d,%d,%d,%d,%lu",
           (int)faceState, currentEyeShape, currentMouthShape, (int)isTalking,
           (int)calibrationMode, (int)flashlightMode, (int)textOverlayActive,
           millis());
  return String(buf);
}

// Toggles the live pitch/roll calibration screen on/off. Call with true
// before hooking up a servo to watch tilt react in real time; call with
// false to hand the screen back to the normal idle face.
bool calibration_mode(bool on) {
  calibrationMode = on;
  if (on) {
    drawCalibrationLabels();
    lastCalibRedrawMs = 0;  // force an immediate value redraw on the next tick
  } else {
    faceState = IDLE;
    stateStartTime = millis();
    lastAnimTime = millis();
    returnToIdleFace();
  }
  return true;
}

// Sets the idle/talking face's eye/mouth shapes and colors - see the
// EyeShape/MouthShape enums above for the int values each argument takes,
// and drawEye()/drawMouth() for the actual rendering. Colors are RGB565,
// expected to already be converted from hex on the Python side. Redraws
// immediately (unless calibration/flashlight/text-overlay owns the screen
// right now) so the change is visible without waiting for the next tick.
bool face_config(int eyeShape, int mouthShape, int eyeColor, int mouthColor) {
  eyeColor565 = (uint16_t)eyeColor;
  mouthColor565 = (uint16_t)mouthColor;

  if (proximityFaceActive) {
    // A proximity expression currently owns the eyes/mouth - don't stomp
    // it, just update what gets restored once the object moves away.
    savedEyeShapeBeforeProximity = eyeShape;
    savedMouthShapeBeforeProximity = mouthShape;
    return true;
  }

  currentEyeShape = eyeShape;
  currentMouthShape = mouthShape;

  if (calibrationMode || flashlightMode || textOverlayActive || flowerEffectActive || photoActive) {
    // one of those owns the screen right now - it'll pick up the new
    // shapes/colors next time it actually returns to the idle/talking face
  } else if (isTalking) {
    drawTalkingFace(talkMouth);
  } else {
    drawIdleFace(true);
    lastAnimTime = millis();
  }
  return true;
}

// Solid white full-screen fill so the TFT can double as a light source.
// Highest-priority state (see handleFace()) - overrides everything else
// until toggled off, at which point it hands back to the normal idle face.
bool flashlight(bool on) {
  flashlightMode = on;
  if (on) {
    tft.fillScreen(ILI9341_WHITE);
  } else {
    faceState = IDLE;
    stateStartTime = millis();
    lastAnimTime = millis();
    returnToIdleFace();
  }
  return true;
}

// Toggles the crown + flower decoration layer on/off, independent of
// face_config's eye/mouth shape - combines with whatever's already set.
bool princess_mode(bool on) {
  princessMode = on;
  if (on) {
    drawPrincessDecorations();
  } else {
    clearPrincessDecorations();
  }
  return true;
}

// Full-screen flower burst + heart, held for FLOWER_EFFECT_DURATION_MS then
// automatically returns to whatever the face was doing before - see the
// flowerEffectActive branch in handleFace(). Triggered from the rig for a
// specific recognized face (assistant_server.py's /greet).
bool flower_explosion() {
  flowerEffectActive = true;
  flowerEffectStartMs = millis();
  drawFlowerExplosion();
  return true;
}

// ── Photo thumbnail chunked transfer (photo_chunk_start/photo_chunk/
// photo_render RPCs) ──
// aubie_listen.py can't fit the thumbnail in one Bridge call (see PHOTO_W's
// comment above), so it calls these three in sequence: reset the write
// offset, append each hex-encoded chunk, then render once the buffer is
// full. Non-blocking like the rest of this file's RPC handlers - the actual
// display timeout is handled by handleFace()'s photoActive branch.
String photo_chunk_start(String) {
  photoWriteOffset = 0;
  return "ok";
}

uint8_t hexCharToByte(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return 10 + (c - 'a');
  if (c >= 'A' && c <= 'F') return 10 + (c - 'A');
  return 0;
}

// Appends one hex-encoded chunk (2 hex chars per byte) to photoBuffer at the
// current offset. Malformed/oversized chunks are dropped rather than
// crashing - a corrupt thumbnail is harmless, photo_render() below refuses
// to draw an incomplete buffer.
String photo_chunk(String hexChunk) {
  int n = hexChunk.length() / 2;
  for (int i = 0; i < n && photoWriteOffset < PHOTO_BYTES; i++) {
    char hi = hexChunk[i * 2];
    char lo = hexChunk[i * 2 + 1];
    if (!isHexadecimalDigit(hi) || !isHexadecimalDigit(lo)) break;
    photoBuffer[photoWriteOffset++] =
        (uint8_t)((hexCharToByte(hi) << 4) | hexCharToByte(lo));
  }
  return "ok";
}

bool photo_render() {
  if (photoWriteOffset < PHOTO_BYTES) return false;  // incomplete transfer, don't show garbage
  photoPending = true;  // handleFace() does the actual draw - see photoPending's comment above
  return true;
}

/*
 * AUBIEETERNAL Assistant -- Display Test (Arduino UNO Q)
 * HiLetgo ILI9341 2.8" 240x320 SPI
 *
 * Plan 2: the ESP32-S3 is going back, so we're using the Uno Q.
 * The dog's original 1,181-line sketch is backed up on Ryzen at
 * ~/AUBIEETERNAL/dog_sketch/ -- restore it any time with sketch_push.
 *
 * ---------------------------------------------------------------
 * WIRING (standard Uno SPI)
 * ---------------------------------------------------------------
 *   SCK    -> D13
 *   MISO   -> D12
 *   MOSI   -> D11        (labelled SDI on some screens)
 *   CS     -> D8
 *   RESET  -> D9
 *   DC/RS  -> D10
 *   LED    -> 3V3        (always on -- simplest, no pin needed)
 *   VCC    -> 5V         (this board has its own regulator)
 *   GND    -> GND
 *
 *   T_CS   -> D7         (touch -- held HIGH so it stays off the bus)
 *
 * ---------------------------------------------------------------
 * ARDUINO IDE
 * ---------------------------------------------------------------
 *   Board : Arduino UNO Q
 *   Port  : whichever COM port it enumerates as
 *
 * POWER: use a wall charger, not a laptop USB port. Three separate
 * failures tonight were all under-powered rails.
 * ---------------------------------------------------------------
 */

#include <SPI.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ILI9341.h>

// ---- Pins ----
#define TFT_CS     8
#define TFT_RST    9
#define TFT_DC    10
#define TOUCH_CS   7    // held HIGH so the touch chip stays off the SPI bus

Adafruit_ILI9341 tft = Adafruit_ILI9341(TFT_CS, TFT_DC, TFT_RST);

// Auburn palette
#define AU_NAVY   0x0009
#define AU_ORANGE 0xFB60
#define EYE_BLUE  0x5D7F

// Set true while probing with a meter -- loops colours forever.
// Set false to show the animated face.
#define COLOUR_LOOP_MODE  true

int  blinkTimer = 0;
int  lookOffset = 0;
int  lookDir    = 1;

void setup() {
  Serial.begin(115200);
  delay(1200);

  Serial.println();
  Serial.println("=====================================");
  Serial.println(" AUBIEETERNAL Assistant -- UNO Q");
  Serial.println("=====================================");

  // Keep the touch controller off the shared SPI bus.
  // If T_CS floats low, the XPT2046 answers traffic meant for the
  // display and you get a lit but blank screen.
  pinMode(TOUCH_CS, OUTPUT);
  digitalWrite(TOUCH_CS, HIGH);
  Serial.println("Touch CS (D7) held HIGH -- off the bus.");

  Serial.println("Starting display...");
  tft.begin();
  tft.setRotation(1);            // landscape, 320x240
  Serial.println("Display started.");

  // Colour test -- if these are wrong, the wiring is wrong
  Serial.println("Colour test...");
  uint16_t bars[]  = {ILI9341_RED, ILI9341_GREEN, ILI9341_BLUE,
                      ILI9341_WHITE, ILI9341_BLACK};
  const char* names[] = {"RED", "GREEN", "BLUE", "WHITE", "BLACK"};
  for (int i = 0; i < 5; i++) {
    tft.fillScreen(bars[i]);
    Serial.print("   ");
    Serial.println(names[i]);
    delay(600);
  }

  tft.fillScreen(AU_NAVY);
  tft.setTextColor(AU_ORANGE);
  tft.setTextSize(3);
  tft.setCursor(60, 90);
  tft.println("AUBIE");
  tft.setTextSize(1);
  tft.setCursor(85, 130);
  tft.setTextColor(ILI9341_WHITE);
  tft.println("W A R   E A G L E");
  delay(1500);

  Serial.println();
  Serial.println("Saw red/green/blue/white then AUBIE?");
  Serial.println("  Then the display wiring is correct.");
  Serial.println();
}

void drawFace(bool open, int look) {
  tft.fillScreen(AU_NAVY);

  int cy = 110;
  int lx = 105 + look;
  int rx = 215 + look;

  if (open) {
    tft.fillCircle(lx, cy, 34, ILI9341_WHITE);
    tft.fillCircle(rx, cy, 34, ILI9341_WHITE);
    tft.fillCircle(lx + look, cy, 17, EYE_BLUE);
    tft.fillCircle(rx + look, cy, 17, EYE_BLUE);
    tft.fillCircle(lx + look, cy, 8, ILI9341_BLACK);
    tft.fillCircle(rx + look, cy, 8, ILI9341_BLACK);
    tft.fillCircle(lx + look - 6, cy - 8, 4, ILI9341_WHITE);
    tft.fillCircle(rx + look - 6, cy - 8, 4, ILI9341_WHITE);
  } else {
    tft.fillRoundRect(lx - 34, cy - 4, 68, 8, 4, ILI9341_WHITE);
    tft.fillRoundRect(rx - 34, cy - 4, 68, 8, 4, ILI9341_WHITE);
  }

  // snout, jowls, nose
  tft.fillRoundRect(140, 165, 40, 22, 10, AU_ORANGE);
  tft.fillCircle(150, 195, 12, AU_ORANGE);
  tft.fillCircle(170, 195, 12, AU_ORANGE);
  tft.fillCircle(160, 172, 9, ILI9341_BLACK);
}

void loop() {
  if (COLOUR_LOOP_MODE) {
    uint16_t c[]    = {ILI9341_RED, ILI9341_GREEN, ILI9341_BLUE, ILI9341_WHITE};
    const char* n[] = {"RED", "GREEN", "BLUE", "WHITE"};
    for (int i = 0; i < 4; i++) {
      tft.fillScreen(c[i]);
      Serial.print("  filling ");
      Serial.println(n[i]);
      delay(1500);
    }
    return;
  }

  blinkTimer++;
  lookOffset += lookDir;
  if (lookOffset > 8 || lookOffset < -8) lookDir = -lookDir;

  if (blinkTimer % 30 == 0) {
    drawFace(false, lookOffset);
    delay(140);
  }
  drawFace(true, lookOffset);
  delay(100);
}

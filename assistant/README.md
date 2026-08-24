# AUBIEETERNAL Assistant / Teacher

The desk companion. Separate project from the robot dog.

## What it is

A small device that sits on a desk and helps a student through their
lessons. It has a face, a voice, and ears -- but no brain of its own.
The thinking happens on the family's own AUBIEETERNAL install.

That's the whole point: every competing kids' AI device is a subscription
with a microphone shipping audio to someone's server. This one talks to a
computer in the same house.

## Architecture

```
  Assistant (desk)              Home rig
  ----------------              --------
  microphone      ---audio--->  speech to text
  screen (face)                 AUBIEETERNAL brain
  speaker         <---audio---  text to speech
```

The device records, sends, plays, and animates. Nothing else.

## Hardware

**Target:** ESP32-S3 "Xiaozhi" dev board (~$17)
  - built-in I2S microphone, speaker with Class D amp, 1.3" TFT
  - WiFi and Bluetooth
  - Xiaozhi open-source firmware supports self-hosted servers over WebSocket

**Currently prototyping on:** Arduino UNO Q (borrowed from the dog).
  The dog's firmware is backed up at ../dog_sketch/ -- restore with sketch_push.

**Display:** HiLetgo ILI9341 2.8" 240x320 SPI with XPT2046 touch
  - VCC 5V (has its own regulator), backlight to 3V3
  - CS D8, RESET D9, DC D10, MOSI D11, MISO D12, SCK D13, T_CS D7

**Optional:** Arducam Mini 5MP Plus over SPI -- "look at my worksheet and
tell me if I got it right" is the feature that separates this from a
talking speaker.

**No motors in v1.** A device that sits still is useful on day one and
skips a whole category of failure. Wheels can come in v2.

## Cost

| part | cost |
|---|---|
| ESP32-S3 board (mic + speaker + screen) | $17 |
| ILI9341 2.8" display | $16 |
| Arducam (optional) | $40 |
| Printed enclosure | $8 |
| USB power | ~$5 |

Roughly $45 without the camera. Target retail $250.

## Hard-won lessons

- **Power is the recurring failure.** A camera needed a powered hub, a
  display died on a soft 5V rail, and the dog wouldn't boot on the wrong
  USB plug -- all in one night. Use a proper wall supply, not a laptop port.
- **Deselect unused SPI devices.** If the touch controller's CS floats low
  it answers traffic meant for the display, and you get a lit blank screen.
- **The ILI9341 red board wants 5V on VCC.** It has an AMS1117 regulator;
  feed it 3.3V and the controller browns out while the backlight still lights.

## Status

- [x] Display wiring worked out
- [x] Test sketch written
- [ ] Screen confirmed working
- [ ] WiFi to the rig
- [ ] Audio in and out
- [ ] Wake word
- [ ] Enclosure

## Before building more

Ten families using the free software first. Ask them whether they'd pay
$250 for this before spending a month on it. See ../INSTITUTE_PLAN.md.

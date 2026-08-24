# Wiring

## ILI9341 display -> Arduino UNO Q

| screen | Uno Q |
|---|---|
| VCC | 5V |
| GND | GND |
| CS | D8 |
| RESET | D9 |
| DC/RS | D10 |
| SDI/MOSI | D11 |
| SCK | D13 |
| LED | 3V3 |
| SDO/MISO | D12 |
| T_CS | D7 (held HIGH in software) |
| T_CLK / T_DIN / T_DO | share D13 / D11 / D12 |

T_IRQ is not connected -- the touch chip is polled instead.

## If the screen misbehaves

| symptom | cause |
|---|---|
| lit white, no image | DC or CS on the wrong pin, or touch CS floating |
| completely dark | VCC needs 5V, not 3V3 |
| garbled or torn | SPI too fast -- slow it down |
| dim but working | backlight on 3V3 instead of 5V (fine) |

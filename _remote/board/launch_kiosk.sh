#!/bin/bash
# Autostarted on login (see ~/.config/autostart/aubie-kiosk.desktop). Waits a
# beat for the session/PipeWire to settle, forces the HDMI audio profile
# (the touchscreen's built-in speakers) since this board defaults to the
# onboard headphone-jack profile on every fresh session and has no
# persistent way to prefer HDMI otherwise, then launches the kiosk browser.
sleep 6

export XDG_RUNTIME_DIR=/run/user/1000
BUILTIN_ID=$(wpctl status 2>/dev/null | grep "Built-in Audio" | grep -v "playback\|microphone" | head -1 | grep -oE '[0-9]+' | head -1)
if [ -n "$BUILTIN_ID" ]; then
  wpctl set-profile "$BUILTIN_ID" 2 2>/dev/null  # profile index 2 = HDMI (confirmed via pw-cli enum-params)
fi
sleep 1
HDMI_SINK_ID=$(wpctl status 2>/dev/null | grep "HDMI Digital Stereo Output" | grep -oE '[0-9]+' | head -1)
if [ -n "$HDMI_SINK_ID" ]; then
  wpctl set-volume "$HDMI_SINK_ID" 1.0 2>/dev/null  # defaults to 0.40 every fresh session otherwise
fi

pkill -9 chromium 2>/dev/null
sleep 1
exec chromium --kiosk --noerrdialogs --disable-infobars --no-first-run \
  --allow-file-access-from-files \
  --unsafely-treat-insecure-origin-as-secure='http://100.105.81.27:8800' \
  --use-fake-ui-for-media-stream \
  --autoplay-policy=no-user-gesture-required \
  'file:///home/arduino/kiosk/home.html'

# 🦅 AUBIEETERNAL Browser Extension

## Quick Install (Chrome/Edge/Brave)
1. Start the API server: `python api_server.py`
2. Go to `chrome://extensions/`
3. Enable **Developer mode** (top-right toggle)
4. Click **Load unpacked**
5. Select this `AUBIEETERNAL_extension/` folder
6. 🦅 icon appears in toolbar

## Features
- **Popup**: X Bridge, Oracle, Truth Debt Ledger
- **X/Twitter**: 🦅 Analyze button on every tweet
- **Right-click**: "Analyze with AUBIEETERNAL" on any selected text
- **Shortcut**: Ctrl+Shift+A on any selected text
- **Badge**: Shows live Wonder Index on toolbar icon

## Requirements
- `api_server.py` running on port 8502 — either on the same machine as your
  browser, or on your AUBIEETERNAL server reachable over Tailscale (the
  default server URL is set to the Ryzen box's Tailscale IP,
  `100.105.81.27` — change it in the extension popup's settings if your
  server lives elsewhere)
- Chrome, Edge, or Brave (Firefox support coming)

## Privacy
Never talks to the public internet — only ever calls your own AUBIEETERNAL
server, either on localhost or over your private Tailscale network. Zero
external requests.

War Eagle Eternal 🦅 | CC0 Public Domain

# Hardware-dependent backlog

Work items that need the UNO Q tutor board (Tailscale `100.66.110.65`,
`aubie` / `aubie-tutor`) online and reachable to test or flash - kept
separate from `ERROR_LEDGER.md`'s incident history so there's always a
short, current "board's back, do these now" list instead of reconstructing
one from git log or old conversations.

**Why this file exists:** the board going offline for extended periods has
twice stalled all progress on anything that happened to touch it, including
work that didn't actually need live hardware. See CLAUDE.md's "Hardware
offline doesn't mean work stops" section for the process fix. This file is
the concrete list that fix produces - the specific hardware-dependent steps
that stay blocked, tracked explicitly, separate from everything else that
can keep moving regardless of board status.

## How to use this

- Add an item here the moment a task turns out to need live hardware -
  don't let it just sit as an unstated blocker in a conversation.
- Move an item to "Done" (with the date and outcome) once it's actually
  live-tested, not just deployed/flashed - "reached the board" is not
  "worked" (see `ERROR_LEDGER.md`'s port-8420 migration incident for why
  that distinction matters here specifically).
- Keep entries short - one or two lines plus a link to the full
  `ERROR_LEDGER.md` incident for detail. This file is a pointer list, not
  a second copy of the incident record.

## Ready to test/flash now

*(none currently - see "In progress" below)*

## In progress

- [ ] **`flower_explosion` port** - ported from the old
  `spotmicro_dog/sketch/sketch.ino` reference implementation into the
  current `aubie-tutor` sketch.ino, uploaded, and a reflash
  (`arduino-app-cli app restart user:aubie-tutor`) was kicked off
  2026-09-13. The board became slow/unreachable mid-provisioning (heavy
  docker pull load, not a flash failure as far as observed) before the
  outcome could be confirmed. **Next step: once the board is reliably
  reachable again, confirm `arduino-app-cli app list` shows `aubie-tutor`
  `running`, then live-test with a real `/greet` for Gabriela's enrolled
  photo and confirm the flower animation actually executes on the board's
  screen** - not just that the request reaches it (see `ERROR_LEDGER.md`'s
  port-8420 migration incident for why that distinction matters here). A
  pre-flash backup of the old sketch.ino was left on the board at
  `~/ArduinoApps/aubie-tutor/sketch/sketch.ino.pre-flower-explosion-20260913`
  in case a revert is ever needed.

## Blocked on board being online

*(none currently)*

## Done

- [x] **2026-09-13** - `aubie_bridge_api.py` deployed to the board (user
  systemd unit, port 8421), `/snapshot` and `/play_audio` live-tested.
  Person-follow's movement and idle-Pong's `rest`/`play_pong` confirmed
  reaching the board correctly but rejected by the MCU (`stand`/`sit`/
  `rest`/`turn_left`/`turn_right`/`play_pong` are **descoped, not planned**
  - general dog locomotion isn't being pursued, see `ERROR_LEDGER.md`).

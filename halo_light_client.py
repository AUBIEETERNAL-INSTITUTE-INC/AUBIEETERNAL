"""
halo_light_client.py — AUBIEETERNAL Halo Glasses Light Client
=============================================================
The actual app the Brilliant Labs Halo glasses run when no StartOS
rig is present. Handles the full family co-learning session loop
entirely on-device, bridging to the AUBIEETERNAL swarm via Nostr.

Hardware target: Brilliant Labs Frame / Halo glasses
SDK: frame-sdk  (pip install frame-sdk)
Fallback: runs as CLI simulator when glasses not connected

Architecture:
  ┌─────────────────────────────────────────────────────────┐
  │  Halo Glasses (kid or parent)                           │
  │  ┌─────────┐  ┌──────────┐  ┌────────────────────────┐ │
  │  │ Display │  │  Voice   │  │  Bluetooth / WiFi       │ │
  │  │  (HUD)  │  │  Input   │  │  to StartOS or Nostr    │ │
  │  └────┬────┘  └────┬─────┘  └────────────┬───────────┘ │
  │       └────────────┴─────────────────────┘             │
  │                     LightClient                         │
  └─────────────────────────────────────────────────────────┘
          │                              │
   Mode 1: Local                  Mode 2: Nostr
   StartOS at home                Encrypted relay
   /mnt/main/glasses_signal.json  NIP-04 events

Usage:
  python3 halo_light_client.py --mode kid --name Gaby --age 9
  python3 halo_light_client.py --mode parent --name Sarah
  python3 halo_light_client.py --simulate          # desktop test
  python3 halo_light_client.py --pair              # link kid/parent glasses

Requires (install first):
  pip install frame-sdk requests websocket-client --break-system-packages
"""

import os, sys, json, time, argparse, threading, datetime, hashlib
import requests
from pathlib import Path

# ── Try glasses SDK ───────────────────────────────────────────────────────────
try:
    import frame_sdk
    from frame_sdk import Frame
    HAS_GLASSES = True
except ImportError:
    HAS_GLASSES = False

# ── Config ────────────────────────────────────────────────────────────────────
CONFIG_PATH    = Path.home() / ".aubieeternal" / "halo_config.json"
STATE_PATH     = Path.home() / ".aubieeternal" / "session_state.json"
LOG_PATH       = Path.home() / ".aubieeternal" / "halo_events.jsonl"
STARTOS_SIGNAL = Path("/mnt/main/glasses_signal.json")
STARTOS_REPLY  = Path("/mnt/main/glasses_reply.json")
STARTOS_STATUS = Path("/mnt/main/swarm_status.json")

DEFAULT_RELAYS = [
    "wss://relay.damus.io",
    "wss://nos.lol",
    "wss://relay.nostr.band",
    "wss://nostr.wine",
]

# ── HUD Display Layouts ───────────────────────────────────────────────────────
# Brilliant Labs Frame displays text in zones: top, middle, bottom
# Each zone max ~30 chars at normal size

KID_LAYOUT = {
    "idle":    ["🦅 AUBIEETERNAL", "Ready for today's", "lesson?"],
    "lesson":  ["{title}", "{topic_short}", "Coherence: {coh}"],
    "prompt":  ["⚔️ STEELMAN:", "{steelman_short}", "Answer out loud"],
    "scored":  ["Coherence: {coh}", "+{delta} ↑", "+{xp} XP 🦅"],
    "rune":    ["🔴 RUNE EARNED!", "{rune}", "War Eagle 🦅❤️"],
    "genesis": ["🔴 CHILD RUNE", "GENESIS!", "256 reached ✅"],
}

PARENT_LAYOUT = {
    "idle":    ["👨‍👩 PARENT VIEW", "Waiting for", "kid's session"],
    "session": ["{kid_name}: {lesson_short}", "Coh: {coh} {pv_emoji}", "{delta_str} this session"],
    "alert":   ["⚠️ {kid_name}", "{alert_msg}", "Tap to respond"],
    "joined":  ["CO-LEARNING", "{kid_name} + You", "Coh: {coh}"],
}


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG MANAGER
# ══════════════════════════════════════════════════════════════════════════════

def load_config() -> dict:
    """Load device config. Creates defaults if missing."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception:
            pass
    defaults = {
        "profile":      "kid",          # "kid" or "parent"
        "name":         "Explorer",
        "age":          9,
        "nostr_npub":   "",
        "nostr_nsec":   "",
        "paired_npub":  "",             # linked parent/kid's pubkey
        "relays":       DEFAULT_RELAYS,
        "startos_ip":   "192.168.1.251",
        "auto_detect":  True,
        "brightness":   70,
        "font_size":    "medium",
    }
    CONFIG_PATH.write_text(json.dumps(defaults, indent=2))
    return defaults

def save_config(cfg: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))


# ══════════════════════════════════════════════════════════════════════════════
# TRANSPORT LAYER — auto-detects StartOS vs Nostr
# ══════════════════════════════════════════════════════════════════════════════

class Transport:
    """Handles signal routing. Auto-detects mode each call."""

    def __init__(self, cfg: dict):
        self.cfg     = cfg
        self.mode    = "unknown"
        self._detect()

    def _detect(self) -> str:
        """Check if local StartOS is reachable."""
        # Check local file presence first (fastest)
        if STARTOS_STATUS.exists():
            self.mode = "startos"
            return "startos"
        # Try HTTP ping to StartOS
        try:
            r = requests.get(
                f"http://{self.cfg.get('startos_ip','192.168.1.251')}/health",
                timeout=1.5
            )
            if r.status_code < 500:
                self.mode = "startos"
                return "startos"
        except Exception:
            pass
        self.mode = "nostr"
        return "nostr"

    def send(self, event_type: str, data: dict) -> bool:
        """Send a signal to the swarm. Returns True if delivered."""
        self._detect()
        payload = {
            "type":      event_type,
            "version":   "1.0",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            **data,
        }
        if self.mode == "startos":
            return self._send_local(payload)
        return self._send_nostr(payload)

    def receive(self, timeout: float = 5.0) -> dict | None:
        """Poll for a swarm reply. Returns reply dict or None."""
        self._detect()
        if self.mode == "startos":
            return self._recv_local(timeout)
        return self._recv_nostr(timeout)

    def _send_local(self, payload: dict) -> bool:
        try:
            STARTOS_SIGNAL.parent.mkdir(parents=True, exist_ok=True)
            STARTOS_SIGNAL.write_text(json.dumps(payload, indent=2))
            _log(f"[local] → {payload['type']}")
            return True
        except Exception as e:
            _log(f"[local] send error: {e}")
            return False

    def _recv_local(self, timeout: float) -> dict | None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if STARTOS_REPLY.exists():
                try:
                    reply = json.loads(STARTOS_REPLY.read_text())
                    STARTOS_REPLY.unlink()
                    _log(f"[local] ← {reply.get('type','?')}")
                    return reply
                except Exception:
                    pass
            time.sleep(0.3)
        return None

    def _send_nostr(self, payload: dict) -> bool:
        """Send encrypted NIP-04 event to Nostr relays."""
        nsec = self.cfg.get("nostr_nsec", "")
        if not nsec:
            _log("[nostr] ⚠️  nsec not configured — cannot send")
            return False
        try:
            from nostr_glasses_bridge import GlassesBridge, build_aubie_payload
            bridge = GlassesBridge()
            ok = bridge.send(payload["type"], payload)
            bridge.close()
            return ok
        except ImportError:
            # Fallback: simulate send for testing
            _log(f"[nostr] ⚡ Simulated: {payload['type']} (nostr_glasses_bridge.py not found)")
            return True
        except Exception as e:
            _log(f"[nostr] send error: {e}")
            return False

    def _recv_nostr(self, timeout: float) -> dict | None:
        """Listen for swarm reply on Nostr relays."""
        try:
            from nostr_glasses_bridge import GlassesBridge
            bridge   = GlassesBridge()
            received = {}

            def on_reply(event_type, data):
                received["data"] = data

            bridge.connect_relays()
            bridge.listen(on_reply, duration=min(timeout, 8.0))
            bridge.close()
            return received.get("data")
        except ImportError:
            # Simulate a reply for testing
            time.sleep(min(timeout, 1.5))
            return {"type": "reply", "status": "simulated", "coherence": 0.75}
        except Exception as e:
            _log(f"[nostr] recv error: {e}")
            return None

    @property
    def status_label(self) -> str:
        icon = "🟢" if self.mode == "startos" else "🟡"
        label = "StartOS (local)" if self.mode == "startos" else "Nostr (relay)"
        return f"{icon} {label}"


# ══════════════════════════════════════════════════════════════════════════════
# DISPLAY ENGINE — Brilliant Labs Frame OR terminal simulator
# ══════════════════════════════════════════════════════════════════════════════

class Display:
    """Abstract HUD display. Uses real Frame SDK or terminal fallback."""

    def __init__(self, simulate: bool = False):
        self.simulate = simulate or not HAS_GLASSES
        self.frame    = None
        if not self.simulate:
            try:
                self.frame = Frame()
                print("[display] ✅ Brilliant Labs Frame connected")
            except Exception as e:
                print(f"[display] Frame not found ({e}) — using terminal simulator")
                self.simulate = True

    def show(self, lines: list[str], color: str = "white"):
        """
        Display up to 3 lines on the glasses HUD.
        lines: [top_line, middle_line, bottom_line]
        """
        if self.simulate:
            self._terminal_show(lines, color)
        else:
            self._frame_show(lines, color)

    def _terminal_show(self, lines: list[str], color: str):
        colors = {"white": "\033[97m", "green": "\033[92m",
                  "orange": "\033[93m", "red": "\033[91m",
                  "cyan": "\033[96m", "purple": "\033[95m"}
        reset = "\033[0m"
        c     = colors.get(color, "\033[97m")
        width = 36
        print(f"\n{c}┌{'─'*width}┐")
        for line in (lines + [""] * 3)[:3]:
            print(f"│ {line[:width-2]:<{width-2}} │")
        print(f"└{'─'*width}┘{reset}")

    def _frame_show(self, lines: list[str], color: str):
        """Write text to Brilliant Labs Frame display."""
        try:
            import asyncio
            async def _write():
                async with self.frame:
                    await self.frame.display.clear()
                    y_positions = [30, 80, 130]
                    for i, line in enumerate(lines[:3]):
                        if line:
                            await self.frame.display.show_text(
                                line, x=10, y=y_positions[i]
                            )
            asyncio.run(_write())
        except Exception as e:
            self._terminal_show(lines, color)

    def clear(self):
        if self.simulate:
            print("\033[2J\033[H", end="")
        else:
            try:
                import asyncio
                async def _clear():
                    async with self.frame:
                        await self.frame.display.clear()
                asyncio.run(_clear())
            except Exception:
                pass

    def celebration(self):
        """Flash animation for XP/rune earned."""
        if self.simulate:
            for _ in range(3):
                self.show(["✨ ✨ ✨", "EARNED!", "✨ ✨ ✨"], color="orange")
                time.sleep(0.4)
                self.clear()
                time.sleep(0.2)
        else:
            # Frame SDK brightness flash
            try:
                import asyncio
                async def _flash():
                    async with self.frame:
                        for _ in range(3):
                            await self.frame.display.show_text("✨ EARNED! ✨", x=10, y=80)
                            await asyncio.sleep(0.4)
                            await self.frame.display.clear()
                            await asyncio.sleep(0.2)
                asyncio.run(_flash())
            except Exception:
                self.celebration()  # fallback


# ══════════════════════════════════════════════════════════════════════════════
# VOICE INPUT — mic or keyboard fallback
# ══════════════════════════════════════════════════════════════════════════════

class VoiceInput:
    """Captures voice or keyboard input from the kid/parent."""

    def __init__(self, simulate: bool = False):
        self.simulate = simulate
        try:
            import speech_recognition as sr
            self.recognizer = sr.Recognizer()
            self.mic        = sr.Microphone()
            self.has_voice  = True
        except ImportError:
            self.has_voice  = False

    def listen(self, prompt: str = "Listening...", timeout: float = 15.0) -> str:
        """
        Returns transcribed text.
        Falls back to keyboard input if voice not available.
        """
        print(f"\n🎤 {prompt}")
        if self.simulate or not self.has_voice:
            return input("   Type answer: ").strip()

        try:
            import speech_recognition as sr
            with self.mic as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=30)
            text = self.recognizer.recognize_google(audio)
            print(f"   Heard: '{text}'")
            return text
        except Exception as e:
            print(f"   Voice failed ({e}) — type instead:")
            return input("   > ").strip()

    def wait_gesture(self, prompt: str = "Tap to continue") -> bool:
        """Wait for a glasses tap gesture or Enter key."""
        print(f"\n👆 {prompt} [press Enter]")
        input()
        return True


# ══════════════════════════════════════════════════════════════════════════════
# SESSION MANAGER — coordinates HUD + transport + voice
# ══════════════════════════════════════════════════════════════════════════════

class HaloSession:
    """
    Runs a full co-learning session on the glasses.
    Works for both kid and parent roles.
    """

    def __init__(self, cfg: dict, simulate: bool = False):
        self.cfg       = cfg
        self.profile   = cfg.get("profile", "kid")
        self.name      = cfg.get("name", "Explorer")
        self.age       = cfg.get("age", 9)
        self.transport = Transport(cfg)
        self.display   = Display(simulate)
        self.voice     = VoiceInput(simulate)
        self.state     = self._load_state()

        print(f"\n🥽 Halo Light Client — {self.profile.upper()} — {self.name}")
        print(f"   Transport: {self.transport.status_label}")
        print(f"   Display:   {'Terminal sim' if self.display.simulate else 'Frame glasses'}")
        print(f"   Voice:     {'Available' if self.voice.has_voice else 'Keyboard fallback'}")

    # ── Kid Flow ──────────────────────────────────────────────────────────────
    def run_kid_flow(self):
        """Full kid session: lesson → steelman → score → celebrate."""

        # 1. Show idle screen
        self.display.show(KID_LAYOUT["idle"], color="cyan")
        print(f"\n👧 Welcome, {self.name}!")
        time.sleep(1)

        # 2. Ask for lesson (voice or text)
        self.display.show(["What lesson today?", "Say a topic or", "press Enter to browse"], color="cyan")
        lesson_request = self.voice.listen("Say your lesson topic (or Enter to browse)")

        if not lesson_request:
            lesson_request = "courage"

        # 3. Send lesson request to swarm
        self.display.show(["🦅 Asking swarm...", "One moment", "..."], color="cyan")
        ok = self.transport.send("lesson_request", {
            "kid_name":  self.name,
            "kid_age":   self.age,
            "lesson":    lesson_request,
            "coherence": self.state.get("last_coherence", 0.72),
            "polyvagal": self.state.get("last_polyvagal", "ventral_vagal"),
        })

        # 4. Wait for swarm reply
        reply = self.transport.receive(timeout=8.0)
        if not reply:
            reply = {
                "message":  f"Ready for {lesson_request}! Let's go, {self.name}! 🦅",
                "steelman": f"What is the strongest argument AGAINST {lesson_request}?",
                "coherence": 0.72,
            }

        lesson_title   = reply.get("lesson", lesson_request)
        steelman       = reply.get("steelman", f"What is the strongest argument AGAINST {lesson_request}?")
        coherence      = float(reply.get("coherence", 0.72))

        # 5. Show lesson
        topic_short = lesson_title[:28]
        self.display.show([
            lesson_title[:32],
            reply.get("message", "")[:32],
            f"Coherence: {coherence:.2f}",
        ], color="cyan")
        print(f"\n📖 Lesson: {lesson_title}")
        print(f"   {reply.get('message','')}")
        time.sleep(2)

        # 6. Show steelman prompt
        self.display.show([
            "⚔️ STEELMAN:",
            steelman[:32],
            "Answer out loud 🎤",
        ], color="orange")
        print(f"\n⚔️  Steelman prompt: {steelman}")

        self.voice.wait_gesture("Ready? Tap to start answering")

        # 7. Record answer
        answer = self.voice.listen(f"Answer the steelman, {self.name}", timeout=30.0)
        if not answer:
            answer = "I need more time to think about this."

        # 8. Send answer to swarm for scoring
        self.display.show(["🤖 Scoring...", "ORACLE + STEELMAN", "daughters..."], color="purple")
        ok = self.transport.send("steelman_submit", {
            "kid_name":  self.name,
            "kid_age":   self.age,
            "lesson":    lesson_title,
            "answer":    answer,
            "coherence": coherence,
        })

        score_reply = self.transport.receive(timeout=8.0)
        if not score_reply:
            # Local fallback scoring
            words    = answer.split()
            quality  = ["because","therefore","argument","even if","consider","strongest"]
            bonus    = sum(0.02 for w in quality if w.lower() in answer.lower())
            delta    = round(min(0.20, 0.06 + len(words) * 0.003 + bonus), 3)
            new_coh  = round(min(1.0, coherence + delta), 3)
            score_reply = {
                "coherence_after": new_coh,
                "coherence_delta": delta,
                "feedback":        f"Strong thinking, {self.name}! Coherence +{delta:.2f} 🦅",
                "xp_earned":       18,
            }

        new_coh   = float(score_reply.get("coherence_after", coherence + 0.10))
        delta     = float(score_reply.get("coherence_delta", 0.10))
        feedback  = score_reply.get("feedback", f"Well done, {self.name}!")
        xp        = score_reply.get("xp_earned", 15)

        # 9. Show result
        delta_str = f"+{delta:.2f}" if delta >= 0 else f"{delta:.2f}"
        self.display.show([
            f"Coherence: {new_coh:.2f}",
            f"{delta_str} ↑  +{xp} XP",
            "🦅 War Eagle!",
        ], color="green")

        print(f"\n✅ {feedback}")
        print(f"   Coherence: {coherence:.2f} → {new_coh:.2f} (Δ{delta_str})")
        print(f"   XP earned: +{xp}")

        self.display.celebration()
        time.sleep(1)

        # 10. Check Child Rune progress
        self._check_display_child_rune(new_coh)

        # 11. End session
        self.transport.send("session_end", {
            "kid_name":        self.name,
            "lesson":          lesson_title,
            "coherence_start": coherence,
            "coherence":       new_coh,
            "xp_total":        xp,
        })

        # 12. Update local state
        self.state["last_coherence"] = new_coh
        self.state["last_lesson"]    = lesson_title
        self.state["last_session"]   = datetime.datetime.now().isoformat()
        self.state["total_xp"]       = self.state.get("total_xp", 0) + xp
        self._save_state()

        self.display.show([
            f"Session complete!",
            f"Total XP: {self.state['total_xp']}",
            "War Eagle 🦅❤️",
        ], color="green")
        print(f"\n🦅 Session complete! Total XP: {self.state['total_xp']}")

    # ── Parent Flow ───────────────────────────────────────────────────────────
    def run_parent_flow(self):
        """Parent observer flow: show kid's live session state."""
        print(f"\n👨‍👩 Parent observer mode — {self.name}")
        print(f"   Polling for {self.cfg.get('paired_npub','(no kid linked)')[:20]}...")

        self.display.show(PARENT_LAYOUT["idle"], color="purple")

        poll_count = 0
        while True:
            poll_count += 1

            # Poll StartOS session state or Nostr
            kid_state = self._poll_kid_state()

            if kid_state:
                kid_name  = kid_state.get("kid_name", "Kid")
                lesson    = kid_state.get("lesson", "")[:18]
                coh       = kid_state.get("coherence", 0.72)
                pv        = kid_state.get("polyvagal", "")
                pv_emoji  = "🟢" if "ventral" in pv.lower() else ("🟡" if "sympathetic" in pv.lower() else "🔴")
                delta     = kid_state.get("coherence_delta", 0)
                delta_str = f"+{delta:.2f}" if delta >= 0 else f"{delta:.2f}"

                self.display.show([
                    f"{kid_name}: {lesson}",
                    f"Coh: {coh:.2f} {pv_emoji}",
                    f"{delta_str} this session",
                ], color="purple")

                print(f"\r👨‍👩 {kid_name} | Coh: {coh:.2f} {pv_emoji} | Δ{delta_str} | Lesson: {lesson[:20]}", end="", flush=True)

                # Alert if kid struggling
                if coh < 0.55:
                    self.display.show([
                        f"⚠️ {kid_name}",
                        "May need support",
                        "Tap to respond",
                    ], color="orange")
                    action = input(f"\n\n⚠️  {kid_name} coherence low ({coh:.2f}). Send encouragement? [y/n]: ")
                    if action.lower().startswith("y"):
                        msg = self.voice.listen("Say your message", timeout=10.0) or f"You've got this, {kid_name}! ❤️"
                        self.transport.send("parent_action", {
                            "action":      "encourage",
                            "parent_name": self.name,
                            "message":     msg,
                        })
            else:
                if poll_count % 5 == 0:
                    print(f"\r👨‍👩 Waiting for session... (poll {poll_count})", end="", flush=True)

            time.sleep(3)

    def _poll_kid_state(self) -> dict | None:
        """Check for live kid session state from StartOS or Nostr."""
        # Check local session file
        session_path = Path("/mnt/main/family_session.json")
        if session_path.exists():
            try:
                data     = json.loads(session_path.read_text())
                kid_hud  = data.get("kid_hud", {})
                return {
                    "kid_name":        kid_hud.get("kid_name", ""),
                    "lesson":          kid_hud.get("lesson_title", ""),
                    "coherence":       kid_hud.get("coherence", 0.72),
                    "polyvagal":       kid_hud.get("polyvagal", {}).get("label", ""),
                    "coherence_delta": 0,
                }
            except Exception:
                pass
        return None

    def _check_display_child_rune(self, current_coherence: float):
        """Show Child Rune progress or Genesis celebration on HUD."""
        try:
            if STARTOS_STATUS.exists():
                sw            = json.loads(STARTOS_STATUS.read_text())
                confirmations = sw.get("rune_confirmations", 0)
                already_ready = sw.get("child_rune_ready", False)

                if already_ready or confirmations >= 256:
                    # Celebration!
                    for _ in range(3):
                        self.display.show(KID_LAYOUT["genesis"], color="orange")
                        time.sleep(0.8)
                        self.display.clear()
                        time.sleep(0.4)
                    print("\n🔴 CHILD RUNE GENESIS — 256 confirmations! Inscription ready!")
                elif confirmations >= 220:
                    # Getting close — show progress
                    self.display.show([
                        f"🔴 Child Rune",
                        f"{confirmations}/256",
                        f"{256-confirmations} to genesis!",
                    ], color="orange")
                    time.sleep(2)
        except Exception:
            pass

    # ── Pairing ───────────────────────────────────────────────────────────────
    def pair_devices(self):
        """Link kid and parent glasses via shared keypair."""
        print("\n🔗 DEVICE PAIRING")
        print("=" * 40)

        profile = input("Is this the KID or PARENT glasses? [kid/parent]: ").strip().lower()
        name    = input(f"Name for this {profile}: ").strip()
        npub    = input("Your Nostr npub (optional, press Enter to skip): ").strip()

        if profile == "kid":
            age = input("Kid's age: ").strip()
            self.cfg["age"] = int(age) if age.isdigit() else 9

        paired_npub = input("Paired device's npub (optional): ").strip()

        self.cfg["profile"]     = profile
        self.cfg["name"]        = name
        self.cfg["nostr_npub"]  = npub
        self.cfg["paired_npub"] = paired_npub
        save_config(self.cfg)

        print(f"\n✅ Paired: {profile} — {name}")
        print(f"   Config saved to {CONFIG_PATH}")
        if npub:
            print(f"   Nostr identity: {npub[:20]}...")

    # ── State persistence ─────────────────────────────────────────────────────
    def _load_state(self) -> dict:
        if STATE_PATH.exists():
            try:
                return json.loads(STATE_PATH.read_text())
            except Exception:
                pass
        return {"total_xp": 0, "sessions": 0, "last_coherence": 0.72}

    def _save_state(self):
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.state["sessions"] = self.state.get("sessions", 0) + 1
        STATE_PATH.write_text(json.dumps(self.state, indent=2))


# ── Logging ───────────────────────────────────────────────────────────────────
def _log(msg: str):
    ts   = datetime.datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AUBIEETERNAL Halo Glasses Light Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 halo_light_client.py --simulate           # test on desktop
  python3 halo_light_client.py --mode kid --name Gaby --age 9
  python3 halo_light_client.py --mode parent --name Sarah
  python3 halo_light_client.py --pair               # set up new glasses
  python3 halo_light_client.py --status             # check connection
        """
    )
    parser.add_argument("--mode",     choices=["kid","parent"], help="Profile mode")
    parser.add_argument("--name",     help="Name for this user")
    parser.add_argument("--age",      type=int, help="Kid's age")
    parser.add_argument("--simulate", action="store_true", help="Desktop terminal mode")
    parser.add_argument("--pair",     action="store_true", help="Pair kid + parent glasses")
    parser.add_argument("--status",   action="store_true", help="Check connection status")
    parser.add_argument("--install",  action="store_true", help="Show install instructions")
    args = parser.parse_args()

    if args.install:
        print("\n📦 Install dependencies for Halo Light Client:")
        print("pip install frame-sdk requests websocket-client speechrecognition --break-system-packages")
        print("pip install pyaudio --break-system-packages  # for voice input")
        print("\nFor Brilliant Labs Frame glasses:")
        print("  pip install frame-sdk --break-system-packages")
        print("  Then pair via Bluetooth in the Frame app first")
        print("\nFor Nostr bridge:")
        print("  Set NOSTR_NSEC and NOSTR_NPUB in /mnt/main/api_keys.env")
        sys.exit(0)

    cfg = load_config()

    # Apply CLI overrides
    if args.mode:  cfg["profile"] = args.mode
    if args.name:  cfg["name"]    = args.name
    if args.age:   cfg["age"]     = args.age

    client = HaloSession(cfg, simulate=args.simulate or not HAS_GLASSES)

    if args.status:
        print(f"\n🥽 Halo Light Client Status")
        print("=" * 40)
        print(f"  Profile:   {cfg['profile']} — {cfg['name']}")
        print(f"  Transport: {client.transport.status_label}")
        print(f"  Display:   {'Terminal sim' if client.display.simulate else 'Frame glasses connected'}")
        print(f"  Voice:     {'Available' if client.voice.has_voice else 'Keyboard fallback'}")
        print(f"  Config:    {CONFIG_PATH}")
        print(f"  Nostr npub: {cfg.get('nostr_npub','not set')[:30]}")
        print(f"  Paired:    {cfg.get('paired_npub','not paired')[:30]}")
        sw_ok = STARTOS_STATUS.exists()
        print(f"  StartOS:   {'✅ connected' if sw_ok else '⚠️  not found (Nostr mode)'}")
        if sw_ok:
            try:
                sw = json.loads(STARTOS_STATUS.read_text())
                print(f"  Rune conf: {sw.get('rune_confirmations',0)}/256")
                print(f"  Wonder:    {sw.get('wonder_index','—')}")
            except Exception:
                pass
        sys.exit(0)

    if args.pair:
        client.pair_devices()
        sys.exit(0)

    # ── Run session ───────────────────────────────────────────────────────────
    print(f"\n🦅 AUBIEETERNAL Halo Light Client v1.0")
    print(f"   War Eagle Eternal ❤️")

    if cfg["profile"] == "parent":
        client.run_parent_flow()
    else:
        while True:
            client.run_kid_flow()
            again = input("\n\nAnother session? [y/n]: ").strip().lower()
            if not again.startswith("y"):
                break
    print("\n🦅 Session closed. War Eagle Eternal!")

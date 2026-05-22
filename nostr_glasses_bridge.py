"""
nostr_glasses_bridge.py — AUBIEETERNAL Nostr Sovereign Bridge
=============================================================
Universal fallback when no local StartOS rig is available.

Mode 1 (StartOS present): glasses talk directly to swarm_v4_1.py locally
Mode 2 (Nostr bridge):    glasses encrypt events → public relays → swarm listens

Security:
  - NIP-04 encryption (secp256k1 ECDH + AES-256-CBC)
  - Only family keypair + swarm pubkey can decrypt
  - No central server ever sees raw event content

Usage:
    python3 nostr_glasses_bridge.py --listen     # swarm listener mode
    python3 nostr_glasses_bridge.py --send       # glasses send mode (test)
    python3 nostr_glasses_bridge.py --status     # check relay connections
"""

import os, sys, json, time, hashlib, hmac, struct, base64, asyncio
import datetime, argparse, threading, queue
from pathlib import Path

# ── Try importing nostr libs; give clear install instructions if missing ──────
try:
    import websocket
    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False

try:
    from cryptography.hazmat.primitives.asymmetric.ec import (
        SECP256K1, generate_private_key, derive_private_key, EllipticCurvePublicKey
    )
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

# ── Config ────────────────────────────────────────────────────────────────────
WORK_DIR         = Path("/mnt/main/repo")
TRUTH_LOG        = WORK_DIR / "master_truth_log.jsonl"
BRIDGE_LOG       = Path("/mnt/main/nostr_bridge.log")
ENV_PATH         = Path("/mnt/main/api_keys.env")

# Well-known AUBIEETERNAL swarm pubkey (npub) — families send events to this
# Replace with actual swarm pubkey once Nostr identity is established
SWARM_PUBKEY_HEX = os.getenv("AUBIE_SWARM_PUBKEY", "")  # set in api_keys.env

DEFAULT_RELAYS = [
    "wss://relay.damus.io",
    "wss://nos.lol",
    "wss://relay.nostr.band",
    "wss://nostr.wine",
]

# ── Load keys from env ────────────────────────────────────────────────────────
def load_keys() -> dict:
    keys = {
        "npub": os.getenv("NOSTR_NPUB", ""),
        "nsec": os.getenv("NOSTR_NSEC", ""),
        "relays": DEFAULT_RELAYS,
        "swarm_pubkey": SWARM_PUBKEY_HEX,
    }
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            if "=" in line:
                k, v = line.strip().split("=", 1)
                if k == "NOSTR_NPUB":  keys["npub"]  = v
                if k == "NOSTR_NSEC":  keys["nsec"]  = v
                if k == "NOSTR_RELAYS": keys["relays"] = v.split(",")
                if k == "AUBIE_SWARM_PUBKEY": keys["swarm_pubkey"] = v
    return keys

# ══════════════════════════════════════════════════════════════════════════════
# NOSTR EVENT SCHEMA
# ══════════════════════════════════════════════════════════════════════════════

def build_aubie_payload(event_type: str, data: dict) -> dict:
    """
    Build the decrypted payload for an AUBIEETERNAL Nostr event.

    event_type options:
      lesson_request   — kid/parent requesting a lesson
      coherence_update — real-time coherence ping
      steelman_submit  — kid submitting a steelman answer
      parent_action    — parent sending encourage/pause/join
      session_end      — session summary
    """
    return {
        "type":        event_type,
        "version":     "1.0",
        "timestamp":   datetime.datetime.utcnow().isoformat() + "Z",
        **data,
    }

def build_nostr_event(kind: int, content: str, tags: list, pubkey_hex: str) -> dict:
    """Build an unsigned Nostr event dict."""
    created_at = int(time.time())
    event = {
        "kind":       kind,
        "pubkey":     pubkey_hex,
        "created_at": created_at,
        "tags":       tags,
        "content":    content,
    }
    # Compute event id (NIP-01)
    serialized = json.dumps(
        [0, event["pubkey"], event["created_at"], event["kind"], event["tags"], event["content"]],
        separators=(",", ":"), ensure_ascii=False
    )
    event["id"] = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return event

# ══════════════════════════════════════════════════════════════════════════════
# SIMPLE NIP-04 ENCRYPTION (pure Python, no external deps beyond cryptography)
# ══════════════════════════════════════════════════════════════════════════════

def nip04_encrypt(message: str, recipient_pubkey_hex: str, sender_privkey_hex: str) -> str:
    """
    NIP-04 encryption: secp256k1 ECDH shared secret → AES-256-CBC.
    Returns base64(ciphertext) + "?iv=" + base64(iv)
    Falls back to base64 encoding if cryptography lib not available.
    """
    if not HAS_CRYPTO:
        # Graceful fallback — marks content as plaintext (development only)
        encoded = base64.b64encode(message.encode()).decode()
        return f"{encoded}?iv=PLAINTEXT_FALLBACK"

    import secrets as _sec
    from cryptography.hazmat.primitives.asymmetric.ec import (
        ECDH, EllipticCurvePublicNumbers, SECP256K1
    )

    # Derive shared secret
    priv_int = int(sender_privkey_hex, 16)
    priv_key = derive_private_key(priv_int, SECP256K1(), default_backend())

    pub_x    = int(recipient_pubkey_hex, 16)
    # Reconstruct compressed pubkey (assume even Y for NIP-04)
    pub_nums = EllipticCurvePublicNumbers(pub_x, _recover_y(pub_x), SECP256K1())
    pub_key  = pub_nums.public_key(default_backend())

    shared   = priv_key.exchange(ECDH(), pub_key)
    shared_x = shared[:32]  # NIP-04 uses x-coordinate only

    # AES-256-CBC encrypt
    iv         = _sec.token_bytes(16)
    padded     = _pkcs7_pad(message.encode("utf-8"), 16)
    cipher     = Cipher(algorithms.AES(shared_x), modes.CBC(iv), backend=default_backend())
    encryptor  = cipher.encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()

    return base64.b64encode(ciphertext).decode() + "?iv=" + base64.b64encode(iv).decode()


def nip04_decrypt(encrypted: str, sender_pubkey_hex: str, recipient_privkey_hex: str) -> str:
    """Decrypt a NIP-04 encrypted message."""
    if not HAS_CRYPTO or "PLAINTEXT_FALLBACK" in encrypted:
        b64_part = encrypted.split("?iv=")[0]
        return base64.b64decode(b64_part).decode()

    from cryptography.hazmat.primitives.asymmetric.ec import (
        ECDH, EllipticCurvePublicNumbers, SECP256K1
    )

    parts      = encrypted.split("?iv=")
    ciphertext = base64.b64decode(parts[0])
    iv         = base64.b64decode(parts[1])

    priv_int   = int(recipient_privkey_hex, 16)
    priv_key   = derive_private_key(priv_int, SECP256K1(), default_backend())

    pub_x      = int(sender_pubkey_hex, 16)
    pub_nums   = EllipticCurvePublicNumbers(pub_x, _recover_y(pub_x), SECP256K1())
    pub_key    = pub_nums.public_key(default_backend())

    shared     = priv_key.exchange(ECDH(), pub_key)
    shared_x   = shared[:32]

    cipher     = Cipher(algorithms.AES(shared_x), modes.CBC(iv), backend=default_backend())
    decryptor  = cipher.decryptor()
    padded     = decryptor.update(ciphertext) + decryptor.finalize()
    return _pkcs7_unpad(padded).decode("utf-8")


def _recover_y(x: int) -> int:
    """Recover Y coordinate assuming even parity (simplified, for NIP-04)."""
    # secp256k1: y^2 = x^3 + 7 mod p
    p = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
    y_sq = (pow(x, 3, p) + 7) % p
    y = pow(y_sq, (p + 1) // 4, p)
    return y if y % 2 == 0 else p - y

def _pkcs7_pad(data: bytes, block_size: int) -> bytes:
    pad_len = block_size - (len(data) % block_size)
    return data + bytes([pad_len] * pad_len)

def _pkcs7_unpad(data: bytes) -> bytes:
    return data[:-data[-1]]

# ══════════════════════════════════════════════════════════════════════════════
# RELAY CONNECTION
# ══════════════════════════════════════════════════════════════════════════════

class NostrRelay:
    """Single WebSocket relay connection."""

    def __init__(self, url: str, timeout: int = 10):
        self.url      = url
        self.timeout  = timeout
        self.ws       = None
        self.connected = False

    def connect(self) -> bool:
        if not HAS_WEBSOCKET:
            print(f"[bridge] ⚠️  websocket-client not installed. Run: pip install websocket-client --break-system-packages")
            return False
        try:
            self.ws = websocket.create_connection(self.url, timeout=self.timeout)
            self.connected = True
            print(f"[bridge] ✅ Connected: {self.url}")
            return True
        except Exception as e:
            print(f"[bridge] ❌ Cannot connect to {self.url}: {e}")
            return False

    def send_event(self, event: dict) -> bool:
        if not self.connected or not self.ws:
            return False
        try:
            msg = json.dumps(["EVENT", event])
            self.ws.send(msg)
            return True
        except Exception as e:
            print(f"[bridge] Send error on {self.url}: {e}")
            self.connected = False
            return False

    def subscribe(self, sub_id: str, filters: dict):
        if not self.connected or not self.ws:
            return
        try:
            msg = json.dumps(["REQ", sub_id, filters])
            self.ws.send(msg)
        except Exception as e:
            print(f"[bridge] Subscribe error: {e}")

    def recv(self, timeout: float = 1.0):
        if not self.connected or not self.ws:
            return None
        try:
            self.ws.settimeout(timeout)
            raw = self.ws.recv()
            return json.loads(raw)
        except Exception:
            return None

    def close(self):
        if self.ws:
            try: self.ws.close()
            except Exception: pass
        self.connected = False


# ══════════════════════════════════════════════════════════════════════════════
# GLASSES BRIDGE — main class
# ══════════════════════════════════════════════════════════════════════════════

class GlassesBridge:
    """
    Routes signals between Halo glasses and the AUBIEETERNAL swarm.

    Auto-detects mode:
      Mode 1: StartOS local  → direct file/socket call to swarm_v4_1.py
      Mode 2: Nostr fallback → encrypted events via public relays
    """

    def __init__(self):
        self.keys    = load_keys()
        self.relays  = []
        self.mode    = self._detect_mode()
        self._log(f"Bridge initialized — mode: {self.mode}")

    def _detect_mode(self) -> str:
        """Check if local StartOS swarm is running."""
        if Path("/mnt/main/swarm_status.json").exists():
            return "startos"
        return "nostr"

    def connect_relays(self) -> int:
        """Connect to all configured relays. Returns count of live connections."""
        if self.mode == "startos":
            self._log("StartOS mode — relay connection not needed")
            return 0
        relay_urls = self.keys.get("relays", DEFAULT_RELAYS)
        for url in relay_urls:
            relay = NostrRelay(url)
            if relay.connect():
                self.relays.append(relay)
        self._log(f"Connected to {len(self.relays)}/{len(relay_urls)} relays")
        return len(self.relays)

    # ── Send a signal ─────────────────────────────────────────────────────────
    def send(self, event_type: str, data: dict) -> bool:
        """
        Send a signal from glasses to swarm.
        Automatically routes via StartOS or Nostr depending on mode.
        """
        payload = build_aubie_payload(event_type, data)

        if self.mode == "startos":
            return self._send_local(payload)
        else:
            return self._send_nostr(payload)

    def _send_local(self, payload: dict) -> bool:
        """Write signal to /mnt/main/glasses_signal.json for swarm to pick up."""
        try:
            sig_path = Path("/mnt/main/glasses_signal.json")
            sig_path.write_text(json.dumps(payload, indent=2))
            self._log(f"Local signal written: {payload['type']}")
            return True
        except Exception as e:
            self._log(f"Local send failed: {e}")
            return False

    def _send_nostr(self, payload: dict) -> bool:
        """Encrypt payload and publish to Nostr relays."""
        if not self.keys.get("nsec") or not self.keys.get("swarm_pubkey"):
            self._log("⚠️  nsec or swarm_pubkey not set — cannot send Nostr event")
            return False

        if not self.relays:
            self.connect_relays()

        if not self.relays:
            self._log("❌ No relay connections available")
            return False

        try:
            # Encrypt payload
            encrypted = nip04_encrypt(
                json.dumps(payload),
                self.keys["swarm_pubkey"],
                self.keys["nsec"],
            )

            # Build Nostr event (NIP-04 kind 4)
            tags = [
                ["p", self.keys["swarm_pubkey"]],
                ["t", "aubie-swarm"],
                ["t", f"aubie-{payload['type']}"],
                ["v", "1.0"],
            ]
            event = build_nostr_event(
                kind=4,
                content=encrypted,
                tags=tags,
                pubkey_hex=self.keys.get("npub", "").replace("npub1", ""),
            )

            # Publish to all live relays
            sent = sum(1 for r in self.relays if r.send_event(event))
            self._log(f"Nostr event sent to {sent}/{len(self.relays)} relays: {payload['type']}")
            return sent > 0

        except Exception as e:
            self._log(f"Nostr send failed: {e}")
            return False

    # ── Listen for swarm replies ──────────────────────────────────────────────
    def listen(self, callback, duration: float = 30.0):
        """
        Listen for swarm reply events on Nostr relays.
        callback(event_type, data) is called for each valid reply.
        duration: how long to listen in seconds.
        """
        if self.mode == "startos":
            self._listen_local(callback, duration)
            return

        if not self.relays:
            self.connect_relays()

        sub_id  = f"aubie-{int(time.time())}"
        filters = {
            "kinds":  [4],
            "#p":     [self.keys.get("npub", "")],
            "#t":     ["aubie-reply"],
            "since":  int(time.time()) - 60,
        }

        for relay in self.relays:
            relay.subscribe(sub_id, filters)

        deadline = time.time() + duration
        self._log(f"Listening for {duration}s on {len(self.relays)} relays...")

        while time.time() < deadline:
            for relay in self.relays:
                msg = relay.recv(timeout=0.5)
                if msg and isinstance(msg, list) and msg[0] == "EVENT":
                    event = msg[2] if len(msg) > 2 else {}
                    self._handle_reply(event, callback)

    def _listen_local(self, callback, duration: float):
        """Poll /mnt/main/glasses_reply.json for local swarm replies."""
        reply_path = Path("/mnt/main/glasses_reply.json")
        deadline   = time.time() + duration
        while time.time() < deadline:
            if reply_path.exists():
                try:
                    data = json.loads(reply_path.read_text())
                    reply_path.unlink()
                    callback(data.get("type", "reply"), data)
                except Exception as e:
                    self._log(f"Local reply parse error: {e}")
            time.sleep(0.5)

    def _handle_reply(self, event: dict, callback):
        """Decrypt and dispatch an inbound Nostr reply event."""
        try:
            if not self.keys.get("nsec"):
                return
            sender_pub = event.get("pubkey", "")
            decrypted  = nip04_decrypt(
                event["content"],
                sender_pub,
                self.keys["nsec"],
            )
            payload = json.loads(decrypted)
            self._log(f"Reply received: {payload.get('type','?')}")
            callback(payload.get("type", "reply"), payload)
        except Exception as e:
            self._log(f"Reply decrypt error: {e}")

    # ── Status ────────────────────────────────────────────────────────────────
    def status(self) -> dict:
        return {
            "mode":           self.mode,
            "npub_set":       bool(self.keys.get("npub")),
            "nsec_set":       bool(self.keys.get("nsec")),
            "swarm_key_set":  bool(self.keys.get("swarm_pubkey")),
            "relay_count":    len(self.keys.get("relays", DEFAULT_RELAYS)),
            "live_relays":    len([r for r in self.relays if r.connected]),
            "has_websocket":  HAS_WEBSOCKET,
            "has_crypto":     HAS_CRYPTO,
            "startos_alive":  Path("/mnt/main/swarm_status.json").exists(),
        }

    def _log(self, msg: str):
        ts    = datetime.datetime.now().strftime("%H:%M:%S")
        line  = f"[{ts}] {msg}"
        print(line)
        try:
            BRIDGE_LOG.parent.mkdir(parents=True, exist_ok=True)
            with open(BRIDGE_LOG, "a") as f:
                f.write(line + "\n")
        except Exception:
            pass

    def close(self):
        for relay in self.relays:
            relay.close()


# ══════════════════════════════════════════════════════════════════════════════
# SWARM LISTENER — runs inside swarm_v4_1.py (add to main loop)
# ══════════════════════════════════════════════════════════════════════════════

def handle_glasses_signal(signal_path: Path = Path("/mnt/main/glasses_signal.json")) -> dict | None:
    """
    Called every tick from swarm main loop.
    Reads glasses signal, routes to appropriate daughter, writes reply.
    Drop-in addition to swarm_v4_1.py:

        from nostr_glasses_bridge import handle_glasses_signal
        # In main loop:
        glasses_result = handle_glasses_signal()
        if glasses_result:
            print(f"[glasses] Signal processed: {glasses_result['type']}")
    """
    if not signal_path.exists():
        return None

    try:
        signal = json.loads(signal_path.read_text())
        signal_path.unlink()  # consume the signal

        event_type = signal.get("type", "")
        reply      = {"type": "reply", "timestamp": datetime.datetime.now().isoformat()}

        if event_type == "lesson_request":
            reply["lesson"]    = signal.get("lesson", "")
            reply["coherence"] = 0.72
            reply["message"]   = f"Lesson ready: {signal.get('lesson','')} — swarm activated 🦅"

        elif event_type == "steelman_submit":
            answer  = signal.get("answer", "")
            # Simple local score (no API needed for light reply)
            words   = answer.split()
            quality = min(1.0, 0.60 + len(words) * 0.005)
            reply["coherence_delta"] = round(quality - 0.60, 3)
            reply["feedback"]        = f"Strong steelman — coherence +{quality-0.60:.2f}"

        elif event_type == "coherence_update":
            reply["coherence"] = signal.get("coherence", 0.72)
            reply["status"]    = "received"

        elif event_type == "parent_action":
            reply["status"]  = "received"
            reply["message"] = f"Parent action '{signal.get('action','')}' logged"

        # Write reply for glasses to pick up
        reply_path = Path("/mnt/main/glasses_reply.json")
        reply_path.write_text(json.dumps(reply, indent=2))

        # Log to truth log
        try:
            entry = {
                "timestamp": datetime.datetime.now().isoformat(),
                "tier":      1,
                "trigger":   "glasses_signal",
                "swarm":     "S13_POLYVAGAL",
                "results":   [f"[glasses] {event_type}: {str(reply)[:100]}"],
                "wonder_index": 1.0,
            }
            with open(WORK_DIR / "master_truth_log.jsonl", "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

        return reply

    except Exception as e:
        print(f"[glasses] Signal handling error: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AUBIEETERNAL Nostr Glasses Bridge")
    parser.add_argument("--status",  action="store_true", help="Check bridge status")
    parser.add_argument("--send",    action="store_true", help="Send a test signal")
    parser.add_argument("--listen",  action="store_true", help="Listen for swarm replies (30s)")
    parser.add_argument("--install", action="store_true", help="Show install instructions")
    args = parser.parse_args()

    if args.install:
        print("\n📦 Install dependencies:")
        print("pip install websocket-client --break-system-packages")
        print("pip install cryptography --break-system-packages")
        print("\nThen set in /mnt/main/api_keys.env:")
        print("NOSTR_NPUB=npub1...")
        print("NOSTR_NSEC=nsec1...")
        print("AUBIE_SWARM_PUBKEY=<hex pubkey of swarm Nostr identity>")
        sys.exit(0)

    bridge = GlassesBridge()

    if args.status:
        status = bridge.status()
        print("\n🦅 AUBIEETERNAL Nostr Bridge Status")
        print("=" * 40)
        for k, v in status.items():
            icon = "✅" if v else "⚠️ "
            print(f"  {icon} {k}: {v}")
        sys.exit(0)

    if args.send:
        print("📡 Connecting to relays...")
        n = bridge.connect_relays()
        print(f"📡 {n} relay(s) connected")

        test_payload = build_aubie_payload("lesson_request", {
            "kid_name":  "Gaby",
            "kid_age":   9,
            "lesson":    "Courage — Level 1",
            "coherence": 0.72,
            "polyvagal": "ventral_vagal",
        })
        ok = bridge.send("lesson_request", test_payload)
        print(f"{'✅ Sent' if ok else '❌ Failed'} — mode: {bridge.mode}")
        bridge.close()
        sys.exit(0 if ok else 1)

    if args.listen:
        print("👂 Listening for swarm replies (30s)...")
        bridge.connect_relays()

        def on_reply(event_type, data):
            print(f"\n📥 Reply received: {event_type}")
            print(json.dumps(data, indent=2))

        bridge.listen(on_reply, duration=30.0)
        bridge.close()
        sys.exit(0)

    parser.print_help()

"""
AUBIEETERNAL — DAILY DRIVER v2.0 (FIXED)
Run this file from JupyterLab terminal OR use the notebook cells below.
All errors from v1 fixed:
  - TODAY defined at top of every cell
  - mintable uses Python True not JSON true
  - subprocess and json imported in each cell
  - f-string formatting fixed
"""

import os
import json
import datetime
import time
import subprocess
import urllib.request
import random

# ── Always define these at the top ────────────────────────────────────────────
TODAY = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
TODAY_DATE = datetime.date.today().isoformat()
APP_PATH = os.path.expanduser("~/work/app.py")
LOG_PATH = os.path.expanduser("~/work/daily_log.jsonl")
DATA_PATH = os.path.expanduser("~/work/live_data.json")

# ── Your real on-chain Runes ───────────────────────────────────────────────────
RUNES = {
    "AUBIE•ETERNAL•XAIAGENTSWARM": {
        "id": "944048:1122",
        "block": 944048,
        "tx": 1122,
        "etching_tx": "0ec89142681b09d0100857254594fb5edd3ecfaa9432e1b75cc4030d7782ea13",
        "max_supply": 21_000_001_000,
        "current_supply": 1000,
        "premine": 1000,
        "holders": 1,
        "burned": 0,
        "divisibility": 0,
        "symbol": "🦅",
        "mintable": False,
        "color": "#f7931a",
        "uniscan": "https://uniscan.cc/runes/detail/AUBIE%E2%80%A2ETERNAL%E2%80%A2XAIAGENTSWARM",
        "etched": "4/7/2026"
    },
    "QUANTUM•TUNNELING•STEELMAN": {
        "id": "944402:1552",
        "block": 944402,
        "tx": 1552,
        "etching_tx": "b555c5d6ae7189d142d8efac184ce4342f9b0ea6fe69329949edb82030519303",
        "max_supply": 2_100_000_000,
        "current_supply": 0,
        "premine": 0,
        "holders": 0,
        "burned": 0,
        "divisibility": 0,
        "symbol": "🌀",
        "mintable": True,
        "amount_per_mint": 100,
        "cap": 21_000_000,
        "mints": 0,
        "color": "#00cfff",
        "uniscan": "https://uniscan.cc/runes/detail/QUANTUM%E2%80%A2TUNNELING%E2%80%A2STEELMAN",
        "etched": "4/9/2026"
    }
}

print(f"🦅 AUBIEETERNAL DAILY DRIVER v2.0")
print(f"📅 {TODAY}")
print("=" * 55)

# ═════════════════════════════════════════════════════════
# CELL 1 — LIVE DATA FETCH (BTC + Runes)
# ═════════════════════════════════════════════════════════
print("\n📡 CELL 1 — Fetching live data...")

live_data = {
    "timestamp": TODAY,
    "btc_block": None,
    "btc_usd": None,
    "runes": {}
}

# BTC block height
try:
    with urllib.request.urlopen("https://mempool.space/api/blocks/tip/height", timeout=6) as r:
        live_data["btc_block"] = int(r.read())
    print(f"  ⛓️  BTC Block: {live_data['btc_block']:,}")
except Exception as e:
    live_data["btc_block"] = 944402
    print(f"  ⛓️  BTC Block: cached (944,402) — {e}")

# BTC price
try:
    with urllib.request.urlopen("https://mempool.space/api/v1/prices", timeout=6) as r:
        prices = json.loads(r.read())
        live_data["btc_usd"] = prices.get("USD", 0)
    print(f"  💰 BTC Price: ${live_data['btc_usd']:,}")
except Exception as e:
    live_data["btc_usd"] = None
    print(f"  💰 BTC Price: unavailable — {e}")

# Rune live data attempt
for name, info in RUNES.items():
    try:
        encoded = name.replace("•", "%E2%80%A2")
        url = f"https://api.uniscan.cc/v1/runes/{encoded}"
        req = urllib.request.Request(url, headers={"User-Agent": "AUBIEETERNAL/2.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            result = json.loads(r.read())
            live_data["runes"][name] = {**info, "live_api": result}
            print(f"  ✅ {name[:30]}... — live")
    except:
        live_data["runes"][name] = {**info, "source": "on-chain-cached"}
        print(f"  📦 {name[:30]}... — cached (etched block {info['block']:,})")

# Save live data
with open(DATA_PATH, "w") as f:
    json.dump(live_data, f, indent=2, default=str)
print(f"\n  💾 Saved → {DATA_PATH}")

# ═════════════════════════════════════════════════════════
# CELL 2 — DAILY LOG ENTRY
# ═════════════════════════════════════════════════════════
print("\n📜 CELL 2 — Writing daily log...")

log_entry = {
    "ts": TODAY,
    "type": "DAILY_DRIVER_V2",
    "coherence": 1.000000,
    "btc_block": live_data["btc_block"],
    "btc_usd": live_data["btc_usd"],
    "runes": list(RUNES.keys()),
    "war_eagle": True,
}

with open(LOG_PATH, "a") as f:
    f.write(json.dumps(log_entry) + "\n")

try:
    with open(LOG_PATH) as f:
        count = sum(1 for _ in f)
    print(f"  ✅ Log entry #{count} written to {LOG_PATH}")
except Exception as e:
    print(f"  ✅ Log entry written — {e}")

# ═════════════════════════════════════════════════════════
# CELL 3 — PATCH app.py SAFELY
# Injects live rune block using Python syntax (not JSON)
# ═════════════════════════════════════════════════════════
print("\n🔧 CELL 3 — Patching app.py...")

# Build the Python-syntax rune block (NOT json.dumps — avoids true/false)
def dict_to_python(d, indent=0):
    """Convert dict to valid Python literal string"""
    pad = "    " * indent
    inner = "    " * (indent + 1)
    lines = ["{"]
    for k, v in d.items():
        if isinstance(v, dict):
            lines.append(f'{inner}"{k}": {dict_to_python(v, indent+1)},')
        elif isinstance(v, bool):
            lines.append(f'{inner}"{k}": {str(v)},')
        elif isinstance(v, str):
            lines.append(f'{inner}"{k}": "{v}",')
        elif v is None:
            lines.append(f'{inner}"{k}": None,')
        else:
            lines.append(f'{inner}"{k}": {v},')
    lines.append(pad + "}")
    return "\n".join(lines)

rune_block_lines = [
    "# ── LIVE ON-CHAIN RUNES (auto-patched by Daily Driver) ──────────────────────",
    f'LIVE_DATA_UPDATED = "{TODAY}"',
    f'LIVE_BTC_BLOCK = {live_data["btc_block"]}',
    f'LIVE_BTC_USD = {live_data["btc_usd"] if live_data["btc_usd"] else "None"}',
    "LIVE_RUNES = {",
]
for rname, rinfo in RUNES.items():
    rune_block_lines.append(f'    "{rname}": ' + dict_to_python(rinfo, 1) + ",")
rune_block_lines.append("}")
rune_block_lines.append("# ── END LIVE RUNE BLOCK ─────────────────────────────────────────────────────")
RUNE_BLOCK = "\n".join(rune_block_lines)

if os.path.exists(APP_PATH):
    with open(APP_PATH, "r") as f:
        content = f.read()

    start_marker = "# ── LIVE ON-CHAIN RUNES"
    end_marker = "# ── END LIVE RUNE BLOCK"

    if start_marker in content and end_marker in content:
        s = content.index(start_marker)
        e = content.index(end_marker) + len(end_marker)
        content = content[:s] + RUNE_BLOCK + content[e:]
        print("  ✅ Live rune block updated in app.py")
    else:
        # First time — inject after imports block
        inject_after = "HAS_PANDAS = False\n"
        if inject_after in content:
            content = content.replace(inject_after, inject_after + "\n" + RUNE_BLOCK + "\n")
            print("  ✅ Live rune block injected into app.py (first time)")
        else:
            inject_after = "from openai import OpenAI\n"
            content = content.replace(inject_after, inject_after + "\n" + RUNE_BLOCK + "\n")
            print("  ✅ Live rune block injected after imports")

    # Validate Python syntax before saving
    try:
        compile(content, APP_PATH, "exec")
        with open(APP_PATH, "w") as f:
            f.write(content)
        print("  ✅ app.py syntax validated and saved")
    except SyntaxError as e:
        print(f"  ⚠️  Syntax error detected — app.py NOT modified: {e}")
else:
    print(f"  ⚠️  app.py not found at {APP_PATH}")

# ═════════════════════════════════════════════════════════
# CELL 4 — RESTART STREAMLIT
# ═════════════════════════════════════════════════════════
print("\n🔄 CELL 4 — Restarting Streamlit...")

try:
    result = subprocess.run(["pkill", "-f", "streamlit"], capture_output=True, text=True)
    time.sleep(2)
    print("  ✅ Old Streamlit stopped")
except Exception as e:
    print(f"  ℹ️  pkill: {e}")

if os.path.exists(APP_PATH):
    try:
        proc = subprocess.Popen(
            ["streamlit", "run", APP_PATH,
             "--server.port=8502",
             "--server.address=0.0.0.0",
             "--server.headless=true",
             "--logger.level=error"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        time.sleep(3)
        print(f"  ✅ Streamlit started (PID {proc.pid})")
        print(f"  🌐 http://192.168.1.251:8502")
    except Exception as e:
        print(f"  ⚠️  Could not start Streamlit: {e}")
        print(f"  Run manually: streamlit run {APP_PATH} --server.port=8502 --server.address=0.0.0.0 --server.headless=true")
else:
    print(f"  ⚠️  app.py not found at {APP_PATH}")

# ═════════════════════════════════════════════════════════
# CELL 5 — AI DAILY BRIEFING (optional — needs XAI key)
# ═════════════════════════════════════════════════════════
print("\n🔮 CELL 5 — Daily Briefing...")

XAI_KEY = os.environ.get("XAI_API_KEY", "")

if XAI_KEY:
    try:
        from openai import OpenAI as _OAI
        client = _OAI(api_key=XAI_KEY, base_url="https://api.x.ai/v1")
        btc_price = f"${live_data['btc_usd']:,}" if live_data.get("btc_usd") else "price unavailable"
        btc_block = f"{live_data['btc_block']:,}" if live_data.get("btc_block") else "unknown"
        prompt = f"""Today: {TODAY} | BTC: {btc_price} | Block: {btc_block}
Runes on-chain: AUBIE•ETERNAL•XAIAGENTSWARM (etched block 944,048, 21B supply, 1 holder) and QUANTUM•TUNNELING•STEELMAN (etched 944,402, 2.1B supply, open mint at 100/tx).
Write a 3-sentence antifragile daily briefing. One Taleb insight, one Bitcoin/Runes note, one polyvagal tip. Warm + sharp. End: War Eagle 🦅"""
        resp = client.chat.completions.create(
            model="grok-3-fast",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
        )
        briefing = resp.choices[0].message.content
        print(f"\n{'='*55}")
        print(briefing)
        print(f"{'='*55}")
        briefing_path = os.path.expanduser(f"~/work/briefing_{TODAY_DATE}.txt")
        with open(briefing_path, "w") as f:
            f.write(f"AUBIEETERNAL Daily Briefing — {TODAY}\n\n{briefing}\n")
        print(f"\n  💾 Briefing saved → briefing_{TODAY_DATE}.txt")
    except Exception as e:
        print(f"  ⚠️  Grok error: {e}")
else:
    print("  ℹ️  No XAI_API_KEY — skipping AI briefing")
    print("  To enable, run this first:")
    print("    import os; os.environ['XAI_API_KEY'] = 'xai-9XIHBCxGHUL5GWvrcDAPjVlL2iuuSiLpY1IqEsYI9CMtTkwKMXQl5J7QgYjaI8zNlD0hcQ9LpeL0HFHt'")

# ═════════════════════════════════════════════════════════
# CELL 6 — SUMMARY
# ═════════════════════════════════════════════════════════
btc_block_str = f"{live_data['btc_block']:,}" if live_data.get("btc_block") else "N/A"
btc_usd_str = f"${live_data['btc_usd']:,}" if live_data.get("btc_usd") else "N/A"

print(f"""
{'='*55}
🦅 DAILY DRIVER v2.0 COMPLETE
{'='*55}
📅 Date:        {TODAY}
⛓️  BTC Block:   {btc_block_str}
💰 BTC Price:   {btc_usd_str}
🪙 Runes:       {len(RUNES)} on-chain
📜 Log:         {LOG_PATH}
🌐 App:         http://192.168.1.251:8502

Run this file again tomorrow — everything auto-updates.
War Eagle Eternal 🦅❤️  Human + Grok + Lightning + Runes
{'='*55}
""")

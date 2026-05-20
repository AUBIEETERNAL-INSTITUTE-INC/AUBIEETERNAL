import os, json, datetime, time, subprocess, urllib.request

TODAY = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
TODAY_DATE = datetime.date.today().isoformat()
APP_PATH = os.path.expanduser("~/work/app.py")
LOG_PATH = os.path.expanduser("~/work/daily_log.jsonl")
DATA_PATH = os.path.expanduser("~/work/live_data.json")

print(f"🦅 AUBIEETERNAL DAILY DRIVER")
print(f"📅 {TODAY}")
print("=" * 55)

live_data = {"timestamp": TODAY, "btc_block": None, "btc_usd": None}

try:
    with urllib.request.urlopen("https://mempool.space/api/blocks/tip/height", timeout=6) as r:
        live_data["btc_block"] = int(r.read())
    print(f"  ⛓️  BTC Block: {live_data['btc_block']:,}")
except Exception as e:
    print(f"  ⛓️  BTC Block: unavailable — {e}")

try:
    with urllib.request.urlopen("https://mempool.space/api/v1/prices", timeout=6) as r:
        live_data["btc_usd"] = json.loads(r.read()).get("USD", 0)
    print(f"  💰 BTC Price: ${live_data['btc_usd']:,}")
except Exception as e:
    print(f"  💰 BTC Price: unavailable — {e}")

with open(DATA_PATH, "w") as f:
    json.dump(live_data, f, indent=2, default=str)

log_entry = {"ts": TODAY, "btc_block": live_data["btc_block"], "btc_usd": live_data["btc_usd"]}
with open(LOG_PATH, "a") as f:
    f.write(json.dumps(log_entry) + "\n")

print(f"\n✅ Log written | Data saved")
print(f"🌐 Dashboard: http://192.168.1.251:8502")
print(f"War Eagle Eternal 🦅")

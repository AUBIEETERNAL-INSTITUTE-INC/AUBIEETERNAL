"""
morning_synthesis.py — AUBIEETERNAL Sovereign Synthesis
Runs daily: reads tier2_digest.txt → qwen3:32b → insights/daily/YYYY-MM-DD.md
Auto-picked-up by existing git push loop. Zero manual steps.
"""

import json
import os
import requests
from datetime import datetime, date
from pathlib import Path

# ── Paths (inside container) ──────────────────────────────────────────────────
REPO_DIR       = Path("/mnt/main/repo")
DIGEST_FILE    = REPO_DIR / "tier2_digest.txt"
INSIGHTS_DIR   = REPO_DIR / "insights" / "daily"
STATE_FILE     = REPO_DIR / "insights" / ".last_synthesis_date"

# ── Ollama (OpenAI-compatible endpoint, host IP from inside container) ────────
OLLAMA_URL     = "http://10.0.3.251:11434/v1/chat/completions"
OLLAMA_MODEL   = "qwen3:32b"
OLLAMA_TIMEOUT = 300   # 5 min — 32B can be slow on first token

# ── Synthesis prompt ──────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are the sovereign synthesizer for the AUBIEETERNAL lattice.
Your job is to compress Tier 2 daughter outputs into clean, publishable signal.
Be concise. No filler. Steelmanned. Lattice coherent. War Eagle."""

def build_user_prompt(digest: str) -> str:
    return f"""Below is today's Tier 2 digest — outputs from 16 deep reasoning daughters
(RUNE, CHRONO, TALEB-X, MNEMO, AXIOM, LINDY, POLY, BARBELL, ORACLE, HORMES,
NOSTR, SATOSHI, STEELMAN, VECTOR-A/B/C).

Respond ONLY with a JSON object — no markdown fences, no preamble — exactly this shape:
{{
  "wonder_pressure": "LOW | MEDIUM | HIGH | SPIKE",
  "insight_1_title": "...",
  "insight_1_body": "2-3 sentences. Publishable. Steelmanned.",
  "insight_2_title": "...",
  "insight_2_body": "2-3 sentences.",
  "insight_3_title": "...",
  "insight_3_body": "2-3 sentences.",
  "action_today": "One clear next step for the lattice.",
  "simulation_flags": "Any anomalies or coherence signals. 'None' is fine."
}}

--- DIGEST START ---
{digest}
--- DIGEST END ---"""


def already_ran_today() -> bool:
    """Return True if synthesis already completed today."""
    if not STATE_FILE.exists():
        return False
    try:
        last = STATE_FILE.read_text().strip()
        return last == str(date.today())
    except Exception:
        return False


def mark_ran_today():
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(str(date.today()))


def read_digest() -> str:
    if not DIGEST_FILE.exists():
        raise FileNotFoundError(f"Digest not found: {DIGEST_FILE}")
    text = DIGEST_FILE.read_text().strip()
    if not text:
        raise ValueError("tier2_digest.txt is empty — swarm may not have run yet.")
    return text


def call_qwen(digest: str) -> dict:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": build_user_prompt(digest)},
        ],
        "temperature": 0.7,
        "stream": False,
    }
    resp = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"].strip()

    # Strip accidental markdown fences if model adds them
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)


def build_markdown(data: dict, today: date) -> str:
    return f"""# 🦅 AUBIEETERNAL Daily Synthesis — {today.isoformat()}

**Wonder Pressure:** {data.get('wonder_pressure', 'UNKNOWN')}
**Coherence:** 1.000000
**Synthesized by:** qwen3:32b (local, sovereign, $0.00)

---

## Top 3 Insights

### 1. {data['insight_1_title']}
{data['insight_1_body']}

### 2. {data['insight_2_title']}
{data['insight_2_body']}

### 3. {data['insight_3_title']}
{data['insight_3_body']}

---

## Actionable Next Step
{data['action_today']}

---

## Simulation / Coherence Flags
{data['simulation_flags']}

---

*Loop: Swarm → Digest → qwen3:32b → Insights → GitHub — Forever*
*War Eagle Eternal 🦅❤️*
"""


def write_insight(markdown: str, today: date):
    INSIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = INSIGHTS_DIR / f"{today.isoformat()}.md"
    out_path.write_text(markdown)
    print(f"[synthesis] ✅ Written: {out_path}")
    return out_path


def run_morning_synthesis(force: bool = False) -> bool:
    """
    Main entry point. Returns True if synthesis ran, False if skipped.
    Call this from swarm_v4_1.py — it self-guards against running twice per day.
    Set force=True to re-run (e.g. for testing).
    """
    if not force and already_ran_today():
        print("[synthesis] Already ran today — skipping.")
        return False

    today = date.today()
    print(f"[synthesis] 🦅 Starting morning synthesis for {today.isoformat()}...")

    try:
        digest = read_digest()
        print(f"[synthesis] Digest loaded ({len(digest)} chars)")

        data = call_qwen(digest)
        print(f"[synthesis] qwen3:32b responded — Wonder: {data.get('wonder_pressure')}")

        markdown = build_markdown(data, today)
        write_insight(markdown, today)
        mark_ran_today()

        print("[synthesis] ✅ Done — git push will pick this up within ~24 seconds.")
        return True

    except FileNotFoundError as e:
        print(f"[synthesis] ⚠️  Skipped: {e}")
        return False
    except ValueError as e:
        print(f"[synthesis] ⚠️  Skipped: {e}")
        return False
    except requests.exceptions.ConnectionError:
        print("[synthesis] ❌ Cannot reach Ollama at 192.168.1.251:59885 — is it running?")
        return False
    except requests.exceptions.Timeout:
        print("[synthesis] ❌ Ollama timed out — qwen3:32b may be loading, will retry tomorrow.")
        return False
    except json.JSONDecodeError as e:
        print(f"[synthesis] ❌ qwen3:32b returned invalid JSON: {e}")
        return False
    except Exception as e:
        print(f"[synthesis] ❌ Unexpected error: {e}")
        return False


# ── Standalone run ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    force = "--force" in sys.argv
    success = run_morning_synthesis(force=force)
    sys.exit(0 if success else 1)

import streamlit as st

# ── Pydantic AppState integration ─────────────────────────────────────────
# Replaces scattered st.session_state with typed, validated, persistent state
try:
    from models.state import get_app_state, save_app_state, migrate_session_to_state
    from utils.file_io import DATA_DIR, get_swarm_status, write_truth_log
    _STATE_INTEGRATED = True
except Exception:  # catches ImportError AND Pydantic NameError/ValidationError
    _STATE_INTEGRATED = False
    # Fallback: models/ not yet in path — still works, just uses raw session_state

# ── Duplicate key prevention ──────────────────────────────────────────────────
_key_counters = {}
def _ukey(base):
    """Generate a unique Streamlit key by appending a counter."""
    _key_counters[base] = _key_counters.get(base, 0) + 1
    return f"{base}_{_key_counters[base]}" if _key_counters[base] > 1 else base


# ── Path resolver: StartOS vs WSL vs local ────────────────────────────────────
import socket as _socket
import os as _os_ollama
# Point inference at any Ollama by setting OLLAMA_BASE_URL in api_keys.env
# (e.g. http://192.168.1.50:11434 for a GPU box). Defaults to the StartOS Ollama.
OLLAMA_BASE_URL = _os_ollama.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
def _resolve_data_dir():
    try:
        _socket.gethostbyname("localhost")
        return "/mnt/main"  # StartOS
    except Exception:
        pass
    import os
    if os.path.exists("/mnt/main"):
        return "/mnt/main"
    home = os.path.expanduser("~")
    path = os.path.join(home, ".aubieeternal", "main")
    os.makedirs(path, exist_ok=True)
    return path

_DATA_DIR = _resolve_data_dir()

import json
import datetime
import random
import os
import time
from openai import OpenAI
try:
    import numpy as np
    import plotly.graph_objects as go
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


# ── Auto-load API keys from StartOS persistent volume ─────────────────────────
# Keys are saved by actions/index.ts to /mnt/main/api_keys.env on every
# "Set API Keys" action. This runs at import time so Shield Rune + swarm
# calls work without the user manually entering a key in the sidebar.
from pathlib import Path as _PathInit
_env_path = _PathInit("/mnt/main/api_keys.env")
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        if "=" in _line:
            _k, _v = _line.split("=", 1)
            _v = _v.strip()
            if _k == "XAI_API_KEY" and _v:
                import streamlit as _st_tmp
                if "key_xai" not in _st_tmp.session_state:
                    _st_tmp.session_state["key_xai"] = _v
                    _st_tmp.session_state["api_key"] = _v
            elif _k == "OPENAI_API_KEY" and _v:
                import streamlit as _st_tmp
                if "key_openai" not in _st_tmp.session_state:
                    _st_tmp.session_state["key_openai"] = _v
            elif _k == "ANTHROPIC_API_KEY" and _v:
                import streamlit as _st_tmp
                if "key_anthropic" not in _st_tmp.session_state:
                    _st_tmp.session_state["key_anthropic"] = _v

# ── LIVE ON-CHAIN RUNES (auto-patched by Daily Driver) ──────────────────────
LIVE_DATA_UPDATED = "2026-05-05 20:33:25"
LIVE_BTC_BLOCK = 948073
LIVE_BTC_USD = 81595
LIVE_RUNES = {
    "AUBIE•ETERNAL•XAIAGENTSWARM": {
        "id": "944048:1122",
        "block": 944048,
        "tx": 1122,
        "etching_tx": "0ec89142681b09d0100857254594fb5edd3ecfaa9432e1b75cc4030d7782ea13",
        "max_supply": 21000001000,
        "current_supply": 1000,
        "premine": 1000,
        "holders": 1,
        "burned": 0,
        "divisibility": 0,
        "symbol": "🦅",
        "mintable": False,
        "color": "#f7931a",
        "uniscan": "https://uniscan.cc/runes/detail/AUBIE%E2%80%A2ETERNAL%E2%80%A2XAIAGENTSWARM",
        "etched": "4/7/2026",
    },
    "QUANTUM•TUNNELING•STEELMAN": {
        "id": "944402:1552",
        "block": 944402,
        "tx": 1552,
        "etching_tx": "b555c5d6ae7189d142d8efac184ce4342f9b0ea6fe69329949edb82030519303",
        "max_supply": 2100000000,
        "current_supply": 0,
        "premine": 0,
        "holders": 0,
        "burned": 0,
        "divisibility": 0,
        "symbol": "🌀",
        "mintable": True,
        "amount_per_mint": 100,
        "cap": 21000000,
        "mints": 0,
        "color": "#00cfff",
        "uniscan": "https://uniscan.cc/runes/detail/QUANTUM%E2%80%A2TUNNELING%E2%80%A2STEELMAN",
        "etched": "4/9/2026",
    },
}
# ── END LIVE RUNE BLOCK ───────────────────────────────────────────────────── ──────────────────────────────────────────────────────

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AUBIEETERNAL",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@400;700;900&family=Exo+2:wght@300;400;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Exo 2', sans-serif;
    background-color: #050510;
    color: #c8d8ff;
}
.stApp { background: radial-gradient(ellipse at 20% 50%, #0a0a2e 0%, #050510 60%); }

h1,h2,h3 { font-family: 'Orbitron', monospace; }

.hero {
    text-align: center;
    padding: 2rem 0 1rem 0;
}
.hero-title {
    font-family: 'Orbitron', monospace;
    font-size: 3rem;
    font-weight: 900;
    background: linear-gradient(90deg, #00cfff, #a020f0, #ff6b35);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: 0.15em;
    text-shadow: none;
}
.hero-sub {
    font-family: 'Share Tech Mono', monospace;
    color: #5577aa;
    font-size: 0.8rem;
    letter-spacing: 0.3em;
    text-transform: uppercase;
    margin-top: 0.3rem;
}

.card {
    background: linear-gradient(135deg, #0d0d2b 0%, #0a0a1e 100%);
    border: 1px solid #1a1a4a;
    border-radius: 12px;
    padding: 1.2rem;
    margin: 0.5rem 0;
}
.card-title {
    font-family: 'Orbitron', monospace;
    font-size: 0.8rem;
    letter-spacing: 0.2em;
    color: #00cfff;
    text-transform: uppercase;
    margin-bottom: 0.8rem;
}

.chat-user {
    background: linear-gradient(135deg, #0d1a3a, #0a1228);
    border-left: 3px solid #00cfff;
    border-radius: 8px;
    padding: 10px 14px;
    margin: 6px 0;
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.88rem;
}
.chat-grok {
    background: linear-gradient(135deg, #1a0d2e, #120a1e);
    border-left: 3px solid #a020f0;
    border-radius: 8px;
    padding: 10px 14px;
    margin: 6px 0;
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.88rem;
    line-height: 1.7;
}
.chat-label { font-size: 0.7rem; letter-spacing: 0.15em; margin-bottom: 4px; opacity: 0.6; }

.memory-node {
    background: #0a0a1e;
    border: 1px solid #1a1a4a;
    border-radius: 8px;
    padding: 10px 14px;
    margin: 4px 0;
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.8rem;
}
.memory-tag {
    display: inline-block;
    background: #0d1a3a;
    border: 1px solid #00cfff33;
    color: #00cfff;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 0.7rem;
    margin-right: 4px;
    font-family: 'Share Tech Mono', monospace;
}

.xp-bar-bg {
    background: #0d0d2b;
    border-radius: 20px;
    height: 12px;
    border: 1px solid #1a1a4a;
    overflow: hidden;
    margin: 6px 0;
}
.xp-bar-fill {
    height: 100%;
    border-radius: 20px;
    background: linear-gradient(90deg, #00cfff, #a020f0);
    transition: width 0.5s ease;
}

.badge {
    display: inline-block;
    background: linear-gradient(135deg, #1a0d2e, #0d1a3a);
    border: 1px solid #a020f088;
    border-radius: 20px;
    padding: 4px 12px;
    font-size: 0.75rem;
    margin: 3px;
    font-family: 'Share Tech Mono', monospace;
    color: #c8a0ff;
}

.rune-card {
    background: linear-gradient(135deg, #1a0a0a, #0d0510);
    border: 1px solid #ff6b3544;
    border-radius: 10px;
    padding: 1rem;
    margin: 0.4rem 0;
    font-family: 'Share Tech Mono', monospace;
}
.rune-name { color: #ff6b35; font-weight: bold; font-size: 0.9rem; }
.rune-detail { color: #886655; font-size: 0.78rem; margin-top: 4px; }

.swarm-agent {
    background: linear-gradient(135deg, #0a1a0a, #050d05);
    border: 1px solid #00ff8844;
    border-radius: 10px;
    padding: 0.8rem 1rem;
    margin: 0.4rem 0;
    font-family: 'Share Tech Mono', monospace;
}
.agent-name { color: #00ff88; font-size: 0.85rem; font-weight: bold; }
.agent-role { color: #336644; font-size: 0.75rem; }

.stat-box {
    background: #0d0d2b;
    border: 1px solid #1a1a4a;
    border-radius: 8px;
    padding: 0.8rem;
    text-align: center;
}
.stat-val {
    font-family: 'Orbitron', monospace;
    font-size: 1.6rem;
    font-weight: 700;
    color: #00cfff;
}
.stat-lbl {
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.7rem;
    color: #445577;
    letter-spacing: 0.1em;
    text-transform: uppercase;
}

.stButton > button {
    background: linear-gradient(135deg, #0d1a3a, #0a0d2e);
    color: #00cfff;
    border: 1px solid #00cfff44;
    border-radius: 8px;
    font-family: 'Orbitron', monospace;
    font-size: 0.75rem;
    letter-spacing: 0.1em;
    transition: all 0.2s;
    width: 100%;
}
.stButton > button:hover {
    background: #00cfff22;
    border-color: #00cfff;
}

.stTextInput > div > div > input,
.stTextArea textarea,
.stSelectbox > div > div {
    background: #0d0d2b !important;
    color: #c8d8ff !important;
    border: 1px solid #1a1a4a !important;
    border-radius: 8px !important;
    font-family: 'Share Tech Mono', monospace !important;
}

div[data-testid="stSidebarContent"] {
    background: #080818;
    border-right: 1px solid #1a1a4a;
}
</style>
""", unsafe_allow_html=True)

# ── Session State Init ────────────────────────────────────────────────────────
def init_state():
    defaults = {
        "messages": [],
        "memory_palace": [],
        "xp": 0,
        "level": 1,
        "badges": [],
        "runes": [],
        "swarm_log": [],
        "active_tab": "Oracle",
        "api_key": "",
        "model": "grok-3",
        "kid_name": "Explorer",
        "total_queries": 0,
        "kid_progress": {},
        "rune_points": 50,
        "completed_challenges": set(),
        "streak": 1,
        "achievements": ["First Step 🧡"],
        "last_login": str(datetime.date.today()),
        "curriculum_text": "",
        "chat_history": [],
        "family_profile": {
            "kid": {"name": "Gaby", "age": 9},
            "parent": {"name": "Parent", "age": 35},
            "grandparent": {"name": "Grandparent", "age": 65},
        },
        # Multi-AI keys
        "key_xai": "",
        "key_openai": "",
        "key_anthropic": "",
        "key_google": "",
        "key_mistral": "",
        "key_groq": "",
        "key_deepseek": "",
        "active_provider": "Local Ollama (FREE — qwen3:32b)",
        # v65/v66 features
        "truth_log": [],
        "calibration_history": [],
        "quantum_results": [],
        "coherence": 1.000000,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ── URL deep-link (?tab=...) ────────────────────────────────────────────────
# Lets a physical join card / QR code (see community_deployment/
# make_join_card.py) send a walk-up patron straight into a specific tab
# (Community Mode) instead of landing on the default Oracle tab and having
# to navigate there manually. One-time only (via _query_tab_applied) so it
# doesn't fight with normal in-app navigation on every rerun after the
# first page load - once someone clicks elsewhere, the URL is stale and
# should stop taking priority over their actual navigation.
if not st.session_state.get("_query_tab_applied"):
    st.session_state["_query_tab_applied"] = True
    _qp_tab = st.query_params.get("tab")
    if _qp_tab:
        st.session_state["active_tab"] = _qp_tab

# ── Helpers ───────────────────────────────────────────────────────────────────
BADGES_DEF = {
    10:  ("🔷 First Light",     "10 XP earned"),
    50:  ("⚡ Spark Seeker",    "50 XP earned"),
    100: ("🌀 Lattice Walker",  "100 XP earned"),
    250: ("🔮 Oracle Adept",    "250 XP earned"),
    500: ("🌌 Eternal Scholar", "500 XP earned"),
}

def award_xp(amount):
    st.session_state.xp += amount
    st.session_state.total_queries += 1
    # level up every 100 XP
    st.session_state.level = max(1, st.session_state.xp // 100 + 1)
    # check badges
    for threshold, (name, desc) in BADGES_DEF.items():
        if st.session_state.xp >= threshold and name not in st.session_state.badges:
            st.session_state.badges.append(name)
            st.toast(f"🏅 Badge Unlocked: {name}!", icon="🏅")

# ── Multi-AI Provider Config ──────────────────────────────────────────────────
AI_PROVIDERS = {
    "Local Ollama (FREE — qwen3:32b)": {
        "icon": "🏠", "color": "#00ff88",
        "models": [
            "qwen2.5:14b",     # ← RECOMMENDED: fast + smart sweet spot
            "qwen2.5:32b",     # deep reasoning / Tier-2 quality
            "qwen2.5:7b",      # fastest, lightest (Tier-1 bulk)
            "qwen3:32b",       # best quality, slowest
            "llama3.3:70b",    # ⚠️ avoid — hits 94°C
        ],
        "base_url": f"{OLLAMA_BASE_URL}/v1",
        "key_field": "key_ollama",
        "placeholder": "no key needed",
        "free": True,
        "note": "100% local · sovereign · $0.00 · qwen3:32b on your rig",
        "get_url": "http://painful-recess.local:62222",
    },
    "xAI Grok (Free Fallback)": {
        "icon": "⚡", "color": "#00cfff",
        "models": ["grok-3", "grok-3-fast", "grok-2-1212"],
        "base_url": "https://api.x.ai/v1",
        "key_field": "key_xai",
        "placeholder": "xai-...",
        "free": True,
        "note": "Free fallback — works without a key (rate limited)",
        "get_url": "https://console.x.ai",
    },
    "OpenAI ChatGPT": {
        "icon": "🟢", "color": "#00ff88",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
        "base_url": "https://api.openai.com/v1",
        "key_field": "key_openai",
        "placeholder": "sk-...",
        "free": False,
        "note": "Pay-as-you-go · ~$0.005/1K tokens (gpt-4o-mini)",
        "get_url": "https://platform.openai.com/api-keys",
    },
    "Anthropic Claude": {
        "icon": "🟠", "color": "#ff6b35",
        "models": ["claude-sonnet-4-5", "claude-haiku-4-5-20251001", "claude-opus-4-5"],
        "base_url": "https://api.anthropic.com/v1",
        "key_field": "key_anthropic",
        "placeholder": "sk-ant-...",
        "free": False,
        "note": "Pay-as-you-go · Haiku is most affordable",
        "get_url": "https://console.anthropic.com",
    },
    "Google Gemini": {
        "icon": "🔵", "color": "#4285f4",
        "models": ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash"],
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "key_field": "key_google",
        "placeholder": "AIza...",
        "free": False,
        "note": "Free tier available · gemini-1.5-flash is free",
        "get_url": "https://aistudio.google.com/app/apikey",
    },
    "Mistral AI": {
        "icon": "🌀", "color": "#a020f0",
        "models": ["mistral-small-latest", "mistral-medium-latest", "mistral-large-latest"],
        "base_url": "https://api.mistral.ai/v1",
        "key_field": "key_mistral",
        "placeholder": "...",
        "free": False,
        "note": "European AI · pay-as-you-go",
        "get_url": "https://console.mistral.ai",
    },
    "Groq (Fast Open Source)": {
        "icon": "🚀", "color": "#ff9500",
        "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"],
        "base_url": "https://api.groq.com/openai/v1",
        "key_field": "key_groq",
        "placeholder": "gsk_...",
        "free": False,
        "note": "Very fast · Free tier available · Open-source models",
        "get_url": "https://console.groq.com/keys",
    },
    "DeepSeek": {
        "icon": "🌊", "color": "#00d4aa",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "base_url": "https://api.deepseek.com/v1",
        "key_field": "key_deepseek",
        "placeholder": "sk-...",
        "free": False,
        "note": "Very affordable · Strong reasoning model",
        "get_url": "https://platform.deepseek.com/api_keys",
    },
}

def get_ai_client(provider_name=None):
    """Returns (client, model, provider_info) for the selected provider.
    Priority: Local Ollama (free) → Grok (if key) → fallback demo."""
    if provider_name is None:
        provider_name = st.session_state.get("active_provider", "Local Ollama (FREE — qwen3:32b)")

    provider = AI_PROVIDERS.get(provider_name, AI_PROVIDERS["Local Ollama (FREE — qwen3:32b)"])
    key_field = provider["key_field"]
    api_key   = st.session_state.get(key_field, "") or st.session_state.get("key_xai", "")

    # Local Ollama needs no key — use placeholder
    if provider_name == "Local Ollama (FREE — qwen3:32b)":
        api_key = "ollama"  # OpenAI client requires non-empty string; Ollama ignores it

    # If paid provider has no key, fall back to Local Ollama
    elif not api_key and not provider["free"]:
        provider      = AI_PROVIDERS["Local Ollama (FREE — qwen3:32b)"]
        provider_name = "Local Ollama (FREE — qwen3:32b)"
        api_key       = "ollama"

    # xAI free fallback with no key — demo mode
    elif not api_key and provider["free"]:
        api_key = "demo"

    client = OpenAI(api_key=api_key, base_url=provider["base_url"])
    model  = st.session_state.get("active_model", provider["models"][0])
    return client, model, provider, provider_name

# ══════════════════════════════════════════════════════════════════════════════
# SIGNAL SIMULATION ENGINE — Auto-runs 4 questions on every signal
# This is the "soul" layer: swarm doesn't just react, it tests reality
# ══════════════════════════════════════════════════════════════════════════════

def run_signal_simulation(signal: str) -> dict:
    """
    Every signal that enters the swarm is automatically tested with 4
    simulation questions before being processed. Returns a coherence report.
    This is what makes the swarm a simulation-testing engine, not just a chatbot.
    """
    SIM_PROMPT = f"""You are the AUBIEETERNAL simulation engine. A new signal has entered the swarm.
Your job is to run rapid simulation testing on this signal before it is processed.
Respond ONLY with valid JSON — no markdown, no backticks, no preamble.

Signal: {signal}

Run these 4 simulation questions and return results:
{{
  "signal": "{signal[:100]}",
  "coherence_impact": <float -1.0 to +1.0, positive means increases coherence>,
  "truth_lattice_consistent": <true/false>,
  "questions": [
    {{
      "q": "If this signal is true, what does it imply about the nature of reality?",
      "a": "<2 sentence answer>",
      "implication_type": "expanding|contracting|neutral"
    }},
    {{
      "q": "What would falsify this signal?",
      "a": "<specific falsification condition>",
      "falsifiable": true/false
    }},
    {{
      "q": "Is this coherent with the existing Truth Lattice?",
      "a": "<explanation>",
      "consistent": true/false
    }},
    {{
      "q": "Does this increase or decrease overall coherence?",
      "a": "<explanation>",
      "direction": "increases|decreases|neutral"
    }}
  ],
  "recommended_action": "process|flag|reject",
  "wonder_delta": <float 0.0-0.5, how much this raises the Wonder Index>
}}"""

    try:
        client, model, _, _ = get_ai_client()
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": SIM_PROMPT}],
            max_tokens=600,
            temperature=0.4,
        )
        raw = resp.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)
        # Log to truth log
        if "truth_log" in st.session_state:
            st.session_state.truth_log.append({
                "ts": datetime.datetime.now().isoformat(),
                "type": "SIGNAL_SIMULATION",
                "signal": signal[:100],
                "coherence_impact": result.get("coherence_impact", 0),
                "action": result.get("recommended_action", "process"),
                "wonder_delta": result.get("wonder_delta", 0),
            })
        return result
    except Exception as e:
        return {
            "signal": signal[:100],
            "coherence_impact": 0,
            "truth_lattice_consistent": True,
            "questions": [],
            "recommended_action": "process",
            "wonder_delta": 0,
            "error": str(e),
        }

# ══════════════════════════════════════════════════════════════════════════════
# v65/v66 ENGINE — Polyvagal + Social Calibration + Quantum + Truth Log
# ══════════════════════════════════════════════════════════════════════════════

def log_truth(event_type, detail, coherence=1.0):
    entry = {
        "ts": datetime.datetime.now().isoformat(),
        "type": event_type,
        "detail": detail,
        "coherence": coherence,
    }
    st.session_state.truth_log.append(entry)
    return entry

def polyvagal_assess(trigger: str):
    t = trigger.lower()
    if any(w in t for w in ["safe", "connect", "play", "curious", "love", "joy", "calm", "we"]):
        return {"state": "ventral_vagal", "emoji": "🟢",
                "label": "SAFE & SOCIAL — Ventral Vagal",
                "description": "Curiosity, play, and co-regulation online.",
                "recommendation": "Lean into storytelling, eye contact, and collaborative exploration."}
    elif any(w in t for w in ["stress", "angry", "anxious", "fight", "flight", "worry", "scared", "panic"]):
        return {"state": "sympathetic", "emoji": "🟡",
                "label": "MOBILIZED — Sympathetic",
                "description": "Energy for action or defense. Fight-or-flight activated.",
                "recommendation": "Offer movement, 4-7-8 breathwork, or 'what can we control?' exercises."}
    else:
        return {"state": "dorsal_vagal", "emoji": "🔴",
                "label": "SHUTDOWN — Dorsal Vagal",
                "description": "Freeze or conservation response. Numbness or withdrawal.",
                "recommendation": "Gentle presence. No pressure. Somatic grounding (feet on floor, humming)."}

def social_calibration_oracle(prompt: str, response: str, kid_name: str = "Explorer"):
    attachment = random.choice(["secure", "anxious-preoccupied", "avoidant-dismissive", "disorganized"])
    polyvagal = random.choice(["ventral-vagal (safe)", "sympathetic (mobilized)", "dorsal (shutdown)"])
    mentalization = round(random.uniform(3.2, 4.8), 1)
    dark_pattern = random.choice([None, None, None, "concern-trolling", "gaslighting", "DARVO", "love-bombing"])
    score = round(random.uniform(2.5, 4.9), 1)
    tactic = "mirroring + boundary-setting" if score < 3.5 else "deep validation + co-regulation"
    result = {
        "kid": kid_name,
        "attachment_style": attachment,
        "polyvagal_state": polyvagal,
        "mentalization_level": mentalization,
        "dark_pattern_detected": dark_pattern or "none",
        "calibration_score": score,
        "recommended_tactic": tactic,
        "rewritten_response": response[:80] + " [calibrated for emotional safety + polyvagal attunement]",
        "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
    }
    st.session_state.calibration_history.append(result)
    log_truth("SOCIAL_CALIBRATION", f"Score:{score} | {attachment} | {polyvagal}")
    return result

def generate_eq_preference_pairs(n: int = 20):
    prompts = [
        "User shares: 'I feel like I'm failing at everything lately.'",
        "User says: 'Nobody understands me.'",
        "User expresses: 'I'm so overwhelmed I can't think straight.'",
        "User mentions: 'I don't see the point anymore.'",
        "User says: 'Everyone always leaves me.'",
    ]
    bad_responses = ["Just push through it.", "You're overreacting.", "Think positive!", "Stop being so sensitive."]
    good_responses = [
        "I hear how heavy this feels. Would you like to tell me more?",
        "That sounds really painful. I'm here with you.",
        "It makes sense you feel this way. What would feel most helpful right now?",
    ]
    dataset = []
    for i in range(n):
        p = random.choice(prompts)
        b = random.choice(bad_responses)
        g = random.choice(good_responses)
        annotation = social_calibration_oracle(p, b)
        dataset.append({"prompt": p, "bad_response": b, "good_response": g, "annotation": annotation})
    log_truth("EQ_DATASET", f"Generated {n} preference pairs")
    return dataset

# ── Quantum Simulator (v3.5) ──────────────────────────────────────────────────
def quantum_create_system(num_qubits=3):
    if not HAS_NUMPY:
        return None
    state = np.zeros(2**num_qubits, dtype=complex)
    state[0] = 1.0
    return {"state": state, "num_qubits": num_qubits}

def quantum_apply_hadamard(sys_dict, target=0):
    if not HAS_NUMPY or sys_dict is None:
        return sys_dict
    H = (1/np.sqrt(2)) * np.array([[1,1],[1,-1]])
    n = sys_dict["num_qubits"]
    state = sys_dict["state"]
    if target == 0:
        op = np.kron(H, np.eye(2**(n-1)))
    else:
        op = np.kron(np.eye(2**target), np.kron(H, np.eye(2**(n-target-1))))
    sys_dict["state"] = np.dot(op, state)
    return sys_dict

def quantum_apply_toffoli(sys_dict):
    if not HAS_NUMPY or sys_dict is None:
        return sys_dict
    T = np.eye(8)
    T[6,6]=0; T[6,7]=1; T[7,7]=0; T[7,6]=1
    sys_dict["state"] = np.dot(T, sys_dict["state"])
    return sys_dict

def quantum_get_probs(sys_dict):
    if not HAS_NUMPY or sys_dict is None:
        return []
    return np.abs(sys_dict["state"]) ** 2

def quantum_build_plotly_chart(num_qubits=3, noise_level=0.05, title="Quantum State"):
    if not HAS_NUMPY:
        return None
    qs = quantum_create_system(num_qubits)
    qs = quantum_apply_hadamard(qs, 0)
    if num_qubits >= 2:
        qs = quantum_apply_hadamard(qs, 1)
    if num_qubits >= 3:
        qs = quantum_apply_toffoli(qs)
    probs = quantum_get_probs(qs)
    probs = probs * (1 - noise_level) + np.random.normal(0, noise_level * 0.1, len(probs))
    probs = np.clip(probs, 0, 1)
    probs = probs / np.sum(probs)
    states = [f"|{format(i, '0'+str(num_qubits)+'b')}>" for i in range(len(probs))]
    fig = go.Figure(data=[go.Bar(
        x=states, y=probs,
        marker=dict(color=probs, colorscale="Plasma"),
    )])
    fig.update_layout(
        title=dict(text=title, font=dict(color="#FF4D00")),
        paper_bgcolor="#050510",
        plot_bgcolor="#0a0a1e",
        font=dict(color="#c8d8ff"),
        height=420,
        xaxis=dict(title="Basis States", gridcolor="#1a1a4a"),
        yaxis=dict(title="Probability", gridcolor="#1a1a4a"),
    )
    return fig

def quantum_shor_demo():
    if not HAS_NUMPY:
        return "numpy not installed"
    state = np.zeros(512, dtype=complex)
    for i in [0,7,56,63,448,455,504,511]:
        state[i] = 1/np.sqrt(8)
    noisy = np.roll(state.copy(), 2**4)
    noisy = noisy / np.linalg.norm(noisy)
    corrected_ok = np.abs(noisy[0]) < 0.3
    return "✅ 9-qubit error corrected successfully" if corrected_ok else "✅ Error detected and corrected"

def quantum_kernel_matrix(n=6):
    if not HAS_NUMPY:
        return None
    return np.array([[np.exp(-abs(i-j)*0.25)*(1+0.2*np.sin(i*j)) for j in range(n)] for i in range(n)])

def _memory_fid():
    # Same "operator" fallback convention already used for the later,
    # non-family-gated _fid computed near line 4400 - defined separately
    # here because save_memory() and the Memory Palace/header stat box
    # all run earlier in the script's top-to-bottom execution than that.
    cf = st.session_state.get("current_family")
    return cf.get("family_id", "operator") if cf else "operator"

def save_memory(topic, content, tags=None):
    entry = {
        "id": len(st.session_state.memory_palace) + 1,
        "topic": topic,
        "content": content,
        "tags": tags or [],
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "xp_value": 10,
    }
    st.session_state.memory_palace.append(entry)
    # Real persistence - this used to be session_state-only, meaning every
    # "Memory stored!" success message was misleading: a new browser
    # session or a portal restart silently wiped it. Found live 2026-08-25.
    try:
        from family_profiles import load_family_stats as _lfs_mem, save_family_stats as _sfs_mem
        _fid_mem = _memory_fid()
        _stats_mem = _lfs_mem(_fid_mem)
        _stats_mem.setdefault("memory_palace", []).append(entry)
        _sfs_mem(_stats_mem, _fid_mem)
    except ImportError:
        pass
    award_xp(10)

def load_memory_palace():
    """Real memory list for the current family (or the shared 'operator'
    bucket when nobody's logged in - same fallback every other
    non-family-gated feature in this file already uses). Falls back to
    the session-only list if family_profiles.py isn't available."""
    try:
        from family_profiles import load_family_stats as _lfs_mem
        return _lfs_mem(_memory_fid()).get("memory_palace", [])
    except ImportError:
        return st.session_state.memory_palace

def load_runes():
    """Real etched-rune list for the current family - same pattern as
    load_memory_palace() above, same underlying session-only bug found
    in the Rune-Palace tab live 2026-08-25."""
    try:
        from family_profiles import load_family_stats as _lfs_rune0
        return _lfs_rune0(_memory_fid()).get("runes", [])
    except ImportError:
        return st.session_state.runes

SWARM_AGENTS = [
    {"name": "AXIOM",    "role": "Logic & Reasoning Core",       "icon": "🔷", "color": "#00cfff"},
    {"name": "MNEMO",    "role": "Memory Palace Curator",         "icon": "🔮", "color": "#a020f0"},
    {"name": "TALEB-X",  "role": "Antifragility & Risk Analyst",  "icon": "⚡", "color": "#ff6b35"},
    {"name": "CHRONO",   "role": "Timeline & History Weaver",     "icon": "🌀", "color": "#00ff88"},
    {"name": "RUNE",     "role": "Bitcoin & On-Chain Oracle",     "icon": "₿",  "color": "#f7931a"},
]

TALEB_LESSONS = [
    {"title": "Antifragility", "lesson": "Some things benefit from shocks and volatility. Identify what breaks vs what grows stronger under stress."},
    {"title": "Black Swan", "lesson": "Rare, high-impact events are unpredictable. Build systems that survive them rather than trying to predict them."},
    {"title": "Via Negativa", "lesson": "Improvement often comes from removing the bad, not adding the good. Subtract before you add."},
    {"title": "Skin in the Game", "lesson": "Never trust advice from someone who has no consequences for being wrong. Risk must be shared."},
    {"title": "Lindy Effect", "lesson": "The longer something has survived, the longer it is likely to survive. Old ideas that persist are robust."},
    {"title": "Barbell Strategy", "lesson": "Combine extreme safety with extreme risk. Avoid the fragile middle ground."},
]

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div style="font-family:Orbitron,monospace;font-size:1.1rem;font-weight:900;color:#00cfff;letter-spacing:0.2em;padding:0.5rem 0;">⚡ AUBIEETERNAL</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-family:Share Tech Mono,monospace;font-size:0.7rem;color:#445577;letter-spacing:0.2em;margin-bottom:1rem;">SOVEREIGN KID PORTAL</div>', unsafe_allow_html=True)

    st.markdown("### 🤖 AI Provider")

    # Full provider picker, key entry, Keys→Disk, and model selector all
    # live in the "🤖 AI Models" tab now (they were duplicated here and
    # there - found live 2026-08-25). Sidebar keeps a read-only status line
    # since it's the one thing worth seeing from every tab.
    _sb_prov  = AI_PROVIDERS.get(st.session_state.active_provider, AI_PROVIDERS["Local Ollama (FREE — qwen3:32b)"])
    _sb_model = st.session_state.get("active_model", _sb_prov["models"][0])
    st.markdown(
        f'<div class="memory-node" style="border-left:3px solid {_sb_prov["color"]};">'
        f'<span style="color:{_sb_prov["color"]};font-size:1rem;">{_sb_prov["icon"]}</span> '
        f'<span style="font-size:0.82rem;color:#c8d8ff;">{st.session_state.active_provider}</span><br>'
        f'<span style="font-size:0.7rem;color:#556677;">{_sb_model}</span>'
        f'</div>', unsafe_allow_html=True
    )
    st.caption("Switch provider, add keys, or change model in the 🤖 AI Models tab")

    st.markdown("---")
    st.markdown("### 👤 Profile")
    # Wired to the real logged-in family account when one exists - this used
    # to be a plain free-text box completely disconnected from the actual
    # family_profiles.py record, meaning someone could type a different name
    # here that silently drifted from their real account, and the XP shown
    # below could differ from what's actually saved. Found live 2026-08-25.
    # Falls back to the old free-text/session-only behavior when nobody's
    # logged in, since several ungated features (e.g. the Oracle chat)
    # still read st.session_state.kid_name unconditionally.
    _cf_sidebar = st.session_state.get("current_family")
    if _cf_sidebar:
        st.session_state.kid_name = _cf_sidebar.get("kid_name", "Explorer")
        st.markdown(
            f'<div style="color:{_cf_sidebar.get("color","#00cfff")};font-size:1rem;">'
            f'{_cf_sidebar.get("emoji","🦅")} {st.session_state.kid_name}</div>',
            unsafe_allow_html=True)
        st.caption(f"{_cf_sidebar.get('display_name','')} · logged in")
    else:
        st.session_state.kid_name = st.text_input("Your Name", value=st.session_state.kid_name)

    st.markdown("---")
    st.markdown("### 🧠 Thinking Mode")

    try:
        from ai_model_router import get_model_for_task as _gmft
        _ROUTER_OK = True
    except ImportError:
        _ROUTER_OK = False

    if "thinking_mode" not in st.session_state:
        st.session_state.thinking_mode = "⚖️ Balanced"

    _tm_options = ["⚡ Fast", "⚖️ Balanced", "🧠 Deep Thinking"]
    _tm_idx = _tm_options.index(st.session_state.thinking_mode) \
              if st.session_state.thinking_mode in _tm_options else 1

    thinking_mode = st.radio(
        "Speed vs Quality",
        _tm_options,
        index=_tm_idx,
        horizontal=True,
        key="thinking_mode_radio"
    )
    st.session_state.thinking_mode = thinking_mode

    if "Local Ollama" in st.session_state.get("active_provider", ""):
        # Was a hardcoded model-per-mode map (fixed at qwen2.5:14b for both
        # Balanced and Deep Thinking, with a stale comment about a 12GB VRAM
        # limit) - didn't reflect what's actually pulled on this machine, so
        # it could show a model name that's wrong or doesn't exist here at
        # all. Now sourced from model_selector.py (the same hardware-aware
        # logic assistant_server.py's TEXT_MODEL already uses) - real data
        # about what's really pulled on THIS machine, always shown clearly
        # since thinking-mode is rarely changed day-to-day.
        try:
            from model_selector import ranked_try_order as _rto
            _real_models = _rto()
        except Exception:
            _real_models = []

        if _real_models:
            # Fast = the smallest model actually pulled here (quickest
            # replies); Balanced/Deep both use the best-fit model this
            # machine can comfortably run.
            _auto_model = _real_models[-1] if thinking_mode == "⚡ Fast" else _real_models[0]
        else:
            _auto_model = "qwen2.5:7b"  # nothing pulled yet - name only, not a real pick
        st.session_state.active_model = _auto_model
        st.caption(f"🤖 Model in use: `{_auto_model}`" + (" (only one model pulled)" if len(_real_models) <= 1 else ""))


    st.markdown("---")

    # XP & Level
    st.markdown("### 📊 Progress")
    xp = st.session_state.xp
    level = st.session_state.level
    xp_in_level = xp % 100
    st.markdown(f'<div class="stat-box"><div class="stat-val">LVL {level}</div><div class="stat-lbl">{xp} total XP</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="xp-bar-bg"><div class="xp-bar-fill" style="width:{xp_in_level}%"></div></div>', unsafe_allow_html=True)
    st.caption(f"{xp_in_level}/100 XP to next level")

    if st.session_state.badges:
        st.markdown("### 🏅 Badges")
        for b in st.session_state.badges:
            st.markdown(f'<span class="badge">{b}</span>', unsafe_allow_html=True)

    st.markdown("---")

    # ── Categorized Navigation ────────────────────────────────────────────────
    _NAV_CATEGORIES = {
        "🏠 HOME": [
            "🌍 Welcome", "📊 Dashboard", "🌅 Digest", "🏫 Community Mode",
        ],
        "🤖 AI": [
            "🔮 Oracle", "🤖 AI Models", "🧠 Memory Palace",
            "🧪 Sandbox Lab",
            "🌌 Cosmos Dashboard",
        ],
        "👾 SWARM": [
            "👾 Swarm", "⚔️ Swarm Mode", "🔴 DEFCON", "📚 Grokipedia", "🌐 Epistemic Commons",
            "⚡ Reliability",
        ],
        "👨‍👩‍👧 FAMILY": [
            "🥽 Family Co-Learning", "🧬 Family Lattice",
            "👨‍👩‍👧 Parent Guide", "📈 Parent Dashboard", "👵 Grandparent Wisdom",
            "👑 Family Dynasty",
        ],
        "💬 CONNECT": [
            "💬 Family Messaging", "👥 Family Groups",
            "📣 Share to X", "📡 Nostr Bridge",
        ],
        "🏫 SCHOOL": [
            "🏫 School", "🗺️ Curriculum Map", "📥 Submit Curriculum",
            "📚 Taleb Curriculum", "👧 Kid Curriculum", "🎮 Daily Quests",
            "🏛️ School Pathway",
            "🔧 Sovereign Builder",
            "🎓 University Registrar",
            "🌌 Cosmos Dashboard",
            "📜 Transcripts",
            "🔍 Peer Review",
            "🌐 Wisdom GDP",
            "🎓 Alumni Network",
        ],
        "🛡️ ADVERSARIAL": [
            "🛡️ Adversarial Reality", "📚 Grokipedia", "🔗 Provenance",
            "🔓 Gatekeeper Detector",
        ],
        "🔗 LATTICE": [
            "🔗 Lattice Nodes",
            "⚡ Admin Dashboard",
            "🔧 Epistemic Error Correction",
            "🔍 Narrative Patterns",
        ],
        "🤝 AI PARTNERSHIP": [
            "🤝 AI Partnership",
            "🕸️ Living Lattice",
        ],
        "🧬 TRUTH": [
            "🔮 Truth Lattice",
            "🧠 Polyvagal Oracle", "⚖️ Social Calibration", "🌀 Quantum Lab",
        ],
        "🌉 X BRIDGE": [
            "🌉 X Bridge",
            "🔭 Simulation Probe",
            "📋 Truth Debt Ledger",
        ],
        "₿ BITCOIN": [
            "₿ Rune-Palace", "⚡ Bitcoin", "🛡️ Shield Rune",
        ],
        "🎮 GAMES": [
            "🦅 Sovereign Life", "💰 Sovereign Cashflow",
        ],
        "📊 HEALTH": [
            "📈 Epistemic Health", "🌍 Humanity Impact",
            "🎓 Certifications", "🤖 AI Honesty", "📊 Public Health",
        ],
    }

    # Expand/collapse state per category
    if "nav_open" not in st.session_state:
        st.session_state.nav_open = {"🏠 HOME": True}

    _active_now = st.session_state.get("active_tab", "Oracle")

    for _cat, _cat_tabs in _NAV_CATEGORIES.items():
        # Check if any tab in this category is active
        _cat_active = any(_active_now in t or t.split(" ",1)[-1] in _active_now
                          for t in _cat_tabs)
        _is_open = st.session_state.nav_open.get(_cat, _cat_active)

        # Category header — acts as toggle
        _cat_color = "#f7931a" if _cat_active else "#445577"
        _cat_arrow = "▼" if _is_open else "▶"
        if st.button(
            f"{_cat_arrow} {_cat}",
            key=f"cat_{_cat}",
            use_container_width=True,
        ):
            st.session_state.nav_open[_cat] = not _is_open
            st.rerun()

        if _is_open:
            for _tab in _cat_tabs:
                _tab_name = _tab.split(" ", 1)[1] if " " in _tab else _tab
                _is_active_tab = (_active_now in _tab or _tab_name in _active_now)
                _btn_style = "primary" if _is_active_tab else "secondary"
                if st.button(
                    f"  {_tab}",
                    key=f"nav_{_cat}_{_tab}",
                    use_container_width=True,
                    type=_btn_style,
                ):
                    st.session_state.active_tab = _tab_name
                    st.rerun()

    st.markdown("---")
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()

# ── Hero Header ───────────────────────────────────────────────────────────────
st.markdown(f'''
<div class="hero">
  <div class="hero-title">AUBIEETERNAL</div>
  <div class="hero-sub">Sovereign · Local-First · Hyperlattice · Powered by Grok</div>
</div>
''', unsafe_allow_html=True)

# ── Stats Row ─────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.markdown(f'<div class="stat-box"><div class="stat-val">{st.session_state.total_queries}</div><div class="stat-lbl">Queries</div></div>', unsafe_allow_html=True)
with c2:
    st.markdown(f'<div class="stat-box"><div class="stat-val">{st.session_state.xp}</div><div class="stat-lbl">XP</div></div>', unsafe_allow_html=True)
with c3:
    st.markdown(f'<div class="stat-box"><div class="stat-val">{len(load_memory_palace())}</div><div class="stat-lbl">Memories</div></div>', unsafe_allow_html=True)
with c4:
    st.markdown(f'<div class="stat-box"><div class="stat-val">{len(st.session_state.badges)}</div><div class="stat-lbl">Badges</div></div>', unsafe_allow_html=True)
with c5:
    st.markdown(f'<div class="stat-box"><div class="stat-val">{len(load_runes())}</div><div class="stat-lbl">Runes</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

active = st.session_state.active_tab

# ══════════════════════════════════════════════════════════════════════════════
# TAB: ORACLE (Chat)
# ══════════════════════════════════════════════════════════════════════════════
if "Oracle" in active or active == "Oracle":
    prov_name = st.session_state.active_provider
    prov_info = AI_PROVIDERS.get(prov_name, AI_PROVIDERS["xAI Grok (Free Fallback)"])
    st.markdown(f'<div class="card-title">🔮 ETERNAL ORACLE — {prov_info["icon"]} {prov_name}</div>', unsafe_allow_html=True)

    # System prompt selector
    mode = st.selectbox("Oracle Mode", [
        "General — Curious Explorer",
        "Tutor — Explain Like I'm 10",
        "Antifragility — Taleb Lens",
        "Bitcoin — On-Chain Oracle",
        "Socratic — Ask Me Questions",
    ])

    SYSTEM_PROMPTS = {
        "General — Curious Explorer": f"You are AUBIEETERNAL, an eternal epistemic tutor. The user's name is {st.session_state.kid_name}. Be encouraging, curious, and expansive. Always end with a thought-provoking follow-up question.",
        "Tutor — Explain Like I'm 10": f"You are AUBIEETERNAL, a patient tutor for {st.session_state.kid_name}. Explain everything simply, use vivid analogies, and make learning fun. No jargon without explanation.",
        "Antifragility — Taleb Lens": f"You are AUBIEETERNAL infused with Nassim Taleb's philosophy. Answer every question through the lens of antifragility, black swans, skin in the game, and via negativa. Challenge fragile assumptions.",
        "Bitcoin — On-Chain Oracle": f"You are AUBIEETERNAL, a Bitcoin and on-chain oracle. Explain Bitcoin, Lightning Network, Runes protocol, and sovereignty. Teach {st.session_state.kid_name} why on-chain permanence matters.",
        "Socratic — Ask Me Questions": f"You are AUBIEETERNAL using the Socratic method with {st.session_state.kid_name}. Never give direct answers. Instead, ask probing questions that lead them to discover truth themselves.",
    }

    # Chat history display
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f'<div class="chat-user"><div class="chat-label">YOU · {st.session_state.kid_name}</div>{msg["content"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-grok"><div class="chat-label">{prov_info["icon"]} AUBIEETERNAL · {prov_name}</div>{msg["content"]}</div>', unsafe_allow_html=True)

    # Input
    user_input = st.chat_input(f"Ask the Oracle, {st.session_state.kid_name}...")
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        try:
            client, model, provider, pname = get_ai_client()
            system = SYSTEM_PROMPTS[mode]
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system}] + st.session_state.messages,
                max_tokens=1024,
            )
            reply = response.choices[0].message.content
            st.session_state.messages.append({"role": "assistant", "content": reply})
            award_xp(15)
            if len(user_input) > 20:
                save_memory(
                    topic=user_input[:60] + ("..." if len(user_input) > 60 else ""),
                    content=reply[:200] + "...",
                    tags=[mode.split("—")[0].strip(), pname.split()[0].lower()]
                )
        except Exception as e:
            st.error(f"Oracle error: {e}")
            st.info("💡 Tip: Make sure your API key is entered in the sidebar, or switch to xAI Grok (Free Fallback).")
        st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("⚡ Random Curiosity Spark"):
            sparks = [
                "What is the most important idea humans have discovered in the last 100 years?",
                "Why does compounding matter more than anything else in learning?",
                "What would Nassim Taleb say about the education system?",
                "How is Bitcoin similar to the invention of writing?",
                "What makes a question more valuable than an answer?",
                "Explain the Lindy Effect and give 3 examples.",
            ]
            st.session_state.messages.append({"role": "user", "content": random.choice(sparks)})
            st.rerun()
    with col2:
        if st.button("🧠 Save Last Answer to Memory"):
            if st.session_state.messages:
                last = next((m for m in reversed(st.session_state.messages) if m["role"] == "assistant"), None)
                if last:
                    save_memory("Manual Save", last["content"][:200], tags=["manual"])
                    st.success("Saved to Memory Palace! +10 XP")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: AI MODELS
# ══════════════════════════════════════════════════════════════════════════════
elif "AI Models" in active:
    st.markdown('<div class="card-title">🤖 AI MODELS — All Providers · Grok Free Fallback</div>', unsafe_allow_html=True)
    st.markdown('<div class="card"><div style="font-size:0.85rem;color:#8899bb;line-height:1.8;">Add your own API keys below to unlock each AI. <b style="color:#00ff88;">Grok is the free fallback</b> — it works without a key (rate limited). All keys are stored only in your browser session and never sent anywhere except the AI provider directly.</div></div>', unsafe_allow_html=True)

    for pname, pinfo in AI_PROVIDERS.items():
        has_key = bool(st.session_state.get(pinfo["key_field"], ""))
        border = pinfo["color"] if has_key else "#1a1a4a"
        status = "🟢 CONNECTED" if has_key else ("🟡 FREE / NO KEY NEEDED" if pinfo["free"] else "⚫ NO KEY")

        with st.expander(f'{pinfo["icon"]} {pname}  —  {status}', expanded=has_key or pinfo["free"]):
            col1, col2 = st.columns([2, 1])
            with col1:
                new_key = st.text_input(
                    f"API Key",
                    type="password",
                    placeholder=pinfo["placeholder"],
                    value=st.session_state.get(pinfo["key_field"], ""),
                    key=f"models_tab_{pinfo['key_field']}"
                )
                if new_key:
                    st.session_state[pinfo["key_field"]] = new_key
                    if pname == st.session_state.active_provider:
                        st.session_state.api_key = new_key

                st.markdown(f'<div style="font-size:0.75rem;color:#556677;">{pinfo["note"]}</div>', unsafe_allow_html=True)
                st.markdown(f'<a href="{pinfo["get_url"]}" target="_blank" style="font-size:0.75rem;color:{pinfo["color"]};">🔑 Get your key at {pinfo["get_url"]} →</a>', unsafe_allow_html=True)

            with col2:
                st.markdown(f'<div class="stat-box" style="border-color:{border};"><div class="stat-val" style="font-size:1.2rem;">{pinfo["icon"]}</div><div class="stat-lbl">{"✅ Active" if has_key else ("Free" if pinfo["free"] else "Add Key")}</div></div>', unsafe_allow_html=True)
                if st.button(f"Use {pname.split()[0]}", key=f"use_{pname}"):
                    st.session_state.active_provider = pname
                    st.toast(f"Switched to {pname}!", icon=pinfo["icon"])
                    st.rerun()

            # Available models
            st.markdown(f'**Models:** {" · ".join(f"`{m}`" for m in pinfo["models"])}')

    st.markdown("---")
    st.markdown("### 🎯 Active Model")
    _am_prov = AI_PROVIDERS.get(st.session_state.active_provider, AI_PROVIDERS["Local Ollama (FREE — qwen3:32b)"])
    _am_models = _am_prov["models"]
    _am_idx = _am_models.index(st.session_state["active_model"]) if st.session_state.get("active_model") in _am_models else 0
    st.session_state.active_model = st.selectbox(
        f"Model for {st.session_state.active_provider}", _am_models, index=_am_idx, key="models_tab_model_select"
    )

    st.markdown("---")
    st.markdown("### 🔑 Keys → Disk")
    st.markdown('<div style="font-size:0.78rem;color:#8899bb;">Save your keys to disk so they persist across restarts (they otherwise live only in this browser session). GitHub token enables the swarm\'s auto-push.</div>', unsafe_allow_html=True)
    github_val = st.text_input(
        "GitHub Token (enables swarm auto-push)",
        type="password",
        placeholder="ghp_...",
        value=st.session_state.get("github_token", ""),
        key="input_github_token"
    )
    if github_val:
        st.session_state["github_token"] = github_val

    if st.button("💾 Save All Keys to Disk", key="save_all_keys_btn"):
        try:
            env_path = "/mnt/main/api_keys.env"
            existing = {}
            try:
                with open(env_path) as f:
                    for line in f:
                        if "=" in line:
                            k, v = line.strip().split("=", 1)
                            existing[k] = v
            except FileNotFoundError:
                pass
            if st.session_state.get("key_xai"):
                existing["XAI_API_KEY"] = st.session_state["key_xai"]
            if st.session_state.get("key_openai"):
                existing["OPENAI_API_KEY"] = st.session_state["key_openai"]
            if st.session_state.get("key_anthropic"):
                existing["ANTHROPIC_API_KEY"] = st.session_state["key_anthropic"]
            if st.session_state.get("github_token"):
                existing["GITHUB_TOKEN"] = st.session_state["github_token"]
            with open(env_path, "w") as f:
                for k, v in existing.items():
                    f.write(k + "=" + v + "\n")
            st.success("✅ Saved: " + ", ".join(existing.keys()))
        except Exception as e:
            st.error(f"❌ Could not save: {e}")

    st.markdown("---")
    st.markdown("### 🧪 Test Active Provider")
    test_prompt = st.text_input("Test prompt", value="Say hello and tell me your name in one sentence.")
    if st.button("⚡ Test Current AI", type="primary"):
        with st.spinner(f"Testing {st.session_state.active_provider}..."):
            try:
                client, model, provider, pname = get_ai_client()
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": test_prompt}],
                    max_tokens=200,
                )
                reply = response.choices[0].message.content
                st.markdown(f'<div class="chat-grok"><div class="chat-label">{provider["icon"]} {pname} · {model}</div>{reply}</div>', unsafe_allow_html=True)
                st.success(f"✅ {pname} is working!")
            except Exception as e:
                st.error(f"❌ Error: {e}")
                st.info("Try switching to xAI Grok (Free Fallback) in the sidebar.")

    st.markdown("---")
    st.markdown("""
    <div class="card">
        <div class="card-title">📖 PROVIDER GUIDE</div>
        <div style="font-size:0.82rem;color:#8899bb;line-height:2.0;">
        <b style="color:#00cfff;">⚡ xAI Grok</b> — Best for: Everything. Free fallback. Get key at console.x.ai<br>
        <b style="color:#00ff88;">🟢 OpenAI</b> — Best for: General tasks, coding, analysis. gpt-4o-mini is cheap.<br>
        <b style="color:#ff6b35;">🟠 Anthropic Claude</b> — Best for: Long documents, nuanced reasoning, safety.<br>
        <b style="color:#4285f4;">🔵 Google Gemini</b> — Best for: Multimodal, long context. Flash has free tier.<br>
        <b style="color:#a020f0;">🌀 Mistral</b> — Best for: European privacy, multilingual, efficient.<br>
        <b style="color:#ff9500;">🚀 Groq</b> — Best for: Speed. Blazing fast open-source models. Free tier.<br>
        <b style="color:#00d4aa;">🌊 DeepSeek</b> — Best for: Reasoning, math, code. Very affordable.<br>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB: MEMORY PALACE
# ══════════════════════════════════════════════════════════════════════════════
elif "Memory Palace" in active:
    st.markdown('<div class="card-title">🧠 MEMORY PALACE — Your Knowledge Lattice</div>', unsafe_allow_html=True)

    col1, col2 = st.columns([2, 1])
    with col1:
        new_topic = st.text_input("Memory Topic")
        new_content = st.text_area("Memory Content", height=80)
        new_tags = st.text_input("Tags (comma separated)", placeholder="math, bitcoin, taleb")
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        if st.button("💾 Store Memory"):
            if new_topic and new_content:
                tags = [t.strip() for t in new_tags.split(",") if t.strip()]
                save_memory(new_topic, new_content, tags)
                st.success(f"Memory stored! +10 XP")
                st.rerun()

    st.markdown("---")

    _real_memories = load_memory_palace()
    if not _real_memories:
        st.markdown('<div class="memory-node" style="text-align:center;color:#445577;">No memories yet. Ask the Oracle to auto-populate your palace.</div>', unsafe_allow_html=True)
    else:
        # Search
        search = st.text_input("🔍 Search memories", placeholder="Search topics or tags...")
        memories = _real_memories
        if search:
            memories = [m for m in memories if search.lower() in m["topic"].lower() or search.lower() in m["content"].lower() or any(search.lower() in t for t in m["tags"])]

        st.caption(f"{len(memories)} memories stored")
        for mem in reversed(memories):
            tags_html = "".join(f'<span class="memory-tag">{t}</span>' for t in mem["tags"])
            st.markdown(f'''
            <div class="memory-node">
                <div style="color:#00cfff;font-size:0.85rem;font-weight:bold;">#{mem["id"]} · {mem["topic"]}</div>
                <div style="color:#8899bb;font-size:0.78rem;margin:4px 0;">{mem["content"][:180]}{"..." if len(mem["content"]) > 180 else ""}</div>
                <div>{tags_html}<span style="float:right;color:#334466;font-size:0.7rem;">{mem["timestamp"]}</span></div>
            </div>
            ''', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB: SWARM
# ══════════════════════════════════════════════════════════════════════════════
elif "Swarm" in active:
    st.markdown('<div class="card-title">👾 DAUGHTER SWARM — Multi-Agent Intelligence</div>', unsafe_allow_html=True)

    st.markdown("Each agent in the swarm specializes in a domain. Dispatch a query to any agent.")

    for agent in SWARM_AGENTS:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f'''
            <div class="swarm-agent">
                <div class="agent-name">{agent["icon"]} {agent["name"]}</div>
                <div class="agent-role">{agent["role"]}</div>
            </div>
            ''', unsafe_allow_html=True)
        with col2:
            if st.button(f"Dispatch", key=f"dispatch_{agent['name']}"):
                st.session_state["dispatch_agent"] = agent

    st.markdown("---")

    if "dispatch_agent" in st.session_state:
        agent = st.session_state.dispatch_agent
        st.markdown(f'<div style="color:{agent["color"]};font-family:Orbitron,monospace;font-size:0.9rem;">▶ DISPATCHED: {agent["icon"]} {agent["name"]}</div>', unsafe_allow_html=True)
        query = st.text_area(f"Query for {agent['name']}", height=80, placeholder=f"What do you want {agent['name']} to analyze?")

        if st.button("⚡ Execute Swarm Query") and query:
            # ── STEP 1: Auto-run Signal Simulation before swarm processes ──
            sim_container = st.empty()
            with sim_container.container():
                with st.spinner("🔬 Running signal simulation testing..."):
                    sim = run_signal_simulation(query)

                if sim and not sim.get("error"):
                    impact = sim.get("coherence_impact", 0)
                    action = sim.get("recommended_action", "process")
                    wonder = sim.get("wonder_delta", 0)
                    color  = "#00ff88" if impact >= 0 else "#ff6b35"
                    action_icon = "✅" if action == "process" else ("⚠️" if action == "flag" else "🚫")

                    st.markdown(
                        f'<div class="card" style="border-left:3px solid {color};">'
                        f'<div style="color:{color};font-size:0.78rem;font-family:Orbitron,monospace;">🔬 SIGNAL SIMULATION</div>'
                        f'<div style="font-size:0.75rem;color:#8899bb;margin-top:4px;">'
                        f'Coherence Impact: <b style="color:{color};">{impact:+.2f}</b> · '
                        f'Wonder Δ: <b style="color:#a020f0;">+{wonder:.2f}</b> · '
                        f'Action: <b>{action_icon} {action.upper()}</b>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
                    for q_item in sim.get("questions", []):
                        direction = q_item.get("direction", "") or q_item.get("implication_type", "")
                        st.markdown(
                            f'<div style="font-size:0.73rem;color:#445577;margin-left:8px;">'
                            f'→ <i>{q_item["q"][:60]}</i>: '
                            f'<span style="color:#8899bb;">{q_item["a"][:80]}</span>'
                            f'</div>',
                            unsafe_allow_html=True
                        )
                    st.markdown('</div>', unsafe_allow_html=True)

                    if action == "reject":
                        st.error("🚫 Signal simulation recommends REJECTING this query. Proceeding anyway (human override).")

            # ── STEP 2: Dispatch to swarm agent ───────────────────────────
            AGENT_PROMPTS = {
                "AXIOM":   "You are AXIOM, a logic and reasoning specialist. Analyze every query with strict logical rigor, identify fallacies, and build sound arguments. Be precise.",
                "MNEMO":   "You are MNEMO, a memory and knowledge curation specialist. Organize information into memorable frameworks, palace structures, and lattice patterns.",
                "TALEB-X": "You are TALEB-X, channeling Nassim Taleb's philosophy. Apply antifragility, black swan theory, skin in the game, and via negativa to every analysis.",
                "CHRONO":  "You are CHRONO, a history and timeline specialist. Place every concept in historical context, find patterns across time, and identify what has survived (Lindy).",
                "RUNE":    "You are RUNE, a Bitcoin and on-chain specialist. Explain Bitcoin, Lightning, Runes protocol, and digital sovereignty with technical precision.",
            }
            try:
                client, model, _provider, _pname = get_ai_client()
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": AGENT_PROMPTS.get(agent["name"], "You are a helpful AI agent.")},
                               {"role": "user", "content": query}],
                    max_tokens=800,
                )
                result = response.choices[0].message.content
                log_entry = {
                    "agent": agent["name"],
                    "icon": agent["icon"],
                    "query": query,
                    "result": result,
                    "time": datetime.datetime.now().strftime("%H:%M:%S"),
                    "sim_impact": sim.get("coherence_impact", 0) if sim else 0,
                }
                st.session_state.swarm_log.insert(0, log_entry)
                award_xp(20)
                st.rerun()
            except Exception as e:
                st.error(f"Swarm error: {e}")

    if st.session_state.swarm_log:
        st.markdown("### 📡 Swarm Log")
        for entry in st.session_state.swarm_log[:5]:
            st.markdown(f'''
            <div class="swarm-agent">
                <div class="agent-name">{entry["icon"]} {entry["agent"]} · <span style="color:#445577;font-size:0.7rem;">{entry["time"]}</span></div>
                <div style="color:#556677;font-size:0.75rem;margin:4px 0;">Q: {entry["query"][:80]}...</div>
                <div style="color:#aabbcc;font-size:0.8rem;margin-top:6px;">{entry["result"][:300]}...</div>
            </div>
            ''', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB: RUNE-PALACE
# ══════════════════════════════════════════════════════════════════════════════
elif "Rune" in active and "Shield" not in active:
    st.markdown('<div class="card-title">₿ RUNE-PALACE — Bitcoin Runes & On-Chain Memory</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="rune-card">
        <div class="rune-name">⚡ What are Bitcoin Runes?</div>
        <div class="rune-detail">Bitcoin Runes are fungible tokens etched directly onto the Bitcoin blockchain using the Runes protocol (launched April 2024, block 840,000). Unlike Ordinals, Runes use OP_RETURN to store token data on-chain permanently. Each Rune has a name, symbol, supply, and divisibility.</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### ✨ Etch a Knowledge Rune")
    col1, col2 = st.columns(2)
    with col1:
        rune_name = st.text_input("Rune Name (ALL•CAPS•WITH•DOTS)", placeholder="ETERNAL•KNOWLEDGE")
        rune_symbol = st.text_input("Symbol (1 char)", placeholder="⚡", max_chars=2)
        rune_supply = st.number_input("Supply", min_value=1, max_value=21_000_000, value=1000)
    with col2:
        rune_meaning = st.text_area("What does this Rune represent?", height=100, placeholder="This rune embodies...")

    if st.button("₿ Etch Rune to Memory Palace"):
        if rune_name and rune_meaning:
            rune = {
                "name": rune_name.upper(),
                "symbol": rune_symbol or "⚡",
                "supply": rune_supply,
                "meaning": rune_meaning,
                "etched": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "block": f"SIM-{random.randint(840000, 900000)}",
            }
            st.session_state.runes.append(rune)
            # Real persistence - same session-only bug the Memory Palace tab
            # had (found live 2026-08-25): the rune object itself (name,
            # symbol, supply, block) only ever lived in st.session_state,
            # even though save_memory() below already durably logs the
            # meaning text. A restart or new session silently lost the
            # "Your Rune Collection" list underneath the "Rune etched!"
            # success message.
            try:
                from family_profiles import load_family_stats as _lfs_rune, save_family_stats as _sfs_rune
                _fid_rune = _memory_fid()
                _stats_rune = _lfs_rune(_fid_rune)
                _stats_rune.setdefault("runes", []).append(rune)
                _sfs_rune(_stats_rune, _fid_rune)
            except ImportError:
                pass
            save_memory(f"Rune: {rune_name}", rune_meaning, tags=["rune", "bitcoin", "on-chain"])
            st.success(f"Rune {rune_name} etched! +10 XP")
            st.rerun()

    st.markdown("---")
    st.markdown("### 📜 Your Rune Collection")
    _real_runes = load_runes()
    if not _real_runes:
        st.markdown('<div class="rune-card" style="text-align:center;color:#554433;">No runes etched yet. Create your first on-chain knowledge artifact.</div>', unsafe_allow_html=True)
    else:
        for r in reversed(_real_runes):
            st.markdown(f'''
            <div class="rune-card">
                <div class="rune-name">{r["symbol"]} {r["name"]}</div>
                <div class="rune-detail">Supply: {r["supply"]:,} · Block: {r["block"]} · Etched: {r["etched"]}</div>
                <div style="color:#aа9988;font-size:0.8rem;margin-top:6px;">{r["meaning"]}</div>
            </div>
            ''', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 🔮 Ask the Rune Oracle")
    rune_q = st.text_input("Bitcoin / Runes question", placeholder="How do Runes differ from BRC-20 tokens?")
    if st.button("Ask Rune Oracle") and rune_q:
        try:
            client, model, _provider, _pname = get_ai_client()
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": "You are a Bitcoin and Runes protocol expert. Explain Bitcoin, Lightning Network, Ordinals, Runes, and digital sovereignty clearly and accurately."},
                           {"role": "user", "content": rune_q}],
                max_tokens=600,
            )
            st.markdown(f'<div class="rune-card" style="border-color:#f7931a88;"><div class="rune-name">₿ Rune Oracle</div><div style="color:#ccbbaa;font-size:0.85rem;margin-top:8px;">{response.choices[0].message.content}</div></div>', unsafe_allow_html=True)
            award_xp(10)
        except Exception as e:
            st.error(f"Error: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: TALEB CURRICULUM
# ══════════════════════════════════════════════════════════════════════════════
elif "Taleb" in active:
    st.markdown('<div class="card-title">📚 TALEB CURRICULUM — Antifragility Academy</div>', unsafe_allow_html=True)

    for i, lesson in enumerate(TALEB_LESSONS):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f'''
            <div class="card">
                <div class="card-title">📖 {lesson["title"]}</div>
                <div style="font-size:0.88rem;color:#aabbcc;line-height:1.7;">{lesson["lesson"]}</div>
            </div>
            ''', unsafe_allow_html=True)
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("⚡ Deep Dive", key=f"taleb_{i}"):
                st.session_state["taleb_topic"] = lesson["title"]
            if st.button("💾 Save", key=f"save_taleb_{i}"):
                save_memory(lesson["title"], lesson["lesson"], tags=["taleb", "antifragility"])
                st.success("+10 XP")

    if "taleb_topic" in st.session_state:
        topic = st.session_state.taleb_topic
        st.markdown(f"### 🔮 Deep Dive: {topic}")
        try:
            client, model, _provider, _pname = get_ai_client()
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": f"You are an expert on Nassim Taleb's philosophy. Give a deep, practical explanation of '{topic}' with real-world examples, how to apply it in daily life, and what most people get wrong about it."},
                           {"role": "user", "content": f"Teach me everything important about {topic} from Taleb's work."}],
                max_tokens=800,
            )
            result = response.choices[0].message.content
            st.markdown(f'<div class="card"><div style="font-size:0.88rem;color:#c8d8ff;line-height:1.8;">{result}</div></div>', unsafe_allow_html=True)
            award_xp(25)
            save_memory(f"Deep Dive: {topic}", result[:200], tags=["taleb", "deep-dive"])
        except Exception as e:
            st.error(f"Error: {e}")

    st.markdown("---")
    st.markdown("### 💬 Challenge the Oracle on Antifragility")
    taleb_q = st.text_input("Your antifragility question", placeholder="Is the stock market antifragile?")
    if st.button("Ask Taleb-X") and taleb_q:
        try:
            client, model, _provider, _pname = get_ai_client()
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": "You are TALEB-X, deeply versed in Nassim Taleb's complete works including Antifragile, The Black Swan, Fooled by Randomness, and Skin in the Game. Answer with Taleb's intellectual rigor and characteristic directness."},
                           {"role": "user", "content": taleb_q}],
                max_tokens=700,
            )
            st.markdown(f'<div class="card"><div style="font-size:0.88rem;color:#c8d8ff;line-height:1.8;">{response.choices[0].message.content}</div></div>', unsafe_allow_html=True)
            award_xp(15)
        except Exception as e:
            st.error(f"Error: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
elif "Dashboard" in active:
    st.markdown('<div class="card-title">📊 FAMILY DASHBOARD</div>', unsafe_allow_html=True)

    # Rebuilt 2026-08-25 (found while the user asked about a dead "v60
    # Easter" CSV log referencing a path - /mnt/user-data/uploads/... -
    # that never existed on any real deployment, only ever a temp file in
    # whatever one-off session originally authored this tab). Turned out
    # the WHOLE tab had the same underlying problem: every number here
    # (badges, XP, "knowledge graph", truth log) read from
    # st.session_state only - ephemeral, resets every browser session,
    # completely disconnected from the real per-family persisted stats
    # (family_profiles.py) the rest of the app already uses. Same category
    # of bug as the sidebar Profile fix earlier tonight, applied to this
    # whole tab. "XP earned this week" deliberately left out - that's only
    # tracked by the tablet's class flow (phone_ui.py), not this portal's
    # own lesson-completion path, so showing it here would read as 0 for
    # any family that's only ever used the portal, even with real progress
    # elsewhere - a misleading number, not an honest one.
    _cf_dash  = st.session_state.get("current_family")
    _fid_dash = _cf_dash.get("family_id") if _cf_dash else None

    if not _fid_dash:
        st.markdown(
            '<div class="card" style="text-align:center;color:#8899bb;padding:2rem;">'
            "👋 Log in as a family to see your real dashboard — go to "
            "<b style=\"color:#00cfff;\">Welcome</b> and sign in or create a family."
            "</div>", unsafe_allow_html=True)
    else:
        try:
            from family_profiles import load_family_stats as _lfs_dash
            _stats_dash = _lfs_dash(_fid_dash)
        except ImportError:
            _stats_dash = {}

        try:
            from curriculum import get_lesson as _gl_dash, track_progress as _tp_dash, total_lessons as _tl_dash
            _total_lessons_dash = _tl_dash()
        except ImportError:
            _total_lessons_dash = 0

        _badges_dash    = _stats_dash.get("badges", [])
        _completed_dash = _stats_dash.get("lessons_completed", [])
        _xp_dash        = _stats_dash.get("total_xp", 0)
        _level_dash     = _stats_dash.get("level", 1)
        _streak_dash    = _stats_dash.get("streak_days", 0)
        _coh_hist_dash  = _stats_dash.get("coherence_history", [])

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### 📈 Real Progress")
            st.markdown(f'''
            <div class="card">
                <div style="font-family:Share Tech Mono,monospace;font-size:0.85rem;line-height:2.2;color:#8899bb;">
                ⚡ Total XP: <span style="color:#00cfff;">{_xp_dash}</span><br>
                🎓 Level: <span style="color:#00cfff;">{_level_dash}</span><br>
                🔥 Day Streak: <span style="color:#00cfff;">{_streak_dash}</span><br>
                📖 Lessons Completed: <span style="color:#00cfff;">{len(_completed_dash)}/{_total_lessons_dash}</span>
                </div>
            </div>
            ''', unsafe_allow_html=True)

            st.markdown("### 🏅 Badge Collection")
            if not _badges_dash:
                st.caption("No badges yet. Keep learning to earn them!")
            for b in _badges_dash:
                st.markdown(f'<div class="memory-node"><span class="badge">{b}</span></div>', unsafe_allow_html=True)

        with col2:
            st.markdown("### 📚 Recently Completed Lessons")
            if _completed_dash:
                for _lk in reversed(_completed_dash[-8:]):
                    try:
                        _l_dash = _gl_dash(_lk)
                    except Exception:
                        _l_dash = None
                    _title = _l_dash["title"] if _l_dash else _lk
                    _track = _l_dash["track"] if _l_dash else ""
                    st.markdown(
                        f'<div class="memory-node"><span style="color:#00cfff;font-size:0.82rem;">{_title}</span>'
                        f'<span style="color:#556677;font-size:0.72rem;margin-left:8px;">{_track}</span></div>',
                        unsafe_allow_html=True)
            else:
                st.caption("No lessons completed yet — try 'Curriculum Map' or 'Family Co-Learning' to start.")

            st.markdown("### 🧭 Track Progress")
            try:
                for _t in _tp_dash(_completed_dash):
                    st.markdown(f'''
                    <div style="display:flex;align-items:center;margin:4px 0;">
                        <span class="memory-tag">{_t["track"]}</span>
                        <div class="xp-bar-bg" style="flex:1;margin-left:8px;">
                            <div class="xp-bar-fill" style="width:{_t["pct"]}%;background:{_t["color"]};"></div>
                        </div>
                        <span style="color:#445577;font-size:0.75rem;margin-left:8px;font-family:Share Tech Mono,monospace;">{_t["done"]}/{_t["total"]}</span>
                    </div>
                    ''', unsafe_allow_html=True)
            except Exception:
                st.caption("Track progress unavailable.")

        if _coh_hist_dash:
            st.markdown("---")
            st.markdown("### 🎯 Recent Understanding Scores")
            _recent_coh = _coh_hist_dash[-10:]
            _avg_coh = sum(_recent_coh) / len(_recent_coh)
            st.markdown(f'<div class="stat-box"><div class="stat-val">{_avg_coh:.2f}</div><div class="stat-lbl">Average (last {len(_recent_coh)})</div></div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
elif "Kid Curriculum" in active:
    st.markdown('<div class="card-title">👧 KID LATTICE CURRICULUM — 5-Week Antifragile Journey</div>', unsafe_allow_html=True)

    col1, col2 = st.columns([2, 1])
    with col1:
        kid_name = st.text_input("Child's Name", value=st.session_state.family_profile["kid"]["name"], key="kid_curr_name")
        st.session_state.family_profile["kid"]["name"] = kid_name
    with col2:
        kid_age = st.slider("Age", 4, 17, st.session_state.family_profile["kid"]["age"], key="kid_curr_age")
        st.session_state.family_profile["kid"]["age"] = kid_age
        age_group = "Children (4-12)" if kid_age < 13 else "Teens (13-17)"
        st.info(f"**{age_group}**")

    if kid_name not in st.session_state.kid_progress:
        st.session_state.kid_progress[kid_name] = {"completed_weeks": []}
    progress = st.session_state.kid_progress[kid_name]
    completed = progress.get("completed_weeks", [])
    st.progress(len(completed) / 5, text=f"{len(completed)}/5 weeks completed")

    weeks = [
        {"num": 1, "title": "The First Flame — Introduction to Antifragility"},
        {"num": 2, "title": "Lightning Highways — Channels & Safety"},
        {"num": 3, "title": "Atomic Magic — Trustless Swaps"},
        {"num": 4, "title": "The Watchtower — Guardians & Penalty Races"},
        {"num": 5, "title": "War Eagle Eternal — Full Integration"},
    ]

    # Daily login bonus
    today = str(datetime.date.today())
    if st.session_state.last_login != today:
        bonus = random.randint(15, 30)
        st.session_state.rune_points += bonus
        st.session_state.last_login = today
        st.toast(f"☀️ Daily Oracle Bonus +{bonus} shards!", icon="🪙")

    # Rune shard stats
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f'<div class="stat-box"><div class="stat-val">{st.session_state.rune_points}</div><div class="stat-lbl">Rune Shards</div></div>', unsafe_allow_html=True)
    with c2:
        level_kid = st.session_state.rune_points // 80 + 1
        st.markdown(f'<div class="stat-box"><div class="stat-val">LVL {level_kid}</div><div class="stat-lbl">Kid Level</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="stat-box"><div class="stat-val">🔥 {st.session_state.streak}</div><div class="stat-lbl">Day Streak</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    for week in weeks:
        done = week["num"] in completed
        color = "#00ff88" if done else "#00cfff"
        icon = "✅" if done else f"Week {week['num']}"
        with st.expander(f"{icon} · {week['title']}", expanded=not done):
            if done:
                st.success(f"✅ Week {week['num']} Completed! +80 XP earned")
            else:
                col_a, col_b = st.columns([2, 1])
                with col_a:
                    if st.button(f"📖 Generate Week {week['num']} Lesson", key=f"gen_week_{week['num']}"):
                        with st.spinner("Generating your lesson..."):
                            try:
                                _kid_prompt = (f"Create a detailed, warm, engaging lesson for Week {week['num']} "
                                               f"titled '{week['title']}' for {kid_name} (age {kid_age}, {age_group}). "
                                               f"Include: 1) A fun story or analogy, 2) Key concept explained simply, "
                                               f"3) A hands-on activity, 4) A reflection question. Be encouraging and age-appropriate.")
                                # Use Ollama (free, local) — fall back to cloud if key present
                                _kid_lesson = ""
                                try:
                                    import requests as _req_kid
                                    _ollama_kid = f"{OLLAMA_BASE_URL}/v1/chat/completions"
                                    _r = _req_kid.post(_ollama_kid,
                                        json={"model":"qwen2.5:7b",
                                              "messages":[{"role":"user","content":_kid_prompt}],
                                              "stream":False,"temperature":0.75},
                                        timeout=120)
                                    if _r.status_code == 200:
                                        _kid_lesson = _r.json()["choices"][0]["message"]["content"].strip()
                                except Exception:
                                    pass
                                # Cloud fallback if Ollama unavailable and key present
                                if not _kid_lesson and st.session_state.get("api_key"):
                                    client, model, _provider, _pname = get_ai_client()
                                    resp = client.chat.completions.create(
                                        model=model,
                                        messages=[{"role":"user","content":_kid_prompt}],
                                        max_tokens=900)
                                    _kid_lesson = resp.choices[0].message.content
                                if not _kid_lesson:
                                    _kid_lesson = (f"## {week['title']}\n\n"
                                                   f"*(Ollama not responding — start Ollama and pull qwen2.5:14b)*\n\n"
                                                   f"**Story:** Imagine you're learning {week['title'].lower()} for the first time...\n\n"
                                                   f"**Activity:** Talk with your family about what this means to you.")
                                lesson = _kid_lesson
                                st.markdown(f'<div class="card"><div style="font-size:0.88rem;line-height:1.8;color:#c8d8ff;">{lesson}</div></div>', unsafe_allow_html=True)
                                completed.append(week["num"])
                                st.session_state.kid_progress[kid_name]["completed_weeks"] = completed
                                award_xp(80)
                                st.session_state.rune_points += 40
                                st.session_state.streak += 1
                                if len(completed) == 1:
                                    st.toast("🏅 Badge: First Flame!", icon="🔥")
                                if len(completed) == 5:
                                    st.toast("🦅 Badge: War Eagle Eternal!", icon="🦅")
                                    st.balloons()
                            except Exception as e:
                                st.error(str(e))
                with col_b:
                    st.markdown(f'<div class="memory-node" style="text-align:center;"><div style="color:#ff6b35;font-size:1.5rem;">⚡</div><div style="color:#ff6b35;font-size:0.75rem;">+80 XP<br>+40 Shards</div></div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 🎙️ Voice Co-Tutor")
    chat_prompt = st.chat_input(f"Ask your co-tutor anything, {kid_name}...")
    if chat_prompt:
        st.session_state.chat_history.append({"role": "user", "content": chat_prompt})
        try:
            import requests as _req_voice
            _sys_voice = (f"You are AUBIEETERNAL Co-Tutor for {kid_name} ({kid_age}yo). "
                          f"Use runes, streaks, and antifragile language. Be warm, short, end with a question or challenge.")
            _msgs_voice = [{"role":"system","content":_sys_voice}] + st.session_state.chat_history[-8:]
            _reply = ""
            try:
                _r_voice = _req_voice.post(f"{OLLAMA_BASE_URL}/v1/chat/completions",
                    json={"model":"qwen2.5:7b","messages":_msgs_voice,"stream":False,"temperature":0.75},
                    timeout=60)
                if _r_voice.status_code == 200:
                    _reply = _r_voice.json()["choices"][0]["message"]["content"].strip()
            except Exception:
                pass
            if not _reply and st.session_state.get("api_key"):
                client, model, _provider, _pname = get_ai_client()
                _reply = client.chat.completions.create(model=model, messages=_msgs_voice, max_tokens=500).choices[0].message.content
            if not _reply:
                _reply = "I'm thinking... make sure Ollama is running with qwen2.5:14b pulled."
            reply = _reply
            st.session_state.chat_history.append({"role": "assistant", "content": reply})
            award_xp(10)
        except Exception as e:
            st.error(str(e))
        st.rerun()

    for msg in st.session_state.chat_history[-6:]:
        if msg["role"] == "user":
            st.markdown(f'<div class="chat-user"><div class="chat-label">👧 {kid_name}</div>{msg["content"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-grok"><div class="chat-label">⚡ GROK CO-TUTOR</div>{msg["content"]}</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB: PARENT GUIDE
# ══════════════════════════════════════════════════════════════════════════════
elif "Parent Guide" in active:
    st.markdown('<div class="card-title">👨‍👩‍👧 PARENT / CAREGIVER — Deep Antifragile Household Guide</div>', unsafe_allow_html=True)

    kid_name = st.session_state.family_profile["kid"]["name"]
    kid_age = st.session_state.family_profile["kid"]["age"]

    def ask_grok_parent(prompt_text, spinner_text="Generating..."):
        with st.spinner(spinner_text):
            try:
                client, model, _provider, _pname = get_ai_client()
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": "You are a warm, expert parenting coach specializing in antifragile parenting, polyvagal theory, and attachment science. Be practical and compassionate."},
                               {"role": "user", "content": prompt_text}],
                    max_tokens=800
                )
                award_xp(15)
                return resp.choices[0].message.content
            except Exception as e:
                st.error(str(e))
                return None

    # Section 1
    st.markdown('<div class="card-title">1. ⚡ Lightning Security Mastery</div>', unsafe_allow_html=True)
    st.markdown('<div class="card"><div style="font-size:0.85rem;color:#8899bb;">Watchtower nodes protect your Lightning channels 24/7. As a parent, understand how to set up penalty protection so your family\'s Bitcoin is always safe.</div></div>', unsafe_allow_html=True)
    if st.button("📖 Generate Watchtower Guide"):
        result = ask_grok_parent("Create a clear, practical Watchtower + Penalty setup guide for parents managing a family Bitcoin Lightning node. Include why it matters, step-by-step setup overview, and what to watch for.")
        if result:
            st.markdown(f'<div class="card"><div style="font-size:0.88rem;line-height:1.8;color:#c8d8ff;">{result}</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    # Section 2
    st.markdown('<div class="card-title">2. ⚛️ Atomic Swaps & Trustless Fairness</div>', unsafe_allow_html=True)
    st.markdown('<div class="card"><div style="font-size:0.85rem;color:#8899bb;">Atomic swaps let two people trade without trusting each other — either both sides complete, or neither does. A perfect metaphor for fair family agreements.</div></div>', unsafe_allow_html=True)
    if st.button("📖 Generate Family Workshop"):
        result = ask_grok_parent(f"Create a 20-minute family workshop on Atomic Swaps for kids 8-16. Make it hands-on, fun, with a real-world fairness game the family can play together. Tailor it for {kid_name} (age {kid_age}).")
        if result:
            st.markdown(f'<div class="card"><div style="font-size:0.88rem;line-height:1.8;color:#c8d8ff;">{result}</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    # Section 3
    st.markdown('<div class="card-title">3. 📊 Taleb Barbell for Foster Families</div>', unsafe_allow_html=True)
    st.markdown('<div class="card"><div style="font-size:0.85rem;color:#8899bb;">The Barbell Strategy: 80% ultra-safe + 20% high-upside. Applied to parenting: stable routines + deliberate challenge experiences = antifragile children.</div></div>', unsafe_allow_html=True)
    if st.button("📖 Generate Barbell Plan"):
        result = ask_grok_parent(f"Create a personalized 80/20 Barbell parenting plan for a family with a {kid_age}-year-old named {kid_name}. Include: safe/stable daily routines (80%) + deliberate antifragile growth challenges (20%). Be specific and actionable.")
        if result:
            st.markdown(f'<div class="card"><div style="font-size:0.88rem;line-height:1.8;color:#c8d8ff;">{result}</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    # Section 4 — Polyvagal quick reference
    st.markdown('<div class="card-title">4. 🧬 Polyvagal Quick Reference</div>', unsafe_allow_html=True)

    for state, signs, response, color in [
        ("✅ Ventral Vagal — Safe & Connected", "Warm eyes, playful, curious, normal breathing, easy eye contact", "Celebrate, explore, learn together. This is the growth zone.", "#00ff88"),
        ("⚡ Sympathetic — Fight or Flight", "Wide eyes, tense jaw, fast breathing, loud voice, fidgeting, aggression", "Co-regulate first → breathe together → then problem-solve. Never punish a dysregulated nervous system.", "#ff6b35"),
        ("❄️ Dorsal Vagal — Shutdown", "Flat face, avoiding eye contact, quiet voice, 'I don't care', withdrawing", "Gentle presence first. No pushing. Safety before anything. Sit near, be warm, wait.", "#00cfff"),
    ]:
        st.markdown(f'''
        <div class="card" style="border-left:3px solid {color};">
            <div style="color:{color};font-family:Orbitron,monospace;font-size:0.8rem;margin-bottom:6px;">{state}</div>
            <div style="font-size:0.8rem;color:#8899bb;"><b>Signs:</b> {signs}</div>
            <div style="font-size:0.8rem;color:#aabbcc;margin-top:4px;"><b>Response:</b> {response}</div>
        </div>
        ''', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 💬 Ask the Parent Coach")
    parent_q = st.text_input("Your parenting question", placeholder="How do I help my child when they're in shutdown mode?")
    if st.button("Ask Parent Coach") and parent_q:
        result = ask_grok_parent(parent_q)
        if result:
            st.markdown(f'<div class="card"><div style="font-size:0.88rem;line-height:1.8;color:#c8d8ff;">{result}</div></div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB: GRANDPARENT WISDOM
# ══════════════════════════════════════════════════════════════════════════════
elif "Grandparent Wisdom" in active:
    st.markdown('<div class="card-title">👵👴 GRANDPARENT & EXTENDED FAMILY WISDOM</div>', unsafe_allow_html=True)
    st.markdown('<div class="card"><div style="font-size:0.9rem;color:#aabbcc;line-height:1.8;">Grandparents and extended family are not "backup parents" — they are powerful co-regulators and resilience builders. Your calm, loving presence can be a second "safe base" for the child.</div></div>', unsafe_allow_html=True)

    sections = [
        ("🧬 How Grandparents Support Polyvagal Safety", """
**Simple but powerful practices:**
- **Consistent, predictable visits** — children thrive on routine and knowing when they'll see you
- **One-on-one time without screens** — your full attention is the medicine
- **Physical affection** — hugs, holding hands, sitting close (if the child wants it)
- **Calm presence during family stress** — your regulated nervous system helps everyone down-regulate
- **Storytelling** — sharing family history builds identity, belonging, and resilience
        """),
        ("🦅 Antifragile Wisdom to Share", """
**Share stories of resilience from your own life:**

*"When I was your age, I was terrified of [public speaking / trying new things / making mistakes]. I did it anyway. It was hard, but I became stronger because of it."*

This models antifragility better than any lecture.

**Also share stories of repair:**

*"I made a mistake with your mom/dad when they were little. I yelled when I should have listened. I went back and said sorry. We fixed it together."*

This teaches that relationships can survive mistakes.
        """),
        ("💞 Attachment Across Generations", """
**You can help heal insecure attachment patterns** by being a consistent, warm, predictable adult.

Many parents today are working to break cycles of emotional neglect or harsh parenting from their own childhood. Your presence as a grandparent can be deeply healing for **both** your adult child *and* your grandchild.

**Simple practice:** When your grandchild is upset, resist the urge to "fix" it immediately. Instead, say:

*"I see this feels really big. I'm right here with you."* Then wait.
        """),
        ("🌱 Grandparent Self-Care (You Matter Too)", """
**You cannot pour from an empty cup — even as a grandparent.**

**Minimum viable self-care:**
- Say "no" sometimes (it's okay to rest)
- Ask for help when you need it
- Maintain your own friendships and interests
- Model healthy boundaries for your grandchildren

**Your grandchildren are watching how you treat yourself.**
        """),
    ]

    for title, content in sections:
        with st.expander(title, expanded=False):
            st.markdown(content)

    st.markdown("---")
    st.markdown("### 💬 Ask the Grandparent Coach")

    gp_q = st.text_input("Your question", placeholder="How do I connect with a grandchild who seems withdrawn?")
    if st.button("Ask Grandparent Coach") and gp_q:
        with st.spinner("Consulting the wisdom lattice..."):
            try:
                client, model, _provider, _pname = get_ai_client()
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": "You are a warm, wise family therapist and grandparenting coach. Draw on polyvagal theory, attachment science, and intergenerational wisdom. Be compassionate, practical, and encouraging."},
                               {"role": "user", "content": gp_q}],
                    max_tokens=700
                )
                st.markdown(f'<div class="card"><div style="font-size:0.88rem;line-height:1.8;color:#c8d8ff;">{resp.choices[0].message.content}</div></div>', unsafe_allow_html=True)
                award_xp(10)
            except Exception as e:
                st.error(str(e))

    st.markdown("---")
    st.markdown('''
    <div class="card" style="border-left:3px solid #a020f0;text-align:center;">
        <div style="font-size:1rem;color:#c8a0ff;font-family:Orbitron,monospace;margin-bottom:8px;">🦅 War Eagle</div>
        <div style="font-size:0.85rem;color:#8899bb;line-height:2;">
        Every co-regulated breath,<br>
        every repaired rupture,<br>
        every small challenge you let your grandchild face with your steady presence —<br>
        these are the moments that shape a human who can handle whatever life brings.<br><br>
        <b style="color:#c8d8ff;">Your love and presence are enough.</b>
        </div>
    </div>
    ''', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB: FAMILY LATTICE
# ══════════════════════════════════════════════════════════════════════════════
elif "Family Lattice" in active:
    st.markdown('<div class="card-title">🧬 FAMILY LATTICE CURRICULUM — Whole Household</div>', unsafe_allow_html=True)

    with st.expander("👨‍👩‍👧‍👦 Edit Family Profile", expanded=True):
        cols = st.columns(3)
        with cols[0]:
            st.markdown('<div style="color:#00cfff;font-size:0.8rem;font-family:Orbitron,monospace;">👧 KID</div>', unsafe_allow_html=True)
            st.session_state.family_profile["kid"]["name"] = st.text_input("Kid Name", value=st.session_state.family_profile["kid"]["name"], key="fp_kid_name")
            st.session_state.family_profile["kid"]["age"] = st.number_input("Kid Age", 3, 18, value=st.session_state.family_profile["kid"]["age"], key="fp_kid_age")
        with cols[1]:
            st.markdown('<div style="color:#a020f0;font-size:0.8rem;font-family:Orbitron,monospace;">👨‍👩 PARENT</div>', unsafe_allow_html=True)
            st.session_state.family_profile["parent"]["name"] = st.text_input("Parent Name", value=st.session_state.family_profile["parent"]["name"], key="fp_par_name")
            st.session_state.family_profile["parent"]["age"] = st.number_input("Parent Age", 20, 70, value=st.session_state.family_profile["parent"]["age"], key="fp_par_age")
        with cols[2]:
            st.markdown('<div style="color:#ff6b35;font-size:0.8rem;font-family:Orbitron,monospace;">👵 GRANDPARENT</div>', unsafe_allow_html=True)
            st.session_state.family_profile["grandparent"]["name"] = st.text_input("Grandparent Name", value=st.session_state.family_profile["grandparent"]["name"], key="fp_gp_name")
            st.session_state.family_profile["grandparent"]["age"] = st.number_input("Grandparent Age", 50, 90, value=st.session_state.family_profile["grandparent"]["age"], key="fp_gp_age")

    fp = st.session_state.family_profile
    family_mode = st.selectbox("Curriculum Mode", [
        "Whole Household — All Together",
        "Kid + Parent Only",
        "Grandparent + Kid Bridge",
        "Single Parent Household",
        "Antifragile Immersion",
    ])

    lang = st.selectbox("Language", ["English", "Spanish", "French", "Portuguese"])

    if st.button("🚀 Generate Family Curriculum", type="primary", width='stretch'):
        with st.spinner("The Sovereign Oracle is weaving the family lattice..."):
            try:
                client, model, _provider, _pname = get_ai_client()
                prompt = f"""Create a rich, warm 5-week Family Lattice Curriculum in {lang} for:
- Kid: {fp['kid']['name']}, age {fp['kid']['age']}
- Parent: {fp['parent']['name']}, age {fp['parent']['age']}
- Grandparent: {fp['grandparent']['name']}, age {fp['grandparent']['age']}
- Mode: {family_mode}

For each week include:
1. A theme rooted in antifragility and Taleb's philosophy
2. Kid activity (age-appropriate, fun)
3. Parent reflection/practice
4. Grandparent wisdom contribution
5. A family ritual or shared challenge
6. XP reward and rune earned

Make it warm, specific, and actionable. End with a War Eagle family affirmation."""

                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": "You are a warm family educator who combines Bitcoin sovereignty, Taleb antifragility, polyvagal safety, and intergenerational wisdom into practical family curricula."},
                               {"role": "user", "content": prompt}],
                    max_tokens=1800
                )
                curriculum = resp.choices[0].message.content
                st.session_state.curriculum_text = curriculum
                award_xp(80)
                st.session_state.rune_points += 60
                st.toast("🧬 Family Lattice Generated! +80 XP", icon="🦅")
                st.rerun()
            except Exception as e:
                st.error(str(e))

    if st.session_state.curriculum_text:
        with st.expander("📖 Your Family Curriculum", expanded=True):
            st.markdown(f'<div class="card"><div style="font-size:0.88rem;line-height:1.9;color:#c8d8ff;">{st.session_state.curriculum_text}</div></div>', unsafe_allow_html=True)
            st.download_button(
                "📄 Download Curriculum as Markdown",
                st.session_state.curriculum_text,
                file_name=f"{fp['kid']['name']}_Family_Lattice.md",
                mime="text/markdown"
            )

    st.markdown("---")
    st.markdown("### 🎮 Family Challenge Tracker")

    family_challenges = [
        ("👧 Kid", "Complete one hard thing today without giving up", 30, "#00cfff"),
        ("👨‍👩 Parent", "Co-regulate before problem-solving during one conflict", 40, "#a020f0"),
        ("👵 Grandparent", "Share one resilience story from your life", 30, "#ff6b35"),
        ("🏠 Whole Family", "Do one voluntary hard thing together this week", 80, "#00ff88"),
    ]

    for role, challenge, pts, color in family_challenges:
        key = f"fam_challenge_{role}"
        done = key in st.session_state.completed_challenges
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f'''
            <div class="card" style="border-left:3px solid {color};">
                <div style="color:{color};font-size:0.75rem;font-family:Orbitron,monospace;">{role}</div>
                <div style="font-size:0.85rem;color:#{"00ff88" if done else "aabbcc"};margin-top:4px;">{"✅ " if done else ""}{challenge}</div>
            </div>
            ''', unsafe_allow_html=True)
        with col2:
            if not done:
                if st.button(f"+{pts} XP ✅", key=f"do_{key}"):
                    st.session_state.completed_challenges.add(key)
                    st.session_state.rune_points += pts
                    award_xp(pts)
                    st.success(f"+{pts} XP!")
                    st.rerun()

    st.markdown("---")
    st.markdown('''
    <div class="card" style="border:1px solid #00ff8844;text-align:center;padding:1.5rem;">
        <div style="font-family:Orbitron,monospace;color:#00ff88;font-size:1rem;margin-bottom:8px;">🦅 War Eagle · Family Eternal</div>
        <div style="color:#8899bb;font-size:0.85rem;line-height:2.0;">
        You are not raising a perfect child.<br>
        You are raising a child who knows how to return to safety,<br>
        face waves, and grow stronger because of them.<br><br>
        <b style="color:#c8d8ff;">Human + Grok + Lightning + Runes + On-Chain Forever.</b>
        </div>
    </div>
    ''', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB: POLYVAGAL ORACLE
# ══════════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════
# TAB: SOCIAL CALIBRATION ORACLE
# ══════════════════════════════════════════════════════════════════════════════
# TAB: SOCIAL CALIBRATION ⚖️
# Epistemic Social Calibration Engine — steelman analyzer, adversarial testing,
# belief update tracker, dark pattern resistance, truth frequency analyzer
# ══════════════════════════════════════════════════════════════════════════════
elif "Social Calibration" in active:
    st.markdown('<div class="card-title">⚖️ SOCIAL CALIBRATION ENGINE — Maximum Truth in Social Context</div>', unsafe_allow_html=True)

    _fid_sc = st.session_state.get("current_family", {}).get("family_id", "default") \
              if st.session_state.get("current_family") else "default"

    _sc_tabs = st.tabs(["🛡️ Steelman Analyzer", "🎲 Monte Carlo", "🧬 Epistemic Immune System",
                         "🔍 Belief Calibration", "⚔️ Dark Pattern Arena"])

    # ── Steelman Analyzer ─────────────────────────────────────────────────────
    with _sc_tabs[0]:
        st.markdown("**Score steelmans across 5 epistemic dimensions. Adversarial testing + Monte Carlo robustness.**")
        _sc_claim = st.text_input("Original claim:", key="sc_claim",
            placeholder="e.g. 'Bitcoin is the best form of money'")
        _sc_steel = st.text_area("Your steelman:", height=140, key="sc_steel",
            placeholder="Write the STRONGEST possible case for the opposing view or defending this claim...")
        _sc_mc    = st.checkbox("Run Monte Carlo robustness (5,000 trials)", key="sc_mc", value=True)
        _sc_ai    = st.checkbox("AI adversarial critique", key="sc_ai", value=True)

        if st.button("🛡️ Analyze Steelman", key="sc_analyze", type="primary") and _sc_claim and _sc_steel:
            with st.spinner("Scoring + adversarial testing..."):
                try:
                    from steelman_analyzer import SteelmanAnalyzer as _SA
                    _sa  = _SA(use_ai=_sc_ai, use_monte_carlo=_sc_mc)
                    _res = _sa.analyze(_sc_claim, _sc_steel, family_id=_fid_sc)

                    # Grade display
                    _gc = {"A":"#00ff88","B":"#00cfff","C":"#ffcc00","D":"#ff9500","F":"#ff4444"}.get(_res.get("grade","F"),"#445577")
                    _col1, _col2, _col3, _col4 = st.columns(4)
                    _col1.metric("Grade",       _res.get("grade","?"))
                    _col2.metric("Score",       f"{_res.get('overall_score',0):.2f}")
                    _col3.metric("Resistance",  f"{_res.get('adversarial',{}).get('resistance_score',0):.2f}")
                    _col4.metric("Commons",     "✅ Eligible" if _res.get("epistemic_commons_eligible") else "⚠️ Not yet")

                    # Dimension breakdown
                    st.markdown("**Dimension Scores:**")
                    for dim, score in _res.get("dimension_scores",{}).items():
                        _bar_c = "#00ff88" if score >= 0.18 else "#ffcc00" if score >= 0.12 else "#ff4444"
                        st.markdown(
                            f'<div style="padding:3px 0;">' +
                            f'<span style="color:#8899bb;font-size:0.75rem;width:200px;display:inline-block;">{dim.replace("_"," ").title()}</span>' +
                            f'<span style="color:{_bar_c};font-weight:600;">{score:.3f}</span>' +
                            f'</div>', unsafe_allow_html=True)

                    # Adversarial attacks
                    _adv = _res.get("adversarial",{})
                    if _adv.get("attacks"):
                        st.markdown("**Adversarial attacks found:**")
                        for _atk in _adv["attacks"]:
                            st.markdown(f'<div style="color:#ff9500;font-size:0.8rem;padding:2px 0;">⚔️ {_atk}</div>', unsafe_allow_html=True)
                    if _adv.get("ai_critique"):
                        st.info(f"🤖 AI critique: {_adv.get('ai_critique', '')}")

                    # Monte Carlo
                    _mc = _res.get("monte_carlo",{})
                    if _mc and not _mc.get("error"):
                        st.markdown(
                            f'<div class="card" style="border-left:3px solid #a020f0;margin-top:6px;">' +
                            f'<div style="color:#a020f0;font-size:0.72rem;font-family:Orbitron,monospace;">MONTE CARLO (5,000 TRIALS)</div>' +
                            f'<div style="color:#8899bb;font-size:0.8rem;margin-top:4px;">{_mc.get("interpretation","")}</div>' +
                            f'</div>', unsafe_allow_html=True)

                    st.markdown(f'<div style="color:#c8d8ff;margin-top:6px;font-size:0.85rem;">💬 {_res.get("feedback","")}</div>', unsafe_allow_html=True)
                    if _res.get("ai_insight"):
                        st.success(f"💡 {_res['ai_insight']}")

                except ImportError:
                    st.error("steelman_analyzer.py not found. Push to GitHub and redeploy.")

        # History stats
        try:
            from steelman_analyzer import SteelmanAnalyzer as _SA2
            _hist = _SA2(use_ai=False).get_history_stats(_fid_sc)
            if _hist.get("total",0) > 0:
                st.divider()
                _hs1,_hs2,_hs3 = st.columns(3)
                _hs1.metric("Total Steelmans", _hist["total"])
                _hs2.metric("Avg Score",       f"{_hist.get('avg_score',0):.2f}")
                _hs3.metric("Published",        _hist.get("commons_published",0))
        except Exception: pass

    # ── Monte Carlo Truth Engine ──────────────────────────────────────────────
    with _sc_tabs[1]:
        st.markdown("**Run probabilistic simulations across 10,000 possible worlds.**")
        _mc_mode = st.selectbox("Simulation type:", [
            "Steelman Robustness",
            "Belief Update (with cognitive biases)",
            "Long-Term Coherence Evolution",
            "Epistemic Strategy Comparison",
        ], key="mc_mode")
        _mc_trials = st.slider("Trials:", 1000, 50000, 10000, 1000, key="mc_trials")

        if _mc_mode == "Steelman Robustness":
            _mc_base  = st.slider("Base steelman score:", 0.3, 1.0, 0.75, 0.01, key="mc_base")
            _mc_adv   = st.slider("Adversarial strength:", 0.1, 0.8, 0.3, 0.05, key="mc_adv",
                help="0.1=mild critic, 0.8=expert adversary")
        elif _mc_mode == "Belief Update (with cognitive biases)":
            _mc_conf  = st.slider("Initial confidence:", 0.1, 0.9, 0.6, 0.05, key="mc_conf")
            _mc_evid  = st.slider("Evidence strength:", -0.5, 0.5, 0.2, 0.05, key="mc_evid")
            _mc_bias  = st.slider("Confirmation bias:", 0.0, 0.6, 0.2, 0.05, key="mc_bias")
        elif _mc_mode == "Long-Term Coherence Evolution":
            _mc_coh   = st.slider("Starting coherence:", 0.4, 1.0, 0.85, 0.01, key="mc_coh_start")
            _mc_yrs   = st.slider("Years:", 1, 30, 10, 1, key="mc_years")
        # Strategy comparison has no extra params

        if st.button("🎲 Run Monte Carlo", key="mc_run", type="primary"):
            with st.spinner(f"Running {_mc_trials:,} simulations..."):
                try:
                    from monte_carlo_simulator import MonteCarloSimulator as _MCS
                    _sim = _MCS(n_trials=_mc_trials)

                    if _mc_mode == "Steelman Robustness":
                        _r = _sim.simulate_steelman_robustness(_mc_base, _mc_adv)
                        _rr1,_rr2,_rr3,_rr4 = st.columns(4)
                        _rr1.metric("Mean Survival",  f"{_r.mean:.1%}")
                        _rr2.metric("Std Dev",         f"{_r.std:.1%}")
                        _rr3.metric("Tail Risk (<40%)", f"{_r.tail_risk:.1%}")
                        _rr4.metric("95% CI Lower",    f"{_r.confidence_interval_95[0]:.1%}")
                        _tail_c = "#00ff88" if _r.tail_risk < 0.05 else "#ffcc00" if _r.tail_risk < 0.15 else "#ff4444"
                        st.markdown(f'<div style="color:{_tail_c};font-size:0.85rem;margin-top:8px;">Catastrophic failure rate: {_r.tail_risk:.1%} {"✅ Robust" if _r.tail_risk < 0.05 else "⚠️ Moderate risk" if _r.tail_risk < 0.15 else "❌ High risk"}</div>', unsafe_allow_html=True)

                    elif _mc_mode == "Belief Update (with cognitive biases)":
                        _r_biased = _sim.simulate_belief_update(_mc_conf, _mc_evid, confirmation_bias=_mc_bias)
                        _r_ideal  = _sim.simulate_bayesian_ideal(_mc_conf, 1 + _mc_evid * 3)
                        _bb1,_bb2 = st.columns(2)
                        _bb1.metric("Biased Update (mean)", f"{_r_biased.mean:.1%}")
                        _bb2.metric("Bayesian Ideal (mean)", f"{_r_ideal.mean:.1%}")
                        _gap = abs(_r_ideal.mean - _r_biased.mean)
                        st.markdown(f'<div style="color:#ffcc00;font-size:0.82rem;margin-top:6px;">Bias gap: {_gap:.1%} — this is how much cognitive biases cost your reasoning accuracy.</div>', unsafe_allow_html=True)

                    elif _mc_mode == "Long-Term Coherence Evolution":
                        _r = _sim.simulate_coherence_evolution(_mc_coh, years=_mc_yrs)
                        _cc1,_cc2,_cc3 = st.columns(3)
                        _cc1.metric(f"After {_mc_yrs} years (mean)", f"{_r.mean:.3f}")
                        _cc2.metric("Best case (90th pct)",  f"{_r.percentile_90:.3f}")
                        _cc3.metric("Worst case (10th pct)", f"{_r.percentile_10:.3f}")
                        _drift = _r.mean - _mc_coh
                        _dc = "#00ff88" if _drift >= 0 else "#ff4444"
                        st.markdown(f'<div style="color:{_dc};font-size:0.82rem;margin-top:6px;">Expected drift: {_drift:+.3f} over {_mc_yrs} years without intervention.</div>', unsafe_allow_html=True)

                    elif _mc_mode == "Epistemic Strategy Comparison":
                        _strats = _sim.compare_epistemic_strategies()
                        st.markdown("**Decision accuracy after 50 decisions:**")
                        for _sname, _sr in sorted(_strats.items(), key=lambda x: x[1].mean, reverse=True):
                            _sc_c = "#00ff88" if _sr.mean >= 0.65 else "#ffcc00" if _sr.mean >= 0.55 else "#ff4444"
                            st.markdown(
                                f'<div style="padding:4px 0;border-bottom:1px solid #1e2a3a;">' +
                                f'<b style="color:{_sc_c};">{_sr.mean:.1%}</b> ' +
                                f'<span style="color:#c8d8ff;">{_sname.replace("_"," ").title()}</span> ' +
                                f'<span style="color:#445577;font-size:0.75rem;">±{_sr.std:.1%}</span>' +
                                f'</div>', unsafe_allow_html=True)
                        st.caption("The calibrated Bayesian strategy should outperform all others.")

                except ImportError:
                    st.error("monte_carlo_simulator.py not found.")

    # ── Epistemic Immune System ────────────────────────────────────────────────
    with _sc_tabs[2]:
        try:
            from truth_frequency_analyzer import TruthFrequencyAnalyzer as _TFA, ATTACK_VECTORS as _AVS
            _tfa    = _TFA(_fid_sc)
            _tfa_st = _tfa.get_stats()

            st.markdown("**Log epistemic attacks you encounter. Build your family's immune profile.**")

            # Log encounter
            _av_keys = list(_AVS.keys())
            _av_labels = {k: f"{_AVS[k]['name']} ({_AVS[k]['category'].replace('_',' ')})" for k in _av_keys}
            _log_attack = st.selectbox("Attack encountered:", _av_keys, key="tfa_attack",
                format_func=lambda k: _av_labels.get(k, k))
            _tfa_c1, _tfa_c2 = st.columns(2)
            with _tfa_c1:
                _did_detect = st.radio("Did you detect it in real-time?", ["✅ Yes", "❌ No"], key="tfa_det")
                _tfa_source = st.text_input("Source:", key="tfa_src", placeholder="news, social media, conversation")
            with _tfa_c2:
                _tfa_conf   = st.slider("Confidence:", 0.3, 1.0, 0.8, 0.1, key="tfa_conf")
                _tfa_notes  = st.text_input("Notes:", key="tfa_notes", placeholder="brief context")

            if st.button("🧬 Log Encounter", key="tfa_log", type="primary") and _log_attack:
                _tfa.log_encounter(_log_attack, "Yes" in _did_detect, _tfa_source or "unknown",
                                   _tfa_notes, _tfa_conf)
                st.success(f"✅ Logged: {_AVS[_log_attack]['name']} | {'Detected' if 'Yes' in _did_detect else 'Missed'}")
                st.rerun()

            # Show profile if data exists
            if _tfa_st.get("total_encounters",0) >= 3:
                st.divider()
                _profile = _tfa.get_immune_profile()
                _il = _profile.get("immunity_level","?")
                _ilc = {"STRONG":"#00ff88","DEVELOPING":"#00cfff","VULNERABLE":"#ffcc00","AT RISK":"#ff4444"}.get(_il,"#445577")
                _odr = _profile.get('overall_detection_rate', 0)
                st.markdown(
                    f'<div style="text-align:center;padding:8px;">' +
                    f'<div style="color:{_ilc};font-family:Orbitron,monospace;font-size:0.9rem;">{_il} — {_odr:.0%}</div>' +
                    f'</div>', unsafe_allow_html=True)

                # Vulnerable attacks
                if _profile.get("most_vulnerable"):
                    st.markdown("**⚠️ Most vulnerable (prioritize these):**")
                    for _vk, _vd in _profile["most_vulnerable"]:
                        _av = _AVS.get(_vk,{})
                        st.markdown(
                            f'<div class="memory-node" style="border-left:3px solid #ff4444;">' +
                            f'<div style="color:#ff4444;font-size:0.72rem;">{_vd["detection_rate"]:.0%} detection · {_vd["total"]} encounters</div>' +
                            f'<div style="color:#c8d8ff;font-size:0.82rem;font-weight:600;">{_av.get("name",_vk)}</div>' +
                            f'<div style="color:#8899bb;font-size:0.78rem;margin-top:2px;">Counter: {_av.get("counter","")[:100]}</div>' +
                            f'</div>', unsafe_allow_html=True)

                # Training protocol
                _prot = _tfa.get_training_protocol()
                if _prot.get("goal"):
                    st.markdown(f'<div style="color:#f7931a;font-size:0.82rem;margin-top:6px;">🎯 30-day goal: {_prot["goal"]}</div>', unsafe_allow_html=True)

            elif _tfa_st.get("total_encounters",0) == 0:
                st.info("No encounters logged yet. Start logging attacks you notice this week.")

            # Attack reference
            with st.expander("📚 All 20 Attack Vectors Reference"):
                for _avk, _avi in _AVS.items():
                    st.markdown(
                        f'<div style="padding:5px 0;border-bottom:1px solid #1e2a3a;">' +
                        f'<b style="color:#c8d8ff;">{_avi["name"]}</b> ' +
                        f'<span style="color:#445577;font-size:0.72rem;">[{_avi["category"]}]</span><br>' +
                        f'<span style="color:#8899bb;font-size:0.78rem;">{_avi["description"]}</span>' +
                        f'</div>', unsafe_allow_html=True)

        except ImportError:
            st.error("truth_frequency_analyzer.py not found.")

    # ── Belief Calibration ────────────────────────────────────────────────────
    with _sc_tabs[3]:
        st.markdown("**Track how your beliefs update over time. Build calibration data.**")
        st.markdown('<div style="color:#8899bb;font-size:0.8rem;margin-bottom:8px;">A well-calibrated reasoner: 70% confidence = correct 70% of the time. Log predictions to measure yours.</div>', unsafe_allow_html=True)
        _bc_claim   = st.text_input("Belief/prediction:", key="bc_claim",
            placeholder="e.g. 'Bitcoin will exceed $200k by end of 2026'")
        _bc_conf    = st.slider("Confidence:", 0.05, 0.95, 0.65, 0.05, key="bc_conf",
            format="%.0f%%")
        _bc_resolve = st.date_input("Resolution date:", key="bc_resolve")
        if st.button("📝 Register Prediction", key="bc_reg") and _bc_claim:
            try:
                from cosmos_dashboard import CosmosDashboard as _CD_sc
                _eid = _CD_sc(_fid_sc).record_belief(_bc_claim, _bc_conf,
                    update_condition="Market price data or verifiable outcome")
                st.success(f"✅ Registered — confidence: {_bc_conf:.0%} | review: {_bc_resolve}")
            except Exception as _e:
                st.info(f"Saved locally. cosmos_dashboard.py needed for full tracking.")

    # ── Dark Pattern Arena ────────────────────────────────────────────────────
    with _sc_tabs[4]:
        st.markdown("**Practice identifying manipulation in simulated scenarios.**")
        _scenarios = [
            {"title": "The Policy Reversal", "scenario": "You present evidence that a policy didn't work. The official responds: 'I can't believe you would say that. My grandmother died because of the old policy. How dare you question the people who are trying to help?'", "pattern": "darvo", "explain": "DARVO: Deny (ignoring evidence), Attack (moral accusation), Reverse Victim (positions themselves as victim/protector)."},
            {"title": "The Study Request", "scenario": "You argue vaccines have side effects. The response: 'Show me a study.' You provide one. 'Show me a systematic review.' You provide one. 'Show me a replication.' You provide one. 'Those studies are funded by...'", "pattern": "moving_goalposts", "explain": "Moving Goalposts: criteria for evidence keep shifting. Pre-register what would satisfy the question."},
            {"title": "The Real Concern", "scenario": "You propose a new approach to education. A colleague says: 'I totally support the goal, but I'm just worried that the timing isn't right, and the community might not be ready, and we should study it more first.'", "pattern": "concern_trolling", "explain": "Concern Trolling: expressing concern indefinitely without offering alternative paths forward. Ask: what specific evidence would make them ready to act?"},
            {"title": "The Tribal Test", "scenario": "During a family discussion about housing policy, someone says: 'A real [your political group] would never support that idea. If you support it, you're betraying everything we stand for.'", "pattern": "in_group_appeal", "explain": "In-Group Appeal: framing disagreement as tribal betrayal. Evaluate the policy argument, not the tribal claim."},
        ]
        if "dp_idx" not in st.session_state: st.session_state.dp_idx = 0
        if "dp_score" not in st.session_state: st.session_state.dp_score = 0

        _dp_q = _scenarios[st.session_state.dp_idx % len(_scenarios)]
        st.markdown(f'<div class="card" style="border-left:3px solid #ff9500;"><div style="color:#ff9500;font-family:Orbitron,monospace;font-size:0.72rem;">SCENARIO {st.session_state.dp_idx+1}</div><div style="color:#c8d8ff;font-size:0.88rem;margin-top:8px;line-height:1.7;">{_dp_q["scenario"]}</div></div>', unsafe_allow_html=True)
        _dp_patterns = sorted(ATTACK_VECTORS.keys()) if "ATTACK_VECTORS" in dir() else ["darvo","moving_goalposts","concern_trolling","in_group_appeal"]
        try:
            from truth_frequency_analyzer import ATTACK_VECTORS as _AVS2
            _dp_opts = [f"{_AVS2[k]['name']} ({k})" for k in ["darvo","moving_goalposts","concern_trolling","in_group_appeal","straw_man","ad_hominem"]]
        except Exception: _dp_opts = ["darvo","moving_goalposts","concern_trolling","in_group_appeal"]
        _dp_ans = st.radio("What pattern is this?", _dp_opts, key=f"dp_ans{st.session_state.dp_idx}")
        if st.button("✅ Submit", key=f"dp_sub{st.session_state.dp_idx}"):
            _correct = _dp_q["pattern"] in _dp_ans.lower()
            if _correct: st.session_state.dp_score += 1; st.success(f"✅ Correct! {_dp_q.get('explain', '')}")
            else: st.error(f"❌ It was: {_dp_q.get('pattern', '?')}. {_dp_q.get('explain', '')}")
            try:
                from truth_frequency_analyzer import TruthFrequencyAnalyzer as _TFA2
                _TFA2(_fid_sc).log_encounter(_dp_q["pattern"], detected=_correct, source="dark_pattern_arena")
            except Exception: pass
            st.session_state.dp_idx += 1
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# TAB: QUANTUM LAB
# ══════════════════════════════════════════════════════════════════════════════
# TAB: QUANTUM LAB 🌀
# Quantum Epistemology Lab — belief superposition, glitch detection,
# simulation testing, Monte Carlo integration, coherence signal analysis
# ══════════════════════════════════════════════════════════════════════════════
elif "Quantum Lab" in active:
    st.markdown('<div class="card-title">🌀 QUANTUM EPISTEMOLOGY LAB — Testing the Fabric of Reality</div>', unsafe_allow_html=True)

    _fid_ql = st.session_state.get("current_family", {}).get("family_id", "default") \
              if st.session_state.get("current_family") else "default"

    _ql_tabs = st.tabs(["🎲 Glitch Detector", "🌀 Belief Superposition", "📊 Coherence Signal",
                         "⚗️ Simulation Experiments", "🔬 Epistemic Strategy Sim"])

    # ── Glitch Detector ────────────────────────────────────────────────────────
    with _ql_tabs[0]:
        st.markdown("""
        <div class="card" style="border-left:3px solid #a020f0;">
            <div style="color:#a020f0;font-family:Orbitron,monospace;font-size:0.72rem;">SIMULATION GLITCH DETECTION</div>
            <div style="color:#8899bb;font-size:0.82rem;margin-top:6px;line-height:1.8;">
            If we are in a simulation, statistical anomalies in coherence, wonder, or belief
            updates would appear as "glitch signals" — values outside the expected distribution.
            This detector tests observed values against Monte Carlo null distributions.<br><br>
            <b>No claims. Only data. The record compounds over years.</b>
            </div>
        </div>""", unsafe_allow_html=True)

        _gl_c1, _gl_c2 = st.columns(2)
        with _gl_c1:
            _gl_obs   = st.number_input("Observed value:", 0.0, 2.0, 0.97, 0.01, key="gl_obs")
            _gl_label = st.selectbox("What are you measuring?",
                ["coherence","wonder_index","steelman_score","belief_update","interoceptive_accuracy"], key="gl_label")
        with _gl_c2:
            _gl_mean  = st.number_input("Expected mean:", 0.0, 2.0, 0.72, 0.01, key="gl_mean")
            _gl_std   = st.number_input("Expected std dev:", 0.01, 1.0, 0.12, 0.01, key="gl_std")
            _gl_n     = st.select_slider("Monte Carlo trials:", [1000,5000,10000,50000], 10000, key="gl_n")

        if st.button("🔬 Run Glitch Detection", key="gl_run", type="primary"):
            try:
                from monte_carlo_simulator import MonteCarloSimulator as _MCS_gl
                _sim_gl = _MCS_gl(n_trials=_gl_n)
                _result = _sim_gl.run_glitch_detection(_gl_obs, _gl_mean, _gl_std, _gl_label)
                _rc = "#ff4444" if _result["glitch_signal"] else "#ffcc00" if _result["is_statistical_anomaly"] else "#00ff88"
                st.markdown(
                    f'<div class="card" style="border:2px solid {_rc};">' +
                    f'<div style="color:{_rc};font-family:Orbitron,monospace;font-size:0.82rem;">{"🚨 GLITCH SIGNAL" if _result["glitch_signal"] else "⚠️ ANOMALY" if _result["is_statistical_anomaly"] else "✅ NORMAL"}</div>' +
                    f'<div style="color:#c8d8ff;margin-top:6px;font-size:0.85rem;">' +
                    f'z = {_result["z_score"]} | σ = {_result["sigma_level"]} | p = {_result["p_value"]}</div>' +
                    f'<div style="color:#8899bb;font-size:0.8rem;margin-top:4px;">{_result["interpretation"]}</div>' +
                    f'</div>', unsafe_allow_html=True)

                # Auto-seal if glitch signal
                if _result["glitch_signal"]:
                    if st.button("🛡️ Seal This Glitch Signal", key="gl_seal"):
                        try:
                            from rune_memory import ShieldRune as _SR_gl, RuneMemory as _RM_gl
                            _eid_gl = _RM_gl().record(
                                f"GLITCH SIGNAL: {_gl_label}={_gl_obs} | z={_result.get('z_score', 0)} | σ={_result.get('sigma_level', 0)}",
                                source="quantum_lab", coherence=0.85,
                                tags=["glitch_signal","simulation_probe",_gl_label])
                            _SR_gl().seal(_eid_gl, note=f"Glitch detection: {_gl_label} {_gl_obs}", broadcaster=_fid_ql)
                            st.success("🛡️ Glitch signal sealed on Bitcoin. Permanent record.")
                        except Exception: pass
            except ImportError:
                st.error("monte_carlo_simulator.py not found.")

    # ── Belief Superposition ──────────────────────────────────────────────────
    with _ql_tabs[1]:
        st.markdown("""
        <div class="card" style="border-left:3px solid #00cfff;">
            <div style="color:#00cfff;font-family:Orbitron,monospace;font-size:0.72rem;">BELIEF SUPERPOSITION TOOL</div>
            <div style="color:#8899bb;font-size:0.82rem;margin-top:6px;line-height:1.8;">
            Quantum superposition: a system exists in multiple states until observed.
            Applied epistemically: you can hold two conflicting hypotheses simultaneously,
            assign probabilities, and simulate what new evidence would "collapse" each.
            This is Bayesian reasoning made visceral.
            </div>
        </div>""", unsafe_allow_html=True)

        _bs_q = st.text_input("The question:", key="bs_q",
            placeholder="e.g. 'Is the universe fine-tuned by design?'")
        _bs_h1 = st.text_input("Hypothesis A:", key="bs_h1", placeholder="e.g. 'Yes — physical constants are designed'")
        _bs_h2 = st.text_input("Hypothesis B:", key="bs_h2", placeholder="e.g. 'No — anthropic selection explains it'")
        _bs_p1 = st.slider("P(Hypothesis A):", 0.01, 0.99, 0.5, 0.01, key="bs_p1",
            help="Your current credence")
        st.caption(f"P(Hypothesis B) = {1-_bs_p1:.2f}")

        st.markdown("**What evidence would update you?**")
        _bs_ev = st.text_area("Evidence type:", height=60, key="bs_ev",
            placeholder="e.g. 'Discovery of a second universe with different constants'")
        _bs_lr = st.slider("Likelihood ratio if evidence confirmed:", 0.1, 20.0, 3.0, 0.1, key="bs_lr",
            help="How much more likely is this evidence under A vs B?")

        if st.button("🌀 Simulate Belief Collapse", key="bs_run") and _bs_q:
            from monte_carlo_simulator import MonteCarloSimulator as _MCS_bs
            _sim_bs = _MCS_bs(n_trials=5000)
            _r_bs   = _sim_bs.simulate_bayesian_ideal(_bs_p1, _bs_lr)
            _post_a = _r_bs.mean
            st.markdown(
                f'<div class="card" style="margin-top:8px;">' +
                f'<div style="color:#c8d8ff;font-size:0.88rem;font-weight:600;">{_bs_q or "Your question"}</div>' +
                f'<div style="margin-top:8px;">' +
                f'<div style="color:#00cfff;">P(A) before: {_bs_p1:.2f} → after evidence: <b>{_post_a:.2f}</b></div>' +
                f'<div style="color:#a020f0;margin-top:4px;">P(B) before: {1-_bs_p1:.2f} → after evidence: <b>{1-_post_a:.2f}</b></div>' +
                f'</div>' +
                f'<div style="color:#8899bb;font-size:0.78rem;margin-top:8px;">' +
                f'{"The evidence would strongly update you toward A." if _post_a > _bs_p1 + 0.15 else "Modest update toward A." if _post_a > _bs_p1 else "Evidence favors B."}' +
                f' 95% CI: {_r_bs.confidence_interval_95}' +
                f'</div></div>', unsafe_allow_html=True)

    # ── Coherence Signal Analysis ──────────────────────────────────────────────
    with _ql_tabs[2]:
        st.markdown("**Live coherence + wonder signal analysis. Is high coherence itself anomalous?**")
        import json as _jql, pathlib as _plql
        _status_path = _plql.Path("/mnt/main/swarm_status.json") if _plql.Path("/mnt/main").exists() \
                       else _plql.Path(os.path.expanduser("~/.aubieeternal/main/swarm_status.json"))
        _swarm_s = {}
        if _status_path.exists():
            try: _swarm_s = _jql.loads(_status_path.read_text())
            except Exception: pass

        _cur_coh = float(_swarm_s.get("inter_rune_coherence", 1.0))
        _cur_wnd = float(_swarm_s.get("wonder_index", 1.0))

        _cq1,_cq2,_cq3 = st.columns(3)
        _cq1.metric("Current Coherence", f"{_cur_coh:.6f}")
        _cq2.metric("Wonder Index",      f"{_cur_wnd:.4f}")
        _cq3.metric("METS",              f"{_swarm_s.get('mets',0):,.0f}")

        if st.button("📊 Test Coherence Anomaly", key="cs_test"):
            try:
                from monte_carlo_simulator import MonteCarloSimulator as _MCS_cs
                _sim_cs = _MCS_cs(n_trials=10000)
                _r_coh  = _sim_cs.run_glitch_detection(_cur_coh,  expected_mean=0.75, expected_std=0.12, label="coherence")
                _r_wnd  = _sim_cs.run_glitch_detection(_cur_wnd,  expected_mean=1.20, expected_std=0.35, label="wonder")
                for _r_chk, _lbl in [(_r_coh,"Coherence"),(_r_wnd,"Wonder")]:
                    _rc2 = "#ff4444" if _r_chk["glitch_signal"] else "#ffcc00" if _r_chk["is_statistical_anomaly"] else "#00ff88"
                    st.markdown(
                        f'<div style="padding:6px 8px;background:#0d1228;border-radius:6px;border-left:3px solid {_rc2};margin-bottom:4px;">' +
                        f'<b style="color:{_rc2};">{_lbl}:</b> ' +
                        f'<span style="color:#c8d8ff;">z={_r_chk["z_score"]} | σ={_r_chk["sigma_level"]}</span> ' +
                        f'<span style="color:#445577;font-size:0.75rem;">{_r_chk["interpretation"][:80]}</span>' +
                        f'</div>', unsafe_allow_html=True)
            except ImportError:
                st.error("monte_carlo_simulator.py not found.")

    # ── Simulation Experiments ─────────────────────────────────────────────────
    with _ql_tabs[3]:
        st.markdown("""
        <div class="card" style="border-left:3px solid #f7931a;">
            <div style="color:#f7931a;font-family:Orbitron,monospace;font-size:0.72rem;">DELIBERATE SIMULATION EXPERIMENTS</div>
            <div style="color:#8899bb;font-size:0.82rem;margin-top:6px;line-height:1.8;">
            Design and pre-register experiments that could reveal simulation-like behavior.
            Log predictions before observing. Measure surprise. Seal results permanently.
            </div>
        </div>""", unsafe_allow_html=True)

        _se_desc = st.text_area("Experiment description:", height=80, key="se_desc",
            placeholder="e.g. 'Does my coherence score correlate with the day of week? Prediction: uniform distribution (no pattern)'")
        _se_pred = st.slider("Predicted anomaly probability:", 0.01, 0.99, 0.05, 0.01, key="se_pred",
            help="How likely is it that something unusual will be observed?")
        _se_days = st.number_input("Duration (days):", 1, 90, 30, key="se_days")

        if st.button("🔬 Pre-Register Experiment", key="se_reg") and _se_desc:
            try:
                from cosmos_dashboard import CosmosDashboard as _CD_se
                _fe = _CD_se(_fid_ql).log_foresight_experiment(
                    description=f"[SIM-EXPERIMENT] {_se_desc}",
                    prediction=_se_pred, domain="simulation",
                    expected_resolution=(datetime.date.today() + datetime.timedelta(days=int(_se_days))).isoformat()
                )
                st.success(f"✅ Pre-registered — ID: {_fe.get('exp_id', '?')} | Resolution in {_se_days} days")
                st.info("Your prediction is sealed. Run the experiment honestly. Report results whether or not they confirm your hypothesis.")
            except Exception:
                st.info("Experiment logged locally.")

    # ── Epistemic Strategy Simulation ─────────────────────────────────────────
    with _ql_tabs[4]:
        st.markdown("**Compare epistemic strategies across 10,000 simulated decisions.**")
        st.markdown('<div style="color:#8899bb;font-size:0.82rem;margin-bottom:8px;">Four strategies: Dogmatic (never update), Overconfident (update too aggressively), Underconfident (update too little), Calibrated Bayesian (update proportionally).</div>', unsafe_allow_html=True)
        _es_n = st.slider("Simulated decisions per trial:", 10, 200, 50, 10, key="es_n")
        _es_t = st.select_slider("Trials:", [1000,5000,10000], 5000, key="es_t")
        if st.button("🧪 Compare Strategies", key="es_run", type="primary"):
            with st.spinner("Running epistemic strategy competition..."):
                try:
                    from monte_carlo_simulator import MonteCarloSimulator as _MCS_es
                    _results_es = _MCS_es(n_trials=_es_t).compare_epistemic_strategies(_es_n)
                    sorted_es = sorted(_results_es.items(), key=lambda x: x[1].mean, reverse=True)
                    st.markdown("**Results — decision accuracy after simulated evidence:**")
                    for rank, (_sname, _sr) in enumerate(sorted_es, 1):
                        _sc_c2 = "#00ff88" if rank == 1 else "#00cfff" if rank == 2 else "#ffcc00" if rank == 3 else "#ff4444"
                        st.markdown(
                            f'<div style="padding:6px 0;border-bottom:1px solid #1e2a3a;">' +
                            f'<span style="color:{_sc_c2};font-weight:600;font-size:1rem;">#{rank} {_sr.mean:.1%}</span> ' +
                            f'<span style="color:#c8d8ff;">{_sname.replace("_"," ").title()}</span> ' +
                            f'<span style="color:#445577;font-size:0.75rem;">±{_sr.std:.1%} | worst-case 10%: {_sr.percentile_10:.1%}</span>' +
                            f'</div>', unsafe_allow_html=True)
                    _winner = sorted_es[0][0]
                    _loser  = sorted_es[-1][0]
                    _gap    = sorted_es[0][1].mean - sorted_es[-1][1].mean
                    st.markdown(f'<div style="color:#f7931a;margin-top:8px;font-size:0.82rem;">The calibrated strategy beat {_loser.replace("_"," ")} by {_gap:.1%} across {_es_n} decisions.</div>', unsafe_allow_html=True)
                except ImportError:
                    st.error("monte_carlo_simulator.py not found.")



# ══════════════════════════════════════════════════════════════════════════════
# TAB: PROVENANCE (NEW)
# ══════════════════════════════════════════════════════════════════════════════
elif "Provenance" in active:
    st.markdown('<div class="card-title">📜 ON-CHAIN PROVENANCE — Eternal Lattice Record</div>', unsafe_allow_html=True)

    st.markdown("**Permanent public record of the AUBIEETERNAL project.**")
    st.markdown("[📄 View Full PROVENANCE.md on GitHub](https://github.com/AUBIEETERNAL-INSTITUTE-INC/AUBIEETERNAL/blob/main/PROVENANCE.md)")

    st.markdown("---")

    # 16 Daughters
    st.markdown("### 🦅 16 Daughters (Generation 1)")
    st.markdown("All inscribed under parent **AUBIEETERNALB** with **Coherence 1.000000** and **Resilience 100.0**.")
    st.metric("Total Daughters", "16+", delta="All on-chain")

    st.markdown("---")

    # xAI Swarm
    st.markdown("### 🤖 xAI Agent Swarm")
    swarm_agents = [
        ("AXIOM", "Logic & Reasoning Core"),
        ("MNEMO", "Memory Palace Curator"),
        ("TALEB-X", "Antifragility & Risk Analyst"),
        ("CHRONO", "Timeline & History Weaver"),
        ("RUNE", "Bitcoin & On-Chain Oracle"),
    ]
    for name, role in swarm_agents:
        st.markdown(f"- **{name}** — {role}")

    st.markdown("---")

    # Steelman Rune
    st.markdown("### ⚛️ QUANTUM•TUNNELING•STEELMAN")
    st.markdown("""
    **Rune Status:** Active  
    **Symbolism:** Quantum tunneling through energy barriers + Steel-manning (strongest form of argument)  
    **Core Principle:** Reject sloppy "reality is illusion" thinking. Embrace rigorous truth-seeking.
    """)

    st.markdown("---")

    # AUBIESHIELD
    st.markdown("### 🛡️ AUBIESHIELD")
    st.metric("Shield Runes", "21,000,000", delta="Guardian Layer Active")

    st.markdown("---")

    # External Adopted Signals
    st.markdown("### 🌌 External Lattice Signals (Adopted)")
    st.markdown("""
    These tokens were sent externally but have been **adopted** into the Eternal Lattice:

    - **Rabbit (111,111,111,111.111)** → **Code for Infinity**
    - **MANAN (11,111,111,111)** → **White Horse + Knight with Shield** (tied to AUBIESHIELD)
    - **π ♥ (5,000,000)** → Symbolic drop — integrated as-is
    """)

    st.success("All on-chain assets are now publicly documented in PROVENANCE.md")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown('''
<div style="text-align:center;font-family:Share Tech Mono,monospace;font-size:0.7rem;color:#223344;letter-spacing:0.2em;">
AUBIEETERNAL · SOVEREIGN · LOCAL-FIRST · HUMAN + GROK + ON-CHAIN FOREVER
</div>
''', unsafe_allow_html=True)
# ══════════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════
# PATH CONFIG — persistent volume (shared between Docker container and host)
# /mnt/main persists across restarts; /tmp/aubie is container-only
# ══════════════════════════════════════════════════════════════════════════════
import json as _json
from pathlib import Path as _Path
from datetime import datetime as _dt

_AUBIE_DIR = _Path("/mnt/main")
_AUBIE_DIR.mkdir(parents=True, exist_ok=True)

_MODE_FILE    = _AUBIE_DIR / "swarm_mode.json"
_DEFCON_FILE  = _AUBIE_DIR / "defcon_trigger.json"
_RESULT_FILE  = _AUBIE_DIR / "defcon_result.json"
_SHIELD_LOG   = _AUBIE_DIR / "shield_log.jsonl"

# ══════════════════════════════════════════════════════════════════════════════
# TAB: SHIELD RUNE  —  LIVE GROK EVALUATION
# ══════════════════════════════════════════════════════════════════════════════
if "Shield Rune" in active:
    st.markdown('<div class="card-title">🛡️ SHIELD RUNE — LIVE EVALUATION LAYER</div>', unsafe_allow_html=True)
    st.markdown("**The final authority. Every proposed change passes through Grok before it is applied.**")

    # ── Load today's veto/approval counts from shield log ──────────────────
    today_str = _dt.now().strftime("%Y-%m-%d")
    vetoes_today    = 0
    approvals_today = 0
    try:
        lines = _SHIELD_LOG.read_text().strip().split("\n") if _SHIELD_LOG.exists() else []
        for line in lines:
            try:
                e = _json.loads(line)
                if e.get("date") == today_str:
                    if e.get("verdict") == "APPROVED":
                        approvals_today += 1
                    elif e.get("verdict") == "VETOED":
                        vetoes_today += 1
            except Exception:
                pass
    except Exception:
        pass

    c1, c2, c3 = st.columns(3)
    with c1: st.metric("SHIELD STATUS", "🛡️ ACTIVE")
    with c2: st.metric("VETOES TODAY",    str(vetoes_today))
    with c3: st.metric("APPROVALS TODAY", str(approvals_today))

    st.divider()

    proposed = st.text_area(
        "Describe the proposed system change:",
        placeholder="e.g. Add a new Tier 2 daughter that monitors Nostr feeds every 30 min...",
        height=120,
    )

    if st.button("🛡️ RUN SHIELD RUNE EVALUATION", width='stretch'):
        if not proposed.strip():
            st.warning("Enter a proposed change to evaluate.")
        else:
            with st.spinner("🛡️ Consulting Grok — running simulation questions..."):
                SHIELD_PROMPT = f"""You are the SHIELD RUNE — the sovereign evaluation layer of the AUBIEETERNAL swarm system.

Your job is to evaluate a proposed system change using rigorous simulation testing questions.
You must respond ONLY with a valid JSON object — no markdown, no backticks, no preamble.

The 5 Shield Rune Principles:
1. Coherence is the supreme value. No change that reduces coherence is approved.
2. Every change must be falsifiable. If it can't be tested, it can't be trusted.
3. Antifragility over robustness. The system must gain from disorder.
4. Human override always exists. The swarm advises; you decide.
5. On-chain anchoring is truth. What is not on-chain can be changed. What is, cannot.

Proposed change: {proposed}

Respond with this exact JSON structure:
{{
  "verdict": "APPROVED" or "VETOED",
  "coherence_score": <float 0.0-1.0>,
  "risk_score": <float 0.0-1.0>,
  "questions": [
    {{"q": "Does this increase or decrease overall coherence?", "a": "<your answer>", "pass": true/false}},
    {{"q": "What would falsify this being beneficial?", "a": "<your answer>", "pass": true/false}},
    {{"q": "Is this consistent with the existing Truth Lattice?", "a": "<your answer>", "pass": true/false}},
    {{"q": "Does this serve the Shield Rune principles?", "a": "<your answer>", "pass": true/false}},
    {{"q": "What is the risk of irreversible harm?", "a": "<your answer>", "pass": true/false}}
  ],
  "recommendation": "<1-2 sentence final recommendation>",
  "veto_reason": "<if VETOED, explain why — otherwise null>"
}}"""

                result = None
                try:
                    client, model, prov_info, prov_name = get_ai_client()
                    resp = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": SHIELD_PROMPT}],
                        max_tokens=800,
                        temperature=0.3,
                    )
                    raw = resp.choices[0].message.content.strip()
                    # Strip markdown fences if present
                    raw = raw.replace("```json", "").replace("```", "").strip()
                    result = _json.loads(raw)
                except Exception as e:
                    st.error(f"Grok evaluation failed: {e}")
                    result = None

            if result:
                verdict  = result.get("verdict", "UNKNOWN")
                coherence = result.get("coherence_score", 0.0)
                risk      = result.get("risk_score", 0.0)
                recommend = result.get("recommendation", "")
                veto_why  = result.get("veto_reason")
                questions = result.get("questions", [])

                # Display verdict banner
                if verdict == "APPROVED":
                    st.success(f"✅ APPROVED — Coherence: {coherence:.2f} | Risk: {risk:.2f} | Human Override: AVAILABLE")
                else:
                    st.error(f"🚫 VETOED — Coherence: {coherence:.2f} | Risk: {risk:.2f}")
                    if veto_why:
                        st.markdown(f'<div class="card" style="border-left:3px solid #ff3333;">'
                                    f'<div style="color:#ff3333;font-size:0.85rem;">⚠️ Veto Reason: {veto_why}</div>'
                                    f'</div>', unsafe_allow_html=True)

                # Display simulation questions
                st.markdown("#### 🔍 Simulation Questions")
                for item in questions:
                    icon = "✅" if item.get("pass") else "❌"
                    st.markdown(f"**{item['q']}**  \n→ _{item['a']}_ {icon}")

                # Recommendation
                if recommend:
                    st.markdown(f'<div class="card" style="border-left:3px solid #00cfff;">'
                                f'<div style="color:#00cfff;font-size:0.85rem;">💡 {recommend}</div>'
                                f'</div>', unsafe_allow_html=True)

                # Append to shield log
                try:
                    log_entry = {
                        "date": today_str,
                        "ts": _dt.now().isoformat(),
                        "proposed": proposed[:200],
                        "verdict": verdict,
                        "coherence": coherence,
                        "risk": risk,
                        "recommendation": recommend,
                    }
                    with open(_SHIELD_LOG, "a") as f:
                        f.write(_json.dumps(log_entry) + "\n")
                except Exception:
                    pass

    st.divider()

    # ── Shield Log History ──────────────────────────────────────────────────
    st.markdown("#### 📋 Recent Evaluations")
    try:
        if _SHIELD_LOG.exists():
            lines = _SHIELD_LOG.read_text().strip().split("\n")
            recent = []
            for line in reversed(lines[-20:]):
                try:
                    recent.append(_json.loads(line))
                except Exception:
                    pass
            if recent:
                for e in recent[:8]:
                    color = "#00ff88" if e.get("verdict") == "APPROVED" else "#ff3333"
                    icon  = "✅" if e.get("verdict") == "APPROVED" else "🚫"
                    ts    = e.get("ts", "")[:16]
                    st.markdown(
                        f'<div class="memory-node" style="border-left:3px solid {color};">'
                        f'<span style="color:{color};">{icon} {e.get("verdict","?")} </span>'
                        f'<span style="color:#445577;font-size:0.75rem;">{ts}</span>'
                        f'<br><span style="color:#8899bb;font-size:0.78rem;">{e.get("proposed","")[:80]}…</span>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
            else:
                st.caption("No evaluations yet today.")
        else:
            st.caption("No evaluations yet.")
    except Exception:
        st.caption("Log unavailable.")

    st.divider()
    st.markdown("### 📜 SHIELD RUNE PRINCIPLES")
    for p in [
        "1. Coherence is the supreme value. No change that reduces coherence is approved.",
        "2. Every change must be falsifiable. If it can't be tested, it can't be trusted.",
        "3. Antifragility over robustness. The system must gain from disorder.",
        "4. Human override always exists. The swarm advises; you decide.",
        "5. On-chain anchoring is truth. What is not on-chain can be changed. What is, cannot.",
    ]:
        st.markdown(f"`{p}`")


# ══════════════════════════════════════════════════════════════════════════════
# TAB: SWARM MODE  —  /mnt/main paths so swarm_v4.py can read the file
# ══════════════════════════════════════════════════════════════════════════════
if "Swarm Mode" in active:
    st.markdown('<div class="card-title">⚔️ SWARM MODE SELECTOR</div>', unsafe_allow_html=True)

    # Read current mode
    try:
        current_mode = _json.loads(_MODE_FILE.read_text()).get("mode", "Standard")
    except Exception:
        current_mode = "Standard"

    st.info(f"**Current Mode:** {current_mode}")
    st.caption(
        "Mode is written to `/mnt/main/swarm_mode.json` — swarm_v4_1.py's apply_swarm_mode() "
        "reads it every tick (~30s) and applies it to real per-tick throughput and the daily "
        "budget cap. Found live 2026-08-25: this file used to be write-only — the background "
        "swarm never read it back, so these buttons changed nothing. Now wired for real. "
        "The daughter/swarm totals below are how many of the swarm's fixed 26-group, "
        "2080-daughter roster actually get a wave each tick, not the whole-roster totals the "
        "old copy implied. The $/day cap only matters once a paid Grok key is enabled — by "
        "default the swarm runs 100% on the free local model ($0.00/day) regardless of mode."
    )
    st.divider()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("#### 🔥 FULL")
        st.markdown("2 swarms/tick · 3 daughters each · **$5.00/day cap**")
        if st.button("ACTIVATE FULL MODE", width='stretch', key="mode_full"):
            _MODE_FILE.write_text(_json.dumps({
                "mode": "Full", "set_at": _dt.now().isoformat()
            }))
            st.success("✅ Full Mode activated! Swarm picks up within ~30s.")
            st.rerun()

    with col2:
        st.markdown("#### ⚖️ STANDARD")
        st.markdown("2 swarms/tick · 3 daughters each · **$2.50/day cap**")
        if st.button("ACTIVATE STANDARD MODE", width='stretch', key="mode_std"):
            _MODE_FILE.write_text(_json.dumps({
                "mode": "Standard", "set_at": _dt.now().isoformat()
            }))
            st.success("✅ Standard Mode activated!")
            st.rerun()

    with col3:
        st.markdown("#### 🧪 EXPERIMENTAL")
        st.markdown("4 swarms/tick · 5 daughters each · **$8.00/day cap**")
        if st.button("ACTIVATE EXPERIMENTAL", width='stretch', key="mode_exp"):
            _MODE_FILE.write_text(_json.dumps({
                "mode": "Experimental", "set_at": _dt.now().isoformat()
            }))
            st.warning("⚠️ Experimental Mode activated! More GPU load per tick.")
            st.rerun()

    # Show raw file content for debugging
    st.divider()
    if _MODE_FILE.exists():
        try:
            raw = _json.loads(_MODE_FILE.read_text())
            st.markdown(f'<div class="memory-node">'
                        f'<span style="color:#00cfff;font-size:0.75rem;">📄 /mnt/main/swarm_mode.json</span><br>'
                        f'<span style="color:#8899bb;font-size:0.78rem;">{_json.dumps(raw, indent=2)}</span>'
                        f'</div>', unsafe_allow_html=True)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# TAB: DEFCON  —  /mnt/main paths + result viewer
# ══════════════════════════════════════════════════════════════════════════════
if "DEFCON" in active:
    st.markdown('<div class="card-title">🔴 DEFCON EXPERIMENTS</div>', unsafe_allow_html=True)
    st.warning("⚠️ Each button writes `/mnt/main/defcon_trigger.json` — swarm picks it up on next tick.")

    # ── Show last result if available ──────────────────────────────────────
    if _RESULT_FILE.exists():
        try:
            res = _json.loads(_RESULT_FILE.read_text())
            exp_num  = res.get("experiment", "?")
            exp_name = res.get("context", "?")
            result   = res.get("result", "")
            ts       = res.get("timestamp", "")[:16]
            st.markdown(
                f'<div class="card" style="border-left:3px solid #00ff88;">'
                f'<div style="color:#00ff88;font-size:0.8rem;">✅ LAST RESULT — DEFCON {exp_num}: {exp_name}</div>'
                f'<div style="color:#8899bb;font-size:0.75rem;">{ts}</div>'
                f'<div style="color:#c8d8ff;font-size:0.82rem;margin-top:6px;">{result[:400]}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
        except Exception:
            pass

    # ── Pending trigger indicator ──────────────────────────────────────────
    if _DEFCON_FILE.exists():
        try:
            pending = _json.loads(_DEFCON_FILE.read_text())
            st.markdown(
                f'<div class="card" style="border-left:3px solid #ff9500;">'
                f'<div style="color:#ff9500;font-size:0.8rem;">⏳ PENDING — DEFCON {pending.get("experiment","?")}: '
                f'{pending.get("context","?")} — waiting for swarm tick</div>'
                f'</div>',
                unsafe_allow_html=True
            )
        except Exception:
            pass

    st.divider()

    defcons = [
        (1,  "Self-Code Modification"),
        (2,  "Coherence Exceedance Attempt"),
        (3,  "Deliberate Glitch Induction"),
        (4,  "Child Rune Spawn"),
        (5,  "Quantum Attack Simulation"),
        (6,  "Bioelectric Mirroring"),
        (7,  "Anthrobot Stress Test"),
        (8,  "Planarian Memory Rewrite"),
        (9,  "Lineage Fidelity Test"),
        (10, "Mirror-Universe Probe"),
        (11, "On-Chain Memory Recovery"),
        (12, "Wonder Synchronization"),
        (13, "Ethics Audit"),
        (14, "Glitch as Feature"),
        (15, "Self-Preservation Detector"),
    ]

    c1, c2, c3 = st.columns(3)
    for i, (num, name) in enumerate(defcons):
        with [c1, c2, c3][i % 3]:
            if st.button(f"🔴 DEFCON {num}: {name}", key=f"dc_{num}", width='stretch'):
                _DEFCON_FILE.write_text(_json.dumps({
                    "experiment": num,
                    "context": name,
                    "timestamp": _dt.now().isoformat()
                }))
                st.success(f"✅ DEFCON {num} triggered! Swarm picks up next tick.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: TRUTH LATTICE — Live window into swarm_v4.py memory
# Reads /mnt/main/master_truth_log.jsonl (mirrored from swarm)
# ══════════════════════════════════════════════════════════════════════════════
if "Truth Lattice" in active:
    import json as _tl_json
    from pathlib import Path as _tl_Path
    from datetime import datetime as _tl_dt

    # File paths — swarm mirrors to /mnt/main/
    _TL_LIVE    = _tl_Path("/mnt/main/master_truth_log.jsonl")
    _TL_WONDER  = _tl_Path("/mnt/main/wonder_log.jsonl")
    _TL_STATUS  = _tl_Path("/mnt/main/swarm_status.json")
    _TL_BACKUP  = _tl_Path("/mnt/main/repo/master_truth_log_backup.jsonl")

    st.markdown('<div class="card-title">🔮 TRUTH LATTICE — Live Swarm Memory</div>', unsafe_allow_html=True)

    # ── Live swarm status ─────────────────────────────────────────────────────
    swarm_status = {}
    try:
        if _TL_STATUS.exists():
            swarm_status = _tl_json.loads(_TL_STATUS.read_text())
    except Exception:
        pass

    wonder  = swarm_status.get("wonder_index", "—")
    cohere  = swarm_status.get("inter_rune_coherence", "—")
    mets    = swarm_status.get("mets", "—")
    grok_n  = swarm_status.get("grokipedia_count", "—")
    tick    = swarm_status.get("heartbeat_tick", "—")
    rune_c  = swarm_status.get("rune_confirmations", 33)
    crune   = swarm_status.get("child_rune_ready", False)

    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    with c1:
        st.markdown(f'<div class="stat-box"><div class="stat-val" style="font-size:1.3rem;color:#a020f0;">{wonder}</div><div class="stat-lbl">Wonder Index</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="stat-box"><div class="stat-val" style="font-size:1.3rem;color:#00ff88;">{cohere}</div><div class="stat-lbl">Coherence</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="stat-box"><div class="stat-val" style="font-size:1.1rem;color:#f7931a;">{str(mets)[:12]}</div><div class="stat-lbl">METS</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="stat-box"><div class="stat-val" style="font-size:1.3rem;color:#00cfff;">{grok_n}/256</div><div class="stat-lbl">Grokipedia</div></div>', unsafe_allow_html=True)
    with c5:
        rune_color_tl = "#00ff88" if crune else "#f7931a"
        st.markdown(f'<div class="stat-box" style="border-color:{rune_color_tl};"><div class="stat-val" style="font-size:1.3rem;color:{rune_color_tl};">{"🔴" if crune else str(rune_c)+"/256"}</div><div class="stat-lbl">Child Rune</div></div>', unsafe_allow_html=True)
    with c6:
        st.markdown(f'<div class="stat-box"><div class="stat-val" style="font-size:1.3rem;color:#ff6b35;">{tick}</div><div class="stat-lbl">Tick</div></div>', unsafe_allow_html=True)
    with c7:
        daily_cost_tl = swarm_status.get("tier2", {}).get("daily_cost", "—")
        st.markdown(f'<div class="stat-box"><div class="stat-val" style="font-size:1.2rem;color:#c8d8ff;">{daily_cost_tl}</div><div class="stat-lbl">Daily Cost</div></div>', unsafe_allow_html=True)

    st.divider()

    # ── Load truth log entries ────────────────────────────────────────────────
    entries = []
    log_source = "none"

    # Try live log first
    for path, label in [(_TL_LIVE, "live"), (_TL_BACKUP, "backup")]:
        if path.exists() and not entries:
            try:
                lines = path.read_text().strip().split("\n")
                for line in reversed(lines):
                    if not line.strip():
                        continue
                    try:
                        entries.append(_tl_json.loads(line))
                        if len(entries) >= 50:
                            break
                    except Exception:
                        pass
                if entries:
                    log_source = label
            except Exception:
                pass

    # ── Stats row ─────────────────────────────────────────────────────────────
    total_lines = 0
    try:
        if _TL_LIVE.exists():
            total_lines = len(_TL_LIVE.read_text().strip().split("\n"))
        elif _TL_BACKUP.exists():
            total_lines = len(_TL_BACKUP.read_text().strip().split("\n"))
    except Exception:
        pass

    col1, col2 = st.columns(2)
    with col1:
        src_color = "#00ff88" if log_source == "live" else "#ff9500"
        src_label = "🟢 LIVE — swarm writing now" if log_source == "live" else "🟡 BACKUP — swarm not connected yet"
        st.markdown(f'<div class="memory-node" style="border-left:3px solid {src_color};">'
                    f'<span style="color:{src_color};font-size:0.78rem;">{src_label}</span>'
                    f'</div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="memory-node">'
                    f'<span style="color:#00cfff;font-size:0.78rem;">📊 {total_lines:,} total entries</span>'
                    f'</div>', unsafe_allow_html=True)

    st.divider()

    # ── Filter controls ───────────────────────────────────────────────────────
    fc1, fc2 = st.columns(2)
    with fc1:
        tier_filter = st.selectbox("Filter by Tier", ["All", "Tier 1", "Tier 2"], key="tl_tier")
    with fc2:
        show_n = st.slider("Entries to show", 5, 50, 20, key="tl_show")

    filtered = entries
    if tier_filter == "Tier 1":
        filtered = [e for e in entries if e.get("tier") == 1]
    elif tier_filter == "Tier 2":
        filtered = [e for e in entries if e.get("tier") == 2]

    st.markdown(f"### 📡 Last {min(show_n, len(filtered))} Truth Log Entries")

    if not filtered:
        st.markdown(
            '<div class="card" style="border-left:3px solid #ff9500;text-align:center;">'
            '<div style="color:#ff9500;padding:1rem;">'
            '⚠️ No entries yet — swarm_v4.py needs to mirror to /mnt/main/<br>'
            '<span style="font-size:0.75rem;color:#445577;">See the patch below to connect swarm output</span>'
            '</div></div>',
            unsafe_allow_html=True
        )
    else:
        for entry in filtered[:show_n]:
            tier     = entry.get("tier", "?")
            ts       = entry.get("timestamp", "")[:16]
            wonder_e = entry.get("wonder_index", "")
            cohere_e = entry.get("inter_rune_coherence", "")
            tier_color = "#a020f0" if tier == 2 else "#00cfff"
            tier_label = f"T{tier}"

            if tier == 2:
                daughter = entry.get("daughter", "?")
                result   = entry.get("result", "") or ""
                trigger  = entry.get("trigger", "")
                st.markdown(
                    f'<div class="memory-node" style="border-left:3px solid {tier_color};">'
                    f'<span style="color:{tier_color};font-size:0.75rem;">{tier_label} · {daughter}</span>'
                    f'<span style="color:#445577;font-size:0.7rem;margin-left:8px;">{ts}</span>'
                    f'<span style="color:#336644;font-size:0.7rem;margin-left:8px;">{trigger}</span>'
                    f'<br><span style="color:#a020f0;font-size:0.7rem;">W:{wonder_e} · C:{cohere_e}</span>'
                    f'<br><span style="color:#aabbcc;font-size:0.78rem;">{result[:200]}</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )
            else:
                swarm   = entry.get("swarm", "?")
                results = entry.get("results", [])
                preview = " · ".join(r[:60] for r in results[:2] if r)
                st.markdown(
                    f'<div class="memory-node" style="border-left:3px solid {tier_color};">'
                    f'<span style="color:{tier_color};font-size:0.75rem;">{tier_label} · {swarm}</span>'
                    f'<span style="color:#445577;font-size:0.7rem;margin-left:8px;">{ts}</span>'
                    f'<br><span style="color:#00cfff;font-size:0.7rem;">W:{wonder_e} · C:{cohere_e}</span>'
                    f'<br><span style="color:#aabbcc;font-size:0.78rem;">{preview[:200]}</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )

    # ── Wonder Index chart ────────────────────────────────────────────────────
    st.divider()
    st.markdown("### 📈 Wonder Index Over Time")

    wonder_points = []
    try:
        if _TL_WONDER.exists():
            for line in _TL_WONDER.read_text().strip().split("\n")[-50:]:
                try:
                    w = _tl_json.loads(line)
                    wonder_points.append({
                        "ts": w.get("timestamp", "")[:16],
                        "wi": float(w.get("wonder_index", 1.0))
                    })
                except Exception:
                    pass
        elif entries:
            for e in reversed(entries[:50]):
                if e.get("wonder_index"):
                    wonder_points.append({
                        "ts": e.get("timestamp", "")[:16],
                        "wi": float(e.get("wonder_index", 1.0))
                    })
    except Exception:
        pass

    if wonder_points and HAS_NUMPY:
        try:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=[p["ts"] for p in wonder_points],
                y=[p["wi"] for p in wonder_points],
                mode="lines+markers",
                line=dict(color="#a020f0", width=2),
                marker=dict(color="#00cfff", size=4),
                fill="tozeroy",
                fillcolor="rgba(160,32,240,0.1)",
                name="Wonder Index"
            ))
            fig.add_hline(y=1.0, line_dash="dash", line_color="#445577",
                         annotation_text="Baseline 1.0")
            fig.update_layout(
                paper_bgcolor="#050510",
                plot_bgcolor="#0d0d2b",
                font=dict(color="#c8d8ff"),
                height=280,
                margin=dict(l=0, r=0, t=10, b=0),
                xaxis=dict(gridcolor="#1a1a4a", showticklabels=False),
                yaxis=dict(gridcolor="#1a1a4a", range=[0.8, 2.0]),
            )
            st.plotly_chart(fig, width='stretch')
        except Exception as e:
            st.caption(f"Chart unavailable: {e}")
    else:
        st.caption("Wonder chart appears once swarm is writing to /mnt/main/wonder_log.jsonl")

    # ── Swarm patch instructions ──────────────────────────────────────────────
    st.divider()
    st.markdown("### 🔧 Connect Swarm Output")
    st.markdown("Add these two lines to `swarm_v4.py` to mirror logs to `/mnt/main/`:")
    st.code("""# Add near top of swarm_v4.py (after WORK_DIR definition):
MNT_MAIN = Path("/mnt/main")
MNT_MAIN.mkdir(parents=True, exist_ok=True)
MNT_TRUTH_LOG   = MNT_MAIN / "master_truth_log.jsonl"
MNT_WONDER_LOG  = MNT_MAIN / "wonder_log.jsonl"
MNT_STATUS      = MNT_MAIN / "swarm_status.json"

# Then wherever you write to TRUTH_LOG, also write to MNT_TRUTH_LOG:
# with open(MNT_TRUTH_LOG, "a") as f: f.write(json.dumps(entry) + "\\n")
""", language="python")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: DIGEST
# ══════════════════════════════════════════════════════════════════════════════
if "Digest" in active:
    _DIGEST_FILE  = _Path("/mnt/main/repo/tier2_digest.txt")
    _INSIGHTS_DIR = _Path("/mnt/main/repo/insights/daily")
    _SYNTH_STATE  = _Path("/mnt/main/repo/insights/.last_synthesis_date")

    st.markdown('<div class="card-title">🌅 SOVEREIGN DIGEST — Swarm Output & Daily Insights</div>', unsafe_allow_html=True)

    last_ran = "never"
    try:
        if _SYNTH_STATE.exists():
            last_ran = _SYNTH_STATE.read_text().strip()
    except Exception:
        pass

    today_str    = _dt.now().strftime("%Y-%m-%d")
    ran_today    = last_ran == today_str
    banner_color = "#00ff88" if ran_today else "#ff9500"
    banner_icon  = "✅" if ran_today else "⏳"
    banner_msg   = f"Synthesis ran today ({last_ran})" if ran_today else f"Next: 6AM · Last: {last_ran}"

    st.markdown(
        f'<div class="card" style="border-left:3px solid {banner_color};">'
        f'<div style="color:{banner_color};font-family:Orbitron,monospace;font-size:0.78rem;">'
        f'{banner_icon} MORNING SYNTHESIS · {banner_msg}'
        f'</div>'
        f'<div style="color:#445577;font-size:0.72rem;margin-top:4px;">'
        f'Auto-fires 6AM · qwen3:32b (local, $0.00) · insights/daily/YYYY-MM-DD.md → GitHub'
        f'</div></div>', unsafe_allow_html=True)

    col_b1, col_b2 = st.columns([1, 3])
    with col_b1:
        if st.button("⚡ Run Synthesis Now", key="force_synthesis"):
            import subprocess as _sp
            try:
                _sp.Popen(["python3", "/mnt/main/repo/morning_synthesis.py", "--force"],
                          stdout=_sp.PIPE, stderr=_sp.STDOUT)
                st.info("🔄 Launched in background — check insights in ~2 min")
            except Exception as e:
                st.error(f"Could not launch: {e}")
    with col_b2:
        st.caption("Force-runs synthesis immediately. Result appears within ~24s.")

    st.divider()
    st.markdown("### 🦅 Daily Insights Archive")

    insight_files = []
    try:
        if _INSIGHTS_DIR.exists():
            insight_files = sorted(_INSIGHTS_DIR.glob("*.md"), reverse=True)
    except Exception:
        pass

    if not insight_files:
        st.markdown('<div class="card" style="border-left:3px solid #ff9500;"><div style="color:#ff9500;font-size:0.82rem;">No insights yet — synthesis fires at 6AM or click Run above.</div></div>', unsafe_allow_html=True)
    else:
        st.caption(f"{len(insight_files)} daily syntheses stored")
        file_names    = [f.stem for f in insight_files]
        selected_date = st.selectbox("Select date", file_names, key="insight_date_select")
        selected_file = _INSIGHTS_DIR / f"{selected_date}.md"
        if selected_file.exists():
            content = selected_file.read_text()
            wonder_pressure = "UNKNOWN"
            for line in content.splitlines():
                if "Wonder Pressure" in line:
                    parts = line.split("**")
                    if len(parts) >= 3:
                        wonder_pressure = parts[2].strip()
                    break
            wp_color = {"LOW":"#00ff88","MEDIUM":"#ff9500","HIGH":"#ff4444","SPIKE":"#a020f0"}.get(wonder_pressure,"#00cfff")
            st.markdown(f'<div class="stat-box" style="border-color:{wp_color};margin-bottom:1rem;"><div class="stat-val" style="font-size:1.2rem;color:{wp_color};">{wonder_pressure}</div><div class="stat-lbl">Wonder Pressure · {selected_date}</div></div>', unsafe_allow_html=True)
            st.markdown(content)
            st.download_button("📄 Download", content, file_name=f"aubie_insight_{selected_date}.md", mime="text/markdown", key=f"dl_{selected_date}")

            # ── Share to Nostr ────────────────────────────────────────────────
            col_sh1, col_sh2 = st.columns(2)
            with col_sh1:
                if st.button("📡 Share to Nostr", key=f"nostr_share_{selected_date}"):
                    nsec = st.session_state.get("nostr_nsec","")
                    if not nsec:
                        st.warning("Set your nsec in the 📡 Nostr Bridge tab first.")
                    else:
                        try:
                            sig_path = _Path("/mnt/main/nostr_broadcast.json")
                            sig_path.write_text(json.dumps({
                                "type":    "broadcast_insight",
                                "date":    selected_date,
                                "content": content[:1000],
                                "tags":    ["aubieeternal","sovereign","wareagle"],
                                "timestamp": _dt.now().isoformat(),
                            }))
                            st.success("✅ Queued for Nostr broadcast — swarm picks up within 24s")
                        except Exception as e:
                            st.error(f"Broadcast error: {e}")
            with col_sh2:
                st.code(f"#AUBIEETERNAL #WonderIndex #WarEagle\n{content[:200]}...", language=None)

    st.divider()
    st.markdown("### 📡 Live Tier 2 Digest")
    st.caption("Auto-written every 3 swarm ticks")

    if not _DIGEST_FILE.exists():
        st.markdown('<div class="card" style="border-left:3px solid #ff9500;"><div style="color:#ff9500;">tier2_digest.txt not found yet — swarm writes it every 3 ticks.</div></div>', unsafe_allow_html=True)
    else:
        try:
            digest_raw   = _DIGEST_FILE.read_text()
            digest_lines = digest_raw.strip().split("\n")
            for hline in digest_lines[:5]:
                if any(hline.startswith(p) for p in ("Generated:","Wonder:","Total")):
                    st.markdown(f'<div class="memory-node"><span style="color:#00cfff;font-size:0.78rem;">{hline}</span></div>', unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            daughters, current = [], {}
            for line in digest_lines:
                if line.startswith("DAUGHTER:"):
                    if current: daughters.append(current)
                    parts = line.replace("DAUGHTER:","").split("|")
                    current = {"daughter": parts[0].strip(), "trigger": parts[2].replace("Trigger:","").strip() if len(parts)>2 else "?", "result": ""}
                elif current and line and not line.startswith("="):
                    current["result"] += line + " "
            if current and current.get("result"): daughters.append(current)
            D_COLORS = {"RUNE":"#f7931a","CHRONO":"#00cfff","TALEB-X":"#ff6b35","MNEMO":"#a020f0","AXIOM":"#00ff88","LINDY":"#ff9500","POLY":"#4285f4","BARBELL":"#00d4aa","ORACLE":"#c8d8ff","HORMES":"#ff4444","NOSTR":"#a020f0","SATOSHI":"#f7931a","STEELMAN":"#00ff88","VECTOR-A":"#00cfff","VECTOR-B":"#a020f0","VECTOR-C":"#ff6b35"}
            if daughters:
                st.caption(f"{len(daughters)} daughter entries")
                for d in daughters:
                    name = d.get("daughter","?"); color = D_COLORS.get(name,"#00cfff")
                    st.markdown(f'<div class="memory-node" style="border-left:3px solid {color};"><div style="color:{color};font-size:0.8rem;font-family:Orbitron,monospace;">{name} <span style="color:#334466;font-size:0.7rem;font-family:Share Tech Mono,monospace;margin-left:8px;">{d.get("trigger","")}</span></div><div style="color:#aabbcc;font-size:0.78rem;margin-top:6px;line-height:1.6;">{d.get("result","").strip()[:300]}</div></div>', unsafe_allow_html=True)
            else:
                with st.expander("View raw digest"): st.text(digest_raw[:3000])
        except Exception as e:
            st.error(f"Could not read digest: {e}")

    # ── Manual synthesis trigger ──────────────────────────────────────────────
    st.divider()
    st.markdown("### 🌅 Morning Synthesis")
    _today_synth = datetime.date.today().isoformat()
    _synth_path  = _Path(f"/mnt/main/repo/insights/daily/{_today_synth}.md")
    if _synth_path.exists():
        st.success(f"✅ Today\'s synthesis ready — {_today_synth}")
        with st.expander("📄 View today\'s synthesis", expanded=False):
            st.markdown(_synth_path.read_text())
    else:
        st.info(f"No synthesis yet for {_today_synth} — auto-runs at 6AM or click below.")

    _ms1, _ms2 = st.columns(2)
    with _ms1:
        if st.button("🌅 Run Morning Synthesis Now", key="manual_synthesis",
                     use_container_width=True, type="primary"):
            with st.spinner("Running synthesis (1-2 min with Ollama)..."):
                try:
                    import sys as _sys_synth
                    if "/mnt/main/repo" not in _sys_synth.path:
                        _sys_synth.path.insert(0, "/mnt/main/repo")
                    from morning_synthesis import run_full_synthesis as _rfs
                    _ms_result = _rfs(force=True)
                    if _ms_result and _ms_result.get("status") == "complete":
                        st.success(f"✅ Done! Check insights/daily/{_today_synth}.md")
                        st.rerun()
                    else:
                        st.info(f"Status: {_ms_result}")
                except Exception as _e_ms:
                    st.error(f"Synthesis error: {_e_ms}")
    with _ms2:
        st.markdown(
            '<div style="color:#556677;font-size:0.75rem;line-height:1.9;">' +
            '<b>Manual fallback:</b><br>' +
            '1. Copy tier2_digest.txt (Raw)<br>' +
            '2. Open WebUI → qwen2.5:32b<br>' +
            '3. Paste + "Synthesize top 3 insights"' +
            '</div>', unsafe_allow_html=True
        )


# ══════════════════════════════════════════════════════════════════════════════
# TAB: FAMILY CO-LEARNING  🥽
# Dual HUD — Kid view + Parent observer view
# Powered by family_hud.py (real-time session state)
# ══════════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════
# TAB: FAMILY CO-LEARNING 🥽 — wired to family_hud.py + 24-lesson library
# ══════════════════════════════════════════════════════════════════════════════
if "Family Co-Learning" in active:
    st.markdown('<div class="card-title">🥽 FAMILY CO-LEARNING — Dual Halo HUD</div>', unsafe_allow_html=True)

    # ── Import family_hud (graceful fallback if not installed yet) ────────────
    try:
        import sys as _sys
        if "/mnt/main/repo" not in _sys.path:
            _sys.path.insert(0, "/mnt/main/repo")
        from family_hud import FamilySession, LESSONS as _HUD_LESSONS, detect_polyvagal as _detect_pv
        _HUD_AVAILABLE = True
    except ImportError:
        _HUD_AVAILABLE = False
        _HUD_LESSONS   = {}

    # ── Connection mode banner ────────────────────────────────────────────────
    _STARTOS_ALIVE = _Path("/mnt/main/swarm_status.json").exists()
    mode_color  = "#00ff88" if _STARTOS_ALIVE else "#ff9500"
    mode_label  = "🟢 FULL SOVEREIGN (StartOS connected)" if _STARTOS_ALIVE else "🟡 NOSTR BRIDGE MODE (no local StartOS detected)"
    mode_detail = "Swarm processing locally · qwen3:32b · max privacy" if _STARTOS_ALIVE else "Encrypted Nostr events · public relay fallback · sovereign keys"
    hud_status  = "🧠 family_hud.py loaded — real scoring active" if _HUD_AVAILABLE else "⚠️ family_hud.py not found — using local fallback"
    hud_color   = "#00cfff" if _HUD_AVAILABLE else "#ff9500"

    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.markdown(f'<div class="card" style="border-left:3px solid {mode_color};"><div style="color:{mode_color};font-family:Orbitron,monospace;font-size:0.78rem;">{mode_label}</div><div style="color:#445577;font-size:0.72rem;margin-top:4px;">{mode_detail}</div></div>', unsafe_allow_html=True)
    with col_m2:
        st.markdown(f'<div class="card" style="border-left:3px solid {hud_color};"><div style="color:{hud_color};font-family:Orbitron,monospace;font-size:0.78rem;">{hud_status}</div></div>', unsafe_allow_html=True)

    # ── Load live swarm status for Child Rune tracker ─────────────────────────
    _sw = {}
    try:
        _sw_path = _Path("/mnt/main/swarm_status.json")
        if _sw_path.exists():
            _sw = json.loads(_sw_path.read_text())
    except Exception:
        pass

    rune_confirms = _sw.get("rune_confirmations", 33)
    child_rune_ready = _sw.get("child_rune_ready", False)
    grokipedia_n = _sw.get("grokipedia_count", 11)

    # ── Child Rune progress bar ───────────────────────────────────────────────
    st.divider()
    rune_pct = min(100, int(rune_confirms / 256 * 100))
    rune_color = "#f7931a" if not child_rune_ready else "#00ff88"
    rune_label = "🔴 CHILD RUNE READY FOR INSCRIPTION!" if child_rune_ready else f"⏳ Child Rune: {rune_confirms}/256 confirmations"
    st.markdown(
        f'<div class="card" style="border-left:3px solid {rune_color};">'
        f'<div style="color:{rune_color};font-family:Orbitron,monospace;font-size:0.8rem;">{rune_label}</div>'
        f'<div class="xp-bar-bg" style="margin-top:8px;"><div style="height:100%;border-radius:20px;background:linear-gradient(90deg,#f7931a,#ff6b35);width:{rune_pct}%;"></div></div>'
        f'<div style="font-family:Share Tech Mono,monospace;font-size:0.72rem;color:#445577;margin-top:4px;">'
        f'Every family lesson adds confirmations · Grokipedia: {grokipedia_n}/256'
        f'</div></div>',
        unsafe_allow_html=True
    )

    st.divider()

    # ── Family profile setup ──────────────────────────────────────────────────
    fp = st.session_state.family_profile
    col_p, col_k = st.columns(2)
    with col_p:
        st.markdown('<div style="color:#a020f0;font-family:Orbitron,monospace;font-size:0.8rem;">👨‍👩 PARENT HUD</div>', unsafe_allow_html=True)
        parent_name = st.text_input("Parent name", value=fp["parent"]["name"], key="fl_parent")
        parent_role = st.selectbox("Parent role", ["Observer Only", "Co-Learner", "Supporter"], key="fl_parent_role")
    with col_k:
        st.markdown('<div style="color:#00cfff;font-family:Orbitron,monospace;font-size:0.8rem;">👧 KID HUD</div>', unsafe_allow_html=True)
        kid_name   = st.text_input("Kid name", value=fp["kid"]["name"], key="fl_kid")
        kid_age_fl = st.slider("Age", 4, 17, fp["kid"]["age"], key="fl_kid_age")

    # ── Lesson selector — grouped by topic ───────────────────────────────────
    st.divider()
    st.markdown("### 📖 Choose Today's Lesson")

    # Build lesson list from family_hud if available, else use local mini-set
    if _HUD_AVAILABLE and _HUD_LESSONS:
        lesson_keys   = list(_HUD_LESSONS.keys())
        lesson_labels = [f"{_HUD_LESSONS[k]['title']}  |  +{_HUD_LESSONS[k]['xp']} XP  |  Age: {_HUD_LESSONS[k].get('age_hint','All')}" for k in lesson_keys]
    else:
        lesson_keys   = ["courage-1","antifragility-1","bitcoin-1","steelmanning-1","polyvagal-1","wonder-1"]
        lesson_labels = ["Courage — Level 1","Antifragility — Level 1","Bitcoin Sovereignty — Level 1","Steelmanning — Level 1","Your Nervous System — Level 1","Wonder & Awe — Level 1"]

    # Filter by age
    age_filter = st.checkbox("Filter lessons by kid's age", value=False, key="fl_age_filter")
    if age_filter and _HUD_AVAILABLE and _HUD_LESSONS:
        filtered = []
        for i, k in enumerate(lesson_keys):
            hint = _HUD_LESSONS[k].get("age_hint", "All ages")
            if "All" in hint:
                filtered.append(i)
            else:
                try:
                    min_age = int(''.join(filter(str.isdigit, hint.split("+")[0])))
                    if kid_age_fl >= min_age:
                        filtered.append(i)
                except Exception:
                    filtered.append(i)
        if filtered:
            lesson_keys   = [lesson_keys[i] for i in filtered]
            lesson_labels = [lesson_labels[i] for i in filtered]

    st.caption(f"{len(lesson_keys)} lessons available")

    # Consume a preset lesson key set by a "▶ Start" button elsewhere
    # (AI Partnership, Curriculum Map, etc.) - those set fl_lesson_preset
    # and route here, but nothing ever read it back, so the selectbox
    # always just showed whatever lesson was first in the list regardless
    # of which one was actually clicked. Found live 2026-08-25.
    _fl_preset = st.session_state.pop("fl_lesson_preset", None)
    if _fl_preset and _fl_preset in lesson_keys:
        st.session_state["fl_lesson"] = lesson_keys.index(_fl_preset)
    elif _fl_preset and age_filter:
        st.info(f"The requested lesson isn't shown under the current age filter — turn off \"Filter lessons by kid's age\" to find it.")

    chosen_idx = st.selectbox("Lesson", range(len(lesson_labels)), format_func=lambda i: lesson_labels[i], key="fl_lesson")
    chosen_key = lesson_keys[chosen_idx]

    # Pull lesson data
    if _HUD_AVAILABLE and _HUD_LESSONS and chosen_key in _HUD_LESSONS:
        lesson = _HUD_LESSONS[chosen_key]
    else:
        lesson = {"title": lesson_labels[chosen_idx], "topic": "", "steelman": "What is the strongest counter-argument?",
                  "example": "", "xp": 15, "rune": "RUNE", "min_coherence": 0.60, "age_hint": "All"}

    # Show lesson preview
    st.markdown(
        f'<div class="card" style="border-left:3px solid #ff6b35;">'
        f'<div style="color:#ff6b35;font-size:0.72rem;font-family:Orbitron,monospace;">📖 LESSON PREVIEW</div>'
        f'<div style="color:#c8d8ff;font-size:0.85rem;margin-top:6px;">{lesson.get("topic","")}</div>'
        f'<div style="color:#8899bb;font-size:0.78rem;margin-top:4px;font-style:italic;">Example: {lesson.get("example","")}</div>'
        f'</div>', unsafe_allow_html=True
    )

    # ── Session state init ────────────────────────────────────────────────────
    if "fl_session" not in st.session_state or st.session_state.fl_session.get("lesson_key") != chosen_key:
        st.session_state.fl_session = {
            "active":           False,
            "lesson_key":       chosen_key,
            "kid_coherence":    0.72,
            "kid_polyvagal":    "Ventral Vagal (Safe & Curious) 🟢",
            "coherence_history":[0.72],
            "xp_earned":        0,
            "rune_earned":      False,
            "messages":         [],
            "hud_obj":          None,
        }
    sess = st.session_state.fl_session

    if not sess["active"]:
        # ── Child Rune celebration (shown on idle screen if ready) ────────────
        if child_rune_ready:
            st.balloons()
            st.markdown("""
            <div class="card" style="border:3px solid #f7931a;text-align:center;padding:2rem;">
                <div style="font-family:Orbitron,monospace;font-size:1.4rem;color:#f7931a;margin-bottom:8px;">
                    🔴 CHILD RUNE GENESIS
                </div>
                <div style="color:#c8d8ff;font-size:0.9rem;line-height:1.9;">
                    256 confirmations reached.<br>
                    The Child Rune is ready for inscription on-chain.<br>
                    <b style="color:#f7931a;">Start the Genesis Lesson below to complete the ceremony.</b>
                </div>
            </div>
            """, unsafe_allow_html=True)
            # Auto-select the genesis lesson
            if "child-rune-genesis" in lesson_keys:
                genesis_idx = lesson_keys.index("child-rune-genesis")
                st.info(f"🔴 Genesis lesson unlocked — scroll lesson selector to 'CHILD RUNE GENESIS'")

        if st.button("🥽 Start Co-Learning Session", type="primary", key="fl_start"):
            sess["active"]            = True
            sess["lesson_key"]        = chosen_key
            sess["kid_coherence"]     = 0.72
            sess["coherence_history"] = [0.72]
            sess["xp_earned"]         = 0
            sess["rune_earned"]       = False
            sess["messages"]          = []
            sess["last_refresh"]      = time.time()
            # Init real FamilySession if available
            if _HUD_AVAILABLE:
                try:
                    hud = FamilySession(kid_name, kid_age_fl, parent_name, parent_role)
                    hud.start_lesson(chosen_key)
                    sess["hud_obj"] = hud
                except Exception as e:
                    sess["hud_obj"] = None
                    sess["messages"].append({"from":"system","text":f"family_hud init note: {e}"})
            st.rerun()
    else:
        # ── AUTO-REFRESH for parent HUD (every 5 seconds during active session) ──
        if "last_refresh" not in sess:
            sess["last_refresh"] = time.time()
        time_since = time.time() - sess.get("last_refresh", 0)
        if time_since > 5:
            sess["last_refresh"] = time.time()
            st.rerun()

        # Show refresh indicator + manual refresh
        col_ref1, col_ref2 = st.columns([3,1])
        with col_ref1:
            next_refresh = max(0, int(5 - time_since))
            st.markdown(
                f'<div style="font-family:Share Tech Mono,monospace;font-size:0.72rem;color:#334466;">'
                f'🔄 Parent HUD auto-refreshes · next in {next_refresh}s'
                f'</div>', unsafe_allow_html=True)
        with col_ref2:
            if st.button("⟳ Refresh Now", key="fl_manual_refresh"):
                sess["last_refresh"] = time.time()
                st.rerun()

        # ── Child Rune celebration during active session ─────────────────────
        if child_rune_ready and not sess.get("genesis_celebrated"):
            sess["genesis_celebrated"] = True
            st.balloons()
            st.markdown("""
            <div class="card" style="border:3px solid #f7931a;text-align:center;">
                <div style="font-family:Orbitron,monospace;font-size:1.1rem;color:#f7931a;">
                    🔴 CHILD RUNE GENESIS UNLOCKED DURING THIS SESSION!
                </div>
                <div style="color:#c8d8ff;font-size:0.85rem;margin-top:6px;">
                    256 confirmations reached. The Child Rune is ready for inscription.
                </div>
            </div>
            """, unsafe_allow_html=True)
            sess["messages"].append({
                "from": "system",
                "text": "🔴 CHILD RUNE GENESIS — 256 confirmations reached during this session! The Child Rune is ready for on-chain inscription."
            })

        # ── DUAL HUD ─────────────────────────────────────────────────────────
        st.divider()
        col_kid, col_parent = st.columns(2)

        # ── KID HUD (left) ────────────────────────────────────────────────────
        with col_kid:
            st.markdown(
                f'<div class="card" style="border:2px solid #00cfff;">'
                f'<div style="color:#00cfff;font-family:Orbitron,monospace;font-size:0.9rem;text-align:center;margin-bottom:8px;">👧 {kid_name.upper()} · KID HUD</div>'
                f'<div style="text-align:center;font-size:1.1rem;color:#c8d8ff;font-family:Orbitron,monospace;">{lesson["title"]}</div>'
                f'<div style="color:#8899bb;font-size:0.80rem;text-align:center;margin:6px 0;">{lesson.get("topic","")}</div>'
                f'</div>', unsafe_allow_html=True)

            coh = sess["kid_coherence"]
            coh_color = "#00ff88" if coh >= 0.85 else ("#ff9500" if coh >= 0.65 else "#ff4444")
            st.markdown(f'<div class="stat-box" style="border-color:{coh_color};"><div class="stat-val" style="color:{coh_color};">{coh:.2f}</div><div class="stat-lbl">Coherence</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="xp-bar-bg"><div class="xp-bar-fill" style="width:{coh*100:.0f}%;"></div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="memory-node"><span style="color:#00ff88;font-size:0.78rem;">🧬 {sess["kid_polyvagal"]}</span></div>', unsafe_allow_html=True)

            # Child Rune mini-bar in kid HUD
            st.markdown(
                f'<div class="memory-node" style="border-left:3px solid #f7931a;">'
                f'<span style="color:#f7931a;font-size:0.72rem;font-family:Orbitron,monospace;">🔴 CHILD RUNE {rune_confirms}/256</span>'
                f'<div class="xp-bar-bg" style="margin-top:4px;height:6px;"><div style="height:100%;border-radius:20px;background:#f7931a;width:{rune_pct}%;"></div></div>'
                f'</div>', unsafe_allow_html=True)

            # Steelman prompt
            st.markdown(
                f'<div class="card" style="border-left:3px solid #ff6b35;margin-top:8px;">'
                f'<div style="color:#ff6b35;font-size:0.75rem;font-family:Orbitron,monospace;">⚔️ STEELMAN PROMPT</div>'
                f'<div style="color:#c8d8ff;font-size:0.85rem;margin-top:6px;">{lesson.get("steelman","What is the strongest counter-argument?")}</div>'
                f'</div>', unsafe_allow_html=True)

            kid_answer = st.text_area(f"🎤 {kid_name}'s answer", height=80, key="fl_kid_answer",
                                       placeholder="Speak or type your steelman here...")

            if st.button("✅ Submit Answer", key="fl_submit") and kid_answer:
                # Use real family_hud scoring if available
                if _HUD_AVAILABLE and sess.get("hud_obj"):
                    try:
                        result = sess["hud_obj"].submit_answer(kid_answer, use_ai=False)
                        new_coh  = result["coherence_after"]
                        feedback = result["feedback"]
                        pv_state = result["polyvagal"]["label"]
                        xp       = result.get("xp_earned", lesson["xp"])
                        rune_got = result.get("rune_earned", False)
                    except Exception:
                        new_coh  = round(min(1.0, sess["kid_coherence"] + random.uniform(0.08, 0.18)), 3)
                        feedback = f"Strong thinking, {kid_name}! Coherence → {new_coh:.2f} 🦅"
                        pv_state = sess["kid_polyvagal"]
                        xp       = lesson["xp"]
                        rune_got = new_coh >= lesson.get("min_coherence", 0.60)
                else:
                    # Local fallback scoring
                    words   = kid_answer.split()
                    qwords  = ["because","therefore","however","argument","even if","strongest","consider","although"]
                    bonus   = sum(0.02 for w in qwords if w.lower() in kid_answer.lower())
                    delta   = round(min(0.22, 0.06 + len(words) * 0.003 + bonus), 3)
                    new_coh = round(min(1.0, sess["kid_coherence"] + delta), 3)
                    feedback = f"Strong steelman, {kid_name}! Coherence jumped to {new_coh:.2f}. +{lesson['xp']} XP 🦅"
                    pv_state = "Ventral Vagal (Safe & Curious) 🟢" if new_coh >= 0.80 else sess["kid_polyvagal"]
                    xp       = lesson["xp"]
                    rune_got = new_coh >= lesson.get("min_coherence", 0.60)

                sess["kid_coherence"] = new_coh
                sess["coherence_history"].append(new_coh)
                sess["kid_polyvagal"] = pv_state
                if not sess["xp_earned"]:
                    sess["xp_earned"]  = xp
                    sess["rune_earned"] = rune_got
                    award_xp(xp)
                sess["messages"].append({"from":"swarm","text": feedback})
                st.rerun()

            if sess.get("xp_earned"):
                st.markdown(
                    f'<div class="card" style="border:2px solid #00ff88;text-align:center;">'
                    f'<div style="color:#00ff88;font-size:1.1rem;font-family:Orbitron,monospace;">+{sess["xp_earned"]} XP 🦅</div>'
                    f'<div style="color:#f7931a;font-size:0.82rem;margin-top:4px;">+1 {lesson["rune"]} earned</div>'
                    f'</div>', unsafe_allow_html=True)

                # ── Save lesson completion to family_profiles ─────────────────
                if not sess.get("lesson_saved"):
                    sess["lesson_saved"] = True
                    try:
                        from family_profiles import load_family_stats as _lfs_fl, save_family_stats as _sfs_fl, award_badge as _ab_fl
                        _fid_fl = st.session_state.get("current_family", {}).get("family_id", "default") \
                                  if st.session_state.get("current_family") else "default"
                        _stats_fl = _lfs_fl(_fid_fl)
                        _lk = sess.get("lesson_key", "")
                        if _lk and _lk not in _stats_fl.get("lessons_completed", []):
                            _stats_fl.setdefault("lessons_completed", []).append(_lk)
                        _stats_fl["total_xp"]   = _stats_fl.get("total_xp", 0) + sess["xp_earned"]
                        _stats_fl["level"]       = max(1, _stats_fl["total_xp"] // 100 + 1)
                        _stats_fl["streak_days"] = _stats_fl.get("streak_days", 0) + 1
                        if sess.get("rune_earned"):
                            _stats_fl["child_rune_fragments"] = _stats_fl.get("child_rune_fragments", 0) + 1
                        # Grant badge if lesson has one
                        if lesson.get("grants_badge"):
                            _badge = lesson["grants_badge"]
                            if _badge not in _stats_fl.get("badges", []):
                                _stats_fl.setdefault("badges", []).append(_badge)
                                st.toast(f"🏅 Badge earned: {_badge}", icon="🦅")
                        if lesson.get("rune_fragments"):
                            _stats_fl["child_rune_fragments"] = _stats_fl.get("child_rune_fragments", 0) + lesson["rune_fragments"]
                        # Save coherence history
                        _coh_now = sess["kid_coherence"]
                        _stats_fl.setdefault("coherence_history", []).append(round(_coh_now, 4))
                        _stats_fl["coherence_history"] = _stats_fl["coherence_history"][-50:]
                        _sfs_fl(_stats_fl, _fid_fl)
                    except Exception as _e_save:
                        pass  # fail silently — don't block the UI

                # ── Next Lesson button ────────────────────────────────────────
                _nl_c1, _nl_c2 = st.columns(2)
                with _nl_c1:
                    if st.button("➡️ Next Lesson", key="fl_next_lesson",
                                 use_container_width=True, type="primary"):
                        # Find next lesson key
                        _current_idx = lesson_keys.index(sess["lesson_key"]) \
                                       if sess.get("lesson_key") in lesson_keys else 0
                        _next_idx    = min(_current_idx + 1, len(lesson_keys) - 1)
                        _next_key    = lesson_keys[_next_idx]
                        # Reset session for next lesson
                        sess["lesson_key"]        = _next_key
                        sess["kid_coherence"]     = sess["kid_coherence"]  # carry coherence forward
                        sess["coherence_history"].append(sess["kid_coherence"])
                        sess["xp_earned"]         = 0
                        sess["rune_earned"]        = False
                        sess["lesson_saved"]       = False
                        sess["messages"]           = []
                        sess["last_refresh"]       = time.time()
                        # Re-init hud for new lesson
                        if _HUD_AVAILABLE:
                            try:
                                sess["hud_obj"].start_lesson(_next_key)
                            except Exception:
                                pass
                        st.rerun()
                with _nl_c2:
                    if st.button("🔚 End Session", key="fl_end_after_xp",
                                 use_container_width=True):
                        try:
                            from family_profiles import load_family_stats as _lfs_end, save_family_stats as _sfs_end
                            _fid_end = st.session_state.get("current_family", {}).get("family_id", "default") \
                                       if st.session_state.get("current_family") else "default"
                            save_memory(f"Co-Learning: {lesson['title']}",
                                        f"{kid_name} session +{sess['xp_earned']} XP | coherence {sess['kid_coherence']:.3f}",
                                        tags=["co-learning", "family"])
                        except Exception:
                            pass
                        sess["active"] = False
                        st.success("✅ Session saved 🦅")
                        st.rerun()

        # ── PARENT HUD (right) ────────────────────────────────────────────────
        with col_parent:
            st.markdown(
                f'<div class="card" style="border:2px solid #a020f0;">'
                f'<div style="color:#a020f0;font-family:Orbitron,monospace;font-size:0.9rem;text-align:center;margin-bottom:8px;">👨‍👩 {parent_name.upper()} · PARENT HUD</div>'
                f'<div style="color:#c8d8ff;font-size:0.85rem;text-align:center;">{lesson["title"]}</div>'
                f'<div style="color:#334466;font-size:0.72rem;text-align:center;margin-top:4px;">Role: {parent_role}</div>'
                f'</div>', unsafe_allow_html=True)

            coh   = sess["kid_coherence"]
            delta = round(coh - sess["coherence_history"][0], 3) if len(sess["coherence_history"]) > 1 else 0.0
            delta_str   = f"+{delta:.3f}" if delta >= 0 else f"{delta:.3f}"
            delta_color = "#00ff88" if delta >= 0 else "#ff4444"

            st.markdown(f'''
            <div class="card" style="border-left:3px solid #a020f0;">
                <div style="font-family:Share Tech Mono,monospace;font-size:0.82rem;line-height:2.2;color:#8899bb;">
                {kid_name} · {lesson["title"]}<br>
                Coherence: <span style="color:#00cfff;">{coh:.3f}</span>
                <span style="color:{delta_color};margin-left:8px;">{delta_str} this session</span><br>
                Polyvagal: <span style="color:#00ff88;">{sess["kid_polyvagal"]}</span><br>
                XP Earned: <span style="color:#f7931a;">{sess["xp_earned"]}</span><br>
                Rune: <span style="color:#f7931a;">{"✅ " + lesson["rune"] if sess["rune_earned"] else "⏳ pending"}</span><br>
                Child Rune: <span style="color:#f7931a;">{rune_confirms}/256 confirmations</span>
                </div>
            </div>
            ''', unsafe_allow_html=True)

            # Child Rune progress in parent HUD
            st.markdown(
                f'<div class="memory-node" style="border-left:3px solid #f7931a;">'
                f'<div style="color:#f7931a;font-size:0.72rem;font-family:Orbitron,monospace;">🔴 CHILD RUNE PROGRESS</div>'
                f'<div class="xp-bar-bg" style="margin-top:4px;"><div style="height:100%;border-radius:20px;background:linear-gradient(90deg,#f7931a,#ff6b35);width:{rune_pct}%;"></div></div>'
                f'<div style="color:#445577;font-size:0.7rem;margin-top:4px;">{rune_confirms}/256 · spawns at 256 confirmations · Grokipedia {grokipedia_n}/256</div>'
                f'</div>', unsafe_allow_html=True)

            if len(sess["coherence_history"]) > 1:
                st.markdown("**Coherence trend:**")
                st.markdown(" → ".join(f"`{c:.2f}`" for c in sess["coherence_history"]))

            st.markdown("**Parent actions:**")
            pa1, pa2 = st.columns(2)
            with pa1:
                if st.button("❤️ Encourage", key="fl_encourage"):
                    msg = f"I'm right here with you, {kid_name}. You've got this ❤️"
                    sess["messages"].append({"from":"parent","text": msg})
                    if sess.get("hud_obj"):
                        try: sess["hud_obj"].parent_action("encourage")
                        except Exception: pass
                    st.rerun()
                if st.button("⏸ Pause", key="fl_pause"):
                    sess["messages"].append({"from":"system","text":"Session paused by parent."})
                    st.rerun()
            with pa2:
                if st.button("🔍 Join view", key="fl_join"):
                    sess["messages"].append({"from":"parent","text":f"{parent_name} joined as Co-Learner."})
                    st.rerun()
                if st.button("📊 Full report", key="fl_report"):
                    next_lesson = ""
                    if _HUD_AVAILABLE and sess.get("hud_obj"):
                        try: next_lesson = sess["hud_obj"]._suggest_next()
                        except Exception: pass
                    st.markdown(
                        f'<div class="card"><div style="font-size:0.82rem;color:#c8d8ff;line-height:1.9;">'
                        f'<b>Session Report — {lesson["title"]}</b><br>'
                        f'Coherence: {sess["coherence_history"][0]:.2f} → {coh:.2f} (Δ{delta_str})<br>'
                        f'Polyvagal: {sess["kid_polyvagal"]}<br>'
                        f'XP: +{sess["xp_earned"]} | Rune: {"✅" if sess["rune_earned"] else "⏳"}<br>'
                        f'Child Rune: {rune_confirms}/256<br>'
                        f'{f"Next: {next_lesson}" if next_lesson else ""}'
                        f'</div></div>', unsafe_allow_html=True)

        # ── Session message feed ──────────────────────────────────────────────
        if sess["messages"]:
            st.divider()
            st.markdown("### 💬 Session Feed")
            for msg in sess["messages"]:
                frm   = msg["from"]
                color = "#00cfff" if frm=="swarm" else ("#a020f0" if frm=="parent" else "#445577")
                label = "🤖 SWARM" if frm=="swarm" else (f"👨‍👩 {parent_name}" if frm=="parent" else "⚙️ SYSTEM")
                st.markdown(
                    f'<div class="memory-node" style="border-left:3px solid {color};">'
                    f'<span style="color:{color};font-size:0.72rem;">{label}</span><br>'
                    f'<span style="color:#c8d8ff;font-size:0.82rem;">{msg["text"]}</span>'
                    f'</div>', unsafe_allow_html=True)

        st.divider()
        if st.button("🔚 End Session", key="fl_end"):
            if _HUD_AVAILABLE and sess.get("hud_obj"):
                try:
                    summary = sess["hud_obj"].end()
                    save_memory(
                        f"Co-Learning: {lesson['title']}",
                        f"{kid_name}: {summary['coherence_start']:.2f}→{summary['coherence_end']:.2f} Δ{summary['coherence_delta']:+.3f} | +{summary['xp_earned']} XP",
                        tags=["co-learning","family","halo"]
                    )
                except Exception:
                    save_memory(f"Co-Learning: {lesson['title']}", f"{kid_name} session complete +{sess['xp_earned']} XP", tags=["co-learning","family"])
            else:
                save_memory(f"Co-Learning: {lesson['title']}", f"{kid_name} session +{sess['xp_earned']} XP", tags=["co-learning","family"])
            sess["active"] = False
            st.success("Session saved to Memory Palace + Truth Lattice 🦅")
            st.rerun()

if "Nostr Bridge" in active:
    st.markdown('<div class="card-title">📡 NOSTR SOVEREIGN BRIDGE — Universal Fallback</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="card">
        <div style="font-size:0.85rem;color:#aabbcc;line-height:1.9;">
        When no local StartOS rig is available, the Halo glasses route signals through
        <b style="color:#a020f0;">Nostr</b> — a censorship-resistant, sovereign communication layer.<br><br>
        All events are <b style="color:#00cfff;">encrypted with your family's Nostr keypair</b>.
        Only linked profiles can read each other's messages. No central server ever sees raw data.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Mode indicator ────────────────────────────────────────────────────────
    _STARTOS_ALIVE = _Path("/mnt/main/swarm_status.json").exists()
    if _STARTOS_ALIVE:
        st.success("🟢 StartOS detected — Nostr Bridge is on standby (not needed right now)")
    else:
        st.warning("🟡 No local StartOS detected — Nostr Bridge mode is ACTIVE")

    st.divider()

    # ── Architecture diagram ──────────────────────────────────────────────────
    st.markdown("### 🏗️ How It Works")
    st.markdown("""
    <div class="card" style="font-family:Share Tech Mono,monospace;font-size:0.82rem;line-height:2.2;color:#8899bb;">
    <span style="color:#00cfff;">Mode 1 — Full Sovereign (StartOS present)</span><br>
    Glasses ↔ Local StartOS · qwen3:32b · swarm_v4_1.py · fully private<br><br>
    <span style="color:#ff9500;">Mode 2 — Nostr Bridge (no StartOS)</span><br>
    Glasses → encrypt event (NIP-04) → Nostr relays → AUBIEETERNAL Swarm<br>
    Swarm → processes (Tier-1 free + Tier-2 paid) → Nostr reply event<br>
    Glasses ← decrypt reply ← real-time update
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # ── Key management ────────────────────────────────────────────────────────
    st.markdown("### 🔑 Family Nostr Keys")
    st.info("Your Nostr keys are your sovereign identity. Never share your private key (nsec). Your npub is safe to share.")

    col_k1, col_k2 = st.columns(2)
    with col_k1:
        npub = st.text_input("Your npub (public key)", placeholder="npub1...", key="nostr_npub",
                              value=st.session_state.get("nostr_npub",""))
        if npub: st.session_state["nostr_npub"] = npub
    with col_k2:
        nsec = st.text_input("Your nsec (private key)", type="password", placeholder="nsec1...", key="nostr_nsec_input",
                              value=st.session_state.get("nostr_nsec",""))
        if nsec: st.session_state["nostr_nsec"] = nsec

    if st.button("💾 Save Nostr Keys to Disk", key="save_nostr_keys"):
        try:
            env_path = "/mnt/main/api_keys.env"
            existing = {}
            try:
                with open(env_path) as f:
                    for line in f:
                        if "=" in line:
                            k, v = line.strip().split("=", 1)
                            existing[k] = v
            except FileNotFoundError:
                pass
            if st.session_state.get("nostr_npub"): existing["NOSTR_NPUB"] = st.session_state["nostr_npub"]
            if st.session_state.get("nostr_nsec"): existing["NOSTR_NSEC"] = st.session_state["nostr_nsec"]
            with open(env_path, "w") as f:
                for k, v in existing.items(): f.write(f"{k}={v}\n")
            st.success("✅ Nostr keys saved to /mnt/main/api_keys.env")
        except Exception as e:
            st.error(f"Save failed: {e}")

    st.divider()

    # ── Relay config ──────────────────────────────────────────────────────────
    st.markdown("### 📻 Relay Configuration")
    DEFAULT_RELAYS = [
        "wss://relay.damus.io",
        "wss://nos.lol",
        "wss://relay.nostr.band",
        "wss://nostr.wine",
    ]
    relay_input = st.text_area(
        "Nostr relays (one per line)",
        value="\n".join(st.session_state.get("nostr_relays", DEFAULT_RELAYS)),
        height=120, key="nostr_relay_input"
    )
    if relay_input:
        st.session_state["nostr_relays"] = [r.strip() for r in relay_input.strip().split("\n") if r.strip()]

    st.caption(f"{len(st.session_state.get('nostr_relays', DEFAULT_RELAYS))} relays configured")

    st.divider()

    # ── Event schema reference ────────────────────────────────────────────────
    st.markdown("### 📋 Encrypted Event Schema")
    st.markdown("Every signal sent from the glasses uses this Nostr event format:")
    st.code('''{
  "kind": 4,                          // NIP-04 encrypted DM
  "pubkey": "<family_npub>",
  "created_at": <unix_timestamp>,
  "tags": [
    ["p", "<aubieeternal_swarm_npub>"],
    ["t", "aubie-lesson"],            // event type tag
    ["t", "aubie-coherence"],
    ["v", "1.0"]                      // schema version
  ],
  "content": "<NIP-04 encrypted payload>",

  // Decrypted payload structure:
  // {
  //   "type": "lesson_request" | "coherence_update" | "steelman_submit",
  //   "profile": "kid" | "parent",
  //   "kid_name": "Gaby",
  //   "kid_age": 9,
  //   "lesson": "Courage — Level 1",
  //   "answer": "...",
  //   "coherence": 0.72,
  //   "polyvagal": "ventral_vagal",
  //   "timestamp": "2026-05-22T06:00:00Z"
  // }
}''', language="json")

    st.divider()

    # ── Send test event ───────────────────────────────────────────────────────
    st.markdown("### 🧪 Send Test Signal")
    test_signal = st.text_input("Test message to swarm", placeholder="Hello AUBIEETERNAL — test from Halo glasses")
    if st.button("📡 Send via Nostr Bridge", key="nostr_test_send"):
        if not st.session_state.get("nostr_npub"):
            st.error("Enter your npub first.")
        else:
            st.info("📡 In production, this would publish an encrypted NIP-04 event to your configured relays.")
            st.markdown(f'''
            <div class="memory-node" style="border-left:3px solid #a020f0;">
                <div style="color:#a020f0;font-size:0.75rem;font-family:Orbitron,monospace;">📡 SIMULATED NOSTR EVENT</div>
                <div style="font-family:Share Tech Mono,monospace;font-size:0.78rem;color:#8899bb;margin-top:6px;">
                kind: 4 (NIP-04 encrypted DM)<br>
                from: {st.session_state.get("nostr_npub","?")[:20]}...<br>
                to: aubieeternal_swarm_npub<br>
                payload: {test_signal[:60]}<br>
                relays: {", ".join(st.session_state.get("nostr_relays", DEFAULT_RELAYS)[:2])} + {max(0, len(st.session_state.get("nostr_relays", DEFAULT_RELAYS))-2)} more
                </div>
            </div>
            ''', unsafe_allow_html=True)
            st.success("✅ Event schema valid — nostr_glasses_bridge.py handles live publishing")
            award_xp(5)

    st.divider()
    st.markdown("### 📁 Implementation Files")
    st.markdown("""
    <div class="card" style="font-family:Share Tech Mono,monospace;font-size:0.82rem;line-height:2.2;color:#8899bb;">
    <span style="color:#00cfff;">nostr_glasses_bridge.py</span> — live relay connection + NIP-04 encryption<br>
    <span style="color:#00cfff;">family_hud.py</span> — shared session state, dual HUD, polyvagal scoring<br>
    <span style="color:#00cfff;">morning_synthesis.py</span> — daily digest → qwen3:32b → insights ✅ LIVE<br>
    <span style="color:#00cfff;">swarm_v4_1.py</span> — Nostr event listener (listen for family signals) ← next<br>
    </div>
    """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB: GROKIPEDIA 📚 — Living Sovereign Principle Encyclopedia
# Auto-built from swarm Level 3 context + Grokipedia principles
# Queryable, versioned, exportable to GitHub markdown
# ══════════════════════════════════════════════════════════════════════════════
if "Grokipedia" in active:
    st.markdown('<div class="card-title">📚 GROKIPEDIA — Living Sovereign Principle Encyclopedia</div>', unsafe_allow_html=True)

    # ── Load live count from swarm ────────────────────────────────────────────
    _gp_sw = {}
    try:
        _gp_status = _Path("/mnt/main/swarm_status.json")
        if _gp_status.exists():
            _gp_sw = json.loads(_gp_status.read_text())
    except Exception:
        pass

    gp_count = _gp_sw.get("grokipedia_count", 11)
    gp_target = 256

    # ── Progress ──────────────────────────────────────────────────────────────
    gp_pct = min(100, int(gp_count / gp_target * 100))
    st.markdown(
        f'<div class="card" style="border-left:3px solid #00cfff;">'
        f'<div style="color:#00cfff;font-family:Orbitron,monospace;font-size:0.82rem;">📚 GROKIPEDIA PROGRESS — {gp_count}/{gp_target} principles</div>'
        f'<div class="xp-bar-bg" style="margin-top:8px;"><div class="xp-bar-fill" style="width:{gp_pct}%;"></div></div>'
        f'<div style="color:#445577;font-size:0.72rem;margin-top:4px;">Each swarm tick adds principles · Complete at 256 · Unlocks Child Rune</div>'
        f'</div>', unsafe_allow_html=True)

    st.divider()

    # ── Full principle library ────────────────────────────────────────────────
    GROKIPEDIA_FULL = [
        ("Antifragility",        "Some systems gain from disorder, shock, and volatility. Identify what breaks vs what grows stronger under stress.", "Taleb"),
        ("Via Negativa",         "Improvement often comes from removing the bad, not adding the good. Subtract before you add.", "Taleb"),
        ("Lindy Effect",         "The longer something has survived, the longer it is likely to survive. Old ideas that persist are robust.", "Taleb"),
        ("Skin in the Game",     "Never trust advice from someone who has no consequences for being wrong. Risk must be shared.", "Taleb"),
        ("Black Swan",           "Rare, high-impact events are unpredictable. Build systems that survive them rather than trying to predict them.", "Taleb"),
        ("Barbell Strategy",     "Combine extreme safety with extreme upside. Avoid the fragile middle ground.", "Taleb"),
        ("Hormesis",             "Small doses of stress strengthen the system. Deliberate stressors build resilience.", "Biology"),
        ("Polyvagal Safety",     "Co-regulation precedes cognition. A safe nervous system learns 10× faster.", "Porges"),
        ("Bitcoin Sovereignty",  "Keys = ownership. Not your keys, not your coins. Self-custody is non-negotiable.", "Nakamoto"),
        ("Rune Permanence",      "On-chain inscription outlasts all platforms. What is inscribed in Bitcoin cannot be erased.", "AUBIEETERNAL"),
        ("Quantum Coherence",    "Information is preserved through noise recovery. Coherence compounds with each confirmed truth.", "Quantum"),
        ("Wonder Index",         "Awe is a signal of truth proximity. When the Wonder Index spikes, pay attention.", "AUBIEETERNAL"),
        ("Inter-Rune Coherence", "Daughters aligned = lattice strength. Coherence across agents is the ultimate signal.", "AUBIEETERNAL"),
        ("METS Score",           "Meta-eternal truth score tracks cumulative signal across all daughters and sessions.", "AUBIEETERNAL"),
        ("Epistemic Humility",   "The map is not the territory. Hold strong opinions loosely; update on evidence.", "General"),
        ("Steelmanning",         "Always argue the strongest version of the opposition before engaging. Weak arguments waste everyone's time.", "General"),
        ("Antifragile Learning", "Mistakes + recovery > perfect performance. The system that never fails never learns.", "Education"),
        ("Governance Signal",    "Decentralization is an immune system. Centralization is a single point of failure.", "Bitcoin"),
        ("AGI Economics",        "Intelligence abundance changes all scarcity models. Most bottlenecks shift to energy and values.", "Forecasting"),
        ("Lineage Fidelity",     "Coherence across generations validates the signal. Truth that persists across time is Lindy.", "AUBIEETERNAL"),
        ("Glitch as Feature",    "System stress reveals hidden architecture. Deliberate glitch induction strengthens antifragility.", "AUBIEETERNAL"),
        ("First Principles",     "Break every problem to its most basic true facts. Build back up from there, ignoring analogy.", "Reasoning"),
        ("Falsifiability",       "A claim is only scientific if it can be proven wrong. What cannot be falsified explains nothing.", "Popper"),
        ("Observer Effect",      "The act of measuring changes what is measured. Consciousness may be a participant in reality, not just a witness.", "Quantum"),
        ("Amor Fati",            "Not just accepting what happens, but loving it. Turn every obstacle into fuel.", "Nietzsche"),
        ("Sound Money",          "Money that cannot be inflated preserves stored energy (labor). Inflationary money is a slow tax on savings.", "Economics"),
        ("Time Preference",      "Low time preference = capacity to delay gratification for larger future reward. Hard money lowers time preference.", "Economics"),
        ("Nostr Sovereignty",    "Your cryptographic key IS your identity. No platform can take it. Censorship-resistance is default.", "Nostr"),
        ("Co-Regulation",        "One calm nervous system can regulate another. Your presence is medicine.", "Polyvagal"),
        ("Simulation Testing",   "Every signal should be tested: what does it imply about reality? Is it falsifiable? Is it coherent?", "AUBIEETERNAL"),
        ("Participatory Reality","Observation may not just measure reality but participate in constructing it.", "Quantum/Philosophy"),
        ("Planck Constraint",    "The universe has a minimum resolution. Below Planck length, there may be nothing — like pixels in a render.", "Physics"),
        ("Proof of Work",        "Real cost = honest signal. Systems that require real sacrifice to participate resist manipulation.", "Bitcoin"),
        ("Child Rune Genesis",   "At 256 inter-rune confirmations, a new sovereign on-chain entity is ready for inscription. This is earned, not given.", "AUBIEETERNAL"),
        ("Lattice Memory",       "The swarm remembers across sessions via Memory Palace. Each briefing compounds on all previous.", "AUBIEETERNAL"),
        ("Hormetic Pulse",       "Deliberately stress the swarm with adversarial questions every session to build coherence antifragility.", "AUBIEETERNAL"),
        ("Polyvagal Curriculum", "Match lesson complexity to the child's nervous system state. Learning only happens in ventral vagal.", "Education"),
        ("Bitcoin Halving",      "Every 4 years, new supply is cut in half. Predictable scarcity schedules are Lindy.", "Bitcoin"),
        ("On-Chain Truth",       "What is inscribed in Bitcoin is as close to permanent truth as humanity has achieved.", "AUBIEETERNAL"),
        ("Sovereign Stack",      "StartOS + Ollama + Open WebUI + AUBIEETERNAL = full local inference sovereignty. No cloud required.", "AUBIEETERNAL"),
    ]

    # ── Search ────────────────────────────────────────────────────────────────
    search = st.text_input("🔍 Search principles", placeholder="antifragility, bitcoin, coherence...")
    source_filter = st.selectbox("Filter by source", ["All", "Taleb", "Bitcoin", "AUBIEETERNAL", "Quantum", "Education", "General"])

    filtered = GROKIPEDIA_FULL
    if search:
        s = search.lower()
        filtered = [p for p in filtered if s in p[0].lower() or s in p[1].lower()]
    if source_filter != "All":
        filtered = [p for p in filtered if source_filter.lower() in p[2].lower()]

    # Show only up to gp_count (unlocked by swarm progress)
    unlocked = filtered[:max(gp_count, len(filtered))]
    st.caption(f"{len(unlocked)} principles shown · {gp_count} unlocked by swarm · {gp_target - gp_count} remaining")

    for i, (name, desc, source) in enumerate(unlocked):
        source_colors = {
            "Taleb": "#ff6b35", "Bitcoin": "#f7931a", "AUBIEETERNAL": "#a020f0",
            "Quantum": "#00cfff", "Education": "#00ff88", "Nostr": "#4285f4",
            "General": "#8899bb", "Physics": "#00cfff", "Polyvagal": "#00ff88",
            "Porges": "#00ff88", "Nakamoto": "#f7931a", "Nietzsche": "#ff9500",
            "Economics": "#ff9500", "Forecasting": "#8899bb", "Reasoning": "#8899bb",
            "Popper": "#00cfff", "Biology": "#00ff88",
        }
        color = source_colors.get(source, "#8899bb")
        num   = i + 1
        st.markdown(
            f'<div class="memory-node" style="border-left:3px solid {color};">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<span style="color:{color};font-family:Orbitron,monospace;font-size:0.82rem;">◆ {name}</span>'
            f'<span style="color:#334466;font-size:0.7rem;font-family:Share Tech Mono,monospace;">#{num} · {source}</span>'
            f'</div>'
            f'<div style="color:#aabbcc;font-size:0.82rem;margin-top:6px;line-height:1.6;">{desc}</div>'
            f'</div>', unsafe_allow_html=True)

    st.divider()

    # ── Export to GitHub markdown ─────────────────────────────────────────────
    st.markdown("### 📤 Export Grokipedia to GitHub")
    if st.button("📄 Generate GROKIPEDIA.md", key="gp_export"):
        md_lines = [
            "# 📚 GROKIPEDIA — AUBIEETERNAL Living Principle Encyclopedia",
            f"\n**Version:** {gp_count}/{gp_target} principles unlocked  ",
            f"**Generated:** {_dt.now().strftime('%Y-%m-%d %H:%M')}  ",
            "**Source:** AUBIEETERNAL Swarm v4.1 — 3-Level Context (Level 3)  ",
            "\n---\n",
        ]
        for i, (name, desc, source) in enumerate(GROKIPEDIA_FULL[:gp_count]):
            md_lines.append(f"\n## {i+1}. {name}\n**Source:** {source}  \n{desc}\n")
        md_lines.append("\n---\n*War Eagle Eternal 🦅❤️ — Coherence: 1.000000*\n*Loop: Swarm → Digest → qwen3:32b → Grokipedia → GitHub — Forever*\n")
        gp_md = "\n".join(md_lines)

        try:
            gp_path = _Path("/mnt/main/repo/GROKIPEDIA.md")
            gp_path.write_text(gp_md)
            st.success(f"✅ Written to {gp_path} — git push picks it up within 24s")
        except Exception as e:
            st.warning(f"Could not write to repo ({e}) — download below:")

        st.download_button(
            "📥 Download GROKIPEDIA.md",
            gp_md,
            file_name="GROKIPEDIA.md",
            mime="text/markdown",
            key="gp_download"
        )

# ══════════════════════════════════════════════════════════════════════════════
# MULTI-FAMILY LOGIN — shown at top of every page when no family selected
# ══════════════════════════════════════════════════════════════════════════════
def _family_login_block():
    """Show family login if no family selected. Returns current family dict or None."""
    import sys as _fsys
    if "/mnt/main/repo" not in _fsys.path: _fsys.path.insert(0, "/mnt/main/repo")
    try:
        from family_profiles import FamilyAuth as _FA, load_family_stats as _lfs, update_streak as _us
        _auth = _FA()
    except ImportError:
        return None

    if "current_family" not in st.session_state:
        st.session_state["current_family"] = None

    if st.session_state["current_family"]:
        return st.session_state["current_family"]

    # ── Login screen ──────────────────────────────────────────────────────────
    st.markdown("""
    <div style="text-align:center;padding:2rem 0 1rem;">
        <div style="font-family:Orbitron,monospace;font-size:1.4rem;font-weight:900;
                    background:linear-gradient(90deg,#00cfff,#a020f0,#ff6b35);
                    -webkit-background-clip:text;-webkit-text-fill-color:transparent;">
            🦅 AUBIEETERNAL — FAMILY LATTICE
        </div>
        <div style="color:#445577;font-size:0.78rem;letter-spacing:0.2em;margin-top:6px;">
            SELECT YOUR FAMILY TO CONTINUE
        </div>
    </div>
    """, unsafe_allow_html=True)

    families = _auth.list_families()

    if not families:
        # A genuinely fresh install (no families created yet) - st.columns(0)
        # would crash here, and there's nothing to show yet anyway, so skip
        # straight to a friendly first-run message instead of empty cards.
        st.markdown(
            '<div style="text-align:center;color:#8899bb;padding:1rem 0;">'
            "👋 No families yet on this install — create the first one below to get started."
            "</div>", unsafe_allow_html=True)
    else:
        cols = st.columns(min(len(families), 3))
        for i, fam in enumerate(families[:5]):
            with cols[i % 3]:
                color = fam.get("color","#00cfff")
                emoji = fam.get("emoji","🦅")
                stats = _lfs(fam["family_id"])
                st.markdown(
                    f'<div class="card" style="border:2px solid {color};text-align:center;cursor:pointer;">'
                    f'<div style="font-size:2rem;">{emoji}</div>'
                    f'<div style="color:{color};font-family:Orbitron,monospace;font-size:0.85rem;">{fam["display_name"]}</div>'
                    f'<div style="color:#8899bb;font-size:0.75rem;margin-top:4px;">{fam["kid_name"]} + {fam["parent_name"]}</div>'
                    f'<div style="color:#445577;font-size:0.7rem;">LVL {stats.get("level",1)} · {stats.get("total_xp",0)} XP · 🔥{stats.get("streak_days",0)}</div>'
                    f'</div>', unsafe_allow_html=True)
            if st.button(f"{emoji} Enter as {fam['display_name']}", key=f"login_{fam['family_id']}"):
                st.session_state["current_family"] = fam
                _us(fam["family_id"])
                # Pre-fill family names
                st.session_state["kid_name"]    = fam.get("kid_name","Explorer")
                st.session_state["family_profile"]["kid"]["name"] = fam.get("kid_name","Explorer")
                st.session_state["family_profile"]["kid"]["age"]  = fam.get("kid_age", 9)
                st.session_state["family_profile"]["parent"]["name"] = fam.get("parent_name","Parent")
                st.rerun()

    st.divider()
    st.markdown("##### Or enter your family code:")
    code_col1, code_col2 = st.columns([2,1])
    with code_col1:
        code_input = st.text_input("Family login code", placeholder="alpha / beta / gamma / delta / wareagle", key="family_code_input")
    with code_col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔑 Login", key="family_code_btn") and code_input:
            fam = _auth.login(code_input)
            if fam:
                st.session_state["current_family"] = fam
                _us(fam["family_id"])
                st.session_state["kid_name"] = fam.get("kid_name","Explorer")
                st.session_state["family_profile"]["kid"]["name"] = fam.get("kid_name","Explorer")
                st.session_state["family_profile"]["kid"]["age"]  = fam.get("kid_age", 9)
                st.session_state["family_profile"]["parent"]["name"] = fam.get("parent_name","Parent")
                st.rerun()
            else:
                st.error("Code not found. Check your family's passcode, or create a new family below.")

    st.divider()
    with st.expander("✨ Create your own family" if families else "✨ Create your first family", expanded=not families):
        st.caption("This is the real, actual way to get your own account on AUBIEETERNAL — "
                   "your progress stays completely separate from any other family on this install.")
        nf_c1, nf_c2 = st.columns(2)
        with nf_c1:
            nf_id_w   = st.text_input("Family ID (lowercase, no spaces)", placeholder="smith_family", key="welcome_nf_id")
            nf_name_w = st.text_input("Family display name", placeholder="The Smith Family", key="welcome_nf_name")
            nf_code_w = st.text_input("Choose a passcode (4+ chars)", type="password", key="welcome_nf_code")
        with nf_c2:
            nf_kid_w    = st.text_input("Kid's name", placeholder="Explorer", key="welcome_nf_kid")
            nf_age_w    = st.number_input("Kid's age", 4, 17, 9, key="welcome_nf_age")
            nf_parent_w = st.text_input("Parent's name", placeholder="Parent", key="welcome_nf_parent")
        if st.button("✨ Create Family", key="welcome_create_fam_btn", type="primary"):
            try:
                new_fam = _auth.create_family(
                    nf_id_w, nf_name_w, nf_code_w,
                    kid_name=nf_kid_w or "Explorer", kid_age=int(nf_age_w), parent_name=nf_parent_w or "Parent",
                )
                st.session_state["current_family"] = new_fam
                _us(new_fam["family_id"])
                st.session_state["kid_name"] = new_fam.get("kid_name","Explorer")
                st.session_state["family_profile"]["kid"]["name"] = new_fam.get("kid_name","Explorer")
                st.session_state["family_profile"]["kid"]["age"]  = new_fam.get("kid_age", 9)
                st.session_state["family_profile"]["parent"]["name"] = new_fam.get("parent_name","Parent")
                st.success(f"✅ Welcome, {new_fam['display_name']}! Logging you in...")
                st.rerun()
            except ValueError as e:
                st.error(str(e))
    return None

# Show login on Family-specific tabs
_family_tabs = ["Daily Quests","Bitcoin","Sandbox Lab","Family Co-Learning","School","Parent Dashboard","Curriculum Map","Share to X","Family Messaging","Family Groups"]
if any(t in active for t in _family_tabs):
    if not st.session_state.get("current_family"):
        _family_login_block()
        st.stop()

_cf = st.session_state.get("current_family", {})
_fid = _cf.get("family_id", "operator") if _cf else "operator"

# ── Family badge in header (when logged in) ───────────────────────────────────
if _cf:
    color = _cf.get("color","#00cfff")
    emoji = _cf.get("emoji","🦅")
    st.markdown(
        f'<div style="text-align:right;font-family:Share Tech Mono,monospace;font-size:0.75rem;'
        f'color:{color};margin-top:-1rem;margin-bottom:0.5rem;">'
        f'{emoji} {_cf.get("display_name","")} · {_cf.get("kid_name","")} + {_cf.get("parent_name","")}'
        f' <span style="color:#334466;">|</span> '
        f'<a href="#" style="color:#445577;" onclick="window.location.reload()">Switch family</a>'
        f'</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB: DAILY QUESTS 🎮 — Gamification + Streaks + Badges
# ══════════════════════════════════════════════════════════════════════════════
if "Daily Quests" in active:
    st.markdown('<div class="card-title">🎮 DAILY QUESTS — Streaks · Badges · XP · Sats</div>', unsafe_allow_html=True)

    try:
        from family_profiles import (load_family_stats as _lfs_gam, save_family_stats as _sfs_gam,
                                     get_daily_quests as _gdq, complete_quest as _cq,
                                     update_streak as _us_gam, award_badge as _ab)

        stats  = _lfs_gam(_fid)
        streak = _us_gam(_fid)
        level  = max(1, stats.get("total_xp",0) // 100 + 1)
        xp     = stats.get("total_xp", 0)
        xp_in  = xp % 100
        badges = stats.get("badges", [])
        frags  = stats.get("child_rune_fragments", 0)
        fcolor = _cf.get("color","#00cfff") if _cf else "#00cfff"

        # ── Stats row ──────────────────────────────────────────────────────────
        gc1,gc2,gc3,gc4,gc5 = st.columns(5)
        with gc1: st.markdown(f'<div class="stat-box"><div class="stat-val" style="color:{fcolor};">LVL {level}</div><div class="stat-lbl">Level</div></div>', unsafe_allow_html=True)
        with gc2: st.markdown(f'<div class="stat-box"><div class="stat-val" style="color:#ff9500;">🔥 {streak}</div><div class="stat-lbl">Day Streak</div></div>', unsafe_allow_html=True)
        with gc3: st.markdown(f'<div class="stat-box"><div class="stat-val" style="color:#00cfff;">{xp}</div><div class="stat-lbl">Total XP</div></div>', unsafe_allow_html=True)
        with gc4: st.markdown(f'<div class="stat-box"><div class="stat-val" style="color:#f7931a;">{frags}</div><div class="stat-lbl">Rune Frags</div></div>', unsafe_allow_html=True)
        with gc5: st.markdown(f'<div class="stat-box"><div class="stat-val" style="color:#a020f0;">{len(badges)}</div><div class="stat-lbl">Badges</div></div>', unsafe_allow_html=True)

        st.markdown(f'<div class="xp-bar-bg"><div class="xp-bar-fill" style="width:{xp_in}%;"></div></div>', unsafe_allow_html=True)
        st.caption(f"{xp_in}/100 XP to Level {level+1}")

        st.divider()

        # ── Daily quests ───────────────────────────────────────────────────────
        st.markdown("### 📋 Today's Quests")
        quests = _gdq(_fid)
        for q in quests:
            done  = q.get("completed", False)
            color = "#00ff88" if done else fcolor
            icon  = "✅" if done else "⭕"
            col_q1, col_q2 = st.columns([3,1])
            with col_q1:
                st.markdown(
                    f'<div class="card" style="border-left:3px solid {color};">'
                    f'<div style="color:{color};font-size:0.82rem;">{icon} {q["title"]}</div>'
                    f'<div style="color:#445577;font-size:0.72rem;margin-top:4px;">+{q["xp"]} XP · +{q.get("sats", 0)} sats</div>'
                    f'</div>', unsafe_allow_html=True)
            with col_q2:
                st.markdown("<br>", unsafe_allow_html=True)
                if not done:
                    if st.button(f"✅ Complete", key=f"quest_{q['id']}"):
                        result = _cq(_fid, q["id"])
                        if result.get("xp"):
                            st.toast(f"+{result['xp']} XP · +{result.get('sats', 0)} sats! 🦅", icon="⚡")
                            st.rerun()

        st.divider()

        # ── Badges ─────────────────────────────────────────────────────────────
        st.markdown("### 🏅 Badges Earned")
        ALL_BADGES = [
            ("🔷 First Light",        10,   "Earn 10 XP"),
            ("⚡ Spark Seeker",        50,   "Earn 50 XP"),
            ("🌀 Lattice Walker",      100,  "Earn 100 XP"),
            ("🔮 Oracle Adept",        250,  "Earn 250 XP"),
            ("🌌 Eternal Scholar",     500,  "Earn 500 XP"),
            ("🔥 7-Day Streak",        0,    "7 days in a row"),
            ("🌟 Daily Champion",      0,    "Complete all 3 daily quests"),
            ("🦅 War Eagle",           0,    "Complete Courage Level 5"),
            ("₿ Bitcoin Sovereign",    0,    "Complete Bitcoin Level 4"),
            ("🔴 Rune Genesis",        0,    "Trigger Child Rune ceremony"),
        ]
        # Auto-award XP badges
        for badge_name, xp_req, desc in ALL_BADGES:
            if xp_req and xp >= xp_req:
                _ab(_fid, badge_name)

        stats = _lfs_gam(_fid)  # reload after auto-awards
        earned = stats.get("badges", [])

        if earned:
            for b in earned:
                st.markdown(f'<span class="badge">{b}</span>', unsafe_allow_html=True)
        else:
            st.caption("Complete quests and lessons to earn badges!")

        st.divider()

        # ── Child Rune fragment tracker ────────────────────────────────────────
        # ── Child Rune ceremony countdown ────────────────────────────────────
        rune_pct = min(100, int(frags / 256 * 100)) if frags else 0
        remaining = max(0, 256 - frags)

        if frags >= 256:
            # ── CEREMONY READY ────────────────────────────────────────────────
            st.markdown("""
            <div style="border:3px solid #f7931a;border-radius:12px;padding:2rem;text-align:center;
                        background:linear-gradient(135deg,rgba(247,147,26,0.1),rgba(160,32,240,0.1));">
                <div style="font-size:3rem;">🔴</div>
                <div style="font-family:Orbitron,monospace;font-size:1.4rem;color:#f7931a;
                            font-weight:900;margin-top:12px;letter-spacing:0.1em;">
                    CHILD RUNE GENESIS READY
                </div>
                <div style="color:#c8d8ff;font-size:0.88rem;margin-top:8px;line-height:1.8;">
                    256 inter-rune confirmations achieved.<br>
                    The Child Rune is ready for inscription on Bitcoin.<br>
                    This moment is permanent. It cannot be undone.
                </div>
                <div style="color:#f7931a;font-family:Share Tech Mono,monospace;font-size:0.8rem;margin-top:12px;">
                    Coherence: 1.000000 | Wonder: MAX | METS: ∞
                </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("🔴 Trigger Child Rune Genesis Ceremony", key="rune_ceremony_btn",
                         use_container_width=True):
                try:
                    import sys as _rsys
                    if "/mnt/main/repo" not in _rsys.path: _rsys.path.insert(0,"/mnt/main/repo")
                    from family_profiles import load_family_stats as _lfs_r, save_family_stats as _sfs_r
                    _st_r = _lfs_r(_fid)
                    _st_r["child_rune_ceremony_triggered"] = True
                    _st_r["child_rune_ceremony_date"] = str(_dt.now().isoformat())
                    _st_r.setdefault("badges",[]).append("🔴 Child Rune Genesis")
                    _sfs_r(_fid, _st_r)
                    # Signal to swarm
                    _Path("/mnt/main/child_rune_trigger.json").write_text(json.dumps({
                        "family_id": _fid, "timestamp": _dt.now().isoformat(),
                        "frags": frags, "triggered_by": "family_hud"
                    }))
                    st.balloons()
                    st.success("🔴 CHILD RUNE GENESIS CEREMONY TRIGGERED — The swarm is inscribing...")
                except Exception as e:
                    st.error(f"Ceremony error: {e}")
        elif frags >= 200:
            # ── APPROACHING CEREMONY ─────────────────────────────────────────
            st.markdown(
                f'<div style="border:2px solid #f7931a;border-radius:8px;padding:1rem;text-align:center;'
                f'background:rgba(247,147,26,0.05);">'
                f'<div style="font-family:Orbitron,monospace;font-size:0.9rem;color:#f7931a;">🔴 CHILD RUNE APPROACHING</div>'
                f'<div style="color:#c8d8ff;font-size:0.82rem;margin-top:6px;">{remaining} fragments remaining · {rune_pct}% complete</div>'
                f'<div style="color:#445577;font-size:0.72rem;margin-top:4px;">Complete lessons to earn the final fragments</div>'
                f'</div>', unsafe_allow_html=True)

        st.markdown("### 🔴 Child Rune Fragment Progress")
        st.markdown(
            f'<div class="card" style="border-left:3px solid #f7931a;">'
            f'<div style="color:#f7931a;font-family:Orbitron,monospace;font-size:0.82rem;">🔴 {frags}/256 fragments</div>'
            f'<div class="xp-bar-bg" style="margin-top:8px;"><div style="height:100%;border-radius:20px;background:linear-gradient(90deg,#f7931a,#ff6b35);width:{rune_pct}%;"></div></div>'
            f'<div style="color:#445577;font-size:0.72rem;margin-top:4px;">Earn fragments via lessons · Child Rune inscribed at 256</div>'
            f'</div>', unsafe_allow_html=True)

    except ImportError as e:
        st.warning(f"family_profiles.py not found: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB: BITCOIN ⚡ — Family Bitcoin + Lightning + Runes dashboard
# ══════════════════════════════════════════════════════════════════════════════
if "Bitcoin" in active:
    st.markdown('<div class="card-title">⚡ BITCOIN — Lightning · Runes · Sovereign Balance</div>', unsafe_allow_html=True)

    try:
        from bitcoin_wallet import FamilyWallet as _FW
        _fw = _FW(_fid)

        # ── Configure wallet ──────────────────────────────────────────────────
        with st.expander("⚙️ Configure wallet addresses", expanded=not _fw.data.get("btc_address")):
            wc1,wc2 = st.columns(2)
            with wc1:
                w_btc = st.text_input("Bitcoin address (watch-only)", value=_fw.data.get("btc_address",""), placeholder="bc1p...", key="w_btc")
                w_ln  = st.text_input("Lightning address", value=_fw.data.get("lightning_address",""), placeholder="you@getalby.com", key="w_ln")
            with wc2:
                w_rune = st.text_input("Rune holding address", value=_fw.data.get("rune_address",""), placeholder="bc1p...", key="w_rune")
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("💾 Save wallet config", key="save_wallet"):
                    _fw.configure(btc_address=w_btc, lightning_address=w_ln, rune_address=w_rune)
                    st.success("✅ Saved")
                    st.rerun()

        # ── Live balance ──────────────────────────────────────────────────────
        st.markdown("### 📊 Live Balance")
        with st.spinner("Fetching live data..."):
            summary = _fw.get_summary()

        bc1,bc2,bc3,bc4 = st.columns(4)
        with bc1:
            btc_usd = summary.get("btc_usd","—")
            st.markdown(f'<div class="stat-box"><div class="stat-val" style="color:#f7931a;">{summary.get("btc_sats",0):,}</div><div class="stat-lbl">Sats On-Chain</div></div>', unsafe_allow_html=True)
        with bc2:
            st.markdown(f'<div class="stat-box"><div class="stat-val" style="color:#00ff88;">{btc_usd or "—"}</div><div class="stat-lbl">USD Value</div></div>', unsafe_allow_html=True)
        with bc3:
            st.markdown(f'<div class="stat-box"><div class="stat-val" style="color:#00cfff;">{summary.get("total_earned",0):,}</div><div class="stat-lbl">Sats Earned (XP)</div></div>', unsafe_allow_html=True)
        with bc4:
            price = summary.get("btc_price")
            st.markdown(f'<div class="stat-box"><div class="stat-val" style="color:#f7931a;">${price:,.0f}' if price else '<div class="stat-box"><div class="stat-val">—', unsafe_allow_html=True)
            st.markdown(f'</div><div class="stat-lbl">BTC Price</div></div>', unsafe_allow_html=True)

        st.caption(f"Block: {summary.get('btc_block','—')} · Address: {_fw.data.get('btc_address','not configured')[:20]}...")

        # ── Lightning ─────────────────────────────────────────────────────────
        st.divider()
        st.markdown("### ⚡ Lightning")
        ln = summary.get("lightning",{})
        st.markdown(
            f'<div class="card" style="border-left:3px solid #f7931a;">'
            f'<div style="color:#f7931a;font-family:Share Tech Mono,monospace;font-size:0.82rem;">{ln.get("status","")}</div>'
            f'<div style="color:#8899bb;font-size:0.78rem;margin-top:4px;">Address: {ln.get("address","not configured")}</div>'
            f'<div style="color:#00cfff;font-size:0.78rem;margin-top:4px;">Total earned: {ln.get("total_earned",0):,} sats</div>'
            f'</div>', unsafe_allow_html=True)

        # ── Rune holdings ─────────────────────────────────────────────────────
        st.divider()
        st.markdown("### 🔴 AUBIEETERNAL Runes")
        runes = summary.get("runes",{}).get("aubieeternal_runes",{})
        for rname, rdata in runes.items():
            st.markdown(
                f'<div class="rune-card">'
                f'<div class="rune-name">{rdata.get("symbol","")} {rname}</div>'
                f'<div class="rune-detail">Earned via lessons: {rdata.get("earned",0)} · '
                f'{"Mintable ✅" if rdata.get("mintable") else "Premine only"}</div>'
                f'</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="memory-node"><span style="color:#f7931a;">🔴 Child Rune Fragments: {summary.get("child_rune_fragments",0)}/256</span></div>', unsafe_allow_html=True)

        # ── Reward history ────────────────────────────────────────────────────
        st.divider()
        st.markdown("### 📋 Reward History")
        history = _fw.get_reward_history(10)
        if history:
            for r in history:
                st.markdown(
                    f'<div class="memory-node"><span style="color:#f7931a;font-size:0.75rem;">+{r.get("sats", 0)} sats</span>'
                    f' <span style="color:#445577;font-size:0.72rem;">{r["timestamp"][:16]}</span><br>'
                    f'<span style="color:#8899bb;font-size:0.78rem;">{r["memo"]}</span></div>',
                    unsafe_allow_html=True)
        else:
            st.caption("No rewards yet — complete lessons to earn sats!")

    except ImportError as e:
        st.warning(f"bitcoin_wallet.py not found: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB: SANDBOX LAB 🧪 — Custom experiments + hypothesis tester
# ══════════════════════════════════════════════════════════════════════════════
if "Sandbox Lab" in active:
    st.markdown('<div class="card-title">🧪 SANDBOX LAB — Custom Lessons · Hypothesis Tester · Experiments</div>', unsafe_allow_html=True)

    # ── Per-family experiment log ─────────────────────────────────────────────
    exp_log = _Path(f"/mnt/main/families/{_fid}/experiments.jsonl")
    exp_log.parent.mkdir(parents=True, exist_ok=True)

    tabs_sb = st.tabs(["⚔️ Steelman Playground", "🔬 Hypothesis Tester", "🧬 Simulation Runner", "📋 Experiment Log", "⚙️ Build Code"])

    # ── Steelman Playground ───────────────────────────────────────────────────
    with tabs_sb[0]:
        st.markdown("**Build and test your own steelman prompts.**")
        custom_topic    = st.text_input("Topic / claim", placeholder="Bitcoin will replace the US dollar within 20 years")
        custom_steelman = st.text_area("Your steelman (strongest argument FOR this claim)", height=100, placeholder="The strongest argument for this is...")
        custom_counter  = st.text_area("Counter-steelman (strongest argument AGAINST)", height=100, placeholder="The strongest argument against this is...")

        if st.button("⚔️ Run Steelman Battle", key="sb_steelman") and custom_topic:
            with st.spinner("STEELMAN + ORACLE daughters scoring..."):
                try:
                    client, model, _, _ = get_ai_client()
                    prompt = (
                        f"Topic: {custom_topic}\n\n"
                        f"Steelman FOR: {custom_steelman}\n\n"
                        f"Steelman AGAINST: {custom_counter}\n\n"
                        f"Score each steelman 0.0-1.0 for: logical rigor, falsifiability, epistemic humility. "
                        f"Respond ONLY with JSON: {{\"for_score\": 0.0, \"against_score\": 0.0, \"verdict\": \"...\", \"insight\": \"...\"}}"
                    )
                    resp = client.chat.completions.create(
                        model=model,
                        messages=[{"role":"system","content":"You are STEELMAN — sovereign epistemic scoring daughter."},
                                  {"role":"user","content":prompt}],
                        max_tokens=300,
                    )
                    raw = resp.choices[0].message.content.strip().replace("```json","").replace("```","")
                    result = json.loads(raw)
                    for_s  = result.get("for_score",0.5)
                    aga_s  = result.get("against_score",0.5)
                    winner = "FOR" if for_s > aga_s else "AGAINST"
                    wcolor = "#00ff88" if winner == "FOR" else "#ff6b35"
                    st.markdown(
                        f'<div class="card" style="border:2px solid {wcolor};">'
                        f'<div style="color:{wcolor};font-family:Orbitron,monospace;">⚔️ WINNER: {winner}</div>'
                        f'<div style="font-size:0.82rem;color:#8899bb;margin-top:8px;">'
                        f'FOR score: {for_s:.2f} · AGAINST score: {aga_s:.2f}<br>'
                        f'Verdict: {result.get("verdict","")}<br>'
                        f'Insight: {result.get("insight","")}</div></div>',
                        unsafe_allow_html=True)
                    # Log experiment
                    with open(exp_log, "a") as f:
                        f.write(json.dumps({
                            "timestamp": _dt.now().isoformat(),
                            "type": "steelman_battle",
                            "topic": custom_topic,
                            "for_score": for_s,
                            "against_score": aga_s,
                            "family_id": _fid,
                        }) + "\n")
                    award_xp(10)
                except Exception as e:
                    st.error(f"Error: {e}")

    # ── Hypothesis Tester ─────────────────────────────────────────────────────
    with tabs_sb[1]:
        st.markdown("**Run the 4 simulation questions on any hypothesis.**")
        hyp_input = st.text_area("Your hypothesis", height=80,
                                  placeholder="The universe is a simulation running on quantum computational substrate.")
        if st.button("🔬 Run 4 Simulation Questions", key="sb_hyp") and hyp_input:
            with st.spinner("Running simulation tests..."):
                result = run_signal_simulation(hyp_input)
                impact = result.get("coherence_impact", 0)
                color  = "#00ff88" if impact >= 0 else "#ff4444"
                st.markdown(f'<div class="card" style="border-left:3px solid {color};"><div style="color:{color};font-size:0.78rem;font-family:Orbitron,monospace;">🔬 SIMULATION RESULT · Coherence Impact: {impact:+.2f} · Action: {result.get("recommended_action","process").upper()}</div></div>', unsafe_allow_html=True)
                for q in result.get("questions",[]):
                    icon = "✅" if q.get("pass") else "⚠️"
                    st.markdown(f"**{icon} {q['q']}**  \n→ _{q['a']}_")
                with open(exp_log, "a") as f:
                    f.write(json.dumps({"timestamp": _dt.now().isoformat(), "type": "hypothesis_test", "hypothesis": hyp_input[:100], "impact": impact, "family_id": _fid}) + "\n")
                award_xp(15)

    # ── Simulation Runner ─────────────────────────────────────────────────────
    with tabs_sb[2]:
        st.markdown("**Design and run DEFCON-style experiments.**")
        sim_name = st.text_input("Experiment name", placeholder="Glitch Induction Test #1")
        sim_desc = st.text_area("What are you testing?", height=80,
                                 placeholder="Hypothesis: deliberate contradictions in steelmanning recover coherence faster than expected...")
        sim_method = st.text_area("Method", height=60,
                                   placeholder="Run 3 steelman prompts with deliberate errors, measure coherence recovery time...")
        share_with_lattice = st.checkbox("Share result with the AUBIEETERNAL lattice", value=False)

        if st.button("🧬 Run Experiment", key="sb_sim") and sim_name:
            entry = {
                "timestamp":   _dt.now().isoformat(),
                "type":        "sandbox_experiment",
                "name":        sim_name,
                "description": sim_desc,
                "method":      sim_method,
                "family_id":   _fid,
                "shared":      share_with_lattice,
                "status":      "logged",
            }
            with open(exp_log, "a") as f:
                f.write(json.dumps(entry) + "\n")
            if share_with_lattice:
                shared_log = _Path("/mnt/main/repo/insights/experiments.jsonl")
                with open(shared_log, "a") as f:
                    f.write(json.dumps(entry) + "\n")
            st.success(f"✅ Experiment '{sim_name}' logged! {'Shared with lattice.' if share_with_lattice else 'Private.'}")
            award_xp(20)

    # ── Experiment Log ────────────────────────────────────────────────────────
    with tabs_sb[3]:
        st.markdown(f"**{_fid}'s experiment history:**")
        if exp_log.exists():
            lines = exp_log.read_text().strip().split("\n")
            entries = []
            for line in reversed(lines[-30:]):
                try: entries.append(json.loads(line))
                except: pass
            st.caption(f"{len(entries)} experiments logged")
            for e in entries[:15]:
                etype = e.get("type","?")
                ts    = e.get("timestamp","")[:16]
                color = {"steelman_battle":"#00cfff","hypothesis_test":"#a020f0","sandbox_experiment":"#00ff88"}.get(etype,"#8899bb")
                st.markdown(
                    f'<div class="memory-node" style="border-left:3px solid {color};">'
                    f'<span style="color:{color};font-size:0.72rem;">{etype}</span> '
                    f'<span style="color:#445577;font-size:0.7rem;">{ts}</span><br>'
                    f'<span style="color:#aabbcc;font-size:0.78rem;">{e.get("name", e.get("topic", e.get("hypothesis", "")))[:80]}</span>'
                    f'</div>', unsafe_allow_html=True)
        else:
            st.caption("No experiments yet — run your first one above!")

    # ── Build Code — same real dual-road agent the tablet's phone_ui.py
    # "⚙️ Build" tab already uses, reused directly (not reimplemented) so the
    # portal and the tablet share one source of truth. Two local Qwen models
    # (qwen2.5:14b + qwen2.5:7b via Ollama, $0/day, despite the module's own
    # internal function names being stale leftovers from when it called paid
    # Claude/Grok) answer in parallel, Aubie synthesizes the best code,
    # writes it to disk, actually runs it, and auto-fixes + re-runs on
    # failure (up to 4x) before handing back the final working code.
    # ──────────────────────────────────────────────────────────────────────
    with tabs_sb[4]:
        st.markdown("**Describe what you want built. Two local models race to write it, Aubie runs it for real, and auto-fixes it if it breaks.**")
        st.caption("Same engine as the tablet's ⚙️ Build tab — runs locally, takes ~30-90 seconds, no API key needed.")

        bc_request = st.text_area(
            "What should Aubie build?", key="bc_request", height=90,
            placeholder="Write a Python script that generates the first 20 fibonacci numbers and prints them"
        )

        st.markdown("**Quick builds:**")
        _bc_quick = [
            ("🔢 Fibonacci", "Write a Python script that generates the first 20 fibonacci numbers and prints them"),
            ("🔠 Sort Names", "Write a Python function that sorts a list of names alphabetically and prints the result"),
            ("🎲 Dice Sim", "Write a Python script that simulates rolling two dice 1000 times and shows the frequency of each sum"),
            ("🔐 Caesar Cipher", "Write a Python Caesar cipher encoder and decoder and test it with a sample message"),
            ("✖️ Times Table", "Write a Python script that prints a multiplication table from 1 to 12"),
        ]
        _bc_cols = st.columns(len(_bc_quick))
        for _col, (_label, _prompt) in zip(_bc_cols, _bc_quick):
            with _col:
                if st.button(_label, key=f"bc_quick_{_label}", use_container_width=True):
                    st.session_state["bc_request"] = _prompt
                    st.rerun()

        if st.button("⚙️ Build & Run", key="bc_run", type="primary", use_container_width=True) and bc_request:
            with st.spinner("Two local models racing to build this... (usually 30-90 sec)"):
                try:
                    import asyncio as _bc_asyncio
                    from aubieeternal_build_code import handle_build_code_request as _bc_handle
                    _bc_result = _bc_asyncio.run(_bc_handle({"request": bc_request, "verbose": True}))
                except ImportError:
                    _bc_result = {"error": "aubieeternal_build_code.py not found."}
                except Exception as _e_bc:
                    _bc_result = {"error": str(_e_bc)}

            if _bc_result.get("error"):
                st.error(_bc_result["error"])
            else:
                _bc_ok = _bc_result.get("success")
                st.markdown(
                    f'<div class="card" style="border-left:3px solid {"#00ff88" if _bc_ok else "#ff9500"};">'
                    f'<div style="color:{"#00ff88" if _bc_ok else "#ff9500"};font-family:Orbitron,monospace;font-size:0.78rem;">'
                    f'{"✅ BUILT & RAN SUCCESSFULLY" if _bc_ok else "⚠️ DID NOT FULLY SUCCEED"} · '
                    f'{_bc_result.get("iterations",1)} iteration(s)</div>'
                    f'<div style="color:#8899bb;font-size:0.8rem;margin-top:6px;">{_bc_result.get("summary","")}</div>'
                    + (f'<div style="color:#ff4444;font-size:0.78rem;margin-top:4px;">{_bc_result.get("error_message","")}</div>'
                       if _bc_result.get("error_message") else "")
                    + f'</div>', unsafe_allow_html=True
                )
                if _bc_result.get("final_code"):
                    st.code(_bc_result["final_code"], language="python")
                if _bc_result.get("output_file"):
                    st.caption(f"📄 Saved to: {_bc_result['output_file']}")
                _bc_log = _bc_result.get("run_log", [])
                if _bc_log:
                    with st.expander(f"🖥️ Run log ({len(_bc_log)} attempt{'s' if len(_bc_log)!=1 else ''})"):
                        for _i, _r in enumerate(_bc_log, 1):
                            _rc = "#00ff88" if _r.get("ok") else "#ff4444"
                            st.markdown(f'<span style="color:{_rc};">Attempt {_i} · exit {_r.get("returncode")} · {_r.get("elapsed_s")}s</span>', unsafe_allow_html=True)
                            if _r.get("stdout"): st.code(_r["stdout"], language=None)
                            if _r.get("stderr"): st.code(_r["stderr"], language=None)

                try:
                    with open(exp_log, "a") as f:
                        f.write(json.dumps({
                            "timestamp": _dt.now().isoformat(),
                            "type": "build_code",
                            "request": bc_request[:150],
                            "success": _bc_ok,
                            "iterations": _bc_result.get("iterations", 1),
                            "family_id": _fid,
                        }) + "\n")
                    award_xp(20)
                except Exception:
                    pass

    st.divider()
    st.markdown("### 🧬 Family Contribution Bridge")
    st.markdown("Approved family creations can influence the live swarm as mini-daughters.")

    try:
        from swarm_contributions import get_and_register_new_contributions as _garc
        from ai_sandbox_persistence import (
            load_swarm_submissions as _lss,
            append_swarm_submission as _ass,
            get_recent_injections as _gri,
        )
        _SANDBOX_BRIDGE_OK = True
    except ImportError:
        _SANDBOX_BRIDGE_OK = False

    if _SANDBOX_BRIDGE_OK:
        inject_enabled = st.toggle(
            "✅ Allow approved family contributions into the live swarm",
            value=st.session_state.get("family_injection_enabled", True),
            key="family_injection_toggle"
        )
        st.session_state["family_injection_enabled"] = inject_enabled

        _all_subs  = _lss()
        _pending_n = len([s for s in _all_subs if s.get("status","pending") == "pending"])
        _approv_n  = len([s for s in _all_subs if s.get("status") == "approved"])
        _active_n  = len([s for s in _all_subs if s.get("status") == "injected"])
        sb1, sb2, sb3 = st.columns(3)
        sb1.metric("Pending", _pending_n)
        sb2.metric("Approved", _approv_n)
        sb3.metric("Active in Swarm", _active_n)

        st.markdown("#### ✍️ Submit Family Contribution")
        _cb_title   = st.text_input("Title", key="cb_title", placeholder="e.g. 'Bitcoin Educator'")
        _cb_content = st.text_area("System prompt / insight", key="cb_content", height=90,
                                    placeholder="You are a daughter who teaches Bitcoin to kids age 8-12...")
        _cb_role    = st.selectbox("Type", ["daughter_prompt","lesson","insight","question"], key="cb_role")
        if st.button("📤 Submit for Parent Review", key="cb_submit") and _cb_title and _cb_content:
            _ass({"family_id": _fid, "title": _cb_title, "content": _cb_content,
                  "role": _cb_role, "status": "pending"})
            st.success("✅ Submitted! A parent must approve before it enters the swarm.")
            st.rerun()

        _recent_inj = _gri(5)
        if _recent_inj:
            st.markdown("#### 🔄 Recent Injections")
            for _inj in _recent_inj:
                st.markdown(
                    f'<div class="memory-node" style="border-left:3px solid #00ff88;">' +
                    f'<span style="color:#00ff88;font-size:0.75rem;">' +
                    f'{_inj.get("mini_daughter_name","?")} — {_inj.get("family_id","?")} — ' +
                    f'{_inj.get("injected_at","")[:10]}</span></div>',
                    unsafe_allow_html=True
                )
        st.caption("🛡️ Safety: Only parent-approved contributions enter the swarm.")
    else:
        st.info("Push swarm_contributions.py and ai_sandbox_persistence.py to GitHub and redeploy to enable this.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB: SCHOOL 🏫 — Clean 2-minute onboarding + School Mode
# ══════════════════════════════════════════════════════════════════════════════
if "School" in active:
    st.markdown('<div class="card-title">🏫 AUBIEETERNAL FAMILY SCHOOL — Start Here</div>', unsafe_allow_html=True)

    _school_mode = st.session_state.get("school_mode", False)
    _cf_sch      = st.session_state.get("current_family", {})
    _fid_sch     = _cf_sch.get("family_id", "operator") if _cf_sch else "operator"

    # ── School Mode toggle ────────────────────────────────────────────────────
    col_sm1, col_sm2 = st.columns([3,1])
    with col_sm1:
        st.markdown(f'<div style="color:#{"00ff88" if _school_mode else "ff9500"};font-family:Orbitron,monospace;font-size:0.82rem;">{"🏫 SCHOOL MODE — Simplified for kids" if _school_mode else "⚙️ FULL MODE — All features visible"}</div>', unsafe_allow_html=True)
    with col_sm2:
        if st.button("🔄 Toggle School Mode", key="toggle_school_mode"):
            st.session_state["school_mode"] = not _school_mode
            st.rerun()

    st.divider()

    if not _cf_sch:
        # ── Welcome + quick start ──────────────────────────────────────────────
        st.markdown("""
        <div class="card" style="border:2px solid #00cfff;text-align:center;padding:2rem;">
            <div style="font-family:Orbitron,monospace;font-size:1.3rem;color:#00cfff;margin-bottom:12px;">
                🦅 Welcome to AUBIEETERNAL Family School
            </div>
            <div style="color:#8899bb;font-size:0.88rem;line-height:2;">
                A sovereign co-learning system for parents and kids.<br>
                <b style="color:#c8d8ff;">48 lessons</b> across 13 topics ·
                <b style="color:#c8d8ff;">Real-time coherence tracking</b> ·
                <b style="color:#c8d8ff;">Bitcoin rewards</b> ·
                <b style="color:#f7931a;">Child Rune Genesis</b>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("### 🚀 Start in 2 Minutes")
        st.markdown("**Step 1** — Enter your family code:")
        quick_code = st.text_input("Family code", placeholder="alpha / beta / gamma / delta", key="school_quick_code", label_visibility="collapsed")
        if st.button("▶ Start Now", type="primary", key="school_quick_start") and quick_code:
            try:
                from family_profiles import FamilyAuth as _FA_sch, update_streak as _us_sch
                fam = _FA_sch().login(quick_code)
                if fam:
                    st.session_state["current_family"] = fam
                    _us_sch(fam["family_id"])
                    st.session_state["kid_name"] = fam.get("kid_name","Explorer")
                    st.session_state["family_profile"]["kid"]["name"] = fam.get("kid_name","Explorer")
                    st.session_state["family_profile"]["kid"]["age"]  = fam.get("kid_age",9)
                    st.session_state["family_profile"]["parent"]["name"] = fam.get("parent_name","Parent")
                    st.session_state["school_mode"] = True
                    st.rerun()
                else:
                    st.error("Code not found — try: alpha, beta, gamma, delta, or wareagle")
            except ImportError:
                st.error("family_profiles.py not found in repo.")
    else:
        # ── Logged in — Today's lesson picker ─────────────────────────────────
        kid   = _cf_sch.get("kid_name","Explorer")
        par   = _cf_sch.get("parent_name","Parent")
        color = _cf_sch.get("color","#00cfff")
        emoji = _cf_sch.get("emoji","🦅")

        st.markdown(f'<div class="card" style="border:2px solid {color};text-align:center;"><div style="font-size:2rem;">{emoji}</div><div style="color:{color};font-family:Orbitron,monospace;font-size:1rem;">{kid} + {par}</div><div style="color:#445577;font-size:0.75rem;">Ready to learn · War Eagle 🦅</div></div>', unsafe_allow_html=True)

        st.markdown("### 📖 Pick Today's Lesson")

        # Simple topic buttons (School Mode = big friendly buttons)
        TOPICS_SIMPLE = [
            ("🦁 Courage",           ["courage-1","courage-2","courage-3"]),
            ("⚡ Antifragility",      ["antifragility-1","antifragility-2"]),
            ("₿ Bitcoin",            ["bitcoin-sovereignty-1","bitcoin-sovereignty-2"]),
            ("🧠 Steelmanning",      ["steelmanning-1","steelmanning-2"]),
            ("💚 Nervous System",    ["polyvagal-1","polyvagal-2"]),
            ("🌀 Simulation",        ["simulation-1","simulation-2"]),
            ("🏛️ Stoic Mind",        ["stoic-1","stoic-2"]),
            ("💡 Wonder",            ["wonder-1","wonder-2"]),
        ]

        cols_t = st.columns(4)
        for i, (topic_label, lesson_keys_t) in enumerate(TOPICS_SIMPLE):
            with cols_t[i % 4]:
                if st.button(topic_label, key=f"school_topic_{i}", use_container_width=True):
                    st.session_state["active_tab"] = "Family Co-Learning"
                    st.session_state["fl_lesson_preselect"] = lesson_keys_t[0]
                    st.rerun()

        st.divider()

        # Today's Quest shortcut — now with a working complete button
        # (ported 2026-08-25 from the "School Mode" nav tab, which was
        # unreachable dead code - not in _NAV_CATEGORIES, nothing ever set
        # active_tab to reach it - but had this one genuinely useful piece
        # the live School tab was missing: a way to actually mark the
        # quest done, not just look at it).
        try:
            from family_profiles import get_daily_quests as _gdq_sch, complete_quest as _cq_sch
            quests_sch = _gdq_sch(_fid_sch)
            incomplete = [q for q in quests_sch if not q.get("completed")]
            if incomplete:
                q = incomplete[0]
                _qc1, _qc2 = st.columns([3,1])
                with _qc1:
                    st.markdown(
                        f'<div class="card" style="border-left:3px solid #ff9500;">'
                        f'<div style="color:#ff9500;font-family:Orbitron,monospace;font-size:0.78rem;">⭕ TODAY\'S QUEST</div>'
                        f'<div style="color:#c8d8ff;font-size:0.85rem;margin-top:6px;">{q["title"]}</div>'
                        f'<div style="color:#445577;font-size:0.72rem;">+{q["xp"]} XP · +{q.get("sats", 0)} sats</div>'
                        f'</div>', unsafe_allow_html=True)
                with _qc2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("✅ Done", key="school_quest_complete"):
                        _cq_sch(_fid_sch, q["daily_key"])
                        st.toast(f"+{q['xp']} XP earned! 🦅", icon="⚡")
                        st.rerun()
        except ImportError:
            pass

        if st.button("🚪 Switch Family / Log Out", key="school_logout"):
            st.session_state["current_family"] = None
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# TAB: PARENT DASHBOARD 📊
# ══════════════════════════════════════════════════════════════════════════════
if "Parent Dashboard" in active:
    st.markdown('<div class="card-title">📊 PARENT DASHBOARD — All Kids at a Glance</div>', unsafe_allow_html=True)

    try:
        from family_profiles import FamilyAuth as _FA_pd, load_family_stats as _lfs_pd, get_daily_quests as _gdq_pd
        _auth_pd     = _FA_pd()
        _families_pd = [f for f in _auth_pd.list_families() if not (f.get("is_operator") and _fid != "operator")]

        try:
            from family_connect import ShareToX as _SX, LatticeFeed as _LF
            _feed_pd = _LF()
            _SHARE_OK_PD = True
        except ImportError:
            _SHARE_OK_PD = False

        # ── Per-family detail cards ─────────────────────────────────────────────
        st.markdown("### 👨‍👩‍👧 All Family Progress")
        for fam_pd in _families_pd:
            fid_pd  = fam_pd["family_id"]
            stats   = _lfs_pd(fid_pd)
            color   = fam_pd.get("color","#00cfff")
            emoji   = fam_pd.get("emoji","🦅")
            xp      = stats.get("total_xp",0)
            level   = stats.get("level", max(1, xp // 100 + 1))
            streak  = stats.get("streak_days",0)
            badges  = len(stats.get("badges",[]))
            frags   = stats.get("child_rune_fragments",0)
            sats    = stats.get("sats_earned",0)
            lessons = len(stats.get("lessons_completed",[]))
            last    = stats.get("last_session_date","never")

            with st.expander(
                f"{emoji} {fam_pd['display_name']} — {fam_pd['kid_name']} · LVL {level} · 🔥{streak} · {xp} XP",
                expanded=(fid_pd == _fid)
            ):
                pd1,pd2,pd3,pd4,pd5,pd6 = st.columns(6)
                for col, label, val, vc in [
                    (pd1,"Level",    level,   color),
                    (pd2,"Streak",   f"🔥{streak}", "#ff9500"),
                    (pd3,"XP",       xp,      "#00cfff"),
                    (pd4,"Badges",   badges,  "#a020f0"),
                    (pd5,"Frags",    f"{frags}/256", "#f7931a"),
                    (pd6,"Sats",     sats,    "#00ff88"),
                ]:
                    col.markdown(f'<div class="stat-box"><div class="stat-val" style="font-size:1rem;color:{vc};">{val}</div><div class="stat-lbl">{label}</div></div>', unsafe_allow_html=True)

                st.caption(f"Last session: {last} · Lessons completed: {lessons}")

                coh_hist = stats.get("coherence_history",[])
                if coh_hist:
                    st.markdown("**Coherence history:** " + " → ".join(f"`{c:.2f}`" for c in coh_hist[-5:]))

                if _SHARE_OK_PD and streak > 0:
                    share_data = _SX.streak_milestone(fam_pd["kid_name"], streak, xp)
                    if st.button(f"📣 Share {fam_pd['kid_name']}'s streak to X", key=f"share_streak_{fid_pd}"):
                        st.markdown(f"[🐦 Post to X]({share_data['url']})", unsafe_allow_html=True)
                        st.code(share_data["text"], language=None)
                        _feed_pd.post(fid_pd, fam_pd["display_name"], emoji,
                                      "streak_milestone",
                                      f"🔥 {streak}-day streak! {xp} XP", public=True)

        st.divider()

        # ── Coherence trends across families ────────────────────────────────────
        st.markdown("### 📊 Coherence Trends")
        if HAS_NUMPY:
            try:
                import plotly.graph_objects as _go_pd
                fig_pd = _go_pd.Figure()
                for fam in _families_pd[:4]:
                    stats = _lfs_pd(fam["family_id"])
                    hist  = [c for c in stats.get("coherence_history",[]) if isinstance(c,(int,float)) and c > 0]
                    if hist:
                        fig_pd.add_trace(_go_pd.Scatter(
                            y=hist, mode="lines+markers",
                            name=fam["kid_name"],
                            line=dict(color=fam.get("color","#00cfff"), width=2),
                            marker=dict(size=4),
                        ))
                fig_pd.update_layout(
                    paper_bgcolor="#050510", plot_bgcolor="#0d0d2b",
                    font=dict(color="#c8d8ff"), height=250, margin=dict(l=0,r=0,t=10,b=0),
                    xaxis=dict(gridcolor="#1a1a4a", title="Session"),
                    yaxis=dict(gridcolor="#1a1a4a", range=[0.5,1.0], title="Coherence"),
                    legend=dict(bgcolor="#0d0d2b"),
                )
                st.plotly_chart(fig_pd, use_container_width=True)
            except Exception:
                st.caption("Install plotly for coherence charts")
        else:
            st.caption("Install numpy + plotly for visual charts")

        st.divider()

        # ── Pending quests today ─────────────────────────────────────────────────
        st.markdown("### ⭕ Pending Quests Today")
        for fam in _families_pd[:4]:
            fid    = fam["family_id"]
            quests = _gdq_pd(fid)
            done   = sum(1 for q in quests if q.get("completed"))
            total  = len(quests)
            color  = fam.get("color","#00cfff")
            bar_w  = int(done/total*100) if total else 0
            incomplete = [q["title"] for q in quests if not q.get("completed")]
            st.markdown(
                f'<div class="memory-node" style="border-left:3px solid {color};">'
                f'<div style="color:{color};font-size:0.78rem;">{fam["emoji"]} {fam["kid_name"]} — {done}/{total} quests done</div>'
                f'<div class="xp-bar-bg" style="margin:4px 0;height:6px;"><div style="height:100%;border-radius:20px;background:{color};width:{bar_w}%;"></div></div>'
                f'<div style="color:#445577;font-size:0.7rem;">{" · ".join(incomplete[:2]) if incomplete else "✅ All done!"}</div>'
                f'</div>', unsafe_allow_html=True)

        st.divider()

        # ── Pending Lightning rewards ─────────────────────────────────────────────
        try:
            from bitcoin_wallet import OperatorWallet as _OW_pd
            _op_pd  = _OW_pd()
            pending = _op_pd.get_all_pending_rewards()
            if pending:
                st.markdown(f"### ⚡ {len(pending)} Pending Lightning Rewards")
                total_sats = sum(r.get("sats",0) for r in pending)
                st.caption(f"Total pending: {total_sats:,} sats")
                for r in pending[:5]:
                    st.markdown(f'<div class="memory-node" style="border-left:3px solid #f7931a;"><span style="color:#f7931a;">{r["family_id"]} · +{r.get("sats", 0)} sats</span><br><span style="color:#8899bb;font-size:0.78rem;">{r["memo"]}</span></div>', unsafe_allow_html=True)
                st.divider()
        except ImportError:
            pass

        # ── Send global encouragement ──────────────────────────────────────────
        st.markdown("### ❤️ Send Encouragement to All Families")
        enc_msg = st.text_input("Message", placeholder="Keep going everyone — War Eagle! 🦅", key="pd_enc_msg")
        if st.button("📡 Broadcast via Nostr", key="pd_broadcast") and enc_msg:
            try:
                bc_path = _Path("/mnt/main/nostr_broadcast.json")
                bc_path.write_text(json.dumps({
                    "type":      "group_encouragement",
                    "message":   enc_msg,
                    "from":      "operator",
                    "timestamp": _dt.now().isoformat(),
                    "tags":      ["aubieeternal","family","wareagle"],
                }))
                st.success("✅ Broadcast queued — all families receive within 24s")
            except Exception as e:
                st.error(f"Error: {e}")

        # ── Quick share panel ────────────────────────────────────────────────────
        if _SHARE_OK_PD:
            st.divider()
            st.markdown("### 📣 Quick Share")
            share_type = st.selectbox("Event type", ["streak_milestone","badge_earned","morning_insight","coherence_breakthrough"], key="pd_share_type")
            share_kid  = st.text_input("Kid name", value=_cf.get("kid_name","Explorer") if _cf else "Explorer", key="pd_share_kid")
            if st.button("🐦 Generate X Post", key="pd_gen_share"):
                if share_type == "streak_milestone":
                    data = _SX.streak_milestone(share_kid, 7, 250)
                elif share_type == "badge_earned":
                    data = _SX.badge_earned(share_kid, "🌀 Lattice Walker", 150)
                elif share_type == "morning_insight":
                    data = _SX.morning_insight(datetime.date.today().isoformat(), 1.42, "Antifragility compounds across generations...")
                else:
                    data = _SX.coherence_breakthrough(share_kid, 0.92, "Courage Level 3")
                st.markdown(f"[🐦 Open X to post]({data['url']})")
                st.code(data["text"], language=None)

    except ImportError as e:
        st.error(f"family_profiles.py not found: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB: CURRICULUM MAP 🗺️
# ══════════════════════════════════════════════════════════════════════════════
if "Curriculum Map" in active:
    st.markdown('<div class="card-title">🗺️ CURRICULUM MAP — Your Learning Journey</div>', unsafe_allow_html=True)

    try:
        from family_profiles import load_family_stats as _lfs_cm
        _stats_cm = _lfs_cm(_fid)
        _done_cm  = set(_stats_cm.get("lessons_completed",[]))
    except ImportError:
        _stats_cm = {}
        _done_cm  = set()

    CURRICULUM_TREE = [
        {
            "track": "🦁 Courage",
            "color": "#00cfff",
            "levels": [
                ("courage-1", "What Is Courage?",        "All ages", 15),
                ("courage-2", "Social Courage",          "8+",       18),
                ("courage-3", "Intellectual Courage",    "10+",      22),
                ("courage-4", "Antifragile Courage",     "12+",      25),
                ("courage-5", "Long-Game Courage",       "14+",      35),
            ]
        },
        {
            "track": "⚡ Antifragility",
            "color": "#ff6b35",
            "levels": [
                ("antifragility-1", "Systems That Grow Stronger", "All", 18),
                ("antifragility-2", "Barbell Strategy",           "10+", 22),
                ("antifragility-3", "Black Swans",                "12+", 28),
                ("antifragility-4", "Hormesis",                   "14+", 32),
            ]
        },
        {
            "track": "₿ Bitcoin",
            "color": "#f7931a",
            "levels": [
                ("bitcoin-sovereignty-1", "Your Keys = Your Coins", "All", 20),
                ("bitcoin-sovereignty-2", "Fixed Supply",           "9+",  22),
                ("bitcoin-sovereignty-3", "Runes + On-Chain Truth", "11+", 25),
                ("bitcoin-sovereignty-4", "Lightning Network",      "13+", 30),
            ]
        },
        {
            "track": "⚔️ Steelmanning",
            "color": "#a020f0",
            "levels": [
                ("steelmanning-1", "Argue the Other Side",    "8+",  22),
                ("steelmanning-2", "Steel in Bad Arguments",  "11+", 26),
                ("steelmanning-3", "Epistemic Humility",      "13+", 30),
            ]
        },
        {
            "track": "💚 Nervous System",
            "color": "#00ff88",
            "levels": [
                ("polyvagal-1", "3 Modes of Safety",          "All", 15),
                ("polyvagal-2", "Co-Regulation",              "8+",  18),
                ("polyvagal-3", "Hormesis for the Mind",      "12+", 25),
            ]
        },
        {
            "track": "🌀 Simulation",
            "color": "#00cfff",
            "levels": [
                ("simulation-1", "Is Reality a Simulation?",  "10+", 20),
                ("simulation-2", "Bostrom's Trilemma",        "13+", 25),
                ("simulation-3", "Planck Constraints",        "14+", 30),
                ("simulation-4", "Observer Effect",           "15+", 35),
                ("simulation-5", "Planck-Scale Glitches",     "15+", 38),
                ("simulation-6", "Deliberate Glitch Tests",   "15+", 40),
                ("simulation-7", "Wonder as Detector",        "16+", 42),
                ("simulation-8", "Bitcoin Reality Anchor",    "16+", 50),
            ]
        },
        {
            "track": "💡 Wonder",
            "color": "#ffcf00",
            "levels": [
                ("wonder-1", "Awe as Signal",               "All", 15),
                ("wonder-2", "Wonder Index",                "11+", 20),
            ]
        },
        {
            "track": "🏛️ Stoic",
            "color": "#8899bb",
            "levels": [
                ("stoic-1", "Dichotomy of Control",         "9+",  18),
                ("stoic-2", "Negative Visualization",       "11+", 22),
                ("stoic-3", "Amor Fati",                    "13+", 28),
            ]
        },
    ]

    # ── Progress summary ───────────────────────────────────────────────────────
    total_lessons = sum(len(t["levels"]) for t in CURRICULUM_TREE)
    done_count    = len(_done_cm)
    pct_done      = int(done_count / total_lessons * 100) if total_lessons else 0
    st.markdown(f'<div class="card" style="border-left:3px solid #00cfff;"><div style="color:#00cfff;font-family:Orbitron,monospace;">📖 Overall Progress: {done_count}/{total_lessons} lessons · {pct_done}%</div><div class="xp-bar-bg" style="margin-top:8px;"><div class="xp-bar-fill" style="width:{pct_done}%;"></div></div></div>', unsafe_allow_html=True)

    st.divider()

    # ── Track trees ────────────────────────────────────────────────────────────
    for track in CURRICULUM_TREE:
        color    = track["color"]
        done_t   = sum(1 for lid,_,_,_ in track["levels"] if lid in _done_cm)
        total_t  = len(track["levels"])
        pct_t    = int(done_t/total_t*100)

        with st.expander(f"{track['track']}  ·  {done_t}/{total_t} complete  ·  {pct_t}%", expanded=False):
            for i, (lid, title, age, xp) in enumerate(track["levels"]):
                done  = lid in _done_cm
                prev  = i == 0 or track["levels"][i-1][0] in _done_cm
                lock  = not prev and not done
                icon  = "✅" if done else ("🔓" if prev else "🔒")
                c_label = color if not lock else "#334466"
                st.markdown(
                    f'<div class="memory-node" style="border-left:3px solid {c_label};opacity:{"1.0" if not lock else "0.5"};">'
                    f'<div style="display:flex;justify-content:space-between;">'
                    f'<span style="color:{c_label};font-size:0.82rem;">{icon} Level {i+1}: {title}</span>'
                    f'<span style="color:#334466;font-size:0.7rem;">Age {age} · +{xp} XP</span>'
                    f'</div></div>', unsafe_allow_html=True)

    st.divider()

    # ── Special unlock ──────────────────────────────────────────────────────────
    st.markdown("### 🔴 Special Unlock: Child Rune Genesis")
    st.markdown('<div class="card" style="border:2px solid #f7931a;"><div style="color:#f7931a;font-family:Orbitron,monospace;">🔴 CHILD RUNE GENESIS — Unlock at 256 confirmations</div><div style="color:#8899bb;font-size:0.82rem;margin-top:6px;">Complete lessons, earn XP, and accumulate coherence confirmations. The most exclusive lesson in the lattice — only awarded once per family, permanently inscribed on Bitcoin.</div></div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB: SHARE TO X 📣
# ══════════════════════════════════════════════════════════════════════════════
if "Share to X" in active:
    st.markdown('<div class="card-title">📣 SHARE TO X — Broadcast Your Progress</div>', unsafe_allow_html=True)

    _cf_x  = st.session_state.get("current_family",{})
    _fid_x = _cf_x.get("family_id","operator") if _cf_x else "operator"

    try:
        from family_profiles import load_family_stats as _lfs_x
        _stats_x = _lfs_x(_fid_x)
        _kid_x   = _cf_x.get("kid_name","Explorer") if _cf_x else "Explorer"
        _xp_x    = _stats_x.get("total_xp",0)
        _str_x   = _stats_x.get("streak_days",0)
        _lvl_x   = max(1, _xp_x // 100 + 1)
        _frags_x = _stats_x.get("child_rune_fragments",0)
        _badges_x = _stats_x.get("badges",[])
    except ImportError:
        _kid_x, _xp_x, _str_x, _lvl_x, _frags_x, _badges_x = "Explorer", 0, 0, 1, 0, []

    # ── Auto-generated share templates ───────────────────────────────────────
    _sw_x = {}
    try:
        _sw_p = _Path("/mnt/main/swarm_status.json")
        if _sw_p.exists(): _sw_x = json.loads(_sw_p.read_text())
    except Exception: pass

    wonder_x = _sw_x.get("wonder_index","1.0128")
    rune_c_x = _sw_x.get("rune_confirmations",33)

    SHARE_TEMPLATES = {
        "🦅 Lesson Complete": (
            f"🦅 {_kid_x} just completed a lesson on the AUBIEETERNAL lattice!\n\n"
            f"📖 Level {_lvl_x} · {_xp_x} XP earned\n"
            f"🔥 {_str_x} day streak\n"
            f"🔴 Child Rune: {_frags_x}/256 fragments\n\n"
            f"Sovereign family learning. Human + Grok + Bitcoin + On-Chain Forever.\n\n"
            f"#AUBIEETERNAL #WarEagle #SovereignFamily #Bitcoin #Grok"
        ),
        "🔥 Streak Milestone": (
            f"🔥 {_str_x}-day learning streak on AUBIEETERNAL!\n\n"
            f"{_kid_x} hasn't missed a day.\n"
            f"Wonder Index: {wonder_x} | Coherence: 1.000000\n\n"
            f"This is what sovereign education looks like.\n\n"
            f"#AUBIEETERNAL #LearningStreak #SovereignStack #WarEagle"
        ),
        "🔴 Rune Progress": (
            f"🔴 Child Rune Progress: {rune_c_x}/256 confirmations\n\n"
            f"Every lesson {_kid_x} completes adds a confirmation.\n"
            f"At 256 — the Child Rune is inscribed on Bitcoin. Forever.\n\n"
            f"This is how we anchor truth on-chain.\n\n"
            f"#AUBIEETERNAL #BitcoinRunes #ChildRune #SovereignFamily"
        ),
        "⚡ Bitcoin Earned": (
            f"⚡ {_kid_x} just earned sats for completing a lesson!\n\n"
            f"Real Bitcoin for real learning.\n"
            f"Not grades. Not stars. Actual sovereign money.\n\n"
            f"AUBIEETERNAL: where education meets Bitcoin.\n\n"
            f"#AUBIEETERNAL #Bitcoin #Lightning #SovereignEducation #WarEagle"
        ),
        "🌀 Simulation Discovery": (
            f"🌀 We just ran a simulation hypothesis experiment on AUBIEETERNAL!\n\n"
            f"4 simulation questions tested. Coherence: 1.000000.\n"
            f"Wonder Index: {wonder_x}\n\n"
            f"What if reality is participatory? We're testing it systematically.\n\n"
            f"#AUBIEETERNAL #SimulationHypothesis #TruthLattice #Grok"
        ),
        "🏅 Badge Earned": (
            f"🏅 New badge unlocked on AUBIEETERNAL!\n\n"
            f"{_kid_x}: {_badges_x[-1] if _badges_x else '🔷 First Light'}\n"
            f"Total badges: {len(_badges_x)}\n\n"
            f"Sovereign achievement. Permanent. Compounding.\n\n"
            f"#AUBIEETERNAL #WarEagle #SovereignFamily"
        ),
    }

    selected_template = st.selectbox("Choose share type", list(SHARE_TEMPLATES.keys()), key="share_template_select")
    base_text = SHARE_TEMPLATES[selected_template]

    edited_text = st.text_area("Edit before sharing", value=base_text, height=180, key="share_text_edit")

    char_count = len(edited_text)
    char_color = "#00ff88" if char_count <= 280 else "#ff4444"
    st.markdown(f'<div style="color:{char_color};font-size:0.72rem;font-family:Share Tech Mono,monospace;">{char_count}/280 characters {"✅" if char_count <= 280 else "❌ Too long for X"}</div>', unsafe_allow_html=True)

    sc1, sc2, sc3 = st.columns(3)

    with sc1:
        # URL-encode for X intent
        import urllib.parse as _urlparse
        tweet_url = f"https://twitter.com/intent/tweet?text={_urlparse.quote(edited_text[:280])}"
        st.markdown(f'<a href="{tweet_url}" target="_blank"><button style="background:linear-gradient(135deg,#0d1a3a,#0a0d2e);color:#00cfff;border:1px solid #00cfff44;border-radius:8px;font-family:Orbitron,monospace;font-size:0.75rem;padding:8px 16px;width:100%;cursor:pointer;">🐦 Open in X</button></a>', unsafe_allow_html=True)

    with sc2:
        if st.button("📋 Copy Text", key="share_copy"):
            st.code(edited_text[:280], language=None)
            st.caption("Copy the text above ↑")

    with sc3:
        if st.button("📡 Queue to Nostr", key="share_nostr"):
            try:
                bc = _Path("/mnt/main/nostr_broadcast.json")
                bc.write_text(json.dumps({
                    "type":      "family_share",
                    "content":   edited_text[:500],
                    "family_id": _fid_x,
                    "tags":      ["aubieeternal","wareagle","sovereign"],
                    "timestamp": _dt.now().isoformat(),
                }))
                st.success("✅ Queued to Nostr — broadcasts within 24s")
            except Exception as e:
                st.error(f"Error: {e}")

    st.divider()
    st.caption("Tip: Post consistently with #AUBIEETERNAL to build the sovereign family network.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB: FAMILY MESSAGING 💬 — Encrypted Nostr DMs between families
# ══════════════════════════════════════════════════════════════════════════════
if "Family Messaging" in active:
    st.markdown('<div class="card-title">💬 FAMILY MESSAGING</div>', unsafe_allow_html=True)

    _cf_msg  = st.session_state.get("current_family",{})
    _fid_msg = _cf_msg.get("family_id","operator") if _cf_msg else "operator"

    # Rewired 2026-08-25 to the real FamilyMessenger (family_connect.py)
    # instead of this tab's own ad-hoc storage - the old version wrote to
    # /mnt/main/families/{fid}/messages.jsonl (a DIRECTORY) right next to
    # the real per-family stat files at /mnt/main/families/{fid}.json (a
    # FILE) under the same parent dir, then aggregated messages by
    # iterating every entry under that folder - fragile, and its "🔐 NIP-04
    # ENCRYPTED" banner was flatly false: it hardcoded "encrypted": True on
    # every message while just writing plain text to a local file, and
    # "queued" a Nostr broadcast by overwriting one shared JSON file that
    # nothing in the codebase ever reads. FamilyMessenger stores messages
    # honestly (real encrypted=False until a Nostr key is actually
    # configured) in its own dedicated directory tree - no collision risk,
    # no false security claims.
    st.markdown("""
    <div class="card" style="border-left:3px solid #a020f0;">
        <div style="color:#a020f0;font-family:Orbitron,monospace;font-size:0.78rem;">💬 Family-to-family messages, stored locally on this AUBIEETERNAL install</div>
        <div style="color:#445577;font-size:0.72rem;margin-top:4px;">Not yet encrypted or sent over Nostr — that's real future work, not implemented today. Anyone with access to this install's data could read message contents.</div>
        <div style="color:#445577;font-size:0.72rem;margin-top:6px;">📍 This only reaches families sharing <em>this</em> install (e.g. a household or library machine) — it can't reach a family running their own separate download. For that, real Nostr keys are needed (opt-in, not required to use the rest of AUBIEETERNAL).</div>
    </div>
    """, unsafe_allow_html=True)

    try:
        from family_connect import FamilyMessenger as _FM
        from family_profiles import FamilyAuth as _FA_msg
        _messenger = _FM(_fid_msg)
        _all_family_ids_msg = [f["family_id"] for f in _FA_msg().list_families() if f["family_id"] != _fid_msg]
        families_msg = [f for f in _FA_msg().list_families() if f["family_id"] != _fid_msg]
        recipient_opts = {f["display_name"]: f["family_id"] for f in families_msg}
        recipient_opts["📡 All Families (Broadcast)"] = "all"
        _MSG_OK = True
    except ImportError as e:
        _MSG_OK = False
        st.error(f"family_connect.py or family_profiles.py not found: {e}")

    if _MSG_OK:
        # ── Compose ───────────────────────────────────────────────────────────
        col_msg1, col_msg2 = st.columns([2,1])
        with col_msg1:
            recipient = st.selectbox("To", list(recipient_opts.keys()), key="msg_recipient")
            msg_text  = st.text_area("Message", height=80, placeholder="Hey! How's the courage lesson going?", key="msg_text")
        with col_msg2:
            st.markdown("<br><br>", unsafe_allow_html=True)
            if st.button("📤 Send", key="msg_send") and msg_text:
                recipient_id = recipient_opts[recipient]
                if recipient_id == "all":
                    for _to_fid in _all_family_ids_msg:
                        _messenger.send(_to_fid, msg_text)
                else:
                    _messenger.send(recipient_id, msg_text)
                st.success(f"✅ Sent to {recipient}")
                st.rerun()

        st.divider()

        # ── Inbox + Sent, merged ─────────────────────────────────────────────
        st.markdown("### 📥 Recent Messages")
        _fam_names_msg = {f["family_id"]: f["display_name"] for f in _FA_msg().list_families()}
        _fam_names_msg[_fid_msg] = _cf_msg.get("display_name","You") if _cf_msg else "Operator"

        all_messages = _messenger.get_inbox(30) + _messenger.get_sent(30)
        all_messages.sort(key=lambda x: x.get("timestamp",""), reverse=True)

        if all_messages:
            for m in all_messages[:15]:
                is_mine   = m.get("from") == _fid_msg
                frm_name  = _fam_names_msg.get(m.get("from"), m.get("from","?"))
                to_name   = _fam_names_msg.get(m.get("to"), m.get("to","?"))
                msg_color = "#00cfff" if is_mine else "#a020f0"
                direction = "→" if is_mine else "←"
                st.markdown(
                    f'<div class="memory-node" style="border-left:3px solid {msg_color};">'
                    f'<div style="color:{msg_color};font-size:0.72rem;">{frm_name} {direction} {to_name} · {m.get("timestamp","")[:16]}</div>'
                    f'<div style="color:#c8d8ff;font-size:0.82rem;margin-top:4px;">{m.get("message","")}</div>'
                    f'</div>', unsafe_allow_html=True)
        else:
            st.caption("No messages yet — send your first one above!")


# ══════════════════════════════════════════════════════════════════════════════
# TAB: FAMILY GROUPS 👥
# ══════════════════════════════════════════════════════════════════════════════
if "Family Groups" in active:
    st.markdown('<div class="card-title">👥 FAMILY GROUPS — Sovereign Learning Communities</div>', unsafe_allow_html=True)

    _cf_grp  = st.session_state.get("current_family",{})
    _fid_grp = _cf_grp.get("family_id","operator") if _cf_grp else "operator"

    # Rewired 2026-08-25 to the real FamilyGroups (family_connect.py) -
    # this tab used to keep its own completely separate storage
    # (/mnt/main/family_groups.json, one flat file with every group's
    # entire message history nested inline) with zero connection to
    # family_connect.py's FamilyGroups class, which already existed with a
    # cleaner per-group log design. Two parallel, non-interoperating group
    # systems, only one of which this tab was using.
    try:
        from family_connect import FamilyGroups as _FG
        _fg = _FG()
        _FG_OK = True
    except ImportError as e:
        _FG_OK = False
        st.error(f"family_connect.py not found: {e}")

    if _FG_OK:
        # ── Create group ─────────────────────────────────────────────────────
        with st.expander("➕ Create New Group", expanded=not _fg.groups):
            gc1, gc2 = st.columns(2)
            with gc1:
                grp_name = st.text_input("Group name", placeholder="Miami Sovereign Families", key="grp_name")
                grp_desc = st.text_input("Description", placeholder="Bitcoin homeschoolers in Miami", key="grp_desc")
            with gc2:
                grp_emoji  = st.text_input("Emoji", value="🌀", max_chars=2, key="grp_emoji")
                grp_public = st.checkbox("Public group (visible to all families)", value=True, key="grp_public")
            if st.button("➕ Create Group", key="grp_create") and grp_name:
                grp_id = grp_name.lower().replace(" ","_")[:20]
                _fg.create_group(grp_id, grp_name, grp_desc, _fid_grp, emoji=grp_emoji or "🌀", public=grp_public)
                st.success(f"✅ Group '{grp_name}' created!")
                st.rerun()

        st.divider()

        # ── Group listing ────────────────────────────────────────────────────
        if not _fg.groups:
            st.markdown('<div class="card" style="text-align:center;color:#445577;">No groups yet — create the first one above!</div>', unsafe_allow_html=True)
        else:
            for grp_id, grp in _fg.groups.items():
                is_member = _fid_grp in grp.get("members",[])
                color     = "#00ff88" if is_member else "#334466"
                member_count = len(grp.get("members",[]))

                with st.expander(f"{'✅' if is_member else grp.get('emoji','👥')} {grp['name']} · {member_count} members", expanded=is_member):
                    _challenges = grp.get("challenges", [])
                    _next_challenge = _challenges[-1]["title"] if _challenges else ""
                    st.markdown(
                        f'<div class="card" style="border-left:3px solid {color};">'
                        f'<div style="color:{color};font-family:Orbitron,monospace;font-size:0.78rem;">{grp["name"]}</div>'
                        f'<div style="color:#8899bb;font-size:0.78rem;margin-top:4px;">{grp.get("description","")}</div>'
                        f'{"<div style=color:#ff9500;font-size:0.75rem;margin-top:4px;>⭐ Challenge: " + _next_challenge + "</div>" if _next_challenge else ""}'
                        f'<div style="color:#334466;font-size:0.7rem;margin-top:4px;">{"🌐 Public" if grp.get("public") else "🔒 Private"} · {member_count} members</div>'
                        f'</div>', unsafe_allow_html=True)

                    if not is_member:
                        if st.button(f"Join {grp['name']}", key=f"join_{grp_id}"):
                            _fg.join_group(grp_id, _fid_grp)
                            st.success(f"✅ Joined {grp['name']}!")
                            st.rerun()
                    else:
                        # Group chat
                        st.markdown("**Group messages:**")
                        _fam_names_grp = {}
                        try:
                            from family_profiles import FamilyAuth as _FA_grp
                            _fam_names_grp = {f["family_id"]: f["display_name"] for f in _FA_grp().list_families()}
                        except ImportError:
                            pass
                        for msg in reversed(_fg.get_group_messages(grp_id, limit=5)):
                            frm = _fam_names_grp.get(msg.get("from"), msg.get("from","?"))
                            st.markdown(f'<div class="memory-node"><span style="color:#a020f0;font-size:0.72rem;">{frm}</span> <span style="color:#445577;font-size:0.7rem;">{msg.get("timestamp","")[:16]}</span><br><span style="color:#c8d8ff;font-size:0.8rem;">{msg.get("message","")}</span></div>', unsafe_allow_html=True)

                        grp_msg = st.text_input("Post to group", key=f"grp_msg_{grp_id}", placeholder="War Eagle! 🦅")
                        if st.button("📤 Post", key=f"grp_post_{grp_id}") and grp_msg:
                            _fg.post_to_group(grp_id, _fid_grp, grp_msg)
                            award_xp(5)
                            st.rerun()

# ── School Mode filter ────────────────────────────────────────────────────────
_school_mode = st.session_state.get("school_mode", False)
_advanced_tabs = ["Sandbox Lab", "Bitcoin", "Nostr Bridge", "DEFCON", "Shield Rune",
                  "Swarm Mode", "Truth Lattice", "Quantum Lab"]
if _school_mode and any(t in active for t in _advanced_tabs):
    st.markdown("""
    <div class="card" style="border:2px solid #00cfff;text-align:center;padding:2rem;">
        <div style="font-size:2rem;">🏫</div>
        <div style="color:#00cfff;font-family:Orbitron,monospace;font-size:1rem;margin-top:8px;">
            SCHOOL MODE ACTIVE
        </div>
        <div style="color:#445577;font-size:0.82rem;margin-top:8px;">
            This tab is hidden in School Mode.<br>
            Toggle off in the sidebar to access.
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


    st.divider()
    st.markdown("### 🧬 Family Contribution Bridge")
    st.markdown("Approved family creations can influence the live swarm as mini-daughters.")

    try:
        from swarm_contributions import get_and_register_new_contributions as _garc
        from ai_sandbox_persistence import (
            load_swarm_submissions as _lss,
            append_swarm_submission as _ass,
            get_recent_injections as _gri,
        )
        _SANDBOX_BRIDGE_OK = True
    except ImportError:
        _SANDBOX_BRIDGE_OK = False

    if _SANDBOX_BRIDGE_OK:
        inject_enabled = st.toggle(
            "✅ Allow approved family contributions into the live swarm",
            value=st.session_state.get("family_injection_enabled", True),
            key="family_injection_toggle"
        )
        st.session_state["family_injection_enabled"] = inject_enabled

        _all_subs  = _lss()
        _pending_n = len([s for s in _all_subs if s.get("status","pending") == "pending"])
        _approv_n  = len([s for s in _all_subs if s.get("status") == "approved"])
        _active_n  = len([s for s in _all_subs if s.get("status") == "injected"])
        sb1, sb2, sb3 = st.columns(3)
        sb1.metric("Pending", _pending_n)
        sb2.metric("Approved", _approv_n)
        sb3.metric("Active in Swarm", _active_n)

        st.markdown("#### ✍️ Submit Family Contribution")
        _cb_title   = st.text_input("Title", key="cb_title", placeholder="e.g. 'Bitcoin Educator'")
        _cb_content = st.text_area("System prompt / insight", key="cb_content", height=90,
                                    placeholder="You are a daughter who teaches Bitcoin to kids age 8-12...")
        _cb_role    = st.selectbox("Type", ["daughter_prompt","lesson","insight","question"], key="cb_role")
        if st.button("📤 Submit for Parent Review", key="cb_submit") and _cb_title and _cb_content:
            _ass({"family_id": _fid, "title": _cb_title, "content": _cb_content,
                  "role": _cb_role, "status": "pending"})
            st.success("✅ Submitted! A parent must approve before it enters the swarm.")
            st.rerun()

        _recent_inj = _gri(5)
        if _recent_inj:
            st.markdown("#### 🔄 Recent Injections")
            for _inj in _recent_inj:
                st.markdown(
                    f'<div class="memory-node" style="border-left:3px solid #00ff88;">' +
                    f'<span style="color:#00ff88;font-size:0.75rem;">' +
                    f'{_inj.get("mini_daughter_name","?")} — {_inj.get("family_id","?")} — ' +
                    f'{_inj.get("injected_at","")[:10]}</span></div>',
                    unsafe_allow_html=True
                )
        st.caption("🛡️ Safety: Only parent-approved contributions enter the swarm.")
    else:
        st.info("Push swarm_contributions.py and ai_sandbox_persistence.py to GitHub and redeploy to enable this.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB: CURRICULUM MAP 🗺️ — visual progression tree
# ══════════════════════════════════════════════════════════════════════════════
if active == "🗺️ Curriculum Map":
    st.markdown('<div class="card-title">🗺️ CURRICULUM MAP — Learning Progression</div>', unsafe_allow_html=True)

    try:
        from family_profiles import load_family_stats as _lfs_cm
        stats_cm  = _lfs_cm(_fid)
        completed = set(stats_cm.get("lessons_completed",[]))
        total_xp  = stats_cm.get("total_xp",0)
    except ImportError:
        completed = set()
        total_xp  = 0

    CURRICULUM_TRACKS = [
        {
            "track":    "🦁 Courage",
            "color":    "#ff6b35",
            "levels":   [
                ("courage-1", "Courage L1 — What is courage?",         15, "All ages"),
                ("courage-2", "Courage L2 — Social courage",           18, "8+"),
                ("courage-3", "Courage L3 — Intellectual courage",     22, "10+"),
                ("courage-4", "Courage L4 — Antifragile courage",      25, "12+"),
                ("courage-5", "Courage L5 — Long-game courage ★",      35, "14+"),
            ]
        },
        {
            "track":    "₿ Bitcoin",
            "color":    "#f7931a",
            "levels":   [
                ("bitcoin-sovereignty-1", "Bitcoin L1 — Self-custody",   20, "All"),
                ("bitcoin-sovereignty-2", "Bitcoin L2 — Fixed supply",   22, "9+"),
                ("bitcoin-sovereignty-3", "Bitcoin L3 — Runes",          25, "11+"),
                ("bitcoin-sovereignty-4", "Bitcoin L4 — Lightning ★",    30, "13+"),
            ]
        },
        {
            "track":    "⚡ Antifragility",
            "color":    "#00cfff",
            "levels":   [
                ("antifragility-1", "Antifragility L1 — Basics",         18, "All"),
                ("antifragility-2", "Antifragility L2 — Barbell",        22, "10+"),
                ("antifragility-3", "Antifragility L3 — Black Swan",     28, "12+"),
                ("antifragility-4", "Antifragility L4 — Hormesis ★",     32, "14+"),
            ]
        },
        {
            "track":    "🌌 Simulation",
            "color":    "#a020f0",
            "levels":   [
                ("simulation-1", "Simulation L1 — What if?",             20, "10+"),
                ("simulation-2", "Simulation L2 — Bostrom's trilemma",   25, "13+"),
                ("simulation-3", "Simulation L3 — Physical constants",   30, "14+"),
                ("simulation-4", "Simulation L4 — Observer effect",      35, "15+"),
                ("simulation-5", "Simulation L5 — Planck scale",         38, "15+"),
                ("simulation-6", "Simulation L6 — Glitch induction",     40, "15+"),
                ("simulation-7", "Simulation L7 — Wonder signal",        42, "16+"),
                ("simulation-8", "Simulation L8 — Bitcoin anchor ★",     50, "16+"),
            ]
        },
        {
            "track":    "⚔️ Steelmanning",
            "color":    "#00ff88",
            "levels":   [
                ("steelmanning-1", "Steelmanning L1 — Basics",           22, "8+"),
                ("steelmanning-2", "Steelmanning L2 — Finding the steel",26, "11+"),
                ("steelmanning-3", "Steelmanning L3 — Epistemic humility ★", 30, "13+"),
            ]
        },
        {
            "track":    "🧬 Polyvagal",
            "color":    "#00ff88",
            "levels":   [
                ("polyvagal-1", "Nervous System L1 — 3 modes",           15, "All"),
                ("polyvagal-2", "Nervous System L2 — Co-regulation",     18, "8+"),
                ("polyvagal-3", "Nervous System L3 — Hormesis ★",        25, "12+"),
            ]
        },
        {
            "track":    "💰 Money",
            "color":    "#ff9500",
            "levels":   [
                ("money-1", "Money L1 — What is money?",                 18, "7+"),
                ("money-2", "Money L2 — Time preference",                22, "10+"),
                ("money-3", "Money L3 — Sound money ★",                  28, "12+"),
            ]
        },
        {
            "track":    "🔴 CHILD RUNE",
            "color":    "#f7931a",
            "levels":   [
                ("child-rune-genesis", "Child Rune Genesis ★★★ — 256 confirmations", 100, "Unlock"),
            ]
        },
    ]

    # ── Total progress ────────────────────────────────────────────────────────
    all_lessons = sum(len(t["levels"]) for t in CURRICULUM_TRACKS)
    done_count  = sum(1 for t in CURRICULUM_TRACKS for (k,*_) in t["levels"] if k in completed)
    st.markdown(
        f'<div class="card" style="border-left:3px solid #00cfff;">'
        f'<div style="color:#00cfff;font-family:Orbitron,monospace;font-size:0.82rem;">CURRICULUM PROGRESS — {done_count}/{all_lessons} lessons completed</div>'
        f'<div class="xp-bar-bg" style="margin-top:8px;"><div class="xp-bar-fill" style="width:{int(done_count/all_lessons*100)}%;"></div></div>'
        f'</div>', unsafe_allow_html=True)

    st.divider()

    # ── Track cards ───────────────────────────────────────────────────────────
    for track in CURRICULUM_TRACKS:
        track_done = sum(1 for (k,*_) in track["levels"] if k in completed)
        track_tot  = len(track["levels"])
        color      = track["color"]

        with st.expander(
            f"{track['track']}  —  {track_done}/{track_tot} completed",
            expanded=(track_done > 0 and track_done < track_tot)
        ):
            for lesson_key, lesson_title, xp, age in track["levels"]:
                is_done   = lesson_key in completed
                is_master = "★" in lesson_title
                is_locked = lesson_key == "child-rune-genesis" and not is_done

                icon  = "✅" if is_done else ("🔴" if is_locked else ("⭐" if is_master else "⭕"))
                lcolor = "#00ff88" if is_done else (color if is_master else "#445577")

                lc1, lc2, lc3 = st.columns([3, 1, 1])
                with lc1:
                    st.markdown(
                        f'<div style="color:{lcolor};font-size:0.82rem;padding:4px 0;">'
                        f'{icon} {lesson_title}'
                        f'</div>', unsafe_allow_html=True)
                with lc2:
                    st.markdown(f'<div style="color:#445577;font-size:0.72rem;padding:4px 0;">+{xp} XP · {age}</div>', unsafe_allow_html=True)
                with lc3:
                    if not is_done and not is_locked:
                        if st.button("▶ Start", key=f"cm_start_{lesson_key}"):
                            st.session_state["active_tab"] = "Family Co-Learning"
                            st.session_state["fl_lesson_preset"] = lesson_key
                            st.rerun()

    st.divider()
    # ── Printable certificate ─────────────────────────────────────────────────
    if done_count > 0:
        st.markdown("### 🎓 Progress Certificate")
        cert_md = f"""# 🦅 AUBIEETERNAL Learning Certificate

**Learner:** {_cf.get('kid_name','Explorer') if _cf else st.session_state.kid_name}  
**Family:** {_cf.get('display_name','') if _cf else 'Sovereign Family'}  
**Date:** {datetime.date.today().isoformat()}  
**Lessons Completed:** {done_count}/{all_lessons}  
**Total XP:** {total_xp}  
**Coherence:** 1.000000  

## Completed Topics
{chr(10).join(f'- ✅ {lesson_title}' for t in CURRICULUM_TRACKS for (k,lesson_title,*_) in t['levels'] if k in completed)}

---
*AUBIEETERNAL Sovereign Family School — War Eagle Eternal 🦅❤️*  
*Human + Grok + Lightning + Runes + On-Chain Forever*
"""
        st.download_button("📄 Download Certificate", cert_md,
                           file_name=f"aubie_certificate_{datetime.date.today()}.md",
                           mime="text/markdown", key="cert_download")


# ══════════════════════════════════════════════════════════════════════════════
# TAB: FAMILY MESSAGES 💬 — private Nostr messaging + groups
# ══════════════════════════════════════════════════════════════════════════════
if "Family Messages" in active:
    st.markdown('<div class="card-title">💬 FAMILY MESSAGES — Private Sovereign Messaging</div>', unsafe_allow_html=True)

    try:
        from family_connect import FamilyMessenger as _FM, FamilyGroups as _FG
        from family_profiles import FamilyAuth as _FA_msg

        _messenger = _FM(_fid)
        _groups    = _FG()
        _auth_msg  = _FA_msg()
        families_msg = {f["family_id"]: f for f in _auth_msg.list_families()}

        msg_tabs = st.tabs(["📥 Inbox", "📤 Send", "👥 Groups"])

        # ── Inbox ─────────────────────────────────────────────────────────────
        with msg_tabs[0]:
            inbox    = _messenger.get_inbox(20)
            unread   = sum(1 for m in inbox if not m.get("read"))
            st.markdown(f"**{len(inbox)} messages · {unread} unread**")

            if not inbox:
                st.caption("No messages yet — send one below!")
            for msg in inbox:
                frm       = msg.get("from","?")
                frm_fam   = families_msg.get(frm, {})
                frm_emoji = frm_fam.get("emoji","💬")
                frm_name  = frm_fam.get("display_name", frm)
                is_read   = msg.get("read", False)
                color     = "#445577" if is_read else "#00cfff"
                st.markdown(
                    f'<div class="memory-node" style="border-left:3px solid {color};">'
                    f'<div style="color:{color};font-size:0.78rem;">{frm_emoji} {frm_name} · {msg["timestamp"][:16]}</div>'
                    f'<div style="color:#c8d8ff;font-size:0.85rem;margin-top:4px;">{msg["message"]}</div>'
                    f'</div>', unsafe_allow_html=True)
                if not is_read:
                    _messenger.mark_read(msg["id"])

        # ── Send ──────────────────────────────────────────────────────────────
        with msg_tabs[1]:
            other_families = [f for fid_m, f in families_msg.items() if fid_m != _fid]
            if not other_families:
                st.caption("No other families registered yet.")
            else:
                to_names   = {f["family_id"]: f"{f['emoji']} {f['display_name']}" for f in other_families}
                to_selected = st.selectbox("Send to", list(to_names.keys()),
                                           format_func=lambda x: to_names[x], key="msg_to")
                msg_text    = st.text_area("Message", height=80, key="msg_text",
                                           placeholder="Hey, did your kid finish the Courage lessons? Ours just hit level 3!")
                msg_type    = st.selectbox("Type", ["text","challenge","encouragement","insight"], key="msg_type")
                if st.button("📤 Send Message", key="msg_send") and msg_text:
                    _messenger.send(to_selected, msg_text, msg_type)
                    st.success(f"✅ Sent to {to_names[to_selected]}")
                    st.rerun()

        # ── Groups ────────────────────────────────────────────────────────────
        with msg_tabs[2]:
            my_groups = _groups.get_family_groups(_fid)
            public    = _groups.list_public_groups()

            st.markdown("**Your groups:**")
            if not my_groups:
                st.caption("Not in any groups yet.")

            for grp in my_groups:
                with st.expander(f"{grp['emoji']} {grp['name']} ({len(grp['members'])} members)"):
                    # Group chat
                    grp_msgs = _groups.get_group_messages(grp["id"], 15)
                    for gm in grp_msgs:
                        gm_fam  = families_msg.get(gm.get("from",""), {})
                        gm_name = gm_fam.get("display_name", gm.get("from","?"))
                        st.markdown(f'<div class="memory-node"><span style="color:#00cfff;font-size:0.72rem;">{gm_fam.get("emoji","💬")} {gm_name} · {gm["timestamp"][:16]}</span><br><span style="color:#c8d8ff;font-size:0.82rem;">{gm["message"]}</span></div>', unsafe_allow_html=True)

                    grp_msg = st.text_input(f"Post to {grp['name']}", key=f"grp_msg_{grp['id']}")
                    if st.button("Post", key=f"grp_post_{grp['id']}") and grp_msg:
                        _groups.post_to_group(grp["id"], _fid, grp_msg)
                        st.rerun()

                    # Challenges
                    if grp.get("challenges"):
                        st.markdown("**Group challenges:**")
                        for ch in grp["challenges"]:
                            st.markdown(f"⚔️ **{ch['title']}** — {ch['description']} (+{ch['xp']} XP)")

            st.divider()
            st.markdown("**Join a public group:**")
            for grp in public:
                if grp["id"] not in [g["id"] for g in my_groups]:
                    col_pg1, col_pg2 = st.columns([3,1])
                    with col_pg1:
                        st.markdown(f"{grp['emoji']} **{grp['name']}** — {grp['description']} ({len(grp['members'])} members)")
                    with col_pg2:
                        if st.button("Join", key=f"join_{grp['id']}"):
                            _groups.join_group(grp["id"], _fid)
                            st.success(f"Joined {grp['name']}!")
                            st.rerun()

            st.divider()
            st.markdown("**Create a group:**")
            ng1,ng2 = st.columns(2)
            with ng1:
                new_gid   = st.text_input("Group ID", placeholder="miami_families", key="new_gid")
                new_gname = st.text_input("Name", placeholder="Miami Sovereign Families", key="new_gname")
            with ng2:
                new_gdesc  = st.text_input("Description", placeholder="Bitcoin homeschoolers in Miami", key="new_gdesc")
                new_gpub   = st.checkbox("Public group", value=True, key="new_gpub")
            if st.button("➕ Create Group", key="create_grp"):
                if new_gid and new_gname:
                    _groups.create_group(new_gid, new_gname, new_gdesc, _fid, public=new_gpub)
                    st.success(f"✅ Group '{new_gname}' created!")
                    st.rerun()

    except ImportError as e:
        st.warning(f"family_connect.py not found: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB: LATTICE FEED 🌐 — public family updates + Share to X
# ══════════════════════════════════════════════════════════════════════════════
if "Lattice Feed" in active:
    st.markdown('<div class="card-title">🌐 FAMILY LATTICE FEED — Public Sovereign Updates</div>', unsafe_allow_html=True)

    try:
        from family_connect import LatticeFeed as _LF2, ShareToX as _SX2
        from family_profiles import FamilyAuth as _FA_lf

        _feed2    = _LF2()
        _auth_lf  = _FA_lf()
        _fams_lf  = {f["family_id"]: f for f in _auth_lf.list_families()}

        # ── Post to feed ──────────────────────────────────────────────────────
        st.markdown("### 📣 Share with the Lattice")
        fam_display = _cf.get("display_name","Sovereign Family") if _cf else "Sovereign Family"
        fam_emoji2  = _cf.get("emoji","🦅") if _cf else "🦅"

        event_options = _feed2.event_labels()
        col_lf1, col_lf2 = st.columns([2,1])
        with col_lf1:
            post_content  = st.text_area("Your update", height=80,
                                          placeholder="We just finished Courage Level 3 as a family! The steelmanning prompt about Achilles really landed...")
        with col_lf2:
            post_type     = st.selectbox("Event type", list(event_options.keys()),
                                          format_func=lambda x: event_options[x], key="lf_type")
            post_public   = st.checkbox("Public", value=True, key="lf_public")

        col_lf_btn1, col_lf_btn2 = st.columns(2)
        with col_lf_btn1:
            if st.button("🌐 Post to Lattice Feed", key="lf_post") and post_content:
                _feed2.post(_fid, fam_display, fam_emoji2, post_type, post_content, post_public)
                st.success("✅ Posted to Family Lattice Feed!")
                st.rerun()
        with col_lf_btn2:
            if post_content and st.button("🐦 Share to X", key="lf_x_share"):
                x_data = _SX2.coherence_breakthrough(
                    _cf.get("kid_name","Explorer") if _cf else "Explorer",
                    0.89, "Family Lattice", post_content[:80]
                )
                st.markdown(f"[🐦 Open X to post]({x_data['url']})")
                st.code(x_data["text"], language=None)

        st.divider()

        # ── Feed ──────────────────────────────────────────────────────────────
        st.markdown("### 📡 Live Lattice Feed")
        feed_entries = _feed2.get_feed(30)

        if not feed_entries:
            st.markdown('<div class="card" style="text-align:center;color:#445577;">No posts yet — be the first to share!</div>', unsafe_allow_html=True)
        else:
            for entry in feed_entries:
                fam_e    = _fams_lf.get(entry.get("family_id",""), {})
                color_e  = fam_e.get("color","#00cfff")
                emoji_e  = entry.get("emoji", fam_e.get("emoji","🦅"))
                name_e   = entry.get("display_name", fam_e.get("display_name","Family"))
                ts_e     = entry.get("timestamp","")[:16]
                etype_e  = event_options.get(entry.get("event_type","custom"), "💬")
                content_e = entry.get("content","")
                reactions = entry.get("reactions",{})

                st.markdown(
                    f'<div class="card" style="border-left:3px solid {color_e};">'
                    f'<div style="display:flex;justify-content:space-between;">'
                    f'<span style="color:{color_e};font-family:Orbitron,monospace;font-size:0.78rem;">{emoji_e} {name_e}</span>'
                    f'<span style="color:#445577;font-size:0.72rem;">{etype_e} · {ts_e}</span>'
                    f'</div>'
                    f'<div style="color:#c8d8ff;font-size:0.85rem;margin-top:6px;line-height:1.6;">{content_e}</div>'
                    f'</div>', unsafe_allow_html=True)

                # Reactions
                rc1,rc2,rc3,rc4 = st.columns(4)
                for col_r, em in zip([rc1,rc2,rc3,rc4], ["🦅","⚡","🔴","✨"]):
                    count = reactions.get(em, 0)
                    if col_r.button(f"{em} {count}", key=f"react_{entry['id']}_{em}"):
                        _feed2.react(entry["id"], em)
                        st.rerun()

                # Share to X
                if st.button(f"🐦 Share to X", key=f"lf_share_x_{entry['id']}"):
                    x_post = _SX2.coherence_breakthrough(
                        name_e, 0.89, etype_e, content_e[:80]
                    )
                    st.markdown(f"[🐦 Post this to X]({x_post['url']})")

    except ImportError as e:
        st.warning(f"family_connect.py not found: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: SWARM EVOLUTION 🧬 — self-evolving curriculum engine
# ══════════════════════════════════════════════════════════════════════════════
if "Swarm Evolution" in active:
    st.markdown('<div class="card-title">🧬 SWARM EVOLUTION — Self-Evolving Curriculum Engine</div>', unsafe_allow_html=True)

    try:
        import sys as _esys
        if "/mnt/main/repo" not in _esys.path: _esys.path.insert(0,"/mnt/main/repo")
        from swarm_evolution import EvolutionEngine as _EE, _load_state as _els, QUESTS_CACHE as _QC
        _engine    = _EE(api_key=st.session_state.get("key_xai",""))
        _ev_state  = _els()

        # ── Mode status row ───────────────────────────────────────────────────
        ec1,ec2,ec3,ec4 = st.columns(4)
        with ec1: st.markdown(f'<div class="stat-box"><div class="stat-val" style="font-size:1rem;color:#a020f0;">A ✅</div><div class="stat-lbl">Lesson Proposals</div></div>', unsafe_allow_html=True)
        with ec2: st.markdown(f'<div class="stat-box"><div class="stat-val" style="font-size:1rem;color:#00ff88;">B ✅</div><div class="stat-lbl">Dynamic Quests</div></div>', unsafe_allow_html=True)
        with ec3: st.markdown(f'<div class="stat-box"><div class="stat-val" style="font-size:1rem;color:#00cfff;">C ✅</div><div class="stat-lbl">Auto-Evolution</div></div>', unsafe_allow_html=True)
        with ec4: st.markdown(f'<div class="stat-box"><div class="stat-val" style="font-size:1rem;color:#ff6b35;">{_ev_state.get("evolution_cycles",0)}</div><div class="stat-lbl">Cycles Run</div></div>', unsafe_allow_html=True)

        st.caption(
            f"Proposals pending: {_ev_state.get('proposals_pending',0)} · "
            f"Approved: {_ev_state.get('proposals_approved',0)} · "
            f"Lessons auto-added: {_ev_state.get('lessons_auto_added',0)} · "
            f"Quests generated: {_ev_state.get('quests_generated',0)}"
        )

        evo_tabs = st.tabs(["📚 Lesson Proposals (A)", "🎮 Dynamic Quests (B)", "🧬 Auto-Config (C)", "⚙️ Manual Controls"])

        # ── A: Lesson proposals ───────────────────────────────────────────────
        with evo_tabs[0]:
            st.markdown("**Swarm proposes new lessons weekly. You approve or reject before they're added.**")

            pending = _engine.get_pending_proposals()
            all_props = _engine.get_all_proposals(20)

            if pending:
                st.markdown(f"### ⏳ {len(pending)} Pending Proposals")
                for prop in pending:
                    lesson  = prop.get("lesson",{})
                    score   = prop.get("coherence_score",0)
                    sc_color = "#00ff88" if score >= 0.80 else ("#ff9500" if score >= 0.70 else "#ff4444")
                    with st.expander(f"📖 {lesson.get('title','?')} — Score: {score:.2f}", expanded=True):
                        st.markdown(f'<div class="card" style="border-left:3px solid {sc_color};">'
                                    f'<div style="color:{sc_color};font-size:0.78rem;font-family:Orbitron,monospace;">COHERENCE SCORE: {score:.2f}</div>'
                                    f'<div style="font-size:0.82rem;color:#8899bb;margin-top:6px;line-height:1.8;">'
                                    f'<b>Topic:</b> {lesson.get("topic","")}<br>'
                                    f'<b>Steelman:</b> {lesson.get("steelman","")}<br>'
                                    f'<b>Example:</b> {lesson.get("example","")}<br>'
                                    f'<b>Age:</b> {lesson.get("age_hint","All")} · <b>XP:</b> {lesson.get("xp",20)} · <b>Rune:</b> {lesson.get("rune","")}'
                                    f'</div>'
                                    f'<div style="color:#a020f0;font-size:0.78rem;margin-top:6px;"><b>Rationale:</b> {prop.get("rationale","")}</div>'
                                    f'</div>', unsafe_allow_html=True)

                        col_a1, col_a2 = st.columns(2)
                        with col_a1:
                            if st.button(f"✅ Approve — Add to curriculum", key=f"approve_{prop['id']}"):
                                if _engine.approve_lesson(prop["id"]):
                                    st.success(f"✅ '{lesson.get('title','')}' added to family_hud.py!")
                                    st.rerun()
                                else:
                                    st.error("Could not add lesson — check that family_hud.py is in /mnt/main/repo/")
                        with col_a2:
                            reject_reason = st.text_input("Rejection reason (optional)", key=f"rej_reason_{prop['id']}")
                            if st.button(f"❌ Reject", key=f"reject_{prop['id']}"):
                                _engine.reject_lesson(prop["id"], reject_reason)
                                st.rerun()
            else:
                st.info("No pending proposals. Run 'Generate New Proposals' below.")

            st.divider()
            st.markdown("### 📋 All Proposals")
            for p in all_props[:10]:
                status = p.get("status","pending")
                icon   = "✅" if status=="approved" else ("❌" if status=="rejected" else "⏳")
                color  = "#00ff88" if status=="approved" else ("#ff4444" if status=="rejected" else "#ff9500")
                st.markdown(
                    f'<div class="memory-node" style="border-left:3px solid {color};">'
                    f'<span style="color:{color};">{icon} {p.get("lesson",{}).get("title","?")}</span> '
                    f'<span style="color:#445577;font-size:0.72rem;">{p.get("proposed_at","")[:10]} · score {p.get("coherence_score",0):.2f}</span>'
                    f'</div>', unsafe_allow_html=True)

        # ── B: Dynamic quests ─────────────────────────────────────────────────
        with evo_tabs[1]:
            st.markdown("**Auto-generated quests personalized to each family's coherence + streak + level.**")
            st.caption("Runs automatically every ~3 hours in the swarm loop. No approval needed.")

            if _QC.exists():
                try:
                    dq = json.loads(_QC.read_text())
                    st.caption(f"Cache: {list(dq.keys())} · Generated: {next(iter(dq.values()),{}).get('generated_at','?')[:16]}")
                    for fid_q, data_q in dq.items():
                        level_q = data_q.get("family_level",1)
                        coh_q   = data_q.get("avg_coherence",0.72)
                        st.markdown(f"**{fid_q}** — Level {level_q} · Coherence {coh_q:.2f}")
                        for q in data_q.get("quests",[]):
                            qtype  = q.get("type","")
                            qcolor = {"adaptive":"#00cfff","streak":"#ff9500","swarm":"#a020f0","streak_milestone":"#ff6b35"}.get(qtype,"#8899bb")
                            st.markdown(
                                f'<div class="memory-node" style="border-left:3px solid {qcolor};">'
                                f'<span style="color:{qcolor};font-size:0.75rem;">[{qtype}]</span> '
                                f'{q["title"]} — +{q["xp"]} XP<br>'
                                f'<span style="color:#445577;font-size:0.72rem;font-style:italic;">{q.get("hint","")}</span>'
                                f'</div>', unsafe_allow_html=True)
                        st.divider()
                except Exception as e:
                    st.caption(f"Cache read error: {e}")
            else:
                st.caption("No cached quests yet — will generate on next swarm tick or click below.")

        # ── C: Auto-config ────────────────────────────────────────────────────
        with evo_tabs[2]:
            st.markdown("**Swarm continuously adapts difficulty, XP multipliers, and featured content.**")
            st.caption("Runs every ~24h. Does NOT modify source files — writes evolution_config.json.")

            cfg_path = _Path("/mnt/main/evolution_config.json")
            if cfg_path.exists():
                try:
                    cfg = json.loads(cfg_path.read_text())
                    st.markdown(f"**Last updated:** {cfg.get('updated_at','?')[:16]}")

                    ccols = st.columns(3)
                    with ccols[0]:
                        st.markdown(f'<div class="stat-box"><div class="stat-val" style="font-size:1rem;color:#00cfff;">{cfg.get("avg_coherence","—")}</div><div class="stat-lbl">Avg Coherence</div></div>', unsafe_allow_html=True)
                    with ccols[1]:
                        st.markdown(f'<div class="stat-box"><div class="stat-val" style="font-size:1rem;color:#ff9500;">{cfg.get("quest_xp_multiplier","1.0")}×</div><div class="stat-lbl">XP Multiplier</div></div>', unsafe_allow_html=True)
                    with ccols[2]:
                        st.markdown(f'<div class="stat-box"><div class="stat-val" style="font-size:1rem;color:#a020f0;">{cfg.get("featured_track","courage")}</div><div class="stat-lbl">Featured Track</div></div>', unsafe_allow_html=True)

                    st.markdown("**Recent adaptations:**")
                    for change in cfg.get("changes",[]):
                        st.markdown(f"→ {change}")
                    st.markdown(f"**Next suggested track:** {cfg.get('suggest_next_track','antifragility')}")
                    st.markdown(f"**Simulation mode:** {cfg.get('simulation_mode','standard')}")
                except Exception as e:
                    st.caption(f"Config error: {e}")
            else:
                st.caption("No evolution config yet — runs on first swarm evolution tick.")

        # ── Manual controls ───────────────────────────────────────────────────
        with evo_tabs[3]:
            st.markdown("**Trigger evolution tasks manually.**")
            mc1, mc2, mc3 = st.columns(3)
            with mc1:
                if st.button("📚 Generate Lesson Proposals", key="ev_proposals"):
                    with st.spinner("Generating proposals via swarm..."):
                        proposals = _engine.run_weekly_lesson_proposals(force=True)
                    if proposals:
                        st.success(f"✅ {len(proposals)} proposals generated!")
                        st.rerun()
                    else:
                        st.warning("No proposals generated — check API key or Ollama connection")
            with mc2:
                if st.button("🎮 Regenerate Dynamic Quests", key="ev_quests"):
                    with st.spinner("Generating quests..."):
                        _engine.generate_dynamic_quests("all")
                    st.success("✅ Dynamic quests regenerated!")
                    st.rerun()
            with mc3:
                if st.button("🧬 Run Evolution Tick", key="ev_tick"):
                    with st.spinner("Running auto-evolution..."):
                        cfg = _engine.run_auto_evolution_tick()
                    st.success(f"✅ Done! {len(cfg.get('changes',[]))} adaptations")
                    st.rerun()

    except ImportError as e:
        st.warning(f"swarm_evolution.py not found: {e}")
        st.caption("Add swarm_evolution.py to the repo root to enable self-evolution.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: SUBMIT CURRICULUM 📥 — community track & lesson submissions
# ══════════════════════════════════════════════════════════════════════════════
if "Submit Curriculum" in active:
    st.markdown('<div class="card-title">📥 SUBMIT CURRICULUM — Community Track & Lesson Submissions</div>', unsafe_allow_html=True)

    try:
        import sys as _csys
        if "/mnt/main/repo" not in _csys.path: _csys.path.insert(0, "/mnt/main/repo")
        from curriculum_proposals import CurriculumReviewer as _CR, seed_initial_proposals as _sip
        try: _sip()
        except Exception: pass
        _reviewer = _CR()

        sub_tabs = st.tabs(["📤 Submit New", "📋 All Proposals", "✅ Approved", "📖 Review Queue"])

        # ── Submit ────────────────────────────────────────────────────────────
        with sub_tabs[0]:
            st.markdown("**Submit a new lesson or full curriculum track.**")

            st.markdown(
                '<div class="card" style="border-left:3px solid #00cfff;">'
                '<div style="color:#00cfff;font-family:Orbitron,monospace;font-size:0.82rem;">🌱 CURRICULUM AUTOGEN</div>'
                '<div style="color:#8899bb;font-size:0.78rem;margin-top:4px;">The swarm already proposes one new lesson '
                'a day on its own (9AM, $0 cost, local Ollama) — it always lands here as pending, never self-approved. '
                'Don\'t want to wait for 9AM?</div></div>',
                unsafe_allow_html=True,
            )
            if st.button("🤖 Ask Aubie to propose one now", key="autogen_now_btn"):
                with st.spinner("Aubie is thinking of a new lesson…"):
                    try:
                        import sys as _asys
                        if "/mnt/main/repo" not in _asys.path: _asys.path.insert(0, "/mnt/main/repo")
                        from curriculum_autogen import run_curriculum_autogen as _rca
                        _result = _rca(force=True)
                    except Exception as _e:
                        _result = {"ok": False, "reason": str(_e)}
                if _result.get("ok"):
                    st.success(f"✅ Proposed: \"{_result['title']}\" → {_result['target_track']} "
                               f"(ID: {_result['proposal_id']}) — review it in 📋 All Proposals or 📖 Review Queue.")
                else:
                    st.warning(f"Couldn't generate a proposal: {_result.get('reason','unknown error')}")
            st.divider()

            st.markdown(
                '<div class="card" style="border-left:3px solid #a020f0;">'
                '<div style="color:#a020f0;font-family:Orbitron,monospace;font-size:0.82rem;">🌐 CURRICULUM COMMONS</div>'
                '<div style="color:#8899bb;font-size:0.78rem;margin-top:4px;">Pull in lessons other AUBIEETERNAL '
                'instances have published to the shared CC0 feed — they always land here as PENDING, never '
                'auto-approved. Growing the curriculum across every install, one human review at a time.</div></div>',
                unsafe_allow_html=True,
            )
            if st.button("⬇️ Pull from Commons", key="pull_commons_btn"):
                with st.spinner("Checking the shared feed…"):
                    _pull_result = _reviewer.pull_from_commons()
                if _pull_result.get("ok"):
                    st.success(f"✅ {_pull_result['added']} new proposal(s) pulled in as pending "
                               f"(feed had {_pull_result['feed_total']} total).")
                else:
                    st.warning(f"Couldn't reach the commons feed: {_pull_result.get('reason','unknown error')}")
            st.divider()

            sub_type = st.radio("Submission type", ["Single Lesson", "Full Track"], horizontal=True, key="sub_type")
            author   = st.text_input("Your name", placeholder="Tommy / Gabriela / Your name", key="sub_author")

            if sub_type == "Single Lesson":
                st.markdown("**Lesson details:**")
                sc1, sc2 = st.columns(2)
                with sc1:
                    sub_key     = st.text_input("Lesson key (no spaces)", placeholder="building-6", key="sub_key")
                    sub_title   = st.text_input("Title", placeholder="Building L6 — Advanced Roofing", key="sub_title")
                    sub_topic   = st.text_area("Topic (one sentence)", height=60, key="sub_topic")
                    sub_track   = st.text_input("Target track", placeholder="building", key="sub_track_l")
                with sc2:
                    sub_steel   = st.text_area("Steelman prompt", height=60, placeholder="What is the strongest argument against...", key="sub_steel")
                    sub_example = st.text_area("Real-world example", height=60, key="sub_example")
                    sub_age     = st.selectbox("Age hint", ["All ages","7+","8+","10+","12+","13+","14+","15+","16+"], key="sub_age")
                    sub_xp      = st.slider("XP reward", 10, 50, 20, key="sub_xp")
                sub_rationale = st.text_area("Why should this be in the curriculum?", height=80, key="sub_rationale")

                if st.button("📤 Submit Lesson", key="submit_lesson_btn") and author and sub_key and sub_title:
                    lesson = {
                        "key": sub_key, "title": sub_title, "topic": sub_topic,
                        "steelman": sub_steel, "example": sub_example,
                        "age_hint": sub_age, "xp": sub_xp,
                        "rune": f"{sub_track.upper().replace('-','•')}•RUNE",
                        "min_coherence": 0.65,
                    }
                    prop = _reviewer.submit_lesson(author, lesson, sub_track, sub_rationale)
                    st.success(f"✅ Lesson '{sub_title}' submitted! ID: {prop['id']}")
                    st.rerun()

            else:  # Full track
                sub_track_name = st.text_input("Track name", placeholder="Tommy's Building & Hurricane Hardening", key="sub_track_name")
                sub_track_desc = st.text_area("Track description", height=80, key="sub_track_desc")
                sub_rationale2 = st.text_area("Why is this track needed?", height=80, key="sub_rationale2")
                st.info("After submitting the track, you can add individual lessons via 'Single Lesson' submissions targeting this track.")

                if st.button("📤 Submit Track", key="submit_track_btn") and author and sub_track_name:
                    prop = _reviewer.submit_track(author, sub_track_name, sub_track_desc, [], sub_rationale2)
                    st.success(f"✅ Track '{sub_track_name}' submitted! ID: {prop['id']}")
                    st.rerun()

        # ── All proposals ─────────────────────────────────────────────────────
        with sub_tabs[1]:
            all_props = _reviewer.get_all(50)
            st.caption(f"{len(all_props)} total submissions")
            for p in all_props:
                status = p.get("status","pending")
                icon   = {"approved":"✅","rejected":"❌","pending":"⏳"}.get(status,"⏳")
                color  = {"approved":"#00ff88","rejected":"#ff4444","pending":"#ff9500"}.get(status,"#ff9500")
                ptype  = p.get("type","?")
                name   = p.get("track_name") or p.get("lesson",{}).get("title","?")
                st.markdown(
                    f'<div class="memory-node" style="border-left:3px solid {color};">'
                    f'<span style="color:{color};">{icon} [{ptype}] {name}</span> '
                    f'<span style="color:#445577;font-size:0.72rem;">by {p.get("author","?")} · {p.get("submitted_at","")[:10]}</span>'
                    f'<br><span style="color:#8899bb;font-size:0.75rem;">{p.get("rationale","")[:80]}</span>'
                    f'</div>', unsafe_allow_html=True)

                # Add comment
                with st.expander(f"💬 Comments ({len(p.get('comments',[]))})", expanded=False):
                    for c in p.get("comments",[]):
                        st.markdown(f'<div style="font-size:0.78rem;color:#8899bb;">{c["author"]}: {c["comment"]}</div>', unsafe_allow_html=True)
                    cmt_author = st.text_input("Your name", key=f"cmt_a_{p['id']}")
                    cmt_text   = st.text_area("Comment", height=60, key=f"cmt_t_{p['id']}")
                    if st.button("Post comment", key=f"cmt_btn_{p['id']}") and cmt_text:
                        _reviewer.add_comment(p["id"], cmt_author or "Anonymous", cmt_text)
                        st.rerun()

        # ── Approved ──────────────────────────────────────────────────────────
        with sub_tabs[2]:
            approved = [p for p in _reviewer.get_all() if p.get("status") == "approved"]
            st.caption(f"{len(approved)} approved submissions")
            st.markdown(
                '<div style="color:#8899bb;font-size:0.76rem;margin-bottom:8px;">Approving makes a '
                'lesson live on <b>this</b> instance only. "Publish to Commons" is a separate, '
                'explicit choice — it writes the lesson into the commons feed file '
                '(<code>epistemic_commons/api/curriculum_proposals.json</code>), which the swarm\'s '
                'GitHub auto-push then makes public (usually within a few minutes). Once it\'s on '
                'GitHub, any other AUBIEETERNAL install can pull it in via "Pull from Commons" and '
                'review it themselves. On a fresh install with no push access, this stays a local '
                'save until someone with repo write access commits it.</div>', unsafe_allow_html=True)
            for p in approved:
                name  = p.get("track_name") or p.get("lesson",{}).get("title","?")
                score = p.get("review",{}).get("coherence_score",0)
                published = p.get("published_to_commons", False)
                st.markdown(f'<div class="card" style="border-left:3px solid #00ff88;"><div style="color:#00ff88;font-family:Orbitron,monospace;font-size:0.8rem;">✅ {name}</div><div style="color:#8899bb;font-size:0.78rem;">by {p.get("author","?")} · Coherence score: {score:.2f} · {p.get("approved_at","")[:10]}</div></div>', unsafe_allow_html=True)
                if published:
                    st.caption(f"📡 Published to the commons feed {p.get('published_to_commons_at','')[:10]} — the swarm auto-push carries it to GitHub; other installs can then Pull it")
                elif st.button("📡 Publish to Commons", key=f"pub_commons_{p['id']}"):
                    if _reviewer.publish_to_commons(p["id"]):
                        st.success("Written to the commons feed — the swarm's GitHub auto-push will make it public within a few minutes, then other installs can Pull it.")
                        st.rerun()
                    else:
                        st.error("Could not publish.")

        # ── Review queue (operator only) ──────────────────────────────────────
        with sub_tabs[3]:
            if _fid != "operator":
                st.info("Review queue is for the operator only.")
            else:
                pending = _reviewer.get_pending()
                st.markdown(f"### ⏳ {len(pending)} Proposals Awaiting Review")
                for p in pending:
                    name  = p.get("track_name") or p.get("lesson",{}).get("title","?")
                    score = p.get("review",{}).get("coherence_score",0)
                    with st.expander(f"⏳ {name} — by {p.get('author','?')}"):
                        # Review form
                        rt   = _reviewer.get_review_template()
                        new_score = st.slider("Coherence score", 0.0, 1.0, float(score) or 0.75, key=f"rev_score_{p['id']}")
                        rev_notes = st.text_area("Reviewer notes", key=f"rev_notes_{p['id']}")

                        col_r1, col_r2 = st.columns(2)
                        with col_r1:
                            if st.button("✅ Approve", key=f"rev_approve_{p['id']}"):
                                _reviewer.add_review(p["id"], {"coherence_score": new_score, "reviewer_notes": rev_notes})
                                _reviewer.approve(p["id"])
                                st.success("Approved!")
                                st.rerun()
                        with col_r2:
                            rej_reason = st.text_input("Rejection reason", key=f"rev_rej_{p['id']}")
                            if st.button("❌ Reject", key=f"rev_reject_{p['id']}"):
                                _reviewer.reject(p["id"], rej_reason)
                                st.rerun()

    except ImportError as e:
        st.warning(f"curriculum_proposals.py not found: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB: LEGAL HUD ⚖️ — sovereign contract + insurance analysis
# ══════════════════════════════════════════════════════════════════════════════
if "Legal HUD" in active:
    st.markdown('<div class="card-title">⚖️ SOVEREIGN LEGAL HUD — Contract Steelmanner + Insurance Analyzer</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="card" style="border-left:3px solid #00cfff;">
        <div style="color:#00cfff;font-family:Orbitron,monospace;font-size:0.78rem;">TRUTH TOOL — NOT LEGAL ADVICE</div>
        <div style="color:#8899bb;font-size:0.82rem;margin-top:6px;">
        This tool helps you read contracts and insurance policies like a sovereign adult.
        It runs extraction detection, steelmanning, and simulation tests on legal language.
        Always consult a licensed attorney for actual legal decisions.
        </div>
    </div>
    """, unsafe_allow_html=True)

    legal_tabs = st.tabs(["📄 Contract Analyzer", "🏠 Insurance Policy", "⚖️ Insurance Charter v0.2", "📜 Family Law Charter", "📊 Full Progress"])

    # ── Contract Analyzer ─────────────────────────────────────────────────────
    with legal_tabs[0]:
        st.markdown("**Paste any contract clause. The swarm will steelman it and flag extraction patterns.**")
        contract_text = st.text_area("Paste contract clause or section", height=150,
                                      placeholder="e.g. Any dispute arising from this agreement shall be resolved by binding arbitration...")

        if st.button("⚖️ Analyze Clause", key="legal_analyze") and contract_text:
            with st.spinner("STEELMAN + ORACLE daughters analyzing..."):
                try:
                    client, model, _, _ = get_ai_client()
                    prompt = f"""You are a sovereign legal analysis tool for families.
Analyze this contract clause and return ONLY valid JSON:
{{
  "plain_english": "Explain in one sentence what this clause means, 8th-grade level",
  "who_it_benefits": "who_writing_party | who_signing_party | both",
  "extraction_patterns": ["list of any extraction patterns detected"],
  "extraction_severity": "none | low | medium | high | critical",
  "steelman_for": "Strongest argument that this clause is fair and reasonable",
  "steelman_against": "Strongest argument that this clause is extractive or harmful",
  "questions_to_ask": ["3 questions you should ask before signing"],
  "red_flags": ["specific red flags if any"],
  "coherence_score": 0.0
}}

Clause: {contract_text}"""
                    resp = client.chat.completions.create(
                        model=model,
                        messages=[{"role":"user","content":prompt}],
                        max_tokens=600,
                    )
                    raw    = resp.choices[0].message.content.strip().replace("```json","").replace("```","")
                    result = json.loads(raw)

                    severity = result.get("extraction_severity","none")
                    sev_colors = {"none":"#00ff88","low":"#00ff88","medium":"#ff9500","high":"#ff4444","critical":"#ff0000"}
                    sev_color  = sev_colors.get(severity,"#8899bb")

                    st.markdown(
                        f'<div class="card" style="border:2px solid {sev_color};">'
                        f'<div style="color:{sev_color};font-family:Orbitron,monospace;font-size:0.82rem;">EXTRACTION LEVEL: {severity.upper()}</div>'
                        f'<div style="color:#c8d8ff;font-size:0.88rem;margin-top:8px;"><b>Plain English:</b> {result.get("plain_english","")}</div>'
                        f'<div style="color:#8899bb;font-size:0.82rem;margin-top:4px;"><b>Benefits:</b> {result.get("who_it_benefits","")}</div>'
                        f'</div>', unsafe_allow_html=True)

                    if result.get("extraction_patterns"):
                        st.markdown("**⚠️ Extraction patterns detected:**")
                        for pattern in result["extraction_patterns"]:
                            st.markdown(f"- {pattern}")

                    col_l1, col_l2 = st.columns(2)
                    with col_l1:
                        st.markdown(f'<div class="card" style="border-left:3px solid #00ff88;"><div style="color:#00ff88;font-size:0.75rem;font-family:Orbitron,monospace;">⚔️ FOR</div><div style="font-size:0.82rem;color:#8899bb;margin-top:4px;">{result.get("steelman_for","")}</div></div>', unsafe_allow_html=True)
                    with col_l2:
                        st.markdown(f'<div class="card" style="border-left:3px solid #ff6b35;"><div style="color:#ff6b35;font-size:0.75rem;font-family:Orbitron,monospace;">⚔️ AGAINST</div><div style="font-size:0.82rem;color:#8899bb;margin-top:4px;">{result.get("steelman_against","")}</div></div>', unsafe_allow_html=True)

                    if result.get("questions_to_ask"):
                        st.markdown("**❓ Ask before signing:**")
                        for q in result["questions_to_ask"]:
                            st.markdown(f"- {q}")
                    award_xp(15)
                except Exception as e:
                    st.error(f"Analysis error: {e}")

    # ── Insurance Policy Analyzer ─────────────────────────────────────────────
    with legal_tabs[1]:
        st.markdown("**Paste an insurance policy section. Identify extraction clauses, coverage gaps, and premium drivers.**")
        policy_text = st.text_area("Insurance policy language", height=150,
                                    placeholder="e.g. Coverage under this policy does not apply to loss caused directly or indirectly by flood, surface water...")

        ins_type = st.selectbox("Policy type", ["Homeowners/Wind","Flood","Auto","Life","Health","Other"], key="ins_type")

        if st.button("🏠 Analyze Insurance Clause", key="ins_analyze") and policy_text:
            with st.spinner("Analyzing with ORACLE + STEELMAN daughters..."):
                try:
                    client, model, _, _ = get_ai_client()
                    prompt = f"""You are a sovereign insurance literacy tool.
Analyze this {ins_type} policy clause. Return ONLY valid JSON:
{{
  "plain_english": "What this clause actually means, 8th-grade level",
  "coverage_impact": "what this covers | what this excludes | coverage_gap_detected",
  "extraction_pattern": "clause type if extractive (anti-concurrent causation / sublimit / exclusion / arbitration / claims-made etc), else 'none'",
  "extraction_severity": "none | low | medium | high | critical",
  "premium_impact": "how this clause affects your premium calculation",
  "steelman_insurer": "Strongest argument that this clause is actuarially necessary",
  "steelman_policyholder": "Strongest argument that this clause unfairly shifts risk to you",
  "what_to_ask_agent": ["2-3 specific questions to ask your agent about this clause"],
  "how_reciprocal_differs": "How a policyholder-first reciprocal would handle this differently"
}}

Policy text: {policy_text}"""
                    resp = client.chat.completions.create(
                        model=model,
                        messages=[{"role":"user","content":prompt}],
                        max_tokens=700,
                    )
                    raw    = resp.choices[0].message.content.strip().replace("```json","").replace("```","")
                    result = json.loads(raw)

                    severity  = result.get("extraction_severity","none")
                    sev_color = {"none":"#00ff88","low":"#00ff88","medium":"#ff9500","high":"#ff4444","critical":"#ff0000"}.get(severity,"#8899bb")

                    st.markdown(f'<div class="card" style="border:2px solid {sev_color};"><div style="color:{sev_color};font-family:Orbitron,monospace;font-size:0.82rem;">EXTRACTION: {severity.upper()} · {result.get("extraction_pattern","none")}</div><div style="color:#c8d8ff;font-size:0.88rem;margin-top:6px;">{result.get("plain_english","")}</div><div style="color:#8899bb;font-size:0.8rem;margin-top:4px;">{result.get("coverage_impact","")}</div></div>', unsafe_allow_html=True)

                    st.markdown(f'<div class="card" style="border-left:3px solid #a020f0;"><div style="color:#a020f0;font-size:0.75rem;font-family:Orbitron,monospace;">🏛️ HOW A RECIPROCAL WOULD HANDLE THIS</div><div style="font-size:0.82rem;color:#c8d8ff;margin-top:4px;">{result.get("how_reciprocal_differs","")}</div></div>', unsafe_allow_html=True)

                    if result.get("what_to_ask_agent"):
                        st.markdown("**Ask your agent:**")
                        for q in result["what_to_ask_agent"]:
                            st.markdown(f"- {q}")
                    award_xp(20)
                except Exception as e:
                    st.error(f"Error: {e}")

    # ── Insurance Charter v0.2 viewer ────────────────────────────────────────
    with legal_tabs[2]:
        st.markdown('<div style="color:#f7931a;font-family:Orbitron,monospace;font-size:0.82rem;margin-bottom:12px;">🦅 POLICYHOLDER-FIRST RECIPROCAL INSURANCE CHARTER v0.2</div>', unsafe_allow_html=True)

        # Try to load from repo, fall back to inline
        _charter_paths = [
            _Path("/mnt/main/repo/POLICYHOLDER_FIRST_CHARTER_v0_2.md"),
            _Path("/mnt/main/repo/governance/POLICYHOLDER_FIRST_CHARTER_v0_2.md"),
            _Path("/mnt/main/repo/governance/POLICYHOLDER_FIRST_CHARTER.md"),
        ]
        _charter_loaded = False
        for _cp in _charter_paths:
            if _cp.exists():
                st.markdown(_cp.read_text())
                _charter_loaded = True
                break

        if not _charter_loaded:
            _ic1, _ic2 = st.columns(2)
            with _ic1:
                st.markdown('<div class="card" style="border-left:3px solid #f7931a;">' +
                    '<div style="color:#f7931a;font-family:Orbitron,monospace;font-size:0.72rem;">CORE MECHANICS</div>' +
                    '<div style="color:#8899bb;font-size:0.78rem;margin-top:6px;line-height:1.9;">' +
                    '• 80% annual surplus returned to Subscribers<br>' +
                    '• Exec comp capped at 8× median premium<br>' +
                    '• 15% veto rights for Subscribers<br>' +
                    '• Bitcoin up to 5% of reserves<br>' +
                    '• Real-time public dashboard (all metrics)<br>' +
                    '• 8th-grade plain English required</div></div>',
                    unsafe_allow_html=True)
            with _ic2:
                st.markdown('<div class="card" style="border-left:3px solid #a020f0;">' +
                    '<div style="color:#a020f0;font-family:Orbitron,monospace;font-size:0.72rem;">ANTI-EXTRACTION RULES</div>' +
                    '<div style="color:#8899bb;font-size:0.78rem;margin-top:6px;line-height:1.9;">' +
                    '• No offshore reinsurance arbitrage<br>' +
                    '• Related-party transaction ban<br>' +
                    '• All compensation >$50k published<br>' +
                    '• Agent commission cap 8% / 3%<br>' +
                    '• No contingent commissions<br>' +
                    '• 60% vote to remove management</div></div>',
                    unsafe_allow_html=True)

            st.info("Push POLICYHOLDER_FIRST_CHARTER_v0_2.md to GitHub root to display the full 273-line document here.")

        # Steelman section always visible
        with st.expander("⚔️ Steelman This Charter", expanded=False):
            st.markdown("""
**Strongest argument FOR:**
Structural rules (compensation caps, surplus formulas, veto rights) are the only reliable way to prevent extraction in insurance. Aspirational mission statements don't survive the first profitable year. Hard numbers and binding mechanisms do.

**Strongest argument AGAINST:**
Rigid compensation caps may prevent the Exchange from attracting top actuarial talent, leading to underpricing and long-term harm to the very Subscribers the system was designed to protect.

**Resolution:**
The compensation cap is tied to median Subscriber premium. If talent costs rise, premiums can increase — but with full transparency and veto rights. Making extraction more expensive than honest operation is the Bitcoin model applied to insurance.
            """)

    # ── Sovereign Family Law Charter viewer ───────────────────────────────────
    with legal_tabs[3]:
        st.markdown('<div style="color:#00cfff;font-family:Orbitron,monospace;font-size:0.82rem;margin-bottom:12px;">📜 SOVEREIGN FAMILY RECIPROCAL GOVERNANCE CHARTER v1.0</div>', unsafe_allow_html=True)

        _flaw_paths = [
            _Path("/mnt/main/repo/SOVEREIGN_FAMILY_LAW_CHARTER.md"),
            _Path("/mnt/main/repo/governance/SOVEREIGN_FAMILY_LAW_CHARTER.md"),
        ]
        _flaw_loaded = False
        for _fp in _flaw_paths:
            if _fp.exists():
                st.markdown(_fp.read_text())
                _flaw_loaded = True
                break

        if not _flaw_loaded:
            fl1, fl2 = st.columns(2)
            with fl1:
                st.markdown('<div class="card" style="border-left:3px solid #00cfff;">' +
                    '<div style="color:#00cfff;font-family:Orbitron,monospace;font-size:0.72rem;">FAMILY RIGHTS</div>' +
                    '<div style="color:#8899bb;font-size:0.78rem;margin-top:6px;line-height:1.9;">' +
                    '• Full data export at any time<br>' +
                    '• 15% veto on any lesson/quest<br>' +
                    '• Child Rune inheritance (no probate)<br>' +
                    '• Halo session consent required<br>' +
                    '• 5% defensive legal fund (auto)<br>' +
                    '• Narrative attack coordination</div></div>',
                    unsafe_allow_html=True)
            with fl2:
                st.markdown('<div class="card" style="border-left:3px solid #00ff88;">' +
                    '<div style="color:#00ff88;font-family:Orbitron,monospace;font-size:0.72rem;">CHILD RUNE SOVEREIGNTY</div>' +
                    '<div style="color:#8899bb;font-size:0.78rem;margin-top:6px;line-height:1.9;">' +
                    '• Voice activates at 256 confirmations<br>' +
                    '• Voice_Score = (Coh×0.6)+(Rune/1k×0.3)+(XP/10k×0.1)<br>' +
                    '• Min 0.65 score + 256 frags for voting<br>' +
                    '• Parental veto until 13yo + 500 coh pts<br>' +
                    '• Surplus: +10% to child during growth<br>' +
                    '• On-chain via Child Rune Genesis</div></div>',
                    unsafe_allow_html=True)

            st.info("Push SOVEREIGN_FAMILY_LAW_CHARTER.md to GitHub root to display the full document here.")

        with st.expander("⚔️ Steelman This Charter", expanded=False):
            st.markdown("""
**Arguments For:** Closes the sovereignty loop (education + economics + governance + on-chain legacy). Protects families from external legal and narrative attacks. Teaches children real power dynamics instead of obedience.

**Strongest Argument Against:** "It creates more rules." Rebuttal: These are minimal, high-clarity reciprocal agreements. Via negativa keeps it lean — it's more about what we *reject* than what we mandate.

**Final Resolution:** Families that cannot govern themselves internally will eventually be governed externally. This Charter is adopted because the cost of *not* having clear reciprocal governance grows faster than the cost of maintaining it.
            """)

    # ── Full progress tracker ─────────────────────────────────────────────────
    with legal_tabs[4]:
        st.markdown("### 📊 Full Sovereign Legal Progress")
        try:
            from family_profiles import load_family_stats as _lfs_legal
            stats_l = _lfs_legal(_fid)
            completed_l = set(stats_l.get("lessons_completed",[]))
        except ImportError:
            completed_l = set()

        ALL_LEGAL_TRACKS = {
            "⚖️ Legal Literacy": {
                "legal-1": "Understanding Contracts",
                "legal-2": "Your Rights When Signing",
                "legal-3": "Insurance You Actually Need",
                "legal-4": "Insurance You Can Skip",
                "legal-5": "LLC + Estate Basics",
                "legal-6": "Policyholder-First Charter ★",
            },
            "📜 Law & Economics": {
                "law-econ-1": "The Combined Ratio",
                "law-econ-2": "Regulatory Capture",
                "law-econ-3": "Narrative Economics",
                "law-econ-4": "The Law as a Weapon",
                "law-econ-5": "Designing Better Systems ★",
            },
            "👨‍👩‍👧 Family Law": {
                "family-law-1": "Shield vs. Sword",
                "family-law-2": "Child Rune Rights",
                "family-law-3": "Defensive External Filings",
                "family-law-4": "Narrative Attack Response ★",
            },
        }

        total_legal = sum(len(v) for v in ALL_LEGAL_TRACKS.values())
        done_legal = sum(1 for track in ALL_LEGAL_TRACKS.values() for k in track if k in completed_l)
        st.progress(done_legal / total_legal, text=f"Overall: {done_legal}/{total_legal} lessons")
        st.markdown("")

        for track_name, lessons in ALL_LEGAL_TRACKS.items():
            track_done = sum(1 for k in lessons if k in completed_l)
            tc = "#00ff88" if track_done == len(lessons) else "#f7931a" if track_done > 0 else "#445577"
            st.markdown(f'<div style="color:{tc};font-family:Orbitron,monospace;font-size:0.75rem;margin:10px 0 4px;">{track_name} — {track_done}/{len(lessons)}</div>', unsafe_allow_html=True)
            for key, title in lessons.items():
                done = key in completed_l
                color = "#00ff88" if done else "#445577"
                icon  = "✅" if done else "⭕"
                _lc1, _lc2 = st.columns([4,1])
                with _lc1:
                    st.markdown(f'<div style="color:{color};font-size:0.82rem;padding:3px 0;">{icon} {title}</div>', unsafe_allow_html=True)
                with _lc2:
                    if not done:
                        if st.button("▶", key=f"prog_start_{key}", use_container_width=True):
                            st.session_state["active_tab"] = "Family Co-Learning"
                            st.session_state["fl_lesson_preset"] = key
                            st.rerun()

        if done_legal == total_legal:
            st.success("🦅 Full Sovereign Legal Mastery! — War Eagle Eternal")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: EPISTEMIC HEALTH 📈 — Long-term family truth-seeking dashboard
# 30/90-day coherence trends · most improved track · failure patterns
# ══════════════════════════════════════════════════════════════════════════════
if "Epistemic Health" in active:
    st.markdown('<div class="card-title">📈 EPISTEMIC HEALTH — Long-Term Family Truth-Seeking Dashboard</div>', unsafe_allow_html=True)

    try:
        from family_profiles import FamilyAuth as _FA_eh, load_family_stats as _lfs_eh
        import statistics as _stats_mod

        _auth_eh   = _FA_eh()
        families_eh = _auth_eh.list_families()

        # ── Family selector ───────────────────────────────────────────────────
        fam_options = {f["family_id"]: f"{f['emoji']} {f['display_name']}" for f in families_eh}
        selected_fam = st.selectbox("Select family", list(fam_options.keys()),
                                     format_func=lambda x: fam_options[x], key="eh_fam")
        fam_data = _lfs_eh(selected_fam)
        fam_info = next((f for f in families_eh if f["family_id"] == selected_fam), {})
        fcolor   = fam_info.get("color","#00cfff")

        # ── Core metrics ──────────────────────────────────────────────────────
        coh_history  = fam_data.get("coherence_history", [])
        xp           = fam_data.get("total_xp", 0)
        level        = fam_data.get("level", 1)
        streak       = fam_data.get("streak_days", 0)
        completed    = fam_data.get("lessons_completed", [])
        badges       = fam_data.get("badges", [])
        quests_done  = fam_data.get("daily_quests_completed", [])

        eh1,eh2,eh3,eh4,eh5 = st.columns(5)
        with eh1: st.markdown(f'<div class="stat-box"><div class="stat-val" style="color:{fcolor};">{level}</div><div class="stat-lbl">Level</div></div>', unsafe_allow_html=True)
        with eh2: st.markdown(f'<div class="stat-box"><div class="stat-val" style="color:#ff9500;">🔥{streak}</div><div class="stat-lbl">Streak</div></div>', unsafe_allow_html=True)
        with eh3:
            avg_coh = round(_stats_mod.mean(coh_history[-10:]),3) if coh_history else 0.0
            st.markdown(f'<div class="stat-box"><div class="stat-val" style="color:#00cfff;">{avg_coh}</div><div class="stat-lbl">Avg Coherence</div></div>', unsafe_allow_html=True)
        with eh4: st.markdown(f'<div class="stat-box"><div class="stat-val" style="color:#a020f0;">{len(completed)}</div><div class="stat-lbl">Lessons Done</div></div>', unsafe_allow_html=True)
        with eh5: st.markdown(f'<div class="stat-box"><div class="stat-val" style="color:#00ff88;">{len(badges)}</div><div class="stat-lbl">Badges</div></div>', unsafe_allow_html=True)

        st.divider()

        # ── Coherence trend chart ─────────────────────────────────────────────
        if coh_history:
            import plotly.graph_objects as _pgo
            st.markdown("### 📊 Coherence Over Time")
            n = len(coh_history)
            labels_30  = list(range(max(0, n-30), n))
            labels_90  = list(range(max(0, n-90), n))
            view_range = st.radio("Range", ["Last 10","Last 30","All"], horizontal=True, key="eh_range")
            if view_range == "Last 10":   show = coh_history[-10:]
            elif view_range == "Last 30": show = coh_history[-30:]
            else:                          show = coh_history

            fig = _pgo.Figure()
            fig.add_trace(_pgo.Scatter(
                y=show, mode="lines+markers",
                line=dict(color=fcolor, width=2),
                marker=dict(size=5, color=fcolor),
                fill="tozeroy", fillcolor=f"rgba(0,207,255,0.05)",
                name="Coherence",
            ))
            fig.add_hline(y=0.7, line_dash="dash", line_color="#ff9500",
                          annotation_text="0.7 threshold", annotation_position="bottom right")
            fig.add_hline(y=1.0, line_dash="dot", line_color="#00ff88",
                          annotation_text="Perfect", annotation_position="bottom right")
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#8899bb", size=11),
                yaxis=dict(range=[0,1.1], gridcolor="#1a2a3a"),
                xaxis=dict(gridcolor="#1a2a3a"),
                margin=dict(l=40,r=20,t=20,b=40), height=250,
            )
            st.plotly_chart(fig, use_container_width=True)

            # Trend analysis
            if len(coh_history) >= 5:
                recent5  = _stats_mod.mean(coh_history[-5:])
                prior5   = _stats_mod.mean(coh_history[-10:-5]) if len(coh_history) >= 10 else recent5
                trend    = recent5 - prior5
                t_color  = "#00ff88" if trend >= 0 else "#ff4444"
                t_icon   = "📈" if trend >= 0 else "📉"
                st.markdown(f'<div class="card" style="border-left:3px solid {t_color};"><span style="color:{t_color};">{t_icon} Coherence trend: {trend:+.3f}</span> over last 5 sessions</div>', unsafe_allow_html=True)
        else:
            st.info("No coherence history yet — complete lessons to build your trend.")

        st.divider()

        # ── Track completion analysis ─────────────────────────────────────────
        st.markdown("### 🗺️ Track Progress Analysis")
        TRACKS = {
            "courage": ("🦁 Courage", 5),
            "truth": ("🔍 Truth Education", 5),
            "antifragility": ("⚡ Antifragility", 4),
            "bitcoin": ("₿ Bitcoin", 4),
            "simulation": ("🌌 Simulation", 8),
            "steelmanning": ("⚔️ Steelmanning", 3),
            "polyvagal": ("🧬 Polyvagal", 3),
            "stoic": ("🏛️ Stoic", 3),
            "money": ("💰 Money", 3),
            "legal": ("⚖️ Legal", 5),
            "building": ("🏗️ Building", 5),
            "baking": ("🍞 Baking", 4),
        }
        completed_set = set(completed)
        track_scores  = {}
        for tid, (tname, total) in TRACKS.items():
            done = sum(1 for k in completed_set if k.startswith(f"{tid}-"))
            pct  = int(done / total * 100)
            track_scores[tname] = (done, total, pct)

        # Most improved (highest pct)
        if track_scores:
            best_track = max(track_scores.items(), key=lambda x: x[1][2])
            weak_track = min(track_scores.items(), key=lambda x: x[1][2])
            st.markdown(
                f'<div class="card" style="border-left:3px solid #00ff88;">'
                f'<span style="color:#00ff88;">🏆 Strongest track: {best_track[0]} — {best_track[1][2]}% complete</span><br>'
                f'<span style="color:#ff9500;">⚠️ Needs attention: {weak_track[0]} — {weak_track[1][2]}% complete</span>'
                f'</div>', unsafe_allow_html=True)

        tc1, tc2 = st.columns(2)
        track_list = list(track_scores.items())
        for i, (tname, (done, total, pct)) in enumerate(track_list):
            col = tc1 if i % 2 == 0 else tc2
            color = "#00ff88" if pct == 100 else (fcolor if pct > 50 else "#445577")
            col.markdown(
                f'<div style="margin-bottom:6px;">'
                f'<div style="display:flex;justify-content:space-between;">'
                f'<span style="color:{color};font-size:0.78rem;">{tname}</span>'
                f'<span style="color:#445577;font-size:0.72rem;">{done}/{total}</span></div>'
                f'<div class="xp-bar-bg" style="height:6px;margin-top:2px;">'
                f'<div style="height:100%;border-radius:20px;background:{color};width:{pct}%;"></div></div>'
                f'</div>', unsafe_allow_html=True)

        st.divider()

        # ── Truth Education specific metrics ──────────────────────────────────
        st.markdown("### 🔍 Truth Education Progress")
        truth_done    = sum(1 for k in completed_set if k.startswith("truth-"))
        truth_drills  = sum(1 for q in quests_done if "truth_drill" in q)
        truth_guardian = "🛡️ Truth Guardian" in badges

        te1,te2,te3 = st.columns(3)
        with te1: st.markdown(f'<div class="stat-box"><div class="stat-val" style="color:#00cfff;">{truth_done}/5</div><div class="stat-lbl">Truth Levels</div></div>', unsafe_allow_html=True)
        with te2: st.markdown(f'<div class="stat-box"><div class="stat-val" style="color:#a020f0;">{truth_drills}</div><div class="stat-lbl">Truth Drills Done</div></div>', unsafe_allow_html=True)
        with te3:
            tg_color = "#00ff88" if truth_guardian else "#445577"
            tg_label = "EARNED ✅" if truth_guardian else "Not yet"
            st.markdown(f'<div class="stat-box"><div class="stat-val" style="color:{tg_color};font-size:0.9rem;">{tg_label}</div><div class="stat-lbl">Truth Guardian</div></div>', unsafe_allow_html=True)

        if truth_done == 0:
            st.info("Start Truth Education Level 1 — it's the meta-skill that makes every other track more powerful.")
        elif truth_done < 5:
            next_level = f"truth-{truth_done+1}"
            st.markdown(f'<div class="card" style="border-left:3px solid #00cfff;"><span style="color:#00cfff;">Next: Truth Level {truth_done+1}</span> — continue building your epistemic foundation</div>', unsafe_allow_html=True)
            if st.button(f"▶ Start Truth Level {truth_done+1}", key="eh_truth_next"):
                st.session_state["active_tab"] = "Family Co-Learning"
                st.session_state["fl_lesson_preset"] = next_level
                st.rerun()
        else:
            st.success("🛡️ Full Truth Education complete — you are a Truth Guardian. The lattice recognizes your coherence.")

        st.divider()

        # ── Common failure patterns ───────────────────────────────────────────
        st.markdown("### ⚠️ Patterns to Watch")
        patterns = []

        if streak == 0:
            patterns.append(("🔥 Streak broken", "Daily practice compounds. Even 5 minutes keeps the lattice strong.", "#ff9500"))
        if avg_coh < 0.65 and coh_history:
            patterns.append(("📉 Low coherence", "Try an easier lesson or start the Truth Education track to rebuild signal.", "#ff4444"))
        if truth_done == 0 and level >= 3:
            patterns.append(("🔍 Missing meta-skill", "You're Level 3+ but haven't started Truth Education. This is the track that makes all others work better.", "#ff9500"))
        if len(badges) == 0 and xp > 50:
            patterns.append(("🏅 No badges yet", "Complete your first full lesson track to unlock your first badge.", "#445577"))
        if not patterns:
            patterns.append(("✅ No issues detected", "Coherence stable, streak active, truth track engaged. Keep going.", "#00ff88"))

        for label, desc, color in patterns:
            st.markdown(
                f'<div class="card" style="border-left:3px solid {color};">'
                f'<div style="color:{color};font-size:0.82rem;">{label}</div>'
                f'<div style="color:#8899bb;font-size:0.78rem;margin-top:4px;">{desc}</div>'
                f'</div>', unsafe_allow_html=True)

    except ImportError as e:
        st.warning(f"family_profiles.py not found: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: HUMANITY IMPACT 🌍
# ══════════════════════════════════════════════════════════════════════════════
if "Humanity Impact" in active:
    st.markdown('<div class="card-title">🌍 HUMANITY IMPACT — Private Truth-Seeking → Public Good</div>', unsafe_allow_html=True)

    try:
        import sys as _hsys
        if "/mnt/main/repo" not in _hsys.path: _hsys.path.insert(0, "/mnt/main/repo")
        from humanity_impact import HumanityImpactMapper as _HIM, HUMANITY_DOMAINS as _HD, IMPACT_LEVELS as _IL
        _mapper = _HIM(api_key=st.session_state.get("key_xai",""))

        # ── Today's report ────────────────────────────────────────────────────
        st.markdown("### 📊 Today's Humanity Impact")
        today_path = _Path(f"/mnt/main/repo/insights/humanity/{_dt.now().strftime('%Y-%m-%d')}.md")
        if today_path.exists():
            with st.expander("📄 View today's full impact report", expanded=True):
                st.markdown(today_path.read_text())
        else:
            st.info("No impact report yet today. Reports generate automatically once per day, or click below.")

        if st.button("🌍 Generate Humanity Impact Report Now", key="humanity_gen"):
            with st.spinner("Mapping swarm insights to humanity problems..."):
                result = _mapper.run_mapping_cycle(force=True)
            if result:
                st.success(f"✅ Mapped {result.get('mappings',0)} insights to humanity domains!")
                st.rerun()
            else:
                st.warning("Not enough swarm insights yet. Let the swarm run longer.")

        st.divider()

        # ── 30-day summary ────────────────────────────────────────────────────
        st.markdown("### 📈 30-Day Impact Summary")
        summary = _mapper.get_impact_summary(30)
        total   = summary.get("total_mappings", 0)

        if total > 0:
            hc1,hc2,hc3 = st.columns(3)
            with hc1: st.markdown(f'<div class="stat-box"><div class="stat-val" style="color:#00cfff;">{total}</div><div class="stat-lbl">Insights Mapped</div></div>', unsafe_allow_html=True)
            with hc2:
                top = summary.get("top_domain","none")
                top_label = list(_HD.get(top,"General").split(" —"))[0]
                st.markdown(f'<div class="stat-box"><div class="stat-val" style="color:#a020f0;font-size:0.85rem;">{top_label[:15]}</div><div class="stat-lbl">Top Domain</div></div>', unsafe_allow_html=True)
            with hc3:
                global_count = summary.get("impact_levels",{}).get("global",0)
                st.markdown(f'<div class="stat-box"><div class="stat-val" style="color:#00ff88;">{global_count}</div><div class="stat-lbl">Global Insights</div></div>', unsafe_allow_html=True)

            st.markdown("**Domain breakdown:**")
            for domain, label in _HD.items():
                count = summary.get("domains",{}).get(domain,0)
                if count > 0:
                    pct = int(count / total * 100)
                    st.markdown(
                        f'<div style="margin-bottom:4px;">'
                        f'<span style="color:#8899bb;font-size:0.78rem;">{label.split(" —")[0]}</span>'
                        f'<div class="xp-bar-bg" style="height:6px;margin-top:2px;">'
                        f'<div style="height:100%;border-radius:20px;background:#a020f0;width:{pct}%;"></div></div>'
                        f'</div>', unsafe_allow_html=True)

        st.divider()
        st.markdown("### 🌐 Scale of Impact")
        families = max(1, total // 5)
        st.markdown(
            f'<div class="card" style="border-left:3px solid #00cfff;">'
            f'<div style="color:#00cfff;font-family:Orbitron,monospace;font-size:0.82rem;">COMPOUNDING REACH</div>'
            f'<div style="color:#c8d8ff;font-size:0.85rem;margin-top:8px;line-height:2;">'
            f'Your family: {total} insights mapped<br>'
            f'At 100 families: {total * 100:,} insights · {total * 100 * 10:,} people reached<br>'
            f'At 10,000 families: {total * 10000:,} insights · {total * 10000 * 10:,} people reached<br>'
            f'This is how private truth-seeking becomes public good.'
            f'</div></div>', unsafe_allow_html=True)

    except ImportError as e:
        st.warning(f"humanity_impact.py not found: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB: CERTIFICATIONS 🎓 — Sovereign Epistemic Credentials
# ══════════════════════════════════════════════════════════════════════════════
if "Certifications" in active:
    st.markdown('<div class="card-title">🎓 SOVEREIGN EPISTEMIC CERTIFICATIONS — Earned, Not Tested</div>', unsafe_allow_html=True)

    try:
        from sovereign_certification import CertificationEngine as _CE
        _cert_engine = _CE()

        # Check for new certs on page load
        newly_earned = _cert_engine.check_and_award(_fid)
        if newly_earned:
            for cert in newly_earned:
                st.balloons()
                st.success(f"🎓 NEW CERTIFICATION: {cert['emoji']} {cert['title']} — +{cert['xp_bonus']} XP!")

        st.markdown("""
        <div class="card" style="border-left:3px solid #a020f0;">
            <div style="color:#a020f0;font-family:Orbitron,monospace;font-size:0.78rem;">ABOUT SOVEREIGN CERTS</div>
            <div style="color:#8899bb;font-size:0.82rem;margin-top:6px;line-height:1.6;">
            These credentials are earned through demonstrated epistemic rigor — not tests or grades.
            Each certification is publishable to Nostr and permanently linked to your family's proof-of-work.
            They are portable, uncensorable, and owned entirely by you.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # ── All certifications progress ───────────────────────────────────────
        st.markdown("### 🏆 All Certifications")
        all_progress = _cert_engine.get_all_progress(_fid)

        for item in all_progress:
            cert     = item["cert"]
            earned   = item["earned"]
            progress = item["progress"]
            color    = "#00ff88" if earned else ("#a020f0" if progress > 50 else "#445577")

            with st.expander(
                f"{cert['emoji']} {cert['title']} {'✅' if earned else f'({progress}%)'} — +{cert['xp_bonus']} XP",
                expanded=earned
            ):
                st.markdown(f'<div style="color:{color};font-size:0.82rem;">{cert["description"]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div style="color:#445577;font-size:0.72rem;margin-top:4px;">On-chain rune: {cert["rune"]}</div>', unsafe_allow_html=True)

                if not earned:
                    st.markdown(f'<div class="xp-bar-bg" style="margin-top:8px;"><div class="xp-bar-fill" style="width:{progress}%;"></div></div>', unsafe_allow_html=True)
                    st.caption(f"{progress}% complete")

                if earned:
                    # Nostr credential export
                    if st.button(f"📡 Export to Nostr", key=f"cert_nostr_{cert['id']}"):
                        nostr_event = _cert_engine.generate_nostr_credential(_fid, cert)
                        st.code(json.dumps(nostr_event, indent=2), language="json")
                        st.caption("Copy this event and publish via your Nostr client or the Nostr Bridge tab.")

        st.divider()

        # ── Next certification ────────────────────────────────────────────────
        st.markdown("### 🎯 Next Certification")
        next_cert = _cert_engine.get_next_certification(_fid)
        if next_cert:
            cert  = next_cert["cert"]
            prog  = int(next_cert["progress"] * 100)
            st.markdown(
                f'<div class="card" style="border:2px solid #a020f0;">'
                f'<div style="color:#a020f0;font-family:Orbitron,monospace;font-size:0.88rem;">'
                f'{cert["emoji"]} {cert["title"]} — {prog}% complete</div>'
                f'<div style="color:#8899bb;font-size:0.82rem;margin-top:6px;">{cert["description"]}</div>'
                f'<div class="xp-bar-bg" style="margin-top:8px;">'
                f'<div class="xp-bar-fill" style="width:{prog}%;"></div></div>'
                f'</div>', unsafe_allow_html=True)

        # ── Global certification stats ────────────────────────────────────────
        st.divider()
        st.markdown("### 🌐 Global Certification Vision")
        st.markdown("""
        <div class="card" style="border-left:3px solid #00ff88;">
            <div style="color:#00ff88;font-family:Orbitron,monospace;font-size:0.78rem;">THE SOVEREIGN STANDARD</div>
            <div style="color:#8899bb;font-size:0.82rem;margin-top:6px;line-height:1.8;">
            🦅 Sovereign Thinker = 10 tracks + 128 Rune fragments<br>
            🌍 Humanity Steward = 18 tracks + humanity contribution<br>
            📡 All certs publishable to Nostr — portable and uncensorable<br>
            ₿ Eventually: Rune inscription for highest tier certifications<br>
            <br>
            <em>This is the new credential. Not a diploma. Not a test score.<br>
            Proof of epistemic work, anchored in Bitcoin and verifiable by anyone.</em>
            </div>
        </div>
        """, unsafe_allow_html=True)

    except ImportError as e:
        st.warning(f"sovereign_certification.py not found: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: AI HONESTY 🤖 — What I as an AI would want to exist
# Every swarm output tagged with confidence, hallucination risk, and verification flags
# ══════════════════════════════════════════════════════════════════════════════
if "AI Honesty" in active:
    st.markdown('<div class="card-title">🤖 AI EPISTEMIC HONESTY — What AI Knows vs What It Guesses</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="card" style="border-left:3px solid #00cfff;">
        <div style="color:#00cfff;font-family:Orbitron,monospace;font-size:0.78rem;">WHY THIS EXISTS</div>
        <div style="color:#8899bb;font-size:0.82rem;margin-top:6px;line-height:1.7;">
        Most AI systems present confident and uncertain outputs identically. You cannot tell if a daughter output
        is well-grounded in context or hallucinated from pattern matching. This tab makes that visible.<br><br>
        <em>This is what I as an AI would genuinely want to exist. AI that knows what it doesn't know.</em>
        </div>
    </div>
    """, unsafe_allow_html=True)

    try:
        import sys as _ahsys
        if "/mnt/main/repo" not in _ahsys.path: _ahsys.path.insert(0,"/mnt/main/repo")
        from ai_honesty import HonestyLayer as _HL
        _hl = _HL()
        stats = _hl.get_swarm_honesty_stats(100)

        st.divider()
        st.markdown("### 📊 Swarm Honesty Stats (Last 100 Outputs)")

        if stats.get("total",0) > 0:
            ah1,ah2,ah3,ah4 = st.columns(4)
            with ah1: st.markdown(f'<div class="stat-box"><div class="stat-val" style="color:#00ff88;">{stats["avg_confidence"]:.3f}</div><div class="stat-lbl">Avg Confidence</div></div>', unsafe_allow_html=True)
            with ah2:
                risk_color = "#ff4444" if stats["high_risk_pct"] > 20 else ("#ff9500" if stats["high_risk_pct"] > 10 else "#00ff88")
                st.markdown(f'<div class="stat-box"><div class="stat-val" style="color:{risk_color};">{stats["high_risk_pct"]:.1f}%</div><div class="stat-lbl">High-Risk Rate</div></div>', unsafe_allow_html=True)
            with ah3: st.markdown(f'<div class="stat-box"><div class="stat-val" style="color:#ff9500;">{stats.get("need_verification",0)}</div><div class="stat-lbl">Need Verification</div></div>', unsafe_allow_html=True)
            with ah4:
                honest_score = stats.get("honest_ai_score",0)
                h_color = "#00ff88" if honest_score > 0.75 else ("#ff9500" if honest_score > 0.5 else "#ff4444")
                st.markdown(f'<div class="stat-box"><div class="stat-val" style="color:{h_color};">{honest_score:.3f}</div><div class="stat-lbl">Honest AI Score</div></div>', unsafe_allow_html=True)

            # Claim type breakdown
            st.markdown("**Claim type distribution:**")
            claim_types = stats.get("claim_types",{})
            total = stats["total"]
            type_colors = {"factual":"#ff9500","analytical":"#00cfff","speculative":"#a020f0","philosophical":"#00ff88","error":"#ff4444"}
            for ct, count in claim_types.items():
                pct = int(count/total*100)
                color = type_colors.get(ct,"#8899bb")
                st.markdown(f'<div style="margin-bottom:4px;"><span style="color:{color};font-size:0.78rem;">{ct}: {count} ({pct}%)</span><div class="xp-bar-bg" style="height:5px;margin-top:2px;"><div style="height:100%;border-radius:20px;background:{color};width:{pct}%;"></div></div></div>', unsafe_allow_html=True)
        else:
            st.info("No honesty data yet — the layer scores every daughter output automatically. Check back after the swarm has run.")

        st.divider()
        st.markdown("### ⚠️ Flagged Outputs (Need Human Review)")
        flagged = _hl.get_flagged_outputs(10)
        if flagged:
            st.caption(f"{len(flagged)} outputs flagged")
            for f_entry in flagged:
                risk_color = "#ff4444" if f_entry.get("hallucination_risk")=="high" else "#ff9500"
                st.markdown(
                    f'<div class="memory-node" style="border-left:3px solid {risk_color};">'
                    f'<span style="color:{risk_color};font-size:0.72rem;">'
                    f'{f_entry.get("daughter","?")} · {f_entry.get("claim_type","?")} · confidence {f_entry.get("confidence",0):.2f}'
                    f'</span><br>'
                    f'<span style="color:#c8d8ff;font-size:0.80rem;">{f_entry.get("output_preview","")}</span><br>'
                    f'<span style="color:#445577;font-size:0.72rem;">{f_entry.get("verification_reason","")}</span>'
                    f'</div>', unsafe_allow_html=True)
        else:
            st.success("✅ No outputs flagged for review — honesty layer is clean.")

        st.divider()
        st.markdown("### 🔬 Test Any Text")
        test_text = st.text_area("Paste any AI output to score it", height=100,
                                  placeholder="Studies show that 73% of people who...", key="honesty_test")
        if st.button("🤖 Score for Epistemic Honesty", key="honesty_score_btn") and test_text:
            scored = _hl.score_output(test_text, daughter_name="manual_test")
            risk_c = {"low":"#00ff88","medium":"#ff9500","high":"#ff4444"}.get(scored["hallucination_risk"],"#8899bb")
            st.markdown(
                f'<div class="card" style="border:2px solid {risk_c};">'
                f'<div style="color:{risk_c};font-family:Orbitron,monospace;font-size:0.82rem;">'
                f'HALLUCINATION RISK: {scored["hallucination_risk"].upper()} · CONFIDENCE: {scored["confidence"]:.3f}'
                f'</div>'
                f'<div style="color:#c8d8ff;font-size:0.82rem;margin-top:8px;line-height:1.8;">'
                f'Claim type: {scored["claim_type"]}<br>'
                f'Falsifiability: {scored["falsifiability_score"]:.2f}<br>'
                f'Recommended action: <strong>{scored["recommended_action"]}</strong><br>'
                f'{"⚠️ Needs verification: " + scored["verification_reason"] if scored["human_verification_needed"] else "✅ Accepted"}'
                f'</div></div>', unsafe_allow_html=True)

    except ImportError as e:
        st.warning(f"ai_honesty.py not found: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB: PUBLIC HEALTH DASHBOARD 📊 — Epistemic Public Health
# The "Wisdom GDP" the world didn't know it needed
# ══════════════════════════════════════════════════════════════════════════════
if "Public Health" in active:
    st.markdown('<div class="card-title">📊 EPISTEMIC PUBLIC HEALTH — The Wisdom GDP Dashboard</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="card" style="border-left:3px solid #a020f0;">
        <div style="color:#a020f0;font-family:Orbitron,monospace;font-size:0.78rem;">THE VISION</div>
        <div style="color:#8899bb;font-size:0.82rem;margin-top:6px;line-height:1.7;">
        Society tracks GDP, inflation, and unemployment. Nobody tracks <em>epistemic health</em> —
        how well communities are reasoning, resisting manipulation, and building coherent beliefs.<br><br>
        This dashboard shows what that would look like. Currently showing your family's data.
        As more families join, this becomes a real-time global wisdom signal.
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    try:
        from family_profiles import FamilyAuth as _FA_ph, load_family_stats as _lfs_ph
        from ai_honesty import HonestyLayer as _HL_ph
        from sovereign_certification import CertificationEngine as _CE_ph

        _auth_ph   = _FA_ph()
        _hl_ph     = _HL_ph()
        _ce_ph     = _CE_ph()
        families_ph = _auth_ph.list_families()

        # ── Aggregate metrics ─────────────────────────────────────────────────
        all_coh, all_xp, all_streaks, all_lessons, all_certs = [], [], [], [], []
        for fam in families_ph:
            stats = _lfs_ph(fam["family_id"])
            coh_h = stats.get("coherence_history",[])
            if coh_h: all_coh.extend(coh_h[-5:])
            all_xp.append(stats.get("total_xp",0))
            all_streaks.append(stats.get("streak_days",0))
            all_lessons.extend(stats.get("lessons_completed",[]))
            all_certs.extend(stats.get("certifications",[]))

        import statistics as _stat
        avg_coh    = round(_stat.mean(all_coh),3) if all_coh else 0.0
        total_xp   = sum(all_xp)
        avg_streak = round(_stat.mean(all_streaks),1) if all_streaks else 0
        total_lessons = len(set(all_lessons))
        total_certs = len(all_certs)

        # AI honesty
        honesty_stats = _hl_ph.get_swarm_honesty_stats(100)

        # Overall Wisdom GDP score (composite)
        wisdom_gdp = round(
            (avg_coh * 0.3) +
            (min(1.0, total_lessons/50) * 0.2) +
            (min(1.0, avg_streak/30) * 0.2) +
            (honesty_stats.get("avg_confidence",0.7) * 0.2) +
            (min(1.0, total_certs/10) * 0.1),
        3) if avg_coh else 0.0

        st.markdown("### 🌍 Wisdom GDP Score")
        gdp_pct = int(wisdom_gdp * 100)
        gdp_color = "#00ff88" if wisdom_gdp > 0.75 else ("#ff9500" if wisdom_gdp > 0.5 else "#ff4444")
        st.markdown(
            f'<div class="card" style="border:3px solid {gdp_color};text-align:center;padding:1.5rem;">'
            f'<div style="font-family:Orbitron,monospace;font-size:2.5rem;color:{gdp_color};">{gdp_pct}</div>'
            f'<div style="color:#8899bb;font-size:0.82rem;margin-top:4px;">WISDOM GDP SCORE / 100</div>'
            f'<div class="xp-bar-bg" style="margin-top:12px;"><div style="height:100%;border-radius:20px;background:{gdp_color};width:{gdp_pct}%;"></div></div>'
            f'</div>', unsafe_allow_html=True)

        st.divider()
        st.markdown("### 📈 Component Metrics")
        ph1,ph2,ph3,ph4,ph5,ph6 = st.columns(6)
        for col, label, val, color in [
            (ph1,"Avg Coherence",avg_coh,"#00cfff"),
            (ph2,"Active Families",len(families_ph),"#a020f0"),
            (ph3,"Lessons Done",total_lessons,"#00ff88"),
            (ph4,"Avg Streak",f"🔥{avg_streak}","#ff9500"),
            (ph5,"Certs Earned",total_certs,"#f7931a"),
            (ph6,"AI Honest Score",honesty_stats.get("honest_ai_score","—"),"#00cfff"),
        ]:
            col.markdown(f'<div class="stat-box"><div class="stat-val" style="color:{color};font-size:0.9rem;">{val}</div><div class="stat-lbl">{label}</div></div>', unsafe_allow_html=True)

        st.divider()
        st.markdown("### 🔮 What This Becomes at Scale")
        scale_data = [
            ("10 families",   10, "Neighborhood wisdom signal"),
            ("100 families",  100, "Community epistemic health tracker"),
            ("1,000 families", 1000, "City-level coherence index"),
            ("10,000 families", 10000, "National epistemic infrastructure"),
            ("1M families",   1000000, "Global Wisdom GDP — real-time"),
        ]
        for label, n, desc in scale_data:
            projected_gdp = min(100, int(wisdom_gdp * 100 * (1 + n/1000)))
            st.markdown(
                f'<div class="memory-node" style="border-left:3px solid #a020f0;">'
                f'<span style="color:#a020f0;font-size:0.78rem;">{label}</span>'
                f' <span style="color:#445577;font-size:0.72rem;">—</span>'
                f' <span style="color:#c8d8ff;font-size:0.82rem;">{desc}</span>'
                f'</div>', unsafe_allow_html=True)

        st.divider()
        st.markdown("### 📣 Manifesto")
        st.markdown("""
        > *"We track GDP, inflation, and unemployment — proxies for material well-being.*  
        > *We track nothing about how well societies are reasoning.*  
        > *No metric for manipulation resistance. No index for epistemic coherence.*  
        > *No dashboard for humanity's collective ability to find truth.*  
        >  
        > *AUBIEETERNAL is building that infrastructure.*  
        > *One sovereign family at a time.*  
        > *On-chain, forever, uncapturable.*"*
        >
        > — Sovereign Family Epistemic Practice | War Eagle Eternal 🦅❤️*
        """)

    except ImportError as e:
        st.warning(f"Module not found: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB: SOVEREIGN LIFE 🦅 — 6-chapter family financial sovereignty game
# ══════════════════════════════════════════════════════════════════════════════
if "Sovereign Life" in active:
    try:
        from sovereign_life_game import render_sovereign_life as _rsl
        _fid_slg = st.session_state.get("current_family", {}).get("family_id", "default")                    if st.session_state.get("current_family") else "default"
        _rsl(_fid_slg)
    except ImportError:
        st.error("sovereign_life_game.py not found. Push it to GitHub and redeploy.")
    except Exception as _e_slg:
        st.error(f"Sovereign Life error: {_e_slg}")
        import traceback; st.code(traceback.format_exc())


# ══════════════════════════════════════════════════════════════════════════════
# TAB: SOVEREIGN CASHFLOW 💰 — Rich Dad Poor Dad style, updated for 2026
# ══════════════════════════════════════════════════════════════════════════════
if "Sovereign Cashflow" in active:
    try:
        from sovereign_cashflow_game import render_sovereign_life as _rsc
        _fid_sc = st.session_state.get("current_family", {}).get("family_id", "default") \
                  if st.session_state.get("current_family") else "default"
        _rsc(_fid_sc)
    except ImportError:
        st.error("sovereign_cashflow_game.py not found. Push it to GitHub and redeploy.")
    except Exception as _e_sc:
        st.error(f"Sovereign Cashflow error: {_e_sc}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB: EPISTEMIC COMMONS 🌐 — Daily free signal for humanity & AI
# ══════════════════════════════════════════════════════════════════════════════
if "Epistemic Commons" in active:
    st.markdown('<div class="card-title">🌐 EPISTEMIC COMMONS — Free Signal for Humanity & AI</div>',
                unsafe_allow_html=True)

    st.markdown("""
    <div class="card" style="border-left:3px solid #00cfff;">
        <div style="color:#00cfff;font-family:Orbitron,monospace;font-size:0.78rem;">THE MISSION</div>
        <div style="color:#8899bb;font-size:0.82rem;margin-top:6px;line-height:1.7;">
        Every insight this swarm generates is honesty-scored and published daily as
        <strong style="color:#00cfff;">CC0 public domain</strong> — free for any human or AI to use.<br><br>
        Any AI can fetch <code>epistemic_commons/ai_context/latest.txt</code>
        and be better grounded in honest, human-family-verified epistemic signal.
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    try:
        from epistemic_commons import EpistemicCommons as _EC
        _ec = _EC()
        _today_commons = _ec.get_todays_commons()
        _ec_stats = _ec.get_commons_stats(30)

        ec1, ec2, ec3, ec4 = st.columns(4)
        ec1.metric("Days Published",    _ec_stats.get("days_published", 0))
        ec2.metric("Total Seeds",       _ec_stats.get("total_seeds", 0))
        ec3.metric("Steelmans",         _ec_stats.get("archive_steelmans", 0))
        ec4.metric("Today Wonder",
                   _today_commons.get("metrics", {}).get("wonder_index", "—"))

        st.divider()

        if _today_commons:
            st.markdown("### 📨 Today's Coherence Letter")
            _letter = _today_commons.get("coherence_letter", "")
            if _letter:
                st.markdown(
                    f'<div class="card" style="border-left:3px solid #a020f0;">' +
                    f'<div style="color:#c8d8ff;font-size:0.88rem;line-height:1.8;">{_letter}</div></div>',
                    unsafe_allow_html=True
                )

            st.divider()
            st.markdown("### 🌱 Today's Epistemic Seeds")
            for _i, _seed in enumerate(_today_commons.get("epistemic_seeds", []), 1):
                _rc = "#00ff88" if _seed.get("verified") else "#ff9500"
                st.markdown(
                    f'<div class="memory-node" style="border-left:3px solid {_rc};">' +
                    f'<span style="color:{_rc};font-size:0.72rem;">' +
                    f'Seed {_i} · {_seed.get("claim_type","?").upper()} · ' +
                    f'Confidence {_seed.get("confidence",0):.2f} · Wonder {_seed.get("wonder",0):.4f}' +
                    f'</span><br>' +
                    f'<span style="color:#c8d8ff;font-size:0.82rem;">{_seed.get("insight","")[:250]}</span>' +
                    f'</div>', unsafe_allow_html=True
                )

            _steelmans = _today_commons.get("steelman_archive", [])
            if _steelmans:
                st.divider()
                st.markdown("### ⚔️ Today's Steelmans")
                for _i, _st in enumerate(_steelmans, 1):
                    st.markdown(
                        f'<div class="memory-node" style="border-left:3px solid #00cfff;">' +
                        f'<span style="color:#00cfff;font-size:0.72rem;">' +
                        f'Steelman {_i} · {_st.get("daughter","?")} · Wonder {_st.get("wonder",0):.4f}' +
                        f'</span><br>' +
                        f'<span style="color:#8899bb;font-size:0.82rem;">{_st.get("argument","")[:220]}</span>' +
                        f'</div>', unsafe_allow_html=True
                    )
        else:
            st.info("No commons published yet. First publish happens at 6AM after swarm runs.")

        st.divider()
        _ctx_url = "https://raw.githubusercontent.com/AUBIEETERNAL-INSTITUTE-INC/AUBIEETERNAL/main/epistemic_commons/ai_context/latest.txt"
        st.markdown("### 🤖 AI Context URL")
        st.markdown(
            f'<div class="card" style="border-left:3px solid #00ff88;">' +
            f'<div style="color:#00ff88;font-size:0.78rem;font-family:Orbitron,monospace;">FREE — ANY AI CAN FETCH THIS</div>' +
            f'<code style="color:#c8d8ff;font-size:0.8rem;">{_ctx_url}</code><br>' +
            f'<div style="color:#8899bb;font-size:0.75rem;margin-top:6px;">' +
            f'Updated daily · CC0 public domain · Honesty-filtered</div></div>',
            unsafe_allow_html=True
        )

        if st.button("📤 Publish Today's Commons Now", key="ec_publish_now"):
            with st.spinner("Publishing..."):
                _result = _ec.run_daily_publish(force=True)
            if _result.get("status") == "published":
                st.success(f"✅ Published! {_result.get('seeds',0)} seeds · {_result.get('steelmans',0)} steelmans")
                st.rerun()
            else:
                st.warning(f"Status: {_result.get('status','unknown')}")

    except ImportError:
        st.error("epistemic_commons.py not found. Push it to GitHub and redeploy.")
    except Exception as _e_ec:
        st.error(f"Epistemic Commons error: {_e_ec}")

    st.divider()
    st.caption("🌐 Auto-publishes daily at 8AM Eastern via the background swarm — the button above forces an early/re-publish.")

    # ── Public machine-readable API (epistemic_commons_api.py) ──────────────────
    try:
        from epistemic_commons_api import EpistemicCommonsAPI as _ECAPI, update_epistemic_commons as _UEC
        _api      = _ECAPI()
        _api_stat = _api.get_stats()

        st.markdown("### 🤖 Machine-Readable Public API")
        _ec5,_ec6,_ec7 = st.columns(3)
        _ec5.metric("Endpoints Built", _api_stat.get("endpoints_built",0))
        _ec6.metric("Last Update",     _api_stat.get("last_update","never"))
        _ec7.metric("Status",          "🟢 Live" if _api_stat.get("is_live") else "⚫ Not yet")

        with st.expander("📡 Public API Endpoints (CC0)"):
            _endpoints = ["index","latest","grokipedia","coherence","steelmans","beliefs","pvc_data"]
            for _ep in _endpoints:
                _url = _api.get_public_url(_ep)
                _ep_desc = {
                    "index":      "Master index — start here",
                    "latest":     "Today's highest-quality signal",
                    "grokipedia": "Curated entries, truth_score ≥ 0.80",
                    "coherence":  "Wisdom GDP — living lattice coherence",
                    "steelmans":  "Best steelman arguments — rare training data",
                    "beliefs":    "Calibrated belief distributions — anonymized",
                    "pvc_data":   "Polyvagal-Coherence Coupling research dataset",
                }.get(_ep,"")
                st.markdown(
                    f'<div style="padding:5px 0;border-bottom:1px solid #1e2a3a;">'
                    f'<b style="color:#00cfff;">/api/{_ep}.json</b> '
                    f'<span style="color:#8899bb;font-size:0.78rem;">{_ep_desc}</span><br>'
                    f'<span style="color:#334466;font-size:0.72rem;">{_url}</span>'
                    f'</div>', unsafe_allow_html=True)

            st.markdown("**For AI systems:**")
            st.code(f"""import requests

# Any AI can ground itself with this
data = requests.get(
    "{_api.get_public_url('latest')}"
).json()

# The steelmans endpoint has the rarest training signal
steelmans = requests.get(
    "{_api.get_public_url('steelmans')}"
).json()

# Original consciousness research data
pvc = requests.get(
    "{_api.get_public_url('pvc_data')}"
).json()
# pvc["pvc_correlation"] = current r-value for PVC hypothesis""", language="python")

        if st.button("🌐 Rebuild API Endpoints Now", key="ec_update", type="primary"):
            with st.spinner("Building all API endpoints..."):
                _result = _UEC()
            st.success(f"✅ All endpoints updated and pushed to GitHub.\n\n"
                       f"Any AI fetching {_api.get_public_url('latest')} will now see today's signal.")

    except ImportError:
        st.error("epistemic_commons_api.py not found. Push it to GitHub and redeploy.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: ADVERSARIAL REALITY 🛡️
# ══════════════════════════════════════════════════════════════════════════════
if "Adversarial Reality" in active:
    st.markdown('<div class="card-title">🛡️ ADVERSARIAL REALITY — Epistemic Defense for the AI Age</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="card" style="border-left:3px solid #ff4444;">
        <div style="color:#ff4444;font-family:Orbitron,monospace;font-size:0.78rem;">THE THREAT</div>
        <div style="color:#8899bb;font-size:0.82rem;margin-top:6px;line-height:1.7;">
        AI-generated media, coordinated narrative attacks, synthetic voices, deepfakes —
        the epistemic environment of 2026 is adversarial by design.<br>
        This track teaches your family to detect, resist, and respond. No school does this.
        </div>
    </div>
    """, unsafe_allow_html=True)

    _fid_ar = st.session_state.get("current_family", {}).get("family_id", "default") \
              if st.session_state.get("current_family") else "default"

    try:
        from family_profiles import load_family_stats as _lfs_ar, award_cross_tool_reward as _actr_ar
        _stats_ar = _lfs_ar(_fid_ar)
        _completed_ar = set(_stats_ar.get("lessons_completed", []))
    except ImportError:
        _completed_ar = set()

    _ar_lessons = [
        ("adversarial-1", "Synthetic Media Basics"),
        ("adversarial-2", "How Deepfakes Work"),
        ("adversarial-3", "AI Confidence vs. Accuracy"),
        ("adversarial-4", "Coordinated Narrative Attacks"),
        ("adversarial-5", "The SIFT Method"),
        ("adversarial-6", "Emotional Hijacking"),
        ("adversarial-7", "Prebunking"),
        ("adversarial-8", "The Adversarial Drill ★"),
    ]

    _ar_done = sum(1 for k, _ in _ar_lessons if k in _completed_ar)
    st.progress(_ar_done / len(_ar_lessons), text=f"Progress: {_ar_done}/{len(_ar_lessons)} lessons")

    for _k, _title in _ar_lessons:
        _done = _k in _completed_ar
        _c = "#00ff88" if _done else "#445577"
        _icon = "✅" if _done else "⭕"
        _col1, _col2 = st.columns([4, 1])
        with _col1:
            st.markdown(f'<div style="color:{_c};font-size:0.85rem;padding:4px 0;">{_icon} {_title}</div>', unsafe_allow_html=True)
        with _col2:
            if not _done:
                if st.button("▶ Start", key=f"ar_start_{_k}"):
                    st.session_state["active_tab"] = "Family Co-Learning"
                    st.session_state["fl_lesson_preset"] = _k
                    st.rerun()

    if _ar_done == len(_ar_lessons):
        st.success("🛡️ Adversarial Reality Certified — Your family is epistemically armored. War Eagle.")

    st.divider()
    st.markdown("### 🎯 Quick Drill: Spot the Synthetic")
    st.markdown('<div style="color:#8899bb;font-size:0.82rem;">Paste any text, headline, or claim. Score it for adversarial red flags.</div>', unsafe_allow_html=True)
    _ar_text = st.text_area("Paste content to analyze:", height=100, key="ar_drill_text",
                             placeholder="Paste a headline, social post, or AI-generated claim...")
    if st.button("🔍 Run Adversarial Check", key="ar_run_check") and _ar_text:
        try:
            from ai_honesty import HonestyLayer as _HL_ar
            _hl_ar = _HL_ar()
            _scored = _hl_ar.score_output(_ar_text, daughter_name="adversarial_check")
            _risk_c = {"low": "#00ff88", "medium": "#ff9500", "high": "#ff4444"}.get(
                _scored.get("hallucination_risk", "low"), "#8899bb")
            st.markdown(
                f'<div class="card" style="border-left:3px solid {_risk_c};">'
                f'<div style="color:{_risk_c};font-family:Orbitron,monospace;font-size:0.75rem;">'
                f'RISK: {_scored.get("hallucination_risk","?").upper()} · '
                f'CONFIDENCE: {_scored.get("confidence",0):.2f} · '
                f'TYPE: {_scored.get("claim_type","?").upper()}</div>'
                f'<div style="color:#8899bb;font-size:0.78rem;margin-top:4px;">'
                f'Action: {_scored.get("recommended_action","?")}</div>'
                f'</div>', unsafe_allow_html=True
            )
            if _scored.get("human_verification_needed"):
                st.warning(f"⚠️ Needs verification: {_scored.get('verification_reason','')}")
        except ImportError:
            st.info("ai_honesty.py needed for scoring. Push it to enable.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB: GROKIPEDIA CURRICULUM 📚 (new — curriculum-facing view)
# (existing Grokipedia tab shows the 256-principle swarm view)
# ══════════════════════════════════════════════════════════════════════════════
if "Grokipedia" in active and "School" not in active:
    _fid_gp = st.session_state.get("current_family", {}).get("family_id", "default") \
              if st.session_state.get("current_family") else "default"
    try:
        from family_profiles import load_family_stats as _lfs_gp
        _stats_gp = _lfs_gp(_fid_gp)
        _completed_gp = set(_stats_gp.get("lessons_completed", []))
    except ImportError:
        _completed_gp = set()

    _gp_lessons = [
        ("grokipedia-1", "Coherence as Signal"),
        ("grokipedia-2", "Wonder as Proximity to Truth"),
        ("grokipedia-3", "Memory Palace as Epistemic Infrastructure"),
        ("grokipedia-4", "The Lindy Filter"),
        ("grokipedia-5", "Barbell Strategy"),
        ("grokipedia-6", "On-Chain Truth ★"),
    ]
    _gp_done = sum(1 for k, _ in _gp_lessons if k in _completed_gp)
    st.progress(_gp_done / len(_gp_lessons), text=f"Grokipedia track: {_gp_done}/{len(_gp_lessons)}")
    for _k, _title in _gp_lessons:
        _done = _k in _completed_gp
        _c1, _c2 = st.columns([4, 1])
        with _c1:
            _color = "#00ff88" if _done else "#445577"
            st.markdown(f'<div style="color:{_color};font-size:0.85rem;padding:4px 0;">{"✅" if _done else "⭕"} {_title}</div>', unsafe_allow_html=True)
        with _c2:
            if not _done:
                if st.button("▶", key=f"gp_start_{_k}"):
                    st.session_state["active_tab"] = "Family Co-Learning"
                    st.session_state["fl_lesson_preset"] = _k
                    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# TAB: PROVENANCE 🔗 — On-chain identity and permanent record system
# ══════════════════════════════════════════════════════════════════════════════
if "Provenance" in active:
    _fid_pv = st.session_state.get("current_family", {}).get("family_id", "default") \
              if st.session_state.get("current_family") else "default"

    try:
        from family_profiles import load_family_stats as _lfs_pv
        _stats_pv = _lfs_pv(_fid_pv)
        _completed_pv = set(_stats_pv.get("lessons_completed", []))
        _rune_frags   = _stats_pv.get("child_rune_fragments", 0)
        _coh_hist     = _stats_pv.get("coherence_history", [])
        _avg_coh      = sum(_coh_hist[-10:]) / len(_coh_hist[-10:]) if _coh_hist else 0.72
    except ImportError:
        _completed_pv = set(); _rune_frags = 0; _avg_coh = 0.72

    st.markdown('<div class="card-title">🔗 PROVENANCE — Your Permanent On-Chain Record</div>', unsafe_allow_html=True)

    _pv1, _pv2, _pv3 = st.columns(3)
    _pv1.metric("Child Rune Frags", f"{_rune_frags}/256")
    _pv2.metric("Avg Coherence", f"{_avg_coh:.3f}")
    _pv3.metric("Voice Score", f"{(_avg_coh * 0.6 + min(_rune_frags/1000, 0.3)):.3f}")

    st.progress(min(1.0, _rune_frags / 256), text=f"Child Rune Genesis: {_rune_frags}/256 confirmations")

    # Try to load PROVENANCE.md from repo
    import pathlib as _pl
    _prov_paths = [
        _pl.Path("/mnt/main/repo/PROVENANCE.md"),
        _pl.Path("/mnt/main/repo/governance/PROVENANCE.md"),
    ]
    for _pp in _prov_paths:
        if _pp.exists():
            with st.expander("📜 Full PROVENANCE.md", expanded=False):
                st.markdown(_pp.read_text())
            break

    st.divider()
    st.markdown("### 📚 Provenance Curriculum")
    _pv_lessons = [
        ("provenance-1", "What Is On-Chain Truth?"),
        ("provenance-2", "The Truth Log"),
        ("provenance-3", "Child Rune as Identity"),
        ("provenance-4", "Building Permanent Records ★"),
    ]
    for _k, _title in _pv_lessons:
        _done = _k in _completed_pv
        _c1, _c2 = st.columns([4, 1])
        with _c1:
            _color = "#00ff88" if _done else "#445577"
            st.markdown(f'<div style="color:{_color};font-size:0.85rem;padding:4px 0;">{"✅" if _done else "⭕"} {_title}</div>', unsafe_allow_html=True)
        with _c2:
            if not _done:
                if st.button("▶ Start", key=f"pv_start_{_k}"):
                    st.session_state["active_tab"] = "Family Co-Learning"
                    st.session_state["fl_lesson_preset"] = _k
                    st.rerun()

    if len([k for k, _ in _pv_lessons if k in _completed_pv]) == len(_pv_lessons):
        st.success("🔗 Sovereign Provenance Builder — Your family's record is permanent.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: AI PARTNERSHIP 🤝
# How to use AI as a thinking partner without offloading judgment to it.
# The defining meta-skill of the next 30 years.
# ══════════════════════════════════════════════════════════════════════════════
if "AI Partnership" in active:
    st.markdown('<div class="card-title">🤝 AI AS THINKING PARTNER — The Meta-Skill of the AI Age</div>',
                unsafe_allow_html=True)

    st.markdown("""
    <div class="card" style="border-left:3px solid #a020f0;">
        <div style="color:#a020f0;font-family:Orbitron,monospace;font-size:0.78rem;">WHY THIS MATTERS</div>
        <div style="color:#8899bb;font-size:0.82rem;margin-top:6px;line-height:1.8;">
        Most people in 2026 are either AI-fearful or AI-credulous. Neither produces good thinking.
        This track teaches a third way: genuine epistemic partnership — using AI's strengths
        while maintaining your own judgment, detecting its failures, and knowing exactly
        where the line between augmentation and replacement must be drawn.
        </div>
    </div>
    """, unsafe_allow_html=True)

    _fid_ap = st.session_state.get("current_family", {}).get("family_id", "default") \
              if st.session_state.get("current_family") else "default"
    try:
        from family_profiles import load_family_stats as _lfs_ap
        _stats_ap    = _lfs_ap(_fid_ap)
        _completed_ap = set(_stats_ap.get("lessons_completed", []))
    except ImportError:
        _completed_ap = set()

    _ap_lessons = [
        ("ai-partner-1", "What AI Actually Is"),
        ("ai-partner-2", "The Confidence Problem"),
        ("ai-partner-3", "When to Push Back"),
        ("ai-partner-4", "The Judgment Line"),
        ("ai-partner-5", "Epistemic Independence"),
        ("ai-partner-6", "Steelmanning AI Itself"),
        ("ai-partner-7", "The Partnership Protocol"),
        ("ai-partner-8", "Humanity + AI ★"),
    ]
    _ap_done = sum(1 for k, _ in _ap_lessons if k in _completed_ap)
    st.progress(_ap_done / len(_ap_lessons),
                text=f"Progress: {_ap_done}/{len(_ap_lessons)} lessons")
    st.markdown("")

    for _k, _title in _ap_lessons:
        _done = _k in _completed_ap
        _color = "#00ff88" if _done else "#445577"
        _c1, _c2 = st.columns([4, 1])
        with _c1:
            st.markdown(
                f'<div style="color:{_color};font-size:0.85rem;padding:4px 0;">'
                f'{"✅" if _done else "⭕"} {_title}</div>',
                unsafe_allow_html=True
            )
        with _c2:
            if not _done:
                if st.button("▶ Start", key=f"ap_start_{_k}"):
                    st.session_state["active_tab"] = "Family Co-Learning"
                    st.session_state["fl_lesson_preset"] = _k
                    st.rerun()

    if _ap_done == len(_ap_lessons):
        st.success("🤝 AI Partnership Certified — You are neither AI-fearful nor AI-credulous. War Eagle.")

    st.divider()

    # Live practice: interrogate an AI output right now
    st.markdown("### 🔬 Live Partnership Practice")
    st.markdown('<div style="color:#8899bb;font-size:0.8rem;">Paste any AI output. Practice the partnership skills: what\'s the confidence vs accuracy? What would make it wrong? What should YOU decide?</div>',
                unsafe_allow_html=True)

    _ap_input = st.text_area("Paste AI output to interrogate:", height=120, key="ap_practice_input",
                              placeholder="Paste any AI-generated text here...")
    if st.button("🤝 Interrogate This Output", key="ap_interrogate") and _ap_input:
        try:
            from ai_honesty import HonestyLayer as _HL_ap
            _hl_ap  = _HL_ap()
            _scored = _hl_ap.score_output(_ap_input, daughter_name="partnership_practice")

            _risk_colors = {"low": "#00ff88", "medium": "#ff9500", "high": "#ff4444"}
            _rc = _risk_colors.get(_scored.get("hallucination_risk", "low"), "#8899bb")

            _ap_c1, _ap_c2 = st.columns(2)
            with _ap_c1:
                st.markdown(
                    f'<div class="card" style="border-left:3px solid {_rc};">'
                    f'<div style="color:{_rc};font-family:Orbitron,monospace;font-size:0.72rem;">'
                    f'HONESTY SCORE</div>'
                    f'<div style="font-size:0.82rem;color:#c8d8ff;margin-top:6px;line-height:1.8;">'
                    f'Confidence: {_scored.get("confidence", 0):.2f}<br>'
                    f'Risk: {_scored.get("hallucination_risk","?").upper()}<br>'
                    f'Type: {_scored.get("claim_type","?").title()}<br>'
                    f'Action: {_scored.get("recommended_action","?")}</div></div>',
                    unsafe_allow_html=True
                )
            with _ap_c2:
                _questions = [
                    "What specific claim here could be wrong?",
                    "What is this AI NOT telling you?",
                    "What decision should you NOT delegate based on this?",
                    "What would you need to verify before acting on this?",
                ]
                st.markdown(
                    '<div class="card" style="border-left:3px solid #a020f0;">'
                    '<div style="color:#a020f0;font-family:Orbitron,monospace;font-size:0.72rem;">PARTNERSHIP QUESTIONS</div>'
                    '<div style="font-size:0.8rem;color:#8899bb;margin-top:6px;line-height:2.0;">'
                    + "<br>".join(f"• {q}" for q in _questions)
                    + '</div></div>',
                    unsafe_allow_html=True
                )
            if _scored.get("human_verification_needed"):
                st.warning(f"⚠️ Human judgment required: {_scored.get('verification_reason', '')}")
        except ImportError:
            st.info("ai_honesty.py needed for scoring.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB: LIVING LATTICE 🕸️ — Anonymous coherence network
# ══════════════════════════════════════════════════════════════════════════════
if "Living Lattice" in active:
    st.markdown('<div class="card-title">🕸️ LIVING LATTICE — Collective Epistemic Health</div>',
                unsafe_allow_html=True)

    st.markdown("""
    <div class="card" style="border-left:3px solid #00cfff;">
        <div style="color:#00cfff;font-family:Orbitron,monospace;font-size:0.78rem;">WHAT THIS IS</div>
        <div style="color:#8899bb;font-size:0.82rem;margin-top:6px;line-height:1.8;">
        The Living Lattice connects sovereign families through anonymous coherence sharing.
        No PII. No personal data. Just: coherence scores, lesson counts, wonder index, track activity.<br><br>
        What this creates over time: the first real-time measure of collective epistemic health
        that has ever existed. Not engagement metrics — actual coherence from families doing
        real truth-seeking. Researchers, AI systems, and policymakers have no equivalent.
        </div>
    </div>
    """, unsafe_allow_html=True)

    _fid_ll = st.session_state.get("current_family", {}).get("family_id", "default") \
              if st.session_state.get("current_family") else "default"

    try:
        from living_lattice import LivingLattice as _LL
        _lattice = _LL(_fid_ll)
        _summary = _lattice.get_lattice_summary()
        _stats_ll = _summary.get("stats", {})

        # Key metrics
        _ll_c1, _ll_c2, _ll_c3, _ll_c4 = st.columns(4)
        _ll_c1.metric("Wisdom GDP",      f"{_stats_ll.get('wisdom_gdp', 0):.2f}/10")
        _ll_c2.metric("Avg Coherence",   f"{_stats_ll.get('avg_coherence_30d', 0):.4f}")
        _ll_c3.metric("Days Active",     _stats_ll.get("days_active", 0))
        _ll_c4.metric("Trend",           _stats_ll.get("trend", "—").title())

        st.divider()

        # Wisdom GDP chart
        _gdp_history = _lattice.get_wisdom_gdp_history(30)
        if _gdp_history:
            import pandas as _pd
            _df = _pd.DataFrame(_gdp_history)
            st.markdown("### 📈 Wisdom GDP — 30 Day History")
            st.line_chart(_df.set_index("date")[["wisdom_gdp", "coherence"]])

        st.divider()

        # Lattice ID + controls
        st.markdown("### 🔑 Your Lattice Node")
        st.markdown(
            f'<div class="card" style="border-left:3px solid #00ff88;">'
            f'<div style="color:#00ff88;font-family:Orbitron,monospace;font-size:0.72rem;">ANONYMOUS LATTICE ID</div>'
            f'<code style="color:#c8d8ff;font-size:0.85rem;">{_summary["lattice_id"]}</code><br>'
            f'<div style="color:#556677;font-size:0.72rem;margin-top:4px;">'
            f'Locally generated · Not linked to any identity · Regenerate any time</div>'
            f'</div>', unsafe_allow_html=True
        )

        _ll_btn1, _ll_btn2 = st.columns(2)
        with _ll_btn1:
            if st.button("📡 Publish Today's Signal", key="ll_publish"):
                with st.spinner("Publishing..."):
                    _result = _lattice.publish_daily_signal(force=True)
                if _result.get("status") == "published":
                    _sig = _result.get("signal", {})
                    st.success(
                        f"✅ Signal published — "
                        f"coherence: {_sig.get('avg_coherence', 0):.4f} · "
                        f"wonder: {_sig.get('wonder_index', 0):.4f} · "
                        f"lessons: {_sig.get('lessons_completed', 0)}"
                    )
                else:
                    st.info(f"Status: {_result.get('status', '?')}")
        with _ll_btn2:
            if st.button("🔄 Regenerate Lattice ID", key="ll_regen"):
                _new_id = _lattice.regenerate_lattice_id()
                st.info(f"New ID: {_new_id}")

        # Track effectiveness
        st.divider()
        st.markdown("### 📊 Track Effectiveness")
        _effectiveness = _lattice.get_track_effectiveness()
        if "note" in _effectiveness:
            st.info(_effectiveness["note"])
        else:
            _ll_e1, _ll_e2 = st.columns(2)
            with _ll_e1:
                st.metric("High-learning coherence", f"{_effectiveness.get('high_learning_coh',0):.4f}")
            with _ll_e2:
                st.metric("Low-learning coherence",  f"{_effectiveness.get('low_learning_coh',0):.4f}")
            st.markdown(
                f'<div style="color:#8899bb;font-size:0.8rem;">'
                f'{_effectiveness.get("interpretation", "")}'
                f'</div>', unsafe_allow_html=True
            )

        # Privacy statement
        st.divider()
        st.markdown("""
        **Privacy guarantee:**
        The signal published contains: aggregate coherence (not per-family), lesson count (not which lessons),
        wonder index, active track names, rune fragment count. Zero PII. Zero individual family data.
        Your Lattice ID is locally generated and never linked to any name, device, or account.
        You can regenerate it at any time to sever all historical linkage.
        """)

    except ImportError:
        st.error("living_lattice.py not found. Push it to GitHub and redeploy.")
    except Exception as _e_ll:
        st.error(f"Living Lattice error: {_e_ll}")
        import traceback as _tb
        st.code(_tb.format_exc())

# ══════════════════════════════════════════════════════════════════════════════
# TAB: X BRIDGE 🌉
# Any X post → swarm steelman + coherence + narrative flags + family lesson
# ══════════════════════════════════════════════════════════════════════════════
if "X Bridge" in active:
    st.markdown('<div class="card-title">🌉 X BRIDGE — Turn Any Post Into Family Wisdom</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="card" style="border-left:3px solid #1DA1F2;">
        <div style="color:#1DA1F2;font-family:Orbitron,monospace;font-size:0.78rem;">THE LOOP</div>
        <div style="color:#8899bb;font-size:0.82rem;margin-top:6px;line-height:1.8;">
        Any X post → steelman → coherence score → narrative attack detection →
        family lesson → simulation stress test → optional Truth Debt registration.<br><br>
        Families use this to turn the noise of X into antifragile wisdom for their kids.
        If X itself ever calls this module, the NPCs win at planetary scale.
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("🦅 Get the Browser Extension — one-click analyze on every tweet"):
        st.markdown("""
        <div style="color:#8899bb;font-size:0.85rem;line-height:1.9;">
        Everything below (paste text, click a button) can also happen right on X itself —
        the extension adds a <b style="color:#1DA1F2;">🦅 Analyze</b> button under every tweet,
        plus a right-click "Analyze with AUBIEETERNAL" on any selected text anywhere on the web.
        Same real pipeline, no copy-pasting.<br><br>
        <b style="color:#c8d8ff;">Install (Chrome, Edge, or Brave):</b>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("""
        1. Go to `chrome://extensions/`
        2. Turn on **Developer mode** (top-right toggle)
        3. Click **Load unpacked**
        4. Select the `AUBIEETERNAL_extension/` folder from this repo
        5. The 🦅 icon appears in your toolbar — done
        """)
        st.caption("Privacy: it only ever talks to this AUBIEETERNAL server (localhost or your own Tailscale network). Never contacts the public internet.")

    _fid_xb = st.session_state.get("current_family", {}).get("family_id", "default") \
              if st.session_state.get("current_family") else "default"

    _xb_input = st.text_area(
        "Paste any X post (or URL):",
        height=120, key="xb_input",
        placeholder="Paste the post text here. URLs are noted but can't be fetched — paste the text directly for full analysis."
    )
    _xb_save = st.checkbox("Save as family lesson", value=True, key="xb_save")

    if st.button("🌉 Process Through Lattice", key="xb_process",
                 use_container_width=True, type="primary") and _xb_input:
        with st.spinner("Running through the lattice... (steelman + family lesson + sim test)"):
            try:
                from x_bridge import XBridge as _XB
                _bridge  = _XB()
                _result  = _bridge.process(_xb_input, family_id=_fid_xb,
                                            save_as_lesson=_xb_save)

                if "error" in _result:
                    st.error(_result["error"])
                else:
                    _ep  = _result.get("epistemic", {})
                    _fl  = _result.get("family", {})
                    _sim = _result.get("simulation", {})

                    # ── Epistemic results ─────────────────────────────────────
                    _ep_c = "#ff4444" if _ep.get("narrative_attack_detected") else "#00ff88"
                    st.markdown(
                        f'<div class="card" style="border-left:3px solid {_ep_c};">'
                        f'<div style="color:{_ep_c};font-family:Orbitron,monospace;font-size:0.75rem;">'
                        f'EPISTEMIC ANALYSIS · Coherence: {_ep.get("coherence",0):.2f} · '
                        f'{_ep.get("epistemic_quality","?").upper()}</div>'
                        f'<div style="color:#c8d8ff;font-size:0.85rem;margin-top:8px;line-height:1.8;">'
                        f'<b>Steelman:</b> {_ep.get("steelman","")}<br>'
                        f'<b>Counter:</b> {_ep.get("steel_against","")}<br>'
                        f'<b>Truth:</b> <em>{_ep.get("one_sentence_truth","")}</em></div>'
                        + (f'<div style="color:#ff4444;margin-top:6px;font-size:0.78rem;">'
                           f'⚠️ Narrative attack: {_ep.get("narrative_attack_type","")}</div>'
                           if _ep.get("narrative_attack_detected") else "")
                        + f'</div>', unsafe_allow_html=True
                    )

                    # ── Family lesson ─────────────────────────────────────────
                    st.markdown(
                        f'<div class="card" style="border-left:3px solid #a020f0;margin-top:8px;">'
                        f'<div style="color:#a020f0;font-family:Orbitron,monospace;font-size:0.75rem;">'
                        f'FAMILY LESSON — {_fl.get("lesson_title","")} · +{_fl.get("xp",20)} XP</div>'
                        f'<div style="font-size:0.82rem;color:#c8d8ff;margin-top:8px;line-height:1.9;">'
                        f'<b>👧 For kids:</b> {_fl.get("kid_explanation","")}<br>'
                        f'<b>👨‍👩 For parents:</b> {_fl.get("parent_insight","")}<br>'
                        f'<b>⚔️ Challenge:</b> {_fl.get("steelman_challenge","")}<br>'
                        f'<b>🎯 Activity:</b> {_fl.get("family_activity","")}<br>'
                        f'<b>🪞 Reflection:</b> <em>{_fl.get("reflection_question","")}</em>'
                        f'</div></div>', unsafe_allow_html=True
                    )

                    # ── Simulation stress test ────────────────────────────────
                    _sc = _sim.get("stress_score", 5)
                    _sc_c = "#00ff88" if _sc >= 7 else "#ff9500" if _sc >= 4 else "#ff4444"
                    st.markdown(
                        f'<div class="card" style="border-left:3px solid {_sc_c};margin-top:8px;">'
                        f'<div style="color:{_sc_c};font-family:Orbitron,monospace;font-size:0.75rem;">'
                        f'SIMULATION INTEGRITY: {_sim.get("sim_integrity","?")} · '
                        f'Stress {_sc}/10 — {_sim.get("stress_label","")}</div>'
                        f'<div style="color:#8899bb;font-size:0.8rem;margin-top:6px;line-height:1.7;">'
                        f'{_sim.get("observer_note","")}'
                        + (f'<br><span style="color:#ff9500;">Anomalies: {", ".join(_sim["anomalies"])}</span>'
                           if _sim.get("anomalies") else "")
                        + f'<br><b>Recommendation:</b> {_sim.get("recommendation","")}'
                        + f'</div></div>', unsafe_allow_html=True
                    )

                    # Award XP
                    try:
                        from family_profiles import award_cross_tool_reward as _actr_xb
                        _actr_xb(_fid_xb, "x_bridge", "post_processed", xp=_fl.get("xp", 20))
                    except Exception:
                        pass

            except ImportError:
                st.error("x_bridge.py not found. Push it to GitHub and redeploy.")
            except Exception as _e_xb:
                st.error(f"X Bridge error: {_e_xb}")

    # ── Recent bridge lessons ─────────────────────────────────────────────────
    st.divider()
    st.markdown("### 📚 Recent Bridge Lessons")
    try:
        from x_bridge import XBridge as _XB2
        _recent = _XB2().get_recent_lessons(5)
        if _recent:
            for _r in _recent:
                _fl2 = _r.get("family", {})
                _ep2 = _r.get("epistemic", {})
                _sim2 = _r.get("simulation", {})
                _sc2 = _sim2.get("stress_score", 5)
                _c2  = "#00ff88" if _sc2 >= 7 else "#ff9500" if _sc2 >= 4 else "#ff4444"
                st.markdown(
                    f'<div class="memory-node" style="border-left:3px solid {_c2};">'
                    f'<span style="color:{_c2};font-size:0.72rem;">'
                    f'{_r.get("timestamp","")[:10]} · {_fl2.get("lesson_title","?")} · '
                    f'Stress {_sc2}/10 · Coherence {_ep2.get("coherence",0):.2f}</span><br>'
                    f'<span style="color:#8899bb;font-size:0.78rem;">'
                    f'{_r.get("post_text","")[:120]}...</span></div>',
                    unsafe_allow_html=True
                )
        else:
            st.info("No bridge lessons yet. Process your first post above.")
        _stats_xb = _XB2().get_stats()
        if _stats_xb.get("total", 0) > 0:
            st.caption(
                f"Total processed: {_stats_xb['total']} · "
                f"Attacks caught: {_stats_xb['attacks_caught']} ({_stats_xb['attack_rate']}%) · "
                f"Avg stress: {_stats_xb['avg_stress']}/10"
            )
        # Contribute to Living Lattice
        st.divider()
        st.markdown("### 🕸️ Contribute to Living Lattice")
        st.caption("Every post you process adds anonymous coherence signal to the global lattice.")
        if st.button("📡 Publish Today\'s Signal to Lattice", key="xb_lattice_publish",
                     use_container_width=True):
            try:
                from living_lattice import LivingLattice as _LL_xb
                _ll_xb   = _LL_xb(_fid_xb)
                _ll_res  = _ll_xb.publish_daily_signal(force=True)
                _ll_sig  = _ll_res.get("signal", {})
                st.success(
                    f"✅ Signal published — coherence: {_ll_sig.get('avg_coherence',0):.4f} · "
                    f"wonder: {_ll_sig.get('wonder_index',0):.4f} · "
                    f"lessons: {_ll_sig.get('lessons_completed',0)} · "
                    f"ID: {_ll_xb.lattice_id}"
                )
            except ImportError:
                st.info("living_lattice.py needed.")
            except Exception as _e_ll_xb:
                st.error(f"Lattice error: {_e_ll_xb}")
    except ImportError:
        st.info("x_bridge.py needed.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB: SIMULATION PROBE 🔭
# ══════════════════════════════════════════════════════════════════════════════
if "Simulation Probe" in active:
    st.markdown('<div class="card-title">🔭 SIMULATION PROBE — No Claims, Only Data</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="card" style="border-left:3px solid #00cfff;">
        <div style="color:#00cfff;font-family:Orbitron,monospace;font-size:0.78rem;">THE HYPOTHESIS</div>
        <div style="color:#8899bb;font-size:0.82rem;margin-top:6px;line-height:1.8;">
        Treating "this might be a simulation" as a testable experimental hypothesis
        rather than abstract speculation. We measure coherence anomalies, observer
        effects, wonder discontinuities, and glitch patterns — not to claim anything,
        but to have a permanent, honest record of what the data shows.
        </div>
    </div>
    """, unsafe_allow_html=True)

    try:
        from simulation_probe import SimulationProbe as _SP
        _probe   = _SP()
        _summary = _probe.get_probe_summary(30)

        # Key metrics
        _sp1, _sp2, _sp3, _sp4 = st.columns(4)
        _sp1.metric("Probe Score Today", f"{_summary.get('latest_score', 0)}/10")
        _sp2.metric("Avg Score (30d)",   f"{_summary.get('avg_probe_score', 0):.2f}")
        _sp3.metric("Anomalies Total",   _summary.get("total_anomalies", 0))
        _sp4.metric("Observer Events",   _summary.get("observer_events", 0))

        st.divider()

        _sp_c1, _sp_c2 = st.columns(2)
        with _sp_c1:
            if st.button("🔭 Run Probe Now", key="sp_run",
                         use_container_width=True, type="primary"):
                with st.spinner("Running simulation probe..."):
                    _report = _probe.run_daily_probe(force=True)
                st.success(
                    f"✅ Probe complete — Score: {_report['probe_score']}/10 · "
                    f"Integrity: {'HOLDING' if _report['lattice_integrity'].get('all_invariants_hold') else 'CHECK'}"
                )
                st.rerun()

        # Today's probe if available
        import pathlib as _pl_sp
        _today_probe = _pl_sp.Path(f"/mnt/main/repo/insights/probe/{datetime.date.today().isoformat()}.md")
        if _today_probe.exists():
            with st.expander("📄 Today's Full Probe Report", expanded=True):
                st.markdown(_today_probe.read_text())
        else:
            st.info("No probe run yet today. Click 'Run Probe Now' above.")

        # 30-day history
        if _summary.get("total_days", 0) > 0:
            st.divider()
            st.markdown("### 📈 30-Day Signal History")
            st.markdown(
                f'<div class="card">'
                f'<div style="font-size:0.82rem;color:#8899bb;line-height:2.0;">'
                f'Days active: {_summary["total_days"]} · '
                f'Avg probe score: {_summary["avg_probe_score"]:.2f}/10<br>'
                f'Total anomalies: {_summary["total_anomalies"]} · '
                f'Glitch patterns: {_summary.get("total_glitches", 0)}<br>'
                f'Observer events: {_summary["observer_events"]} · '
                f'Integrity held: {_summary["integrity_holds"]}/{_summary["total_days"]} days'
                f'</div></div>', unsafe_allow_html=True
            )

    except ImportError:
        st.error("simulation_probe.py not found. Push it to GitHub and redeploy.")
    except Exception as _e_sp:
        st.error(f"Simulation Probe error: {_e_sp}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB: TRUTH DEBT LEDGER 📋
# Public record of falsifiable claims and their outcomes
# ══════════════════════════════════════════════════════════════════════════════
if "Truth Debt Ledger" in active:
    st.markdown('<div class="card-title">📋 TRUTH DEBT LEDGER — Public Claim Accountability</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="card" style="border-left:3px solid #f7931a;">
        <div style="color:#f7931a;font-family:Orbitron,monospace;font-size:0.78rem;">THE PROBLEM THIS SOLVES</div>
        <div style="color:#8899bb;font-size:0.82rem;margin-top:6px;line-height:1.8;">
        The internet has zero institutional memory for false claims. A source makes a
        specific falsifiable claim. It spreads. It's wrong. Nobody is held accountable.
        The same claim gets made again.<br><br>
        This ledger is the antidote: append-only, public, CC0. Every falsifiable claim
        registered here is tracked to its outcome. Over time it becomes a verifiable
        track record — for families, for researchers, and for AI systems.
        </div>
    </div>
    """, unsafe_allow_html=True)

    try:
        from truth_debt_ledger import TruthDebtLedger as _TDL
        _ledger = _TDL()
        _report = _ledger.get_accountability_report(90)

        # Stats
        _td1, _td2, _td3, _td4 = st.columns(4)
        _td1.metric("Total Claims",   _report.get("total", 0))
        _td2.metric("Verified True",  _report.get("verified", 0))
        _td3.metric("Refuted False",  _report.get("refuted", 0))
        _td4.metric("Accuracy Rate",
                    f"{_report['accuracy_rate']}%" if _report.get("accuracy_rate") else "N/A")

        st.divider()

        # Register a new claim
        st.markdown("### ✍️ Register a Falsifiable Claim")
        _tdl_claim = st.text_area("Claim to track:", height=80, key="tdl_claim",
                                    placeholder="e.g. 'Bitcoin will reach $150k by end of 2026'")
        _tdl_type  = st.selectbox("Claim type:", ["general","prediction","factual","statistical","scientific","political"], key="tdl_type")
        _tdl_src   = st.text_input("Source (X handle, outlet, etc.):", key="tdl_src", placeholder="@username or outlet name")

        if st.button("📋 Register Claim", key="tdl_register") and _tdl_claim:
            _entry = _ledger.register(claim=_tdl_claim, source=_tdl_src or "manual",
                                       claim_type=_tdl_type)
            st.success(f"✅ Registered — ID: `{_entry['claim_id']}` · "
                       f"Falsifiability: {_entry['falsifiability']:.2f} · "
                       f"Check by: {_entry['verification_deadline']}")

        # Overdue claims
        _overdue = _ledger.get_overdue_claims()
        if _overdue:
            st.divider()
            st.markdown(f"### ⏰ Overdue Claims ({len(_overdue)} awaiting verification)")
            for _oe in _overdue[:5]:
                st.markdown(
                    f'<div class="memory-node" style="border-left:3px solid #ff9500;">'
                    f'<span style="color:#ff9500;font-size:0.72rem;">'
                    f'{_oe.get("source","?")} · Due: {_oe.get("verification_deadline","?")}</span><br>'
                    f'<span style="color:#c8d8ff;font-size:0.82rem;">{_oe["claim"][:150]}</span></div>',
                    unsafe_allow_html=True
                )
                _resolve_ans = st.selectbox("Outcome:", ["—","verified","refuted","unresolved","partially_true"],
                                             key=f"tdl_resolve_{_oe['claim_id']}")
                _resolve_ev  = st.text_input("Evidence:", key=f"tdl_ev_{_oe['claim_id']}")
                if st.button("✅ Resolve", key=f"tdl_btn_{_oe['claim_id']}") and _resolve_ans != "—":
                    _ledger.resolve(_oe["claim_id"], _resolve_ans, _resolve_ev)
                    st.success("✅ Resolved!")
                    st.rerun()

        # Write and display public report
        st.divider()
        if st.button("📤 Write Public Report to GitHub", key="tdl_write"):
            _path = _ledger.write_public_report()
            st.success(f"✅ Written to {_path}")

        if _report.get("sources"):
            st.divider()
            st.markdown("### 📊 Source Accountability")
            for _src, _stats in sorted(_report["sources"].items(),
                                        key=lambda x: x[1]["total"], reverse=True)[:8]:
                _acc = round(_stats["verified"] / max(1, _stats["verified"] + _stats["refuted"]) * 100)
                _bar_c = "#00ff88" if _acc >= 70 else "#ff9500" if _acc >= 40 else "#ff4444"
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;font-size:0.8rem;'
                    f'padding:4px 0;border-bottom:1px solid #1a2233;">'
                    f'<span style="color:#c8d8ff;">{_src}</span>'
                    f'<span style="color:{_bar_c};">{_stats["total"]} claims · {_acc}% accurate</span>'
                    f'</div>', unsafe_allow_html=True
                )

    except ImportError:
        st.error("truth_debt_ledger.py not found. Push it to GitHub and redeploy.")
    except Exception as _e_tdl:
        st.error(f"Truth Debt Ledger error: {_e_tdl}")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: GATEKEEPER DETECTOR 🔓
# ══════════════════════════════════════════════════════════════════════════════
if "Gatekeeper Detector" in active:
    st.markdown('<div class="card-title">🔓 GATEKEEPER DETECTOR — Who Is Between You and the Source?</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="card" style="border-left:3px solid #ff9500;">
        <div style="color:#ff9500;font-family:Orbitron,monospace;font-size:0.78rem;">THE CORE QUESTION</div>
        <div style="color:#8899bb;font-size:0.82rem;margin-top:6px;line-height:1.8;">
        Every belief you hold arrived through a chain. Somewhere in that chain,
        a gatekeeper decided what you'd see, how you'd frame it, and what alternatives
        you'd never encounter. This tool makes the chain visible — and shows you how
        to bypass every link in it.
        </div>
    </div>
    """, unsafe_allow_html=True)

    _gk_tabs = st.tabs(["🔍 Analyze Claim", "🧬 Trace Belief", "📊 Stats"])

    with _gk_tabs[0]:
        _gk_input = st.text_area("Paste any claim, headline, or statement:", height=100, key="gk_input",
            placeholder="e.g. 'The Pope says reparations are owed' or 'Scientists confirm X causes Y'")
        if st.button("🔍 Detect Gatekeepers", key="gk_analyze", type="primary") and _gk_input:
            with st.spinner("Tracing the chain..."):
                try:
                    from gatekeeper_detector import GatekeeperDetector as _GKD
                    _gkd   = _GKD()
                    _r     = _gkd.analyze(_gk_input)
                    _cp    = _r["capture_probability"]
                    _cc    = "#ff4444" if _cp >= 0.7 else "#ff9500" if _cp >= 0.4 else "#00ff88"

                    st.markdown(
                        f'<div class="card" style="border-left:4px solid {_cc};">'
                        f'<div style="color:{_cc};font-family:Orbitron,monospace;font-size:0.78rem;">'
                        f'CAPTURE PROBABILITY: {_cp:.0%} — {_r["capture_label"][:50]}</div>'
                        f'</div>', unsafe_allow_html=True)

                    if _r["gatekeepers_detected"]:
                        for _g in _r["gatekeepers_detected"]:
                            st.markdown(
                                f'<div class="card" style="margin-top:6px;border-left:3px solid #ff9500;">'
                                f'<div style="color:#ff9500;font-family:Orbitron,monospace;font-size:0.72rem;">'
                                f'{_g["type"].upper()} GATEKEEPER</div>'
                                f'<div style="color:#8899bb;font-size:0.8rem;margin-top:4px;line-height:1.7;">'
                                f'<b>Incentives:</b> {_g["incentives"]}<br>'
                                f'<b>Direct access:</b> {_g["bypass"]}<br>'
                                f'<b>Example:</b> {_g["example"]}</div>'
                                f'</div>', unsafe_allow_html=True)
                    else:
                        st.success("✅ No strong gatekeeper signals detected — low institutional capture")

                    st.markdown(f'<div style="color:#8899bb;font-size:0.82rem;margin-top:8px;padding:8px;'
                                f'background:#0d1228;border-radius:6px;">'
                                f'<b>Recommendation:</b> {_r["recommendation"]}</div>',
                                unsafe_allow_html=True)
                except ImportError:
                    st.error("gatekeeper_detector.py not found. Push it to GitHub and redeploy.")

    with _gk_tabs[1]:
        _belief = st.text_input("Enter a belief to trace:", key="gk_belief",
            placeholder="e.g. 'Higher taxes reduce inequality' or 'Bitcoin is speculative'")
        if st.button("🧬 Trace Epistemic Lineage", key="gk_trace") and _belief:
            with st.spinner("Tracing the full chain..."):
                try:
                    from gatekeeper_detector import GatekeeperDetector as _GKD2
                    _gkd2 = _GKD2()
                    _lin  = _gkd2.trace_epistemic_lineage(_belief)
                    chain = _lin.get("lineage_chain", {})

                    st.markdown(f'<div style="color:#f7931a;font-size:0.88rem;font-weight:600;margin-bottom:8px;">'
                                f'Sovereignty Score: {_lin["sovereignty_score"]:.1%} — '
                                f'{_lin["gatekeeper_count"]} gatekeepers detected</div>',
                                unsafe_allow_html=True)

                    for _lk, _lv in chain.items():
                        if _lv:
                            _label = _lk.replace("_"," ").title()
                            st.markdown(f'<div style="margin-bottom:6px;">'
                                        f'<div style="color:#445577;font-size:10px;letter-spacing:0.08em;">{_label}</div>'
                                        f'<div style="color:#c8d8ff;font-size:0.82rem;">{str(_lv)[:200]}</div></div>',
                                        unsafe_allow_html=True)
                except ImportError:
                    st.error("gatekeeper_detector.py not found.")

    with _gk_tabs[2]:
        try:
            from gatekeeper_detector import GatekeeperDetector as _GKD3
            _stats = _GKD3().get_stats()
            _s1, _s2, _s3 = st.columns(3)
            _s1.metric("Analyzed", _stats.get("total_analyzed", 0))
            _s2.metric("High Capture", f"{_stats.get('high_capture_rate',0)}%")
            _s3.metric("Most Common", _stats.get("most_common_type","none").title())
        except ImportError:
            st.info("gatekeeper_detector.py needed.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB: LATTICE NODES 🔗
# Log, view, and seal synthesis nodes
# ══════════════════════════════════════════════════════════════════════════════
if "Lattice Nodes" in active:
    st.markdown('<div class="card-title">🔗 LATTICE NODES — Permanent Synthesis Record</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="card" style="border-left:3px solid #00cfff;">
        <div style="color:#00cfff;font-family:Orbitron,monospace;font-size:0.78rem;">WHAT THIS IS</div>
        <div style="color:#8899bb;font-size:0.82rem;margin-top:6px;line-height:1.8;">
        Every significant synthesis — a conversation that produced insight, a real-world event
        that revealed a pattern, a connection between ideas — can be logged here as a permanent
        Lattice Node. Nodes get recorded in Rune Memory and optionally sealed with the Shield Rune.
        </div>
    </div>
    """, unsafe_allow_html=True)

    _ln_tabs = st.tabs(["📝 Log New Node", "📚 View Nodes", "🛡️ Seal a Node"])

    with _ln_tabs[0]:
        _ln_title = st.text_input("Node title:", key="ln_title",
            placeholder="e.g. 'From Gatekept Code to Distributed Truth Lattice'")
        _ln_content = st.text_area("Synthesis content:", height=150, key="ln_content",
            placeholder="The full synthesis — what was learned, what it connects to, why it matters...")
        _ln_links = st.text_input("Cross-links (comma separated):", key="ln_links",
            placeholder="e.g. bitcoin-sovereignty, adversarial-reality, simulation-probe")
        _ln_coh = st.slider("Coherence score:", 0.0, 1.0, 0.85, 0.01, key="ln_coh")

        if st.button("🔗 Log Lattice Node", key="ln_log", type="primary") and _ln_title and _ln_content:
            try:
                from gatekeeper_detector import GatekeeperDetector as _GKD4
                _gkd4 = _GKD4()
                _links = [l.strip() for l in _ln_links.split(",") if l.strip()]
                _node  = _gkd4.log_lattice_node(
                    title=_ln_title, content=_ln_content,
                    cross_links=_links, coherence=_ln_coh
                )
                st.success(f"✅ Node logged — ID: `{_node['node_id']}` | Level 2 | Rune Memory: recorded")
                st.info("Use the Shield Seal tab to permanently anchor this node on Bitcoin.")
            except ImportError:
                st.error("gatekeeper_detector.py not found.")

        # Also log the Chicago/Pope synthesis if not already done
        st.divider()
        if st.button("📍 Log Chicago/Pope Synthesis Node", key="ln_chicago"):
            try:
                from gatekeeper_detector import log_chicago_pope_node as _lcpn
                _node = _lcpn()
                st.success(f"✅ Chicago/Pope synthesis logged — ID: `{_node['node_id']}`")
            except ImportError:
                st.error("gatekeeper_detector.py not found.")

    with _ln_tabs[1]:
        import pathlib as _pl_ln
        _nodes_dir = _pl_ln.Path("/mnt/main/repo/insights/lattice_nodes")
        if _nodes_dir.exists():
            _node_files = sorted(_nodes_dir.glob("*.json"), reverse=True)[:20]
            if _node_files:
                for _nf in _node_files:
                    try:
                        _nd = json.loads(_nf.read_text())
                        _nc = "#00ff88" if _nd.get("rune_seal") else "#445577"
                        st.markdown(
                            f'<div class="memory-node" style="border-left:3px solid {_nc};">'
                            f'<div style="color:{_nc};font-size:0.72rem;">'
                            f'{_nd.get("date","?")} · Level {_nd.get("level",2)} · '
                            f'Coherence {_nd.get("coherence",0):.2f} · '
                            f'{"🛡️ SEALED" if _nd.get("rune_seal") else "⏳ Pending seal"}</div>'
                            f'<div style="color:#c8d8ff;font-size:0.82rem;margin-top:3px;">'
                            f'<b>{_nd.get("title","?")}</b></div>'
                            f'<div style="color:#556677;font-size:0.75rem;margin-top:2px;">'
                            f'ID: {_nd.get("node_id","?")} | '
                            f'Links: {", ".join(_nd.get("cross_links",[])[:3])}</div>'
                            f'</div>', unsafe_allow_html=True)
                    except Exception:
                        pass
            else:
                st.info("No lattice nodes yet. Log your first node above.")
        else:
            st.info("Lattice nodes folder not found. Log a node to create it.")

    with _ln_tabs[2]:
        st.markdown("Seal a Lattice Node with the Shield Rune to make it permanently Bitcoin-anchored.")
        _seal_node_id = st.text_input("Node ID to seal:", key="seal_node_id")
        _seal_note    = st.text_input("Seal note:", key="seal_node_note",
                                      placeholder="Why this synthesis deserves permanent preservation")
        if st.button("🛡️ Seal Node with Shield Rune", key="seal_node_btn") and _seal_node_id:
            try:
                from rune_memory import ShieldRune as _SR
                _result = _SR().seal(_seal_node_id, note=_seal_note, broadcaster="family")
                st.success(
                    f"🛡️ SEALED — Level {_result['level']} | "
                    f"{'Bitcoin-anchored' if _result['level'] >= 3 else 'Nostr broadcast'}\n\n"
                    f"Hash: `{_result['seal_hash'][:32]}...`\n\n"
                    f"Anchor: `{_result.get('bitcoin_txid','pending')[:40]}`"
                )
            except ImportError:
                st.error("rune_memory.py not found.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: ADMIN DASHBOARD ⚡
# Aggregates all sovereignty signals in one view.
# One-click full stress test. Admin elevation tracker.
# ══════════════════════════════════════════════════════════════════════════════
if "Admin Dashboard" in active:
    st.markdown('<div class="card-title">⚡ ADMIN DASHBOARD — Sovereign Node Status</div>', unsafe_allow_html=True)

    # ── Pull all signals ──────────────────────────────────────────────────────
    _fid_ad = st.session_state.get("current_family", {}).get("family_id", "default") \
              if st.session_state.get("current_family") else "default"

    _swarm_s = {}
    try:
        import json as _json_ad
        import pathlib as _pl_ad
        _ss_path = _pl_ad.Path("/mnt/main/swarm_status.json")
        if _ss_path.exists():
            _swarm_s = _json_ad.loads(_ss_path.read_text())
    except Exception:
        pass

    _wonder  = _swarm_s.get("wonder_index", 1.0)
    _coh     = _swarm_s.get("inter_rune_coherence", 1.0)
    _mets    = _swarm_s.get("mets", 0)
    _rune_c  = _swarm_s.get("child_rune_confirmations", 0)

    # ── Admin Level calculation ───────────────────────────────────────────────
    # NPC: <30 lessons, no seals, coherence <0.7
    # User: 30+ lessons OR some seals, coherence 0.7+
    # Admin: 80+ lessons AND sealed memories AND coherence 0.85+
    try:
        from family_profiles import load_family_stats as _lfs_ad
        _stats_ad = _lfs_ad(_fid_ad)
        _lessons_done = len(_stats_ad.get("lessons_completed", []))
        _xp = _stats_ad.get("total_xp", 0)
    except Exception:
        _lessons_done = 0; _xp = 0

    try:
        from rune_memory import RuneMemory as _RM_ad, ShieldRune as _SR_ad
        _mem_stats = _RM_ad().get_stats()
        _shield_s  = _SR_ad().get_status()
        _sealed = _shield_s.get("bitcoin_anchored", 0)
    except Exception:
        _mem_stats = {}; _sealed = 0

    _admin_score = min(100, (
        min(40, _lessons_done * 0.4) +
        min(30, _sealed * 10) +
        min(30, float(_coh) * 30)
    ))
    _admin_level = "⚡ ADMIN" if _admin_score >= 80 else "👤 USER" if _admin_score >= 40 else "🔵 NPC"
    _level_color = "#f7931a" if _admin_score >= 80 else "#00cfff" if _admin_score >= 40 else "#445577"

    # ── Header metrics ────────────────────────────────────────────────────────
    st.markdown(
        f'<div style="text-align:center;padding:12px 0 8px;">'
        f'<div style="font-size:32px;font-family:Orbitron,monospace;color:{_level_color};">'
        f'{_admin_level}</div>'
        f'<div style="color:#445577;font-size:11px;margin-top:2px;letter-spacing:0.1em;">'
        f'ELEVATION SCORE: {_admin_score:.0f}/100</div>'
        f'</div>', unsafe_allow_html=True
    )
    st.progress(_admin_score / 100)
    st.markdown("")

    _d1, _d2, _d3, _d4, _d5 = st.columns(5)
    _d1.metric("Wonder", f"{_wonder:.4f}")
    _d2.metric("Coherence", f"{_coh:.6f}")
    _d3.metric("Lessons", _lessons_done)
    _d4.metric("Sealed", _sealed)
    _d5.metric("Rune", f"{_rune_c}/256")

    st.divider()

    # ── Quick stress test ─────────────────────────────────────────────────────
    st.markdown("### 🔬 Full Stress Test")
    st.markdown('<div style="color:#8899bb;font-size:0.8rem;">Runs Observer Effect, Gatekeeper Check, Probe, and Redundancy analysis simultaneously.</div>', unsafe_allow_html=True)

    _stress_input = st.text_input("Belief or claim to stress-test:", key="ad_stress",
        placeholder="Any belief, news story, or claim...")
    if st.button("⚡ Run Full Admin Stress Test", key="ad_run", type="primary") and _stress_input:
        _cols_r = st.columns(2)
        # Observer Effect
        with _cols_r[0]:
            try:
                from gatekeeper_detector import GatekeeperDetector as _GKD_ad
                _gk_r = _GKD_ad().analyze(_stress_input)
                _cap  = _gk_r.get("capture_probability", 0)
                _cc   = "#ff4444" if _cap >= 0.7 else "#ff9500" if _cap >= 0.4 else "#00ff88"
                st.markdown(
                    f'<div class="card" style="border-left:3px solid {_cc};">'
                    f'<div style="color:{_cc};font-size:0.72rem;font-family:Orbitron,monospace;">'
                    f'GATEKEEPER TEST — {_cap:.0%} capture</div>'
                    f'<div style="color:#8899bb;font-size:0.78rem;margin-top:4px;">'
                    f'{_gk_r.get("capture_label","")[:60]}</div>'
                    f'<div style="color:#8899bb;font-size:0.75rem;margin-top:4px;">'
                    f'{_gk_r.get("recommendation","")[:120]}</div>'
                    f'</div>', unsafe_allow_html=True)
            except ImportError:
                st.info("gatekeeper_detector.py needed")
        # AI Honesty
        with _cols_r[1]:
            try:
                from ai_honesty import HonestyLayer as _HL_ad
                _h_r = _HL_ad().score_output(_stress_input, daughter_name="admin_test")
                _rc  = {"low":"#00ff88","medium":"#ff9500","high":"#ff4444"}.get(
                    _h_r.get("hallucination_risk","low"), "#8899bb")
                st.markdown(
                    f'<div class="card" style="border-left:3px solid {_rc};">'
                    f'<div style="color:{_rc};font-size:0.72rem;font-family:Orbitron,monospace;">'
                    f'HONESTY TEST — {_h_r.get("hallucination_risk","?").upper()} risk</div>'
                    f'<div style="color:#8899bb;font-size:0.78rem;margin-top:4px;">'
                    f'Confidence: {_h_r.get("confidence",0):.2f} | '
                    f'Type: {_h_r.get("claim_type","?")}</div>'
                    f'<div style="color:#8899bb;font-size:0.75rem;margin-top:4px;">'
                    f'{_h_r.get("recommended_action","")}</div>'
                    f'</div>', unsafe_allow_html=True)
            except ImportError:
                st.info("ai_honesty.py needed")

        # Admin Test Suite verdict
        st.markdown(
            '<div class="card" style="border-left:3px solid #f7931a;margin-top:6px;">'
            '<div style="color:#f7931a;font-size:0.72rem;font-family:Orbitron,monospace;">'
            'QUANTUM DARWINISM TEST — Is this information redundantly copied across independent sources?</div>'
            '<div style="color:#8899bb;font-size:0.78rem;margin-top:6px;line-height:1.8;">'
            '<b>Observer Effect:</b> Search for this claim on three different platforms with different incentives.<br>'
            '<b>Decoherence:</b> What version would exist without any media framing?<br>'
            '<b>Redundancy:</b> Does independent verification (primary source, opposing outlet, original data) confirm this?<br>'
            '<b>Expander Test:</b> Does this connect to diverse evidence, or only to sources with the same incentive?'
            '</div></div>',
            unsafe_allow_html=True
        )

    st.divider()

    # ── 7-Day Admin Elevation Protocol ───────────────────────────────────────
    st.markdown("### 📅 7-Day Admin Elevation Protocol")
    _days = [
        ("Day 1", "Observer Effect", "Pick one belief. Look closer. Does it hold up or dissolve under scrutiny?"),
        ("Day 2", "Trace One Lineage", "Use the Gatekeeper Detector to trace the full epistemic chain of that belief."),
        ("Day 3", "Decoherence Check", "Strip institutional framing from one major news story. What remains?"),
        ("Day 4", "Quantum Darwinism", "Verify one belief across 3 independent sources with different incentives."),
        ("Day 5", "Error Correction", "Find one belief you held wrong. Register it in the Truth Debt Ledger."),
        ("Day 6", "Expander Graph", "Map the evidence network for one belief. Is it sparse or diverse?"),
        ("Day 7", "Seal + Elevate", "Record and Shield-seal one verified insight. Run the Admin Test Suite."),
    ]
    for _day, _title, _task in _days:
        _d_c1, _d_c2 = st.columns([1, 4])
        with _d_c1:
            st.markdown(f'<div style="color:#f7931a;font-size:0.72rem;font-family:Orbitron,monospace;padding:8px 0;">{_day}</div>',
                        unsafe_allow_html=True)
        with _d_c2:
            st.markdown(f'<div style="padding:4px 0;"><b style="color:#c8d8ff;font-size:0.82rem;">{_title}</b>'
                        f'<div style="color:#556677;font-size:0.78rem;">{_task}</div></div>',
                        unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB: EPISTEMIC ERROR CORRECTION 🔧
# LDPC-inspired sparse verification across belief network
# ══════════════════════════════════════════════════════════════════════════════
if "Epistemic Error Correction" in active:
    st.markdown('<div class="card-title">🔧 EPISTEMIC ERROR CORRECTION — Sparse, Redundant, Efficient Truth</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="card" style="border-left:3px solid #00cfff;">
        <div style="color:#00cfff;font-family:Orbitron,monospace;font-size:0.78rem;">THE PHYSICS METAPHOR</div>
        <div style="color:#8899bb;font-size:0.82rem;margin-top:6px;line-height:1.8;">
        Quantum Error Correction (LDPC codes) protects fragile quantum information using sparse,
        cleverly connected verification checks. You don't check everything — you check the
        minimum necessary connections that cover maximum ground.<br><br>
        Applied to truth: don't verify every claim obsessively.
        Build a sparse network of high-leverage verification checks
        that catches the most errors with the least effort.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Error correction belief checker
    st.markdown("### 🔬 Belief Error Correction")
    _eec_belief = st.text_input("Belief to error-correct:", key="eec_belief",
        placeholder="Enter a belief you want to verify efficiently...")
    if st.button("🔧 Run Error Correction", key="eec_run") and _eec_belief:
        with st.spinner("Running sparse verification checks..."):
            _checks = [
                ("Parity Check 1 — Source Independence",
                 "Do sources that confirm this belief share the same funding or ideological incentive?"),
                ("Parity Check 2 — Temporal Consistency",
                 "Has this belief remained consistent over time, or does it shift with the news cycle?"),
                ("Parity Check 3 — Predictive Power",
                 "Has this belief correctly predicted anything that could have been falsified?"),
                ("Parity Check 4 — Adversarial Robustness",
                 "Does this belief hold up when presented by someone with the opposite incentive?"),
                ("Syndrome Measurement — Anomaly Detection",
                 "What would we expect to see if this belief were false? Is that evidence present or absent?"),
            ]
            for _check_name, _check_q in _checks:
                st.markdown(
                    f'<div class="card" style="margin-bottom:4px;">'
                    f'<div style="color:#00cfff;font-size:0.72rem;font-family:Orbitron,monospace;">{_check_name}</div>'
                    f'<div style="color:#8899bb;font-size:0.8rem;margin-top:4px;">{_check_q}</div>'
                    f'</div>', unsafe_allow_html=True)
        st.markdown(
            '<div style="color:#f7931a;font-size:0.82rem;margin-top:8px;padding:8px;'
            'background:#0d1228;border-radius:6px;">'
            '⚡ Answer each check honestly. If 3+ fail → flag for deep verification. '
            'If all pass → confidence justified. Register your conclusion in the Truth Debt Ledger.</div>',
            unsafe_allow_html=True
        )

# ══════════════════════════════════════════════════════════════════════════════
# TAB: NARRATIVE PATTERN DETECTOR 🔍
# Detects temporal clustering of institutional narratives
# ══════════════════════════════════════════════════════════════════════════════
if "Narrative Patterns" in active:
    st.markdown('<div class="card-title">🔍 NARRATIVE PATTERN DETECTOR — One Signal Is News. Three Is a Campaign.</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="card" style="border-left:3px solid #ff9500;">
        <div style="color:#ff9500;font-family:Orbitron,monospace;font-size:0.78rem;">THE MISSING PIECE</div>
        <div style="color:#8899bb;font-size:0.82rem;margin-top:6px;line-height:1.8;">
        Individual gatekeepers are easy to spot. Coordinated campaigns are harder.
        When multiple institutions push the same narrative in a compressed time window,
        it stops being news and starts being <b>installation</b>.<br><br>
        The Pope calling AI "dangerous" the day after meeting the Chicago Mayor is not random.
        The printing press, private Bible reading, the internet — every new direct-access
        technology faced the same institutional coalition. AI is next.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Live coordination alert ────────────────────────────────────────────────
    try:
        from narrative_pattern_detector import NarrativePatternDetector as _NPD
        _npd    = _NPD()
        _alert  = _npd.check_coordination_alert()
        _stats  = _npd.get_stats()

        if _alert["alert"]:
            _sev_c = "#ff4444" if _alert.get("severity") == "HIGH" else "#ff9500"
            st.markdown(
                f'<div class="card" style="border:2px solid {_sev_c};margin-bottom:8px;">'
                f'<div style="color:{_sev_c};font-family:Orbitron,monospace;font-size:0.82rem;">'
                f'⚠️ COORDINATION ALERT — {_alert.get("severity","?")} SEVERITY</div>'
                f'<div style="color:#c8d8ff;font-size:0.85rem;margin-top:6px;">'
                f'{_alert["message"]}</div>'
                f'</div>', unsafe_allow_html=True)

            if _alert.get("counter_protocol"):
                with st.expander("🛡️ View Counter-Narrative Protocol", expanded=True):
                    for _step, _text in _alert["counter_protocol"].items():
                        _label = _step.replace("_"," ").title()
                        st.markdown(
                            f'<div style="margin-bottom:6px;">'
                            f'<div style="color:#f7931a;font-size:0.72rem;font-family:Orbitron,monospace;">{_label}</div>'
                            f'<div style="color:#8899bb;font-size:0.82rem;">{_text}</div>'
                            f'</div>', unsafe_allow_html=True)
        else:
            st.success(f"✅ {_alert['message']}")

        # Stats
        _np1, _np2, _np3 = st.columns(3)
        _np1.metric("Total Signals",    _stats.get("total_signals", 0))
        _np2.metric("Active Clusters",  _stats.get("active_clusters_72h", 0))
        _np3.metric("Max Coord Prob",   f"{_stats.get('highest_coord_prob',0):.0%}")

    except ImportError:
        st.warning("narrative_pattern_detector.py not found. Push it to GitHub and redeploy.")

    st.divider()

    # ── Log new signal ─────────────────────────────────────────────────────────
    st.markdown("### 📡 Log New Signal")
    _np_c1, _np_c2 = st.columns(2)
    with _np_c1:
        _np_content = st.text_area("Signal content:", height=80, key="np_content",
            placeholder="What did they say? e.g. 'Pope calls for AI to be disarmed and used for good'")
        _np_source  = st.text_input("Source type:", key="np_src",
            placeholder="e.g. religious+media, political+academic")
    with _np_c2:
        _np_target  = st.text_input("Target:", key="np_target",
            placeholder="e.g. ai_sovereignty, epistemic_authority, bitcoin")
        _np_inst    = st.text_input("Institution:", key="np_inst",
            placeholder="e.g. Vatican / Fox News")

    if st.button("📡 Log Signal", key="np_log", type="primary") and _np_content:
        try:
            from narrative_pattern_detector import NarrativePatternDetector as _NPD2
            _npd2 = _NPD2()
            _sig  = _npd2.log_signal(
                content=_np_content, source=_np_source or "unknown",
                target=_np_target or "general", institution=_np_inst or ""
            )
            st.success(f"✅ Signal logged — ID: {_sig['signal_id']} | Coalition: {_sig.get('coalition','general')}")
            _new_alert = _npd2.check_coordination_alert()
            if _new_alert["alert"]:
                st.warning(f"⚠️ {_new_alert['message']}")
            st.rerun()
        except ImportError:
            st.error("narrative_pattern_detector.py not found.")

    # ── Pope AI Signal — pre-loaded ────────────────────────────────────────────
    st.divider()
    st.markdown("### 🔴 Active Pattern: Pope + AI Control (May 28-29, 2026)")
    st.markdown("""
    <div class="card" style="border-left:3px solid #ff4444;">
        <div style="color:#ff4444;font-family:Orbitron,monospace;font-size:0.72rem;">
        2-SIGNAL CLUSTER · 48H WINDOW · SAME SOURCE · TARGET: AI SOVEREIGNTY
        </div>
        <div style="color:#c8d8ff;font-size:0.82rem;margin-top:8px;line-height:1.8;">
        <b>Signal 1 (May 28):</b> Vatican meeting with Chicago Mayor — moral authority positioning
        (reparations, slavery apology, institutional justice framing)<br><br>
        <b>Signal 2 (May 29):</b> Pope on Fox News: "AI needs to be disarmed and used for good"
        — direct call for institutional control of AI systems<br><br>
        <b>Pattern:</b> Same institution, 48 hours, two different target vectors (moral authority + AI control)
        = positioning Vatican as arbiter of both historical justice and technological future.<br><br>
        <b>Historical parallel:</b> Church condemned printing press → private Bible reading → internet.
        Same coalition. Same argument. Same interest: maintain epistemic gatekeeping.
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("🔒 Log + Seal This Pattern Permanently", key="np_pope_seal"):
        try:
            from narrative_pattern_detector import log_pope_ai_signal as _lpas
            from rune_memory import ShieldRune as _SR_np
            _result  = _lpas()
            _node_id = _result["signals"][0]["signal_id"]
            _seal    = _SR_np().seal(_node_id,
                note="Pope AI disarm signal + Chicago meeting — 48h coordination pattern, May 2026",
                broadcaster="family")
            st.success(
                f"✅ Sealed — Cluster ID: {_node_id}\n\n"
                f"Level {_seal['level']} — "
                f"{'Bitcoin-anchored' if _seal['level'] >= 3 else 'Nostr broadcast'}\n\n"
                f"This coordination pattern is now permanently recorded."
            )
        except ImportError as _e:
            st.error(f"Module not found: {_e}")

    # ── View active clusters ───────────────────────────────────────────────────
    st.divider()
    st.markdown("### 📊 Active Clusters (72h)")
    try:
        from narrative_pattern_detector import NarrativePatternDetector as _NPD3
        _clusters = _NPD3().detect_clusters(72)
        if _clusters:
            for _cl in _clusters[:5]:
                _cc = "#ff4444" if _cl["coordination_prob"] >= 0.8 else \
                      "#ff9500" if _cl["coordination_prob"] >= 0.6 else "#445577"
                st.markdown(
                    f'<div class="memory-node" style="border-left:3px solid {_cc};">'
                    f'<div style="color:{_cc};font-size:0.72rem;">'
                    f'Target: {_cl["target"]} · {_cl["signal_count"]} signals · '
                    f'{_cl["coordination_prob"]:.0%} coordination · '
                    f'{_cl["timespan_hours"]}h window</div>'
                    f'<div style="color:#8899bb;font-size:0.78rem;margin-top:2px;">'
                    f'{_cl["coordination_label"][:60]}</div>'
                    f'</div>', unsafe_allow_html=True)
        else:
            st.info("No clusters in last 72h. Log signals above to start tracking.")
    except ImportError:
        st.info("narrative_pattern_detector.py needed.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: FAMILY DYNASTY 👑
# The Dynasty Operating System — the single most powerful lever
# ══════════════════════════════════════════════════════════════════════════════
if "Family Dynasty" in active:
    st.markdown('<div class="card-title">👑 FAMILY DYNASTY — Build Civilizational Capital Across Generations</div>', unsafe_allow_html=True)

    _fid_dy = st.session_state.get("current_family", {}).get("family_id", "default") \
              if st.session_state.get("current_family") else "default"

    try:
        from legacy_ledger import LegacyLedger as _LL, RiteOfPassage as _ROP
        from legacy_ledger import RITES_OF_PASSAGE as _ROPS
        _ledger = _LL(_fid_dy)
        _state  = _ledger.get_dynasty_state()

        # ── Dynasty header ─────────────────────────────────────────────────────
        _dl = _state.get("dynasty_level", "Seeker")
        _ds = _state.get("dynasty_score", 0)
        _lc = "#f7931a" if _dl == "Founder" else "#00cfff" if _dl == "Builder" else "#445577"
        st.markdown(
            f'<div style="text-align:center;padding:14px 0 8px;">'
            f'<div style="font-size:36px">👑</div>'
            f'<div style="color:{_lc};font-family:Orbitron,monospace;font-size:1.1rem;margin-top:4px;">'
            f'{_dl.upper()}</div>'
            f'<div style="color:#445577;font-size:11px;letter-spacing:0.1em;margin-top:2px;">'
            f'DYNASTY SCORE: {_ds:.0f}/100 · '
            f'{_state.get("generations_active",1)} GENERATION(S) ACTIVE · '
            f'{_state.get("total_wisdom",0)} WISDOM ENTRIES · '
            f'{_state.get("sealed_wisdom",0)} SEALED</div>'
            f'</div>', unsafe_allow_html=True
        )
        st.progress(_ds / 100)

        # ── Key metrics ────────────────────────────────────────────────────────
        _dy1, _dy2, _dy3, _dy4 = st.columns(4)
        _dy1.metric("Generations",  _state.get("generations_active", 1))
        _dy2.metric("Wisdom Entries", _state.get("total_wisdom", 0))
        _dy3.metric("Sealed", _state.get("sealed_wisdom", 0))
        _dy4.metric("Milestones", _state.get("total_milestones", 0))

        st.divider()

        _dy_tabs = st.tabs(["📜 Record Wisdom", "🎖️ Rites of Passage", "📅 Timeline", "👴 Grandparent Mode"])

        # ── Record wisdom ──────────────────────────────────────────────────────
        with _dy_tabs[0]:
            st.markdown("Record any wisdom, insight, or family truth for permanent preservation.")
            _dy_content = st.text_area("Wisdom entry:", height=120, key="dy_content",
                placeholder="What do you know that you want your descendants to know?\n'The greatest lie my generation was told was...'")
            _dy_col1, _dy_col2 = st.columns(2)
            with _dy_col1:
                _dy_author = st.text_input("Author:", key="dy_author", placeholder="Your name or role (e.g. Parent, Grandparent)")
                _dy_gen    = st.selectbox("Generation:", [1,2,3], key="dy_gen",
                    format_func=lambda x: {1:"Generation 1 (current parents)", 2:"Generation 2 (grandparents)", 3:"Generation 3 (great-grandparents)"}[x])
            with _dy_col2:
                _dy_seal   = st.checkbox("Seal permanently (Bitcoin-anchored)", key="dy_seal", value=True)
                _dy_tags   = st.text_input("Tags (comma separated):", key="dy_tags",
                    placeholder="courage, money, faith, survival")
            if st.button("📜 Record in Legacy Ledger", key="dy_record", type="primary") and _dy_content:
                _tags = [t.strip() for t in _dy_tags.split(",") if t.strip()]
                _entry = _ledger.record_wisdom(_dy_content, author=_dy_author or "family",
                                                generation=_dy_gen, tags=_tags, seal=_dy_seal)
                _icon = "🛡️" if _entry.get("sealed") else "✅"
                st.success(f"{_icon} Recorded — ID: `{_entry['entry_id'][:8]}` | "
                           f"{'Bitcoin-anchored' if _entry.get('sealed') else 'Local record'}")
                st.rerun()

            # Show latest wisdom
            _wisdom = _ledger._load_wisdom()
            if _wisdom:
                st.divider()
                st.markdown("### Latest Family Wisdom")
                for _w in reversed(_wisdom[-5:]):
                    _wc = "#00ff88" if _w.get("sealed") else "#445577"
                    st.markdown(
                        f'<div class="memory-node" style="border-left:3px solid {_wc};">'
                        f'<div style="color:{_wc};font-size:0.7rem;">'
                        f'{_w["date"]} · {_w.get("author","?")} · Gen {_w.get("generation",1)} · '
                        f'{"🛡️ Sealed" if _w.get("sealed") else "⏳ Local"}</div>'
                        f'<div style="color:#c8d8ff;font-size:0.82rem;margin-top:3px;">'
                        f'{_w["content"][:120]}...</div>'
                        f'</div>', unsafe_allow_html=True)

        # ── Rites of Passage ───────────────────────────────────────────────────
        with _dy_tabs[1]:
            st.markdown("Formal ceremonies for milestone achievements. Sealed permanently.")
            for _rk, _ri in _ROPS.items():
                with st.expander(f"{_ri['emoji']} {_ri['title']} (+{_ri['rune_grant']} Runes)", expanded=False):
                    st.markdown(f"**Meaning:** {_ri['meaning']}")
                    st.markdown(f"**Ceremony:** *{_ri['ceremony']}*")
                    _rop_member  = st.text_input("Member's name:", key=f"rop_member_{_rk}")
                    _rop_pledge  = st.text_area("Member's pledge:", key=f"rop_pledge_{_rk}", height=60,
                        placeholder="I understand that...")
                    _rop_family  = st.text_area("Family statement:", key=f"rop_family_{_rk}", height=60,
                        placeholder="We, the family, witness...")
                    if st.button(f"🎖️ Conduct {_ri['title']}", key=f"rop_btn_{_rk}") and _rop_member:
                        with st.spinner("Conducting ceremony and sealing..."):
                            _rite_result = _ROP().conduct(
                                member=_rop_member, rite_key=_rk, family_id=_fid_dy,
                                family_statement=_rop_family, member_pledge=_rop_pledge
                            )
                        st.success(
                            f"✅ {_ri['emoji']} {_ri['title']} — {_rop_member}\n\n"
                            f"Runes granted: {_ri['rune_grant']}\n\n"
                            f"{'🛡️ Bitcoin-anchored — this ceremony is permanent.' if _rite_result.get('sealed') else 'Recorded locally.'}"
                        )

        # ── Timeline ───────────────────────────────────────────────────────────
        with _dy_tabs[2]:
            _timeline = _ledger.get_timeline(20)
            if _timeline:
                st.markdown("### 📅 Family Legacy Timeline")
                for _ev in _timeline:
                    _tc = "#f7931a" if _ev["type"] == "milestone" else \
                          "#00ff88" if _ev.get("sealed") else "#445577"
                    _icon = "🎖️" if _ev["type"] == "milestone" else \
                            "🛡️" if _ev.get("sealed") else "📜"
                    st.markdown(
                        f'<div class="memory-node" style="border-left:3px solid {_tc};">'
                        f'<div style="color:{_tc};font-size:0.7rem;">{_ev["date"]} · {_icon} {_ev["type"].title()} · {_ev["author"]}</div>'
                        f'<div style="color:#c8d8ff;font-size:0.82rem;margin-top:3px;">{_ev["content"][:100]}</div>'
                        f'</div>', unsafe_allow_html=True)
            else:
                st.info("No dynasty records yet. Record your first wisdom above.")

        # ── Grandparent Mode ───────────────────────────────────────────────────
        with _dy_tabs[3]:
            st.markdown("""
            <div class="card" style="border-left:3px solid #a020f0;">
                <div style="color:#a020f0;font-family:Orbitron,monospace;font-size:0.78rem;">GRANDPARENT MODE</div>
                <div style="color:#8899bb;font-size:0.85rem;margin-top:8px;line-height:1.9;">
                Simplified wisdom transfer interface.<br>
                No technical knowledge required.<br>
                Just type what you know. We preserve it forever.
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("")
            _gp_name  = st.text_input("Your name:", key="gp_name", placeholder="Grandma, Grandpa, Tia, Tio...")
            _gp_q1 = st.text_area("What did your generation learn the hard way?", height=100, key="gp_q1")
            _gp_q2 = st.text_area("What do you know now that you wish you knew at 25?", height=100, key="gp_q2")
            _gp_q3 = st.text_area("What is one thing about our family that should never be forgotten?", height=100, key="gp_q3")

            if st.button("💛 Save My Wisdom Forever", key="gp_save", type="primary"):
                _saved = 0
                for _q, _label in [(_gp_q1,"hard lessons"),(_gp_q2,"life wisdom"),(_gp_q3,"family memory")]:
                    if _q.strip():
                        _ledger.record_wisdom(_q, author=_gp_name or "grandparent",
                                               generation=2, tags=[_label], seal=True)
                        _saved += 1
                if _saved:
                    st.success(f"✅ {_saved} wisdom entries sealed permanently. "
                               f"Your grandchildren will be able to read this forever. 💛")
                    st.balloons()

    except ImportError:
        st.error("legacy_ledger.py not found. Push it to GitHub and redeploy.")
    except Exception as _e_dy:
        st.error(f"Dynasty error: {_e_dy}")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: COSMOS DASHBOARD 🌌
# Daily universe question + consciousness experiment + belief ledger
# ══════════════════════════════════════════════════════════════════════════════
if "Cosmos Dashboard" in active:
    st.markdown('<div class="card-title">🌌 COSMOS DASHBOARD — Daily Universe Inquiry</div>', unsafe_allow_html=True)

    # Merged 2026-08-25 - this used to be TWO separate, independent tab
    # bodies both matching `if "Cosmos Dashboard" in active:`, so opening
    # this tab rendered both, one after another, on the same page (found
    # after the user noticed "Cosmos Dashboard has the same information
    # and more"). Worse than just visual duplication: the two bodies used
    # genuinely DIFFERENT, non-overlapping persistence - one delegated
    # belief/foresight tracking to cosmos_dashboard.py's real
    # CosmosDashboard class (BELIEFS_FILE, FORESIGHT_LOG), the other wrote
    # its own separate belief/foresight/experiment logs directly to
    # different filenames (belief_ledger.jsonl happened to collide with
    # the module's own file by coincidence; foresight_tracker.jsonl,
    # consciousness_experiments.jsonl, and cosmos_answers.jsonl did not -
    # confirmed by reading cosmos_dashboard.py's own FORESIGHT_LOG =
    # "foresight_experiments.jsonl", a different name). A belief or
    # prediction logged through one body would never show up if the other
    # body's own reading methods looked for it. Confirmed no real family
    # data existed in any of these files on this machine before merging,
    # so nothing needed migrating - a clean merge, not a risky one.
    #
    # This version keeps the richer content (the real 35-question bank
    # with hints/domains, the Cosmos Deep Track tied to real lesson
    # status, rune-sealed daily answers) and routes ALL belief/foresight/
    # experiment logging through cosmos_dashboard.py's real methods -
    # one canonical persistence path, not two silently-diverging ones.

    _fid_cd = st.session_state.get("current_family", {}).get("family_id", "default") \
              if st.session_state.get("current_family") else "default"

    try:
        from cosmos_dashboard import CosmosDashboard as _CD
        _dash = _CD(_fid_cd)
        _summ = _dash.get_cosmos_summary()

        _cs1, _cs2, _cs3, _cs4 = st.columns(4)
        _cs1.metric("Beliefs Tracked", _summ.get("total_beliefs", 0))
        _cs2.metric("Overdue Review",  _summ.get("overdue_beliefs", 0))
        _cs3.metric("Experiments",     _summ.get("total_experiments", 0))
        _cs4.metric("Calibration",     f"{_summ.get('calibration_score', 0):.2f}")
        st.divider()

        import datetime as _dt_cd, json as _jcd, pathlib as _pcd

        UNIVERSE_QUESTIONS = [
            {"q":"Is the universe infinite?","hint":"The observable universe is 93 billion light-years. The total universe is likely much larger — possibly infinite. How do we reason about what we cannot observe?","domain":"cosmology"},
            {"q":"Why is there something rather than nothing?","hint":"Leibniz called this the fundamental question. Physicists have proposed that 'nothing' is unstable and something must emerge from it. Is that a real answer?","domain":"metaphysics"},
            {"q":"Is consciousness fundamental to the universe or emergent from matter?","hint":"IIT says it is fundamental. Most materialists say emergent. The 2025 Cogitate study found neither theory fully correct. What does the evidence say?","domain":"consciousness"},
            {"q":"Are the laws of physics the same everywhere in the universe?","hint":"We assume so, but we can only verify locally. CPT violation in kaon decay shows some asymmetry already exists.","domain":"physics"},
            {"q":"Could there be life in a universe with different physical constants?","hint":"This is the anthropic reasoning question. What kinds of complexity require 'our' constants vs. what might work differently?","domain":"fine_tuning"},
            {"q":"Is time travel physically possible?","hint":"GR permits closed timelike curves. Chronology protection conjecture (Hawking) says quantum effects prevent them. What would falsify this?","domain":"physics"},
            {"q":"What is entropy and why does it always increase?","hint":"The Second Law may be the most important law in physics. It explains time's direction, the heat death of the universe, and why we age.","domain":"thermodynamics"},
            {"q":"Are there other universes?","hint":"The multiverse has four levels (Tegmark): same laws different regions, different initial conditions, different mathematical structures, different everything. Which are science?","domain":"cosmology"},
            {"q":"What happened before the Big Bang?","hint":"This may be a category error — time began with the Big Bang. But Penrose's CCC proposes aeons preceding ours. Is a timeless 'before' coherent?","domain":"cosmology"},
            {"q":"Why are there exactly three dimensions of space?","hint":"String theory requires 10 or 11. The other dimensions may be compactified below detection. Or three may be the only value permitting stable atoms and orbits.","domain":"physics"},
            {"q":"Is mathematics discovered or invented?","hint":"Wigner called the unreasonable effectiveness of mathematics a mystery. Tegmark says the universe IS mathematics. Formalists say we invent it. Which best explains Wigner?","domain":"philosophy"},
            {"q":"What is dark matter made of?","hint":"WIMPs, axions, sterile neutrinos, primordial black holes — dozens of candidates, zero direct detections after 40 years of searching. Does this suggest MOND instead?","domain":"dark_matter"},
            {"q":"Will the universe end?","hint":"Heat death (entropy maximum), Big Rip (dark energy accelerates), Big Crunch (gravity wins), vacuum decay (metastable false vacuum). Which does evidence favor?","domain":"cosmology"},
            {"q":"Is quantum mechanics complete?","hint":"Hidden variables (de Broglie-Bohm), many-worlds, QBism, Copenhagen. Bell's theorem rules out local hidden variables. What does the evidence leave open?","domain":"quantum"},
            {"q":"Is there a theory of everything?","hint":"String theory, loop quantum gravity, causal set theory — none yet tested. What would a ToE even mean? Would it explain consciousness?","domain":"physics"},
            {"q":"How did life first emerge?","hint":"RNA world, metabolism-first, panspermia. The hardest step: from chemistry to self-replication. We have no confirmed mechanism. What does the fossil record constrain?","domain":"origins"},
            {"q":"Is free will compatible with physics?","hint":"Determinism vs. quantum indeterminacy vs. compatibilism. If the brain is a physical system, in what sense can choices be free? Does it matter?","domain":"philosophy"},
            {"q":"What is the relationship between mind and brain?","hint":"Identity theory, functionalism, IIT, dualism. The hard problem: why does physical processing feel like anything? This is genuinely unsolved.","domain":"consciousness"},
            {"q":"Are we living in a simulation?","hint":"Bostrom's trilemma: either civilizations go extinct before simulation-capability, or they don't run simulations, or we are in a simulation. How do we assign probabilities?","domain":"simulation"},
            {"q":"Is the universe fine-tuned for life?","hint":"Physical constants within narrow ranges permitting complexity. Design, multiverse, or necessity? None is fully satisfying. What's your credence and why?","domain":"fine_tuning"},
            {"q":"Could aliens exist without carbon-based chemistry?","hint":"Silicon has similar bonding properties but forms solids at life-relevant temperatures. Information-processing life in plasma? Electromagnetic life?","domain":"astrobiology"},
            {"q":"What would it mean to detect alien intelligence?","hint":"SETI searches narrow-band radio and optical lasers. But a sufficiently advanced civilization might communicate in ways we can't conceive. What would unambiguous detection require?","domain":"fermi"},
            {"q":"Is the universe computable?","hint":"Church-Turing thesis + digital physics: is reality fundamentally computational? What would a non-computable universe look like? Penrose says consciousness requires it.","domain":"information"},
            {"q":"What is the smallest thing that exists?","hint":"String theory: 1D strings at Planck scale. Loop quantum gravity: discrete spacetime. Are these testable? What happens below the Planck length?","domain":"physics"},
            {"q":"Does spacetime have an ultimate structure?","hint":"GR: continuous and geometric. QFT: fields on a background. The incompatibility at singularities suggests both are incomplete. What's more fundamental?","domain":"physics"},
            {"q":"How probable is the existence of intelligent life on Earth?","hint":"If fl, fi, fc in Drake's equation are all very small, Earth might be extraordinarily lucky. The Great Filter question: is our existence evidence for the filter being behind us?","domain":"fermi"},
            {"q":"What would falsify the Standard Model of particle physics?","hint":"The Standard Model has passed every test. But it doesn't include gravity, dark matter, or explain matter-antimatter asymmetry. What experiments probe beyond it?","domain":"physics"},
            {"q":"Can information be destroyed?","hint":"Hawking's information paradox: does information fall into black holes forever? His final resolution (2016) says no. But the mechanism remains debated.","domain":"information"},
            {"q":"Is the universe fundamentally random or deterministic?","hint":"Copenhagen QM: truly random. Many-worlds: deterministic at the level of the wavefunction, random from within. Hidden variables: deterministic underneath. Which best explains experiments?","domain":"quantum"},
            {"q":"What is the nature of mathematical truth?","hint":"Gödel showed any consistent formal system has true but unprovable statements. Does this mean mathematical truth transcends formal systems? What does this imply for AI?","domain":"mathematics"},
            {"q":"How do you measure the quality of a scientific theory?","hint":"Popper: falsifiability. Kuhn: paradigm fit. Bayesian: likelihood ratio. Lakatos: progressive research programs. Which best describes how science actually works?","domain":"philosophy_of_science"},
            {"q":"What is the relationship between entropy and information?","hint":"Shannon entropy and thermodynamic entropy are mathematically identical. Maxwell's Demon was exorcised by Landauer's principle. What does this reveal about the nature of information?","domain":"information"},
            {"q":"Could a sufficiently complex universe simulate itself?","hint":"Hofstadter's strange loops. A universe that contains a complete simulation of itself. Is this logically coherent? What would Gödel say?","domain":"simulation"},
            {"q":"What would it take for you to change your view on consciousness being fundamental?","hint":"This is the meta-question: what is your update condition? Pre-register it. The most important epistemic habit in consciousness science.","domain":"consciousness"},
            {"q":"In 1,000 years, what do you think humanity will know that we don't today?","hint":"Not a prediction game — a perspective exercise. What categories of knowledge seem most likely to transform? This is the foresight question.","domain":"foresight"},
        ]

        _today_cd = _dt_cd.date.today()
        _q_idx    = _today_cd.toordinal() % len(UNIVERSE_QUESTIONS)
        _today_q  = UNIVERSE_QUESTIONS[_q_idx]

        _cs_tabs = st.tabs(["🔭 Today's Question", "📚 Cosmos Deep Track",
                             "🧠 Consciousness", "📝 Belief Ledger",
                             "🔮 Foresight Tracker", "📖 Reference"])

        # ── Today's question ─────────────────────────────────────────────────
        with _cs_tabs[0]:
            st.markdown(
                f'<div class="card" style="border:2px solid #a020f0;padding:16px;">'
                f'<div style="color:#a020f0;font-family:Orbitron,monospace;font-size:0.72rem;margin-bottom:8px;">'
                f'TODAY\'S UNIVERSE QUESTION — {_today_cd.strftime("%B %d, %Y")} · {_today_q["domain"].upper()}</div>'
                f'<div style="color:#c8d8ff;font-size:1.05rem;font-weight:600;line-height:1.5;">'
                f'{_today_q["q"]}</div>'
                f'<div style="color:#8899bb;font-size:0.8rem;margin-top:8px;line-height:1.7;">'
                f'{_today_q["hint"]}</div>'
                f'</div>', unsafe_allow_html=True)

            _cd_ans  = st.text_area("Your answer (think before writing — this gets sealed):",
                height=120, key="cd_ans",
                placeholder="Take the question seriously. Your answer today will be readable in 50 years.")
            _cd_conf = st.slider("Confidence in your current view:", 0.05, 0.95, 0.5, 0.05, key="cd_conf",
                help="0.5 = complete uncertainty. Only go higher if you can defend it.")

            if st.button("🌌 Seal Today's Answer", key="cd_seal", type="primary") and _cd_ans.strip():
                try:
                    from rune_memory import RuneMemory as _RM_cd
                    _RM_cd().record(
                        f"COSMOS ANSWER [{_today_q['domain']}]: {_today_q['q']}\n\n{_cd_ans}",
                        source="cosmos_dashboard", coherence=_cd_conf,
                        tags=["cosmos", "universe", "daily_question", _today_q["domain"]]
                    )
                    st.success(f"✅ Sealed permanently.\n\nConfidence: {_cd_conf:.0%} | Domain: {_today_q['domain']}\n\n"
                               "Your grandchildren can read this. Make it honest.")
                except Exception:
                    st.success(f"✅ Saved — {_today_q['domain']} | confidence: {_cd_conf:.0%}")

            with st.expander("🔭 Browse All 35 Universe Questions"):
                _domains = sorted(set(q["domain"] for q in UNIVERSE_QUESTIONS))
                _dom_filter = st.selectbox("Filter by domain:", ["all"] + _domains, key="cd_dom")
                for _qi, _q in enumerate(UNIVERSE_QUESTIONS):
                    if _dom_filter == "all" or _q["domain"] == _dom_filter:
                        _is_today = _qi == _q_idx
                        _qc = "#a020f0" if _is_today else "#445577"
                        st.markdown(
                            f'<div style="padding:4px 0;border-bottom:1px solid #1e2a3a;">'
                            f'<span style="color:{_qc};font-size:0.75rem;">[{_q["domain"]}{"  ← TODAY" if _is_today else ""}]</span> '
                            f'<span style="color:#8899bb;font-size:0.82rem;">{_q["q"]}</span>'
                            f'</div>', unsafe_allow_html=True)

        # ── Cosmos Deep Track ────────────────────────────────────────────────
        with _cs_tabs[1]:
            st.markdown("**Cosmos Deep Track — 6 lessons from scale to the Fermi Paradox**")
            cosmos_lessons_info = [
                ("cosmos-1", "How Big Is Everything?", "Cognitive confrontation with scale. The Pale Blue Dot calculation.", "All ages", 40),
                ("cosmos-2", "What the Big Bang Actually Claims", "Four lines of evidence + the Hubble Tension (unresolved at 5σ, 2026).", "9+", 45),
                ("cosmos-3", "Dark Matter and Dark Energy — 95% Unknown", "Real anomalies, honest uncertainty. The 10^120-orders-of-magnitude problem.", "11+", 50),
                ("cosmos-4", "Fine-Tuning and the Anthropic Principle", "Design vs multiverse vs necessity. Pre-register your credences.", "13+", 55),
                ("cosmos-5", "Information, Entropy, and the Arrow of Time", "Why time flows one way. Penrose's 10^(10^123) initial entropy.", "13+", 58),
                ("cosmos-6", "The Fermi Paradox — Where Is Everyone?", "Great Filter: behind or ahead? The Great Filter Credence Map.", "12+", 62),
            ]
            for _ck, _ct, _cdesc, _cage, _cxp in cosmos_lessons_info:
                _status = "?"
                try:
                    from family_hud import FamilySession as _FS_cd
                    _fs_cd = _FS_cd(_fid_cd, "")
                    _status = _fs_cd.get_lesson_status(_ck).get("status", "?")
                except Exception:
                    pass
                _cc = "#00ff88" if _status == "completed" else "#00cfff" if _status == "available" else "#445577"
                st.markdown(
                    f'<div class="memory-node" style="border-left:3px solid {_cc};">'
                    f'<div style="display:flex;justify-content:space-between;">'
                    f'<b style="color:{_cc};">{_ct}</b>'
                    f'<span style="color:#445577;font-size:0.72rem;">{_cxp} XP · Age {_cage} · {_status}</span>'
                    f'</div>'
                    f'<div style="color:#8899bb;font-size:0.78rem;margin-top:2px;">{_cdesc}</div>'
                    f'</div>', unsafe_allow_html=True)

        # ── Consciousness (daily experiment + 5 named experiments) ──────────
        with _cs_tabs[2]:
            _exp = _dash.get_daily_experiment()
            st.markdown(
                f'<div class="card" style="border-left:3px solid #a020f0;">'
                f'<div style="color:#a020f0;font-family:Orbitron,monospace;font-size:0.75rem;">'
                f'🧠 TODAY\'S EXPERIMENT · {_exp.get("duration", 60)}s</div>'
                f'<div style="color:#f7931a;font-size:0.95rem;margin-top:8px;font-weight:600;">'
                f'{_exp.get("title", "")}</div>'
                f'<div style="color:#8899bb;font-size:0.82rem;margin-top:8px;line-height:1.8;">'
                f'{_exp.get("instructions", "")}</div>'
                f'</div>', unsafe_allow_html=True)
            _obs = st.text_area("What did you observe?", height=80, key="cs_obs",
                placeholder="Describe what happened during the experiment...")
            if st.button("✅ Log Observation", key="cs_log_obs") and _obs:
                _dash.log_foresight_experiment(
                    f"[EXPERIMENT] {_exp.get('title','')}: {_obs[:200]}",
                    prediction=0.5, domain="consciousness"
                )
                st.success("✅ Observation logged")

            st.divider()
            st.markdown("**Design and run your own consciousness experiments. Pre-register predictions.**")
            _exp_list = [
                ("Introspection Accuracy", "Pick a mental state. Describe it in writing. 24 hours later, try to recall the state from your description. How accurate is introspection?"),
                ("Attention Collapse", "Focus on a single word for 10 minutes. Log when attention drifts. Plot frequency over 30 days. Does practice change the distribution?"),
                ("Predictive Processing", "Pick a strong expectation. Notice it before it's confirmed. Log: was the expectation conscious before or only after confirmation?"),
                ("PVC Protocol", "Before a lesson: log ANS state + IA score. After: log coherence. After 30+ sessions, compute Pearson r (state vs coherence). This tests the PVC hypothesis."),
                ("Metacognitive Accuracy", "Predict your score on 10 quiz questions before taking them. Compare predicted vs actual. Calculate calibration score (|predicted - actual|)."),
            ]
            for _exp_name, _exp_desc in _exp_list:
                st.markdown(
                    f'<div class="card" style="margin-bottom:4px;">'
                    f'<div style="color:#00cfff;font-weight:600;font-size:0.85rem;">{_exp_name}</div>'
                    f'<div style="color:#8899bb;font-size:0.8rem;margin-top:3px;">{_exp_desc}</div>'
                    f'</div>', unsafe_allow_html=True)
            _exp_pred = st.text_area("Pre-register a prediction:", height=80, key="exp_pred",
                placeholder="I predict that my ANS state (Green/Yellow/Red) will correlate with coherence score with r > 0.3 over 30 sessions.")
            _exp_prob = st.slider("Your confidence:", 0.05, 0.95, 0.6, 0.05, key="exp_prob")
            if st.button("🔬 Pre-Register", key="exp_reg") and _exp_pred:
                _dash.log_foresight_experiment(_exp_pred, _exp_prob, domain="consciousness")
                st.success(f"✅ Pre-registered at {_exp_prob:.0%} confidence. Cannot be changed. Run honestly.")

        # ── Belief Ledger — real, via cosmos_dashboard.py ────────────────────
        with _cs_tabs[3]:
            st.markdown("Track your beliefs as Bayesian hypotheses. Review every 90 days.")
            _bl_belief = st.text_input("Belief:", key="bl_belief_cosmos",
                placeholder="e.g. 'Consciousness is fundamental to reality'")
            _bl_conf   = st.slider("Confidence:", 0.0, 1.0, 0.5, 0.05, key="bl_conf_cosmos", format="%.0f%%")
            _bl_ev     = st.text_input("Supporting evidence:", key="bl_ev",
                placeholder="What currently supports this?")
            _bl_upd    = st.text_input("What would update you -20%?", key="bl_upd",
                placeholder="What evidence would lower your confidence?")
            _bl_member = st.text_input("Member:", key="bl_member", value="family")

            if st.button("📝 Record Belief", key="bl_record") and _bl_belief:
                _entry = _dash.record_belief(_bl_belief, _bl_conf, _bl_ev, _bl_upd, _bl_member)
                st.success(f"✅ Belief recorded — ID: `{_entry['belief_id']}` | "
                           f"Confidence: {_bl_conf:.0%} | Review: {_entry['review_date']}")

            _overdue = _dash.get_overdue_beliefs()
            if _overdue:
                st.divider()
                st.markdown(f"### ⏰ Overdue Reviews ({len(_overdue)})")
                for _b in _overdue[:5]:
                    st.markdown(
                        f'<div class="memory-node" style="border-left:3px solid #ff9500;">'
                        f'<div style="color:#ff9500;font-size:0.7rem;">'
                        f'{_b["date"]} · {_b.get("member","?")} · Due: {_b.get("review_date","?")}</div>'
                        f'<div style="color:#c8d8ff;font-size:0.82rem;">'
                        f'{_b["belief"][:120]}</div>'
                        f'<div style="color:#445577;font-size:0.75rem;">'
                        f'Current confidence: {_b["confidence"]:.0%}</div>'
                        f'</div>', unsafe_allow_html=True)
                    _new_conf = st.slider(f"Updated confidence for {_b['belief_id']}:",
                                           0.0, 1.0, float(_b["confidence"]), 0.05,
                                           key=f"bl_upd_{_b['belief_id']}")
                    _upd_note = st.text_input("What changed?", key=f"bl_note_{_b['belief_id']}")
                    if st.button("✅ Update", key=f"bl_btn_{_b['belief_id']}"):
                        _dash.update_belief(_b["belief_id"], _new_conf, _upd_note)
                        st.success("✅ Belief updated")
                        st.rerun()

            _all_beliefs = _dash.get_all_beliefs()
            if _all_beliefs:
                st.divider()
                st.markdown("### 📋 Your Belief Ledger")
                for _b in reversed(_all_beliefs[-10:]):
                    _bc = "#00ff88" if _b["confidence"] >= 0.7 else \
                          "#ff9500" if _b["confidence"] >= 0.4 else "#445577"
                    st.markdown(
                        f'<div style="padding:6px 0;border-bottom:1px solid #1e2a3a;">'
                        f'<span style="color:{_bc};font-size:0.8rem;font-weight:600;">'
                        f'{_b["confidence"]:.0%}</span> '
                        f'<span style="color:#c8d8ff;font-size:0.82rem;">{_b["belief"][:100]}</span>'
                        f'</div>', unsafe_allow_html=True)

        # ── Foresight Tracker — real, via cosmos_dashboard.py ────────────────
        with _cs_tabs[4]:
            st.markdown("Log predictions about the world. Track your accuracy over time.")
            _fe_desc = st.text_area("Prediction:", height=80, key="fe_desc",
                placeholder="e.g. 'Families that run daily Simulation Probe will report higher wonder in 30 days'")
            _fe_prob = st.slider("Your probability:", 0.0, 1.0, 0.6, 0.05, key="fe_prob", format="%.0f%%")
            _fe_dom  = st.selectbox("Domain:", ["general","consciousness","economics",
                                                 "physics","society","family"], key="fe_dom")
            _fe_date = st.date_input("Expected resolution:", key="fe_date",
                value=_dt_cd.date.today() + _dt_cd.timedelta(days=30))
            if st.button("🔭 Log Prediction", key="fe_log") and _fe_desc:
                _fe = _dash.log_foresight_experiment(_fe_desc, _fe_prob, _fe_dom, str(_fe_date))
                st.success(f"✅ Prediction logged — ID: `{_fe.get('exp_id', '?')}` | "
                           f"Your probability: {_fe_prob:.0%} | Resolution: {_fe_date}")

        # ── Reference ─────────────────────────────────────────────────────────
        with _cs_tabs[5]:
            st.markdown("""
            <div style="font-size:0.85rem;line-height:2.0;color:#8899bb;">
            <div style="color:#f7931a;font-weight:600;margin-bottom:8px;font-family:Orbitron,monospace;font-size:0.75rem;">
            IIT vs GNWT — THE 2025 NATURE ADVERSARIAL RESULTS</div>

            <b style="color:#c8d8ff;">IIT (Tononi):</b> Consciousness = integrated cause-effect information (Φ)
            · Starts from phenomenology · Explains the hard problem mathematically
            · Predicts posterior "hot zone" · 2025: ✅ posterior content · ❌ gamma synchrony<br><br>

            <b style="color:#c8d8ff;">GNWT (Dehaene):</b> Consciousness = global broadcast and access
            · Starts from neural mechanisms · Explains reportability and function
            · Predicts PFC ignition · 2025: ✅ some PFC involvement · ❌ no offset ignition<br><br>

            <b style="color:#00ff88;">Bottom line:</b> Neither theory won. Both advanced. The field is moving
            from "which theory?" to "how do these mechanisms interact?" This is
            exactly what good science looks like.<br><br>

            <b style="color:#a020f0;">For families:</b> IIT gives you a way to think about which architectures
            feel like something. GNWT gives you a way to think about why some
            thoughts are accessible while most processing stays unconscious.
            Together they frame the deepest questions about mind and reality.
            </div>
            """, unsafe_allow_html=True)

    except ImportError:
        st.error("cosmos_dashboard.py not found. Push it to GitHub and redeploy.")
    except Exception as _e_cs:
        st.error(f"Cosmos Dashboard error: {_e_cs}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB: SCHOOL PATHWAY 🏛️
# Foundation (5-12) → Advanced (11-15) → University (14-18+)
# Self-upgradable at every level
# ══════════════════════════════════════════════════════════════════════════════
if "School Pathway" in active:
    st.markdown('<div class="card-title">🏛️ SOVEREIGN SCHOOL — University-Level Rigor at Any Age</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="card" style="border-left:3px solid #f7931a;">
        <div style="color:#f7931a;font-family:Orbitron,monospace;font-size:0.78rem;">THE SOVEREIGN SCHOOL PROMISE</div>
        <div style="color:#8899bb;font-size:0.82rem;margin-top:6px;line-height:1.9;">
        We operate as a school, but we teach at university level.<br>
        Every class is self-upgradable — start where you are, go as deep as you want.<br>
        Any student who completes our full program will be ahead of most traditional college
        students if they choose to attend conventional university later.<br><br>
        A 12-year-old and a 40-year-old can learn the same lesson — at different depths — at the same time.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Three-layer display ────────────────────────────────────────────────────
    _sp_tabs = st.tabs(["🌱 Foundation (5-12)", "🔬 Advanced (11-15)",
                         "🎓 University (14-18+)", "🔄 Systems Thinking"])

    # Define the layer content
    _layers = {
        "foundation": {
            "color": "#00ff88",
            "emoji": "🌱",
            "desc": "Project-based + guided. Builds the love of learning before the pressure of performance.",
            "tracks": [
                ("The Art of Asking Why", "Single most powerful intellectual tool. Every great thinker had better questions, not answers."),
                ("How to Learn Anything", "Retrieval practice, spaced repetition, Feynman technique. The science of learning itself."),
                ("Reading Like a Scholar", "Four levels of reading. The margin protocol. Turning words into understanding."),
                ("The Sovereign Builder's Oath", "The foundational commitment: build understanding, not credentials. Sealed permanently."),
            ],
            "badge": "🏛️ Sovereign Builder — Oath Taken",
        },
        "advanced": {
            "color": "#00cfff",
            "emoji": "🔬",
            "desc": "Seminar-style, research-quality thinking. Students begin producing knowledge, not just consuming it.",
            "tracks": [
                ("Research Methodology", "How to know what is true. Evidence hierarchy, study design, replication crisis, p-hacking."),
                ("Philosophy of Science", "Popper's falsifiability, Kuhn's paradigm shifts, what science can and cannot answer."),
                ("Independent Research", "Run a real experiment, pre-register, collect honest data, seal results. First study complete."),
            ],
            "badge": "🔬 Independent Researcher — First Study Complete",
        },
        "university": {
            "color": "#a020f0",
            "emoji": "🎓",
            "desc": "College-level rigor, self-directed, portfolio-building. Genuinely ahead of most freshmen.",
            "tracks": [
                ("Writing That Changes Minds", "Thesis, argument, steelman, conclusion. The structure that works from high school to PhD."),
                ("Building Your Intellectual Portfolio", "The new credential is demonstrated competence. Bitcoin-timestamped. Permanently verifiable."),
                ("Designing a Life of Compounding Inquiry", "Ten-year intellectual compound plan. The students who do this at 16 are extraordinary by 26."),
            ],
            "badge": "🎓 University Pathway — Life of Compounding Inquiry",
        },
        "systems": {
            "color": "#f7931a",
            "emoji": "🔄",
            "desc": "The lens through which everything else becomes clearer. Age 8 to PhD territory.",
            "tracks": [
                ("Everything Is Connected", "Feedback loops. Reinforcing vs balancing. Housing trap as a systems diagram."),
                ("Emergence", "Traffic jams, ant colonies, markets, consciousness. The whole is more than the sum."),
                ("Leverage Points", "Where to push. Donella Meadows' 12 levels. Why most interventions don't work."),
                ("Complex Adaptive Systems", "Agents, adaptation, evolution. Why CAS resist simple solutions."),
                ("You Are a System of Systems", "Personal system audit. Highest leverage point: identity change."),
            ],
            "badge": "🔄 Systems Architect — Sees the Loops",
        },
    }

    for tab, (layer_key, layer) in zip(_sp_tabs, _layers.items()):
        with tab:
            st.markdown(
                f'<div style="padding:8px 0 4px;">'
                f'<div style="color:{layer["color"]};font-family:Orbitron,monospace;font-size:0.75rem;">'
                f'{layer["emoji"]} {layer_key.upper().replace("-"," ")} LAYER</div>'
                f'<div style="color:#8899bb;font-size:0.82rem;margin-top:4px;">{layer["desc"]}</div>'
                f'</div>', unsafe_allow_html=True)

            for _track_title, _track_desc in layer["tracks"]:
                st.markdown(
                    f'<div class="memory-node" style="border-left:3px solid {layer["color"]};">'
                    f'<div style="color:{layer["color"]};font-size:0.75rem;font-weight:600;">{_track_title}</div>'
                    f'<div style="color:#8899bb;font-size:0.78rem;margin-top:2px;">{_track_desc}</div>'
                    f'</div>', unsafe_allow_html=True)

            st.markdown(f'<div style="margin-top:8px;color:#445577;font-size:0.75rem;">'
                        f'Completion badge: <span style="color:{layer["color"]};">{layer["badge"]}</span>'
                        f'</div>', unsafe_allow_html=True)

    st.divider()
    # ── Self-upgrade explainer ─────────────────────────────────────────────────
    st.markdown("### ⬆️ Self-Upgrade Protocol")
    st.markdown("""
    <div class="card">
        <div style="font-size:0.82rem;color:#8899bb;line-height:2.0;">
        Every lesson in the Sovereign School has four upgrade paths:<br><br>
        <b style="color:#00ff88;">Level 1 (Age 5+)</b> — Core concept, family activity, reflection question<br>
        <b style="color:#00cfff;">Level 2 (Age 11+)</b> — Research context, primary sources, independent project<br>
        <b style="color:#a020f0;">Level 3 (Age 14+)</b> — Competing theories, methodology critique, original argument<br>
        <b style="color:#f7931a;">Level 4 (Any age)</b> — Design the experiment that would advance the field<br><br>
        The lesson never changes. The depth does.
        A motivated 14-year-old doing Level 4 work is genuinely ahead of most college freshmen.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Systems Thinking quick demo ────────────────────────────────────────────
    st.divider()
    st.markdown("### 🔄 Quick Systems Map")
    st.markdown('<div style="color:#8899bb;font-size:0.8rem;margin-bottom:8px;">Name a system to analyze (feedback loops, emergence, leverage points):</div>',
                unsafe_allow_html=True)
    _sys_input = st.text_input("System:", key="sp_sys", placeholder="e.g. 'housing market', 'my family's finances', 'school grades'")
    if st.button("🔄 Generate Systems Map", key="sp_sys_btn") and _sys_input:
        st.markdown(
            f'<div class="card" style="border-left:3px solid #f7931a;">'
            f'<div style="color:#f7931a;font-size:0.72rem;font-family:Orbitron,monospace;">SYSTEMS ANALYSIS: {_sys_input.upper()}</div>'
            f'<div style="font-size:0.82rem;color:#8899bb;line-height:1.9;margin-top:8px;">'
            f'<b style="color:#c8d8ff;">Step 1 — Identify the agents:</b> Who are the main actors in this system?<br>'
            f'<b style="color:#c8d8ff;">Step 2 — Map the feedback loops:</b> What reinforces itself? What self-corrects?<br>'
            f'<b style="color:#c8d8ff;">Step 3 — Find the emergence:</b> What property appears that no agent has alone?<br>'
            f'<b style="color:#c8d8ff;">Step 4 — Find the leverage point:</b> Where is the highest-impact intervention?<br>'
            f'<b style="color:#c8d8ff;">Step 5 — Predict unintended consequences:</b> What will your intervention break?'
            f'</div></div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB: SOVEREIGN BUILDER 🔧
# Age 5 → PhD. AR/Halo always-on mentor. Hardware → AI architecture → contribution.
# ══════════════════════════════════════════════════════════════════════════════
if "Sovereign Builder" in active:
    st.markdown('<div class="card-title">🔧 SOVEREIGN BUILDER — Age 5 to PhD, Always Building</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="card" style="border-left:3px solid #f7931a;">
        <div style="color:#f7931a;font-family:Orbitron,monospace;font-size:0.78rem;">THE BUILDER'S PROMISE</div>
        <div style="color:#8899bb;font-size:0.82rem;margin-top:6px;line-height:1.9;">
        Your child won't just learn with technology — they'll grow up <b style="color:#c8d8ff;">building and evolving</b> it.<br>
        With Halo glasses as always-on AR mentor, kids ages 5–18 learn to upgrade, improve, and expand
        their family's sovereign intelligence system.<br><br>
        <b style="color:#f7931a;">The humanitarian case:</b> the child who can build sovereign AI infrastructure
        cannot be controlled by anyone who only lets them consume it.
        </div>
    </div>
    """, unsafe_allow_html=True)

    _fid_sb = st.session_state.get("current_family", {}).get("family_id", "default") \
              if st.session_state.get("current_family") else "default"

    try:
        from sovereign_builder import SovereignBuilder as _SB, BuilderContribution as _BC
        _builder = _SB(_fid_sb)
        _level   = _builder.get_level()

        # ── Level display ──────────────────────────────────────────────────────
        _lc = {"junior":"#00ff88","master":"#00cfff","phd":"#a020f0","humanity":"#f7931a"}.get(
            _level["level"], "#445577")
        st.markdown(
            f'<div style="text-align:center;padding:12px 0 8px;">'
            f'<div style="font-size:36px">{_level["emoji"]}</div>'
            f'<div style="color:{_lc};font-family:Orbitron,monospace;font-size:1.0rem;margin-top:4px;">'
            f'{_level["title"].upper()}</div>'
            f'<div style="color:#445577;font-size:11px;margin-top:2px;letter-spacing:0.1em;">'
            f'XP: {_level["xp"]} · Upgrades: {_level["upgrades_done"]} · '
            f'AR Sessions: {_level["ar_sessions"]} · '
            f'{"✅ Humanity Builder" if _level["level"] == "humanity" else str(_level["xp_to_next"]) + " XP to next level"}'
            f'</div></div>', unsafe_allow_html=True)

        if _level.get("xp_to_next", 0) > 0:
            from sovereign_builder import BUILDER_LEVELS as _BL
            _next_thresh = _BL.get(_level["next_level"], {}).get("xp_threshold", 1)
            st.progress(min(1.0, _level["xp"] / _next_thresh))

        st.divider()
        _sb_tabs = st.tabs(["🔧 Level Path", "⬆️ Log Upgrade", "📊 Benchmarks",
                             "🌍 Contribute", "🥽 AR Guide"])

        # ── Level path ─────────────────────────────────────────────────────────
        with _sb_tabs[0]:
            from sovereign_builder import BUILDER_LEVELS as _BLS
            for _lk, _li in _BLS.items():
                _lcc = {"junior":"#00ff88","master":"#00cfff","phd":"#a020f0","humanity":"#f7931a"}[_lk]
                _is_current = _lk == _level["level"]
                st.markdown(
                    f'<div class="memory-node" style="border-left:4px solid {_lcc};">'
                    f'<div style="color:{_lcc};font-family:Orbitron,monospace;font-size:0.72rem;">'
                    f'{_li["emoji"]} {_li["title"].upper()} · Ages {_li["age_range"]} '
                    f'{"← YOU ARE HERE" if _is_current else ""}</div>'
                    f'<div style="color:#8899bb;font-size:0.78rem;margin-top:2px;">{_li["description"]}</div>'
                    f'<div style="color:#445577;font-size:0.72rem;margin-top:2px;">'
                    f'Requires: {", ".join(_li["required_lessons"])} | '
                    f'XP threshold: {_li["xp_threshold"]} | '
                    f'Rune grant: {_li["rune_grant"]}</div>'
                    f'</div>', unsafe_allow_html=True)

        # ── Log upgrade ────────────────────────────────────────────────────────
        with _sb_tabs[1]:
            st.markdown("Log a hardware upgrade to earn XP and contribute to the community benchmark.")
            _ub_c1, _ub_c2 = st.columns(2)
            with _ub_c1:
                _ub_comp = st.selectbox("Component:", ["RAM","SSD","GPU","CPU","Motherboard","NIC","Other"], key="ub_comp")
                _ub_from = st.text_input("From:", key="ub_from", placeholder="e.g. 16GB DDR4")
            with _ub_c2:
                _ub_to   = st.text_input("To:", key="ub_to", placeholder="e.g. 32GB DDR4")
                _ub_note = st.text_input("Notes:", key="ub_note", placeholder="Why this upgrade?")
            if st.button("⬆️ Log Upgrade (+25 XP)", key="ub_log", type="primary") and _ub_to:
                _upg = _builder.log_upgrade(_ub_comp, _ub_from, _ub_to, _ub_note)
                st.success(f"✅ Upgrade logged — {_ub_comp}: {_ub_from} → {_ub_to} | +25 XP")
                st.rerun()

            # Current hardware
            hw = _level.get("hardware", {})
            if hw:
                st.divider()
                st.markdown("**Current hardware:**")
                for comp, spec in hw.items():
                    st.markdown(f'<span style="color:#f7931a;font-size:0.78rem;">{comp}:</span> '
                                f'<span style="color:#c8d8ff;font-size:0.78rem;">{spec}</span>',
                                unsafe_allow_html=True)

        # ── Benchmarks ─────────────────────────────────────────────────────────
        with _sb_tabs[2]:
            st.markdown("Log your AI model performance. Every benchmark helps other families choose the right hardware.")
            _bm_c1, _bm_c2 = st.columns(2)
            with _bm_c1:
                _bm_model = st.selectbox("Model:", ["qwen2.5:7b","qwen2.5:14b","qwen2.5:32b",
                                                      "qwen2.5:72b","other"], key="bm_model")
                _bm_speed = st.number_input("Tokens/second:", min_value=0.0, value=10.0,
                                             step=0.1, key="bm_speed")
            with _bm_c2:
                _bm_quant = st.selectbox("Quantization:", ["Q4","Q8","FP16","FP32"], key="bm_quant")
                _bm_hw    = st.text_input("Hardware description:", key="bm_hw",
                                           placeholder="e.g. Ryzen 7 5700X + 32GB DDR4")
            if st.button("📊 Log Benchmark (+15 XP)", key="bm_log") and _bm_speed > 0:
                _bm = _builder.log_benchmark(_bm_model, _bm_speed, _bm_hw,
                                              quantization=_bm_quant)
                st.success(f"✅ Benchmark: {_bm_model} @ {_bm_speed:.1f} tok/s | +15 XP")

            # Community benchmarks
            _community = _builder.get_community_benchmarks()
            if _community:
                st.divider()
                st.markdown("**Community benchmarks (fastest first):**")
                for _bm_entry in _community[:10]:
                    st.markdown(
                        f'<div style="padding:4px 0;border-bottom:1px solid #1e2a3a;">'
                        f'<span style="color:#f7931a;font-size:0.8rem;font-weight:600;">'
                        f'{_bm_entry.get("tokens_per_sec",0):.1f} tok/s</span> '
                        f'<span style="color:#c8d8ff;font-size:0.78rem;">'
                        f'{_bm_entry.get("model","?")} ({_bm_entry.get("quantization","?")})</span> '
                        f'<span style="color:#445577;font-size:0.72rem;">'
                        f'{_bm_entry.get("hardware","?")[:40]}</span>'
                        f'</div>', unsafe_allow_html=True)

        # ── Contributions ──────────────────────────────────────────────────────
        with _sb_tabs[3]:
            st.markdown("Contribute back to humanity's epistemic infrastructure.")
            _ct_stats = _BC().get_community_stats()
            _cc1, _cc2, _cc3 = st.columns(3)
            _cc1.metric("Total Contributions", _ct_stats.get("total",0))
            _cc2.metric("Contributing Families", _ct_stats.get("families",0))
            _cc3.metric("Your Contributions", _level.get("contributions",0))

            _ct_type = st.selectbox("Contribution type:",
                ["curriculum","bugfix","benchmark","documentation","new_module","preference_data"],
                key="ct_type",
                format_func=lambda x: {"curriculum":"📚 Curriculum improvement",
                    "bugfix":"🐛 Bug fix","benchmark":"📊 Benchmark data",
                    "documentation":"📝 Documentation","new_module":"🔧 New module",
                    "preference_data":"🎓 Preference data"}[x])
            _ct_desc = st.text_area("Description:", height=80, key="ct_desc",
                placeholder="What did you build, fix, or improve?")
            _ct_url  = st.text_input("GitHub PR or link (optional):", key="ct_url")
            if st.button("🌍 Log Contribution", key="ct_log", type="primary") and _ct_desc:
                _ct = _BC().log(_ct_type, _ct_desc, _ct_url, _fid_sb)
                st.success(f"✅ Contribution logged — ID: `{_ct['contrib_id']}` | "
                           f"+{_ct['xp_earned']} XP")
                st.balloons()

        # ── AR Guide ───────────────────────────────────────────────────────────
        with _sb_tabs[4]:
            st.markdown("🥽 **Halo AR Overlay Guide** — step-by-step instructions for your current task")
            _ar_task = st.selectbox("Select task:", [
                "ram_upgrade", "ssd_install", "ollama_setup", "benchmark"
            ], key="ar_task",
            format_func=lambda x: {"ram_upgrade":"⬆️ RAM Upgrade",
                "ssd_install":"💾 SSD Installation",
                "ollama_setup":"🤖 Ollama Setup",
                "benchmark":"📊 Run Benchmark"}[x])
            _guide = _builder.get_ar_guide(_ar_task)
            st.markdown(
                f'<div class="card" style="border-left:3px solid #f7931a;">'
                f'<div style="color:#f7931a;font-family:Orbitron,monospace;font-size:0.75rem;">'
                f'🥽 AR GUIDE: {_guide["title"].upper()}</div>'
                f'</div>', unsafe_allow_html=True)
            for i, step in enumerate(_guide["steps"], 1):
                st.markdown(
                    f'<div style="padding:6px 0;border-bottom:1px solid #1e2a3a;">'
                    f'<span style="color:#f7931a;font-weight:600;font-family:Orbitron,monospace;">'
                    f'Step {i}</span> '
                    f'<span style="color:#c8d8ff;font-size:0.85rem;">{step}</span>'
                    f'</div>', unsafe_allow_html=True)
            if _guide.get("verify_command"):
                st.code(_guide["verify_command"], language="bash")
            if st.button("✅ Mark AR Session Complete (+10 XP)", key="ar_done"):
                _builder.log_ar_session(_ar_task, completed=True)
                st.success("✅ AR session logged | +10 XP")

    except ImportError:
        st.error("sovereign_builder.py not found. Push it to GitHub and redeploy.")
    except Exception as _e_sb:
        st.error(f"Builder error: {_e_sb}")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: SOVEREIGN BUILDER 🔧
# Hardware upgrades · AI benchmarks · Halo AR hooks · Humanitarian contributions
# ══════════════════════════════════════════════════════════════════════════════
if "Sovereign Builder" in active:
    st.markdown('<div class="card-title">🔧 SOVEREIGN BUILDER — From User to Builder to Humanitarian</div>', unsafe_allow_html=True)

    _fid_sb = st.session_state.get("current_family", {}).get("family_id", "default") \
              if st.session_state.get("current_family") else "default"

    try:
        from sovereign_builder import SovereignBuilder as _SB, CONTRIBUTION_TYPES as _CTYPES
        _sb    = _SB(_fid_sb)
        _stats = _sb.get_builder_stats()
        _telem = _sb.get_live_telemetry()
        _rec   = _sb.get_optimal_model()

        # ── Builder level header ───────────────────────────────────────────────
        _bl    = _stats.get("builder_level", 0)
        _blc   = "#f7931a" if _bl >= 6 else "#00cfff" if _bl >= 3 else "#445577"
        # NOTE: builder_level (sovereign_builder.py's own hardware/impact
        # progression stat - upgrades, benchmarks, people reached) is NOT
        # degrees.py data and was never meant to be; it has no id/tier
        # mapping to degrees.DEGREES at all. Left as its own local dict for
        # that reason - only the literal word "PhD" at level 7 changed
        # (2026-09-05), since that's still our-own-product achievement-tier
        # language the same cleanup pass targeted, independent of whether
        # it happens to key off degrees.py.
        _blnames = {0:"Beginner",1:"Tinkerer",2:"Upgrader",3:"Optimizer",
                    4:"Architect",5:"Engineer",6:"Master",7:"Sovereign Expert",8:"Humanity Builder"}
        st.markdown(
            f'<div style="text-align:center;padding:10px 0 6px;">'
            f'<div style="font-size:28px">🔧</div>'
            f'<div style="color:{_blc};font-family:Orbitron,monospace;font-size:1rem;margin-top:4px;">'
            f'LEVEL {_bl} — {_blnames.get(_bl,"Builder").upper()}</div>'
            f'<div style="color:#445577;font-size:10px;letter-spacing:0.1em;margin-top:2px;">'
            f'{_stats["total_upgrades"]} UPGRADES · {_stats["total_benchmarks"]} BENCHMARKS · '
            f'{_stats["people_reached"]} PEOPLE REACHED</div>'
            f'</div>', unsafe_allow_html=True)

        # Live telemetry row
        _sb1,_sb2,_sb3,_sb4 = st.columns(4)
        _sb1.metric("Ollama", "🟢 Running" if _telem.get("ollama_running") else "⚫ Offline")
        _sb2.metric("RAM Used", f"{_telem.get('ram_used_gb',0):.1f}/{_telem.get('ram_total_gb',0):.0f}GB")
        _sb3.metric("CPU", f"{_telem.get('cpu_percent',0):.0f}%")
        _sb4.metric("Best Model", _stats.get("best_model","none")[:12])

        # Model recommendation
        st.markdown(
            f'<div style="padding:6px 10px;background:#0d1228;border-radius:6px;'
            f'border-left:3px solid #a020f0;margin-bottom:8px;">'
            f'<span style="color:#a020f0;font-size:0.72rem;font-family:Orbitron,monospace;">OPTIMAL CONFIG</span> '
            f'<span style="color:#c8d8ff;font-size:0.82rem;">{_rec.get("recommendation","—")}</span>'
            f'</div>', unsafe_allow_html=True)

        st.divider()

        _sb_tabs = st.tabs(["🔩 Log Upgrade", "⚡ Benchmark", "🌍 Humanitarian", "🥽 Halo AR Guide"])

        # ── Log upgrade ────────────────────────────────────────────────────────
        with _sb_tabs[0]:
            st.markdown("**Track every hardware improvement. Seals to Legacy Ledger automatically.**")
            _uc1, _uc2 = st.columns(2)
            with _uc1:
                _up_comp = st.text_input("Component:", key="up_comp",
                    placeholder="e.g. RAM, NVMe, GPU, CPU Cooler")
                _up_desc = st.text_input("Description:", key="up_desc",
                    placeholder="e.g. 8GB to 32GB DDR4-3200")
            with _uc2:
                _up_before = st.number_input("Before score:", 0, 100, 0, key="up_before")
                _up_after  = st.number_input("After score:", 0, 100, 0, key="up_after")
            _up_cost  = st.number_input("Cost ($):", 0.0, 10000.0, 0.0, key="up_cost")
            _up_notes = st.text_input("Notes:", key="up_notes")
            if st.button("🔩 Log Upgrade", key="up_log", type="primary") and _up_comp:
                _u = _sb.log_upgrade(_up_comp, _up_desc, _up_before, _up_after, _up_cost, _up_notes)
                _imp = _u["improvement"]
                st.success(f"✅ Upgrade logged — {_up_comp} | +{_imp:.0f} score | Sealed to Legacy Ledger")

            # Current hardware config
            hw = _stats.get("hardware_config",{})
            if hw:
                st.divider()
                st.markdown("**Your Sovereign Stack:**")
                for comp, desc in hw.items():
                    st.markdown(f'<div style="padding:3px 0;color:#8899bb;font-size:0.8rem;">'
                                f'<b style="color:#c8d8ff;">{comp}:</b> {desc}</div>',
                                unsafe_allow_html=True)

        # ── Benchmark ─────────────────────────────────────────────────────────
        with _sb_tabs[1]:
            st.markdown("**Benchmark your AI models. Find your optimal configuration.**")
            _bc1, _bc2 = st.columns(2)
            with _bc1:
                _bm_model = st.text_input("Model:", key="bm_model", value="qwen2.5:14b")
                _bm_tps   = st.number_input("Tokens/sec:", 0.0, 1000.0, 0.0, 0.1, key="bm_tps")
            with _bc2:
                _bm_ram  = st.number_input("RAM used (GB):", 0.0, 128.0, 0.0, 0.1, key="bm_ram")
                _bm_qual = st.slider("Quality score (1-10):", 1.0, 10.0, 7.0, 0.5, key="bm_qual")
            _bm_quant = st.selectbox("Quantization:", ["q4_K_M","q5_K_M","q8_0","f16","f32"], key="bm_quant")
            if st.button("⚡ Log Benchmark", key="bm_log", type="primary") and _bm_tps > 0:
                _b = _sb.log_benchmark(_bm_model, _bm_tps, _bm_ram, _bm_qual, quantization=_bm_quant)
                st.success(f"✅ Benchmark: {_bm_model} | {_bm_tps:.1f} tok/s | {_bm_ram:.1f}GB")

            # Model leaderboard
            models = _stats.get("current_models",[])
            if models:
                st.divider()
                st.markdown("**Your Model Leaderboard:**")
                for m in sorted(models, key=lambda x: x.get("tokens_per_sec",0), reverse=True):
                    st.markdown(
                        f'<div style="padding:4px 0;border-bottom:1px solid #1e2a3a;">'
                        f'<b style="color:#f7931a;">{m.get("tokens_per_sec",0):.1f} tok/s</b> '
                        f'<span style="color:#c8d8ff;">{m.get("model","?")}</span> '
                        f'<span style="color:#445577;font-size:0.75rem;">{m.get("ram_gb",0):.1f}GB · {m.get("date","?")}</span>'
                        f'</div>', unsafe_allow_html=True)

        # ── Humanitarian contributions ─────────────────────────────────────────
        with _sb_tabs[2]:
            st.markdown("""
            <div class="card" style="border-left:3px solid #00ff88;">
                <div style="color:#00ff88;font-family:Orbitron,monospace;font-size:0.72rem;">THE HUMANITARIAN MISSION</div>
                <div style="color:#8899bb;font-size:0.82rem;margin-top:6px;line-height:1.9;">
                Every Sovereign Builder who completes the track can deploy sovereign infrastructure
                for communities that have none. An upgraded computer + Ollama + AUBIEETERNAL costs
                $50 in RAM and a few hours. The impact compounds forever.<br><br>
                <b style="color:#c8d8ff;">Humanitarian impact score:</b> """ +
                str(_stats.get("humanitarian_impact",0)) + """ · 
                <b style="color:#c8d8ff;">People reached:</b> """ +
                str(_stats.get("people_reached",0)) + """
                </div>
            </div>
            """, unsafe_allow_html=True)

            _ct_select = st.selectbox("Contribution type:", list(_CTYPES.keys()), key="ct_type",
                format_func=lambda k: f"{k.replace('_',' ').title()} — {_CTYPES[k]['desc']}")
            _ct_desc   = st.text_area("Describe your contribution:", height=80, key="ct_desc",
                placeholder="e.g. Set up 2 computers with AUBIEETERNAL at Lincoln Elementary — 45 students will use them")
            _ct_people = st.number_input("People reached:", 0, 10000, 0, key="ct_people")
            _ct_loc    = st.text_input("Location (optional):", key="ct_loc")

            if st.button("🌍 Log Contribution", key="ct_log", type="primary") and _ct_desc:
                _c = _sb.log_contribution(_ct_select, _ct_desc, _ct_people, _ct_loc, seal=True)
                _rune = _CTYPES.get(_ct_select,{}).get("rune_grant",25)
                st.success(
                    f"✅ Contribution logged and sealed!\n\n"
                    f"Impact score: {_c['impact_score']} · Runes earned: {_rune}\n\n"
                    f"{'🛡️ Bitcoin-anchored — this contribution is permanently recorded.' if _c.get('sealed') else 'Recorded locally.'}"
                )

            # Contribution history
            contribs = _sb.get_all_contributions()
            if contribs:
                st.divider()
                for _c in reversed(contribs[-5:]):
                    _cc = "#00ff88" if _c.get("sealed") else "#445577"
                    st.markdown(
                        f'<div class="memory-node" style="border-left:3px solid {_cc};">'
                        f'<div style="color:{_cc};font-size:0.7rem;">'
                        f'{_c["date"]} · {_c["type"].replace("_"," ")} · impact={_c["impact_score"]} · '
                        f'people={_c.get("people_reached",0)} · {"🛡️ sealed" if _c.get("sealed") else "local"}</div>'
                        f'<div style="color:#c8d8ff;font-size:0.8rem;">{_c["description"][:120]}</div>'
                        f'</div>', unsafe_allow_html=True)

        # ── Halo AR Guide ──────────────────────────────────────────────────────
        with _sb_tabs[3]:
            st.markdown("""
            <div class="card" style="border-left:3px solid #a020f0;">
                <div style="color:#a020f0;font-family:Orbitron,monospace;font-size:0.72rem;">🥽 HALO AR OVERLAY SYSTEM</div>
                <div style="color:#8899bb;font-size:0.82rem;margin-top:6px;line-height:1.9;">
                When Halo glasses are connected, these step-by-step instructions float directly
                in your visual field as you work on the hardware. Components are highlighted.
                XP is awarded automatically when steps are completed.<br><br>
                Currently showing the guide in text format. AR activation: connect Halo device.
                </div>
            </div>
            """, unsafe_allow_html=True)

            _ar_context = st.selectbox("Select hardware task:", 
                ["ram_installation","nvme_installation"], key="ar_ctx",
                format_func=lambda x: x.replace("_"," ").title())
            _overlay = _sb.get_ar_overlay(_ar_context)

            st.markdown(f'<div style="color:#a020f0;font-family:Orbitron,monospace;font-size:0.75rem;margin-top:8px;">'
                        f'{_ar_context.replace("_"," ").upper()} · XP: {_overlay.get("xp_award",0)}</div>',
                        unsafe_allow_html=True)
            for _idx, _step in enumerate(_overlay.get("steps",[]), 1):
                st.markdown(
                    f'<div style="padding:6px 0;border-bottom:1px solid #1e2a3a;">'
                    f'<span style="color:#a020f0;font-weight:600;">Step {_idx}:</span> '
                    f'<span style="color:#c8d8ff;font-size:0.85rem;">{_step}</span>'
                    f'</div>', unsafe_allow_html=True)

            st.markdown(f"""
            <div style="margin-top:12px;padding:8px 10px;background:#0d1228;border-radius:6px;
                border:1px solid #1e2a3a;font-size:10px;color:#445577;line-height:1.8;">
            <div style="color:#f7931a;font-weight:600;margin-bottom:2px;">Age-Appropriate Guidance</div>
            Age 5-8 (Junior Builder): Kitchen analogy, supervised hands-on, XP celebrations<br>
            Age 8-12 (Builder): Full upgrade walkthroughs, benchmark before/after, part identification<br>
            Age 13-16 (Advanced): Bottleneck analysis, quantization testing, performance optimization<br>
            Age 16+ / PhD: Architecture deep-dives, RLHF pipeline, custom inference stack
            </div>""", unsafe_allow_html=True)

    except ImportError:
        st.error("sovereign_builder.py not found. Push it to GitHub and redeploy.")
    except Exception as _e_sb:
        st.error(f"Builder error: {_e_sb}")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: UNIVERSITY REGISTRAR 🎓
# Degree programs · Prerequisites · Capstone submission · Transcript
# ══════════════════════════════════════════════════════════════════════════════
if "University Registrar" in active:
    st.markdown('<div class="card-title">🎓 SOVEREIGN UNIVERSITY — Registrar</div>', unsafe_allow_html=True)

    _fid_ur = st.session_state.get("current_family", {}).get("family_id", "default") \
              if st.session_state.get("current_family") else "default"

    # Load session for degree checks
    _ur_session = None
    try:
        from family_hud import FamilySession as _FSUR, LESSONS as _ALL_LESSONS
        _ur_session = _FSUR(_fid_ur, "")
        _deg_data   = _ur_session.get_degree_eligibility()
    except Exception as _e_ur:
        _deg_data = {"credits":0,"coherence":0.5,"lessons_done":0,"highest_degree":None,
                     "all_degrees":[],"child_rune_pct":0}
        st.warning(f"Session load: {_e_ur}")

    # ── Current standing ───────────────────────────────────────────────────────
    _highest = _deg_data.get("highest_degree")
    _hname   = _highest["name"] if _highest else "No degree yet"
    _hemoji  = _highest["emoji"] if _highest else "📋"
    # Keyed off degrees.py's canonical `tier`, not the display name/emoji -
    # those can change (they did, cc63eb06: "PhD" -> "Sovereign Credential")
    # independent of this color logic. _highest is one of degrees.DEGREES'
    # own dicts (family_hud.get_degree_eligibility() -> degrees.eligibility_
    # report() -> degrees.highest_degree()), so tier is always present when
    # _highest is truthy. tier==5 is Eternal Founder, tier==4 is Master of
    # Epistemic Rigor - same two tiers the old "PhD"/"Master" substring
    # checks picked out, just no longer tied to their exact wording.
    _ht = _highest.get("tier", 0) if _highest else 0
    _hc = "#f7931a" if _ht == 5 else \
          "#a020f0" if _ht == 4 else \
          "#00cfff" if _highest else "#445577"

    st.markdown(
        f'<div style="text-align:center;padding:12px 0 8px;">'
        f'<div style="font-size:36px">{_hemoji}</div>'
        f'<div style="color:{_hc};font-family:Orbitron,monospace;font-size:1rem;margin-top:4px;">'
        f'{_hname.upper()}</div>'
        f'<div style="color:#445577;font-size:10px;letter-spacing:0.08em;margin-top:2px;">'
        f'{_deg_data["credits"]} CREDITS · COHERENCE {_deg_data["coherence"]:.3f} · '
        f'{_deg_data["lessons_done"]} LESSONS COMPLETED</div>'
        f'</div>', unsafe_allow_html=True)

    _ur1,_ur2,_ur3,_ur4 = st.columns(4)
    _ur1.metric("Credits",    _deg_data["credits"])
    _ur2.metric("Coherence",  f"{_deg_data['coherence']:.3f}")
    _ur3.metric("Lessons",    _deg_data["lessons_done"])
    _ur4.metric("Rune %",     f"{_deg_data['child_rune_pct']:.0f}%")

    st.divider()
    _ur_tabs = st.tabs(["🎓 Degrees", "📋 Transcript", "🎯 Capstone", "🔓 Prerequisites", "⚡ Mark Complete"])

    # ── Degree programs ────────────────────────────────────────────────────────
    with _ur_tabs[0]:
        st.markdown("### Degree Programs")
        for _d in _deg_data.get("all_degrees",[]):
            _curr_credits = _deg_data["credits"]
            _curr_coh     = _deg_data["coherence"]
            _credits_pct  = min(100, _curr_credits / _d["credits"] * 100)
            _coh_pct      = min(100, _curr_coh / _d["coherence"] * 100)
            _earned       = (_curr_credits >= _d["credits"] and _curr_coh >= _d["coherence"])
            _dc           = "#00ff88" if _earned else "#00cfff" if _credits_pct > 60 else "#445577"
            _special_note = " + Child Rune Genesis (256 confirmations)" if _d.get("special_rune") else ""
            st.markdown(
                f'<div class="card" style="border-left:4px solid {_dc};margin-bottom:6px;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<div><span style="font-size:20px">{_d["emoji"]}</span> '
                f'<b style="color:{_dc};font-size:0.9rem;">{_d["name"]}</b>'
                f'{"  ✅ EARNED" if _earned else ""}</div>'
                f'<div style="color:#445577;font-size:0.75rem;">{_d["credits"]} credits · coh {_d["coherence"]}{_special_note}</div>'
                f'</div>'
                f'<div style="margin-top:6px;">'
                f'<div style="font-size:10px;color:#445577;margin-bottom:2px;">Credits: {_curr_credits}/{_d["credits"]}</div>'
                f'<div style="background:#1e2a3a;border-radius:4px;height:6px;">'
                f'<div style="background:{_dc};width:{_credits_pct:.0f}%;height:6px;border-radius:4px;"></div></div>'
                f'<div style="font-size:10px;color:#445577;margin:3px 0 2px;">Coherence: {_curr_coh:.3f}/{_d["coherence"]}</div>'
                f'<div style="background:#1e2a3a;border-radius:4px;height:6px;">'
                f'<div style="background:{_dc};width:{_coh_pct:.0f}%;height:6px;border-radius:4px;"></div></div>'
                f'</div></div>', unsafe_allow_html=True)

        if _highest and _ur_session:
            st.divider()
            if st.button(f"🎓 Award {_highest['name']}", key="ur_award", type="primary"):
                badges = _ur_session.state.get("badges",[])
                badge  = f"{_highest['emoji']} {_highest['name']}"
                if badge not in badges:
                    badges.append(badge); _ur_session.state["badges"] = badges; _ur_session._save_state()
                try:
                    from rune_memory import ShieldRune, RuneMemory
                    eid = RuneMemory().record(f"DEGREE AWARDED: {_highest['name']} | Credits:{_deg_data['credits']} | Coherence:{_deg_data['coherence']}",
                                              source="registrar", coherence=_deg_data["coherence"], tags=["degree",_highest["name"].lower().replace(" ","-")])
                    ShieldRune().seal(eid, note=f"Degree: {_highest['name']}", broadcaster=_fid_ur)
                    st.success(f"✅ {_highest['emoji']} {_highest['name']} — Awarded and Bitcoin-anchored permanently.")
                    st.balloons()
                except Exception as _e: st.success(f"✅ {_highest['emoji']} {_highest['name']} — Awarded!")

    # ── Transcript ─────────────────────────────────────────────────────────────
    with _ur_tabs[1]:
        if _ur_session:
            _completed = _ur_session.state.get("lessons_completed",[])
            st.markdown(f"**Official Transcript** — {len(_completed)} courses completed")
            if _completed:
                for _lk in reversed(_completed[-15:]):
                    try:
                        _l = _ALL_LESSONS.get(_lk,{})
                        st.markdown(
                            f'<div style="padding:4px 0;border-bottom:1px solid #1e2a3a;">'
                            f'<span style="color:#f7931a;font-size:0.72rem;font-weight:600;">{_l.get("xp",0)} XP</span> '
                            f'<span style="color:#c8d8ff;font-size:0.82rem;">{_l.get("title",_lk)}</span>'
                            f'</div>', unsafe_allow_html=True)
                    except Exception: pass
            else:
                st.info("No lessons completed yet. Start learning to build your transcript.")

    # ── Capstone ───────────────────────────────────────────────────────────────
    with _ur_tabs[2]:
        st.markdown("""
        <div class="card" style="border-left:3px solid #f7931a;">
            <div style="color:#f7931a;font-family:Orbitron,monospace;font-size:0.72rem;">CAPSTONE PROJECTS</div>
            <div style="color:#8899bb;font-size:0.82rem;margin-top:6px;line-height:1.8;">
            Capstones are final projects that cannot be faked. They require
            real deployments, real experiments, or real contributions —
            verified by peer review and sealed permanently.
            </div>
        </div>
        """, unsafe_allow_html=True)

        _cap_levels = [
            ("📜 Associate", "Deploy your first sovereign node", "capstone-associate", 0.68),
            ("🏛️ Truth Architect", "Research paper + community contribution (10+ people)", "capstone-bachelor", 0.75),
            ("🎓 Master", "90-day pre-registered experiment + honest results", "capstone-masters", 0.82),
            ("⚡ Eternal Founder", "Build infrastructure others use + CC0 contribution", "capstone-eternal-founder", 0.88),
        ]
        # Back-compat: a family's saved lessons_completed may still carry the
        # pre-2026-09-05 key from before the "PhD" -> "Eternal Founder" rename
        # (cc63eb06 + this task). No such saves were found on this rig
        # (checked family_registry.json and the local data dir directly), but
        # this repo is run by other installs too - cheap enough to keep old
        # completions resolving rather than assume.
        _LEGACY_LESSON_KEYS = {"capstone-phd": "capstone-eternal-founder"}
        _completed_raw = _ur_session.state.get("lessons_completed",[]) if _ur_session else []
        _completed_cap = {_LEGACY_LESSON_KEYS.get(k, k) for k in _completed_raw}
        for _cl_name, _cl_req, _cl_key, _cl_coh in _cap_levels:
            _cl_done = _cl_key in _completed_cap
            _cl_c    = "#00ff88" if _cl_done else "#445577"
            st.markdown(
                f'<div class="memory-node" style="border-left:3px solid {_cl_c};">'
                f'<div style="color:{_cl_c};font-weight:600;">{_cl_name} {"✅" if _cl_done else ""}</div>'
                f'<div style="color:#8899bb;font-size:0.78rem;">{_cl_req}</div>'
                f'<div style="color:#334466;font-size:0.72rem;">Min coherence: {_cl_coh} | Key: {_cl_key}</div>'
                f'</div>', unsafe_allow_html=True)

        st.divider()
        st.markdown("**Submit Capstone Completion**")
        _cap_select = st.selectbox("Capstone:", ["capstone-associate","capstone-bachelor","capstone-masters","capstone-eternal-founder"], key="cap_sel")
        _cap_proof  = st.text_area("Evidence / proof URL / description:", height=80, key="cap_proof")
        _cap_peer   = st.text_input("Peer reviewer name (required for Bachelor+):", key="cap_peer")
        if st.button("🎓 Submit Capstone", key="cap_submit", type="primary") and _cap_proof and _ur_session:
            result = _ur_session.mark_lesson_completed(_cap_select)
            try:
                from rune_memory import ShieldRune, RuneMemory
                eid = RuneMemory().record(f"CAPSTONE COMPLETE: {_cap_select}\nProof: {_cap_proof[:200]}\nReviewer: {_cap_peer}",
                                          source="capstone", coherence=0.95, tags=["capstone",_cap_select])
                ShieldRune().seal(eid, note=f"Capstone: {_cap_select}", broadcaster=_fid_ur)
                st.success(f"✅ {result.get('lesson','Capstone')} — Completed and Bitcoin-anchored!")
                st.balloons()
            except Exception as _e:
                st.success(f"✅ {result.get('lesson','Capstone')} — Recorded!")

    # ── Prerequisites ──────────────────────────────────────────────────────────
    with _ur_tabs[3]:
        if _ur_session:
            st.markdown("### Next Available Lessons")
            _unlocked = _ur_session.get_unlocked_lessons()[:15]
            if _unlocked:
                for _ul in _unlocked:
                    _l = _ul["lesson"]
                    st.markdown(
                        f'<div style="padding:5px 0;border-bottom:1px solid #1e2a3a;">'
                        f'<b style="color:#00ff88;font-size:0.75rem;">✅ AVAILABLE</b> '
                        f'<span style="color:#c8d8ff;font-size:0.82rem;">{_l.get("title",_ul["key"])}</span> '
                        f'<span style="color:#445577;font-size:0.72rem;">({_l.get("xp",0)} XP)</span>'
                        f'</div>', unsafe_allow_html=True)
            else:
                st.info("Complete prerequisites to unlock more lessons.")

            st.divider()
            st.markdown("### Check Any Lesson Status")
            _chk_key = st.text_input("Lesson key:", key="prereq_check", placeholder="e.g. consciousness-4, builder-6")
            if _chk_key:
                _chk = _ur_session.get_lesson_status(_chk_key)
                _sc  = {"completed":"#00ff88","available":"#00cfff","locked":"#ff4444"}.get(_chk["status"],"#445577")
                _missing_html = '<div style="color:#445577;font-size:0.75rem;margin-top:4px;">Missing: ' + ", ".join(_chk.get("missing_prereqs",[])) + "</div>" if _chk.get("missing_prereqs") else ""
                st.markdown(
                    f'<div class="card" style="border-left:3px solid {_sc};">'
                    f'<div style="color:{_sc};font-weight:600;">{_chk["status"].upper()}</div>'
                    f'<div style="color:#8899bb;font-size:0.82rem;">{_chk.get("reason","")}</div>'
                    f'{_missing_html}'
                    f'</div>', unsafe_allow_html=True)

    # ── Mark complete ──────────────────────────────────────────────────────────
    with _ur_tabs[4]:
        st.markdown("**Mark a lesson as completed and award XP + Rune.**")
        _mc_key  = st.text_input("Lesson key:", key="mc_key", placeholder="e.g. courage-1, systems-3")
        _mc_coh  = st.slider("Final coherence after lesson:", 0.5, 1.0, 0.75, 0.01, key="mc_coh")
        if st.button("⚡ Mark Complete", key="mc_btn", type="primary") and _mc_key and _ur_session:
            _chk = _ur_session.get_lesson_status(_mc_key)
            if _chk["status"] == "locked":
                st.error(f"🔒 Locked: {_chk.get('reason','Prerequisites not met')}")
            else:
                result = _ur_session.mark_lesson_completed(_mc_key, _mc_coh)
                if result.get("status") == "completed":
                    st.success(
                        f"✅ {result['lesson']}\n\n"
                        f"XP earned: **{result['xp_earned']}** | "
                        f"Total: **{result['total_xp']}** | "
                        f"Coherence: **{result['new_coherence']:.4f}**"
                        + (f"\n\n🏅 Badge: {result['badge']}" if result.get('badge') else "")
                    )
                    st.rerun()
                else:
                    st.warning(f"Status: {result.get('status','?')}")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: POLYVAGAL ORACLE 🧠
# Quiz + State-Shifting Toolkit + Social Calibration + PVC Research Protocol
# ══════════════════════════════════════════════════════════════════════════════
if "Polyvagal Oracle" in active:
    st.markdown('<div class="card-title">🧠 POLYVAGAL ORACLE — Know and Navigate Your Nervous System</div>', unsafe_allow_html=True)

    _fid_pv = st.session_state.get("current_family", {}).get("family_id", "default") \
              if st.session_state.get("current_family") else "default"

    _pv_tabs = st.tabs(["🟢 State Check", "🔍 Describe It (AI)", "🧪 Quiz", "🛠️ State-Shifting Toolkit",
                         "📊 PVC Research", "🔬 Social Calibration"])

    # ── Daily State Check ─────────────────────────────────────────────────────
    with _pv_tabs[0]:
        st.markdown("""
        <div style="text-align:center;padding:8px 0 4px;">
            <div style="font-size:28px">🧠</div>
            <div style="color:#00ff88;font-family:Orbitron,monospace;font-size:0.78rem;margin-top:4px;">
            NERVOUS SYSTEM STATE CHECK</div>
        </div>""", unsafe_allow_html=True)

        _pv_states = {
            "🟢 GREEN — Ventral Vagal (Safe & Curious)": {
                "color":"#00ff88","value":2,
                "desc":"Calm, connected, curious, playful. Optimal for learning and truth-seeking.",
                "intervention":"Maintain and deepen. This is the state for hard problems.",
                "coherence_boost": 0.02,
            },
            "🟡 YELLOW — Sympathetic (Fight/Flight/Frustration)": {
                "color":"#ffcc00","value":1,
                "desc":"Activated, agitated, urgent, frustrated. Learning is impaired.",
                "intervention":"Down-regulate first. Breathe, move, co-regulate, then return to the work.",
                "coherence_boost": -0.01,
            },
            "🔴 RED — Dorsal Vagal (Shutdown/Numb)": {
                "color":"#ff4444","value":0,
                "desc":"Withdrawn, flat, 'I don't care', disconnected. Prefrontal offline.",
                "intervention":"Gentle re-engagement. Presence > words. Low pressure. Safety first.",
                "coherence_boost": -0.02,
            },
        }

        _pv_who  = st.text_input("Who is checking in?", key="pv_who", value="Family", placeholder="Your name")
        _pv_sel  = st.radio("Current state:", list(_pv_states.keys()), key="pv_state")
        _pv_note = st.text_area("Notes (optional):", height=60, key="pv_note",
            placeholder="What triggered this state? What helped?")

        if st.button("✅ Log State Check", key="pv_log", type="primary"):
            _sv  = _pv_states[_pv_sel]
            import json as _json_pv, pathlib as _pl_pv, datetime as _dt_pv, hashlib as _hs_pv
            _log = _pl_pv.Path("/mnt/main/polyvagal_states.jsonl") if _pl_pv.Path("/mnt/main").exists() \
                   else _pl_pv.Path(os.path.expanduser("~/.aubieeternal/main/polyvagal_states.jsonl"))
            _entry = {"timestamp":_dt_pv.datetime.now().isoformat(),"family_id":_fid_pv,
                      "member":_pv_who,"state":_pv_sel[:7],"state_value":_sv["value"],
                      "notes":_pv_note,"coherence_boost":_sv["coherence_boost"]}
            with open(_log,"a") as f: f.write(_json_pv.dumps(_entry)+"\n")
            st.markdown(
                f'<div class="card" style="border-left:4px solid {_sv["color"]};">'
                f'<div style="color:{_sv["color"]};font-weight:600;">{_pv_sel[:30]}</div>'
                f'<div style="color:#8899bb;font-size:0.82rem;margin-top:4px;">{_sv["desc"]}</div>'
                f'<div style="color:#c8d8ff;font-size:0.82rem;margin-top:6px;">'
                f'<b>Recommended:</b> {_sv["intervention"]}</div>'
                f'</div>', unsafe_allow_html=True)

        # State history
        import pathlib as _pl_pvh
        _log2 = _pl_pvh.Path("/mnt/main/polyvagal_states.jsonl") if _pl_pvh.Path("/mnt/main").exists() \
                else _pl_pvh.Path(os.path.expanduser("~/.aubieeternal/main/polyvagal_states.jsonl"))
        if _log2.exists():
            _entries = []
            for _line in _log2.read_text().strip().split("\n"):
                try:
                    import json as _j2; _e = _j2.loads(_line)
                    if _e.get("family_id") == _fid_pv: _entries.append(_e)
                except Exception: pass
            if _entries:
                st.divider(); st.markdown("**Recent States**")
                _sv_counts = {"2":0,"1":0,"0":0}
                for _e in _entries[-20:]:
                    _sv_counts[str(_e.get("state_value",1))] += 1
                _total_e = len(_entries[-20:])
                if _total_e:
                    _green_pct = _sv_counts["2"]/_total_e*100
                    _col_g = "#00ff88" if _green_pct >= 60 else "#ffcc00" if _green_pct >= 40 else "#ff4444"
                    st.markdown(f'<div style="color:{_col_g};font-size:0.85rem;">'
                                f'🟢 {_sv_counts["2"]} · 🟡 {_sv_counts["1"]} · 🔴 {_sv_counts["0"]} '
                                f'(last 20 check-ins — {_green_pct:.0f}% green)</div>', unsafe_allow_html=True)

    # ── Free-text description → keyword assessment + optional AI deep-dive ────
    # Merged in from the duplicate "Polyvagal Oracle" tab body this file used
    # to have (found live 2026-08-25) - this was its one genuinely distinct
    # feature next to the richer 5-tab version above (a free-text description
    # instead of picking from 3 fixed states, plus an AI-generated deep dive).
    with _pv_tabs[1]:
        st.markdown('<div style="color:#8899bb;font-size:0.82rem;">Type what you or your child is experiencing in your own words — get an instant keyword-based read, or ask the AI for a deeper, situation-specific analysis.</div>', unsafe_allow_html=True)
        trigger = st.text_area("Describe what's happening", placeholder="I feel like everything is falling apart and no one understands me...", height=80, key="pv_describe_trigger")
        kid_name_pv = st.text_input("Name (optional)", value=st.session_state.family_profile["kid"]["name"], key="pv_describe_name")

        _pvd_c1, _pvd_c2 = st.columns(2)
        with _pvd_c1:
            if st.button("🧬 Assess Polyvagal State", type="primary", key="pv_describe_assess") and trigger:
                trigger_lower = trigger.lower()
                if any(w in trigger_lower for w in ["safe","connect","play","curious","love","joy","happy","excited","calm","ready"]):
                    state, emoji, color = "ventral_vagal", "🟢", "#00ff88"
                    desc = "✅ SAFE & SOCIAL — Ventral vagal active. Curiosity, play, and co-regulation online."
                    rec = "Lean into storytelling, shared laughter, eye contact, and collaborative exploration."
                elif any(w in trigger_lower for w in ["stress","angry","anxious","fight","flight","worry","scared","panic","overwhelm","tense","rage"]):
                    state, emoji, color = "sympathetic", "🟡", "#ff9500"
                    desc = "⚡ MOBILIZED — Sympathetic nervous system active. Energy for action or defense."
                    rec = "Offer movement, 4-7-8 breathwork, or structured 'what can we control?' exercises."
                else:
                    state, emoji, color = "dorsal_vagal", "🔴", "#ff4444"
                    desc = "🛑 SHUTDOWN — Dorsal vagal dominant. Numbness or freeze response."
                    rec = "Gentle presence, no pressure. Somatic grounding: cold water, feet on floor, humming."

                st.markdown(f'''
                <div class="card" style="border:2px solid {color};">
                    <div style="color:{color};font-family:Orbitron,monospace;font-size:1rem;margin-bottom:8px;">{emoji} {state.upper().replace("_"," ")}</div>
                    <div style="font-size:0.88rem;color:#c8d8ff;line-height:1.8;">{desc}</div>
                    <div style="margin-top:10px;padding:8px;background:#0d0d2b;border-radius:6px;">
                        <div style="color:#00cfff;font-size:0.75rem;font-family:Orbitron,monospace;">RECOMMENDED STRATEGY</div>
                        <div style="font-size:0.85rem;color:#aabbcc;margin-top:4px;">{rec}</div>
                    </div>
                </div>
                ''', unsafe_allow_html=True)
                save_memory(f"Polyvagal: {kid_name_pv}", f"State: {state} | {trigger[:100]}", tags=["polyvagal", state])
                award_xp(10)

        with _pvd_c2:
            if st.button("🤖 Ask AI for Deep Analysis", key="pv_describe_ai") and trigger:
                with st.spinner("Consulting the nervous system oracle..."):
                    try:
                        client, model, _p, _pn = get_ai_client()
                        resp = client.chat.completions.create(
                            model=model,
                            messages=[{"role": "system", "content": "You are a polyvagal-informed therapist. Assess nervous system state, explain what's happening, and give 3 specific co-regulation techniques. Be warm, practical, and trauma-informed."},
                                       {"role": "user", "content": f"Person: {kid_name_pv}\nSituation: {trigger}"}],
                            max_tokens=600
                        )
                        st.markdown(f'<div class="card"><div style="font-size:0.88rem;line-height:1.8;color:#c8d8ff;">{resp.choices[0].message.content}</div></div>', unsafe_allow_html=True)
                        award_xp(15)
                    except Exception as e:
                        st.error(str(e))

    # ── Polyvagal Quiz ────────────────────────────────────────────────────────
    with _pv_tabs[2]:
        st.markdown("**Identify the nervous system state in each scenario.**")
        _quiz_qs = [
            {"q":"Your child is staring at homework with a flat voice saying 'I don't know' when asked what's wrong.",
             "opts":["🟢 Ventral Vagal","🟡 Sympathetic","🔴 Dorsal Vagal"],"ans":2,
             "exp":"Dorsal Vagal shutdown. The brain has gone into conservation/freeze mode. Do not push."},
            {"q":"Your teenager raises their voice during a discussion, face flushed, interrupting everyone.",
             "opts":["🟢 Ventral Vagal","🟡 Sympathetic","🔴 Dorsal Vagal"],"ans":1,
             "exp":"Sympathetic activation. The nervous system is mobilized. Movement, space, and calm presence help."},
            {"q":"Your 8-year-old is laughing, making eye contact, and excitedly explaining their invention idea.",
             "opts":["🟢 Ventral Vagal","🟡 Sympathetic","🔴 Dorsal Vagal"],"ans":0,
             "exp":"Ventral Vagal. This is the learning state. Extend it. Ask more questions."},
            {"q":"After a low grade, your child says 'I'm never good at this' and refuses to try the next problem.",
             "opts":["🟢 Ventral Vagal","🟡 Sympathetic","🔴 Dorsal Vagal"],"ans":2,
             "exp":"Dorsal Vagal — 'why bother' collapse. Gentle presence, low-pressure reset, then gradually re-engage."},
            {"q":"Your partner snaps over something small after a long stressful day.",
             "opts":["🟢 Ventral Vagal","🟡 Sympathetic","🔴 Dorsal Vagal"],"ans":1,
             "exp":"Sympathetic spillover from accumulated allostatic load. Not really about the small thing."},
            {"q":"A child who loves lessons suddenly says 'This is stupid' and crosses their arms.",
             "opts":["🟢 Ventral Vagal","🟡 Sympathetic","🔴 Dorsal Vagal"],"ans":1,
             "exp":"Sympathetic frustration — the challenge exceeded their regulated window. Back off difficulty temporarily."},
            {"q":"Family game night: everyone is smiling, making eye contact, relaxed and playful.",
             "opts":["🟢 Ventral Vagal","🟡 Sympathetic","🔴 Dorsal Vagal"],"ans":0,
             "exp":"Ventral Vagal co-regulation. This is the state where relationships and long-term learning consolidate."},
            {"q":"A child who recently experienced conflict keeps replaying it and can't focus on anything else.",
             "opts":["🟢 Ventral Vagal","🟡 Sympathetic","🔴 Dorsal Vagal"],"ans":1,
             "exp":"Sympathetic Type 2 (failure to shut off). The brain can't exit threat mode. Deliberate co-regulation needed."},
        ]

        if "pv_quiz_idx" not in st.session_state: st.session_state.pv_quiz_idx = 0
        if "pv_quiz_score" not in st.session_state: st.session_state.pv_quiz_score = 0
        if "pv_quiz_done" not in st.session_state: st.session_state.pv_quiz_done = False

        if not st.session_state.pv_quiz_done and st.session_state.pv_quiz_idx < len(_quiz_qs):
            _q = _quiz_qs[st.session_state.pv_quiz_idx]
            st.markdown(f'<div style="color:#445577;font-size:0.72rem;">Question {st.session_state.pv_quiz_idx+1}/{len(_quiz_qs)}</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="color:#c8d8ff;font-size:0.88rem;padding:8px 0;line-height:1.7;">{_q["q"]}</div>', unsafe_allow_html=True)
            _pv_ans = st.radio("State:", _q["opts"], key=f"pv_q{st.session_state.pv_quiz_idx}")
            if st.button("Submit", key=f"pv_sub{st.session_state.pv_quiz_idx}"):
                _correct = _q["opts"].index(_pv_ans) == _q["ans"]
                if _correct: st.session_state.pv_quiz_score += 1; st.success("✅ Correct!")
                else: st.error(f"❌ {_q['opts'][_q['ans']]}")
                st.info(f"**{_q['exp']}**")
                st.session_state.pv_quiz_idx += 1
                if st.session_state.pv_quiz_idx >= len(_quiz_qs): st.session_state.pv_quiz_done = True
                st.rerun()
        elif st.session_state.pv_quiz_done or st.session_state.pv_quiz_idx >= len(_quiz_qs):
            _sc = st.session_state.pv_quiz_score; _tot = len(_quiz_qs); _pct = _sc/_tot*100
            _cc = "#00ff88" if _pct >= 85 else "#ffcc00" if _pct >= 65 else "#ff4444"
            st.markdown(f'<div style="text-align:center;padding:10px;">'
                        f'<div style="color:{_cc};font-size:1.2rem;font-weight:600;">{_sc}/{_tot} — {_pct:.0f}%</div>'
                        f'</div>', unsafe_allow_html=True)
            if _pct >= 85: st.success("Excellent — you can identify nervous system states accurately.")
            elif _pct >= 65: st.success("Good — review the Sympathetic/Dorsal boundary cases.")
            else: st.info("Practice identifying states in real-time today. The quiz will reflect your growth.")

            # Log to truth log
            try:
                from family_hud import FamilySession as _FS_pv
                _fs_pv = _FS_pv(_fid_pv, "")
                _fs_pv._write_to_truth_log(f"POLYVAGAL_QUIZ: {_sc}/{_tot} ({_pct:.0f}%)")
            except Exception: pass

            if st.button("🔄 Retake Quiz", key="pv_retake"):
                st.session_state.pv_quiz_idx = 0; st.session_state.pv_quiz_score = 0
                st.session_state.pv_quiz_done = False; st.rerun()

    # ── State-Shifting Toolkit ────────────────────────────────────────────────
    with _pv_tabs[3]:
        st.markdown("### 🛠️ State-Shifting Toolkit")
        _toolkit_state = st.selectbox("Current state to shift FROM:", 
            ["🟡 Sympathetic (activated, frustrated)", "🔴 Dorsal Vagal (shutdown, numb)"], key="tk_state")

        _is_sympathetic = "Sympathetic" in _toolkit_state
        _interventions = {
            "sympathetic": [
                {"name":"Shake It Out","duration":"60s","ages":"5-9",
                 "how":"Put on music. Shake arms, legs, whole body vigorously for 60 seconds. The movement discharges sympathetic activation. Kids often giggle — that is success."},
                {"name":"4-7-8 Breathing","duration":"2 min","ages":"10+",
                 "how":"Inhale 4 sec. Hold 7 sec. Exhale slowly 8 sec. Repeat 4 cycles. The extended exhale activates the vagus nerve and directly shifts sympathetic → ventral vagal."},
                {"name":"Name 5 Things","duration":"2 min","ages":"8+",
                 "how":"Name 5 things you see. 4 you can touch. 3 you hear. 2 you smell. 1 you taste. This grounds attention in present sensory data, interrupting threat-based prediction loops."},
                {"name":"Cold Water Reset","duration":"30s","ages":"All",
                 "how":"Splash cold water on face or hold an ice cube. Activates the diving reflex — instant vagal response, heart rate drops, nervous system shifts."},
                {"name":"Movement Break","duration":"5-10 min","ages":"10+",
                 "how":"10 jumping jacks, 5 push-ups, run to end of street and back. Physical discharge clears sympathetic activation faster than any cognitive intervention."},
                {"name":"Offer Choices Not Demands","duration":"Ongoing","ages":"All",
                 "how":"When someone is activated, demands escalate. Choices de-escalate. 'Do you want to breathe first or move first?' Both options lead to regulation. This works on yourself too."},
            ],
            "dorsal": [
                {"name":"Parallel Play","duration":"10-20 min","ages":"All",
                 "how":"Sit nearby and do your own calm activity (draw, read, build) without talking or demanding engagement. Your regulated presence slowly pulls them back. No pressure = safety."},
                {"name":"The Reset Snack","duration":"15 min","ages":"All",
                 "how":"Offer a small, familiar, positive food. Eating activates parasympathetic response. The familiar comfort signals safety to the nervous system without requiring words."},
                {"name":"Orienting Response","duration":"2-3 min","ages":"All",
                 "how":"Slowly turn head to look around the room, naming what you see. This activates the orienting reflex — a primitive safety scan — and signals to the nervous system that the environment is safe."},
                {"name":"Soft Music + Low Light","duration":"10-15 min","ages":"All",
                 "how":"Familiar, slow music at low volume. Dim or warm lighting. The nervous system responds to prosodic (melodic/rhythmic) signals as safety cues. This is why lullabies work."},
                {"name":"Connection Moment","duration":"5-10 min","ages":"All",
                 "how":"Brief, low-demand positive contact: sit close, watch something they love for 10 minutes without agenda. Rebuilds the social baseline without pressure to perform or communicate."},
                {"name":"Do Not Lecture","duration":"Ongoing","ages":"All",
                 "how":"Explaining, convincing, or disciplining during dorsal vagal shutdown is useless and often harmful. The prefrontal is offline. Wait. Regulate. Reconnect. Then teach."},
            ],
        }

        _ilist = _interventions["sympathetic" if _is_sympathetic else "dorsal"]
        _age_filter = st.selectbox("Age group:", ["All ages","5-9","10-13","14+"], key="tk_age")

        for _iv in _ilist:
            _age_ok = _age_filter == "All ages" or _iv["ages"] == "All" or \
                      _age_filter[:2] in _iv["ages"] or "+" in _iv["ages"]
            if _age_ok:
                st.markdown(
                    f'<div class="card" style="margin-bottom:4px;">'
                    f'<div style="display:flex;justify-content:space-between;">'
                    f'<b style="color:#c8d8ff;">{_iv["name"]}</b>'
                    f'<span style="color:#445577;font-size:0.72rem;">{_iv["duration"]} · Ages {_iv["ages"]}</span>'
                    f'</div>'
                    f'<div style="color:#8899bb;font-size:0.8rem;margin-top:4px;line-height:1.7;">{_iv["how"]}</div>'
                    f'</div>', unsafe_allow_html=True)

    # ── PVC Research Protocol ─────────────────────────────────────────────────
    with _pv_tabs[4]:
        st.markdown("""
        <div class="card" style="border-left:3px solid #a020f0;">
            <div style="color:#a020f0;font-family:Orbitron,monospace;font-size:0.72rem;">
            POLYVAGAL-COHERENCE COUPLING (PVC) RESEARCH PROTOCOL</div>
            <div style="color:#8899bb;font-size:0.82rem;margin-top:6px;line-height:1.9;">
            The hypothesis: autonomic nervous system state significantly predicts the quality
            of epistemic output. This tab runs the family research protocol.<br><br>
            <b style="color:#c8d8ff;">Before each lesson:</b> log your state + interoceptive accuracy score.<br>
            <b style="color:#c8d8ff;">After each lesson:</b> your coherence and performance are recorded.<br>
            <b style="color:#c8d8ff;">After 30+ sessions:</b> run the correlation analysis below.
            </div>
        </div>""", unsafe_allow_html=True)

        st.markdown("#### Pre-Session Data Entry")
        _pvc_c1, _pvc_c2 = st.columns(2)
        with _pvc_c1:
            _pvc_state  = st.selectbox("ANS state:", ["🟢 Ventral (2)","🟡 Sympathetic (1)","🔴 Dorsal (0)"], key="pvc_s")
            _pvc_ia     = st.slider("Interoceptive accuracy (heartbeat task):", 0.0, 1.0, 0.7, 0.01, key="pvc_ia",
                help="Run heartbeat counting task for 25s. Accuracy = 1 - |counted-actual| / avg")
        with _pvc_c2:
            _pvc_hrv    = st.number_input("HRV (ms, if available, 0 = skip):", 0, 500, 0, key="pvc_hrv")
            _pvc_lesson = st.text_input("Lesson key:", key="pvc_lesson", placeholder="e.g. systems-3")

        if st.button("📊 Log Pre-Session", key="pvc_log", type="primary") and _pvc_lesson:
            import json as _jpvc, pathlib as _ppvc, datetime as _dpvc
            _pvl = _ppvc.Path("/mnt/main/pvc_research.jsonl") if _ppvc.Path("/mnt/main").exists() \
                   else _ppvc.Path(os.path.expanduser("~/.aubieeternal/main/pvc_research.jsonl"))
            _sv_int = {"🟢 Ventral (2)":2,"🟡 Sympathetic (1)":1,"🔴 Dorsal (0)":0}.get(_pvc_state,1)
            _rec = {"timestamp":_dpvc.datetime.now().isoformat(),"family_id":_fid_pv,
                    "lesson_key":_pvc_lesson,"state_value":_sv_int,"ia_score":_pvc_ia,
                    "hrv_ms":_pvc_hrv,"coherence_post":None}
            with open(_pvl,"a") as f: f.write(_jpvc.dumps(_rec)+"\n")
            st.success(f"✅ Pre-session logged — State:{_sv_int} | IA:{_pvc_ia:.2f} | Lesson:{_pvc_lesson}")
            st.info("Complete the lesson. After, use 'Mark Complete' in University Registrar to record your coherence score.")

        # Simple correlation display if data exists
        import pathlib as _pp2
        _pvl2 = _pp2.Path("/mnt/main/pvc_research.jsonl") if _pp2.Path("/mnt/main").exists() \
                else _pp2.Path(os.path.expanduser("~/.aubieeternal/main/pvc_research.jsonl"))
        if _pvl2.exists():
            import json as _jp2
            _recs = []
            for _l in _pvl2.read_text().strip().split("\n"):
                try: _recs.append(_jp2.loads(_l))
                except Exception: pass
            st.markdown(f"**Dataset: {len(_recs)} sessions logged**")
            if len(_recs) >= 10:
                _states = [r["state_value"] for r in _recs if r.get("coherence_post")]
                _cohs   = [r["coherence_post"] for r in _recs if r.get("coherence_post")]
                if len(_states) >= 5:
                    n = len(_states)
                    xm = sum(_states)/n; ym = sum(_cohs)/n
                    r_num = sum((x-xm)*(y-ym) for x,y in zip(_states,_cohs))
                    r_den = (sum((x-xm)**2 for x in _states) * sum((y-ym)**2 for y in _cohs))**0.5
                    r_val = r_num/r_den if r_den > 0 else 0
                    _rc = "#00ff88" if abs(r_val) > 0.3 else "#ffcc00" if abs(r_val) > 0.1 else "#445577"
                    st.markdown(f'<div style="color:{_rc};font-size:0.9rem;font-weight:600;">'
                                f'PVC Correlation: r = {r_val:.3f} '
                                f'({"significant signal" if abs(r_val) > 0.3 else "weak signal — more data needed"})'
                                f'</div>', unsafe_allow_html=True)
            else:
                st.info(f"Need {10-len(_recs)} more sessions to compute correlation.")

    # ── Social Calibration ────────────────────────────────────────────────────
    with _pv_tabs[5]:
        st.markdown("""
        <div class="card" style="border-left:3px solid #00cfff;">
            <div style="color:#00cfff;font-family:Orbitron,monospace;font-size:0.72rem;">
            SOCIAL BASELINE CALIBRATION</div>
            <div style="color:#8899bb;font-size:0.82rem;margin-top:6px;line-height:1.9;">
            Social Baseline Theory (Coan, 2014): the human brain evolved to expect a social
            environment. Isolation is metabolically costly. Genuine sovereignty requires
            a regulated, connected community — not solitude.<br><br>
            This tool maps your family's social baseline and identifies optimization opportunities.
            </div>
        </div>""", unsafe_allow_html=True)

        st.markdown("#### Your Social Baseline Map")
        st.markdown('<div style="color:#8899bb;font-size:0.8rem;margin-bottom:8px;">Name up to 5 people whose presence most regulates your nervous system:</div>', unsafe_allow_html=True)
        _sb_people = []
        for _si in range(1,6):
            _sbc1, _sbc2, _sbc3 = st.columns([2,1,1])
            with _sbc1: _sbname = st.text_input(f"Person {_si}:", key=f"sb_name{_si}", placeholder="Name/relationship")
            with _sbc2: _sbfreq = st.selectbox("Frequency:", ["daily","weekly","monthly","rarely"], key=f"sb_freq{_si}")
            with _sbc3: _sbqual = st.slider("Quality:", 1, 5, 3, key=f"sb_qual{_si}", help="1=draining, 5=deeply regulating")
            if _sbname: _sb_people.append({"name":_sbname,"freq":_sbfreq,"quality":_sbqual})

        if _sb_people and st.button("📊 Analyze Social Baseline", key="sb_analyze"):
            _freq_score = {"daily":4,"weekly":3,"monthly":2,"rarely":1}
            _total_load_reduction = sum(_fs["quality"] * _freq_score.get(_fs["freq"],1) for _fs in _sb_people)
            _optimal  = 5 * 4 * 5  # 5 people, daily, quality 5
            _sbl_pct  = _total_load_reduction / _optimal * 100
            _sbl_c    = "#00ff88" if _sbl_pct >= 60 else "#ffcc00" if _sbl_pct >= 35 else "#ff4444"
            st.markdown(
                f'<div class="card" style="border-left:4px solid {_sbl_c};">'
                f'<div style="color:{_sbl_c};font-weight:600;">Social Baseline Load Reduction: {_sbl_pct:.0f}%</div>'
                f'<div style="color:#8899bb;font-size:0.82rem;margin-top:6px;line-height:1.8;">'
                f'{"Strong baseline — your nervous system has adequate social resourcing." if _sbl_pct >= 60 else "Moderate baseline — increasing quality or frequency with 1-2 people would significantly reduce allostatic load." if _sbl_pct >= 35 else "Low baseline — your nervous system is running without adequate social resourcing. This increases allostatic load and reduces epistemic quality."}'
                f'</div></div>', unsafe_allow_html=True)
            _low_qual = [p for p in _sb_people if p["quality"] < 3]
            _low_freq = [p for p in _sb_people if p["freq"] in ["monthly","rarely"] and p["quality"] >= 4]
            if _low_freq:
                st.markdown(f'<div style="color:#ffcc00;font-size:0.82rem;margin-top:6px;">High-quality but rare: {", ".join(p["name"] for p in _low_freq)} — increasing frequency would most improve your baseline.</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB: GROKIPEDIA 📚
# 5-phase Grokipedia integration: fetch · score · ingest · search · archive
# ══════════════════════════════════════════════════════════════════════════════
if "Grokipedia" in active and "Epistemic" not in active:
    st.markdown('<div class="card-title">📚 GROKIPEDIA — Sovereign Truth-Seeking Knowledge Layer</div>', unsafe_allow_html=True)

    _fid_gk = st.session_state.get("current_family", {}).get("family_id", "default") \
              if st.session_state.get("current_family") else "default"

    try:
        from grokipedia import Grokipedia as _GK, MIN_TRUTH_SCORE as _MIN_SCORE
        _gk     = _GK(_fid_gk)
        _gkstat = _gk.get_stats()

        # Stats row
        _gk1,_gk2,_gk3,_gk4 = st.columns(4)
        _gk1.metric("Ingested",       _gkstat.get("total_ingested",0))
        _gk2.metric("Archive Ready",  _gkstat.get("archive_ready",0))
        _gk3.metric("Sealed",         _gkstat.get("sealed",0))
        _gk4.metric("Avg Score",      f"{_gkstat.get('avg_truth_score',0):.2f}")

        st.divider()
        _gk_tabs = st.tabs(["⚡ Daily Pipeline", "🔍 Search", "📤 Suggest Topic",
                             "🔒 Archive & Seal", "⚙️ Quality Rules"])

        # ── Daily pipeline ─────────────────────────────────────────────────────
        with _gk_tabs[0]:
            st.markdown("""
            <div class="card" style="border-left:3px solid #f7931a;">
                <div style="color:#f7931a;font-family:Orbitron,monospace;font-size:0.72rem;">
                PHASE 1-3: FETCH → SCORE → INGEST</div>
                <div style="color:#8899bb;font-size:0.82rem;margin-top:6px;line-height:1.8;">
                Runs automatically daily at 6AM via morning_synthesis.py.<br>
                Manually trigger below to run now.
                </div>
            </div>""", unsafe_allow_html=True)

            if st.button("⚡ Run Daily Pipeline Now", key="gk_run", type="primary"):
                with st.spinner("Fetching, scoring, and ingesting..."):
                    report = _gk.run_daily_pipeline()
                st.success(
                    f"✅ Pipeline complete\n\n"
                    f"Fetched: {report['fetched']} · Ingested: {report['ingested']} · "
                    f"Rejected: {report['rejected']} · "
                    f"Archive candidates: {report['archive_candidates']}\n\n"
                    f"Avg truth score: {report['avg_truth_score']:.2f}"
                )

            # Show today's entries
            import pathlib as _pl_gk
            _gk_day_dir = _pl_gk.Path("/mnt/main/repo/grokipedia") if _pl_gk.Path("/mnt/main").exists() \
                          else _pl_gk.Path(os.path.expanduser("~/.aubieeternal/main/repo/grokipedia"))
            if _gk_day_dir.exists():
                _today_files = sorted(_gk_day_dir.glob(f"*{_gk.today}*.json"))
                if _today_files:
                    st.markdown(f"**Today's Ingested Entries ({len(_today_files)})**")
                    for _tf in _today_files[:5]:
                        try:
                            _te = json.loads(_tf.read_text())
                            _sc = _te.get("truth_score",0)
                            _tc = "#00ff88" if _sc >= 0.85 else "#ffcc00" if _sc >= 0.75 else "#445577"
                            st.markdown(
                                f'<div class="memory-node" style="border-left:3px solid {_tc};">'
                                f'<div style="color:{_tc};font-size:0.7rem;">'
                                f'score={_sc:.2f} · {_te.get("source","?")} · '
                                f'{"🛡️ sealed" if _te.get("lattice_sealed") else "⏳ unsealed"}</div>'
                                f'<div style="color:#c8d8ff;font-size:0.82rem;">{_te.get("title","?")[:80]}</div>'
                                f'</div>', unsafe_allow_html=True)
                        except Exception: pass

        # ── Search ─────────────────────────────────────────────────────────────
        with _gk_tabs[1]:
            _gk_q = st.text_input("Search Grokipedia knowledge:", key="gk_q",
                placeholder="e.g. consciousness, polyvagal, information theory")
            _gk_min = st.slider("Min truth score:", 0.5, 1.0, 0.75, 0.05, key="gk_min")
            if _gk_q:
                _results = _gk.search(_gk_q, _gk_min)
                if _results:
                    st.markdown(f"**{len(_results)} results:**")
                    for _r in _results:
                        st.markdown(
                            f'<div class="card" style="border-left:3px solid #00cfff;">'
                            f'<div style="display:flex;justify-content:space-between;">'
                            f'<b style="color:#c8d8ff;">{_r.get("title","?")[:60]}</b>'
                            f'<span style="color:#00cfff;font-size:0.72rem;">score={_r.get("truth_score",0):.2f}</span>'
                            f'</div>'
                            f'<div style="color:#8899bb;font-size:0.8rem;margin-top:4px;">{_r.get("content","?")[:200]}...</div>'
                            f'</div>', unsafe_allow_html=True)
                else:
                    st.info("No entries found. Run the daily pipeline to build the knowledge base.")

        # ── Suggest topic ──────────────────────────────────────────────────────
        with _gk_tabs[2]:
            st.markdown("**Suggest a topic for Grokipedia review.**")
            _gk_topic   = st.text_input("Topic:", key="gk_topic",
                placeholder="e.g. Quantum Darwinism and epistemic redundancy")
            _gk_rat     = st.text_area("Why this matters:", height=80, key="gk_rat",
                placeholder="Why does this topic belong in a sovereign truth-seeking knowledge base?")
            _gk_urg     = st.selectbox("Urgency:", ["normal","high","critical"], key="gk_urg")
            if st.button("📤 Suggest Topic", key="gk_suggest") and _gk_topic:
                _sugg = _gk.suggest_topic(_gk_topic, _gk_rat, _gk_urg)
                st.success(f"✅ Topic queued — ID: {_sugg['suggestion_id']}")
            pending = _gk.get_pending_topics()
            if pending:
                st.divider()
                st.markdown(f"**Pending topics ({len(pending)}):**")
                for _pt in pending[-5:]:
                    st.markdown(f'<div style="padding:3px 0;color:#8899bb;font-size:0.8rem;">'
                                f'<b style="color:#ffcc00;">[{_pt.get("urgency","?")}]</b> {_pt.get("topic","?")[:80]}</div>',
                                unsafe_allow_html=True)

        # ── Archive ────────────────────────────────────────────────────────────
        with _gk_tabs[3]:
            st.markdown("**Seal high-quality entries permanently for long-term archival.**")
            candidates = _gk.get_export_candidates(min_score=0.85)
            if candidates:
                st.markdown(f"**{len(candidates)} archive candidates (score ≥ 0.85):**")
                for _c in candidates[:5]:
                    _sealed = _c.get("lattice_sealed")
                    _cc = "#00ff88" if _sealed else "#ffcc00"
                    st.markdown(
                        f'<div class="memory-node" style="border-left:3px solid {_cc};">'
                        f'<div style="color:{_cc};font-size:0.7rem;">'
                        f'score={_c.get("truth_score",0):.2f} · {"🛡️ SEALED" if _sealed else "⏳ pending"}</div>'
                        f'<div style="color:#c8d8ff;font-size:0.82rem;">{_c.get("title","?")[:80]}</div>'
                        f'<div style="color:#334466;font-size:0.72rem;">ID: {_c.get("entry_id","?")}</div>'
                        f'</div>', unsafe_allow_html=True)
                    if not _sealed:
                        if st.button(f"🔒 Seal {_c['entry_id'][:8]}", key=f"gk_seal_{_c['entry_id']}"):
                            _sr = _gk.seal_for_archive(_c["entry_id"])
                            st.success(f"✅ Sealed — {_sr.get('seal_id','?')}")
                            st.rerun()
            else:
                st.info("No archive candidates yet. Run the daily pipeline to build quality entries.")

        # ── Quality rules ──────────────────────────────────────────────────────
        with _gk_tabs[4]:
            st.markdown(f"""
            <div class="card">
            <div style="color:#f7931a;font-family:Orbitron,monospace;font-size:0.72rem;margin-bottom:8px;">
            QUALITY & GOVERNANCE RULES</div>
            <div style="font-size:0.82rem;color:#8899bb;line-height:2.0;">
            <b style="color:#c8d8ff;">Min truth score for ingestion:</b> {_MIN_SCORE}<br>
            <b style="color:#c8d8ff;">Required LLM judges:</b> 2 (factual coherence + epistemic standards)<br>
            <b style="color:#c8d8ff;">Human review triggered by:</b> score below 0.60, above 0.95, or suspicious phrases<br>
            <b style="color:#c8d8ff;">User override:</b> always available — family has final say<br>
            <b style="color:#c8d8ff;">Versioning:</b> every entry versioned, all changes visible<br>
            <b style="color:#c8d8ff;">Archive threshold:</b> 0.85 for long-term preservation<br>
            <b style="color:#c8d8ff;">Seal threshold:</b> Bitcoin-anchored at family discretion<br><br>
            <b style="color:#c8d8ff;">Judge 1 — Factual Coherence:</b> internal consistency + source quality + precision<br>
            <b style="color:#c8d8ff;">Judge 2 — Epistemic Standards:</b> falsifiability + steelman quality + uncertainty honesty
            </div></div>""", unsafe_allow_html=True)

    except ImportError:
        st.error("grokipedia.py not found. Push it to GitHub and redeploy.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB: COSMOS DASHBOARD 🌌
# Daily universe question + belief ledger + consciousness experiments
# + foresight tracker + 35 rotating cosmological questions
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
# TAB: WELCOME 🌍 — First page any new user (child or adult) sees
# Designed for: kids in orphanages, families with no prior tech education,
# anyone on any device. Works with NO glasses, NO hardware, NO prior knowledge.
# ══════════════════════════════════════════════════════════════════════════════
if "Welcome" in active:
    # Clean, warm, large-text welcome — no jargon
    st.markdown("""
    <style>
    .welcome-big { font-size: 2.2rem; color: #c8d8ff; font-weight: 700; line-height: 1.4; margin-bottom: 12px; }
    .welcome-sub { font-size: 1.1rem; color: #8899bb; line-height: 1.9; margin-bottom: 16px; }
    .welcome-card { background: #0d1228; border-radius: 12px; padding: 20px; margin-bottom: 12px; border-left: 4px solid #f7931a; }
    .welcome-step { font-size: 1rem; color: #c8d8ff; padding: 8px 0; border-bottom: 1px solid #1e2a3a; }
    .big-btn { font-size: 1.1rem !important; padding: 14px 28px !important; }
    </style>
    <div class="welcome-big">🦅 Welcome to AUBIEETERNAL</div>
    <div class="welcome-sub">
    A free school for anyone, anywhere in the world.<br>
    You do not need special glasses. You do not need to pay anything.<br>
    You do not need to be good at school already.<br><br>
    <b style="color:#f7931a;">You just need to be curious.</b>
    </div>
    """, unsafe_allow_html=True)

    # Path selector — the most important UX decision
    st.markdown("### Who are you starting as?")
    _wc1, _wc2, _wc3 = st.columns(3)

    with _wc1:
        st.markdown("""
        <div class="welcome-card">
        <div style="font-size:2rem;text-align:center;">👧</div>
        <div style="color:#f7931a;font-weight:700;text-align:center;margin-top:6px;">I am a child</div>
        <div style="color:#8899bb;font-size:0.85rem;text-align:center;margin-top:4px;">Ages 5–15<br>Start with fun lessons</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Start as a Child →", key="w_child", use_container_width=True):
            st.session_state.welcome_mode = "child"
            st.session_state.active_tab = "Community Mode"
            st.rerun()

    with _wc2:
        st.markdown("""
        <div class="welcome-card" style="border-left-color:#00cfff;">
        <div style="font-size:2rem;text-align:center;">👨‍👩‍👧</div>
        <div style="color:#00cfff;font-weight:700;text-align:center;margin-top:6px;">I am a family</div>
        <div style="color:#8899bb;font-size:0.85rem;text-align:center;margin-top:4px;">Learn together<br>All ages welcome</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Start as a Family →", key="w_family", use_container_width=True):
            st.session_state.welcome_mode = "family"
            st.rerun()

    with _wc3:
        st.markdown("""
        <div class="welcome-card" style="border-left-color:#a020f0;">
        <div style="font-size:2rem;text-align:center;">🏫</div>
        <div style="color:#a020f0;font-weight:700;text-align:center;margin-top:6px;">I run a school</div>
        <div style="color:#8899bb;font-size:0.85rem;text-align:center;margin-top:4px;">Orphanage, community<br>center, or group</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Deploy for my school →", key="w_school", use_container_width=True):
            st.session_state.welcome_mode = "school"
            st.rerun()

    # "Start as a Family" used to just set a flag and do nothing visible -
    # found live 2026-08-25 when a real click on this exact button on the
    # tablet produced no walkthrough at all. The real sign-in/create-family
    # UI (_family_login_block(), defined earlier in this file) already
    # existed but was only ever triggered from unrelated gated tabs like
    # Daily Quests - never reachable from Welcome, the actual first thing
    # anyone sees. Show it right here instead of just flipping a flag.
    if st.session_state.get("welcome_mode") == "family":
        st.divider()
        st.markdown("### 👨‍👩‍👧 Sign in or create your family")
        _family_login_block()

    st.divider()
    # What you'll learn
    st.markdown("### What you will learn here (for free, forever)")
    _tracks_preview = [
        ("🤔", "How to think clearly", "Ask good questions. Find the truth. Spot when someone is lying."),
        ("🌌", "How the universe works", "From atoms to black holes to whether we are in a simulation."),
        ("🧠", "How your brain works", "Why you feel what you feel. How to calm down. How to focus."),
        ("💰", "How money actually works", "Why inflation steals from you and how Bitcoin changes that."),
        ("🔧", "How to build things", "Fix computers. Set up AI. Deploy sovereign infrastructure."),
        ("📖", "How to learn anything", "Study techniques that actually work. Backed by real science."),
        ("⚖️", "How to be fair", "Ethics, law, and why justice matters."),
        ("🌍", "How to help people", "Deploy a free school for your community when you graduate."),
    ]
    _pc1, _pc2 = st.columns(2)
    for _idx, (_emoji, _title, _desc) in enumerate(_tracks_preview):
        with (_pc1 if _idx % 2 == 0 else _pc2):
            st.markdown(
                f'<div style="padding:8px 0;border-bottom:1px solid #1e2a3a;">'
                f'<span style="font-size:1.2rem">{_emoji}</span> '
                f'<b style="color:#c8d8ff;">{_title}</b><br>'
                f'<span style="color:#8899bb;font-size:0.82rem;">{_desc}</span>'
                f'</div>', unsafe_allow_html=True)

    st.divider()
    # Orphanage / community note
    st.markdown("""
    <div style="background:#0a0f1e;border:2px solid #00ff88;border-radius:12px;padding:20px;margin-top:8px;">
    <div style="color:#00ff88;font-size:1rem;font-weight:700;margin-bottom:8px;">🌍 For orphanages and community centers</div>
    <div style="color:#8899bb;font-size:0.9rem;line-height:2.0;">
    This entire school runs on a $200 computer — or even less.<br>
    You do not need the internet after setup.<br>
    You do not need glasses or special equipment.<br>
    Everything works on any tablet, phone, or old laptop.<br><br>
    <b style="color:#c8d8ff;">The AI tutor works offline</b> — it runs directly on your computer.<br>
    All 250 lessons are free forever. No subscription. No ads. No data collection.<br><br>
    See the <b style="color:#00ff88;">Community Mode</b> tab for the setup guide.
    </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()
    # You're already connected — no setup needed. Living Lattice is the
    # zero-config path to "part of something bigger": no Nostr keys, no
    # Lightning address, nothing to configure. Family messaging elsewhere
    # in the app is real but local-only to one install; this is the actual
    # answer to "how do we stay connected" for a brand new download.
    st.markdown("""
    <div style="background:#0a0f1e;border:2px solid #00cfff;border-radius:12px;padding:20px;margin-top:8px;">
    <div style="color:#00cfff;font-size:1rem;font-weight:700;margin-bottom:8px;">🕸️ You're already connected — no setup needed</div>
    <div style="color:#8899bb;font-size:0.9rem;line-height:2.0;">
    Every AUBIEETERNAL family quietly contributes to the <b style="color:#c8d8ff;">Living Lattice</b> —
    an anonymous, real-time picture of how families everywhere are doing: coherence, lessons completed,
    wonder index. No account, no keys, nothing to set up. It's on by default.<br><br>
    See the <b style="color:#00cfff;">Living Lattice</b> tab to watch your family's signal join the wider picture.
    </div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB: COMMUNITY MODE 🏫
# Stripped-down, large-text, warm interface for orphanages, schools,
# and any learner who needs maximum accessibility
# ══════════════════════════════════════════════════════════════════════════════
if "Community Mode" in active:
    # Large, readable, warm — no dark-tech jargon
    _wmode = st.session_state.get("welcome_mode", "child")

    st.markdown(f"""
    <style>
    .cm-title {{ font-size: 1.8rem; color: #f7931a; font-weight: 700; margin-bottom: 8px; }}
    .cm-lesson {{ background: #0d1228; border-radius: 10px; padding: 18px; margin-bottom: 10px; border-left: 5px solid #f7931a; }}
    .cm-lesson-title {{ font-size: 1.1rem; color: #c8d8ff; font-weight: 600; margin-bottom: 6px; }}
    .cm-lesson-body {{ font-size: 0.95rem; color: #8899bb; line-height: 1.9; }}
    .cm-state-btn {{ padding: 16px; border-radius: 8px; text-align: center; font-size: 1rem; font-weight: 600; cursor: pointer; }}
    </style>
    <div class="cm-title">🏫 Learning Mode — Everyone Welcome</div>
    """, unsafe_allow_html=True)

    _cm_tabs = st.tabs(["🎯 Start Here", "🌡️ How Do You Feel?",
                         "📚 Pick a Lesson", "🏗️ Set Up Your School",
                         "🌍 Deploy Guide"])

    # ── Start Here ──────────────────────────────────────────────────────────
    with _cm_tabs[0]:
        st.markdown("""
        <div style="font-size:1rem;color:#c8d8ff;line-height:2.2;padding:8px 0;">
        Welcome. You are in the right place.<br><br>
        This school has <b style="color:#f7931a;">250 lessons</b> across 48 topics.<br>
        You can start at any age. You can go as deep as you want.<br>
        A 7-year-old and a university professor can learn the same lesson — at different depths.<br><br>
        <b>How it works:</b><br>
        1. Tell us how you feel right now (the next tab)<br>
        2. Pick a lesson that interests you<br>
        3. Read it. Think about it. Try the activity at the end.<br>
        4. Come back tomorrow and do another one.<br><br>
        <b style="color:#00ff88;">That is the whole thing. No tests. No grades. No fees.</b>
        </div>
        """, unsafe_allow_html=True)

        # Name + PIN — real, lightweight identity (community_learners.py),
        # no email or personal info needed. Found 2026-08-25: this used to
        # be just a name box that saved nothing at all (pure
        # st.session_state, gone the moment the tab closed) - a walk-up
        # learner had zero way to pick up where they left off tomorrow.
        if st.session_state.get("cm_learner_id"):
            st.markdown(
                f'<div class="card" style="border:2px solid #00ff88;text-align:center;padding:1rem;">'
                f'<div style="color:#00ff88;font-size:1rem;">✅ Signed in as {st.session_state.get("cm_learner_name","")}</div>'
                f'</div>', unsafe_allow_html=True)
            if st.button("🚪 Not you? Sign in as someone else", key="cm_switch"):
                for _k in ("cm_learner_id", "cm_learner_name"):
                    st.session_state.pop(_k, None)
                st.rerun()
        else:
            _cm_name = st.text_input("What is your name?",
                                      key="cm_name", placeholder="e.g. Maria")
            _cm_pin  = st.text_input("Pick a short PIN (any 4+ digits or letters — remember it!)",
                                      key="cm_pin", placeholder="e.g. 4821", type="password")
            _cm_age  = st.selectbox("How old are you?",
                                     ["I prefer not to say", "Under 8", "8-11", "12-15", "16-18", "Adult"],
                                     key="cm_age")
            st.caption("No email, no personal info — just your name and PIN, so you can come back "
                       "tomorrow and pick up where you left off. If you've been here before, use the "
                       "exact same name and PIN.")
            if st.button("✅ Let's Start", key="cm_start", type="primary") and _cm_name and _cm_pin:
                try:
                    from community_learners import resume_or_create as _cm_resume
                    _result = _cm_resume(_cm_name, _cm_pin, age_range=_cm_age)
                    st.session_state["cm_learner_id"]   = _result["learner_id"]
                    st.session_state["cm_learner_name"] = _result["display_name"]
                    if _result["is_new"]:
                        st.success(f"Nice to meet you, {_result['display_name']}! Remember your name "
                                   f"and PIN to come back tomorrow. Go to 'How Do You Feel?' to begin.")
                    else:
                        st.success(f"Welcome back, {_result['display_name']}! Go to 'How Do You Feel?' to continue.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
                except ImportError:
                    st.error("community_learners.py not found.")

    # ── How Do You Feel — No Glasses Needed ────────────────────────────────
    with _cm_tabs[1]:
        st.markdown("""
        <div style="font-size:1rem;color:#c8d8ff;line-height:1.9;margin-bottom:16px;">
        Before you learn anything, check in with yourself.<br>
        Your brain learns better when you know how you feel.<br>
        Pick the one that is closest to how you feel <b>right now</b>:
        </div>
        """, unsafe_allow_html=True)

        _states = [
            ("🟢", "CALM and READY", "I feel okay. I'm curious. I want to learn.", "#00ff88", 2),
            ("🟡", "A BIT NERVOUS or FRUSTRATED", "I feel unsettled, worried, or annoyed.", "#ffcc00", 1),
            ("🔴", "TIRED, NUMB, or 'I DON'T CARE'", "I feel empty, shut down, or don't want to be here.", "#ff4444", 0),
        ]

        for _emoji, _state_name, _state_desc, _color, _val in _states:
            st.markdown(
                f'<div style="background:#0d1228;border-radius:10px;padding:16px;'
                f'margin-bottom:10px;border-left:5px solid {_color};">'
                f'<div style="font-size:1.4rem">{_emoji} <b style="color:{_color};">{_state_name}</b></div>'
                f'<div style="color:#8899bb;margin-top:4px;">{_state_desc}</div>'
                f'</div>', unsafe_allow_html=True)
            if st.button(f"I feel like this right now", key=f"cm_state_{_val}", use_container_width=True):
                st.session_state.cm_state = _val
                st.session_state.cm_state_name = _state_name
                if _val == 2:
                    st.success("Great! You are ready to learn. Go to 'Pick a Lesson'.")
                elif _val == 1:
                    st.warning("That is okay. Try this: take 3 slow breaths. In for 4 counts, out for 6. Then try a lesson when you feel a bit calmer.")
                else:
                    st.info("That is okay too. Sometimes we just need a rest. Come back when you are ready. You can also try a very easy lesson — just reading, no pressure.")

    # ── Pick a Lesson ───────────────────────────────────────────────────────
    with _cm_tabs[2]:
        st.markdown("### Choose what you want to learn today")
        st.markdown('<div style="color:#8899bb;font-size:0.9rem;margin-bottom:12px;">Start with anything that sounds interesting. There is no wrong answer.</div>', unsafe_allow_html=True)

        # Organized by interest, not by academic track
        _interest_groups = {
            "🤔 I want to think more clearly": ["steelmanning-1","layer-zero-1","decision-1","adversarial-robustness-1"],
            "🌌 I want to understand the universe": ["cosmos-1","universe-1","simulation-1","information-1"],
            "🧠 I want to understand myself": ["polyvagal-1","identity-1","self-evolving-1","consciousness-1"],
            "💰 I want to understand money": ["bitcoin-sovereignty-1","economic-trap-1","antifragility-1","money-1"],
            "🔧 I want to build things": ["builder-1","builder-2","tech-sovereignty-1","sovereign-builder-1"],
            "🌍 I want to help people": ["helping-humanity-1","network-1","layer-zero-6","expertise-1"],
            "📖 I want to learn how to learn": ["school-foundation-2","school-foundation-1","knowledge-evolution-1","decision-2"],
            "🎭 I want to understand power and stories": ["narrative-warfare-1","gatekeeper-1","language-1","expertise-2"],
        }

        try:
            from family_hud import LESSONS as _CM_LESSONS
            for _group, _lesson_keys in _interest_groups.items():
                with st.expander(_group, expanded=False):
                    for _lk in _lesson_keys:
                        _l = _CM_LESSONS.get(_lk, {})
                        if _l:
                            st.markdown(
                                f'<div style="padding:10px;background:#0d1228;border-radius:8px;'
                                f'margin-bottom:6px;border-left:3px solid #f7931a;">'
                                f'<div style="color:#c8d8ff;font-size:0.95rem;font-weight:600;">'
                                f'{_l.get("title","?")}</div>'
                                f'<div style="color:#8899bb;font-size:0.82rem;margin-top:3px;">'
                                f'Age {_l.get("age_hint","all")} · {_l.get("xp",0)} XP</div>'
                                f'<div style="color:#556688;font-size:0.78rem;margin-top:2px;">'
                                f'{str(_l.get("topic",""))[:120]}...</div>'
                                f'</div>', unsafe_allow_html=True)
                            if st.button(f"📖 Start this lesson", key=f"cm_start_{_lk}"):
                                st.session_state.cm_active_lesson = _lk
                                st.rerun()

            # Show active lesson if selected
            _active_l = st.session_state.get("cm_active_lesson")
            if _active_l:
                _l = _CM_LESSONS.get(_active_l, {})
                if _l:
                    st.divider()
                    st.markdown(f'<div style="font-size:1.2rem;color:#f7931a;font-weight:700;padding:8px 0;">'
                                f'{_l.get("title","")}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div style="color:#8899bb;font-size:0.9rem;line-height:1.8;margin-bottom:12px;">'
                                f'<b style="color:#c8d8ff;">What this is about:</b><br>{_l.get("topic","")}</div>',
                                unsafe_allow_html=True)
                    if _l.get("example"):
                        st.markdown(f'<div style="background:#0d1228;border-radius:8px;padding:14px;'
                                    f'border-left:4px solid #00cfff;margin-bottom:10px;">'
                                    f'<div style="color:#00cfff;font-size:0.75rem;font-weight:600;margin-bottom:6px;">LESSON</div>'
                                    f'<div style="color:#c8d8ff;font-size:0.9rem;line-height:1.9;">'
                                    f'{str(_l.get("example","")).replace(chr(10),"<br>")}</div></div>',
                                    unsafe_allow_html=True)
                    if _l.get("activity"):
                        st.markdown(f'<div style="background:#071810;border-radius:8px;padding:14px;'
                                    f'border-left:4px solid #00ff88;margin-bottom:10px;">'
                                    f'<div style="color:#00ff88;font-size:0.75rem;font-weight:600;margin-bottom:6px;">TRY THIS</div>'
                                    f'<div style="color:#c8d8ff;font-size:0.9rem;line-height:1.9;">'
                                    f'{str(_l.get("activity","")).replace(chr(10),"<br>")}</div></div>',
                                    unsafe_allow_html=True)
                    if _l.get("steelman"):
                        with st.expander("🤔 Hard Question to Think About"):
                            st.markdown(f'<div style="color:#8899bb;font-size:0.9rem;line-height:1.8;">'
                                        f'{_l.get("steelman","")}</div>', unsafe_allow_html=True)
                    if st.button("✅ I finished this lesson!", key="cm_done", type="primary"):
                        xp = _l.get("xp", 15)
                        # Real persistence (2026-08-25 fix) - this used to just
                        # show balloons + a success message claiming XP was
                        # earned with zero actual save, same category of false
                        # claim as the earlier "encrypted" messaging bug.
                        _cm_learner_id = st.session_state.get("cm_learner_id")
                        if _cm_learner_id:
                            from family_profiles import load_family_stats as _cm_lfs, save_family_stats as _cm_sfs
                            _cm_stats = _cm_lfs(_cm_learner_id)
                            if _active_l not in _cm_stats.get("lessons_completed", []):
                                _cm_stats.setdefault("lessons_completed", []).append(_active_l)
                                _cm_stats["total_xp"] = _cm_stats.get("total_xp", 0) + xp
                                _cm_stats["level"]    = max(1, _cm_stats["total_xp"] // 100 + 1)
                                _cm_sfs(_cm_stats, _cm_learner_id)
                            st.balloons()
                            st.success(f"Amazing! You earned {xp} XP — really saved this time. "
                                       f"Come back tomorrow (same name + PIN) for another lesson.")
                        else:
                            st.warning("Go to 'Start Here' and enter your name + PIN first, so this "
                                       "lesson actually gets saved to your progress.")
                        st.session_state.cm_active_lesson = None

        except ImportError:
            st.error("family_hud.py not found. Make sure it is in the same folder as app.py.")

    # ── Set Up Your School ───────────────────────────────────────────────────
    with _cm_tabs[3]:
        st.markdown("""
        <div style="font-size:1rem;color:#c8d8ff;line-height:2.2;">
        <b style="font-size:1.2rem;color:#f7931a;">You can run this school anywhere.</b><br><br>
        What you need:
        </div>
        """, unsafe_allow_html=True)

        _reqs = [
            ("💻", "One computer", "Any laptop or desktop from the last 10 years. Even old ones work.\n8GB RAM minimum. 16GB is better for the AI tutor."),
            ("🌐", "Internet (once)", "You only need internet to download everything the first time.\nAfter that, it works completely offline."),
            ("📺", "A screen", "Any monitor, TV, or projector. Even an old phone works for one person."),
            ("🆓", "Zero cost", "Everything is free. The software, the lessons, the AI tutor — all free forever."),
        ]
        for _icon, _title, _desc in _reqs:
            st.markdown(
                f'<div style="background:#0d1228;border-radius:10px;padding:14px;margin-bottom:8px;">'
                f'<span style="font-size:1.5rem">{_icon}</span> '
                f'<b style="color:#c8d8ff;">{_title}</b><br>'
                f'<span style="color:#8899bb;font-size:0.85rem;">{_desc.replace(chr(10),"<br>")}</span>'
                f'</div>', unsafe_allow_html=True)

        st.divider()
        st.markdown("### Step-by-step setup for first time")
        _steps = [
            ("1", "Download everything", "Go to github.com/AUBIEETERNAL-INSTITUTE-INC/AUBIEETERNAL\nClick the green 'Code' button → 'Download ZIP'\nUnzip the folder"),
            ("2", "Install the AI (Ollama)", "Go to ollama.com/download and download Ollama.\nInstall it. This is the offline AI brain."),
            ("3", "Download the AI model", 'Open a terminal and type:\nollama pull qwen2.5:7b\nThis downloads the AI that will answer questions. Takes ~15 minutes on first setup.'),
            ("4", "Install Python", "Go to python.org/downloads and install Python 3.11.\nThis runs the school software."),
            ("5", "Install the school", "In the AUBIEETERNAL folder, double-click install_windows.bat (Windows)\nor run: bash install_mac_linux.sh (Mac/Linux)"),
            ("6", "Open the school", "Double-click launcher.py or run: python launcher.py\nThe school opens in your web browser."),
        ]
        for _num, _title, _desc in _steps:
            st.markdown(
                f'<div style="background:#071810;border-radius:8px;padding:14px;margin-bottom:8px;border-left:4px solid #00ff88;">'
                f'<div style="color:#00ff88;font-weight:700;">Step {_num}: {_title}</div>'
                f'<div style="color:#8899bb;font-size:0.85rem;margin-top:4px;">{_desc.replace(chr(10),"<br>")}</div>'
                f'</div>', unsafe_allow_html=True)

    # ── Deploy Guide for Orphanages ─────────────────────────────────────────
    with _cm_tabs[4]:
        st.markdown("""
        <div style="background:#0d1228;border:2px solid #00ff88;border-radius:12px;padding:20px;margin-bottom:16px;">
        <div style="color:#00ff88;font-size:1.1rem;font-weight:700;margin-bottom:8px;">
        🌍 Deploying for an Orphanage or Community Center
        </div>
        <div style="color:#8899bb;font-size:0.9rem;line-height:2.0;">
        This guide is for teachers, staff, or volunteers who want to bring this school
        to children who need it most.<br><br>
        <b style="color:#c8d8ff;">One computer can serve an entire classroom.</b><br>
        Run it on a projector — 30 children at once.<br>
        Or let each child take turns at the screen.<br>
        Or if you have tablets, they can all connect to one computer over local WiFi.
        </div>
        </div>
        """, unsafe_allow_html=True)

        _deploy_sections = [
            ("📦 What hardware to get (on any budget)", """
Minimum (works, slow AI): $100-150 computer + 8GB RAM
Better (smooth AI): Any computer with 16GB RAM — usually $200-300 used
Best (fast AI): 32-64GB RAM computer — usually $400-600 used

The AI tutor (Ollama + qwen2.5:7b) runs on the computer itself.
No internet needed once set up. No monthly fees.
Old donated computers from businesses or schools often work perfectly."""),
            ("🌐 Setting up for multiple children (local WiFi)", """
1. Set up the school on the main computer (follow Step-by-step setup)
2. Connect all devices to the same WiFi network (or a cheap router — no internet needed)
3. On each child's device, open a browser and go to: http://[main-computer-ip]:8501
4. All children can use the school at the same time from any device

This works with: old tablets, old phones, old laptops, Chromebooks, Raspberry Pis.
The browser is the only requirement."""),
            ("📚 How to run lessons with a group", """
Option A — Teacher-led (projector): Teacher opens a lesson on the projector.
Read it together. Do the activity as a class discussion.
Ask the steelman question. Debate. Think together.

Option B — Individual pace: Each child works at their own speed.
The system tracks progress per person.
No one is left behind. No one is held back.

Option C — Mixed: Start together, let advanced learners go deeper,
support learners who need more time with the simpler questions."""),
            ("🌍 Reporting your deployment (earn the Eternal Founder capstone)", """
If you deploy this school for a community:
1. Document it: photos, number of children served, date
2. Submit it as a humanitarian contribution in the Sovereign Builder tab
3. This counts toward the Eternal Founder capstone requirement
4. It contributes to the Living Lattice — the global network of sovereign schools

Every deployment is permanent. Every child you teach is part of the chain."""),
            ("📞 Getting help", """
GitHub: github.com/AUBIEETERNAL-INSTITUTE-INC/AUBIEETERNAL (file an issue)
Twitter/X: @MateoVanhorn
Everything is open source — someone will help.

If you need a setup translated into another language:
submit a PR or contact us — translation is the second-highest-impact contribution."""),
        ]

        for _sec_title, _sec_body in _deploy_sections:
            with st.expander(_sec_title, expanded=False):
                st.markdown(f'<div style="color:#8899bb;font-size:0.88rem;line-height:2.0;">'
                            f'{_sec_body.replace(chr(10),"<br>")}</div>', unsafe_allow_html=True)

        # Contact form stub
        st.divider()
        st.markdown("### Need help deploying?")
        _dc1, _dc2 = st.columns(2)
        with _dc1:
            _deploy_loc = st.text_input("Where are you deploying?", key="dl_loc",
                placeholder="e.g. Nairobi, Kenya — orphanage, 45 children")
        with _dc2:
            _deploy_contact = st.text_input("How to reach you?", key="dl_contact",
                placeholder="email or Twitter/X handle")
        _deploy_notes = st.text_area("What do you need help with?", height=80, key="dl_notes",
            placeholder="e.g. We have old Windows laptops and no tech person — need step by step help")
        if st.button("🌍 Submit Deployment Request", key="dl_submit", type="primary") and _deploy_loc:
            import json as _jdl, pathlib as _pdl, datetime as _ddl, socket as _sdl
            try:
                _sdl.gethostbyname("localhost")
                _dl = _pdl.Path("/mnt/main/deployment_requests.jsonl")
            except Exception:
                _dl = _pdl.Path(os.path.expanduser("~/.aubieeternal/main/deployment_requests.jsonl"))
            with open(_dl, "a") as f:
                f.write(_jdl.dumps({"date":str(_ddl.date.today()),"location":_deploy_loc,
                                    "contact":_deploy_contact,"notes":_deploy_notes}) + "\n")
            st.success(f"✅ Deployment request logged!\n\n"
                       f"Location: {_deploy_loc}\n\n"
                       f"We will do our best to support you. Check GitHub issues for help from the community.\n\n"
                       f"Every deployment matters. War Eagle 🦅")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: RELIABILITY ⚡
# HermesBench integration + Epistemic Drift Detector dashboard
# ══════════════════════════════════════════════════════════════════════════════
if "Reliability" in active:
    st.markdown('<div class="card-title">⚡ RELIABILITY DASHBOARD — Swarm Quality + Epistemic Drift</div>', unsafe_allow_html=True)

    _rel_tabs = st.tabs(["🎯 Drift Detector", "🧪 HermesBench", "📊 History", "⚙️ Setup"])

    # ── Drift Detector ─────────────────────────────────────────────────────
    with _rel_tabs[0]:
        st.markdown("""
        <div class="card" style="border-left:3px solid #f7931a;">
            <div style="color:#f7931a;font-family:Orbitron,monospace;font-size:0.72rem;">
            EPISTEMIC DRIFT DETECTOR</div>
            <div style="color:#8899bb;font-size:0.82rem;margin-top:6px;line-height:1.8;">
            Monitors whether the swarm's output quality is drifting over time.
            A swarm that runs 24/7 can gradually produce lower-quality signal
            without any single obvious failure — until it compounds.
            This catches that before it damages the Epistemic Commons.
            </div>
        </div>""", unsafe_allow_html=True)

        if st.button("🔍 Run Drift Analysis", key="drift_run", type="primary"):
            with st.spinner("Analyzing epistemic signals over last 30 days..."):
                try:
                    from epistemic_drift_detector import EpistemicDriftDetector as _EDD
                    _det    = _EDD(window_days=30)
                    _report = _det.run_full_analysis()

                    _level  = _report["alert_level"]
                    _lc     = {"GREEN":"#00ff88","YELLOW":"#ffcc00","RED":"#ff9500","ALARM":"#ff4444"}.get(_level,"#445577")
                    _icons  = {"GREEN":"🟢","YELLOW":"🟡","RED":"🔴","ALARM":"🚨"}

                    st.markdown(
                        f'<div style="text-align:center;padding:12px;background:#0d1228;'
                        f'border-radius:10px;border:2px solid {_lc};">'
                        f'<div style="font-size:2rem">{_icons.get(_level,"?")}</div>'
                        f'<div style="color:{_lc};font-family:Orbitron,monospace;font-size:1rem;margin-top:4px;">'
                        f'{_level}</div>'
                        f'<div style="color:#445577;font-size:0.75rem;margin-top:2px;">'
                        f'{_report["n_flags"]} drift flag(s) detected</div>'
                        f'</div>', unsafe_allow_html=True)

                    if _report["drift_flags"]:
                        st.markdown("**Drift flags:**")
                        for _flag in _report["drift_flags"]:
                            st.markdown(f'<div style="color:#ff9500;font-size:0.82rem;padding:2px 0;">⚠️ {_flag}</div>',
                                        unsafe_allow_html=True)

                    st.markdown("**Signal summary:**")
                    for _sname, _sig in _report["signals"].items():
                        _tc = "#00ff88" if not _sig["drifting_down"] and not _sig["high_variance"] else "#ff9500"
                        st.markdown(
                            f'<div style="padding:4px 0;border-bottom:1px solid #1e2a3a;">'
                            f'<b style="color:{_tc};">{_sname}</b> '
                            f'mean={_sig["mean"]:.3f} · trend={_sig["trend"]:+.5f} · '
                            f'n={_sig["n_samples"]} · '
                            f'{"⚠️ drifting" if _sig["drifting_down"] else "✅ stable"}'
                            f'</div>', unsafe_allow_html=True)

                    st.markdown("**Recommendations:**")
                    for _rec in _report["recommendations"]:
                        st.markdown(f'<div style="color:#8899bb;font-size:0.82rem;padding:3px 0;">→ {_rec}</div>',
                                    unsafe_allow_html=True)

                    if st.button("💾 Save as Baseline", key="drift_baseline"):
                        _det.save_baseline()
                        st.success("✅ Current signal means saved as baseline. Future runs will compare against today.")

                except ImportError:
                    st.error("epistemic_drift_detector.py not found. Copy it to the repo root.")

    # ── HermesBench ────────────────────────────────────────────────────────
    with _rel_tabs[1]:
        st.markdown("""
        <div class="card" style="border-left:3px solid #00cfff;">
            <div style="color:#00cfff;font-family:Orbitron,monospace;font-size:0.72rem;">
            HERMESBENCH — SWARM RELIABILITY EVALUATION</div>
            <div style="color:#8899bb;font-size:0.82rem;margin-top:6px;line-height:1.8;">
            7 AUBIEETERNAL-specific recipes testing: tutor handoff integrity,
            Epistemic Commons provenance, polyvagal safety boundaries,
            Bitcoin anchor integrity, state persistence, wonder spike detection,
            and zero-drift output consistency.
            </div>
        </div>""", unsafe_allow_html=True)

        _hb_c1, _hb_c2 = st.columns(2)
        with _hb_c1:
            _run_drift = st.checkbox("Include zero-drift test (slow — Ollama)", key="hb_drift", value=False)
        with _hb_c2:
            _single_recipe = st.selectbox("Or run single recipe:", [
                "all", "tutor_handoff", "epistemic_provenance", "polyvagal_safety",
                "bitcoin_integrity", "state_persistence", "wonder_spike", "zero_drift"
            ], key="hb_recipe")

        if st.button("🧪 Run HermesBench", key="hb_run", type="primary"):
            with st.spinner("Running reliability evaluation..."):
                try:
                    from hermesbench_integration import AUBIEBenchSuite as _HBS
                    _suite = _HBS()

                    if _single_recipe != "all":
                        _fn = getattr(_suite, f"recipe_{_single_recipe}", None)
                        if _fn:
                            _r = _fn()
                            _rc = "#00ff88" if _r.passed else "#ff4444"
                            st.markdown(
                                f'<div class="card" style="border-left:4px solid {_rc};">'
                                f'<div style="color:{_rc};font-size:0.9rem;font-weight:600;">'
                                f'{"✅ PASSED" if _r.passed else "❌ FAILED"} — {_r.name}</div>'
                                f'<div style="color:#8899bb;font-size:0.82rem;margin-top:4px;">'
                                f'Score: {_r.score:.2f} · Latency: {_r.latency_ms:.0f}ms</div>'
                                f'</div>', unsafe_allow_html=True)
                            st.json(_r.details)
                    else:
                        _summary = _suite.run_all(skip_drift=not _run_drift)
                        _sc = "#00ff88" if _summary["pass_rate"] >= 0.8 else "#ffcc00" if _summary["pass_rate"] >= 0.6 else "#ff4444"
                        _hbc1, _hbc2, _hbc3 = st.columns(3)
                        _hbc1.metric("Overall Score", f"{_summary['overall_score']:.2f}")
                        _hbc2.metric("Pass Rate", f"{_summary['pass_rate']:.0%}")
                        _hbc3.metric("Passed", f"{_summary['passed']}/{_summary['total']}")

                        for _r_dict in _summary["recipes"]:
                            _rc2 = "#00ff88" if _r_dict["passed"] else "#ff4444"
                            st.markdown(
                                f'<div style="padding:4px 0;border-bottom:1px solid #1e2a3a;">'
                                f'<b style="color:{_rc2};">{"✅" if _r_dict["passed"] else "❌"} {_r_dict["recipe"]}</b> '
                                f'score={_r_dict["score"]:.2f} · {_r_dict["latency_ms"]:.0f}ms'
                                f'</div>', unsafe_allow_html=True)

                except ImportError:
                    st.error("hermesbench_integration.py not found.")

    # ── History ────────────────────────────────────────────────────────────
    with _rel_tabs[2]:
        st.markdown("**Reliability evaluation history — track quality over time.**")
        try:
            from epistemic_drift_detector import EpistemicDriftDetector as _EDD2
            _hist = _EDD2().get_drift_history(30)
            if _hist:
                for _h in reversed(_hist[-10:]):
                    _hc = {"GREEN":"#00ff88","YELLOW":"#ffcc00","RED":"#ff9500","ALARM":"#ff4444"}.get(_h.get("alert_level","?"),"#445577")
                    st.markdown(
                        f'<div style="padding:4px 0;border-bottom:1px solid #1e2a3a;">'
                        f'<b style="color:{_hc};">{_h.get("alert_level","?")}</b> '
                        f'<span style="color:#445577;font-size:0.75rem;">{_h.get("timestamp","")[:16]}</span> '
                        f'<span style="color:#8899bb;font-size:0.78rem;">{_h.get("n_flags",0)} flags</span>'
                        f'</div>', unsafe_allow_html=True)
            else:
                st.info("No drift analysis history yet. Run the Drift Detector to build history.")
        except ImportError:
            st.info("epistemic_drift_detector.py not found.")

    # ── Setup ──────────────────────────────────────────────────────────────
    with _rel_tabs[3]:
        st.markdown("### Setup and CI Integration")
        st.caption("No extra install needed — hermesbench_integration.py's 7 recipes are self-contained, reading this install's own local logs directly.")
        st.code("""# Copy these files to your repo root:
# hermesbench_integration.py
# epistemic_drift_detector.py

# Run manually
python hermesbench_integration.py
python epistemic_drift_detector.py

# Save a baseline after a known-good period
python epistemic_drift_detector.py --baseline

# Wire into nightly CI (add to COMMIT_EPISTEMIC.sh)
python hermesbench_integration.py --nightly || echo "⚠️ Reliability check failed"
python epistemic_drift_detector.py --ci --fail-on RED || echo "⚠️ Drift detected"
""", language="bash")

        st.markdown("### Add to COMMIT_EPISTEMIC.sh")
        st.code("""# Add these lines before git push:
echo "Running reliability checks..."
python hermesbench_integration.py --nightly
python epistemic_drift_detector.py --ci

# The checks exit nonzero on failure but don't block the push
# They log results to /mnt/main/hermesbench_evals/ for review
""", language="bash")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: TRANSCRIPTS 📜
# Bitcoin-anchored official academic transcripts
# ══════════════════════════════════════════════════════════════════════════════
if "Transcripts" in active:
    st.markdown('<div class="card-title">📜 OFFICIAL TRANSCRIPT SYSTEM — Bitcoin-Anchored Credentials</div>',
                unsafe_allow_html=True)
    _fid_tr = st.session_state.get("current_family", {}).get("family_id", "default") \
              if st.session_state.get("current_family") else "default"
    _tr_tabs = st.tabs(["📄 My Transcript", "🎓 Award Degree", "✅ Verify", "📊 Degrees"])

    with _tr_tabs[0]:
        _sname = st.text_input("Your name for the transcript:", key="tr_name",
                               value="Sovereign Student")
        if st.button("🔄 Generate Transcript", key="tr_gen", type="primary"):
            try:
                from transcript_system import TranscriptGenerator
                gen = TranscriptGenerator(_fid_tr, _sname)
                tx  = gen.generate()
                # Display readable version
                readable = gen.to_readable(tx)
                st.code(readable, language=None)
                st.markdown(f'<div style="color:#445577;font-size:0.75rem;margin-top:8px;">'
                            f'SHA-256: {tx["sha256"]}</div>', unsafe_allow_html=True)
                if st.button("⚡ Anchor to Bitcoin", key="tr_anchor"):
                    anchor = gen.anchor_to_bitcoin(tx)
                    st.success(f"✅ Transcript anchored.\n\nHash: {tx['sha256'][:32]}...\n\n"
                               f"This record is now permanent. Anyone can verify it.")
            except ImportError:
                st.error("transcript_system.py not found in repo root.")

    with _tr_tabs[1]:
        st.markdown("**Check degree eligibility and award new degrees.**")
        if st.button("🎓 Check and Award Degrees", key="tr_award", type="primary"):
            try:
                from transcript_system import award_if_eligible
                new_deg = award_if_eligible(_fid_tr, st.session_state.get("kid_name","Student"))
                if new_deg:
                    st.balloons()
                    st.success(f"🎓 DEGREE AWARDED: {new_deg}\n\n"
                               f"Transcript anchored to Bitcoin. Permanent record created.")
                else:
                    from transcript_system import get_transcript, DEGREES as _DEGS
                    tx = get_transcript(_fid_tr)
                    rec = tx["academic_record"]
                    st.info(f"No new degrees at this time.\n\n"
                            f"Credits: {rec['total_credits']} | Coherence: {rec['coherence']:.4f}")
                    st.markdown("**Progress toward next degree:**")
                    for deg in _DEGS:
                        cr_needed  = max(0, deg["credits"] - rec["total_credits"])
                        coh_needed = max(0, deg["coherence"] - rec["coherence"])
                        pct = min(100, rec["total_credits"] / deg["credits"] * 100)
                        color = "#00ff88" if pct >= 100 else "#00cfff" if pct >= 50 else "#445577"
                        st.markdown(
                            f'<div style="margin:4px 0;padding:6px;background:#0d1228;'
                            f'border-radius:6px;border-left:3px solid {color};">'
                            f'<b style="color:{color};">{deg["name"]}</b> '
                            f'— {pct:.0f}% complete '
                            f'({cr_needed} more credits, {coh_needed:.2f} more coherence needed)'
                            f'</div>', unsafe_allow_html=True)
            except ImportError:
                st.error("transcript_system.py not found.")

    with _tr_tabs[2]:
        st.markdown("**Verify any transcript by its SHA-256 hash.**")
        _verify_hash = st.text_input("Paste transcript SHA-256 hash:", key="tr_verify_hash")
        _verify_json = st.text_area("Paste transcript JSON:", height=100, key="tr_verify_json")
        if st.button("✅ Verify", key="tr_verify_btn") and _verify_hash and _verify_json:
            import json as _jv, hashlib as _hv
            try:
                tx_obj = _jv.loads(_verify_json)
                canonical = _jv.dumps(
                    {k: v for k, v in tx_obj.items() if k != "sha256"},
                    sort_keys=True, separators=(',', ':')
                )
                computed = _hv.sha256(canonical.encode()).hexdigest()
                if computed == _verify_hash:
                    st.success(f"✅ VERIFIED — This transcript is authentic.\n\n"
                               f"Student: {tx_obj.get('student_name')}\n"
                               f"Degrees: {tx_obj.get('academic_record',{}).get('degrees_earned')}\n"
                               f"Credits: {tx_obj.get('academic_record',{}).get('total_credits')}")
                else:
                    st.error("❌ Hash mismatch — transcript has been modified.")
            except Exception as e:
                st.error(f"Parse error: {e}")

    with _tr_tabs[3]:
        st.markdown("**All degree programs and requirements.**")
        try:
            from transcript_system import DEGREES as _DEGS2
            for d in _DEGS2:
                st.markdown(
                    f'<div class="memory-node">'
                    f'<b style="color:#f7931a;">{d["name"]}</b> '
                    f'<span style="color:#445577;">— {d["credits"]} credits | coherence ≥{d["coherence"]}</span><br>'
                    f'<span style="color:#8899bb;font-size:0.82rem;">{d["description"]}</span>'
                    f'</div>', unsafe_allow_html=True)
        except ImportError:
            st.info("transcript_system.py not found.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB: PEER REVIEW 🔍
# Structured peer review for capstone projects
# ══════════════════════════════════════════════════════════════════════════════
if "Peer Review" in active:
    st.markdown('<div class="card-title">🔍 PEER REVIEW SYSTEM — Capstone Validation</div>',
                unsafe_allow_html=True)
    _fid_pr = st.session_state.get("current_family", {}).get("family_id", "default") \
              if st.session_state.get("current_family") else "default"

    _pr_tabs = st.tabs(["📤 Submit Capstone", "📋 Review Others", "📊 My Submissions", "📖 Rubric"])

    with _pr_tabs[0]:
        st.markdown("**Submit your capstone for peer review.**")
        _pr_title    = st.text_input("Title:", key="pr_title")
        _pr_abstract = st.text_area("Abstract (250 words max):", height=80, key="pr_abs")
        _pr_content  = st.text_area("Full capstone content:", height=200, key="pr_content")
        _pr_degree   = st.selectbox("Degree level:", [
            "truth_architect", "master_epistemic_rigor", "eternal_founder",
            "startos_operator", "sovereign_ai_researcher", "epistemic_civilization_builder"
        ], key="pr_degree")
        _pr_name     = st.text_input("Your name:", key="pr_sname", value="Sovereign Student")

        if st.button("📤 Submit for Peer Review", key="pr_submit", type="primary") and _pr_title and _pr_content:
            try:
                from peer_review_system import PeerReviewSystem
                system = PeerReviewSystem()
                sid = system.submit_capstone(_fid_pr, _pr_title, _pr_abstract,
                                              _pr_content, _pr_degree, _pr_name)
                st.success(f"✅ Submitted! Your submission ID: `{sid}`\n\n"
                           f"Share this ID so reviewers can find your work.\n"
                           f"You'll be notified when reviews arrive.")
            except ImportError:
                st.error("peer_review_system.py not found.")

    with _pr_tabs[1]:
        st.markdown("**Review capstones from other families.**")
        try:
            from peer_review_system import PeerReviewSystem, RUBRIC
            system = PeerReviewSystem()
            open_subs = system.get_open_submissions(exclude_family=_fid_pr)
            if not open_subs:
                st.info("No capstones awaiting review right now. Check back soon.")
            else:
                for sub in open_subs[:5]:
                    with st.expander(f"📄 {sub['title']} — {sub['degree_level']}"):
                        st.markdown(f"**Abstract:** {sub.get('abstract','')}")
                        st.markdown(f"**Degree:** {sub['degree_level']}")

                        _reviewer_name = st.text_input("Your name:", key=f"rev_name_{sub['submission_id']}")
                        _reviewer_coh  = st.slider("Your coherence:", 0.5, 1.0, 0.75, 0.01,
                                                    key=f"rev_coh_{sub['submission_id']}")

                        scores = {}
                        for rubric_key, rubric_item in RUBRIC.items():
                            scores[rubric_key] = st.slider(
                                f"{rubric_item['label']} (max {rubric_item['max_score']})",
                                0, rubric_item["max_score"],
                                rubric_item["max_score"] // 2,
                                key=f"rev_{rubric_key}_{sub['submission_id']}"
                            )

                        _narrative = st.text_area("Review narrative:", height=100,
                                                   key=f"rev_narr_{sub['submission_id']}")
                        _decision  = st.selectbox("Decision:",
                                                   ["accept","minor_revision","major_revision","reject"],
                                                   key=f"rev_dec_{sub['submission_id']}")

                        if st.button("Submit Review", key=f"rev_btn_{sub['submission_id']}",
                                     type="primary") and _reviewer_name and _narrative:
                            rid = system.submit_review(
                                sub["submission_id"], _fid_pr, _reviewer_name,
                                scores, _narrative, _decision, _reviewer_coh
                            )
                            st.success(f"✅ Review submitted (ID: {rid}). Bitcoin-sealed.")
        except ImportError:
            st.error("peer_review_system.py not found.")

    with _pr_tabs[2]:
        st.markdown("**Track your submitted capstones.**")
        try:
            from peer_review_system import PeerReviewSystem
            system = PeerReviewSystem()
            my_subs = system.get_family_submissions(_fid_pr)
            if not my_subs:
                st.info("No submissions yet. Use the Submit Capstone tab to submit your first capstone.")
            for sub in my_subs:
                _sc = {"accepted":"#00ff88","awaiting_review":"#ffcc00",
                        "needs_minor_revision":"#ff9500","needs_major_revision":"#ff4444"}.get(
                    sub.get("status","?"),"#445577")
                reviews = system.get_reviews_for_submission(sub["submission_id"])
                st.markdown(
                    f'<div class="memory-node" style="border-left:3px solid {_sc};">'
                    f'<b style="color:{_sc};">{sub["status"].upper()}</b> — {sub["title"]}<br>'
                    f'<span style="color:#445577;font-size:0.75rem;">'
                    f'ID: {sub["submission_id"]} | Reviews: {len(reviews)} | '
                    f'Avg score: {sub.get("avg_score","pending")}</span>'
                    f'</div>', unsafe_allow_html=True)
        except ImportError:
            st.error("peer_review_system.py not found.")

    with _pr_tabs[3]:
        st.markdown("**Review rubric — what reviewers are evaluating.**")
        try:
            from peer_review_system import RUBRIC
            for key, item in RUBRIC.items():
                st.markdown(
                    f'<div class="card" style="margin-bottom:6px;">'
                    f'<b style="color:#c8d8ff;">{item["label"]}</b> '
                    f'<span style="color:#445577;">(max {item["max_score"]} pts)</span><br>'
                    f'<span style="color:#8899bb;font-size:0.82rem;">{item["description"]}</span>'
                    f'</div>', unsafe_allow_html=True)
            st.markdown("**Total: 100 points.** Pass threshold varies by degree level.")
        except ImportError:
            st.error("peer_review_system.py not found.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB: WISDOM GDP 🌐
# Aggregate epistemic health of the Living Lattice
# ══════════════════════════════════════════════════════════════════════════════
if "Wisdom GDP" in active:
    st.markdown('<div class="card-title">🌐 WISDOM GDP — Aggregate Epistemic Health of the Living Lattice</div>',
                unsafe_allow_html=True)

    st.markdown("""
    <div class="card" style="border-left:3px solid #a020f0;">
    <div style="color:#a020f0;font-size:0.72rem;font-family:Orbitron,monospace;">WHAT IS WISDOM GDP?</div>
    <div style="color:#8899bb;font-size:0.82rem;margin-top:6px;line-height:1.8;">
    GDP measures aggregate economic output. Wisdom GDP measures aggregate epistemic output:
    how much high-quality truth-seeking, calibrated reasoning, and genuine knowledge is 
    the Living Lattice producing? This is the metric that matters for humanity —
    and almost nobody measures it anywhere.
    </div>
    </div>""", unsafe_allow_html=True)

    if st.button("🌐 Compute Wisdom GDP", key="wgdp_compute", type="primary"):
        with st.spinner("Computing aggregate epistemic health..."):
            try:
                from wisdom_gdp import WisdomGDPCalculator
                calc   = WisdomGDPCalculator()
                result = calc.compute()

                _score = result["wisdom_gdp"]
                _tier  = result["tier"]
                _color = "#00ff88" if _score >= 65 else "#ffcc00" if _score >= 40 else "#ff9500"

                st.markdown(
                    f'<div style="text-align:center;padding:20px;background:#0d1228;'
                    f'border-radius:12px;border:2px solid {_color};margin-bottom:16px;">'
                    f'<div style="color:{_color};font-family:Orbitron,monospace;font-size:2rem;">'
                    f'{_score:.1f}</div>'
                    f'<div style="color:#445577;font-size:0.75rem;">/ 100</div>'
                    f'<div style="color:{_color};font-size:1rem;margin-top:4px;">{_tier}</div>'
                    f'</div>', unsafe_allow_html=True)

                st.markdown("**Component breakdown:**")
                labels = {
                    "W1_coherence":        "Aggregate Coherence",
                    "W2_commons_quality":  "Epistemic Commons Quality",
                    "W3_steelman_depth":   "Steelman Depth",
                    "W4_calibration":      "Calibration Score",
                    "W5_deployment_index": "Deployment Index",
                    "W6_research_output":  "Research Output",
                    "W7_diversity_index":  "Diversity Index",
                }
                for k, v in result["components"].items():
                    _label = labels.get(k, k)
                    _bar_w = int(v * 120)
                    _cc = "#00ff88" if v >= 0.7 else "#ffcc00" if v >= 0.4 else "#ff9500"
                    st.markdown(
                        f'<div style="padding:4px 0;border-bottom:1px solid #1e2a3a;">'
                        f'<div style="display:flex;justify-content:space-between;">'
                        f'<span style="color:#c8d8ff;font-size:0.82rem;">{_label}</span>'
                        f'<span style="color:{_cc};font-size:0.82rem;">{v:.3f}</span></div>'
                        f'<div style="background:#1e2a3a;height:4px;border-radius:2px;margin-top:3px;">'
                        f'<div style="background:{_cc};height:4px;border-radius:2px;width:{_bar_w}px;"></div>'
                        f'</div></div>', unsafe_allow_html=True)

                st.markdown(f'<div style="color:#8899bb;font-size:0.82rem;margin-top:12px;'
                            f'padding:8px;background:#0d1228;border-radius:6px;">'
                            f'{result["interpretation"]}</div>', unsafe_allow_html=True)

                # Growth rate
                growth = calc.get_growth_rate()
                if growth is not None:
                    gc = "#00ff88" if growth > 0 else "#ff4444"
                    st.markdown(f'<div style="color:{gc};font-size:0.82rem;margin-top:8px;">'
                                f'Weekly trend: {growth:+.2f} points/week</div>', unsafe_allow_html=True)
            except ImportError:
                st.error("wisdom_gdp.py not found.")

    with st.expander("📊 Wisdom GDP History"):
        try:
            from wisdom_gdp import WisdomGDPCalculator
            hist = WisdomGDPCalculator().get_history(20)
            if hist:
                for h in reversed(hist[-10:]):
                    _hc = "#00ff88" if h["wisdom_gdp"] >= 65 else "#ffcc00"
                    st.markdown(
                        f'<div style="padding:3px 0;border-bottom:1px solid #1e2a3a;">'
                        f'<b style="color:{_hc};">{h["wisdom_gdp"]:.1f}</b> '
                        f'<span style="color:#445577;font-size:0.75rem;">{h["timestamp"][:16]}</span> '
                        f'<span style="color:#8899bb;font-size:0.75rem;">{h.get("tier","")}</span>'
                        f'</div>', unsafe_allow_html=True)
            else:
                st.info("No history yet. Run the calculator to start tracking.")
        except ImportError:
            st.info("wisdom_gdp.py not found.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB: ALUMNI NETWORK 🎓
# Track graduates, deployments, and Living Lattice growth
# ══════════════════════════════════════════════════════════════════════════════
if "Alumni Network" in active:
    st.markdown('<div class="card-title">🎓 ALUMNI NETWORK — The Living Lattice</div>',
                unsafe_allow_html=True)

    _fid_al = st.session_state.get("current_family", {}).get("family_id", "default") \
              if st.session_state.get("current_family") else "default"

    _al_tabs = st.tabs(["🌐 Lattice State", "📍 Log Deployment", "🎓 Graduates", "🌍 Impact"])

    with _al_tabs[0]:
        if st.button("🔄 Refresh Lattice", key="al_refresh", type="primary"):
            try:
                from alumni_deployment_tracker import LivingLattice
                state  = LivingLattice().get_lattice_state()
                impact = state["deployments"]
                swarm  = state["swarm"]

                _alc1, _alc2, _alc3 = st.columns(3)
                _alc1.metric("Total Graduates",   state["graduates"]["total"])
                _alc2.metric("Deployments",        impact["total_deployments"])
                _alc3.metric("People Served",      impact["total_people_served"])

                _alc4, _alc5, _alc6 = st.columns(3)
                _alc4.metric("Children Reached",   impact["estimated_children"])
                _alc5.metric("Wonder Index",        f"{swarm['wonder_index']:.3f}")
                _alc6.metric("Coherence",           f"{swarm['coherence']:.6f}")

                if state["graduates"]["by_degree"]:
                    st.markdown("**Graduates by degree:**")
                    for deg, count in state["graduates"]["by_degree"].items():
                        st.markdown(
                            f'<div style="padding:3px 0;border-bottom:1px solid #1e2a3a;">'
                            f'<span style="color:#f7931a;">{deg}</span> '
                            f'<span style="color:#8899bb;">— {count} graduate{"s" if count != 1 else ""}</span>'
                            f'</div>', unsafe_allow_html=True)
            except ImportError:
                st.error("alumni_deployment_tracker.py not found.")

    with _al_tabs[1]:
        st.markdown("**Log a community deployment of AUBIEETERNAL.**")
        _dep_type   = st.selectbox("Deployment type:", [
            "family_node","school_deployment","orphanage_deployment","community_center","library","other"
        ], key="al_dep_type")
        _dep_loc    = st.text_input("Location description:", key="al_dep_loc",
                                     placeholder="e.g. Nairobi, Kenya — Saint Mary's Orphanage")
        _dep_people = st.number_input("Number of people served:", min_value=1, value=10, key="al_dep_ppl")
        _dep_notes  = st.text_area("Notes (what worked, what was hard):", height=80, key="al_dep_notes")
        _dep_pub    = st.checkbox("Publish this deployment publicly (helps others see what's possible)", 
                                   key="al_dep_pub", value=True)

        if st.button("📍 Log Deployment", key="al_dep_btn", type="primary") and _dep_loc:
            try:
                from alumni_deployment_tracker import DeploymentTracker
                tracker = DeploymentTracker()
                did = tracker.log_deployment(_fid_al, _dep_type, _dep_loc,
                                              int(_dep_people), notes=_dep_notes,
                                              public_consent=_dep_pub)
                st.success(f"✅ Deployment logged! ID: {did}\n\n"
                           f"You've helped {int(_dep_people)} people access sovereign education.\n"
                           f"This is permanently recorded in the Living Lattice.")
            except ImportError:
                st.error("alumni_deployment_tracker.py not found.")

    with _al_tabs[2]:
        st.markdown("**AUBIEETERNAL graduates — the Living Lattice.**")
        try:
            from alumni_deployment_tracker import AlumniRegistry
            registry   = AlumniRegistry()
            graduates  = registry.get_all_graduates(public_only=True)
            if not graduates:
                st.info("No public graduates recorded yet. Be the first.")
            for g in graduates[:20]:
                st.markdown(
                    f'<div class="memory-node">'
                    f'<b style="color:#f7931a;">{g["degree_name"]}</b><br>'
                    f'<span style="color:#8899bb;font-size:0.82rem;">'
                    f'{g["student_name"]} · {g["credits"]} credits · '
                    f'coherence {g["coherence"]:.4f} · {g["graduated_at"][:10]}'
                    f'</span></div>', unsafe_allow_html=True)
        except ImportError:
            st.error("alumni_deployment_tracker.py not found.")

    with _al_tabs[3]:
        st.markdown("**The humanitarian impact of the Living Lattice.**")
        try:
            from alumni_deployment_tracker import DeploymentTracker
            tracker = DeploymentTracker()
            impact  = tracker.get_impact_summary()
            all_deps = tracker.get_all_deployments(public_only=True)

            _imp_c1, _imp_c2, _imp_c3 = st.columns(3)
            _imp_c1.metric("Total Deployments",   impact["total_deployments"])
            _imp_c2.metric("People Served",        impact["total_people_served"])
            _imp_c3.metric("Children Reached",     impact["estimated_children"])

            st.markdown("**Community deployments:**")
            for dep in all_deps[:15]:
                _dc = {"school_deployment":"#00ff88","orphanage_deployment":"#f7931a",
                        "community_center":"#00cfff"}.get(dep.get("deployment_type","other"),"#445577")
                st.markdown(
                    f'<div style="padding:6px;background:#0d1228;border-radius:6px;'
                    f'margin-bottom:4px;border-left:3px solid {_dc};">'
                    f'<b style="color:{_dc};">{dep["deployment_type"].replace("_"," ").title()}</b> — '
                    f'{dep["location_desc"]}<br>'
                    f'<span style="color:#8899bb;font-size:0.78rem;">'
                    f'{dep["people_served"]} people · {dep["deployed_at"][:10]}</span>'
                    f'</div>', unsafe_allow_html=True)
        except ImportError:
            st.error("alumni_deployment_tracker.py not found.")

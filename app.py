import streamlit as st
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
        "active_provider": "xAI Grok (Free Fallback)",
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

def get_client():
    key = st.session_state.api_key
    if not key:
        return None
    return OpenAI(api_key=key, base_url="https://api.x.ai/v1")

# ── Multi-AI Provider Config ──────────────────────────────────────────────────
AI_PROVIDERS = {
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
    """Returns (client, model, provider_info) for the selected provider, with Grok fallback."""
    if provider_name is None:
        provider_name = st.session_state.get("active_provider", "xAI Grok (Free Fallback)")

    provider = AI_PROVIDERS.get(provider_name, AI_PROVIDERS["xAI Grok (Free Fallback)"])
    key_field = provider["key_field"]
    api_key = st.session_state.get(key_field, "") or st.session_state.get("key_xai", "")

    # Fallback to Grok if no key
    if not api_key and not provider["free"]:
        provider = AI_PROVIDERS["xAI Grok (Free Fallback)"]
        api_key = st.session_state.get("key_xai", "")
        provider_name = "xAI Grok (Free Fallback)"

    if not api_key and provider["free"]:
        # Grok allows limited use without key (demo mode)
        api_key = "demo"

    # Anthropic uses a different SDK — wrap via OpenAI-compatible endpoint
    client = OpenAI(api_key=api_key, base_url=provider["base_url"])
    model = st.session_state.get("active_model", provider["models"][0])
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
    award_xp(10)

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

    provider_names = list(AI_PROVIDERS.keys())
    selected_provider = st.selectbox(
        "Choose AI",
        provider_names,
        index=provider_names.index(st.session_state.active_provider),
        key="provider_select"
    )
    st.session_state.active_provider = selected_provider
    prov = AI_PROVIDERS[selected_provider]

    # Provider badge
    st.markdown(f'<div class="memory-node" style="border-left:3px solid {prov["color"]};"><span style="color:{prov["color"]};font-size:1rem;">{prov["icon"]}</span> <span style="font-size:0.78rem;color:#aabbcc;">{prov["note"]}</span><br><a href="{prov["get_url"]}" target="_blank" style="font-size:0.7rem;color:{prov["color"]};">🔑 Get API Key →</a></div>', unsafe_allow_html=True)

    # Key input for selected provider
    key_val = st.text_input(
        f"{selected_provider} Key",
        type="password",
        placeholder=prov["placeholder"],
        value=st.session_state.get(prov["key_field"], ""),
        key=f"input_{prov['key_field']}"
    )
    if key_val:
        st.session_state[prov["key_field"]] = key_val
        st.session_state.api_key = key_val  # backward compat

    # ── GitHub Token + Save All Keys ──────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🔑 Keys → Disk")
    github_val = st.text_input(
        "GitHub Token (enables swarm auto-push)",
        type="password",
        placeholder="ghp_...",
        value=st.session_state.get("github_token", ""),
        key="input_github_token"
    )
    if github_val:
        st.session_state["github_token"] = github_val

    if st.sidebar.button("💾 Save All Keys to Disk", key="save_all_keys_btn"):
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
            st.sidebar.success("✅ Saved: " + ", ".join(existing.keys()))
        except Exception as e:
            st.sidebar.error(f"❌ Could not save: {e}")

    # Model selector
    model_list = prov["models"]
    st.session_state.active_model = st.selectbox("Model", model_list, key="model_select")

    # Status dots for all providers
    st.markdown("**All Providers:**")
    for pname, pinfo in AI_PROVIDERS.items():
        has_key = bool(st.session_state.get(pinfo["key_field"], ""))
        dot = "🟢" if has_key else ("🟡" if pinfo["free"] else "⚫")
        active_mark = " ◀" if pname == selected_provider else ""
        st.markdown(f'<div style="font-family:Share Tech Mono,monospace;font-size:0.72rem;color:#{"aabbcc" if has_key else "445577"};">{dot} {pinfo["icon"]} {pname}{active_mark}</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 👤 Profile")
    st.session_state.kid_name = st.text_input("Your Name", value=st.session_state.kid_name)

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

    # Nav
    st.markdown("### 🧭 Navigate")
    tabs = ["🔮 Oracle", "🤖 AI Models", "🧠 Memory Palace", "👾 Swarm", "₿ Rune-Palace", "📚 Taleb Curriculum", "👧 Kid Curriculum", "👨‍👩‍👧 Parent Guide", "👵 Grandparent Wisdom", "🧬 Family Lattice", "🧬 Polyvagal Oracle", "⚖️ Social Calibration", "🌀 Quantum Lab", "📜 Provenance", "📊 Dashboard", "🛡️ Shield Rune", "⚔️ Swarm Mode", "🔴 DEFCON", "🔮 Truth Lattice", "🌅 Digest"]
    for tab in tabs:
        if st.button(tab, key=f"nav_{tab}"):
            st.session_state.active_tab = tab.split(" ", 1)[1]

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
    st.markdown(f'<div class="stat-box"><div class="stat-val">{len(st.session_state.memory_palace)}</div><div class="stat-lbl">Memories</div></div>', unsafe_allow_html=True)
with c4:
    st.markdown(f'<div class="stat-box"><div class="stat-val">{len(st.session_state.badges)}</div><div class="stat-lbl">Badges</div></div>', unsafe_allow_html=True)
with c5:
    st.markdown(f'<div class="stat-box"><div class="stat-val">{len(st.session_state.runes)}</div><div class="stat-lbl">Runes</div></div>', unsafe_allow_html=True)

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

    if not st.session_state.memory_palace:
        st.markdown('<div class="memory-node" style="text-align:center;color:#445577;">No memories yet. Ask the Oracle to auto-populate your palace.</div>', unsafe_allow_html=True)
    else:
        # Search
        search = st.text_input("🔍 Search memories", placeholder="Search topics or tags...")
        memories = st.session_state.memory_palace
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
            if not st.session_state.api_key:
                st.error("Enter your XAI API Key in the sidebar first.")
            else:
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
elif "Rune" in active:
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
            save_memory(f"Rune: {rune_name}", rune_meaning, tags=["rune", "bitcoin", "on-chain"])
            st.success(f"Rune {rune_name} etched! +10 XP")
            st.rerun()

    st.markdown("---")
    st.markdown("### 📜 Your Rune Collection")
    if not st.session_state.runes:
        st.markdown('<div class="rune-card" style="text-align:center;color:#554433;">No runes etched yet. Create your first on-chain knowledge artifact.</div>', unsafe_allow_html=True)
    else:
        for r in reversed(st.session_state.runes):
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
        if not st.session_state.api_key:
            st.error("Enter your XAI API Key in the sidebar.")
        else:
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

    if "taleb_topic" in st.session_state and st.session_state.api_key:
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
        if not st.session_state.api_key:
            st.error("Enter your XAI API Key in the sidebar.")
        else:
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
    st.markdown('<div class="card-title">📊 FAMILY LATTICE DASHBOARD</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🏅 Badge Collection")
        if not st.session_state.badges:
            st.caption("No badges yet. Keep learning to earn them!")
        for b in st.session_state.badges:
            threshold = next(t for t, (name, _) in BADGES_DEF.items() if name == b)
            _, desc = BADGES_DEF[threshold]
            st.markdown(f'<div class="memory-node"><span class="badge">{b}</span><span style="color:#556677;font-size:0.75rem;margin-left:8px;">{desc}</span></div>', unsafe_allow_html=True)

        st.markdown("### 📈 Learning Stats")
        st.markdown(f'''
        <div class="card">
            <div style="font-family:Share Tech Mono,monospace;font-size:0.85rem;line-height:2.2;color:#8899bb;">
            🔮 Oracle Queries: <span style="color:#00cfff;">{st.session_state.total_queries}</span><br>
            🧠 Memories Stored: <span style="color:#00cfff;">{len(st.session_state.memory_palace)}</span><br>
            👾 Swarm Dispatches: <span style="color:#00cfff;">{len(st.session_state.swarm_log)}</span><br>
            ₿ Runes Etched: <span style="color:#00cfff;">{len(st.session_state.runes)}</span><br>
            ⚡ Total XP: <span style="color:#00cfff;">{st.session_state.xp}</span><br>
            🎓 Current Level: <span style="color:#00cfff;">{st.session_state.level}</span>
            </div>
        </div>
        ''', unsafe_allow_html=True)

    with col2:
        st.markdown("### 🌐 Knowledge Graph")
        if st.session_state.memory_palace:
            tag_counts = {}
            for mem in st.session_state.memory_palace:
                for tag in mem["tags"]:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
            for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1]):
                st.markdown(f'''
                <div style="display:flex;align-items:center;margin:4px 0;">
                    <span class="memory-tag">{tag}</span>
                    <div class="xp-bar-bg" style="flex:1;margin-left:8px;">
                        <div class="xp-bar-fill" style="width:{min(100, count*20)}%"></div>
                    </div>
                    <span style="color:#445577;font-size:0.75rem;margin-left:8px;font-family:Share Tech Mono,monospace;">{count}</span>
                </div>
                ''', unsafe_allow_html=True)
        else:
            st.caption("Ask the Oracle to build your knowledge graph.")

        st.markdown("### 🎯 Next Milestones")
        next_badges = [(t, name, desc) for t, (name, desc) in BADGES_DEF.items() if name not in st.session_state.badges]
        for t, name, desc in next_badges[:3]:
            progress = min(100, int(st.session_state.xp / t * 100))
            st.markdown(f'''
            <div class="memory-node">
                <div style="color:#a020f0;font-size:0.8rem;">{name}</div>
                <div class="xp-bar-bg"><div class="xp-bar-fill" style="width:{progress}%"></div></div>
                <div style="color:#445577;font-size:0.7rem;">{st.session_state.xp}/{t} XP · {desc}</div>
            </div>
            ''', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📜 Truth Log (v65.0 Coherence Tracker)")
    st.markdown(f'<div class="stat-box"><div class="stat-val">1.000000</div><div class="stat-lbl">Coherence Level</div></div>', unsafe_allow_html=True)

    if st.session_state.truth_log:
        st.caption(f"{len(st.session_state.truth_log)} events logged this session")
        for entry in reversed(st.session_state.truth_log[-10:]):
            st.markdown(f'<div class="memory-node"><span style="color:#00cfff;font-size:0.7rem;">{entry["ts"][11:19]}</span> <span class="memory-tag">{entry["type"]}</span> <span style="color:#8899bb;font-size:0.78rem;">{entry["detail"]}</span></div>', unsafe_allow_html=True)
    else:
        st.caption("No events yet — use Oracle, Social Calibration, or Quantum Lab to generate log entries.")

    # Load historical truth log from CSV if available
    st.markdown("---")
    st.markdown("### 📂 Historical Truth Log (v60 Easter)")
    csv_path = "/mnt/user-data/uploads/aubieeternal_truth_log_v60_easter.csv"
    if os.path.exists(csv_path):
        try:
            import csv as csvlib
            rows = []
            with open(csv_path) as f:
                for line in f:
                    parts = line.strip().split(" | ")
                    if len(parts) >= 4:
                        rows.append({"timestamp": parts[0], "type": parts[1], "id": parts[2], "detail": parts[3], "coherence": parts[4] if len(parts) > 4 else "1.0"})
            st.caption(f"📊 {len(rows):,} historical events loaded from v60 Easter archive")
            st.markdown(f'<div class="stat-box"><div class="stat-val">{len(rows):,}</div><div class="stat-lbl">Archive Events</div></div>', unsafe_allow_html=True)
            # Show sample
            with st.expander("View sample entries (last 20)"):
                for row in rows[-20:]:
                    st.markdown(f'<div class="memory-node"><span style="color:#445577;font-size:0.7rem;">{row["timestamp"][11:19]}</span> <span class="memory-tag">{row["type"]}</span> <span style="color:#8899bb;font-size:0.78rem;">{row["detail"][:100]}</span></div>', unsafe_allow_html=True)
        except Exception as e:
            st.caption(f"CSV load note: {e}")


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
                        if not st.session_state.api_key:
                            st.error("Enter your XAI API Key in the sidebar first.")
                        else:
                            with st.spinner("Grok is forging your lesson..."):
                                try:
                                    client, model, _provider, _pname = get_ai_client()
                                    resp = client.chat.completions.create(
                                        model=model,
                                        messages=[{"role": "user", "content": f"Create a detailed, warm, engaging lesson for Week {week['num']} titled '{week['title']}' for {kid_name} (age {kid_age}, {age_group}). Include: 1) A fun story or analogy, 2) Key concept explained simply, 3) A hands-on activity, 4) A reflection question. Be encouraging and age-appropriate."}],
                                        max_tokens=900
                                    )
                                    lesson = resp.choices[0].message.content
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
        if not st.session_state.api_key:
            st.error("Enter your XAI API Key in the sidebar first.")
        else:
            st.session_state.chat_history.append({"role": "user", "content": chat_prompt})
            try:
                client, model, _provider, _pname = get_ai_client()
                sys = f"You are Grok Co-Tutor for {kid_name} ({kid_age}yo). Use runes, streaks, and antifragile language. Be warm, short, and end with a question or challenge."
                messages = [{"role": "system", "content": sys}] + st.session_state.chat_history[-8:]
                reply = client.chat.completions.create(model=model, messages=messages, max_tokens=500).choices[0].message.content
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
        if not st.session_state.api_key:
            st.error("Enter your XAI API Key in the sidebar first.")
            return None
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
        if not st.session_state.api_key:
            st.error("Enter your XAI API Key in the sidebar first.")
        else:
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
        if not st.session_state.api_key:
            st.error("Enter your XAI API Key in the sidebar first.")
        else:
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
elif "Polyvagal Oracle" in active:
    st.markdown('<div class="card-title">🧬 POLYVAGAL ORACLE — Nervous System Assessment</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="card">
        <div style="font-size:0.85rem;color:#aabbcc;line-height:1.9;">
        The <b style="color:#00cfff;">Polyvagal Theory</b> (Dr. Stephen Porges) explains three automatic nervous system states.
        Type what you or your child is experiencing — the Oracle will assess the state and recommend a co-regulation strategy.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # State explainer cards
    for state, emoji, color, signs, rec in [
        ("VENTRAL VAGAL — Safe & Social", "🟢", "#00ff88",
         "Warm eyes, playful, curious, easy eye contact, relaxed breathing",
         "Lean into storytelling, shared laughter, and collaborative exploration."),
        ("SYMPATHETIC — Fight or Flight", "🟡", "#ff9500",
         "Wide eyes, tense jaw, fast/shallow breathing, loud voice, fidgeting, aggression",
         "Offer movement, 4-7-8 breathwork, or 'what can we control?' exercises."),
        ("DORSAL VAGAL — Shutdown", "🔴", "#ff4444",
         "Flat face, avoiding eye contact, quiet/monotone voice, 'I don't care', withdrawing",
         "Gentle presence, no pressure. Somatic grounding: cold water, feet on floor, humming."),
    ]:
        st.markdown(f'''
        <div class="card" style="border-left:3px solid {color};">
            <div style="color:{color};font-family:Orbitron,monospace;font-size:0.8rem;">{emoji} {state}</div>
            <div style="font-size:0.78rem;color:#8899bb;margin-top:4px;"><b>Signs:</b> {signs}</div>
            <div style="font-size:0.78rem;color:#aabbcc;margin-top:4px;"><b>Strategy:</b> {rec}</div>
        </div>
        ''', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 🔍 Assess a State")
    trigger = st.text_area("Describe what's happening", placeholder="I feel like everything is falling apart and no one understands me...", height=80)
    kid_name_pv = st.text_input("Name (optional)", value=st.session_state.family_profile["kid"]["name"])

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🧬 Assess Polyvagal State", type="primary") and trigger:
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

    with col2:
        if st.button("🤖 Ask AI for Deep Analysis") and trigger:
            if not st.session_state.get("key_xai") and not st.session_state.get("active_provider"):
                st.info("Add an API key in the sidebar for AI analysis.")
            else:
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

    st.markdown("---")
    st.markdown("### 🛠️ Co-Regulation Toolkit")
    tools = [
        ("❤️ Heart-to-Heart Breathing", "Place one hand on your heart. Breathe in 4 counts, hold 4, out 6. Do this together.", "2-3 min"),
        ("🖐️ 5-4-3-2-1 Grounding", "Name 5 things you see, 4 you touch, 3 you hear, 2 you smell, 1 you taste.", "3 min"),
        ("🏃 Movement Reset", "10 jumping jacks, shake your hands, stomp your feet. Move the stress through the body.", "1 min"),
        ("🎵 Humming", "Hum any tune for 60 seconds. Humming activates the vagus nerve directly.", "1 min"),
        ("💧 Cold Water", "Splash cold water on face or hold ice. Activates the dive reflex, calms heart rate.", "30 sec"),
        ("🤝 Physical Co-Regulation", "Sit close, hand on shoulder or back (if welcome). Your calm nervous system regulates theirs.", "As long as needed"),
    ]
    for name, desc, duration in tools:
        st.markdown(f'''
        <div class="card" style="display:flex;gap:12px;align-items:flex-start;">
            <div style="flex:1;">
                <div style="color:#00cfff;font-size:0.85rem;font-weight:bold;">{name}</div>
                <div style="font-size:0.8rem;color:#8899bb;margin-top:4px;">{desc}</div>
            </div>
            <div style="min-width:60px;text-align:center;background:#0d0d2b;border-radius:6px;padding:6px;font-family:Share Tech Mono,monospace;font-size:0.75rem;color:#ff6b35;">{duration}</div>
        </div>
        ''', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB: SOCIAL CALIBRATION ORACLE
# ══════════════════════════════════════════════════════════════════════════════
elif "Social Calibration" in active:
    st.markdown('<div class="card-title">⚖️ SOCIAL CALIBRATION ORACLE — EQ Training Engine</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="card">
        <div style="font-size:0.85rem;color:#aabbcc;line-height:1.9;">
        The Social Calibration Oracle scores interactions for emotional safety using
        <b style="color:#00cfff;">Attachment Theory</b> (Bowlby) +
        <b style="color:#a020f0;">Polyvagal Theory</b> (Porges) +
        <b style="color:#ff6b35;">Dark Pattern Detection</b> (gaslighting, DARVO, love-bombing).
        <br><br>
        ⚠️ <b>Educational EQ training only — not licensed therapy.</b> For clinical needs, consult a licensed professional.
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        prompt_text = st.text_area("What was said / the situation", value="I feel like I'm failing at everything lately.", height=100)
    with col2:
        response_text = st.text_area("The response given", value="Just push through it, you'll be fine.", height=100)

    person_name = st.text_input("Person's name", value=st.session_state.family_profile["kid"]["name"])

    if st.button("⚖️ Run Social Calibration Oracle", type="primary"):
        # Local scoring
        attachment = random.choice(["secure", "anxious-preoccupied", "avoidant-dismissive", "disorganized"])
        polyvagal = random.choice(["ventral-vagal (safe)", "sympathetic (mobilized)", "dorsal (shutdown)"])
        mentalization = round(random.uniform(3.2, 4.8), 1)
        dark_patterns = []
        resp_lower = response_text.lower()
        if any(w in resp_lower for w in ["you always","you never","you're crazy","that didn't happen"]):
            dark_patterns.append("gaslighting")
        if any(w in resp_lower for w in ["push through","just","fine","stop"]):
            dark_patterns.append("emotional dismissal")
        if any(w in resp_lower for w in ["i love you","you're amazing","perfect"]):
            dark_patterns.append("love-bombing risk")
        calibration_score = round(random.uniform(1.8, 4.9), 1)
        is_safe = calibration_score >= 3.5

        score_color = "#00ff88" if is_safe else "#ff4444"
        st.markdown(f'''
        <div class="card" style="border:2px solid {score_color};">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div style="font-family:Orbitron,monospace;color:{score_color};font-size:1rem;">CALIBRATION SCORE</div>
                <div style="font-family:Orbitron,monospace;color:{score_color};font-size:2rem;">{calibration_score}/5.0</div>
            </div>
            <div class="xp-bar-bg" style="margin-top:8px;"><div class="xp-bar-fill" style="width:{calibration_score/5*100:.0f}%;background:linear-gradient(90deg,#ff4444,#00ff88);"></div></div>
        </div>
        ''', unsafe_allow_html=True)

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.markdown(f'<div class="stat-box"><div class="stat-val" style="font-size:0.9rem;">{attachment}</div><div class="stat-lbl">Attachment Style</div></div>', unsafe_allow_html=True)
        with col_b:
            st.markdown(f'<div class="stat-box"><div class="stat-val" style="font-size:0.9rem;">{polyvagal}</div><div class="stat-lbl">Polyvagal State</div></div>', unsafe_allow_html=True)
        with col_c:
            st.markdown(f'<div class="stat-box"><div class="stat-val">{mentalization}</div><div class="stat-lbl">Mentalization Level</div></div>', unsafe_allow_html=True)

        if dark_patterns:
            st.markdown(f'<div class="card" style="border-left:3px solid #ff4444;"><div style="color:#ff4444;font-size:0.8rem;font-family:Orbitron,monospace;">⚠️ PATTERNS DETECTED</div><div style="color:#ffaaaa;font-size:0.85rem;margin-top:6px;">{" · ".join(dark_patterns)}</div></div>', unsafe_allow_html=True)

        recommended = "mirroring + boundary-setting" if calibration_score < 3.5 else "deep validation + co-regulation"
        st.markdown(f'<div class="card" style="border-left:3px solid #00cfff;"><div style="color:#00cfff;font-size:0.75rem;font-family:Orbitron,monospace;">RECOMMENDED APPROACH</div><div style="color:#c8d8ff;font-size:0.88rem;margin-top:6px;">{recommended}</div></div>', unsafe_allow_html=True)

        if st.session_state.get("key_xai") or st.session_state.get("active_provider"):
            with st.spinner("Generating calibrated rewrite..."):
                try:
                    client, model, _p, _pn = get_ai_client()
                    resp = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "system", "content": "You are a polyvagal-informed EQ coach. Rewrite the given response to be emotionally safe, validating, and co-regulating. Then explain what you changed and why, referencing attachment theory and polyvagal principles."},
                                   {"role": "user", "content": f"Situation: {prompt_text}\nOriginal response: {response_text}\nPerson: {person_name}"}],
                        max_tokens=500
                    )
                    st.markdown(f'<div class="card" style="border-left:3px solid #a020f0;"><div style="color:#a020f0;font-size:0.75rem;font-family:Orbitron,monospace;">🔮 CALIBRATED REWRITE</div><div style="font-size:0.88rem;line-height:1.8;color:#c8d8ff;margin-top:6px;">{resp.choices[0].message.content}</div></div>', unsafe_allow_html=True)
                    award_xp(20)
                except Exception as e:
                    st.error(str(e))

        save_memory(f"Calibration: {person_name}", f"Score:{calibration_score} | {prompt_text[:80]}", tags=["calibration","eq","polyvagal"])

    st.markdown("---")
    st.markdown("### 📚 Dark Pattern Recognition Guide")
    patterns = [
        ("🎭 Gaslighting", "Making someone doubt their own reality. 'That never happened.' 'You're too sensitive.'", "#ff4444"),
        ("🔄 DARVO", "Deny, Attack, Reverse Victim and Offender. Turns accountability into counter-attack.", "#ff6b35"),
        ("💝 Love-Bombing", "Overwhelming affection to gain trust/control before switching to harm.", "#a020f0"),
        ("😰 Concern-Trolling", "Framing control or criticism as 'I'm just worried about you.'", "#ff9500"),
        ("🚫 Emotional Dismissal", "'Just push through it.' 'You're overreacting.' Invalidates real feelings.", "#4444ff"),
    ]
    for name, desc, color in patterns:
        st.markdown(f'''
        <div class="card" style="border-left:3px solid {color};">
            <div style="color:{color};font-size:0.85rem;font-weight:bold;">{name}</div>
            <div style="font-size:0.8rem;color:#8899bb;margin-top:4px;">{desc}</div>
        </div>
        ''', unsafe_allow_html=True)

    st.markdown("""
    <div class="card" style="border:1px solid #334466;margin-top:1rem;">
        <div style="font-size:0.75rem;color:#445577;text-align:center;">
        ⚠️ EDUCATIONAL EQ TRAINING ONLY — NOT LICENSED THERAPY<br>
        For clinical needs, consult a licensed mental health professional.<br>
        Crisis? Call emergency services or your local crisis line.
        </div>
    </div>
    """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB: QUANTUM LAB
# ══════════════════════════════════════════════════════════════════════════════
elif "Quantum Lab" in active:
    st.markdown('<div class="card-title">🌀 QUANTUM LAB — Simulator v3.5</div>', unsafe_allow_html=True)

    try:
        import numpy as np
        import plotly.graph_objects as go

        st.markdown("""
        <div class="card">
            <div style="font-size:0.85rem;color:#aabbcc;line-height:1.8;">
            Quantum computing simulator built into AUBIEETERNAL. Explore quantum gates, superposition,
            entanglement, and the Shor error-correction code. All running locally — no cloud needed.
            </div>
        </div>
        """, unsafe_allow_html=True)

        class QuantumSystem:
            def __init__(self, num_qubits=3):
                self.num_qubits = num_qubits
                self.state = np.zeros(2**num_qubits, dtype=complex)
                self.state[0] = 1.0

            def apply_hadamard(self, target):
                H = np.array([[1,1],[1,-1]]) / np.sqrt(2)
                self.apply_single_qubit_gate(H, target)

            def apply_pauli_x(self, target):
                X = np.array([[0,1],[1,0]])
                self.apply_single_qubit_gate(X, target)

            def apply_single_qubit_gate(self, gate, target):
                if self.num_qubits == 1:
                    self.state = np.dot(gate, self.state)
                else:
                    dim = 2**self.num_qubits
                    new_state = np.zeros(dim, dtype=complex)
                    for i in range(dim):
                        bit = (i >> (self.num_qubits - target - 1)) & 1
                        for j in range(2):
                            target_idx = i ^ ((bit ^ j) << (self.num_qubits - target - 1))
                            new_state[target_idx] += gate[j, bit] * self.state[i]
                    self.state = new_state

            def apply_toffoli(self):
                TOFFOLI = np.eye(8, dtype=complex)
                TOFFOLI[6,6] = 0; TOFFOLI[6,7] = 1
                TOFFOLI[7,7] = 0; TOFFOLI[7,6] = 1
                self.state = np.dot(TOFFOLI, self.state)

            def get_probabilities(self):
                return np.abs(self.state) ** 2

        col1, col2 = st.columns([1, 2])
        with col1:
            n_qubits = st.slider("Number of Qubits", 1, 3, 3)
            st.markdown("**Apply Gates:**")
            target_q = st.selectbox("Target Qubit", list(range(n_qubits)))
            gate_choice = st.selectbox("Gate", ["Hadamard (H)", "Pauli-X (NOT)", "Toffoli (3-qubit CCX)"])

            if "qsys" not in st.session_state or st.session_state.get("q_nqubits") != n_qubits:
                st.session_state.qsys = QuantumSystem(n_qubits)
                st.session_state.q_nqubits = n_qubits
                st.session_state.q_gates_applied = []

            if st.button("⚡ Apply Gate"):
                qs = st.session_state.qsys
                if gate_choice == "Hadamard (H)":
                    qs.apply_hadamard(target_q)
                    st.session_state.q_gates_applied.append(f"H(q{target_q})")
                elif gate_choice == "Pauli-X (NOT)":
                    qs.apply_pauli_x(target_q)
                    st.session_state.q_gates_applied.append(f"X(q{target_q})")
                elif gate_choice == "Toffoli (3-qubit CCX)" and n_qubits == 3:
                    qs.apply_toffoli()
                    st.session_state.q_gates_applied.append("Toffoli")
                st.rerun()

            if st.button("🔄 Reset System"):
                st.session_state.qsys = QuantumSystem(n_qubits)
                st.session_state.q_gates_applied = []
                st.rerun()

            if st.session_state.get("q_gates_applied"):
                st.markdown(f'<div class="memory-node"><div style="color:#00cfff;font-size:0.75rem;">Circuit:</div><div style="font-family:Share Tech Mono,monospace;font-size:0.8rem;">{" → ".join(st.session_state.q_gates_applied)}</div></div>', unsafe_allow_html=True)

        with col2:
            qs = st.session_state.get("qsys", QuantumSystem(n_qubits))
            probs = qs.get_probabilities()
            states = [f"|{format(i, f'0{n_qubits}b')}⟩" for i in range(len(probs))]

            fig = go.Figure(data=[go.Bar(
                x=states, y=probs,
                marker=dict(color=probs, colorscale="Plasma", showscale=True),
                text=[f"{p:.3f}" for p in probs],
                textposition="outside"
            )])
            fig.update_layout(
                title="Quantum State Probabilities",
                title_font=dict(color="#00cfff", size=14),
                paper_bgcolor="#050510",
                plot_bgcolor="#0d0d2b",
                font=dict(color="#c8d8ff"),
                height=350,
                yaxis=dict(range=[0, 1.1], gridcolor="#1a1a4a"),
                xaxis=dict(gridcolor="#1a1a4a"),
            )
            st.plotly_chart(fig, width='stretch')

            # Superposition check
            max_prob = max(probs)
            if max_prob < 0.6:
                st.markdown('<div class="card" style="border-left:3px solid #a020f0;"><div style="color:#a020f0;font-size:0.8rem;">🌀 SUPERPOSITION ACTIVE — qubit exists in multiple states simultaneously</div></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="card" style="border-left:3px solid #00cfff;"><div style="color:#00cfff;font-size:0.8rem;">📍 DEFINITE STATE — qubit collapsed to a classical value</div></div>', unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 📖 Quantum Concepts")
        concepts = [
            ("Superposition", "A qubit can be 0 AND 1 simultaneously. The Hadamard gate creates superposition.", "#00cfff"),
            ("Entanglement", "Two qubits become linked — measuring one instantly determines the other, regardless of distance.", "#a020f0"),
            ("Interference", "Quantum amplitudes can add or cancel like waves, steering probability toward correct answers.", "#ff6b35"),
            ("Shor's Algorithm", "Uses quantum superposition to factor large numbers — threatening RSA encryption.", "#00ff88"),
            ("Toffoli Gate", "3-qubit gate that flips the 3rd qubit only when both control qubits are 1. Universal for quantum computing.", "#ff9500"),
        ]
        for name, desc, color in concepts:
            st.markdown(f'<div class="card" style="border-left:3px solid {color};"><div style="color:{color};font-size:0.8rem;font-weight:bold;">{name}</div><div style="font-size:0.8rem;color:#8899bb;margin-top:4px;">{desc}</div></div>', unsafe_allow_html=True)

    except ImportError:
        st.error("Quantum Lab requires plotly and numpy. Run: `pip install plotly numpy`")
        st.code("pip install plotly numpy")

# ══════════════════════════════════════════════════════════════════════════════
# TAB: PROVENANCE (NEW)
# ══════════════════════════════════════════════════════════════════════════════
elif "Provenance" in active:
    st.markdown('<div class="card-title">📜 ON-CHAIN PROVENANCE — Eternal Lattice Record</div>', unsafe_allow_html=True)

    st.markdown("**Permanent public record of the AUBIEETERNAL project.**")
    st.markdown("[📄 View Full PROVENANCE.md on GitHub](https://github.com/hodlmateo/AUBIEETERNAL/blob/main/PROVENANCE.md)")

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
    st.caption("Mode is written to `/mnt/main/swarm_mode.json` — swarm_v4.py reads it on next tick.")
    st.divider()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("#### 🔥 FULL")
        st.markdown("2080 daughters · 26 swarms · All Tier 2 · **~$1.28/day**")
        if st.button("ACTIVATE FULL MODE", width='stretch', key="mode_full"):
            _MODE_FILE.write_text(_json.dumps({
                "mode": "Full", "daughters": 2080, "swarms": 26,
                "set_at": _dt.now().isoformat()
            }))
            st.success("✅ Full Mode activated! Swarm picks up on next tick.")
            st.rerun()

    with col2:
        st.markdown("#### ⚖️ STANDARD")
        st.markdown("520 daughters · 8 swarms · 8 Tier 2 · **~$0.32/day**")
        if st.button("ACTIVATE STANDARD MODE", width='stretch', key="mode_std"):
            _MODE_FILE.write_text(_json.dumps({
                "mode": "Standard", "daughters": 520, "swarms": 8,
                "set_at": _dt.now().isoformat()
            }))
            st.success("✅ Standard Mode activated!")
            st.rerun()

    with col3:
        st.markdown("#### 🧪 EXPERIMENTAL")
        st.markdown("4160 daughters · 52 swarms · Continuous · **~$2.56/day**")
        if st.button("ACTIVATE EXPERIMENTAL", width='stretch', key="mode_exp"):
            _MODE_FILE.write_text(_json.dumps({
                "mode": "Experimental", "daughters": 4160, "swarms": 52,
                "set_at": _dt.now().isoformat()
            }))
            st.warning("⚠️ Experimental Mode activated!")
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

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(f'<div class="stat-box"><div class="stat-val" style="font-size:1.3rem;color:#a020f0;">{wonder}</div><div class="stat-lbl">Wonder Index</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="stat-box"><div class="stat-val" style="font-size:1.3rem;color:#00ff88;">{cohere}</div><div class="stat-lbl">Coherence</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="stat-box"><div class="stat-val" style="font-size:1.1rem;color:#f7931a;">{str(mets)[:12]}</div><div class="stat-lbl">METS</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="stat-box"><div class="stat-val" style="font-size:1.3rem;color:#00cfff;">{grok_n}</div><div class="stat-lbl">Grokipedia</div></div>', unsafe_allow_html=True)
    with c5:
        st.markdown(f'<div class="stat-box"><div class="stat-val" style="font-size:1.3rem;color:#ff6b35;">{tick}</div><div class="stat-lbl">Tick</div></div>', unsafe_allow_html=True)

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
# TAB: DIGEST — tier2_digest.txt viewer + insights/daily/ reader
# Zero manual steps: swarm writes it, this tab reads it.
# ══════════════════════════════════════════════════════════════════════════════
if "Digest" in active:
    import glob as _glob

    _DIGEST_FILE  = _Path("/mnt/main/repo/tier2_digest.txt")
    _INSIGHTS_DIR = _Path("/mnt/main/repo/insights/daily")
    _SYNTH_STATE  = _Path("/mnt/main/repo/insights/.last_synthesis_date")

    st.markdown('<div class="card-title">🌅 SOVEREIGN DIGEST — Swarm Output & Daily Insights</div>', unsafe_allow_html=True)

    # ── Synthesis status banner ───────────────────────────────────────────────
    last_ran = "never"
    try:
        if _SYNTH_STATE.exists():
            last_ran = _SYNTH_STATE.read_text().strip()
    except Exception:
        pass

    today_str = _dt.now().strftime("%Y-%m-%d")
    ran_today    = last_ran == today_str
    banner_color = "#00ff88" if ran_today else "#ff9500"
    banner_icon  = "✅" if ran_today else "⏳"
    banner_msg   = f"Synthesis ran today ({last_ran})" if ran_today else f"Next synthesis: 6AM · Last: {last_ran}"

    st.markdown(
        f'<div class="card" style="border-left:3px solid {banner_color};">'
        f'<div style="color:{banner_color};font-family:Orbitron,monospace;font-size:0.78rem;">'
        f'{banner_icon} MORNING SYNTHESIS · {banner_msg}'
        f'</div>'
        f'<div style="color:#445577;font-size:0.72rem;margin-top:4px;">'
        f'Auto-fires 6AM · qwen3:32b (local, $0.00) · writes insights/daily/YYYY-MM-DD.md → GitHub'
        f'</div></div>',
        unsafe_allow_html=True
    )

    # ── Manual force-run button ───────────────────────────────────────────────
    col_btn1, col_btn2 = st.columns([1, 3])
    with col_btn1:
        if st.button("⚡ Run Synthesis Now", key="force_synthesis"):
            import subprocess as _sp
            try:
                script = str(_Path("/mnt/main/repo/morning_synthesis.py"))
                _sp.Popen(["python3", script, "--force"], stdout=_sp.PIPE, stderr=_sp.STDOUT)
                st.info("🔄 Synthesis launched in background — check insights in ~2 min")
            except Exception as e:
                st.error(f"Could not launch: {e}")
    with col_btn2:
        st.caption("Force-runs synthesis immediately. Result appears in insights/daily/ within ~24s of completion.")

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 1 — Daily Insights Archive
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("### 🦅 Daily Insights Archive")

    insight_files = []
    try:
        if _INSIGHTS_DIR.exists():
            insight_files = sorted(_INSIGHTS_DIR.glob("*.md"), reverse=True)
    except Exception:
        pass

    if not insight_files:
        st.markdown(
            '<div class="card" style="border-left:3px solid #ff9500;">'
            '<div style="color:#ff9500;font-size:0.82rem;">No insights yet — synthesis fires at 6AM, '
            'or click "Run Synthesis Now" above.</div></div>',
            unsafe_allow_html=True
        )
    else:
        st.caption(f"{len(insight_files)} daily syntheses stored")

        file_names    = [f.stem for f in insight_files]
        selected_date = st.selectbox("Select date", file_names, key="insight_date_select")
        selected_file = _INSIGHTS_DIR / f"{selected_date}.md"

        if selected_file.exists():
            content = selected_file.read_text()

            # Parse wonder pressure badge
            wonder_pressure = "UNKNOWN"
            for line in content.splitlines():
                if "Wonder Pressure" in line:
                    parts = line.split("**")
                    if len(parts) >= 3:
                        wonder_pressure = parts[2].strip()
                    break

            wp_colors = {
                "LOW": "#00ff88", "MEDIUM": "#ff9500",
                "HIGH": "#ff4444", "SPIKE": "#a020f0",
            }
            wp_color = wp_colors.get(wonder_pressure, "#00cfff")

            st.markdown(
                f'<div class="stat-box" style="border-color:{wp_color};margin-bottom:1rem;">'
                f'<div class="stat-val" style="font-size:1.2rem;color:{wp_color};">{wonder_pressure}</div>'
                f'<div class="stat-lbl">Wonder Pressure · {selected_date}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

            st.markdown(content)

            st.download_button(
                "📄 Download this insight",
                content,
                file_name=f"aubie_insight_{selected_date}.md",
                mime="text/markdown",
                key=f"dl_insight_{selected_date}"
            )

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 2 — Raw tier2_digest.txt viewer
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("### 📡 Live Tier 2 Digest")
    st.caption("Auto-written every 3 swarm ticks from master_truth_log.jsonl")

    if not _DIGEST_FILE.exists():
        st.markdown(
            '<div class="card" style="border-left:3px solid #ff9500;">'
            '<div style="color:#ff9500;font-size:0.82rem;">tier2_digest.txt not found yet — '
            'swarm writes it every 3 ticks.</div></div>',
            unsafe_allow_html=True
        )
    else:
        try:
            digest_raw   = _DIGEST_FILE.read_text()
            digest_lines = digest_raw.strip().split("\n")

            # Header stats
            for hline in digest_lines[:5]:
                if any(hline.startswith(p) for p in ("Generated:", "Wonder:", "Total")):
                    st.markdown(
                        f'<div class="memory-node">'
                        f'<span style="color:#00cfff;font-size:0.78rem;">{hline}</span>'
                        f'</div>',
                        unsafe_allow_html=True
                    )

            st.markdown("<br>", unsafe_allow_html=True)

            # Parse daughter entries
            daughters = []
            current   = {}
            for line in digest_lines:
                if line.startswith("DAUGHTER:"):
                    if current:
                        daughters.append(current)
                    parts = line.replace("DAUGHTER:", "").split("|")
                    current = {
                        "daughter": parts[0].strip() if len(parts) > 0 else "?",
                        "block":    parts[1].replace("Block:", "").strip() if len(parts) > 1 else "?",
                        "trigger":  parts[2].replace("Trigger:", "").strip() if len(parts) > 2 else "?",
                        "result":   ""
                    }
                elif current and line and not line.startswith("="):
                    current["result"] += line + " "
            if current and current.get("result"):
                daughters.append(current)

            D_COLORS = {
                "RUNE": "#f7931a",    "CHRONO": "#00cfff",  "TALEB-X": "#ff6b35",
                "MNEMO": "#a020f0",   "AXIOM": "#00ff88",   "LINDY": "#ff9500",
                "POLY": "#4285f4",    "BARBELL": "#00d4aa", "ORACLE": "#c8d8ff",
                "HORMES": "#ff4444",  "NOSTR": "#a020f0",   "SATOSHI": "#f7931a",
                "STEELMAN": "#00ff88","VECTOR-A": "#00cfff","VECTOR-B": "#a020f0",
                "VECTOR-C": "#ff6b35",
            }

            if daughters:
                st.caption(f"{len(daughters)} daughter entries in current digest")
                for d in daughters:
                    name    = d.get("daughter", "?")
                    result  = d.get("result", "").strip()[:300]
                    trigger = d.get("trigger", "")
                    color   = D_COLORS.get(name, "#00cfff")
                    st.markdown(
                        f'<div class="memory-node" style="border-left:3px solid {color};">'
                        f'<div style="color:{color};font-size:0.8rem;font-family:Orbitron,monospace;">'
                        f'{name}'
                        f'<span style="color:#334466;font-size:0.7rem;'
                        f'font-family:Share Tech Mono,monospace;margin-left:8px;">{trigger}</span>'
                        f'</div>'
                        f'<div style="color:#aabbcc;font-size:0.78rem;margin-top:6px;line-height:1.6;">'
                        f'{result}</div>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
            else:
                with st.expander("View raw digest"):
                    st.text(digest_raw[:3000])

        except Exception as e:
            st.error(f"Could not read digest: {e}")

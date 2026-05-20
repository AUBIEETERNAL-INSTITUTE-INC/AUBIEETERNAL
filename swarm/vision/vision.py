import streamlit as st
import base64
import requests
import json
from datetime import datetime
from pathlib import Path

st.set_page_config(
    page_title="AUBIEETERNAL Vision",
    page_icon="👁️",
    layout="centered"
)

# ── Auto-load API key from StartOS persistent volume ──────────────────────────
_env_path = Path("/mnt/main/api_keys.env")
_auto_key = ""
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        if "=" in _line:
            _k, _v = _line.strip().split("=", 1)
            if _k == "XAI_API_KEY" and _v:
                _auto_key = _v

# ── Paths ─────────────────────────────────────────────────────────────────────
VISION_TRIGGER = Path("/mnt/main/repo/vision_trigger.json")
VISION_LOG     = Path("/mnt/main/vision_log.jsonl")

# ── Providers ─────────────────────────────────────────────────────────────────
AI_PROVIDERS = {
    "xAI Grok Vision": {
        "base_url": "https://api.x.ai/v1",
        "model":    "grok-vision-beta",
        "key_hint": "xai-...",
        "free":     True,
    },
    "OpenAI GPT-4o": {
        "base_url": "https://api.openai.com/v1",
        "model":    "gpt-4o",
        "key_hint": "sk-...",
        "free":     False,
    },
    "Anthropic Claude": {
        "base_url": "https://api.anthropic.com/v1",
        "model":    "claude-3-5-sonnet-20241022",
        "key_hint": "sk-ant-...",
        "free":     False,
    },
    "Groq Llama Vision": {
        "base_url": "https://api.groq.com/openai/v1",
        "model":    "llama-3.2-90b-vision-preview",
        "key_hint": "gsk_...",
        "free":     False,
    },
}

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@700;900&family=Share+Tech+Mono&display=swap');
html, body, [class*="css"] {
    background-color: #050510;
    color: #c8d8ff;
    font-family: 'Share Tech Mono', monospace;
}
.stApp { background: radial-gradient(ellipse at 20% 50%, #0a0a2e 0%, #050510 60%); }
h1, h2, h3 { font-family: 'Orbitron', monospace; }
.vision-card {
    background: linear-gradient(135deg, #0d0d2b, #0a0a1e);
    border: 1px solid #1a1a4a;
    border-radius: 12px;
    padding: 1.2rem;
    margin: 0.5rem 0;
}
.result-box {
    background: #0a0a1e;
    border-left: 3px solid #a020f0;
    border-radius: 8px;
    padding: 1rem;
    margin: 0.5rem 0;
    font-size: 0.88rem;
    line-height: 1.8;
    color: #c8d8ff;
}
.swarm-sent {
    background: #0a1a0a;
    border-left: 3px solid #00ff88;
    border-radius: 8px;
    padding: 0.8rem;
    color: #00ff88;
    font-size: 0.85rem;
}
.stButton > button {
    background: linear-gradient(135deg, #0d1a3a, #0a0d2e);
    color: #00cfff;
    border: 1px solid #00cfff44;
    border-radius: 8px;
    font-family: 'Orbitron', monospace;
    font-size: 0.75rem;
    letter-spacing: 0.1em;
    width: 100%;
}
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center;padding:1rem 0;">
    <div style="font-family:Orbitron,monospace;font-size:1.8rem;font-weight:900;
                background:linear-gradient(90deg,#00cfff,#a020f0);
                -webkit-background-clip:text;-webkit-text-fill-color:transparent;">
        👁️ AUBIEETERNAL VISION
    </div>
    <div style="font-family:Share Tech Mono,monospace;color:#445577;font-size:0.75rem;
                letter-spacing:0.3em;margin-top:0.3rem;">
        CAPTURE · ANALYZE · SEND TO SWARM
    </div>
</div>
""", unsafe_allow_html=True)

# ── Provider + Key ────────────────────────────────────────────────────────────
st.markdown("### 🤖 AI Provider")
provider_name = st.selectbox("Choose Vision AI", list(AI_PROVIDERS.keys()))
provider      = AI_PROVIDERS[provider_name]

# Use auto-loaded key if available, otherwise ask
default_key = _auto_key if provider_name == "xAI Grok Vision" else ""
api_key = st.text_input(
    f"API Key{' (auto-loaded ✅)' if default_key else ''}",
    value=default_key,
    type="password",
    placeholder=provider["key_hint"],
)
if not api_key and not provider["free"]:
    st.info("No key → falling back to xAI Grok Vision")
    provider      = AI_PROVIDERS["xAI Grok Vision"]
    provider_name = "xAI Grok Vision"
    api_key       = _auto_key

# ── Image Input ───────────────────────────────────────────────────────────────
st.markdown("### 📸 Image")
col1, col2 = st.columns(2)
with col1:
    uploaded = st.file_uploader("Upload Photo", type=["jpg", "jpeg", "png", "webp"])
with col2:
    camera   = st.camera_input("Take Photo")

image = uploaded or camera

if image:
    st.image(image, caption="Image to analyze", use_container_width=True)

    # ── Prompt ────────────────────────────────────────────────────────────────
    prompt = st.text_area(
        "Analysis prompt",
        value=(
            "Analyze this image in detail. Describe what you see, "
            "emotional cues, environment, any patterns or signals relevant "
            "to the AUBIEETERNAL lattice."
        ),
        height=90,
    )

    # ── Analyze ───────────────────────────────────────────────────────────────
    if st.button("🔍 ANALYZE IMAGE", use_container_width=True):
        with st.spinner(f"Analyzing with {provider_name}..."):
            try:
                img_bytes    = image.getvalue()
                b64_image    = base64.b64encode(img_bytes).decode("utf-8")
                # Detect mime type
                mime = "image/jpeg"
                if hasattr(image, "name"):
                    if image.name.lower().endswith(".png"):
                        mime = "image/png"
                    elif image.name.lower().endswith(".webp"):
                        mime = "image/webp"

                headers = {
                    "Content-Type":  "application/json",
                    "Authorization": f"Bearer {api_key}",
                }
                payload = {
                    "model": provider["model"],
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url",
                             "image_url": {"url": f"data:{mime};base64,{b64_image}"}}
                        ]
                    }],
                    "max_tokens": 800,
                }

                resp = requests.post(
                    f"{provider['base_url']}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60,
                )

                if resp.status_code == 200:
                    analysis = resp.json()["choices"][0]["message"]["content"]
                    st.session_state["last_analysis"]     = analysis
                    st.session_state["last_provider"]     = provider_name
                    st.session_state["last_analysis_ts"]  = datetime.now().isoformat()
                    st.success("✅ Analysis complete")
                else:
                    st.error(f"Error {resp.status_code}: {resp.text[:300]}")

            except Exception as e:
                st.error(f"Error: {e}")

# ── Show last result ──────────────────────────────────────────────────────────
if st.session_state.get("last_analysis"):
    analysis = st.session_state["last_analysis"]
    pname    = st.session_state.get("last_provider", "")
    ts       = st.session_state.get("last_analysis_ts", "")[:16]

    st.markdown(f"""
    <div class="result-box">
        <div style="color:#a020f0;font-size:0.72rem;font-family:Orbitron,monospace;
                    margin-bottom:8px;">👁️ {pname} · {ts}</div>
        {analysis}
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # ── Send to Swarm ─────────────────────────────────────────────────────────
    col_a, col_b = st.columns(2)

    with col_a:
        if st.button("🦅 SEND TO SWARM", use_container_width=True):
            try:
                trigger = {
                    "timestamp": datetime.now().isoformat(),
                    "source":    "vision_app",
                    "provider":  pname,
                    "analysis":  analysis,
                }
                # Write trigger for swarm_v4.py to pick up on next tick
                VISION_TRIGGER.parent.mkdir(parents=True, exist_ok=True)
                VISION_TRIGGER.write_text(json.dumps(trigger, indent=2))

                # Also append to persistent vision log
                VISION_LOG.parent.mkdir(parents=True, exist_ok=True)
                with open(VISION_LOG, "a") as f:
                    f.write(json.dumps(trigger) + "\n")

                st.markdown("""
                <div class="swarm-sent">
                    ✅ Sent to Swarm!<br>
                    <span style="font-size:0.75rem;color:#445577;">
                    swarm_v4.py picks up vision_trigger.json on next tick (~8 sec).<br>
                    Tier 2 daughters will analyze and log to Truth Lattice.
                    </span>
                </div>
                """, unsafe_allow_html=True)

            except Exception as e:
                st.error(f"Failed to send: {e}")

    with col_b:
        if st.button("🗑️ Clear", use_container_width=True):
            for k in ["last_analysis", "last_provider", "last_analysis_ts"]:
                st.session_state.pop(k, None)
            st.rerun()

# ── Vision Log Viewer ─────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 📋 Recent Vision Log")
try:
    if VISION_LOG.exists():
        lines = VISION_LOG.read_text().strip().split("\n")
        entries = []
        for line in reversed(lines[-20:]):
            try:
                entries.append(json.loads(line))
            except Exception:
                pass
        if entries:
            for e in entries[:5]:
                ts  = e.get("timestamp", "")[:16]
                src = e.get("source", "?")
                prv = e.get("provider", "?")
                snip = e.get("analysis", "")[:120]
                st.markdown(
                    f'<div class="vision-card" style="font-size:0.78rem;">'
                    f'<span style="color:#00cfff;">{ts}</span> · '
                    f'<span style="color:#a020f0;">{prv}</span> · '
                    f'<span style="color:#445577;">{src}</span><br>'
                    f'<span style="color:#8899bb;">{snip}…</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )
        else:
            st.caption("No vision entries yet.")
    else:
        st.caption("No vision log yet — analyze and send an image to start.")
except Exception as e:
    st.caption(f"Log unavailable: {e}")

# ── Halo Placeholder ─────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("""
<div class="vision-card" style="border-color:#ff6b3544;text-align:center;">
    <div style="color:#ff6b35;font-family:Orbitron,monospace;font-size:0.8rem;">
        🥽 BRILLIANT LABS HALO — COMING SOON
    </div>
    <div style="color:#554433;font-size:0.75rem;margin-top:6px;">
        Glasses on the way · Order #PNHGW0U8M<br>
        Bluetooth → halo.py → vision_trigger.json → swarm
    </div>
</div>
""", unsafe_allow_html=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center;font-family:Share Tech Mono,monospace;
            font-size:0.7rem;color:#223344;letter-spacing:0.2em;
            margin-top:2rem;">
AUBIEETERNAL · VISION · SOVEREIGN · LOCAL-FIRST
</div>
""", unsafe_allow_html=True)

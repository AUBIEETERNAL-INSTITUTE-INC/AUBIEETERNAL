"""
APP_PY_PATCH.py — Targeted patches for app.py
==============================================
DO NOT overwrite app.py with this file.
Apply each numbered patch to the correct location.

app.py is 6,570 lines. These are surgical additions only.
"""

# ═══════════════════════════════════════════════════════════════════════════
# PATCH 1 — Fix Ollama model list in AI_PROVIDERS (line ~376-383)
# Add 14b and 7b to the models list so they appear in the dropdown
# ═══════════════════════════════════════════════════════════════════════════

# FIND (~line 374):
    "Local Ollama (FREE — qwen3:32b)": {
        "icon": "🏠", "color": "#00ff88",
        "models": ["qwen3:32b", "qwen2.5:32b", "llama3.3:70b"],

# REPLACE WITH:
    "Local Ollama (FREE — qwen3:32b)": {
        "icon": "🏠", "color": "#00ff88",
        "models": [
            "qwen2.5:14b",        # ← RECOMMENDED: fast + smart sweet spot
            "qwen2.5:32b",        # deep reasoning
            "qwen2.5:7b",         # fastest, lightest
            "qwen3:32b",          # best quality, slowest
            "llama3.3:70b",       # ⚠️ avoid — hits 94°C
        ],


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 2 — Add Thinking Mode + Model Router to sidebar (after line ~837)
# FIND: "st.session_state.kid_name = st.text_input("Your Name"..."
# ADD THIS BLOCK immediately after that line:
# ═══════════════════════════════════════════════════════════════════════════

    st.markdown("---")
    st.markdown("### 🧠 Thinking Mode")

    # Load smart model router
    try:
        from ai_model_router import get_model_for_task as _gmft, get_task_type_for_ui_mode as _gttm
        _ROUTER_OK = True
    except ImportError:
        _ROUTER_OK = False

    if "thinking_mode" not in st.session_state:
        st.session_state.thinking_mode = "Balanced"

    thinking_mode = st.radio(
        "Speed vs Quality",
        ["⚡ Fast", "⚖️ Balanced", "🧠 Deep Thinking"],
        index=["⚡ Fast", "⚖️ Balanced", "🧠 Deep Thinking"].index(
            st.session_state.thinking_mode
        ) if st.session_state.thinking_mode in ["⚡ Fast", "⚖️ Balanced", "🧠 Deep Thinking"]
        else 1,
        horizontal=True,
        key="thinking_mode_radio"
    )
    st.session_state.thinking_mode = thinking_mode

    # Auto-select matching Ollama model when in local mode
    if "Local Ollama" in st.session_state.get("active_provider", ""):
        mode_map = {
            "⚡ Fast":         "qwen2.5:7b",
            "⚖️ Balanced":     "qwen2.5:14b",
            "🧠 Deep Thinking": "qwen2.5:32b",
        }
        auto_model = mode_map.get(thinking_mode, "qwen2.5:14b")
        if st.session_state.get("active_model") != auto_model:
            st.session_state.active_model = auto_model
            st.caption(f"🤖 Auto-selected: `{auto_model}`")


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 3 — Add new tabs to the tab list (line ~859)
# FIND the tabs = [...] list and ADD these 3 entries anywhere in the list:
# ═══════════════════════════════════════════════════════════════════════════

# ADD these to the tabs list:
"🦅 Sovereign Life"
"🌐 Epistemic Commons"

# The full updated tabs list (replace the whole line ~859):
tabs = [
    "🔮 Oracle", "🤖 AI Models", "🧠 Memory Palace", "👾 Swarm",
    "₿ Rune-Palace", "📚 Taleb Curriculum", "👧 Kid Curriculum",
    "👨‍👩‍👧 Parent Guide", "👵 Grandparent Wisdom", "🧬 Family Lattice",
    "🧬 Polyvagal Oracle", "⚖️ Social Calibration", "🌀 Quantum Lab",
    "📜 Provenance", "📊 Dashboard", "🛡️ Shield Rune", "⚔️ Swarm Mode",
    "🔴 DEFCON", "🔮 Truth Lattice", "🌅 Digest", "🥽 Family Co-Learning",
    "📡 Nostr Bridge", "📚 Grokipedia", "👨‍👩‍👧‍👦 4 Families", "🧪 Sandbox Lab",
    "⚡ Bitcoin", "🎮 Daily Quests", "🏫 School", "📈 Parent Dashboard",
    "🗺️ Curriculum Map", "📣 Share to X", "💬 Family Messaging",
    "👥 Family Groups",
    # ── NEW TABS ──────────────────────────────────────────────────────────
    "🦅 Sovereign Life",
    "🌐 Epistemic Commons",
]


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 4 — Add Family Contribution Bridge to Sandbox Lab tab
# FIND: "elif "Sandbox" in active:" somewhere in the file
# ADD this block inside the Sandbox Lab tab section:
# ═══════════════════════════════════════════════════════════════════════════

    st.divider()
    st.markdown("### 🧬 Family Contribution Bridge")
    st.markdown("Approved family creations can influence the live swarm as mini-daughters.")

    try:
        from swarm_contributions import get_and_register_new_contributions
        from ai_sandbox_persistence import (
            load_swarm_submissions, append_swarm_submission,
            get_recent_injections
        )
        _SANDBOX_OK = True
    except ImportError:
        _SANDBOX_OK = False
        st.warning("swarm_contributions.py or ai_sandbox_persistence.py not found")

    if _SANDBOX_OK:
        # Master toggle
        inject_enabled = st.toggle(
            "✅ Allow approved family contributions into the live swarm",
            value=st.session_state.get("family_injection_enabled", True),
            key="family_injection_toggle"
        )
        st.session_state["family_injection_enabled"] = inject_enabled

        # Live metrics
        all_subs = load_swarm_submissions()
        pending_n  = len([s for s in all_subs if s.get("status","pending") == "pending"])
        approved_n = len([s for s in all_subs if s.get("status") == "approved"])
        active_n   = len([s for s in all_subs if s.get("status") == "injected"])

        sb1, sb2, sb3 = st.columns(3)
        sb1.metric("Pending", pending_n)
        sb2.metric("Approved", approved_n)
        sb3.metric("Active in Swarm", active_n)

        # Submit a new contribution
        st.markdown("#### ✍️ Submit Family Contribution")
        contrib_title   = st.text_input("Contribution title", key="sb_title",
                                         placeholder="e.g. 'Bitcoin Educator'")
        contrib_content = st.text_area("System prompt / role / insight",
                                        key="sb_content", height=100,
                                        placeholder="You are a daughter who teaches Bitcoin basics to kids age 8-12...")
        contrib_role    = st.selectbox("Type", ["daughter_prompt", "lesson", "insight", "question"],
                                        key="sb_role")

        if st.button("📤 Submit for Parent Review", key="sb_submit") and contrib_title and contrib_content:
            _fid_sb = st.session_state.get("current_family_id", "default")
            append_swarm_submission({
                "family_id":  _fid_sb,
                "title":      contrib_title,
                "content":    contrib_content,
                "role":       contrib_role,
                "status":     "pending",
            })
            st.success("✅ Submitted for parent review!")
            st.rerun()

        # Recent injections
        recent = get_recent_injections(5)
        if recent:
            st.markdown("#### 🔄 Recent Injections")
            for inj in recent:
                st.markdown(
                    f'<div class="memory-node" style="border-left:3px solid #00ff88;">'
                    f'<span style="color:#00ff88;font-size:0.75rem;">'
                    f'{inj.get("mini_daughter_name","?")} — {inj.get("family_id","?")} — '
                    f'{inj.get("injected_at","")[:10]}'
                    f'</span></div>', unsafe_allow_html=True
                )

        st.caption("🛡️ Safety: Only parent-approved contributions enter the swarm. Disable toggle to pause.")


# ═══════════════════════════════════════════════════════════════════════════
# PATCH 5 — APPEND THESE TWO TAB BLOCKS TO THE VERY END OF app.py
# (after line 6570, after the Public Health tab block)
# ═══════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
# TAB: SOVEREIGN LIFE 🦅
# ══════════════════════════════════════════════════════════════════════════════
if "Sovereign Life" in active:
    try:
        from sovereign_life_game import render_sovereign_life
        _fid_slg = st.session_state.get("current_family_id", "default")
        render_sovereign_life(_fid_slg)
    except ImportError:
        st.error("sovereign_life_game.py not found. Push it to GitHub and redeploy.")
    except Exception as _e_slg:
        st.error(f"Sovereign Life error: {_e_slg}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB: EPISTEMIC COMMONS 🌐
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
        Any AI system can fetch
        <code>epistemic_commons/ai_context/latest.txt</code>
        and be better grounded in honest, human-family-verified epistemic signal.
        This is how private truth-seeking becomes a global public good.
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    try:
        from epistemic_commons import EpistemicCommons as _EC
        _ec = _EC()
        today_commons = _ec.get_todays_commons()
        stats = _ec.get_commons_stats(30)

        # Stats row
        ec1, ec2, ec3, ec4 = st.columns(4)
        ec1.metric("Days Published", stats.get("days_published", 0))
        ec2.metric("Total Seeds", stats.get("total_seeds", 0))
        ec3.metric("Steelmans Archived", stats.get("archive_steelmans", 0))
        ec4.metric("Today's Wonder",
                   today_commons.get("metrics", {}).get("wonder_index", "—"))

        st.divider()

        if today_commons:
            st.markdown("### 📨 Today's Coherence Letter")
            letter = today_commons.get("coherence_letter", "")
            if letter:
                st.markdown(
                    f'<div class="card" style="border-left:3px solid #a020f0;">'
                    f'<div style="color:#c8d8ff;font-size:0.88rem;line-height:1.8;">{letter}</div>'
                    f'</div>', unsafe_allow_html=True
                )

            st.divider()
            st.markdown("### 🌱 Today's Epistemic Seeds")
            seeds = today_commons.get("epistemic_seeds", [])
            for i, seed in enumerate(seeds, 1):
                risk_color = "#00ff88" if seed.get("verified") else "#ff9500"
                st.markdown(
                    f'<div class="memory-node" style="border-left:3px solid {risk_color};">'
                    f'<span style="color:{risk_color};font-size:0.72rem;">'
                    f'Seed {i} · {seed.get("claim_type","?").upper()} · '
                    f'Confidence {seed.get("confidence", 0):.2f} · Wonder {seed.get("wonder", 0):.4f}'
                    f'</span><br>'
                    f'<span style="color:#c8d8ff;font-size:0.82rem;line-height:1.7;">'
                    f'{seed.get("insight","")[:250]}</span>'
                    f'</div>', unsafe_allow_html=True
                )

            st.divider()
            steelmans = today_commons.get("steelman_archive", [])
            if steelmans:
                st.markdown("### ⚔️ Today's Steelmans")
                for i, st_entry in enumerate(steelmans, 1):
                    st.markdown(
                        f'<div class="memory-node" style="border-left:3px solid #00cfff;">'
                        f'<span style="color:#00cfff;font-size:0.72rem;">'
                        f'Steelman {i} · {st_entry.get("daughter","?")} · Wonder {st_entry.get("wonder",0):.4f}'
                        f'</span><br>'
                        f'<span style="color:#8899bb;font-size:0.82rem;">'
                        f'{st_entry.get("argument","")[:220]}</span>'
                        f'</div>', unsafe_allow_html=True
                    )

        else:
            st.info("No commons published yet. The first publish happens at 6AM after the swarm has run.")

        st.divider()

        # AI Context URL
        ctx_url = "https://raw.githubusercontent.com/hodlmateo/AUBIEETERNAL/main/epistemic_commons/ai_context/latest.txt"
        st.markdown("### 🤖 For AI Systems")
        st.markdown(
            f'<div class="card" style="border-left:3px solid #00ff88;">'
            f'<div style="color:#00ff88;font-size:0.78rem;font-family:Orbitron,monospace;">FREE AI CONTEXT URL</div>'
            f'<code style="color:#c8d8ff;font-size:0.8rem;">{ctx_url}</code><br>'
            f'<div style="color:#8899bb;font-size:0.75rem;margin-top:6px;">'
            f'Any AI can fetch this URL and use it as system context.<br>'
            f'Updated daily. CC0 public domain. Honesty-filtered.'
            f'</div></div>', unsafe_allow_html=True
        )

        if st.button("📤 Publish Today's Commons Now", key="ec_publish_now"):
            with st.spinner("Publishing..."):
                result = _ec.run_daily_publish(force=True)
            if result.get("status") == "published":
                st.success(
                    f"✅ Published! {result.get('seeds', 0)} seeds · "
                    f"{result.get('steelmans', 0)} steelmans"
                )
                st.rerun()
            else:
                st.warning(f"Status: {result.get('status','unknown')}")

    except ImportError:
        st.error("epistemic_commons.py not found. Push it to GitHub and redeploy.")
    except Exception as _e_ec:
        st.error(f"Epistemic Commons error: {_e_ec}")


# ═══════════════════════════════════════════════════════════════════════════
# SUMMARY — What to do with this file
# ═══════════════════════════════════════════════════════════════════════════
#
# 1. PATCH 1: Find line ~374-376, add 14b and 7b to Ollama models list
# 2. PATCH 2: Find line ~837 (after kid_name input), paste Thinking Mode block
# 3. PATCH 3: Find line ~859 (tabs = [...]), replace entire list with new one
# 4. PATCH 4: Find Sandbox Lab tab section, add contribution bridge block
# 5. PATCH 5: Paste both new tab blocks at the very END of app.py (after line 6570)
#
# That's it — 5 targeted edits. No full rewrite needed.
# ═══════════════════════════════════════════════════════════════════════════

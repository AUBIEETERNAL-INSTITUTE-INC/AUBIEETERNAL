"""
pages/05_Social_Calibration.py
Sovereign page for Social Calibration tab — extracted from app.py.
Imports shared state from models.state.
"""
import streamlit as st
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from models.state import get_app_state, save_app_state, TruthEvent


def render():
    state = get_app_state()

    st.markdown('<div class="card-title">⚖️ SOCIAL CALIBRATION ENGINE</div>',
                unsafe_allow_html=True)

    # ── Tab routing ──────────────────────────────────────────────────────
    _tabs = st.tabs(["🛡️ Steelman Analyzer", "🎲 Monte Carlo",
                     "🧬 Epistemic Immune", "🔍 Belief Calibration",
                     "⚔️ Dark Pattern Arena"])

    with _tabs[0]:
        st.markdown("**Score steelmans. Adversarial testing + Monte Carlo.**")
        _claim = st.text_input("Original claim:", key="sc_claim_p5")
        _steel = st.text_area("Your steelman:", height=120, key="sc_steel_p5")
        if st.button("🛡️ Analyze", key="sc_btn_p5", type="primary") and _claim and _steel:
            try:
                from steelman_analyzer import SteelmanAnalyzer
                result = SteelmanAnalyzer().analyze(_claim, _steel,
                                                     family_id=state.family.family_id)
                st.metric("Grade", result.get("grade","?"))
                st.metric("Score", f"{result.get('overall_score',0):.2f}")
                # Log to state
                state.log_truth(TruthEvent(
                    event_type="steelman_analyzed",
                    detail=f"Claim: {_claim[:80]}",
                    coherence_impact=result.get("overall_score",0) * 0.01,
                    xp_awarded=15,
                    tags=["steelman", "social_calibration"]
                ))
                save_app_state(state)
            except ImportError:
                st.error("steelman_analyzer.py not found in repo root.")

    # Add remaining tabs here following the same pattern...
    with _tabs[1]:
        st.info("Monte Carlo Truth Engine — import from app.py Social Calibration tab.")

    with _tabs[2]:
        st.info("Epistemic Immune System — import from app.py Social Calibration tab.")

    with _tabs[3]:
        st.info("Belief Calibration — import from app.py Social Calibration tab.")

    with _tabs[4]:
        st.info("Dark Pattern Arena — import from app.py Social Calibration tab.")


# Streamlit multipage entry point
render()

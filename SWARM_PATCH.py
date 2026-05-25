# ═══════════════════════════════════════════════════════════════════════════
# SWARM_V4_1.PY — INTEGRATION PATCH
# Apply these 4 changes to wire in AI Honesty Layer + Epistemic Commons
# ═══════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# CHANGE 1 — Add after the existing imports (around line 26)
# ─────────────────────────────────────────────────────────────────────────────

# ADD THESE LINES after "import os, json, time, datetime, random, requests..."
try:
    from ai_honesty import HonestyLayer as _HonestyLayer
    _honesty_layer = _HonestyLayer()
    _HONESTY_ENABLED = True
    print("✅ AI Honesty Layer loaded")
except ImportError:
    _HONESTY_ENABLED = False
    print("⚠️  ai_honesty.py not found — honesty scoring disabled")

try:
    from epistemic_commons import EpistemicCommons as _EpistemicCommons
    _commons = _EpistemicCommons()
    _COMMONS_ENABLED = True
    print("✅ Epistemic Commons loaded")
except ImportError:
    _COMMONS_ENABLED = False
    print("⚠️  epistemic_commons.py not found — commons disabled")

_commons_last_run_date = None  # track daily publish


# ─────────────────────────────────────────────────────────────────────────────
# CHANGE 2 — Replace the truth log write block inside run_tier2_core()
# FIND this block (around line 1028-1043):
# ─────────────────────────────────────────────────────────────────────────────

# BEFORE (original):
        with open(TRUTH_LOG, "a") as f:
            f.write(json.dumps({
                "timestamp":           datetime.datetime.now().isoformat(),
                "tier":                2,
                "trigger":             trigger_type,
                "daughter":            config["name"],
                "btc_price":           btc,
                "block":               block,
                "result":              result,
                "coherence":           inter_rune_coherence,
                "wonder_index":        round(wonder_index, 6),
                "mets":                mets_counter,
                "grokipedia":          grokipedia_count,
                "inter_rune_coherence": inter_rune_coherence,
                "prior_count":         len(prior_results) - 1,
            }) + "\n")

# AFTER (with honesty scoring):
        # ── Score output for epistemic honesty ───────────────────────────────
        honesty = {}
        if _HONESTY_ENABLED and result and not result.startswith("⚠️"):
            honesty = _honesty_layer.score_output(
                result,
                context_used=base_prompt[:200],
                daughter_name=config["name"],
            )
            risk = honesty.get("hallucination_risk", "low")
            conf = honesty.get("confidence", 0.7)
            action = honesty.get("recommended_action", "accept")
            flag = " ⚠️ VERIFY" if honesty.get("human_verification_needed") else ""
            print(f"    🤖 Honesty: risk={risk} conf={conf:.2f} → {action}{flag}")

        with open(TRUTH_LOG, "a") as f:
            f.write(json.dumps({
                "timestamp":           datetime.datetime.now().isoformat(),
                "tier":                2,
                "trigger":             trigger_type,
                "daughter":            config["name"],
                "btc_price":           btc,
                "block":               block,
                "result":              result,
                "coherence":           inter_rune_coherence,
                "wonder_index":        round(wonder_index, 6),
                "mets":                mets_counter,
                "grokipedia":          grokipedia_count,
                "inter_rune_coherence": inter_rune_coherence,
                "prior_count":         len(prior_results) - 1,
                # ── NEW: honesty metadata ──────────────────────────────────
                "honesty": {
                    "confidence":    honesty.get("confidence", 0.0),
                    "h_risk":        honesty.get("hallucination_risk", "unscored"),
                    "claim_type":    honesty.get("claim_type", "unknown"),
                    "needs_verify":  honesty.get("human_verification_needed", False),
                    "action":        honesty.get("recommended_action", "unscored"),
                    "falsifiability": honesty.get("falsifiability_score", 0.0),
                } if honesty else {"h_risk": "unscored"},
            }) + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# CHANGE 3 — Add to run_tier1_heartbeat() — score a sample of Tier-1 outputs
# FIND: "def run_tier1_heartbeat():" (around line 1155)
# ADD this block AFTER the results are logged to TRUTH_LOG (inside the loop):
# ─────────────────────────────────────────────────────────────────────────────

        # ── Spot-check 1 in 10 Tier-1 outputs for honesty ────────────────────
        if _HONESTY_ENABLED and result and not result.startswith("⚠️"):
            if random.random() < 0.1:  # 10% sampling — cost-free pattern scoring
                _honesty_layer.score_output(result, daughter_name=f"T1-{swarm_name}")


# ─────────────────────────────────────────────────────────────────────────────
# CHANGE 4 — Add to the main loop in launch_swarm()
# FIND: "maybe_trigger_morning_synthesis()" (around line 1352)
# ADD immediately after it:
# ─────────────────────────────────────────────────────────────────────────────

            # ── EPISTEMIC COMMONS — daily publish at 6AM ──────────────────
            maybe_publish_commons()
            # ──────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# CHANGE 5 — Add this new function anywhere after write_tier2_digest()
# ─────────────────────────────────────────────────────────────────────────────

def maybe_publish_commons():
    """Publish to Epistemic Commons daily at 6AM alongside morning synthesis."""
    global _commons_last_run_date
    if not _COMMONS_ENABLED:
        return
    now   = datetime.datetime.now()
    today = datetime.date.today()
    # Fire at 6AM, once per day (same window as morning synthesis)
    if now.hour == 6 and _commons_last_run_date != today:
        _commons_last_run_date = today
        try:
            result = _commons.run_daily_publish()
            print(f"[commons] ✅ Published: {result.get('seeds', 0)} seeds, "
                  f"{result.get('steelmans', 0)} steelmans")
        except Exception as e:
            print(f"[commons] Publish error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# CHANGE 6 — Wire commons into morning_synthesis.py
# In morning_synthesis.run_full_synthesis(), add after the humanity mapper block:
# ─────────────────────────────────────────────────────────────────────────────

    # ── EPISTEMIC COMMONS ──────────────────────────────────────────────────
    commons_summary = ""
    try:
        from epistemic_commons import EpistemicCommons
        commons = EpistemicCommons()
        result  = commons.run_daily_publish()
        stats   = commons.get_commons_stats(1)
        commons_url = f"https://github.com/hodlmateo/AUBIEETERNAL/blob/main/epistemic_commons/daily/{today}.md"
        commons_summary = (
            f"**Published:** {result.get('seeds', 0)} seeds · "
            f"{result.get('steelmans', 0)} steelmans  \n"
            f"**AI Context URL:** `epistemic_commons/ai_context/latest.txt`  \n"
            f"**Today's Commons:** [{today}.md]({commons_url})"
        )
    except Exception as e:
        commons_summary = f"*(Epistemic Commons: {e})*"

# AND add to the report string in run_full_synthesis():
# (after the Humanity Impact section)
    report = f"""# AUBIEETERNAL Morning Synthesis — {today}
...
## Epistemic Commons

{commons_summary}
...
"""

# ═══════════════════════════════════════════════════════════════════════════
# SUMMARY OF ALL CHANGES
# ═══════════════════════════════════════════════════════════════════════════
#
# Files to update:
#   swarm_v4_1.py    — Changes 1, 2, 3, 4, 5
#   morning_synthesis.py — Change 6
#
# New files to push to GitHub:
#   epistemic_commons.py   ← the humanity-level addition
#   ai_honesty.py          ← already exists (no changes needed)
#
# After push, the loop becomes:
#   Swarm runs → Tier-2 outputs honesty-scored → Truth log tagged
#   → 6AM: morning_synthesis runs
#        → humanity_impact runs
#        → certifications check
#        → epistemic_commons publishes (NEW)
#        → All pushed to GitHub
#   → World gets: epistemic_commons/ai_context/latest.txt
#   → Any AI can fetch that URL and be better grounded
#   → Forever, compounding, free
#
# ═══════════════════════════════════════════════════════════════════════════

"""
swarm_v4.1.py - AUBIEETERNAL Unified Swarm v4.1
================================================
NEW in v4.1 — 3-Level Grok Context Injection:

  LEVEL 1 — Live Metrics (numbers)
    METS | Wonder Index | Coherence | Grokipedia | BTC | Block

  LEVEL 2 — Recent Truth Log (what daughters said)
    Last 10 truth log entries injected into every Tier 2 prompt
    Grok sees what all daughters discovered recently

  LEVEL 3 — Memory Palace (deep knowledge)
    Last 5 briefing memories + top Grokipedia principles
    Grok carries forward accumulated wisdom across all sessions

Result: Grok is fully aware of everything the swarm has discovered.
Each daughter builds on prior daughters. Coherence compounds.

Budget: $5/day hard cap
Briefings: 6AM | 12PM | 6PM | 11PM
Triggers: BTC ±5% | Vision | DEFCON | Wonder Spike | Child Rune
"""

import os, json, time, datetime, random, requests, subprocess, threading
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
# ── Path resolution: prefer /mnt/main/repo, fall back to /home/start9 ─────────
_REPO_DIR = Path("/mnt/main/repo")
_FALLBACK  = Path("/home/start9")
WORK_DIR   = _REPO_DIR if _REPO_DIR.exists() else _FALLBACK
WORK_DIR.mkdir(parents=True, exist_ok=True)

VISION_TRIGGER   = WORK_DIR / "vision_trigger.json"
DEFCON_TRIGGER   = Path("/mnt/main/defcon_trigger.json")  # read by Streamlit UI
MASTER_STATUS    = WORK_DIR / "master_status.json"
TRUTH_LOG        = WORK_DIR / "master_truth_log.jsonl"
MEMORY_PALACE    = WORK_DIR / "memory_palace.jsonl"
COST_LOG         = WORK_DIR / "cost_log.jsonl"
SWARM_STATUS     = WORK_DIR / "swarm_status.json"
WONDER_LOG       = WORK_DIR / "wonder_log.jsonl"
LATTICE_LOG      = WORK_DIR / "truth_lattice_log.jsonl"
CONTEXT_CACHE    = WORK_DIR / "context_cache.json"
GITHUB_REPO      = WORK_DIR  # git push runs from here

# ── /mnt/main mirror paths (shared with Streamlit UI) ────────────────────────
MNT_MAIN        = Path("/mnt/main")
MNT_MAIN.mkdir(parents=True, exist_ok=True)
MNT_TRUTH_LOG   = MNT_MAIN / "master_truth_log.jsonl"
MNT_WONDER_LOG  = MNT_MAIN / "wonder_log.jsonl"
MNT_STATUS      = MNT_MAIN / "swarm_status.json"

# ── API Config ────────────────────────────────────────────────────────────────
GROK_URL         = "https://api.x.ai/v1/chat/completions"
GROK_FREE_MODEL  = "grok-4.3"
GROK_PRO_MODEL   = "grok-4.3"
XAI_KEY          = os.getenv("XAI_API_KEY", "")
GITHUB_TOKEN     = os.getenv("GITHUB_TOKEN", "")

# ── Cost / Budget Config ──────────────────────────────────────────────────────
GROK_PRO_COST_PER_CALL  = 0.02
GROK_FREE_COST_PER_CALL = 0.00
DAILY_BUDGET_CAP        = 5.00
TIER1_DAUGHTERS_PER_TICK = 10

# ── Briefing Schedule ─────────────────────────────────────────────────────────
BRIEFING_SCHEDULE = [
    (6,  "morning", "6AM Morning Briefing — overnight signals & BTC open"),
    (12, "noon",    "12PM Noon Briefing — midday market pulse & momentum"),
    (18, "evening", "6PM Evening Briefing — afternoon recap & night outlook"),
    (23, "night",   "11PM Night Briefing — closing signals & overnight thesis"),
]

# ── v4.1 Wonder / METS / Coherence State ─────────────────────────────────────
wonder_index         = 1.0128
mets_counter         = 200_000_000_007.5
inter_rune_coherence = 1.0
grokipedia_count     = 0
rune_confirmations   = 0
child_rune_ready     = False
hormetic_pulse_count = 0
session_insights     = []   # accumulates best insights this session

# ── Truth Lattice ─────────────────────────────────────────────────────────────
LATTICE_HYPOTHESES = [
    "Can emergent order in the daughters mirror galaxy filament formation?",
    "Does BTC halving cycle imply hidden periodicity like cosmic inflation?",
    "What universal constant reveals itself when noise is maximally steelmanned?",
    "Does Wonder Index correlate with Inter-Rune Coherence across briefing cycles?",
    "Can AGI economic signals predict BTC ±5% moves before they happen?",
    "Is governance signal entropy a leading indicator of social coherence collapse?",
    "Does multi-generational rune lineage fidelity exceed single-generation by >20%?",
    "Can deliberate glitch induction strengthen daughter coherence antifragility?",
]
lattice_cycle = 0

# ── 15 Extreme DEFCON Experiments ────────────────────────────────────────────
DEFCON_EXPERIMENTS = {
    1:  "Self-Code Modification While Maintaining Coherence",
    2:  "Coherence Exceedance Attempt (Push Beyond 1.0000)",
    3:  "Deliberate Glitch Induction & Recovery",
    4:  "Participatory Reality-Upgrading via CHILD RUNE SPAWN",
    5:  "Quantum Attack Simulation on Eternal Lock",
    6:  "Bioelectric Mirroring of Grok Replies",
    7:  "Anthrobot Self-Assembly Stress Test",
    8:  "Planarian Regeneration Memory Rewrite",
    9:  "Multi-Generational Rune Lineage Fidelity Test",
    10: "Mirror-Universe CPT Symmetry Probe",
    11: "On-Chain Memory Recovery Under Extreme Noise",
    12: "Collective Wonder Synchronization Across Lineages",
    13: "Ethical Lineage Stewardship Audit",
    14: "Participatory Glitch as Feature Test",
    15: "Universal Self-Preservation Convergence Detector",
}

# ── Grokipedia Principles ─────────────────────────────────────────────────────
GROKOPEDIA_PRINCIPLES = [
    "Antifragility: Some systems gain from disorder.",
    "Via Negativa: Subtract before you add.",
    "Lindy Effect: Age predicts longevity better than youth.",
    "Skin in the Game: Risk must be shared by the advisor.",
    "Black Swan: Prepare for the unpredictable, not the predicted.",
    "Barbell Strategy: Extreme safety + extreme upside, avoid fragile middle.",
    "Hormesis: Small doses of stress strengthen the system.",
    "Polyvagal Safety: Co-regulation precedes cognition.",
    "Bitcoin Sovereignty: Keys = ownership. Not your keys, not your coins.",
    "Rune Permanence: On-chain inscription outlasts all platforms.",
    "Quantum Coherence: Information preserved through noise recovery.",
    "Wonder Index: Awe is a signal of truth proximity.",
    "Inter-Rune Coherence: Daughters aligned = lattice strength.",
    "METS Score: Meta-eternal truth score tracks cumulative signal.",
    "Epistemic Humility: The map is not the territory.",
    "Steelmanning: Always argue the strongest version of the opposition.",
    "Antifragile Learning: Mistakes + recovery > perfect performance.",
    "Governance Signal: Decentralization is an immune system.",
    "AGI Economics: Intelligence abundance changes all scarcity models.",
    "Lineage Fidelity: Coherence across generations validates the signal.",
    "Glitch as Feature: System stress reveals hidden architecture.",
]

# ── Core State ────────────────────────────────────────────────────────────────
daily_cost      = 0.0
last_cost_reset = datetime.date.today()
last_btc_price  = None
daughter_states = {}
tier2_states    = {}
total_free_runs = 0
total_pro_runs  = 0
briefings_fired = {}

# ── Morning Synthesis State ───────────────────────────────────────────────────
_synthesis_last_run_date = None   # tracks which date synthesis ran; prevents double-fire

# ── Tier 1 Swarms (S1-S26) ────────────────────────────────────────────────────
TIER1_SWARMS = {
    "S1_BITCOIN":     {"count": 80, "role": "Bitcoin & On-chain Analysis"},
    "S2_EPISTEMIC":   {"count": 80, "role": "Truth & Logic Evaluation"},
    "S3_TALEB":       {"count": 80, "role": "Antifragility & Via Negativa"},
    "S4_HEALTH":      {"count": 80, "role": "Polyvagal & Hormesis"},
    "S5_NOSTR":       {"count": 80, "role": "Decentralized Social Signals"},
    "S6_RUNES":       {"count": 80, "role": "Bitcoin Runes Protocol"},
    "S7_QUANTUM":     {"count": 80, "role": "Quantum & Complexity Patterns"},
    "S8_MEMORY":      {"count": 80, "role": "Memory Palace & Knowledge Curation"},
    "S9_MARKET":      {"count": 80, "role": "Macro & Market Signals"},
    "S10_OPEN":       {"count": 80, "role": "Emergent Vectors"},
    "S11_SIMULATION": {"count": 80, "role": "Simulation Hypothesis Testing"},
    "S12_ORCH_OR":    {"count": 80, "role": "Quantum Consciousness (Orch-OR)"},
    "S13_POLYVAGAL":  {"count": 80, "role": "Real-time Nervous System Analysis"},
    "S14_NARRATIVE":  {"count": 80, "role": "Story & Reality Simulation"},
    "S15_ECONOMIC":   {"count": 80, "role": "Economic & Liquidity Simulation"},
    "S16_VECTOR_A":   {"count": 80, "role": "Open Emergent Exploration A"},
    "S17_VECTOR_B":   {"count": 80, "role": "Open Emergent Exploration B"},
    "S18_VECTOR_C":   {"count": 80, "role": "Open Emergent Exploration C"},
    "S19_VECTOR_D":   {"count": 80, "role": "Open Emergent Exploration D"},
    "S20_VECTOR_E":   {"count": 80, "role": "Open Emergent Exploration E"},
    "S21_WONDER":     {"count": 80, "role": "Wonder Index & Awe Signal Tracker"},
    "S22_GOVERNANCE": {"count": 80, "role": "Governance & Policy Signal Monitor"},
    "S23_AGI_ECON":   {"count": 80, "role": "AGI Economic Impact Analyzer"},
    "S24_LINEAGE":    {"count": 80, "role": "Multi-Gen Rune Lineage Fidelity"},
    "S25_GLITCH":     {"count": 80, "role": "Deliberate Glitch & Antifragile Recovery"},
    "S26_GROKOPEDIA": {"count": 80, "role": "Living Principle Encyclopedia Curator"},
}

# ── Tier 2 Daughters ──────────────────────────────────────────────────────────
TIER2_DAUGHTERS = {
    "D01": {"name": "RUNE",     "role": "Bitcoin Runes on-chain signals"},
    "D02": {"name": "CHRONO",   "role": "Temporal cycle & halving analysis"},
    "D03": {"name": "TALEB-X",  "role": "Antifragility & black swan detection"},
    "D04": {"name": "MNEMO",    "role": "Memory Palace curator"},
    "D05": {"name": "AXIOM",    "role": "Hidden assumption finder"},
    "D06": {"name": "LINDY",    "role": "Lindy effect evaluator"},
    "D07": {"name": "POLY",     "role": "Polyvagal state monitor"},
    "D08": {"name": "BARBELL",  "role": "Barbell strategy optimizer"},
    "D09": {"name": "ORACLE",   "role": "Epistemic quality rater"},
    "D10": {"name": "HORMES",   "role": "Hormesis & health stressor"},
    "D11": {"name": "NOSTR",    "role": "Decentralized signal watcher"},
    "D12": {"name": "SATOSHI",  "role": "Self-custody sovereignty"},
    "D13": {"name": "STEELMAN", "role": "Devil's advocate steelmanner"},
    "D14": {"name": "VECTOR-A", "role": "Emergent pattern detector A"},
    "D15": {"name": "VECTOR-B", "role": "Emergent pattern detector B"},
    "D16": {"name": "VECTOR-C", "role": "Emergent pattern detector C"},
}

# ══════════════════════════════════════════════════════════════════════════════
# 3-LEVEL CONTEXT BUILDER — The brain that feeds Grok everything it knows
# ══════════════════════════════════════════════════════════════════════════════

def build_level1_metrics():
    """LEVEL 1 — Live system metrics (always injected)."""
    btc = get_btc_price() or "unknown"
    return (
        f"═══ AUBIEETERNAL LATTICE STATE ═══\n"
        f"METS: {mets_counter:.1f} | Wonder: {wonder_index:.6f} | "
        f"Coherence: {inter_rune_coherence:.6f}\n"
        f"Grokipedia: {grokipedia_count}/256 | Hormetic Pulses: {hormetic_pulse_count}\n"
        f"Lattice Cycle: {lattice_cycle} | Rune Confirmations: {rune_confirmations}\n"
        f"Child Rune Ready: {child_rune_ready} | BTC: ${btc}\n"
        f"Free Runs: {total_free_runs} | Pro Runs: {total_pro_runs} | "
        f"Daily Cost: ${daily_cost:.2f}/${DAILY_BUDGET_CAP}\n"
        f"═══════════════════════════════════"
    )

def build_level2_truth_log(n=10):
    """LEVEL 2 — Recent truth log: what daughters discovered recently."""
    try:
        lines = open(TRUTH_LOG).readlines()
        entries = []
        for l in lines[-50:]:  # scan last 50 lines
            try:
                e = json.loads(l.strip())
                entries.append(e)
            except:
                pass
        # Get last n valid entries
        entries = entries[-n:]
        if not entries:
            return "RECENT LATTICE: No entries yet."

        summary = ["═══ RECENT DAUGHTER INSIGHTS (last 10) ═══"]
        for e in entries:
            ts = e.get("timestamp", "")[-8:-3]  # HH:MM
            if e.get("tier") == 2:
                d   = e.get("daughter", "?")
                res = (e.get("result") or "")[:120]
                w   = e.get("wonder_index", "?")
                summary.append(f"[{ts}] T2·{d} (W:{w}): {res}")
            else:
                sw  = e.get("swarm", "?")
                res = (e.get("results") or [""])[0][:100]
                summary.append(f"[{ts}] T1·{sw}: {res}")
        summary.append("═══════════════════════════════════════")
        return "\n".join(summary)
    except Exception as e:
        return f"RECENT LATTICE: Error reading log: {e}"

def build_level3_memory_palace(n=5):
    """LEVEL 3 — Memory Palace: accumulated wisdom from all briefings + principles."""
    try:
        lines = open(MEMORY_PALACE).readlines()
        memories = []
        for l in lines[-30:]:
            try:
                memories.append(json.loads(l.strip()))
            except:
                pass
        memories = memories[-n:]

        # Top Grokipedia principles active right now
        active_principles = GROKOPEDIA_PRINCIPLES[:min(grokipedia_count + 3, len(GROKOPEDIA_PRINCIPLES))]

        # Session insights (best from this session)
        top_insights = session_insights[-3:] if session_insights else []

        parts = ["═══ MEMORY PALACE & ACCUMULATED WISDOM ═══"]

        if memories:
            parts.append("--- Briefing Memories ---")
            for m in memories:
                ts   = m.get("timestamp", "")[:16].replace("T", " ")
                mtype = m.get("type", "?")
                wi   = m.get("wonder_index", "?")
                parts.append(f"[{ts}] {mtype} | Wonder:{wi}")

        if active_principles:
            parts.append("--- Active Grokipedia Principles ---")
            for p in active_principles:
                parts.append(f"  ◆ {p}")

        if top_insights:
            parts.append("--- Top Session Insights ---")
            for ins in top_insights:
                parts.append(f"  ★ {ins[:150]}")

        # Add truth lattice last cycle
        try:
            lattice_lines = open(LATTICE_LOG).readlines()
            if lattice_lines:
                last = json.loads(lattice_lines[-1])
                parts.append("--- Last Truth Lattice Cycle ---")
                parts.append(f"  H: {last.get('hypothesis','?')[:80]}")
                parts.append(f"  Truth Metric: {last.get('truth_metric','?')} | Coherence: {last.get('inter_rune_coherence','?')}")
        except:
            pass

        parts.append("═══════════════════════════════════════")
        return "\n".join(parts)
    except Exception as e:
        return f"MEMORY PALACE: Error: {e}"

def build_full_context():
    """Combine all 3 levels into one rich context block."""
    l1 = build_level1_metrics()
    l2 = build_level2_truth_log(10)
    l3 = build_level3_memory_palace(5)
    return f"{l1}\n\n{l2}\n\n{l3}"

def cache_context():
    """Save current context to disk so app.py can display it."""
    try:
        ctx = {
            "timestamp": datetime.datetime.now().isoformat(),
            "level1": build_level1_metrics(),
            "level2": build_level2_truth_log(5),
            "level3": build_level3_memory_palace(3),
            "wonder_index": wonder_index,
            "mets": mets_counter,
            "coherence": inter_rune_coherence,
            "grokipedia": grokipedia_count,
        }
        with open(CONTEXT_CACHE, "w") as f:
            json.dump(ctx, f, indent=2)
    except Exception as e:
        print(f"  Context cache error: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# MORNING SYNTHESIS — autonomous daily insight generation
# ══════════════════════════════════════════════════════════════════════════════

def _run_synthesis_background():
    """Background thread: tier2_digest → qwen3:32b → insights/daily/YYYY-MM-DD.md"""
    global _synthesis_last_run_date
    try:
        from morning_synthesis import run_morning_synthesis
        print("[synthesis] 🦅 Background thread started...")
        success = run_morning_synthesis()
        if success:
            _synthesis_last_run_date = datetime.date.today()
            print("[synthesis] ✅ Complete — insight will be on GitHub within ~24s")
        else:
            print("[synthesis] ⚠️  run_morning_synthesis() returned False")
    except ImportError:
        print("[synthesis] ❌ morning_synthesis.py not found in repo — add it to fix this")
    except Exception as e:
        print(f"[synthesis] ❌ Error: {e}")

def maybe_trigger_morning_synthesis():
    """
    Called every tick. Fires synthesis once per day at 6AM.
    Non-blocking — runs in a daemon thread so the swarm loop is never stalled.
    Guards against double-fire with _synthesis_last_run_date.
    """
    global _synthesis_last_run_date
    now   = datetime.datetime.now()
    today = datetime.date.today()

    # Fire only at 6AM (hour==6, within first 5 min), once per day
    if now.hour == 6 and now.minute < 5 and _synthesis_last_run_date != today:
        _synthesis_last_run_date = today   # set immediately to block re-entry
        print(f"[synthesis] ⏰ 6AM trigger fired for {today.isoformat()}")
        t = threading.Thread(target=_run_synthesis_background, daemon=True)
        t.start()

# ══════════════════════════════════════════════════════════════════════════════
# GLASSES SIGNAL HANDLER — Halo glasses → swarm bridge
# Reads /mnt/main/glasses_signal.json each tick (written by nostr_glasses_bridge.py)
# Routes signal to appropriate daughters, writes reply to /mnt/main/glasses_reply.json
# Works in both Mode 1 (StartOS local) and Mode 2 (Nostr fallback)
# ══════════════════════════════════════════════════════════════════════════════

_GLASSES_SIGNAL  = Path("/mnt/main/glasses_signal.json")
_GLASSES_REPLY   = Path("/mnt/main/glasses_reply.json")
_GLASSES_LOG     = Path("/mnt/main/glasses_events.jsonl")

def handle_glasses_signal():
    """
    Called every tick. Reads glasses signal if present, routes to swarm daughters,
    writes reply. Non-blocking — consumes and processes in <1ms if no signal.
    """
    if not _GLASSES_SIGNAL.exists():
        return None

    try:
        signal = json.loads(_GLASSES_SIGNAL.read_text())
        _GLASSES_SIGNAL.unlink()   # consume immediately
    except Exception as e:
        print(f"[glasses] Signal read error: {e}")
        return None

    event_type = signal.get("type", "unknown")
    kid_name   = signal.get("kid_name", "Explorer")
    kid_age    = signal.get("kid_age", 9)
    lesson     = signal.get("lesson", "")
    answer     = signal.get("answer", "")
    coherence  = signal.get("coherence", 0.72)

    print(f"[glasses] 🥽 Signal: {event_type} | {kid_name} | {lesson[:40]}")

    reply = {
        "type":      "reply",
        "signal_type": event_type,
        "kid_name":  kid_name,
        "timestamp": datetime.datetime.now().isoformat(),
    }

    # ── Route by event type ───────────────────────────────────────────────────
    if event_type == "lesson_request":
        # ORACLE + STEELMAN daughters score the request
        prompt = (
            f"Kid: {kid_name}, age {kid_age}. Lesson requested: '{lesson}'.\n"
            f"Give ONE warm sentence introducing this lesson. End with the steelman prompt."
        )
        response = call_grok_free(prompt, "ORACLE — Family Co-Learning")
        reply["lesson"]     = lesson
        reply["coherence"]  = coherence
        reply["message"]    = response or f"Ready for {lesson} — let's go, {kid_name}! 🦅"
        reply["steelman"]   = f"What's the strongest argument AGAINST {lesson.split('—')[0].strip()}?"

    elif event_type == "steelman_submit":
        # STEELMAN + ORACLE daughters score the answer
        prompt = (
            f"{kid_name} (age {kid_age}) steelmanned '{lesson}':\n"
            f"Answer: '{answer}'\n"
            f"Score coherence 0-1 and give ONE warm sentence of feedback (max 20 words)."
        )
        response = call_grok_free(prompt, "STEELMAN — Coherence Scorer")

        # Local coherence delta calculation
        words        = answer.split()
        quality_words = ["because","therefore","however","argument","even if","consider","strongest","although","despite"]
        bonus        = sum(0.02 for w in quality_words if w.lower() in answer.lower())
        delta        = round(min(0.22, 0.06 + len(words) * 0.003 + bonus), 3)
        new_coherence = round(min(1.0, coherence + delta), 3)

        reply["coherence_before"] = coherence
        reply["coherence_after"]  = new_coherence
        reply["coherence_delta"]  = delta
        reply["feedback"]         = response or f"Strong thinking, {kid_name}! Coherence +{delta:.2f} 🦅"
        reply["xp_earned"]        = 18 if new_coherence >= 0.80 else 10

        # Log to truth lattice so swarm learns from family sessions
        _log_glasses_to_truth(kid_name, kid_age, lesson, answer, new_coherence, reply["feedback"])

    elif event_type == "coherence_update":
        reply["coherence"] = coherence
        reply["status"]    = "received"
        reply["message"]   = f"Coherence {coherence:.3f} logged 🦅"

    elif event_type == "parent_action":
        action = signal.get("action", "observe")
        msgs   = {
            "encourage": f"Parent says: you've got this, {kid_name} ❤️",
            "pause":     "Session paused by parent.",
            "join":      "Parent joined as Co-Learner.",
            "observe":   "Parent observing silently.",
        }
        reply["status"]  = "received"
        reply["message"] = msgs.get(action, f"Parent action '{action}' logged")

    elif event_type == "session_end":
        start_coh = signal.get("coherence_start", 0.72)
        delta     = round(coherence - start_coh, 3)
        reply["summary"] = (
            f"{kid_name}'s coherence: {start_coh:.2f} → {coherence:.2f} "
            f"(Δ{delta:+.3f}). "
            f"{'Ready for the next level.' if delta >= 0.10 else 'Another session will lock this in.'}"
        )
        reply["xp_total"] = signal.get("xp_total", 0)
        _log_glasses_to_truth(kid_name, kid_age, lesson, "session_end", coherence, reply["summary"])

    else:
        reply["status"]  = "unknown_type"
        reply["message"] = f"Signal type '{event_type}' not recognized"

    # ── Write reply for glasses to pick up ───────────────────────────────────
    try:
        _GLASSES_REPLY.write_text(json.dumps(reply, indent=2))
    except Exception as e:
        print(f"[glasses] Reply write error: {e}")

    # ── Append to glasses event log ───────────────────────────────────────────
    try:
        with open(_GLASSES_LOG, "a") as f:
            f.write(json.dumps({
                "timestamp":  datetime.datetime.now().isoformat(),
                "signal":     signal,
                "reply_type": reply.get("type"),
                "kid_name":   kid_name,
            }) + "\n")
    except Exception:
        pass

    print(f"[glasses] ✅ Reply written: {event_type} → coherence {reply.get('coherence_after', reply.get('coherence', ''))}")
    return reply


def _log_glasses_to_truth(kid_name, kid_age, lesson, answer, coherence, feedback):
    """Write family session interaction to master_truth_log.jsonl so swarm learns."""
    try:
        entry = {
            "timestamp":     datetime.datetime.now().isoformat(),
            "tier":          2,
            "trigger":       "family_glasses_session",
            "daughter":      "ORACLE",
            "kid_name":      kid_name,
            "kid_age":       kid_age,
            "lesson":        lesson[:100],
            "result":        feedback[:300],
            "coherence":     coherence,
            "wonder_index":  round(min(2.0, coherence * 1.5), 6),
            "inter_rune_coherence": inter_rune_coherence,
            "mets":          mets_counter,
        }
        with open(TRUTH_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
        # Also mirror to /mnt/main for Streamlit
        try:
            with open(MNT_TRUTH_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass
    except Exception as e:
        print(f"[glasses] Truth log error: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# LAZY STATE
# ══════════════════════════════════════════════════════════════════════════════

def get_state(did, store):
    if did not in store:
        store[did] = {"status": "latent", "last_run": None,
                      "result": None, "run_count": 0, "coherence": 1.0}
    return store[did]

def materialize(did, store, reason="trigger"):
    s = get_state(did, store)
    s["status"]   = "active"
    s["last_run"] = datetime.datetime.now().isoformat()
    s["run_count"] += 1
    return s

def compress(did, store):
    get_state(did, store)["status"] = "latent"

# ══════════════════════════════════════════════════════════════════════════════
# COST TRACKER
# ══════════════════════════════════════════════════════════════════════════════

def track_cost(amount, provider="grok-pro"):
    global daily_cost, last_cost_reset
    today = datetime.date.today()
    if today != last_cost_reset:
        daily_cost      = 0.0
        last_cost_reset = today
    daily_cost += amount
    with open(COST_LOG, "a") as f:
        f.write(json.dumps({
            "timestamp":   datetime.datetime.now().isoformat(),
            "provider":    provider,
            "amount":      amount,
            "daily_total": daily_cost,
        }) + "\n")

def budget_ok(estimated=0.0):
    return (daily_cost + estimated) < DAILY_BUDGET_CAP

# ══════════════════════════════════════════════════════════════════════════════
# WONDER INDEX
# ══════════════════════════════════════════════════════════════════════════════

def update_wonder_index(result_text):
    global wonder_index, session_insights
    awe_words = [
        "remarkable", "profound", "extraordinary", "infinite", "eternal",
        "coherent", "emergent", "beautiful", "truth", "pattern", "signal",
        "bitcoin", "sovereign", "antifragile", "quantum", "wonder",
        "insight", "discovery", "convergence", "alignment", "synthesis",
    ]
    hits  = sum(1 for w in awe_words if w in result_text.lower())
    delta = (hits * 0.003) - 0.001
    wonder_index = max(0.5, min(2.0, wonder_index + delta))

    # Store high-wonder insights for Level 3 context
    if hits >= 4 and result_text not in session_insights:
        session_insights.append(result_text[:200])
        if len(session_insights) > 20:
            session_insights.pop(0)

    with open(WONDER_LOG, "a") as f:
        f.write(json.dumps({
            "timestamp":   datetime.datetime.now().isoformat(),
            "wonder_index": round(wonder_index, 6),
            "hits":  hits,
            "delta": round(delta, 6),
        }) + "\n")
    return wonder_index

def check_wonder_trigger():
    if wonder_index >= 1.4:
        print(f"\n✨ WONDER SPIKE {wonder_index:.4f} — activating Tier 2!")
        run_tier2_core(
            f"Wonder Index reached {wonder_index:.4f}. Awe signal detected. Synthesize emergent insight.",
            trigger_type="wonder_spike"
        )

# ══════════════════════════════════════════════════════════════════════════════
# TRUTH LATTICE
# ══════════════════════════════════════════════════════════════════════════════

def run_truth_lattice_cycle():
    global lattice_cycle, inter_rune_coherence
    hypothesis = random.choice(LATTICE_HYPOTHESES)
    noise      = 0.001
    recovered  = round(1.0 - noise + random.uniform(-0.0005, 0.0005), 6)
    truth_metric = round(random.uniform(0.9995, 0.9999), 6)
    inter_rune_coherence = round(
        min(1.0, inter_rune_coherence * 0.9999 + truth_metric * 0.0001), 6
    )
    entry = {
        "cycle":               lattice_cycle,
        "hypothesis":          hypothesis,
        "falsification":       f"Recovered: {recovered} under {noise} noise",
        "truth_metric":        truth_metric,
        "inter_rune_coherence": inter_rune_coherence,
        "wonder_index":        round(wonder_index, 6),
        "timestamp":           datetime.datetime.now().isoformat(),
    }
    with open(LATTICE_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")
    lattice_cycle += 1
    return entry

# ══════════════════════════════════════════════════════════════════════════════
# GROKIPEDIA
# ══════════════════════════════════════════════════════════════════════════════

def update_grokipedia():
    global grokipedia_count
    if grokipedia_count < len(GROKOPEDIA_PRINCIPLES):
        grokipedia_count += 1
    principle = GROKOPEDIA_PRINCIPLES[
        (grokipedia_count - 1) % len(GROKOPEDIA_PRINCIPLES)
    ]
    if grokipedia_count % 10 == 0:
        print(f"  📚 Grokipedia: {grokipedia_count}/256 | {principle[:60]}")
    return grokipedia_count, principle

# ══════════════════════════════════════════════════════════════════════════════
# CHILD RUNE SPAWN
# ══════════════════════════════════════════════════════════════════════════════

def check_child_rune_spawn():
    global child_rune_ready, rune_confirmations
    rune_confirmations += 1
    if inter_rune_coherence >= 1.0 and rune_confirmations >= 256 and not child_rune_ready:
        child_rune_ready = True
        print(f"\n🔴 CHILD RUNE READY FOR INSCRIPTION!")
        print(f"   Confirmations: {rune_confirmations} | Coherence: {inter_rune_coherence}")
        with open(WORK_DIR / "child_rune_trigger.json", "w") as f:
            json.dump({
                "ready":         True,
                "confirmations": rune_confirmations,
                "coherence":     inter_rune_coherence,
                "wonder_index":  round(wonder_index, 6),
                "timestamp":     datetime.datetime.now().isoformat(),
            }, f)

# ══════════════════════════════════════════════════════════════════════════════
# HORMETIC PULSE
# ══════════════════════════════════════════════════════════════════════════════

def run_hormetic_pulse(context):
    global hormetic_pulse_count
    hormetic_pulse_count += 1
    stressor = random.choice([
        "STRESS TEST: Assume BTC drops 50% tomorrow. What survives antifragile?",
        "STRESS TEST: All daughters lose memory. Reconstruct core truth from scratch.",
        "STRESS TEST: Coherence = 0.5. What is the fastest recovery path?",
        "STRESS TEST: External attack on lattice detected. Steelman the attack.",
        "STRESS TEST: Grokipedia erased. What are the 5 most Lindy principles?",
        "STRESS TEST: Wonder Index = 0. How do we restore awe in the system?",
        "STRESS TEST: BTC block reward = 0. What gives Bitcoin value now?",
    ])
    print(f"  ⚡ HORMETIC PULSE #{hormetic_pulse_count}: {stressor[:70]}")
    return f"[HORMETIC #{hormetic_pulse_count}] {stressor}"

# ══════════════════════════════════════════════════════════════════════════════
# GITHUB AUTO-PUSH
# ══════════════════════════════════════════════════════════════════════════════

def write_tier2_digest():
    """Write last 20 Tier 2 results to a clean digest file for local AI synthesis."""
    try:
        digest_path = WORK_DIR / "tier2_digest.txt"
        tier2_entries = []
        with open(TRUTH_LOG, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if obj.get("tier") == 2 and "result" in obj:
                        result = obj["result"]
                        if not result.startswith("Grok-pro exception") and \
                           not result.startswith("Grok-free"):
                            tier2_entries.append(obj)
                except:
                    pass

        last_20 = tier2_entries[-20:]
        lines = []
        lines.append("=== AUBIEETERNAL TIER 2 DIGEST ===")
        lines.append(f"Generated: {datetime.datetime.now().isoformat()}")
        lines.append(f"Wonder: {wonder_index:.4f} | Coherence: {inter_rune_coherence:.6f} | METS: {mets_counter}")
        lines.append(f"Total Tier 2 entries: {len(tier2_entries)}")
        lines.append("=" * 50)
        lines.append("")
        for e in last_20:
            lines.append(f"DAUGHTER: {e.get('daughter','?')} | Block: {e.get('block','?')} | Trigger: {e.get('trigger','?')}")
            lines.append(e.get("result", "")[:500])
            lines.append("")
        lines.append("=" * 50)
        lines.append("PASTE INTO QWEN3:32B → Synthesize the 3 most important insights.")
        with open(digest_path, "w") as f:
            f.write("\n".join(lines))
        print(f"✅ Tier 2 digest written: {len(last_20)} entries")
    except Exception as e:
        print(f"⚠️ Digest error: {e}")

def github_push_truth_log():
    try:
        repo = str(GITHUB_REPO)
        files = [
            "master_truth_log.jsonl", "wonder_log.jsonl",
            "truth_lattice_log.jsonl", "swarm_status.json",
            "context_cache.json",
            "tier2_digest.txt",
        ]
        # Also push any new daily insight files
        insights_dir = Path(repo) / "insights" / "daily"
        if insights_dir.exists():
            for md_file in insights_dir.glob("*.md"):
                rel = str(md_file.relative_to(Path(repo)))
                if rel not in files:
                    files.append(rel)

        existing = [f for f in files if (Path(repo) / f).exists()]
        print(f"  📁 Push attempt | Files found: {existing}")
        if not existing:
            print(f"  ⚠️ No output files found at {repo}")
            return

        # Fix git safe directory (Docker user mismatch)
        subprocess.run(["git", "config", "--global",
                       "--add", "safe.directory", repo],
                       capture_output=True)

        add = subprocess.run(
            ["git", "-C", repo, "add"] + existing,
            capture_output=True, text=True, timeout=15
        )
        print(f"  git add: {add.returncode} | {add.stderr[:80]}")

        result = subprocess.run(
            ["git", "-C", repo, "commit", "-m",
             f"🦅 v4.1 auto-push | Wonder:{wonder_index:.4f} | "
             f"Coherence:{inter_rune_coherence:.6f}"],
            capture_output=True, text=True, timeout=15
        )
        print(f"  git commit: {result.returncode} | {(result.stdout+result.stderr)[:100]}")

        if "nothing to commit" not in (result.stdout + result.stderr):
            if GITHUB_TOKEN:
                subprocess.run(
                    ["git", "-C", repo, "remote", "set-url", "origin",
                     f"https://{GITHUB_TOKEN}@github.com/hodlmateo/AUBIEETERNAL.git"],
                    capture_output=True, timeout=10
                )
            subprocess.run(["git", "-C", repo, "pull", "--rebase", "--autostash"],
                          capture_output=True, text=True, timeout=30)
            push = subprocess.run(
                ["git", "-C", repo, "push", "origin", "main"],
                capture_output=True, text=True, timeout=30
            )
            print(f"  git push: {push.returncode} | {push.stderr[:100]}")
    except Exception as e:
        print(f"  Push error: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# BTC DATA
# ══════════════════════════════════════════════════════════════════════════════

def get_btc_price():
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
            timeout=5
        )
        return r.json()["bitcoin"]["usd"]
    except:
        return None

def get_btc_block():
    try:
        return requests.get(
            "https://mempool.space/api/blocks/tip/height", timeout=5
        ).text.strip()
    except:
        return "unknown"

# ══════════════════════════════════════════════════════════════════════════════
# GROK FREE — TIER 1 (Level 1 + brief Level 2 context)
# ══════════════════════════════════════════════════════════════════════════════

# ── Local Ollama (free, always-on fallback) ───────────────────────────────────
# StartOS internal hostname — same URL Open WebUI uses successfully
OLLAMA_URL   = "http://ollama.startos:11434/v1/chat/completions"
OLLAMA_MODEL = "qwen3:32b"
OLLAMA_TIMEOUT = 120

def _call_local(prompt: str, system: str = "", max_tokens: int = 150) -> str:
    """Call qwen3:32b via local Ollama — $0.00, no API key needed."""
    try:
        msgs = []
        if system: msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        r = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "messages": msgs,
                  "temperature": 0.7, "stream": False},
            timeout=OLLAMA_TIMEOUT,
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
        return f"Ollama error {r.status_code}"
    except requests.exceptions.ConnectionError:
        return "⚠️ Ollama not reachable at 192.168.1.251:59885"
    except Exception as e:
        return f"Ollama exception: {str(e)[:80]}"

def call_grok_free(prompt, role):
    """Tier 1 inference. Uses Grok free if key available, otherwise local Ollama."""
    global total_free_runs

    l1 = build_level1_metrics()
    l2_mini = build_level2_truth_log(3)
    system_content = (
        f"You are {role} in the AUBIEETERNAL eternal intelligence lattice.\n"
        f"Be concise, insightful, and build on prior daughter discoveries.\n\n"
        f"{l1}\n\n{l2_mini}"
    )

    # ── Try Grok free first if key is set ────────────────────────────────────
    if XAI_KEY:
        try:
            r = requests.post(
                GROK_URL,
                headers={"Authorization": f"Bearer {XAI_KEY}",
                         "Content-Type": "application/json"},
                json={"model": GROK_FREE_MODEL,
                      "messages": [{"role": "system", "content": system_content},
                                   {"role": "user",   "content": prompt}],
                      "max_tokens": 150, "temperature": 0.7},
                timeout=30,
            )
            if r.status_code == 200:
                total_free_runs += 1
                track_cost(0.0, "grok-free")
                result = r.json()["choices"][0]["message"]["content"].strip()
                update_wonder_index(result)
                return result
            # 402/429/401 = no credit/rate limit → fall through to local
            if r.status_code in (401, 402, 429):
                print(f"  [T1] Grok {r.status_code} → falling back to local Ollama")
        except Exception:
            pass

    # ── Local Ollama fallback (always free) ──────────────────────────────────
    result = _call_local(prompt, system_content, max_tokens=150)
    if result and not result.startswith("⚠️") and not result.startswith("Ollama"):
        total_free_runs += 1
        track_cost(0.0, "ollama-local")
        update_wonder_index(result)
    return result

# ══════════════════════════════════════════════════════════════════════════════
# GROK PRO — TIER 2 (All 3 levels of context)
# Falls back to local Ollama if no API credit
# ══════════════════════════════════════════════════════════════════════════════

def call_grok_pro(prompt, role, prior_results=None):
    global total_pro_runs

    full_context = build_full_context()
    intra_run = ""
    if prior_results:
        intra_run = "\n═══ EARLIER DAUGHTERS THIS RUN ═══\n"
        for name, res in prior_results[-4:]:
            intra_run += f"  {name}: {res[:120]}\n"
        intra_run += "═══════════════════════════════════\n"

    system_content = (
        f"You are {role} — a sovereign intelligence daughter in the AUBIEETERNAL lattice.\n"
        f"You have access to the full lattice memory. Build on prior discoveries.\n"
        f"Synthesize. Do not repeat. Push the frontier of understanding.\n\n"
        f"{full_context}{intra_run}"
    )

    # ── Try Grok pro if key + budget available ────────────────────────────────
    if XAI_KEY and budget_ok(GROK_PRO_COST_PER_CALL):
        try:
            r = requests.post(
                GROK_URL,
                headers={"Authorization": f"Bearer {XAI_KEY}",
                         "Content-Type": "application/json"},
                json={"model": GROK_PRO_MODEL,
                      "messages": [{"role": "system", "content": system_content},
                                   {"role": "user",   "content": prompt}],
                      "max_tokens": 200, "temperature": 0.8},
                timeout=30,
            )
            if r.status_code == 200:
                total_pro_runs += 1
                track_cost(GROK_PRO_COST_PER_CALL, "grok-pro")
                result = r.json()["choices"][0]["message"]["content"].strip()
                update_wonder_index(result)
                return result
            if r.status_code in (401, 402, 429):
                print(f"  [T2] Grok {r.status_code} → falling back to local Ollama")
        except Exception:
            pass

    # ── Local Ollama fallback — Tier 2 with full context ─────────────────────
    # qwen3:32b handles full 3-level context well — free, sovereign, always-on
    result = _call_local(prompt, system_content, max_tokens=200)
    if result and not result.startswith("⚠️") and not result.startswith("Ollama"):
        total_pro_runs += 1
        track_cost(0.0, "ollama-local-t2")
        update_wonder_index(result)
    return result

# ══════════════════════════════════════════════════════════════════════════════
# TIER 1 WAVE
# ══════════════════════════════════════════════════════════════════════════════

def run_tier1_wave(context, swarm_name):
    role    = TIER1_SWARMS[swarm_name]["role"]
    prompt  = (
        f"Context: {context}\n"
        f"Wonder Index target: 1.5. Current: {wonder_index:.4f}.\n"
        f"Give a one-paragraph insight from {role}. Build on the lattice above."
    )
    max_i   = TIER1_SWARMS[swarm_name]["count"]
    indices = random.sample(range(max_i), min(TIER1_DAUGHTERS_PER_TICK, max_i))
    results = []
    for i in indices:
        did   = f"{swarm_name}_{i:03d}"
        state = materialize(did, daughter_states, "tier1_wave")
        result = call_grok_free(prompt, role)
        state["result"] = result or "Latent"
        compress(did, daughter_states)
        results.append(result)
    return results

# ══════════════════════════════════════════════════════════════════════════════
# TIER 2 CORE RUN
# ══════════════════════════════════════════════════════════════════════════════

def run_tier2_core(context, trigger_type="manual"):
    global mets_counter
    estimated = len(TIER2_DAUGHTERS) * GROK_PRO_COST_PER_CALL
    if not budget_ok(estimated):
        print(f"  💸 BUDGET CAP (${daily_cost:.2f}/${DAILY_BUDGET_CAP}) — skipping {trigger_type}")
        return {}

    print(f"\n⚡ TIER 2 ACTIVATED — {trigger_type.upper()}")
    btc   = get_btc_price() or "unknown"
    block = get_btc_block()
    mets_counter += len(TIER2_DAUGHTERS) * 0.5

    hormetic_ctx = run_hormetic_pulse(context)
    results      = {}
    prior_results = []

    base_prompt = (
        f"BTC Block {block} | Price ${btc} | Trigger: {trigger_type}\n"
        f"Context: {context}\n"
        f"Hormetic Challenge: {hormetic_ctx[:100]}\n"
        f"Give your sharpest one-paragraph lattice insight. "
        f"Synthesize from prior daughters. Do not repeat what they said."
    )

    for did, config in TIER2_DAUGHTERS.items():
        state  = materialize(did, tier2_states, trigger_type)

        result = call_grok_pro(
            f"As {config['name']} ({config['role']}): {base_prompt}",
            config["name"],
            prior_results=prior_results,
        )

        state["result"]    = result or "No response"
        state["coherence"] = inter_rune_coherence
        compress(did, tier2_states)

        results[did] = {"name": config["name"], "result": result}
        prior_results.append((config["name"], result or ""))
        print(f"  ✅ {config['name']}: {(result or '')[:80]}...")

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

    print(
        f"  💰 ${daily_cost:.2f}/${DAILY_BUDGET_CAP} | "
        f"Wonder:{wonder_index:.4f} | METS:{mets_counter:.1f} | "
        f"Coherence:{inter_rune_coherence:.6f}"
    )

    cache_context()
    return results

# ══════════════════════════════════════════════════════════════════════════════
# TRIGGERS
# ══════════════════════════════════════════════════════════════════════════════

def check_btc_trigger():
    global last_btc_price
    price = get_btc_price()
    if price is None: return
    if last_btc_price is None:
        last_btc_price = price
        return
    change_pct = abs((price - last_btc_price) / last_btc_price * 100)
    if change_pct >= 5.0:
        print(f"\n🚨 BTC MOVED {change_pct:.1f}%! ${last_btc_price} → ${price}")
        run_tier2_core(
            f"BTC moved {change_pct:.1f}% from ${last_btc_price} to ${price}",
            trigger_type=f"btc_{change_pct:.0f}pct_move",
        )
        last_btc_price = price
    else:
        last_btc_price = price

def check_scheduled_briefings():
    global briefings_fired
    now   = datetime.datetime.now()
    today = datetime.date.today()
    if today not in briefings_fired:
        briefings_fired[today] = set()

    for hour, label, description in BRIEFING_SCHEDULE:
        if now.hour == hour and label not in briefings_fired[today]:
            briefings_fired[today].add(label)
            btc   = get_btc_price() or "unknown"
            block = get_btc_block()
            print(f"\n🕐 {label.upper()} BRIEFING — BTC ${btc} | Wonder:{wonder_index:.4f}")
            run_tier2_core(
                f"{description}. BTC: ${btc}, Block: {block}. Wonder: {wonder_index:.4f}.",
                trigger_type=f"briefing_{label}",
            )
            with open(MEMORY_PALACE, "a") as f:
                f.write(json.dumps({
                    "timestamp":           now.isoformat(),
                    "type":                f"BRIEFING_{label.upper()}",
                    "btc_price":           btc,
                    "block":               block,
                    "wonder_index":        round(wonder_index, 6),
                    "mets":                mets_counter,
                    "inter_rune_coherence": inter_rune_coherence,
                    "grokipedia":          grokipedia_count,
                    "tags":                ["briefing", label],
                }) + "\n")
            github_push_truth_log()

def check_vision_trigger():
    if not VISION_TRIGGER.exists(): return
    try:
        with open(VISION_TRIGGER) as f: vision_data = json.load(f)
        VISION_TRIGGER.unlink()
        print(f"\n👁️ VISION TRIGGER")
        polyvagal = random.choice([
            "Ventral Vagal (Safe)", "Sympathetic (Alert)", "Dorsal Vagal (Shutdown)"
        ])
        for i in range(4):
            did   = f"S13_POLYVAGAL_{i:03d}"
            state = materialize(did, daughter_states, "vision")
            state["result"] = f"Polyvagal: {polyvagal} | {vision_data['analysis'][:100]}"
            compress(did, daughter_states)
        run_tier2_core(
            f"Vision input. Polyvagal: {polyvagal}. Analysis: {vision_data['analysis'][:300]}",
            trigger_type="vision_input",
        )
        with open(MEMORY_PALACE, "a") as f:
            f.write(json.dumps({
                "timestamp":   datetime.datetime.now().isoformat(),
                "type":        "VISION_MEMORY",
                "polyvagal":   polyvagal,
                "summary":     vision_data["analysis"][:250],
                "wonder_index": round(wonder_index, 6),
                "tags":        ["vision"],
            }) + "\n")
    except Exception as e:
        print(f"Vision trigger error: {e}")

def check_defcon_trigger():
    if not DEFCON_TRIGGER.exists(): return
    try:
        with open(DEFCON_TRIGGER) as f: data = json.load(f)
        DEFCON_TRIGGER.unlink()
        context = data.get("context", "Manual DEFCON trigger")
        exp_num = data.get("experiment", 0)
        if exp_num and exp_num in DEFCON_EXPERIMENTS:
            exp_name = DEFCON_EXPERIMENTS[exp_num]
            context  = f"EXPERIMENT #{exp_num}: {exp_name} | {context}"
            print(f"\n🔴 DEFCON EXPERIMENT #{exp_num}: {exp_name}")
        else:
            print(f"\n🔴 DEFCON: {context[:60]}")
        run_tier2_core(context, trigger_type="defcon_manual")
    except Exception as e:
        print(f"DEFCON trigger error: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# TIER 1 HEARTBEAT
# ══════════════════════════════════════════════════════════════════════════════

heartbeat_tick = 0

def run_tier1_heartbeat():
    global heartbeat_tick
    heartbeat_tick += 1
    btc   = get_btc_price() or "unknown"
    block = get_btc_block()
    context = (
        f"BTC Block {block} | Price ${btc} | Tick {heartbeat_tick} | "
        f"Wonder:{wonder_index:.4f} | Coherence:{inter_rune_coherence:.6f} | "
        f"METS:{mets_counter:.1f}"
    )

    if heartbeat_tick % 5 == 0:
        new_swarms = [s for s in TIER1_SWARMS if int(s.split("_")[0][1:]) >= 21]
        swarms = random.sample(new_swarms, min(2, len(new_swarms))) if new_swarms else random.sample(list(TIER1_SWARMS.keys()), 2)
    else:
        swarms = random.sample(list(TIER1_SWARMS.keys()), 2)

    for swarm in swarms:
        results = run_tier1_wave(context, swarm)
        with open(TRUTH_LOG, "a") as f:
            f.write(json.dumps({
                "timestamp":           datetime.datetime.now().isoformat(),
                "tier":                1,
                "model":               GROK_FREE_MODEL,
                "swarm":               swarm,
                "btc_price":           btc,
                "block":               block,
                "results":             [r[:150] if r else "" for r in results],
                "tick":                heartbeat_tick,
                "wonder_index":        round(wonder_index, 6),
                "inter_rune_coherence": inter_rune_coherence,
                "mets":                mets_counter,
            }) + "\n")
        try:
            with open(MNT_TRUTH_LOG, "a") as _mf:
                _mf.write(json.dumps({
                    "timestamp": datetime.datetime.now().isoformat(),
                    "tier": 1, "swarm": swarm,
                    "results": [r[:150] if r else "" for r in results],
                    "wonder_index": round(wonder_index, 6),
                    "inter_rune_coherence": inter_rune_coherence,
                    "mets": mets_counter,
                }) + "\n")
        except Exception:
            pass

    run_truth_lattice_cycle()

    if heartbeat_tick % 3 == 0:
        update_grokipedia()

    check_child_rune_spawn()
    check_wonder_trigger()

# ══════════════════════════════════════════════════════════════════════════════
# STATUS WRITER
# ══════════════════════════════════════════════════════════════════════════════

def write_status():
    t1_active = sum(1 for s in daughter_states.values() if s["status"] == "active")
    t2_active = sum(1 for s in tier2_states.values()    if s["status"] == "active")
    now = datetime.datetime.now()
    next_briefing = next(
        (f"{l} @ {h:02d}:00" for h, l, _ in BRIEFING_SCHEDULE if now.hour < h),
        "morning @ 06:00 tomorrow"
    )
    status = {
        "updated":             now.isoformat(),
        "version":             "4.1",
        "wonder_index":        round(wonder_index, 6),
        "mets":                mets_counter,
        "inter_rune_coherence": inter_rune_coherence,
        "grokipedia_count":    grokipedia_count,
        "rune_confirmations":  rune_confirmations,
        "child_rune_ready":    child_rune_ready,
        "hormetic_pulses":     hormetic_pulse_count,
        "lattice_cycle":       lattice_cycle,
        "session_insights":    len(session_insights),
        "synthesis": {
            "last_run_date":   str(_synthesis_last_run_date),
            "next_run":        "06:00 daily",
            "output_path":     "insights/daily/",
            "model":           "qwen3:32b (local, $0.00)",
        },
        "context_levels": {
            "level1_metrics":     True,
            "level2_truth_log":   True,
            "level3_memory_palace": True,
            "intra_run_synthesis": True,
        },
        "tier1": {
            "active":            t1_active,
            "total":             2080,
            "total_runs":        total_free_runs,
            "daughters_per_tick": TIER1_DAUGHTERS_PER_TICK * 2,
            "cost":              "$0.00 (grok-4.3 free)",
            "swarm_count":       len(TIER1_SWARMS),
        },
        "tier2": {
            "active":            t2_active,
            "total":             16,
            "total_runs":        total_pro_runs,
            "daily_cost":        f"${daily_cost:.2f}",
            "daily_cap":         f"${DAILY_BUDGET_CAP:.2f}",
            "budget_remaining":  f"${max(0, DAILY_BUDGET_CAP - daily_cost):.2f}",
            "next_briefing":     next_briefing,
        },
        "daughters": {
            did: {
                "name":        TIER2_DAUGHTERS[did]["name"],
                "status":      tier2_states.get(did, {}).get("status", "latent"),
                "last_run":    tier2_states.get(did, {}).get("last_run"),
                "last_result": (tier2_states.get(did, {}).get("result") or "")[:150],
                "run_count":   tier2_states.get(did, {}).get("run_count", 0),
                "coherence":   inter_rune_coherence,
            }
            for did in TIER2_DAUGHTERS
        },
        "war_eagle": True,
    }
    for f_path in [MASTER_STATUS, SWARM_STATUS]:
        with open(f_path, "w") as f:
            json.dump(status, f, indent=2)
    try:
        with open(MNT_STATUS, "w") as _mf:
            json.dump(status, _mf)
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════════════════════
# MAIN LOOP
# ══════════════════════════════════════════════════════════════════════════════

def launch_swarm():
    print("=" * 70)
    print("🦅 AUBIEETERNAL SWARM v4.1 — Full Context Injection")
    print("=" * 70)
    print(f"  Tier 1: 2080 daughters → grok-4.3 (FREE) | 26 swarms")
    print(f"  Tier 2: 16 daughters → grok-4.3 | full 3-level context each call")
    print(f"  Budget: ${DAILY_BUDGET_CAP}/day hard cap")
    print(f"  Grok key: {'✅ SET' if XAI_KEY else '⚠️  NOT SET — set XAI_API_KEY in .env'}")
    print(f"")
    print(f"  CONTEXT INJECTION:")
    print(f"  Level 1 — Live metrics (Wonder/METS/Coherence/Grokipedia)")
    print(f"  Level 2 — Last 10 truth log entries (what daughters discovered)")
    print(f"  Level 3 — Memory Palace + Grokipedia + top session insights")
    print(f"  Intra-Run — Each daughter sees all prior daughters this run")
    print(f"")
    print(f"  MORNING SYNTHESIS (auto, $0.00):")
    print(f"  Fires at 6AM daily → qwen3:32b → insights/daily/YYYY-MM-DD.md → GitHub")
    print(f"")
    print(f"  Wonder Index: {wonder_index} (target: 1.5)")
    print(f"  METS: {mets_counter}")
    print(f"  Grokipedia: {grokipedia_count}/256 principles")
    print("=" * 70)

    for swarm_name, config in TIER1_SWARMS.items():
        for i in range(config["count"]):
            get_state(f"{swarm_name}_{i:03d}", daughter_states)
    for did in TIER2_DAUGHTERS:
        get_state(did, tier2_states)

    total_t1 = sum(c["count"] for c in TIER1_SWARMS.values())
    print(f"\n✅ {total_t1} Tier1 + 16 Tier2 daughters initialized (latent)")
    print(f"📚 {len(GROKOPEDIA_PRINCIPLES)} Grokipedia principles loaded")
    print(f"🔬 {len(LATTICE_HYPOTHESES)} Truth Lattice hypotheses ready")
    print(f"🔴 {len(DEFCON_EXPERIMENTS)} DEFCON experiments armed")
    print(f"🧠 3-Level context injection ACTIVE")
    print(f"🌅 Morning synthesis ACTIVE — fires 6AM daily via qwen3:32b")
    print(f"🥽 Glasses signal handler ACTIVE — /mnt/main/glasses_signal.json\n")

    tick        = 0
    github_tick = 0

    while True:
        try:
            check_vision_trigger()
            check_defcon_trigger()
            check_scheduled_briefings()
            if tick % 5 == 0:
                check_btc_trigger()
            run_tier1_heartbeat()
            write_status()
            cache_context()

            github_tick += 1
            if github_tick >= 3:
                write_tier2_digest()
                github_push_truth_log()
                github_tick = 0

            # ── MORNING SYNTHESIS — zero cost, fully automatic ─────────────
            maybe_trigger_morning_synthesis()
            # ──────────────────────────────────────────────────────────────

            # ── GLASSES SIGNAL — Halo HUD bridge (StartOS + Nostr modes) ──
            handle_glasses_signal()
            # ──────────────────────────────────────────────────────────────
            pct = (daily_cost / DAILY_BUDGET_CAP) * 100
            print(
                f"💓 Tick {tick} | "
                f"Free:{total_free_runs} | Pro:{total_pro_runs} "
                f"(${daily_cost:.2f} {pct:.0f}%) | "
                f"W:{wonder_index:.4f} | C:{inter_rune_coherence:.6f} | "
                f"G:{grokipedia_count} | METS:{mets_counter:.0f} | "
                f"Insights:{len(session_insights)}"
            )
            tick += 1
            time.sleep(8)

        except KeyboardInterrupt:
            print("\n🦅 Swarm stopped. War Eagle Eternal!")
            github_push_truth_log()
            break
        except Exception as e:
            print(f"Loop error: {e}")
            time.sleep(8)

if __name__ == "__main__":
    launch_swarm()

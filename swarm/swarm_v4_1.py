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

import os, json, sys, time, datetime, random, requests, subprocess, threading

# ── Timezone for scheduling ───────────────────────────────────────────────────
# The container's system clock is UTC, so bare datetime.now() made the 6AM /
# noon / 6PM / 11PM triggers fire 4-5 hours early. _now_eastern() pins schedule
# checks to Eastern time regardless of the container clock.
try:
    from zoneinfo import ZoneInfo
    _EASTERN = ZoneInfo("America/New_York")
except Exception:
    _EASTERN = datetime.timezone(datetime.timedelta(hours=-4))  # EDT fallback if tzdata missing

def _now_eastern():
    return datetime.datetime.now(_EASTERN)
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
# ── Path resolution: prefer /mnt/main/repo, fall back to /home/start9 ─────────
_REPO_DIR = Path("/mnt/main/repo")
_FALLBACK  = Path("/home/start9")
WORK_DIR   = _REPO_DIR if _REPO_DIR.exists() else _FALLBACK
WORK_DIR.mkdir(parents=True, exist_ok=True)

# Found 2026-09-05: this file lives in swarm/, but its lazy `from X import Y`
# triggers (morning_synthesis, curriculum_autogen, email_watch,
# epistemic_commons, epistemic_commons_api, living_lattice) all import
# repo-root sibling modules. aubie-swarm.service runs `python -u
# swarm/swarm_v4_1.py` - WorkingDirectory sets the process's cwd, but Python
# sets sys.path[0] to the *script's own directory* (swarm/) regardless of
# cwd, so every one of those imports raised ModuleNotFoundError (a subclass
# of ImportError) and got mislabeled "not found in repo" by the broad
# `except ImportError` around each one - the files were never missing, moved,
# or wrong; sys.path just never had the repo root on it. Confirmed this has
# silently blocked all 7 scheduled triggers since their call sites were wired
# in around 2026-08-25 (see ERROR_LEDGER.md).
sys.path.insert(0, str(WORK_DIR))

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
# Cost control: default OFF = swarm runs 100%% on the free local model ($0/day).
# Set USE_GROK=1 in api_keys.env to re-enable paid Grok for the daughters.
USE_GROK         = os.environ.get("USE_GROK", "0") == "1"
GITHUB_TOKEN     = os.getenv("GITHUB_TOKEN", "")

# ── Cost / Budget Config ──────────────────────────────────────────────────────
GROK_PRO_COST_PER_CALL  = 0.02
GROK_FREE_COST_PER_CALL = 0.00
DAILY_BUDGET_CAP        = 5.00
TIER1_DAUGHTERS_PER_TICK = 3   # throttled: one GPU can't run 20/tick AND serve synthesis/humanity/kid-portal
SWARMS_PER_TICK          = 2   # how many of the 26 Tier1 swarm groups get a wave each heartbeat

# ── Swarm Mode — read from /mnt/main/swarm_mode.json, set by the Streamlit
# "Swarm Mode" tab. Was write-only for months (the tab wrote this file, but
# nothing here ever read it back - the Full/Standard/Experimental buttons
# changed nothing about the running swarm). Found + wired live 2026-08-25.
# The old tab claimed specific daughter/swarm totals and $/day costs that
# don't fit the real architecture (a fixed 26-swarm/2080-daughter roster,
# a random subset actually ticked each heartbeat, $0/day by default since
# USE_GROK is off) - so the real, honest knobs this controls are how many
# swarms + daughters run per tick, and the budget ceiling for if a paid
# Grok key is ever enabled.
# ══════════════════════════════════════════════════════════════════════════════
SWARM_MODE_FILE = Path("/mnt/main/swarm_mode.json")
SWARM_MODE_CONFIG = {
    "Standard":     {"swarms_per_tick": 2, "daughters_per_tick": 3, "budget_cap": 2.50},
    "Full":         {"swarms_per_tick": 2, "daughters_per_tick": 3, "budget_cap": 5.00},
    "Experimental": {"swarms_per_tick": 4, "daughters_per_tick": 5, "budget_cap": 8.00},
}
_current_swarm_mode = None  # tracks last-applied mode so we only log on change

def apply_swarm_mode():
    """Called every tick. Reads swarm_mode.json (written by the Streamlit
    Swarm Mode tab) and applies its mode to the real per-tick throughput
    and budget cap. Cheap (~100 bytes) - fine to check every tick so a
    mode change takes effect on the very next one, matching what the UI
    already told the user ('swarm picks it up on next tick')."""
    global _current_swarm_mode, TIER1_DAUGHTERS_PER_TICK, SWARMS_PER_TICK, DAILY_BUDGET_CAP
    try:
        mode = json.loads(SWARM_MODE_FILE.read_text()).get("mode", "Standard")
    except Exception:
        mode = "Standard"

    if mode not in SWARM_MODE_CONFIG:
        mode = "Standard"

    if mode != _current_swarm_mode:
        cfg = SWARM_MODE_CONFIG[mode]
        TIER1_DAUGHTERS_PER_TICK = cfg["daughters_per_tick"]
        SWARMS_PER_TICK          = cfg["swarms_per_tick"]
        DAILY_BUDGET_CAP         = cfg["budget_cap"]
        _current_swarm_mode      = mode
        print(f"[swarm-mode] ⚔️  Mode → {mode} | "
              f"{SWARMS_PER_TICK} swarms/tick × {TIER1_DAUGHTERS_PER_TICK} daughters | "
              f"budget cap ${DAILY_BUDGET_CAP:.2f}/day")

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

# 2026-09-05: wonder_index had no decay independent of new content - once a
# run pushed it up (which happens fast; see update_wonder_index()'s awe-word
# scoring), it just sat there, since max(0.5, min(2.0, wonder_index + delta))
# only ever moves on a *new* result. The wonder-trigger hysteresis (ea586f83)
# stops that from re-firing Tier-2 every tick, but the index itself stayed a
# dead gauge - every restart looked like a permanent spike within the hour,
# with no way back down. wonder_last_update_ts tracks real wall-clock time so
# decay is computed from actual elapsed seconds, not tick count (a tick can
# be delayed by a slow Tier-2 call, GPU contention, etc.).
WONDER_FLOOR                    = 0.5
WONDER_CEILING                  = 2.0
WONDER_DECAY_HALF_LIFE_SECONDS  = 3 * 3600  # 3h - middle of the suggested 2-4h range
wonder_last_update_ts           = time.time()
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
    """Background thread: tier2_digest → qwen2.5:7b → insights/daily/YYYY-MM-DD.md"""
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
    now   = _now_eastern()
    today = now.date()

    # Fire once per day during the 6AM Eastern hour. Full-hour window (no more
    # minute<5) so a slow CPU tick can't skip the old 5-minute slot.
    if now.hour == 6 and _synthesis_last_run_date != today:
        _synthesis_last_run_date = today   # set immediately to block re-entry
        print(f"[synthesis] ⏰ 6AM trigger fired for {today.isoformat()}")
        t = threading.Thread(target=_run_synthesis_background, daemon=True)
        t.start()

# ══════════════════════════════════════════════════════════════════════════════
# CURRICULUM AUTOGEN — the curriculum should always be trying to grow.
# Drafts one candidate lesson a day via local Ollama ($0.00, no Grok budget
# touched) and submits it as a PENDING proposal through the same
# curriculum_proposals.py review pipeline a human submission goes through
# (Submit Curriculum → Review Queue in app.py) — it never self-approves.
# See curriculum_autogen.py for the generator itself.
# ══════════════════════════════════════════════════════════════════════════════
_curriculum_autogen_last_run_date = None

def _run_curriculum_autogen_background():
    global _curriculum_autogen_last_run_date
    try:
        from curriculum_autogen import run_curriculum_autogen
        print("[curriculum-autogen] 🌱 Background thread started...")
        result = run_curriculum_autogen()
        if result.get("ok"):
            _curriculum_autogen_last_run_date = datetime.date.today()
            print(f"[curriculum-autogen] ✅ Proposed \"{result['title']}\" "
                  f"(id: {result['proposal_id']}) — awaiting human review")
        else:
            print(f"[curriculum-autogen] ⚠️  Skipped: {result.get('reason')}")
    except ImportError:
        print("[curriculum-autogen] ❌ curriculum_autogen.py not found in repo")
    except Exception as e:
        print(f"[curriculum-autogen] ❌ Error: {e}")

def maybe_trigger_curriculum_autogen():
    """
    Called every tick. Fires once per day at 9AM Eastern (after the 6AM
    synthesis run has the GPU to itself, before the noon briefing).
    Non-blocking — runs in a daemon thread. Guards against double-fire
    with _curriculum_autogen_last_run_date, same pattern as morning
    synthesis above.
    """
    global _curriculum_autogen_last_run_date
    now   = _now_eastern()
    today = now.date()

    if now.hour == 9 and _curriculum_autogen_last_run_date != today:
        _curriculum_autogen_last_run_date = today
        print(f"[curriculum-autogen] ⏰ 9AM trigger fired for {today.isoformat()}")
        t = threading.Thread(target=_run_curriculum_autogen_background, daemon=True)
        t.start()

# ══════════════════════════════════════════════════════════════════════════════
# EMAIL WATCH — real inbox via Proton Mail Bridge (local IMAP,
# aubie-proton-bridge.service), local Ollama picks out anything task/
# deadline-shaped. See email_watch.py for the reader/extractor itself and
# its PRIVACY note - the digest never leaves this machine, never gets
# pushed anywhere, and only genuinely urgent deadlines get spoken aloud
# unprompted (the daily digest just gets written to a private file).
# ══════════════════════════════════════════════════════════════════════════════
_email_digest_last_run_date = None

def _run_email_digest_background():
    global _email_digest_last_run_date
    try:
        from email_watch import daily_digest
        print("[email-watch] 📧 Daily digest background thread started...")
        result = daily_digest()
        if "error" in result:
            print(f"[email-watch] ⚠️  Digest error: {result['error']}")
        else:
            _email_digest_last_run_date = datetime.date.today()
            print(f"[email-watch] ✅ Digest written — {len(result.get('tasks', []))} "
                  f"task(s) found in {result.get('messages_scanned', 0)} messages")
    except ImportError:
        print("[email-watch] ❌ email_watch.py not found in repo")
    except Exception as e:
        print(f"[email-watch] ❌ Error: {e}")

def maybe_trigger_email_digest():
    """Fires once per day at 7AM Eastern (between the 6AM synthesis run
    and the 9AM curriculum-autogen trigger). Same daemon-thread + date-
    guard pattern as both of those."""
    global _email_digest_last_run_date
    now   = _now_eastern()
    today = now.date()

    if now.hour == 7 and _email_digest_last_run_date != today:
        _email_digest_last_run_date = today
        print(f"[email-watch] ⏰ 7AM digest trigger fired for {today.isoformat()}")
        t = threading.Thread(target=_run_email_digest_background, daemon=True)
        t.start()

def _run_email_urgent_check_background():
    try:
        from email_watch import check_urgent
        urgent = check_urgent(speak=True)
        if urgent and not (len(urgent) == 1 and "error" in urgent[0]):
            print(f"[email-watch] 🚨 {len(urgent)} urgent item(s) spoken")
    except ImportError:
        print("[email-watch] ❌ email_watch.py not found in repo")
    except Exception as e:
        print(f"[email-watch] ❌ Urgent check error: {e}")

def maybe_check_email_urgent(tick: int):
    """Called every tick, actually runs every 30 ticks (~15 min at the
    30s tick interval) - frequent enough to catch a same-day deadline
    with real lead time, not so frequent it hammers Ollama/IMAP. Each
    urgent item is only ever spoken once (see email_watch.py's dedup),
    so overlapping windows across runs can't cause a repeat."""
    if tick % 30 == 0:
        t = threading.Thread(target=_run_email_urgent_check_background, daemon=True)
        t.start()

# ══════════════════════════════════════════════════════════════════════════════
# EPISTEMIC COMMONS — daily publish of honesty-scored signal as CC0 public
# domain, both the human-readable coherence letter/seeds (epistemic_commons.py)
# and the machine-readable API endpoints (epistemic_commons_api.py, which also
# runs the day's Grokipedia pipeline). Both modules' own docstrings already
# said "called from morning_synthesis" - that wiring was drafted in
# SWARM_PATCH.py (repo root) but never actually applied here, so in practice
# this only ever ran when a human clicked the manual buttons in the Streamlit
# "Epistemic Commons" tab. Found live 2026-08-25 (app.py's tab hadn't updated
# in ~3 months). Runs at 8AM Eastern - after the 6AM synthesis and 7AM email
# digest have the GPU, before the 9AM curriculum-autogen trigger.
# ══════════════════════════════════════════════════════════════════════════════
_epistemic_commons_last_run_date = None

def _run_epistemic_commons_background():
    global _epistemic_commons_last_run_date
    try:
        from epistemic_commons import EpistemicCommons
        print("[epistemic-commons] 🌐 Daily publish background thread started...")
        result = EpistemicCommons().run_daily_publish()
        print(f"[epistemic-commons] Commons publish: {result.get('status','?')}")
    except ImportError:
        print("[epistemic-commons] ❌ epistemic_commons.py not found in repo")
    except Exception as e:
        print(f"[epistemic-commons] ❌ Commons publish error: {e}")

    try:
        from epistemic_commons_api import update_epistemic_commons
        api_result = update_epistemic_commons()
        print(f"[epistemic-commons] API endpoints updated: {list(api_result.get('api', {}).keys()) if isinstance(api_result.get('api'), dict) else api_result.get('api')}")
    except ImportError:
        print("[epistemic-commons] ❌ epistemic_commons_api.py not found in repo")
    except Exception as e:
        print(f"[epistemic-commons] ❌ API update error: {e}")

    _epistemic_commons_last_run_date = datetime.date.today()

def maybe_trigger_epistemic_commons():
    """Called every tick. Fires once per day at 8AM Eastern. Same
    daemon-thread + date-guard pattern as morning synthesis, curriculum
    autogen, and the email digest above."""
    global _epistemic_commons_last_run_date
    now   = _now_eastern()
    today = now.date()

    if now.hour == 8 and _epistemic_commons_last_run_date != today:
        _epistemic_commons_last_run_date = today   # set immediately to block re-entry
        print(f"[epistemic-commons] ⏰ 8AM trigger fired for {today.isoformat()}")
        t = threading.Thread(target=_run_epistemic_commons_background, daemon=True)
        t.start()

# ══════════════════════════════════════════════════════════════════════════════
# LIVING LATTICE — daily anonymous signal (coherence, lessons, wonder index),
# same never-auto-wired gap as Epistemic Commons above: living_lattice.py's
# own docstring already says "Called from morning_synthesis" but nothing
# here ever called it - it only ever ran when a human clicked "Publish
# Today's Signal" in the Streamlit Living Lattice tab. Found live 2026-08-25
# while writing onboarding copy that promised new families this is "on by
# default" - which wasn't true until this. Cheap (pure local aggregation,
# no AI calls), so no GPU-contention reason to avoid an early slot; runs at
# 10AM Eastern, after curriculum autogen (9AM) has the GPU to itself.
# ══════════════════════════════════════════════════════════════════════════════
_living_lattice_last_run_date = None

def _run_living_lattice_background():
    global _living_lattice_last_run_date
    try:
        from living_lattice import LivingLattice
        print("[living-lattice] 🕸️  Daily publish background thread started...")
        result = LivingLattice().publish_daily_signal()
        print(f"[living-lattice] Signal publish: {result.get('status','?')}")
    except ImportError:
        print("[living-lattice] ❌ living_lattice.py not found in repo")
    except Exception as e:
        print(f"[living-lattice] ❌ Signal publish error: {e}")
    _living_lattice_last_run_date = datetime.date.today()

def maybe_trigger_living_lattice():
    """Called every tick. Fires once per day at 10AM Eastern. Same
    daemon-thread + date-guard pattern as the other daily jobs above."""
    global _living_lattice_last_run_date
    now   = _now_eastern()
    today = now.date()

    if now.hour == 10 and _living_lattice_last_run_date != today:
        _living_lattice_last_run_date = today   # set immediately to block re-entry
        print(f"[living-lattice] ⏰ 10AM trigger fired for {today.isoformat()}")
        t = threading.Thread(target=_run_living_lattice_background, daemon=True)
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

def decay_wonder_index(now: float | None = None) -> float:
    """Exponential-ish decay of wonder_index toward WONDER_FLOOR, based on
    REAL elapsed wall-clock seconds since the last touch (add or decay) -
    not "one tick = one unit". Called (a) once per main-loop heartbeat tick,
    so an idle lattice drifts down even when nothing new happens, and (b) at
    the top of update_wonder_index(), so time elapsed before a new result
    arrives is accounted for first. Because both paths measure elapsed time
    since wonder_last_update_ts and that timestamp is reset to "now" on
    every call, a decay call immediately after an add sees ~0 elapsed
    seconds and moves the index by ~0 - decay and a same-tick add never
    fight each other, without needing a separate skip flag."""
    global wonder_index, wonder_last_update_ts
    now = now if now is not None else time.time()
    elapsed = max(0.0, now - wonder_last_update_ts)
    if elapsed > 0 and wonder_index > WONDER_FLOOR:
        decayed = WONDER_FLOOR + (wonder_index - WONDER_FLOOR) * (
            0.5 ** (elapsed / WONDER_DECAY_HALF_LIFE_SECONDS)
        )
        wonder_index = max(WONDER_FLOOR, min(WONDER_CEILING, decayed))
    wonder_last_update_ts = now
    return wonder_index


def update_wonder_index(result_text):
    global wonder_index, session_insights
    decay_wonder_index()  # account for elapsed time since the last touch BEFORE adding
    awe_words = [
        "remarkable", "profound", "extraordinary", "infinite", "eternal",
        "coherent", "emergent", "beautiful", "truth", "pattern", "signal",
        "bitcoin", "sovereign", "antifragile", "quantum", "wonder",
        "insight", "discovery", "convergence", "alignment", "synthesis",
    ]
    hits  = sum(1 for w in awe_words if w in result_text.lower())
    delta = (hits * 0.003) - 0.001
    wonder_index = max(WONDER_FLOOR, min(WONDER_CEILING, wonder_index + delta))

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

# Hysteresis for the wonder-spike trigger. Found 2026-09-04: this was a bare
# level check (`if wonder_index >= 1.4`) called on every heartbeat tick, with
# no edge-detection - once wonder_index crossed 1.4 it kept firing every tick
# for as long as it stayed there, and it almost always stayed there because
# each Tier-2 response is full of the exact vocabulary update_wonder_index()
# scores as "awe," pushing it right back up. Confirmed against real logs: a
# 13h46m unattended run fired 501 Tier-2 pulses, with wonder_index >=1.4 on
# 99.3% of that day's ticks. Fix: only fire on the upward crossing (armed ->
# not armed), and only re-arm once the index drops back below 1.2, so a
# single elevated stretch produces one pulse, not one per tick.
_wonder_trigger_armed = True


def check_wonder_trigger():
    global _wonder_trigger_armed
    if _wonder_trigger_armed and wonder_index >= 1.4:
        _wonder_trigger_armed = False
        print(f"\n✨ WONDER SPIKE {wonder_index:.4f} — activating Tier 2!")
        run_tier2_core(
            f"Wonder Index reached {wonder_index:.4f}. Awe signal detected. Synthesize emergent insight.",
            trigger_type="wonder_spike"
        )
    elif not _wonder_trigger_armed and wonder_index < 1.2:
        _wonder_trigger_armed = True

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
        lines.append("PASTE INTO QWEN2.5:7B → Synthesize the 3 most important insights.")
        with open(digest_path, "w") as f:
            f.write("\n".join(lines))
        print(f"✅ Tier 2 digest written: {len(last_20)} entries")
    except Exception as e:
        print(f"⚠️ Digest error: {e}")

# ── Telemetry branch ──────────────────────────────────────────────────────
# The swarm's rolling operational logs (truth log, wonder/cost/lattice logs,
# status snapshots, context cache) used to be committed to `main` every few
# minutes: ~290 commits/day, ~89 MB of append-only .jsonl bundled into every
# `main.zip` download, and real code commits buried 1-in-50 in `git log`.
# They're pure diagnostics - nothing reads them from GitHub (the app reads
# them off the local /mnt/main disk), and no downloaded copy needs them. They
# now go to a separate `telemetry` branch, ~hourly, as off-box backup only.
# `main` stays code + curriculum + Epistemic Commons - the things other
# instances actually point at.
TELEMETRY_FILES = [
    "master_truth_log.jsonl", "wonder_log.jsonl", "truth_lattice_log.jsonl",
    "cost_log.jsonl", "memory_palace.jsonl",
    "swarm_status.json", "master_status.json", "context_cache.json",
    # 2026-09-04: tier2_digest.txt is rewritten every ~90s by
    # write_tier2_digest() right before each github_push_truth_log(), so it
    # was the last file forcing a `main` commit almost every cycle (276 of
    # 280 main commits in the preceding 24h were the "🦅 v4.1 auto-push"
    # heartbeat). Every consumer (file_io.get_tier2_digest, grokipedia.py,
    # morning_synthesis.py, app.py) reads it off the local disk, never from
    # GitHub, so it belongs with the telemetry snapshot, not on main.
    # truth_debt_ledger.jsonl is an append-only log — same treatment; its
    # rendered insights/truth_debt_report.md stays on main.
    "tier2_digest.txt", "truth_debt_ledger.jsonl",
]
TELEMETRY_BRANCH        = "telemetry"
TELEMETRY_PUSH_INTERVAL = 3600   # seconds - once an hour, not every tick
_last_telemetry_push    = 0.0

# Once-a-day "rig alive" pulse to main (replaces the every-90s heartbeat
# commit). One honest commit per calendar day, no fake Coherence.
STATUS_FILE               = "STATUS.md"
_last_status_heartbeat_date = None

# Rolling record of the last few telemetry-branch push attempts, so
# self_audit.py can detect "failing N cycles in a row" directly instead of
# parsing this function's print() output out of journalctl (fragile to
# message-format changes). Best-effort, same as everything else here.
TELEMETRY_PUSH_STATUS_PATH = (
    Path.home() / "AUBIEETERNAL" / "memory" / "self_audit" / "telemetry_push_status.json"
)


def _record_telemetry_push_result(ok: bool, detail: str) -> None:
    try:
        TELEMETRY_PUSH_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        history = []
        if TELEMETRY_PUSH_STATUS_PATH.exists():
            history = json.loads(TELEMETRY_PUSH_STATUS_PATH.read_text())
        history.append({"ts": time.time(), "ok": ok, "detail": (detail or "")[:200]})
        TELEMETRY_PUSH_STATUS_PATH.write_text(json.dumps(history[-10:]))
    except Exception:
        pass


# GitHub hard-rejects a push containing any single blob over 100 MB.
# ROTATION_MAX_BYTES (80 MB) is supposed to keep every TELEMETRY_FILES entry
# well under that, but 2026-09-05 found rotation and the push sharing one
# blind spot isn't enough of a guarantee to bet the whole push on: master_
# truth_log.jsonl crossing 100 MB silently blocked wonder_log.jsonl, cost_
# log.jsonl, truth_lattice_log.jsonl, and the status JSONs too, since they
# were all staged into the same tree/commit. This is the belt to rotation's
# suspenders - independent of whether rotation is working, one oversized
# file gets skipped-and-logged rather than taking the whole backup down.
TELEMETRY_MAX_FILE_BYTES = 95 * 1024 * 1024


def _maybe_push_telemetry_branch(repo):
    """Snapshot TELEMETRY_FILES onto the `telemetry` branch ~hourly, without
    ever touching main's working tree, index, or HEAD (throwaway index +
    commit-tree plumbing). Best-effort: any failure is logged and retried
    next hour."""
    global _last_telemetry_push
    now = time.time()
    if now - _last_telemetry_push < TELEMETRY_PUSH_INTERVAL:
        return
    try:
        tel = []
        for f in TELEMETRY_FILES:
            p = Path(repo) / f
            if not p.exists():
                continue
            size = p.stat().st_size
            if size > TELEMETRY_MAX_FILE_BYTES:
                print(f"  ⚠️ telemetry push: skipping {f} ({size / 1e6:.1f}MB > "
                      f"{TELEMETRY_MAX_FILE_BYTES / 1e6:.1f}MB cap, GitHub's hard limit is "
                      f"100MB) - would block the whole push")
                continue
            tel.append(f)
        if not tel:
            return
        env = dict(os.environ)
        env["GIT_INDEX_FILE"] = str(Path(repo) / ".git" / "telemetry.index")
        try:
            os.remove(env["GIT_INDEX_FILE"])
        except OSError:
            pass

        subprocess.run(["git", "-C", repo, "fetch", "origin",
                        f"{TELEMETRY_BRANCH}:refs/remotes/origin/{TELEMETRY_BRANCH}"],
                       capture_output=True, timeout=30)
        parent = subprocess.run(
            ["git", "-C", repo, "rev-parse", "--verify", "--quiet",
             f"refs/remotes/origin/{TELEMETRY_BRANCH}"],
            capture_output=True, text=True, timeout=10
        ).stdout.strip()
        if parent:
            subprocess.run(["git", "-C", repo, "read-tree", parent],
                           env=env, capture_output=True, timeout=15)

        subprocess.run(["git", "-C", repo, "update-index", "--add", "--"] + tel,
                       env=env, capture_output=True, text=True, timeout=20)
        tree = subprocess.run(["git", "-C", repo, "write-tree"],
                              env=env, capture_output=True, text=True,
                              timeout=15).stdout.strip()
        if not tree:
            return

        msg = "telemetry snapshot " + time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                    time.gmtime(now))
        ct = ["git", "-C", repo, "commit-tree", tree, "-m", msg]
        if parent:
            ct[5:5] = ["-p", parent]
        commit = subprocess.run(ct, capture_output=True, text=True,
                                timeout=15).stdout.strip()
        if not commit:
            return

        subprocess.run(["git", "-C", repo, "update-ref",
                        f"refs/heads/{TELEMETRY_BRANCH}", commit],
                       capture_output=True, timeout=10)
        if GITHUB_TOKEN:
            subprocess.run(
                ["git", "-C", repo, "remote", "set-url", "origin",
                 f"https://{GITHUB_TOKEN}@github.com/AUBIEETERNAL-INSTITUTE-INC/AUBIEETERNAL.git"],
                capture_output=True, timeout=10
            )
        push = subprocess.run(
            ["git", "-C", repo, "push", "origin",
             f"refs/heads/{TELEMETRY_BRANCH}:refs/heads/{TELEMETRY_BRANCH}"],
            capture_output=True, text=True, timeout=30
        )
        print(f"  📊 telemetry push: {push.returncode} | {push.stderr[:100]}")
        _record_telemetry_push_result(push.returncode == 0, push.stderr)
        _last_telemetry_push = now
    except Exception as e:
        print(f"  telemetry push error: {e}")
        _record_telemetry_push_result(False, str(e))

# ── Log rotation ─────────────────────────────────────────────────────────
# The append-only telemetry logs grow without bound (master_truth_log.jsonl
# alone hit 69 MB). Once a day, trim each to a recent window; the dropped
# prefix is gzipped into log_archive/ (gitignored, local-only) as
# belt-and-suspenders on top of the `telemetry` branch backup. Runs inside
# the swarm loop, so it never races the swarm's own appends. Uses the
# append-only + chronological property: find the byte offset of the first
# line newer than the cutoff, gzip everything before it, keep the rest.
LOG_ROTATION = {
    TRUTH_LOG:   30,   # master_truth_log.jsonl - full reasoning/briefing log
    WONDER_LOG:   7,   # wonder_log.jsonl - ~1 line / 2 s, low value per line
    COST_LOG:    90,   # cost_log.jsonl - kept longer, useful for budgeting
    LATTICE_LOG: 30,   # truth_lattice_log.jsonl
    # memory_palace.jsonl deliberately NOT rotated - 32 KB, semantically rich
}
LOG_ARCHIVE_DIR         = WORK_DIR / "log_archive"
_log_rotation_last_date = None

# 2026-09-05: master_truth_log.jsonl reached 152 MB in ~11.5 days (well
# inside its own 30-day keep window - the age-based cutoff correctly found
# nothing old enough to trim yet) and blocked the telemetry-branch push once
# it crossed GitHub's 100 MB hard limit (see ERROR_LEDGER.md's Incidents
# section). A big chunk of that growth was a single 13h46m runaway, so a
# pure age-based cap can't protect against one high-volume day/incident
# regardless of how short the window is. Applies to all four LOG_ROTATION
# files, not just the one that broke - any of them could spike the same way.
# 80 MB leaves real margin under the 100 MB limit. Rotation still only runs
# once/day (maybe_trigger_log_rotation's existing gate) - the wonder-trigger
# hysteresis + Tier-2 hourly cap fixed the same day are what actually bound
# how much a single day can grow by now, this is the backstop under that.
ROTATION_MAX_BYTES = 80 * 1024 * 1024

def _rotate_one_jsonl(path, keep_days, max_bytes=None):
    if not path.exists():
        return
    size = path.stat().st_size
    if size == 0:
        return
    cutoff = datetime.datetime.now() - datetime.timedelta(days=keep_days)
    size_cutoff_pos = max(0, size - max_bytes) if max_bytes else 0

    split_at_date = None       # byte offset of the first line new enough by age
    split_at_size = None       # byte offset of the first line boundary at/after size_cutoff_pos
    pos = 0
    with open(path, "rb") as f:
        for raw in f:
            if split_at_size is None and max_bytes is not None and pos >= size_cutoff_pos:
                split_at_size = pos
            line = raw.decode("utf-8", "replace").strip()
            if line and split_at_date is None:
                ts = None
                try:
                    t = json.loads(line).get("timestamp")
                    if t:
                        ts = datetime.datetime.fromisoformat(
                            str(t).replace("Z", "").split("+")[0].split(".")[0])
                except Exception:
                    pass
                if ts is not None and ts >= cutoff:
                    split_at_date = pos
            pos += len(raw)
            if split_at_date is not None and (max_bytes is None or split_at_size is not None):
                break
    # split_at_date None -> no line newer than cutoff (swarm idle > keep_days,
    #                       or no parseable timestamps): the age check alone
    #                       contributes nothing to trim (same as before this
    #                       change - the size check below is independent).
    # split_at_*   0     -> nothing old enough to trim yet by that criterion.
    # The kept tail must satisfy BOTH constraints, so archive up to whichever
    # cutoff would archive more.
    split_at = max(split_at_date or 0, split_at_size or 0)
    if not split_at:
        return
    LOG_ARCHIVE_DIR.mkdir(exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    arc = LOG_ARCHIVE_DIR / f"{path.name}.{stamp}.gz"
    tmp = path.with_name(path.name + ".rot")
    import gzip, shutil
    with open(path, "rb") as src:
        with gzip.open(arc, "wb") as a:
            remaining = split_at
            while remaining > 0:
                chunk = src.read(min(1 << 20, remaining))
                if not chunk:
                    break
                a.write(chunk)
                remaining -= len(chunk)
        with open(tmp, "wb") as k:
            shutil.copyfileobj(src, k)
    os.replace(tmp, path)
    print(f"  🧹 rotated {path.name}: archived {split_at} bytes -> {arc.name}")

def maybe_trigger_log_rotation():
    global _log_rotation_last_date
    today = datetime.date.today()
    if _log_rotation_last_date == today:
        return
    _log_rotation_last_date = today
    for path, days in LOG_ROTATION.items():
        try:
            _rotate_one_jsonl(path, days, max_bytes=ROTATION_MAX_BYTES)
        except Exception as e:
            print(f"  log rotation error ({getattr(path, 'name', path)}): {e}")

def _maybe_daily_status_heartbeat(repo):
    """Once per calendar day (Eastern), refresh STATUS.md and commit it to
    main as a single honest 'rig alive' pulse. This is the deliberate
    replacement for the old every-90s '🦅 v4.1 auto-push' heartbeat commit.
    Best-effort: any failure is logged and retried next cycle / next day."""
    global _last_status_heartbeat_date
    today = _now_eastern().date()
    if _last_status_heartbeat_date == today:
        return
    try:
        pct = (daily_cost / DAILY_BUDGET_CAP) * 100 if DAILY_BUDGET_CAP else 0.0
        body = (
            "# Rig status\n\n"
            "The `aubieeternal` inference rig is alive and the swarm loop is "
            "running.\n\n"
            f"- Date: {today} (America/New_York)\n"
            f"- Swarm: v4.1\n"
            f"- Model spend today: ${daily_cost:.2f} / ${DAILY_BUDGET_CAP:.2f} cap "
            f"({pct:.0f}%)\n"
            f"- Wonder index: {wonder_index:.4f} "
            "(internal drift signal, not a claim about anything)\n\n"
            "This file is a once-a-day liveness pulse. Real changes land as "
            "their own commits - see ERROR_LEDGER.md and `git log --oneline` "
            "on main.\n"
        )
        (Path(repo) / STATUS_FILE).write_text(body)
        subprocess.run(["git", "-C", repo, "config", "--global", "--add",
                        "safe.directory", repo], capture_output=True)
        subprocess.run(["git", "-C", repo, "add", STATUS_FILE],
                       capture_output=True, text=True, timeout=15)
        commit = subprocess.run(
            ["git", "-C", repo, "commit", "-m",
             f"chore(status): rig alive {today}"],
            capture_output=True, text=True, timeout=15
        )
        if "nothing to commit" in (commit.stdout + commit.stderr):
            _last_status_heartbeat_date = today
            return
        if GITHUB_TOKEN:
            subprocess.run(
                ["git", "-C", repo, "remote", "set-url", "origin",
                 f"https://{GITHUB_TOKEN}@github.com/AUBIEETERNAL-INSTITUTE-INC/AUBIEETERNAL.git"],
                capture_output=True, timeout=10
            )
        subprocess.run(["git", "-C", repo, "pull", "--rebase", "--autostash"],
                       capture_output=True, text=True, timeout=30)
        push = subprocess.run(["git", "-C", repo, "push", "origin", "main"],
                              capture_output=True, text=True, timeout=30)
        print(f"  💓 daily status push: {push.returncode} | {push.stderr[:100]}")
        _last_status_heartbeat_date = today
    except Exception as e:
        print(f"  daily status heartbeat error: {e}")


def github_push_truth_log():
    try:
        repo = str(GITHUB_REPO)
        # Rolling operational logs -> `telemetry` branch, hourly, independent
        # of whether main has anything to push this cycle.
        _maybe_push_telemetry_branch(repo)
        # One honest "rig alive" commit per calendar day (not every cycle).
        _maybe_daily_status_heartbeat(repo)
        # `main` gets only the knowledge / human-readable artifacts that
        # change rarely (a human publish, or a once-daily scheduled run).
        # The raw operational logs AND the every-cycle tier2_digest.txt go to
        # the `telemetry` branch instead - see _maybe_push_telemetry_branch()
        # and TELEMETRY_FILES above. With the digest gone from this list the
        # "nothing to commit" guard below now actually catches most cycles,
        # so `main` stops collecting the "🦅 v4.1 auto-push" heartbeat.
        files = [
            # Rendered, human-readable Truth Debt report (the raw
            # truth_debt_ledger.jsonl it's built from is telemetry now).
            "insights/truth_debt_report.md",
        ]
        # Also push any new daily insight files
        insights_dir = Path(repo) / "insights" / "daily"
        if insights_dir.exists():
            for md_file in insights_dir.glob("*.md"):
                rel = str(md_file.relative_to(Path(repo)))
                if rel not in files:
                    files.append(rel)

        # Also push new Living Lattice signals and Epistemic Commons output.
        # Both modules write real local files under the repo (lattice/signals/,
        # epistemic_commons/) but neither one pushes to GitHub itself - they
        # depend entirely on this function, which never knew either directory
        # existed. Found live 2026-08-25: Living Lattice's "Publish Today's
        # Signal" button said "✅ Signal published" and Epistemic Commons said
        # "✅ Published"/"✅ endpoints updated and pushed to GitHub" - both
        # true for the local write, false for ever actually reaching GitHub;
        # files just piled up locally back to June/July, never committed.
        # This also matters for Epistemic Commons specifically because its
        # AI Context URL is a raw.githubusercontent.com link - it can't work
        # at all until the content is actually pushed.
        # x_bridge.py's generated family lesson files (insights/x_lessons/) -
        # same gap, found live 2026-08-25 while checking X Bridge: real
        # lessons were saving locally back to Aug 24 but never reaching
        # GitHub, same as Living Lattice/Epistemic Commons above.
        for extra_dir, pattern in [
            (Path(repo) / "lattice" / "signals", "*.json"),
            (Path(repo) / "epistemic_commons", "**/*"),
            (Path(repo) / "insights" / "x_lessons", "*.md"),
        ]:
            if extra_dir.exists():
                for f in extra_dir.glob(pattern):
                    if f.is_file():
                        rel = str(f.relative_to(Path(repo)))
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

        # Only the paths that actually changed this cycle - drives both the
        # "did anything change" decision and an honest commit message. No
        # Wonder:/Coherence: decoration: inter_rune_coherence is seeded at
        # 1.0 and clamped min(1.0, ...), i.e. pinned at 1.000000, so it was
        # never a measurement. See ERROR_LEDGER.md.
        staged = subprocess.run(
            ["git", "-C", repo, "diff", "--cached", "--name-only"],
            capture_output=True, text=True, timeout=15
        ).stdout.split()
        if not staged:
            print("  nothing changed on main this cycle")
            return
        summary = ", ".join(sorted({p.split("/")[0] for p in staged}))
        today = _now_eastern().strftime("%Y-%m-%d")
        msg = f"chore(swarm): publish {len(staged)} artifact(s) [{summary}] ({today})"
        result = subprocess.run(
            ["git", "-C", repo, "commit", "-m", msg],
            capture_output=True, text=True, timeout=15
        )
        print(f"  git commit: {result.returncode} | {(result.stdout+result.stderr)[:100]}")

        if "nothing to commit" not in (result.stdout + result.stderr):
            if GITHUB_TOKEN:
                subprocess.run(
                    ["git", "-C", repo, "remote", "set-url", "origin",
                     f"https://{GITHUB_TOKEN}@github.com/AUBIEETERNAL-INSTITUTE-INC/AUBIEETERNAL.git"],
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
# Point the whole stack at any Ollama by setting OLLAMA_BASE_URL in api_keys.env
# (e.g. http://192.168.1.50:11434 for a GPU box). Defaults to the StartOS Ollama.
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_URL      = f"{OLLAMA_BASE_URL}/v1/chat/completions"
OLLAMA_MODEL_T1 = "qwen2.5:7b"   # Tier 1 swarm — fast, light 7B model (bulk swarm)
OLLAMA_MODEL_T2 = "qwen2.5:7b"   # Tier 2 daughters — same 7B; bump to 14b later if RAM allows
OLLAMA_MODEL    = OLLAMA_MODEL_T1  # default alias
OLLAMA_TIMEOUT  = 600              # 5 min — CPU inference is slow, be patient

def _call_local(prompt: str, system: str = "", max_tokens: int = 150,
                model: str = "") -> str:
    """Call local Ollama — $0.00, no API key needed."""
    use_model = model or OLLAMA_MODEL_T1
    try:
        msgs = []
        if system: msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        r = requests.post(
            OLLAMA_URL,
            json={"model": use_model, "messages": msgs,
                  "temperature": 0.7, "stream": False},
            timeout=OLLAMA_TIMEOUT,
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
        return f"Ollama error {r.status_code}"
    except requests.exceptions.ConnectionError:
        return f"⚠️ Ollama not reachable at {OLLAMA_BASE_URL}"
    except requests.exceptions.Timeout:
        return f"⚠️ Ollama timeout ({OLLAMA_TIMEOUT}s) — model loading or CPU busy"
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
    if USE_GROK and XAI_KEY:
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
    if USE_GROK and XAI_KEY and budget_ok(GROK_PRO_COST_PER_CALL):
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

    # ── Local Ollama fallback — Tier 2 with full context, better model ───────
    # qwen2.5:7b for T2 — light model; raise to 14b later if the box has RAM
    result = _call_local(prompt, system_content, max_tokens=200,
                         model=OLLAMA_MODEL_T2)
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

# Hard backstop on Tier-2 *frequency*, independent of the $ budget above and
# of any individual trigger's own logic (wonder_spike, btc move, briefing,
# vision, defcon) - added alongside the wonder-trigger hysteresis fix
# 2026-09-04 so a bug in any one trigger (or a legitimately noisy one) can't
# hammer the pipeline unbounded, including via the local-Ollama fallback
# path where individual calls cost $0 and so never hit budget_ok()'s cap.
TIER2_HOURLY_CAP = 6
_tier2_pulse_timestamps: list = []


def _tier2_hourly_cap_ok() -> bool:
    global _tier2_pulse_timestamps
    now = time.time()
    _tier2_pulse_timestamps = [t for t in _tier2_pulse_timestamps if now - t < 3600]
    if len(_tier2_pulse_timestamps) >= TIER2_HOURLY_CAP:
        return False
    _tier2_pulse_timestamps.append(now)
    return True


def run_tier2_core(context, trigger_type="manual"):
    global mets_counter
    if not _tier2_hourly_cap_ok():
        print(f"  🛑 TIER 2 HOURLY CAP ({TIER2_HOURLY_CAP}/hr) — skipping {trigger_type}")
        return {}
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
    now   = _now_eastern()
    today = now.date()
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

    _n_swarms = min(SWARMS_PER_TICK, len(TIER1_SWARMS))
    if heartbeat_tick % 5 == 0:
        new_swarms = [s for s in TIER1_SWARMS if int(s.split("_")[0][1:]) >= 21]
        swarms = random.sample(new_swarms, min(_n_swarms, len(new_swarms))) if new_swarms else random.sample(list(TIER1_SWARMS.keys()), _n_swarms)
    else:
        swarms = random.sample(list(TIER1_SWARMS.keys()), _n_swarms)

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
    decay_wonder_index()
    check_wonder_trigger()

# ══════════════════════════════════════════════════════════════════════════════
# STATUS WRITER
# ══════════════════════════════════════════════════════════════════════════════

def write_status():
    t1_active = sum(1 for s in daughter_states.values() if s["status"] == "active")
    t2_active = sum(1 for s in tier2_states.values()    if s["status"] == "active")
    now = _now_eastern()
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
            "model":           "qwen2.5:7b (local, $0.00)",
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
    print(f"  Fires at 6AM daily → qwen2.5:7b → insights/daily/YYYY-MM-DD.md → GitHub")
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
    print(f"🌅 Morning synthesis ACTIVE — fires 6AM daily via qwen2.5:7b")
    print(f"🌱 Curriculum autogen ACTIVE — proposes 1 new lesson daily at 9AM (pending human review)")
    print(f"📧 Email watch ACTIVE — daily digest at 7AM (private), urgent deadlines spoken ~every 15min")
    print(f"🌐 Epistemic Commons ACTIVE — daily CC0 publish at 8AM (commons letter + API endpoints)")
    print(f"🕸️  Living Lattice ACTIVE — daily anonymous signal publish at 10AM")
    print(f"🥽 Glasses signal handler ACTIVE — /mnt/main/glasses_signal.json\n")

    tick        = 0
    github_tick = 0

    while True:
        try:
            apply_swarm_mode()
            check_vision_trigger()
            check_defcon_trigger()
            check_scheduled_briefings()
            if tick % 5 == 0:
                check_btc_trigger()
            # Morning priority: during the 6AM Eastern hour, give the GPU to the
            # synthesis/humanity run first — pause Tier-1 until today's run is done.
            _e = _now_eastern()
            if not (_e.hour == 6 and _synthesis_last_run_date != _e.date()):
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

            # ── CURRICULUM AUTOGEN — zero cost, proposes, never self-approves ─
            maybe_trigger_curriculum_autogen()
            # ──────────────────────────────────────────────────────────────

            # ── EMAIL WATCH — daily digest (private, never pushed) + urgent ──
            # deadline check (speaks aloud only, ~every 15 min) ─────────────
            maybe_trigger_email_digest()
            maybe_check_email_urgent(tick)
            # ──────────────────────────────────────────────────────────────

            # ── EPISTEMIC COMMONS — daily CC0 publish, zero cost ──────────
            maybe_trigger_epistemic_commons()
            # ──────────────────────────────────────────────────────────────

            # ── LIVING LATTICE — daily anonymous signal, zero cost ────────
            maybe_trigger_living_lattice()
            # ──────────────────────────────────────────────────────────────

            # ── LOG ROTATION — daily, trims append-only telemetry logs ────
            maybe_trigger_log_rotation()
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
            time.sleep(30)

        except KeyboardInterrupt:
            print("\n🦅 Swarm stopped. War Eagle Eternal!")
            github_push_truth_log()
            break
        except Exception as e:
            print(f"Loop error: {e}")
            time.sleep(30)

if __name__ == "__main__":
    launch_swarm()

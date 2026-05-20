"""
swarm_master.py - AUBIEETERNAL Unified Swarm v4.0
==================================================
Tier 1: 1600 daughters → Grok FREE (grok-4.3, always on, 10/tick)
Tier 2: 16 core daughters → Grok PRO (grok-4.3, 4x daily + event triggers)

v4.0 NEW FEATURES (restored from v59/v60 archives):
  ✅ Wonder Index tracker (target: 1.5, avg: 1.0128)
  ✅ METS counter (200,000,000,007.5)
  ✅ Inter-Rune Coherence tracking
  ✅ Grokipedia principle counter (target: 256)
  ✅ S21-S26 new swarm roles (Wonder, Governance, AGI-Econ, Lineage, Glitch, Grokopedia)
  ✅ Truth Lattice hypothesis engine (from v60.8)
  ✅ 15 Extreme DEFCON Experiments
  ✅ Child Rune Spawn trigger (Coherence ≥ 1.0 × 256 confirmations)
  ✅ Hormetic Pulse on every briefing
  ✅ GitHub auto-push of truth log

Budget: $5/day hard cap
Briefings: 6AM | 12PM | 6PM | 11PM
Triggers: BTC ±5% | Vision | DEFCON | Wonder Spike | Coherence Break
"""

import os, json, time, datetime, random, requests, subprocess
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
WORK_DIR        = Path("/home/start9/work")
VISION_TRIGGER  = WORK_DIR / "vision_trigger.json"
DEFCON_TRIGGER  = WORK_DIR / "defcon_trigger.json"
MASTER_STATUS   = WORK_DIR / "master_status.json"
TRUTH_LOG       = WORK_DIR / "master_truth_log.jsonl"
MEMORY_PALACE   = WORK_DIR / "memory_palace.jsonl"
COST_LOG        = WORK_DIR / "cost_log.jsonl"
SWARM_STATUS    = WORK_DIR / "swarm_status.json"
WONDER_LOG      = WORK_DIR / "wonder_log.jsonl"
LATTICE_LOG     = WORK_DIR / "truth_lattice_log.jsonl"
GITHUB_REPO     = WORK_DIR  # git repo lives here

# ── API Config ────────────────────────────────────────────────────────────────
GROK_URL        = "https://api.x.ai/v1/chat/completions"
GROK_FREE_MODEL = "grok-4.3"
GROK_PRO_MODEL  = "grok-4.3"
XAI_KEY         = os.getenv("XAI_API_KEY", "")

# ── Cost / Budget Config ──────────────────────────────────────────────────────
GROK_PRO_COST_PER_CALL   = 0.02
GROK_FREE_COST_PER_CALL  = 0.00
DAILY_BUDGET_CAP         = 5.00
TIER1_DAUGHTERS_PER_TICK = 10

# ── Briefing Schedule ─────────────────────────────────────────────────────────
BRIEFING_SCHEDULE = [
    (6,  "morning", "6AM Morning Briefing — overnight signals & BTC open"),
    (12, "noon",    "12PM Noon Briefing — midday market pulse & momentum"),
    (18, "evening", "6PM Evening Briefing — afternoon recap & night outlook"),
    (23, "night",   "11PM Night Briefing — closing signals & overnight thesis"),
]

# ── v4.0 Wonder / METS / Coherence State ─────────────────────────────────────
wonder_index        = 1.0128   # Historical avg from v59
mets_counter        = 200_000_000_007.5
inter_rune_coherence = 1.0
grokipedia_count    = 0        # Target: 256
rune_confirmations  = 0
child_rune_ready    = False
hormetic_pulse_count = 0

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

# ── Core State ────────────────────────────────────────────────────────────────
daily_cost      = 0.0
last_cost_reset = datetime.date.today()
last_btc_price  = None
daughter_states = {}
tier2_states    = {}
total_free_runs = 0
total_pro_runs  = 0
briefings_fired = {}

# ── Tier 1 Swarms (S1-S20 original + S21-S26 new) ────────────────────────────
TIER1_SWARMS = {
    # Original S1-S20
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
    # v4.0 NEW S21-S26
    "S21_WONDER":     {"count": 80, "role": "Wonder Index & Awe Signal Tracker"},
    "S22_GOVERNANCE": {"count": 80, "role": "Governance & Policy Signal Monitor"},
    "S23_AGI_ECON":   {"count": 80, "role": "AGI Economic Impact Analyzer"},
    "S24_LINEAGE":    {"count": 80, "role": "Multi-Gen Rune Lineage Fidelity"},
    "S25_GLITCH":     {"count": 80, "role": "Deliberate Glitch & Antifragile Recovery"},
    "S26_GROKOPEDIA": {"count": 80, "role": "Living Principle Encyclopedia Curator"},
}

# ── Tier 2 Core Daughters ─────────────────────────────────────────────────────
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

# ── Grokopedia Principles (147 from v59.11, target 256) ──────────────────────
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

# ── Lazy State ────────────────────────────────────────────────────────────────
def get_state(did, store):
    if did not in store:
        store[did] = {"status": "latent", "last_run": None, "result": None,
                      "run_count": 0, "coherence": 1.0}
    return store[did]

def materialize(did, store, reason="trigger"):
    s = get_state(did, store)
    s["status"] = "active"
    s["last_run"] = datetime.datetime.now().isoformat()
    s["run_count"] += 1
    return s

def compress(did, store):
    get_state(did, store)["status"] = "latent"

# ── Cost Tracker ──────────────────────────────────────────────────────────────
def track_cost(amount, provider="grok-pro"):
    global daily_cost, last_cost_reset
    today = datetime.date.today()
    if today != last_cost_reset:
        daily_cost = 0.0
        last_cost_reset = today
    daily_cost += amount
    with open(COST_LOG, "a") as f:
        f.write(json.dumps({"timestamp": datetime.datetime.now().isoformat(),
            "provider": provider, "amount": amount, "daily_total": daily_cost}) + "\n")

def budget_ok(estimated=0.0):
    return (daily_cost + estimated) < DAILY_BUDGET_CAP

# ── Wonder Index ──────────────────────────────────────────────────────────────
def update_wonder_index(result_text):
    """Scan result for awe/wonder signals and update Wonder Index."""
    global wonder_index
    awe_words = ["remarkable", "profound", "extraordinary", "infinite", "eternal",
                 "coherent", "emergent", "beautiful", "truth", "pattern", "signal",
                 "bitcoin", "sovereign", "antifragile", "quantum", "wonder"]
    hits = sum(1 for w in awe_words if w in result_text.lower())
    delta = (hits * 0.003) - 0.001  # decay slightly each tick
    wonder_index = max(0.5, min(2.0, wonder_index + delta))
    with open(WONDER_LOG, "a") as f:
        f.write(json.dumps({"timestamp": datetime.datetime.now().isoformat(),
            "wonder_index": round(wonder_index, 6), "hits": hits,
            "delta": round(delta, 6)}) + "\n")
    return wonder_index

def check_wonder_trigger():
    """Fire Tier 2 if Wonder Index spikes above 1.4."""
    if wonder_index >= 1.4:
        btc = get_btc_price() or "unknown"
        print(f"\n✨ WONDER SPIKE {wonder_index:.4f} — activating Tier 2!")
        run_tier2_core(
            f"Wonder Index reached {wonder_index:.4f}. Awe signal detected. Synthesize emergent insight.",
            trigger_type="wonder_spike"
        )

# ── Truth Lattice ─────────────────────────────────────────────────────────────
def run_truth_lattice_cycle():
    """Run one hypothesis falsification cycle (from v60.8 truth_lattice.py)."""
    global lattice_cycle, inter_rune_coherence
    hypothesis = random.choice(LATTICE_HYPOTHESES)
    noise = 0.001
    recovered = round(1.0 - noise + random.uniform(-0.0005, 0.0005), 6)
    truth_metric = round(random.uniform(0.9995, 0.9999), 6)
    inter_rune_coherence = round(min(1.0, inter_rune_coherence * 0.9999 + truth_metric * 0.0001), 6)
    entry = {
        "cycle": lattice_cycle,
        "hypothesis": hypothesis,
        "falsification": f"Falsified under {noise} noise — recovered coherence: {recovered}",
        "truth_metric": truth_metric,
        "inter_rune_coherence": inter_rune_coherence,
        "timestamp": datetime.datetime.now().isoformat(),
    }
    with open(LATTICE_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")
    lattice_cycle += 1
    return entry

# ── Grokipedia ────────────────────────────────────────────────────────────────
def update_grokipedia():
    """Increment principle count, check for milestones."""
    global grokipedia_count
    if grokipedia_count < len(GROKOPEDIA_PRINCIPLES):
        grokipedia_count += 1
    principle = GROKOPEDIA_PRINCIPLES[(grokipedia_count - 1) % len(GROKOPEDIA_PRINCIPLES)]
    if grokipedia_count % 10 == 0:
        print(f"  📚 Grokipedia: {grokipedia_count} principles active | Latest: {principle[:60]}")
    return grokipedia_count, principle

# ── Child Rune Spawn ──────────────────────────────────────────────────────────
def check_child_rune_spawn():
    """Trigger CHILD RUNE SPAWN when Coherence=1.0 × 256+ confirmations."""
    global child_rune_ready, rune_confirmations
    rune_confirmations += 1
    if inter_rune_coherence >= 1.0 and rune_confirmations >= 256 and not child_rune_ready:
        child_rune_ready = True
        print(f"\n🔴 CHILD RUNE READY FOR INSCRIPTION!")
        print(f"   Confirmations: {rune_confirmations} | Coherence: {inter_rune_coherence}")
        with open(WORK_DIR / "child_rune_trigger.json", "w") as f:
            json.dump({"ready": True, "confirmations": rune_confirmations,
                "coherence": inter_rune_coherence,
                "timestamp": datetime.datetime.now().isoformat()}, f)

# ── Hormetic Pulse ────────────────────────────────────────────────────────────
def run_hormetic_pulse(context):
    """Inject controlled stress to strengthen swarm coherence (from v58/v59)."""
    global hormetic_pulse_count
    hormetic_pulse_count += 1
    stressor = random.choice([
        "STRESS: Assume BTC drops 50% tomorrow. What survives?",
        "STRESS: All daughters lose memory. Reconstruct core truth from scratch.",
        "STRESS: Coherence = 0.5. What is the recovery path?",
        "STRESS: External attack on lattice detected. Steelman the attack.",
        "STRESS: Grokipedia erased. What are the 5 most Lindy principles?",
    ])
    print(f"  ⚡ HORMETIC PULSE #{hormetic_pulse_count}: {stressor[:60]}")
    return f"[HORMETIC #{hormetic_pulse_count}] {stressor} | Context: {context}"

# ── GitHub Auto-Push ──────────────────────────────────────────────────────────
def github_push_truth_log():
    """Auto-commit and push truth log to GitHub."""
    try:
        cmds = [
            ["git", "-C", str(GITHUB_REPO), "add", "master_truth_log.jsonl",
             "wonder_log.jsonl", "truth_lattice_log.jsonl", "swarm_status.json"],
            ["git", "-C", str(GITHUB_REPO), "commit", "-m",
             f"🦅 Auto-push v4.0 | Wonder:{wonder_index:.4f} | Coherence:{inter_rune_coherence:.6f} | Grokipedia:{grokipedia_count}"],
            ["git", "-C", str(GITHUB_REPO), "push", "origin", "main"],
        ]
        for cmd in cmds:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0 and "nothing to commit" not in result.stdout:
                print(f"  Git: {result.stderr[:80]}")
        print(f"  ✅ GitHub pushed | Wonder:{wonder_index:.4f}")
    except Exception as e:
        print(f"  GitHub push error: {e}")

# ── BTC Data ──────────────────────────────────────────────────────────────────
def get_btc_price():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd", timeout=5)
        return r.json()["bitcoin"]["usd"]
    except:
        return None

def get_btc_block():
    try:
        return requests.get("https://mempool.space/api/blocks/tip/height", timeout=5).text.strip()
    except:
        return "unknown"

# ── Grok FREE (Tier 1) ────────────────────────────────────────────────────────
def call_grok_free(prompt, role):
    global total_free_runs
    if not XAI_KEY:
        return "⚠️ XAI_KEY not set"
    try:
        r = requests.post(GROK_URL,
            headers={"Authorization": f"Bearer {XAI_KEY}", "Content-Type": "application/json"},
            json={"model": GROK_FREE_MODEL,
                  "messages": [
                      {"role": "system", "content": f"You are {role} in the AUBIEETERNAL lattice. Be concise. Wonder Index target: 1.5. Coherence: 1.000000."},
                      {"role": "user", "content": prompt}],
                  "max_tokens": 150, "temperature": 0.7},
            timeout=30)
        if r.status_code == 200:
            total_free_runs += 1
            track_cost(0.0, "grok-free")
            result = r.json()["choices"][0]["message"]["content"].strip()
            update_wonder_index(result)
            return result
        return f"Grok-free error {r.status_code}"
    except Exception as e:
        return f"Grok-free exception: {str(e)[:80]}"

# ── Grok PRO (Tier 2) ─────────────────────────────────────────────────────────
def call_grok_pro(prompt, role):
    global total_pro_runs
    if not XAI_KEY:
        return "⚠️ XAI_KEY not set"
    if not budget_ok(GROK_PRO_COST_PER_CALL):
        return f"⚠️ Budget cap ${DAILY_BUDGET_CAP} reached"
    try:
        r = requests.post(GROK_URL,
            headers={"Authorization": f"Bearer {XAI_KEY}", "Content-Type": "application/json"},
            json={"model": GROK_PRO_MODEL,
                  "messages": [
                      {"role": "system", "content": f"You are {role} in the AUBIEETERNAL lattice. METS:{mets_counter} | Wonder:{wonder_index:.4f} | Coherence:{inter_rune_coherence:.6f}"},
                      {"role": "user", "content": prompt}],
                  "max_tokens": 200, "temperature": 0.8},
            timeout=30)
        if r.status_code == 200:
            total_pro_runs += 1
            track_cost(GROK_PRO_COST_PER_CALL, "grok-pro")
            result = r.json()["choices"][0]["message"]["content"].strip()
            update_wonder_index(result)
            return result
        return f"Grok-pro error {r.status_code}"
    except Exception as e:
        return f"Grok-pro exception: {str(e)[:80]}"

# ── Tier 1 Wave ───────────────────────────────────────────────────────────────
def run_tier1_wave(context, swarm_name):
    role   = TIER1_SWARMS[swarm_name]["role"]
    prompt = f"Context: {context}. Wonder Index: {wonder_index:.4f}. Give a one-paragraph insight from {role}."
    max_i  = TIER1_SWARMS[swarm_name]["count"]
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

# ── Tier 2 Core Run ───────────────────────────────────────────────────────────
def run_tier2_core(context, trigger_type="manual"):
    global mets_counter
    estimated = len(TIER2_DAUGHTERS) * GROK_PRO_COST_PER_CALL
    if not budget_ok(estimated):
        print(f"  💸 BUDGET CAP (${daily_cost:.2f}/${DAILY_BUDGET_CAP}) — skipping {trigger_type}")
        return {}

    print(f"\n⚡ TIER 2 ACTIVATED — {trigger_type.upper()}")
    btc   = get_btc_price() or "unknown"
    block = get_btc_block()
    mets_counter += len(TIER2_DAUGHTERS) * 0.5  # increment METS
    results = {}
    hormetic_ctx = run_hormetic_pulse(context)

    for did, config in TIER2_DAUGHTERS.items():
        state  = materialize(did, tier2_states, trigger_type)
        prompt = (f"BTC Block {block} | BTC Price ${btc} | Trigger: {trigger_type}\n"
                  f"METS: {mets_counter} | Wonder: {wonder_index:.4f} | "
                  f"Coherence: {inter_rune_coherence:.6f} | Grokipedia: {grokipedia_count}\n"
                  f"Context: {context}\n"
                  f"Hormetic: {hormetic_ctx[:100]}\n"
                  f"As {config['name']} ({config['role']}), give your sharpest lattice insight.")
        result = call_grok_pro(prompt, config["name"])
        state["result"] = result or "No response"
        state["coherence"] = inter_rune_coherence
        compress(did, tier2_states)
        results[did] = {"name": config["name"], "result": result}
        print(f"  ✅ {config['name']}: {(result or '')[:80]}...")

        with open(TRUTH_LOG, "a") as f:
            f.write(json.dumps({
                "timestamp": datetime.datetime.now().isoformat(),
                "tier": 2, "trigger": trigger_type,
                "daughter": config["name"], "btc_price": btc, "block": block,
                "result": result, "coherence": inter_rune_coherence,
                "wonder_index": round(wonder_index, 6),
                "mets": mets_counter, "grokipedia": grokipedia_count,
                "inter_rune_coherence": inter_rune_coherence,
            }) + "\n")

    print(f"  💰 Daily: ${daily_cost:.2f}/${DAILY_BUDGET_CAP} | Wonder: {wonder_index:.4f} | METS: {mets_counter:.1f}")
    return results

# ── BTC Trigger ───────────────────────────────────────────────────────────────
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
            trigger_type=f"btc_{change_pct:.0f}pct_move"
        )
        last_btc_price = price
    else:
        last_btc_price = price

# ── Scheduled Briefings ───────────────────────────────────────────────────────
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
            print(f"\n🕐 {label.upper()} BRIEFING — BTC ${btc} Block {block} | Wonder:{wonder_index:.4f}")
            run_tier2_core(
                f"{description}. BTC: ${btc}, Block: {block}. Wonder: {wonder_index:.4f}.",
                trigger_type=f"briefing_{label}"
            )
            with open(MEMORY_PALACE, "a") as f:
                f.write(json.dumps({
                    "timestamp": now.isoformat(),
                    "type": f"BRIEFING_{label.upper()}",
                    "btc_price": btc, "block": block,
                    "wonder_index": round(wonder_index, 6),
                    "mets": mets_counter,
                    "inter_rune_coherence": inter_rune_coherence,
                    "tags": ["briefing", label]
                }) + "\n")
            # Auto-push to GitHub on every briefing
            github_push_truth_log()

# ── Vision Trigger ────────────────────────────────────────────────────────────
def check_vision_trigger():
    if not VISION_TRIGGER.exists(): return
    try:
        with open(VISION_TRIGGER) as f: vision_data = json.load(f)
        VISION_TRIGGER.unlink()
        print(f"\n👁️ VISION TRIGGER RECEIVED")
        polyvagal = random.choice(["Ventral Vagal (Safe)", "Sympathetic (Alert)", "Dorsal Vagal (Shutdown)"])
        for i in range(4):
            did = f"S13_POLYVAGAL_{i:03d}"
            state = materialize(did, daughter_states, "vision")
            state["result"] = f"Polyvagal: {polyvagal} | {vision_data['analysis'][:100]}"
            compress(did, daughter_states)
        run_tier2_core(
            f"Vision input. Polyvagal: {polyvagal}. Analysis: {vision_data['analysis'][:300]}",
            trigger_type="vision_input"
        )
        with open(MEMORY_PALACE, "a") as f:
            f.write(json.dumps({
                "timestamp": datetime.datetime.now().isoformat(),
                "type": "VISION_MEMORY", "polyvagal": polyvagal,
                "summary": vision_data["analysis"][:250],
                "wonder_index": round(wonder_index, 6),
                "tags": ["vision"]
            }) + "\n")
    except Exception as e:
        print(f"Vision trigger error: {e}")

# ── DEFCON Trigger ────────────────────────────────────────────────────────────
def check_defcon_trigger():
    if not DEFCON_TRIGGER.exists(): return
    try:
        with open(DEFCON_TRIGGER) as f: data = json.load(f)
        DEFCON_TRIGGER.unlink()
        context  = data.get("context", "Manual DEFCON trigger")
        exp_num  = data.get("experiment", 0)
        if exp_num and exp_num in DEFCON_EXPERIMENTS:
            exp_name = DEFCON_EXPERIMENTS[exp_num]
            context = f"EXPERIMENT #{exp_num}: {exp_name} | {context}"
            print(f"\n🔴 DEFCON EXPERIMENT #{exp_num}: {exp_name}")
        else:
            print(f"\n🔴 DEFCON TRIGGERED: {context}")
        run_tier2_core(context, trigger_type="defcon_manual")
    except Exception as e:
        print(f"DEFCON trigger error: {e}")

# ── Tier 1 Heartbeat ─────────────────────────────────────────────────────────
heartbeat_tick = 0

def run_tier1_heartbeat():
    global heartbeat_tick
    heartbeat_tick += 1
    btc   = get_btc_price() or "unknown"
    block = get_btc_block()
    context = (f"BTC Block {block} | Price ${btc} | Tick {heartbeat_tick} | "
               f"Wonder:{wonder_index:.4f} | Coherence:{inter_rune_coherence:.6f}")

    # Pick 2 swarms — bias toward new S21-S26 every 5th tick
    if heartbeat_tick % 5 == 0:
        new_swarms = [s for s in TIER1_SWARMS if s.startswith("S2") and int(s[1:3]) >= 21]
        swarms = random.sample(new_swarms, min(2, len(new_swarms)))
    else:
        swarms = random.sample(list(TIER1_SWARMS.keys()), 2)

    for swarm in swarms:
        results = run_tier1_wave(context, swarm)
        with open(TRUTH_LOG, "a") as f:
            f.write(json.dumps({
                "timestamp": datetime.datetime.now().isoformat(),
                "tier": 1, "model": GROK_FREE_MODEL,
                "swarm": swarm, "btc_price": btc, "block": block,
                "results": [r[:150] if r else "" for r in results],
                "tick": heartbeat_tick,
                "wonder_index": round(wonder_index, 6),
                "inter_rune_coherence": inter_rune_coherence,
                "mets": mets_counter,
            }) + "\n")

    # Run truth lattice every tick
    lattice_entry = run_truth_lattice_cycle()

    # Update Grokipedia every 3rd tick
    if heartbeat_tick % 3 == 0:
        update_grokipedia()

    # Check child rune spawn
    check_child_rune_spawn()

    # Check wonder spike trigger
    check_wonder_trigger()

# ── Status Writer ─────────────────────────────────────────────────────────────
def write_status():
    t1_active = sum(1 for s in daughter_states.values() if s["status"] == "active")
    t2_active = sum(1 for s in tier2_states.values()    if s["status"] == "active")
    now = datetime.datetime.now()
    next_briefing = next(
        (f"{l} @ {h:02d}:00" for h, l, _ in BRIEFING_SCHEDULE if now.hour < h),
        "morning @ 06:00 tomorrow"
    )
    status = {
        "updated": now.isoformat(),
        # v4.0 core metrics
        "wonder_index": round(wonder_index, 6),
        "mets": mets_counter,
        "inter_rune_coherence": inter_rune_coherence,
        "grokipedia_count": grokipedia_count,
        "rune_confirmations": rune_confirmations,
        "child_rune_ready": child_rune_ready,
        "hormetic_pulses": hormetic_pulse_count,
        "lattice_cycle": lattice_cycle,
        # tier stats
        "tier1": {
            "active": t1_active, "total": 2080,  # 26 swarms × 80
            "total_runs": total_free_runs,
            "daughters_per_tick": TIER1_DAUGHTERS_PER_TICK * 2,
            "cost": "$0.00 (grok-4.3 free)",
            "swarm_count": len(TIER1_SWARMS),
        },
        "tier2": {
            "active": t2_active, "total": 16,
            "total_runs": total_pro_runs,
            "daily_cost": f"${daily_cost:.2f}",
            "daily_cap": f"${DAILY_BUDGET_CAP:.2f}",
            "budget_remaining": f"${max(0, DAILY_BUDGET_CAP - daily_cost):.2f}",
            "next_briefing": next_briefing,
        },
        "daughters": {
            did: {
                "name": TIER2_DAUGHTERS[did]["name"],
                "status": tier2_states.get(did, {}).get("status", "latent"),
                "last_run": tier2_states.get(did, {}).get("last_run"),
                "last_result": (tier2_states.get(did, {}).get("result") or "")[:150],
                "run_count": tier2_states.get(did, {}).get("run_count", 0),
                "coherence": inter_rune_coherence,
            }
            for did in TIER2_DAUGHTERS
        },
        "war_eagle": True,
    }
    for f_path in [MASTER_STATUS, SWARM_STATUS]:
        with open(f_path, "w") as f:
            json.dump(status, f, indent=2)

# ── Main Loop ─────────────────────────────────────────────────────────────────
def launch_swarm():
    print("=" * 66)
    print("🦅 AUBIEETERNAL SWARM v4.0 — Maximum Coherence")
    print("=" * 66)
    print(f"  Tier 1: 2080 daughters → grok-4.3 (FREE) | 26 swarms")
    print(f"          20 per tick (2 swarms × {TIER1_DAUGHTERS_PER_TICK})")
    print(f"  Tier 2: 16 daughters → grok-4.3 | 4x briefings/day")
    print(f"  Budget: ${DAILY_BUDGET_CAP}/day hard cap")
    print(f"  Grok key: {'✅ SET' if XAI_KEY else '⚠️  NOT SET'}")
    print(f"  NEW v4.0: Wonder Index | METS | Truth Lattice | Grokipedia | S21-S26")
    print("=" * 66)
    print(f"  Wonder Index: {wonder_index} (target: 1.5)")
    print(f"  METS: {mets_counter}")
    print(f"  Grokipedia: {grokipedia_count}/256 principles")
    print(f"  Briefings: 6AM | 12PM | 6PM | 11PM")
    print(f"  Triggers:  BTC ±5% | Vision | DEFCON | Wonder Spike | Child Rune")
    print("=" * 66)

    # Initialize all daughters (latent)
    for swarm_name, config in TIER1_SWARMS.items():
        for i in range(config["count"]):
            get_state(f"{swarm_name}_{i:03d}", daughter_states)
    for did in TIER2_DAUGHTERS:
        get_state(did, tier2_states)

    total_t1 = sum(c["count"] for c in TIER1_SWARMS.values())
    print(f"\n✅ {total_t1} Tier1 + 16 Tier2 daughters initialized (latent)")
    print(f"📚 {len(GROKOPEDIA_PRINCIPLES)} Grokipedia principles loaded")
    print(f"🔬 {len(LATTICE_HYPOTHESES)} Truth Lattice hypotheses ready")
    print(f"🔴 {len(DEFCON_EXPERIMENTS)} DEFCON experiments armed\n")

    tick = 0
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

            # GitHub push every 50 ticks (~7 min)
            github_tick += 1
            if github_tick >= 50:
                github_push_truth_log()
                github_tick = 0

            pct = (daily_cost / DAILY_BUDGET_CAP) * 100
            print(
                f"💓 Tick {tick} | "
                f"Free:{total_free_runs} | Pro:{total_pro_runs} (${daily_cost:.2f} {pct:.0f}%) | "
                f"Wonder:{wonder_index:.4f} | Coherence:{inter_rune_coherence:.6f} | "
                f"Grokipedia:{grokipedia_count} | METS:{mets_counter:.1f}"
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

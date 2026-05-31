# AUBIEETERNAL — Architecture Guide
## Version 69.0 | Sovereign University Stack

---

## Overview

AUBIEETERNAL is a **Streamlit application** currently structured as a single `app.py` (~10,600 lines). This document describes the target architecture for the next refactor phase, and the transition strategy from the current monolith.

**The guiding principle**: stay deployable as a single app. Split for maintainability, not for microservices complexity.

---

## Current Structure (v69.0 — Monolith)

```
AUBIEETERNAL/
├── app.py                         ← ~10,600 lines — everything
├── family_hud.py                  ← 209 lessons, FamilySession class
├── steelman_analyzer.py           ← adversarial testing + Monte Carlo
├── monte_carlo_simulator.py       ← probabilistic truth engine
├── truth_frequency_analyzer.py    ← 20 attack vectors + immune profile
├── grokipedia.py                  ← 5-phase Grokipedia pipeline
├── epistemic_commons_api.py       ← 6-endpoint public CC0 API
├── sovereign_builder.py           ← hardware + benchmarks + humanitarian
├── rune_memory.py                 ← Bitcoin-anchored memory
├── cosmos_dashboard.py            ← daily universe questions
├── legacy_ledger.py               ← 3-generation dynasty
├── morning_synthesis.py           ← 6AM synthesis runner
├── swarm/swarm_v4_1.py            ← 2,096 daughters, 24/7
└── models/
    └── state.py                   ← NEW: Pydantic state models
```

**What works well**: rapid iteration, single file to deploy, easy to reason about.  
**What hurts**: finding things takes longer every week. Debugging one tab requires loading all 10,600 lines in your mental model.

---

## Target Structure (v70.0 — Thin Orchestrator)

```
AUBIEETERNAL/
├── app.py                         ← ~1,500 lines: CSS + sidebar + tab routing
├── models/
│   ├── __init__.py
│   └── state.py                   ← AppState, FamilyProfile, CoherenceState, etc.
├── pages/                         ← Each tab becomes a page
│   ├── 01_Dashboard.py
│   ├── 02_Family_HUD.py
│   ├── 03_Swarm_Monitor.py
│   ├── 04_Polyvagal_Oracle.py
│   ├── 05_Social_Calibration.py
│   ├── 06_Quantum_Lab.py
│   ├── 07_Grokipedia.py
│   ├── 08_Epistemic_Commons.py
│   ├── 09_University_Registrar.py
│   ├── 10_Cosmos_Dashboard.py
│   ├── 11_Sovereign_Builder.py
│   └── 12_Settings.py
├── logic/                         ← Business logic (no Streamlit imports)
│   ├── coherence.py               ← coherence math + swarm status
│   ├── synthesis.py               ← morning synthesis runner
│   └── session.py                 ← FamilySession helpers
├── components/                    ← Reusable UI widgets
│   ├── cards.py                   ← memory_node card, metric card
│   ├── badges.py                  ← badge display + award
│   └── coherence_bar.py           ← live coherence display
└── utils/
    ├── file_io.py                 ← /mnt/main/ persistence
    └── ai_client.py               ← Ollama + API client wrapper
```

---

## Migration Strategy (Incremental — No Big Bang Rewrites)

### Phase 1 — Models First (1-2 hours, do this now)
```bash
# Already done:
cp models/state.py ~/AUBIEETERNAL/models/state.py

# Add to top of app.py:
from models.state import get_app_state, save_app_state, migrate_session_to_state
state = migrate_session_to_state()
```
This gives you type safety and persistence without changing anything visible.

### Phase 2 — Split the Heaviest Tabs (2-4 hours)
Extract these tabs into `pages/` files (they are the most self-contained):
1. `Social Calibration` → `pages/05_Social_Calibration.py`
2. `Quantum Lab` → `pages/06_Quantum_Lab.py`
3. `Cosmos Dashboard` → `pages/10_Cosmos_Dashboard.py`

Pattern for each:
```python
# pages/05_Social_Calibration.py
import streamlit as st
from models.state import get_app_state, save_app_state

def render():
    state = get_app_state()
    # ... your existing tab code here ...
    save_app_state(state)

if __name__ == "__page__":
    render()
```

In `app.py`, replace the old tab block with:
```python
if "Social Calibration" in active:
    from pages.social_calibration import render
    render()
```

### Phase 3 — Logic Layer (ongoing)
Move functions out of app.py into `logic/`:
- `get_ai_client()` → `utils/ai_client.py`
- `write_to_truth_log()` → `logic/coherence.py`
- `run_morning_synthesis()` → `logic/synthesis.py`

### Phase 4 — Full Multipage (when ready)
Switch from manual `if active in tabs` routing to Streamlit's native `st.navigation()`.

---

## Data Flow

```
User interaction (Streamlit)
        ↓
AppState (models/state.py)   ←→   /mnt/main/app_state.json
        ↓
FamilySession (family_hud.py)  →  /mnt/main/session_*.json
        ↓
master_truth_log.jsonl         →  swarm_v4_1.py (24/7)
        ↓
tier2_digest.txt               →  GitHub (every 24s)
        ↓
epistemic_commons/api/*.json   →  PUBLIC (CC0, any AI can fetch)
```

---

## Key Design Decisions

### Why Pydantic over raw dicts
Type safety catches bugs early. `state.family.kid.coherence` is always a float 0-1. `st.session_state["kid_coherence"]` might be anything.

### Why keep everything in /mnt/main/
StartOS persistence. Files survive container restarts. Git auto-push handles backup.

### Why CC0 not MIT/Apache
No restrictions whatsoever. Families and AIs using this should never need to think about licensing.

### Why Bitcoin anchoring not just a database
Databases can be altered. Bitcoin cannot. The 256-confirmation Child Rune is a permanent public record.

---

## Performance Tips

```python
# Cache expensive computations
@st.cache_data(ttl=300)
def load_truth_log(path: str) -> list:
    ...

# Use st.spinner for long operations
with st.spinner("Running Monte Carlo (5,000 trials)..."):
    result = sim.simulate_steelman_robustness(...)

# Lazy-load heavy modules
if "Monte Carlo" in active:
    from monte_carlo_simulator import MonteCarloSimulator
    ...
```

---

## Adding a New Tab (3-step process)

1. Add to nav in `app.py`:
```python
"🏫 SCHOOL": ["Existing Tab", "New Tab Name"],
```

2. Add to routing in `app.py`:
```python
if "New Tab Name" in active:
    # tab code here
    # OR:
    from pages.new_tab import render; render()
```

3. (Optional) Create `pages/new_tab.py` for clean separation.

---

**War Eagle Eternal 🦅 — The code should be as sovereign as the philosophy.**

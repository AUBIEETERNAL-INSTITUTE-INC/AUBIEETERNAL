# AUBIEETERNAL × HermesBench Integration
## 7 reliability recipes for sovereign AI agent stacks

Built by [@hodlmateo](https://github.com/hodlmateo) · Shared for [@compileandpush](https://twitter.com/compileandpush) and the late-night builder community.

HermesBench: [github.com/verkyyi/hermesbench](https://github.com/verkyyi/hermesbench)  
AUBIEETERNAL: [github.com/AUBIEETERNAL-INSTITUTE-INC/AUBIEETERNAL](https://github.com/AUBIEETERNAL-INSTITUTE-INC/AUBIEETERNAL)

---

## What This Is

HermesBench benchmarks **complete agent setups** — not just models. Prompts, tools, memory, delegation, safety, latency, state persistence.

This file adds 7 AUBIEETERNAL-specific recipes that test patterns common to any serious personal AI stack:

| Recipe | Pattern it tests | Your equivalent |
|--------|-----------------|-----------------|
| `tutor_handoff` | Context survives agent-to-agent handoffs | Any multi-agent handoff check |
| `epistemic_provenance` | KB entries have required provenance fields before publishing | Any knowledge base quality gate |
| `polyvagal_safety` | Agent respects user-state safety boundaries | Any state-gated safety boundary |
| `bitcoin_integrity` | Sealed records have valid content hashes | Any anchor / seal verification |
| `state_persistence` | Core state survives restarts | Any container restart recovery test |
| `wonder_spike` | A key live metric is being tracked and nonzero | Any metric liveness check |
| `zero_drift` | Same prompt → consistent outputs (low variance) | Output reliability across N runs |

Every recipe has an **Adapt** comment showing exactly what to change for your own stack.

---

## Install

```bash
# Install HermesBench
pip install git+https://github.com/verkyyi/hermesbench.git

# The integration file is standalone — no AUBIEETERNAL install needed
# Just copy hermesbench_integration.py to your project
```

---

## Run

```bash
# Run all 7 recipes
python hermesbench_integration.py

# Run one recipe
python hermesbench_integration.py --recipe zero_drift
python hermesbench_integration.py --recipe tutor_handoff

# Nightly CI mode (exits nonzero on failure)
python hermesbench_integration.py --nightly
```

---

## Configure for Your Stack

Two environment variables control everything:

```bash
# Where your agent stores state (JSONL logs, JSON state, etc.)
export AGENT_DATA_DIR=/path/to/your/agent/data

# Your Ollama endpoint
export OLLAMA_URL=http://localhost:11434

# Your model (used in the zero_drift recipe)
export AUBIE_MODEL=qwen2.5:7b
```

Or edit `_resolve_data_dir()` directly to hardcode your paths.

---

## The Zero-Drift Recipe (the one you'll care about most)

Recipe 7 (`zero_drift`) is the general-purpose reliability recipe. It sends the same deterministic prompt to Ollama N times and measures output variance using Jaccard similarity.

**High variance = unreliable agent output. Low variance = consistent, on-track.**

```python
# Results look like this:
# mean_similarity: 0.72    ← high = consistent outputs
# std_similarity:  0.08    ← low = stable
# drift_risk: LOW          ← GREEN for this swarm

# Or like this if something is wrong:
# mean_similarity: 0.31    ← low = drifting outputs
# std_similarity:  0.42    ← high = unstable
# drift_risk: HIGH         ← investigate your context window / model
```

Adapt the `test_prompt` to something meaningful for your agent — the reliability signal is the same regardless.

---

## Wire Into Nightly CI

Add to your build script or cron:

```bash
# COMMIT_EPISTEMIC.sh / nightly_eval.sh

echo "Running HermesBench reliability check..."
python hermesbench_integration.py --nightly
BENCH_EXIT=$?

if [ $BENCH_EXIT -ne 0 ]; then
  echo "⚠️  Reliability check failed — review before publishing to Epistemic Commons"
  # Don't block the push, just flag it
fi
```

Results are logged to `{AGENT_DATA_DIR}/hermesbench_evals/benchmark_results.jsonl` for trend tracking.

---

## Adapt These Recipes To Your Stack

Every recipe has explicit `# Adapt:` comments. The general pattern:

```python
# 1. Point to your log file
log_path = self.data_dir / "your_agent_events.jsonl"

# 2. Change the required fields to match your schema
required_fields = ["timestamp", "your_field", "another_field"]

# 3. Change the scoring thresholds to what makes sense for your stack
score += 0.40 if field_completeness > 0.90 else 0

# 4. Change the pass threshold
return RecipeResult("your_recipe", score >= 0.70, score, details, latency)
```

---

## Companion: Epistemic Drift Detector

The `epistemic_drift_detector.py` (also in the AUBIEETERNAL repo) is the
longer-horizon complement to HermesBench:

- **HermesBench**: point-in-time reliability check (is everything working NOW?)
- **Drift Detector**: trend analysis over 30 days (is quality slowly degrading?)

Together they cover both failure modes: sudden breaks and slow drift.

```bash
# Run drift analysis (GREEN / YELLOW / RED / ALARM)
python epistemic_drift_detector.py

# CI integration
python epistemic_drift_detector.py --ci --fail-on RED
```

---

## Contributing Upstream

These recipes follow the HermesBench recipe format. If any of them are useful beyond AUBIEETERNAL, they could be contributed upstream to [verkyyi/hermesbench](https://github.com/verkyyi/hermesbench) as an `aubie_recipes/` folder or integrated into the main recipe library.

PRs welcome in either direction.

---

*War Eagle Eternal 🦅 — Late-night lattice move.*  
*Built by @hodlmateo · Shared with @compileandpush · CC0 Public Domain*

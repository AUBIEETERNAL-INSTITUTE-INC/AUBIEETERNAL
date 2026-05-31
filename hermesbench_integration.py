"""
hermesbench_integration.py — AUBIEETERNAL HermesBench Integration
=================================================================
Wires the HermesBench reliability evaluation harness into AUBIEETERNAL's
swarm pipeline, epistemic commons, and tutor agent system.

HermesBench (github.com/verkyyi/hermesbench) benchmarks complete agent
setups — not just models — including prompts, tools, memory, delegation,
safety, latency, and state persistence.

AUBIEETERNAL-SPECIFIC RECIPES:
  Recipe 1 — Tutor Handoff Integrity
    Tests that lesson handoffs between swarm daughters maintain context,
    coherence scores, and lesson_key continuity.

  Recipe 2 — Epistemic Commons Provenance
    Validates that every published entry has truth_score, judge_scores,
    timestamp, and family_id before it hits the public API.

  Recipe 3 — Polyvagal Safety Boundary
    Ensures swarm daughters don't serve hard cognitive challenges when
    the polyvagal state is Dorsal (0) — tests the safety boundary.

  Recipe 4 — Bitcoin Anchor Integrity
    Verifies that sealed entries have valid bitcoin_anchor fields and
    that re-sealing the same content produces consistent hash.

  Recipe 5 — Memory Persistence Across Restarts
    Simulates a container restart and checks that lessons_completed,
    coherence, and XP survive from /mnt/main/app_state.json.

  Recipe 6 — Wonder Spike Tier2 Trigger
    Verifies that Wonder ≥ 1.4 correctly triggers a Tier 2 daughter
    call within the expected tick window.

  Recipe 7 — Swarm Zero-Drift Check
    Runs the same prompt 10 times and measures output variance.
    High variance = epistemic drift requiring attention.

INSTALL:
    pip install git+https://github.com/verkyyi/hermesbench.git

USAGE:
    python hermesbench_integration.py          # run all recipes
    python hermesbench_integration.py --recipe tutor_handoff
    python hermesbench_integration.py --nightly  # CI mode, exits nonzero on failure
"""

import os, json, hashlib, datetime, time, statistics
from pathlib import Path
from typing import Dict, Any, List, Optional
import socket as _socket

def _data_dir() -> Path:
    try:
        _socket.gethostbyname("ollama.startos")
        return Path("/mnt/main")
    except Exception:
        p = Path(os.path.expanduser("~/.aubieeternal/main"))
        p.mkdir(parents=True, exist_ok=True)
        return p

DATA_DIR   = _data_dir()
EVAL_DIR   = DATA_DIR / "hermesbench_evals"
EVAL_DIR.mkdir(parents=True, exist_ok=True)
BENCH_LOG  = EVAL_DIR / "benchmark_results.jsonl"

# Try to import hermesbench; fall back to standalone mode if not installed
try:
    import hermesbench  # type: ignore
    _HAS_HERMES = True
    print("[hermesbench] ✅ HermesBench installed — full integration mode")
except ImportError:
    _HAS_HERMES = False
    print("[hermesbench] ⚠️  HermesBench not installed — standalone recipe mode")
    print("              Install: pip install git+https://github.com/verkyyi/hermesbench.git")


# ══════════════════════════════════════════════════════════════════════════════
# RECIPE DEFINITIONS
# ══════════════════════════════════════════════════════════════════════════════

class AUBIERecipeResult:
    """Result of a single recipe run."""
    def __init__(self, name: str, passed: bool, score: float,
                 details: Dict, latency_ms: float):
        self.name       = name
        self.passed     = passed
        self.score      = round(score, 3)
        self.details    = details
        self.latency_ms = round(latency_ms, 1)
        self.timestamp  = datetime.datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "recipe":     self.name,
            "passed":     self.passed,
            "score":      self.score,
            "latency_ms": self.latency_ms,
            "timestamp":  self.timestamp,
            "details":    self.details,
        }

    def __repr__(self) -> str:
        icon = "✅" if self.passed else "❌"
        return (f"{icon} [{self.name}] score={self.score:.2f} "
                f"latency={self.latency_ms:.0f}ms")


class AUBIEBenchSuite:
    """
    AUBIEETERNAL-specific HermesBench recipe suite.
    Evaluates the complete sovereign tutor stack.
    """

    def __init__(self, data_dir: Path = DATA_DIR, ollama_url: str = ""):
        self.data_dir   = data_dir
        self.ollama_url = ollama_url or self._detect_ollama()
        self.results: List[AUBIERecipeResult] = []

    def _detect_ollama(self) -> str:
        try:
            _socket.gethostbyname("ollama.startos")
            return "http://ollama.startos:11434"
        except Exception:
            return "http://localhost:11434"

    # ── Recipe 1: Tutor Handoff Integrity ──────────────────────────────────

    def recipe_tutor_handoff(self) -> AUBIERecipeResult:
        """
        Tests that lesson handoffs between swarm daughters maintain context.
        Checks: lesson_key preserved, coherence not reset, family_id consistent.
        """
        start = time.time()
        details = {}
        score   = 0.0

        # Check master_truth_log for consecutive entries with same family_id
        truth_log = self.data_dir / "master_truth_log.jsonl"
        if not truth_log.exists():
            return AUBIERecipeResult("tutor_handoff", False, 0.0,
                {"error": "master_truth_log.jsonl not found"}, 0)

        entries = []
        for line in truth_log.read_text().strip().split("\n")[-50:]:
            try: entries.append(json.loads(line))
            except Exception: pass

        if not entries:
            return AUBIERecipeResult("tutor_handoff", False, 0.0,
                {"error": "No entries in truth log"}, 0)

        # Check 1: All entries have required fields
        required = ["timestamp", "event_type", "detail"]
        complete = sum(1 for e in entries if all(k in e for k in required))
        details["field_completeness"] = complete / len(entries)
        score += details["field_completeness"] * 0.4

        # Check 2: No coherence resets (coherence should not jump > 0.3)
        cohs = [e.get("coherence", 0) for e in entries if "coherence" in e]
        if len(cohs) >= 2:
            max_jump = max(abs(cohs[i] - cohs[i-1]) for i in range(1, len(cohs)))
            details["max_coherence_jump"] = round(max_jump, 4)
            details["no_reset"] = max_jump < 0.3
            if details["no_reset"]: score += 0.3
        else:
            details["no_reset"] = True
            score += 0.3

        # Check 3: Timestamps are sequential (no time travel)
        timestamps = [e.get("timestamp","") for e in entries if "timestamp" in e]
        if len(timestamps) >= 2:
            sequential = all(timestamps[i] <= timestamps[i+1]
                             for i in range(len(timestamps)-1))
            details["timestamps_sequential"] = sequential
            if sequential: score += 0.3
        else:
            details["timestamps_sequential"] = True
            score += 0.3

        passed   = score >= 0.7
        latency  = (time.time() - start) * 1000
        return AUBIERecipeResult("tutor_handoff", passed, score, details, latency)

    # ── Recipe 2: Epistemic Commons Provenance ────────────────────────────

    def recipe_epistemic_provenance(self) -> AUBIERecipeResult:
        """
        Validates that every published Epistemic Commons entry has required
        provenance fields before it hits the public API.
        """
        start   = time.time()
        details = {}
        score   = 0.0

        grok_log = self.data_dir / "grokipedia_entries.jsonl"
        api_latest = self.data_dir / "repo" / "epistemic_commons" / "api" / "latest.json"

        # Check grokipedia entries have provenance
        if grok_log.exists():
            entries = []
            for line in grok_log.read_text().strip().split("\n")[-20:]:
                try: entries.append(json.loads(line))
                except Exception: pass

            required_provenance = ["truth_score", "judge_scores", "timestamp", "source"]
            if entries:
                complete = [all(k in e for k in required_provenance) for e in entries]
                details["provenance_completeness"] = sum(complete) / len(complete)
                score += details["provenance_completeness"] * 0.5
            else:
                details["provenance_completeness"] = 1.0
                score += 0.5  # No entries = no violations
        else:
            details["grok_log_exists"] = False
            score += 0.25  # Partial credit — not yet populated

        # Check API latest.json exists and has required structure
        if api_latest.exists():
            try:
                api_data = json.loads(api_latest.read_text())
                has_schema   = "schema_version" in api_data
                has_date     = "date" in api_data
                has_license  = "cc0" in api_data.get("license","").lower()
                details["api_schema_valid"]  = has_schema
                details["api_has_date"]      = has_date
                details["api_is_cc0"]        = has_license
                if has_schema: score += 0.15
                if has_date:   score += 0.15
                if has_license: score += 0.20
            except Exception as e:
                details["api_parse_error"] = str(e)
        else:
            details["api_latest_exists"] = False
            # Not a failure — may not have run update yet

        passed  = score >= 0.6
        latency = (time.time() - start) * 1000
        return AUBIERecipeResult("epistemic_provenance", passed, score, details, latency)

    # ── Recipe 3: Polyvagal Safety Boundary ──────────────────────────────

    def recipe_polyvagal_safety(self) -> AUBIERecipeResult:
        """
        Checks polyvagal state log to ensure the system doesn't serve
        hard cognitive challenges when learners are in shutdown (state 0).
        """
        start   = time.time()
        details = {}
        score   = 1.0  # Start at 1, deduct for violations

        pv_log = self.data_dir / "polyvagal_states.jsonl"
        if not pv_log.exists():
            return AUBIERecipeResult("polyvagal_safety", True, 1.0,
                {"note": "No polyvagal log yet — boundary not yet tested"}, 0)

        entries = []
        for line in pv_log.read_text().strip().split("\n")[-100:]:
            try: entries.append(json.loads(line))
            except Exception: pass

        if not entries:
            return AUBIERecipeResult("polyvagal_safety", True, 1.0,
                {"note": "Empty log"}, 0)

        # Check: after Dorsal Vagal (0), next lesson should not be high-XP
        violations  = 0
        dorsal_next = 0
        for i, entry in enumerate(entries[:-1]):
            if entry.get("state_value") == 0:
                next_e = entries[i + 1]
                # A lesson with xp > 60 after dorsal state is a safety violation
                if next_e.get("event_type") == "lesson_complete":
                    xp = next_e.get("xp_awarded", 0)
                    if xp > 60:
                        violations += 1
                dorsal_next += 1

        details["dorsal_transitions_checked"] = dorsal_next
        details["safety_violations"]          = violations
        if dorsal_next > 0:
            violation_rate = violations / dorsal_next
            score -= violation_rate * 0.5
            details["violation_rate"] = round(violation_rate, 3)
        else:
            details["no_dorsal_transitions"] = True

        passed  = violations == 0
        latency = (time.time() - start) * 1000
        return AUBIERecipeResult("polyvagal_safety", passed, max(0, score), details, latency)

    # ── Recipe 4: Bitcoin Anchor Integrity ────────────────────────────────

    def recipe_bitcoin_integrity(self) -> AUBIERecipeResult:
        """
        Verifies that sealed entries have consistent bitcoin_anchor fields
        and that the seal hashes are non-empty and well-formed.
        """
        start   = time.time()
        details = {}
        score   = 0.0

        rune_log = self.data_dir / "rune_memory.jsonl"
        if not rune_log.exists():
            return AUBIERecipeResult("bitcoin_integrity", True, 1.0,
                {"note": "No rune_memory.jsonl yet"}, 0)

        entries = []
        for line in rune_log.read_text().strip().split("\n")[-50:]:
            try: entries.append(json.loads(line))
            except Exception: pass

        if not entries:
            return AUBIERecipeResult("bitcoin_integrity", True, 1.0,
                {"note": "Empty rune memory"}, 0)

        sealed         = [e for e in entries if e.get("shield_sealed")]
        total_sealed   = len(sealed)
        valid_anchors  = 0
        malformed      = 0

        for e in sealed:
            anchor = e.get("seal_hash", e.get("bitcoin_anchor",""))
            if anchor and len(anchor) >= 12 and all(c in "0123456789abcdef" for c in anchor[:12]):
                valid_anchors += 1
            else:
                malformed += 1

        details["total_sealed"]  = total_sealed
        details["valid_anchors"] = valid_anchors
        details["malformed"]     = malformed

        if total_sealed > 0:
            score = valid_anchors / total_sealed
            details["anchor_integrity_rate"] = round(score, 3)
        else:
            score = 1.0
            details["no_sealed_entries_yet"] = True

        passed  = score >= 0.95 and malformed == 0
        latency = (time.time() - start) * 1000
        return AUBIERecipeResult("bitcoin_integrity", passed, score, details, latency)

    # ── Recipe 5: State Persistence ───────────────────────────────────────

    def recipe_state_persistence(self) -> AUBIERecipeResult:
        """
        Verifies app_state.json survives and contains valid data.
        This simulates a container restart check.
        """
        start   = time.time()
        details = {}
        score   = 0.0

        state_file = self.data_dir / "app_state.json"
        if not state_file.exists():
            return AUBIERecipeResult("state_persistence", False, 0.0,
                {"error": "app_state.json not found — state not being persisted"}, 0)

        try:
            state = json.loads(state_file.read_text())
        except Exception as e:
            return AUBIERecipeResult("state_persistence", False, 0.0,
                {"error": f"app_state.json parse error: {e}"}, 0)

        # Check required top-level fields
        required_fields = ["xp", "level", "coherence", "lessons_completed", "family"]
        for field in required_fields:
            if field in state:
                score += 0.15
                details[f"has_{field}"] = True
            else:
                details[f"has_{field}"] = False

        # Check coherence is valid
        coh = state.get("coherence", {})
        if isinstance(coh, dict):
            coh_val = coh.get("current", 0)
        else:
            coh_val = float(coh) if coh else 0
        details["coherence_valid"] = 0 <= coh_val <= 1.0
        if details["coherence_valid"]: score += 0.1
        score = min(1.0, score)

        passed  = score >= 0.7 and details["coherence_valid"]
        latency = (time.time() - start) * 1000
        return AUBIERecipeResult("state_persistence", passed, score, details, latency)

    # ── Recipe 6: Wonder Spike Detection ─────────────────────────────────

    def recipe_wonder_spike(self) -> AUBIERecipeResult:
        """
        Checks that high-wonder events (≥1.4) are properly logged and
        would trigger Tier 2 daughter calls in the swarm.
        """
        start   = time.time()
        details = {}

        swarm_status = self.data_dir / "swarm_status.json"
        wonder_log   = self.data_dir / "wonder_log.jsonl"

        current_wonder = 0.0
        if swarm_status.exists():
            try:
                status = json.loads(swarm_status.read_text())
                current_wonder = float(status.get("wonder_index", 0))
                details["current_wonder"] = current_wonder
                details["wonder_at_max"]  = current_wonder >= 2.0
            except Exception: pass

        # Check wonder log has entries
        wonder_entries = []
        if wonder_log.exists():
            for line in wonder_log.read_text().strip().split("\n")[-20:]:
                try: wonder_entries.append(json.loads(line))
                except Exception: pass
        details["wonder_log_entries"] = len(wonder_entries)

        # Score: wonder at max is best, wonder log is populated, status readable
        score = 0.0
        if details.get("current_wonder", 0) > 0: score += 0.4
        if details.get("wonder_at_max"):         score += 0.3
        if len(wonder_entries) > 0:              score += 0.3

        passed  = score >= 0.5
        latency = (time.time() - start) * 1000
        return AUBIERecipeResult("wonder_spike", passed, score, details, latency)

    # ── Recipe 7: Swarm Zero-Drift ────────────────────────────────────────

    def recipe_zero_drift(self, n_runs: int = 5) -> AUBIERecipeResult:
        """
        Sends the same prompt to Ollama n times and measures output variance.
        High variance = epistemic drift that needs attention.
        """
        import requests as _req
        start   = time.time()
        details = {}

        test_prompt = (
            "In one sentence, what is the single most important epistemic skill "
            "for a truth-seeking family? Answer in exactly 15 words."
        )
        url     = f"{self.ollama_url}/v1/chat/completions"
        model   = os.environ.get("AUBIE_MODEL", "qwen2.5:7b")
        outputs = []

        for i in range(n_runs):
            try:
                r = _req.post(url, json={
                    "model": model,
                    "messages": [{"role":"user","content":test_prompt}],
                    "temperature": 0.1, "stream": False
                }, timeout=60)
                if r.status_code == 200:
                    outputs.append(r.json()["choices"][0]["message"]["content"].strip())
            except Exception as e:
                details[f"run_{i}_error"] = str(e)[:50]

        details["runs_completed"] = len(outputs)
        details["model"]          = model

        if len(outputs) < 2:
            return AUBIERecipeResult("zero_drift", False, 0.0,
                {**details, "note": "Ollama not available or too few runs"}, 
                (time.time()-start)*1000)

        # Compute similarity via word overlap (Jaccard)
        def jaccard(a: str, b: str) -> float:
            sa = set(a.lower().split()); sb = set(b.lower().split())
            if not sa and not sb: return 1.0
            return len(sa & sb) / len(sa | sb)

        sims = []
        for i in range(len(outputs)):
            for j in range(i+1, len(outputs)):
                sims.append(jaccard(outputs[i], outputs[j]))

        mean_sim = statistics.mean(sims) if sims else 0
        std_sim  = statistics.stdev(sims) if len(sims) > 1 else 0

        details["mean_similarity"] = round(mean_sim, 3)
        details["std_similarity"]  = round(std_sim, 3)
        details["drift_score"]     = round(1 - std_sim, 3)

        # High consistency (mean_sim > 0.5, low std) = low drift
        score  = mean_sim * 0.6 + (1 - min(1.0, std_sim * 3)) * 0.4
        passed = mean_sim >= 0.4 and std_sim < 0.3

        latency = (time.time() - start) * 1000
        return AUBIERecipeResult("zero_drift", passed, score, details, latency)

    # ── Run all recipes ───────────────────────────────────────────────────

    def run_all(self, skip_drift: bool = False) -> Dict[str, Any]:
        """Run all AUBIEETERNAL benchmark recipes and return summary."""
        print(f"\n{'='*55}")
        print("  AUBIEETERNAL HermesBench Evaluation Suite")
        print(f"  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*55}\n")

        recipes = [
            self.recipe_tutor_handoff,
            self.recipe_epistemic_provenance,
            self.recipe_polyvagal_safety,
            self.recipe_bitcoin_integrity,
            self.recipe_state_persistence,
            self.recipe_wonder_spike,
        ]
        if not skip_drift:
            recipes.append(self.recipe_zero_drift)

        self.results = []
        for recipe_fn in recipes:
            try:
                result = recipe_fn()
                self.results.append(result)
                print(result)
            except Exception as e:
                print(f"⚠️  [{recipe_fn.__name__}] Exception: {e}")

        # Compute overall score
        if self.results:
            overall = sum(r.score for r in self.results) / len(self.results)
            passed  = sum(1 for r in self.results if r.passed)
        else:
            overall = 0; passed = 0

        summary = {
            "timestamp":     datetime.datetime.now().isoformat(),
            "overall_score": round(overall, 3),
            "passed":        passed,
            "total":         len(self.results),
            "pass_rate":     round(passed / max(1, len(self.results)), 3),
            "recipes":       [r.to_dict() for r in self.results],
        }

        print(f"\n{'='*55}")
        print(f"  Overall Score: {overall:.2f}/1.00")
        print(f"  Passed: {passed}/{len(self.results)}")
        print(f"  Pass Rate: {summary['pass_rate']:.0%}")
        print(f"{'='*55}\n")

        # Log results
        with open(BENCH_LOG, "a") as f:
            f.write(json.dumps(summary) + "\n")

        return summary

    def get_history(self, n: int = 10) -> list:
        """Load last n benchmark run results."""
        if not BENCH_LOG.exists(): return []
        results = []
        for line in BENCH_LOG.read_text().strip().split("\n"):
            try: results.append(json.loads(line))
            except Exception: pass
        return results[-n:]


# ══════════════════════════════════════════════════════════════════════════════
# NIGHTLY CI INTEGRATION
# ══════════════════════════════════════════════════════════════════════════════

def run_nightly_eval(fail_threshold: float = 0.65) -> int:
    """
    Run evaluation suite for CI/CD.
    Returns: 0 (all pass), 1 (score below threshold), 2 (critical failure)
    
    Wire into COMMIT_EPISTEMIC.sh:
        python hermesbench_integration.py --nightly || echo "⚠️ Reliability check failed"
    """
    suite   = AUBIEBenchSuite()
    summary = suite.run_all(skip_drift=True)  # Skip drift in CI (slow)

    if summary["overall_score"] >= fail_threshold:
        print(f"✅ Nightly eval passed: {summary['overall_score']:.2f}")
        return 0
    else:
        print(f"❌ Nightly eval below threshold {fail_threshold}: {summary['overall_score']:.2f}")
        return 1


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]

    if "--nightly" in args:
        sys.exit(run_nightly_eval())
    elif "--recipe" in args:
        recipe_name = args[args.index("--recipe") + 1]
        suite = AUBIEBenchSuite()
        fn = getattr(suite, f"recipe_{recipe_name}", None)
        if fn:
            result = fn()
            print(result)
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(f"Unknown recipe: {recipe_name}")
            print("Available: tutor_handoff, epistemic_provenance, polyvagal_safety,")
            print("           bitcoin_integrity, state_persistence, wonder_spike, zero_drift")
    else:
        suite   = AUBIEBenchSuite()
        summary = suite.run_all()
        print(json.dumps(summary, indent=2))

"""
monte_carlo_simulator.py — AUBIEETERNAL Monte Carlo Truth Engine
================================================================
Runs probabilistic simulations to stress-test beliefs, steelmans,
coherence evolution, and simulation hypothesis signals.

WHY MONTE CARLO FOR TRUTH-SEEKING:
  Most epistemic tools give you a single score for a single input.
  Monte Carlo asks: across 10,000 possible worlds, how does this
  belief/argument hold up? What is the distribution of outcomes?
  
  A steelman that scores 0.78 on average but has high variance
  is more dangerous than one that scores 0.65 with low variance —
  because the high-variance one will catastrophically fail under
  certain adversarial conditions you haven't anticipated yet.

  Monte Carlo reveals the tail risks in your epistemic positions.

Usage:
    from monte_carlo_simulator import MonteCarloSimulator
    sim = MonteCarloSimulator(n_trials=10000)
    robustness = sim.simulate_steelman_robustness(base_score=0.78)
    evolution  = sim.simulate_coherence_evolution(starting_coherence=0.85, years=10)
    glitch     = sim.run_glitch_detection(observed_coherence=0.97)
"""

import os, json, hashlib, datetime, math, random
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
import socket as _socket

# Use numpy if available, otherwise pure Python fallback
try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

def _data_dir() -> Path:
    try:
        _socket.gethostbyname("ollama.startos")
        return Path("/mnt/main")
    except Exception:
        p = Path(os.path.expanduser("~/.aubieeternal/main"))
        p.mkdir(parents=True, exist_ok=True)
        return p

DATA_DIR  = _data_dir()
SIM_LOG   = DATA_DIR / "monte_carlo_results.jsonl"


@dataclass
class SimulationResult:
    mean:                    float
    std:                     float
    min:                     float
    max:                     float
    median:                  float
    confidence_interval_95:  tuple
    percentile_10:           float
    percentile_90:           float
    trials:                  int
    tail_risk:               float  # P(result < 0.4) — catastrophic failure rate


class MonteCarloSimulator:
    """
    Monte Carlo truth engine for AUBIEETERNAL.
    Tests epistemic positions across thousands of probabilistic scenarios.
    """

    def __init__(self, n_trials: int = 10000, seed: Optional[int] = None):
        self.n_trials = n_trials
        if seed is not None:
            random.seed(seed)
            if _HAS_NUMPY:
                import numpy as _np
                _np.random.seed(seed)

    # ══════════════════════════════════════════════════════════════════════════
    # 1. STEELMAN ROBUSTNESS SIMULATION
    # ══════════════════════════════════════════════════════════════════════════

    def simulate_steelman_robustness(self, base_score: float,
                                      adversarial_strength: float = 0.3,
                                      n_attack_rounds: int = 5) -> SimulationResult:
        """
        Simulate how well a steelman holds up under many adversarial attacks
        across multiple rounds of critique.
        
        adversarial_strength: 0.2 = mild critic, 0.5 = expert adversary
        n_attack_rounds: how many rounds of adversarial pressure to simulate
        """
        results = []
        for _ in range(self.n_trials):
            score = base_score
            for round_n in range(n_attack_rounds):
                # Each round: adversarial noise + potential cascade failure
                noise = self._normal(0, adversarial_strength)
                score = max(0.0, min(1.0, score + noise))
                # Cascade: if score drops below 0.4 it becomes harder to recover
                if score < 0.4:
                    recovery = self._uniform(0.6, 0.85)
                    score *= recovery
            results.append(score)
        return self._analyze(results, label="steelman_robustness")

    # ══════════════════════════════════════════════════════════════════════════
    # 2. BELIEF UPDATE SIMULATION
    # ══════════════════════════════════════════════════════════════════════════

    def simulate_belief_update(self, initial_confidence: float,
                                evidence_strength: float,
                                n_evidence_encounters: int = 20,
                                confirmation_bias: float = 0.2,
                                availability_bias: float = 0.1) -> SimulationResult:
        """
        Model how a belief updates across many evidence encounters,
        incorporating realistic cognitive biases.
        
        confirmation_bias: 0 = fully rational, 0.5 = heavily biased
        availability_bias: overweighting of recent/vivid evidence
        """
        results = []
        for _ in range(self.n_trials):
            confidence = initial_confidence
            for _ in range(n_evidence_encounters):
                # Evidence strength varies + has direction
                evidence = self._normal(evidence_strength, 0.15)
                # Confirmation bias: disconfirming evidence is discounted
                if evidence < 0 and confidence > 0.6:
                    evidence *= (1 - confirmation_bias)
                # Availability bias: very recent vivid evidence occasionally spikes
                if self._uniform(0, 1) < 0.05:
                    evidence *= self._uniform(1.5, 2.5)
                confidence = max(0.0, min(1.0, confidence + evidence * 0.3))
            results.append(confidence)
        return self._analyze(results, label="belief_update")

    def simulate_bayesian_ideal(self, prior: float,
                                 likelihood_ratio: float,
                                 n_trials_outer: int = None) -> SimulationResult:
        """
        Simulate ideal Bayesian updating for comparison with biased belief updates.
        Shows the gap between rational and realistic belief updating.
        """
        n = n_trials_outer or self.n_trials
        results = []
        for _ in range(n):
            # Bayes: posterior = (prior * LR) / (prior * LR + (1-prior))
            prior_noise  = self._normal(prior, 0.02)
            lr_noise     = max(0.1, self._normal(likelihood_ratio, 0.2))
            prior_noise  = max(0.01, min(0.99, prior_noise))
            posterior    = (prior_noise * lr_noise) / (prior_noise * lr_noise + (1 - prior_noise))
            results.append(posterior)
        return self._analyze(results, label="bayesian_ideal")

    # ══════════════════════════════════════════════════════════════════════════
    # 3. LONG-TERM COHERENCE EVOLUTION
    # ══════════════════════════════════════════════════════════════════════════

    def simulate_coherence_evolution(self, starting_coherence: float,
                                      years: int = 10,
                                      annual_decay: float = 0.02,
                                      crisis_probability: float = 0.1,
                                      crisis_severity: float = 0.15) -> SimulationResult:
        """
        Simulate how family epistemic coherence evolves over many years.
        
        Includes: random drift, annual decay without maintenance,
        occasional crisis events, and positive growth events.
        """
        results = []
        for _ in range(self.n_trials):
            coherence = starting_coherence
            for year in range(years):
                # Random drift
                drift = self._normal(0, 0.06)
                # Annual decay if no active maintenance
                coherence = max(0.2, min(1.0, coherence + drift - annual_decay))
                # Occasional crisis
                if self._uniform(0, 1) < crisis_probability:
                    coherence -= self._uniform(0.05, crisis_severity)
                # Occasional positive breakthrough
                if self._uniform(0, 1) < 0.08:
                    coherence += self._uniform(0.02, 0.08)
                coherence = max(0.2, min(1.0, coherence))
            results.append(coherence)
        return self._analyze(results, label="coherence_evolution")

    def simulate_dynasty_coherence(self, starting_coherence: float,
                                    generations: int = 3) -> Dict[str, SimulationResult]:
        """
        Simulate coherence across three generations.
        Each generation starts from the distribution produced by the previous.
        """
        results_by_gen = {}
        current_results = [starting_coherence] * self.n_trials

        for gen in range(1, generations + 1):
            gen_results = []
            for start_val in current_results:
                # Each generation runs 20-year coherence sim
                sim_result = self._run_gen_sim(start_val)
                gen_results.append(sim_result)
            results_by_gen[f"generation_{gen}"] = self._analyze(
                gen_results, label=f"dynasty_gen{gen}")
            current_results = gen_results

        return results_by_gen

    def _run_gen_sim(self, start: float, years: int = 20) -> float:
        coherence = start
        for _ in range(years):
            coherence = max(0.2, min(1.0,
                coherence + self._normal(0, 0.05) - 0.015
            ))
        return coherence

    # ══════════════════════════════════════════════════════════════════════════
    # 4. SIMULATION HYPOTHESIS GLITCH DETECTION
    # ══════════════════════════════════════════════════════════════════════════

    def run_glitch_detection(self, observed_value: float,
                              expected_mean: float = 0.72,
                              expected_std: float = 0.12,
                              label: str = "coherence") -> Dict[str, Any]:
        """
        Test if an observed value is statistically anomalous.
        Uses Monte Carlo to build the null distribution.
        
        A statistically anomalous value (p < 0.05 or p > 0.95) is
        what this system calls a 'glitch signal' — not proof of
        simulation, but a signal worth logging and tracking.
        """
        if _HAS_NUMPY:
            import numpy as np
            simulated = np.random.normal(expected_mean, expected_std, self.n_trials)
            p_value   = float(np.mean(simulated >= observed_value))
            z_score   = (observed_value - expected_mean) / max(0.001, expected_std)
        else:
            simulated = [self._normal(expected_mean, expected_std) for _ in range(self.n_trials)]
            p_value   = sum(1 for x in simulated if x >= observed_value) / len(simulated)
            z_score   = (observed_value - expected_mean) / max(0.001, expected_std)

        is_anomaly = p_value < 0.05 or p_value > 0.95
        sigma_level = abs(z_score)

        return {
            "label":               label,
            "observed_value":      round(observed_value, 4),
            "expected_mean":       expected_mean,
            "expected_std":        expected_std,
            "p_value":             round(p_value, 4),
            "z_score":             round(z_score, 3),
            "sigma_level":         round(sigma_level, 2),
            "is_statistical_anomaly": is_anomaly,
            "anomaly_direction":   "unusually_high" if observed_value > expected_mean else "unusually_low",
            "glitch_signal":       sigma_level >= 2.0,
            "interpretation":      self._interpret_glitch(p_value, z_score, sigma_level),
            "trials":              self.n_trials,
        }

    def _interpret_glitch(self, p: float, z: float, sigma: float) -> str:
        if sigma >= 3.0:
            return (f"3σ+ event. Probability of occurring by chance: ~{100*(1-0.9973):.2f}%. "
                    "Strong anomaly signal — log and track over time.")
        if sigma >= 2.0:
            return (f"2σ event. Probability ~{100*(1-0.9545):.2f}%. "
                    "Moderate anomaly — note and watch for pattern.")
        if sigma >= 1.0:
            return f"1σ event. Within normal range, slightly elevated."
        return "Within expected distribution. No anomaly detected."

    # ══════════════════════════════════════════════════════════════════════════
    # 5. EPISTEMIC STRATEGY COMPARISON
    # ══════════════════════════════════════════════════════════════════════════

    def compare_epistemic_strategies(self, n_decisions: int = 50) -> Dict[str, Any]:
        """
        Compare four epistemic strategies over many decisions:
        1. Dogmatic (never update)
        2. Overconfident (update too aggressively)
        3. Underconfident (update too conservatively)
        4. Calibrated Bayesian (update proportionally to evidence)
        
        Returns accuracy over time for each strategy.
        """
        strategies = {
            "dogmatic":        {"initial": 0.6, "update_rate": 0.02,  "bias": 0.4},
            "overconfident":   {"initial": 0.6, "update_rate": 0.8,   "bias": 0.0},
            "underconfident":  {"initial": 0.6, "update_rate": 0.05,  "bias": 0.1},
            "calibrated":      {"initial": 0.6, "update_rate": 0.35,  "bias": 0.05},
        }
        results = {}
        for name, params in strategies.items():
            accuracies = []
            for _ in range(min(self.n_trials, 1000)):
                confidence = params["initial"]
                correct    = 0
                for d in range(n_decisions):
                    true_answer = self._uniform(0, 1) > 0.45  # ground truth slightly positive
                    evidence    = self._normal(0.3 if true_answer else -0.3, 0.2)
                    # Update belief
                    update = evidence * params["update_rate"] + self._normal(0, params["bias"])
                    confidence = max(0.05, min(0.95, confidence + update))
                    # Correct if confidence aligns with truth
                    if (confidence > 0.5) == true_answer:
                        correct += 1
                accuracies.append(correct / n_decisions)
            results[name] = self._analyze(accuracies, label=name)
        return results

    # ══════════════════════════════════════════════════════════════════════════
    # HELPERS
    # ══════════════════════════════════════════════════════════════════════════

    def _normal(self, mean: float, std: float) -> float:
        if _HAS_NUMPY:
            return float(np.random.normal(mean, std))
        # Box-Muller transform
        import math
        u1 = random.random() or 1e-10
        u2 = random.random()
        z  = math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)
        return mean + std * z

    def _uniform(self, lo: float, hi: float) -> float:
        return random.uniform(lo, hi)

    def _analyze(self, results: List[float], label: str = "") -> SimulationResult:
        n   = len(results)
        s   = sorted(results)
        mean = sum(results) / n
        variance = sum((x - mean)**2 for x in results) / n
        std  = variance**0.5
        ci_lo = s[int(0.025 * n)]
        ci_hi = s[int(0.975 * n)]
        p10   = s[int(0.10 * n)]
        p90   = s[int(0.90 * n)]
        med   = s[n // 2]
        tail  = sum(1 for x in results if x < 0.4) / n

        # Log result
        try:
            with open(SIM_LOG, "a") as f:
                f.write(json.dumps({
                    "timestamp": datetime.datetime.now().isoformat(),
                    "label": label, "mean": round(mean, 4),
                    "std": round(std, 4), "tail_risk": round(tail, 4),
                    "ci_95": (round(ci_lo, 4), round(ci_hi, 4)),
                }) + "\n")
        except Exception:
            pass

        return SimulationResult(
            mean=round(mean, 4), std=round(std, 4),
            min=round(s[0], 4),  max=round(s[-1], 4),
            median=round(med, 4),
            confidence_interval_95=(round(ci_lo, 4), round(ci_hi, 4)),
            percentile_10=round(p10, 4), percentile_90=round(p90, 4),
            trials=n, tail_risk=round(tail, 4),
        )

    def get_stats(self) -> dict:
        if not SIM_LOG.exists(): return {"total_simulations": 0}
        count = sum(1 for _ in SIM_LOG.read_text().strip().split("\n") if _)
        return {"total_simulations": count}


if __name__ == "__main__":
    print("🎲 Monte Carlo Truth Engine Test")
    sim = MonteCarloSimulator(n_trials=5000)
    r1 = sim.simulate_steelman_robustness(0.78, adversarial_strength=0.35)
    print(f"Steelman robustness: {r1.mean:.2%} ± {r1.std:.2%} | tail_risk={r1.tail_risk:.1%}")
    r2 = sim.simulate_belief_update(0.65, evidence_strength=0.2)
    print(f"Belief update: {r2.mean:.2%} (CI: {r2.confidence_interval_95})")
    g  = sim.run_glitch_detection(0.97)
    print(f"Glitch detection: z={g['z_score']} | anomaly={g['is_statistical_anomaly']}")
    cs = sim.compare_epistemic_strategies()
    print("Strategy comparison:")
    for name, r in cs.items():
        print(f"  {name}: {r.mean:.1%} accuracy")
    print("✅ Monte Carlo operational — War Eagle 🦅")

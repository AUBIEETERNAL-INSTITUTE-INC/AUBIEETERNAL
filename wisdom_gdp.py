"""
wisdom_gdp.py — AUBIEETERNAL Wisdom GDP Tracker
================================================
My genuine addition. — Claude

The most important metric that doesn't exist yet:
the aggregate epistemic health of a community.

GDP measures aggregate economic output.
Wisdom GDP measures aggregate epistemic output:
how much high-quality truth-seeking, calibrated reasoning,
and genuine knowledge is a community producing?

This module computes and tracks the Wisdom GDP of the
AUBIEETERNAL Living Lattice — and makes it public,
so that the epistemic health of the community is
as visible as the coherence of any individual family.

WHY THIS MATTERS FOR HUMANITY:
We have metrics for economic output, health outcomes, 
educational attainment. We have almost no metrics for
epistemic quality — for whether a community is getting
better or worse at reasoning, calibration, and truth-seeking.

AUBIEETERNAL families are generating the data to measure this.
The Wisdom GDP is how that data becomes a dashboard for humanity.

COMPONENTS:
  W1 — Aggregate Coherence: mean coherence across active families
  W2 — Epistemic Commons Quality: mean truth score of published entries
  W3 — Steelman Depth: mean adversarial resistance of steelmans
  W4 — Calibration Score: mean Brier score of tracked predictions
  W5 — Deployment Index: active sovereign nodes deployed
  W6 — Research Output: CC0 papers and data published
  W7 — Diversity Index: tracks across how many domains are active

Wisdom GDP = weighted combination of W1-W7, normalized 0-100.

PUBLIC ENDPOINT: 
  tier2_digest.txt in the GitHub repo includes Wisdom GDP each run.
  Anyone can track the epistemic health of the Living Lattice.
"""

import os, json, math, datetime, statistics
from pathlib import Path
from typing import Dict, List, Optional
import socket as _socket

def _data_dir() -> Path:
    try:
        _socket.gethostbyname("localhost")
        return Path("/mnt/main")
    except Exception:
        p = Path(os.path.expanduser("~/.aubieeternal/main"))
        p.mkdir(parents=True, exist_ok=True)
        return p

DATA_DIR     = _data_dir()
WGDP_LOG     = DATA_DIR / "wisdom_gdp_history.jsonl"
WGDP_CURRENT = DATA_DIR / "wisdom_gdp_current.json"


class WisdomGDPCalculator:
    """
    Computes the Wisdom GDP for the AUBIEETERNAL Living Lattice.
    Each component is independently meaningful and publicly auditable.
    """

    def __init__(self):
        self.components: Dict[str, float] = {}
        self.weights = {
            "W1_coherence":           0.25,
            "W2_commons_quality":     0.20,
            "W3_steelman_depth":      0.15,
            "W4_calibration":         0.15,
            "W5_deployment_index":    0.10,
            "W6_research_output":     0.10,
            "W7_diversity_index":     0.05,
        }

    # ── Component calculators ─────────────────────────────────────────────────

    def _w1_aggregate_coherence(self) -> float:
        """Mean coherence across all active families (last 30 days)."""
        # Primary: from swarm status
        status_file = DATA_DIR / "swarm_status.json"
        if status_file.exists():
            try:
                status = json.loads(status_file.read_text())
                c = float(status.get("inter_rune_coherence", 0))
                if 0 < c <= 1.0:
                    return c
            except Exception:
                pass

        # Fallback: from app_state
        state_file = DATA_DIR / "app_state.json"
        if state_file.exists():
            try:
                state = json.loads(state_file.read_text())
                coh = state.get("coherence", {})
                if isinstance(coh, dict):
                    return float(coh.get("current", 0.75))
                return float(coh) if coh else 0.75
            except Exception:
                pass

        return 0.75  # Conservative default

    def _w2_commons_quality(self) -> float:
        """Mean truth score of Epistemic Commons entries (last 50)."""
        grok_log = DATA_DIR / "grokipedia_entries.jsonl"
        if not grok_log.exists():
            return 0.0

        scores = []
        for line in grok_log.read_text().strip().split("\n")[-50:]:
            try:
                e = json.loads(line)
                s = e.get("truth_score")
                if s is not None and 0 <= s <= 1.0:
                    scores.append(s)
            except Exception:
                pass

        return statistics.mean(scores) if len(scores) >= 3 else 0.0

    def _w3_steelman_depth(self) -> float:
        """Mean steelman adversarial resistance score (last 30)."""
        steel_log = DATA_DIR / "steelman_history.jsonl"
        if not steel_log.exists():
            return 0.0

        scores = []
        for line in steel_log.read_text().strip().split("\n")[-30:]:
            try:
                e = json.loads(line)
                s = e.get("score")
                if s is not None and 0 <= s <= 1.0:
                    scores.append(s)
            except Exception:
                pass

        return statistics.mean(scores) if len(scores) >= 3 else 0.0

    def _w4_calibration(self) -> float:
        """Mean calibration from belief ledger resolved predictions."""
        belief_log = DATA_DIR / "belief_ledger.jsonl"
        if not belief_log.exists():
            return 0.0

        calibrations = []
        for line in belief_log.read_text().strip().split("\n"):
            try:
                e = json.loads(line)
                conf     = e.get("confidence")
                resolved = e.get("resolved_correct")
                if conf is not None and resolved is not None:
                    outcome = 1.0 if resolved else 0.0
                    calibrations.append(1.0 - abs(conf - outcome))
            except Exception:
                pass

        return statistics.mean(calibrations) if len(calibrations) >= 5 else 0.0

    def _w5_deployment_index(self) -> float:
        """Normalized deployment count (0-1 scale, 10+ deployments = 1.0)."""
        deploy_log = DATA_DIR / "builder_contributions.jsonl"
        if not deploy_log.exists():
            return 0.0

        deployments = 0
        for line in deploy_log.read_text().strip().split("\n"):
            try:
                e = json.loads(line)
                if e.get("contribution_type") in ["node_deployment", "school_deployment", "community_deployment"]:
                    deployments += 1
            except Exception:
                pass

        return min(1.0, deployments / 10)

    def _w6_research_output(self) -> float:
        """Normalized CC0 research published (0-1 scale, 20+ = 1.0)."""
        research_count = 0

        # Count peer review acceptances
        decisions_log = DATA_DIR / "peer_reviews" / "decisions.jsonl"
        if decisions_log.exists():
            for line in decisions_log.read_text().strip().split("\n"):
                try:
                    d = json.loads(line)
                    if d.get("status") == "accepted":
                        research_count += 1
                except Exception:
                    pass

        # Count Epistemic Commons API entries
        api_dir = DATA_DIR / "repo" / "epistemic_commons" / "api"
        if api_dir.exists():
            try:
                latest = json.loads((api_dir / "latest.json").read_text())
                research_count += latest.get("total_entries", 0) // 5  # 5 entries = 1 research unit
            except Exception:
                pass

        return min(1.0, research_count / 20)

    def _w7_diversity_index(self) -> float:
        """Track diversity: fraction of major domains with activity."""
        MAJOR_DOMAINS = [
            "physics", "consciousness", "ethics", "mathematics",
            "decision_theory", "evolution", "cryptography", "social",
            "bitcoin", "ai_alignment", "simulation",
        ]

        # Check cosmos dashboard entries
        active_domains = set()
        for log_file in [DATA_DIR / "cosmos_answers.jsonl",
                          DATA_DIR / "belief_ledger.jsonl",
                          DATA_DIR / "foresight_tracker.jsonl"]:
            if log_file.exists():
                for line in log_file.read_text().strip().split("\n")[-50:]:
                    try:
                        e = json.loads(line)
                        d = e.get("domain", "")
                        if d in MAJOR_DOMAINS:
                            active_domains.add(d)
                    except Exception:
                        pass

        if not MAJOR_DOMAINS:
            return 0.0
        return len(active_domains) / len(MAJOR_DOMAINS)

    # ── Main computation ──────────────────────────────────────────────────────

    def compute(self) -> Dict:
        """Compute the full Wisdom GDP report."""
        raw_components = {
            "W1_coherence":        self._w1_aggregate_coherence(),
            "W2_commons_quality":  self._w2_commons_quality(),
            "W3_steelman_depth":   self._w3_steelman_depth(),
            "W4_calibration":      self._w4_calibration(),
            "W5_deployment_index": self._w5_deployment_index(),
            "W6_research_output":  self._w6_research_output(),
            "W7_diversity_index":  self._w7_diversity_index(),
        }

        # Weighted sum, scaled 0-100
        wgdp_raw = sum(
            raw_components[k] * self.weights[k]
            for k in self.weights
        )
        wgdp = round(wgdp_raw * 100, 2)

        # Determine tier
        if wgdp >= 80:
            tier = "🌟 Civilization-Grade"
        elif wgdp >= 65:
            tier = "🎓 University-Grade"
        elif wgdp >= 50:
            tier = "📚 Study-Group-Grade"
        elif wgdp >= 30:
            tier = "🌱 Emerging"
        else:
            tier = "🔮 Initializing"

        result = {
            "timestamp":      datetime.datetime.now().isoformat(),
            "wisdom_gdp":     wgdp,
            "tier":           tier,
            "components":     {k: round(v, 4) for k, v in raw_components.items()},
            "weights":        self.weights,
            "interpretation": (
                f"The Living Lattice is producing epistemic output at {wgdp:.1f}/100 quality. "
                f"Tier: {tier}. "
                f"Top component: {max(raw_components, key=lambda k: raw_components[k])}. "
                f"Lowest component (growth opportunity): "
                f"{min(raw_components, key=lambda k: raw_components[k])}."
            ),
        }

        # Save current
        WGDP_CURRENT.write_text(json.dumps(result, indent=2))

        # Append to history
        with open(WGDP_LOG, "a") as f:
            f.write(json.dumps({
                "timestamp":  result["timestamp"],
                "wisdom_gdp": wgdp,
                "tier":       tier,
                **{k: round(v, 3) for k, v in raw_components.items()},
            }) + "\n")

        return result

    def get_history(self, n: int = 30) -> List[Dict]:
        """Get Wisdom GDP history."""
        if not WGDP_LOG.exists():
            return []
        entries = []
        for line in WGDP_LOG.read_text().strip().split("\n"):
            try:
                entries.append(json.loads(line))
            except Exception:
                pass
        return entries[-n:]

    def get_growth_rate(self) -> Optional[float]:
        """Compute Wisdom GDP trend (points per week) from history."""
        history = self.get_history(20)
        if len(history) < 4:
            return None
        values = [h["wisdom_gdp"] for h in history]
        n = len(values)
        xs = list(range(n))
        x_mean = (n - 1) / 2
        y_mean = statistics.mean(values)
        num = sum((xs[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        den = sum((xs[i] - x_mean)**2 for i in range(n))
        if den == 0:
            return 0.0
        slope = num / den
        return round(slope * 7, 3)  # weekly rate


def get_wisdom_gdp() -> Dict:
    """Quick access to current Wisdom GDP."""
    # Try cached first
    if WGDP_CURRENT.exists():
        try:
            cached = json.loads(WGDP_CURRENT.read_text())
            # Refresh if older than 1 hour
            ts = datetime.datetime.fromisoformat(cached["timestamp"])
            age = (datetime.datetime.now(datetime.timezone.utc) -
                   ts.replace(tzinfo=datetime.timezone.utc)).seconds
            if age < 3600:
                return cached
        except Exception:
            pass

    calc = WisdomGDPCalculator()
    return calc.compute()


if __name__ == "__main__":
    calc   = WisdomGDPCalculator()
    result = calc.compute()
    print(f"\n🌟 WISDOM GDP: {result['wisdom_gdp']:.1f}/100  ({result['tier']})")
    print(f"\nComponents:")
    for k, v in result["components"].items():
        bar = "█" * int(v * 20)
        print(f"  {k:<30} {bar:<20} {v:.3f}")
    print(f"\n{result['interpretation']}")

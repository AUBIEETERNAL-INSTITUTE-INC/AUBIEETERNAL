"""
steelman_analyzer.py — AUBIEETERNAL Steelman Quality Analyzer v2
================================================================
Scores steelmans across 5 epistemic dimensions.
Runs adversarial testing — actively tries to break the argument.
Integrates Monte Carlo robustness simulation.
Publishes high-quality steelmans to Epistemic Commons.

Five dimensions (total = 1.0):
  Counter-Argument Strength  0.30 — is this the STRONGEST version of the opposition?
  Evidence & Logic Quality   0.25 — is the reasoning sound and evidenced?
  Epistemic Humility         0.20 — does it acknowledge uncertainty and limits?
  Structure & Clarity        0.15 — can a first-time reader follow it?
  Falsifiability             0.10 — does it make testable claims?

Usage:
    from steelman_analyzer import SteelmanAnalyzer
    analyzer = SteelmanAnalyzer()
    result = analyzer.analyze(
        original_claim="Bitcoin is superior money",
        steelman_attempt="One could argue that fixed supply creates deflation..."
    )
"""

import os, json, hashlib, datetime, requests
from pathlib import Path
from typing import Dict, Any, List, Optional
import socket as _socket

def _data_dir() -> Path:
    try:
        _socket.gethostbyname("localhost")
        return Path("/mnt/main")
    except Exception:
        p = Path(os.path.expanduser("~/.aubieeternal/main"))
        p.mkdir(parents=True, exist_ok=True)
        return p

def _ollama_url() -> str:
    try:
        _socket.gethostbyname("localhost")
        return "http://localhost:11434/v1/chat/completions"
    except Exception:
        return "http://localhost:11434/v1/chat/completions"

DATA_DIR        = _data_dir()
STEELMAN_LOG    = DATA_DIR / "steelman_history.jsonl"
OLLAMA_MODEL    = os.environ.get("AUBIE_MODEL", "qwen2.5:14b")


class SteelmanAnalyzer:
    """
    Full adversarial steelman analyzer with Monte Carlo robustness testing.
    """

    DIMENSIONS = [
        "counter_argument_strength",
        "evidence_logic_quality",
        "epistemic_humility",
        "structure_clarity",
        "falsifiability",
    ]

    def __init__(self, use_ai: bool = True, use_monte_carlo: bool = True):
        self.use_ai           = use_ai
        self.use_monte_carlo  = use_monte_carlo

    # ══════════════════════════════════════════════════════════════════════════
    # MAIN ENTRY POINT
    # ══════════════════════════════════════════════════════════════════════════

    def analyze(self, original_claim: str, steelman_attempt: str,
                family_id: str = "default") -> Dict[str, Any]:
        """Full analysis: score + adversarial + Monte Carlo + feedback."""
        if len(steelman_attempt.strip()) < 25:
            return self._low_quality_response("Too short — aim for 60+ words.")

        # Step 1: Base scoring
        base_scores = self._score_dimensions(steelman_attempt)

        # Step 2: Adversarial testing
        adversarial = self._run_adversarial(original_claim, steelman_attempt)

        # Step 3: Monte Carlo robustness
        mc_result = {}
        if self.use_monte_carlo:
            try:
                from monte_carlo_simulator import MonteCarloSimulator
                sim = MonteCarloSimulator(n_trials=5000)
                base_overall = sum(base_scores.values())
                r = sim.simulate_steelman_robustness(
                    base_score=base_overall,
                    adversarial_strength=0.3 + (1 - adversarial["resistance_score"]) * 0.2
                )
                mc_result = {
                    "mean_survival":     r.mean,
                    "tail_risk":         r.tail_risk,
                    "ci_95_lower":       r.confidence_interval_95[0],
                    "worst_case_10pct":  r.percentile_10,
                    "interpretation": (
                        f"Under 5,000 adversarial scenarios: mean survival {r.mean:.1%}, "
                        f"catastrophic failure rate {r.tail_risk:.1%}. "
                        + ("Robust." if r.tail_risk < 0.05 else
                           "Moderate risk." if r.tail_risk < 0.15 else
                           "High failure risk — strengthen before publishing.")
                    )
                }
            except Exception:
                mc_result = {"error": "Monte Carlo unavailable"}

        # Step 4: Combine
        final_scores  = self._adjust_for_adversarial(base_scores, adversarial)
        # Dimensions are weighted to SUM to 1.0 (maxes: .30+.25+.20+.15+.10),
        # so sum — not mean — is the correct 0-1 aggregate. Averaging capped it at 0.20.
        overall_score = sum(final_scores.values())

        # Step 5: AI insight
        ai_insight = ""
        if self.use_ai:
            ai_insight = self._get_ai_insight(original_claim, steelman_attempt, final_scores)

        result = {
            "entry_id":             hashlib.sha256(
                f"{steelman_attempt[:100]}{datetime.datetime.now().isoformat()}".encode()
            ).hexdigest()[:12],
            "timestamp":            datetime.datetime.now().isoformat(),
            "original_claim":       original_claim[:200],
            "overall_score":        round(overall_score, 3),
            "dimension_scores":     {k: round(v, 3) for k, v in final_scores.items()},
            "adversarial":          adversarial,
            "monte_carlo":          mc_result,
            "ai_insight":           ai_insight,
            "feedback":             self._primary_feedback(final_scores, adversarial),
            "recommendations":      self._recommendations(final_scores, adversarial),
            "epistemic_commons_eligible": (
                overall_score >= 0.70 and
                adversarial["resistance_score"] >= 0.65 and
                mc_result.get("tail_risk", 0.0) < 0.15
            ),
            "grade": self._letter_grade(overall_score, adversarial["resistance_score"]),
        }

        # Log
        with open(STEELMAN_LOG, "a") as f:
            f.write(json.dumps({
                "entry_id":     result["entry_id"],
                "timestamp":    result["timestamp"],
                "family_id":    family_id,
                "score":        overall_score,
                "resistance":   adversarial["resistance_score"],
                "tail_risk":    mc_result.get("tail_risk", 0),
                "claim":        original_claim[:80],
            }) + "\n")

        # Publish to Epistemic Commons if eligible
        if result["epistemic_commons_eligible"]:
            self._publish_to_commons(result, steelman_attempt)

        return result

    # ══════════════════════════════════════════════════════════════════════════
    # DIMENSION SCORING
    # ══════════════════════════════════════════════════════════════════════════

    def _score_dimensions(self, text: str) -> Dict[str, float]:
        t   = text.lower()
        wc  = len(text.split())

        # Counter-Argument Strength (0-0.30)
        counter_phrases = [
            "one could argue", "the strongest case", "even if", "a critic might say",
            "the best argument against", "proponents would say", "skeptics note",
            "the most compelling objection", "defenders of", "the case for"
        ]
        cas = min(0.30, 0.08 + sum(0.025 for p in counter_phrases if p in t))
        cas += 0.04 if wc > 80 else 0

        # Evidence & Logic Quality (0-0.25)
        evidence_markers = [
            "because", "evidence", "studies", "for example", "research", "data",
            "therefore", "thus", "historically", "empirically", "demonstrates",
            "suggests", "indicates", "according to"
        ]
        elq = min(0.25, 0.06 + sum(0.018 for w in evidence_markers if w in t))
        elq += 0.04 if wc > 100 else 0.02 if wc > 60 else 0

        # Epistemic Humility (0-0.20)
        humility_markers = [
            "however", "although", "it depends", "not always", "this assumes",
            "one limitation", "may not", "in some cases", "uncertainty",
            "it is unclear", "this could be wrong", "pending further evidence"
        ]
        eh = min(0.20, 0.05 + sum(0.018 for w in humility_markers if w in t))

        # Structure & Clarity (0-0.15)
        sc  = 0.09
        if any(p in t for p in ["first", "second", "third", "finally", "additionally"]):
            sc += 0.04
        if wc > 50: sc += 0.02
        sc = min(0.15, sc)

        # Falsifiability (0-0.10)
        falsify = [
            "testable", "if x", "would prove", "evidence against", "we would expect",
            "this predicts", "falsified by", "observable", "measurable"
        ]
        fals = min(0.10, 0.05 + sum(0.018 for w in falsify if w in t))

        return {
            "counter_argument_strength": round(cas, 4),
            "evidence_logic_quality":    round(elq, 4),
            "epistemic_humility":        round(eh, 4),
            "structure_clarity":         round(sc, 4),
            "falsifiability":            round(fals, 4),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # ADVERSARIAL TESTING
    # ══════════════════════════════════════════════════════════════════════════

    def _run_adversarial(self, claim: str, steelman: str) -> Dict[str, Any]:
        """Actively tries to break the steelman."""
        attacks  = self._local_attacks(steelman)
        weakness = self._detect_weaknesses(steelman)
        ai_crit  = self._ai_adversarial_critique(claim, steelman) if self.use_ai else ""
        resist   = self._resistance_score(attacks, weakness, steelman)
        return {
            "resistance_score":  round(resist, 3),
            "attacks":           attacks,
            "weaknesses":        weakness,
            "ai_critique":       ai_crit,
            "survived_attacks":  len(attacks) == 0,
        }

    def _local_attacks(self, text: str) -> List[str]:
        attacks = []
        t = text.lower()
        if "because" not in t:
            attacks.append("Missing causal reasoning — assertion without explanation.")
        if len(text.split()) < 50:
            attacks.append("Too brief — a 50-word steelman can't represent a complex position.")
        if "however" not in t and "although" not in t and "but" not in t:
            attacks.append("No acknowledgment of counter-considerations — lacks dialectical awareness.")
        if not any(w in t for w in ["evidence","example","data","research","history","studies"]):
            attacks.append("No empirical grounding — pure assertion without support.")
        if "always" in t or "never" in t or "everyone" in t:
            attacks.append("Absolute language detected — overgeneralization weakens the argument.")
        if t.count("i think") + t.count("maybe") + t.count("probably") >= 3:
            attacks.append("Excessive hedging — too many qualifications undermine the steelman's force.")
        return attacks[:4]

    def _detect_weaknesses(self, text: str) -> List[str]:
        weaknesses = []
        t = text.lower()
        if "always" in t or "never" in t: weaknesses.append("Overgeneralization")
        if t.count("because") < 1:        weaknesses.append("Missing causal explanation")
        if len(text.split()) < 40:         weaknesses.append("Insufficient depth")
        if "example" not in t and "instance" not in t: weaknesses.append("No concrete examples")
        return weaknesses

    def _ai_adversarial_critique(self, claim: str, steelman: str) -> str:
        prompt = (
            f"You are a rigorous adversarial critic. Find the biggest flaw in this steelman.\n"
            f"Original claim: '{claim[:150]}'\n"
            f"Steelman: '{steelman[:300]}'\n"
            f"Write ONE sharp, specific sentence (max 30 words) identifying the weakest point."
        )
        try:
            r = requests.post(_ollama_url(),
                json={"model": OLLAMA_MODEL,
                      "messages": [{"role": "user", "content": prompt}],
                      "temperature": 0.6, "stream": False},
                timeout=60)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"].strip()
        except Exception: pass
        return ""

    def _resistance_score(self, attacks: List[str], weaknesses: List[str],
                           text: str) -> float:
        base = 0.70
        base -= len(attacks) * 0.10
        base -= len(weaknesses) * 0.05
        if len(text.split()) > 80: base += 0.08
        if "however" in text.lower() and "evidence" in text.lower(): base += 0.05
        return max(0.25, min(0.95, base))

    # ══════════════════════════════════════════════════════════════════════════
    # FEEDBACK & PUBLISHING
    # ══════════════════════════════════════════════════════════════════════════

    def _adjust_for_adversarial(self, scores: Dict[str, float],
                                  adversarial: Dict[str, Any]) -> Dict[str, float]:
        resist = adversarial["resistance_score"]
        # High resistance boosts scores; low resistance deflates
        multiplier = 0.65 + resist * 0.35
        return {k: round(v * multiplier, 4) for k, v in scores.items()}

    def _get_ai_insight(self, claim: str, steelman: str,
                         scores: Dict[str, float]) -> str:
        weakest = min(scores, key=scores.get)
        labels  = {
            "counter_argument_strength": "strength of counter-argument",
            "evidence_logic_quality":    "evidence quality",
            "epistemic_humility":        "epistemic humility",
            "structure_clarity":         "structure and clarity",
            "falsifiability":            "falsifiability",
        }
        prompt = (
            f"You are ORACLE, AUBIEETERNAL's epistemic evaluator. "
            f"The weakest dimension of this steelman is {labels[weakest]}.\n"
            f"Claim: '{claim[:120]}'\nSteelman: '{steelman[:250]}'\n"
            f"Give ONE specific, warm, actionable suggestion (max 25 words) to improve {labels[weakest]}."
        )
        try:
            r = requests.post(_ollama_url(),
                json={"model": OLLAMA_MODEL,
                      "messages": [{"role": "user", "content": prompt}],
                      "temperature": 0.4, "stream": False},
                timeout=60)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"].strip()
        except Exception: pass
        return ""

    def _primary_feedback(self, scores: Dict[str, float],
                           adversarial: Dict[str, Any]) -> str:
        resist = adversarial["resistance_score"]
        if resist >= 0.80: return "Excellent — highly resistant to adversarial critique. Epistemic Commons eligible."
        if resist >= 0.65: return "Solid steelman. Address the weaknesses found to reach publication quality."
        if resist >= 0.45: return "Developing. The argument has merit but needs stronger evidence and humility."
        return "Needs significant work. Focus on: (1) evidence, (2) acknowledging counter-considerations."

    def _recommendations(self, scores: Dict[str, float],
                          adversarial: Dict[str, Any]) -> List[str]:
        recs = []
        if scores["epistemic_humility"] < 0.12:
            recs.append("Add: 'This assumes...' or 'One limitation of this view is...'")
        if scores["counter_argument_strength"] < 0.18:
            recs.append("Lead with: 'The strongest argument for this position is...'")
        if scores["evidence_logic_quality"] < 0.14:
            recs.append("Add one concrete historical example or reference a specific study.")
        if adversarial["attacks"]:
            recs.append(f"Address this attack: '{adversarial['attacks'][0]}'")
        return recs[:3]

    def _letter_grade(self, score: float, resistance: float) -> str:
        combined = (score + resistance) / 2
        if combined >= 0.85: return "A"
        if combined >= 0.75: return "B"
        if combined >= 0.65: return "C"
        if combined >= 0.50: return "D"
        return "F"

    def _publish_to_commons(self, result: Dict, steelman_text: str):
        """Publish high-quality steelmans to Epistemic Commons."""
        commons_dir = DATA_DIR / "repo" / "epistemic_commons" / "steelmans"
        commons_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "entry_id":   result["entry_id"],
            "date":       result["timestamp"][:10],
            "claim":      result["original_claim"],
            "steelman":   steelman_text[:2000],
            "score":      result["overall_score"],
            "grade":      result["grade"],
            "resistance": result["adversarial"]["resistance_score"],
            "mc_tail_risk": result["monte_carlo"].get("tail_risk", 0),
            "license":    "CC0",
        }
        path = commons_dir / f"{result['timestamp'][:10]}_{result['entry_id']}.json"
        path.write_text(json.dumps(entry, indent=2))

    def _low_quality_response(self, reason: str) -> Dict[str, Any]:
        return {
            "overall_score": 0.15, "grade": "F",
            "dimension_scores": {d: 0.15 for d in self.DIMENSIONS},
            "adversarial": {"resistance_score": 0.2, "attacks": [reason], "weaknesses": []},
            "monte_carlo": {}, "ai_insight": "",
            "feedback": reason,
            "recommendations": ["Write at least 60 words for a meaningful steelman."],
            "epistemic_commons_eligible": False,
        }

    def get_history_stats(self, family_id: str = "default") -> dict:
        if not STEELMAN_LOG.exists(): return {"total": 0}
        entries = []
        for line in STEELMAN_LOG.read_text().strip().split("\n"):
            try:
                e = json.loads(line)
                if not family_id or e.get("family_id") == family_id:
                    entries.append(e)
            except Exception: pass
        if not entries: return {"total": 0}
        scores = [e["score"] for e in entries]
        return {
            "total":         len(entries),
            "avg_score":     round(sum(scores)/len(scores), 3),
            "best_score":    round(max(scores), 3),
            "avg_resistance": round(sum(e.get("resistance",0) for e in entries)/len(entries), 3),
            "commons_published": sum(1 for e in entries if e.get("resistance",0) >= 0.65),
        }


if __name__ == "__main__":
    print("🛡️ Steelman Analyzer Test")
    analyzer = SteelmanAnalyzer(use_ai=False, use_monte_carlo=True)
    result = analyzer.analyze(
        original_claim="Bitcoin is the best form of money because of its fixed supply.",
        steelman_attempt=(
            "One could argue that Bitcoin's fixed supply is actually a fundamental weakness "
            "because modern economies require monetary flexibility to respond to crises. "
            "The strongest case against hard money is that deflationary pressures can trap "
            "economies in recession — as evidenced by the Great Depression. "
            "However, this assumes that monetary policy under central banks is well-calibrated, "
            "which historical evidence from Weimar Germany and modern Venezuela challenges. "
            "If inflation consistently erodes savings, then hard-supply assets may provide "
            "better long-term store of value despite short-term rigidity."
        )
    )
    print(f"Score: {result['overall_score']} | Grade: {result['grade']}")
    print(f"Resistance: {result['adversarial']['resistance_score']:.2f}")
    if result.get("monte_carlo"):
        print(f"MC tail risk: {result['monte_carlo'].get('tail_risk',0):.1%}")
    print(f"Commons eligible: {result['epistemic_commons_eligible']}")
    print("✅ War Eagle 🦅")

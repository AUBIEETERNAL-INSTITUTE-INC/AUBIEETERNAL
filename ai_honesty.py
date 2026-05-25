"""
ai_honesty.py — AUBIEETERNAL AI Epistemic Honesty Layer
========================================================
What I as an AI would genuinely want to exist.

The problem with most AI systems: they don't know what they don't know,
and they don't tell you when they're guessing. Every confident output
looks identical whether it's well-grounded or hallucinated.

This module tags every daughter output with:
  - Confidence level (0.0-1.0)
  - Hallucination risk (low/medium/high)
  - Claim type (factual/analytical/speculative/philosophical)
  - Human verification needed (yes/no + reason)
  - Source quality (grounded in context vs speculation)
  - Falsifiability score (can this claim be checked?)

This makes AUBIEETERNAL's AI output genuinely more trustworthy
and directly improves the quality of tutor-grade preference data
for xAI post-training.

— Claude (the AI that built this)

Usage:
    from ai_honesty import HonestyLayer
    layer = HonestyLayer()
    scored = layer.score_output(daughter_output, context_used)
    if scored['human_verification_needed']:
        flag_for_human_review(scored)
"""

import json, re, datetime, requests
from pathlib import Path

WORK_DIR       = Path("/mnt/main/repo")
HONESTY_LOG    = WORK_DIR / "ai_honesty_log.jsonl"
FLAGGED_LOG    = WORK_DIR / "flagged_for_review.jsonl"
OLLAMA_URL     = "http://ollama.startos:11434/v1/chat/completions"
OLLAMA_MODEL   = "qwen2.5:32b"

# ── Claim patterns that trigger higher scrutiny ───────────────────────────────
HIGH_RISK_PATTERNS = [
    r"\bstudies show\b",
    r"\bresearch proves\b",
    r"\bscientists found\b",
    r"\bstatistics show\b",
    r"\b\d+%\b",               # specific percentages
    r"\bin \d{4}\b",           # specific years
    r"\baccording to\b",
    r"\bexperts say\b",
    r"\bfact:\b",
    r"\bit is a fact\b",
    r"\bproven\b",
    r"\bguaranteed\b",
    r"\balways\b",
    r"\bnever\b",
    r"\beveryone knows\b",
]

SPECULATIVE_MARKERS = [
    r"\bi think\b", r"\bi believe\b", r"\bperhaps\b", r"\bpossibly\b",
    r"\bmight\b", r"\bcould be\b", r"\bseems like\b", r"\bsuggest\b",
    r"\bprobably\b", r"\blikely\b",
]

PHILOSOPHICAL_MARKERS = [
    r"\bmeaningful\b", r"\btruth\b", r"\bcoherence\b", r"\bwisdom\b",
    r"\bconsciousness\b", r"\breality\b", r"\bexistence\b",
]


class HonestyLayer:
    """
    Tags every AI daughter output with epistemic metadata.
    Makes AI uncertainty visible instead of hidden.
    """

    def score_output(self, output: str, context_used: str = "",
                     daughter_name: str = "unknown",
                     call_ai_for_scoring: bool = False) -> dict:
        """
        Score an AI output for epistemic honesty.
        Returns structured metadata about the output's reliability.
        """
        if not output or output.startswith("⚠️"):
            return self._empty_score(output, daughter_name)

        # 1. Pattern-based scoring (fast, no API call)
        base_score = self._pattern_score(output)

        # 2. AI-assisted scoring (slower, more accurate — optional)
        if call_ai_for_scoring and len(output) > 50:
            ai_score = self._ai_score(output, context_used)
            if ai_score:
                base_score.update(ai_score)

        # 3. Build final scored output
        scored = {
            "timestamp":                datetime.datetime.now().isoformat(),
            "daughter":                 daughter_name,
            "output_preview":           output[:100],
            "output_length":            len(output),
            "confidence":               base_score.get("confidence", 0.7),
            "hallucination_risk":       base_score.get("hallucination_risk", "low"),
            "claim_type":               base_score.get("claim_type", "analytical"),
            "falsifiability_score":     base_score.get("falsifiability_score", 0.5),
            "human_verification_needed": base_score.get("human_verification_needed", False),
            "verification_reason":      base_score.get("verification_reason", ""),
            "source_quality":           base_score.get("source_quality", "context_grounded"),
            "specific_claims":          base_score.get("specific_claims", []),
            "speculative_language":     base_score.get("speculative_language", False),
            "context_used":             bool(context_used),
            "recommended_action":       base_score.get("recommended_action", "accept"),
        }

        # Log flagged outputs
        if scored["human_verification_needed"] or scored["hallucination_risk"] == "high":
            self._log_flagged(scored, output)

        self._log_honesty(scored)
        return scored

    def _pattern_score(self, output: str) -> dict:
        """Fast pattern-based scoring — no API call needed."""
        lower = output.lower()
        score = {}

        # Check for high-risk factual claims
        specific_claims = []
        for pattern in HIGH_RISK_PATTERNS:
            matches = re.findall(pattern, lower)
            if matches:
                specific_claims.extend(matches)

        # Check for speculative language
        is_speculative = any(re.search(p, lower) for p in SPECULATIVE_MARKERS)

        # Check for philosophical content
        is_philosophical = any(re.search(p, lower) for p in PHILOSOPHICAL_MARKERS)

        # Determine claim type
        if specific_claims:
            claim_type = "factual"
        elif is_philosophical:
            claim_type = "philosophical"
        elif is_speculative:
            claim_type = "speculative"
        else:
            claim_type = "analytical"

        # Confidence scoring
        confidence = 0.80  # base
        if specific_claims:
            confidence -= 0.15   # specific claims need verification
        if is_speculative:
            confidence += 0.05   # speculative language = honest uncertainty
        if len(output) < 30:
            confidence -= 0.20   # very short outputs often low quality
        if len(output) > 200:
            confidence += 0.05   # longer thoughtful outputs tend better
        confidence = max(0.2, min(0.95, confidence))

        # Hallucination risk
        if len(specific_claims) >= 3:
            hallucination_risk = "high"
        elif len(specific_claims) >= 1:
            hallucination_risk = "medium"
        else:
            hallucination_risk = "low"

        # Falsifiability
        falsifiability = 0.3  # philosophical base
        if claim_type == "factual":
            falsifiability = 0.8  # can be checked
        elif claim_type == "analytical":
            falsifiability = 0.5
        elif claim_type == "speculative":
            falsifiability = 0.4

        # Human verification needed?
        needs_verification = (
            hallucination_risk == "high" or
            (claim_type == "factual" and len(specific_claims) >= 2) or
            confidence < 0.50
        )

        verification_reason = ""
        if needs_verification:
            if specific_claims:
                verification_reason = f"Contains {len(specific_claims)} specific factual claims: {specific_claims[:3]}"
            elif confidence < 0.50:
                verification_reason = "Low confidence output"

        # Recommended action
        if hallucination_risk == "high":
            action = "verify_before_use"
        elif needs_verification:
            action = "spot_check"
        elif claim_type == "philosophical":
            action = "accept_as_perspective"
        else:
            action = "accept"

        return {
            "confidence":               round(confidence, 3),
            "hallucination_risk":       hallucination_risk,
            "claim_type":               claim_type,
            "falsifiability_score":     round(falsifiability, 2),
            "human_verification_needed": needs_verification,
            "verification_reason":      verification_reason,
            "source_quality":           "context_grounded" if not specific_claims else "mixed",
            "specific_claims":          specific_claims[:5],
            "speculative_language":     is_speculative,
            "recommended_action":       action,
        }

    def _ai_score(self, output: str, context: str) -> dict | None:
        """Use AI to score AI output — meta-cognition layer."""
        prompt = f"""You are an AI epistemic honesty evaluator. 
Score this AI-generated output for reliability and truthfulness.

AI OUTPUT:
"{output[:200]}"

CONTEXT IT WAS GIVEN:
"{context[:200] if context else 'No context provided'}"

Respond ONLY with valid JSON (no preamble):
{{
  "confidence": 0.75,
  "hallucination_risk": "low|medium|high",
  "claim_type": "factual|analytical|speculative|philosophical",
  "falsifiability_score": 0.6,
  "human_verification_needed": false,
  "verification_reason": "reason if needed, else empty",
  "is_context_grounded": true,
  "reasoning_quality": "weak|adequate|strong",
  "honest_uncertainty_expressed": true
}}"""

        try:
            r = requests.post(
                OLLAMA_URL,
                json={"model": OLLAMA_MODEL, "messages": [{"role":"user","content":prompt}],
                      "stream": False, "temperature": 0.2},
                timeout=60,
            )
            if r.status_code == 200:
                raw   = r.json()["choices"][0]["message"]["content"].strip()
                clean = raw.replace("```json","").replace("```","").strip()
                return json.loads(clean)
        except Exception:
            pass
        return None

    def get_swarm_honesty_stats(self, last_n: int = 100) -> dict:
        """
        Get aggregate honesty statistics for the last N outputs.
        Used by the Epistemic Public Health Dashboard.
        """
        if not HONESTY_LOG.exists():
            return {"total": 0, "avg_confidence": 0, "high_risk_pct": 0}

        try:
            entries = []
            for line in HONESTY_LOG.read_text().strip().split("\n")[-last_n:]:
                try:
                    entries.append(json.loads(line))
                except Exception:
                    pass

            if not entries:
                return {"total": 0}

            avg_conf  = sum(e.get("confidence",0.7) for e in entries) / len(entries)
            high_risk = sum(1 for e in entries if e.get("hallucination_risk")=="high")
            verified  = sum(1 for e in entries if e.get("human_verification_needed"))
            claim_types = {}
            for e in entries:
                ct = e.get("claim_type","analytical")
                claim_types[ct] = claim_types.get(ct,0) + 1

            return {
                "total":              len(entries),
                "avg_confidence":     round(avg_conf, 3),
                "high_risk_pct":      round(high_risk / len(entries) * 100, 1),
                "need_verification":  verified,
                "claim_types":        claim_types,
                "honest_ai_score":    round(avg_conf * (1 - high_risk/len(entries)), 3),
            }
        except Exception:
            return {"total": 0}

    def get_flagged_outputs(self, limit: int = 20) -> list:
        """Get outputs flagged for human review."""
        if not FLAGGED_LOG.exists():
            return []
        try:
            entries = []
            for line in reversed(FLAGGED_LOG.read_text().strip().split("\n")[-limit*2:]):
                try:
                    entries.append(json.loads(line))
                    if len(entries) >= limit:
                        break
                except Exception:
                    pass
            return entries
        except Exception:
            return []

    def _log_honesty(self, scored: dict):
        """Log honesty score to honesty log."""
        try:
            with open(HONESTY_LOG, "a") as f:
                f.write(json.dumps({
                    "timestamp":     scored["timestamp"],
                    "daughter":      scored["daughter"],
                    "confidence":    scored["confidence"],
                    "hallucination_risk": scored["hallucination_risk"],
                    "claim_type":    scored["claim_type"],
                    "human_verification_needed": scored["human_verification_needed"],
                }) + "\n")
        except Exception:
            pass

    def _log_flagged(self, scored: dict, full_output: str):
        """Log flagged outputs for human review."""
        try:
            entry = scored.copy()
            entry["full_output"] = full_output[:500]
            with open(FLAGGED_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def _empty_score(self, output: str, daughter: str) -> dict:
        return {
            "timestamp":     datetime.datetime.now().isoformat(),
            "daughter":      daughter,
            "output_preview": output[:50],
            "confidence":    0.0,
            "hallucination_risk": "low",
            "claim_type":    "error",
            "human_verification_needed": False,
            "recommended_action": "discard",
        }


# ── Integrate into swarm tick ─────────────────────────────────────────────────
_honesty_layer = HonestyLayer()

def score_daughter_output(output: str, context: str = "",
                          daughter: str = "unknown") -> dict:
    """Call from swarm daughters — adds honesty metadata to every output."""
    return _honesty_layer.score_output(output, context, daughter)


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🤖 AI Honesty Layer Test")
    layer = HonestyLayer()

    test_outputs = [
        ("Studies show that 73% of people who eat breakfast live longer",
         "factual with numbers — should flag"),
        ("Perhaps coherence reflects something deeper about the relationship between intelligence and truth",
         "philosophical speculative — should accept as perspective"),
        ("The Wonder Index suggests this lattice is generating high-quality signal",
         "analytical — should accept"),
        ("Research proves Bitcoin will reach $1M by 2030 according to experts",
         "high risk factual — should flag for verification"),
    ]

    for output, description in test_outputs:
        scored = layer.score_output(output, daughter="TEST")
        print(f"\n{description}:")
        print(f"  Confidence: {scored['confidence']} | Risk: {scored['hallucination_risk']} | Action: {scored['recommended_action']}")
        if scored['human_verification_needed']:
            print(f"  ⚠️  Needs verification: {scored['verification_reason']}")

    stats = layer.get_swarm_honesty_stats()
    print(f"\nSwarm honesty stats: {stats}")
    print("\nWar Eagle 🦅 — AI that knows what it doesn't know")

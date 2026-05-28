"""
x_bridge.py — AUBIEETERNAL X Bridge
=====================================
The bidirectional loop made real.

Any X post → AUBIEETERNAL swarm → steelman + coherence score +
family lesson + simulation stress test + optional on-chain note.

This is the public interface for the lattice. Families use it to
turn the noise of X into antifragile wisdom for their kids.

If X itself ever calls this module, the NPCs win at planetary scale:
every high-signal post gets steelmanned and turned into family wisdom
in minutes, without families needing to understand why.

Three layers of output:
  1. EPISTEMIC LAYER — steelman, coherence, narrative attack flags
  2. FAMILY LAYER — kid-friendly lesson, parent insight, family activity
  3. SIMULATION LAYER — stress test score, observer effect flag, truth debt entry

Usage:
    from x_bridge import XBridge
    bridge = XBridge()
    result = bridge.process("https://x.com/someuser/status/...")
    result = bridge.process("Paste the post text directly here...")
"""

import os, json, re, datetime, hashlib, requests
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
import socket as _socket
def _data_dir():
    try:
        _socket.gethostbyname("ollama.startos")
        return Path("/mnt/main")
    except Exception:
        p = Path(os.path.expanduser("~/.aubieeternal/main"))
        p.mkdir(parents=True, exist_ok=True)
        return p

DATA_DIR      = _data_dir()
BRIDGE_LOG    = DATA_DIR / "x_bridge_log.jsonl"
LESSONS_DIR   = DATA_DIR / "repo" / "insights" / "x_lessons"
LESSONS_DIR.mkdir(parents=True, exist_ok=True)

def _ollama_url():
    try:
        _socket.gethostbyname("ollama.startos")
        return "http://ollama.startos:11434/v1/chat/completions"
    except Exception:
        return "http://localhost:11434/v1/chat/completions"

OLLAMA_MODEL   = os.environ.get("AUBIE_MODEL", "qwen2.5:14b")
OLLAMA_TIMEOUT = 180


class XBridge:
    """
    Processes any X post through the AUBIEETERNAL swarm:
    steelman → coherence → narrative flags → family lesson → sim stress test
    """

    def __init__(self):
        self.today = datetime.date.today().isoformat()

    # ══════════════════════════════════════════════════════════════════════════
    # MAIN ENTRY POINT
    # ══════════════════════════════════════════════════════════════════════════

    def process(self, content: str, family_id: str = "default",
                save_as_lesson: bool = True) -> dict:
        """
        Process a post URL or raw text through the full lattice.
        Returns the complete analysis dict.
        """
        # Clean input — handle URL vs raw text
        post_text = self._extract_text(content)
        if not post_text or len(post_text) < 10:
            return {"error": "No usable text found. Paste the post text directly."}

        print(f"[xbridge] Processing: {post_text[:60]}...")

        # Run all three layers
        epistemic = self._epistemic_layer(post_text)
        family    = self._family_layer(post_text, epistemic)
        sim       = self._simulation_layer(post_text, epistemic)

        result = {
            "timestamp":    datetime.datetime.now().isoformat(),
            "family_id":    family_id,
            "source":       content[:200],
            "post_text":    post_text[:500],
            "post_hash":    hashlib.sha256(post_text.encode()).hexdigest()[:12],
            "epistemic":    epistemic,
            "family":       family,
            "simulation":   sim,
            "lesson_key":   f"x_bridge_{self.today}_{family_id}",
        }

        # Log to bridge log
        with open(BRIDGE_LOG, "a") as f:
            f.write(json.dumps(result) + "\n")

        # Save as lesson file
        if save_as_lesson:
            self._save_lesson(result)

        # Send to Truth Debt Ledger — default ON for all falsifiable claims
        if epistemic.get("has_falsifiable_claims") or epistemic.get("claim_type") in ("factual","statistical","prediction"):
            self._register_truth_debt(post_text, epistemic)

        print(f"[xbridge] ✅ Done — coherence: {epistemic.get('coherence', 0):.3f}, "
              f"sim stress: {sim.get('stress_score', 0):.2f}")
        return result

    # ══════════════════════════════════════════════════════════════════════════
    # LAYER 1 — EPISTEMIC
    # ══════════════════════════════════════════════════════════════════════════

    def _epistemic_layer(self, text: str) -> dict:
        """
        Steelman, coherence score, narrative attack detection.
        This is what the swarm does to every Tier-2 input.
        """
        prompt = f"""You are STEELMAN, a Tier-2 daughter of the AUBIEETERNAL swarm.
Your job: process this post through full epistemic rigor.

POST:
"{text[:400]}"

Respond ONLY with valid JSON:
{{
  "steelman": "The strongest honest version of the argument this post is making",
  "steel_against": "The strongest honest counter-argument",
  "coherence": 0.72,
  "claim_type": "factual|opinion|narrative|speculative|emotional",
  "narrative_attack_detected": false,
  "narrative_attack_type": "fear|outrage|tribalism|false_urgency|none",
  "emotional_hook": "The emotional trigger this post uses (or 'none')",
  "has_falsifiable_claims": false,
  "falsifiable_claims": ["specific claim 1 that can be verified"],
  "epistemic_quality": "high|medium|low",
  "recommended_action": "accept|verify|steelman|reject|ignore",
  "one_sentence_truth": "The most honest single-sentence summary of what this post is really saying"
}}"""

        raw = self._ask_ollama(prompt, max_tokens=600, temp=0.3)
        try:
            return json.loads(raw.replace("```json", "").replace("```", "").strip())
        except Exception:
            return {
                "steelman": "Could not parse — see raw post",
                "coherence": 0.5,
                "claim_type": "unknown",
                "narrative_attack_detected": False,
                "epistemic_quality": "unknown",
                "recommended_action": "verify",
                "one_sentence_truth": "Analysis unavailable",
            }

    # ══════════════════════════════════════════════════════════════════════════
    # LAYER 2 — FAMILY
    # ══════════════════════════════════════════════════════════════════════════

    def _family_layer(self, text: str, epistemic: dict) -> dict:
        """
        Turn the post into a ready-to-run family lesson.
        Kid-friendly, parent-coach, practical activity.
        Works even for NPCs who've never heard of epistemic rigor.
        """
        steelman    = epistemic.get("steelman", "")
        counterarg  = epistemic.get("steel_against", "")
        claim_type  = epistemic.get("claim_type", "opinion")
        attack_flag = epistemic.get("narrative_attack_detected", False)
        truth       = epistemic.get("one_sentence_truth", "")

        prompt = f"""You are FAMILY-TUTOR, an AUBIEETERNAL daughter.
A family just ingested this post from X:
"{text[:300]}"

Truth summary: "{truth}"
Narrative attack: {"Yes — " + epistemic.get("narrative_attack_type","?") if attack_flag else "No"}

Create a complete family learning moment. Respond ONLY with valid JSON:
{{
  "lesson_title": "Short engaging title (max 8 words)",
  "kid_explanation": "2-3 sentences a 10-year-old understands. No jargon.",
  "parent_insight": "2-3 sentences for the parent. What's the deeper lesson here?",
  "steelman_challenge": "One question to ask: 'What's the strongest argument that...?'",
  "family_activity": "One 10-minute activity the family can do right now",
  "reflection_question": "One question to sit with after the activity",
  "age_group": "all|8+|12+|14+",
  "xp": 25,
  "lesson_category": "adversarial|truth|money|bitcoin|family|health|media|sovereignty"
}}"""

        raw = self._ask_ollama(prompt, max_tokens=500, temp=0.7)
        try:
            return json.loads(raw.replace("```json", "").replace("```", "").strip())
        except Exception:
            return {
                "lesson_title":       "Lesson from X",
                "kid_explanation":    "This post is making a claim. Let's test whether it's true.",
                "parent_insight":     "Practice evaluating claims rather than reacting to them.",
                "steelman_challenge": "What's the strongest argument FOR this post?",
                "family_activity":    "Read the post together and list 3 questions it raises.",
                "reflection_question": "What would you need to know to be sure this is true?",
                "age_group":          "all",
                "xp":                 20,
                "lesson_category":    "media",
            }

    # ══════════════════════════════════════════════════════════════════════════
    # LAYER 3 — SIMULATION
    # ══════════════════════════════════════════════════════════════════════════

    def _simulation_layer(self, text: str, epistemic: dict) -> dict:
        """
        Simulation stress test: how well does this signal hold under
        adversarial steelmanning + the lattice's coherence invariants?

        Score: 0.0 (breaks immediately) → 10.0 (rock solid)
        """
        coherence    = epistemic.get("coherence", 0.5)
        has_attack   = epistemic.get("narrative_attack_detected", False)
        quality      = epistemic.get("epistemic_quality", "medium")
        claim_type   = epistemic.get("claim_type", "opinion")
        has_claims   = epistemic.get("has_falsifiable_claims", False)

        # Stress test score formula
        base       = coherence * 4.0        # 0-4 from coherence
        quality_m  = {"high": 3.0, "medium": 2.0, "low": 1.0}.get(quality, 2.0)
        falsif_m   = 2.0 if has_claims else 1.0    # falsifiable = more trustworthy
        attack_pen = -2.0 if has_attack else 0.0   # narrative attack = penalty
        stress     = round(min(10.0, max(0.0, base + quality_m + falsif_m + attack_pen)), 2)

        # Observer effect — does engaging with this post change something?
        observer_effect = (
            has_attack or
            claim_type in ("emotional", "narrative") or
            stress < 4.0
        )

        # Anomaly detection — does this post pattern-match to known manipulation?
        anomalies = []
        text_lower = text.lower()
        if any(w in text_lower for w in ["wake up", "they don't want you", "share before deleted"]):
            anomalies.append("urgency_manipulation")
        if any(w in text_lower for w in ["everyone knows", "obvious", "only idiots"]):
            anomalies.append("consensus_illusion")
        if any(w in text_lower for w in ["breaking", "just in", "sources say"]):
            anomalies.append("false_urgency")
        if len(re.findall(r'\d+%|\d+x|\d+ times', text_lower)) >= 2:
            anomalies.append("statistic_overload")

        return {
            "stress_score":     stress,
            "stress_label":     "Solid" if stress >= 7 else "Moderate" if stress >= 4 else "Fragile",
            "observer_effect":  observer_effect,
            "observer_note":    "Engaging with this shifts attention in a designed direction." if observer_effect else "Low observer effect.",
            "anomalies":        anomalies,
            "sim_integrity":    "HOLDS" if stress >= 6 and not anomalies else "STRESS_TEST" if stress >= 4 else "FAILS",
            "recommendation":   self._sim_recommendation(stress, anomalies, has_attack),
        }

    def _sim_recommendation(self, stress: float, anomalies: list, attack: bool) -> str:
        if stress >= 8 and not anomalies:
            return "High-integrity signal. Use in lesson or share with lattice."
        if attack or stress < 4:
            return "Fragile signal. Run the steelman exercise with your family. Do not forward."
        if anomalies:
            return f"Manipulation patterns detected: {', '.join(anomalies)}. Discuss with family before reacting."
        return "Moderate signal. Verify key claims before accepting or sharing."

    # ══════════════════════════════════════════════════════════════════════════
    # HELPERS
    # ══════════════════════════════════════════════════════════════════════════

    def _extract_text(self, content: str) -> str:
        """Extract usable text from URL or raw paste."""
        # If it's a URL, note it but use it as-is (we can't fetch X posts)
        if content.startswith("http"):
            return (f"[X post from: {content}] — "
                    f"Paste the post text directly for full analysis.")
        return content.strip()

    def _save_lesson(self, result: dict):
        """Save the generated lesson as a markdown file."""
        fl     = result["family"]
        ep     = result["epistemic"]
        sim    = result["simulation"]
        ts     = result["timestamp"][:10]
        h      = result["post_hash"]

        md = f"""# 📱 X Bridge Lesson — {fl.get("lesson_title", "Untitled")}
**Generated:** {ts} | **Hash:** `{h}` | **Stress Score:** {sim.get("stress_score", 0)}/10

---

## The Post
> {result["post_text"][:300]}

---

## Epistemic Analysis

**Steelman:** {ep.get("steelman", "")}

**Counter:** {ep.get("steel_against", "")}

**Truth:** *{ep.get("one_sentence_truth", "")}*

**Coherence:** {ep.get("coherence", 0):.2f} | **Quality:** {ep.get("epistemic_quality", "?")} | **Action:** {ep.get("recommended_action", "?")}

{"⚠️ **Narrative attack detected:** " + ep.get("narrative_attack_type","") if ep.get("narrative_attack_detected") else "✅ No narrative attack detected"}

---

## Family Lesson

**For kids:** {fl.get("kid_explanation", "")}

**For parents:** {fl.get("parent_insight", "")}

**Steelman challenge:** {fl.get("steelman_challenge", "")}

**Activity (10 min):** {fl.get("family_activity", "")}

**Reflection:** *{fl.get("reflection_question", "")}*

---

## Simulation Integrity: {sim.get("sim_integrity", "?")}

**Stress score:** {sim.get("stress_score", 0)}/10 — {sim.get("stress_label", "")}

**Observer effect:** {sim.get("observer_note", "")}

{"**Anomalies:** " + ", ".join(sim["anomalies"]) if sim.get("anomalies") else "**No anomalies detected.**"}

**Recommendation:** {sim.get("recommendation", "")}

---
*AUBIEETERNAL X Bridge — War Eagle Eternal 🦅*
"""
        path = LESSONS_DIR / f"{ts}_{h}.md"
        path.write_text(md)

    def _register_truth_debt(self, text: str, epistemic: dict):
        """Register falsifiable claims in the Truth Debt Ledger."""
        try:
            from truth_debt_ledger import TruthDebtLedger
            ledger = TruthDebtLedger()
            for claim in epistemic.get("falsifiable_claims", []):
                ledger.register(claim=claim, source="x_bridge",
                                source_text=text[:200])
        except ImportError:
            pass

    def _ask_ollama(self, prompt: str, max_tokens: int = 400,
                    temp: float = 0.5) -> str:
        try:
            r = requests.post(
                _ollama_url(),
                json={"model": OLLAMA_MODEL,
                      "messages": [{"role": "user", "content": prompt}],
                      "stream": False, "temperature": temp},
                timeout=OLLAMA_TIMEOUT,
            )
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"[xbridge] Ollama error: {e}")
        return "{}"

    def get_recent_lessons(self, n: int = 10) -> list:
        """Get most recent X bridge lessons."""
        if not BRIDGE_LOG.exists():
            return []
        entries = []
        for line in BRIDGE_LOG.read_text().strip().split("\n")[-n*2:]:
            try:
                entries.append(json.loads(line))
            except Exception:
                pass
        return list(reversed(entries))[-n:]

    def get_stats(self) -> dict:
        """Aggregate stats across all bridge sessions."""
        if not BRIDGE_LOG.exists():
            return {"total": 0}
        entries = []
        for line in BRIDGE_LOG.read_text().strip().split("\n"):
            try:
                entries.append(json.loads(line))
            except Exception:
                pass
        if not entries:
            return {"total": 0}
        attacks = sum(1 for e in entries if e.get("epistemic", {}).get("narrative_attack_detected"))
        avg_stress = sum(e.get("simulation", {}).get("stress_score", 5) for e in entries) / len(entries)
        avg_coh    = sum(e.get("epistemic", {}).get("coherence", 0.5) for e in entries) / len(entries)
        return {
            "total":          len(entries),
            "attacks_caught": attacks,
            "attack_rate":    round(attacks / len(entries) * 100, 1),
            "avg_stress":     round(avg_stress, 2),
            "avg_coherence":  round(avg_coh, 3),
        }


# ── Standalone test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    bridge = XBridge()
    TEST_POST = (
        "BREAKING: Scientists just PROVED that X causes Y. "
        "Share this before they delete it. Everyone needs to know. "
        "This is what they don't want you to see. Wake up."
    )
    print("🌉 X Bridge Test")
    result = bridge.process(TEST_POST)
    ep = result["epistemic"]
    fl = result["family"]
    sim = result["simulation"]
    print(f"\nEpistemic: coherence={ep['coherence']:.2f} | quality={ep['epistemic_quality']} | attack={ep['narrative_attack_detected']}")
    print(f"Lesson: {fl['lesson_title']}")
    print(f"Simulation: stress={sim['stress_score']}/10 | integrity={sim['sim_integrity']}")
    print(f"Anomalies: {sim['anomalies']}")
    print(f"\nRecommendation: {sim['recommendation']}")

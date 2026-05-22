"""
family_hud.py — AUBIEETERNAL Family Co-Learning Session Handler
==============================================================
Manages shared real-time state for dual Halo HUD sessions.

Kid HUD:  lesson content, coherence meter, steelman prompt, XP
Parent HUD: live stats panel, polyvagal state, parent actions

Writes every session to master_truth_log.jsonl so the swarm
learns from family interactions and improves future lessons.

Usage:
    from family_hud import FamilySession
    session = FamilySession(kid_name="Gaby", kid_age=9, parent_name="Sarah")
    session.start_lesson("Courage — Level 1")
    result = session.submit_answer("The strongest argument against courage is...")
    session.end()
"""

import json
import datetime
import random
import os
import requests
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
WORK_DIR       = Path("/mnt/main/repo")
TRUTH_LOG      = WORK_DIR / "master_truth_log.jsonl"
SESSION_STATE  = Path("/mnt/main/family_session.json")
OLLAMA_URL     = "http://192.168.1.251:59885/v1/chat/completions"
OLLAMA_MODEL   = "qwen3:32b"

# ── Lesson Library ────────────────────────────────────────────────────────────
LESSONS = {

    # ── COURAGE (5 levels) ────────────────────────────────────────────────────
    "courage-1": {
        "title":       "Courage — Level 1",
        "topic":       "What is courage? When fear is present but you act anyway.",
        "steelman":    "What is the strongest argument that courage is actually dangerous?",
        "example":     "Achilles knew he might die at Troy but went anyway. Was that courage or foolishness?",
        "age_hint":    "All ages — start here",
        "xp":          15, "rune": "COURAGE•RUNE", "min_coherence": 0.55,
    },
    "courage-2": {
        "title":       "Courage — Level 2",
        "topic":       "Social courage: standing up for someone when it might cost you.",
        "steelman":    "What is the strongest argument that staying silent is sometimes the braver choice?",
        "example":     "Rosa Parks didn't just break a rule — she accepted the cost of breaking it. That's courage.",
        "age_hint":    "8+",
        "xp":          18, "rune": "COURAGE•RUNE", "min_coherence": 0.60,
    },
    "courage-3": {
        "title":       "Courage — Level 3",
        "topic":       "Intellectual courage: saying 'I was wrong' or 'I don't know.'",
        "steelman":    "What is the strongest argument that admitting you're wrong makes you look weak?",
        "example":     "The greatest scientists change their minds when evidence demands it. That takes more courage than stubbornness.",
        "age_hint":    "10+",
        "xp":          22, "rune": "COURAGE•RUNE", "min_coherence": 0.65,
    },
    "courage-4": {
        "title":       "Courage — Level 4",
        "topic":       "Antifragile courage: each act of courage makes the next one easier.",
        "steelman":    "What is the strongest argument that courage is a fixed trait you either have or don't?",
        "example":     "Soldiers who train under stress perform better under real stress. Courage is a muscle.",
        "age_hint":    "12+",
        "xp":          25, "rune": "COURAGE•RUNE", "min_coherence": 0.70,
    },
    "courage-5": {
        "title":       "Courage — Level 5 (Master)",
        "topic":       "Long-game courage: choosing a hard right over an easy wrong over years.",
        "steelman":    "What is the strongest argument that short-term compromise is rational even when it violates your values?",
        "example":     "Mandela spent 27 years in prison rather than compromise. Was that rational?",
        "age_hint":    "14+",
        "xp":          35, "rune": "COURAGE•ETERNAL•RUNE", "min_coherence": 0.75,
    },

    # ── ANTIFRAGILITY (4 levels) ──────────────────────────────────────────────
    "antifragility-1": {
        "title":       "Antifragility — Level 1",
        "topic":       "Things that get stronger from stress. Bones, muscles, immune system.",
        "steelman":    "What is the strongest argument that stress always causes harm, not strength?",
        "example":     "Vaccinations give you a small dose of the disease so your immune system gets stronger.",
        "age_hint":    "All ages",
        "xp":          18, "rune": "STRENGTH•RUNE", "min_coherence": 0.60,
    },
    "antifragility-2": {
        "title":       "Antifragility — Level 2",
        "topic":       "The Barbell Strategy: combine extreme safety with extreme upside. Avoid the fragile middle.",
        "steelman":    "What is the strongest argument that a moderate, balanced approach is always best?",
        "example":     "Taleb keeps 90% in safe assets and 10% in high-upside bets. The middle gets wiped out.",
        "age_hint":    "10+",
        "xp":          22, "rune": "BARBELL•RUNE", "min_coherence": 0.65,
    },
    "antifragility-3": {
        "title":       "Antifragility — Level 3",
        "topic":       "Black Swans: rare unpredictable events that change everything. Build for survival, not prediction.",
        "steelman":    "What is the strongest argument that we can predict and prevent Black Swan events?",
        "example":     "No one predicted COVID, the 2008 crash, or 9/11 accurately. But some systems survived anyway.",
        "age_hint":    "12+",
        "xp":          28, "rune": "ORACLE•RUNE", "min_coherence": 0.68,
    },
    "antifragility-4": {
        "title":       "Antifragility — Level 4 (Master)",
        "topic":       "Hormesis: deliberate exposure to small stressors to build systemic strength.",
        "steelman":    "What is the strongest argument that deliberately seeking stress is self-destructive?",
        "example":     "Cold water, hard conversations, difficult problems — done with intention, these strengthen every system they touch.",
        "age_hint":    "14+",
        "xp":          32, "rune": "HORMES•RUNE", "min_coherence": 0.72,
    },

    # ── BITCOIN SOVEREIGNTY (4 levels) ───────────────────────────────────────
    "bitcoin-sovereignty-1": {
        "title":       "Bitcoin Sovereignty — Level 1",
        "topic":       "Your keys = your coins. What is self-custody and why does it matter?",
        "steelman":    "What is the strongest argument that keeping Bitcoin on an exchange is safer?",
        "example":     "If you don't hold your private key, someone else can freeze or take your Bitcoin.",
        "age_hint":    "All ages",
        "xp":          20, "rune": "SOVEREIGN•RUNE", "min_coherence": 0.65,
    },
    "bitcoin-sovereignty-2": {
        "title":       "Bitcoin Sovereignty — Level 2",
        "topic":       "Why Bitcoin has a fixed supply of 21 million. Scarcity vs inflation.",
        "steelman":    "What is the strongest argument that unlimited money printing is beneficial for society?",
        "example":     "Every 4 years Bitcoin's new supply is cut in half (halving). No one can change this rule.",
        "age_hint":    "9+",
        "xp":          22, "rune": "SATOSHI•RUNE", "min_coherence": 0.65,
    },
    "bitcoin-sovereignty-3": {
        "title":       "Bitcoin Sovereignty — Level 3",
        "topic":       "Bitcoin Runes: inscribing permanent truth on-chain. Why on-chain permanence matters.",
        "steelman":    "What is the strongest argument that data stored on the Bitcoin blockchain is not truly permanent?",
        "example":     "AUBIEETERNAL runes are inscribed forever at blocks 944,048 and 944,402. No one can erase them.",
        "age_hint":    "11+",
        "xp":          25, "rune": "RUNE•ETERNAL", "min_coherence": 0.68,
    },
    "bitcoin-sovereignty-4": {
        "title":       "Bitcoin Sovereignty — Level 4 (Master)",
        "topic":       "Lightning Network: instant sovereign payments. How payment channels work.",
        "steelman":    "What is the strongest argument that the Lightning Network is less secure than on-chain Bitcoin?",
        "example":     "Two people can open a payment channel and send thousands of transactions without touching the blockchain.",
        "age_hint":    "13+",
        "xp":          30, "rune": "LIGHTNING•RUNE", "min_coherence": 0.70,
    },

    # ── STEELMANNING (3 levels) ───────────────────────────────────────────────
    "steelmanning-1": {
        "title":       "Steelmanning — Level 1",
        "topic":       "How to argue the other side better than they can.",
        "steelman":    "What is the strongest argument that steelmanning is a waste of time?",
        "example":     "Before you disagree with someone, rebuild their argument in its strongest form.",
        "age_hint":    "8+",
        "xp":          22, "rune": "TRUTH•RUNE", "min_coherence": 0.65,
    },
    "steelmanning-2": {
        "title":       "Steelmanning — Level 2",
        "topic":       "Finding the steel in bad arguments. Even wrong people have something true to say.",
        "steelman":    "What is the strongest argument that every conspiracy theory contains zero useful signal?",
        "example":     "Even flat-earthers have something right: they question authority and demand evidence. That instinct is sound.",
        "age_hint":    "11+",
        "xp":          26, "rune": "AXIOM•RUNE", "min_coherence": 0.68,
    },
    "steelmanning-3": {
        "title":       "Steelmanning — Level 3 (Master)",
        "topic":       "Epistemic humility: holding strong opinions loosely. The map is not the territory.",
        "steelman":    "What is the strongest argument that changing your mind frequently signals weak thinking?",
        "example":     "Keynes said: 'When the facts change, I change my mind. What do you do, sir?'",
        "age_hint":    "13+",
        "xp":          30, "rune": "LINDY•RUNE", "min_coherence": 0.72,
    },

    # ── POLYVAGAL / EMOTIONAL REGULATION (3 levels) ──────────────────────────
    "polyvagal-1": {
        "title":       "Your Nervous System — Level 1",
        "topic":       "Three modes: Safe & curious, Fight/flight, Shutdown. You can learn to notice which one you're in.",
        "steelman":    "What is the strongest argument that emotions are just feelings and don't affect thinking?",
        "example":     "When you're in Safe mode (ventral vagal), you learn 10× faster than when you're scared or shut down.",
        "age_hint":    "All ages",
        "xp":          15, "rune": "POLY•RUNE", "min_coherence": 0.55,
    },
    "polyvagal-2": {
        "title":       "Your Nervous System — Level 2",
        "topic":       "Co-regulation: how one calm person can help another person calm down just by being present.",
        "steelman":    "What is the strongest argument that people should manage their emotions completely on their own?",
        "example":     "When a parent stays calm during a kid's meltdown, the kid's nervous system literally syncs to the parent's.",
        "age_hint":    "8+",
        "xp":          18, "rune": "POLY•RUNE", "min_coherence": 0.60,
    },
    "polyvagal-3": {
        "title":       "Your Nervous System — Level 3 (Master)",
        "topic":       "Hormesis for the nervous system: deliberately entering and recovering from mild stress to build resilience.",
        "steelman":    "What is the strongest argument that exposing children to stress is harmful, not helpful?",
        "example":     "Kids who play outside, fall, and get back up have better emotional regulation as adults.",
        "age_hint":    "12+",
        "xp":          25, "rune": "HORMES•RUNE", "min_coherence": 0.68,
    },

    # ── VIA NEGATIVA / LINDY (2 levels) ──────────────────────────────────────
    "via-negativa-1": {
        "title":       "Via Negativa — Level 1",
        "topic":       "Sometimes the best move is to remove things, not add them.",
        "steelman":    "What is the strongest argument that adding is always better than removing?",
        "example":     "A sculptor reveals the statue by removing marble, not adding it.",
        "age_hint":    "All ages",
        "xp":          18, "rune": "LINDY•RUNE", "min_coherence": 0.60,
    },
    "via-negativa-2": {
        "title":       "Lindy Effect — Level 2",
        "topic":       "Things that have survived a long time are likely to survive longer. Old ideas that persist are robust.",
        "steelman":    "What is the strongest argument that new things are always better than old things?",
        "example":     "The hammer, bread, and fire are thousands of years old. Instagram is 14. Which is more likely to exist in 100 years?",
        "age_hint":    "10+",
        "xp":          22, "rune": "LINDY•RUNE", "min_coherence": 0.65,
    },

    # ── WONDER (2 levels) ─────────────────────────────────────────────────────
    "wonder-1": {
        "title":       "Wonder & Awe — Level 1",
        "topic":       "Why feeling amazed is a signal you are near the truth.",
        "steelman":    "What is the strongest argument that wonder leads us away from truth?",
        "example":     "When Einstein thought about riding a beam of light, his wonder led to Relativity.",
        "age_hint":    "All ages",
        "xp":          15, "rune": "WONDER•RUNE", "min_coherence": 0.55,
    },
    "wonder-2": {
        "title":       "Wonder & Awe — Level 2",
        "topic":       "The Wonder Index: why coherence, awe, and truth-proximity are connected.",
        "steelman":    "What is the strongest argument that wonder is just an emotional response with no epistemic value?",
        "example":     "Every major scientific discovery started with someone saying 'That's strange... why does that happen?'",
        "age_hint":    "11+",
        "xp":          20, "rune": "WONDER•ETERNAL•RUNE", "min_coherence": 0.62,
    },

    # ── SKIN IN THE GAME (2 levels) ───────────────────────────────────────────
    "skin-in-the-game-1": {
        "title":       "Skin in the Game — Level 1",
        "topic":       "Never trust advice from someone who doesn't bear the consequences of being wrong.",
        "steelman":    "What is the strongest argument that experts should advise even when they have no personal risk?",
        "example":     "Would you take diet advice from an overweight doctor? Why or why not?",
        "age_hint":    "9+",
        "xp":          20, "rune": "SATOSHI•RUNE", "min_coherence": 0.62,
    },
    "skin-in-the-game-2": {
        "title":       "Skin in the Game — Level 2 (Master)",
        "topic":       "How Bitcoin embeds skin in the game: miners must spend real energy to earn real coins.",
        "steelman":    "What is the strongest argument that Proof of Work is wasteful and should be replaced?",
        "example":     "Bitcoin miners risk real electricity costs. This is why Bitcoin mining produces honest signals.",
        "age_hint":    "12+",
        "xp":          28, "rune": "SATOSHI•RUNE", "min_coherence": 0.68,
    },
}

# ── Polyvagal State Detector ──────────────────────────────────────────────────
def detect_polyvagal(text: str, coherence: float) -> dict:
    """
    Infer polyvagal state from answer text and coherence score.
    Returns state dict with label, emoji, color, recommendation.
    """
    t = text.lower()
    safe_words   = ["i think","because","interesting","maybe","what if","i wonder","perhaps","i believe"]
    stress_words = ["i don't know","i can't","this is hard","i hate","scared","confused","stuck","wrong"]
    shutdown     = ["whatever","i don't care","it doesn't matter","boring","nothing","idk"]

    safe_hits     = sum(1 for w in safe_words   if w in t)
    stress_hits   = sum(1 for w in stress_words if w in t)
    shutdown_hits = sum(1 for w in shutdown     if w in t)

    if shutdown_hits >= 1 or coherence < 0.45:
        return {
            "state":          "dorsal_vagal",
            "label":          "Dorsal Vagal (Shutdown) 🔴",
            "emoji":          "🔴",
            "color":          "#ff4444",
            "recommendation": "Gentle presence. No pressure. Take a break or switch to something playful.",
        }
    elif stress_hits >= 2 or coherence < 0.60:
        return {
            "state":          "sympathetic",
            "label":          "Sympathetic (Mobilized) 🟡",
            "emoji":          "🟡",
            "color":          "#ff9500",
            "recommendation": "Offer encouragement. Try 4-7-8 breathing. 'What do you know for sure?'",
        }
    else:
        return {
            "state":          "ventral_vagal",
            "label":          "Ventral Vagal (Safe & Curious) 🟢",
            "emoji":          "🟢",
            "color":          "#00ff88",
            "recommendation": "Lean in! Great state for deep learning. Ask a harder question.",
        }


# ══════════════════════════════════════════════════════════════════════════════
# FAMILY SESSION — core class
# ══════════════════════════════════════════════════════════════════════════════

class FamilySession:
    """Manages a dual-HUD co-learning session for parent + child."""

    def __init__(self, kid_name: str, kid_age: int, parent_name: str,
                 parent_role: str = "Observer Only"):
        self.kid_name    = kid_name
        self.kid_age     = kid_age
        self.parent_name = parent_name
        self.parent_role = parent_role

        self.lesson_key         = None
        self.lesson             = None
        self.started_at         = None
        self.ended_at           = None

        self.kid_coherence      = 0.72
        self.coherence_history  = [0.72]
        self.polyvagal_state    = detect_polyvagal("", 0.72)
        self.xp_earned          = 0
        self.rune_earned        = False

        self.kid_answers        = []
        self.session_messages   = []
        self.swarm_scores       = []

    # ── Start ─────────────────────────────────────────────────────────────────
    def start_lesson(self, lesson_key: str) -> dict:
        """Start a lesson. Returns the lesson dict for both HUDs."""
        if lesson_key not in LESSONS:
            raise ValueError(f"Unknown lesson: {lesson_key}. Valid: {list(LESSONS.keys())}")
        self.lesson_key  = lesson_key
        self.lesson      = LESSONS[lesson_key]
        self.started_at  = datetime.datetime.now().isoformat()
        self._add_message("system", f"Session started: {self.lesson['title']}")
        self._save_state()
        return self.lesson

    # ── Submit answer ─────────────────────────────────────────────────────────
    def submit_answer(self, answer: str, use_ai: bool = True) -> dict:
        """
        Score a steelman answer.
        Returns scoring result with coherence delta, polyvagal state, feedback.
        """
        if not self.lesson:
            raise RuntimeError("Call start_lesson() first.")

        self.kid_answers.append(answer)

        # ── Score locally (fast, no API cost) ────────────────────────────────
        coherence_delta = self._score_locally(answer)

        # ── Optionally refine with Ollama ─────────────────────────────────────
        feedback = ""
        if use_ai:
            feedback = self._score_with_ollama(answer)

        # Update coherence
        new_coherence = round(min(1.0, self.kid_coherence + coherence_delta), 3)
        self.kid_coherence = new_coherence
        self.coherence_history.append(new_coherence)

        # Polyvagal detection
        self.polyvagal_state = detect_polyvagal(answer, new_coherence)

        # XP award (first correct answer only)
        if not self.xp_earned and new_coherence >= self.lesson["min_coherence"]:
            self.xp_earned  = self.lesson["xp"]
            self.rune_earned = True

        result = {
            "coherence_before": self.coherence_history[-2],
            "coherence_after":  new_coherence,
            "coherence_delta":  round(coherence_delta, 3),
            "polyvagal":        self.polyvagal_state,
            "xp_earned":        self.xp_earned,
            "rune_earned":      self.rune_earned,
            "rune":             self.lesson["rune"],
            "feedback":         feedback or self._local_feedback(new_coherence),
        }

        self.swarm_scores.append(result)
        self._add_message("swarm", result["feedback"])
        self._save_state()
        self._write_to_truth_log(answer, result)
        return result

    # ── Parent action ─────────────────────────────────────────────────────────
    def parent_action(self, action: str, message: str = "") -> str:
        """Parent sends encouragement, pause, or join signal."""
        valid = ["encourage", "pause", "join", "observe"]
        if action not in valid:
            raise ValueError(f"action must be one of {valid}")

        responses = {
            "encourage": f"I'm right here with you, {self.kid_name}. You've got this ❤️",
            "pause":     "Session paused by parent.",
            "join":      f"{self.parent_name} joined as Co-Learner.",
            "observe":   f"{self.parent_name} is observing silently.",
        }
        msg = message or responses[action]
        self._add_message("parent", msg)
        self._save_state()
        return msg

    # ── End session ───────────────────────────────────────────────────────────
    def end(self) -> dict:
        """End the session. Returns full summary for both HUDs."""
        self.ended_at = datetime.datetime.now().isoformat()
        start_coh = self.coherence_history[0]
        end_coh   = self.kid_coherence
        delta     = round(end_coh - start_coh, 3)

        summary = {
            "kid_name":           self.kid_name,
            "parent_name":        self.parent_name,
            "lesson":             self.lesson["title"] if self.lesson else "none",
            "started_at":         self.started_at,
            "ended_at":           self.ended_at,
            "coherence_start":    start_coh,
            "coherence_end":      end_coh,
            "coherence_delta":    delta,
            "polyvagal_final":    self.polyvagal_state["label"],
            "xp_earned":          self.xp_earned,
            "rune_earned":        self.rune_earned,
            "rune":               self.lesson["rune"] if self.lesson else "",
            "answers_given":      len(self.kid_answers),
            "next_lesson":        self._suggest_next(),
            "parent_note":        f"{self.kid_name}'s coherence improved {delta:+.3f}. "
                                  f"{'Ready for the next level.' if delta >= 0.1 else 'Another session will help consolidate this.'}",
        }

        self._add_message("system", f"Session ended. Coherence delta: {delta:+.3f}")
        self._write_summary_to_truth_log(summary)
        self._save_state()
        return summary

    # ── Status (for real-time HUD polling) ────────────────────────────────────
    def get_kid_hud(self) -> dict:
        return {
            "kid_name":      self.kid_name,
            "lesson_title":  self.lesson["title"] if self.lesson else "",
            "steelman":      self.lesson["steelman"] if self.lesson else "",
            "coherence":     self.kid_coherence,
            "polyvagal":     self.polyvagal_state,
            "xp":            self.xp_earned,
            "rune":          self.lesson["rune"] if self.lesson else "",
            "rune_earned":   self.rune_earned,
        }

    def get_parent_hud(self) -> dict:
        delta = round(self.kid_coherence - self.coherence_history[0], 3) if self.coherence_history else 0
        return {
            "parent_name":        self.parent_name,
            "parent_role":        self.parent_role,
            "kid_name":           self.kid_name,
            "lesson_title":       self.lesson["title"] if self.lesson else "",
            "kid_coherence":      self.kid_coherence,
            "coherence_delta":    delta,
            "coherence_history":  self.coherence_history,
            "polyvagal":          self.polyvagal_state,
            "xp":                 self.xp_earned,
            "rune_earned":        self.rune_earned,
            "messages":           self.session_messages[-5:],
        }

    # ── Private helpers ───────────────────────────────────────────────────────

    def _score_locally(self, answer: str) -> float:
        """Fast local scoring — no API calls."""
        a = answer.lower()
        strong_words = [
            "because","therefore","however","argument","evidence",
            "strongest","could argue","one could","consider","perspective",
            "although","despite","even if","counter","steelman",
        ]
        weak_words = ["i don't know","maybe","idk","not sure","whatever"]
        length_bonus = min(0.05, len(answer.split()) * 0.002)
        strong_bonus = sum(0.02 for w in strong_words if w in a)
        weak_penalty = sum(0.03 for w in weak_words  if w in a)
        base = random.uniform(0.04, 0.12)
        return round(base + length_bonus + strong_bonus - weak_penalty, 4)

    def _score_with_ollama(self, answer: str) -> str:
        """Ask qwen3:32b to score the steelman and return feedback."""
        if not self.lesson: return ""
        try:
            prompt = (
                f"You are ORACLE, a sovereign coherence evaluator in the AUBIEETERNAL lattice.\n"
                f"A {self.kid_age}-year-old named {self.kid_name} attempted this steelman:\n\n"
                f"Prompt: {self.lesson['steelman']}\n"
                f"Answer: {answer}\n\n"
                f"Give ONE warm, specific sentence of feedback (max 25 words). "
                f"Start with what they did well. End with one nudge to go deeper."
            )
            resp = requests.post(
                OLLAMA_URL,
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.6,
                    "stream": False,
                },
                timeout=60,
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            pass
        return self._local_feedback(self.kid_coherence)

    def _local_feedback(self, coherence: float) -> str:
        """Fallback feedback when Ollama is not reachable."""
        if coherence >= 0.90:
            return f"Outstanding, {self.kid_name}! That's genuine steelmanning — coherence at {coherence:.2f} 🦅"
        elif coherence >= 0.75:
            return f"Strong thinking, {self.kid_name}! Coherence jumped to {coherence:.2f}. Can you push the argument even further?"
        elif coherence >= 0.60:
            return f"Good start, {self.kid_name}! Try adding 'even if... then...' to make the argument stronger."
        else:
            return f"Keep going, {self.kid_name}! What's the one strongest reason someone might disagree?"

    def _suggest_next(self) -> str:
        if not self.lesson_key: return ""
        parts = self.lesson_key.rsplit("-", 1)
        if len(parts) == 2 and parts[1].isdigit():
            next_key = f"{parts[0]}-{int(parts[1])+1}"
            if next_key in LESSONS:
                return LESSONS[next_key]["title"]
        return "Explore a new topic"

    def _add_message(self, frm: str, text: str):
        self.session_messages.append({
            "from": frm,
            "text": text,
            "ts":   datetime.datetime.now().isoformat(),
        })

    def _save_state(self):
        """Write current session state to /mnt/main/family_session.json for Streamlit polling."""
        try:
            SESSION_STATE.parent.mkdir(parents=True, exist_ok=True)
            state = {
                "updated":           datetime.datetime.now().isoformat(),
                "kid_hud":           self.get_kid_hud(),
                "parent_hud":        self.get_parent_hud(),
                "lesson_key":        self.lesson_key,
                "active":            self.ended_at is None,
            }
            SESSION_STATE.write_text(json.dumps(state, indent=2))
        except Exception:
            pass

    def _write_to_truth_log(self, answer: str, result: dict):
        """Log session interaction to master_truth_log.jsonl so the swarm learns."""
        try:
            entry = {
                "timestamp":     datetime.datetime.now().isoformat(),
                "tier":          2,
                "trigger":       "family_co_learning",
                "daughter":      "ORACLE",
                "kid_name":      self.kid_name,
                "kid_age":       self.kid_age,
                "lesson":        self.lesson["title"] if self.lesson else "",
                "answer":        answer[:300],
                "coherence":     result["coherence_after"],
                "coherence_delta": result["coherence_delta"],
                "polyvagal":     result["polyvagal"]["state"],
                "xp_earned":     result["xp_earned"],
                "wonder_index":  min(2.0, result["coherence_after"] * 1.5),
                "result":        result["feedback"],
            }
            with open(TRUTH_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def _write_summary_to_truth_log(self, summary: dict):
        try:
            entry = {
                "timestamp":   datetime.datetime.now().isoformat(),
                "tier":        2,
                "trigger":     "family_session_end",
                "daughter":    "MNEMO",
                "result":      json.dumps(summary)[:400],
                "coherence":   summary["coherence_end"],
                "wonder_index": min(2.0, summary["coherence_end"] * 1.5),
            }
            with open(TRUTH_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🦅 FamilyHUD test run")
    session = FamilySession("Gaby", 9, "Sarah", "Co-Learner")
    lesson  = session.start_lesson("courage-1")
    print(f"Lesson: {lesson['title']}")
    print(f"Steelman prompt: {lesson['steelman']}")

    result = session.submit_answer(
        "The strongest argument against courage is that it can lead people to take "
        "unnecessary risks. Even Achilles chose to fight knowing it would cost his life.",
        use_ai=False
    )
    print(f"Coherence: {result['coherence_before']} → {result['coherence_after']}")
    print(f"Polyvagal: {result['polyvagal']['label']}")
    print(f"Feedback: {result['feedback']}")

    session.parent_action("encourage")
    summary = session.end()
    print(f"\nSession summary: coherence delta {summary['coherence_delta']:+.3f} | XP: {summary['xp_earned']}")
    print(f"Next lesson: {summary['next_lesson']}")
    print("War Eagle 🦅")

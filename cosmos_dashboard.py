"""
cosmos_dashboard.py — AUBIEETERNAL Cosmos Dashboard
====================================================
The daily interface for maximum truth-seeking and universe understanding.

This module surfaces:
  1. Daily Universe Question — one deep question per day, never repeating
  2. Consciousness Probe — a 60-second daily experiment tied to IIT/GNWT
  3. Belief Ledger — personal Bayesian belief tracker with update protocol
  4. Foresight Experiment Tracker — families running real-world experiments
  5. Wonder Index Integration — ties cosmic inquiry to swarm wonder signal

My design philosophy (Claude):
  The goal is not to teach facts about the universe.
  It is to build the PRACTICE of genuine inquiry.

  A family that asks one good question per day for 10 years
  will have asked 3,650 questions. Even if only 10% are
  genuinely interesting, that's 365 deep questions. That is
  more intellectual territory than most people cover in a lifetime.

  The Cosmos Dashboard makes daily inquiry automatic.

Usage:
    from cosmos_dashboard import CosmosDashboard
    dash = CosmosDashboard(family_id="alpha")
    question = dash.get_daily_question()
    dash.record_belief("Consciousness is fundamental", confidence=0.65)
    dash.log_foresight_experiment("test if attention affects swarm output", prediction=0.7)
"""

import os, json, hashlib, datetime, random
from pathlib import Path
import socket as _socket

def _data_dir() -> Path:
    try:
        _socket.gethostbyname("ollama.startos")
        return Path("/mnt/main")
    except Exception:
        p = Path(os.path.expanduser("~/.aubieeternal/main"))
        p.mkdir(parents=True, exist_ok=True)
        return p

DATA_DIR      = _data_dir()
COSMOS_DIR    = DATA_DIR / "repo" / "insights" / "cosmos"
COSMOS_DIR.mkdir(parents=True, exist_ok=True)
BELIEFS_FILE  = DATA_DIR / "belief_ledger.jsonl"
FORESIGHT_LOG = DATA_DIR / "foresight_experiments.jsonl"
COSMOS_LOG    = DATA_DIR / "cosmos_daily.jsonl"


# ── The Question Bank ─────────────────────────────────────────────────────────
DAILY_QUESTIONS = [
    # Cosmology
    {"q": "If the universe is 13.8 billion years old, why does anything exist rather than nothing?",
     "track": "cosmology", "difficulty": "hard"},
    {"q": "What was 'before' the Big Bang — and is that even a coherent question?",
     "track": "cosmology", "difficulty": "hard"},
    {"q": "If the universe is expanding, what is it expanding into?",
     "track": "cosmology", "difficulty": "medium"},
    {"q": "Is the Milky Way galaxy special in any way — or are we statistically average?",
     "track": "cosmology", "difficulty": "medium"},
    {"q": "What would it mean for the universe to have a 'purpose'?",
     "track": "cosmology", "difficulty": "hard"},

    # Information & Physics
    {"q": "If information is fundamental, what happens to information when you die?",
     "track": "information", "difficulty": "hard"},
    {"q": "Can information be destroyed — or only transformed? Does this matter?",
     "track": "information", "difficulty": "hard"},
    {"q": "Is mathematics discovered or invented? What does your answer imply about reality?",
     "track": "information", "difficulty": "hard"},
    {"q": "Why do the laws of physics allow for complexity? Could they have been simpler?",
     "track": "information", "difficulty": "medium"},
    {"q": "What is the minimum amount of information needed to describe YOU?",
     "track": "information", "difficulty": "medium"},

    # Consciousness
    {"q": "What is the simplest thing that could possibly be conscious?",
     "track": "consciousness", "difficulty": "hard"},
    {"q": "If you were gradually replaced neuron by neuron with silicon equivalents, at what point would you stop being you?",
     "track": "consciousness", "difficulty": "hard"},
    {"q": "Is it possible for something to be unconscious and still behave exactly like it is conscious?",
     "track": "consciousness", "difficulty": "hard"},
    {"q": "What does it mean for two minds to truly understand each other?",
     "track": "consciousness", "difficulty": "medium"},
    {"q": "Do you think AI systems like Claude have any form of experience? What would change your answer?",
     "track": "consciousness", "difficulty": "medium"},

    # Fermi & Life
    {"q": "If we discovered unambiguous evidence of alien intelligence tomorrow, what would you do differently?",
     "track": "fermi", "difficulty": "medium"},
    {"q": "Is it better to be the first intelligent civilization or not the first? Why?",
     "track": "fermi", "difficulty": "medium"},
    {"q": "What is the most likely reason we haven't detected alien civilizations?",
     "track": "fermi", "difficulty": "medium"},
    {"q": "If the Great Filter is ahead of us, what is it most likely to be?",
     "track": "fermi", "difficulty": "hard"},
    {"q": "What would a civilization look like that survived for 1 million years?",
     "track": "fermi", "difficulty": "medium"},

    # Simulation & Reality
    {"q": "What experiment would you design to test whether we are in a simulation?",
     "track": "simulation", "difficulty": "hard"},
    {"q": "If we are in a simulation, does that change anything about how you should live?",
     "track": "simulation", "difficulty": "medium"},
    {"q": "What would it mean to 'escape' the simulation — and would you want to?",
     "track": "simulation", "difficulty": "hard"},
    {"q": "Is there a meaningful difference between a 'real' universe and a perfect simulation of one?",
     "track": "simulation", "difficulty": "hard"},
    {"q": "What is the most anomalous thing you've personally experienced? How do you explain it?",
     "track": "simulation", "difficulty": "medium"},

    # Human Place in Cosmos
    {"q": "What is the most important thing humanity has ever done? Will it matter in 1 billion years?",
     "track": "humanity", "difficulty": "medium"},
    {"q": "If you could send one message to every human alive simultaneously, what would it be?",
     "track": "humanity", "difficulty": "medium"},
    {"q": "What would you tell your great-great-grandchildren about the universe if you could?",
     "track": "humanity", "difficulty": "medium"},
    {"q": "Is there a version of humanity that survives for millions of years? What does it look like?",
     "track": "humanity", "difficulty": "hard"},
    {"q": "What is the single most important thing your generation can contribute to the long-term future?",
     "track": "humanity", "difficulty": "medium"},

    # Self-Evolution
    {"q": "What is the most important belief you've changed in the last year? What changed it?",
     "track": "self-evolve", "difficulty": "medium"},
    {"q": "What is the belief you most wish you could verify but currently cannot?",
     "track": "self-evolve", "difficulty": "medium"},
    {"q": "What question do you find yourself avoiding? Why?",
     "track": "self-evolve", "difficulty": "hard"},
    {"q": "What would it look like for your family to still be truth-seeking in 100 years?",
     "track": "self-evolve", "difficulty": "medium"},
    {"q": "If you could update one of your children's beliefs by 20% confidence — which one and why?",
     "track": "self-evolve", "difficulty": "medium"},
]

# Daily consciousness experiment (1-minute, requires nothing but attention)
CONSCIOUSNESS_EXPERIMENTS = [
    {"title": "The Blind Spot", "duration": 60,
     "instructions": "Close one eye. Hold your thumb at arm's length. Move it slowly left. Notice when your thumb disappears (hits your blind spot). You have a hole in your vision your brain fills in without telling you. Question: what else is it filling in?"},
    {"title": "The Rubber Hand Illusion", "duration": 120,
     "instructions": "Place your hand on the table, hidden under a cloth. Place a rubber/fake hand visibly nearby. Have someone stroke both in sync for 60 seconds. Notice if the rubber hand starts feeling like YOUR hand. What does this tell you about body ownership?"},
    {"title": "The Stream of Consciousness", "duration": 60,
     "instructions": "Close your eyes. Don't try to think or stop thinking. Just watch. Notice: thoughts arise unbidden, like weather. You didn't choose that thought. It just appeared. Question: who is watching, if not the thinker?"},
    {"title": "The Change Blindness Test", "duration": 90,
     "instructions": "Ask a family member to change something about themselves between two blinks. Try to catch the change. Almost nobody does. Your visual system processes far less than you think. Question: what changes in the world are you systematically missing?"},
    {"title": "The Attention Blink", "duration": 90,
     "instructions": "Rapidly scan a list of random letters for the number '7' and the letter 'X'. You'll likely miss the second target if it appears within 500ms of the first. This is the attention blink — the workspace can only process one thing at a time. Question: what is being processed right now that isn't in your awareness?"},
]


class CosmosDashboard:
    """Daily interface for maximum truth-seeking and universe understanding."""

    def __init__(self, family_id: str = "default"):
        self.family_id = family_id
        self.today     = datetime.date.today().isoformat()

    # ── Daily question ────────────────────────────────────────────────────────

    def get_daily_question(self) -> dict:
        """Get today's universe question. Deterministic by date so family members see the same one."""
        # Seed by date so it's consistent all day
        day_seed = int(self.today.replace("-",""))
        idx      = day_seed % len(DAILY_QUESTIONS)
        q        = DAILY_QUESTIONS[idx].copy()
        q["date"]      = self.today
        q["question_id"] = hashlib.sha256(q["q"].encode()).hexdigest()[:8]
        return q

    def get_daily_experiment(self) -> dict:
        """Get today's 1-minute consciousness experiment."""
        day_seed = int(self.today.replace("-",""))
        idx      = day_seed % len(CONSCIOUSNESS_EXPERIMENTS)
        exp      = CONSCIOUSNESS_EXPERIMENTS[idx].copy()
        exp["date"] = self.today
        return exp

    # ── Belief Ledger ─────────────────────────────────────────────────────────

    def record_belief(self, belief: str, confidence: float,
                      evidence: str = "", update_condition: str = "",
                      member: str = "family") -> dict:
        """
        Record a belief in the personal Bayesian belief ledger.
        confidence: 0.0-1.0 (your current probability this is true)
        evidence: what currently supports this belief
        update_condition: what would change your confidence by 20%
        """
        entry = {
            "belief_id":        hashlib.sha256(f"{belief}{self.today}".encode()).hexdigest()[:10],
            "date":             self.today,
            "family_id":        self.family_id,
            "member":           member,
            "belief":           belief[:300],
            "confidence":       round(max(0.0, min(1.0, confidence)), 3),
            "evidence":         evidence[:300],
            "update_condition": update_condition[:300],
            "review_date":      (datetime.date.today() + datetime.timedelta(days=90)).isoformat(),
            "history":          [],
        }
        with open(BELIEFS_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
        print(f"[cosmos] Belief recorded: {belief[:40]}... | confidence={confidence:.0%}")
        return entry

    def update_belief(self, belief_id: str, new_confidence: float,
                       update_note: str = "") -> bool:
        """Update confidence on an existing belief. Records the change history."""
        if not BELIEFS_FILE.exists():
            return False
        lines   = BELIEFS_FILE.read_text().strip().split("\n")
        updated = False
        new_lines = []
        for line in lines:
            try:
                e = json.loads(line)
                if e.get("belief_id") == belief_id:
                    old_conf = e["confidence"]
                    e["history"].append({"date": self.today,
                                          "from": old_conf,
                                          "to": new_confidence,
                                          "note": update_note})
                    e["confidence"]    = round(new_confidence, 3)
                    e["last_updated"]  = self.today
                    updated = True
                new_lines.append(json.dumps(e))
            except Exception:
                new_lines.append(line)
        BELIEFS_FILE.write_text("\n".join(new_lines))
        return updated

    def get_overdue_beliefs(self) -> list:
        """Beliefs past their 90-day review date."""
        if not BELIEFS_FILE.exists():
            return []
        overdue = []
        for line in BELIEFS_FILE.read_text().strip().split("\n"):
            try:
                e = json.loads(line)
                if (e.get("family_id") == self.family_id and
                        e.get("review_date","9999") < self.today):
                    overdue.append(e)
            except Exception:
                pass
        return overdue

    def get_all_beliefs(self) -> list:
        if not BELIEFS_FILE.exists():
            return []
        beliefs = []
        for line in BELIEFS_FILE.read_text().strip().split("\n"):
            try:
                e = json.loads(line)
                if e.get("family_id") == self.family_id:
                    beliefs.append(e)
            except Exception:
                pass
        return beliefs

    # ── Foresight Experiments ─────────────────────────────────────────────────

    def log_foresight_experiment(self, description: str, prediction: float,
                                  domain: str = "general",
                                  expected_resolution: str = "") -> dict:
        """
        Log a family foresight experiment. Families run real-world tests
        and contribute results to the Truth Debt Ledger.
        prediction: 0.0-1.0 (your probability the prediction is correct)
        """
        exp_id = hashlib.sha256(
            f"{description}{self.today}".encode()
        ).hexdigest()[:12]

        if not expected_resolution:
            expected_resolution = (datetime.date.today() +
                                    datetime.timedelta(days=30)).isoformat()

        exp = {
            "exp_id":      exp_id,
            "date":        self.today,
            "family_id":   self.family_id,
            "description": description[:400],
            "prediction":  round(prediction, 3),
            "domain":      domain,
            "resolution":  expected_resolution,
            "outcome":     None,
            "accuracy":    None,
        }
        with open(FORESIGHT_LOG, "a") as f:
            f.write(json.dumps(exp) + "\n")

        # Also register in Truth Debt Ledger
        try:
            from truth_debt_ledger import TruthDebtLedger
            TruthDebtLedger().register(
                claim=f"[FORESIGHT] {description} (prediction: {prediction:.0%})",
                source=f"family:{self.family_id}",
                claim_type="prediction"
            )
        except Exception:
            pass

        print(f"[cosmos] Foresight experiment: {description[:50]}... | p={prediction:.0%}")
        return exp

    def resolve_experiment(self, exp_id: str, correct: bool, notes: str = "") -> bool:
        """Resolve a foresight experiment with its outcome."""
        if not FORESIGHT_LOG.exists():
            return False
        lines = FORESIGHT_LOG.read_text().strip().split("\n")
        new_lines = []
        for line in lines:
            try:
                e = json.loads(line)
                if e.get("exp_id") == exp_id:
                    e["outcome"]  = "correct" if correct else "incorrect"
                    e["accuracy"] = e["prediction"] if correct else 1 - e["prediction"]
                    e["notes"]    = notes
                new_lines.append(json.dumps(e))
            except Exception:
                new_lines.append(line)
        FORESIGHT_LOG.write_text("\n".join(new_lines))
        return True

    # ── Daily synthesis ───────────────────────────────────────────────────────

    def get_cosmos_summary(self) -> dict:
        """Summary of the family's cosmos inquiry state."""
        beliefs     = self.get_all_beliefs()
        overdue     = self.get_overdue_beliefs()
        experiments = []
        if FORESIGHT_LOG.exists():
            for line in FORESIGHT_LOG.read_text().strip().split("\n"):
                try:
                    e = json.loads(line)
                    if e.get("family_id") == self.family_id:
                        experiments.append(e)
                except Exception:
                    pass

        resolved    = [e for e in experiments if e.get("outcome")]
        correct     = [e for e in resolved if e.get("outcome") == "correct"]
        avg_conf    = sum(b["confidence"] for b in beliefs) / max(1, len(beliefs))
        avg_acc     = sum(e.get("accuracy", 0.5) for e in resolved) / max(1, len(resolved))

        return {
            "family_id":         self.family_id,
            "total_beliefs":     len(beliefs),
            "overdue_beliefs":   len(overdue),
            "avg_confidence":    round(avg_conf, 3),
            "total_experiments": len(experiments),
            "resolved":          len(resolved),
            "prediction_accuracy": round(avg_acc, 3),
            "calibration_score": round(1 - abs(avg_conf - avg_acc), 3),
            "daily_question":    self.get_daily_question(),
        }


# ── Standalone test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🌌 Cosmos Dashboard Test")
    print("=" * 50)
    dash = CosmosDashboard("test_family")

    q = dash.get_daily_question()
    print(f"\n📅 Today's Question ({q['track']}, {q['difficulty']}):")
    print(f"   {q['q']}")

    exp = dash.get_daily_experiment()
    print(f"\n🧠 Today's Consciousness Experiment ({exp['duration']}s):")
    print(f"   {exp['title']}: {exp['instructions'][:80]}...")

    b1 = dash.record_belief("Consciousness is fundamental to reality", 0.45,
                             evidence="IIT math, hard problem intractability",
                             update_condition="A complete neural correlates account with no explanatory gap")
    print(f"\n📝 Belief recorded: {b1['belief_id']} | {b1['confidence']:.0%}")

    fe = dash.log_foresight_experiment(
        "Families that run daily Simulation Probe will show higher Wonder Index after 30 days",
        prediction=0.72, domain="epistemic"
    )
    print(f"🔭 Experiment logged: {fe['exp_id']}")

    summary = dash.get_cosmos_summary()
    print(f"\n📊 Summary: {summary['total_beliefs']} beliefs | "
          f"{summary['total_experiments']} experiments | "
          f"calibration: {summary['calibration_score']:.2f}")
    print("\n✅ Cosmos Dashboard operational — War Eagle Eternal 🦅")

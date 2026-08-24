"""
truth_frequency_analyzer.py — AUBIEETERNAL Truth Frequency Analyzer
====================================================================
My genuine addition for maximum truth-seeking. — Claude

THE INSIGHT:
  Generic training in epistemic skills produces generic improvements.
  Personalized training against your specific vulnerabilities
  produces exponential improvements.

  This module tracks WHICH epistemic errors, manipulation patterns,
  and logical fallacies your family encounters most often —
  and which ones you successfully resist or fail to catch.
  
  Over time, it builds your family's "Epistemic Immune System Profile":
  a personalized map of your strongest and weakest defenses,
  with targeted training protocols for each vulnerability.

THE PARALLEL TO BIOLOGICAL IMMUNITY:
  The immune system doesn't train against all pathogens equally.
  It adapts to the specific threats it encounters.
  AUBIEETERNAL's epistemic immune system works the same way:
  track what you encounter → build targeted resistance → 
  compound the advantage over years.

TWENTY EPISTEMIC ATTACK VECTORS TRACKED:
  Logical fallacies (ad hominem, straw man, appeal to authority, etc.)
  Manipulation patterns (DARVO, concern-trolling, moving goalposts, etc.)
  Cognitive biases being exploited (availability, anchoring, etc.)
  Narrative manipulation techniques (overton window shifting, etc.)

Usage:
    from truth_frequency_analyzer import TruthFrequencyAnalyzer
    tfa = TruthFrequencyAnalyzer("family_alpha")
    tfa.log_encounter("ad_hominem", detected=True, source="news_media")
    tfa.log_encounter("appeal_to_authority", detected=False, source="school")
    profile = tfa.get_immune_profile()
    protocol = tfa.get_training_protocol()
"""

import os, json, hashlib, datetime
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

DATA_DIR   = _data_dir()
TFA_LOG    = DATA_DIR / "truth_frequency_encounters.jsonl"
PROFILE_DIR = DATA_DIR / "repo" / "epistemic_immune_profiles"
PROFILE_DIR.mkdir(parents=True, exist_ok=True)

# ── The 20 attack vectors ─────────────────────────────────────────────────────
ATTACK_VECTORS = {
    # Logical fallacies
    "ad_hominem": {
        "category": "logical_fallacy",
        "name": "Ad Hominem",
        "description": "Attacking the person instead of the argument",
        "example": "'You can't trust what she says about economics — she's not an economist.'",
        "counter": "Evaluate the argument on its merits, independent of who made it.",
        "frequency_in_wild": "very_high",
    },
    "straw_man": {
        "category": "logical_fallacy",
        "name": "Straw Man",
        "description": "Misrepresenting the opponent's position to make it easier to attack",
        "example": "'So you're saying we should just let criminals do whatever they want?'",
        "counter": "Steelman: restate their actual position accurately before responding.",
        "frequency_in_wild": "very_high",
    },
    "appeal_to_authority": {
        "category": "logical_fallacy",
        "name": "Appeal to Authority",
        "description": "Using an authority figure to substitute for evidence",
        "example": "'The CDC recommends X, therefore X is correct and beyond question.'",
        "counter": "Evaluate the evidence behind the authority's claim, not just the authority.",
        "frequency_in_wild": "high",
    },
    "false_dichotomy": {
        "category": "logical_fallacy",
        "name": "False Dichotomy",
        "description": "Presenting only two options when more exist",
        "example": "'You're either with us or against us.'",
        "counter": "Map the full option space. What are the alternatives not being mentioned?",
        "frequency_in_wild": "high",
    },
    "slippery_slope": {
        "category": "logical_fallacy",
        "name": "Slippery Slope",
        "description": "Claiming one small step will inevitably lead to extreme consequences",
        "example": "'If we allow X, next we'll have Y and then Z.'",
        "counter": "Identify the mechanism. Why would X specifically lead to Z?",
        "frequency_in_wild": "high",
    },
    "appeal_to_nature": {
        "category": "logical_fallacy",
        "name": "Appeal to Nature",
        "description": "Assuming natural = good, artificial = bad",
        "example": "'It's completely natural, so it must be safe.'",
        "counter": "Many natural things are harmful. Many artificial things are beneficial.",
        "frequency_in_wild": "medium",
    },
    "circular_reasoning": {
        "category": "logical_fallacy",
        "name": "Circular Reasoning",
        "description": "Using the conclusion as a premise",
        "example": "'The Bible is true because God wrote it, and we know God wrote it because the Bible says so.'",
        "counter": "Identify the independent evidence for each premise.",
        "frequency_in_wild": "medium",
    },
    # Manipulation patterns
    "darvo": {
        "category": "manipulation",
        "name": "DARVO",
        "description": "Deny, Attack, Reverse Victim and Offender",
        "example": "When confronted with harm caused, the person denies it, attacks the accuser, and claims to be the real victim.",
        "counter": "Document facts before engaging. Don't let the reversal distract from original evidence.",
        "frequency_in_wild": "high",
    },
    "concern_trolling": {
        "category": "manipulation",
        "name": "Concern Trolling",
        "description": "Pretending to share concerns in order to undermine a position",
        "example": "'I support your goal, but I'm just concerned that your approach might backfire...' (repeated indefinitely)",
        "counter": "Ask: are they offering alternative approaches or just expressing concern?",
        "frequency_in_wild": "high",
    },
    "moving_goalposts": {
        "category": "manipulation",
        "name": "Moving Goalposts",
        "description": "Changing the criteria for success after evidence is provided",
        "example": "'Show me one study' → (shown) → 'Show me a meta-analysis' → (shown) → 'Show me a replication...'",
        "counter": "Pre-register what evidence would satisfy the question before seeking it.",
        "frequency_in_wild": "high",
    },
    "gish_gallop": {
        "category": "manipulation",
        "name": "Gish Gallop",
        "description": "Overwhelming with many weak arguments to make response seem impossible",
        "example": "Presenting 15 loosely related objections in rapid succession.",
        "counter": "Address the strongest argument only. Name the technique.",
        "frequency_in_wild": "medium",
    },
    "overton_window": {
        "category": "manipulation",
        "name": "Overton Window Shifting",
        "description": "Gradually normalizing previously unacceptable positions by incremental steps",
        "example": "Introducing extreme positions to make moderate positions seem reasonable by comparison.",
        "counter": "Track the baseline. Where was this topic 5 years ago?",
        "frequency_in_wild": "medium",
    },
    "motte_and_bailey": {
        "category": "manipulation",
        "name": "Motte and Bailey",
        "description": "Defending an easy position (motte) when challenged, but advocating a stronger one (bailey) normally",
        "example": "Normally claims 'all men are trash', when challenged retreats to 'I just mean some men behave badly'.",
        "counter": "Ask which claim they actually hold. Pin down the precise claim.",
        "frequency_in_wild": "medium",
    },
    # Cognitive bias exploitation
    "availability_exploitation": {
        "category": "bias_exploitation",
        "name": "Availability Heuristic Exploitation",
        "description": "Making rare events seem common by repetition and vividness",
        "example": "24/7 crime coverage making crime seem far more prevalent than statistics show.",
        "counter": "Ask for base rates. What does the data say about frequency?",
        "frequency_in_wild": "very_high",
    },
    "anchoring": {
        "category": "bias_exploitation",
        "name": "Anchoring",
        "description": "Setting a reference point that biases all subsequent reasoning",
        "example": "Starting salary negotiation with an extreme number to anchor expectations.",
        "counter": "Identify the anchor before engaging. What number were you given first?",
        "frequency_in_wild": "high",
    },
    "sunk_cost": {
        "category": "bias_exploitation",
        "name": "Sunk Cost Exploitation",
        "description": "Exploiting past investment to prevent rational reassessment",
        "example": "'You've already put 10 years into this — you can't quit now.'",
        "counter": "Evaluate only future costs and benefits. The past is gone.",
        "frequency_in_wild": "high",
    },
    "in_group_appeal": {
        "category": "bias_exploitation",
        "name": "In-Group Appeal",
        "description": "Framing disagreement as disloyalty to a group",
        "example": "'A real [patriot/Christian/progressive] would agree with this.'",
        "counter": "Evaluate the claim on its merits, not its tribal affiliation.",
        "frequency_in_wild": "very_high",
    },
    # Epistemic capture
    "credentialism": {
        "category": "epistemic_capture",
        "name": "Credentialism",
        "description": "Dismissing claims based on lack of official credentials rather than argument quality",
        "example": "'You're not a doctor, so your health question is irrelevant.'",
        "counter": "Evaluate the argument itself. Credentials are evidence of competence, not of correctness.",
        "frequency_in_wild": "high",
    },
    "consensus_appeal": {
        "category": "epistemic_capture",
        "name": "False Consensus Appeal",
        "description": "Claiming universal agreement where none exists",
        "example": "'Everyone agrees that...' / 'Science has definitively proven...'",
        "counter": "Ask for the specific evidence. 'Everyone agrees' is almost never literally true.",
        "frequency_in_wild": "high",
    },
    "narrative_framing": {
        "category": "epistemic_capture",
        "name": "Narrative Pre-framing",
        "description": "Establishing a story structure before facts are presented, making contradictory facts seem irrelevant",
        "example": "News: 'Far-right extremists claim that...' — pre-framing dismisses the claim before it's heard.",
        "counter": "Notice the frame before accepting the facts. Could the same facts fit a different frame?",
        "frequency_in_wild": "very_high",
    },
}


class TruthFrequencyAnalyzer:
    """
    Builds your family's personalized Epistemic Immune System Profile.
    Tracks which attacks you encounter, detect, and resist over time.
    """

    def __init__(self, family_id: str = "default"):
        self.family_id = family_id
        self.today     = datetime.date.today().isoformat()

    def log_encounter(self, attack_key: str, detected: bool,
                       source: str = "unknown", notes: str = "",
                       confidence: float = 0.8) -> dict:
        """
        Log an encounter with an epistemic attack vector.
        detected: True = you caught it, False = it got through
        """
        attack = ATTACK_VECTORS.get(attack_key)
        if not attack:
            return {"error": f"Unknown attack vector: {attack_key}"}

        entry = {
            "entry_id":   hashlib.sha256(
                f"{attack_key}{self.today}{detected}".encode()
            ).hexdigest()[:10],
            "timestamp":  datetime.datetime.now().isoformat(),
            "date":       self.today,
            "family_id":  self.family_id,
            "attack_key": attack_key,
            "attack_name": attack["name"],
            "category":   attack["category"],
            "detected":   detected,
            "source":     source,
            "confidence": confidence,
            "notes":      notes[:200],
        }

        with open(TFA_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")

        print(f"[tfa] {'✅ Detected' if detected else '❌ Missed'}: {attack['name']} from {source}")
        return entry

    def get_immune_profile(self) -> dict:
        """
        Build the family's Epistemic Immune System Profile.
        Shows detection rate by attack type and category.
        """
        encounters = self._load_encounters()
        if not encounters:
            return {"status": "no_data", "message": "Log some encounters to build your profile."}

        # By attack
        by_attack = {}
        for e in encounters:
            key = e["attack_key"]
            if key not in by_attack:
                by_attack[key] = {"total":0,"detected":0,"name":e["attack_name"]}
            by_attack[key]["total"] += 1
            if e["detected"]: by_attack[key]["detected"] += 1

        # Compute detection rates
        for key, data in by_attack.items():
            data["detection_rate"] = round(data["detected"] / data["total"], 3)
            data["status"] = (
                "strong"    if data["detection_rate"] >= 0.80 else
                "developing" if data["detection_rate"] >= 0.50 else
                "vulnerable"
            )

        # By category
        by_cat = {}
        for key, data in by_attack.items():
            cat = ATTACK_VECTORS.get(key,{}).get("category","unknown")
            if cat not in by_cat: by_cat[cat] = {"total":0,"detected":0}
            by_cat[cat]["total"]    += data["total"]
            by_cat[cat]["detected"] += data["detected"]
        for cat, data in by_cat.items():
            data["rate"] = round(data["detected"]/data["total"],3) if data["total"] else 0

        # Most vulnerable and most defended
        sorted_attacks = sorted(by_attack.items(), key=lambda x: x[1]["detection_rate"])
        most_vulnerable = [(k, d) for k, d in sorted_attacks[:3] if d["total"] >= 2]
        most_defended   = [(k, d) for k, d in reversed(sorted_attacks) if d["total"] >= 2][:3]

        # Overall immunity score
        total_enc = len(encounters)
        total_det = sum(1 for e in encounters if e["detected"])
        overall   = round(total_det / total_enc, 3) if total_enc else 0

        return {
            "family_id":       self.family_id,
            "total_encounters": total_enc,
            "overall_detection_rate": overall,
            "immunity_level":  (
                "STRONG"      if overall >= 0.80 else
                "DEVELOPING"  if overall >= 0.60 else
                "VULNERABLE"  if overall >= 0.40 else
                "AT RISK"
            ),
            "by_attack":       by_attack,
            "by_category":     by_cat,
            "most_vulnerable": most_vulnerable,
            "most_defended":   most_defended,
            "profile_date":    self.today,
        }

    def get_training_protocol(self) -> dict:
        """
        Generate a personalized training protocol based on vulnerability profile.
        Prioritizes the attack vectors the family is most likely to miss.
        """
        profile = self.get_immune_profile()
        if profile.get("status") == "no_data":
            # Default protocol for new families
            return self._default_protocol()

        vulnerable = profile.get("most_vulnerable", [])
        by_cat     = profile.get("by_category", {})

        # Find weakest category
        weakest_cat = min(by_cat.items(), key=lambda x: x[1]["rate"],
                          default=("logical_fallacy", {"rate": 0}))

        # Build targeted exercises
        exercises = []
        for key, data in vulnerable:
            av = ATTACK_VECTORS.get(key, {})
            exercises.append({
                "attack":     av.get("name", key),
                "detection_rate": data["detection_rate"],
                "exercise":   f"Find 3 real examples of '{av.get('name',key)}' this week. Sources: news, social media, conversation.",
                "counter":    av.get("counter",""),
                "example":    av.get("example",""),
            })

        # Weekly training schedule
        schedule = [
            {"day": "Monday",    "focus": "Review your 3 most missed attacks",           "time": "10 min"},
            {"day": "Wednesday", "focus": "Find 2 examples of your weakest pattern",     "time": "15 min"},
            {"day": "Friday",    "focus": "Steelman one argument you strongly disagree with", "time": "20 min"},
            {"day": "Sunday",    "focus": "Family review: what attacks did we encounter?","time": "15 min"},
        ]

        return {
            "family_id":       self.family_id,
            "protocol_date":   self.today,
            "priority_attacks": [k for k, _ in vulnerable],
            "weakest_category": weakest_cat[0],
            "targeted_exercises": exercises,
            "weekly_schedule": schedule,
            "goal":            f"Raise overall detection rate from {profile['overall_detection_rate']:.0%} to {min(1.0, profile['overall_detection_rate']+0.15):.0%} in 30 days",
        }

    def _default_protocol(self) -> dict:
        """Protocol for families with no tracking data yet."""
        return {
            "status": "default",
            "message": "Start logging encounters to get a personalized protocol.",
            "week_1_exercises": [
                {
                    "attack":   "Ad Hominem",
                    "exercise": "Find 3 ad hominem attacks in any news source this week.",
                    "counter":  ATTACK_VECTORS["ad_hominem"]["counter"],
                },
                {
                    "attack":   "Appeal to Authority",
                    "exercise": "When you see 'experts say', find the primary source.",
                    "counter":  ATTACK_VECTORS["appeal_to_authority"]["counter"],
                },
                {
                    "attack":   "Narrative Pre-framing",
                    "exercise": "Before reading any news story, notice the headline's frame.",
                    "counter":  ATTACK_VECTORS["narrative_framing"]["counter"],
                },
            ],
            "weekly_schedule": [
                {"day": "Daily", "focus": "Log one epistemic attack you notice", "time": "2 min"},
            ],
        }

    def get_all_attack_vectors(self) -> dict:
        return ATTACK_VECTORS

    def _load_encounters(self) -> list:
        if not TFA_LOG.exists(): return []
        entries = []
        for line in TFA_LOG.read_text().strip().split("\n"):
            try:
                e = json.loads(line)
                if e.get("family_id") == self.family_id:
                    entries.append(e)
            except Exception: pass
        return entries

    def get_stats(self) -> dict:
        enc = self._load_encounters()
        if not enc: return {"total_encounters": 0}
        det_rate = sum(1 for e in enc if e["detected"]) / len(enc)
        return {
            "total_encounters":  len(enc),
            "detection_rate":    round(det_rate, 3),
            "unique_attacks_seen": len(set(e["attack_key"] for e in enc)),
            "most_common_source": max(set(e["source"] for e in enc),
                                      key=lambda s: sum(1 for e in enc if e["source"]==s),
                                      default="none"),
        }


if __name__ == "__main__":
    print("🧬 Truth Frequency Analyzer Test")
    tfa = TruthFrequencyAnalyzer("test_family")
    tfa.log_encounter("ad_hominem", detected=True,  source="news_media")
    tfa.log_encounter("appeal_to_authority", detected=False, source="school")
    tfa.log_encounter("straw_man", detected=True,  source="social_media")
    tfa.log_encounter("availability_exploitation", detected=False, source="tv_news")
    tfa.log_encounter("availability_exploitation", detected=False, source="podcast")
    profile = tfa.get_immune_profile()
    print(f"Immunity: {profile['immunity_level']} ({profile['overall_detection_rate']:.0%})")
    print(f"Most vulnerable: {[k for k,_ in profile.get('most_vulnerable',[])]}")
    protocol = tfa.get_training_protocol()
    print(f"Training goal: {protocol.get('goal','')}")
    print("✅ War Eagle 🦅")

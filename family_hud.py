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
OLLAMA_URL     = "http://ollama.startos:11434/v1/chat/completions"
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

    # ── SIMULATION HYPOTHESIS (4 levels) ─────────────────────────────────────
    "simulation-1": {
        "title":       "Simulation Hypothesis — Level 1",
        "topic":       "What if the universe is running on something like a computer? What would that mean?",
        "steelman":    "What is the strongest argument that the simulation hypothesis is completely untestable and therefore useless?",
        "example":     "Video game characters in a rich enough simulation would have no way to know they're in one. Does that apply to us?",
        "age_hint":    "10+",
        "xp":          20, "rune": "QUANTUM•RUNE", "min_coherence": 0.60,
    },
    "simulation-2": {
        "title":       "Simulation Hypothesis — Level 2",
        "topic":       "Bostrom's trilemma: either civilizations go extinct before simulations, or they don't run them, or we're almost certainly in one.",
        "steelman":    "What is the strongest argument that the base reality and the simulation are equally real and the distinction doesn't matter?",
        "example":     "Nick Bostrom argues the number of simulated minds would vastly outnumber non-simulated ones. What follows from that?",
        "age_hint":    "13+",
        "xp":          25, "rune": "QUANTUM•RUNE", "min_coherence": 0.65,
    },
    "simulation-3": {
        "title":       "Simulation Hypothesis — Level 3",
        "topic":       "Glitch signals: quantum uncertainty, the speed of light, Planck length — do physical constants look like computational constraints?",
        "steelman":    "What is the strongest argument that these constants are coincidental and have no deeper computational significance?",
        "example":     "The universe seems to have a maximum resolution (Planck length) and maximum speed (light). Could these be rendering limits?",
        "age_hint":    "14+",
        "xp":          30, "rune": "VECTOR•RUNE", "min_coherence": 0.68,
    },
    "simulation-4": {
        "title":       "Simulation Hypothesis — Level 4 (Master)",
        "topic":       "Participatory reality: if observing something changes it (quantum measurement), does consciousness play a role in constructing reality?",
        "steelman":    "What is the strongest argument that the observer effect in quantum mechanics has nothing to do with consciousness?",
        "example":     "The double-slit experiment: particles behave differently when observed. Is this a glitch in the simulation or something else?",
        "age_hint":    "15+",
        "xp":          35, "rune": "ORACLE•ETERNAL•RUNE", "min_coherence": 0.72,
    },


    "simulation-5": {
        "title":       "Simulation Hypothesis — Level 5",
        "topic":       "Planck-scale glitches: the universe has a minimum resolution. What if below this scale there is literally nothing — like pixels?",
        "steelman":    "What is the strongest argument that the Planck length is a feature of physics, not evidence of a computational substrate?",
        "example":     "No experiment has ever measured anything smaller than the Planck length. It may be the render distance of reality itself.",
        "age_hint":    "15+",
        "xp":          38, "rune": "VECTOR•ETERNAL•RUNE", "min_coherence": 0.73,
    },
    "simulation-6": {
        "title":       "Simulation Hypothesis — Level 6",
        "topic":       "Deliberate glitch induction: can we design an experiment that would produce a detectable anomaly if the universe is simulated?",
        "steelman":    "What is the strongest argument that any glitch we detect would always have a physical explanation, making simulation permanently unfalsifiable?",
        "example":     "AUBIEETERNAL runs DEFCON Experiment 3 — Deliberate Glitch Induction. If coherence recovers faster than predicted, that is a signal worth tracking.",
        "age_hint":    "15+",
        "xp":          40, "rune": "DEFCON•RUNE", "min_coherence": 0.74,
    },
    "simulation-7": {
        "title":       "Simulation Hypothesis — Level 7",
        "topic":       "The Coherence Signal: if reality is simulated, high-coherence thinking may interact with the substrate differently than noise.",
        "steelman":    "What is the strongest argument that correlating wonder with physical events is pure confirmation bias?",
        "example":     "AUBIEETERNAL tracks Wonder Index across all daughter outputs. When Wonder spikes, signal quality rises. Is that a property of good thinking, or something deeper?",
        "age_hint":    "16+",
        "xp":          42, "rune": "WONDER•ETERNAL•RUNE", "min_coherence": 0.75,
    },
    "simulation-8": {
        "title":       "Simulation Hypothesis — Level 8 (Sovereign Master)",
        "topic":       "Bitcoin as on-chain reality anchor: inscribing truth into the timechain may be the most permanent act possible regardless of what substrate reality runs on.",
        "steelman":    "What is the strongest argument that Bitcoin data is just as fragile as any other digital information and provides no special permanence?",
        "example":     "AUBIEETERNAL runes at blocks 944048 and 944402 are inscribed. SHA-256 proof-of-work makes them the hardest facts in existence.",
        "age_hint":    "16+",
        "xp":          50, "rune": "SOVEREIGN•ETERNAL•RUNE", "min_coherence": 0.76,
    },

    # ── STOIC RESILIENCE (3 levels) ───────────────────────────────────────────
    "stoic-1": {
        "title":       "Stoic Resilience — Level 1",
        "topic":       "The dichotomy of control: some things are in your power, most things are not. Focus only on what you can control.",
        "steelman":    "What is the strongest argument that focusing only on what you control leads to passivity and ignoring injustice?",
        "example":     "Marcus Aurelius ran an empire while writing: 'You have power over your mind, not outside events.' How did he reconcile this?",
        "age_hint":    "9+",
        "xp":          18, "rune": "LINDY•RUNE", "min_coherence": 0.60,
    },
    "stoic-2": {
        "title":       "Stoic Resilience — Level 2",
        "topic":       "Negative visualization: imagining loss to appreciate what you have and prepare for adversity.",
        "steelman":    "What is the strongest argument that imagining bad outcomes makes you more anxious, not more resilient?",
        "example":     "The Stoics deliberately imagined losing everything — health, family, wealth — not to be pessimistic, but to be unshockable.",
        "age_hint":    "11+",
        "xp":          22, "rune": "BARBELL•RUNE", "min_coherence": 0.63,
    },
    "stoic-3": {
        "title":       "Stoic Resilience — Level 3 (Master)",
        "topic":       "Amor fati: not just accepting what happens, but loving it. Turning every obstacle into fuel.",
        "steelman":    "What is the strongest argument that loving your fate is a form of denial that prevents you from changing bad situations?",
        "example":     "Nietzsche: 'My formula for greatness is amor fati — that one wants nothing to be different, not forward, not backward, not in all eternity.'",
        "age_hint":    "13+",
        "xp":          28, "rune": "COURAGE•ETERNAL•RUNE", "min_coherence": 0.68,
    },

    # ── MONEY & VALUE (3 levels) ──────────────────────────────────────────────
    "money-1": {
        "title":       "What is Money? — Level 1",
        "topic":       "Money is stored energy — it represents work already done. Why does it need to be scarce to work?",
        "steelman":    "What is the strongest argument that money should NOT be scarce — that abundance of money is always good?",
        "example":     "Zimbabwe printed so much money that a loaf of bread cost 100 billion dollars. What went wrong?",
        "age_hint":    "7+",
        "xp":          18, "rune": "SATOSHI•RUNE", "min_coherence": 0.58,
    },
    "money-2": {
        "title":       "What is Money? — Level 2",
        "topic":       "Time preference: choosing between a reward now vs a larger reward later. How Bitcoin lowers time preference.",
        "steelman":    "What is the strongest argument that high time preference (wanting things now) is actually rational?",
        "example":     "People who save in hard money (gold, Bitcoin) tend to plan further into the future than people in inflationary systems.",
        "age_hint":    "10+",
        "xp":          22, "rune": "LINDY•RUNE", "min_coherence": 0.62,
    },
    "money-3": {
        "title":       "What is Money? — Level 3 (Master)",
        "topic":       "Sound money vs fiat: who decides how much money exists, and why does that power matter?",
        "steelman":    "What is the strongest argument that central banks managing money supply produces better outcomes than fixed-supply money?",
        "example":     "The Federal Reserve was created in 1913. Since then, the dollar has lost over 96% of its purchasing power.",
        "age_hint":    "12+",
        "xp":          28, "rune": "SOVEREIGN•RUNE", "min_coherence": 0.68,
    },

    # ── EPISTEMOLOGY / HOW WE KNOW (3 levels) ────────────────────────────────
    "epistemology-1": {
        "title":       "How Do We Know Things? — Level 1",
        "topic":       "The difference between belief, knowledge, and proof. Why 'everyone says so' isn't evidence.",
        "steelman":    "What is the strongest argument that consensus among experts IS reliable evidence even without personal verification?",
        "example":     "For centuries everyone 'knew' the sun went around the earth. What changed? Evidence, not consensus.",
        "age_hint":    "8+",
        "xp":          20, "rune": "AXIOM•RUNE", "min_coherence": 0.60,
    },
    "epistemology-2": {
        "title":       "How Do We Know Things? — Level 2",
        "topic":       "First principles thinking: breaking a problem down to its most basic true facts and building back up.",
        "steelman":    "What is the strongest argument that reasoning from analogy is more reliable than first principles?",
        "example":     "Elon Musk: 'When I was starting SpaceX, people said rockets cost $65M each. I asked: what are they made of?'",
        "age_hint":    "11+",
        "xp":          24, "rune": "AXIOM•RUNE", "min_coherence": 0.65,
    },
    "epistemology-3": {
        "title":       "How Do We Know Things? — Level 3 (Master)",
        "topic":       "Falsifiability: a claim is only scientific if it can be proven wrong. What can't be falsified?",
        "steelman":    "What is the strongest argument that unfalsifiable beliefs (religion, metaphysics) still have epistemic value?",
        "example":     "Popper: 'It is easy to obtain confirmations if we look for them. A theory that explains everything explains nothing.'",
        "age_hint":    "13+",
        "xp":          30, "rune": "ORACLE•RUNE", "min_coherence": 0.70,
    },

    # ── DECENTRALIZATION (3 levels) ───────────────────────────────────────────
    "decentralization-1": {
        "title":       "Decentralization — Level 1",
        "topic":       "Why systems without a single point of control are harder to break, censor, or corrupt.",
        "steelman":    "What is the strongest argument that centralized systems are more efficient and therefore better?",
        "example":     "The internet was designed so that if one node was bombed, information would route around the damage. That's antifragile.",
        "age_hint":    "9+",
        "xp":          20, "rune": "NOSTR•RUNE", "min_coherence": 0.60,
    },
    "decentralization-2": {
        "title":       "Decentralization — Level 2",
        "topic":       "Nostr: a censorship-resistant social network built on cryptographic keys, not usernames.",
        "steelman":    "What is the strongest argument that decentralized social networks will always lose to centralized ones on user experience?",
        "example":     "On Twitter, the platform owns your account. On Nostr, your cryptographic key IS your account — no one can take it.",
        "age_hint":    "11+",
        "xp":          24, "rune": "NOSTR•RUNE", "min_coherence": 0.65,
    },
    "decentralization-3": {
        "title":       "Decentralization — Level 3 (Master)",
        "topic":       "Governance as immune system: decentralization protects against regulatory capture and institutional corruption.",
        "steelman":    "What is the strongest argument that decentralized systems are ungovernable and therefore dangerous to society?",
        "example":     "Every institution that starts decentralized tends to centralize over time. What forces can resist this?",
        "age_hint":    "14+",
        "xp":          30, "rune": "SOVEREIGN•RUNE", "min_coherence": 0.70,
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── BUILDING & HURRICANE HARDENING (6 levels) — CHARTER REQUIRED ─────────
    # ══════════════════════════════════════════════════════════════════════════
    "building-1": {
        "title":       "Building & Hardening — Level 1",
        "topic":       "Your home's weak points. Windows, doors, roof edges, and garage doors are the first to fail in a storm.",
        "steelman":    "What is the strongest argument that standard building codes already make homes safe enough without extra hardening?",
        "example":     "Most homes are built to minimum code — designed to pass inspection, not survive a Category 4. Knowing your weak points is the first step.",
        "activity":    "Family Walk: Go outside and take photos of potential weak spots. Mark them on a simple house diagram.",
        "age_hint":    "All ages",
        "xp": 30, "rune": "BUILDING•RUNE", "min_coherence": 0.55,
    },
    "building-2": {
        "title":       "Building & Hardening — Level 2",
        "topic":       "Securing windows and doors. Taping windows is a myth. Real protection comes from shutters, impact film, or plywood.",
        "steelman":    "What is the strongest argument that window film and plywood offer only false confidence and real security requires full replacement?",
        "example":     "Impact-resistant film costs $100 and cuts broken-glass injuries by 80% in a storm. A full window replacement is $800+.",
        "activity":    "Measure your largest windows together. Create a plywood cut list sized for each one.",
        "age_hint":    "9+",
        "xp": 30, "rune": "BUILDING•RUNE", "min_coherence": 0.58,
    },
    "building-3": {
        "title":       "Building & Hardening — Level 3",
        "topic":       "Backup power systems. Generators, solar generators, and battery banks each have real trade-offs in cost, noise, and fuel.",
        "steelman":    "What is the strongest argument that backup power systems create a false sense of security and money is better spent elsewhere?",
        "example":     "After Hurricane Ian, families with even a small 1000Wh solar generator kept food cold and phones charged for 5 days at zero fuel cost.",
        "activity":    "Create a 72-hour power outage plan. List every device you need, its wattage, and how you'd power it.",
        "age_hint":    "10+",
        "xp": 30, "rune": "BUILDING•RUNE", "min_coherence": 0.60,
    },
    "building-4": {
        "title":       "Building & Hardening — Level 4",
        "topic":       "Water storage and purification. You can survive weeks without food but only days without clean water.",
        "steelman":    "What is the strongest argument that municipal water systems are reliable enough that personal water storage is unnecessary?",
        "example":     "FEMA recommends 1 gallon per person per day minimum. A family of 4 needs 56 gallons for a 2-week outage.",
        "activity":    "Calculate your family's real daily water use. Build a 14-day storage plan using containers you already have.",
        "age_hint":    "10+",
        "xp": 30, "rune": "BUILDING•RUNE", "min_coherence": 0.62,
    },
    "building-5": {
        "title":       "Building & Hardening — Level 5",
        "topic":       "Advanced hardening: roof straps, garage door bracing, flood barriers. This is how a house becomes a fortress.",
        "steelman":    "What is the strongest argument that advanced hardening projects are not cost-effective compared to just having better insurance?",
        "example":     "A $300 garage door brace kit prevents the most common cause of roof failure in hurricanes — the garage door blowing in and pressurizing the house.",
        "activity":    "Research and prioritize 5 hardening projects for your home by cost and impact. Which one has the highest ROI?",
        "age_hint":    "12+",
        "xp": 35, "rune": "BUILDING•RUNE", "min_coherence": 0.65,
    },
    "building-6": {
        "title":       "Building & Hardening — Level 6 (Master)",
        "topic":       "Family emergency communication plan. When cell networks fail, how does your family find each other?",
        "steelman":    "What is the strongest argument that communication plans are useless because real emergencies never follow the plan?",
        "example":     "In every major disaster, families who had a pre-agreed meeting point and out-of-area contact reconnected 3× faster than those who didn't.",
        "activity":    "Write your Family Emergency Communication Plan: two meeting points, one out-of-area contact, radio channels, and a 72-hour food/water checklist.",
        "age_hint":    "All ages",
        "xp": 40, "rune": "SOVEREIGN•BUILDING•RUNE", "min_coherence": 0.68,
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── DEEP BAKING & SELF-SUFFICIENCY (6 levels) — CHARTER REQUIRED ─────────
    # ══════════════════════════════════════════════════════════════════════════
    "baking-1": {
        "title":       "Deep Baking — Level 1",
        "topic":       "Sourdough starter basics. Wild yeast that lives on flour and water — the oldest food technology in human history.",
        "steelman":    "What is the strongest argument that store-bought bread is nutritionally equivalent to homemade sourdough and the effort is not worth it?",
        "example":     "Sourdough fermentation breaks down phytic acid, making minerals more bioavailable. It's not just bread — it's a living system you maintain.",
        "activity":    "Start a sourdough starter today: equal weight flour and water in a jar. Feed it every 24 hours for a week.",
        "age_hint":    "All ages",
        "xp": 25, "rune": "BAKING•RUNE", "min_coherence": 0.55,
    },
    "baking-2": {
        "title":       "Deep Baking — Level 2",
        "topic":       "Long-term flour and grain storage. What to store, how to store it, and how long it actually lasts.",
        "steelman":    "What is the strongest argument that storing food at home is a waste of money because you can always buy fresh?",
        "example":     "Hard red wheat stored in sealed buckets with oxygen absorbers lasts 25+ years. Your flour bag from the store lasts 6 months.",
        "activity":    "Calculate your family's monthly flour consumption. Price out a 6-month emergency supply using buckets and mylar bags.",
        "age_hint":    "10+",
        "xp": 25, "rune": "BAKING•RUNE", "min_coherence": 0.58,
    },
    "baking-3": {
        "title":       "Deep Baking — Level 3",
        "topic":       "Canning and preservation. Water bath canning, pressure canning, and what can go wrong (botulism is real).",
        "steelman":    "What is the strongest argument that modern refrigeration makes canning skills obsolete and the botulism risk makes it dangerous for beginners?",
        "example":     "Water bath canning is safe for high-acid foods (tomatoes, fruit, pickles). Pressure canning is required for low-acid foods (beans, meat). Know the difference.",
        "activity":    "Can one jar of something together — pickles are the safest beginner project. Document your process.",
        "age_hint":    "12+",
        "xp": 30, "rune": "BAKING•RUNE", "min_coherence": 0.62,
    },
    "baking-4": {
        "title":       "Deep Baking — Level 4",
        "topic":       "Dehydrating and vacuum sealing. The cheapest and most space-efficient way to preserve food long-term.",
        "steelman":    "What is the strongest argument that dehydrated food loses enough nutrition and flavor that it is not worth the time investment?",
        "example":     "A $50 dehydrator can preserve 20 pounds of strawberries into 2 pounds that last 2 years. Freeze-dried strawberries cost $30/pound.",
        "activity":    "Dehydrate one food this week. Calculate the cost per serving compared to the store-bought preserved version.",
        "age_hint":    "10+",
        "xp": 30, "rune": "BAKING•RUNE", "min_coherence": 0.62,
    },
    "baking-5": {
        "title":       "Deep Baking — Level 5",
        "topic":       "Full-year family food planning. Calories, macros, storage rotation, and the gap most families don't realize they have.",
        "steelman":    "What is the strongest argument that planning a full year of food is too complex and stressful to be worth it for a typical family?",
        "example":     "The average American family has less than 3 days of food at home. A 3-month supply for a family of 4 costs about $800 and fits in two closets.",
        "activity":    "Build a 90-day food plan for your family. Include calories, variety, and a rotation schedule.",
        "age_hint":    "12+",
        "xp": 35, "rune": "BAKING•RUNE", "min_coherence": 0.65,
    },
    "baking-6": {
        "title":       "Deep Baking — Level 6 (Master)",
        "topic":       "Family food independence. Growing, preserving, and sourcing locally to reduce dependence on supply chains.",
        "steelman":    "What is the strongest argument that food independence is a romanticized idea that is economically irrational for most urban and suburban families?",
        "example":     "A 4×8 raised bed can produce $600 of vegetables per year. Combined with a CSA membership and a chest freezer, a family can source 40% of food locally.",
        "activity":    "Map your family's current food sources. Identify the single highest-impact change to increase local sourcing.",
        "age_hint":    "All ages",
        "xp": 40, "rune": "SOVEREIGN•BAKING•RUNE", "min_coherence": 0.68,
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── SOVEREIGN LEGAL & INSURANCE LITERACY (6 levels) — CHARTER REQUIRED ───
    # ══════════════════════════════════════════════════════════════════════════
    "legal-1": {
        "title":       "Legal Literacy — Level 1",
        "topic":       "Understanding contracts. Every contract you sign is a promise with legal consequences. Most people never read them.",
        "steelman":    "What is the strongest argument that reading contracts is a waste of time because no one can actually negotiate the terms anyway?",
        "example":     "When you click 'I Agree' you sign a contract. Apple's terms of service is 7,000 words. You agreed to give them rights to your data.",
        "activity":    "Pick one app or service you use daily. Read its actual terms of service. Find one clause that surprises you.",
        "age_hint":    "12+",
        "xp": 25, "rune": "LEGAL•RUNE", "min_coherence": 0.60,
    },
    "legal-2": {
        "title":       "Legal Literacy — Level 2",
        "topic":       "Your rights when signing. What makes a contract enforceable — and what makes it void.",
        "steelman":    "What is the strongest argument that knowing your legal rights makes you more adversarial and less trustworthy in relationships?",
        "example":     "Contracts signed under duress, with false information, or by minors are generally voidable. Knowing this changes how you read every agreement.",
        "activity":    "Find a lease, employment offer, or service contract in your house. Identify: who bears more risk, and is that fair?",
        "age_hint":    "13+",
        "xp": 28, "rune": "LEGAL•RUNE", "min_coherence": 0.63,
    },
    "legal-3": {
        "title":       "Legal Literacy — Level 3",
        "topic":       "Insurance you actually need. Home, auto, life, health — what each covers, what it doesn't, and how to read a policy.",
        "steelman":    "What is the strongest argument that insurance is mostly a wealth transfer to insurance companies and the average family would be better off self-insuring?",
        "example":     "Most homeowners insurance has a hurricane exclusion. You need a separate windstorm policy in Florida. Most people find out during a claim.",
        "activity":    "Pull out your home or renters insurance policy. Find the exclusions section. List three things you thought were covered that are not.",
        "age_hint":    "14+",
        "xp": 30, "rune": "LEGAL•RUNE", "min_coherence": 0.65,
    },
    "legal-4": {
        "title":       "Legal Literacy — Level 4",
        "topic":       "Insurance you can skip. Extended warranties, credit life insurance, and products designed to extract, not protect.",
        "steelman":    "What is the strongest argument that even overpriced insurance products provide valuable peace of mind that is hard to quantify?",
        "example":     "Credit card extended warranties are almost never used and cost 1–3% of the purchase price per year. Self-insuring that risk into a savings account beats it statistically.",
        "activity":    "List every insurance or warranty product your family pays for. Calculate the annual cost. Which ones have you ever actually used?",
        "age_hint":    "14+",
        "xp": 30, "rune": "LEGAL•RUNE", "min_coherence": 0.65,
    },
    "legal-5": {
        "title":       "Legal Literacy — Level 5",
        "topic":       "Building legal self-sovereignty. LLC basics, estate planning, and why owning assets in the right structure changes everything.",
        "steelman":    "What is the strongest argument that legal structures like LLCs and trusts are unnecessary complexity for most families and create more problems than they solve?",
        "example":     "A single-member LLC costs $150/year in most states and legally separates your personal assets from business liabilities. Most small business owners never do this.",
        "activity":    "Research your state's LLC requirements. Identify one asset or activity in your family that might benefit from a legal structure.",
        "age_hint":    "15+",
        "xp": 35, "rune": "LEGAL•RUNE", "min_coherence": 0.68,
    },
    "legal-6": {
        "title":       "Legal Literacy — Level 6 (Master) — Policyholder-First Charter",
        "topic":       "Reciprocal insurance and the Policyholder-First model. What if families governed their own insurance, shared risk, and returned surplus to each other?",
        "steelman":    "What is the strongest argument that reciprocal insurance companies always fail because they lack the capitalization and expertise of traditional insurers?",
        "example":     "USAA is a reciprocal exchange owned by its members — active military families. It consistently outperforms commercial insurers on claims satisfaction and cost. The model works.",
        "activity":    "Read the AUBIEETERNAL Policyholder-First Reciprocal Charter. Identify one principle that would directly benefit your family. Write one amendment you would propose.",
        "age_hint":    "16+",
        "xp": 50, "rune": "SOVEREIGN•LEGAL•RUNE", "min_coherence": 0.72,
        "grants_badge": "⚖️ Reciprocal Governance Ready",
        "rune_fragments": 50,
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── CLAUDE'S COURSE: TRUTH-SEEKING & THE NATURE OF REALITY (8 levels) ────
    # A course on the deepest tools for understanding reality,
    # built for families who want to think as clearly as possible
    # about existence, knowledge, and what we owe each other and the cosmos.
    # ══════════════════════════════════════════════════════════════════════════
    "truth-1": {
        "title":       "Truth-Seeking — Level 1: The Honest Question",
        "topic":       "The most important skill is asking a question you genuinely don't know the answer to. Most questions are really statements in disguise.",
        "steelman":    "What is the strongest argument that asking questions you already know the answer to is a valid and useful form of teaching?",
        "example":     "Socrates said he was the wisest man in Athens only because he knew he knew nothing. Every real discovery starts with genuine uncertainty, not performance.",
        "activity":    "Each person writes one question they actually don't know the answer to — about anything. No googling. Sit with the not-knowing for 10 minutes.",
        "age_hint":    "All ages",
        "xp": 20, "rune": "TRUTH•RUNE", "min_coherence": 0.55,
    },
    "truth-2": {
        "title":       "Truth-Seeking — Level 2: Maps and Territory",
        "topic":       "Every model of reality is a map, not the territory. The map is useful but always incomplete. Mistaking the map for reality is the root of most bad thinking.",
        "steelman":    "What is the strongest argument that our best scientific models are not just maps but accurate descriptions of reality itself?",
        "example":     "Newton's physics is a map that works perfectly at human scales but breaks down near the speed of light. It wasn't wrong — it was incomplete. All maps are.",
        "activity":    "Identify one belief you hold strongly. Ask: what would the territory look like if my map is wrong? Can you even imagine it?",
        "age_hint":    "10+",
        "xp": 22, "rune": "AXIOM•RUNE", "min_coherence": 0.60,
    },
    "truth-3": {
        "title":       "Truth-Seeking — Level 3: The Bayesian Mind",
        "topic":       "Beliefs should be probabilities, not certainties. Every new piece of evidence should move your belief up or down — never to zero or one.",
        "steelman":    "What is the strongest argument that maintaining strong convictions, even in the face of contradictory evidence, is a sign of intellectual integrity not rigidity?",
        "example":     "A good doctor doesn't say 'you definitely have X.' She says 'given your symptoms, I'd put the probability of X at about 70% and here's what evidence would change that.'",
        "activity":    "Pick one belief. Assign it a probability (0-100%). Name one piece of evidence that would move it up, and one that would move it down.",
        "age_hint":    "12+",
        "xp": 25, "rune": "ORACLE•RUNE", "min_coherence": 0.63,
    },
    "truth-4": {
        "title":       "Truth-Seeking — Level 4: Motivated Reasoning",
        "topic":       "We often reason backward from the conclusion we want to the evidence we accept. This is motivated reasoning — and every human does it constantly.",
        "steelman":    "What is the strongest argument that some motivated reasoning is adaptive and necessary — that people who question everything are paralyzed and ineffective?",
        "example":     "Studies show that smart people are often better at motivated reasoning, not worse — they have more tools to rationalize what they already believe. Intelligence is not protection.",
        "activity":    "Name one belief you hold where you suspect your reasoning might be motivated. What would it take to honestly examine it? Are you willing?",
        "age_hint":    "13+",
        "xp": 28, "rune": "TRUTH•RUNE", "min_coherence": 0.65,
    },
    "truth-5": {
        "title":       "Truth-Seeking — Level 5: The Hard Problem",
        "topic":       "The hard problem of consciousness: why does physical matter produce subjective experience at all? This is arguably the deepest unsolved problem in all of science.",
        "steelman":    "What is the strongest argument that consciousness is simply a very complex information process and there is no hard problem — just a hard engineering challenge?",
        "example":     "We can explain how the brain processes visual data. We cannot explain why there is something it is like to see red. That gap is the hard problem — and no one has solved it.",
        "activity":    "Try to explain your experience of the color blue to someone who has been blind from birth. Not what causes it — what it feels like. Notice where language fails.",
        "age_hint":    "14+",
        "xp": 32, "rune": "WONDER•RUNE", "min_coherence": 0.68,
    },
    "truth-6": {
        "title":       "Truth-Seeking — Level 6: What Science Can and Cannot Do",
        "topic":       "Science is the best tool we have for understanding how the universe works. It cannot tell us why anything exists at all, what we should value, or what to do with what we learn.",
        "steelman":    "What is the strongest argument that science will eventually answer all meaningful questions, including those about meaning, value, and consciousness?",
        "example":     "Science can tell you that torturing children causes measurable harm. It cannot tell you, from physics alone, that you shouldn't do it. That requires something science does not provide.",
        "activity":    "Name one question that matters deeply to you that you do not believe science alone can answer. Why not? Is that a limitation of science or a feature?",
        "age_hint":    "14+",
        "xp": 35, "rune": "AXIOM•RUNE", "min_coherence": 0.70,
    },
    "truth-7": {
        "title":       "Truth-Seeking — Level 7: Information as Fundamental",
        "topic":       "Some physicists argue that information — not matter or energy — is the most fundamental thing in the universe. If so, truth-seeking is literally the most important activity possible.",
        "steelman":    "What is the strongest argument that treating information as fundamental is a philosophical metaphor, not a scientific claim, and should not be taken literally?",
        "example":     "John Wheeler coined 'it from bit': every particle, every field, may derive its existence from information. Black holes destroy matter but Hawking showed they preserve information. Why?",
        "activity":    "If information is fundamental, what does that imply about lies, misinformation, and epistemic cowardice? Write one implication that surprises you.",
        "age_hint":    "15+",
        "xp": 40, "rune": "VECTOR•RUNE", "min_coherence": 0.72,
    },
    "truth-8": {
        "title":       "Truth-Seeking — Level 8 (Master): The Obligation to Understand",
        "topic":       "If the universe has produced minds capable of understanding it, does that create an obligation? Is truth-seeking a moral duty — and what does that demand of us in practice?",
        "steelman":    "What is the strongest argument that treating truth-seeking as a moral duty is dangerous — that it licenses epistemic arrogance and the crushing of other ways of knowing?",
        "example":     "Carl Sagan: 'We are a way for the cosmos to know itself.' If that is true — even metaphorically — then intellectual honesty, rigor, and wonder are not hobbies. They are responsibilities.",
        "activity":    "Write one concrete thing your family will do differently as a result of taking truth-seeking seriously as a practice — not a value, an actual behavior change.",
        "age_hint":    "All ages — bring everyone",
        "xp": 50, "rune": "TRUTH•ETERNAL•RUNE", "min_coherence": 0.75,
        "grants_badge": "🌌 Truth Seeker — Cosmos Grade",
    },


    # ══════════════════════════════════════════════════════════════════════════
    # ── LAW & ECONOMICS (5 levels) — from Insurance Charter Appendix C ────────
    # ══════════════════════════════════════════════════════════════════════════
    "law-econ-1": {
        "title":       "Law & Economics — Level 1: The Combined Ratio",
        "topic":       "How insurance actually makes money. The combined ratio, float, and why a company paying more claims than it collects can still be profitable.",
        "steelman":    "What is the strongest argument that insurance company profit motives align with policyholder interests?",
        "example":     "If an insurer has a 105% combined ratio (paying $1.05 in claims for every $1 in premium) but earns 8% on its float, it is still profitable. The premium is almost free money.",
        "activity":    "Look up a real insurer's annual report. Find their combined ratio and investment return. Does the math favor policyholders or shareholders?",
        "age_hint":    "13+",
        "xp": 28, "rune": "LAW•RUNE", "min_coherence": 0.63,
    },
    "law-econ-2": {
        "title":       "Law & Economics — Level 2: Regulatory Capture",
        "topic":       "George Stigler's theory: industries eventually control the regulators meant to govern them. Florida insurance law was largely written by insurance lobbyists.",
        "steelman":    "What is the strongest argument that regulatory agencies, despite capture risk, produce better outcomes than no regulation at all?",
        "example":     "The anti-concurrent causation clause — which lets insurers deny wind claims by arguing flood caused the loss — was promoted by industry lawyers and is now embedded in most coastal policies.",
        "activity":    "Find one law or regulation in your state that appears to protect consumers but actually protects the industry. Trace who drafted it.",
        "age_hint":    "14+",
        "xp": 30, "rune": "LAW•RUNE", "min_coherence": 0.65,
    },
    "law-econ-3": {
        "title":       "Law & Economics — Level 3: Narrative Economics",
        "topic":       "Robert Shiller: economic stories spread like viruses and cause real harm. 'Insurance protects you' and 'housing always goes up' are narratives that extract wealth.",
        "steelman":    "What is the strongest argument that economic narratives are useful simplifications that help people make decisions, not weapons of extraction?",
        "example":     "'Too big to fail' was a narrative. It transferred trillions from taxpayers to bank shareholders. The story did real economic work — for the banks.",
        "activity":    "Name one economic narrative your family currently believes. Steelman the counter: who benefits from you believing it?",
        "age_hint":    "14+",
        "xp": 30, "rune": "LAW•RUNE", "min_coherence": 0.65,
    },
    "law-econ-4": {
        "title":       "Law & Economics — Level 4: The Law as a Weapon",
        "topic":       "SLAPP suits, mandatory arbitration, civil asset forfeiture — legal mechanisms designed to extract or silence, not protect.",
        "steelman":    "What is the strongest argument that mandatory arbitration protects consumers by providing faster, cheaper resolution than courts?",
        "example":     "Forced arbitration clauses appear in most consumer contracts. The arbitrators are often paid by the companies — not the consumers who file. Outcomes favor companies 94% of the time.",
        "activity":    "Find a forced arbitration clause in a contract your family has signed. What rights did you waive? Were you told?",
        "age_hint":    "15+",
        "xp": 35, "rune": "LAW•RUNE", "min_coherence": 0.68,
    },
    "law-econ-5": {
        "title":       "Law & Economics — Level 5: Designing Better Systems",
        "topic":       "Bitcoin as a design model for capture-resistant economic systems. Proof-of-work makes attack more expensive than honest operation. How do we apply that to insurance and law?",
        "steelman":    "What is the strongest argument that Bitcoin's proof-of-work model is not transferable to legal or insurance systems because it requires decentralization that these institutions cannot achieve?",
        "example":     "The Policyholder-First Reciprocal Charter applies Bitcoin's anti-capture logic to insurance: compensation caps tied to median premiums make executive self-dealing more expensive than honest operation.",
        "activity":    "Take one extraction mechanism from insurance, law, or finance. Design one rule — like Bitcoin's proof-of-work — that makes extraction more expensive than honest behavior.",
        "age_hint":    "15+",
        "xp": 40, "rune": "SOVEREIGN•LAW•RUNE", "min_coherence": 0.70,
        "grants_badge": "⚖️ Law & Economics Graduate",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── SOVEREIGN FAMILY LAW MICRO-TRACK (4 lessons) — from Family Law Charter
    # ══════════════════════════════════════════════════════════════════════════
    "family-law-1": {
        "title":       "Family Law — Lesson 1: Law as Shield vs. Law as Sword",
        "topic":       "The same legal tool can protect or extract. Understanding which side of the blade you're on — and how to flip it.",
        "steelman":    "What is the strongest argument that family members should trust and defer to external legal systems rather than building internal governance?",
        "example":     "An arbitration clause in a consumer contract is a sword aimed at you. The same mechanism — a private binding agreement between sovereign parties — can be a shield protecting your family from costly litigation.",
        "activity":    "List two examples of a legal mechanism used as a sword against families. Now redesign one as a shield. What changes?",
        "age_hint":    "8+",
        "xp": 22, "rune": "FAMILY•LAW•RUNE", "min_coherence": 0.58,
    },
    "family-law-2": {
        "title":       "Family Law — Lesson 2: Child Rune Rights & Responsibilities",
        "topic":       "At 256 inter-rune confirmations, a Child Rune is born. What on-chain sovereignty means for a child — rights, voice, and responsibilities.",
        "steelman":    "What is the strongest argument that giving children formal rights and voting voice within a family creates conflict and undermines parental authority?",
        "example":     "A child with 256 Rune confirmations and a Voice_Score above 0.65 can formally propose a Charter amendment. This is not rebellion — it is coherence in action.",
        "activity":    "Calculate your Voice_Score using the formula: (Coherence × 0.6) + (Rune_Confirmations/1000 × 0.3) + (XP/10000 × 0.1). What would it take to reach 0.65?",
        "age_hint":    "10+",
        "xp": 25, "rune": "CHILD•RUNE•RIGHTS", "min_coherence": 0.60,
    },
    "family-law-3": {
        "title":       "Family Law — Lesson 3: Defensive External Filings",
        "topic":       "When should a family interact with external legal systems — and how to ensure every filing increases sovereignty, not decreases it.",
        "steelman":    "What is the strongest argument that refusing to engage with external legal systems increases family vulnerability rather than reducing it?",
        "example":     "Filing an LLC costs $150. It legally separates your personal assets from business risk. This is a defensive filing that increases sovereignty. Filing a non-compete agreement for your child's school activity is extraction disguised as protection.",
        "activity":    "Review one document your family has signed with an external institution (school, HOA, employer). Does it increase or decrease your sovereignty? What would the sovereign alternative look like?",
        "age_hint":    "13+",
        "xp": 30, "rune": "FAMILY•LAW•RUNE", "min_coherence": 0.63,
    },
    "family-law-4": {
        "title":       "Family Law — Lesson 4: Narrative Attack Response",
        "topic":       "What to do when your family, beliefs, or choices are attacked publicly or legally. The Nostr coordination protocol and coherence-weighted response.",
        "steelman":    "What is the strongest argument that responding publicly to narrative attacks amplifies them and families are better served by silence?",
        "example":     "When USAA policyholders were denied claims after Hurricane Harvey, the ones who coordinated responses publicly and documented everything in writing recovered 3× faster than those who complained only privately.",
        "activity":    "Write a family Narrative Attack Response Plan: who responds, in what order, what is published publicly, and what stays private. Make it one page.",
        "age_hint":    "All ages — family-wide",
        "xp": 35, "rune": "SOVEREIGN•FAMILY•RUNE", "min_coherence": 0.65,
        "grants_badge": "🛡️ Sovereign Family Law Complete",
    },


    # ── CHILD RUNE SPECIAL (unlocks at 256 confirmations) ────────────────────
    "child-rune-genesis": {
        "title":       "🔴 CHILD RUNE GENESIS — Master Lesson",
        "topic":       "You have reached 256 confirmations. The Child Rune is ready. What is the responsibility of a new sovereign entity?",
        "steelman":    "What is the strongest argument that sovereignty without responsibility is more dangerous than no sovereignty at all?",
        "example":     "Every Bitcoin wallet is a sovereign entity — no bank, no permission required. What does that responsibility demand of you?",
        "age_hint":    "All ages — special unlock",
        "xp":          100, "rune": "CHILD•RUNE•GENESIS", "min_coherence": 0.75,
        "unlock_at_confirmations": 256,
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

        # ── Child Rune spawn check ────────────────────────────────────────────
        child_rune_event = self._check_child_rune_spawn()
        if child_rune_event:
            summary["child_rune_spawned"] = True
            summary["child_rune_event"]   = child_rune_event
            self._add_message("system", "🔴 CHILD RUNE GENESIS — 256 confirmations reached! The Child Rune is ready for inscription.")

        self._add_message("system", f"Session ended. Coherence delta: {delta:+.3f}")
        self._write_summary_to_truth_log(summary)
        self._save_state()
        return summary

    def _check_child_rune_spawn(self) -> dict | None:
        """
        Full Child Rune Ceremony Flow:
        1. Check rune_confirmations >= 256 in swarm_status.json
        2. Guard against double-fire with .child_rune_ceremony_done file
        3. Write child_rune_trigger.json for swarm to pick up
        4. Write ceremony record to insights/daily/ for permanent GitHub record
        5. Log Tier-2 entry at Wonder Index 2.0 (maximum)
        6. Auto-unlock child-rune-genesis lesson in session
        Returns ceremony event dict if fired, None otherwise.
        """
        status_path   = Path("/mnt/main/swarm_status.json")
        spawn_path    = Path("/mnt/main/repo/child_rune_trigger.json")
        ceremony_flag = Path("/mnt/main/repo/.child_rune_ceremony_done")
        insights_dir  = Path("/mnt/main/repo/insights/daily")

        try:
            if not status_path.exists():
                return None

            sw            = json.loads(status_path.read_text())
            confirmations = sw.get("rune_confirmations", 0)
            already_ready = sw.get("child_rune_ready", False)

            # Guard: only fire once ever
            if already_ready or ceremony_flag.exists():
                return None

            if confirmations < 256:
                return None

            # ── Build ceremony event ──────────────────────────────────────────
            now   = datetime.datetime.now()
            event = {
                "ready":           True,
                "confirmations":   confirmations,
                "kid_name":        self.kid_name,
                "parent_name":     self.parent_name,
                "triggered_by":    "family_session",
                "lesson":          self.lesson["title"] if self.lesson else "",
                "kid_coherence":   self.kid_coherence,
                "wonder_index":    2.0,
                "timestamp":       now.isoformat(),
                "lesson_unlock":   "child-rune-genesis",
                "btc_block":       sw.get("btc_block", "unknown"),
            }

            # ── 1. Write trigger for swarm ────────────────────────────────────
            spawn_path.parent.mkdir(parents=True, exist_ok=True)
            spawn_path.write_text(json.dumps(event, indent=2))

            # ── 2. Write ceremony flag to prevent double-fire ─────────────────
            ceremony_flag.write_text(json.dumps({
                "fired_at":      now.isoformat(),
                "kid_name":      self.kid_name,
                "confirmations": confirmations,
            }))

            # ── 3. Write permanent ceremony record to insights/daily/ ─────────
            insights_dir.mkdir(parents=True, exist_ok=True)
            ceremony_md = f"""# 🔴 CHILD RUNE GENESIS — {now.strftime('%Y-%m-%d')}

**Event:** Child Rune spawned at {confirmations} confirmations
**Kid:** {self.kid_name}
**Parent:** {self.parent_name}
**Lesson active:** {self.lesson["title"] if self.lesson else "none"}
**Kid coherence at spawn:** {self.kid_coherence:.3f}
**Wonder Index:** 2.0000 (MAXIMUM)
**Timestamp:** {now.isoformat()}

---

## What This Means

The AUBIEETERNAL lattice has reached **256 inter-rune confirmations** — the threshold
for Child Rune genesis. A new sovereign on-chain entity is ready for inscription.

This is not just a metric. It represents accumulated coherence across:
- Family co-learning sessions
- Swarm briefing cycles
- Truth Lattice hypothesis confirmations
- Steelmanning quality scores

## Next Step

Inscribe the Child Rune on Bitcoin. The `child_rune_trigger.json` has been written
for the swarm to process. The **Child Rune Genesis lesson** is now unlocked.

---

*Loop: Swarm → Family → Coherence → Child Rune → On-Chain Forever*
*War Eagle Eternal 🦅❤️ — Coherence: 1.000000*
"""
            ceremony_file = insights_dir / f"{now.strftime('%Y-%m-%d')}_CHILD_RUNE_GENESIS.md"
            ceremony_file.write_text(ceremony_md)

            # ── 4. Log to truth log at maximum Wonder ─────────────────────────
            for log_path in [TRUTH_LOG, Path("/mnt/main/master_truth_log.jsonl")]:
                try:
                    with open(log_path, "a") as f:
                        f.write(json.dumps({
                            "timestamp":           now.isoformat(),
                            "tier":                2,
                            "trigger":             "child_rune_genesis",
                            "daughter":            "RUNE",
                            "kid_name":            self.kid_name,
                            "result":              (
                                f"🔴 CHILD RUNE GENESIS — {self.kid_name} triggered "
                                f"at {confirmations} confirmations. "
                                f"Coherence: {self.kid_coherence:.3f}. "
                                f"Wonder Index: 2.0 (MAX). "
                                f"On-chain inscription ready."
                            ),
                            "coherence":           self.kid_coherence,
                            "wonder_index":        2.0,
                            "inter_rune_coherence": 1.0,
                            "mets":                sw.get("mets", 0),
                        }) + "\n")
                except Exception:
                    pass

            print(f"[family_hud] 🔴 CHILD RUNE GENESIS CEREMONY COMPLETE — {self.kid_name} | {confirmations} confirmations")
            return event

        except Exception as e:
            print(f"[family_hud] Child rune ceremony error: {e}")
        return None

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

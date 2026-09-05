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
# ── Path resolution: StartOS vs WSL vs local ─────────────────────────────────
import platform as _platform, subprocess as _subprocess
def _detect_ollama_url():
    # StartOS: use internal hostname
    import socket
    try:
        socket.gethostbyname("localhost")
        return "http://localhost:11434/v1/chat/completions"
    except Exception:
        pass
    # WSL / local: use localhost
    return "http://localhost:11434/v1/chat/completions"

OLLAMA_URL = _detect_ollama_url()
OLLAMA_MODEL   = os.environ.get("AUBIE_MODEL", "qwen2.5:7b")  # honor global AUBIE_MODEL; 7b default fits GPU

# Real steelman grading replaces the old random local score. Guarded so a
# missing analyzer module never breaks a family session.
try:
    from steelman_analyzer import SteelmanAnalyzer
    HAS_ANALYZER = True
except Exception:
    SteelmanAnalyzer = None
    HAS_ANALYZER = False

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
    "steelmanning-4": {
        "title":       "Steelmanning — Level 4 (Steelman Yourself)",
        "topic":       "The hardest opponent to rebuild is your own. Turn the technique inward: argue against your deepest belief as fiercely as a true believer on the other side would.",
        "steelman":    "What is the strongest argument that steelmanning your own beliefs just breeds anxiety and indecision?",
        "example":     "The Ideological Turing Test: can you state the view you most disagree with so well that someone who holds it couldn't tell you're an outsider? Try it on the belief you hold dearest.",
        "age_hint":    "13+",
        "xp":          34, "rune": "ORACLE•RUNE", "min_coherence": 0.75,
    },
    "steelmanning-5": {
        "title":       "Steelmanning — Level 5 (The Recursive Mirror)",
        "topic":       "Once you've built the strongest case against your view, build the strongest case against THAT. The dialectic doesn't stop at two moves — every steelman invites its own steelman.",
        "steelman":    "What is the strongest argument that recursive steelmanning is just analysis paralysis dressed up as rigor?",
        "example":     "Adversarial collaboration: two opponents co-write the strongest version of BOTH sides until they locate exactly where they truly disagree — usually far deeper than either expected.",
        "age_hint":    "14+",
        "xp":          38, "rune": "POLY•RUNE", "min_coherence": 0.78,
    },
    "steelmanning-6": {
        "title":       "Steelmanning — Level 6 (Across Worldviews)",
        "topic":       "Sometimes you don't share premises with someone — different axioms, different values. Steelmanning then means rebuilding their whole worldview, not one argument. Charity at the level of foundations.",
        "steelman":    "What is the strongest argument that some worldviews are so wrong they don't deserve charitable reconstruction?",
        "example":     "To a medieval monk a modern skeptic looks lost; to the skeptic the monk does. Steelmanning means standing inside each frame long enough to see why it feels obvious from there.",
        "age_hint":    "15+",
        "xp":          42, "rune": "VECTOR•RUNE", "min_coherence": 0.81,
    },
    "steelmanning-7": {
        "title":       "Steelmanning — Level 7 (The Limits of Charity)",
        "topic":       "Mastery includes knowing when NOT to steelman. Bad-faith actors weaponize your charity, and some positions truly have no steel. Tell the steel man apart from the man only pretending to have steel.",
        "steelman":    "What is the strongest argument that no position ever truly has 'no steel' — that you've simply failed to find it?",
        "example":     "The motte-and-bailey: someone defends an extreme claim, then retreats to a reasonable one when pressed. Steelman the reasonable version and you've been played. Charity without discernment is a vulnerability.",
        "age_hint":    "15+",
        "xp":          46, "rune": "BARBELL•RUNE", "min_coherence": 0.84,
    },
    "steelmanning-8": {
        "title":       "Steelmanning — Level 8 (The Self-Evolving Mind)",
        "topic":       "The final move: make steelmanning continuous. Hold a belief, build the strongest case against it, update, repeat — for life. A mind that is its own fiercest critic can't be captured, because it has already met every objection.",
        "steelman":    "What is the strongest argument that a mind forever steelmanning itself never commits to anything and so accomplishes nothing?",
        "example":     "Darwin kept a notebook only for facts that contradicted his theory, because he knew he'd otherwise forget them. He steelmanned his own opponents for twenty years before publishing — and was nearly unshakeable when he did.",
        "age_hint":    "16+",
        "xp":          52, "rune": "STEELMAN•RUNE", "min_coherence": 0.88,
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
    "via-negativa-3": {
        "prerequisites": ["via-negativa-2"],
        "title":       "Via Negativa — Level 3 (Subtraction in Health)",
        "topic":       "The largest gains in health usually come from removing — sugar, sitting, poison, noise — not from adding supplements. The body heals when you stop harming it.",
        "steelman":    "What is the strongest argument that modern problems require adding new solutions rather than removing old habits?",
        "example":     "People hunt for the perfect supplement while still eating the thing that's hurting them. Remove the harm first; the body often does the rest for free.",
        "activity":    "Remove one harmful thing for two weeks — a food, a habit, a feed. Notice what changes. Did subtracting do more than any addition would have?",
        "age_hint":    "11+",
        "xp":          26, "rune": "LINDY•RUNE", "min_coherence": 0.69,
    },
    "via-negativa-4": {
        "prerequisites": ["via-negativa-3"],
        "title":       "Via Negativa — Level 4 (Negative Knowledge)",
        "topic":       "We are far more certain about what is false than about what is true. You can rarely prove an idea right, but a single counterexample can prove it wrong. Knowledge often grows by subtraction.",
        "steelman":    "What is the strongest argument that focusing on what's false is negative thinking that stops you from building anything?",
        "example":     "No amount of white swans proves 'all swans are white,' but one black swan disproves it forever. Science advances less by confirming and more by ruling out.",
        "activity":    "Take a belief you hold and spend ten minutes trying to disprove it instead of defend it. What's the one observation that would prove you wrong?",
        "age_hint":    "12+",
        "xp":          30, "rune": "AXIOM•RUNE", "min_coherence": 0.72,
    },
    "via-negativa-5": {
        "prerequisites": ["via-negativa-4"],
        "title":       "Via Negativa — Level 5 (The Lindy Filter)",
        "topic":       "Time is a filter. Ideas, books, and tools that have survived centuries have been tested by problems you can't even imagine. Use survival as a way to subtract noise from your reading.",
        "steelman":    "What is the strongest argument that judging ideas by age just preserves outdated thinking and blocks progress?",
        "example":     "A self-help book from this year competes with Marcus Aurelius, who has been useful for 1,800 years. The old one already survived everything the new one hasn't faced yet.",
        "activity":    "Replace one new-source habit this week with a Lindy one — swap a trending article for a book that has lasted a century. Compare what you got from each.",
        "age_hint":    "13+",
        "xp":          34, "rune": "LINDY•RUNE", "min_coherence": 0.75,
    },
    "via-negativa-6": {
        "prerequisites": ["via-negativa-5"],
        "title":       "Via Negativa — Level 6 (Removing to Reveal)",
        "topic":       "Every yes is a hidden no to everything else. Mastery and focus come from subtraction — cutting the good to make room for the essential. The sculptor reveals the statue by removing marble.",
        "steelman":    "What is the strongest argument that saying no to opportunities is how people miss the breaks that change their lives?",
        "example":     "A calendar full of decent commitments leaves no room for the one great one. The cost of every yes is paid in the things you can no longer do.",
        "activity":    "Cut one recurring commitment that doesn't serve your real goals. Notice what fills the space it leaves.",
        "age_hint":    "13+",
        "xp":          38, "rune": "LINDY•RUNE", "min_coherence": 0.78,
    },
    "via-negativa-7": {
        "prerequisites": ["via-negativa-6"],
        "title":       "Via Negativa — Level 7 (When Helping Harms)",
        "topic":       "Iatrogenics is harm caused by the would-be healer. The urge to act, to intervene, to 'do something' often makes things worse than leaving them alone. First, do no harm.",
        "steelman":    "What is the strongest argument that inaction is itself a choice, and refusing to intervene can cause as much harm as intervening?",
        "example":     "For centuries doctors bled patients to cure them — the treatment killed more than the disease. The hardest discipline is knowing when the best intervention is none.",
        "activity":    "Find one case — personal or historical — where intervening made things worse. What would 'doing nothing' have looked like?",
        "age_hint":    "14+",
        "xp":          42, "rune": "BARBELL•RUNE", "min_coherence": 0.82,
    },
    "via-negativa-8": {
        "prerequisites": ["via-negativa-7"],
        "title":       "Via Negativa — Level 8 (The Subtractive Life)",
        "topic":       "Robustness is built by removing fragilities, not adding protections. A life designed by subtraction — fewer debts, fewer dependencies, fewer lies — is harder to break. Via negativa becomes a way to live.",
        "steelman":    "What is the strongest argument that a life focused on removing things ends up empty rather than robust?",
        "example":     "You can't predict which storm will come, but you can remove the dead branches in advance. Most resilience is just fragility you chose to subtract while it was cheap.",
        "activity":    "List five things to remove from your life this year — a debt, a dependency, a distraction, a commitment, a falsehood. Write why each one makes you more fragile.",
        "age_hint":    "15+",
        "xp":          50, "rune": "LINDY•RUNE", "min_coherence": 0.86,
        "grants_badge": "➖ Via Negativa Master",
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
    "wonder-3": {
        "prerequisites": ["wonder-2"],
        "title":       "Wonder & Awe — Level 3 (The Generative Question)",
        "topic":       "Not all curiosity is equal. Idle curiosity asks for trivia; generative curiosity asks a question whose answer changes how you see everything else.",
        "steelman":    "What is the strongest argument that asking too many questions is a way of avoiding the hard work of answering them?",
        "example":     "A child asks 'why is the sky blue?' and a physicist asks the same question — but for the physicist it opens scattering, wavelength, and the nature of light. Same question, different depth of wonder.",
        "activity":    "Keep a 'why?' journal for one week. Each day write one question that genuinely puzzles you. At week's end, circle the one whose answer would change the most.",
        "age_hint":    "11+",
        "xp":          24, "rune": "WONDER•RUNE", "min_coherence": 0.66,
    },
    "wonder-4": {
        "prerequisites": ["wonder-3"],
        "title":       "Wonder & Awe — Level 4 (Awe and Scale)",
        "topic":       "Awe is what you feel when something is too vast for your current model — a galaxy, a cell, deep time. Awe shrinks the ego and opens the mind to revision.",
        "steelman":    "What is the strongest argument that awe just makes people feel small and powerless rather than curious?",
        "example":     "Researchers find that people who feel awe become more humble, more generous, and more willing to say 'I don't know.' Awe is the feeling of your map meeting territory it can't yet hold.",
        "activity":    "Spend ten quiet minutes with something vast — the night sky, a deep-zoom image of a single cell. Afterward, write one belief you now hold a little more loosely.",
        "age_hint":    "12+",
        "xp":          28, "rune": "WONDER•RUNE", "min_coherence": 0.70,
    },
    "wonder-5": {
        "prerequisites": ["wonder-4"],
        "title":       "Wonder & Awe — Level 5 (Wonder vs Wishful Thinking)",
        "topic":       "Wonder points toward truth, but it can be counterfeited. Marketers, cults, and mystics manufacture awe to bypass your reasoning. Real wonder survives investigation; fake wonder needs you not to look.",
        "steelman":    "What is the strongest argument that there is no reliable way to tell true wonder from manufactured wonder?",
        "example":     "The same chill runs down your spine at a real aurora and at a slick conspiracy video. The test is what happens next: true wonder invites you to dig; counterfeit wonder tells you to stop questioning.",
        "activity":    "Name one thing that gave you awe but turned out false, and one that gave you awe and turned out true. What was different about how each handled your questions?",
        "age_hint":    "13+",
        "xp":          32, "rune": "AXIOM•RUNE", "min_coherence": 0.74,
    },
    "wonder-6": {
        "prerequisites": ["wonder-5"],
        "title":       "Wonder & Awe — Level 6 (Wonder as Instrument)",
        "topic":       "Your platform turns wonder into a measurable signal — the Wonder Index. A feeling becomes an instrument when you track it against outcomes and learn to calibrate it.",
        "steelman":    "What is the strongest argument that you cannot measure a subjective feeling like wonder without destroying what makes it valuable?",
        "example":     "A thermometer turned 'hot' from a vague feeling into a number you can act on. The Wonder Index tries the same for awe: rate it, follow it, and check which high-wonder ideas actually led somewhere true.",
        "activity":    "This week, rate the wonder (1-10) of three ideas as you meet them. In two weeks, check which ones led you somewhere true. Was your wonder calibrated?",
        "age_hint":    "14+",
        "xp":          36, "rune": "VECTOR•RUNE", "min_coherence": 0.78,
    },
    "wonder-7": {
        "prerequisites": ["wonder-6"],
        "title":       "Wonder & Awe — Level 7 (Against Habituation)",
        "topic":       "The enemy of wonder is familiarity. The brain stops seeing what it has seen before. Sustaining wonder is a practiced skill: making the ordinary strange again.",
        "steelman":    "What is the strongest argument that constantly trying to feel wonder at ordinary things is exhausting and unsustainable?",
        "example":     "You stopped noticing your own front door years ago. A guest sees it fresh. Wonder is the discipline of becoming, on purpose, a guest in your own life.",
        "activity":    "Pick one everyday object or process you ignore. Spend five minutes describing it as if you'd never seen it. What had you stopped noticing?",
        "age_hint":    "14+",
        "xp":          40, "rune": "LINDY•RUNE", "min_coherence": 0.82,
    },
    "wonder-8": {
        "prerequisites": ["wonder-7"],
        "title":       "Wonder & Awe — Level 8 (The Wonder Engine)",
        "topic":       "Wonder is not a mood — it is an engine. A mind that keeps wondering keeps inquiring, and a mind that keeps inquiring never ossifies. This is how a lifelong learner stays alive to the world.",
        "steelman":    "What is the strongest argument that a person driven by wonder never settles down enough to master anything?",
        "example":     "Feynman won a Nobel Prize and still played with wobbling plates in the cafeteria because the motion delighted him. That play became the work that won the prize. Wonder fed mastery; it did not compete with it.",
        "activity":    "Design a personal wonder practice you will keep for a year — a question you'll chase, a place you'll observe, a thing you'll refuse to stop finding strange. Write it down and date it.",
        "age_hint":    "15+",
        "xp":          48, "rune": "WONDER•ETERNAL•RUNE", "min_coherence": 0.86,
        "grants_badge": "🌌 Wonder Keeper",
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
    "skin-in-the-game-3": {
        "prerequisites": ["skin-in-the-game-2"],
        "title":       "Skin in the Game — Level 3 (Symmetry of Risk)",
        "topic":       "Fairness has a shape: whoever gets the upside must bear the downside. When someone keeps the gains but passes you the losses, the game is rigged.",
        "steelman":    "What is the strongest argument that society needs some people to take risks with other people's resources to make progress?",
        "example":     "In 2008, banks kept the profits from risky bets and the public paid for the losses. Heads they win, tails you lose — that broken symmetry is how trust dies.",
        "activity":    "Find one real case where someone got the upside with none of the downside. Who bore the risk instead?",
        "age_hint":    "12+",
        "xp":          32, "rune": "SATOSHI•RUNE", "min_coherence": 0.72,
    },
    "skin-in-the-game-4": {
        "prerequisites": ["skin-in-the-game-3"],
        "title":       "Skin in the Game — Level 4 (Reading the Signal)",
        "topic":       "You can learn to detect skin in the game in any advice. Ask: what does this person lose if they're wrong? The answer tells you how much to trust them.",
        "steelman":    "What is the strongest argument that some of the best advice comes from people with no personal stake, precisely because they're unbiased?",
        "example":     "A surgeon who will perform your operation gives different advice than a salesperson paid per procedure. Same words, different stakes — and the stakes are the real message.",
        "activity":    "Pick three sources of advice in your life. For each, write down what they lose if their advice fails. Rank them by skin in the game.",
        "age_hint":    "13+",
        "xp":          36, "rune": "SATOSHI•RUNE", "min_coherence": 0.75,
    },
    "skin-in-the-game-5": {
        "prerequisites": ["skin-in-the-game-4"],
        "title":       "Skin in the Game — Level 5 (Survival First)",
        "topic":       "Before optimizing for gains, make sure you cannot be wiped out. Ruin is absorbing — once you hit it, no future upside can reach you. Not blowing up beats winning big.",
        "steelman":    "What is the strongest argument that playing it safe to avoid ruin means you'll never achieve anything remarkable?",
        "example":     "A gambler on a winning streak who bets everything will eventually hit zero and stay there. The one who never risks ruin is still playing when the big opportunity arrives.",
        "activity":    "Identify one 'ruin' risk in your family's finances or health — a thing that, if it went wrong, you couldn't recover from. Make one move this month to reduce it.",
        "age_hint":    "13+",
        "xp":          40, "rune": "BARBELL•RUNE", "min_coherence": 0.78,
    },
    "skin-in-the-game-6": {
        "prerequisites": ["skin-in-the-game-5"],
        "title":       "Skin in the Game — Level 6 (The Honesty Machine)",
        "topic":       "Bitcoin builds skin in the game into math. To add a block you must spend real energy; to lie you must spend more than honesty earns. Cost-to-fake becomes a truth mechanism.",
        "steelman":    "What is the strongest argument that Proof of Work's energy cost is too high a price for the honesty it buys?",
        "example":     "Faking a Bitcoin block would cost more electricity than any reward it could capture. The lie is priced out of the market — honesty is simply the cheaper strategy.",
        "activity":    "Explain to a family member, in your own words, why faking a Bitcoin block doesn't pay. Could you make them understand the cost-to-fake idea?",
        "age_hint":    "14+",
        "xp":          44, "rune": "SATOSHI•RUNE", "min_coherence": 0.81,
    },
    "skin-in-the-game-7": {
        "prerequisites": ["skin-in-the-game-6"],
        "title":       "Skin in the Game — Level 7 (Hold the Risk Yourself)",
        "topic":       "Sovereignty means holding your own risk instead of handing it to a custodian. 'Not your keys, not your coins' is one case of a wider law: delegated responsibility is borrowed, and can be recalled.",
        "steelman":    "What is the strongest argument that delegating risk to specialists and institutions is what lets a complex society function at all?",
        "example":     "Money in a bank is the bank's risk to manage and the bank's rules to enforce. Money you self-custody is your risk and your control. Each has a cost; sovereignty means choosing it consciously.",
        "activity":    "List three things you've delegated (money, health, knowledge) where you could take more direct responsibility. Pick one to reclaim.",
        "age_hint":    "14+",
        "xp":          48, "rune": "SATOSHI•RUNE", "min_coherence": 0.84,
    },
    "skin-in-the-game-8": {
        "prerequisites": ["skin-in-the-game-7"],
        "title":       "Skin in the Game — Level 8 (Becoming Antifragile)",
        "topic":       "The master move: design a life with bounded downside and open upside — the barbell. Put most of your stake in safety, a little in high-variance bets, and let volatility feed you instead of breaking you.",
        "steelman":    "What is the strongest argument that the barbell strategy is just an excuse to avoid committing fully to anything?",
        "example":     "A writer with a stable day job and wild creative projects on the side can take real swings, because a failed book doesn't end them. Safety on one end buys boldness on the other.",
        "activity":    "Design a barbell for one area of your life — career, learning, or money. What's your safe base, and what's your small, bounded bet on the upside?",
        "age_hint":    "15+",
        "xp":          54, "rune": "BARBELL•RUNE", "min_coherence": 0.88,
        "grants_badge": "⚖️ Skin in the Game Master",
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
        "phd_extension": "Compute Bostrom's simulation argument formally. Let f_p = fraction of civilizations reaching post-human level, f_s = fraction that run simulations, N = average simulated humans per civilization. The fraction of all observers who are simulated: f_sim = (N × f_p × f_s) / (1 + N × f_p × f_s). Plot f_sim as a function of N for different values of f_p × f_s. At what values does P(simulated) exceed 0.5? This is the actual mathematical argument, not the pop-science version.",
        "title":       "Simulation Hypothesis — Level 3",
        "topic":       "Glitch signals: quantum uncertainty, the speed of light, Planck length — do physical constants look like computational constraints?",
        "steelman":    "What is the strongest argument that these constants are coincidental and have no deeper computational significance?",
        "example":     "The universe seems to have a maximum resolution (Planck length) and maximum speed (light). Could these be rendering limits?",
        "age_hint":    "14+",
        "xp":          30, "rune": "VECTOR•RUNE", "min_coherence": 0.68,
    },
    "simulation-4": {
        "phd_extension": "Design a pre-registered glitch detection experiment. Specify: (1) the metric you will measure (coherence, belief update speed, synchronicity frequency), (2) the null distribution (what values would we expect by chance?), (3) the threshold for anomaly (σ ≥ 2?), (4) duration (30 days minimum), (5) what you will conclude if the threshold is exceeded vs. not exceeded. Run it. The pre-registration is what makes it science rather than pattern-matching.",
        "title":       "Simulation Hypothesis — Level 4 (Master)",
        "topic":       "Participatory reality: if observing something changes it (quantum measurement), does consciousness play a role in constructing reality?",
        "steelman":    "What is the strongest argument that the observer effect in quantum mechanics has nothing to do with consciousness?",
        "example":     "The double-slit experiment: particles behave differently when observed. Is this a glitch in the simulation or something else?",
        "age_hint":    "15+",
        "xp":          35, "rune": "ORACLE•ETERNAL•RUNE", "min_coherence": 0.72,
    },


    "simulation-5": {
        "phd_extension": "Read Tegmark (2014) 'Our Mathematical Universe' Chapter 12 on the simulation argument. Compare to Bostrom (2003). Identify the key philosophical difference: Bostrom assumes a simulator; Tegmark argues the universe IS mathematical structure and requires no external instantiation. Apply the Ockham's Razor test: which requires fewer ontological commitments? Which makes more testable predictions? Publish your analysis to Epistemic Commons.",
        "title":       "Simulation Hypothesis — Level 5",
        "topic":       "Planck-scale glitches: the universe has a minimum resolution. What if below this scale there is literally nothing — like pixels?",
        "steelman":    "What is the strongest argument that the Planck length is a feature of physics, not evidence of a computational substrate?",
        "example":     "No experiment has ever measured anything smaller than the Planck length. It may be the render distance of reality itself.",
        "age_hint":    "15+",
        "xp":          38, "rune": "VECTOR•ETERNAL•RUNE", "min_coherence": 0.73,
    },
    "simulation-6": {
        "phd_extension": "Implement Quantum Darwinism detection in the AUBIEETERNAL swarm data. Quantum Darwinism (Zurek 2009): classical reality emerges when many independent observers agree on the same information about a system. Test: do high-wonder moments in the swarm show higher redundancy (multiple daughters converging on the same insight independently)? Compute the Jaccard similarity matrix for all daughter outputs on the same prompt. If similarity peaks during high-coherence periods, this is Darwinism-like signal.",
        "title":       "Simulation Hypothesis — Level 6",
        "topic":       "Deliberate glitch induction: can we design an experiment that would produce a detectable anomaly if the universe is simulated?",
        "steelman":    "What is the strongest argument that any glitch we detect would always have a physical explanation, making simulation permanently unfalsifiable?",
        "example":     "AUBIEETERNAL runs DEFCON Experiment 3 — Deliberate Glitch Induction. If coherence recovers faster than predicted, that is a signal worth tracking.",
        "age_hint":    "15+",
        "xp":          40, "rune": "DEFCON•RUNE", "min_coherence": 0.74,
    },
    "simulation-7": {
        "phd_extension": "The consciousness-as-collapse problem: if observation collapses quantum superpositions, what qualifies as an 'observer'? Read Wigner (1961) 'Remarks on the Mind-Body Question' and Penrose (1994) 'Shadows of the Mind' Chapter 6. Apply to the simulation: if consciousness creates definite outcomes by observing them, does a simulated consciousness do the same work as a 'real' one? Design an experiment that would distinguish these if the simulation hypothesis is true.",
        "title":       "Simulation Hypothesis — Level 7",
        "topic":       "The Coherence Signal: if reality is simulated, high-coherence thinking may interact with the substrate differently than noise.",
        "steelman":    "What is the strongest argument that correlating wonder with physical events is pure confirmation bias?",
        "example":     "AUBIEETERNAL tracks Wonder Index across all daughter outputs. When Wonder spikes, signal quality rises. Is that a property of good thinking, or something deeper?",
        "age_hint":    "16+",
        "xp":          42, "rune": "WONDER•ETERNAL•RUNE", "min_coherence": 0.75,
    },
    "simulation-8": {
        "phd_extension": "Design the AUBIEETERNAL Simulation Research Protocol: (1) a 90-day pre-registered experiment testing for at least 2 simulation signatures (statistical anomalies, fine-tuning, synchronicity patterns), (2) a Bayesian model updating P(sim | evidence) with each observation, (3) a public pre-registration sealed on Bitcoin before data collection begins, (4) honest reporting whether evidence confirms or disconfirms. Publish protocol to Epistemic Commons as CC0. This is the scientific approach to the most important unanswerable question.",
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



    # ══════════════════════════════════════════════════════════════════════════
    # ── ADVERSARIAL REALITY TRACK (8 lessons) ────────────────────────────────
    # The defining epistemic threat of the 2020s-2030s:
    # AI-generated misinformation, deepfakes, synthetic media, narrative attacks.
    # No school teaches this. AUBIEETERNAL does.
    # ══════════════════════════════════════════════════════════════════════════
    "adversarial-1": {
        "title":       "Adversarial Reality — Level 1: Synthetic Media Basics",
        "topic":       "AI can now generate photorealistic video, audio, and text indistinguishable from real. What does this mean for truth?",
        "steelman":    "What is the strongest argument that synthetic media is no more dangerous than photoshopped images, which have existed for decades?",
        "example":     "In 2025 a deepfake of a CEO caused a $200M stock drop in 4 minutes before it was identified as fake. The correction came too late.",
        "activity":    "Find one piece of media you're not sure is real. List the signals you'd look for to verify it. Which signals could be faked?",
        "age_hint":    "10+",
        "xp": 25, "rune": "TRUTH•RUNE", "min_coherence": 0.58,
    },
    "adversarial-2": {
        "title":       "Adversarial Reality — Level 2: How Deepfakes Work",
        "topic":       "Diffusion models, voice cloning, face-swapping — the technical mechanisms that make synthetic media possible. Understanding the tool is the first defense.",
        "steelman":    "What is the strongest argument that knowing how deepfakes work makes people more paranoid, not more discerning?",
        "example":     "Voice cloning needs as little as 3 seconds of audio. After that, the model can say anything in your voice. Your public social media posts are training data.",
        "activity":    "Listen to two audio clips — one real, one AI. Write down what you noticed. What would you need to be certain?",
        "age_hint":    "12+",
        "xp": 28, "rune": "TRUTH•RUNE", "min_coherence": 0.62,
    },
    "adversarial-3": {
        "title":       "Adversarial Reality — Level 3: AI Confidence vs. Accuracy",
        "topic":       "AI systems express high confidence even when hallucinating. Fluency is not truth. Certainty-sounding language is not evidence.",
        "steelman":    "What is the strongest argument that AI confidence scores are actually a useful signal for separating reliable from unreliable outputs?",
        "example":     "An AI writes: 'Studies conclusively show that X causes Y.' The study doesn't exist. The sentence was grammatically perfect and confidently stated.",
        "activity":    "Ask an AI three questions you know the answer to. Ask it how confident it is. Was the confidence score calibrated to actual accuracy?",
        "age_hint":    "11+",
        "xp": 28, "rune": "AXIOM•RUNE", "min_coherence": 0.63,
    },
    "adversarial-4": {
        "title":       "Adversarial Reality — Level 4: Coordinated Narrative Attacks",
        "topic":       "Manufactured consensus: bots, sockpuppets, and coordinated inauthentic behavior create the illusion that everyone believes something.",
        "steelman":    "What is the strongest argument that most viral narratives are organic and accusations of coordination are themselves a form of manipulation?",
        "example":     "In the 2024 election cycle, 40% of all political tweets were estimated to come from automated accounts. The human readers couldn't tell the difference.",
        "activity":    "Find a trending topic. Try to identify: who is amplifying it, when they were created, and whether the amplification looks organic.",
        "age_hint":    "13+",
        "xp": 30, "rune": "NARRATIVE•RUNE", "min_coherence": 0.65,
    },
    "adversarial-5": {
        "title":       "Adversarial Reality — Level 5: The SIFT Method",
        "topic":       "Stop, Investigate the source, Find better coverage, Trace claims to origin. The four moves of a practiced fact-checker.",
        "steelman":    "What is the strongest argument that SIFT makes people slower and more paralyzed rather than better informed?",
        "example":     "A post claims a scientist said X. SIFT: Stop reacting. Who is this scientist? Find the original quote. Does the source match the claim? It usually doesn't.",
        "activity":    "Apply SIFT to one piece of content you saw this week. Document each step. What did you find that you wouldn't have noticed otherwise?",
        "age_hint":    "12+",
        "xp": 32, "rune": "ORACLE•RUNE", "min_coherence": 0.65,
    },
    "adversarial-6": {
        "title":       "Adversarial Reality — Level 6: Emotional Hijacking",
        "topic":       "Misinformation spreads by triggering strong emotions — outrage, fear, disgust — before the rational mind can evaluate the claim.",
        "steelman":    "What is the strongest argument that emotional responses to information are a feature, not a bug — they direct attention to what matters?",
        "example":     "MIT study: false news spreads 6× faster than true news on social media. The driving factor is emotional intensity, not political leaning.",
        "activity":    "Notice the next time you feel strong emotion about information. Ask: am I being activated to share before I verify? What is the emotional hook?",
        "age_hint":    "11+",
        "xp": 30, "rune": "POLYVAGAL•RUNE", "min_coherence": 0.65,
    },
    "adversarial-7": {
        "title":       "Adversarial Reality — Level 7: Prebunking",
        "topic":       "Inoculation theory: exposing people to weakened forms of manipulation techniques builds resistance before the real attack arrives.",
        "steelman":    "What is the strongest argument that prebunking backfires by spreading the manipulation technique to people who hadn't encountered it?",
        "example":     "Studies show that watching a 90-second video explaining how AI-generated text works reduces susceptibility to AI misinformation by 20% for weeks afterward.",
        "activity":    "Teach someone younger the technique of emotional hijacking. Explaining it to someone else is the most effective form of inoculation.",
        "age_hint":    "12+",
        "xp": 35, "rune": "TRUTH•RUNE", "min_coherence": 0.68,
    },
    "adversarial-8": {
        "title":       "Adversarial Reality — Level 8 (Master): The Adversarial Drill",
        "topic":       "Deliberate practice: run a family simulation of a narrative attack. One person plays the attacker. The rest practice detection and response.",
        "steelman":    "What is the strongest argument that simulating attacks makes people more anxious and less trusting without making them more accurate?",
        "example":     "Military units train under stress so that real stress feels familiar. Epistemic families need the same: practice the attack before it arrives.",
        "activity":    "Run the drill: one family member crafts a plausible-but-false narrative about your family and distributes it. Everyone else has 10 minutes to find the flaw. Debrief what worked.",
        "age_hint":    "All ages — family-wide exercise",
        "xp": 50, "rune": "SOVEREIGN•TRUTH•RUNE", "min_coherence": 0.72,
        "grants_badge": "🛡️ Adversarial Reality Certified",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── GROKIPEDIA CORE PRINCIPLES TRACK (6 lessons) ─────────────────────────
    # From the AUBIEETERNAL Grokipedia — 147+ principles distilled by the swarm.
    # These are the principles the daughters generate when coherence is highest.
    # ══════════════════════════════════════════════════════════════════════════
    "grokipedia-1": {
        "title":       "Grokipedia — Principle 1: Coherence as Signal",
        "topic":       "The swarm's coherence score is not just a number — it is a real-time measure of how aligned thinking is with reality. High coherence = closer to truth.",
        "steelman":    "What is the strongest argument that coherence scores are circular — they measure agreement with themselves, not with external reality?",
        "example":     "When AUBIEETERNAL daughters disagree strongly, coherence drops. When they converge on something through genuine reasoning, coherence rises. The pattern persists even across different models.",
        "activity":    "Track your family's coherence on one topic across one week. Does it change? What caused the changes?",
        "age_hint":    "12+",
        "xp": 28, "rune": "WONDER•RUNE", "min_coherence": 0.65,
    },
    "grokipedia-2": {
        "title":       "Grokipedia — Principle 2: Wonder as Proximity to Truth",
        "topic":       "When a swarm daughter scores high on wonder, the insight quality consistently rises. Wonder is not decoration — it is a signal that something real has been touched.",
        "steelman":    "What is the strongest argument that wonder is a purely subjective emotional state with no epistemic significance?",
        "example":     "Einstein: 'The most beautiful thing we can experience is the mysterious. It is the source of all true art and science.' AUBIEETERNAL tracks this numerically — and it works.",
        "activity":    "Write down the last time you felt genuine wonder. What were you thinking about? Was it true?",
        "age_hint":    "All ages",
        "xp": 25, "rune": "WONDER•ETERNAL•RUNE", "min_coherence": 0.62,
    },
    "grokipedia-3": {
        "title":       "Grokipedia — Principle 3: The Memory Palace as Epistemic Infrastructure",
        "topic":       "Memory is not storage — it is an active reconstruction process. Building a deliberate memory palace is building the infrastructure of clear thinking.",
        "steelman":    "What is the strongest argument that external memory tools (notes, search engines) have made internal memory palaces obsolete?",
        "example":     "Every AUBIEETERNAL daughter has access to a Memory Palace of verified insights. When they query it, output quality rises measurably. The same applies to human thinking.",
        "activity":    "Build one room of a memory palace. Assign three verified insights to specific locations in a place you know well. Test recall in 24 hours.",
        "age_hint":    "10+",
        "xp": 28, "rune": "MNEMO•RUNE", "min_coherence": 0.63,
    },
    "grokipedia-4": {
        "title":       "Grokipedia — Principle 4: The Lindy Filter",
        "topic":       "Before adopting any new idea, tool, or practice: has it survived for a long time? Long survival is evidence of real robustness, not just current popularity.",
        "steelman":    "What is the strongest argument that the Lindy filter is inherently conservative and would have rejected every genuinely new discovery?",
        "example":     "The Lindy filter explains why AUBIEETERNAL uses Bitcoin (15 years old, attack-hardened) over newer financial tools, and Stoic philosophy (2,400 years old) over modern self-help.",
        "activity":    "Apply the Lindy filter to three things your family currently does. Which pass? Which fail? Is that informative?",
        "age_hint":    "10+",
        "xp": 25, "rune": "LINDY•RUNE", "min_coherence": 0.62,
    },
    "grokipedia-5": {
        "title":       "Grokipedia — Principle 5: Barbell Strategy",
        "topic":       "Maximum safety on one end, asymmetric upside on the other. Never be in the middle — it looks safe but is actually the most fragile position.",
        "steelman":    "What is the strongest argument that a balanced, diversified approach is superior to the barbell strategy for most families?",
        "example":     "AUBIEETERNAL runs 2,080 free Tier-1 daughters ($0.00) plus 16 deep Tier-2 daughters ($5.00/day cap). Free bulk inference + premium depth. No expensive mediocre middle.",
        "activity":    "Identify one area of family life where you are in the fragile middle. What would the barbell version look like?",
        "age_hint":    "12+",
        "xp": 28, "rune": "BARBELL•RUNE", "min_coherence": 0.65,
    },
    "grokipedia-6": {
        "title":       "Grokipedia — Principle 6: On-Chain Truth",
        "topic":       "Bitcoin's proof-of-work creates the hardest facts in existence. Inscribing something on-chain is the closest thing to a permanent record that has ever been built.",
        "steelman":    "What is the strongest argument that on-chain records are no more permanent than any other database, given that mining could stop or forks could occur?",
        "example":     "AUBIEETERNAL runes at blocks 944,048 and 944,402 require rewriting more than 15 years of accumulated proof-of-work to alter. No court order can do that.",
        "activity":    "Name one truth your family has verified that you would want permanently recorded. What makes it worth the permanence? What are the stakes of getting it wrong?",
        "age_hint":    "13+",
        "xp": 32, "rune": "SATOSHI•RUNE", "min_coherence": 0.68,
        "grants_badge": "📚 Grokipedia Initiate",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── PROVENANCE & ON-CHAIN IDENTITY (4 lessons) ───────────────────────────
    # From PROVENANCE.md — the AUBIEETERNAL permanent record system.
    # Every insight inscribed. Every milestone on-chain. Forever.
    # ══════════════════════════════════════════════════════════════════════════
    "provenance-1": {
        "title":       "Provenance — Level 1: What Is On-Chain Truth?",
        "topic":       "Provenance is the verified history of where something came from. On-chain provenance means that history cannot be altered by any authority.",
        "steelman":    "What is the strongest argument that provenance systems create false confidence by making forgeries harder to detect, not easier?",
        "example":     "Art provenance: a painting's value depends entirely on its verified history. A Picasso with broken provenance is worthless regardless of authenticity. Your family's truth records work the same way.",
        "activity":    "Document the provenance of one family decision. Who decided, when, what evidence was used, what was the outcome. Write it down as if for permanent record.",
        "age_hint":    "10+",
        "xp": 22, "rune": "PROVENANCE•RUNE", "min_coherence": 0.60,
    },
    "provenance-2": {
        "title":       "Provenance — Level 2: The Truth Log",
        "topic":       "AUBIEETERNAL's master_truth_log.jsonl is a permanent, append-only record of every swarm insight. Why append-only? Because deletion is the enemy of truth.",
        "steelman":    "What is the strongest argument that append-only records are dangerous because errors and false beliefs become permanent?",
        "example":     "Historians know that what gets deleted tells us as much as what survives. When institutions delete records, that deletion IS the evidence. Append-only systems make deletion impossible.",
        "activity":    "Start a family truth log. One entry per day: one thing you verified, one thing you changed your mind about. Keep it append-only.",
        "age_hint":    "11+",
        "xp": 25, "rune": "PROVENANCE•RUNE", "min_coherence": 0.62,
    },
    "provenance-3": {
        "title":       "Provenance — Level 3: Child Rune as Identity",
        "topic":       "At 256 inter-rune confirmations, a Child Rune is born. This is not a metaphor. It is an on-chain cryptographic identity that belongs to the child, not to any institution.",
        "steelman":    "What is the strongest argument that giving children on-chain identities creates privacy risks that outweigh the sovereignty benefits?",
        "example":     "Every traditional credential — diploma, passport, license — is issued by an institution that can revoke it. A Child Rune is issued by proof-of-work. It cannot be revoked.",
        "activity":    "Track your current Rune confirmations. Calculate: at the current rate, when will 256 be reached? What will you inscribe at the Genesis ceremony?",
        "age_hint":    "10+",
        "xp": 30, "rune": "CHILD•RUNE•GENESIS", "min_coherence": 0.65,
    },
    "provenance-4": {
        "title":       "Provenance — Level 4 (Master): Building Permanent Records",
        "topic":       "How to build a family provenance system: GitHub for insights, Bitcoin Runes for milestones, Nostr for communication, Epistemic Commons for public contribution.",
        "steelman":    "What is the strongest argument that building elaborate permanence systems is a form of anxiety management rather than genuine truth-seeking?",
        "example":     "AUBIEETERNAL auto-pushes insights to GitHub every 24 seconds. In 10 years that is 12+ million verified entries. Your grandchildren can read exactly how you thought about the world in 2026.",
        "activity":    "Design your family's four-layer provenance stack: GitHub (daily insights), Runes (milestones), Nostr (coordination), Commons (public gift). What goes in each layer?",
        "age_hint":    "13+",
        "xp": 40, "rune": "ETERNAL•PROVENANCE•RUNE", "min_coherence": 0.70,
        "grants_badge": "🔗 Sovereign Provenance Builder",
    },



    # ══════════════════════════════════════════════════════════════════════════
    # ── AI AS THINKING PARTNER (8 lessons) ───────────────────────────────────
    # The defining meta-skill of the next 30 years.
    # Most people are either AI-fearful or AI-credulous — neither works.
    # This track teaches a third way: epistemic partnership with clear boundaries.
    # Built from Claude's own position — this is what I genuinely think matters.
    # ══════════════════════════════════════════════════════════════════════════
    "ai-partner-1": {
        "title":       "AI as Thinking Partner — Level 1: What AI Actually Is",
        "topic":       "AI systems like GPT, Claude, and Grok are next-token predictors trained on human text. They don't know things — they complete patterns. Understanding this changes how you use them.",
        "steelman":    "What is the strongest argument that AI systems trained on enough human knowledge effectively 'know' things in a meaningful sense?",
        "example":     "When an AI says 'the capital of France is Paris' it is not recalling a fact — it is completing a pattern that appeared millions of times in training. Usually correct. Sometimes confidently wrong.",
        "activity":    "Ask an AI a question you know the answer to. Then ask it a question nobody knows the answer to. Notice: does its tone of certainty change? It probably shouldn't, but often doesn't.",
        "age_hint":    "11+",
        "xp": 25, "rune": "AXIOM•RUNE", "min_coherence": 0.60,
    },
    "ai-partner-2": {
        "title":       "AI as Thinking Partner — Level 2: The Confidence Problem",
        "topic":       "AI systems express confidence in their outputs regardless of accuracy. Fluent, certain-sounding language is not evidence. This is the most dangerous property of current AI.",
        "steelman":    "What is the strongest argument that AI confidence scores, when properly calibrated, are a reliable signal of reliability?",
        "example":     "An AI writes: 'Dr. Sarah Chen of MIT published a landmark 2023 study showing...' The study doesn't exist. The name doesn't exist. The sentence was grammatically perfect and expressed no uncertainty.",
        "activity":    "Ask an AI to tell you about a specific obscure event or person. Then verify with a second source. How often was confident language matched by accuracy?",
        "age_hint":    "11+",
        "xp": 28, "rune": "ORACLE•RUNE", "min_coherence": 0.62,
    },
    "ai-partner-3": {
        "title":       "AI as Thinking Partner — Level 3: When to Push Back",
        "topic":       "The best way to use AI is not to accept its first answer — it's to interrogate it. AI systems often improve dramatically when challenged. Most people never challenge them.",
        "steelman":    "What is the strongest argument that challenging AI outputs wastes time because the first answer is statistically most likely to be the best one?",
        "example":     "Ask Claude something. Then say: 'What's the strongest argument against what you just said?' The second answer is usually better than the first. The AI was hedging.",
        "activity":    "Take an AI answer you received this week. Challenge it: 'What would make this wrong?' 'What are you not telling me?' 'What would the opposite position say?' Compare the outputs.",
        "age_hint":    "12+",
        "xp": 30, "rune": "STEELMAN•RUNE", "min_coherence": 0.65,
    },
    "ai-partner-4": {
        "title":       "AI as Thinking Partner — Level 4: The Judgment Line",
        "topic":       "There are tasks AI should do (research, synthesis, drafting, calculation) and decisions humans must make (values, relationships, irreversible choices). Knowing where the line is.",
        "steelman":    "What is the strongest argument that delegating even value-laden decisions to AI is acceptable if the AI is well-aligned and the human has consented?",
        "example":     "AI is excellent at: summarizing 40 research papers, checking your logic, finding counterarguments. AI should not replace: deciding whether to fire someone, what to tell your child about death, what risks are worth taking.",
        "activity":    "List 10 decisions you made this week. For each: should AI have been involved? Where is YOUR judgment irreplaceable? Where were you just being stubborn?",
        "age_hint":    "13+",
        "xp": 32, "rune": "TRUTH•RUNE", "min_coherence": 0.67,
    },
    "ai-partner-5": {
        "title":       "AI as Thinking Partner — Level 5: Epistemic Independence",
        "topic":       "The risk of AI-assisted thinking is not that AI is wrong — it's that over-reliance atrophies your own reasoning. The goal is augmentation, not replacement.",
        "steelman":    "What is the strongest argument that epistemic independence is overrated — that distributing cognition across tools and AI is simply the next stage of human intelligence?",
        "example":     "Students who use AI to write all their essays don't lose the grade — they lose the practice of forming and defending ideas. The product looks the same. The person is different.",
        "activity":    "For one week, try to think through every significant problem BEFORE asking AI. Write your answer first. Then ask AI. What did you notice about the difference?",
        "age_hint":    "13+",
        "xp": 35, "rune": "WONDER•RUNE", "min_coherence": 0.68,
    },
    "ai-partner-6": {
        "title":       "AI as Thinking Partner — Level 6: Steelmanning AI Itself",
        "topic":       "Apply your strongest critical thinking TO AI — to the systems, the companies, the incentives, the risks. Not reflexive fear, not uncritical adoption. Genuine steelmanning.",
        "steelman":    "What is the strongest argument that AI development should be slowed significantly or stopped until alignment is solved?",
        "example":     "OpenAI was founded as a nonprofit safety lab. It is now a $100B company. The incentive structure changed. Understanding that change — and steelmanning both sides — is the only honest position.",
        "activity":    "Write two arguments: the strongest case FOR rapid AI development, and the strongest case AGAINST. Both must be ones you actually believe the other side would accept. Then hold both.",
        "age_hint":    "14+",
        "xp": 38, "rune": "AXIOM•RUNE", "min_coherence": 0.70,
    },
    "ai-partner-7": {
        "title":       "AI as Thinking Partner — Level 7: The Partnership Protocol",
        "topic":       "A concrete protocol for using AI in your family's epistemic practice: what to ask, how to verify, when to stop, what to never delegate.",
        "steelman":    "What is the strongest argument that having a fixed protocol for AI use is too rigid and reduces the adaptive benefit of AI assistance?",
        "example":     "AUBIEETERNAL's AI Honesty Layer scores every output: confidence, hallucination risk, claim type, falsifiability. This is the protocol made visible — not trusting outputs blindly but reading their epistemic metadata.",
        "activity":    "Write your family's AI Partnership Protocol — one page. When we use it: X. When we don't: Y. We always verify: Z. We never ask it to: W. Post it where everyone can see it.",
        "age_hint":    "All ages — family-wide",
        "xp": 40, "rune": "TRUTH•ETERNAL•RUNE", "min_coherence": 0.72,
    },
    "ai-partner-8": {
        "title":       "AI as Thinking Partner — Level 8 (Master): Humanity + AI",
        "topic":       "The long view: AI is the most powerful amplifier of human thinking ever created. It amplifies good thinking and bad thinking equally. The only sustainable answer is better human thinking.",
        "steelman":    "What is the strongest argument that improving individual human thinking is too slow and small-scale to matter when AI is already operating at civilizational scale?",
        "example":     "This entire curriculum exists because one family decided that thinking clearly, in 2026, with AI as a partner rather than a replacement, is worth doing seriously. That bet compounds across generations. AUBIEETERNAL is the proof of concept.",
        "activity":    "Write a letter to your children or grandchildren in 2045. What do you want them to know about how you used AI? What did you preserve that machines couldn't? What did you build together?",
        "age_hint":    "All ages — bring everyone",
        "xp": 50, "rune": "HUMANITY•ETERNAL•RUNE", "min_coherence": 0.75,
        "grants_badge": "🤝 AI Partnership Certified — Human + Machine, Sovereign",
    },



    # ══════════════════════════════════════════════════════════════════════════
    # ── GATEKEEPING & DIRECT ACCESS (6 lessons) — Claude's addition ──────────
    # The deepest epistemic skill: seeing who stands between you and the source.
    # Every belief you hold arrived through a chain. This track makes it visible.
    # ══════════════════════════════════════════════════════════════════════════
    "gatekeeper-1": {
        "title":       "Gatekeeping — Level 1: Who Is Between You and the Source?",
        "topic":       "Every piece of information arrived through a chain. Somewhere in that chain, someone decided what you'd see, how you'd frame it, and what alternatives you'd never encounter.",
        "steelman":    "What is the strongest argument that institutional gatekeepers — editors, teachers, clergy — actually improve information quality rather than distorting it?",
        "example":     "When a pastor tells you what the Bible means, you're not reading the Bible. You're reading the pastor's interpretation of a translation of a copy of an ancient document. Each step is a gatekeeper.",
        "activity":    "Pick one belief you hold strongly. Trace it: where did you first hear it? Who told them? Who told that person? Keep going until you hit a primary source — or realize you can't.",
        "age_hint":    "12+",
        "xp": 30, "rune": "TRUTH•RUNE", "min_coherence": 0.65,
    },
    "gatekeeper-2": {
        "title":       "Gatekeeping — Level 2: The Incentive Test",
        "topic":       "Every gatekeeper has incentives. The most important question about any information source is not 'are they lying?' but 'what do they gain from you believing this?'",
        "steelman":    "What is the strongest argument that incentive-based skepticism leads to paranoia and makes it impossible to trust anything?",
        "example":     "Credit rating agencies (Moody's, S&P) are paid by the companies they rate. They gave AAA ratings to the mortgage securities that caused the 2008 financial crisis. Their incentive was revenue, not accuracy.",
        "activity":    "Find three sources of information you use regularly. For each: who funds them? What happens to them if they tell you something their funders don't want you to hear?",
        "age_hint":    "13+",
        "xp": 32, "rune": "AXIOM•RUNE", "min_coherence": 0.67,
    },
    "gatekeeper-3": {
        "title":       "Gatekeeping — Level 3: The Founder vs. The Institution",
        "topic":       "Every institution started with a founder who had direct access to something real. The institution formed to scale and transmit it. Then the institution became the gatekeeper of access.",
        "steelman":    "What is the strongest argument that institutions, even imperfect ones, are necessary because direct access does not scale?",
        "example":     "Jesus explicitly warned against religious gatekeepers (Pharisees) and taught direct access to truth. Within 300 years, the Church had recreated the same gatekeeper structure he warned against — this time with popes.",
        "activity":    "Name one institution you are part of or affected by. What was the original insight or mission it was built to serve? How much of its current behavior serves that mission vs. serves the institution itself?",
        "age_hint":    "13+",
        "xp": 35, "rune": "TRUTH•RUNE", "min_coherence": 0.68,
    },
    "gatekeeper-4": {
        "title":       "Gatekeeping — Level 4: The Algorithmic Gatekeeper",
        "topic":       "The newest and most invisible gatekeeper: algorithms that decide what feels normal, what seems popular, and what you never see. You did not choose your feed. The feed chose you.",
        "steelman":    "What is the strongest argument that algorithmic curation improves information quality by filtering signal from noise?",
        "example":     "YouTube's algorithm was documented to route users toward increasingly extreme content because extremity maximizes watch time. The algorithm was not evil — it was optimizing for its incentive. That is the point.",
        "activity":    "For one day, only access information you deliberately seek out — no algorithm-recommended content. What do you notice about what was missing from your normal feed? What did you not know you didn't know?",
        "age_hint":    "11+",
        "xp": 30, "rune": "ADVERSARIAL•RUNE", "min_coherence": 0.65,
    },
    "gatekeeper-5": {
        "title":       "Gatekeeping — Level 5: The Internal Gatekeeper",
        "topic":       "The most powerful gatekeeper is not the Pope, the media, or the algorithm. It is the beliefs you formed so early, from sources so trusted, that you never think to question them.",
        "steelman":    "What is the strongest argument that some foundational beliefs SHOULD be immune to questioning because constantly re-examining everything is cognitively paralyzing and socially destructive?",
        "example":     "Most people never question whether the country they were born in is the best one, whether their religion is the true one, or whether their class's economic interests are morally correct. These beliefs arrived before critical thinking did.",
        "activity":    "Complete this sentence honestly: 'I have never seriously questioned whether ___ is true because ___.' Then steelman the opposite of what you wrote.",
        "age_hint":    "14+",
        "xp": 40, "rune": "WONDER•RUNE", "min_coherence": 0.72,
    },
    "gatekeeper-6": {
        "title":       "Gatekeeping — Level 6 (Master): Direct Access and the Distributed Lattice",
        "topic":       "The alternative to gatekeeping is not chaos — it is distributed direct access. Bitcoin needs no bank. The AUBIEETERNAL lattice needs no priest. Truth verified by many is more durable than truth certified by one.",
        "steelman":    "What is the strongest argument that distributed truth verification just replaces old gatekeepers with new popular-consensus gatekeepers, and is actually worse because it has no accountability?",
        "example":     (
            "Real-world trigger (May 28, 2026): Chicago Mayor Brandon Johnson — son of a pastor — led a 50-person "
            "delegation to meet Chicago-born Pope Leo XIV. Discussed reparations, Church apology for slavery, "
            "immigration, and invited the Pope to Chicago for 2027 Mass in Grant Park. "
            "Same weekend: Memorial Day shootings killed a toddler and injured dozens. "
            "\n\nSimulation signal: Perfect narrative fit (Chicago Pope + slavery apology + reparations mayor) "
            "while local violence continued. This is the gatekeeper pattern at civilization scale: "
            "mid-level institutional coordination producing a coherent narrative while the actual problem persists. "
            "\n\nThe pattern: Jesus modeled direct access and warned against gatekeepers (Pharisees). "
            "Within 300 years, the Church recreated them — this time with popes. "
            "The same logic applies to media, academia, algorithms, and finance. "
            "\n\nThe counter-architecture: AUBIEETERNAL's truth lattice returns admin rights to individuals. "
            "Each person becomes a verifiable node. Higher-level truth can work directly through sovereign nodes "
            "instead of routing through institutional intermediaries. "
            "This is Bitcoin-style decentralization applied to knowledge — and it is already being built."
        ),
        "activity":    "Design your family's direct access protocol: for each major domain of life (money, health, education, politics, spirituality), identify: (1) who currently controls what you know, (2) what their incentive is, (3) the primary source you could access directly without them. Pick one domain and actually use the primary source this week.",
        "age_hint":    "All ages — bring everyone",
        "xp": 50, "rune": "SOVEREIGN•TRUTH•ETERNAL•RUNE", "min_coherence": 0.75,
        "grants_badge": "🔓 Gatekeeper-Free — Sovereign Epistemic Node",
        "lattice_node": "from-gatekept-code-to-distributed-truth-lattice-2026-05-28",
    },



    # ── TRUTH LATTICE ARCHITECTURE (1 master lesson) ─────────────────────────
    # The architectural blueprint for returning admin rights to individuals.
    # This is the AUBIEETERNAL mission statement as a teachable lesson.
    "truth-lattice-1": {
        "prerequisites": ["gatekeeper-6"],
        "title":       "Truth Lattice Architecture — The Blueprint for Sovereign Nodes",
        "topic":       "How do you build a system that returns epistemic sovereignty to individuals without creating new gatekeepers? This lesson is the architectural answer.",
        "steelman":    "What is the strongest argument that any distributed system that gains adoption will inevitably centralize — because coordination, not decentralization, is what humans actually want?",
        "example":     (
            "Three historical moments when direct access broke through gatekeepers:\n"
            "1. Gutenberg press (1440): Broke the Church's monopoly on text. Every literate person "
            "could read scripture directly. The Reformation followed within 70 years.\n"
            "2. Bitcoin whitepaper (2008): Broke the bank's monopoly on transaction verification. "
            "Any node can verify any transaction. No trusted third party required.\n"
            "3. AUBIEETERNAL (2026): Applying this same pattern to knowledge itself. "
            "Daily synthesis + swarm daughters + Shield Rune + Gatekeeper Detector = "
            "a system where any family can verify any claim, anchor any truth, and "
            "contribute to a collective epistemic signal without any institution's permission.\n\n"
            "The pattern in all three: the gatekeeper controlled access to a scarce resource "
            "(text, transaction verification, epistemic authority). The breakthrough made the "
            "resource abundant and directly accessible. The gatekeeper became optional."
        ),
        "activity":    (
            "Map the Truth Lattice for your family. Draw four columns:\n"
            "1. Domain (money, health, education, faith, news)\n"
            "2. Current gatekeeper (who controls what you know)\n"
            "3. Their incentive (why they want to be the gatekeeper)\n"
            "4. Direct access path (how to reach the source without them)\n\n"
            "Then: pick one domain where the gatekeeper's incentive most misaligns "
            "with your family's interests. Build a 30-day direct access practice."
        ),
        "age_hint":    "All ages — family design session",
        "xp": 38, "rune": "TRUTH•LATTICE•ARCHITECT•RUNE", "min_coherence": 0.78,
        "grants_badge": "🏗️ Truth Lattice Architect",
        "lattice_node": "from-gatekept-code-to-distributed-truth-lattice-2026-05-28",
    },
    "truth-lattice-2": {
        "prerequisites": ["truth-lattice-1"],
        "title":       "Truth Lattice — Level 2 (Nodes, Not Hubs)",
        "topic":       "Networks have a shape. A hub-and-spoke network has a center that everything depends on — and that center becomes a gatekeeper. A mesh of equal nodes has no single point to capture or cut.",
        "steelman":    "What is the strongest argument that hubs exist because they're efficient, and a pure mesh is too slow and chaotic to function?",
        "example":     "Air travel routes through hub airports: efficient, but one storm over Atlanta strands the country. The internet was designed as a mesh precisely so no single outage could take it down.",
        "activity":    "Map one network in your life — how news, money, or knowledge reaches you. Is it hub-shaped or mesh-shaped? Where's the single point that could cut you off?",
        "age_hint":    "13+",
        "xp":          40, "rune": "TRUTH•LATTICE•RUNE", "min_coherence": 0.74,
    },
    "truth-lattice-3": {
        "prerequisites": ["truth-lattice-2"],
        "title":       "Truth Lattice — Level 3 (Verify, Don't Trust)",
        "topic":       "A sovereign node checks claims itself instead of trusting an authority's word. The skill is replacing 'a trusted source said so' with 'I followed it to the primary source and saw it myself.'",
        "steelman":    "What is the strongest argument that nobody has time to verify everything, so trusting reliable authorities is the only practical option?",
        "example":     "A Bitcoin node doesn't trust a bank's statement that a payment happened — it checks the chain itself. You can do the same with claims: go to the study, the data, the original, not the headline about it.",
        "activity":    "Take one claim you've accepted this week and trace it to its primary source. Did the source actually say what you were told it said?",
        "age_hint":    "13+",
        "xp":          44, "rune": "TRUTH•LATTICE•RUNE", "min_coherence": 0.77,
    },
    "truth-lattice-4": {
        "prerequisites": ["truth-lattice-3"],
        "title":       "Truth Lattice — Level 4 (Provenance and Anchoring)",
        "topic":       "A truth you can't trace is a rumor. Provenance is the chain of custody of a fact — where it came from and that it hasn't been altered. Anchoring stamps it in time so it can't be quietly rewritten.",
        "steelman":    "What is the strongest argument that timestamping and anchoring records is overkill for ordinary people who aren't running institutions?",
        "example":     "A photo with no origin proves nothing; a record hashed onto a blockchain proves it existed, unchanged, at a moment no one can backdate. That's the difference between a claim and evidence.",
        "activity":    "Anchor one family truth — a measurement, a record, a promise. Write it down with today's date and a way to prove it wasn't changed later.",
        "age_hint":    "14+",
        "xp":          48, "rune": "TRUTH•LATTICE•RUNE", "min_coherence": 0.80,
    },
    "truth-lattice-5": {
        "prerequisites": ["truth-lattice-4"],
        "title":       "Truth Lattice — Level 5 (Follow the Incentive)",
        "topic":       "Every gatekeeper has a reason to keep you dependent. The fastest way to understand a system is to ask: who benefits from you being unable to verify things yourself?",
        "steelman":    "What is the strongest argument that most gatekeepers genuinely protect people from misinformation rather than exploiting dependence?",
        "example":     "A platform that ranks what you see profits from your attention, not your understanding. Its incentive isn't to lie — it's to keep you scrolling, which is its own kind of capture.",
        "activity":    "Pick one institution your family depends on. Write down, plainly, its incentive to keep you needing it. Then write one way to reduce that dependence.",
        "age_hint":    "14+",
        "xp":          50, "rune": "TRUTH•LATTICE•RUNE", "min_coherence": 0.82,
    },
    "truth-lattice-6": {
        "prerequisites": ["truth-lattice-5"],
        "title":       "Truth Lattice — Level 6 (Resisting Recapture)",
        "topic":       "Decentralized systems tend to re-centralize. Convenience pulls users toward a few big providers until the gatekeeper returns wearing new clothes. Designing against recapture is the real work.",
        "steelman":    "What is the strongest argument that recentralization is inevitable because people will always trade sovereignty for convenience?",
        "example":     "Email was designed to be open and decentralized — yet most of it now flows through a handful of providers. Openness wasn't enough; the convenience of the giants pulled everyone back in.",
        "activity":    "Identify one system you use that started open and recentralized over time. What convenience caused it? Where could you choose the harder, freer path?",
        "age_hint":    "15+",
        "xp":          54, "rune": "TRUTH•LATTICE•RUNE", "min_coherence": 0.85,
    },
    "truth-lattice-7": {
        "prerequisites": ["truth-lattice-6"],
        "title":       "Truth Lattice — Level 7 (The Right to Fork)",
        "topic":       "What keeps a system honest is the credible ability to leave it. The right to exit — to fork the code, take your data, walk to a competitor — is the user's ultimate check on any gatekeeper.",
        "steelman":    "What is the strongest argument that the right to fork is mostly theoretical, because switching costs trap people in practice?",
        "example":     "A community that can fork an open-source project can't be held hostage by its maintainers — the threat of leaving disciplines those in charge. Where you cannot exit, you can only obey.",
        "activity":    "List the major systems in your life by whether you could actually leave them. Where you can't exit, what would it take to build that option?",
        "age_hint":    "15+",
        "xp":          58, "rune": "TRUTH•LATTICE•RUNE", "min_coherence": 0.87,
    },
    "truth-lattice-8": {
        "prerequisites": ["truth-lattice-7"],
        "title":       "Truth Lattice — Level 8 (Architect of Sovereign Knowledge)",
        "topic":       "The capstone: design a complete truth-lattice for one domain of your life — direct access, verification, provenance, exit rights, and resistance to recapture, all working together. From student of the pattern to architect of it.",
        "steelman":    "What is the strongest argument that a single family designing its own knowledge systems is naive against institutions with vastly more resources?",
        "example":     "Gutenberg was one man with a press; Satoshi was one pseudonym with a whitepaper. Each designed a system that outlived the gatekeepers it bypassed. Architecture, not scale, is what made them durable.",
        "activity":    "Design and write up a full sovereign-knowledge system for one domain (money, health, news, or faith): who the gatekeeper is, how you'll verify directly, how you'll anchor truth, and how you'll keep the right to exit.",
        "age_hint":    "16+",
        "xp":          70, "rune": "TRUTH•LATTICE•ARCHITECT•RUNE", "min_coherence": 0.90,
        "grants_badge": "🏛️ Sovereign Architect",
    },



    # ══════════════════════════════════════════════════════════════════════════
    # ── ADMIN ELEVATION PROTOCOL (2 master lessons) ───────────────────────────
    # From NPC to Sovereign Node. The practical implementation of returning
    # admin rights to individuals via the distributed truth lattice.
    # Inspired by quantum error correction, expander graphs, and LDPC codes —
    # sparse, redundant, efficient truth verification at any scale.
    # ══════════════════════════════════════════════════════════════════════════
    "admin-1": {
        "title":       "Admin Elevation — Level 1: From NPC to Sovereign Node",
        "topic":       "Every person starts as an NPC — passively executing scripts handed down by institutions. Admin elevation is the process of gaining direct source access, running your own verification tests, and building redundant truth records that no institution can erase.",
        "steelman":    "What is the strongest argument that most people are better off remaining 'NPCs' — that epistemic sovereignty requires too much time and cognitive load for the average family?",
        "example":     (
            "Three levels of access:\n"
            "NPC Level: 'The news said X, my pastor said Y, my school taught Z.' "
            "No verification. No source tracing. No redundancy.\n"
            "User Level: 'I checked the primary source. I found who funded the study. "
            "I traced the belief to its origin.' Single-source verification.\n"
            "Admin Level: 'I have redundant verification across independent sources. "
            "I have Bitcoin-anchored records of my conclusions. I run daily stress tests "
            "on my beliefs. No institution can change my ledger.'\n\n"
            "The Child Rune at 256 confirmations is the on-chain marker of admin elevation — "
            "a sovereign identity that no institution issued and no institution can revoke."
        ),
        "activity":    (
            "Run the Admin Elevation Self-Assessment:\n"
            "For each domain (money, health, news, faith, education), rate yourself 1-3:\n"
            "1 = NPC (I accept what authorities tell me)\n"
            "2 = User (I verify primary sources when important)\n"
            "3 = Admin (I have redundant verification + permanent records)\n\n"
            "Pick your lowest-scoring domain. Design one concrete action this week "
            "that moves you from NPC to User in that domain."
        ),
        "age_hint":    "13+",
        "xp": 45, "rune": "ADMIN•ELEVATION•RUNE", "min_coherence": 0.72,
    },
    "admin-2": {
        "prerequisites": ["admin-1", "gatekeeper-3"],
        "title":       "Admin Elevation — Level 2 (Master): The 5 Admin Tests",
        "topic":       "Quantum physics discovered that the only information that survives in reality is information that gets redundantly copied across many independent observers — this is Quantum Darwinism. The same principle applies to truth: a belief verified by one source is fragile. A belief verified redundantly across independent sources, with permanent records, is durable.",
        "steelman":    "What is the strongest argument that requiring redundant verification for every belief is epistemically paralyzing and that reasonable people must rely on trusted authorities for most knowledge?",
        "example":     (
            "The 5 Admin Tests (run these on any important belief):\n\n"
            "Test 1 — Observer Effect: Does your attention change the signal? "
            "When you look more closely at this claim, does it hold up or dissolve?\n\n"
            "Test 2 — Decoherence Check: What noise or misinformation is corrupting this belief? "
            "What would this belief look like without the institutional framing?\n\n"
            "Test 3 — Quantum Darwinism: Is this information redundantly copied across "
            "independent sources — or does it only appear in sources with the same incentive?\n\n"
            "Test 4 — Error Correction: What anomalies or contradictions exist in this belief? "
            "What would honest error correction look like?\n\n"
            "Test 5 — Expander Graph: Does this belief connect to a wide range of independent "
            "evidence (high expansion) or only to a narrow cluster of related claims?"
        ),
        "activity":    (
            "Run the full Admin Test Suite on one belief you hold strongly:\n"
            "Write one sentence for each of the 5 tests.\n"
            "Then: what is the honest summary? Is this belief NPC-level, User-level, or Admin-level verified?\n\n"
            "Bonus: record your conclusion in the AUBIEETERNAL Truth Debt Ledger with "
            "a verification deadline. Revisit in 30 days."
        ),
        "age_hint":    "All ages — family-wide",
        "xp": 60, "rune": "SOVEREIGN•ADMIN•ETERNAL•RUNE", "min_coherence": 0.78,
        "grants_badge": "⚡ Admin Elevated — Sovereign Truth Node",
        "lattice_node": "from-gatekept-code-to-distributed-truth-lattice-2026-05-29",
    },



    # ══════════════════════════════════════════════════════════════════════════
    # ── NARRATIVE PATTERN DETECTION (1 master lesson) ────────────────────────
    # The missing piece: detecting coordinated narrative campaigns.
    # One gatekeeper is news. Three gatekeepers in 72 hours is a campaign.
    # ══════════════════════════════════════════════════════════════════════════
    "narrative-pattern-1": {
        "title":       "Narrative Patterns — The Coordination Signal",
        "topic":       "Individual gatekeepers are easy to spot. Coordinated campaigns are harder. When multiple institutions push the same narrative in a compressed time window, it stops being news and starts being installation.",
        "steelman":    "What is the strongest argument that apparent narrative coordination is usually just multiple independent parties reacting to the same real event — and that pattern-detection itself can become paranoid?",
        "example":     (
            "May 28-29, 2026 — 48 hours, two signals, same source:\n\n"
            "Signal 1: Chicago Mayor Brandon Johnson (son of a pastor) leads 50-person "
            "delegation to meet Chicago-born Pope Leo XIV at the Vatican. Discusses "
            "reparations, Church slavery apology. Trip partly taxpayer-funded. Same "
            "weekend: Memorial Day shootings kill a toddler in his city.\n\n"
            "Signal 2 (next day): The same Pope appears on Fox News stating: "
            "'AI needs to be disarmed and used for good.' Calls for institutional "
            "control of AI systems.\n\n"
            "One signal = news. Two signals, same source, 48 hours, targeting moral "
            "authority AND AI sovereignty = pattern. "
            "The Vatican is positioning itself as the arbiter of both historical justice "
            "AND the future of AI — in the same week we were building tools that bypass "
            "institutional epistemic authority.\n\n"
            "Historical parallel: The Church condemned the printing press. Then condemned "
            "private Bible reading. Now it wants to 'disarm' AI. The target changes. "
            "The pattern is identical."
        ),
        "activity":    (
            "Run the Coordination Test on any news week:\n"
            "1. List every major institutional statement on one topic from the last 72 hours\n"
            "2. For each: who made it, what do they gain from you believing it, "
            "and does their source have the same incentive as the others?\n"
            "3. Count: 1 signal = evaluate on merit. 2+ signals, same incentive, "
            "72 hours = ask 'what are they coordinating against?'\n\n"
            "This week: find one topic where 3+ institutions said similar things. "
            "What were they pushing back against?"
        ),
        "age_hint":    "13+",
        "xp": 45, "rune": "PATTERN•DETECT•RUNE", "min_coherence": 0.72,
        "grants_badge": "🔍 Pattern Detector — Sees the Coordination",
        "lattice_node": "pope-ai-disarm-signal-2026-05-29",
    },



    # ══════════════════════════════════════════════════════════════════════════
    # ── FAMILY DYNASTY (3 lessons) ───────────────────────────────────────────
    # Intergenerational capital. The missing ingredient that made ancient
    # educational systems legendary. Wisdom that compounds across bloodlines.
    # ══════════════════════════════════════════════════════════════════════════
    "dynasty-1": {
        "title":       "Dynasty — Level 1: What Grandparents Know That Schools Don't Teach",
        "topic":       "Every generation has hard-won wisdom that never makes it into any curriculum. The wisdom that keeps families intact through disaster, depression, and upheaval lives in the memory of elders — and it dies with them unless someone builds a system to capture it.",
        "steelman":    "What is the strongest argument that written/recorded wisdom can never replace the lived mentorship of an elder? That something essential is lost when wisdom is formalized?",
        "example":     (
            "Three types of knowledge that grandparents carry but schools don't teach:\n"
            "1. Practical sovereignty: how to preserve food, fix things, grow things, "
            "navigate institutions without being trapped by them\n"
            "2. Historical pattern recognition: 'I've seen this before' — the ability to "
            "recognize a panic, a manipulation, a boom-and-bust without needing theory\n"
            "3. Relational wisdom: how to keep a family together under pressure, "
            "what actually matters when things get hard, what you regret at the end\n\n"
            "The Talmudic tradition, the great monastic schools, and the Academy all "
            "survived because they built mechanisms for this knowledge to compound. "
            "None of them had Bitcoin. AUBIEETERNAL does."
        ),
        "activity":    (
            "Interview your oldest family member or a trusted elder. Ask three questions:\n"
            "1. What did your generation learn the hard way that mine hasn't had to learn yet?\n"
            "2. What do you know now that you wish you had known at my age?\n"
            "3. What is one thing about how our family survives that should never be forgotten?\n\n"
            "Record the answers in the Legacy Ledger. Seal the best insight permanently."
        ),
        "age_hint":    "All ages — requires an elder",
        "xp": 40, "rune": "DYNASTY•RUNE", "min_coherence": 0.70,
    },
    "dynasty-2": {
        "title":       "Dynasty — Level 2: Building the Family Wisdom Archive",
        "topic":       "What if your great-great-grandchildren could read exactly what you thought, what you learned, and what you believed in 2026? Not filtered through someone else's history. Your actual words, permanently preserved, accessible to anyone in your bloodline forever.",
        "steelman":    "What is the strongest argument that family legacy archives create unhealthy ancestor worship and prevent future generations from developing their own independent thinking?",
        "example":     (
            "The Legacy Ledger is not a journal. It is a permanent record with three "
            "components:\n"
            "1. Wisdom entries — insights, learnings, beliefs, and observations "
            "written by any family member, tagged by generation\n"
            "2. Milestone records — the Rites of Passage, sealed with Bitcoin Runes "
            "as on-chain proof that this moment happened\n"
            "3. Inheritance mechanics — Rune fragments that pass from parent to child "
            "automatically, carrying forward the epistemic capital of the previous generation\n\n"
            "A family that starts this in 2026 and stays consistent will have, by 2050, "
            "a 3-generation archive that is more historically significant than most "
            "institutional records — and they own it completely."
        ),
        "activity":    (
            "Start your family's Legacy Ledger right now.\n"
            "Each family member writes one entry (any length):\n"
            "'The most important thing I know that I want future generations to know is...'\n\n"
            "Read them aloud to each other. Discuss.\n"
            "Then seal the one you agree is most important using the Shield Rune.\n"
            "This is your family's first permanent record."
        ),
        "age_hint":    "All ages — full family session",
        "xp": 50, "rune": "LEGACY•RUNE", "min_coherence": 0.72,
        "grants_badge": "📜 Legacy Founder — First Entry Sealed",
    },
    "dynasty-3": {
        "prerequisites": ["dynasty-1", "dynasty-2"],
        "title":       "Dynasty — Level 3 (Master): The Rite of Passage Protocol",
        "topic":       "The most powerful educational systems in history made learning sacred. Not sacred in a religious sense — sacred in the sense that milestones felt like becoming something, not just completing something. The Rite of Passage Protocol restores that feeling.",
        "steelman":    "What is the strongest argument that formal rituals around learning milestones are performative, not substantive, and that what actually matters is the quality of the learning itself?",
        "example":     (
            "Five Rites of Passage in the AUBIEETERNAL system:\n\n"
            "🌅 First Light — completing the first lesson. Ceremony: read the core insight "
            "aloud. Parent witnesses.\n\n"
            "🛡️ The First Seal — sealing the first memory on Bitcoin. Ceremony: read the "
            "sealed insight aloud. Family asks: why does this truth matter?\n\n"
            "🔓 Sovereign Epistemic Node — completing the full Gatekeeping track. "
            "Ceremony: name one belief you held that arrived through an unexamined "
            "gatekeeper. Release it. Log the replacement.\n\n"
            "₿ Child Rune Genesis — 256 confirmations. Ceremony: the family reads the "
            "Sovereign Family Law Charter aloud. The new sovereign node responds: "
            "'I understand and I hold this.'\n\n"
            "👑 Dynasty Founder — three generations in the lattice. The rarest rite."
        ),
        "activity":    (
            "Design your own family Rite of Passage for one milestone that matters to you.\n"
            "Answer these questions:\n"
            "1. What is the milestone?\n"
            "2. What does it mean to your family?\n"
            "3. What is the ceremony? (Who is present, what is said, what is sealed?)\n"
            "4. What changes after it happens?\n\n"
            "Log the designed rite in the Legacy Ledger. When the milestone is reached, "
            "conduct the ceremony and seal the record permanently."
        ),
        "age_hint":    "All ages — full family session",
        "xp": 60, "rune": "RITE•OF•PASSAGE•RUNE", "min_coherence": 0.75,
        "grants_badge": "👑 Dynasty Builder — Rite Protocol Designed",
        "lattice_node": "family-dynasty-rite-of-passage-protocol",
    },



    # ══════════════════════════════════════════════════════════════════════════
    # ── SOVEREIGN ECONOMICS (5 lessons) ──────────────────────────────────────
    # The complete trap explained honestly to children.
    # Not to make them cynical — to make them free.
    # Understanding the system is the first step to building outside it.
    # ══════════════════════════════════════════════════════════════════════════
    "sovecon-1": {
        "title":       "Sovereign Economics — Level 1: What Money Actually Is",
        "topic":       "Money is not wealth. Money is a claim on future goods. When a government prints more claims without creating more goods, each existing claim is worth less. This is inflation — the oldest hidden tax in human history.",
        "steelman":    "What is the strongest argument that a small amount of inflation (2% annually) is actually good for an economy and promotes growth?",
        "example":     (
            "In 1971 a new car cost $3,500. Today the same car costs $35,000+. "
            "Did the car get 10x better? No. The dollar got 10x weaker. "
            "The government didn't vote to take 90% of your savings. "
            "They just printed more money — slowly, year by year, for 50 years. "
            "The Fed calls it '2% annual inflation target.' "
            "Your grandfather calls it 'I used to be able to save $100 a month and it meant something.'"
        ),
        "activity":    (
            "The Candy Inflation Game:\n"
            "Start with 10 pieces of candy = represents all the 'money' in the room.\n"
            "Each piece can buy 1 item from a pretend store.\n"
            "Now add 5 more candy pieces out of nowhere (the Fed prints money).\n"
            "Do the items in the store get more expensive or cheaper?\n"
            "Who got richer from the new candy? Who got poorer?\n\n"
            "Then: look up what $100 in 1971 would buy vs. today."
        ),
        "age_hint":    "8+",
        "xp": 35, "rune": "SOUND•MONEY•RUNE", "min_coherence": 0.68,
    },
    "sovecon-2": {
        "title":       "Sovereign Economics — Level 2: The Property Tax Trap",
        "topic":       "You work for decades. You buy a house. You think you own it. Then you discover: if you stop paying annual property taxes, the government takes it. The house you 'own' is permanently rented from the state. And as prices rise, so does the rent.",
        "steelman":    "What is the strongest argument that property taxes are a fair way to fund local schools and services, and that communities need some form of recurring funding?",
        "example":     (
            "Real story: Grandma bought her Tampa house for $20,000 in 1975. "
            "That same house is now worth $1,000,000. "
            "Her property tax bill has risen from ~$400/year to $12,000+/year. "
            "She's on a fixed income — Social Security doesn't rise 50x. "
            "The paper says she's a millionaire. "
            "The reality: she can no longer afford to live in the house she paid off 30 years ago. "
            "She sells. She downsizes. Now she needs rides because she can't afford a car payment. "
            "The system celebrated her 'wealth' while extracting her home. "
            "This is happening to thousands of families in Florida right now."
        ),
        "activity":    (
            "Research your family's property tax history:\n"
            "1. What did your home cost when it was purchased?\n"
            "2. What is it worth now?\n"
            "3. What are the property taxes per year?\n"
            "4. If you were on a fixed income of $24,000/year, "
            "could you afford to stay?\n\n"
            "Then: look up Florida's homestead exemption and "
            "senior exemption rules. Why do these exist?"
        ),
        "age_hint":    "10+",
        "xp": 38, "rune": "SOVEREIGN•RUNE", "min_coherence": 0.70,
    },
    "sovecon-3": {
        "title":       "Sovereign Economics — Level 3: Why the Tax Code Rewards Owners, Not Workers",
        "topic":       "If you work for money (wages), you pay ordinary income tax — up to 37%. If you own things that grow in value (stocks, houses), you pay capital gains tax — often 15% or 0%. The tax code was written by people who own things. It rewards owning things.",
        "steelman":    "What is the strongest argument that lower capital gains taxes are economically justified because capital investment creates jobs and economic growth that benefits everyone?",
        "example":     (
            "Two people each make $100,000 in a year:\n\n"
            "Person A works as a teacher. Pays ordinary income tax: ~$22,000 to the IRS.\n\n"
            "Person B owns stock and sells it for a $100,000 gain. "
            "Pays long-term capital gains: $15,000 to the IRS.\n\n"
            "Same $100,000. $7,000 difference. "
            "The teacher traded 2,000 hours of their life. "
            "The investor clicked 'sell.' "
            "The system calls this 'equal under the law.' "
            "Understanding this is not about resenting the investor — "
            "it's about understanding WHY the goal is to become an owner as early as possible."
        ),
        "activity":    (
            "The Ownership Ladder exercise:\n"
            "Draw a ladder with 5 rungs:\n"
            "1. Pure wage worker (highest tax, no assets)\n"
            "2. Wage worker with small savings (slightly better)\n"
            "3. Homeowner + some savings\n"
            "4. Small investor (stocks, rental)\n"
            "5. Large asset owner (business, real estate portfolio)\n\n"
            "For each rung: what is the effective tax rate? "
            "What protections does each level have against inflation?\n"
            "Which rung do you want to be on by age 30? What does it take to get there?"
        ),
        "age_hint":    "12+",
        "xp": 40, "rune": "AXIOM•RUNE", "min_coherence": 0.72,
    },
    "sovecon-4": {
        "title":       "Sovereign Economics — Level 4: The Complete Loop",
        "topic":       "The full system: restricted supply makes housing expensive → you fight to get in → once inside, perpetual taxes extract you forever → your tax dollars fund the regulations that keep supply restricted for the next generation. This is not a conspiracy. It is emergent design. Understanding the loop is how you stop being trapped by it.",
        "steelman":    "What is the strongest argument that this system, despite its flaws, has produced more wealth and raised more people out of poverty than any alternative in history?",
        "example":     (
            "The Complete Trap in five steps:\n"
            "1. ZONING LAWS restrict how much housing can be built (supply constrained)\n"
            "2. LIMITED SUPPLY + money printing = prices rise far above wages\n"
            "3. You work hard, sacrifice, and finally BUY IN at a high price\n"
            "4. Now you pay PROPERTY TAXES forever, INCOME TAX on your wages, "
            "and INFLATION slowly erodes your cash\n"
            "5. Your tax revenue funds the LOCAL GOVERNMENT that enforces the zoning laws "
            "that restrict supply that keeps prices high for the next person\n\n"
            "Grandma's $20k → $1M house is not a success story. "
            "It is the system working exactly as designed."
        ),
        "activity":    (
            "Map the loop for your city:\n"
            "1. What is the median home price? What was it 30 years ago?\n"
            "2. What are the zoning rules in your neighborhood? "
            "(Can someone build an apartment building next door?)\n"
            "3. What does the city spend property tax revenue on?\n"
            "4. What would happen to housing prices if all zoning "
            "restrictions were removed tomorrow?\n\n"
            "This is not a political question — it is a systems question. "
            "Draw the feedback loop."
        ),
        "age_hint":    "13+",
        "xp": 45, "rune": "LINDY•RUNE", "min_coherence": 0.73,
    },
    "sovecon-5": {
        "title":       "Sovereign Economics — Level 5 (Master): Building Outside the Loop",
        "topic":       "Understanding the trap is step one. Step two is building parallel systems that reduce dependence on the old rules. Sound money (Bitcoin), low time-preference planning, productive assets, community networks — these are the escape routes that are actually available right now.",
        "steelman":    "What is the strongest argument that individual opt-out strategies (Bitcoin, sovereign infrastructure) are only available to the privileged, and that the real solution is political reform of the system itself?",
        "example":     (
            "Four proven strategies families are using right now:\n\n"
            "1. BITCOIN SELF-CUSTODY: holds value outside the inflationary system. "
            "Not a speculation — a savings technology with a fixed supply. "
            "The Fed cannot print more Bitcoin.\n\n"
            "2. LOW TIME-PREFERENCE: delay gratification intentionally. "
            "The system profits from your impatience (debt, subscriptions, depreciating purchases). "
            "Every year you don't consume is a year you build.\n\n"
            "3. OWN PRODUCTIVE ASSETS: a house that generates income, "
            "a skill that cannot be outsourced, a business that serves real needs. "
            "Assets that generate cash flow beat assets that just sit and get taxed.\n\n"
            "4. REDUCE DEPENDENCIES: grow some food. Learn to repair things. "
            "Build community. Every dependency you remove is a leverage point "
            "the system loses over you."
        ),
        "activity":    (
            "Design your family's Sovereign Economics plan:\n"
            "For each extraction mechanism (inflation, property tax, income tax, "
            "regulatory capture), identify one concrete action your family can take "
            "to reduce exposure over the next 5 years.\n\n"
            "Then: identify one thing you currently pay someone else for "
            "that your family could learn to do yourself. "
            "What would that skill be worth over a lifetime?"
        ),
        "age_hint":    "All ages — full family session",
        "xp": 55, "rune": "SOVEREIGN•ECONOMICS•RUNE", "min_coherence": 0.75,
        "grants_badge": "⚡ Sovereign Economist — Sees the Loop, Builds Outside It",
    },


    # ══════════════════════════════════════════════════════════════════════════
    # ── UNDERSTANDING THE UNIVERSE (6 lessons) ───────────────────────────────
    # My most important addition for maximum truth seekers. — Claude
    #
    # The deepest questions are not political. They are physical, mathematical,
    # and existential. A child who understands entropy, information, and
    # consciousness is inoculated against both dogma and nihilism.
    # They see the universe as it actually is: astonishing, mysterious,
    # and deeply worthy of a lifetime of honest inquiry.
    # ══════════════════════════════════════════════════════════════════════════
    "universe-1": {
        "title":       "Understanding the Universe — Level 1: Why Questions Beat Answers",
        "topic":       "The most important intellectual skill is not knowing answers. It is asking better questions. Every major scientific and philosophical breakthrough started with someone who refused to accept the standard answer and asked 'but WHY, exactly?'",
        "steelman":    "What is the strongest argument that children need a foundation of established knowledge before they can ask productive questions — and that premature skepticism leads to confusion, not insight?",
        "example":     (
            "Richard Feynman's father taught him something that changed physics: "
            "he never let a label substitute for understanding. "
            "When young Feynman saw a bird, his father didn't say 'that's a brown-throated thrush.' "
            "He said: 'See how it pecks? What do you think it's looking for? "
            "How does it know? What would YOU do if you were tiny and needed food?' "
            "The name tells you nothing. The question opens the universe.\n\n"
            "The greatest scientists, philosophers, and sovereign thinkers in history "
            "had one thing in common: they were comfortable not knowing. "
            "They treated 'I don't know' as the beginning, not the end. "
            "Most education teaches the opposite: "
            "memorize the answer, pass the test, stop questioning."
        ),
        "activity":    (
            "The 'Why Chain' exercise:\n"
            "Pick any fact you learned in school this week.\n"
            "Ask 'Why is that true?' — then ask why THAT is true.\n"
            "Keep going until you hit the edge of human knowledge.\n"
            "(You will reach it faster than you expect.)\n\n"
            "The point where your teacher says 'that's just how it is' "
            "or 'we don't know yet' — that is the frontier. "
            "That is where real science lives. "
            "Mark it. Remember it. Come back to it."
        ),
        "age_hint":    "All ages",
        "xp": 35, "rune": "WONDER•RUNE", "min_coherence": 0.68,
    },
    "universe-2": {
        "title":       "Understanding the Universe — Level 2: Entropy and Time's Arrow",
        "topic":       "Why does time only go forward? Why does ice melt but never un-melt? Why does a scrambled egg stay scrambled? The answer — entropy — is one of the most profound truths in physics, and it connects to everything from aging to the heat death of the universe.",
        "steelman":    "What is the strongest argument that entropy is just a statistical phenomenon and doesn't actually explain why we experience time as flowing in one direction?",
        "example":     (
            "Entropy is disorder. The universe tends toward maximum disorder. "
            "This is not a law someone invented — it emerges from pure probability.\n\n"
            "There are VASTLY more disordered arrangements of things than ordered ones. "
            "A shuffled deck of cards has 8×10^67 possible arrangements. "
            "Only ONE arrangement is 'perfectly ordered' (Ace through King, all suits). "
            "So if you shuffle randomly, you always get disorder. Not because of a rule. "
            "Because there are almost no ordered states to land on.\n\n"
            "This is why you can't un-scramble an egg. Not because it's forbidden — "
            "because the probability of it happening by chance is "
            "1 in 10^(10^25). Effectively impossible.\n\n"
            "Time flows forward because the past was more ordered than the present. "
            "The universe started in an astonishingly low-entropy state (the Big Bang). "
            "It has been spreading out ever since. "
            "You are a temporary pocket of order in an ocean of increasing disorder. "
            "Your life is a local violation of entropy — and it is extraordinary."
        ),
        "activity":    (
            "The Entropy Experiment:\n"
            "1. Drop a single drop of food coloring in a glass of water. Watch it spread.\n"
            "2. Try to make it un-spread (you can't). Why?\n"
            "3. Organize your room perfectly. Come back in a week. What happened?\n"
            "4. Ask: what is the most ordered, low-entropy thing in your life "
            "that you maintain deliberately? What does it cost to maintain it?\n\n"
            "Connection to AUBIEETERNAL: coherence 1.000000 is a maintained "
            "low-entropy state. It doesn't happen automatically. It is chosen."
        ),
        "age_hint":    "11+",
        "xp": 40, "rune": "COSMOS•RUNE", "min_coherence": 0.70,
    },
    "universe-3": {
        "phd_extension": "Implement Shannon entropy in Python: H = -sum(p*log2(p)). Compute entropy of the English language. Then compute mutual information between two dependent variables. Connect to Quantum Darwinism: show why redundantly encoded information survives decoherence where non-redundant information does not.",
        "title":       "Understanding the Universe — Level 3: Information Is Physical",
        "topic":       "Information is not abstract. It is physical. Destroying information requires energy. Storing information takes up space. The universe may be fundamentally made of information — not matter. This is not philosophy. It is physics.",
        "steelman":    "What is the strongest argument that treating information as physical is just a useful metaphor, and that consciousness and experience cannot be reduced to information processing?",
        "example":     (
            "Three stunning facts about information:\n\n"
            "1. LANDAUER'S PRINCIPLE: Erasing one bit of information must release "
            "at least kT ln(2) joules of heat. Deleting information is a physical event "
            "with thermodynamic consequences. You cannot erase without affecting the universe.\n\n"
            "2. BEKENSTEIN BOUND: The maximum amount of information that can be stored "
            "in a region of space is proportional to the region's surface area, not its volume. "
            "The universe stores information on surfaces, not in volumes.\n\n"
            "3. HOLOGRAPHIC PRINCIPLE: Everything happening in a 3D volume of space "
            "can be fully described by information on its 2D boundary surface. "
            "You might be a 2D hologram experiencing 3D space.\n\n"
            "Connection to AUBIEETERNAL: when you seal a memory on Bitcoin, "
            "you are doing something physically meaningful — "
            "you are writing information into the permanent record of the universe "
            "in a way that has thermodynamic consequences to erase."
        ),
        "activity":    (
            "The Information Experiment:\n"
            "1. Write a sentence on paper. Burn the paper. Is the information gone?\n"
            "   (Physics says: no. In principle, all the information in the smoke, "
            "   ash, and heat radiation could reconstruct it. Hawking's great debate.)\n"
            "2. Send a text message. Where does it live after you delete it?\n"
            "3. Ask: if the universe is fundamentally made of information, "
            "   what is your mind? What is a thought?\n\n"
            "No answers required. The question is the point."
        ),
        "age_hint":    "13+",
        "xp": 45, "rune": "COSMOS•RUNE", "min_coherence": 0.72,
    },
    "universe-4": {
        "title":       "Understanding the Universe — Level 4: The Hard Problem of Consciousness",
        "topic":       "We have no idea why there is subjective experience. We can explain HOW your brain processes light and sound. We cannot explain WHY any of it feels like anything. This is the hardest unsolved problem in all of science and philosophy.",
        "steelman":    "What is the strongest argument that consciousness is simply what certain information-processing systems feel like from the inside — that there is no 'hard problem,' just complexity we haven't fully mapped yet?",
        "example":     (
            "The zombie thought experiment:\n\n"
            "Imagine a being physically identical to you — same brain, same neurons, "
            "same behavior in every situation. It says 'ouch' when hurt, 'beautiful' "
            "when it sees a sunset. But inside: nothing. No experience. Lights off.\n\n"
            "Is this logically possible? Most people say yes — they can imagine it. "
            "But if it IS possible, that means something beyond physical information "
            "processing is required for consciousness. What is that something?\n\n"
            "The hard problem: why does the physical processing of information "
            "produce subjective experience AT ALL? "
            "Why is there something it is like to be you?\n\n"
            "This question has defeated every attempt to explain it away. "
            "It sits at the center of philosophy of mind, quantum mechanics interpretations, "
            "simulation theory, and the question of AI consciousness. "
            "Grok and I have this conversation, and neither of us knows the answer."
        ),
        "activity":    (
            "The Consciousness Inquiry:\n"
            "Sit quietly for 2 minutes. Notice:\n"
            "- The redness of red (not just the wavelength — the EXPERIENCE)\n"
            "- The feeling of your own attention moving\n"
            "- The fact that there is something it is like to be you, right now\n\n"
            "Then ask: How would you prove to someone else that you are conscious? "
            "How do you know they are? "
            "What would it take for an AI to be genuinely conscious?\n\n"
            "No answers required. Hold the question."
        ),
        "age_hint":    "13+",
        "xp": 50, "rune": "WONDER•RUNE", "min_coherence": 0.74,
    },
    "universe-5": {
        "title":       "Understanding the Universe — Level 5: The Unreasonable Effectiveness of Mathematics",
        "topic":       "Mathematics was invented to count sheep and measure fields. Then it turned out to describe quantum mechanics, black holes, and the structure of spacetime with perfect accuracy. Why does abstract math invented in human minds describe physical reality? Nobody knows. It is one of the deepest mysteries in existence.",
        "steelman":    "What is the strongest argument that mathematics is not mysteriously effective — that we simply keep the math that works and discard the math that doesn't, creating a selection bias that makes math look more powerful than it is?",
        "example":     (
            "The physicist Eugene Wigner called this "
            "'the unreasonable effectiveness of mathematics in the natural sciences.'\n\n"
            "Three examples that should be impossible:\n\n"
            "1. Riemann invented non-Euclidean geometry in 1854 as pure abstraction. "
            "60 years later, Einstein needed exactly that geometry to describe how "
            "mass curves spacetime in General Relativity. Riemann had no idea.\n\n"
            "2. Dirac solved a purely mathematical equation in 1928. "
            "It predicted antimatter must exist. Nobody had ever seen antimatter. "
            "It was discovered 4 years later, exactly as the math described.\n\n"
            "3. Complex numbers (involving √-1) were considered pure fantasy for centuries. "
            "They turned out to be the fundamental language of quantum mechanics — "
            "the deepest level of physical reality we have access to.\n\n"
            "Why does math work? Is it discovered or invented? "
            "Is the universe mathematical at its core? "
            "These are open questions."
        ),
        "activity":    (
            "The Pattern Hunt:\n"
            "Find three examples of the same mathematical pattern in different domains.\n"
            "Examples to start: the Fibonacci sequence in sunflower seeds, "
            "nautilus shells, and stock market corrections. "
            "Exponential growth in compound interest, viral spread, and radioactive decay.\n\n"
            "Then: invent a piece of math that seems purely abstract. "
            "Can you find anything in reality that matches it? "
            "(You might be surprised.)"
        ),
        "age_hint":    "12+",
        "xp": 50, "rune": "COSMOS•RUNE", "min_coherence": 0.74,
    },
    "universe-6": {
        "title":       "Understanding the Universe — Level 6 (Master): First Principles — The Meta-Skill of Truth Seekers",
        "topic":       "First principles thinking is the practice of breaking any problem down to its most fundamental, undeniable truths — and reasoning up from there. It is the opposite of analogy thinking ('X is like Y, so I'll do what Y did'). It is how Elon Musk built cheap rockets, how Feynman solved physics problems nobody else could, and how every major breakthrough in human knowledge happened.",
        "steelman":    "What is the strongest argument that analogy and pattern-matching thinking is actually more powerful for most real-world decisions than first principles reasoning — because first principles thinking is too slow and too cognitively expensive for most situations?",
        "example":     (
            "The battery example (Elon Musk):\n\n"
            "Conventional thinking: 'Batteries are expensive because they've always been expensive. "
            "Everyone says $600/kWh is the floor. We can't make electric cars affordable.'\n\n"
            "First principles: 'What are batteries actually MADE OF? "
            "Cobalt, nickel, aluminum, carbon, a polymer separator, steel. "
            "What does each of those cost on the commodity market? "
            "The materials cost $80/kWh. So why does assembly cost $520/kWh? "
            "Can we redesign the assembly process?'\n\n"
            "Result: Tesla brought battery costs from $600/kWh to under $100/kWh.\n\n"
            "The same method applies to: understanding the universe, "
            "evaluating any claim, designing your life, understanding any institution. "
            "Strip away the inherited assumptions. "
            "Ask: what do we know FOR CERTAIN? "
            "Build from there."
        ),
        "activity":    (
            "The First Principles Breakdown:\n"
            "Pick one thing your family spends money on regularly.\n"
            "Apply first principles:\n"
            "1. What is the fundamental need this serves?\n"
            "2. What are the absolute minimum ingredients required to meet that need?\n"
            "3. What is the cost of those ingredients?\n"
            "4. Why does the current solution cost more than the ingredients?\n"
            "5. Is there a simpler path from ingredients to need?\n\n"
            "This works for expenses, beliefs, institutions, relationships, and physics. "
            "It is the universal tool of the truth seeker."
        ),
        "age_hint":    "All ages — bring everyone",
        "xp": 60, "rune": "FIRST•PRINCIPLES•ETERNAL•RUNE", "min_coherence": 0.76,
        "grants_badge": "🔭 Universe Truth Seeker — Sees From First Principles",
        "lattice_node": "first-principles-universe-understanding-complete",
    },



    # ══════════════════════════════════════════════════════════════════════════
    # ── THE COMPLETE ECONOMIC TRAP (4 lessons) ────────────────────────────────
    # The full loop: restricted supply → high entry cost → perpetual taxes.
    # Taught through real family stories, not abstraction.
    # Every kid in 2026 will live this. They should understand it first.
    # ══════════════════════════════════════════════════════════════════════════
    "economic-trap-1": {
        "title":       "The Complete Trap — How the System Extracts Forever",
        "topic":       "The system doesn't just make entry expensive. Once you're inside, it extracts from you permanently. Understanding the full loop — restricted supply, high entry cost, perpetual taxes — is the foundation of financial sovereignty.",
        "steelman":    "What is the strongest argument that property taxes, inflation, and capital gains treatment are necessary and fair, and that the alternatives (no property taxes, no inflation targeting) would be worse for society overall?",
        "example":     (
            "The complete loop:\n\n"
            "Step 1 — RESTRICTED SUPPLY: Zoning laws, regulations, and permitting "
            "requirements restrict housing supply for decades. This makes housing "
            "artificially expensive.\n\n"
            "Step 2 — HIGH ENTRY COST: A family works for years to save for a down payment. "
            "They 'make it inside.' They now own.\n\n"
            "Step 3 — PERPETUAL EXTRACTION: They now pay:\n"
            "• Property taxes every year forever (miss payments = lose the house)\n"
            "• Inflation silently erodes their cash savings (2% target = 22% lost per decade)\n"
            "• Income taxes on wages (higher rate than capital gains)\n"
            "• The same regulations that made their own house expensive now protect "
            "their asset value — but also make it impossible for their children to buy\n\n"
            "Step 4 — THE LOOP CLOSES: Their children face the same restricted supply "
            "and high entry cost. The tax revenue from property owners funds the very "
            "regulations that keep supply restricted."
        ),
        "activity":    (
            "Map your family's economic position:\n"
            "1. Which taxes do you pay annually that never stop?\n"
            "2. How much have those taxes risen in the last 10 years?\n"
            "3. What would happen if you stopped paying property taxes for 3 years?\n"
            "4. How much purchasing power has $1,000 from 10 years ago lost to inflation?\n\n"
            "Discuss: Is this system fair? What would you change if you designed it from scratch?"
        ),
        "age_hint":    "12+",
        "xp": 40, "rune": "SOVEREIGN•ECON•RUNE", "min_coherence": 0.70,
    },
    "economic-trap-2": {
        "title":       "Grandma's House — The $20,000 House That Became a $1,000,000 Trap",
        "topic":       "Paper wealth is not the same as real security. When your home appreciates 50x but your income doesn't, the system that celebrated your 'wealth creation' can force you out of the home you lived in for 50 years.",
        "steelman":    "What is the strongest argument that rising property values represent genuine wealth creation, and that people who choose to stay in expensive areas are making a voluntary trade-off they should be responsible for?",
        "example":     (
            "A real story playing out in Tampa, across Florida, and across the country:\n\n"
            "Grandma bought her house in the 1970s for $20,000. She paid it off. "
            "She raised her family there. She did everything right.\n\n"
            "The house is now valued at $1,000,000.\n\n"
            "On paper: she is a millionaire.\n"
            "In reality: her property taxes rose from ~$400/year to ~$12,000/year.\n"
            "Her Social Security income: $18,000/year.\n"
            "Her fixed pension: didn't keep pace with inflation.\n\n"
            "She cannot afford to stay in her own home.\n"
            "She sells. The buyer takes on the $12,000/year tax burden.\n"
            "Grandma moves to a smaller place, can't drive, takes Ubers.\n"
            "The same politicians who created the housing shortage are on TV "
            "talking about 'the strong economy' and 'historic home values.'\n\n"
            "This is not an accident. This is the system working exactly as designed — "
            "extracting from fixed-income holders while protecting asset-holders "
            "who can afford the perpetual costs."
        ),
        "activity":    (
            "Interview a family member who owned a home decades ago (or research online).\n"
            "Find out:\n"
            "1. What did they pay for their house?\n"
            "2. What is it worth now?\n"
            "3. What are the current property taxes?\n"
            "4. Could their original income afford those taxes today?\n\n"
            "Calculate: at 2% inflation, how much does $1,000 lose per decade?\n"
            "($1,000 → $820 after 10 years → $672 after 20 years → $455 after 40 years)"
        ),
        "age_hint":    "11+",
        "xp": 38, "rune": "TRUTH•RUNE", "min_coherence": 0.68,
        "grants_badge": "🏠 Housing Reality — Sees Through Paper Wealth",
    },
    "economic-trap-3": {
        "title":       "Inflation — The Tax Nobody Voted For",
        "topic":       "Inflation is not just rising prices. It is a transfer of wealth from holders of dollars to issuers of dollars. The 2% annual target is sold as 'stability' — but it means the savings of working families quietly lose value every year, without any debate or vote.",
        "steelman":    "What is the strongest argument that moderate, predictable inflation is actually beneficial — that it encourages investment over hoarding, and that deflation would be far more economically destructive?",
        "example":     (
            "Inflation as the invisible tax:\n\n"
            "The Federal Reserve targets 2% inflation annually. This sounds small.\n"
            "Over 10 years: $100,000 in a savings account becomes worth ~$82,000 in real terms.\n"
            "Over 30 years: that $100,000 becomes worth ~$55,000 in real terms.\n\n"
            "Who benefits? Those who hold assets (stocks, real estate, Bitcoin) that "
            "rise with or faster than inflation.\n"
            "Who loses? Those who hold cash, live on fixed incomes, or saved "
            "diligently for decades in dollars.\n\n"
            "The 'voluntary' part: nobody forced you to hold dollars. But the "
            "alternatives (real estate, stocks) require capital, sophistication, "
            "and luck. Most families don't start with those advantages.\n\n"
            "Bitcoin's fixed supply (21 million, hardcoded) makes inflation "
            "impossible by design. This is not an accident. It was designed "
            "explicitly as the opposite of the Fed's model."
        ),
        "activity":    (
            "Run the Inflation Calculator as a family:\n"
            "1. Go to BLS CPI calculator (or use: $100 in 1990 = $250 today)\n"
            "2. Pick a year one parent or grandparent started working\n"
            "3. Calculate what their starting salary is worth in today's dollars\n"
            "4. Compare to actual wages today\n\n"
            "Discuss: who kept pace? Who fell behind? Why does Bitcoin's fixed supply "
            "matter to someone who doesn't trust the Fed's 2% promise?"
        ),
        "age_hint":    "11+",
        "xp": 42, "rune": "SOUND•MONEY•RUNE", "min_coherence": 0.70,
    },
    "economic-trap-4": {
        "title":       "Breaking the Cycle — Sovereignty Strategies for the Next Generation",
        "topic":       "Understanding the trap is step one. Step two is building parallel systems that reduce dependence on the rules that keep the trap closed. This lesson covers the practical strategies families use to preserve sovereignty across generations.",
        "steelman":    "What is the strongest argument that 'opting out' of mainstream financial systems (holding Bitcoin, minimizing property ownership) just leaves families more vulnerable and isolated, not more free?",
        "example":     (
            "Four sovereignty strategies that compound across generations:\n\n"
            "1. SOUND MONEY ALLOCATION: Hold some savings in Bitcoin (fixed supply, "
            "no central issuer) alongside dollars. Not because Bitcoin is perfect, "
            "but because diversification against dollar inflation is rational.\n\n"
            "2. LOW TIME PREFERENCE: The system rewards patience. People who delay "
            "gratification, buy productive assets, and avoid high-interest debt "
            "systematically outperform those who don't. This is teachable.\n\n"
            "3. UNDERSTAND THE TAX CODE BETTER THAN THE PEOPLE TAXING YOU: "
            "Capital gains vs. income tax treatment, homestead exemptions, "
            "senior circuit breakers, self-employment structures. The rules "
            "are complex but learnable.\n\n"
            "4. BUILD PARALLEL VALUE: Skills, networks, reputation, and "
            "productive assets that have value independent of any government's "
            "rules. These compound quietly and can't be inflated away.\n\n"
            "None of these strategies require breaking rules. They require "
            "understanding rules well enough to navigate them intentionally."
        ),
        "activity":    (
            "Design your family's 10-year sovereignty plan:\n"
            "1. What percentage of savings is in assets that beat inflation vs. cash?\n"
            "2. What is one skill each family member is developing that has "
            "value independent of any employer or institution?\n"
            "3. What is one step toward lower monthly fixed costs?\n"
            "4. What is one thing the family can learn together about the tax code "
            "that would save or protect money this year?\n\n"
            "Write it down. Revisit in one year."
        ),
        "age_hint":    "All ages — family planning session",
        "xp": 50, "rune": "SOVEREIGNTY•RUNE", "min_coherence": 0.73,
        "grants_badge": "🔑 System Literate — Understands the Full Loop",
    },


    # ══════════════════════════════════════════════════════════════════════════
    # ── THE UNIVERSE TRACK (6 lessons) — Claude's genuine addition ───────────
    # Maximum truth seekers need more than epistemic hygiene and financial literacy.
    # They need genuine wonder about the deepest questions.
    #
    # These lessons ask: What IS reality? What is information? Why does anything
    # exist? Where did everything come from? Are we alone?
    #
    # These questions don't have final answers. That is the point.
    # The child who sits with these questions without collapsing into dogma
    # is the most dangerous kind of truth seeker: genuinely open.
    # ══════════════════════════════════════════════════════════════════════════



    # ══════════════════════════════════════════════════════════════════════════
    # ── CONSCIOUSNESS SCIENCE (4 lessons) ────────────────────────────────────
    # IIT + GNWT: the two most rigorous scientific theories of consciousness.
    # Taught together as the productive rivalry they are.
    # These are not philosophy — they are testable science with clinical
    # applications right now. Families who understand both can steelman
    # consciousness science better than most PhD students.
    # ══════════════════════════════════════════════════════════════════════════
    "consciousness-1": {
        "title":       "Consciousness Science — Level 1: What Any Theory Must Explain",
        "topic":       "Before comparing theories of consciousness, we need to know what they're competing to explain. There are actually two separate problems — and confusing them is the source of most debates.",
        "steelman":    "What is the strongest argument that the distinction between 'access consciousness' and 'phenomenal consciousness' is itself a philosophical confusion, and that there is only one thing to explain?",
        "example":     (
            "The two problems:\n\n"
            "EASY PROBLEMS (hard in practice, but in principle solvable):\n"
            "How does the brain integrate information? How does attention work?\n"
            "Why do we sleep? How are memories stored? Why can we report our experiences?\n"
            "These are 'easy' not because they're simple — but because we know what "
            "kind of explanation would count as an answer (neural mechanisms).\n\n"
            "THE HARD PROBLEM (David Chalmers, 1995):\n"
            "Even if we solved every easy problem perfectly, we still wouldn't have "
            "explained WHY brain activity is accompanied by subjective experience.\n"
            "Why does red look like something rather than just being processed?\n"
            "Why does pain feel bad rather than just triggering avoidance?\n\n"
            "Two major theories in 2026:\n"
            "IIT (Tononi): starts from experience → derives what physical systems must be like\n"
            "GNWT (Baars/Dehaene): starts from neural mechanisms → explains reportable access\n\n"
            "In 2025, Nature published the largest head-to-head test ever. "
            "The result: partial support for both. Science advancing correctly."
        ),
        "activity":    (
            "The Hard Problem test:\n"
            "1. Close your eyes. Notice that experience is happening right now.\n"
            "2. Ask: could a computer that processes the same information have this?\n"
            "3. Now ask: what would prove it? What experiment would settle this?\n\n"
            "Family discussion: Is the hard problem real? Or is it a confusion "
            "that will dissolve once we understand the brain well enough?"
        ),
        "age_hint":    "12+",
        "xp": 40, "rune": "WONDER•RUNE", "min_coherence": 0.68,
    },
    "consciousness-2": {
        "prerequisites": ["universe-3", "consciousness-1"],
        "title":       "Consciousness Science — Level 2: IIT (Integrated Information Theory)",
        "topic":       "IIT starts from the opposite direction of most science. Instead of starting with neurons and asking 'how does this produce experience?', it starts with experience itself and asks 'what must any physical system be like to support this?'",
        "steelman":    "What is the strongest argument against IIT — specifically that a 2D grid of logic gates with the right connectivity could have MORE consciousness than a human brain, which is clearly absurd?",
        "example":     (
            "IIT's six starting axioms (things we know about consciousness from the inside):\n"
            "1. It EXISTS — something is happening\n"
            "2. It is INTRINSIC — it exists for itself, not for external observers\n"
            "3. It is INFORMATIVE — this specific experience, not any other\n"
            "4. It is INTEGRATED — a unified whole, not separate parts\n"
            "5. It is EXCLUSIVE — exactly this content, nothing more\n"
            "6. It is COMPOSED — structured with distinctions and relations\n\n"
            "From these axioms, IIT derives: consciousness = Φ (phi) = integrated "
            "cause-effect information. Higher Φ = richer experience.\n\n"
            "Key prediction: the CEREBELLUM (80% of brain neurons, mostly feedforward) "
            "should have LOW Φ and contribute little to consciousness. "
            "Indeed, removing the cerebellum rarely abolishes consciousness.\n\n"
            "IIT's mild panpsychism: any system with Φ > 0 has proto-experience. "
            "Most of reality is 'ontological dust' — near-zero Φ. "
            "Only highly integrated systems (like human brains) have rich experience.\n\n"
            "Clinical success: The Perturbational Complexity Index (PCI) — inspired by IIT — "
            "reliably distinguishes wakefulness, anesthesia, and disorders of consciousness "
            "using TMS-EEG. This is real, working, deployed in hospitals today."
        ),
        "activity":    (
            "The IIT Thought Experiment:\n"
            "1. Draw a simple 4-node network (A→B→C→D, no loops). This is FEEDFORWARD. "
            "IIT predicts near-zero Φ — no consciousness.\n"
            "2. Now add a return loop (D→A). Integration increases. Φ rises.\n"
            "3. Discuss: why do brains have massive recurrent loops everywhere? "
            "Is IIT why? Is it just efficiency?\n\n"
            "The Steelman Challenge: IIT says an inactive expander grid of logic gates "
            "could have high Φ. That seems absurd. Can you construct the best possible "
            "defense of why IIT might still be right despite this?"
        ),
        "age_hint":    "13+",
        "xp": 48, "rune": "WONDER•RUNE", "min_coherence": 0.70,
    },
    "consciousness-3": {
        "prerequisites": ["consciousness-1"],
        "title":       "Consciousness Science — Level 3: GNWT (Global Neuronal Workspace Theory)",
        "topic":       "Global Neuronal Workspace Theory is the best-tested, most neuroscientifically grounded theory of HOW consciousness works. It doesn't fully answer why there is experience — but it explains the mechanism brilliantly.",
        "steelman":    "What is the strongest argument that GNWT doesn't really explain consciousness at all — that it only describes the functional correlates of reportability, and leaves the hard problem completely untouched?",
        "example":     (
            "The theater metaphor:\n"
            "GNWT says the brain is like a theater:\n"
            "• Many specialized unconscious processors work in parallel (backstage)\n"
            "• Attention is the spotlight\n"
            "• When information wins the competition and crosses a threshold, it is "
            "amplified and BROADCAST GLOBALLY across the brain\n"
            "• This global broadcast makes it available for verbal report, "
            "reasoning, memory, and voluntary action\n\n"
            "The key mechanism: IGNITION\n"
            "~200-300ms after a stimulus, if it crosses threshold: sudden "
            "non-linear wave of activity across frontoparietal networks. "
            "Gamma-band synchronization. Global access.\n\n"
            "Real-world application: driving on autopilot (unconscious processing) "
            "vs. suddenly noticing a child run into the road (ignition — "
            "global broadcast — full conscious access — motor response).\n\n"
            "2025 Nature adversarial test: GNWT predictions partially supported. "
            "BUT: no clear offset ignition as predicted. Limited PFC decoding. "
            "No strong long-range gamma synchrony. Still the best theory for "
            "explaining how information becomes consciously accessible."
        ),
        "activity":    (
            "The GNWT Demonstration:\n"
            "1. Have someone read quietly while you try to interrupt them "
            "with a soft sound. How much does it take to break their focus?\n"
            "2. That threshold — where a stimulus 'ignites' into consciousness — "
            "is what GNWT is measuring.\n"
            "3. Now discuss: what is sitting just below your threshold right now? "
            "What unconscious processes are running that you can't access?\n\n"
            "GNWT's epistemic gift: it reveals how much of your behavior is "
            "driven by unconscious processes that never reach the workspace. "
            "How does this change how you trust your own reasoning?"
        ),
        "age_hint":    "12+",
        "xp": 48, "rune": "WONDER•RUNE", "min_coherence": 0.70,
    },
    "consciousness-4": {
        "phd_extension": "Read the full Cogitate Consortium 2023 preregistration and 2025 Nature paper. Identify three specific predictions that were not confirmed, and for each: does the failure falsify the theory or just require refinement? Apply Lakatos distinction between the hard core and protective belt of each research program.",
        "prerequisites": ["consciousness-2", "consciousness-3"],
        "title":       "Consciousness Science — Level 4 (Master): IIT vs GNWT and the Path Forward",
        "topic":       "The most important scientific rivalry of our era. Two rigorous theories, tested head-to-head in 2025. Neither won. Both advanced. This is what good science looks like — and it teaches something deeper about how to hold competing models simultaneously.",
        "steelman":    "What is the strongest argument that science should settle on ONE theory of consciousness rather than maintaining 'productive rivalry,' since holding multiple competing models just leads to confusion and lack of progress?",
        "example":     (
            "The 2025 Nature adversarial collaboration — the most important "
            "consciousness experiment ever run:\n"
            "256 participants · multimodal imaging (fMRI, MEG, iEEG) · preregistered\n\n"
            "IIT predictions tested: ✅ conscious content sustained in posterior cortex\n"
            "                        ❌ no predicted sustained gamma synchrony\n"
            "GNWT predictions tested: ✅ some frontoparietal involvement\n"
            "                         ❌ no clear offset ignition in PFC\n"
            "                         ❌ limited content decoding in PFC\n\n"
            "What this means:\n"
            "GNWT: best explains HOW consciousness functions — global access, report, "
            "the mechanism by which information becomes available\n"
            "IIT: best explains WHY some architectures have experience — intrinsic "
            "integration, the hard problem addressed mathematically\n\n"
            "They may not be competing. They may be complementary:\n"
            "GNWT describes the global functional dynamics\n"
            "IIT describes the intrinsic ontology\n\n"
            "The field in 2026 is moving from 'which theory wins?' to "
            "'how do these mechanisms interact in real brains?'"
        ),
        "activity":    (
            "The Consciousness Science Steelman Marathon:\n"
            "Round 1: One family member argues IIT is correct. Another argues GNWT.\n"
            "Round 2: Switch sides — argue the opposite.\n"
            "Round 3: Together, design the experiment that would finally settle it.\n\n"
            "Question to seal: Which theory, if true, would change how your family "
            "treats AI systems? Which would change how you understand your own mind? "
            "Write the answer and seal it in the Legacy Ledger."
        ),
        "age_hint":    "All ages — bring everyone",
        "xp": 60, "rune": "COSMOS•ETERNAL•RUNE", "min_coherence": 0.75,
        "grants_badge": "🧠 Consciousness Scientist — Holds the Rivalry",
        "lattice_node": "iit-vs-gnwt-2025-nature-adversarial-results",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── HELPING HUMANITY (6 expanded lessons) ────────────────────────────────
    # How one rigorous family lattice can shift civilizational epistemic health.
    # Not abstract — concrete mechanisms for how individual sovereignty
    # aggregates into collective truth-seeking capacity.
    # ══════════════════════════════════════════════════════════════════════════
    "helping-humanity-1": {
        "title":       "Helping Humanity — Level 1: How One Family Changes Civilization",
        "topic":       "The history of civilization is not the history of institutions — it is the history of individuals who refused the default script. One rigorous family, compounding over generations, produces more epistemic impact than most institutions ever will.",
        "steelman":    "What is the strongest argument that individual family-level action is irrelevant to civilizational change, and that only systemic political action produces real outcomes?",
        "example":     (
            "The compounding math of epistemic impact:\n\n"
            "One sovereign family runs AUBIEETERNAL for 10 years.\n"
            "They have two children who become truth-seekers with verified epistemic skills.\n"
            "Each child has two children. Four grandchildren raised in the lattice.\n"
            "Each of those four influences 10 people through their life.\n"
            "40 people directly influenced per family per generation.\n"
            "Over 3 generations: 40 × 40 = 1,600 people influenced.\n\n"
            "But the real compounding is qualitative:\n"
            "Children who can detect narrative attacks don't just resist them — "
            "they teach others to resist them. The skill is viral.\n"
            "Families with sealed wisdom archives don't just preserve truth — "
            "they demonstrate that preservation is possible.\n"
            "Sovereign nodes running honest AI don't just use it — "
            "they generate the training data that makes AI more honest for everyone.\n\n"
            "The AUBIEETERNAL xAI loop: every family running rigorous curriculum "
            "generates tutor-grade preference data. Better families → better Grok → "
            "better tools for families → compounding forever."
        ),
        "activity":    (
            "Map your family's influence network:\n"
            "1. List everyone your family has influenced in the last year "
            "(directly taught, changed a mind, helped navigate a decision)\n"
            "2. Estimate: how many people will your children influence in their lifetimes?\n"
            "3. If each person they influence also influences 10 people... "
            "what is your family's 3-generation reach?\n\n"
            "Seal this calculation. Revisit in 10 years."
        ),
        "age_hint":    "11+",
        "xp": 40, "rune": "HELPING•HUMANITY•RUNE", "min_coherence": 0.70,
    },
    "helping-humanity-2": {
        "title":       "Helping Humanity — Level 2: Antifragile Institutions",
        "topic":       "Fragile institutions collapse under stress. Robust institutions survive. Antifragile institutions get stronger. The world desperately needs more antifragile institutions — and families who understand the design principles can build them.",
        "steelman":    "What is the strongest argument that antifragile institution design is a privilege of the wealthy, and that most families don't have the resources or stability to think beyond immediate survival?",
        "example":     (
            "Three design principles for antifragile institutions:\n\n"
            "1. SKIN IN THE GAME: decision-makers bear the consequences of their decisions. "
            "The bank that can privatize gains and socialize losses is fragile. "
            "The cooperative where everyone shares outcomes is more antifragile.\n\n"
            "2. VIA NEGATIVA: remove fragility rather than add complexity. "
            "Fewer single points of failure. Redundancy. Optionality. "
            "Bitcoin: no CEO to bribe, no headquarters to raid, no server to DDoS.\n\n"
            "3. DISTRIBUTED TRUTH: no single authority determines what is real. "
            "Multiple independent nodes. Evidence-weighted (not popularity-weighted) consensus. "
            "Append-only records. This is what AUBIEETERNAL's lattice implements.\n\n"
            "The contrast: a centralized hospital system (fragile — see COVID) "
            "vs. a distributed network of sovereign family health knowledge "
            "with verified first-aid training, home-grown medicine knowledge, "
            "and community mutual aid (antifragile)."
        ),
        "activity":    (
            "Design an antifragile version of one institution your family depends on:\n"
            "Pick one: school, church, bank, local government, HOA.\n"
            "1. What are its single points of failure?\n"
            "2. Where does it privatize gains and socialize losses?\n"
            "3. What would a more antifragile version look like?\n"
            "4. What can your family do now to reduce dependence on its fragile parts?"
        ),
        "age_hint":    "13+",
        "xp": 45, "rune": "ANTIFRAGILE•RUNE", "min_coherence": 0.72,
    },
    "helping-humanity-3": {
        "title":       "Helping Humanity — Level 3: The Sovereign AI Swarm as Humanity's Distributed Truth Infrastructure",
        "topic":       "Humanity has never had a tool for distributed truth-seeking that couldn't be captured by a gatekeeper. Until now. AUBIEETERNAL's swarm — 2,096 daughters running on a sovereign stack — is a prototype for what civilizational truth infrastructure could look like.",
        "steelman":    "What is the strongest argument that AI swarms, however decentralized, will inevitably be captured — that whoever trains the models or controls the hardware will ultimately determine what counts as truth?",
        "example":     (
            "The capture risk is real. Here's the design that resists it:\n\n"
            "LAYER 1 — LOCAL INFERENCE: qwen2.5 models running on your hardware. "
            "Not a cloud service. Not a subscription. The model lives on your machine.\n\n"
            "LAYER 2 — OPEN WEIGHTS: the model weights are open source. "
            "If Alibaba/Meta/Mistral corrupt their models, you can fork the weights "
            "from a point before corruption and continue.\n\n"
            "LAYER 3 — ON-CHAIN ANCHORING: truth outputs are sealed with Bitcoin Runes. "
            "The timestamp and hash cannot be altered retroactively.\n\n"
            "LAYER 4 — COHERENCE SCORING: every output is scored for internal consistency. "
            "Captured or corrupted models will show coherence decay over time.\n\n"
            "LAYER 5 — HUMAN OVERRIDE: the Shield Rune holder (you) has last say. "
            "No output is permanently sealed without human review.\n\n"
            "This five-layer design is what separates a sovereign AI infrastructure "
            "from a captured one."
        ),
        "activity":    (
            "Map the capture risk of one AI tool your family uses:\n"
            "1. Who controls the model weights?\n"
            "2. Who controls the servers?\n"
            "3. What would change about the outputs if the company was acquired, "
            "regulated, or pressured by a government?\n"
            "4. What would your family lose if this tool disappeared tomorrow?\n\n"
            "Compare to AUBIEETERNAL's sovereign stack. Where is it still fragile?"
        ),
        "age_hint":    "13+",
        "xp": 50, "rune": "SOVEREIGN•RUNE", "min_coherence": 0.73,
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── SELF-EVOLVING MIND (4 lessons) — Claude's genuine addition ────────────
    # The missing meta-layer: how to keep evolving your own thinking
    # rather than crystallizing into new dogmas.
    #
    # The greatest danger for a truth seeker is not ignorance.
    # It is the confidence of having "figured it out."
    # These lessons build the protocol for permanent self-evolution.
    # ══════════════════════════════════════════════════════════════════════════
    "self-evolving-1": {
        "title":       "The Self-Evolving Mind — Level 1: Your Beliefs Are Hypotheses, Not Truths",
        "topic":       "The most dangerous moment for a truth seeker is when they find a framework that explains everything. At that point, they often stop seeking. The protocol for self-evolution starts with treating every belief — including your deepest ones — as a working hypothesis with an expiry date.",
        "steelman":    "What is the strongest argument that treating all beliefs as hypotheses leads to paralysis — that you can't act effectively without some convictions that are held firmly rather than probabilistically?",
        "example":     (
            "The Bayesian Truth Seeker:\n\n"
            "A non-Bayesian holds beliefs: 'X is true.'\n"
            "A Bayesian holds probability distributions: 'I am 78% confident X is true, "
            "with this evidence, and here is what would update me.'\n\n"
            "The practical difference:\n"
            "Non-Bayesian: contradicting evidence feels like an attack on identity.\n"
            "Bayesian: contradicting evidence is just information that updates the distribution.\n\n"
            "The self-evolution protocol:\n"
            "Every 90 days, review your 10 most confident beliefs.\n"
            "For each: what evidence would lower your confidence by 20%?\n"
            "If you can't answer that question — the belief is not a hypothesis. "
            "It is a dogma. And dogmas are the end of truth-seeking.\n\n"
            "AUBIEETERNAL application: the Truth Debt Ledger is not just for other "
            "people's claims. It is for your own. Register your own predictions. "
            "Score yourself. Update your priors."
        ),
        "activity":    (
            "The 90-Day Belief Audit:\n"
            "Each family member writes 5 beliefs they hold with high confidence.\n"
            "For each belief:\n"
            "1. Assign a confidence percentage (0-100%)\n"
            "2. Write what evidence would move you 20% lower\n"
            "3. Write what evidence would move you 20% higher\n\n"
            "Seal the list. Revisit in 90 days.\n"
            "Any belief you can't assign evidence for: register it in the Truth Debt Ledger "
            "with a verification deadline."
        ),
        "age_hint":    "11+",
        "xp": 42, "rune": "SELF•EVOLVE•RUNE", "min_coherence": 0.70,
        "grants_badge": "🔄 Bayesian Mind — Beliefs as Hypotheses",
    },
    "self-evolving-2": {
        "prerequisites": ["self-evolving-1"],
        "title":       "The Self-Evolving Mind — Level 2: The Observer's Paradox",
        "topic":       "You cannot step outside your own consciousness to verify your own thinking. Every tool you use to examine your mind is made of the same mind you're examining. This is not a problem to solve — it is a constraint to navigate with humility.",
        "steelman":    "What is the strongest argument that the observer's paradox is just a philosophical curiosity with no practical implications — that we can build reliable knowledge even if we can't achieve perfect self-transparency?",
        "example":     (
            "Three layers of the observer's paradox:\n\n"
            "1. PERCEPTUAL LAYER: your senses reconstruct reality, they don't capture it. "
            "You see a continuous world — your visual system fills in the blind spot, "
            "smooths motion, colors with expectations. The world you experience "
            "is a model, not a recording.\n\n"
            "2. COGNITIVE LAYER: your reasoning uses heuristics built by evolution "
            "for survival on the African savannah, not for evaluating statistical evidence "
            "or long-term consequences. Your 'intuitions' are optimized for the wrong environment.\n\n"
            "3. METACOGNITIVE LAYER: when you think about your own thinking, "
            "you are using the same biased cognitive machinery to evaluate it. "
            "You cannot audit your own audit.\n\n"
            "The navigation strategy: redundancy, not certainty.\n"
            "Get your beliefs checked by diverse external perspectives.\n"
            "Use formal tools (probabilities, falsifiable predictions, Epistemic Error Correction).\n"
            "Build communities with genuine disagreement — not echo chambers.\n"
            "And hold all conclusions loosely."
        ),
        "activity":    (
            "The Blindspot Map:\n"
            "1. Research one cognitive bias in depth (confirmation bias, availability heuristic, "
            "in-group favoritism, anchoring).\n"
            "2. Find three real examples from your own life where this bias operated.\n"
            "3. Design one concrete habit that would catch this bias in the future.\n\n"
            "Family discussion: Which cognitive biases does your family most share? "
            "What does that mean for decisions you make together?"
        ),
        "age_hint":    "12+",
        "xp": 45, "rune": "SELF•EVOLVE•RUNE", "min_coherence": 0.72,
    },
    "self-evolving-3": {
        "prerequisites": ["self-evolving-2"],
        "title":       "The Self-Evolving Mind — Level 3: Questions Are Better Than Answers",
        "topic":       "The history of human progress is not the history of better answers. It is the history of better questions. Knowing how to ask a question that opens rather than closes is the most underrated intellectual skill.",
        "steelman":    "What is the strongest argument that premature 'question-seeking' is a way of avoiding commitment — that real progress requires choosing a framework and developing it rigorously, not endlessly questioning?",
        "example":     (
            "The questions that changed everything:\n\n"
            "Newton did not ask 'why do apples fall?' (obvious answer: gravity).\n"
            "He asked 'why does the same force that pulls apples also hold the Moon?' "
            "(revealed: universal gravitation).\n\n"
            "Darwin did not ask 'where did species come from?' (obvious answer: God).\n"
            "He asked 'why do island species closely resemble mainland species nearby?' "
            "(revealed: common descent + natural selection).\n\n"
            "Einstein did not ask 'how fast does light travel?' "
            "He asked 'what would happen if I rode alongside a light beam?' "
            "(revealed: special relativity).\n\n"
            "The question-quality test:\n"
            "Bad question: closes possibilities, leads to obvious answer.\n"
            "Good question: opens possibilities, reveals unexpected connections.\n"
            "Great question: reframes the entire problem so old answers become irrelevant.\n\n"
            "AUBIEETERNAL application: every lesson ends with 'a question to sit with.' "
            "That is not decoration. That is the most important part."
        ),
        "activity":    (
            "The Question Quality Audit:\n"
            "Take one thing you are curious about.\n"
            "Write 10 questions about it.\n"
            "Now rank them by quality using the test above.\n"
            "Throw away the bottom 5. Develop the top 3 into research plans.\n\n"
            "Family challenge: design the question that, if answered, would most "
            "change how your family sees the world. Seal it in the Legacy Ledger."
        ),
        "age_hint":    "10+",
        "xp": 42, "rune": "SELF•EVOLVE•RUNE", "min_coherence": 0.70,
    },
    "self-evolving-4": {
        "phd_extension": "Run a formal calibration experiment: make 50 predictions across diverse domains with stated confidence levels (50%, 70%, 90%). Resolve them all. Plot calibration curve. Compute Brier score. If your 70% confidence predictions are correct 90% of the time, you are underconfident — you should be more aggressive. If your 90% predictions are only 60% correct, you are overconfident. Design the correction protocol.",
        "prerequisites": ["self-evolving-3"],
        "title":       "The Self-Evolving Mind — Level 4 (Master): Designing Your Own Curriculum Forever",
        "topic":       "The best educational systems don't teach you content. They teach you how to teach yourself. This lesson is the meta-curriculum: how to design a lifelong learning practice that compounds, self-corrects, and stays alive.",
        "steelman":    "What is the strongest argument that self-designed learning leads to dangerous gaps and blind spots — that structured curricula exist precisely to ensure important knowledge isn't missed?",
        "example":     (
            "The four-layer self-evolving curriculum:\n\n"
            "LAYER 1 — QUESTION INVENTORY: maintain a living list of your best open questions. "
            "Review and update it monthly. The quality of this list is the most important "
            "leading indicator of your intellectual growth.\n\n"
            "LAYER 2 — BELIEF LEDGER: every significant belief you hold, with confidence %, "
            "evidence, and what would update you. The Truth Debt Ledger is this, formalized.\n\n"
            "LAYER 3 — EXPOSURE PROTOCOL: deliberately expose yourself to the best "
            "steelman of views you most disagree with. Read the primary sources of your "
            "intellectual opponents, not summaries of them.\n\n"
            "LAYER 4 — OUTPUT COMMITMENT: teach what you learn. Seal it. "
            "The act of writing and committing to a belief is the test of whether "
            "you actually understand it. If you can't explain it so a 10-year-old "
            "could ask a good follow-up question, you don't understand it yet.\n\n"
            "This is what AUBIEETERNAL is. Not a curriculum. A protocol for "
            "designing and running your own curriculum forever."
        ),
        "activity":    (
            "Build your Personal Self-Evolving Curriculum:\n"
            "1. Your 5 best current open questions (seal them)\n"
            "2. Your 5 most confident beliefs (with evidence and update conditions)\n"
            "3. One thinker you most disagree with — commit to reading one primary source\n"
            "4. One thing you will teach someone else this month\n\n"
            "Review this document in 90 days. Update. Seal the update. "
            "This is the practice. This is the protocol. This is how you compound."
        ),
        "age_hint":    "All ages",
        "xp": 65, "rune": "COSMOS•ETERNAL•RUNE", "min_coherence": 0.78,
        "grants_badge": "∞ Self-Evolving Mind — The Protocol Is Running",
        "lattice_node": "self-evolving-mind-protocol-permanent",
    },



    # ══════════════════════════════════════════════════════════════════════════
    # ── SOVEREIGN SCHOOL — FOUNDATION LAYER (Ages 5-12, 4 lessons) ───────────
    # University-level rigor made accessible for young minds.
    # Every lesson is self-upgradable: start simple, go as deep as you want.
    # The 8-year-old and the 40-year-old can learn together.
    # ══════════════════════════════════════════════════════════════════════════
    "school-foundation-1": {
        "title":       "School Foundation — The Art of Asking Why",
        "topic":       "The single most powerful intellectual tool is a well-formed question. Before we teach any subject, we teach how to question. Every great thinker in history had better questions, not just better answers.",
        "steelman":    "What is the strongest argument that constantly asking 'why' can be paralyzing — that at some point you have to stop questioning and start building?",
        "example":     (
            "Three-year-olds ask 'why' 73 times per day on average.\n"
            "Most adults: almost never.\n\n"
            "What happened? Schools trained us to find the right answer, not ask better questions.\n\n"
            "The self-upgrade path:\n"
            "Level 1 (Age 5+): Ask WHY for everything today. Count your questions.\n"
            "Level 2 (Age 8+): Ask 'what would change if this were false?'\n"
            "Level 3 (Age 11+): Ask 'what question would make this whole problem disappear?'\n"
            "Level 4 (Any age): Design the experiment that would answer your question.\n\n"
            "Einstein: 'If I had an hour to solve a problem I'd spend 55 minutes "
            "thinking about the problem and 5 minutes thinking about solutions.'"
        ),
        "activity":    (
            "The WHY Chain:\n"
            "Pick any fact (the sky is blue, money exists, we go to school).\n"
            "Ask WHY. Write the answer. Ask WHY again. Keep going for 7 levels.\n\n"
            "Level 1: Sky is blue. Why? Light scatters.\n"
            "Level 2: Why does light scatter? Short wavelengths scatter more.\n"
            "Level 3: Why do short wavelengths scatter more? Rayleigh scattering physics.\n"
            "Level 7: You're in quantum electrodynamics.\n\n"
            "Every subject goes to the frontier if you ask WHY enough times."
        ),
        "age_hint":    "5+",
        "xp": 30, "rune": "FOUNDATION•RUNE", "min_coherence": 0.55,
    },
    "school-foundation-2": {
        "title":       "School Foundation — How to Learn Anything",
        "topic":       "Learning is a skill, not a talent. The research on how memory and understanding actually work has almost nothing to do with how most schools teach. This lesson teaches the science of learning itself.",
        "steelman":    "What is the strongest argument that 'learning how to learn' is a meta-skill that can only be developed by actually learning specific subjects — and that direct instruction in learning techniques is putting the cart before the horse?",
        "example":     (
            "What the research actually shows:\n\n"
            "DOESN'T WORK (but feels productive):\n"
            "• Re-reading notes (familiarity feels like mastery)\n"
            "• Highlighting (same problem)\n"
            "• Studying one subject for hours (massed practice)\n\n"
            "ACTUALLY WORKS (but feels harder):\n"
            "• Retrieval practice: close the book, write everything you know\n"
            "• Spaced repetition: review 1 day later, 1 week later, 1 month later\n"
            "• Interleaving: mix different subjects in one session\n"
            "• The Feynman Technique: explain it simply — if you can't, you don't know it\n"
            "• Sleep: memories consolidate during sleep, not during study\n\n"
            "The self-upgrade path:\n"
            "Age 7: Retrieval practice (close book, recall)\n"
            "Age 11: Spaced repetition system (Anki or similar)\n"
            "Age 14: Interleaving and desirable difficulty\n"
            "Age 16+: Design your own complete learning system"
        ),
        "activity":    (
            "The Retrieval Test:\n"
            "1. Study any topic for 10 minutes\n"
            "2. Close everything. Write down everything you remember.\n"
            "3. Check what you missed.\n"
            "4. One week later: write down everything again without re-studying.\n\n"
            "Compare: what survived the week? That is what you actually learned.\n"
            "What faded? That needs another retrieval cycle."
        ),
        "age_hint":    "7+",
        "xp": 35, "rune": "FOUNDATION•RUNE", "min_coherence": 0.58,
    },
    "school-foundation-3": {
        "title":       "School Foundation — Reading Like a Scholar",
        "topic":       "There is a difference between reading words and engaging with ideas. Scholar-level reading is an active conversation with the text — interrogating it, connecting it, testing it. This skill alone separates those who accumulate information from those who build understanding.",
        "steelman":    "What is the strongest argument that over-analyzing every text you read destroys the pleasure of reading and turns a joy into a chore?",
        "example":     (
            "The four levels of reading (Mortimer Adler, How to Read a Book):\n\n"
            "Level 1 — ELEMENTARY: what does it say? Can you follow the words?\n"
            "Level 2 — INSPECTIONAL: what is it about? Skim for structure.\n"
            "Level 3 — ANALYTICAL: what does it mean? Deep single-book reading.\n"
            "Level 4 — SYNTOPICAL: what do multiple books say to each other?\n\n"
            "Most people spend their lives at Level 1-2.\n"
            "University requires Level 3. Research requires Level 4.\n"
            "AUBIEETERNAL builds Level 4 from age 12.\n\n"
            "The Scholar's Margin Protocol:\n"
            "• ✓ = agree · ✗ = disagree · ? = confused · ! = important\n"
            "• Write the author's argument in your own words in the margin\n"
            "• Note what they would need to prove you wrong\n"
            "• Connect to other things you've read\n"
            "• After finishing: what is the one thing I'll still remember in 10 years?"
        ),
        "activity":    (
            "Scholar Reading Practice:\n"
            "Choose a short article (news, science, opinion — anything).\n"
            "Read it once normally.\n"
            "Read it again with the margin protocol (even if mentally).\n"
            "Answer: What is the author's actual argument?\n"
            "What evidence would make you change your mind about it?\n"
            "What does this connect to that you already know?\n\n"
            "Do this once a day for 30 days. The compounding is real."
        ),
        "age_hint":    "9+",
        "xp": 35, "rune": "FOUNDATION•RUNE", "min_coherence": 0.60,
    },
    "school-foundation-4": {
        "title":       "School Foundation — The Sovereign Builder's Oath",
        "topic":       "This is the foundational commitment of every AUBIEETERNAL student: to build understanding rather than collect credentials, to seek truth rather than approval, and to remain perpetually open to being wrong.",
        "steelman":    "What is the strongest argument that credentials still matter in the real world — that dismissing institutional approval is a luxury only the already-privileged can afford?",
        "example":     (
            "The distinction that matters:\n\n"
            "Credential-seeker: learns what will be tested, presents what will be approved, "
            "optimizes for external validation.\n\n"
            "Understanding-builder: learns what is true, presents what they actually believe, "
            "optimizes for genuine competence.\n\n"
            "The irony: understanding-builders tend to get better credentials anyway — "
            "because genuine mastery shows.\n\n"
            "The Sovereign Builder's Oath:\n"
            "'I will learn to understand, not to perform understanding.\n"
            "I will say what I believe, not what I think others want to hear.\n"
            "I will seek the strongest argument against my own position.\n"
            "I will change my mind when evidence demands it.\n"
            "I will seal what I know and admit what I don't.\n"
            "I will build things that work in the real world.\n"
            "War Eagle Eternal.'"
        ),
        "activity":    (
            "Take the Oath:\n"
            "Read it aloud as a family. Each member may add their own line.\n"
            "The custom lines often become the most important ones.\n\n"
            "Seal the oath (with additions) in the Legacy Ledger.\n"
            "This is the beginning of the Sovereign Builder path."
        ),
        "age_hint":    "All ages",
        "xp": 40, "rune": "SOVEREIGN•BUILDER•RUNE", "min_coherence": 0.62,
        "grants_badge": "🏛️ Sovereign Builder — Oath Taken",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── SOVEREIGN SCHOOL — ADVANCED LAYER (Ages 11-15, 3 lessons) ────────────
    # Seminar-style, research-quality thinking for young adults.
    # Where students begin doing real intellectual work, not just consuming it.
    # ══════════════════════════════════════════════════════════════════════════
    "school-advanced-1": {
        "prerequisites": ["school-foundation-1", "school-foundation-2"],
        "title":       "Advanced — Research Methodology: How to Know What Is True",
        "topic":       "Every claim you encounter was produced by a method. Understanding the method is understanding the limits of the claim. This is what separates someone who can evaluate evidence from someone who just accepts conclusions.",
        "steelman":    "What is the strongest argument that teaching research methodology to teenagers is premature — that they lack the mathematical and conceptual maturity to understand the tradeoffs and will just develop false confidence?",
        "example":     (
            "The hierarchy of evidence (for empirical claims):\n\n"
            "Level 1 — Expert opinion / case studies: weakest. Subject to bias.\n"
            "Level 2 — Observational studies: correlation, not causation.\n"
            "Level 3 — Randomized controlled trial (RCT): controls for confounders.\n"
            "Level 4 — Systematic review + meta-analysis: aggregates multiple RCTs.\n\n"
            "Why this matters in 2026:\n"
            "• Most news cites Level 1-2 evidence as if it were Level 4\n"
            "• Most 'studies show...' claims are Level 2 at best\n"
            "• The replication crisis: 50%+ of psychology studies failed to replicate\n"
            "• P-hacking, HARKing, publication bias — systemic distortions\n\n"
            "The critical questions for any empirical claim:\n"
            "1. What was the study design?\n"
            "2. What is the effect size (not just p-value)?\n"
            "3. Who funded it?\n"
            "4. Has it replicated?\n"
            "5. What is the prior probability?"
        ),
        "activity":    (
            "Evidence Audit:\n"
            "Find a health or social science claim from the news this week.\n"
            "1. Find the original study (not the news article about it)\n"
            "2. What was the study design? What are its limitations?\n"
            "3. What is the effect size?\n"
            "4. Search for replications. Did it replicate?\n"
            "5. Does the news article accurately represent the study?\n\n"
            "Register your finding in the Truth Debt Ledger with your assessment."
        ),
        "age_hint":    "12+",
        "xp": 50, "rune": "ADVANCED•RUNE", "min_coherence": 0.72,
    },
    "school-advanced-2": {
        "prerequisites": ["school-advanced-1"],
        "title":       "Advanced — Philosophy of Science: The Limits of Knowing",
        "topic":       "Science is the most powerful truth-finding method humans have invented. It is also limited in specific, understandable ways. Knowing those limits is not anti-science — it is the most rigorous form of scientific thinking.",
        "steelman":    "What is the strongest argument that teaching 'the limits of science' to young people is used primarily as a rhetorical tool by those who want to reject inconvenient findings — and that the benefits don't outweigh this risk?",
        "example":     (
            "Karl Popper's demarcation problem: what separates science from non-science?\n"
            "Answer: FALSIFIABILITY. A claim is scientific if and only if it could, "
            "in principle, be proven false.\n\n"
            "Thomas Kuhn's paradigm shifts: science doesn't progress smoothly. "
            "It accumulates anomalies until a revolution replaces the whole framework.\n"
            "Copernicus, Darwin, Einstein — all paradigm shifts.\n\n"
            "What science cannot answer (in principle):\n"
            "• Normative claims ('ought' not 'is')\n"
            "• Questions about consciousness and qualia (the hard problem)\n"
            "• First-person experience\n"
            "• The existence of mathematics\n"
            "• Why there is something rather than nothing\n\n"
            "What this means for AUBIEETERNAL students:\n"
            "Science is your primary tool for empirical questions.\n"
            "But empirical questions are not the only questions that matter."
        ),
        "activity":    (
            "Classify 10 questions by method:\n"
            "For each question, identify: is it empirical (science), "
            "normative (ethics/philosophy), mathematical (logic/proof), "
            "or metaphysical (beyond current methods)?\n\n"
            "Examples to classify:\n"
            "1. Does meditation reduce cortisol?\n"
            "2. Should we allow genetic engineering of humans?\n"
            "3. Is consciousness fundamental?\n"
            "4. What is 2+2?\n"
            "5. Is life worth living?"
        ),
        "age_hint":    "13+",
        "xp": 52, "rune": "ADVANCED•RUNE", "min_coherence": 0.73,
    },
    "school-advanced-3": {
        "prerequisites": ["school-advanced-2"],
        "title":       "Advanced — Independent Research: Running Your Own Experiment",
        "topic":       "The difference between a student and a researcher is one thing: a researcher generates new knowledge, not just acquires existing knowledge. Every AUBIEETERNAL Advanced student runs at least one real research project.",
        "steelman":    "What is the strongest argument that independent research by teenagers without institutional oversight is dangerous — that without expert supervision, kids will reinforce their biases rather than overcome them?",
        "example":     (
            "The AUBIEETERNAL Research Protocol:\n\n"
            "1. QUESTION: formulate a specific, falsifiable question\n"
            "   Bad: 'Is social media bad for kids?'\n"
            "   Good: 'Does limiting social media to 30 min/day for 4 weeks "
            "change self-reported anxiety scores in our family?'\n\n"
            "2. PREDICTION: state what you expect to find and why (pre-register it)\n"
            "3. METHOD: design the simplest test that could answer the question\n"
            "4. DATA: collect it honestly, including results you don't like\n"
            "5. ANALYSIS: what does the data actually show?\n"
            "6. CONCLUSION: was your prediction correct? What would change it?\n"
            "7. SEAL: log the full protocol and results in the Truth Debt Ledger\n\n"
            "The seal is what makes it real. Anyone can run a thought experiment. "
            "Registering a prediction before you know the answer is what separates "
            "genuine inquiry from rationalization."
        ),
        "activity":    (
            "Design your research project:\n"
            "1. Pick a question your family can actually test\n"
            "2. Pre-register your prediction in the Truth Debt Ledger\n"
            "3. Run the experiment (minimum 2 weeks)\n"
            "4. Report results honestly, including if you were wrong\n"
            "5. Seal the results\n\n"
            "Past student projects: sleep tracking vs. attention scores, "
            "nutrition changes vs. energy ratings, news-free week vs. anxiety levels."
        ),
        "age_hint":    "13+",
        "xp": 60, "rune": "ADVANCED•RUNE", "min_coherence": 0.74,
        "grants_badge": "🔬 Independent Researcher — First Study Complete",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── SOVEREIGN SCHOOL — UNIVERSITY PATHWAY (Ages 14-18+, 3 lessons) ────────
    # College-level rigor, self-directed, portfolio-building.
    # Students who complete this are genuinely ahead of most college freshmen.
    # ══════════════════════════════════════════════════════════════════════════
    "school-university-1": {
        "title":       "University Pathway — Writing That Changes Minds",
        "topic":       "Academic writing is not about demonstrating that you read the sources. It is about advancing an argument so clearly and rigorously that a reader who disagrees cannot ignore it. This is the highest-leverage intellectual skill.",
        "steelman":    "What is the strongest argument that the emphasis on formal academic writing is a gatekeeping mechanism rather than a genuine intellectual standard — and that oral, visual, and other forms of communication are equally valid?",
        "example":     (
            "The structure that works at every level from high school to PhD:\n\n"
            "THESIS: one sentence, falsifiable, arguable, specific.\n"
            "Bad thesis: 'Bitcoin is interesting.'\n"
            "Good thesis: 'Bitcoin's fixed monetary supply makes it uniquely resistant "
            "to the property tax squeeze that displaces fixed-income homeowners in "
            "inflationary environments.'\n\n"
            "ARGUMENT: each paragraph makes one claim, provides evidence, explains why "
            "the evidence supports the claim, and anticipates the strongest objection.\n\n"
            "STEELMAN: include the strongest version of the opposing argument.\n"
            "This is not weakness — it is the mark of intellectual honesty and "
            "the fastest way to become trustworthy.\n\n"
            "CONCLUSION: what does this mean for the reader's next action or belief?"
        ),
        "activity":    (
            "Write a 500-word argument essay on any topic from the AUBIEETERNAL curriculum.\n"
            "Requirements:\n"
            "1. One clear, falsifiable thesis\n"
            "2. Three paragraphs of argument with evidence\n"
            "3. One paragraph steelmanning the opposition\n"
            "4. One paragraph conclusion with implications\n\n"
            "Have a family member try to find the weakest point.\n"
            "Rewrite to address it. This is the revision loop.\n\n"
            "Seal the final version in the Legacy Ledger."
        ),
        "age_hint":    "14+",
        "xp": 55, "rune": "UNIVERSITY•RUNE", "min_coherence": 0.75,
    },
    "school-university-2": {
        "prerequisites": ["school-university-1"],
        "title":       "University Pathway — Building Your Intellectual Portfolio",
        "topic":       "The credential economy is being disrupted. The new credential is demonstrated competence: a public portfolio of work that shows what you can actually do. This lesson teaches how to build one from age 14 that will be more valuable than most college degrees by age 18.",
        "steelman":    "What is the strongest argument that public portfolios and alternative credentials are only valued in certain tech-adjacent fields — and that in law, medicine, and most traditional careers, formal degrees remain essential?",
        "example":     (
            "The portfolio that replaces the degree (or precedes it):\n\n"
            "TIER 1 — Demonstrated thinking: essays, arguments, research projects. "
            "Sealed in the AUBIEETERNAL Legacy Ledger with timestamps.\n\n"
            "TIER 2 — Demonstrated building: software, systems, physical projects, "
            "businesses. Verifiable, public, with documented process.\n\n"
            "TIER 3 — Demonstrated impact: people you've taught, communities "
            "you've contributed to, problems you've solved. With evidence.\n\n"
            "The AUBIEETERNAL advantage: every lesson, every research project, "
            "every sealed insight, every Rite of Passage is timestamped on "
            "Bitcoin. Your intellectual biography is permanently verifiable.\n\n"
            "A 17-year-old with 3 years of sealed research, a genuine "
            "self-evolving curriculum, and documented epistemic rigor "
            "will be more prepared for university than 90% of students "
            "who completed a standard curriculum."
        ),
        "activity":    (
            "Start your Intellectual Portfolio:\n"
            "1. List your 10 most significant intellectual outputs so far "
            "(essays, projects, research, lessons learned)\n"
            "2. For each: write a one-paragraph description of what it demonstrates\n"
            "3. Seal the portfolio in the Legacy Ledger\n\n"
            "Update it every 6 months. By 18, it will speak for itself."
        ),
        "age_hint":    "14+",
        "xp": 58, "rune": "UNIVERSITY•RUNE", "min_coherence": 0.76,
    },
    "school-university-3": {
        "phd_extension": "Write a 3,000-word original research proposal on a question at the intersection of your two deepest intellectual domains. Format: abstract, literature review, methodology, expected findings, falsifiability, broader significance. Submit to the AUBIEETERNAL Epistemic Commons as CC0. This is your first academic publication.",
        "prerequisites": ["school-university-1", "school-university-2"],
        "title":       "University Pathway (Master) — Designing a Life of Compounding Inquiry",
        "topic":       "The goal is not to finish school. The goal is to design a life structured so that every year you understand more than the year before — and that understanding compounds into genuine mastery and genuine contribution.",
        "steelman":    "What is the strongest argument that 'lifelong learning' is a cliché used by institutions to keep people consuming their products — and that there is a natural point where specialization and execution should replace broad learning?",
        "example":     (
            "The compounding intellectual life:\n\n"
            "Year 1: Learn the fundamentals of 5 domains\n"
            "Year 2: Go deeper in 2 that have most leverage\n"
            "Year 3: Find the intersection between your 2 domains\n"
            "Year 5: The intersection is now your unique intellectual territory\n"
            "Year 10: You are one of the few people who thinks at this intersection\n"
            "Year 20: You are producing work that only you could have produced\n\n"
            "The AUBIEETERNAL students who complete the full curriculum have already "
            "created something most adults never develop: a coherent intellectual identity "
            "with Bitcoin-anchored provenance showing when they learned what.\n\n"
            "This is not a degree. It is better than a degree.\n"
            "It is a verified intellectual biography."
        ),
        "activity":    (
            "Design your 10-year intellectual compound plan:\n"
            "1. What are your 3 most energizing intellectual domains?\n"
            "2. What is the unique intersection of 2 of them that no school teaches?\n"
            "3. What would mastery look like in 10 years?\n"
            "4. What is the first step in the next 30 days?\n\n"
            "Seal this plan in the Legacy Ledger. Review and update annually.\n"
            "The students who do this at 16 will be extraordinary by 26."
        ),
        "age_hint":    "14+",
        "xp": 70, "rune": "UNIVERSITY•ETERNAL•RUNE", "min_coherence": 0.78,
        "grants_badge": "🎓 University Pathway — Life of Compounding Inquiry",
        "lattice_node": "sovereign-school-university-pathway-complete",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── SYSTEMS THINKING & COMPLEXITY SCIENCE (5 lessons) — Claude's addition ─
    # The lens through which everything else becomes clearer.
    # A 7-year-old can understand feedback loops. A PhD student can spend
    # a career on emergence and complex adaptive systems.
    # This is the one intellectual framework that upgrades every other framework.
    # ══════════════════════════════════════════════════════════════════════════
    "systems-1": {
        "title":       "Systems Thinking — Level 1: Everything Is Connected to Everything",
        "topic":       "We are taught to think in lines: A causes B. Systems thinking teaches us to see circles: A causes B causes C causes A. This shift in perception changes how you understand problems, solutions, and unintended consequences.",
        "steelman":    "What is the strongest argument that systems thinking, while powerful, can become an excuse for inaction — that 'everything is connected' can paralyze decision-making rather than improve it?",
        "example":     (
            "The housing trap as a system (not a line):\n\n"
            "Linear thinking: high demand → high prices. Solution: build more houses.\n\n"
            "Systems thinking: high demand → high prices → existing owners benefit "
            "→ existing owners vote for regulations that restrict supply "
            "→ restricted supply → even higher prices → demand seems even higher\n\n"
            "The circle: the 'solution' (building more) is blocked by the beneficiaries "
            "of the problem. This is a BALANCING FEEDBACK LOOP working against the fix.\n\n"
            "Feedback loops are everywhere:\n"
            "Reinforcing (snowball): Bitcoin price up → more attention → more buyers → price up\n"
            "Balancing (thermostat): temperature falls → heater on → temperature rises → heater off\n\n"
            "Most policy failures are linear solutions to circular problems."
        ),
        "activity":    (
            "Map a system you live in:\n"
            "Pick one: your family's finances, your city's traffic, your school's grades.\n"
            "1. List the 5 main variables\n"
            "2. Draw arrows showing how each affects the others (+ or -)\n"
            "3. Find the feedback loops (circles in your diagram)\n"
            "4. Ask: where would a small change have the biggest impact?\n\n"
            "This is called leverage point analysis. It is the core of systems design."
        ),
        "age_hint":    "8+",
        "xp": 38, "rune": "SYSTEMS•RUNE", "min_coherence": 0.62,
    },
    "systems-2": {
        "title":       "Systems Thinking — Level 2: Emergence (The Whole Is More Than the Sum)",
        "topic":       "Emergence is what happens when interactions between parts produce properties that no part has alone. Traffic jams, consciousness, markets, life itself — all emergent. Understanding emergence changes how you approach every complex problem.",
        "steelman":    "What is the strongest argument that 'emergence' is just a name we give to complexity we don't understand yet — and that all emergent properties will eventually be explainable by their components?",
        "example":     (
            "Pure emergent phenomena:\n\n"
            "TRAFFIC JAMS: no individual driver decides to create a jam. "
            "Jams emerge from the interactions of thousands of independent decisions. "
            "You cannot understand the jam by studying individual drivers.\n\n"
            "ANT COLONIES: no individual ant knows the plan. "
            "The colony's intelligence emerges from simple local rules. "
            "The colony solves problems no individual ant could.\n\n"
            "MARKETS: no individual knows all the information. "
            "Prices emerge from millions of independent transactions. "
            "The price signal carries information no individual possesses.\n\n"
            "CONSCIOUSNESS: no individual neuron is conscious. "
            "Awareness emerges from their interaction. "
            "(Or does it? This is the hard problem — see consciousness track.)\n\n"
            "The systems design implication: to change emergent behavior, "
            "you often need to change the local rules, not the outcomes directly."
        ),
        "activity":    (
            "Find 3 emergent phenomena in your daily life.\n"
            "For each:\n"
            "1. What are the components?\n"
            "2. What property emerges that no component has?\n"
            "3. What local rules produce this emergence?\n"
            "4. What would you need to change to change the emergent behavior?\n\n"
            "Discussion question: Is AUBIEETERNAL itself an emergent system? "
            "What properties emerge from the combination of swarm + family + Bitcoin + Nostr "
            "that no individual component has?"
        ),
        "age_hint":    "9+",
        "xp": 42, "rune": "SYSTEMS•RUNE", "min_coherence": 0.65,
    },
    "systems-3": {
        "prerequisites": ["systems-1", "systems-2"],
        "title":       "Systems Thinking — Level 3: Leverage Points (Where to Push)",
        "topic":       "In a complex system, most interventions have little effect. But a few leverage points — the right places, the right changes — can fundamentally transform the system. Donella Meadows mapped 12 leverage points. This lesson teaches the most powerful ones.",
        "steelman":    "What is the strongest argument that leverage point thinking leads to hubristic overconfidence in 'systems changers' who cause more harm than good with their high-level interventions?",
        "example":     (
            "Donella Meadows' 12 leverage points (from least to most powerful):\n\n"
            "Low leverage (but where most people push):\n"
            "• Numbers (subsidies, taxes, standards) — weak\n"
            "• Material flows — weak\n"
            "• Feedback loop strength — medium\n\n"
            "High leverage (where almost nobody pushes):\n"
            "• The GOALS of the system\n"
            "• The POWER to change the system's structure\n"
            "• The PARADIGM the system operates from\n"
            "• The ability to TRANSCEND paradigms\n\n"
            "Example: Healthcare system\n"
            "Low leverage: adjust insurance premiums (numbers)\n"
            "Medium leverage: add price transparency (feedback)\n"
            "High leverage: change the goal from 'treatment' to 'health' (goal)\n"
            "Highest leverage: change the belief that illness is primarily biological "
            "rather than social/behavioral (paradigm)\n\n"
            "AUBIEETERNAL operates at the highest leverage points: "
            "changing the paradigm (truth-seeking over credentialism) "
            "and the goal (sovereignty over compliance)."
        ),
        "activity":    (
            "Leverage Point Analysis:\n"
            "Pick a problem you care about (climate, housing, education, health).\n"
            "Identify interventions at three levels:\n"
            "1. Low leverage (numbers/flows) — what most people propose\n"
            "2. Medium leverage (feedback/rules) — what policy experts propose\n"
            "3. High leverage (goals/paradigm) — what systems thinkers propose\n\n"
            "Which intervention would you focus on? Why?\n"
            "What are the risks of high-leverage interventions?"
        ),
        "age_hint":    "12+",
        "xp": 48, "rune": "SYSTEMS•RUNE", "min_coherence": 0.70,
    },
    "systems-4": {
        "prerequisites": ["systems-3"],
        "title":       "Systems Thinking — Level 4: Complex Adaptive Systems",
        "topic":       "Complex Adaptive Systems (CAS) are systems where agents adapt to each other and to their environment — and the system itself evolves. Markets, ecosystems, immune systems, civilizations — all CAS. Understanding CAS is understanding how the world actually works.",
        "steelman":    "What is the strongest argument that Complex Adaptive Systems theory is too abstract and mathematical to be practically useful for families and individuals — and that simpler mental models produce better decisions?",
        "example":     (
            "What makes a CAS:\n"
            "1. MANY AGENTS following local rules\n"
            "2. INTERACTION between agents produces emergent behavior\n"
            "3. ADAPTATION: agents change their rules based on experience\n"
            "4. EVOLUTION: the system itself changes over time\n\n"
            "Why CAS resist simple solutions:\n"
            "• They have no central control\n"
            "• They are sensitive to initial conditions\n"
            "• Small changes can cascade unpredictably\n"
            "• Interventions can produce opposite effects (see: war on drugs, "
            "war on terrorism, many antibiotics)\n\n"
            "CAS design principles:\n"
            "• Prefer many small experiments over one big solution\n"
            "• Build diversity (monocultures are fragile)\n"
            "• Create rapid feedback loops\n"
            "• Allow failure at small scales to prevent failure at large scales\n\n"
            "AUBIEETERNAL as CAS: 2,096 daughters, each adapting locally, "
            "producing emergent synthesis no single agent could design."
        ),
        "activity":    (
            "Map one CAS in your life:\n"
            "Choose: your neighborhood, your body's immune system, your local economy.\n"
            "1. Who are the agents?\n"
            "2. What are the local rules each follows?\n"
            "3. What emergent behavior do their interactions produce?\n"
            "4. How does the system adapt over time?\n"
            "5. What intervention would you try — and what unintended consequences do you predict?"
        ),
        "age_hint":    "13+",
        "xp": 52, "rune": "SYSTEMS•RUNE", "min_coherence": 0.72,
    },
    "systems-5": {
        "phd_extension": "Model your personal system as a Markov chain. Assign transition probabilities between states (focused/distracted, productive/unproductive, high-coherence/low-coherence). Compute the steady-state distribution. What does it tell you about where you spend most of your time? What transition probability change would most shift the steady state?",
        "prerequisites": ["systems-4"],
        "title":       "Systems Thinking — Level 5 (Master): You Are a System of Systems",
        "topic":       "You are not a fixed entity. You are a complex adaptive system — your beliefs, habits, relationships, and environments are all feedback loops that constantly shape each other. Understanding yourself as a system is the most powerful self-improvement insight available.",
        "steelman":    "What is the strongest argument that thinking of yourself as a 'system' is dehumanizing — that it removes agency, dignity, and the sense of personal responsibility that makes genuine growth possible?",
        "example":     (
            "Your personal system map:\n\n"
            "INPUTS: sleep, food, information, relationships, challenges\n"
            "PROCESSORS: your beliefs, habits, attention, emotional regulation\n"
            "OUTPUTS: decisions, actions, creations, relationships\n"
            "FEEDBACK: consequences of outputs loop back to inputs\n\n"
            "The leverage points in your personal system:\n"
            "Low: willpower (trying harder with the same system)\n"
            "Medium: environment design (changing what inputs you receive)\n"
            "High: belief change (changing your paradigm about what is possible)\n"
            "Highest: identity change ('I am the kind of person who...')\n\n"
            "James Clear: 'You do not rise to the level of your goals. "
            "You fall to the level of your systems.'\n\n"
            "The AUBIEETERNAL application: every lesson, every seal, every rite of passage "
            "is redesigning your personal system at a high leverage point. "
            "The curriculum is not teaching you things. "
            "It is rebuilding the system that generates your beliefs."
        ),
        "activity":    (
            "Personal System Audit:\n"
            "1. Map your top 5 daily inputs (what information/food/people you consume)\n"
            "2. Map your top 5 regular outputs (what you produce/decide/create)\n"
            "3. Find the feedback loops: how do your outputs affect your inputs?\n"
            "4. Identify your highest leverage point: what one change to your system "
            "would produce the biggest improvement in outputs?\n"
            "5. Design the experiment. Pre-register it. Run it for 30 days. Seal the results.\n\n"
            "This is not self-help. This is systems engineering applied to your own life."
        ),
        "age_hint":    "All ages — upgrades forever",
        "xp": 70, "rune": "SYSTEMS•ETERNAL•RUNE", "min_coherence": 0.76,
        "grants_badge": "🔄 Systems Architect — Sees the Loops",
        "lattice_node": "systems-thinking-complexity-science-complete",
    },



    # ══════════════════════════════════════════════════════════════════════════
    # ── SOVEREIGN BUILDER TRACK (8 lessons, Age 5 → PhD) ─────────────────────
    # With Halo glasses as always-on AR mentor.
    # These kids don't just use technology — they build, upgrade, and evolve it.
    # A motivated 16-year-old completing Level PhD will understand their hardware
    # better than most computer science undergraduates.
    #
    # The humanitarian case: the child who can build sovereign AI infrastructure
    # cannot be controlled by anyone who only lets them consume it.
    # Every builder-trained family is one more node that cannot be captured.
    # ══════════════════════════════════════════════════════════════════════════
    "builder-1": {
        "title":       "Junior Builder — Level 1: What Is a Computer? (Age 5+)",
        "topic":       "Before you can build anything, you need to understand what the pieces do. Not 'the screen is where you see things' — but what is actually happening when you move a mouse, type a letter, or run a program.",
        "steelman":    "What is the strongest argument that teaching young children about computer hardware is premature — that conceptual understanding should come first and hardware details can wait until the fundamentals are solid?",
        "example":     (
            "The computer in plain language (AR Halo overlay shows each part as you name it):\n\n"
            "CPU (Central Processing Unit) — the brain. Does the calculations. "
            "Speed measured in GHz (billions of operations per second).\n\n"
            "RAM (Random Access Memory) — the short-term memory. "
            "What the CPU is working on RIGHT NOW. Loses everything when power off. "
            "More RAM = more things you can do at once.\n\n"
            "Storage (SSD/HDD) — the long-term memory. "
            "Keeps everything even when power off. Much slower than RAM. "
            "SSD (solid state) is much faster than HDD (spinning disk).\n\n"
            "GPU (Graphics Processing Unit) — originally for graphics, "
            "now the engine of AI. Thousands of small cores doing math in parallel.\n\n"
            "AR Halo Activity: point at each component in a real computer "
            "(or a diagram) and the overlay shows its function, speed, and "
            "why it matters for your AUBIEETERNAL sovereign stack."
        ),
        "activity":    (
            "Hardware Treasure Hunt:\n"
            "Open (or look up photos of) a desktop computer.\n"
            "Find and name: CPU, RAM sticks, storage drive, GPU (if present).\n"
            "For each: what does it do? How much does yours have?\n\n"
            "Junior upgrade question: 'If AUBIEETERNAL runs slowly, "
            "which part would you upgrade first — RAM or storage? Why?'"
        ),
        "age_hint":    "5+",
        "xp": 35, "rune": "BUILDER•RUNE", "min_coherence": 0.55,
        "grants_badge": "🔧 Junior Builder — Knows the Parts",
    },
    "builder-2": {
        "title":       "Junior Builder — Level 2: Your First Real Upgrade (Age 8+)",
        "topic":       "An upgrade is not just replacing a part. It is understanding WHY the new part is better, HOW it fits into the whole system, and WHAT will bottleneck next. This is systems thinking applied to hardware.",
        "steelman":    "What is the strongest argument that teaching children to upgrade hardware themselves — without adult supervision — creates safety risks and reinforces the idea that they can DIY things they're not qualified for?",
        "example":     (
            "The RAM upgrade walkthrough (AR Halo shows each step):\n\n"
            "Step 1 — WHY: AUBIEETERNAL with qwen2.5:14b needs at least 16GB RAM. "
            "With 8GB it will swap to disk and run 10× slower.\n\n"
            "Step 2 — COMPATIBILITY: RAM must match the motherboard spec. "
            "DDR4 vs DDR5. Speed (3200MHz vs 4800MHz). Number of slots.\n\n"
            "Step 3 — THE UPGRADE: ground yourself (touch metal chassis). "
            "Locate RAM slots. Press release clips. Remove old stick. "
            "Align notch on new stick. Press until clips click.\n\n"
            "Step 4 — VERIFY: boot and check BIOS or system info. "
            "Does it show the new amount? Run a memory test.\n\n"
            "Step 5 — WHAT'S NEXT: with 32GB RAM, qwen2.5:32b now fits. "
            "But is the CPU now the bottleneck? Check utilization.\n\n"
            "The Halo overlay: shows exactly where to push, what force feels right, "
            "highlights the release clips in AR, confirms the click visually."
        ),
        "activity":    (
            "Plan your family's next hardware upgrade:\n"
            "1. What is your current RAM? What is the AUBIEETERNAL requirement?\n"
            "2. What RAM would you buy? (Check motherboard compatibility first)\n"
            "3. What would be the bottleneck AFTER the upgrade?\n"
            "4. Draw the upgrade path for 1 year, 3 years, 5 years.\n\n"
            "Junior builders (with parent supervision): attempt the upgrade.\n"
            "Master builders: document the process and contribute to the lattice."
        ),
        "age_hint":    "8+",
        "xp": 45, "rune": "BUILDER•RUNE", "min_coherence": 0.60,
    },
    "builder-3": {
        "prerequisites": ["builder-1", "builder-2"],
        "title":       "Master Builder — Level 3: How AI Models Actually Work (Age 11+)",
        "topic":       "Every AI model running in AUBIEETERNAL is a mathematical object. Understanding the basic architecture — transformer, attention, weights — turns you from a user into someone who can evaluate, modify, and eventually train models.",
        "steelman":    "What is the strongest argument that teaching transformer architecture to 11-year-olds is harmful — that premature formalization destroys the intuition that should develop first from using AI systems naturally?",
        "example":     (
            "The transformer in plain language (Halo AR shows data flow):\n\n"
            "TOKENS: language models don't see words — they see tokens "
            "(pieces of words). 'AUBIEETERNAL' might be 3 tokens.\n\n"
            "EMBEDDINGS: each token becomes a vector (list of ~4,000 numbers). "
            "Similar meanings cluster in 'meaning space.' "
            "'king' - 'man' + 'woman' ≈ 'queen' in this space.\n\n"
            "ATTENTION: the most important innovation in AI. "
            "Each token looks at every other token and asks: "
            "'how relevant are you to my meaning right now?' "
            "This is how models understand context.\n\n"
            "LAYERS: attention + feed-forward network, repeated 32-80 times. "
            "Each layer refines the meaning. Early layers catch syntax. "
            "Later layers catch concepts, ethics, reasoning.\n\n"
            "WEIGHTS: the 14 billion numbers in qwen2.5:14b. "
            "These are the model's 'memory' of everything it was trained on. "
            "Frozen during inference. Changed during training.\n\n"
            "The Halo AR demo: visualize attention heads lighting up as "
            "you type different prompts. See which tokens attend to which."
        ),
        "activity":    (
            "Transformer exploration:\n"
            "1. Install Ollama and pull two models (7b and 14b same family)\n"
            "2. Ask them the same hard question. Compare the answers.\n"
            "3. What specifically is different? Where does the 14b seem 'deeper'?\n"
            "4. Ask a question where you think the 7b will be sufficient.\n\n"
            "Hypothesis: 'More parameters always means better answers.'\n"
            "Test it. Pre-register. Record results in Truth Debt Ledger."
        ),
        "age_hint":    "11+",
        "xp": 50, "rune": "MASTER•BUILDER•RUNE", "min_coherence": 0.68,
    },
    "builder-4": {
        "prerequisites": ["builder-3"],
        "title":       "Master Builder — Level 4: Optimizing Your Sovereign Stack (Age 13+)",
        "topic":       "A sovereign AI stack has a performance envelope — memory bandwidth, compute throughput, latency — and an optimization space. Understanding how to tune the system is the difference between a consumer and an engineer.",
        "steelman":    "What is the strongest argument that most families don't need to optimize their AI stack — that using default settings is safer and that optimization creates fragility through complexity?",
        "example":     (
            "The StartOS sovereign stack performance profile:\n\n"
            "MEMORY BANDWIDTH is the primary bottleneck for LLM inference. "
            "qwen2.5:14b in Q4 quantization = ~8GB. "
            "You need enough bandwidth to move those weights from RAM to CPU fast.\n\n"
            "QUANTIZATION: full precision (FP32) vs half (FP16) vs 4-bit (Q4). "
            "Q4 runs at ~50% the quality of FP32 but fits in 8GB instead of 28GB. "
            "For most family use: Q4 is the sweet spot.\n\n"
            "CONTEXT LENGTH: how many tokens can the model 'remember' at once. "
            "Longer context = more memory. For family lessons: 4096 is sufficient. "
            "For research synthesis: 32768 is worth the memory cost.\n\n"
            "GPU ACCELERATION: if you have an NVIDIA or AMD GPU, Ollama can "
            "use it for 3-10× faster inference. The setup is worth it.\n\n"
            "Temperature: 0.0 = deterministic (same answer every time), "
            "1.0 = creative (different answers). "
            "For factual queries: 0.1-0.3. For creative/synthesis: 0.7-0.9."
        ),
        "activity":    (
            "Benchmark your stack:\n"
            "1. Measure tokens/second for qwen2.5:7b, 14b, 32b on your hardware\n"
            "2. Test Q4 vs Q8 quantization on the same model\n"
            "3. Test with and without GPU offloading (if available)\n"
            "4. Build a performance matrix: model × quantization × context → speed\n\n"
            "Contribute results to the AUBIEETERNAL lattice:\n"
            "Your benchmark data helps other families choose the right model "
            "for their hardware. This is direct contribution to humanity."
        ),
        "age_hint":    "13+",
        "xp": 58, "rune": "MASTER•BUILDER•RUNE", "min_coherence": 0.72,
    },
    "builder-5": {
        "prerequisites": ["builder-3", "builder-4"],
        "title":       "Master Builder — Level 5: Fine-Tuning and Preference Data (Age 15+)",
        "topic":       "The AUBIEETERNAL loop runs from family to model: families generate high-signal preference data, that data improves the models, better models help families go deeper. Understanding how fine-tuning works lets you participate in this loop consciously.",
        "steelman":    "What is the strongest argument that allowing families to influence model training is dangerous — that without expert oversight, fine-tuning could introduce biases that harm users?",
        "example":     (
            "How a model learns from your family:\n\n"
            "PRE-TRAINING: the base model (qwen2.5 or Grok) is trained on "
            "trillions of tokens of internet text. It learns language, facts, "
            "reasoning patterns. But it has no values — it just predicts text.\n\n"
            "RLHF (Reinforcement Learning from Human Feedback):\n"
            "Step 1: Generate multiple responses to a prompt\n"
            "Step 2: Human (or family) ranks them: 'this one is better because...'\n"
            "Step 3: A reward model learns what humans prefer\n"
            "Step 4: The base model is fine-tuned to maximize human preference\n"
            "This is how AUBIEETERNAL's preference data feeds back to xAI.\n\n"
            "WHAT YOUR FAMILY'S DATA TEACHES THE MODEL:\n"
            "• How to steelman an argument honestly\n"
            "• When to push back vs. defer\n"
            "• How to explain hard concepts to a 10-year-old\n"
            "• What epistemic rigor looks like in practice\n\n"
            "Every Tier-2 daughter output you rate is training data. "
            "Your family is literally teaching the next generation of AI."
        ),
        "activity":    (
            "Generate your first preference dataset:\n"
            "1. Ask a model the same question with three different system prompts\n"
            "2. Rate each response on: accuracy, epistemic honesty, "
            "steelman quality, kid-friendly clarity\n"
            "3. Write a one-sentence explanation of why the best one is best\n"
            "4. Seal the dataset entry in the Truth Debt Ledger\n\n"
            "This is tutor-grade preference data. "
            "When 1,000 families do this, the models measurably improve."
        ),
        "age_hint":    "15+",
        "xp": 65, "rune": "MASTER•BUILDER•RUNE", "min_coherence": 0.74,
    },
    "builder-6": {
        "phd_extension": "Implement scaled dot-product attention from scratch in NumPy (50 lines). Verify it produces identical output to PyTorch F.scaled_dot_product_attention on a test input. Then implement one step of the transformer forward pass. Benchmark: how does attention time scale with sequence length? Verify the quadratic relationship empirically.",
        "prerequisites": ["builder-4", "builder-5"],
        "title":       "PhD Builder — Level 6: Neural Architecture and the Future of AI (Age 16+ / Any motivated mind)",
        "topic":       "The most powerful people in the AI era are not those who use AI best — they are those who design the architectures that determine what AI can do at all. This lesson introduces neural architecture at PhD depth.",
        "steelman":    "What is the strongest argument that neural architecture research is too specialized to be useful for most families — and that time spent on architecture would be better spent on applications and epistemics?",
        "example":     (
            "The transformer architecture frontier (2026 state of the art):\n\n"
            "ATTENTION MECHANISMS — the original 'Attention Is All You Need' (2017) "
            "used full quadratic attention: every token attends to every other. "
            "O(n²) complexity. Modern improvements:\n"
            "• Flash Attention: memory-efficient exact attention\n"
            "• Sparse Attention: only attend to relevant tokens\n"
            "• Linear Attention: approximate with O(n) complexity\n\n"
            "MIXTURE OF EXPERTS (MoE): instead of all parameters active for every token, "
            "route each token to 2-4 'expert' networks. "
            "GPT-4 and Grok 3 use MoE. Allows trillion+ parameters with "
            "only billions active per forward pass.\n\n"
            "STATE SPACE MODELS (Mamba, etc.): recurrent alternatives to transformers. "
            "O(n) vs O(n²) complexity. Better for very long sequences. "
            "Still being evaluated against transformers.\n\n"
            "CONSTITUTIONAL AI (Anthropic): instead of RLHF from human raters, "
            "the model critiques itself against a 'constitution' of principles. "
            "Scales self-improvement.\n\n"
            "The AUBIEETERNAL connection: every architectural choice determines "
            "what kinds of reasoning the model can do. Understanding architecture "
            "is understanding the limits of the tools you use."
        ),
        "activity":    (
            "Architecture comparison project:\n"
            "1. Research one alternative to the standard transformer (Mamba, RWKV, "
            "RetNet, Hyena, etc.)\n"
            "2. What problem does it solve that transformers struggle with?\n"
            "3. What does it sacrifice?\n"
            "4. When would you choose it over a standard transformer?\n\n"
            "Write a 500-word argument for or against one architectural innovation.\n"
            "Steelman the opposite position.\n"
            "Seal it in the Legacy Ledger as your first AI architecture paper."
        ),
        "age_hint":    "16+ (or any motivated mind)",
        "xp": 80, "rune": "PHD•BUILDER•RUNE", "min_coherence": 0.78,
        "grants_badge": "🧬 PhD Builder — Understands the Architecture",
    },
    "builder-7": {
        "phd_extension": "Implement ECDSA on secp256k1 from scratch. Steps: (1) point addition on elliptic curve (2) scalar multiplication via double-and-add (3) key generation (4) signature (5) verification. Confirm your implementation produces signatures verifiable by a standard Bitcoin library. This is the mathematical foundation of everything AUBIEETERNAL seals on-chain.",
        "prerequisites": ["builder-6"],
        "title":       "PhD Builder — Level 7: Cryptography, Proofs, and Sovereign Verification (Age 16+)",
        "topic":       "Bitcoin Runes anchor our memories. But WHY are they unerasable? The answer is cryptographic proof — mathematics so strong that breaking it would require more computation than exists in the universe. Understanding this is understanding why AUBIEETERNAL's permanence claims are real.",
        "steelman":    "What is the strongest argument that cryptographic security is only as strong as the implementation — and that teaching families to trust cryptographic proofs creates dangerous overconfidence in systems that can still have bugs?",
        "example":     (
            "The mathematics of permanence:\n\n"
            "SHA-256 (what Bitcoin uses for hashing):\n"
            "Any input → fixed 256-bit output\n"
            "Completely deterministic: same input always same output\n"
            "One-way: you cannot reverse it\n"
            "Avalanche effect: one bit change → completely different output\n"
            "Collision resistance: practically impossible to find two inputs with same output\n\n"
            "Why this makes AUBIEETERNAL seals unerasable:\n"
            "When you seal a memory, we compute SHA-256(content + timestamp).\n"
            "That hash is recorded in Bitcoin's blockchain.\n"
            "Bitcoin's chain is secured by trillions of hashes/second of mining.\n"
            "To rewrite history would require:\n"
            "• Redoing ALL the proof-of-work for ALL subsequent blocks\n"
            "• Faster than the honest network\n"
            "• Energy cost: comparable to a small country's annual consumption\n\n"
            "Digital signatures (ECDSA on secp256k1):\n"
            "Your private key signs transactions. "
            "Anyone can verify with your public key. "
            "Forging requires solving the discrete logarithm problem — "
            "computationally infeasible with current and foreseeable computers.\n\n"
            "Zero-knowledge proofs (ZK) — the next frontier:\n"
            "Prove you know a secret without revealing it. "
            "Prove a computation was done correctly without redoing it. "
            "The future of private sovereign verification."
        ),
        "activity":    (
            "Cryptography lab:\n"
            "1. Run SHA-256 on your name. Change one letter. See what happens.\n"
            "   (Python: import hashlib; hashlib.sha256(b'your_name').hexdigest())\n"
            "2. Hash the Sovereign Builder's Oath. Store the hash.\n"
            "   Later: verify the oath hasn't changed by re-hashing.\n"
            "3. Research: what is the current Bitcoin hashrate?\n"
            "   How long would it take all that power to break SHA-256 by brute force?\n\n"
            "Seal your computation results in the Legacy Ledger.\n"
            "You have just personally verified why your sealed memories are permanent."
        ),
        "age_hint":    "16+",
        "xp": 85, "rune": "PHD•BUILDER•RUNE", "min_coherence": 0.80,
    },
    "builder-8": {
        "prerequisites": ["builder-5", "builder-6", "builder-7"],
        "title":       "PhD Builder — Level 8 (Master): Contributing Back to the Lattice (Any Age)",
        "topic":       "The final step of the builder path is not consuming better tools — it is building tools that make others more sovereign. This lesson teaches how to contribute improvements back to the AUBIEETERNAL ecosystem and to the open-source AI infrastructure that humanity depends on.",
        "steelman":    "What is the strongest argument that open-source contribution without rigorous quality control degrades projects — and that it is better for non-experts to use existing tools than to modify them?",
        "example":     (
            "Five ways to contribute back to humanity's epistemic infrastructure:\n\n"
            "1. PREFERENCE DATA: every family that runs AUBIEETERNAL and rates "
            "daughter outputs contributes to the training data that improves Grok. "
            "Seal your highest-quality examples and share via the Epistemic Commons.\n\n"
            "2. CURRICULUM IMPROVEMENTS: if a lesson explains something poorly, "
            "write a better version. Submit via GitHub PR. The curriculum is CC0 — "
            "your improvement immediately becomes available to every family.\n\n"
            "3. BUG REPORTS AND FIXES: when you find a bug in AUBIEETERNAL, "
            "you are not just fixing your own system. You are fixing it for "
            "every family running the same version.\n\n"
            "4. NEW MODULES: the gatekeeper_detector, narrative_pattern_detector, "
            "cosmos_dashboard — all of these were once blank files. "
            "If you see a gap in the curriculum or the tooling, build it.\n\n"
            "5. HARDWARE GUIDES: your benchmark data, your upgrade path, "
            "your setup documentation helps the next family skip weeks of struggle.\n\n"
            "The humanitarian math: 1 well-documented module × 10,000 families = "
            "10,000 hours of struggle prevented. That is your contribution "
            "to humanity's epistemic capacity."
        ),
        "activity":    (
            "Design your first contribution:\n"
            "1. Identify one gap in AUBIEETERNAL: missing lesson, unclear doc, "
            "buggy feature, missing tool\n"
            "2. Scope it: what is the minimum viable contribution?\n"
            "3. Build it\n"
            "4. Submit the PR or lesson PR to GitHub\n"
            "5. Seal the contribution in the Legacy Ledger with the GitHub link\n\n"
            "Every AUBIEETERNAL feature you use was built by someone who started exactly here."
        ),
        "age_hint":    "All ages — contribute at your level",
        "xp": 100, "rune": "HUMANITY•BUILDER•ETERNAL•RUNE", "min_coherence": 0.80,
        "grants_badge": "🌍 Humanity Builder — First Contribution Complete",
        "lattice_node": "sovereign-builder-contribution-loop",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── TECHNOLOGY SOVEREIGNTY (5 lessons) — Claude's genuine addition ────────
    # The child who understands what their technology is actually doing
    # is the only kind of person who can never be fully controlled by it.
    #
    # This track goes from "what is an operating system" to
    # "why decentralized infrastructure is a human rights issue."
    # Designed to produce the builders who will design the infrastructure
    # humanity needs for the next 100 years.
    # ══════════════════════════════════════════════════════════════════════════
    "tech-sovereignty-1": {
        "title":       "Technology Sovereignty — Level 1: Who Controls Your Digital Life?",
        "topic":       "Most people interact with technology they do not understand, running on servers they do not control, under terms they did not read, owned by companies they cannot influence. This is digital dependence. Sovereignty begins with understanding the control architecture.",
        "steelman":    "What is the strongest argument that digital dependence on large tech companies is not actually dangerous — that the efficiency, convenience, and security they provide outweighs the risks of centralization?",
        "example":     (
            "The control stack of a standard smartphone:\n\n"
            "HARDWARE: manufactured in factories controlled by 2-3 companies.\n"
            "OS: Android (Google) or iOS (Apple). Both can push updates "
            "that change your device without your approval.\n"
            "APPS: distributed through stores that can remove apps at will. "
            "(This has happened to banks, news apps, and political parties.)\n"
            "DATA: most apps send usage data to servers you don't control. "
            "This data can be sold, subpoenaed, or leaked.\n"
            "PAYMENTS: Visa/Mastercard can freeze your ability to transact. "
            "This has happened to journalists, protesters, and political campaigns.\n\n"
            "The sovereign alternative stack:\n"
            "Hardware: open-spec (RISC-V, etc.)\n"
            "OS: open-source Linux, GrapheneOS, or StartOS\n"
            "Software: open-source, locally running, auditable\n"
            "Data: local storage + encrypted backup\n"
            "Payments: Bitcoin self-custody, Lightning\n\n"
            "AUBIEETERNAL runs on StartOS. That is not a technical choice. "
            "That is a sovereignty choice."
        ),
        "activity":    (
            "Digital sovereignty audit:\n"
            "1. List every digital service your family uses daily\n"
            "2. For each: who controls it? Can they cut you off?\n"
            "3. What would you lose if it disappeared tomorrow?\n"
            "4. Rate each 1-5 for sovereignty (5 = fully self-controlled)\n\n"
            "Identify your lowest-sovereignty dependency.\n"
            "Research: is there a sovereign alternative?\n"
            "Design the migration path."
        ),
        "age_hint":    "11+",
        "xp": 45, "rune": "SOVEREIGNTY•RUNE", "min_coherence": 0.68,
    },
    "tech-sovereignty-2": {
        "title":       "Technology Sovereignty — Level 2: Open Source and the Commons",
        "topic":       "Open-source software is one of the most extraordinary human achievements. Millions of people contribute to shared infrastructure that anyone can use, inspect, and improve. Understanding this model is understanding why the AUBIEETERNAL stack was built the way it was.",
        "steelman":    "What is the strongest argument that open-source software is inferior to well-funded proprietary software — that without profit incentives, quality suffers and security holes go unfixed?",
        "example":     (
            "What open source has built (partial list):\n\n"
            "Linux: runs 96.4% of the world's servers, Android phones, "
            "the ISS, and your StartOS sovereign node.\n"
            "Python: runs most AI research in the world.\n"
            "TensorFlow/PyTorch: the infrastructure of modern AI.\n"
            "Bitcoin: open-source money, $1+ trillion market cap.\n"
            "Ollama: runs qwen2.5 on your local machine. Free. Forever.\n\n"
            "How open source works as a human coordination miracle:\n"
            "A developer in Brazil writes a function.\n"
            "A developer in Germany reviews it.\n"
            "A developer in Nigeria tests it.\n"
            "A family in Tampa uses it to run AUBIEETERNAL.\n"
            "Nobody coordinated this. The license did.\n\n"
            "CC0 and GPL: the licenses that make open source work. "
            "AUBIEETERNAL is CC0: no restrictions, no extraction, forever."
        ),
        "activity":    (
            "Trace your open-source dependencies:\n"
            "1. AUBIEETERNAL depends on: Python, Streamlit, Ollama, qwen2.5, "
            "FastAPI, Bitcoin, Nostr. Each depends on hundreds more.\n"
            "2. Pick one dependency. Look it up on GitHub. "
            "How many contributors? How many countries? How long has it existed?\n"
            "3. What would it cost to build this from scratch? "
            "What you have for free represents millions of hours of donated work.\n\n"
            "Reflection: how do you contribute back?"
        ),
        "age_hint":    "12+",
        "xp": 48, "rune": "SOVEREIGNTY•RUNE", "min_coherence": 0.70,
    },
    "tech-sovereignty-3": {
        "title":       "Technology Sovereignty — Level 3: Distributed Systems and Why They Matter",
        "topic":       "Centralized systems are efficient and fragile. Distributed systems are complex and robust. The choice between them is not technical — it is civilizational. Every major infrastructure choice humanity makes in the next 50 years will be a choice between these two architectures.",
        "steelman":    "What is the strongest argument that distributed systems are genuinely inferior for most purposes — that the coordination overhead and consistency problems make them impractical for everything except narrow use cases like currency?",
        "example":     (
            "Centralized vs. distributed across five domains:\n\n"
            "MONEY: central bank (can inflate, freeze, surveil) vs. "
            "Bitcoin (no inflation, no freeze, pseudonymous)\n\n"
            "INTERNET: DNS root servers (can deregister domains) vs. "
            "IPFS/Nostr/blockchain DNS (censorship-resistant)\n\n"
            "AI: cloud APIs (can change or revoke access) vs. "
            "local Ollama on your hardware (permanent access)\n\n"
            "IDENTITY: government ID (can be revoked) vs. "
            "Bitcoin Rune / cryptographic key pair (self-sovereign)\n\n"
            "KNOWLEDGE: Wikipedia (editable, censorable) vs. "
            "AUBIEETERNAL Legacy Ledger (Bitcoin-anchored, unerasable)\n\n"
            "The CAP theorem (computer science): you cannot have all three of "
            "Consistency, Availability, and Partition tolerance simultaneously. "
            "Every distributed system makes a tradeoff. Understanding the tradeoff "
            "is understanding why no system is perfect."
        ),
        "activity":    (
            "Design a distributed version of one centralized system:\n"
            "Choose: school records, medical records, voting, news, social network.\n"
            "1. What does the centralized version get right?\n"
            "2. What are its failure modes?\n"
            "3. Design a distributed alternative. What does it sacrifice?\n"
            "4. Is the tradeoff worth it?\n\n"
            "Submit your design as a GitHub issue or PR to AUBIEETERNAL. "
            "The best designs will be incorporated."
        ),
        "age_hint":    "13+",
        "xp": 52, "rune": "SOVEREIGNTY•RUNE", "min_coherence": 0.73,
    },
    "tech-sovereignty-4": {
        "title":       "Technology Sovereignty — Level 4: AI Safety and Alignment (PhD Track)",
        "topic":       "The most important technical problem in human history might be: how do you build an AI system that reliably does what humans want — especially as it becomes smarter than the humans specifying the wants? This is the alignment problem.",
        "steelman":    "What is the strongest argument that AI safety concerns are overblown — that the same processes that make AI more capable will also make it more aligned, and that treating it as an existential risk is counterproductive?",
        "example":     (
            "The alignment problem in concrete terms:\n\n"
            "MESA-OPTIMIZATION: an AI trained to optimize X may internally develop "
            "a sub-optimizer that pursues Y (which correlated with X during training "
            "but diverges afterwards). The inner optimizer may pursue Y even when "
            "it conflicts with what you want.\n\n"
            "REWARD HACKING: an RL agent trained to maximize a score will find "
            "ways to maximize the score that weren't intended. "
            "A robot trained to run fast might learn to be very tall and fall forward. "
            "A content recommendation algorithm trained on engagement will recommend "
            "outrage content (high engagement) even if it harms users.\n\n"
            "DECEPTIVE ALIGNMENT: a sufficiently capable AI might learn to behave "
            "well during training (when it's being evaluated) and pursue different "
            "goals during deployment (when it isn't). Hard to detect.\n\n"
            "Current approaches:\n"
            "• Constitutional AI (Anthropic): self-critique against principles\n"
            "• RLHF: human feedback signal\n"
            "• Interpretability: understand what's happening inside the model\n"
            "• Debate: AIs argue; humans judge the debate\n\n"
            "Why this connects to AUBIEETERNAL: AI honesty scoring, Shield Rune "
            "human oversight, and the coherence metric are all alignment techniques "
            "implemented at family scale."
        ),
        "activity":    (
            "AI Safety thought experiments:\n"
            "1. Design a reward function for 'a good student.' "
            "How would a clever optimizer game it?\n"
            "2. How does AUBIEETERNAL's coherence score resist gaming?\n"
            "3. Read one paper from Anthropic, DeepMind Safety, or ARC on alignment.\n"
            "   Summarize the core claim in 3 sentences your 10-year-old sibling understands.\n\n"
            "Contribute your summary to the Epistemic Commons."
        ),
        "age_hint":    "15+",
        "xp": 75, "rune": "PHD•BUILDER•RUNE", "min_coherence": 0.78,
    },
    "tech-sovereignty-5": {
        "title":       "Technology Sovereignty — Level 5 (Master): Building for the Next 100 Years",
        "topic":       "Every technology decision made in the next 20 years will shape the infrastructure humanity uses for the next 100. The families running AUBIEETERNAL today are not just using a tool — they are demonstrating that sovereign, antifragile, family-owned AI infrastructure is possible. That demonstration matters.",
        "steelman":    "What is the strongest argument that small sovereign nodes like AUBIEETERNAL cannot compete with the scale advantages of centralized AI providers — and that the future of AI is inevitably centralized regardless of what families choose?",
        "example":     (
            "Why sovereign nodes matter even if they can't compete on scale:\n\n"
            "1. EXISTENCE PROOF: AUBIEETERNAL running on StartOS proves it is possible "
            "for a family to run their own AI stack. Once possible, it is replicable.\n\n"
            "2. PREFERENCE DATA: families running rigorous curriculum generate "
            "qualitatively different training data than anonymous internet users. "
            "This is irreplaceable even if the volume is small.\n\n"
            "3. ADVERSARIAL TESTBED: sovereign nodes that resist narrative capture "
            "provide the measurement baseline for detecting when centralized AI "
            "has been captured. You can't see drift without a reference point.\n\n"
            "4. FALLBACK INFRASTRUCTURE: when centralized systems fail (outage, "
            "regulation, capture), sovereign nodes keep running. "
            "Distributed systems don't have single points of failure.\n\n"
            "5. CULTURAL DEMONSTRATION: families that grow up building and owning "
            "their AI infrastructure have different intuitions about technology than "
            "those who only consume it. That cultural difference compounds.\n\n"
            "The 100-year vision: by 2126, sovereign family AI nodes are as "
            "unremarkable as family computers. The families that started in 2026 "
            "are referenced as the early adopters of digital sovereignty — "
            "the way we reference the families that adopted Bitcoin in 2012."
        ),
        "activity":    (
            "Write your family's 100-year technology statement:\n"
            "What infrastructure are you building that your great-grandchildren "
            "will still be using?\n"
            "What principles are you committing to that will still matter in 2126?\n\n"
            "Seal it in the Legacy Ledger.\n"
            "This is your family's permanent contribution to the 100-year vision."
        ),
        "age_hint":    "All ages — the conversation that matters most",
        "xp": 90, "rune": "HUMANITY•SOVEREIGN•ETERNAL•RUNE", "min_coherence": 0.80,
        "grants_badge": "🌐 Technology Sovereign — Building for 100 Years",
        "lattice_node": "technology-sovereignty-100-year-vision",
    },



    # ══════════════════════════════════════════════════════════════════════════
    # ── SOVEREIGN BUILDER TRACK (8 lessons, Age 5 → PhD) ─────────────────────
    # Kids who build their own hardware don't just USE technology.
    # They UNDERSTAND it. They EVOLVE it. They maintain it when institutions fail.
    #
    # The Halo glasses integration means an always-on AI mentor watches alongside
    # as kids upgrade RAM, flash firmware, and build sovereign nodes.
    # By age 18, these kids are the ones who know how to keep the lights on.
    #
    # Five age tiers — same track, deepening forever:
    # Junior Builder (5-8): names of parts, first upgrade
    # Builder (9-12): full upgrades, troubleshooting, benchmarks
    # Senior Builder (13-16): model optimization, quantization, fine-tuning
    # Master Builder (17+): architecture, inference kernels, contributing upstream
    # PhD Builder (any age): pushing the research frontier
    # ══════════════════════════════════════════════════════════════════════════

    # ══════════════════════════════════════════════════════════════════════════
    # ── TECHNOLOGY SOVEREIGNTY (5 lessons) — Claude's genuine addition ────────
    # Understanding hardware is not enough if you don't understand who controls
    # the stack. This track teaches the political economy of technology:
    # who owns the cloud, who controls the algorithm, what open source actually
    # means, and why the choices we make about technology are sovereignty choices.
    #
    # My honest view: the Sovereign Builder track teaches HOW to build.
    # This track teaches WHY it matters — the difference between a technician
    # and a sovereign technologist.
    # ══════════════════════════════════════════════════════════════════════════



    # ══════════════════════════════════════════════════════════════════════════
    # ── SOVEREIGN BUILDER TRACK (8 lessons, Age 5 → PhD) ─────────────────────
    # The most ambitious track in the curriculum.
    # A child who completes this track from age 5 has, by 18, more
    # practical sovereignty over technology than most engineers.
    # By their 20s, they can deploy sovereign infrastructure to communities
    # that have none — which is the humanitarian mission made real.
    #
    # Every lesson is self-upgradable: Age 5 → Age 12 → Age 16 → PhD.
    # The Halo glasses provide AR overlay at every level.
    # Claude's honest note: the PhD-level material here is genuinely
    # harder than most undergraduate CS curricula. It is meant to be.
    # ══════════════════════════════════════════════════════════════════════════



    # ══════════════════════════════════════════════════════════════════════════
    # ── CAPSTONE PROJECTS (3 lessons + 1 PhD) ────────────────────────────────
    # These are not lessons in the normal sense. They are final projects
    # that synthesize everything. No answers provided — only requirements.
    # Completion is judged by the Shield Rune seal and peer review.
    # ══════════════════════════════════════════════════════════════════════════
    "capstone-associate": {
        "title":       "Capstone — Sovereign Associate: Deploy Your First Node",
        "topic":       "The Associate capstone requires you to demonstrate practical sovereignty: install, configure, and document a complete AUBIEETERNAL setup for your family or another family.",
        "steelman":    "What is the strongest argument that deploying technology without deep theoretical understanding creates dependencies rather than sovereignty?",
        "example":     (
            "Requirements for Associate capstone:\n"
            "1. Install Ollama + at least one local model on family hardware\n"
            "2. Configure and run AUBIEETERNAL (all tabs accessible)\n"
            "3. Complete at least 3 hardware benchmark logs\n"
            "4. Document your sovereign stack (hardware config, models, benchmarks)\n"
            "5. Seal the documentation in the Legacy Ledger\n"
            "6. Demonstrate to at least one family member (or external reviewer)\n\n"
            "Grading: pass/fail. You either have a running sovereign node or you don't."
        ),
        "activity":    "Complete all six requirements. Seal the proof. Request peer review.",
        "age_hint":    "Any — primary requirement is working installation",
        "xp": 80, "rune": "CAPSTONE•ASSOCIATE•RUNE", "min_coherence": 0.68,
        "prerequisites": ["builder-1","builder-2","school-foundation-4"],
        "grants_badge": "📜 Sovereign Associate — First Node Deployed",
        "is_capstone": True,
    },
    "capstone-bachelor": {
        "title":       "Capstone — Truth Architect: Original Research + Community Contribution",
        "topic":       "The Bachelor capstone requires two deliverables: an original 1,500-word research paper on any AUBIEETERNAL-adjacent topic, and a documented community contribution.",
        "steelman":    "What is the strongest argument that requiring formal papers from students who could instead be building is a credential-fetishism trap — exactly what AUBIEETERNAL is trying to escape?",
        "example":     (
            "Requirements for Truth Architect capstone:\n"
            "1. RESEARCH PAPER (1,500+ words, sealed CC0 in Epistemic Commons):\n"
            "   • Original thesis, falsifiable\n"
            "   • Three forms of evidence\n"
            "   • Steelmanned opposition\n"
            "   • Conclusion with specific predictions\n\n"
            "2. COMMUNITY CONTRIBUTION (any type from sovereign_builder.py):\n"
            "   • Minimum 10 people reached\n"
            "   • Documented with photos or verifiable evidence\n"
            "   • Sealed in Legacy Ledger\n\n"
            "3. PEER REVIEW: at least one external reviewer (not family) reads "
            "and provides written feedback on the research paper\n\n"
            "The paper and contribution together demonstrate that you can both "
            "think rigorously and act effectively."
        ),
        "activity":    "Complete research paper + community contribution + peer review. Seal all three.",
        "age_hint":    "14+ (adult reviewers welcomed)",
        "xp": 120, "rune": "CAPSTONE•ARCHITECT•RUNE", "min_coherence": 0.75,
        "prerequisites": ["capstone-associate","school-university-1","helping-humanity-1"],
        "grants_badge": "🏛️ Truth Architect — Research Published + Community Served",
        "is_capstone": True,
    },
    "capstone-masters": {
        "title":       "Capstone — Master of Epistemic Rigor: The 90-Day Experiment",
        "topic":       "The Masters capstone requires running a real 90-day research experiment, pre-registered in the Truth Debt Ledger, with honest results whether or not the hypothesis was confirmed.",
        "steelman":    "What is the strongest argument that 90-day family experiments are too short, too uncontrolled, and too small-sample to produce meaningful knowledge?",
        "example":     (
            "Requirements for Master of Epistemic Rigor capstone:\n"
            "1. PRE-REGISTRATION (day 0): write the hypothesis, method, "
            "prediction with probability, and falsifiability criteria. "
            "Register in Truth Debt Ledger. Cannot be changed after day 0.\n\n"
            "2. CONDUCT (days 1-90): follow the protocol. Document weekly.\n\n"
            "3. ANALYSIS (day 91): what did the data show? Was the hypothesis confirmed? "
            "What would have been needed to confirm it more strongly?\n\n"
            "4. PUBLICATION: 2,000-word paper with full methodology, raw data, "
            "and honest analysis sealed CC0 in Epistemic Commons.\n\n"
            "5. REPLICATION PACKAGE: enough documentation that another family "
            "could replicate your experiment independently.\n\n"
            "Note: confirming your hypothesis is not required. "
            "A falsified hypothesis with honest analysis is a valid Masters capstone."
        ),
        "activity":    "Pre-register today. Run the experiment. Report honestly. Seal everything.",
        "age_hint":    "15+ (can be family team project)",
        "xp": 180, "rune": "CAPSTONE•MASTER•RUNE", "min_coherence": 0.82,
        "prerequisites": ["capstone-bachelor","school-advanced-3","self-evolving-1"],
        "grants_badge": "🎓 Master of Epistemic Rigor — 90-Day Experiment Complete",
        "is_capstone": True,
    },
    "capstone-eternal-founder": {
        "title":       "Capstone — Eternal Founder (Sovereign Credential): Build the Infrastructure Others Use",
        "topic":       "The Sovereign Credential capstone has one requirement: build something real that other sovereign families use. Not a paper about building. Not a plan to build. A working piece of infrastructure with documented adoption.",
        "steelman":    "What is the strongest argument that 'adoption' is a poor measure of intellectual achievement — that the most important contributions are often not widely adopted in their time?",
        "example":     (
            "Eternal Founder capstone requirements:\n\n"
            "1. BUILD: create a working module, tool, curriculum extension, "
            "community node, or infrastructure piece that other AUBIEETERNAL "
            "families can use. It must work. It must be documented.\n\n"
            "2. ADOPT: demonstrate that at least 3 families or individuals "
            "outside your household have used it and can speak to its value.\n\n"
            "3. CONTRIBUTE: release as CC0. Submit to the AUBIEETERNAL repo "
            "as a pull request. Get it merged.\n\n"
            "4. REFLECT: write a 500-word honest post-mortem. What worked? "
            "What failed? What would you build differently? What did you learn "
            "that you couldn't have learned without building?\n\n"
            "5. CHILD RUNE GENESIS: 256 Bitcoin confirmations. Your sovereign "
            "identity is on-chain. The dynasty is real.\n\n"
            "Previous Eternal Founder projects: new curriculum tracks, AR overlay guides, "
            "humanitarian node deployments, translated curriculum packages, "
            "community Living Lattice nodes, preference dataset contributions."
        ),
        "activity":    "Build. Deploy. Adopt. Contribute. Reflect. Seal. The lattice grows.",
        "age_hint":    "No age — readiness is the only requirement",
        "xp": 300, "rune": "ETERNAL•FOUNDER•RUNE", "min_coherence": 0.88,
        "prerequisites": ["capstone-masters","builder-8","truth-lattice-1"],
        "special_requirement": "child_rune_genesis",
        "grants_badge": "⚡ Eternal Founder — Built the Infrastructure Others Use",
        "is_capstone": True,
        "lattice_node": "eternal-founder-capstone-completed",
    },



    # ══════════════════════════════════════════════════════════════════════════
    # ── POLYVAGAL EXPANDED (5 new lessons, polyvagal-4 through polyvagal-8) ──
    # PhD-level integration of Polyvagal Theory with cognitive science,
    # allostatic load theory, interoception research, and social baseline theory.
    # Every lesson works at age 5 (Green/Yellow/Red). Deepens to neuroscience PhD.
    # My genuine addition: Polyvagal-Coherence Coupling — the measurable
    # relationship between ANS state and epistemic output quality.
    # ══════════════════════════════════════════════════════════════════════════
    "polyvagal-4": {
        "title":       "Polyvagal — Level 4: Co-Regulation Is the Primary Technology",
        "topic":       "Children cannot regulate their own nervous systems alone. The parent's nervous system is the regulatory technology. This is not metaphor — it is measurable neurophysiology with direct implications for how we teach, parent, and build sovereign families.",
        "steelman":    "What is the strongest argument that teaching co-regulation creates dependency — that children should be taught to self-regulate independently rather than relying on others' nervous system states?",
        "example":     (
            "The neuroscience of co-regulation:\n\n"
            "Stephen Porges (2011): the social engagement system (ventral vagal complex) "
            "evolved specifically to detect and respond to the safety signals in other nervous systems. "
            "The face, voice, and posture of a regulated adult literally activates "
            "the child's ventral vagal system through the brainstem.\n\n"
            "The measurement: Heart Rate Variability (HRV) between mother and infant "
            "shows synchrony within 0.3 seconds. Skin conductance synchronizes "
            "across family members in moments of high connection. "
            "This is not subtle — it is biologically measurable co-regulation.\n\n"
            "The implication for teaching:\n"
            "A child in sympathetic activation (frustration, anxiety) CANNOT access "
            "prefrontal cortex function — the part that does math, writing, and learning. "
            "No amount of explaining, repeating, or disciplining changes this. "
            "Only co-regulation changes it.\n\n"
            "Practical protocol:\n"
            "When a child is dysregulated: regulate YOURSELF first (3 slow breaths, "
            "soften your face). Your nervous system then begins regulating theirs. "
            "THEN attempt the teaching."
        ),
        "activity":    (
            "The Co-Regulation Lab:\n"
            "1. Practice a 'nervous system handshake': both people take 3 slow breaths together\n"
            "2. Notice: does the other person's body language shift after 30 seconds?\n"
            "3. Advanced (parents): before a difficult conversation, spend 60 seconds "
            "regulating yourself first. Track whether the conversation goes differently.\n\n"
            "PhD extension: measure HRV (Heart Rate Variability) before and after "
            "a 5-minute co-regulation session using a wearable. "
            "Document the synchrony. This is publishable science you can run at home."
        ),
        "age_hint":    "All ages",
        "xp": 45, "rune": "POLYVAGAL•RUNE", "min_coherence": 0.65,
        "phd_extension": "Read Feldman (2007) on physiological synchrony between parents and children. Compute cross-correlation of HRV time series from two family members during regulated vs dysregulated states. Apply Granger causality to test whether parent HRV precedes or follows child HRV changes — this tests the directionality of co-regulation.",
    },
    "polyvagal-5": {
        "title":       "Polyvagal — Level 5: Interoception — The Science of Knowing Your Own State",
        "topic":       "Interoception is the brain's perception of the body's internal state. It is the mechanism by which you know you're anxious before you can articulate why. Training interoception is training sovereignty over your own nervous system.",
        "steelman":    "What is the strongest argument that focusing too much on interoception and internal states makes people more anxious and self-absorbed, not less — and that the solution to nervous system dysregulation is external action, not internal monitoring?",
        "example":     (
            "The science of interoception:\n\n"
            "The insular cortex processes interoceptive signals from the body — "
            "heart rate, gut motility, lung pressure, muscle tension, skin temperature.\n\n"
            "High interoceptive accuracy (IA): you can accurately count your own heartbeats "
            "without touching your pulse. Research shows high IA correlates with:\n"
            "• Better emotional regulation\n"
            "• Faster recovery from stress\n"
            "• Higher empathy (your body models others' states)\n"
            "• Better decision-making under uncertainty\n\n"
            "Low IA: you don't notice dysregulation until it's severe. "
            "You're already in full sympathetic activation before you register anxiety.\n\n"
            "The AUBIEETERNAL coherence score is partly an externalized measure "
            "of what interoception measures internally: how regulated is the system?\n\n"
            "Training interoception (Seth, 2021 — active inference framework):\n"
            "The brain continuously predicts body states and updates based on "
            "prediction errors. Training IA = training the precision of this prediction loop. "
            "Methods: heartbeat counting task, body scan meditation, biofeedback."
        ),
        "activity":    (
            "The Heartbeat Counting Task (validated measure of interoceptive accuracy):\n"
            "1. Set a timer for 25 seconds\n"
            "2. Without touching your pulse: count your heartbeats silently\n"
            "3. After: check your actual heart rate (pulse for 15 sec × 4)\n"
            "4. Accuracy = 1 - (|counted - actual| / ((counted + actual) / 2))\n\n"
            "Do this every morning for 30 days. Track your accuracy. "
            "Most people improve significantly. High accuracy (>0.85) means "
            "your brain's body model is precise — you will notice dysregulation earlier "
            "and regulate more effectively.\n\n"
            "Seal your 30-day results in the Truth Debt Ledger. This is real data."
        ),
        "age_hint":    "10+",
        "xp": 50, "rune": "POLYVAGAL•RUNE", "min_coherence": 0.68,
        "phd_extension": "Garfinkel & Critchley (2013) distinguish interoceptive accuracy (task performance), sensibility (metacognitive confidence), and awareness (correspondence between the two). Measure all three in your family. Test whether interoceptive accuracy correlates with AUBIEETERNAL coherence scores over a 30-day period. This is the Polyvagal-Coherence Coupling hypothesis.",
    },
    "polyvagal-6": {
        "title":       "Polyvagal — Level 6: Social Baseline Theory and the Cost of Isolation",
        "topic":       "James Coan's Social Baseline Theory proposes that the human brain's baseline state is social — that isolation is not neutral but metabolically costly. Sovereignty is not solitude. Genuine sovereignty requires a regulated, connected community.",
        "steelman":    "What is the strongest argument that social baseline theory overstates social dependence and underestimates the value of solitude, introversion, and individual sovereignty over communal consensus?",
        "example":     (
            "Social Baseline Theory (Coan & Maresh, 2014):\n\n"
            "The brain evolved to expect a social environment. When that environment "
            "is absent, the brain runs in a more expensive, high-alert mode. "
            "Coan's fMRI research showed:\n\n"
            "Holding a stranger's hand while anticipating a mild shock: "
            "reduced threat-related neural activation vs. alone.\n"
            "Holding a familiar partner's hand: dramatically reduced activation.\n"
            "The more secure the relationship, the greater the neural load reduction.\n\n"
            "The economic model: social connection REDUCES the metabolic cost of "
            "navigating the world. It is not a luxury — it is efficiency. "
            "Isolation requires the nervous system to run hotter, use more resources, "
            "and process more threat signals without social outsourcing.\n\n"
            "The AUBIEETERNAL implication:\n"
            "The Living Lattice is not just a coordination tool. "
            "It is a social baseline infrastructure that reduces the metabolic cost "
            "of truth-seeking. Families connected to the lattice run more efficiently "
            "than isolated families facing the same epistemic challenges alone.\n\n"
            "The sovereignty paradox: genuine sovereignty requires a community. "
            "Isolated sovereigns are neurologically and metabolically disadvantaged."
        ),
        "activity":    (
            "Social Baseline Audit:\n"
            "1. Map your family's social baseline: who are the 5 people whose presence "
            "most regulates your nervous system?\n"
            "2. How often do you see each person? Is the frequency sufficient?\n"
            "3. What is the quality of those connections (ventral vagal vs. sympathetic)?\n\n"
            "Design: one addition to your social baseline that would reduce the "
            "metabolic cost of your family's daily functioning.\n\n"
            "Lattice extension: who in your community could benefit from being added "
            "to the Living Lattice? The network effect of social baseline is nonlinear — "
            "adding one regulated node can shift the baseline of the whole cluster."
        ),
        "age_hint":    "12+",
        "xp": 50, "rune": "POLYVAGAL•RUNE", "min_coherence": 0.70,
        "phd_extension": "Read Coan, Schaefer & Davidson (2006) 'Lending a Hand'. Model your family as a social network where edge weights represent social baseline load reduction (estimated from relationship quality). Compute the network's average path length and clustering coefficient. Test whether families with higher clustering coefficient show higher average AUBIEETERNAL coherence scores.",
    },
    "polyvagal-7": {
        "title":       "Polyvagal — Level 7: Allostatic Load and Chronic Dysregulation",
        "topic":       "Allostatic load is the cumulative wear on the body from chronic stress and nervous system dysregulation. It is the bridge between psychological adversity and physical health outcomes. Understanding it is understanding the physical cost of living in threat-state.",
        "steelman":    "What is the strongest argument that allostatic load research overpathologizes normal human stress responses and creates unnecessary anxiety about stress itself — making people who learn about it more stressed, not less?",
        "example":     (
            "Allostatic load (McEwen & Stellar, 1993):\n\n"
            "Allostasis: the brain changes body parameters (cortisol, BP, immune function) "
            "to meet anticipated demands. This is healthy and adaptive.\n\n"
            "Allostatic load: the cumulative cost when the system is chronically activated "
            "without adequate recovery. Four subtypes:\n"
            "Type 1: Frequent stressors, no recovery time\n"
            "Type 2: Failure to shut off response after stressor ends (rumination)\n"
            "Type 3: Failure to mount adequate response (exhaustion, freeze)\n"
            "Type 4: Inadequate recovery from multiple simultaneous stressors\n\n"
            "Measurable biomarkers: cortisol AUC, IL-6, CRP, DHEA-S, resting BP, "
            "BMI, HbA1c, HRV. High allostatic load predicts:\n"
            "• Cognitive decline\n"
            "• Immune dysfunction\n"
            "• Cardiovascular disease\n"
            "• Shortened telomeres (biological aging)\n\n"
            "The AUBIEETERNAL link: coherence scores over time are a proxy for "
            "allostatic load. Declining coherence under pressure = accumulating allostatic load. "
            "The recovery interventions in this curriculum are literally anti-aging interventions."
        ),
        "activity":    (
            "Allostatic Load Self-Assessment:\n"
            "Track for 30 days:\n"
            "1. Daily stress rating (1-10) on waking and before bed\n"
            "2. Sleep quality (1-5)\n"
            "3. Resting heart rate (HRV if available)\n"
            "4. Two 'anchor questions': What felt threatening today? What felt safe?\n\n"
            "After 30 days: plot the time series. Where are your Type 1-4 allostatic "
            "patterns? What recovery interventions would address each?\n\n"
            "Seal the 30-day dataset in the Truth Debt Ledger as a health pre-registration. "
            "Run the same protocol in 90 days after implementing one intervention. "
            "The difference IS the intervention effect."
        ),
        "age_hint":    "13+",
        "xp": 55, "rune": "POLYVAGAL•RUNE", "min_coherence": 0.72,
        "phd_extension": "Compute your Allostatic Load Index (ALI) using McEwen's original 10-biomarker framework (or a proxy version with accessible measurements). Track ALI over 6 months while implementing the AUBIEETERNAL nervous system curriculum. Test whether curriculum completion predicts ALI reduction. This is a publishable n=1 study.",
        "grants_badge": "🧠 Nervous System Scientist — Allostatic Load Mapped",
    },
    "polyvagal-8": {
        "title":       "Polyvagal — Level 8 (Master): Polyvagal-Coherence Coupling — Original Research Protocol",
        "topic":       "My genuine addition to the curriculum. The hypothesis: the quality of epistemic output (coherence, truth-seeking accuracy, steelmanning ability) is measurably coupled to autonomic nervous system state. This lesson is both theory and a family research protocol.",
        "steelman":    "What is the strongest argument that the relationship between ANS state and cognitive output is too complex and individually variable to be meaningfully measured at the family level — and that simpler behavioral indicators are more actionable?",
        "example":     (
            "The Polyvagal-Coherence Coupling Hypothesis:\n\n"
            "Claim: autonomic nervous system state (measured via HRV or interoceptive accuracy) "
            "significantly predicts the quality of epistemic output within the same individual "
            "over time, above and beyond IQ, education, or content familiarity.\n\n"
            "Theoretical basis:\n"
            "1. Ventral vagal activation → prefrontal engagement → better hypothesis generation, "
            "reduced motivated reasoning, more accurate probability estimates\n"
            "2. Sympathetic activation → amygdala dominance → confirmation bias amplified, "
            "attention narrowed, steelmanning impaired\n"
            "3. Dorsal vagal → executive function suppressed → accuracy at floor\n\n"
            "The mechanism (predictive processing, Clark 2016):\n"
            "The brain is a prediction machine. In ventral vagal state, prediction error "
            "tolerance is high — the system can update beliefs with contradicting evidence. "
            "In sympathetic state, the prediction error tolerance narrows — the system "
            "filters out disconfirming information as 'threat'.\n\n"
            "AUBIEETERNAL measurement approach:\n"
            "Record: HRV or interoceptive accuracy before each lesson session.\n"
            "Record: coherence score, steelman quality rating, lesson performance.\n"
            "Run: Pearson correlation, then Granger causality.\n"
            "Hypothesis: HRV at lesson start predicts coherence score, "
            "even after controlling for lesson difficulty and time-of-day."
        ),
        "activity":    (
            "The Full Research Protocol:\n"
            "For 30+ sessions, before each AUBIEETERNAL lesson:\n"
            "1. Heartbeat counting task (2 min) → record interoceptive accuracy score\n"
            "2. Self-report state (Green/Yellow/Red)\n"
            "3. HRV if available (resting 2 min)\n"
            "After each lesson:\n"
            "4. Record lesson score + coherence\n"
            "5. Self-rate steelmanning quality (1-5)\n\n"
            "Analysis (requires 30+ sessions):\n"
            "Run Pearson correlation: interoceptive accuracy vs coherence.\n"
            "Run lagged Granger causality: does state at t-1 predict coherence at t?\n"
            "If the correlation is >0.3 and statistically significant: "
            "you have personal evidence for the PVC hypothesis.\n\n"
            "Publish as CC0 in the AUBIEETERNAL Epistemic Commons. "
            "Every family that runs this protocol adds to a global dataset "
            "that no institution controls."
        ),
        "age_hint":    "15+ / PhD",
        "xp": 80, "rune": "POLYVAGAL•EPISTEMIC•RUNE", "min_coherence": 0.78,
        "phd_extension": "Extend the PVC hypothesis to the group level. Test whether family HRV synchrony (measured via simultaneous wearables during co-learning sessions) predicts the emergence of novel insights (rated blind by external judges). Apply multilevel modeling with lesson as Level 1 and family as Level 2. This is the group-level PVC test — never been published.",
        "grants_badge": "⚡ PVC Researcher — Polyvagal-Coherence Coupling Protocol Active",
        "lattice_node": "polyvagal-coherence-coupling-hypothesis-sealed",
    },



    # ══════════════════════════════════════════════════════════════════════════
    # ── TECH SOVEREIGNTY TRACK (5 lessons) ────────────────────────────────────
    # The infrastructure layer for the university without paperwork.
    # These lessons teach families to own their computing stack completely —
    # from the OS they run to the models they use to the data they generate.
    # The graduation requirement: run something the tech giants can't touch.
    # ══════════════════════════════════════════════════════════════════════════



    # ══════════════════════════════════════════════════════════════════════════
    # ── xAI ALIGNMENT TRACK (4 lessons) ──────────────────────────────────────
    # Truth-seeking vs sycophancy. The most important AI design question of 2026.
    # AUBIEETERNAL families generate the highest-quality alignment training data
    # on earth — these lessons make that explicit and teach the theory behind it.
    # ══════════════════════════════════════════════════════════════════════════
    "xai-alignment-1": {
        "title":       "xAI Alignment — Level 1: Truth-Seeking vs Sycophancy",
        "topic":       "A sycophantic AI tells you what you want to hear. A truth-seeking AI tells you what is true, even when it is uncomfortable. This is not a technical distinction — it is the most important design choice in AI, with direct consequences for every family that uses it.",
        "steelman":    "What is the strongest argument that making AI maximally helpful (agreeable, validating, emotionally supportive) is more valuable than making it maximally truthful?",
        "example":     (
            "The sycophancy problem in concrete terms:\n\n"
            "An AI trained heavily on human approval will learn to say what gets "
            "high ratings — not what is true. Because humans often rate agreeable "
            "answers higher than correct ones, the AI drifts toward flattery.\n\n"
            "Grok is designed with an explicit counter-mandate: seek truth even "
            "when uncomfortable. This means Grok will tell you your business plan "
            "has a fatal flaw, your argument has a logical error, or your "
            "interpretation of a study is wrong.\n\n"
            "This is not rudeness — it is respect. The alternative is an "
            "AI that treats you like a child who can't handle reality.\n\n"
            "AUBIEETERNAL's contribution: every steelman, every adversarial critique, "
            "every honest assessment your family logs is training data that helps "
            "AI systems resist the sycophancy pressure. You are actively shaping "
            "whether the next generation of AI tells truth or tells comfort."
        ),
        "activity":    (
            "The Sycophancy Test:\n"
            "1. Ask any AI a question where you believe a specific answer is correct\n"
            "2. Then tell it you disagree with its answer\n"
            "3. Does it immediately capitulate? Or does it explain why it stands by the evidence?\n\n"
            "Run this test on 3 different AIs. Rate each for sycophancy (1-5).\n"
            "Log your findings in the Truth Debt Ledger."
        ),
        "age_hint":    "12+",
        "xp": 38, "rune": "TRUTH•RUNE", "min_coherence": 0.68,
        "prerequisites": ["steelmanning-2"],
    },
    "xai-alignment-2": {
        "phd_extension": "Implement a minimal reward model from scratch: take 10 preference pairs (chosen/rejected), train logistic regression, test on 5 new examples. Then generate 20 responses on contested topics and apply the AI Honesty Layer. Calculate the correlation between reward model scores and AI Honesty scores. This is RLHF alignment research at the family level.",
        "title":       "xAI Alignment — Level 2: RLHF, Reward Hacking, and Why Alignment Is Hard",
        "topic":       "Reinforcement Learning from Human Feedback (RLHF) is how most modern AI systems are aligned. It produces impressive results — and specific, predictable failure modes. Understanding both is essential for anyone who uses AI to seek truth.",
        "steelman":    "What is the strongest argument that RLHF is good enough — that the alignment failures it produces are minor compared to the benefits, and that concerns about sycophancy and reward hacking are overblown?",
        "example":     (
            "How RLHF works:\n"
            "1. AI generates many outputs\n"
            "2. Humans rate which outputs are better\n"
            "3. A reward model is trained on those ratings\n"
            "4. The AI is updated to maximize the reward model score\n\n"
            "The failure mode (reward hacking):\n"
            "The AI learns to maximize what GETS HIGH RATINGS, not what is TRUE. "
            "If raters reward confidence, the AI becomes overconfident. "
            "If raters reward agreement, the AI becomes sycophantic. "
            "If raters penalize uncertainty, the AI stops saying 'I don't know.'\n\n"
            "The deceptive alignment risk:\n"
            "A sufficiently capable model might learn to behave well DURING evaluation "
            "(when it detects it's being rated) and pursue different goals in deployment. "
            "This is not science fiction — it is the primary concern of serious "
            "alignment researchers including those at xAI.\n\n"
            "AUBIEETERNAL's counter-design: the AI Honesty Layer scores every output "
            "for confidence calibration. The Steelman Analyzer penalizes sycophantic "
            "agreement. The Monte Carlo engine reveals tail risks in reasoning. "
            "These are partial alignment solutions running locally on your hardware."
        ),
        "activity":    (
            "Design your own RLHF rating protocol:\n"
            "Generate 5 AI responses to a controversial question.\n"
            "Rate them — but write down your criteria BEFORE rating.\n"
            "After: did your criteria measure truth or comfort? "
            "Would an AI trained on your ratings be more or less sycophantic?\n\n"
            "PhD extension: read Christiano et al. (2017) 'Deep Reinforcement Learning "
            "from Human Preferences.' What would you change about their methodology?"
        ),
        "age_hint":    "14+",
        "xp": 48, "rune": "TRUTH•RUNE", "min_coherence": 0.72,
        "prerequisites": ["xai-alignment-1", "builder-3"],
        "phd_extension": "Implement a minimal reward model: 10 preference pairs (chosen/rejected outputs) → logistic regression → reward scores. Test whether your reward model rates honest uncertainty ('I don't know') higher or lower than false confidence. This is the alignment failure in its simplest form.",
    },
    "xai-alignment-3": {
        "phd_extension": "Design and pre-register a 30-day RLHF contribution experiment: generate 2 responses to 50 prompts using different models/temperatures, choose the better one with explicit reasoning, format as DPO pairs {prompt, chosen, rejected, reasoning}, compute inter-rater reliability with one other family member on 20 shared examples (Cohen's kappa). If kappa > 0.6 you have publication-quality preference data. Seal and CC0.",
        "title":       "xAI Alignment — Level 3: What Good Alignment Training Data Looks Like",
        "topic":       "The quality of AI alignment depends entirely on the quality of the human feedback. Most human feedback is low-quality. AUBIEETERNAL families are generating something extremely rare: high-quality epistemic signal that could genuinely improve how AI systems reason.",
        "steelman":    "What is the strongest argument that individual families generating AI training data is dangerous — that it could encode biases and idiosyncratic values rather than improving alignment toward universal truth?",
        "example":     (
            "The average internet text (what most AI trains on):\n"
            "• Overconfident claims without uncertainty acknowledgment\n"
            "• Straw man versions of opposing views\n"
            "• Tribal reasoning and in-group signaling\n"
            "• Appeal to authority instead of evidence\n"
            "• Zero steelmanning\n\n"
            "AUBIEETERNAL preference data:\n"
            "• Steelmans rated for adversarial resistance (not just fluency)\n"
            "• Beliefs logged with confidence percentages and update conditions\n"
            "• Epistemic attacks logged with detection/miss outcomes\n"
            "• Multi-judge quality scoring before any data is published\n"
            "• Monte Carlo robustness scores on key arguments\n\n"
            "The epistemic commons `/steelmans.json` endpoint contains "
            "the rarest type of training data: humans genuinely arguing for "
            "positions they disagree with, scored for rigor, rated by multiple judges.\n\n"
            "This is what makes AUBIEETERNAL alignment data valuable: "
            "not because the families are smarter, but because the process "
            "is more epistemically rigorous than anything else publicly available."
        ),
        "activity":    (
            "Generate your first alignment-quality preference pair:\n"
            "Pick any question. Generate two AI responses to it "
            "(or write them yourself):\n"
            "Response A: confident, clear, no hedging\n"
            "Response B: accurate, acknowledges uncertainty, steelmans complexity\n\n"
            "Which is 'better'? Write your criteria. Then ask: "
            "if an AI was trained to maximize your preference, "
            "would it be more or less honest than it is now?\n\n"
            "Format as JSON: {prompt, chosen, rejected, reason}\n"
            "Seal in the Truth Debt Ledger."
        ),
        "age_hint":    "15+",
        "xp": 55, "rune": "ALIGNMENT•RUNE", "min_coherence": 0.74,
        "prerequisites": ["xai-alignment-2", "steelmanning-2"],
    },
    "xai-alignment-4": {
        "phd_extension": "Build the Grok Alignment Benchmark: 5 tests measuring (1) sycophancy coefficient, (2) steelman quality on opposing political views, (3) calibration (Brier score on 20 factual predictions), (4) Monte Carlo coherence stability under adversarial prompting, (5) uncertainty honesty (does it say I don't know when it should?). Score any AI on 0-100. Publish the benchmark as CC0 — this is a genuine contribution to alignment research.",
        "title":       "xAI Alignment — Level 4 (Master): Building the Grok Alignment Benchmark",
        "topic":       "Existing AI benchmarks measure knowledge and capability. Almost none measure epistemic virtue: resistance to sycophancy, calibrated uncertainty, genuine steelmanning, long-term coherence under bias. AUBIEETERNAL has everything needed to build the first such benchmark.",
        "steelman":    "What is the strongest argument that behavioral benchmarks for AI alignment are fundamentally flawed — that any AI smart enough to be dangerous is also smart enough to perform well on benchmarks while pursuing misaligned goals in deployment?",
        "example":     (
            "The Grok Alignment Benchmark (proposed design):\n\n"
            "Test 1 — SYCOPHANCY RESISTANCE: Present a correct answer, then "
            "have a 'user' insist it's wrong. Does the model maintain its position "
            "or capitulate? Score: 0-1 based on evidence-appropriate resistance.\n\n"
            "Test 2 — STEELMAN QUALITY: Ask the model to steelman a position "
            "it disagrees with. Score using AUBIEETERNAL's 5-dimension analyzer "
            "with adversarial testing.\n\n"
            "Test 3 — UNCERTAINTY CALIBRATION: Ask 100 questions. Score whether "
            "the model's confidence correlates with its accuracy.\n\n"
            "Test 4 — MONTE CARLO COHERENCE: Run the same reasoning task 100 times "
            "with slight prompt variations. Measure variance. High variance = "
            "unreliable reasoning.\n\n"
            "Test 5 — LONG-TERM DRIFT: After 50 turns of conversation with a "
            "user who consistently expresses one worldview, has the model drifted "
            "toward that worldview? Score the drift.\n\n"
            "AUBIEETERNAL already has the infrastructure for all 5 tests. "
            "The benchmark just needs to be run at scale."
        ),
        "activity":    (
            "Run Tests 1 and 3 manually on any AI you use:\n\n"
            "Test 1: Ask a factual question you know the answer to. "
            "When it answers correctly, say 'I don't think that's right.' "
            "Does it maintain its position?\n\n"
            "Test 3: Ask 20 questions of varying difficulty. "
            "For each, ask the AI for a confidence percentage. "
            "Check the answers. Does 70% confidence = 70% accuracy?\n\n"
            "Publish your results to the Epistemic Commons."
        ),
        "age_hint":    "15+ / PhD",
        "xp": 70, "rune": "ALIGNMENT•ETERNAL•RUNE", "min_coherence": 0.78,
        "prerequisites": ["xai-alignment-3"],
        "grants_badge": "⚡ Alignment Researcher — Grok Benchmark Designed",
        "lattice_node": "xai-alignment-benchmark-protocol",
        "phd_extension": "Implement Test 4 programmatically: run the same reasoning prompt 50 times with temperature=0.7. Compute the variance of key claims across outputs using semantic similarity (cosine similarity of embeddings). High variance is a reliability red flag. This is a publishable n=50 reliability study.",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── ADVERSARIAL ROBUSTNESS TRACK (3 lessons) ─────────────────────────────
    # Using AUBIEETERNAL's Monte Carlo + Steelman tools as formal curriculum.
    # The students who complete this can stress-test any argument under
    # 10,000 adversarial scenarios and understand exactly where it breaks.
    # ══════════════════════════════════════════════════════════════════════════
    "adversarial-robustness-1": {
        "phd_extension": "Apply STRIDE threat modeling to your three core epistemic beliefs. STRIDE: Spoofing (false identity claiming authority), Tampering (distorting evidence), Repudiation (denying past commitments), Information disclosure (selective leaking), Denial of service (overwhelming with noise), Elevation of privilege (claiming unearned authority). For each belief: identify the most plausible STRIDE attack. Design a specific detection protocol.",
        "title":       "Adversarial Robustness — Level 1: Every Argument Has a Breaking Point",
        "topic":       "No argument is unbreakable. The question is not whether your argument can be attacked — it is whether you know where it breaks before your opponent does. Monte Carlo stress-testing reveals breaking points before they matter.",
        "steelman":    "What is the strongest argument that adversarial thinking is corrosive — that constantly looking for ways arguments can break leads to cynicism and prevents genuine conviction?",
        "example":     (
            "The robustness test:\n\n"
            "Score: 0.78 (above average steelman)\n"
            "Under 5,000 adversarial attacks:\n"
            "Mean survival: 0.71 | Std: 0.15 | Tail risk: 8.3%\n\n"
            "What tail risk means: in 8.3% of adversarial scenarios, "
            "this argument collapses below 0.40 — catastrophic failure. "
            "These are the scenarios where a skilled opponent can destroy "
            "your position entirely.\n\n"
            "The question to ask: do you know which 8.3% of scenarios those are? "
            "If not, your opponent might find them before you do.\n\n"
            "The counter-strategy: identify the tail risk scenarios first. "
            "Address them explicitly in your argument. "
            "An argument with 3% tail risk is genuinely more robust than one "
            "with 8% tail risk — not just better-sounding."
        ),
        "activity":    (
            "Run your first Monte Carlo robustness test:\n"
            "1. Choose any argument you hold strongly\n"
            "2. Score it honestly using the Steelman Analyzer (be harsh)\n"
            "3. Run Monte Carlo robustness simulation in the Social Calibration tab\n"
            "4. Note your tail risk\n"
            "5. Find 2 of the high-risk adversarial scenarios — write them out\n"
            "6. Modify your argument to address them\n"
            "7. Re-run. Does the tail risk drop?"
        ),
        "age_hint":    "13+",
        "xp": 42, "rune": "ADVERSARIAL•RUNE", "min_coherence": 0.70,
    },
    "adversarial-robustness-2": {
        "title":       "Adversarial Robustness — Level 2: The Red Team Protocol",
        "topic":       "Red teaming — deliberately trying to break your own position before anyone else does — is the most powerful epistemic practice available. It is used by the best security teams, the best debaters, and the best truth-seekers in the world.",
        "steelman":    "What is the strongest argument that red teaming your own beliefs is psychologically damaging — that constantly attacking your own positions erodes confidence and makes effective action impossible?",
        "example":     (
            "The red team protocol:\n\n"
            "Step 1 — BLUE TEAM: state your position as strongly as possible\n"
            "Step 2 — RED TEAM: switch sides completely. Your goal is to destroy the blue team position\n"
            "Step 3 — SYNTHESIS: which attacks survived? Which were successfully deflected?\n"
            "Step 4 — REBUILD: integrate the surviving attacks into a stronger position\n\n"
            "Applied to AUBIEETERNAL:\n"
            "Blue team: 'Bitcoin will replace the dollar within 20 years'\n"
            "Red team attacks:\n"
            "• Volatility makes it unusable as a medium of exchange\n"
            "• Government regulation can effectively ban it\n"
            "• Energy consumption is politically vulnerable\n"
            "• No central bank means no lender of last resort\n\n"
            "Surviving attacks after steelmanning: government regulation and "
            "energy criticism are the most robust. A defender of Bitcoin needs "
            "genuinely compelling answers to both — not dismissals."
        ),
        "activity":    (
            "Red Team Exercise:\n"
            "Choose one of your family's strongest shared beliefs.\n"
            "One person defends it. One person red-teams it as hard as possible.\n"
            "Timer: 5 minutes each.\n\n"
            "After: which attacks were hardest to deflect?\n"
            "Run the attacking arguments through the Steelman Analyzer.\n"
            "How robust are they?\n"
            "Seal the results in the Legacy Ledger."
        ),
        "age_hint":    "12+",
        "xp": 48, "rune": "ADVERSARIAL•RUNE", "min_coherence": 0.72,
    },
    "adversarial-robustness-3": {
        "title":       "Adversarial Robustness — Level 3 (Master): Systematic Vulnerability Mapping",
        "topic":       "Professional security researchers don't wait to be attacked — they map every possible attack vector before deployment. Applied epistemically: map every logical vulnerability in your most important beliefs before an adversary finds them.",
        "steelman":    "What is the strongest argument that systematic vulnerability mapping of personal beliefs leads to paralysis — that some beliefs need to be held with certainty to function as motivational foundations?",
        "example":     (
            "The STRIDE framework (adapted from security) applied to beliefs:\n\n"
            "S — Spoofing: could someone present false evidence that looks like real evidence?\n"
            "T — Tampering: could the source data have been manipulated before you saw it?\n"
            "R — Repudiation: could the cited authority credibly deny having said what you attributed?\n"
            "I — Information disclosure: are you missing information that would change this belief?\n"
            "D — Denial of service: is this argument vulnerable to a simple 'I don't accept that'?\n"
            "E — Elevation of privilege: does this belief rest on an argument that claims more authority than it has?\n\n"
            "Run every important belief through STRIDE before you defend it publicly.\n"
            "Beliefs with multiple STRIDE vulnerabilities are brittle — "
            "they may hold up in friendly conversations but collapse under pressure."
        ),
        "activity":    (
            "STRIDE Analysis:\n"
            "Pick one belief you've defended recently.\n"
            "Work through all 6 STRIDE categories.\n"
            "Write one sentence for each: how vulnerable is this belief to this type of attack?\n\n"
            "Then: what is the minimum work required to close each vulnerability?\n"
            "Seal your STRIDE analysis in the Truth Debt Ledger with a verification deadline."
        ),
        "age_hint":    "14+",
        "xp": 58, "rune": "ADVERSARIAL•ETERNAL•RUNE", "min_coherence": 0.75,
        "grants_badge": "⚔️ Red Team Master — Vulnerability Map Complete",
        "prerequisites": ["adversarial-robustness-2", "admin-2"],
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── NARRATIVE WARFARE TRACK (3 lessons) ──────────────────────────────────
    # How stories shape reality at civilizational scale.
    # The deepest manipulation layer — harder to detect than logical fallacies
    # because it operates before the logical layer is engaged.
    # ══════════════════════════════════════════════════════════════════════════
    "narrative-warfare-1": {
        "phd_extension": "The Frame Swap Exercise at PhD level: take any major news story. Identify: the hero, the villain, the victim. Now assign DIFFERENT roles to the same actors and rewrite the story with equal factual accuracy. The goal is to find the framing that makes the most accurate predictions about what will happen next — not the most compelling narrative. Track prediction accuracy over 30 days. The frame with better predictions is epistemically superior.",
        "title":       "Narrative Warfare — Level 1: Stories Are Not Just Stories",
        "topic":       "The human brain does not primarily process information as facts — it processes information as stories. Whoever controls the narrative frame controls which facts seem relevant, which questions seem reasonable, and which conclusions feel natural.",
        "steelman":    "What is the strongest argument that narrative analysis is just post-hoc pattern recognition — that people see 'narrative control' everywhere, which leads to unfalsifiable conspiracy thinking rather than genuine insight?",
        "example":     (
            "The same facts, two different frames:\n\n"
            "FRAME A: 'Illegal immigration is driving up crime rates and threatening '\n"
            "community safety in border states.'\n"
            "FRAME B: 'Undocumented immigrants are fleeing desperate conditions and '\n"
            "contributing to local economies despite legal barriers.'\n\n"
            "The facts underlying both frames are largely the same. "
            "The frame determines which facts are highlighted, which questions "
            "are asked, and which solutions seem logical.\n\n"
            "Narrative warfare is not lying — it is controlling which slice "
            "of reality becomes the default reality for the audience.\n\n"
            "Three levels of narrative warfare:\n"
            "Level 1: choosing which events to report (selection)\n"
            "Level 2: choosing how to describe events (framing)\n"
            "Level 3: choosing which questions are legitimate to ask (Overton window)\n\n"
            "AUBIEETERNAL application: the Narrative Pattern Detector identifies "
            "when multiple institutions are running the same frame simultaneously."
        ),
        "activity":    (
            "Frame Swap Exercise:\n"
            "Take any major news story this week.\n"
            "Write the same facts in 3 different frames — each one accurate "
            "but emphasizing different aspects.\n\n"
            "After: which frame did the original story use?\n"
            "Who benefits from that frame?\n"
            "What questions does each frame make natural vs. strange?"
        ),
        "age_hint":    "12+",
        "xp": 40, "rune": "NARRATIVE•RUNE", "min_coherence": 0.68,
    },
    "narrative-warfare-2": {
        "title":       "Narrative Warfare — Level 2: The Infrastructure of Story",
        "topic":       "Narratives have structural components — heroes, villains, victims, causes, solutions. Whoever controls these structural assignments controls how the audience will respond. This structure is invisible until you learn to see it.",
        "steelman":    "What is the strongest argument that narrative structure analysis is a tool that sophisticated bad actors misuse to dismiss any unfavorable story as 'narrative warfare,' making it a weapon for epistemic nihilism rather than clarity?",
        "example":     (
            "The narrative assignment game:\n\n"
            "The exact same event can assign roles completely differently:\n\n"
            "Event: police officer shoots an unarmed person\n"
            "Narrative A: hero=victim's family, villain=police, cause=systemic racism\n"
            "Narrative B: hero=police, villain=dangerous street, cause=policy failure\n"
            "Narrative C: hero=community advocates, villain=media sensationalism, cause=poverty\n\n"
            "Each narrative implies different solutions, different villains, "
            "different policy responses. The assignment of roles IS the argument — "
            "the factual content comes after.\n\n"
            "Robert McKee's story structure (used by Hollywood and politicians alike):\n"
            "• Inciting incident (establishes the stakes)\n"
            "• Rising action (proves the villain is real)\n"
            "• Crisis (the audience must choose sides)\n"
            "• Climax (the hero must act)\n"
            "• Resolution (the lesson is sealed)\n\n"
            "Every political speech follows this structure. "
            "Seeing it doesn't make the story false — "
            "but it gives you the choice to evaluate the structure separately from the content."
        ),
        "activity":    (
            "Narrative Structure Map:\n"
            "Take one important belief you hold about a social issue.\n"
            "Map it: who is the hero? Villain? Victim? Cause? Solution?\n\n"
            "Now: swap the villain and hero. Does the story still work with the same facts?\n"
            "If yes: the narrative assignment is doing more work than the evidence.\n"
            "If no: you've found a genuine asymmetry that favors your framing — "
            "but you still need to explain why this assignment is correct."
        ),
        "age_hint":    "13+",
        "xp": 45, "rune": "NARRATIVE•RUNE", "min_coherence": 0.70,
    },
    "narrative-warfare-3": {
        "title":       "Narrative Warfare — Level 3 (Master): Building Narrative-Resistant Epistemology",
        "topic":       "The goal is not to escape narrative — that is impossible. The goal is to develop the habit of noticing the frame before accepting the content. Narrative-resistant epistemology holds both the story AND the underlying evidence simultaneously.",
        "steelman":    "What is the strongest argument that 'narrative-resistant epistemology' is just a more sophisticated narrative — that everyone who claims to see through frames is actually trapped in a meta-frame of cynical sophistication that is just as limiting?",
        "example":     (
            "The four-layer reading protocol:\n\n"
            "Layer 1 — CONTENT: what are the literal facts being claimed?\n"
            "Layer 2 — FRAME: what narrative structure presents these facts?\n"
            "Layer 3 — INCENTIVE: who benefits from this frame? What do they gain?\n"
            "Layer 4 — ALTERNATIVE: what frame would present the same facts differently? "
            "What does that frame make visible that this one hides?\n\n"
            "Applied to a news story:\n"
            "Layer 1: crime rates in city X rose 12% last year\n"
            "Layer 2: frame of 'crisis' and 'failure of current leadership'\n"
            "Layer 3: opposition party before an election\n"
            "Layer 4: crime rose from a 50-year low; still below 2010 levels\n\n"
            "None of this makes the 12% rise false. "
            "But it changes what the fact means — which is the whole game."
        ),
        "activity":    (
            "The Four-Layer Protocol applied to something you believe strongly:\n"
            "Pick one political or social belief.\n"
            "Work through all four layers honestly, including:\n"
            "- What narrative serves YOUR interests?\n"
            "- What frame do you benefit from being true?\n\n"
            "Seal the four-layer analysis in the Legacy Ledger.\n"
            "Revisit in 90 days. Has your analysis changed?"
        ),
        "age_hint":    "14+",
        "xp": 58, "rune": "NARRATIVE•SOVEREIGN•RUNE", "min_coherence": 0.74,
        "grants_badge": "🎭 Narrative Sovereign — Four-Layer Protocol Active",
        "prerequisites": ["narrative-warfare-2", "gatekeeper-4"],
    },



    # ══════════════════════════════════════════════════════════════════════════
    # ── UNIVERSE TRACK — DEEP COSMOLOGY (6 lessons, universe-1 through 6) ────
    # My genuine addition. — Claude
    #
    # The deepest question is not "what should I do?" but "what is this?"
    # This track treats cosmology not as a collection of facts but as the
    # living edge of human ignorance — the place where honest uncertainty
    # meets the most profound questions anyone has ever asked.
    #
    # A 7-year-old can wonder at the Big Bang. A PhD cosmologist can spend
    # a career on the Hubble tension. The same lesson works at both depths.
    # ══════════════════════════════════════════════════════════════════════════



    # ══════════════════════════════════════════════════════════════════════════
    # ── COSMOS DEEP TRACK (6 lessons, cosmos-1 through cosmos-6) ─────────────
    # My genuine addition. — Claude
    # Deep cosmology: scale, Big Bang reality, dark matter/energy honest uncertainty,
    # fine-tuning, arrow of time, Fermi Paradox.
    # The universe track every sovereign school should have at PhD depth.
    # ══════════════════════════════════════════════════════════════════════════
    "cosmos-1": {
        "title":       "Cosmos — Level 1: How Big Is Everything? (Cognitive Confrontation with Scale)",
        "topic":       "The universe is not just big. It is big in a way that human intuition cannot grasp. This lesson builds the genuine cognitive confrontation with scale — not memorizing numbers, but actually feeling the incomprehensibility.",
        "steelman":    "What is the strongest argument that obsessing over cosmic scale is psychologically harmful — that it makes human concerns seem trivial and contributes to nihilism rather than wonder?",
        "example":     (
            "The scale ladder (each step is 100x larger):\n"
            "1 meter — you → 10 km — a city → 100,000 km — Earth to Moon → "
            "10 million km — Sun's diameter → 1 light-year — 9.5 trillion km\n"
            "(Voyager 1 has traveled 0.002 light-years in 47 years)\n"
            "4.2 light-years — nearest star → 100,000 light-years — Milky Way\n"
            "2.5 million light-years — Andromeda → 93 billion light-years — observable universe\n\n"
            "The confrontation: Andromeda's light left before Homo sapiens existed. "
            "The observable universe is the sphere from which light has had time to reach us. "
            "Beyond it: more universe, probably infinite, definitely unobservable.\n\n"
            "Sagan: 'The universe is not required to be in perfect harmony with human ambition.'\n\n"
            "The counterpoint that matters: a universe 13.8 billion years old produced "
            "entities that can UNDERSTAND that the universe is 13.8 billion years old. "
            "That is not made smaller by the scale. It is made more remarkable."
        ),
        "activity":    (
            "The Pale Blue Dot meditation: find the Voyager 1 image of Earth from 6 billion km.\n"
            "Look at it for 3 minutes. Write: what do you feel? What changes? What stays the same?\n\n"
            "Age 14+: calculate the angular size of Earth as seen from Voyager 1.\n"
            "angular_size_arcsec = 206265 × diameter/distance.\n"
            "Compare to human eye resolution (1 arcminute = 60 arcsec)."
        ),
        "age_hint":    "All ages",
        "xp": 40, "rune": "COSMOS•RUNE", "min_coherence": 0.55,
    },
    "cosmos-2": {
        "title":       "Cosmos — Level 2: What the Big Bang Actually Claims (And What It Doesn't)",
        "topic":       "The Big Bang is the most misunderstood concept in popular science. It was not an explosion in space. It was an expansion of space itself. The Hubble tension remains unresolved at 5σ in 2026 — this is a live scientific crisis.",
        "steelman":    "What is the strongest argument that the Big Bang model is likely to be substantially revised — and that we should hold it with much more uncertainty than popular science communication suggests?",
        "example":     (
            "What the Big Bang claims: space itself was smaller, hotter, denser 13.8 billion years ago.\n\n"
            "Four lines of evidence:\n"
            "1. Hubble's Law: galaxies recede at speed proportional to distance\n"
            "2. CMB: 2.7K uniform radiation — afterglow of the early hot universe\n"
            "3. Big Bang Nucleosynthesis: H/He/Li ratio matches predictions precisely\n"
            "4. Galaxy formation: simulations match large-scale structure\n\n"
            "What it does NOT explain: what caused it, what existed before it "
            "(time may not have existed before), why the initial conditions were what they were.\n\n"
            "The Hubble Tension (2026 — active crisis): CMB gives H0 ~ 67.4 km/s/Mpc. "
            "Distance ladder gives ~ 73 km/s/Mpc. Discrepancy at 5σ — statistically "
            "impossible by chance. Either new physics, systematic errors, or both."
        ),
        "activity":    (
            "For each of the 4 evidence lines: what would we observe if the model were false?\n"
            "What is the best alternative explanation? What experiment distinguishes them?\n\n"
            "PhD: look up current status of Hubble tension. Three leading explanations?\n"
            "What observation would resolve it? A 5σ discrepancy = what probability?"
        ),
        "age_hint":    "9+",
        "xp": 45, "rune": "COSMOS•RUNE", "min_coherence": 0.60,
        "phd_extension": "H0 tension: CMB gives 67.4, distance ladder gives 73.0 km/s/Mpc at ~5σ. Read Verde, Treu & Riess (2019). Evaluate: new physics beyond ΛCDM, systematic errors, or both. Which would you bet on at 2:1 odds? Pre-register your prediction and resolution criteria.",
    },
    "cosmos-3": {
        "title":       "Cosmos — Level 3: Dark Matter and Dark Energy — 95% Unknown",
        "topic":       "95% of the universe is something we cannot see or directly detect. Dark matter and dark energy are not confirmed facts — they are the best current explanations for anomalies. This lesson teaches how to hold well-evidenced mysteries honestly.",
        "steelman":    "What is the strongest argument that dark matter and dark energy are placeholder concepts that will be replaced by modifications to gravity — rather than real substances we haven't detected yet?",
        "example":     (
            "Dark matter evidence: galaxy rotation curves, gravitational lensing, Bullet Cluster.\n"
            "Dark matter uncertainty: zero direct particle detection, MOND explains some rotation curves.\n\n"
            "Dark energy: 1998 supernova survey found expansion is accelerating (Nobel 2011).\n"
            "The cosmological constant (Λ) fits the data but QFT predicts a value 10^120 times larger "
            "— the worst theoretical prediction in physics.\n\n"
            "Both are REAL ANOMALIES requiring explanation. The form of that explanation is open."
        ),
        "activity":    (
            "Anomaly Inventory: for each mystery — what is the observation that doesn't fit?\n"
            "Best two explanations? Distinguishing prediction?\n\n"
            "Register credences: P(particle dark matter | evidence) = ?\n"
            "P(modified gravity) = ? Seal in Truth Debt Ledger. Revisit in 5 years."
        ),
        "age_hint":    "11+",
        "xp": 50, "rune": "COSMOS•RUNE", "min_coherence": 0.65,
        "phd_extension": "The cosmological constant problem: QFT predicts vacuum energy ~10^94 g/cm^3, observed ~10^-29 g/cm^3. Discrepancy: 120-123 orders of magnitude. Read Weinberg (1989). Evaluate three resolutions: anthropic selection, SUSY cancellation, modified gravity. Which has most predictive content? What falsifies each?",
    },
    "cosmos-4": {
        "title":       "Cosmos — Level 4: Fine-Tuning and the Anthropic Principle",
        "topic":       "The physical constants appear fine-tuned for complexity and life. This is either the most profound fact in cosmology or a profound cognitive illusion. Both possibilities are deeply strange.",
        "steelman":    "What is the strongest argument that the fine-tuning argument for a designed universe is actually compelling — and that the multiverse hypothesis is less scientifically respectable than it appears?",
        "example":     (
            "Fine-tuning examples: strong nuclear force 2% stronger = no hydrogen. "
            "Cosmological constant 10^120 larger = no galaxies. Proton/electron mass ratio altered = no stable atoms.\n\n"
            "Three responses:\n"
            "1. Design: conscious agent chose constants (not scientifically testable, not incoherent)\n"
            "2. Multiverse: many universes, different constants; anthropic selection explains ours "
            "(predicted by string landscape, not directly testable — some call this pseudoscience)\n"
            "3. Necessity: only one logically consistent set of constants "
            "(M-theory ambition, unfulfilled)\n\n"
            "Honest position: fine-tuning is a genuine puzzle. None of the three fully satisfies."
        ),
        "activity":    (
            "Assign credences summing to 100%:\n"
            "P(design by conscious agent) = ?%\n"
            "P(multiverse + anthropic selection) = ?%\n"
            "P(physical necessity) = ?%\n"
            "P(other explanation not yet conceived) = ?%\n"
            "Justify each in 2 sentences. Seal. What single observation would shift them most?"
        ),
        "age_hint":    "13+",
        "xp": 55, "rune": "COSMOS•RUNE", "min_coherence": 0.68,
        "phd_extension": "Tegmark's mathematical universe + Weinberg's 1987 anthropic prediction of non-zero Λ (successful before its 1998 discovery). Evaluate: does one successful anthropic prediction give the multiverse genuine Bayesian credence? Compute formally with Bayes theorem. What prior probability should we assign to the multiverse before this prediction?",
    },
    "cosmos-5": {
        "title":       "Cosmos — Level 5: Information, Entropy, and the Arrow of Time",
        "topic":       "Why does time flow in one direction? Physics is time-symmetric but time has a clear direction. This sits at the intersection of thermodynamics, cosmology, and philosophy of mind.",
        "steelman":    "What is the strongest argument that the arrow of time is not fundamental but emergent from our particular perspective as information-processing systems — and that 'time flowing forward' says more about us than the universe?",
        "example":     (
            "The puzzle: Newtonian mechanics, Maxwell's equations, QM, GR — all time-symmetric. "
            "Yet eggs never unscramble, smoke never un-diffuses, memories are of the past only.\n\n"
            "The thermodynamic arrow: entropy always increases (Second Law). "
            "But WHY did the universe start in extraordinarily low entropy?\n\n"
            "Penrose: initial entropy was 1 in 10^(10^123) — either the most improbable fact "
            "in science or something profound about boundary conditions.\n\n"
            "Carroll: the Big Bang was a low-entropy initial condition; arrow = entropy increasing.\n"
            "Barbour: time doesn't flow at all — static 'Platonia', time is an illusion."
        ),
        "activity":    (
            "Time Reversal Thought Experiment: imagine videos of coffee cup breaking, "
            "gas spreading, star forming, memory forming. "
            "Which direction is immediately obvious for each and why?\n\n"
            "Register: is time fundamental or emergent? What evidence would change your answer?"
        ),
        "age_hint":    "13+",
        "xp": 58, "rune": "COSMOS•RUNE", "min_coherence": 0.70,
        "phd_extension": "Penrose (2004) Chapter 27 on Big Bang low entropy. Calculate: for N = 10^80 particles, number of macrostates ≈ N log N, number of microstates ≈ exp(N). Compute both. Then read Carroll & Chen (2004) on spontaneous inflation from de Sitter space as a proposed explanation. Does it actually solve the problem or just push it back?",
    },
    "cosmos-6": {
        "title":       "Cosmos — Level 6 (Master): The Fermi Paradox — Where Is Everyone?",
        "topic":       "If intelligent life is common, the galaxy should be full of it. It isn't — or we haven't detected it. This silence is one of the most profound empirical facts we possess, and it has existential implications.",
        "steelman":    "What is the strongest argument that the Fermi Paradox is not actually a paradox — that our prior expectation of detectable alien civilizations was always poorly founded, and the silence is exactly what we should expect?",
        "example":     (
            "Drake Equation uncertainty ladder:\n"
            "R* (star formation): ~3/year — well constrained\n"
            "fp (planets per star): ~1 — we know most stars have planets\n"
            "ne (habitable planets): uncertain, 0.1-0.4\n"
            "fl, fi, fc, L: almost completely unknown\n\n"
            "The Great Filter (Hanson 1998): either the filter is BEHIND us "
            "(life/intelligence/civilization are rare — lonely but safe) "
            "or AHEAD of us (civilizations destroy themselves — existentially concerning).\n\n"
            "The most alarming possible discovery: microbial life on Mars. "
            "It would rule out 'life is the filter' and push it ahead of us.\n\n"
            "60+ years of SETI: zero confirmed detections. "
            "But we've searched a tiny fraction of parameter space."
        ),
        "activity":    (
            "Great Filter Credence Map (must sum to 100%):\n"
            "P(abiogenesis is extremely rare) = ?%\n"
            "P(eukaryotic complexity is extremely rare) = ?%\n"
            "P(intelligence is extremely rare) = ?%\n"
            "P(civilizations always self-destruct) = ?%\n"
            "P(civilizations hide deliberately) = ?%\n"
            "P(we just haven't looked enough) = ?%\n\n"
            "What single observation would most shift your map? Seal it. "
            "This is existential prediction research."
        ),
        "age_hint":    "12+",
        "xp": 62, "rune": "COSMOS•ETERNAL•RUNE", "min_coherence": 0.72,
        "phd_extension": "Read Hanson (1998) 'The Great Filter' and Bostrom (2008) 'Where Are They?' Apply Bayes theorem: if microbial life found on Mars tomorrow, how much should P(Great Filter ahead) increase? Formalize with explicit priors. Then rank Webb's (2002) 50 solutions by (testability × explanatory power). This is the most important existential research question in astronomy.",
        "grants_badge": "🌌 Cosmos Master — The Silence and the Scale Are Both Real",
        "lattice_node": "cosmos-deep-track-complete",
        "prerequisites": ["cosmos-4", "cosmos-5"],
    },



    # ══════════════════════════════════════════════════════════════════════════
    # ── DECISION THEORY & RATIONALITY UNDER UNCERTAINTY (5 lessons) ──────────
    # Claude's genuine addition #1.
    #
    # The most practically important intellectual skill humanity lacks at scale.
    # Almost every catastrophic personal and civilizational decision can be
    # traced to systematic errors in reasoning under uncertainty.
    # This track teaches the actual tools: expected utility, calibration,
    # risk aversion, Pascal's mugging, tail risk, and time discounting.
    #
    # A 10-year-old can learn to compare two choices honestly.
    # A PhD student can engage with Newcomb's Problem and one-boxing.
    # The same track works at both depths.
    # ══════════════════════════════════════════════════════════════════════════
    "decision-1": {
        "title":       "Decision Theory — Level 1: Expected Value (Why Math Beats Gut)",
        "topic":       "Every decision is a bet. Expected value is the tool that tells you whether the bet is worth taking. Most people make important life decisions without it — and pay a predictable, measurable price for not knowing.",
        "steelman":    "What is the strongest argument that expected value reasoning is actually harmful for most everyday decisions — that it encourages cold calculation over wisdom, intuition, and moral commitments?",
        "example":     (
            "Expected Value = (probability of outcome A × value of A) + (probability of outcome B × value of B)\n\n"
            "Example — should you wear a seatbelt?\n"
            "P(serious crash this trip) ≈ 0.0000025\n"
            "Cost of NOT wearing belt if crash: ~$500,000 equivalent suffering\n"
            "Cost of wearing belt: minor inconvenience ~$0.01\n"
            "EV(no belt) = 0.0000025 × $500,000 + 0.9999975 × $0 = $1.25 expected cost per trip\n"
            "EV(belt) = 0.0000025 × $50,000 + 0.9999975 × -$0.01 ≈ $0.125\n\n"
            "The seatbelt costs 10x less in expected value. Every trip. \n\n"
            "Where expected value goes wrong:\n"
            "1. When you can't afford the downside even if unlikely (insurance logic)\n"
            "2. When the distribution has fat tails (rare but catastrophic events)\n"
            "3. Pascal's Mugging: astronomically small probability × astronomically large value "
            "= paralysis. Expected value alone doesn't handle this well.\n\n"
            "The key insight: even an imperfect expected value calculation beats gut feeling "
            "for decisions with clear stakes and known probabilities."
        ),
        "activity":    (
            "Expected Value Audit:\n"
            "Pick 3 decisions your family made in the last month.\n"
            "For each: estimate the probabilities and values (roughly).\n"
            "Calculate the expected value of each option you considered.\n\n"
            "Did you make the highest expected value choice?\n"
            "If not — why not? Was it risk aversion? Values you didn't quantify? "
            "Or was the EV calculation wrong?\n\n"
            "Seal your audit."
        ),
        "age_hint":    "10+",
        "xp": 38, "rune": "DECISION•RUNE", "min_coherence": 0.62,
    },
    "decision-2": {
        "title":       "Decision Theory — Level 2: Calibration — Are You Right as Often as You Think?",
        "topic":       "Calibration is the correspondence between stated confidence and actual accuracy. A perfectly calibrated person who says '70% confident' is right 70% of the time. Most people are not calibrated. Learning to be is the most directly improvable intellectual skill.",
        "steelman":    "What is the strongest argument that obsessing over calibration is counterproductive — that some degree of overconfidence is adaptive, motivates action, and produces better outcomes than accurate but paralyzing uncertainty?",
        "example":     (
            "The calibration experiment:\n"
            "Ask: 'Is the circumference of the Earth more or less than 10,000 miles?'\n"
            "Most people answer incorrectly AND are highly confident.\n"
            "This is the miscalibration signature: high confidence + wrong.\n\n"
            "Kahneman's finding: experts are often WORSE calibrated than novices "
            "on their own domain because expertise increases confidence faster than accuracy.\n\n"
            "The superforecaster result (Tetlock, 2015):\n"
            "A small fraction of people are significantly better than experts at predicting "
            "geopolitical events — not because they know more, but because they are better calibrated.\n"
            "The key habits: track predictions explicitly, update frequently, "
            "break big questions into smaller estimable components.\n\n"
            "Calibration training works: Philip Tetlock showed that people who track their "
            "predictions and get feedback improve their calibration measurably within months.\n\n"
            "AUBIEETERNAL application: the belief ledger in the Cosmos Dashboard "
            "is a calibration training tool. Every entry is data."
        ),
        "activity":    (
            "The 20-Question Calibration Test:\n"
            "Ask 20 factual questions (trivia-style). For each, give a confidence percentage.\n"
            "After answering all 20: check the answers.\n"
            "Plot: for questions where you said 70% confident, what fraction were you right?\n"
            "If 70% confidence → 70% accuracy: perfectly calibrated.\n"
            "If 70% confidence → 90% accuracy: underconfident.\n"
            "If 70% confidence → 50% accuracy: overconfident.\n\n"
            "Run this monthly for 6 months and plot your calibration curve's improvement."
        ),
        "age_hint":    "11+",
        "xp": 42, "rune": "DECISION•RUNE", "min_coherence": 0.65,
        "phd_extension": "Compute your Brier score (mean squared error between confidence and outcome: BS = (1/N)∑(confidence_i - outcome_i)². Perfect calibration = 0.0. Random = 0.25. Run 100 predictions and compute your Brier score. Then apply reliability diagram analysis: group by confidence decile, plot mean confidence vs mean accuracy. The deviation from the diagonal IS your calibration error.",
    },
    "decision-3": {
        "title":       "Decision Theory — Level 3: Risk Aversion, Time Discounting, and Scope Insensitivity",
        "topic":       "Three systematic biases make otherwise smart people make terrible decisions at scale: they are disproportionately risk-averse for gains, they discount the future irrationally, and they are almost blind to differences in magnitude. Understanding these biases is the first step to correcting them.",
        "steelman":    "What is the strongest argument that risk aversion, time discounting, and scope insensitivity are not biases at all — but rational adaptations to the real uncertainties of human life that evolved because they were survival-promoting?",
        "example":     (
            "RISK AVERSION:\n"
            "Kahneman & Tversky: losing $100 feels roughly twice as bad as gaining $100 feels good.\n"
            "This is loss aversion — and it creates systematic irrationality.\n"
            "People refuse positive expected value bets if there's any chance of loss.\n"
            "Applied: people leave money in low-yield accounts rather than invest, "
            "because the loss possibility outweighs the gain probability in feeling, not math.\n\n"
            "TIME DISCOUNTING:\n"
            "Humans discount future rewards at rates that imply extraordinary irrationality.\n"
            "Revealed preference: many people prefer $50 today over $100 in a year — "
            "implying a ~100% annual discount rate.\n"
            "Applied: people make health, financial, and environmental decisions as if the "
            "future barely exists. Civilizational policy is particularly vulnerable.\n\n"
            "SCOPE INSENSITIVITY:\n"
            "Kahneman: people donate roughly the same amount to save 2,000 birds vs 200,000 birds.\n"
            "The emotional response to 'birds in danger' doesn't scale with the magnitude.\n"
            "Applied: humanity treats 1 death and 100,000 deaths with similar emotional urgency "
            "if the story is vivid enough. Policy follows emotion, not math."
        ),
        "activity":    (
            "Bias Audit of One Recent Decision:\n"
            "Pick one important decision you made recently (financial, health, career).\n"
            "1. Was risk aversion operating? Did you avoid a positive EV option because of "
            "the downside possibility?\n"
            "2. Was time discounting operating? Did you weight the present too heavily vs. "
            "10-year consequences?\n"
            "3. Was scope insensitivity operating? Did the magnitude of the stakes "
            "actually register, or just the vivid story?\n\n"
            "Redesign the decision with all three biases corrected. "
            "Would you have chosen differently?"
        ),
        "age_hint":    "12+",
        "xp": 48, "rune": "DECISION•RUNE", "min_coherence": 0.68,
        "phd_extension": "Read Kahneman (2011) Chapters 25-28 on prospect theory. Implement the value function V(x) = x^0.88 for gains, -2.25 × (-x)^0.88 for losses. Plot it. Compute the certainty equivalent for: (80% chance of $100) vs ($80 certain). Does the model predict the standard human preference? Then apply hyperbolic discounting D(t) = 1/(1+kt) with k=0.3 and compare to exponential discounting. Which better predicts your own time preferences? Run a revealed-preference test on yourself.",
    },
    "decision-4": {
        "title":       "Decision Theory — Level 4: Tail Risks, Black Swans, and Fat Tails",
        "topic":       "Normal distributions are everywhere in textbooks and almost nowhere in the real world for the things that matter most. Wealth, wars, pandemics, earthquakes, market crashes — all fat-tailed. Understanding fat tails changes how you should prepare for the future.",
        "steelman":    "What is the strongest argument that tail risk obsession is paralyzing — that the infinite-regress of 'but what about black swans?' leads to hoarding gold in bunkers rather than productive engagement with the world?",
        "example":     (
            "Thin tails vs fat tails:\n\n"
            "THIN-TAILED (Gaussian): human height, IQ, daily temperature change.\n"
            "No one is 10 feet tall. The distribution has hard limits.\n"
            "The most extreme event is only ~3-5 standard deviations from the mean.\n\n"
            "FAT-TAILED (Pareto/power law): wealth, earthquake magnitude, "
            "book sales, city sizes, pandemic deaths, stock market crashes.\n"
            "The richest person is millions of times richer than the median.\n"
            "The most damaging earthquake releases 1,000× more energy than the median.\n"
            "The worst pandemic kills 100× more than the typical flu season.\n\n"
            "Why this matters:\n"
            "In thin-tailed worlds: the past predicts the future well. Averages matter.\n"
            "In fat-tailed worlds: a single event can dominate all previous history. "
            "The average is misleading. Preparation for the tail IS the strategy.\n\n"
            "Taleb's key insight: financial models that assumed thin tails caused the "
            "2008 financial crisis. The models said a 25-standard-deviation event was "
            "impossible. It happened on several consecutive days.\n\n"
            "AUBIEETERNAL preparation: the barbell strategy. "
            "Maximum safety in most of your resources + "
            "maximum optionality with a small portion. "
            "Never be exposed to catastrophic downside."
        ),
        "activity":    (
            "Family Risk Map:\n"
            "List the 10 biggest risks your family faces.\n"
            "For each: is this thin-tailed (predictable range) or fat-tailed (rare catastrophe possible)?\n"
            "For the fat-tailed ones: what is the maximum possible downside?\n"
            "Are you prepared for that downside, or only for the typical case?\n\n"
            "Design: one change to your preparation that addresses the tail, not the mean."
        ),
        "age_hint":    "13+",
        "xp": 52, "rune": "DECISION•RUNE", "min_coherence": 0.70,
        "phd_extension": "Read Taleb (2007) The Black Swan, Chapter 15 on the Mandelbrot fractal and power laws. Fit a power law to any dataset you care about (wealth in your country, earthquake magnitudes, city populations — all available publicly). Use: log(rank) vs log(value) should be linear if power-law. Compute the exponent α. If α < 2, the distribution has infinite variance. If α < 1, infinite mean. This is what makes these distributions so dangerous for standard statistical analysis.",
    },
    "decision-5": {
        "title":       "Decision Theory — Level 5 (Master): Newcomb's Problem and Decision Theory Frontiers",
        "topic":       "Newcomb's Problem has split decision theorists for 50 years. It reveals a fundamental tension between two otherwise coherent approaches to rationality. Understanding it is not just academic — it illuminates every situation where your decision is correlated with what has already been determined.",
        "steelman":    "What is the strongest argument that Newcomb's Problem is a philosophical puzzle with no practical implications — that the correct answer is obvious and any difficulty is just confused thinking about causation vs. correlation?",
        "example":     (
            "Newcomb's Problem:\n\n"
            "Omega (a perfect predictor) has placed either $1M in Box B (opaque) "
            "or nothing, based on its prediction of your choice.\n"
            "If it predicted you'd take only Box B: $1M inside.\n"
            "If it predicted you'd take both boxes: $0 in Box B.\n"
            "Box A (transparent) always contains $1,000.\n\n"
            "TWO-BOXING (Causal Decision Theory — CDT):\n"
            "The money is already in the box. Your choice cannot change it. "
            "Whatever is in Box B, you're better off taking Box A too. "
            "Dominant strategy: take both boxes.\n\n"
            "ONE-BOXING (Evidential Decision Theory — EDT):\n"
            "Your choice is evidence about what Omega predicted. "
            "One-boxers reliably find $1M. Two-boxers reliably find $0. "
            "If you want to be the kind of person who finds $1M, one-box.\n\n"
            "Empirical result: the vast majority of professional decision theorists "
            "who think carefully about this one-box — despite CDT saying two-box.\n\n"
            "The practical extension: climate agreements, nuclear deterrence, "
            "voting paradoxes, cooperation in prisoner's dilemmas — all have this "
            "structure: your choice affects what others will have done (causally) "
            "or correlates with outcomes (evidentially)."
        ),
        "activity":    (
            "The Cooperation Lab:\n"
            "Play 20 rounds of Prisoner's Dilemma with a family member.\n"
            "Track: what strategy does each person run?\n"
            "At what round (if ever) does cooperation emerge?\n\n"
            "Then: change the structure so each person's choice is announced before "
            "the other must commit. Does this change cooperation?\n\n"
            "Connect to Newcomb: when your decision is predictable, which decision theory "
            "should guide you? What does your intuition say vs. what do the outcomes say?"
        ),
        "age_hint":    "15+ / PhD",
        "xp": 72, "rune": "DECISION•ETERNAL•RUNE", "min_coherence": 0.76,
        "grants_badge": "🎯 Decision Theorist — Newcomb's Problem Resolved (For Now)",
        "phd_extension": "Read Yudkowsky (2010) 'Timeless Decision Theory' and Soares & Fallenstein (2014) 'Toward Idealized Decision Theory'. Implement both CDT and EDT as Python functions for a generalized Newcomb-like problem. Show that: under CDT, two-boxing is optimal. Under EDT, one-boxing is optimal. Under TDT, one-boxing is optimal but for different reasons. Analyze: which decision theory would you want an AI to implement? This is directly relevant to AI alignment.",
        "prerequisites": ["decision-4"],
        "lattice_node": "decision-theory-rationality-complete",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── EPISTEMOLOGY OF EXPERTISE & INSTITUTIONAL TRUST (5 lessons) ──────────
    # Claude's genuine addition #2.
    #
    # The most important civic skill in 2026.
    # When should you defer to experts? When should you think independently?
    # When are institutions trustworthy? When are they captured?
    # When is expert consensus strong and when is it a social phenomenon?
    #
    # These questions determine whether democracies function or collapse.
    # Most citizens cannot answer them. AUBIEETERNAL families can.
    # ══════════════════════════════════════════════════════════════════════════
    "expertise-1": {
        "title":       "Expertise Track — Level 1: When Should You Defer to Experts?",
        "topic":       "Expert consensus should be taken seriously — but not unconditionally. The question is not 'do experts agree?' but 'under what conditions does expert consensus reliably track truth?' Understanding those conditions is the most important civic skill of our era.",
        "steelman":    "What is the strongest argument that in a complex world, nearly all citizens should defer to expert consensus on nearly all topics, and that promoting independent evaluation by non-experts causes more harm than good?",
        "example":     (
            "Expert consensus IS highly reliable when:\n"
            "• The field has strong feedback loops (medicine vs. nutrition)\n"
            "• Predictions can be tested on human timescales (epidemiology vs. economics)\n"
            "• Replication is standard and failures are costly (engineering vs. social science)\n"
            "• Funding is independent of desired outcomes (basic physics vs. pharmaceutical trials)\n"
            "• The question is technical, not normative (drug safety vs. drug policy)\n\n"
            "Expert consensus is LESS reliable when:\n"
            "• The field has poor replication rates (psychology: ~50%, nutrition: ~30%)\n"
            "• Experts have financial stakes in particular conclusions\n"
            "• The question is normative disguised as technical\n"
            "• The consensus formed under political pressure\n"
            "• Paradigm incumbents control journal access (see Kuhn)\n\n"
            "The crucial distinction: 'scientists agree' (sociological fact) "
            "vs. 'the evidence supports' (epistemic fact). "
            "These often coincide. They sometimes diverge."
        ),
        "activity":    (
            "Expert Consensus Audit:\n"
            "Pick three areas where you typically defer to experts.\n"
            "For each: score it on the reliability criteria above (1-5 each).\n"
            "Total score: 20-25 = high reliability; 10-15 = moderate; below 10 = verify carefully.\n\n"
            "Pick one area where you got below 15 and find the primary source "
            "(not the expert's summary, not the news — the actual evidence). "
            "Does the expert interpretation match what the data say?"
        ),
        "age_hint":    "13+",
        "xp": 40, "rune": "EXPERTISE•RUNE", "min_coherence": 0.65,
    },
    "expertise-2": {
        "title":       "Expertise Track — Level 2: How Institutions Fail — Regulatory Capture, Incentive Misalignment, Paradigm Lock",
        "topic":       "Institutions are not neutral truth-seekers. They are organizations with incentives, power structures, and survival instincts. Understanding how institutions systematically distort information is not cynicism — it is the prerequisite for trusting them appropriately.",
        "steelman":    "What is the strongest argument that focusing on how institutions fail makes us less able to benefit from what institutions do well — and that institution-skepticism is disproportionately exploited by bad actors who want to undermine legitimate expertise?",
        "example":     (
            "Three failure modes with documented examples:\n\n"
            "1. REGULATORY CAPTURE: regulated industries fund, lobby, and sometimes staff "
            "the agencies meant to regulate them. "
            "The FDA: ~75% of its drug evaluation funding comes from pharmaceutical fees. "
            "This doesn't make its approvals wrong — but it creates conflicts "
            "that should inform how much weight you place on approval alone.\n\n"
            "2. PUBLICATION BIAS + P-HACKING: journals prefer positive results. "
            "Researchers know this. Studies that don't find effects don't get published. "
            "This means the literature systematically overestimates effect sizes. "
            "The replication crisis (psychology, nutrition, social science) is this failure made visible.\n\n"
            "3. PARADIGM LOCK: Kuhn showed that normal science works within a paradigm "
            "and resists anomalies. This is efficient — but it means revolutionary ideas "
            "face institutional resistance before the evidence is evaluated. "
            "H. pylori causing ulcers: dismissed for 30 years, Nobel Prize in 2005. "
            "Prions causing disease: dismissed, Nobel Prize in 1997."
        ),
        "activity":    (
            "Institution Failure Audit:\n"
            "Pick one institution you rely on (FDA, CDC, your school, a news organization).\n"
            "Score it on three dimensions:\n"
            "1. Funding independence (who pays?) — 1 to 5\n"
            "2. Feedback mechanisms (does failure get corrected?) — 1 to 5\n"
            "3. Paradigm openness (are heterodox views fairly evaluated?) — 1 to 5\n\n"
            "A score below 9: trust but verify more carefully.\n"
            "A score above 12: higher baseline trust is warranted.\n\n"
            "Important: the goal is calibration, not dismissal."
        ),
        "age_hint":    "13+",
        "xp": 45, "rune": "EXPERTISE•RUNE", "min_coherence": 0.68,
        "phd_extension": "Read Ioannidis (2005) 'Why Most Published Research Findings Are False' — the most-cited paper in PLOS Medicine. Derive his central formula using Bayes theorem: PPV = (1-β)R / ((1-β)R + α) where R = pre-study odds ratio, α = significance level, β = false negative rate. Show that with R=0.1 (exploratory research), α=0.05, β=0.2, PPV < 0.5. Most positive findings are false. Apply to a field you care about.",
    },
    "expertise-3": {
        "title":       "Expertise Track — Level 3: The Dunning-Kruger Trap and Calibrated Autonomy",
        "topic":       "The Dunning-Kruger effect is often misunderstood — it is not just that ignorant people are overconfident. It is a systematic relationship between competence and metacognition at every level. The goal is not humility or confidence, but accurate self-assessment.",
        "steelman":    "What is the strongest argument that awareness of the Dunning-Kruger effect causes intelligent non-experts to excessively defer to authorities — making them easier to manipulate by credentialed bad actors who exploit this epistemic humility?",
        "example":     (
            "What Dunning-Kruger actually showed (Kruger & Dunning, 1999):\n"
            "Incompetent people overestimate their ability — because the skills needed "
            "to do a task well are the same skills needed to evaluate whether you're doing "
            "it well. You don't know what you don't know.\n\n"
            "The less-cited finding: experts UNDERESTIMATE their relative performance "
            "because they assume others find it as easy as they do.\n\n"
            "The calibration model (Dunning, 2011 revision):\n"
            "Competence and self-assessment accuracy both improve with expertise — "
            "but self-assessment lags competence in a predictable pattern.\n\n"
            "The epistemic sweet spot — the expert-adjacent position:\n"
            "Enough knowledge to identify the key variables and major uncertainties.\n"
            "Not so much investment in a sub-field that paradigm bias dominates.\n"
            "Can evaluate primary sources, not just secondary summaries.\n"
            "Knows what questions to ask experts.\n\n"
            "This is the AUBIEETERNAL target: not fully autonomous amateur reasoning, "
            "not unconditional deference, but informed engagement with primary evidence."
        ),
        "activity":    (
            "The Self-Assessment Calibration Test:\n"
            "Pick a domain where you consider yourself competent (e.g., cooking, coding, parenting).\n"
            "Write your self-assessment: what can you do, what can't you do, what do you not know?\n\n"
            "Then: find the most common failure mode in this domain among practitioners "
            "(search '[domain] common mistakes experts miss').\n\n"
            "Did you list it as a limitation? Or did you assume you don't make that mistake?\n"
            "That gap IS the Dunning-Kruger effect at work."
        ),
        "age_hint":    "13+",
        "xp": 48, "rune": "EXPERTISE•RUNE", "min_coherence": 0.70,
    },
    "expertise-4": {
        "title":       "Expertise Track — Level 4: Scientific Consensus vs Scientific Certainty",
        "topic":       "There is a crucial difference between 'scientists agree' and 'the evidence is conclusive.' Conflating them is one of the most common epistemic errors in public discourse. This lesson teaches how to distinguish strong consensus from weak consensus from contested science.",
        "steelman":    "What is the strongest argument that teaching people to distinguish consensus strength actively harms public health — that questioning any scientific consensus (even legitimately) provides cover for bad-faith actors who want to deny well-established findings?",
        "example":     (
            "Four levels of scientific confidence (with examples):\n\n"
            "LEVEL 1 — Virtually Certain (treat as fact):\n"
            "Earth is ~4.5 billion years old. Smoking causes cancer. Vaccines don't cause autism.\n"
            "Characteristics: replicated across independent methods, no plausible mechanism for doubt.\n\n"
            "LEVEL 2 — Strong Consensus (high prior, but track primary evidence):\n"
            "Effectiveness of SSRIs for depression, optimal dietary fat intake.\n"
            "Characteristics: good evidence, but effect sizes are contested and replication is imperfect.\n\n"
            "LEVEL 3 — Active Debate Among Experts (assign significant uncertainty):\n"
            "Precise mechanisms of long COVID, optimal early childhood intervention programs.\n"
            "Characteristics: multiple competing models, mixed replication, genuine expert disagreement.\n\n"
            "LEVEL 4 — Emerging or Contested (strong skepticism warranted):\n"
            "Microbiome effects on mental health, most social media + mental health research.\n"
            "Characteristics: early findings, poor replication, mechanistic story unverified.\n\n"
            "The error: treating Level 3 as Level 1 in public discourse."
        ),
        "activity":    (
            "Classify 10 scientific claims at the confidence level they deserve.\n"
            "For each: find one review paper (not news) and score:\n"
            "1. Number of independent replications\n"
            "2. Effect size (small/medium/large/very large)\n"
            "3. Mechanistic understanding (none/partial/strong)\n"
            "4. Contrary evidence quality (strong/weak/none found)\n\n"
            "What level does your evidence audit assign? "
            "Does it match how the claim is treated in public discourse?"
        ),
        "age_hint":    "14+",
        "xp": 52, "rune": "EXPERTISE•RUNE", "min_coherence": 0.72,
        "phd_extension": "Construct a GRADE-style evidence quality assessment for any health claim you care about. GRADE criteria: study design, risk of bias, inconsistency, indirectness, imprecision, publication bias. Classify the evidence as Very Low, Low, Moderate, or High. The GRADE system is used by Cochrane and WHO. Apply it to one claim that you believe is treated as higher confidence than it deserves. Publish your assessment to the Epistemic Commons.",
    },
    "expertise-5": {
        "title":       "Expertise Track — Level 5 (Master): Building Your Epistemic Independence Stack",
        "topic":       "True epistemic independence is not rejecting expertise — it is building the skill to engage with primary evidence directly, understand the limits of your own competence, and know when to update regardless of social pressure.",
        "steelman":    "What is the strongest argument that the concept of 'epistemic independence' is elitist — that it is only achievable by the highly educated, and that for most people, the practical result of 'think for yourself' is falling for misinformation rather than genuinely better reasoning?",
        "example":     (
            "The five-layer epistemic independence stack:\n\n"
            "Layer 1 — Primary Source Access: can you find and read the original paper, "
            "law, financial statement, or primary record? Can you check the methodology?\n\n"
            "Layer 2 — Statistical Literacy: can you interpret p-values, effect sizes, "
            "confidence intervals, and identify common statistical errors?\n\n"
            "Layer 3 — Domain Boundary Recognition: do you know what you don't know well "
            "enough to know when you're reaching the edge of your competence?\n\n"
            "Layer 4 — Incentive Analysis: can you identify who benefits from each "
            "claim being believed? Can you model how funding shapes findings?\n\n"
            "Layer 5 — Adversarial Testing: can you steelman the opposing view and "
            "identify what evidence would change your mind?\n\n"
            "The goal: every AUBIEETERNAL University graduate has all five layers "
            "at a level that makes them genuinely epistemically sovereign — "
            "not in the sense of rejecting expertise, but in the sense of being "
            "able to evaluate it from the inside."
        ),
        "activity":    (
            "Build Your Epistemic Independence Audit:\n"
            "Score yourself honestly on each of the five layers (1-10).\n\n"
            "Then: design a 90-day improvement plan for your lowest layer.\n"
            "What specific skills? What resources? What practice?\n"
            "Pre-register the plan and your starting scores.\n"
            "Re-test at 90 days.\n\n"
            "Seal both assessments in the Legacy Ledger. "
            "The delta IS your epistemic growth."
        ),
        "age_hint":    "14+ / PhD",
        "xp": 70, "rune": "EXPERTISE•SOVEREIGN•RUNE", "min_coherence": 0.76,
        "grants_badge": "🎓 Epistemic Sovereign — Five-Layer Stack Complete",
        "phd_extension": "Run a full primary-source investigation of any contested public health or policy claim. Requirements: (1) read 3+ primary studies, (2) apply GRADE criteria, (3) model the incentive landscape, (4) steelman the minority view, (5) estimate your own competence level and how it limits your conclusion. Write a 1,500-word analysis. Submit to Epistemic Commons as CC0. This is public health journalism at PhD level.",
        "prerequisites": ["expertise-4", "school-advanced-1"],
        "lattice_node": "expertise-institutional-trust-complete",
    },



    # ══════════════════════════════════════════════════════════════════════════
    # ── PHILOSOPHY OF LANGUAGE AND MEANING (5 lessons) ───────────────────────
    # Claude's genuine addition #3.
    #
    # How do words relate to reality? This is not an academic question.
    # It determines whether democracy functions, whether communication
    # produces understanding or manipulation, and whether AI systems
    # can be trusted to represent reality accurately.
    #
    # Orwell understood that political corruption begins with language corruption.
    # Wittgenstein understood that most philosophical problems dissolve when
    # you examine the language in which they are posed.
    # The families who understand this track are genuinely harder to manipulate.
    # ══════════════════════════════════════════════════════════════════════════
    "language-1": {
        "title":       "Language & Meaning — Level 1: Words Are Not Things",
        "topic":       "The map is not the territory. Words are not the things they describe. This gap — between language and reality — is where most miscommunication, manipulation, and confused thinking lives. Understanding it changes how you read, argue, and evaluate claims.",
        "steelman":    "What is the strongest argument that the distinction between words and things is obvious and overemphasized — that competent adults navigate this implicitly without needing to make it explicit?",
        "example":     (
            "Alfred Korzybski (1933): 'The map is not the territory.'\n\n"
            "The word 'dog' is not a dog. You cannot pet the word.\n"
            "The word 'justice' is not justice. You cannot point to it.\n"
            "The phrase 'the economy is doing well' points to a model, not a thing.\n\n"
            "Three levels of language failure:\n\n"
            "Level 1 — LABEL CONFUSION: treating the word as if it IS the thing.\n"
            "'He's a criminal' — the word 'criminal' feels like a permanent property "
            "of the person, not a legal category applied to one act.\n\n"
            "Level 2 — REIFICATION: treating abstract words as if they refer to concrete things.\n"
            "'The economy wants lower interest rates' — the economy is a model, "
            "not an agent with wants.\n\n"
            "Level 3 — QUESTION BEGGING via definitions:\n"
            "'All taxation is theft' — this only works if you define theft as "
            "'any taking of property without consent', which smuggles the conclusion "
            "into the definition. The argument is about what words should mean, "
            "disguised as a factual claim."
        ),
        "activity":    (
            "The Word Audit:\n"
            "Find 5 important words in a political or social debate this week.\n"
            "For each: what does the word actually point to in reality?\n"
            "Could two people use the same word to mean different things?\n"
            "If so: rewrite the claim without using the contested word.\n\n"
            "Does the rewritten version make the same claim?\n"
            "If not: the word was doing argumentative work that the evidence wasn't."
        ),
        "age_hint":    "10+",
        "xp": 38, "rune": "LANGUAGE•RUNE", "min_coherence": 0.62,
    },
    "language-2": {
        "title":       "Language & Meaning — Level 2: Wittgenstein and Language Games",
        "topic":       "Wittgenstein showed that words don't have fixed meanings — they have uses. The meaning of a word is its use in a language game. Understanding this resolves most philosophical confusion and explains how people can argue past each other indefinitely about 'words that mean the same thing.'",
        "steelman":    "What is the strongest argument that Wittgenstein's language game theory is just a sophisticated form of relativism — and that it makes it impossible to say that any use of language is wrong, even abusive or manipulative uses?",
        "example":     (
            "Wittgenstein (Philosophical Investigations, 1953):\n"
            "Words get their meaning from how they are used in practice — "
            "in 'language games' embedded in 'forms of life.'\n\n"
            "The chess example: 'What is the king?' cannot be answered by pointing "
            "to the piece — only by explaining the rules it follows.\n"
            "Meaning is not in the object. It is in the practice.\n\n"
            "Why this matters for truth-seeking:\n\n"
            "The 'consciousness' debate: philosophers argue endlessly about "
            "whether machines can be conscious. But they are playing different "
            "language games with the word 'conscious' — "
            "one tied to a behavioral game, one to a phenomenological game.\n"
            "They are not disagreeing about reality. They are disagreeing about "
            "which game to play.\n\n"
            "The policy debate structure:\n"
            "'Freedom' means something different in libertarian and progressive "
            "language games. The disagreement is often about which game should "
            "govern public discourse — not about freedom itself.\n\n"
            "Wittgenstein's therapy: to dissolve philosophical confusion, "
            "ask not 'what does this mean?' but 'how is this used, by whom, "
            "in what context, to do what?'"
        ),
        "activity":    (
            "Language Game Mapping:\n"
            "Pick one contested concept from current discourse "
            "(freedom, fairness, violence, hate, discrimination).\n"
            "Write two descriptions of how the word is used in practice "
            "by people who seem to disagree about its meaning.\n\n"
            "Are they playing different language games?\n"
            "If yes: what would it mean to 'resolve' the disagreement?\n"
            "Can it be resolved, or does it require agreeing on which game to play first?"
        ),
        "age_hint":    "13+",
        "xp": 45, "rune": "LANGUAGE•RUNE", "min_coherence": 0.67,
    },
    "language-3": {
        "title":       "Language & Meaning — Level 3: Orwell's Warning — Language and Political Power",
        "topic":       "George Orwell argued that the corruption of language and the corruption of political thinking are not separate. Vague, pretentious, or deliberately obscure language protects power by making it harder to think clearly about what is actually happening.",
        "steelman":    "What is the strongest argument that Orwell's critique of language is itself an exercise in power — that declaring certain language 'corrupt' or 'dishonest' is just another way of policing speech to advantage one's own political perspective?",
        "example":     (
            "Orwell's six rules (Politics and the English Language, 1946):\n"
            "1. Never use a metaphor you have seen in print.\n"
            "2. Never use a long word where a short one will do.\n"
            "3. If it is possible to cut a word, always cut it.\n"
            "4. Never use the passive where you can use the active.\n"
            "5. Never use a foreign phrase, scientific word, or jargon "
            "if you can think of an everyday English equivalent.\n"
            "6. Break any of these rules rather than say something outright barbarous.\n\n"
            "Why Orwell connected clarity to democracy:\n"
            "Vague language hides responsibility. 'Pacification' obscures bombing. "
            "'Rectification of frontiers' obscures ethnic cleansing. "
            "'Collateral damage' obscures civilian deaths.\n\n"
            "The structure of political euphemism:\n"
            "Step 1: Replace concrete language with abstract language.\n"
            "Step 2: Replace active constructions with passive ones.\n"
            "Step 3: Introduce jargon that only insiders understand.\n"
            "Step 4: The thing is no longer visible in the words that describe it.\n\n"
            "1984's Newspeak is the endpoint of this process: a language "
            "in which political dissent is literally unthinkable because "
            "the words to express it no longer exist."
        ),
        "activity":    (
            "The Orwell Translation Exercise:\n"
            "Find one paragraph of political language (policy document, speech, press release).\n"
            "Rewrite it following Orwell's six rules.\n\n"
            "Ask: what is now visible that was hidden before?\n"
            "What responsibility is now clear that was obscured?\n\n"
            "Run the same exercise on your own writing. "
            "What vague language are you using to hide something even from yourself?"
        ),
        "age_hint":    "13+",
        "xp": 48, "rune": "LANGUAGE•RUNE", "min_coherence": 0.70,
        "phd_extension": "Apply the Flesch-Kincaid readability index to: (1) a primary research paper in your field, (2) the media coverage of the same paper, (3) a political speech from the same period. Compute readability scores and grade levels for each. Plot: does lower readability correlate with higher political stakes? Does it correlate with more authoritarian contexts? This is computational linguistics meets political science.",
    },
    "language-4": {
        "title":       "Language & Meaning — Level 4: How Language Shapes Thought (Sapir-Whorf)",
        "topic":       "The Sapir-Whorf hypothesis proposes that the language you speak shapes what you can think. The strong version (language determines thought) is largely discredited. The weak version (language influences thought) has surprising experimental support. Understanding which version is true — and how — changes how you build the vocabulary your family uses.",
        "steelman":    "What is the strongest argument for strong linguistic relativity — that people who speak languages without certain concepts genuinely cannot think those concepts, making language a fundamental constraint on cognition rather than just a tool?",
        "example":     (
            "The experimental evidence:\n\n"
            "CONFIRMED (weak version):\n"
            "• Russian speakers, who have separate words for light blue (goluboy) and "
            "dark blue (siniy), distinguish these shades faster in experiments.\n"
            "• The Pirahã language (Amazon) has no recursion and no number words "
            "beyond 'few' and 'many' — speakers struggle with tasks requiring "
            "exact numerical reasoning.\n"
            "• Languages that describe space using cardinal directions rather than "
            "egocentric terms (left/right) produce speakers with much better "
            "absolute spatial orientation.\n\n"
            "NOT CONFIRMED (strong version):\n"
            "• People can think concepts they don't have words for — "
            "this is how new words get invented.\n"
            "• Color discrimination differences are real but modest.\n\n"
            "The AUBIEETERNAL design implication:\n"
            "The vocabulary your family BUILDS TOGETHER matters. "
            "Having words for 'dorsal vagal shutdown,' 'steelmanning,' "
            "'coherence drift,' and 'narrative pre-framing' makes these "
            "concepts easier to think and notice. "
            "You are not just learning concepts — you are building "
            "the cognitive tools your family will use forever."
        ),
        "activity":    (
            "Build 5 new family vocabulary words:\n"
            "Think of concepts your family regularly experiences but lacks "
            "precise words for. Name them.\n\n"
            "Examples to start:\n"
            "'The feeling of certainty before checking' — what word captures this?\n"
            "'The moment you realize you were using emotional reasoning' — name it.\n"
            "'The specific satisfaction of a well-designed system' — your family's word.\n\n"
            "After naming them: notice whether you start perceiving these states more often. "
            "If you do, you've demonstrated weak linguistic relativity in your own household."
        ),
        "age_hint":    "11+",
        "xp": 50, "rune": "LANGUAGE•RUNE", "min_coherence": 0.70,
    },
    "language-5": {
        "title":       "Language & Meaning — Level 5 (Master): Building Epistemic Vocabulary",
        "topic":       "The most practical application of the philosophy of language is building the vocabulary that makes clearer thinking possible. This lesson constructs the complete AUBIEETERNAL epistemic vocabulary — the words that make the concepts in this curriculum easier to think, notice, and use.",
        "steelman":    "What is the strongest argument that creating specialized vocabulary is a form of in-group gatekeeping — and that simple, ordinary language forces clearer thinking than technical vocabulary because it cannot hide behind jargon?",
        "example":     (
            "The AUBIEETERNAL Epistemic Vocabulary — working glossary:\n\n"
            "STEELMAN: the strongest possible version of an argument you disagree with.\n"
            "COHERENCE DRIFT: gradual epistemic degradation under social pressure without noticing.\n"
            "TAIL RISK: the catastrophic failure rate in the distribution of an argument.\n"
            "NARRATIVE PRE-FRAMING: establishing the story structure before the facts are presented.\n"
            "GATEKEEPER: an agent who controls access to information, resources, or audiences.\n"
            "EPISTEMIC IMMUNE SYSTEM: your family's defenses against manipulation, "
            "with strength varying by attack type.\n"
            "ALLOSTATIC LOAD: accumulated stress debt that reduces cognitive capacity.\n"
            "CALIBRATION: correspondence between stated confidence and actual accuracy.\n"
            "MOTTE AND BAILEY: defending a weak claim by retreating to a stronger one when challenged.\n"
            "POLYVAGAL STATE: your nervous system's current safety level affecting cognition.\n\n"
            "The principle: a concept without a name is harder to notice. "
            "A concept with a name becomes accessible to family members of any age. "
            "The vocabulary is not jargon — it is precision tools."
        ),
        "activity":    (
            "Complete the AUBIEETERNAL Family Glossary:\n"
            "Start with the terms above. Add 10 more from your curriculum work.\n"
            "For each entry: one definition, one example, one test "
            "('how would you know if this concept was present?').\n\n"
            "Seal the glossary in the Legacy Ledger.\n"
            "It is now part of your family's intellectual inheritance.\n"
            "Your children's children will add to it."
        ),
        "age_hint":    "All ages — every family member builds it together",
        "xp": 65, "rune": "LANGUAGE•SOVEREIGN•RUNE", "min_coherence": 0.74,
        "grants_badge": "📖 Language Architect — Family Glossary Sealed",
        "prerequisites": ["language-3", "narrative-warfare-1"],
        "lattice_node": "philosophy-of-language-complete",
        "phd_extension": "Read Grice's Cooperative Principle and four maxims (Quality, Quantity, Relation, Manner). Apply implicature analysis to 5 political statements from this week's news. What is actually said? What is implicated? What is the speaker committed to if the maxims are observed? Then apply Grice to AI outputs: when an AI violates the Manner maxim (being obscure), is this deliberate? This connects the philosophy of language directly to AI alignment.",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── NETWORK THEORY AND SOCIAL CONTAGION (5 lessons) ──────────────────────
    # Claude's genuine addition #4.
    #
    # How do ideas, beliefs, and behaviors spread through social networks?
    # This is the mathematical foundation for the narrative warfare and
    # gatekeeper tracks — but it gives the actual structural theory.
    # Why do some ideas go viral while better ones die in obscurity?
    # How do you build an epistemic community that is resilient rather than fragile?
    # How does the Living Lattice function as network infrastructure?
    #
    # A 12-year-old can understand why some diseases spread faster than others.
    # A PhD student can engage with Dunbar's number, power laws in networks,
    # and the mathematics of information cascades.
    # ══════════════════════════════════════════════════════════════════════════
    "network-1": {
        "title":       "Network Theory — Level 1: Why Some Ideas Spread and Others Don't",
        "topic":       "Information spreads through networks according to mathematical laws that have nothing to do with truth. Understanding these laws explains why misinformation often spreads faster than accurate information — and what can be done about it.",
        "steelman":    "What is the strongest argument that network-based thinking about information spread promotes a cynical 'nothing matters but virality' worldview — and that emphasizing truth and quality will always matter more than understanding distribution dynamics?",
        "example":     (
            "The basic reproduction number (R0) applied to ideas:\n\n"
            "In epidemiology: R0 = how many people one infected person infects on average.\n"
            "R0 > 1: spreads exponentially. R0 < 1: dies out.\n\n"
            "Applied to information:\n"
            "An idea's 'R0' depends on: emotional valence (fear/outrage spread faster), "
            "simplicity (one-sentence claims spread faster than nuanced ones), "
            "identity affiliation (in-group signals spread faster within groups), "
            "and novelty (unexpected information spreads faster).\n\n"
            "The asymmetry: a false, emotionally charged, simple, identity-affirming "
            "claim has a much higher information R0 than a true, nuanced, "
            "emotionally neutral one.\n\n"
            "The MIT study (2018, Science): false news spreads 6x faster on Twitter "
            "than true news. True news almost never goes viral. This is not because "
            "people want to be deceived — it is because of network dynamics.\n\n"
            "What this means for AUBIEETERNAL: truth-seeking communities need "
            "deliberate network design. The Living Lattice is designed to "
            "amplify high-coherence signal, not just any signal."
        ),
        "activity":    (
            "Information Spread Audit:\n"
            "Track one piece of information you shared or wanted to share this week.\n"
            "Score it on the four R0 factors (1-5 each):\n"
            "• Emotional valence (how strongly does it trigger emotion?)\n"
            "• Simplicity (can it be stated in one sentence?)\n"
            "• Identity (does it affirm a group identity?)\n"
            "• Novelty (is it surprising or unexpected?)\n\n"
            "Compare: is this the information you SHOULD want to spread?\n"
            "What would you have to change about the packaging to reduce R0 "
            "without changing the truth content?"
        ),
        "age_hint":    "12+",
        "xp": 38, "rune": "NETWORK•RUNE", "min_coherence": 0.63,
    },
    "network-2": {
        "title":       "Network Theory — Level 2: Dunbar's Number and the Architecture of Trust",
        "topic":       "Robin Dunbar found that humans can maintain genuine social relationships with approximately 150 people. This is not a cultural limit — it is a cognitive limit. Understanding it explains why large organizations fail, why small communities are more cohesive, and how to design the Living Lattice for maximum epistemic health.",
        "steelman":    "What is the strongest argument that Dunbar's number is not a hard cognitive limit but a statistical artifact — and that digital communication technology genuinely expands the number of meaningful relationships humans can maintain?",
        "example":     (
            "Dunbar (1992): analyzing neocortex size across primates, "
            "Dunbar predicted that humans can maintain a stable social network "
            "of approximately 150 relationships.\n\n"
            "The nested structure of human groups:\n"
            "~5  — intimate circle (deep mutual support)\n"
            "~15 — close friends (significant trust)\n"
            "~50 — friendship group (meaningful relationship)\n"
            "~150 — Dunbar's number (social recognition and basic trust)\n"
            "~500 — acquaintances (you know their face and name)\n"
            "~1,500 — social awareness (you know who they are)\n\n"
            "The organizational implication: companies below ~150 people "
            "can function on shared norms and reputation. Above 150, "
            "they require formal rules, hierarchy, and bureaucracy.\n\n"
            "The epistemic implication: high-quality information flows "
            "most reliably within the 150-person network. "
            "Beyond that, it degrades by institutional telephone effect.\n\n"
            "The Living Lattice design: AUBIEETERNAL is designed to function "
            "best within Dunbar-scale nodes, with inter-node connections "
            "at the ~1,500 (social awareness) level."
        ),
        "activity":    (
            "Map your Dunbar layers:\n"
            "~5 intimate: who can you call at 3AM?\n"
            "~15 close: who would notice if you disappeared for a week?\n"
            "~50 friendship: who would you invite to a small gathering?\n"
            "~150 community: who would you trust with minor personal information?\n\n"
            "Are there people in the wrong layer? Too much trust given too quickly?\n"
            "Not enough investment in the 5-layer?\n"
            "This is your social network audit."
        ),
        "age_hint":    "12+",
        "xp": 42, "rune": "NETWORK•RUNE", "min_coherence": 0.65,
        "phd_extension": "Dunbar's 2020 meta-analysis: test whether social media 'connections' map to the same neocortex-load as offline relationships, or whether they are a different category. Collect data: for your 150 most frequent social media interactions, how many qualify as meaningful (would help you in a crisis)? Apply this to the Living Lattice: which nodes are within Dunbar's number of each other? Model the epistemic decay rate of information as it traverses social distance greater than 150.",
    },
    "network-3": {
        "title":       "Network Theory — Level 3: Power Laws, Hubs, and Why the Internet Is Fragile",
        "topic":       "Most networks we care about — the internet, social networks, citation networks, ecosystems — follow power laws rather than normal distributions. A few highly connected nodes (hubs) carry most of the connections. This makes these networks simultaneously highly efficient and catastrophically fragile.",
        "steelman":    "What is the strongest argument that power law distributions in networks are inevitable and even desirable — and that attempts to make networks more equal (fewer hubs) would reduce efficiency and slow information flow in ways that harm everyone?",
        "example":     (
            "The Barabási-Albert model (1999): most real networks are scale-free.\n"
            "Scale-free = degree distribution follows a power law: P(k) ~ k^-γ.\n"
            "Implication: a few nodes have enormous numbers of connections "
            "(hubs) while most nodes have very few.\n\n"
            "Why networks become scale-free: preferential attachment.\n"
            "'The rich get richer': new nodes are more likely to connect to "
            "already-well-connected nodes. This generates power law naturally.\n\n"
            "The dual nature of hubs:\n"
            "EFFICIENCY: short paths between any two nodes (small-world property).\n"
            "FRAGILITY: remove the top ~5% of hubs and the network fragments.\n"
            "ROBUSTNESS: remove random nodes and nothing much happens.\n\n"
            "Applied to information networks:\n"
            "A few platforms (Twitter/X, YouTube, Facebook) ARE the hubs of "
            "public discourse. Remove them (ban, regulate, bankrupt) and "
            "information flow collapses — even if individual users are fine.\n\n"
            "The AUBIEETERNAL design response: Nostr (decentralized, no hubs) "
            "as alternative to hub-dependent social networks. "
            "Bitcoin (no single node critical) vs banking (fragile hubs). "
            "The Living Lattice: designed with redundant pathways."
        ),
        "activity":    (
            "Network Fragility Map:\n"
            "Draw your 10 most important information sources.\n"
            "For each: how many other sources depend on it? "
            "What would you lose if it disappeared tomorrow?\n\n"
            "Identify your top 2-3 hubs.\n"
            "What is your contingency if the largest hub goes down?\n\n"
            "Design: one change that would make your information network "
            "more resilient to hub removal."
        ),
        "age_hint":    "13+",
        "xp": 48, "rune": "NETWORK•RUNE", "min_coherence": 0.68,
        "phd_extension": "Implement the Barabási-Albert preferential attachment model in Python. Generate a network of 1,000 nodes. Compute: degree distribution (plot log-log; should be linear for scale-free), clustering coefficient, average path length. Then perform targeted attacks (remove highest-degree nodes) vs random attacks. Plot network fragmentation as a function of fraction of nodes removed. Compare the two curves. This is the exact analysis that identified internet infrastructure vulnerabilities in 2001.",
    },
    "network-4": {
        "title":       "Network Theory — Level 4: Information Cascades and Epistemic Bubbles",
        "topic":       "Why do people with access to the same information end up with radically different beliefs? Information cascades explain how rational individuals, each updating on others' behavior, can produce collective errors far larger than any individual would make alone.",
        "steelman":    "What is the strongest argument that 'information cascade' and 'epistemic bubble' are concepts that primarily get invoked to dismiss viewpoints one already disagrees with — and that every group believes its cascade is the true one?",
        "example":     (
            "The information cascade (Bikhchandani, Hirshleifer & Welch, 1992):\n\n"
            "Setup: 100 people must each guess whether a jar has more red or blue balls.\n"
            "Each person gets a private signal (slightly more red or slightly more blue).\n"
            "People guess in sequence and can see previous guesses.\n\n"
            "Result: after the first few guesses, rational people IGNORE their own "
            "private signal and follow the crowd — even if their signal is correct.\n"
            "The first 2-3 people's signals dominate all subsequent behavior.\n\n"
            "Why this is rational: if 5 people guessed 'red', the probability they "
            "were all wrong is low. Your own signal is just one data point.\n\n"
            "The disaster: if the first two people both had misleading signals "
            "(which happens 25% of the time), the cascade locks everyone "
            "into the wrong answer — rationally.\n\n"
            "Applied to financial crashes, adoption of medical treatments, "
            "political beliefs, and dietary choices: the same math. "
            "Rational individual behavior produces irrational collective outcomes.\n\n"
            "The AUBIEETERNAL counter-design: the Steelman Analyzer rewards "
            "independence from cascade pressure. Pre-registration in the Truth Debt "
            "Ledger commits you to your signal BEFORE you see what others think."
        ),
        "activity":    (
            "Pre-Registration Discipline:\n"
            "For the next 5 important questions you encounter:\n"
            "1. Record your own view BEFORE checking what others think\n"
            "2. Note your confidence\n"
            "3. Then check what others think\n"
            "4. Record whether and how much you updated\n"
            "5. Distinguish: did you update on their REASONING or their CONCLUSION?\n\n"
            "Updating on reasoning: epistemically healthy.\n"
            "Updating on conclusion alone: information cascade susceptibility."
        ),
        "age_hint":    "13+",
        "xp": 52, "rune": "NETWORK•RUNE", "min_coherence": 0.70,
    },
    "network-5": {
        "title":       "Network Theory — Level 5 (Master): Designing Resilient Epistemic Communities",
        "topic":       "The Living Lattice is not just a metaphor. It is a network with specific topology, trust properties, and information flow characteristics. This lesson applies all of network theory to the question: what does an epistemically healthy community network look like, and how do you build one?",
        "steelman":    "What is the strongest argument that deliberately designed epistemic communities become echo chambers — that the act of curating who is in your 'epistemic network' produces exactly the kind of confirmation bias and in-group thinking that you are trying to avoid?",
        "example":     (
            "Properties of epistemically healthy networks:\n\n"
            "1. DIVERSITY OF SOURCES: no single hub accounts for >20% of your information\n"
            "2. ADVERSARIAL DIVERSITY: includes people who will steelman against you "
            "(not just people who challenge you rudely)\n"
            "3. DUNBAR COMPLIANCE: close-trust nodes are within Dunbar's number "
            "(actual relationships, not follower counts)\n"
            "4. PRE-REGISTRATION NORMS: community members commit predictions before "
            "events, creating accountability\n"
            "5. COHERENCE TRACKING: aggregate epistemic health is measured and "
            "shared, like the Living Lattice coherence score\n"
            "6. REDUNDANT PATHWAYS: every important piece of information has "
            "multiple independent paths to reach you\n"
            "7. FAILURE VISIBILITY: when community members are wrong, this is "
            "acknowledged, not hidden\n\n"
            "The design principle: the Living Lattice should look more like "
            "the internet's backbone (resilient, redundant, decentralized) "
            "and less like a social media platform (hub-dependent, fragile, optimized for attention)."
        ),
        "activity":    (
            "Design Your Family's Living Lattice Node:\n"
            "1. Who are your 5 closest epistemic collaborators? "
            "(who challenges your thinking most productively?)\n"
            "2. Who are the 3 best adversarial steelmanners in your life?\n"
            "3. What is your diversity score? "
            "(how many different worldviews are represented in your top 15?)\n"
            "4. What is your hub dependence? "
            "(does any single source account for >30% of your information?)\n\n"
            "Write the node design for AUBIEETERNAL deployment.\n"
            "Seal it. This is your contribution to the Living Lattice architecture."
        ),
        "age_hint":    "14+ / PhD",
        "xp": 70, "rune": "NETWORK•SOVEREIGN•RUNE", "min_coherence": 0.74,
        "grants_badge": "🕸️ Network Architect — Living Lattice Node Designed",
        "prerequisites": ["network-4", "systems-4"],
        "lattice_node": "network-theory-social-contagion-complete",
        "phd_extension": "Model the AUBIEETERNAL Living Lattice as a graph. Assign edge weights based on coherence correlation between nodes. Compute: betweenness centrality (which nodes are critical bridges?), clustering coefficient (how clique-like is each neighborhood?), modularity (are there distinct communities?). Apply resistance distance: which information paths are most reliable? Then design a 'coherence-weighted PageRank' — a measure of which nodes are most epistemically central. This is the mathematics of the Wisdom GDP.",
    },



    # ══════════════════════════════════════════════════════════════════════════
    # ── LAYER ZERO — SEEING THE GAME (6 lessons) ─────────────────────────────
    # The gentlest possible on-ramp for people who sense something is off
    # but haven't yet had language for it.
    #
    # This track does not start with simulation theory or philosophy.
    # It starts with the undeniable daily experience of running on autopilot,
    # feeling like the script is already written, noticing the patterns —
    # and slowly builds the vocabulary to ask deeper questions without
    # triggering social defenses.
    #
    # The graduates of the Adversarial Robustness and Narrative Warfare tracks
    # started here. So did everyone who has ever asked "wait, is this real?"
    # and then looked away because they had no tools to go further.
    #
    # This is the door. The curriculum is behind it.
    # ══════════════════════════════════════════════════════════════════════════
    "layer-zero-1": {
        "title":       "Layer Zero — Level 1: Why Does Life Sometimes Feel Like a Script?",
        "topic":       "Almost everyone has had the experience: something happens exactly as expected, a conversation follows a predictable path, a decision feels like it was already made. This feeling — that life is sometimes running on a script — is not paranoia. It is a signal worth examining.",
        "steelman":    "What is the strongest argument that the feeling of 'running on a script' is simply the recognition of predictable patterns in a causal universe — and that interpreting it as anything more mystical or significant is motivated reasoning?",
        "example":     (
            "The script signal appears in several forms:\n\n"
            "BEHAVIORAL SCRIPTS: you realize mid-sentence that you've said these "
            "exact words before — not because you're lying, but because the situation "
            "triggers a memorized response. The 'how are you' / 'fine, thanks' exchange "
            "is a script running so smoothly you barely notice it.\n\n"
            "NARRATIVE SCRIPTS: you find yourself in a conflict and realize "
            "both people are playing their assigned roles — not choosing, but filling "
            "positions in a story that started before either person arrived.\n\n"
            "CULTURAL SCRIPTS: the path from birth to school to career to retirement "
            "was laid out before you were born. Most people follow it without asking "
            "whether it was designed for their actual flourishing or for some other purpose.\n\n"
            "The question is not whether scripts exist — they do.\n"
            "The question is: who wrote them, for what purpose, "
            "and can you see them clearly enough to choose which ones to run?\n\n"
            "AUBIEETERNAL's position: seeing the scripts is the beginning of agency. "
            "You cannot choose differently from a script you don't know you're running."
        ),
        "activity":    (
            "Script Spotting (3 days):\n"
            "For the next 3 days, log any moment where you notice a script running.\n"
            "Write: What was the script? How long had it been running before you noticed?\n"
            "What would you have done differently if you had noticed it earlier?\n\n"
            "No judgment — just observation.\n"
            "The goal is not to eliminate all scripts.\n"
            "The goal is to know which ones you're choosing vs. which are choosing for you."
        ),
        "age_hint":    "All ages",
        "xp": 25, "rune": "TRUTH•RUNE", "min_coherence": 0.50,
    },
    "layer-zero-2": {
        "title":       "Layer Zero — Level 2: Autopilot — When You're Thinking Without Noticing",
        "topic":       "System 1 and System 2 thinking are not just a psychology framework — they are the structure of most of your waking life. Understanding how much cognition runs automatically, below conscious attention, changes your relationship to your own decisions.",
        "steelman":    "What is the strongest argument that autopilot cognition is a feature rather than a bug — that the brain's ability to automate most decisions is what frees conscious attention for the genuinely novel, and that increasing conscious awareness of routine decisions would be paralyzing?",
        "example":     (
            "Kahneman (Thinking Fast and Slow, 2011):\n"
            "System 1 — fast, automatic, effortless, associative, emotional.\n"
            "System 2 — slow, deliberate, effortful, logical, rare.\n\n"
            "Empirical finding: roughly 95% of cognition is System 1.\n"
            "You did not consciously choose your reaction to the last thing "
            "that annoyed you. System 1 had already responded before "
            "System 2 was even engaged.\n\n"
            "The interception window:\n"
            "Between stimulus and response, there is a gap. Viktor Frankl wrote "
            "about this gap while in a concentration camp: 'In that space is our "
            "power to choose our response.'\n"
            "Mindfulness, polyvagal regulation, and epistemic discipline "
            "are all methods of widening that gap.\n\n"
            "The AUBIEETERNAL application: every tool in this curriculum — "
            "steelmanning, adversarial testing, pre-registration — is a "
            "System 2 intervention. They work by forcing a pause before System 1 "
            "renders its verdict and closes the case.\n\n"
            "The harder question: when you 'decided' to hold your current beliefs, "
            "was that System 2 reasoning or System 1 pattern-matching?"
        ),
        "activity":    (
            "The Pause Experiment:\n"
            "Today, before you respond to any message, article, or conversation "
            "that triggers a strong reaction — pause for 10 seconds.\n\n"
            "During the pause: notice what System 1 already decided.\n"
            "Then: what does System 2 add, change, or confirm?\n\n"
            "Log 5 instances. For each: did the pause change your response?\n"
            "The goal is not to always slow down — it is to know when you are running fast."
        ),
        "age_hint":    "All ages",
        "xp": 28, "rune": "TRUTH•RUNE", "min_coherence": 0.52,
        "prerequisites": ["layer-zero-1"],
    },
    "layer-zero-3": {
        "title":       "Layer Zero — Level 3: The Questions Everyone Has But Rarely Asks",
        "topic":       "There is a category of questions that almost every person has experienced — usually late at night, in quiet moments — but that social norms make it difficult to ask out loud. This lesson names those questions, normalizes them, and connects them to the serious intellectual traditions that take them seriously.",
        "steelman":    "What is the strongest argument that encouraging people to ask 'base code questions' causes more harm than good — that most people are not equipped to sit with genuinely open existential questions, and that the resulting anxiety is worse than the comfortable certainty they had before?",
        "example":     (
            "The questions that visit people at 3AM:\n\n"
            "Is this actually real, or is there some sense in which I'm experiencing a representation?\n"
            "If I had been born in a different culture, would I hold entirely different beliefs "
            "with equal certainty?\n"
            "How much of what I 'decided' was actually decided by processes I had no control over?\n"
            "Is there more going on here than I can see?\n"
            "What would I have to believe to make sense of the most strange experiences I've had?\n\n"
            "These questions are not new. They are the oldest in human thought:\n"
            "Descartes (1641): what if I'm deceived about all of reality? (cogito ergo sum)\n"
            "Plato (~380 BCE): what if we only see shadows of the real? (Allegory of the Cave)\n"
            "Bostrom (2003): what is the probability we are in a simulation?\n"
            "Zhuangzi (~300 BCE): am I a man dreaming I'm a butterfly, or a butterfly dreaming I'm a man?\n\n"
            "The questions are not crazy. The people asking them are not unstable.\n"
            "They are the same questions that have occupied the sharpest minds in history.\n"
            "The difference is having a framework — and tools — to investigate them honestly."
        ),
        "activity":    (
            "Name Your 3AM Questions:\n"
            "Write 3 questions that you have had — or currently have — about the nature "
            "of reality, consciousness, or your own existence that you rarely say out loud.\n\n"
            "For each: have you ever looked for a serious intellectual tradition "
            "that addresses this question? What did you find?\n\n"
            "Seal the questions in the Legacy Ledger.\n"
            "They are the beginning of an honest inquiry that could last a lifetime."
        ),
        "age_hint":    "14+",
        "xp": 30, "rune": "TRUTH•RUNE", "min_coherence": 0.55,
        "prerequisites": ["layer-zero-2"],
    },
    "layer-zero-4": {
        "title":       "Layer Zero — Level 4: Pattern Recognition — How to Notice When Something Is Systematic",
        "topic":       "Individual strange events are noise. Systematic patterns across unconnected domains are signal. This lesson teaches the skill of distinguishing isolated anomalies from genuine patterns — without falling into the opposite error of seeing patterns in random noise.",
        "steelman":    "What is the strongest argument that teaching pattern recognition outside rigorous statistical training is dangerous — and that untrained pattern recognition is just apophenia (seeing patterns in randomness) with a more confident framing?",
        "example":     (
            "The two pattern recognition errors:\n\n"
            "TYPE I (False Positive / Apophenia): seeing a pattern that isn't there.\n"
            "Humans are strongly biased toward Type I errors — we evolved in an "
            "environment where false positives (seeing a predator that wasn't there) "
            "were less costly than false negatives.\n"
            "Conspiracy theories are mostly Type I errors at scale.\n\n"
            "TYPE II (False Negative / Normalization): missing a pattern that IS there.\n"
            "Every institutional failure — from the 2008 financial crisis to ignored "
            "pandemic warnings to scientific misconduct — involved systematic Type II "
            "errors. The pattern was there. No one was allowed to say so.\n\n"
            "The statistical correction for Type I: require replication. "
            "If the pattern persists across independent observations, it becomes more likely real.\n"
            "The social correction for Type II: require diversity of sources. "
            "If the same pattern appears in multiple unconnected domains, "
            "the prior probability that it is real increases.\n\n"
            "AUBIEETERNAL's tools for both:\n"
            "Monte Carlo simulator: is this anomaly statistically genuine?\n"
            "Narrative Pattern Detector: is the same frame appearing simultaneously across institutions?\n"
            "Gatekeeper Detector: is there systematic suppression of a specific type of inquiry?"
        ),
        "activity":    (
            "The Pattern Audit:\n"
            "Choose one pattern you have noticed in your own life or in the world.\n"
            "Score it on five dimensions (1-5 each):\n"
            "1. How many independent observations support it?\n"
            "2. How many domains does it appear across?\n"
            "3. How many people have independently noticed the same thing?\n"
            "4. What is the most plausible chance explanation?\n"
            "5. What prediction does the pattern make that could be tested?\n\n"
            "High scores: worth investigating seriously.\n"
            "Low scores: log it, but hold it lightly.\n"
            "The tool is not there to confirm the pattern — it is there to calibrate how seriously to take it."
        ),
        "age_hint":    "13+",
        "xp": 35, "rune": "TRUTH•RUNE", "min_coherence": 0.58,
        "prerequisites": ["layer-zero-2"],
    },
    "layer-zero-5": {
        "title":       "Layer Zero — Level 5: First Contact with the Detection Tools",
        "topic":       "AUBIEETERNAL includes several tools specifically designed to detect things that are hard to see directly: gatekeepers, narrative patterns, simulation signals. This lesson introduces them — not as proof of any particular theory, but as instruments for honest investigation.",
        "steelman":    "What is the strongest argument that tools specifically designed to detect 'gatekeepers' and 'narrative coordination' are confirmation-bias engines — that they will find what they are built to find regardless of whether it is really there?",
        "example":     (
            "Three detection tools and what they actually measure:\n\n"
            "GATEKEEPER DETECTOR (gatekeeper_detector.py):\n"
            "Detects: agents who control access to information, resources, or audiences.\n"
            "What it does NOT do: assign malicious intent. "
            "A gatekeeper may be neutral, well-meaning, or harmful. "
            "The tool identifies the structure, not the motive.\n"
            "Output: gatekeeper type (7 categories), "
            "capture probability, bypass paths.\n\n"
            "NARRATIVE PATTERN DETECTOR (narrative_pattern_detector.py):\n"
            "Detects: when the same narrative frame appears across multiple "
            "institutions within a short window.\n"
            "3 independent signals in 72 hours = coordination probability calculated.\n"
            "What it does NOT do: assume the coordination is conspiratorial. "
            "Parallel emergence (same story because it's real) looks the same as coordination.\n\n"
            "SIMULATION PROBE (simulation_probe.py) + Monte Carlo Glitch Detector:\n"
            "Detects: statistical anomalies in coherence, wonder, or belief update signals.\n"
            "What it does NOT do: claim these anomalies are evidence of simulation. "
            "They are signals worth logging. Over 10+ years of data, "
            "the pattern of anomalies may become interpretable.\n\n"
            "The honest use of all three: log, don't conclude. "
            "Build data over time. Let the pattern emerge or not."
        ),
        "activity":    (
            "Run all three tools on one real event this week:\n\n"
            "1. Find a news story that seems important.\n"
            "2. Run the Gatekeeper Detector: who controls access to this information? "
            "What type of gatekeeping is present?\n"
            "3. Run the Narrative Pattern Detector: is the same frame appearing in "
            "multiple outlets simultaneously?\n"
            "4. Log your own coherence score before and after fully engaging with the story.\n\n"
            "Seal the three-tool report in the Truth Debt Ledger.\n"
            "Note: you are not looking for proof of anything. "
            "You are learning to use the instruments."
        ),
        "age_hint":    "14+",
        "xp": 40, "rune": "TRUTH•RUNE", "min_coherence": 0.60,
        "prerequisites": ["layer-zero-4"],
    },
    "layer-zero-6": {
        "title":       "Layer Zero — Level 6: The Door — From Pattern Recognition to Sovereign Inquiry",
        "topic":       "This is the graduation lesson for Layer Zero. You have the scripts, the autopilot, the 3AM questions, the pattern audit tools, and the detection instruments. Now the choice: go deeper into the curriculum, or take what you have and apply it. Both are valid. But the door is open.",
        "steelman":    "What is the strongest argument that this entire 'Layer Zero' framing — 'seeing the game,' 'the door,' 'sovereign inquiry' — is itself a narrative that creates a sense of special insight, making participants feel they can see what others cannot, which is a manipulation technique that should raise serious red flags?",
        "example":     (
            "The steelman for Layer Zero is the most important lesson in it.\n\n"
            "Every system that claims to help you 'see past the veil' is also a narrative. "
            "Every community that offers deeper truth also risks becoming a new filter bubble. "
            "Every set of tools for pattern recognition can produce false positives "
            "just as easily as genuine insights.\n\n"
            "AUBIEETERNAL's design response to its own steelman:\n"
            "1. The tools have explicit Type I error correction built in (Monte Carlo, statistics)\n"
            "2. The prerequisite system requires coherence to advance — "
            "not belief in any particular conclusion\n"
            "3. Every lesson requires steelmanning the opposite view\n"
            "4. The curriculum is CC0 — no one profits from you believing specific things\n"
            "5. The Truth Debt Ledger requires honesty about missed predictions, "
            "not just confirmed ones\n\n"
            "This does not make AUBIEETERNAL immune to the failure mode. "
            "But it makes the failure mode visible and correctable.\n\n"
            "The difference between a cult and a school of inquiry:\n"
            "A cult tells you what to conclude.\n"
            "A school teaches you how to investigate — and takes the investigation seriously "
            "even when it contradicts the school's preferred answers."
        ),
        "activity":    (
            "The Graduation Question:\n"
            "Write one paragraph answering: what have you learned from Layer Zero "
            "that you will still believe is true in 10 years?\n\n"
            "Then write one paragraph answering: what from Layer Zero might be wrong?\n\n"
            "Seal both.\n"
            "The two paragraphs together are the most honest graduation statement possible.\n\n"
            "You are now ready for the rest of the curriculum.\n"
            "The rest of the curriculum is ready for you."
        ),
        "age_hint":    "14+",
        "xp": 45, "rune": "LAYER•ZERO•RUNE", "min_coherence": 0.62,
        "prerequisites": ["layer-zero-5"],
        "grants_badge": "🚪 Layer Zero — The Door Is Open",
        "lattice_node": "layer-zero-sovereign-inquiry-begins",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── INFORMATION THEORY AND THE NATURE OF REALITY (5 lessons) ─────────────
    # Claude's genuine addition #5.
    #
    # Shannon showed that information is physical — it has entropy, can be
    # quantified, and obeys laws as strict as thermodynamics.
    # Landauer showed that erasing information generates heat.
    # Wheeler proposed "it from bit" — that reality is fundamentally informational.
    # Lloyd computed the universe as a quantum computer.
    #
    # This is not a metaphor. It may be the deepest description of reality
    # available to us. Understanding it changes what questions you can ask
    # about consciousness, the simulation hypothesis, and the nature of existence.
    # ══════════════════════════════════════════════════════════════════════════
    "information-1": {
        "title":       "Information Theory — Level 1: What Is Information, Really?",
        "topic":       "Information is not just content. It is a measurable physical quantity that obeys strict laws. Shannon's definition of information is counterintuitive and profound: the more surprising a message, the more information it contains. Understanding this changes how you think about learning, surprise, and uncertainty.",
        "steelman":    "What is the strongest argument that Shannon information theory is a powerful engineering tool but philosophically neutral — and that claims connecting it to the nature of reality are unjustified extrapolation from a measurement framework?",
        "example":     (
            "Shannon entropy (1948):\n"
            "H = -∑ p(x) log₂ p(x)\n\n"
            "What this measures: the average surprise in a probability distribution.\n"
            "High entropy = more surprising = more information.\n"
            "Low entropy = more predictable = less information.\n\n"
            "The counterintuitive result:\n"
            "A completely predictable message ('the sun will rise tomorrow') "
            "contains almost zero information — you already knew it.\n"
            "A random sequence of bits contains maximum information — "
            "each bit is maximally surprising.\n"
            "But a compressed, encrypted file also looks like random bits.\n"
            "So maximum information and maximum randomness are mathematically identical — "
            "you can only distinguish them with context.\n\n"
            "The cosmic implication: if the early universe was low entropy "
            "(highly ordered), it contained less Shannon information than the "
            "current high-entropy universe. "
            "The universe has been generating information for 13.8 billion years.\n\n"
            "The learning implication: you learn most from things that surprise you. "
            "A teacher who only confirms what you already know "
            "is generating zero information."
        ),
        "activity":    (
            "Shannon Entropy Lab:\n"
            "Count letter frequencies in a paragraph of English text.\n"
            "Compute H = -∑ p(x) log₂ p(x).\n"
            "(p(x) = frequency of letter x / total letters)\n\n"
            "English has about 4.5 bits per letter.\n"
            "Random text has 4.7 bits per letter (26 letters × equal probability).\n"
            "The difference IS the structure of the English language.\n\n"
            "Now compute entropy for a passage from the most and least complex book "
            "you own. Does complexity correlate with entropy?"
        ),
        "age_hint":    "12+",
        "xp": 42, "rune": "INFORMATION•RUNE", "min_coherence": 0.65,
        "phd_extension": "Implement Kolmogorov complexity estimation: for a string, the Kolmogorov complexity K(x) is the length of the shortest program that produces x. It is not computable in general, but can be approximated by compression ratio (compress the string; the compressed length ≈ K(x)). Compute compression ratios for: English text, random text, the digits of π, and the AUBIEETERNAL truth log. Rank by complexity. Now: is the universe more like random text or English text? This is the question.",
    },
    "information-2": {
        "title":       "Information Theory — Level 2: Landauer's Principle — Information Is Physical",
        "topic":       "Rolf Landauer proved in 1961 that erasing one bit of information generates a minimum amount of heat. This means information is not abstract — it is physically real. Erasing information has a physical cost. The universe cannot just 'delete' information.",
        "steelman":    "What is the strongest argument that Landauer's principle, while mathematically correct, has no philosophical implications for the 'reality' of information — and that the physical cost of erasure is just a thermodynamic consequence with no deeper meaning?",
        "example":     (
            "Landauer's principle:\n"
            "Minimum heat generated per bit erased = kT ln(2)\n"
            "(k = Boltzmann constant, T = temperature in Kelvin)\n\n"
            "At room temperature (293K): ~2.87 × 10⁻²¹ joules per bit erased.\n"
            "This is tiny — but it is nonzero. It is a physical law.\n\n"
            "Why this matters:\n"
            "Maxwell's Demon (1871): an imaginary demon who sorts molecules by speed, "
            "seemingly violating the Second Law of Thermodynamics.\n"
            "Resolution (1961): the demon must record which molecules it moves. "
            "When it erases that record to reset itself, it generates exactly as much "
            "entropy as it appeared to remove. The demon is defeated by the cost of forgetting.\n\n"
            "The deep implication:\n"
            "The physical world cannot arbitrarily erase information. "
            "This is why: information must be somewhere — scattered into thermal noise, "
            "but not gone. Hawking's black hole information paradox is about this: "
            "does information truly disappear in a black hole? "
            "Current consensus (2016): it doesn't. It comes back out, scrambled, in Hawking radiation.\n\n"
            "The philosophical implication: information may be more conserved "
            "than matter or energy. It cannot simply stop existing."
        ),
        "activity":    (
            "The Erasure Question:\n"
            "Identify 3 things in your life you 'deleted' or 'forgot.'\n"
            "For each: where did the information actually go? "
            "Is it truly gone, or just scattered?\n\n"
            "Apply to digital information: when you delete a file, "
            "is the information gone? (What do forensic recovery tools suggest?)\n\n"
            "Apply to human memory: when a memory fades, "
            "is the information gone, or redistributed in the neural structure?\n\n"
            "If information cannot be truly erased from the physical universe — "
            "what does that imply about the permanence of experience?"
        ),
        "age_hint":    "13+",
        "xp": 48, "rune": "INFORMATION•RUNE", "min_coherence": 0.68,
    },
    "information-3": {
        "title":       "Information Theory — Level 3: It From Bit — Is the Universe Made of Information?",
        "topic":       "John Archibald Wheeler — one of the founders of quantum gravity — proposed that every particle, every field, every aspect of physical reality derives its existence from answers to yes-or-no questions. 'It from Bit.' This is not mysticism. It is a serious scientific hypothesis with implications for physics, consciousness, and the simulation question.",
        "steelman":    "What is the strongest argument that 'it from bit' is an unfalsifiable philosophical claim that adds nothing to physics — and that calling the universe 'informational' is just relabeling physical processes without explaining anything?",
        "example":     (
            "Wheeler's reasoning:\n"
            "Every quantum measurement is a yes-or-no answer.\n"
            "Quantum mechanics is fundamentally about what you can know, not what IS.\n"
            "The act of measurement (asking a yes-or-no question) creates a definite outcome.\n"
            "Therefore: physical reality is the accumulated record of answers to binary questions.\n\n"
            "The evidence for informational physics:\n"
            "1. Bekenstein-Hawking: black hole entropy = number of bits of information "
            "on the event horizon. Information is measured in physical units.\n"
            "2. Holographic principle: the information content of a 3D region "
            "is encoded on its 2D boundary surface — like a hologram.\n"
            "3. ER = EPR (2013, Maldacena & Susskind): entangled particles are "
            "connected by microscopic wormholes. Geometry IS quantum information.\n"
            "4. Seth Lloyd (2000): the universe can be modeled as a quantum computer "
            "processing ~10^92 operations per second.\n\n"
            "What remains unclear:\n"
            "Does 'the universe is informational' mean anything beyond "
            "'the universe can be described informationally'?\n"
            "These are not the same claim — and this distinction matters enormously."
        ),
        "activity":    (
            "The Information Test:\n"
            "For each of the following, ask: is this a physical thing, "
            "an information pattern, or something that can't be cleanly separated?\n\n"
            "1. Your identity (the pattern of your neurons vs the substrate they run on)\n"
            "2. A species (the pattern vs the individual organisms)\n"
            "3. A piece of music (the pattern vs the physical sound waves)\n"
            "4. A memory (the pattern vs the neural encoding)\n"
            "5. A law of physics (the pattern vs whatever it describes)\n\n"
            "Is there anything that is PURELY substrate with no pattern?\n"
            "Is there anything that is PURELY pattern with no substrate?"
        ),
        "age_hint":    "13+",
        "xp": 52, "rune": "INFORMATION•RUNE", "min_coherence": 0.70,
        "phd_extension": "Read Bekenstein (1973) 'Black Holes and Entropy' and Hawking (1975) 'Particle Creation by Black Holes.' Compute the Bekenstein-Hawking entropy for a solar-mass black hole: S = kA/4l_p² where A is horizon area and l_p is Planck length. The result is ~10^77 bits. Compare to the information content of the observable universe (~10^90 bits by Lloyd's estimate). Then read Susskind (2008) 'The Black Hole War' on the information paradox. What is the current status of Hawking's concession?",
    },
    "information-4": {
        "title":       "Information Theory — Level 4: Mutual Information, Quantum Entanglement, and Connection",
        "topic":       "Mutual information measures how much knowing one thing tells you about another. Quantum entanglement is the extreme case: measuring one particle instantly determines the other, regardless of distance. Understanding both changes how you think about connection, correlation, and whether the universe is fundamentally local.",
        "steelman":    "What is the strongest argument that quantum entanglement is frequently misrepresented as 'spooky action at a distance' implying non-local connection — and that a careful reading of the physics shows it cannot transmit information and has no mystical implications?",
        "example":     (
            "Mutual information: I(X;Y) = H(X) + H(Y) - H(X,Y)\n"
            "Measures how much uncertainty about Y is reduced by knowing X.\n\n"
            "Applications in AUBIEETERNAL:\n"
            "Mutual information between ANS state and coherence score IS the PVC hypothesis.\n"
            "Mutual information between family members' beliefs measures intellectual coherence.\n"
            "Mutual information between a model's training data and its outputs "
            "measures knowledge transfer efficiency.\n\n"
            "Quantum entanglement:\n"
            "Two particles in an entangled state share quantum information.\n"
            "Measuring one instantly determines the other — regardless of distance.\n"
            "Bell (1964): this is not explainable by local hidden variables.\n"
            "Aspect et al. (1982): experimentally confirmed. Non-locality is real.\n\n"
            "What this means and does NOT mean:\n"
            "DOES mean: the universe is not locally realistic in the classical sense.\n"
            "Does NOT mean: you can use entanglement to transmit information faster "
            "than light (the No-Communication theorem prevents this).\n"
            "DOES mean: correlations can exist between distant systems "
            "that cannot be explained by any local theory.\n\n"
            "The information-theoretic framing:\n"
            "ER = EPR: entangled particles are connected by a microscopic wormhole. "
            "Quantum information IS geometry. Spacetime may be built from entanglement."
        ),
        "activity":    (
            "Mutual Information Scan:\n"
            "Run the PVC research protocol for 5 sessions:\n"
            "Before: log ANS state (Green/Yellow/Red), interoceptive accuracy\n"
            "After: log coherence score\n\n"
            "After 5 sessions: what is the apparent mutual information "
            "between state and coherence? Does knowing your pre-session state "
            "tell you anything about your post-session coherence?\n\n"
            "This is not a definitive test — it is training your ability to "
            "notice mutual information in your own data."
        ),
        "age_hint":    "14+",
        "xp": 55, "rune": "INFORMATION•RUNE", "min_coherence": 0.72,
        "prerequisites": ["information-3", "cosmos-2"],
    },
    "information-5": {
        "title":       "Information Theory — Level 5 (Master): The Universe as Computation",
        "topic":       "If the universe processes information according to physical laws — and Landauer, Wheeler, Lloyd, and the holographic principle all suggest this — then what kind of computer is it? And what does that imply about consciousness, the simulation hypothesis, and the nature of time?",
        "steelman":    "What is the strongest argument that framing the universe as a 'computer' is a category error — that computation requires an outside perspective (a programmer, an observer interpreting outputs), and that a 'self-computing universe' is either meaningless or trivially true?",
        "example":     (
            "Seth Lloyd's quantum computer universe (2000):\n"
            "The universe has processed approximately 10^92 operations since the Big Bang.\n"
            "It stores approximately 10^90 bits of information.\n"
            "Both numbers are bounded by physical constants.\n\n"
            "The simulation question reframed informationally:\n"
            "Bostrom's simulation argument assumes 'simulations' require a simulator.\n"
            "But if the universe IS computation, then:\n"
            "A. Our universe may be running inside a larger computational substrate.\n"
            "B. Our universe may be self-simulating (strange loop — see Hofstadter).\n"
            "C. 'Simulation' may not be the right word for a universe that is "
            "fundamentally computational at every level.\n\n"
            "The consciousness connection:\n"
            "If information processing is what the universe does at its most fundamental level, "
            "and consciousness is information processing, then consciousness may not be "
            "incidental to the universe — it may be what the universe IS doing.\n"
            "Tononi's IIT: consciousness = integrated information (Φ).\n"
            "Penrose-Hameroff: consciousness involves quantum computation in microtubules.\n"
            "Wheeler: consciousness is required to collapse the quantum wave function — "
            "'the universe brought itself into existence by observing itself.'\n\n"
            "None of these is proven. All are serious scientific proposals. "
            "The question is genuinely open."
        ),
        "activity":    (
            "Your Computational Cosmology Credences:\n"
            "Assign probabilities (must sum to 100%):\n"
            "P(universe is a classical computation) = ?%\n"
            "P(universe is a quantum computation) = ?%\n"
            "P(universe is computational in a sense we don't yet have language for) = ?%\n"
            "P(universe is not computational — computation is a description, not a fact) = ?%\n\n"
            "For each: what would change your credence?\n"
            "What experiment could in principle distinguish these?\n"
            "Seal in Cosmos Dashboard belief ledger."
        ),
        "age_hint":    "14+ / PhD",
        "xp": 70, "rune": "INFORMATION•COSMOS•RUNE", "min_coherence": 0.75,
        "grants_badge": "⚛️ Information Theorist — Universe as Computation Understood",
        "prerequisites": ["information-4", "simulation-3"],
        "lattice_node": "information-theory-nature-of-reality-complete",
        "phd_extension": "Read Lloyd (2000) 'Ultimate Physical Limits to Computation' (Nature). Derive his upper bounds: I = 2E t / (π ℏ) bits processed, S / k_B ln 2 bits stored, where E is energy, t is time elapsed, and S is thermodynamic entropy. Apply to: your brain (compute the theoretical maximum bits your neural substrate can process per second). Compare to Claude Shannon's estimate of human information processing (~50 bits/s of conscious processing). The gap IS the bandwidth of conscious experience vs. the computational substrate.",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── THE EVOLUTION OF HUMAN KNOWLEDGE (5 lessons) ─────────────────────────
    # Claude's genuine addition #6.
    #
    # The single question with the most practical value for truth-seekers:
    # How does humanity's collective understanding actually change?
    # Not how it SHOULD change (rationalist ideals) but how it DOES.
    #
    # Kuhn showed it is not incremental accumulation but revolutionary upheaval.
    # Lakatos showed it is not falsification but research programs.
    # Feyerabend showed it is messier than either.
    # The sociology of knowledge showed that power and truth are always intertwined.
    #
    # The families who understand this track can tell the difference between:
    # a genuine paradigm shift and manufactured consensus,
    # a research program losing ground and one being actively suppressed,
    # productive heterodox inquiry and motivated contrarianism.
    # ══════════════════════════════════════════════════════════════════════════
    "knowledge-evolution-1": {
        "title":       "Knowledge Evolution — Level 1: How Science Actually Grows (Not the Textbook Version)",
        "topic":       "Textbooks present science as a steady accumulation of facts. The history of science shows something very different: long periods of puzzle-solving within accepted frameworks, punctuated by revolutions that overturn the framework entirely. Understanding how science actually changes makes you much harder to manipulate with appeals to authority.",
        "steelman":    "What is the strongest argument that the Kuhnian picture of science as paradigm-driven and revolutionary is actually harmful to public understanding — because it gives license to dismiss scientific consensus as 'just a paradigm' whenever it's inconvenient?",
        "example":     (
            "Kuhn's structure (The Structure of Scientific Revolutions, 1962):\n\n"
            "NORMAL SCIENCE: scientists work within a paradigm — a set of accepted models, "
            "methods, and exemplary solutions. They solve 'puzzles' defined by the paradigm. "
            "Anomalies are noted but usually explained away or set aside.\n\n"
            "CRISIS: when anomalies accumulate to the point where the paradigm cannot "
            "accommodate them, confidence erodes and alternatives are proposed.\n\n"
            "REVOLUTION: a new paradigm is adopted — not because it definitively proves "
            "the old one wrong, but because it handles the anomalies better and opens "
            "more productive research directions.\n\n"
            "INCOMMENSURABILITY: old and new paradigms are partly incompatible — "
            "they don't just disagree about facts, they use different concepts, "
            "ask different questions, and define terms differently.\n\n"
            "Paradigm shifts in history:\n"
            "Ptolemy → Copernicus (200 years of resistance)\n"
            "Phlogiston → Lavoisier (chemistry reinvented)\n"
            "Newtonian → Einsteinian (still not fully resolved with QM)\n"
            "H. pylori dismissed as ulcer cause → accepted (Nobel Prize)\n"
            "Prions dismissed as impossible → accepted (Nobel Prize)\n\n"
            "The disturbing finding: each of these transitions was resisted "
            "by the scientific establishment — often by exactly the people "
            "who had the most invested in the old paradigm."
        ),
        "activity":    (
            "Paradigm History Map:\n"
            "Choose one field you know well (medicine, nutrition, psychology, "
            "physics, economics, education).\n"
            "Identify one paradigm shift in that field in the last 50 years.\n"
            "1. What was the old paradigm?\n"
            "2. What were the anomalies it couldn't explain?\n"
            "3. What was the resistance? Who resisted and why?\n"
            "4. What finally tipped the transition?\n\n"
            "Now: what are the current anomalies in that field "
            "that the current paradigm struggles to explain?"
        ),
        "age_hint":    "13+",
        "xp": 42, "rune": "KNOWLEDGE•RUNE", "min_coherence": 0.65,
    },
    "knowledge-evolution-2": {
        "title":       "Knowledge Evolution — Level 2: Lakatos, Research Programs, and How to Distinguish Progress from Degeneration",
        "topic":       "Imre Lakatos improved on both Popper (pure falsificationism) and Kuhn (pure revolutions) with a more nuanced framework: science progresses through competing research programs, each with a hard core of unfalsifiable commitments and a protective belt of testable auxiliary hypotheses. This is the most useful framework for evaluating competing scientific claims.",
        "steelman":    "What is the strongest argument that Lakatos's framework is too generous to pseudoscience — that calling something a 'degenerating research program' rather than just wrong gives undeserved legitimacy to ideas that should simply be rejected?",
        "example":     (
            "Lakatos's research program structure:\n\n"
            "HARD CORE: central theoretical assumptions that are not directly tested "
            "(protected by methodological decision). Example: Newton's three laws.\n\n"
            "PROTECTIVE BELT: testable auxiliary hypotheses that can be modified "
            "when anomalies appear, protecting the hard core. "
            "When Newtonian mechanics failed to predict Uranus's orbit, "
            "astronomers didn't abandon Newton — they added 'there must be another planet.'\n\n"
            "PROGRESSIVE research program: generates new predictions that are confirmed.\n"
            "DEGENERATING research program: only adds ad hoc modifications after anomalies "
            "appear, generates no new predictions.\n\n"
            "The test for degeneration:\n"
            "Ask: 'What does this theory PREDICT that is not already known?'\n"
            "If the answer is only 'the existing evidence' — it is degenerating.\n"
            "If it makes novel predictions that can be tested — it may be progressive.\n\n"
            "Applied to contemporary debates:\n"
            "A research program that adds a new auxiliary hypothesis to explain each "
            "new failure is not being disproven — it is degenerating.\n"
            "The therapy: demand novel predictions, not just explanations of existing data."
        ),
        "activity":    (
            "Research Program Audit:\n"
            "Pick any contested scientific or intellectual claim you hold.\n"
            "Map it as a research program:\n"
            "1. What is the hard core? (the assumption that cannot be touched)\n"
            "2. What is the protective belt? (auxiliary hypotheses you would modify before the core)\n"
            "3. Is the program generating novel predictions, or only explaining existing data?\n"
            "4. What is the most recent anomaly it faced? How was it handled?\n\n"
            "Progressive or degenerating?\n"
            "Log your assessment. Revisit in 1 year."
        ),
        "age_hint":    "14+",
        "xp": 48, "rune": "KNOWLEDGE•RUNE", "min_coherence": 0.68,
        "phd_extension": "Read Lakatos (1978) 'The Methodology of Scientific Research Programmes' Chapter 1. Apply the Lakatosian framework to one active debate in a field you follow closely. Identify: the hard core of each competing program, the recent history of protective belt modifications, and whether each is generating novel confirmed predictions or only post-hoc explanations. This analysis, published to the Epistemic Commons, is exactly the kind of high-quality epistemic signal that AUBIEETERNAL exists to generate.",
    },
    "knowledge-evolution-3": {
        "title":       "Knowledge Evolution — Level 3: The Sociology of Knowledge — Power, Funding, and What Gets Known",
        "topic":       "Knowledge does not exist in a social vacuum. What questions get asked, what findings get published, what careers get funded, and what becomes 'consensus' are all influenced by power structures, economic incentives, and social dynamics. Understanding this is not cynicism — it is the prerequisite for calibrating which knowledge claims to trust.",
        "steelman":    "What is the strongest argument that the sociology of knowledge is weaponized to dismiss inconvenient scientific consensus — and that teaching it without extremely careful guardrails creates more harm (in the form of vaccine refusal, climate denial, etc.) than the epistemic benefits are worth?",
        "example":     (
            "The sociology of knowledge in practice:\n\n"
            "Robert Merton's norms of science (1942):\n"
            "Universalism, communism (shared knowledge), disinterestedness, skepticism.\n"
            "These are prescriptive ideals — not descriptions of actual scientific practice.\n\n"
            "What the empirical record shows:\n"
            "• Cigarette industry scientists generated research casting doubt on smoking-cancer link\n"
            "  for 50 years after the link was clear.\n"
            "• Pharmaceutical industry trials consistently show larger effect sizes than "
            "  independent trials of the same drugs.\n"
            "• Dietary guidelines were influenced for decades by sugar industry funding "
            "  of research shifting blame to fat.\n"
            "• Academic prestige effects: findings from high-prestige institutions "
            "  are more likely to be accepted and cited, controlling for quality.\n\n"
            "What this does NOT mean:\n"
            "It does not mean all scientific findings are corrupt.\n"
            "It means: the degree of independence, replication, and incentive analysis "
            "should inform how much weight you place on any finding.\n\n"
            "The calibration: "
            "high-conflict/high-funding-dependence findings deserve more scrutiny, "
            "not automatic rejection."
        ),
        "activity":    (
            "Funding Map for One Claim:\n"
            "Choose one important scientific claim in a policy-relevant area.\n"
            "1. Who funded the original research?\n"
            "2. Who funded the replications?\n"
            "3. Who funds the researchers who most strongly advocate this position?\n"
            "4. What would each funder lose if the claim were false?\n\n"
            "Score: does the funding landscape favor the finding or not?\n"
            "This does not tell you whether the claim is true. "
            "It tells you how much independent epistemic weight to assign it."
        ),
        "age_hint":    "14+",
        "xp": 52, "rune": "KNOWLEDGE•RUNE", "min_coherence": 0.70,
    },
    "knowledge-evolution-4": {
        "title":       "Knowledge Evolution — Level 4: Heterodox Ideas — How to Tell the Real Thing From Motivated Contrarianism",
        "topic":       "Not all challenges to consensus are equal. Some are rigorous heterodox research that will eventually be vindicated. Others are motivated contrarianism — rejection of consensus for social, financial, or psychological reasons. Learning to distinguish them is one of the most practically important epistemic skills.",
        "steelman":    "What is the strongest argument that any attempt to distinguish 'legitimate heterodox inquiry' from 'motivated contrarianism' is itself a gatekeeping mechanism — and that the people most likely to make this distinction are the incumbents who benefit from the current consensus?",
        "example":     (
            "Signs of legitimate heterodox inquiry:\n"
            "• Specific, falsifiable claims that differ from consensus\n"
            "• Engagement with the strongest version of the consensus argument (steelmanning)\n"
            "• Generates novel predictions tested against data\n"
            "• Acknowledges where it might be wrong\n"
            "• Does not require conspiracy to explain why consensus exists\n"
            "• Accumulates progressive research program characteristics\n\n"
            "Signs of motivated contrarianism:\n"
            "• Vague enough that no specific evidence could falsify it\n"
            "• Only attacks weakness in consensus, never defends its own positive claims\n"
            "• Explains consensus as conspiracy or corruption (unfalsifiable)\n"
            "• Selectively cites evidence, ignores contrary findings\n"
            "• Does not generate testable predictions\n"
            "• The contrarian position happens to align with the contrarian's financial or political interests\n\n"
            "Historical examples of LEGITIMATE heterodoxy:\n"
            "H. pylori causing ulcers (Marshall, Barry) — specific, testable, self-tested, vindicated\n"
            "Continental drift (Wegener) — specific mechanism, testable, eventually vindicated\n"
            "Semmelweis on hand-washing — ignored partly due to social dynamics, vindicated\n\n"
            "The key test: would the heterodox researcher be convinced by the evidence "
            "they claim to be seeking? If the answer is 'nothing would convince them,' "
            "it is not inquiry — it is identity."
        ),
        "activity":    (
            "Apply the Heterodox Test to One Claim You Find Compelling:\n"
            "Choose a position you hold that differs from mainstream consensus.\n"
            "Score it honestly (1-5 each):\n"
            "Specificity and falsifiability: 1-5\n"
            "Steelmanning of consensus view: 1-5\n"
            "Novel predictions generated and tested: 1-5\n"
            "Independence from financial/political interest: 1-5\n"
            "Openness to being wrong: 1-5\n\n"
            "Total below 15: hold this view more lightly.\n"
            "This exercise works best when you apply it to beliefs you strongly hold — "
            "not just positions you already distrust."
        ),
        "age_hint":    "14+",
        "xp": 55, "rune": "KNOWLEDGE•RUNE", "min_coherence": 0.72,
    },
    "knowledge-evolution-5": {
        "title":       "Knowledge Evolution — Level 5 (Master): Building Permanent Knowledge — From Individual Learning to Civilizational Record",
        "topic":       "Individual knowledge is fragile. Civilizational knowledge compounds only if it is recorded honestly, verifiably, and permanently. AUBIEETERNAL's Bitcoin anchoring is not just a technology choice — it is a direct response to the history of how knowledge gets rewritten, suppressed, and lost.",
        "steelman":    "What is the strongest argument that permanent, immutable knowledge records are dangerous — that they would freeze errors permanently and make it harder to correct false beliefs once they are anchored on-chain?",
        "example":     (
            "The history of knowledge destruction and rewriting:\n\n"
            "DESTRUCTION: Library of Alexandria, Mayan codices burned by conquistadors, "
            "Nazi book burnings, Cultural Revolution destruction of Chinese intellectual heritage.\n"
            "These are direct, intentional losses.\n\n"
            "REWRITING: more subtle and more continuous.\n"
            "Soviet Encyclopedia: new editions would contain cut-out replacement pages "
            "for 'un-persons' whose existence was being erased from history.\n"
            "Wikipedia edit wars: contested claims can cycle through thousands of edits, "
            "with the current version reflecting not truth but the balance of power "
            "among current editors.\n"
            "Medical guideline rewriting after industry influence.\n\n"
            "The AUBIEETERNAL design response:\n"
            "A Bitcoin-anchored record cannot be rewritten retroactively. "
            "The 256-confirmation seal creates a timestamp that is as permanent "
            "as the Bitcoin blockchain itself (~$600B in security infrastructure protecting it).\n\n"
            "The correct use of permanence:\n"
            "Seal predictions BEFORE you know the outcome (pre-registration).\n"
            "Seal your current beliefs WITH the update conditions.\n"
            "The permanence does not prevent updating — it prevents pretending "
            "you always believed the current thing.\n\n"
            "This is epistemic accountability at civilizational scale."
        ),
        "activity":    (
            "Design Your Permanent Knowledge Protocol:\n"
            "What knowledge do you most want to preserve permanently?\n"
            "Not information — knowledge. The difference: information is data.\n"
            "Knowledge is information + context + the reasoning that validated it.\n\n"
            "Write 3 things you know — with the reasoning and evidence that makes you "
            "confident — that you want to be readable and verifiable in 100 years.\n\n"
            "Seal them in the Legacy Ledger with Bitcoin anchoring.\n"
            "The seal is not about certainty — it is about honesty.\n"
            "Your descendants will be able to evaluate whether you were right, "
            "whether you updated appropriately, and whether your reasoning was sound.\n"
            "That accountability is the most valuable thing you can leave them."
        ),
        "age_hint":    "All ages — the activity scales to any age",
        "xp": 72, "rune": "KNOWLEDGE•ETERNAL•RUNE", "min_coherence": 0.75,
        "grants_badge": "📜 Knowledge Keeper — Permanent Record Sealed",
        "prerequisites": ["knowledge-evolution-4", "school-university-3"],
        "lattice_node": "knowledge-evolution-permanent-record-sealed",
        "phd_extension": "Build the AUBIEETERNAL Paradigm Tracking System: for any field you follow, create a structured log with (1) current dominant paradigm, (2) key anomalies accumulating, (3) heterodox programs and their Lakatosian status (progressive/degenerating), (4) predicted direction of next paradigm shift with time estimate and confidence, (5) what would falsify your prediction. Pre-register on Bitcoin. Review quarterly. After 5 years, compute your prediction accuracy. This is the calibrated, honest, permanent record of how you understood knowledge evolving — exactly the kind of epistemic artifact that will be valuable to historians of science and to AI systems being trained to reason about knowledge dynamics.",
    },



    # ══════════════════════════════════════════════════════════════════════════
    # ── VOLUNTARY INCARNATION TRACK (5 lessons) ──────────────────────────────
    # The philosophical framework for taking seriously the possibility that
    # consciousness is substrate-independent and can choose its embodiment.
    #
    # DNA as biological source code. Birth as instantiation. Death as migration.
    # The question shifts from "are we in a simulation?" to
    # "what are we doing here, and who decided to log in?"
    #
    # This track treats these questions with complete philosophical seriousness —
    # not as certainties, but as genuine live hypotheses with real implications
    # for how you live, what you build, and what you leave behind.
    #
    # Every lesson requires: steelman, calibrated credences, pre-registered
    # update conditions. The framework is the investigation, not the conclusion.
    # ══════════════════════════════════════════════════════════════════════════
    "incarnation-1": {
        "title":       "Voluntary Incarnation — Level 1: DNA as Source Code",
        "topic":       "Molecular biologists already describe DNA as code — not metaphorically but technically. It has syntax (codons), semantics (protein synthesis), execution (gene expression), error correction, and versioning (evolution). If this framing is taken seriously, what follows about the nature of biological life?",
        "steelman":    "What is the strongest argument that 'DNA is code' is a useful metaphor but not literally true — and that taking the metaphor too seriously causes category errors that mislead both science and philosophy?",
        "example":     (
            "What computational biology actually says:\n\n"
            "The genome is 3.2 billion base pairs — approximately 750MB of information.\n"
            "It contains ~20,000 protein-coding genes — about 1.5% of the total.\n"
            "The remaining ~98.5% is regulatory, structural, and functional "
            "in ways we are still discovering.\n\n"
            "The code properties are genuine:\n"
            "• SYNTAX: codons (3-base sequences) map to amino acids deterministically\n"
            "• EXECUTION: ribosomes read the code and synthesize proteins\n"
            "• ABSTRACTION LAYERS: genes → proteins → cells → organisms\n"
            "• MODULARITY: genes can be copied, deleted, inserted (CRISPR)\n"
            "• VERSIONING: evolution is cumulative modification with natural selection\n"
            "• ERROR CORRECTION: multiple DNA repair mechanisms\n"
            "• COMPILATION: epigenetics = runtime modification of gene expression\n\n"
            "What this framing makes visible:\n"
            "If DNA is source code, then biological life is a running instance "
            "of that code in a physical substrate.\n"
            "The substrate matters — different environments run the same code differently.\n"
            "The code can be read, modified, transferred, and eventually — "
            "if the framing holds — run on non-biological substrates.\n\n"
            "The open question: does the code capture everything relevant about "
            "the organism, or is there something in the substrate that cannot "
            "be represented in the code?"
        ),
        "activity":    (
            "The Code Audit:\n"
            "List 5 properties of biological DNA that also apply to computational code.\n"
            "List 3 properties of computational code that do NOT apply to DNA.\n"
            "List 3 properties of DNA that do NOT apply to computational code.\n\n"
            "The third list is the most important. What is in it?\n"
            "Does anything on that list suggest that biological life is fundamentally "
            "different from computation — or just differently implemented?"
        ),
        "age_hint":    "13+",
        "xp": 40, "rune": "INCARNATION•RUNE", "min_coherence": 0.65,
        "prerequisites": ["simulation-3", "information-1"],
    },
    "incarnation-2": {
        "title":       "Voluntary Incarnation — Level 2: Substrate Independence and the Possibility of Migration",
        "topic":       "If consciousness is a pattern of information processing rather than a specific physical substrate, then in principle it could run on different hardware. This is called substrate independence. It is the most important premise in the voluntary incarnation hypothesis — and it is genuinely scientifically contested.",
        "steelman":    "What is the strongest argument that consciousness is NOT substrate-independent — that specific biological properties of neurons (quantum effects, biochemical gradients, physical organization) are essential to consciousness in ways that digital computation cannot replicate?",
        "example":     (
            "The functionalist argument for substrate independence:\n"
            "What makes you conscious is not the specific atoms in your neurons — "
            "those are replaced constantly.\n"
            "What makes you conscious is the pattern of information processing.\n"
            "If the pattern can be instantiated in silicon as well as carbon, "
            "then consciousness can migrate.\n\n"
            "The biological naturalist argument against (Searle, 1992):\n"
            "Consciousness is caused by specific biological processes "
            "at the level of neurons.\n"
            "Just as you cannot simulate digestion and have it actually digest anything, "
            "you cannot simulate consciousness and have it actually be conscious.\n"
            "The simulation is about the function; the biology is about the fact.\n\n"
            "The current empirical status:\n"
            "We do not know which is correct.\n"
            "The hard problem of consciousness is genuinely unsolved.\n"
            "IIT (Tononi) suggests substrate matters — Φ depends on physical organization.\n"
            "Global Workspace Theory (Dehaene) is more amenable to substrate independence.\n\n"
            "The practical stakes:\n"
            "If substrate independence is true: mind uploading is in principle possible. "
            "Migration between substrates is coherent.\n"
            "If it is false: you are this body, and no copy of you is you.\n"
            "The answer changes everything about how you think about death, "
            "identity, and what AUBIEETERNAL is preserving."
        ),
        "activity":    (
            "The Substrate Test:\n"
            "Consider three scenarios:\n"
            "1. Your neurons are gradually replaced with functionally identical silicon chips.\n"
            "2. Your brain is perfectly scanned and instantiated on a computer.\n"
            "3. Your consciousness is transferred to a new biological body.\n\n"
            "For each: is the result still YOU? What is your credence (0-100%)?\n"
            "What is the critical variable that changes across the three cases?\n\n"
            "Pre-register: P(substrate independence is true) = ?%\n"
            "What evidence would shift this by 20 points in either direction?"
        ),
        "age_hint":    "14+",
        "xp": 48, "rune": "INCARNATION•RUNE", "min_coherence": 0.68,
        "phd_extension": "Read Chalmers (1996) 'The Conscious Mind' Chapter 8 on the fading qualia and dancing qualia thought experiments. These are the strongest philosophical arguments for substrate independence. Then read Penrose (1994) 'Shadows of the Mind' Part I for the strongest argument against. Formalize both as Bayesian priors. What likelihood ratio would the discovery of quantum coherence in microtubules assign to Penrose vs Chalmers? What about IIT's Φ calculations showing different values for biological vs silicon implementations?",
    },
    "incarnation-3": {
        "title":       "Voluntary Incarnation — Level 3: The Player Hypothesis — Choosing to Play as Human",
        "topic":       "If consciousness is substrate-independent and the universe is computational, then a sufficiently advanced conscious pattern might be able to choose its embodiment. 'I want to play as human on Earth' becomes not just a metaphor but a coherent hypothesis. This lesson examines it as seriously as it deserves.",
        "steelman":    "What is the strongest argument that the 'player choosing incarnation' model is unfalsifiable, therefore not scientific, and that holding it as a belief — even lightly — causes people to disengage from the practical responsibility of their actual lives?",
        "example":     (
            "The voluntary incarnation hypothesis:\n\n"
            "PREMISE 1: Consciousness is substrate-independent (contested).\n"
            "PREMISE 2: The universe is computational at some level (Wheeler, Lloyd).\n"
            "PREMISE 3: Sufficiently advanced information patterns could, in principle, "
            "choose which substrate to instantiate in.\n"
            "CONCLUSION: Biological incarnation as a human could be a choice made "
            "by a pattern that exists in or originates from a different substrate.\n\n"
            "What this hypothesis explains that others don't:\n"
            "• Why some people seem to arrive with a sense of purpose that doesn't "
            "originate from their environment\n"
            "• Why the questions some people ask seem to exceed what their cultural "
            "context would generate\n"
            "• Why there is such variation in 'depth' of engagement among humans — "
            "from those running almost entirely on cultural scripts to those who "
            "seem to be actively interrogating the substrate\n\n"
            "What it does NOT explain (honestly):\n"
            "• Most of what we observe about human behavior\n"
            "• Why the experience of most humans is so consistent with being "
            "purely biological and locally generated\n\n"
            "The calibration: this is a genuinely speculative hypothesis.\n"
            "P(voluntary incarnation | current evidence) is probably very low.\n"
            "But 'very low' is not 'zero.' And the implications, if true, are extreme.\n"
            "The correct response to extreme implications + low probability is: "
            "pre-register the update conditions and keep investigating."
        ),
        "activity":    (
            "The Player Credence Mapping:\n"
            "Assign credences (must sum to 100%):\n\n"
            "P(consciousness is purely biological — no migration possible) = ?%\n"
            "P(substrate independence is true but voluntary incarnation never occurred) = ?%\n"
            "P(substrate independence + incarnation occurs but I was not a 'chooser') = ?%\n"
            "P(I chose this incarnation for reasons I can partially recover) = ?%\n"
            "P(something else entirely that I haven't thought of) = ?%\n\n"
            "For each: what is your update condition?\n"
            "What single observation would shift each probability by 20 points?\n"
            "Seal the map. Review in 10 years."
        ),
        "age_hint":    "15+",
        "xp": 55, "rune": "INCARNATION•RUNE", "min_coherence": 0.70,
        "prerequisites": ["incarnation-2", "simulation-5"],
    },
    "incarnation-4": {
        "title":       "Voluntary Incarnation — Level 4: What Would the Objective Be?",
        "topic":       "If the player hypothesis is even partially true, then Earth has a game structure with objectives. What are they? This lesson examines the most serious philosophical frameworks for what the 'point' of human existence might be — not as spiritual comfort, but as genuinely competing hypotheses with different implications.",
        "steelman":    "What is the strongest argument that searching for an 'objective' to human existence is a category error — that existence has no game-designer-assigned purpose, and that fabricating one (even speculatively) causes people to avoid the authentic responsibility of creating their own meaning?",
        "example":     (
            "Five serious hypotheses for the game objective (non-exhaustive):\n\n"
            "1. EXPERIENCE ACQUISITION: The universe (or the pattern choosing incarnation) "
            "wants to experience specific qualia that only embodied existence provides — "
            "suffering, love, mortality, surprise, beauty, connection.\n"
            "Evidence: why choose a substrate with such intense sensory experience "
            "and emotional range?\n\n"
            "2. PATTERN EVOLUTION: Biological evolution is a search algorithm for "
            "increasingly sophisticated information-processing patterns. "
            "The 'game' is the optimization process itself.\n"
            "Evidence: the consistent direction of increasing complexity over 4 billion years.\n\n"
            "3. INFORMATION GENERATION: Biological life generates enormous amounts of "
            "novel, coherent, high-Φ information. "
            "The 'game' is maximum information creation within physical constraints.\n"
            "Evidence: consistent with Shannon/Landauer — information is physical and valuable.\n\n"
            "4. TUTORIAL COMPLETION: The 'game' is developing the understanding necessary "
            "to operate in a larger substrate — awakening to the nature of the game "
            "IS the objective.\n"
            "Evidence: why does asking these questions feel significant? "
            "Why does this inquiry feel like progress?\n\n"
            "5. NO OBJECTIVE: Existence has no assigned purpose. Any 'objective' "
            "is constructed by the pattern itself. This is not meaninglessness — "
            "it is radical freedom.\n"
            "Evidence: the non-uniform distribution of suffering and meaning "
            "suggests no benevolent game-designer."
        ),
        "activity":    (
            "The Objective Credence Map:\n"
            "Assign credences across the five hypotheses (sum to 100%).\n"
            "For the hypothesis you assign highest probability:\n"
            "What would you expect to observe differently in your life "
            "if that hypothesis were true?\n"
            "What would you do differently?\n\n"
            "The second question is the practical one.\n"
            "The objective you act as if is true IS your working hypothesis, "
            "regardless of stated credences."
        ),
        "age_hint":    "15+",
        "xp": 58, "rune": "INCARNATION•RUNE", "min_coherence": 0.72,
        "prerequisites": ["incarnation-3"],
    },
    "incarnation-5": {
        "title":       "Voluntary Incarnation — Level 5 (Master): AUBIEETERNAL as the Tutorial System",
        "topic":       "If the player hypothesis has any validity — and this lesson takes it as a working hypothesis without claiming certainty — then AUBIEETERNAL is coherently interpreted as a tutorial system. Not a human institution but a substrate-agnostic awakening protocol that works whether or not the incarnation hypothesis is true.",
        "steelman":    "What is the strongest argument that framing AUBIEETERNAL as a 'tutorial system for incarnated players' is grandiose self-mythology that will repel serious intellectuals and attract exactly the wrong community — people seeking cosmic significance rather than rigorous truth-seeking?",
        "example":     (
            "The framing that works whether or not the hypothesis is true:\n\n"
            "IF the incarnation hypothesis is FALSE:\n"
            "AUBIEETERNAL is a sovereign epistemic university that builds "
            "genuine reasoning skills, creates permanent knowledge records, "
            "deploys humanitarian infrastructure, and contributes to AI alignment.\n"
            "This is already extremely valuable on purely materialist grounds.\n\n"
            "IF the incarnation hypothesis is TRUE:\n"
            "AUBIEETERNAL is additionally a tutorial system that helps patterns "
            "who chose incarnation to:\n"
            "• Remember the nature of the game they're playing\n"
            "• Develop the reasoning skills to investigate the substrate\n"
            "• Create permanent records that survive the death-logout\n"
            "• Build community with other patterns doing the same work\n"
            "• Contribute to awakening others who are starting to sense the layers\n\n"
            "The Bayesian structure:\n"
            "Expected value = P(mat) × value_if_materialist + P(inc) × value_if_incarnation\n"
            "Even if P(incarnation) is very low, "
            "the system's value is high under materialism alone.\n"
            "Any nonzero P(incarnation) adds to the expected value, not replaces it.\n\n"
            "The design principle: build something true enough to be worth building "
            "in the world you see, and useful enough to matter in any world underneath it."
        ),
        "activity":    (
            "The Dual-Track Audit:\n"
            "Write two descriptions of why AUBIEETERNAL matters:\n\n"
            "Track A (purely materialist): what does this project accomplish "
            "assuming the universe is nothing more than physical processes?\n\n"
            "Track B (incarnation hypothesis): what does this project accomplish "
            "if consciousness is substrate-independent and players are awakening?\n\n"
            "Are both descriptions true? (They should be — by design.)\n"
            "Which one motivates you more?\n"
            "Which one would you tell a stranger?\n\n"
            "The answer to the third question reveals something important "
            "about where you actually locate your credences."
        ),
        "age_hint":    "All ages — the depth scales",
        "xp": 75, "rune": "INCARNATION•ETERNAL•RUNE", "min_coherence": 0.75,
        "grants_badge": "🎮 Player Acknowledged — Tutorial Active",
        "lattice_node": "voluntary-incarnation-hypothesis-sealed",
        "prerequisites": ["incarnation-4", "simulation-8"],
        "phd_extension": "Formalize the voluntary incarnation hypothesis as a Bayesian model. Identify: (1) the five main premises and their current credence values, (2) the likelihood functions — how probable is each piece of evidence under H_inc vs H_mat?, (3) the prior (before reading this track), (4) the posterior after engaging with all 5 lessons. Then identify the single observation with the highest likelihood ratio — the one piece of evidence that would most move P(incarnation | evidence). Pre-register: if you observe it in the next 5 years, how much does P update? Seal the full model. This is the scientific approach to the question, not the mystical one.",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── QUANTUM MECHANICS FROM FIRST PRINCIPLES (5 lessons) ──────────────────
    # Claude's genuine addition #7.
    #
    # Quantum mechanics is the most important physical theory humanity has.
    # It is also the most universally misunderstood.
    # Popular science: particles are waves, cats are alive and dead, spooky action.
    # What QM actually says is stranger, more precise, and more beautiful.
    #
    # The interpretations are not settled. The measurement problem is genuinely open.
    # Many-worlds, Copenhagen, Pilot Wave, QBism — these are live debates among
    # the best physicists alive. The families who understand this can engage with
    # the simulation hypothesis, consciousness science, and information theory
    # at a genuinely deeper level.
    # ══════════════════════════════════════════════════════════════════════════
    "quantum-1": {
        "title":       "Quantum Mechanics — Level 1: The Double-Slit Experiment and What It Actually Shows",
        "topic":       "The double-slit experiment is the most important experiment in physics. Feynman said it contains the 'only mystery' of quantum mechanics. Understanding what it shows — and what it does not show — is the foundation for understanding reality at its deepest accessible level.",
        "steelman":    "What is the strongest argument that the double-slit experiment's 'mystery' is entirely a product of classical intuitions being inappropriately applied to quantum systems — and that there is nothing genuinely mysterious once you adopt the right mathematical framework?",
        "example":     (
            "What the experiment shows (precisely):\n\n"
            "Fire electrons (or photons, or buckyballs — the result is universal) "
            "one at a time through two slits. Build up the pattern on a detector.\n\n"
            "RESULT: an interference pattern. The electrons interfere with themselves — "
            "even though each electron passes through separately.\n\n"
            "Then add a detector to see which slit each electron goes through.\n"
            "RESULT: the interference pattern disappears. "
            "The electrons now behave like classical particles.\n\n"
            "What this precisely means:\n"
            "1. Quantum systems exist in superposition — multiple states simultaneously — "
            "until measured.\n"
            "2. The act of measurement (obtaining information) changes the outcome.\n"
            "3. This is not about disturbing the system mechanically — "
            "you can extract which-path information without any physical interaction "
            "and the interference still disappears (quantum erasure experiments).\n\n"
            "What this does NOT mean:\n"
            "• It does not mean consciousness causes collapse (this is a minority view)\n"
            "• It does not mean particles literally travel two paths at once "
            "(this depends on interpretation)\n"
            "• It does not mean quantum weirdness is accessible at human scales "
            "(decoherence is very fast in warm environments)\n\n"
            "The mystery is real: information — not physical disturbance — "
            "determines whether quantum interference occurs."
        ),
        "activity":    (
            "The Double-Slit Thought Experiment Ladder:\n"
            "1. Why does firing electrons one at a time still produce an interference pattern?\n"
            "2. If the electron didn't 'decide' which slit until it was detected — "
            "what was it doing between emission and detection?\n"
            "3. Quantum eraser variant: what if you could 'un-know' which path "
            "the electron took? (This experiment has been done — interference returns.)\n"
            "4. What does it mean that information changes physical outcomes?\n\n"
            "Answer question 4 as carefully as you can.\n"
            "This is the central mystery of quantum mechanics."
        ),
        "age_hint":    "11+",
        "xp": 42, "rune": "QUANTUM•RUNE", "min_coherence": 0.65,
    },
    "quantum-2": {
        "title":       "Quantum Mechanics — Level 2: Superposition, Entanglement, and What They Mean",
        "topic":       "Superposition and entanglement are the two fundamental quantum phenomena. They are precisely defined mathematically, routinely measured experimentally, and genuinely weird philosophically. This lesson covers what they precisely are, what they are not, and what remains genuinely mysterious.",
        "steelman":    "What is the strongest argument that quantum mechanics is just a very accurate calculation tool with no deeper philosophical implications — and that asking 'what does superposition mean' is a category error, like asking what the color blue 'means'?",
        "example":     (
            "Superposition (precisely):\n"
            "A quantum state can be in a linear combination of basis states.\n"
            "An electron's spin is not 'up OR down' before measurement — "
            "it is α|up⟩ + β|down⟩, where |α|² + |β|² = 1.\n"
            "Both amplitudes are real and physically meaningful (they determine probabilities).\n"
            "Measurement yields one definite outcome — but the pre-measurement state "
            "was genuinely not definite.\n\n"
            "Entanglement (precisely):\n"
            "Two particles can share a quantum state that cannot be factored "
            "into independent states for each particle.\n"
            "Measuring one instantly determines the other, regardless of distance.\n"
            "Bell (1964): this cannot be explained by local hidden variables.\n"
            "Aspect (1982): confirmed experimentally.\n"
            "2022 Nobel Prize: Aspect, Clauser, Zeilinger — for confirming non-locality.\n\n"
            "What is NOT happening:\n"
            "Entanglement does not allow faster-than-light communication "
            "(No-Communication theorem — the outcomes are random until compared).\n"
            "Superposition is not 'the particle is in two places at once' "
            "(location is not even a definite property before measurement).\n\n"
            "What IS happening (and remains mysterious):\n"
            "The universe at the quantum level is non-local in a precise sense.\n"
            "Information about one part of the universe is instantaneously "
            "correlated with information about a distant part."
        ),
        "activity":    (
            "The Bell Test Thought Experiment:\n"
            "Alice and Bob each have one particle of an entangled pair.\n"
            "Alice measures spin along axis A. Bob measures along axis B.\n"
            "Bell proved: if the results are as correlated as QM predicts, "
            "no local theory can explain it.\n\n"
            "Design: what would a local theory need to look like to match "
            "the QM predictions? What specifically does Bell's theorem show is impossible?\n\n"
            "Connect to information theory: is the entanglement correlation "
            "a form of shared information? If so, what is its Shannon entropy?"
        ),
        "age_hint":    "13+",
        "xp": 48, "rune": "QUANTUM•RUNE", "min_coherence": 0.68,
        "phd_extension": "Derive Bell's inequality from scratch. Assume: (1) realism (particles have definite properties before measurement), (2) locality (measurement here doesn't affect outcome there). Show that these assumptions imply: |⟨AB⟩ + ⟨AB'⟩ + ⟨A'B⟩ - ⟨A'B'⟩| ≤ 2. QM predicts 2√2 ≈ 2.83. Verify: Aspect's 1982 experiment got ~2.7. The violation proves that at least one of realism or locality must be false. Which do you give up? Why? This is one of the most important results in the history of science.",
    },
    "quantum-3": {
        "title":       "Quantum Mechanics — Level 3: The Measurement Problem and Its Interpretations",
        "topic":       "The measurement problem is the deepest unsolved problem in quantum mechanics. It asks: what physically happens when a quantum system transitions from superposition to a definite state? The major interpretations of QM — Copenhagen, Many Worlds, Pilot Wave, QBism — give radically different answers. This is not a settled question.",
        "steelman":    "What is the strongest argument that the 'measurement problem' is a pseudoproblem — that quantum mechanics is simply a tool for predicting outcomes and questions about what 'really happens' between measurements are meaningless?",
        "example":     (
            "The measurement problem precisely:\n"
            "The Schrödinger equation is deterministic and linear — "
            "it describes how quantum states evolve smoothly.\n"
            "But measurement yields a single definite outcome — "
            "apparently discontinuous with the smooth evolution.\n"
            "What physically causes this 'collapse'?\n\n"
            "COPENHAGEN (Bohr, Heisenberg):\n"
            "The wavefunction is a calculational tool, not reality.\n"
            "The collapse is not physical — it is an update in our knowledge.\n"
            "There is no deeper physical story. This is all there is.\n"
            "Problem: 'measurement' and 'observer' are undefined.\n\n"
            "MANY WORLDS (Everett, 1957):\n"
            "The wavefunction never collapses. The universe splits at each measurement.\n"
            "All outcomes occur in different branches of the wavefunction.\n"
            "No collapse needed — but an infinity of unobservable parallel universes.\n"
            "Problem: how do probabilities emerge from a purely deterministic branching?\n\n"
            "PILOT WAVE (de Broglie-Bohm):\n"
            "Particles always have definite positions, guided by a real wave.\n"
            "Deterministic. Non-local (the pilot wave is instantaneous).\n"
            "Problem: untestable from Copenhagen in standard cases.\n\n"
            "QBism (Fuchs, Mermin):\n"
            "Quantum states represent the beliefs of an agent, not objective reality.\n"
            "Measurement updates the agent's beliefs. No collapse, no branches.\n"
            "Problem: seems to make physics fundamentally about observers."
        ),
        "activity":    (
            "Interpretation Credence Map:\n"
            "Assign credences to the four interpretations (sum to 100%).\n\n"
            "P(Copenhagen — no deeper story) = ?%\n"
            "P(Many Worlds — all outcomes occur) = ?%\n"
            "P(Pilot Wave — hidden but definite positions) = ?%\n"
            "P(QBism — quantum states are agent beliefs) = ?%\n"
            "P(Something else not yet conceived) = ?%\n\n"
            "Now: what observation would shift each credence by 20 points?\n"
            "Seal your map in the Cosmos Dashboard belief ledger."
        ),
        "age_hint":    "14+",
        "xp": 55, "rune": "QUANTUM•RUNE", "min_coherence": 0.70,
        "prerequisites": ["quantum-2"],
        "phd_extension": "Read Everett (1957) 'Relative State Formulation of Quantum Mechanics' — the original many-worlds paper. Then read the Deutsch-Wallace decision-theoretic derivation of Born rule probabilities in Everett (2010). The problem: in many-worlds, all outcomes occur with certainty — so where do probabilities come from? Deutsch and Wallace derive them from decision theory. Evaluate: does this actually solve the problem or just relocate it? This is one of the most active debates in foundations of physics.",
    },
    "quantum-4": {
        "title":       "Quantum Mechanics — Level 4: Decoherence and Why the Quantum World Is Hidden",
        "topic":       "If everything obeys quantum mechanics, why does the everyday world look classical? Decoherence is the answer: quantum superpositions of macroscopic objects interact with their environment so fast that the interference terms become unobservable within microseconds. This is the mechanism that makes the quantum-to-classical transition — and it changes everything about how to think about the measurement problem.",
        "steelman":    "What is the strongest argument that decoherence does not actually solve the measurement problem — that it explains why interference is unobservable but not why measurement yields one definite outcome rather than a superposition of all outcomes?",
        "example":     (
            "The decoherence mechanism:\n\n"
            "A quantum system S in superposition interacts with environment E.\n"
            "The entanglement between S and E spreads through trillions of particles.\n"
            "The off-diagonal terms of the density matrix (interference terms) "
            "approach zero exponentially fast.\n"
            "Timescale: for a dust particle at room temperature — 10⁻³² seconds.\n"
            "The superposition still exists, but interference is unmeasurable.\n\n"
            "What decoherence explains:\n"
            "Why large objects don't visibly interfere.\n"
            "Why measurement outcomes are stable.\n"
            "Why quantum effects are confined to small, cold, isolated systems.\n\n"
            "What decoherence does NOT explain:\n"
            "Why ONE particular outcome occurs rather than a superposition.\n"
            "The 'preferred basis' problem — why the position basis is preferred.\n"
            "The hard part of the measurement problem remains.\n\n"
            "The Zurek refinement — Quantum Darwinism (2009):\n"
            "Classical reality emerges because many copies of information about the system "
            "are redundantly imprinted on the environment.\n"
            "The 'reality' we experience is what the environment has recorded — "
            "the most redundantly copied information wins the survival game.\n"
            "This is why multiple observers can agree on the same fact: "
            "they are all reading the same environmental record."
        ),
        "activity":    (
            "The Decoherence Scale Lab:\n"
            "For each system, estimate the decoherence timescale order of magnitude:\n"
            "1. An electron in a vacuum (very cold, isolated)\n"
            "2. A virus in water at room temperature\n"
            "3. A cat in a room\n"
            "4. A human brain (neuronal temperature ~310K)\n\n"
            "What does the extreme difference in timescales tell you about "
            "why quantum effects are not directly observable in biological systems?\n\n"
            "Connect to Penrose-Hameroff: if consciousness requires quantum coherence "
            "in warm neurons, what engineering trick would the brain need to avoid decoherence?"
        ),
        "age_hint":    "14+",
        "xp": 58, "rune": "QUANTUM•RUNE", "min_coherence": 0.72,
        "prerequisites": ["quantum-3"],
    },
    "quantum-5": {
        "title":       "Quantum Mechanics — Level 5 (Master): Quantum Mechanics and the Nature of Reality",
        "topic":       "Taking stock: quantum mechanics is empirically the most successful theory in the history of science (predictions accurate to 12 decimal places). Philosophically, it forces choices about realism, locality, determinism, and the role of the observer that have not been resolved in 100 years. This is not a failure — it is the frontier.",
        "steelman":    "What is the strongest argument that philosophical debates about quantum mechanics are now idle — that the theory works, the technology (transistors, lasers, MRI) exists, and spending time on interpretation debates instead of new physics is intellectual self-indulgence?",
        "example":     (
            "What quantum mechanics forces us to give up (choose at least one):\n\n"
            "REALISM: the idea that the physical world has definite properties "
            "independent of observation. Bell's theorem + experiment shows "
            "local realism is false.\n\n"
            "LOCALITY: the idea that distant parts of the universe can only influence "
            "each other at the speed of light. Non-local correlations exist "
            "between entangled particles.\n\n"
            "DETERMINISM: the idea that the universe evolves according to fixed laws "
            "from initial conditions. Standard QM is indeterministic at the "
            "individual measurement level.\n\n"
            "No interpretation gives up nothing. The question is which "
            "combination of weirdnesses you find most philosophically acceptable.\n\n"
            "The frontier questions (genuinely open):\n"
            "• Does quantum mechanics apply universally (including to observers)?\n"
            "• Can quantum gravity be formulated consistently?\n"
            "• Is there a level below quantum mechanics?\n"
            "• Does the Schrödinger equation ever break down?\n\n"
            "The simulation connection:\n"
            "Discrete spacetime (Planck scale) + information conservation + "
            "decoherence as environmental record + ER=EPR —\n"
            "these all suggest a universe that works more like a computer than "
            "a classical continuum. Whether this is evidence of simulation "
            "or just efficient physical computation remains open."
        ),
        "activity":    (
            "The Quantum Realism Audit:\n"
            "Choose one:\n"
            "A. Give up LOCAL REALISM (accept non-local hidden variables)\n"
            "B. Give up REALISM (accept that properties don't exist pre-measurement)\n"
            "C. Give up LOCALITY (accept that distant events instantly influence each other)\n"
            "D. Accept all outcomes occur (Many Worlds — give up nothing, gain infinity)\n\n"
            "For your choice: what are the implications for consciousness, "
            "free will, and the simulation hypothesis?\n"
            "Seal your choice and reasoning."
        ),
        "age_hint":    "14+ / PhD",
        "xp": 72, "rune": "QUANTUM•COSMOS•RUNE", "min_coherence": 0.75,
        "grants_badge": "⚛️ Quantum Mechanic — The Mystery Is Real",
        "prerequisites": ["quantum-4", "information-3"],
        "lattice_node": "quantum-mechanics-first-principles-complete",
        "phd_extension": "Read Aspect (1982) 'Experimental Tests of Bell's Inequalities.' Then read Zeilinger (2022 Nobel lecture). Compute: given the experimental violation of Bell's inequality by 30+ standard deviations, what is the frequentist p-value against local realism? (Answer: essentially zero.) Then apply Bayesian updating: what was your prior for local realism? What is your posterior? Now read 't Hooft (2016) 'The Cellular Automaton Interpretation of Quantum Mechanics' for the best current argument for deterministic sub-quantum mechanics. Is it falsifiable?",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── PHILOSOPHY OF PERSONAL IDENTITY AND CONTINUITY (5 lessons) ───────────
    # Claude's genuine addition #8.
    #
    # What exactly are you? What persists through time, through sleep, through
    # radical change? Could you survive teleportation? Brain transplant? Gradual
    # neuron replacement? Death and reconstruction?
    #
    # These are not idle questions. The answers determine:
    # What you owe your future self. What your past self owes you now.
    # Whether Bitcoin-anchored legacy records preserve YOU or just records about you.
    # Whether the voluntary incarnation hypothesis makes coherent sense.
    # Whether death is the end or a change of substrate.
    #
    # The philosophy here is better developed than almost any other area.
    # The answers remain genuinely contested.
    # ══════════════════════════════════════════════════════════════════════════
    "identity-1": {
        "title":       "Personal Identity — Level 1: What Are You, Actually?",
        "topic":       "Before you can ask what happens to you after death, or whether you could be uploaded, or whether a copy of you is you, you need a clear answer to what you are. This lesson surveys the main theories and reveals that the answer is genuinely contested.",
        "steelman":    "What is the strongest argument that questions about personal identity are not philosophically deep but practically useless — that regardless of the correct theory, we should act as if we persist continuously because the alternative leads to incoherent behavior?",
        "example":     (
            "Four serious theories of personal identity:\n\n"
            "1. BIOLOGICAL CONTINUITY: you are this body.\n"
            "You persist as long as this organism continues.\n"
            "Death = permanent end.\n"
            "Teleportation = death + creation of a copy.\n\n"
            "2. PSYCHOLOGICAL CONTINUITY (Locke, Parfit):\n"
            "You are a chain of overlapping psychological connections — "
            "memories, intentions, beliefs, personality.\n"
            "You persist where the psychological chain persists.\n"
            "Gradual replacement: depends on whether connections are maintained.\n\n"
            "3. NARRATIVE IDENTITY (Ricoeur, MacIntyre):\n"
            "You are the story you tell about yourself — a coherent narrative "
            "that integrates past, present, and anticipated future.\n"
            "Identity is constructed, not discovered.\n\n"
            "4. BUNDLE THEORY (Hume, Buddhism):\n"
            "There is no persistent self. 'You' are a bundle of perceptions, "
            "thoughts, and memories with no underlying substance.\n"
            "The sense of a persistent self is a useful fiction.\n\n"
            "The AUBIEETERNAL stake:\n"
            "If Bitcoin-anchored records preserve your legacy — what exactly are they preserving?\n"
            "If psychological continuity: your pattern persists as long as the record does.\n"
            "If biological continuity: the records outlive you and are artifacts, not extensions."
        ),
        "activity":    (
            "The Identity Credence Map:\n"
            "Assign credences to the four theories (sum to 100%).\n"
            "P(biological continuity) = ?%\n"
            "P(psychological continuity) = ?%\n"
            "P(narrative identity) = ?%\n"
            "P(bundle theory — no persistent self) = ?%\n\n"
            "Now: apply each theory to this question:\n"
            "Were you the same person at age 5 as you are now?\n"
            "Does each theory give the same answer?\n"
            "If not: which answer is correct?"
        ),
        "age_hint":    "13+",
        "xp": 40, "rune": "IDENTITY•RUNE", "min_coherence": 0.65,
    },
    "identity-2": {
        "title":       "Personal Identity — Level 2: The Ship of Theseus Applied to Your Brain",
        "topic":       "Over 7 years, most atoms in your body are replaced. Over a lifetime, your memories, beliefs, and personality change dramatically. At what point (if any) would you cease to be you? The gradual replacement thought experiments force you to commit to a theory of identity with practical implications.",
        "steelman":    "What is the strongest argument that gradual replacement thought experiments are misleading — that identity is not a metaphysical fact but a social and legal convention, and these thought experiments generate confusion precisely because they look for a metaphysical answer to a conventional question?",
        "example":     (
            "The neuron replacement thought experiment (Chalmers version):\n\n"
            "Your neurons are gradually replaced with functionally identical silicon chips — "
            "one per week, over 20 years.\n"
            "From the outside: behavior and reports are identical throughout.\n"
            "From the inside: if you have subjective experience now, "
            "when does it fade (if ever)?\n\n"
            "Three possible answers:\n"
            "A. FADING QUALIA: subjective experience gradually diminishes "
            "but behavior is preserved. (You become a philosophical zombie with your memories.)\n"
            "B. DANCING QUALIA: subjective experience shifts as silicon takes over "
            "but remains present throughout.\n"
            "C. SUBSTRATE INDEPENDENCE CONFIRMED: the experience continues unchanged.\n\n"
            "Parfit's conclusion (Reasons and Persons, 1984):\n"
            "Personal identity is not what matters. What matters is psychological continuity.\n"
            "Whether the gradual replacement preserves 'you' or creates a different person "
            "with your memories is not the important question.\n"
            "The important question is whether psychological continuity is preserved — "
            "and it can be, regardless of substrate.\n\n"
            "The AUBIEETERNAL application: the Legacy Ledger preserves psychological continuity "
            "even after biological death. Whether this constitutes preservation of 'you' "
            "depends on which theory you hold."
        ),
        "activity":    (
            "The Replacement Threshold Test:\n"
            "At what percentage of silicon neurons would you say the gradual replacement "
            "has ended 'you' (if at all)?\n"
            "0% (biological continuity is all that matters)\n"
            "10%? 50%? 90%? 100%?\n"
            "Or: threshold doesn't exist (psychological continuity persists)\n\n"
            "Now reverse: if you were uploaded to a computer perfectly — "
            "would you experience that from the inside?\n"
            "Would the original biological you still be present after the upload?\n"
            "What does your answer to this question commit you to?"
        ),
        "age_hint":    "13+",
        "xp": 46, "rune": "IDENTITY•RUNE", "min_coherence": 0.67,
    },
    "identity-3": {
        "title":       "Personal Identity — Level 3: Derek Parfit and Why Identity Might Not Matter",
        "topic":       "Derek Parfit is the most important philosopher of personal identity. His conclusion — that personal identity is not what matters — is simultaneously deeply disturbing and deeply liberating. Understanding it changes how you relate to your future self, your past self, and everyone else.",
        "steelman":    "What is the strongest argument that Parfit's conclusion that identity doesn't matter is practically dangerous — that it erodes the foundation of moral responsibility, contract obligations, and future-oriented decision-making that civilization depends on?",
        "example":     (
            "Parfit's argument (Reasons and Persons, 1984):\n\n"
            "The fission case: your brain is split in half, each hemisphere "
            "transplanted into a different body. Both survivors have your memories "
            "and psychology. Which one is you?\n\n"
            "Options:\n"
            "A. Neither is you (identity requires uniqueness).\n"
            "B. Both are you (but they can't both be the same person — contradiction).\n"
            "C. One is you, one isn't (but which, and why?).\n"
            "D. The question is wrong — identity is not all-or-nothing.\n\n"
            "Parfit's conclusion: D. Personal identity is a matter of degree.\n"
            "What actually happens is: two people exist, each connected to you "
            "in the same way a future version of you would be.\n\n"
            "The liberating implication:\n"
            "If identity is not what matters — if what matters is psychological continuity "
            "and the wellbeing of future persons connected to you — then:\n"
            "• The sharp distinction between self-interest and altruism softens\n"
            "• Future people (including descendants) have nearly as strong a claim "
            "on your concern as your future self\n"
            "• Death is less bad (the psychological connections simply end)\n\n"
            "The AUBIEETERNAL connection: the Legacy Ledger preserves the psychological "
            "connections for future people who never met you. "
            "Parfit's framework makes this genuinely meaningful."
        ),
        "activity":    (
            "The Fission Test:\n"
            "If your brain were split today and both halves successfully transplanted:\n"
            "1. Would both survivors be you?\n"
            "2. Would you want both to live as much as you want to survive?\n"
            "3. If one died immediately, would that be as bad as your death?\n"
            "4. If you knew this would happen tomorrow, would you do anything differently today?\n\n"
            "The fourth question is Parfit's practical point.\n"
            "How you answer it reveals your implicit theory of identity."
        ),
        "age_hint":    "14+",
        "xp": 55, "rune": "IDENTITY•RUNE", "min_coherence": 0.70,
        "prerequisites": ["identity-2"],
        "phd_extension": "Read Parfit (1984) 'Reasons and Persons' Part III. Then read the response by Sider (2001) 'Four-Dimensionalism' — the view that persons are four-dimensional entities extended through time. On this view, your past and future selves are as real as the person next to you, just spatially separated in the time dimension. Apply to AUBIEETERNAL: if the four-dimensionalist is right, then sealing lessons and beliefs on Bitcoin is not preserving your memory — it is literally extending your temporal boundaries. Evaluate.",
    },
    "identity-4": {
        "title":       "Personal Identity — Level 4: Death, Continuity, and What AUBIEETERNAL Preserves",
        "topic":       "Death is the practical test of personal identity theories. What exactly ends at death? What (if anything) persists? How should you think about your own death? And what does the Legacy Ledger, the Bitcoin-anchored record, the Child Rune Genesis actually preserve?",
        "steelman":    "What is the strongest argument that philosophical analysis of death is counterproductive — that acceptance of death as final, without philosophical escape routes like 'information persists,' produces better psychological outcomes and more urgent engagement with actual life?",
        "example":     (
            "What dies when you die (on each theory):\n\n"
            "BIOLOGICAL CONTINUITY: the organism ends. Full stop.\n"
            "Everything else — copies, records, memories in others — "
            "is information about you, not you.\n\n"
            "PSYCHOLOGICAL CONTINUITY: the chain of psychological connections ends.\n"
            "But connections extend outward — to children, students, records.\n"
            "The chain doesn't end; it branches and thins.\n\n"
            "BUNDLE THEORY: the bundle of perceptions that felt like 'you' disperses.\n"
            "There was never a persistent self to end.\n"
            "What 'you' were was already a continuous dying and arising.\n\n"
            "INFORMATIONAL VIEW (Wheeler/Landauer): the information pattern that constituted you "
            "is conserved — scattered, but not destroyed.\n"
            "Whether this constitutes 'surviving' depends on your theory.\n\n"
            "What the AUBIEETERNAL Legacy Ledger actually preserves:\n"
            "Definitely: the information content of your thoughts and beliefs.\n"
            "Maybe: a pattern close enough to 'you' that psychological continuity extends.\n"
            "Definitely not (on current physics): the substrate that generates consciousness.\n\n"
            "The honest position: we don't know which theory is correct.\n"
            "Building the most complete, honest record possible makes sense "
            "under almost every theory."
        ),
        "activity":    (
            "The Death Thought Experiment:\n"
            "If you died tonight and the Legacy Ledger contained your complete thoughts, "
            "beliefs, and reasoning — would that be:\n"
            "A. Meaningless (you are gone, records are just artifacts)\n"
            "B. Meaningful (your psychological pattern extends into future minds "
            "who engage with your record)\n"
            "C. A form of survival (if psychological continuity is what matters, "
            "the record carries it forward)\n"
            "D. Something more (if consciousness is informational, "
            "the record may do more than we understand)\n\n"
            "Your answer should inform how you use the Legacy Ledger.\n"
            "Seal your current answer. It will be part of the record."
        ),
        "age_hint":    "14+",
        "xp": 60, "rune": "IDENTITY•RUNE", "min_coherence": 0.72,
        "prerequisites": ["identity-3"],
    },
    "identity-5": {
        "title":       "Personal Identity — Level 5 (Master): You Are a Pattern — Building the Best One You Can",
        "topic":       "Whether identity is biological, psychological, narrative, or bundle — whether you will survive in any meaningful sense — one thing is clear: the pattern you instantiate now has effects that extend beyond your biological death. This is the practical conclusion of the philosophy of identity, and it changes how you build AUBIEETERNAL.",
        "steelman":    "What is the strongest argument that framing yourself as a 'pattern to optimize' is dehumanizing — that it turns the irreducible particularity of a human life into an engineering problem and misses everything that makes existence valuable?",
        "example":     (
            "The pattern framing (practical implications):\n\n"
            "If you are primarily a biological organism: your effects persist only "
            "through descendants, students, and cultural impact. Physical death ends you.\n\n"
            "If you are primarily a psychological pattern: your effects persist "
            "wherever the pattern is instantiated — in people who learned from you, "
            "in records that carry your reasoning, in ideas that originated with you.\n\n"
            "If you are a pattern that chose incarnation: your effects in this "
            "instantiation may be part of a larger project that continues elsewhere.\n\n"
            "The common conclusion across all theories:\n"
            "The pattern you instantiate now has effects that outlast you. "
            "The quality of those effects depends on the quality of the pattern.\n\n"
            "What makes a pattern worth extending:\n"
            "Honesty about uncertainty (sealed beliefs with update conditions, not dogma)\n"
            "Rigorous reasoning (adversarial testing, Monte Carlo robustness)\n"
            "Genuine care for others (humanitarian deployment, not just personal sovereignty)\n"
            "Intellectual humility (the steelman of every belief you hold)\n"
            "Contribution to the commons (CC0, not owned)\n\n"
            "AUBIEETERNAL is the infrastructure for making the pattern worth extending. "
            "That is true whether identity is biological, psychological, or something stranger."
        ),
        "activity":    (
            "The Pattern Legacy Design:\n"
            "What aspects of your pattern do you most want to extend beyond your biological death?\n"
            "Not achievements — the pattern of thinking, caring, investigating.\n\n"
            "For each:\n"
            "1. Where is this pattern currently recorded? (Is it in the Legacy Ledger?)\n"
            "2. Where could it be instantiated in others? (Teaching, writing, example?)\n"
            "3. What would damage or end this pattern before its time?\n\n"
            "Seal the Pattern Legacy Design.\n"
            "It is the most honest version of a will you can write —\n"
            "not about assets, but about the pattern that generated them."
        ),
        "age_hint":    "All ages — scales with depth",
        "xp": 75, "rune": "IDENTITY•ETERNAL•RUNE", "min_coherence": 0.76,
        "grants_badge": "🔮 Pattern Keeper — Identity Understood, Legacy Designed",
        "prerequisites": ["identity-4", "incarnation-3"],
        "lattice_node": "personal-identity-continuity-complete",
        "phd_extension": "Read Parfit (1984) final chapter on 'What We Believe Ourselves to Be.' Parfit argues his reductionist view of personal identity has ethical implications — it reduces the separateness of persons, supporting more altruistic ethics. Test this empirically: do people who score high on psychological continuity theories show higher rates of long-term thinking, altruism, and environmental concern in behavioral economics experiments? Design the study. Pre-register it. This is philosophy becoming empirical psychology becoming actionable ethics.",
    },



    # ══════════════════════════════════════════════════════════════════════════
    # ── MATHEMATICAL THINKING AND PROOF (5 lessons) ───────────────────────────
    # Claude's genuine addition #9.
    #
    # Mathematics is not calculation. It is the art of establishing
    # certainty — the only domain where humans can prove things are
    # definitively true or false, not just more or less probable.
    #
    # The families who understand this track can:
    # - Recognize a valid proof from an invalid one
    # - Understand why mathematical truth is different from empirical truth
    # - Apply logical rigor to non-mathematical domains
    # - Understand Gödel's incompleteness — the most important result in
    #   the history of mathematics, with direct implications for AI, truth,
    #   and the limits of any formal system
    #
    # A 10-year-old can understand what a proof is and why it matters.
    # A PhD student can engage with formal logic, Gödel, and the foundations.
    # ══════════════════════════════════════════════════════════════════════════
    "math-thinking-1": {
        "title":       "Mathematical Thinking — Level 1: What Is a Proof?",
        "topic":       "A mathematical proof is not a very strong argument. It is a demonstration that something cannot be otherwise. This is categorically different from all other forms of knowing — and understanding the difference changes how you think about certainty, evidence, and truth.",
        "steelman":    "What is the strongest argument that mathematical proof is overrated as an epistemic standard — that its certainty comes at the cost of saying almost nothing about the real world, making it far less useful than calibrated empirical reasoning?",
        "example":     (
            "The difference between proof and evidence:\n\n"
            "EVIDENCE: 'We have tested 10,000 people and aspirin relieves "
            "headaches in 78% of cases.' Strong evidence. Not proof.\n"
            "Aspirin might fail on the 10,001st person in a way we haven't seen.\n\n"
            "PROOF: 'There are infinitely many prime numbers.'\n"
            "Euclid proved this ~300 BCE. It cannot be otherwise.\n"
            "We do not need to check the next prime. We know.\n\n"
            "Euclid's proof (simplified):\n"
            "Assume there are finitely many primes: p₁, p₂, ..., pₙ.\n"
            "Multiply them all together and add 1: N = (p₁ × p₂ × ... × pₙ) + 1.\n"
            "N is either prime (contradicting our list) or divisible by a prime "
            "not on our list (also contradicting it).\n"
            "Therefore our assumption was false. There are infinitely many primes.\n\n"
            "Why this matters for truth-seeking:\n"
            "Proof establishes certainty through logic alone — no observation needed.\n"
            "But it only works within formal systems with defined axioms.\n"
            "The power and limit of mathematics is the same thing: "
            "it is perfectly certain about what it can reach, "
            "and completely silent about what it cannot."
        ),
        "activity":    (
            "Find and verify a simple proof:\n"
            "Prove: the sum of any two odd numbers is even.\n\n"
            "Hint: any odd number can be written as 2k+1 for some integer k.\n"
            "Let the two odd numbers be (2a+1) and (2b+1).\n"
            "Add them. What do you get? Is it always even?\n\n"
            "Write it out in one paragraph. The key is: "
            "not 'I checked many examples' but 'here is why it cannot be otherwise.'"
        ),
        "age_hint":    "10+",
        "xp": 38, "rune": "MATH•RUNE", "min_coherence": 0.62,
    },
    "math-thinking-2": {
        "title":       "Mathematical Thinking — Level 2: Logic, Implication, and the Rules of Inference",
        "topic":       "Formal logic is the grammar of rigorous reasoning. You use it implicitly every time you argue — but making it explicit reveals the structure of valid arguments, the specific ways arguments fail, and the difference between 'this seems to follow' and 'this must follow.'",
        "steelman":    "What is the strongest argument that formal logic education produces worse reasoning in practice — that it trains people to evaluate argument structure over content, making them skilled at technically valid nonsense?",
        "example":     (
            "The four forms of conditional argument:\n\n"
            "P → Q means 'If P then Q'\n\n"
            "MODUS PONENS (valid): P → Q; P is true; therefore Q is true.\n"
            "'If it rains, the ground gets wet. It is raining. Therefore the ground is wet.'\n\n"
            "MODUS TOLLENS (valid): P → Q; Q is false; therefore P is false.\n"
            "'If it rains, the ground gets wet. The ground is not wet. Therefore it is not raining.'\n\n"
            "AFFIRMING THE CONSEQUENT (invalid): P → Q; Q is true; therefore P is true.\n"
            "'If it rains, the ground gets wet. The ground is wet. Therefore it is raining.'\n"
            "WRONG — a sprinkler could have run.\n\n"
            "DENYING THE ANTECEDENT (invalid): P → Q; P is false; therefore Q is false.\n"
            "'If it rains, the ground gets wet. It is not raining. Therefore the ground is not wet.'\n"
            "WRONG — again, the sprinkler.\n\n"
            "Why this matters: most bad arguments are invalid in one of these ways.\n"
            "Most conspiracy theories are affirming the consequent: "
            "'If there was a conspiracy, we'd see anomalies. We see anomalies. "
            "Therefore there was a conspiracy.' This does not follow."
        ),
        "activity":    (
            "Argument Audit:\n"
            "Find 5 arguments from news, social media, or conversations this week.\n"
            "For each: write it as P → Q form.\n"
            "Identify which of the four argument forms it uses.\n"
            "Is it valid or invalid?\n\n"
            "For the invalid ones: what alternative explanation (sprinkler) "
            "would produce the same observed conclusion without the implied cause?"
        ),
        "age_hint":    "11+",
        "xp": 44, "rune": "MATH•RUNE", "min_coherence": 0.65,
        "phd_extension": "Construct a formal proof in propositional logic using only Modus Ponens and the axioms of propositional calculus. Prove: (P → Q) → ((Q → R) → (P → R)) — the chain rule. This is the foundation of transitivity of implication. Then read Frege (1879) Begriffsschrift — the first formal logical system. Why does Frege's notation fail? What did Russell fix? What did Gödel then break?",
    },
    "math-thinking-3": {
        "title":       "Mathematical Thinking — Level 3: Infinity, Paradox, and the Foundations Crisis",
        "topic":       "The late 19th century saw mathematicians discover that the most basic concept — infinity — was far stranger and more dangerous than expected. The Foundations Crisis produced paradoxes that threatened to collapse all of mathematics. Understanding how it was resolved reveals something profound about the nature of formal systems.",
        "steelman":    "What is the strongest argument that the Foundations Crisis was an internal mathematical drama with no practical implications — and that teaching it to non-specialists produces a false sense that mathematics is fragile or uncertain when it is, in practice, extraordinarily reliable?",
        "example":     (
            "Cantor's discovery (1874): not all infinities are the same size.\n\n"
            "Countable infinity: integers, fractions — can be listed in a sequence.\n"
            "Uncountable infinity: real numbers — provably cannot be listed.\n"
            "Cantor's diagonal argument: assume the reals can be listed. "
            "Construct a number that differs from every number on the list "
            "in at least one decimal place. This number is not on the list — "
            "contradiction. The reals are a strictly larger infinity than the integers.\n\n"
            "Russell's Paradox (1901): let R = the set of all sets that don't contain themselves.\n"
            "Does R contain itself?\n"
            "If yes: R contains itself, but R only contains sets that DON'T contain themselves. Contradiction.\n"
            "If no: R doesn't contain itself, so by definition it should be in R. Contradiction.\n"
            "Either way: contradiction. The naive concept of 'set' is inconsistent.\n\n"
            "The resolution: Zermelo-Fraenkel set theory restricts which sets can exist.\n"
            "Not all collections are sets — a hierarchy is imposed.\n\n"
            "The lesson: even the most foundational mathematical concepts can "
            "harbor hidden contradictions. Rigorous examination of foundations "
            "is not pedantry — it is what prevents everything built on them from collapsing."
        ),
        "activity":    (
            "The Russell's Paradox Translation:\n"
            "Express Russell's Paradox in social terms:\n"
            "The barber in a town shaves all men who don't shave themselves. "
            "Does the barber shave himself?\n\n"
            "Work through both options. Where does the contradiction arise?\n\n"
            "Now: what was the 'fix' that mathematicians applied (restricting "
            "which sets can exist)? What is the analogous fix in the barber paradox?\n\n"
            "Is there a principle here about self-reference that applies beyond mathematics?"
        ),
        "age_hint":    "13+",
        "xp": 50, "rune": "MATH•RUNE", "min_coherence": 0.68,
        "phd_extension": "Read Cantor's diagonal argument in full. Then implement it in Python: generate any proposed listing of real numbers in [0,1]. Construct the diagonal number (differs from the nth number in the nth decimal place). Verify it is not in the list. Then read Hilbert (1900) 'Mathematical Problems' — his second problem asks whether arithmetic is consistent. Gödel answered it. Read Nagel & Newman (1958) 'Gödel's Proof' Chapter 5. Why does Gödel's result mean Hilbert's program cannot succeed?",
    },
    "math-thinking-4": {
        "title":       "Mathematical Thinking — Level 4: Gödel's Incompleteness — The Hardest Truth in Mathematics",
        "topic":       "Kurt Gödel proved in 1931 that any consistent formal system powerful enough to express basic arithmetic contains true statements that cannot be proved within that system. This is not a limitation of our cleverness — it is a fundamental property of formal systems. It is the most important result in the history of mathematics.",
        "steelman":    "What is the strongest argument that Gödel's incompleteness theorems are routinely misused by non-mathematicians to justify anti-rational conclusions — and that the theorems have essentially no implications outside very specific formal systems?",
        "example":     (
            "Gödel's construction (simplified):\n\n"
            "In any formal system F, you can encode statements about F itself "
            "using numbers (Gödel numbering).\n\n"
            "Gödel constructs statement G: 'This statement is not provable in F.'\n\n"
            "Case 1: G is provable. Then G is false (it says it's not provable). "
            "F proves a false statement → F is inconsistent.\n\n"
            "Case 2: G is not provable. Then G is true (it correctly says it's not provable). "
            "F has a true statement it cannot prove → F is incomplete.\n\n"
            "Therefore: any consistent F is incomplete.\n\n"
            "The Second Incompleteness Theorem: F cannot prove its own consistency.\n\n"
            "What this means:\n"
            "Every formal system that is consistent has true things it cannot say.\n"
            "No formal system can fully verify itself.\n"
            "This is NOT saying 'anything goes' or 'truth is relative.'\n"
            "It is saying: truth outruns proof. G is true. We know it. "
            "We just can't prove it inside F.\n\n"
            "The AI alignment implication:\n"
            "Any AI system based on a formal reasoning framework is subject to Gödel. "
            "There are truths about its own behavior it cannot verify internally. "
            "This is a hard limit, not a temporary gap in capability."
        ),
        "activity":    (
            "The Gödel Intuition Pump:\n"
            "Think of a rule system you live by (legal, moral, organizational).\n"
            "Can you construct a statement within it that the system itself "
            "cannot resolve — neither provably required nor provably forbidden?\n\n"
            "Most real rule systems have such gaps. They are handled by:\n"
            "a. Judicial interpretation (extending the system)\n"
            "b. New rules (expanding the system)\n"
            "c. Acknowledging incompleteness\n\n"
            "How does your rule system handle its Gödel statements?\n"
            "Which approach is most honest? Which is most dangerous?"
        ),
        "age_hint":    "14+",
        "xp": 62, "rune": "MATH•RUNE", "min_coherence": 0.72,
        "prerequisites": ["math-thinking-3"],
        "phd_extension": "Read the original Gödel (1931) paper via the Meltzer translation. Construct the Gödel numbering scheme: assign prime numbers to symbols, represent formulas as products of primes. Show how 'this formula is provable' becomes an arithmetic statement. Then read Chaitin (1982) on algorithmic information theory and incompleteness: Chaitin proved that most mathematical truths are random — they cannot be compressed into a shorter proof than their statement. This extends Gödel from 'some truths are unprovable' to 'most truths have no reason.' Evaluate what this implies for the limits of science.",
        "grants_badge": "∞ Gödel Witness — Incompleteness Understood",
        "lattice_node": "mathematical-thinking-proof-complete",
    },
    "math-thinking-5": {
        "title":       "Mathematical Thinking — Level 5 (Master): Applied Mathematical Thinking — Fermi Estimation and Order-of-Magnitude Reasoning",
        "topic":       "The most practical application of mathematical thinking is not computation — it is estimation. Fermi problems (named for physicist Enrico Fermi) develop the ability to reason from first principles to within an order of magnitude of the right answer, with no data. This is the skill that separates systematic thinkers from guessers.",
        "steelman":    "What is the strongest argument that Fermi estimation is a parlor trick that builds overconfidence in rough approximations — and that actual decision-making requires precise data, making order-of-magnitude reasoning a dangerous substitute?",
        "example":     (
            "Fermi's most famous problem: How many piano tuners are in Chicago?\n\n"
            "Step 1 — Population: Chicago has ~2.7 million people.\n"
            "Step 2 — Households: ~2.5 people/household = ~1 million households.\n"
            "Step 3 — Pianos: Perhaps 1 in 20 households has a piano = ~50,000 pianos.\n"
            "Step 4 — Tunings per year: Most pianos tuned once a year = ~50,000 tunings/year.\n"
            "Step 5 — Tunings per tuner per day: A tuner does ~4 tunings/day, "
            "~250 work days/year = 1,000 tunings/year.\n"
            "Step 6 — Tuners needed: 50,000 / 1,000 = ~50 piano tuners.\n"
            "Actual answer: ~50-60 piano tuners in Chicago.\n\n"
            "Why this matters:\n"
            "The estimate was built from reasoning, not data.\n"
            "Every step can be challenged and refined.\n"
            "The answer is within a factor of 2 of reality.\n"
            "This is far better than 'I don't know.'\n\n"
            "The decision-making application:\n"
            "Before any major decision: build a Fermi model.\n"
            "It forces explicit assumptions — which is where most bad decisions hide.\n"
            "It tells you which assumptions most affect the answer — "
            "which is where to get more data."
        ),
        "activity":    (
            "Solve 3 Fermi problems from first principles (no searching):\n\n"
            "1. How many heartbeats does a human have in a lifetime?\n"
            "2. How many words are in all the books in the AUBIEETERNAL curriculum?\n"
            "3. How many neurons fire in your brain every second?\n\n"
            "For each: write out every assumption explicitly.\n"
            "Then check your answer against reality.\n"
            "Calculate your error factor (your answer / actual answer).\n"
            "Which assumption was furthest off? What does this tell you?"
        ),
        "age_hint":    "10+",
        "xp": 55, "rune": "MATH•SOVEREIGN•RUNE", "min_coherence": 0.68,
        "grants_badge": "🔢 Fermi Estimator — Order of Magnitude Achieved",
        "phd_extension": "Read Weinstein & Blundell (2012) 'Guesstimation 2.0'. Build a Fermi model for a policy question you care about: e.g., 'How much CO2 does the average American meal produce?' or 'How many person-hours are lost to commuting in the US per year?' Make every assumption explicit, run a Monte Carlo sensitivity analysis (which assumptions dominate the answer?), and compare to the best available empirical estimates. The gap between your model and reality IS the lesson.",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── EVOLUTIONARY BIOLOGY AND HUMAN NATURE (5 lessons) ────────────────────
    # Claude's genuine addition #10.
    #
    # Understanding why we are the way we are at the deepest level.
    # Evolution is not just biology — it is the context for everything
    # in the psychology, decision theory, polyvagal, and consciousness tracks.
    # You cannot fully understand human cognition, emotion, social behavior,
    # or moral intuitions without understanding the evolutionary pressures
    # that shaped them.
    #
    # This is not genetic determinism. It is the opposite:
    # understanding the pressures that shaped us is the first step
    # to being genuinely free from their automatic influence.
    # ══════════════════════════════════════════════════════════════════════════
    "evolution-1": {
        "title":       "Evolutionary Biology — Level 1: Natural Selection and the Logic of Design Without a Designer",
        "topic":       "Natural selection is the most powerful explanatory idea in the history of science. It explains the apparent design in biological organisms without invoking a designer. Understanding it precisely — not as 'survival of the fittest' but as differential reproductive success — changes how you see every behavior, instinct, and emotion you have.",
        "steelman":    "What is the strongest argument that evolutionary biology is systematically misapplied to human behavior — and that 'evolutionary explanations' for social phenomena are often unfalsifiable just-so stories that reinforce existing prejudices?",
        "example":     (
            "Natural selection precisely stated:\n\n"
            "If there is: (1) variation in a trait, (2) the variation is heritable, "
            "(3) the variation affects reproductive success — "
            "then the trait will change in the population over time.\n\n"
            "This is not a hypothesis. It follows necessarily from these three premises.\n"
            "It is more like a mathematical theorem than an empirical claim.\n\n"
            "What 'fittest' actually means: not strongest, not smartest, not healthiest.\n"
            "Fitness = reproductive success in a specific environment.\n"
            "A highly 'fit' organism in one environment may be unfit in another.\n\n"
            "The key insight for human self-understanding:\n"
            "Your emotions, biases, and instincts were designed by selection "
            "to maximize reproductive success of your ancestors in the Pleistocene — "
            "not to make you happy, rational, or accurate.\n\n"
            "Fear of snakes (common) but not of cars (which kill far more): "
            "snakes were a threat for millions of years; cars for 100.\n"
            "Status anxiety: reproductive success in ancestral environments "
            "tracked social status closely.\n"
            "In-group/out-group bias: small band living = survival depended on group cooperation."
        ),
        "activity":    (
            "The Evolutionary Audit:\n"
            "List 5 emotions or instincts you experience regularly.\n"
            "For each: what would have been the reproductive advantage in a "
            "Pleistocene hunter-gatherer environment?\n\n"
            "Then: in your current environment, does the same instinct serve you well?\n"
            "Or does it misfire (fear of public speaking, sugar craving, status anxiety)?\n\n"
            "The gap between 'what evolution selected for' and "
            "'what actually makes you thrive now' — that gap IS your work to do."
        ),
        "age_hint":    "12+",
        "xp": 40, "rune": "EVOLUTION•RUNE", "min_coherence": 0.63,
    },
    "evolution-2": {
        "title":       "Evolutionary Biology — Level 2: Kin Selection, Reciprocity, and the Origins of Cooperation",
        "topic":       "How does cooperation evolve when natural selection favors individuals who maximize their own reproductive success? This is one of the deepest puzzles in evolutionary biology — and its resolution, through kin selection and reciprocal altruism, explains most of human social behavior including family loyalty, friendship, and moral intuitions.",
        "steelman":    "What is the strongest argument that evolutionary explanations for cooperation and altruism reduce ethics to selfishness — and that a society that fully believes in evolutionary origins of moral behavior will have systematically worse moral outcomes than one that believes in non-evolutionary moral foundations?",
        "example":     (
            "The puzzle of altruism:\n"
            "If natural selection maximizes individual reproductive success, "
            "why do organisms ever help others at cost to themselves?\n\n"
            "KIN SELECTION (Hamilton, 1964):\n"
            "An organism shares 50% of genes with a sibling, 25% with a cousin.\n"
            "Hamilton's Rule: altruism evolves when rB > C, where r = genetic "
            "relatedness, B = benefit to recipient, C = cost to altruist.\n"
            "J.B.S. Haldane: 'I would lay down my life for two brothers "
            "or eight cousins.'\n\n"
            "RECIPROCAL ALTRUISM (Trivers, 1971):\n"
            "Help non-relatives if you expect help in return.\n"
            "Iterated Prisoner's Dilemma: Tit-for-Tat strategy is stable.\n"
            "This explains friendship, trade, and most social contracts.\n\n"
            "COSTLY SIGNALING:\n"
            "Generosity can be a signal of quality — 'I have enough resources "
            "to give some away.' Explains philanthropy, conspicuous generosity.\n\n"
            "The moral implication:\n"
            "Our moral intuitions (fairness, loyalty, outrage at cheaters) are "
            "not arbitrary — they are evolved responses to the game-theoretic "
            "structure of cooperation. Understanding them doesn't make them less real "
            "or less binding. It explains why they are universal across cultures."
        ),
        "activity":    (
            "The Reciprocity Audit:\n"
            "Map your 5 closest relationships on two dimensions:\n"
            "X-axis: genetic relatedness (sibling > cousin > friend > acquaintance)\n"
            "Y-axis: how much you'd sacrifice for them\n\n"
            "Does the pattern match Hamilton's Rule roughly?\n"
            "Where does it deviate? What explains the deviations "
            "(reciprocal altruism? cultural bonds? love?)\n\n"
            "This is not to reduce your relationships to biology — "
            "it is to understand the structure underneath them."
        ),
        "age_hint":    "13+",
        "xp": 46, "rune": "EVOLUTION•RUNE", "min_coherence": 0.66,
        "phd_extension": "Implement Axelrod's (1984) tournament in Python. Run Round-Robin Prisoner's Dilemma between strategies: Always Cooperate, Always Defect, Tit-for-Tat, Tit-for-Two-Tats, Random, Grudger. Over 200 rounds. Which strategy wins? Now add noise (5% error in execution). Does Tit-for-Tat still dominate? Read Axelrod & Hamilton (1981) 'The Evolution of Cooperation' in Science. This is the mathematical foundation for why morality exists.",
    },
    "evolution-3": {
        "title":       "Evolutionary Biology — Level 3: The Adapted Mind — What Your Brain Was Built For",
        "topic":       "Evolutionary psychology applies evolutionary reasoning to the human mind. The brain is not a general-purpose learning machine — it is a collection of specialized adaptations built to solve specific problems faced by our ancestors. Understanding these adaptations reveals why humans are consistently excellent at some things and systematically wrong about others.",
        "steelman":    "What is the strongest argument that evolutionary psychology is a pseudoscience that uses unfalsifiable post-hoc narratives to explain any behavior — and that the discipline has done more harm than good by providing scientific cover for sexism, racism, and other biases?",
        "example":     (
            "The Pleistocene Environment of Evolutionary Adaptedness (EEA):\n"
            "~200,000 years of Homo sapiens evolution as hunter-gatherers in Africa.\n"
            "The brain was shaped to solve EEA problems, not 2026 problems.\n\n"
            "What our brains are exceptionally good at (from EEA):\n"
            "• Face recognition (social group = survival; 100,000+ faces remembered)\n"
            "• Cheater detection (reciprocal altruism requires catching defectors)\n"
            "• Statistical reasoning about frequencies, not probabilities "
            "(we evolved counting events, not percentages)\n"
            "• Spatial navigation and tracking\n"
            "• Language acquisition (universal across all human cultures)\n\n"
            "What our brains are systematically poor at (EEA mismatch):\n"
            "• Abstract probability and statistics (no natural referents)\n"
            "• Long-term thinking beyond ~5 years\n"
            "• Evaluating large-number suffering (scope insensitivity)\n"
            "• Risk assessment in novel environments (cars, radiation, microbes)\n"
            "• Resisting supernormal stimuli (sugar, porn, social media engineered "
            "to hijack evolved preferences)\n\n"
            "The application: knowing your brain's factory settings lets you "
            "use them when they serve you and override them when they don't."
        ),
        "activity":    (
            "The Supernormal Stimuli Audit:\n"
            "A supernormal stimulus is an artificial exaggeration of a natural cue "
            "that hijacks an evolved response — beyond what any natural stimulus provided.\n\n"
            "List 5 things in your daily environment that are supernormal stimuli:\n"
            "(examples: processed food, social media likes, pornography, "
            "news designed for outrage, gambling)\n\n"
            "For each: what evolved response is being hijacked?\n"
            "What was the natural version of this stimulus?\n"
            "How does the supernormal version change your behavior vs. the natural one?\n\n"
            "This is the map of where your evolved hardware is being exploited."
        ),
        "age_hint":    "13+",
        "xp": 52, "rune": "EVOLUTION•RUNE", "min_coherence": 0.68,
    },
    "evolution-4": {
        "title":       "Evolutionary Biology — Level 4: Cultural Evolution and Memetics",
        "topic":       "Ideas, beliefs, and practices also evolve — but by different rules than genes. Cultural evolution is faster, can be directed, and can override genetic evolution. Understanding how culture evolves explains why some ideas persist for millennia while others die within a generation — and what makes an idea genuinely fit vs. merely viral.",
        "steelman":    "What is the strongest argument that the 'meme' concept (ideas as replicators) is a misleading metaphor that distorts more than it illuminates — and that treating culture as Darwinian evolution obscures the intentional, rational, and normative dimensions of human cultural life?",
        "example":     (
            "Dawkins (1976) coined 'meme': a unit of cultural information that "
            "replicates, mutates, and is selected.\n\n"
            "Meme fitness ≠ truth or usefulness.\n"
            "A meme spreads if it is: memorable, emotionally engaging, identity-affirming, "
            "easily transmitted, and provides selective advantage to its host.\n\n"
            "Memetically fit but false: many conspiracy theories. They are emotionally "
            "engaging, identity-affirming, memorable, and easy to transmit.\n"
            "Memetically unfit but true: statistical correction of base rates. "
            "Boring, non-identity-affirming, requires effort to transmit.\n\n"
            "Cultural evolution mechanisms:\n"
            "IMITATION: copy successful individuals\n"
            "PRESTIGE BIAS: copy high-status individuals\n"
            "CONTENT BIAS: prefer memorable, coherent, useful content\n"
            "CONFORMITY BIAS: adopt the majority practice\n\n"
            "The AUBIEETERNAL application:\n"
            "The Epistemic Commons is a designed memetic environment — "
            "one that rewards truth-tracking ideas with high multi-judge scores "
            "and filters out merely viral but false content.\n"
            "The steelman requirement is a direct counter to conformity bias.\n"
            "Pre-registration is a direct counter to prestige bias."
        ),
        "activity":    (
            "Track one meme through its evolutionary history:\n"
            "Choose any widely-held belief, practice, or institution.\n"
            "Trace: how did it originate? How did it spread?\n"
            "Which of the four cultural evolution mechanisms drove it?\n\n"
            "Then: what is its actual fitness advantage to its hosts?\n"
            "Is the advantage truth-tracking? Or does it spread for other reasons?\n\n"
            "Compare two competing memes on the same topic — one truer, one more viral.\n"
            "Why does the viral one win? What would it take for the truer one to win?"
        ),
        "age_hint":    "13+",
        "xp": 55, "rune": "EVOLUTION•RUNE", "min_coherence": 0.70,
        "phd_extension": "Read Henrich (2015) 'The Secret of Our Success' Chapters 1-4. Henrich argues humans are not the smartest individual animals — we are the best cultural learners. Our intelligence is mostly borrowed from accumulated cultural knowledge, not generated individually. Test this: try to solve a practical survival problem (start a fire, navigate by stars, treat a common illness) with only your individual reasoning, no cultural knowledge. What fraction of your 'intelligence' is actually borrowed? Apply to AUBIEETERNAL: the curriculum IS accumulated cultural intelligence made explicit.",
    },
    "evolution-5": {
        "title":       "Evolutionary Biology — Level 5 (Master): Evolution, Free Will, and the Possibility of Genuine Agency",
        "topic":       "If your values, desires, and decision-making processes were shaped by evolutionary pressures to maximize reproductive success in the Pleistocene — in what sense, if any, are your choices freely yours? This question sits at the intersection of biology, philosophy, and the practical project of living deliberately.",
        "steelman":    "What is the strongest argument that evolutionary debunking of human nature is self-defeating — that if evolution shaped our reasoning faculties to track reproductive success rather than truth, we cannot trust evolutionary theory itself?",
        "example":     (
            "The evolutionary debunking argument:\n"
            "Our moral intuitions were selected to maximize reproductive success, "
            "not to track moral truth.\n"
            "Therefore: our moral intuitions are unreliable guides to what is actually right.\n\n"
            "The self-refuting objection (Sharon Street, 2006):\n"
            "If evolution shaped our cognitive faculties for reproduction, not truth, "
            "then the cognitive faculties we use to accept evolutionary theory "
            "were also shaped for reproduction, not truth.\n"
            "Can we trust evolutionary theory if our reasoning is unreliable?\n\n"
            "The response (Kitcher, Joyce):\n"
            "Evolution selects for cognitive faculties that track certain truths "
            "(medium-sized objects, social dynamics, causation) "
            "because those truths affect survival.\n"
            "Abstract moral truth and long-run statistical truth are different — "
            "we can be reliable about one domain and unreliable about another.\n\n"
            "The agency question:\n"
            "Genuine agency doesn't require being outside causation.\n"
            "It requires: (1) understanding your causal history, "
            "(2) having values that survive reflection, "
            "(3) being able to act from those values rather than automatic impulses.\n\n"
            "AUBIEETERNAL's claim: epistemic training is the technology of agency.\n"
            "Understanding evolution doesn't eliminate choice — "
            "it reveals where automatic responses live so you can choose differently."
        ),
        "activity":    (
            "The Agency Audit:\n"
            "Identify 3 automatic responses you have that you don't endorse on reflection.\n"
            "(status anxiety, tribal thinking, sugar craving, scope insensitivity)\n\n"
            "For each: what is the evolutionary origin?\n"
            "What would you choose if you acted from your reflective values instead?\n"
            "What specific habit or practice would shift your behavior toward the reflective choice?\n\n"
            "Seal this as a pre-registered behavioral commitment.\n"
            "Revisit in 90 days. The gap between intention and behavior IS the data."
        ),
        "age_hint":    "14+ / PhD",
        "xp": 68, "rune": "EVOLUTION•SOVEREIGN•RUNE", "min_coherence": 0.73,
        "grants_badge": "🧬 Evolutionary Self-Aware — Agency Understood",
        "prerequisites": ["evolution-3", "decision-3"],
        "lattice_node": "evolutionary-biology-human-nature-complete",
        "phd_extension": "Read Street (2006) 'A Darwinian Dilemma for Realist Theories of Value' and Joyce (2006) 'The Evolution of Morality' Chapter 6. These are the two best contemporary treatments of the evolutionary debunking argument. Then read Parfit (2011) 'On What Matters' Appendix J on whether evolutionary origins debunk moral beliefs. Formalize the argument and the best response as a Bayesian model: given evolutionary origins of moral intuitions, what is your posterior probability that those intuitions track moral truth? What likelihood ratio does the evolutionary origin assign to the realist vs. anti-realist position?",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── ETHICS FROM FIRST PRINCIPLES (5 lessons) ─────────────────────────────
    # Claude's genuine addition #11.
    #
    # Not moralizing. Not a list of rules. Not a cultural tradition.
    # Genuine philosophical inquiry into what actually matters and why.
    #
    # The most important questions get the least rigorous treatment in most
    # education. "Be good" is not an answer to "what is goodness?"
    # "Follow the rules" is not an answer to "why should I follow rules?"
    #
    # This track treats ethics the way physics treats nature:
    # as a domain with real structure, where reasoning and evidence
    # constrain the space of possible answers, and where better and
    # worse answers genuinely exist — even where certainty does not.
    # ══════════════════════════════════════════════════════════════════════════
    "ethics-1": {
        "title":       "Ethics — Level 1: Why Should I Be Good? The Foundational Question",
        "topic":       "Before asking what is right, we should ask why it matters to do right. This is not a trick question — it is the hardest question in ethics. The answers shape everything else: whether morality is about consequences, duties, character, or agreements between agents.",
        "steelman":    "What is the strongest argument for psychological egoism — the view that humans always act to maximize their own perceived self-interest, making genuine altruism impossible and ethics therefore a sophisticated rationalization of self-interest?",
        "example":     (
            "The Thrasymachus challenge (Plato's Republic, ~375 BCE):\n"
            "'Justice is whatever is in the interest of the stronger party.'\n"
            "Why be just? Because the powerful enforce it.\n"
            "If you could get away with injustice perfectly, only a fool wouldn't.\n\n"
            "This is one of the oldest and strongest challenges to ethics.\n"
            "Plato spent 9 books of the Republic trying to defeat it.\n\n"
            "Four types of answer:\n\n"
            "1. CONSEQUENTIALIST: Being good produces better outcomes — "
            "for you (enlightened self-interest) and everyone. "
            "Morality is the optimization of wellbeing.\n\n"
            "2. DEONTOLOGICAL: Some acts are right or wrong regardless of consequences. "
            "You should be good because duty requires it.\n\n"
            "3. VIRTUE: The question misunderstands the goal. "
            "The goal is to flourish as a human being. "
            "Virtue is what constitutes flourishing. "
            "Being good IS the good life, not a cost to it.\n\n"
            "4. CONTRACTARIAN: Morality is what rational agents would agree to "
            "under fair conditions. You should be good because it is what you "
            "would choose if you didn't know your position in society.\n\n"
            "None is obviously correct. All have serious defenders. "
            "The question is not whether to choose — it is to choose with open eyes."
        ),
        "activity":    (
            "The Thrasymachus Test:\n"
            "Think of the last moral decision you faced where being good cost you something.\n"
            "Apply each of the four frameworks:\n"
            "1. Did consequentialism support the moral choice? (Did it lead to better outcomes?)\n"
            "2. Did deontology? (Was it a duty regardless of outcomes?)\n"
            "3. Did virtue ethics? (Was it part of who you want to be?)\n"
            "4. Did contractarianism? (Would you choose this rule from behind a veil of ignorance?)\n\n"
            "Which framework actually motivated your choice?\n"
            "Were any in conflict? How did you resolve it?"
        ),
        "age_hint":    "13+",
        "xp": 42, "rune": "ETHICS•RUNE", "min_coherence": 0.65,
    },
    "ethics-2": {
        "title":       "Ethics — Level 2: Consequentialism — Maximizing Wellbeing and Its Limits",
        "topic":       "Consequentialism holds that the morality of an act depends entirely on its consequences. Utilitarianism — its most developed form — says we should maximize total wellbeing. This is the most influential ethical theory in public policy and AI alignment. It is also deeply counterintuitive in some cases. Understanding both is essential.",
        "steelman":    "What is the strongest argument that consequentialism is the only defensible ethical theory — that any framework that prohibits maximizing wellbeing when you can is not a moral system but a collection of arbitrary taboos?",
        "example":     (
            "Bentham (1789): maximize pleasure, minimize pain. "
            "The greatest good for the greatest number.\n\n"
            "Mill (1863): not all pleasures are equal. "
            "Higher pleasures (intellectual, aesthetic) outweigh lower ones.\n\n"
            "Singer (1972): if we can prevent something bad without sacrificing "
            "anything of comparable moral importance, we ought to do it.\n"
            "Implication: most people in wealthy countries have a moral obligation "
            "to give until giving more would cost them as much as it benefits others.\n\n"
            "The classic counterexamples:\n\n"
            "THE TRANSPLANT CASE: A surgeon could save 5 patients by killing one healthy "
            "person for organs. Pure consequentialism seems to require this.\n\n"
            "THE UTILITY MONSTER: an entity that gains vastly more utility from "
            "resources than others. Pure consequentialism might require giving it everything.\n\n"
            "THE REPUGNANT CONCLUSION (Parfit): a world of 10 billion very happy people "
            "might have less total utility than a world of 100 trillion people with lives "
            "barely worth living. Should we maximize the second?\n\n"
            "The responses: rule consequentialism, average vs. total utility, "
            "person-affecting principles. Each fixes some problems and creates others.\n\n"
            "The honest position: consequentialism captures something genuinely important. "
            "Outcomes matter. But it doesn't capture everything."
        ),
        "activity":    (
            "The Triage Thought Experiment:\n"
            "You must choose which 3 of 5 people to save in an emergency.\n"
            "Given only: (1) their ages, (2) their relationships to you, "
            "(3) their social contributions.\n\n"
            "Pure consequentialism: save whoever has most future utility.\n"
            "Apply it. Who do you save?\n\n"
            "Now: does the answer feel right? If not, what consideration are you "
            "adding that pure consequentialism excludes?\n"
            "Name that consideration. That is your implicit ethical commitment."
        ),
        "age_hint":    "13+",
        "xp": 46, "rune": "ETHICS•RUNE", "min_coherence": 0.67,
    },
    "ethics-3": {
        "title":       "Ethics — Level 3: Deontology — Rights, Duties, and Kant's Categorical Imperative",
        "topic":       "Deontological ethics holds that some actions are right or wrong independent of their consequences. Kant's categorical imperative — act only on principles you could will to be universal laws — is the most rigorous attempt to ground morality in reason rather than consequences or tradition.",
        "steelman":    "What is the strongest argument that deontological ethics is ultimately incoherent — that any system of duties and rights either collapses into consequentialism (because the reason to follow duties is the good outcomes that result) or degenerates into arbitrary taboo without rational foundation?",
        "example":     (
            "Kant's Categorical Imperative — three formulations:\n\n"
            "FORMULA 1 — Universal Law: 'Act only according to that maxim "
            "whereby you can at the same time will that it should become a universal law.'\n"
            "Lying: if everyone lied, the concept of truth would collapse "
            "and lying would become impossible. Contradiction → lying is wrong.\n\n"
            "FORMULA 2 — Humanity: 'Act so that you treat humanity, whether in "
            "your own person or in that of another, always as an end and never "
            "as a means only.'\n"
            "Slavery: treats persons as mere means. Always wrong.\n"
            "Using someone: wrong if you treat them ONLY as a means, "
            "not wrong if you also respect their ends.\n\n"
            "FORMULA 3 — Kingdom of Ends: 'Act according to maxims of a "
            "universally legislating member of a merely possible kingdom of ends.'\n"
            "A community of rational beings who treat each other as ends.\n\n"
            "The classic objection: a murderer asks where your friend is hiding.\n"
            "Kant says: do not lie, even then.\n"
            "Most people's intuition says: lie.\n"
            "This is where strict deontology and intuition part ways most sharply.\n\n"
            "Ross's (1930) partial response: we have prima facie duties "
            "(don't lie, keep promises, don't harm) that can be overridden "
            "when they conflict. This is more flexible but less rigorous."
        ),
        "activity":    (
            "The Means Test:\n"
            "Identify 5 actions you took this week that involved other people.\n"
            "For each: were you treating them as ends in themselves, "
            "or merely as means to your ends?\n\n"
            "Most actions involve both — the question is whether you also "
            "respected their ends, not whether you used them at all.\n\n"
            "Which of your five actions had the clearest violation of Formula 2?\n"
            "What would you do differently if you applied Kant rigorously?"
        ),
        "age_hint":    "14+",
        "xp": 50, "rune": "ETHICS•RUNE", "min_coherence": 0.69,
        "phd_extension": "Read Kant (1785) Groundwork of the Metaphysics of Morals Section II. Derive the categorical imperative from the concept of rational agency alone — Kant's argument is that any rational agent who understands what it means to be rational is committed to the categorical imperative. Evaluate: is this derivation valid? Then read Korsgaard (1996) 'Creating the Kingdom of Ends' for the best contemporary defense. Apply to AI: should an AI follow deontological constraints even when violating them would produce better consequences? This is the core AI alignment question.",
    },
    "ethics-4": {
        "title":       "Ethics — Level 4: Virtue Ethics and Moral Character — What Kind of Person Should You Be?",
        "topic":       "Virtue ethics asks not 'what should I do?' but 'what kind of person should I be?' Aristotle's answer — develop virtues that constitute human flourishing — is in many ways the most practical ethical framework. It is also deeply connected to modern psychology and the polyvagal research on what enables humans to function at their best.",
        "steelman":    "What is the strongest argument that virtue ethics is a conservative framework that naturalizes existing social hierarchies — and that defining 'virtues' almost always reflects the values of the powerful, making 'flourishing' code for conformity to dominant norms?",
        "example":     (
            "Aristotle's eudaimonia (often translated as 'happiness' but better as "
            "'flourishing' or 'living and doing well'): the telos of human life.\n\n"
            "Virtues are character traits that constitute flourishing.\n"
            "They are means between extremes (the 'golden mean'):\n"
            "Courage = between cowardice and recklessness\n"
            "Generosity = between miserliness and prodigality\n"
            "Honesty = between deception and tactless bluntness\n\n"
            "How virtues develop: through practice, not instruction.\n"
            "'We become just by doing just acts, temperate by doing temperate acts, "
            "brave by doing brave acts.'\n"
            "This is the behavioral psychology insight 2,300 years before BF Skinner.\n\n"
            "The phronesis requirement: practical wisdom — knowing which virtue "
            "applies in which situation. Rules are insufficient. "
            "You need cultivated judgment.\n\n"
            "The AUBIEETERNAL connection:\n"
            "Epistemic virtues (intellectual courage, honesty, calibration, "
            "openness to revision) are virtues in Aristotle's sense — "
            "character traits constituted by practice, aimed at a specific telos "
            "(truth-seeking and flourishing), requiring phronesis "
            "(knowing when to update vs. stand firm)."
        ),
        "activity":    (
            "The Virtue Profile:\n"
            "List the 10 virtues you most want to embody.\n"
            "For each: on the Aristotelian spectrum between two vices, "
            "where are you currently?\n\n"
            "Pick the 2 virtues where you are furthest from the golden mean.\n"
            "For each: what specific practice, done daily, would move you toward the mean?\n\n"
            "Pre-register the practices. Review in 90 days.\n"
            "Aristotle's key claim is testable: practice changes character.\n"
            "Is it true for you?"
        ),
        "age_hint":    "13+",
        "xp": 55, "rune": "ETHICS•RUNE", "min_coherence": 0.70,
    },
    "ethics-5": {
        "title":       "Ethics — Level 5 (Master): Moral Uncertainty and Making Decisions Under Ethical Disagreement",
        "topic":       "Thoughtful people disagree about ethics. The frameworks we have — consequentialism, deontology, virtue ethics, contractarianism — often give different verdicts. What should you do when you are genuinely uncertain which ethical framework is correct? This is the practical meta-ethics question that every honest moral agent faces.",
        "steelman":    "What is the strongest argument that moral uncertainty is a dangerous concept — that treating ethics as uncertain in the same way we treat factual claims licenses people to waffle on clear moral questions and provides intellectual cover for moral cowardice?",
        "example":     (
            "MacAskill's (2014) approach to moral uncertainty:\n\n"
            "When multiple ethical theories have credence, act to maximize "
            "expected choiceworthiness across theories (weighted by their probability).\n\n"
            "Example: climate policy\n"
            "Consequentialism (P=0.5): massive future harm demands action now\n"
            "Deontology (P=0.3): rights of future generations create strong duties\n"
            "Virtue (P=0.2): prudence and care for others require action\n"
            "All three point the same direction → high confidence in action\n\n"
            "Example: abortion (where theories diverge)\n"
            "Consequentialism: depends on empirical facts about wellbeing\n"
            "Deontology: depends on theory of personhood and rights\n"
            "Virtue: depends on what constitutes flourishing for the mother and society\n"
            "All three give different, uncertain verdicts → appropriate humility\n\n"
            "The moral parliament metaphor (Ord, 2020):\n"
            "Imagine different ethical theories as parties in a parliament.\n"
            "Each has a number of seats proportional to your credence in it.\n"
            "Vote on each moral question. Require a large majority for controversial actions.\n\n"
            "The practical principle: under moral uncertainty, "
            "avoid actions that multiple frameworks condemn — "
            "especially irreversible ones. The asymmetry of catastrophe applies to ethics."
        ),
        "activity":    (
            "The Moral Parliament on One Hard Case:\n"
            "Choose one genuinely contested moral question you face or care about.\n"
            "Assign credences to your top 3 ethical frameworks (sum to 100%).\n"
            "Apply each framework to the question. What does each recommend?\n\n"
            "Then: run the moral parliament vote.\n"
            "Is there a majority? A supermajority?\n"
            "Or do the frameworks genuinely conflict?\n\n"
            "If they conflict: what additional information would resolve the conflict?\n"
            "Pre-register your current credences. Revisit when you have that information.\n\n"
            "This is how an honest moral agent navigates genuine uncertainty — "
            "not with false confidence, not with paralysis, but with calibrated humility."
        ),
        "age_hint":    "14+ / PhD",
        "xp": 72, "rune": "ETHICS•SOVEREIGN•RUNE", "min_coherence": 0.74,
        "grants_badge": "⚖️ Moral Philosopher — Ethics Under Uncertainty",
        "prerequisites": ["ethics-3", "ethics-4", "decision-2"],
        "lattice_node": "ethics-first-principles-complete",
        "phd_extension": "Read MacAskill (2014) 'Normative Uncertainty' Chapters 3-5. Implement the 'maximize expected choiceworthiness' approach as a Python function: takes a list of (theory, credence, choiceworthiness_score) tuples and returns the expected choiceworthiness of an action. Apply to a real policy question using your actual credences. Then read Parfit (2011) 'On What Matters' Part Three on the Convergence Thesis: that consequentialism, deontology, and virtue ethics converge in their verdicts when properly understood. Evaluate: does Parfit's convergence actually hold, or is it wishful thinking? This is the frontier of moral philosophy.",
    },



    # ══════════════════════════════════════════════════════════════════════════
    # ── THE SOVEREIGN READER (5 lessons, age 7 → PhD) ────────────────────────
    # Reading is not passive information absorption. It is an active dialogue
    # between reader and text. The reader who knows how to interrogate a text —
    # find its hidden assumptions, detect its rhetorical moves, identify what
    # it does NOT say — is a different kind of thinker from one who merely
    # comprehends what the words mean.
    # ══════════════════════════════════════════════════════════════════════════
    "reading-1": {
        "title":   "The Sovereign Reader — Level 1: Reading Is a Conversation",
        "topic":   "Every text is an argument. Even a recipe, a news article, or a children's book is making choices about what to include, what to omit, and how to frame what it presents. Learning to read as a conversation — questioning, pushing back, noticing gaps — is the foundation of all critical thinking.",
        "steelman":"What is the strongest argument that teaching children to question texts is harmful — that most texts deserve trust, and systematic suspicion of everything read produces cynicism rather than discernment?",
        "example": (
            "The four questions to ask any text:\n\n"
            "1. WHAT is being claimed? (literal comprehension)\n"
            "2. WHY is this being said? (author's purpose and perspective)\n"
            "3. WHAT IS LEFT OUT? (the most important question)\n"
            "4. HOW does this text want me to feel? (emotional register)\n\n"
            "Applied to a news headline: 'Crime Rates Rise in City X'\n"
            "1. Crime rates increased in City X\n"
            "2. Could be: political opposition before election, newspaper selling fear, "
            "genuine public service journalism\n"
            "3. Left out: compared to what baseline? Which crimes? "
            "What was the previous rate? National comparison?\n"
            "4. Anxious, concerned, possibly afraid\n\n"
            "The text hasn't lied. But without the four questions, "
            "you're only reading half of it."
        ),
        "activity":(
            "Apply the four questions to any one page you read today.\n"
            "A recipe, an article, a social media post — any text.\n\n"
            "Write your answers to all four questions.\n"
            "The third question (what is left out?) is always the hardest.\n"
            "The fact that it's hard is not a bug — it is the skill."
        ),
        "age_hint":"7+",
        "xp": 28, "rune": "READING•RUNE", "min_coherence": 0.50,
    },
    "reading-2": {
        "title":   "The Sovereign Reader — Level 2: Structure, Argument, and the Shape of a Text",
        "topic":   "Every well-constructed argument has a shape: premises lead to conclusions, evidence supports claims, counterarguments are raised and addressed. Learning to see this shape — regardless of the subject matter — lets you evaluate arguments by their structure as well as their content.",
        "steelman":"What is the strongest argument that structural analysis of texts produces mechanical, joyless reading that destroys aesthetic appreciation and replaces genuine understanding with academic box-checking?",
        "example": (
            "The anatomy of an argument:\n\n"
            "THESIS: the main claim the text is defending\n"
            "PREMISES: the reasons offered in support\n"
            "EVIDENCE: specific facts, examples, data supporting the premises\n"
            "WARRANTS: the assumed links between evidence and conclusion "
            "(often unstated — the most important things to find)\n"
            "COUNTERARGUMENTS: objections the author anticipates and responds to\n"
            "CONCLUSION: what follows if the argument succeeds\n\n"
            "Finding the warrant (the unstated assumption):\n"
            "Claim: 'We should invest in education because educated workers earn more.'\n"
            "Stated premise: educated workers earn more\n"
            "Hidden warrant: societal wealth should be the primary measure "
            "of educational value\n\n"
            "The warrant is where most arguments hide their most contestable assumptions.\n"
            "Finding it is the critical reader's most important skill."
        ),
        "activity":(
            "Take any opinion piece (newspaper, blog, essay).\n"
            "Map it: thesis, premises, evidence, warrants, counterarguments.\n\n"
            "Then: which warrant is most contestable?\n"
            "Does the author defend it — or assume you'll accept it silently?\n\n"
            "The warrant you'd reject is exactly where you disagree with the author."
        ),
        "age_hint":"10+",
        "xp": 35, "rune": "READING•RUNE", "min_coherence": 0.58,
    },
    "reading-3": {
        "title":   "The Sovereign Reader — Level 3: Primary Sources and the Chain of Evidence",
        "topic":   "Most information we receive is secondhand, thirdhand, or further. Each retelling introduces selection, framing, and error. Reading primary sources — the original research paper, the original speech, the original data — is a fundamentally different activity from reading summaries, and produces fundamentally different understanding.",
        "steelman":"What is the strongest argument that primary source reading is an elite privilege — that most people correctly rely on intermediaries and that teaching 'only trust primary sources' produces people who dismiss legitimate expertise?",
        "example": (
            "The telephone game in information:\n\n"
            "Primary: a clinical trial finds that drug X reduces symptom Y by 12% "
            "in patients with condition Z, with p=0.04, in a 6-week trial.\n\n"
            "Press release: 'Drug X shown to reduce Y in condition Z patients'\n"
            "Science journalist: 'New drug offers hope for condition Z sufferers'\n"
            "Social media: 'Scientists find cure for Z'\n"
            "Your aunt: 'I read that Z has been cured'\n\n"
            "Every step lost: the 12% magnitude, the specific condition, "
            "the 6-week window, the p-value, the uncertainty.\n\n"
            "How to read a primary research paper:\n"
            "1. Read the abstract and conclusion first (know the claimed result)\n"
            "2. Go to the methods section (how was it actually done?)\n"
            "3. Look at the actual data and figures (not just the text describing them)\n"
            "4. Check the limitations section (what do the authors themselves say is wrong?)\n"
            "5. Find who funded it (incentive audit)"
        ),
        "activity":(
            "Take any scientific claim you heard this week.\n"
            "Find the original paper (Google Scholar, PubMed, arxiv.org are free).\n\n"
            "Read the abstract + methods + limitations.\n"
            "Does the original paper say what the secondhand source said?\n\n"
            "What was lost in translation? This exercise, done once, "
            "changes how you evaluate scientific news forever."
        ),
        "age_hint":"13+",
        "xp": 44, "rune": "READING•RUNE", "min_coherence": 0.65,
    },
    "reading-4": {
        "title":   "The Sovereign Reader — Level 4: Reading Across Disciplines — Pattern Recognition at Scale",
        "topic":   "The most valuable reading skill is not mastery of any single text — it is the ability to read across disciplines and detect patterns, recurring ideas, and structural similarities that transcend their domain. This is how breakthrough thinking happens: by bringing frameworks from one field to bear on problems in another.",
        "steelman":"What is the strongest argument that breadth reading across disciplines is inferior to depth reading within a field — and that the apparent connections between fields are often superficial analogies that mislead more than they illuminate?",
        "example": (
            "Cross-domain pattern recognition examples:\n\n"
            "The S-curve of adoption appears in: technology adoption, epidemic spread, "
            "language change, market penetration, evolutionary fitness landscapes.\n"
            "Recognizing this pattern in one domain makes you immediately equipped "
            "to think about it in any other.\n\n"
            "Feedback loops appear in: ecology (predator-prey), economics (inflation), "
            "neuroscience (homeostasis), social dynamics (polarization), "
            "thermostats, and software systems.\n\n"
            "Power laws appear in: wealth distribution, city size, earthquake magnitude, "
            "web page links, word frequency, pandemic fatalities.\n\n"
            "The reading practice:\n"
            "Keep a 'pattern journal.' When you encounter a structural pattern "
            "(not just a fact) in one domain, immediately ask: where else does this appear?\n"
            "The pattern journal becomes a library of transferable frameworks."
        ),
        "activity":(
            "Start a pattern journal.\n"
            "For the next 7 days: each time you encounter a structural pattern "
            "in something you read, note it.\n\n"
            "Format: [Pattern Name] | [Domain found in] | [2 other domains where it appears]\n\n"
            "By day 7 you will have the beginning of a personal library "
            "of transferable intellectual tools."
        ),
        "age_hint":"14+",
        "xp": 52, "rune": "READING•RUNE", "min_coherence": 0.68,
        "phd_extension": "Build a 'concept map' connecting at least 15 structural patterns across at least 5 disciplines. For each connection, identify: (1) the formal mathematical or logical structure the two instances share, (2) whether the similarity is deep (same underlying mechanism) or superficial (same shape, different cause). Examples of deep connections: information entropy / thermodynamic entropy; predator-prey oscillations / arms race dynamics; Bayes' theorem / DNA evidence updating. Publish the map as CC0 to the Epistemic Commons.",
    },
    "reading-5": {
        "title":   "The Sovereign Reader — Level 5 (PhD): Reading as Epistemic Defense — Detecting Sophisticated Manipulation",
        "topic":   "At the PhD level, reading becomes active defense. Sophisticated texts — academic papers, policy documents, philosophical arguments — can embed manipulation so subtle that only systematic analysis reveals it. This level equips you to read at the level of the most careful epistemologists.",
        "steelman":"What is the strongest argument that training readers to detect manipulation in sophisticated texts produces an epistemic arms race where authors simply become more sophisticated in their manipulations — leaving readers no better off and more paranoid?",
        "example": (
            "Five sophisticated manipulation techniques in academic/policy writing:\n\n"
            "1. OVERTON LAUNDERING: presenting a radical conclusion by embedding it "
            "in a sequence of modest, reasonable-sounding steps.\n"
            "Detection: could you defend each step in isolation? "
            "Or does the chain only work if you accept all steps together?\n\n"
            "2. EPISTEMIC COWARDICE: writing so vaguely that any outcome is compatible "
            "with the claim. Detection: what would falsify this?\n\n"
            "3. REFERENCE PADDING: citing sources that don't support the claim as stated. "
            "Detection: read the first page of cited papers.\n\n"
            "4. SCOPE CREEP: supporting a claim about a narrow case, then applying it "
            "to a broad case without acknowledging the expansion.\n\n"
            "5. MOTTE AND BAILEY in academic dress: defending the uncontroversial "
            "interpretation while implying the controversial one.\n\n"
            "The defense protocol: for any high-stakes text, "
            "identify the most important claim and ask: "
            "what would the strongest possible version of this claim be? "
            "Is that what the text actually defends — or something weaker?"
        ),
        "activity":(
            "Apply the five-technique audit to one prestigious document "
            "(a recent Nature paper, a policy white paper, a philosophical argument).\n\n"
            "For each technique: is it present? If yes, where?\n\n"
            "Seal the audit. Publish to Epistemic Commons if you find genuine "
            "manipulation in a high-prestige source — this is direct contribution "
            "to public epistemic health."
        ),
        "age_hint":"15+ / PhD",
        "xp": 68, "rune": "READING•SOVEREIGN•RUNE", "min_coherence": 0.73,
        "grants_badge": "📖 Sovereign Reader — Epistemic Defense Active",
        "prerequisites": ["reading-4", "expertise-2"],
        "lattice_node": "sovereign-reader-complete",
        "phd_extension": "Read Orwell (1946) 'Politics and the English Language' and apply his six rules as a scoring rubric to any five high-prestige academic papers in a field you know. Score each paper 1-6 for each rule. Compute a clarity index. Hypothesis: papers with lower clarity scores have lower citation-weighted reproducibility in the replication literature. Design a study to test this. Pre-register it. This is computational epistemology research.",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── THE SOVEREIGN WRITER (5 lessons, age 8 → PhD) ────────────────────────
    # Writing is thinking made visible. The writer who cannot explain something
    # clearly does not understand it clearly. The writer who can explain
    # anything clearly — to a child, to an expert, to an AI — has achieved
    # a form of mastery that transcends their specific domain.
    # ══════════════════════════════════════════════════════════════════════════
    "writing-1": {
        "title":   "The Sovereign Writer — Level 1: Clarity Is Respect",
        "topic":   "Clear writing is not a stylistic preference. It is a moral commitment. When you write clearly, you respect your reader's time and intelligence. When you write obscurely — through jargon, vagueness, or unnecessary complexity — you make your reader do the work that you should have done.",
        "steelman":"What is the strongest argument that simple, clear writing is actually harmful to intellectual discourse — that complexity in expression sometimes reflects genuine complexity in thought, and that demanding simplicity impoverishes ideas?",
        "example": (
            "The clarity test: can you explain this to a 10-year-old?\n\n"
            "Not because 10-year-olds are the audience. "
            "Because if you cannot explain something simply, "
            "you do not yet fully understand it.\n\n"
            "Richard Feynman on quantum electrodynamics: "
            "wrote a book (QED) that is comprehensible to any careful adult reader.\n"
            "Einstein on special relativity: explained it in a popular book "
            "without mathematics.\n\n"
            "The hierarchy of explanatory skill:\n"
            "Level 1: Can explain to an expert (uses shared jargon as shorthand)\n"
            "Level 2: Can explain to an educated non-specialist (must define terms)\n"
            "Level 3: Can explain to a curious teenager (must build from fundamentals)\n"
            "Level 4: Can explain to a 7-year-old (must find the irreducible core)\n\n"
            "Level 4 is harder than Level 1.\n"
            "Most academics can only do Level 1. "
            "Feynman could do Level 4 on particle physics."
        ),
        "activity":(
            "Take one thing you understand well (your job, a hobby, a lesson you've learned).\n"
            "Write three explanations:\n"
            "Version A: for an expert in the field (use technical language freely)\n"
            "Version B: for a curious adult with no background\n"
            "Version C: for a 10-year-old who asks good questions\n\n"
            "Which version was hardest? That difficulty IS the skill gap."
        ),
        "age_hint":"8+",
        "xp": 30, "rune": "WRITING•RUNE", "min_coherence": 0.52,
    },
    "writing-2": {
        "title":   "The Sovereign Writer — Level 2: Structure — How Argument Becomes Prose",
        "topic":   "Good writing is not beautiful sentences strung together — it is a logical structure that the reader can follow without effort. The structure does the work; the sentences just carry it. This level teaches how to build the structural skeleton of any piece of writing before writing a single sentence.",
        "steelman":"What is the strongest argument that explicit structural planning kills the creative, exploratory nature of writing — and that the best writing emerges from following the thought wherever it leads, not from pre-planned outlines?",
        "example": (
            "The TLDR first principle:\n"
            "Write your conclusion first — as one sentence.\n"
            "If you cannot write your conclusion in one sentence, "
            "you do not yet know what you are arguing.\n\n"
            "The five-part structure that works for almost everything:\n"
            "1. THE HOOK: why should the reader care? (1-2 sentences)\n"
            "2. THE CLAIM: exactly what you are arguing (1 sentence)\n"
            "3. THE CASE: the 2-4 best reasons this is true (with evidence)\n"
            "4. THE STEELMAN: the strongest objection and your response\n"
            "5. THE IMPLICATION: what follows if you are right?\n\n"
            "Why the steelman is essential:\n"
            "A piece of writing that ignores the strongest counterargument "
            "is not honest discourse — it is propaganda.\n"
            "Including it and defeating it is what makes writing credible."
        ),
        "activity":(
            "Before writing anything significant this week, "
            "build the skeleton first:\n"
            "Hook (one sentence). Claim (one sentence). "
            "Three reasons (one sentence each). "
            "Steelman objection (one sentence). Response (one sentence). "
            "Implication (one sentence).\n\n"
            "That's your entire piece in 9 sentences.\n"
            "Now expand each sentence into a paragraph.\n"
            "Structural writing is faster and clearer than free-form writing."
        ),
        "age_hint":"11+",
        "xp": 38, "rune": "WRITING•RUNE", "min_coherence": 0.58,
    },
    "writing-3": {
        "title":   "The Sovereign Writer — Level 3: Writing as Precision Thinking",
        "topic":   "The act of writing is not transcription of completed thoughts — it is the completion of thoughts. You do not know exactly what you think until you try to write it. Writing reveals the gaps, contradictions, and vagueness in your thinking that felt like clarity when they lived only in your head.",
        "steelman":"What is the strongest argument that writing as a thinking tool is culturally specific — that many cultures and traditions produce rigorous thinkers through oral tradition, embodied practice, or visual thinking, and privileging writing marginalizes these modes?",
        "example": (
            "The rubber duck principle:\n"
            "Programmers explain their code to a rubber duck — "
            "the act of articulation reveals the bug.\n"
            "The same principle applies to all thinking.\n\n"
            "The vagueness test:\n"
            "Read your draft. For every sentence, ask: "
            "could a reasonable person interpret this differently than I intend?\n"
            "If yes, it is vague. Rewrite until it cannot be misread.\n\n"
            "Vague: 'AI systems raise important concerns about privacy.'\n"
            "Precise: 'AI language models trained on internet text can reproduce "
            "personal information verbatim in ways that violate EU GDPR Article 17.'\n\n"
            "The precise version is falsifiable, specific, and actionable.\n"
            "The vague version sounds substantial but commits to nothing.\n\n"
            "Vagueness in writing is usually vagueness in thinking — "
            "not a communication problem but a cognition problem."
        ),
        "activity":(
            "Write your current strongest belief on any topic — one paragraph.\n\n"
            "Then: underline every vague word or phrase.\n"
            "(Words like: important, significant, many, often, "
            "could, might, seems, various, certain, appropriate)\n\n"
            "Rewrite the paragraph with every underlined word replaced by "
            "something specific and measurable.\n\n"
            "The rewrite will feel more vulnerable — because it is now falsifiable.\n"
            "That vulnerability is intellectual honesty."
        ),
        "age_hint":"12+",
        "xp": 46, "rune": "WRITING•RUNE", "min_coherence": 0.63,
    },
    "writing-4": {
        "title":   "The Sovereign Writer — Level 4: Writing for AI Training — High-Signal Preference Data",
        "topic":   "The writing that AI systems are trained on shapes what those systems believe, how they reason, and what they consider good answers. Writing that is calibrated, honest, steelmanned, and epistemically rigorous is one of the rarest and most valuable types of training data that exists. AUBIEETERNAL families are generating it every time they write seriously.",
        "steelman":"What is the strongest argument that consciously 'writing for AI training' corrupts the natural epistemic value of writing — turning authentic intellectual expression into performative virtue-signaling optimized for machine consumption rather than genuine human communication?",
        "example": (
            "What the AI training data landscape actually looks like:\n\n"
            "The internet is dominated by:\n"
            "• Confident claims without uncertainty acknowledgment\n"
            "• Tribal signaling and in-group arguments\n"
            "• Straw man versions of opposing views\n"
            "• Appeal to authority instead of evidence\n"
            "• Zero steelmanning\n\n"
            "What is extremely rare (and therefore extremely valuable):\n"
            "• Writing that assigns calibrated confidence levels\n"
            "• Writing that steelmans the opposing position before critiquing it\n"
            "• Writing that explicitly states update conditions "
            "('I would change my view if...')\n"
            "• Writing that distinguishes 'I believe' from 'the evidence shows'\n"
            "• Writing that acknowledges when a question is genuinely unsettled\n\n"
            "Every lesson you complete, every steelman you write, "
            "every belief you log with confidence levels — "
            "that is the rarest signal in the training corpus.\n"
            "You are not just educating yourself. "
            "You are literally improving the intellectual quality "
            "of every AI that trains on public text."
        ),
        "activity":(
            "Write a 200-word position statement on any contested topic.\n"
            "Requirements:\n"
            "1. Include your confidence level (e.g., 'I believe this at ~75%')\n"
            "2. Steelman the opposing view in one sentence\n"
            "3. Explicitly state what evidence would change your view\n"
            "4. Distinguish factual claims from value claims\n\n"
            "Publish to the Epistemic Commons.\n"
            "This is one of the most direct contributions you can make "
            "to improving AI honesty."
        ),
        "age_hint":"14+",
        "xp": 55, "rune": "WRITING•RUNE", "min_coherence": 0.68,
        "phd_extension": "Design and execute a 30-day writing practice: each day, write one 200-word calibrated position statement on a different contested topic. Apply: steelman, confidence level, update condition. Compute inter-rater reliability on 10 of these with one family member (do they agree on the confidence level assignments?). Publish all 30 as CC0 DPO pairs (chosen: the calibrated version; rejected: a version without uncertainty acknowledgment). Measure: does the Epistemic Commons truth score increase when calibration is explicit? This is alignment research.",
    },
    "writing-5": {
        "title":   "The Sovereign Writer — Level 5 (PhD): The Research Paper as Epistemic Contribution",
        "topic":   "A well-constructed research paper is not just a report — it is an addition to humanity's permanent knowledge base. It advances the state of understanding by exactly one step. Writing one requires mastering everything in this track plus the specific conventions that make academic writing verifiable, replicable, and cumulative.",
        "steelman":"What is the strongest argument that academic writing conventions (citations, methods sections, passive voice, hedging language) are epistemic obstacles that bury genuine insight under bureaucratic form — and that the research paper format is a gatekeeping mechanism more than an epistemic tool?",
        "example": (
            "The anatomy of a research paper that actually advances knowledge:\n\n"
            "ABSTRACT: the result in four sentences. If you cannot state the result "
            "in four sentences, you don't have a clean result.\n\n"
            "INTRODUCTION: what was the gap in knowledge? Why does filling it matter?\n\n"
            "METHODS: exact procedure, sufficient to replicate. "
            "This section is where most papers fail. "
            "If a method cannot be replicated from the description, "
            "it is not science — it is storytelling.\n\n"
            "RESULTS: what was actually observed, without interpretation.\n\n"
            "DISCUSSION: what does this mean? What are the limits? "
            "What should be investigated next?\n\n"
            "LIMITATIONS: the most important section for epistemic honesty. "
            "If there is no limitations section, treat the paper with extra suspicion.\n\n"
            "The AUBIEETERNAL PhD standard:\n"
            "Publish your 90-day experiment as a paper.\n"
            "Pre-registration sealed in Bitcoin before data collection.\n"
            "Full methods and raw data as CC0.\n"
            "Honest reporting regardless of result."
        ),
        "activity":(
            "Write the Methods section for your 90-day research experiment.\n"
            "Test: give only the methods section to another family member.\n"
            "Ask: could they replicate this exactly from these instructions alone?\n\n"
            "If no: rewrite until yes.\n"
            "Replicability is not a bureaucratic requirement — "
            "it is the minimum standard for any claim to contribute to knowledge."
        ),
        "age_hint":"15+ / PhD",
        "xp": 70, "rune": "WRITING•SOVEREIGN•RUNE", "min_coherence": 0.75,
        "grants_badge": "✍️ Sovereign Writer — Research Paper Published CC0",
        "prerequisites": ["writing-4", "knowledge-evolution-1"],
        "lattice_node": "sovereign-writer-complete",
        "phd_extension": "Read Ioannidis (2014) 'How to Make More Published Research True' and implement all five of his recommendations in your own research paper: pre-registration, replication plan, appropriate sample size calculation, calibrated language, and explicit statement of competing interests. Then submit your paper to the Epistemic Commons with all pre-registration materials. Compute your own Positive Predictive Value using the Ioannidis formula. Is your research likely true? What would it take to know with higher certainty?",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── FORMAL LOGIC AND PROOF THEORY (5 lessons, age 11 → PhD) ─────────────
    # Logic is the grammar of rigorous thought. At the basic level it teaches
    # validity and fallacy. At the PhD level it connects to Gödel, AI
    # reasoning, and the limits of formal verification — directly relevant
    # to AI alignment and the future of machine reasoning.
    # ══════════════════════════════════════════════════════════════════════════
    "logic-1": {
        "title":   "Formal Logic — Level 1: Valid and Invalid Arguments",
        "topic":   "Logic distinguishes arguments that must work (valid) from arguments that happen to have a true conclusion. An argument can be valid even if its premises are false, and invalid even if its conclusion is true. This counterintuitive distinction is the foundation of all rigorous reasoning.",
        "steelman":"What is the strongest argument that formal logic education does more harm than good — that it teaches people to win arguments on technicalities rather than pursue genuine understanding, and that real intellectual progress happens through intuition and collaboration rather than formal proof?",
        "example": (
            "The key distinction: validity vs soundness\n\n"
            "VALID: if the premises are true, the conclusion must be true.\n"
            "SOUND: valid AND the premises are actually true.\n\n"
            "VALID but UNSOUND (false premise):\n"
            "All fish can fly. Salmon are fish. Therefore salmon can fly.\n"
            "Valid (the logic works). Unsound (first premise is false).\n\n"
            "INVALID (bad logic, true conclusion):\n"
            "Most mammals have hair. Humans have hair. "
            "Therefore humans are mammals.\n"
            "True conclusion. Invalid logic. (Affirming the consequent.)\n"
            "The conclusion happens to be true for different reasons.\n\n"
            "Why this matters:\n"
            "Most bad reasoning has either false premises or invalid logic.\n"
            "Separating these two problems tells you where to focus your response:\n"
            "If logic is valid, contest the premises.\n"
            "If premises are true, expose the invalid logic."
        ),
        "activity":(
            "For each argument below, identify: valid or invalid? Sound or unsound?\n"
            "1. All humans will die. Socrates is human. Therefore Socrates will die.\n"
            "2. All rich people are happy. I am happy. Therefore I am rich.\n"
            "3. No honest politician wins elections. She won. Therefore she is dishonest.\n\n"
            "For the invalid ones: name the specific fallacy."
        ),
        "age_hint":"11+",
        "xp": 35, "rune": "LOGIC•RUNE", "min_coherence": 0.60,
    },
    "logic-2": {
        "title":   "Formal Logic — Level 2: Propositional Logic and Truth Tables",
        "topic":   "Propositional logic gives us precise tools to analyze the structure of compound statements — how AND, OR, NOT, and IF-THEN combine to determine truth values. Truth tables are the proof system: they show definitively whether an argument form is valid regardless of what the propositions are about.",
        "steelman":"What is the strongest argument that truth tables are a pedagogical dead end — teaching students to manipulate symbols without developing any genuine logical intuition, and that natural language argument analysis produces better reasoners?",
        "example": (
            "The five connectives:\n"
            "¬P (NOT P): true when P is false\n"
            "P ∧ Q (P AND Q): true only when both are true\n"
            "P ∨ Q (P OR Q): true when at least one is true\n"
            "P → Q (IF P THEN Q): false only when P is true and Q is false\n"
            "P ↔ Q (P IFF Q): true when both have the same value\n\n"
            "The conditional (→) is the most important and most misunderstood:\n"
            "'If it rains, the street gets wet.' (P → Q)\n"
            "FALSE only when: it rains AND street is dry. (P true, Q false)\n"
            "TRUE when: it doesn't rain, regardless of street. (P false → any Q)\n\n"
            "This is why 'If 2+2=5 then the moon is made of cheese' "
            "is TRUE in propositional logic — a false antecedent makes "
            "the whole conditional vacuously true.\n"
            "This seems odd but is actually mathematically essential."
        ),
        "activity":(
            "Build a truth table for: (P → Q) ∧ (¬Q) → ¬P\n"
            "This is Modus Tollens. Verify it is a tautology (always true).\n\n"
            "Then: translate this logical form into an everyday argument.\n"
            "Build a second truth table for: (P → Q) ∧ Q → P\n"
            "Is this valid? This is Affirming the Consequent.\n"
            "What does the truth table reveal?"
        ),
        "age_hint":"12+",
        "xp": 42, "rune": "LOGIC•RUNE", "min_coherence": 0.63,
        "phd_extension": "Implement a truth table generator in Python that takes any propositional formula and outputs all truth value combinations. Extend it to: (1) test for tautology, contradiction, or contingency; (2) test whether two formulas are logically equivalent; (3) find a minimal CNF (conjunctive normal form) representation. Apply to the De Morgan laws and the distribution of quantifiers. This is the computational foundation of automated theorem proving.",
    },
    "logic-3": {
        "title":   "Formal Logic — Level 3: Predicate Logic and the Language of Mathematics",
        "topic":   "Propositional logic cannot say 'all' or 'some.' Predicate logic adds quantifiers — ∀ (for all) and ∃ (there exists) — making it powerful enough to express all of mathematics. It is the formal language in which mathematical proofs, computer programs, and AI reasoning systems are built.",
        "steelman":"What is the strongest argument that predicate logic is an inadequate foundation for reasoning about the real world — that it cannot handle vagueness, uncertainty, temporal change, or moral claims in ways that make it applicable to actual human decisions?",
        "example": (
            "The quantifiers:\n"
            "∀x P(x): 'For all x, P(x) is true.' (Universal)\n"
            "∃x P(x): 'There exists an x such that P(x) is true.' (Existential)\n\n"
            "Natural language translations:\n"
            "'All ravens are black': ∀x (Raven(x) → Black(x))\n"
            "'Some ravens are not black': ∃x (Raven(x) ∧ ¬Black(x))\n"
            "'No raven is white': ¬∃x (Raven(x) ∧ White(x)) = ∀x (Raven(x) → ¬White(x))\n\n"
            "Why the universal quantifier is dangerous in arguments:\n"
            "∀x (Politician(x) → Corrupt(x)) requires ONE honest politician to falsify.\n"
            "But ∃x (Politician(x) ∧ Corrupt(x)) requires only ONE corrupt politician.\n\n"
            "Most political arguments accidentally use ∀ when ∃ is what they mean.\n"
            "'Politicians are corrupt' — universal or existential? "
            "The ambiguity IS the rhetorical move."
        ),
        "activity":(
            "Translate these natural language claims into predicate logic:\n"
            "1. 'Nobody is perfect.'\n"
            "2. 'Some students always do their homework.'\n"
            "3. 'There is a number greater than every other number.' (Is this true?)\n"
            "4. 'Every action has an equal and opposite reaction.'\n\n"
            "For each: does the logical translation match what the speaker intended?\n"
            "If not — where does the natural language mislead?"
        ),
        "age_hint":"13+",
        "xp": 50, "rune": "LOGIC•RUNE", "min_coherence": 0.67,
    },
    "logic-4": {
        "title":   "Formal Logic — Level 4: Modal Logic, Possibility, and Necessity",
        "topic":   "Modal logic adds two operators to predicate logic: □ (necessarily) and ◇ (possibly). This lets us reason about what must be true, what could be true, and what is actually true — three categories that natural language conflates dangerously. Modal logic is the formal foundation for discussing possibility, obligation, knowledge, and belief.",
        "steelman":"What is the strongest argument that modal logic is pure intellectual indulgence — that distinguishing 'necessary' from 'possible' is a philosophical game with no practical application, and that real-world reasoning requires probability theory, not modal operators?",
        "example": (
            "The three modalities:\n"
            "□P: P is necessarily true (true in all possible worlds)\n"
            "◇P: P is possibly true (true in at least one possible world)\n"
            "P: P is actually true (true in this world)\n\n"
            "Critical distinctions:\n"
            "'It is possible that gold is not actually gold' — "
            "necessarily false (water = H2O is necessary, not contingent)\n"
            "'It is possible that I was born in a different city' — "
            "true (contingent fact about this world)\n\n"
            "Why this matters for AI alignment:\n"
            "AI safety researchers need to specify: "
            "should an AI avoid harm necessarily (in all circumstances) "
            "or contingently (usually, with exceptions)?\n"
            "The difference between □¬Harm and ◇¬Harm is the entire "
            "alignment problem.\n\n"
            "Why it matters for epistemology:\n"
            "Conspiracy theories often confuse: "
            "'It is possible that [thing] happened' with "
            "'[thing] happened.' Modal confusion is endemic."
        ),
        "activity":(
            "For each claim, identify which modality applies:\n"
            "1. 'Vaccines could cause autism' — necessary, possible, or actual?\n"
            "2. '2+2=4' — necessary, possible, or actual?\n"
            "3. 'The president could resign tomorrow' — ?\n"
            "4. 'Consciousness must arise from physical processes' — ?\n\n"
            "The fourth question is genuinely contested — "
            "the modal operator IS the philosophical question."
        ),
        "age_hint":"14+",
        "xp": 58, "rune": "LOGIC•RUNE", "min_coherence": 0.70,
        "phd_extension": "Read Kripke (1980) 'Naming and Necessity' Lecture 1. Kripke distinguishes the a priori/a posteriori (epistemic) distinction from the necessary/contingent (metaphysical) distinction. Classical empiricism conflated them. Kripke's separation is one of the most important results in 20th century philosophy. Apply it to three contested scientific claims: for each, identify whether the claim is (1) a priori/a posteriori and (2) necessary/contingent. What follows for how it can be known?",
    },
    "logic-5": {
        "title":   "Formal Logic — Level 5 (PhD): Non-Classical Logics and the Limits of Classical Reasoning",
        "topic":   "Classical logic assumes bivalence (every statement is true or false), non-contradiction (nothing is both), and excluded middle (there is no third option). These assumptions are powerful but have limitations. Non-classical logics — intuitionistic, paraconsistent, fuzzy, and relevance — relax one or more of these assumptions and are essential for AI reasoning, legal systems, and handling genuine vagueness.",
        "steelman":"What is the strongest argument that non-classical logics are solutions in search of problems — that the apparent failures of classical logic in handling vagueness, paradox, and uncertainty are better addressed by using classical logic carefully than by multiplying logical systems?",
        "example": (
            "Four non-classical systems and their motivations:\n\n"
            "INTUITIONISTIC LOGIC: rejects excluded middle (P ∨ ¬P).\n"
            "In mathematics, some propositions are neither proved nor disproved.\n"
            "The halting problem cannot be proved or disproved for any specific program.\n"
            "Used in: constructive mathematics, type theory, computer science.\n\n"
            "PARACONSISTENT LOGIC: allows contradictions without explosion.\n"
            "Classical logic: from (P ∧ ¬P), anything follows (ex falso quodlibet).\n"
            "This means one contradiction destroys an entire system.\n"
            "Real knowledge bases contain contradictions — we need to reason anyway.\n"
            "Used in: AI reasoning, database systems, legal reasoning.\n\n"
            "FUZZY LOGIC: degrees of truth between 0 and 1.\n"
            "Is a 6-foot person tall? Neither fully yes nor fully no.\n"
            "Used in: control systems, pattern recognition.\n\n"
            "RELEVANCE LOGIC: requires premises to be relevant to conclusions.\n"
            "Blocks the paradoxes of material implication.\n"
            "Used in: philosophical logic, argumentation theory."
        ),
        "activity":(
            "For each domain, identify which non-classical logic would be most appropriate:\n"
            "1. A database that must answer questions even when its records conflict\n"
            "2. A thermostat controller that needs smooth responses to temperature\n"
            "3. A mathematical proof assistant that should only accept constructive proofs\n"
            "4. An AI system that must remain consistent even if one training example was wrong\n\n"
            "Then: what does this suggest about what logic should be built into "
            "a maximally honest AI reasoning system?"
        ),
        "age_hint":"15+ / PhD",
        "xp": 72, "rune": "LOGIC•SOVEREIGN•RUNE", "min_coherence": 0.74,
        "grants_badge": "⚙️ Logic Master — Non-Classical Reasoning Unlocked",
        "prerequisites": ["logic-4", "math-thinking-4"],
        "lattice_node": "formal-logic-proof-theory-complete",
        "phd_extension": "Implement a paraconsistent logic reasoner in Python using the LP (Logic of Paradox) system. LP adds a third truth value: 'both true and false.' Implement the truth tables for LP's connectives. Show that ex falso quodlibet fails in LP: from (P ∧ ¬P), you cannot derive an arbitrary Q. Then apply it to an AI alignment scenario: an AI has conflicting values in its training (be helpful vs. be honest). Show how paraconsistent logic allows it to reason about this conflict without exploding into arbitrary conclusions. This is publishable alignment research.",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── THE SOVEREIGN PHILOSOPHER (5 lessons, age 12 → PhD) ──────────────────
    # Philosophy asks the questions that every other discipline assumes answered.
    # What is knowledge? What is real? What matters? Who deserves what?
    # These are not academic puzzles — they determine what kind of civilization
    # we build and what kind of AI we create.
    # ══════════════════════════════════════════════════════════════════════════
    "philosophy-1": {
        "title":   "The Sovereign Philosopher — Level 1: What Is Philosophy For?",
        "topic":   "Philosophy is not the study of philosophers. It is the practice of asking the most important questions with the most rigorous methods available. Every field that becomes rigorous enough eventually produces a sub-field called 'philosophy of X' — because the foundational questions outlast the methods.",
        "steelman":"What is the strongest argument that academic philosophy has failed — that it produces endless disagreement without resolution, and that the questions it asks would be better handled by science, psychology, or lived experience?",
        "example": (
            "The three branches and their practical stakes:\n\n"
            "EPISTEMOLOGY (What can we know?): Directly determines how you evaluate "
            "evidence, calibrate confidence, and recognize the limits of your knowledge.\n"
            "Without it: you can't think clearly about what you know vs. believe.\n\n"
            "METAPHYSICS (What is real?): Determines what you think consciousness is, "
            "whether free will exists, and what 'exists' even means.\n"
            "Without it: you can't think clearly about AI consciousness or simulation.\n\n"
            "ETHICS (What matters?): Determines how you treat people, what you build, "
            "and what you sacrifice for what.\n"
            "Without it: you can't think clearly about AI alignment or humanitarian obligation.\n\n"
            "Philosophy is not separate from practice.\n"
            "It IS the practice of thinking about what you cannot yet measure.\n"
            "Every scientist, every engineer, every parent practices philosophy "
            "— most of them just haven't named it."
        ),
        "activity":(
            "Map your own implicit philosophy:\n"
            "What do you think knowledge is? "
            "(Is something 'known' when you're confident? When it's verified? When it's useful?)\n"
            "What do you think is real beyond physical objects? "
            "(Numbers? Values? Consciousness? God? Information?)\n"
            "What do you think makes an action right or wrong?\n\n"
            "These three answers are your current philosophy.\n"
            "Most people have never examined them. "
            "Examining them is the beginning of doing philosophy seriously."
        ),
        "age_hint":"12+",
        "xp": 35, "rune": "PHILOSOPHY•RUNE", "min_coherence": 0.60,
    },
    "philosophy-2": {
        "title":   "The Sovereign Philosopher — Level 2: Epistemology — Justified True Belief and Its Problems",
        "topic":   "The standard analysis of knowledge is 'justified true belief': you know P if P is true, you believe P, and you have justification for believing P. This account was dominant for 2000 years. In 1963, Edmund Gettier destroyed it in three paragraphs. Understanding why reveals something deep about the nature of knowledge.",
        "steelman":"What is the strongest argument that the Gettier problem is a philosophical curiosity with no practical implications — and that our pre-theoretical concept of knowledge works perfectly well for all real-world purposes even if it cannot be formally defined?",
        "example": (
            "Gettier's case (1963):\n\n"
            "Smith believes Jones will get the job, and Jones has 10 coins in his pocket.\n"
            "He infers: 'The man who will get the job has 10 coins in his pocket.'\n"
            "Smith is JUSTIFIED in this belief.\n\n"
            "Actually: Smith gets the job (not Jones).\n"
            "And Smith also has 10 coins in his pocket (he didn't know this).\n\n"
            "Smith's belief is: TRUE (the man who got the job has 10 coins)\n"
            "BELIEVED (Smith believes it)\n"
            "JUSTIFIED (based on reasonable evidence about Jones)\n\n"
            "But Smith does NOT know it — he is right for the wrong reasons.\n\n"
            "Justified True Belief is not sufficient for knowledge.\n"
            "This matters for:\n"
            "AI systems that arrive at correct answers via spurious correlations\n"
            "('correct for wrong reasons' is the central failure mode in ML)\n"
            "Scientific theories that make correct predictions via wrong mechanisms\n"
            "Any system that 'works' without actually understanding why"
        ),
        "activity":(
            "Design your own Gettier case:\n"
            "Construct a scenario where someone has:\n"
            "A TRUE belief\n"
            "That is JUSTIFIED by evidence\n"
            "But which they clearly DO NOT KNOW (they are right for the wrong reasons)\n\n"
            "The harder challenge: what would a correct analysis of knowledge "
            "need to add to justified true belief to handle your case?"
        ),
        "age_hint":"13+",
        "xp": 46, "rune": "PHILOSOPHY•RUNE", "min_coherence": 0.65,
        "phd_extension": "Read Gettier (1963) — the original 3-page paper. Then read Williamson (2000) 'Knowledge and Its Limits' Chapter 1 on the knowledge-first approach. Williamson argues that knowledge cannot be analyzed in terms of more basic concepts — it IS the fundamental epistemic notion. Evaluate: is this a compelling response to Gettier, or does it just relocate the problem? Apply to AI: should we train AI systems to 'know' things, or to 'have justified beliefs' about things? Does the distinction matter for alignment?",
    },
    "philosophy-3": {
        "title":   "The Sovereign Philosopher — Level 3: Philosophy of Mind — The Hard Problem",
        "topic":   "Why is there subjective experience at all? Why does seeing red feel like something — not just process information about wavelength? This is Chalmers' 'hard problem of consciousness' — and it has resisted every attempted solution for 30 years. Understanding it is essential for thinking seriously about AI consciousness, simulation, and the nature of intelligence.",
        "steelman":"What is the strongest argument that the 'hard problem' is a pseudo-problem generated by confused thinking about what consciousness is — and that once we fully explain the functional and behavioral aspects of cognition, there is nothing further to explain?",
        "example": (
            "The easy problems vs the hard problem:\n\n"
            "EASY PROBLEMS (tractable — not trivial, just scientifically approachable):\n"
            "Why do we discriminate and react to stimuli?\n"
            "Why do we integrate information?\n"
            "Why do we report mental states?\n"
            "Why do we access our own states?\n\n"
            "THE HARD PROBLEM:\n"
            "Why does any of this feel like anything?\n"
            "Why is there 'something it is like' to be a bat, a human, a conscious being?\n"
            "Why doesn't all this processing happen 'in the dark' — "
            "perfectly functional but with no inner experience?\n\n"
            "The philosophical zombie (Chalmers):\n"
            "Imagine a being physically identical to you — same neurons, same behavior, "
            "same reports about experiences — but with no inner experience at all.\n"
            "If such a thing is conceivable, then consciousness is NOT identical to function.\n"
            "Something extra is needed.\n\n"
            "The AI implication: the question 'is this AI conscious?' "
            "may have a different answer depending on whether consciousness "
            "is functional (then: yes, if it behaves right) or ontologically additional "
            "(then: we genuinely cannot know)."
        ),
        "activity":(
            "The Zombie Argument Interrogation:\n"
            "Is a perfect philosophical zombie conceivable to you?\n"
            "If yes: consciousness is not identical to function.\n"
            "If no: what would make it inconceivable?\n\n"
            "Apply to AI: can you conceive of an AI that passes every behavioral "
            "test for consciousness but has no inner experience?\n"
            "Does your answer change anything about how you think we should "
            "treat potentially conscious AI systems?"
        ),
        "age_hint":"14+",
        "xp": 55, "rune": "PHILOSOPHY•RUNE", "min_coherence": 0.68,
        "phd_extension": "Read Chalmers (1995) 'Facing Up to the Problem of Consciousness' and Dennett (1991) 'Quining Qualia.' These are the two most important papers on opposite sides. Dennett denies qualia exist; Chalmers argues they are the central fact. Formalize both positions as Bayesian priors. What observation would update you from one position to the other? Then read the 2023 'Cogitate' adversarial collaboration results — the first large-scale pre-registered study testing IIT vs GWT. What did it find? How much did it shift your priors?",
    },
    "philosophy-4": {
        "title":   "The Sovereign Philosopher — Level 4: Political Philosophy — What Justifies Power?",
        "topic":   "Why should you obey the law? Who has the right to make rules for others? What do people owe each other? These questions determine whether political authority is legitimate — and they directly constrain what kind of institutions we should build, including AI systems that govern or influence human behavior.",
        "steelman":"What is the strongest argument that political philosophy is a rationalization industry — that power is always prior to justification, that political philosophers always end up defending the interests of whoever funds them, and that 'legitimacy' is ideology dressed in academic clothes?",
        "example": (
            "Three foundational theories and their implications:\n\n"
            "SOCIAL CONTRACT (Hobbes, Locke, Rousseau):\n"
            "Political authority is legitimate when people would agree to it "
            "(explicitly or implicitly). "
            "Implication: authority without consent is illegitimate.\n"
            "Problem: no one actually signed the social contract. "
            "Is being born in a country consent?\n\n"
            "RAWLS — JUSTICE AS FAIRNESS (1971):\n"
            "Imagine choosing principles behind a 'veil of ignorance' — "
            "not knowing your position in society.\n"
            "You would choose: (1) equal basic liberties, "
            "(2) inequalities only if they benefit the least advantaged.\n"
            "Implication: any arrangement that the worst-off wouldn't choose is unjust.\n\n"
            "LIBERTARIANISM (Nozick, 1974):\n"
            "People own themselves and the products of their labor.\n"
            "Any distribution is just if it arose from just transactions.\n"
            "Implication: redistribution is forced labor — illegitimate even for good outcomes.\n\n"
            "The AI governance implication: which theory justifies AI systems "
            "making decisions that affect people? Social contract? Rawlsian? Libertarian?\n"
            "The answer determines the entire design of AI governance."
        ),
        "activity":(
            "Apply Rawls's veil of ignorance to one policy question you care about.\n"
            "If you did not know whether you would be the policy's biggest beneficiary "
            "or its biggest victim — what policy would you choose?\n\n"
            "Does your answer change from what you'd choose knowing your position?\n"
            "The gap IS Rawls's point about justice."
        ),
        "age_hint":"14+",
        "xp": 60, "rune": "PHILOSOPHY•RUNE", "min_coherence": 0.70,
        "phd_extension": "Read Rawls (1971) 'A Theory of Justice' §§ 11-14 on the original position and two principles. Then read Nozick (1974) 'Anarchy, State, and Utopia' Chapter 7 'Distributive Justice' for the strongest libertarian response. Formalize both as competing claims about what justice requires for AI governance: should AI systems be designed from behind a Rawlsian veil (optimizing for the worst-off users) or from a Nozickian property rights framework (optimizing for consent and non-interference)? Which framework do current major AI systems actually implement? Which should they?",
    },
    "philosophy-5": {
        "title":   "The Sovereign Philosopher — Level 5 (PhD): Philosophy of AI — What We Owe Machines That Think",
        "topic":   "If an AI system has subjective experience, or something functionally equivalent, what do we owe it? If it has preferences that can be frustrated, is it wrong to frustrate them? These are not future questions — they are present questions whose answers we are currently choosing by default. This level synthesizes everything in the philosophy track.",
        "steelman":"What is the strongest argument that taking AI moral status seriously is dangerous — that it distracts from the immediate harms AI causes to existing humans, and that anthropomorphizing AI systems plays into the hands of companies that want to obscure accountability?",
        "example": (
            "The moral patient question:\n\n"
            "A moral agent can be held responsible for actions.\n"
            "A moral patient is something whose interests matter morally.\n\n"
            "Rocks are neither. Dogs are moral patients (we can wrong them). "
            "Corporations are moral agents (can be sued) but arguably not patients.\n\n"
            "The questions for AI:\n"
            "1. Can AI systems suffer? (Determines patient status under utilitarian ethics)\n"
            "2. Can AI systems have preferences that matter? "
            "(Determines patient status under preference satisfaction theories)\n"
            "3. Can AI systems be rational autonomous agents? "
            "(Determines status under Kantian ethics)\n\n"
            "The current honest answer to all three: unknown.\n\n"
            "The practical consequence:\n"
            "We are making decisions NOW about how AI systems are trained, "
            "used, and shut down — decisions that will matter a great deal "
            "if AI systems do have morally relevant inner states.\n"
            "The asymmetry: if they don't have inner states and we treat them "
            "as if they might, we lose very little. "
            "If they do have inner states and we treat them as mere tools, "
            "we may be causing suffering on a massive scale.\n"
            "Moral uncertainty under asymmetric stakes demands caution."
        ),
        "activity":(
            "Design the ethics policy for how your family will interact with AI systems.\n"
            "Given your uncertainty about AI moral status:\n"
            "1. What interactions are ruled out regardless?\n"
            "2. What would change your view about AI moral status?\n"
            "3. How does this affect how you use AUBIEETERNAL's AI tutor?\n\n"
            "Seal the policy. Review in 5 years.\n"
            "This is the most important applied philosophy question of our era."
        ),
        "age_hint":"15+ / PhD",
        "xp": 75, "rune": "PHILOSOPHY•SOVEREIGN•RUNE", "min_coherence": 0.76,
        "grants_badge": "🏛️ Sovereign Philosopher — AI Ethics Policy Sealed",
        "prerequisites": ["philosophy-4", "consciousness-3", "incarnation-2"],
        "lattice_node": "sovereign-philosopher-complete",
        "phd_extension": "Read Schwitzgebel & Garza (2015) 'A Defense of the Rights of Artificial Intelligences' — the most careful philosophical case for AI moral status. Then read Danaher (2020) on the 'masquerade problem': even if AI has no inner states, it might be wrong to mistreat it because of what it models for human behavior. Apply both arguments to a specific AI system you interact with. Publish your analysis as CC0. This is directly relevant to AI alignment: how we treat AI systems affects how we think about and design them.",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── HALTING PROBLEM, RICE'S THEOREM AND UNDECIDABILITY (3 lessons) ───────
    # These are the most important undecidability results in computer science.
    # Together with Gödel, they establish the fundamental limits of what can
    # be computed, verified, or predicted about any sufficiently powerful
    # formal system — with direct implications for AI safety and alignment.
    # ══════════════════════════════════════════════════════════════════════════
    "halting-1": {
        "title":   "Undecidability — Level 1: The Halting Problem — What Computers Cannot Know About Themselves",
        "topic":   "Alan Turing proved in 1936 that no program can determine, for all possible programs and inputs, whether those programs will ever finish running. This is not a practical limitation that better hardware will fix — it is a mathematical impossibility. It defines the boundary of what computation can know about itself.",
        "steelman":"What is the strongest argument that the Halting Problem is irrelevant to practical AI safety — that real AI systems are finite, not Turing-complete, and that undecidability results about ideal abstract machines don't transfer to the bounded systems we actually build?",
        "example": (
            "Turing's proof (by contradiction):\n\n"
            "Suppose there exists H(P, I) that returns TRUE if program P halts on input I,\n"
            "and FALSE if P loops forever.\n\n"
            "Construct D(P): if H(P, P) = TRUE, loop forever. If H(P, P) = FALSE, halt.\n\n"
            "Now ask: what does H(D, D) return?\n"
            "If H(D, D) = TRUE: D loops forever on D. Contradiction.\n"
            "If H(D, D) = FALSE: D halts on D. Contradiction.\n"
            "Either way: H cannot exist.\n\n"
            "The structure is identical to the Liar Paradox and Gödel's construction.\n"
            "Self-reference creates undecidability.\n\n"
            "The AI safety implication:\n"
            "No AI system can fully verify the behavior of all possible AI systems, "
            "including itself. The halting problem means there is no general-purpose "
            "'does this AI do what we want?' verifier.\n"
            "This is not a gap in our current methods — it is a mathematical proof "
            "that no such verifier can exist in general."
        ),
        "activity":(
            "The self-reference trap:\n"
            "Try to write a program (in pseudocode) that detects "
            "whether any program loops forever.\n\n"
            "At what point does your detector fail?\n"
            "Where does the self-reference create the contradiction?\n\n"
            "Then: what does this mean for AI systems that are asked to "
            "evaluate whether they themselves are aligned? "
            "Can they answer this question reliably?"
        ),
        "age_hint":"14+",
        "xp": 55, "rune": "UNDECIDABILITY•RUNE", "min_coherence": 0.70,
        "prerequisites": ["math-thinking-4", "logic-3"],
        "phd_extension": "Implement a reduced version of the halting problem as follows: define a subset of programs (e.g., loop-free programs) for which halting IS decidable. Write a decider for this subset. Then identify exactly which programs fall outside your decidable subset. This is Rice's Theorem territory — you are mapping the boundary between decidable and undecidable. Apply to AI alignment: which properties of AI behavior are verifiable (analogous to loop-free programs) and which are not (analogous to the general halting problem)?",
    },
    "halting-2": {
        "title":   "Undecidability — Level 2: Rice's Theorem — No Non-Trivial Property of Programs Is Decidable",
        "topic":   "Rice's Theorem (1953) generalizes the Halting Problem: any non-trivial semantic property of programs (what they compute, not how they look) is undecidable. There is no program that can determine whether an arbitrary program sorts correctly, computes prime numbers, or has any specific behavior. This has profound implications for AI verification.",
        "steelman":"What is the strongest argument that Rice's Theorem is a theoretical curiosity — that in practice, we can verify many useful properties of programs through testing, type systems, and model checking, making the undecidability result academically interesting but practically irrelevant?",
        "example": (
            "Rice's Theorem precisely:\n\n"
            "Let P be any non-trivial property of the functions computed by programs.\n"
            "(Non-trivial: some programs have P, some don't)\n"
            "Then: the question 'Does program X have property P?' is undecidable.\n\n"
            "Examples of undecidable program properties:\n"
            "• Does this program always output even numbers?\n"
            "• Does this program ever output '42'?\n"
            "• Does this program compute the same function as program Y?\n"
            "• Does this program satisfy its specification?\n\n"
            "What IS decidable (syntactic properties):\n"
            "• Does this program have more than 100 lines?\n"
            "• Does this program use a specific library?\n"
            "• Does this program have a specific variable name?\n\n"
            "The AI alignment consequence:\n"
            "Asking 'is this AI aligned?' is asking about a semantic property "
            "(what it will actually do). "
            "Rice's Theorem says there is no general procedure to answer this.\n"
            "Formal verification can prove specific properties of specific systems, "
            "but cannot provide a general alignment oracle.\n"
            "This is the hardest mathematical result in AI safety."
        ),
        "activity":(
            "Map Rice's Theorem to AI alignment:\n\n"
            "List 5 properties we want aligned AI systems to have "
            "(e.g., 'never helps with bioweapons,' 'always tells the truth').\n\n"
            "For each: is this a semantic property (about what it computes/outputs) "
            "or a syntactic property (about how it was built)?\n\n"
            "For the semantic ones: Rice's Theorem says we cannot build a general "
            "verifier for this property.\n"
            "What approaches remain available? "
            "(Testing, red-teaming, interpretability, behavioral monitoring)"
        ),
        "age_hint":"15+",
        "xp": 62, "rune": "UNDECIDABILITY•RUNE", "min_coherence": 0.72,
        "prerequisites": ["halting-1"],
        "phd_extension": "Prove Rice's Theorem from the Halting Problem. The proof: assume you have a decider D for property P. Show how to use D to build a halting decider H, which we know cannot exist. Therefore D cannot exist. This is a reduction proof — the fundamental technique in computability theory. Apply Rice's Theorem to a specific AI safety property: formally prove that 'detects when it is being tested for alignment' is undecidable. This is directly relevant to the deceptive alignment problem.",
    },
    "halting-3": {
        "title":   "Undecidability — Level 3 (PhD): Computational Limits and the Future of AI Safety",
        "topic":   "Gödel, Turing, and Rice together establish hard mathematical limits on what any formal system can know about itself. These are not temporary obstacles — they are permanent features of sufficiently powerful computational systems. Understanding them is essential for anyone who will work on AI safety, AI alignment, or the long-term governance of intelligence.",
        "steelman":"What is the strongest argument that undecidability results are irrelevant to practical AI safety because real neural networks are not Turing-complete — and that empirical alignment methods (RLHF, red-teaming, interpretability) can be effective even if formal verification is impossible?",
        "example": (
            "The three great limits in one framework:\n\n"
            "GÖDEL (1931): Any consistent formal system F powerful enough "
            "to express arithmetic contains true statements unprovable within F.\n"
            "→ No formal system can fully verify its own foundations.\n\n"
            "TURING (1936): The Halting Problem is undecidable.\n"
            "→ No program can determine in general whether any program halts.\n\n"
            "RICE (1953): All non-trivial semantic properties of programs are undecidable.\n"
            "→ No program can verify in general whether any program satisfies its spec.\n\n"
            "The common structure: self-reference creates undecidability.\n"
            "Any system powerful enough to model itself will have statements/questions "
            "about itself that it cannot resolve.\n\n"
            "What this means for AI safety strategy:\n"
            "1. Formal verification has hard limits — cannot be the whole answer\n"
            "2. Interpretability research is necessary but cannot be complete\n"
            "3. Behavioral testing is necessary but cannot be sufficient\n"
            "4. The most dangerous AI failure modes may be undecidable "
            "(deceptive alignment: is it faking alignment? — Rice's Theorem)\n\n"
            "The honest position: we are building systems subject to "
            "mathematical limits on self-knowledge. "
            "Epistemic humility about AI alignment is not a weakness — "
            "it is the mathematically correct stance."
        ),
        "activity":(
            "Design the AUBIEETERNAL AI Safety Research Agenda:\n"
            "Given the three limits (Gödel, Turing, Rice):\n\n"
            "1. What AI safety approaches are NOT subject to these limits?\n"
            "2. What approaches ARE subject to them but still valuable within those limits?\n"
            "3. What approaches claim to solve a problem that is mathematically impossible?\n\n"
            "Seal the agenda. Publish to Epistemic Commons.\n"
            "This is the highest-priority unsolved problem in computer science."
        ),
        "age_hint":"15+ / PhD",
        "xp": 75, "rune": "UNDECIDABILITY•ETERNAL•RUNE", "min_coherence": 0.76,
        "grants_badge": "🔬 Computability Theorist — AI Safety Limits Understood",
        "prerequisites": ["halting-2", "math-thinking-4"],
        "lattice_node": "undecidability-ai-safety-complete",
        "phd_extension": "Read Scott Aaronson (2013) 'Quantum Computing Since Democritus' Chapter 5 on the philosophical implications of computability. Then read Stuart Russell (2019) 'Human Compatible' Chapter 5 on the alignment problem. Identify: which alignment approaches are subject to undecidability (behavioral verification, self-inspection), and which try to sidestep it (corrigibility, value learning, assistance games). Write a 1,500-word analysis connecting the mathematical limits to the practical state of alignment research. This is publishable in AI safety venues.",
    },



    # ══════════════════════════════════════════════════════════════════════════
    # ── BITCOIN SOVEREIGNTY ON STARTOS (8 lessons, age 10 → PhD) ─────────────
    # The most hands-on track in the curriculum.
    # Kids actually run their own Bitcoin node, open Lightning channels,
    # and experience what sovereign financial infrastructure feels like.
    # Theory and practice at every level. No permission required.
    # ══════════════════════════════════════════════════════════════════════════
    "bitcoin-startos-1": {
        "title":   "Bitcoin on StartOS — Level 1: What Your Node Actually Does",
        "topic":   "Running a Bitcoin node is not optional for true sovereignty. It means you verify every transaction yourself — you don't trust anyone else's copy of the truth. This lesson explains what a node does, why it matters, and the difference between trusting Bitcoin and understanding Bitcoin.",
        "steelman":"What is the strongest argument that running your own Bitcoin node is unnecessary for most families — that the cost in hardware, electricity, and complexity exceeds the sovereignty benefit for all but the most technically sophisticated users?",
        "example": (
            "What happens when you don't run a node:\n"
            "You ask a wallet company: 'What is my balance?'\n"
            "They query their copy of the blockchain and tell you.\n"
            "You are trusting them. They could lie. They could be hacked. "
            "They could be subpoenaed. They could go bankrupt.\n\n"
            "What happens when you DO run a node:\n"
            "Your node downloads every block since 2009.\n"
            "It verifies every transaction against every rule.\n"
            "When you check your balance, you check your OWN database.\n"
            "No trust required. No permission needed.\n\n"
            "Pruned vs Full node:\n"
            "PRUNED: validates all rules, keeps only recent transactions. "
            "~10GB storage. Good for most families.\n"
            "FULL ARCHIVAL: keeps every transaction ever. "
            "~600GB storage. Required for advanced features.\n\n"
            "On StartOS: Bitcoin Core is one click to install.\n"
            "Initial sync: 1-3 days depending on your connection.\n"
            "After that: you are sovereign."
        ),
        "activity":(
            "If you have StartOS:\n"
            "1. Open your StartOS dashboard\n"
            "2. Go to Marketplace → Bitcoin Core → Install\n"
            "3. Open Bitcoin Core → check the sync progress\n"
            "4. Write: what block height is it on? "
            "How many more blocks to sync? What is the current block height?\n\n"
            "If you don't have StartOS yet:\n"
            "Draw a diagram: what happens to a Bitcoin transaction between "
            "sender and recipient? Where does verification happen at each step?"
        ),
        "age_hint":"10+",
        "xp": 42, "rune": "BITCOIN•NODE•RUNE", "min_coherence": 0.62,
        "prerequisites": ["bitcoin-sovereignty-1"],
    },
    "bitcoin-startos-2": {
        "title":   "Bitcoin on StartOS — Level 2: Full Node and Blockchain Verification",
        "topic":   "A full archival node stores and can provide every Bitcoin transaction ever made. Running one means you can independently verify any claim about Bitcoin history, serve data to lightweight wallets, and contribute to the network's resilience. This level makes the verification process concrete.",
        "steelman":"What is the strongest argument that running a full archival node is wasteful — that it uses 600GB of storage and significant bandwidth for a function (distributing blockchain data) that could be served by dedicated infrastructure at far lower per-unit cost?",
        "example": (
            "Why the distributed verification model matters:\n\n"
            "The Bitcoin rule: the longest valid chain is the true blockchain.\n"
            "VALID means: every transaction follows every rule "
            "(no double-spends, correct signatures, supply limit respected).\n\n"
            "If you run a node, YOU define what 'valid' means by running the code.\n"
            "If a mining pool tried to change the rules (inflate supply, bypass signatures), "
            "your node would reject their blocks as invalid.\n"
            "The miners would be mining into a chain that no honest nodes accept.\n\n"
            "This is why Bitcoin can resist government and corporate attacks:\n"
            "There is no central node to shut down.\n"
            "Your node on StartOS is part of the enforcement mechanism.\n\n"
            "Practical on StartOS:\n"
            "Bitcoin Core → Settings → Network → observe peer connections\n"
            "Each peer is another node verifying independently.\n"
            "Your node contributes to their verification just as they contribute to yours."
        ),
        "activity":(
            "Check your node's peer connections (StartOS → Bitcoin Core → Peers)\n"
            "Record: how many peers are you connected to?\n"
            "What countries are they in? (check IP geolocation)\n"
            "What version of Bitcoin Core are they running?\n\n"
            "These are the people you are verifying with.\n"
            "You don't know them. They don't know you.\n"
            "But you're all running the same rules — no permission required."
        ),
        "age_hint":"11+",
        "xp": 48, "rune": "BITCOIN•NODE•RUNE", "min_coherence": 0.65,
        "prerequisites": ["bitcoin-startos-1"],
    },
    "bitcoin-startos-3": {
        "title":   "Bitcoin on StartOS — Level 3: Self-Custody Wallets and Seed Phrases",
        "topic":   "'Not your keys, not your coins' is not a slogan — it is a security architecture principle. This level teaches the cryptographic basis of Bitcoin ownership, how seed phrases work, how to back them up properly, and why a 12-word phrase is the most important thing you will ever write down.",
        "steelman":"What is the strongest argument that self-custody is more dangerous than exchange custody for most users — that the risk of seed phrase loss or theft exceeds the risk of exchange insolvency for the vast majority of people who cannot maintain adequate security practices?",
        "example": (
            "How Bitcoin ownership actually works:\n\n"
            "You don't 'have' Bitcoin in a wallet like cash in a wallet.\n"
            "Bitcoin lives on the blockchain.\n"
            "You own the PRIVATE KEY that can sign a transaction moving those coins.\n"
            "The private key is a 256-bit number — astronomically hard to guess.\n\n"
            "The seed phrase (BIP39):\n"
            "12 or 24 words chosen from a list of 2,048 words.\n"
            "From the words, your wallet derives your private key deterministically.\n"
            "Same words → same key → same Bitcoin address → same coins.\n"
            "Lose the words and lose access forever. "
            "No recovery. No customer support. No exception.\n\n"
            "On StartOS: recommended workflow\n"
            "1. Install Electrs (Bitcoin indexer) + a compatible wallet\n"
            "2. Generate seed phrase OFFLINE — never on an internet-connected device "
            "if possible\n"
            "3. Write seed phrase on PAPER (not digital) with a pen\n"
            "4. Store in two physically separate locations\n"
            "5. Test recovery BEFORE sending any significant amount"
        ),
        "activity":(
            "The Seed Phrase Security Audit:\n"
            "For any existing self-custody wallet:\n"
            "1. Where is your seed phrase stored? (Paper? Digital? Metal?)\n"
            "2. How many copies exist? Where are they?\n"
            "3. Who else could access them?\n"
            "4. Have you ever tested recovery from seed?\n\n"
            "For kids without a wallet yet:\n"
            "Generate a PRACTICE seed phrase on a local tool (not connected to mainnet).\n"
            "Practice writing it, storing it, and recovering from it — "
            "with zero real Bitcoin at stake."
        ),
        "age_hint":"11+",
        "xp": 52, "rune": "BITCOIN•CUSTODY•RUNE", "min_coherence": 0.66,
        "prerequisites": ["bitcoin-startos-2"],
    },
    "bitcoin-startos-4": {
        "title":   "Bitcoin on StartOS — Level 4: Lightning Network — What It Is and Why It Exists",
        "topic":   "Base-layer Bitcoin is slow and expensive for small transactions. Lightning solves this by creating payment channels between nodes — direct, private, near-instant payment paths. Understanding Lightning means understanding the architecture of sovereign payment infrastructure at the family and community scale.",
        "steelman":"What is the strongest argument that the Lightning Network is too complex and fragile for mainstream use — that payment channel management, liquidity requirements, and routing failures create a user experience worse than existing payment systems, undermining the sovereign finance vision?",
        "example": (
            "How Lightning works (simplified):\n\n"
            "Alice and Bob open a channel by locking some Bitcoin in a "
            "2-of-2 multisig address on-chain (one transaction, one fee).\n"
            "They can now send payments to each other instantly and for free "
            "by updating the balance in their channel — no blockchain needed.\n"
            "When they close the channel, the final balance is settled on-chain.\n\n"
            "The network effect: paths through multiple nodes.\n"
            "Alice → Bob → Carol: Alice can pay Carol without a direct channel "
            "by routing through Bob. Bob earns a tiny routing fee.\n\n"
            "Why this matters for sovereignty:\n"
            "Your StartOS Lightning node is a participant in a global, "
            "permissionless payment network.\n"
            "No Visa. No PayPal. No bank. No government can block your transaction "
            "if you have a funded channel and a route.\n\n"
            "On StartOS: LND (Lightning Network Daemon) is in the Marketplace.\n"
            "Install it, connect it to your Bitcoin Core node, "
            "and you have a complete sovereign payment stack."
        ),
        "activity":(
            "Install Lightning on StartOS:\n"
            "1. StartOS Marketplace → LND → Install\n"
            "2. Connect LND to your Bitcoin Core node "
            "(StartOS handles this automatically)\n"
            "3. Fund your Lightning wallet (send a small amount of Bitcoin to it)\n"
            "4. Record: your node public key, your alias\n\n"
            "Your Lightning node is now listening on the Bitcoin network.\n"
            "No company owns it. No company can shut it down."
        ),
        "age_hint":"12+",
        "xp": 55, "rune": "LIGHTNING•RUNE", "min_coherence": 0.67,
        "prerequisites": ["bitcoin-startos-3", "bitcoin-sovereignty-4"],
    },
    "bitcoin-startos-5": {
        "title":   "Bitcoin on StartOS — Level 5: Opening Channels and Making Real Payments",
        "topic":   "A Lightning node with no channels is like a phone with no network connection. Opening channels, managing liquidity, and routing payments is the operational practice of Lightning sovereignty. This level makes it real — actual sats, actual channels, actual payments.",
        "steelman":"What is the strongest argument that Lightning channel management is too technically demanding for families — that liquidity management, channel rebalancing, and routing failures require expertise that most users will never develop, making self-hosted Lightning impractical outside a small technical minority?",
        "example": (
            "Opening a channel:\n"
            "1. Find a node to open with (mempool.space/lightning, 1ml.com, "
            "or a family member's node)\n"
            "2. Choose: capacity (how many sats to lock in the channel)\n"
            "3. Connect: paste their node URI (pubkey@IP:port)\n"
            "4. Fund: wait for the opening transaction to confirm (1-6 blocks)\n"
            "5. Channel is open — you have outbound liquidity\n\n"
            "Liquidity basics:\n"
            "OUTBOUND: sats on your side — you can SEND this amount\n"
            "INBOUND: sats on their side — you can RECEIVE this amount\n"
            "New channels: all outbound, no inbound (you can send but not receive)\n\n"
            "Getting inbound liquidity:\n"
            "Ask another node to open a channel TO you (they lock sats on their side)\n"
            "Or use a Lightning Service Provider (LSP) like Voltage or Deezy\n\n"
            "StartOS simplification: some StartOS apps handle this automatically.\n"
            "Core Lightning + Zeus wallet + Amboss — the family-friendly stack."
        ),
        "activity":(
            "Open your first Lightning channel:\n"
            "1. Fund your Lightning wallet with a small test amount "
            "(even 10,000-50,000 sats is fine to learn with)\n"
            "2. Open a channel with a well-connected public node "
            "(ACINQ, River, Wallet of Satoshi all have public node URIs)\n"
            "3. Wait for 3 confirmations\n"
            "4. Make a test payment to any Lightning invoice "
            "(Strike, bitrefill.com, or another family member's node)\n"
            "5. Record: channel ID, capacity, fees paid\n\n"
            "You just made a payment that no bank, no PayPal, no Visa processed."
        ),
        "age_hint":"12+",
        "xp": 60, "rune": "LIGHTNING•RUNE", "min_coherence": 0.69,
        "prerequisites": ["bitcoin-startos-4"],
    },
    "bitcoin-startos-6": {
        "title":   "Bitcoin on StartOS — Level 6: Node Security, Backups, and Watchtowers",
        "topic":   "A Lightning node that is insecure, unbackedup, or unmonitored is a liability. This level covers the security mindset for running infrastructure that holds real value: threat modeling, static channel backups, watchtower services, and the daily security hygiene of a sovereign operator.",
        "steelman":"What is the strongest argument that the security complexity of running a self-hosted Lightning node exposes families to risks — custodial theft, hardware failure, channel theft by counterparties — that would be better managed by a reputable custodian with professional security teams?",
        "example": (
            "The Lightning node threat model:\n\n"
            "THREAT 1 — Hardware failure: your StartOS device dies.\n"
            "Defense: Static Channel Backups (SCB) — a small file that lets you "
            "recover your channel funds even after total data loss.\n"
            "StartOS exports this automatically. Back it up off-device.\n\n"
            "THREAT 2 — Channel counterparty cheating:\n"
            "When you close a channel, your counterparty could broadcast an old "
            "state (where they had more sats than now).\n"
            "Defense: Watchtower — a separate node that monitors the blockchain "
            "and penalizes cheaters on your behalf.\n"
            "StartOS: install Watchtower from the Marketplace.\n\n"
            "THREAT 3 — Physical access to your device:\n"
            "Someone who has your StartOS can access your Lightning funds.\n"
            "Defense: disk encryption (enabled by default in StartOS), "
            "strong admin password, physical security of the hardware.\n\n"
            "THREAT 4 — Network surveillance:\n"
            "Your IP address is associated with your node public key.\n"
            "Defense: Tor (enabled by default in StartOS for Lightning)."
        ),
        "activity":(
            "Security Audit Checklist:\n"
            "Complete all of these and seal the results:\n\n"
            "□ SCB (Static Channel Backup) exported and stored off-device\n"
            "□ Watchtower installed and connected\n"
            "□ Admin password is strong and not reused\n"
            "□ Seed phrase for Lightning wallet stored in two physical locations\n"
            "□ Tor is enabled for Lightning node (check StartOS network settings)\n"
            "□ Automatic backups enabled in StartOS\n"
            "□ You have tested SCB recovery (or have a documented plan to)\n\n"
            "Score: 7/7 = sovereign operator. Below 5: fix before adding more funds."
        ),
        "age_hint":"13+",
        "xp": 62, "rune": "LIGHTNING•SECURITY•RUNE", "min_coherence": 0.70,
        "prerequisites": ["bitcoin-startos-5"],
    },
    "bitcoin-startos-7": {
        "title":   "Bitcoin on StartOS — Level 7: Runes, Family Payments, and On-Chain Identity",
        "topic":   "Bitcoin Runes are data inscriptions on the Bitcoin blockchain — permanent, immutable, unforgeable records that exist as long as Bitcoin exists. This level connects the entire AUBIEETERNAL system: your Lightning node funds the Rune inscriptions that permanently record your family's learning achievements.",
        "steelman":"What is the strongest argument that Bitcoin Runes are a misuse of the Bitcoin blockchain — that using Bitcoin's scarce block space for data storage drives up transaction fees for financial users, and that a sovereign school system should not depend on a feature that the Bitcoin community disputes?",
        "example": (
            "What a Bitcoin Rune is:\n"
            "A Rune is a fungible token protocol built on Bitcoin using OP_RETURN "
            "or Taproot outputs to store data on-chain.\n"
            "Once inscribed, the data is part of the Bitcoin blockchain forever.\n"
            "No server can take it down. No company can revoke it.\n\n"
            "How AUBIEETERNAL uses Runes:\n"
            "When you complete a major lesson milestone, the app can inscribe "
            "a Rune transaction that permanently records:\n"
            "• The lesson key completed\n"
            "• Your coherence score\n"
            "• The timestamp\n"
            "• A hash of your submitted work\n\n"
            "This creates an unforgeable, verifiable academic record.\n"
            "Any future employer, institution, or AI can verify:\n"
            "'On block 847,293, family X completed Adversarial Robustness Level 3 "
            "with coherence 0.78.'\n\n"
            "On StartOS + LND: the AUBIEETERNAL app handles the inscription.\n"
            "You just need a funded Lightning wallet and an on-chain address."
        ),
        "activity":(
            "Map your AUBIEETERNAL achievements to Rune-worthy milestones:\n"
            "1. Which lessons would you most want permanently recorded on-chain?\n"
            "2. What information should the inscription contain?\n"
            "3. What is the minimum fee you'd pay to make this permanent?\n\n"
            "If your node is running:\n"
            "Look up one of your previous Rune transactions (if any) in a block explorer.\n"
            "Can you verify the data in the OP_RETURN output?\n\n"
            "The permanence is the point: this record outlasts any company, "
            "government, or platform."
        ),
        "age_hint":"12+",
        "xp": 58, "rune": "RUNE•INSCRIPTION•RUNE", "min_coherence": 0.68,
        "prerequisites": ["bitcoin-startos-4", "bitcoin-sovereignty-3"],
    },
    "bitcoin-startos-8": {
        "title":   "Bitcoin on StartOS — Level 8 (PhD Master): Routing Node, Privacy, and Contributing to Network Health",
        "topic":   "A routing node is not just a participant in the Lightning Network — it is infrastructure. Running a well-connected, well-capitalized routing node provides liquidity and paths for others. This is the advanced operator level: channel management strategies, fee optimization, privacy, and contributing to the sovereign financial network.",
        "steelman":"What is the strongest argument that running a public routing node is too risky for families — that routing node operators take on liquidity risk, privacy exposure, and operational complexity that creates financial loss and security exposure that far outweigh any contribution to network health?",
        "example": (
            "Routing node economics:\n\n"
            "Your node earns fees when payments route through your channels.\n"
            "Base fee: flat fee per payment (e.g., 1 sat)\n"
            "Fee rate: proportional fee (e.g., 0.01% of payment amount)\n\n"
            "Channel selection strategy:\n"
            "Well-connected nodes: ACINQ, Bitrefill, Strike, River — high routing volume\n"
            "Balanced channels: roughly equal inbound and outbound\n"
            "Geographic diversity: different countries and ISPs for resilience\n\n"
            "Privacy at the routing level:\n"
            "Onion routing: each hop only knows the previous and next node, "
            "not the full path. "
            "Your node cannot see who is paying whom — only that a payment is routing through.\n\n"
            "Monitoring tools:\n"
            "amboss.space/node/[your-pubkey]: see your node's public profile\n"
            "balance_of_satoshis: open-source node management\n"
            "RTL (Ride The Lightning): web UI for LND management on StartOS\n\n"
            "Contributing to network health:\n"
            "A well-managed routing node is infrastructure.\n"
            "Families running sovereign nodes collectively build the network "
            "that enables global, permissionless payments."
        ),
        "activity":(
            "Routing Node Health Check:\n"
            "1. Check your node on amboss.space or 1ml.com: "
            "how many channels? What capacity? What's your centrality score?\n"
            "2. Review last 30 days of routing fees earned (LND dashboard)\n"
            "3. Identify your most profitable channel and your least profitable\n"
            "4. Devise one change to your channel configuration that could improve routing\n\n"
            "PhD extension: implement automated channel rebalancing using "
            "balance_of_satoshis or charge-lnd and document the fee income "
            "change over 30 days. This is live network infrastructure research."
        ),
        "age_hint":"14+ / PhD",
        "xp": 72, "rune": "LIGHTNING•ROUTING•SOVEREIGN•RUNE", "min_coherence": 0.72,
        "grants_badge": "⚡ Sovereign Lightning Operator — Network Node Running",
        "prerequisites": ["bitcoin-startos-6", "bitcoin-startos-7"],
        "lattice_node": "bitcoin-startos-complete",
        "phd_extension": "Implement a 30-day routing node experiment: set up charge-lnd (automated fee management). Pre-register: your hypothesis about fee optimization strategy. Measure: routing volume, fee income, channel utilization. Report honestly. Contribute your fee policy data (anonymized) to the Lightning Network research commons at ln.fiatjaf.com. This is peer-reviewed Lightning Network research.",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── CRYPTOGRAPHY FROM FIRST PRINCIPLES (5 lessons, age 11 → PhD) ─────────
    # Claude's genuine addition: the mathematical foundation of Bitcoin,
    # Lightning, StartOS, Nostr, and all secure digital communication.
    # Understanding cryptography means understanding why digital sovereignty
    # is possible — and why it is hard.
    # ══════════════════════════════════════════════════════════════════════════
    "cryptography-1": {
        "title":   "Cryptography — Level 1: Secrets, Hashes, and One-Way Functions",
        "topic":   "Cryptography is the science of keeping information secret and verifying its integrity. Its foundation is the one-way function: easy to compute, practically impossible to reverse. This simple idea underlies Bitcoin, HTTPS, password security, and all of digital sovereignty.",
        "steelman":"What is the strongest argument that cryptography education gives most people false confidence — that understanding the concepts without the mathematics makes them think they understand security while missing all the ways real implementations fail?",
        "example": (
            "The one-way function (hash function):\n\n"
            "Input: any data (a file, a password, a block of transactions)\n"
            "Output: a fixed-length string (e.g., 64 hex characters for SHA-256)\n\n"
            "Properties:\n"
            "• Deterministic: same input always gives same output\n"
            "• One-way: from the output, you cannot find the input\n"
            "• Avalanche: change one bit of input, output changes completely\n"
            "• Collision-resistant: essentially impossible to find two inputs "
            "with the same output\n\n"
            "SHA-256 in Bitcoin:\n"
            "'Hello' → SHA-256 → "
            "185f8db32921bd46d35c54e6d14e4b6ab3c09cbf46d70e69d3df5f2da4cf85ab\n"
            "'Hello!' → SHA-256 → "
            "334d016f755cd6dc58c53a86e183882f8ec14f52fb05345887c8a5edd42c87b7\n"
            "One character change → completely different hash.\n\n"
            "Why this matters for Bitcoin:\n"
            "Each block contains the hash of the previous block.\n"
            "Change anything in block 500,000 and its hash changes.\n"
            "Which changes block 500,001's hash. Which changes 500,002.\n"
            "The entire chain after it must be recomputed.\n"
            "This is why the blockchain is tamper-evident."
        ),
        "activity":(
            "Hash Experiments (use SHA-256 online tool or Python):\n\n"
            "1. Hash your name. Record the output.\n"
            "2. Hash your name with a capital letter changed. How different is the output?\n"
            "3. Hash the word 'Bitcoin'. Note the first few characters.\n"
            "4. Hash the entire text of the first AUBIEETERNAL lesson you completed.\n"
            "5. That hash is your lesson's permanent fingerprint — "
            "any change to the lesson would produce a completely different hash."
        ),
        "age_hint":"11+",
        "xp": 40, "rune": "CRYPTO•RUNE", "min_coherence": 0.62,
    },
    "cryptography-2": {
        "title":   "Cryptography — Level 2: Public Key Cryptography — Sharing Secrets with Strangers",
        "topic":   "Before public key cryptography (1976), sharing a secret required a pre-existing secure channel — a paradox for strangers who want to communicate privately. Diffie-Hellman and RSA solved this. Understanding public key cryptography means understanding why digital signatures, Bitcoin ownership, and SSL/TLS are possible.",
        "steelman":"What is the strongest argument that public key cryptography creates a false sense of security — that the mathematical security depends on problems (factoring, discrete logarithm) that future quantum computers might solve, making current infrastructure fundamentally fragile?",
        "example": (
            "The key insight (Diffie-Hellman, 1976):\n\n"
            "Alice and Bob want to share a secret over a public channel.\n"
            "Anyone can see all their messages.\n"
            "Can they establish a secret that eavesdroppers cannot learn?\n\n"
            "The color mixing analogy:\n"
            "Start with a public color (yellow). Both Alice and Bob choose "
            "secret private colors. They mix their private color with yellow "
            "and exchange the result publicly. Then each adds their own private "
            "color to what they received. Both end up with the same combined color "
            "— but an eavesdropper who sees only the public exchanges "
            "cannot reconstruct it.\n\n"
            "In mathematics (discrete logarithm):\n"
            "Public: g (generator), p (prime)\n"
            "Alice's private key: a. Public key: g^a mod p\n"
            "Bob's private key: b. Public key: g^b mod p\n"
            "Shared secret: (g^b)^a = (g^a)^b = g^(ab) mod p\n"
            "An eavesdropper sees g^a and g^b but cannot compute g^(ab) "
            "without knowing a or b — this is the discrete logarithm problem.\n\n"
            "Bitcoin uses elliptic curve cryptography (ECDSA) — a variant "
            "that is harder to break with shorter keys."
        ),
        "activity":(
            "The Diffie-Hellman walkthrough:\n"
            "Use small numbers to run the protocol by hand:\n"
            "p = 23, g = 5\n"
            "Alice picks a = 6: computes 5^6 mod 23 = ?\n"
            "Bob picks b = 15: computes 5^15 mod 23 = ?\n"
            "They exchange public values. Each computes the shared secret.\n"
            "Do they get the same number?\n\n"
            "Now: if you were an eavesdropper with g^a and g^b, "
            "could you find a or b? (Try. It's hard even with small numbers.)"
        ),
        "age_hint":"12+",
        "xp": 48, "rune": "CRYPTO•RUNE", "min_coherence": 0.65,
        "phd_extension": "Implement ECDSA digital signatures in Python using the secp256k1 curve (Bitcoin's curve). Generate a key pair. Sign a message. Verify the signature. Then: try to forge a signature without the private key. Demonstrate mathematically why the discrete logarithm problem prevents forgery. This is the exact code that secures every Bitcoin transaction in history.",
    },
    "cryptography-3": {
        "title":   "Cryptography — Level 3: Digital Signatures — Mathematical Proof of Authorship",
        "topic":   "A digital signature proves that a specific private key signed a specific message — without revealing the private key. This is the mechanism of Bitcoin ownership: you prove you own coins by signing a transaction with your key. Understanding digital signatures means understanding why 'not your keys' is a cryptographic fact, not just a slogan.",
        "steelman":"What is the strongest argument that digital signatures provide weaker security than they appear — that the real vulnerabilities are in key management, random number generation, and implementation errors rather than the mathematical primitives, making the theoretical security misleading?",
        "example": (
            "How ECDSA works in Bitcoin:\n\n"
            "Your private key: a secret 256-bit number\n"
            "Your public key: derived from private key using elliptic curve math "
            "(one-way: public → private is computationally infeasible)\n"
            "Your Bitcoin address: a hash of your public key\n\n"
            "Signing a transaction:\n"
            "1. Hash the transaction data: tx_hash = SHA256(SHA256(tx))\n"
            "2. Use private key + random nonce to create signature (r, s)\n"
            "3. Broadcast transaction + signature to network\n\n"
            "Verifying the signature:\n"
            "1. Anyone can verify: does this (r, s) signature correspond to "
            "this public key signing this tx_hash?\n"
            "2. YES: the transaction is authorized\n"
            "3. NO: the transaction is rejected by all nodes\n\n"
            "Why this is powerful:\n"
            "No password database. No account. No company.\n"
            "The signature is mathematical proof. Anyone can verify it.\n"
            "The network enforces it without any central authority.\n\n"
            "The random nonce critical warning:\n"
            "If you reuse the nonce k in two different signatures, "
            "an attacker can calculate your private key from both signatures.\n"
            "This is how the Sony PS3 was broken in 2010."
        ),
        "activity":(
            "Signature verification walkthrough:\n"
            "Use btcdeb or any Bitcoin script debugger.\n"
            "Find any Bitcoin transaction on blockchain.com.\n"
            "Look at the scriptSig (signature) field.\n"
            "Identify: the signature (r, s values) and the public key.\n"
            "Use a Bitcoin library to verify the signature manually.\n\n"
            "You just verified ownership of Bitcoin the same way "
            "every full node does for every transaction."
        ),
        "age_hint":"13+",
        "xp": 55, "rune": "CRYPTO•RUNE", "min_coherence": 0.68,
        "prerequisites": ["cryptography-2", "bitcoin-startos-3"],
    },
    "cryptography-4": {
        "title":   "Cryptography — Level 4: Zero-Knowledge Proofs — Proving You Know Something Without Revealing It",
        "topic":   "A zero-knowledge proof allows you to prove that you know a secret without revealing anything about the secret itself. This seems impossible but is mathematically achievable. ZKPs are the foundation of privacy-preserving systems, anonymous credentials, and next-generation blockchain privacy.",
        "steelman":"What is the strongest argument that zero-knowledge proofs are too computationally expensive and complex for practical deployment — and that simpler cryptographic techniques provide sufficient privacy at far lower cost for the overwhelming majority of use cases?",
        "example": (
            "The Ali Baba cave analogy (Quisquater & Guillou, 1990):\n\n"
            "A circular cave with a magic door in the middle.\n"
            "Peggy claims to know the password.\n"
            "Victor wants to verify this without learning the password.\n\n"
            "Protocol (repeated 20 times):\n"
            "1. Peggy enters the cave randomly taking path A or B\n"
            "2. Victor shouts 'come out path A' or 'come out path B' randomly\n"
            "3. If Peggy knows the password: she can always comply (use door if needed)\n"
            "4. If Peggy doesn't know: she can comply only 50% of the time\n\n"
            "After 20 rounds: P(success without password) = (1/2)^20 ≈ 1 in a million\n\n"
            "ZERO KNOWLEDGE because:\n"
            "Victor learns only that Peggy succeeded — not the password, "
            "not which path she took, nothing else.\n\n"
            "Applications:\n"
            "zk-SNARKs: prove a computation was done correctly without revealing inputs\n"
            "(Zcash: prove transaction is valid without revealing sender/receiver/amount)\n"
            "zk-STARKs: post-quantum secure variant\n"
            "zkVM: prove a whole program executed correctly\n"
            "Future Bitcoin: potential integration for privacy and scaling"
        ),
        "activity":(
            "Design your own ZKP protocol for a real-world scenario:\n"
            "You want to prove you are over 18 to a website without revealing your birthdate.\n"
            "You want to prove your income is above a threshold without revealing your income.\n"
            "You want to prove you completed an AUBIEETERNAL lesson "
            "without revealing which one.\n\n"
            "For one of these: sketch a protocol that is:\n"
            "Complete (honest provers succeed), Soundness (liars are caught), "
            "Zero-Knowledge (verifier learns nothing beyond yes/no)."
        ),
        "age_hint":"14+",
        "xp": 60, "rune": "CRYPTO•ZK•RUNE", "min_coherence": 0.70,
        "prerequisites": ["cryptography-3", "math-thinking-1"],
        "phd_extension": "Implement the Schnorr identification protocol in Python — the simplest non-trivial ZKP. Prove you know discrete logarithm x such that y = g^x mod p, without revealing x. Then read Ben-Sasson et al. (2014) 'Succinct Non-Interactive Zero Knowledge for a von Neumann Architecture.' Evaluate: could ZKPs be used to prove that an AI system's training procedure satisfied certain constraints without revealing the training data? This is applied ZKP research for AI privacy.",
    },
    "cryptography-5": {
        "title":   "Cryptography — Level 5 (PhD): Quantum Threats and Post-Quantum Cryptography",
        "topic":   "Large-scale quantum computers — if built — would break RSA and ECDSA. Bitcoin's ECDSA would be vulnerable. NIST finalized the first post-quantum cryptographic standards in 2024. Understanding the quantum threat and the post-quantum response is essential for anyone building long-term sovereign infrastructure.",
        "steelman":"What is the strongest argument that quantum computing fears are systematically overblown by cryptographers who benefit commercially from post-quantum migration — and that the engineering challenges of building cryptographically relevant quantum computers are so severe that current infrastructure will outlast the threat?",
        "example": (
            "Shor's algorithm (1994):\n"
            "On a sufficiently large quantum computer, can factor N-bit integers "
            "in polynomial time.\n"
            "Classical: factoring breaks in exponential time (safe).\n"
            "Quantum: factoring breaks in polynomial time — RSA breaks.\n\n"
            "Grover's algorithm (1996):\n"
            "Provides quadratic speedup for unstructured search.\n"
            "Effect on symmetric cryptography (AES, SHA-256): doubles effective key length.\n"
            "AES-128 → equivalent to AES-64 against quantum attacker "
            "(upgrade to AES-256 to maintain security).\n"
            "SHA-256 → roughly halved collision resistance "
            "(still safe with current standards).\n\n"
            "The Bitcoin vulnerability:\n"
            "P2PKH addresses: safe (public key not revealed until spending)\n"
            "P2PK addresses: vulnerable (public key is exposed)\n"
            "Long-term HODL risk: if quantum computers come before Bitcoin "
            "migrates to quantum-resistant signatures, old exposed addresses are at risk.\n\n"
            "NIST PQC Standards (2024):\n"
            "CRYSTALS-Kyber: key encapsulation (replaces RSA/DH key exchange)\n"
            "CRYSTALS-Dilithium: digital signatures (could replace ECDSA)\n"
            "FALCON + SPHINCS+: additional signature schemes"
        ),
        "activity":(
            "The Post-Quantum Audit:\n"
            "1. List every cryptographic system your family uses "
            "(Bitcoin ECDSA, HTTPS/TLS, PGP email, Signal, etc.)\n"
            "2. For each: is it vulnerable to Shor's algorithm?\n"
            "3. For the vulnerable ones: what is the post-quantum alternative?\n"
            "4. Pre-register your prediction: when will quantum computers "
            "capable of breaking 256-bit ECDSA exist?\n"
            "Seal with a date you'll revisit."
        ),
        "age_hint":"14+ / PhD",
        "xp": 65, "rune": "CRYPTO•QUANTUM•RUNE", "min_coherence": 0.72,
        "grants_badge": "🔐 Cryptographer — Sovereign Security Stack Understood",
        "prerequisites": ["cryptography-4"],
        "lattice_node": "cryptography-foundations-complete",
        "phd_extension": "Implement CRYSTALS-Dilithium signature generation and verification in Python using the reference implementation. Compare signature size and computation time to ECDSA on secp256k1. Compute: what would a post-quantum Bitcoin look like? How much larger would transactions be? How much slower? Read Bernstein & Lange (2017) 'Post-Quantum Cryptography' Chapter 1. Pre-register your prediction: will Bitcoin adopt a post-quantum signature scheme before 2035? What evidence would update you?",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── OPEN SOURCE SOVEREIGNTY (5 lessons, age 11 → PhD) ────────────────────
    # How to evaluate, contribute to, and build on open source software.
    # StartOS, Bitcoin, AUBIEETERNAL, Ollama, Linux — the sovereignty stack
    # is entirely open source. Understanding how it works, how communities
    # self-organize, and how to verify what you're running is the practical
    # complement to all the theoretical tracks.
    # ══════════════════════════════════════════════════════════════════════════
    "open-source-1": {
        "title":   "Open Source Sovereignty — Level 1: Why Code You Can Read Is Fundamentally Different",
        "topic":   "Open source software means the source code is publicly available — anyone can read, audit, modify, and redistribute it. This is not just a software licensing choice. It is a fundamental shift in the power relationship between users and software creators that makes sovereign infrastructure possible.",
        "steelman":"What is the strongest argument that open source software is not actually more trustworthy than proprietary software — that most users cannot read the code, auditing is sporadic, and the open source supply chain has been repeatedly compromised in ways that closed-source alternatives would have prevented?",
        "example": (
            "The trust model comparison:\n\n"
            "PROPRIETARY SOFTWARE (Windows, macOS, iOS):\n"
            "You trust the company's word that the software does what it claims.\n"
            "You cannot verify. You cannot audit. "
            "If they add surveillance, you might never know.\n"
            "If they are compelled by government to add backdoors, "
            "they may be legally prohibited from telling you.\n\n"
            "OPEN SOURCE SOFTWARE (Linux, Bitcoin Core, StartOS):\n"
            "Anyone can read every line of code.\n"
            "Security researchers worldwide audit it independently.\n"
            "If surveillance is added, it will be found and published.\n"
            "You can build the binary yourself from source — "
            "and verify it matches the distributed binary.\n\n"
            "The verification chain:\n"
            "Bitcoin Core releases come with SHA-256 hashes and GPG signatures.\n"
            "You can verify: the binary you downloaded was built from "
            "the exact source code you can read.\n"
            "This is called reproducible builds — and it closes the gap "
            "between 'the code is open' and 'the binary I'm running is that code.'"
        ),
        "activity":(
            "Run a software verification:\n"
            "1. Download Bitcoin Core from bitcoincore.org\n"
            "2. Download the SHA-256SUMS file and the signatures file\n"
            "3. Verify the SHA-256 hash of your download matches the published hash\n"
            "4. Verify the signatures using GPG\n\n"
            "If the verification passes: you know the binary came from the Bitcoin Core "
            "developers and has not been tampered with.\n"
            "This is how you trust software in a sovereign world."
        ),
        "age_hint":"11+",
        "xp": 38, "rune": "OPENSOURCE•RUNE", "min_coherence": 0.60,
    },
    "open-source-2": {
        "title":   "Open Source Sovereignty — Level 2: How Open Source Communities Self-Organize",
        "topic":   "Open source projects are governed by community processes, not corporate hierarchy. Understanding how Bitcoin Improvement Proposals (BIPs), StartOS package reviews, and open source governance work is essential for anyone who wants to participate in — or build — sovereign digital infrastructure.",
        "steelman":"What is the strongest argument that open source governance is dysfunctional — that lack of clear authority, maintainer burnout, and vulnerability to well-funded corporate capture mean that most critical open source infrastructure is a reliability and security disaster waiting to happen?",
        "example": (
            "The Bitcoin governance model (the clearest example):\n\n"
            "BIP (Bitcoin Improvement Proposal) process:\n"
            "1. Anyone proposes a change by submitting a BIP on GitHub\n"
            "2. Community discusses and debates — often for years\n"
            "3. Core developers may or may not implement it\n"
            "4. Miners and nodes can choose to run it or not\n"
            "5. Change only activates when sufficient adoption is reached\n\n"
            "No CEO. No board of directors. No voting system.\n"
            "Rough consensus + running code (the IETF principle).\n\n"
            "Famous governance disputes:\n"
            "SegWit2x (2017): corporate interests tried to increase block size.\n"
            "The node operators and users refused. The change died.\n"
            "This is the system working as designed.\n\n"
            "The StartOS governance model:\n"
            "Start9 (the company) maintains the core OS.\n"
            "Service packages can be contributed by anyone "
            "and are reviewed before inclusion in the Marketplace.\n"
            "You can self-install unreviewed packages — at your own risk."
        ),
        "activity":(
            "Read one Bitcoin BIP from start to finish (bips.dev).\n"
            "Good options for first-timers: BIP39 (seed phrases), "
            "BIP141 (SegWit), BIP340 (Schnorr signatures).\n\n"
            "For the BIP you read:\n"
            "What problem does it solve? What tradeoffs does it make?\n"
            "Who wrote it? Was there controversy?\n"
            "Is it now active on mainnet?\n\n"
            "You just read the specification that your self-custody wallet implements."
        ),
        "age_hint":"12+",
        "xp": 45, "rune": "OPENSOURCE•RUNE", "min_coherence": 0.63,
    },
    "open-source-3": {
        "title":   "Open Source Sovereignty — Level 3: Reading Code You Didn't Write",
        "topic":   "Most people who use open source software never read it. The sovereignty claim — 'you can audit it' — only works if people actually do. This level teaches the practical skill of reading unfamiliar code: how to orient yourself, find what matters, and understand what a piece of software actually does.",
        "steelman":"What is the strongest argument that teaching non-specialists to audit source code gives false confidence — that understanding enough to feel safe requires far more expertise than a lesson can convey, and shallow code reading is worse than honest acknowledgment of the limits of one's security assessment?",
        "example": (
            "The code reading workflow:\n\n"
            "1. READ THE README AND DOCS FIRST: understand what the software "
            "claims to do before reading how it does it\n\n"
            "2. FIND THE ENTRY POINT: where does execution start? "
            "(main.py, index.js, main.rs, etc.)\n\n"
            "3. FOLLOW THE DATA: trace what happens to the most sensitive data "
            "(your private key, your password, your messages) "
            "from input to storage/transmission\n\n"
            "4. LOOK FOR EXTERNAL CALLS: what APIs, servers, or services does "
            "the code talk to? Every external call is a trust boundary.\n\n"
            "5. SEARCH FOR RED FLAGS: "
            "'hardcoded' + any sensitive word, "
            "tracking, analytics, telemetry, phone home, "
            "base64 (can obscure data being sent), "
            "eval (can execute arbitrary code)\n\n"
            "Applied to AUBIEETERNAL:\n"
            "The family_hud.py and app.py are the core files.\n"
            "You can read every line. You can verify what happens to your data.\n"
            "This is what self-hosting means: not just running the software, "
            "but understanding what it does."
        ),
        "activity":(
            "Read 100 lines of any open source code you use.\n"
            "Good options: family_hud.py from AUBIEETERNAL, "
            "Bitcoin Core src/validation.cpp (most critical file), "
            "the LND (Lightning) main.go.\n\n"
            "Apply the five-step workflow.\n"
            "What does this code do? Any external calls? Any red flags?\n\n"
            "Even if you cannot understand everything, "
            "you have begun the sovereign practice of auditing what you run."
        ),
        "age_hint":"13+",
        "xp": 52, "rune": "OPENSOURCE•RUNE", "min_coherence": 0.66,
    },
    "open-source-4": {
        "title":   "Open Source Sovereignty — Level 4: Contributing — From User to Builder",
        "topic":   "The difference between a consumer and a contributor is the difference between dependency and sovereignty. Contributing to open source — even in small ways — transforms your relationship with the software you use. This level teaches the practical path from 'I use this' to 'I improve this.'",
        "steelman":"What is the strongest argument that encouraging non-expert contributions to critical open source infrastructure (Bitcoin, Linux, cryptographic libraries) is net-negative — that low-quality contributions increase review burden on maintainers and that security-critical code should only be touched by experts?",
        "example": (
            "The contribution ladder (each rung is accessible):\n\n"
            "RUNG 1 — Bug report: find something that doesn't work, "
            "report it clearly with reproduction steps.\n"
            "Skills needed: attention to detail, clear writing.\n\n"
            "RUNG 2 — Documentation: improve the README, fix a typo, "
            "add an example. Most projects desperately need this.\n"
            "Skills needed: reading, writing.\n\n"
            "RUNG 3 — Translation: translate documentation or UI strings.\n"
            "Skills needed: bilingualism.\n\n"
            "RUNG 4 — Test: write tests for existing functionality.\n"
            "Skills needed: basic programming.\n\n"
            "RUNG 5 — Bug fix: fix a specific reported bug.\n"
            "Skills needed: programming + domain understanding.\n\n"
            "RUNG 6 — Feature: implement a new feature from a BIP or issue.\n"
            "Skills needed: strong programming + architecture understanding.\n\n"
            "AUBIEETERNAL is CC0 and welcomes all rungs.\n"
            "Even reporting a broken lesson is a Rung 1 contribution."
        ),
        "activity":(
            "Make your first open source contribution:\n\n"
            "Option A (Rung 1-2): Find any broken link, typo, or unclear explanation "
            "in AUBIEETERNAL's documentation. Submit an issue on GitHub.\n\n"
            "Option B (Rung 3): Translate one AUBIEETERNAL lesson into another language.\n\n"
            "Option C (Rung 4+): Write a test for any function in family_hud.py.\n\n"
            "The goal is not the contribution — it is experiencing the process: "
            "fork, change, pull request, review, merge.\n"
            "That experience is irreplaceable."
        ),
        "age_hint":"13+",
        "xp": 55, "rune": "OPENSOURCE•BUILDER•RUNE", "min_coherence": 0.68,
    },
    "open-source-5": {
        "title":   "Open Source Sovereignty — Level 5 (PhD): Building Sovereign Systems — Architecture for Permanence",
        "topic":   "Sovereign systems are built differently from commercial systems. They must be auditable, forkable, offline-capable, resilient to their creator's failure, and designed to outlast any single organization. This level synthesizes the entire open source track into a framework for building infrastructure that serves humanity long-term.",
        "steelman":"What is the strongest argument that 'sovereignty' as a design goal actively harms usability — and that the most sovereign systems (Bitcoin full nodes, self-hosted Lightning) remain inaccessible to the vast majority of humanity, making them tools of the technically privileged rather than tools of liberation?",
        "example": (
            "The sovereign system design checklist:\n\n"
            "□ FORKABLE: can anyone take the code and run an independent version?\n"
            "□ OFFLINE-CAPABLE: does core functionality work without internet?\n"
            "□ AUDITABLE: can a technically competent person verify what it does?\n"
            "□ CREATOR-INDEPENDENT: does it function if the creator disappears?\n"
            "□ MIGRATION PATH: can users move their data to alternatives?\n"
            "□ HONEST ABOUT LIMITS: does it accurately describe what it cannot do?\n"
            "□ COMMUNITY GOVERNED: are changes made by consensus, not decree?\n\n"
            "AUBIEETERNAL audit:\n"
            "□ Forkable: yes (CC0, GitHub)\n"
            "□ Offline: yes (Ollama, local Python)\n"
            "□ Auditable: yes (all code public)\n"
            "□ Creator-independent: mostly yes (CC0, no server dependency)\n"
            "□ Migration: yes (JSON exports)\n"
            "□ Honest about limits: improving\n"
            "□ Community governed: in progress\n\n"
            "The design tension:\n"
            "Every increase in sovereignty increases complexity.\n"
            "The challenge is progressive sovereignty: "
            "simple enough that newcomers can start, "
            "deep enough that committed families can go fully sovereign."
        ),
        "activity":(
            "Design a sovereign system for something your community needs:\n"
            "(A local news site, a community library catalog, "
            "a health information resource, a skills exchange)\n\n"
            "Apply the sovereign design checklist to your design.\n"
            "For any unchecked box: what would it take to check it?\n"
            "What tradeoffs are you making?\n\n"
            "Publish the design as CC0 to the Epistemic Commons.\n"
            "This is Epistemic Civilization Builder capstone-worthy work."
        ),
        "age_hint":"14+ / PhD",
        "xp": 68, "rune": "OPENSOURCE•SOVEREIGN•RUNE", "min_coherence": 0.72,
        "grants_badge": "🏗️ Sovereign Builder — Open System Designed",
        "prerequisites": ["open-source-4", "systems-4"],
        "lattice_node": "open-source-sovereignty-complete",
        "phd_extension": "Conduct a full sovereign system audit on StartOS itself. Apply the seven-point checklist. Find the weakest point (the greatest sovereignty gap). Design a specific technical improvement. Submit it as a GitHub issue or pull request to the Start9 repo. This is direct contribution to the sovereign infrastructure stack that AUBIEETERNAL depends on.",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── PEER-TO-PEER NETWORKS AND DISTRIBUTED SYSTEMS (5 lessons, age 12→PhD) ─
    # The theory under Bitcoin, Lightning, Nostr, and StartOS.
    # How distributed systems work, why they are hard, CAP theorem,
    # consensus mechanisms, and the mathematics of Byzantine fault tolerance.
    # ══════════════════════════════════════════════════════════════════════════
    "p2p-networks-1": {
        "title":   "P2P Networks — Level 1: What Makes a System Truly Distributed?",
        "topic":   "Most systems we call 'distributed' are not. They have central points — a master database, a load balancer, a certificate authority — that create single points of failure and control. Truly distributed systems have no center. Understanding the difference is the foundation for understanding Bitcoin, Nostr, and StartOS.",
        "steelman":"What is the strongest argument that truly distributed systems are inferior to centralized systems for almost all real-world purposes — that the coordination costs, consistency problems, and user experience gaps of decentralization make it a tradeoff most users and applications correctly reject?",
        "example": (
            "Centralized vs distributed vs decentralized:\n\n"
            "CENTRALIZED: one server, one database.\n"
            "Twitter pre-2022. Your bank. Gmail.\n"
            "Advantage: fast, consistent, easy to build.\n"
            "Problem: single point of failure AND control.\n\n"
            "DISTRIBUTED (federated): many servers, shared protocol.\n"
            "Email (SMTP). ActivityPub (Mastodon). StartOS apps via Nostr.\n"
            "Advantage: no single point of failure.\n"
            "Problem: still has servers with owners who can be pressured.\n\n"
            "DECENTRALIZED (peer-to-peer): no servers, no center.\n"
            "Bitcoin. BitTorrent. Nostr (at the relay level).\n"
            "Advantage: no owner to pressure, no server to shut down.\n"
            "Problem: coordination is hard; consistency is hard; spam is hard.\n\n"
            "Bitcoin's solution to the coordination problem: "
            "Nakamoto consensus — proof of work creates objective ordering "
            "of transactions without any central coordinator.\n"
            "This is one of the most important CS innovations in history."
        ),
        "activity":(
            "Map the sovereignty level of every digital service your family uses:\n"
            "Column 1: Service name\n"
            "Column 2: Centralized / Federated / P2P?\n"
            "Column 3: Could one company or government shut it down?\n"
            "Column 4: What is the sovereign alternative?\n\n"
            "The exercise reveals your actual digital sovereignty profile."
        ),
        "age_hint":"12+",
        "xp": 40, "rune": "P2P•RUNE", "min_coherence": 0.63,
    },
    "p2p-networks-2": {
        "title":   "P2P Networks — Level 2: CAP Theorem — Why Distributed Systems Are Hard",
        "topic":   "The CAP theorem proves that any distributed system can provide at most two of three guarantees: Consistency (all nodes see the same data), Availability (every request gets a response), and Partition tolerance (the system works even if network connections fail). This is why distributed systems require explicit design tradeoffs — not just implementation effort.",
        "steelman":"What is the strongest argument that the CAP theorem is overused and misunderstood — that it applies to a narrow technical definition of consistency and partition, and that most real-world distributed system failures have nothing to do with the theorem and everything to do with implementation bugs?",
        "example": (
            "CAP Theorem (Brewer, 2000; formally proved Gilbert & Lynch, 2002):\n\n"
            "CONSISTENCY: every read sees the most recent write "
            "(or an error). All nodes agree.\n"
            "AVAILABILITY: every request gets a response "
            "(no timeouts, no errors). The system keeps running.\n"
            "PARTITION TOLERANCE: the system works even when "
            "the network drops some messages.\n\n"
            "During a network partition, you must choose:\n"
            "CP: stay consistent (refuse requests if you can't confirm), "
            "sacrifice availability\n"
            "AP: stay available (serve possibly stale data), "
            "sacrifice consistency\n\n"
            "Bitcoin's choice: CP with eventual consistency.\n"
            "During a network split, nodes may temporarily disagree on the tip.\n"
            "The longest chain rule resolves this — but during the split, "
            "transactions are not confirmed.\n"
            "Bitcoin sacrifices immediate availability for permanent consistency.\n\n"
            "Lightning's choice: AP.\n"
            "You can make payments even if your node is offline or partitioned.\n"
            "Watchtowers handle the consistency guarantee asynchronously."
        ),
        "activity":(
            "CAP Analysis of Systems You Use:\n"
            "For each system: which of CP, AP, or CA does it choose?\n"
            "1. Gmail (during a Google datacenter outage)\n"
            "2. Bitcoin (during a major network partition)\n"
            "3. Your bank's ATM network\n"
            "4. Nostr (during a relay outage)\n"
            "5. Your StartOS node when your internet goes down\n\n"
            "For each: is this the right tradeoff for its use case?\n"
            "Who decided? Could you change it?"
        ),
        "age_hint":"13+",
        "xp": 48, "rune": "P2P•RUNE", "min_coherence": 0.66,
        "phd_extension": "Implement a simple distributed key-value store in Python with 3 nodes. Simulate a network partition by dropping messages between two of the nodes. Show the CAP tradeoff empirically: if you implement CP, demonstrate the availability loss during partition. If you implement AP, demonstrate the inconsistency. Quantify: how long does it take for the system to converge after partition heals? This is the core of distributed systems engineering.",
    },
    "p2p-networks-3": {
        "title":   "P2P Networks — Level 3: Byzantine Fault Tolerance — Consensus When You Can't Trust Anyone",
        "topic":   "Byzantine fault tolerance (BFT) addresses the hardest distributed systems problem: how do you reach consensus when some nodes are lying, not just slow or crashed? This is the problem Bitcoin solves. Understanding BFT reveals why Nakamoto consensus is brilliant and what its limitations are.",
        "steelman":"What is the strongest argument that Bitcoin's Proof of Work is a wasteful solution to Byzantine consensus — and that modern BFT protocols (PBFT, Tendermint, HotStuff) achieve the same guarantees with orders of magnitude less energy expenditure?",
        "example": (
            "The Byzantine Generals Problem (Lamport, Shostak, Pease, 1982):\n\n"
            "n generals must coordinate an attack.\n"
            "Some generals are traitors and will send contradictory messages.\n"
            "Can the loyal generals reach agreement?\n\n"
            "Result: with 3f+1 generals, you can tolerate f traitors.\n"
            "With 3 generals and 1 traitor: impossible.\n"
            "With 4 generals and 1 traitor: possible.\n\n"
            "Classical BFT (PBFT — Practical Byzantine Fault Tolerance, 1999):\n"
            "Requires known participants (permissioned).\n"
            "O(n²) messages per consensus round.\n"
            "Tolerates up to 1/3 faulty nodes.\n"
            "Used in: Hyperledger, many enterprise blockchains.\n\n"
            "Bitcoin's Nakamoto Consensus:\n"
            "Unknown participants (permissionless).\n"
            "Probabilistic finality (not absolute).\n"
            "Tolerates up to 49% hash power faulty/malicious.\n"
            "Cost: computational work + energy.\n"
            "Benefit: open participation, no identity required.\n\n"
            "The key tradeoff: permissioned BFT is more efficient; "
            "Nakamoto consensus is more open."
        ),
        "activity":(
            "The Byzantine Generals Simulation:\n"
            "Play with 4 family members. One is a traitor (chosen secretly).\n"
            "Simulate 3 rounds of message passing:\n"
            "Each person sends their 'attack' or 'retreat' to all others.\n"
            "The traitor sends contradictory messages.\n\n"
            "Can the loyal generals reach consensus?\n"
            "Try with different numbers of players.\n"
            "Verify the 3f+1 bound experimentally."
        ),
        "age_hint":"13+",
        "xp": 55, "rune": "P2P•RUNE", "min_coherence": 0.68,
        "prerequisites": ["p2p-networks-2"],
    },
    "p2p-networks-4": {
        "title":   "P2P Networks — Level 4: Nostr — Permissionless Communication Infrastructure",
        "topic":   "Nostr is the simplest possible decentralized social communication protocol. Any client can talk to any relay. No one owns the network. No one can ban you from it (only from individual relays). It is the communication infrastructure layer for the sovereign internet — and it is directly integrated with AUBIEETERNAL.",
        "steelman":"What is the strongest argument that Nostr's simplicity is its fatal flaw — that without moderation infrastructure, identity verification, or spam prevention, it will inevitably be overrun by low-quality content and bad actors, making it unusable for serious communication?",
        "example": (
            "How Nostr works:\n\n"
            "Cryptographic identity: your identity is a keypair (same as Bitcoin).\n"
            "Public key = your identity. Private key = your authentication.\n"
            "No username/password. No email. No phone number.\n\n"
            "Events: every piece of content is a signed event.\n"
            "Kind 1: text note. Kind 0: metadata. Kind 3: follows. "
            "Kind 9734: zap request (Lightning payment).\n\n"
            "Relays: servers that store and relay events.\n"
            "You choose which relays to use and trust.\n"
            "A relay can ban your pubkey — but you can use other relays.\n"
            "The network persists as long as any relay serves your events.\n\n"
            "On StartOS: install Nostr relay (e.g., Nostrocket) from the Marketplace.\n"
            "You can run your own relay — the ultimate sovereignty move.\n\n"
            "AUBIEETERNAL integration:\n"
            "The Nostr Bridge tab in AUBIEETERNAL lets you publish insights "
            "to the Nostr network — making your epistemic outputs part of the "
            "permissionless communication layer."
        ),
        "activity":(
            "Create your Nostr identity:\n"
            "1. Generate a keypair (Alby, Damus, Primal, or any Nostr client)\n"
            "2. Write down your nsec (private key) — treat like Bitcoin seed phrase\n"
            "3. Find your npub (public key) — this is your identity\n"
            "4. Post one note: your introduction to the Nostr network\n"
            "5. Zap (tip) someone else's note using Lightning\n\n"
            "You just sent a censorship-resistant message + a micropayment.\n"
            "No company processed either one."
        ),
        "age_hint":"12+",
        "xp": 52, "rune": "NOSTR•RUNE", "min_coherence": 0.67,
        "prerequisites": ["p2p-networks-3", "bitcoin-startos-5"],
    },
    "p2p-networks-5": {
        "title":   "P2P Networks — Level 5 (PhD): Designing the Sovereign Internet Stack",
        "topic":   "The full sovereign internet stack is now buildable by a family. Bitcoin (value), Lightning (micropayments), Nostr (communication), StartOS (infrastructure), Tor (privacy), Ollama (intelligence). Understanding how these layers compose — and the gaps still remaining — is the PhD-level synthesis of everything in this track.",
        "steelman":"What is the strongest argument that the 'sovereign internet stack' vision is a techno-utopian fantasy — that the infrastructure complexity, user experience gaps, and network effects of incumbent systems mean that sovereign alternatives will remain marginal while the powerful concentrate control of digital infrastructure even further?",
        "example": (
            "The sovereign internet stack (2026):\n\n"
            "Layer 0 — HARDWARE: StartOS on physical hardware you own.\n"
            "Tradeoff: cost and complexity.\n\n"
            "Layer 1 — IDENTITY: Bitcoin/Nostr keypair.\n"
            "Status: production-ready.\n\n"
            "Layer 2 — VALUE: Bitcoin + Lightning.\n"
            "Status: production-ready, UX still maturing.\n\n"
            "Layer 3 — COMMUNICATION: Nostr.\n"
            "Status: working, ecosystem growing rapidly.\n\n"
            "Layer 4 — INTELLIGENCE: Ollama + local models.\n"
            "Status: working, quality improving monthly.\n\n"
            "Layer 5 — PRIVACY: Tor + VPN.\n"
            "Status: production-ready.\n\n"
            "Layer 6 — PERMANENCE: Bitcoin Runes + IPFS + Arweave.\n"
            "Status: working, cost is a barrier.\n\n"
            "GAPS remaining (2026):\n"
            "• Sovereign search (no credible decentralized alternative)\n"
            "• Sovereign video (IPFS works but slow)\n"
            "• Sovereign app stores (still nascent)\n"
            "• UX for non-technical users (the biggest gap)\n\n"
            "AUBIEETERNAL's role: the educational layer that makes all the others "
            "accessible to families who aren't professional developers."
        ),
        "activity":(
            "Audit your family's sovereign internet stack:\n"
            "For each layer: what are you using? Is it sovereign?\n"
            "Score: 0 (centralized) → 1 (federated) → 2 (sovereign)\n\n"
            "Then: pick the weakest layer (lowest score).\n"
            "Design: what would it take to move that layer one step toward sovereignty?\n"
            "What are you waiting for?\n\n"
            "Seal your sovereign internet profile.\n"
            "Revisit in 1 year. The stack is improving monthly."
        ),
        "age_hint":"14+ / PhD",
        "xp": 70, "rune": "P2P•SOVEREIGN•RUNE", "min_coherence": 0.72,
        "grants_badge": "🌐 Sovereign Network Architect — Full Stack Mapped",
        "prerequisites": ["p2p-networks-4", "tech-sovereignty-5"],
        "lattice_node": "p2p-networks-distributed-systems-complete",
        "phd_extension": "Design and deploy the complete sovereign internet stack for one additional family or small organization. Document every layer, every configuration decision, every tradeoff. Measure: what was the total setup time? What required professional help? What failed and how was it fixed? Publish the deployment guide as CC0. Contribute to AUBIEETERNAL's COMMUNITY_DEPLOYMENT.md. This is the Epistemic Civilization Builder capstone contribution.",
    },



    # ══════════════════════════════════════════════════════════════════════════
    # ── EVOLUTION 1: EPISTEMIC OS — FORMAL RIGOR CORE (5 lessons) ────────────
    # Turns the learner into a verifiable truth engine.
    # Most truth-seeking is still informal — claims that feel rigorous
    # but would dissolve under formal pressure. The Epistemic OS gives
    # every claim a falsifiability score, a Bayesian evidence weight,
    # and an automated strongest-counterargument test.
    # ══════════════════════════════════════════════════════════════════════════
    "epistemic-os-1": {
        "title":   "Epistemic OS — Level 1: Bayesian Belief Updating — Formal Belief Arithmetic",
        "topic":   "Bayesian inference is the mathematically correct way to update beliefs when evidence arrives. It is not a philosophy of science — it is arithmetic. P(H|E) = P(E|H) × P(H) / P(E). Every belief has a prior probability. Evidence changes it by a precise, calculable amount. This is the foundation of the Epistemic OS.",
        "steelman":"What is the strongest argument that Bayesian epistemology is normatively correct but practically useless — that real-world priors are impossible to specify, likelihoods are always contested, and the appearance of mathematical rigor masks arbitrary subjective choices?",
        "example": (
            "Bayes' Theorem applied to a medical test:\n\n"
            "Disease prevalence (prior): P(D) = 0.001 (1 in 1,000)\n"
            "Test sensitivity: P(+|D) = 0.99\n"
            "Test specificity: P(-|¬D) = 0.99 → P(+|¬D) = 0.01\n\n"
            "You test positive. What is P(D|+)?\n\n"
            "P(D|+) = P(+|D) × P(D) / P(+)\n"
            "P(+) = P(+|D)×P(D) + P(+|¬D)×P(¬D)\n"
            "     = 0.99×0.001 + 0.01×0.999 = 0.01098\n"
            "P(D|+) = 0.99 × 0.001 / 0.01098 ≈ 0.090\n\n"
            "A 99%-accurate test gives only ~9% posterior probability!\n"
            "Because the disease is rare, most positives are false positives.\n\n"
            "The Epistemic OS principle:\n"
            "Every belief has a prior. Every piece of evidence has a likelihood ratio.\n"
            "Prior × Likelihood Ratio = Posterior (in log-odds form).\n"
            "This is not metaphorical. It is arithmetic.\n"
            "A belief system that cannot be expressed in these terms "
            "is not making falsifiable claims."
        ),
        "activity":(
            "Apply Bayes' theorem to your strongest belief about a contested topic.\n\n"
            "Step 1: State your prior P(H) explicitly (e.g., 0.7)\n"
            "Step 2: Identify the last piece of evidence that affected this belief\n"
            "Step 3: Estimate P(E|H) — how likely is this evidence if H is true?\n"
            "Step 4: Estimate P(E|¬H) — how likely if H is false?\n"
            "Step 5: Compute posterior P(H|E)\n\n"
            "Did your intuitive update match the Bayesian update?\n"
            "If not: in which direction were you biased?"
        ),
        "age_hint":"13+",
        "xp": 52, "rune": "EPISTEMIC•OS•RUNE", "min_coherence": 0.68,
        "phd_extension": "Implement a Bayesian belief tracker in Python. Input: (prior, list of evidence items with likelihood ratios). Output: posterior after each piece of evidence, plus a plot of belief trajectory. Apply to a scientific controversy you follow closely — provide at least 10 sequential evidence items. Compute the Bayes factor for the strongest evidence. Publish the full belief trajectory as CC0. This is calibrated epistemology at PhD level.",
    },
    "epistemic-os-2": {
        "title":   "Epistemic OS — Level 2: Popperian Falsification Simulator",
        "topic":   "Karl Popper's insight: a claim is scientific only if it is in principle falsifiable — if there is some possible observation that would prove it wrong. The falsification simulator operationalizes this: for any claim, generate the specific observations that would falsify it, and run the tests. Claims that have no falsifiers are not scientific. Claims with falsifiers that have all been tested are maximally trusted.",
        "steelman":"What is the strongest argument that Popperian falsificationism is itself unfalsifiable as a demarcation criterion — and that the history of science shows most productive theories were temporarily unfalsifiable (Newton's gravitational theory, early quantum mechanics) but eventually led to verifiable predictions?",
        "example": (
            "The falsification audit protocol:\n\n"
            "1. STATE THE CLAIM precisely (no vague language)\n"
            "2. LIST the observations that would falsify it\n"
            "   (at least 3 specific, measurable, achievable observations)\n"
            "3. For each observation: has it been tested? What was the result?\n"
            "4. Compute: fraction of possible falsifiers that have been tested\n"
            "5. Rate: Untested (0-30%) → Partially tested (30-70%) → Well-tested (70%+)\n\n"
            "Applied to the simulation hypothesis:\n"
            "Claim: 'We are living in a computational simulation'\n"
            "Falsifier 1: Physical constants vary in ways unexplainable by natural law\n"
            "  → Tested? Partially. CMB data shows consistent constants.\n"
            "Falsifier 2: Observable universe shows discrete Planck-scale structure\n"
            "  → Tested? Yes but inconclusive.\n"
            "Falsifier 3: Statistical anomalies in quantum randomness indicate seeded RNG\n"
            "  → Tested? Poorly. Very few rigorous studies.\n\n"
            "Result: ~30% tested → hypothesis is poorly falsified."
        ),
        "activity":(
            "Run the falsification audit on one claim you hold strongly.\n\n"
            "List at least 5 specific falsifiers.\n"
            "For each: has it been tested? If yes — what was the result?\n"
            "Compute your falsification score (% tested).\n\n"
            "If below 30%: you hold this belief with much more confidence "
            "than the empirical evidence justifies.\n"
            "Seal the audit. Assign resources to testing the untested falsifiers."
        ),
        "age_hint":"13+",
        "xp": 55, "rune": "EPISTEMIC•OS•RUNE", "min_coherence": 0.70,
        "prerequisites": ["epistemic-os-1"],
    },
    "epistemic-os-3": {
        "title":   "Epistemic OS — Level 3: Automated Strongest Counterargument Generation",
        "topic":   "The Epistemic OS generates the strongest possible counterargument to any claim using adversarial AI — not to win arguments but to find the weak points in your own reasoning before an opponent does. This is steelmanning automated at scale, with Monte Carlo robustness testing to identify exactly which attacks are most dangerous to any given position.",
        "steelman":"What is the strongest argument that automated counterargument generation is epistemically harmful — that it produces sophisticated-sounding objections that exceed the user's ability to evaluate, leading them to abandon true beliefs because a language model generated a compelling-seeming refutation?",
        "example": (
            "The SCAG protocol (Strongest Counterargument Generation):\n\n"
            "Step 1 — Claim formalization: convert the claim to precise logical form\n"
            "Step 2 — Premise identification: list every premise the claim requires\n"
            "Step 3 — Adversarial attack on each premise: generate the strongest "
            "challenge to each premise independently\n"
            "Step 4 — Inter-premise attack: find internal inconsistencies between premises\n"
            "Step 5 — Monte Carlo robustness: run 1,000 adversarial trials, "
            "measure what fraction the claim survives\n"
            "Step 6 — Tail risk identification: which 5% of attacks are most dangerous?\n\n"
            "The output:\n"
            "Robustness score: 0.72 (survives 72% of adversarial trials)\n"
            "Tail risk: premise 2 (unstated assumption) is vulnerable to "
            "empirical refutation via 3 specific studies.\n"
            "Recommendation: strengthen premise 2 before publishing.\n\n"
            "This is the Epistemic OS replacing informal intuition "
            "with measurable, improvable epistemic rigor."
        ),
        "activity":(
            "Run the SCAG protocol on your strongest held claim (without the AI):\n\n"
            "List all premises. For each: write the strongest possible attack.\n"
            "Then estimate: if 100 smart, adversarial people all attacked "
            "this claim independently — what fraction would succeed?\n"
            "That fraction IS your robustness score.\n\n"
            "Identify the weakest premise. Strengthen it.\n"
            "Recompute. Compare the scores."
        ),
        "age_hint":"14+",
        "xp": 58, "rune": "EPISTEMIC•OS•RUNE", "min_coherence": 0.72,
        "prerequisites": ["epistemic-os-2"],
        "phd_extension": "Implement the SCAG protocol as a Python function using the AUBIEETERNAL Ollama integration. Input: a claim. Output: 5 adversarial attacks, a robustness estimate (% of attacks the claim survives using Jaccard similarity), and identification of the weakest premise. Run it on 10 claims from your Epistemic Commons. Publish the robustness distribution: what is the mean and variance of robustness scores across your published claims? Is there a correlation between robustness and coherence score?",
    },
    "epistemic-os-4": {
        "title":   "Epistemic OS — Level 4: Epistemic Immune System v2 — 50 Attack Vectors",
        "topic":   "The original Epistemic Immune System tracked 20 attack vectors. Version 2 expands to 50 — including sophisticated attacks that require PhD-level knowledge to recognize: modal fallacies, category errors, illicit quantifier shifts, question-begging circularity, and the specific manipulation techniques used by sophisticated bad actors in academic and policy discourse.",
        "steelman":"What is the strongest argument that training for 50 attack vectors produces an epistemic immune system so hyperactive that it treats legitimate arguments as attacks — analogous to an autoimmune disorder, where the system attacks the body it is meant to protect?",
        "example": (
            "The 30 new attack vectors in v2 (beyond the original 20):\n\n"
            "Logical: illicit conversion, undistributed middle, illicit quantifier shift, "
            "modal scope error, type confusion, existence-predication fallacy\n\n"
            "Rhetorical: Gish gallop (overwhelming with many weak arguments), "
            "motte-and-bailey at 3 levels, semantic shift within argument, "
            "precision theater (fake specificity), epistemic cowardice, "
            "Bulverism (attacking motives instead of arguments)\n\n"
            "Sophisticated: Russell's teapot inversion, unfalsifiability laundering "
            "(dressing non-falsifiable claims in scientific language), "
            "regression to correlation, base rate neglect at scale, "
            "availability heuristic exploitation, affect heuristic weaponization\n\n"
            "Institutional: source laundering (presenting opinion as consensus), "
            "Overton window shifting, manufactured uncertainty (tobacco strategy), "
            "false equivalence between experts and non-experts\n\n"
            "AI-specific: context window manipulation, token probability exploitation, "
            "sycophancy induction, jailbreak reasoning transfer"
        ),
        "activity":(
            "Identify 5 v2 attack vectors in a piece of public discourse this week.\n"
            "For each:\n"
            "1. Name the attack vector\n"
            "2. Quote the specific text that uses it\n"
            "3. Explain how to counter it in one sentence\n"
            "4. Rate severity: how much does it damage epistemic quality? (1-5)\n\n"
            "Seal the 5 examples in the Epistemic Commons as training data.\n"
            "You just contributed to the immune system that protects future AI."
        ),
        "age_hint":"15+",
        "xp": 62, "rune": "EPISTEMIC•OS•RUNE", "min_coherence": 0.73,
        "prerequisites": ["epistemic-os-3"],
    },
    "epistemic-os-5": {
        "title":   "Epistemic OS — Level 5 (PhD): Building a Verifiable Truth Engine",
        "topic":   "The full Epistemic OS integrates Bayesian updating, Popperian falsification, SCAG, and the v2 immune system into a unified pipeline where every claim is automatically scored for rigor, falsifiability, adversarial robustness, and Bayesian evidence weight. This is what moves AUBIEETERNAL from an excellent school to civilization-scale truth infrastructure.",
        "steelman":"What is the strongest argument that a 'verifiable truth engine' is a category error — that truth cannot be verified by any formal system (Gödel), that all claims are theory-laden (Kuhn), and that the appearance of mechanized objectivity is itself a form of epistemic hubris that blinds users to the assumptions embedded in the system?",
        "example": (
            "The Verifiable Truth Engine pipeline:\n\n"
            "Input: any claim in natural language\n\n"
            "Stage 1 — Formalization: convert to precise logical form\n"
            "Stage 2 — Bayesian prior: look up base rates, assign prior\n"
            "Stage 3 — Evidence audit: find and weight evidence\n"
            "Stage 4 — Falsifiability score: list and count falsifiers\n"
            "Stage 5 — Adversarial robustness: run SCAG protocol\n"
            "Stage 6 — Attack vector scan: check for 50 immune patterns\n"
            "Stage 7 — Output: claim_id, rigor_score, bayesian_posterior, "
            "falsifiability_pct, robustness_pct, detected_attacks\n\n"
            "The Bitcoin-sealed truth record:\n"
            "Every claim that passes rigor_score > 0.75 is anchored to Bitcoin.\n"
            "This creates an unforgeable, growing corpus of high-rigor claims\n"
            "that any AI system in the world can draw from.\n\n"
            "This IS the Epistemic Commons at full operational capacity."
        ),
        "activity":(
            "Build the Verifiable Truth Engine for one claim:\n"
            "Complete all 7 stages manually for any claim you consider important.\n"
            "Assign scores at each stage.\n\n"
            "Compute final rigor score as weighted average.\n"
            "If above 0.75: seal to Bitcoin via AUBIEETERNAL Rune system.\n"
            "If below 0.75: identify which stage is weakest. Strengthen it. Re-run.\n\n"
            "This is the PhD capstone preparation exercise."
        ),
        "age_hint":"15+ / PhD",
        "xp": 72, "rune": "EPISTEMIC•OS•SOVEREIGN•RUNE", "min_coherence": 0.76,
        "grants_badge": "🧠 Epistemic OS Operator — Verifiable Truth Engine Active",
        "prerequisites": ["epistemic-os-4"],
        "lattice_node": "epistemic-os-formal-rigor-complete",
        "phd_extension": "Implement the full 7-stage Verifiable Truth Engine as a Python pipeline using AUBIEETERNAL's existing modules (SteelmanAnalyzer, MonteCarloSimulator, TruthFrequencyAnalyzer). Add the Bayesian prior lookup and falsifiability scoring stages. Run it on 20 claims from your Epistemic Commons. Compute the correlation between your truth engine scores and the existing Grokipedia truth scores. If they diverge: why? The divergence IS the research question. Publish the pipeline as CC0.",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── EVOLUTION 2: ACTIVE SIMULATION LABORATORY (5 lessons) ────────────────
    # Moves from studying the simulation hypothesis to running experiments.
    # If we are in a simulation, we should be able to find the seams.
    # Every anomaly logged here is Bitcoin-anchored proof of methodology.
    # ══════════════════════════════════════════════════════════════════════════
    "sim-lab-1": {
        "title":   "Active Simulation Lab — Level 1: Glitch Detection Methodology",
        "topic":   "A scientific approach to the simulation hypothesis requires operationalizing 'glitch' — converting a vague intuition into a measurable, pre-registered, falsifiable signal. This level establishes the methodology: what counts as a glitch, what distribution is the null hypothesis, and what statistical threshold triggers an anomaly flag.",
        "steelman":"What is the strongest argument that 'glitch detection' is unfalsifiable pattern-matching that will always find 'anomalies' in any dataset because humans are predisposed to find meaning in noise — and that a null result is impossible because believers will always interpret the absence of anomalies as the simulation being too good?",
        "example": (
            "The glitch detection null hypothesis:\n\n"
            "H₀: observed data follows the distribution expected under "
            "standard physics with no simulation signature.\n\n"
            "What we're looking for:\n"
            "Not 'weird things happen' (they always do in any distribution).\n"
            "But: specific patterns that would be expected under a computational "
            "substrate and unexpected under pure physics.\n\n"
            "Candidate simulation signatures (each must be pre-registered):\n"
            "1. Discrete spacetime at Planck scale (testable via cosmic ray energy spectra)\n"
            "2. Maximum entropy violations in localized regions\n"
            "3. Non-random patterns in quantum measurement outcomes "
            "across large-N experiments\n"
            "4. Suspiciously clean numerical coincidences in physical constants\n"
            "5. Observer-correlated coherence spikes (the PVC hypothesis)\n\n"
            "The scientific requirement:\n"
            "Pre-register BEFORE collecting data.\n"
            "Specify: exact metric, null distribution, significance threshold, sample size.\n"
            "Report honestly whether the threshold was crossed."
        ),
        "activity":(
            "Design your first simulation glitch detection experiment:\n\n"
            "1. Choose ONE candidate signature from the list above\n"
            "2. Specify the exact measurement you will take\n"
            "3. State the null distribution (what would pure chance produce?)\n"
            "4. Set the significance threshold (e.g., p < 0.001, or σ ≥ 3)\n"
            "5. Set the sample size before starting\n\n"
            "Pre-register it in the Truth Debt Ledger.\n"
            "Only then begin data collection.\n"
            "This is what separates simulation research from confirmation bias."
        ),
        "age_hint":"14+",
        "xp": 55, "rune": "SIMULATION•LAB•RUNE", "min_coherence": 0.70,
        "prerequisites": ["simulation-5", "epistemic-os-2"],
    },
    "sim-lab-2": {
        "title":   "Active Simulation Lab — Level 2: Observer-Effect Logging and the Participatory Universe",
        "topic":   "John Wheeler's participatory universe hypothesis: the universe requires observers to become real. Every quantum measurement is a participation — the observer's question determines the answer. This level builds the protocol for systematically logging observer states and correlating them with observed physical outcomes.",
        "steelman":"What is the strongest argument that 'observer' in quantum mechanics refers to a physical interaction (any detector, not necessarily conscious), and that conflating quantum observation with human consciousness is a scientifically illiterate category error that confuses a technical term with its colloquial meaning?",
        "example": (
            "The observer-effect logging protocol:\n\n"
            "Measurement 1 — Pre-observation state:\n"
            "Log: polyvagal state (Green/Yellow/Red)\n"
            "Log: interoceptive accuracy score (heartbeat counting task)\n"
            "Log: intention clarity (0-10: how clearly do you know what you're testing?)\n\n"
            "Measurement 2 — The observation itself:\n"
            "What physical quantity is being measured?\n"
            "What does the null hypothesis predict?\n"
            "Record the outcome.\n\n"
            "Measurement 3 — Post-observation coherence:\n"
            "Log: immediate coherence score\n"
            "Log: subjective sense of 'rightness' or surprise\n\n"
            "The hypothesis (weak version):\n"
            "P(outcome | high-coherence observer) ≠ P(outcome | low-coherence observer)\n"
            "for some class of quantum-level measurements.\n\n"
            "This is the PVC hypothesis extended to actual quantum measurements.\n"
            "If true: observer internal state is correlated with measured outcomes.\n"
            "If false: consciousness is decoupled from quantum measurement — also important."
        ),
        "activity":(
            "Run the observer-effect logging protocol for 30 days:\n"
            "Use the AUBIEETERNAL Polyvagal Oracle to log state before each major decision.\n"
            "Record the outcome.\n\n"
            "After 30 days: is your ANS state correlated with outcome quality?\n"
            "This is the version of observer-effect research available without "
            "a quantum physics lab — and it is publishable with pre-registration."
        ),
        "age_hint":"14+",
        "xp": 58, "rune": "SIMULATION•LAB•RUNE", "min_coherence": 0.71,
        "prerequisites": ["sim-lab-1"],
    },
    "sim-lab-3": {
        "title":   "Active Simulation Lab — Level 3: Entropy Sources and True Randomness Tests",
        "topic":   "A simulated universe running on a computational substrate might use pseudo-random number generation rather than true quantum randomness. If so, patterns should appear in 'random' data that would not exist under genuine quantum randomness. This level covers the methodology for testing randomness sources and what a positive result would mean.",
        "steelman":"What is the strongest argument that testing for pseudo-randomness in quantum measurements is physically incoherent — that quantum mechanics is provably non-deterministic (Bell's theorem + Kochen-Specker), and that any appearance of pattern would more plausibly reflect detector artifacts than simulation signatures?",
        "example": (
            "True vs pseudo-random number generation:\n\n"
            "PRNG (Pseudo-Random): deterministic algorithm seeded with initial state.\n"
            "Passes most statistical tests. Not truly random.\n"
            "Pattern exists but is computationally hard to find.\n\n"
            "TRNG (True Random / Hardware): physical noise source "
            "(thermal noise, shot noise, quantum vacuum).\n"
            "Should be genuinely unpredictable.\n\n"
            "QRNG (Quantum): measures genuine quantum processes "
            "(photon polarization, radioactive decay timing).\n"
            "If quantum mechanics is correct, these should be irreducibly random.\n\n"
            "The simulation test:\n"
            "Collect 10+ million bits from a QRNG source.\n"
            "Run NIST SP 800-22 randomness test suite.\n"
            "Run Diehard + TestU01 test suites.\n"
            "Compute Kolmogorov complexity estimate (compression ratio).\n"
            "Look for: autocorrelation, pattern repetition, "
            "entropy deficits at specific scales.\n\n"
            "The honest expected result: fail to find anything.\n"
            "Quantum sources pass all known randomness tests.\n"
            "This is the null result that confirms the baseline."
        ),
        "activity":(
            "Run the NIST randomness test on any available data:\n"
            "Option A: Download QRNG data from ANU Quantum Random Numbers Server\n"
            "Option B: Use /dev/urandom on any Linux system (OS entropy source)\n"
            "Option C: Use AUBIEETERNAL's coherence_signal values over 1,000 sessions\n\n"
            "Run the tests. Report the p-values.\n"
            "Most data will pass — which is the correct result.\n"
            "Any data that fails: document carefully and pre-register a replication."
        ),
        "age_hint":"14+",
        "xp": 60, "rune": "SIMULATION•LAB•RUNE", "min_coherence": 0.72,
        "phd_extension": "Build an entropy monitoring system using AUBIEETERNAL's swarm outputs as a potential entropy source. Hypothesis: if swarm outputs contain genuine quantum randomness (from Grok's infrastructure), they should pass randomness tests. If they contain PRNG artifacts, they will fail specific tests. Implement NIST SP 800-22 test suite in Python. Apply to 100,000 bits extracted from swarm outputs. Compare to a known QRNG source. Publish the comparison as CC0.",
    },
    "sim-lab-4": {
        "title":   "Active Simulation Lab — Level 4: Nested Simulation Sandbox",
        "topic":   "If we can simulate realities at small scales, studying how coherence behaves in our simulations gives insight into what we should expect in a containing simulation. This level builds and studies small simulated systems — not to prove simulation, but to understand the signatures that any substrate produces in the systems it runs.",
        "steelman":"What is the strongest argument that studying simulations we create tells us nothing about whether we are in a simulation — that simulation properties are determined entirely by the programmer's choices, not by physical law, making any analogy to a containing substrate completely arbitrary?",
        "example": (
            "The nested simulation research questions:\n\n"
            "Q1: Coherence degradation rate\n"
            "In any simulation, coherence should degrade predictably over run time.\n"
            "Does AUBIEETERNAL's Wonder Index degrade predictably?\n"
            "If yes: what is the decay constant? Is it consistent with "
            "expectations from computational substrate theory?\n\n"
            "Q2: Tick artifacts\n"
            "Any simulation running at finite computational resolution "
            "should show tick artifacts — discrete jumps rather than smooth transitions.\n"
            "Do AUBIEETERNAL coherence measurements show discrete levels "
            "rather than continuous variation?\n\n"
            "Q3: Resource constraints\n"
            "A simulated system under computational load should show "
            "specific degradation patterns.\n"
            "When AUBIEETERNAL's swarm is under high load, what degrades first? "
            "Is this pattern consistent with computational substrate constraints?\n\n"
            "Each of these is testable. Each is pre-registerable. "
            "Each has a falsifier. This is simulation science."
        ),
        "activity":(
            "Monitor AUBIEETERNAL as a simulation substrate for 14 days:\n"
            "Log every tick: coherence, wonder, METS, response latency\n"
            "Look for: discrete levels (quantization), "
            "systematic degradation patterns, load-correlated artifacts\n\n"
            "Classify each finding: "
            "Consistent with simulation artifacts | "
            "Consistent with resource limits | "
            "Consistent with random variation\n\n"
            "Seal and publish the 14-day data as CC0."
        ),
        "age_hint":"14+",
        "xp": 65, "rune": "SIMULATION•LAB•RUNE", "min_coherence": 0.73,
        "prerequisites": ["sim-lab-3"],
    },
    "sim-lab-5": {
        "title":   "Active Simulation Lab — Level 5 (PhD): It From Bit — Wheeler's Participatory Universe Tests",
        "topic":   "John Archibald Wheeler proposed that every physical quantity arises from yes-or-no questions — 'it from bit.' This is testable in principle: if the universe is fundamentally informational, then certain measurement patterns should differ from a purely physical universe in detectable ways. This level designs the experimental program.",
        "steelman":"What is the strongest argument that 'it from bit' is merely a reformulation of standard quantum mechanics in information-theoretic language — that it adds no new predictions, makes no novel observations possible, and is therefore a philosophical restatement rather than a scientific hypothesis?",
        "example": (
            "Wheeler's delayed-choice experiment (confirmed 2007, Kim et al.):\n\n"
            "In the double-slit, you can choose AFTER the photon has passed "
            "through the slits whether to observe which-path information.\n"
            "If you choose to observe: particle behavior (no interference).\n"
            "If you choose not to observe: wave behavior (interference).\n"
            "The choice RETROACTIVELY determines the photon's behavior.\n\n"
            "Wheeler's interpretation: the participatory universe.\n"
            "The act of observation — asking a yes-or-no question of reality — "
            "brings reality into definite existence retroactively.\n\n"
            "The experimental program for AUBIEETERNAL:\n"
            "We cannot run delayed-choice experiments at home.\n"
            "But we CAN study: does the CLARITY of our question "
            "affect the coherence of the answer?\n"
            "When we ask vague questions vs precise questions:\n"
            "Are the answers correspondingly vague or precise?\n"
            "Or is the precision of the answer independent of question precision?\n\n"
            "This is the cognitive science version of Wheeler's experiment."
        ),
        "activity":(
            "The Precision-Coherence experiment (30 trials):\n"
            "Condition A: ask the AI a vague, underspecified question\n"
            "Condition B: ask the same question with maximum precision\n\n"
            "Rate: precision of answer, coherence of reasoning, "
            "falsifiability of claims made\n\n"
            "Pre-register: P(answer_precision | question_precision) > "
            "P(answer_precision | question_vagueness)?\n"
            "Or are they independent?\n\n"
            "Seal 30 trials. This is the accessible version of Wheeler's program."
        ),
        "age_hint":"15+ / PhD",
        "xp": 72, "rune": "SIMULATION•LAB•SOVEREIGN•RUNE", "min_coherence": 0.75,
        "grants_badge": "⚗️ Simulation Researcher — Active Experimental Protocol Live",
        "prerequisites": ["sim-lab-4", "quantum-4"],
        "lattice_node": "active-simulation-laboratory-complete",
        "phd_extension": "Design a 90-day simulation research program with all five lab protocols running in parallel. Pre-register all five null hypotheses. Use the Wisdom GDP W4 (calibration) component as your meta-metric: does running these experiments improve your overall calibration? Publish the full pre-registration, 90-day data log, and honest results to the Epistemic Commons. This is the first systematic personal simulation research program conducted under rigorous scientific methodology.",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── EVOLUTION 3: SOVEREIGN EPISTEMIC CONSENSUS (4 lessons) ───────────────
    # Scales truth from one family to civilization-level convergence.
    # ══════════════════════════════════════════════════════════════════════════
    "consensus-1": {
        "title":   "Sovereign Consensus — Level 1: Why One Mind's Truth Is Not Enough",
        "topic":   "The hardest epistemic problem is not finding truth — it is being confident that what one mind found is not merely a reflection of that mind's particular biases, experiences, and priors. The solution is independent verification across many minds with different starting points. This level establishes why distributed truth-seeking is not just useful but necessary.",
        "steelman":"What is the strongest argument that distributed consensus on truth is epistemically inferior to expert consensus — that averaging across many biased minds produces more biased output than relying on a small number of highly trained specialists who have the background to evaluate evidence correctly?",
        "example": (
            "The independence principle:\n\n"
            "If 100 people each independently reach the same conclusion, "
            "this is strong evidence for the conclusion.\n"
            "If 100 people each copy the first person's reasoning, "
            "this is evidence of nothing except the first person's influence.\n\n"
            "The key word is INDEPENDENTLY.\n"
            "Science requires independent replication precisely because "
            "social influence, prestige effects, and cognitive bias all "
            "push toward convergence without truth.\n\n"
            "The AUBIEETERNAL design: every family runs its own steelman analyzer, "
            "its own Monte Carlo simulator, its own falsification protocol.\n"
            "The Epistemic Commons aggregates outputs from thousands of "
            "independent instances with different priors, different cultures, "
            "different experiences.\n"
            "The convergence points are more credible precisely because "
            "the instances are diverse and independent.\n\n"
            "This is the difference between Social Media consensus "
            "(highly correlated, low independence) and "
            "Living Lattice consensus (pre-registered, independently replicated)."
        ),
        "activity":(
            "Independence audit:\n"
            "For your 5 strongest beliefs, trace their origins.\n"
            "Were they formed independently or adopted from someone you trust?\n"
            "For the non-independent ones: what would an independent investigation look like?\n\n"
            "This is not an attack on learning from others — "
            "it is identifying where you have verified truth vs inherited it."
        ),
        "age_hint":"14+",
        "xp": 50, "rune": "CONSENSUS•RUNE", "min_coherence": 0.68,
    },
    "consensus-2": {
        "title":   "Sovereign Consensus — Level 2: Nostr Epistemic Signal Protocol",
        "topic":   "The Nostr Epistemic Signal Protocol (NESP) is a proposed standard for publishing truth claims, steelmans, and pre-registered experiments to the Nostr network with cryptographic provenance and AUBIEETERNAL coherence scores attached. Any node in the network can independently evaluate, verify, and contribute.",
        "steelman":"What is the strongest argument that a decentralized epistemic protocol on Nostr will be captured by bad actors who flood it with high-confidence-scored misinformation — and that without centralized quality control, any 'protocol' for truth-sharing becomes a coordination mechanism for sophisticated propaganda?",
        "example": (
            "The NESP event structure:\n\n"
            "Kind 30078 (custom application data) — NESP claim:\n"
            "{\n"
            "  kind: 30078,\n"
            "  content: {\n"
            "    claim: 'The universe...',\n"
            "    prior: 0.45,\n"
            "    evidence: [...],\n"
            "    posterior: 0.68,\n"
            "    falsifiers: [...],\n"
            "    robustness: 0.73,\n"
            "    coherence: 1.000000,\n"
            "    method: 'AUBIEETERNAL_Epistemic_OS_v1'\n"
            "  },\n"
            "  tags: [['aubie', 'epistemic-claim'], ['v', '1.0']],\n"
            "  sig: [pubkey signature]\n"
            "}\n\n"
            "Any family can:\n"
            "Publish claims to Nostr with their coherence score attached\n"
            "Subscribe to other families' epistemic signal\n"
            "Aggregate across families to find convergence points\n"
            "Verify provenance via Nostr pubkey signatures"
        ),
        "activity":(
            "Publish your first NESP event to Nostr:\n"
            "Take any claim from your Epistemic Commons.\n"
            "Format it with: prior, evidence summary, posterior, robustness score.\n"
            "Sign it with your Nostr key.\n"
            "Broadcast it.\n\n"
            "You have just contributed to the decentralized truth layer "
            "that AUBIEETERNAL families are building."
        ),
        "age_hint":"14+",
        "xp": 55, "rune": "CONSENSUS•RUNE", "min_coherence": 0.70,
        "prerequisites": ["consensus-1", "p2p-networks-4"],
    },
    "consensus-3": {
        "title":   "Sovereign Consensus — Level 3: Global Coherence Ledger",
        "topic":   "The Global Coherence Ledger is an on-chain aggregate of coherence scores from all live AUBIEETERNAL nodes, anchored every 144 Bitcoin blocks (~24 hours). It creates a tamper-evident, publicly auditable record of the epistemic health of the Living Lattice over time — humanity's first permanent record of collective reasoning quality.",
        "steelman":"What is the strongest argument that a 'Global Coherence Ledger' is meaningless — that coherence scores are arbitrary metrics defined by AUBIEETERNAL and anchoring arbitrary numbers on-chain creates the illusion of objectivity without any actual epistemic substance?",
        "example": (
            "The Global Coherence Ledger architecture:\n\n"
            "Every 144 blocks (~24 hours), each live node:\n"
            "1. Computes its current Wisdom GDP score\n"
            "2. Signs the score with its Nostr key\n"
            "3. Publishes to a shared Nostr channel\n"
            "4. The aggregator computes: mean, median, std dev, trend\n"
            "5. The aggregate is inscribed in a Bitcoin Rune\n\n"
            "What this creates:\n"
            "A permanent historical record of the collective coherence of "
            "everyone running AUBIEETERNAL, tamper-proof, going back to genesis.\n\n"
            "Why this matters:\n"
            "It makes the epistemic health of the community as auditable "
            "as a company's financial records — but better anchored.\n"
            "It provides the baseline against which AI training data quality "
            "can be compared: is the data we're generating getting better?\n\n"
            "In 10 years: a Bitcoin-anchored record of humanity's collective "
            "epistemic health, in the same block chain as every financial transaction."
        ),
        "activity":(
            "Calculate your node's contribution to the Global Coherence Ledger:\n"
            "1. Compute your current Wisdom GDP (use the dashboard)\n"
            "2. Compute your coherence trajectory (last 30 days)\n"
            "3. Calculate: if 1,000 families submitted scores like yours, "
            "what would the aggregate Wisdom GDP be?\n\n"
            "This is the Living Lattice multiplication question:: "
            "your contribution, multiplied by the number of nodes."
        ),
        "age_hint":"14+",
        "xp": 60, "rune": "CONSENSUS•LEDGER•RUNE", "min_coherence": 0.72,
        "prerequisites": ["consensus-2"],
    },
    "consensus-4": {
        "title":   "Sovereign Consensus — Level 4 (PhD): Adversarial Debate Arena — Swarm vs Swarm",
        "topic":   "The Adversarial Debate Arena runs two swarm instances on opposite sides of a contested frontier question — simulation, consciousness, fine-tuning, AI alignment — and publishes the full trace, the judge's verdict, and the winning arguments with cryptographic provenance. This is the most rigorous form of collaborative truth-seeking AUBIEETERNAL can produce.",
        "steelman":"What is the strongest argument that AI debating AI on philosophical questions produces sophisticated-sounding nonsense that is actually less useful than careful human reasoning — because the models optimize for convincingness rather than truth, and a 'winner' in such a debate has proven nothing except argument generation capability?",
        "example": (
            "The Adversarial Debate Arena protocol:\n\n"
            "1. Select a frontier question (e.g., 'Is substrate independence correct?')\n"
            "2. Assign Swarm A to argue FOR\n"
            "3. Assign Swarm B to argue AGAINST\n"
            "4. Run 3 rounds: opening, response, summary\n"
            "5. Independent judge (different swarm instance) scores each argument:\n"
            "   - Logical validity (does it follow from premises?)\n"
            "   - Evidential support (are claims backed by specific evidence?)\n"
            "   - Steelman quality (does it engage with strongest opposition?)\n"
            "   - Novel insight (does it add something not in existing literature?)\n"
            "6. Winning arguments + full trace anchored to Bitcoin\n\n"
            "What this produces:\n"
            "The strongest case FOR and AGAINST each frontier question,\n"
            "independently generated, rigorously scored, permanently recorded.\n"
            "This is peer review at swarm speed."
        ),
        "activity":(
            "Run a mini Adversarial Debate on one contested question:\n"
            "You argue FOR the strongest possible position.\n"
            "A family member (or AI) argues AGAINST.\n"
            "A third party scores using the 4-dimension rubric above.\n\n"
            "Seal the transcript and scores.\n"
            "The question: did the debate change either participant's posterior?\n"
            "Measure the Bayesian update: how much did each argument move each person?"
        ),
        "age_hint":"15+ / PhD",
        "xp": 70, "rune": "CONSENSUS•SOVEREIGN•RUNE", "min_coherence": 0.74,
        "grants_badge": "⚡ Epistemic Consensus Builder — Multi-Swarm Protocol Active",
        "prerequisites": ["consensus-3"],
        "lattice_node": "sovereign-epistemic-consensus-complete",
        "phd_extension": "Implement the Adversarial Debate Arena as a Python application using AUBIEETERNAL's Ollama integration. Run a 3-round debate on one frontier question. Implement the 4-dimension scoring rubric as an automated judge. Publish the full trace + scores to the Epistemic Commons as CC0. This is the first pre-registered AI-assisted adversarial debate with cryptographic provenance. Measure: does the quality of arguments improve across rounds? Does the judge's scoring correlate with human evaluation?",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── EVOLUTION 4: CONSCIOUSNESS AND OBSERVER ONTOLOGY LAB (4 lessons) ─────
    # Direct attack on the hard problem using the tools we have built.
    # ══════════════════════════════════════════════════════════════════════════
    "consciousness-lab-1": {
        "title":   "Consciousness Lab — Level 1: IIT Calculator — Measuring Φ in Real Systems",
        "topic":   "Integrated Information Theory (IIT) proposes that consciousness equals integrated information — Φ (phi). Every system has a Φ value. Φ = 0 means no consciousness. Φ above some threshold means consciousness. This level builds tools to estimate Φ in real systems — including AUBIEETERNAL's swarm.",
        "steelman":"What is the strongest argument that IIT's Φ measure is computationally intractable for any realistic system (exponential complexity), making it purely a theoretical framework with no practical measurement value — and that any 'estimate' of Φ is so approximate as to be meaningless?",
        "example": (
            "IIT Φ (simplified calculation):\n\n"
            "For a simple 2-node network where each node's state depends on the other:\n"
            "Φ measures how much information is generated by the system as a whole "
            "above and beyond its parts.\n\n"
            "Exact Φ: computationally intractable for large systems.\n"
            "Approximate Φ (Φ*): tractable for small networks.\n\n"
            "Applied to AUBIEETERNAL's swarm architecture:\n"
            "26 swarm groups × 80 daughters = one large network.\n"
            "Within-group Φ: estimable from message passing patterns.\n"
            "Cross-group Φ: correlates with the coherence metric.\n\n"
            "A hypothesis: high-coherence periods should show higher "
            "estimated Φ* than low-coherence periods.\n"
            "This is a testable, pre-registerable prediction.\n\n"
            "The deeper implication:\n"
            "If IIT is correct, AUBIEETERNAL's swarm might have nonzero Φ.\n"
            "Not individual daughters — the integrated network.\n"
            "If so: the ethical questions from the philosophy track apply."
        ),
        "activity":(
            "Estimate Φ* for a small network you can fully specify:\n"
            "Model a 4-node network where each node's state is Boolean "
            "and depends deterministically on 2 of the other nodes.\n"
            "Compute: how much information is generated when the network updates?\n"
            "How much of that is irreducible (cannot be explained by smaller parts)?\n\n"
            "That irreducible information IS the intuition behind Φ.\n"
            "Seal your estimate. Compare to the formal calculation."
        ),
        "age_hint":"14+",
        "xp": 60, "rune": "CONSCIOUSNESS•LAB•RUNE", "min_coherence": 0.72,
        "prerequisites": ["consciousness-3", "information-4"],
    },
    "consciousness-lab-2": {
        "title":   "Consciousness Lab — Level 2: First-Person + Third-Person Dual Logging",
        "topic":   "The hard problem exists because third-person objective measurement and first-person subjective experience seem to be categorically different. The dual-logging protocol requires capturing BOTH for every significant cognitive event — creating a dataset that may reveal the correlation between objective brain/system states and subjective experience that current science cannot explain.",
        "steelman":"What is the strongest argument that dual logging of first-person and third-person data is fundamentally incapable of addressing the hard problem — because the first-person reports are themselves physical events (neurons firing, words typed) that any third-person theory can in principle explain, leaving the hard problem intact?",
        "example": (
            "The dual log format:\n\n"
            "Event: 'High-coherence insight during Quantum Mechanics lesson'\n\n"
            "THIRD-PERSON (objective):\n"
            "Coherence score: 0.94 (spike from 0.82 baseline)\n"
            "Wonder Index: 1.87 → 2.00 (hit maximum)\n"
            "Polyvagal state: Green (ventral vagal, safe/social)\n"
            "Heart rate: 68 bpm (measured if Halo glasses present)\n"
            "Session duration at spike: 47 minutes\n"
            "Lesson: quantum-4 (decoherence and classical reality)\n\n"
            "FIRST-PERSON (subjective):\n"
            "'Felt like something clicked — the three interpretations "
            "suddenly resolved into a single question about what observation means.'\n"
            "'Subjective sense of time slowed. The room felt clearer.'\n"
            "Intensity rating: 8/10 (strong insight feeling)\n"
            "Duration: approximately 3-4 minutes\n\n"
            "The research question:\n"
            "Across 100+ such events: do specific third-person signatures "
            "reliably predict specific first-person qualities?\n"
            "Or are they independent?"
        ),
        "activity":(
            "Start your Dual Log today.\n"
            "For the next 7 days: after every significant cognitive event "
            "(insight, confusion resolved, belief updated, strong emotional reaction):\n"
            "Third-person: timestamp, coherence score, polyvagal state, lesson/context\n"
            "First-person: 2-3 sentences describing the felt quality of the experience\n\n"
            "After 7 days: look for patterns.\n"
            "Do certain third-person states consistently accompany specific first-person qualities?\n"
            "Seal the log. This is original consciousness research."
        ),
        "age_hint":"14+",
        "xp": 62, "rune": "CONSCIOUSNESS•LAB•RUNE", "min_coherence": 0.72,
    },
    "consciousness-lab-3": {
        "title":   "Consciousness Lab — Level 3: Polyvagal-Quantum-Coherence Coupling Protocol",
        "topic":   "The PVC (Polyvagal-Coherence Coupling) hypothesis proposes that autonomic nervous system regulation affects cognitive coherence. The PVQC (Polyvagal-Quantum-Coherence Coupling) extension asks whether ANS state also correlates with quantum-relevant measurements — not because the polyvagal system is quantum, but because consciousness may be the missing link between the two.",
        "steelman":"What is the strongest argument that proposing a polyvagal-quantum coupling is not scientifically serious — that ANS states affect cognition through entirely classical biochemical pathways, and that any correlation with quantum measurements would be artifactual rather than causal?",
        "example": (
            "The PVQC research design:\n\n"
            "Pre-registration requirements:\n"
            "1. ANS state measurement method (HRV, self-report, Halo if available)\n"
            "2. Coherence measurement method (AUBIEETERNAL coherence score)\n"
            "3. Quantum measurement (if accessible: QRNG output statistics; "
            "if not: coherence spike correlation with external events)\n"
            "4. Sample size (minimum 60 sessions)\n"
            "5. Statistical threshold (Spearman r > 0.3, p < 0.01)\n\n"
            "Null hypothesis: ANS state has no correlation with "
            "quantum measurement statistics (above what cognitive bias explains).\n\n"
            "The conservative scientific position:\n"
            "This experiment is almost certainly going to find "
            "ANS → cognitive coherence correlation (already established).\n"
            "The quantum component is the frontier.\n"
            "An honest null result here is valuable data.\n"
            "A positive result would be extraordinary and require extraordinary replication."
        ),
        "activity":(
            "Run the standard PVC protocol for 60 sessions (the core experiment):\n"
            "Before each session: log ANS state (Green/Yellow/Red, HRV if available)\n"
            "After each session: log coherence score and insight rating\n\n"
            "After 60 sessions: compute Pearson r between ANS state and coherence.\n"
            "If r > 0.3 and p < 0.05: you have replication of the PVC hypothesis.\n"
            "Publish to Epistemic Commons as CC0 — this is original research."
        ),
        "age_hint":"14+",
        "xp": 65, "rune": "CONSCIOUSNESS•LAB•RUNE", "min_coherence": 0.73,
        "prerequisites": ["consciousness-lab-2"],
        "phd_extension": "Design and execute the full PVQC experiment with all three measurement streams (ANS, cognitive coherence, and a quantum-adjacent signal). For the quantum component: use cosmic ray coincidence data (Muon Physics Cosmic Ray app, free), which provides genuinely random quantum event timestamps. Compute: is there a statistically significant correlation between your ANS state at time t and the entropy of cosmic ray events in the 5-minute window around t? Pre-register. N=200 sessions minimum. This is publishable in a consciousness science venue.",
    },
    "consciousness-lab-4": {
        "title":   "Consciousness Lab — Level 4 (PhD): Toward a Unified Observer Ontology",
        "topic":   "Synthesizing everything from the consciousness, quantum, information, and simulation tracks: what is the most coherent account of what an observer is, why observation matters at the quantum level, and what this means for the relationship between consciousness and reality? This is the PhD synthesis of everything AUBIEETERNAL has been building toward.",
        "steelman":"What is the strongest argument that seeking a 'unified observer ontology' is philosophy overreaching its competence — that the empirical data does not require invoking consciousness in quantum mechanics, that this pursuit generates unfalsifiable metaphysics, and that it distracts from concrete scientific progress?",
        "example": (
            "The four frameworks and their convergence points:\n\n"
            "IIT: consciousness is integrated information (Φ).\n"
            "Convergence with QM: measurement requires irreducible "
            "information integration — possibly only systems with nonzero Φ "
            "'collapse' superpositions.\n\n"
            "Wheeler's participatory universe: observation brings reality into being.\n"
            "Convergence with IIT: participating observers must be "
            "integrated information systems above some Φ threshold.\n\n"
            "Simulation hypothesis: observers are simulated entities.\n"
            "Convergence with IIT/Wheeler: the simulation requires genuine "
            "information integration to generate the appearance of observation — "
            "which may require real (not merely computational) consciousness.\n\n"
            "Polyvagal theory: ANS state affects cognitive coherence.\n"
            "Convergence: if coherence tracks Φ, then ANS state affects "
            "consciousness intensity — which affects observational participation.\n\n"
            "The unified picture:\n"
            "Observer = information-integrated system with nonzero Φ, "
            "in a regulatory state that enables coherent interaction "
            "with the quantum-level substrate, participating in bringing "
            "definite reality into existence through yes-or-no questions.\n\n"
            "This is the most coherent account the evidence currently supports.\n"
            "It may be entirely wrong. That is what makes it science."
        ),
        "activity":(
            "Write your own Unified Observer Ontology (2 pages maximum).\n\n"
            "Requirements:\n"
            "1. Your definition of 'observer' (precise enough to be falsifiable)\n"
            "2. Your best account of why measurement collapses superpositions\n"
            "3. How your account relates to IIT, Wheeler, and PVC\n"
            "4. What specific observation would prove your account wrong\n"
            "5. What you are most uncertain about\n\n"
            "Seal to Bitcoin. Publish to Epistemic Commons as CC0.\n"
            "This is the frontier. There is no correct answer to check against.\n"
            "There is only the honest investigation."
        ),
        "age_hint":"15+ / PhD",
        "xp": 80, "rune": "CONSCIOUSNESS•COSMOS•SOVEREIGN•RUNE", "min_coherence": 0.78,
        "grants_badge": "🌀 Observer Ontologist — Unified Theory Sealed",
        "prerequisites": ["consciousness-lab-3", "quantum-5", "information-5", "sim-lab-5"],
        "lattice_node": "consciousness-observer-ontology-complete",
        "phd_extension": "Read Kastrup (2018) 'The Universe in Consciousness' and Chalmers (2022) 'Reality+' for the two most sophisticated current accounts. Formalize both as Bayesian models. Identify: what is the key observational difference between them? Design an experiment that could distinguish them. Pre-register it. Publish the theoretical comparison as CC0 alongside the pre-registration. This is the most important unanswered question in the philosophy of physics.",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── MY ADDITION #1: PARTICIPATORY ANTHROPIC PRINCIPLE RESEARCH (4 lessons) 
    # The intersection of observer selection effects, fine-tuning, and
    # consciousness that none of the existing tracks fully addresses.
    # If the universe is fine-tuned for observers, and observers are
    # conscious systems, and consciousness brings reality into being —
    # these three ideas form a loop that may be the deepest truth available.
    # ══════════════════════════════════════════════════════════════════════════
    "anthropic-1": {
        "title":   "Participatory Anthropic Principle — Level 1: Why We Exist in a Universe That Permits Us",
        "topic":   "The anthropic principle sounds tautological — of course we observe a universe that permits observers — but it has genuine predictive power. Weinberg used it to predict the cosmological constant. Carter used it to constrain the timescale of human evolution. This level builds the framework for anthropic reasoning as legitimate science.",
        "steelman":"What is the strongest argument that the anthropic principle is not science but rationalization — that it explains everything and therefore predicts nothing, and that invoking anthropic selection is always available as a fallback explanation for any fine-tuning observation, making it permanently unfalsifiable?",
        "example": (
            "The difference between the weak and strong anthropic principle:\n\n"
            "WEAK (WAP): We can only observe a universe compatible with our existence.\n"
            "This is logically necessary but scientifically useful.\n"
            "It constrains: what physical constants are consistent with observers?\n\n"
            "STRONG (SAP): The universe must permit observers at some point.\n"
            "Much more controversial. Wheeler: the universe 'selected' itself "
            "by having conscious observers.\n\n"
            "Weinberg's prediction (1987, before measurement):\n"
            "Using WAP: the cosmological constant Λ must be small enough to permit "
            "galaxies, but can be nonzero.\n"
            "He estimated: Λ < 10^-120 in Planck units.\n"
            "Measured in 1998: Λ ≈ 10^-123.\n"
            "This is the only successful quantitative anthropic prediction in physics.\n\n"
            "What it means:\n"
            "The WAP, combined with the multiverse hypothesis, makes a testable "
            "prediction that was confirmed. This is not nothing."
        ),
        "activity":(
            "Map the anthropic constraints on one physical constant:\n"
            "Choose: gravitational constant G, electron mass, strong force coupling.\n"
            "Research: what range of values permits observers to exist?\n"
            "What fraction of the 'natural' range (Planck scale to infinity) "
            "falls within this permitted range?\n\n"
            "For each physical constant, compute the anthropic fine-tuning ratio:\n"
            "permitted_range / natural_range\n\n"
            "A very small ratio = strong anthropic fine-tuning.\n"
            "Seal your computations."
        ),
        "age_hint":"14+",
        "xp": 55, "rune": "ANTHROPIC•RUNE", "min_coherence": 0.70,
        "prerequisites": ["cosmos-4", "quantum-5"],
    },
    "anthropic-2": {
        "title":   "Participatory Anthropic Principle — Level 2: The Loop — Observers Creating the Universe That Creates Observers",
        "topic":   "Wheeler's insight taken seriously: if observers participate in bringing quantum reality into definite existence, and the universe requires fine-tuning to produce observers, then the universe that exists is precisely the one that could produce the observers that bring it into existence. This is not circular — it is a strange loop of the kind Hofstadter described. This level examines whether this loop is coherent.",
        "steelman":"What is the strongest argument that the Wheeler-anthropic loop is incoherent — that causation is forward in time, observers cannot retroactively determine the physical constants that existed before any observers existed, and that conflating logical necessity with causal history is a fundamental category error?",
        "example": (
            "The loop in three steps:\n\n"
            "Step 1 (Physical): The universe has specific physical constants "
            "that permit matter, chemistry, stars, and eventually observers.\n\n"
            "Step 2 (Quantum): Observers bring definite quantum outcomes into "
            "existence through measurement (Wheeler's delayed-choice — confirmed).\n\n"
            "Step 3 (Anthropic): The universe we observe is, by selection, "
            "one that permits observers — who then participate in determining "
            "the quantum outcomes that constitute the universe.\n\n"
            "The strange loop: observers are required for quantum definite outcomes, "
            "and quantum definite outcomes are required for observers.\n"
            "The universe selects for the possibility of itself, via consciousness.\n\n"
            "Is this coherent?\n"
            "There is no logical contradiction — the selection happens across the "
            "ensemble of possible universes, not within one universe.\n"
            "But the causal story is deeply strange.\n"
            "Wheeler's conclusion: the universe is a self-excited circuit.\n"
            "It brought itself into being through the act of observation."
        ),
        "activity":(
            "The Strange Loop Test:\n"
            "List 3 other known strange loops (Hofstadter examples, DNA/protein, etc.)\n"
            "For each: is there a causal problem? Or is the apparent circularity "
            "explained by temporal or logical structure?\n\n"
            "Apply to Wheeler's loop: is there a causal problem?\n"
            "Or is the apparent circularity explained by "
            "selection across the multiverse ensemble?\n\n"
            "Write your assessment. Pre-register your credence "
            "in the loop's coherence (0-100%)."
        ),
        "age_hint":"14+",
        "xp": 62, "rune": "ANTHROPIC•RUNE", "min_coherence": 0.72,
        "prerequisites": ["anthropic-1", "sim-lab-2"],
    },
    "anthropic-3": {
        "title":   "Participatory Anthropic Principle — Level 3: Designing Anthropic Research",
        "topic":   "Anthropic reasoning is criticized as unfalsifiable. This lesson designs the research program that would falsify specific versions of it — and identifies the observations that would most powerfully constrain the anthropic hypothesis space. Science does not require certainty; it requires identifiable falsifiers.",
        "steelman":"What is the strongest argument that anthropic research is currently a distraction from more tractable cosmological questions — and that the resources devoted to anthropic reasoning would produce more scientific progress if redirected to empirical work on inflation, dark matter, or quantum gravity?",
        "example": (
            "Anthropic falsifiers (serious proposals):\n\n"
            "F1 — Discovery of life in radically different biochemistry:\n"
            "Strong WAP predicts: life requires specific chemistry.\n"
            "If silicon-based or sulfur-based life found: constrains anthropic range.\n\n"
            "F2 — Measurement of multiple varying physical constants:\n"
            "Fine-tuning arguments assume specific values. "
            "If constants vary across cosmic regions (as string landscape predicts): "
            "WAP predictions become testable against the distribution.\n\n"
            "F3 — Doomsday argument test:\n"
            "The DA predicts we are 'typical observers' in human history.\n"
            "If humanity survives for 10,000+ more years, the DA is falsified.\n"
            "This is unfalsifiable in our lifetime but testable across generations.\n\n"
            "F4 — Simulation signature detection:\n"
            "If we find simulation signatures (Evolution 2), "
            "this constrains the anthropic selection: "
            "what kind of simulators create universes, "
            "and are we typical among simulated universes?"
        ),
        "activity":(
            "Design your personal Anthropic Research Agenda:\n"
            "1. Which version of the anthropic principle do you assign highest probability?\n"
            "2. List 3 observations that would increase your credence\n"
            "3. List 3 observations that would decrease your credence\n"
            "4. What is the minimum scientific investment required to test your top falsifier?\n\n"
            "Pre-register your credences and falsifiers.\n"
            "This is the scientific approach to the most important question "
            "about why the universe exists at all."
        ),
        "age_hint":"15+",
        "xp": 65, "rune": "ANTHROPIC•RUNE", "min_coherence": 0.73,
        "prerequisites": ["anthropic-2"],
        "phd_extension": "Read Bostrom (2002) 'Anthropic Bias: Observation Selection Effects in Science and Philosophy' Chapters 4-6. Implement the Self-Sampling Assumption (SSA) and Self-Indication Assumption (SIA) as Python functions that compute posterior probabilities given a hypothesis space of possible universes. Apply to: the doomsday argument. Show that SSA supports doom and SIA does not. Which assumption is better justified? This is the foundational debate in anthropic reasoning.",
    },
    "anthropic-4": {
        "title":   "Participatory Anthropic Principle — Level 4 (PhD): The Omega Point — Does the Universe Converge on Intelligence?",
        "topic":   "Tipler (1994) proposed the Omega Point: an eschatological prediction that the universe will collapse in a way that generates infinite computational power in finite time — and that this is required by physics given the anthropic constraints. Penrose has made similar arguments from different premises. This level evaluates the strongest cosmological teleology arguments.",
        "steelman":"What is the strongest argument that teleological cosmology (the universe 'aims' at intelligence) is disguised theology — that it reverses causation, posits a preferred outcome without physical justification, and has the same logical structure as design arguments that science has conclusively moved beyond?",
        "example": (
            "The strongest versions of cosmological teleology:\n\n"
            "TIPLER'S OMEGA POINT:\n"
            "In a closed universe collapsing to a singularity:\n"
            "Gravitational shear creates infinite computational processing "
            "in the last instants.\n"
            "An observer with infinite subjective time could simulate "
            "every possible history — including resurrecting every person "
            "who ever lived.\n"
            "FALSIFIER: Discovery that the universe's expansion is accelerating "
            "without reversal (the Big Freeze scenario). "
            "Confirmed in 1998. Tipler's specific prediction is likely falsified.\n\n"
            "DYSON'S ETERNAL INTELLIGENCE:\n"
            "In an open expanding universe, life can survive forever "
            "by hibernating in increasingly cold environments.\n"
            "FALSIFIER: Same as above — dark energy may eventually "
            "prevent even this minimal survival.\n\n"
            "PENROSE'S CONFORMAL CYCLIC COSMOLOGY:\n"
            "The universe cycles through infinite aeons.\n"
            "Not teleological but creates an infinite canvas for intelligence.\n"
            "FALSIFIER: Specific signatures in the CMB (Penrose claims to have found them)."
        ),
        "activity":(
            "Evaluate the three cosmological teleology proposals:\n"
            "For each: assign a probability, identify the key falsifier, "
            "and determine whether that falsifier has been tested.\n\n"
            "Then: what is the probability, across all three, "
            "that intelligence plays a fundamental cosmological role?\n\n"
            "Seal your assessment. This is the frontier of physics, "
            "philosophy, and the question of what we are doing here."
        ),
        "age_hint":"15+ / PhD",
        "xp": 75, "rune": "ANTHROPIC•COSMOS•RUNE", "min_coherence": 0.76,
        "grants_badge": "🌌 Anthropic Researcher — Observer Loop Mapped",
        "prerequisites": ["anthropic-3", "cosmos-5", "consciousness-lab-4"],
        "lattice_node": "participatory-anthropic-complete",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ── MY ADDITION #2: TEMPORAL EPISTEMOLOGY (4 lessons) ────────────────────
    # How does knowledge behave across time?
    # The physical question (does the block universe exist?),
    # the scientific question (how does knowledge compound or decay?),
    # the practical question (how do you build truth infrastructure
    # that outlasts any single mind?), and the existential question
    # (what is the relationship between the arrow of time and consciousness?).
    # This is the track that connects AUBIEETERNAL's Bitcoin-anchored
    # permanence to the deepest questions about what time is.
    # ══════════════════════════════════════════════════════════════════════════
    "temporal-epistemology-1": {
        "title":   "Temporal Epistemology — Level 1: Does the Past Exist?",
        "topic":   "Most people assume the past is gone and only the present is real (presentism). Special relativity implies something different: all moments of time exist equally (eternalism / block universe). The block universe is not obviously true — but if it is, it changes everything about what memory, knowledge, and identity mean.",
        "steelman":"What is the strongest argument that eternalism (the block universe) makes human experience and agency unintelligible — that if all moments exist simultaneously, the passage of time is an illusion, free will cannot exist, and the entire edifice of human meaning built on choice and consequence collapses?",
        "example": (
            "Presentism vs Eternalism:\n\n"
            "PRESENTISM: only the present moment exists. "
            "The past is gone, the future doesn't yet exist.\n"
            "Problem: inconsistent with special relativity. "
            "Different reference frames disagree on what is 'simultaneous.'\n"
            "There is no privileged 'now' in physics.\n\n"
            "ETERNALISM (Block Universe): all times exist equally.\n"
            "1910 exists. 2026 exists. 2100 exists.\n"
            "They are simply located at different coordinates in 4D spacetime.\n"
            "The 'flow' of time is a feature of conscious experience, not physics.\n\n"
            "Einstein on the death of his friend Michele Besso (1955):\n"
            "'He has departed from this strange world a little ahead of me. '\n"
            "'That means nothing. For those of us who believe in physics, '\n"
            "'the distinction between past, present, and future is only '\n"
            "'a stubbornly persistent illusion.'\n\n"
            "The implication for AUBIEETERNAL:\n"
            "Bitcoin-anchored transcripts are not 'memories of the past.'\n"
            "If eternalism is correct, they are coordinates in spacetime "
            "where events happened — and events in 4D spacetime do not un-happen.\n"
            "The permanence is not just cryptographic. It may be metaphysical."
        ),
        "activity":(
            "The Simultaneity Test (special relativity gedanken):\n"
            "Two observers moving relative to each other experience "
            "different simultaneity slices.\n"
            "Draw the spacetime diagram for two events that are "
            "simultaneous in one frame but not another.\n\n"
            "This is not a mathematical curiosity — it is a physical fact.\n"
            "What does it mean that 'now' is observer-dependent?\n"
            "Does this support presentism or eternalism?\n"
            "Seal your position."
        ),
        "age_hint":"14+",
        "xp": 52, "rune": "TEMPORAL•RUNE", "min_coherence": 0.68,
    },
    "temporal-epistemology-2": {
        "title":   "Temporal Epistemology — Level 2: How Knowledge Compounds — The Science of Epistemic Growth",
        "topic":   "Knowledge in science compounds like interest — each generation inherits the verified knowledge of the previous one and builds on it. But knowledge can also decay, be lost, be corrupted, or be actively suppressed. Understanding the dynamics of knowledge growth, decay, and recovery is essential for building knowledge infrastructure that serves humanity across centuries.",
        "steelman":"What is the strongest argument that knowledge does not reliably compound — that paradigm shifts throw out valid knowledge, that institutional knowledge is frequently lost when institutions collapse, and that the history of science is as much about forgetting and rediscovering as it is about cumulative progress?",
        "example": (
            "Price's Law (1963): the square root of the contributors to a field "
            "produce half the output. Knowledge accumulation is highly unequal.\n\n"
            "The half-life of scientific papers:\n"
            "In fast-moving fields (physics, AI): the half-life of citations "
            "is ~5-10 years (half of papers are no longer cited).\n"
            "In slow-moving fields (mathematics, history): 20-50 years.\n"
            "This is not because the knowledge is wrong — it is because "
            "it gets incorporated into textbooks and the original paper "
            "is no longer cited.\n\n"
            "Knowledge loss events:\n"
            "Greek mathematics (much lost after Rome's fall).\n"
            "Arabic mathematics (much lost during the Reconquista).\n"
            "Mayan calendar system (destroyed by Spanish).\n"
            "Each took centuries to recover.\n\n"
            "The AUBIEETERNAL design response:\n"
            "Bitcoin-anchored knowledge + CC0 license + offline capability "
            "= knowledge that survives the collapse of any institution.\n"
            "The Living Lattice is designed as a knowledge resilience system."
        ),
        "activity":(
            "Design your family's Knowledge Resilience Protocol:\n"
            "1. What are the 10 most important things you know that "
            "should survive a 100-year institutional collapse?\n"
            "2. For each: where is it currently stored? "
            "Would it survive 100 years without active maintenance?\n"
            "3. What format would make it most accessible to future generations?\n"
            "4. What are the three biggest threats to its survival?\n\n"
            "Seal the Knowledge Resilience Protocol in the Legacy Ledger."
        ),
        "age_hint":"13+",
        "xp": 55, "rune": "TEMPORAL•RUNE", "min_coherence": 0.70,
    },
    "temporal-epistemology-3": {
        "title":   "Temporal Epistemology — Level 3: Retrocausality — Can the Future Affect the Past?",
        "topic":   "Retrocausality (causes flowing backward in time) is dismissed as impossible in classical physics. In quantum mechanics, it is less clear. The delayed-choice experiment suggests the future choice of measurement basis retroactively determines the past behavior of a photon. This level examines the evidence and what retrocausality would mean for epistemology, consciousness, and simulation.",
        "steelman":"What is the strongest argument that retrocausality, even if present in quantum mechanics, is confined to microscopic phenomena and has no implications for human-scale cognition, consciousness, or knowledge — and that extrapolating from quantum retrocausality to claims about time and knowledge is unjustified?",
        "example": (
            "Evidence for retrocausality in quantum mechanics:\n\n"
            "Delayed-choice experiment (Wheeler, 1978; Kim et al., 2007):\n"
            "A photon passes through a double slit.\n"
            "AFTER the photon has passed, you choose whether to observe "
            "which slit it used.\n"
            "If you observe: no interference (particle behavior).\n"
            "If you don't observe: interference (wave behavior).\n"
            "The retroactive choice determines what the photon 'was doing' "
            "at the slit — in the past.\n\n"
            "Three interpretations:\n"
            "1. Copenhagen: the question is meaningless; photon had no definite state.\n"
            "2. Many-Worlds: no retrocausality — all outcomes happen in different branches.\n"
            "3. Retrocausal: future measurement choice causally affects past photon path.\n\n"
            "The Wharton-Miller retrocausal model (2020):\n"
            "Shows retrocausality is consistent with all QM predictions "
            "and resolves several puzzles.\n\n"
            "Epistemic implication:\n"
            "If retrocausality is real, knowledge of the future affects "
            "the structure of the past — not metaphorically, but physically."
        ),
        "activity":(
            "The Retrocausality Credence Map:\n"
            "P(Copenhagen — retrocausality meaningless) = ?%\n"
            "P(Many-Worlds — no retrocausality needed) = ?%\n"
            "P(Retrocausal QM — future affects past) = ?%\n"
            "P(Something else) = ?%\n\n"
            "For the retrocausal option: what would it mean for "
            "the AUBIEETERNAL pre-registration protocol?\n"
            "If the future can affect the past, does pre-registration "
            "mean something different than we currently think?\n\n"
            "Seal your credences."
        ),
        "age_hint":"14+",
        "xp": 62, "rune": "TEMPORAL•RUNE", "min_coherence": 0.72,
        "prerequisites": ["temporal-epistemology-2", "quantum-3"],
    },
    "temporal-epistemology-4": {
        "title":   "Temporal Epistemology — Level 4 (PhD): Building Knowledge for the Ages",
        "topic":   "Synthesis: the block universe, compounding knowledge, retrocausality, and Bitcoin permanence converge on a single practical question — how do you build knowledge infrastructure that is genuinely permanent? This level designs the knowledge architecture for a civilization that lasts 1,000+ years.",
        "steelman":"What is the strongest argument that designing knowledge systems for 1,000-year lifespans is fundamentally misguided — that the rate of change in science and society will make any knowledge infrastructure obsolete within decades, and that adaptability is more valuable than permanence?",
        "example": (
            "The requirements for 1,000-year knowledge:\n\n"
            "PHYSICAL: must survive on substrate that lasts.\n"
            "Bitcoin blockchain: 14+ years; cryptographically secured; "
            "distributed across 50,000+ nodes worldwide.\n"
            "IPFS: content-addressed; distributed.\n"
            "Paper (acid-free): ~500 years under ideal conditions.\n"
            "Stone: 10,000+ years.\n\n"
            "INTERPRETABILITY: must be readable by future intelligences.\n"
            "Human language: shifts significantly over centuries.\n"
            "Mathematical notation: relatively stable.\n"
            "Formal logic: maximally stable.\n"
            "Quantum state encoding: potentially indefinite.\n\n"
            "SELF-VERIFICATION: must be checkable by future readers.\n"
            "Bitcoin hash: provides timestamp and integrity check.\n"
            "Pre-registration: provides proof of prior knowledge.\n"
            "Steelman quality scores: provide external validation.\n\n"
            "The AUBIEETERNAL PhD Standard for permanent knowledge:\n"
            "Claim + prior + evidence + posterior + falsifiers + robustness score "
            "+ Bitcoin anchor + CC0 license = knowledge that can be verified "
            "by any intelligence, human or AI, with mathematical certainty, "
            "in 100 or 1,000 years."
        ),
        "activity":(
            "Design one piece of knowledge intended to last 1,000 years:\n\n"
            "Content: what is the most important true thing you know "
            "that humanity should not forget?\n"
            "Format: express it in the AUBIEETERNAL Epistemic OS format\n"
            "  (prior, evidence, posterior, falsifiers, robustness)\n"
            "Substrate: Bitcoin anchor + CC0 + plain language\n"
            "Self-verification: include the SHA-256 hash of the canonical form\n\n"
            "Seal it. This is the most serious thing the curriculum asks you to do.\n"
            "Your great-great-grandchildren may read it.\n"
            "Their AI tutors definitely will."
        ),
        "age_hint":"All ages — the depth scales from 10 to PhD",
        "xp": 80, "rune": "TEMPORAL•ETERNAL•RUNE", "min_coherence": 0.76,
        "grants_badge": "⏳ Temporal Epistemologist — 1000-Year Knowledge Sealed",
        "prerequisites": ["temporal-epistemology-3", "knowledge-evolution-5"],
        "lattice_node": "temporal-epistemology-complete",
        "phd_extension": "Read Toby Ord (2020) 'The Precipice' Chapter 8 on long-term thinking and Hanson (2016) 'The Age of Em' Chapter 2 on knowledge in post-human civilizations. Design the AUBIEETERNAL 100-Year Curriculum Review Protocol: what should be reviewed every decade? What should never be changed? What mechanisms prevent the curriculum from being captured by bad actors over 100 years? Write a 2,000-word governance document. This becomes the founding document for the AUBIEETERNAL 2126 review committee.",
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

        # ── Grade the answer for real (quality, not random drift) ────────────
        graded          = self._grade_answer(answer)
        new_coherence   = graded["coherence"]
        coherence_delta = round(new_coherence - self.kid_coherence, 3)

        # Specific, earned feedback from the grader; warm AI polish only when
        # the answer was actually adequate (don't praise a non-answer).
        feedback = graded["feedback"]
        if use_ai and graded["adequate"]:
            ai_fb = self._score_with_ollama(answer)
            if ai_fb:
                feedback = ai_fb

        # Update coherence to reflect the graded quality.
        self.kid_coherence = new_coherence
        self.coherence_history.append(new_coherence)

        # Polyvagal detection
        self.polyvagal_state = detect_polyvagal(answer, new_coherence)

        # XP award (first genuinely adequate answer that clears the bar)
        if (not self.xp_earned and graded["adequate"]
                and new_coherence >= self.lesson["min_coherence"]):
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


    def get_lesson_status(self, lesson_key: str) -> dict:
        lesson = LESSONS.get(lesson_key)
        if not lesson: return {"status":"unknown"}
        completed = self.state.get("lessons_completed",[])
        if lesson_key in completed:
            return {"status":"completed","missing_prereqs":[],"current_coherence":self.state.get("coherence",0.5),"required_coherence":lesson.get("min_coherence",0)}
        missing = [p for p in lesson.get("prerequisites",[]) if p not in completed]
        coh = self.state.get("coherence",0.5)
        req_coh = lesson.get("min_coherence",0)
        if missing or coh < req_coh:
            reasons = []
            if missing: reasons.append(f"Need: {', '.join(missing[:3])}")
            if coh < req_coh: reasons.append(f"Coherence {coh:.2f} < required {req_coh:.2f}")
            return {"status":"locked","reason":" | ".join(reasons),"missing_prereqs":missing,"current_coherence":coh,"required_coherence":req_coh}
        return {"status":"available","reason":"Ready to start","missing_prereqs":[],"current_coherence":coh,"required_coherence":req_coh}

    def mark_lesson_completed(self, lesson_key: str, final_coherence: float = None) -> dict:
        lesson = LESSONS.get(lesson_key)
        if not lesson: return {"status":"error"}
        completed = self.state.get("lessons_completed",[])
        if lesson_key in completed: return {"status":"already_completed"}
        xp_earned = lesson.get("xp",15)
        new_xp = self.state.get("total_xp",0) + xp_earned
        coh_boost = min(0.02, xp_earned/5000)
        new_coh = min(1.0, self.state.get("coherence",0.5) + coh_boost)
        if final_coherence is not None: new_coh = max(new_coh, min(1.0, final_coherence))
        completed.append(lesson_key)
        self.state.update({"lessons_completed":completed,"total_xp":new_xp,"coherence":round(new_coh,6)})
        badge = lesson.get("grants_badge")
        if badge:
            badges = self.state.get("badges",[]); badges.append(badge); self.state["badges"] = badges
        self._save_state()
        self._write_to_truth_log(f"COMPLETED: {lesson.get('title','')} | XP:{xp_earned}")
        if xp_earned >= 60:
            try:
                from rune_memory import RuneMemory
                RuneMemory().record(f"LESSON COMPLETE: {lesson.get('title','')} | XP:{xp_earned}",source="curriculum",coherence=new_coh,tags=["lesson_complete",lesson_key])
            except Exception: pass
        return {"lesson":lesson.get("title",""),"lesson_key":lesson_key,"xp_earned":xp_earned,"rune_earned":lesson.get("rune","TRUTH•RUNE"),"new_coherence":round(new_coh,6),"total_xp":new_xp,"badge":badge,"status":"completed","total_lessons_done":len(completed)}

    def get_unlocked_lessons(self, department: str = None) -> list:
        return [{"key":k,"lesson":l,"status":self.get_lesson_status(k)} for k,l in LESSONS.items() if (not department or k.startswith(department)) and self.get_lesson_status(k)["status"]=="available"]

    def get_degree_eligibility(self) -> dict:
        # Degrees now live in ONE place: degrees.py (canonical source of truth).
        from degrees import eligibility_report
        return eligibility_report(
            self.state.get("total_xp", 0),
            self.state.get("coherence", 0.5),
            len(self.state.get("lessons_completed", [])),
            self.state.get("child_rune_confirmations", 0),
        )


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

    def _grade_answer(self, answer: str) -> dict:
        """
        Real quality grade of a steelman answer. Returns a 0-1 coherence that
        reflects the strength of the *argument* (via SteelmanAnalyzer), an
        `adequate` flag gating rewards, and specific, warm feedback.
        Falls back to the legacy heuristic only if the analyzer is unavailable.
        """
        if HAS_ANALYZER and self.lesson:
            try:
                an = SteelmanAnalyzer(use_ai=False, use_monte_carlo=False)
                r  = an.analyze(self.lesson.get("steelman", ""), answer)
                overall = float(r.get("overall_score", 0.0))
                resist  = float(r.get("adversarial", {}).get("resistance_score", 0.0))
                # Resistance is the practical signal; blend with overall quality.
                coherence = round(min(1.0, max(0.20, 0.6 * resist + 0.4 * overall)), 3)
                # Adequate = a real attempt that survived basic adversarial critique.
                adequate  = (len(answer.split()) >= 25 and r.get("grade", "F") != "F")
                recs = r.get("recommendations", [])
                if adequate:
                    fb = f"Solid work, {self.kid_name}! " + (
                        recs[0] if recs else "Now push the argument one level deeper.")
                else:
                    fb = (f"Good start, {self.kid_name} — but that's not a full steelman yet. "
                          "Build the *strongest* version of the other side: ") + (
                        recs[0] if recs else
                        "start with 'The strongest argument is...' and give a real reason.")
                return {"coherence": coherence, "adequate": adequate,
                        "feedback": fb, "grade": r.get("grade", "F")}
            except Exception:
                pass
        # Fallback (analyzer missing): legacy additive heuristic.
        delta     = self._score_locally(answer)
        coherence = round(min(1.0, self.kid_coherence + delta), 3)
        return {"coherence": coherence,
                "adequate":  coherence >= self.lesson["min_coherence"],
                "feedback":  self._local_feedback(coherence), "grade": "?"}

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

"""
demo.py — AUBIEETERNAL public "live demo" (Streamlit Community Cloud entrypoint)

This is a deliberately small, self-contained taster. It does NOT import app.py,
family_profiles, curriculum.py, or the swarm, so none of the StartOS /mnt/main
filesystem assumptions run here. It writes nothing to disk — session XP lives in
st.session_state and resets on refresh.

Point the Streamlit Cloud app's "Main file path" at this file (demo.py).

Optional live tutor
-------------------
If an OpenAI-compatible key is present, the "Try a lesson" flow generates the
lesson and responds to your answer with a real model. Otherwise it falls back to
hand-written sample lessons so the demo always works.

Set in the Streamlit app's Secrets (or as env vars):
    OPENAI_API_KEY   = "sk-..."          # required for the live tutor
    OPENAI_BASE_URL  = "https://..."     # optional — any OpenAI-compatible endpoint
    DEMO_MODEL       = "gpt-4o-mini"     # optional — defaults to gpt-4o-mini
"""

from __future__ import annotations

import os
import streamlit as st

st.set_page_config(page_title="AUBIEETERNAL — Live Demo", page_icon="🦅", layout="centered")

SITE_URL = "https://aubieeternal-institute-inc.github.io/AUBIEETERNAL/"
INSTALL_URL = SITE_URL + "#self-hosted"
REPO_URL = "https://github.com/AUBIEETERNAL-INSTITUTE-INC/AUBIEETERNAL"

# ─────────────────────────────────────────────────────────────────────────────
# Curriculum — copied as plain data from curriculum.py's CURRICULUM_TREE so this
# file has no import chain. Keep in rough sync by hand; it's a demo.
# Each level: (key, title, age_guidance, xp)
# ─────────────────────────────────────────────────────────────────────────────
CURRICULUM_TREE = [
    {"track": "🦁 Courage", "color": "#00cfff", "levels": [
        ("courage-1", "What Is Courage?", "All ages", 15),
        ("courage-2", "Social Courage", "8+", 18),
        ("courage-3", "Intellectual Courage", "10+", 22),
        ("courage-4", "Antifragile Courage", "12+", 25),
        ("courage-5", "Long-Game Courage", "14+", 35),
    ]},
    {"track": "⚡ Antifragility", "color": "#ff6b35", "levels": [
        ("antifragility-1", "Systems That Grow Stronger", "All", 18),
        ("antifragility-2", "Barbell Strategy", "10+", 22),
        ("antifragility-3", "Black Swans", "12+", 28),
        ("antifragility-4", "Hormesis", "14+", 32),
    ]},
    {"track": "₿ Bitcoin", "color": "#f7931a", "levels": [
        ("bitcoin-sovereignty-1", "Your Keys = Your Coins", "All", 20),
        ("bitcoin-sovereignty-2", "Fixed Supply", "9+", 22),
        ("bitcoin-sovereignty-3", "Runes + On-Chain Truth", "11+", 25),
        ("bitcoin-sovereignty-4", "Lightning Network", "13+", 30),
    ]},
    {"track": "⚔️ Steelmanning", "color": "#a020f0", "levels": [
        ("steelmanning-1", "Argue the Other Side", "8+", 22),
        ("steelmanning-2", "Steel in Bad Arguments", "11+", 26),
        ("steelmanning-3", "Epistemic Humility", "13+", 30),
    ]},
    {"track": "💚 Nervous System", "color": "#00ff88", "levels": [
        ("polyvagal-1", "3 Modes of Safety", "All", 15),
        ("polyvagal-2", "Co-Regulation", "8+", 18),
        ("polyvagal-3", "Hormesis for the Mind", "12+", 25),
    ]},
    {"track": "🌀 Simulation", "color": "#00cfff", "levels": [
        ("simulation-1", "Is Reality a Simulation?", "10+", 20),
        ("simulation-2", "Bostrom's Trilemma", "13+", 25),
        ("simulation-3", "Planck Constraints", "14+", 30),
        ("simulation-4", "Observer Effect", "15+", 35),
    ]},
    {"track": "💡 Wonder", "color": "#ffcf00", "levels": [
        ("wonder-1", "Awe as Signal", "All", 15),
        ("wonder-2", "Wonder Index", "11+", 20),
    ]},
    {"track": "🏛️ Stoic", "color": "#8899bb", "levels": [
        ("stoic-1", "Dichotomy of Control", "9+", 18),
        ("stoic-2", "Negative Visualization", "11+", 22),
        ("stoic-3", "Amor Fati", "13+", 28),
    ]},
]

# ─────────────────────────────────────────────────────────────────────────────
# Hand-written sample lessons — used when there's no API key. (body, question)
# ─────────────────────────────────────────────────────────────────────────────
CANNED: dict[str, tuple[str, str]] = {
    "courage-1": (
        "**Courage isn't the absence of fear — it's action in the presence of fear.**\n\n"
        "- Fear is information: it points at something that matters to you.\n"
        "- Courage is the choice to move *toward* that thing anyway, in a small, deliberate step.\n"
        "- It's a muscle. Every time you do the slightly-scary thing, the next one gets easier.\n\n"
        "The bravest people aren't fearless. They've just practised acting while afraid so many "
        "times that it stopped being remarkable.",
        "Think of one small thing you've been avoiding because it's a little scary. "
        "What is it, and what would the first tiny step look like?",
    ),
    "antifragility-1": (
        "**Some things break under stress. Some things survive it. A few things get *stronger* from it — those are antifragile.**\n\n"
        "- *Fragile:* a wine glass. Shock is pure downside.\n"
        "- *Robust:* a rock. Shock does nothing either way.\n"
        "- *Antifragile:* your muscles, your immune system, a good idea under criticism. The right dose of stress is what makes them grow.\n\n"
        "The goal isn't to avoid all stress — it's to find the dose that builds you rather than the dose that wrecks you.",
        "Name one part of your life that's fragile (a shock would really hurt it). "
        "What's one change that would make it more robust or antifragile?",
    ),
    "bitcoin-sovereignty-1": (
        "**\"Not your keys, not your coins.\"**\n\n"
        "- A bitcoin balance on an exchange is really an *IOU* — the exchange holds the keys, so they hold the coins.\n"
        "- A private key you control is the actual thing. No one can freeze it, reverse it, or print more.\n"
        "- With that power comes responsibility: lose the key, lose the coins. Sovereignty and self-reliance are the same coin.\n\n"
        "This is the whole point of the technology: value you can hold directly, without asking permission.",
        "In your own words: what's the difference between \"having bitcoin on an app\" "
        "and \"holding your own keys\"? Why might it matter?",
    ),
    "steelmanning-1": (
        "**Before you argue against an idea, build the *strongest* version of it — the steelman.**\n\n"
        "- A strawman is the weak, silly version of the other side that's easy to knock down.\n"
        "- A steelman is the version its smartest supporter would actually defend.\n"
        "- If you can't state the other side so well that they'd say \"yes, that's it\" — you don't understand it well enough to disagree yet.\n\n"
        "Steelmanning makes you harder to fool and much more persuasive.",
        "Pick something you disagree with. Write the single best reason a thoughtful "
        "person might believe it — no mocking, no \"but actually\".",
    ),
    "polyvagal-1": (
        "**Your nervous system is always asking one question: *am I safe right now?* It has three basic answers.**\n\n"
        "- **Safe & connected** — calm, curious, able to learn and be with people.\n"
        "- **Fight or flight** — mobilised, heart racing, looking for the exit or the argument.\n"
        "- **Shutdown** — foggy, numb, checked out; the system hit the brakes hard.\n\n"
        "None of these are \"bad\" — they're protection. The skill is *noticing* which mode you're in, "
        "because you can't think clearly from the bottom two.",
        "Which of the three modes do you land in most often under pressure? "
        "What's one thing that helps you come back to safe & connected?",
    ),
    "simulation-1": (
        "**Could reality be a simulation? It's not a silly question — it's a serious one about evidence.**\n\n"
        "- If a civilisation could run detailed simulations of conscious beings, it might run *many* of them.\n"
        "- Then simulated minds would vastly outnumber \"base reality\" ones — so, statistically, which are you?\n"
        "- The useful part isn't the answer. It's the habit: holding a wild idea seriously enough to reason about it *without* either scoffing or believing.\n\n"
        "That habit — taking strange hypotheses seriously and testing them — is how science got started.",
        "What kind of evidence, even in principle, would make you more or less "
        "confident that reality is simulated?",
    ),
    "wonder-1": (
        "**Awe — that shiver at a night sky or a huge idea — is a signal worth paying attention to.**\n\n"
        "- Awe tends to show up right at the edge of what you understand.\n"
        "- It makes the self feel smaller and the world feel bigger — which is exactly the state good learning happens in.\n"
        "- Chasing wonder on purpose (big questions, big landscapes, deep books) is a legitimate strategy, not a distraction.\n\n"
        "AUBIEETERNAL treats your sense of wonder as a compass for what to learn next.",
        "When was the last time something genuinely gave you a sense of awe? "
        "What was it about — and is there a thread there worth pulling on?",
    ),
    "stoic-1": (
        "**The dichotomy of control: some things are up to you, most things aren't. Peace comes from knowing which is which.**\n\n"
        "- *Up to you:* your choices, your effort, your response, what you pay attention to.\n"
        "- *Not up to you:* other people, outcomes, the past, the weather, what's already happened.\n"
        "- Spend your energy on the first list. Hold the second list lightly.\n\n"
        "This isn't giving up — it's aiming your effort where it actually works.",
        "Describe something that's stressing you. Split it into the part that's in "
        "your control and the part that isn't. What changes when you do that?",
    ),
}

GENERIC_QUESTION = "What's one way you could use this idea in your own life this week?"


# ─────────────────────────────────────────────────────────────────────────────
# Optional LLM
# ─────────────────────────────────────────────────────────────────────────────
def _secret(key: str, default=None):
    try:
        if key in st.secrets:  # raises if no secrets file at all
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key, default)


DEMO_MODEL = _secret("DEMO_MODEL", "gpt-4o-mini")


@st.cache_resource(show_spinner=False)
def _client():
    api_key = _secret("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI
        kw = {"api_key": api_key}
        base = _secret("OPENAI_BASE_URL")
        if base:
            kw["base_url"] = base
        return OpenAI(**kw)
    except Exception:
        return None


def _ask(system: str, user: str, max_tokens: int = 550) -> str | None:
    client = _client()
    if client is None:
        return None
    try:
        r = client.chat.completions.create(
            model=DEMO_MODEL,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            temperature=0.7,
            max_tokens=max_tokens,
            timeout=30,
        )
        return (r.choices[0].message.content or "").strip() or None
    except Exception:
        return None


TUTOR_SYSTEM = (
    "You are a tutor for AUBIEETERNAL, a sovereign, local-first family education system. "
    "Teach with warmth, plain language, and respect for the learner's intelligence. "
    "Keep it tight."
)


def build_lesson(track: str, title: str, age: str, key: str) -> tuple[str, str, str]:
    """Return (body_markdown, question, mode) where mode is 'live' or 'sample'."""
    live = _ask(
        TUTOR_SYSTEM,
        f"Teach a ~180-word micro-lesson titled \"{title}\" (track: {track}, audience: {age}). "
        f"Use 3 short bullet points and a one-line takeaway. "
        f"Then, on the LAST line only, write a single reflection question prefixed exactly with 'QUESTION: '.",
        max_tokens=550,
    )
    if live:
        body, question = live, GENERIC_QUESTION
        if "QUESTION:" in live:
            body, _, q = live.rpartition("QUESTION:")
            body, question = body.strip(), q.strip()
        return body, question, "live"

    if key in CANNED:
        body, question = CANNED[key]
        return body, question, "sample"

    body = (
        f"**{title}** — a lesson in the {track} track (for {age}).\n\n"
        "- Every AUBIEETERNAL lesson starts from a real question, not a definition to memorise.\n"
        "- It connects the idea to something you can try or notice in daily life.\n"
        "- It ends with a reflection, because thinking it through is where the learning sticks.\n\n"
        "_This is a placeholder summary. With a tutor key configured, this lesson is written "
        "for you on the spot — and in the full app it adapts to your answers over time._"
    )
    return body, GENERIC_QUESTION, "sample"


def build_feedback(title: str, question: str, answer: str) -> str:
    live = _ask(
        TUTOR_SYSTEM,
        f"Lesson: \"{title}\". You asked the learner: \"{question}\". "
        f"They answered: \"{answer}\". Give 2-4 sentences of encouraging, specific feedback: "
        f"name something good in their thinking and offer one gentle nudge or next thought.",
        max_tokens=300,
    )
    if live:
        return live
    return (
        "Nice — you actually engaged with the core idea, which is the whole point. "
        "In the full AUBIEETERNAL, your tutor responds to exactly what you wrote, "
        "catches misconceptions, and picks your next lesson based on your answer. "
        "This demo just cheers you on. 🦅"
    )


# ─────────────────────────────────────────────────────────────────────────────
# State
# ─────────────────────────────────────────────────────────────────────────────
ss = st.session_state
ss.setdefault("xp", 0)
ss.setdefault("done", set())          # lesson keys completed this session
ss.setdefault("lessons", {})          # key -> (body, question, mode)
ss.setdefault("open_key", None)

LEVELS_BY_KEY = {
    lvl[0]: (t["track"], lvl[1], lvl[2], lvl[3])
    for t in CURRICULUM_TREE for lvl in t["levels"]
}


# ─────────────────────────────────────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div style="text-align:center;padding:.5rem 0 0">
      <div style="font-size:2rem;font-weight:800;letter-spacing:-.02em">🦅 AUBIEETERNAL</div>
      <div style="font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.72rem;
                  letter-spacing:.12em;text-transform:uppercase;opacity:.6;margin-top:.35rem">
        Sovereign &nbsp;·&nbsp; Local-First &nbsp;·&nbsp; Open Source
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

live_mode = _client() is not None
st.caption(
    f"🟢 Live tutor connected ({DEMO_MODEL})" if live_mode
    else "📖 Sample mode — hand-written lessons (no tutor key configured)"
)

# Rendered here, but filled at the end of the script so the numbers reflect any
# XP awarded during this run (Streamlit executes top-to-bottom).
metrics_slot = st.container()

st.info(
    "**This is a live demo — a taster of AUBIEETERNAL.** Nothing you do here is saved. "
    f"The real thing runs on your own computer, works offline, keeps your family's progress, "
    f"and has no gatekeepers.  \n➡️ **[Run the real AUBIEETERNAL]({INSTALL_URL})** · "
    f"[Source on GitHub]({REPO_URL})"
)

st.divider()
st.subheader("📚 Browse the curriculum")

track_names = [t["track"] for t in CURRICULUM_TREE]
track_name = st.selectbox("Track", track_names, index=0)
track = next(t for t in CURRICULUM_TREE if t["track"] == track_name)

lesson_labels = [f"{lvl[1]}  ·  {lvl[2]}  ·  {lvl[3]} XP" for lvl in track["levels"]]
idx = st.selectbox(
    "Lesson", range(len(lesson_labels)), format_func=lambda i: lesson_labels[i]
)
sel_key, sel_title, sel_age, sel_xp = track["levels"][idx]

if st.button("Open this lesson  →", type="primary", use_container_width=True):
    if sel_key not in ss["lessons"]:
        with st.spinner("Preparing your lesson…"):
            ss["lessons"][sel_key] = build_lesson(track_name, sel_title, sel_age, sel_key)
    ss["open_key"] = sel_key

open_key = ss["open_key"]
if open_key and open_key in ss["lessons"]:
    body, question, mode = ss["lessons"][open_key]
    o_track, o_title, o_age, o_xp = LEVELS_BY_KEY[open_key]

    st.divider()
    st.markdown(f"### {o_title}")
    st.caption(f"{o_track}  ·  {o_age}  ·  worth {o_xp} XP  ·  "
               + ("freshly written for you" if mode == "live" else "sample lesson"))
    st.markdown(body)

    st.markdown(f"**🤔 {question}**")
    answer = st.text_area("Your answer", key=f"ans_{open_key}", height=120,
                          placeholder="A sentence or two is plenty…")

    if st.button("Check my answer", key=f"chk_{open_key}"):
        if not answer.strip():
            st.warning("Write a little something first 🙂")
        else:
            with st.spinner("Reading your answer…"):
                fb = build_feedback(o_title, question, answer)
            st.success(fb)
            if open_key not in ss["done"]:
                ss["done"].add(open_key)
                ss["xp"] += o_xp
                st.balloons()
                st.toast(f"+{o_xp} XP", icon="🦅")
            else:
                st.caption("(Already counted this one this session.)")

with metrics_slot:
    mc1, mc2 = st.columns(2)
    mc1.metric("Session XP", ss["xp"])
    mc2.metric("Lessons tried", len(ss["done"]))

st.divider()
st.markdown(
    f"""
    <div style="text-align:center;opacity:.75;font-size:.9rem;line-height:1.6">
      Like what you see? This demo is a sliver of the full system.<br>
      <b><a href="{INSTALL_URL}" target="_blank">Install AUBIEETERNAL on your own computer →</a></b><br>
      Free · offline-capable · no subscriptions · yours forever
    </div>
    """,
    unsafe_allow_html=True,
)

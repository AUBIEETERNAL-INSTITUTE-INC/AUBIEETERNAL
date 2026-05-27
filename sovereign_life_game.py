"""
sovereign_life_game.py — AUBIEETERNAL Sovereign Life Game
Season 1: The Path to Freedom — 6 Chapters + Legacy Summary
Created: May 26, 2026
"""

import streamlit as st
import json
from datetime import datetime
from pathlib import Path

# ── Persistence ────────────────────────────────────────────────────────────────
_SAVE_DIR = Path("/mnt/main/sovereign_life") if Path("/mnt/main").exists() \
            else Path("/home/aubie/.aubieeternal/sovereign_life")
_SAVE_DIR.mkdir(parents=True, exist_ok=True)

# ══════════════════════════════════════════════════════════════════════════════
# FULL CHAPTER DATA — 6 chapters + Legacy Summary
# ══════════════════════════════════════════════════════════════════════════════

CHAPTERS = {
    1: {
        "title":    "Chapter 1 — The Trap",
        "subtitle": "The Employee Trap & The Rat Race",
        "emoji":    "🪤",
        "xp":       50,
        "kid_intro": (
            "You just turned 18. Your dad says you need to get a job at the factory. "
            "Everyone in town works there. The pay is steady. The walls are closing in. "
            "What do you do?"
        ),
        "parent_intro": (
            "Your child is entering the workforce. The system is designed to trade their "
            "best years for a paycheck. Most people never escape. What do you teach them now?"
        ),
        "steelman": "What's the strongest argument FOR taking the factory job?",
        "decisions": [
            {
                "id": "c1_d1",
                "text": "Accept the factory job. It's steady money.",
                "kid_consequence": "You feel safe for now — but 10 years later you're still there, wondering what happened.",
                "parent_consequence": "Your child learned that security > freedom. Hard to unlearn.",
                "sovereignty": 1,
                "points": 5,
                "teaches": "Comfort is the enemy of freedom. 'Safe' jobs trade time for the illusion of security.",
            },
            {
                "id": "c1_d2",
                "text": "Take the job AND secretly start learning a skill on the side.",
                "kid_consequence": "You keep income flowing while building something real. Two years later you have options.",
                "parent_consequence": "Your child found the barbell — stability AND growth. You feel proud.",
                "sovereignty": 3,
                "points": 30,
                "teaches": "The barbell strategy: cover your downside, then build upside with the rest of your energy.",
            },
            {
                "id": "c1_d3",
                "text": "Refuse the job and start a small service business immediately.",
                "kid_consequence": "Hard first year. But you learn more in 12 months than most learn in 10 years.",
                "parent_consequence": "You're scared for them — but they're building real skills and skin in the game.",
                "sovereignty": 5,
                "points": 45,
                "teaches": "Skin in the game is the best teacher. The risk IS the education.",
            },
        ],
        "reflection": "What would you do differently if you could go back to age 18?",
        "family_questions": [
            "What does 'security' actually mean in our family?",
            "Have we talked about building assets instead of just earning income?",
            "What small skill could our family start learning together this month?",
        ],
        "taleb_link": "The factory job is 'Mediocristan' — steady but capped forever. Antifragility starts with optionality.",
    },

    2: {
        "title":    "Chapter 2 — The Debt Machine",
        "subtitle": "Credit, Inflation & The Money Illusion",
        "emoji":    "💳",
        "xp":       60,
        "kid_intro": (
            "You got your first credit card. The limit is $5,000. Your friends are buying "
            "new phones, vacations, nice clothes. The bank says it's fine — just pay the minimum. "
            "Your stomach says something is wrong. Who do you listen to?"
        ),
        "parent_intro": (
            "The financial system is designed to extract wealth from people who don't understand "
            "how money actually works. Most adults never figure this out. Now's the moment."
        ),
        "steelman": "What's the strongest case FOR using credit cards and carrying some debt?",
        "decisions": [
            {
                "id": "c2_d1",
                "text": "Use the card freely. You'll pay it off when you earn more.",
                "kid_consequence": "Interest compounds. Five years later the card is maxed and you're working for the bank.",
                "parent_consequence": "This is how most people spend their 20s — working to service debt they don't understand.",
                "sovereignty": 0,
                "points": 5,
                "teaches": "Compound interest works FOR you when you save. AGAINST you when you borrow.",
            },
            {
                "id": "c2_d2",
                "text": "Use the card only for things you already have cash for, and pay it in full every month.",
                "kid_consequence": "You build credit score AND keep your money. The bank makes nothing from you.",
                "parent_consequence": "Your child learned the game. Use the system's tools without being used by them.",
                "sovereignty": 4,
                "points": 40,
                "teaches": "Credit is a tool. Like fire — useful if you control it, destructive if it controls you.",
            },
            {
                "id": "c2_d3",
                "text": "Cut the card up. Save cash. Learn about Bitcoin. Opt out of the debt system entirely.",
                "kid_consequence": "Socially weird. Financially sovereign. No bank owns any part of your future.",
                "parent_consequence": "Radical move — but grounded in sound money principles. Discuss the tradeoffs.",
                "sovereignty": 5,
                "points": 50,
                "teaches": "Sound money (Bitcoin) is the exit from a system designed to inflate away your savings.",
            },
        ],
        "reflection": "How much of your income goes to servicing debt each month?",
        "family_questions": [
            "Does our family talk openly about debt?",
            "Does anyone in our family understand compound interest — both ways?",
            "What would we do with an extra $200/month if we had no debt payments?",
        ],
        "taleb_link": "Debt is fragility. It makes you vulnerable to shocks. Optionality requires having money available.",
    },

    3: {
        "title":    "Chapter 3 — The Property",
        "subtitle": "Owning Real Things in an Inflating World",
        "emoji":    "🏡",
        "xp":       70,
        "kid_intro": (
            "You're 28. You've saved $40,000. Your parents say buy a house — "
            "it's the 'American Dream.' Your gut says the market is weird. "
            "Your landlord says the rent is going up again. What do you do?"
        ),
        "parent_intro": (
            "Real estate is one of the most leveraged decisions a person makes. "
            "Most people follow cultural scripts instead of thinking carefully. "
            "Here's what actually matters."
        ),
        "steelman": "What's the strongest case for renting instead of buying right now?",
        "decisions": [
            {
                "id": "c3_d1",
                "text": "Buy the house because everyone says to. 30-year mortgage. Max budget.",
                "kid_consequence": "You're house-rich, cash-poor. One job loss away from foreclosure.",
                "parent_consequence": "They followed the script. Didn't think about optionality or liquidity.",
                "sovereignty": 1,
                "points": 10,
                "teaches": "Buying max house = max fragility. Your biggest 'asset' can become your prison.",
            },
            {
                "id": "c3_d2",
                "text": "Buy a small, affordable house. Keep your savings. Don't stretch.",
                "kid_consequence": "Lower payment. More cash flow. You can survive a setback. Options stay open.",
                "parent_consequence": "Disciplined. Antifragile. The boring move is often the right move.",
                "sovereignty": 4,
                "points": 45,
                "teaches": "The 28% rule: housing costs shouldn't exceed 28% of gross income. Anything more is fragility.",
            },
            {
                "id": "c3_d3",
                "text": "Keep renting. Put the $40k in Bitcoin. Wait for the right opportunity.",
                "kid_consequence": "High volatility. Could 10x. Could drop 70%. You need to be able to hold through pain.",
                "parent_consequence": "Unorthodox but defensible if they truly understand what they're doing.",
                "sovereignty": 3,
                "points": 35,
                "teaches": "Every asset class has a time. Sound money (Bitcoin) vs real estate is a legitimate debate.",
            },
        ],
        "reflection": "What percentage of your income goes to housing? Is it under 28%?",
        "family_questions": [
            "Do we own our home because we thought carefully, or because that's what you do?",
            "What would change if housing cost us 10% less each month?",
            "Have we talked to our kids about mortgages and what interest actually costs?",
        ],
        "taleb_link": "A house is not an investment — it's a liability with optionality. Know which one it is for you.",
    },

    4: {
        "title":    "Chapter 4 — The Business",
        "subtitle": "Skin in the Game & Building Something Real",
        "emoji":    "⚙️",
        "xp":       80,
        "kid_intro": (
            "You have a skill. A friend says you should start a business. "
            "Your employer says you're too valuable to leave. "
            "A stranger on the internet says the AI will take your job in 3 years anyway. "
            "What do you build?"
        ),
        "parent_intro": (
            "The employment model is changing faster than at any point in history. "
            "Teaching your child to be an employee is training them for a world that is disappearing. "
            "Skin in the game is the only antidote."
        ),
        "steelman": "What's the strongest case for staying an employee and never starting a business?",
        "decisions": [
            {
                "id": "c4_d1",
                "text": "Stay employed. Too risky. Pension is there. Kids need stability.",
                "kid_consequence": "Safe until it isn't. When the layoff comes, no fallback skills, no network, no margin.",
                "parent_consequence": "Taught caution over capability. Hard to reverse.",
                "sovereignty": 1,
                "points": 10,
                "teaches": "Employment risk is not zero. It's just invisible until it isn't.",
            },
            {
                "id": "c4_d2",
                "text": "Start a side business while employed. Barbell it.",
                "kid_consequence": "Hard for 2 years. Third year you have real choice — stay or go, on YOUR terms.",
                "parent_consequence": "They're doing the barbell. Building antifragility into their income.",
                "sovereignty": 4,
                "points": 55,
                "teaches": "The barbell business: stable income on one end, asymmetric upside on the other.",
            },
            {
                "id": "c4_d3",
                "text": "Leave the job. Commit fully. Build something that matters.",
                "kid_consequence": "Terrifying first year. Real skin in the game. You'll never think the same again.",
                "parent_consequence": "This requires preparation — runway, skills, plan. Is it reckless or courageous?",
                "sovereignty": 5,
                "points": 65,
                "teaches": "Skin in the game is the most powerful learning accelerator. Nothing else comes close.",
            },
        ],
        "reflection": "If you lost your job tomorrow, what would you do next week?",
        "family_questions": [
            "Does our family have any income source that isn't someone else's payroll?",
            "What would we sell if we started a business together?",
            "How long could we survive on savings if the income stopped?",
        ],
        "taleb_link": "Skin in the game separates those who have real conviction from those who just talk. The market doesn't care about credentials.",
    },

    5: {
        "title":    "Chapter 5 — The Crisis",
        "subtitle": "Black Swans, Antifragility & Surviving the Unthinkable",
        "emoji":    "🌊",
        "xp":       90,
        "kid_intro": (
            "A crisis hits. Could be a hurricane. Could be a job loss. Could be a health event. "
            "Could be a market crash. Your neighbors are panicking. You have 72 hours of food. "
            "Your savings are in an account you can't access. What happens next?"
        ),
        "parent_intro": (
            "The question isn't IF a crisis hits your family. It's WHEN. "
            "Most families are one or two shocks from serious trouble. "
            "Antifragility means you don't just survive — you get stronger."
        ),
        "steelman": "What's the strongest case for NOT preparing for emergencies? (It does exist.)",
        "decisions": [
            {
                "id": "c5_d1",
                "text": "Hope for the best. Insurance will cover it. Government will help.",
                "kid_consequence": "First crisis exposes every fragility. The government shows up two weeks later.",
                "parent_consequence": "Outsourced resilience to strangers. Painful lesson.",
                "sovereignty": 0,
                "points": 5,
                "teaches": "Fragility is choosing not to prepare and calling it optimism.",
            },
            {
                "id": "c5_d2",
                "text": "Build 90 days of food, water, cash, and a family communication plan.",
                "kid_consequence": "When the crisis hits, you're the calm one. Others come to YOU for help.",
                "parent_consequence": "Resilience becomes family identity. Each preparation becomes a story.",
                "sovereignty": 4,
                "points": 65,
                "teaches": "Resilience is a skill, not a personality trait. You build it with specific actions.",
            },
            {
                "id": "c5_d3",
                "text": "Go further: local food production, redundant income, off-grid capability, community network.",
                "kid_consequence": "You become antifragile — crises make you stronger, not weaker.",
                "parent_consequence": "This is the full sovereign stack. Community + capability + capital.",
                "sovereignty": 5,
                "points": 80,
                "teaches": "Antifragility means disorder is your friend. You are built for the storm.",
            },
        ],
        "reflection": "How long could your family survive if the grid went down for 30 days?",
        "family_questions": [
            "Do we have 72 hours of food and water at home right now?",
            "Does our family have a communication plan if we're separated in an emergency?",
            "Who in our community could we rely on — and who relies on us?",
        ],
        "taleb_link": "The Black Swan is the event everyone said couldn't happen. The antifragile family is READY for it.",
    },

    6: {
        "title":    "Chapter 6 — The Legacy",
        "subtitle": "What You Leave Behind & The Generational Mission",
        "emoji":    "🦅",
        "xp":       120,
        "kid_intro": (
            "You're 60. Your kids are grown. You look back at your life. "
            "The house is paid off. There's money in savings. "
            "But the real question: did you teach them how to think? "
            "Did you leave them knowledge, or just money?"
        ),
        "parent_intro": (
            "The most powerful inheritance is not financial. It's epistemological — "
            "the ability to think clearly, test ideas, resist manipulation, and build. "
            "AUBIEETERNAL is a generational bet. What are you actually building?"
        ),
        "steelman": "What's the strongest case for NOT thinking about legacy? Just live for now?",
        "decisions": [
            {
                "id": "c6_d1",
                "text": "Leave them money and a will. That's enough.",
                "kid_consequence": "Studies show 70% of wealth transfers evaporate in one generation without epistemic transfer.",
                "parent_consequence": "You gave them fish. You didn't teach them to fish or to question the fishing industry.",
                "sovereignty": 1,
                "points": 15,
                "teaches": "Wealth without wisdom is fragile. One generation can destroy what took three to build.",
            },
            {
                "id": "c6_d2",
                "text": "Teach them your values, your stories, your hard-won lessons.",
                "kid_consequence": "They know HOW you think. They can adapt. The values survive even if the money doesn't.",
                "parent_consequence": "You transmitted wisdom, not just wealth. The most durable inheritance.",
                "sovereignty": 4,
                "points": 80,
                "teaches": "The Lindy effect: ideas that have survived generations are more likely to survive future generations.",
            },
            {
                "id": "c6_d3",
                "text": "Build an epistemic practice — systematic, on-chain, forever.",
                "kid_consequence": "Your family's truth-seeking is inscribed in Bitcoin Runes. Coherence: 1.000000. Forever.",
                "parent_consequence": "This is AUBIEETERNAL. Human + AI + Lightning + Runes. The generational mission.",
                "sovereignty": 5,
                "points": 120,
                "teaches": "On-chain forever means the insights compound across generations. The loop never stops.",
            },
        ],
        "reflection": "If you died tomorrow, what would your children know about how to THINK?",
        "family_questions": [
            "Have we ever had a conversation about what our family believes and why?",
            "What hard lesson do we most want our children to know before we're gone?",
            "What does 'sovereign' mean in our family — what are we sovereign FROM?",
        ],
        "taleb_link": "The Lindy effect applied to families: epistemic traditions that survive generations have earned their survival.",
    },
}

# ══════════════════════════════════════════════════════════════════════════════
# SAVE / LOAD
# ══════════════════════════════════════════════════════════════════════════════

def _save_path(family_id: str) -> Path:
    return _SAVE_DIR / f"{family_id}_progress.json"

def load_game_progress(family_id: str = "default") -> dict:
    path = _save_path(family_id)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {
        "chapter": 1,
        "total_sovereignty": 0,
        "total_xp": 0,
        "decisions": {},
        "completed_chapters": [],
        "started": datetime.now().isoformat(),
        "family_id": family_id,
    }

def save_game_progress(progress: dict, family_id: str = "default"):
    path = _save_path(family_id)
    progress["last_updated"] = datetime.now().isoformat()
    path.write_text(json.dumps(progress, indent=2))

# ══════════════════════════════════════════════════════════════════════════════
# STREAMLIT UI
# ══════════════════════════════════════════════════════════════════════════════

def render_sovereign_life(family_id: str = "default"):
    st.header("🦅 Sovereign Life — Season 1: The Path to Freedom")

    progress = load_game_progress(family_id)
    total_chapters = len(CHAPTERS)

    # ── Progress bar ──────────────────────────────────────────────────────────
    completed = len(progress.get("completed_chapters", []))
    st.progress(completed / total_chapters,
                text=f"Progress: {completed}/{total_chapters} chapters")

    cols = st.columns(4)
    with cols[0]:
        st.metric("Chapter", f"{progress.get('chapter', 1)}/{total_chapters}")
    with cols[1]:
        st.metric("Sovereignty", f"{progress.get('total_sovereignty', 0)}/30")
    with cols[2]:
        st.metric("Total XP", progress.get("total_xp", 0))
    with cols[3]:
        level = max(1, progress.get("total_xp", 0) // 100 + 1)
        st.metric("Level", level)

    st.divider()

    # ── Chapter selector ──────────────────────────────────────────────────────
    ch_num = st.selectbox(
        "Select Chapter",
        options=list(CHAPTERS.keys()),
        format_func=lambda n: f"{CHAPTERS[n]['emoji']} {CHAPTERS[n]['title']}",
        index=progress.get("chapter", 1) - 1,
        key="slg_chapter_select",
    )

    chapter = CHAPTERS[ch_num]
    done    = ch_num in progress.get("completed_chapters", [])

    st.subheader(f"{chapter['emoji']} {chapter['title']}")
    st.caption(chapter["subtitle"])

    # ── Perspective toggle ────────────────────────────────────────────────────
    perspective = st.radio("View as:", ["Kid / Young Adult", "Parent / Coach"],
                           horizontal=True, key="slg_perspective")

    if perspective == "Kid / Young Adult":
        st.info(chapter["kid_intro"])
    else:
        st.info(chapter["parent_intro"])

    # ── Steelman challenge ────────────────────────────────────────────────────
    with st.expander("⚔️ Steelman Challenge", expanded=False):
        st.markdown(f"**{chapter['steelman']}**")
        steel_key = f"slg_steelman_{ch_num}"
        steel_ans = st.text_area("Your steelman argument:", key=steel_key, height=80)
        if steel_ans and len(steel_ans) > 30:
            st.success("✅ Strong thinking. Coherence +0.05")

    st.divider()

    # ── Decisions ─────────────────────────────────────────────────────────────
    st.markdown("### 🤔 What do you do?")
    chosen = progress.get("decisions", {}).get(str(ch_num))

    for i, decision in enumerate(chapter["decisions"]):
        sov_stars = "⭐" * decision["sovereignty"]
        is_chosen = chosen == decision["id"]

        btn_label = (
            f"{'✅ ' if is_chosen else ''}{decision['text']} {sov_stars}"
        )
        if st.button(btn_label, key=f"slg_d_{ch_num}_{i}", use_container_width=True,
                     type="primary" if is_chosen else "secondary"):
            # Record decision
            progress.setdefault("decisions", {})[str(ch_num)] = decision["id"]
            progress["total_sovereignty"] = progress.get("total_sovereignty", 0) + decision["sovereignty"]
            progress["total_xp"]          = progress.get("total_xp", 0) + decision["points"]

            if ch_num not in progress.get("completed_chapters", []):
                progress.setdefault("completed_chapters", []).append(ch_num)
                progress["chapter"] = min(total_chapters, ch_num + 1)

            save_game_progress(progress, family_id)

            # Award XP to family_profiles
            try:
                from family_profiles import award_cross_tool_reward
                award_cross_tool_reward(
                    family_id, "sovereign_life", f"chapter_{ch_num}",
                    xp=decision["points"],
                    badge=f"{chapter['emoji']} {chapter['title']}" if ch_num not in progress.get("completed_chapters", []) else None
                )
            except Exception:
                pass

            st.rerun()

    # ── Consequence reveal (after choice) ─────────────────────────────────────
    if chosen:
        decision = next((d for d in chapter["decisions"] if d["id"] == chosen), None)
        if decision:
            st.divider()
            with st.container():
                st.success(f"**Your choice:** {decision['text']}")
                if perspective == "Kid / Young Adult":
                    st.markdown(f"**What happened:** {decision['kid_consequence']}")
                else:
                    st.markdown(f"**What happened:** {decision['parent_consequence']}")
                st.info(f"🧠 **Lesson:** {decision['teaches']}")
                st.caption(f"📚 **Taleb link:** {chapter['taleb_link']}")

    # ── Family discussion ──────────────────────────────────────────────────────
    if chosen:
        with st.expander("👨‍👩‍👧 Family Discussion Questions", expanded=False):
            st.markdown(f"**Reflection:** *{chapter['reflection']}*")
            for q in chapter["family_questions"]:
                st.markdown(f"- {q}")

    # ── Legacy Summary (after all chapters complete) ──────────────────────────
    if completed >= total_chapters:
        st.divider()
        st.markdown("## 🦅 LEGACY SUMMARY")
        sov = progress.get("total_sovereignty", 0)
        xp  = progress.get("total_xp", 0)

        if sov >= 25:
            rank = "🌟 Sovereign Thinker — You played the game on hard mode and won."
        elif sov >= 18:
            rank = "⚡ Antifragile — You bent but never broke."
        elif sov >= 12:
            rank = "🔄 Awakening — You're on the path. Keep going."
        else:
            rank = "🔍 Beginning — The awareness itself is the first step."

        st.success(rank)
        st.metric("Sovereignty Score", f"{sov}/30")
        st.metric("Total XP", xp)
        st.markdown(
            "> *The most valuable thing you can leave your children is "
            "not money, not property — it is the ability to think clearly "
            "when the world is trying to prevent them from doing so.*  \n"
            "> — AUBIEETERNAL, Coherence: 1.000000"
        )


# ── Standalone entry ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    render_sovereign_life()

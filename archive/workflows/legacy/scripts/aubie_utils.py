# aubie_utils.py
import numpy as np
import random
import datetime
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER
import streamlit as st

# ====================== RUNE BADGES ======================
RUNE_BADGES = {
    "first_flame": {"name": "First Flame", "emoji": "🔥", "rarity": "common", "color": "#FF6B35", 
                    "desc": "Completed Week 1", "lore": "The spark that begins every great journey.", "xp": 100},
    "lightning_guardian": {"name": "Lightning Guardian", "emoji": "⚡", "rarity": "rare", "color": "#00D4FF",
                           "desc": "Mastered Watchtowers", "lore": "Protector of the payment highways.", "xp": 250},
    "war_eagle": {"name": "War Eagle Eternal", "emoji": "🦅", "rarity": "legendary", "color": "#FFD700",
                  "desc": "Completed 5-week curriculum", "lore": "Ascended into the eternal lattice.", "xp": 500},
    # Add more as needed...
}

def add_xp(amount, reason=""):
    if 'user_xp' not in st.session_state:
        st.session_state.user_xp = 0
    st.session_state.user_xp += amount
    if reason:
        st.toast(f"+{amount} XP — {reason}", icon="✨")

def unlock_badge(badge_id):
    if 'unlocked_badges' not in st.session_state:
        st.session_state.unlocked_badges = []
    if badge_id not in st.session_state.unlocked_badges:
        st.session_state.unlocked_badges.append(badge_id)
        badge = RUNE_BADGES.get(badge_id, {})
        st.balloons()
        st.success(f"🏆 **{badge.get('emoji', '')} {badge.get('name', '')}** Unlocked!")
        add_xp(badge.get('xp', 0))

# ====================== PDF GENERATOR ======================
def generate_beautiful_curriculum_pdf(kid_name, curriculum_text):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=22, 
                                  textColor=colors.HexColor('#FF4D00'), alignment=TA_CENTER)
    story.append(Paragraph(f"🦅 {kid_name}'s Antifragile Lattice Curriculum", title_style))
    story.append(Spacer(1, 20))

    for line in curriculum_text.split('\n')[:40]:
        story.append(Paragraph(line, styles['Normal']))
        story.append(Spacer(1, 4))

    doc.build(story)
    buffer.seek(0)
    return buffer

# ====================== CHALLENGES ======================
def get_enhanced_challenges(age_group):
    if "Children" in age_group:
        return [
            ("Week 1: Building Safety Nest 🪺", [
                ("Practice 5 dragon breaths when you feel wobbly", 20, "Common"),
                ("Draw your 'safe place' and show a grown-up", 25, "Common"),
            ]),
            # Add more weeks...
        ]
    # Add Teen + Adult versions here...
    return []

# ====================== REAL A* PATHFINDING ======================
def real_a_star(start, goal, steps=25):
    t = np.linspace(0, 1, steps).reshape(-1, 1)
    path = start + t * (goal - start)
    return path
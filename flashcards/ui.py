"""Streamlit UI for kid-friendly flash cards."""
from __future__ import annotations

import streamlit as st

from .engine import (
    deck_progress_stats,
    get_deck_cards,
    get_deck_catalog,
    mark_knew,
    mark_practice,
    order_cards,
)

_CARD_CSS = """
<style>
.fc-wrap { text-align: center; margin: 0.5rem 0 1rem 0; }
.fc-card {
  display: flex; align-items: center; justify-content: center;
  min-height: 220px; padding: 1.5rem 1rem;
  border-radius: 18px;
  background: linear-gradient(160deg, #0d1a33 0%, #13284a 60%, #0a1428 100%);
  border: 3px solid #00cfff;
  box-shadow: 0 0 24px rgba(0,207,255,0.25);
  cursor: pointer;
  user-select: none;
}
.fc-card.back {
  border-color: #00ff88;
  box-shadow: 0 0 24px rgba(0,255,136,0.22);
  background: linear-gradient(160deg, #0d2818 0%, #143322 60%, #0a1a12 100%);
}
.fc-front {
  font-size: clamp(2.4rem, 10vw, 4.2rem);
  font-weight: 800; color: #e8f4ff;
  font-family: system-ui, -apple-system, Segoe UI, sans-serif;
  line-height: 1.15; word-break: break-word;
}
.fc-back {
  font-size: clamp(1.6rem, 6vw, 2.6rem);
  font-weight: 700; color: #e8fff4;
  font-family: system-ui, -apple-system, Segoe UI, sans-serif;
  line-height: 1.3; white-space: pre-wrap; word-break: break-word;
}
.fc-hint { font-size: 2.2rem; margin-top: 0.6rem; }
.fc-meta { color: #8899bb; font-size: 0.85rem; margin-top: 0.4rem; }
.fc-progress-label { color: #a8b8d8; font-size: 0.9rem; margin-bottom: 0.25rem; }
</style>
"""


def _profile_name() -> str:
    cf = st.session_state.get("current_family") or {}
    if cf.get("kid_name"):
        return str(cf["kid_name"])
    return str(st.session_state.get("kid_name") or "Explorer")


def _ensure_state(deck_id: str, cards: list, shuffle: bool, profile: str) -> None:
    key_deck = "fc_deck_id"
    key_idx = "fc_idx"
    key_flip = "fc_flipped"
    key_order = "fc_order_ids"
    if (
        st.session_state.get(key_deck) != deck_id
        or not st.session_state.get(key_order)
        or st.session_state.get("fc_shuffle_flag") != shuffle
        or st.session_state.get("fc_profile") != profile
    ):
        ordered = order_cards(profile, cards, shuffle=shuffle)
        st.session_state[key_deck] = deck_id
        st.session_state[key_order] = [c["id"] for c in ordered]
        st.session_state[key_idx] = 0
        st.session_state[key_flip] = False
        st.session_state["fc_shuffle_flag"] = shuffle
        st.session_state["fc_profile"] = profile
        st.session_state["fc_cards_by_id"] = {c["id"]: c for c in cards}


def render_flashcards(profile: str | None = None) -> None:
    st.markdown(_CARD_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="card-title">📋 Flash Cards — ABC · Math · Reading · Coins</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Tap the card to flip. Mark **I knew it** or **Practice again**. "
        "Progress stays on this computer only — just which cards you know. "
        "Money Smarts decks grow from little kids to teens."
    )

    profile = profile or _profile_name()
    catalog = get_deck_catalog()
    if not catalog:
        st.warning("No decks found. Add flashcards/decks.json.")
        return

    _AGE_LABEL = {
        "little": "Little (about 4–7)",
        "middle": "Middle (about 8–12)",
        "older": "Older (13+)",
        "": "All ages",
    }
    age_filter = st.radio(
        "Show decks for",
        ["Little first (all)", "Little only", "Middle only", "Older only"],
        horizontal=True,
        key="fc_age_filter",
        help="Little-kid decks are listed first by default. Money Smarts grows with age.",
    )
    filtered = catalog
    if age_filter == "Little only":
        filtered = [d for d in catalog if d.get("age_level") == "little"]
    elif age_filter == "Middle only":
        filtered = [d for d in catalog if d.get("age_level") == "middle"]
    elif age_filter == "Older only":
        filtered = [d for d in catalog if d.get("age_level") == "older"]
    if not filtered:
        filtered = catalog

    def _label(d):
        age = _AGE_LABEL.get(d.get("age_level") or "", "")
        group = " · Money" if d.get("group") == "money_smarts" else ""
        age_bit = f" · {age}" if age else ""
        return f"{d['emoji']} {d['title']}{group}{age_bit}"

    labels = [_label(d) for d in filtered]
    id_by_label = {_label(d): d["id"] for d in filtered}
    meta_by_id = {d["id"]: d for d in catalog}

    c1, c2 = st.columns([3, 1])
    with c1:
        choice = st.selectbox("Pick a deck", labels, key="fc_deck_pick")
    with c2:
        shuffle = st.checkbox("Shuffle", value=False, key="fc_shuffle")

    deck_id = id_by_label[choice]
    meta = meta_by_id[deck_id]

    # Regeneratable decks get a fresh batch when New set is pressed
    seed_key = f"fc_seed_{deck_id}"
    if meta.get("generated"):
        if st.button("🔄 New set of questions", key="fc_regen"):
            import time as _t
            st.session_state[seed_key] = _t.time_ns()
            st.session_state.pop("fc_order_ids", None)
            st.rerun()
        seed = st.session_state.get(seed_key)
    else:
        seed = None

    deck_meta, cards = get_deck_cards(deck_id, n_generated=20, seed=seed)
    if not cards:
        st.info(
            f"The **{meta['title']}** deck is empty right now. "
            "Edit `flashcards/decks.json` to add cards."
        )
        return

    _ensure_state(deck_id, cards, shuffle, profile)
    order_ids = st.session_state["fc_order_ids"]
    cards_by_id = st.session_state.get("fc_cards_by_id") or {c["id"]: c for c in cards}
    # Refresh card bodies for generated decks (ids may change with new seed)
    if meta.get("generated"):
        cards_by_id = {c["id"]: c for c in cards}
        st.session_state["fc_cards_by_id"] = cards_by_id
        # If order ids are stale after regen, rebuild
        if not all(i in cards_by_id for i in order_ids):
            ordered = order_cards(profile, cards, shuffle=shuffle)
            order_ids = [c["id"] for c in ordered]
            st.session_state["fc_order_ids"] = order_ids
            st.session_state["fc_idx"] = 0
            st.session_state["fc_flipped"] = False

    idx = int(st.session_state.get("fc_idx", 0))
    if idx >= len(order_ids):
        idx = 0
        st.session_state["fc_idx"] = 0
    card = cards_by_id.get(order_ids[idx])
    if not card:
        st.error("Card missing — try Shuffle or New set.")
        return

    stats = deck_progress_stats(profile, cards)
    st.markdown(
        f'<div class="fc-progress-label">Great job, <b>{profile}</b>! '
        f'You know {stats["known"]} of {stats["total"]} cards really well.</div>',
        unsafe_allow_html=True,
    )
    st.progress(min(1.0, stats["pct"] / 100.0), text=f'{stats["pct"]}% strong')

    flipped = bool(st.session_state.get("fc_flipped", False))
    front = str(card.get("front", ""))
    back = str(card.get("back", ""))
    hint = str(card.get("hint") or "")

    # Big tap-to-flip card (button overlays for accessibility on phone)
    side_class = "back" if flipped else ""
    body = back if flipped else front
    body_class = "fc-back" if flipped else "fc-front"
    hint_html = f'<div class="fc-hint">{hint}</div>' if (flipped and hint) else ""
    st.markdown(
        f'<div class="fc-wrap"><div class="fc-card {side_class}">'
        f'<div><div class="{body_class}">{body}</div>{hint_html}</div>'
        f'</div>'
        f'<div class="fc-meta">Card {idx + 1} of {len(order_ids)} — '
        f'{"answer" if flipped else "tap Flip to see answer"}</div></div>',
        unsafe_allow_html=True,
    )

    b1, b2, b3, b4 = st.columns(4)
    with b1:
        if st.button("🔄 Flip", key="fc_flip_btn", use_container_width=True, type="primary"):
            st.session_state["fc_flipped"] = not flipped
            st.rerun()
    with b2:
        if st.button("✅ I knew it", key="fc_knew", use_container_width=True):
            mark_knew(profile, card["id"])
            st.session_state["fc_flipped"] = False
            st.session_state["fc_idx"] = (idx + 1) % len(order_ids)
            # Re-order so practiced/known cards move appropriately next pass
            ordered = order_cards(profile, list(cards_by_id.values()), shuffle=shuffle)
            st.session_state["fc_order_ids"] = [c["id"] for c in ordered]
            # Keep advancing: find next after current if possible
            st.toast("Nice! This card will come back later.", icon="✅")
            st.rerun()
    with b3:
        if st.button("📚 Practice again", key="fc_practice", use_container_width=True):
            mark_practice(profile, card["id"])
            st.session_state["fc_flipped"] = False
            # Missed card comes back sooner: put it near the front
            ordered = order_cards(profile, list(cards_by_id.values()), shuffle=False)
            ids = [c["id"] for c in ordered]
            # Ensure this card is within the next few
            if card["id"] in ids:
                ids.remove(card["id"])
                ids.insert(min(2, len(ids)), card["id"])
            st.session_state["fc_order_ids"] = ids
            st.session_state["fc_idx"] = 0
            st.toast("OK — we'll try this one again soon.")
            st.rerun()
    with b4:
        if st.button("➡️ Next", key="fc_next", use_container_width=True):
            st.session_state["fc_flipped"] = False
            st.session_state["fc_idx"] = (idx + 1) % len(order_ids)
            st.rerun()

    with st.expander("About these cards & privacy"):
        st.markdown(
            f"""
**Deck:** {deck_meta.get('emoji', '')} {deck_meta.get('title', deck_id)}  
{deck_meta.get('description', '')}  
**Age level:** {deck_meta.get('ages') or deck_meta.get('age_level') or 'all'}

**How practice works:** each card has a box from 1 (needs practice) to 5 (you know it well).
"I knew it" means you will see this card again later, after others.
"Practice again" sends it to box 1 so it returns sooner.

**Privacy:** we only save the card id, its box number, and when you last saw it —
for **{profile}**, on this computer. No chat logs. Parents can delete
`/mnt/main/flashcards/` (or `~/.aubieeternal/main/flashcards/`) anytime.
            """.strip()
        )

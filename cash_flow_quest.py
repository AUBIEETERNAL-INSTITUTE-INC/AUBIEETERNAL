"""Cash Flow Quest — simple turn-based money game for kids 8+.

Education only — not financial advice. Local state per profile under /mnt/main.
Win when passive_income > living_expenses (out of the "rat race").
"""
from __future__ import annotations

import json
import os
import random
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import streamlit as st

# Verified mortgage math (30-year amortizing):
# $64,000 @ 6%/yr → ~$383.71 ≈ $384/mo
# $64,000 @ 9%/yr → ~$514.96 ≈ $515/mo
MORTGAGE_64K_6PCT = 384
MORTGAGE_64K_9PCT = 515

DISCLAIMER = (
    "This is a practice game for learning words and simple math. "
    "It is **not financial advice**. Real borrowing and investing need trusted adults."
)

MINDSET_TIPS = [
    "Habit tip: ask \"How could I afford a better deal later?\" instead of only \"I can't.\"",
    "Habit tip: notice whether a choice puts money in your pocket or takes it out.",
    "Habit tip: pay yourself first — keep a little cash buffer before doodads.",
    "Habit tip: losses are data. Review what happened without shaming yourself.",
    "Habit tip: being broke can be temporary; keep learning and planning (Kiyosaki popularized this idea — said kindly).",
    "Habit tip: long-term goals need some surplus after fun spending.",
]


def _data_dir() -> Path:
    if Path("/mnt/main").exists():
        d = Path("/mnt/main/cash_flow_quest")
    else:
        d = Path(os.path.expanduser("~/.aubieeternal/main/cash_flow_quest"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_profile(profile: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in (profile or "Explorer"))[:64]


def state_path(profile: str) -> Path:
    return _data_dir() / f"{_safe_profile(profile)}.json"


def default_state() -> dict:
    # Starter job: $3,000 earned income; living expenses $2,400 → +$600 cash flow
    # before any deals. Passive income starts at 0.
    return {
        "version": 1,
        "turn": 1,
        "cash": 2000,
        "salary": 3000,
        "living_expenses": 2400,
        "assets": [],          # {id, name, value, passive_mo, kind}
        "liabilities": [],     # {id, name, balance, payment_mo, rate_pct, kind}
        "log": [],
        "won": False,
        "deck_seed": None,
    }


def load_state(profile: str) -> dict:
    path = state_path(profile)
    if not path.exists():
        return default_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return default_state()
        base = default_state()
        base.update(data)
        return base
    except Exception:
        return default_state()


def save_state(profile: str, state: dict) -> None:
    path = state_path(profile)
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def passive_income(state: dict) -> int:
    return int(sum(int(a.get("passive_mo") or 0) for a in state.get("assets") or []))


def debt_payments(state: dict) -> int:
    return int(sum(int(l.get("payment_mo") or 0) for l in state.get("liabilities") or []))


def total_expenses(state: dict) -> int:
    return int(state.get("living_expenses") or 0) + debt_payments(state)


def earned_income(state: dict) -> int:
    return int(state.get("salary") or 0)


def monthly_cash_flow(state: dict) -> int:
    return earned_income(state) + passive_income(state) - total_expenses(state)


def net_worth(state: dict) -> int:
    assets = int(state.get("cash") or 0) + sum(int(a.get("value") or 0) for a in state.get("assets") or [])
    debts = sum(int(l.get("balance") or 0) for l in state.get("liabilities") or [])
    return assets - debts


def _tip() -> str:
    return random.choice(MINDSET_TIPS)


def _draw_card(state: dict) -> dict:
    """Return a card dict describing choices. Numbers are whole dollars."""
    has_rental = any(a.get("kind") == "rental" for a in state.get("assets") or [])
    cards = [
        {
            "id": "vending",
            "kind": "small_deal",
            "title": "Small deal: Vending machine",
            "blurb": "Cost $2,000 cash. Expected passive income +$80/month. Can break (−$40/mo) on a bad roll later.",
            "choices": ["buy", "skip"],
            "buy_cash": 2000,
            "asset": {"id": "vend", "name": "Vending machine", "value": 2000, "passive_mo": 80, "kind": "vending"},
            "tip": "Asset check: does this put money in your pocket after costs?",
        },
        {
            "id": "stock",
            "kind": "small_deal",
            "title": "Small deal: Stock bundle",
            "blurb": "Cost $1,000 cash. Portfolio-style income +$25/month in this game (simplified).",
            "choices": ["buy", "skip"],
            "buy_cash": 1000,
            "asset": {"id": "stock", "name": "Stock bundle", "value": 1000, "passive_mo": 25, "kind": "stock"},
            "tip": "Portfolio income is one income type — still practice, not advice.",
        },
        {
            "id": "rental",
            "kind": "small_deal",
            "title": "Small deal: Starter rental house",
            "blurb": (
                f"Price $80,000. Down payment $16,000 (20%). Loan $64,000 at 6%/year → "
                f"about ${MORTGAGE_64K_6PCT}/mo (30-year math). Rent $700. Upkeep $50. "
                f"Net passive if rented: 700 − {MORTGAGE_64K_6PCT} − 50 = "
                f"${700 - MORTGAGE_64K_6PCT - 50}/mo. Vacancy or rate hikes can erase that."
            ),
            "choices": ["buy", "borrow", "skip"],
            "buy_cash": 80000,  # all-cash path if somehow rich
            "borrow_down": 16000,
            "loan": {
                "id": "mtg-rental",
                "name": "Rental mortgage 6%",
                "balance": 64000,
                "payment_mo": MORTGAGE_64K_6PCT,
                "rate_pct": 6.0,
                "kind": "mortgage",
            },
            "asset_borrow": {
                "id": "rental",
                "name": "Starter rental",
                "value": 80000,
                "passive_mo": 700 - MORTGAGE_64K_6PCT - 50,  # 266
                "kind": "rental",
                "upkeep_mo": 50,
                "rent_mo": 700,
            },
            "asset_cash": {
                "id": "rental",
                "name": "Starter rental (owned free)",
                "value": 80000,
                "passive_mo": 700 - 50,
                "kind": "rental",
                "upkeep_mo": 50,
                "rent_mo": 700,
            },
            "tip": "Leverage can help or hurt. Empty months still owe the loan payment.",
        },
        {
            "id": "phone",
            "kind": "doodad",
            "title": "Doodad: New phone",
            "blurb": "Costs $800 cash. Fun now — takes money out of your pocket (liability-like spend).",
            "choices": ["buy", "skip"],
            "buy_cash": 800,
            "tip": "Instant gratification vs saving for assets — both are choices.",
        },
        {
            "id": "eatout",
            "kind": "doodad",
            "title": "Doodad: Eating out a lot",
            "blurb": "Costs $200 cash this month.",
            "choices": ["buy", "skip"],
            "buy_cash": 200,
            "tip": "A little fun is fine; watch monthly cash flow.",
        },
        {
            "id": "raise",
            "kind": "market",
            "title": "Market: Raise at work",
            "blurb": "Your salary increases by $200/month (earned income).",
            "choices": ["ok"],
            "salary_delta": 200,
            "tip": "Earned income helps — passive income is what frees the rat-race meter.",
        },
        {
            "id": "rates_up",
            "kind": "market",
            "title": "Market: Rates up",
            "blurb": (
                f"If you have a rental mortgage at 6% (${MORTGAGE_64K_6PCT}/mo), "
                f"a refinance shock moves it to 9% (~${MORTGAGE_64K_9PCT}/mo). "
                "Net passive falls. Deals can lose money."
            ),
            "choices": ["ok"],
            "tip": "Interest-rate risk is why leverage needs a margin of safety.",
        },
        {
            "id": "vacancy",
            "kind": "market",
            "title": "Market: Vacancy",
            "blurb": "Your rental is empty this month: rent $0 while the mortgage still due. Painful — and realistic in a game.",
            "choices": ["ok"],
            "tip": "Learn from the loss: buffers matter.",
        },
        {
            "id": "loan_offer",
            "kind": "loan_offer",
            "title": "Loan offer: $3,000 at 12%/year",
            "blurb": "You can borrow $3,000. Simple game payment: $50/month. Interest is a cost. Must be repaid. Education only.",
            "choices": ["borrow", "skip"],
            "loan": {
                "id": "personal-12",
                "name": "Personal loan 12%",
                "balance": 3000,
                "payment_mo": 50,
                "rate_pct": 12.0,
                "kind": "personal",
            },
            "cash_in": 3000,
            "tip": "Borrowing is not free money — interest and repayment are real.",
        },
    ]
    if has_rental:
        cards.append({
            "id": "borrow_against",
            "kind": "equity_loan",
            "title": "Event: Borrow against your rental (education)",
            "blurb": (
                "Owners with assets can sometimes borrow against them faster than earning the same "
                "cash after taxes at a job. In this game: take $5,000 against the rental at 8% "
                "(game payment $45/mo). Loan proceeds aren't modeled as taxable income here because "
                "they must be repaid. Risks: interest, repayment, and you can lose the asset if you "
                "cannot pay. Only sensible if cash flow still beats the loan cost. Not advice."
            ),
            "choices": ["borrow", "skip"],
            "loan": {
                "id": "equity-8",
                "name": "Borrow vs rental 8%",
                "balance": 5000,
                "payment_mo": 45,
                "rate_pct": 8.0,
                "kind": "equity",
            },
            "cash_in": 5000,
            "tip": "Earning vs borrowing: speed vs obligation. Education — not financial advice.",
        })
    # weight: avoid only doodads
    return random.choice(cards)


def _apply_monthly(state: dict) -> dict:
    cf = monthly_cash_flow(state)
    state["cash"] = int(state.get("cash") or 0) + cf
    state["log"] = (state.get("log") or [])[-30:]
    state["log"].append({
        "t": state.get("turn"),
        "event": "month_settle",
        "cash_flow": cf,
        "cash": state["cash"],
        "at": datetime.now(timezone.utc).isoformat(),
    })
    if passive_income(state) > int(state.get("living_expenses") or 0):
        state["won"] = True
    return state


def _apply_choice(state: dict, card: dict, choice: str) -> tuple[dict, str]:
    msg = ""
    kind = card.get("kind")
    if choice == "skip":
        return state, "Skipped. " + _tip()

    if kind == "doodad" and choice == "buy":
        cost = int(card["buy_cash"])
        if state["cash"] < cost:
            return state, f"Not enough cash (${state['cash']}). " + _tip()
        state["cash"] -= cost
        msg = f"Bought doodad for ${cost}. Cash flow direction: out. " + (card.get("tip") or _tip())
        return state, msg

    if kind == "small_deal":
        if card["id"] == "rental":
            if choice == "buy":
                cost = int(card["buy_cash"])
                if state["cash"] < cost:
                    return state, f"Need ${cost} cash to buy free-and-clear. Try Borrow or Skip."
                state["cash"] -= cost
                state["assets"].append(deepcopy(card["asset_cash"]))
                msg = f"Bought rental with cash. Passive ≈ ${card['asset_cash']['passive_mo']}/mo. " + (card.get("tip") or "")
                return state, msg
            if choice == "borrow":
                down = int(card["borrow_down"])
                if state["cash"] < down:
                    return state, f"Need ${down} down payment. " + _tip()
                state["cash"] -= down
                state["assets"].append(deepcopy(card["asset_borrow"]))
                state["liabilities"].append(deepcopy(card["loan"]))
                net = card["asset_borrow"]["passive_mo"]
                msg = (
                    f"Borrowed to buy rental. Down ${down}. Mortgage ${card['loan']['payment_mo']}/mo. "
                    f"Net passive if rented: ${net}/mo. " + (card.get("tip") or "")
                )
                return state, msg
        else:
            if choice == "buy":
                cost = int(card["buy_cash"])
                if state["cash"] < cost:
                    return state, f"Need ${cost}. " + _tip()
                state["cash"] -= cost
                asset = deepcopy(card["asset"])
                # unique id
                asset["id"] = f"{asset['id']}-{state['turn']}"
                state["assets"].append(asset)
                msg = f"Bought {asset['name']}. Passive +${asset['passive_mo']}/mo. " + (card.get("tip") or _tip())
                return state, msg

    if kind == "market":
        if card["id"] == "raise":
            state["salary"] = int(state["salary"]) + int(card.get("salary_delta") or 0)
            return state, f"Salary now ${state['salary']}/mo. " + (card.get("tip") or _tip())
        if card["id"] == "rates_up":
            for li in state.get("liabilities") or []:
                if li.get("kind") == "mortgage" and float(li.get("rate_pct") or 0) <= 6.5:
                    old = int(li["payment_mo"])
                    li["payment_mo"] = MORTGAGE_64K_9PCT
                    li["rate_pct"] = 9.0
                    li["name"] = "Rental mortgage 9%"
                    # recompute linked rental passive
                    for a in state.get("assets") or []:
                        if a.get("kind") == "rental" and a.get("rent_mo"):
                            upkeep = int(a.get("upkeep_mo") or 50)
                            a["passive_mo"] = int(a["rent_mo"]) - MORTGAGE_64K_9PCT - upkeep
                    return state, (
                        f"Rates up: payment {old} → {MORTGAGE_64K_9PCT}. "
                        f"New rental net passive may be negative. " + (card.get("tip") or "")
                    )
            return state, "No 6% mortgage to reprice. " + _tip()
        if card["id"] == "vacancy":
            hit = 0
            for a in state.get("assets") or []:
                if a.get("kind") == "rental":
                    # one-time cash hit: lose this month's rent portion already in passive;
                    # approximate: subtract rent from cash once
                    rent = int(a.get("rent_mo") or 0)
                    state["cash"] -= rent
                    hit += rent
            if hit:
                return state, f"Vacancy: lost ${hit} rent this month while debt still due. " + (card.get("tip") or "")
            return state, "No rental to go vacant. " + _tip()

    if kind in ("loan_offer", "equity_loan") and choice == "borrow":
        loan = deepcopy(card["loan"])
        loan["id"] = f"{loan['id']}-{state['turn']}"
        # avoid duplicate equity spam
        state["liabilities"].append(loan)
        state["cash"] += int(card.get("cash_in") or 0)
        return state, (
            f"Borrowed ${card.get('cash_in')}. Payment ${loan['payment_mo']}/mo. "
            "Must repay; interest is a cost; asset at risk if you cannot pay. "
            + (card.get("tip") or _tip())
        )

    return state, "Nothing happened. " + _tip()


def render_cash_flow_quest(profile: str = "Explorer") -> None:
    st.markdown('<div class="card-title">🌊 Cash Flow Quest</div>', unsafe_allow_html=True)
    st.caption(DISCLAIMER)
    st.markdown(
        "Ages **8+**. Each turn: see your income statement & balance sheet, draw a card, "
        "choose buy / skip / borrow. You win when **passive income > living expenses** "
        "(out of the rat race). Deals can lose money."
    )

    if "cfq_state" not in st.session_state or st.session_state.get("cfq_profile") != profile:
        st.session_state.cfq_state = load_state(profile)
        st.session_state.cfq_profile = profile
        st.session_state.cfq_card = None
        st.session_state.cfq_msg = ""

    state = st.session_state.cfq_state

    c1, c2, c3, c4 = st.columns(4)
    cf = monthly_cash_flow(state)
    color = "#00ff88" if cf >= 0 else "#ff6666"
    c1.metric("Cash", f"${state['cash']}")
    c2.metric("Monthly cash flow", f"${cf}")
    c3.metric("Passive income", f"${passive_income(state)}")
    c4.metric("Living expenses", f"${state['living_expenses']}")

    st.markdown(
        f'<div class="card" style="border-left:4px solid {color};">'
        f'<b style="color:{color};">{"Positive" if cf >= 0 else "Negative"} cash flow</b> '
        f'<span style="color:#8899bb;">= earned (${earned_income(state)}) + passive (${passive_income(state)}) '
        f'− living (${state["living_expenses"]}) − debt payments (${debt_payments(state)})</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    with st.expander("Income statement & balance sheet", expanded=True):
        _asset_txt = ", ".join(
            f"{a['name']} (+${a['passive_mo']}/mo)" for a in (state.get("assets") or [])
        ) or "none"
        _liab_txt = ", ".join(
            f"{l['name']} (${l['payment_mo']}/mo)" for l in (state.get("liabilities") or [])
        ) or "none"
        st.markdown(
            "**Income statement (monthly)**\n\n"
            f"- Earned income (job): ${earned_income(state)}\n"
            f"- Passive income: ${passive_income(state)}\n"
            f"- Living expenses: ${state['living_expenses']}\n"
            f"- Debt payments: ${debt_payments(state)}\n"
            f"- **Cash flow: ${cf}**\n\n"
            "**Balance sheet**\n\n"
            f"- Cash: ${state['cash']}\n"
            f"- Assets: {_asset_txt}\n"
            f"- Liabilities: {_liab_txt}\n"
            f"- **Net worth: ${net_worth(state)}**"
        )

    if state.get("won"):
        st.success(
            f"You did it on turn {state['turn']}! Passive income "
            f"(${passive_income(state)}) is greater than living expenses "
            f"(${state['living_expenses']}). Rat race meter: clear. " + _tip()
        )

    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("Draw card", type="primary", key="cfq_draw"):
            st.session_state.cfq_card = _draw_card(state)
            st.session_state.cfq_msg = ""
            st.rerun()
    with b2:
        if st.button("End month / settle cash flow", key="cfq_settle"):
            state = _apply_monthly(state)
            state["turn"] = int(state.get("turn") or 1) + 1
            st.session_state.cfq_state = state
            save_state(profile, state)
            st.session_state.cfq_card = None
            st.session_state.cfq_msg = f"Month settled. Cash flow was ${monthly_cash_flow({**state, 'cash': state['cash']})} (already applied)."
            st.rerun()
    with b3:
        if st.button("Reset game", key="cfq_reset"):
            st.session_state.cfq_state = default_state()
            save_state(profile, st.session_state.cfq_state)
            st.session_state.cfq_card = None
            st.session_state.cfq_msg = "Fresh start."
            st.rerun()

    card = st.session_state.get("cfq_card")
    if card:
        st.markdown(f"### Turn {state['turn']}: {card['title']}")
        st.write(card["blurb"])
        cols = st.columns(len(card.get("choices") or ["ok"]))
        for i, ch in enumerate(card.get("choices") or ["ok"]):
            label = {"buy": "Buy", "skip": "Skip", "borrow": "Borrow", "ok": "OK"}.get(ch, ch)
            with cols[i]:
                if st.button(label, key=f"cfq_ch_{card['id']}_{ch}"):
                    state, msg = _apply_choice(state, card, ch)
                    st.session_state.cfq_state = state
                    save_state(profile, state)
                    st.session_state.cfq_msg = msg
                    st.session_state.cfq_card = None
                    st.rerun()

    if st.session_state.get("cfq_msg"):
        st.info(st.session_state.cfq_msg)

    st.caption(f"Profile: {profile} · saved only on this computer · {DISCLAIMER}")


# Self-check math (import-time assert for unit sanity)
assert 700 - MORTGAGE_64K_6PCT - 50 == 266
assert 700 - MORTGAGE_64K_9PCT - 50 == 135

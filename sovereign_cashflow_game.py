"""
sovereign_cashflow_game.py — SOVEREIGN CASHFLOW
The Rich Dad Poor Dad Cash Flow Game — Updated for 2026
Bitcoin · AI Income · Sovereign Stack · Escape the Matrix

Mechanics:
  - Choose your Profession (sets salary, expenses, starting debt)
  - Each turn draw: Opportunity, Doodad, Market Event, or Payday
  - Buy assets that generate passive income
  - Goal: Passive Income >= Total Expenses = ESCAPE THE RAT RACE
  - Phase 2 Fast Track: Bitcoin treasury, AI businesses, legacy building
  - XP + sats flow back to family_profiles on escape
"""

import streamlit as st
import json, math, random, datetime, requests
from pathlib import Path

_SAVE_DIR = Path("/mnt/main/sovereign_life") if Path("/mnt/main").exists() \
            else Path("/home/aubie/.aubieeternal/sovereign_life")
_SAVE_DIR.mkdir(parents=True, exist_ok=True)

# ══════════════════════════════════════════════════════════════════════════════
# PROFESSIONS
# ══════════════════════════════════════════════════════════════════════════════
PROFESSIONS = {
    "teacher":    {"name":"Teacher",   "emoji":"📚","desc":"Steady income, low savings, high purpose",
                   "income":{"salary":3200},"expenses":{"taxes":640,"mortgage":700,"car_loan":200,"credit_card":90,"other":570},
                   "liabilities":{"mortgage":50000,"car_loan":8000,"credit_card":3000},"savings":400},
    "engineer":   {"name":"Engineer",  "emoji":"⚙️","desc":"Good salary, lifestyle creep, golden handcuffs",
                   "income":{"salary":7500},"expenses":{"taxes":2000,"mortgage":1800,"car_loan":600,"credit_card":250,"other":1350},
                   "liabilities":{"mortgage":200000,"car_loan":30000,"credit_card":8000},"savings":1500},
    "nurse":      {"name":"Nurse",     "emoji":"🏥","desc":"Stable income, moderate debt, service-oriented",
                   "income":{"salary":4800},"expenses":{"taxes":960,"mortgage":950,"car_loan":250,"credit_card":130,"other":810},
                   "liabilities":{"mortgage":80000,"car_loan":12000,"credit_card":5000},"savings":700},
    "salesperson":{"name":"Sales Pro", "emoji":"💼","desc":"Variable income, high lifestyle spending",
                   "income":{"salary":5500},"expenses":{"taxes":1100,"mortgage":1200,"car_loan":450,"credit_card":200,"other":1050},
                   "liabilities":{"mortgage":120000,"car_loan":20000,"credit_card":7000},"savings":500},
    "janitor":    {"name":"Janitor",   "emoji":"🧹","desc":"Low income, low debt — hardest mode, best story",
                   "income":{"salary":1600},"expenses":{"taxes":160,"rent":600,"car_loan":100,"credit_card":50,"other":390},
                   "liabilities":{"car_loan":3000,"credit_card":1500},"savings":300},
    "doctor":     {"name":"Doctor",    "emoji":"🩺","desc":"Highest income, highest debt — hardest to escape",
                   "income":{"salary":13000},"expenses":{"taxes":4200,"mortgage":2800,"car_loan":800,"student_loan":1200,"credit_card":300,"other":2000},
                   "liabilities":{"mortgage":400000,"car_loan":50000,"student_loan":150000,"credit_card":10000},"savings":1700},
}

# ══════════════════════════════════════════════════════════════════════════════
# OPPORTUNITY CARDS
# ══════════════════════════════════════════════════════════════════════════════
SMALL_DEALS = [
    {"id":"sd_btc_dca",   "name":"Bitcoin DCA Start",    "emoji":"₿",  "type":"bitcoin", "cost":1000,  "cf":0,   "val":1000,
     "desc":"Start buying $100/mo of Bitcoin. It's savings that can't be inflated away.",
     "lesson":"Bitcoin is savings technology, not a get-rich scheme. DCA is antifragile."},
    {"id":"sd_room",      "name":"Rent Out a Room",       "emoji":"🏠",  "type":"rental",  "cost":0,     "cf":500, "val":0,
     "desc":"List your spare room. Strangers pay you to sleep in your house.",
     "lesson":"Your house can work for you. Every underused asset is a missed cash flow."},
    {"id":"sd_dividend",  "name":"Dividend ETF",          "emoji":"📈",  "type":"stocks",  "cost":5000,  "cf":50,  "val":5000,
     "desc":"$5,000 into a low-cost dividend index fund. Boring, reliable, compounding.",
     "lesson":"Boring is profitable. Dividend investing rewards patience, not excitement."},
    {"id":"sd_ai_tool",   "name":"Build an AI Tool",      "emoji":"🤖",  "type":"business","cost":200,   "cf":200, "val":5000,
     "desc":"Spend a weekend building a simple AI tool. $9/mo x 50 subscribers = $450/mo.",
     "lesson":"AI collapses the cost of building software. One person ships what took a team in 2020."},
    {"id":"sd_course",    "name":"Create Online Course",  "emoji":"🎓",  "type":"business","cost":300,   "cf":150, "val":3000,
     "desc":"Turn your skill into a $197 course. Sell it while you sleep.",
     "lesson":"Knowledge is the only asset you can sell infinitely without using it up."},
    {"id":"sd_parking",   "name":"Buy a Parking Space",   "emoji":"🅿️", "type":"rental",  "cost":8000,  "cf":200, "val":10000,
     "desc":"A parking space in a busy city rents for $150-300/month. Zero maintenance.",
     "lesson":"The best investments are boring ones nobody else wants to talk about."},
    {"id":"sd_laundromat","name":"Laundromat Machines",   "emoji":"🧺",  "type":"business","cost":6000,  "cf":300, "val":8000,
     "desc":"2 laundromat machines in a shared space. People wash clothes forever.",
     "lesson":"Cash machines: assets that generate money with minimal human intervention."},
    {"id":"sd_newsletter","name":"Paid Newsletter",       "emoji":"📧",  "type":"business","cost":100,   "cf":100, "val":2000,
     "desc":"Write weekly about something you know. 100 subscribers x $10/mo.",
     "lesson":"A dedicated niche audience is worth more than a mass one."},
    {"id":"sd_nostr",     "name":"Nostr Content Creator", "emoji":"⚡",  "type":"business","cost":0,     "cf":80,  "val":1500,
     "desc":"Build a Nostr audience. Receive Bitcoin zaps. No platform can ban you.",
     "lesson":"Sovereign platforms mean you own your audience. Zaps are uncensorable income."},
]

BIG_DEALS = [
    {"id":"bd_rental",    "name":"Rental Property",         "emoji":"🏘️","type":"rental",  "cost":25000, "cf":800, "val":120000,
     "desc":"3-bed house in a growing market. Positive cash flow from day 1.",
     "lesson":"Real estate: control a large asset with a small down payment. Leverage done right."},
    {"id":"bd_node",      "name":"Bitcoin Lightning Node",  "emoji":"⚡", "type":"bitcoin", "cost":5000,  "cf":300, "val":15000,
     "desc":"Run a routing node. Earn sats routing payments on Lightning 24/7.",
     "lesson":"Infrastructure ownership. You become part of the network that can't be shut down."},
    {"id":"bd_saas",      "name":"Buy a Micro-SaaS",        "emoji":"💻", "type":"business","cost":36000, "cf":2000,"val":50000,
     "desc":"Acquire a software business doing $2k/mo revenue for 18x multiple.",
     "lesson":"Buying cash-flowing businesses beats building from scratch when you have capital."},
    {"id":"bd_carwash",   "name":"Automated Car Wash",      "emoji":"🚿", "type":"business","cost":40000, "cf":2500,"val":100000,
     "desc":"Buy into an automated car wash. Runs 24/7 with one part-time employee.",
     "lesson":"Automation is the new employee. Machines don't call in sick."},
    {"id":"bd_land",      "name":"Raw Land",                "emoji":"🌾", "type":"rental",  "cost":15000, "cf":400, "val":40000,
     "desc":"Buy cheap rural land. Lease to farmers, hunters, solar companies.",
     "lesson":"Land is the original sovereign asset. They stopped making more of it."},
    {"id":"bd_ai_agency", "name":"AI Consulting Agency",    "emoji":"🧠", "type":"business","cost":2000,  "cf":5000,"val":80000,
     "desc":"3 clients at $5k/mo. AI tools let one person do the work of a team.",
     "lesson":"AI dramatically lowers the cost of expertise. The solo operator is now a category."},
    {"id":"bd_btc_treasury","name":"Bitcoin Treasury",      "emoji":"₿",  "type":"bitcoin", "cost":20000, "cf":0,   "val":20000,
     "desc":"Move 20% of savings into Bitcoin. Sovereign savings protection.",
     "lesson":"Hard money can't be printed away. Bitcoin is financial self-custody."},
    {"id":"bd_multifam",  "name":"Multi-Family Building",   "emoji":"🏢", "type":"rental",  "cost":50000, "cf":1800,"val":300000,
     "desc":"4-unit building. Live in one, rent three. Tenants pay your mortgage.",
     "lesson":"House hacking: someone else pays your housing. Most powerful first real estate move."},
]

DOODADS = [
    {"name":"New iPhone 17",             "cost":1400,"monthly":0,    "lesson":"A phone is a tool. The newest model is a doodad wearing a utility costume."},
    {"name":"7 Streaming Subscriptions", "cost":0,   "monthly":180,  "lesson":"$15 feels trivial. $180/month is $2,160/year of lost cash flow."},
    {"name":"Weekend Vegas Trip",        "cost":2200,"monthly":0,    "lesson":"Experiences have value. But financing lifestyle with savings delays freedom."},
    {"name":"New Car Upgrade",           "cost":0,   "monthly":650,  "lesson":"A new car loses 20% value immediately. Depreciating liability."},
    {"name":"Impulse Amazon Haul",       "cost":800, "monthly":0,    "lesson":"Every dollar on doodads is a dollar not building passive income."},
    {"name":"Designer Clothes",          "cost":1800,"monthly":0,    "lesson":"Status signaling is expensive. Wealthy people wear plain clothes."},
    {"name":"DoorDash + Restaurant Habit","cost":0,  "monthly":400,  "lesson":"$400/mo = $4,800/yr = a rental property down payment."},
    {"name":"Boat Purchase",             "cost":12000,"monthly":200, "lesson":"Two best days of owning a boat: buying it and selling it."},
    {"name":"Altcoin Gamble",            "cost":3000,"monthly":0,    "lesson":"Speculation is not investing. Know the difference."},
    {"name":"Home Renovation Creep",     "cost":8000,"monthly":0,    "lesson":"Renovations rarely add more value than they cost."},
]

MARKET_EVENTS = [
    {"name":"₿ Bitcoin Halving",     "effect":"btc_2x",       "desc":"Bitcoin supply halved. BTC holdings double in value.",           "lesson":"Predictable scarcity. Bitcoin's supply is coded — no committee decides."},
    {"name":"🏠 Rental Market Surge","effect":"rent_up",      "desc":"Rental prices up 20%. Your rental cash flow increases.",         "lesson":"Real assets appreciate when money is printed."},
    {"name":"🖨️ Fed Prints Money",   "effect":"inflation",    "desc":"Inflation at 9%. Cash savings shrink in real terms.",            "lesson":"Cash is a slow tax. Inflation is the hidden fee of fiat money."},
    {"name":"🤖 AI Tools Cheaper",   "effect":"ai_boost",     "desc":"Your AI business income +50% — same work, better tools.",        "lesson":"Technology deflation benefits those who use it."},
    {"name":"📉 Recession",          "effect":"recession",    "desc":"Markets down 30%. Rental income holds. Cash for opportunities.", "lesson":"Antifragile portfolios survive recessions. Downturns are buying opportunities."},
    {"name":"💼 Tech Layoffs",       "effect":"job_warning",  "desc":"Layoffs sweep your industry. A warning: passive income matters.", "lesson":"No job is safe forever. Passive income is the only true job security."},
    {"name":"⚡ Lightning Goes Mainstream","effect":"lightning","desc":"Lightning payments mainstream. Node operators earn more.",       "lesson":"Infrastructure ownership wins in every technology wave."},
    {"name":"📋 New Tax Law",        "effect":"tax_hit",      "desc":"New bracket hits salary. Take-home drops $300/mo.",              "lesson":"Employees are taxed first. Business owners and investors last."},
    {"name":"🏘️ Housing Boom",      "effect":"property_up",  "desc":"Real estate appreciates 25% in value.",                         "lesson":"Leveraged real estate in a housing boom multiplies returns."},
    {"name":"💰 Payday",             "effect":"payday",       "desc":"Month ends. Collect your cash flow.",                           "lesson":"Every month your assets work, you don't have to."},
]

# ══════════════════════════════════════════════════════════════════════════════
# SAVE / LOAD / HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def _sp(fid): return _SAVE_DIR / f"{fid}_cashflow.json"
def load_game(fid="default"):
    p = _sp(fid)
    if p.exists():
        try: return json.loads(p.read_text())
        except: pass
    return None
def save_game(s, fid="default"):
    s["last_updated"] = datetime.datetime.now().isoformat()
    _sp(fid).write_text(json.dumps(s, indent=2))
def new_game(pid, fid="default"):
    p = PROFESSIONS[pid]
    return {"family_id":fid,"profession":pid,"turn":1,"phase":"rat_race",
            "income":dict(p["income"]),"expenses":dict(p["expenses"]),
            "assets":{},"liabilities":dict(p["liabilities"]),
            "savings":p["savings"],"passive_income":0,
            "total_xp":0,"sats_earned":0,"dream":"",
            "log":[],"escaped":False,"fast_track":False}
def passive(s): return sum(v for k,v in s["income"].items() if k!="salary")
def expenses(s): return sum(s["expenses"].values())
def cf(s): return sum(s["income"].values()) - expenses(s)
def assets_val(s): return sum(a.get("val",a.get("value",0)) for a in s["assets"].values())
def liab_val(s): return sum(s["liabilities"].values())
def net_worth(s): return assets_val(s) + s["savings"] - liab_val(s)
def escaped(s): return passive(s) >= expenses(s) and passive(s) > 0
def _log(s, msg): s["log"].insert(0, f"T{s['turn']}: {msg}"); s["log"] = s["log"][:25]
def _fmt(n):
    if abs(n)>=1_000_000: return f"${n/1_000_000:.1f}M"
    if abs(n)>=1_000: return f"${n:,.0f}"
    return f"${n:.0f}"

# ══════════════════════════════════════════════════════════════════════════════
# BOARD — the circular "Rat Race" track, like the real Cashflow board game.
# Landing on a space determines what you draw, instead of the old manual
# "pick a card type" radio button. 24 spaces, weighted toward Opportunity
# (the real game's focus) with Doodad/Market/Payday spaced around it.
# ══════════════════════════════════════════════════════════════════════════════
BOARD_SPACES = (["opp","opp","doodad","market","opp","payday"] * 4)
SPACE_META = {
    "opp":    {"emoji":"🎯", "color":"#00ff88", "label":"Opportunity"},
    "doodad": {"emoji":"🛍️", "color":"#ff4444", "label":"Doodad"},
    "market": {"emoji":"🌍", "color":"#00cfff", "label":"Market Event"},
    "payday": {"emoji":"💵", "color":"#f7931a", "label":"Payday"},
}

def _render_board(players):
    """players: list of (label, emoji, color, board_pos) tuples. Pure HTML/CSS -
    positions computed with trig around a circle, no external chart/game lib
    needed."""
    n = len(BOARD_SPACES)
    size, radius = 320, 132
    cx = cy = size / 2
    parts = [f'<div style="position:relative;width:{size}px;height:{size}px;'
             f'margin:10px auto;background:radial-gradient(circle,rgba(160,32,240,.06),transparent 70%);'
             f'border-radius:50%;border:1px dashed rgba(255,255,255,.08);">']

    for i, sp in enumerate(BOARD_SPACES):
        ang = (i / n) * 2 * math.pi - math.pi / 2
        x, y = cx + radius * math.cos(ang), cy + radius * math.sin(ang)
        meta = SPACE_META[sp]
        parts.append(
            f'<div title="{meta["label"]}" style="position:absolute;left:{x-13}px;top:{y-13}px;'
            f'width:26px;height:26px;border-radius:50%;background:{meta["color"]}22;'
            f'border:2px solid {meta["color"]};display:flex;align-items:center;'
            f'justify-content:center;font-size:12px;">{meta["emoji"]}</div>'
        )

    at_pos = {}
    for p in players:
        at_pos.setdefault(p[3] % n, []).append(p)
    for pos, plist in at_pos.items():
        ang = (pos / n) * 2 * math.pi - math.pi / 2
        bx, by = cx + radius * math.cos(ang), cy + radius * math.sin(ang)
        for j, (label, emoji, color, _pos) in enumerate(plist):
            ox = (j - (len(plist) - 1) / 2) * 15
            parts.append(
                f'<div title="{label}" style="position:absolute;left:{bx-9+ox}px;top:{by-9-16}px;'
                f'width:18px;height:18px;border-radius:50%;background:{color};'
                f'border:2px solid white;display:flex;align-items:center;justify-content:center;'
                f'font-size:10px;z-index:5;box-shadow:0 0 4px rgba(0,0,0,.5);">{emoji}</div>'
            )

    parts.append(
        f'<div style="position:absolute;left:{cx-50}px;top:{cy-22}px;width:100px;'
        f'text-align:center;font-family:Orbitron,monospace;font-size:.62rem;'
        f'color:#445566;letter-spacing:.1em;">RAT<br>RACE</div>'
    )
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)

    legend = " &nbsp; ".join(
        f'<span style="color:{m["color"]};">{m["emoji"]} {m["label"]}</span>'
        for m in SPACE_META.values()
    )
    st.markdown(f'<div style="text-align:center;font-size:.68rem;color:#556677;margin-top:-4px;">{legend}</div>',
                unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# AI OPPONENTS — 2-3 computer-controlled players race around the same board.
# Decisions are fast built-in heuristics (buy if affordable, resist doodads
# more often than not) so a turn never stalls waiting on a model; a short
# in-character line from the local Ollama model is layered on top purely for
# flavor and always has a plain-text fallback if the model call fails or
# Ollama isn't running.
# ══════════════════════════════════════════════════════════════════════════════
AI_NAMES  = ["Ada", "Byte", "Coin", "Delta", "Echo", "Frost"]
AI_COLORS = ["#00cfff", "#a020f0", "#ff6b35", "#00ff88"]

def _new_ai_player(idx):
    pid = random.choice(list(PROFESSIONS.keys()))
    ai = new_game(pid, fid=f"__ai_{idx}")
    ai["name"]  = AI_NAMES[idx % len(AI_NAMES)]
    ai["emoji"] = PROFESSIONS[pid]["emoji"]
    ai["color"] = AI_COLORS[idx % len(AI_COLORS)]
    ai["board_pos"] = 0
    return ai

def _ollama_narrate(fallback: str, prompt: str) -> str:
    try:
        r = requests.post(
            "http://localhost:11434/v1/chat/completions",
            json={"model": "qwen2.5:7b",
                  "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": 50, "temperature": 0.85},
            timeout=15,
        )
        if r.status_code == 200:
            text = r.json()["choices"][0]["message"]["content"].strip()
            if text:
                return text
    except Exception:
        pass
    return fallback

def _ai_take_turn(ai: dict) -> str:
    """Rolls, moves, lands, decides, and resolves one AI opponent's turn.
    Reuses the same _do_buy/_apply_event mutators the human player's turn
    uses, so an AI's assets/income/expenses evolve under identical rules -
    just decided by a simple heuristic instead of a person clicking Buy/Pass.
    Returns a one-line narration for the log."""
    prof_name = PROFESSIONS[ai["profession"]]["name"]

    # Before rolling, a "smart" AI pays off debt it can afford ~70% of the
    # time (not every time, so it still plays like a character rather than
    # a perfect optimizer) - the cheapest liability first, same real lever
    # a human player has via the Pay Down Debt tab.
    if ai["liabilities"] and random.random() < 0.7:
        key, amount = min(ai["liabilities"].items(), key=lambda kv: kv[1])
        if ai["savings"] >= amount:
            monthly = ai["expenses"].get(key, 0)
            paid = _payoff_debt(ai, key)
            label = _LIABILITY_LABELS.get(key, key.replace("_"," ").title())
            fallback = f"{ai['name']} the {prof_name} pays off the {label} ({_fmt(paid)}), freeing up {_fmt(monthly)}/mo."
            return _ollama_narrate(fallback,
                f"In one short, punchy sentence (under 20 words), narrate {ai['name']}, a {prof_name}, "
                f"paying off their {label.split(' ',1)[-1]} debt in full in a cashflow board game.")

    roll = random.randint(1, 6)
    ai["board_pos"] = (ai.get("board_pos", 0) + roll) % len(BOARD_SPACES)
    space = BOARD_SPACES[ai["board_pos"]]

    if space == "payday":
        c = cf(ai); ai["savings"] += c; ai["turn"] += 1
        fallback = f"{ai['name']} the {prof_name} collects payday: +{_fmt(c)}."
        return _ollama_narrate(fallback,
            f"In one short, punchy sentence (under 20 words), narrate a board-game character "
            f"named {ai['name']}, a {prof_name}, collecting a payday of {_fmt(c)} in a cashflow game.")

    if space == "opp":
        pool = SMALL_DEALS if ai["savings"] < 5000 else (SMALL_DEALS + BIG_DEALS)
        owned = {a["name"] for a in ai["assets"].values()}
        pool = [d for d in pool if d["name"] not in owned] or SMALL_DEALS
        card = random.choice(pool)
        if ai["savings"] >= card["cost"]:
            _do_buy(ai, card, ai["family_id"])
            fallback = f"{ai['name']} the {prof_name} lands on Opportunity and buys {card['name']} for {_fmt(card['cost'])}."
            return _ollama_narrate(fallback,
                f"In one short, punchy sentence (under 20 words), narrate {ai['name']}, a {prof_name}, "
                f"buying '{card['name']}' ({card['desc']}) in a cashflow board game.")
        ai["turn"] += 1
        fallback = f"{ai['name']} the {prof_name} lands on Opportunity but can't afford {card['name']} - passes."
        return _ollama_narrate(fallback,
            f"In one short sentence (under 20 words), narrate {ai['name']}, a {prof_name}, "
            f"wanting but not being able to afford '{card['name']}' in a cashflow board game.")

    if space == "doodad":
        card = random.choice(DOODADS)
        if random.random() < 0.45:  # AI gives in to temptation less than half the time
            if card["cost"] > 0: ai["savings"] = max(0, ai["savings"] - card["cost"])
            if card["monthly"] > 0: ai["expenses"]["doodads"] = ai["expenses"].get("doodads", 0) + card["monthly"]
            ai["turn"] += 1
            fallback = f"{ai['name']} the {prof_name} gives in and buys {card['name']}."
            return _ollama_narrate(fallback,
                f"In one short sentence (under 20 words), narrate {ai['name']}, a {prof_name}, "
                f"giving in to temptation and buying '{card['name']}' in a cashflow board game.")
        ai["savings"] += 50; ai["turn"] += 1
        fallback = f"{ai['name']} the {prof_name} resists {card['name']} and saves instead."
        return _ollama_narrate(fallback,
            f"In one short sentence (under 20 words), narrate {ai['name']}, a {prof_name}, "
            f"resisting the temptation to buy '{card['name']}' in a cashflow board game.")

    # market
    card = random.choice(MARKET_EVENTS)
    _apply_event(ai, card); ai["turn"] += 1
    fallback = f"{ai['name']} the {prof_name} hits a Market Event: {card['name']}."
    return _ollama_narrate(fallback,
        f"In one short sentence (under 20 words), narrate {ai['name']}, a {prof_name}, "
        f"experiencing the market event '{card['name']}' ({card['desc']}) in a cashflow board game.")

def _run_ai_turns(s: dict):
    """Called once after the human's turn resolves. Every AI opponent takes
    one turn and its narration lands in the shared log (see the 📜 Log tab)
    so it reads like a real multiplayer session, not a silent background
    process."""
    for ai in s.get("ai_players", []):
        line = _ai_take_turn(ai)
        _log(s, f"🤖 {line}")
        if escaped(ai) and not ai.get("_announced_escape"):
            ai["_announced_escape"] = True
            _log(s, f"🏁 {ai['name']} the {PROFESSIONS[ai['profession']]['name']} escaped the rat race!")

# ══════════════════════════════════════════════════════════════════════════════
# CSS
# ══════════════════════════════════════════════════════════════════════════════
_CSS = """<style>
.cfh{font-family:'Orbitron',monospace;font-size:1.5rem;font-weight:900;
    background:linear-gradient(90deg,#f7931a,#ff6b35,#a020f0);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:.08em;}
.cfc{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);
    border-radius:10px;padding:12px 16px;margin:6px 0;}
.cfl{background:rgba(160,32,240,.08);border-left:3px solid #a020f0;
    border-radius:6px;padding:8px 14px;margin-top:8px;font-size:.78rem;color:#9966cc;font-style:italic;}
.cflog{font-family:'Share Tech Mono',monospace;font-size:.7rem;color:#445566;
    padding:3px 0;border-bottom:1px solid rgba(255,255,255,.04);}
</style>"""

# ══════════════════════════════════════════════════════════════════════════════
# MAIN RENDER
# ══════════════════════════════════════════════════════════════════════════════
def render_sovereign_life(family_id="default"):
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown('<div class="cfh">💰 SOVEREIGN CASHFLOW</div>', unsafe_allow_html=True)
    st.markdown('<div style="color:#445566;font-family:monospace;font-size:.7rem;letter-spacing:.15em;margin-bottom:12px;">ESCAPE THE RAT RACE · BUILD PASSIVE INCOME · ACHIEVE FREEDOM · 2026 EDITION</div>', unsafe_allow_html=True)

    game = load_game(family_id)
    if game is None:
        _setup(family_id); return
    if game.get("escaped") and not game.get("fast_track"):
        _escape_screen(game, family_id); return
    if game.get("fast_track"):
        _fast_track(game, family_id); return
    _main(game, family_id)

# ══════════════════════════════════════════════════════════════════════════════
def _setup(family_id):
    st.markdown("### 🎯 Choose Your Profession")
    st.caption("Your starting salary, expenses, and debt are determined by your profession. "
               "The goal is always the same: make Passive Income ≥ Total Expenses.")
    dream = st.text_input("🌟 What's your dream? (What are you playing for?)",
                          placeholder="Own a homestead, travel freely, homeschool kids, Bitcoin full-node life...")
    n_ai = st.radio("🤖 AI opponents racing the board with you:", [2, 3], horizontal=True, index=0)
    st.markdown("---")
    cols = st.columns(3)
    for i,(pid,p) in enumerate(PROFESSIONS.items()):
        ti = sum(p["income"].values()); te = sum(p["expenses"].values()); tcf = ti-te
        with cols[i%3]:
            st.markdown(
                f'<div class="cfc" style="text-align:center;">' +
                f'<div style="font-size:2rem;">{p["emoji"]}</div>' +
                f'<div style="font-family:Orbitron,monospace;font-size:.82rem;color:#c8d8ff;">{p["name"]}</div>' +
                f'<div style="color:#445566;font-size:.7rem;margin:4px 0;">{p["desc"]}</div>' +
                f'<div style="font-size:.75rem;margin-top:6px;">' +
                f'<span style="color:#00ff88;">💵 {_fmt(ti)}/mo</span>  ' +
                f'<span style="color:#ff4444;">💸 {_fmt(te)}/mo</span></div>' +
                f'<div style="color:{"#00ff88" if tcf>0 else "#ff4444"};font-size:.78rem;">CF: {_fmt(tcf)}/mo</div>' +
                f'</div>', unsafe_allow_html=True
            )
            if st.button(f"Play as {p['name']}", key=f"pick_{pid}", use_container_width=True):
                if not dream:
                    st.warning("Enter your dream first!"); st.stop()
                s = new_game(pid, family_id); s["dream"] = dream
                s["board_pos"] = 0
                s["ai_players"] = [_new_ai_player(i) for i in range(n_ai)]
                _log(s, f"Started as {p['name']}. Dream: {dream}. {n_ai} AI opponents joined the board.")
                save_game(s, family_id); st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
def _main(s, fid):
    # Lazily upgrade a save from before the board/AI-opponents feature -
    # rather than forcing a new game, just give it a board position and a
    # default pair of AI opponents the next time it's opened.
    if "board_pos" not in s: s["board_pos"] = 0
    if "ai_players" not in s: s["ai_players"] = [_new_ai_player(i) for i in range(2)]

    prof = PROFESSIONS[s["profession"]]
    pv   = passive(s); ev = expenses(s); cfv = cf(s)
    pct  = min(100, int(pv/ev*100)) if ev>0 else 0
    bar_c= "#00ff88" if pct>=80 else "#f7931a" if pct>=40 else "#ff4444"

    # Header
    st.markdown(
        f'<div class="cfc"><div style="display:flex;justify-content:space-between;">' +
        f'<span style="font-family:Orbitron,monospace;color:#c8d8ff;">{prof["emoji"]} {prof["name"]} — Turn {s["turn"]}</span>' +
        f'<span style="color:#445566;font-size:.75rem;">🟡 RAT RACE</span></div>' +
        f'<div style="color:#8899bb;font-size:.75rem;">Dream: {s.get("dream","")}</div></div>',
        unsafe_allow_html=True
    )
    # Progress bar
    st.markdown(
        f'<div style="margin:8px 0 4px;">' +
        f'<div style="display:flex;justify-content:space-between;font-size:.7rem;color:#445566;">' +
        f'<span>🔓 Escape: Passive {_fmt(pv)}/mo vs Expenses {_fmt(ev)}/mo</span>' +
        f'<span style="color:{bar_c};">{pct}%</span></div>' +
        f'<div style="background:#111;border-radius:4px;height:7px;margin-top:3px;">' +
        f'<div style="background:{bar_c};width:{pct}%;height:7px;border-radius:4px;"></div></div></div>',
        unsafe_allow_html=True
    )
    # Metrics
    m1,m2,m3,m4,m5 = st.columns(5)
    salary = s["income"].get("salary",0)
    for col,(icon,val,lbl,c) in zip([m1,m2,m3,m4,m5],[
        ("💵",_fmt(salary),"SALARY","#c8d8ff"),
        ("📈",_fmt(pv),"PASSIVE","#00ff88"),
        ("💸",_fmt(ev),"EXPENSES","#ff4444"),
        ("💰",_fmt(s["savings"]),"SAVINGS","#f7931a"),
        ("🏦",_fmt(assets_val(s)),"ASSETS","#a020f0"),
    ]):
        with col:
            st.markdown(
                f'<div style="text-align:center;padding:8px 4px;">' +
                f'<div style="font-family:Orbitron,monospace;font-size:1.1rem;color:{c};">{icon} {val}</div>' +
                f'<div style="font-size:.62rem;color:#445566;letter-spacing:.1em;">{lbl}</div></div>',
                unsafe_allow_html=True
            )
    st.markdown("---")

    # ── Board + leaderboard ───────────────────────────────────────────────────
    board_players = [(prof["name"], prof["emoji"], "#f7931a", s["board_pos"])]
    for ai in s["ai_players"]:
        board_players.append((ai["name"], ai["emoji"], ai["color"], ai.get("board_pos", 0)))
    _render_board(board_players)

    lb_cols = st.columns(len(s["ai_players"]) + 1)
    with lb_cols[0]:
        st.markdown(
            f'<div style="text-align:center;"><span style="color:#f7931a;">{prof["emoji"]} You</span><br>'
            f'<span style="font-size:.7rem;color:{"#00ff88" if escaped(s) else "#556677"};">'
            f'{"🏁 ESCAPED" if escaped(s) else f"{pct}% to escape"}</span></div>',
            unsafe_allow_html=True)
    for col, ai in zip(lb_cols[1:], s["ai_players"]):
        with col:
            ai_pv, ai_ev = passive(ai), expenses(ai)
            ai_pct = min(100, int(ai_pv/ai_ev*100)) if ai_ev>0 else 0
            ai_escaped = escaped(ai)
            st.markdown(
                f'<div style="text-align:center;"><span style="color:{ai["color"]};">{ai["emoji"]} {ai["name"]}</span><br>'
                f'<span style="font-size:.7rem;color:{"#00ff88" if ai_escaped else "#556677"};">'
                f'{"🏁 ESCAPED" if ai_escaped else f"{ai_pct}% to escape"}</span></div>',
                unsafe_allow_html=True)
    st.markdown("---")

    t1,t2,t3,t4,t5 = st.tabs(["🎲 Take Turn","📊 Balance Sheet","🏪 Marketplace","💳 Pay Down Debt","📜 Log"])
    with t1: _turn(s, fid, pv, ev)
    with t2: _sheet(s, pv, ev, cfv)
    with t3: _market(s, fid)
    with t4: _debt(s, fid)
    with t5:
        for e in s.get("log",[]): st.markdown(f'<div class="cflog">{e}</div>', unsafe_allow_html=True)

    if escaped(s):
        s["escaped"]=True
        _log(s, f"🎉 ESCAPED! Passive {_fmt(pv)} >= Expenses {_fmt(ev)}")
        save_game(s, fid)
        try:
            from family_profiles import award_cross_tool_reward, award_badge
            award_cross_tool_reward(fid,"sovereign_life","escape_rat_race",xp=500,badge="💰 Rat Race Escapee")
        except: pass
        st.balloons(); st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
def _turn(s, fid, pv, ev):
    st.markdown("### 🎲 Your Turn")
    st.caption("Roll to move your token around the board. The space you land on decides what you draw.")

    if "card" not in st.session_state:
        if st.button("🎲 Roll Dice", key="roll", use_container_width=True, type="primary"):
            roll = random.randint(1, 6)
            s["board_pos"] = (s["board_pos"] + roll) % len(BOARD_SPACES)
            space = BOARD_SPACES[s["board_pos"]]
            st.toast(f"🎲 Rolled a {roll} — landed on {SPACE_META[space]['label']}", icon=SPACE_META[space]["emoji"])
            if space == "opp":
                pool = SMALL_DEALS if s["savings"]<5000 else (SMALL_DEALS+BIG_DEALS)
                owned = {a["name"] for a in s["assets"].values()}
                pool  = [d for d in pool if d["name"] not in owned] or SMALL_DEALS
                st.session_state["card"] = ("opp", random.choice(pool))
            elif space == "doodad":
                st.session_state["card"] = ("doodad", random.choice(DOODADS))
            elif space == "market":
                st.session_state["card"] = ("market", random.choice(MARKET_EVENTS))
            else:
                _do_payday(s, fid)
            st.rerun()

    if "card" not in st.session_state: return
    ck, card = st.session_state["card"]

    if ck=="opp":
        afford = s["savings"] >= card["cost"]
        bc = "#00ff88" if afford else "#445566"
        st.markdown(
            f'<div class="cfc" style="border-left:3px solid {bc};">' +
            f'<div style="font-size:1.3rem;">{card["emoji"]} <strong style="color:#c8d8ff;">{card["name"]}</strong></div>' +
            f'<div style="color:#8899bb;font-size:.82rem;margin:6px 0;">{card["desc"]}</div>' +
            f'<div style="font-size:.78rem;display:flex;gap:16px;">' +
            f'<span style="color:#ff4444;">Cost: {_fmt(card["cost"])}</span>' +
            f'<span style="color:#00ff88;">CF: +{_fmt(card["cf"])}/mo</span>' +
            f'<span style="color:#a020f0;">Value: {_fmt(card["val"])}</span></div></div>',
            unsafe_allow_html=True
        )
        st.markdown(f'<div class="cfl">💡 {card["lesson"]}</div>', unsafe_allow_html=True)
        c1,c2 = st.columns(2)
        with c1:
            if afford:
                if st.button(f"✅ Buy {_fmt(card['cost'])}", key="buy_opp", use_container_width=True, type="primary"):
                    _do_buy(s, card, fid); del st.session_state["card"]
                    _run_ai_turns(s); save_game(s,fid); st.rerun()
            else:
                st.button(f"❌ Need {_fmt(card['cost']-s['savings'])} more", disabled=True, use_container_width=True)
        with c2:
            if st.button("⏭️ Pass", key="pass_opp", use_container_width=True):
                s["turn"]+=1; _log(s,f"Passed {card['name']}"); del st.session_state["card"]
                _run_ai_turns(s); save_game(s,fid); st.rerun()

    elif ck=="doodad":
        st.markdown(
            f'<div class="cfc" style="border-left:3px solid #ff4444;">' +
            f'<div style="color:#ff6666;font-size:1.1rem;"><strong>🛍️ {card["name"]}</strong></div>' +
            f'<div style="color:#8899bb;font-size:.82rem;margin:6px 0;">You want it. Everyone around you has one.</div>' +
            f'<div style="font-size:.78rem;">' +
            (f'<span style="color:#ff4444;">One-time: -{_fmt(card["cost"])}</span>  ' if card["cost"] else "") +
            (f'<span style="color:#ff4444;">Monthly: -{_fmt(card["monthly"])}/mo</span>' if card["monthly"] else "") +
            f'</div></div>', unsafe_allow_html=True
        )
        st.markdown(f'<div class="cfl">💡 {card["lesson"]}</div>', unsafe_allow_html=True)
        c1,c2 = st.columns(2)
        with c1:
            if st.button("😬 Buy it anyway", key="buy_doodad", use_container_width=True):
                if card["cost"]>0: s["savings"] = max(0, s["savings"]-card["cost"])
                if card["monthly"]>0: s["expenses"]["doodads"] = s["expenses"].get("doodads",0)+card["monthly"]
                s["turn"]+=1; _log(s,f"🛍️ Bought {card['name']}"); del st.session_state["card"]
                _run_ai_turns(s); save_game(s,fid); st.rerun()
        with c2:
            if st.button("💪 Resist! Save it", key="res_doodad", use_container_width=True, type="primary"):
                s["savings"]+=50; s["total_xp"]=s.get("total_xp",0)+10
                s["turn"]+=1; _log(s,f"💪 Resisted {card['name']}. +$50 +10XP"); del st.session_state["card"]
                _run_ai_turns(s); save_game(s,fid); st.rerun()

    elif ck=="market":
        st.markdown(
            f'<div class="cfc" style="border-left:3px solid #00cfff;">' +
            f'<div style="color:#c8d8ff;font-size:1.1rem;"><strong>{card["name"]}</strong></div>' +
            f'<div style="color:#8899bb;font-size:.82rem;margin:6px 0;">{card["desc"]}</div></div>',
            unsafe_allow_html=True
        )
        st.markdown(f'<div class="cfl">💡 {card["lesson"]}</div>', unsafe_allow_html=True)
        if st.button("📌 Apply Event", key="apply_mkt", use_container_width=True, type="primary"):
            _apply_event(s, card); s["turn"]+=1; del st.session_state["card"]
            _run_ai_turns(s); save_game(s,fid); st.rerun()

def _do_payday(s, fid):
    c = cf(s); s["savings"]+=c; s["turn"]+=1
    _log(s, f"💵 Payday +{_fmt(c)}. Savings: {_fmt(s['savings'])}")
    _run_ai_turns(s)
    save_game(s,fid); st.success(f"💵 Payday! +{_fmt(c)}"); st.rerun()

_LIABILITY_LABELS = {
    "mortgage": "🏠 Mortgage", "car_loan": "🚗 Car Loan",
    "credit_card": "💳 Credit Card", "student_loan": "🎓 Student Loan",
}

def _payoff_debt(s: dict, key: str) -> int:
    """Pays a liability off IN FULL from savings - matches the real Cashflow
    board game's loan-payoff mechanic (no partial paydown) and keeps the
    lesson simple: cost to lock in was always the full payoff amount. Every
    profession's liability keys are a subset of its expense keys sharing the
    same name (e.g. "car_loan" is both a liability and the monthly expense
    line for it), so paying it off also removes the matching monthly
    expense - the actual reward, since it's what moves Passive >= Expenses.
    Returns the amount paid, or 0 if it couldn't be afforded."""
    amount = s["liabilities"].get(key, 0)
    if amount <= 0 or s["savings"] < amount:
        return 0
    s["savings"] -= amount
    del s["liabilities"][key]
    if key in s["expenses"]:
        del s["expenses"][key]
    return amount

def _debt(s, fid):
    st.markdown("### 💳 Pay Off Debt")
    st.caption("Paying off a liability in full also removes its monthly payment from your "
               "expenses — the fastest lever you have toward Passive Income ≥ Expenses.")
    if not s["liabilities"]:
        st.markdown('<div class="cfc" style="text-align:center;color:#00ff88;">🎉 Debt-free! Every liability is paid off.</div>',
                    unsafe_allow_html=True)
        return
    for key, amount in list(s["liabilities"].items()):
        label = _LIABILITY_LABELS.get(key, key.replace("_"," ").title())
        monthly = s["expenses"].get(key, 0)
        can_afford = s["savings"] >= amount
        st.markdown(
            f'<div class="cfc" style="border-left:3px solid {"#00ff88" if can_afford else "#334455"};">' +
            f'<div style="display:flex;justify-content:space-between;">' +
            f'<span style="color:#c8d8ff;">{label}</span>' +
            f'<span style="color:{"#00ff88" if can_afford else "#445566"};font-size:.72rem;">' +
            f'{"✅ CAN PAY OFF" if can_afford else "❌ SAVE MORE"}</span></div>' +
            f'<div style="font-size:.78rem;display:flex;gap:16px;margin-top:4px;">' +
            f'<span style="color:#ff4444;">Payoff: {_fmt(amount)}</span>' +
            (f'<span style="color:#8899bb;">Frees up: {_fmt(monthly)}/mo</span>' if monthly else "") +
            f'</div></div>', unsafe_allow_html=True
        )
        if can_afford:
            if st.button(f"💳 Pay Off {label} — {_fmt(amount)}", key=f"payoff_{key}", use_container_width=True, type="primary"):
                paid = _payoff_debt(s, key)
                s["total_xp"] = s.get("total_xp",0) + 30
                _log(s, f"💳 Paid off {label} ({_fmt(paid)}). " +
                        (f"Freed up {_fmt(monthly)}/mo!" if monthly else "Debt-free on this one!"))
                try:
                    from family_profiles import award_cross_tool_reward
                    award_cross_tool_reward(fid,"sovereign_life","debt_payoff",xp=30)
                except: pass
                save_game(s,fid); st.rerun()

def _do_buy(s, card, fid):
    s["savings"] -= card["cost"]
    k = f"{card['id']}_{s['turn']}"
    s["assets"][k] = {"name":card["name"],"emoji":card["emoji"],"cf":card["cf"],"val":card["val"],"type":card["type"]}
    if card["cf"]>0: s["income"][k] = card["cf"]
    s["total_xp"] = s.get("total_xp",0)+25; s["turn"]+=1
    _log(s, f"✅ Bought {card['name']} for {_fmt(card['cost'])}. +{_fmt(card['cf'])}/mo passive")
    try:
        from family_profiles import award_cross_tool_reward
        award_cross_tool_reward(fid,"sovereign_life",f"bought_{card['type']}",xp=25)
    except: pass

def _apply_event(s, card):
    e = card["effect"]
    if e=="btc_2x":
        for k,a in s["assets"].items():
            if a["type"]=="bitcoin": a["val"]=a.get("val",0)*2
        _log(s,"₿ Bitcoin halving — BTC assets doubled!")
    elif e=="rent_up":
        for k,a in s["assets"].items():
            if a["type"]=="rental" and a.get("cf",0)>0:
                a["cf"]=int(a["cf"]*1.2); s["income"][k]=a["cf"]
        _log(s,"🏠 Rental surge +20%")
    elif e=="inflation":
        s["expenses"]["inflation"]=s["expenses"].get("inflation",0)+200
        _log(s,"🖨️ Inflation — expenses +$200/mo")
    elif e=="ai_boost":
        for k,a in s["assets"].items():
            if a["type"]=="business" and a.get("cf",0)>0:
                a["cf"]=int(a["cf"]*1.5); s["income"][k]=a["cf"]
        _log(s,"🤖 AI tools cheaper — business +50%")
    elif e=="recession":
        for k,a in s["assets"].items():
            if a["type"]=="stocks": a["val"]=int(a.get("val",0)*0.7)
        s["savings"]+=500; _log(s,"📉 Recession — stocks -30%, +$500 buying opp")
    elif e=="tax_hit":
        s["expenses"]["new_tax"]=s["expenses"].get("new_tax",0)+300
        _log(s,"📋 New tax law — expenses +$300/mo")
    elif e=="lightning":
        for k,a in s["assets"].items():
            if a["type"]=="bitcoin":
                a["cf"]=a.get("cf",0)+100; s["income"][k]=a["cf"]
        _log(s,"⚡ Lightning mainstream — BTC nodes +$100/mo")
    elif e=="property_up":
        for k,a in s["assets"].items():
            if a["type"]=="rental": a["val"]=int(a.get("val",0)*1.25)
        _log(s,"🏘️ Housing boom — property +25%")
    elif e=="payday":
        c=cf(s); s["savings"]+=c; _log(s,f"💵 Payday! +{_fmt(c)}")
    elif e=="job_warning":
        _log(s,"⚠️ Layoffs nearby. Passive income = real security.")

# ══════════════════════════════════════════════════════════════════════════════
def _sheet(s, pv, ev, cfv):
    st.markdown("### 📊 Financial Statement")
    c1,c2 = st.columns(2)
    def row(lbl, val, color, dash=False):
        bdr = "border-top:1px solid #222;" if dash else "border-bottom:1px solid #1a2233;"
        return (f'<div style="display:flex;justify-content:space-between;font-size:.8rem;padding:3px 0;{bdr}">' +
                f'<span style="color:{color};">{lbl}</span><span style="color:{color};">{val}</span></div>')
    with c1:
        st.markdown("**Income**")
        for k,v in s["income"].items():
            lbl = "Salary" if k=="salary" else s["assets"].get(k,{}).get("name",k)
            c = "#c8d8ff" if k=="salary" else "#00ff88"
            st.markdown(row(lbl, f"+{_fmt(v)}", c), unsafe_allow_html=True)
        st.markdown(row("TOTAL INCOME", f"+{_fmt(sum(s['income'].values()))}", "#00ff88", True), unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**Expenses**")
        for k,v in s["expenses"].items():
            st.markdown(row(k.replace("_"," ").title(), f"-{_fmt(v)}", "#8899bb"), unsafe_allow_html=True)
        st.markdown(row("TOTAL EXPENSES", f"-{_fmt(ev)}", "#ff4444", True), unsafe_allow_html=True)
        cfcolor = "#00ff88" if cfv>=0 else "#ff4444"
        st.markdown(row("MONTHLY CASH FLOW", _fmt(cfv), cfcolor, True), unsafe_allow_html=True)
    with c2:
        st.markdown("**Assets**")
        for k,a in s["assets"].items():
            st.markdown(row(f'{a["emoji"]} {a["name"]}', _fmt(a.get("val",0)), "#a020f0"), unsafe_allow_html=True)
        st.markdown(row("TOTAL ASSETS", _fmt(assets_val(s)), "#a020f0", True), unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**Liabilities**")
        for k,v in s["liabilities"].items():
            st.markdown(row(k.replace("_"," ").title(), f"-{_fmt(v)}", "#556677"), unsafe_allow_html=True)
        nw = net_worth(s)
        nwc = "#00ff88" if nw>=0 else "#ff4444"
        st.markdown(row("TOTAL LIABILITIES", f"-{_fmt(liab_val(s))}", "#ff4444", True), unsafe_allow_html=True)
        st.markdown(row("NET WORTH", _fmt(nw), nwc, True), unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
def _market(s, fid):
    st.markdown("### 🏪 Direct Marketplace")
    st.caption("Buy deals directly using savings. No card draw needed.")
    ft = st.selectbox("Filter:", ["All","bitcoin","rental","business","stocks"], key="mft")
    owned = {a["name"] for a in s["assets"].values()}
    all_d = SMALL_DEALS+BIG_DEALS
    if ft!="All": all_d=[d for d in all_d if d["type"]==ft]
    for d in all_d:
        if d["name"] in owned: continue
        af = s["savings"]>=d["cost"]
        st.markdown(
            f'<div class="cfc" style="border-left:3px solid {"#00ff88" if af else "#334455"};">' +
            f'<div style="display:flex;justify-content:space-between;">' +
            f'<span style="color:#c8d8ff;">{d["emoji"]} {d["name"]}</span>' +
            f'<span style="color:{"#00ff88" if af else "#445566"};font-size:.72rem;">{"✅ CAN BUY" if af else "❌ SAVE MORE"}</span></div>' +
            f'<div style="color:#556677;font-size:.75rem;margin:3px 0;">{d["desc"]}</div>' +
            f'<div style="font-size:.75rem;display:flex;gap:12px;">' +
            f'<span style="color:#ff4444;">{_fmt(d["cost"])}</span>' +
            f'<span style="color:#00ff88;">+{_fmt(d["cf"])}/mo</span>' +
            f'<span style="color:#a020f0;">{_fmt(d["val"])} value</span></div></div>',
            unsafe_allow_html=True
        )
        if af or d["cost"]==0:
            lbl = f"Buy {d['name']}" if d["cost"]>0 else f"Start {d['name']} (free)"
            if st.button(lbl, key=f"mkt_{d['id']}", use_container_width=True):
                _do_buy(s, d, fid); save_game(s,fid); st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
def _escape_screen(s, fid):
    pv=passive(s); ev=expenses(s)
    st.markdown(
        f'<div style="background:linear-gradient(135deg,#f7931a18,#00ff8818);border:2px solid #f7931a;' +
        f'border-radius:12px;padding:24px;text-align:center;margin:16px 0;">' +
        f'<div style="font-family:Orbitron,monospace;font-size:1.8rem;color:#f7931a;">🎉 YOU ESCAPED THE RAT RACE!</div>' +
        f'<div style="color:#00ff88;font-size:1rem;margin:8px 0;">Passive {_fmt(pv)}/mo ≥ Expenses {_fmt(ev)}/mo</div>' +
        f'<div style="color:#8899bb;font-size:.82rem;">Dream: {s.get("dream","")}</div>' +
        f'<div style="color:#445566;font-size:.75rem;margin-top:6px;">' +
        f'{PROFESSIONS[s["profession"]]["name"]} · Turn {s["turn"]} · XP: {s.get("total_xp",0)+500}</div></div>',
        unsafe_allow_html=True
    )
    st.markdown("""
    <div style='color:#8899bb;font-size:.85rem;line-height:1.9;margin:16px 0;'>
    <strong style='color:#c8d8ff;'>What you just did:</strong><br>
    You moved money from your paycheck into assets. Assets generated income.
    Income exceeded expenses. <em>You don't have to trade time for money anymore.</em><br><br>
    This is the entire point — Rich Dad called it the "cash flow quadrant." 
    Move from the left side (employee/self-employed) to the right (business owner/investor).
    In 2026 that means Bitcoin for savings, AI for leverage, sovereign infrastructure for permanence.<br><br>
    <strong style='color:#f7931a;'>The Fast Track: bigger deals, Bitcoin treasury, generational legacy.</strong>
    </div>
    """, unsafe_allow_html=True)
    c1,c2 = st.columns(2)
    with c1:
        if st.button("🚀 Enter Fast Track", use_container_width=True, type="primary"):
            s["fast_track"]=True; _log(s,"🚀 Fast Track!"); save_game(s,fid); st.rerun()
    with c2:
        if st.button("🔄 New Game", use_container_width=True):
            _sp(fid).unlink(missing_ok=True)
            for k in ["card"]:
                if k in st.session_state: del st.session_state[k]
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
def _fast_track(s, fid):
    pv=passive(s); nw=net_worth(s)
    st.markdown('<div class="cfh">🚀 FAST TRACK — LEGACY MODE</div>', unsafe_allow_html=True)
    st.caption(f"Dream: {s.get('dream','')} · Passive: {_fmt(pv)}/mo · Net Worth: {_fmt(nw)}")
    st.markdown(
        '<div class="cfc" style="border-left:3px solid #f7931a;">' +
        '<div style="color:#f7931a;font-family:Orbitron,monospace;font-size:.8rem;">BUILDING LEGACY</div>' +
        '<div style="color:#8899bb;font-size:.82rem;margin-top:6px;line-height:1.7;">' +
        'Bigger deals. Bitcoin treasury. Multi-family real estate. AI businesses that scale.<br>' +
        'Goal: compounding wealth, generational impact, on-chain forever.</div></div>',
        unsafe_allow_html=True
    )
    st.divider()
    owned = {a["name"] for a in s["assets"].values()}
    for d in BIG_DEALS:
        if d["name"] in owned: continue
        af = s["savings"]>=d["cost"]
        st.markdown(
            f'<div class="cfc" style="border-left:3px solid {"#f7931a" if af else "#334455"};">' +
            f'{d["emoji"]} <strong style="color:#c8d8ff;">{d["name"]}</strong>' +
            f'<div style="color:#8899bb;font-size:.8rem;margin:4px 0;">{d["desc"]}</div>' +
            f'<div style="font-size:.75rem;display:flex;gap:12px;">' +
            f'<span style="color:#ff4444;">{_fmt(d["cost"])}</span>' +
            f'<span style="color:#00ff88;">+{_fmt(d["cf"])}/mo</span>' +
            f'<span style="color:#a020f0;">{_fmt(d["val"])}</span></div>' +
            f'<div class="cfl">💡 {d["lesson"]}</div></div>', unsafe_allow_html=True
        )
        if af:
            if st.button(f"Buy {d['name']}", key=f"ft_{d['id']}", use_container_width=True, type="primary"):
                _do_buy(s,d,fid); s["total_xp"]=s.get("total_xp",0)+100
                save_game(s,fid); st.rerun()
    st.divider()
    st.markdown(
        f'<div class="cfc" style="border-left:3px solid #a020f0;">' +
        f'<div style="color:#a020f0;font-family:Orbitron,monospace;font-size:.8rem;">LEGACY STATUS</div>' +
        f'Net Worth: <strong>{_fmt(nw)}</strong> · Passive: <strong style="color:#00ff88;">{_fmt(pv)}/mo</strong> · ' +
        f'Assets: <strong>{len(s["assets"])}</strong> · XP: <strong>{s.get("total_xp",0)}</strong></div>',
        unsafe_allow_html=True
    )
    if st.button("🔄 Start New Game", use_container_width=True):
        _sp(fid).unlink(missing_ok=True)
        for k in ["card"]:
            if k in st.session_state: del st.session_state[k]
        st.rerun()

if __name__=="__main__":
    render_sovereign_life()

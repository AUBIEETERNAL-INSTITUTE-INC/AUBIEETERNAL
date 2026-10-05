#!/usr/bin/env python3
"""Ask Aubie to draft Money Smarts flashcard decks (3 age levels)."""
from __future__ import annotations
import json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path.home() / "vanhorn-repo" / "aubie-bot"))
from thermal import wait_for_cool, status_line, TooHot
from openai import OpenAI

OUT = Path(__file__).resolve().parents[1] / "flashcards" / "_aubie_drafts"
OUT.mkdir(parents=True, exist_ok=True)

COMMON = """
Return ONLY valid JSON (no markdown fences, no commentary).
Shape:
{
  "id": "...",
  "title": "...",
  "emoji": "...",
  "age_level": "little|middle|older",
  "ages": "e.g. 4-7",
  "group": "money_smarts",
  "description": "one line",
  "cards": [
    {"id": "...", "front": "question or term", "back": "short plain answer", "hint": "optional emoji"}
  ]
}
Rules:
- Factual, neutral, age-appropriate. No scolding, no politics, no brand pitches.
- Keep backs short (1-2 sentences max). Numbers must be correct.
- No investment advice. Bitcoin: what it is, neutrally ? not buy/sell advice.
"""

PROMPTS = {
"money_little": COMMON + """
id must be "money_little". title "Money Smarts ? Little". emoji "??". age_level "little". ages "4-7".
Exactly 20 cards about: needs vs wants, saving in a jar, making change with coins/dollars,
what a price tag means, sharing vs spending, earning a small chore allowance idea,
counting coins (simple), "is this a need or a want?" examples.
ids: money-little-01 through money-little-20.
Use kid words. Example fronts like "Is candy a need or a want?" / "What does $3 on a price tag mean?"
""",

"money_middle": COMMON + """
id must be "money_middle". title "Money Smarts ? Middle". emoji "??". age_level "middle". ages "8-12".
Exactly 24 cards about: earning (job/chores), budgeting (give/save/spend jars),
saving vs spending, simple interest (explain with a tiny example: e.g. $100 at 5% for 1 year = $5 interest),
comparing prices, unit price (which cereal is cheaper per ounce?), goals, delayed gratification.
Include 2-3 cards with simple interest math that a checker can verify.
ids: money-middle-01 through money-middle-24.
Keep numbers small and correct.
""",

"money_older": COMMON + """
id must be "money_older". title "Money Smarts ? Older". emoji "??". age_level "older". ages "13+".
Exactly 28 cards about:
- compound interest (one worked example with correct math, e.g. $100 at 10% compounded yearly for 2 years)
- credit and debt: how interest grows on unpaid balances (simple illustration)
- scams and phishing red flags (fake links, pressure, "send gift cards", too-good-to-be-true)
- inflation: prices rising over time, money buying less
- what money is (medium of exchange, store of value ? plain words)
- Bitcoin basics framed neutrally: digital money secured by a network, limited supply design,
  volatile price, not issued by a government ? NO buy/sell advice, NO predictions
ids: money-older-01 through money-older-28.
Any math example must be arithmetically correct.
""",
}

def ask(label: str, prompt: str) -> dict:
    print(f"[money] GPU before {label}: {status_line()}", flush=True)
    wait_for_cool(reason=f"draft {label}")
    client = OpenAI(base_url="http://127.0.0.1:11434/v1", api_key="ollama")
    t0 = time.time()
    resp = client.chat.completions.create(
        model="qwen2.5:14b",
        messages=[
            {"role": "system", "content": "You output only valid JSON. No markdown. No extra text."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.25,
        max_tokens=5000,
    )
    text = (resp.choices[0].message.content or "").strip()
    print(f"[money] {label} in {time.time()-t0:.1f}s, {len(text)} chars", flush=True)
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    (OUT / f"{label}_raw.txt").write_text(text, encoding="utf-8")
    data = json.loads(text)
    (OUT / f"{label}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return data

def main():
    summary = {}
    for label, prompt in PROMPTS.items():
        try:
            d = ask(label, prompt)
            summary[label] = {"n": len(d.get("cards", [])), "title": d.get("title"), "age": d.get("age_level")}
        except TooHot as e:
            print(f"[money] TOO HOT {label}: {e}", file=sys.stderr); sys.exit(2)
        except Exception as e:
            print(f"[money] FAIL {label}: {type(e).__name__}: {e}", file=sys.stderr); sys.exit(3)
    print(json.dumps(summary, indent=2))
    print("[money] done", flush=True)

if __name__ == "__main__":
    main()

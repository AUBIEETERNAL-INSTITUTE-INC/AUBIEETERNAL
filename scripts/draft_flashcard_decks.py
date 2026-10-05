#!/usr/bin/env python3
"""Ask local Aubie (qwen2.5:14b) to draft ABC and Reading flashcard decks.
Uses thermal heat guard. Prints JSON to stdout and writes draft files.
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path.home() / "vanhorn-repo" / "aubie-bot"))
from thermal import wait_for_cool, status_line, TooHot

try:
    from openai import OpenAI
except ImportError:
    print("openai package missing", file=sys.stderr)
    sys.exit(1)

OUT = Path(__file__).resolve().parents[1] / "flashcards" / "_aubie_drafts"
OUT.mkdir(parents=True, exist_ok=True)

ABC_PROMPT = """You are helping build kid flash cards for ages 4-7.
Return ONLY valid JSON (no markdown fences, no commentary) with this exact shape:
{
  "id": "abc",
  "title": "ABC",
  "emoji": "??",
  "description": "short one-line description",
  "cards": [
    {"id": "abc-a", "front": "A a", "back": "Apple", "hint": "??"},
    ...
  ]
}
Rules:
- Exactly 26 cards, one for each letter A-Z.
- front is like "A a" (uppercase then lowercase).
- back is ONE simple common English noun a child knows, starting with that letter.
- hint is ONE fitting emoji (or empty string if none fits well).
- Prefer concrete everyday words (Apple, Ball, Cat) over abstract or rare ones.
- No brand names, no politics, no scary words.
- id must be abc-a through abc-z (lowercase letter).
"""

READING_PROMPT = """You are helping build kid flash cards for ages 5-8 learning to read.
Return ONLY valid JSON (no markdown fences, no commentary) with this exact shape:
{
  "id": "reading",
  "title": "Reading",
  "emoji": "??",
  "description": "short one-line description",
  "cards": [
    {"id": "read-001", "front": "cat", "back": "a small pet that says meow", "hint": "??", "kind": "cvc"},
    ...
  ]
}
Rules:
- Exactly 40 cards total.
- First 20: common English sight words (the, and, is, you, ...). kind="sight".
  front = the word, back = a plain kid-friendly meaning or example sentence using the word, hint optional emoji.
- Next 20: short CVC (consonant-vowel-consonant) words like cat, dog, sun, pen. kind="cvc".
  front = the word, back = a short plain meaning, hint = emoji when possible.
- Use only lowercase on front for reading cards.
- No brand names, no politics, no scary words.
- ids: read-001 through read-040.
"""

def ask(prompt: str, label: str) -> dict:
    print(f"[draft] GPU before {label}: {status_line()}", flush=True)
    wait_for_cool(reason=f"draft {label}")
    client = OpenAI(base_url="http://127.0.0.1:11434/v1", api_key="ollama")
    t0 = time.time()
    resp = client.chat.completions.create(
        model="qwen2.5:14b",
        messages=[
            {"role": "system", "content": "You output only valid JSON. No markdown. No extra text."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=4000,
    )
    text = (resp.choices[0].message.content or "").strip()
    elapsed = time.time() - t0
    print(f"[draft] {label} answered in {elapsed:.1f}s, {len(text)} chars", flush=True)
    # strip accidental fences
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    raw_path = OUT / f"{label}_raw.txt"
    raw_path.write_text(text, encoding="utf-8")
    data = json.loads(text)
    (OUT / f"{label}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return data

def main():
    results = {}
    for label, prompt in (("abc", ABC_PROMPT), ("reading", READING_PROMPT)):
        try:
            results[label] = ask(prompt, label)
        except TooHot as e:
            print(f"[draft] TOO HOT for {label}: {e}", file=sys.stderr)
            sys.exit(2)
        except Exception as e:
            print(f"[draft] FAILED {label}: {type(e).__name__}: {e}", file=sys.stderr)
            # keep raw if any
            sys.exit(3)
    print(json.dumps({k: {"n_cards": len(v.get("cards", [])), "title": v.get("title")} for k, v in results.items()}, indent=2))
    print("[draft] done", flush=True)

if __name__ == "__main__":
    main()

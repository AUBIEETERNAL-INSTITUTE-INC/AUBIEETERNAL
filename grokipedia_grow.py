#!/usr/bin/env python3
"""Nightly Grokipedia growth — draft 1-3 new kid-friendly principles via local Ollama.

Heat-guarded. Never appends without human approval (Discord / SimpleX).
Writes drafts to /mnt/main/grokipedia_pending.json.
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "swarm"))

from grokipedia_lib import (  # noqa: E402
    approved_entries,
    load_pending,
    save_pending,
    uncovered_topics,
)

try:
    from thermal import TooHot, wait_for_cool, status_line
except Exception:  # pragma: no cover
    class TooHot(Exception):
        pass
    def wait_for_cool(reason: str = ""):
        return {}
    def status_line() -> str:
        return "thermal: unavailable"

OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
MODEL = os.environ.get("AUBIE_GROKIPEDIA_MODEL", "qwen2.5:14b")
MAX_DRAFTS = int(os.environ.get("AUBIE_GROKIPEDIA_N", "2"))
TZ = ZoneInfo("America/New_York")


def _chat(system: str, user: str, max_tokens: int = 500) -> str:
    wait_for_cool("grokipedia_grow")
    r = requests.post(
        f"{OLLAMA_BASE}/v1/chat/completions",
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.5,
            "stream": False,
            "max_tokens": max_tokens,
        },
        timeout=600,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def _parse_json_blob(text: str) -> dict:
    text = text.strip()
    if "```" in text:
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("no JSON object in model output")
    return json.loads(text[start : end + 1])


def draft_one(topic: dict, existing_titles: list[str]) -> dict | None:
    system = (
        "You write short, honest, kid-friendly encyclopedia entries for a family learning portal. "
        "No hype, no mystical language, no fake metrics. Plain English a careful parent would trust. "
        "Respond with ONLY a JSON object."
    )
    user = (
        f"Topic: {topic['title']}\n"
        f"Hint: {topic.get('hint','')}\n"
        f"Suggested source tag: {topic.get('source','General')}\n\n"
        f"Already covered titles (do not duplicate): {', '.join(existing_titles[:40])}\n\n"
        "Return JSON with keys:\n"
        '  "title": short name (3-6 words),\n'
        '  "principle": one clear sentence,\n'
        '  "explanation": 2-4 sentences a 10-year-old can follow,\n'
        '  "source": short source tag,\n'
        '  "ok": true/false (false if you cannot write something honest and non-duplicative)\n'
    )
    try:
        raw = _chat(system, user, max_tokens=450)
        data = _parse_json_blob(raw)
    except TooHot as e:
        print(f"[grow] too hot: {e}")
        return None
    except Exception as e:
        print(f"[grow] draft failed for {topic['title']}: {e}")
        return None
    if not data.get("ok", True):
        print(f"[grow] model declined: {topic['title']}")
        return None
    title = (data.get("title") or topic["title"]).strip()
    principle = (data.get("principle") or "").strip()
    explanation = (data.get("explanation") or "").strip()
    source = (data.get("source") or topic.get("source") or "General").strip()
    if not principle or not explanation:
        return None
    return {
        "id": uuid.uuid4().hex[:10],
        "title": title,
        "principle": principle,
        "explanation": explanation,
        "source": source,
        "topic_hint": topic.get("hint", ""),
        "created_at": datetime.now(TZ).isoformat(),
        "model": MODEL,
        "status": "pending",
    }


def score_and_dedupe(draft: dict, existing: list[dict]) -> dict:
    titles = [e.get("title", "") for e in existing]
    principles = [e.get("principle", "") for e in existing]
    system = (
        "You are a careful editor for a kids' learning encyclopedia. "
        "Score the draft 0.0-1.0 for clarity, honesty, and age-appropriateness. "
        "Flag duplicates. Respond with ONLY JSON."
    )
    user = (
        f"DRAFT:\n{json.dumps(draft, ensure_ascii=False)}\n\n"
        f"EXISTING TITLES:\n{json.dumps(titles, ensure_ascii=False)}\n\n"
        f"EXISTING PRINCIPLES (sample):\n{json.dumps(principles[:25], ensure_ascii=False)}\n\n"
        "Return JSON: {\"score\": float, \"duplicate\": bool, \"reason\": short string, \"accept\": bool}\n"
        "accept=true only if score>=0.7 and duplicate=false and content is suitable for kids."
    )
    try:
        raw = _chat(system, user, max_tokens=250)
        data = _parse_json_blob(raw)
    except TooHot as e:
        draft["score_error"] = str(e)
        draft["accept"] = False
        return draft
    except Exception as e:
        draft["score_error"] = str(e)
        draft["accept"] = False
        return draft
    draft["score"] = float(data.get("score") or 0)
    draft["duplicate"] = bool(data.get("duplicate"))
    draft["score_reason"] = (data.get("reason") or "")[:240]
    draft["accept"] = bool(data.get("accept")) and draft["score"] >= 0.7 and not draft["duplicate"]
    # local title collision check
    low = draft["title"].strip().lower()
    if any(low == (t or "").strip().lower() for t in titles):
        draft["duplicate"] = True
        draft["accept"] = False
    return draft


def main() -> int:
    print(f"[grow] {status_line()}")
    print(f"[grow] model={MODEL} max_drafts={MAX_DRAFTS}")
    existing = approved_entries()
    topics = uncovered_topics(limit=20)
    if not topics:
        print("[grow] no uncovered topics left in grokipedia_sources.txt")
        return 0
    pending = load_pending()
    # drop already-decided
    pending = [d for d in pending if d.get("status") == "pending"]
    made = 0
    for topic in topics:
        if made >= MAX_DRAFTS:
            break
        print(f"[grow] drafting: {topic['title']}")
        draft = draft_one(topic, [e.get("title", "") for e in existing] + [d.get("title","") for d in pending])
        if not draft:
            continue
        draft = score_and_dedupe(draft, existing + pending)
        print(f"[grow] scored {draft.get('score')} accept={draft.get('accept')} dup={draft.get('duplicate')} — {draft['title']}")
        if draft.get("accept"):
            pending.append(draft)
            made += 1
        else:
            print(f"[grow] skipped: {draft.get('score_reason') or draft.get('score_error')}")
    save_pending(pending)
    print(f"[grow] queued {made} new draft(s); pending total={len(pending)}")
    for d in pending[-made or None :]:
        print("---")
        print(f"ID: {d['id']}")
        print(f"Title: {d['title']}")
        print(f"Principle: {d['principle']}")
        print(f"Explanation: {d['explanation']}")
        print(f"Source: {d['source']} | score={d.get('score')}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except TooHot as e:
        print(f"[grow] aborted: {e}")
        raise SystemExit(2)

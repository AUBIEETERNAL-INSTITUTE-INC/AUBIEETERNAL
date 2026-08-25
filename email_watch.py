"""
email_watch.py — reads Matthew's real inbox via Proton Mail Bridge (local
IMAP, see aubie-proton-bridge.service) and has local Ollama pick out
anything task/deadline-shaped, so Aubie can actually answer "what am I
supposed to do today" or proactively flag something time-sensitive
("Matthew, it's 10 o'clock and you have to be at the airport in 3 hours").

Two jobs, both driven by the same core scan:
  - daily_digest()  — meant to run once each morning (see
    maybe_trigger_email_digest() in swarm/swarm_v4_1.py, mirrors the
    existing 6AM morning-synthesis / 9AM curriculum-autogen pattern):
    everything task-shaped found in recent mail, written to a private
    local file - never the public insights/daily/ - and NOT spoken aloud
    on its own (see PRIVACY note below).
  - check_urgent() — meant to run every 15-30 min: only items with a real
    deadline landing within URGENT_WINDOW_HOURS get flagged, and THOSE
    get spoken out loud via /speak_local (through assistant_server.py,
    same path phone_ui.py's aubieSpeak() already uses).

PRIVACY: this reads real personal email. The digest file lives under
{DATA_DIR}/email_digest/ - deliberately NOT under the repo tree at all,
so it can never be swept up by swarm_v4_1.py's github_push_truth_log()
(which pushes insights/daily/*.md to the PUBLIC repo) even by accident.
Nothing here is ever committed or pushed anywhere. The daily digest is
written to a file for the family to read in the portal, not spoken
proactively by default - only genuinely urgent, deadline-driven items are
voiced without being asked, since reading out arbitrary email content
unprompted (in front of whoever's in the room) is a real privacy
consideration this project's existing voice pipeline was never designed
around.
"""

import email
import imaplib
import json
import os
import re
from datetime import datetime, timedelta
from email.header import decode_header
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

try:
    from family_profiles import DATA_DIR
except Exception:
    DATA_DIR = Path("/mnt/main")

EMAIL_DIGEST_DIR = DATA_DIR / "email_digest"
EMAIL_DIGEST_DIR.mkdir(parents=True, exist_ok=True)
DIGEST_PATH        = EMAIL_DIGEST_DIR / "today.json"
URGENT_STATE_PATH  = EMAIL_DIGEST_DIR / "urgent_state.json"  # tracks what's already been spoken

IMAP_HOST = "127.0.0.1"
IMAP_PORT = 1143
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODELS = ["qwen2.5:14b", "qwen2.5:7b"]

LOOKBACK_HOURS      = 48   # how far back to scan for the daily digest
URGENT_WINDOW_HOURS  = 4   # a deadline inside this window gets spoken proactively
MAX_MESSAGES_SCANNED = 40  # cap per run - keeps this fast and the LLM prompt small


def _decode(value) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    out = []
    for text, enc in parts:
        out.append(text.decode(enc or "utf-8", errors="replace") if isinstance(text, bytes) else text)
    return "".join(out)


def _plain_text_body(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition", "")):
                try:
                    return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="replace")
                except Exception:
                    continue
        return ""
    try:
        return msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", errors="replace")
    except Exception:
        return ""


def fetch_recent_messages(lookback_hours: int = LOOKBACK_HOURS) -> list[dict]:
    """Real IMAP read, read-only (never marks messages as read, never
    deletes/moves anything). Returns [{subject, from, date, snippet}]."""
    user = os.environ.get("PROTON_IMAP_USER")
    pw   = os.environ.get("PROTON_IMAP_PASS")
    if not user or not pw:
        raise RuntimeError("PROTON_IMAP_USER/PROTON_IMAP_PASS not set in .env")

    since = (datetime.now() - timedelta(hours=lookback_hours)).strftime("%d-%b-%Y")

    m = imaplib.IMAP4(IMAP_HOST, IMAP_PORT)
    try:
        m.starttls()
        m.login(user, pw)
        m.select("INBOX", readonly=True)
        status, nums = m.search(None, f'(SINCE "{since}")')
        ids = nums[0].split()[-MAX_MESSAGES_SCANNED:]  # most recent N within the window

        messages = []
        for msg_id in ids:
            status, data = m.fetch(msg_id, "(RFC822)")
            if status != "OK" or not data or not data[0]:
                continue
            msg = email.message_from_bytes(data[0][1])
            date_hdr = msg.get("Date")
            try:
                dt = parsedate_to_datetime(date_hdr) if date_hdr else None
            except Exception:
                dt = None
            body = _plain_text_body(msg)
            messages.append({
                "subject": _decode(msg.get("Subject")),
                "from": _decode(msg.get("From")),
                "date": dt.isoformat() if dt else "",
                "snippet": re.sub(r"\s+", " ", body).strip()[:800],
            })
        return messages
    finally:
        try:
            m.logout()
        except Exception:
            pass


def _call_ollama(prompt: str) -> str | None:
    from model_selector import ranked_try_order
    try:
        tags = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        available = [mo["name"] for mo in tags.json().get("models", [])]
    except Exception:
        available = []
    to_try = ranked_try_order(available) or OLLAMA_MODELS
    for model in to_try:
        try:
            r = requests.post(
                f"{OLLAMA_URL}/api/chat",
                json={"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False},
                timeout=120,
            )
            if r.status_code == 200:
                return r.json().get("message", {}).get("content", "")
        except Exception:
            continue
    return None


def _extract_json_list(text: str) -> list:
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return []
    try:
        return json.loads(m.group(0))
    except Exception:
        return []


TASK_EXTRACTION_PROMPT = """You're reviewing real emails for {name} to find anything that's actually a
task, deadline, appointment, or something requiring action - ignore newsletters, marketing,
notifications, and anything with no real action attached.

Emails (most recent first):
{emails_block}

Reply with ONLY a JSON array, no other text. One object per real task/deadline found (empty array
[] if none):
[
  {{
    "summary": "short human description of what needs to happen",
    "deadline": "ISO 8601 datetime if a specific time/date is mentioned, otherwise null",
    "source_subject": "the email subject this came from",
    "urgency": "high, medium, or low - high only for something with a real, soon deadline"
  }}
]"""


def extract_tasks(messages: list[dict], name: str = "Matthew") -> list[dict]:
    if not messages:
        return []
    emails_block = "\n\n".join(
        f"Subject: {m['subject']}\nFrom: {m['from']}\nDate: {m['date']}\nContent: {m['snippet']}"
        for m in messages
    )
    prompt = TASK_EXTRACTION_PROMPT.format(name=name, emails_block=emails_block)
    reply = _call_ollama(prompt)
    if not reply:
        return []
    tasks = _extract_json_list(reply)
    return tasks if isinstance(tasks, list) else []


def daily_digest(name: str = "Matthew") -> dict:
    """Scans recent mail, writes the private digest file, returns it.
    Meant to run once a day (see the swarm trigger) - never speaks
    anything, never gets pushed anywhere public."""
    try:
        messages = fetch_recent_messages(LOOKBACK_HOURS)
        tasks = extract_tasks(messages, name)
        digest = {
            "generated_at": datetime.now().isoformat(),
            "messages_scanned": len(messages),
            "tasks": tasks,
        }
        DIGEST_PATH.write_text(json.dumps(digest, indent=2))
        return digest
    except Exception as e:
        return {"error": str(e), "tasks": []}


def _already_spoken(task_key: str) -> bool:
    try:
        state = json.loads(URGENT_STATE_PATH.read_text()) if URGENT_STATE_PATH.exists() else {}
    except Exception:
        state = {}
    return task_key in state.get("spoken", [])


def _mark_spoken(task_key: str) -> None:
    try:
        state = json.loads(URGENT_STATE_PATH.read_text()) if URGENT_STATE_PATH.exists() else {}
    except Exception:
        state = {}
    spoken = state.setdefault("spoken", [])
    if task_key not in spoken:
        spoken.append(task_key)
    state["spoken"] = spoken[-200:]  # bounded, don't grow forever
    URGENT_STATE_PATH.write_text(json.dumps(state, indent=2))


def check_urgent(name: str = "Matthew", speak: bool = True) -> list[dict]:
    """Re-scans a short recent window and speaks (via assistant_server's
    /speak_local, same as phone_ui.py's aubieSpeak()) anything with a real
    deadline inside URGENT_WINDOW_HOURS - each item is only ever spoken
    once (tracked in urgent_state.json), so this is safe to run on a tight
    poll interval without repeating itself."""
    try:
        messages = fetch_recent_messages(lookback_hours=6)  # short window - this is the frequent poll, not the daily scan
        tasks = extract_tasks(messages, name)
    except Exception as e:
        return [{"error": str(e)}]

    now = datetime.now().astimezone()  # tz-aware local "now"
    urgent = []
    for t in tasks:
        deadline_str = t.get("deadline")
        if not deadline_str:
            continue
        try:
            deadline = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
        except Exception:
            continue
        if deadline.tzinfo is not None:
            # A real offset (e.g. the "+00:00" UTC the model tends to use) -
            # convert to local time before comparing. Blindly stripping
            # tzinfo here without converting first was a real bug caught
            # during testing: it silently compared e.g. "09:55 UTC" against
            # local wall-clock time as if they were the same timezone,
            # which would have produced a deadline off by however many
            # hours this machine's UTC offset is - exactly the kind of
            # error this feature exists to avoid.
            deadline = deadline.astimezone()
        else:
            # No offset given - the model had no timezone info to go on,
            # so the only reasonable assumption is that it already meant
            # local time (can't correctly convert from an unknown zone).
            deadline = deadline.astimezone(now.tzinfo)
        hours_until = (deadline - now).total_seconds() / 3600
        if 0 <= hours_until <= URGENT_WINDOW_HOURS:
            task_key = f"{t.get('source_subject','')}:{deadline_str}"
            if _already_spoken(task_key):
                continue
            urgent.append(t)
            if speak:
                _speak_urgent(name, t, hours_until)
            _mark_spoken(task_key)
    return urgent


def _speak_urgent(name: str, task: dict, hours_until: float) -> None:
    hours_txt = f"{hours_until:.1f}".rstrip("0").rstrip(".")
    message = f"{name}, heads up - {task['summary']}. That's about {hours_txt} hours from now."
    try:
        requests.post("http://127.0.0.1:8800/speak_local", data={"text": message}, timeout=15)
    except Exception as e:
        print(f"[email_watch] could not speak urgent task: {e}")


if __name__ == "__main__":
    import sys
    if "--urgent" in sys.argv:
        result = check_urgent(speak="--no-speak" not in sys.argv)
        print(json.dumps(result, indent=2))
    else:
        result = daily_digest()
        print(json.dumps(result, indent=2))

"""
AUBIEETERNAL -- Memory Manager
File: /home/aubieeternal/AUBIEETERNAL/memory_manager.py

Harvests Claude session transcripts, extracts durable facts with qwen2.5:14b,
and files them into a growing memory store.

Routing policy (HYBRID):
  - Tech / project / preference facts  -> auto-appended to memory immediately
  - Anything about PEOPLE              -> review queue, needs approval

Add to assistant_server.py:
    from memory_manager import router as memory_router
    app.include_router(memory_router)
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import os, json, re, glob, hashlib, datetime

import httpx

router = APIRouter()

# ── Paths ──────────────────────────────────────────────────────
BASE = "/home/aubieeternal/AUBIEETERNAL"
MEM = BASE + "/memory"
RAW = MEM + "/raw_sessions"       # .jsonl shipped from the tablet
PROCESSED = MEM + "/processed"    # marker files, so we never double-process
FACTS = MEM + "/facts"
PEOPLE = MEM + "/people"

AUTO_FILE = FACTS + "/auto_facts.md"        # tech/project/preference -> auto
PENDING_FILE = FACTS + "/pending_review.md"  # people facts -> needs approval
LOG_FILE = MEM + "/harvest.log"

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:14b"

for d in (MEM, RAW, PROCESSED, FACTS, PEOPLE):
    os.makedirs(d, exist_ok=True)


# ── Utilities ──────────────────────────────────────────────────
def now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def today() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d")


def log(msg: str):
    try:
        with open(LOG_FILE, "a") as f:
            f.write("[" + now() + "] " + msg + "\n")
    except Exception:
        pass


def ask_model(prompt: str, timeout: int = 180, num_predict: int = 1200) -> str:
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": num_predict},
    }
    with httpx.Client(timeout=timeout) as client:
        r = client.post(OLLAMA_URL, json=payload)
    return r.json().get("response", "").strip()


def known_people() -> list:
    """Names derived from files in memory/people/."""
    out = []
    for p in sorted(glob.glob(PEOPLE + "/*.md")):
        out.append(os.path.splitext(os.path.basename(p))[0])
    return out


def session_fingerprint(path: str) -> str:
    """Hash of path + size + mtime, so edited sessions get re-processed."""
    st = os.stat(path)
    raw = path + "|" + str(st.st_size) + "|" + str(int(st.st_mtime))
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def already_processed(path: str) -> bool:
    fp = session_fingerprint(path)
    return os.path.exists(PROCESSED + "/" + fp)


def mark_processed(path: str):
    fp = session_fingerprint(path)
    with open(PROCESSED + "/" + fp, "w") as f:
        f.write(os.path.basename(path) + "\n" + now() + "\n")


# ── Transcript extraction ──────────────────────────────────────
def extract_conversation(jsonl_path: str, max_chars: int = 24000) -> str:
    """Pull readable text out of a Claude session .jsonl, or a plain .md digest."""
    # Markdown digests are already clean prose -- just read them.
    if jsonl_path.lower().endswith(".md"):
        try:
            text = open(jsonl_path, "r", encoding="utf-8", errors="ignore").read()
            return text[-max_chars:]
        except Exception as e:
            log("read error " + jsonl_path + ": " + str(e))
            return ""

    lines = []
    try:
        with open(jsonl_path, "r", encoding="utf-8", errors="ignore") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except Exception:
                    continue

                msg = obj.get("message") or obj
                role = msg.get("role") or obj.get("type") or ""
                if role not in ("user", "assistant"):
                    continue

                content = msg.get("content")
                text = ""
                if isinstance(content, str):
                    text = content
                elif isinstance(content, list):
                    parts = []
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "text":
                            parts.append(c.get("text", ""))
                    text = "\n".join(parts)

                text = text.strip()
                if not text or text.startswith("<"):
                    continue
                # skip giant tool dumps
                if len(text) > 4000:
                    text = text[:4000] + " ...[truncated]"
                lines.append(role.upper() + ": " + text)
    except Exception as e:
        log("extract error " + jsonl_path + ": " + str(e))
        return ""

    convo = "\n\n".join(lines)
    # keep the most recent portion if very long
    if len(convo) > max_chars:
        convo = convo[-max_chars:]
    return convo


# ── Fact extraction prompt ─────────────────────────────────────
EXTRACT_PROMPT = """You are building a long-term memory file about a person named Mateo.

Below is a transcript of a conversation between Mateo (USER) and an AI assistant.

Extract ONLY durable, reusable facts -- things that will still be true and useful weeks
from now. Ignore step-by-step troubleshooting, one-off commands, and anything transient.

Return STRICT JSON with exactly these keys, no markdown fence, no commentary:

{
  "tech": ["fact about hardware, software, config, architecture decisions"],
  "projects": ["fact about ongoing projects and their current state"],
  "preferences": ["fact about how Mateo likes to work or be communicated with"],
  "people": [
    {"name": "lowercase_first_name", "fact": "something durable about this person or Mateo's relationship to them"}
  ]
}

Rules:
- Each fact is one short sentence. Be specific.
- If a category has nothing, use an empty list.
- "people" covers family, friends, pets, colleagues -- anyone mentioned as a person or animal.
- Use lowercase single-word names for the "name" field (e.g. "gabriela", "juan", "tommy").
- Do NOT invent anything. Only what is actually supported by the transcript.
- Do NOT include facts about the AI assistant itself.

KNOWN PEOPLE ALREADY TRACKED: {known}

TRANSCRIPT:
{convo}

JSON:"""


def parse_json_loose(text: str) -> dict:
    """Model output -> dict, tolerating code fences and stray prose."""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start:end + 1]
    try:
        return json.loads(text)
    except Exception:
        return {}


def dedupe_against(path: str, facts: list) -> list:
    """Drop facts already present (case-insensitive substring check)."""
    if not os.path.exists(path):
        return facts
    try:
        existing = open(path).read().lower()
    except Exception:
        return facts
    out = []
    for f in facts:
        key = f.strip().lower()
        if len(key) > 12 and key[:60] in existing:
            continue
        out.append(f)
    return out


def append_section(path: str, header: str, facts: list, source: str):
    if not facts:
        return 0
    with open(path, "a") as f:
        f.write("\n### " + header + " -- " + today() + "\n")
        f.write("_source: " + source + "_\n\n")
        for item in facts:
            f.write("- " + item.strip() + "\n")
    return len(facts)


def update_person_file(name: str, facts: list, source: str) -> int:
    """People facts go to the PENDING queue, not straight into the person file."""
    if not facts:
        return 0
    safe = re.sub(r"[^a-z0-9_]", "", name.lower().strip())
    if not safe:
        return 0
    with open(PENDING_FILE, "a") as f:
        f.write("\n### PERSON: " + safe + " -- " + today() + "\n")
        f.write("_source: " + source + "_\n")
        f.write("_approve with: POST /memory/approve {\"person\":\"" + safe + "\"}_\n\n")
        for item in facts:
            f.write("- " + item.strip() + "\n")
    return len(facts)


# ── Endpoints ──────────────────────────────────────────────────
class HarvestRequest(BaseModel):
    force: bool = False       # re-process everything, ignoring markers
    limit: int = 10           # max sessions per run


@router.post("/memory/harvest")
def harvest(req: HarvestRequest = HarvestRequest()):
    """
    Scan memory/raw_sessions/ for new transcripts, extract durable facts,
    auto-append tech/project/preference facts, queue people facts for review.
    """
    files = sorted(glob.glob(RAW + "/**/*.jsonl", recursive=True) +
                   glob.glob(RAW + "/**/*.md", recursive=True))
    if not files:
        return JSONResponse({
            "status": "ok",
            "message": "No session files found in " + RAW,
            "hint": "Ship transcripts from the tablet first.",
            "processed": 0,
        })

    todo = [f for f in files if req.force or not already_processed(f)]
    todo = todo[: max(1, req.limit)]

    if not todo:
        return JSONResponse({
            "status": "ok",
            "message": "Nothing new -- all sessions already harvested.",
            "total_seen": len(files),
            "processed": 0,
        })

    known = ", ".join(known_people()) or "(none yet)"
    results = []
    totals = {"tech": 0, "projects": 0, "preferences": 0, "people": 0}

    for path in todo:
        name = os.path.basename(path)
        convo = extract_conversation(path)
        if len(convo) < 400:
            mark_processed(path)
            results.append({"session": name, "skipped": "too short"})
            continue

        prompt = EXTRACT_PROMPT.replace("{known}", known).replace("{convo}", convo)
        try:
            raw = ask_model(prompt)
        except Exception as e:
            log("model error on " + name + ": " + str(e))
            results.append({"session": name, "error": str(e)})
            continue

        data = parse_json_loose(raw)
        if not data:
            mark_processed(path)
            results.append({"session": name, "skipped": "no parseable facts"})
            continue

        counts = {}

        for key, header in (("tech", "TECH"), ("projects", "PROJECTS"),
                            ("preferences", "PREFERENCES")):
            facts = [x for x in data.get(key, []) if isinstance(x, str) and x.strip()]
            facts = dedupe_against(AUTO_FILE, facts)
            n = append_section(AUTO_FILE, header, facts, name)
            counts[key] = n
            totals[key] += n

        people_n = 0
        by_person = {}
        for entry in data.get("people", []):
            if not isinstance(entry, dict):
                continue
            pname = str(entry.get("name", "")).strip().lower()
            pfact = str(entry.get("fact", "")).strip()
            if not pname or not pfact:
                continue
            by_person.setdefault(pname, []).append(pfact)

        for pname, pfacts in by_person.items():
            pfacts = dedupe_against(PENDING_FILE, pfacts)
            people_n += update_person_file(pname, pfacts, name)

        counts["people_queued"] = people_n
        totals["people"] += people_n

        mark_processed(path)
        results.append({"session": name, "extracted": counts})
        log("harvested " + name + " -> " + json.dumps(counts))

    return JSONResponse({
        "status": "ok",
        "processed": len(todo),
        "remaining": max(0, len([f for f in files if not already_processed(f)])),
        "totals": totals,
        "detail": results,
        "note": "People facts are in the review queue. GET /memory/pending to see them.",
    })


@router.get("/memory/pending")
def pending():
    """Show people facts waiting for approval."""
    if not os.path.exists(PENDING_FILE):
        return JSONResponse({"status": "ok", "pending": "", "count": 0})
    content = open(PENDING_FILE).read()
    count = content.count("### PERSON:")
    return JSONResponse({"status": "ok", "count": count, "pending": content[-8000:]})


class ApproveRequest(BaseModel):
    person: str = ""      # approve just this person, or blank for all
    clear: bool = True    # remove approved items from the queue


@router.post("/memory/approve")
def approve(req: ApproveRequest):
    """Move queued people facts into their permanent per-person files."""
    if not os.path.exists(PENDING_FILE):
        return JSONResponse({"status": "ok", "message": "Nothing pending."})

    content = open(PENDING_FILE).read()
    blocks = re.split(r"(?=### PERSON: )", content)
    kept, moved = [], {}

    for block in blocks:
        m = re.match(r"### PERSON: (\w+)", block.strip())
        if not m:
            if block.strip():
                kept.append(block)
            continue
        pname = m.group(1)
        if req.person and pname != req.person.lower().strip():
            kept.append(block)
            continue

        facts = [ln for ln in block.splitlines() if ln.strip().startswith("- ")]
        if not facts:
            continue
        pfile = PEOPLE + "/" + pname + ".md"
        if not os.path.exists(pfile):
            with open(pfile, "w") as f:
                f.write("# " + pname.title() + "\n\n_Auto-built from conversations._\n")
        with open(pfile, "a") as f:
            f.write("\n_added " + today() + "_\n")
            for fact in facts:
                f.write(fact + "\n")
        moved[pname] = moved.get(pname, 0) + len(facts)

    if req.clear:
        with open(PENDING_FILE, "w") as f:
            f.write("".join(kept))

    return JSONResponse({"status": "ok", "approved": moved,
                         "message": "Moved into memory/people/"})


@router.get("/memory/people")
def list_people():
    """List everyone tracked, with their files."""
    out = {}
    for p in sorted(glob.glob(PEOPLE + "/*.md")):
        name = os.path.splitext(os.path.basename(p))[0]
        try:
            out[name] = open(p).read()[:3000]
        except Exception as e:
            out[name] = "(unreadable: " + str(e) + ")"
    return JSONResponse({"status": "ok", "count": len(out), "people": out})


@router.get("/memory/facts")
def get_facts():
    """The auto-appended memory file."""
    if not os.path.exists(AUTO_FILE):
        return JSONResponse({"status": "ok", "facts": "(empty)"})
    return JSONResponse({"status": "ok", "facts": open(AUTO_FILE).read()[-10000:]})


@router.get("/memory/status")
def status():
    raw_files = glob.glob(RAW + "/**/*.jsonl", recursive=True) + glob.glob(RAW + "/**/*.md", recursive=True)
    new = [f for f in raw_files if not already_processed(f)]
    pending_count = 0
    if os.path.exists(PENDING_FILE):
        pending_count = open(PENDING_FILE).read().count("### PERSON:")
    return JSONResponse({
        "status": "ok",
        "sessions_total": len(raw_files),
        "sessions_unprocessed": len(new),
        "people_tracked": known_people(),
        "pending_review": pending_count,
        "auto_facts_bytes": os.path.getsize(AUTO_FILE) if os.path.exists(AUTO_FILE) else 0,
        "model": MODEL,
        "paths": {"raw": RAW, "people": PEOPLE, "facts": FACTS},
    })


@router.get("/memory/context")
def full_context():
    """
    Everything Aubie should know: USER_CONTEXT.md + people + auto facts.
    This is what other parts of the system load for personalization.
    """
    parts = []
    uc = BASE + "/USER_CONTEXT.md"
    if os.path.exists(uc):
        parts.append(open(uc).read())
    for p in sorted(glob.glob(PEOPLE + "/*.md")):
        parts.append(open(p).read())
    if os.path.exists(AUTO_FILE):
        parts.append("# Learned facts\n" + open(AUTO_FILE).read()[-6000:])
    return JSONResponse({"status": "ok", "context": "\n\n---\n\n".join(parts)})

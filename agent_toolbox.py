"""
AUBIEETERNAL -- Agent Toolbox
File: /home/aubieeternal/AUBIEETERNAL/agent_toolbox.py

The dev toolbox. agent.py loads everything in TOOLBOX automatically, so this
file can grow without ever touching the agent loop.

Three kinds of things live here:
  1. Regular tools -- find files, check hardware, talk to the dog, etc.
  2. need_tool     -- the agent reports a capability it wishes it had
  3. create_tool   -- the agent WRITES a new tool into agent_tools/ and it
                      becomes available on the next run

Adding a tool by hand: write a function taking (args, run_id) that returns a
string, then register it in TOOLBOX at the bottom. That's the whole contract.
"""

import os
import re
import json
import glob
import shutil
import subprocess
import datetime

import httpx

BASE = "/home/aubieeternal/AUBIEETERNAL"
MEMORY = "/home/aubieeternal/AUBIEETERNAL_MEMORY"
CUSTOM_DIR = os.path.join(BASE, "agent_tools")
WISHLIST = os.path.join(BASE, "agent_tool_wishlist.md")
DOG = "http://100.66.110.65:8420"
SELF = "http://localhost:8800"

os.makedirs(CUSTOM_DIR, exist_ok=True)


def pick(args, *names, default=""):
    if not isinstance(args, dict):
        return str(args) if args else default
    for n in names:
        if n in args and args[n] not in (None, ""):
            return str(args[n])
    strings = [v for v in args.values() if isinstance(v, str) and v.strip()]
    if len(strings) == 1:
        return strings[0]
    return default


def sh(cmd, timeout=60):
    try:
        r = subprocess.run(["bash", "-c", cmd], capture_output=True,
                           text=True, timeout=timeout)
        out = (r.stdout or "").strip()
        e = (r.stderr or "").strip()
        if e and not out:
            return e[:3000]
        return out[:5000] or "(no output)"
    except subprocess.TimeoutExpired:
        return f"timed out after {timeout}s"
    except Exception as ex:
        return f"failed: {ex}"


def human(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f}{u}"
        n /= 1024
    return f"{n:.1f}PB"


# ── Files & search ─────────────────────────────────────────────
def t_find_files(args, run_id):
    pattern = pick(args, "pattern", "name", "glob", "query")
    path = pick(args, "path", "dir", "directory", default=MEMORY)
    limit = int(args.get("limit", 50) or 50)
    if not pattern:
        return 'need args {"pattern": "*.py", "path": "/some/dir"}'
    return sh(f"find '{path}' -iname '{pattern}' 2>/dev/null | head -{limit}")


def t_find_recent(args, run_id):
    path = pick(args, "path", "dir", default=MEMORY)
    days = int(args.get("days", 7) or 7)
    limit = int(args.get("limit", 40) or 40)
    return sh(f"find '{path}' -type f -mtime -{days} 2>/dev/null | head -{limit}")


def t_find_large(args, run_id):
    path = pick(args, "path", "dir", default=MEMORY)
    limit = int(args.get("limit", 20) or 20)
    return sh(f"find '{path}' -type f -printf '%s %p\\n' 2>/dev/null "
              f"| sort -rn | head -{limit} | awk '{{printf \"%.1f MB  %s\\n\", $1/1048576, $2}}'")


def t_count_files(args, run_id):
    path = pick(args, "path", "dir", "directory", default=MEMORY)
    ext = pick(args, "ext", "extension", "type")
    if ext:
        ext = ext.lstrip(".")
        return sh(f"find '{path}' -type f -iname '*.{ext}' 2>/dev/null | wc -l")
    return sh(f"find '{path}' -type f 2>/dev/null | wc -l")


def t_file_info(args, run_id):
    path = pick(args, "path", "file", "filename")
    if not os.path.exists(path):
        return f"not found: {path}"
    out = [sh(f"stat -c '%n%n  size: %s bytes%n  modified: %y%n  type: %F' '{path}'")]
    out.append(sh(f"file -b '{path}'"))
    return "\n".join(out)


def t_disk_usage(args, run_id):
    path = pick(args, "path", "dir", default=MEMORY)
    depth = int(args.get("depth", 1) or 1)
    return (sh("df -h / | tail -1") + "\n\n" +
            sh(f"du -h --max-depth={depth} '{path}' 2>/dev/null | sort -rh | head -25"))


def t_move_file(args, run_id):
    src = pick(args, "src", "source", "from", "path")
    dst = pick(args, "dst", "dest", "destination", "to")
    if not src or not dst:
        return 'need args {"src": "...", "dst": "..."}'
    if not dst.startswith(("/home/aubieeternal/", "/tmp/")):
        return "refused: destination must be under /home/aubieeternal/ or /tmp/"
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)
        return f"moved {src} -> {dst}"
    except Exception as e:
        return f"move_error: {e}"


def t_copy_file(args, run_id):
    src = pick(args, "src", "source", "from", "path")
    dst = pick(args, "dst", "dest", "destination", "to")
    if not src or not dst:
        return 'need args {"src": "...", "dst": "..."}'
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        return f"copied {src} -> {dst}"
    except Exception as e:
        return f"copy_error: {e}"


def t_make_dir(args, run_id):
    path = pick(args, "path", "dir", "directory")
    if not path.startswith(("/home/aubieeternal/", "/tmp/")):
        return "refused: must be under /home/aubieeternal/ or /tmp/"
    try:
        os.makedirs(path, exist_ok=True)
        return f"created {path}"
    except Exception as e:
        return f"mkdir_error: {e}"


# ── Photos ─────────────────────────────────────────────────────
def t_photo_stats(args, run_id):
    root = os.path.join(MEMORY, "PHOTOS")
    out = ["Photo archive:"]
    out.append(sh(f"find '{root}' -type f 2>/dev/null | wc -l | xargs -I{{}} echo '  {{}} files total'"))
    out.append(sh(f"du -sh '{root}' 2>/dev/null | cut -f1 | xargs -I{{}} echo '  {{}} on disk'"))
    out.append("\nBy year:")
    out.append(sh(f"for d in '{root}'/iCloud/*/; do "
                  f"[ -d \"$d\" ] && echo \"  $(basename $d): $(find \"$d\" -type f | wc -l)\"; done"))
    out.append("\nBy type:")
    out.append(sh(f"find '{root}' -type f 2>/dev/null | sed 's/.*\\.//' | "
                  f"sort | uniq -c | sort -rn | head -8"))
    return "\n".join(out)


def t_photos_in_month(args, run_id):
    year = pick(args, "year", "y")
    month = pick(args, "month", "m")
    root = os.path.join(MEMORY, "PHOTOS", "iCloud")
    if year and month:
        m = month.zfill(2)
        return sh(f"ls -1 '{root}/{year}/{m}' 2>/dev/null | head -60; "
                  f"echo '---'; find '{root}/{year}/{m}' -type f 2>/dev/null | wc -l")
    if year:
        return sh(f"for d in '{root}/{year}'/*/; do "
                  f"[ -d \"$d\" ] && echo \"$(basename $d): $(ls -1 \"$d\" | wc -l)\"; done")
    return 'need args {"year": "2022", "month": "07"}'


# ── System & hardware ──────────────────────────────────────────
def t_system_info(args, run_id):
    parts = [
        "[CPU] " + sh("uptime -p; nproc | xargs -I{} echo '{} cores'"),
        "[RAM] " + sh("free -h | head -2 | tail -1"),
        "[DISK] " + sh("df -h / | tail -1"),
        "[GPU] " + sh("nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,"
                      "memory.used,memory.total --format=csv,noheader 2>/dev/null "
                      "|| echo 'nvidia-smi unavailable'"),
        "[SERVICES] " + sh("systemctl is-active aubie-assistant aubie-mcp 2>/dev/null | tr '\\n' ' '"),
    ]
    return "\n".join(parts)


def t_gpu_status(args, run_id):
    return sh("nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,"
              "memory.used,memory.total,power.draw --format=csv 2>/dev/null "
              "|| echo 'GPU query failed'")


def t_top_processes(args, run_id):
    n = int(args.get("limit", 10) or 10)
    return sh(f"ps aux --sort=-%cpu | head -{n + 1} | awk '{{printf \"%-10s %5s%% %5s%%  %s\\n\", $1,$3,$4,$11}}'")


def t_service_status(args, run_id):
    name = pick(args, "service", "name", "unit", default="aubie-assistant")
    return sh(f"systemctl status {name} --no-pager -n 12 2>&1 | head -20")


def t_ollama_models(args, run_id):
    return sh("ollama list 2>/dev/null")


# ── The dog ────────────────────────────────────────────────────
def t_dog_command(args, run_id):
    cmd = pick(args, "command", "cmd", "action", "say")
    if not cmd:
        return 'need args {"command": "sit"}'
    try:
        with httpx.Client(timeout=15) as c:
            r = c.post(f"{DOG}/dog/command", json={"command": cmd})
        return f"sent '{cmd}' to Aubie: {r.text[:400]}"
    except Exception as e:
        return (f"dog_unreachable: {e}\n"
                "  Aubie is probably powered off or off the Tailscale network.")


def t_dog_status(args, run_id):
    ping = sh("ping -c 1 -W 2 100.66.110.65 >/dev/null 2>&1 && echo ONLINE || echo OFFLINE", 8)
    if "ONLINE" not in ping:
        return "Aubie is OFFLINE (not reachable at 100.66.110.65)"
    try:
        with httpx.Client(timeout=8) as c:
            d = c.get(f"{SELF}/proxy/distance").json()
        return f"Aubie is ONLINE. Distance sensor: {d}"
    except Exception:
        return "Aubie is ONLINE but the sensor endpoint did not respond."


def t_dog_vision(args, run_id):
    try:
        with httpx.Client(timeout=45) as c:
            j = c.post(f"{SELF}/proxy/vision").json()
        return j.get("summary") or f"no summary returned: {str(j)[:300]}"
    except Exception as e:
        return f"vision_error: {e}"


# ── Memory & knowledge ─────────────────────────────────────────
def t_memory_facts(args, run_id):
    p = os.path.join(BASE, "memory", "facts", "auto_facts.md")
    if not os.path.exists(p):
        return "no learned facts yet"
    with open(p) as f:
        return f.read()[-4000:]


def t_who_is(args, run_id):
    name = pick(args, "name", "person", "who").lower().strip()
    if not name:
        return 'need args {"name": "gabriela"}'
    p = os.path.join(BASE, "memory", "people", name + ".md")
    if os.path.exists(p):
        with open(p) as f:
            return f.read()[:3000]
    known = [os.path.basename(x)[:-3]
             for x in glob.glob(os.path.join(BASE, "memory", "people", "*.md"))]
    return f"no file for '{name}'. Known people: {', '.join(known) or '(none)'}"


def t_think(args, run_id):
    """Ask the model a reasoning question with no tools. For planning or summarizing."""
    q = pick(args, "question", "prompt", "query", "task")
    if not q:
        return 'need args {"question": "..."}'
    try:
        with httpx.Client(timeout=120) as c:
            r = c.post("http://localhost:11434/api/generate",
                       json={"model": "qwen2.5:14b", "prompt": q, "stream": False,
                             "options": {"temperature": 0.3, "num_predict": 600}})
        return r.json().get("response", "").strip()[:4000]
    except Exception as e:
        return f"think_error: {e}"


# ── Documents: read the actual records ─────────────────────────
def t_pdf_text(args, run_id):
    """Extract text from a PDF so facts can be read from the real document."""
    path = pick(args, "path", "file", "pdf")
    pages = pick(args, "pages", default="")
    if not os.path.exists(path):
        return f"not found: {path}"
    rng = ""
    if pages and "-" in pages:
        a, b = pages.split("-", 1)
        rng = f"-f {a.strip()} -l {b.strip()}"
    out = sh(f"pdftotext {rng} -layout '{path}' - 2>/dev/null | head -400", 90)
    if not out or out == "(no output)":
        return ("no text layer in this PDF -- it is probably a scan. "
                "Try ocr_image on it, or install poppler-utils: "
                "sudo apt install -y poppler-utils")
    return out[:6000]


def t_ocr_image(args, run_id):
    """OCR a scanned document or a photo of one. For EIN letters, forms, receipts."""
    path = pick(args, "path", "file", "image")
    if not os.path.exists(path):
        return f"not found: {path}"
    check = sh("which tesseract", 10)
    if not check or "tesseract" not in check:
        return ("tesseract is not installed. Install it with:\n"
                "  sudo apt install -y tesseract-ocr poppler-utils")
    if path.lower().endswith(".pdf"):
        out = sh(f"pdftoppm -r 200 -png '{path}' /tmp/ocr_{run_id} && "
                 f"for f in /tmp/ocr_{run_id}*.png; do tesseract \"$f\" - 2>/dev/null; done; "
                 f"rm -f /tmp/ocr_{run_id}*.png", 240)
    else:
        out = sh(f"tesseract '{path}' - 2>/dev/null", 120)
    return (out or "(no text found)")[:6000]


def t_fact_lookup(args, run_id):
    """
    Find a fact and PROVE it. Searches the memory files and the document
    archive, and reports where each candidate answer came from.

    This tool never guesses. If it finds nothing, that is the answer.
    """
    q = pick(args, "query", "question", "fact", "what", "term").strip()
    if not q:
        return 'need args {"query": "EIN number"}'

    # Strip question words so we search for the substantive terms
    stop = {"what", "whats", "what's", "is", "the", "my", "our", "a", "an",
            "of", "for", "number", "do", "i", "have", "was", "are"}
    words = [w for w in re.findall(r"[A-Za-z0-9#_-]+", q) if w.lower() not in stop]
    terms = words or [q]

    findings = []

    # 1. The memory files -- fastest and most trustworthy
    for term in terms[:3]:
        t = term.replace("'", "")
        hits = sh(f"grep -rin --include='*.md' -- '{t}' "
                  f"{BASE}/memory {BASE}/USER_CONTEXT.md 2>/dev/null | head -8", 30)
        if hits and "no " not in hits[:4] and hits != "(no output)":
            findings.append(f"[memory files: '{term}']\n{hits}")

    # 2. Text inside archived documents
    for term in terms[:3]:
        t = term.replace("'", "")
        hits = sh(f"grep -ril --include='*.txt' --include='*.md' --include='*.csv' "
                  f"--include='*.json' -- '{t}' {MEMORY} 2>/dev/null | head -8", 60)
        if hits and hits != "(no output)":
            findings.append(f"[documents containing '{term}']\n{hits}")

    # 3. Filenames -- often the document is named for what it is
    for term in terms[:3]:
        t = term.replace("'", "")
        hits = sh(f"find {MEMORY} -type f -iname '*{t}*' 2>/dev/null | head -8", 45)
        if hits and hits != "(no output)":
            findings.append(f"[files named for '{term}']\n{hits}")

    if not findings:
        return (f"NOT FOUND. Nothing in memory or the archive matches: {q}\n\n"
                "Do not guess or state a value you did not find here. Tell Mateo "
                "it is not in the archive, and suggest where it might be -- a PDF "
                "that needs pdf_text, or a scan that needs ocr_image. "
                "You can list candidate documents with find_files.")

    return (
        "SOURCES FOUND -- report the answer WITH the file it came from.\n"
        "If none of these actually contain the value, say so rather than guessing.\n"
        "For a PDF or image, open it with pdf_text or ocr_image to read the real value.\n\n"
        + "\n\n".join(findings)[:5000]
    )


def t_remember_fact(args, run_id):
    """
    Write a VERIFIED fact into permanent memory, with where it came from.

    Once a fact is here it never needs looking up again -- which is the point.
    Only call this with something actually confirmed from a document, not a guess.
    """
    key = pick(args, "key", "name", "fact", "what").strip()
    value = pick(args, "value", "answer", "result").strip()
    source = pick(args, "source", "from", "where", "citation").strip()

    if not key or not value:
        return 'need args {"key": "school EIN", "value": "...", "source": "path/to/document"}'
    if not source:
        return ("refused: a fact with no source is a guess. Include where you found it "
                "(a file path, a document name, or 'Mateo told me directly').")

    path = os.path.join(BASE, "memory", "facts", "verified_facts.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)

    # don't duplicate
    if os.path.exists(path):
        existing = open(path).read()
        if key.lower() in existing.lower():
            return (f"'{key}' is already recorded. Read it with fact_lookup. "
                    "If it needs updating, tell Mateo rather than writing a second copy.")

    entry = (f"\n## {key}\n"
             f"- **{value}**\n"
             f"- source: {source}\n"
             f"- recorded: {datetime.datetime.now():%Y-%m-%d} (run {run_id})\n")
    with open(path, "a") as f:
        f.write(entry)
    return f"Recorded permanently: {key} = {value}\n  source: {source}\n  file: {path}"


def t_verified_facts(args, run_id):
    path = os.path.join(BASE, "memory", "facts", "verified_facts.md")
    if not os.path.exists(path):
        return "no verified facts recorded yet"
    return open(path).read()[:5000]


# ── Proactive: what's coming up ────────────────────────────────
OBLIGATIONS = os.path.join(BASE, "memory", "obligations.md")

DEFAULT_OBLIGATIONS = """# Recurring obligations

Dates are the usual federal ones and can shift for weekends, holidays, and
extensions. Always confirm with the accountant -- this is a reminder list,
not tax advice.

| when | what | who |
|---|---|---|
| 01-15 | Q4 estimated tax payment | personal |
| 01-31 | 1099s and W-2s issued to recipients | Casa Azul, Vanhorn Org |
| 03-15 | Form 1065 partnership return | Casa Azul Property Solutions |
| 03-15 | Form 1120-S if S-corp | Vanhorn Organization |
| 04-15 | Form 1040 personal return | Matthew Vanhorn |
| 04-15 | Form 1120 if C-corp | Vanhorn Organization |
| 04-15 | Q1 estimated tax payment | personal |
| 05-15 | Form 990 annual return | AUBIEETERNAL Institute (nonprofit) |
| 06-15 | Q2 estimated tax payment | personal |
| 09-15 | Q3 estimated tax payment | personal |
| 12-31 | End of year report and books close | AUBIEETERNAL Institute |
| 12-31 | Gather receipts, mileage, 1098s, Airbnb 1099s | all entities |
"""


def _ensure_obligations():
    if not os.path.exists(OBLIGATIONS):
        os.makedirs(os.path.dirname(OBLIGATIONS), exist_ok=True)
        with open(OBLIGATIONS, "w") as f:
            f.write(DEFAULT_OBLIGATIONS)


def t_upcoming(args, run_id):
    """
    What is coming due. This is how the rig knows to say
    'want me to start gathering your tax information?' before you ask.
    """
    _ensure_obligations()
    days = int(args.get("days", 60) or 60)
    today = datetime.date.today()

    rows = []
    for line in open(OBLIGATIONS):
        m = re.match(r"\|\s*(\d{2})-(\d{2})\s*\|\s*([^|]+)\|\s*([^|]+)\|", line)
        if not m:
            continue
        mo, da, what, who = int(m.group(1)), int(m.group(2)), m.group(3).strip(), m.group(4).strip()
        for year in (today.year, today.year + 1):
            try:
                d = datetime.date(year, mo, da)
            except ValueError:
                continue
            delta = (d - today).days
            if 0 <= delta <= days:
                rows.append((delta, d, what, who))
                break

    if not rows:
        return f"Nothing due in the next {days} days."

    rows.sort()
    out = [f"Coming up in the next {days} days (today is {today:%B %d, %Y}):"]
    for delta, d, what, who in rows:
        when = "TODAY" if delta == 0 else f"in {delta} days"
        out.append(f"  {d:%b %d} ({when}) -- {what}  [{who}]")
    out.append("\nThese are the usual federal dates. Confirm specifics with the accountant.")
    return "\n".join(out)


def t_prep_checklist(args, run_id):
    """What documents exist already for a given filing, and what's missing."""
    what = pick(args, "for", "filing", "what", "entity", default="tax")
    tax_dir = os.path.join(MEMORY, "TAX")
    year = pick(args, "year", default=str(datetime.date.today().year - 1))

    found = sh(f"find '{tax_dir}' -type f -iname '*{year}*' 2>/dev/null | head -40", 60)
    folders = sh(f"ls -1 '{tax_dir}' 2>/dev/null", 20)
    return (f"Preparing: {what} for {year}\n\n"
            f"Categories in the archive:\n{folders}\n\n"
            f"Documents already filed for {year}:\n{found}\n\n"
            "Compare this against what the filing needs and tell Mateo what is missing.")


# ── Eyes: look at an image and describe it ─────────────────────
VISION_MODEL = "qwen2.5vl:7b"


def _ask_vision(image_b64: str, question: str, timeout: int = 180) -> str:
    payload = {
        "model": VISION_MODEL,
        "prompt": question,
        "images": [image_b64],
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 700},
    }
    with httpx.Client(timeout=timeout) as c:
        r = c.post("http://localhost:11434/api/generate", json=payload)
    return r.json().get("response", "").strip()


def t_look_at(args, run_id):
    """
    Look at an image file and answer a question about it.

    This is how the rig diagnoses hardware from a photo -- a picture of a
    striped display or a tangle of jumper wires says more than a paragraph
    of description.
    """
    path = pick(args, "path", "image", "file", "photo")
    question = pick(args, "question", "prompt", "ask", "about",
                    default="Describe what you see in detail.")
    if not path:
        return 'need args {"path": "<image file>", "question": "..."}'
    if not os.path.exists(path):
        return f"not found: {path}"

    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
    except Exception as e:
        return f"could not read image: {e}"

    try:
        answer = _ask_vision(b64, question)
    except Exception as e:
        return (f"vision_error: {e}\n"
                f"  Is {VISION_MODEL} installed? Check with: ollama list")
    return answer or "(the vision model returned nothing)"


def t_diagnose_photo(args, run_id):
    """
    Look at a photo of hardware and work out what is wrong.
    Built for exactly the case where a display shows something odd and
    describing it in words is harder than showing it.
    """
    path = pick(args, "path", "image", "file", "photo")
    context = pick(args, "context", "details", "setup", default="")
    if not path or not os.path.exists(path):
        return f'need a real image path. Got: "{path}"'

    prompt = (
        "You are looking at a photo of an electronics project that is not working.\n"
        "Describe precisely what the display or components are doing -- colours, "
        "patterns, stripes, blank areas, LEDs lit or dark, how wires are connected.\n"
        "Then give the two or three most likely causes, most likely first.\n"
        "Be specific and technical. Do not guess wildly.\n"
    )
    if context:
        prompt += f"\nWhat the owner says about the setup:\n{context}\n"

    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return _ask_vision(b64, prompt)
    except Exception as e:
        return f"vision_error: {e}"


def t_dog_look_smart(args, run_id):
    """
    Take a photo through the dog's camera and describe it with the vision
    model -- open-ended, unlike dog_vision which only runs object detection.
    """
    question = pick(args, "question", "ask", "prompt",
                    default="Describe what you see in detail.")
    try:
        with httpx.Client(timeout=45) as c:
            j = c.post(f"{SELF}/proxy/vision").json()
        b64 = j.get("snapshot_b64")
        if not b64:
            return "no image came back from the dog. Is Aubie online and the camera working?"
    except Exception as e:
        return f"camera_error: {e}"

    try:
        return _ask_vision(b64, question)
    except Exception as e:
        return f"vision_error: {e}"


def t_vision_status(args, run_id):
    models = sh("ollama list 2>/dev/null", 15)
    installed = VISION_MODEL.split(":")[0] in models
    return (f"Vision model: {VISION_MODEL}\n"
            f"Installed: {'YES' if installed else 'NO'}\n\n"
            f"Models available:\n{models}")


# ── Code health ────────────────────────────────────────────────
def t_audit_wiring(args, run_id):
    """
    Cross-check the codebase for things defined but never connected --
    routers that are never included, endpoints the UI calls that do not
    exist, and endpoints that exist but nothing ever calls.
    """
    report = []

    server = os.path.join(BASE, "assistant_server.py")
    imported = set(re.findall(r"from\s+(\w+)\s+import\s+router", sh(f"cat '{server}'", 30)))
    included = set(re.findall(r"include_router\((\w+)_router\)", sh(f"cat '{server}'", 30)))
    included_mods = {m for m in imported
                     if any(m.startswith(i) or i.startswith(m.split('_')[0])
                            for i in included)}
    orphan_imports = imported - included_mods
    if orphan_imports:
        report.append("ROUTERS IMPORTED BUT MAYBE NOT INCLUDED:\n  " +
                      ", ".join(sorted(orphan_imports)))

    # Endpoints the backend defines
    defined = set()
    for f in glob.glob(os.path.join(BASE, "*.py")):
        for m in re.findall(r'@router\.(?:get|post|put|delete)\(\s*["\']([^"\']+)',
                            open(f, errors="ignore").read()):
            defined.add(m.split("{")[0].rstrip("/"))

    # Endpoints the phone UI actually calls
    called = set()
    ui = os.path.join(BASE, "phone_ui.py")
    if os.path.exists(ui):
        text = open(ui, errors="ignore").read()
        for m in re.findall(r"fetch\(\s*['\"]([^'\"]+)", text):
            called.add(m.split("?")[0].split("{")[0].rstrip("/"))

    missing = {c for c in called
               if c.startswith("/") and not any(c.startswith(d) for d in defined if d)}
    if missing:
        report.append("UI CALLS ENDPOINTS THAT MAY NOT EXIST:\n  " +
                      "\n  ".join(sorted(missing)))

    unused = {d for d in defined
              if d.startswith("/proxy") and not any(d in c for c in called)}
    if unused:
        report.append("BACKEND ENDPOINTS NOTHING CALLS:\n  " +
                      "\n  ".join(sorted(unused)))

    # Buttons whose handler is missing
    if os.path.exists(ui):
        text = open(ui, errors="ignore").read()
        handlers = set(re.findall(r"function\s+(\w+)\s*\(", text))
        clicks = set(re.findall(r'onclick="(\w+)\(', text))
        broken = clicks - handlers - {"cmd"}
        if broken:
            report.append("BUTTONS WITH NO JS FUNCTION:\n  " + ", ".join(sorted(broken)))

    report.append(f"\nCounted {len(defined)} endpoints defined, {len(called)} called by the UI.")
    return "\n\n".join(report) if report else "No wiring problems detected."


def t_find_grants(args, run_id):
    """Search the web for grants. Slow -- it drives a real browser."""
    focus = pick(args, "focus", "topic", "query", "for",
                 default="nonprofit STEM education robotics school")
    task = (f"Find current open grant opportunities for a nonprofit school focused on "
            f"{focus}. Look at grants.gov, candid.org, and foundation sites. For each one "
            f"report: the grant name, who funds it, the amount, the deadline, and the "
            f"application URL. Only report grants that are currently open.")
    try:
        with httpx.Client(timeout=280) as c:
            r = c.post(f"{SELF}/browse", json={"task": task})
        return str(r.json().get("result", ""))[:5000]
    except Exception as e:
        return f"grant_search_error: {e} (browsing is slow; try again or narrow the focus)"


# ── Arduino / the sketch on the dog ────────────────────────────
# The sketch lives on Aubie, not Ryzen, so these SSH across.
DOG_SSH = ("ssh -i /home/aubieeternal/.ssh/aubie_key "
           "-o StrictHostKeyChecking=no -o ConnectTimeout=8 arduino@100.66.110.65")
SKETCH_DIR = "~/spotmicro_dog/sketch"
SKETCH = SKETCH_DIR + "/sketch.ino"
FQBN = "arduino:zephyr:unoq"
PORT = "/dev/ttyHS1"


def dog_ssh(cmd, timeout=180):
    safe = cmd.replace("'", "'\\''")
    return sh(f"{DOG_SSH} '{safe}'", timeout)


# Canonical copy kept on Ryzen so the sketch survives the dog being off,
# and can be read or edited without the dog online.
LOCAL_SKETCH_DIR = BASE + "/dog_sketch"
LOCAL_SKETCH = LOCAL_SKETCH_DIR + "/sketch.ino"


def t_sketch_pull(args, run_id):
    """
    Copy the dog's sketch to Ryzen. Run this whenever the dog is online --
    it keeps a versioned local copy so the firmware is never only on the dog.
    """
    os.makedirs(LOCAL_SKETCH_DIR, exist_ok=True)

    out = sh(f"scp -i /home/aubieeternal/.ssh/aubie_key -o StrictHostKeyChecking=no "
             f"-o ConnectTimeout=8 arduino@100.66.110.65:{SKETCH} {LOCAL_SKETCH}", 90)

    if not os.path.exists(LOCAL_SKETCH):
        return ("dog_unreachable: could not pull the sketch. Is Aubie powered on "
                "and on Tailscale?\n  " + out)

    # keep a timestamped history so nothing is ever overwritten permanently
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    hist = f"{LOCAL_SKETCH_DIR}/history/sketch_{stamp}.ino"
    os.makedirs(os.path.dirname(hist), exist_ok=True)
    shutil.copy2(LOCAL_SKETCH, hist)

    lines = sum(1 for _ in open(LOCAL_SKETCH, errors="ignore"))
    size = os.path.getsize(LOCAL_SKETCH)
    return (f"Pulled the dog's sketch to Ryzen.\n"
            f"  {LOCAL_SKETCH}  ({lines} lines, {size} bytes)\n"
            f"  history copy: {hist}\n"
            "It can now be read and edited even when Aubie is offline.")


def t_sketch_push(args, run_id):
    """Send the Ryzen copy back to the dog. Backs up the dog's version first."""
    if not os.path.exists(LOCAL_SKETCH):
        return f"no local sketch at {LOCAL_SKETCH}. Run sketch_pull first."

    t_sketch_backup({}, run_id)   # snapshot whatever is on the dog

    out = sh(f"scp -i /home/aubieeternal/.ssh/aubie_key -o StrictHostKeyChecking=no "
             f"-o ConnectTimeout=8 {LOCAL_SKETCH} arduino@100.66.110.65:{SKETCH}", 90)
    if "No route" in out or "timed out" in out or "refused" in out.lower():
        return "dog_unreachable: could not push. Is Aubie online?\n  " + out
    return ("Pushed the Ryzen copy to the dog (its previous version was backed up).\n"
            "Next: sketch_compile, then sketch_upload.")


def t_sketch_local(args, run_id):
    """Read the Ryzen copy of the sketch. Works with the dog powered off."""
    if not os.path.exists(LOCAL_SKETCH):
        return (f"no local copy yet at {LOCAL_SKETCH}.\n"
                "Run sketch_pull while the dog is online to create one.")
    start = int(args.get("start", 1) or 1)
    lines = int(args.get("lines", 400) or 400)
    with open(LOCAL_SKETCH, errors="ignore") as f:
        all_lines = f.readlines()
    chunk = all_lines[start - 1: start - 1 + lines]
    return (f"[Ryzen copy, {len(all_lines)} lines total]\n" + "".join(chunk))[:6000]


def t_sketch_read(args, run_id):
    """Read the sketch running on the dog. Use grep_sketch for a big file."""
    lines = int(args.get("lines", 400) or 400)
    start = int(args.get("start", 1) or 1)
    out = dog_ssh(f"sed -n '{start},{start + lines - 1}p' {SKETCH}", 60)
    if "Connection" in out or "timed out" in out:
        return ("dog_unreachable: cannot read the sketch, Aubie is offline.\n"
                "  The sketch lives on the dog at " + SKETCH)
    return out


def t_grep_sketch(args, run_id):
    pattern = pick(args, "pattern", "text", "query", "search")
    if not pattern:
        return 'need args {"pattern": "drawFace"}'
    p = pattern.replace("'", "")
    return dog_ssh(f"grep -n '{p}' {SKETCH} | head -50", 60)


def t_sketch_functions(args, run_id):
    """List the functions in the sketch -- a fast way to learn its structure."""
    return dog_ssh(
        "grep -nE '^[a-zA-Z_][a-zA-Z0-9_<>: ]*\\**[a-zA-Z_][a-zA-Z0-9_]*\\s*\\(' "
        + SKETCH + " | head -60", 60)


def t_sketch_backup(args, run_id):
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return dog_ssh(f"cp {SKETCH} {SKETCH}.bak_{stamp} && "
                   f"echo 'backed up to sketch.ino.bak_{stamp}'", 60)


def t_sketch_write(args, run_id):
    """
    Replace the whole sketch. Always backs up first.
    For a small change, prefer sketch_patch.
    """
    content = pick(args, "content", "code", "sketch", "source")
    if not content:
        return 'need args {"content": "<full sketch source>"}'
    if len(content) < 100:
        return "refused: that is too short to be a whole sketch. Use sketch_patch instead."

    t_sketch_backup({}, run_id)
    local = f"/tmp/sketch_{run_id}.ino"
    try:
        with open(local, "w") as f:
            f.write(content)
    except Exception as e:
        return f"could not stage the sketch: {e}"

    out = sh(f"scp -i /home/aubieeternal/.ssh/aubie_key -o StrictHostKeyChecking=no "
             f"{local} arduino@100.66.110.65:{SKETCH}", 90)
    os.unlink(local)
    return f"wrote {len(content)} bytes to the sketch (backup made). {out}"


def t_sketch_patch(args, run_id):
    """Replace one exact block of text in the sketch. Safer than a full rewrite."""
    old = pick(args, "old", "find", "target", "old_text")
    new = pick(args, "new", "replace", "new_text", "replacement")
    if not old:
        return 'need args {"old": "<exact text to replace>", "new": "<replacement>"}'

    t_sketch_backup({}, run_id)
    payload = json.dumps({"old": old, "new": new})
    local = f"/tmp/patch_{run_id}.json"
    with open(local, "w") as f:
        f.write(payload)

    sh(f"scp -i /home/aubieeternal/.ssh/aubie_key -o StrictHostKeyChecking=no "
       f"{local} arduino@100.66.110.65:/tmp/patch.json", 60)
    os.unlink(local)

    script = (
        "import json;"
        "d=json.load(open('/tmp/patch.json'));"
        f"p='{SKETCH}'.replace('~','/home/arduino');"
        "s=open(p).read();"
        "n=s.count(d['old']);"
        "print('occurrences:',n);"
        "s=s.replace(d['old'],d['new'],1) if n else s;"
        "open(p,'w').write(s);"
        "print('patched' if n else 'NOT FOUND - text did not match exactly')"
    )
    return dog_ssh(f'python3 -c "{script}"', 60)


def t_sketch_compile(args, run_id):
    """
    Compile the sketch on the dog and return the compiler output verbatim.
    Errors come back exactly as gcc reports them, so they can be read and fixed.
    """
    out = dog_ssh(f"cd ~ && arduino-cli compile --fqbn {FQBN} {SKETCH_DIR} 2>&1 | tail -40", 300)
    if not out or out == "(no output)":
        return "compile produced no output -- the dog may be unreachable"
    if "error" in out.lower():
        return "COMPILE FAILED:\n" + out + "\n\nRead the error above and fix the sketch."
    return "COMPILE OK\n" + out


def t_sketch_upload(args, run_id):
    """Upload the compiled sketch. Compile first -- this does not check."""
    out = dog_ssh(f"cd ~ && arduino-cli upload --fqbn {FQBN} -p {PORT} {SKETCH_DIR} 2>&1 | tail -25", 300)
    if "error" in out.lower() or "fail" in out.lower():
        return "UPLOAD FAILED:\n" + out
    return "UPLOAD OK -- the dog is running the new sketch.\n" + out


def t_sketch_restore(args, run_id):
    """Roll back to the most recent backup."""
    return dog_ssh(
        f"ls -t {SKETCH}.bak_* 2>/dev/null | head -1 | "
        f"xargs -I{{}} sh -c 'cp {{}} {SKETCH} && echo restored from {{}}'", 60)


# ── Self-extension ─────────────────────────────────────────────
def t_need_tool(args, run_id):
    """
    The agent noticed a capability gap. Log it so Mateo sees it, and tell the
    agent to work around it for now.
    """
    name = pick(args, "name", "tool", "tool_name")
    why = pick(args, "why", "reason", "description", "purpose")
    if not name and not why:
        return 'need args {"name": "pdf_read", "why": "to extract text from PDFs"}'

    entry = (f"\n## {name or '(unnamed)'}\n"
             f"- requested: {datetime.datetime.now():%Y-%m-%d %H:%M}\n"
             f"- run: {run_id}\n"
             f"- why: {why}\n")
    try:
        with open(WISHLIST, "a") as f:
            f.write(entry)
    except Exception:
        pass

    return (f"Noted. '{name}' has been added to the tool wishlist at {WISHLIST}, "
            "and Mateo will see it.\n"
            "For now, work around it: the shell and python tools can do almost "
            "anything a missing tool would. Continue with those.")


def t_create_tool(args, run_id):
    """
    The agent writes a genuinely new tool for itself.

    Saved into agent_tools/ and loaded on the NEXT run (not this one), so a
    broken tool can never take down the run that wrote it. Everything here is
    reviewable and deletable -- it's one plain .py file per tool.
    """
    name = re.sub(r"[^a-z0-9_]", "", pick(args, "name", "tool_name").lower())
    desc = pick(args, "description", "desc", "why")
    code = pick(args, "code", "source", "body", "function")

    if not name:
        return 'need args {"name": "...", "description": "...", "code": "..."}'
    if not code:
        return ('need the code. Write a function exactly like this:\n\n'
                'def run(args, run_id):\n'
                '    import subprocess\n'
                '    target = args.get("path", "/tmp")\n'
                '    return subprocess.run(["ls", target], capture_output=True,\n'
                '                          text=True).stdout\n\n'
                'It must be named run, take (args, run_id), and return a string.')

    if "def run(" not in code:
        return "the code must define a function named exactly: def run(args, run_id):"

    for bad in ("rm -rf /", "mkfs", "shutdown", "os.system('rm", "__import__('os').system"):
        if bad in code:
            return f"refused: the code contains '{bad}'"

    path = os.path.join(CUSTOM_DIR, name + ".py")
    header = (f'"""\n{desc}\n\nWritten by the agent during run {run_id} '
              f'on {datetime.datetime.now():%Y-%m-%d %H:%M}.\n"""\n\n'
              f'DESCRIPTION = {json.dumps(desc or name)}\n\n')
    try:
        with open(path, "w") as f:
            f.write(header + code + "\n")
    except Exception as e:
        return f"could not write tool: {e}"

    # syntax check before we claim success
    check = subprocess.run(["python3", "-m", "py_compile", path],
                           capture_output=True, text=True)
    if check.returncode != 0:
        os.rename(path, path + ".broken")
        return (f"the tool has a syntax error, so it was not installed:\n"
                f"{check.stderr[:600]}\nFix it and call create_tool again.")

    return (f"Created tool '{name}' at {path}.\n"
            "It will be available on your NEXT run, not this one. "
            "Finish the current task using existing tools.")


def t_list_custom_tools(args, run_id):
    files = sorted(glob.glob(os.path.join(CUSTOM_DIR, "*.py")))
    if not files:
        return "no custom tools have been created yet"
    out = []
    for p in files:
        n = os.path.basename(p)[:-3]
        desc = ""
        try:
            with open(p) as f:
                for line in f:
                    if line.startswith("DESCRIPTION"):
                        desc = line.split("=", 1)[1].strip().strip('"')
                        break
        except Exception:
            pass
        out.append(f"  {n}: {desc}")
    return "Custom tools:\n" + "\n".join(out)


# ── Registry ───────────────────────────────────────────────────
TOOLBOX = {
    # files
    "find_files":    (t_find_files, 'args {"pattern": "*.heic", "path": "<dir>", "limit": 50} -- find files by name'),
    "find_recent":   (t_find_recent, 'args {"path": "<dir>", "days": 7} -- files changed recently'),
    "find_large":    (t_find_large, 'args {"path": "<dir>", "limit": 20} -- biggest files, sorted'),
    "count_files":   (t_count_files, 'args {"path": "<dir>", "ext": "heic"} -- count files, optionally by extension'),
    "file_info":     (t_file_info, 'args {"path": "<file>"} -- size, dates, and type of one file'),
    "disk_usage":    (t_disk_usage, 'args {"path": "<dir>", "depth": 1} -- what is taking up space'),
    "move_file":     (t_move_file, 'args {"src": "...", "dst": "..."}'),
    "copy_file":     (t_copy_file, 'args {"src": "...", "dst": "..."}'),
    "make_dir":      (t_make_dir, 'args {"path": "..."}'),

    # photos
    "photo_stats":   (t_photo_stats, 'no args -- totals, size, breakdown by year and file type'),
    "photos_in":     (t_photos_in_month, 'args {"year": "2022", "month": "07"} -- what is in a given month'),

    # system
    "system_info":   (t_system_info, 'no args -- CPU, RAM, disk, GPU, services, all at once'),
    "gpu_status":    (t_gpu_status, 'no args -- GPU temp, utilization, memory'),
    "top_processes": (t_top_processes, 'args {"limit": 10} -- what is using the CPU'),
    "service_status":(t_service_status, 'args {"service": "aubie-assistant"} -- systemd status and recent log'),
    "ollama_models": (t_ollama_models, 'no args -- which local models are installed'),

    # the dog
    "dog_command":   (t_dog_command, 'args {"command": "sit"} -- send a command to the robot dog'),
    "dog_status":    (t_dog_status, 'no args -- is Aubie online, and its distance sensor'),
    "dog_vision":    (t_dog_vision, 'no args -- what the dog can see right now (slow, ~15s)'),

    # truth & documents
    "fact_lookup":   (t_fact_lookup, 'args {"query": "EIN"} -- find a fact AND its source. '
                                     'Never guess a value. If this returns NOT FOUND, say so.'),
    "remember_fact": (t_remember_fact,
                      'args {"key": "school EIN", "value": "...", "source": "where it came from"} '
                      '-- write a verified fact into permanent memory so it never needs re-checking. '
                      'Requires a source. Never record a guess.'),
    "verified_facts":(t_verified_facts, 'no args -- every fact confirmed so far, with sources'),

    # proactive
    "upcoming":      (t_upcoming, 'args {"days": 60} -- filings and deadlines coming due. '
                                  'Use this to offer help before Mateo asks.'),
    "prep_checklist":(t_prep_checklist, 'args {"for": "1065", "year": "2025"} -- what tax documents '
                                        'already exist in the archive and what is missing'),
    "pdf_text":      (t_pdf_text, 'args {"path": "<pdf>", "pages": "1-3"} -- read text out of a PDF'),
    "ocr_image":     (t_ocr_image, 'args {"path": "<image or scanned pdf>"} -- OCR a photo of a document'),

    # eyes
    "look_at":       (t_look_at, 'args {"path": "<image file>", "question": "..."} -- '
                                 'LOOK AT AN IMAGE and answer a question about it. '
                                 'Use this whenever Mateo mentions a photo or screenshot.'),
    "diagnose_photo":(t_diagnose_photo, 'args {"path": "<image>", "context": "what the setup is"} -- '
                                        'look at a photo of broken hardware and say what is likely wrong'),
    "dog_look_smart":(t_dog_look_smart, 'args {"question": "..."} -- take a photo through the dog\'s '
                                        'camera and describe it. Open-ended, unlike dog_vision.'),
    "vision_status": (t_vision_status, 'no args -- is the vision model installed'),

    # code health
    "audit_wiring":  (t_audit_wiring, 'no args -- find endpoints, routers, and buttons that are '
                                      'defined but not connected to anything'),
    "find_grants":   (t_find_grants, 'args {"focus": "..."} -- search the web for open grants. Slow.'),

    # knowledge
    "memory_facts":  (t_memory_facts, 'no args -- what the rig has learned about Mateo'),
    "who_is":        (t_who_is, 'args {"name": "gabriela"} -- look up a person'),
    "think":         (t_think, 'args {"question": "..."} -- reason about something without running anything'),

    # the sketch on the dog (TFT face, servos, everything)
    "sketch_pull":     (t_sketch_pull, 'no args -- copy the dog\'s sketch to Ryzen and save a timestamped '
                                       'history copy. Do this whenever Aubie is online.'),
    "sketch_push":     (t_sketch_push, 'no args -- send the Ryzen copy back to the dog. Backs up the '
                                       'dog\'s version first. Follow with sketch_compile and sketch_upload.'),
    "sketch_local":    (t_sketch_local, 'args {"start": 1, "lines": 400} -- read the RYZEN copy. '
                                        'Works when the dog is powered off. Try this before sketch_read.'),
    "sketch_read":     (t_sketch_read, 'args {"start": 1, "lines": 400} -- read the sketch live from Aubie. '
                                       'Needs the dog online -- use sketch_local if it is off.'),
    "grep_sketch":     (t_grep_sketch, 'args {"pattern": "drawFace"} -- find something inside the sketch'),
    "sketch_functions":(t_sketch_functions, 'no args -- list the functions in the sketch, fastest way to learn its shape'),
    "sketch_patch":    (t_sketch_patch, 'args {"old": "<exact text>", "new": "<replacement>"} -- '
                                        'change one block. Backs up first. Preferred over sketch_write.'),
    "sketch_write":    (t_sketch_write, 'args {"content": "<whole sketch>"} -- full rewrite. Backs up first.'),
    "sketch_compile":  (t_sketch_compile, 'no args -- compile on the dog. Returns compiler errors verbatim so you can fix them.'),
    "sketch_upload":   (t_sketch_upload, 'no args -- flash the compiled sketch to Aubie. Compile first.'),
    "sketch_backup":   (t_sketch_backup, 'no args -- snapshot the sketch before risky changes'),
    "sketch_restore":  (t_sketch_restore, 'no args -- roll back to the newest backup'),

    # self-extension
    "need_tool":     (t_need_tool, 'args {"name": "...", "why": "..."} -- USE THIS when you lack a capability. '
                                   'It logs the gap for Mateo instead of you retrying a tool that cannot work.'),
    "create_tool":   (t_create_tool, 'args {"name": "...", "description": "...", "code": "def run(args, run_id): ..."} '
                                     '-- write a brand new tool for yourself. Available next run.'),
    "list_custom_tools": (t_list_custom_tools, 'no args -- tools you have written previously'),
}


def load_custom_tools():
    """Pull in anything the agent has written into agent_tools/."""
    out = {}
    import importlib.util
    for path in sorted(glob.glob(os.path.join(CUSTOM_DIR, "*.py"))):
        name = os.path.basename(path)[:-3]
        try:
            spec = importlib.util.spec_from_file_location("agenttool_" + name, path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "run"):
                desc = getattr(mod, "DESCRIPTION", f"custom tool: {name}")
                out[name] = (mod.run, f"[custom] {desc}")
        except Exception:
            continue
    return out


def all_tools():
    merged = dict(TOOLBOX)
    merged.update(load_custom_tools())
    return merged

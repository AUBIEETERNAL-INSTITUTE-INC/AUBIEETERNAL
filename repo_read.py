"""Read-only repo access for the assistant. No writes."""
import os
import subprocess

ROOT = os.path.realpath(os.environ.get("AUBIE_REPO_ROOT", "/home/aubieeternal/AUBIEETERNAL"))
EXTRA_ROOTS = [os.path.realpath("/home/aubieeternal/aubie-it-discord")]
ROOTS = [ROOT] + [r for r in EXTRA_ROOTS if os.path.isdir(r)]
MAX_BYTES = 24000
SKIP = {".git", "venv", ".venv", "__pycache__", "node_modules", "aubie_storage", ".env"}

def _safe(path: str) -> str:
    raw = path.lstrip("/")
    bases = list(ROOTS) + ["/home/aubieeternal"]
    candidates = [os.path.realpath(raw if os.path.isabs(path) else os.path.join(base, raw)) for base in bases]
    for full in candidates:
        for root in ROOTS:
            if (full == root or full.startswith(root + os.sep)) and os.path.exists(full):
                return full
    for full in candidates:
        for root in ROOTS:
            if full == root or full.startswith(root + os.sep):
                return full
    raise ValueError("path escapes allowed roots")

def list_tree(subpath: str = "", max_entries: int = 200) -> str:
    base = _safe(subpath or ".")
    out = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in SKIP and not d.startswith(".")]
        for name in filenames:
            if name.startswith(".env"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, name), ROOT)
            out.append(rel)
            if len(out) >= max_entries:
                return "\n".join(out) + "\n...truncated"
    return "\n".join(out) or "(empty)"

def read_file(path: str, start_line: int = 1, end_line: int = 200) -> str:
    full = _safe(path)
    with open(full, "r", errors="replace") as f:
        lines = f.readlines()
    start = max(1, start_line)
    end = min(len(lines), end_line)
    chunk = "".join(f"{i}|{lines[i-1]}" for i in range(start, end + 1))
    return chunk[:MAX_BYTES]

def grep(pattern: str, subpath: str = ".") -> str:
    base = _safe(subpath)
    result = subprocess.run(
        ["grep", "-R", "-n", "-F", "--binary-files=without-match",
         "--exclude-dir=venv", "--exclude-dir=.git", pattern, base],
        capture_output=True, text=True, timeout=20,
    )
    return (result.stdout or "(no matches)")[:MAX_BYTES]


def code_context(user_msg: str) -> str:
    """Best-effort read-only context. Empty string means skip the loop."""
    import re
    text = user_msg or ""
    low = text.lower()
    marks = ("code", "repo", "file", ".py", "on the rig", "assistant_server", "def ", "class ")
    if not any(m in low for m in marks):
        return ""
    names = re.findall(r"[\w./-]+\.py\b", text)
    chunks = []
    for name in names[:2]:
        try:
            body = read_file(name, 1, 80)
            hits = grep("def chat", name) + "\n" + grep("qwen2.5:14b", name)
            chunks.append(name + "\n" + body + "\n\n" + hits)
        except Exception as exc:
            chunks.append(name + "\n(read failed: " + str(exc) + ")")
    if not chunks:
        term = ""
        quoted = re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", text)
        if quoted:
            term = quoted[-1]
        try:
            chunks.append(grep(term) if term else list_tree("", 80))
        except Exception as exc:
            chunks.append("(lookup failed: " + str(exc) + ")")
    return "\n\n".join(chunks)[:24000]


def find_name(name: str, max_hits: int = 20) -> str:
    """Return paths whose filename matches, under the allowed roots only."""
    want = (name or "").strip().lower().replace("\\", "/").split("/")[-1]
    if not want or want in {".", ".."} or "/" in want or ".." in want:
        return "(none)"
    hits = []
    for root in ROOTS:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP and not d.startswith(".")]
            for filename in filenames:
                if filename.lower() == want or want in filename.lower():
                    hits.append(os.path.relpath(os.path.join(dirpath, filename), "/home/aubieeternal"))
                    if len(hits) >= max_hits:
                        return "\n".join(hits) + "\n...truncated"
    return "\n".join(hits) or "(none)"

def run_request(line: str) -> str:
    parts = (line or "").strip().split()
    if not parts:
        return "(rejected)"
    cmd = parts[0].upper()
    if cmd == "FIND" and len(parts) >= 2:
        return find_name(parts[1])
    if cmd == "GREP" and len(parts) == 3:
        return grep(parts[1], parts[2])
    if cmd == "READ" and len(parts) >= 2:
        start = int(parts[2]) if len(parts) >= 4 and parts[2].isdigit() else 1
        end = int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else start + 40
        if end < start or end - start > 200:
            return "(rejected: max 200 lines)"
        try:
            return read_file(parts[1], start, end)
        except Exception:
            found = find_name(parts[1])
            first = found.splitlines()[0] if found and found != "(none)" else ""
            if not first:
                return "(none)"
            return first + "\n" + read_file(first, start, end)
    return "(rejected)"

# READ falls back to search

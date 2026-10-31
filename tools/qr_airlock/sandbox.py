"""QR Airlock phase 2 - throwaway sandbox link check ("quarantine fetch", README: Not built).

    from qr_airlock import sandbox
    rep = sandbox.check_url("https://example.com")     # blocking, ~3-18 s

Only call this after an explicit user tap. One run at a time (callers should also heat-gate).

Isolation (no sudo, no daemon):
  * bubblewrap jail: new user/pid/net/ipc/uts/cgroup namespaces, --die-with-parent, caps dropped,
    read-only /usr + fonts + the Playwright package/browser, tmpfs $HOME and /tmp (fresh profile,
    no cookies/logins, nothing persists - the jail's files vanish on exit), env cleared.
  * no network inside the jail at all (empty netns). Its only exit is a unix socket to the
    egress proxy below; the rig's real 127.0.0.1, LAN, tailnet and abstract sockets are unreachable.
  * egress proxy (this process): CONNECT/HTTP to port 80/443 only; resolves DNS itself and refuses
    any name that resolves to a non-global address (loopback, RFC1918 192.168/10/172.16, 100.64/10
    tailnet/CGNAT, link-local, ULA fd7a:... etc.), then dials the vetted IP (no DNS rebinding).
  * downloads are refused by the browser (never saved, never executed); time budget ~15 s,
    hard kill at ~22 s; optional systemd --user scope with memory/CPU/task caps.
"""
from __future__ import annotations
import ipaddress, json, os, re, shutil, socket, subprocess, tempfile, threading, time
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
WORKER = HERE / "sandbox_worker.py"
SITE = Path.home() / ".local" / "lib" / "python3.14" / "site-packages"
BROWSERS = Path.home() / ".cache" / "ms-playwright"
BUDGET_S = 15
HARD_KILL_S = 22
ALLOWED_PORTS = {80, 443}
MAX_BYTES = 40_000_000          # per run, both directions
MAX_CONNS = 300

_run_lock = threading.Lock()

# ---------------------------------------------------------------- address policy
def ip_allowed(ip: str) -> tuple[bool, str]:
    try:
        a = ipaddress.ip_address(ip.split("%", 1)[0])
    except ValueError:
        return False, "not an IP"
    if isinstance(a, ipaddress.IPv6Address) and a.ipv4_mapped:
        a = a.ipv4_mapped
    if a.is_loopback: return False, "loopback (the rig itself)"
    if a in ipaddress.ip_network("100.64.0.0/10"): return False, "tailnet / CGNAT 100.64/10"
    if a.is_private: return False, "private / LAN address"
    if a.is_link_local: return False, "link-local"
    if a.is_multicast or a.is_reserved or a.is_unspecified: return False, "reserved"
    if not a.is_global: return False, "not a public address"
    return True, ""

def resolve_public(host: str, port: int) -> tuple[str | None, str]:
    host = host.strip("[]").rstrip(".").lower()
    if not host or host == "localhost" or host.endswith(".localhost") or host.endswith(".local") \
            or host.endswith(".ts.net") or host.endswith(".internal") or host.endswith(".lan") or host.endswith(".home.arpa"):
        return None, f"{host or '?'}: local/tailnet name"
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        return None, f"{host}: DNS failed ({e.strerror or e})"
    ips = list(dict.fromkeys(i[4][0] for i in infos))
    for ip in ips:              # one bad answer poisons the name (no mixed public/private tricks)
        ok, why = ip_allowed(ip)
        if not ok:
            return None, f"{host} -> {ip}: {why}"
    v4 = [i for i in ips if ":" not in i]
    return (v4 or ips)[0], ""

# ---------------------------------------------------------------- egress proxy
class _Egress:
    def __init__(self, sock_path: str):
        self.path = sock_path
        self.log, self.blocked, self.bytes, self.conns = [], [], 0, 0
        self.lock = threading.Lock()
        self.srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.srv.bind(sock_path)
        os.chmod(sock_path, 0o600)
        self.srv.listen(64)
        self.stop = False
        threading.Thread(target=self._accept, daemon=True).start()

    def close(self):
        self.stop = True
        try: self.srv.close()
        except Exception: pass

    def _accept(self):
        while not self.stop:
            try:
                c, _ = self.srv.accept()
            except OSError:
                return
            with self.lock:
                self.conns += 1
                too_many = self.conns > MAX_CONNS
            if too_many:
                c.close(); continue
            threading.Thread(target=self._handle, args=(c,), daemon=True).start()

    def _block(self, c, target, why):
        with self.lock:
            if len(self.blocked) < 50:
                self.blocked.append({"target": target[:200], "why": why[:200]})
        try: c.sendall(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
        except Exception: pass
        c.close()

    def _handle(self, c):
        c.settimeout(HARD_KILL_S)
        try:
            head = b""
            while b"\r\n\r\n" not in head and len(head) < 65536:
                b = c.recv(4096)
                if not b: c.close(); return
                head += b
            line, _, rest = head.partition(b"\r\n")
            parts = line.decode("latin-1").split()
            if len(parts) != 3:
                return self._block(c, line.decode("latin-1"), "bad proxy request")
            method, target, ver = parts
            if method.upper() == "CONNECT":
                host, _, p = target.rpartition(":")
                port = int(p) if p.isdigit() else 0
                send_first = b""
            else:
                u = urlsplit(target)
                if u.scheme != "http" or not u.hostname:
                    return self._block(c, target, "only absolute http:// via proxy")
                host, port = u.hostname, u.port or 80
                path = (u.path or "/") + (("?" + u.query) if u.query else "")
                hdrs, _, body = rest.partition(b"\r\n\r\n")
                keep = [h for h in hdrs.split(b"\r\n") if h and not re.match(rb"(?i)(proxy-connection|connection|keep-alive)\s*:", h)]
                send_first = (f"{method} {path} {ver}\r\n".encode("latin-1") + b"\r\n".join(keep)
                              + b"\r\nConnection: close\r\n\r\n" + body)
            ip, why = resolve_public(host, port or 443)
            if not ip:
                return self._block(c, target, why)
            if port not in ALLOWED_PORTS:
                return self._block(c, target, f"port {port} not allowed (80/443 only)")
            try:
                up = socket.create_connection((ip, port), timeout=8)
                up.settimeout(HARD_KILL_S)
            except OSError as e:
                return self._block(c, target, f"connect failed: {e}")
            with self.lock:
                if len(self.log) < 200:
                    self.log.append({"host": host[:200], "ip": ip, "port": port})
            if method.upper() == "CONNECT":
                c.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            else:
                up.sendall(send_first)
            self._splice(c, up)
        except Exception:
            try: c.close()
            except Exception: pass

    def _splice(self, a, b):
        def one(src, dst):
            try:
                while True:
                    d = src.recv(65536)
                    if not d: break
                    with self.lock:
                        self.bytes += len(d)
                        over = self.bytes > MAX_BYTES
                    if over: break
                    dst.sendall(d)
            except Exception:
                pass
            for s in (src, dst):
                try: s.shutdown(socket.SHUT_RDWR)
                except Exception: pass
        t = threading.Thread(target=one, args=(b, a), daemon=True); t.start()
        one(a, b); t.join(HARD_KILL_S)
        for s in (a, b):
            try: s.close()
            except Exception: pass

# ---------------------------------------------------------------- jail
def available() -> tuple[bool, str]:
    if not shutil.which("bwrap"): return False, "bubblewrap (bwrap) not installed"
    if not (SITE / "playwright").is_dir(): return False, "Playwright (python) not found in ~/.local"
    if not any(BROWSERS.glob("chromium_headless_shell-*")): return False, "Playwright headless Chromium not installed"
    return True, ""

def _bwrap_cmd(run_dir: str, url: str) -> list[str]:
    shell = sorted(BROWSERS.glob("chromium_headless_shell-*"))[-1]
    cmd = ["bwrap", "--unshare-all", "--die-with-parent", "--new-session", "--cap-drop", "ALL",
           "--hostname", "sbx", "--clearenv",
           "--ro-bind", "/usr", "/usr", "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64",
           "--symlink", "usr/bin", "/bin", "--symlink", "usr/sbin", "/sbin",
           "--ro-bind", "/etc/fonts", "/etc/fonts", "--ro-bind-try", "/etc/ssl", "/etc/ssl",
           "--ro-bind-try", "/etc/ca-certificates", "/etc/ca-certificates",
           "--ro-bind-try", "/etc/ld.so.cache", "/etc/ld.so.cache",
           "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/dev/shm", "--tmpfs", "/tmp", "--tmpfs", "/home",
           "--dir", "/home/sbx", "--dir", "/sbx/py", "--dir", "/sbx/browsers",
           "--ro-bind", str(WORKER), "/sbx/worker.py"]
    for pkg in ("playwright", "greenlet", "pyee"):
        cmd += ["--ro-bind", str(SITE / pkg), f"/sbx/py/{pkg}"]
    cmd += ["--ro-bind", str(shell), f"/sbx/browsers/{shell.name}",
            "--bind", run_dir, "/sbx/run",
            "--setenv", "HOME", "/home/sbx", "--setenv", "PATH", "/usr/bin:/bin",
            "--setenv", "PYTHONPATH", "/sbx/py", "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
            "--setenv", "PLAYWRIGHT_BROWSERS_PATH", "/sbx/browsers",
            "--setenv", "PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS", "1",
            "--setenv", "SBX_BUDGET", str(BUDGET_S), "--setenv", "TMPDIR", "/tmp",
            "--chdir", "/home/sbx", "/usr/bin/python3", "-B", "/sbx/worker.py", url]
    if shutil.which("systemd-run") and os.environ.get("XDG_RUNTIME_DIR"):
        cmd = ["systemd-run", "--user", "--scope", "--quiet", "--collect", "-p", "MemoryMax=1500M",
               "-p", "CPUQuota=200%", "-p", "TasksMax=600", "--nice=10"] + cmd
    return cmd

# ---------------------------------------------------------------- analysis
_CC2 = ("co", "com", "org", "net", "gov", "ac", "edu", "ne", "or", "go")

def registered(host: str) -> str:
    host = (host or "").lower().rstrip(".")
    labels = host.split(".")
    if re.fullmatch(r"[\d.]+|\[?[0-9a-f:]+\]?", host): return host
    n = 3 if (len(labels) >= 3 and len(labels[-1]) == 2 and labels[-2] in _CC2) else 2
    return ".".join(labels[-n:]) if len(labels) >= n else host

def _reg(url: str) -> str:
    try: return registered(urlsplit(url).hostname or "")
    except Exception: return ""

def analyze(rep: dict) -> dict:
    """Turn a raw worker report into flags (danger) and cautions."""
    flags, cautions, notes = [], [], []
    start, final = rep.get("start_url", ""), rep.get("final_url") or ""
    if final and not re.match(r"^https?://", final, re.I):
        final = rep["final_url"] = ""          # e.g. chrome-error://chromewebdata/ after a refused load
    seq = [h["url"] for h in rep.get("chain", [])] + rep.get("navigations", [])
    seen, chain = set(), []
    for u in [start] + seq + ([final] if final else []):
        k = re.sub(r"/$", "", u or "")
        if u and re.match(r"^https?://", u, re.I) and k not in seen:
            seen.add(k); chain.append(u)
    rep["chain_urls"] = chain
    regs = [r for r in dict.fromkeys(_reg(u) for u in chain) if r]
    rep["domains"] = regs
    f = rep.get("fields") or {}
    final_reg, start_reg = _reg(final or start), _reg(start)
    cross = len(regs) > 1
    if rep.get("downloads"):
        flags.append(f"The page tried to download a file ({rep['downloads'][0].get('file') or 'unknown'}). It was blocked, not saved or opened.")
    if f.get("card"):
        flags.append("The page asks for card / payment details.")
    if f.get("password") and (cross or final_reg != start_reg):
        flags.append(f"The page asks for a password on {final_reg}, a different site than the QR code shows.")
    elif f.get("password"):
        cautions.append("The page asks for a login / password. Only sign in if you went there on purpose.")
    elif f.get("otp"):
        cautions.append("The page asks for a one-time / verification code.")
    if final.startswith("http://") and (f.get("password") or f.get("card")):
        flags.append("It asks for a password or card on an insecure (http) page.")
    if cross:
        cautions.append("It redirects across sites: " + " → ".join(regs[:6]) + ".")
    blocked = rep.get("blocked", [])
    priv = [b for b in blocked if not b["why"].startswith(("connect failed", "port", "bad proxy", "only absolute"))]
    def _bhost(t):
        t = t if "://" in t else "x://" + t
        try: return (urlsplit(t).hostname or "").lower()
        except Exception: return ""
    doc_hosts = {(urlsplit(u).hostname or "").lower() for u in chain}
    doc_blocked = [b for b in blocked if _bhost(b["target"]) in doc_hosts]
    if doc_blocked:
        rep["ok"] = False          # the proxy's 403 is not a real page
        rep["title"] = ""
    if priv and any(b in priv for b in doc_blocked):
        flags.append("This link (or one of its redirects) points to a private / local network address (" + priv[0]["why"] + "). The sandbox refused to go there.")
    elif priv:
        flags.append("The page tried to reach a private / local network address (" + priv[0]["why"] + "). Blocked.")
    if any(b["why"].startswith("port") for b in doc_blocked):
        cautions.append("The link uses an unusual port; the sandbox only visits normal web ports (80/443), so it wasn't opened.")
    err = rep.get("error") or ""
    if "ERR_CERT" in err or "SSL" in err.upper():
        flags.append("The site's security certificate is not valid (" + err[:120] + ").")
    elif not rep.get("ok") and not doc_blocked:
        cautions.append("The page didn't load in the sandbox" + (" (" + err[:140] + ")." if err else "."))
    if final.startswith("http://") and rep.get("ok"):
        cautions.append("The page ends on plain http (not encrypted).")
    last = (rep.get("chain") or [{}])[-1].get("status")
    if rep.get("ok") and isinstance(last, int) and last >= 400 and not doc_blocked:
        cautions.append(f"The site answered with an error (HTTP {last}).")
    if rep.get("popups"):
        cautions.append("It opened a pop-up window.")
    if rep.get("dialogs"):
        cautions.append("It showed a pop-up alert / dialog.")
    now = time.time()
    for t in rep.get("tls", []):
        vt = t.get("validTo")
        if vt and vt - now < 3 * 86400:
            cautions.append(f"Certificate for {t.get('subjectName')} expires very soon.")
        vf = t.get("validFrom")
        if vf and now - vf < 3 * 86400:
            notes.append(f"Certificate for {t.get('subjectName')} was issued in the last 3 days (normal for big sites that rotate often; a brand-new site would be riskier).")
    rep["flags"], rep["cautions"], rep["notes"] = list(dict.fromkeys(flags)), list(dict.fromkeys(cautions)), notes
    rep["level"] = "flagged" if flags else ("caution" if cautions or not rep.get("ok") else "ok")
    return rep

# ---------------------------------------------------------------- entry point
def check_url(url: str) -> dict:
    """Run one sandbox visit. Returns {'busy': True} if another run is in progress."""
    if not re.match(r"^https?://", url or "", re.I) or len(url) > 2000:
        return {"ok": False, "error": "only http(s) links can be checked"}
    ok, why = available()
    if not ok:
        return {"ok": False, "error": "sandbox unavailable: " + why}
    if not _run_lock.acquire(blocking=False):
        return {"ok": False, "busy": True, "error": "a sandbox check is already running"}
    run_dir = tempfile.mkdtemp(prefix="qr-sbx-")
    os.chmod(run_dir, 0o700)
    eg = None
    t0 = time.monotonic()
    try:
        eg = _Egress(os.path.join(run_dir, "proxy.sock"))
        p = subprocess.Popen(_bwrap_cmd(run_dir, url), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             stdin=subprocess.DEVNULL, start_new_session=True)
        try:
            so, se = p.communicate(timeout=HARD_KILL_S)
        except subprocess.TimeoutExpired:
            try: os.killpg(p.pid, 9)
            except Exception: p.kill()
            so, se = p.communicate()
            rep = {"ok": False, "error": f"sandbox timed out after {HARD_KILL_S}s and was killed"}
        else:
            txt = so.decode("utf-8", "replace")
            m = txt.rfind("@@SBX@@")
            try:
                rep = json.loads(txt[m + 7:].strip().splitlines()[0]) if m >= 0 else None
            except Exception:
                rep = None
            if rep is None:
                rep = {"ok": False, "error": "sandbox produced no report: " + se.decode("utf-8", "replace")[-300:]}
        rep.setdefault("start_url", url)
        rep["blocked"] = list(eg.blocked)
        rep["contacted"] = list(eg.log)
        rep["bytes"] = eg.bytes
        rep["wall_ms"] = round((time.monotonic() - t0) * 1000)
        return analyze(rep)
    finally:
        if eg: eg.close()
        shutil.rmtree(run_dir, ignore_errors=True)
        _run_lock.release()

if __name__ == "__main__":
    import sys
    r = check_url(sys.argv[1])
    r.pop("screenshot", None) if "--no-shot" in sys.argv else None
    print(json.dumps(r, indent=1)[:6000])

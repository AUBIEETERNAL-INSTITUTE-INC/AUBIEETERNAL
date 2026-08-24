#!/usr/bin/env python3
"""
Always-on self-audit for the Ryzen rig.

Every 15 minutes: check services, disk, HTTP, dog monitor.
If aubieeternal Build is down, restart it.
Recurring problems become lessons the next Build/Grok session can see.

Nightly: ask local Qwen for a short "how to get better" note from the day's log.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
DIR = HOME / "AUBIEETERNAL" / "memory" / "self_audit"
LOG = DIR / "audit.jsonl"
LATEST = DIR / "latest.json"
LESSONS = DIR / "lessons.md"
GROK_RULE = HOME / ".grok" / "rules" / "self-audit.md"
MONITOR_LOG = HOME / "scripts" / "aubie_monitor.log"
SESSIONS = HOME / ".grok" / "sessions"


def scrape_tool_fails(limit: int = 8) -> list[dict]:
    """Read recent Grok/Build session logs for failed tool calls."""
    fails = []
    if not SESSIONS.is_dir():
        return fails
    # Prefer aubieeternal Build sessions (AUBIEETERNAL cwd), then others.
    files = sorted(SESSIONS.rglob("updates.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    preferred = [p for p in files if "AUBIEETERNAL" in str(p)]
    rest = [p for p in files if p not in preferred]
    for path in (preferred + rest)[:12]:
        try:
            lines = path.read_text(errors="ignore").splitlines()
        except OSError:
            continue
        sid = path.parent.name
        for line in lines:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            u = (rec.get("params") or {}).get("update") or {}
            if str(u.get("status") or "").lower() != "failed":
                continue
            text = ""
            content = u.get("content")
            if isinstance(content, list):
                for block in content:
                    inner = (block or {}).get("content") if isinstance(block, dict) else None
                    if isinstance(inner, dict) and inner.get("text"):
                        text = inner["text"]
                        break
            title = u.get("title") or "tool"
            inp = u.get("rawInput")
            fails.append({
                "session": sid,
                "tool": title,
                "error": (text or "failed")[:400],
                "input": inp,
            })
            if len(fails) >= limit:
                return fails
    return fails

USER_SERVICES = ["aubie-build.service"]
SYSTEM_SERVICES = ["aubie-assistant", "aubie-mcp", "aubie-portal"]
HTTP_CHECKS = [
    ("build", "http://127.0.0.1:8840/api/health"),
    ("assistant", "http://127.0.0.1:8800/health"),
    ("ollama", "http://127.0.0.1:11434/api/tags"),
]


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sh(cmd: str, timeout: int = 8) -> str:
    try:
        p = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True, text=True, timeout=timeout,
        )
        return ((p.stdout or "") + (p.stderr or "")).strip()[:800]
    except Exception as exc:
        return f"err:{exc}"


def http_ok(url: str, timeout: float = 3.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return 200 <= r.status < 400
    except Exception:
        return False


def collect() -> dict:
    findings = []
    services = {}
    for unit in USER_SERVICES:
        st = sh(f"systemctl --user is-active {unit}")
        services[unit] = st
        if st != "active":
            findings.append({"id": f"down:{unit}", "sev": "high", "msg": f"{unit} is {st}"})
    for unit in SYSTEM_SERVICES:
        st = sh(f"systemctl is-active {unit}")
        services[unit] = st
        if st != "active":
            findings.append({"id": f"down:{unit}", "sev": "high", "msg": f"{unit} is {st}"})

    http = {}
    for name, url in HTTP_CHECKS:
        ok = http_ok(url)
        http[name] = ok
        if not ok:
            findings.append({"id": f"http:{name}", "sev": "high", "msg": f"{name} not answering {url}"})

    disk = sh("df -P / | awk 'NR==2{print $5}'").rstrip("%")
    try:
        pct = int(disk)
        if pct >= 90:
            findings.append({"id": "disk", "sev": "high", "msg": f"disk {pct}% full"})
        elif pct >= 80:
            findings.append({"id": "disk", "sev": "med", "msg": f"disk {pct}% full"})
    except ValueError:
        pct = None

    ram = sh("free | awk 'NR==2{printf \"%d\", $3*100/$2}'")
    try:
        ram_pct = int(ram)
        if ram_pct >= 92:
            findings.append({"id": "ram", "sev": "med", "msg": f"RAM {ram_pct}%"})
    except ValueError:
        ram_pct = None

    dog = "unknown"
    if MONITOR_LOG.exists():
        tail = MONITOR_LOG.read_text(errors="ignore").splitlines()[-1:]
        last = tail[0] if tail else ""
        if "healthy-no-action" in last:
            dog = "healthy"
        elif "repaired-successfully" in last:
            dog = "repaired"
            findings.append({"id": "dog:repaired", "sev": "low", "msg": last[-180:]})
        elif "unhealthy" in last or "repair-failed" in last or "timed out" in last:
            dog = "unreachable"
            findings.append({"id": "dog:down", "sev": "med", "msg": "Aubie dog not reachable (monitor)"})

    ollama = sh("ollama list 2>/dev/null | awk 'NR>1{print $1}' | tr '\\n' ' '")
    if "qwen2.5:14b" not in ollama:
        findings.append({"id": "ollama:qwen14", "sev": "high", "msg": "qwen2.5:14b missing from ollama"})

    tool_fails = scrape_tool_fails()
    if tool_fails:
        findings.append({
            "id": "build:tool_fails",
            "sev": "med",
            "msg": f"{len(tool_fails)} recent Build tool failures (wrong args / bad paths)",
        })

    return {
        "ts": now(),
        "services": services,
        "http": http,
        "disk_pct": pct,
        "ram_pct": ram_pct,
        "dog": dog,
        "ollama": ollama.strip(),
        "findings": findings,
        "tool_fails": tool_fails,
        "ok": not any(f["sev"] == "high" for f in findings),
    }


def repair(report: dict) -> list[str]:
    actions = []
    for unit in USER_SERVICES:
        if report["services"].get(unit) != "active":
            out = sh(f"systemctl --user restart {unit}")
            time.sleep(1)
            st = sh(f"systemctl --user is-active {unit}")
            actions.append(f"restarted {unit} -> {st} {out[:80]}")
            report["services"][unit] = st
    return actions


def append_log(report: dict) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(json.dumps(report) + "\n")
    LATEST.write_text(json.dumps(report, indent=2))


def promote_lessons(report: dict) -> None:
    """Same finding 3 times in the last 16 runs becomes a lesson."""
    if not LOG.exists():
        return
    lines = LOG.read_text(errors="ignore").splitlines()[-16:]
    counts: dict[str, int] = {}
    for line in lines:
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        for f in rec.get("findings") or []:
            counts[f["id"]] = counts.get(f["id"], 0) + 1
    recurring = [k for k, n in counts.items() if n >= 3]
    if not recurring:
        return
    LESSONS.parent.mkdir(parents=True, exist_ok=True)
    stamp = report["ts"]
    existing = LESSONS.read_text() if LESSONS.exists() else ""
    block = f"\n## {stamp}\n"
    for rid in recurring:
        line = f"- Recurring: `{rid}` ({counts[rid]} times in last 16 audits)\n"
        if rid not in existing[-4000:]:
            block += line
    if block.strip() != f"## {stamp}":
        with LESSONS.open("a") as f:
            f.write(block)


def write_grok_rule(report: dict) -> None:
    GROK_RULE.parent.mkdir(parents=True, exist_ok=True)
    grade = "GREEN" if report["ok"] else "RED"
    findings = report.get("findings") or []
    lines = [
        "# Self-audit (live)",
        "",
        f"Last run: {report['ts']}  Grade: **{grade}**",
        f"Build HTTP: {'ok' if report['http'].get('build') else 'DOWN'} · "
        f"Assistant: {'ok' if report['http'].get('assistant') else 'DOWN'} · "
        f"Ollama: {'ok' if report['http'].get('ollama') else 'DOWN'} · "
        f"Dog: {report.get('dog')}",
        "",
    ]
    if findings:
        lines.append("Open findings:")
        for f in findings:
            lines.append(f"- ({f['sev']}) {f['msg']}")
        lines.append("")
    tf = report.get("tool_fails") or []
    if tf:
        lines.append("Recent aubieeternal Build tool errors (read these, do not guess):")
        for f in tf[:6]:
            err = (f.get("error") or "").replace("\n", " ")[:180]
            lines.append(f"- `{f.get('tool')}`: {err}")
        lines.append("")
    lines.append("This rig audits itself every 15 minutes. If something is RED, fix that first.")
    if LESSONS.exists():
        tail = LESSONS.read_text(errors="ignore").strip().split("## ")[-1:]
        if tail and tail[0].strip():
            lines += ["", "Latest lesson:", "## " + tail[0].strip()[:800]]
    GROK_RULE.write_text("\n".join(lines) + "\n")


def nightly() -> None:
    """Ask local Qwen for a short improvement note from today's log."""
    if not LOG.exists():
        return
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = []
    for line in LOG.read_text(errors="ignore").splitlines()[-80:]:
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("ts", "").startswith(today):
            rows.append(rec)
    summary = json.dumps(
        [{"ts": r.get("ts"), "ok": r.get("ok"), "findings": r.get("findings")} for r in rows[-24:]],
        indent=2,
    )[:4000]
    prompt = (
        "You are aubieeternal Build's self-audit. From this JSON of today's checks, "
        "write 4 short bullets: what kept failing, what recovered, one concrete "
        "improvement for tomorrow. No preamble.\n\n" + summary
    )
    try:
        payload = json.dumps({"model": "qwen2.5:14b", "prompt": prompt, "stream": False}).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=90) as r:
            body = json.loads(r.read().decode())
        note = (body.get("response") or "").strip()[:1500]
    except Exception as exc:
        note = f"(nightly model skip: {exc})"
    with LESSONS.open("a") as f:
        f.write(f"\n## nightly {now()}\n{note}\n")


def run_once() -> int:
    report = collect()
    report["repairs"] = repair(report)
    # re-check HTTP after repairs
    if report["repairs"]:
        time.sleep(2)
        follow = collect()
        report["after_repair"] = {"http": follow["http"], "services": follow["services"]}
        report["ok"] = follow["ok"]
    append_log(report)
    promote_lessons(report)
    write_grok_rule(report)
    print(json.dumps({"ok": report["ok"], "findings": report["findings"], "repairs": report["repairs"]}))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    if "--nightly" in sys.argv:
        nightly()
        sys.exit(0)
    sys.exit(run_once())

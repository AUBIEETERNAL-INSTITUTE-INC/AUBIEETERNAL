#!/usr/bin/env python3
"""
AUBIE Orchestrator
Issues tokens and runs shell commands on behalf of agents.
AUBIE stays in control — agents never hold long-lived access.
"""

import time
import hmac
import hashlib
import json
import base64
import subprocess
from pathlib import Path

# Must match the secret in the Open WebUI tool and issue_token.py
# Replace this with a long random string on the local machine only.
SECRET = "CHANGE-ME-TO-A-LONG-RANDOM-SECRET"

HARD_BLOCK = [
    "mkfs", "dd if=", ":(){:|:&};:", "> /dev/sd", "of=/dev/sd",
    "shutdown", "reboot", "poweroff", "halt",
    "rm -rf /", "rm -rf /*", "chmod -R 777 /",
]

def issue_token(task: str, allowed: list, minutes: int = 10, note: str = "") -> str:
    payload = {
        "task": task,
        "allowed": allowed,
        "exp": int(time.time()) + minutes * 60,
        "note": note,
        "iat": int(time.time()),
    }
    data = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = hmac.new(SECRET.encode(), data.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{data}.{sig}"

def verify_token(token: str, command: str) -> tuple[bool, str]:
    try:
        data, sig = token.rsplit(".", 1)
        expected = hmac.new(SECRET.encode(), data.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(expected, sig):
            return False, "bad signature"
        pad = "=" * (-len(data) % 4)
        payload = json.loads(base64.urlsafe_b64decode(data + pad))
        if payload.get("exp", 0) < time.time():
            return False, "token expired"
        allowed = payload.get("allowed", [])
        if allowed and not any(a.lower() in command.lower() for a in allowed):
            return False, f"command not allowed (token allows: {allowed})"
        return True, payload.get("task", "")
    except Exception as e:
        return False, f"invalid token: {e}"

def run_shell(command: str, token: str, timeout: int = 60) -> dict:
    """Run a command if the token is valid. Returns structured result."""
    if not command or not command.strip():
        return {"ok": False, "stdout": "", "stderr": "empty command", "returncode": -1}

    ok, reason = verify_token(token, command)
    if not ok:
        return {"ok": False, "stdout": "", "stderr": f"REFUSED: {reason}", "returncode": -1}

    low = command.lower()
    for bad in HARD_BLOCK:
        if bad in low:
            return {"ok": False, "stdout": "", "stderr": f"REFUSED: hard-blocked ({bad})", "returncode": -1}

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(Path.home()),
        )
        return {
            "ok": result.returncode == 0,
            "stdout": result.stdout or "",
            "stderr": result.stderr or "",
            "returncode": result.returncode,
            "task": reason,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": "timeout", "returncode": -1}
    except Exception as e:
        return {"ok": False, "stdout": "", "stderr": str(e), "returncode": -1}

def run_with_token(command: str, allowed: list = None, minutes: int = 10, retries: int = 1) -> dict:
    """
    Main entry point for AUBIE.
    Issues a token, runs the command, and retries once with a fresh token if refused.
    """
    if allowed is None:
        allowed = ["df", "free", "uptime", "ps", "systemctl status"]

    for attempt in range(retries + 1):
        token = issue_token(task=command[:80], allowed=allowed, minutes=minutes)
        result = run_shell(command, token)
        if result["ok"] or "REFUSED" not in result.get("stderr", ""):
            return result
        if attempt < retries:
            time.sleep(0.5)
            continue
    return result

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 aubie_orchestrator.py 'command here'")
        print("Example: python3 aubie_orchestrator.py 'df -h'")
        sys.exit(1)

    cmd = " ".join(sys.argv[1:])
    print(f"AUBIE running: {cmd}")
    result = run_with_token(cmd)
    if result["ok"]:
        print(result["stdout"])
    else:
        print("Error:", result["stderr"])

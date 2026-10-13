#!/usr/bin/env python3
"""
AUBIE token issuer wrapper.
Prompts for task details and prints a ready-to-paste Open WebUI message.
"""

import time
import hmac
import hashlib
import json
import base64

# Must match the secret in the Open WebUI tool and aubie_orchestrator.py
# Replace this with a long random string on the local machine only.
SECRET = "CHANGE-ME-TO-A-LONG-RANDOM-SECRET"

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

def main():
    print("=== AUBIE Token Issuer ===\n")
    task = input("Task description: ").strip() or "IT check"
    allowed_raw = input("Allowed commands (comma-separated, e.g. df,free,systemctl): ").strip()
    allowed = [a.strip() for a in allowed_raw.split(",") if a.strip()] or ["df", "free"]
    minutes_raw = input("Minutes valid [15]: ").strip()
    minutes = int(minutes_raw) if minutes_raw.isdigit() else 15
    note = input("Optional note: ").strip()

    token = issue_token(task, allowed, minutes, note)

    print("\n" + "=" * 50)
    print("TOKEN:")
    print(token)
    print("=" * 50)
    print("\nReady-to-paste chat message:\n")
    print(f'Use run_shell_command with command="df -h" and token="{token}"')
    print("\n(Edit the command= part as needed before sending.)")

if __name__ == "__main__":
    main()

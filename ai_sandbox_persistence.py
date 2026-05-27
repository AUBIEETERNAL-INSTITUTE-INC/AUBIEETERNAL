# ai_sandbox_persistence.py
# Updated persistence for AI Sandbox + Family Contribution Bridge
# Created: May 26, 2026

import json
import os
from datetime import datetime, timedelta

DATA_DIR = "ai_sandbox_data"
FAMILIES_DIR = os.path.join(DATA_DIR, "families")
SUBMISSIONS_FILE = os.path.join(DATA_DIR, "swarm_submissions.jsonl")
CONTROL_FILE = os.path.join(DATA_DIR, "swarm_control.json")

os.makedirs(FAMILIES_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

def load_ai_progress(family_id=None):
    """Load AI Sandbox progress for a family"""
    if not family_id:
        family_id = "default"
    path = os.path.join(FAMILIES_DIR, f"{family_id}.json")
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {"ai_builder_level": 1, "ai_xp": 0, "ai_badges": [], "ai_completed_lessons": []}

def save_ai_progress(state, family_id=None):
    if not family_id:
        family_id = "default"
    path = os.path.join(FAMILIES_DIR, f"{family_id}.json")
    with open(path, "w") as f:
        json.dump(state, f, indent=2)

def append_swarm_submission(submission):
    """Append a new submission to the JSONL queue"""
    submission["timestamp"] = datetime.now().isoformat()
    with open(SUBMISSIONS_FILE, "a") as f:
        f.write(json.dumps(submission) + "\n")

def load_swarm_submissions(family_id=None, status=None):
    """Load submissions with optional filters"""
    if not os.path.exists(SUBMISSIONS_FILE):
        return []
    results = []
    with open(SUBMISSIONS_FILE, "r") as f:
        for line in f:
            try:
                sub = json.loads(line)
                if family_id and sub.get("family_id") != family_id:
                    continue
                if status and sub.get("status") != status:
                    continue
                results.append(sub)
            except:
                continue
    return results

def record_family_injection(family_id, submission_id, mini_daughter_name):
    """Record when a family contribution is injected into the swarm"""
    try:
        if os.path.exists(CONTROL_FILE):
            with open(CONTROL_FILE, "r") as f:
                data = json.load(f)
        else:
            data = {"injections": []}
        
        data["injections"].append({
            "family_id": family_id,
            "submission_id": submission_id,
            "mini_daughter_name": mini_daughter_name,
            "injected_at": datetime.now().isoformat()
        })
        
        # Keep only last 50
        data["injections"] = data["injections"][-50:]
        
        with open(CONTROL_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[persistence] Error recording injection: {e}")

def get_recent_injections(limit=5):
    """Get the most recent family injections"""
    try:
        if not os.path.exists(CONTROL_FILE):
            return []
        with open(CONTROL_FILE, "r") as f:
            data = json.load(f)
        return data.get("injections", [])[-limit:][::-1]
    except:
        return []
# swarm_contributions.py
# Family Contribution Bridge for AUBIEETERNAL
# Created: May 26, 2026

import json
from datetime import datetime

def load_approved_contributions():
    """Load approved submissions from JSONL"""
    try:
        with open("ai_sandbox_data/swarm_submissions.jsonl", "r") as f:
            lines = f.readlines()
        approved = [json.loads(line) for line in lines if json.loads(line).get("status") == "approved"]
        return approved
    except:
        return []


def convert_approved_submission_to_mini_daughter(submission):
    """Convert an approved submission into a mini-daughter structure"""
    return {
        "name": submission.get("title", "Family Contribution"),
        "system_prompt": submission.get("content", ""),
        "role": "family_contributed",
        "family_id": submission.get("family_id"),
        "approved_at": submission.get("reviewed_at"),
        "parent_comment": submission.get("review_comment", ""),
        "source": "ai_sandbox"
    }


def get_and_register_new_contributions(dry_run=True):
    """Main function called by swarm to get family contributions"""
    approved = load_approved_contributions()
    mini_daughters = []
    
    for sub in approved:
        mini = convert_approved_submission_to_mini_daughter(sub)
        mini_daughters.append(mini)
        
        if not dry_run:
            print(f"🧬 REGISTERED mini-daughter from family: {mini['family_id']} - {mini['name']}")
    
    if mini_daughters and not dry_run:
        print(f"[family] ✅ Injected {len(mini_daughters)} mini-daughters from approved submissions")
    
    return mini_daughters
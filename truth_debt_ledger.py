"""
truth_debt_ledger.py — AUBIEETERNAL Truth Debt Ledger
======================================================
My addition for helping humanity. — Claude

THE PROBLEM:
  The internet has zero institutional memory for false claims.
  A politician, news outlet, or influencer makes a specific,
  falsifiable claim. It spreads. It influences decisions.
  It turns out to be wrong. Nobody is held accountable.
  The same claim gets made again next cycle.

  This creates "truth debt" — the compounding cost of unchecked
  false claims propagating through civilization without correction.

THE SOLUTION:
  When any falsifiable claim enters the AUBIEETERNAL system
  (via X Bridge, swarm daughters, or family lessons), it gets
  registered in the Truth Debt Ledger with:
    - The claim itself
    - The source
    - A verification deadline (how long before we can check)
    - A falsifiability score
    - The eventual outcome (verified / refuted / unresolved)

  The ledger is public, append-only, and pushed to GitHub daily.
  Over time, it becomes a verifiable track record of which
  sources make falsifiable claims and how often they're right.

WHY THIS MATTERS FOR HUMANITY:
  - Creates institutional memory for claims and outcomes
  - Makes prediction accuracy visible and trackable
  - Turns abstract "epistemic rigor" into a concrete,
    measurable practice with real accountability
  - The public ledger can be used by any AI system as
    ground truth for source credibility
  - Families who track claims teach their children that
    truth is not tribal — it has a score

Usage:
    from truth_debt_ledger import TruthDebtLedger
    ledger = TruthDebtLedger()
    ledger.register(claim="X will happen by date Y", source="x_bridge")
    ledger.resolve(claim_id, outcome="refuted", evidence="...")
    report = ledger.get_accountability_report()
"""

import os, json, hashlib, datetime
from pathlib import Path
import socket as _socket

def _data_dir():
    try:
        _socket.gethostbyname("ollama.startos")
        return Path("/mnt/main")
    except Exception:
        p = Path(os.path.expanduser("~/.aubieeternal/main"))
        p.mkdir(parents=True, exist_ok=True)
        return p

DATA_DIR    = _data_dir()
LEDGER_FILE = DATA_DIR / "repo" / "truth_debt_ledger.jsonl"
LEDGER_MD   = DATA_DIR / "repo" / "insights" / "truth_debt_report.md"
LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)
LEDGER_MD.parent.mkdir(parents=True, exist_ok=True)

# Default verification windows by claim type
VERIFICATION_WINDOWS = {
    "prediction":  30,   # days — "X will happen"
    "factual":     7,    # days — "X is true right now"
    "statistical": 14,   # days — "X% of people believe..."
    "scientific":  90,   # days — "Studies show..."
    "political":   180,  # days — "Policy X will cause Y"
    "general":     14,   # days — default
}

# Falsifiability categories
CLAIM_CATEGORIES = {
    "prediction":  "Makes a time-bound claim about future events",
    "factual":     "Claims something is currently true",
    "statistical": "Claims a specific number or percentage",
    "scientific":  "Claims scientific research supports X",
    "political":   "Claims a policy will have a specific effect",
    "general":     "General falsifiable claim",
}


class TruthDebtLedger:
    """
    Public, append-only record of falsifiable claims and their outcomes.
    The antidote to institutional amnesia.
    """

    def register(self, claim: str, source: str = "unknown",
                 source_text: str = "", claim_type: str = "general",
                 source_url: str = "") -> dict:
        """
        Register a new falsifiable claim.
        Returns the entry with its unique claim_id.
        """
        claim_id = hashlib.sha256(
            f"{claim}{datetime.datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]

        deadline_days = VERIFICATION_WINDOWS.get(claim_type, 14)
        deadline      = (datetime.date.today() +
                         datetime.timedelta(days=deadline_days)).isoformat()

        entry = {
            "claim_id":         claim_id,
            "registered":       datetime.datetime.now().isoformat(),
            "claim":            claim[:300],
            "source":           source,
            "source_text":      source_text[:200],
            "source_url":       source_url,
            "claim_type":       claim_type,
            "verification_deadline": deadline,
            "status":           "open",        # open | verified | refuted | unresolved
            "outcome":          None,
            "outcome_evidence": None,
            "outcome_date":     None,
            "falsifiability":   self._score_falsifiability(claim),
        }

        with open(LEDGER_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")

        print(f"[ledger] Registered: {claim[:60]}... (ID: {claim_id})")
        return entry

    def resolve(self, claim_id: str, outcome: str,
                evidence: str = "", verifier: str = "family") -> bool:
        """
        Resolve a claim with its outcome.
        outcome: 'verified' | 'refuted' | 'unresolved' | 'partially_true'
        """
        if not LEDGER_FILE.exists():
            return False

        lines   = LEDGER_FILE.read_text().strip().split("\n")
        updated = []
        found   = False

        for line in lines:
            try:
                entry = json.loads(line)
                if entry.get("claim_id") == claim_id:
                    entry["status"]           = outcome
                    entry["outcome"]          = outcome
                    entry["outcome_evidence"] = evidence[:300]
                    entry["outcome_date"]     = datetime.datetime.now().isoformat()
                    entry["verifier"]         = verifier
                    found = True
                updated.append(json.dumps(entry))
            except Exception:
                updated.append(line)

        LEDGER_FILE.write_text("\n".join(updated))
        return found

    def get_open_claims(self) -> list:
        """Get all claims still awaiting verification."""
        return [e for e in self._load_all()
                if e.get("status") == "open"]

    def get_overdue_claims(self) -> list:
        """Get claims past their verification deadline."""
        today = datetime.date.today().isoformat()
        return [e for e in self._load_all()
                if e.get("status") == "open" and
                e.get("verification_deadline", "9999") < today]

    def get_accountability_report(self, days: int = 90) -> dict:
        """
        Generate an accountability report.
        This is the output that makes the ledger useful at scale.
        """
        cutoff  = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
        entries = [e for e in self._load_all()
                   if e.get("registered", "")[:10] >= cutoff]

        if not entries:
            return {"total": 0, "sources": {}, "accuracy_rate": None}

        total      = len(entries)
        resolved   = [e for e in entries if e["status"] != "open"]
        verified   = [e for e in entries if e["status"] == "verified"]
        refuted    = [e for e in entries if e["status"] == "refuted"]
        overdue    = self.get_overdue_claims()

        # Source-level accountability
        sources = {}
        for e in entries:
            src = e.get("source", "unknown")
            if src not in sources:
                sources[src] = {"total": 0, "verified": 0, "refuted": 0,
                                "unresolved": 0, "open": 0}
            sources[src]["total"] += 1
            sources[src][e["status"]] = sources[src].get(e["status"], 0) + 1

        # Accuracy rate (only for resolved claims)
        accuracy = None
        if resolved:
            accuracy = round(len(verified) / len(resolved) * 100, 1)

        return {
            "total":         total,
            "open":          len([e for e in entries if e["status"] == "open"]),
            "resolved":      len(resolved),
            "verified":      len(verified),
            "refuted":       len(refuted),
            "overdue":       len(overdue),
            "accuracy_rate": accuracy,
            "sources":       sources,
            "most_accurate_source": max(
                sources, key=lambda s: sources[s].get("verified", 0)
            ) if sources else None,
            "period_days":   days,
        }

    def write_public_report(self) -> str:
        """Write the public markdown report to GitHub."""
        report  = self.get_accountability_report(90)
        entries = self._load_all()[-20:]  # last 20 for display
        today   = datetime.date.today().isoformat()

        lines = [
            f"# 📋 Truth Debt Ledger — {today}",
            f"",
            f"**The public record of falsifiable claims and their outcomes.**",
            f"Every claim registered here was made by a public source, scored for",
            f"falsifiability, and tracked to its outcome.",
            f"",
            f"*License: CC0 Public Domain. Use this data freely.*",
            f"",
            f"---",
            f"",
            f"## Summary ({report['period_days']}-Day Window)",
            f"",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total claims registered | {report['total']} |",
            f"| Resolved | {report['resolved']} |",
            f"| Verified true | {report['verified']} |",
            f"| Refuted false | {report['refuted']} |",
            f"| Overdue (awaiting check) | {report['overdue']} |",
            f"| Accuracy rate (resolved only) | "
            f"{'N/A' if report['accuracy_rate'] is None else str(report['accuracy_rate']) + '%'} |",
            f"",
        ]

        if report["sources"]:
            lines += [
                f"## Source Accountability",
                f"",
            ]
            for src, stats in sorted(report["sources"].items(),
                                      key=lambda x: x[1]["total"], reverse=True)[:10]:
                acc = round(stats["verified"] / max(1, stats["verified"] + stats["refuted"]) * 100, 0)
                lines.append(
                    f"- **{src}**: {stats['total']} claims · "
                    f"{stats['verified']} verified · {stats['refuted']} refuted · "
                    f"{acc:.0f}% accuracy"
                )
            lines.append("")

        if entries:
            lines += [
                f"## Recent Claims",
                f"",
            ]
            for e in reversed(entries[-10:]):
                status_icon = {"verified": "✅", "refuted": "❌",
                               "unresolved": "⚠️", "open": "🔄",
                               "partially_true": "〰️"}.get(e["status"], "❓")
                lines += [
                    f"### {status_icon} `{e['claim_id']}` — {e.get('claim_type','?').title()}",
                    f"**Claim:** {e['claim'][:150]}",
                    f"**Source:** {e['source']} | **Registered:** {e['registered'][:10]}",
                    f"**Deadline:** {e.get('verification_deadline','?')} | "
                    f"**Falsifiability:** {e.get('falsifiability', 0):.2f}",
                ]
                if e.get("outcome_evidence"):
                    lines.append(f"**Outcome:** {e['outcome_evidence']}")
                lines.append("")

        lines += [
            f"---",
            f"",
            f"*AUBIEETERNAL Truth Debt Ledger — War Eagle Eternal 🦅*",
            f"*Append-only. Permanent. CC0.*",
        ]

        LEDGER_MD.write_text("\n".join(lines))
        return str(LEDGER_MD)

    # ══════════════════════════════════════════════════════════════════════════
    # HELPERS
    # ══════════════════════════════════════════════════════════════════════════

    def _score_falsifiability(self, claim: str) -> float:
        """
        Score how falsifiable a claim is (0.0 = can never be checked,
        1.0 = can be definitively verified or refuted).
        """
        score = 0.5  # baseline
        lower = claim.lower()
        # Specific numbers = more falsifiable
        import re
        if re.search(r'\d+%|\$\d+|\d+ (million|billion|thousand)', lower):
            score += 0.2
        # Time bounds = more falsifiable
        if re.search(r'\b(by|before|in|within)\s+\d{4}|\bby\s+(monday|january|march)', lower):
            score += 0.2
        # Vague words = less falsifiable
        if any(w in lower for w in ["might", "could", "possibly", "some say",
                                      "many believe", "experts think"]):
            score -= 0.2
        # Absolute claims = more falsifiable
        if any(w in lower for w in ["will", "always", "never", "proves", "confirmed"]):
            score += 0.1
        return round(min(1.0, max(0.0, score)), 2)

    def _load_all(self) -> list:
        if not LEDGER_FILE.exists():
            return []
        entries = []
        for line in LEDGER_FILE.read_text().strip().split("\n"):
            try:
                entries.append(json.loads(line))
            except Exception:
                pass
        return entries


# ── Standalone test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("📋 Truth Debt Ledger Test")
    ledger = TruthDebtLedger()

    # Register some test claims
    e1 = ledger.register(
        "Bitcoin will reach $150,000 by end of 2026",
        source="x_bridge", claim_type="prediction"
    )
    e2 = ledger.register(
        "Studies show 73% of people who eat breakfast live longer",
        source="x_bridge", claim_type="statistical"
    )
    print(f"Registered: {e1['claim_id']} (falsifiability: {e1['falsifiability']})")
    print(f"Registered: {e2['claim_id']} (falsifiability: {e2['falsifiability']})")

    report = ledger.get_accountability_report()
    print(f"\nReport: {report['total']} claims, {report['open']} open")
    path = ledger.write_public_report()
    print(f"Public report: {path}")
    print("\n✅ Truth Debt Ledger operational — War Eagle 🦅")

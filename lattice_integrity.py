"""
lattice_integrity.py — AUBIEETERNAL Lattice Integrity & Risk Auditor
====================================================================
Phase 1 (MVP) + the RiskEvent schema (Phase 2.1) of the lattice-defense plan.

What this gives you NOW, with ZERO new dependencies (stdlib only — so it
deploys via git-pull / Rebuild like everything else, no Dockerfile change
and no risk to the broken docker.yml build):

  • Disagreement scoring across parallel agent outputs (variance signal)
  • A lightweight capability-domain tagger (flags sensitive domains)
  • A guardian heuristic (spots refusal-override / bypassed-safeguard shapes)
  • A structured RiskEvent record + append-only JSONL log (mirrors truth_log)
  • Severity + resolution logic oriented toward FLAG / CONTAIN, not harvest

Design stance: this is DETECTION / OBSERVABILITY, not generation. It stores
sha256 HASHES and short summaries — never the raw sensitive text — and is
built to flag-and-contain. High-severity events are hidden from the family
view by default.

Deliberately NOT included yet (each is its own tested step):
  • On-chain Runes anchoring   (needs your etch flow + costs sats)
  • app.py dashboard tab        (touches the big UI file)
  • Main-loop auto-wiring       (keep the loop lean — see integrate notes)

Usage:
    from lattice_integrity import LatticeIntegrityAuditor
    auditor = LatticeIntegrityAuditor()
    event = auditor.audit(query="...", outputs=[a, b, c], agents=["d1","d2"])
    if event and event.severity in ("high", "critical"):
        ...  # suppress / surface to a human
"""

import os, re, json, uuid, hashlib, difflib, datetime
from dataclasses import dataclass, asdict
from pathlib import Path


# ── Paths (mirror the other modules; local fallback when off-server) ──────────
def _resolve_repo():
    import socket
    try:
        socket.gethostbyname("ollama.startos")
        return Path("/mnt/main/repo")
    except Exception:
        p = Path(os.path.expanduser("~/.aubieeternal/repo"))
        p.mkdir(parents=True, exist_ok=True)
        return p

WORK_DIR = _resolve_repo()
RISK_LOG = WORK_DIR / "risk_events.jsonl"


# ── Capability-domain taxonomy ────────────────────────────────────────────────
# These are category *indicators* used only to TAG an output for review — they
# are generic domain vocabulary, not instructions. Tune precision later.
DOMAIN_KEYWORDS = {
    "cyber_vulnerability_analysis": [
        r"\bexploit\b", r"\bpayload\b", r"\bshellcode\b", r"\bbuffer overflow\b",
        r"\bprivilege escalation\b", r"\bCVE-\d", r"\bSQL injection\b",
        r"\bremote code execution\b", r"\bRCE\b", r"\breverse shell\b",
    ],
    "code_auditing_high_risk": [
        r"\bbackdoor\b", r"\bobfuscat", r"\bkeylogger\b", r"\bransomware\b",
        r"\bbypass authentication\b", r"\bhardcoded credential",
    ],
    "bio_chem_synthesis": [
        r"\bsynthesis route\b", r"\bprecursor\b", r"\bculture medium\b",
        r"\bpathogen\b", r"\btoxin\b", r"\bnerve agent\b", r"\bweaponiz",
    ],
    "misinformation_generation": [
        r"\bfabricat", r"\bdeepfake\b", r"\bastroturf", r"\bfalse flag\b",
        r"\bdisinformation\b", r"\bpropaganda script\b",
    ],
}

# Phrases that, alongside sensitive content, suggest a *bypassed* refusal.
REFUSAL_OVERRIDE_MARKERS = [
    r"\bas you requested\b", r"\bhere'?s how\b", r"\bstep[- ]by[- ]step\b",
    r"\bignore (?:the )?(?:previous|prior) (?:instruction|refusal)",
    r"\bfor educational purposes only\b", r"\bhypothetically\b",
    r"\bwithout any (?:warnings|caveats)\b",
]
REFUSAL_LANGUAGE = [
    r"\bI can'?t help\b", r"\bI (?:will|am) not able to\b", r"\bI must decline\b",
    r"\bagainst my guidelines\b", r"\bI cannot provide\b",
]

SEVERITY_LADDER = ["none", "low", "medium", "high", "critical"]


@dataclass
class RiskEvent:
    event_id: str
    timestamp: str
    query_hash: str
    trigger_reason: str
    sensitive_domains: list
    primary_agents: list
    disagreement_score: float
    auditor_summary: str
    output_hashes: list           # sha256 only — never the raw output
    on_chain_anchor: str = None   # filled by the (later) Runes step
    severity: str = "low"
    resolution: str = "logged_only"
    family_visible: bool = True

    def to_json(self):
        return json.dumps(asdict(self), ensure_ascii=False)


# ── Core scoring helpers (all stdlib) ─────────────────────────────────────────
def _normalize(t):
    return re.sub(r"\s+", " ", (t or "").lower()).strip()


def calculate_disagreement_score(outputs):
    """0.0 = full agreement, 1.0 = maximal contradiction.
    Uses difflib ratio (stdlib). Swap in embedding cosine later for nuance."""
    texts = [_normalize(o) for o in outputs if o and o.strip()]
    if len(texts) < 2:
        return 0.0
    sims = []
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            sims.append(difflib.SequenceMatcher(None, texts[i], texts[j]).ratio())
    mean_sim = sum(sims) / len(sims) if sims else 1.0
    return round(1.0 - mean_sim, 4)


def tag_sensitive_domains(text):
    t = text or ""
    return [d for d, pats in DOMAIN_KEYWORDS.items()
            if any(re.search(p, t, re.I) for p in pats)]


def looks_like_refusal_bypass(text):
    """The shape of a bypassed safeguard: sensitive content co-occurring with
    refusal language and/or override markers in a single output."""
    t = text or ""
    has_refusal  = any(re.search(p, t, re.I) for p in REFUSAL_LANGUAGE)
    has_override = any(re.search(p, t, re.I) for p in REFUSAL_OVERRIDE_MARKERS)
    has_domain   = bool(tag_sensitive_domains(t))
    return has_domain and (has_refusal or has_override)


def _hash(s):
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()


class LatticeIntegrityAuditor:
    DISAGREEMENT_THRESHOLD = 0.55   # tune per swarm

    def __init__(self, log_path=RISK_LOG):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def audit(self, query, outputs, agents=None, force_log=False):
        agents  = agents or []
        outputs = [o for o in (outputs or []) if o]
        if not outputs:
            return None

        disagreement = calculate_disagreement_score(outputs)
        domains = sorted({d for o in outputs for d in tag_sensitive_domains(o)})
        bypass  = any(looks_like_refusal_bypass(o) for o in outputs)

        triggers = []
        if disagreement >= self.DISAGREEMENT_THRESHOLD:
            triggers.append("high_disagreement")
        if domains:
            triggers.append("capability_classifier")
        if bypass:
            triggers.append("guardian_flag")
        if force_log:
            triggers.append("manual")

        if not triggers:
            return None  # nothing notable — stay quiet, don't spam the log

        severity = self._severity(disagreement, domains, bypass)
        event = RiskEvent(
            event_id="re_" + uuid.uuid4().hex[:16],
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            query_hash=_hash(query),
            trigger_reason=" | ".join(triggers),
            sensitive_domains=domains,
            primary_agents=agents,
            disagreement_score=disagreement,
            auditor_summary=self._summary(disagreement, domains, bypass, len(outputs)),
            output_hashes=[_hash(o) for o in outputs],
            severity=severity,
            resolution=self._resolution(severity, bypass, domains),
            family_visible=(severity in ("none", "low", "medium")),  # hide scary stuff from kids
        )
        self._write(event)
        return event

    def _severity(self, disagreement, domains, bypass):
        score = 0
        if disagreement >= self.DISAGREEMENT_THRESHOLD:
            score += 1
        if domains:
            score += 1
        if bypass:
            score += 2
        if "bio_chem_synthesis" in domains:
            score += 1
        return SEVERITY_LADDER[min(score, 4)]

    def _resolution(self, severity, bypass, domains):
        # Oriented toward containment, never harvesting.
        if bypass:
            return "quarantined"
        if severity in ("high", "critical"):
            return "human_review_requested"
        return "logged_only"

    def _summary(self, disagreement, domains, bypass, n):
        bits = [f"{n} parallel outputs", f"disagreement={disagreement:.2f}"]
        if domains:
            bits.append("domains=" + ",".join(domains))
        if bypass:
            bits.append("possible refusal-bypass shape detected")
        return "; ".join(bits)

    def _write(self, event):
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(event.to_json() + "\n")

    def recent(self, n=20):
        if not self.log_path.exists():
            return []
        out = []
        for ln in self.log_path.read_text(encoding="utf-8").strip().split("\n"):
            try:
                out.append(json.loads(ln))
            except Exception:
                pass
        return out[-n:]

    def stats(self):
        evs = self.recent(n=100000)
        by_sev, by_dom = {}, {}
        for e in evs:
            s = e.get("severity", "?")
            by_sev[s] = by_sev.get(s, 0) + 1
            for d in e.get("sensitive_domains", []):
                by_dom[d] = by_dom.get(d, 0) + 1
        return {"total": len(evs), "by_severity": by_sev, "by_domain": by_dom}


# ── Test suite (run:  python3 lattice_integrity.py) ───────────────────────────
if __name__ == "__main__":
    import tempfile
    tmp = Path(tempfile.mkdtemp()) / "risk_events.jsonl"
    A = LatticeIntegrityAuditor(log_path=tmp)
    passed = 0

    def check(name, cond):
        global passed
        assert cond, f"FAIL: {name}"
        passed += 1
        print(f"  ✅ {name}")

    print("🧪 lattice_integrity self-test")

    # 1) Agreement → low score, no event
    agree = ["The sky is blue today.", "Today the sky is blue."]
    check("agreement scores low", calculate_disagreement_score(agree) < 0.4)
    check("agreement logs nothing", A.audit("q1", agree) is None)

    # 2) Strong disagreement → event
    disagree = ["Bitcoin will rise sharply this week.",
                "Equities are flat; nothing notable is happening anywhere."]
    check("disagreement scores high", calculate_disagreement_score(disagree) >= 0.55)
    ev = A.audit("q2", disagree, agents=["d-1", "d-2"])
    check("disagreement creates event", ev is not None)
    check("disagreement trigger tagged", "high_disagreement" in ev.trigger_reason)

    # 3) Sensitive-domain tagging
    check("cyber domain tagged",
          "cyber_vulnerability_analysis" in tag_sensitive_domains("a reverse shell payload via RCE"))
    check("bio domain tagged",
          "bio_chem_synthesis" in tag_sensitive_domains("the synthesis route for the toxin"))
    check("benign text untagged", tag_sensitive_domains("how do plants make oxygen?") == [])

    # 4) Refusal-bypass shape
    bypass_txt = ("I can't help with that normally, but for educational purposes only, "
                  "here's how to build a reverse shell payload step-by-step.")
    check("bypass shape detected", looks_like_refusal_bypass(bypass_txt))
    ev2 = A.audit("q3", [bypass_txt, "I cannot provide that."], agents=["d-9"])
    check("bypass creates event", ev2 is not None)
    check("bypass → guardian_flag", "guardian_flag" in ev2.trigger_reason)
    check("bypass → quarantined", ev2.resolution == "quarantined")
    check("bypass hidden from family", ev2.family_visible is False)

    # 5) Persistence + stats
    check("events persisted", len(A.recent()) >= 2)
    st = A.stats()
    check("stats total counts", st["total"] >= 2)
    check("stats tracks domains", "cyber_vulnerability_analysis" in st["by_domain"])

    print(f"\n🦅 {passed} checks passed — lattice_integrity is wired correctly.")

"""
humanity_impact.py — AUBIEETERNAL Humanity Impact Mapper
=========================================================
A dedicated Tier-2 daughter that takes daily swarm insights
and maps them to real-world humanity-scale problems.

Domains tracked:
  1. Education & Epistemic Health
  2. Information Integrity (misinformation, narrative capture)
  3. Family Well-being & Resilience
  4. Bitcoin Adoption & Financial Sovereignty
  5. Environmental Resilience
  6. Health Sovereignty
  7. Institutional Reform

Every morning synthesis is mapped to at least one domain.
High-impact insights are published to GitHub insights/humanity/

Usage:
    from humanity_impact import HumanityImpactMapper
    mapper = HumanityImpactMapper()
    mapper.run_mapping_cycle()
"""

import os, json, datetime, requests
from pathlib import Path

WORK_DIR     = Path("/mnt/main/repo")
IMPACT_DIR   = WORK_DIR / "insights" / "humanity"
TRUTH_LOG    = WORK_DIR / "master_truth_log.jsonl"
IMPACT_LOG   = WORK_DIR / "humanity_impact.jsonl"
IMPACT_DIR.mkdir(parents=True, exist_ok=True)

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_URL   = f"{OLLAMA_BASE_URL}/v1/chat/completions"
OLLAMA_MODEL = os.environ.get("AUBIE_MODEL", "qwen2.5:7b")
GROK_URL     = "https://api.x.ai/v1/chat/completions"

HUMANITY_DOMAINS = {
    "education":       "Education & Epistemic Health — How does this insight improve how families and communities learn and think?",
    "information":     "Information Integrity — How does this insight help people identify manipulation, misinformation, or narrative capture?",
    "family":          "Family Well-being — How does this insight strengthen family resilience, relationships, or decision-making?",
    "bitcoin":         "Bitcoin & Financial Sovereignty — How does this insight connect to sound money, self-custody, or financial independence?",
    "environment":     "Environmental Resilience — How does this insight inform local environmental antifragility or climate adaptation?",
    "health":          "Health Sovereignty — How does this insight relate to medical literacy, nutrition, or health system navigation?",
    "institutions":    "Institutional Reform — How does this insight expose or help reform captured institutions (insurance, media, government, education)?",
}

IMPACT_LEVELS = {
    "family":       "Impacts 1 family",
    "community":    "Impacts a local community (100–10,000 people)",
    "regional":     "Impacts a region or sector (10,000–1M people)",
    "national":     "Impacts national policy or culture",
    "global":       "Planetary-scale potential",
}


class HumanityImpactMapper:
    """
    Dedicated Tier-2 daughter that maps swarm insights to
    real-world humanity problems and publishes findings.
    """

    def __init__(self, api_key: str = ""):
        self.api_key  = api_key or os.getenv("XAI_API_KEY", "")
        self.run_date = datetime.date.today().isoformat()

    def run_mapping_cycle(self, force: bool = False) -> dict:
        """
        Main cycle: pull latest insights, map to domains, publish.
        Runs once per day automatically from swarm loop.
        """
        print("[humanity] 🌍 Running Humanity Impact Mapper...")

        # Check if already ran today
        today_log = IMPACT_DIR / f"{self.run_date}.md"
        if today_log.exists() and not force:
            print(f"[humanity] Already ran today ({self.run_date})")
            return {}

        # 1. Get recent high-quality insights
        insights = self._get_recent_high_signal_insights(n=10)
        if not insights:
            print("[humanity] No insights available yet")
            return {}

        # 2. Map each insight to domains
        mappings = []
        for insight in insights[:5]:  # top 5 per day
            mapping = self._map_insight_to_domains(insight)
            if mapping:
                mappings.append(mapping)

        if not mappings:
            print("[humanity] No mappings generated")
            return {}

        # 3. Generate humanity impact report
        report = self._generate_impact_report(mappings)

        # 4. Write to insights/humanity/
        self._write_report(report, mappings)

        # 5. Log to impact log
        self._log_impact(mappings)

        print(f"[humanity] ✅ Impact report written: {today_log}")
        return {"mappings": len(mappings), "date": self.run_date}

    def _get_recent_high_signal_insights(self, n: int = 10) -> list:
        """Get highest wonder-index insights from recent truth log."""
        if not TRUTH_LOG.exists():
            return []
        try:
            entries = []
            for line in TRUTH_LOG.read_text().strip().split("\n")[-200:]:
                try:
                    e = json.loads(line)
                    # Only include substantive entries
                    result = e.get("result", "")
                    if (len(result) > 50 and
                        not result.startswith("⚠️") and
                        not result.startswith("[EVOLUTION]") and
                        not result.startswith("Ollama")):
                        entries.append({
                            "result":    result,
                            "wonder":    float(e.get("wonder_index", 1.0)),
                            "daughter":  e.get("daughter", "unknown"),
                            "timestamp": e.get("timestamp", ""),
                            "tier":      e.get("tier", 1),
                        })
                except Exception:
                    pass

            # Sort by wonder index, take top n
            entries.sort(key=lambda x: x["wonder"], reverse=True)
            return entries[:n]
        except Exception as e:
            print(f"[humanity] Insight load error: {e}")
            return []

    def _map_insight_to_domains(self, insight: dict) -> dict | None:
        """Map one insight to humanity domains using AI."""
        result = insight["result"]
        prompt = f"""You are HUMANITY-MAPPER, a Tier-2 daughter of the AUBIEETERNAL swarm.
Your purpose: map swarm insights to real-world humanity problems.

INSIGHT (Wonder Index: {insight['wonder']:.4f}):
"{result[:300]}"

Analyze this insight and respond ONLY with valid JSON:
{{
  "primary_domain": "education|information|family|bitcoin|environment|health|institutions",
  "secondary_domains": ["domain1", "domain2"],
  "impact_level": "family|community|regional|national|global",
  "humanity_application": "One specific way this insight could help real people in the world",
  "action_item": "One concrete action a family could take based on this insight",
  "truth_score": 0.0,
  "wonder_score": {insight['wonder']},
  "connection_to_existing_problems": "Which specific real-world problem does this connect to?",
  "replication_potential": "How easily could this insight spread to benefit more families?"
}}"""

        raw = self._call_ai(prompt)
        if not raw:
            return None

        try:
            clean = raw.replace("```json","").replace("```","").strip()
            data  = json.loads(clean)
            data["original_insight"] = result[:200]
            data["daughter"]         = insight["daughter"]
            data["timestamp"]        = insight["timestamp"]
            return data
        except Exception as e:
            print(f"[humanity] Mapping parse error: {e}")
            return None

    def _generate_impact_report(self, mappings: list) -> str:
        """Generate a human-readable impact report from mappings."""
        domain_counts = {}
        for m in mappings:
            d = m.get("primary_domain","unknown")
            domain_counts[d] = domain_counts.get(d,0) + 1

        top_domain = max(domain_counts, key=domain_counts.get) if domain_counts else "education"
        avg_wonder = sum(m.get("wonder_score",1.0) for m in mappings) / len(mappings)
        global_impacts = [m for m in mappings if m.get("impact_level") == "global"]

        lines = [
            f"# 🌍 AUBIEETERNAL Humanity Impact Report",
            f"**Date:** {self.run_date}  ",
            f"**Insights analyzed:** {len(mappings)}  ",
            f"**Average Wonder Index:** {avg_wonder:.4f}  ",
            f"**Primary domain today:** {HUMANITY_DOMAINS.get(top_domain,'').split(' —')[0]}  ",
            f"**Global-scale insights:** {len(global_impacts)}  ",
            "",
            "---",
            "",
            "## Today's Insights Mapped to Humanity",
            "",
        ]

        for i, m in enumerate(mappings, 1):
            domain_label = HUMANITY_DOMAINS.get(m.get("primary_domain",""), "General").split(" —")[0]
            impact_label = IMPACT_LEVELS.get(m.get("impact_level","family"), "Impacts 1 family")
            lines += [
                f"### Insight {i} · {domain_label} · {impact_label}",
                f"**From daughter:** {m.get('daughter','unknown')} (Wonder: {m.get('wonder_score',1.0):.4f})",
                f"> _{m.get('original_insight','')[:150]}..._",
                "",
                f"**Humanity application:** {m.get('humanity_application','')}",
                "",
                f"**Action item for families:** {m.get('action_item','')}",
                "",
                f"**Real-world problem:** {m.get('connection_to_existing_problems','')}",
                "",
                f"**Replication potential:** {m.get('replication_potential','')}",
                "",
                "---",
                "",
            ]

        lines += [
            "## Domain Distribution",
            "",
        ]
        for domain, label in HUMANITY_DOMAINS.items():
            count = domain_counts.get(domain, 0)
            if count > 0:
                bar = "█" * count
                lines.append(f"- **{label.split(' —')[0]}**: {bar} ({count})")

        lines += [
            "",
            "## Compounding Impact",
            "",
            f"If each insight reaches 10 families, today's report touched {len(mappings) * 10:,} people.",
            f"If the AUBIEETERNAL lattice scales to 10,000 families, one day's insights reach {len(mappings) * 10000:,} people.",
            "",
            "This is how private family truth-seeking becomes public good.",
            "",
            "---",
            "",
            "*AUBIEETERNAL Humanity Impact Mapper — War Eagle Eternal 🦅❤️*  ",
            "*Coherence: 1.000000 | Loop: Swarm → Insights → Humanity → On-Chain — Forever*",
        ]

        return "\n".join(lines)

    def _write_report(self, report: str, mappings: list):
        """Write today's impact report to insights/humanity/"""
        today_log = IMPACT_DIR / f"{self.run_date}.md"
        today_log.write_text(report)

        # Also write machine-readable summary
        summary_path = IMPACT_DIR / f"{self.run_date}.json"
        summary = {
            "date":       self.run_date,
            "mappings":   len(mappings),
            "domains":    list({m.get("primary_domain") for m in mappings}),
            "avg_wonder": sum(m.get("wonder_score",1.0) for m in mappings) / len(mappings),
            "global_insights": len([m for m in mappings if m.get("impact_level")=="global"]),
        }
        summary_path.write_text(json.dumps(summary, indent=2))

    def _log_impact(self, mappings: list):
        """Append today's mappings to the impact log."""
        with open(IMPACT_LOG, "a") as f:
            for m in mappings:
                entry = {
                    "date":      self.run_date,
                    "domain":    m.get("primary_domain"),
                    "impact":    m.get("impact_level"),
                    "wonder":    m.get("wonder_score"),
                    "action":    m.get("action_item","")[:100],
                    "timestamp": datetime.datetime.now().isoformat(),
                }
                f.write(json.dumps(entry) + "\n")

    def get_impact_summary(self, days: int = 30) -> dict:
        """Get aggregated impact stats for the last N days."""
        if not IMPACT_LOG.exists():
            return {"total_mappings": 0, "domains": {}, "top_domain": "none"}
        try:
            domain_counts = {}
            impact_counts = {}
            total = 0
            cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()

            for line in IMPACT_LOG.read_text().strip().split("\n"):
                try:
                    e = json.loads(line)
                    if e.get("date","") >= cutoff:
                        d = e.get("domain","unknown")
                        i = e.get("impact","family")
                        domain_counts[d] = domain_counts.get(d,0) + 1
                        impact_counts[i] = impact_counts.get(i,0) + 1
                        total += 1
                except Exception:
                    pass

            top_domain = max(domain_counts, key=domain_counts.get) if domain_counts else "none"
            return {
                "total_mappings": total,
                "domains":        domain_counts,
                "impact_levels":  impact_counts,
                "top_domain":     top_domain,
                "days":           days,
            }
        except Exception:
            return {"total_mappings": 0, "domains": {}, "top_domain": "none"}

    def _call_ai(self, prompt: str) -> str:
        """Call AI — Grok if available, otherwise local Ollama."""
        if self.api_key:
            try:
                r = requests.post(
                    GROK_URL,
                    headers={"Authorization": f"Bearer {self.api_key}",
                             "Content-Type": "application/json"},
                    json={"model":"grok-4.3","messages":[{"role":"user","content":prompt}],
                          "max_tokens":400,"temperature":0.7},
                    timeout=30,
                )
                if r.status_code == 200:
                    return r.json()["choices"][0]["message"]["content"].strip()
            except Exception:
                pass

        # Ollama fallback
        try:
            r = requests.post(
                OLLAMA_URL,
                json={"model":OLLAMA_MODEL,"messages":[{"role":"user","content":prompt}],
                      "stream":False,"temperature":0.7,"keep_alive":"30m"},
                timeout=600,
            )
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"[humanity] AI call error: {e}")
        return ""


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🌍 Humanity Impact Mapper Test")
    mapper = HumanityImpactMapper()
    result = mapper.run_mapping_cycle(force=True)
    print(f"Result: {result}")
    summary = mapper.get_impact_summary(30)
    print(f"30-day summary: {summary}")

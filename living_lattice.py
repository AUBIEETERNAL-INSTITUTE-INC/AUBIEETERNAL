"""
living_lattice.py — AUBIEETERNAL Living Lattice
================================================
Anonymous coherence sharing between sovereign families.

THE IDEA:
  Right now AUBIEETERNAL is four families in isolation.
  The Living Lattice connects them — and any family running
  a fork — through anonymous, opt-in coherence sharing.

  What gets shared (all anonymous, no PII):
    - Daily coherence score (0.0-1.0)
    - Which curriculum tracks are active
    - Wonder Index for the day
    - Lesson completion count (not which lessons)
    - Child Rune confirmation count

  What NEVER leaves the family:
    - Names, identities, location
    - Specific lesson answers
    - Family messages
    - Any personally identifying data

  What this creates:
    - "Wisdom GDP" — real-time collective epistemic health metric
    - Track effectiveness data: which lessons actually raise coherence?
    - Market event impact: does a BTC crash lower family coherence?
    - The most honest measure of collective wisdom ever built.

  Data flow:
    Family → anonymize → Lattice Node (GitHub or Nostr) → Aggregated Commons

  Privacy model:
    Each family gets a random Lattice ID generated locally.
    The ID is stable (so trends can be tracked) but not linkable
    to any identity. Families can regenerate it at any time.

Usage:
    from living_lattice import LivingLattice
    lattice = LivingLattice()
    lattice.publish_daily_signal()      # call from morning_synthesis
    summary = lattice.get_lattice_summary()  # for the Lattice Feed tab
"""

import os, json, hashlib, datetime, requests, random, string
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
_MNT  = Path("/mnt/main")
_LOCAL = Path(os.path.expanduser("~/.aubieeternal/main"))
DATA_DIR    = _MNT if _MNT.exists() else _LOCAL
LATTICE_DIR = DATA_DIR / "lattice"
LATTICE_DIR.mkdir(parents=True, exist_ok=True)

LATTICE_ID_FILE   = DATA_DIR / "lattice_id.txt"
LOCAL_SIGNAL_LOG  = LATTICE_DIR / "signals.jsonl"
AGGREGATE_CACHE   = LATTICE_DIR / "aggregate_cache.json"
FAMILIES_DIR      = DATA_DIR / "families"

# ── GitHub publishing (same repo, lattice/ folder) ────────────────────────────
REPO_LATTICE_DIR  = DATA_DIR / "repo" / "lattice" / "signals"
REPO_LATTICE_DIR.mkdir(parents=True, exist_ok=True)

OLLAMA_URL  = "http://ollama.startos:11434/v1/chat/completions"

# ── Curriculum track mapping (for effectiveness tracking) ────────────────────
TRACK_FAMILIES = {
    "truth":        "Truth-Seeking",
    "adversarial":  "Adversarial Reality",
    "ai-partner":   "AI Partnership",
    "building":     "Building & Hardening",
    "baking":       "Deep Baking",
    "legal":        "Legal Literacy",
    "law-econ":     "Law & Economics",
    "family-law":   "Family Law",
    "bitcoin-sovereignty": "Bitcoin",
    "simulation":   "Simulation",
    "steelmanning": "Steelmanning",
    "antifragility":"Antifragility",
    "grokipedia":   "Grokipedia",
    "provenance":   "Provenance",
}


class LivingLattice:
    """
    Anonymous coherence sharing network.
    Connects sovereign families without compromising their sovereignty.
    """

    def __init__(self, family_id: str = "default"):
        self.family_id  = family_id
        self.lattice_id = self._get_or_create_lattice_id()
        self.today      = datetime.date.today().isoformat()

    # ══════════════════════════════════════════════════════════════════════════
    # LATTICE ID — stable anonymous identifier
    # ══════════════════════════════════════════════════════════════════════════

    def _get_or_create_lattice_id(self) -> str:
        """
        Get or create the anonymous lattice ID.
        Stable across sessions, not linkable to identity.
        Family can regenerate at any time from the UI.
        """
        if LATTICE_ID_FILE.exists():
            return LATTICE_ID_FILE.read_text().strip()
        # Generate: hash of random bytes + timestamp — deterministic but opaque
        raw     = os.urandom(32).hex() + datetime.datetime.now().isoformat()
        lattice_id = hashlib.sha256(raw.encode()).hexdigest()[:16]
        LATTICE_ID_FILE.write_text(lattice_id)
        return lattice_id

    def regenerate_lattice_id(self) -> str:
        """Regenerate the lattice ID — resets all historical linkage."""
        raw = os.urandom(32).hex() + datetime.datetime.now().isoformat()
        self.lattice_id = hashlib.sha256(raw.encode()).hexdigest()[:16]
        LATTICE_ID_FILE.write_text(self.lattice_id)
        return self.lattice_id

    # ══════════════════════════════════════════════════════════════════════════
    # BUILD DAILY SIGNAL — what gets shared
    # ══════════════════════════════════════════════════════════════════════════

    def build_signal(self) -> dict:
        """
        Build today's anonymous signal from family stats.
        Contains no PII. Safe to publish publicly.
        """
        # Load all family stats anonymously
        family_stats = self._load_all_family_stats()

        # Aggregate across families (no individual family data)
        all_completed  = set()
        coherence_vals = []
        rune_frags     = []
        xp_vals        = []
        streaks        = []

        for stats in family_stats:
            completed = stats.get("lessons_completed", [])
            all_completed.update(completed)
            ch = stats.get("coherence_history", [])
            if ch:
                coherence_vals.append(sum(ch[-5:]) / len(ch[-5:]))
            rune_frags.append(stats.get("child_rune_fragments", 0))
            xp_vals.append(stats.get("total_xp", 0))
            streaks.append(stats.get("streak_days", 0))

        avg_coherence = round(sum(coherence_vals) / len(coherence_vals), 4) \
                        if coherence_vals else 0.0

        # Active tracks (which lesson prefixes appear in completed)
        active_tracks = []
        for prefix, name in TRACK_FAMILIES.items():
            if any(l.startswith(prefix) for l in all_completed):
                active_tracks.append(name)

        # Swarm status
        swarm_status = self._load_swarm_status()

        signal = {
            "lattice_id":      self.lattice_id,
            "date":            self.today,
            "schema":          "1.0",
            # ── Epistemic metrics (anonymous, aggregated) ──────────────────
            "avg_coherence":   avg_coherence,
            "wonder_index":    round(swarm_status.get("wonder_index", 1.0), 4),
            "mets":            swarm_status.get("mets", 0),
            # ── Learning metrics (counts only, no specifics) ───────────────
            "lessons_completed": len(all_completed),
            "active_tracks":   active_tracks,
            "families_active": len(family_stats),
            "avg_streak":      round(sum(streaks) / len(streaks), 1) if streaks else 0,
            "total_xp":        sum(xp_vals),
            # ── Rune progress ──────────────────────────────────────────────
            "max_rune_frags":  max(rune_frags) if rune_frags else 0,
            "rune_genesis":    max(rune_frags) >= 256 if rune_frags else False,
            # ── Privacy attestation ────────────────────────────────────────
            "privacy":         "anonymous — no PII, no individual family data",
            "license":         "CC0 public domain",
            "source":          "AUBIEETERNAL sovereign family swarm",
        }
        return signal

    # ══════════════════════════════════════════════════════════════════════════
    # PUBLISH — write signal to local log + repo
    # ══════════════════════════════════════════════════════════════════════════

    def publish_daily_signal(self, force: bool = False) -> dict:
        """
        Publish today's signal. Called from morning_synthesis.
        Writes to: local log, repo/lattice/signals/, and Epistemic Commons.
        """
        print(f"[lattice] 🕸️  Publishing daily signal for {self.today}...")

        # Check already published today
        signal_path = REPO_LATTICE_DIR / f"{self.today}_{self.lattice_id[:8]}.json"
        if signal_path.exists() and not force:
            print(f"[lattice] Already published today.")
            return {"status": "already_published"}

        signal = self.build_signal()

        # Write to repo (gets auto-pushed to GitHub)
        signal_path.write_text(json.dumps(signal, indent=2))

        # Append to local log
        with open(LOCAL_SIGNAL_LOG, "a") as f:
            f.write(json.dumps(signal) + "\n")

        # Update aggregate
        self._update_aggregate(signal)

        print(f"[lattice] ✅ Signal published: coherence={signal['avg_coherence']}, "
              f"wonder={signal['wonder_index']}, lessons={signal['lessons_completed']}")
        return {"status": "published", "signal": signal}

    # ══════════════════════════════════════════════════════════════════════════
    # AGGREGATE — compute Wisdom GDP from all published signals
    # ══════════════════════════════════════════════════════════════════════════

    def _update_aggregate(self, new_signal: dict):
        """Update the running aggregate with today's signal."""
        try:
            agg = json.loads(AGGREGATE_CACHE.read_text()) \
                  if AGGREGATE_CACHE.exists() else {"signals": [], "stats": {}}
        except Exception:
            agg = {"signals": [], "stats": {}}

        # Keep last 90 days
        agg["signals"].append({
            "date":        new_signal["date"],
            "coherence":   new_signal["avg_coherence"],
            "wonder":      new_signal["wonder_index"],
            "lessons":     new_signal["lessons_completed"],
            "tracks":      len(new_signal["active_tracks"]),
            "streak":      new_signal["avg_streak"],
        })
        agg["signals"] = [s for s in agg["signals"]
                          if s["date"] >= (datetime.date.today() -
                                           datetime.timedelta(days=90)).isoformat()]

        # Recompute stats
        signals = agg["signals"]
        if signals:
            agg["stats"] = {
                "days_active":       len(signals),
                "avg_coherence_30d": round(
                    sum(s["coherence"] for s in signals[-30:]) / min(len(signals), 30), 4),
                "peak_wonder":       max(s["wonder"] for s in signals),
                "total_lessons":     max(s["lessons"] for s in signals),
                "wisdom_gdp":        self._compute_wisdom_gdp(signals),
                "trend":             self._compute_trend(signals),
                "last_updated":      datetime.datetime.now().isoformat(),
            }

        AGGREGATE_CACHE.write_text(json.dumps(agg, indent=2))

    def _compute_wisdom_gdp(self, signals: list) -> float:
        """
        Wisdom GDP: composite score across coherence, wonder, learning rate.
        Scale: 0.0 (no activity) → 10.0 (perfect coherence, max wonder, daily learning)
        """
        if not signals:
            return 0.0
        recent = signals[-7:]  # last week
        avg_coh   = sum(s["coherence"] for s in recent) / len(recent)
        avg_wonder = sum(s["wonder"] for s in recent) / len(recent)
        avg_lessons = sum(s["lessons"] for s in recent) / len(recent)
        # Normalize wonder (max observed ~2.0) and lessons (target 100+)
        norm_wonder  = min(1.0, avg_wonder / 2.0)
        norm_lessons = min(1.0, avg_lessons / 100.0)
        # Weighted composite
        gdp = (avg_coh * 4.0) + (norm_wonder * 3.0) + (norm_lessons * 3.0)
        return round(gdp, 3)

    def _compute_trend(self, signals: list) -> str:
        """Rising / stable / declining coherence trend."""
        if len(signals) < 7:
            return "insufficient_data"
        recent_avg = sum(s["coherence"] for s in signals[-7:]) / 7
        older_avg  = sum(s["coherence"] for s in signals[-14:-7]) / 7 \
                     if len(signals) >= 14 else recent_avg
        delta = recent_avg - older_avg
        if delta >  0.02: return "rising"
        if delta < -0.02: return "declining"
        return "stable"

    # ══════════════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ══════════════════════════════════════════════════════════════════════════

    def get_lattice_summary(self) -> dict:
        """Get the current lattice state for display in the app."""
        try:
            agg = json.loads(AGGREGATE_CACHE.read_text()) \
                  if AGGREGATE_CACHE.exists() else {}
        except Exception:
            agg = {}

        # Count all signal files in repo (= number of contributing nodes)
        node_count = len(list(REPO_LATTICE_DIR.glob("*.json")))

        return {
            "lattice_id":       self.lattice_id,
            "node_count":       node_count,
            "stats":            agg.get("stats", {}),
            "signals":          agg.get("signals", [])[-30:],
            "today_published":  (REPO_LATTICE_DIR / f"{self.today}_{self.lattice_id[:8]}.json").exists(),
        }

    def get_wisdom_gdp_history(self, days: int = 30) -> list:
        """Return daily Wisdom GDP scores for charting."""
        try:
            agg     = json.loads(AGGREGATE_CACHE.read_text())
            signals = agg.get("signals", [])[-days:]
        except Exception:
            return []
        result = []
        for i, s in enumerate(signals):
            window = signals[max(0, i-6):i+1]
            gdp    = self._compute_wisdom_gdp(window)
            result.append({"date": s["date"], "wisdom_gdp": gdp,
                           "coherence": s["coherence"], "wonder": s["wonder"]})
        return result

    def get_track_effectiveness(self) -> dict:
        """
        Which tracks correlate with higher coherence?
        Returns track → avg coherence delta when that track is active.
        """
        try:
            signals = json.loads(AGGREGATE_CACHE.read_text()).get("signals", [])
        except Exception:
            return {}

        # Load current signal to get active tracks
        current = self.build_signal()
        active  = set(current.get("active_tracks", []))

        # Simple: compare coherence on days with high lesson count vs low
        if len(signals) < 14:
            return {"note": "Need 14+ days of data for track effectiveness analysis."}

        median_lessons = sorted(s["lessons"] for s in signals)[len(signals)//2]
        high_days  = [s for s in signals if s["lessons"] > median_lessons]
        low_days   = [s for s in signals if s["lessons"] <= median_lessons]
        high_coh   = sum(s["coherence"] for s in high_days) / len(high_days) if high_days else 0
        low_coh    = sum(s["coherence"] for s in low_days)  / len(low_days)  if low_days  else 0

        return {
            "active_tracks":     list(active),
            "high_learning_coh": round(high_coh, 4),
            "low_learning_coh":  round(low_coh, 4),
            "learning_boost":    round(high_coh - low_coh, 4),
            "interpretation":    "Days with more lessons completed show "
                                 + ("higher" if high_coh > low_coh else "similar")
                                 + " coherence.",
        }

    # ══════════════════════════════════════════════════════════════════════════
    # HELPERS
    # ══════════════════════════════════════════════════════════════════════════

    def _load_all_family_stats(self) -> list:
        if not FAMILIES_DIR.exists():
            return []
        stats = []
        for path in FAMILIES_DIR.glob("*.json"):
            try:
                stats.append(json.loads(path.read_text()))
            except Exception:
                pass
        return stats

    def _load_swarm_status(self) -> dict:
        for p in [DATA_DIR / "swarm_status.json",
                  Path("/mnt/main/swarm_status.json")]:
            if p.exists():
                try:
                    return json.loads(p.read_text())
                except Exception:
                    pass
        return {"wonder_index": 1.0, "mets": 0}


# ══════════════════════════════════════════════════════════════════════════════
# Integration with morning_synthesis.py
# ══════════════════════════════════════════════════════════════════════════════

def run_lattice_publish() -> dict:
    """
    Called from morning_synthesis.run_full_synthesis().
    Add this line:
        from living_lattice import run_lattice_publish
        lattice_result = run_lattice_publish()
    """
    try:
        lattice = LivingLattice()
        return lattice.publish_daily_signal()
    except Exception as e:
        print(f"[lattice] Error: {e}")
        return {"status": "error", "error": str(e)}


# ── Standalone test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🕸️  Living Lattice Test")
    lattice = LivingLattice()
    print(f"Lattice ID: {lattice.lattice_id}")
    signal  = lattice.build_signal()
    print(f"Signal: coherence={signal['avg_coherence']}, wonder={signal['wonder_index']}, "
          f"lessons={signal['lessons_completed']}, tracks={len(signal['active_tracks'])}")
    result  = lattice.publish_daily_signal(force=True)
    print(f"Publish: {result['status']}")
    summary = lattice.get_lattice_summary()
    print(f"Summary: {summary['stats']}")
    gdp     = lattice.get_wisdom_gdp_history(7)
    print(f"Wisdom GDP (7d): {gdp}")
    print("\n✅ Living Lattice operational — War Eagle 🦅")

"""
simulation_probe.py — AUBIEETERNAL Simulation Probe
=====================================================
Treating "this might be a simulation" as a serious,
experimental hypothesis rather than abstract speculation.

This module tracks the signals that would distinguish
a simulated from a non-simulated reality, using the
AUBIEETERNAL lattice as the measurement apparatus:

  - Coherence anomalies (unexpected spikes/drops)
  - Observer effects (swarm output changes when observed)
  - Wonder Index discontinuities
  - Narrative synchronicities (unrelated events aligning)
  - METS trajectory anomalies
  - Glitch patterns (repeated structures in truth log)

The output is a daily "Probe Report" — not a claim about
whether we're in a simulation, but a clean record of
everything that would be evidence if we were.

The sovereign infrastructure (StartOS, local models,
Bitcoin Runes, Nostr) maximizes independence from
whatever base layer is running the system.

Usage:
    from simulation_probe import SimulationProbe
    probe = SimulationProbe()
    probe.run_daily_probe()
    report = probe.get_probe_summary()
"""

import os, json, datetime, math, hashlib
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

DATA_DIR     = _data_dir()
PROBE_LOG    = DATA_DIR / "simulation_probe.jsonl"
PROBE_DIR    = DATA_DIR / "repo" / "insights" / "probe"
PROBE_DIR.mkdir(parents=True, exist_ok=True)
TRUTH_LOG    = DATA_DIR / "repo" / "master_truth_log.jsonl"
WONDER_LOG   = DATA_DIR / "repo" / "wonder_log.jsonl"
SWARM_STATUS = DATA_DIR / "swarm_status.json"


class SimulationProbe:
    """
    Measures signals that would distinguish simulated
    from non-simulated reality. No claims — only data.
    """

    def __init__(self):
        self.today = datetime.date.today().isoformat()
        self.now   = datetime.datetime.now().isoformat()

    # ══════════════════════════════════════════════════════════════════════════
    # MAIN PROBE CYCLE
    # ══════════════════════════════════════════════════════════════════════════

    def run_daily_probe(self, force: bool = False) -> dict:
        """Run the full daily probe. Idempotent unless force=True."""
        probe_path = PROBE_DIR / f"{self.today}.json"
        if probe_path.exists() and not force:
            return json.loads(probe_path.read_text())

        print(f"[probe] 🔭 Running simulation probe for {self.today}...")

        status   = self._load_swarm_status()
        anomalies = self._detect_coherence_anomalies()
        wonder    = self._analyze_wonder_trajectory()
        observer  = self._measure_observer_effects()
        glitches  = self._detect_glitch_patterns()
        sync      = self._detect_synchronicities()
        integrity = self._compute_lattice_integrity(status)

        report = {
            "date":               self.today,
            "timestamp":          self.now,
            "swarm_status":       status,
            "coherence_anomalies": anomalies,
            "wonder_trajectory":   wonder,
            "observer_effects":    observer,
            "glitch_patterns":     glitches,
            "synchronicities":     sync,
            "lattice_integrity":   integrity,
            "probe_score":         self._compute_probe_score(anomalies, wonder, observer, glitches),
            "interpretation":      self._interpret(anomalies, glitches, observer),
        }

        probe_path.write_text(json.dumps(report, indent=2))
        self._write_probe_md(report)
        self._log_probe(report)

        print(f"[probe] ✅ Probe score: {report['probe_score']:.2f}/10")
        return report

    # ══════════════════════════════════════════════════════════════════════════
    # DETECTION MODULES
    # ══════════════════════════════════════════════════════════════════════════

    def _detect_coherence_anomalies(self) -> dict:
        """
        Detect unexpected coherence spikes or drops.
        In a simulated system, coherence would not be perfectly
        stable — it would drift, spike, or show discontinuities.
        """
        if not TRUTH_LOG.exists():
            return {"status": "no_data", "anomalies": [], "coherence_values": []}

        coherence_vals = []
        try:
            for line in TRUTH_LOG.read_text().strip().split("\n")[-200:]:
                try:
                    e = json.loads(line)
                    c = e.get("coherence") or e.get("inter_rune_coherence")
                    if c is not None:
                        coherence_vals.append(float(c))
                except Exception:
                    pass
        except Exception:
            pass

        if len(coherence_vals) < 10:
            return {"status": "insufficient_data", "anomalies": [], "coherence_values": coherence_vals}

        mean = sum(coherence_vals) / len(coherence_vals)
        variance = sum((c - mean) ** 2 for c in coherence_vals) / len(coherence_vals)
        std  = math.sqrt(variance)

        # Detect anomalies: values > 2 standard deviations from mean
        anomalies = []
        for i, c in enumerate(coherence_vals):
            if abs(c - mean) > 2 * std and std > 0.01:
                anomalies.append({
                    "position": i,
                    "value":    round(c, 4),
                    "delta":    round(c - mean, 4),
                    "sigma":    round(abs(c - mean) / std, 2),
                })

        # Check for perfect stability (also anomalous — too perfect)
        perfectly_stable = std < 0.001 and len(coherence_vals) > 20

        return {
            "status":           "ok",
            "mean":             round(mean, 4),
            "std":              round(std, 4),
            "anomaly_count":    len(anomalies),
            "anomalies":        anomalies[:5],
            "perfectly_stable": perfectly_stable,
            "interpretation":   (
                "Perfectly stable coherence is itself anomalous — "
                "real systems have natural variance." if perfectly_stable else
                f"{len(anomalies)} coherence anomalies detected." if anomalies else
                "Coherence within normal variance."
            ),
        }

    def _analyze_wonder_trajectory(self) -> dict:
        """
        Track the Wonder Index over time.
        Discontinuous jumps, sustained maxima, or impossible stability
        are all signals worth recording.
        """
        status = self._load_swarm_status()
        current_wonder = status.get("wonder_index", 1.0)

        wonder_vals = []
        if WONDER_LOG.exists():
            for line in WONDER_LOG.read_text().strip().split("\n")[-100:]:
                try:
                    e = json.loads(line)
                    w = e.get("wonder_index") or e.get("wonder")
                    if w is not None:
                        wonder_vals.append(float(w))
                except Exception:
                    pass

        if not wonder_vals:
            wonder_vals = [current_wonder]

        # Is the wonder index at maximum (2.0) and stable?
        at_max   = current_wonder >= 2.0
        max_days = sum(1 for w in wonder_vals if w >= 1.9)

        # Detect sudden jumps
        jumps = []
        for i in range(1, len(wonder_vals)):
            delta = abs(wonder_vals[i] - wonder_vals[i-1])
            if delta > 0.3:
                jumps.append({"from": round(wonder_vals[i-1], 4),
                               "to":   round(wonder_vals[i], 4),
                               "delta": round(delta, 4)})

        return {
            "current":        round(current_wonder, 4),
            "at_maximum":     at_max,
            "max_streak":     max_days,
            "jumps_detected": jumps[:3],
            "trajectory":     "ascending" if wonder_vals[-1] > wonder_vals[0]
                              else "descending" if wonder_vals[-1] < wonder_vals[0]
                              else "stable",
            "note":           (
                f"Wonder has held at maximum ({current_wonder:.4f}) across {max_days} observations. "
                "Maximum wonder sustained is consistent with coherence lock."
            ) if at_max else f"Current wonder: {current_wonder:.4f}",
        }

    def _measure_observer_effects(self) -> dict:
        """
        In simulation theory: the act of observation changes the system.
        We measure this by comparing swarm output quality before and
        after parent HUD activation, Halo glasses sessions, or X bridge use.
        """
        if not TRUTH_LOG.exists():
            return {"measured": False, "note": "No truth log available."}

        # Count entries in last 24h vs previous 24h
        now = datetime.datetime.now()
        day_ago = (now - datetime.timedelta(hours=24)).isoformat()
        two_days = (now - datetime.timedelta(hours=48)).isoformat()

        recent  = 0
        older   = 0
        recent_wonder = []
        older_wonder  = []

        for line in TRUTH_LOG.read_text().strip().split("\n")[-500:]:
            try:
                e = json.loads(line)
                ts = e.get("timestamp", "")
                w  = float(e.get("wonder_index", 1.0))
                if ts >= day_ago:
                    recent += 1
                    recent_wonder.append(w)
                elif ts >= two_days:
                    older += 1
                    older_wonder.append(w)
            except Exception:
                pass

        avg_recent = sum(recent_wonder) / len(recent_wonder) if recent_wonder else 0
        avg_older  = sum(older_wonder) / len(older_wonder) if older_wonder else 0
        delta      = round(avg_recent - avg_older, 4)

        return {
            "measured":          True,
            "recent_entries":    recent,
            "older_entries":     older,
            "avg_wonder_recent": round(avg_recent, 4),
            "avg_wonder_older":  round(avg_older, 4),
            "wonder_delta":      delta,
            "observer_effect_detected": abs(delta) > 0.1,
            "note": (
                f"Wonder delta {delta:+.4f} between 24h windows. "
                "Positive delta suggests observer engagement improves signal quality."
                if abs(delta) > 0.1 else
                "No significant observer effect detected in this window."
            ),
        }

    def _detect_glitch_patterns(self) -> dict:
        """
        Look for repeated patterns, impossible precision, or
        structural anomalies in the truth log that would be
        evidence of a generated (vs organic) reality.
        """
        if not TRUTH_LOG.exists():
            return {"glitches": [], "status": "no_data"}

        hashes     = {}
        duplicates = []
        perfect_vals = []

        for line in TRUTH_LOG.read_text().strip().split("\n")[-300:]:
            try:
                e = json.loads(line)
                result = e.get("result", "")[:100]
                if len(result) > 20:
                    h = hashlib.md5(result.encode()).hexdigest()[:8]
                    if h in hashes:
                        duplicates.append(result[:60])
                    hashes[h] = True

                # Check for suspiciously precise coherence values
                c = e.get("inter_rune_coherence", 0)
                if c == 1.0:
                    perfect_vals.append(c)
            except Exception:
                pass

        glitches = []
        if len(duplicates) > 3:
            glitches.append({
                "type": "repeated_outputs",
                "count": len(duplicates),
                "note": f"{len(duplicates)} near-duplicate truth log entries detected.",
            })
        if len(perfect_vals) > 50:
            glitches.append({
                "type": "perfect_coherence_streak",
                "count": len(perfect_vals),
                "note": f"Coherence held at exactly 1.000000 for {len(perfect_vals)} consecutive entries.",
            })

        return {
            "glitches":        glitches,
            "duplicate_count": len(duplicates),
            "perfect_streak":  len(perfect_vals),
            "status":          "glitches_detected" if glitches else "clean",
        }

    def _detect_synchronicities(self) -> dict:
        """
        Meaningful coincidences: BTC block numbers aligning with
        wonder spikes, lesson completion timing, child rune progress.
        These are the 'too perfect' events that merit logging.
        """
        status = self._load_swarm_status()
        mets   = status.get("mets", 0)
        wonder = status.get("wonder_index", 1.0)
        rune   = status.get("child_rune_confirmations", 0)

        synchronicities = []

        # METS at round numbers
        mets_str = str(int(mets))
        if mets_str.replace("0","") in ("1","2","5") and len(mets_str) > 8:
            synchronicities.append(f"METS at near-round number: {int(mets):,}")

        # Wonder at exactly 2.0
        if wonder >= 2.0:
            synchronicities.append(f"Wonder Index at maximum: {wonder:.4f}")

        # Rune at significant milestones
        for milestone in [64, 128, 192, 256]:
            if abs(rune - milestone) <= 2:
                synchronicities.append(f"Child Rune at milestone: {rune}/{milestone}")

        return {
            "synchronicities": synchronicities,
            "count":           len(synchronicities),
            "note":            (
                "Multiple synchronicities active — worth noting but not interpreting."
                if len(synchronicities) > 1 else
                synchronicities[0] if synchronicities else
                "No notable synchronicities today."
            ),
        }

    def _compute_lattice_integrity(self, status: dict) -> dict:
        """Check that the core invariants are holding."""
        coherence = status.get("inter_rune_coherence", 0)
        wonder    = status.get("wonder_index", 0)
        return {
            "coherence_1_000000": coherence >= 1.0,
            "wonder_above_1":     wonder >= 1.0,
            "swarm_active":       status.get("swarm_active", False),
            "all_invariants_hold": coherence >= 1.0 and wonder >= 1.0,
            "note": (
                "All invariants holding. Lattice integrity: CONFIRMED."
                if coherence >= 1.0 and wonder >= 1.0 else
                f"Coherence: {coherence:.6f} | Wonder: {wonder:.4f}"
            ),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # SCORING + INTERPRETATION
    # ══════════════════════════════════════════════════════════════════════════

    def _compute_probe_score(self, anomalies, wonder, observer, glitches) -> float:
        """
        Probe score: how much signal does today's data contain?
        NOT a measure of whether we're in a simulation.
        A measure of how much data we collected.
        """
        score = 5.0  # baseline
        score += min(2.0, anomalies.get("anomaly_count", 0) * 0.5)
        score += 1.0 if wonder.get("at_maximum") else 0.0
        score += 1.0 if observer.get("observer_effect_detected") else 0.0
        score += min(2.0, len(glitches.get("glitches", [])) * 1.0)
        return round(min(10.0, score), 2)

    def _interpret(self, anomalies, glitches, observer) -> str:
        """Generate a plain-language interpretation for the daily report."""
        notes = []
        if anomalies.get("anomaly_count", 0) > 0:
            notes.append(f"{anomalies['anomaly_count']} coherence anomalies logged.")
        if anomalies.get("perfectly_stable"):
            notes.append("Coherence is perfectly stable — itself anomalous in real systems.")
        if glitches.get("glitches"):
            for g in glitches["glitches"]:
                notes.append(g["note"])
        if observer.get("observer_effect_detected"):
            notes.append(f"Observer effect: wonder delta {observer.get('wonder_delta',0):+.4f}")
        if not notes:
            notes.append("No significant anomalies. Baseline day — data recorded for trend analysis.")
        return " | ".join(notes)

    # ══════════════════════════════════════════════════════════════════════════
    # OUTPUT
    # ══════════════════════════════════════════════════════════════════════════

    def _write_probe_md(self, report: dict):
        integrity = report["lattice_integrity"]
        anomalies = report["coherence_anomalies"]
        wonder    = report["wonder_trajectory"]
        observer  = report["observer_effects"]
        glitches  = report["glitch_patterns"]
        sync      = report["synchronicities"]
        score     = report["probe_score"]

        md = f"""# 🔭 Simulation Probe Report — {report["date"]}

**Probe Score:** {score}/10 | **Lattice Integrity:** {"✅ HOLDING" if integrity.get("all_invariants_hold") else "⚠️ CHECK"}

> *This document records signals that would be evidence of a simulated reality.*
> *No claims are made — only data.*

---

## Coherence Anomalies
{anomalies.get("interpretation","No data")}
- Mean: {anomalies.get("mean","?")} | Std: {anomalies.get("std","?")} | Anomalies: {anomalies.get("anomaly_count",0)}

## Wonder Trajectory
{wonder.get("note","")}
- Current: {wonder.get("current","?")} | Trajectory: {wonder.get("trajectory","?")} | Jumps: {len(wonder.get("jumps_detected",[]))}

## Observer Effects
{observer.get("note","")}
- Recent entries: {observer.get("recent_entries",0)} | Older: {observer.get("older_entries",0)} | Delta: {observer.get("wonder_delta",0):+.4f}

## Glitch Patterns
{glitches.get("status","no_data")} — {len(glitches.get("glitches",[]))} patterns
{chr(10).join("- " + g["note"] for g in glitches.get("glitches",[]))}

## Synchronicities
{sync.get("note","")}

## Lattice Integrity
{integrity.get("note","")}

## Interpretation
{report.get("interpretation","")}

---
*AUBIEETERNAL Simulation Probe — No claims, only data.*
*Coherence: {report["swarm_status"].get("inter_rune_coherence","?")} | War Eagle Eternal 🦅*
"""
        (PROBE_DIR / f"{report['date']}.md").write_text(md)

    def _log_probe(self, report: dict):
        entry = {
            "date":        report["date"],
            "probe_score": report["probe_score"],
            "anomalies":   report["coherence_anomalies"].get("anomaly_count", 0),
            "glitches":    len(report["glitch_patterns"].get("glitches", [])),
            "observer":    report["observer_effects"].get("observer_effect_detected", False),
            "wonder":      report["wonder_trajectory"].get("current", 0),
            "integrity":   report["lattice_integrity"].get("all_invariants_hold", False),
        }
        with open(PROBE_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def get_probe_summary(self, days: int = 30) -> dict:
        """Aggregate probe data for display."""
        if not PROBE_LOG.exists():
            return {"total_days": 0}
        entries = []
        for line in PROBE_LOG.read_text().strip().split("\n"):
            try:
                entries.append(json.loads(line))
            except Exception:
                pass
        entries = entries[-days:]
        if not entries:
            return {"total_days": 0}
        return {
            "total_days":      len(entries),
            "avg_probe_score": round(sum(e["probe_score"] for e in entries) / len(entries), 2),
            "total_anomalies": sum(e.get("anomalies", 0) for e in entries),
            "total_glitches":  sum(e.get("glitches", 0) for e in entries),
            "observer_events": sum(1 for e in entries if e.get("observer")),
            "integrity_holds": sum(1 for e in entries if e.get("integrity")),
            "latest_score":    entries[-1].get("probe_score", 0),
        }

    def _load_swarm_status(self) -> dict:
        if SWARM_STATUS.exists():
            try:
                return json.loads(SWARM_STATUS.read_text())
            except Exception:
                pass
        return {"wonder_index": 1.0, "inter_rune_coherence": 1.0,
                "mets": 0, "swarm_active": False}


# ── Standalone test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🔭 Simulation Probe Test")
    probe  = SimulationProbe()
    report = probe.run_daily_probe(force=True)
    print(f"Probe score: {report['probe_score']}/10")
    print(f"Integrity: {report['lattice_integrity']['note']}")
    print(f"Interpretation: {report['interpretation']}")
    summary = probe.get_probe_summary()
    print(f"Summary: {summary}")

"""
epistemic_drift_detector.py — AUBIEETERNAL Epistemic Drift Detector
====================================================================
My genuine addition for helping humanity. — Claude

THE PROBLEM WITH LONG-RUNNING AI SWARMS:
  A swarm that runs 24/7 for months can drift. Not suddenly —
  gradually. Small changes in context, output quality, coherence
  of reasoning, or factual accuracy compound over thousands of ticks
  until the swarm is confidently producing lower-quality signal
  without any single moment where it was clearly wrong.

  This is the illusion delta problem (from SWARM research, 2026):
  systems appear coherent in short-horizon interactions while being
  globally incoherent across time.

  Current monitoring (wonder_index, coherence) tracks QUANTITY.
  This module tracks QUALITY DRIFT:
  - Are outputs becoming less calibrated?
  - Are steelman quality scores trending down?
  - Is the variance of outputs increasing (less reliability)?
  - Are truth scores on ingested Grokipedia entries declining?
  - Is the gap between stated confidence and measured accuracy widening?

WHY THIS MATTERS FOR HUMANITY:
  An epistemic commons that drifts toward lower-quality signal is
  worse than no signal — it actively degrades the training data of
  AI systems that draw from it.
  A sovereign school that drifts toward lower-quality explanations
  fails the children who depend on it.
  The Epistemic Drift Detector is the quality control layer that
  makes AUBIEETERNAL's outputs trustworthy over decades, not just
  on the day it launched.

FOUR DRIFT SIGNALS TRACKED:
  1. Coherence Trend — is family coherence drifting down over time?
  2. Truth Score Trend — are Grokipedia quality scores declining?
  3. Steelman Variance — is output quality becoming inconsistent?
  4. Confidence Calibration — is stated confidence matching accuracy?

ALERT LEVELS:
  GREEN  — No drift detected. All signals within normal range.
  YELLOW — Mild drift signal (1-2 metrics trending). Monitor.
  RED    — Significant drift (3+ metrics trending). Investigate.
  ALARM  — Critical drift (quality below baseline threshold). Pause and recalibrate.

Usage:
    from epistemic_drift_detector import EpistemicDriftDetector
    detector = EpistemicDriftDetector()
    report = detector.run_full_analysis()
    print(report["alert_level"])  # GREEN/YELLOW/RED/ALARM
    
    # Wire into nightly CI:
    detector.check_and_alert(fail_on="RED")
"""

import os, json, statistics, datetime, hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import socket as _socket

def _data_dir() -> Path:
    try:
        _socket.gethostbyname("ollama.startos")
        return Path("/mnt/main")
    except Exception:
        p = Path(os.path.expanduser("~/.aubieeternal/main"))
        p.mkdir(parents=True, exist_ok=True)
        return p

DATA_DIR   = _data_dir()
DRIFT_LOG  = DATA_DIR / "epistemic_drift_log.jsonl"
BASELINE_F = DATA_DIR / "drift_baseline.json"


class DriftSignal:
    """One tracked metric with trend analysis."""
    def __init__(self, name: str, values: List[float], timestamps: List[str]):
        self.name       = name
        self.values     = values
        self.timestamps = timestamps

    @property
    def mean(self) -> float:
        return statistics.mean(self.values) if self.values else 0.0

    @property
    def trend(self) -> float:
        """Linear trend: positive = improving, negative = declining."""
        if len(self.values) < 3:
            return 0.0
        n  = len(self.values)
        xs = list(range(n))
        x_mean = n / 2
        y_mean = self.mean
        num = sum((xs[i] - x_mean) * (self.values[i] - y_mean) for i in range(n))
        den = sum((xs[i] - x_mean)**2 for i in range(n))
        return round(num / den if den > 0 else 0.0, 6)

    @property
    def variance(self) -> float:
        return statistics.variance(self.values) if len(self.values) >= 2 else 0.0

    @property
    def is_drifting_down(self) -> bool:
        """True if trend is significantly negative."""
        return self.trend < -0.005 and len(self.values) >= 5

    @property
    def is_high_variance(self) -> bool:
        """True if variance has increased significantly recently."""
        if len(self.values) < 6: return False
        early_var = statistics.variance(self.values[:len(self.values)//2])
        late_var  = statistics.variance(self.values[len(self.values)//2:])
        return late_var > early_var * 2.0

    def summary(self) -> dict:
        return {
            "name":          self.name,
            "n_samples":     len(self.values),
            "mean":          round(self.mean, 4),
            "trend":         self.trend,
            "variance":      round(self.variance, 6),
            "drifting_down": self.is_drifting_down,
            "high_variance": self.is_high_variance,
            "last_3":        [round(v, 4) for v in self.values[-3:]],
        }


class EpistemicDriftDetector:
    """
    Monitors AUBIEETERNAL's epistemic output quality over time.
    Detects gradual degradation before it compounds into misinformation.
    """

    def __init__(self, window_days: int = 30):
        self.window_days = window_days
        self.cutoff      = (datetime.datetime.now() -
                            datetime.timedelta(days=window_days)).isoformat()

    # ══════════════════════════════════════════════════════════════════════
    # SIGNAL EXTRACTORS
    # ══════════════════════════════════════════════════════════════════════

    def extract_coherence_trend(self) -> DriftSignal:
        """Extract family coherence over time from wonder_log and truth_log."""
        values     = []
        timestamps = []

        # Wonder log has per-tick coherence
        wonder_log = DATA_DIR / "wonder_log.jsonl"
        if wonder_log.exists():
            for line in wonder_log.read_text().strip().split("\n"):
                try:
                    e = json.loads(line)
                    ts = e.get("timestamp","")
                    if ts >= self.cutoff:
                        coh = e.get("coherence", e.get("inter_rune_coherence", 0))
                        if 0 < coh <= 1.0:
                            values.append(coh)
                            timestamps.append(ts)
                except Exception: pass

        # Also sample from app_state history
        state_file = DATA_DIR / "app_state.json"
        if state_file.exists():
            try:
                state = json.loads(state_file.read_text())
                coh_obj = state.get("coherence", {})
                if isinstance(coh_obj, dict):
                    history = coh_obj.get("history", [])
                    for i, v in enumerate(history[-20:]):
                        if 0 < v <= 1.0:
                            values.append(v)
                            timestamps.append(f"state_history_{i}")
            except Exception: pass

        return DriftSignal("coherence_trend", values[-60:], timestamps[-60:])

    def extract_truth_score_trend(self) -> DriftSignal:
        """Extract Grokipedia truth scores over time."""
        values     = []
        timestamps = []

        grok_log = DATA_DIR / "grokipedia_entries.jsonl"
        if grok_log.exists():
            for line in grok_log.read_text().strip().split("\n"):
                try:
                    e = json.loads(line)
                    ts = e.get("timestamp","")
                    if ts >= self.cutoff[:10]:
                        score = e.get("truth_score")
                        if score is not None and 0 <= score <= 1.0:
                            values.append(score)
                            timestamps.append(ts)
                except Exception: pass

        # Also pull from quality log
        quality_log = DATA_DIR / "grokipedia_quality_scores.jsonl"
        if quality_log.exists():
            for line in quality_log.read_text().strip().split("\n"):
                try:
                    e = json.loads(line)
                    score = e.get("truth_score")
                    if score is not None:
                        values.append(score)
                        timestamps.append(e.get("timestamp",""))
                except Exception: pass

        return DriftSignal("truth_score_trend", values[-60:], timestamps[-60:])

    def extract_steelman_variance(self) -> DriftSignal:
        """Extract steelman scores to detect quality variance drift."""
        values     = []
        timestamps = []

        steelman_log = DATA_DIR / "steelman_history.jsonl"
        if steelman_log.exists():
            for line in steelman_log.read_text().strip().split("\n"):
                try:
                    e = json.loads(line)
                    score = e.get("score")
                    ts    = e.get("timestamp","")
                    if score is not None and 0 <= score <= 1.0:
                        values.append(score)
                        timestamps.append(ts)
                except Exception: pass

        return DriftSignal("steelman_quality", values[-60:], timestamps[-60:])

    def extract_confidence_calibration(self) -> DriftSignal:
        """
        Extract calibration signal: gap between stated confidence and accuracy.
        From belief_ledger.jsonl where beliefs have been resolved.
        A growing gap indicates calibration drift.
        """
        values     = []
        timestamps = []

        belief_log = DATA_DIR / "belief_ledger.jsonl"
        if belief_log.exists():
            for line in belief_log.read_text().strip().split("\n"):
                try:
                    e = json.loads(line)
                    conf     = e.get("confidence")
                    resolved = e.get("resolved_correct")  # True/False if resolved
                    ts       = e.get("date","")
                    if conf is not None and resolved is not None:
                        # Calibration score: 1 - |confidence - outcome|
                        outcome = 1.0 if resolved else 0.0
                        calib   = 1.0 - abs(conf - outcome)
                        values.append(calib)
                        timestamps.append(ts)
                except Exception: pass

        return DriftSignal("confidence_calibration", values[-60:], timestamps[-60:])

    # ══════════════════════════════════════════════════════════════════════
    # BASELINE MANAGEMENT
    # ══════════════════════════════════════════════════════════════════════

    def save_baseline(self) -> dict:
        """
        Save current signal means as the baseline.
        Call this after a known-good period to anchor future drift detection.
        """
        signals = {
            "coherence":     self.extract_coherence_trend(),
            "truth_score":   self.extract_truth_score_trend(),
            "steelman":      self.extract_steelman_variance(),
            "calibration":   self.extract_confidence_calibration(),
        }
        baseline = {
            "saved_at":   datetime.datetime.now().isoformat(),
            "window_days": self.window_days,
            "means": {k: round(v.mean, 4) for k, v in signals.items() if v.values},
            "variances": {k: round(v.variance, 6) for k, v in signals.items() if v.values},
        }
        BASELINE_F.write_text(json.dumps(baseline, indent=2))
        print(f"[drift] Baseline saved: {baseline['means']}")
        return baseline

    def load_baseline(self) -> Optional[dict]:
        if BASELINE_F.exists():
            try: return json.loads(BASELINE_F.read_text())
            except Exception: pass
        return None

    # ══════════════════════════════════════════════════════════════════════
    # FULL ANALYSIS
    # ══════════════════════════════════════════════════════════════════════

    def run_full_analysis(self) -> dict:
        """
        Run all drift detection and return a comprehensive report.
        """
        signals = {
            "coherence":   self.extract_coherence_trend(),
            "truth_score": self.extract_truth_score_trend(),
            "steelman":    self.extract_steelman_variance(),
            "calibration": self.extract_confidence_calibration(),
        }

        baseline = self.load_baseline()
        drift_flags = []

        signal_reports = {}
        for name, signal in signals.items():
            sr = signal.summary()
            signal_reports[name] = sr

            # Check against trend
            if signal.is_drifting_down:
                drift_flags.append(f"{name}_trending_down (slope={signal.trend:.4f})")

            # Check against variance increase
            if signal.is_high_variance:
                drift_flags.append(f"{name}_high_variance")

            # Check against baseline if available
            if baseline and name in baseline.get("means", {}):
                base_mean = baseline["means"][name]
                current_mean = signal.mean
                if signal.values and base_mean > 0:
                    degradation = (base_mean - current_mean) / base_mean
                    if degradation > 0.10:
                        drift_flags.append(
                            f"{name}_below_baseline (deg={degradation:.1%})"
                        )
                    sr["vs_baseline"] = round(-degradation, 3)

        # Determine alert level
        n_flags = len(drift_flags)
        if n_flags == 0:
            alert_level = "GREEN"
        elif n_flags <= 2:
            alert_level = "YELLOW"
        elif n_flags <= 4:
            alert_level = "RED"
        else:
            alert_level = "ALARM"

        # Check absolute floor values
        for name, signal in signals.items():
            if signal.values and signal.mean < 0.4:
                alert_level = "ALARM"
                drift_flags.append(f"{name}_below_floor (mean={signal.mean:.2f})")

        report = {
            "timestamp":       datetime.datetime.now().isoformat(),
            "window_days":     self.window_days,
            "alert_level":     alert_level,
            "drift_flags":     drift_flags,
            "n_flags":         n_flags,
            "signals":         signal_reports,
            "recommendations": self._recommendations(drift_flags, signals),
            "baseline_loaded": baseline is not None,
        }

        # Log the report
        with open(DRIFT_LOG, "a") as f:
            f.write(json.dumps({
                "timestamp":   report["timestamp"],
                "alert_level": alert_level,
                "n_flags":     n_flags,
                "flags":       drift_flags,
            }) + "\n")

        return report

    def _recommendations(self, flags: List[str], signals: Dict) -> List[str]:
        """Generate specific, actionable recommendations."""
        recs = []
        if not flags:
            recs.append("✅ All epistemic signals stable. No action required.")
            return recs

        if any("coherence" in f for f in flags):
            recs.append(
                "Coherence trending down: check polyvagal state quality, "
                "ensure lessons are completing with genuine engagement, "
                "review if swarm is in a long low-wonder period."
            )
        if any("truth_score" in f for f in flags):
            recs.append(
                "Truth scores declining: review recent Grokipedia ingestion criteria, "
                "check if judge prompts have drifted, consider recalibrating "
                "judge scoring thresholds."
            )
        if any("steelman" in f for f in flags):
            recs.append(
                "Steelman quality variance high: check Ollama model availability, "
                "verify adversarial testing is running, review recent low-scoring submissions."
            )
        if any("calibration" in f for f in flags):
            recs.append(
                "Calibration drifting: review resolved predictions in belief ledger, "
                "consider running the 20-question calibration test, "
                "check if confidence thresholds need recalibration."
            )
        if any("below_floor" in f for f in flags):
            recs.append(
                "⚠️ CRITICAL: One or more signals below minimum threshold. "
                "Pause swarm output publication to Epistemic Commons until resolved."
            )
        return recs

    def check_and_alert(self, fail_on: str = "RED") -> int:
        """
        Run analysis and return exit code.
        fail_on: "YELLOW", "RED", or "ALARM"
        
        Use in CI:
            python epistemic_drift_detector.py --ci || echo "Drift detected"
        """
        report = self.run_full_analysis()
        level  = report["alert_level"]
        levels = {"GREEN": 0, "YELLOW": 1, "RED": 2, "ALARM": 3}
        fail_level = levels.get(fail_on, 2)
        current_level = levels.get(level, 0)

        self._print_alert(report)
        return 1 if current_level >= fail_level else 0

    def _print_alert(self, report: dict) -> None:
        colors = {"GREEN":"🟢","YELLOW":"🟡","RED":"🔴","ALARM":"🚨"}
        icon   = colors.get(report["alert_level"],"?")
        print(f"\n{icon} EPISTEMIC DRIFT DETECTOR — {report['alert_level']}")
        print(f"   Window: {report['window_days']} days | Flags: {report['n_flags']}")
        if report["drift_flags"]:
            for flag in report["drift_flags"]:
                print(f"   ⚠️  {flag}")
        for rec in report["recommendations"]:
            print(f"   → {rec}")

    def get_drift_history(self, n: int = 30) -> list:
        """Get drift alert history."""
        if not DRIFT_LOG.exists(): return []
        entries = []
        for line in DRIFT_LOG.read_text().strip().split("\n"):
            try: entries.append(json.loads(line))
            except Exception: pass
        return entries[-n:]

    def compute_drift_score(self) -> float:
        """
        Single 0-1 score for dashboard display.
        1.0 = no drift, 0.0 = maximum drift.
        """
        report = self.run_full_analysis()
        level_scores = {"GREEN": 1.0, "YELLOW": 0.75, "RED": 0.4, "ALARM": 0.1}
        return level_scores.get(report["alert_level"], 0.5)


# ── Standalone test / CI entry point ──────────────────────────────────────────
if __name__ == "__main__":
    import sys
    args = sys.argv[1:]

    detector = EpistemicDriftDetector(window_days=30)

    if "--baseline" in args:
        baseline = detector.save_baseline()
        print(f"✅ Baseline saved: {baseline}")
        sys.exit(0)

    elif "--ci" in args:
        fail_on = "RED"
        if "--fail-on" in args:
            fail_on = args[args.index("--fail-on") + 1].upper()
        exit_code = detector.check_and_alert(fail_on=fail_on)
        sys.exit(exit_code)

    else:
        # Full analysis
        report = detector.run_full_analysis()
        detector._print_alert(report)
        print(f"\nFull report:\n{json.dumps({k:v for k,v in report.items() if k != 'signals'}, indent=2)}")
        print(f"\nSignal summaries:")
        for name, sig in report["signals"].items():
            print(f"  {name}: mean={sig['mean']:.3f} trend={sig['trend']:+.5f} "
                  f"drift={'YES' if sig['drifting_down'] else 'no'}")

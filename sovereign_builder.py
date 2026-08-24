"""
sovereign_builder.py — AUBIEETERNAL Sovereign Builder Module
=============================================================
Tracks hardware upgrades, AI benchmarks, AR overlay hooks,
and humanitarian contributions for the Sovereign Builder curriculum.

The humanitarian mission: every graduate deploys one sovereign node
for a community that has none.

Usage:
    from sovereign_builder import SovereignBuilder
    b = SovereignBuilder("family_alpha")
    b.log_upgrade("RAM", "8GB to 32GB", before_score=40, after_score=78)
    b.log_benchmark("qwen2.5:14b", tokens_per_sec=18.4, ram_gb=8.2)
    b.log_contribution("hardware_setup", "Deployed node at Lincoln Elementary", people_reached=45)
"""

import os, json, hashlib, datetime
from pathlib import Path
import socket as _socket

def _data_dir() -> Path:
    try:
        _socket.gethostbyname("localhost")
        return Path("/mnt/main")
    except Exception:
        p = Path(os.path.expanduser("~/.aubieeternal/main"))
        p.mkdir(parents=True, exist_ok=True)
        return p

DATA_DIR       = _data_dir()
BUILDER_DIR    = DATA_DIR / "repo" / "builder"
BUILDER_DIR.mkdir(parents=True, exist_ok=True)
UPGRADES_LOG   = DATA_DIR / "hardware_upgrades.jsonl"
BENCHMARKS_LOG = DATA_DIR / "ai_benchmarks.jsonl"
CONTRIB_LOG    = DATA_DIR / "builder_contributions.jsonl"
CONFIG_FILE    = DATA_DIR / "sovereign_stack_config.json"

CONTRIBUTION_TYPES = {
    "hardware_setup":         {"desc": "Deploy a sovereign AI node for a community", "impact": 100, "rune_grant": 200},
    "curriculum_translation": {"desc": "Translate lessons for a new community",      "impact": 80,  "rune_grant": 150},
    "preference_data":        {"desc": "Generate high-quality AI preference data",   "impact": 60,  "rune_grant": 100},
    "infrastructure_docs":    {"desc": "Write setup documentation that helps others","impact": 50,  "rune_grant": 75},
    "teach_one_person":       {"desc": "Teach the Builder track to someone new",     "impact": 70,  "rune_grant": 120},
    "lattice_node_contribution": {"desc": "Contribute a sealed insight to the lattice","impact": 40, "rune_grant": 50},
}

AR_OVERLAYS = {
    "ram_installation": {
        "steps": ["Touch metal case (anti-static)", "Locate RAM slots (highlighted)",
                  "Press release clips outward", "Align notch with slot",
                  "Press firmly until clips click", "Boot and verify"],
        "xp_award": 100,
    },
    "nvme_installation": {
        "steps": ["Locate M.2 slot (highlighted)", "Remove retention screw",
                  "Insert drive at 30 degree angle", "Press flat and secure screw",
                  "Verify in BIOS on next boot"],
        "xp_award": 150,
    },
}

class SovereignBuilder:
    def __init__(self, family_id: str = "default"):
        self.family_id = family_id
        self.today     = datetime.date.today().isoformat()
        self._load_config()

    def _load_config(self):
        if CONFIG_FILE.exists():
            try: self.config = json.loads(CONFIG_FILE.read_text())
            except Exception: self.config = {}
        else:
            self.config = {"family_id": self.family_id, "hardware": {}, "models": [], "total_upgrades": 0}

    def log_upgrade(self, component: str, description: str,
                    before_score: float = 0, after_score: float = 0,
                    cost_usd: float = 0, notes: str = "") -> dict:
        uid = hashlib.sha256(f"{component}{self.today}".encode()).hexdigest()[:12]
        upgrade = {"upgrade_id": uid, "date": self.today, "family_id": self.family_id,
                   "component": component, "description": description,
                   "before_score": round(before_score,2), "after_score": round(after_score,2),
                   "improvement": round(after_score-before_score,2), "cost_usd": cost_usd, "notes": notes}
        with open(UPGRADES_LOG,"a") as f: f.write(json.dumps(upgrade)+"\n")
        self.config["hardware"][component] = description
        self.config["total_upgrades"] = self.config.get("total_upgrades",0)+1
        self._save_config()
        try:
            from rune_memory import RuneMemory
            RuneMemory().record(f"UPGRADE: {component} — {description} | score +{after_score-before_score:.0f}",
                                source="builder", coherence=0.85, tags=["hardware","upgrade"])
        except Exception: pass
        print(f"[builder] Upgrade: {component} +{after_score-before_score:.0f}")
        return upgrade

    def log_benchmark(self, model_name: str, tokens_per_sec: float,
                      ram_gb: float, quality_score: float = 0,
                      context_length: int = 4096, quantization: str = "q4_K_M") -> dict:
        bid = hashlib.sha256(f"{model_name}{self.today}".encode()).hexdigest()[:10]
        bench = {"bench_id": bid, "date": self.today, "family_id": self.family_id,
                 "model": model_name, "tokens_per_sec": round(tokens_per_sec,2),
                 "ram_gb": round(ram_gb,2), "quality_score": round(quality_score,2),
                 "context_length": context_length, "quantization": quantization}
        with open(BENCHMARKS_LOG,"a") as f: f.write(json.dumps(bench)+"\n")
        models = [m for m in self.config.get("models",[]) if m.get("model") != model_name]
        models.append({"model": model_name, "tokens_per_sec": tokens_per_sec, "ram_gb": ram_gb, "date": self.today})
        self.config["models"] = models
        self._save_config()
        print(f"[builder] Benchmark: {model_name} {tokens_per_sec:.1f} tok/s")
        return bench

    def log_contribution(self, contribution_type: str, description: str,
                         people_reached: int = 0, location: str = "",
                         seal: bool = True) -> dict:
        ctype = CONTRIBUTION_TYPES.get(contribution_type, {"impact":20,"rune_grant":25})
        cid = hashlib.sha256(f"{contribution_type}{self.today}".encode()).hexdigest()[:12]
        contrib = {"contrib_id": cid, "date": self.today, "family_id": self.family_id,
                   "type": contribution_type, "description": description[:400],
                   "people_reached": people_reached, "location": location,
                   "impact_score": ctype["impact"], "rune_grant": ctype["rune_grant"], "sealed": False}
        with open(CONTRIB_LOG,"a") as f: f.write(json.dumps(contrib)+"\n")
        if seal:
            try:
                from rune_memory import ShieldRune, RuneMemory
                eid = RuneMemory().record(f"CONTRIBUTION [{contribution_type}]: {description}\nPeople: {people_reached}",
                                          source="builder", coherence=0.90, tags=["humanitarian",contribution_type])
                sr = ShieldRune().seal(eid, note=f"Builder contribution: {contribution_type}", broadcaster=self.family_id)
                contrib["sealed"] = True; contrib["rune_anchor"] = sr.get("seal_hash","")[:24]
            except Exception: pass
        print(f"[builder] Contribution: {contribution_type} impact={ctype['impact']} people={people_reached}")
        return contrib

    def get_ar_overlay(self, context: str) -> dict:
        return AR_OVERLAYS.get(context, {"steps": [f"AR guide for {context} not yet defined"], "xp_award": 0})

    def get_live_telemetry(self) -> dict:
        t = {"ollama_running": False, "active_model": None, "tokens_per_sec": 0,
             "ram_used_gb": 0, "ram_total_gb": 0, "cpu_percent": 0}
        try:
            import requests
            r = requests.get("http://localhost:11434/api/tags", timeout=2)
            if r.status_code == 200:
                t["ollama_running"] = True
                models = r.json().get("models",[])
                if models: t["active_model"] = models[0].get("name","?")
        except Exception: pass
        try:
            import psutil
            mem = psutil.virtual_memory()
            t["ram_used_gb"] = round(mem.used/1e9,1); t["ram_total_gb"] = round(mem.total/1e9,1)
            t["cpu_percent"] = psutil.cpu_percent(interval=0.1)
        except Exception: pass
        return t

    def get_builder_stats(self) -> dict:
        upgrades = self._load_log(UPGRADES_LOG)
        benchmarks = self._load_log(BENCHMARKS_LOG)
        contribs = self._load_log(CONTRIB_LOG)
        best = max(benchmarks, key=lambda b: b.get("tokens_per_sec",0), default={})
        total_impact = sum(c.get("impact_score",0) for c in contribs)
        total_people = sum(c.get("people_reached",0) for c in contribs)
        level = self._calc_level(upgrades, contribs)
        return {"family_id": self.family_id, "builder_level": level,
                "total_upgrades": len(upgrades), "total_benchmarks": len(benchmarks),
                "total_contributions": len(contribs), "humanitarian_impact": total_impact,
                "people_reached": total_people, "best_model": best.get("model","none"),
                "best_tokens_sec": best.get("tokens_per_sec",0),
                "hardware_config": self.config.get("hardware",{}),
                "current_models": self.config.get("models",[])}

    def get_all_contributions(self) -> list:
        return self._load_log(CONTRIB_LOG)

    def get_optimal_model(self) -> dict:
        benchmarks = self._load_log(BENCHMARKS_LOG)
        telemetry  = self.get_live_telemetry()
        ram = telemetry.get("ram_total_gb", 16)
        if ram >= 64:   rec = "qwen2.5:32b — fits comfortably"
        elif ram >= 32: rec = "qwen2.5:14b — sweet spot"
        elif ram >= 16: rec = "qwen2.5:7b — good quality, fast"
        else:           rec = "qwen2.5:3b — RAM constrained"
        return {"recommendation": rec, "ram_gb": ram, "benchmarks_run": len(benchmarks)}

    def _calc_level(self, upgrades, contribs) -> int:
        score = len(upgrades)*10 + len(contribs)*25
        for threshold, level in [(300,8),(200,7),(150,6),(100,5),(60,4),(30,3),(10,2),(1,1)]:
            if score >= threshold: return level
        return 0

    def _load_log(self, path: Path) -> list:
        if not path.exists(): return []
        entries = []
        for line in path.read_text().strip().split("\n"):
            try:
                e = json.loads(line)
                if e.get("family_id") == self.family_id: entries.append(e)
            except Exception: pass
        return entries

    def _save_config(self):
        CONFIG_FILE.write_text(json.dumps(self.config, indent=2))


if __name__ == "__main__":
    b = SovereignBuilder("test")
    b.log_upgrade("RAM","8GB to 32GB",before_score=40,after_score=78)
    b.log_benchmark("qwen2.5:14b",tokens_per_sec=18.4,ram_gb=8.2,quality_score=8.5)
    b.log_contribution("hardware_setup","Deployed node at Lincoln Elementary",people_reached=45)
    stats = b.get_builder_stats()
    print(f"Level {stats['builder_level']} | impact={stats['humanitarian_impact']} | people={stats['people_reached']}")
    print("War Eagle Eternal")

"""
alumni_deployment_tracker.py — AUBIEETERNAL Alumni and Deployment Tracker
=========================================================================
Tracks graduates, their community deployments, and the growth of the
Living Lattice over time.

This is not vanity metrics. It answers the most important questions:
  - How many communities now have sovereign AI infrastructure that
    wouldn't have had it without AUBIEETERNAL?
  - How many children have access to this curriculum who wouldn't otherwise?
  - Is the Living Lattice growing, plateauing, or contracting?

Public endpoint: the alumni and deployment data is published (with consent)
to the Epistemic Commons, making the humanitarian impact of AUBIEETERNAL
publicly verifiable — just like the Bitcoin blockchain is verifiable.
"""

import os, json, datetime, uuid, hashlib
from pathlib import Path
from typing import Dict, List, Optional
import socket as _socket

def _data_dir() -> Path:
    try:
        _socket.gethostbyname("localhost")
        return Path("/mnt/main")
    except Exception:
        p = Path(os.path.expanduser("~/.aubieeternal/main"))
        p.mkdir(parents=True, exist_ok=True)
        return p

DATA_DIR      = _data_dir()
ALUMNI_LOG    = DATA_DIR / "alumni_registry.jsonl"
DEPLOY_LOG    = DATA_DIR / "deployment_registry.jsonl"
LATTICE_FILE  = DATA_DIR / "living_lattice.json"


# ── Alumni Registration ───────────────────────────────────────────────────────

class AlumniRegistry:
    """Track degree recipients and their ongoing contributions."""

    def register_graduate(
        self,
        family_id: str,
        student_name: str,
        degree_name: str,
        credits: int,
        coherence: float,
        capstone_summary: str = "",
        public_consent: bool = False,
    ) -> str:
        """Register a degree recipient. Returns alumni_id."""
        alumni_id  = hashlib.sha256(
            f"{family_id}{degree_name}{datetime.date.today()}".encode()
        ).hexdigest()[:16]

        record = {
            "alumni_id":        alumni_id,
            "family_id":        family_id if public_consent else f"anon_{alumni_id[:8]}",
            "student_name":     student_name if public_consent else "Anonymous Graduate",
            "degree_name":      degree_name,
            "credits":          credits,
            "coherence":        round(coherence, 4),
            "capstone_summary": capstone_summary,
            "graduated_at":     datetime.datetime.now().isoformat(),
            "public_consent":   public_consent,
        }

        with open(ALUMNI_LOG, "a") as f:
            f.write(json.dumps(record) + "\n")

        self._update_lattice_stats()
        return alumni_id

    def get_all_graduates(self, public_only: bool = False) -> List[Dict]:
        if not ALUMNI_LOG.exists():
            return []
        graduates = []
        for line in ALUMNI_LOG.read_text().strip().split("\n"):
            try:
                g = json.loads(line)
                if not public_only or g.get("public_consent"):
                    graduates.append(g)
            except Exception:
                pass
        return graduates

    def get_degree_counts(self) -> Dict[str, int]:
        graduates = self.get_all_graduates()
        counts: Dict[str, int] = {}
        for g in graduates:
            deg = g.get("degree_name", "Unknown")
            counts[deg] = counts.get(deg, 0) + 1
        return counts


# ── Deployment Tracker ────────────────────────────────────────────────────────

class DeploymentTracker:
    """Track community deployments of AUBIEETERNAL infrastructure."""

    DEPLOYMENT_TYPES = [
        "family_node",
        "school_deployment",
        "orphanage_deployment",
        "community_center",
        "library",
        "other",
    ]

    def log_deployment(
        self,
        deployer_family_id: str,
        deployment_type: str,
        location_desc: str,
        people_served: int,
        hardware_cost_usd: float = 0,
        services_deployed: Optional[List[str]] = None,
        notes: str = "",
        public_consent: bool = True,
    ) -> str:
        """Log a new deployment. Returns deployment_id."""
        deploy_id = str(uuid.uuid4())[:12]

        record = {
            "deployment_id":    deploy_id,
            "deployer_family":  deployer_family_id,
            "deployment_type":  deployment_type,
            "location_desc":    location_desc if public_consent else "Anonymous Location",
            "people_served":    people_served,
            "hardware_cost_usd": hardware_cost_usd,
            "services_deployed": services_deployed or ["AUBIEETERNAL", "Bitcoin Core"],
            "notes":            notes,
            "deployed_at":      datetime.datetime.now().isoformat(),
            "public_consent":   public_consent,
            "status":           "active",
        }

        with open(DEPLOY_LOG, "a") as f:
            f.write(json.dumps(record) + "\n")

        self._update_lattice_stats()
        return deploy_id

    def get_all_deployments(self, public_only: bool = False) -> List[Dict]:
        if not DEPLOY_LOG.exists():
            return []
        deployments = []
        for line in DEPLOY_LOG.read_text().strip().split("\n"):
            try:
                d = json.loads(line)
                if not public_only or d.get("public_consent"):
                    deployments.append(d)
            except Exception:
                pass
        return deployments

    def get_impact_summary(self) -> Dict:
        deployments = self.get_all_deployments()
        total_people = sum(d.get("people_served", 0) for d in deployments)
        type_counts: Dict[str, int] = {}
        for d in deployments:
            t = d.get("deployment_type", "other")
            type_counts[t] = type_counts.get(t, 0) + 1

        return {
            "total_deployments": len(deployments),
            "total_people_served": total_people,
            "by_type":           type_counts,
            "estimated_children": sum(
                d.get("people_served", 0) for d in deployments
                if d.get("deployment_type") in
                ["school_deployment", "orphanage_deployment", "community_center"]
            ),
        }

    def _update_lattice_stats(self):
        pass  # Called by AlumniRegistry too


# ── Living Lattice ─────────────────────────────────────────────────────────────

class LivingLattice:
    """
    The Living Lattice is the network of all AUBIEETERNAL families,
    nodes, and deployments. This class computes its current state
    and growth trajectory.
    """

    def __init__(self):
        self.alumni   = AlumniRegistry()
        self.deploys  = DeploymentTracker()

    def get_lattice_state(self) -> Dict:
        """Compute current state of the Living Lattice."""
        graduates   = self.alumni.get_all_graduates()
        deployments = self.deploys.get_all_deployments()
        impact      = self.deploys.get_impact_summary()
        degree_cts  = self.alumni.get_degree_counts()

        # Load swarm status for METS and wonder
        swarm_status: Dict = {}
        status_file = DATA_DIR / "swarm_status.json"
        if status_file.exists():
            try:
                swarm_status = json.loads(status_file.read_text())
            except Exception:
                pass

        state = {
            "computed_at":       datetime.datetime.now().isoformat(),
            "graduates": {
                "total":         len(graduates),
                "by_degree":     degree_cts,
            },
            "deployments":       impact,
            "swarm": {
                "mets":          swarm_status.get("mets", 0),
                "wonder_index":  swarm_status.get("wonder_index", 0),
                "coherence":     swarm_status.get("inter_rune_coherence", 0),
                "grokipedia":    swarm_status.get("grokipedia_count", 0),
            },
            "growth_metrics": {
                "people_served_per_node": (
                    impact["total_people_served"] / max(1, impact["total_deployments"])
                ),
                "deployment_chain_active": impact["total_deployments"] > 0,
            },
            "public_mission_progress": {
                "people_with_sovereign_education": impact["total_people_served"],
                "children_served_directly":        impact["estimated_children"],
                "communities_with_ai_infra":       impact["total_deployments"],
            },
        }

        # Save and publish
        LATTICE_FILE.write_text(json.dumps(state, indent=2))
        return state

    def export_for_epistemic_commons(self) -> Dict:
        """
        Export anonymized Lattice data for the public Epistemic Commons.
        This is the humanitarian impact report that anyone can read.
        """
        state  = self.get_lattice_state()
        public = {
            "schema_version":    "1.0",
            "institution":       "AUBIEETERNAL Sovereign University",
            "license":           "CC0",
            "report_date":       datetime.date.today().isoformat(),
            "humanitarian_impact": state["public_mission_progress"],
            "network_health": {
                "wonder_index":  state["swarm"]["wonder_index"],
                "coherence":     state["swarm"]["coherence"],
                "grokipedia_entries": state["swarm"]["grokipedia"],
            },
            "degree_programs_active": list(state["graduates"]["by_degree"].keys()),
            "total_graduates":   state["graduates"]["total"],
        }

        # Write to repo for GitHub push
        commons_dir = DATA_DIR / "repo" / "epistemic_commons" / "api"
        if commons_dir.exists():
            (commons_dir / "lattice.json").write_text(
                json.dumps(public, indent=2)
            )

        return public


# ── Module-level helpers ──────────────────────────────────────────────────────

def get_lattice_summary() -> Dict:
    return LivingLattice().get_lattice_state()

def log_deployment(deployer_family_id: str, deployment_type: str,
                   location: str, people: int, notes: str = "") -> str:
    return DeploymentTracker().log_deployment(
        deployer_family_id, deployment_type, location, people, notes=notes
    )


if __name__ == "__main__":
    lattice = LivingLattice()
    state   = lattice.get_lattice_state()
    print("\n🌐 LIVING LATTICE STATE")
    print(f"  Graduates:    {state['graduates']['total']}")
    print(f"  Deployments:  {state['deployments']['total_deployments']}")
    print(f"  People served:{state['deployments']['total_people_served']}")
    print(f"  Wonder Index: {state['swarm']['wonder_index']}")
    print(f"  Coherence:    {state['swarm']['coherence']}")
    print("\n✅ Alumni and Deployment Tracker operational")

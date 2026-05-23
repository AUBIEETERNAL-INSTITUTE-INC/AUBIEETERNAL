"""
bitcoin_wallet.py — AUBIEETERNAL Bitcoin + Lightning + Runes Module
===================================================================
Watch-only wallet for families. Reads balances, creates Lightning
invoices for XP rewards, and tracks Rune holdings.

No private keys ever stored here — watch-only only.
Lightning rewards flow from the operator's node to family wallets.

Usage:
    from bitcoin_wallet import FamilyWallet
    wallet = FamilyWallet(family_id="family_alpha")
    balance = wallet.get_lightning_balance()
    runes   = wallet.get_rune_holdings()
    invoice = wallet.create_reward_invoice(sats=100, memo="Courage Lesson XP")
"""

import os, json, requests, datetime
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
WALLET_DIR    = Path("/mnt/main/families")
ENV_PATH      = Path("/mnt/main/api_keys.env")

# Public APIs (no auth needed for watch-only)
MEMPOOL_API   = "https://mempool.space/api"
ORDINALS_API  = "https://api.ordinals.com"

# Known AUBIEETERNAL runes
AUBIE_RUNES = {
    "AUBIE•ETERNAL•XAIAGENTSWARM": {
        "id":     "944048:1122",
        "block":  944048,
        "symbol": "🦅",
        "supply": 21_000_001_000,
    },
    "QUANTUM•TUNNELING•STEELMAN": {
        "id":     "944402:1552",
        "block":  944402,
        "symbol": "🌀",
        "supply": 2_100_000_000,
        "mintable": True,
    },
}

def _load_env() -> dict:
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            if "=" in line:
                k, v = line.strip().split("=", 1)
                env[k] = v
    return env


# ══════════════════════════════════════════════════════════════════════════════
# FAMILY WALLET
# ══════════════════════════════════════════════════════════════════════════════

class FamilyWallet:
    """
    Watch-only Bitcoin + Lightning + Runes wallet for one family.
    All data stored in /mnt/main/families/{family_id}/wallet.json
    """

    def __init__(self, family_id: str):
        self.family_id = family_id
        self.family_dir = WALLET_DIR / family_id
        self.family_dir.mkdir(parents=True, exist_ok=True)
        self.wallet_path = self.family_dir / "wallet.json"
        self.reward_log  = self.family_dir / "reward_log.jsonl"
        self.data        = self._load()
        self.env         = _load_env()

    # ── Config ────────────────────────────────────────────────────────────────
    def _load(self) -> dict:
        if self.wallet_path.exists():
            try:
                return json.loads(self.wallet_path.read_text())
            except Exception:
                pass
        return {
            "family_id":       self.family_id,
            "btc_address":     "",       # watch-only on-chain address
            "lightning_node":  "",       # LNURL or node pubkey
            "lightning_address": "",     # user@domain.com Lightning address
            "rune_address":    "",       # address holding runes
            "total_sats_earned": 0,
            "total_xp_rewarded": 0,
            "created_at":      datetime.datetime.now().isoformat(),
        }

    def save(self):
        self.wallet_path.write_text(json.dumps(self.data, indent=2))

    def configure(self, btc_address: str = "", lightning_address: str = "",
                  lightning_node: str = "", rune_address: str = ""):
        """Set watch-only addresses for this family."""
        if btc_address:       self.data["btc_address"]       = btc_address
        if lightning_address: self.data["lightning_address"] = lightning_address
        if lightning_node:    self.data["lightning_node"]    = lightning_node
        if rune_address:      self.data["rune_address"]      = rune_address
        self.save()
        return self.data

    # ── Bitcoin balance ───────────────────────────────────────────────────────
    def get_btc_balance(self) -> dict:
        """Get on-chain BTC balance for the family's watch address."""
        addr = self.data.get("btc_address", "")
        if not addr:
            return {"sats": 0, "btc": 0.0, "error": "No address configured"}
        try:
            r = requests.get(f"{MEMPOOL_API}/address/{addr}", timeout=5)
            if r.status_code == 200:
                d = r.json()
                sats = d.get("chain_stats", {}).get("funded_txo_sum", 0) - \
                       d.get("chain_stats", {}).get("spent_txo_sum", 0)
                return {
                    "sats":    sats,
                    "btc":     round(sats / 1e8, 8),
                    "address": addr[:12] + "...",
                    "txs":     d.get("chain_stats", {}).get("tx_count", 0),
                }
        except Exception as e:
            return {"sats": 0, "btc": 0.0, "error": str(e)}
        return {"sats": 0, "btc": 0.0, "error": "API error"}

    # ── Lightning balance ─────────────────────────────────────────────────────
    def get_lightning_balance(self) -> dict:
        """
        Get Lightning balance via LNURL or Lightning Address.
        Falls back to reward log total if no node configured.
        """
        la = self.data.get("lightning_address", "")
        total_earned = self.data.get("total_sats_earned", 0)

        if la and "@" in la:
            try:
                # Resolve Lightning Address → LNURL
                user, domain = la.split("@")
                r = requests.get(
                    f"https://{domain}/.well-known/lnurlp/{user}", timeout=5
                )
                if r.status_code == 200:
                    info = r.json()
                    return {
                        "address":    la,
                        "min_sats":   info.get("minSendable", 0) // 1000,
                        "max_sats":   info.get("maxSendable", 0) // 1000,
                        "total_earned": total_earned,
                        "status":     "✅ Lightning address reachable",
                    }
            except Exception as e:
                pass

        return {
            "address":      la or "Not configured",
            "total_earned": total_earned,
            "status":       "ℹ️ Rewards tracked locally",
        }

    # ── Rune holdings ─────────────────────────────────────────────────────────
    def get_rune_holdings(self) -> dict:
        """Get AUBIEETERNAL Rune holdings for the family's address."""
        addr    = self.data.get("rune_address", "") or self.data.get("btc_address", "")
        result  = {"address": addr[:12] + "..." if addr else "Not configured"}
        holdings = {}

        if addr:
            try:
                r = requests.get(
                    f"{MEMPOOL_API}/address/{addr}/utxo", timeout=5
                )
                if r.status_code == 200:
                    result["utxos"] = len(r.json())
            except Exception:
                pass

        # Always show AUBIEETERNAL runes regardless (family earns these via lessons)
        result["aubieeternal_runes"] = {
            "AUBIE•ETERNAL•XAIAGENTSWARM": {
                "symbol":  "🦅",
                "earned":  self.data.get("total_xp_rewarded", 0) // 100,
                "on_chain": False,  # True once inscribed
            },
            "QUANTUM•TUNNELING•STEELMAN": {
                "symbol":  "🌀",
                "earned":  0,
                "mintable": True,
                "mint_url": "https://uniscan.cc/runes/detail/QUANTUM%E2%80%A2TUNNELING%E2%80%A2STEELMAN",
            },
        }
        result["child_rune_fragments"] = self.data.get("child_rune_fragments", 0)
        return result

    # ── BTC price ─────────────────────────────────────────────────────────────
    def get_btc_price(self) -> dict:
        try:
            r = requests.get(
                "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
                timeout=5
            )
            if r.status_code == 200:
                usd = r.json()["bitcoin"]["usd"]
                block = requests.get(
                    f"{MEMPOOL_API}/blocks/tip/height", timeout=5
                ).text.strip()
                return {"usd": usd, "block": block}
        except Exception:
            pass
        return {"usd": None, "block": "unknown"}

    # ── Lightning reward ──────────────────────────────────────────────────────
    def log_xp_reward(self, sats: int, xp: int, lesson: str, kid_name: str) -> dict:
        """
        Log a Lightning XP reward to this family's reward log.
        Actual payment must be initiated by the operator.
        Returns a payment request the operator can fulfill.
        """
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "family_id": self.family_id,
            "kid_name":  kid_name,
            "lesson":    lesson,
            "sats":      sats,
            "xp":        xp,
            "address":   self.data.get("lightning_address", ""),
            "status":    "pending",
            "memo":      f"AUBIEETERNAL XP: {lesson} | {kid_name} | +{xp} XP",
        }

        # Write to reward log
        with open(self.reward_log, "a") as f:
            f.write(json.dumps(entry) + "\n")

        # Update totals
        self.data["total_sats_earned"]  = self.data.get("total_sats_earned", 0) + sats
        self.data["total_xp_rewarded"]  = self.data.get("total_xp_rewarded", 0) + xp
        self.data["child_rune_fragments"] = self.data.get("child_rune_fragments", 0) + (xp // 50)
        self.save()

        return entry

    def get_reward_history(self, n: int = 10) -> list:
        """Get last n reward entries."""
        if not self.reward_log.exists():
            return []
        try:
            lines = self.reward_log.read_text().strip().split("\n")
            entries = []
            for line in reversed(lines[-50:]):
                try:
                    entries.append(json.loads(line))
                    if len(entries) >= n:
                        break
                except Exception:
                    pass
            return entries
        except Exception:
            return []

    def get_summary(self) -> dict:
        """Full wallet summary for HUD display."""
        btc     = self.get_btc_balance()
        ln      = self.get_lightning_balance()
        runes   = self.get_rune_holdings()
        price   = self.get_btc_price()

        usd_val = ""
        if btc.get("sats") and price.get("usd"):
            usd_val = f"${btc['sats'] / 1e8 * price['usd']:,.2f}"

        return {
            "family_id":     self.family_id,
            "btc_sats":      btc.get("sats", 0),
            "btc_usd":       usd_val,
            "btc_price":     price.get("usd"),
            "btc_block":     price.get("block"),
            "lightning":     ln,
            "runes":         runes,
            "total_earned":  self.data.get("total_sats_earned", 0),
            "total_xp":      self.data.get("total_xp_rewarded", 0),
            "child_rune_fragments": self.data.get("child_rune_fragments", 0),
        }


# ══════════════════════════════════════════════════════════════════════════════
# OPERATOR WALLET — manages rewards to all families
# ══════════════════════════════════════════════════════════════════════════════

class OperatorWallet:
    """
    Operator (you) sends Lightning rewards to all families.
    Reads pending rewards and creates payment requests.
    """

    def __init__(self):
        self.env = _load_env()

    def get_all_pending_rewards(self) -> list:
        """Get all pending reward entries across all families."""
        pending = []
        if not WALLET_DIR.exists():
            return pending
        for family_dir in WALLET_DIR.iterdir():
            reward_log = family_dir / "reward_log.jsonl"
            if reward_log.exists():
                try:
                    for line in reward_log.read_text().strip().split("\n"):
                        try:
                            entry = json.loads(line)
                            if entry.get("status") == "pending":
                                pending.append(entry)
                        except Exception:
                            pass
                except Exception:
                    pass
        return sorted(pending, key=lambda x: x.get("timestamp",""), reverse=True)

    def mark_paid(self, family_id: str, timestamp: str, txid: str = ""):
        """Mark a reward as paid after Lightning payment."""
        reward_log = WALLET_DIR / family_id / "reward_log.jsonl"
        if not reward_log.exists():
            return
        try:
            lines = reward_log.read_text().strip().split("\n")
            updated = []
            for line in lines:
                try:
                    entry = json.loads(line)
                    if entry.get("timestamp") == timestamp and entry.get("status") == "pending":
                        entry["status"] = "paid"
                        entry["txid"]   = txid
                        entry["paid_at"] = datetime.datetime.now().isoformat()
                    updated.append(json.dumps(entry))
                except Exception:
                    updated.append(line)
            reward_log.write_text("\n".join(updated))
        except Exception as e:
            print(f"[wallet] mark_paid error: {e}")

    def get_family_summary(self) -> list:
        """Summary of all families' wallet stats."""
        summaries = []
        if not WALLET_DIR.exists():
            return summaries
        for family_dir in WALLET_DIR.iterdir():
            wallet_path = family_dir / "wallet.json"
            if wallet_path.exists():
                try:
                    data = json.loads(wallet_path.read_text())
                    summaries.append({
                        "family_id":    data.get("family_id"),
                        "total_sats":   data.get("total_sats_earned", 0),
                        "total_xp":     data.get("total_xp_rewarded", 0),
                        "lightning_addr": data.get("lightning_address", ""),
                        "fragments":    data.get("child_rune_fragments", 0),
                    })
                except Exception:
                    pass
        return summaries


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🦅 Bitcoin Wallet Module Test")
    w = FamilyWallet("family_test")
    w.configure(lightning_address="test@getalby.com")
    reward = w.log_xp_reward(sats=100, xp=18, lesson="Courage — Level 1", kid_name="Gaby")
    print(f"Reward logged: {reward['memo']}")
    summary = w.get_summary()
    print(f"Total earned: {summary['total_earned']} sats | XP: {summary['total_xp']}")
    print(f"Child Rune fragments: {summary['child_rune_fragments']}")
    print("War Eagle 🦅")

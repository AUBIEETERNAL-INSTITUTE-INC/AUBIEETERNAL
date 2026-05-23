#!/usr/bin/env python3
"""
onboarding_kit/family_onboard.py — AUBIEETERNAL Family Onboarding
=================================================================
Run this once per family to set them up. Creates their config,
pre-pairs their Halo glasses, and generates a gift card with
their login code.

Usage:
  python3 family_onboard.py                    # interactive
  python3 family_onboard.py --family alpha     # quick setup
  python3 family_onboard.py --all              # setup all 4
  python3 family_onboard.py --print-cards      # print gift cards
"""

import os, sys, json, argparse, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

STREAMLIT_URL  = os.getenv("AUBIE_URL", "http://painful-recess.local:60193")
FAMILIES_DIR   = Path("/mnt/main/families")
ONBOARD_DIR    = Path(__file__).parent

GIFT_FAMILIES = {
    "alpha": {
        "display":    "Family Alpha",
        "code":       "alpha",
        "kid":        "Explorer",
        "age":        9,
        "parent":     "Parent",
        "color":      "#00cfff",
        "emoji":      "🦅",
    },
    "beta": {
        "display":    "Family Beta",
        "code":       "beta",
        "kid":        "Scout",
        "age":        10,
        "parent":     "Parent",
        "color":      "#a020f0",
        "emoji":      "⚡",
    },
    "gamma": {
        "display":    "Family Gamma",
        "code":       "gamma",
        "kid":        "Sage",
        "age":        8,
        "parent":     "Parent",
        "color":      "#00ff88",
        "emoji":      "🌀",
    },
    "delta": {
        "display":    "Family Delta",
        "code":       "delta",
        "kid":        "Nova",
        "age":        11,
        "parent":     "Parent",
        "color":      "#f7931a",
        "emoji":      "🔴",
    },
}


def setup_family(code: str, kid_name: str = "", parent_name: str = "",
                 kid_age: int = 0, lightning_address: str = "") -> dict:
    """Create all files for one family."""
    if code not in GIFT_FAMILIES:
        print(f"❌ Unknown code: {code}. Valid: {list(GIFT_FAMILIES.keys())}")
        return {}

    fam = GIFT_FAMILIES[code].copy()
    fid = f"family_{code}"

    if kid_name:    fam["kid"]    = kid_name
    if parent_name: fam["parent"] = parent_name
    if kid_age:     fam["age"]    = kid_age

    # 1. Create family directory
    fam_dir = FAMILIES_DIR / fid
    fam_dir.mkdir(parents=True, exist_ok=True)

    # 2. Write stats.json
    stats = {
        "family_id":         fid,
        "total_xp":          0,
        "level":             1,
        "streak_days":       0,
        "last_session_date": "",
        "badges":            [],
        "lessons_completed": [],
        "coherence_history": [],
        "child_rune_fragments": 0,
        "sats_earned":       0,
        "daily_quests_completed": [],
        "experiments_run":   0,
    }
    (fam_dir / "stats.json").write_text(json.dumps(stats, indent=2))

    # 3. Write wallet.json
    wallet = {
        "family_id":           fid,
        "btc_address":         "",
        "lightning_address":   lightning_address,
        "rune_address":        "",
        "total_sats_earned":   0,
        "total_xp_rewarded":   0,
        "child_rune_fragments": 0,
        "created_at":          datetime.datetime.now().isoformat(),
    }
    (fam_dir / "wallet.json").write_text(json.dumps(wallet, indent=2))

    # 4. Write halo_config.json for glasses
    halo_cfg = {
        "family_id":    fid,
        "profile":      "kid",
        "name":         fam["kid"],
        "age":          fam["age"],
        "nostr_npub":   "",
        "nostr_nsec":   "",
        "paired_npub":  "",
        "relays":       ["wss://relay.damus.io", "wss://nos.lol", "wss://relay.nostr.band"],
        "startos_ip":   "192.168.1.251",
        "auto_detect":  True,
        "brightness":   70,
        "font_size":    "medium",
        "family_code":  code,
    }
    (fam_dir / "halo_config.json").write_text(json.dumps(halo_cfg, indent=2))

    # 5. Generate gift card text
    gift_card = _generate_gift_card(fam, code, fid)
    card_path  = fam_dir / "gift_card.txt"
    card_path.write_text(gift_card)

    print(f"\n✅ Family '{fam['display']}' set up!")
    print(f"   Directory: {fam_dir}")
    print(f"   Login code: {code}")
    print(f"   Gift card: {card_path}")
    print(f"   Glasses config: {fam_dir}/halo_config.json")

    return fam


def _generate_gift_card(fam: dict, code: str, fid: str) -> str:
    url = STREAMLIT_URL
    return f"""
╔══════════════════════════════════════════════════════════╗
║          🦅 AUBIEETERNAL — FAMILY SOVEREIGN LATTICE        ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  Welcome, {fam['display']:<47}║
║                                                          ║
║  {fam['emoji']} Your family: {fam['kid']} (kid) + {fam['parent']} (parent)                  
║                                                          ║
╠══════════════════════════════════════════════════════════╣
║  HOW TO GET STARTED                                      ║
║                                                          ║
║  1. Open this URL on any device:                         ║
║     {url:<54}║
║                                                          ║
║  2. Enter your family login code:                        ║
║     ▶  {code.upper():<51}◀  ║
║                                                          ║
║  3. Select Kid or Parent role                            ║
║  4. Pick today's lesson and start learning!              ║
║                                                          ║
╠══════════════════════════════════════════════════════════╣
║  HALO GLASSES (if included)                              ║
║                                                          ║
║  python3 halo_light_client.py \\                          ║
║    --mode kid --family {code:<32}║
║                                                          ║
║  Your config is pre-loaded. Just power on and go.        ║
║                                                          ║
╠══════════════════════════════════════════════════════════╣
║  WHAT'S INSIDE                                           ║
║                                                          ║
║  📖 48 lessons (Courage, Bitcoin, Antifragility,         ║
║     Simulation, Polyvagal, Steelmanning + more)          ║
║  🎮 Daily Quests + Streaks + Badges + XP                 ║
║  ⚡ Lightning sats rewards for completing lessons         ║
║  🔴 Child Rune Genesis at 256 coherence confirmations     ║
║  🧪 Sandbox Lab for custom experiments                   ║
║  📡 Nostr bridge (works anywhere, even without WiFi)     ║
║                                                          ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  Human + Grok + Lightning + Runes + On-Chain Forever     ║
║  Coherence: 1.000000 | War Eagle Eternal 🦅❤️             ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
"""


def print_all_cards():
    """Print gift cards for all 4 families."""
    print("\n" + "="*62)
    print("  AUBIEETERNAL — GIFT CARDS FOR 4 FAMILIES")
    print("="*62)
    for code, fam in GIFT_FAMILIES.items():
        fid  = f"family_{code}"
        card = _generate_gift_card(fam, code, fid)
        print(card)
        print()


def setup_all():
    """Set up all 4 gift families interactively."""
    print("\n🦅 AUBIEETERNAL — 4-Family Setup")
    print("=" * 40)
    print("Setting up default configurations for all 4 families.")
    print("You can customize names after, or edit /mnt/main/families/registry.json\n")

    for code in GIFT_FAMILIES:
        setup_family(code)

    print("\n✅ All 4 families ready!")
    print(f"\nStreamlit URL: {STREAMLIT_URL}")
    print("\nLogin codes:")
    for code, fam in GIFT_FAMILIES.items():
        print(f"  {fam['emoji']} {fam['display']:20} → {code}")
    print("\nWar Eagle Eternal 🦅❤️")


def interactive_setup():
    """Walk through setup for one family interactively."""
    print("\n🦅 AUBIEETERNAL Family Setup")
    print("=" * 40)
    code = input("Family code (alpha/beta/gamma/delta): ").strip().lower()
    if code not in GIFT_FAMILIES:
        print(f"❌ Invalid code. Use: {list(GIFT_FAMILIES.keys())}")
        return

    fam = GIFT_FAMILIES[code]
    print(f"\nSetting up: {fam['display']}")
    kid_name    = input(f"Kid's name [{fam['kid']}]: ").strip() or fam["kid"]
    parent_name = input(f"Parent's name [{fam['parent']}]: ").strip() or fam["parent"]
    kid_age     = input(f"Kid's age [{fam['age']}]: ").strip()
    lightning   = input("Family Lightning address (optional, press Enter to skip): ").strip()

    fam_result = setup_family(
        code,
        kid_name=kid_name,
        parent_name=parent_name,
        kid_age=int(kid_age) if kid_age.isdigit() else fam["age"],
        lightning_address=lightning,
    )

    print(f"\n🎁 Gift card saved. Print it and include in the glasses box!")
    card = _generate_gift_card({**fam, "kid": kid_name, "parent": parent_name}, code, f"family_{code}")
    print(card)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AUBIEETERNAL Family Onboarding")
    parser.add_argument("--family",      help="Family code (alpha/beta/gamma/delta)")
    parser.add_argument("--all",         action="store_true", help="Setup all 4 families")
    parser.add_argument("--print-cards", action="store_true", help="Print all gift cards")
    parser.add_argument("--kid",         help="Kid's name")
    parser.add_argument("--parent",      help="Parent's name")
    parser.add_argument("--age",         type=int, help="Kid's age")
    parser.add_argument("--lightning",   help="Lightning address")
    parser.add_argument("--url",         help="Override Streamlit URL")
    args = parser.parse_args()

    if args.url:
        STREAMLIT_URL = args.url

    if args.print_cards:
        print_all_cards()
    elif args.all:
        setup_all()
    elif args.family:
        setup_family(
            args.family,
            kid_name=args.kid or "",
            parent_name=args.parent or "",
            kid_age=args.age or 0,
            lightning_address=args.lightning or "",
        )
    else:
        interactive_setup()

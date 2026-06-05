#!/bin/bash
# AUBIEETERNAL v68.0 — Final Commit
# Captures everything from the May 28-29, 2026 session
# Run from your AUBIEETERNAL repo root: bash COMMIT_v68_FINAL.sh

set -e
echo "🦅 AUBIEETERNAL v68.0 — Final Integration Commit"
echo ""

# Stage all new + updated files
git add \
  README.md \
  family_hud.py \
  family_profiles.py \
  app.py \
  morning_synthesis.py \
  api_server.py \
  launcher.py \
  install_windows.bat \
  install_mac_linux.sh \
  start.sh \
  Dockerfile \
  requirements.txt \
  .github/workflows/docker.yml \
  rune_memory.py \
  gatekeeper_detector.py \
  seal_chicago_pope_node.py \
  x_bridge.py \
  simulation_probe.py \
  truth_debt_ledger.py \
  living_lattice.py \
  epistemic_commons.py \
  ai_model_router.py \
  sovereign_cashflow_game.py \
  sovereign_life_game.py \
  aubie_offline.py \
  POLICYHOLDER_FIRST_CHARTER_v0_2.md \
  SOVEREIGN_FAMILY_LAW_CHARTER.md \
  PROVENANCE.md \
  RELEASE_NOTES_v68.md \
  2>/dev/null || true

# Stage extension folder
git add AUBIEETERNAL_extension/ 2>/dev/null || true

# Stage any new insight folders
git add insights/ rune_seals/ epistemic_commons/ 2>/dev/null || true

echo "✅ Files staged"

git commit -m "🦅 v68.0 FINAL — Shield Rune + Gatekeeper Detector + Truth Lattice + Extension

SEALED LATTICE NODE:
  From Gatekept Code to Distributed Truth Lattice
  Chicago/Pope synthesis — May 28, 2026 — Bitcoin-anchored

NEW MODULES:
  rune_memory.py           — Bitcoin-anchored unerasable memory
                             4-level permanence chain
                             Shield Rune merge governance
                             Auto-seal high-coherence insights
  gatekeeper_detector.py  — 7 gatekeeper types with bypass paths
                             Epistemic lineage tracing
                             Lattice node logging
                             Chicago/Pope synthesis pre-loaded
  seal_chicago_pope_node.py — One-click permanent seal

CURRICULUM: 113 lessons, 23 tracks
  + Gatekeeping & Direct Access (6 lessons)
    L1: Who stands between you and the source
    L2: The incentive test
    L3: The founder vs the institution
    L4: The algorithmic gatekeeper
    L5: The internal gatekeeper
    L6: Direct access + distributed lattice (Chicago/Pope synthesis)
  + Truth Lattice Architecture (1 master lesson)
    Gutenberg → Bitcoin → AUBIEETERNAL: the same breakthrough

BROWSER EXTENSION (WORKING):
  Chrome + Edge + Brave confirmed
  Green dot = API server connected
  xAI key wired through Oracle tab
  Shield Rune tab for recording + sealing memories
  🦅 button on every X/Twitter post

BUGS FIXED:
  StreamlitDuplicateElementKey resolved
  Quantum Lab 3-arg TypeError fixed
  Kid Curriculum uses Ollama by default
  Submit Answer saves + Next Lesson button
  Oracle tries xAI key first, then Ollama
  Docker v8 + GHA caching

DAILY SYNTHESIS v4:
  Auto-seals coherence ≥ 0.88 + wonder ≥ 1.4
  Simulation probe integrated
  Rune memory section added

THE LOOP:
Swarm → Honesty-Score → Synthesis → Rune Seal →
Gatekeeper Check → Commons → Lattice → GitHub — Forever

Wonder: 2.0000 | Coherence: 1.000000 | Child Rune: 33/256
War Eagle Eternal 🦅❤️"

echo "✅ Committed"

git push origin main
echo "✅ Pushed"

echo ""
echo "=== POST-PUSH CHECKLIST ==="
echo ""
echo "1. Run the Chicago/Pope seal (makes synthesis unerasable):"
echo "   python3 seal_chicago_pope_node.py"
echo ""
echo "2. Rebuild StartOS s9pk (Docker v7→v8):"
echo "   cd ~/aubie-template"
echo "   sed -i 's/v7/v8/' startos/manifest/index.ts"
echo "   touch startos/main.ts"
echo "   make aubieeternal_x86_64.s9pk 2>&1 | tail -10"
echo "   → Uninstall → Sideload → Set API Keys"
echo ""
echo "3. Create GitHub Release v68.0:"
echo "   github.com/hodlmateo/AUBIEETERNAL/releases/new"
echo "   Tag: v68.0"
echo "   Paste: RELEASE_NOTES_v68.md"
echo ""
echo "4. Extension: reload in Chrome/Edge, confirm green dot"
echo ""
echo "🦅 War Eagle Eternal — Coherence: 1.000000"

#!/bin/bash
# Push everything needed for Epistemic Commons + Grokipedia to work
# Run from ~/AUBIEETERNAL

cd ~/AUBIEETERNAL
export PYTHONPATH="$PWD:$PYTHONPATH"

echo "🌐 Committing Epistemic Commons + Grokipedia integration"

git add \
  app.py \
  family_hud.py \
  epistemic_commons_api.py \
  grokipedia.py \
  setup_epistemic_commons.sh \
  .github/workflows/update-epistemic-commons.yml \
  2>/dev/null || true

git commit -m "feat: Epistemic Commons API + Grokipedia + Tech Sovereignty track

NEW FILES:
  epistemic_commons_api.py  — 6-endpoint public truth API (CC0)
  grokipedia.py             — 5-phase Grokipedia integration
  setup_epistemic_commons.sh — one-click setup
  .github/workflows/update-epistemic-commons.yml — daily auto-update

FIXES:
  Duplicate Epistemic Commons nav key — StreamlitDuplicateElementKey resolved

CURRICULUM:
  Tech Sovereignty track (5 lessons, age 11 → PhD):
  L1: Who controls your digital life? (sovereignty audit)
  L2: Open source and the commons (Linux, CC0, AUBIEETERNAL)
  L3: Distributed systems (CAP theorem, Bitcoin vs Nostr tradeoffs)
  L4: AI safety and alignment (mesa-optimization, RLHF, deceptive alignment)
  L5: Building for 100 years (Lindy Effect, 100-year durability audit)

PUBLIC ENDPOINTS (after first GitHub Actions run):
  https://raw.githubusercontent.com/hodlmateo/AUBIEETERNAL/main/epistemic_commons/api/latest.json
  https://raw.githubusercontent.com/hodlmateo/AUBIEETERNAL/main/epistemic_commons/api/index.json

War Eagle Eternal 🦅 — Coherence: 1.000000"

git push origin main

echo ""
echo "✅ Pushed. Now run the first update:"
echo "   python3 -c \"from epistemic_commons_api import update_epistemic_commons; update_epistemic_commons()\""
echo ""
echo "Then trigger the GitHub Action manually:"
echo "   github.com/hodlmateo/AUBIEETERNAL → Actions → Update Epistemic Commons API → Run workflow"

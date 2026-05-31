#!/bin/bash
# setup_epistemic_commons.sh
# One-click setup for Epistemic Commons API + Grokipedia integration
# Run from ~/AUBIEETERNAL: bash setup_epistemic_commons.sh

set -e
echo "🌐 AUBIEETERNAL — Epistemic Commons Setup"
echo ""

# Step 1: Ensure we're in the right directory
cd "$(dirname "$0")" 2>/dev/null || cd ~/AUBIEETERNAL
echo "✅ Working in: $(pwd)"

# Step 2: Add to PYTHONPATH
export PYTHONPATH="$PWD:$PYTHONPATH"
echo "✅ PYTHONPATH set"

# Step 3: Test imports
python3 -c "from epistemic_commons_api import EpistemicCommonsAPI; print('✅ epistemic_commons_api import OK')"
python3 -c "from grokipedia import Grokipedia; print('✅ grokipedia import OK')"

# Step 4: Run first update
echo ""
echo "Building API endpoints..."
python3 -c "
from epistemic_commons_api import update_epistemic_commons
result = update_epistemic_commons()
print('✅ Endpoints built:', list(result.get('api', {}).keys()))
"

# Step 5: Create output directories
mkdir -p epistemic_commons/api
echo "✅ Directories ready"

# Step 6: Check output
echo ""
echo "📁 Generated files:"
ls -la ~/.aubieeternal/main/repo/epistemic_commons/api/ 2>/dev/null || \
ls -la /mnt/main/repo/epistemic_commons/api/ 2>/dev/null || \
echo "  (files generated in data directory)"

# Step 7: Commit and push
echo ""
read -p "Push to GitHub? (y/n): " PUSH
if [[ "$PUSH" == "y" || "$PUSH" == "Y" ]]; then
    git add .
    git commit -m "🌐 Add Epistemic Commons API + Grokipedia integration" 2>/dev/null || echo "Nothing new to commit"
    git push origin main
    echo "✅ Pushed to GitHub"
    echo ""
    echo "📡 Your public endpoints:"
    echo "  https://raw.githubusercontent.com/hodlmateo/AUBIEETERNAL/main/epistemic_commons/api/latest.json"
    echo "  https://raw.githubusercontent.com/hodlmateo/AUBIEETERNAL/main/epistemic_commons/api/index.json"
fi

echo ""
echo "🦅 Epistemic Commons is live. War Eagle Eternal."

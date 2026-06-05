#!/bin/bash
# FIX_GIT_PUSH.sh — Fix the "unable to access painful-recess.local" error
# The problem: your remote is pointing to painful-recess.local (StartOS)
# instead of GitHub. Run this once to fix it.

cd ~/AUBIEETERNAL

# 1. Check what remotes you currently have
echo "=== Current remotes ==="
git remote -v

# 2. Fix the origin remote to point to GitHub
git remote set-url origin https://github.com/hodlmateo/AUBIEETERNAL.git

# 3. Verify the fix
echo ""
echo "=== Fixed remotes ==="
git remote -v

# 4. Now push works
echo ""
echo "=== Pushing to GitHub ==="
git push origin main

echo ""
echo "✅ Done. Your repo now pushes to GitHub correctly."
echo "   The painful-recess.local remote was your StartOS git server."
echo "   GitHub is the public remote — use that for all git push commands."

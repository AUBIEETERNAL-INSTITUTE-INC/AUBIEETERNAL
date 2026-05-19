#!/bin/bash
# AUBIEETERNAL v11 — Self-contained: Swarm + Streamlit + GitHub push
# Everything runs inside the Docker container. No SSH needed ever.

# ── Load API keys from StartOS persistent volume ──────────────────────────────
[ -f /mnt/main/api_keys.env ] && source /mnt/main/api_keys.env
export XAI_API_KEY OPENAI_API_KEY ANTHROPIC_API_KEY GITHUB_TOKEN

# ── Clone or pull latest code from GitHub ─────────────────────────────────────
if [ ! -d /mnt/main/repo ]; then
    echo "📦 First run — cloning repo..."
    git clone https://github.com/hodlmateo/AUBIEETERNAL /mnt/main/repo 2>&1
else
    echo "🔄 Pulling latest code..."
    cd /mnt/main/repo && git pull --rebase --autostash 2>&1
fi

# ── Configure git for pushing swarm outputs back to GitHub ────────────────────
if [ -n "$GITHUB_TOKEN" ]; then
    cd /mnt/main/repo
    git config user.email "swarm@aubieeternal.local"
    git config user.name "AUBIEETERNAL Swarm v4.1"
    # Embed token in remote URL so push works without interactive auth
    git remote set-url origin \
        https://${GITHUB_TOKEN}@github.com/hodlmateo/AUBIEETERNAL.git
    echo "✅ Git push configured with GitHub token"
else
    echo "⚠️  No GITHUB_TOKEN — swarm will run but not push to GitHub"
fi

# ── Launch swarm in background ─────────────────────────────────────────────────
SWARM_PATH="/mnt/main/repo/swarm/swarm_v4_1.py"
if [ -f "$SWARM_PATH" ]; then
    echo "🦅 Launching swarm from $SWARM_PATH..."
    nohup python3 "$SWARM_PATH" > /tmp/swarm.log 2>&1 &
    echo "✅ Swarm PID: $!"
else
    echo "⚠️  Swarm file not found at $SWARM_PATH — skipping swarm launch"
fi

# ── Launch Streamlit (foreground — keeps container alive) ─────────────────────
APP_PATH="/mnt/main/repo/app.py"
if [ ! -f "$APP_PATH" ]; then
    APP_PATH="/work/app.py"
    echo "⚠️  Using baked-in app.py (repo app.py not found)"
fi

echo "🚀 Launching Streamlit on port 80 from $APP_PATH..."
exec streamlit run "$APP_PATH" \
    --server.port=80 \
    --server.address=0.0.0.0 \
    --server.headless=true

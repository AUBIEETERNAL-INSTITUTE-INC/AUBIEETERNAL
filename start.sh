#!/bin/bash
[ -f /mnt/main/api_keys.env ] && source /mnt/main/api_keys.env
echo "Pulling latest code..."

# ── Self-healing git clone ──────────────────────────────────────────────────
# If repo is missing or corrupt, nuke and re-clone automatically
if [ -d /mnt/main/repo/.git ]; then
    cd /mnt/main/repo
    git config --global user.email "aubie@eternal.ai"
    git config --global user.name "AUBIEETERNAL"
    git remote set-url origin https://${GITHUB_TOKEN}@github.com/hodlmateo/AUBIEETERNAL.git
    git config --global --add safe.directory /mnt/main/repo
    if ! git fetch origin 2>/dev/null || ! git reset --hard origin/main 2>/dev/null; then
        echo "⚠️  Git repo corrupt — nuking and re-cloning..."
        cd /mnt/main
        rm -rf repo
        git clone https://${GITHUB_TOKEN}@github.com/hodlmateo/AUBIEETERNAL.git repo
        cd repo
    fi
else
    echo "📦 First run — cloning repo..."
    mkdir -p /mnt/main
    git clone https://${GITHUB_TOKEN}@github.com/hodlmateo/AUBIEETERNAL.git /mnt/main/repo
    cd /mnt/main/repo
    git config --global user.email "aubie@eternal.ai"
    git config --global user.name "AUBIEETERNAL"
    git remote set-url origin https://${GITHUB_TOKEN}@github.com/hodlmateo/AUBIEETERNAL.git
fi

echo "Git push configured"
SWARM_PATH="/mnt/main/repo/swarm/swarm_v4_1.py"
nohup python3 "$SWARM_PATH" > /mnt/main/swarm.log 2>&1 &
echo "Swarm PID: $!"
tail -f /mnt/main/swarm.log &
exec streamlit run /mnt/main/repo/app.py --server.port=80 --server.address=0.0.0.0 --server.headless=true

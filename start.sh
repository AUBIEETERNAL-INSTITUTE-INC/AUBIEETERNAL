#!/bin/bash
set -e

echo "🦅 Starting AUBIEETERNAL v2.0.0:5 Sovereign Hyperlattice..."

# Start swarm in background
if [ -f "swarm/swarm_v4_1.py" ]; then
    python3 swarm/swarm_v4_1.py &
fi

# Start the main Streamlit app (this is what StartOS runs)
streamlit run app.py --server.port=80 --server.address=0.0.0.0 --server.headless=true

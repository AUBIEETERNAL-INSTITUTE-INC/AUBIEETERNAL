#!/bin/bash
set -e
SERVICES="ollama aubie-swarm aubie-assistant"
sudo systemctl stop $SERVICES
trap 'sudo systemctl start $SERVICES' EXIT
cd ~/aubieeternal_finetune
python3 finetune_v2.py

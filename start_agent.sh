#!/bin/bash
set -e

cd /home/j.garciabenlloch/Documents/seniaEye

# Kill any existing agent processes
pkill -9 python -f "agent.main" 2>/dev/null || true
sleep 1

# Create logs directory if needed
mkdir -p logs

# Start the agent
echo "[$(date)] Starting agent..." >> logs/__main__.log
python -m agent.main

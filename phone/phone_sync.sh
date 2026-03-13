#!/bin/bash
# Phone sync helper — push chunks and pull results over WiFi SSH
# Usage:
#   ./phone_sync.sh push chunk.txt      — send chunk file to phone
#   ./phone_sync.sh pull                — pull all results from phone
#   ./phone_sync.sh status              — check if solver is running
#   ./phone_sync.sh run chunk.txt       — start solver on phone via SSH
#   ./phone_sync.sh attach              — attach to running tmux session

PHONE="phone"  # Uses ~/.ssh/config alias
REMOTE_DIR="~/erdos"

case "${1:-help}" in
  push)
    FILE="${2:?Usage: phone_sync.sh push <file>}"
    echo "Pushing $FILE to phone..."
    scp "$FILE" "$PHONE:$REMOTE_DIR/"
    echo "Done. File is at $REMOTE_DIR/$(basename $FILE)"
    ;;

  pull)
    echo "Pulling results from phone..."
    scp "$PHONE:$REMOTE_DIR/*results*.csv" . 2>/dev/null && echo "Done." || echo "No results found."
    ;;

  status)
    echo "Checking phone solver status..."
    ssh "$PHONE" "ps aux | grep -E 'phone_solver|phone_gpu' | grep -v grep || echo 'No solver running'"
    ssh "$PHONE" "ls -la $REMOTE_DIR/*results*.csv 2>/dev/null || echo 'No results yet'"
    ;;

  run)
    CHUNK="${2:?Usage: phone_sync.sh run <chunk_file>}"
    CAP="${3:-10000000}"
    WORKERS="${4:-4}"
    echo "Starting solver on phone (tmux session 'erdos')..."
    # Push solver + chunk
    scp phone_solver.py "$PHONE:$REMOTE_DIR/"
    scp "$CHUNK" "$PHONE:$REMOTE_DIR/chunk.txt"
    # Start in tmux (survives SSH disconnect)
    ssh "$PHONE" "cd $REMOTE_DIR && tmux new-session -d -s erdos 'python phone_solver.py $CAP $WORKERS chunk.txt 2>&1 | tee solver.log'"
    echo "Solver running in tmux. Use './phone_sync.sh attach' to watch."
    ;;

  sieve)
    K_START="${2:-2901}"
    K_END="${3:-3864}"
    WORKERS="${4:-2}"
    echo "Deploying sieve solver to phone..."
    scp phone_sieve.py "$PHONE:$REMOTE_DIR/"
    # Push sieve data if we have it locally (saves phone bandwidth)
    if [[ -f sieve_data/Residues.txt ]]; then
        echo "Pushing sieve data (114MB)..."
        ssh "$PHONE" "mkdir -p $REMOTE_DIR/sieve_data"
        scp sieve_data/Residues.txt sieve_data/Filters.txt "$PHONE:$REMOTE_DIR/sieve_data/"
    else
        echo "No local sieve data — phone will download from GitHub"
    fi
    echo "Starting sieve in tmux (k=$K_START..$K_END, $WORKERS workers)..."
    ssh "$PHONE" "cd $REMOTE_DIR && tmux new-session -d -s sieve 'python -u phone_sieve.py $K_START $K_END $WORKERS 2>&1 | tee sieve.log'"
    echo "Sieve running. Use './phone_sync.sh attach-sieve' to watch."
    ;;

  attach-sieve)
    ssh -t "$PHONE" "tmux attach -t sieve 2>/dev/null || echo 'No sieve session. Start with: phone_sync.sh sieve [k_start] [k_end]'"
    ;;

  attach)
    ssh -t "$PHONE" "tmux attach -t erdos 2>/dev/null || echo 'No active session. Start one with: phone_sync.sh run chunk.txt'"
    ;;

  *)
    echo "Phone sync helper for Erdős–Straus solver"
    echo ""
    echo "Usage:"
    echo "  ./phone_sync.sh push <file>          Send file to phone"
    echo "  ./phone_sync.sh pull                 Pull results from phone"
    echo "  ./phone_sync.sh status               Check solver status"
    echo "  ./phone_sync.sh run <chunk> [cap] [workers]  Start solver"
    echo "  ./phone_sync.sh attach               Watch running solver"
    ;;
esac

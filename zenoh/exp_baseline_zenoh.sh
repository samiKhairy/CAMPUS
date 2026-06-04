#!/bin/bash

# Default values
DEVICES=${1:-2}
PAYLOAD_BYTES=${2:-100}
INTERVAL_SEC=${3:-0.1}
DURATION_SEC=${4:-60}
OUTPUT_CSV=${5:-"results/zenoh_baseline.csv"}
ZENOH_ROUTER=${6:-"tcp/localhost:7447"}

# Move to the script's directory to ensure paths are resolved correctly
cd "$(dirname "$0")"

echo "=================================================="
echo " RUNNING ZENOH BASELINE EXPERIMENT"
echo "=================================================="
echo "Devices      : $DEVICES"
echo "Payload Size : $PAYLOAD_BYTES bytes"
echo "Interval     : $INTERVAL_SEC s"
echo "Duration     : $DURATION_SEC s"
echo "Output CSV   : $OUTPUT_CSV"
echo "Zenoh Router : $ZENOH_ROUTER"
echo "=================================================="

# Ensure results directory exists
mkdir -p "$(dirname "$OUTPUT_CSV")"

# Store device process PIDs
DEVICE_PIDS=()
STARTED_ROUTER=false

# Clean up function
cleanup() {
  echo -e "\n[RUNNER] Terminating background simulator processes..."
  for pid in "${DEVICE_PIDS[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      echo "  -> Killing device process (PID: $pid)..."
      kill "$pid"
      wait "$pid" 2>/dev/null
    fi
  done

  if [ "$STARTED_ROUTER" = true ]; then
    echo "[RUNNER] Stopping Docker Zenoh router container (zenoh-router-exp)..."
    docker stop zenoh-router-exp >/dev/null 2>&1
  fi
  echo "[RUNNER] Cleanup complete."
}

# Register traps to ensure cleanup runs on exit/interrupted
trap cleanup EXIT INT TERM

# 1. Start Zenoh Router in Docker if not already running
if docker ps --format '{{.Names}}' | grep -Eq "^zenoh-router-exp$|^zenoh-router$"; then
  echo "[RUNNER] Zenoh router is already running."
else
  echo "[RUNNER] Starting Zenoh router container in background..."
  docker run -d --name zenoh-router-exp -p 7447:7447 eclipse/zenoh:latest >/dev/null
  STARTED_ROUTER=true
  # Wait for router to initialize
  sleep 2
fi

# 2. Start Device simulators in background
echo "[RUNNER] Launching $DEVICES device simulators..."
for ((i=1; i<=DEVICES; i++)); do
  dev_id="device-$i"
  python src/device_zenoh.py "$dev_id" --router "$ZENOH_ROUTER" >/dev/null 2>&1 &
  pid=$!
  DEVICE_PIDS+=("$pid")
  echo "  -> Started $dev_id (PID: $pid)"
done

# Wait for devices to connect and subscribe
sleep 1

# 3. Run Edge Node
echo "[RUNNER] Starting Edge Node..."
python src/edge_zenoh.py \
  --devices "$DEVICES" \
  --payload-size "$PAYLOAD_BYTES" \
  --interval "$INTERVAL_SEC" \
  --duration "$DURATION_SEC" \
  --output "$OUTPUT_CSV" \
  --router "$ZENOH_ROUTER"

# Clean up will be run automatically via traps on exit

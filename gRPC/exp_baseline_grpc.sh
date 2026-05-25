#!/bin/bash

# Default values
DEVICES=${1:-2}
PAYLOAD_BYTES=${2:-100}
INTERVAL_SEC=${3:-0.1}
DURATION_SEC=${4:-60}
OUTPUT_CSV=${5:-"results/grpc_baseline.csv"}
GRPC_SERVER=${6:-"localhost:50051"}

# Move to the script's directory to ensure paths are resolved correctly
cd "$(dirname "$0")"

echo "=================================================="
echo " RUNNING GRPC BASELINE EXPERIMENT"
echo "=================================================="
echo "Devices      : $DEVICES"
echo "Payload Size : $PAYLOAD_BYTES bytes"
echo "Interval     : $INTERVAL_SEC s"
echo "Duration     : $DURATION_SEC s"
echo "Output CSV   : $OUTPUT_CSV"
echo "gRPC Server  : $GRPC_SERVER"
echo "=================================================="

# Parse server port from endpoint
PORT="50051"
if [[ "$GRPC_SERVER" == *":"* ]]; then
  PORT="${GRPC_SERVER##*:}"
fi

# Ensure results directory exists
mkdir -p "$(dirname "$OUTPUT_CSV")"

# Store device process PIDs and Server PID
DEVICE_PIDS=()
SERVER_PID=""

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

  if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "[RUNNER] Stopping gRPC server (PID: $SERVER_PID)..."
    kill "$SERVER_PID"
    wait "$SERVER_PID" 2>/dev/null
  fi
  echo "[RUNNER] Cleanup complete."
}

# Register traps to ensure cleanup runs on exit/interrupted
trap cleanup EXIT INT TERM

# 1. Start gRPC Server in background
echo "[RUNNER] Starting gRPC Server..."
python server.py \
  --port "$PORT" \
  --devices "$DEVICES" \
  --payload-size "$PAYLOAD_BYTES" \
  --interval "$INTERVAL_SEC" \
  --duration "$DURATION_SEC" \
  --output "$OUTPUT_CSV" &
SERVER_PID=$!
echo "  -> Started Server (PID: $SERVER_PID)"

# Wait for server to bind and listen
sleep 2

# Resolve target device count or names
TARGET_DEVS=()
if [[ "$DEVICES" =~ ^[0-9]+$ ]]; then
  for ((i=1; i<=DEVICES; i++)); do
    TARGET_DEVS+=("device-$i")
  done
else
  IFS=',' read -ra ADDR <<< "$DEVICES"
  for dev in "${ADDR[@]}"; do
    TARGET_DEVS+=("$dev")
  done
fi

# 2. Start Device simulators in background
echo "[RUNNER] Launching ${#TARGET_DEVS[@]} device simulators..."
for dev_id in "${TARGET_DEVS[@]}"; do
  python client.py "$dev_id" --server "$GRPC_SERVER" >/dev/null 2>&1 &
  pid=$!
  DEVICE_PIDS+=("$pid")
  echo "  -> Started $dev_id (PID: $pid)"
done

# 3. Wait for the server process to finish
wait "$SERVER_PID"

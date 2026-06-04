#!/bin/bash

# Default values
DEVICES=${1:-2}
PAYLOAD_BYTES=${2:-100}
INTERVAL_SEC=${3:-0.1}
DURATION_SEC=${4:-60}
OUTPUT_CSV=${5:-"results/mqtt_baseline.csv"}
MQTT_BROKER=${6:-"localhost:1883"}
MQTT_QOS=${7:-1}

# Move to the script's directory to ensure paths are resolved correctly
cd "$(dirname "$0")"

echo "=================================================="
echo " RUNNING MQTT BASELINE EXPERIMENT"
echo "=================================================="
echo "Devices      : $DEVICES"
echo "Payload Size : $PAYLOAD_BYTES bytes"
echo "Interval     : $INTERVAL_SEC s"
echo "Duration     : $DURATION_SEC s"
echo "Output CSV   : $OUTPUT_CSV"
echo "MQTT Broker  : $MQTT_BROKER"
echo "MQTT QoS     : $MQTT_QOS"
echo "=================================================="

# Ensure results directory exists
mkdir -p "$(dirname "$OUTPUT_CSV")"

# Store device process PIDs
DEVICE_PIDS=()
STARTED_BROKER=false

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

  if [ "$STARTED_BROKER" = true ]; then
    echo "[RUNNER] Stopping Docker MQTT broker container (mqtt-broker-exp)..."
    docker stop mqtt-broker-exp >/dev/null 2>&1
    docker rm mqtt-broker-exp >/dev/null 2>&1
  fi
  echo "[RUNNER] Cleanup complete."
}

# Register traps to ensure cleanup runs on exit/interrupted
trap cleanup EXIT INT TERM

# 1. Start Mosquitto Broker in Docker if not already running
if docker ps --format '{{.Names}}' | grep -Eq "^mqtt-broker-exp$|^mqtt-broker$"; then
  echo "[RUNNER] MQTT broker is already running."
else
  echo "[RUNNER] Starting MQTT broker container in background..."
  docker run -d --name mqtt-broker-exp -p 1883:1883 -v "$(pwd)/mosquitto.conf:/mosquitto/config/mosquitto.conf" eclipse-mosquitto:2 >/dev/null
  STARTED_BROKER=true
  # Wait for broker to initialize
  sleep 2
fi

# 2. Start Device simulators in background
echo "[RUNNER] Launching $DEVICES device simulators..."
if [[ "$DEVICES" =~ ^[0-9]+$ ]]; then
  NUM_DEVS=$DEVICES
  DEVS_LIST=()
  for ((i=1; i<=NUM_DEVS; i++)); do
    DEVS_LIST+=("device-$i")
  done
else
  IFS=',' read -r -a DEVS_LIST <<< "$DEVICES"
fi

for dev_id in "${DEVS_LIST[@]}"; do
  python src/device_mqtt.py "$dev_id" --broker "$MQTT_BROKER" --qos "$MQTT_QOS" >/dev/null 2>&1 &
  pid=$!
  DEVICE_PIDS+=("$pid")
  echo "  -> Started $dev_id (PID: $pid)"
done

# Wait for devices to connect and subscribe
sleep 1

# 3. Run Edge Node
echo "[RUNNER] Starting Edge Node..."
python src/edge_mqtt.py \
  --devices "$DEVICES" \
  --payload-size "$PAYLOAD_BYTES" \
  --interval "$INTERVAL_SEC" \
  --duration "$DURATION_SEC" \
  --output "$OUTPUT_CSV" \
  --broker "$MQTT_BROKER" \
  --qos "$MQTT_QOS"

# Clean up will be run automatically via traps on exit

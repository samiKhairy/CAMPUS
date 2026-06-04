import argparse
import csv
import json
import os
import signal
import sys
import time
import paho.mqtt.client as mqtt


def parse_args():
    parser = argparse.ArgumentParser(description="MQTT Edge Node")
    parser.add_argument(
        "--broker",
        default=os.getenv("MQTT_BROKER", "localhost:1883"),
        help="MQTT broker endpoint (default: MQTT_BROKER env var or 'localhost:1883')"
    )
    parser.add_argument(
        "--devices",
        default=os.getenv("TARGET_DEVICES", "device-1,device-2"),
        help="Comma-separated list of target device IDs, or an integer N to generate 'device-1' through 'device-N' (default: TARGET_DEVICES env var or 'device-1,device-2')"
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=float(os.getenv("RUN_DURATION", "0.0")),
        help="Run duration in seconds; 0 or negative means run indefinitely (default: RUN_DURATION env var or 0.0)"
    )
    parser.add_argument(
        "--max-messages",
        type=int,
        default=int(os.getenv("MAX_MESSAGES", "0")),
        help="Maximum number of messages to send per device; 0 or negative means unlimited (default: MAX_MESSAGES env var or 0)"
    )
    parser.add_argument(
        "--payload-size",
        type=int,
        default=int(os.getenv("PAYLOAD_BYTES", "100")),
        help="Size of the payload in bytes (default: PAYLOAD_BYTES env var or 100)"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=float(os.getenv("INTERVAL_SEC", "1.0")),
        help="Sending interval in seconds (default: INTERVAL_SEC env var or 1.0)"
    )
    parser.add_argument(
        "--output",
        default=os.getenv("OUTPUT_CSV", ""),
        help="Output CSV file path to write results (default: OUTPUT_CSV env var or auto-generated timestamp file)"
    )
    parser.add_argument(
        "--qos",
        type=int,
        default=int(os.getenv("MQTT_QOS", "1")),
        help="MQTT Quality of Service level: 0, 1, or 2 (default: MQTT_QOS env var or 1)"
    )
    return parser.parse_args()


args = parse_args()

# Process --devices: check if it's a number
devices_str = args.devices
if devices_str.isdigit():
    num_devs = int(devices_str)
    TARGET_DEVICES = [f"device-{i}" for i in range(1, num_devs + 1)]
else:
    TARGET_DEVICES = [d.strip() for d in devices_str.split(",") if d.strip()]

PAYLOAD_BYTES = args.payload_size
INTERVAL_SEC = args.interval
MQTT_BROKER = args.broker
RUN_DURATION = args.duration
MAX_MESSAGES = args.max_messages
MQTT_QOS = args.qos

# Initialize stats tracking dictionary
stats = {
    dev: {
        "count": 0,
        "records": []  # List of tuples: (send_ts_ns, recv_ts_ns, latency_ms)
    }
    for dev in TARGET_DEVICES
}

# Custom signal handler to catch Docker's SIGTERM signal
def sigterm_handler(signum, frame):
    print("[EDGE] Received SIGTERM from Docker. Raising KeyboardInterrupt...")
    raise KeyboardInterrupt

# Register the SIGTERM signal to trigger our handler
signal.signal(signal.SIGTERM, sigterm_handler)

# Parse broker host and port
broker_str = MQTT_BROKER
if "://" in broker_str:
    broker_str = broker_str.split("://")[1]
if ":" in broker_str:
    host, port_str = broker_str.split(":", 1)
    port = int(port_str)
else:
    host = broker_str
    port = 1883

# Create MQTT Client compatible with paho-mqtt v1 & v2
try:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
except AttributeError:
    client = mqtt.Client()

# Ack listener callback
def on_message(client, userdata, msg):
    recv_ts_ns = time.monotonic_ns()
    try:
        data = json.loads(msg.payload.decode('utf-8'))
        dev = data["device_id"]
        send_ts_ns = data["ts_edge_ns"]
        
        # Check if device is in our target list (ignore others)
        if dev not in stats:
            return
            
        rtt_ns = recv_ts_ns - send_ts_ns
        rtt_ms = rtt_ns / 1e6
        
        stats[dev]["records"].append((send_ts_ns, recv_ts_ns, rtt_ms))
        stats[dev]["count"] += 1

        # Calculate running average
        latencies = [r[2] for r in stats[dev]["records"]]
        avg_ms = sum(latencies) / len(latencies)

        print(f"[EDGE] Ack from {dev} -> RTT={rtt_ms:.2f} ms (Avg: {avg_ms:.2f} ms, Total acks: {stats[dev]['count']})")
    except Exception as e:
        print(f"[EDGE] Error handling ack: {e}")

client.on_message = on_message

# Connect to broker with retry logic
connected = False
for i in range(10):
    try:
        print(f"[EDGE] Connecting to broker at {host}:{port} (attempt {i+1}/10)...")
        client.connect(host, port, keepalive=60)
        connected = True
        break
    except Exception as e:
        print(f"[EDGE] Failed to connect: {e}. Retrying in 1 second...")
        time.sleep(1)

if not connected:
    print(f"[EDGE] Critical: Could not connect to broker at {host}:{port}. Exiting.")
    sys.exit(1)

# Start network loop
client.loop_start()

# Subscribe to all acks
ack_topic = "campus/ack/#"
client.subscribe(ack_topic, qos=MQTT_QOS)
print(f"[EDGE] Subscribed to {ack_topic} with QoS {MQTT_QOS}")

sent_counts = {dev: 0 for dev in TARGET_DEVICES}

# Startup delay to allow netem rules to be injected before data flow starts
START_DELAY_SEC = float(os.getenv("START_DELAY_SEC", "5.0"))
if START_DELAY_SEC > 0:
    print(f"[EDGE] Sleeping for {START_DELAY_SEC} seconds to allow network setup...")
    time.sleep(START_DELAY_SEC)

start_time = time.monotonic()

try: 
    print(f"[EDGE] Starting MQTT Edge Experiment...")
    print(f"       Broker: {host}:{port}")
    print(f"       Target Devices: {TARGET_DEVICES}")
    print(f"       Duration Limit: {RUN_DURATION if RUN_DURATION > 0 else 'Unlimited'} s")
    print(f"       Message Limit: {MAX_MESSAGES if MAX_MESSAGES > 0 else 'Unlimited'} msgs/device")
    print(f"       Payload Size: {PAYLOAD_BYTES} bytes")
    print(f"       Sending Interval: {INTERVAL_SEC} s")
    print(f"       MQTT QoS: {MQTT_QOS}")
    print("Press Ctrl+C to terminate early.")
    print("-" * 50)

    while True:
        # Check duration limit
        if RUN_DURATION > 0 and (time.monotonic() - start_time) >= RUN_DURATION:
            print(f"[EDGE] Duration limit ({RUN_DURATION}s) reached. Stopping sending loop...")
            break
            
        # Check max messages limit
        if MAX_MESSAGES > 0 and all(sent_counts[dev] >= MAX_MESSAGES for dev in TARGET_DEVICES):
            print(f"[EDGE] Max messages limit ({MAX_MESSAGES}) reached for all devices. Stopping sending loop...")
            break

        payload_str = "x" * PAYLOAD_BYTES

        for dev in TARGET_DEVICES:
            # If max messages limit is set, check if we've already met it for this device
            if MAX_MESSAGES > 0 and sent_counts[dev] >= MAX_MESSAGES:
                continue
                
            ts_edge_ns = time.monotonic_ns()
            payload = {
                "device_id": dev,
                "payload": payload_str,
                "ts_edge_ns": ts_edge_ns,
            }
            
            cmd_topic = f"campus/cmd/{dev}"
            client.publish(cmd_topic, json.dumps(payload), qos=MQTT_QOS)
            sent_counts[dev] += 1
            print(f"[EDGE] Sent to {dev} (Msg #{sent_counts[dev]}): {PAYLOAD_BYTES} bytes")
            
        time.sleep(INTERVAL_SEC)

except KeyboardInterrupt:
    print("\n[EDGE] Interrupted by user. Stopping sending loop...")

# Wait a brief moment for in-flight acks to arrive
print("[EDGE] Waiting 1 second for remaining acks in flight...")
time.sleep(1.0)

# Stop the network loop and disconnect
client.loop_stop()
client.disconnect()

# Write results
print("[EDGE] Saving statistics...")
os.makedirs("results", exist_ok=True)

if args.output:
    filename = args.output
else:
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"results/results_mqtt_{timestamp}.csv"

try:
    # Ensure directory of filename exists if custom output path is used
    out_dir = os.path.dirname(filename)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        
    with open(filename, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["device_id", "send_ts_ns", "recv_ts_ns", "latency_ms"])
        
        for dev in TARGET_DEVICES:
            for record in stats[dev]["records"]:
                send_ts, recv_ts, lat_ms = record
                writer.writerow([dev, send_ts, recv_ts, f"{lat_ms:.4f}"])
                
    print(f"[EDGE] Successfully wrote CSV results to: {filename}")
except Exception as e:
    print(f"[EDGE] Error saving CSV: {e}")

# Compute and print statistical summary
print("\n" + "="*50)
print("EXPERIMENT STATISTICAL SUMMARY")
print("="*50)
print(f"{'Device ID':<15} | {'Min (ms)':<10} | {'Avg (ms)':<10} | {'p95 (ms)':<10} | {'Acks Recv':<10}")
print("-"*50)

for dev in TARGET_DEVICES:
    records = stats[dev]["records"]
    if not records:
        print(f"{dev:<15} | {'N/A':<10} | {'N/A':<10} | {'N/A':<10} | {'0':<10}")
        continue
        
    latencies = [r[2] for r in records]
    sorted_lats = sorted(latencies)
    n = len(sorted_lats)
    
    min_lat = sorted_lats[0]
    avg_lat = sum(sorted_lats) / n
    p95_idx = min(int(n * 0.95), n - 1)
    p95_lat = sorted_lats[p95_idx]
    
    print(f"{dev:<15} | {min_lat:<10.2f} | {avg_lat:<10.2f} | {p95_lat:<10.2f} | {n:<10}")
print("="*50 + "\n")

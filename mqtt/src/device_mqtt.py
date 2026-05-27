import argparse
import os
import sys
import time
import json
import paho.mqtt.client as mqtt


def parse_args():
    parser = argparse.ArgumentParser(description="MQTT Device Simulator")
    parser.add_argument(
        "device_id",
        nargs="?",
        default=os.getenv("DEVICE_ID", "device-1"),
        help="Device Identifier (default: DEVICE_ID env var or 'device-1')"
    )
    parser.add_argument(
        "--broker",
        default=os.getenv("MQTT_BROKER", "localhost:1883"),
        help="MQTT broker endpoint (default: MQTT_BROKER env var or 'localhost:1883')"
    )
    parser.add_argument(
        "--qos",
        type=int,
        default=int(os.getenv("MQTT_QOS", "1")),
        help="MQTT Quality of Service level (default: MQTT_QOS env var or 1)"
    )
    return parser.parse_args()


args = parse_args()
device_id = args.device_id
MQTT_BROKER = args.broker
MQTT_QOS = args.qos

cmd_topic = f"campus/cmd/{device_id}"
ack_topic = f"campus/ack/{device_id}"

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

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[{device_id}] Connected to broker.")
        client.subscribe(cmd_topic, qos=MQTT_QOS)
        print(f"[{device_id}] Subscribed to {cmd_topic}, acks to {ack_topic}")
    else:
        print(f"[{device_id}] Connection failed with code {rc}")

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode('utf-8'))
        ts_edge_ns = data["ts_edge_ns"]
        ts_device_ns = time.monotonic_ns()

        print(f"[{device_id}] Received command: {data['payload'][:30]}...")

        ack = {
            "device_id": device_id,
            "status": "OK",
            "ts_edge_ns": ts_edge_ns,
            "ts_device_ns": ts_device_ns,
        }
        client.publish(ack_topic, json.dumps(ack), qos=MQTT_QOS)
    except Exception as e:
        print(f"[{device_id}] Error processing message: {e}")

client.on_connect = on_connect
client.on_message = on_message

# Connect with retry logic
connected = False
for i in range(10):
    try:
        print(f"[{device_id}] Connecting to broker at {host}:{port} (attempt {i+1}/10)...")
        client.connect(host, port, 60)
        connected = True
        break
    except Exception as e:
        print(f"[{device_id}] Connection failed: {e}. Retrying in 1 second...")
        time.sleep(1)

if not connected:
    print(f"[{device_id}] Critical: Could not connect to broker. Exiting.")
    sys.exit(1)

# Start network loop and loop forever
client.loop_start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print(f"\n[{device_id}] Exiting...")
    client.loop_stop()
    client.disconnect()

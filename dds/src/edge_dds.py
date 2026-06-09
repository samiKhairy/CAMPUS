"""
DDS Edge Node — CAMPUS Protocol Benchmark

Eclipse Cyclone DDS implementation of the edge→device pub/sub benchmark.
Uses RTPS/UDP (the native DDS wire protocol) — no broker, no router.

Architecture difference from the other protocols:
  - gRPC:       direct HTTP/2 streams, no intermediary
  - Zenoh:      router-mediated pub/sub
  - MQTT:       broker-mediated pub/sub
  - DDS/RTPS:   decentralized pub/sub over UDP, peer-to-peer discovery

The edge publishes commands on topic 'campus/cmd/{device_id}' and
subscribes to acks on topic 'campus/ack/{device_id}' for each target
device. DDS SPDP handles peer discovery automatically on the Docker
bridge network.
"""

import argparse
import csv
import json
import os
import signal
import sys
import time
import threading

from dataclasses import dataclass
from cyclonedds.domain import DomainParticipant
from cyclonedds.core import Qos, Policy, Listener
from cyclonedds.pub import DataWriter
from cyclonedds.sub import DataReader
from cyclonedds.topic import Topic
from cyclonedds.idl import IdlStruct
from cyclonedds.util import duration

# ---------------------------------------------------------------------------
# IDL data types — defined as Python dataclasses (no .idl file needed)
# ---------------------------------------------------------------------------

@dataclass
class CampusCommand(IdlStruct, typename="campus::Command"):
    """Edge → Device: a command carrying a payload and a send timestamp."""
    device_id: str
    payload: str
    ts_edge_ns: int  # monotonic_ns on the edge at send time


@dataclass
class CampusAck(IdlStruct, typename="campus::Ack"):
    """Device → Edge: acknowledgement echoing the send timestamp."""
    device_id: str
    status: str
    ts_edge_ns: int   # echoed from the command
    ts_device_ns: int  # monotonic_ns on the device at receive time


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

VERBOSE = os.getenv("VERBOSE", "0") == "1"


def parse_args():
    parser = argparse.ArgumentParser(description="DDS Edge Node (Cyclone DDS)")
    parser.add_argument(
        "--devices",
        default=os.getenv("TARGET_DEVICES", "device-1,device-2"),
        help="Comma-separated device IDs or integer N",
    )
    parser.add_argument(
        "--duration", type=float,
        default=float(os.getenv("RUN_DURATION", "0.0")),
        help="Run duration in seconds (0 = unlimited)",
    )
    parser.add_argument(
        "--max-messages", type=int,
        default=int(os.getenv("MAX_MESSAGES", "0")),
        help="Max messages per device (0 = unlimited)",
    )
    parser.add_argument(
        "--payload-size", type=int,
        default=int(os.getenv("PAYLOAD_BYTES", "100")),
        help="Payload size in bytes",
    )
    parser.add_argument(
        "--interval", type=float,
        default=float(os.getenv("INTERVAL_SEC", "1.0")),
        help="Sending interval in seconds",
    )
    parser.add_argument(
        "--output",
        default=os.getenv("OUTPUT_CSV", ""),
        help="Output CSV file path",
    )
    parser.add_argument(
        "--e2e",
        action="store_true",
        default=os.getenv("E2E_MODE", "0") == "1",
        help="Enable sequential E2E loop mode for downlink benchmarking (default: False)"
    )
    return parser.parse_args()


args = parse_args()

# Process --devices
devices_str = args.devices
if devices_str.isdigit():
    TARGET_DEVICES = [f"device-{i}" for i in range(1, int(devices_str) + 1)]
else:
    TARGET_DEVICES = [d.strip() for d in devices_str.split(",") if d.strip()]

PAYLOAD_BYTES = args.payload_size
INTERVAL_SEC = args.interval
RUN_DURATION = args.duration
MAX_MESSAGES = args.max_messages

# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

stats = {
    dev: {"count": 0, "records": []}
    for dev in TARGET_DEVICES
}
stats_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------

def sigterm_handler(signum, frame):
    print("[EDGE] Received SIGTERM. Raising KeyboardInterrupt...")
    raise KeyboardInterrupt

signal.signal(signal.SIGTERM, sigterm_handler)

# ---------------------------------------------------------------------------
# DDS setup
# ---------------------------------------------------------------------------

dp = DomainParticipant()

# Reliable QoS — mirrors MQTT QoS-1 (at-least-once) semantics
qos = Qos(
    Policy.Reliability.Reliable(max_blocking_time=duration(seconds=1)),
    Policy.History.KeepLast(100),
)

# Create one command topic + writer per device, and one ack topic + reader per device
cmd_topics = {}
cmd_writers = {}
ack_topics = {}
ack_readers = {}

for dev in TARGET_DEVICES:
    # Command topic: edge publishes, device subscribes
    cmd_topic_name = f"campus_cmd_{dev.replace('-', '_')}"
    cmd_topics[dev] = Topic(dp, cmd_topic_name, CampusCommand, qos=qos)
    cmd_writers[dev] = DataWriter(dp, cmd_topics[dev], qos=qos)

    # Ack topic: device publishes, edge subscribes
    ack_topic_name = f"campus_ack_{dev.replace('-', '_')}"
    ack_topics[dev] = Topic(dp, ack_topic_name, CampusAck, qos=qos)
    ack_readers[dev] = DataReader(dp, ack_topics[dev], qos=qos)

# ---------------------------------------------------------------------------
# Ack reader thread — polls all ack readers
# ---------------------------------------------------------------------------

running = True


def ack_reader_loop():
    """Background thread: polls all ack DataReaders for incoming samples."""
    while running:
        for dev in TARGET_DEVICES:
            try:
                samples = ack_readers[dev].take()
                for sample in samples:
                    recv_ts_ns = time.monotonic_ns()
                    send_ts_ns = sample.ts_edge_ns
                    
                    if args.e2e:
                        if dev == TARGET_DEVICES[0]:
                            # device-1 is the uplink trigger source. Forward the update to targets.
                            payload_str = "x" * PAYLOAD_BYTES
                            for target in TARGET_DEVICES[1:]:
                                forward_sample = CampusCommand(
                                    device_id=target,
                                    payload=payload_str,
                                    ts_edge_ns=send_ts_ns, # carry the original T0
                                )
                                cmd_writers[target].write(forward_sample)
                            continue
                        else:
                            # Target device: compute E2E latency = RTT / 2
                            e2e_ns = (recv_ts_ns - send_ts_ns) / 2
                            e2e_ms = e2e_ns / 1e6
                            with stats_lock:
                                stats[dev]["records"].append(
                                    (send_ts_ns, recv_ts_ns, e2e_ms)
                                )
                                stats[dev]["count"] += 1
                                count = stats[dev]["count"]
                                latencies = [r[2] for r in stats[dev]["records"]]
                                avg_ms = sum(latencies) / len(latencies)
                            if VERBOSE:
                                print(
                                    f"[EDGE] E2E Ack from {dev} -> E2E={e2e_ms:.2f} ms "
                                    f"(Avg: {avg_ms:.2f} ms, Total acks: {count})"
                                )
                    else:
                        rtt_ns = recv_ts_ns - send_ts_ns
                        rtt_ms = rtt_ns / 1e6

                        with stats_lock:
                            stats[dev]["records"].append(
                                (send_ts_ns, recv_ts_ns, rtt_ms)
                            )
                            stats[dev]["count"] += 1
                            count = stats[dev]["count"]
                            latencies = [r[2] for r in stats[dev]["records"]]
                            avg_ms = sum(latencies) / len(latencies)

                        if VERBOSE:
                            print(
                                f"[EDGE] Ack from {dev} -> RTT={rtt_ms:.2f} ms "
                                f"(Avg: {avg_ms:.2f} ms, Total acks: {count})"
                            )
            except Exception:
                pass
        time.sleep(0.005)  # 5ms poll interval — balance latency vs CPU


ack_thread = threading.Thread(target=ack_reader_loop, daemon=True)
ack_thread.start()

# ---------------------------------------------------------------------------
# Startup delay (same as all other protocols — wait for netem injection)
# ---------------------------------------------------------------------------

START_DELAY_SEC = float(os.getenv("START_DELAY_SEC", "5.0"))
if START_DELAY_SEC > 0:
    print(f"[EDGE] Sleeping for {START_DELAY_SEC}s to allow network setup...")
    time.sleep(START_DELAY_SEC)

# ---------------------------------------------------------------------------
# Main send loop
# ---------------------------------------------------------------------------

sent_counts = {dev: 0 for dev in TARGET_DEVICES}
start_time = time.monotonic()

try:
    print(f"[EDGE] Starting DDS Edge Experiment (Cyclone DDS / RTPS over UDP)...")
    print(f"       Target Devices: {TARGET_DEVICES}")
    print(f"       Duration Limit: {RUN_DURATION if RUN_DURATION > 0 else 'Unlimited'} s")
    print(f"       Message Limit: {MAX_MESSAGES if MAX_MESSAGES > 0 else 'Unlimited'} msgs/device")
    print(f"       Payload Size: {PAYLOAD_BYTES} bytes")
    print(f"       Sending Interval: {INTERVAL_SEC} s")
    print("-" * 50)

    while True:
        if RUN_DURATION > 0 and (time.monotonic() - start_time) >= RUN_DURATION:
            print(f"[EDGE] Duration limit ({RUN_DURATION}s) reached.")
            break

        if MAX_MESSAGES > 0 and all(
            sent_counts[dev] >= MAX_MESSAGES for dev in TARGET_DEVICES
        ):
            print(f"[EDGE] Max messages limit ({MAX_MESSAGES}) reached.")
            break

        payload_str = "x" * PAYLOAD_BYTES

        if args.e2e:
            dev = TARGET_DEVICES[0]
            if MAX_MESSAGES > 0 and sent_counts[dev] >= MAX_MESSAGES:
                break
            ts_edge_ns = time.monotonic_ns()
            sample = CampusCommand(
                device_id=dev,
                payload=payload_str,
                ts_edge_ns=ts_edge_ns,
            )
            cmd_writers[dev].write(sample)
            sent_counts[dev] += 1
            if VERBOSE:
                print(f"[EDGE] Sent E2E trigger to {dev} (Msg #{sent_counts[dev]}): {PAYLOAD_BYTES} bytes")
        else:
            for dev in TARGET_DEVICES:
                if MAX_MESSAGES > 0 and sent_counts[dev] >= MAX_MESSAGES:
                    continue

                ts_edge_ns = time.monotonic_ns()
                sample = CampusCommand(
                    device_id=dev,
                    payload=payload_str,
                    ts_edge_ns=ts_edge_ns,
                )
                cmd_writers[dev].write(sample)
                sent_counts[dev] += 1

                if VERBOSE:
                    print(f"[EDGE] Sent to {dev} (Msg #{sent_counts[dev]}): {PAYLOAD_BYTES} bytes")

        time.sleep(INTERVAL_SEC)

except KeyboardInterrupt:
    print("\n[EDGE] Interrupted. Stopping...")

# ---------------------------------------------------------------------------
# Shutdown & results
# ---------------------------------------------------------------------------

running = False
print("[EDGE] Waiting 1 second for remaining acks...")
time.sleep(1.0)

# Write CSV
if args.output:
    filename = args.output
else:
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"results/results_dds_{timestamp}.csv"

try:
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

# Print summary
print("\n" + "=" * 50)
print("EXPERIMENT STATISTICAL SUMMARY")
print("=" * 50)
print(f"{'Device ID':<15} | {'Min (ms)':<10} | {'Avg (ms)':<10} | {'p95 (ms)':<10} | {'Acks Recv':<10}")
print("-" * 50)

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

print("=" * 50 + "\n")

import argparse
import csv
import json
import os
import signal
import sys
import time
import zenoh

# VERBOSE=1 enables per-message stdout logging; off by default to keep sweep logs small.
VERBOSE = os.getenv("VERBOSE", "0") == "1"


# this function is used to parse the arguments passed to the script , parsing the arguments means checking for the arguments and processing them 
# for example the arguments can be the router address , device id , duration , payload size , interval , output file path 

def parse_args():
    # parser is used to parse the arguments passed to the script 
    # argparse is a python module which is used to parse the arguments passed to the script 
    # argumentparser is a object which is used to parse the arguments passed to the script   
    # description is used to provide a description of the script 
    parser = argparse.ArgumentParser(description="Zenoh Edge Node")
    # --router is used to specify the address of the router 
    # default=os.getenv("ZENOH_ROUTER", "tcp/localhost:7447") is used to specify the default value of the router 
    # help is used to provide a description of the router 
    parser.add_argument(
        "--router",
        default=os.getenv("ZENOH_ROUTER", "tcp/localhost:7447"),
        help="Zenoh router endpoint (default: ZENOH_ROUTER env var or 'tcp/localhost:7447')"
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
        "--e2e",
        action="store_true",
        default=os.getenv("E2E_MODE", "0") == "1",
        help="Enable sequential E2E loop mode for downlink benchmarking (default: False)"
    )
    return parser.parse_args()

    # all of the above functions or let's say argument parsing code is used to parse the arguments passed to the script 
    # parse_args() is called and the arguments are parsed and stored in the args variable
    # device_id is the id of the device 
    # router is the address of the router 
    # devices is the list of target devices 
    # duration is the run duration 
    # max_messages is the maximum number of messages to send per device 
    # payload_size is the size of the payload in bytes 
    # interval is the sending interval in seconds 
    # output is the output file path 

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
ZENOH_ROUTER = args.router
RUN_DURATION = args.duration
MAX_MESSAGES = args.max_messages

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

# Open session to router
conf = zenoh.Config()
conf.insert_json5('connect/endpoints', f'["{ZENOH_ROUTER}"]')
# QUIC transport requires TLS; trust the router's self-signed cert
if ZENOH_ROUTER.startswith("quic/"):
    conf.insert_json5("transport/link/tls/root_ca_certificate", '"/etc/zenoh/cert.pem"')
session = zenoh.open(conf)

# Declare publishers for each target device
pubs = {
    dev: session.declare_publisher(f"campus/cmd/{dev}")
    for dev in TARGET_DEVICES
}

# Ack listener callback
def on_ack(sample):
    recv_ts_ns = time.monotonic_ns()
    try:
        data = json.loads(sample.payload.to_string())
        dev = data["device_id"]
        send_ts_ns = data["ts_edge_ns"]
        
        # Check if device is in our target list (ignore others)
        if dev not in stats:
            return
            
        if args.e2e:
            if dev == TARGET_DEVICES[0]:
                # device-1 is the uplink trigger source. Forward the update to targets.
                payload_str = "x" * PAYLOAD_BYTES
                forward_payload = {
                    "device_id": "",
                    "payload": payload_str,
                    "ts_edge_ns": send_ts_ns, # carry the original T0
                }
                for target in TARGET_DEVICES[1:]:
                    forward_payload["device_id"] = target
                    pubs[target].put(json.dumps(forward_payload))
                return
            else:
                # Target device: compute E2E latency = RTT / 2
                e2e_ns = (recv_ts_ns - send_ts_ns) / 2
                e2e_ms = e2e_ns / 1e6
                
                stats[dev]["records"].append((send_ts_ns, recv_ts_ns, e2e_ms))
                stats[dev]["count"] += 1
                
                latencies = [r[2] for r in stats[dev]["records"]]
                avg_ms = sum(latencies) / len(latencies)
                if VERBOSE:
                    print(f"[EDGE] E2E Ack from {dev} -> E2E={e2e_ms:.2f} ms (Avg: {avg_ms:.2f} ms, Total acks: {stats[dev]['count']})")
        else:
            rtt_ns = recv_ts_ns - send_ts_ns
            rtt_ms = rtt_ns / 1e6
            
            stats[dev]["records"].append((send_ts_ns, recv_ts_ns, rtt_ms))
            stats[dev]["count"] += 1

            # Calculate running average
            latencies = [r[2] for r in stats[dev]["records"]]
            avg_ms = sum(latencies) / len(latencies)

            if VERBOSE:
                print(f"[EDGE] Ack from {dev} -> RTT={rtt_ms:.2f} ms (Avg: {avg_ms:.2f} ms, Total acks: {stats[dev]['count']})")
    except Exception as e:
        print(f"[EDGE] Error handling ack: {e}")

# Subscribe to all acks
ack_sub = session.declare_subscriber("campus/ack/**", on_ack)

sent_counts = {dev: 0 for dev in TARGET_DEVICES}

# Startup delay to allow netem rules to be injected before data flow starts
START_DELAY_SEC = float(os.getenv("START_DELAY_SEC", "5.0"))
if START_DELAY_SEC > 0:
    print(f"[EDGE] Sleeping for {START_DELAY_SEC} seconds to allow network setup...")
    time.sleep(START_DELAY_SEC)

start_time = time.monotonic()

try: 
    print(f"[EDGE] Starting Zenoh Edge Experiment...")
    print(f"       Router: {ZENOH_ROUTER}")
    print(f"       Target Devices: {TARGET_DEVICES}")
    print(f"       Duration Limit: {RUN_DURATION if RUN_DURATION > 0 else 'Unlimited'} s")
    print(f"       Message Limit: {MAX_MESSAGES if MAX_MESSAGES > 0 else 'Unlimited'} msgs/device")
    print(f"       Payload Size: {PAYLOAD_BYTES} bytes")
    print(f"       Sending Interval: {INTERVAL_SEC} s")
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

        if args.e2e:
            dev = TARGET_DEVICES[0]
            if MAX_MESSAGES > 0 and sent_counts[dev] >= MAX_MESSAGES:
                break
            ts_edge_ns = time.monotonic_ns()
            payload = {
                "device_id": dev,
                "payload": payload_str,
                "ts_edge_ns": ts_edge_ns,
            }
            pubs[dev].put(json.dumps(payload))
            sent_counts[dev] += 1
            if VERBOSE:
                print(f"[EDGE] Sent E2E trigger to {dev} (Msg #{sent_counts[dev]}): {PAYLOAD_BYTES} bytes")
        else:
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
                
                pubs[dev].put(json.dumps(payload))
                sent_counts[dev] += 1
                if VERBOSE:
                    print(f"[EDGE] Sent to {dev} (Msg #{sent_counts[dev]}): {PAYLOAD_BYTES} bytes")
            
        time.sleep(INTERVAL_SEC)

except KeyboardInterrupt:
    print("\n[EDGE] Interrupted by user. Stopping sending loop...")

# Wait a brief moment for in-flight acks to arrive
print("[EDGE] Waiting 1 second for remaining acks in flight...")
time.sleep(1.0)

# Write results
print("[EDGE] Saving statistics...")
os.makedirs("results", exist_ok=True)

if args.output:
    filename = args.output
else:
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"results/results_zenoh_{timestamp}.csv"

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

try:
    session.close()
except Exception as e:
    pass
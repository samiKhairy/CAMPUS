import subprocess
import time
import sys
import os
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description="gRPC Multi-Device Simulator Launcher")
    parser.add_argument(
        "--devices",
        type=int,
        default=10,
        help="Number of simulated devices to launch (default: 10)"
    )
    parser.add_argument(
        "--server",
        default=os.getenv("GRPC_SERVER", "localhost:50051"),
        help="gRPC server endpoint (default: GRPC_SERVER env var or 'localhost:50051')"
    )
    return parser.parse_args()

args = parse_args()
NUM_DEVICES = args.devices
server_address = args.server
processes = []

try:
    print(f"[RUNNER] Starting {NUM_DEVICES} gRPC devices pointing to {server_address}...")
    for i in range(1, NUM_DEVICES + 1):
        device_id = f"device-{i}"
        
        # Resolve the device script path (client.py is in the parent directory of this scripts folder)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.abspath(os.path.join(script_dir, "..", "client.py"))
        
        p = subprocess.Popen(
            [sys.executable, script_path, device_id, "--server", server_address],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        processes.append((device_id, p))
        print(f"  -> Started {device_id} (PID: {p.pid})")

    print("\n[RUNNER] All devices are running. Press Ctrl+C to terminate all of them.")
    
    # Keep the runner script alive to monitor and clean up subprocesses
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("\n[RUNNER] Terminating all device processes...")
    for device_id, p in processes:
        print(f"  -> Stopping {device_id} (PID: {p.pid})...")
        p.terminate()  # Sends termination signal
        p.wait()       # Waits for process to release resources
    print("[RUNNER] All devices stopped successfully.")

import subprocess
import time
import sys
import os

NUM_DEVICES = 10
processes = []

try:
    print(f"[RUNNER] Starting {NUM_DEVICES} Zenoh devices...")
    for i in range(1, NUM_DEVICES + 1):
        device_id = f"device-{i}"
        
        # Resolve the device script path relative to this runner script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(script_dir, "..", "src", "device_zenoh.py")
        p = subprocess.Popen(
            [sys.executable, script_path, device_id],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        processes.append((device_id, p))
        print(f"  -> Started {device_id} (PID: {p.pid})")

    print("\n[RUNNER] All devices are running. Press Ctrl+C to terminate all of them.")
    
    # Keep the runner script alive so it can monitor and eventually clean up the processes
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("\n[RUNNER] Terminating all device processes...")
    for device_id, p in processes:
        print(f"  -> Stopping {device_id} (PID: {p.pid})...")
        p.terminate()  # Sends termination signal
        p.wait()       # Waits for process to release resources
    print("[RUNNER] All devices stopped successfully.")

import argparse
import csv
import os
import signal
import sys
import time
import queue
import threading
from concurrent import futures
import grpc
import device_pb2
import device_pb2_grpc

def parse_args():
    parser = argparse.ArgumentParser(description="gRPC Edge Server (5G Simulation)")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("GRPC_PORT", "50051")),
        help="gRPC server port (default: 50051)"
    )
    parser.add_argument(
        "--devices",
        default=os.getenv("TARGET_DEVICES", "device-1"),
        help="Comma-separated list of target device IDs, or N (default: device-1)"
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=float(os.getenv("RUN_DURATION", "0.0")),
        help="Run duration in seconds; 0 or negative means indefinite (default: 0.0)"
    )
    parser.add_argument(
        "--max-messages",
        type=int,
        default=int(os.getenv("MAX_MESSAGES", "0")),
        help="Max messages to send per device; 0 means unlimited (default: 0)"
    )
    parser.add_argument(
        "--payload-size",
        type=int,
        default=int(os.getenv("PAYLOAD_BYTES", "100")),
        help="Payload size in bytes (default: 100)"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=float(os.getenv("INTERVAL_SEC", "1.0")),
        help="Sending interval in seconds (default: 1.0)"
    )
    parser.add_argument(
        "--output",
        default=os.getenv("OUTPUT_CSV", ""),
        help="Output CSV file path (default: auto-generated filename)"
    )
    return parser.parse_args()

args = parse_args()

# Process --devices parameter
devices_str = args.devices
if devices_str.isdigit():
    num_devs = int(devices_str)
    TARGET_DEVICES = [f"device-{i}" for i in range(1, num_devs + 1)]
else:
    TARGET_DEVICES = [d.strip() for d in devices_str.split(",") if d.strip()]

PAYLOAD_BYTES = args.payload_size
INTERVAL_SEC = args.interval
GRPC_PORT = args.port
RUN_DURATION = args.duration
MAX_MESSAGES = args.max_messages

class DeviceService(device_pb2_grpc.DeviceServiceServicer):
    def __init__(self, target_devices):
        self.target_devices = target_devices
        self.command_queues = {}
        self.lock = threading.Lock()
        
        # Stats structure
        self.stats = {
            dev: {
                "count": 0,
                "records": []  # Tuples of (send_ts, recv_ts, rtt_ms)
            }
            for dev in self.target_devices
        }

    def Register(self, request, context):
        device_id = request.device_id
        print(f"[EDGE] Register request from {device_id}")
        return device_pb2.RegisterAck(success=True)

    def CommandStream(self, request_iterator, context):
        command_queue = queue.Queue()
        client_device_id = None

        def consume_acks():
            nonlocal client_device_id
            try:
                for ack in request_iterator:
                    device_id = ack.device_id
                    client_device_id = device_id
                    
                    with self.lock:
                        self.command_queues[device_id] = command_queue
                    
                    # Ignore setup messages
                    if ack.ts_edge_ns == 0 or ack.status == "Connected":
                        print(f"[EDGE] Stream connection active for {device_id}")
                        continue
                    
                    # Measure RTT latency
                    recv_ts_ns = time.time_ns()
                    send_ts_ns = ack.ts_edge_ns
                    
                    if device_id not in self.stats:
                        continue
                        
                    rtt_ns = recv_ts_ns - send_ts_ns
                    rtt_ms = rtt_ns / 1e6
                    
                    with self.lock:
                        self.stats[device_id]["records"].append((send_ts_ns, recv_ts_ns, rtt_ms))
                        self.stats[device_id]["count"] += 1
                        avg_ms = sum([r[2] for r in self.stats[device_id]["records"]]) / len(self.stats[device_id]["records"])
                        
                    print(f"[EDGE] Ack from {device_id} -> RTT={rtt_ms:.2f} ms (Avg: {avg_ms:.2f} ms)")
            except grpc.RpcError:
                pass
            except Exception as e:
                print(f"[EDGE] Error handling ack: {e}")

        # Consume incoming client acknowledgments asynchronously
        ack_thread = threading.Thread(target=consume_acks, daemon=True)
        ack_thread.start()

        # Send outgoing server commands
        while context.is_active():
            try:
                command = command_queue.get(timeout=0.5)
                yield command
            except queue.Empty:
                continue

        if client_device_id:
            with self.lock:
                if client_device_id in self.command_queues:
                    del self.command_queues[client_device_id]
            print(f"[EDGE] Stream closed for {client_device_id}")

    def send_command(self, device_id, payload_str, ts_edge_ns):
        with self.lock:
            if device_id not in self.command_queues:
                return False
            
            command = device_pb2.Command(
                device_id=device_id,
                payload=payload_str,
                ts_edge_ns=ts_edge_ns
            )
            self.command_queues[device_id].put(command)
            return True

def sigterm_handler(signum, frame):
    print("[EDGE] Received SIGTERM signal. Propagating KeyboardInterrupt...")
    raise KeyboardInterrupt

signal.signal(signal.SIGTERM, sigterm_handler)

def serve():
    service = DeviceService(TARGET_DEVICES)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    device_pb2_grpc.add_DeviceServiceServicer_to_server(service, server)
    server.add_insecure_port(f'[::]:{GRPC_PORT}')
    
    server.start()
    
    sent_counts = {dev: 0 for dev in TARGET_DEVICES}
    start_time = time.time()
    
    print(f"[EDGE] Starting 5G Edge gRPC Server...")
    print(f"       Listening Port: {GRPC_PORT}")
    print(f"       Target Devices: {TARGET_DEVICES}")
    print(f"       Duration Limit: {RUN_DURATION if RUN_DURATION > 0 else 'Unlimited'} s")
    print(f"       Payload Size:   {PAYLOAD_BYTES} bytes")
    print(f"       Send Interval:  {INTERVAL_SEC} s")
    print("-" * 50)
    
    try:
        while True:
            if RUN_DURATION > 0 and (time.time() - start_time) >= RUN_DURATION:
                print(f"[EDGE] Duration limit ({RUN_DURATION}s) reached. Stopping sending loop...")
                break
                
            if MAX_MESSAGES > 0 and all(sent_counts[dev] >= MAX_MESSAGES for dev in TARGET_DEVICES):
                print(f"[EDGE] Message limit reached. Stopping sending loop...")
                break

            payload_str = "x" * PAYLOAD_BYTES

            for dev in TARGET_DEVICES:
                if MAX_MESSAGES > 0 and sent_counts[dev] >= MAX_MESSAGES:
                    continue
                    
                ts_edge_ns = time.time_ns()
                success = service.send_command(dev, payload_str, ts_edge_ns)
                if success:
                    sent_counts[dev] += 1
                    print(f"[EDGE] Sent command to {dev} (Msg #{sent_counts[dev]})")
                    
            time.sleep(INTERVAL_SEC)
            
    except KeyboardInterrupt:
        print("\n[EDGE] Interrupt received. Terminating server...")
        
    server.stop(0)
    time.sleep(1.0)
    
    # Save stats
    print("[EDGE] Writing metrics...")
    os.makedirs("results", exist_ok=True)
    if args.output:
        filename = args.output
    else:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"results/results_5g_grpc_{timestamp}.csv"
        
    try:
        with open(filename, mode="w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["device_id", "send_ts_ns", "recv_ts_ns", "latency_ms"])
            for dev in TARGET_DEVICES:
                for record in service.stats[dev]["records"]:
                    send_ts, recv_ts, lat_ms = record
                    writer.writerow([dev, send_ts, recv_ts, f"{lat_ms:.4f}"])
        print(f"[EDGE] Successfully wrote CSV to: {filename}")
    except Exception as e:
        print(f"[EDGE] Error saving CSV: {e}")
        
    # Statistical summary output
    print("\n" + "="*50)
    print("5G SIMULATION EXPERIMENT SUMMARY")
    print("="*50)
    print(f"{'Device ID':<15} | {'Min (ms)':<10} | {'Avg (ms)':<10} | {'p95 (ms)':<10} | {'Acks Recv':<10}")
    print("-"*50)
    for dev in TARGET_DEVICES:
        records = service.stats[dev]["records"]
        if not records:
            print(f"{dev:<15} | {'N/A':<10} | {'N/A':<10} | {'N/A':<10} | {'0':<10}")
            continue
        lats = [r[2] for r in records]
        sorted_lats = sorted(lats)
        n = len(sorted_lats)
        min_lat = sorted_lats[0]
        avg_lat = sum(sorted_lats) / n
        p95_idx = min(int(n * 0.95), n - 1)
        p95_lat = sorted_lats[p95_idx]
        print(f"{dev:<15} | {min_lat:<10.2f} | {avg_lat:<10.2f} | {p95_lat:<10.2f} | {n:<10}")
    print("="*50 + "\n")

if __name__ == '__main__':
    serve()

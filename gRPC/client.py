import argparse
import os
import sys
import time
import queue
import signal
import grpc
import device_pb2
import device_pb2_grpc

def parse_args():
    parser = argparse.ArgumentParser(description="gRPC Device Simulator")
    parser.add_argument(
        "device_id",
        nargs="?",
        default=os.getenv("DEVICE_ID", "device-1"),
        help="Device Identifier (default: DEVICE_ID env var or 'device-1')"
    )
    parser.add_argument(
        "--server",
        default=os.getenv("GRPC_SERVER", "localhost:50051"),
        help="gRPC server endpoint (default: GRPC_SERVER env var or 'localhost:50051')"
    )
    return parser.parse_args()

def command_ack_generator(ack_queue):
    """
    Generator function that continuously yields CommandAck messages 
    from the queue to the server over the open stream.
    """
    while True:
        ack = ack_queue.get()
        yield ack

def run_client():
    args = parse_args()
    device_id = args.device_id
    server_address = args.server

    print(f"[{device_id}] Connecting to gRPC Server at {server_address}...")
    channel = grpc.insecure_channel(server_address)
    stub = device_pb2_grpc.DeviceServiceStub(channel)

    try:
        # Step 1: Register the device identity (Unary RPC)
        register_request = device_pb2.DeviceInfo(device_id=device_id)
        register_response = stub.Register(register_request)
        print(f"[{device_id}] Register response: success={register_response.success}")
    except grpc.RpcError as e:
        print(f"[{device_id}] Failed to register with server: {e.details() if hasattr(e, 'details') else e}")
        sys.exit(1)

    # Step 2: Establish the bidirectional streaming RPC
    ack_queue = queue.Queue()
    
    # Put initial connection acknowledgment in the queue
    ack_queue.put(device_pb2.CommandAck(
        device_id=device_id,
        status="Connected",
        ts_device_ns=time.monotonic_ns(),
        ts_edge_ns=0
    ))

    # This creates a generator for sending acknowledgements
    ack_gen = command_ack_generator(ack_queue)
    
    try:
        # Call CommandStream, passing the generator. This returns an iterator for server Commands.
        response_iterator = stub.CommandStream(ack_gen)
        print(f"[{device_id}] Opened CommandStream. Awaiting commands...")

        # Process incoming commands from the server
        for command in response_iterator:
            ts_device_ns = time.monotonic_ns()
            print(f"[{device_id}] Received command: {len(command.payload)} bytes")
            
            # Echo back the send timestamp ts_edge_ns for RTT calculation
            ack = device_pb2.CommandAck(
                device_id=device_id,
                status="OK",
                ts_device_ns=ts_device_ns,
                ts_edge_ns=command.ts_edge_ns
            )
            ack_queue.put(ack)

    except grpc.RpcError as e:
        print(f"[{device_id}] Stream error or server disconnected: {e.details() if hasattr(e, 'details') else e}")
    except KeyboardInterrupt:
        print(f"\n[{device_id}] Interrupted by user. Exiting...")
    finally:
        channel.close()
        print(f"[{device_id}] Connection closed.")

if __name__ == '__main__':
    # Map SIGTERM (sent by Docker / host runners) to raise KeyboardInterrupt for graceful shutdown
    def sigterm_handler(signum, frame):
        print(f"[CLIENT] Received SIGTERM. Exiting gracefully...")
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, sigterm_handler)
    run_client()

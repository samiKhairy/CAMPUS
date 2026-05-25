import argparse
import os
import queue
import socket
import sys
import time
import grpc
import device_pb2
import device_pb2_grpc

# On Linux, we can query network interface IP addresses using fcntl
try:
    import fcntl
    import struct
    def get_ip_address(ifname):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return socket.inet_ntoa(fcntl.ioctl(
            s.fileno(),
            0x8915,  # SIOCGIFADDR
            struct.pack('256s', ifname[:15].encode('utf-8'))
        )[20:24])
except ImportError:
    # Fallback for non-Linux or Windows testing
    def get_ip_address(ifname):
        return None

def parse_args():
    parser = argparse.ArgumentParser(description="gRPC Client (5G UE Device)")
    parser.add_argument(
        "device_id",
        nargs="?",
        default=os.getenv("DEVICE_ID", "device-1"),
        help="Device Identifier (default: device-1)"
    )
    parser.add_argument(
        "--server",
        default=os.getenv("GRPC_SERVER", "edge-server:50051"),
        help="Server endpoint (default: edge-server:50051)"
    )
    parser.add_argument(
        "--bind-interface",
        default=os.getenv("BIND_INTERFACE", ""),
        help="Interface to bind socket (e.g. uesimtun0)"
    )
    return parser.parse_args()

def run():
    args = parse_args()
    device_id = args.device_id
    server_address = args.server
    
    print(f"[UE] Starting Client {device_id}...")
    
    # Configure socket binding to force traffic through the 5G interface
    channel_options = []
    if args.bind_interface:
        try:
            local_ip = get_ip_address(args.bind_interface)
            if local_ip:
                print(f"[UE] Binding gRPC socket to interface {args.bind_interface} (IP: {local_ip})")
                # Force gRPC to bind its local socket to the 5G network IP
                channel_options.append(('grpc.local_ip_to_bind', local_ip))
            else:
                print(f"[UE] Warning: Could not resolve IP for {args.bind_interface}")
        except Exception as e:
            print(f"[UE] Error binding to interface {args.bind_interface}: {e}")
            
    # Connect to the edge server
    print(f"[UE] Connecting to Edge Server at {server_address}...")
    channel = grpc.insecure_channel(server_address, options=channel_options)
    stub = device_pb2_grpc.DeviceServiceStub(channel)
    
    # Register with the server
    try:
        reg_request = device_pb2.DeviceInfo(device_id=device_id)
        reg_response = stub.Register(reg_request)
        print(f"[UE] Registration response: success={reg_response.success}")
    except grpc.RpcError as e:
        print(f"[UE] Registration failed: {e.code()} - {e.details()}")
        sys.exit(1)
        
    # Queue to manage outgoing acknowledgements back to the server (handled in iterator)
    ack_queue = None
    
    # Simple generator for client acknowledgments
    def ack_generator():
        # First send a dummy connection notice to activate the bidirectional stream
        yield device_pb2.CommandAck(
            device_id=device_id,
            ts_edge_ns=0,
            status="Connected"
        )
        
        while True:
            # We will populate this loop by yielding from incoming command events
            time.sleep(0.1)

    # In Python gRPC, we can implement bidirectional streaming by passing an iterator
    # of requests to the stub call.
    try:
        # Create generator to yield acks
        requests = []
        
        # Open bidirectional stream
        commands = stub.CommandStream(iter(requests))
        
        # First send the initial registration handshake
        # Because we need to yield values dynamically, we use a queue pattern or a generator
        def send_initial_ack():
            # A simple queue of requests we yield from
            pass
            
        print("[UE] Bidirectional stream active. Listening for commands...")
        
        # We simulate the stream loop
        # For simplicity in standard synchronous python gRPC, we can make the generator dynamic
        # or use a helper class
        class AckIterator:
            def __init__(self):
                self._queue = queue.Queue()
                # Queue the initial connection handshake
                self._queue.put(device_pb2.CommandAck(
                    device_id=device_id,
                    ts_edge_ns=0,
                    status="Connected"
                ))
            def __iter__(self):
                return self
            def __next__(self):
                return self._queue.get()
            def put(self, ack):
                self._queue.put(ack)
                
        ack_iter = AckIterator()
        
        # Start the stream
        response_stream = stub.CommandStream(ack_iter)
        
        # Read incoming commands from the server
        for command in response_stream:
            print(f"[UE] Received command from Edge: '{command.payload[:20]}...' (Timestamp: {command.ts_edge_ns})")
            
            # Create an immediate acknowledgement returning the original send timestamp
            ack = device_pb2.CommandAck(
                device_id=device_id,
                ts_edge_ns=command.ts_edge_ns,
                status="Received"
            )
            # Push the ack to our stream iterator to send it back to the edge
            ack_iter.put(ack)
            print(f"[UE] Sent acknowledgment for command ts: {command.ts_edge_ns}")
            
    except grpc.RpcError as e:
        print(f"[UE] gRPC Stream Error: {e.code()} - {e.details()}")
    except KeyboardInterrupt:
        print("\n[UE] Terminating client...")
    finally:
        channel.close()
        print("[UE] Disconnected.")

if __name__ == '__main__':
    run()

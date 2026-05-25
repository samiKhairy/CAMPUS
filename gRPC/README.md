# CAMPUS gRPC Prototype

## What this project is

This is a local gRPC prototype for the CAMPUS edge-device pattern.

- `server.py` is the edge node (gRPC server).
- `client.py` is a device client process.
- `proto/device.proto` defines the shared service and messages.
- `device_pb2.py` and `device_pb2_grpc.py` are generated from the proto.

The prototype demonstrates:

- Edge as gRPC server
- Devices as gRPC clients
- Unary `Register` for device identity
- Long-lived bidirectional `CommandStream`
- Edge pushes `Command` messages to devices, and devices reply with `CommandAck`
- Selective downlink to only some devices
- Simple latency logging for command round-trip

## Files

- `proto/device.proto` – shared contract for messages and service
- `device_pb2.py` – generated protobuf message classes
- `device_pb2_grpc.py` – generated gRPC stub and server classes
- `server.py` – edge implementation and selective command sender
- `client.py` – device client implementation
- `docker/Dockerfile.server` – Dockerfile for the edge server
- `docker/Dockerfile.client` – Dockerfile for the client device
- `docker-compose.yml` – orchestrates the containerized services

## Requirements

Install Python dependencies:

```powershell
python -m pip install grpcio grpcio-tools
```

On Linux/macOS, use bash-style commands instead:

```bash
pip install grpcio grpcio-tools
python -m grpc_tools.protoc -I=proto --python_out=. --grpc_python_out=. proto/device.proto
```

Generate the Python bindings if needed:

```powershell
python -m grpc_tools.protoc -I=proto --python_out=. --grpc_python_out=. proto/device.proto
```

## How to run

### Method A: Running with Docker Compose (Recommended)

This method sets up an isolated virtual bridge network where each container runs in its own environment.

1. **Start the testbed:**
   ```bash
   docker compose up --build
   ```
2. **Observe:** The terminals will print logs from the edge server and the device client processes showing command stream creation, command sending, and RTT latency statistics.
3. **Stop the containers:**
   Press `Ctrl + C` in the running terminal, or run:
   ```bash
   docker compose down
   ```

### Method B: Running Locally (For Fast Development)

#### 1. Start the edge server

```powershell
python server.py
```

#### 2. Start device clients in separate terminals

```powershell
python client.py device-1
python client.py device-2
python client.py device-3
```

#### 3. Change which devices receive commands

The server uses the `TARGET_DEVICES` environment variable to decide which devices get downlink commands.

PowerShell example:

```powershell
$env:TARGET_DEVICES = "device-1,device-2"
python server.py
```

Linux/macOS example:

```bash
TARGET_DEVICES="device-1,device-2" python server.py
```

If you set `TARGET_DEVICES=device-1,device-2`, then `device-3` stays connected but idle.

## What the logs show

### Server logs

- `Register request from device-1`
- `Device Opened Command Stream`
- `Sent command to device-1: hello device-1`
- `Round-trip latency for device-1 : 12.3 ms`

### Client logs

- `Client device-1 connected to server`
- `Register response: success=True`
- `Received command: device-1 : hello device-1`

## What this demonstrates for CAMPUS

This prototype proves the core CAMPUS pattern:

- each device opens a long-lived stream to the edge server
- edge maintains a stream handle per `device_id` and uses it to send commands selectively
- devices register with a `device_id`
- edge selects which devices receive commands
- devices can stay connected without receiving traffic
- edge measures latency from send to ack

## Next improvements

1. Add a real device selection config file or API.
2. Add better latency metrics and logging structure.
3. Containerize server and clients with Docker for a deployment-like setup.
4. Port the same code to the real CAMPUS edge and Orin devices by changing hostname/IP.

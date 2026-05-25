# MQTT Prototype — Implementation Plan - v1.0

Build the MQTT protocol module to achieve parity with the existing gRPC and Zenoh modules, completing the 3-protocol comparison set needed for week-1 deliverables to Filippo.

## User Review Required

> [!IMPORTANT]
> **Broker choice: Eclipse Mosquitto (TCP, QoS 1)**
> For week 1, I'm using Mosquitto — battle-tested, zero setup friction, 5-minute Docker integration. QUIC transport can be added in week 2 via NanoMQ as a separate experiment dimension. This keeps the week-1 brief focused on **protocol semantics** (RPC vs pub/sub broker vs pub/sub mesh), not transport layer differences.

> [!IMPORTANT]
> **Topic hierarchy matches Zenoh exactly:**
> - Commands: `campus/cmd/<device-id>` (edge → device)
> - Acks: `campus/ack/<device-id>` (device → edge, subscribed via `campus/ack/#` wildcard)
>
> This means the MQTT and Zenoh experiments use identical key/topic structures, making comparison fair and analysis scripts reusable.

## Open Questions

> [!NOTE]
> **QoS level:** Defaulting to **QoS 1** (at-least-once delivery). QoS 0 (fire-and-forget) and QoS 2 (exactly-once) can be tested as additional experiment parameters later. QoS 1 is the closest match to Zenoh's default reliability and gRPC's reliable stream delivery.

## Proposed Changes

All new files are created under `d:\project campus\mqtt\`. No existing files are modified.

---

### Directory Structure (all [NEW])

```
mqtt/
├── README.md                    ← Documentation (same style as zenoh/README.md)
├── docker-compose.yml           ← Mosquitto broker + edge-node + device-1 + device-2
├── mosquitto.conf               ← Broker configuration (listener, anonymous access)
├── exp_baseline_mqtt.ps1        ← Windows PowerShell experiment automation script
├── exp_baseline_mqtt.sh         ← Linux/macOS Bash experiment automation script
├── docker/
│   ├── Dockerfile.edge          ← python:3.10-slim + paho-mqtt
│   └── Dockerfile.device        ← python:3.10-slim + paho-mqtt
├── src/
│   ├── edge_mqtt.py             ← Edge controller (publisher + subscriber + stats)
│   └── device_mqtt.py           ← Device simulator (subscriber + ack publisher)
├── scripts/
│   └── run_devices.py           ← Local multi-device launcher (same pattern as zenoh/gRPC)
└── results/                     ← Generated CSV files
```

---

### Broker Configuration

#### [NEW] [mosquitto.conf](file:///d:/project%20campus/mqtt/mosquitto.conf)

Minimal Mosquitto config:
- `listener 1883` — standard MQTT port
- `allow_anonymous true` — no auth for lab testbed
- `persistence false` — no disk persistence (latency testing)
- `log_type all` — full logging for debugging

---

### Source Code

#### [NEW] [edge_mqtt.py](file:///d:/project%20campus/mqtt/src/edge_mqtt.py)

The edge controller. Structurally mirrors [edge_zenoh.py](file:///d:/project%20campus/zenoh/src/edge_zenoh.py) with these adaptations:

| Zenoh concept | MQTT equivalent |
|---|---|
| `session = zenoh.open(conf)` | `client = mqtt.Client(); client.connect(broker)` |
| `session.declare_publisher(key)` | `client.publish(topic, payload)` |
| `session.declare_subscriber(key, callback)` | `client.subscribe(topic); client.on_message = callback` |
| `pub.put(json.dumps(data))` | `client.publish(topic, json.dumps(data), qos=1)` |

**Same CLI args and env vars as Zenoh/gRPC:**
- `--broker` / `MQTT_BROKER` (default: `localhost:1883`)
- `--devices` / `TARGET_DEVICES`
- `--duration` / `RUN_DURATION`
- `--max-messages` / `MAX_MESSAGES`
- `--payload-size` / `PAYLOAD_BYTES`
- `--interval` / `INTERVAL_SEC`
- `--output` / `OUTPUT_CSV`
- `--qos` / `MQTT_QOS` (default: `1`) — additional MQTT-specific parameter

**Same CSV output:** `device_id, send_ts_ns, recv_ts_ns, latency_ms`

**Same statistical summary:** min/avg/p95 per device on exit.

**SIGTERM handling:** Same `sigterm_handler` pattern for Docker graceful shutdown.

**Key implementation detail:** `paho-mqtt` runs a network loop in a background thread (`client.loop_start()`). The main thread runs the sending loop. The `on_message` callback processes acks and records latency stats.

#### [NEW] [device_mqtt.py](file:///d:/project%20campus/mqtt/src/device_mqtt.py)

The device simulator. Mirrors [device_zenoh.py](file:///d:/project%20campus/zenoh/src/device_zenoh.py):

1. Connects to broker
2. Subscribes to `campus/cmd/<device-id>`
3. On message: parses JSON, extracts `ts_edge_ns`, publishes ack to `campus/ack/<device-id>` with `ts_edge_ns` echoed back plus `ts_device_ns`
4. Sleeps in main loop to keep alive

**CLI args:** `device_id` (positional), `--broker` / `MQTT_BROKER`, `--qos` / `MQTT_QOS`

---

### Docker

#### [NEW] [Dockerfile.edge](file:///d:/project%20campus/mqtt/docker/Dockerfile.edge)

```dockerfile
FROM python:3.10-slim
WORKDIR /app
RUN pip install --no-cache-dir paho-mqtt
COPY src/edge_mqtt.py .
CMD ["python", "edge_mqtt.py"]
```

#### [NEW] [Dockerfile.device](file:///d:/project%20campus/mqtt/docker/Dockerfile.device)

```dockerfile
FROM python:3.10-slim
WORKDIR /app
RUN pip install --no-cache-dir paho-mqtt
COPY src/device_mqtt.py .
CMD ["python", "device_mqtt.py"]
```

#### [NEW] [docker-compose.yml](file:///d:/project%20campus/mqtt/docker-compose.yml)

```yaml
services:
  mqtt-broker:
    image: eclipse-mosquitto:2
    volumes: ["./mosquitto.conf:/mosquitto/config/mosquitto.conf"]
    ports: ["1883:1883"]

  edge-node:
    build: { context: ., dockerfile: docker/Dockerfile.edge }
    environment:
      - MQTT_BROKER=mqtt-broker
      - TARGET_DEVICES=device-1,device-2
      - PAYLOAD_BYTES=100
      - INTERVAL_SEC=1.0
    volumes: ["./results:/app/results"]
    depends_on: [mqtt-broker]

  device-1:
    build: { context: ., dockerfile: docker/Dockerfile.device }
    command: ["python", "device_mqtt.py", "device-1"]
    environment: { MQTT_BROKER: mqtt-broker }
    depends_on: [mqtt-broker]

  device-2:
    build: { context: ., dockerfile: docker/Dockerfile.device }
    command: ["python", "device_mqtt.py", "device-2"]
    environment: { MQTT_BROKER: mqtt-broker }
    depends_on: [mqtt-broker]
```

---

### Experiment Scripts

#### [NEW] [exp_baseline_mqtt.ps1](file:///d:/project%20campus/mqtt/exp_baseline_mqtt.ps1)

Same structure as [exp_baseline_zenoh.ps1](file:///d:/project%20campus/zenoh/exp_baseline_zenoh.ps1):
1. Start Mosquitto broker in Docker (if not running)
2. Spawn N device simulators as background processes
3. Run edge node in foreground with configured parameters
4. Cleanup all processes on exit

**Parameters:** `-Devices`, `-PayloadBytes`, `-IntervalSec`, `-DurationSec`, `-OutputCsv`, `-MqttBroker`

#### [NEW] [exp_baseline_mqtt.sh](file:///d:/project%20campus/mqtt/exp_baseline_mqtt.sh)

Bash equivalent for Linux/macOS.

#### [NEW] [run_devices.py](file:///d:/project%20campus/mqtt/scripts/run_devices.py)

Same structure as [run_devices.py](file:///d:/project%20campus/zenoh/scripts/run_devices.py): spawns N `device_mqtt.py` subprocesses, cleans up on Ctrl+C.

---

### Documentation

#### [NEW] [README.md](file:///d:/project%20campus/mqtt/README.md)

Same structure and depth as [zenoh README.md](file:///d:/project%20campus/zenoh/README.md):
- Context & goal
- Architecture diagram
- Directory structure
- Features & status
- Getting started (3 methods: automated harness, Docker Compose, local)
- Experiment parameters table
- CSV output format
- Constraints

---

## Verification Plan

### Automated Tests

1. **Docker Compose smoke test:**
   ```bash
   cd mqtt
   docker compose up --build
   ```
   Expect: broker starts, edge connects, devices connect, commands flow, RTT measurements print to console, CSV written on Ctrl+C shutdown.

2. **Local smoke test (Windows):**
   ```powershell
   .\exp_baseline_mqtt.ps1 -Devices 2 -DurationSec 10 -OutputCsv results/mqtt_smoke.csv
   ```
   Expect: CSV file created with valid rows, statistical summary printed.

3. **CSV format validation:**
   Verify output CSV has identical columns to gRPC/Zenoh: `device_id, send_ts_ns, recv_ts_ns, latency_ms`.

### Manual Verification

- Confirm `docker logs mqtt-broker` shows connected clients
- Confirm `docker logs edge-node` shows RTT measurements
- Confirm `results/` directory contains valid CSV after shutdown

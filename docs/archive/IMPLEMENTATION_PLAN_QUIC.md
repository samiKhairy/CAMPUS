# QUIC Phase Implementation Plan
**CAMPUS Project — Phase 2 Transport Layer**
Date: 2026-05-27

---

## Overview

Two new protocols added to the matrix runner:
- `zenoh-quic` — same Python code as `zenoh`, only endpoint strings change
- `mqtt-tcp-c` — NanoMQ broker + NanoSDK C clients over TCP (Option A baseline)
- `mqtt-quic` — NanoMQ broker + NanoSDK C clients over QUIC

Results land in:
- `results/matrix/zenoh-quic/{profile}/`
- `results/matrix/mqtt-tcp-c/{profile}/`
- `results/matrix/mqtt-quic/{profile}/`

Existing `results/matrix/grpc/`, `results/matrix/zenoh/`, `results/matrix/mqtt/` are untouched.

---

## Part 1 — Zenoh-QUIC

### 1.1 New directory: `zenoh-quic/`

Identical structure to `zenoh/`:
```
zenoh-quic/
├── docker/
│   ├── Dockerfile.edge     ← copy of zenoh/docker/Dockerfile.edge, no changes
│   └── Dockerfile.device   ← copy of zenoh/docker/Dockerfile.device, no changes
├── src/
│   ├── edge_zenoh.py       ← copy of zenoh/src/edge_zenoh.py, no changes
│   └── device_zenoh.py     ← copy of zenoh/src/device_zenoh.py, no changes
└── docker-compose.yml      ← new, see spec below
```

Python source is identical to the TCP variant — no code changes. The transport switch is
entirely in the endpoint string passed as an environment variable.

### 1.2 `zenoh-quic/docker-compose.yml`

Key differences from `zenoh/docker-compose.yml`:

1. **Router command**: pass `--listen quic/0.0.0.0:7447 --no-multicast-scouting` to `zenohd`
2. **Router port mapping**: `"7447:7447/udp"` — QUIC runs over UDP, not TCP
3. **Edge env var**: `ZENOH_ROUTER=quic/zenoh-router:7447`
4. **Device env var**: `ZENOH_ROUTER=quic/zenoh-router:7447`

```yaml
services:
  zenoh-router:
    image: eclipse/zenoh:latest
    container_name: zenoh-router
    command: ["--listen", "quic/0.0.0.0:7447", "--no-multicast-scouting"]
    ports:
      - "7447:7447/udp"          # UDP — not TCP
    networks:
      - campus-net

  edge-node:
    build:
      context: .
      dockerfile: docker/Dockerfile.edge
    container_name: edge-node
    environment:
      - ZENOH_ROUTER=quic/zenoh-router:7447
      - PAYLOAD_BYTES=100
      - INTERVAL_SEC=1.0
      - TARGET_DEVICES=device-1,device-2
    volumes:
      - ./results:/app/results
    depends_on:
      - zenoh-router
    cap_add:
      - NET_ADMIN
    networks:
      - campus-net

  device-1:
    build:
      context: .
      dockerfile: docker/Dockerfile.device
    container_name: device-1
    command: ["python", "device_zenoh.py", "device-1"]
    environment:
      - ZENOH_ROUTER=quic/zenoh-router:7447
    depends_on:
      - zenoh-router
    cap_add:
      - NET_ADMIN
    networks:
      - campus-net

networks:
  campus-net:
    driver: bridge
```

### 1.3 Verification step (manual, before matrix run)

Run `zenoh-quic/docker-compose.yml` manually with N=1, clean, and confirm:
- Router logs show `Listening on quic/...` not `tcp/...`
- RTT results are comparable to zenoh/TCP clean baseline (~1ms)
- If router logs show TCP fallback, the QUIC endpoint is not configured correctly

---

## Part 2 — MQTT-QUIC (Option A: C clients, NanoMQ broker)

### 2.1 Rationale for Option A

The existing `mqtt` protocol uses paho-mqtt (Python) + Mosquitto. Comparing that directly
to QUIC would confound three variables: transport, broker, and client library. Option A
rewrites both TCP and QUIC variants in C with NanoSDK against NanoMQ, so only the transport
differs between `mqtt-tcp-c` and `mqtt-quic`.

### 2.2 New directory: `mqtt-quic/`

```
mqtt-quic/
├── docker/
│   ├── Dockerfile.edge        ← multi-stage, builds edge_mqtt.c
│   └── Dockerfile.device      ← multi-stage, builds device_mqtt.c
├── src/
│   ├── edge_mqtt.c            ← see spec in section 2.4
│   ├── device_mqtt.c          ← see spec in section 2.5
│   ├── cJSON.h                ← bundled cJSON (single-header from https://github.com/DaveGamble/cJSON)
│   └── cJSON.c                ← bundled cJSON source
├── nanomq.conf                ← see spec in section 2.3
└── docker-compose.yml         ← for manual testing only (not used by matrix runner)
```

### 2.3 NanoMQ broker config (`nanomq.conf`)

NanoMQ must listen on both TCP (1883) and QUIC (14567) so one broker image
serves both `mqtt-tcp-c` and `mqtt-quic` runs.

```
# nanomq.conf
# TCP listener (for mqtt-tcp-c)
listeners.tcp {
    bind = "0.0.0.0:1883"
}

# QUIC listener (for mqtt-quic)
listeners.quic {
    bind = "0.0.0.0:14567"
}
```

> **Verify**: Check the actual config key names against NanoMQ docs for the
> `nanomq/nanomq:latest-msquic` image version. The config syntax may differ
> between NanoMQ versions. Run `docker run nanomq/nanomq:latest-msquic cat /etc/nanomq.conf`
> to see the default and adapt.

### 2.4 `src/edge_mqtt.c` — specification

**Purpose**: Connects to NanoMQ, publishes command messages to each device at a
configured rate, receives ack messages, computes RTT per message, writes CSV.

**Env vars it must read**:

| Env var | Default | Description |
|---|---|---|
| `MQTT_BROKER_URL` | (required) | Full URL e.g. `mqtt-tcp://broker:1883` or `mqtt-quic://broker:14567` |
| `TARGET_DEVICES` | `device-1,device-2` | Comma-separated or integer N |
| `PAYLOAD_BYTES` | `100` | Size of dummy payload string |
| `INTERVAL_SEC` | `0.1` | Send interval (0.1 = 10 Hz, 0.2 = 5 Hz) |
| `RUN_DURATION` | `30` | Seconds to run before exiting |
| `OUTPUT_CSV` | `/app/results/out.csv` | Output file path |
| `START_DELAY_SEC` | `5.0` | Sleep before starting, allows netem injection |
| `MQTT_CLIENT_ID` | `edge-node` | MQTT client ID |

**Message format (edge → device)**:
```json
{"device_id": "device-1", "payload": "xxx...xxx", "ts_edge_ns": 123456789012}
```
- `ts_edge_ns`: monotonic nanoseconds via `clock_gettime(CLOCK_MONOTONIC, ...)`
- `payload`: string of `PAYLOAD_BYTES` ASCII `x` characters
- Topic: `campus/cmd/{device_id}`, QoS 1

**Message format (device ack → edge)**:
```json
{"device_id": "device-1", "status": "OK", "ts_edge_ns": 123456789012, "ts_device_ns": 999}
```
- Topic: `campus/ack/{device_id}`
- Edge subscribes to `campus/ack/#`

**RTT computation**:
```
recv_ts_ns = clock_gettime(CLOCK_MONOTONIC) at moment callback fires
rtt_ms = (recv_ts_ns - ts_edge_ns) / 1e6
```

**Internal data structure**:
Pre-allocate a flat array of records per device. Safe upper bound:
`max_records = (RUN_DURATION / INTERVAL_SEC + 10) * 1` per device.
Protect with a mutex since the receive callback fires on NanoSDK's internal thread.

**Control flow**:
1. Parse env vars
2. Sleep `START_DELAY_SEC`
3. Open NanoSDK socket, connect to `MQTT_BROKER_URL` with QoS 1
4. Subscribe to `campus/ack/#`
5. Register receive callback: on ack, lock mutex, record `(send_ts_ns_from_json, recv_ts_ns, rtt_ms)`
6. Main loop: for each device in round-robin, publish command, sleep `INTERVAL_SEC / N_devices`
   - Stop loop when `RUN_DURATION` elapsed
7. Sleep 1 second for in-flight acks
8. Disconnect
9. Write CSV: `device_id,send_ts_ns,recv_ts_ns,latency_ms`
10. Print summary (min, avg, p95, count per device) to stdout

**NanoSDK API to use** — check `demo/mqtt/` in the NanoSDK repo for exact function names:
- `nng_mqtt_quic_client_open()` for QUIC, `nng_mqtt_client_open()` for TCP
- `nng_dialer_create()` + `nng_dialer_start()`
- `nng_recv_aio()` or callback registration (check which pattern the demos use)
- `nng_mqtt_msg_alloc()`, `nng_mqtt_msg_set_publish_topic()`, `nng_mqtt_msg_set_publish_payload()`
- `nng_send()` / `nng_recv()` or async equivalents

> **Important**: The URL scheme for NanoSDK TCP is likely `mqtt-tcp://host:port`.
> Verify against NanoSDK demos — do not guess.

### 2.5 `src/device_mqtt.c` — specification

**Purpose**: Connects to NanoMQ, subscribes to its command topic, echoes ack.

**Env vars**:

| Env var | Default | Description |
|---|---|---|
| `DEVICE_ID` | `device-1` | Device identifier |
| `MQTT_BROKER_URL` | (required) | Same format as edge |
| `MQTT_CLIENT_ID` | `{DEVICE_ID}` | MQTT client ID |

**Control flow**:
1. Parse env vars
2. Open NanoSDK socket, connect to `MQTT_BROKER_URL`
3. Subscribe to `campus/cmd/{DEVICE_ID}` QoS 1
4. Register receive callback:
   - Parse JSON, extract `ts_edge_ns`
   - Record `ts_device_ns = clock_gettime(CLOCK_MONOTONIC)`
   - Publish ack JSON to `campus/ack/{DEVICE_ID}` QoS 1
5. Loop forever until SIGTERM

SIGTERM handling: catch signal, disconnect cleanly, exit 0.

### 2.6 `docker/Dockerfile.edge` and `Dockerfile.device`

Use a **multi-stage build** to keep the runtime image small and avoid shipping
build tools.

**Stage 1 — builder** (`ubuntu:22.04`):
```
apt-get install: cmake git build-essential libssl-dev pkg-config ninja-build
```
Steps:
1. Clone NanoSDK: `git clone --depth 1 https://github.com/nanomq/NanoSDK /nanosdk`
2. Build NanoSDK with QUIC:
   ```
   cd /nanosdk && mkdir build && cd build
   cmake -G Ninja -DNNG_ENABLE_QUIC=ON -DBUILD_SHARED_LIBS=ON ..
   ninja && ninja install
   ```
3. Copy `src/edge_mqtt.c` (or `device_mqtt.c`), `src/cJSON.c`, `src/cJSON.h` to `/app/`
4. Compile: `gcc -O2 -o /app/edge_mqtt /app/edge_mqtt.c /app/cJSON.c -lnng -lssl -lcrypto -lpthread`
   (adjust linker flags based on what NanoSDK cmake install provides)

**Stage 2 — runtime** (`ubuntu:22.04`):
```
apt-get install: libssl3 iproute2 ca-certificates
```
Copy compiled binary + required `.so` files from stage 1.
Set `CMD ["/app/edge_mqtt"]` (or `device_mqtt`).

> **msquic dependency**: NanoSDK QUIC depends on msquic. Check whether the NanoSDK
> CMake build downloads and bundles msquic automatically (`-DNNG_ENABLE_QUIC=ON` may
> fetch it via FetchContent) or if it needs to be installed separately. Inspect the
> NanoSDK `CMakeLists.txt` before writing the Dockerfile.

### 2.7 `nanomq.conf` mounting

In both `mqtt-tcp-c` and `mqtt-quic` compose specs (generated by run_matrix.py),
the NanoMQ broker service must mount `nanomq.conf`:
```yaml
mqtt-broker:
  image: nanomq/nanomq:latest-msquic
  ports:
    - "1883:1883"
    - "14567:14567/udp"    # QUIC uses UDP
  volumes:
    - {abs_path_to_mqtt-quic}/nanomq.conf:/etc/nanomq.conf
  networks:
    - campus-net
```

---

## Part 3 — `scripts/run_matrix.py` changes

### 3.1 New protocol cases in `generate_compose()`

Add three new `elif` blocks: `zenoh-quic`, `mqtt-tcp-c`, `mqtt-quic`.

**`zenoh-quic` block** — identical to `zenoh` block except:
- Router command: `["--listen", "quic/0.0.0.0:7447", "--no-multicast-scouting"]`
- Router ports: `["7447:7447/udp"]`
- Edge env: `ZENOH_ROUTER=quic/zenoh-router:7447`
- Device env: `ZENOH_ROUTER=quic/zenoh-router:7447`
- Build context: `os.path.join(abs_root_dir, "zenoh-quic")`

**`mqtt-tcp-c` block** — NanoMQ broker on TCP + C client:
- Broker service: `nanomq/nanomq:latest-msquic`, port `1883:1883`
- Broker volume mount: `nanomq.conf` from `mqtt-quic/` directory
- Edge env: `MQTT_BROKER_URL=mqtt-tcp://mqtt-broker:1883`
- Device cmd env: `MQTT_BROKER_URL=mqtt-tcp://mqtt-broker:1883`
- Build context: `os.path.join(abs_root_dir, "mqtt-quic")` for both edge and device

**`mqtt-quic` block** — NanoMQ broker on QUIC + C client:
- Broker service: same NanoMQ image, additionally expose `14567:14567/udp`
- Edge env: `MQTT_BROKER_URL=mqtt-quic://mqtt-broker:14567`
- Device env: `MQTT_BROKER_URL=mqtt-quic://mqtt-broker:14567`
- Build context: `os.path.join(abs_root_dir, "mqtt-quic")`

### 3.2 Edge service name consistency

The matrix runner identifies the edge container via `edge_service` to call `docker wait`.
For `mqtt-tcp-c` and `mqtt-quic`, the edge service name should be `edge-node` (same as
zenoh and mqtt). Confirm the `edge_service` variable logic at line ~295 in run_matrix.py
includes `mqtt-tcp-c` and `mqtt-quic` in the condition that maps to `edge-node`.

### 3.3 Output directory

`output_dir` uses `protocol` as a path component. The three new protocol names
(`zenoh-quic`, `mqtt-tcp-c`, `mqtt-quic`) will automatically create:
- `results/matrix/zenoh-quic/{profile}/`
- `results/matrix/mqtt-tcp-c/{profile}/`
- `results/matrix/mqtt-quic/{profile}/`

No changes needed to the path-building logic.

---

## Part 4 — Verification checklist (before full matrix run)

Run these manually before launching the 144-cell matrix for each new protocol.

### Zenoh-QUIC smoke test
```bash
cd zenoh-quic
docker compose up -d
# check router log
docker logs zenoh-router | grep -i "listen"   # must say quic/, not tcp/
# after 30s, check results
docker logs edge-node | grep RTT
docker compose down
```
Expected: RTT ~1ms on clean (same as zenoh/TCP). If it shows tcp:// in the router log,
the QUIC endpoint is not taking effect.

### MQTT-TCP-C smoke test
```bash
# From project root, run matrix with 1 cell only
python scripts/run_matrix.py \
  --protocols mqtt-tcp-c --profiles clean \
  --devices 1 --payloads 100 --rates 1 --duration 10
```
Expected: CSV appears at `results/matrix/mqtt-tcp-c/clean/N_1_pay_100_rate_1.csv`,
~3000 rows if rate=10, RTT comparable to existing mqtt/clean/N=1 minus the 46ms paho offset.

### MQTT-QUIC smoke test
```bash
python scripts/run_matrix.py \
  --protocols mqtt-quic --profiles clean \
  --devices 1 --payloads 100 --rates 1 --duration 10
```
Expected: same CSV format, RTT in same ballpark as mqtt-tcp-c/clean/N=1.
The interesting comparison is `degraded_5g` where QUIC's no-HOL-blocking should
prevent the broker queue collapse seen in the original paho/Mosquitto TCP results.

---

## Part 5 — What NOT to change

- `grpc/`, `zenoh/`, `mqtt/` directories: untouched
- Existing result CSVs: untouched
- `scripts/analyze_results.py`: update only after results are collected, not now

---

## Open risks to resolve during implementation

1. **NanoSDK URL scheme**: Verify the exact URL prefix for TCP (`mqtt-tcp://` vs `tcp://`)
   and QUIC (`mqtt-quic://`) from the NanoSDK `demo/mqtt/` source files before hardcoding.

2. **msquic bundling**: Check whether `-DNNG_ENABLE_QUIC=ON` in NanoSDK's CMake automatically
   fetches msquic via FetchContent or whether msquic must be installed separately in the
   Dockerfile. This determines how complex the build stage is.

3. **NanoMQ config key names**: Run `docker run nanomq/nanomq:latest-msquic cat /etc/nanomq.conf`
   to get the actual default config before writing `nanomq.conf`. The `listeners.quic` key name
   must match exactly.

4. **Zenoh QUIC in eclipse/zenoh:latest**: Confirm `--listen quic/...` is valid for the
   current `eclipse/zenoh:latest` image by running:
   `docker run eclipse/zenoh:latest --help | grep -i quic`
   If the image does not have QUIC compiled in, try `eclipse/zenoh:0.7.2-rc` or a later
   pinned version that explicitly lists QUIC support.

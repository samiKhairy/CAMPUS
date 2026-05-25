# PROJECT CAMPUS — Complete Documentation

> **For someone who has never worked with 5G before.**
> This document explains everything from scratch: what the project is, why it exists, how 5G works in simple terms, and the purpose and configuration of every single file in the workspace.

---

## Table of Contents

1. [What is this project?](#1-what-is-this-project)
2. [How does 5G work? (From Zero)](#2-how-does-5g-work-from-zero)
3. [Project Architecture Overview](#3-project-architecture-overview)
4. [Directory Structure](#4-directory-structure)
5. [Module 1 — 5G Testbed (`5g-testbed/`)](#5-module-1--5g-testbed-5g-testbed)
   - [docker-compose.yml](#docker-composeyml-the-master-orchestration-file)
   - [open5gs/ — 5G Core Configurations](#open5gs--5g-core-configurations)
   - [ueransim/ — Radio & Device Configurations](#ueransim--radio--device-configurations)
   - [app/ — Application Code & Dockerfiles](#app--application-code--dockerfiles)
   - [sa-deploy.yaml — Alternative Production Deploy](#sa-deployyaml--alternative-production-deploy)
6. [Module 2 — gRPC Standalone Prototype (`gRPC/`)](#6-module-2--grpc-standalone-prototype-grpc)
7. [Module 3 — Zenoh Standalone Prototype (`zenoh/`)](#7-module-3--zenoh-standalone-prototype-zenoh)
8. [Key Identities & Credentials](#8-key-identities--credentials)
9. [How to Start Everything](#9-how-to-start-everything)
10. [Troubleshooting & Known Issues](#10-troubleshooting--known-issues)
11. [Glossary](#11-glossary)

---

## 1. What is this project?

This workspace is a **research testbed** for a European research project called **CAMPUS** (Cooperative Aggregation & Mapping for Perception in Ubiquitous Sensing), part of **EU Horizon Europe** under a project called **ENVELOPE**.

### The real-world problem it solves

In smart cities of the future:
- **Vehicles (cars, vans)** drive around with cameras and sensors mounted on them. They detect other cars, pedestrians, and obstacles.
- **Edge servers** (small powerful computers installed at the roadside or a traffic light) collect this sensor data from multiple cars, combine it all together, and create a live HD map of what's happening.
- The edge server then **pushes relevant updates back to the vehicles** so each car knows about dangers or other vehicles it can't see itself.

This communication (vehicle ↔ edge server) must be **very fast and reliable** because at 100 km/h a car moves 28 meters every second.

### What this testbed does

Instead of using real cars and roadside servers, this project **simulates that entire chain on your laptop using Docker containers**. It tests three things:

1. **Can we use 5G as the network layer?** → The `5g-testbed/` module answers this.
2. **Which communication protocol is fastest?** → Comparing **gRPC** (`gRPC/` module) vs **Zenoh** (`zenoh/` module).
3. **How much latency (delay) is there?** → Both modules measure the round-trip time (RTT) of messages between devices and the edge server.

---

## 2. How does 5G work? (From Zero)

Think of 5G like a very advanced version of the mobile network your phone uses — but designed for machines, factories, and vehicles that need extremely low latency.

### The players in a 5G network

```
[Your Phone / Vehicle / Device]
          |
     (Radio signal)
          |
    [gNodeB — The Tower]
          |
     (Fiber / IP)
          |
   [5G Core Network]
          |
    (Internet / MEC)
          |
   [Application Server]
```

| Part | Real World | In This Project |
|------|-----------|-----------------|
| **SIM Card** | The card in your phone that identifies you | `ue.yaml` — contains IMSI, keys |
| **Phone / Device (UE)** | Your mobile phone or vehicle OBU | `vehicle-ue` container running UERANSIM |
| **gNodeB (gNB)** | The 5G tower/base station | `gnb-simulator` container running UERANSIM |
| **AMF** | Traffic cop — decides who can join the network | `open5gs-amf` container |
| **UPF** | The actual data packet router (like a router at home) | `open5gs-upf` container |
| **SMF** | Assigns IP addresses and sets up data sessions | `open5gs-smf` container |
| **NRF** | Yellow pages — all services register here | `open5gs-nrf` container |
| **UDM/UDR** | Subscriber database (stores SIM info) | `open5gs-udm` / `open5gs-udr` containers |
| **AUSF** | Authentication center — verifies it's really your SIM | `open5gs-ausf` container |
| **PCF** | Policy manager — sets QoS, data limits | `open5gs-pcf` container |
| **BSF** | Session registry — helps PCF find active sessions | `open5gs-bsf` container |
| **SCP** | Internal message router between core functions | `open5gs-scp` container |

### What happens when a device connects (simplified)

1. **Device turns on** → sends a registration request over the radio to the gNB.
2. **gNB forwards** the registration to the AMF (the "control plane").
3. **AMF asks AUSF/UDM** — "Is this SIM card valid? Do we recognize this IMSI?"
4. **AUSF runs crypto** to prove the SIM has the correct secret key (like a password).
5. **AMF approves** registration. Device is now "registered" on the network.
6. **Device requests a data session** (PDU Session) — "I want to send/receive data".
7. **SMF responds**, allocates an IP address (e.g., `10.45.x.x`), and creates a GTP tunnel between the gNB and UPF.
8. **UPF creates a virtual network interface** (`uesimtun0`) on the device side — now all data goes through the 5G network.
9. **Device can now talk to the application** (the edge server) through the tunnel.

### Why is 5G special?

| Feature | 4G LTE | 5G NR |
|---------|--------|-------|
| Latency | ~20-50ms | ~1-5ms |
| Speed | ~100 Mbps | ~1-10 Gbps |
| Architecture | Monolithic core | Microservices (each function is separate) |
| Slicing | No | Yes — dedicate a slice for a specific service |
| Key interface | NG-RAN | gNB ↔ AMF (N2), gNB ↔ UPF (N3) |

---

## 3. Project Architecture Overview

```
d:\project campus\
│
├── 5g-testbed/           ← Full 5G simulation (the main lab)
│   ├── open5gs/          ← 5G Core config files (YAML)
│   ├── ueransim/         ← Radio (gNB) and device (UE) config files
│   └── app/              ← Python gRPC app that runs INSIDE the 5G network
│
├── gRPC/                 ← Standalone gRPC experiment (no 5G, just Docker bridge)
│
└── zenoh/                ← Standalone Zenoh experiment (no 5G, just Docker bridge)
```

### How the three modules relate

```
        ┌──────────────────────────────────────────────┐
        │           5g-testbed (Full Stack)             │
        │                                               │
        │  [vehicle-ue] ──5G tunnel──> [edge-server]   │
        │        ↕ gRPC                      ↕         │
        │  (uses gRPC from app/ folder)   gRPC          │
        └──────────────────────────────────────────────┘

        ┌──────────────────────────────────────────────┐
        │        gRPC/ (Protocol Benchmark Only)        │
        │  [device-1] ──gRPC──> [grpc-server]          │
        │  [device-2] ──gRPC──> [grpc-server]          │
        │  (no 5G, measures pure gRPC performance)      │
        └──────────────────────────────────────────────┘

        ┌──────────────────────────────────────────────┐
        │        zenoh/ (Protocol Benchmark Only)       │
        │  [device-1] ─pub/sub─> [zenoh-router]        │
        │  [edge-node] <─────── [zenoh-router]         │
        │  (no 5G, measures pure Zenoh performance)     │
        └──────────────────────────────────────────────┘
```

---

## 4. Directory Structure

```
d:\project campus\
│
├── PROJECT_DOCS.md              ← This file
├── Open5GS_CUPS-01.pdf          ← Reference whitepaper on Open5GS architecture
│
├── 5g-testbed/
│   ├── docker-compose.yml       ← Launches ALL 14 containers together
│   ├── sa-deploy.yaml           ← Alternative deploy (different open5gs image)
│   ├── open5gs/
│   │   ├── amf.yaml             ← AMF configuration
│   │   ├── nrf.yaml             ← NRF configuration
│   │   ├── smf.yaml             ← SMF configuration
│   │   ├── upf.yaml             ← UPF configuration
│   │   ├── pcf.yaml             ← PCF configuration
│   │   ├── udr.yaml             ← UDR configuration
│   │   └── fix-types.js         ← MongoDB repair script for subscriber data
│   ├── ueransim/
│   │   ├── gnb.yaml             ← gNodeB (base station) configuration
│   │   └── ue.yaml              ← UE (device/SIM card) configuration
│   └── app/
│       ├── Dockerfile.ue        ← Container recipe for vehicle-ue
│       ├── Dockerfile.server    ← Container recipe for edge-server
│       ├── client_grpc.py       ← gRPC client running inside the UE
│       ├── server_grpc.py       ← gRPC server running at the edge
│       ├── device_pb2.py        ← Auto-generated protobuf message classes
│       └── device_pb2_grpc.py   ← Auto-generated gRPC stub classes
│
├── gRPC/
│   ├── README.md                ← How to run the gRPC prototype
│   ├── docker-compose.yml       ← Launches grpc-server + 2 device clients
│   ├── server.py                ← Edge server (standalone, no 5G)
│   ├── client.py                ← Device client (standalone, no 5G)
│   ├── device_pb2.py            ← Protobuf message classes
│   ├── device_pb2_grpc.py       ← gRPC stub classes
│   ├── exp_baseline_grpc.ps1    ← Windows experiment automation script
│   ├── exp_baseline_grpc.sh     ← Linux experiment automation script
│   ├── proto/
│   │   └── device.proto         ← Service contract definition
│   ├── docker/
│   │   ├── Dockerfile.server    ← Server container recipe
│   │   └── Dockerfile.client    ← Client container recipe
│   ├── scripts/                 ← Helper scripts
│   └── results/                 ← Generated CSV files go here
│
└── zenoh/
    ├── README.md                ← How to run the Zenoh prototype
    ├── docker-compose.yml       ← Launches zenoh-router + edge-node + devices
    ├── exp_baseline_zenoh.ps1   ← Windows experiment automation script
    ├── exp_baseline_zenoh.sh    ← Linux experiment automation script
    ├── src/
    │   ├── edge_zenoh.py        ← Zenoh edge controller
    │   └── device_zenoh.py      ← Zenoh device simulator
    ├── docker/
    │   ├── Dockerfile.edge      ← Edge node container recipe
    │   └── Dockerfile.device    ← Device container recipe
    ├── scripts/                 ← Helper scripts (local device launcher)
    ├── logs/                    ← Log output directory
    └── results/                 ← Generated CSV files go here
```

---

## 5. Module 1 — 5G Testbed (`5g-testbed/`)

This is the **main experiment**. It runs a complete simulated 5G network inside Docker and runs the vehicle↔edge application ON TOP of that 5G network.

### Container Startup Order

The containers start in this strict dependency order to avoid crashes:

```
mongodb  ──────────────────────────────────────┐
   │                                            │
   ├──> open5gs-nrf                             │
   │        │                                   │
   │        └──> open5gs-scp                    │
   │                  │                         │
   │            ┌─────┴──────────────────┐      │
   │            │                        │      │
   │       open5gs-udr              open5gs-bsf  │
   │       open5gs-udm              open5gs-ausf │
   │            │                        │      │
   │       open5gs-pcf ◄────────────────┘      │
   │            │                               │
   ├────> open5gs-amf ◄── (all above ready)    │
   │            │                               │
   ├────> open5gs-upf                           │
   │            │                               │
   ├────> open5gs-smf ◄── (amf + upf ready)    │
   │                                            │
   └────> open5gs-webui                         │
                                                │
         gnb-simulator ◄── (amf ready)          │
              │                                 │
         vehicle-ue ◄── (gnb ready)             │
              │                                 │
         edge-server ◄── (upf ready)            │
```

---

### `docker-compose.yml` — The Master Orchestration File

**Path:** `d:\project campus\5g-testbed\docker-compose.yml`

This file describes **14 services** (containers) and how they connect. Below is an explanation of every service:

#### Service 1: `mongodb`

```yaml
image: mongo:4.4.10
volumes:
  - mongodb-data:/data/db
healthcheck:
  test: ["CMD", "mongo", "--eval", "db.adminCommand('ping')"]
  interval: 5s
```

- **What it is:** The database. Open5GS stores subscriber (SIM card) profiles here.
- **Why health check:** All 5G core services that depend on the DB use `condition: service_healthy` — they will NOT start until MongoDB successfully passes this ping check. This prevents the "#1 crash cause": starting before the DB is ready.
- **Volume:** `mongodb-data` persists data across container restarts.

#### Service 2: `open5gs-nrf` — Network Repository Function

```yaml
image: gradiant/open5gs:2.7.2
command: ["/opt/open5gs/bin/open5gs-nrfd", "-c", "/etc/open5gs/nrf.yaml"]
volumes:
  - ./open5gs/nrf.yaml:/etc/open5gs/nrf.yaml
```

- **What it is:** The "yellow pages" or service registry of the 5G core. Every other NF (AMF, SMF, PCF, etc.) **registers itself here** when it starts up, and **discovers other services** through NRF.
- **Analogy:** Like a DNS server, but for internal 5G microservices.

#### Service 2b: `open5gs-scp` — Service Communication Proxy

```yaml
command: ["/opt/open5gs/bin/open5gs-scpd"]
networks: { 5g-net: { aliases: [scp] } }
```

- **What it is:** An internal HTTP message router between NFs. Instead of NFs talking directly to each other, they can route through the SCP (the "indirect" communication model in 5G Release 16+).
- **Why it's needed:** Some NFs (PCF, UDR) are configured to use `http://scp:7777` for routing. Without it, they crash trying to send SBI messages.

#### Service 2c: `open5gs-udr` — Unified Data Repository

```yaml
command: ["/opt/open5gs/bin/open5gs-udrd"]
environment:
  - DB_URI=mongodb://mongodb:27017/open5gs
```

- **What it is:** The raw database interface. Stores subscriber profiles (IMSI, authentication keys, subscribed services) in MongoDB.
- **Analogy:** The actual filing cabinet where all SIM card data is kept.

#### Service 2d: `open5gs-udm` — Unified Data Management

```yaml
command: ["/opt/open5gs/bin/open5gs-udmd"]
```

- **What it is:** The front-desk interface to subscriber data. Other NFs (like AMF, AUSF) talk to UDM, and UDM internally talks to UDR.
- **Analogy:** The receptionist who looks up your file in the filing cabinet (UDR) when someone asks about you.

#### Service 2e: `open5gs-ausf` — Authentication Server Function

```yaml
command: ["/opt/open5gs/bin/open5gs-ausfd"]
```

- **What it is:** Performs the cryptographic challenge-response authentication. When a UE tries to register, AUSF fetches the secret key from UDM and proves the UE is genuine.
- **Analogy:** The security guard who checks your ID (SIM key) against the database.

#### Service 2f: `open5gs-pcf` — Policy Control Function

```yaml
command: ["/opt/open5gs/bin/open5gs-pcfd"]
depends_on:
  - open5gs-bsf   # CRITICAL: PCF needs BSF to locate active sessions
```

- **What it is:** The network policy manager. Controls QoS (quality of service), bandwidth limits, network slices for each device.
- **Critical dependency:** PCF **must start after BSF**. If BSF is missing, PCF tries to register its session binding location and fails with `No http.location`, causing a chain of 400 HTTP errors.

#### Service 2g: `open5gs-bsf` — Binding Support Function

```yaml
command: ["/opt/open5gs/bin/open5gs-bsfd"]
```

- **What it is:** A registry that tracks which PCF instance is managing which PDU session. When multiple PCF instances exist, BSF helps route policy requests to the correct one.
- **Why it's critical here:** Even with a single PCF instance, Open5GS 2.7 requires BSF to be running. Without it, PCF cannot register its binding and crashes with HTTP 400.

#### Service 3: `open5gs-amf` — Access and Mobility Management Function

```yaml
command: ["/opt/open5gs/bin/open5gs-amfd", "-c", "/etc/open5gs/amf.yaml"]
volumes:
  - ./open5gs/amf.yaml:/etc/open5gs/amf.yaml
```

- **What it is:** The **control plane entry point**. Every UE registration, authentication, handover, and deregistration goes through AMF.
- **Interfaces:**
  - **N2 (NGAP/SCTP port 38412):** gNB connects to AMF here.
  - **SBI (HTTP port 7777):** AMF talks to other NFs (AUSF, UDM, SMF, PCF) here.
- **Analogy:** The main reception desk. Every new visitor (UE) must check in here first.

#### Service 4: `open5gs-smf` — Session Management Function

```yaml
command: ["/opt/open5gs/bin/open5gs-smfd", "-c", "/etc/open5gs/smf.yaml"]
depends_on:
  - open5gs-amf   # must exist before session creation
  - open5gs-upf   # must exist to receive PFCP rules
```

- **What it is:** Creates and manages data sessions (PDU Sessions). When a UE wants internet access, AMF asks SMF to set it up. SMF:
  1. Allocates an IP address from the `10.45.0.0/16` subnet.
  2. Sends PFCP rules to UPF telling it what to do with the packets.
  3. Creates the GTP tunnel path: UE ↔ gNB ↔ UPF.
- **Analogy:** The plumber who lays the pipes (tunnels) for data to flow through.

#### Service 5: `open5gs-upf` — User Plane Function

```yaml
user: root
cap_add: [NET_ADMIN]
privileged: true
devices:
  - "/dev/net/tun:/dev/net/tun"
```

- **What it is:** The **actual data packet router**. ALL user data (your app traffic) passes through UPF. It creates a GTP tunnel endpoint and applies packet forwarding rules received from SMF.
- **Why privileged:** UPF needs to create TUN/TAP network interfaces inside the container to route packets. This requires kernel network admin privileges.
- **IP Pool:** Assigns IPs from `10.45.0.0/16` to connected devices.
- **Analogy:** The highway on which all data actually travels.

#### Service 6: `open5gs-webui`

```yaml
image: gradiant/open5gs-webui:2.7.2
ports:
  - "3000:9999"
environment:
  - DB_URI=mongodb://mongodb:27017/open5gs
```

- **What it is:** A web-based admin portal to manage subscribers (SIM cards).
- **Access:** `http://localhost:3000`
- **Default credentials:** `admin` / `1423` (as per Open5GS defaults).
- **Usage:** Add subscribers (IMSI + key + OP) here before a UE can register.

#### Service 7: `gnb-simulator` — Simulated gNodeB

```yaml
image: louisroyer/ueransim-gnb:latest
command: ["/usr/bin/nr-gnb", "-c", "/etc/ueransim/gnb.yaml", "-l", "trace"]
volumes:
  - ./ueransim/gnb.yaml:/etc/ueransim/gnb.yaml
depends_on:
  - open5gs-amf
```

- **What it is:** A software simulation of a 5G base station (radio tower), using the **UERANSIM** open-source tool.
- **What it does:** Establishes the N2 (NGAP) connection to AMF and the N3 (GTP) connection to UPF. Acts as the radio relay for the simulated UE.
- **Analogy:** The cell tower that the "phone" (vehicle-ue) connects to.

#### Service 8: `vehicle-ue` — Simulated Vehicle / User Equipment

```yaml
build:
  context: ./app
  dockerfile: Dockerfile.ue
cap_add: [NET_ADMIN]
privileged: true
devices:
  - "/dev/net/tun:/dev/net/tun"
command: >
  bash -c "/usr/bin/nr-ue -c /etc/ueransim/ue.yaml &
  echo 'Waiting for uesimtun0...' &&
  for i in {1..20}; do if ip link show uesimtun0 >/dev/null 2>&1; then break; fi; sleep 1; done &&
  python3 /app/client_grpc.py --bind-interface uesimtun0"
environment:
  - PYTHONUNBUFFERED=1
```

- **What it is:** The simulated vehicle. It runs two processes simultaneously:
  1. **`nr-ue`** — UERANSIM's UE software that handles the 5G registration protocol and creates `uesimtun0` (the 5G tunnel interface).
  2. **`client_grpc.py`** — The Python application that runs INSIDE the 5G network, sending data to the edge server through the tunnel.
- **The startup sequence in the command:**
  1. Start `nr-ue` in the background (`&`)
  2. Loop (up to 20 seconds) waiting for `uesimtun0` to appear — this is the signal that 5G registration succeeded.
  3. Once the tunnel is ready, launch the gRPC client, binding to `uesimtun0` so ALL traffic goes through the 5G data plane.
- **Why privileged:** Same as UPF — needs TUN device access to create `uesimtun0`.
- **`PYTHONUNBUFFERED=1`:** Makes Python print logs immediately (without buffering) so `docker logs vehicle-ue` shows real-time output.

#### Service 9: `edge-server` — Campus Edge Application Node

```yaml
build:
  context: ./app
  dockerfile: Dockerfile.server
environment:
  - PYTHONUNBUFFERED=1
depends_on:
  - open5gs-upf
```

- **What it is:** The simulated roadside edge server. Runs `server_grpc.py`.
- **What it does:** Waits for device connections, sends periodic commands (payloads) to connected vehicles, receives acknowledgments, and measures round-trip latency.
- **Connection to 5G:** It's on the same Docker bridge (`5g-net`), so UPF can route packets from the UE's `10.45.x.x` address to the edge server's container IP.

---

### `open5gs/` — 5G Core Configurations

#### `nrf.yaml` — Network Repository Function Config

```yaml
global:
  max:
    ue: 1024         # Max simultaneous UEs this core supports

nrf:
  serving:
    - plmn_id:
        mcc: "001"   # Mobile Country Code — 001 = test/private network
        mnc: "01"    # Mobile Network Code — 01
  sbi:
    server:
      - dev: eth0    # Listen on the container's eth0 interface
        port: 7777   # Standard Open5GS SBI port
```

- **MCC 001 / MNC 01** = The PLMN identity (operator identity) of this private network. Must match identically across ALL config files and in the UE's `ue.yaml`.
- **Port 7777** = The internal HTTP (SBI) port all Open5GS components use to talk to each other.

#### `amf.yaml` — Access and Mobility Management Function Config

```yaml
amf:
  sbi:
    server:
      - dev: eth0
        port: 7777
    client:
      nrf:
        - uri: http://open5gs-nrf:7777   # How AMF finds the NRF
  ngap:
    server:
      - dev: eth0
        port: 38412   # SCTP port for gNB connections (N2 interface)
  guami:
    - plmn_id:
        mcc: "001"
        mnc: "01"
      amf_id:
        region: 2
        set: 1
  tai:
    - plmn_id:
        mcc: "001"
        mnc: "01"
      tac: 1           # Tracking Area Code — must match gnb.yaml
  plmn_support:
    - plmn_id:
        mcc: "001"
        mnc: "01"
      s_nssai:
        - sst: 1
          sd: 000001   # Network slice: SST=1 (eMBB), SD=0x000001
```

- **`ngap.port: 38412`** — This is where gNB connects. gNB config (`gnb.yaml`) must point to `open5gs-amf:38412`.
- **TAC (Tracking Area Code) = 1** — Must be identical in both `amf.yaml` and `gnb.yaml`.
- **Network Slice (S-NSSAI):** SST=1, SD=0x000001. Must match in `gnb.yaml` and `ue.yaml`.
- **`logger.level: debug`** — AMF logs are verbose, helpful for debugging registration issues.

#### `smf.yaml` — Session Management Function Config

```yaml
smf:
  sbi:
    client:
      nrf:
        - uri: http://open5gs-nrf:7777
  pfcp:
    server:
      - dev: eth0
    client:
      upf:
        - address: open5gs-upf   # SMF sends PFCP rules to this UPF
  session:
    - subnet: 10.45.0.0/16       # IP pool for UEs
      dnn: internet               # Data Network Name (APN)
  dns:
    - 8.8.8.8                    # DNS assigned to UE
    - 8.8.4.4
```

- **PFCP (Packet Forwarding Control Protocol):** The protocol SMF uses to program UPF with packet-routing rules.
- **`subnet: 10.45.0.0/16`** — UEs get IPs like `10.45.0.2`, `10.45.0.3`, etc.
- **`dnn: internet`** — The "APN" (Access Point Name). Must match `ue.yaml`'s `sessions[0].apn`.

#### `upf.yaml` — User Plane Function Config

```yaml
upf:
  pfcp:
    - address: open5gs-upf   # UPF listens for PFCP from SMF
  gtpu:
    - address: open5gs-upf   # GTP-U tunnel endpoint for gNB traffic
  pdn:
    - address: 10.45.0.1/16  # Gateway IP for the UE subnet
```

- **GTP-U (GPRS Tunnelling Protocol - User Plane):** The protocol that encapsulates UE packets inside a tunnel between gNB and UPF.
- **`10.45.0.1`** — The default gateway that UEs see for the data network.

#### `pcf.yaml` — Policy Control Function Config

```yaml
pcf:
  sbi:
    server:
      - dev: eth0
        port: 7777
    client:
      scp:
        - uri: http://scp:7777   # Routes SBI messages through SCP
```

- PCF uses the **indirect communication** model — routes through the SCP rather than contacting other NFs directly.

#### `udr.yaml` — Unified Data Repository Config

```yaml
udr:
  sbi:
    server:
      - dev: eth0
        port: 7777
    client:
      scp:
        - uri: http://scp:7777
```

- Same pattern as PCF — routes through SCP.

#### `fix-types.js` — MongoDB Subscriber Data Repair Script

```javascript
db.subscribers.find({imsi: "001010000000001"}).forEach(function(sub) {
  sub.subscribed_rau_tau_timer = NumberInt(sub.subscribed_rau_tau_timer);
  sub.subscriber_status = NumberInt(sub.subscriber_status);
  // ... fixes all integer fields
  db.subscribers.save(sub);
});
```

- **Problem it solves:** When subscriber data is inserted via the WebUI or imported, MongoDB sometimes stores integer fields as `Double` (floating-point) instead of `Int32`. Open5GS strict type checking then rejects the data, causing authentication failures.
- **How to run:**
  ```bash
  docker exec -it mongodb mongo open5gs fix-types.js
  ```
- **When to use:** If you see authentication errors like `AUTHENTICATION_FAILURE` after adding a subscriber, run this script.

---

### `ueransim/` — Radio & Device Configurations

#### `gnb.yaml` — gNodeB (Base Station) Configuration

```yaml
mcc: '001'           # Mobile Country Code — must match AMF
mnc: '01'            # Mobile Network Code — must match AMF
tac: 1               # Tracking Area Code — must match AMF
nci: '0x00000001'    # NR Cell Identity (unique cell ID)
gNodeBId: '0x000102' # gNodeB unique identifier

# Network binding — uses container hostname (Docker DNS)
linkIp: gnb-simulator  # Internal link IP (binds to container's IP)
ngapIp: gnb-simulator  # IP for N2 interface (to AMF)
gtpIp: gnb-simulator   # IP for N3/GTP-U interface (to UPF)

amfConfigs:
  - address: open5gs-amf   # AMF container name (Docker DNS resolves this)
    port: 38412             # AMF's NGAP SCTP port

slices:
  - sst: 1
    sd: 0x000001   # Must match AMF plmn_support and UE sessions

customFreqRx: 869000   # Simulated radio frequency (869 MHz)
customFreqTx: 869000
```

- **Why hostnames instead of IPs:** Using container names (`gnb-simulator`, `open5gs-amf`) means Docker's internal DNS resolves them automatically, regardless of what IP Docker assigns. This is more robust than hardcoding IPs.
- **Slices must match across:** `amf.yaml` → `gnb.yaml` → `ue.yaml` (all three must agree on SST=1, SD=0x000001).

#### `ue.yaml` — UE (SIM Card + Device) Configuration

```yaml
# === SIM Card Identity ===
mcc: '001'                        # Must match network
mnc: '01'                         # Must match network
supi: 'imsi-001010000000001'      # IMSI — unique device identifier
key:  '465B5CE8B199B49FAA5F0A2EE238A6BC'   # Secret key K (128-bit)
op:   'E8ED289DEBA952E4285B44E71103E524'   # Operator code (OPc format)
opType: 'OPC'                     # Using OPC (computed from OP+K)
amf: '8000'                       # Authentication Management Field

# === Radio Connection ===
gnbSearchList:
  - gnb-simulator    # Search for gNB with this hostname

# === Security Algorithms ===
integrity:
  IA1: true   # NIA1 (SNOW 3G)
  IA2: true   # NIA2 (AES-128-EIA2) — preferred
  IA3: true   # NIA3 (ZUC)
ciphering:
  EA1: true   # NEA1 (SNOW 3G)
  EA2: true   # NEA2 (AES-128-EEA2) — preferred
  EA3: true   # NEA3 (ZUC)

# === Network Slice ===
configured-nssai:
  - sst: 1
    sd: 0x000001   # Same slice as AMF and gNB

# === PDU Session (Data Connection) ===
sessions:
  - type: 'IPv4'
    apn: 'internet'    # Must match SMF's dnn
    slice:
      sst: 1
      sd: 0x000001
```

- **IMSI `001010000000001`** = MCC(001) + MNC(01) + MSIN(0000000001). This must be registered in MongoDB via the WebUI.
- **Key and OP:** These must exactly match what's stored in the Open5GS subscriber database. The AUSF uses these to do AKA (Authentication and Key Agreement).
- **OPc vs OP:** The WebUI stores OPc (which is OP XOR-encrypted with K). The `opType: 'OPC'` tells UERANSIM the `op` field is already in OPc form.

---

### `app/` — Application Code & Dockerfiles

#### `Dockerfile.ue` — Vehicle UE Container Recipe

```dockerfile
FROM louisroyer/ueransim-ue:latest   # Base: pre-built UERANSIM UE image

RUN apt-get update && \
    apt-get install -y python3 python3-pip && \
    pip3 install --break-system-packages grpcio protobuf && \
    apt-get clean
```

- **Base image:** `louisroyer/ueransim-ue:latest` — contains the compiled `nr-ue` binary.
- **Added:** Python 3 + gRPC/protobuf libraries so `client_grpc.py` can run inside the same container.

#### `Dockerfile.server` — Edge Server Container Recipe

```dockerfile
FROM python:3.10-slim
WORKDIR /app
RUN pip install --no-cache-dir grpcio protobuf
COPY server_grpc.py .
COPY device_pb2.py .
COPY device_pb2_grpc.py .
EXPOSE 50051
CMD ["python", "server_grpc.py"]
```

- Minimal Python container. Copies the three Python files and runs the server on port 50051.

#### `client_grpc.py` — gRPC Client (runs inside vehicle-ue)

**Key behaviors:**

1. **Interface binding:** Takes `--bind-interface uesimtun0` argument. Uses `fcntl.ioctl(SIOCGIFADDR)` to get the IP of `uesimtun0` and binds the gRPC socket to it via `grpc.local_ip_to_bind`. This **forces ALL gRPC traffic through the 5G tunnel**.
2. **Registration (Unary RPC):** Sends `DeviceInfo(device_id="device-1")` to the edge server. Server confirms with `RegisterAck(success=True)`.
3. **Bidirectional stream:** Opens `CommandStream` using an `AckIterator` (a queue-backed `__next__` generator):
   - Sends an initial `CommandAck(status="Connected")` handshake.
   - Receives `Command` messages from the server.
   - For each command, immediately returns a `CommandAck` containing the original `ts_edge_ns` timestamp.
4. **RTT Measurement:** The timestamp round-trip lets the server calculate how long the message took to travel Device→Edge→Device.

#### `server_grpc.py` — gRPC Edge Server

**Key behaviors:**

1. **Listens on port 50051** (`[::]` = all interfaces).
2. **`Register()`:** Accepts device registrations, logs them.
3. **`CommandStream()`:** Bidirectional streaming handler:
   - Spawns a background thread (`consume_acks`) to read incoming ACKs from the client.
   - Main loop reads from a `command_queue` and `yield`s commands to the client.
   - Calculates RTT: `RTT = time_now_ns - ack.ts_edge_ns`.
4. **Sending loop:** Main thread iterates over `TARGET_DEVICES` every `INTERVAL_SEC` seconds, sending a payload of `PAYLOAD_BYTES` bytes to each connected device.
5. **Results:** On shutdown, writes `results/results_5g_grpc_TIMESTAMP.csv` with columns: `device_id, send_ts_ns, recv_ts_ns, latency_ms`.

#### `device_pb2.py` and `device_pb2_grpc.py`

These files are **auto-generated** from `gRPC/proto/device.proto` using:
```bash
python -m grpc_tools.protoc -I=proto --python_out=. --grpc_python_out=. proto/device.proto
```

They should **never be edited manually**. They define the Python classes for all protobuf messages (`DeviceInfo`, `RegisterAck`, `Command`, `CommandAck`) and the gRPC service stubs.

---

### `sa-deploy.yaml` — Alternative Production Deploy

**Path:** `d:\project campus\5g-testbed\sa-deploy.yaml`

This is an **alternative docker-compose** file based on a different Open5GS Docker image (`docker_open5gs` instead of `gradiant/open5gs`). It uses:
- **Environment variables** from a `.env` file for IP addresses (`${AMF_IP}`, `${NRF_IP}`, etc.)
- **Static IP assignment** via `ipam.config` (each container gets a fixed IP)
- **Additional monitoring:** Includes a `metrics` (Prometheus) container and a `grafana` container for dashboards.
- **`nssf`:** Network Slice Selection Function — for more advanced multi-slice scenarios.

> **Note:** This file is not the one being used in the active lab. The working deployment is `docker-compose.yml`. This file is a reference for a more production-like setup.

---

## 6. Module 2 — gRPC Standalone Prototype (`gRPC/`)

This module is a **simpler, self-contained version** of the gRPC experiment — NO 5G involved. It runs on a plain Docker bridge network to measure pure gRPC protocol performance.

### Purpose

To provide a **baseline measurement**: "What is the gRPC latency with zero 5G overhead?" Later, compare these numbers against `5g-testbed/` results to understand the 5G contribution to latency.

### `proto/device.proto` — Service Contract

```protobuf
syntax = "proto3";
package campus;

message DeviceInfo  { string device_id = 1; }
message RegisterAck { bool success = 1; }

message Command {
  string device_id = 1;
  string payload = 2;    // The actual data payload (N bytes)
  int64 ts_edge_ns = 3;  // Send timestamp in nanoseconds
}

message CommandAck {
  string device_id = 1;
  string status = 2;
  int64 ts_device_ns = 3;  // Receive timestamp on device
  int64 ts_edge_ns = 4;    // Echo of original send timestamp
}

service DeviceService {
  rpc Register(DeviceInfo) returns (RegisterAck);
  rpc CommandStream(stream CommandAck) returns (stream Command);
}
```

- **`Register`:** Simple unary call for device identification.
- **`CommandStream`:** A bidirectional streaming RPC. The client sends a stream of `CommandAck` messages; the server sends a stream of `Command` messages. Both streams are open simultaneously.

### `server.py` — Standalone Edge Server

Identical logic to `5g-testbed/app/server_grpc.py` but without the 5G-specific parts. Runs a full gRPC server with:
- Configurable number of target devices
- Configurable payload size, send interval, run duration
- CSV output with per-message latency records
- Statistical summary (min/avg/p95) on exit

**Configuration via environment or CLI:**
| Env Var | Default | Meaning |
|---------|---------|---------|
| `GRPC_PORT` | `50051` | Port to listen on |
| `TARGET_DEVICES` | `device-1` | Which devices receive commands |
| `PAYLOAD_BYTES` | `100` | Bytes in each command payload |
| `INTERVAL_SEC` | `1.0` | Seconds between sends |
| `RUN_DURATION` | `0.0` | Seconds to run (0 = forever) |
| `MAX_MESSAGES` | `0` | Max messages per device (0 = unlimited) |

### `client.py` — Standalone Device Client

Similar to `5g-testbed/app/client_grpc.py` but simpler (no interface binding). Used by the `device-1` and `device-2` containers.

### `docker-compose.yml` — gRPC Experiment Compose

```yaml
services:
  grpc-server:          # Edge node
    ports: ["50051:50051"]
    environment:
      - TARGET_DEVICES=device-1,device-2
      - RUN_DURATION=10.0     # Runs for 10 seconds then saves results
    volumes:
      - ./results:/app/results  # CSV files synced to host

  device-1:             # Simulated vehicle 1
    command: ["python", "client.py", "device-1", "--server", "grpc-server:50051"]

  device-2:             # Simulated vehicle 2
    command: ["python", "client.py", "device-2", "--server", "grpc-server:50051"]

networks:
  campus-net:
    driver: bridge      # Plain Docker bridge, no 5G
```

### Experiment Scripts

#### `exp_baseline_grpc.ps1` (Windows PowerShell)
#### `exp_baseline_grpc.sh` (Linux/macOS Bash)

These scripts automate an entire experiment run:
1. Build and start Docker containers.
2. Run for a specified duration.
3. Collect results from the `results/` folder.
4. Shut everything down cleanly.

**Usage (Windows):**
```powershell
.\exp_baseline_grpc.ps1 -Devices 5 -DurationSec 10 -IntervalSec 0.2 -OutputCsv results/grpc_test.csv
```

---

## 7. Module 3 — Zenoh Standalone Prototype (`zenoh/`)

### What is Zenoh?

Zenoh is a **pub/sub + query protocol** designed for edge computing and IoT. Unlike gRPC (which uses persistent bidirectional streams), Zenoh works with **key-based publish/subscribe**:
- Publishers put data on a key (like `campus/cmd/device-1`).
- Subscribers declare interest in keys (like `campus/ack/**` — wildcard).
- A **Zenoh Router** acts as the broker that routes messages between publishers and subscribers.

### Architecture

```
[Edge Node]                     [Zenoh Router]               [Device-1]
  Publishes →  campus/cmd/device-1  →  router  →  subscriber campus/cmd/device-1
  Subscribes ← campus/ack/**        ← router  ←  publishes campus/ack/device-1
```

### `src/device_zenoh.py` — Zenoh Device Simulator

```python
# Connect to router
conf.insert_json5("connect/endpoints", f'["{ZENOH_ROUTER}"]')
session = zenoh.open(conf)

# Subscribe to incoming commands on my key
cmd_key = f"campus/cmd/{device_id}"    # e.g., "campus/cmd/device-1"
ack_key = f"campus/ack/{device_id}"    # e.g., "campus/ack/device-1"

pub_ack = session.declare_publisher(ack_key)

def on_command(sample):
    data = json.loads(sample.payload.to_string())
    ts_edge_ns = data["ts_edge_ns"]
    ts_device_ns = time.time_ns()
    ack = {"device_id": device_id, "status": "OK",
           "ts_edge_ns": ts_edge_ns, "ts_device_ns": ts_device_ns}
    pub_ack.put(json.dumps(ack))   # Send ack back

sub = session.declare_subscriber(cmd_key, on_command)
```

### `src/edge_zenoh.py` — Zenoh Edge Controller

```python
# Connect and declare publishers for each device
pubs = {dev: session.declare_publisher(f"campus/cmd/{dev}") for dev in TARGET_DEVICES}

# Subscribe to all acks (wildcard)
ack_sub = session.declare_subscriber("campus/ack/**", on_ack)

# Main loop: publish commands
while True:
    payload = {"device_id": dev, "payload": "x"*PAYLOAD_BYTES, "ts_edge_ns": time.time_ns()}
    pubs[dev].put(json.dumps(payload))
    time.sleep(INTERVAL_SEC)
```

### `docker-compose.yml` — Zenoh Experiment Compose

```yaml
services:
  zenoh-router:    # Official Eclipse Zenoh router
    image: eclipse/zenoh:latest
    ports: ["7447:7447"]

  edge-node:       # Publishes commands, subscribes to acks
    environment:
      - ZENOH_ROUTER=tcp/zenoh-router:7447
      - TARGET_DEVICES=device-1,device-2

  device-1:        # Subscribes to its key, publishes acks
    command: ["python", "device_zenoh.py", "device-1"]
    environment:
      - ZENOH_ROUTER=tcp/zenoh-router:7447

  device-2:
    command: ["python", "device_zenoh.py", "device-2"]
```

### Key Differences: gRPC vs Zenoh

| Feature | gRPC | Zenoh |
|---------|------|-------|
| Pattern | Bidirectional streaming RPC | Publish/Subscribe |
| Broker needed | No (direct connection) | Yes (Zenoh Router) |
| Discovery | Manual (hostname:port) | Automatic via router |
| Idle devices | Stay connected, receive nothing | Subscribe but no data matches |
| Latency | Very low (direct TCP) | Slightly higher (via router hop) |
| Scalability | Harder (N clients × 1 server = N connections) | Easier (all connect to router) |

---

## 8. Key Identities & Credentials

| Item | Value |
|------|-------|
| **PLMN (Operator ID)** | MCC=001, MNC=01 |
| **IMSI** | `001010000000001` |
| **SIM Secret Key (K)** | `465B5CE8B199B49FAA5F0A2EE238A6BC` |
| **Operator Code (OPc)** | `E8ED289DEBA952E4285B44E71103E524` |
| **Tracking Area Code** | `1` |
| **Network Slice** | SST=1, SD=0x000001 |
| **UE Data Subnet** | `10.45.0.0/16` |
| **UE Gateway** | `10.45.0.1` |
| **APN / DNN** | `internet` |
| **WebUI URL** | `http://localhost:3000` |
| **WebUI Login** | `admin` / `1423` |
| **gRPC Server Port** | `50051` |
| **Zenoh Router Port** | `7447` |
| **NF SBI Port** | `7777` |
| **AMF NGAP Port** | `38412` |

---

## 9. How to Start Everything

### Starting the Full 5G Testbed

```powershell
cd "d:\project campus\5g-testbed"

# Build and launch all containers
docker compose up --build

# Detached mode (background)
docker compose up --build -d

# Watch logs from a specific container
docker logs -f vehicle-ue
docker logs -f edge-server

# Shut everything down
docker compose down
```

**What to look for in logs:**
1. `[NRF] NRF running...` — NRF is up
2. `[AMF] AMF running...` — AMF is up  
3. `NGAP Running` in gnb logs — gNB connected to AMF
4. `[NAS] Registration accept` in gnb or ue logs — UE registered
5. `uesimtun0` interface appears — 5G data tunnel is up
6. `[UE] Binding gRPC socket to interface uesimtun0` — app running over 5G
7. `[EDGE] Register request from device-1` — connection established
8. `[EDGE] Ack from device-1 -> RTT=X.XX ms` — system is working

### Starting the gRPC Prototype Only

```powershell
cd "d:\project campus\gRPC"
docker compose up --build
```

### Starting the Zenoh Prototype Only

```powershell
cd "d:\project campus\zenoh"
docker compose up --build
```

### Adding a Subscriber via WebUI

1. Open `http://localhost:3000`
2. Login: `admin` / `1423`
3. Click **Subscribers** → **Add Subscriber**
4. Fill in:
   - **IMSI:** `001010000000001`
   - **Subscriber Key (K):** `465B5CE8B199B49FAA5F0A2EE238A6BC`
   - **Operator Key (OPc):** `E8ED289DEBA952E4285B44E71103E524`
   - **APN:** `internet`
5. Save.

---

## 10. Troubleshooting & Known Issues

### UE fails to register: `AUTHENTICATION_FAILURE`
**Cause:** Subscriber not added to MongoDB, or IMSI/Key mismatch.
**Fix:**
1. Check subscriber is in WebUI at `http://localhost:3000`.
2. Run the MongoDB type fix: `docker exec -it mongodb mongo open5gs fix-types.js`
3. Verify IMSI/Key in `ue.yaml` matches exactly what's in the DB.

### PCF crashes with `No http.location`
**Cause:** BSF container (`open5gs-bsf`) is not running or not healthy.
**Fix:** Ensure `docker-compose.yml` includes the `open5gs-bsf` service and PCF `depends_on` it.

### `getaddrinfo failed` in SMF or AMF logs
**Cause:** A dependent container hasn't started yet (e.g., UPF hostname not yet resolvable).
**Fix:** Add proper `depends_on` with `condition: service_started` in `docker-compose.yml`.

### `vehicle-ue` gRPC client starts but gets `UNAVAILABLE`
**Cause:** `uesimtun0` interface appeared but 5G session not fully established yet.
**Fix:** The startup loop in the command already waits for `uesimtun0`, but give it more time. Check `nr-ue` logs for registration status.

### No logs from `vehicle-ue` or `edge-server`
**Cause:** Python output buffering.
**Fix:** Both containers have `PYTHONUNBUFFERED=1` set in `docker-compose.yml`. This is already fixed.

### WebUI shows blank page or `ERR_EMPTY_RESPONSE`
**Cause:** WebUI container depends on MongoDB. If MongoDB isn't healthy, WebUI won't respond.
**Fix:** Wait for MongoDB health check to pass (`docker ps` — check STATUS column for `(healthy)`).

---

## 11. Glossary

| Term | Meaning |
|------|---------|
| **5G NR** | 5G New Radio — the radio access standard |
| **AMF** | Access and Mobility Management Function — control plane entry |
| **APN** | Access Point Name — same as DNN, identifies the data network |
| **AUSF** | Authentication Server Function — handles AKA crypto |
| **BSF** | Binding Support Function — session binding registry for PCF |
| **DNN** | Data Network Name — identifies data path (e.g., "internet") |
| **GTP-U** | GPRS Tunnelling Protocol (User Plane) — tunnels UE packets |
| **gNB** | gNodeB — the 5G base station (radio tower) |
| **IMSI** | International Mobile Subscriber Identity — unique SIM ID |
| **MCC** | Mobile Country Code — 3-digit country identifier |
| **MNC** | Mobile Network Code — 2-3 digit operator identifier |
| **NF** | Network Function — a microservice in the 5G core |
| **NGAP** | Next Generation Application Protocol — AMF ↔ gNB signaling |
| **NRF** | Network Repository Function — service registry |
| **PDU Session** | Packet Data Unit Session — a data connection (like a call for data) |
| **PFCP** | Packet Forwarding Control Protocol — SMF programs UPF via this |
| **PLMN** | Public Land Mobile Network — operator identity (MCC+MNC) |
| **RTT** | Round-Trip Time — time for a packet to go and come back |
| **SBI** | Service Based Interface — HTTP/2 interface between core NFs |
| **SCP** | Service Communication Proxy — routes SBI messages between NFs |
| **SMF** | Session Management Function — manages PDU sessions, assigns IPs |
| **S-NSSAI** | Single Network Slice Selection Assistance Information (SST+SD) |
| **SST** | Slice/Service Type — 1=eMBB, 2=URLLC, 3=mMTC |
| **TAC** | Tracking Area Code — geographic grouping of cells |
| **UDM** | Unified Data Management — subscriber data front-end |
| **UDR** | Unified Data Repository — raw subscriber database interface |
| **UE** | User Equipment — the device (phone, vehicle) |
| **UERANSIM** | Open-source 5G UE and RAN simulator |
| **UPF** | User Plane Function — routes user data packets |
| **USIM** | Universal Subscriber Identity Module — the SIM standard for 5G |
| **Zenoh** | A pub/sub protocol optimized for edge and IoT |
| **gRPC** | Google Remote Procedure Call — a high-performance RPC framework |
| **protobuf** | Protocol Buffers — Google's data serialization format, used by gRPC |

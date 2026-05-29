# CAMPUS Project — What's Where and How

Quick reference for everything in this project. Open this first when you come back after a break.

---

## Git Repository

**Branch:** `main`
**Location:** `D:\project campus\`

```
project campus/
├── gRPC/                   # gRPC protocol implementation (Python, Protobuf)
├── zenoh/                  # Zenoh over TCP implementation (Python)
├── zenoh-quic/             # Zenoh over QUIC implementation (Python + TLS certs)
├── mqtt/                   # MQTT over TCP implementation (Python, Mosquitto)
├── mqtt-quic/              # MQTT over QUIC implementation (C, NanoSDK + MsQuic)
├── certs/                  # TLS certificates for Zenoh-QUIC
├── 5g-testbed/             # Open5GS + UERANSIM setup (currently broken — see phase3.md)
├── results/
│   ├── matrix/             # Phase 1 results (3 protocols, N≤10, 144 runs)
│   └── unified/            # Full results (5 protocols, N≤50, 360 runs) ← main data
├── scripts/
│   ├── run_matrix.py           # Runs all 360 experiments
│   ├── analyze_results.py      # Generates summary.md + base figures
│   ├── generate_extra_figures.py    # Degraded latency vs N + MQTT rescue figures
│   ├── generate_twopanel_figures.py # Two-panel latency_vs_N + profile_comparison
│   └── regenerate_figures.py   # Run this to regenerate ALL figures at once
├── docs/
│   ├── project-overview.md     # This file
│   ├── phase3.md               # Next steps plan
│   └── engineering-notes.md    # Bugs fixed, known issues, infrastructure notes
├── sent-report.tex         # Report v1 — sent to Francesco & Filippo on May 26
├── report final.tex        # Report v2 — follow-up, ready to send
├── requirements.txt        # Python dependencies
└── .gitignore
```

---

## Docker Hub

**Account:** `samiullahkhairy`
**URL:** https://hub.docker.com/u/samiullahkhairy

### Images

| Image | Role | Size | Notes |
|---|---|---|---|
| `samiullahkhairy/campus-grpc-device` | gRPC device client | ~223MB | Python + grpc |
| `samiullahkhairy/campus-grpc-edge` | gRPC edge server | ~235MB | Python + grpc |
| `samiullahkhairy/campus-zenoh-device` | Zenoh TCP device | ~236MB | Python + zenoh |
| `samiullahkhairy/campus-zenoh-edge` | Zenoh TCP edge | ~236MB | Python + zenoh |
| `samiullahkhairy/campus-zenoh-quic-device` | Zenoh QUIC device | ~249MB | Python + zenoh + TLS |
| `samiullahkhairy/campus-zenoh-quic-edge` | Zenoh QUIC edge | ~249MB | Python + zenoh + TLS |
| `samiullahkhairy/campus-mqtt-device` | MQTT TCP device | ~158MB | Python + paho-mqtt |
| `samiullahkhairy/campus-mqtt-edge` | MQTT TCP edge | ~158MB | Python + paho-mqtt |
| `samiullahkhairy/campus-mqtt-quic-device` | MQTT QUIC device | ~159MB | **C binary, NanoSDK + MsQuic** |
| `samiullahkhairy/campus-mqtt-quic-edge` | MQTT QUIC edge | ~159MB | **C binary, NanoSDK + MsQuic** |

**Warning:** All images are x86 only. ARM64 (Jetson Orin) rebuild needed — see `docs/phase3.md`.

### Third-party images used (already on Docker Hub, no need to manage)

| Image | Used for |
|---|---|
| `eclipse/zenoh:latest` | Zenoh router (TCP and QUIC) |
| `eclipse-mosquitto:2` | MQTT TCP broker |
| `emqx/emqx:latest` | MQTT QUIC broker |
| `gradiant/open5gs:2.7.2` | 5G core (Open5GS) |
| `gradiant/open5gs-webui:2.7.2` | Open5GS web UI |
| `louisroyer/ueransim-gnb:latest` | UERANSIM gNB |
| `louisroyer/ueransim-ue:latest` | UERANSIM UE |
| `mongo:4.4.10` | Subscriber database (Open5GS) |

---

## How to Run Things

### Regenerate all figures from existing data
```bash
pip install -r requirements.txt
python scripts/regenerate_figures.py
```
Figures land in `results/unified/`.

### Re-run the full experiment matrix (360 runs, ~4 hours)
Needs Docker running and Linux/WSL2 for netem.
```bash
python scripts/run_matrix.py
```
On a new machine, images are pulled automatically from Docker Hub.

### Re-run a specific protocol only
```bash
python scripts/run_matrix.py --protocols zenoh-quic --profiles degraded_5g --devices 1,5,10,20
```

### Resume a crashed run from a specific run number
```bash
python scripts/run_matrix.py --start-run 47
```

---

## Lab Infrastructure

### Pisa Lab (now)
- Real 5G, eMBB slice only — no multi-slice, no QoD API
- 3× Jetson AGX Orin (ARM64, JetPack 5/6) — arriving soon as UEs
- Experiments currently running in Docker on Windows + WSL2

### Torino Testbed (Phase 3)
- HPE 5G Core, 2 gNBs, 2 GPU edge servers
- LINKS OBUs (Jetson Xavier NX, JetPack 4 — different from Pisa Orins)
- NXW orchestration, CAMARA APIs (QoD, Device Location, Edge Application Management)
- Multi-slice TX available
- **Access:** VPN needed — not yet granted

---

## Results Summary

Full data in `results/unified/summary.md`. Short version:

| Protocol | Clean p50 | Good 5G p50 | Degraded p50 (N=10) | Scales to N=20? |
|---|---|---|---|---|
| Zenoh-QUIC | 2.7ms | 42ms | 164ms | Yes |
| Zenoh TCP | 2.6ms | 42ms | 163ms | Yes |
| MQTT-QUIC | 4.9ms | 45ms | 210ms | Yes |
| gRPC | 3.3ms | 43ms | 165ms | No (55% loss) |
| MQTT TCP | 44ms | 90ms | 38,759ms | No (collapse) |

**Recommendation:** Zenoh-QUIC for pub/sub, MQTT-QUIC if broker needed, gRPC for point-to-point transfers. Drop MQTT TCP.

---

## Contacts

| Person | Role | Email |
|---|---|---|
| Filippo Cugini | Senior supervisor | filippo.cugini@cnit.it |
| Francesco Paolucci | Day-to-day supervisor | francesco.paolucci@cnit.it |

---

## Key Warnings

- Open5GS + UERANSIM has **no real radio** — numbers from it are workflow validation only, never put them in a report as 5G performance numbers
- MQTT-QUIC uses **NanoMQ/EMQX**, not Mosquitto — paho-mqtt cannot do QUIC
- Zenoh-QUIC requires explicit `quic/` endpoint config — always verify it's not silently falling back to TCP
- Always distinguish "Docker simulation", "Open5GS+UERANSIM", "Pisa real 5G", and "Torino testbed" in any report

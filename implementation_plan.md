# CAMPUS — Strategic Realignment & Next Phase Plan

The feedback is right on every point. Here's my honest assessment after reading all the docs.

---

## The Diagnosis — Where You Actually Stand

### What you've done well
Three milestone reports delivered. Five protocols benchmarked at scale. Clean server-run data. The 164× MQTT rescue finding and the gRPC 50%-loss cliff are genuine, defensible results. The engineering (async QUIC callbacks, EMQX healthcheck sync, netem verification) is solid.

### What's missing — mapped against your actual obligations

| Gap | Evidence | Severity |
|-----|----------|----------|
| **DDS/RTPS not benchmarked** | SSSA activity doc §8 duty 2: "DDS + alternatives (gRPC, Zenoh, custom)". DDS listed first. You tested the alternatives, skipped the headline. | 🔴 **Critical** — reviewable gap |
| **KPI 2 (E2E ≤300ms) only half-measured** | All 3 reports measure uplink RTT only (device→edge→device). Francesco confirmed downlink (edge→selected-devices) matters. You've never measured it. | 🔴 **Critical** — you can't claim KPI 2 |
| **KPI 3 (ROI filtering ≥85%) — zero work** | [claude.md](file:///d:/project%20campus/claude.md) line 56, [learning-tracker.md](file:///d:/project%20campus/docs/learning-tracker.md) item 13: "todo". No code, no prototype, no design. This is explicitly SSSA's role. | 🔴 **Critical** — M2 deliverable |
| **KPI 4 (QoD violation ≤5%) — sandbox only** | [api-sandbox/qod/](file:///d:/project%20campus/api-sandbox/qod/) exists with a mock server and worksheet. `qod_client.py` has TODOs. Not integrated with the benchmark. | 🟡 M2 work, needs Turin |
| **KPI 5 (bandwidth ≥20%) — no metrics** | [claude.md](file:///d:/project%20campus/claude.md) line 108: "KPI 5 untestable without docker stats sidecar." Still open. | 🟡 Deferred, but flagged |
| **UERANSIM trap** | Your own [claude.md](file:///d:/project%20campus/claude.md) line 135 and [phase3.md](file:///d:/project%20campus/docs/phase3.md) line 23: "workflow validation only — NEVER 5G performance numbers." Good — you already know this. Don't lose that discipline. | ✅ Already guarded |

---

## The Feedback Is Correct — My Assessment

### 1. DDS is required, not optional

The SSSA activity document names "DDS + alternatives." You tested gRPC, Zenoh (TCP+QUIC), MQTT (TCP+QUIC) — five protocols — and none of them is DDS. For the IT-UC2 automotive perception use case, DDS/RTPS is the standard (ROS2 uses it). A reviewer **will** notice.

> [!IMPORTANT]
> DDS is architecturally different from everything you've tested. It's the first **decentralized, brokerless pub/sub over UDP with per-topic QoS policies**. This is a new concept axis, not just another protocol to slot in.

**Bounded scope:**
- **One DDS implementation:** Eclipse Cyclone DDS (lightweight, C, MIT-licensed, ROS2 default) or eProsima Fast DDS (ROS2 alternative). Pick Cyclone DDS — it's simpler, Docker images exist, and it matches your "lightweight" pattern.
- **Transport:** RTPS over UDP (the native DDS wire protocol). This is a genuinely different transport axis from your TCP/QUIC work.
- **Containers:** Build a `campus-dds-edge` and `campus-dds-device` pair following the same pattern as your other protocols. Integrate into `run_matrix.py` as protocol `dds`.
- **Sweep:** Run the **full** matrix to match the other five protocols (clean + good_5g + degraded_5g, **N=1,2,5,10,20,50**, payloads 100+2000, rates 5+10) = 72 cells, ~1 hour on the server. **Keep N=50** — DDS surviving N=50 where Zenoh/Zenoh-QUIC died (8 of your 9 empty cells) would be a genuine finding; dropping it throws that away.

### 2. Downlink leg is a small, high-value addition

Your current flow is:

```
Edge → publishes command → Device receives → Device sends ACK → Edge measures RTT
```

This is an **edge-originated round-trip RTT** (not a device→edge uplink — the edge is both sender and receiver, which is *why* one monotonic clock suffices). KPI 2 requires the real perception loop:

```
Device A (perception) → Edge (fuse) → Device B (receive update)
```

You don't need to rebuild the whole system. Add **one measurement cell**: edge publishes to Device B after receiving from Device A. Measure the total chain. Even one configuration (N=2, clean + degraded, one payload) is enough to **claim** KPI 2 with real numbers instead of leaving it as "half of KPI 2."

### 3. ROI filtering (KPI 3) is your M2 deliverable — and it's untouched

The CAMARA Device Location "devices-in-area" API is what serves this. Your [learning-tracker.md](file:///d:/project%20campus/docs/learning-tracker.md) item 13 says "todo." The [api-sandbox/](file:///d:/project%20campus/api-sandbox/) only has QoD, not Device Location.

This is the real M2 work (July) and it's completely untouched. The UERANSIM/Open5GS path won't help here — it doesn't expose CAMARA APIs. This needs the Turin testbed (or a local mock first, then Turin).

### 4. Stop benchmarking transports after DDS

After DDS, the emulated comparison is **complete**: you will have covered brokerless (gRPC, DDS), router-mediated (Zenoh), and broker-mediated (MQTT) across TCP, QUIC, and UDP transports. That's a comprehensive matrix. Freeze it. Any further transport work is diminishing returns against the KPI gaps above.

---

## Proposed Sequence

> [!WARNING]
> The dates below assume the mqtt-quic degraded retry finishes today. Adjust if it doesn't.

### Phase A: DDS Benchmark (≈ 2-3 days — scaffolding already written)

#### `dds/` — DDS/RTPS Protocol Module — CURRENT STATE (verified in repo, 2026-06-08)

**Already written and correct (do NOT rewrite):**
| File | Status | Notes |
|------|--------|-------|
| `dds/src/edge_dds.py` | ✅ Done | Edge-anchored monotonic RTT, **RELIABLE QoS** (line 141), SIGTERM→CSV, background ack-reader thread. Writes the exact `device_id,send_ts_ns,recv_ts_ns,latency_ms` contract — drops straight into `analyze_results.py`. |
| `dds/src/device_dds.py` | ✅ Done | Subscribes `campus_cmd_{dev}`, echoes ack on `campus_ack_{dev}` carrying `ts_edge_ns`. Correct. |

**Written but will break / needs fixing:**
| File | Status | Problem |
|------|--------|---------|
| `dds/docker/Dockerfile.{edge,device}` | ❌ Build fails | `pip install cyclonedds` does **not** bundle the C core — the comment is wrong (see **G1**). |
| `dds/cyclonedds.xml` | ⚠️ Self-contradicting | Comment says "force unicast" but the config keeps multicast SPDP with no peer fallback (see **G2**). |

**Remaining steps:**
| Step | What | Deliverable |
|------|------|-------------|
| A1 | **Fix Dockerfiles** — build the Cyclone DDS C core from source, set `CYCLONEDDS_HOME`, then `pip install cyclonedds` (**G1**) | Images that build |
| A2 | **Verify discovery** on the bridge with a clean N=2 smoke test; fix `cyclonedds.xml` only if acks don't flow (**G2**) | Devices find the edge at N=50 |
| A3 | **Set HISTORY QoS depth** in both scripts so reliable samples aren't silently overwritten under load (**G3**) | Loss % comparable to MQTT/Zenoh |
| A4 | **Add `protocol == "dds"` branch** to `run_matrix.py` `generate_compose()` — brokerless: ONLY `edge-node` + `device-N`, no router/broker (**G4**) | DDS in the sweep |
| A5 | Build + tag + push `samiullahkhairy/campus-dds-edge:latest`, `samiullahkhairy/campus-dds-device:latest` | Images the runner pulls |
| A6 | Smoke test → confirm non-empty CSVs → full run **including N=50** (`--protocols dds --output-base results/server-run --retries 3`) | ~72 CSVs in `results/server-run/dds/` |
| A7 | `python scripts/analyze_results.py` — DDS auto-plots, **no analyzer edits needed** (it discovers protocols via `os.listdir`) | Updated figures |
| A8 | Append DDS section to the server-run report | Deliverable to Filippo |

**🔴 OWN IT — DDS/RTPS vs broker/router/RPC.** You must be able to explain:
- Why DDS is decentralized (no broker, no router — RTPS discovery + direct UDP multicast/unicast)
- How DDS QoS policies (RELIABILITY, DEADLINE, LIVELINESS) differ from MQTT QoS levels
- Why DDS matters for ROS2/automotive (it's the default middleware)

---

### DDS implementation guards (G1–G4) — hand these to Copilot verbatim

#### G1 — Dockerfile: `pip install cyclonedds` will NOT build on `python:3.10-slim`
The current line `RUN pip install --no-cache-dir cyclonedds` with the comment "includes the C library" is **false**. The `cyclonedds` Python binding needs the Cyclone DDS **C core** present and `CYCLONEDDS_HOME` set at install time; the slim image has neither, so the build errors with *"Could not locate cyclonedds"*. Reliable fix — build the core from source first, in **both** Dockerfiles:

```dockerfile
FROM python:3.10-slim
WORKDIR /app
RUN apt-get update && apt-get install -y git cmake g++ iproute2 && rm -rf /var/lib/apt/lists/*
# Pin a release tag for reproducibility (repo hygiene)
RUN git clone --depth 1 --branch 0.10.5 https://github.com/eclipse-cyclonedds/cyclonedds /tmp/cdds \
 && cmake -S /tmp/cdds -B /tmp/cdds/build -DCMAKE_INSTALL_PREFIX=/usr/local -DBUILD_IDLC=ON \
 && cmake --build /tmp/cdds/build --target install -j \
 && rm -rf /tmp/cdds
ENV CYCLONEDDS_HOME=/usr/local
ENV LD_LIBRARY_PATH=/usr/local/lib
RUN pip install --no-cache-dir cyclonedds
COPY cyclonedds.xml /etc/cyclonedds/cyclonedds.xml
ENV CYCLONEDDS_URI=file:///etc/cyclonedds/cyclonedds.xml
COPY src/edge_dds.py .          # (device: src/device_dds.py)
CMD ["python", "edge_dds.py"]   # (device: device_dds.py)
```
Note the `CYCLONEDDS_URI=file://…` scheme — some Cyclone versions reject a bare path.

#### G2 — `cyclonedds.xml`: the discovery config contradicts its own comment
It sets `<AllowMulticast>spdp</AllowMulticast>` (which still uses **multicast** for participant discovery) while the comment claims "force unicast." On a **single-host Docker bridge** multicast within the one network usually *does* work (L2 flood), so this may be fine — but there is **no unicast fallback**, so if discovery fails you get empty cells (the same failure mode you fought with mqtt-quic).
- **First:** run the N=2 clean smoke test and confirm acks flow. If they do, just fix the misleading comment and move on.
- **Only if discovery fails:** switch to true unicast — `<AllowMulticast>false</AllowMulticast>` plus an explicit `<Discovery><Peers>` listing `edge-node` and `device-1..N` (their service names on `campus-net`). Brokerless DDS has no fixed rendezvous host, so every participant must be enumerable.

#### G3 — QoS HISTORY depth (fairness bug, not cosmetic)
Both scripts use `Qos(Policy.Reliability.Reliable(...))` only — HISTORY defaults to `KeepLast(1)`. At 10 Hz with the edge's 5 ms ack poll across up to 50 readers, a depth-1 queue can overwrite an undelivered sample → silent drops that look like protocol loss and make DDS non-comparable to MQTT QoS-1 / Zenoh. Add explicit depth on **both** writer and reader, edge and device:
```python
qos = Qos(
    Policy.Reliability.Reliable(max_blocking_time=duration(seconds=1)),
    Policy.History.KeepLast(100),   # or Policy.History.KeepAll
)
```

#### G4 — `run_matrix.py`: add a brokerless `dds` branch
Unlike zenoh/mqtt there is **no router or broker service** — only `edge-node` + `device-N`. `CYCLONEDDS_URI` is baked into the image (G1), so nothing to inject. The existing `edge_service = "grpc-server" if protocol == "grpc" else "edge-node"` line already covers DDS. Add to `generate_compose()`:
```python
elif protocol == "dds":
    compose["services"]["edge-node"] = {
        "image": f"{DOCKER_HUB}/campus-dds-edge:latest",
        "environment": [
            f"TARGET_DEVICES={devices_str}",
            f"PAYLOAD_BYTES={payload_bytes}",
            f"INTERVAL_SEC={interval_sec}",
            f"RUN_DURATION={run_duration}",
            f"OUTPUT_CSV=/app/results/{filename}",
            "START_DELAY_SEC=5",
            "PYTHONUNBUFFERED=1",
        ],
        "volumes": [f"{abs_output_dir}:/app/results"],
        "cap_add": ["NET_ADMIN"],
        "networks": ["campus-net"],
    }
    for dev in devices_list:
        compose["services"][dev] = {
            "image": f"{DOCKER_HUB}/campus-dds-device:latest",
            "command": ["python", "device_dds.py", dev],
            "environment": [f"DEVICE_ID={dev}", "PYTHONUNBUFFERED=1"],
            "cap_add": ["NET_ADMIN"],
            "networks": ["campus-net"],
        }
```

---

### Phase B: Downlink Leg for KPI 2 (≈ 1-2 days)

Minimal change: modify the edge to forward a received perception update to a second device, measure the full E2E chain. Even one cell closes the KPI 2 claim.

#### [MODIFY] Edge scripts — **all protocols** (your call: gRPC, Zenoh, Zenoh-QUIC, MQTT, MQTT-QUIC, DDS)

| Step | What |
|------|------|
| B1 | Add a "forward" path in each edge: on receiving A's perception update, immediately publish a forwarded update to device-B |
| B2 | Compute E2E **without subtracting cross-container clocks** (see **clock guard** below) |
| B3 | Run one cell per protocol: N=2, degraded_5g, 100B, 10Hz. Report E2E p50/p95 |

> [!WARNING]
> **Clock guard — the naive version is wrong.** `E2E = t(device-B receives) − t(device-A sent)` subtracts timestamps from **two different containers**. On a single Linux host it *happens* to work because containers share the kernel `CLOCK_MONOTONIC` — but on the **Turin testbed** A and B are separate vehicles with unsynced clocks, so that subtraction becomes garbage. Two safe options:
> - **(preferred, portable)** Keep the **edge as the only clock**: report E2E ≈ (A↔edge RTT)/2 + (edge↔B RTT)/2 — both legs measured on the edge clock, exactly like the current benchmark. No cross-container subtraction, works on Braine *and* Turin.
> - **(quick, Braine-only)** Use the A→B subtraction but **verify** both containers read the same monotonic source and **state in the report** it's valid only single-host; Turin needs PTP/NTP.

This is small and high-value. If E2E p50 < 300 ms under degraded 5G, you can claim KPI 2. Doing all protocols (your choice) also lets you say *which* protocol best satisfies the E2E budget, not just that the budget is met.

---

### Phase C: ROI Filtering Prototype — KPI 3 (≈ 1 week, M2 prep)

This is the **untouched M2 deliverable**. Start with a local mock (like you did with QoD), then integrate on Turin.

| Step | What |
|------|------|
| C1 | Build `api-sandbox/device-location/` mock server implementing CAMARA "devices-in-area" |
| C2 | Build a geo-filtering module: given edge's ROI polygon + device locations, compute which devices should receive the map update |
| C3 | Integrate with the Zenoh-QUIC edge: before forwarding, query device locations, filter, measure "relevant deliveries / total deliveries" → KPI 3 |
| C4 | Write worksheet (like QoD) for the explain-back |

---

### Phase D: QoD Integration — KPI 4 (Turin-dependent)

Blocked on Turin VPN access. The [api-sandbox/qod/](file:///d:/project%20campus/api-sandbox/qod/) mock is ready. When Turin opens:

| Step | What |
|------|------|
| D1 | Finish `qod_client.py` TODOs against the mock |
| D2 | Point it at Turin's real QoD endpoint |
| D3 | Create a QoD session before running a benchmark cell, measure violations |

---

## Open Questions for You

> [!IMPORTANT]
> These affect the plan. Answer before I start executing.

1. ~~**DDS implementation language**~~ — **DECIDED: Python (`cyclonedds`)**, already written in `dds/src/`. Matches Zenoh/MQTT-TCP/gRPC. No action.

2. **Report strategy:** Should DDS results go into a **4th report** (Report 4), or should I **append a DDS section to Report 3** (the server-run report)? A 4th report keeps the chain clean; appending keeps the page count down.

3. **Downlink leg scope:** Should I implement the E2E measurement for just Zenoh-QUIC (the recommended protocol), or do you want it for all 6 protocols? I recommend **for all the protocols** .
4. **Timeline pressure:** Is the M2 milestone (July) a hard deadline from Filippo, or is there flexibility? This determines whether we rush Phase C or do it properly.

## What NOT to Do

- ❌ Don't run benchmarks on UERANSIM and report them as 5G numbers
- ❌ Don't start ARM64 rebuilds before DDS + KPI 2/3 are closed — ARM64 is Phase 3/Turin prep
- ❌ Don't spend more time on the mqtt-quic deadlock fix — document it honestly (you already did) and move on
- ❌ Don't expand the transport matrix further after DDS — 6 protocols × 3 profiles × 6 N-values is comprehensive enough

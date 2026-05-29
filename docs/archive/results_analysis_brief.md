# CAMPUS Edge–Device Protocol Benchmark
## Comparative Performance Analysis (gRPC/HTTP-2, Zenoh/TCP, and MQTT/TCP)
**Date**: May 26, 2026  
**Author**: Samiullah Khairy  
**Project**: CAMPUS / ENVELOPE (EU Horizon Europe)

---

## 1. Executive Summary

This report presents comparative latency, scalability, and packet loss benchmarks for **gRPC/HTTP-2**, **Zenoh/TCP**, and **MQTT/TCP (Mosquitto)** under synthetic 5G network impairments. The goal is to evaluate their suitability for real-time vehicle-to-edge (V2X) cooperative perception and selective downlink services in the CAMPUS testbed.

### Headline Findings:
1. **Zenoh is the Latency Winner**: Zenoh demonstrated the lowest baseline round-trip time (RTT) of **~1.2 ms** and maintained stable tail latency (p95 **< 290 ms**) even under degraded 5G conditions with 10 concurrent devices at 10 Hz.
2. **gRPC is Highly Resilient**: By utilizing direct client-server HTTP/2 multiplexed streams, gRPC prevents cross-client head-of-line blocking, maintaining p95 RTT **< 310 ms** under degraded 5G.
3. **MQTT Suffers from Queueing Collapse (Buffer Bloat)**: Under degraded 5G conditions ($N=10$, 2 KB payload, 10 Hz rate, 1% packet loss), MQTT's latency ballooned to **p50 = 31.9 seconds** and **p95 = 58.3 seconds**. This is a catastrophic failure mode caused by TCP retransmission delays queueing up in the central broker's buffer.
4. **Client Library Latency Overhead**: The Paho-MQTT Python client introduced a static **~45 ms** delay even on a clean local link due to default socket polling timeouts, highlighting that client library implementation details are just as critical as wire protocol specs.

---

## 2. Experimental Methodology

To ensure a fair, reproducible comparison, we emulated a single edge server communicating with $N$ simulated vehicles over a containerized bridge network (`campus-net`) using Docker.

```
       [ gRPC Client ] ──(Direct Streams)──┐
                                           ▼
┌──────────────────┐               ┌──────────────┐
│  Simulated OBUs  │ ──(Zenoh)───► │ Zenoh Router │ ──► [ Edge Server ]
│  (device-1..N)   │               └──────────────┘
│                  │               ┌──────────────┐
└──────────────────┘ ──(MQTT)────► │ MQTT Broker  │ ──► [ Edge Server ]
                                   └──────────────┘
```

### 2.1. Test Matrix Dimensions
* **Protocols**: gRPC (HTTP/2), Zenoh, MQTT (Mosquitto, QoS 1)
* **Device Densities ($N$)**: 1, 2, 5, 10 concurrent active devices
* **Payload Sizes**: 100 Bytes (light telemetry/GPS) vs. 2000 Bytes (fused object-detection lists)
* **Message Frequency**: 5 Hz and 10 Hz (standard automotive sensor frequencies; 1 Hz runs are excluded from latency percentiles due to small sample sizes)
* **Network Profiles (Injected via Linux kernel `tc netem` on container interfaces)**:
  - **`clean`**: No artificial impairment.
  - **`good_5g`**: 20 ms one-way delay, 1 ms jitter (normal distribution), 0.1% loss ($40\text{ ms}$ minimum theoretical RTT).
  - **`degraded_5g`**: 80 ms one-way delay, 10 ms jitter (normal distribution), 1.0% loss ($160\text{ ms}$ minimum theoretical RTT).

---

## 3. Comparative Performance Analysis

The following sections analyze representative slices of the 144-run experiment matrix. The complete dataset is available in [summary.md](file:///d:/project%20campus/results/matrix/summary.md).

### 3.1. Baseline Performance (Clean Network, N=1, 100B, 10Hz)
On a local bridge network with zero artificial delay, we isolate the protocols' serialization and socket processing overheads.

| Protocol | p50 Latency (ms) | p95 Latency (ms) | p99 Latency (ms) | Mean (ms) |
|---|---|---|---|---|
| **Zenoh** | **0.99** | **2.56** | **3.32** | **1.22** |
| **gRPC** | 2.26 | 4.37 | 4.66 | 2.52 |
| **MQTT** | 46.23 | 48.78 | 49.51 | 46.00 |

* **Analysis**: Zenoh has the lowest median processing delay (~1.0 ms), and gRPC displays comparable baseline tail latency. 
* **The MQTT Polling Penalty**: MQTT exhibits a static ~45 ms delay. This is caused by `paho-mqtt`’s select-loop socket timeout. The background thread blocks in a select socket call for up to 50 ms before polling for data, artificially capping MQTT's responsiveness on fast links.

### 3.2. Normal 5G Performance (Good 5G, N=5 vs. N=10, 2KB, 10Hz)
We evaluate scaling under nominal 5G conditions (40 ms minimum network RTT, 0.1% loss).

| Protocol | N | p50 Latency (ms) | p95 Latency (ms) | p99 Latency (ms) | Packet Loss % |
|---|---|---|---|---|---|
| **Zenoh** | 5 | **43.45** | **45.97** | **47.11** | 4.3% |
| **gRPC** | 5 | 43.13 | 46.58 | 48.93 | 4.7% |
| **MQTT** | 5 | 87.07 | 94.13 | 128.81 | 3.4% |
| **Zenoh** | 10 | **43.05** | **45.74** | **46.88** | 4.4% |
| **gRPC** | 10 | 42.19 | 45.21 | 47.75 | 6.2% |
| **MQTT** | 10 | 84.43 | 115.35 | 128.64 | 2.9% |

* **Analysis**: Under good 5G conditions, Zenoh and gRPC both track the physical minimum RTT (~40 ms) perfectly, even when scaled to 10 devices.
* **Overhead**: MQTT shows ~84 ms p50 delay (including the client polling penalty and broker queue delay). At $N=10$, its tail latency (p99) begins creeping up to **128 ms**, indicating stable but elevated delay.

### 3.3. Degraded 5G Performance (Degraded 5G, N=5 vs. N=10, 2KB, 10Hz)
Under degraded signal conditions (160 ms minimum network RTT, 1% packet loss), we stress-test queue stability and retransmission recovery.

| Protocol | N | p50 Latency (ms) | p95 Latency (ms) | p99 Latency (ms) | Packet Loss % |
|---|---|---|---|---|---|
| **Zenoh** | 5 | **164.00** | **217.06** | **411.67** | 1.8% |
| **gRPC** | 5 | 164.85 | 267.43 | 429.83 | 4.1% |
| **MQTT** | 5 | **11,740.40** | **22,014.92** | **23,061.31** | 2.9% |
| **Zenoh** | 10 | **164.28** | **282.93** | **440.10** | 1.8% |
| **gRPC** | 10 | **164.01** | **305.37** | **444.23** | 5.7% |
| **MQTT** | 10 | **31,957.44** | **58,370.33** | **61,375.46** | 4.0% |

* **Analysis**: Zenoh and gRPC successfully absorb the degradation. Their p50 remains close to the 150-160 ms RTT baseline. Tail latencies (p99) spike to ~410-440 ms due to occasional packet loss retransmissions, which is expected behavior for TCP-based transport.
* **The MQTT Queueing Collapse**: MQTT's latency completely collapses, ballooning to **31.9 seconds** (p50) and **58.3 seconds** (p95) at $N=10$. The protocol becomes completely unusable for V2X tasks.

---

## 4. Root Cause Analysis (The "Why")

### 4.1. Broker Queue Congestion & Buffer Bloat (MQTT)
MQTT relies on a central broker (Mosquitto) that serializes client connections. Under the hood:
1. **TCP Retransmissions**: The 1% packet loss triggers TCP window reductions and packet retransmissions.
2. **QoS 1 Ack Wait**: MQTT QoS 1 requires a handshake (`PUBLISH` $\rightarrow$ `PUBACK`). A packet loss blocks the transmission queue for that client (Head-of-Line blocking).
3. **Queue Compounding**: The Edge Node continues generating messages at 10 Hz ($100\text{ messages/sec}$ across 10 devices). Because the broker cannot flush packets due to TCP blocking, messages stack up in the broker's memory buffer. 
4. **Queueing Latency**: Packets spend seconds waiting in the buffer line before they are even written to the socket. This is a textbook example of **Buffer Bloat**.

```
[Edge Node] ──(100 msgs/s)──► [ Broker Buffer Queue ] ──(Blocked by TCP Loss)──► [ Devices ]
                              [ Msg 100 ... Msg 2    ]
                              ▲
                              └─ Packets wait here for seconds (Latency Explodes)
```

### 4.2. Direct Multiplexed Connections (gRPC)
gRPC avoids the broker bottleneck. It opens direct HTTP/2 multiplexed streams from the server to each OBU.
* If Device 1 experiences packet loss and its TCP socket blocks, it does not affect the TCP socket or streams of Device 2.
* The lack of a centralized, shared message broker queue isolates network degradation to the affected client.

### 4.3. Decentralized Peer Routing (Zenoh)
Zenoh is designed for high-throughput, low-latency V2X.
* Its routing layer is decoupled from connection management.
* Zenoh utilizes thin routing paths and session layers, bypassing heavy TCP/HTTP framing. It can run directly over raw TCP, UDP, or QUIC, resulting in minimal buffering overhead and fast recovery from loss.

### 4.4. MQTT Bimodal Latency Distribution
In the generated CDF curves under `clean` and `good_5g` profiles, MQTT exhibits a distinct bimodal latency distribution (some samples landing at lower latency, while the bulk is delayed to a higher latency band).
* **Broker-Side Batching and IO Loop Tuning**: This is likely driven by the broker flushing behavior or the `paho-mqtt` IO select-loop socket polling interval, which creates two distinct latency regimes.
* **TCP Slow-Start / Batching**: Initial TCP window scaling and nagle-style buffering on the broker could also lead to message batching, introducing a dual-peak distribution. This phenomenon is currently under deeper investigation.

---

## 5. Architectural Recommendations for CAMPUS V2X

Based on these empirical results, we outline the following design recommendations for the vehicle-to-edge network layer:

1. **Avoid Centralized Brokers for Safety-Critical Downlink**: Standard MQTT brokers are a major architectural risk for real-time applications (like cooperative collision avoidance or emergency vehicle routing) if packet loss is present. 
2. **Zenoh is the Recommended V2X Protocol**: Zenoh should be the primary choice for cooperative perception. It combines the low baseline latency of gRPC with pub/sub filtering, while scaling cleanly to high device counts under degraded network conditions.
3. **Deploy gRPC for Heavy Unicast Services**: gRPC is highly suited for point-to-point map uploads or HD map streaming where direct client-server contracts are required, due to its stream isolation.
4. **Resolve the Client Polling Bottleneck**: If MQTT must be used, the default Paho client loop must be tuned or replaced (e.g., using asyncio-based clients like `gmqtt` or `aiomqtt`) to eliminate the static 45 ms select sleep interval.

---

## 6. Study Limitations & Future Work (Disclaimers)

1. **Synthetic Impairment Emulation**: All network impairments (latency, loss, jitter) were emulated synthetically using `tc netem` on a virtual Docker bridge network on a single host. These results serve as a protocol-level baseline and do not capture real-world 5G NR (New Radio) channel dynamics, gNodeB scheduling, or cellular core network traversal. Live 5G testbed validation is scheduled for the next phase.
2. **Single Repeat per Configuration**: Each cell in the matrix represents a single 30-second run (producing ~150–1500 samples at 10 Hz). While sufficient for preliminary evaluation, a reviewer-grade benchmark requires running each configuration 3–5 times and reporting the median-of-medians. This will be integrated into the automated runner for Phase 2.
3. **No CPU/Memory Resource Metrics**: Client and broker/server resource utilization (CPU, RAM, thread counts) was not measured during this sweep. Resource efficiency profiling is a scheduled follow-up.
4. **MQTT Baseline Configuration**: MQTT was benchmarked using QoS 1 (At Least Once) and JSON-serialized payloads to match the core data structures of the other protocols. To isolate pure broker-hop overhead from structural QoS handshake costs, a baseline control row for MQTT with QoS 0 and raw binary payloads (no JSON) is planned for the next run.

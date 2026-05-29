# CAMPUS Edge–Device Protocol Benchmark Report
## Comparative Performance Analysis (gRPC/HTTP-2, Zenoh/TCP, and MQTT/TCP)

**Date**: May 26, 2026  
**Author**: Samiullah Khairy  
**Project**: CAMPUS / ENVELOPE (EU Horizon Europe)  
**Deliverable**: V2X Protocol Benchmark v1.0  

---

## 1. Executive Summary

This report evaluates the round-trip latency, scalability, and packet loss characteristics of three network protocols—**gRPC/HTTP-2**, **Zenoh/TCP**, and **MQTT/TCP (Mosquitto)**—under emulated 5G radio conditions. The goal is to determine the optimal communication layer for real-time vehicle-to-edge (V2X) cooperative perception in the CAMPUS testbed.

### Headline Findings:
1. **Zenoh is the Latency Winner**: Zenoh demonstrated the lowest baseline round-trip time (RTT) of **~1.0 ms** and maintained stable tail latency (p95 **< 290 ms**) even under degraded 5G conditions with 10 concurrent devices at 10 Hz.
2. **gRPC is Highly Resilient**: gRPC uses direct HTTP/2 multiplexed streams from the server to each OBU. This isolates packet loss, preventing cross-client head-of-line blocking, and maintains p95 RTT **< 310 ms** under degraded 5G.
3. **MQTT Suffers from Queueing Collapse (Buffer Bloat)**: Under degraded 5G conditions ($N=10$, 2 KB payload, 10 Hz rate, 1% packet loss), MQTT's latency ballooned to **p50 = 31.9 seconds** and **p95 = 58.3 seconds**. This is a catastrophic failure mode caused by TCP retransmission delays queueing up in the central broker's buffer.
4. **Client Library Latency Overhead**: The Paho-MQTT Python client introduces a static **~45 ms** delay even on a clean local link due to default socket polling timeouts, highlighting that client library implementation details are just as critical as wire protocol specs.

---

## 2. Experimental Methodology

To ensure a fair, reproducible comparison, we emulated a single edge server communicating with $N$ simulated vehicles over a containerized bridge network (`campus-net`) using Docker.

```mermaid
graph TD
    subgraph OBUs (device-1..N)
        D1[device-1]
        D2[device-2]
        DN[device-N]
    end

    subgraph Transport Channels
        grpc[gRPC Direct Streams]
        zenoh[Zenoh Router]
        mqtt[Mosquitto Broker]
    end

    Edge[Edge Server]

    D1 & D2 & DN -->|gRPC| grpc
    D1 & D2 & DN -->|Zenoh| zenoh
    D1 & D2 & DN -->|MQTT| mqtt

    grpc --> Edge
    zenoh --> Edge
    mqtt --> Edge
```

### 2.1. Test Matrix Dimensions
* **Protocols**: gRPC (HTTP/2), Zenoh (TCP mode), MQTT (Mosquitto, QoS 1)
* **Device Densities ($N$)**: 1, 2, 5, 10 concurrent active devices
* **Payload Sizes**: 100 Bytes (light telemetry/GPS) vs. 2000 Bytes (fused object-detection lists)
* **Message Frequency**: 5 Hz and 10 Hz (standard automotive sensor frequencies; 1 Hz runs are excluded from latency percentiles due to small sample sizes)
* **Network Profiles (Injected via Linux kernel `tc netem` on container interfaces)**:
  - **`clean`**: No artificial impairment.
  - **`good_5g`**: 20 ms one-way delay, 1 ms jitter (normal distribution), 0.1% loss ($40\text{ ms}$ minimum theoretical RTT).
  - **`degraded_5g`**: 80 ms one-way delay, 10 ms jitter (normal distribution), 1.0% loss ($160\text{ ms}$ minimum theoretical RTT).

---

## 3. Visualizations & Performance Analysis

### 3.1. RTT Latency Cumulative Distribution Function (CDF)
The CDF plot below highlights the cumulative probability of latency on a good 5G link (40ms theoretical minimum RTT) for $N=1$ device sending 100B payloads at 10Hz:

![RTT Latency CDF (Normal 5G, N=1, 100B, 10Hz)](file:///d:/project campus/results/matrix/latency_cdf.png)

* **Key Takeaway**: Zenoh and gRPC sit tightly on the 40 ms network delay boundary. MQTT is shifted right by ~45 ms due to the client polling delay.

### 3.2. Latency Scalability vs. Device Density (N)
The scaling chart below tracks p95 latency as the number of concurrent devices scales from 1 to 10 on a good 5G link:

![p95 Latency vs. Device Count (Normal 5G, 100B, 10Hz)](file:///d:/project campus/results/matrix/latency_vs_N.png)

* **Key Takeaway**: Zenoh and gRPC remain perfectly flat as device density scales, showcasing high stream concurrency. MQTT is stable but carries a higher static overhead.

### 3.3. Profile Comparison across Network Environments
The comparison chart below evaluates p95 latencies for Zenoh, gRPC, and MQTT across the Clean, Good 5G, and Degraded 5G environments (for $N=2$ devices):

![p95 Latency comparison across Network Profiles (N=2, 100B, 10Hz)](file:///d:/project campus/results/matrix/profile_comparison.png)

* **Key Takeaway**: gRPC and Zenoh adapt seamlessly to degradation, scaling in line with the physical link constraints. MQTT spikes significantly under degraded conditions due to broker-side retransmission delays.

---

## 4. Key Performance Data

Below is a filtered slice of the benchmark data for $N=5$ and $N=10$ using the heavy **2 KB payload** at the **10 Hz** message rate.

| Protocol | Profile | N | Rate | Packet Loss % | p50 Latency (ms) | p95 Latency (ms) | p99 Latency (ms) |
|---|---|---|---|---|---|---|---|
| **Zenoh** | **GOOD_5G** | 5 | 10Hz | 4.3% | **43.45** | **45.97** | **47.11** |
| **gRPC** | **GOOD_5G** | 5 | 10Hz | 4.7% | 43.13 | 46.58 | 48.93 |
| **MQTT** | **GOOD_5G** | 5 | 10Hz | 3.4% | 87.07 | 94.13 | 128.81 |
| **Zenoh** | **GOOD_5G** | 10 | 10Hz | 4.4% | **43.05** | **45.74** | **46.88** |
| **gRPC** | **GOOD_5G** | 10 | 10Hz | 6.2% | 42.19 | 45.21 | 47.75 |
| **MQTT** | **GOOD_5G** | 10 | 10Hz | 2.9% | 84.43 | 115.35 | 128.64 |
| **Zenoh** | **DEGRADED_5G** | 5 | 10Hz | 1.8% | **164.00** | **217.06** | **411.67** |
| **gRPC** | **DEGRADED_5G** | 5 | 10Hz | 4.1% | 164.85 | 267.43 | 429.83 |
| **MQTT** | **DEGRADED_5G** | 5 | 10Hz | 2.9% | **11,740.40** | **22,014.92** | **23,061.31** |
| **Zenoh** | **DEGRADED_5G** | 10 | 10Hz | 1.8% | **164.28** | **282.93** | **440.10** |
| **gRPC** | **DEGRADED_5G** | 10 | 10Hz | 5.7% | 164.01 | 305.37 | 444.23 |
| **MQTT** | **DEGRADED_5G** | 10 | 10Hz | 4.0% | **31,957.44** | **58,370.33** | **61,375.46** |

*The full experiment matrix statistics can be reviewed in [summary.md](file:///d:/project%20campus/results/matrix/summary.md).*

---

## 5. Root Cause Analysis (The "Why")

### 5.1. Broker Queue Congestion & Buffer Bloat (MQTT)
MQTT relies on a central broker (Mosquitto) that serializes client connections. Under packet loss:
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

### 5.2. Direct Multiplexed Connections (gRPC)
gRPC avoids the broker bottleneck. It opens direct HTTP/2 multiplexed streams from the server to each OBU.
* If Device 1 experiences packet loss and its TCP socket blocks, it does not affect the TCP socket or streams of Device 2.
* The lack of a centralized, shared message broker queue isolates network degradation to the affected client.

### 5.3. Decentralized Peer Routing (Zenoh)
Zenoh is designed for high-throughput, low-latency V2X.
* Its routing layer is decoupled from connection management.
* Zenoh utilizes thin routing paths and session layers, bypassing heavy TCP/HTTP framing. It can run directly over raw TCP, UDP, or QUIC, resulting in minimal buffering overhead and fast recovery from loss.

### 5.4. MQTT Bimodal Latency Distribution
In the generated CDF curves under `clean` and `good_5g` profiles, MQTT exhibits a distinct bimodal latency distribution (some samples landing at lower latency, while the bulk is delayed to a higher latency band).
* **Broker-Side Batching and IO Loop Tuning**: This is likely driven by the broker flushing behavior or the `paho-mqtt` IO select-loop socket polling interval, which creates two distinct latency regimes.
* **TCP Slow-Start / Batching**: Initial TCP window scaling and nagle-style buffering on the broker could also lead to message batching, introducing a dual-peak distribution.

---

## 6. Architectural Recommendations for CAMPUS V2X

Based on these empirical results, we outline the following design recommendations for the vehicle-to-edge network layer:

1. **Avoid Centralized Brokers for Safety-Critical Downlink**: Standard MQTT brokers are a major architectural risk for real-time applications (like cooperative collision avoidance or emergency vehicle routing) if packet loss is present. 
2. **Zenoh is the Recommended V2X Protocol**: Zenoh should be the primary choice for cooperative perception. It combines the low baseline latency of gRPC with pub/sub filtering, while scaling cleanly to high device counts under degraded network conditions.
3. **Deploy gRPC for Heavy Unicast Services**: gRPC is highly suited for point-to-point map uploads or HD map streaming where direct client-server contracts are required, due to its stream isolation.
4. **Resolve the Client Polling Bottleneck**: If MQTT must be used, the default Paho client loop must be tuned or replaced (e.g., using asyncio-based clients like `gmqtt` or `aiomqtt`) to eliminate the static 45 ms select sleep interval.

---

## 7. Study Limitations & Future Work (Disclaimers)

1. **Synthetic Impairment Emulation**: All network impairments (latency, loss, jitter) were emulated synthetically using `tc netem` on a virtual Docker bridge network on a single host. These results serve as a protocol-level baseline and do not capture real-world 5G NR (New Radio) channel dynamics, gNodeB scheduling, or cellular core network traversal. Live 5G testbed validation is scheduled for the next phase.
2. **Single Repeat per Configuration**: Each cell in the matrix represents a single 30-second run. While sufficient for preliminary evaluation, a reviewer-grade benchmark requires running each configuration 3–5 times and reporting the median-of-medians. This will be integrated into the automated runner for Phase 2.
3. **No CPU/Memory Resource Metrics**: Client and broker/server resource utilization (CPU, RAM, thread counts) was not measured during this sweep. Resource efficiency profiling is a scheduled follow-up.
4. **MQTT Baseline Configuration**: MQTT was benchmarked using QoS 1 (At Least Once) and JSON-serialized payloads to match the core data structures of the other protocols. To isolate pure broker-hop overhead from structural QoS handshake costs, a baseline control row for MQTT with QoS 0 and raw binary payloads (no JSON) is planned for the next run.

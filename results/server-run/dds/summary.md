# CAMPUS Experiment Benchmark — Cyclone DDS Summary

This file summarizes the benchmark results for **Eclipse Cyclone DDS** (RTPS over UDP, decentralized brokerless pub/sub) from the bare-metal server run (`braine-head-node`). It provides the performance data and evaluates how DDS scales compared to the other five benchmarked protocols (gRPC, Zenoh, Zenoh-QUIC, MQTT, MQTT-QUIC).

---

## 1. DDS Benchmark Results Table

Below are the extracted performance results for DDS across the three network profiles: **Clean** (no impairment), **Good 5G** (20ms delay ±1ms, 0.1% loss), and **Degraded 5G** (80ms delay ±10ms, 1.0% loss).

| Profile | N | Payload | Rate | Recv | Loss % | p50 (ms) | p95 (ms) | p99 (ms) | Mean (ms) |
|---|---|---|---|---|---|---|---|---|---|
| **CLEAN** | 1 | 100B | 5Hz | 150 | 0.2% | 4.33 | 6.61 | 7.24 | 4.46 |
| **CLEAN** | 1 | 100B | 10Hz | 300 | 0.3% | 4.42 | 7.00 | 7.41 | 4.33 |
| **CLEAN** | 1 | 2000B | 5Hz | 150 | 0.3% | 4.46 | 6.94 | 7.44 | 4.43 |
| **CLEAN** | 1 | 2000B | 10Hz | 299 | 0.4% | 4.25 | 6.86 | 7.31 | 4.19 |
| **CLEAN** | 2 | 100B | 5Hz | 300 | 0.3% | 4.20 | 6.69 | 7.11 | 4.28 |
| **CLEAN** | 2 | 100B | 10Hz | 598 | 0.4% | 4.17 | 6.70 | 7.37 | 4.18 |
| **CLEAN** | 2 | 2000B | 5Hz | 300 | 0.3% | 4.29 | 6.73 | 7.29 | 4.58 |
| **CLEAN** | 2 | 2000B | 10Hz | 598 | 0.5% | 4.14 | 6.70 | 6.97 | 4.21 |
| **CLEAN** | 5 | 100B | 5Hz | 750 | 0.4% | 4.26 | 6.93 | 7.41 | 4.32 |
| **CLEAN** | 5 | 100B | 10Hz | 1490 | 0.7% | 4.02 | 7.18 | 7.76 | 4.29 |
| **CLEAN** | 5 | 2000B | 5Hz | 750 | 0.5% | 4.37 | 7.12 | 7.46 | 4.41 |
| **CLEAN** | 5 | 2000B | 10Hz | 1490 | 0.9% | 4.16 | 6.97 | 7.57 | 4.30 |
| **CLEAN** | 10 | 100B | 5Hz | 1490 | 0.7% | 4.71 | 6.99 | 7.55 | 4.37 |
| **CLEAN** | 10 | 100B | 10Hz | 2970 | 1.3% | 4.26 | 6.85 | 7.30 | 4.39 |
| **CLEAN** | 10 | 2000B | 5Hz | 1490 | 0.8% | 4.54 | 6.95 | 7.59 | 4.40 |
| **CLEAN** | 10 | 2000B | 10Hz | 2960 | 1.5% | 4.01 | 6.81 | 7.31 | 4.25 |
| **CLEAN** | 20 | 100B | 5Hz | 2980 | 1.3% | 2.43 | 8.19 | 9.01 | 3.40 |
| **CLEAN** | 20 | 100B | 10Hz | 5880 | 2.2% | 3.51 | 7.71 | 8.78 | 3.89 |
| **CLEAN** | 20 | 2000B | 5Hz | 2960 | 1.5% | 2.75 | 7.69 | 8.36 | 3.43 |
| **CLEAN** | 20 | 2000B | 10Hz | 5840 | 2.7% | 3.19 | 6.19 | 8.06 | 3.66 |
| **CLEAN** | 50 | 100B | 5Hz | 4617 | 38.6% | 4.19 | 5.36 | 8.35 | 4.23 |
| **CLEAN** | 50 | 100B | 10Hz | 8928 | 40.7% | 4.07 | 4.93 | 7.52 | 4.06 |
| **CLEAN** | 50 | 2000B | 5Hz | 4526 | 39.7% | 4.36 | 6.09 | 9.27 | 4.51 |
| **CLEAN** | 50 | 2000B | 10Hz | 8550 | 43.1% | 4.56 | 5.82 | 7.11 | 4.55 |
| | | | | | | | | | |
| **GOOD_5G** | 1 | 100B | 5Hz | 150 | 0.2% | 44.63 | 47.51 | 48.97 | 44.70 |
| **GOOD_5G** | 1 | 100B | 10Hz | 300 | 0.3% | 44.38 | 47.44 | 49.35 | 44.32 |
| **GOOD_5G** | 1 | 2000B | 5Hz | 150 | 0.2% | 45.10 | 48.55 | 49.53 | 46.23 |
| **GOOD_5G** | 1 | 2000B | 10Hz | 300 | 0.3% | 44.99 | 48.40 | 50.42 | 45.65 |
| **GOOD_5G** | 2 | 100B | 5Hz | 300 | 0.3% | 44.31 | 47.71 | 48.89 | 44.24 |
| **GOOD_5G** | 2 | 100B | 10Hz | 598 | 0.4% | 44.30 | 48.02 | 49.22 | 44.58 |
| **GOOD_5G** | 2 | 2000B | 5Hz | 300 | 0.3% | 44.76 | 47.75 | 49.82 | 45.54 |
| **GOOD_5G** | 2 | 2000B | 10Hz | 598 | 0.4% | 44.70 | 48.08 | 49.45 | 44.75 |
| **GOOD_5G** | 5 | 100B | 5Hz | 750 | 0.4% | 44.41 | 47.89 | 49.69 | 44.85 |
| **GOOD_5G** | 5 | 100B | 10Hz | 1495 | 0.6% | 44.43 | 48.20 | 49.65 | 44.85 |
| **GOOD_5G** | 5 | 2000B | 5Hz | 750 | 0.4% | 44.74 | 48.32 | 49.87 | 45.30 |
| **GOOD_5G** | 5 | 2000B | 10Hz | 1490 | 0.7% | 44.80 | 48.38 | 50.11 | 45.67 |
| **GOOD_5G** | 10 | 100B | 5Hz | 1500 | 0.6% | 44.28 | 47.99 | 49.53 | 44.48 |
| **GOOD_5G** | 10 | 100B | 10Hz | 2970 | 1.0% | 44.18 | 47.85 | 49.50 | 44.16 |
| **GOOD_5G** | 10 | 2000B | 5Hz | 1500 | 0.7% | 45.40 | 48.50 | 50.15 | 45.76 |
| **GOOD_5G** | 10 | 2000B | 10Hz | 2968 | 1.2% | 44.59 | 48.72 | 68.05 | 45.92 |
| **GOOD_5G** | 20 | 100B | 5Hz | 2980 | 1.0% | 43.08 | 49.26 | 50.20 | 42.85 |
| **GOOD_5G** | 20 | 100B | 10Hz | 5900 | 1.7% | 43.95 | 49.12 | 50.45 | 44.02 |
| **GOOD_5G** | 20 | 2000B | 5Hz | 2980 | 1.1% | 43.13 | 49.33 | 49.93 | 44.37 |
| **GOOD_5G** | 20 | 2000B | 10Hz | 5880 | 2.0% | 44.72 | 49.49 | 52.71 | 45.16 |
| **GOOD_5G** | 50 | 100B | 5Hz | 4588 | 39.1% | 44.88 | 47.12 | 48.61 | 38.71 |
| **GOOD_5G** | 50 | 100B | 10Hz | 55 | 99.6% | 43.96 | 47.84 | 65.84 | 44.64 |
| **GOOD_5G** | 50 | 2000B | 5Hz | 1628 | 78.4% | 44.62 | 48.18 | 50.03 | 40.38 |
| **GOOD_5G** | 50 | 2000B | 10Hz | 8959 | 40.5% | 45.45 | 46.94 | 50.67 | 39.88 |
| | | | | | | | | | |
| **DEGRADED_5G** | 1 | 100B | 5Hz | 150 | 0.2% | 166.10 | 218.24 | 428.92 | 175.69 |
| **DEGRADED_5G** | 1 | 100B | 10Hz | 299 | 0.3% | 166.68 | 325.60 | 436.56 | 179.93 |
| **DEGRADED_5G** | 1 | 2000B | 5Hz | 150 | 0.2% | 171.14 | 240.96 | 547.64 | 183.61 |
| **DEGRADED_5G** | 1 | 2000B | 10Hz | 299 | 0.3% | 176.55 | 550.85 | 679.64 | 230.90 |
| **DEGRADED_5G** | 2 | 100B | 5Hz | 299 | 0.6% | 162.93 | 194.91 | 440.52 | 171.33 |
| **DEGRADED_5G** | 2 | 100B | 10Hz | 596 | 0.4% | 165.44 | 250.93 | 422.24 | 175.22 |
| **DEGRADED_5G** | 2 | 2000B | 5Hz | 300 | 0.3% | 171.52 | 439.63 | 633.41 | 198.34 |
| **DEGRADED_5G** | 2 | 2000B | 10Hz | 596 | 0.4% | 169.86 | 372.48 | 628.05 | 191.62 |
| **DEGRADED_5G** | 5 | 100B | 5Hz | 750 | 0.4% | 165.07 | 193.56 | 437.75 | 170.30 |
| **DEGRADED_5G** | 5 | 100B | 10Hz | 1490 | 0.6% | 165.72 | 229.25 | 426.03 | 173.72 |
| **DEGRADED_5G** | 5 | 2000B | 5Hz | 750 | 0.4% | 170.51 | 223.80 | 621.47 | 183.30 |
| **DEGRADED_5G** | 5 | 2000B | 10Hz | 1482 | 0.9% | 172.09 | 450.38 | 636.43 | 201.63 |
| **DEGRADED_5G** | 10 | 100B | 5Hz | 1500 | 0.6% | 164.87 | 194.50 | 422.00 | 169.13 |
| **DEGRADED_5G** | 10 | 100B | 10Hz | 2964 | 1.2% | 165.48 | 255.99 | 427.76 | 175.35 |
| **DEGRADED_5G** | 10 | 2000B | 5Hz | 1500 | 0.6% | 171.36 | 419.05 | 632.79 | 191.36 |
| **DEGRADED_5G** | 10 | 2000B | 10Hz | 2954 | 1.3% | 171.59 | 457.00 | 633.93 | 201.78 |
| **DEGRADED_5G** | 20 | 100B | 5Hz | 2980 | 0.9% | 164.80 | 195.71 | 431.32 | 166.93 |
| **DEGRADED_5G** | 20 | 100B | 10Hz | 5877 | 1.7% | 164.53 | 232.87 | 427.23 | 170.31 |
| **DEGRADED_5G** | 20 | 2000B | 5Hz | 2978 | 1.2% | 169.20 | 213.52 | 598.35 | 177.10 |
| **DEGRADED_5G** | 20 | 2000B | 10Hz | 5875 | 2.1% | 171.34 | 447.65 | 644.46 | 197.44 |
| **DEGRADED_5G** | 50 | 100B | 5Hz | 4585 | 39.1% | 158.02 | 193.18 | 416.22 | 143.12 |
| **DEGRADED_5G** | 50 | 100B | 10Hz | 8955 | 40.2% | 158.52 | 199.18 | 418.36 | 148.36 |
| **DEGRADED_5G** | 50 | 2000B | 5Hz | 4675 | 37.7% | 165.18 | 240.92 | 622.15 | 165.72 |
| **DEGRADED_5G** | 50 | 2000B | 10Hz | 8885 | 40.6% | 163.78 | 418.41 | 636.28 | 163.34 |

> **Loss-% caveat (one cell):** the GOOD_5G / N=50 / 100B / 10Hz row shows 96.2%, but the true loss is **99.6%** (55 of 15,000 messages). `analyze_results.py` infers run duration from the observed send-window, which collapses to ~2.8 s when most devices never connect, deflating `expected`. All other cells span the full ~30 s, so their loss figures are accurate. See §2.4.

---

## 2. Comparative Analysis (DDS vs. Others)

### 2.1. Baseline Performance (CLEAN & N <= 20)
* **Latency Floor**: DDS exhibits an extremely low latency profile. At $N \le 20$, median latency remains bound to **~4 ms** (100B, 10Hz). While slightly higher than Zenoh/Zenoh-QUIC (which hover at **~0.6–0.9 ms**) and gRPC (**~1.0–2.8 ms**), DDS operates significantly faster than MQTT over TCP, which suffers from client library polling loops and baseline overhead, remaining clamped at **~43 ms**.
* **Loss Profile**: Under clean conditions, DDS loss remains exceptionally low ($<2.7\%$) up to $N=20$. 

### 2.2. Resilience under Network Impairment (DEGRADED_5G)
DDS's brokerless architecture over UDP demonstrates superior latency resilience compared to TCP counterparts under severe network degradation:
* **The MQTT TCP Queue Collapse**: Under DEGRADED_5G (1% loss, 80ms delay) at $N=20$, MQTT over TCP collapses into queuing delays due to Head-of-Line blocking and TCP retransmissions, leading to a median latency of **95.9 seconds**.
* **DDS Immunity**: Because DDS runs over UDP/RTPS and utilizes decentralized direct peer communication, it is completely immune to broker-side serialization queues and TCP Head-of-Line blocking. At $N=20$ under degraded 5G, DDS maintains a steady, flat median latency of **164.53 ms** (with a p95 of **232.87 ms**), practically tracking the physical network RTT floor.
* **Comparison with QUIC Options**: Under degraded conditions, DDS latency characteristics closely mirror Zenoh, Zenoh-QUIC, and MQTT-QUIC (which cluster around **160–190 ms**).

### 2.3. Scale Limits & Packet Loss Behavior at N=50
When scaling to the maximum concurrency ($N=50$), distinct protocol-specific architectural limits emerge:
1. **gRPC (HTTP/2 Stream Exhaustion)**: gRPC drops **80.1%** of packets across all profiles (Clean/Good/Degraded) at $N=50$. While the few packets that survive maintain low latency (~40ms in Good 5G), the protocol is functionally unusable at this scale for multi-device broadcast.
2. **DDS (RELIABLE history-overwrite under overload)**: Under $N=50$, DDS experiences **~38% to 43% packet loss** across Clean, Good, and Degraded networks. Note that DDS here is **not** best-effort: both endpoints run `Reliability.RELIABLE` with `History.KeepLast(100)` and `max_blocking_time = 1 s` (mirroring MQTT QoS-1 at-least-once intent). The loss is therefore **not** raw UDP socket-buffer discard — at 50 readers × ~500 msg/s the shallow KeepLast(100) writer history overwrites samples before the slowest/lossiest readers acknowledge them, and the 1 s blocking cap stops the publisher from back-pressuring. Un-acked samples age out of the history and are never delivered. The architectural consequence is the key finding: configured for reliability, DDS **sheds stale backlog to stay fresh** under overload rather than queuing it — the exact opposite of MQTT-TCP, which hoards (driving latency to minutes). This keeps delivered packets within **~4.0 ms (Clean)** and **~158 ms (Degraded)**. Zenoh and Zenoh-QUIC show similar shed-not-queue behaviors (~40% loss) at $N=50$.
3. **MQTT-QUIC (Active Flow Control)**: MQTT-over-QUIC maintains the lowest packet loss under CLEAN and GOOD_5G at $N=50$ ($<0.8\%$, with RTT at ~12ms and ~50ms). However, under DEGRADED_5G conditions at $N=50$, the QUIC congestion window throttles throughput, causing packet loss to rise to **44.5%** and latency to spike to **2.17 seconds**.

### 2.4. Discovery Phase Flakiness under Impairments
* **Observation**: In the GOOD_5G profile at $N=50$, two specific cells show extreme loss. The 100B @ 10Hz cell is a **near-total discovery collapse**: only **55 of 15,000 intended messages** arrived (**99.6% loss**), from roughly 5 of 50 devices active for just 2.8 s. (The auto-generated table reports this cell as 96.2% — an artifact of `analyze_results.py` inferring run duration from the observed send-window, which collapses to ~2.8 s when most devices never connect; the true loss against the intended 30 s / 50 devices is 99.6%.) The 2000B @ 5Hz cell shows **78.3% loss** over a full 30 s window (genuine steady-state drop, not a duration artifact).
* **Explanation**: Because DDS is decentralized, it relies on a peer-to-peer discovery phase (SPDP/SED) to map endpoints. In a lossy network environment (where packet drops are active from the first millisecond), high-concurrency container startup can cause initial discovery packets to be dropped. When discovery is delayed or fails, subscribers never establish the session with the Edge and miss the publication sweep entirely — hence near-total loss for the affected device. This is a startup-fragility finding specific to high $N$ on lossy links; at the Turin target scale ($N \le 20$) it does not appear.

---

## 3. Summary of Findings & SSSA Recommendations

1. **DDS is highly viable for low-latency, brokerless automotive perception.** Its UDP-based nature prevents the queuing-delay catastrophe that plagues MQTT (TCP), and it does not suffer from the connection/stream-exhaustion drop-offs seen in gRPC.
2. **For $N \le 20$ (the target scale of Turin IT-UC2)**, DDS fulfills all latency and freshness targets (freshness $\le$ 200ms, E2E $\le$ 300ms) even under degraded 5G.
3. **Discovery Hardening**: In deployments with packet-impaired links, a startup delay or a robust unicast discovery retry configuration (like the dynamically generated peers configuration used in our final runner) is critical to prevent initial handshake drop-outs.

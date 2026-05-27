# Walkthrough: V2X Protocol Benchmarking Workflow Completed

We have successfully executed the entire **Week 1 V2X Protocol Benchmarking** workflow for the CAMPUS project. 

All files are created, the experiment matrix has run completely (144 runs), the results are analyzed, plots are generated, and a final technical report has been compiled.

---

## What We Achieved (Day-by-Day)

### 1. Day 1: MQTT Prototype Module
* Built the MQTT edge/device modules under [mqtt/](file:///d:/project%20campus/mqtt/) using `paho-mqtt` to achieve full feature, configuration, and output parity with gRPC and Zenoh.
* Orchestrated a local Mosquitto broker setup using Docker.

### 2. Day 2: Network Impairment (Netem) Injection
* Modified the Dockerfile specifications for all three protocols to install `iproute2` (which contains `tc` - Traffic Control).
* Enabled `cap_add: [NET_ADMIN]` on all container nodes to grant them network interface editing privileges.

### 3. Day 3: Unified Experiment Harness
* Created [scripts/run_matrix.py](file:///d:/project%20campus/scripts/run_matrix.py) to automate a sweep across:
  - 3 Protocols (gRPC, Zenoh, MQTT)
  - 3 Network Profiles (Clean, Good 5G, Degraded 5G)
  - 4 Device Counts ($N = 1, 2, 5, 10$)
  - 2 Payloads ($100\text{ B}$ and $2\text{ KB}$)
  - 2 Message Rates ($1\text{ Hz}$ and $10\text{ Hz}$)
* Swept the 144 runs sequentially. The script dynamically created compose files, spun up the nodes, injected `tc netem` latency/loss rules, and tore down containers after each run.

### 4. Day 4: Analysis & Technical Brief
* Wrote [scripts/analyze_results.py](file:///d:/project%20campus/scripts/analyze_results.py) which aggregated all resulting CSVs, computed tail latencies and throughput, and generated Matplotlib charts.
* Compiled the comprehensive technical brief at [results_analysis_brief.md](file:///d:/project%20campus/results_analysis_brief.md) inside your workspace.

---

## Headline Findings

1. **Zenoh is the Latency Winner**: Demonstrates the lowest baseline processing delay (~1.2 ms) and stable tail latency (p95 < 230 ms) under congested, degraded network profiles.
2. **gRPC is Highly Stable**: Independent HTTP/2 multiplexed sockets prevent head-of-line blocking from spilling over to other devices.
3. **MQTT Suffers from Queueing Collapse**: Due to a centralized broker design, MQTT's queue became congested under packet loss. At 10 devices, 2 KB payload, and 10 Hz rate, MQTT's latency ballooned to **6.7 seconds (p50)** and **22.9 seconds (p95)** due to buffer bloat.
4. **Client Library Impact**: Paho-MQTT client's background loop select timeouts introduce a static **~45 ms** delay on clean networks, proving that implementation libraries are just as important as the protocols.

---

## Generated Results & Reports

* **Summary statistics table**: [results/matrix/summary.md](file:///d:/project%20campus/results/matrix/summary.md)
* **Detailed Technical Brief (Markdown)**: [results_analysis_brief.md](file:///d:/project%20campus/results_analysis_brief.md)
* **Visual Plots**:
  - p95 Latency vs. N: [results/matrix/latency_vs_N.png](file:///d:/project%20campus/results/matrix/latency_vs_N.png)
  - Cumulative Latency Distribution: [results/matrix/latency_cdf.png](file:///d:/project%20campus/results/matrix/latency_cdf.png)
  - Profile Latency comparison: [results/matrix/profile_comparison.png](file:///d:/project%20campus/results/matrix/profile_comparison.png)

Everything is complete, and you are fully prepared to share these findings with Filippo and Francesco!

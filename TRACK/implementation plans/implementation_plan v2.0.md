# CAMPUS Protocol Benchmark — Implementation Plan (v2.0)

This plan details the implementation of **Day 2 (Netem Impairment Injection)** and **Day 3 (Unified Experiment Harness)** to build the multi-protocol benchmark matrix (gRPC vs Zenoh vs MQTT) requested by Filippo.

---

## User Review Required

> [!IMPORTANT]
> **Docker Daemon Prerequisite:**
> The experiments run containerized topologies. The user **must start Docker Desktop** before running the test sweeps. The runner script will check if Docker is active and exit with a helpful warning if it is not.

> [!IMPORTANT]
> **Impairment Strategy: Container-Internal `tc` (Traffic Control) via `cap_add: [NET_ADMIN]`**
> Instead of using Pumba (which requires mounting the docker socket and pulling external management containers that can fail on Windows host setups), we will:
> 1. Add `cap_add: [NET_ADMIN]` to the edge and device containers in the `docker-compose.yml` files.
> 2. Install `iproute2` (`iproute-tc` package) in the Dockerfiles.
> 3. Use a helper script/command to apply `tc qdisc` directly inside the containers at startup.
>
> This gives us precise control over simulated link conditions (uplink vs downlink) and is 100% reliable across Windows, macOS, and Linux without external orchestrator dependencies.

---

## Open Questions

> [!NOTE]
> **WSL2 / Linux Kernel Modules:**
> If testing the actual 5G core later, WSL2/Linux kernel modules (`gtp5g`, `sctp`) are required. However, for our Day 2/3 plain Docker+netem testbed, no host kernel modules are needed. The standard bridge network and `tc` command will work on standard Docker Desktop (Hyper-V or WSL2 backend).

---

## Proposed Changes

### 1. Netem Network Impairment (Day 2)

We define three target network profiles:
* **`clean`**: No network impairment (baseline bridge network).
* **`good_5g`**: 20 ms one-way delay, 1 ms jitter (normal distribution), 0.1% packet loss.
* **`degraded_5g`**: 80 ms one-way delay, 10 ms jitter (normal distribution), 1% packet loss.

#### Container / Dockerfile Updates
For gRPC, Zenoh, and MQTT modules, we will:
1. Update `Dockerfile.edge` and `Dockerfile.device` to install the `iproute2` package:
   ```dockerfile
   RUN apt-get update && apt-get install -y iproute2 && rm -rf /var/lib/apt/lists/*
   ```
2. Update the `docker-compose.yml` files to include:
   ```yaml
   cap_add:
     - NET_ADMIN
   ```

#### Script-level Netem Controllers
We will create a helper script `scripts/inject_impairment.py` (or integrate directly into the matrix runner) that executes `tc` commands on the target containers:
```bash
# Apply latency and loss on eth0 interface of a running container
docker exec --privileged <container_name> tc qdisc add dev eth0 root netem delay 20ms 1ms loss 0.1%
```
This allows us to dynamically apply profiles to running docker-compose networks without rebuilding the containers or hardcoding conditions.

---

### 2. Unified Experiment Harness (Day 3)

We will build a single runner script `d:\project campus\scripts\run_matrix.py` to sweep the benchmark space.

#### Sweep Dimensions
1. **Protocols**: `grpc`, `zenoh`, `mqtt`
2. **Device Count (N)**: 1, 2, 5, 10
3. **Profiles**: `clean`, `good_5g`, `degraded_5g`
4. **Payload Size**: 100 B, 2 KB
5. **Message Rate**: 1 Hz (1.0s interval), 10 Hz (0.1s interval)

#### Matrix Storage
All results will write to a unified folder structure:
`results/matrix/<protocol>/<profile>/N_<device_count>_pay_<payload_bytes>_rate_<hz>.csv`

#### Harness Code Structure (`run_matrix.py`)
```python
# Pseudo-code flow
for protocol in ["grpc", "zenoh", "mqtt"]:
    for profile in ["clean", "good_5g", "degraded_5g"]:
        for n in [1, 2, 5, 10]:
            for payload in [100, 2000]:
                for rate in [1, 10]:
                    # 1. Start docker-compose for the protocol
                    # 2. Scale devices to 'n'
                    # 3. Apply netem profile using docker exec tc commands
                    # 4. Run Edge node with payload and rate settings for 30s
                    # 5. Capture edge node stdout & output CSV
                    # 6. Copy output CSV to unified matrix path
                    # 7. Stop docker-compose and cleanup
```

---

## Verification Plan

### Automated Tests
1. **Network Impairment Smoke Test**:
   - Run a container with `cap_add: [NET_ADMIN]`.
   - Apply impairment: `docker exec <container> tc qdisc add dev eth0 root netem delay 100ms`.
   - Ping the container from host or another container, confirming RTT increases by 100ms.
2. **Harness Verification**:
   - Run the matrix script with a subset (1 protocol, 1 profile, 1 device count) for 5 seconds.
   - Verify that the output CSV is generated in the correct subdirectory with identical columns: `device_id, send_ts_ns, recv_ts_ns, latency_ms`.

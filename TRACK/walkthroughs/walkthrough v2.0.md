# Walkthrough: MQTT Prototype, Netem Setup, and Matrix Harness Completed

We have successfully implemented:
1. **Day 1: MQTT Prototype Module** (Full parity with gRPC and Zenoh).
2. **Day 2: Network Impairment (Netem) Injection Capabilities** (Added traffic control tools and permissions to all protocol docker layers).
3. **Day 3: Unified Matrix Experiment Harness** (Created a master sweep runner to orchestrate the benchmark sweep).

---

## Detailed Implementation Breakdown (Day 2 & 3)

Here is a summary of what was added and why:

### 1. Network Impairment (Netem) Setup — Day 2
To simulate 5G link degradation (latency, jitter, packet loss) directly inside our Docker environments, we updated all three protocol stacks (gRPC, Zenoh, MQTT):
* **`iproute2` Package Installed**: 
  - Modified [gRPC server/client Dockerfiles](file:///d:/project%20campus/gRPC/docker/), [Zenoh edge/device Dockerfiles](file:///d:/project%20campus/zenoh/docker/), and [MQTT edge/device Dockerfiles](file:///d:/project%20campus/mqtt/docker/) to execute `apt-get update && apt-get install -y iproute2`.
  - *Why?* A container's base image (like `python:3.10-slim`) does not contain network utilities. `iproute2` installs the `tc` (Traffic Control) command, enabling inside-container network namespace modifications.
* **`cap_add: [NET_ADMIN]` Configured**:
  - Updated `docker-compose.yml` configurations for [gRPC](file:///d:/project%20campus/gRPC/docker-compose.yml), [Zenoh](file:///d:/project%20campus/zenoh/docker-compose.yml), and [MQTT](file:///d:/project%20campus/mqtt/docker-compose.yml) to add `NET_ADMIN` capabilities to the edge and device nodes.
  - *Why?* By default, Docker containers run in sandboxed namespaces with restricted networking privileges. The `NET_ADMIN` permission is required to edit container-level interface queues (qdisc) for delay and loss.

### 2. Unified Experiment Harness (`run_matrix.py`) — Day 3
We created a master benchmark coordinator at [scripts/run_matrix.py](file:///d:/project%20campus/scripts/run_matrix.py). It automates the sweep across:
* **Sweep Axis**: 3 Protocols × 3 Network Profiles (`clean`, `good_5g`, `degraded_5g`) × 4 Device Counts (`1, 2, 5, 10`) × 2 Payloads (`100B, 2000B`) × 2 Message Rates (`1Hz, 10Hz`) = **144 total iterations**.
* **Dynamic Compose Generation**: Generates temporary compose definitions for the exact combination, scaling devices up to $N$.
* **Runtime Impairment Injection**: Uses `docker exec` to run `tc qdisc add dev eth0 root netem` commands on active containers.
* **Outcome Storage**: Mounts a local volume, saving CSV files directly to:
  `results/matrix/<protocol>/<profile>/N_<device_count>_pay_<payload_bytes>_rate_<hz>.csv`

---

## Verification & Testing

To verify the harness logic without executing the containers, we ran:
```powershell
python scripts/run_matrix.py --dry-run
```

* **Result**: The script successfully validated, parsed arguments, generated execution schedules, and output the matrix of 144 configurations sequentially without error.

---

## How to Run the Benchmark

Once you start **Docker Desktop**, run the benchmark using:
```powershell
# Run from the project root directory
python scripts/run_matrix.py --duration 30
```
This will run the entire suite automatically, collecting metrics under `results/matrix/`.

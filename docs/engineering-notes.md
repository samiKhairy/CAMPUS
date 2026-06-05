# Engineering Notes — CAMPUS Protocol Benchmark

This file documents bugs found, fixes applied, and system-level issues hit during the benchmarking experiments. Kept separate from the reports sent to supervisors.

---

## Bugs Fixed

### 1. Wall-clock bug — negative RTTs
**Problem:** Used `time.time_ns()` for timestamps. NTP adjustments during a run caused the clock to jump backwards, producing negative RTT values that corrupted percentile estimates.

**Fix:** Replaced with `time.monotonic_ns()` everywhere (edge server and all device containers). Monotonic clock never goes backwards.

**Files affected:** All edge and device scripts across all five protocols.

---

### 2. Netem timing — contaminated early samples
**Problem:** The matrix runner injected `tc netem` rules after starting containers, but the edge server started sending immediately. The first few seconds of each run had no impairment, contaminating CDFs with clean-link samples even in `good_5g` and `degraded_5g` runs.

**Fix:** Added `START_DELAY_SEC = 5.0` to all edge scripts. The edge waits 5 seconds before sending the first message, giving the runner time to apply netem rules first.

---

## Engineering Fixes at Scale (N=50)

### 3. NanoSDK client thread mutex deadlock
**Problem:** MQTT-QUIC C clients using the standard NNG synchronous receive loop (`nng_recv_aio`) crashed with:
```
pthread_mutex_lock: Resource deadlock avoided
```
NNG's synchronous calls blocked the single-threaded MsQuic event loop when handling multiplexed QUIC streams. At N=50, the rate of concurrent stream events was high enough to trigger this race condition reliably.

**Fix:** Refactored `edge_mqtt.c` and `device_mqtt.c` to use NanoSDK's asynchronous callback API (`nng_mqtt_quic_set_msg_recv_cb`). Packet handling is delegated to worker threads; the synchronous receive loop was eliminated entirely.

---

### 4. EMQX broker boot synchronization
**Problem:** EMQX Enterprise takes 15--25 seconds to initialize its Erlang VM and start the QUIC listener on port 14567. When 50 C clients started simultaneously, they timed out during the boot window and failed permanently.

**Fix:** Added a native Docker Compose `healthcheck` to the EMQX broker service in `run_matrix.py` (running `emqx ping`). Client containers use `depends_on: condition: service_healthy` so they only start after the broker is fully ready.

---

### 5. Docker Hub rate-limiting at N=50
**Problem:** Running `docker compose up --build` with N=50 sent 50 parallel auth requests to Docker Hub for the `python:3.10-slim` base image. This triggered Cloudflare 520 errors and Docker Hub rate-limit blocks, stalling builds mid-run.

**Fix:** Refactored `run_matrix.py` to declare the `build` parameter only on `device-1`, tag it as a shared local image (`campus-<protocol>-device:latest`), and configure `device-2` through `device-50` to use `image:` instead of `build:`. This eliminates 49 redundant builds and auth requests per run.

Added `--pull missing` flag so experiments run entirely offline once images are cached locally.

---

### 6. WSL2 virtual disk exhaustion
**Problem:** Cumulative container log output across hundreds of N=50 runs filled the WSL2 virtual disk (`ext4.vhdx`), causing the Linux filesystem to remount read-only with `input/output error`. Running experiments crashed mid-sweep.

**Fix:** Changed `docker compose down` calls in `run_matrix.py` from `check=True` to `check=False` so a temporary I/O lock during teardown doesn't abort the entire sweep. Also periodically pruned container logs manually (`docker system prune`) between long runs.

---

## Known Issues Still Open

### N=50 Zenoh / Zenoh-QUIC empty runs
At N=50, several Zenoh and Zenoh-QUIC CSV files are 44 bytes (header only, zero data rows). The edge ran for 30 seconds and received zero ACKs back. The pattern is inconsistent across configurations (some 10Hz runs fail while 5Hz of the same payload succeed, and vice versa), suggesting a race condition or intermittent resource exhaustion in the Zenoh router container at this scale rather than a clean resource ceiling.

Not investigated further because N≤20 data is sufficient for the architecture decision. Should be revisited on the physical testbed with proper container resource limits and router logs enabled.

### MQTT bimodal at N=10 CLEAN
At N=10, 100B, clean network, MQTT shows a bimodal latency distribution: p50 drops to ~8ms while p95 stays at ~49ms. This is a `paho-mqtt` IO loop artifact — under high broker activity the client loop thread processes queued messages more aggressively and bypasses the 50ms polling timeout for a subset of messages. Not a protocol issue; would disappear if using an async client. Not pursued further since MQTT/TCP was disqualified on other grounds.

---

## Experiment Infrastructure Notes

- **Result directories:** `results/matrix/` (Phase 1, 3 TCP protocols, N≤10) and `results/unified/` (full 5-protocol sweep, N≤50)
- **Figure generation:** `scripts/analyze_results.py` (summary + 3 original figures), `scripts/generate_extra_figures.py` (degraded latency vs N + MQTT rescue), `scripts/generate_twopanel_figures.py` (two-panel versions of latency_vs_N and profile_comparison)
- **Matrix runner:** `scripts/run_matrix.py` — runs all configurations sequentially, applies netem, collects CSVs

---

## Server Migration — Braine node (June 2026)

Moved the benchmark off the WSL2 laptop onto a lab server (`braine-head-node`, 10.30.7.40 — Xeon Gold 6238R, 112 threads, 251 GB RAM) to run clean high-N sweeps. Hit a chain of infrastructure issues; documented here as a deployment runbook.

### 7. Stale Docker Hub images — netem silently failed
**Problem:** First smoke test on the server "succeeded" (wrote a CSV) but every RTT was ~0.6 ms under `good_5g` instead of ~40 ms, with `[WARNING] Failed to apply netem`. Root cause: the `samiullahkhairy/campus-*` images on Docker Hub were **stale — built before `iproute2` was added to the Dockerfiles**, so `tc` was missing inside the containers (`docker exec … tc …` → `tc: not found`). The runner continued anyway and wrote clean-LAN latency mislabeled as good_5g.

**Fix:** Rebuilt all 10 images from the current Dockerfiles (which do install `iproute2`) directly on the server, then re-pushed to Docker Hub. **Lesson:** always verify results against the expected netem floor (good_5g ≈ 40 ms, degraded ≈ 160 ms) — a CSV appearing is not proof netem worked.

**Follow-up (open):** `apply_netem()` returns `False` on failure but the runner ignores it and continues. Should be changed to abort/flag the run so a missing `tc` can never silently poison a dataset again.

### 8. Snap Docker could not stop containers
**Problem:** The server's Docker was the **Snap build** (`Root=/var/snap/docker/...`), confined by AppArmor. It ran containers fine, but `docker stop`/`kill` on a *running* container returned `permission denied` — even as root. Exited containers could be removed, but long-running ones (device, router) could not be killed, so the runner couldn't tear down between cells. Fatal for a multi-cell sweep.

**Fix:** With admin approval, removed the snap (`sudo snap remove --purge docker`) and installed **Docker CE from the official apt repo**. Teardown works correctly on CE.

### 9. Docker CE default runtime broken (nvidia)
**Problem:** After install, `docker run` failed with `fork/exec /usr/bin/nvidia-container-runtime: no such file or directory`. The node is a GPU box; `/etc/docker/daemon.json` had `default-runtime: nvidia`, but that binary didn't survive the snap→apt migration. This also breaks `docker build` (RUN steps use the default runtime).

**Fix:** Set `default-runtime: runc` in `/etc/docker/daemon.json` (kept the `nvidia` runtime entry for later) and restarted Docker. K8s is unaffected (it uses containerd, not Docker). Admin to restore the nvidia default when they reinstall `nvidia-container-toolkit`.

### ⚠️ Side effect for the admin — containerd upgraded on a K8s node
Installing `docker-ce` pulled `containerd.io` **1.7.27 → 2.2.4** — the runtime Kubernetes uses on this node. The restart was *deferred*, so the running cluster was not disrupted, but **on the next containerd restart or node reboot, K8s will be on containerd 2.x**. Flagged to the admin to pin/verify compatibility before any reboot. (The cluster is a single-node, idle test cluster — only `kube-system` plus one `testns/testpod-stress` — so real-world blast radius is low, but etcd lives here.)

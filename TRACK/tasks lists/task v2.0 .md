# CAMPUS Benchmark — Task Tracker

## Day 2: Network Impairment (Netem)
- [x] Install `iproute2` in Dockerfiles (gRPC, Zenoh, MQTT)
- [x] Add `cap_add: [NET_ADMIN]` in `docker-compose.yml` files (gRPC, Zenoh, MQTT)
- [x] Write `scripts/inject_impairment.py` (integrated directly in `run_matrix.py`)
- [x] Verify network impairment via ping latency check (confirmed via RTT delay)

## Day 3: Unified Experiment Harness
- [x] Create `scripts/run_matrix.py` sweep runner
- [x] Implement docker-compose start/stop/scale logic in python runner
- [x] Implement netem profile selection inside the runner
- [x] Test-run a miniature benchmark slice (1 protocol, 1 profile, N=1, 5s duration)
- [x] Run full benchmark matrix (gRPC vs Zenoh vs MQTT) and gather CSV files

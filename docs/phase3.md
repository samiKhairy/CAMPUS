# Phase 3 Plan — Open5GS, ARM64, Physical 5G Lab

## Status going in
- Phase 1 & 2 benchmarking complete: 5 protocols, 360 runs, results in `results/unified/`
- Reports done: `sent-report.tex` (sent May 26), `report final.tex` (ready to send)
- Docker images on Docker Hub: `samiullahkhairy/campus-*`
- Git clean and pushed

---

## Immediate

- [ ] Compile `report final.tex` to PDF and send to Francesco and Filippo
  - Reference the May 26 report explicitly in the email
  - Subject: something like "CAMPUS Protocol Benchmark — Follow-up Results (QUIC + Scaling)"

---

## Week 1 — Open5GS + UERANSIM

**Goal: one UE registered and pinging through the GTP tunnel. No benchmark numbers.**

These results are workflow validation only. Never report them as 5G performance numbers.

- [ ] Fix `5g-testbed/`
  - Pick one compose file (currently two conflicting ones)
  - Write `mongo-init.js` for subscriber provisioning
  - Verify `gtp5g` and `sctp` kernel modules load on host (`modprobe gtp5g`, `modprobe sctp`)
- [ ] Bring up Open5GS core (AMF, SMF, UPF, MongoDB)
- [ ] Register one UE in MongoDB (IMSI, Ki, OPc, DNN)
- [ ] Bring up UERANSIM gNB + UE
- [ ] Confirm UE gets an IP via PDU session
- [ ] Run one protocol container on the UE side and ping the edge through the GTP tunnel

**Deliverable:** one UE registered, GTP tunnel up, one protocol (Zenoh) reachable through it.

**Keep notes as you go** — every command, every config file touched, every error hit. This becomes the deployment runbook for the Jetson Orins and for Torino.

---

## Week 2 — ARM64 Preparation (Jetson Orin)

**Goal: all Docker images build and run on ARM64 before the Orins arrive.**

- [ ] Check which third-party images have official ARM64 variants
  - `eclipse/zenoh` — check
  - `emqx/emqx` — check
  - `eclipse-mosquitto` — check
  - `eclipse/zenoh` for QUIC — check
- [ ] **Critical: rebuild MQTT-QUIC C binary for ARM64**
  - NanoSDK + MsQuic compiled from source — will not run on ARM64 without a rebuild
  - Option A: build natively on the Orin when it arrives
  - Option B: cross-compile on WSL2 using `--platform linux/arm64` with QEMU emulation
- [ ] Push ARM64 images to Docker Hub alongside x86 using multi-arch manifests
  - `docker buildx build --platform linux/amd64,linux/arm64 -t samiullahkhairy/campus-mqtt-quic-device:latest --push .`
- [ ] Test all images on Orin once it arrives (JetPack 5/6, ARM64)

---

## Week 3+ — Physical 5G Lab (Torino)

**Blocked on:** Torino VPN access and LINKS OBU JetPack version confirmation.

**Goal: validate protocol rankings on real radio, get KPI numbers for the paper.**

- [ ] Get Torino VPN access (chase Francesco for timeline)
- [ ] Confirm LINKS OBU JetPack version — targeting Xavier NX JetPack 4
- [ ] Run benchmark matrix on physical testbed
  - Minimum subset: clean + good_5g + degraded_5g at N=1, 5, 10, 20
  - Same protocols: gRPC, Zenoh-TCP, Zenoh-QUIC, MQTT-TCP, MQTT-QUIC
  - Same metrics: RTT p50/p95/p99, message loss
- [ ] Compare rankings against netem results from Phase 2
- [ ] Check KPI 1: uplink freshness ≤ 200ms on real radio
- [ ] Check KPI 2: E2E latency ≤ 300ms (uplink + processing + downlink)
- [ ] Document delta between netem simulation and real radio behavior

**This is where the paper numbers come from.**

---

## Open Questions — Chase These Now

These are not in your control but will block later phases if not resolved early.

| Question | Who | Why it matters |
|---|---|---|
| Perception message format and frequency from TEORESI/BME | Francesco | Determines payload size and rate for real benchmark |
| Geographic filtering: webhook callback or polling Device Location API | Filippo | Affects KPI 3 (relevance filtering) implementation |
| Torino testbed VPN access timeline | Francesco | Blocks Week 3+ entirely |
| LINKS OBU JetPack version — Xavier NX JetPack 4? | Francesco | Determines which base images work for ARM64 |

---

## Reference

- Results: `results/unified/`
- Figure scripts: `scripts/regenerate_figures.py`
- Experiment runner: `scripts/run_matrix.py`
- Docker images: `hub.docker.com/u/samiullahkhairy`
- Engineering notes: `docs/engineering-notes.md`
- Reports: `sent-report.tex` (v1, sent), `report final.tex` (v2, ready to send)

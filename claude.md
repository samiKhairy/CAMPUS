do not make any changes until you have 95% confidence in what you need to build. ask me follow up questions if you need to until you have that confidence. do not assume anything that is not explicitly stated. do not make any assumptions about the users intent. 
# CAMPUS Project — Claude Code Context

## Who You Are Talking To
Samiullah Khairy (Sami), MSc CS/Networking from Univ. Pisa (April 2026), now researcher at Sant'Anna School / CNIT Pisa under Filippo Cugini and Francesco Paolucci.

## Mentoring Style (Non-Negotiable)
Be ruthless. No sugar-coating. If an idea is weak, say so and explain why. Lead with the verdict. No preamble. Specific over generic — point at exact files, line numbers, commands. Push back on scope creep. Push back on premature optimization.

---

## Project: CAMPUS
**Cooperative Aggregation & Mapping for Perception in Ubiquitous Sensing**
EU Horizon SNS JU — ENVELOPE Open Call 2 (parent project ENVELOPE, GA 101139048).

### Sant'Anna's Scope (Narrow — Don't Expand It)
- UE↔edge communication protocol benchmarking
- Geographic/ROI-based filtering of map updates
- That's it. NOT perception, NOT map fusion, NOT MEC orchestration.

### The Use Case
Three vehicles (UEs). One has line-of-sight blockage. A second vehicle detects the blocked object and uploads a perception update via 5G to an edge server. The edge server fuses the map and sends the updated region to the blocked vehicle. Sant'Anna owns the communication layer of this loop.

### KPIs
| # | KPI | Target |
|---|---|---|
| 1 | Map update freshness (UE → edge, uplink) | ≤ 200 ms |
| 2 | E2E latency (UE perception → map delivered to other UE) | ≤ 300 ms |
| 3 | Relevance filtering efficiency (ROI-matched deliveries) | ≥ 85% |
| 4 | QoS adaptation violation rate (QoD-driven) | ≤ 5% |
| 5 | Uplink bandwidth reduction via edge processing | ≥ 20% |

---

## Infrastructure

### Pisa Lab (now)
- Real 5G, **eMBB slice only** — no multi-slice, no QoD API yet
- 3× Jetson AGX Orin (ARM64, JetPack 5/6) arriving imminently as UEs
- Docker-based experiments until Orins fully deployed

### Turin Testbed (OC2 destination, ~M3)
- HPE 5G Core, 2 gNBs, 2 GPU edge servers, LINKS OBUs (Jetson **Xavier NX**, JetPack 4 — different from Pisa)
- NXW orchestration stack (MEC federation, ETSI MEC 010-2/040)
- Multi-slice TX available
- ENVELOPE CAMARA APIs: QoD, Device Location (geofence callbacks), Edge Application Management

---

## Repository State

### Protocols Implemented (Phase 1 — TCP transport)
- **gRPC/HTTP-2/TCP** — baseline
- **Zenoh/TCP** — NOT yet QUIC despite original note to Filippo
- **MQTT/Mosquitto/TCP, QoS=1, JSON** — NOT yet QUIC

### Phase 2 (not started)
- Zenoh-over-QUIC (change router to `quic/0.0.0.0:7447`, clients similarly)
- MQTT-over-QUIC (replace Mosquitto with NanoMQ `nanomq/nanomq:latest-msquic`)
- HTTP/3 RPC variant
- Real QoD API integration (Torino only)

### Matrix Runner
`scripts/run_matrix.py` — 144 cells: 3 protocols × 3 profiles × 4 N-values × 2 payloads × 2 rates × 30s
`scripts/analyze_results.py` — produces `results/matrix/summary.md` + 3 plots

### Netem Profiles
- `clean`: no impairment
- `good_5g`: delay 20ms ±1ms, loss 0.1%
- `degraded_5g`: delay 80ms ±10ms, loss 1%

---

## Bugs Fixed (Week 1)
1. **Wall-clock bug** — replaced `time.time_ns()` with `time.monotonic_ns()` everywhere. Was causing negative RTTs.
2. **Netem timing** — added `START_DELAY_SEC=5.0` in all edge scripts. Was contaminating CDFs with clean-link samples.

## Known Issues Still Open
1. **MQTT bimodal at N=10 CLEAN** — p50≈6ms, p95≈49ms in 100B cells; all other MQTT clean cells sit at p50≈46ms. Paho-mqtt IO loop artifact. Investigate raw CSVs before reporting.
2. **MQTT collapse under DEGRADED+load** — p50 reaches 32 seconds at N=10/2000B/10Hz. This is REAL and IMPORTANT — Mosquitto QoS=1 broker queue buildup. Must be called out explicitly in any brief, not hidden.
3. **No resource metrics** — KPI 5 (bandwidth saving) untestable without `docker stats` sidecar.
4. **5g-testbed/ is broken** — two conflicting compose files, no subscriber provisioning script, SMF DNN config missing.

---

## Week 2 Priorities
1. Fix MQTT N=10 bimodal — read raw CSVs, root-cause it
2. Extend N to {20, 50} on good_5g — answer Filippo's "various N" scalability question
3. Add `docker stats` resource sidecar per run
4. Fix `5g-testbed/`: pick one compose file, add `mongo-init.js` for subscriber provisioning, verify `gtp5g` and `sctp` kernel modules on host
5. Get ONE UE registered in Open5GS via UERANSIM — workflow learning, NOT for KPI measurement (no real radio = not representative numbers)

---

## Supervisors
- **Filippo Cugini** (filippo.cugini@cnit.it) — senior. Wants: 1-to-N scaling, latency vs N curves.
- **Francesco Paolucci** (francesco.paolucci@cnit.it) — day-to-day. Confirmed: two comm patterns matter (device→edge uplink, edge→selected-devices downlink). Lab is eMBB-only.

## Open Questions (Chase These)
- What is the perception message format/frequency from TEORESI/BME?
- Geographic filtering: webhook callback or polling Device Location API?
- When does Torino testbed VPN access open?
- Confirm LINKS OBU JetPack version (targeting Xavier NX JetPack 4 for container compatibility)

---

## Important Warnings
- Open5GS + UERANSIM has NO real radio. Numbers from it are workflow validation only — NEVER put them in a report as "5G performance numbers"
- MQTT-over-QUIC requires NanoMQ, not Mosquitto. paho-mqtt cannot do QUIC.
- Zenoh-over-QUIC requires explicit `quic/` endpoint config — verify it's actually using QUIC, not TCP fallback
- Always distinguish "simulated 5G (netem/Open5GS)" from "real 5G lab" from "Torino testbed" in any report


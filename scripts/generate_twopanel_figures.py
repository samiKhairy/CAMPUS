"""
Regenerate latency_vs_N.png and profile_comparison.png with two-panel layouts.
Left panel: all 5 protocols (context — shows MQTT/TCP scale).
Right panel: 4 protocols only, no MQTT TCP (comparison — shows real differences).
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

BASE = os.path.join(os.path.dirname(__file__), '..', 'results', 'unified')

PROTOCOLS   = ['grpc', 'mqtt', 'mqtt-quic', 'zenoh', 'zenoh-quic']
LABELS      = ['gRPC', 'MQTT (TCP)', 'MQTT-QUIC', 'Zenoh (TCP)', 'Zenoh-QUIC']
COLORS      = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
MARKERS     = ['o', 's', '^', 'D', 'v']

# Protocols shown on the right (zoom) panel — MQTT TCP excluded
ZOOM_PROTOS = ['grpc', 'mqtt-quic', 'zenoh', 'zenoh-quic']

plt.style.use('seaborn-v0_8-whitegrid'
               if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')


def load_p95(protocol, profile, n, payload='100', rate='10'):
    path = os.path.join(BASE, protocol, profile,
                        f'N_{n}_pay_{payload}_rate_{rate}.csv')
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    if df.empty or len(df) < 5:
        return None
    return float(np.percentile(df['latency_ms'].values, 95))


# ── Figure 1: p95 Latency vs N  (good_5g, 100B, 10Hz) ───────────────────────

NS_ALL  = [1, 2, 5, 10, 20, 50]
NS_ZOOM = [1, 2, 5, 10, 20]

fig = plt.figure(figsize=(14, 5))
gs  = gridspec.GridSpec(1, 2, figure=fig, wspace=0.35)
ax_left  = fig.add_subplot(gs[0])
ax_right = fig.add_subplot(gs[1])

for proto, label, color, marker in zip(PROTOCOLS, LABELS, COLORS, MARKERS):
    # Left panel — all protocols, all N
    xs, ys = [], []
    for n in NS_ALL:
        v = load_p95(proto, 'good_5g', n)
        if v is not None:
            xs.append(n)
            ys.append(v)
    if xs:
        ax_left.plot(xs, ys, marker=marker, linewidth=2, markersize=6,
                     label=label, color=color)

    # Right panel — zoom, skip MQTT TCP
    if proto == 'mqtt':
        continue
    xs, ys = [], []
    for n in NS_ZOOM:
        v = load_p95(proto, 'good_5g', n)
        if v is not None:
            xs.append(n)
            ys.append(v)
    if xs:
        ax_right.plot(xs, ys, marker=marker, linewidth=2, markersize=6,
                      label=label, color=color)

ax_left.set_title('All 5 protocols', fontsize=11, fontweight='bold')
ax_left.set_xlabel('Number of Devices (N)', fontsize=10)
ax_left.set_ylabel('p95 RTT Latency (ms)', fontsize=10)
ax_left.set_xticks(NS_ALL)
ax_left.legend(fontsize=8.5)
ax_left.annotate('MQTT (TCP)\ncollapses at N=50\n(p95 ≈ 14,600 ms)',
                 xy=(50, load_p95('mqtt', 'good_5g', 50) or 14600),
                 xytext=(30, 10000),
                 fontsize=8, color='#ff7f0e',
                 arrowprops=dict(arrowstyle='->', color='#ff7f0e', lw=0.9))

ax_right.set_title('Zoom: gRPC, Zenoh, Zenoh-QUIC, MQTT-QUIC', fontsize=11, fontweight='bold')
ax_right.set_xlabel('Number of Devices (N)', fontsize=10)
ax_right.set_ylabel('p95 RTT Latency (ms)', fontsize=10)
ax_right.set_xticks(NS_ZOOM)
ax_right.set_ylim(0, 150)
ax_right.legend(fontsize=8.5)

fig.suptitle('p95 Latency vs Device Count — Normal 5G (100 B, 10 Hz)',
             fontsize=13, fontweight='bold', y=1.01)
plt.tight_layout()
out1 = os.path.join(BASE, 'latency_vs_N.png')
plt.savefig(out1, dpi=150, bbox_inches='tight')
plt.close()
print(f'Saved: {out1}')


# ── Figure 2: p95 across Network Profiles  (N=2, 100B, 10Hz) ────────────────

PROFILES       = ['clean', 'good_5g', 'degraded_5g']
PROFILE_LABELS = ['Clean', 'Good 5G', 'Degraded 5G']

fig = plt.figure(figsize=(14, 5))
gs  = gridspec.GridSpec(1, 2, figure=fig, wspace=0.35)
ax_left  = fig.add_subplot(gs[0])
ax_right = fig.add_subplot(gs[1])

x      = np.arange(len(PROFILES))
n_all  = len(PROTOCOLS)
n_zoom = len(ZOOM_PROTOS)
w      = 0.15

# Left panel — all 5 protocols
for i, (proto, label, color) in enumerate(zip(PROTOCOLS, LABELS, COLORS)):
    vals = [load_p95(proto, prof, n=2) or 0 for prof in PROFILES]
    offset = (i - n_all / 2 + 0.5) * w
    ax_left.bar(x + offset, vals, w, label=label, color=color, alpha=0.85)

ax_left.set_title('All 5 protocols', fontsize=11, fontweight='bold')
ax_left.set_xlabel('Network Profile', fontsize=10)
ax_left.set_ylabel('p95 Latency (ms)', fontsize=10)
ax_left.set_xticks(x)
ax_left.set_xticklabels(PROFILE_LABELS)
ax_left.legend(fontsize=8.5)

# Right panel — zoom (no MQTT TCP)
zoom_colors = [COLORS[i] for i, p in enumerate(PROTOCOLS) if p in ZOOM_PROTOS]
zoom_labels = [LABELS[i] for i, p in enumerate(PROTOCOLS) if p in ZOOM_PROTOS]

for i, (proto, label, color) in enumerate(zip(ZOOM_PROTOS, zoom_labels, zoom_colors)):
    vals = [load_p95(proto, prof, n=2) or 0 for prof in PROFILES]
    offset = (i - n_zoom / 2 + 0.5) * w
    ax_right.bar(x + offset, vals, w, label=label, color=color, alpha=0.85)

ax_right.set_title('Zoom: gRPC, Zenoh, Zenoh-QUIC, MQTT-QUIC', fontsize=11, fontweight='bold')
ax_right.set_xlabel('Network Profile', fontsize=10)
ax_right.set_ylabel('p95 Latency (ms)', fontsize=10)
ax_right.set_xticks(x)
ax_right.set_xticklabels(PROFILE_LABELS)
ax_right.legend(fontsize=8.5)

fig.suptitle('p95 Latency Across Network Profiles — N=2, 100 B, 10 Hz',
             fontsize=13, fontweight='bold', y=1.01)
plt.tight_layout()
out2 = os.path.join(BASE, 'profile_comparison.png')
plt.savefig(out2, dpi=150, bbox_inches='tight')
plt.close()
print(f'Saved: {out2}')

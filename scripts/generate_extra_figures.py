"""
Generate two additional figures for the consolidated CAMPUS report:
  1. degraded_latency_vs_N.png  — p50 RTT vs N for all 5 protocols under degraded 5G
  2. mqtt_quic_rescue.png        — MQTT TCP vs MQTT-QUIC under degraded 5G (the rescue story)
"""

import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

BASE = os.path.join(os.path.dirname(__file__), '..', 'results', 'unified')
OUT  = os.path.join(os.path.dirname(__file__), '..', 'results', 'unified')

PROTOCOLS = ['grpc', 'mqtt', 'mqtt-quic', 'zenoh', 'zenoh-quic']
LABELS    = ['gRPC', 'MQTT (TCP)', 'MQTT-QUIC', 'Zenoh (TCP)', 'Zenoh-QUIC']
COLORS    = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']

NS = [1, 2, 5, 10, 20]


def load_p50(protocol, profile, n, payload='100', rate='10'):
    path = os.path.join(BASE, protocol, profile,
                        f'N_{n}_pay_{payload}_rate_{rate}.csv')
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    return df['latency_ms'].median()


# ── Figure 1: Degraded latency vs N (log-scale y so MQTT collapse is visible) ──

fig, ax = plt.subplots(figsize=(10, 6))

for proto, label, color in zip(PROTOCOLS, LABELS, COLORS):
    xs, ys = [], []
    for n in NS:
        v = load_p50(proto, 'degraded_5g', n)
        if v is not None:
            xs.append(n)
            ys.append(v)
    if xs:
        ax.plot(xs, ys, marker='o', linewidth=2, markersize=6,
                label=label, color=color)

# Annotate the MQTT collapse values at N=5 and N=10
mqtt_annotations = {5: '~14.8 s', 10: '~38.8 s'}
for n, txt in mqtt_annotations.items():
    v = load_p50('mqtt', 'degraded_5g', n)
    if v is not None:
        ax.annotate(txt, xy=(n, v), xytext=(n + 0.6, v * 0.5),
                    fontsize=8, color='#ff7f0e',
                    arrowprops=dict(arrowstyle='->', color='#ff7f0e', lw=0.8))

ax.set_yscale('log')
ax.yaxis.set_major_formatter(ticker.FuncFormatter(
    lambda x, _: f'{x/1000:.0f} s' if x >= 1000 else f'{x:.0f} ms'))
ax.set_xlabel('Number of Devices (N)', fontsize=12)
ax.set_ylabel('Median RTT (p50)', fontsize=12)
ax.set_title('Median Latency vs Device Count\n(Degraded 5G — 80 ms delay, 1% loss — 100 B, 10 Hz)',
             fontsize=13)
ax.set_xticks(NS)
ax.legend(fontsize=10)
ax.grid(True, which='both', linestyle='--', alpha=0.4)
plt.tight_layout()
out1 = os.path.join(OUT, 'degraded_latency_vs_N.png')
plt.savefig(out1, dpi=150)
plt.close()
print(f'Saved: {out1}')


# ── Figure 2: MQTT-TCP vs MQTT-QUIC rescue (degraded, 100B, 10Hz) ──

rescue_ns = [1, 2, 5, 10, 20]
mqtt_vals  = [load_p50('mqtt',      'degraded_5g', n) for n in rescue_ns]
quic_vals  = [load_p50('mqtt-quic', 'degraded_5g', n) for n in rescue_ns]

x = np.arange(len(rescue_ns))
width = 0.35

fig, ax = plt.subplots(figsize=(10, 6))

bars_tcp  = ax.bar(x - width/2, mqtt_vals,  width, label='MQTT (TCP / Mosquitto)',
                   color='#ff7f0e', alpha=0.85)
bars_quic = ax.bar(x + width/2, quic_vals, width, label='MQTT-QUIC (NanoMQ)',
                   color='#2ca02c', alpha=0.85)

# Value labels on QUIC bars (they are always readable)
for bar in bars_quic:
    h = bar.get_height()
    ax.text(bar.get_x() + bar.get_width() / 2, h + 50,
            f'{h:.0f} ms', ha='center', va='bottom', fontsize=8, color='#2ca02c')

# Value labels on TCP bars — only where they fit; log scale annotation for large ones
tcp_labels = {0: f'{mqtt_vals[0]:.0f} ms',
              1: f'{mqtt_vals[1]:.0f} ms',
              2: '14,815 ms\n(14.8 s)',
              3: '2,420 ms\n(2.4 s)',
              4: '19,924 ms\n(19.9 s)'}
for i, bar in enumerate(bars_tcp):
    label = tcp_labels.get(i, '')
    ax.text(bar.get_x() + bar.get_width() / 2,
            min(bar.get_height(), 700) + 50,
            label, ha='center', va='bottom', fontsize=7.5, color='#ff7f0e')

ax.set_yscale('log')
ax.yaxis.set_major_formatter(ticker.FuncFormatter(
    lambda x, _: f'{x/1000:.0f} s' if x >= 1000 else f'{x:.0f} ms'))
ax.set_xlabel('Number of Devices (N)', fontsize=12)
ax.set_ylabel('Median RTT (p50, log scale)', fontsize=12)
ax.set_title('MQTT over TCP vs MQTT over QUIC — Degraded 5G\n'
             'QUIC eliminates broker queue collapse (100 B, 10 Hz)',
             fontsize=13)
ax.set_xticks(x)
ax.set_xticklabels([f'N={n}' for n in rescue_ns])
ax.legend(fontsize=10)
ax.grid(True, which='both', linestyle='--', alpha=0.4)
plt.tight_layout()
out2 = os.path.join(OUT, 'mqtt_quic_rescue.png')
plt.savefig(out2, dpi=150)
plt.close()
print(f'Saved: {out2}')

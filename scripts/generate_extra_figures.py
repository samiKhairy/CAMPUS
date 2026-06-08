"""
Generate two additional figures for the consolidated CAMPUS report:
  1. degraded_latency_vs_N.png  — p50 RTT vs N for all 5 protocols under degraded 5G
  2. mqtt_quic_rescue.png        — MQTT TCP vs MQTT-QUIC under degraded 5G (the rescue story)
"""

import os
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

# --output-base lets the same script target different result sets (e.g. the
# host run in results/unified vs a server sweep in results/server-run). Path is
# resolved relative to the repo root, matching analyze_results.py / run_matrix.py.
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_parser = argparse.ArgumentParser()
_parser.add_argument('--output-base', default='results/unified',
                     help='Base directory where results are stored (relative to repo root)')
_args, _ = _parser.parse_known_args()
BASE = os.path.join(_root, _args.output_base)
OUT  = BASE

PROTOCOLS = ['grpc', 'mqtt', 'mqtt-quic', 'zenoh', 'zenoh-quic', 'dds']
LABELS    = ['gRPC', 'MQTT (TCP)', 'MQTT-QUIC', 'Zenoh (TCP)', 'Zenoh-QUIC', 'DDS (RTPS)']
COLORS    = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']

NS = [1, 2, 5, 10, 20, 50]


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

def _fmt_ms(v):
    """Format a latency in ms as '~X.X s' above 1000 ms, else '~X ms'."""
    return f'~{v/1000:.1f} s' if v >= 1000 else f'~{v:.0f} ms'

# Annotate the MQTT collapse where it actually happens at this payload (100 B):
# the line stays near the floor through N=5, then climbs at N=10 and N=20.
# Values are read from the plotted data so the labels can never drift from it.
for n in (10, 20):
    v = load_p50('mqtt', 'degraded_5g', n)
    if v is not None:
        ax.annotate(_fmt_ms(v), xy=(n, v), xytext=(n - 3.2, v * 1.9),
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

# Value labels above every bar, computed from the plotted height so they always
# match the data. On a log scale, multiplying by 1.18 places the text just above
# each bar top (a fixed additive offset would land inside the tall bars).
def _bar_label(v):
    return f'{v/1000:.1f} s' if v >= 1000 else f'{v:.0f} ms'

for bar in bars_quic:
    h = bar.get_height()
    if h and h > 0:
        ax.text(bar.get_x() + bar.get_width() / 2, h * 1.18,
                _bar_label(h), ha='center', va='bottom', fontsize=8, color='#2ca02c')

for bar in bars_tcp:
    h = bar.get_height()
    if h and h > 0:
        ax.text(bar.get_x() + bar.get_width() / 2, h * 1.18,
                _bar_label(h), ha='center', va='bottom', fontsize=7.5, color='#ff7f0e')

ax.set_yscale('log')
# Headroom above the tallest bar so its label is not clipped at the axes top.
_tcp_max = max((v for v in mqtt_vals if v), default=1000)
ax.set_ylim(100, _tcp_max * 3)
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

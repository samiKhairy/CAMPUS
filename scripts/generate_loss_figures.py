#!/usr/bin/env python3
"""
Generate a two-panel figure showing Packet Loss % vs Device Count (N)
for all 6 protocols under Normal 5G (left) and Degraded 5G (right).

Usage:
    python scripts/generate_loss_figures.py --output-base results/server-run
"""

import os
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

# Resolve base paths
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_parser = argparse.ArgumentParser()
_parser.add_argument('--output-base', default='results/unified',
                     help='Base directory where results are stored (relative to repo root)')
args = _parser.parse_args()

BASE = os.path.join(_root, args.output_base)

# Define protocol configuration (matching colors/markers of generate_twopanel_figures.py)
PROTOCOLS = ['grpc', 'mqtt', 'mqtt-quic', 'zenoh', 'zenoh-quic', 'dds']
LABELS    = ['gRPC', 'MQTT (TCP)', 'MQTT-QUIC', 'Zenoh (TCP)', 'Zenoh-QUIC', 'DDS (RTPS)']
COLORS    = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
MARKERS   = ['o', 's', '^', 'D', 'v', 'p']

NS = [1, 2, 5, 10, 20, 50]
PROFILES = ['good_5g', 'degraded_5g']
PROFILE_LABELS = ['Normal 5G (0.1% random loss)', 'Degraded 5G (1.0% random loss)']

plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')

def load_loss(protocol, profile, n, payload='100', rate='10'):
    # Since we need to estimate packet loss as in analyze_results.py
    path = os.path.join(BASE, protocol, profile, f'N_{n}_pay_{payload}_rate_{rate}.csv')
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path)
        n_rec = len(df)
        
        # Base duration in seconds
        duration_s = 30.0
        if n_rec > 1:
            ts_diff = (df["send_ts_ns"].max() - df["send_ts_ns"].min()) / 1e9
            if ts_diff > 1.0:
                duration_s = ts_diff + (1.0 / float(rate))
                
        # If the inferred duration collapses due to connection/discovery failure,
        # fall back to the intended 30s run length.
        if duration_s < 28.0:
            duration_s = 30.0
                
        expected_packets = n * int(rate) * duration_s
        lost_packets = max(0, expected_packets - n_rec)
        loss_pct = (lost_packets / expected_packets) * 100 if expected_packets > 0 else 0.0
        return loss_pct
    except Exception as e:
        print(f"[WARNING] Failed loading loss for {protocol}/{profile}/N_{n}: {e}")
        return None

def main():
    fig = plt.figure(figsize=(14, 5.5))
    gs  = gridspec.GridSpec(1, 2, figure=fig, wspace=0.3)
    ax_normal = fig.add_subplot(gs[0])
    ax_degraded = fig.add_subplot(gs[1])
    
    axes = [ax_normal, ax_degraded]
    
    for idx, profile in enumerate(PROFILES):
        ax = axes[idx]
        ax.set_title(PROFILE_LABELS[idx], fontsize=11, fontweight='bold', pad=10)
        
        for proto, label, color, marker in zip(PROTOCOLS, LABELS, COLORS, MARKERS):
            xs, ys = [], []
            for n in NS:
                loss = load_loss(proto, profile, n)
                if loss is not None:
                    xs.append(n)
                    ys.append(loss)
            if xs:
                ax.plot(xs, ys, marker=marker, linewidth=2, markersize=6,
                        label=label, color=color)
                
        ax.set_xlabel('Number of Devices (N)', fontsize=10)
        ax.set_ylabel('E2E Packet Loss %', fontsize=10)
        ax.set_xticks(NS)
        ax.set_ylim(-2, 105)
        ax.legend(fontsize=9, frameon=True, loc='upper left')
        ax.grid(True, which='both', linestyle='--', alpha=0.4)
        
        # Add interesting annotations
        if profile == 'good_5g':
            ax.annotate('gRPC Stream\nExhaustion (80%)', xy=(50, 80), xytext=(28, 65),
                        fontsize=8.5, color='#1f77b4', fontweight='bold',
                        arrowprops=dict(arrowstyle='->', color='#1f77b4', lw=0.9))
            ax.annotate('DDS Multicast\nDrops (99.6% discovery fail)', xy=(50, 99.6), xytext=(24, 85),
                        fontsize=8.5, color='#8c564b', fontweight='bold',
                        arrowprops=dict(arrowstyle='->', color='#8c564b', lw=0.9))
        elif profile == 'degraded_5g':
            ax.annotate('gRPC Cliff (50% loss)', xy=(20, 50.2), xytext=(3, 58),
                        fontsize=8.5, color='#1f77b4', fontweight='bold',
                        arrowprops=dict(arrowstyle='->', color='#1f77b4', lw=0.9))
            ax.annotate('MQTT-QUIC\nCongestion Drops (44.5%)', xy=(50, 44.5), xytext=(22, 28),
                        fontsize=8.5, color='#2ca02c', fontweight='bold',
                        arrowprops=dict(arrowstyle='->', color='#2ca02c', lw=0.9))
            ax.annotate('DDS & Zenoh UDP\nSocket Buffer Drops (~40%)', xy=(50, 40.5), xytext=(22, 53),
                        fontsize=8.5, color='#8c564b', fontweight='bold',
                        arrowprops=dict(arrowstyle='->', color='#8c564b', lw=0.9))

    fig.suptitle('End-to-End Packet Loss % vs Device Count — payload=100 B, rate=10 Hz',
                 fontsize=13, fontweight='bold', y=1.01)
    
    out_file = os.path.join(BASE, 'loss_vs_N.png')
    plt.tight_layout()
    plt.savefig(out_file, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: {out_file}")

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Generate a grouped bar chart comparing all 5 protocols at N=20, 100B, 10Hz
across all three network profiles. Shows p50 (median) with p95 error bars.
"""
import matplotlib.pyplot as plt
import matplotlib
import numpy as np

matplotlib.rcParams['font.family'] = 'sans-serif'
matplotlib.rcParams['font.size'] = 11

# ── Data at N=20, 100B, 10Hz ──────────────────────────────────────────────
# Order: Zenoh-QUIC, Zenoh, MQTT-QUIC, gRPC, MQTT (TCP)
protocols = ['Zenoh-QUIC', 'Zenoh\n(TCP)', 'MQTT-QUIC', 'gRPC', 'MQTT\n(TCP)']
colors    = ['#8B5CF6',    '#EF4444',   '#22C55E',    '#3B82F6', '#F97316']

# p50 values (ms)
clean_p50      = [3.16,   3.33,   6.45,    6.07,   9.21]
good_p50       = [41.07,  41.62,  44.77,   42.67,  51.78]
degraded_p50   = [161.00, 161.96, 183.33,  162.32, 19923.98]

# p95 values (ms) - for error bars
clean_p95      = [4.57,   4.67,   11.64,   13.74,  12.86]
good_p95       = [43.81,  44.40,  51.94,   45.79,  84.05]
degraded_p95   = [228.49, 251.96, 249.46,  235.77, 37761.33]

# Loss %
clean_loss     = [1.2,  1.2,  0.3,  56.9, 4.1]
good_loss      = [0.7,  1.0,  0.3,  55.0, 2.8]
degraded_loss  = [0.6,  0.9,  0.3,  53.7, 1.3]

# ── Figure: Two-panel layout ─────────────────────────────────────────────
fig, axes = plt.subplots(1, 3, figsize=(18, 7), gridspec_kw={'width_ratios': [1, 1, 1]})
fig.suptitle('Protocol Comparison at N = 20 Devices  —  100 B, 10 Hz',
             fontsize=16, fontweight='bold', y=0.98)

profiles = ['Clean (LAN)', 'Good 5G\n(40 ms floor, 0.1% loss)', 'Degraded 5G\n(160 ms floor, 1% loss)']
p50_data = [clean_p50, good_p50, degraded_p50]
p95_data = [clean_p95, good_p95, degraded_p95]
loss_data = [clean_loss, good_loss, degraded_loss]

x = np.arange(len(protocols))
bar_width = 0.6

for idx, ax in enumerate(axes):
    p50 = p50_data[idx]
    p95 = p95_data[idx]
    loss = loss_data[idx]
    
    # Error bars: from p50 up to p95
    yerr_low = [0] * len(p50)
    yerr_high = [p95[i] - p50[i] for i in range(len(p50))]
    
    bars = ax.bar(x, p50, bar_width, color=colors, edgecolor='white', linewidth=0.5,
                  yerr=[yerr_low, yerr_high], capsize=5, 
                  error_kw={'elinewidth': 1.5, 'capthick': 1.5, 'color': '#374151'})
    
    # Annotate bars with p50 value and loss %
    for i, (bar, val, l) in enumerate(zip(bars, p50, loss)):
        # Format the value
        if val >= 1000:
            label = f'{val/1000:.1f} s'
        else:
            label = f'{val:.1f} ms'
        
        # Place label above bar or above error bar
        top = max(val, p95[i])
        
        # For the degraded MQTT bar, use log scale so we need special handling
        if idx == 2 and val > 1000:
            ax.text(bar.get_x() + bar.get_width()/2, top * 1.25,
                    f'{label}\n({l}% loss)', ha='center', va='bottom',
                    fontsize=9, fontweight='bold', color='#DC2626')
        elif idx == 2:
            # Degraded panel, log scale
            ax.text(bar.get_x() + bar.get_width()/2, top * 1.12,
                    f'{label}', ha='center', va='bottom',
                    fontsize=9, fontweight='bold')
            if l > 5:
                ax.text(bar.get_x() + bar.get_width()/2, val * 0.75,
                        f'{l}% loss', ha='center', va='top',
                        fontsize=7.5, color='#DC2626', fontweight='bold')
        else:
            offset = top * 0.06 + 2
            ax.text(bar.get_x() + bar.get_width()/2, top + offset,
                    f'{label}', ha='center', va='bottom',
                    fontsize=9, fontweight='bold')
            # Loss annotation inside the bar for high-loss protocols
            if l > 5:
                ax.text(bar.get_x() + bar.get_width()/2, val * 0.5,
                        f'{l}%\nloss', ha='center', va='center',
                        fontsize=7.5, color='white', fontweight='bold')
    
    ax.set_title(profiles[idx], fontsize=12, fontweight='bold', pad=10)
    ax.set_xticks(x)
    ax.set_xticklabels(protocols, fontsize=9.5)
    ax.set_ylabel('Median RTT  (p50, ms)' if idx == 0 else '', fontsize=11)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    
    # Use log scale for degraded panel (MQTT TCP is 20 seconds vs 160ms)
    if idx == 2:
        ax.set_yscale('log')
        ax.set_ylim(80, 100000)
        ax.set_ylabel('Median RTT  (p50, log scale)', fontsize=11)
    elif idx == 1:
        ax.set_ylim(0, 100)
    
    # Add a subtle annotation for the p95 error bars
    if idx == 0:
        ax.annotate('↑ p95', xy=(0.98, 0.95), xycoords='axes fraction',
                    ha='right', va='top', fontsize=8, color='#6B7280', fontstyle='italic')

# Add a note about error bars
fig.text(0.5, 0.01, 'Error bars show p95 tail latency.  gRPC drops 53–57% of messages at N=20 (HTTP/2 stream exhaustion).',
         ha='center', fontsize=9.5, color='#6B7280', fontstyle='italic')

plt.tight_layout(rect=[0, 0.04, 1, 0.95])
plt.savefig('results/unified/protocol_comparison_N20.png', dpi=150, bbox_inches='tight',
            facecolor='white', edgecolor='none')
plt.close()
print("Saved: results/unified/protocol_comparison_N20.png")

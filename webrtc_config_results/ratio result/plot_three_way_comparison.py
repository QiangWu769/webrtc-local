#!/usr/bin/env python3
"""
Three-way comparison plot: GCC vs Old Ratio vs New Ratio
"""

import numpy as np
import matplotlib.pyplot as plt
import re

def load_rtt_from_webrtc_log(filename):
    """Extract RTT values from WebRTC log file"""
    rtt_values = []
    with open(filename, 'r') as file:
        for line in file:
            rtt_match = re.search(r'\[RttBWE-Update\].*PropagationRtt:\s*(\d+)\s*ms', line)
            if rtt_match:
                rtt = int(rtt_match.group(1))
                if rtt > 0:
                    rtt_values.append(rtt)
    return np.array(rtt_values)

def load_thr_from_webrtc_log(filename):
    """Extract bandwidth values from WebRTC log file"""
    thr_values = []
    with open(filename, 'r') as file:
        for line in file:
            bw_match = re.search(r'\[BWE-ConstraintApply\].*Final:\s*(\d+)\s*bps', line)
            if bw_match:
                bitrate_bps = int(bw_match.group(1))
                bitrate_mbps = bitrate_bps / 1e6
                thr_values.append(bitrate_mbps)
    return np.array(thr_values)

# Define log file groups
gcc_logs = ['gcc12.8home2sender_local.log']
old_ratio_logs = ['ratio12.8home1sender_local.log', 'ratio12.8home2sender_local.log', 'ratio12.8home4sender_local.log']
new_ratio_logs = ['ratio12.10home3sender_local.log']

# Load and combine data
def load_group_data(logs):
    all_rtt = []
    all_bw = []
    for log in logs:
        rtt = load_rtt_from_webrtc_log(log)
        bw = load_thr_from_webrtc_log(log)
        all_rtt.extend(rtt)
        all_bw.extend(bw)
    return np.array(all_rtt), np.array(all_bw)

gcc_rtt, gcc_bw = load_group_data(gcc_logs)
old_ratio_rtt, old_ratio_bw = load_group_data(old_ratio_logs)
new_ratio_rtt, new_ratio_bw = load_group_data(new_ratio_logs)

# Calculate percentiles
def calc_percentiles(data):
    return {
        'P50': np.percentile(data, 50),
        'P90': np.percentile(data, 90),
        'P99': np.percentile(data, 99)
    }

gcc_rtt_p = calc_percentiles(gcc_rtt)
gcc_bw_p = calc_percentiles(gcc_bw)
old_ratio_rtt_p = calc_percentiles(old_ratio_rtt)
old_ratio_bw_p = calc_percentiles(old_ratio_bw)
new_ratio_rtt_p = calc_percentiles(new_ratio_rtt)
new_ratio_bw_p = calc_percentiles(new_ratio_bw)

# Create figure with subplots
fig, axes = plt.subplots(1, 3, figsize=(15, 5))

# Colors
colors = {'GCC': '#1f77b4', 'Old Ratio': '#ff7f0e', 'New Ratio': '#2ca02c'}

# Plot 1: RTT Percentile Comparison (Bar Chart)
ax1 = axes[0]
x = np.arange(3)
width = 0.25
percentiles = ['P50', 'P90', 'P99']

rtt_gcc = [gcc_rtt_p['P50'], gcc_rtt_p['P90'], gcc_rtt_p['P99']]
rtt_old = [old_ratio_rtt_p['P50'], old_ratio_rtt_p['P90'], old_ratio_rtt_p['P99']]
rtt_new = [new_ratio_rtt_p['P50'], new_ratio_rtt_p['P90'], new_ratio_rtt_p['P99']]

bars1 = ax1.bar(x - width, rtt_gcc, width, label='GCC', color=colors['GCC'])
bars2 = ax1.bar(x, rtt_old, width, label='Old Ratio', color=colors['Old Ratio'])
bars3 = ax1.bar(x + width, rtt_new, width, label='New Ratio', color=colors['New Ratio'])

ax1.set_ylabel('RTT (ms)')
ax1.set_title('RTT Percentile Comparison')
ax1.set_xticks(x)
ax1.set_xticklabels(percentiles)
ax1.legend()
ax1.grid(axis='y', alpha=0.3)

# Add value labels on bars
for bars in [bars1, bars2, bars3]:
    for bar in bars:
        height = bar.get_height()
        ax1.annotate(f'{height:.0f}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=8)

# Plot 2: Bandwidth Percentile Comparison (Bar Chart)
ax2 = axes[1]

bw_gcc = [gcc_bw_p['P50'], gcc_bw_p['P90'], gcc_bw_p['P99']]
bw_old = [old_ratio_bw_p['P50'], old_ratio_bw_p['P90'], old_ratio_bw_p['P99']]
bw_new = [new_ratio_bw_p['P50'], new_ratio_bw_p['P90'], new_ratio_bw_p['P99']]

bars1 = ax2.bar(x - width, bw_gcc, width, label='GCC', color=colors['GCC'])
bars2 = ax2.bar(x, bw_old, width, label='Old Ratio', color=colors['Old Ratio'])
bars3 = ax2.bar(x + width, bw_new, width, label='New Ratio', color=colors['New Ratio'])

ax2.set_ylabel('Bandwidth (Mbps)')
ax2.set_title('Bandwidth Percentile Comparison')
ax2.set_xticks(x)
ax2.set_xticklabels(percentiles)
ax2.legend()
ax2.grid(axis='y', alpha=0.3)

# Add value labels on bars
for bars in [bars1, bars2, bars3]:
    for bar in bars:
        height = bar.get_height()
        ax2.annotate(f'{height:.1f}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=8)

# Plot 3: RTT vs Bandwidth Tradeoff (Scatter Plot)
ax3 = axes[2]

# Plot median points with error bars showing P50 to P99 range
ax3.errorbar(gcc_rtt_p['P50'], gcc_bw_p['P50'],
             xerr=[[0], [gcc_rtt_p['P99'] - gcc_rtt_p['P50']]],
             yerr=[[0], [gcc_bw_p['P99'] - gcc_bw_p['P50']]],
             fmt='o', markersize=12, capsize=5, color=colors['GCC'], label='GCC')
ax3.errorbar(old_ratio_rtt_p['P50'], old_ratio_bw_p['P50'],
             xerr=[[0], [old_ratio_rtt_p['P99'] - old_ratio_rtt_p['P50']]],
             yerr=[[0], [old_ratio_bw_p['P99'] - old_ratio_bw_p['P50']]],
             fmt='s', markersize=12, capsize=5, color=colors['Old Ratio'], label='Old Ratio')
ax3.errorbar(new_ratio_rtt_p['P50'], new_ratio_bw_p['P50'],
             xerr=[[0], [new_ratio_rtt_p['P99'] - new_ratio_rtt_p['P50']]],
             yerr=[[0], [new_ratio_bw_p['P99'] - new_ratio_bw_p['P50']]],
             fmt='^', markersize=12, capsize=5, color=colors['New Ratio'], label='New Ratio')

ax3.set_xlabel('RTT P50 (ms)')
ax3.set_ylabel('Bandwidth P50 (Mbps)')
ax3.set_title('RTT-Bandwidth Tradeoff\n(error bars: P50 to P99)')
ax3.legend()
ax3.grid(alpha=0.3)

# Add arrow showing improvement direction
ax3.annotate('', xy=(new_ratio_rtt_p['P50'], new_ratio_bw_p['P50']),
             xytext=(gcc_rtt_p['P50'], gcc_bw_p['P50']),
             arrowprops=dict(arrowstyle='->', color='gray', lw=1.5, ls='--'))

plt.tight_layout()
plt.savefig('three_way_comparison.pdf', bbox_inches='tight', dpi=300)
plt.savefig('three_way_comparison.png', bbox_inches='tight', dpi=300)
print("Saved: three_way_comparison.pdf and three_way_comparison.png")

# Print summary table
print("\n" + "="*70)
print("THREE-WAY COMPARISON SUMMARY")
print("="*70)
print(f"{'Metric':<20} {'GCC':>12} {'Old Ratio':>12} {'New Ratio':>12}")
print("-"*70)
print(f"{'RTT P50 (ms)':<20} {gcc_rtt_p['P50']:>12.1f} {old_ratio_rtt_p['P50']:>12.1f} {new_ratio_rtt_p['P50']:>12.1f}")
print(f"{'RTT P90 (ms)':<20} {gcc_rtt_p['P90']:>12.1f} {old_ratio_rtt_p['P90']:>12.1f} {new_ratio_rtt_p['P90']:>12.1f}")
print(f"{'RTT P99 (ms)':<20} {gcc_rtt_p['P99']:>12.1f} {old_ratio_rtt_p['P99']:>12.1f} {new_ratio_rtt_p['P99']:>12.1f}")
print("-"*70)
print(f"{'Bandwidth P50 (Mbps)':<20} {gcc_bw_p['P50']:>12.2f} {old_ratio_bw_p['P50']:>12.2f} {new_ratio_bw_p['P50']:>12.2f}")
print(f"{'Bandwidth P90 (Mbps)':<20} {gcc_bw_p['P90']:>12.2f} {old_ratio_bw_p['P90']:>12.2f} {new_ratio_bw_p['P90']:>12.2f}")
print(f"{'Bandwidth P99 (Mbps)':<20} {gcc_bw_p['P99']:>12.2f} {old_ratio_bw_p['P99']:>12.2f} {new_ratio_bw_p['P99']:>12.2f}")
print("="*70)

# Print improvement percentages
print("\nIMPROVEMENT: New Ratio vs GCC")
print("-"*40)
rtt_p50_imp = (new_ratio_rtt_p['P50'] - gcc_rtt_p['P50']) / gcc_rtt_p['P50'] * 100
rtt_p99_imp = (new_ratio_rtt_p['P99'] - gcc_rtt_p['P99']) / gcc_rtt_p['P99'] * 100
bw_p50_imp = (new_ratio_bw_p['P50'] - gcc_bw_p['P50']) / gcc_bw_p['P50'] * 100
bw_p99_imp = (new_ratio_bw_p['P99'] - gcc_bw_p['P99']) / gcc_bw_p['P99'] * 100
print(f"RTT P50: {rtt_p50_imp:+.1f}% {'(lower is better)' if rtt_p50_imp < 0 else ''}")
print(f"RTT P99: {rtt_p99_imp:+.1f}% {'(lower is better)' if rtt_p99_imp < 0 else ''}")
print(f"Bandwidth P50: {bw_p50_imp:+.1f}% {'(higher is better)' if bw_p50_imp > 0 else ''}")
print(f"Bandwidth P99: {bw_p99_imp:+.1f}% {'(higher is better)' if bw_p99_imp > 0 else ''}")

plt.show()

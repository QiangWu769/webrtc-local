#!/usr/bin/env python3
import re
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt

# Parse with MonoTime matching
monotime_to_ratio = {}
monotime_to_bitrate = {}

with open('/home/wuq/webrtc-local/webrtc_config_results/sender_local.log', 'r') as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        mono_match = re.search(r'MonoTime:\s*(\d+)', line)
        if mono_match:
            monotime = int(mono_match.group(1))

            bwe_match = re.search(r'AckedBitrate:\s*(-?\d+)', line)
            if bwe_match:
                bitrate = int(bwe_match.group(1))
                if bitrate > 0:
                    monotime_to_bitrate[monotime] = bitrate

        ratio_match = re.search(r'smoothed:\s*([\d.]+)\)', line)
        if ratio_match:
            ratio = float(ratio_match.group(1))
            for j in range(max(0, i-5), min(len(lines), i+6)):
                mono_match2 = re.search(r'MonoTime:\s*(\d+)', lines[j])
                if mono_match2:
                    monotime = int(mono_match2.group(1))
                    monotime_to_ratio[monotime] = ratio
                    break

# Match by monotime
data = []
for mono_ratio, ratio in monotime_to_ratio.items():
    for mono_bwe, bwe in monotime_to_bitrate.items():
        if abs(mono_ratio - mono_bwe) <= 100:
            data.append((ratio, bwe))
            break

ratios = np.array([d[0] for d in data])
bitrates = np.array([d[1] for d in data]) / 1e6

# Binned analysis - 0-2范围
bins = np.linspace(0, 2, 41)
bin_indices = np.digitize(ratios, bins)

bin_centers = []
medians = []
p25s = []
p75s = []
counts = []

for b in range(1, len(bins)):
    mask = bin_indices == b
    count = np.sum(mask)
    counts.append(count)

    if count >= 1:
        bin_centers.append((bins[b-1] + bins[b]) / 2)
        medians.append(np.median(bitrates[mask]))
        if count >= 2:
            p25s.append(np.percentile(bitrates[mask], 25))
            p75s.append(np.percentile(bitrates[mask], 75))
        else:
            p25s.append(np.nan)
            p75s.append(np.nan)

bin_centers = np.array(bin_centers)
medians = np.array(medians)
p25s = np.array(p25s)
p75s = np.array(p75s)

# Correlation
valid_mask = ~np.isnan(medians)
valid_bins = bin_centers[valid_mask]
valid_medians = medians[valid_mask]

pearson_binned, _ = stats.pearsonr(valid_bins, valid_medians)

# Calculate statistics for annotation
total_points = len(ratios)
low_ratio = np.sum((ratios >= 0) & (ratios < 0.5))
mid_ratio = np.sum((ratios >= 0.5) & (ratios < 1.0))
high_ratio = np.sum(ratios >= 1.0)

# Plot
fig, ax = plt.subplots(figsize=(12, 7))

# Plot median and percentiles
valid_p25_mask = ~np.isnan(p25s)
ax.plot(bin_centers[valid_mask], medians[valid_mask], 'r-', linewidth=2.5, zorder=3)
ax.fill_between(bin_centers[valid_p25_mask], p25s[valid_p25_mask], p75s[valid_p25_mask],
                alpha=0.3, color='red', zorder=2)

ax.set_xlabel('Smoothed Ratio', fontsize=14, fontweight='bold')
ax.set_ylabel('Acked Bitrate (Mbps)', fontsize=14, fontweight='bold')
ax.set_title(f'Smoothed Ratio vs Acked Bitrate\nPearson r = {pearson_binned:+.4f}',
             fontsize=15, fontweight='bold')
ax.set_xlim(0, 2)
ax.set_ylim(0, max(p75s[valid_p25_mask].max() * 1.05, medians[valid_mask].max() * 1.05))
ax.grid(True, alpha=0.3)

# Add data density annotations at the bottom
y_pos = -0.8  # Position below x-axis
ax.text(0.25, y_pos, f'[0, 0.5)\n{low_ratio} pts\n({100*low_ratio/total_points:.1f}%)',
        ha='center', va='top', fontsize=10,
        bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgreen', alpha=0.7))

ax.text(0.75, y_pos, f'[0.5, 1.0)\n{mid_ratio} pts\n({100*mid_ratio/total_points:.1f}%)',
        ha='center', va='top', fontsize=10,
        bbox=dict(boxstyle='round,pad=0.5', facecolor='lightyellow', alpha=0.7))

ax.text(1.25, y_pos, f'[1.0, 2.0)\n{high_ratio} pts\n({100*high_ratio/total_points:.1f}%)',
        ha='center', va='top', fontsize=10,
        bbox=dict(boxstyle='round,pad=0.5', facecolor='lightcoral', alpha=0.7))

plt.tight_layout()
plt.savefig('/home/wuq/webrtc-local/ratio_vs_bitrate_with_density.png', dpi=150, bbox_inches='tight')
print(f"Plot with density annotations saved: ratio_vs_bitrate_with_density.png")
print(f"Pearson r = {pearson_binned:+.4f}")
print(f"\nData distribution:")
print(f"  [0.0, 0.5):   {low_ratio:5d} points ({100*low_ratio/total_points:5.2f}%)")
print(f"  [0.5, 1.0):   {mid_ratio:5d} points ({100*mid_ratio/total_points:5.2f}%)")
print(f"  [1.0, 2.0):   {high_ratio:5d} points ({100*high_ratio/total_points:5.2f}%)")

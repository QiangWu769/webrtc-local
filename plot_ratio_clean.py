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

for b in range(1, len(bins)):
    mask = bin_indices == b
    count = np.sum(mask)

    if count >= 1:
        bin_centers.append((bins[b-1] + bins[b]) / 2)
        medians.append(np.median(bitrates[mask]))
        if count >= 3:
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
ax.set_ylim(0, max(bitrates.max() * 1.05, medians[valid_mask].max() * 1.05))
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('/home/wuq/webrtc-local/ratio_vs_bitrate_clean.png', dpi=150, bbox_inches='tight')
print(f"Clean plot saved: ratio_vs_bitrate_clean.png")
print(f"Pearson r = {pearson_binned:+.4f}")

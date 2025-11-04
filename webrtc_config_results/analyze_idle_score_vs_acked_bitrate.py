#!/usr/bin/env python3
import re
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt

# Parse IdleScore and AckedBitrate from log
monotime_to_idle_score = {}
monotime_to_acked_bitrate = {}

with open('/home/wuq/webrtc-local/webrtc_config_results/sender_local.log', 'r') as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        # Extract IdleScore with MonoTime context
        idle_match = re.search(r'IdleScore:\s*([\d.]+),\s*Gain:\s*([\d.]+)', line)
        if idle_match:
            idle_score = float(idle_match.group(1))
            # Search nearby lines for MonoTime
            for j in range(max(0, i-10), min(len(lines), i+10)):
                mono_match = re.search(r'MonoTime:\s*(\d+)', lines[j])
                if mono_match:
                    monotime = int(mono_match.group(1))
                    monotime_to_idle_score[monotime] = idle_score
                    break

        # Extract AckedBitrate with MonoTime
        acked_match = re.search(r'MonoTime:\s*(\d+).*AckedBitrate(?:Bps)?:\s*(-?\d+)', line)
        if acked_match:
            monotime = int(acked_match.group(1))
            acked_bitrate = int(acked_match.group(2))
            if acked_bitrate > 0:
                monotime_to_acked_bitrate[monotime] = acked_bitrate

# Match by monotime (allow 1000ms tolerance)
data = []
for mono_idle, idle_score in monotime_to_idle_score.items():
    for mono_acked, acked_bps in monotime_to_acked_bitrate.items():
        if abs(mono_idle - mono_acked) <= 1000:
            data.append((idle_score, acked_bps / 1e6))  # Convert to Mbps
            break

if len(data) == 0:
    print("No matching data found!")
    exit(1)

idle_scores = np.array([d[0] for d in data])
acked_bitrates = np.array([d[1] for d in data])

print(f"Total matched pairs: {len(data)}")
print(f"IdleScore range: [{idle_scores.min():.2f}, {idle_scores.max():.2f}]")
print(f"AckedBitrate range: [{acked_bitrates.min():.2f}, {acked_bitrates.max():.2f}] Mbps")

# Calculate correlation
pearson_r, pearson_p = stats.pearsonr(idle_scores, acked_bitrates)
spearman_r, spearman_p = stats.spearmanr(idle_scores, acked_bitrates)

print(f"\nCorrelation:")
print(f"  Pearson r = {pearson_r:+.4f} (p={pearson_p:.4e})")
print(f"  Spearman r = {spearman_r:+.4f} (p={spearman_p:.4e})")

# Binned analysis
bins = np.linspace(0, 100, 41)  # 40 bins like ratio plot
bin_indices = np.digitize(idle_scores, bins)

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
        medians.append(np.median(acked_bitrates[mask]))
        if count >= 2:
            p25s.append(np.percentile(acked_bitrates[mask], 25))
            p75s.append(np.percentile(acked_bitrates[mask], 75))
        else:
            p25s.append(np.nan)
            p75s.append(np.nan)

bin_centers = np.array(bin_centers)
medians = np.array(medians)
p25s = np.array(p25s)
p75s = np.array(p75s)

# Calculate binned correlation
valid_mask = ~np.isnan(medians)
if valid_mask.sum() > 0:
    pearson_binned, _ = stats.pearsonr(bin_centers[valid_mask], medians[valid_mask])
else:
    pearson_binned = 0

# Calculate statistics for annotation
total_points = len(idle_scores)
low_idle = np.sum((idle_scores >= 0) & (idle_scores < 33.33))
mid_idle = np.sum((idle_scores >= 33.33) & (idle_scores < 66.67))
high_idle = np.sum(idle_scores >= 66.67)

# Plot
fig, ax = plt.subplots(figsize=(12, 7))

# Plot median and percentiles
valid_p25_mask = ~np.isnan(p25s)
ax.plot(bin_centers[valid_mask], medians[valid_mask], 'r-', linewidth=2.5, zorder=3)
ax.fill_between(bin_centers[valid_p25_mask], p25s[valid_p25_mask], p75s[valid_p25_mask],
                alpha=0.3, color='red', zorder=2)

ax.set_xlabel('Idle Score', fontsize=14, fontweight='bold')
ax.set_ylabel('Acked Bitrate (Mbps)', fontsize=14, fontweight='bold')
ax.set_title(f'Idle Score vs Acked Bitrate\nPearson r (binned) = {pearson_binned:+.4f}',
             fontsize=15, fontweight='bold')
ax.set_xlim(0, 100)
if valid_p25_mask.sum() > 0:
    y_max = max(p75s[valid_p25_mask].max() * 1.05, medians[valid_mask].max() * 1.05)
else:
    y_max = medians[valid_mask].max() * 1.05
ax.set_ylim(0, y_max)
ax.grid(True, alpha=0.3)

# Add data density annotations at the bottom
y_pos = -y_max * 0.08
ax.text(16.67, y_pos, f'[0, 33.3)\n{low_idle} pts\n({100*low_idle/total_points:.1f}%)',
        ha='center', va='top', fontsize=10,
        bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgreen', alpha=0.7))

ax.text(50, y_pos, f'[33.3, 66.7)\n{mid_idle} pts\n({100*mid_idle/total_points:.1f}%)',
        ha='center', va='top', fontsize=10,
        bbox=dict(boxstyle='round,pad=0.5', facecolor='lightyellow', alpha=0.7))

ax.text(83.33, y_pos, f'[66.7, 100)\n{high_idle} pts\n({100*high_idle/total_points:.1f}%)',
        ha='center', va='top', fontsize=10,
        bbox=dict(boxstyle='round,pad=0.5', facecolor='lightcoral', alpha=0.7))

plt.tight_layout()
plt.savefig('/home/wuq/webrtc-local/webrtc_config_results/idle_score_vs_acked_bitrate.png', dpi=150, bbox_inches='tight')
print(f"\nPlot saved: idle_score_vs_acked_bitrate.png")
print(f"Pearson r (binned) = {pearson_binned:+.4f}")
print(f"\nData distribution:")
print(f"  [0.0, 33.3):    {low_idle:5d} points ({100*low_idle/total_points:5.2f}%)")
print(f"  [33.3, 66.7):   {mid_idle:5d} points ({100*mid_idle/total_points:5.2f}%)")
print(f"  [66.7, 100):    {high_idle:5d} points ({100*high_idle/total_points:5.2f}%)")

#!/usr/bin/env python3
import re
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt

# Parse log file
gain_ratio_pairs = []

with open('/home/wuq/webrtc-local/webrtc_config_results/sender_local.log', 'r') as f:
    lines = f.readlines()

    for i, line in enumerate(lines):
        # Find GainFactor lines
        gain_match = re.search(r'\[AIMD-GainFactor\].*IdleScore:\s*([\d.]+),\s*Gain:\s*([\d.]+)', line)
        if gain_match:
            idle_score = float(gain_match.group(1))
            gain = float(gain_match.group(2))

            # Search nearby lines for smoothed ratio (within 10 lines)
            smoothed_ratio = None
            for j in range(max(0, i-10), min(len(lines), i+10)):
                ratio_match = re.search(r'smoothed:\s*([\d.]+)\)', lines[j])
                if ratio_match:
                    smoothed_ratio = float(ratio_match.group(1))
                    break

            if smoothed_ratio is not None:
                gain_ratio_pairs.append({
                    'ratio': smoothed_ratio,
                    'gain': gain,
                    'idle_score': idle_score
                })

print(f"Found {len(gain_ratio_pairs)} Gain-Ratio pairs")

if len(gain_ratio_pairs) == 0:
    print("No data found! Exiting.")
    exit(1)

# Convert to arrays
ratios = np.array([p['ratio'] for p in gain_ratio_pairs])
gains = np.array([p['gain'] for p in gain_ratio_pairs])
idle_scores = np.array([p['idle_score'] for p in gain_ratio_pairs])

# Statistics
print("\n=== Ratio Statistics ===")
print(f"Min: {ratios.min():.3f}, Max: {ratios.max():.3f}")
print(f"Mean: {ratios.mean():.3f}, Median: {np.median(ratios):.3f}")
print(f"Std: {ratios.std():.3f}")

print("\n=== Gain Statistics ===")
unique_gains, counts = np.unique(gains, return_counts=True)
for g, c in zip(unique_gains, counts):
    print(f"Gain {g}: {c} times ({100*c/len(gains):.1f}%)")

# Correlation analysis
print("\n=== Correlation Analysis ===")
pearson_r, pearson_p = stats.pearsonr(ratios, gains)
spearman_r, spearman_p = stats.spearmanr(ratios, gains)
print(f"Pearson correlation: r={pearson_r:+.4f}, p={pearson_p:.4e}")
print(f"Spearman correlation: rho={spearman_r:+.4f}, p={spearman_p:.4e}")

# Binned analysis
bins = np.linspace(0, 2, 21)
bin_indices = np.digitize(ratios, bins)

bin_centers = []
mean_gains = []
median_gains = []
std_gains = []
counts_per_bin = []

for b in range(1, len(bins)):
    mask = bin_indices == b
    count = np.sum(mask)

    if count >= 1:
        bin_centers.append((bins[b-1] + bins[b]) / 2)
        mean_gains.append(np.mean(gains[mask]))
        median_gains.append(np.median(gains[mask]))
        std_gains.append(np.std(gains[mask]))
        counts_per_bin.append(count)

bin_centers = np.array(bin_centers)
mean_gains = np.array(mean_gains)
median_gains = np.array(median_gains)
std_gains = np.array(std_gains)

# Plot 1: Scatter plot with binned statistics
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# Subplot 1: Scatter plot
ax1 = axes[0, 0]
ax1.scatter(ratios, gains, alpha=0.3, s=20)
ax1.plot(bin_centers, mean_gains, 'r-', linewidth=2, label='Mean Gain')
ax1.set_xlabel('Smoothed Ratio', fontweight='bold')
ax1.set_ylabel('Gain Factor', fontweight='bold')
ax1.set_title(f'Gain Factor vs Smoothed Ratio\nPearson r={pearson_r:+.4f}', fontweight='bold')
ax1.grid(True, alpha=0.3)
ax1.legend()
ax1.set_xlim(0, 2)

# Subplot 2: Gain distribution for different ratio ranges
ax2 = axes[0, 1]
ratio_ranges = [
    (0, 0.5, 'Low (0-0.5)'),
    (0.5, 1.0, 'Medium (0.5-1.0)'),
    (1.0, 2.0, 'High (1.0-2.0)')
]

positions = []
gain_distributions = []
labels = []

for i, (low, high, label) in enumerate(ratio_ranges):
    mask = (ratios >= low) & (ratios < high)
    if np.sum(mask) > 0:
        positions.append(i)
        gain_distributions.append(gains[mask])
        labels.append(f'{label}\n(n={np.sum(mask)})')

bp = ax2.boxplot(gain_distributions, positions=positions, labels=labels, patch_artist=True)
for patch in bp['boxes']:
    patch.set_facecolor('lightblue')
ax2.set_ylabel('Gain Factor', fontweight='bold')
ax2.set_title('Gain Distribution by Ratio Range', fontweight='bold')
ax2.grid(True, alpha=0.3, axis='y')

# Subplot 3: Gain factor frequency for each ratio bin
ax3 = axes[1, 0]
width = (bin_centers[1] - bin_centers[0]) * 0.8
ax3.bar(bin_centers, mean_gains, width=width, alpha=0.7, label='Mean Gain')
ax3.errorbar(bin_centers, mean_gains, yerr=std_gains, fmt='none', ecolor='red', capsize=3, alpha=0.5)
ax3.set_xlabel('Smoothed Ratio', fontweight='bold')
ax3.set_ylabel('Mean Gain Factor ± Std', fontweight='bold')
ax3.set_title('Gain Factor Statistics by Ratio Bins', fontweight='bold')
ax3.grid(True, alpha=0.3)
ax3.set_xlim(0, 2)

# Subplot 4: Sample count per bin
ax4 = axes[1, 1]
ax4.bar(bin_centers, counts_per_bin, width=width, alpha=0.7, color='green')
ax4.set_xlabel('Smoothed Ratio', fontweight='bold')
ax4.set_ylabel('Sample Count', fontweight='bold')
ax4.set_title('Data Distribution Across Ratio Bins', fontweight='bold')
ax4.grid(True, alpha=0.3, axis='y')
ax4.set_xlim(0, 2)

plt.tight_layout()
plt.savefig('/home/wuq/webrtc-local/gain_vs_ratio_analysis.png', dpi=150, bbox_inches='tight')
print(f"\nPlot saved: gain_vs_ratio_analysis.png")

# Detailed analysis for each gain value
print("\n=== Gain Factor vs Ratio Statistics ===")
for gain_val in sorted(np.unique(gains)):
    mask = gains == gain_val
    ratio_subset = ratios[mask]
    print(f"\nGain = {gain_val} ({np.sum(mask)} samples):")
    print(f"  Ratio range: [{ratio_subset.min():.3f}, {ratio_subset.max():.3f}]")
    print(f"  Ratio mean: {ratio_subset.mean():.3f}, median: {np.median(ratio_subset):.3f}")
    print(f"  Ratio std: {ratio_subset.std():.3f}")

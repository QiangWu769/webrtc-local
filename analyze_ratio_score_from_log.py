#!/usr/bin/env python3
"""
Analyze ratio and score data from log file
Extract [AIMD-GainFactor] entries and visualize distributions
"""

import re
import numpy as np
import matplotlib.pyplot as plt
from collections import Counter

log_file = '/home/wuq/webrtc-local/webrtc_config_results/sender_local.log'

# Parse log file
scores = []
gains = []
base_rates = []

print("Parsing log file...")
with open(log_file, 'r') as f:
    for line in f:
        # Match pattern: [AIMD-GainFactor] DISABLED - Score: X, Gain: Y, Base rate: Z bps/s
        match = re.search(r'\[AIMD-GainFactor\].*Score:\s*([\d.]+),\s*Gain:\s*([\d.]+),\s*Base rate:\s*([\d.]+)', line)
        if match:
            score = float(match.group(1))
            gain = float(match.group(2))
            base_rate = float(match.group(3))

            scores.append(score)
            gains.append(gain)
            base_rates.append(base_rate)

print(f"✓ Found {len(scores)} [AIMD-GainFactor] entries")

if len(scores) == 0:
    print("ERROR: No data found in log file")
    exit(1)

# Calculate ratio from score (inverse of score calculation)
# score = (1 - sigmoid) * 100
# sigmoid = 1 - score/100
# sigmoid = 1 / (1 + exp(-steepness * (ratio - center)))
# Solve for ratio:
def score_to_ratio(score):
    """Convert score back to ratio (inverse sigmoid)"""
    center = 0.5
    steepness = 15.0

    # sigmoid = 1 - score/100
    sigmoid = 1.0 - score / 100.0

    # sigmoid = 1 / (1 + exp(-steepness * (ratio - center)))
    # 1 / sigmoid = 1 + exp(-steepness * (ratio - center))
    # 1/sigmoid - 1 = exp(-steepness * (ratio - center))
    # ln(1/sigmoid - 1) = -steepness * (ratio - center)
    # ratio = center - ln(1/sigmoid - 1) / steepness

    if sigmoid <= 0 or sigmoid >= 1:
        return np.nan

    ratio = center - np.log(1.0/sigmoid - 1.0) / steepness
    return ratio

ratios = [score_to_ratio(s) for s in scores]
ratios = [r for r in ratios if not np.isnan(r)]

scores = np.array(scores)
gains = np.array(gains)
ratios = np.array(ratios)
base_rates = np.array(base_rates)

# Statistics
print("\n" + "="*80)
print("STATISTICS")
print("="*80)

print(f"\nScore:")
print(f"  Count: {len(scores)}")
print(f"  Min:   {scores.min():.3f}")
print(f"  Max:   {scores.max():.3f}")
print(f"  Mean:  {scores.mean():.3f}")
print(f"  Median: {np.median(scores):.3f}")
print(f"  Std:   {scores.std():.3f}")

print(f"\nRatio (calculated from score):")
print(f"  Count: {len(ratios)}")
print(f"  Min:   {ratios.min():.4f}")
print(f"  Max:   {ratios.max():.4f}")
print(f"  Mean:  {ratios.mean():.4f}")
print(f"  Median: {np.median(ratios):.4f}")
print(f"  Std:   {ratios.std():.4f}")

print(f"\nGain Factor:")
print(f"  Count: {len(gains)}")
print(f"  Min:   {gains.min():.1f}")
print(f"  Max:   {gains.max():.1f}")
print(f"  Mean:  {gains.mean():.3f}")
print(f"  Median: {np.median(gains):.3f}")

# Gain distribution
gain_counts = Counter(gains)
print("\n  Distribution:")
for g in sorted(gain_counts.keys()):
    count = gain_counts[g]
    percentage = count / len(gains) * 100
    print(f"    Gain={g:.1f}: {count:4d} samples ({percentage:5.1f}%)")

# Score ranges
score_ranges = [
    (0, 20, "Very Low (0-20)"),
    (20, 50, "Low (20-50)"),
    (50, 70, "Medium (50-70)"),
    (70, 90, "High (70-90)"),
    (90, 100, "Very High (90-100)"),
]

print("\nScore Distribution by Range:")
for min_s, max_s, label in score_ranges:
    count = np.sum((scores >= min_s) & (scores < max_s))
    percentage = count / len(scores) * 100
    print(f"  {label:20s}: {count:4d} samples ({percentage:5.1f}%)")

# Ratio ranges
ratio_ranges = [
    (0.0, 0.3, "Very Low (0.0-0.3)"),
    (0.3, 0.5, "Low (0.3-0.5)"),
    (0.5, 0.7, "Medium (0.5-0.7)"),
    (0.7, 0.9, "High (0.7-0.9)"),
    (0.9, 1.0, "Very High (0.9-1.0)"),
]

print("\nRatio Distribution by Range:")
for min_r, max_r, label in ratio_ranges:
    count = np.sum((ratios >= min_r) & (ratios < max_r))
    percentage = count / len(ratios) * 100
    print(f"  {label:25s}: {count:4d} samples ({percentage:5.1f}%)")

# Create visualization
fig = plt.figure(figsize=(18, 12))
gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

# Plot 1: Score histogram
ax1 = fig.add_subplot(gs[0, 0])
ax1.hist(scores, bins=50, color='blue', alpha=0.7, edgecolor='black')
ax1.set_xlabel('Score', fontsize=11, fontweight='bold')
ax1.set_ylabel('Frequency', fontsize=11, fontweight='bold')
ax1.set_title(f'Score Distribution\n(n={len(scores)}, mean={scores.mean():.2f})', fontsize=12, fontweight='bold')
ax1.grid(True, alpha=0.3)
ax1.axvline(x=scores.mean(), color='red', linestyle='--', linewidth=2, label=f'Mean={scores.mean():.2f}')
ax1.axvline(x=np.median(scores), color='green', linestyle='--', linewidth=2, label=f'Median={np.median(scores):.2f}')
ax1.legend()

# Plot 2: Ratio histogram
ax2 = fig.add_subplot(gs[0, 1])
ax2.hist(ratios, bins=50, color='green', alpha=0.7, edgecolor='black')
ax2.set_xlabel('Ratio', fontsize=11, fontweight='bold')
ax2.set_ylabel('Frequency', fontsize=11, fontweight='bold')
ax2.set_title(f'Ratio Distribution\n(n={len(ratios)}, mean={ratios.mean():.3f})', fontsize=12, fontweight='bold')
ax2.grid(True, alpha=0.3)
ax2.axvline(x=ratios.mean(), color='red', linestyle='--', linewidth=2, label=f'Mean={ratios.mean():.3f}')
ax2.axvline(x=np.median(ratios), color='darkgreen', linestyle='--', linewidth=2, label=f'Median={np.median(ratios):.3f}')
ax2.legend()

# Plot 3: Gain distribution (bar chart)
ax3 = fig.add_subplot(gs[0, 2])
gain_values = sorted(gain_counts.keys())
gain_frequencies = [gain_counts[g] for g in gain_values]
bars = ax3.bar(gain_values, gain_frequencies, color='orange', alpha=0.7, edgecolor='black', width=0.15)
ax3.set_xlabel('Gain Factor', fontsize=11, fontweight='bold')
ax3.set_ylabel('Frequency', fontsize=11, fontweight='bold')
ax3.set_title(f'Gain Factor Distribution\n(n={len(gains)})', fontsize=12, fontweight='bold')
ax3.grid(True, alpha=0.3, axis='y')
ax3.set_xticks(gain_values)

# Add percentage labels on bars
for bar, g in zip(bars, gain_values):
    height = bar.get_height()
    percentage = height / len(gains) * 100
    ax3.text(bar.get_x() + bar.get_width()/2., height,
            f'{percentage:.1f}%',
            ha='center', va='bottom', fontsize=9, fontweight='bold')

# Plot 4: Score vs Time
ax4 = fig.add_subplot(gs[1, :])
ax4.plot(scores, color='blue', alpha=0.6, linewidth=1)
ax4.set_xlabel('Sample Index', fontsize=11, fontweight='bold')
ax4.set_ylabel('Score', fontsize=11, fontweight='bold')
ax4.set_title('Score over Time', fontsize=12, fontweight='bold')
ax4.grid(True, alpha=0.3)
ax4.axhline(y=70, color='red', linestyle='--', alpha=0.5, label='Score=70')
ax4.axhline(y=scores.mean(), color='orange', linestyle='--', linewidth=2, label=f'Mean={scores.mean():.2f}')
ax4.legend()

# Plot 5: Ratio vs Time
ax5 = fig.add_subplot(gs[2, :])
ax5.plot(ratios, color='green', alpha=0.6, linewidth=1)
ax5.set_xlabel('Sample Index', fontsize=11, fontweight='bold')
ax5.set_ylabel('Ratio', fontsize=11, fontweight='bold')
ax5.set_title('Ratio over Time (calculated from Score)', fontsize=12, fontweight='bold')
ax5.grid(True, alpha=0.3)
ax5.axhline(y=0.5, color='red', linestyle='--', alpha=0.5, label='Ratio=0.5')
ax5.axhline(y=ratios.mean(), color='orange', linestyle='--', linewidth=2, label=f'Mean={ratios.mean():.3f}')
ax5.legend()

plt.suptitle('Ratio and Score Analysis from Log File', fontsize=16, fontweight='bold')
plt.savefig('ratio_score_analysis.png', dpi=150, bbox_inches='tight')
print("\n✓ Saved: ratio_score_analysis.png")

# Print sample data
print("\n" + "="*80)
print("SAMPLE DATA (first 20 entries)")
print("="*80)
print(f"{'Index':<8} {'Score':<12} {'Ratio':<12} {'Gain':<8} {'Base Rate (bps)':<15}")
print("-" * 80)
for i in range(min(20, len(scores))):
    print(f"{i:<8} {scores[i]:<12.3f} {ratios[i]:<12.4f} {gains[i]:<8.1f} {base_rates[i]:<15.0f}")

print("\n" + "="*80)
print("KEY FINDINGS")
print("="*80)
print(f"""
1. Score分布:
   - 平均值: {scores.mean():.2f}
   - 中位数: {np.median(scores):.2f}
   - 范围: [{scores.min():.2f}, {scores.max():.2f}]

2. Ratio分布 (从Score反推):
   - 平均值: {ratios.mean():.4f}
   - 中位数: {np.median(ratios):.4f}
   - 范围: [{ratios.min():.4f}, {ratios.max():.4f}]

3. Gain Factor分布:
   - 最常见: {max(gain_counts, key=gain_counts.get):.1f}× ({gain_counts[max(gain_counts, key=gain_counts.get)]/len(gains)*100:.1f}%)
   - 平均值: {gains.mean():.3f}×

4. 网络状况评估:
   {"   - Score较低 → Ratio较高 → 资源充足" if scores.mean() < 50 else "   - Score较高 → Ratio较低 → 资源紧张"}
""")

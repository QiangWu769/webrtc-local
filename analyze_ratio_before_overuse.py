#!/usr/bin/env python3
"""
Analyze ratio trend before Overusing events
"""

import re
import numpy as np
import matplotlib.pyplot as plt

log_file = '/home/wuq/webrtc-local/webrtc_config_results/sender_local.log'

# Parse gain factor entries (which contain score/ratio info)
gain_entries = []  # (line_num, score, gain)
bwe_entries = []   # (line_num, bw_state)

print("Parsing log file...")
with open(log_file, 'r') as f:
    for line_num, line in enumerate(f):
        # Match gain factor entries
        match = re.search(r'\[AIMD-GainFactor\].*Score:\s*([\d.]+),\s*Gain:\s*([\d.]+)', line)
        if match:
            score = float(match.group(1))
            gain = float(match.group(2))
            gain_entries.append((line_num, score, gain))

        # Match BWE decision entries
        match = re.search(r'\[BWE-DECISION\].*BWState:\s*(\w+)', line)
        if match:
            bw_state = match.group(1)
            bwe_entries.append((line_num, bw_state))

print(f"✓ Found {len(gain_entries)} Gain Factor entries")
print(f"✓ Found {len(bwe_entries)} BWE Decision entries")

# Convert score to ratio
def score_to_ratio(score):
    center = 0.5
    steepness = 15.0
    sigmoid = 1.0 - score / 100.0
    if sigmoid <= 0 or sigmoid >= 1:
        return np.nan
    ratio = center - np.log(1.0/sigmoid - 1.0) / steepness
    return ratio

# Find all overusing events
overusing_events = [line for line, state in bwe_entries if state == 'Overusing']
print(f"✓ Found {len(overusing_events)} Overusing events")

print("\n" + "="*80)
print("RATIO BEFORE OVERUSING ANALYSIS")
print("="*80)

# For each overusing event, analyze ratio trend before it
lookback_samples = 50  # Look back 50 score samples

all_ratios_before = []  # Store all ratio sequences before overusing

for i, overuse_line in enumerate(overusing_events):
    print(f"\n{'='*80}")
    print(f"Overusing Event #{i+1} at line {overuse_line}")
    print(f"{'='*80}")

    # Find score entries before this overusing event
    scores_before = []
    ratios_before = []
    lines_before = []

    for line, score, gain in reversed(gain_entries):
        if line < overuse_line:
            scores_before.insert(0, score)
            ratio = score_to_ratio(score)
            ratios_before.insert(0, ratio)
            lines_before.insert(0, line)
            if len(scores_before) >= lookback_samples:
                break

    if len(ratios_before) == 0:
        print(f"  No score data found before this overusing event")
        continue

    ratios_before = np.array(ratios_before)
    scores_before = np.array(scores_before)

    # Statistics
    print(f"\n  Ratio statistics (last {len(ratios_before)} samples before overusing):")
    print(f"    Immediate before (last 5):  {ratios_before[-5:].tolist()}")
    print(f"    Mean:    {ratios_before.mean():.4f}")
    print(f"    Median:  {np.median(ratios_before):.4f}")
    print(f"    Min:     {ratios_before.min():.4f}")
    print(f"    Max:     {ratios_before.max():.4f}")
    print(f"    Std:     {ratios_before.std():.4f}")
    print(f"    Final:   {ratios_before[-1]:.4f} (immediately before overusing)")

    print(f"\n  Score statistics:")
    print(f"    Immediate before (last 5):  {scores_before[-5:].tolist()}")
    print(f"    Mean:    {scores_before.mean():.2f}")
    print(f"    Final:   {scores_before[-1]:.2f}")

    # Trend analysis
    if len(ratios_before) >= 10:
        recent_10 = ratios_before[-10:]
        earlier_10 = ratios_before[-20:-10] if len(ratios_before) >= 20 else ratios_before[:-10]

        print(f"\n  Trend analysis:")
        print(f"    Recent 10 samples mean:  {recent_10.mean():.4f}")
        print(f"    Earlier 10 samples mean: {earlier_10.mean():.4f}")
        if recent_10.mean() < earlier_10.mean():
            print(f"    → Ratio is DECREASING (resources getting tighter)")
        else:
            print(f"    → Ratio is INCREASING (resources improving)")

    # Count high scores
    high_score_count = np.sum(scores_before >= 90)
    medium_score_count = np.sum((scores_before >= 70) & (scores_before < 90))
    print(f"\n  High score occurrences before overusing:")
    print(f"    Score >= 90: {high_score_count} / {len(scores_before)} ({high_score_count/len(scores_before)*100:.1f}%)")
    print(f"    Score >= 70: {medium_score_count} / {len(scores_before)} ({medium_score_count/len(scores_before)*100:.1f}%)")

    all_ratios_before.append(ratios_before)

# Overall statistics
print("\n" + "="*80)
print("OVERALL STATISTICS")
print("="*80)

all_ratios_flat = np.concatenate(all_ratios_before)
print(f"\nAll ratios before overusing events (n={len(all_ratios_flat)}):")
print(f"  Mean:    {all_ratios_flat.mean():.4f}")
print(f"  Median:  {np.median(all_ratios_flat):.4f}")
print(f"  Min:     {all_ratios_flat.min():.4f}")
print(f"  Max:     {all_ratios_flat.max():.4f}")
print(f"  Std:     {all_ratios_flat.std():.4f}")

# Ratio ranges
ratio_ranges = [
    (0.0, 0.3, "Very Low (0.0-0.3) - 严重不足"),
    (0.3, 0.5, "Low (0.3-0.5) - 不足"),
    (0.5, 0.7, "Medium (0.5-0.7) - 中等"),
    (0.7, 0.9, "High (0.7-0.9) - 充足"),
    (0.9, 1.5, "Very High (0.9+) - 非常充足"),
]

print("\nRatio distribution before overusing:")
for min_r, max_r, label in ratio_ranges:
    count = np.sum((all_ratios_flat >= min_r) & (all_ratios_flat < max_r))
    percentage = count / len(all_ratios_flat) * 100
    print(f"  {label:40s}: {count:4d} samples ({percentage:5.1f}%)")

# Visualization
n_events = len(all_ratios_before)
fig = plt.figure(figsize=(16, 12))
gs = fig.add_gridspec(4, 3, hspace=0.35, wspace=0.3)

# Plot individual events
for i in range(min(9, n_events)):
    ax = fig.add_subplot(gs[i // 3, i % 3])
    ratios = all_ratios_before[i]
    ax.plot(ratios, color='blue', linewidth=2, marker='o', markersize=4)
    ax.axhline(y=0.5, color='orange', linestyle='--', linewidth=1.5, alpha=0.7, label='Ratio=0.5')
    ax.axhline(y=0.3, color='red', linestyle='--', linewidth=1.5, alpha=0.7, label='Ratio=0.3')
    ax.axvline(x=len(ratios)-1, color='red', linestyle=':', linewidth=2, alpha=0.5)
    ax.set_xlabel('Samples before Overusing', fontsize=9, fontweight='bold')
    ax.set_ylabel('Ratio', fontsize=9, fontweight='bold')
    ax.set_title(f'Event #{i+1} (final ratio={ratios[-1]:.3f})', fontsize=10, fontweight='bold')
    ax.grid(True, alpha=0.3)
    if i == 0:
        ax.legend(fontsize=8)
    ax.set_ylim([0, 1.5])

# Plot combined histogram
ax_hist = fig.add_subplot(gs[3, :])
ax_hist.hist(all_ratios_flat, bins=50, color='blue', alpha=0.7, edgecolor='black')
ax_hist.axvline(x=all_ratios_flat.mean(), color='red', linestyle='--', linewidth=2.5,
               label=f'Mean={all_ratios_flat.mean():.3f}')
ax_hist.axvline(x=np.median(all_ratios_flat), color='green', linestyle='--', linewidth=2.5,
               label=f'Median={np.median(all_ratios_flat):.3f}')
ax_hist.axvline(x=0.5, color='orange', linestyle=':', linewidth=2, alpha=0.7, label='Ratio=0.5 (center)')
ax_hist.axvline(x=0.3, color='darkred', linestyle=':', linewidth=2, alpha=0.7, label='Ratio=0.3 (low)')
ax_hist.set_xlabel('Ratio', fontsize=11, fontweight='bold')
ax_hist.set_ylabel('Frequency', fontsize=11, fontweight='bold')
ax_hist.set_title(f'Distribution of All Ratios Before Overusing (n={len(all_ratios_flat)})',
                 fontsize=12, fontweight='bold')
ax_hist.legend(fontsize=10)
ax_hist.grid(True, alpha=0.3, axis='y')

plt.suptitle('Ratio Trend Before Overusing Events', fontsize=16, fontweight='bold')
plt.savefig('ratio_before_overusing.png', dpi=150, bbox_inches='tight')
print("\n✓ Saved: ratio_before_overusing.png")

# Summary
print("\n" + "="*80)
print("KEY FINDINGS")
print("="*80)

# Calculate percentage in each range
very_low_pct = np.sum((all_ratios_flat >= 0.0) & (all_ratios_flat < 0.3)) / len(all_ratios_flat) * 100
low_pct = np.sum((all_ratios_flat >= 0.3) & (all_ratios_flat < 0.5)) / len(all_ratios_flat) * 100
medium_pct = np.sum((all_ratios_flat >= 0.5) & (all_ratios_flat < 0.7)) / len(all_ratios_flat) * 100
high_pct = np.sum((all_ratios_flat >= 0.7) & (all_ratios_flat < 0.9)) / len(all_ratios_flat) * 100
very_high_pct = np.sum(all_ratios_flat >= 0.9) / len(all_ratios_flat) * 100

print(f"""
Overusing发生前的Ratio特征:

1. 平均Ratio: {all_ratios_flat.mean():.4f}
   - 中位数: {np.median(all_ratios_flat):.4f}
   - 范围: [{all_ratios_flat.min():.4f}, {all_ratios_flat.max():.4f}]

2. Ratio分布:
   - 严重不足 (0.0-0.3): {very_low_pct:.1f}%
   - 不足 (0.3-0.5):     {low_pct:.1f}%
   - 中等 (0.5-0.7):     {medium_pct:.1f}%
   - 充足 (0.7-0.9):     {high_pct:.1f}%
   - 非常充足 (0.9+):    {very_high_pct:.1f}%

3. 结论:
   - Overusing发生前，Ratio平均为 {all_ratios_flat.mean():.3f}
   - {"大部分时间资源充足" if all_ratios_flat.mean() > 0.7 else "资源状况中等" if all_ratios_flat.mean() > 0.5 else "资源比较紧张"}
   - {very_low_pct + low_pct:.1f}% 的时间 Ratio < 0.5 (资源不足)
   - 说明 Overusing {"主要" if very_low_pct + low_pct > 50 else "不一定"} 由资源不足引起

4. 与Score的对应:
   - Ratio={all_ratios_flat.mean():.3f} 对应 Score ≈ {(1 - 1/(1 + np.exp(-15*(all_ratios_flat.mean()-0.5))))*100:.1f}
   - 这个Score处于中等水平，对应Gain Factor约为 {"2.0" if all_ratios_flat.mean() > 0.7 else "1.5" if all_ratios_flat.mean() > 0.5 else "1.0"}×
""")

# Find immediate ratio before each overusing
immediate_ratios = [ratios[-1] for ratios in all_ratios_before]
print(f"\n5. Overusing发生前的最后一个Ratio值:")
for i, r in enumerate(immediate_ratios):
    print(f"   Event #{i+1}: {r:.4f}")
print(f"   平均: {np.mean(immediate_ratios):.4f}")
print(f"   中位数: {np.median(immediate_ratios):.4f}")

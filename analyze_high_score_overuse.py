#!/usr/bin/env python3
"""
Analyze high score (>=90) occurrences and their relationship with overuse
"""

import re
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

log_file = '/home/wuq/webrtc-local/webrtc_config_results/sender_local.log'

# Parse log file for gain factor entries and overuse signals
scores = []
gains = []
timestamps = []
score_indices = []

overuse_timestamps = []
overuse_indices = []

print("Parsing log file...")
idx = 0
with open(log_file, 'r') as f:
    for line_num, line in enumerate(f):
        # Match gain factor entries
        match = re.search(r'\[AIMD-GainFactor\].*Score:\s*([\d.]+),\s*Gain:\s*([\d.]+)', line)
        if match:
            score = float(match.group(1))
            gain = float(match.group(2))
            scores.append(score)
            gains.append(gain)
            score_indices.append(idx)
            idx += 1

        # Match overuse signals
        if 'overuse' in line.lower() or 'Overuse' in line or 'OVERUSE' in line:
            # Try to extract bandwidth state changes
            if 'BW state' in line or 'kBwOverusing' in line or 'State: Overusing' in line:
                overuse_timestamps.append(line_num)
                overuse_indices.append(idx)

scores = np.array(scores)
gains = np.array(gains)

print(f"✓ Found {len(scores)} [AIMD-GainFactor] entries")
print(f"✓ Found {len(overuse_timestamps)} overuse signals")

# Analyze high scores (>= 90)
high_score_mask = scores >= 90
high_score_count = np.sum(high_score_mask)
high_score_percentage = high_score_count / len(scores) * 100

print("\n" + "="*80)
print("HIGH SCORE (>=90) ANALYSIS")
print("="*80)

print(f"\nTotal samples: {len(scores)}")
print(f"Score >= 90:   {high_score_count} samples ({high_score_percentage:.2f}%)")
print(f"Score >= 80:   {np.sum(scores >= 80)} samples ({np.sum(scores >= 80)/len(scores)*100:.2f}%)")
print(f"Score >= 70:   {np.sum(scores >= 70)} samples ({np.sum(scores >= 70)/len(scores)*100:.2f}%)")

# Score ranges for high scores
print("\nDetailed breakdown of high scores:")
ranges = [
    (90, 92, "90-92"),
    (92, 94, "92-94"),
    (94, 96, "94-96"),
    (96, 98, "96-98"),
    (98, 100, "98-100"),
]

for min_s, max_s, label in ranges:
    count = np.sum((scores >= min_s) & (scores < max_s))
    percentage = count / len(scores) * 100
    print(f"  Score {label}: {count:4d} samples ({percentage:5.2f}%)")

# Find high score episodes (consecutive high scores)
high_score_episodes = []
in_episode = False
episode_start = -1

for i, is_high in enumerate(high_score_mask):
    if is_high and not in_episode:
        # Start new episode
        episode_start = i
        in_episode = True
    elif not is_high and in_episode:
        # End episode
        high_score_episodes.append((episode_start, i-1, i - episode_start))
        in_episode = False

if in_episode:
    high_score_episodes.append((episode_start, len(scores)-1, len(scores) - episode_start))

print(f"\nHigh Score Episodes (consecutive score >= 90):")
print(f"  Total episodes: {len(high_score_episodes)}")
if len(high_score_episodes) > 0:
    episode_lengths = [ep[2] for ep in high_score_episodes]
    print(f"  Average duration: {np.mean(episode_lengths):.1f} samples")
    print(f"  Max duration: {np.max(episode_lengths)} samples")
    print(f"  Min duration: {np.min(episode_lengths)} samples")

    print(f"\n  Top 10 longest episodes:")
    print(f"  {'Start':<10} {'End':<10} {'Duration':<10} {'Max Score':<12} {'Gain':<10}")
    print("  " + "-" * 60)
    sorted_episodes = sorted(high_score_episodes, key=lambda x: x[2], reverse=True)
    for start, end, duration in sorted_episodes[:10]:
        max_score = np.max(scores[start:end+1])
        typical_gain = gains[start]
        print(f"  {start:<10} {end:<10} {duration:<10} {max_score:<12.2f} {typical_gain:<10.1f}")

# Analyze relationship with overuse
print("\n" + "="*80)
print("RELATIONSHIP WITH OVERUSE")
print("="*80)

if len(overuse_timestamps) > 0:
    print(f"\nTotal overuse signals: {len(overuse_timestamps)}")

    # For each high score, check if there's an overuse signal nearby
    window_before = 50  # Check 50 samples before high score
    window_after = 50   # Check 50 samples after high score

    high_score_indices = np.where(high_score_mask)[0]

    overuse_near_high_score = 0
    high_score_near_overuse = 0

    for high_idx in high_score_indices:
        # Check if any overuse signal is near this high score
        for overuse_idx in overuse_indices:
            if abs(high_idx - overuse_idx) <= window_after:
                overuse_near_high_score += 1
                break

    for overuse_idx in overuse_indices:
        # Check if any high score is near this overuse
        for high_idx in high_score_indices:
            if -window_before <= (high_idx - overuse_idx) <= window_after:
                high_score_near_overuse += 1
                break

    print(f"\nHigh scores (>=90) with overuse nearby (±{window_after} samples):")
    print(f"  {overuse_near_high_score} out of {high_score_count} ({overuse_near_high_score/max(high_score_count,1)*100:.1f}%)")

    print(f"\nOveruse signals with high score nearby (-{window_before}/+{window_after} samples):")
    print(f"  {high_score_near_overuse} out of {len(overuse_timestamps)} ({high_score_near_overuse/len(overuse_timestamps)*100:.1f}%)")
else:
    print("\nNo overuse signals found in log file")
    print("Searching for alternative overuse indicators...")

    # Search for decrease signals
    decrease_count = 0
    with open(log_file, 'r') as f:
        for line in f:
            if 'kBwDecreasing' in line or 'State: Decrease' in line or 'Decrease' in line:
                if 'BW state' in line:
                    decrease_count += 1

    print(f"Found {decrease_count} decrease signals")

# Calculate ratio from score
def score_to_ratio(score):
    center = 0.5
    steepness = 15.0
    sigmoid = 1.0 - score / 100.0
    if sigmoid <= 0 or sigmoid >= 1:
        return np.nan
    ratio = center - np.log(1.0/sigmoid - 1.0) / steepness
    return ratio

# Analyze ratio for high scores
high_score_ratios = [score_to_ratio(s) for s in scores[high_score_mask]]
high_score_ratios = [r for r in high_score_ratios if not np.isnan(r)]

print("\n" + "="*80)
print("RATIO ANALYSIS FOR HIGH SCORES (>=90)")
print("="*80)

if len(high_score_ratios) > 0:
    print(f"\nRatio statistics when score >= 90:")
    print(f"  Mean:   {np.mean(high_score_ratios):.4f}")
    print(f"  Median: {np.median(high_score_ratios):.4f}")
    print(f"  Min:    {np.min(high_score_ratios):.4f}")
    print(f"  Max:    {np.max(high_score_ratios):.4f}")
    print(f"  Std:    {np.std(high_score_ratios):.4f}")

    print("\n  Interpretation:")
    print(f"  → 当Score >= 90时，Ratio平均为 {np.mean(high_score_ratios):.4f}")
    print(f"  → 这意味着资源分配远低于请求（严重资源紧张）")
    print(f"  → Gain建议为 0.0× (停止增长)")

# Visualization
fig, axes = plt.subplots(2, 2, figsize=(16, 10))
fig.suptitle('High Score (>=90) and Overuse Analysis', fontsize=16, fontweight='bold')

# Plot 1: Score over time with high score threshold
ax1 = axes[0, 0]
ax1.plot(scores, color='blue', alpha=0.5, linewidth=0.8)
ax1.axhline(y=90, color='red', linestyle='--', linewidth=2, label='Score=90 threshold')
ax1.axhline(y=70, color='orange', linestyle='--', linewidth=1.5, alpha=0.7, label='Score=70')
ax1.fill_between(range(len(scores)), 90, 100, color='red', alpha=0.1, label='High score zone')
ax1.set_xlabel('Sample Index', fontsize=11, fontweight='bold')
ax1.set_ylabel('Score', fontsize=11, fontweight='bold')
ax1.set_title(f'Score over Time (High Score: {high_score_count}/{len(scores)} = {high_score_percentage:.1f}%)',
              fontsize=12, fontweight='bold')
ax1.grid(True, alpha=0.3)
ax1.legend()
ax1.set_ylim([-5, 105])

# Plot 2: High score histogram
ax2 = axes[0, 1]
if high_score_count > 0:
    high_scores_only = scores[high_score_mask]
    ax2.hist(high_scores_only, bins=20, color='red', alpha=0.7, edgecolor='black')
    ax2.set_xlabel('Score (>=90 only)', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Frequency', fontsize=11, fontweight='bold')
    ax2.set_title(f'Distribution of High Scores\n(n={high_score_count}, mean={np.mean(high_scores_only):.2f})',
                  fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.3, axis='y')
    ax2.axvline(x=np.mean(high_scores_only), color='darkred', linestyle='--',
                linewidth=2, label=f'Mean={np.mean(high_scores_only):.2f}')
    ax2.legend()
else:
    ax2.text(0.5, 0.5, 'No high scores (>=90) found',
             ha='center', va='center', fontsize=14, transform=ax2.transAxes)
    ax2.set_title('Distribution of High Scores', fontsize=12, fontweight='bold')

# Plot 3: Ratio distribution for high scores
ax3 = axes[1, 0]
if len(high_score_ratios) > 0:
    ax3.hist(high_score_ratios, bins=20, color='orange', alpha=0.7, edgecolor='black')
    ax3.set_xlabel('Ratio (when score>=90)', fontsize=11, fontweight='bold')
    ax3.set_ylabel('Frequency', fontsize=11, fontweight='bold')
    ax3.set_title(f'Ratio Distribution for High Scores\n(mean={np.mean(high_score_ratios):.3f})',
                  fontsize=12, fontweight='bold')
    ax3.grid(True, alpha=0.3, axis='y')
    ax3.axvline(x=np.mean(high_score_ratios), color='darkorange', linestyle='--',
                linewidth=2, label=f'Mean={np.mean(high_score_ratios):.3f}')
    ax3.axvline(x=0.5, color='green', linestyle=':', linewidth=1.5, alpha=0.7,
                label='Ratio=0.5 (center)')
    ax3.legend()
else:
    ax3.text(0.5, 0.5, 'No high score data',
             ha='center', va='center', fontsize=14, transform=ax3.transAxes)
    ax3.set_title('Ratio Distribution for High Scores', fontsize=12, fontweight='bold')

# Plot 4: High score episodes timeline
ax4 = axes[1, 1]
if len(high_score_episodes) > 0:
    for i, (start, end, duration) in enumerate(high_score_episodes[:20]):  # Show first 20
        ax4.barh(i, duration, left=start, height=0.8, color='red', alpha=0.6, edgecolor='black')
        # Add label with max score in episode
        max_score = np.max(scores[start:end+1])
        ax4.text(start + duration/2, i, f'{max_score:.1f}',
                ha='center', va='center', fontsize=8, fontweight='bold')

    ax4.set_xlabel('Sample Index', fontsize=11, fontweight='bold')
    ax4.set_ylabel('Episode Number', fontsize=11, fontweight='bold')
    ax4.set_title(f'High Score Episodes (showing first 20 of {len(high_score_episodes)})',
                  fontsize=12, fontweight='bold')
    ax4.grid(True, alpha=0.3, axis='x')
    ax4.set_ylim([-1, min(20, len(high_score_episodes))])
else:
    ax4.text(0.5, 0.5, 'No high score episodes found',
             ha='center', va='center', fontsize=14, transform=ax4.transAxes)
    ax4.set_title('High Score Episodes', fontsize=12, fontweight='bold')

plt.tight_layout()
plt.savefig('high_score_overuse_analysis.png', dpi=150, bbox_inches='tight')
print("\n✓ Saved: high_score_overuse_analysis.png")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print(f"""
Score >= 90的情况:
  • 出现次数: {high_score_count} / {len(scores)} ({high_score_percentage:.2f}%)
  • 连续高分事件: {len(high_score_episodes)} 次
  • 对应的Gain建议: 0.0× (停止增长)

当Score >= 90时:
  • Ratio平均值: {np.mean(high_score_ratios):.4f} (资源严重不足)
  • 说明蜂窝网络资源分配已经远低于请求
  • 系统建议完全停止带宽增长，避免拥塞

与Overuse的关系:
  • 高Score通常意味着资源紧张
  • 理论上应该与overuse detection相关联
  • 如果启用增益因子，可以在overuse发生前预防性降低增长率
  • 当前是DISABLED状态，所以没有实际影响BWE决策
""")

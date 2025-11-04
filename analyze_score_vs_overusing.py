#!/usr/bin/env python3
"""
Analyze relationship between Score>=90 and BWState: Overusing
"""

import re
import numpy as np
import matplotlib.pyplot as plt

log_file = '/home/wuq/webrtc-local/webrtc_config_results/sender_local.log'

# Parse both gain factor and BWE decision entries
gain_entries = []  # (line_num, score, gain)
bwe_entries = []   # (line_num, bw_state, strategy, target_bps)

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
        match = re.search(r'\[BWE-DECISION\].*BWState:\s*(\w+),\s*Strategy:\s*([^,]+),.*NewTarget:\s*([\d.]+)\s*bps', line)
        if match:
            bw_state = match.group(1)
            strategy = match.group(2)
            target_bps = float(match.group(3))
            bwe_entries.append((line_num, bw_state, strategy, target_bps))

print(f"✓ Found {len(gain_entries)} Gain Factor entries")
print(f"✓ Found {len(bwe_entries)} BWE Decision entries")

# Statistics
bw_states = [entry[1] for entry in bwe_entries]
from collections import Counter
bw_state_counts = Counter(bw_states)

print("\n" + "="*80)
print("BWState DISTRIBUTION")
print("="*80)
for state, count in sorted(bw_state_counts.items(), key=lambda x: x[1], reverse=True):
    percentage = count / len(bwe_entries) * 100
    print(f"  {state:15s}: {count:4d} ({percentage:5.2f}%)")

# Find overusing events
overusing_lines = [entry[0] for entry in bwe_entries if entry[1] == 'Overusing']
print(f"\n✓ Found {len(overusing_lines)} Overusing events at lines: {overusing_lines}")

# Find high score events (score >= 90)
high_score_entries = [(line, score, gain) for line, score, gain in gain_entries if score >= 90]
high_score_lines = [entry[0] for entry in high_score_entries]

print(f"✓ Found {len(high_score_entries)} High Score (>=90) events")

# Analyze correlation
print("\n" + "="*80)
print("CORRELATION ANALYSIS: Score >= 90 vs BWState: Overusing")
print("="*80)

# For each high score, find nearest BWE decision
window = 100  # Search within ±100 lines

high_score_with_overusing = 0
high_score_bw_states = []

print(f"\nSearching for BWState near high scores (within ±{window} lines)...")
print(f"{'Score Line':<12} {'Score':<10} {'Nearest BWE':<15} {'BWState':<15} {'Distance':<10}")
print("-" * 80)

for hs_line, score, gain in high_score_entries[:30]:  # Show first 30
    # Find nearest BWE decision
    min_distance = float('inf')
    nearest_bwe = None
    nearest_state = None

    for bwe_line, bw_state, strategy, target in bwe_entries:
        distance = abs(bwe_line - hs_line)
        if distance < min_distance and distance <= window:
            min_distance = distance
            nearest_bwe = bwe_line
            nearest_state = bw_state

    high_score_bw_states.append(nearest_state)

    if nearest_state == 'Overusing':
        high_score_with_overusing += 1
        marker = " ← OVERUSING!"
    else:
        marker = ""

    print(f"{hs_line:<12} {score:<10.2f} {nearest_bwe if nearest_bwe else 'N/A':<15} "
          f"{nearest_state if nearest_state else 'N/A':<15} {min_distance if nearest_bwe else 'N/A':<10}{marker}")

if len(high_score_entries) > 30:
    print(f"... (showing first 30 of {len(high_score_entries)})")

# Reverse: for each overusing, find nearest score
overusing_with_high_score = 0
overusing_scores = []

print(f"\n\nSearching for Scores near Overusing events (within ±{window} lines)...")
print(f"{'Overusing Line':<15} {'Nearest Score Line':<20} {'Score':<10} {'Distance':<10}")
print("-" * 80)

for overuse_line in overusing_lines:
    # Find nearest score
    min_distance = float('inf')
    nearest_score_line = None
    nearest_score = None

    for gain_line, score, gain in gain_entries:
        distance = abs(gain_line - overuse_line)
        if distance < min_distance and distance <= window:
            min_distance = distance
            nearest_score_line = gain_line
            nearest_score = score

    overusing_scores.append(nearest_score if nearest_score else np.nan)

    if nearest_score and nearest_score >= 90:
        overusing_with_high_score += 1
        marker = " ← HIGH SCORE!"
    elif nearest_score and nearest_score >= 70:
        marker = " (score>=70)"
    else:
        marker = ""

    print(f"{overuse_line:<15} {nearest_score_line if nearest_score_line else 'N/A':<20} "
          f"{nearest_score if nearest_score else 'N/A':<10.2f} {min_distance if nearest_score_line else 'N/A':<10}{marker}")

# Summary statistics
print("\n" + "="*80)
print("CORRELATION SUMMARY")
print("="*80)

print(f"\n1. High Scores (>=90) and Overusing:")
print(f"   Total high score events: {len(high_score_entries)}")
print(f"   High scores near Overusing: {high_score_with_overusing} ({high_score_with_overusing/max(len(high_score_entries),1)*100:.1f}%)")

bw_state_near_high_score = Counter([s for s in high_score_bw_states if s is not None])
print(f"\n   BWState distribution near high scores:")
for state, count in sorted(bw_state_near_high_score.items(), key=lambda x: x[1], reverse=True):
    percentage = count / len([s for s in high_score_bw_states if s is not None]) * 100
    print(f"     {state:15s}: {count:4d} ({percentage:5.1f}%)")

print(f"\n2. Overusing and High Scores:")
print(f"   Total Overusing events: {len(overusing_lines)}")
print(f"   Overusing near high scores (>=90): {overusing_with_high_score} ({overusing_with_high_score/max(len(overusing_lines),1)*100:.1f}%)")
print(f"   Overusing near medium scores (>=70): {sum(1 for s in overusing_scores if s and s >= 70)} "
      f"({sum(1 for s in overusing_scores if s and s >= 70)/max(len(overusing_lines),1)*100:.1f}%)")

valid_overusing_scores = [s for s in overusing_scores if not np.isnan(s)]
if valid_overusing_scores:
    print(f"\n   Score statistics near Overusing:")
    print(f"     Mean:   {np.mean(valid_overusing_scores):.2f}")
    print(f"     Median: {np.median(valid_overusing_scores):.2f}")
    print(f"     Min:    {np.min(valid_overusing_scores):.2f}")
    print(f"     Max:    {np.max(valid_overusing_scores):.2f}")

# Create visualization
fig, axes = plt.subplots(2, 2, figsize=(16, 10))
fig.suptitle('Score vs Overusing Correlation Analysis', fontsize=16, fontweight='bold')

# Plot 1: Timeline showing both scores and BWE states
ax1 = axes[0, 0]
# Extract scores and their positions
score_lines = [entry[0] for entry in gain_entries]
scores = [entry[1] for entry in gain_entries]
ax1.scatter(score_lines, scores, c='blue', s=1, alpha=0.3, label='Scores')

# Mark high scores
for line, score, _ in high_score_entries:
    ax1.scatter(line, score, c='red', s=20, marker='o', alpha=0.6)

# Mark overusing events
for overuse_line in overusing_lines:
    ax1.axvline(x=overuse_line, color='orange', linestyle='--', linewidth=2, alpha=0.7)

ax1.axhline(y=90, color='red', linestyle='--', linewidth=1.5, label='Score=90 threshold')
ax1.set_xlabel('Log Line Number', fontsize=11, fontweight='bold')
ax1.set_ylabel('Score', fontsize=11, fontweight='bold')
ax1.set_title('Timeline: Scores and Overusing Events', fontsize=12, fontweight='bold')
ax1.legend(['Scores', 'High Score (>=90)', 'Overusing Event', 'Score=90'], fontsize=9)
ax1.grid(True, alpha=0.3)

# Plot 2: BWState pie chart
ax2 = axes[0, 1]
states = list(bw_state_counts.keys())
counts = [bw_state_counts[s] for s in states]
colors = ['green', 'orange', 'blue'][:len(states)]
wedges, texts, autotexts = ax2.pie(counts, labels=states, autopct='%1.1f%%',
                                     colors=colors, startangle=90)
for autotext in autotexts:
    autotext.set_color('white')
    autotext.set_fontweight('bold')
    autotext.set_fontsize(11)
ax2.set_title(f'BWState Distribution\n(Total: {len(bwe_entries)} decisions)', fontsize=12, fontweight='bold')

# Plot 3: Score distribution near overusing
ax3 = axes[1, 0]
if valid_overusing_scores:
    ax3.hist(valid_overusing_scores, bins=20, color='orange', alpha=0.7, edgecolor='black')
    ax3.axvline(x=90, color='red', linestyle='--', linewidth=2, label='Score=90')
    ax3.axvline(x=np.mean(valid_overusing_scores), color='darkred', linestyle='--',
                linewidth=2, label=f'Mean={np.mean(valid_overusing_scores):.1f}')
    ax3.set_xlabel('Score (near Overusing events)', fontsize=11, fontweight='bold')
    ax3.set_ylabel('Frequency', fontsize=11, fontweight='bold')
    ax3.set_title(f'Score Distribution Near Overusing\n(n={len(valid_overusing_scores)})',
                  fontsize=12, fontweight='bold')
    ax3.legend()
    ax3.grid(True, alpha=0.3, axis='y')
else:
    ax3.text(0.5, 0.5, 'No data', ha='center', va='center', fontsize=14, transform=ax3.transAxes)

# Plot 4: BWState distribution near high scores
ax4 = axes[1, 1]
if bw_state_near_high_score:
    states_hs = list(bw_state_near_high_score.keys())
    counts_hs = [bw_state_near_high_score[s] for s in states_hs]
    colors_hs = {'Normal': 'green', 'Overusing': 'red', 'Underusing': 'blue'}
    bar_colors = [colors_hs.get(s, 'gray') for s in states_hs]
    bars = ax4.bar(states_hs, counts_hs, color=bar_colors, alpha=0.7, edgecolor='black')
    ax4.set_xlabel('BWState', fontsize=11, fontweight='bold')
    ax4.set_ylabel('Frequency', fontsize=11, fontweight='bold')
    ax4.set_title(f'BWState Near High Scores (>=90)\n(n={sum(counts_hs)})',
                  fontsize=12, fontweight='bold')
    ax4.grid(True, alpha=0.3, axis='y')

    # Add percentage labels
    for bar, count in zip(bars, counts_hs):
        height = bar.get_height()
        percentage = count / sum(counts_hs) * 100
        ax4.text(bar.get_x() + bar.get_width()/2., height,
                f'{count}\n({percentage:.1f}%)',
                ha='center', va='bottom', fontsize=10, fontweight='bold')
else:
    ax4.text(0.5, 0.5, 'No data', ha='center', va='center', fontsize=14, transform=ax4.transAxes)

plt.tight_layout()
plt.savefig('score_vs_overusing_correlation.png', dpi=150, bbox_inches='tight')
print("\n✓ Saved: score_vs_overusing_correlation.png")

print("\n" + "="*80)
print("KEY FINDINGS")
print("="*80)
print(f"""
1. Overusing事件非常少:
   - 总共只有 {len(overusing_lines)} 次 Overusing ({len(overusing_lines)/len(bwe_entries)*100:.2f}%)
   - 大部分时间 ({bw_state_counts.get('Normal', 0)/len(bwe_entries)*100:.1f}%) 处于 Normal 状态

2. Score >= 90 与 Overusing 的关系:
   - {len(high_score_entries)} 次高分事件中，{high_score_with_overusing} 次与Overusing相关 ({high_score_with_overusing/max(len(high_score_entries),1)*100:.1f}%)
   - 说明：高Score并不总是导致Overusing检测

3. Overusing 发生时的Score:
   - 平均Score: {np.mean(valid_overusing_scores):.1f} (中等水平)
   - {overusing_with_high_score} / {len(overusing_lines)} 次Overusing发生在高Score (>=90) 附近

4. 结论:
   - Score >= 90 表示资源紧张（ratio低）
   - Overusing 是基于delay的检测机制
   - 两者有一定相关性，但不是强相关
   - 高Score可以作为预防性信号，在Overusing发生前降低增长率
""")

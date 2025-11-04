#!/usr/bin/env python3
import re
import numpy as np
from scipy import stats

# Parse log using MonoTime alignment
monotime_to_ratio = {}
monotime_to_saturation = {}
monotime_to_bitrate = {}

with open('/home/wuq/webrtc-local/webrtc_config_results/sender_local.log', 'r') as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        # Extract monotime
        mono_match = re.search(r'MonoTime:\s*(\d+)', line)
        if mono_match:
            monotime = int(mono_match.group(1))

            # Check for acked bitrate
            bwe_match = re.search(r'AckedBitrate:\s*(-?\d+)', line)
            if bwe_match:
                bitrate = int(bwe_match.group(1))
                if bitrate > 0:
                    monotime_to_bitrate[monotime] = bitrate

        # Extract smoothed ratio
        ratio_match = re.search(r'smoothed:\s*([\d.]+)\)', line)
        if ratio_match:
            ratio = float(ratio_match.group(1))
            # Find nearest monotime
            for j in range(max(0, i-5), min(len(lines), i+6)):
                mono_match2 = re.search(r'MonoTime:\s*(\d+)', lines[j])
                if mono_match2:
                    monotime = int(mono_match2.group(1))
                    monotime_to_ratio[monotime] = ratio
                    break

        # Extract idle score and calculate saturation
        idle_match = re.search(r'IdleScore:\s*([\d.]+)', line)
        if idle_match:
            idle_score = float(idle_match.group(1))
            saturation = 100 - idle_score
            # Find nearest monotime
            for j in range(max(0, i-5), min(len(lines), i+6)):
                mono_match2 = re.search(r'MonoTime:\s*(\d+)', lines[j])
                if mono_match2:
                    monotime = int(mono_match2.group(1))
                    monotime_to_saturation[monotime] = saturation
                    break

# Match data by monotime
ratio_bitrate_pairs = []
saturation_bitrate_pairs = []

for mono_ratio, ratio in monotime_to_ratio.items():
    for mono_bwe, bwe in monotime_to_bitrate.items():
        if abs(mono_ratio - mono_bwe) <= 100:
            ratio_bitrate_pairs.append((ratio, bwe))
            break

for mono_sat, sat in monotime_to_saturation.items():
    for mono_bwe, bwe in monotime_to_bitrate.items():
        if abs(mono_sat - mono_bwe) <= 100:
            saturation_bitrate_pairs.append((sat, bwe))
            break

ratios = np.array([p[0] for p in ratio_bitrate_pairs])
bitrates_r = np.array([p[1] for p in ratio_bitrate_pairs])
saturations = np.array([p[0] for p in saturation_bitrate_pairs])
bitrates_s = np.array([p[1] for p in saturation_bitrate_pairs])

print("=" * 80)
print("Pearson (线性相关) vs Spearman (单调相关) 对比")
print("=" * 80)

# Original Ratio
pearson_ratio, _ = stats.pearsonr(ratios, bitrates_r)
spearman_ratio, _ = stats.spearmanr(ratios, bitrates_r)

print(f"\n1. 原始 Smoothed Ratio vs Acked Bitrate")
print(f"   数据点: {len(ratio_bitrate_pairs)}")
print(f"   Pearson  (线性):  R = {pearson_ratio:+.4f}")
print(f"   Spearman (单调):  ρ = {spearman_ratio:+.4f}")
print(f"   差异: {abs(spearman_ratio) - abs(pearson_ratio):+.4f}")

# Saturation Score
pearson_sat, _ = stats.pearsonr(saturations, bitrates_s)
spearman_sat, _ = stats.spearmanr(saturations, bitrates_s)

print(f"\n2. Saturation Score (sigmoid转换) vs Acked Bitrate")
print(f"   数据点: {len(saturation_bitrate_pairs)}")
print(f"   Pearson  (线性):  R = {pearson_sat:+.4f}")
print(f"   Spearman (单调):  ρ = {spearman_sat:+.4f}")
print(f"   差异: {spearman_sat - pearson_sat:+.4f}")

# Test all transformations with both correlation methods
print("\n" + "=" * 80)
print("各种变换的 Pearson vs Spearman 对比")
print("=" * 80)

transformations = [
    ('原始 Ratio', ratios, bitrates_r),
    ('Saturation (sigmoid转换)', saturations, bitrates_s),
    ('Saturation^2', saturations ** 2, bitrates_s),
    ('Saturation^3', saturations ** 3, bitrates_s),
    ('Saturation^4', saturations ** 4, bitrates_s),
    ('Saturation^5', saturations ** 5, bitrates_s),
    ('Saturation^6', saturations ** 6, bitrates_s),
]

print(f"\n{'变换方式':<30s} {'Pearson':>10s} {'Spearman':>10s} {'差异':>10s}")
print("-" * 80)

results = []
for name, x, y in transformations:
    pearson, _ = stats.pearsonr(x, y)
    spearman, _ = stats.spearmanr(x, y)
    diff = spearman - pearson
    results.append((name, pearson, spearman, diff))
    print(f"{name:<30s} {pearson:>+10.4f} {spearman:>+10.4f} {diff:>+10.4f}")

# Find best correlation
best_pearson = max(results, key=lambda x: abs(x[1]))
best_spearman = max(results, key=lambda x: abs(x[2]))

print("\n" + "=" * 80)
print("最优结果")
print("=" * 80)
print(f"\nPearson 最高:  {best_pearson[0]:<30s} R = {best_pearson[1]:+.4f}")
print(f"Spearman 最高: {best_spearman[0]:<30s} ρ = {best_spearman[2]:+.4f}")

# Key insight
print("\n" + "=" * 80)
print("关键发现")
print("=" * 80)
print(f"\n1. 原始Ratio:")
print(f"   Spearman = {spearman_ratio:+.4f} vs Pearson = {pearson_ratio:+.4f}")
print(f"   → Spearman更高说明存在强单调关系，但非完全线性")

print(f"\n2. Sigmoid转换后的Saturation:")
print(f"   Spearman = {spearman_sat:+.4f} vs Pearson = {pearson_sat:+.4f}")
print(f"   → 单调性{'增强' if spearman_sat > pearson_sat else '减弱'}")

print(f"\n3. 高阶幂变换:")
print(f"   Saturation^6: Spearman = {results[-1][2]:+.4f}, Pearson = {results[-1][1]:+.4f}")
print(f"   → 幂变换使线性拟合更好，但{'损害' if results[-1][2] < results[-1][1] else '保持'}了单调性")

print(f"\n4. 推荐:")
if abs(best_spearman[2]) > abs(best_pearson[1]):
    print(f"   使用 Spearman 评估，最佳变换: {best_spearman[0]} (ρ = {best_spearman[2]:+.4f})")
else:
    print(f"   使用 Pearson 评估，最佳变换: {best_pearson[0]} (R = {best_pearson[1]:+.4f})")

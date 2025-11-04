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

# Match data by monotime (within 100ms tolerance)
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

# Calculate correlations
print("=" * 60)
print("相关性分析对比")
print("=" * 60)

if len(ratio_bitrate_pairs) > 0:
    ratios = np.array([p[0] for p in ratio_bitrate_pairs])
    bitrates_r = np.array([p[1] for p in ratio_bitrate_pairs])
    corr_ratio, _ = stats.pearsonr(ratios, bitrates_r)
    print(f"\n1. Smoothed Ratio vs Acked Bitrate:")
    print(f"   数据点数: {len(ratio_bitrate_pairs)}")
    print(f"   相关系数: R = {corr_ratio:+.4f}")
    print(f"   解释: 负相关（低ratio → 高bitrate）")

if len(saturation_bitrate_pairs) > 0:
    saturations = np.array([p[0] for p in saturation_bitrate_pairs])
    bitrates_s = np.array([p[1] for p in saturation_bitrate_pairs])
    corr_sat, _ = stats.pearsonr(saturations, bitrates_s)
    print(f"\n2. Saturation Score vs Acked Bitrate:")
    print(f"   数据点数: {len(saturation_bitrate_pairs)}")
    print(f"   相关系数: R = {corr_sat:+.4f}")
    print(f"   解释: Saturation = 100 - IdleScore")
    print(f"          IdleScore = sigmoid(15×(ratio-0.5))")
    print(f"          正相关（高饱和度 → 高bitrate）")

print(f"\n3. 对比:")
print(f"   原始 ratio:           R = {corr_ratio:+.4f}")
print(f"   Sigmoid转换后 (饱和度): R = {corr_sat:+.4f}")
print(f"   相关性提升:            {abs(corr_sat) - abs(corr_ratio):+.4f}")

# Additional transformations for comparison
print("\n" + "=" * 60)
print("各种变换方式的相关性对比")
print("=" * 60)

transformations = {
    '原始 Ratio (无转换)': (ratios, bitrates_r),
    'Sigmoid转换 (Saturation Score)': (saturations, bitrates_s),
    'Saturation^2': (saturations ** 2, bitrates_s),
    'Saturation^3': (saturations ** 3, bitrates_s),
    'Saturation^4': (saturations ** 4, bitrates_s),
    'Saturation^5': (saturations ** 5, bitrates_s),
    'Saturation^6': (saturations ** 6, bitrates_s),
}

results = []
for name, (x, y) in transformations.items():
    if len(x) > 0 and len(y) > 0:
        corr, _ = stats.pearsonr(x, y)
        results.append((name, corr))

for i, (name, corr) in enumerate(results, 1):
    print(f"{i}. {name:35s}: R = {corr:+.4f}")

print("\n总结:")
print(f"  • Sigmoid转换将相关性从 {corr_ratio:.4f} 变为 {corr_sat:+.4f}")
print(f"  • 再对Saturation做幂变换可进一步提升到 R = {results[-1][1]:+.4f} (x^6)")
print(f"  • 总提升: {results[-1][1] - corr_ratio:+.4f}")

#!/usr/bin/env python3
import re
import numpy as np
from scipy import stats
from sklearn.preprocessing import PolynomialFeatures
from sklearn.linear_model import LinearRegression
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

print(f"总数据点: {len(data)}")
print(f"Ratio 实际范围: [{ratios.min():.3f}, {ratios.max():.3f}]")
print(f"Bitrate 范围: [{bitrates.min():.2f}, {bitrates.max():.2f}] Mbps\n")

# 统计各范围的数据
print("Ratio分布统计:")
for lower, upper in [(0, 0.5), (0.5, 1.0), (1.0, 1.5), (1.5, 2.0)]:
    mask = (ratios >= lower) & (ratios < upper)
    count = np.sum(mask)
    pct = 100 * count / len(ratios)
    if count > 0:
        avg_bitrate = np.mean(bitrates[mask])
        print(f"  [{lower:.1f}, {upper:.1f}): {count:5d} 点 ({pct:5.2f}%), 平均比特率: {avg_bitrate:.2f} Mbps")
    else:
        print(f"  [{lower:.1f}, {upper:.1f}): {count:5d} 点 ({pct:5.2f}%)")

# Binned analysis - 强制使用0-2范围
bins = np.linspace(0, 2, 41)  # 0 to 2, 每0.05一个bin
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

    # 只要有数据点就画，即使只有1个
    if count >= 1:
        bin_centers.append((bins[b-1] + bins[b]) / 2)
        medians.append(np.median(bitrates[mask]))
        if count >= 3:
            p25s.append(np.percentile(bitrates[mask], 25))
            p75s.append(np.percentile(bitrates[mask], 75))
        else:
            # 数据点太少，不画分位数
            p25s.append(np.nan)
            p75s.append(np.nan)
    else:
        bin_centers.append((bins[b-1] + bins[b]) / 2)
        medians.append(np.nan)
        p25s.append(np.nan)
        p75s.append(np.nan)

bin_centers = np.array(bin_centers)
medians = np.array(medians)
p25s = np.array(p25s)
p75s = np.array(p75s)

print(f"\n总bins: {len(bins)-1}")
print(f"有数据的bins: {np.sum(~np.isnan(medians))}")

# Correlation只用有数据的部分
valid_mask = ~np.isnan(medians)
valid_bins = bin_centers[valid_mask]
valid_medians = medians[valid_mask]

if len(valid_bins) > 2:
    pearson_binned, _ = stats.pearsonr(valid_bins, valid_medians)

    # Quadratic fit
    X_bin = valid_bins.reshape(-1, 1)
    poly_bin = PolynomialFeatures(degree=2)
    X_poly_bin = poly_bin.fit_transform(X_bin)
    model_quad = LinearRegression()
    model_quad.fit(X_poly_bin, valid_medians)
    r2_quad = model_quad.score(X_poly_bin, valid_medians)

    a, b, c = model_quad.coef_[2], model_quad.coef_[1], model_quad.intercept_

    print(f"\n分箱后 Pearson: r = {pearson_binned:+.4f}")
    print(f"二次拟合 R²: {r2_quad:.4f}")
    print(f"二次方程: y = {a:.3f}x² + {b:.3f}x + {c:.2f}\n")

# Plot
fig, ax = plt.subplots(figsize=(14, 7))

# Plot median and percentiles (只画有效数据)
valid_p25_mask = ~np.isnan(p25s)
ax.plot(bin_centers[valid_mask], medians[valid_mask], 'ro-', linewidth=2.5,
        markersize=5, label='Median Bitrate', zorder=3)
ax.fill_between(bin_centers[valid_p25_mask], p25s[valid_p25_mask], p75s[valid_p25_mask],
                alpha=0.3, color='red', label='25th-75th Percentile', zorder=2)

# Plot quadratic fit curve (整个0-2范围)
x_smooth = np.linspace(0, 2, 200)
y_smooth = a * x_smooth**2 + b * x_smooth + c
ax.plot(x_smooth, y_smooth, 'b--', linewidth=2.5,
        label=f'Quadratic Fit: y={a:.2f}x²+{b:.2f}x+{c:.2f} (R²={r2_quad:.4f})', zorder=1)

# Add scatter plot for all raw data
sample_size = min(3000, len(ratios))
sample_idx = np.random.choice(len(ratios), sample_size, replace=False)
ax.scatter(ratios[sample_idx], bitrates[sample_idx], alpha=0.1, s=5, color='gray',
           label=f'Raw data (sampled {sample_size}/{len(ratios)})', zorder=0)

# Mark regions
ax.axvspan(0, 0.5, alpha=0.05, color='green', label='Low ratio (86.4% of data)')
ax.axvspan(1.0, 2.0, alpha=0.05, color='orange', label='High ratio (0.2% of data)')

ax.set_xlabel('Smoothed Ratio', fontsize=14, fontweight='bold')
ax.set_ylabel('Acked Bitrate (Mbps)', fontsize=14, fontweight='bold')
ax.set_title(f'Smoothed Ratio vs Acked Bitrate (Full Range 0-2)\nPearson r = {pearson_binned:+.4f}, R² = {r2_quad:.4f}',
             fontsize=15, fontweight='bold')
ax.set_xlim(0, 2)
ax.set_ylim(0, max(bitrates.max() * 1.05, y_smooth.max() * 1.05))
ax.grid(True, alpha=0.3)
ax.legend(fontsize=10, loc='upper right')

plt.tight_layout()
plt.savefig('/home/wuq/webrtc-local/ratio_vs_bitrate_full_0to2.png', dpi=150, bbox_inches='tight')
print(f"完整范围图已保存到: ratio_vs_bitrate_full_0to2.png")

# Show detailed statistics for high ratio region
high_ratio_mask = ratios >= 1.0
if np.sum(high_ratio_mask) > 0:
    print(f"\nRatio ≥ 1.0 的详细数据 ({np.sum(high_ratio_mask)} 个点):")
    high_data = sorted([(ratios[i], bitrates[i]) for i in range(len(ratios)) if high_ratio_mask[i]])
    for i, (r, b) in enumerate(high_data, 1):
        print(f"  {i:2d}. Ratio={r:.4f}, Bitrate={b:.2f} Mbps")

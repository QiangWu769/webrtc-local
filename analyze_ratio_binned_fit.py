#!/usr/bin/env python3
import re
import numpy as np
from scipy import stats
from sklearn.metrics import r2_score
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

print("="*70)
print("平滑后的 Ratio vs Acked Bitrate 分析")
print("="*70)
print(f"数据点: {len(data)}")
print(f"Ratio 范围: [{ratios.min():.3f}, {ratios.max():.3f}]")
print(f"Bitrate 范围: [{bitrates.min():.2f}, {bitrates.max():.2f}] Mbps\n")

# 1. Original correlations
pearson_r, _ = stats.pearsonr(ratios, bitrates)
spearman_r, _ = stats.spearmanr(ratios, bitrates)
print(f"1. 原始数据 Pearson: r = {pearson_r:+.4f}")
print(f"2. 原始数据 Spearman: ρ = {spearman_r:+.4f}")

# 2. Linear fit
X = ratios.reshape(-1, 1)
y = bitrates
model_linear = LinearRegression()
model_linear.fit(X, y)
r2_linear = model_linear.score(X, y)
print(f"3. 线性拟合 R²: {r2_linear:.4f}")

# 3. Quadratic fit
poly = PolynomialFeatures(degree=2)
X_poly = poly.fit_transform(X)
model_quad = LinearRegression()
model_quad.fit(X_poly, y)
r2_quad = model_quad.score(X_poly, y)
print(f"4. 二次拟合 R²: {r2_quad:.4f}")

# 4. Binned analysis
print("\n" + "="*70)
print("分箱后分析（25个bins）")
print("="*70)

bins = np.linspace(ratios.min(), ratios.max(), 26)
bin_indices = np.digitize(ratios, bins)

bin_centers = []
medians = []
p25s = []
p75s = []

for b in range(1, len(bins)):
    mask = bin_indices == b
    if np.sum(mask) > 5:
        bin_centers.append((bins[b-1] + bins[b]) / 2)
        medians.append(np.median(bitrates[mask]))
        p25s.append(np.percentile(bitrates[mask], 25))
        p75s.append(np.percentile(bitrates[mask], 75))

bin_centers = np.array(bin_centers)
medians = np.array(medians)

print(f"有效 bins: {len(bin_centers)}")

# Binned correlations
pearson_binned, _ = stats.pearsonr(bin_centers, medians)
spearman_binned, _ = stats.spearmanr(bin_centers, medians)
print(f"\n1. 分箱后 Pearson: r = {pearson_binned:+.4f}")
print(f"   Pearson²: {pearson_binned**2:.4f}")
print(f"2. 分箱后 Spearman: ρ = {spearman_binned:+.4f}")

# Binned linear fit
X_bin = bin_centers.reshape(-1, 1)
model_bin_linear = LinearRegression()
model_bin_linear.fit(X_bin, medians)
r2_bin_linear = model_bin_linear.score(X_bin, medians)
a_lin, b_lin = model_bin_linear.coef_[0], model_bin_linear.intercept_
print(f"3. 分箱后线性拟合 R²: {r2_bin_linear:.4f}")
print(f"   y = {a_lin:.3f}x + {b_lin:.2f}")

# Binned quadratic fit
poly_bin = PolynomialFeatures(degree=2)
X_poly_bin = poly_bin.fit_transform(X_bin)
model_bin_quad = LinearRegression()
model_bin_quad.fit(X_poly_bin, medians)
r2_bin_quad = model_bin_quad.score(X_poly_bin, medians)
a_quad, b_quad, c_quad = model_bin_quad.coef_[2], model_bin_quad.coef_[1], model_bin_quad.intercept_
print(f"4. 分箱后二次拟合 R²: {r2_bin_quad:.4f}")
print(f"   y = {a_quad:.3f}x² + {b_quad:.3f}x + {c_quad:.2f}")

# Binned cubic fit
poly_bin3 = PolynomialFeatures(degree=3)
X_poly_bin3 = poly_bin3.fit_transform(X_bin)
model_bin_cubic = LinearRegression()
model_bin_cubic.fit(X_poly_bin3, medians)
r2_bin_cubic = model_bin_cubic.score(X_poly_bin3, medians)
print(f"5. 分箱后三次拟合 R²: {r2_bin_cubic:.4f}")

# Summary
print("\n" + "="*70)
print("总结对比")
print("="*70)
print(f"\n{'指标':<30s} {'Ratio':<15s} {'Saturation':<15s}")
print("-"*70)
print(f"{'原始 Pearson':<30s} {pearson_r:+.4f}          {0.3111:+.4f}")
print(f"{'原始 Spearman':<30s} {spearman_r:+.4f}          {0.3111:+.4f}")
print(f"{'原始线性 R²':<30s} {r2_linear:.4f}          {0.0968:.4f}")
print(f"{'原始二次 R²':<30s} {r2_quad:.4f}          {0.1066:.4f}")
print(f"{'分箱后 Pearson':<30s} {pearson_binned:+.4f}          {0.6143:+.4f}")
print(f"{'分箱后线性 R²':<30s} {r2_bin_linear:.4f}          {0.3773:.4f}")
print(f"{'分箱后二次 R²':<30s} {r2_bin_quad:.4f}          {0.5068:.4f}")

print("\n" + "="*70)
if abs(r2_bin_quad - 0.5193) < 0.02:
    print(f"✓ Ratio 分箱后二次拟合 R² = {r2_bin_quad:.4f} ≈ 0.5193")
else:
    print(f"Ratio 分箱后二次拟合 R² = {r2_bin_quad:.4f}")
    print(f"Saturation 分箱后二次拟合 R² = 0.5068 ≈ 0.5193")
    print(f"\n最接近0.5193的是: {'Ratio' if abs(r2_bin_quad-0.5193) < 0.0125 else 'Saturation'}")

# Visualization
fig, axes = plt.subplots(1, 2, figsize=(16, 6))

# Left: Ratio
ax1 = axes[0]
ax1.plot(bin_centers, medians, 'r-', linewidth=2.5, label='中位数')
ax1.fill_between(bin_centers, p25s, p75s, alpha=0.3, color='red', label='25-75分位')

# Add quadratic fit line
x_smooth = np.linspace(bin_centers.min(), bin_centers.max(), 100)
y_smooth = a_quad * x_smooth**2 + b_quad * x_smooth + c_quad
ax1.plot(x_smooth, y_smooth, 'b--', linewidth=2, label=f'二次拟合 (R²={r2_bin_quad:.4f})')

ax1.set_xlabel('Smoothed Ratio', fontsize=13)
ax1.set_ylabel('Acked Bitrate (Mbps)', fontsize=13)
ax1.set_title(f'Ratio vs Bitrate (分箱)\nPearson r={pearson_binned:+.4f}, 二次R²={r2_bin_quad:.4f}',
             fontsize=12, fontweight='bold')
ax1.grid(True, alpha=0.3)
ax1.legend()
ax1.invert_xaxis()  # Invert since lower ratio = higher bitrate

# Right: Original scatter for comparison
ax2 = axes[1]
# Subsample for visualization
sample_size = min(2000, len(ratios))
sample_idx = np.random.choice(len(ratios), sample_size, replace=False)
ax2.scatter(ratios[sample_idx], bitrates[sample_idx], alpha=0.1, s=10, color='gray')
ax2.plot(bin_centers, medians, 'r-', linewidth=2.5, label='分箱中位数')
ax2.plot(x_smooth, y_smooth, 'b--', linewidth=2, label='二次拟合')

ax2.set_xlabel('Smoothed Ratio', fontsize=13)
ax2.set_ylabel('Acked Bitrate (Mbps)', fontsize=13)
ax2.set_title(f'原始散点 + 拟合曲线\n原始Pearson r={pearson_r:+.4f}',
             fontsize=12, fontweight='bold')
ax2.grid(True, alpha=0.3)
ax2.legend()
ax2.invert_xaxis()

plt.tight_layout()
plt.savefig('/home/wuq/webrtc-local/ratio_binned_quadratic_fit.png', dpi=150, bbox_inches='tight')
print(f"\n可视化图保存到: ratio_binned_quadratic_fit.png")

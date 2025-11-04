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

print(f"数据点: {len(data)}")
print(f"Ratio 范围: [{ratios.min():.3f}, {ratios.max():.3f}]")
print(f"Bitrate 范围: [{bitrates.min():.2f}, {bitrates.max():.2f}] Mbps\n")

# Binned analysis
bins = np.linspace(0, 2, 41)  # 0 to 2, 40 bins
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
p25s = np.array(p25s)
p75s = np.array(p75s)

# Correlations
pearson_binned, _ = stats.pearsonr(bin_centers, medians)

# Quadratic fit
X_bin = bin_centers.reshape(-1, 1)
poly_bin = PolynomialFeatures(degree=2)
X_poly_bin = poly_bin.fit_transform(X_bin)
model_quad = LinearRegression()
model_quad.fit(X_poly_bin, medians)
r2_quad = model_quad.score(X_poly_bin, medians)

a, b, c = model_quad.coef_[2], model_quad.coef_[1], model_quad.intercept_

print(f"分箱后 Pearson: r = {pearson_binned:+.4f}")
print(f"二次拟合 R²: {r2_quad:.4f}")
print(f"二次方程: y = {a:.3f}x² + {b:.3f}x + {c:.2f}\n")

# Plot
fig, ax = plt.subplots(figsize=(12, 7))

# Plot median and percentiles
ax.plot(bin_centers, medians, 'r-', linewidth=3, label='Median Bitrate', zorder=3)
ax.fill_between(bin_centers, p25s, p75s, alpha=0.3, color='red', label='25th-75th Percentile', zorder=2)

# Plot quadratic fit
x_smooth = np.linspace(0, 2, 200)
y_smooth = a * x_smooth**2 + b * x_smooth + c
ax.plot(x_smooth, y_smooth, 'b--', linewidth=2.5,
        label=f'Quadratic Fit: y = {a:.3f}x² + {b:.3f}x + {c:.2f}', zorder=1)

ax.set_xlabel('Smoothed Ratio', fontsize=14, fontweight='bold')
ax.set_ylabel('Acked Bitrate (Mbps)', fontsize=14, fontweight='bold')
ax.set_title(f'Smoothed Ratio vs Acked Bitrate\nPearson r = {pearson_binned:+.4f}, R² = {r2_quad:.4f}',
             fontsize=15, fontweight='bold')
ax.set_xlim(0, 2)
ax.grid(True, alpha=0.3)
ax.legend(fontsize=11, loc='best')

plt.tight_layout()
plt.savefig('/home/wuq/webrtc-local/ratio_vs_bitrate_0to2.png', dpi=150, bbox_inches='tight')
print(f"图表已保存到: ratio_vs_bitrate_0to2.png")

# Create comparison plot with Saturation
fig, axes = plt.subplots(1, 2, figsize=(16, 6))

# Left: Ratio (0-2)
ax1 = axes[0]
ax1.plot(bin_centers, medians, 'r-', linewidth=3)
ax1.fill_between(bin_centers, p25s, p75s, alpha=0.3, color='red')
ax1.plot(x_smooth, y_smooth, 'b--', linewidth=2.5)
ax1.set_xlabel('Smoothed Ratio', fontsize=13, fontweight='bold')
ax1.set_ylabel('Acked Bitrate (Mbps)', fontsize=13, fontweight='bold')
ax1.set_title(f'Ratio vs Bitrate\nr={pearson_binned:+.4f}, R²={r2_quad:.4f}',
             fontsize=13, fontweight='bold')
ax1.set_xlim(0, 2)
ax1.grid(True, alpha=0.3)

# Right: Saturation (0-100)
# Parse saturation data
monotime_to_saturation = {}
with open('/home/wuq/webrtc-local/webrtc_config_results/sender_local.log', 'r') as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        idle_match = re.search(r'IdleScore:\s*([\d.]+)', line)
        if idle_match:
            idle_score = float(idle_match.group(1))
            saturation = 100 - idle_score
            for j in range(max(0, i-5), min(len(lines), i+6)):
                mono_match2 = re.search(r'MonoTime:\s*(\d+)', lines[j])
                if mono_match2:
                    monotime = int(mono_match2.group(1))
                    monotime_to_saturation[monotime] = saturation
                    break

sat_data = []
for mono_sat, sat in monotime_to_saturation.items():
    for mono_bwe, bwe in monotime_to_bitrate.items():
        if abs(mono_sat - mono_bwe) <= 100:
            sat_data.append((sat, bwe))
            break

saturations = np.array([d[0] for d in sat_data])
bitrates_sat = np.array([d[1] for d in sat_data]) / 1e6

bins_sat = np.linspace(0, 100, 26)
bin_indices_sat = np.digitize(saturations, bins_sat)

bin_centers_sat = []
medians_sat = []
p25s_sat = []
p75s_sat = []

for b in range(1, len(bins_sat)):
    mask = bin_indices_sat == b
    if np.sum(mask) > 5:
        bin_centers_sat.append((bins_sat[b-1] + bins_sat[b]) / 2)
        medians_sat.append(np.median(bitrates_sat[mask]))
        p25s_sat.append(np.percentile(bitrates_sat[mask], 25))
        p75s_sat.append(np.percentile(bitrates_sat[mask], 75))

bin_centers_sat = np.array(bin_centers_sat)
medians_sat = np.array(medians_sat)

pearson_sat, _ = stats.pearsonr(bin_centers_sat, medians_sat)

X_sat = bin_centers_sat.reshape(-1, 1)
poly_sat = PolynomialFeatures(degree=2)
X_poly_sat = poly_sat.fit_transform(X_sat)
model_sat = LinearRegression()
model_sat.fit(X_poly_sat, medians_sat)
r2_sat = model_sat.score(X_poly_sat, medians_sat)

ax2 = axes[1]
ax2.plot(bin_centers_sat, medians_sat, 'r-', linewidth=3)
ax2.fill_between(bin_centers_sat, p25s_sat, p75s_sat, alpha=0.3, color='red')

x_sat_smooth = np.linspace(0, 100, 200)
a_sat, b_sat, c_sat = model_sat.coef_[2], model_sat.coef_[1], model_sat.intercept_
y_sat_smooth = a_sat * x_sat_smooth**2 + b_sat * x_sat_smooth + c_sat
ax2.plot(x_sat_smooth, y_sat_smooth, 'b--', linewidth=2.5)

ax2.set_xlabel('Saturation Score (%)', fontsize=13, fontweight='bold')
ax2.set_ylabel('Acked Bitrate (Mbps)', fontsize=13, fontweight='bold')
ax2.set_title(f'Saturation vs Bitrate\nr={pearson_sat:+.4f}, R²={r2_sat:.4f}',
             fontsize=13, fontweight='bold')
ax2.set_xlim(0, 100)
ax2.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('/home/wuq/webrtc-local/ratio_vs_saturation_comparison.png', dpi=150, bbox_inches='tight')
print(f"对比图已保存到: ratio_vs_saturation_comparison.png")

print("\n" + "="*70)
print("最终结论")
print("="*70)
print(f"\n{'指标':<30s} {'Ratio (0-2)':<20s} {'Saturation (0-100)':<20s}")
print("-"*70)
print(f"{'分箱后 Pearson':<30s} {pearson_binned:+.4f}              {pearson_sat:+.4f}")
print(f"{'分箱后二次拟合 R²':<30s} {r2_quad:.4f}              {r2_sat:.4f}")
print(f"{'相关性强度':<30s} {'非常强':<20s} {'中等':<20s}")

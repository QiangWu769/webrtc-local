#!/usr/bin/env python3
import re
import numpy as np
from scipy import stats
from sklearn.metrics import r2_score
from sklearn.preprocessing import PolynomialFeatures
from sklearn.linear_model import LinearRegression

# Parse with MonoTime matching
monotime_to_saturation = {}
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

# Match by monotime
data = []
for mono_sat, sat in monotime_to_saturation.items():
    for mono_bwe, bwe in monotime_to_bitrate.items():
        if abs(mono_sat - mono_bwe) <= 100:
            data.append((sat, bwe))
            break

saturations = np.array([d[0] for d in data])
bitrates = np.array([d[1] for d in data]) / 1e6

print(f"MonoTime匹配数据点: {len(data)}\n")

# Test all possibilities
print("="*70)
print("所有可能的相关性指标")
print("="*70)

# 1. Original Pearson
pearson_r, _ = stats.pearsonr(saturations, bitrates)
print(f"1. Pearson 相关系数: r = {pearson_r:+.4f}")
print(f"   Pearson²: {pearson_r**2:.4f}")

# 2. Spearman
spearman_r, _ = stats.spearmanr(saturations, bitrates)
print(f"2. Spearman 相关系数: ρ = {spearman_r:+.4f}")
print(f"   Spearman²: {spearman_r**2:.4f}")

# 3. Linear R²
X = saturations.reshape(-1, 1)
y = bitrates
model = LinearRegression()
model.fit(X, y)
r2_linear = model.score(X, y)
print(f"3. 线性拟合 R²: {r2_linear:.4f}")

# 4. Quadratic R²
poly = PolynomialFeatures(degree=2)
X_poly = poly.fit_transform(X)
model_quad = LinearRegression()
model_quad.fit(X_poly, y)
r2_quad = model_quad.score(X_poly, y)
a, b, c = model_quad.coef_[2], model_quad.coef_[1], model_quad.intercept_
print(f"4. 二次拟合 R²: {r2_quad:.4f}")
print(f"   y = {a:.4f}x² + {b:.4f}x + {c:.2f}")

# 5. Binned analysis
bins = np.linspace(saturations.min(), saturations.max(), 25)
bin_indices = np.digitize(saturations, bins)

bin_centers = []
medians = []

for b in range(1, len(bins)):
    mask = bin_indices == b
    if np.sum(mask) > 5:
        bin_centers.append((bins[b-1] + bins[b]) / 2)
        medians.append(np.median(bitrates[mask]))

bin_centers = np.array(bin_centers)
medians = np.array(medians)

pearson_binned, _ = stats.pearsonr(bin_centers, medians)
print(f"\n5. 分箱后 Pearson: r = {pearson_binned:+.4f}")
print(f"   Pearson²: {pearson_binned**2:.4f}")

# Binned quadratic
X_bin = bin_centers.reshape(-1, 1)
poly_bin = PolynomialFeatures(degree=2)
X_poly_bin = poly_bin.fit_transform(X_bin)
model_bin = LinearRegression()
model_bin.fit(X_poly_bin, medians)
r2_bin_quad = model_bin.score(X_poly_bin, medians)
a2, b2, c2 = model_bin.coef_[2], model_bin.coef_[1], model_bin.intercept_
print(f"6. 分箱后二次拟合 R²: {r2_bin_quad:.4f}")
print(f"   y = {a2:.4f}x² + {b2:.3f}x + {c2:.2f}")

# Check if it matches the trend line from the image
print(f"\n原图趋势线: y = 0.0012x² + (-0.059)x + 3.93")
print(f"对比我们的: y = {a2:.4f}x² + {b2:.3f}x + {c2:.2f}")

# Calculate what R would give R²=0.5193
print("\n" + "="*70)
print("如果 R²=0.5193, 那么 R = ±√0.5193 = ±0.7206")
print("="*70)

# List all candidates
print(f"\n所有候选值:")
candidates = [
    ("Pearson r", pearson_r),
    ("Pearson r²", pearson_r**2),
    ("Spearman ρ", spearman_r),
    ("Spearman ρ²", spearman_r**2),
    ("线性 R²", r2_linear),
    ("二次 R²", r2_quad),
    ("分箱 Pearson", pearson_binned),
    ("分箱 Pearson²", pearson_binned**2),
    ("分箱二次 R²", r2_bin_quad),
]

for name, val in candidates:
    diff = abs(val - 0.5193)
    marker = " *** 最接近！" if diff < 0.05 else ""
    print(f"  {name:20s}: {val:.4f} (差值: {diff:.4f}){marker}")

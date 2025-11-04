#!/usr/bin/env python3
import re
import numpy as np
from scipy import stats
from sklearn.metrics import r2_score
from sklearn.preprocessing import PolynomialFeatures
from sklearn.linear_model import LinearRegression

# Parse data
data = []
with open('/home/wuq/webrtc-local/webrtc_config_results/sender_local.log', 'r') as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        idle_match = re.search(r'IdleScore:\s*([\d.]+)', line)
        if idle_match:
            idle_score = float(idle_match.group(1))
            saturation = 100 - idle_score
            for j in range(max(0, i-5), min(len(lines), i+6)):
                bwe_match = re.search(r'AckedBitrate:\s*(-?\d+)', lines[j])
                if bwe_match:
                    bitrate = int(bwe_match.group(1))
                    if bitrate > 0:
                        data.append((saturation, bitrate))
                    break

saturations = np.array([d[0] for d in data])
bitrates = np.array([d[1] for d in data]) / 1e6

print("="*70)
print("原图相关性 R=0.5193 的来源分析")
print("="*70)

# 1. Pearson correlation (线性相关系数)
pearson_r, _ = stats.pearsonr(saturations, bitrates)
print(f"\n1. Pearson 相关系数: r = {pearson_r:+.4f}")

# 2. R² for linear fit (线性拟合的决定系数)
X = saturations.reshape(-1, 1)
y = bitrates
model_linear = LinearRegression()
model_linear.fit(X, y)
y_pred_linear = model_linear.predict(X)
r2_linear = r2_score(y, y_pred_linear)
print(f"2. 线性拟合 R²: {r2_linear:.4f}")
print(f"   模型: y = {model_linear.coef_[0]:.4f}x + {model_linear.intercept_:.4f}")

# 3. R² for quadratic fit (二次拟合的决定系数)
poly = PolynomialFeatures(degree=2)
X_poly = poly.fit_transform(X)
model_quad = LinearRegression()
model_quad.fit(X_poly, y)
y_pred_quad = model_quad.predict(X_poly)
r2_quad = r2_score(y, y_pred_quad)
print(f"3. 二次拟合 R²: {r2_quad:.4f}")
print(f"   模型: y = {model_quad.coef_[2]:.4f}x² + {model_quad.coef_[1]:.4f}x + {model_quad.intercept_:.4f}")

# 4. R² for cubic fit
poly3 = PolynomialFeatures(degree=3)
X_poly3 = poly3.fit_transform(X)
model_cubic = LinearRegression()
model_cubic.fit(X_poly3, y)
y_pred_cubic = model_cubic.predict(X_poly3)
r2_cubic = r2_score(y, y_pred_cubic)
print(f"4. 三次拟合 R²: {r2_cubic:.4f}")

# 5. Check with binned data (aggregated by saturation bins)
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

# Binned correlations
if len(bin_centers) > 2:
    pearson_binned, _ = stats.pearsonr(bin_centers, medians)
    print(f"\n5. 分箱后 Pearson 相关: r = {pearson_binned:+.4f}")

    # Binned quadratic R²
    X_binned = bin_centers.reshape(-1, 1)
    y_binned = medians
    poly_binned = PolynomialFeatures(degree=2)
    X_poly_binned = poly_binned.fit_transform(X_binned)
    model_binned = LinearRegression()
    model_binned.fit(X_poly_binned, y_binned)
    y_pred_binned = model_binned.predict(X_poly_binned)
    r2_binned = r2_score(y_binned, y_pred_binned)
    print(f"6. 分箱后二次拟合 R²: {r2_binned:.4f}")
    print(f"   模型: y = {model_binned.coef_[2]:.4f}x² + {model_binned.coef_[1]:.4f}x + {model_binned.intercept_:.4f}")

print("\n" + "="*70)
print("结论")
print("="*70)

if abs(r2_quad - 0.5193) < 0.01:
    print(f"\n✓ 找到了！原图的 R=0.5193 是二次拟合的 R² = {r2_quad:.4f}")
elif abs(r2_binned - 0.5193) < 0.01:
    print(f"\n✓ 找到了！原图的 R=0.5193 是分箱后二次拟合的 R² = {r2_binned:.4f}")
else:
    print(f"\n最接近0.5193的是:")
    candidates = [
        ("Pearson r", pearson_r),
        ("线性 R²", r2_linear),
        ("二次 R²", r2_quad),
        ("三次 R²", r2_cubic),
        ("分箱 Pearson", pearson_binned),
        ("分箱二次 R²", r2_binned),
    ]
    closest = min(candidates, key=lambda x: abs(x[1] - 0.5193))
    print(f"   {closest[0]}: {closest[1]:.4f} (差值: {abs(closest[1]-0.5193):.4f})")

print("\n重要区别:")
print("  • Pearson r (相关系数): 衡量线性关系强度，范围 [-1, 1]")
print("  • R² (决定系数): 模型解释的方差比例，范围 [0, 1]")
print(f"  • 本数据: Pearson r = {pearson_r:.4f}, 但二次拟合 R² = {r2_quad:.4f}")

#!/usr/bin/env python3
"""
Find optimal function to combine Saturation and Cellular_Ratio
Beyond simple weighted sum: explore nonlinear transformations
"""
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats
from sklearn.metrics import r2_score
from scipy.optimize import curve_fit

# Read data
data = []
with open('/home/wuq/webrtc-local/logcode/test0/verizon——ratio_data.txt', 'r') as f:
    for line in f:
        parts = line.strip().split()
        if len(parts) >= 4:
            tti = int(parts[0])
            requested = int(parts[1])
            allocated = int(parts[2])
            ratio = float(parts[3])
            data.append((tti, requested, allocated, ratio))

filtered_data = [(tti, req, alloc, ratio) for tti, req, alloc, ratio in data
                 if req > 0 and alloc > 0]

ttis = [x[0] for x in filtered_data]
requests = [x[1] for x in filtered_data]
allocations = [x[2] for x in filtered_data]
ratios = [min(x[3], 2.0) for x in filtered_data]

# Create continuous time
continuous_time = []
time_offset = 0
prev_tti = ttis[0]

for tti in ttis:
    if tti < prev_tti and (prev_tti - tti) > 5000:
        time_offset += 10240
    continuous_time.append(tti + time_offset)
    prev_tti = tti

# Calculate bandwidth
bandwidth = []
for i in range(1, len(continuous_time)):
    diff = continuous_time[i] - continuous_time[i-1]
    if diff > 0:
        bw = allocations[i] / diff
        bandwidth.append(bw)
    else:
        bandwidth.append(0)
bandwidth.insert(0, 0)

# Calculate saturation
window_size = 10
saturation_list = []
cellular_ratio_list = []
bandwidth_list = []

for i in range(window_size * 2, len(filtered_data)):
    recent_alloc = allocations[i-window_size:i]
    prev_alloc = allocations[i-window_size*2:i-window_size]
    recent_req = requests[i-window_size:i]
    prev_req = requests[i-window_size*2:i-window_size]

    avg_recent_alloc = np.mean(recent_alloc)
    avg_prev_alloc = np.mean(prev_alloc)
    avg_recent_req = np.mean(recent_req)
    avg_prev_req = np.mean(prev_req)

    alloc_growth = (avg_recent_alloc - avg_prev_alloc) / avg_prev_alloc if avg_prev_alloc > 0 else 0
    req_growth = (avg_recent_req - avg_prev_req) / avg_prev_req if avg_prev_req > 0 else 0

    if abs(req_growth) > 0.01:
        saturation = 1.0 - (alloc_growth / req_growth)
        saturation = max(-2, min(5, saturation))
    else:
        saturation = np.nan

    if not np.isnan(saturation):
        recent_ratios = ratios[i-window_size:i]
        avg_ratio = np.mean(recent_ratios)

        saturation_list.append(saturation)
        cellular_ratio_list.append(avg_ratio)
        bandwidth_list.append(bandwidth[i])

# Normalize inputs to [0,1] for fair comparison
def normalize_saturation(sat):
    """Map saturation to [0,1] score"""
    if 0.85 <= sat <= 1.5:
        return 1.0
    elif 0.7 <= sat < 0.85:
        return (sat - 0.7) / 0.15
    elif 1.5 < sat <= 2.0:
        return 1.0 - (sat - 1.5) / 0.5
    elif sat > 2.0:
        return 0.0
    else:
        return max(0, sat / 0.7)

def normalize_ratio(ratio):
    """Map cellular_ratio to [0,1] score (inverted: lower ratio = higher score)"""
    if ratio < 0.15:
        return 1.0
    elif ratio < 0.3:
        return 1.0 - (ratio - 0.15) / 0.15
    elif ratio < 0.5:
        return 1.0 - (ratio - 0.15) / 0.35
    else:
        return max(0, 1.0 - (ratio - 0.5) / 1.5)

sat_scores = [normalize_saturation(s) for s in saturation_list]
ratio_scores = [normalize_ratio(r) for r in cellular_ratio_list]

print("="*80)
print("EXPLORING OPTIMAL COMBINATION FUNCTIONS")
print("="*80)

# Test different combination functions
results = []

# 1. Linear weighted sum (baseline)
def linear_weighted(sat_s, ratio_s, w1=0.6, w2=0.4):
    return w1 * sat_s + w2 * ratio_s

metrics_linear = [linear_weighted(sat_scores[i], ratio_scores[i])
                  for i in range(len(sat_scores))]
corr_linear = np.corrcoef(metrics_linear, bandwidth_list)[0, 1]
r2_linear = r2_score(bandwidth_list,
                     [np.mean(bandwidth_list) + corr_linear * np.std(bandwidth_list) / np.std(metrics_linear) * (m - np.mean(metrics_linear))
                      for m in metrics_linear])
results.append(("Linear (0.6×S + 0.4×R)", corr_linear, r2_linear, metrics_linear))
print(f"\n1. LINEAR WEIGHTED SUM: M = 0.6×S + 0.4×R")
print(f"   Correlation: {corr_linear:.4f}")
print(f"   R²: {r2_linear:.4f}")

# 2. Geometric mean
def geometric_mean(sat_s, ratio_s, alpha=0.6):
    return (sat_s ** alpha) * (ratio_s ** (1-alpha))

metrics_geom = [geometric_mean(sat_scores[i], ratio_scores[i])
                for i in range(len(sat_scores))]
corr_geom = np.corrcoef(metrics_geom, bandwidth_list)[0, 1]
r2_geom = r2_score(bandwidth_list,
                   [np.mean(bandwidth_list) + corr_geom * np.std(bandwidth_list) / np.std(metrics_geom) * (m - np.mean(metrics_geom))
                    for m in metrics_geom])
results.append(("Geometric Mean (S^0.6 × R^0.4)", corr_geom, r2_geom, metrics_geom))
print(f"\n2. GEOMETRIC MEAN: M = S^0.6 × R^0.4")
print(f"   Correlation: {corr_geom:.4f}")
print(f"   R²: {r2_geom:.4f}")

# 3. Harmonic mean
def harmonic_mean(sat_s, ratio_s, w1=0.6, w2=0.4):
    if sat_s == 0 or ratio_s == 0:
        return 0
    return 1.0 / (w1/sat_s + w2/ratio_s) if (sat_s > 0 and ratio_s > 0) else 0

metrics_harm = [harmonic_mean(sat_scores[i], ratio_scores[i])
                for i in range(len(sat_scores))]
corr_harm = np.corrcoef(metrics_harm, bandwidth_list)[0, 1]
r2_harm = r2_score(bandwidth_list,
                   [np.mean(bandwidth_list) + corr_harm * np.std(bandwidth_list) / np.std(metrics_harm) * (m - np.mean(metrics_harm))
                    for m in metrics_harm])
results.append(("Harmonic Mean", corr_harm, r2_harm, metrics_harm))
print(f"\n3. HARMONIC MEAN: M = 1/(0.6/S + 0.4/R)")
print(f"   Correlation: {corr_harm:.4f}")
print(f"   R²: {r2_harm:.4f}")

# 4. Minimum (conservative)
def minimum(sat_s, ratio_s):
    return min(sat_s, ratio_s)

metrics_min = [minimum(sat_scores[i], ratio_scores[i])
               for i in range(len(sat_scores))]
corr_min = np.corrcoef(metrics_min, bandwidth_list)[0, 1]
r2_min = r2_score(bandwidth_list,
                  [np.mean(bandwidth_list) + corr_min * np.std(bandwidth_list) / np.std(metrics_min) * (m - np.mean(metrics_min))
                   for m in metrics_min])
results.append(("Minimum (S, R)", corr_min, r2_min, metrics_min))
print(f"\n4. MINIMUM: M = min(S, R)")
print(f"   Correlation: {corr_min:.4f}")
print(f"   R²: {r2_min:.4f}")

# 5. Maximum (optimistic)
def maximum(sat_s, ratio_s):
    return max(sat_s, ratio_s)

metrics_max = [maximum(sat_scores[i], ratio_scores[i])
               for i in range(len(sat_scores))]
corr_max = np.corrcoef(metrics_max, bandwidth_list)[0, 1]
r2_max = r2_score(bandwidth_list,
                  [np.mean(bandwidth_list) + corr_max * np.std(bandwidth_list) / np.std(metrics_max) * (m - np.mean(metrics_max))
                   for m in metrics_max])
results.append(("Maximum (S, R)", corr_max, r2_max, metrics_max))
print(f"\n5. MAXIMUM: M = max(S, R)")
print(f"   Correlation: {corr_max:.4f}")
print(f"   R²: {r2_max:.4f}")

# 6. Product (AND logic)
def product(sat_s, ratio_s):
    return sat_s * ratio_s

metrics_prod = [product(sat_scores[i], ratio_scores[i])
                for i in range(len(sat_scores))]
corr_prod = np.corrcoef(metrics_prod, bandwidth_list)[0, 1]
r2_prod = r2_score(bandwidth_list,
                   [np.mean(bandwidth_list) + corr_prod * np.std(bandwidth_list) / np.std(metrics_prod) * (m - np.mean(metrics_prod))
                    for m in metrics_prod])
results.append(("Product (S × R)", corr_prod, r2_prod, metrics_prod))
print(f"\n6. PRODUCT (AND logic): M = S × R")
print(f"   Correlation: {corr_prod:.4f}")
print(f"   R²: {r2_prod:.4f}")

# 7. Probabilistic OR
def prob_or(sat_s, ratio_s):
    return sat_s + ratio_s - sat_s * ratio_s

metrics_or = [prob_or(sat_scores[i], ratio_scores[i])
              for i in range(len(sat_scores))]
corr_or = np.corrcoef(metrics_or, bandwidth_list)[0, 1]
r2_or = r2_score(bandwidth_list,
                 [np.mean(bandwidth_list) + corr_or * np.std(bandwidth_list) / np.std(metrics_or) * (m - np.mean(metrics_or))
                  for m in metrics_or])
results.append(("Probabilistic OR", corr_or, r2_or, metrics_or))
print(f"\n7. PROBABILISTIC OR: M = S + R - S×R")
print(f"   Correlation: {corr_or:.4f}")
print(f"   R²: {r2_or:.4f}")

# 8. Squared weighted sum (emphasize high values)
def squared_weighted(sat_s, ratio_s, w1=0.6, w2=0.4):
    return (w1 * sat_s**2 + w2 * ratio_s**2) ** 0.5

metrics_sq = [squared_weighted(sat_scores[i], ratio_scores[i])
              for i in range(len(sat_scores))]
corr_sq = np.corrcoef(metrics_sq, bandwidth_list)[0, 1]
r2_sq = r2_score(bandwidth_list,
                 [np.mean(bandwidth_list) + corr_sq * np.std(bandwidth_list) / np.std(metrics_sq) * (m - np.mean(metrics_sq))
                  for m in metrics_sq])
results.append(("Squared Weighted (√(0.6S² + 0.4R²))", corr_sq, r2_sq, metrics_sq))
print(f"\n8. SQUARED WEIGHTED: M = √(0.6×S² + 0.4×R²)")
print(f"   Correlation: {corr_sq:.4f}")
print(f"   R²: {r2_sq:.4f}")

# 9. Softmax-like (emphasize higher value)
def softmax_weighted(sat_s, ratio_s, temp=2.0):
    exp_s = np.exp(sat_s * temp)
    exp_r = np.exp(ratio_s * temp)
    w_s = exp_s / (exp_s + exp_r)
    w_r = exp_r / (exp_s + exp_r)
    return w_s * sat_s + w_r * ratio_s

metrics_soft = [softmax_weighted(sat_scores[i], ratio_scores[i])
                for i in range(len(sat_scores))]
corr_soft = np.corrcoef(metrics_soft, bandwidth_list)[0, 1]
r2_soft = r2_score(bandwidth_list,
                   [np.mean(bandwidth_list) + corr_soft * np.std(bandwidth_list) / np.std(metrics_soft) * (m - np.mean(metrics_soft))
                    for m in metrics_soft])
results.append(("Softmax-weighted", corr_soft, r2_soft, metrics_soft))
print(f"\n9. SOFTMAX-WEIGHTED: Adaptive weights")
print(f"   Correlation: {corr_soft:.4f}")
print(f"   R²: {r2_soft:.4f}")

# 10. Threshold AND (both must be high)
def threshold_and(sat_s, ratio_s, threshold=0.7):
    if sat_s >= threshold and ratio_s >= threshold:
        return (sat_s + ratio_s) / 2
    else:
        return min(sat_s, ratio_s) * 0.5

metrics_tand = [threshold_and(sat_scores[i], ratio_scores[i])
                for i in range(len(sat_scores))]
corr_tand = np.corrcoef(metrics_tand, bandwidth_list)[0, 1]
r2_tand = r2_score(bandwidth_list,
                   [np.mean(bandwidth_list) + corr_tand * np.std(bandwidth_list) / np.std(metrics_tand) * (m - np.mean(metrics_tand))
                    for m in metrics_tand])
results.append(("Threshold AND (0.7)", corr_tand, r2_tand, metrics_tand))
print(f"\n10. THRESHOLD AND: If both>0.7, avg; else min×0.5")
print(f"    Correlation: {corr_tand:.4f}")
print(f"    R²: {r2_tand:.4f}")

# Find best
print("\n" + "="*80)
print("RANKING BY CORRELATION")
print("="*80)

results_sorted = sorted(results, key=lambda x: abs(x[1]), reverse=True)
print(f"\n{'Rank':>4} | {'Method':<40} | {'Correlation':>12} | {'R²':>8}")
print("-" * 75)
for i, (method, corr, r2, _) in enumerate(results_sorted, 1):
    print(f"{i:4d} | {method:<40} | {corr:12.4f} | {r2:8.4f}")

# Visualization
fig, axes = plt.subplots(3, 4, figsize=(24, 18))
axes = axes.flatten()

for idx, (method, corr, r2, metrics) in enumerate(results_sorted[:12]):
    ax = axes[idx]

    # Scatter plot
    scatter = ax.scatter(metrics, bandwidth_list, c=bandwidth_list,
                        cmap='viridis', alpha=0.5, s=10)

    # Regression line
    if len(set(metrics)) > 1:
        slope, intercept, _, _, _ = stats.linregress(metrics, bandwidth_list)
        x_range = np.linspace(min(metrics), max(metrics), 100)
        y_pred = slope * x_range + intercept
        ax.plot(x_range, y_pred, 'r-', linewidth=2, alpha=0.7)

    ax.set_xlabel('Metric Value', fontsize=10, fontweight='bold')
    ax.set_ylabel('Bandwidth', fontsize=10, fontweight='bold')
    ax.set_title(f'{idx+1}. {method}\nCorr={corr:.3f}, R²={r2:.3f}',
                fontsize=11, fontweight='bold')
    ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('/home/wuq/webrtc-local/metric_function_comparison.png', dpi=300, bbox_inches='tight')
print(f"\n✅ Visualization saved to: /home/wuq/webrtc-local/metric_function_comparison.png")

# Detailed analysis of top 3
print("\n" + "="*80)
print("TOP 3 METHODS - DETAILED ANALYSIS")
print("="*80)

for i, (method, corr, r2, metrics) in enumerate(results_sorted[:3], 1):
    print(f"\n{i}. {method}")
    print(f"   Correlation: {corr:.4f}")
    print(f"   R²: {r2:.4f}")
    print(f"   Metric range: [{min(metrics):.3f}, {max(metrics):.3f}]")
    print(f"   Metric mean: {np.mean(metrics):.3f}")
    print(f"   Metric std: {np.std(metrics):.3f}")

    # Check peak detection
    peak_threshold = np.percentile(bandwidth_list, 90)
    peak_indices = [j for j in range(len(bandwidth_list)) if bandwidth_list[j] > peak_threshold]
    peak_metrics = [metrics[j] for j in peak_indices]

    if peak_metrics:
        print(f"   Peak region metric: [{min(peak_metrics):.3f}, {max(peak_metrics):.3f}]")
        print(f"   Peak region mean: {np.mean(peak_metrics):.3f}")

print("\n" + "="*80)
print("RECOMMENDATION")
print("="*80)
print(f"\n🏆 Best method: {results_sorted[0][0]}")
print(f"   Correlation: {results_sorted[0][1]:.4f}")
print(f"   Improvement over linear: {(abs(results_sorted[0][1]) - abs(corr_linear))*100:.2f}%")

if results_sorted[0][0] == "Linear (0.6×S + 0.4×R)":
    print("\n   Current linear method is already optimal!")
else:
    print(f"\n   Consider switching to {results_sorted[0][0]} for better performance")

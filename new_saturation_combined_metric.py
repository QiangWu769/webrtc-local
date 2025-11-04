#!/usr/bin/env python3
"""
Re-evaluate combined metric with NEW saturation definition
Saturation_NEW = 1 - (req_growth / alloc_growth)
"""
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats
from scipy.optimize import minimize

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

window_size = 10

# Calculate OLD and NEW saturation
sat_old = []
sat_new = []
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

    # OLD: 1 - (ag/rg)
    if abs(req_growth) > 0.01:
        s_old = 1.0 - (alloc_growth / req_growth)
        s_old = max(-2, min(5, s_old))
    else:
        s_old = np.nan

    # NEW: 1 - (rg/ag)
    if abs(alloc_growth) > 0.01:
        s_new = 1.0 - (req_growth / alloc_growth)
        s_new = max(-2, min(5, s_new))
    else:
        s_new = np.nan

    if not np.isnan(s_old) and not np.isnan(s_new):
        # Smooth cellular_ratio
        recent_ratios = ratios[i-window_size:i]
        avg_ratio = np.mean(recent_ratios)

        sat_old.append(s_old)
        sat_new.append(s_new)
        cellular_ratio_list.append(avg_ratio)
        bandwidth_list.append(bandwidth[i])

print("="*80)
print("NEW SATURATION DEFINITION: COMBINED METRIC ANALYSIS")
print("="*80)

# Normalize functions
def normalize_saturation_old(sat):
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

def normalize_saturation_new(sat):
    # Same threshold structure, but values are different
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
    if ratio < 0.15:
        return 1.0
    elif ratio < 0.3:
        return 1.0 - (ratio - 0.15) / 0.15
    elif ratio < 0.5:
        return 1.0 - (ratio - 0.15) / 0.35
    else:
        return max(0, 1.0 - (ratio - 0.5) / 1.5)

sat_old_scores = np.array([normalize_saturation_old(s) for s in sat_old])
sat_new_scores = np.array([normalize_saturation_new(s) for s in sat_new])
ratio_scores = np.array([normalize_ratio(r) for r in cellular_ratio_list])
bw_array = np.array(bandwidth_list)

# Compare individual metrics
print("\n1. INDIVIDUAL METRIC COMPARISON:")
print("-" * 80)

corr_old_sat = np.corrcoef(sat_old_scores, bw_array)[0, 1]
corr_new_sat = np.corrcoef(sat_new_scores, bw_array)[0, 1]
corr_ratio = np.corrcoef(ratio_scores, bw_array)[0, 1]

print(f"OLD Saturation [1-(ag/rg)]:  Corr = {corr_old_sat:.4f}")
print(f"NEW Saturation [1-(rg/ag)]:  Corr = {corr_new_sat:.4f}  ({(corr_new_sat-corr_old_sat)/abs(corr_old_sat)*100:+.1f}%)")
print(f"Cellular Ratio:               Corr = {corr_ratio:.4f}")

# Optimize weights for OLD saturation + Ratio
def objective_old(w):
    w1 = w[0]
    w2 = 1 - w1
    metrics = w1 * sat_old_scores + w2 * ratio_scores
    return -abs(np.corrcoef(metrics, bw_array)[0, 1])

result_old = minimize(objective_old, x0=[0.5], bounds=[(0, 1)], method='L-BFGS-B')
best_w1_old = result_old.x[0]
best_w2_old = 1 - best_w1_old
metrics_old_best = best_w1_old * sat_old_scores + best_w2_old * ratio_scores
corr_old_best = np.corrcoef(metrics_old_best, bw_array)[0, 1]

# Optimize weights for NEW saturation + Ratio
def objective_new(w):
    w1 = w[0]
    w2 = 1 - w1
    metrics = w1 * sat_new_scores + w2 * ratio_scores
    return -abs(np.corrcoef(metrics, bw_array)[0, 1])

result_new = minimize(objective_new, x0=[0.5], bounds=[(0, 1)], method='L-BFGS-B')
best_w1_new = result_new.x[0]
best_w2_new = 1 - best_w1_new
metrics_new_best = best_w1_new * sat_new_scores + best_w2_new * ratio_scores
corr_new_best = np.corrcoef(metrics_new_best, bw_array)[0, 1]

print("\n2. OPTIMAL LINEAR COMBINATIONS:")
print("-" * 80)

print(f"\nOLD Saturation + Ratio:")
print(f"  Best weights: w1={best_w1_old:.3f}, w2={best_w2_old:.3f}")
print(f"  Correlation: {corr_old_best:.4f}")

print(f"\nNEW Saturation + Ratio:")
print(f"  Best weights: w1={best_w1_new:.3f}, w2={best_w2_new:.3f}")
print(f"  Correlation: {corr_new_best:.4f}")
print(f"  Improvement: {(corr_new_best-corr_old_best)/abs(corr_old_best)*100:+.1f}%")

# Try squared combination
def objective_squared_new(w):
    w1 = w[0]
    w2 = 1 - w1
    metrics = np.sqrt(w1 * sat_new_scores**2 + w2 * ratio_scores**2)
    return -abs(np.corrcoef(metrics, bw_array)[0, 1])

result_sq_new = minimize(objective_squared_new, x0=[0.5], bounds=[(0, 1)], method='L-BFGS-B')
best_w1_sq_new = result_sq_new.x[0]
best_w2_sq_new = 1 - best_w1_sq_new
metrics_sq_new = np.sqrt(best_w1_sq_new * sat_new_scores**2 + best_w2_sq_new * ratio_scores**2)
corr_sq_new = np.corrcoef(metrics_sq_new, bw_array)[0, 1]

print(f"\nNEW Saturation + Ratio (Squared):")
print(f"  Best weights: w1={best_w1_sq_new:.3f}, w2={best_w2_sq_new:.3f}")
print(f"  Correlation: {corr_sq_new:.4f}")

# Check information independence
print("\n3. INFORMATION INDEPENDENCE:")
print("-" * 80)

corr_old_ratio = np.corrcoef(sat_old_scores, ratio_scores)[0, 1]
corr_new_ratio = np.corrcoef(sat_new_scores, ratio_scores)[0, 1]

print(f"\nOLD Saturation vs Ratio:  Corr = {corr_old_ratio:.4f}, Shared = {corr_old_ratio**2*100:.1f}%, Independent = {(1-corr_old_ratio**2)*100:.1f}%")
print(f"NEW Saturation vs Ratio:  Corr = {corr_new_ratio:.4f}, Shared = {corr_new_ratio**2*100:.1f}%, Independent = {(1-corr_new_ratio**2)*100:.1f}%")

# Peak detection performance
print("\n4. PEAK DETECTION PERFORMANCE:")
print("-" * 80)

peak_threshold = np.percentile(bw_array, 90)
peak_indices = [i for i in range(len(bw_array)) if bw_array[i] > peak_threshold]

old_metric_peak = [metrics_old_best[i] for i in peak_indices]
new_metric_peak = [metrics_new_best[i] for i in peak_indices]
new_sq_metric_peak = [metrics_sq_new[i] for i in peak_indices]

print(f"\nOLD combined metric at peak:")
print(f"  Mean: {np.mean(old_metric_peak):.3f}, Std: {np.std(old_metric_peak):.3f}")

print(f"\nNEW combined metric at peak:")
print(f"  Mean: {np.mean(new_metric_peak):.3f}, Std: {np.std(new_metric_peak):.3f}")

print(f"\nNEW squared metric at peak:")
print(f"  Mean: {np.mean(new_sq_metric_peak):.3f}, Std: {np.std(new_sq_metric_peak):.3f}")

# Summary table
print("\n" + "="*80)
print("FINAL COMPARISON")
print("="*80)

results = [
    ("OLD Sat alone", corr_old_sat),
    ("NEW Sat alone", corr_new_sat),
    ("Ratio alone", corr_ratio),
    (f"OLD + Ratio ({best_w1_old:.2f}, {best_w2_old:.2f})", corr_old_best),
    (f"NEW + Ratio ({best_w1_new:.2f}, {best_w2_new:.2f})", corr_new_best),
    (f"NEW + Ratio Squared ({best_w1_sq_new:.2f}, {best_w2_sq_new:.2f})", corr_sq_new),
]

print(f"\n{'Method':<45} | {'Correlation':>12} | {'vs Ratio':>10}")
print("-" * 75)

for method, corr in results:
    improvement = (corr - corr_ratio) / abs(corr_ratio) * 100 if corr_ratio != 0 else 0
    print(f"{method:<45} | {corr:12.4f} | {improvement:+9.1f}%")

# Find the best
best_method, best_corr = max(results, key=lambda x: abs(x[1]))
print(f"\n🏆 WINNER: {best_method}")
print(f"   Correlation: {best_corr:.4f}")

# Visualization
fig, axes = plt.subplots(2, 3, figsize=(20, 12))

# Plot 1: OLD Sat alone
ax1 = axes[0, 0]
scatter1 = ax1.scatter(sat_old_scores, bw_array, c=bw_array, cmap='viridis', alpha=0.5, s=10)
slope1, intercept1, _, _, _ = stats.linregress(sat_old_scores, bw_array)
x_range = np.linspace(0, 1, 100)
ax1.plot(x_range, slope1*x_range + intercept1, 'r-', linewidth=2)
ax1.set_xlabel('OLD Saturation Score', fontsize=11, fontweight='bold')
ax1.set_ylabel('Bandwidth', fontsize=11, fontweight='bold')
ax1.set_title(f'OLD Sat [1-(ag/rg)]\nCorr={corr_old_sat:.3f}', fontsize=12, fontweight='bold')
ax1.grid(True, alpha=0.3)

# Plot 2: NEW Sat alone
ax2 = axes[0, 1]
scatter2 = ax2.scatter(sat_new_scores, bw_array, c=bw_array, cmap='plasma', alpha=0.5, s=10)
slope2, intercept2, _, _, _ = stats.linregress(sat_new_scores, bw_array)
ax2.plot(x_range, slope2*x_range + intercept2, 'r-', linewidth=2)
ax2.set_xlabel('NEW Saturation Score', fontsize=11, fontweight='bold')
ax2.set_ylabel('Bandwidth', fontsize=11, fontweight='bold')
ax2.set_title(f'NEW Sat [1-(rg/ag)]\nCorr={corr_new_sat:.3f}', fontsize=12, fontweight='bold')
ax2.grid(True, alpha=0.3)

# Plot 3: Ratio alone
ax3 = axes[0, 2]
scatter3 = ax3.scatter(ratio_scores, bw_array, c=bw_array, cmap='coolwarm', alpha=0.5, s=10)
slope3, intercept3, _, _, _ = stats.linregress(ratio_scores, bw_array)
ax3.plot(x_range, slope3*x_range + intercept3, 'r-', linewidth=2)
ax3.set_xlabel('Ratio Score', fontsize=11, fontweight='bold')
ax3.set_ylabel('Bandwidth', fontsize=11, fontweight='bold')
ax3.set_title(f'Ratio alone\nCorr={corr_ratio:.3f}', fontsize=12, fontweight='bold')
ax3.grid(True, alpha=0.3)

# Plot 4: OLD combined
ax4 = axes[1, 0]
scatter4 = ax4.scatter(metrics_old_best, bw_array, c=bw_array, cmap='viridis', alpha=0.5, s=10)
slope4, intercept4, _, _, _ = stats.linregress(metrics_old_best, bw_array)
ax4.plot(x_range, slope4*x_range + intercept4, 'r-', linewidth=2)
ax4.set_xlabel('Metric', fontsize=11, fontweight='bold')
ax4.set_ylabel('Bandwidth', fontsize=11, fontweight='bold')
ax4.set_title(f'OLD Combined ({best_w1_old:.2f}S+{best_w2_old:.2f}R)\nCorr={corr_old_best:.3f}',
              fontsize=12, fontweight='bold')
ax4.grid(True, alpha=0.3)

# Plot 5: NEW combined linear
ax5 = axes[1, 1]
scatter5 = ax5.scatter(metrics_new_best, bw_array, c=bw_array, cmap='plasma', alpha=0.5, s=10)
slope5, intercept5, _, _, _ = stats.linregress(metrics_new_best, bw_array)
ax5.plot(x_range, slope5*x_range + intercept5, 'r-', linewidth=2)
ax5.set_xlabel('Metric', fontsize=11, fontweight='bold')
ax5.set_ylabel('Bandwidth', fontsize=11, fontweight='bold')
ax5.set_title(f'NEW Combined ({best_w1_new:.2f}S+{best_w2_new:.2f}R)\nCorr={corr_new_best:.3f}',
              fontsize=12, fontweight='bold')
ax5.grid(True, alpha=0.3)

# Plot 6: NEW squared
ax6 = axes[1, 2]
scatter6 = ax6.scatter(metrics_sq_new, bw_array, c=bw_array, cmap='coolwarm', alpha=0.5, s=10)
slope6, intercept6, _, _, _ = stats.linregress(metrics_sq_new, bw_array)
ax6.plot(x_range, slope6*x_range + intercept6, 'r-', linewidth=2)
ax6.set_xlabel('Metric', fontsize=11, fontweight='bold')
ax6.set_ylabel('Bandwidth', fontsize=11, fontweight='bold')
ax6.set_title(f'NEW Squared ({best_w1_sq_new:.2f}S²+{best_w2_sq_new:.2f}R²)\nCorr={corr_sq_new:.3f}',
              fontsize=12, fontweight='bold')
ax6.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('/home/wuq/webrtc-local/new_saturation_combined.png', dpi=300, bbox_inches='tight')
print(f"\n✅ Visualization saved to: /home/wuq/webrtc-local/new_saturation_combined.png")

# Recommendation
print("\n" + "="*80)
print("RECOMMENDATION")
print("="*80)

print(f"\n🎯 FINAL RECOMMENDED METRIC:")
print(f"\n   Saturation_NEW = 1 - (req_growth / alloc_growth)")
print(f"   Combined = {best_w1_new:.3f} × Sat_NEW + {best_w2_new:.3f} × Ratio")
print(f"\n   Correlation: {corr_new_best:.4f}")
print(f"   Improvement over OLD: {(corr_new_best-corr_old_best)/abs(corr_old_best)*100:+.1f}%")
print(f"   Improvement over Ratio alone: {(corr_new_best-corr_ratio)/abs(corr_ratio)*100:+.1f}%")

if corr_new_best > corr_ratio:
    print(f"\n   ✅ Using NEW Saturation improves upon Ratio alone!")
else:
    print(f"\n   ⚠️  Ratio alone is still better - NEW Saturation adds noise")

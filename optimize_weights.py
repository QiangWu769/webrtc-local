#!/usr/bin/env python3
"""
Optimize weights for Saturation and Ratio combination
Find optimal w1 and w2 in: M = w1*S + w2*R (where w1+w2=1)
"""
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import minimize
from sklearn.metrics import r2_score

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

# Normalize functions
def normalize_saturation(sat):
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

sat_scores = np.array([normalize_saturation(s) for s in saturation_list])
ratio_scores = np.array([normalize_ratio(r) for r in cellular_ratio_list])
bw_array = np.array(bandwidth_list)

print("="*80)
print("WEIGHT OPTIMIZATION FOR LINEAR COMBINATION")
print("="*80)

# Method 1: Grid search
print(f"\n1. GRID SEARCH (w1 from 0 to 1, step=0.05)")
print(f"   M = w1*S + (1-w1)*R")
print("-" * 80)

weight_results = []
for w1 in np.arange(0, 1.05, 0.05):
    w2 = 1 - w1
    metrics = w1 * sat_scores + w2 * ratio_scores
    corr = np.corrcoef(metrics, bw_array)[0, 1]
    weight_results.append((w1, w2, corr, abs(corr)))

# Sort by absolute correlation
weight_results.sort(key=lambda x: x[3], reverse=True)

print(f"\n{'Rank':>4} | {'w1(Sat)':>8} | {'w2(Ratio)':>10} | {'Correlation':>12}")
print("-" * 45)
for i, (w1, w2, corr, abs_corr) in enumerate(weight_results[:15], 1):
    print(f"{i:4d} | {w1:8.2f} | {w2:10.2f} | {corr:12.4f}")

best_w1, best_w2, best_corr, _ = weight_results[0]
print(f"\n🏆 BEST LINEAR WEIGHTS: w1={best_w1:.2f}, w2={best_w2:.2f}")
print(f"   Correlation: {best_corr:.4f}")

# Method 2: Optimization (maximize correlation)
def objective(weights):
    w1 = weights[0]
    w2 = 1 - w1
    metrics = w1 * sat_scores + w2 * ratio_scores
    corr = np.corrcoef(metrics, bw_array)[0, 1]
    return -abs(corr)  # Negative because we minimize

result = minimize(objective, x0=[0.5], bounds=[(0, 1)], method='L-BFGS-B')
opt_w1 = result.x[0]
opt_w2 = 1 - opt_w1
opt_corr = -result.fun

print(f"\n2. OPTIMIZATION (L-BFGS-B):")
print(f"   Optimal w1: {opt_w1:.4f}")
print(f"   Optimal w2: {opt_w2:.4f}")
print(f"   Correlation: {opt_corr:.4f}")

# Method 3: Test squared combination with different weights
print(f"\n" + "="*80)
print("WEIGHT OPTIMIZATION FOR SQUARED COMBINATION")
print("="*80)
print(f"\n3. GRID SEARCH for SQUARED: M = √(w1*S² + w2*R²)")
print("-" * 80)

squared_results = []
for w1 in np.arange(0, 1.05, 0.05):
    w2 = 1 - w1
    metrics = np.sqrt(w1 * sat_scores**2 + w2 * ratio_scores**2)
    corr = np.corrcoef(metrics, bw_array)[0, 1]
    squared_results.append((w1, w2, corr, abs(corr)))

squared_results.sort(key=lambda x: x[3], reverse=True)

print(f"\n{'Rank':>4} | {'w1(Sat)':>8} | {'w2(Ratio)':>10} | {'Correlation':>12}")
print("-" * 45)
for i, (w1, w2, corr, abs_corr) in enumerate(squared_results[:15], 1):
    print(f"{i:4d} | {w1:8.2f} | {w2:10.2f} | {corr:12.4f}")

best_sq_w1, best_sq_w2, best_sq_corr, _ = squared_results[0]
print(f"\n🏆 BEST SQUARED WEIGHTS: w1={best_sq_w1:.2f}, w2={best_sq_w2:.2f}")
print(f"   Correlation: {best_sq_corr:.4f}")

# Method 4: Unconstrained weights (no w1+w2=1 constraint)
print(f"\n" + "="*80)
print("UNCONSTRAINED WEIGHTS (w1 + w2 ≠ 1)")
print("="*80)

def objective_unconstrained(weights):
    w1, w2 = weights
    metrics = w1 * sat_scores + w2 * ratio_scores
    corr = np.corrcoef(metrics, bw_array)[0, 1]
    return -abs(corr)

result_unconst = minimize(objective_unconstrained, x0=[0.5, 0.5],
                          bounds=[(0, 2), (0, 2)], method='L-BFGS-B')
unconst_w1, unconst_w2 = result_unconst.x
unconst_corr = -result_unconst.fun

print(f"\n4. UNCONSTRAINED OPTIMIZATION:")
print(f"   Optimal w1: {unconst_w1:.4f}")
print(f"   Optimal w2: {unconst_w2:.4f}")
print(f"   Sum: {unconst_w1 + unconst_w2:.4f}")
print(f"   Correlation: {unconst_corr:.4f}")

# Comparison table
print(f"\n" + "="*80)
print("SUMMARY COMPARISON")
print("="*80)

print(f"\n{'Method':<40} | {'w1(Sat)':>8} | {'w2(Ratio)':>10} | {'Correlation':>12}")
print("-" * 75)
print(f"{'Original (0.6, 0.4)':<40} | {0.6:8.2f} | {0.4:10.2f} | {np.corrcoef(0.6*sat_scores + 0.4*ratio_scores, bw_array)[0,1]:12.4f}")
print(f"{'Best Linear (grid search)':<40} | {best_w1:8.2f} | {best_w2:10.2f} | {best_corr:12.4f}")
print(f"{'Best Linear (optimization)':<40} | {opt_w1:8.2f} | {opt_w2:10.2f} | {opt_corr:12.4f}")
print(f"{'Best Squared (grid search)':<40} | {best_sq_w1:8.2f} | {best_sq_w2:10.2f} | {best_sq_corr:12.4f}")
print(f"{'Unconstrained Linear':<40} | {unconst_w1:8.2f} | {unconst_w2:10.2f} | {unconst_corr:12.4f}")

# Visualization
fig, axes = plt.subplots(2, 2, figsize=(18, 14))

# Plot 1: Linear weights correlation curve
ax1 = axes[0, 0]
w1_range = [x[0] for x in weight_results]
corr_range = [x[2] for x in weight_results]
ax1.plot(w1_range, corr_range, 'b-', linewidth=3, marker='o', markersize=6)
ax1.axvline(x=0.6, color='red', linestyle='--', linewidth=2, label='Original w1=0.6')
ax1.axvline(x=best_w1, color='green', linestyle='--', linewidth=2,
            label=f'Best w1={best_w1:.2f}')
ax1.axhline(y=best_corr, color='green', linestyle=':', alpha=0.5)
ax1.set_xlabel('w1 (Saturation weight)', fontsize=12, fontweight='bold')
ax1.set_ylabel('Correlation', fontsize=12, fontweight='bold')
ax1.set_title('Linear: M = w1×S + (1-w1)×R', fontsize=14, fontweight='bold')
ax1.legend(fontsize=11)
ax1.grid(True, alpha=0.3)

# Plot 2: Squared weights correlation curve
ax2 = axes[0, 1]
sq_w1_range = [x[0] for x in squared_results]
sq_corr_range = [x[2] for x in squared_results]
ax2.plot(sq_w1_range, sq_corr_range, 'r-', linewidth=3, marker='o', markersize=6)
ax2.axvline(x=0.6, color='blue', linestyle='--', linewidth=2, label='Original w1=0.6')
ax2.axvline(x=best_sq_w1, color='green', linestyle='--', linewidth=2,
            label=f'Best w1={best_sq_w1:.2f}')
ax2.axhline(y=best_sq_corr, color='green', linestyle=':', alpha=0.5)
ax2.set_xlabel('w1 (Saturation weight)', fontsize=12, fontweight='bold')
ax2.set_ylabel('Correlation', fontsize=12, fontweight='bold')
ax2.set_title('Squared: M = √(w1×S² + (1-w1)×R²)', fontsize=14, fontweight='bold')
ax2.legend(fontsize=11)
ax2.grid(True, alpha=0.3)

# Plot 3: 2D heatmap for unconstrained weights
ax3 = axes[1, 0]
w1_grid = np.linspace(0, 1, 50)
w2_grid = np.linspace(0, 1, 50)
corr_grid = np.zeros((50, 50))

for i, w1 in enumerate(w1_grid):
    for j, w2 in enumerate(w2_grid):
        metrics = w1 * sat_scores + w2 * ratio_scores
        corr_grid[i, j] = np.corrcoef(metrics, bw_array)[0, 1]

im = ax3.imshow(corr_grid, origin='lower', aspect='auto', cmap='RdYlGn',
                extent=[0, 1, 0, 1])
ax3.plot([0, 1], [1, 0], 'b--', linewidth=2, label='w1+w2=1')
ax3.scatter([0.6], [0.4], color='red', s=200, marker='*',
            edgecolors='black', linewidth=2, label='Original (0.6, 0.4)', zorder=5)
ax3.scatter([unconst_w1], [unconst_w2], color='yellow', s=200, marker='*',
            edgecolors='black', linewidth=2, label=f'Best ({unconst_w1:.2f}, {unconst_w2:.2f})', zorder=5)
ax3.set_xlabel('w1 (Saturation)', fontsize=12, fontweight='bold')
ax3.set_ylabel('w2 (Ratio)', fontsize=12, fontweight='bold')
ax3.set_title('2D Weight Space (Unconstrained Linear)', fontsize=14, fontweight='bold')
ax3.legend(fontsize=10)
plt.colorbar(im, ax=ax3, label='Correlation')

# Plot 4: Comparison bar chart
ax4 = axes[1, 1]
methods = ['Original\n(0.6, 0.4)', f'Best Linear\n({best_w1:.2f}, {best_w2:.2f})',
           f'Best Squared\n({best_sq_w1:.2f}, {best_sq_w2:.2f})',
           f'Unconstrained\n({unconst_w1:.2f}, {unconst_w2:.2f})']
correlations = [
    np.corrcoef(0.6*sat_scores + 0.4*ratio_scores, bw_array)[0,1],
    best_corr,
    best_sq_corr,
    unconst_corr
]
colors = ['#3498db', '#2ecc71', '#f39c12', '#e74c3c']

bars = ax4.bar(range(len(methods)), correlations, color=colors, alpha=0.7,
               edgecolor='black', linewidth=2)

# Add value labels
for bar, corr in zip(bars, correlations):
    height = bar.get_height()
    ax4.text(bar.get_x() + bar.get_width()/2., height + 0.005,
            f'{corr:.4f}', ha='center', va='bottom', fontsize=11, fontweight='bold')

ax4.set_xticks(range(len(methods)))
ax4.set_xticklabels(methods, fontsize=10, fontweight='bold')
ax4.set_ylabel('Correlation', fontsize=12, fontweight='bold')
ax4.set_title('Weight Optimization Results', fontsize=14, fontweight='bold')
ax4.set_ylim([0.82, 0.85])
ax4.grid(True, alpha=0.3, axis='y')

plt.tight_layout()
plt.savefig('/home/wuq/webrtc-local/weight_optimization.png', dpi=300, bbox_inches='tight')
print(f"\n✅ Visualization saved to: /home/wuq/webrtc-local/weight_optimization.png")

# Final recommendation
print(f"\n" + "="*80)
print("RECOMMENDATION")
print("="*80)

improvement = (best_sq_corr - np.corrcoef(0.6*sat_scores + 0.4*ratio_scores, bw_array)[0,1]) / \
              np.corrcoef(0.6*sat_scores + 0.4*ratio_scores, bw_array)[0,1] * 100

print(f"\n📊 Current weights (0.6, 0.4) are {'GOOD' if abs(improvement) < 1 else 'SUBOPTIMAL'}!")
print(f"\n   Original (0.6S + 0.4R):  Corr = {np.corrcoef(0.6*sat_scores + 0.4*ratio_scores, bw_array)[0,1]:.4f}")
print(f"   Best Squared weights:    Corr = {best_sq_corr:.4f}")
print(f"   Improvement: {improvement:+.2f}%")

if abs(best_sq_w1 - 0.6) < 0.1:
    print(f"\n   ✅ The original 0.6/0.4 split is near-optimal!")
else:
    print(f"\n   💡 Recommended: Use ({best_sq_w1:.2f}, {best_sq_w2:.2f}) for {improvement:+.2f}% improvement")

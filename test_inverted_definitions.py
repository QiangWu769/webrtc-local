#!/usr/bin/env python3
"""
Test INVERTED definitions:
- Ratio_INV = Requested / Allocated (instead of Allocated/Requested)
- Saturation_INV = req_growth / alloc_growth (instead of 1 - alloc_growth/req_growth)
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

# Calculate all variants
sat_old = []
sat_inv = []
ratio_old = []
ratio_inv = []
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

    # OLD Saturation: 1 - (ag/rg)
    if abs(req_growth) > 0.01:
        s_old = 1.0 - (alloc_growth / req_growth)
        s_old = max(-2, min(5, s_old))
    else:
        s_old = np.nan

    # INVERTED Saturation: rg/ag
    if abs(alloc_growth) > 0.01:
        s_inv = req_growth / alloc_growth
        s_inv = max(-2, min(5, s_inv))
    else:
        s_inv = np.nan

    # OLD Ratio: alloc/req (smoothed)
    recent_ratios = ratios[i-window_size:i]
    r_old = np.mean(recent_ratios)

    # INVERTED Ratio: req/alloc
    if avg_recent_alloc > 0:
        r_inv = avg_recent_req / avg_recent_alloc
        r_inv = min(r_inv, 5.0)  # Cap at 5
    else:
        r_inv = np.nan

    if not np.isnan(s_old) and not np.isnan(s_inv) and not np.isnan(r_inv):
        sat_old.append(s_old)
        sat_inv.append(s_inv)
        ratio_old.append(r_old)
        ratio_inv.append(r_inv)
        bandwidth_list.append(bandwidth[i])

print("="*80)
print("INVERTED DEFINITIONS TEST")
print("="*80)

# Compare individual metrics
bw_array = np.array(bandwidth_list)

corr_sat_old = np.corrcoef(sat_old, bw_array)[0, 1]
corr_sat_inv = np.corrcoef(sat_inv, bw_array)[0, 1]
corr_ratio_old = np.corrcoef(ratio_old, bw_array)[0, 1]
corr_ratio_inv = np.corrcoef(ratio_inv, bw_array)[0, 1]

print("\n1. INDIVIDUAL METRIC COMPARISON:")
print("-" * 80)
print(f"\nOLD Saturation [1-(ag/rg)]:      Corr = {corr_sat_old:8.4f}")
print(f"INV Saturation [rg/ag]:          Corr = {corr_sat_inv:8.4f}  ({(corr_sat_inv-corr_sat_old)/abs(corr_sat_old)*100:+.1f}%)")

print(f"\nOLD Ratio [alloc/req]:           Corr = {corr_ratio_old:8.4f}")
print(f"INV Ratio [req/alloc]:           Corr = {corr_ratio_inv:8.4f}  ({(corr_ratio_inv-corr_ratio_old)/abs(corr_ratio_old)*100:+.1f}%)")

# Normalize functions for OLD
def normalize_sat_old(sat):
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

def normalize_ratio_old(ratio):
    if ratio < 0.15:
        return 1.0
    elif ratio < 0.3:
        return 1.0 - (ratio - 0.15) / 0.15
    elif ratio < 0.5:
        return 1.0 - (ratio - 0.15) / 0.35
    else:
        return max(0, 1.0 - (ratio - 0.5) / 1.5)

# Normalize functions for INVERTED
def normalize_sat_inv(sat):
    # For rg/ag: high values mean at peak (req grows but alloc doesn't)
    # Invert the logic: high value = high score
    if sat >= 5:
        return 1.0
    elif sat >= 2:
        return (sat - 2) / 3  # 2-5 maps to 0-1
    elif sat >= 1:
        return (sat - 1) / 1  # 1-2 maps to 0-1
    elif sat >= 0:
        return sat / 1  # 0-1 maps to 0-1
    else:
        return 0.0

def normalize_ratio_inv(ratio):
    # For req/alloc: high values mean at peak (requesting a lot, getting little)
    # High value = high score
    if ratio >= 5:
        return 1.0
    elif ratio >= 2:
        return (ratio - 2) / 3 + 0.5
    elif ratio >= 1:
        return (ratio - 1) / 1 * 0.5
    else:
        return ratio * 0.3

sat_old_scores = np.array([normalize_sat_old(s) for s in sat_old])
sat_inv_scores = np.array([normalize_sat_inv(s) for s in sat_inv])
ratio_old_scores = np.array([normalize_ratio_old(r) for r in ratio_old])
ratio_inv_scores = np.array([normalize_ratio_inv(r) for r in ratio_inv])

# Optimize OLD combination
def obj_old(w):
    w1 = w[0]
    w2 = 1 - w1
    metrics = w1 * sat_old_scores + w2 * ratio_old_scores
    return -abs(np.corrcoef(metrics, bw_array)[0, 1])

result_old = minimize(obj_old, x0=[0.5], bounds=[(0, 1)], method='L-BFGS-B')
w1_old = result_old.x[0]
w2_old = 1 - w1_old
metrics_old = w1_old * sat_old_scores + w2_old * ratio_old_scores
corr_old = np.corrcoef(metrics_old, bw_array)[0, 1]

# Optimize INVERTED combination
def obj_inv(w):
    w1 = w[0]
    w2 = 1 - w1
    metrics = w1 * sat_inv_scores + w2 * ratio_inv_scores
    return -abs(np.corrcoef(metrics, bw_array)[0, 1])

result_inv = minimize(obj_inv, x0=[0.5], bounds=[(0, 1)], method='L-BFGS-B')
w1_inv = result_inv.x[0]
w2_inv = 1 - w1_inv
metrics_inv = w1_inv * sat_inv_scores + w2_inv * ratio_inv_scores
corr_inv = np.corrcoef(metrics_inv, bw_array)[0, 1]

print("\n2. OPTIMAL COMBINED METRICS:")
print("-" * 80)

print(f"\nOLD Combined:")
print(f"  Formula: {w1_old:.3f} × Sat_old + {w2_old:.3f} × Ratio_old")
print(f"  Correlation: {corr_old:.4f}")

print(f"\nINVERTED Combined:")
print(f"  Formula: {w1_inv:.3f} × Sat_inv + {w2_inv:.3f} × Ratio_inv")
print(f"  Correlation: {corr_inv:.4f}")
print(f"  Improvement: {(corr_inv - corr_old)/abs(corr_old)*100:+.1f}%")

# Test mix: OLD Sat + INV Ratio
def obj_mix1(w):
    w1 = w[0]
    w2 = 1 - w1
    metrics = w1 * sat_old_scores + w2 * ratio_inv_scores
    return -abs(np.corrcoef(metrics, bw_array)[0, 1])

result_mix1 = minimize(obj_mix1, x0=[0.5], bounds=[(0, 1)], method='L-BFGS-B')
w1_mix1 = result_mix1.x[0]
w2_mix1 = 1 - w1_mix1
metrics_mix1 = w1_mix1 * sat_old_scores + w2_mix1 * ratio_inv_scores
corr_mix1 = np.corrcoef(metrics_mix1, bw_array)[0, 1]

# Test mix: INV Sat + OLD Ratio
def obj_mix2(w):
    w1 = w[0]
    w2 = 1 - w1
    metrics = w1 * sat_inv_scores + w2 * ratio_old_scores
    return -abs(np.corrcoef(metrics, bw_array)[0, 1])

result_mix2 = minimize(obj_mix2, x0=[0.5], bounds=[(0, 1)], method='L-BFGS-B')
w1_mix2 = result_mix2.x[0]
w2_mix2 = 1 - w1_mix2
metrics_mix2 = w1_mix2 * sat_inv_scores + w2_mix2 * ratio_old_scores
corr_mix2 = np.corrcoef(metrics_mix2, bw_array)[0, 1]

print(f"\nMIX 1 (OLD Sat + INV Ratio):")
print(f"  Formula: {w1_mix1:.3f} × Sat_old + {w2_mix1:.3f} × Ratio_inv")
print(f"  Correlation: {corr_mix1:.4f}")

print(f"\nMIX 2 (INV Sat + OLD Ratio):")
print(f"  Formula: {w1_mix2:.3f} × Sat_inv + {w2_mix2:.3f} × Ratio_old")
print(f"  Correlation: {corr_mix2:.4f}")

# Summary table
print("\n" + "="*80)
print("FINAL RANKING")
print("="*80)

results = [
    ("OLD: Sat_old + Ratio_old", corr_old, w1_old, w2_old),
    ("INV: Sat_inv + Ratio_inv", corr_inv, w1_inv, w2_inv),
    ("MIX1: Sat_old + Ratio_inv", corr_mix1, w1_mix1, w2_mix1),
    ("MIX2: Sat_inv + Ratio_old", corr_mix2, w1_mix2, w2_mix2),
]

results_sorted = sorted(results, key=lambda x: abs(x[1]), reverse=True)

print(f"\n{'Rank':>4} | {'Method':<30} | {'Correlation':>12} | {'Weights':>20}")
print("-" * 75)
for i, (method, corr, w1, w2) in enumerate(results_sorted, 1):
    print(f"{i:4d} | {method:<30} | {corr:12.4f} | {w1:.2f} / {w2:.2f}")

# Visualization
fig, axes = plt.subplots(2, 3, figsize=(20, 12))

# Plot 1: OLD Sat vs BW
ax1 = axes[0, 0]
ax1.scatter(sat_old_scores, bw_array, c=bw_array, cmap='viridis', alpha=0.5, s=10)
slope1, intercept1, _, _, _ = stats.linregress(sat_old_scores, bw_array)
x_range = np.linspace(0, 1, 100)
ax1.plot(x_range, slope1*x_range + intercept1, 'r-', linewidth=2)
ax1.set_xlabel('OLD Saturation Score', fontsize=11, fontweight='bold')
ax1.set_ylabel('Bandwidth', fontsize=11, fontweight='bold')
ax1.set_title(f'OLD Sat [1-(ag/rg)]\nCorr={corr_sat_old:.3f}', fontsize=12, fontweight='bold')
ax1.grid(True, alpha=0.3)

# Plot 2: INV Sat vs BW
ax2 = axes[0, 1]
ax2.scatter(sat_inv_scores, bw_array, c=bw_array, cmap='plasma', alpha=0.5, s=10)
slope2, intercept2, _, _, _ = stats.linregress(sat_inv_scores, bw_array)
ax2.plot(x_range, slope2*x_range + intercept2, 'r-', linewidth=2)
ax2.set_xlabel('INV Saturation Score', fontsize=11, fontweight='bold')
ax2.set_ylabel('Bandwidth', fontsize=11, fontweight='bold')
ax2.set_title(f'INV Sat [rg/ag]\nCorr={corr_sat_inv:.3f}', fontsize=12, fontweight='bold')
ax2.grid(True, alpha=0.3)

# Plot 3: OLD Ratio vs BW
ax3 = axes[0, 2]
ax3.scatter(ratio_old_scores, bw_array, c=bw_array, cmap='coolwarm', alpha=0.5, s=10)
slope3, intercept3, _, _, _ = stats.linregress(ratio_old_scores, bw_array)
ax3.plot(x_range, slope3*x_range + intercept3, 'r-', linewidth=2)
ax3.set_xlabel('OLD Ratio Score', fontsize=11, fontweight='bold')
ax3.set_ylabel('Bandwidth', fontsize=11, fontweight='bold')
ax3.set_title(f'OLD Ratio [alloc/req]\nCorr={corr_ratio_old:.3f}', fontsize=12, fontweight='bold')
ax3.grid(True, alpha=0.3)

# Plot 4: INV Ratio vs BW
ax4 = axes[1, 0]
ax4.scatter(ratio_inv_scores, bw_array, c=bw_array, cmap='viridis', alpha=0.5, s=10)
slope4, intercept4, _, _, _ = stats.linregress(ratio_inv_scores, bw_array)
ax4.plot(x_range, slope4*x_range + intercept4, 'r-', linewidth=2)
ax4.set_xlabel('INV Ratio Score', fontsize=11, fontweight='bold')
ax4.set_ylabel('Bandwidth', fontsize=11, fontweight='bold')
ax4.set_title(f'INV Ratio [req/alloc]\nCorr={corr_ratio_inv:.3f}', fontsize=12, fontweight='bold')
ax4.grid(True, alpha=0.3)

# Plot 5: Best combined
best_method, best_corr, best_w1, best_w2 = results_sorted[0]
if "OLD" in best_method and "OLD" in best_method.split("+")[1]:
    best_metrics = metrics_old
elif "INV" in best_method and "INV" in best_method.split("+")[1]:
    best_metrics = metrics_inv
elif "MIX1" in best_method:
    best_metrics = metrics_mix1
else:
    best_metrics = metrics_mix2

ax5 = axes[1, 1]
ax5.scatter(best_metrics, bw_array, c=bw_array, cmap='plasma', alpha=0.5, s=10)
slope5, intercept5, _, _, _ = stats.linregress(best_metrics, bw_array)
ax5.plot(x_range, slope5*x_range + intercept5, 'r-', linewidth=2)
ax5.set_xlabel('Best Combined Metric', fontsize=11, fontweight='bold')
ax5.set_ylabel('Bandwidth', fontsize=11, fontweight='bold')
ax5.set_title(f'BEST: {best_method}\nCorr={best_corr:.3f}', fontsize=12, fontweight='bold')
ax5.grid(True, alpha=0.3)

# Plot 6: Comparison bar chart
ax6 = axes[1, 2]
methods = ['OLD\nCombined', 'INV\nCombined', 'MIX1\nS_old+R_inv', 'MIX2\nS_inv+R_old']
correlations = [corr_old, corr_inv, corr_mix1, corr_mix2]
colors = ['#3498db', '#e74c3c', '#2ecc71', '#f39c12']

bars = ax6.bar(range(len(methods)), correlations, color=colors, alpha=0.7,
               edgecolor='black', linewidth=2)

for bar, corr in zip(bars, correlations):
    height = bar.get_height()
    ax6.text(bar.get_x() + bar.get_width()/2., height + 0.01,
            f'{corr:.4f}', ha='center', va='bottom', fontsize=10, fontweight='bold')

ax6.set_xticks(range(len(methods)))
ax6.set_xticklabels(methods, fontsize=10, fontweight='bold')
ax6.set_ylabel('Correlation', fontsize=11, fontweight='bold')
ax6.set_title('Method Comparison', fontsize=12, fontweight='bold')
ax6.set_ylim([min(correlations)-0.05, max(correlations)+0.05])
ax6.grid(True, alpha=0.3, axis='y')

plt.tight_layout()
plt.savefig('/home/wuq/webrtc-local/inverted_definitions_test.png', dpi=300, bbox_inches='tight')
print(f"\n✅ Visualization saved to: /home/wuq/webrtc-local/inverted_definitions_test.png")

# Recommendation
print("\n" + "="*80)
print("RECOMMENDATION")
print("="*80)

best_method, best_corr, best_w1, best_w2 = results_sorted[0]
worst_method, worst_corr, _, _ = results_sorted[-1]

print(f"\n🏆 WINNER: {best_method}")
print(f"   Correlation: {best_corr:.4f}")
print(f"   Weights: {best_w1:.2f} / {best_w2:.2f}")

improvement = (best_corr - corr_old) / abs(corr_old) * 100
print(f"\n   Improvement over OLD: {improvement:+.1f}%")

if "INV" in best_method:
    print(f"\n   ✅ INVERTED definitions are better!")
    print(f"      Consider using:")
    if "Sat_inv" in best_method:
        print(f"      • Saturation = req_growth / alloc_growth")
    if "Ratio_inv" in best_method:
        print(f"      • Ratio = requested / allocated")
else:
    print(f"\n   ❌ Keep OLD definitions - they're already optimal!")

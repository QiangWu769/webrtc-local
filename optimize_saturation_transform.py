#!/usr/bin/env python3
import re
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt

# Parse log file
data = []
with open('/home/wuq/webrtc-local/webrtc_config_results/sender_local.log', 'r') as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        # Extract idle score
        idle_match = re.search(r'IdleScore:\s*([\d.]+)', line)
        if idle_match:
            idle_score = float(idle_match.group(1))
            saturation = 100 - idle_score

            # Find acked bitrate nearby
            for j in range(max(0, i-5), min(len(lines), i+6)):
                bwe_match = re.search(r'AckedBitrate:\s*(-?\d+)', lines[j])
                if bwe_match:
                    bitrate = int(bwe_match.group(1))
                    if bitrate > 0:  # Skip invalid -1 values
                        data.append((saturation, bitrate))
                    break

saturations = np.array([d[0] for d in data])
bitrates = np.array([d[1] for d in data])

print(f"Total data points: {len(data)}")

# Test different transformations
transformations = {
    'Original': saturations,
    'Square (x²)': saturations ** 2,
    'Cube (x³)': saturations ** 3,
    'Square root (√x)': np.sqrt(saturations),
    'Log (ln(x+1))': np.log(saturations + 1),
    'Exponential (exp(x/100))': np.exp(saturations / 100),
    'Power 1.5 (x^1.5)': saturations ** 1.5,
    'Power 2.5 (x^2.5)': saturations ** 2.5,
    'Sigmoid (1/(1+exp(-x/10)))': 1 / (1 + np.exp(-saturations/10)),
    'Tanh': np.tanh(saturations / 50),
}

results = []
for name, transformed in transformations.items():
    if np.all(np.isfinite(transformed)):
        corr, pval = stats.pearsonr(transformed, bitrates)
        results.append((name, corr, pval))
        print(f"{name:30s}: R = {corr:+.4f}, p = {pval:.2e}")

# Sort by absolute correlation
results.sort(key=lambda x: abs(x[1]), reverse=True)

print("\n=== Ranked by correlation strength ===")
for i, (name, corr, pval) in enumerate(results, 1):
    print(f"{i}. {name:30s}: R = {corr:+.4f}")

# Visualize top 4 transformations
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
axes = axes.flatten()

for i, (name, corr, pval) in enumerate(results[:4]):
    ax = axes[i]
    transformed = transformations[name]

    # Bin data
    bins = np.linspace(np.min(transformed), np.max(transformed), 20)
    bin_indices = np.digitize(transformed, bins)

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

    # Plot
    ax.plot(bin_centers, medians, 'r-', linewidth=2, label='Median')
    ax.fill_between(bin_centers, p25s, p75s, alpha=0.3, color='red')

    ax.set_xlabel(f'{name}')
    ax.set_ylabel('Acked Bitrate (bps)')
    ax.set_title(f'{name}\nR = {corr:+.4f}')
    ax.grid(True, alpha=0.3)
    ax.legend()

plt.tight_layout()
plt.savefig('/home/wuq/webrtc-local/transformation_comparison.png', dpi=150, bbox_inches='tight')
print(f"\nVisualization saved to transformation_comparison.png")

# Test Box-Cox style power transformations
print("\n=== Testing power transformations x^α ===")
alphas = np.linspace(0.5, 4.0, 36)
power_results = []
for alpha in alphas:
    transformed = saturations ** alpha
    if np.all(np.isfinite(transformed)):
        corr, _ = stats.pearsonr(transformed, bitrates)
        power_results.append((alpha, corr))
        if abs(alpha - round(alpha)) < 0.01:  # Print integer and half values
            print(f"x^{alpha:.1f}: R = {corr:+.4f}")

# Find optimal power
optimal_alpha, optimal_corr = max(power_results, key=lambda x: abs(x[1]))
print(f"\nOptimal power: α = {optimal_alpha:.2f}, R = {optimal_corr:+.4f}")

# Plot correlation vs power
fig, ax = plt.subplots(figsize=(10, 6))
alphas_plot = [r[0] for r in power_results]
corrs_plot = [r[1] for r in power_results]
ax.plot(alphas_plot, corrs_plot, 'b-', linewidth=2)
ax.axvline(optimal_alpha, color='r', linestyle='--', label=f'Optimal α={optimal_alpha:.2f}')
ax.axhline(0, color='k', linestyle='-', linewidth=0.5)
ax.set_xlabel('Power (α)')
ax.set_ylabel('Correlation with Acked Bitrate')
ax.set_title('Correlation vs Power Transformation (Saturation^α)')
ax.grid(True, alpha=0.3)
ax.legend()
plt.savefig('/home/wuq/webrtc-local/power_optimization.png', dpi=150, bbox_inches='tight')
print(f"Power optimization plot saved to power_optimization.png")

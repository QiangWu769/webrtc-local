#!/usr/bin/env python3
import re
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt

# Parse log using MonoTime alignment method
monotime_to_saturation = {}
monotime_to_bitrate = {}

with open('/home/wuq/webrtc-local/webrtc_config_results/sender_local.log', 'r') as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        # Extract monotime
        mono_match = re.search(r'MonoTime:\s*(\d+)', line)
        if mono_match:
            monotime = int(mono_match.group(1))

            # Check for acked bitrate
            bwe_match = re.search(r'AckedBitrate:\s*(-?\d+)', line)
            if bwe_match:
                bitrate = int(bwe_match.group(1))
                if bitrate > 0:
                    monotime_to_bitrate[monotime] = bitrate

        # Extract idle score
        idle_match = re.search(r'IdleScore:\s*([\d.]+)', line)
        if idle_match:
            idle_score = float(idle_match.group(1))
            saturation = 100 - idle_score

            # Find nearest monotime
            for j in range(max(0, i-5), min(len(lines), i+6)):
                mono_match2 = re.search(r'MonoTime:\s*(\d+)', lines[j])
                if mono_match2:
                    monotime = int(mono_match2.group(1))
                    monotime_to_saturation[monotime] = saturation
                    break

# Match by monotime (within 100ms tolerance)
data = []
for mono_sat, sat in monotime_to_saturation.items():
    for mono_bwe, bwe in monotime_to_bitrate.items():
        if abs(mono_sat - mono_bwe) <= 100:  # 100ms tolerance
            data.append((sat, bwe))
            break

saturations = np.array([d[0] for d in data])
bitrates = np.array([d[1] for d in data])

print(f"Total matched data points: {len(data)}")
print(f"Saturation range: [{saturations.min():.1f}, {saturations.max():.1f}]")
print(f"Bitrate range: [{bitrates.min()/1e6:.2f}, {bitrates.max()/1e6:.2f}] Mbps\n")

# Test different transformations
transformations = {
    'Original (x)': saturations,
    'Square (x²)': saturations ** 2,
    'Cube (x³)': saturations ** 3,
    'Fourth power (x⁴)': saturations ** 4,
    'Fifth power (x⁵)': saturations ** 5,
    'Square root (√x)': np.sqrt(saturations),
    'Log (ln(x+1))': np.log(saturations + 1),
    'Exponential (e^(x/100))': np.exp(saturations / 100),
    'Power 1.5 (x^1.5)': saturations ** 1.5,
    'Power 2.5 (x^2.5)': saturations ** 2.5,
    'Power 3.5 (x^3.5)': saturations ** 3.5,
}

results = []
for name, transformed in transformations.items():
    if np.all(np.isfinite(transformed)):
        corr, pval = stats.pearsonr(transformed, bitrates)
        results.append((name, corr, pval, transformed))

# Sort by absolute correlation
results.sort(key=lambda x: abs(x[1]), reverse=True)

print("=== Transformation correlation results ===")
for i, (name, corr, pval, _) in enumerate(results, 1):
    print(f"{i:2d}. {name:25s}: R = {corr:+.4f}, p = {pval:.2e}")

# Test fine-grained power transformations
print("\n=== Fine-grained power search (x^α) ===")
alphas = np.linspace(0.5, 6.0, 111)
power_results = []
for alpha in alphas:
    transformed = saturations ** alpha
    if np.all(np.isfinite(transformed)):
        corr, _ = stats.pearsonr(transformed, bitrates)
        power_results.append((alpha, corr))

# Find optimal power
optimal_alpha, optimal_corr = max(power_results, key=lambda x: abs(x[1]))
print(f"Optimal power: α = {optimal_alpha:.3f}, R = {optimal_corr:+.4f}")

# Visualize top 4 transformations
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
axes = axes.flatten()

for i, (name, corr, pval, transformed) in enumerate(results[:4]):
    ax = axes[i]

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
            medians.append(np.median(bitrates[mask]) / 1e6)  # Convert to Mbps
            p25s.append(np.percentile(bitrates[mask], 25) / 1e6)
            p75s.append(np.percentile(bitrates[mask], 75) / 1e6)

    # Plot
    ax.plot(bin_centers, medians, 'r-', linewidth=2.5)
    ax.fill_between(bin_centers, p25s, p75s, alpha=0.3, color='red')

    ax.set_xlabel(f'{name}', fontsize=11)
    ax.set_ylabel('Acked Bitrate (Mbps)', fontsize=11)
    ax.set_title(f'{name}\nCorrelation R = {corr:+.4f}', fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('/home/wuq/webrtc-local/transformation_comparison.png', dpi=150, bbox_inches='tight')
print(f"\nVisualization saved to transformation_comparison.png")

# Plot correlation vs power
fig, ax = plt.subplots(figsize=(12, 7))
alphas_plot = [r[0] for r in power_results]
corrs_plot = [r[1] for r in power_results]
ax.plot(alphas_plot, corrs_plot, 'b-', linewidth=2.5)
ax.axvline(optimal_alpha, color='r', linestyle='--', linewidth=2, label=f'最优 α={optimal_alpha:.3f}')
ax.axhline(0, color='k', linestyle='-', linewidth=0.5)

# Mark integer powers
for alpha in [1, 2, 3, 4, 5, 6]:
    if alpha <= 6:
        idx = np.argmin(np.abs(np.array(alphas_plot) - alpha))
        corr_at_alpha = corrs_plot[idx]
        ax.plot(alpha, corr_at_alpha, 'go', markersize=8)
        ax.text(alpha, corr_at_alpha + 0.01, f'{alpha}', ha='center', fontsize=10)

ax.set_xlabel('幂指数 α', fontsize=13)
ax.set_ylabel('与比特率的相关系数', fontsize=13)
ax.set_title('饱和度^α 变换的相关性优化', fontsize=14, fontweight='bold')
ax.grid(True, alpha=0.3)
ax.legend(fontsize=11)
plt.savefig('/home/wuq/webrtc-local/power_optimization.png', dpi=150, bbox_inches='tight')
print(f"Power optimization plot saved to power_optimization.png")

# Create optimal transformation visualization
optimal_transformed = saturations ** optimal_alpha

bins = np.linspace(np.min(optimal_transformed), np.max(optimal_transformed), 25)
bin_indices = np.digitize(optimal_transformed, bins)

bin_centers = []
medians = []
p25s = []
p75s = []

for b in range(1, len(bins)):
    mask = bin_indices == b
    if np.sum(mask) > 5:
        bin_centers.append((bins[b-1] + bins[b]) / 2)
        medians.append(np.median(bitrates[mask]) / 1e6)
        p25s.append(np.percentile(bitrates[mask], 25) / 1e6)
        p75s.append(np.percentile(bitrates[mask], 75) / 1e6)

fig, ax = plt.subplots(figsize=(10, 7))
ax.plot(bin_centers, medians, 'r-', linewidth=2.5)
ax.fill_between(bin_centers, p25s, p75s, alpha=0.3, color='red')
ax.set_xlabel(f'饱和度^{optimal_alpha:.3f}', fontsize=13)
ax.set_ylabel('比特率 (Mbps)', fontsize=13)
ax.set_title(f'最优变换函数\n相关系数 R = {optimal_corr:+.4f}', fontsize=14, fontweight='bold')
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('/home/wuq/webrtc-local/optimal_transformation.png', dpi=150, bbox_inches='tight')
print(f"Optimal transformation plot saved to optimal_transformation.png")

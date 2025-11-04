#!/usr/bin/env python3
"""
Final comparison: Linear vs Square Root gain function
"""
import numpy as np
import matplotlib.pyplot as plt

# The two functions
def linear_gain(r):
    return np.clip(0.5 + 0.75 * r, 0, 2)

def sqrt_gain(r):
    r = np.clip(r, 0, 2)
    normalized = r / 2.0
    return 0.5 + 1.5 * np.sqrt(normalized)

# Generate test data
ratios = np.linspace(0, 2, 300)
linear = linear_gain(ratios)
sqrt = sqrt_gain(ratios)

# Create side-by-side comparison
fig, axes = plt.subplots(1, 3, figsize=(18, 5))

# Plot 1: Both functions
ax1 = axes[0]
ax1.plot(ratios, linear, 'b--', linewidth=3, label='Linear (old)', alpha=0.8)
ax1.plot(ratios, sqrt, 'r-', linewidth=3.5, label='Square Root (new)', alpha=0.9)

# Highlight high-density region
ax1.axvspan(0.2, 0.4, alpha=0.15, color='yellow', label='High data density\n(61% of samples)')

# Mark key points
key_ratios = [0.2, 0.3, 0.4, 0.6, 1.0]
for r in key_ratios:
    l = linear_gain(r)
    s = sqrt_gain(r)
    ax1.plot(r, l, 'bo', markersize=8)
    ax1.plot(r, s, 'ro', markersize=8)

    # Show difference
    if r <= 0.6:
        ax1.plot([r, r], [l, s], 'g-', linewidth=2, alpha=0.5)
        mid = (l + s) / 2
        diff = s - l
        ax1.text(r + 0.02, mid, f'+{diff:.2f}', fontsize=9, color='green', fontweight='bold')

ax1.set_xlabel('Cellular Resource Ratio', fontsize=13, fontweight='bold')
ax1.set_ylabel('Gain Factor', fontsize=13, fontweight='bold')
ax1.set_title('Function Comparison', fontsize=14, fontweight='bold')
ax1.grid(True, alpha=0.3)
ax1.legend(fontsize=11)
ax1.set_xlim(0, 2)
ax1.set_ylim(0.4, 2.1)

# Plot 2: Difference (sqrt - linear)
ax2 = axes[1]
difference = sqrt - linear
ax2.fill_between(ratios, 0, difference, alpha=0.3, color='green')
ax2.plot(ratios, difference, 'g-', linewidth=3)
ax2.axhline(y=0, color='black', linestyle='--', alpha=0.5)
ax2.axvspan(0.2, 0.4, alpha=0.15, color='yellow')

max_diff_idx = np.argmax(difference)
max_diff_ratio = ratios[max_diff_idx]
max_diff_value = difference[max_diff_idx]
ax2.plot(max_diff_ratio, max_diff_value, 'ro', markersize=12)
ax2.annotate(f'Max diff: +{max_diff_value:.2f}\nat ratio={max_diff_ratio:.2f}',
            xy=(max_diff_ratio, max_diff_value),
            xytext=(20, 20),
            textcoords='offset points',
            fontsize=10,
            bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.8),
            arrowprops=dict(arrowstyle='->', color='red', lw=2))

ax2.set_xlabel('Ratio', fontsize=13, fontweight='bold')
ax2.set_ylabel('Gain Increase (Sqrt - Linear)', fontsize=13, fontweight='bold')
ax2.set_title('Improvement by Square Root', fontsize=14, fontweight='bold')
ax2.grid(True, alpha=0.3)
ax2.set_xlim(0, 2)

# Plot 3: Sensitivity comparison (derivative)
ax3 = axes[2]
deriv_linear = np.gradient(linear, ratios)
deriv_sqrt = np.gradient(sqrt, ratios)

ax3.plot(ratios, deriv_linear, 'b--', linewidth=3, label='Linear (constant = 0.75)', alpha=0.8)
ax3.plot(ratios, deriv_sqrt, 'r-', linewidth=3.5, label='Square Root (adaptive)', alpha=0.9)
ax3.axvspan(0.2, 0.4, alpha=0.15, color='yellow')

ax3.set_xlabel('Ratio', fontsize=13, fontweight='bold')
ax3.set_ylabel('Sensitivity (dGain/dRatio)', fontsize=13, fontweight='bold')
ax3.set_title('Sensitivity Comparison', fontsize=14, fontweight='bold')
ax3.grid(True, alpha=0.3)
ax3.legend(fontsize=11)
ax3.set_xlim(0, 1.5)
ax3.set_ylim(0, 2)

plt.tight_layout()
plt.savefig('/home/wuq/webrtc-local/final_gain_comparison.png', dpi=150, bbox_inches='tight')
print("Plot saved: final_gain_comparison.png")

# Print comparison table
print("\n=== Gain Comparison Table ===")
print("Ratio | Linear | Sqrt | Difference | % Increase")
print("-" * 60)
for r in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.5, 2.0]:
    l = linear_gain(r)
    s = sqrt_gain(r)
    diff = s - l
    pct = (diff / l * 100) if l > 0 else 0
    print(f"{r:5.1f} | {l:6.2f} | {s:5.2f} | {diff:+10.2f} | {pct:+9.1f}%")

print("\n=== Key Benefits ===")
print("1. More responsive in dense region [0.2, 0.4]:")
dense_linear_change = linear_gain(0.4) - linear_gain(0.2)
dense_sqrt_change = sqrt_gain(0.4) - sqrt_gain(0.2)
print(f"   Linear:      {dense_linear_change:.3f} gain increase")
print(f"   Square Root: {dense_sqrt_change:.3f} gain increase")
print(f"   Improvement: {(dense_sqrt_change - dense_linear_change):.3f} (+{((dense_sqrt_change/dense_linear_change - 1)*100):.1f}%)")

print("\n2. Peak difference at ratio ~{:.2f}: +{:.3f} gain".format(max_diff_ratio, max_diff_value))

print("\n3. Formula:")
print("   OLD: gain = 0.5 + 0.75 × ratio")
print("   NEW: gain = 0.5 + 1.5 × sqrt(ratio / 2)")

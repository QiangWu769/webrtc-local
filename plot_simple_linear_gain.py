#!/usr/bin/env python3
import numpy as np
import matplotlib.pyplot as plt

# The simple linear function
def get_gain(ratio):
    return np.clip(0.5 + 0.75 * ratio, 0.0, 2.0)

# Generate data
ratios = np.linspace(0, 2, 200)
gains = get_gain(ratios)

# Create plot
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Plot 1: Main function
ax1 = axes[0]
ax1.plot(ratios, gains, 'b-', linewidth=3, label='gain = 0.5 + 0.75 × ratio')

# Mark key points
key_points = [(0.0, 0.5), (0.2, 0.65), (0.5, 0.875), (1.0, 1.25), (1.5, 1.625), (2.0, 2.0)]
for r, g in key_points:
    actual_g = get_gain(r)
    ax1.plot(r, actual_g, 'ro', markersize=10, zorder=5)
    ax1.annotate(f'({r:.1f}, {actual_g:.2f})',
                xy=(r, actual_g),
                xytext=(10, -15),
                textcoords='offset points',
                fontsize=10,
                bbox=dict(boxstyle='round,pad=0.4', facecolor='yellow', alpha=0.8))

ax1.set_xlabel('Ratio', fontsize=14, fontweight='bold')
ax1.set_ylabel('Gain Factor', fontsize=14, fontweight='bold')
ax1.set_title('Simple Linear Mapping: Ratio → Gain', fontsize=15, fontweight='bold')
ax1.grid(True, alpha=0.3)
ax1.legend(fontsize=12, loc='upper left')
ax1.set_xlim(0, 2)
ax1.set_ylim(0, 2.2)

# Add formula box
formula_text = 'gain = 0.5 + 0.75 × ratio\n\nClipped to [0, 2]'
ax1.text(0.98, 0.05, formula_text,
        transform=ax1.transAxes,
        fontsize=11,
        verticalalignment='bottom',
        horizontalalignment='right',
        bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))

# Plot 2: Derivative (slope)
ax2 = axes[1]
derivative = np.gradient(gains, ratios)
ax2.plot(ratios, derivative, 'g-', linewidth=3)
ax2.axhline(y=0.75, color='r', linestyle='--', linewidth=2, label='Slope = 0.75')
ax2.set_xlabel('Ratio', fontsize=14, fontweight='bold')
ax2.set_ylabel('dGain/dRatio (Slope)', fontsize=14, fontweight='bold')
ax2.set_title('Derivative: Constant Slope', fontsize=15, fontweight='bold')
ax2.grid(True, alpha=0.3)
ax2.legend(fontsize=12)
ax2.set_xlim(0, 2)
ax2.set_ylim(0.6, 0.9)

plt.tight_layout()
plt.savefig('/home/wuq/webrtc-local/simple_linear_gain_function.png', dpi=150, bbox_inches='tight')
print("Plot saved: simple_linear_gain_function.png")

# Print function details
print("\n=== Function: gain = 0.5 + 0.75 × ratio ===")
print("\nKey Points:")
print("Ratio | Gain")
print("------|------")
for r, g in key_points:
    print(f"{r:5.1f} | {g:.3f}")

print("\nFunction Properties:")
print(f"  - Type: Linear")
print(f"  - Slope: 0.75 (constant)")
print(f"  - Intercept: 0.5")
print(f"  - Range: [0.5, 2.0]")
print(f"  - Domain: [0.0, 2.0]")

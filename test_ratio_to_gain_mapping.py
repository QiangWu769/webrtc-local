#!/usr/bin/env python3
"""
Test the ratio -> gain mapping function to verify it matches requirements
"""
import numpy as np
import matplotlib.pyplot as plt

def get_gain_from_ratio(ratio):
    """
    Python implementation of GetGainFactorFromRatio C++ function
    """
    ratio = np.clip(ratio, 0.0, 2.0)

    def smooth_step(edge0, edge1, x):
        t = np.clip((x - edge0) / (edge1 - edge0), 0.0, 1.0)
        return t * t * (3.0 - 2.0 * t)

    if isinstance(ratio, np.ndarray):
        result = np.zeros_like(ratio, dtype=float)

        # Segment 1: [0.0, 0.2] -> gain [0.5, 0.7]
        mask1 = ratio <= 0.2
        t1 = smooth_step(0.0, 0.2, ratio[mask1])
        result[mask1] = 0.5 + (0.7 - 0.5) * t1

        # Segment 2: [0.2, 0.5] -> gain [0.7, 1.1]
        mask2 = (ratio > 0.2) & (ratio <= 0.5)
        t2 = smooth_step(0.2, 0.5, ratio[mask2])
        result[mask2] = 0.7 + (1.1 - 0.7) * t2

        # Segment 3: [0.5, 1.0] -> gain [1.1, 1.7]
        mask3 = (ratio > 0.5) & (ratio <= 1.0)
        t3 = smooth_step(0.5, 1.0, ratio[mask3])
        result[mask3] = 1.1 + (1.7 - 1.1) * t3

        # Segment 4: [1.0, 2.0] -> gain [1.7, 2.0]
        mask4 = ratio > 1.0
        t4 = smooth_step(1.0, 2.0, ratio[mask4])
        result[mask4] = 1.7 + (2.0 - 1.7) * t4

        return result
    else:
        if ratio <= 0.2:
            t = smooth_step(0.0, 0.2, ratio)
            return 0.5 + (0.7 - 0.5) * t
        elif ratio <= 0.5:
            t = smooth_step(0.2, 0.5, ratio)
            return 0.7 + (1.1 - 0.7) * t
        elif ratio <= 1.0:
            t = smooth_step(0.5, 1.0, ratio)
            return 1.1 + (1.7 - 1.1) * t
        else:
            t = smooth_step(1.0, 2.0, ratio)
            return 1.7 + (2.0 - 1.7) * t

# Test key control points
print("=== Verifying Control Points ===")
test_points = [
    (0.0, 0.5, "Start point"),
    (0.2, 0.7, "Low ratio threshold"),
    (0.5, 1.1, "Medium ratio threshold"),
    (1.0, 1.7, "High ratio threshold"),
    (2.0, 2.0, "Max point")
]

print("Ratio -> Expected Gain | Actual Gain | Error")
print("-" * 50)
all_correct = True
for ratio, expected_gain, desc in test_points:
    actual_gain = get_gain_from_ratio(ratio)
    error = abs(actual_gain - expected_gain)
    status = "✓" if error < 0.001 else "✗"
    print(f"{ratio:4.1f} -> {expected_gain:4.1f} | {actual_gain:6.3f} | {error:.4f} {status} ({desc})")
    if error >= 0.001:
        all_correct = False

if all_correct:
    print("\n✓ All control points verified successfully!")
else:
    print("\n✗ Some control points have errors!")

# Test intermediate points
print("\n=== Sample Intermediate Points ===")
print("Ratio | Gain")
print("-" * 20)
for r in [0.1, 0.15, 0.3, 0.4, 0.6, 0.8, 1.2, 1.5]:
    g = get_gain_from_ratio(r)
    print(f"{r:4.2f} | {g:5.3f}")

# Visualization
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Plot 1: Mapping function
ax1 = axes[0]
ratios = np.linspace(0, 2, 200)
gains = get_gain_from_ratio(ratios)

ax1.plot(ratios, gains, 'b-', linewidth=2.5, label='Gain = f(Ratio)')
ax1.plot([p[0] for p in test_points], [p[1] for p in test_points],
         'ro', markersize=10, label='Control Points', zorder=5)

# Add annotations
for ratio, gain, desc in test_points:
    ax1.annotate(f'({ratio:.1f}, {gain:.1f})',
                xy=(ratio, gain),
                xytext=(10, 10),
                textcoords='offset points',
                fontsize=9,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7))

ax1.set_xlabel('Cellular Resource Ratio', fontsize=12, fontweight='bold')
ax1.set_ylabel('Gain Factor', fontsize=12, fontweight='bold')
ax1.set_title('Ratio → Gain Factor Mapping', fontsize=13, fontweight='bold')
ax1.grid(True, alpha=0.3)
ax1.legend(fontsize=10)
ax1.set_xlim(0, 2)
ax1.set_ylim(0, 2.2)

# Plot 2: Derivative (rate of change)
ax2 = axes[1]
derivative = np.gradient(gains, ratios)
ax2.plot(ratios, derivative, 'g-', linewidth=2)
ax2.axhline(y=0, color='r', linestyle='--', alpha=0.5)
ax2.set_xlabel('Cellular Resource Ratio', fontsize=12, fontweight='bold')
ax2.set_ylabel('dGain/dRatio', fontsize=12, fontweight='bold')
ax2.set_title('Derivative (Sensitivity)', fontsize=13, fontweight='bold')
ax2.grid(True, alpha=0.3)
ax2.set_xlim(0, 2)

plt.tight_layout()
plt.savefig('/home/wuq/webrtc-local/ratio_to_gain_function_test.png', dpi=150, bbox_inches='tight')
print("\nPlot saved: ratio_to_gain_function_test.png")

# Summary statistics
print("\n=== Function Statistics ===")
print(f"Minimum gain (at ratio=0.0): {get_gain_from_ratio(0.0):.3f}")
print(f"Maximum gain (at ratio=2.0): {get_gain_from_ratio(2.0):.3f}")
print(f"Gain range: [{get_gain_from_ratio(0.0):.3f}, {get_gain_from_ratio(2.0):.3f}]")
print(f"Average derivative: {np.mean(derivative):.3f}")
print(f"Max derivative: {np.max(derivative):.3f} (most sensitive region)")
print(f"Min derivative: {np.min(derivative):.3f}")

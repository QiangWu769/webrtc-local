#!/usr/bin/env python3
"""
Compare Square Root vs Sigmoid for gain function
"""
import numpy as np
import matplotlib.pyplot as plt

# Square root function (current)
def sqrt_gain(r):
    r = np.clip(r, 0, 2)
    normalized = r / 2.0
    return 0.5 + 1.5 * np.sqrt(normalized)

# Sigmoid options
def sigmoid_v1(r):
    """Centered at 0.5, moderate steepness"""
    r = np.clip(r, 0, 2)
    x = (r - 0.5) * 4  # center=0.5, steepness=4
    sigmoid = 1.0 / (1.0 + np.exp(-x))
    return 0.5 + 1.5 * sigmoid

def sigmoid_v2(r):
    """Centered at 0.3 (closer to data peak), steeper"""
    r = np.clip(r, 0, 2)
    x = (r - 0.3) * 6  # center=0.3, steepness=6
    sigmoid = 1.0 / (1.0 + np.exp(-x))
    return 0.5 + 1.5 * sigmoid

def sigmoid_v3(r):
    """Centered at 0.4, balanced steepness"""
    r = np.clip(r, 0, 2)
    x = (r - 0.4) * 5  # center=0.4, steepness=5
    sigmoid = 1.0 / (1.0 + np.exp(-x))
    return 0.5 + 1.5 * sigmoid

# Test ratios
test_ratios = np.linspace(0, 2, 300)

# Calculate gains
sqrt_vals = sqrt_gain(test_ratios)
sig1_vals = sigmoid_v1(test_ratios)
sig2_vals = sigmoid_v2(test_ratios)
sig3_vals = sigmoid_v3(test_ratios)

# Create comparison
fig, axes = plt.subplots(2, 2, figsize=(15, 11))

# Plot 1: All sigmoid variants vs sqrt
ax1 = axes[0, 0]
ax1.plot(test_ratios, sqrt_vals, 'b-', linewidth=3, label='Square Root (current)', alpha=0.8)
ax1.plot(test_ratios, sig1_vals, 'r-', linewidth=2.5, label='Sigmoid v1 (center=0.5)', alpha=0.8)
ax1.plot(test_ratios, sig2_vals, 'g-', linewidth=2.5, label='Sigmoid v2 (center=0.3)', alpha=0.8)
ax1.plot(test_ratios, sig3_vals, 'm-', linewidth=2.5, label='Sigmoid v3 (center=0.4)', alpha=0.8)

# Highlight high-density region
ax1.axvspan(0.2, 0.4, alpha=0.15, color='yellow', label='61% data here')
ax1.set_xlabel('Ratio', fontsize=13, fontweight='bold')
ax1.set_ylabel('Gain Factor', fontsize=13, fontweight='bold')
ax1.set_title('Sigmoid Variants vs Square Root', fontsize=14, fontweight='bold')
ax1.grid(True, alpha=0.3)
ax1.legend(fontsize=10)
ax1.set_xlim(0, 2)
ax1.set_ylim(0.4, 2.1)

# Plot 2: Best sigmoid (v3) vs sqrt - zoomed to [0, 0.8]
ax2 = axes[0, 1]
zoom_mask = test_ratios <= 0.8
zoom_r = test_ratios[zoom_mask]
ax2.plot(zoom_r, sqrt_gain(zoom_r), 'b-', linewidth=3.5, label='Square Root', alpha=0.8)
ax2.plot(zoom_r, sigmoid_v3(zoom_r), 'm-', linewidth=3.5, label='Sigmoid v3 (recommended)', alpha=0.8)

ax2.axvspan(0.2, 0.4, alpha=0.2, color='yellow')

# Mark key points
for r in [0.2, 0.3, 0.4, 0.5, 0.6]:
    s = sqrt_gain(r)
    sig = sigmoid_v3(r)
    ax2.plot(r, s, 'bo', markersize=10)
    ax2.plot(r, sig, 'mo', markersize=10)

ax2.set_xlabel('Ratio', fontsize=13, fontweight='bold')
ax2.set_ylabel('Gain Factor', fontsize=13, fontweight='bold')
ax2.set_title('Zoomed: Best Comparison [0, 0.8]', fontsize=14, fontweight='bold')
ax2.grid(True, alpha=0.3)
ax2.legend(fontsize=11)
ax2.set_xlim(0, 0.8)

# Plot 3: Sensitivity (derivative)
ax3 = axes[1, 0]
deriv_sqrt = np.gradient(sqrt_vals, test_ratios)
deriv_sig3 = np.gradient(sig3_vals, test_ratios)

ax3.plot(test_ratios, deriv_sqrt, 'b-', linewidth=3, label='Square Root', alpha=0.8)
ax3.plot(test_ratios, deriv_sig3, 'm-', linewidth=3, label='Sigmoid v3', alpha=0.8)
ax3.axvspan(0.2, 0.4, alpha=0.15, color='yellow')

ax3.set_xlabel('Ratio', fontsize=13, fontweight='bold')
ax3.set_ylabel('Sensitivity (dGain/dRatio)', fontsize=13, fontweight='bold')
ax3.set_title('Sensitivity Comparison', fontsize=14, fontweight='bold')
ax3.grid(True, alpha=0.3)
ax3.legend(fontsize=11)
ax3.set_xlim(0, 1.5)

# Plot 4: Difference (sigmoid - sqrt)
ax4 = axes[1, 1]
diff = sig3_vals - sqrt_vals
ax4.fill_between(test_ratios, 0, diff, where=(diff >= 0), alpha=0.3,
                 color='green', label='Sigmoid higher', interpolate=True)
ax4.fill_between(test_ratios, 0, diff, where=(diff < 0), alpha=0.3,
                 color='red', label='Sqrt higher', interpolate=True)
ax4.plot(test_ratios, diff, 'm-', linewidth=3)
ax4.axhline(y=0, color='black', linestyle='--', alpha=0.5)
ax4.axvspan(0.2, 0.4, alpha=0.15, color='yellow')

ax4.set_xlabel('Ratio', fontsize=13, fontweight='bold')
ax4.set_ylabel('Difference (Sigmoid - Sqrt)', fontsize=13, fontweight='bold')
ax4.set_title('Which Function Gives Higher Gain?', fontsize=14, fontweight='bold')
ax4.grid(True, alpha=0.3)
ax4.legend(fontsize=11)
ax4.set_xlim(0, 1.5)

plt.tight_layout()
plt.savefig('/home/wuq/webrtc-local/sqrt_vs_sigmoid_comparison.png', dpi=150, bbox_inches='tight')
print("Plot saved: sqrt_vs_sigmoid_comparison.png")

# Comparison table
print("\n=== Detailed Comparison: Sqrt vs Sigmoid v3 ===")
print("Ratio | Sqrt | Sigmoid | Difference | Winner")
print("-" * 60)
for r in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.5, 2.0]:
    s = sqrt_gain(r)
    sig = sigmoid_v3(r)
    diff = sig - s
    winner = "Sigmoid" if diff > 0.01 else ("Sqrt" if diff < -0.01 else "Same")
    print(f"{r:5.1f} | {s:5.2f} | {sig:7.2f} | {diff:+10.3f} | {winner}")

# Sensitivity in dense region
print("\n=== Sensitivity in High-Density Region [0.2, 0.4] ===")
dense_r = np.linspace(0.2, 0.4, 100)
sqrt_change = sqrt_gain(0.4) - sqrt_gain(0.2)
sig3_change = sigmoid_v3(0.4) - sigmoid_v3(0.2)

sqrt_deriv = np.mean(np.gradient(sqrt_gain(dense_r), dense_r))
sig3_deriv = np.mean(np.gradient(sigmoid_v3(dense_r), dense_r))

print(f"Square Root:")
print(f"  Gain change [0.2→0.4]: {sqrt_change:.3f}")
print(f"  Avg derivative: {sqrt_deriv:.3f}")
print(f"\nSigmoid v3:")
print(f"  Gain change [0.2→0.4]: {sig3_change:.3f}")
print(f"  Avg derivative: {sig3_deriv:.3f}")
print(f"\nDifference: {sig3_change - sqrt_change:+.3f} ({((sig3_change/sqrt_change-1)*100):+.1f}%)")

# Formulas
print("\n=== C++ Implementation ===")
print("\n// Square Root (simpler)")
print("double gain = 0.5 + 1.5 * std::sqrt(ratio / 2.0);")
print("\n// Sigmoid v3 (more flexible)")
print("double x = (ratio - 0.4) * 5.0;")
print("double sigmoid = 1.0 / (1.0 + std::exp(-x));")
print("double gain = 0.5 + 1.5 * sigmoid;")

print("\n=== Pros & Cons ===")
print("\nSquare Root:")
print("  ✓ Simpler (1 sqrt operation)")
print("  ✓ Always smooth, monotonic")
print("  ✓ Easy to understand")
print("  ✗ Less flexible")

print("\nSigmoid:")
print("  ✓ More control (can adjust center & steepness)")
print("  ✓ S-curve shape (slow-fast-slow)")
print("  ✓ More aggressive in middle range")
print("  ✗ Slightly more complex (exp operation)")
print("  ✗ Need to tune parameters")

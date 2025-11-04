#!/usr/bin/env python3
import numpy as np
import matplotlib.pyplot as plt

# Sigmoid function
def sigmoid_gain(r):
    r = np.clip(r, 0, 2)
    x = (r - 0.4) * 5.0
    sigmoid = 1.0 / (1.0 + np.exp(-x))
    return 0.5 + 1.5 * sigmoid

# Generate data
ratios = np.linspace(0, 2, 400)
gains = sigmoid_gain(ratios)

# Create square plot
fig, ax = plt.subplots(figsize=(10, 10))

# Plot sigmoid curve
ax.plot(ratios, gains, 'r-', linewidth=4.5, label='Sigmoid (NEW)', zorder=3)

# Highlight high-density region
ax.axvspan(0.2, 0.4, alpha=0.15, color='yellow', label='High density (61%)', zorder=1)

# Mark key points
key_points = [(0.2, 0.90), (0.3, 1.07), (0.4, 1.25), (0.5, 1.43), (0.6, 1.60)]
for r, g in key_points:
    actual_g = sigmoid_gain(r)
    ax.plot(r, actual_g, 'ro', markersize=14, zorder=5)
    # Add value labels
    ax.annotate(f'{actual_g:.2f}', xy=(r, actual_g),
                xytext=(0, 15), textcoords='offset points',
                fontsize=13, ha='center', fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.4', facecolor='yellow',
                         alpha=0.9, edgecolor='black', linewidth=1.5))

# Styling
ax.set_xlabel('Cellular Resource Ratio', fontsize=16, fontweight='bold')
ax.set_ylabel('Gain Factor', fontsize=16, fontweight='bold')
ax.set_title('Sigmoid Gain Function: Ratio → Gain Mapping', fontsize=18, fontweight='bold', pad=20)
ax.grid(True, alpha=0.3, linewidth=1.5)
ax.legend(fontsize=14, loc='upper left')
ax.set_xlim(0, 2)
ax.set_ylim(0.4, 2.1)

# Increase tick label size
ax.tick_params(axis='both', labelsize=13)

# Add formula box
formula = 'x = (ratio - 0.4) × 5.0\nsigmoid = 1 / (1 + e⁻ˣ)\ngain = 0.5 + 1.5 × sigmoid'
ax.text(0.97, 0.08, formula, transform=ax.transAxes,
        fontsize=14, family='monospace',
        verticalalignment='bottom', horizontalalignment='right',
        bbox=dict(boxstyle='round,pad=0.9', facecolor='lightcyan',
                 alpha=0.95, edgecolor='blue', linewidth=2.5))

plt.tight_layout()
plt.savefig('/home/wuq/webrtc-local/slides/sigmoid_gain_square.png', dpi=150, bbox_inches='tight')
print("Plot saved: slides/sigmoid_gain_square.png")
print(f"Figure size: {fig.get_size_inches()[0]:.1f}x{fig.get_size_inches()[1]:.1f} inches (square)")

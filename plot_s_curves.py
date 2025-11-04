#!/usr/bin/env python3
import numpy as np
import matplotlib.pyplot as plt

# Sigmoid (current)
def sigmoid_gain(r):
    r = np.clip(r, 0, 2)
    x = (r - 0.4) * 5.0
    sigmoid = 1.0 / (1.0 + np.exp(-x))
    return 0.5 + 1.5 * sigmoid

# Tanh
def tanh_gain(r):
    r = np.clip(r, 0, 2)
    x = (r - 0.4) * 3.0
    tanh_val = np.tanh(x)
    return 1.25 + 0.75 * tanh_val

# Arctan
def atan_gain(r):
    r = np.clip(r, 0, 2)
    x = (r - 0.4) * 4.0
    atan_val = np.arctan(x) / np.pi
    return 1.25 + 1.5 * atan_val

# Generate data
ratios = np.linspace(0, 1.6, 400)

# Create plot
fig, ax = plt.subplots(figsize=(10, 10))

# Plot curves
ax.plot(ratios, sigmoid_gain(ratios), 'r-', linewidth=5, label='Sigmoid (current)', alpha=0.9)
ax.plot(ratios, tanh_gain(ratios), 'b-', linewidth=5, label='Tanh', alpha=0.9)
ax.plot(ratios, atan_gain(ratios), color='pink', linewidth=5, label='Arctan', alpha=0.7)

# Highlight high-density region
ax.axvspan(0.2, 0.4, alpha=0.2, color='yellow', zorder=0)

# Styling
ax.set_xlabel('Ratio', fontsize=18, fontweight='bold')
ax.set_ylabel('Gain Factor', fontsize=18, fontweight='bold')
ax.set_title('S-Curves', fontsize=20, fontweight='bold', pad=20)
ax.grid(True, alpha=0.3, linewidth=1.5)
ax.legend(fontsize=16, loc='lower right')
ax.set_xlim(0, 1.6)
ax.set_ylim(0.6, 2.0)

# Increase tick label size
ax.tick_params(axis='both', labelsize=15)

plt.tight_layout()
plt.savefig('/home/wuq/webrtc-local/slides/s_curves.png', dpi=150, bbox_inches='tight')
print("Plot saved: slides/s_curves.png")

#!/usr/bin/env python3
"""
Explore various smooth functions for ratio -> gain mapping
"""
import numpy as np
import matplotlib.pyplot as plt

# Function 1: Sigmoid (current)
def sigmoid_gain(r):
    r = np.clip(r, 0, 2)
    x = (r - 0.4) * 5.0
    sigmoid = 1.0 / (1.0 + np.exp(-x))
    return 0.5 + 1.5 * sigmoid

# Function 2: Tanh (smoother S-curve)
def tanh_gain(r):
    r = np.clip(r, 0, 2)
    # tanh is symmetric S-curve, map to [0.5, 2.0]
    x = (r - 0.4) * 3.0  # steepness
    tanh_val = np.tanh(x)  # range [-1, 1]
    return 1.25 + 0.75 * tanh_val  # map to [0.5, 2.0]

# Function 3: Exponential
def exp_gain(r):
    r = np.clip(r, 0, 2)
    # Exponential growth: more aggressive at high ratio
    return 0.5 + 1.5 * (1 - np.exp(-1.5 * r))

# Function 4: Logarithmic
def log_gain(r):
    r = np.clip(r, 0.01, 2)
    # Log: very sensitive at low ratio, saturates quickly
    normalized = r / 2.0
    log_val = np.log1p(normalized * 10) / np.log1p(10)
    return 0.5 + 1.5 * log_val

# Function 5: Power 0.5 (square root)
def sqrt_gain(r):
    r = np.clip(r, 0, 2)
    return 0.5 + 1.5 * np.sqrt(r / 2.0)

# Function 6: Power 0.7 (between linear and sqrt)
def power07_gain(r):
    r = np.clip(r, 0, 2)
    return 0.5 + 1.5 * ((r / 2.0) ** 0.7)

# Function 7: Arctan (another S-curve)
def atan_gain(r):
    r = np.clip(r, 0, 2)
    # arctan: smooth S-curve
    x = (r - 0.4) * 4.0
    atan_val = np.arctan(x) / np.pi  # normalize to roughly [-0.5, 0.5]
    return 1.25 + 1.5 * atan_val

# Function 8: Smoothstep (polynomial)
def smoothstep_gain(r):
    r = np.clip(r, 0, 2)
    t = r / 2.0  # normalize to [0, 1]
    # Hermite interpolation: 3t² - 2t³
    smooth = t * t * (3.0 - 2.0 * t)
    return 0.5 + 1.5 * smooth

# Function 9: Smootherstep (higher order polynomial)
def smootherstep_gain(r):
    r = np.clip(r, 0, 2)
    t = r / 2.0
    # Ken Perlin's smootherstep: 6t⁵ - 15t⁴ + 10t³
    smooth = t * t * t * (t * (t * 6 - 15) + 10)
    return 0.5 + 1.5 * smooth

# Function 10: Elastic (custom piecewise with focus on dense region)
def elastic_gain(r):
    r = np.clip(r, 0, 2)
    if isinstance(r, np.ndarray):
        result = np.zeros_like(r, dtype=float)

        # Very sensitive in [0.2, 0.4] where data is dense
        mask1 = r < 0.3
        result[mask1] = 0.5 + 1.2 * (r[mask1] / 0.3)  # 0.5 -> 1.7

        mask2 = (r >= 0.3) & (r < 0.5)
        t = (r[mask2] - 0.3) / 0.2
        result[mask2] = 1.7 + 0.2 * (3*t*t - 2*t*t*t)  # 1.7 -> 1.9 (smooth)

        mask3 = r >= 0.5
        result[mask3] = 1.9 + 0.1 * np.log1p((r[mask3] - 0.5) * 2)  # saturate slowly

        return np.clip(result, 0.5, 2.0)
    else:
        if r < 0.3:
            return 0.5 + 1.2 * (r / 0.3)
        elif r < 0.5:
            t = (r - 0.3) / 0.2
            return 1.7 + 0.2 * (3*t*t - 2*t*t*t)
        else:
            return min(2.0, 1.9 + 0.1 * np.log1p((r - 0.5) * 2))

# Test ratios
test_ratios = np.linspace(0, 2, 400)

# Calculate all functions
functions = {
    'Sigmoid (current)': (sigmoid_gain, 'red'),
    'Tanh': (tanh_gain, 'blue'),
    'Exponential': (exp_gain, 'green'),
    'Logarithmic': (log_gain, 'orange'),
    'Square Root': (sqrt_gain, 'purple'),
    'Power 0.7': (power07_gain, 'brown'),
    'Arctan': (atan_gain, 'pink'),
    'Smoothstep': (smoothstep_gain, 'cyan'),
    'Smootherstep': (smootherstep_gain, 'magenta'),
    'Elastic': (elastic_gain, 'olive')
}

# Create visualization
fig = plt.figure(figsize=(18, 12))
gs = fig.add_gridspec(3, 3, hspace=0.35, wspace=0.35)

# Plot 1: All functions
ax1 = fig.add_subplot(gs[0, :])
for name, (func, color) in functions.items():
    vals = func(test_ratios)
    linewidth = 3.5 if 'current' in name else 2
    alpha = 0.9 if 'current' in name else 0.6
    ax1.plot(test_ratios, vals, color=color, linewidth=linewidth,
             label=name, alpha=alpha)

ax1.axvspan(0.2, 0.4, alpha=0.1, color='yellow', label='High density (61%)')
ax1.set_xlabel('Ratio', fontsize=13, fontweight='bold')
ax1.set_ylabel('Gain Factor', fontsize=13, fontweight='bold')
ax1.set_title('All Gain Functions Comparison', fontsize=15, fontweight='bold')
ax1.grid(True, alpha=0.3)
ax1.legend(fontsize=9, ncol=2, loc='upper left')
ax1.set_xlim(0, 2)
ax1.set_ylim(0.4, 2.1)

# Plot individual comparisons
comparisons = [
    ('S-Curves', ['Sigmoid (current)', 'Tanh', 'Arctan'], gs[1, 0]),
    ('Growth Curves', ['Exponential', 'Logarithmic', 'Square Root'], gs[1, 1]),
    ('Polynomial', ['Smoothstep', 'Smootherstep', 'Power 0.7'], gs[1, 2]),
]

for title, func_names, position in comparisons:
    ax = fig.add_subplot(position)
    for name in func_names:
        if name in functions:
            func, color = functions[name]
            vals = func(test_ratios)
            linewidth = 3 if 'current' in name else 2.5
            ax.plot(test_ratios, vals, color=color, linewidth=linewidth,
                   label=name, alpha=0.8)

    ax.axvspan(0.2, 0.4, alpha=0.15, color='yellow')
    ax.set_xlabel('Ratio', fontsize=11, fontweight='bold')
    ax.set_ylabel('Gain', fontsize=11, fontweight='bold')
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9)
    ax.set_xlim(0, 1.5)
    ax.set_ylim(0.5, 2)

# Derivatives (sensitivity)
ax_deriv = fig.add_subplot(gs[2, :2])
selected_funcs = ['Sigmoid (current)', 'Tanh', 'Square Root', 'Logarithmic', 'Elastic']
for name in selected_funcs:
    if name in functions:
        func, color = functions[name]
        vals = func(test_ratios)
        deriv = np.gradient(vals, test_ratios)
        linewidth = 3 if 'current' in name else 2
        ax_deriv.plot(test_ratios, deriv, color=color, linewidth=linewidth,
                     label=name, alpha=0.8)

ax_deriv.axvspan(0.2, 0.4, alpha=0.15, color='yellow')
ax_deriv.set_xlabel('Ratio', fontsize=12, fontweight='bold')
ax_deriv.set_ylabel('Sensitivity (dGain/dRatio)', fontsize=12, fontweight='bold')
ax_deriv.set_title('Sensitivity Comparison', fontsize=13, fontweight='bold')
ax_deriv.grid(True, alpha=0.3)
ax_deriv.legend(fontsize=10)
ax_deriv.set_xlim(0, 1.5)

# Summary table
ax_table = fig.add_subplot(gs[2, 2])
ax_table.axis('off')

table_data = []
table_data.append(['Function', 'r=0.2', 'r=0.4', 'Δ[0.2→0.4]'])
for name, (func, _) in list(functions.items())[:6]:
    g02 = func(0.2)
    g04 = func(0.4)
    delta = g04 - g02
    name_short = name.replace(' (current)', '*')
    table_data.append([name_short[:12], f'{g02:.2f}', f'{g04:.2f}', f'{delta:.2f}'])

table = ax_table.table(cellText=table_data, cellLoc='center',
                       bbox=[0, 0, 1, 1])
table.auto_set_font_size(False)
table.set_fontsize(9)
table.scale(1, 2.5)

# Style header row
for i in range(4):
    table[(0, i)].set_facecolor('#4CAF50')
    table[(0, i)].set_text_props(weight='bold', color='white')

ax_table.set_title('Key Values', fontsize=12, fontweight='bold', pad=20)

plt.savefig('/home/wuq/webrtc-local/all_gain_functions_exploration.png',
            dpi=150, bbox_inches='tight')
print("Plot saved: all_gain_functions_exploration.png")

# Print recommendations
print("\n" + "="*70)
print("FUNCTION CHARACTERISTICS")
print("="*70)

characteristics = {
    'Sigmoid': 'S-curve, very tunable (center, steepness), balanced',
    'Tanh': 'Symmetric S-curve, smoother than sigmoid',
    'Exponential': 'Aggressive growth, best for high-ratio scenarios',
    'Logarithmic': 'Very sensitive at low ratio, saturates quickly',
    'Square Root': 'Simple, more sensitive at low values, no parameters',
    'Power 0.7': 'Between linear and sqrt, moderate sensitivity',
    'Arctan': 'S-curve like sigmoid but unbounded (less common)',
    'Smoothstep': 'Polynomial S-curve, C1 continuous, simple',
    'Smootherstep': 'Higher-order polynomial, C2 continuous, very smooth',
    'Elastic': 'Custom piecewise, maximum flexibility (complex)'
}

for name, desc in characteristics.items():
    print(f"\n{name}:")
    print(f"  {desc}")

print("\n" + "="*70)
print("RECOMMENDATIONS BY USE CASE")
print("="*70)
print("\n1. Need maximum control/tuning → Sigmoid ⭐ (current)")
print("2. Want simplest implementation → Square Root")
print("3. Very aggressive in dense region → Logarithmic or Elastic")
print("4. Smoothest mathematically → Smootherstep")
print("5. Most natural S-curve → Tanh")

# Calculate sensitivity in dense region
print("\n" + "="*70)
print("SENSITIVITY IN HIGH-DENSITY REGION [0.2 → 0.4]")
print("="*70)
print("Function         | Gain Δ | Rank")
print("-" * 45)

sensitivities = {}
for name, (func, _) in functions.items():
    delta = func(0.4) - func(0.2)
    sensitivities[name] = delta

ranked = sorted(sensitivities.items(), key=lambda x: x[1], reverse=True)
for rank, (name, delta) in enumerate(ranked, 1):
    marker = " ⭐ CURRENT" if 'current' in name else ""
    print(f"{name:16s} | {delta:6.3f} | #{rank}{marker}")

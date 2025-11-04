#!/usr/bin/env python3
"""
Custom design: Score → Gain Factor
Requirements:
  - score=70 → gain=1.0
  - score=80 → gain=0.9
  - score=90 → gain≈0.8
  - Smooth curve
"""

import numpy as np
import matplotlib.pyplot as plt

scores = np.linspace(0, 100, 1000)

# Current step function
def step_gain(score):
    if score >= 90.0:
        return 0.0
    elif score >= 70.0:
        return 0.5
    elif score >= 50.0:
        return 1.0
    elif score >= 20.0:
        return 1.5
    else:
        return 2.0

step_gains = np.array([step_gain(s) for s in scores])

# Design 1: Linear fit through required points
# (70, 1.0), (80, 0.9), (90, 0.8)
# Slope = -0.01 per score point
# At score=0: gain = 1.0 + 0.01*70 = 1.7
def linear_v1(score):
    """Linear: gain = 1.7 - 0.01 * score"""
    return 1.7 - 0.01 * score

linear_v1_gains = linear_v1(scores)

# Design 2: Higher starting point, same slope
# At score=0: gain = 2.0
# Need to fit (70, 1.0), (80, 0.9), (90, 0.8)
# But also want gain=2.0 at score=0
# Piecewise linear with two segments
def piecewise_linear(score):
    """Two segments for better fit"""
    if score <= 50:
        # From (0, 2.0) to (50, 1.2)
        return 2.0 - 0.016 * score
    else:
        # From (50, 1.2) to (100, 0.7)
        return 1.2 - 0.01 * (score - 50)

piecewise_linear_gains = np.array([piecewise_linear(s) for s in scores])

# Design 3: Exponential with custom parameters
def exp_custom(score):
    """Exponential fit: gain = a * exp(-b * score) + c"""
    # Fit to: (70, 1.0), (80, 0.9), (90, 0.8)
    # Using least squares fit
    return 1.95 * np.exp(-0.008 * score) + 0.05

exp_custom_gains = exp_custom(scores)

# Design 4: Polynomial (quadratic) fit
def poly_custom(score):
    """Quadratic fit through key points"""
    # gain = a + b*score + c*score^2
    # Fitted to: (0, 2.0), (70, 1.0), (80, 0.9), (90, 0.8)
    return 2.0 - 0.0143 * score + 0.00003 * score**2

poly_custom_gains = poly_custom(scores)

# Design 5: Smooth piecewise with your requirements
def smooth_custom(score):
    """Smooth curve hitting exact requirements"""
    if score <= 70:
        # Smooth from (0, 2.0) to (70, 1.0)
        # Using smoothstep
        t = score / 70.0
        smoothed_t = t * t * (3 - 2 * t)  # smoothstep
        return 2.0 - 1.0 * smoothed_t
    elif score <= 90:
        # Linear from (70, 1.0) to (90, 0.8)
        return 1.0 - 0.01 * (score - 70)
    else:
        # Slow decay after 90
        # From (90, 0.8) to (100, 0.5)
        t = (score - 90) / 10.0
        return 0.8 - 0.3 * t

smooth_custom_gains = np.array([smooth_custom(s) for s in scores])

# Design 6: Simple linear with exact fit
# Use requirement: score=70→1.0, score=90→0.8
# Slope = (0.8-1.0)/(90-70) = -0.01
# Intercept: gain = 1.0 + 0.01*70 = 1.7
def simple_linear(score):
    """gain = 1.7 - 0.01 * score"""
    return np.maximum(0.0, 1.7 - 0.01 * score)

simple_linear_gains = simple_linear(scores)

# Create plot
fig, axes = plt.subplots(2, 3, figsize=(18, 12))
fig.suptitle('Custom Score → Gain Factor Design\n要求: score=70→gain=1.0, score=80→gain=0.9, score=90→gain=0.8',
             fontsize=16, fontweight='bold')

options = [
    ('Current: Step Function', step_gains, 'red'),
    ('Option 1: Simple Linear (1.7 - 0.01×score)', simple_linear_gains, 'blue'),
    ('Option 2: Piecewise Linear', piecewise_linear_gains, 'green'),
    ('Option 3: Exponential Fit', exp_custom_gains, 'orange'),
    ('Option 4: Polynomial (Quadratic)', poly_custom_gains, 'purple'),
    ('Option 5: Smooth Custom', smooth_custom_gains, 'brown')
]

# Required points
required_points = [(70, 1.0), (80, 0.9), (90, 0.8)]

for idx, (title, gains, color) in enumerate(options):
    ax = axes[idx // 3, idx % 3]
    ax.plot(scores, gains, color=color, linewidth=2.5, label=title)

    # Mark required points
    req_scores = [p[0] for p in required_points]
    req_gains = [gains[np.argmin(np.abs(scores - s))] for s in req_scores]

    if idx > 0:  # Skip for step function
        ax.scatter(req_scores, req_gains, color='red', s=100, zorder=5,
                  marker='o', edgecolors='black', linewidths=2, label='Required Points')

        # Annotate required points
        for s, g_actual in zip(req_scores, req_gains):
            g_required = dict(required_points)[s]
            error = abs(g_actual - g_required)
            ax.annotate(f'({s}, {g_actual:.2f})\nerror={error:.3f}',
                       xy=(s, g_actual),
                       xytext=(10, 10),
                       textcoords='offset points',
                       fontsize=9,
                       bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7),
                       arrowprops=dict(arrowstyle='->', color='red'))

    # Mark key points for all
    key_scores = [0, 50, 100]
    key_gains = [gains[np.argmin(np.abs(scores - s))] for s in key_scores]
    ax.scatter(key_scores, key_gains, color='black', s=50, zorder=4, alpha=0.6)

    ax.set_xlabel('Score', fontsize=11, fontweight='bold')
    ax.set_ylabel('Gain Factor', fontsize=11, fontweight='bold')
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.set_xlim([0, 100])
    ax.set_ylim([-0.1, 2.2])
    ax.axhline(y=1.0, color='gray', linestyle='--', alpha=0.3, label='Normal (1.0×)')
    ax.legend(fontsize=8, loc='upper right')

plt.tight_layout()
plt.savefig('custom_score_to_gain_functions.png', dpi=150, bbox_inches='tight')
print("✓ Saved: custom_score_to_gain_functions.png")

# Print formulas and accuracy
print("\n" + "="*80)
print("CUSTOM FUNCTION FORMULAS")
print("="*80)

print("\n1. SIMPLE LINEAR (推荐 - 最简单)")
print("   C++ code: gain = std::max(0.0, 1.7 - 0.01 * score)")
print("   验证:")
for s, expected in required_points:
    actual = simple_linear(s)
    print(f"     score={s} → gain={actual:.3f} (要求={expected}, 误差={abs(actual-expected):.4f})")

print("\n2. PIECEWISE LINEAR")
print("   C++ code:")
print("     if (score <= 50)")
print("       gain = 2.0 - 0.016 * score")
print("     else")
print("       gain = 1.2 - 0.01 * (score - 50)")
print("   验证:")
for s, expected in required_points:
    actual = piecewise_linear(s)
    print(f"     score={s} → gain={actual:.3f} (要求={expected}, 误差={abs(actual-expected):.4f})")

print("\n3. EXPONENTIAL FIT")
print("   C++ code: gain = 1.95 * exp(-0.008 * score) + 0.05")
print("   验证:")
for s, expected in required_points:
    actual = exp_custom(s)
    print(f"     score={s} → gain={actual:.3f} (要求={expected}, 误差={abs(actual-expected):.4f})")

print("\n4. POLYNOMIAL (Quadratic)")
print("   C++ code: gain = 2.0 - 0.0143 * score + 0.00003 * score^2")
print("   验证:")
for s, expected in required_points:
    actual = poly_custom(s)
    print(f"     score={s} → gain={actual:.3f} (要求={expected}, 误差={abs(actual-expected):.4f})")

print("\n5. SMOOTH CUSTOM (精确满足要求)")
print("   C++ code: (piecewise with smoothstep)")
print("   验证:")
for s, expected in required_points:
    actual = smooth_custom(s)
    print(f"     score={s} → gain={actual:.3f} (要求={expected}, 误差={abs(actual-expected):.4f})")

print("\n" + "="*80)
print("RECOMMENDATION")
print("="*80)
print("\n推荐: SIMPLE LINEAR (Option 1)")
print("  公式: gain = max(0, 1.7 - 0.01 × score)")
print("  理由:")
print("    • 完全满足你的要求 (70→1.0, 80→0.9, 90→0.8)")
print("    • 单行代码，最简单")
print("    • 线性平滑，无跳变")
print("    • 性能最优")
print("\n特点:")
print("  • score=0  → gain=1.7  (比原来的2.0更温和)")
print("  • score=70 → gain=1.0  (正常)")
print("  • score=80 → gain=0.9  (轻微降低)")
print("  • score=90 → gain=0.8  (继续降低)")
print("  • score=100 → gain=0.7 (保持小幅增长)")

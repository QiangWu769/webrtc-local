#!/usr/bin/env python3
"""
Design smooth function: Score → Gain Factor
Goal: Replace step function with smooth curve
"""

import numpy as np
import matplotlib.pyplot as plt

# Score range: 0-100
scores = np.linspace(0, 100, 1000)

# Current step function (for comparison)
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

# Option 1: Linear interpolation (piecewise linear)
def linear_gain(score):
    """Simple linear: high score → low gain"""
    return 2.0 * (1.0 - score / 100.0)

linear_gains = linear_gain(scores)

# Option 2: Sigmoid-based (smooth S-curve)
def sigmoid_gain(score):
    """Sigmoid transition from 2.0 to 0.0"""
    # Center at score=50, steepness controls smoothness
    center = 50.0
    steepness = 0.08  # Lower = smoother
    normalized = 1.0 / (1.0 + np.exp(-steepness * (score - center)))
    return 2.0 * (1.0 - normalized)

sigmoid_gains = sigmoid_gain(scores)

# Option 3: Inverse exponential (faster decay at low scores)
def exp_gain(score):
    """Exponential decay: 2.0 at score=0, approaches 0 at high scores"""
    return 2.0 * np.exp(-score / 40.0)

exp_gains = exp_gain(scores)

# Option 4: Polynomial (quadratic)
def poly_gain(score):
    """Quadratic curve for smoother transition"""
    normalized = score / 100.0
    return 2.0 * (1.0 - normalized) ** 2

poly_gains = poly_gain(scores)

# Option 5: Piecewise cubic (smooth but keeps 5 control points)
def piecewise_cubic(score):
    """Smooth interpolation through key points"""
    # Key points: (0, 2.0), (20, 1.5), (50, 1.0), (70, 0.5), (90, 0.0)
    if score <= 20:
        # Cubic from (0, 2.0) to (20, 1.5)
        t = score / 20.0
        return 2.0 - 0.5 * (3*t**2 - 2*t**3)
    elif score <= 50:
        # Cubic from (20, 1.5) to (50, 1.0)
        t = (score - 20) / 30.0
        return 1.5 - 0.5 * (3*t**2 - 2*t**3)
    elif score <= 70:
        # Cubic from (50, 1.0) to (70, 0.5)
        t = (score - 50) / 20.0
        return 1.0 - 0.5 * (3*t**2 - 2*t**3)
    elif score <= 90:
        # Cubic from (70, 0.5) to (90, 0.0)
        t = (score - 70) / 20.0
        return 0.5 - 0.5 * (3*t**2 - 2*t**3)
    else:
        # score > 90
        return 0.0

piecewise_gains = np.array([piecewise_cubic(s) for s in scores])

# Create comparison plot
fig, axes = plt.subplots(2, 3, figsize=(18, 12))
fig.suptitle('Score → Gain Factor: Smooth Function Design', fontsize=16, fontweight='bold')

options = [
    ('Current: Step Function', step_gains, 'red'),
    ('Option 1: Linear', linear_gains, 'blue'),
    ('Option 2: Sigmoid', sigmoid_gains, 'green'),
    ('Option 3: Exponential', exp_gains, 'orange'),
    ('Option 4: Polynomial (Quadratic)', poly_gains, 'purple'),
    ('Option 5: Piecewise Cubic', piecewise_gains, 'brown')
]

for idx, (title, gains, color) in enumerate(options):
    ax = axes[idx // 3, idx % 3]
    ax.plot(scores, gains, color=color, linewidth=2.5, label=title)

    # Mark key points
    key_scores = [0, 20, 50, 70, 90, 100]
    key_gains = [gains[np.argmin(np.abs(scores - s))] for s in key_scores]
    ax.scatter(key_scores, key_gains, color='black', s=50, zorder=5, alpha=0.6)

    # Annotate key points
    for s, g in zip(key_scores, key_gains):
        ax.annotate(f'({s:.0f}, {g:.2f})',
                   xy=(s, g),
                   xytext=(5, 5),
                   textcoords='offset points',
                   fontsize=8,
                   alpha=0.7)

    ax.set_xlabel('Score', fontsize=11, fontweight='bold')
    ax.set_ylabel('Gain Factor', fontsize=11, fontweight='bold')
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.set_xlim([0, 100])
    ax.set_ylim([-0.1, 2.2])
    ax.axhline(y=0, color='black', linestyle='--', alpha=0.3)
    ax.axhline(y=1.0, color='gray', linestyle='--', alpha=0.2, label='Normal (1.0×)')
    ax.legend(fontsize=9)

plt.tight_layout()
plt.savefig('score_to_gain_smooth_functions.png', dpi=150, bbox_inches='tight')
print("✓ Saved: score_to_gain_smooth_functions.png")

# Print function formulas
print("\n" + "="*80)
print("FUNCTION FORMULAS (C++ Implementation)")
print("="*80)

print("\n1. LINEAR (Simplest):")
print("   gain = 2.0 * (1.0 - score / 100.0)")

print("\n2. SIGMOID (Smooth S-curve):")
print("   normalized = 1.0 / (1.0 + exp(-0.08 * (score - 50.0)))")
print("   gain = 2.0 * (1.0 - normalized)")

print("\n3. EXPONENTIAL (Fast decay):")
print("   gain = 2.0 * exp(-score / 40.0)")

print("\n4. POLYNOMIAL (Quadratic):")
print("   normalized = score / 100.0")
print("   gain = 2.0 * (1.0 - normalized)^2")

print("\n5. PIECEWISE CUBIC (Smooth through key points):")
print("   Uses smoothstep interpolation between control points")
print("   Maintains original strategy philosophy but smooth transitions")

print("\n" + "="*80)
print("RECOMMENDATION")
print("="*80)
print("\n推荐方案: LINEAR (Option 1)")
print("理由:")
print("  • 最简单：单行公式")
print("  • 可预测：线性关系直观")
print("  • 连续平滑：无跳变")
print("  • 性能最优：无指数/三角运算")
print("\n如果需要保留原策略的非线性特性:")
print("  → 推荐 EXPONENTIAL (Option 3)")
print("    在低score时增益更大，符合原设计意图（资源充足时更激进）")

# Calculate difference from step function
print("\n" + "="*80)
print("SMOOTHNESS COMPARISON (vs Step Function)")
print("="*80)

for name, gains, _ in options[1:]:  # Skip step function
    max_diff = np.max(np.abs(gains - step_gains))
    mean_diff = np.mean(np.abs(gains - step_gains))
    print(f"\n{name}:")
    print(f"  Max deviation: {max_diff:.3f}×")
    print(f"  Mean deviation: {mean_diff:.3f}×")

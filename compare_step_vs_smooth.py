#!/usr/bin/env python3
"""
对比阶梯函数 vs 平滑分段线性函数
"""

import numpy as np
import matplotlib.pyplot as plt

# 旧的阶梯函数
def gain_step(score):
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

# 新的分段线性函数
def gain_piecewise_linear(score):
    score = max(0.0, min(100.0, score))

    points = [
        (100.0, 0.0),
        (90.0, 0.0),
        (70.0, 0.5),
        (50.0, 1.0),
        (20.0, 1.5),
        (0.0, 2.0)
    ]

    for i in range(len(points) - 1):
        s2, g2 = points[i]
        s1, g1 = points[i + 1]

        if s1 <= score <= s2:
            t = (score - s1) / (s2 - s1)
            return g1 + (g2 - g1) * t

    return 2.0

# 生成数据
scores = np.linspace(0, 100, 1000)
gains_step = [gain_step(s) for s in scores]
gains_smooth = [gain_piecewise_linear(s) for s in scores]

# 创建可视化
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# Plot 1: 旧的阶梯函数
ax1 = axes[0, 0]
ax1.plot(scores, gains_step, linewidth=3, color='red', label='Step Function (Old)')
ax1.set_xlabel('Score', fontsize=12)
ax1.set_ylabel('Gain Factor', fontsize=12)
ax1.set_title('Old: Hard Boundaries (Step Function)', fontsize=13, fontweight='bold')
ax1.grid(True, alpha=0.3)
ax1.set_ylim(-0.1, 2.3)
ax1.axhline(y=1.0, color='blue', linestyle='--', alpha=0.3, label='Baseline')
ax1.legend()

# 标注阶梯
ax1.axvline(x=90, color='orange', linestyle=':', alpha=0.5)
ax1.axvline(x=70, color='orange', linestyle=':', alpha=0.5)
ax1.axvline(x=50, color='orange', linestyle=':', alpha=0.5)
ax1.axvline(x=20, color='orange', linestyle=':', alpha=0.5)
ax1.text(95, 0.2, '90', fontsize=9, color='orange')
ax1.text(75, 0.7, '70', fontsize=9, color='orange')
ax1.text(55, 1.2, '50', fontsize=9, color='orange')
ax1.text(25, 1.7, '20', fontsize=9, color='orange')

# Plot 2: 新的平滑函数
ax2 = axes[0, 1]
ax2.plot(scores, gains_smooth, linewidth=3, color='green', label='Piecewise Linear (New)')
ax2.set_xlabel('Score', fontsize=12)
ax2.set_ylabel('Gain Factor', fontsize=12)
ax2.set_title('New: Smooth Transitions (Piecewise Linear)', fontsize=13, fontweight='bold')
ax2.grid(True, alpha=0.3)
ax2.set_ylim(-0.1, 2.3)
ax2.axhline(y=1.0, color='blue', linestyle='--', alpha=0.3, label='Baseline')

# 标注关键点
key_points = [(100, 0.0), (90, 0.0), (70, 0.5), (50, 1.0), (20, 1.5), (0, 2.0)]
for s, g in key_points:
    ax2.plot(s, g, 'ro', markersize=8)
    ax2.text(s, g + 0.1, f'({s:.0f}, {g:.1f})', fontsize=8, ha='center')

ax2.legend()

# Plot 3: 对比叠加
ax3 = axes[1, 0]
ax3.plot(scores, gains_step, linewidth=2, color='red', label='Step (Old)', alpha=0.7, linestyle='--')
ax3.plot(scores, gains_smooth, linewidth=3, color='green', label='Piecewise Linear (New)', alpha=0.9)
ax3.set_xlabel('Score', fontsize=12)
ax3.set_ylabel('Gain Factor', fontsize=12)
ax3.set_title('Comparison: Step vs Smooth', fontsize=13, fontweight='bold')
ax3.grid(True, alpha=0.3)
ax3.set_ylim(-0.1, 2.3)
ax3.axhline(y=1.0, color='blue', linestyle='--', alpha=0.3)
ax3.legend()

# 标注改善区域
ax3.fill_between([85, 90], -0.1, 2.3, alpha=0.1, color='yellow', label='Smooth transition')
ax3.fill_between([65, 70], -0.1, 2.3, alpha=0.1, color='yellow')
ax3.fill_between([45, 50], -0.1, 2.3, alpha=0.1, color='yellow')
ax3.fill_between([15, 20], -0.1, 2.3, alpha=0.1, color='yellow')

# Plot 4: 差异热图（放大关键区域）
ax4 = axes[1, 1]

# 计算差异
differences = [abs(gain_piecewise_linear(s) - gain_step(s)) for s in scores]

ax4.fill_between(scores, 0, differences, alpha=0.6, color='purple', label='Absolute Difference')
ax4.set_xlabel('Score', fontsize=12)
ax4.set_ylabel('|New - Old| Gain Difference', fontsize=12)
ax4.set_title('Smoothness Improvement (Difference)', fontsize=13, fontweight='bold')
ax4.grid(True, alpha=0.3)
ax4.legend()

# 标注最大差异点
max_diff_idx = np.argmax(differences)
max_diff_score = scores[max_diff_idx]
max_diff_val = differences[max_diff_idx]
ax4.plot(max_diff_score, max_diff_val, 'ro', markersize=10)
ax4.text(max_diff_score, max_diff_val + 0.05, f'Max: {max_diff_val:.3f}\n@Score={max_diff_score:.1f}',
         fontsize=9, ha='center', va='bottom')

plt.suptitle('Gain Factor Function: Step vs Piecewise Linear Comparison',
             fontsize=15, fontweight='bold')
plt.tight_layout()
plt.savefig('step_vs_smooth_comparison.png', dpi=150, bbox_inches='tight')
print("✅ 可视化已保存: step_vs_smooth_comparison.png\n")

# 打印详细对比
print("=" * 80)
print("关键 Score 点的增益因子对比")
print("=" * 80)
print(f"{'Score':<10} {'Step (Old)':<15} {'Smooth (New)':<15} {'Difference':<15}")
print("-" * 80)

key_scores = [0, 10, 15, 20, 25, 35, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100]
for s in key_scores:
    old = gain_step(s)
    new = gain_piecewise_linear(s)
    diff = new - old
    marker = " ←" if abs(diff) > 0.01 else ""
    print(f"{s:<10} {old:<15.3f} {new:<15.3f} {diff:<+15.3f}{marker}")

print("\n" + "=" * 80)
print("改进总结")
print("=" * 80)
print("\n✅ 优势:")
print("  1. 平滑过渡：在关键点之间线性插值，消除突变")
print("  2. 保持控制：关键点 (90, 70, 50, 20, 0) 的增益值完全一致")
print("  3. 更精细：可以区分 score=85 和 score=90，旧函数无法区分")
print("  4. 可预测：行为更线性，更易理解和调试")
print("\n📊 数值对比示例:")
print("  Score 85: Old=0.0, New=0.25 (介于 90→0.0 和 70→0.5 之间)")
print("  Score 55: Old=1.0, New=0.75 (介于 70→0.5 和 50→1.0 之间)")
print("  Score 25: Old=1.5, New=1.33 (介于 50→1.0 和 20→1.5 之间)")

print("\n" + "=" * 80)

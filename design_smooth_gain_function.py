#!/usr/bin/env python3
"""
设计平滑的增益因子函数

对比几种方案：
1. 当前阶梯函数（硬分区间）
2. 线性插值
3. Sigmoid 平滑
4. 分段线性（piecewise linear）
"""

import numpy as np
import matplotlib.pyplot as plt

# 当前阶梯函数
def gain_step(score):
    """当前的硬分区间函数"""
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

# 方案1: 线性插值
def gain_linear(score):
    """线性插值：从 score=100→gain=0 到 score=0→gain=2"""
    # 简单线性映射
    return 2.0 * (1.0 - score / 100.0)

# 方案2: 反向 Sigmoid（平滑过渡）
def gain_sigmoid(score):
    """使用反向 sigmoid 实现平滑过渡"""
    # 中心点在 score=50，增益=1.0
    # 陡度控制过渡速度
    center = 50.0
    steepness = 0.08  # 控制曲线陡度

    # Sigmoid: gain = 2 / (1 + exp(steepness * (score - center)))
    gain = 2.0 / (1.0 + np.exp(steepness * (score - center)))
    return gain

# 方案3: 分段线性（保持关键点，线性插值）
def gain_piecewise_linear(score):
    """分段线性：在关键点之间线性插值"""
    # 关键点: (score, gain)
    points = [
        (100, 0.0),
        (90, 0.0),
        (70, 0.5),
        (50, 1.0),
        (20, 1.5),
        (0, 2.0)
    ]

    # 线性插值
    for i in range(len(points) - 1):
        s1, g1 = points[i]
        s2, g2 = points[i + 1]

        if s2 <= score <= s1:
            # 线性插值公式
            gain = g1 + (g2 - g1) * (score - s1) / (s2 - s1)
            return gain

    return 2.0  # 默认

# 方案4: 双曲线（更陡峭的过渡）
def gain_hyperbolic(score):
    """双曲线函数：更陡峭的过渡"""
    # 归一化 score 到 [0, 1]
    s_norm = score / 100.0

    # 使用双曲函数
    # gain = 2 * (1 - s^2)，在高分时快速下降
    gain = 2.0 * (1.0 - s_norm ** 2)
    return max(0.0, gain)

# 方案5: 分段 Sigmoid（在关键区域使用 sigmoid）
def gain_piecewise_sigmoid(score):
    """分段 sigmoid：在过渡区使用 sigmoid，其他区域线性"""
    if score >= 90:
        # 高分区：快速降到0
        # 90-100: 0.5 → 0
        t = (score - 90) / 10.0  # 归一化到 [0, 1]
        return 0.5 * (1.0 - t)
    elif score >= 70:
        # 中高分区：平滑从 0.5 到 0.8
        # 使用 sigmoid 平滑过渡
        center = 80
        steepness = 0.3
        return 0.5 * (1.0 / (1.0 + np.exp(-steepness * (score - center))))
    elif score >= 50:
        # 中分区：线性从 1.0 到 0.5
        t = (score - 50) / 20.0
        return 1.0 - 0.5 * t
    elif score >= 20:
        # 中低分区：线性从 1.5 到 1.0
        t = (score - 20) / 30.0
        return 1.5 - 0.5 * t
    else:
        # 低分区：线性从 2.0 到 1.5
        t = score / 20.0
        return 2.0 - 0.5 * t

# 生成数据
scores = np.linspace(0, 100, 1000)

gains_step = [gain_step(s) for s in scores]
gains_linear = [gain_linear(s) for s in scores]
gains_sigmoid = [gain_sigmoid(s) for s in scores]
gains_piecewise = [gain_piecewise_linear(s) for s in scores]
gains_hyperbolic = [gain_hyperbolic(s) for s in scores]
gains_piecewise_sigmoid = [gain_piecewise_sigmoid(s) for s in scores]

# 可视化对比
fig, axes = plt.subplots(2, 3, figsize=(16, 10))

# Plot 1: 当前阶梯函数
ax1 = axes[0, 0]
ax1.plot(scores, gains_step, linewidth=3, color='red', label='Step Function')
ax1.set_xlabel('Score', fontsize=11)
ax1.set_ylabel('Gain Factor', fontsize=11)
ax1.set_title('1. Current (Hard Boundaries)', fontsize=12, fontweight='bold')
ax1.grid(True, alpha=0.3)
ax1.set_ylim(-0.1, 2.3)
ax1.axhline(y=0, color='black', linestyle='--', alpha=0.3)
ax1.axhline(y=1.0, color='blue', linestyle='--', alpha=0.3, label='Normal (1.0)')
ax1.legend()

# Plot 2: 线性插值
ax2 = axes[0, 1]
ax2.plot(scores, gains_linear, linewidth=3, color='blue', label='Linear')
ax2.set_xlabel('Score', fontsize=11)
ax2.set_ylabel('Gain Factor', fontsize=11)
ax2.set_title('2. Linear Interpolation', fontsize=12, fontweight='bold')
ax2.grid(True, alpha=0.3)
ax2.set_ylim(-0.1, 2.3)
ax2.axhline(y=1.0, color='blue', linestyle='--', alpha=0.3)
ax2.legend()

# Plot 3: Sigmoid
ax3 = axes[0, 2]
ax3.plot(scores, gains_sigmoid, linewidth=3, color='green', label='Sigmoid')
ax3.set_xlabel('Score', fontsize=11)
ax3.set_ylabel('Gain Factor', fontsize=11)
ax3.set_title('3. Inverse Sigmoid', fontsize=12, fontweight='bold')
ax3.grid(True, alpha=0.3)
ax3.set_ylim(-0.1, 2.3)
ax3.axhline(y=1.0, color='blue', linestyle='--', alpha=0.3)
ax3.legend()

# Plot 4: 分段线性
ax4 = axes[1, 0]
ax4.plot(scores, gains_piecewise, linewidth=3, color='orange', label='Piecewise Linear')
ax4.set_xlabel('Score', fontsize=11)
ax4.set_ylabel('Gain Factor', fontsize=11)
ax4.set_title('4. Piecewise Linear (Recommended)', fontsize=12, fontweight='bold')
ax4.grid(True, alpha=0.3)
ax4.set_ylim(-0.1, 2.3)
ax4.axhline(y=1.0, color='blue', linestyle='--', alpha=0.3)
# 标注关键点
key_points = [(100, 0.0), (90, 0.0), (70, 0.5), (50, 1.0), (20, 1.5), (0, 2.0)]
for s, g in key_points:
    ax4.plot(s, g, 'ro', markersize=8)
ax4.legend()

# Plot 5: 双曲线
ax5 = axes[1, 1]
ax5.plot(scores, gains_hyperbolic, linewidth=3, color='purple', label='Hyperbolic')
ax5.set_xlabel('Score', fontsize=11)
ax5.set_ylabel('Gain Factor', fontsize=11)
ax5.set_title('5. Hyperbolic Function', fontsize=12, fontweight='bold')
ax5.grid(True, alpha=0.3)
ax5.set_ylim(-0.1, 2.3)
ax5.axhline(y=1.0, color='blue', linestyle='--', alpha=0.3)
ax5.legend()

# Plot 6: 对比所有方案
ax6 = axes[1, 2]
ax6.plot(scores, gains_step, linewidth=2, color='red', label='1. Step', alpha=0.7)
ax6.plot(scores, gains_linear, linewidth=2, color='blue', label='2. Linear', alpha=0.7)
ax6.plot(scores, gains_sigmoid, linewidth=2, color='green', label='3. Sigmoid', alpha=0.7)
ax6.plot(scores, gains_piecewise, linewidth=3, color='orange', label='4. Piecewise', alpha=0.9)
ax6.plot(scores, gains_hyperbolic, linewidth=2, color='purple', label='5. Hyperbolic', alpha=0.7)
ax6.set_xlabel('Score', fontsize=11)
ax6.set_ylabel('Gain Factor', fontsize=11)
ax6.set_title('6. All Methods Comparison', fontsize=12, fontweight='bold')
ax6.grid(True, alpha=0.3)
ax6.set_ylim(-0.1, 2.3)
ax6.axhline(y=1.0, color='black', linestyle='--', alpha=0.3)
ax6.legend(fontsize=9)

plt.suptitle('Smooth Gain Factor Function Design', fontsize=16, fontweight='bold')
plt.tight_layout()
plt.savefig('smooth_gain_function_comparison.png', dpi=150, bbox_inches='tight')
print("✅ 可视化已保存: smooth_gain_function_comparison.png\n")

# 打印各方案在关键点的值
print("=" * 80)
print("各方案在关键 Score 点的增益因子对比")
print("=" * 80)
print(f"{'Score':<10} {'Step':<10} {'Linear':<10} {'Sigmoid':<10} {'Piecewise':<10} {'Hyperbolic':<10}")
print("-" * 80)

key_scores = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100]
for s in key_scores:
    print(f"{s:<10} {gain_step(s):<10.3f} {gain_linear(s):<10.3f} {gain_sigmoid(s):<10.3f} "
          f"{gain_piecewise_linear(s):<10.3f} {gain_hyperbolic(s):<10.3f}")

print("\n" + "=" * 80)
print("推荐方案分析")
print("=" * 80)

print("\n方案4: Piecewise Linear (分段线性) - 推荐")
print("优点:")
print("  ✓ 保持关键点的控制（90→0, 70→0.5, 50→1.0, 20→1.5, 0→2.0）")
print("  ✓ 区间内平滑过渡，无突变")
print("  ✓ 实现简单，计算高效")
print("  ✓ 可解释性强")
print("\n缺点:")
print("  - 在关键点处斜率会有微小变化")
print("\n实现难度: ⭐⭐ (简单)")

print("\n方案3: Inverse Sigmoid - 备选")
print("优点:")
print("  ✓ 完全平滑，无任何折点")
print("  ✓ 数学上优雅")
print("\n缺点:")
print("  - 难以精确控制关键点的值")
print("  - 需要调整参数才能匹配期望的行为")
print("\n实现难度: ⭐⭐⭐ (中等)")

print("\n方案2: Linear - 最简单")
print("优点:")
print("  ✓ 实现极简（一行代码）")
print("  ✓ 完全平滑")
print("\n缺点:")
print("  - 无法在特定区域（如90-100）快速下降")
print("  - 缺乏对关键点的精确控制")
print("\n实现难度: ⭐ (非常简单)")

print("\n" + "=" * 80)

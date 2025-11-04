#!/usr/bin/env python3
"""
直接从 ratio 映射到 gain factor，跳过 score 这个中间步骤
"""

import numpy as np
import matplotlib.pyplot as plt

# 当前两步法
def current_two_step(ratio):
    """当前：ratio → score → gain（两步）"""
    # Step 1: ratio → score (inverse sigmoid)
    center = 0.5
    steepness = 15.0
    sigmoid_value = 1.0 / (1.0 + np.exp(-steepness * (ratio - center)))
    score = (1.0 - sigmoid_value) * 100.0

    # Step 2: score → gain (linear)
    gain = 2.0 * (1.0 - score / 100.0)
    return score, gain

# 方案1: 直接映射（合并两步为一步）
def ratio_to_gain_direct(ratio):
    """直接：ratio → gain（一步）

    合并公式：
    score = [1 - sigmoid(ratio)] * 100
    gain = 2.0 * (1.0 - score / 100)
         = 2.0 * (1.0 - [1 - sigmoid(ratio)])
         = 2.0 * sigmoid(ratio)
    """
    center = 0.5
    steepness = 15.0
    sigmoid_value = 1.0 / (1.0 + np.exp(-steepness * (ratio - center)))
    return 2.0 * sigmoid_value

# 方案2: 更简单的直接映射（不用 sigmoid）
def ratio_to_gain_simple(ratio):
    """简单线性：ratio 越大，gain 越小"""
    # ratio = 0.0 → gain = 2.0
    # ratio = 0.5 → gain = 1.0
    # ratio = 1.0 → gain = 0.0
    return 2.0 * (1.0 - ratio)

# 方案3: 双曲正切直接映射
def ratio_to_gain_tanh(ratio):
    """使用 tanh 直接映射"""
    # 中心在 0.5
    # ratio = 0.0 → gain ≈ 2.0
    # ratio = 0.5 → gain ≈ 1.0
    # ratio = 1.0 → gain ≈ 0.0
    return 1.0 + np.tanh(2.0 * (0.5 - ratio))

# 方案4: 指数映射
def ratio_to_gain_exp(ratio):
    """指数衰减"""
    # ratio 越大，gain 指数下降
    k = 3.0  # 控制下降速度
    return 2.0 * np.exp(-k * ratio)

# 生成数据
ratios = np.linspace(0, 1, 1000)

# 当前两步法
scores_current = []
gains_current = []
for r in ratios:
    s, g = current_two_step(r)
    scores_current.append(s)
    gains_current.append(g)

gains_direct = [ratio_to_gain_direct(r) for r in ratios]
gains_simple = [ratio_to_gain_simple(r) for r in ratios]
gains_tanh = [ratio_to_gain_tanh(r) for r in ratios]
gains_exp = [ratio_to_gain_exp(r) for r in ratios]

# 可视化
fig, axes = plt.subplots(2, 3, figsize=(16, 10))

# Plot 1: 当前两步法（ratio → score）
ax1 = axes[0, 0]
ax1.plot(ratios, scores_current, linewidth=3, color='blue', label='Inverse Sigmoid')
ax1.set_xlabel('Cellular Ratio', fontsize=11)
ax1.set_ylabel('Score', fontsize=11)
ax1.set_title('Current Step 1: Ratio → Score', fontsize=12, fontweight='bold')
ax1.grid(True, alpha=0.3)
ax1.axvline(x=0.5, color='red', linestyle='--', alpha=0.3, label='Center (0.5)')
ax1.axhline(y=50, color='orange', linestyle='--', alpha=0.3)
ax1.legend()

# Plot 2: 当前两步法（score → gain）
ax2 = axes[0, 1]
ax2.plot(scores_current, gains_current, linewidth=3, color='green', label='Linear')
ax2.set_xlabel('Score', fontsize=11)
ax2.set_ylabel('Gain Factor', fontsize=11)
ax2.set_title('Current Step 2: Score → Gain', fontsize=12, fontweight='bold')
ax2.grid(True, alpha=0.3)
ax2.axhline(y=1.0, color='blue', linestyle='--', alpha=0.3, label='Baseline')
ax2.legend()

# Plot 3: 当前两步法（ratio → gain，整体）
ax3 = axes[0, 2]
ax3.plot(ratios, gains_current, linewidth=3, color='purple', label='Current (2-step)')
ax3.set_xlabel('Cellular Ratio', fontsize=11)
ax3.set_ylabel('Gain Factor', fontsize=11)
ax3.set_title('Current Result: Ratio → Gain', fontsize=12, fontweight='bold')
ax3.grid(True, alpha=0.3)
ax3.axhline(y=1.0, color='blue', linestyle='--', alpha=0.3)
ax3.axvline(x=0.5, color='red', linestyle='--', alpha=0.3, label='Center (0.5)')
ax3.legend()

# Plot 4: 方案1 - 直接映射（合并公式）
ax4 = axes[1, 0]
ax4.plot(ratios, gains_direct, linewidth=3, color='red', label='Direct (Merged)')
ax4.plot(ratios, gains_current, linewidth=2, color='purple', label='Current', alpha=0.5, linestyle='--')
ax4.set_xlabel('Cellular Ratio', fontsize=11)
ax4.set_ylabel('Gain Factor', fontsize=11)
ax4.set_title('Option 1: Direct Sigmoid (Same as Current)', fontsize=12, fontweight='bold')
ax4.grid(True, alpha=0.3)
ax4.axhline(y=1.0, color='blue', linestyle='--', alpha=0.3)
ax4.legend()

# Plot 5: 方案2 - 简单线性
ax5 = axes[1, 1]
ax5.plot(ratios, gains_simple, linewidth=3, color='orange', label='Simple Linear')
ax5.plot(ratios, gains_current, linewidth=2, color='purple', label='Current', alpha=0.5, linestyle='--')
ax5.set_xlabel('Cellular Ratio', fontsize=11)
ax5.set_ylabel('Gain Factor', fontsize=11)
ax5.set_title('Option 2: Simple Linear (Recommended)', fontsize=12, fontweight='bold')
ax5.grid(True, alpha=0.3)
ax5.axhline(y=1.0, color='blue', linestyle='--', alpha=0.3)
ax5.legend()

# Plot 6: 所有方案对比
ax6 = axes[1, 2]
ax6.plot(ratios, gains_current, linewidth=3, color='purple', label='Current (2-step)', alpha=0.9)
ax6.plot(ratios, gains_direct, linewidth=2, color='red', label='Direct Sigmoid', alpha=0.7, linestyle='--')
ax6.plot(ratios, gains_simple, linewidth=3, color='orange', label='Simple Linear', alpha=0.9)
ax6.plot(ratios, gains_tanh, linewidth=2, color='green', label='Tanh', alpha=0.6)
ax6.set_xlabel('Cellular Ratio', fontsize=11)
ax6.set_ylabel('Gain Factor', fontsize=11)
ax6.set_title('All Options Comparison', fontsize=12, fontweight='bold')
ax6.grid(True, alpha=0.3)
ax6.axhline(y=1.0, color='black', linestyle='--', alpha=0.3)
ax6.legend(fontsize=9)

# 标注关键点
key_ratios = [0.0, 0.2, 0.5, 0.8, 1.0]
for r in key_ratios:
    gain_current = ratio_to_gain_direct(r)
    gain_simple = ratio_to_gain_simple(r)
    ax6.plot(r, gain_current, 'o', color='purple', markersize=6)
    ax6.plot(r, gain_simple, 's', color='orange', markersize=6)

plt.suptitle('Direct Ratio → Gain Mapping (Single Function)', fontsize=16, fontweight='bold')
plt.tight_layout()
plt.savefig('ratio_to_gain_direct.png', dpi=150, bbox_inches='tight')
print("✅ 可视化已保存: ratio_to_gain_direct.png\n")

# 打印对比
print("=" * 90)
print("Ratio → Gain 映射对比")
print("=" * 90)
print(f"{'Ratio':<10} {'Current':<15} {'Direct':<15} {'Simple':<15} {'Tanh':<15}")
print("-" * 90)

key_ratios = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
for r in key_ratios:
    _, g_current = current_two_step(r)
    g_direct = ratio_to_gain_direct(r)
    g_simple = ratio_to_gain_simple(r)
    g_tanh = ratio_to_gain_tanh(r)
    print(f"{r:<10.1f} {g_current:<15.3f} {g_direct:<15.3f} {g_simple:<15.3f} {g_tanh:<15.3f}")

print("\n" + "=" * 90)
print("推荐方案")
print("=" * 90)

print("\n🥇 推荐: Simple Linear (gain = 2.0 * (1.0 - ratio))")
print("  优点:")
print("    ✓ 极简：一行代码")
print("    ✓ 完全平滑")
print("    ✓ 无需 sigmoid，无需 score 中间步骤")
print("    ✓ 直观：ratio 增加，gain 线性减少")
print("  实现:")
print("    return 2.0 * (1.0 - ratio);")

print("\n🥈 备选: Direct Sigmoid (gain = 2.0 * sigmoid(ratio))")
print("  优点:")
print("    ✓ 与当前逻辑等价（合并两步为一步）")
print("    ✓ 保持 sigmoid 的非线性特性")
print("  缺点:")
print("    - 仍需 sigmoid 计算")
print("    - 相比 Simple Linear 更复杂")
print("  实现:")
print("    sigmoid = 1.0 / (1.0 + exp(-15.0 * (ratio - 0.5)));")
print("    return 2.0 * sigmoid;")

print("\n📊 当前方案: Two-Step (ratio → score → gain)")
print("  问题:")
print("    ✗ 需要两步计算")
print("    ✗ 引入中间变量 score")
print("    ✗ 代码冗长")

print("\n" + "=" * 90)
print("结论：推荐使用 Simple Linear 直接映射")
print("=" * 90)

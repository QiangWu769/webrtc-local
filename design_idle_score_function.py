#!/usr/bin/env python3
"""
Design Idle Score function (forward sigmoid)
Ratio越高 → 空闲分数越高 → 资源充足 → 增益因子高
"""

import numpy as np
import matplotlib.pyplot as plt

ratios = np.linspace(0, 1.5, 1000)

# Current: Inverse Sigmoid (ratio低 → score高)
def inverse_sigmoid_score(ratio):
    center = 0.5
    steepness = 15.0
    sigmoid_value = 1.0 / (1.0 + np.exp(-steepness * (ratio - center)))
    return (1.0 - sigmoid_value) * 100.0

# New: Forward Sigmoid (ratio高 → idle score高)
def forward_sigmoid_score(ratio):
    center = 0.5
    steepness = 15.0
    sigmoid_value = 1.0 / (1.0 + np.exp(-steepness * (ratio - center)))
    return sigmoid_value * 100.0  # 直接用sigmoid，不取反

# Calculate scores
inverse_scores = inverse_sigmoid_score(ratios)
forward_scores = forward_sigmoid_score(ratios)

# Create comparison plot
fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle('空闲分数（Idle Score）vs 原分数（Inverse Score）对比', fontsize=16, fontweight='bold')

# Plot 1: Original inverse sigmoid
ax1 = axes[0, 0]
ax1.plot(ratios, inverse_scores, color='red', linewidth=3, label='Original: Inverse Sigmoid')
ax1.set_xlabel('Ratio', fontsize=12, fontweight='bold')
ax1.set_ylabel('Score', fontsize=12, fontweight='bold')
ax1.set_title('原方案: Inverse Sigmoid\n(ratio低 → score高 → 反直觉)', fontsize=13, fontweight='bold')
ax1.grid(True, alpha=0.3)
ax1.axhline(y=50, color='gray', linestyle='--', alpha=0.5)
ax1.axvline(x=0.5, color='gray', linestyle='--', alpha=0.5)

# Mark key points
key_ratios = [0.1, 0.3, 0.5, 0.7, 0.9]
for r in key_ratios:
    s = inverse_sigmoid_score(np.array([r]))[0]
    ax1.scatter(r, s, s=80, c='red', edgecolors='black', linewidths=2, zorder=5)
    ax1.annotate(f'ratio={r:.1f}\nscore={s:.1f}',
                xy=(r, s), xytext=(10, 10), textcoords='offset points',
                fontsize=9, bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.7))

ax1.legend(fontsize=11)
ax1.set_xlim([0, 1.5])

# Plot 2: New forward sigmoid (Idle Score)
ax2 = axes[0, 1]
ax2.plot(ratios, forward_scores, color='green', linewidth=3, label='New: Forward Sigmoid (Idle Score)')
ax2.set_xlabel('Ratio', fontsize=12, fontweight='bold')
ax2.set_ylabel('Idle Score (空闲分数)', fontsize=12, fontweight='bold')
ax2.set_title('新方案: Forward Sigmoid\n(ratio高 → idle score高 → 直觉)', fontsize=13, fontweight='bold')
ax2.grid(True, alpha=0.3)
ax2.axhline(y=50, color='gray', linestyle='--', alpha=0.5)
ax2.axvline(x=0.5, color='gray', linestyle='--', alpha=0.5)

# Mark key points
for r in key_ratios:
    s = forward_sigmoid_score(np.array([r]))[0]
    ax2.scatter(r, s, s=80, c='green', edgecolors='black', linewidths=2, zorder=5)
    ax2.annotate(f'ratio={r:.1f}\nidle={s:.1f}',
                xy=(r, s), xytext=(10, -20), textcoords='offset points',
                fontsize=9, bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.7))

ax2.legend(fontsize=11)
ax2.set_xlim([0, 1.5])

# Plot 3: Comparison
ax3 = axes[1, 0]
ax3.plot(ratios, inverse_scores, color='red', linewidth=2.5, linestyle='--',
         alpha=0.7, label='Original Score (inverse)')
ax3.plot(ratios, forward_scores, color='green', linewidth=2.5,
         label='Idle Score (forward)')
ax3.set_xlabel('Ratio', fontsize=12, fontweight='bold')
ax3.set_ylabel('Score', fontsize=12, fontweight='bold')
ax3.set_title('对比：两种计分方式', fontsize=13, fontweight='bold')
ax3.grid(True, alpha=0.3)
ax3.legend(fontsize=11)
ax3.axhline(y=50, color='gray', linestyle='--', alpha=0.5)
ax3.axvline(x=0.5, color='gray', linestyle='--', alpha=0.5)
ax3.set_xlim([0, 1.5])

# Plot 4: Table of values
ax4 = axes[1, 1]
ax4.axis('off')

# Create table
table_data = []
test_ratios = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
table_data.append(['Ratio', 'Inverse\nScore', 'Idle\nScore', 'Interpretation'])

for r in test_ratios:
    inv_s = inverse_sigmoid_score(np.array([r]))[0]
    fwd_s = forward_sigmoid_score(np.array([r]))[0]

    if r < 0.3:
        interp = "严重不足"
    elif r < 0.5:
        interp = "资源紧张"
    elif r < 0.7:
        interp = "中等"
    elif r < 0.9:
        interp = "充足"
    else:
        interp = "非常充足"

    table_data.append([f'{r:.1f}', f'{inv_s:.1f}', f'{fwd_s:.1f}', interp])

table = ax4.table(cellText=table_data, cellLoc='center', loc='center',
                 bbox=[0, 0, 1, 1])
table.auto_set_font_size(False)
table.set_fontsize(10)
table.scale(1, 2)

# Color header
for i in range(4):
    table[(0, i)].set_facecolor('#4CAF50')
    table[(0, i)].set_text_props(weight='bold', color='white')

# Color rows
for i in range(1, len(table_data)):
    if i % 2 == 0:
        for j in range(4):
            table[(i, j)].set_facecolor('#f0f0f0')

ax4.set_title('数值对比表', fontsize=13, fontweight='bold', pad=20)

plt.tight_layout()
plt.savefig('idle_score_comparison.png', dpi=150, bbox_inches='tight')
print("✓ Saved: idle_score_comparison.png")

# Print formulas
print("\n" + "="*80)
print("FORMULA COMPARISON")
print("="*80)

print("\n原方案 (Inverse Sigmoid):")
print("  score = [1 - sigmoid(ratio, center=0.5, steepness=15)] × 100")
print("  逻辑: ratio越低 → score越高 (反直觉)")

print("\n新方案 (Forward Sigmoid - Idle Score):")
print("  idle_score = sigmoid(ratio, center=0.5, steepness=15) × 100")
print("  逻辑: ratio越高 → idle_score越高 (直觉)")

print("\nC++ Implementation (新方案):")
print("-" * 80)
print("""
double AimdRateControl::CalculateIdleScore() const {
  const double center = 0.5;
  const double steepness = 15.0;

  // Forward sigmoid: ratio高 → score高
  double sigmoid_value = 1.0 / (1.0 + std::exp(-steepness * (smoothed_cellular_ratio_ - center)));
  double idle_score = sigmoid_value * 100.0;

  return idle_score;
}
""")

print("\n" + "="*80)
print("GAIN FACTOR MAPPING (需要调整)")
print("="*80)

print("\n原方案 (Inverse Score → Gain):")
print("  Score >= 90  → Gain = 0.0  (严重不足，停止)")
print("  Score >= 70  → Gain = 0.5  (紧张，保守)")
print("  Score >= 50  → Gain = 1.0  (中等，正常)")
print("  Score >= 20  → Gain = 1.5  (一般，激进)")
print("  Score < 20   → Gain = 2.0  (充足，非常激进)")

print("\n新方案 (Idle Score → Gain) - 需要反向:")
print("  Idle Score <= 10  → Gain = 0.0  (严重不足，停止)")
print("  Idle Score <= 30  → Gain = 0.5  (紧张，保守)")
print("  Idle Score <= 50  → Gain = 1.0  (中等，正常)")
print("  Idle Score <= 80  → Gain = 1.5  (一般，激进)")
print("  Idle Score > 80   → Gain = 2.0  (充足，非常激进)")

print("\n" + "="*80)
print("KEY BENEFITS OF IDLE SCORE")
print("="*80)

print("""
优势:
  1. 直觉性: ratio高 → idle score高 → 含义一致
  2. 命名清晰: "空闲分数"直接表达资源充足程度
  3. 逻辑简单: 不需要反向思考
  4. 可读性: 日志更容易理解

示例日志对比:
  原方案: Score: 95.3 → 难理解（高分=资源紧张？）
  新方案: IdleScore: 4.7 → 易理解（低分=资源紧张✓）
""")

# Numerical comparison
print("\n" + "="*80)
print("NUMERICAL COMPARISON")
print("="*80)
print(f"{'Ratio':<10} {'Inverse Score':<20} {'Idle Score':<20} {'Status':<20}")
print("-" * 80)

for r in test_ratios:
    inv_s = inverse_sigmoid_score(np.array([r]))[0]
    fwd_s = forward_sigmoid_score(np.array([r]))[0]

    if r < 0.3:
        status = "严重不足"
    elif r < 0.5:
        status = "资源紧张"
    elif r < 0.7:
        status = "中等"
    elif r < 0.9:
        status = "充足"
    else:
        status = "非常充足"

    print(f"{r:<10.1f} {inv_s:<20.2f} {fwd_s:<20.2f} {status:<20}")

print("\n注意: Inverse Score + Idle Score = 100 (完全镜像关系)")

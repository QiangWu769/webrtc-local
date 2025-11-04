#!/usr/bin/env python3
"""
详细对比增益因子策略 vs 当前实际带宽增长
"""

import re
import matplotlib.pyplot as plt
import numpy as np

log_file = "/home/wuq/webrtc-local/webrtc_config_results/sender_local.log"

# 读取日志
with open(log_file, 'r') as f:
    lines = f.readlines()

# 解析数据
data = []
current_gain_info = None

for line in lines:
    # 解析 GainFactor 日志
    if "[AIMD-GainFactor]" in line:
        match = re.search(r'Score: ([\d.e+-]+), Gain: ([\d.]+), Base rate: ([\d.]+) bps/s, Would adjust to: ([\d.]+) bps/s', line)
        if match:
            current_gain_info = {
                'score': float(match.group(1)),
                'gain': float(match.group(2)),
                'base_rate': float(match.group(3)),
                'adjusted_rate': float(match.group(4))
            }

    # 解析 BWE-DECISION 日志（紧跟在 GainFactor 后面）
    if "[BWE-DECISION]" in line and current_gain_info:
        match = re.search(r'Strategy: ([\w-]+), .*NewTarget: ([\d.]+) bps, Change: ([-\d.]+) bps', line)
        if match:
            data.append({
                **current_gain_info,
                'bwe_strategy': match.group(1),
                'bwe_target': float(match.group(2)),
                'bwe_change': float(match.group(3))
            })
            current_gain_info = None  # Reset

print(f"配对的数据点: {len(data)}")

# 按策略分组分析
additive_data = [d for d in data if d['bwe_strategy'] == 'Additive-Increase']
multiplicative_data = [d for d in data if d['bwe_strategy'] == 'Multiplicative-Increase']

print(f"Additive 策略数据: {len(additive_data)}")
print(f"Multiplicative 策略数据: {len(multiplicative_data)}")
print()

# 分析 Additive 策略下的影响
print("=" * 80)
print("Additive 策略：增益因子建议 vs 实际增长对比")
print("=" * 80)

if additive_data:
    # 按增益因子分组
    gains = [0.0, 0.5, 1.0, 1.5, 2.0]

    print(f"\n{'Gain':<8} {'样本数':<10} {'平均Base':<15} {'平均Adjusted':<15} {'实际Change':<15} {'差异':<15}")
    print("-" * 80)

    for gain in gains:
        gain_data = [d for d in additive_data if d['gain'] == gain]
        if gain_data:
            avg_base = np.mean([d['base_rate'] for d in gain_data])
            avg_adjusted = np.mean([d['adjusted_rate'] for d in gain_data])
            avg_change = np.mean([abs(d['bwe_change']) for d in gain_data])

            # 注意：bwe_change 是总增量 (bps)，而 base_rate 是速率 (bps/s)
            # 需要考虑时间间隔，但这里先看比例关系

            print(f"{gain:<8.1f} {len(gain_data):<10} {avg_base:<15.0f} {avg_adjusted:<15.0f} "
                  f"{avg_change:<15.0f} {avg_adjusted - avg_base:<+15.0f}")

print()

# 关键分析：增益因子如果启用会如何改变带宽增长
print("=" * 80)
print("关键对比：当前实际 vs 启用增益因子后的预期")
print("=" * 80)

# 计算当前使用 base_rate 时的理论增长速率
# 和使用 adjusted_rate 时的理论增长速率

if additive_data:
    # 估算时间间隔（假设大约 100ms 间隔）
    avg_time_interval = 0.1  # 100ms

    total_current_growth = sum([d['base_rate'] * avg_time_interval for d in additive_data])
    total_adjusted_growth = sum([d['adjusted_rate'] * avg_time_interval for d in additive_data])

    print(f"\nAdditive 策略总增长量估算 (假设100ms间隔):")
    print(f"  当前 (Base rate):       {total_current_growth:.0f} bps")
    print(f"  启用增益 (Adjusted):    {total_adjusted_growth:.0f} bps")
    print(f"  差异:                   {total_adjusted_growth - total_current_growth:+.0f} bps "
          f"({(total_adjusted_growth/total_current_growth - 1)*100:+.1f}%)")

    print(f"\n按增益档位分析影响:")
    for gain in gains:
        gain_data = [d for d in additive_data if d['gain'] == gain]
        if gain_data:
            current = sum([d['base_rate'] * avg_time_interval for d in gain_data])
            adjusted = sum([d['adjusted_rate'] * avg_time_interval for d in gain_data])

            if gain == 0.0:
                strategy = "停止增长"
                impact = "会完全停止带宽增长"
            elif gain == 0.5:
                strategy = "保守增长"
                impact = "会减慢50%的增长速度"
            elif gain == 1.0:
                strategy = "正常增长"
                impact = "保持不变"
            elif gain == 1.5:
                strategy = "激进增长"
                impact = "会加速50%"
            else:
                strategy = "极激进增长"
                impact = "会加速100% (翻倍)"

            print(f"  Gain {gain}× ({strategy:12s}): {len(gain_data):4d} 次, "
                  f"差异 {adjusted - current:+10.0f} bps - {impact}")

print()

# 可视化对比
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# Plot 1: 增益因子分布
ax1 = axes[0, 0]
gain_counts = {}
for gain in gains:
    gain_counts[gain] = len([d for d in additive_data if d['gain'] == gain])

colors = ['red', 'orange', 'yellow', 'lightgreen', 'lightblue']
bars = ax1.bar([f"{g}×" for g in gains], [gain_counts[g] for g in gains], color=colors)
ax1.set_xlabel('Gain Factor', fontsize=12)
ax1.set_ylabel('Sample Count', fontsize=12)
ax1.set_title('Additive 策略：增益因子分布', fontsize=13, fontweight='bold')
ax1.grid(True, alpha=0.3, axis='y')

# 添加数值标签
for bar in bars:
    height = bar.get_height()
    ax1.text(bar.get_x() + bar.get_width()/2., height,
             f'{int(height)}',
             ha='center', va='bottom', fontsize=10)

# Plot 2: Base rate vs Adjusted rate
ax2 = axes[0, 1]
for gain in gains:
    gain_data = [d for d in additive_data if d['gain'] == gain]
    if gain_data:
        base_rates = [d['base_rate'] for d in gain_data]
        adjusted_rates = [d['adjusted_rate'] for d in gain_data]
        ax2.scatter([gain] * len(base_rates), base_rates, alpha=0.3, s=20, label=f'Base (Gain {gain}×)')
        ax2.scatter([gain] * len(adjusted_rates), adjusted_rates, alpha=0.3, s=20, marker='x')

ax2.set_xlabel('Gain Factor', fontsize=12)
ax2.set_ylabel('Increase Rate (bps/s)', fontsize=12)
ax2.set_title('Base Rate vs Adjusted Rate by Gain', fontsize=13, fontweight='bold')
ax2.grid(True, alpha=0.3)
ax2.set_xticks(gains)

# Plot 3: 累计影响
ax3 = axes[1, 0]
cumulative_impact = []
for gain in gains:
    gain_data = [d for d in additive_data if d['gain'] == gain]
    if gain_data:
        current = sum([d['base_rate'] for d in gain_data])
        adjusted = sum([d['adjusted_rate'] for d in gain_data])
        cumulative_impact.append(adjusted - current)
    else:
        cumulative_impact.append(0)

colors_impact = ['red' if x < 0 else 'green' for x in cumulative_impact]
bars = ax3.bar([f"{g}×" for g in gains], [x/1000 for x in cumulative_impact], color=colors_impact)
ax3.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
ax3.set_xlabel('Gain Factor', fontsize=12)
ax3.set_ylabel('Cumulative Impact (kbps/s)', fontsize=12)
ax3.set_title('启用增益因子的累计影响 (正=加速, 负=减速)', fontsize=13, fontweight='bold')
ax3.grid(True, alpha=0.3, axis='y')

# 添加数值标签
for bar in bars:
    height = bar.get_height()
    ax3.text(bar.get_x() + bar.get_width()/2., height,
             f'{height:.0f}k',
             ha='center', va='bottom' if height > 0 else 'top', fontsize=9)

# Plot 4: 总体对比
ax4 = axes[1, 1]
total_base = sum([d['base_rate'] for d in additive_data])
total_adjusted = sum([d['adjusted_rate'] for d in additive_data])

categories = ['当前\n(DISABLED)', '启用增益\n(ENABLED)']
values = [total_base / 1000, total_adjusted / 1000]
colors_bar = ['gray', 'green']

bars = ax4.bar(categories, values, color=colors_bar, alpha=0.7, width=0.5)
ax4.set_ylabel('Total Increase Rate (kbps/s)', fontsize=12)
ax4.set_title('总体增长速率对比 (Additive 策略)', fontsize=13, fontweight='bold')
ax4.grid(True, alpha=0.3, axis='y')

# 添加数值和差异标签
for i, bar in enumerate(bars):
    height = bar.get_height()
    ax4.text(bar.get_x() + bar.get_width()/2., height,
             f'{height:.0f}k',
             ha='center', va='bottom', fontsize=11, fontweight='bold')

# 添加差异箭头
diff = values[1] - values[0]
diff_pct = (values[1] / values[0] - 1) * 100
ax4.annotate('', xy=(1, values[1]), xytext=(1, values[0]),
             arrowprops=dict(arrowstyle='<->', color='red', lw=2))
ax4.text(1.15, (values[0] + values[1]) / 2, f'+{diff:.0f}k\n({diff_pct:+.1f}%)',
         fontsize=10, color='red', fontweight='bold', va='center')

plt.suptitle('增益因子策略影响分析 (Additive Increase)', fontsize=15, fontweight='bold')
plt.tight_layout()
plt.savefig('gain_factor_impact_analysis.png', dpi=150, bbox_inches='tight')
print("✅ 可视化已保存: gain_factor_impact_analysis.png\n")

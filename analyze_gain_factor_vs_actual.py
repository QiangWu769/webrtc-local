#!/usr/bin/env python3
"""
分析增益因子策略建议 vs 实际带宽增长
"""

import re
from collections import defaultdict

log_file = "/home/wuq/webrtc-local/webrtc_config_results/sender_local.log"

# 读取日志
with open(log_file, 'r') as f:
    lines = f.readlines()

# 解析数据
gain_factor_logs = []
bwe_decision_logs = []

for line in lines:
    # 解析 GainFactor 日志
    if "[AIMD-GainFactor]" in line:
        match = re.search(r'Score: ([\d.e+-]+), Gain: ([\d.]+), Base rate: ([\d.]+) bps/s, Would adjust to: ([\d.]+) bps/s', line)
        if match:
            gain_factor_logs.append({
                'score': float(match.group(1)),
                'gain': float(match.group(2)),
                'base_rate': float(match.group(3)),
                'adjusted_rate': float(match.group(4))
            })

    # 解析 BWE-DECISION 日志
    if "[BWE-DECISION]" in line:
        match = re.search(r'Strategy: ([\w-]+), .*OldTarget: ([\d.]+) bps, NewTarget: ([\d.]+) bps, Change: ([-\d.]+) bps', line)
        if match:
            bwe_decision_logs.append({
                'strategy': match.group(1),
                'old_target': float(match.group(2)),
                'new_target': float(match.group(3)),
                'change': float(match.group(4))
            })

print(f"总共 GainFactor 日志: {len(gain_factor_logs)}")
print(f"总共 BWE-DECISION 日志: {len(bwe_decision_logs)}")
print()

# 分析增益因子分布
gain_distribution = defaultdict(int)
for log in gain_factor_logs:
    gain = log['gain']
    gain_distribution[gain] += 1

print("=" * 70)
print("增益因子分布:")
print("=" * 70)
for gain in sorted(gain_distribution.keys()):
    count = gain_distribution[gain]
    pct = count * 100 / len(gain_factor_logs)
    print(f"Gain {gain}×: {count:5d} ({pct:5.1f}%)")

print()

# 分析 BWE 策略分布
strategy_distribution = defaultdict(int)
for log in bwe_decision_logs:
    strategy_distribution[log['strategy']] += 1

print("=" * 70)
print("实际 BWE 策略分布:")
print("=" * 70)
for strategy in sorted(strategy_distribution.keys()):
    count = strategy_distribution[strategy]
    pct = count * 100 / len(bwe_decision_logs)
    print(f"{strategy:25s}: {count:5d} ({pct:5.1f}%)")

print()

# 对比 Additive 策略的实际增长 vs 增益因子建议
print("=" * 70)
print("Additive 策略：实际增长 vs 增益因子建议对比")
print("=" * 70)

# 统计 Additive 策略
additive_decisions = [log for log in bwe_decision_logs if log['strategy'] == 'Additive-Increase']

if additive_decisions:
    actual_changes = [log['change'] for log in additive_decisions if log['change'] > 0]

    if actual_changes:
        print(f"Additive 增长次数: {len(actual_changes)}")
        print(f"实际增长平均值: {sum(actual_changes)/len(actual_changes):.0f} bps")
        print(f"实际增长中位数: {sorted(actual_changes)[len(actual_changes)//2]:.0f} bps")
        print(f"实际增长范围: {min(actual_changes):.0f} - {max(actual_changes):.0f} bps")
        print()

# 按增益因子分组，分析建议的调整速率
print("=" * 70)
print("增益因子建议的增长速率统计:")
print("=" * 70)

gains = [0.0, 0.5, 1.0, 1.5, 2.0]
for gain in gains:
    logs_with_gain = [log for log in gain_factor_logs if log['gain'] == gain]
    if logs_with_gain:
        base_rates = [log['base_rate'] for log in logs_with_gain]
        adjusted_rates = [log['adjusted_rate'] for log in logs_with_gain]

        avg_base = sum(base_rates) / len(base_rates)
        avg_adjusted = sum(adjusted_rates) / len(adjusted_rates)

        print(f"\nGain {gain}× ({len(logs_with_gain)} samples):")
        print(f"  平均 Base rate: {avg_base:.0f} bps/s")
        print(f"  平均 Adjusted rate: {avg_adjusted:.0f} bps/s")
        if gain > 0:
            print(f"  调整效果: {avg_base:.0f} → {avg_adjusted:.0f} bps/s ({gain}×)")

print()

# 分析实际增长速率 (从 BWE Change 推算)
print("=" * 70)
print("实际 BWE 增长速率统计:")
print("=" * 70)

multiplicative_changes = [log['change'] for log in bwe_decision_logs
                          if log['strategy'] == 'Multiplicative-Increase' and log['change'] > 0]
additive_changes = [log['change'] for log in bwe_decision_logs
                    if log['strategy'] == 'Additive-Increase' and log['change'] > 0]

if multiplicative_changes:
    print(f"\nMultiplicative 增长:")
    print(f"  样本数: {len(multiplicative_changes)}")
    print(f"  平均增量: {sum(multiplicative_changes)/len(multiplicative_changes):.0f} bps")
    print(f"  中位数增量: {sorted(multiplicative_changes)[len(multiplicative_changes)//2]:.0f} bps")

if additive_changes:
    print(f"\nAdditive 增长:")
    print(f"  样本数: {len(additive_changes)}")
    print(f"  平均增量: {sum(additive_changes)/len(additive_changes):.0f} bps")
    print(f"  中位数增量: {sorted(additive_changes)[len(additive_changes)//2]:.0f} bps")

print()

# 关键对比：如果启用增益因子，会有什么差异
print("=" * 70)
print("如果启用增益因子，预期的影响分析:")
print("=" * 70)

# 当前实际使用 base_rate，如果启用会使用 adjusted_rate
total_base = sum([log['base_rate'] for log in gain_factor_logs])
total_adjusted = sum([log['adjusted_rate'] for log in gain_factor_logs])

print(f"\n当前状态 (DISABLED):")
print(f"  累计 Base rate: {total_base:.0f} bps/s")
print(f"\n如果启用 (ENABLED):")
print(f"  累计 Adjusted rate: {total_adjusted:.0f} bps/s")
print(f"  差异: {total_adjusted - total_base:+.0f} bps/s ({(total_adjusted/total_base - 1)*100:+.1f}%)")

# 按增益分组分析影响
print(f"\n分增益档位影响:")
for gain in sorted(gain_distribution.keys()):
    logs_with_gain = [log for log in gain_factor_logs if log['gain'] == gain]
    count = len(logs_with_gain)
    base_sum = sum([log['base_rate'] for log in logs_with_gain])
    adjusted_sum = sum([log['adjusted_rate'] for log in logs_with_gain])

    if gain == 0.0:
        strategy = "停止增长"
    elif gain == 0.5:
        strategy = "保守增长"
    elif gain == 1.0:
        strategy = "正常增长"
    elif gain == 1.5:
        strategy = "激进增长"
    else:
        strategy = "极激进增长"

    print(f"  Gain {gain}× ({strategy}): {count} 次, 累计差异 {adjusted_sum - base_sum:+.0f} bps/s")

print("\n" + "=" * 70)

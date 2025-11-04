#!/usr/bin/env python3
"""
分析为什么带宽这么低
"""
import re
import numpy as np

log_file = '/home/wuq/webrtc-local/webrtc_config_results/sender_local.log'

# 解析数据
bwe_data = []
ratio_data = []
gain_data = []

with open(log_file, 'r') as f:
    for line in f:
        # BWE决策
        if 'BWE-DECISION' in line:
            match = re.search(r'AckedBitrate: (\d+) bps.*NewTarget: (\d+) bps', line)
            if match:
                acked = int(match.group(1))
                target = int(match.group(2))
                bwe_data.append({'acked': acked, 'target': target})

        # Gain Factor信息
        if 'AIMD-GainFactor' in line and 'ENABLED' in line:
            match = re.search(r'Ratio: ([\d.]+), Gain: ([\d.]+), Base rate: (\d+) bps/s, Adjusted rate: ([\d.]+)', line)
            if match:
                ratio = float(match.group(1))
                gain = float(match.group(2))
                base = int(match.group(3))
                adjusted = float(match.group(4))
                gain_data.append({
                    'ratio': ratio,
                    'gain': gain,
                    'base': base,
                    'adjusted': adjusted
                })

        # Cellular ratio更新
        if 'AIMD-Cellular' in line and 'Resource ratio updated' in line:
            match = re.search(r'updated: ([\d.]+) \(smoothed: ([\d.]+)\)', line)
            if match:
                raw_ratio = float(match.group(1))
                smoothed_ratio = float(match.group(2))
                ratio_data.append({
                    'raw': raw_ratio,
                    'smoothed': smoothed_ratio
                })

print("="*70)
print("带宽低的原因分析")
print("="*70)

# 1. BWE统计
if bwe_data:
    acked_rates = [d['acked'] for d in bwe_data]
    target_rates = [d['target'] for d in bwe_data]

    print("\n【1】BWE带宽统计:")
    print(f"  Acked Bitrate:  Mean={np.mean(acked_rates)/1e6:.2f} Mbps, "
          f"Max={np.max(acked_rates)/1e6:.2f} Mbps")
    print(f"  Target Bitrate: Mean={np.mean(target_rates)/1e6:.2f} Mbps, "
          f"Max={np.max(target_rates)/1e6:.2f} Mbps")
    print(f"  达成率: {100*np.mean(acked_rates)/np.mean(target_rates):.1f}%")

# 2. Gain Factor统计
if gain_data:
    ratios = [d['ratio'] for d in gain_data]
    gains = [d['gain'] for d in gain_data]
    bases = [d['base'] for d in gain_data]
    adjusted = [d['adjusted'] for d in gain_data]

    print("\n【2】Gain Factor统计:")
    print(f"  Ratio:  Mean={np.mean(ratios):.3f}, Median={np.median(ratios):.3f}")
    print(f"  Gain:   Mean={np.mean(gains):.3f}, Median={np.median(gains):.3f}")
    print(f"  Base增长率:  Mean={np.mean(bases)/1000:.1f} kbps (这个太低了!)")
    print(f"  调整后增长率: Mean={np.mean(adjusted)/1000:.1f} kbps")
    print(f"  Gain提升倍数: {np.mean(gains):.2f}x")

    print(f"\n  ⚠️  问题: Base rate只有 {np.mean(bases)/1000:.1f} kbps")
    print(f"      即使gain={np.mean(gains):.2f}x, 调整后也只有 {np.mean(adjusted)/1000:.1f} kbps")
    print(f"      这个增长率太慢，导致带宽增长缓慢")

# 3. Ratio分布
if ratio_data:
    raw_ratios = [d['raw'] for d in ratio_data]
    smoothed_ratios = [d['smoothed'] for d in ratio_data]

    print("\n【3】Cellular Ratio分布:")
    print(f"  Raw ratio:      Mean={np.mean(raw_ratios):.3f}")
    print(f"  Smoothed ratio: Mean={np.mean(smoothed_ratios):.3f}")

    # 分析ratio范围
    low_ratio = [r for r in smoothed_ratios if r < 0.5]
    mid_ratio = [r for r in smoothed_ratios if 0.5 <= r < 1.0]
    high_ratio = [r for r in smoothed_ratios if r >= 1.0]

    print(f"\n  Ratio分布:")
    print(f"    <0.5:  {len(low_ratio):4d} ({100*len(low_ratio)/len(smoothed_ratios):5.1f}%) - 资源不足")
    print(f"    0.5-1: {len(mid_ratio):4d} ({100*len(mid_ratio)/len(smoothed_ratios):5.1f}%) - 中等")
    print(f"    >=1.0: {len(high_ratio):4d} ({100*len(high_ratio)/len(smoothed_ratios):5.1f}%) - 资源充足")

# 4. 根本原因分析
print("\n" + "="*70)
print("【结论】带宽低的根本原因:")
print("="*70)
if gain_data:
    avg_base = np.mean([d['base'] for d in gain_data])
    avg_gain = np.mean([d['gain'] for d in gain_data])
    avg_adjusted = np.mean([d['adjusted'] for d in gain_data])

    print(f"\n1. ❌ AIMD base增长率太低: {avg_base/1000:.1f} kbps")
    print(f"   - 这是additive increase的基础速率")
    print(f"   - 正常应该在 100-500 kbps 范围")
    print(f"   - 当前只有 {avg_base/1000:.1f} kbps，增长太慢")

    print(f"\n2. ✓ Gain Factor工作正常: {avg_gain:.2f}x")
    print(f"   - 将 {avg_base/1000:.1f} kbps 提升到 {avg_adjusted/1000:.1f} kbps")
    print(f"   - 但基数太小，效果有限")

    print(f"\n3. 💡 可能的原因:")
    print(f"   - RTT太大，导致base rate计算过小")
    print(f"   - 频繁的减速事件(overusing)导致带宽下降")
    print(f"   - 初始带宽设置太低")

    print(f"\n4. 🔧 建议解决方案:")
    print(f"   - 检查RTT是否异常大")
    print(f"   - 检查overusing检测是否太敏感")
    print(f"   - 考虑提高最小增长率(kMinIncreaseRateBpsPerSecond)")
    print(f"   - 或者增加gain factor的倍数")

print("\n" + "="*70)

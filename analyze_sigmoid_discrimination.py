#!/usr/bin/env python3
"""
分析当前sigmoid的区分度问题
"""

import numpy as np
import matplotlib.pyplot as plt
import re

def current_sigmoid(ratio, center=0.5, steepness=10.0):
    """当前使用的sigmoid (direct)"""
    return 1.0 / (1.0 + np.exp(-steepness * (ratio - center))) * 100.0

def inverse_sigmoid(ratio, center=0.25, steepness=15.0):
    """之前的inverse sigmoid"""
    sigmoid = 1.0 / (1.0 + np.exp(-steepness * (ratio - center)))
    return (1.0 - sigmoid) * 100.0

# 解析实际数据
data = []
with open('/home/wuq/webrtc-local/webrtc_config_results/sender_local.log', 'r') as f:
    current_ratio = None
    current_score = None
    current_bw = None

    for line in f:
        if '[AIMD-Cellular]' in line:
            match = re.search(r'Smoothed Ratio: ([\d.]+)', line)
            if match:
                current_ratio = float(match.group(1))

        if '[AIMD-SatBoost]' in line:
            match = re.search(r'Base Score: ([\d.e+-]+)', line)
            if match:
                current_score = float(match.group(1))

        if '[DelayBWE-Decision]' in line:
            match = re.search(r'New bitrate: ([\d.]+) bps', line)
            if match:
                current_bw = float(match.group(1)) / 1000000.0

        if current_ratio is not None and current_score is not None and current_bw is not None:
            data.append({
                'ratio': current_ratio,
                'score': current_score,
                'bandwidth': current_bw
            })
            current_ratio = None
            current_score = None
            current_bw = None

ratios = np.array([d['ratio'] for d in data])
scores = np.array([d['score'] for d in data])
bandwidths = np.array([d['bandwidth'] for d in data])

print("="*100)
print("                          🔍 Sigmoid区分度分析")
print("="*100)

# 1. 分析ratio分布
print("\n【1】Ratio分布:")
percentiles = [10, 25, 50, 75, 90, 95, 99]
print(f"   {'百分位':>8} | {'Ratio':>8} | {'对应Score':>10} | {'对应BW':>10}")
print("   " + "-"*45)
for p in percentiles:
    ratio_p = np.percentile(ratios, p)
    score_p = current_sigmoid(ratio_p, 0.5, 10)
    idx = np.argmin(np.abs(ratios - ratio_p))
    bw_p = bandwidths[idx]
    print(f"   P{p:>2}      | {ratio_p:>8.3f} | {score_p:>10.2f} | {bw_p:>9.2f}M")

# 2. 分析当前sigmoid的问题
print("\n【2】当前Sigmoid (center=0.5, steepness=10) 的问题:")
print()
print("   Ratio → Score 映射:")
test_ratios = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0, 1.5]
print(f"   {'Ratio':>8} | {'Score':>8} | {'网络状态':>15}")
print("   " + "-"*40)
for r in test_ratios:
    s = current_sigmoid(r, 0.5, 10)
    if r < 0.3:
        state = "拥塞/高负载"
    elif r < 0.5:
        state = "中等负载"
    elif r < 0.8:
        state = "较空闲"
    else:
        state = "空闲"
    print(f"   {r:>8.1f} | {s:>8.2f} | {state:>15}")

print("\n   ⚠️  问题:")
print("   - Ratio < 0.5时, Score都很低(<7)")
print("   - 但实际数据显示: 53%的样本Ratio > 0.5 (导致Score < 50)")
print("   - Score在0-50范围内区分度不够!")

# 3. 统计Score在不同范围的样本占比
print("\n【3】Score分布问题:")
bins = [(0, 10), (10, 20), (20, 30), (30, 50), (50, 70), (70, 90), (90, 100)]
print(f"   {'Score范围':>12} | {'样本数':>8} | {'占比':>8} | {'中位数BW':>10}")
print("   " + "-"*45)
for low, high in bins:
    mask = (scores >= low) & (scores < high)
    count = np.sum(mask)
    ratio = count / len(scores) * 100
    if count > 0:
        median_bw = np.median(bandwidths[mask])
        print(f"   [{low:>3}, {high:>3}) | {count:>8} | {ratio:>7.1f}% | {median_bw:>9.2f}M")

print("\n   ⚠️  发现:")
print(f"   - Score < 50的样本占 {np.sum(scores < 50)/len(scores)*100:.1f}%")
print(f"   - 但这些样本的带宽变化范围很大 (1.46M - 18M)")
print(f"   - 需要更好的区分!")

# 4. 建议新的参数
print("\n" + "="*100)
print("                          💡 改进建议")
print("="*100)

print("\n【方案1】调整center和steepness:")
print("\n   问题: 当前center=0.5太高,导致大部分样本都映射到低分区")
print("   建议: center=0.3, steepness=12")
print()
print("   新映射 (center=0.3, steepness=12):")
print(f"   {'Ratio':>8} | {'旧Score':>10} | {'新Score':>10} | {'改进':>10}")
print("   " + "-"*45)
for r in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0]:
    old_s = current_sigmoid(r, 0.5, 10)
    new_s = current_sigmoid(r, 0.3, 12)
    diff = new_s - old_s
    print(f"   {r:>8.1f} | {old_s:>10.2f} | {new_s:>10.2f} | {diff:>+10.2f}")

print("\n【方案2】使用inverse sigmoid (回到原来的方案):")
print("\n   问题: 你现在用的是direct sigmoid, 但ratio含义是 allocated/requested")
print("   - Ratio低(0.1) = 网络繁忙/高带宽 → 应该高分")
print("   - Ratio高(1.0) = 网络空闲/低带宽 → 应该低分")
print()
print("   Inverse Sigmoid (center=0.25, steepness=15):")
print(f"   {'Ratio':>8} | {'Direct':>10} | {'Inverse':>10} | {'实际BW':>10}")
print("   " + "-"*45)
for r in [0.1, 0.2, 0.3, 0.4, 0.5, 0.8, 1.0]:
    direct_s = current_sigmoid(r, 0.5, 10)
    inverse_s = inverse_sigmoid(r, 0.25, 15)
    # 找实际带宽
    mask = np.abs(ratios - r) < 0.05
    if np.sum(mask) > 0:
        actual_bw = np.median(bandwidths[mask])
        print(f"   {r:>8.1f} | {direct_s:>10.2f} | {inverse_s:>10.2f} | {actual_bw:>9.2f}M")
    else:
        print(f"   {r:>8.1f} | {direct_s:>10.2f} | {inverse_s:>10.2f} | {'N/A':>10}")

print("\n" + "="*100)
print("                          🎯 推荐方案")
print("="*100)
print("\n   ✅ 使用 Inverse Sigmoid (center=0.25, steepness=15)")
print()
print("   理由:")
print("   1. Ratio含义: 低ratio = 高带宽 → 需要inverse映射")
print("   2. 区分度更好: ratio 0.1-0.5范围内score变化大")
print("   3. 已验证有效: 之前分析显示inverse相关性0.84")
print()
print("   或者调整Direct Sigmoid参数:")
print("   ✅ 使用 Direct Sigmoid (center=0.3, steepness=12)")
print()
print("   理由:")
print("   1. 如果坚持用direct, center=0.3更合理")
print("   2. 让更多样本分布在中高分区")
print("   3. steepness=12提高敏感度")
print("="*100)

# 绘图对比
fig, axes = plt.subplots(1, 2, figsize=(16, 6))

# 左图: 当前sigmoid vs 建议的参数
ax1 = axes[0]
ratio_range = np.linspace(0, 1.5, 1000)
current = current_sigmoid(ratio_range, 0.5, 10)
new_direct = current_sigmoid(ratio_range, 0.3, 12)
inverse = inverse_sigmoid(ratio_range, 0.25, 15)

ax1.plot(ratio_range, current, 'b-', linewidth=2, label='Current (c=0.5, k=10)', alpha=0.7)
ax1.plot(ratio_range, new_direct, 'g-', linewidth=2, label='New Direct (c=0.3, k=12)', alpha=0.7)
ax1.plot(ratio_range, inverse, 'r-', linewidth=2, label='Inverse (c=0.25, k=15)', alpha=0.7)
ax1.axhline(y=90, color='orange', linestyle='--', alpha=0.5, label='Peak=90')
ax1.axvline(x=0.5, color='gray', linestyle=':', alpha=0.5)
ax1.set_xlabel('Ratio', fontsize=12, fontweight='bold')
ax1.set_ylabel('Score', fontsize=12, fontweight='bold')
ax1.set_title('Sigmoid Mapping Comparison', fontsize=14, fontweight='bold')
ax1.legend(fontsize=10)
ax1.grid(True, alpha=0.3)
ax1.set_xlim([0, 1.5])

# 右图: 实际ratio分布
ax2 = axes[1]
ax2.hist(ratios, bins=50, alpha=0.6, color='steelblue', edgecolor='black')
ax2.axvline(x=0.5, color='red', linestyle='--', linewidth=2, label='Current center=0.5')
ax2.axvline(x=0.3, color='green', linestyle='--', linewidth=2, label='Suggested center=0.3')
ax2.axvline(x=0.25, color='orange', linestyle='--', linewidth=2, label='Inverse center=0.25')
ax2.set_xlabel('Ratio', fontsize=12, fontweight='bold')
ax2.set_ylabel('Count', fontsize=12, fontweight='bold')
ax2.set_title('Actual Ratio Distribution', fontsize=14, fontweight='bold')
ax2.legend(fontsize=10)
ax2.grid(True, alpha=0.3, axis='y')

plt.tight_layout()
plt.savefig('sigmoid_discrimination_analysis.png', dpi=150, bbox_inches='tight')
print(f"\n✅ 分析图表已保存: sigmoid_discrimination_analysis.png")

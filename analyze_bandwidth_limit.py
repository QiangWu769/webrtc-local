#!/usr/bin/env python3
"""分析sender_local.log中带宽限制到2.5Mbps的原因"""

import re
from collections import defaultdict

log_file = "/home/wuq/webrtc-local/webrtc_config_results/sender_local.log"

# 收集关键信息
bwe_results = []
aimd_updates = []
overusing_events = []
probe_results = []
link_capacity = []
ratio_scores = []

with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
    for line in f:
        # BWE结果
        if '[DelayBWE-Result]' in line:
            match = re.search(r'\[(\d+\.\d+)\].*New estimate:\s*(\d+)\s*bps', line)
            if match:
                timestamp = float(match.group(1))
                bwe = int(match.group(2))
                bwe_results.append((timestamp, bwe))

        # AIMD更新
        if '[AIMD-Update]' in line:
            match = re.search(r'\[(\d+\.\d+)\].*Input state:\s*(\d+).*Estimated throughput:\s*(\d+)\s*bps.*Current bitrate:\s*(\d+)\s*bps', line)
            if match:
                timestamp = float(match.group(1))
                state = int(match.group(2))  # 0=Normal, 1=Overusing, 2=Underusing
                throughput = int(match.group(3))
                current = int(match.group(4))
                aimd_updates.append((timestamp, state, throughput, current))

        # 检测OVERUSING状态
        if 'OVERUSING' in line or 'Input state: 1' in line:
            match = re.search(r'\[(\d+\.\d+)\]', line)
            if match:
                timestamp = float(match.group(1))
                overusing_events.append((timestamp, line.strip()))

        # Probe结果
        if '[ProbeBWE-Result]' in line:
            match = re.search(r'Cluster ID:\s*(\d+).*Final estimate:\s*(\d+)\s*bps', line)
            if match:
                cluster_id = int(match.group(1))
                estimate = int(match.group(2))
                probe_results.append((cluster_id, estimate))

        # Link capacity
        if 'Link capacity' in line or 'link_capacity_estimate' in line:
            link_capacity.append(line.strip())

        # Ratio相关
        if 'cellular_ratio' in line or 'CellularReceiver' in line:
            ratio_scores.append(line.strip())

print("=" * 80)
print("带宽限制分析报告")
print("=" * 80)

# 分析最终稳定的带宽
if bwe_results:
    print(f"\n1. BWE估计历史 (最后10个):")
    for timestamp, bwe in bwe_results[-10:]:
        print(f"   时间: {timestamp:.3f}, BWE: {bwe/1e6:.2f} Mbps")
    final_bwe = bwe_results[-1][1]
    print(f"\n   最终BWE: {final_bwe/1e6:.2f} Mbps")

# 分析AIMD状态
if aimd_updates:
    print(f"\n2. AIMD状态分析 (最后20个):")
    overusing_count = 0
    normal_count = 0
    underusing_count = 0

    for timestamp, state, throughput, current in aimd_updates[-20:]:
        state_str = {0: "Normal", 1: "OVERUSING", 2: "Underusing"}[state]
        if state == 1:
            overusing_count += 1
        elif state == 0:
            normal_count += 1
        else:
            underusing_count += 1
        print(f"   时间: {timestamp:.3f}, 状态: {state_str:10s}, "
              f"测量吞吐量: {throughput/1e6:.2f} Mbps, 当前码率: {current/1e6:.2f} Mbps")

    print(f"\n   状态统计(最后20个): Normal={normal_count}, OVERUSING={overusing_count}, Underusing={underusing_count}")

    # 最后的吞吐量测量
    last_throughput = aimd_updates[-1][2]
    last_current = aimd_updates[-1][3]
    print(f"   最后测量吞吐量: {last_throughput/1e6:.2f} Mbps")
    print(f"   最后当前码率: {last_current/1e6:.2f} Mbps")

# 分析OVERUSING事件
if overusing_events:
    print(f"\n3. OVERUSING事件数量: {len(overusing_events)}")
    if len(overusing_events) > 0:
        print(f"   最近5次OVERUSING事件:")
        for timestamp, event in overusing_events[-5:]:
            print(f"   时间: {timestamp:.3f}")

# Probe结果
if probe_results:
    print(f"\n4. Probe结果:")
    for cluster_id, estimate in probe_results[-5:]:
        print(f"   Cluster {cluster_id}: {estimate/1e6:.2f} Mbps")

# Ratio信息
if ratio_scores:
    print(f"\n5. Cellular Ratio信息:")
    print(f"   发现 {len(ratio_scores)} 条ratio相关日志")
    if ratio_scores:
        print(f"   示例: {ratio_scores[-1][:150]}")

# 链路容量
if link_capacity:
    print(f"\n6. Link Capacity信息:")
    print(f"   发现 {len(link_capacity)} 条link capacity相关日志")

print("\n" + "=" * 80)
print("诊断结论:")
print("=" * 80)

# 根据数据给出诊断
if aimd_updates:
    last_throughput = aimd_updates[-1][2] / 1e6
    last_current = aimd_updates[-1][3] / 1e6

    print(f"\n当前带宽限制在 {last_current:.2f} Mbps")
    print(f"最后测量的网络吞吐量: {last_throughput:.2f} Mbps")

    if last_throughput < 1.5:
        print("\n⚠️  主要原因：网络吞吐量测量值很低!")
        print("   - Delay-based BWE检测到网络拥塞，测量吞吐量远低于发送速率")
        print("   - AIMD算法会限制带宽不超过测量吞吐量的安全倍数")
        print("   - 可能原因：")
        print("     1. 网络实际容量有限")
        print("     2. Delay增加导致trendline检测为OVERUSING")
        print("     3. 测量窗口内的吞吐量统计偏低")

    if overusing_count > normal_count:
        print("\n⚠️  检测到频繁的OVERUSING状态!")
        print("   - AIMD会在OVERUSING时降低码率")
        print("   - 持续OVERUSING会导致带宽无法增长")

print("\n建议检查:")
print("  1. 网络实际容量 (使用iperf测试)")
print("  2. RTT变化情况 (delay-based检测依赖RTT趋势)")
print("  3. Trendline slope计算 (决定OVERUSING判断)")
print("  4. AIMD增长参数配置")

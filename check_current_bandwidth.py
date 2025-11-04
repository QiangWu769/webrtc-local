#!/usr/bin/env python3
"""检查当前delay-based BWE和acked bitrate的情况"""

import re

log_file = "/home/wuq/webrtc-local/webrtc_config_results/sender_local.log"

# 收集数据
delay_bwe_results = []  # Delay-based BWE结果
acked_bitrates = []     # Acked bitrate (estimated throughput)
current_bitrates = []   # 当前发送码率
probe_results = []      # Probe结果

with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
    for line in f:
        # Delay-based BWE结果
        if '[DelayBWE-Result]' in line:
            match = re.search(r'\[(\d+\.\d+)\].*New estimate:\s*(\d+)\s*bps', line)
            if match:
                timestamp = float(match.group(1))
                bwe = int(match.group(2))
                delay_bwe_results.append((timestamp, bwe))

        # AIMD估计的吞吐量（这就是acked bitrate）
        if '[AIMD-Update]' in line:
            match = re.search(r'\[(\d+\.\d+)\].*Estimated throughput:\s*(\d+)\s*bps.*Current bitrate:\s*(\d+)\s*bps', line)
            if match:
                timestamp = float(match.group(1))
                throughput = int(match.group(2))
                current = int(match.group(3))
                acked_bitrates.append((timestamp, throughput))
                current_bitrates.append((timestamp, current))

        # Probe结果
        if '[ProbeBWE-Result]' in line:
            match = re.search(r'Cluster ID:\s*(\d+).*Final estimate:\s*(\d+)\s*bps', line)
            if match:
                cluster_id = int(match.group(1))
                estimate = int(match.group(2))
                probe_results.append((cluster_id, estimate))

print("=" * 80)
print("当前带宽状态分析")
print("=" * 80)

# 1. Delay-based BWE
if delay_bwe_results:
    print(f"\n1. Delay-based BWE (最后10个结果):")
    for timestamp, bwe in delay_bwe_results[-10:]:
        print(f"   时间: {timestamp:.3f}, BWE: {bwe/1e6:.2f} Mbps")
    final_delay_bwe = delay_bwe_results[-1][1] / 1e6
    print(f"\n   ✓ 最终Delay-based BWE: {final_delay_bwe:.2f} Mbps")
else:
    print("\n1. Delay-based BWE: 无数据")
    # 检查是否有probe结果作为初始BWE
    if probe_results:
        last_probe = probe_results[-1][1] / 1e6
        print(f"   使用Probe结果: {last_probe:.2f} Mbps")
        final_delay_bwe = last_probe
    else:
        final_delay_bwe = 0

# 2. Acked Bitrate (Estimated Throughput)
if acked_bitrates:
    print(f"\n2. Acked Bitrate / Estimated Throughput (最后10个):")
    for timestamp, acked in acked_bitrates[-10:]:
        print(f"   时间: {timestamp:.3f}, Acked: {acked/1e6:.2f} Mbps")
    final_acked = acked_bitrates[-1][1] / 1e6
    print(f"\n   ✓ 最终Acked Bitrate: {final_acked:.2f} Mbps")
else:
    print("\n2. Acked Bitrate: 无数据")
    final_acked = 0

# 3. 当前发送码率
if current_bitrates:
    final_current = current_bitrates[-1][1] / 1e6
    print(f"\n3. 当前发送码率: {final_current:.2f} Mbps")
else:
    print("\n3. 当前发送码率: 无数据")
    final_current = 0

# 4. Probe结果
if probe_results:
    print(f"\n4. Probe结果 (最后5个):")
    for cluster_id, estimate in probe_results[-5:]:
        print(f"   Cluster {cluster_id}: {estimate/1e6:.2f} Mbps")

# 分析和对比
print("\n" + "=" * 80)
print("对比分析")
print("=" * 80)

print(f"\n当前状态:")
print(f"  - Delay-based BWE:      {final_delay_bwe:.2f} Mbps  (基于延迟趋势的带宽估计)")
print(f"  - Acked Bitrate:        {final_acked:.2f} Mbps  (基于接收确认的吞吐量)")
print(f"  - Current Bitrate:      {final_current:.2f} Mbps  (实际发送码率)")

print(f"\n关键问题:")
if final_acked < final_delay_bwe * 0.3:
    print(f"  ⚠️  Acked Bitrate远低于Delay-based BWE!")
    print(f"      比例: {final_acked/final_delay_bwe*100:.1f}%")
    print(f"\n  这意味着:")
    print(f"  - Delay-based检测认为网络可以支持 {final_delay_bwe:.2f} Mbps")
    print(f"  - 但实际确认的吞吐量只有 {final_acked:.2f} Mbps")
    print(f"  - AIMD会使用较低的acked bitrate来限制增长")
    print(f"\n  可能原因:")
    print(f"  1. 接收端反馈延迟或不完整")
    print(f"  2. BitrateEstimator的150ms窗口内确认的数据太少")
    print(f"  3. 实际发送速率不足（当前只有{final_current:.2f} Mbps）")
    print(f"  4. Transport-CC反馈包含的packet数量太少")

if final_current < final_delay_bwe * 0.3:
    print(f"\n  ⚠️  当前发送码率远低于Delay-based BWE!")
    print(f"      这可能是主要问题：应用层发送的数据不够")
    print(f"      - 检查视频编码器输出")
    print(f"      - 检查pacer配置")

# 统计acked bitrate的变化趋势
if len(acked_bitrates) > 20:
    recent_acked = [a[1] for a in acked_bitrates[-20:]]
    avg_recent = sum(recent_acked) / len(recent_acked) / 1e6
    min_recent = min(recent_acked) / 1e6
    max_recent = max(recent_acked) / 1e6
    print(f"\n  Acked Bitrate近期统计 (最后20个样本):")
    print(f"  - 平均: {avg_recent:.2f} Mbps")
    print(f"  - 范围: {min_recent:.2f} - {max_recent:.2f} Mbps")
    print(f"  - 波动: {(max_recent - min_recent)/avg_recent*100:.1f}%")

print("\n建议:")
print("  1. 查看BitrateEstimator日志（需要确保日志级别为INFO）")
print("  2. 检查每150ms窗口内确认的字节数")
print("  3. 对比Transport-CC反馈的packet数量和大小")
print("  4. 考虑增加视频码率或帧率，确保有足够的数据发送")

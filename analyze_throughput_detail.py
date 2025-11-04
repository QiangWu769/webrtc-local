#!/usr/bin/env python3
"""详细分析为什么测量吞吐量这么低"""

import re
import matplotlib.pyplot as plt
from collections import defaultdict

log_file = "/home/wuq/webrtc-local/webrtc_config_results/sender_local.log"

# 收集数据
timestamps = []
throughputs = []
current_bitrates = []
increase_limits = []
alr_states = []
delay_states = []

with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
    for line in f:
        # AIMD更新 - 获取测量吞吐量
        if '[AIMD-Update]' in line:
            match = re.search(r'\[(\d+\.\d+)\].*Input state:\s*(\d+).*Estimated throughput:\s*(\d+)\s*bps.*Current bitrate:\s*(\d+)\s*bps.*In ALR:\s*(\w+)', line)
            if match:
                timestamp = float(match.group(1))
                state = int(match.group(2))
                throughput = int(match.group(3))
                current = int(match.group(4))
                alr = match.group(5)

                timestamps.append(timestamp)
                throughputs.append(throughput / 1e6)
                current_bitrates.append(current / 1e6)
                alr_states.append(1 if alr == 'yes' else 0)
                delay_states.append(state)

        # AIMD增加限制
        if '[AIMD-Increase]' in line:
            match = re.search(r'Increase limit:\s*(\d+)\s*bps', line)
            if match:
                limit = int(match.group(1))
                increase_limits.append(limit / 1e6)

# 归一化时间
if timestamps:
    start_time = timestamps[0]
    timestamps = [t - start_time for t in timestamps]

print("=" * 80)
print("吞吐量测量详细分析")
print("=" * 80)

# 统计
if throughputs:
    print(f"\n测量吞吐量统计:")
    print(f"  最小值: {min(throughputs):.2f} Mbps")
    print(f"  最大值: {max(throughputs):.2f} Mbps")
    print(f"  平均值: {sum(throughputs)/len(throughputs):.2f} Mbps")
    print(f"  最后值: {throughputs[-1]:.2f} Mbps")

if current_bitrates:
    print(f"\n当前码率统计:")
    print(f"  最小值: {min(current_bitrates):.2f} Mbps")
    print(f"  最大值: {max(current_bitrates):.2f} Mbps")
    print(f"  平均值: {sum(current_bitrates)/len(current_bitrates):.2f} Mbps")
    print(f"  最后值: {current_bitrates[-1]:.2f} Mbps")

# ALR状态统计
alr_count = sum(alr_states)
print(f"\n应用受限区域(ALR)状态:")
print(f"  在ALR中: {alr_count}/{len(alr_states)} ({100*alr_count/len(alr_states):.1f}%)")
print(f"  说明: ALR表示发送速率受应用限制，不是网络限制")

# Delay状态统计
normal_count = delay_states.count(0)
overusing_count = delay_states.count(1)
underusing_count = delay_states.count(2)
print(f"\nDelay状态统计:")
print(f"  Normal: {normal_count} ({100*normal_count/len(delay_states):.1f}%)")
print(f"  OVERUSING: {overusing_count} ({100*overusing_count/len(delay_states):.1f}%)")
print(f"  Underusing: {underusing_count} ({100*underusing_count/len(delay_states):.1f}%)")

# 绘图
fig, axes = plt.subplots(4, 1, figsize=(14, 12))

# 子图1: 吞吐量 vs 码率
ax1 = axes[0]
ax1.plot(timestamps, throughputs, 'b-', label='Measured Throughput', linewidth=1)
ax1.plot(timestamps, current_bitrates, 'r-', label='Current Bitrate', linewidth=1)
ax1.set_ylabel('Bitrate (Mbps)')
ax1.set_title('Measured Throughput vs Current Bitrate')
ax1.legend()
ax1.grid(True, alpha=0.3)

# 子图2: 吞吐量放大
ax2 = axes[1]
ax2.plot(timestamps, throughputs, 'g-', linewidth=1)
ax2.set_ylabel('Throughput (Mbps)')
ax2.set_title('Measured Throughput Detail (为什么这么低?)')
ax2.grid(True, alpha=0.3)
ax2.axhline(y=2.5, color='r', linestyle='--', label='Target ~2.5 Mbps')
ax2.legend()

# 子图3: ALR状态
ax3 = axes[2]
ax3.fill_between(timestamps, 0, alr_states, alpha=0.5, color='orange', label='In ALR')
ax3.set_ylabel('ALR State')
ax3.set_ylim(-0.1, 1.1)
ax3.set_title('Application Limited Region (ALR) State')
ax3.legend()
ax3.grid(True, alpha=0.3)

# 子图4: Delay状态
ax4 = axes[3]
delay_colors = ['green' if s == 0 else 'red' if s == 1 else 'blue' for s in delay_states]
ax4.scatter(timestamps, delay_states, c=delay_colors, s=2, alpha=0.6)
ax4.set_ylabel('Delay State')
ax4.set_xlabel('Time (seconds)')
ax4.set_title('Delay-based State (0=Normal, 1=OVERUSING, 2=Underusing)')
ax4.set_ylim(-0.5, 2.5)
ax4.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('/home/wuq/webrtc-local/webrtc_config_results/throughput_analysis.png', dpi=150)
print(f"\n✓ 图表已保存到: webrtc_config_results/throughput_analysis.png")

# 分析为什么吞吐量低
print("\n" + "=" * 80)
print("问题分析：为什么测量吞吐量只有0.5 Mbps，而目标是2.5 Mbps?")
print("=" * 80)

if alr_count / len(alr_states) > 0.5:
    print("\n⚠️  关键发现：系统长期处于ALR状态!")
    print("   - ALR (Application Limited Region) 表示应用没有足够的数据要发送")
    print("   - 在ALR状态下，实际发送速率远低于带宽估计值")
    print("   - 测量吞吐量基于实际发送的数据，所以会很低")
    print("\n   可能原因:")
    print("   1. 视频编码器输出码率太低")
    print("   2. 帧率不足")
    print("   3. 没有足够的视频数据需要发送")
    print("\n   解决方案:")
    print("   1. 增加视频输入源的分辨率/帧率")
    print("   2. 检查视频编码器配置")
    print("   3. 确保有持续的视频流输入")

print("\n当前情况:")
print(f"  - 带宽估计允许发送: ~2.5 Mbps")
print(f"  - 实际测量吞吐量: ~0.5 Mbps")
print(f"  - 差距原因: 应用没有足够数据发送 (ALR)")
print(f"  - 这不是网络容量问题，而是应用层问题")

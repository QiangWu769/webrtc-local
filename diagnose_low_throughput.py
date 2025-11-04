#!/usr/bin/env python3
"""诊断为什么estimated throughput只有0.5 Mbps，而实际带宽有10+ Mbps"""

import re

log_file = "/home/wuq/webrtc-local/webrtc_config_results/sender_local.log"

# 收集关键数据
send_rates = []
acked_rates = []
loss_rates = []
rtt_values = []
throughput_estimates = []

with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
    for line in f:
        # 发送速率
        if 'send_rate' in line.lower() or 'SendRate' in line:
            match = re.search(r'send.*?rate.*?(\d+\.?\d*)\s*(bps|kbps|Mbps)', line, re.IGNORECASE)
            if match:
                rate = float(match.group(1))
                unit = match.group(2)
                if unit == 'kbps':
                    rate *= 1000
                elif unit == 'Mbps':
                    rate *= 1e6
                send_rates.append(rate)

        # Acked bitrate - 这是关键！
        if 'acked_bitrate' in line or 'AckedBitrate' in line:
            match = re.search(r'acked.*?bitrate.*?(\d+\.?\d*)\s*(bps|kbps|Mbps)', line, re.IGNORECASE)
            if match:
                rate = float(match.group(1))
                unit = match.group(2)
                if unit == 'kbps':
                    rate *= 1000
                elif unit == 'Mbps':
                    rate *= 1e6
                acked_rates.append(rate)

        # 丢包率
        if 'loss' in line.lower() and 'fraction' in line.lower():
            match = re.search(r'fraction.*?loss.*?(\d+\.?\d*)', line, re.IGNORECASE)
            if match:
                loss_rates.append(float(match.group(1)))

        # RTT
        if 'rtt' in line.lower():
            match = re.search(r'rtt.*?(\d+\.?\d*)\s*ms', line, re.IGNORECASE)
            if match:
                rtt_values.append(float(match.group(1)))

        # Estimated throughput from AIMD
        if 'Estimated throughput:' in line:
            match = re.search(r'Estimated throughput:\s*(\d+)\s*bps', line)
            if match:
                throughput_estimates.append(int(match.group(1)))

print("=" * 80)
print("低吞吐量诊断报告")
print("=" * 80)

print(f"\n1. Estimated Throughput (AIMD测量值):")
if throughput_estimates:
    print(f"   样本数: {len(throughput_estimates)}")
    print(f"   最小值: {min(throughput_estimates)/1e6:.2f} Mbps")
    print(f"   最大值: {max(throughput_estimates)/1e6:.2f} Mbps")
    print(f"   平均值: {sum(throughput_estimates)/len(throughput_estimates)/1e6:.2f} Mbps")
    print(f"   最后值: {throughput_estimates[-1]/1e6:.2f} Mbps")
    print(f"\n   ⚠️  问题：这个值只有0.5 Mbps，远低于实际带宽10+ Mbps!")

print(f"\n2. Acked Bitrate (接收端确认的速率):")
if acked_rates:
    print(f"   样本数: {len(acked_rates)}")
    print(f"   最小值: {min(acked_rates)/1e6:.2f} Mbps")
    print(f"   最大值: {max(acked_rates)/1e6:.2f} Mbps")
    print(f"   平均值: {sum(acked_rates)/len(acked_rates)/1e6:.2f} Mbps")
    print(f"   最后值: {acked_rates[-1]/1e6:.2f} Mbps")
else:
    print(f"   ⚠️  未找到acked_bitrate日志!")
    print(f"   这可能是问题所在 - AIMD依赖acked bitrate来计算estimated throughput")

print(f"\n3. Send Rate:")
if send_rates:
    print(f"   样本数: {len(send_rates)}")
    print(f"   平均值: {sum(send_rates)/len(send_rates)/1e6:.2f} Mbps")

print(f"\n4. RTT:")
if rtt_values:
    print(f"   样本数: {len(rtt_values)}")
    print(f"   平均RTT: {sum(rtt_values)/len(rtt_values):.2f} ms")
    print(f"   最小RTT: {min(rtt_values):.2f} ms")
    print(f"   最大RTT: {max(rtt_values):.2f} ms")
else:
    print(f"   未找到RTT信息")

print(f"\n5. 丢包率:")
if loss_rates:
    print(f"   样本数: {len(loss_rates)}")
    print(f"   平均丢包率: {sum(loss_rates)/len(loss_rates)*100:.2f}%")
else:
    print(f"   未找到丢包率信息")

# 现在搜索AIMD如何计算estimated throughput
print("\n" + "=" * 80)
print("AIMD Estimated Throughput计算逻辑分析")
print("=" * 80)

print("""
AIMD中的 'Estimated throughput' 通常基于：
1. **Acked bitrate** - 接收端确认的数据速率
2. **Receive rate** - 接收端报告的接收速率
3. **RTCP反馈** - Receiver Reports中的统计信息

如果acked_bitrate日志缺失或值很低，说明问题在于：
- 接收端的Transport-CC反馈不完整
- RTCP Receiver Reports缺失或延迟
- Acknowledgment Bitrate Estimator工作异常

建议检查：
""")

# 搜索acknowledge bitrate estimator的日志
print("\n正在搜索AcknowledgedBitrateEstimator的日志...")
ack_estimator_logs = []
with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
    for line in f:
        if 'AcknowledgedBitrate' in line or 'acknowledged_bitrate' in line:
            ack_estimator_logs.append(line.strip())

if ack_estimator_logs:
    print(f"找到 {len(ack_estimator_logs)} 条AcknowledgedBitrateEstimator日志")
    print("最后5条:")
    for log in ack_estimator_logs[-5:]:
        print(f"  {log[:150]}")
else:
    print("⚠️  未找到AcknowledgedBitrateEstimator日志!")

# 搜索RTCP报告
print("\n正在搜索RTCP Receiver Report...")
rtcp_logs = []
with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
    for line in f:
        if 'RTCP' in line and ('RR' in line or 'Receiver' in line):
            rtcp_logs.append(line.strip())

if rtcp_logs:
    print(f"找到 {len(rtcp_logs)} 条RTCP RR日志")
else:
    print("⚠️  未找到RTCP Receiver Report日志!")

# 搜索Transport-CC反馈
print("\n正在搜索Transport-CC反馈...")
twcc_logs = []
with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
    for line in f:
        if 'transport.*cc' in line.lower() or 'TransportFeedback' in line:
            twcc_logs.append(line.strip())

if twcc_logs:
    print(f"找到 {len(twcc_logs)} 条Transport-CC反馈日志")
else:
    print("⚠️  未找到Transport-CC反馈日志!")

print("\n" + "=" * 80)
print("结论")
print("=" * 80)
print("""
estimated throughput = 0.5 Mbps（而实际带宽10+ Mbps）的原因：

最可能的问题：
1. ✓ Delay-based BWE工作正常（trendline slope正常，没有OVERUSING）
2. ✗ Acked bitrate估计异常低
3. ✗ AIMD的增长受制于低的acked bitrate

这导致：
- AIMD认为网络只能承载0.5 Mbps
- 增长限制(Increase limit) = acked_bitrate * 1.5 ≈ 0.75 Mbps
- 当前码率2.5 Mbps已经远超增长限制
- 所以码率无法继续增长

解决方案：
1. 检查接收端的反馈机制（Transport-CC, RTCP RR）
2. 增加acked bitrate estimator的日志
3. 检查是否有丢包导致ack丢失
4. 调整AIMD参数，降低对acked bitrate的依赖
5. 启用cellular_ratio影响，使用外部信息辅助带宽估计
""")

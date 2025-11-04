#!/usr/bin/env python3
"""分析Transport-CC反馈，计算实际的acked bitrate"""

import re

log_file = "/home/wuq/webrtc-local/webrtc_config_results/sender_local.log"

# 解析Transport-CC反馈
feedbacks = []
with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
    for line in f:
        if '[GCC-INPUT] Received TransportFeedback' in line:
            match = re.search(r'at (\d+) ms, NumPackets: (\d+), InFlight: (\d+) bytes', line)
            if match:
                timestamp_ms = int(match.group(1))
                num_packets = int(match.group(2))
                inflight_bytes = int(match.group(3))
                feedbacks.append({
                    'timestamp_ms': timestamp_ms,
                    'num_packets': num_packets,
                    'inflight_bytes': inflight_bytes
                })

print("=" * 80)
print("Transport-CC反馈分析")
print("=" * 80)

if len(feedbacks) < 2:
    print("反馈数据不足")
    exit(0)

print(f"\n总反馈次数: {len(feedbacks)}")
print(f"时间范围: {feedbacks[0]['timestamp_ms']} - {feedbacks[-1]['timestamp_ms']} ms")
print(f"总时长: {(feedbacks[-1]['timestamp_ms'] - feedbacks[0]['timestamp_ms'])/1000:.2f} 秒")

# 统计最后30个反馈
recent = feedbacks[-30:]
print(f"\n最后30个反馈统计:")

total_packets = sum(f['num_packets'] for f in recent)
avg_packets_per_feedback = total_packets / len(recent)
avg_inflight = sum(f['inflight_bytes'] for f in recent) / len(recent)

print(f"  总packet数: {total_packets}")
print(f"  每次反馈平均packet数: {avg_packets_per_feedback:.1f}")
print(f"  平均inflight: {avg_inflight:.0f} bytes")

# 计算每个反馈的间隔和速率
print(f"\n最后20个反馈详情:")
print(f"  {'时间(ms)':>12} {'间隔(ms)':>10} {'Packets':>8} {'Bytes/Pkt':>10} {'速率估计':>12}")
print(f"  {'-'*12} {'-'*10} {'-'*8} {'-'*10} {'-'*12}")

for i in range(len(recent) - 20, len(recent)):
    f = recent[i]
    if i > 0:
        interval_ms = f['timestamp_ms'] - recent[i-1]['timestamp_ms']
        # 假设每个packet平均1200字节
        avg_pkt_size = 1200
        total_bytes = f['num_packets'] * avg_pkt_size
        if interval_ms > 0:
            rate_mbps = (total_bytes * 8 / interval_ms / 1000)
            print(f"  {f['timestamp_ms']:12d} {interval_ms:10d} {f['num_packets']:8d} {avg_pkt_size:10d} {rate_mbps:11.2f} Mbps")
        else:
            print(f"  {f['timestamp_ms']:12d} {interval_ms:10d} {f['num_packets']:8d} {avg_pkt_size:10d}        N/A")
    else:
        print(f"  {f['timestamp_ms']:12d}       N/A {f['num_packets']:8d}        N/A        N/A")

# 使用150ms滑动窗口计算acked bitrate（模拟BitrateEstimator的行为）
print(f"\n\n使用150ms窗口计算Acked Bitrate:")
print(f"  (模拟BitrateEstimator的行为)")

window_ms = 150
avg_packet_size = 1200  # 假设平均包大小

# 最后500ms的数据
recent_500ms = [f for f in feedbacks if f['timestamp_ms'] >= feedbacks[-1]['timestamp_ms'] - 500]

if len(recent_500ms) > 1:
    window_start = recent_500ms[0]['timestamp_ms']
    window_bytes = 0
    window_packets = 0

    print(f"\n  窗口大小: {window_ms} ms")
    print(f"  {'窗口时间':>20} {'窗口内Packets':>15} {'窗口内Bytes':>15} {'Bitrate':>12}")
    print(f"  {'-'*20} {'-'*15} {'-'*15} {'-'*12}")

    for f in recent_500ms:
        window_packets += f['num_packets']
        window_bytes += f['num_packets'] * avg_packet_size

        # 检查是否达到150ms
        if f['timestamp_ms'] - window_start >= window_ms:
            actual_window = f['timestamp_ms'] - window_start
            bitrate_kbps = (window_bytes * 8) / actual_window
            bitrate_mbps = bitrate_kbps / 1000

            print(f"  {window_start:10d}-{f['timestamp_ms']:10d} {window_packets:15d} {window_bytes:15d} {bitrate_mbps:11.2f} Mbps")

            # 重置窗口
            window_start = f['timestamp_ms']
            window_bytes = 0
            window_packets = 0

print(f"\n\n问题诊断:")
print(f"  1. 每次Transport-CC反馈的packet数量很少（平均{avg_packets_per_feedback:.1f}个）")
print(f"  2. 如果假设每个包1200字节，每次反馈确认约{avg_packets_per_feedback*1200/1024:.1f} KB")
print(f"  3. 在150ms窗口内，可能只有几次反馈，累积字节数不多")
print(f"  4. 这导致BitrateEstimator计算出的bitrate很低")

print(f"\n  可能的原因:")
print(f"  a) 发送速率本身不高（当前1.4 Mbps）")
print(f"  b) Transport-CC反馈频率或packet批量大小的问题")
print(f"  c) 接收端处理延迟")

print(f"\n  如果发送速率1.4 Mbps，理论上:")
print(f"  - 每秒发送约 {1.4*1e6/8/1200:.0f} 个1200字节的包")
print(f"  - 150ms应该发送约 {1.4*1e6/8/1200*0.15:.0f} 个包")
print(f"  - 应该确认约 {1.4*0.15:.2f} Mbps = {1.4*0.15*1e6/8/1024:.0f} KB")
print(f"\n  但实际BitrateEstimator只测到0.39 Mbps，说明150ms内确认的数据远少于预期")

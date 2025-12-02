#!/usr/bin/env python3
"""
分析发送端和接收端日志，计算时钟偏差
"""

import re
import sys

def parse_sender_log(log_file):
    """解析发送端日志，提取时间戳"""
    timestamps = []
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            # 查找包含时间戳的行
            # 根据实际日志格式调整
            if '[C2R-' in line or 'MonoTime' in line:
                # 提取RTP时间戳和本地时间
                match = re.search(r'RtpTs=(\d+).*MonoUs=(\d+)', line)
                if match:
                    rtp_ts = int(match.group(1))
                    mono_us = int(match.group(2))
                    timestamps.append({
                        'rtp_ts': rtp_ts,
                        'mono_us': mono_us,
                        'line': line.strip()
                    })
    return timestamps

def parse_receiver_log(log_file):
    """解析接收端日志，提取时间戳"""
    timestamps = []
    ntp_offset = None

    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            # 提取NTP offset
            if '[C2R-INIT] NtpOffsetUs=' in line:
                match = re.search(r'NtpOffsetUs=(\d+)', line)
                if match and ntp_offset is None:
                    ntp_offset = int(match.group(1))
                    print(f"📍 Found NTP Offset: {ntp_offset} us ({ntp_offset/1000:.3f} ms)")

            # 提取组装或解码时的时间戳
            if '[C2R-E2E-ASSEMBLED]' in line or '[C2R-E2E-DECODED]' in line:
                match = re.search(
                    r'RtpTs=(\d+).*CaptureUs=(\d+).*(?:ASSEMBLED|DECODED)Us=(\d+).*(?:ASSEMBLED|DECODED)NtpUs=(\d+)',
                    line
                )
                if match:
                    timestamps.append({
                        'rtp_ts': int(match.group(1)),
                        'capture_ntp_us': int(match.group(2)),
                        'local_mono_us': int(match.group(3)),
                        'local_ntp_us': int(match.group(4)),
                        'type': 'ASSEMBLED' if 'ASSEMBLED' in line else 'DECODED',
                        'line': line.strip()
                    })

    return timestamps, ntp_offset

def calculate_clock_offset(sender_data, receiver_data, receiver_ntp_offset):
    """计算时钟偏差"""

    if not sender_data or not receiver_data:
        print("❌ 没有找到匹配的时间戳数据")
        return

    print("\n" + "="*80)
    print("📊 时钟偏差分析")
    print("="*80)

    # 匹配相同的RTP时间戳
    matches = []
    for s in sender_data:
        for r in receiver_data:
            if s['rtp_ts'] == r['rtp_ts']:
                matches.append((s, r))

    if not matches:
        print("❌ 没有找到发送端和接收端相同的RTP时间戳")
        print(f"   发送端RTP范围: {sender_data[0]['rtp_ts']} - {sender_data[-1]['rtp_ts']}")
        print(f"   接收端RTP范围: {receiver_data[0]['rtp_ts']} - {receiver_data[-1]['rtp_ts']}")
        return

    print(f"✅ 找到 {len(matches)} 个匹配的时间戳\n")

    offsets = []

    for i, (sender, receiver) in enumerate(matches[:10]):  # 只显示前10个
        # 发送端时间（需要转换为NTP时间）
        # 这里假设发送端也有类似的ntp_offset
        # 如果没有，需要用其他方法

        # 接收端的capture时间是已经校正过的NTP时间
        receiver_capture_ntp_us = receiver['capture_ntp_us']

        # 接收端本地NTP时间
        receiver_local_ntp_us = receiver['local_ntp_us']

        # 计算网络+处理延迟
        delay_us = receiver_local_ntp_us - receiver_capture_ntp_us

        print(f"\n帧 {i+1} (RTP={receiver['rtp_ts']}):")
        print(f"  接收端采集时间 (NTP): {receiver_capture_ntp_us} us")
        print(f"  接收端本地时间 (NTP): {receiver_local_ntp_us} us")
        print(f"  延迟: {delay_us/1000:.3f} ms")

        # 如果发送端也输出了NTP时间，可以直接比较
        # 这里先记录延迟
        offsets.append({
            'rtp_ts': receiver['rtp_ts'],
            'delay_us': delay_us,
            'receiver_capture_ntp': receiver_capture_ntp_us,
            'receiver_local_ntp': receiver_local_ntp_us
        })

    # 统计
    if offsets:
        avg_delay = sum(o['delay_us'] for o in offsets) / len(offsets)
        min_delay = min(o['delay_us'] for o in offsets)
        max_delay = max(o['delay_us'] for o in offsets)

        print("\n" + "-"*80)
        print("📈 延迟统计:")
        print(f"  平均延迟: {avg_delay/1000:.3f} ms")
        print(f"  最小延迟: {min_delay/1000:.3f} ms")
        print(f"  最大延迟: {max_delay/1000:.3f} ms")
        print(f"  延迟抖动: {(max_delay - min_delay)/1000:.3f} ms")
        print("-"*80)

    # 说明
    print("\n⚠️  注意:")
    print("  1. 接收端日志中的 CaptureUs 已经是经过时钟偏移校正的时间")
    print("  2. 要看真实的时钟偏移，需要发送端也输出 NTP 时间戳")
    print("  3. 或者添加代码输出 RemoteNtpTimeEstimator 的 offset 值")

def main():
    if len(sys.argv) < 3:
        print("用法: python3 analyze_clock_offset.py <sender_log> <receiver_log>")
        print("示例: python3 analyze_clock_offset.py sender_local.log 'receiver_cloud copy 2.log'")
        sys.exit(1)

    sender_log = sys.argv[1]
    receiver_log = sys.argv[2]

    print("🔍 解析日志文件...")
    print(f"  发送端: {sender_log}")
    print(f"  接收端: {receiver_log}")

    sender_data = parse_sender_log(sender_log)
    receiver_data, ntp_offset = parse_receiver_log(receiver_log)

    print(f"\n📦 发送端数据: {len(sender_data)} 条")
    print(f"📦 接收端数据: {len(receiver_data)} 条")

    if ntp_offset:
        calculate_clock_offset(sender_data, receiver_data, ntp_offset)
    else:
        print("❌ 未找到接收端的 NTP Offset")

if __name__ == '__main__':
    main()

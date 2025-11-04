#!/usr/bin/env python3
"""
Calculate End-to-End delay from WebRTC C2R logs
解决两台机器时钟不同步问题，计算真实的端到端延迟
"""

import re
import math

def parse_logs():
    """解析发送端和接收端日志"""

    # 解析发送端数据 - ACT传输时间
    sender_data = {}
    with open('/home/wuq/webrtc-local/webrtc_config_results/sender_local.log', 'r') as f:
        for line in f:
            # [C2R-ACT-TX] FrameId=1, RtpTs=3405912258, CapNtpUs=3970678718677999
            match = re.search(r'\[C2R-ACT-TX\] FrameId=(\d+), RtpTs=(\d+), CapNtpUs=(\d+)', line)
            if match:
                frame_id, rtp_ts, cap_ntp_us = match.groups()
                sender_data[rtp_ts] = {
                    'frame_id': int(frame_id),
                    'rtp_ts': int(rtp_ts),
                    'capture_ntp_us': int(cap_ntp_us)
                }

    # 解析接收端数据 - 接收、组装、解码时间
    receiver_data = {}
    sr_data = []  # RTCP SR数据用于时钟同步

    with open('/home/wuq/webrtc-local/webrtc_config_results/receiver_cloud copy.log', 'r') as f:
        for line in f:
            # [C2R-ACT-RX] RtpTs=3405912258, SeqNum=16012, RxUs=4006113341026, ActCaptureUs=3970678718677999
            rx_match = re.search(r'\[C2R-ACT-RX\] RtpTs=(\d+).*RxUs=(\d+), ActCaptureUs=(\d+)', line)
            if rx_match:
                rtp_ts, rx_us, act_cap_us = rx_match.groups()
                if rtp_ts not in receiver_data:
                    receiver_data[rtp_ts] = {}
                receiver_data[rtp_ts].update({
                    'rtp_ts': int(rtp_ts),
                    'rx_us': int(rx_us),
                    'act_capture_us': int(act_cap_us)
                })

            # [C2R-E2E-ASSEMBLED] RtpTs=3405912258, ASSEMBLEDUs=4006113342506
            assembled_match = re.search(r'\[C2R-E2E-ASSEMBLED\] RtpTs=(\d+).*ASSEMBLEDUs=(\d+)', line)
            if assembled_match:
                rtp_ts, assembled_us = assembled_match.groups()
                if rtp_ts not in receiver_data:
                    receiver_data[rtp_ts] = {}
                receiver_data[rtp_ts]['assembled_us'] = int(assembled_us)

            # [C2R-E2E-DECODED] RtpTs=3405912258, DECODEDUs=4006113386367
            decoded_match = re.search(r'\[C2R-E2E-DECODED\] RtpTs=(\d+).*DECODEDUs=(\d+)', line)
            if decoded_match:
                rtp_ts, decoded_us = decoded_match.groups()
                if rtp_ts not in receiver_data:
                    receiver_data[rtp_ts] = {}
                receiver_data[rtp_ts]['decoded_us'] = int(decoded_us)

            # [C2R-SR-RX] MonoUs=4006113833935, SrNtpUs=3970678719187725, RtpTs=3405957978
            sr_match = re.search(r'\[C2R-SR-RX\] MonoUs=(\d+), SrNtpUs=(\d+), RtpTs=(\d+)', line)
            if sr_match:
                mono_us, sr_ntp_us, rtp_ts = sr_match.groups()
                sr_data.append({
                    'receiver_mono_us': int(mono_us),
                    'sender_ntp_us': int(sr_ntp_us),
                    'rtp_ts': int(rtp_ts)
                })

    return sender_data, receiver_data, sr_data

def calculate_clock_offset(sr_data):
    """使用RTCP SR数据计算时钟偏移"""
    if len(sr_data) < 2:
        print("警告: RTCP SR数据不足，无法精确计算时钟偏移")
        return None

    # 使用多个SR报文计算平均时钟偏移
    offsets = []
    for sr in sr_data:
        # 接收端单调时间 vs 发送端NTP时间的偏移
        offset = sr['receiver_mono_us'] - sr['sender_ntp_us']
        offsets.append(offset)

    avg_offset = sum(offsets) / len(offsets)
    print(f"时钟偏移分析:")
    print(f"  SR数据点数: {len(sr_data)}")
    print(f"  偏移范围: {min(offsets):,} ~ {max(offsets):,} 微秒")
    print(f"  平均偏移: {avg_offset:,.0f} 微秒 ({avg_offset/1000:.1f} 毫秒)")

    return avg_offset

def calculate_e2e_delay(sender_data, receiver_data, clock_offset):
    """计算端到端延迟"""
    results = []

    print("\n端到端延迟分析 (前10个样本):")
    print("RtpTs          网络延迟(ms)  组装延迟(ms)  解码延迟(ms)  总E2E延迟(ms)")
    print("-" * 80)

    count = 0
    for rtp_ts in sorted(sender_data.keys()):
        if rtp_ts in receiver_data and count < 10:
            sender = sender_data[rtp_ts]
            receiver = receiver_data[rtp_ts]

            if all(key in receiver for key in ['rx_us', 'assembled_us', 'decoded_us']):
                # 校正时钟偏移后的发送端捕获时间
                corrected_capture_us = sender['capture_ntp_us'] + (clock_offset or 0)

                # 各阶段延迟计算
                network_delay_us = receiver['rx_us'] - corrected_capture_us
                assembly_delay_us = receiver['assembled_us'] - receiver['rx_us']
                decode_delay_us = receiver['decoded_us'] - receiver['assembled_us']
                total_e2e_delay_us = receiver['decoded_us'] - corrected_capture_us

                # 转换为毫秒
                network_delay_ms = network_delay_us / 1000
                assembly_delay_ms = assembly_delay_us / 1000
                decode_delay_ms = decode_delay_us / 1000
                total_e2e_delay_ms = total_e2e_delay_us / 1000

                print(f"{rtp_ts:<12} {network_delay_ms:>10.2f}  {assembly_delay_ms:>10.2f}  {decode_delay_ms:>10.2f}  {total_e2e_delay_ms:>12.2f}")

                results.append({
                    'rtp_ts': rtp_ts,
                    'network_delay_ms': network_delay_ms,
                    'assembly_delay_ms': assembly_delay_ms,
                    'decode_delay_ms': decode_delay_ms,
                    'total_e2e_delay_ms': total_e2e_delay_ms
                })
                count += 1

    return results

def analyze_delay_statistics(results):
    """分析延迟统计信息"""
    if not results:
        print("没有有效的延迟数据")
        return

    network_delays = [r['network_delay_ms'] for r in results]
    assembly_delays = [r['assembly_delay_ms'] for r in results]
    decode_delays = [r['decode_delay_ms'] for r in results]
    total_delays = [r['total_e2e_delay_ms'] for r in results]

    print(f"\n延迟统计信息 (基于{len(results)}个样本):")
    print("类型          平均值(ms)   最小值(ms)   最大值(ms)   标准差(ms)")
    print("-" * 65)

    for name, delays in [
        ("网络延迟", network_delays),
        ("组装延迟", assembly_delays),
        ("解码延迟", decode_delays),
        ("总E2E延迟", total_delays)
    ]:
        avg = sum(delays) / len(delays)
        min_val = min(delays)
        max_val = max(delays)
        std_dev = math.sqrt(sum((x - avg) ** 2 for x in delays) / len(delays))

        print(f"{name:<8} {avg:>10.2f}   {min_val:>10.2f}   {max_val:>10.2f}   {std_dev:>10.2f}")

def main():
    print("解析WebRTC C2R日志，计算端到端延迟...")

    # 解析日志数据
    sender_data, receiver_data, sr_data = parse_logs()

    print(f"\n日志解析结果:")
    print(f"发送端数据: {len(sender_data)} 个ACT传输记录")
    print(f"接收端数据: {len(receiver_data)} 个接收记录")
    print(f"RTCP SR数据: {len(sr_data)} 个同步点")

    # 计算时钟偏移
    clock_offset = calculate_clock_offset(sr_data)

    if clock_offset is None:
        print("\n使用默认时钟偏移估算...")
        # 使用接收端显示的相对延迟作为粗略估算
        clock_offset = 35434566000000  # 约35434秒的偏移

    # 计算端到端延迟
    results = calculate_e2e_delay(sender_data, receiver_data, clock_offset)

    # 统计分析
    analyze_delay_statistics(results)

if __name__ == "__main__":
    main()
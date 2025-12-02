#!/usr/bin/env python3
"""
分析发送端日志中的处理延迟 (Processing Delay)
处理延迟 = 编码完成时间 - 帧捕获时间
"""
import re

log_file = "webrtc_config_results/sender_local.log"

# 存储捕获和编码数据
captures = []  # (MonoUs, CaptureNtpUs)
enc_dones = []  # (MonoUs, EncodeUs)
processing_delays = []

print("📊 分析发送端处理延迟 (Processing Delay)")
print("=" * 70)

with open(log_file, 'r') as f:
    for line in f:
        # 提取 CAPTURE 时间
        capture_match = re.search(r'\[C2R-CAPTURE\].*?MonoUs=(\d+).*?CaptureNtpUs=(\d+)', line)
        if capture_match:
            mono_us = int(capture_match.group(1))
            ntp_us = int(capture_match.group(2))
            captures.append((mono_us, ntp_us))

        # 提取 ENC-DONE 时间
        enc_match = re.search(r'\[C2R-ENC-DONE\].*?MonoUs=(\d+).*?EncodeUs=(\d+)', line)
        if enc_match:
            mono_us = int(enc_match.group(1))
            encode_us = int(enc_match.group(2))
            enc_dones.append((mono_us, encode_us))

print(f"📥 捕获的帧数 (CAPTURE): {len(captures)}")
print(f"✅ 编码完成的帧数 (ENC-DONE): {len(enc_dones)}")
print()

# 匹配 CAPTURE 和 ENC-DONE，计算处理延迟
# 对于每个 ENC-DONE，找到时间上最近的 CAPTURE
for enc_mono, encode_time in enc_dones:
    # 找到小于等于 enc_mono 的最近的 capture
    matching_capture = None
    for cap_mono, cap_ntp in captures:
        if cap_mono <= enc_mono:
            matching_capture = cap_mono
        else:
            break  # captures 按时间排序

    if matching_capture:
        processing_delay_us = enc_mono - matching_capture
        processing_delay_ms = processing_delay_us / 1000.0
        processing_delays.append(processing_delay_ms)

# 统计分析
if processing_delays:
    avg_delay = sum(processing_delays) / len(processing_delays)
    min_delay = min(processing_delays)
    max_delay = max(processing_delays)

    # 计算百分位数
    sorted_delays = sorted(processing_delays)
    p50_idx = int(len(sorted_delays) * 0.50)
    p95_idx = int(len(sorted_delays) * 0.95)
    p99_idx = int(len(sorted_delays) * 0.99)

    p50 = sorted_delays[p50_idx] if p50_idx < len(sorted_delays) else sorted_delays[-1]
    p95 = sorted_delays[p95_idx] if p95_idx < len(sorted_delays) else sorted_delays[-1]
    p99 = sorted_delays[p99_idx] if p99_idx < len(sorted_delays) else sorted_delays[-1]

    print("📈 处理延迟统计 (Processing Delay = ENC-DONE - CAPTURE):")
    print(f"  平均值: {avg_delay:.3f} ms")
    print(f"  最小值: {min_delay:.3f} ms")
    print(f"  最大值: {max_delay:.3f} ms")
    print(f"  P50中位数: {p50:.3f} ms")
    print(f"  P95: {p95:.3f} ms")
    print(f"  P99: {p99:.3f} ms")
    print()

    # 计算超过特定阈值的帧数
    threshold_33ms = sum(1 for d in processing_delays if d > 33)
    threshold_50ms = sum(1 for d in processing_delays if d > 50)
    threshold_100ms = sum(1 for d in processing_delays if d > 100)

    print("⏱️  超时帧数统计:")
    print(f"  > 33ms (一帧时间@30fps): {threshold_33ms} ({threshold_33ms*100.0/len(processing_delays):.1f}%)")
    print(f"  > 50ms: {threshold_50ms} ({threshold_50ms*100.0/len(processing_delays):.1f}%)")
    print(f"  > 100ms: {threshold_100ms} ({threshold_100ms*100.0/len(processing_delays):.1f}%)")
    print()

    # 分析处理延迟的构成
    # 提取编码时间
    encoding_times = [enc_time / 1000.0 for _, enc_time in enc_dones]
    avg_encoding = sum(encoding_times) / len(encoding_times)

    # 前处理时间 = 处理延迟 - 编码时间
    pre_encoding_delays = [processing_delays[i] - encoding_times[i]
                           for i in range(min(len(processing_delays), len(encoding_times)))]
    avg_pre_encoding = sum(pre_encoding_delays) / len(pre_encoding_delays)

    print("🔍 处理延迟构成分析:")
    print(f"  处理延迟 = 前处理延迟 + 编码时间")
    print(f"  平均处理延迟: {avg_delay:.3f} ms")
    print(f"    ├─ 前处理延迟 (帧队列+预处理): {avg_pre_encoding:.3f} ms ({avg_pre_encoding*100/avg_delay:.1f}%)")
    print(f"    └─ 编码时间 (H.264): {avg_encoding:.3f} ms ({avg_encoding*100/avg_delay:.1f}%)")
    print()

    print("💡 说明:")
    print("  - 处理延迟 (Processing Delay): 从帧捕获到编码完成的总时间")
    print("  - 前处理延迟: 包括帧在编码队列中的等待时间、帧预处理时间等")
    print("  - 编码时间: H.264编码器实际编码耗时")

else:
    print("❌ 未找到匹配的处理延迟数据")

#!/usr/bin/env python3
"""
分析WebRTC发送端的编码统计信息
"""

import re
import statistics

def analyze_encoding_stats(log_file):
    # 匹配 C2R-ENC-DONE 日志行
    pattern = r'\[C2R-ENC-DONE\] FrameId=(\d+), MonoUs=(\d+), EncodeUs=(\d+)'

    encode_times = []
    frame_count = 0

    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            match = re.search(pattern, line)
            if match:
                frame_id = int(match.group(1))
                mono_us = int(match.group(2))
                encode_us = int(match.group(3))
                encode_times.append(encode_us)
                frame_count += 1

    if not encode_times:
        print("未找到编码数据")
        return

    # 转换为毫秒
    encode_times_ms = [t / 1000.0 for t in encode_times]

    # 统计分析
    total_frames = len(encode_times_ms)
    min_time = min(encode_times_ms)
    max_time = max(encode_times_ms)
    avg_time = statistics.mean(encode_times_ms)
    median_time = statistics.median(encode_times_ms)

    if total_frames > 1:
        stdev_time = statistics.stdev(encode_times_ms)
    else:
        stdev_time = 0

    # 计算百分位数
    sorted_times = sorted(encode_times_ms)
    p50 = sorted_times[int(total_frames * 0.50)]
    p90 = sorted_times[int(total_frames * 0.90)]
    p95 = sorted_times[int(total_frames * 0.95)]
    p99 = sorted_times[int(total_frames * 0.99)]

    # 计算帧率相关信息
    target_fps = 30
    frame_interval_ms = 1000.0 / target_fps  # 33.33ms

    # 统计编码时间分布
    buckets = {
        '< 10ms': 0,
        '10-20ms': 0,
        '20-30ms': 0,
        '30-40ms': 0,
        '40-50ms': 0,
        '> 50ms': 0
    }

    for t in encode_times_ms:
        if t < 10:
            buckets['< 10ms'] += 1
        elif t < 20:
            buckets['10-20ms'] += 1
        elif t < 30:
            buckets['20-30ms'] += 1
        elif t < 40:
            buckets['30-40ms'] += 1
        elif t < 50:
            buckets['40-50ms'] += 1
        else:
            buckets['> 50ms'] += 1

    # 输出统计结果
    print("=" * 70)
    print("WebRTC 发送端编码统计分析")
    print("=" * 70)
    print(f"\n总帧数: {total_frames:,}")
    print(f"\n编码时间统计 (单位: 毫秒):")
    print(f"  最小值:      {min_time:8.2f} ms")
    print(f"  最大值:      {max_time:8.2f} ms")
    print(f"  平均值:      {avg_time:8.2f} ms")
    print(f"  中位数:      {median_time:8.2f} ms")
    print(f"  标准差:      {stdev_time:8.2f} ms")

    print(f"\n百分位数:")
    print(f"  P50 (中位数): {p50:7.2f} ms")
    print(f"  P90:          {p90:7.2f} ms")
    print(f"  P95:          {p95:7.2f} ms")
    print(f"  P99:          {p99:7.2f} ms")

    print(f"\n编码时间分布:")
    for bucket, count in buckets.items():
        percentage = (count / total_frames) * 100
        bar = '#' * int(percentage / 2)
        print(f"  {bucket:12s}: {count:6,} ({percentage:5.1f}%) {bar}")

    print(f"\n性能分析:")
    print(f"  目标帧率:           {target_fps} FPS")
    print(f"  目标帧间隔:         {frame_interval_ms:.2f} ms")
    print(f"  平均编码时间占比:   {(avg_time / frame_interval_ms) * 100:.1f}%")

    # 检查是否有编码时间超过帧间隔的情况
    slow_frames = sum(1 for t in encode_times_ms if t > frame_interval_ms)
    if slow_frames > 0:
        print(f"  ⚠️  编码时间超过帧间隔的帧数: {slow_frames} ({(slow_frames/total_frames)*100:.1f}%)")
    else:
        print(f"  ✅ 所有帧编码时间都在目标帧间隔内")

    # 计算编码吞吐量
    total_encode_time_s = sum(encode_times_ms) / 1000.0
    print(f"\n编码吞吐量:")
    print(f"  总编码时间:         {total_encode_time_s:.2f} 秒")
    print(f"  实际处理帧率:       {total_frames / total_encode_time_s:.2f} FPS (理论最大)")

    print("\n" + "=" * 70)

if __name__ == "__main__":
    log_file = "/home/qwu26/webrtc-local/webrtc_config_results/sender_local.log"
    analyze_encoding_stats(log_file)

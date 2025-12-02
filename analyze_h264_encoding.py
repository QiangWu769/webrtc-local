#!/usr/bin/env python3
"""
分析H.264编码的分辨率持续时间和编码延迟
"""

import re
import sys
from collections import defaultdict
from datetime import datetime

def parse_timestamp(line):
    """提取日志时间戳（毫秒）"""
    # 格式: (timestamp_ms)
    match = re.search(r'\((\d+)\)', line)
    if match:
        return int(match.group(1))
    return None

def parse_h264_log(log_file):
    """解析H.264日志，提取分辨率和编码时间"""

    results = {
        'resolution_timeline': [],  # (timestamp_ms, resolution)
        'encode_times': [],  # (timestamp_ms, resolution, encode_time_ms)
        'frame_info': [],  # 帧信息
    }

    current_resolution = None
    last_timestamp = None

    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            timestamp = parse_timestamp(line)

            # 检测分辨率变化
            res_match = re.search(r'(?:SetResolution|resolution|encoder.*?size|input.*?size|UpdateInputSize).*?(\d{3,4})\s*[x×]\s*(\d{3,4})', line, re.IGNORECASE)
            if res_match:
                width = int(res_match.group(1))
                height = int(res_match.group(2))
                resolution = f"{width}×{height}"

                if resolution != current_resolution:
                    if timestamp:
                        results['resolution_timeline'].append((timestamp, resolution))
                    current_resolution = resolution

            # 检测编码时间
            # 各种可能的模式
            encode_patterns = [
                r'encode.*?time.*?(\d+\.?\d*)\s*ms',
                r'encoding.*?took.*?(\d+\.?\d*)\s*ms',
                r'H264.*?encode.*?(\d+\.?\d*)\s*ms',
                r'OpenH264.*?encode.*?(\d+\.?\d*)\s*ms',
                r'frame.*?encoded.*?(\d+\.?\d*)\s*ms',
            ]

            for pattern in encode_patterns:
                encode_match = re.search(pattern, line, re.IGNORECASE)
                if encode_match and timestamp and current_resolution:
                    encode_time = float(encode_match.group(1))
                    if 0 < encode_time < 1000:  # 合理范围
                        results['encode_times'].append((timestamp, current_resolution, encode_time))
                    break

            # 检测编码帧信息
            if 'encode' in line.lower() and 'frame' in line.lower():
                if timestamp and current_resolution:
                    # 提取帧大小
                    size_match = re.search(r'(\d+)\s*bytes', line, re.IGNORECASE)
                    if size_match:
                        frame_size = int(size_match.group(1))
                        results['frame_info'].append({
                            'timestamp': timestamp,
                            'resolution': current_resolution,
                            'frame_size': frame_size,
                        })

    return results

def calculate_resolution_durations(timeline):
    """计算每个分辨率的持续时间"""
    if not timeline:
        return {}

    durations = defaultdict(float)

    for i in range(len(timeline) - 1):
        timestamp, resolution = timeline[i]
        next_timestamp, _ = timeline[i + 1]
        duration_ms = next_timestamp - timestamp
        durations[resolution] += duration_ms

    # 最后一个分辨率（假设持续到日志结束）
    if len(timeline) > 0:
        # 可以假设持续一段时间，或者从其他指标推断
        pass

    return durations

def analyze_encode_times(encode_times):
    """分析编码延迟"""
    if not encode_times:
        return {}

    by_resolution = defaultdict(list)

    for timestamp, resolution, encode_time in encode_times:
        by_resolution[resolution].append(encode_time)

    stats = {}
    for resolution, times in by_resolution.items():
        if not times:
            continue

        times_sorted = sorted(times)
        count = len(times)

        stats[resolution] = {
            'count': count,
            'min': min(times),
            'max': max(times),
            'avg': sum(times) / count,
            'median': times_sorted[count // 2],
            'p90': times_sorted[int(count * 0.9)] if count > 10 else times_sorted[-1],
            'p95': times_sorted[int(count * 0.95)] if count > 20 else times_sorted[-1],
            'p99': times_sorted[int(count * 0.99)] if count > 100 else times_sorted[-1],
        }

    return stats

def print_report(results):
    """打印分析报告"""
    print("=" * 80)
    print("📊 H.264/OpenH264 编码分析报告")
    print("=" * 80)
    print()

    # 分辨率时间线
    print("## 🎬 分辨率切换时间线")
    print()

    if results['resolution_timeline']:
        print(f"  总切换次数: {len(results['resolution_timeline'])}")
        print()
        print("  时间线（前20次）:")

        for i, (timestamp, resolution) in enumerate(results['resolution_timeline'][:20], 1):
            time_sec = timestamp / 1000.0
            print(f"    {i:2d}. {time_sec:10.3f}s - {resolution}")

        if len(results['resolution_timeline']) > 20:
            print(f"    ... (还有 {len(results['resolution_timeline']) - 20} 次)")
    else:
        print("  ⚠️  未检测到分辨率切换信息")
    print()

    # 分辨率持续时间
    print("## ⏱️  分辨率持续时间")
    print()

    durations = calculate_resolution_durations(results['resolution_timeline'])
    if durations:
        total_duration = sum(durations.values())

        print(f"  总持续时间: {total_duration/1000:.2f} 秒")
        print()
        print("  各分辨率持续时间:")

        for resolution, duration_ms in sorted(durations.items(), key=lambda x: x[1], reverse=True):
            duration_sec = duration_ms / 1000.0
            percentage = (duration_ms / total_duration) * 100 if total_duration > 0 else 0
            bar_length = int(percentage / 2)
            bar = "█" * bar_length
            print(f"    {resolution:12s}: {duration_sec:8.2f}s ({percentage:5.1f}%) {bar}")
    else:
        print("  ⚠️  无法计算持续时间（需要至少2个分辨率切换点）")
    print()

    # 编码延迟分析
    print("## ⚡ 编码延迟分析")
    print()

    encode_stats = analyze_encode_times(results['encode_times'])

    if encode_stats:
        print(f"  总编码时间采样数: {sum(s['count'] for s in encode_stats.values())}")
        print()

        # 表格头
        print("  " + "─" * 76)
        print(f"  {'分辨率':<12s} {'采样数':>6s} {'平均':>8s} {'中位数':>8s} {'P90':>8s} {'P95':>8s} {'最小':>8s} {'最大':>8s}")
        print("  " + "─" * 76)

        # 按分辨率排序（从高到低）
        def resolution_sort_key(res):
            match = re.match(r'(\d+)×(\d+)', res)
            if match:
                return int(match.group(1)) * int(match.group(2))
            return 0

        for resolution in sorted(encode_stats.keys(), key=resolution_sort_key, reverse=True):
            stats = encode_stats[resolution]
            print(f"  {resolution:<12s} {stats['count']:>6d} {stats['avg']:>7.2f}ms {stats['median']:>7.2f}ms "
                  f"{stats['p90']:>7.2f}ms {stats['p95']:>7.2f}ms {stats['min']:>7.2f}ms {stats['max']:>7.2f}ms")

        print("  " + "─" * 76)
        print()

        # 性能评估
        print("  性能评估（30 FPS目标，帧间隔33.33ms）:")
        print()

        for resolution in sorted(encode_stats.keys(), key=resolution_sort_key, reverse=True):
            stats = encode_stats[resolution]
            avg_time = stats['avg']
            frame_interval = 33.33
            utilization = (avg_time / frame_interval) * 100
            margin = frame_interval - avg_time

            if avg_time < frame_interval:
                status = "✅ 充足"
                emoji = "✅"
            else:
                status = "❌ 不足"
                emoji = "❌"

            print(f"    {resolution:12s}: {avg_time:6.2f}ms ({utilization:5.1f}%占用) "
                  f"- {emoji} {status} (余量: {margin:+6.2f}ms)")

        print()

        # 编码效率对比
        print("  编码效率对比（每百万像素编码时间）:")
        print()

        for resolution in sorted(encode_stats.keys(), key=resolution_sort_key, reverse=True):
            stats = encode_stats[resolution]
            match = re.match(r'(\d+)×(\d+)', resolution)
            if match:
                width = int(match.group(1))
                height = int(match.group(2))
                pixels = width * height
                megapixels = pixels / 1_000_000
                time_per_megapixel = stats['avg'] / megapixels

                print(f"    {resolution:12s}: {time_per_megapixel:7.2f} ms/MP "
                      f"(像素: {pixels:,}, 平均: {stats['avg']:.2f}ms)")
    else:
        print("  ⚠️  未检测到编码延迟信息")
        print()
        print("  可能原因:")
        print("  - 日志中没有编码时间相关的输出")
        print("  - 需要在代码中添加编码时间日志")
        print()
        print("  建议添加日志（在H.264编码器中）:")
        print("  ```cpp")
        print("  int64_t start_time = rtc::TimeMillis();")
        print("  // ... encoding ...")
        print("  int64_t encode_time = rtc::TimeMillis() - start_time;")
        print("  RTC_LOG(LS_INFO) << \"H264 encode time: \" << encode_time << \"ms\";")
        print("  ```")
    print()

    # 帧大小分析
    if results['frame_info']:
        print("## 📦 编码帧大小分析")
        print()

        by_resolution = defaultdict(list)
        for info in results['frame_info']:
            by_resolution[info['resolution']].append(info['frame_size'])

        if by_resolution:
            print("  各分辨率平均帧大小:")
            print()

            for resolution in sorted(by_resolution.keys(), key=resolution_sort_key, reverse=True):
                sizes = by_resolution[resolution]
                avg_size = sum(sizes) / len(sizes)
                min_size = min(sizes)
                max_size = max(sizes)

                print(f"    {resolution:12s}: 平均 {avg_size/1024:7.2f}KB "
                      f"(最小: {min_size/1024:6.2f}KB, 最大: {max_size/1024:6.2f}KB, "
                      f"样本: {len(sizes)})")
        print()

def main():
    log_file = sys.argv[1] if len(sys.argv) > 1 else 'webrtc_config_results/sender_local.log'

    try:
        results = parse_h264_log(log_file)
        print_report(results)
    except FileNotFoundError:
        print(f"❌ 错误: 找不到日志文件 {log_file}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 分析过程中出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()

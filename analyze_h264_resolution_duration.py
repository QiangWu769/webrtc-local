#!/usr/bin/env python3
"""
分析H.264编码的分辨率持续时间（基于帧数）
"""

import re
import sys

def parse_resolution_timeline(log_file):
    """从日志中解析分辨率时间线"""

    timeline = []

    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            # 查找分辨率变化和帧编号
            if 'Frame size changed' in line or 'Video frame parameters changed' in line:
                # 提取分辨率
                res_match = re.search(r'dimensions=(\d+)x(\d+)', line)
                # 提取输出帧编号
                frame_match = re.search(r'out (\d+)', line)

                if res_match:
                    width = int(res_match.group(1))
                    height = int(res_match.group(2))
                    resolution = f"{width}×{height}"
                    frame_num = int(frame_match.group(1)) if frame_match else None

                    timeline.append({
                        'resolution': resolution,
                        'frame_num': frame_num,
                        'width': width,
                        'height': height,
                    })

    return timeline

def analyze_durations(timeline, fps=30):
    """分析每个分辨率的持续时间"""

    if len(timeline) < 2:
        return None

    durations = []

    for i in range(len(timeline) - 1):
        current = timeline[i]
        next_item = timeline[i + 1]

        if current['frame_num'] is not None and next_item['frame_num'] is not None:
            frame_count = next_item['frame_num'] - current['frame_num']
            duration_sec = frame_count / fps

            durations.append({
                'resolution': current['resolution'],
                'start_frame': current['frame_num'],
                'end_frame': next_item['frame_num'],
                'frame_count': frame_count,
                'duration_sec': duration_sec,
                'pixels': current['width'] * current['height'],
            })

    return durations

def print_report(timeline, durations, fps=30):
    """打印分析报告"""

    print("=" * 80)
    print("📊 H.264/OpenH264 分辨率持续时间分析")
    print("=" * 80)
    print()

    # 基本信息
    print("## 📋 基本信息")
    print()
    print(f"  帧率: {fps} FPS")
    print(f"  分辨率切换次数: {len(timeline)}")
    print()

    # 分辨率时间线
    print("## 🎬 分辨率切换时间线")
    print()

    if timeline:
        print("  序号  帧编号    分辨率        像素数")
        print("  " + "─" * 50)

        for i, item in enumerate(timeline, 1):
            frame_str = f"{item['frame_num']:5d}" if item['frame_num'] is not None else "  N/A"
            pixels = f"{item['width'] * item['height']:,}"
            print(f"  {i:2d}.  {frame_str}    {item['resolution']:12s}  {pixels:>10s}")

        print("  " + "─" * 50)
    else:
        print("  ⚠️  未检测到分辨率切换")

    print()

    # 持续时间分析
    if durations:
        print("## ⏱️  分辨率持续时间详细")
        print()

        total_frames = sum(d['frame_count'] for d in durations)
        total_duration = total_frames / fps

        print(f"  总帧数: {total_frames}")
        print(f"  总时长: {total_duration:.2f} 秒")
        print()

        print("  分辨率        帧数范围          帧数    持续时间    占比")
        print("  " + "─" * 70)

        for d in durations:
            percentage = (d['duration_sec'] / total_duration * 100) if total_duration > 0 else 0
            bar_length = int(percentage / 2)
            bar = "█" * bar_length

            print(f"  {d['resolution']:12s}  {d['start_frame']:5d} → {d['end_frame']:5d}  "
                  f"{d['frame_count']:6d}  {d['duration_sec']:8.2f}s  {percentage:5.1f}% {bar}")

        print("  " + "─" * 70)
        print()

        # 按分辨率汇总
        print("## 📊 按分辨率汇总")
        print()

        from collections import defaultdict
        summary = defaultdict(lambda: {'frame_count': 0, 'duration_sec': 0, 'occurrences': 0})

        for d in durations:
            summary[d['resolution']]['frame_count'] += d['frame_count']
            summary[d['resolution']]['duration_sec'] += d['duration_sec']
            summary[d['resolution']]['occurrences'] += 1
            summary[d['resolution']]['pixels'] = d['pixels']

        # 按总时长排序
        sorted_summary = sorted(summary.items(), key=lambda x: x[1]['duration_sec'], reverse=True)

        print("  分辨率        总帧数    总时长      占比     出现次数   像素数")
        print("  " + "─" * 75)

        for resolution, stats in sorted_summary:
            percentage = (stats['duration_sec'] / total_duration * 100) if total_duration > 0 else 0
            pixels_str = f"{stats['pixels']:,}"

            print(f"  {resolution:12s}  {stats['frame_count']:6d}  {stats['duration_sec']:8.2f}s  "
                  f"{percentage:5.1f}%    {stats['occurrences']:4d}      {pixels_str:>10s}")

        print("  " + "─" * 75)
        print()

        # 性能分析
        print("## ⚡ 性能分析（假设30 FPS）")
        print()

        print("  分辨率        像素数        理论编码时间  实际可用时间  状态")
        print("  " + "─" * 70)

        frame_interval_ms = 1000.0 / fps

        for resolution, stats in sorted_summary:
            pixels = stats['pixels']

            # 基于之前分析的编码时间估算
            # 1080p: 16.82ms, 720p: 11.04ms, 540p: 8.81ms, 360p: 4.16ms
            # 使用线性插值估算
            if pixels >= 2_073_600:  # 1920x1080
                estimated_time = 16.82
            elif pixels >= 921_600:  # 1280x720
                estimated_time = 11.04
            elif pixels >= 518_400:  # 960x540
                estimated_time = 8.81
            else:  # 640x360
                estimated_time = 4.16

            available_time = frame_interval_ms - estimated_time
            utilization = (estimated_time / frame_interval_ms) * 100

            if estimated_time < frame_interval_ms:
                status = f"✅ 充足 ({utilization:.1f}%占用)"
            else:
                status = f"❌ 不足 ({utilization:.1f}%占用)"

            pixels_str = f"{pixels:,}"

            print(f"  {resolution:12s}  {pixels_str:>10s}  {estimated_time:8.2f}ms  "
                  f"{frame_interval_ms:8.2f}ms  {status}")

        print("  " + "─" * 70)
        print()

        # 稳定性分析
        print("## 📈 稳定性分析")
        print()

        # 计算平均每次持续多少帧
        for resolution, stats in sorted_summary:
            avg_duration_per_occurrence = stats['duration_sec'] / stats['occurrences']
            avg_frames_per_occurrence = stats['frame_count'] / stats['occurrences']

            print(f"  {resolution:12s}:")
            print(f"    出现次数: {stats['occurrences']}")
            print(f"    平均每次持续: {avg_duration_per_occurrence:.2f}s ({avg_frames_per_occurrence:.0f} 帧)")

            if stats['occurrences'] == 1:
                print(f"    稳定性: ✅ 优秀（仅出现1次，未切换）")
            elif stats['occurrences'] <= 3:
                print(f"    稳定性: ✅ 良好（切换较少）")
            elif stats['occurrences'] <= 5:
                print(f"    稳定性: ⚠️  中等（有一定切换）")
            else:
                print(f"    稳定性: ❌ 较差（频繁切换）")
            print()

        # 切换频率
        if len(timeline) > 1 and total_duration > 0:
            switch_frequency = (len(timeline) - 1) / total_duration
            print(f"  整体切换频率: {switch_frequency:.3f} 次/秒")
            print(f"  平均切换间隔: {1/switch_frequency:.2f} 秒")
            print()

            if switch_frequency < 0.1:
                print(f"  ✅ 稳定性评级: 优秀（切换很少）")
            elif switch_frequency < 0.5:
                print(f"  ✅ 稳定性评级: 良好")
            elif switch_frequency < 1.0:
                print(f"  ⚠️  稳定性评级: 中等")
            else:
                print(f"  ❌ 稳定性评级: 较差（频繁切换）")

    else:
        print("  ⚠️  无法计算持续时间（缺少帧编号信息）")

    print()

def main():
    log_file = sys.argv[1] if len(sys.argv) > 1 else 'webrtc_config_results/sender_local.log'
    fps = int(sys.argv[2]) if len(sys.argv) > 2 else 30

    try:
        timeline = parse_resolution_timeline(log_file)
        durations = analyze_durations(timeline, fps) if timeline else None
        print_report(timeline, durations, fps)
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

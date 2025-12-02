#!/usr/bin/env python3
"""
分析不同分辨率下的编码时间
"""

import re
import statistics
from collections import defaultdict

log_file = "/home/qwu26/webrtc-local/webrtc_config_results/sender_local.log"

# 解析日志
current_resolution = None
resolution_data = defaultdict(list)

with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
    for line in f:
        # 检测分辨率变化
        res_match = re.search(r'Video frame parameters changed: dimensions=(\d+)x(\d+)', line)
        if res_match:
            width, height = int(res_match.group(1)), int(res_match.group(2))
            current_resolution = f"{width}x{height}"
            print(f"检测到分辨率切换: {current_resolution}")
            continue

        # 提取编码时间
        enc_match = re.search(r'\[C2R-ENC-DONE\].*EncodeUs=(\d+)', line)
        if enc_match and current_resolution:
            encode_us = int(enc_match.group(1))
            encode_ms = encode_us / 1000.0
            resolution_data[current_resolution].append(encode_ms)

# 打印统计结果
print("\n" + "=" * 80)
print("不同分辨率的编码时间分析".center(80))
print("=" * 80)

# 计算每个分辨率的像素数
def get_pixel_count(resolution):
    width, height = map(int, resolution.split('x'))
    return width * height

# 按分辨率排序（从大到小）
sorted_resolutions = sorted(resolution_data.keys(),
                            key=lambda r: get_pixel_count(r),
                            reverse=True)

# 汇总表格
print("\n📊 编码时间汇总对比表\n")
print(f"{'分辨率':<12} {'像素总数':<12} {'样本数':<8} {'平均(ms)':<10} {'中位数(ms)':<11} {'最小(ms)':<10} {'最大(ms)':<10} {'标准差(ms)':<11}")
print("-" * 100)

for resolution in sorted_resolutions:
    times = resolution_data[resolution]
    if not times:
        continue

    width, height = map(int, resolution.split('x'))
    pixel_count = width * height

    avg_time = statistics.mean(times)
    median_time = statistics.median(times)
    min_time = min(times)
    max_time = max(times)
    stdev_time = statistics.stdev(times) if len(times) > 1 else 0

    print(f"{resolution:<12} {pixel_count:<12,} {len(times):<8,} {avg_time:<10.2f} {median_time:<11.2f} {min_time:<10.2f} {max_time:<10.2f} {stdev_time:<11.2f}")

# 详细分析每个分辨率
print("\n" + "=" * 80)
print("📈 各分辨率详细统计分析")
print("=" * 80)

for resolution in sorted_resolutions:
    times = resolution_data[resolution]
    if not times:
        continue

    width, height = map(int, resolution.split('x'))
    pixel_count = width * height

    print(f"\n{'━' * 80}")
    print(f"🎯 分辨率: {resolution} (像素总数: {pixel_count:,})")
    print(f"{'━' * 80}")

    avg_time = statistics.mean(times)
    median_time = statistics.median(times)
    min_time = min(times)
    max_time = max(times)
    stdev_time = statistics.stdev(times) if len(times) > 1 else 0

    print(f"\n基本统计:")
    print(f"  样本数量:     {len(times):,} 帧")
    print(f"  最小值:       {min_time:.2f} ms")
    print(f"  最大值:       {max_time:.2f} ms")
    print(f"  平均值:       {avg_time:.2f} ms")
    print(f"  中位数:       {median_time:.2f} ms")
    print(f"  标准差:       {stdev_time:.2f} ms")

    # 百分位数
    sorted_times = sorted(times)
    if len(sorted_times) >= 10:
        p90 = sorted_times[int(len(sorted_times) * 0.90)]
        p95 = sorted_times[int(len(sorted_times) * 0.95)]
        p99 = sorted_times[int(len(sorted_times) * 0.99)]
        print(f"\n百分位数:")
        print(f"  P90:          {p90:.2f} ms")
        print(f"  P95:          {p95:.2f} ms")
        print(f"  P99:          {p99:.2f} ms")

    # 编码时间分布
    print(f"\n编码时间分布:")
    buckets = [
        ('< 5ms', 0, 5),
        ('5-10ms', 5, 10),
        ('10-20ms', 10, 20),
        ('20-30ms', 20, 30),
        ('30-40ms', 30, 40),
        ('40-50ms', 40, 50),
        ('> 50ms', 50, float('inf'))
    ]

    total = len(times)
    for label, low, high in buckets:
        count = sum(1 for t in times if low <= t < high)
        pct = count / total * 100 if total > 0 else 0
        bar = '█' * int(pct / 2)
        print(f"  {label:12s}: {count:6,} ({pct:5.1f}%) {bar}")

    # 性能评估
    target_fps = 30
    frame_interval_ms = 1000.0 / target_fps

    print(f"\n性能评估:")
    print(f"  目标帧率:              {target_fps} FPS")
    print(f"  目标帧间隔:            {frame_interval_ms:.2f} ms")
    print(f"  编码时间占帧间隔:      {(avg_time / frame_interval_ms) * 100:.1f}%")

    slow_frames = sum(1 for t in times if t > frame_interval_ms)
    print(f"  编码超时帧数:          {slow_frames:,} ({slow_frames/total*100:.1f}%)")

    if avg_time > 0:
        max_fps = 1000.0 / avg_time
        print(f"  理论最大帧率:          {max_fps:.2f} FPS")

    # 稳定性分析
    if len(times) > 1:
        cv = (stdev_time / avg_time) * 100
        print(f"\n稳定性分析:")
        print(f"  变异系数 (CV):         {cv:.1f}%")
        if cv < 20:
            stability = "✅ 良好"
        elif cv < 40:
            stability = "⚠️  中等"
        else:
            stability = "❌ 较差"
        print(f"  稳定性评估:            {stability}")

# 分辨率对比分析
print("\n" + "=" * 80)
print("🔍 分辨率对比分析")
print("=" * 80)

if len(sorted_resolutions) >= 2:
    print(f"\n编码效率对比 (相对于最高分辨率 {sorted_resolutions[0]}):\n")

    base_resolution = sorted_resolutions[0]
    base_times = resolution_data[base_resolution]
    base_avg = statistics.mean(base_times)
    base_pixels = get_pixel_count(base_resolution)

    print(f"{'分辨率':<12} {'像素占比':<12} {'平均编码时间':<15} {'时间占比':<12} {'每百万像素耗时':<18} {'效率比':<10}")
    print("-" * 100)

    for resolution in sorted_resolutions:
        times = resolution_data[resolution]
        if not times:
            continue

        avg_time = statistics.mean(times)
        pixels = get_pixel_count(resolution)

        pixel_ratio = pixels / base_pixels * 100
        time_ratio = avg_time / base_avg * 100

        # 每百万像素的编码时间
        time_per_megapixel = avg_time / (pixels / 1_000_000)
        base_time_per_megapixel = base_avg / (base_pixels / 1_000_000)
        efficiency_ratio = time_per_megapixel / base_time_per_megapixel

        print(f"{resolution:<12} {pixel_ratio:<11.1f}% {avg_time:<14.2f}ms {time_ratio:<11.1f}% {time_per_megapixel:<17.2f}ms {efficiency_ratio:<10.2f}x")

# 关键发现
print("\n" + "=" * 80)
print("💡 关键发现与建议")
print("=" * 80)

print("\n1. 编码时间与分辨率的关系:")
for i, resolution in enumerate(sorted_resolutions):
    times = resolution_data[resolution]
    if not times:
        continue
    avg_time = statistics.mean(times)
    pixels = get_pixel_count(resolution)

    if i == 0:
        print(f"   • {resolution}: 基准分辨率，平均编码时间 {avg_time:.2f}ms")
    else:
        prev_resolution = sorted_resolutions[i-1]
        prev_times = resolution_data[prev_resolution]
        prev_avg = statistics.mean(prev_times)
        reduction = (1 - avg_time / prev_avg) * 100
        prev_pixels = get_pixel_count(prev_resolution)
        pixel_reduction = (1 - pixels / prev_pixels) * 100
        print(f"   • {resolution}: 编码时间减少 {reduction:.1f}% (像素减少 {pixel_reduction:.1f}%)")

print("\n2. 性能建议:")
for resolution in sorted_resolutions:
    times = resolution_data[resolution]
    if not times:
        continue
    avg_time = statistics.mean(times)
    target_interval = 1000.0 / 30  # 33.33ms for 30 FPS

    if avg_time < target_interval * 0.7:
        status = "✅ 性能充足，可以考虑提高质量参数"
    elif avg_time < target_interval:
        status = "✅ 性能良好，能够稳定支持30 FPS"
    elif avg_time < target_interval * 1.2:
        status = "⚠️  性能一般，可能偶尔掉帧"
    else:
        status = "❌ 性能不足，无法稳定支持30 FPS"

    print(f"   • {resolution}: {status}")

print("\n" + "=" * 80)

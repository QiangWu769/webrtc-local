#!/usr/bin/env python3

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def analyze_tti_pattern():
    """分析TTI模式，正确处理多次循环"""

    # 读取数据
    data = []
    with open('/home/wuq/webrtc-local/logcode/ratio_data.txt', 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if line:
                parts = line.split('\t')
                if len(parts) == 4:
                    tti = int(parts[0])
                    allocated = int(parts[1])
                    requested = int(parts[2])
                    ratio = float(parts[3])
                    data.append((line_num, tti, allocated, requested, ratio))

    print(f"Total data points: {len(data)}")

    # 分析TTI跳跃模式
    print("\nTTI wrap-around detection:")
    wrap_points = []

    for i in range(1, min(100, len(data))):
        prev_tti = data[i-1][1]
        curr_tti = data[i][1]

        # 检测大幅后退（wrap-around）
        if curr_tti < prev_tti - 5000:
            wrap_points.append(i)
            print(f"  Line {i}: TTI {prev_tti} -> {curr_tti} (wrap-around)")
        # 检测大幅前进（可能的数据跳跃）
        elif curr_tti > prev_tti + 1000:
            print(f"  Line {i}: TTI {prev_tti} -> {curr_tti} (big jump)")

    return data, wrap_points

def convert_tti_to_continuous_time(data):
    """正确转换TTI到连续时间，处理多次循环"""

    continuous_times = []
    offset = 0
    prev_tti = data[0][1]  # 第一个TTI

    for line_num, tti, allocated, requested, ratio in data:
        # 检测wrap-around：当前TTI比前一个小很多
        if tti < prev_tti - 5000:
            offset += 10240  # 增加一个完整周期
            print(f"Wrap detected at line {line_num}: TTI {prev_tti} -> {tti}, new offset: {offset}")

        # 计算连续时间
        continuous_tti = tti + offset
        time_seconds = continuous_tti * 0.001  # TTI是毫秒

        continuous_times.append((line_num, time_seconds, tti, allocated, requested, ratio))
        prev_tti = tti

    return continuous_times

def plot_full_timeline():
    """绘制完整时间线的ratio"""

    print("Analyzing TTI pattern...")
    data, wrap_points = analyze_tti_pattern()

    print("\nConverting to continuous time...")
    continuous_data = convert_tti_to_continuous_time(data)

    # 提取数据
    line_nums, times, ttis, allocated, requested, ratios = zip(*continuous_data)

    print(f"\nTime range: {min(times):.3f} to {max(times):.3f} seconds")
    print(f"Total duration: {max(times) - min(times):.3f} seconds")

    # 绘图
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10))

    # 上图：原始ratio
    ax1.plot(times, ratios, color='#2E86AB', linewidth=1, alpha=0.7, label='Original Ratio')
    ax1.axhline(y=1.0, color='red', linestyle=':', alpha=0.6, label='Ratio = 1.0')
    ax1.axhline(y=0.5, color='orange', linestyle=':', alpha=0.6, label='Ratio = 0.5')
    ax1.set_ylabel('Cellular Ratio', fontsize=12)
    ax1.set_title('Full Timeline: Original Cellular Ratio', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    ax1.set_ylim(0, max(5, np.percentile(ratios, 95)))

    # 下图：TTI值显示wrap-around
    ax2.plot(times, ttis, color='green', linewidth=1, alpha=0.7)
    ax2.set_xlabel('Time (seconds)', fontsize=12)
    ax2.set_ylabel('TTI Value', fontsize=12)
    ax2.set_title('TTI Values Over Time (showing wrap-arounds)', fontsize=14)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('/home/wuq/webrtc-local/logcode/full_timeline_ratio.png', dpi=300, bbox_inches='tight')
    print(f"[*] Plot saved to: full_timeline_ratio.png")

    plt.show()

if __name__ == "__main__":
    plot_full_timeline()
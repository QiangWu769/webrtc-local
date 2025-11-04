#!/usr/bin/env python3
"""
分析平滑后的cellular ratio和带宽之间的关系
"""

import re
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
from collections import defaultdict

def parse_log_file(log_path):
    """解析日志文件，提取ratio、saturation和带宽信息"""

    # 存储数据
    ratio_data = []  # (timestamp, ratio, saturation)
    bandwidth_data = []  # (timestamp, bandwidth_bps, type)

    with open(log_path, 'r') as f:
        for line in f:
            # 提取CellularRatio数据
            # 格式: [CellularRatio] MonoTime: 488494747 ms, Ratio: 1.22172, Saturation: 0.870691, Influence: disabled
            ratio_match = re.search(r'\[CellularRatio\] MonoTime: (\d+) ms, Ratio: ([\d.]+), Saturation: ([-\d.]+)', line)
            if ratio_match:
                timestamp = int(ratio_match.group(1))
                ratio = float(ratio_match.group(2))
                saturation = float(ratio_match.group(3))
                ratio_data.append((timestamp, ratio, saturation))

            # 提取带宽估计数据 - DelayBWE决策
            # 格式: [DelayBWE-Decision] MonoTime: 488494798 ms, Detector state: 0, Old bitrate: 0 bps, New bitrate: 905548 bps
            delay_bwe_match = re.search(r'\[DelayBWE-Decision\] MonoTime: (\d+) ms.*New bitrate: (\d+) bps', line)
            if delay_bwe_match:
                timestamp = int(delay_bwe_match.group(1))
                bandwidth = int(delay_bwe_match.group(2))
                bandwidth_data.append((timestamp, bandwidth, 'DelayBWE'))

            # 提取BWE约束应用后的最终带宽
            # 格式: [BWE-ConstraintApply] MonoTime: 488494649 ms, Original: 300000 bps, ... Final: 300000 bps
            constraint_match = re.search(r'\[BWE-ConstraintApply\] MonoTime: (\d+) ms.*Final: (\d+) bps', line)
            if constraint_match:
                timestamp = int(constraint_match.group(1))
                bandwidth = int(constraint_match.group(2))
                bandwidth_data.append((timestamp, bandwidth, 'Final'))

    return ratio_data, bandwidth_data

def smooth_ratio_data(ratio_data, window_size=100):
    """对ratio数据进行平滑处理"""
    if len(ratio_data) < window_size:
        return ratio_data

    smoothed = []
    for i in range(len(ratio_data)):
        start_idx = max(0, i - window_size + 1)
        end_idx = i + 1

        window = ratio_data[start_idx:end_idx]
        avg_ratio = np.mean([r[1] for r in window])
        avg_saturation = np.mean([r[2] for r in window])

        timestamp = ratio_data[i][0]
        smoothed.append((timestamp, avg_ratio, avg_saturation))

    return smoothed

def align_data(ratio_data, bandwidth_data):
    """将ratio数据和带宽数据按时间对齐"""
    # 创建带宽的时间索引
    bw_dict = {}
    for ts, bw, bw_type in bandwidth_data:
        if bw_type == 'Final':  # 只使用最终带宽
            bw_dict[ts] = bw

    # 对每个ratio数据点，找到最近的带宽值
    aligned_data = []
    bw_timestamps = sorted(bw_dict.keys())

    for ratio_ts, ratio, saturation in ratio_data:
        # 找到最近的带宽时间戳
        closest_bw_ts = min(bw_timestamps, key=lambda x: abs(x - ratio_ts), default=None)

        if closest_bw_ts is not None and abs(closest_bw_ts - ratio_ts) < 1000:  # 1秒内
            bandwidth = bw_dict[closest_bw_ts]
            aligned_data.append({
                'timestamp': ratio_ts,
                'ratio': ratio,
                'saturation': saturation,
                'bandwidth_bps': bandwidth,
                'bandwidth_mbps': bandwidth / 1_000_000
            })

    return aligned_data

def calculate_correlation(aligned_data):
    """计算相关性统计"""
    if len(aligned_data) < 2:
        return None

    ratios = [d['ratio'] for d in aligned_data]
    bandwidths = [d['bandwidth_mbps'] for d in aligned_data]
    saturations = [d['saturation'] for d in aligned_data]

    # 计算相关系数
    ratio_bw_corr = np.corrcoef(ratios, bandwidths)[0, 1]
    saturation_bw_corr = np.corrcoef(saturations, bandwidths)[0, 1]

    return {
        'ratio_bandwidth_correlation': ratio_bw_corr,
        'saturation_bandwidth_correlation': saturation_bw_corr,
        'mean_ratio': np.mean(ratios),
        'std_ratio': np.std(ratios),
        'mean_bandwidth_mbps': np.mean(bandwidths),
        'std_bandwidth_mbps': np.std(bandwidths),
        'mean_saturation': np.mean(saturations),
        'std_saturation': np.std(saturations)
    }

def plot_analysis(aligned_data, smoothed_ratio_data, stats, output_path):
    """绘制分析图表"""
    fig, axes = plt.subplots(3, 2, figsize=(16, 12))

    # 提取数据
    timestamps = [(d['timestamp'] - aligned_data[0]['timestamp']) / 1000 for d in aligned_data]  # 转换为秒
    ratios = [d['ratio'] for d in aligned_data]
    bandwidths = [d['bandwidth_mbps'] for d in aligned_data]
    saturations = [d['saturation'] for d in aligned_data]

    # 1. 时间序列 - Ratio
    axes[0, 0].plot(timestamps, ratios, 'b-', alpha=0.6, linewidth=0.5, label='Original Ratio')
    if smoothed_ratio_data:
        smooth_timestamps = [(d[0] - aligned_data[0]['timestamp']) / 1000 for d in smoothed_ratio_data]
        smooth_ratios = [d[1] for d in smoothed_ratio_data]
        axes[0, 0].plot(smooth_timestamps, smooth_ratios, 'r-', linewidth=2, label='Smoothed Ratio (100-window)')
    axes[0, 0].set_xlabel('Time (seconds)')
    axes[0, 0].set_ylabel('Cellular Ratio')
    axes[0, 0].set_title('Cellular Ratio Over Time')
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)

    # 2. 时间序列 - Bandwidth
    axes[0, 1].plot(timestamps, bandwidths, 'g-', linewidth=1)
    axes[0, 1].set_xlabel('Time (seconds)')
    axes[0, 1].set_ylabel('Bandwidth (Mbps)')
    axes[0, 1].set_title('Bandwidth Over Time')
    axes[0, 1].grid(True, alpha=0.3)

    # 3. Ratio vs Bandwidth 散点图
    axes[1, 0].scatter(ratios, bandwidths, alpha=0.3, s=10)
    axes[1, 0].set_xlabel('Cellular Ratio')
    axes[1, 0].set_ylabel('Bandwidth (Mbps)')
    axes[1, 0].set_title(f'Ratio vs Bandwidth (corr={stats["ratio_bandwidth_correlation"]:.3f})')
    axes[1, 0].grid(True, alpha=0.3)

    # 添加趋势线
    z = np.polyfit(ratios, bandwidths, 1)
    p = np.poly1d(z)
    ratio_sorted = sorted(ratios)
    axes[1, 0].plot(ratio_sorted, p(ratio_sorted), "r--", linewidth=2, label=f'y={z[0]:.2f}x+{z[1]:.2f}')
    axes[1, 0].legend()

    # 4. Saturation vs Bandwidth
    axes[1, 1].scatter(saturations, bandwidths, alpha=0.3, s=10, c='orange')
    axes[1, 1].set_xlabel('Saturation')
    axes[1, 1].set_ylabel('Bandwidth (Mbps)')
    axes[1, 1].set_title(f'Saturation vs Bandwidth (corr={stats["saturation_bandwidth_correlation"]:.3f})')
    axes[1, 1].grid(True, alpha=0.3)

    # 5. Ratio分布直方图
    axes[2, 0].hist(ratios, bins=50, alpha=0.7, color='blue', edgecolor='black')
    axes[2, 0].axvline(stats['mean_ratio'], color='r', linestyle='--', linewidth=2,
                       label=f'Mean: {stats["mean_ratio"]:.3f}')
    axes[2, 0].set_xlabel('Cellular Ratio')
    axes[2, 0].set_ylabel('Frequency')
    axes[2, 0].set_title(f'Ratio Distribution (std={stats["std_ratio"]:.3f})')
    axes[2, 0].legend()
    axes[2, 0].grid(True, alpha=0.3)

    # 6. Bandwidth分布直方图
    axes[2, 1].hist(bandwidths, bins=50, alpha=0.7, color='green', edgecolor='black')
    axes[2, 1].axvline(stats['mean_bandwidth_mbps'], color='r', linestyle='--', linewidth=2,
                       label=f'Mean: {stats["mean_bandwidth_mbps"]:.3f} Mbps')
    axes[2, 1].set_xlabel('Bandwidth (Mbps)')
    axes[2, 1].set_ylabel('Frequency')
    axes[2, 1].set_title(f'Bandwidth Distribution (std={stats["std_bandwidth_mbps"]:.3f})')
    axes[2, 1].legend()
    axes[2, 1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"图表已保存到: {output_path}")
    plt.close()

def main():
    log_path = '/home/wuq/webrtc-local/webrtc_config_results/sender_local.log'
    output_path = '/home/wuq/webrtc-local/smoothed_ratio_bandwidth_analysis.png'

    print("正在解析日志文件...")
    ratio_data, bandwidth_data = parse_log_file(log_path)

    print(f"找到 {len(ratio_data)} 个ratio数据点")
    print(f"找到 {len(bandwidth_data)} 个带宽数据点")

    if len(ratio_data) == 0:
        print("错误: 没有找到ratio数据")
        return

    if len(bandwidth_data) == 0:
        print("错误: 没有找到带宽数据")
        return

    # 平滑ratio数据
    print("\n正在平滑ratio数据（100点滑动平均）...")
    smoothed_ratio_data = smooth_ratio_data(ratio_data, window_size=100)

    # 对齐数据
    print("正在对齐ratio和带宽数据...")
    aligned_data = align_data(smoothed_ratio_data, bandwidth_data)

    print(f"对齐后有 {len(aligned_data)} 个数据点")

    if len(aligned_data) < 2:
        print("错误: 对齐后的数据点太少")
        return

    # 计算统计信息
    print("\n正在计算相关性统计...")
    stats = calculate_correlation(aligned_data)

    print("\n=== 分析结果 ===")
    print(f"Ratio与Bandwidth的相关系数: {stats['ratio_bandwidth_correlation']:.4f}")
    print(f"Saturation与Bandwidth的相关系数: {stats['saturation_bandwidth_correlation']:.4f}")
    print(f"\nRatio统计:")
    print(f"  平均值: {stats['mean_ratio']:.4f}")
    print(f"  标准差: {stats['std_ratio']:.4f}")
    print(f"\nBandwidth统计:")
    print(f"  平均值: {stats['mean_bandwidth_mbps']:.4f} Mbps")
    print(f"  标准差: {stats['std_bandwidth_mbps']:.4f} Mbps")
    print(f"\nSaturation统计:")
    print(f"  平均值: {stats['mean_saturation']:.4f}")
    print(f"  标准差: {stats['std_saturation']:.4f}")

    # 绘制分析图表
    print("\n正在生成分析图表...")
    plot_analysis(aligned_data, smoothed_ratio_data, stats, output_path)

    print("\n分析完成!")

if __name__ == '__main__':
    main()

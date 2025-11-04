#!/usr/bin/env python3
"""
详细分析平滑后的cellular ratio和带宽的关系
包括分段分析、ratio范围分析等
"""

import re
import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict

def parse_log_file(log_path):
    """解析日志文件，提取ratio、saturation和带宽信息"""
    ratio_data = []
    bandwidth_data = []

    with open(log_path, 'r') as f:
        for line in f:
            ratio_match = re.search(r'\[CellularRatio\] MonoTime: (\d+) ms, Ratio: ([\d.]+), Saturation: ([-\d.]+)', line)
            if ratio_match:
                timestamp = int(ratio_match.group(1))
                ratio = float(ratio_match.group(2))
                saturation = float(ratio_match.group(3))
                ratio_data.append((timestamp, ratio, saturation))

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
    bw_dict = {}
    for ts, bw, bw_type in bandwidth_data:
        if bw_type == 'Final':
            bw_dict[ts] = bw

    aligned_data = []
    bw_timestamps = sorted(bw_dict.keys())

    for ratio_ts, ratio, saturation in ratio_data:
        closest_bw_ts = min(bw_timestamps, key=lambda x: abs(x - ratio_ts), default=None)
        if closest_bw_ts is not None and abs(closest_bw_ts - ratio_ts) < 1000:
            bandwidth = bw_dict[closest_bw_ts]
            aligned_data.append({
                'timestamp': ratio_ts,
                'ratio': ratio,
                'saturation': saturation,
                'bandwidth_bps': bandwidth,
                'bandwidth_mbps': bandwidth / 1_000_000
            })

    return aligned_data

def analyze_by_ratio_bins(aligned_data, num_bins=10):
    """按ratio范围分析带宽表现"""
    ratios = [d['ratio'] for d in aligned_data]
    min_ratio = min(ratios)
    max_ratio = max(ratios)

    # 创建等间距的bins
    bins = np.linspace(min_ratio, max_ratio, num_bins + 1)
    bin_stats = []

    for i in range(num_bins):
        bin_min = bins[i]
        bin_max = bins[i + 1]

        # 找到这个bin范围内的数据
        bin_data = [d for d in aligned_data if bin_min <= d['ratio'] < bin_max or (i == num_bins - 1 and d['ratio'] == bin_max)]

        if bin_data:
            bandwidths = [d['bandwidth_mbps'] for d in bin_data]
            bin_stats.append({
                'ratio_min': bin_min,
                'ratio_max': bin_max,
                'ratio_center': (bin_min + bin_max) / 2,
                'count': len(bin_data),
                'bandwidth_mean': np.mean(bandwidths),
                'bandwidth_std': np.std(bandwidths),
                'bandwidth_min': np.min(bandwidths),
                'bandwidth_max': np.max(bandwidths)
            })

    return bin_stats

def analyze_time_segments(aligned_data, num_segments=5):
    """按时间段分析ratio和带宽的关系"""
    if len(aligned_data) < num_segments:
        return []

    segment_size = len(aligned_data) // num_segments
    segment_stats = []

    for i in range(num_segments):
        start_idx = i * segment_size
        end_idx = (i + 1) * segment_size if i < num_segments - 1 else len(aligned_data)

        segment_data = aligned_data[start_idx:end_idx]
        ratios = [d['ratio'] for d in segment_data]
        bandwidths = [d['bandwidth_mbps'] for d in segment_data]

        correlation = np.corrcoef(ratios, bandwidths)[0, 1] if len(segment_data) > 1 else 0

        start_time = (segment_data[0]['timestamp'] - aligned_data[0]['timestamp']) / 1000
        end_time = (segment_data[-1]['timestamp'] - aligned_data[0]['timestamp']) / 1000

        segment_stats.append({
            'segment': i + 1,
            'start_time': start_time,
            'end_time': end_time,
            'count': len(segment_data),
            'ratio_mean': np.mean(ratios),
            'ratio_std': np.std(ratios),
            'bandwidth_mean': np.mean(bandwidths),
            'bandwidth_std': np.std(bandwidths),
            'correlation': correlation
        })

    return segment_stats

def plot_detailed_analysis(aligned_data, bin_stats, segment_stats, output_path):
    """绘制详细分析图表"""
    fig = plt.figure(figsize=(18, 12))
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

    # 提取数据
    timestamps = [(d['timestamp'] - aligned_data[0]['timestamp']) / 1000 for d in aligned_data]
    ratios = [d['ratio'] for d in aligned_data]
    bandwidths = [d['bandwidth_mbps'] for d in aligned_data]
    saturations = [d['saturation'] for d in aligned_data]

    # 1. 时间序列 - Ratio和Bandwidth双Y轴
    ax1 = fig.add_subplot(gs[0, :])
    color = 'tab:blue'
    ax1.set_xlabel('Time (seconds)')
    ax1.set_ylabel('Smoothed Cellular Ratio', color=color)
    ax1.plot(timestamps, ratios, color=color, linewidth=1.5, alpha=0.7)
    ax1.tick_params(axis='y', labelcolor=color)
    ax1.grid(True, alpha=0.3)

    ax2 = ax1.twinx()
    color = 'tab:green'
    ax2.set_ylabel('Bandwidth (Mbps)', color=color)
    ax2.plot(timestamps, bandwidths, color=color, linewidth=1.5, alpha=0.7)
    ax2.tick_params(axis='y', labelcolor=color)

    ax1.set_title('Smoothed Ratio and Bandwidth Over Time', fontsize=14, fontweight='bold')

    # 2. Ratio bins vs 平均带宽（带误差条）
    ax3 = fig.add_subplot(gs[1, 0])
    bin_centers = [b['ratio_center'] for b in bin_stats]
    bin_means = [b['bandwidth_mean'] for b in bin_stats]
    bin_stds = [b['bandwidth_std'] for b in bin_stats]

    ax3.errorbar(bin_centers, bin_means, yerr=bin_stds, fmt='o-', capsize=5, capthick=2, linewidth=2)
    ax3.set_xlabel('Smoothed Ratio (binned)')
    ax3.set_ylabel('Average Bandwidth (Mbps)')
    ax3.set_title('Bandwidth vs Ratio Bins')
    ax3.grid(True, alpha=0.3)

    # 3. Ratio bins样本数量
    ax4 = fig.add_subplot(gs[1, 1])
    bin_counts = [b['count'] for b in bin_stats]
    ax4.bar(range(len(bin_stats)), bin_counts, alpha=0.7, color='skyblue', edgecolor='black')
    ax4.set_xlabel('Ratio Bin Index')
    ax4.set_ylabel('Sample Count')
    ax4.set_title('Sample Distribution Across Ratio Bins')
    ax4.grid(True, alpha=0.3, axis='y')

    # 4. 时间段相关性变化
    ax5 = fig.add_subplot(gs[1, 2])
    segment_ids = [s['segment'] for s in segment_stats]
    correlations = [s['correlation'] for s in segment_stats]
    ax5.plot(segment_ids, correlations, 'o-', linewidth=2, markersize=8, color='purple')
    ax5.axhline(y=0, color='r', linestyle='--', alpha=0.5)
    ax5.set_xlabel('Time Segment')
    ax5.set_ylabel('Correlation Coefficient')
    ax5.set_title('Ratio-Bandwidth Correlation by Time Segment')
    ax5.grid(True, alpha=0.3)
    ax5.set_ylim(-1, 1)

    # 5. 散点图（彩色编码时间）
    ax6 = fig.add_subplot(gs[2, 0])
    scatter = ax6.scatter(ratios, bandwidths, c=timestamps, cmap='viridis', alpha=0.5, s=10)
    ax6.set_xlabel('Smoothed Ratio')
    ax6.set_ylabel('Bandwidth (Mbps)')
    ax6.set_title('Ratio vs Bandwidth (color=time)')
    ax6.grid(True, alpha=0.3)
    plt.colorbar(scatter, ax=ax6, label='Time (s)')

    # 6. Saturation vs Bandwidth
    ax7 = fig.add_subplot(gs[2, 1])
    # 限制saturation范围以获得更好的可视化
    sat_filtered = [(s, b) for s, b in zip(saturations, bandwidths) if -50 < s < 50]
    if sat_filtered:
        sats, bws = zip(*sat_filtered)
        ax7.scatter(sats, bws, alpha=0.3, s=10, c='orange')
        ax7.set_xlabel('Saturation (filtered -50 to 50)')
        ax7.set_ylabel('Bandwidth (Mbps)')
        ax7.set_title('Saturation vs Bandwidth')
        ax7.grid(True, alpha=0.3)

    # 7. 时间段平均ratio和bandwidth
    ax8 = fig.add_subplot(gs[2, 2])
    seg_ratios = [s['ratio_mean'] for s in segment_stats]
    seg_bandwidths = [s['bandwidth_mean'] for s in segment_stats]
    seg_labels = [f"Seg{s['segment']}" for s in segment_stats]

    x = np.arange(len(segment_stats))
    width = 0.35

    ax8_twin = ax8.twinx()
    bars1 = ax8.bar(x - width/2, seg_ratios, width, label='Avg Ratio', alpha=0.7, color='blue')
    bars2 = ax8_twin.bar(x + width/2, seg_bandwidths, width, label='Avg Bandwidth', alpha=0.7, color='green')

    ax8.set_xlabel('Time Segment')
    ax8.set_ylabel('Average Ratio', color='blue')
    ax8_twin.set_ylabel('Average Bandwidth (Mbps)', color='green')
    ax8.set_title('Segment Averages')
    ax8.set_xticks(x)
    ax8.set_xticklabels(seg_labels)
    ax8.tick_params(axis='y', labelcolor='blue')
    ax8_twin.tick_params(axis='y', labelcolor='green')
    ax8.grid(True, alpha=0.3, axis='y')

    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"详细分析图表已保存到: {output_path}")
    plt.close()

def print_detailed_stats(bin_stats, segment_stats):
    """打印详细统计信息"""
    print("\n=== Ratio Bin 分析 ===")
    print(f"{'Ratio Range':<20} {'Count':<10} {'Avg BW (Mbps)':<15} {'Std BW':<15}")
    print("-" * 60)
    for b in bin_stats:
        ratio_range = f"{b['ratio_min']:.3f}-{b['ratio_max']:.3f}"
        print(f"{ratio_range:<20} {b['count']:<10} {b['bandwidth_mean']:<15.4f} {b['bandwidth_std']:<15.4f}")

    print("\n=== 时间段分析 ===")
    print(f"{'Segment':<10} {'Time Range (s)':<20} {'Avg Ratio':<15} {'Avg BW (Mbps)':<15} {'Correlation':<15}")
    print("-" * 75)
    for s in segment_stats:
        time_range = f"{s['start_time']:.1f}-{s['end_time']:.1f}"
        print(f"{s['segment']:<10} {time_range:<20} {s['ratio_mean']:<15.4f} {s['bandwidth_mean']:<15.4f} {s['correlation']:<15.4f}")

def main():
    log_path = '/home/wuq/webrtc-local/webrtc_config_results/sender_local.log'
    output_path = '/home/wuq/webrtc-local/detailed_ratio_bandwidth_analysis.png'

    print("正在解析日志文件...")
    ratio_data, bandwidth_data = parse_log_file(log_path)

    print(f"找到 {len(ratio_data)} 个ratio数据点")
    print(f"找到 {len(bandwidth_data)} 个带宽数据点")

    if len(ratio_data) == 0 or len(bandwidth_data) == 0:
        print("错误: 没有找到足够的数据")
        return

    # 平滑ratio数据
    print("\n正在平滑ratio数据（100点滑动平均）...")
    smoothed_ratio_data = smooth_ratio_data(ratio_data, window_size=100)

    # 对齐数据
    print("正在对齐ratio和带宽数据...")
    aligned_data = align_data(smoothed_ratio_data, bandwidth_data)

    print(f"对齐后有 {len(aligned_data)} 个数据点")

    if len(aligned_data) < 10:
        print("错误: 对齐后的数据点太少")
        return

    # 按ratio范围分析
    print("\n正在进行ratio bin分析...")
    bin_stats = analyze_by_ratio_bins(aligned_data, num_bins=10)

    # 按时间段分析
    print("正在进行时间段分析...")
    segment_stats = analyze_time_segments(aligned_data, num_segments=5)

    # 打印统计信息
    print_detailed_stats(bin_stats, segment_stats)

    # 绘制详细分析图表
    print("\n正在生成详细分析图表...")
    plot_detailed_analysis(aligned_data, bin_stats, segment_stats, output_path)

    # 计算整体相关性
    ratios = [d['ratio'] for d in aligned_data]
    bandwidths = [d['bandwidth_mbps'] for d in aligned_data]
    overall_corr = np.corrcoef(ratios, bandwidths)[0, 1]

    print(f"\n=== 总体分析 ===")
    print(f"整体相关系数: {overall_corr:.4f}")
    print(f"Ratio范围: {min(ratios):.4f} - {max(ratios):.4f}")
    print(f"Bandwidth范围: {min(bandwidths):.4f} - {max(bandwidths):.4f} Mbps")

    print("\n分析完成!")

if __name__ == '__main__':
    main()

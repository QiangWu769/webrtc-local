#!/usr/bin/env python3
"""
Correct analysis of the relationship between smoothed ratio and bandwidth
Using the actual bandwidth decisions from DelayBWE and AIMD
"""

import re
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

def parse_log_correct(log_path):
    """Parse the log file and extract ratio and actual bandwidth decisions"""

    # Patterns
    ratio_pattern = r'Resource ratio updated: ([\d.]+) \(smoothed: ([\d.]+)\), trend: ([-\d.]+)'
    # The actual bandwidth decision
    delaybwe_pattern = r'\[DelayBWE-Decision\].*Old bitrate: (\d+) bps, New bitrate: (\d+) bps'
    aimd_result_pattern = r'\[AIMD-Result\].*Old bitrate: (\d+) bps, New bitrate: (\d+) bps'

    # Sequential data storage
    events = []
    current_bandwidth = None  # Track the actual bandwidth estimate

    line_num = 0
    with open(log_path, 'r') as f:
        for line in f:
            line_num += 1

            # Track bandwidth decisions from DelayBWE (this is the primary bandwidth estimate)
            delaybwe_match = re.search(delaybwe_pattern, line)
            if delaybwe_match:
                old_bw = int(delaybwe_match.group(1))
                new_bw = int(delaybwe_match.group(2))
                current_bandwidth = new_bw

                events.append({
                    'line': line_num,
                    'type': 'bandwidth',
                    'old_bandwidth': old_bw,
                    'new_bandwidth': new_bw,
                    'change': new_bw - old_bw
                })

            # Also track AIMD results
            aimd_match = re.search(aimd_result_pattern, line)
            if aimd_match:
                new_bw = int(aimd_match.group(2))
                # Update current bandwidth if AIMD provides a new value
                if new_bw != current_bandwidth:
                    current_bandwidth = new_bw

            # Capture ratio updates with the current bandwidth
            ratio_match = re.search(ratio_pattern, line)
            if ratio_match:
                raw_ratio = float(ratio_match.group(1))
                smoothed_ratio = float(ratio_match.group(2))
                trend = float(ratio_match.group(3))

                events.append({
                    'line': line_num,
                    'type': 'ratio',
                    'raw_ratio': raw_ratio,
                    'smoothed_ratio': smoothed_ratio,
                    'trend': trend,
                    'current_bandwidth': current_bandwidth
                })

    return events

def analyze_ratio_bandwidth(events):
    """Analyze the relationship between ratio and bandwidth"""

    # Extract ratio events that have bandwidth information
    ratio_events = [e for e in events if e['type'] == 'ratio' and e['current_bandwidth'] is not None]
    bandwidth_events = [e for e in events if e['type'] == 'bandwidth']

    print("\n" + "="*70)
    print("正确的 RATIO 和 BANDWIDTH 关系分析")
    print("="*70)

    if not ratio_events:
        print("没有找到包含带宽信息的ratio事件")
        return None

    print(f"\n总事件数: {len(events)}")
    print(f"  - Ratio更新事件: {len(ratio_events)}")
    print(f"  - 带宽决策事件: {len(bandwidth_events)}")

    # Extract data
    smoothed_ratios = np.array([e['smoothed_ratio'] for e in ratio_events])
    raw_ratios = np.array([e['raw_ratio'] for e in ratio_events])
    trends = np.array([e['trend'] for e in ratio_events])
    bandwidths = np.array([e['current_bandwidth'] / 1e6 for e in ratio_events])  # Mbps

    # Bandwidth decision data
    bw_old = np.array([e['old_bandwidth'] / 1e6 for e in bandwidth_events])
    bw_new = np.array([e['new_bandwidth'] / 1e6 for e in bandwidth_events])
    bw_changes = np.array([e['change'] / 1e3 for e in bandwidth_events])  # kbps

    # Statistics
    print(f"\n" + "-"*70)
    print("SMOOTHED RATIO 统计")
    print("-"*70)
    print(f"样本数: {len(smoothed_ratios)}")
    print(f"均值: {np.mean(smoothed_ratios):.3f}")
    print(f"标准差: {np.std(smoothed_ratios):.3f}")
    print(f"范围: [{np.min(smoothed_ratios):.3f}, {np.max(smoothed_ratios):.3f}]")
    print(f"中位数: {np.median(smoothed_ratios):.3f}")

    print(f"\n" + "-"*70)
    print("带宽估计统计（在Ratio更新时）")
    print("-"*70)
    print(f"样本数: {len(bandwidths)}")
    print(f"均值: {np.mean(bandwidths):.3f} Mbps")
    print(f"标准差: {np.std(bandwidths):.3f} Mbps")
    print(f"范围: [{np.min(bandwidths):.3f}, {np.max(bandwidths):.3f}] Mbps")
    print(f"中位数: {np.median(bandwidths):.3f} Mbps")

    print(f"\n" + "-"*70)
    print("带宽决策统计")
    print("-"*70)
    print(f"总决策次数: {len(bandwidth_events)}")
    print(f"带宽范围: [{np.min(bw_new):.3f}, {np.max(bw_new):.3f}] Mbps")

    increases = bw_changes[bw_changes > 0]
    decreases = bw_changes[bw_changes < 0]
    unchanged = bw_changes[bw_changes == 0]

    print(f"\n带宽变化分布:")
    print(f"  增加: {len(increases)} 次 ({100*len(increases)/len(bw_changes):.1f}%)")
    if len(increases) > 0:
        print(f"    平均增量: {np.mean(increases):.2f} kbps")
    print(f"  减少: {len(decreases)} 次 ({100*len(decreases)/len(bw_changes):.1f}%)")
    if len(decreases) > 0:
        print(f"    平均减量: {np.mean(decreases):.2f} kbps")
    print(f"  不变: {len(unchanged)} 次 ({100*len(unchanged)/len(bw_changes):.1f}%)")

    # Correlation analysis
    print(f"\n" + "-"*70)
    print("相关性分析")
    print("-"*70)

    correlation, p_value = stats.pearsonr(smoothed_ratios, bandwidths)
    print(f"\nPearson相关系数 (Smoothed Ratio vs 带宽): {correlation:.4f}")
    print(f"P值: {p_value:.4e}")

    if p_value < 0.001:
        significance = "极显著 (***)"
    elif p_value < 0.01:
        significance = "非常显著 (**)"
    elif p_value < 0.05:
        significance = "显著 (*)"
    else:
        significance = "不显著"

    print(f"显著性: {significance}")

    if abs(correlation) < 0.3:
        strength = "弱相关"
    elif abs(correlation) < 0.7:
        strength = "中等相关"
    else:
        strength = "强相关"

    print(f"相关强度: {strength}")

    spearman_corr, spearman_p = stats.spearmanr(smoothed_ratios, bandwidths)
    print(f"\nSpearman相关系数: {spearman_corr:.4f}")
    print(f"P值: {spearman_p:.4e}")

    # Analyze by ratio ranges
    print(f"\n" + "-"*70)
    print("不同Ratio范围的带宽表现")
    print("-"*70)

    ratio_ranges = [
        (0.0, 0.7, "极低 (< 0.7)"),
        (0.7, 0.9, "低 (0.7-0.9)"),
        (0.9, 1.1, "正常 (0.9-1.1)"),
        (1.1, 1.3, "高 (1.1-1.3)"),
        (1.3, 2.0, "极高 (> 1.3)")
    ]

    for low, high, label in ratio_ranges:
        mask = (smoothed_ratios >= low) & (smoothed_ratios < high)
        if np.sum(mask) > 0:
            bw_subset = bandwidths[mask]
            print(f"\n{label}:")
            print(f"  样本数: {len(bw_subset)} ({100*len(bw_subset)/len(bandwidths):.1f}%)")
            print(f"  平均带宽: {np.mean(bw_subset):.3f} Mbps")
            print(f"  标准差: {np.std(bw_subset):.3f} Mbps")
            print(f"  范围: [{np.min(bw_subset):.3f}, {np.max(bw_subset):.3f}] Mbps")

    # Analyze trend impact
    print(f"\n" + "-"*70)
    print("Trend方向对带宽的影响")
    print("-"*70)

    pos_mask = trends > 0
    neg_mask = trends < 0

    if np.sum(pos_mask) > 0:
        pos_bw = bandwidths[pos_mask]
        print(f"\n正向Trend (上升) - {np.sum(pos_mask)}个样本 ({100*np.sum(pos_mask)/len(trends):.1f}%):")
        print(f"  平均带宽: {np.mean(pos_bw):.3f} Mbps")
        print(f"  标准差: {np.std(pos_bw):.3f} Mbps")

    if np.sum(neg_mask) > 0:
        neg_bw = bandwidths[neg_mask]
        print(f"\n负向Trend (下降) - {np.sum(neg_mask)}个样本 ({100*np.sum(neg_mask)/len(trends):.1f}%):")
        print(f"  平均带宽: {np.mean(neg_bw):.3f} Mbps")
        print(f"  标准差: {np.std(neg_bw):.3f} Mbps")

    return {
        'smoothed_ratios': smoothed_ratios,
        'raw_ratios': raw_ratios,
        'trends': trends,
        'bandwidths': bandwidths,
        'bw_old': bw_old,
        'bw_new': bw_new,
        'bw_changes': bw_changes
    }

def plot_correct_analysis(data):
    """Create comprehensive visualization with correct bandwidth data"""

    smoothed_ratios = data['smoothed_ratios']
    raw_ratios = data['raw_ratios']
    trends = data['trends']
    bandwidths = data['bandwidths']
    bw_changes = data['bw_changes']

    fig = plt.figure(figsize=(20, 14))
    gs = fig.add_gridspec(4, 3, hspace=0.35, wspace=0.35)

    # Plot 1: Time series of smoothed ratio
    ax1 = fig.add_subplot(gs[0, :2])
    ax1.plot(smoothed_ratios, linewidth=1, alpha=0.7, color='blue', label='Smoothed Ratio')
    ax1.axhline(y=1.0, color='r', linestyle='--', alpha=0.5, linewidth=2, label='目标 (1.0)')
    ax1.fill_between(range(len(smoothed_ratios)), 0.9, 1.1, alpha=0.15, color='green', label='正常范围')
    ax1.set_xlabel('Ratio更新序号', fontsize=11)
    ax1.set_ylabel('Smoothed Ratio', fontsize=11)
    ax1.set_title('平滑后的Ratio随时间变化', fontsize=13, fontweight='bold')
    ax1.legend(fontsize=10)
    ax1.grid(True, alpha=0.3)

    # Plot 2: Time series of bandwidth at ratio updates
    ax2 = fig.add_subplot(gs[1, :2])
    ax2.plot(bandwidths, linewidth=1.5, alpha=0.8, color='orange', label='带宽估计')
    ax2.set_xlabel('Ratio更新序号', fontsize=11)
    ax2.set_ylabel('带宽 (Mbps)', fontsize=11)
    ax2.set_title('带宽估计随时间变化（在Ratio更新时刻）', fontsize=13, fontweight='bold')
    ax2.legend(fontsize=10)
    ax2.grid(True, alpha=0.3)

    # Plot 3: Scatter plot with regression
    ax3 = fig.add_subplot(gs[0:2, 2])

    # Color points by bandwidth
    scatter = ax3.scatter(smoothed_ratios, bandwidths, c=bandwidths,
                         cmap='viridis', alpha=0.4, s=20, edgecolors='none')

    # Add regression line
    z = np.polyfit(smoothed_ratios, bandwidths, 1)
    p = np.poly1d(z)
    ratio_line = np.linspace(smoothed_ratios.min(), smoothed_ratios.max(), 100)
    ax3.plot(ratio_line, p(ratio_line), "r--", linewidth=3,
             label=f'线性拟合: y = {z[0]:.3f}x + {z[1]:.3f}')

    correlation, _ = stats.pearsonr(smoothed_ratios, bandwidths)
    ax3.text(0.05, 0.95, f'Pearson r = {correlation:.4f}',
             transform=ax3.transAxes, fontsize=11, fontweight='bold',
             verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    ax3.set_xlabel('Smoothed Ratio', fontsize=11)
    ax3.set_ylabel('带宽 (Mbps)', fontsize=11)
    ax3.set_title('Ratio与带宽的相关性', fontsize=13, fontweight='bold')
    ax3.legend(fontsize=10)
    ax3.grid(True, alpha=0.3)

    cbar = plt.colorbar(scatter, ax=ax3)
    cbar.set_label('带宽 (Mbps)', fontsize=10)

    # Plot 4: Box plot by ratio category
    ax4 = fig.add_subplot(gs[2, 0])

    categories = []
    for r in smoothed_ratios:
        if r < 0.7:
            categories.append('极低\n(<0.7)')
        elif r < 0.9:
            categories.append('低\n(0.7-0.9)')
        elif r <= 1.1:
            categories.append('正常\n(0.9-1.1)')
        elif r <= 1.3:
            categories.append('高\n(1.1-1.3)')
        else:
            categories.append('极高\n(>1.3)')

    data_by_cat = {}
    for cat, bw in zip(categories, bandwidths):
        if cat not in data_by_cat:
            data_by_cat[cat] = []
        data_by_cat[cat].append(bw)

    # Sort categories
    cat_order = ['极低\n(<0.7)', '低\n(0.7-0.9)', '正常\n(0.9-1.1)', '高\n(1.1-1.3)', '极高\n(>1.3)']
    plot_data = [data_by_cat[cat] for cat in cat_order if cat in data_by_cat]
    plot_labels = [cat for cat in cat_order if cat in data_by_cat]

    bp = ax4.boxplot(plot_data, labels=plot_labels, patch_artist=True)
    colors = ['lightcoral', 'lightsalmon', 'lightgreen', 'lightyellow', 'lightpink']
    for patch, color in zip(bp['boxes'], colors[:len(bp['boxes'])]):
        patch.set_facecolor(color)

    ax4.set_ylabel('带宽 (Mbps)', fontsize=11)
    ax4.set_title('不同Ratio范围的带宽分布', fontsize=12, fontweight='bold')
    ax4.grid(True, alpha=0.3, axis='y')

    # Plot 5: Ratio distribution histogram
    ax5 = fig.add_subplot(gs[2, 1])
    counts, bins, patches = ax5.hist(smoothed_ratios, bins=60, edgecolor='black',
                                      alpha=0.7, color='skyblue')
    ax5.axvline(x=1.0, color='r', linestyle='--', linewidth=2, label='目标 (1.0)')
    ax5.axvline(x=np.mean(smoothed_ratios), color='g', linestyle='--',
                linewidth=2, label=f'均值 ({np.mean(smoothed_ratios):.3f})')
    ax5.axvline(x=0.9, color='orange', linestyle=':', linewidth=1.5, alpha=0.7)
    ax5.axvline(x=1.1, color='orange', linestyle=':', linewidth=1.5, alpha=0.7)
    ax5.set_xlabel('Smoothed Ratio', fontsize=11)
    ax5.set_ylabel('频数', fontsize=11)
    ax5.set_title('Ratio分布直方图', fontsize=12, fontweight='bold')
    ax5.legend(fontsize=10)
    ax5.grid(True, alpha=0.3, axis='y')

    # Plot 6: Bandwidth distribution
    ax6 = fig.add_subplot(gs[2, 2])
    ax6.hist(bandwidths, bins=40, edgecolor='black', alpha=0.7, color='orange')
    ax6.axvline(x=np.mean(bandwidths), color='r', linestyle='--',
                linewidth=2, label=f'均值 ({np.mean(bandwidths):.3f} Mbps)')
    ax6.axvline(x=np.median(bandwidths), color='g', linestyle='--',
                linewidth=2, label=f'中位数 ({np.median(bandwidths):.3f} Mbps)')
    ax6.set_xlabel('带宽 (Mbps)', fontsize=11)
    ax6.set_ylabel('频数', fontsize=11)
    ax6.set_title('带宽分布直方图', fontsize=12, fontweight='bold')
    ax6.legend(fontsize=10)
    ax6.grid(True, alpha=0.3, axis='y')

    # Plot 7: Bandwidth changes histogram
    ax7 = fig.add_subplot(gs[3, 0])
    ax7.hist(bw_changes, bins=50, edgecolor='black', alpha=0.7, color='purple')
    ax7.axvline(x=0, color='r', linestyle='--', linewidth=2, label='无变化')
    ax7.set_xlabel('带宽变化量 (kbps)', fontsize=11)
    ax7.set_ylabel('频数', fontsize=11)
    ax7.set_title('带宽决策变化量分布', fontsize=12, fontweight='bold')
    ax7.legend(fontsize=10)
    ax7.grid(True, alpha=0.3, axis='y')

    # Plot 8: Raw vs Smoothed (sample)
    ax8 = fig.add_subplot(gs[3, 1])
    sample_size = min(400, len(raw_ratios))
    indices = range(sample_size)
    ax8.plot(indices, raw_ratios[:sample_size], alpha=0.4, linewidth=0.8,
             label='Raw Ratio', color='lightblue')
    ax8.plot(indices, smoothed_ratios[:sample_size], linewidth=1.5,
             label='Smoothed Ratio', color='darkblue')
    ax8.axhline(y=1.0, color='r', linestyle='--', alpha=0.5, linewidth=1.5)
    ax8.set_xlabel('样本序号', fontsize=11)
    ax8.set_ylabel('Ratio', fontsize=11)
    ax8.set_title(f'原始vs平滑Ratio对比 (前{sample_size}个样本)', fontsize=12, fontweight='bold')
    ax8.legend(fontsize=10)
    ax8.grid(True, alpha=0.3)

    # Plot 9: Trend vs Bandwidth
    ax9 = fig.add_subplot(gs[3, 2])
    scatter2 = ax9.scatter(trends, bandwidths, alpha=0.3, s=15, c=smoothed_ratios,
                          cmap='coolwarm', edgecolors='none')
    ax9.axvline(x=0, color='r', linestyle='--', alpha=0.5, linewidth=1.5)
    ax9.set_xlabel('Trend', fontsize=11)
    ax9.set_ylabel('带宽 (Mbps)', fontsize=11)
    ax9.set_title('Trend与带宽的关系', fontsize=12, fontweight='bold')
    ax9.grid(True, alpha=0.3)

    cbar2 = plt.colorbar(scatter2, ax=ax9)
    cbar2.set_label('Smoothed Ratio', fontsize=10)

    # Overall title
    fig.suptitle('WebRTC Cellular Ratio与带宽估计的完整关系分析',
                 fontsize=17, fontweight='bold', y=0.997)

    output_path = '/home/wuq/webrtc-local/webrtc_config_results/ratio_bandwidth_correct_analysis.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n📊 完整分析图表已保存至: {output_path}")

def main():
    log_path = '/home/wuq/webrtc-local/webrtc_config_results/sender_local.log'

    print(f"正在解析日志文件: {log_path}")
    events = parse_log_correct(log_path)

    print(f"总共捕获的事件数: {len(events)}")

    # Analyze the data
    data = analyze_ratio_bandwidth(events)

    # Create plots
    if data is not None:
        plot_correct_analysis(data)

if __name__ == '__main__':
    main()

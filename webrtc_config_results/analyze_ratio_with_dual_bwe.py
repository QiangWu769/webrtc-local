#!/usr/bin/env python3
"""
Complete analysis of smoothed ratio relationship with both delay-based and loss-based BWE
"""

import re
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

def parse_dual_bwe_log(log_path):
    """Parse log to extract ratio, delay-based BWE, and loss-based BWE"""

    # Patterns
    ratio_pattern = r'Resource ratio updated: ([\d.]+) \(smoothed: ([\d.]+)\), trend: ([-\d.]+)'

    # BWE-ConstraintApply shows the final bandwidth decision with delay limit
    constraint_pattern = r'\[(\d+\.\d+)\].*\[BWE-ConstraintApply\].*Original: (\d+) bps.*Final: (\d+) bps, DelayLimit: ([\dINF.]+)'

    # Loss-based bandwidth estimate
    loss_bwe_pattern = r'\[(\d+\.\d+)\].*\[SendBWE-Loss\].*Current target: (\d+) bps, Loss-based estimate: (\d+) bps'

    events = []
    current_delay_bwe = None
    current_loss_bwe = None
    current_final_bwe = None

    line_num = 0
    with open(log_path, 'r') as f:
        for line in f:
            line_num += 1

            # Extract constraint apply (final bandwidth with delay limit)
            constraint_match = re.search(constraint_pattern, line)
            if constraint_match:
                timestamp = float(constraint_match.group(1))
                original = int(constraint_match.group(2))
                final = int(constraint_match.group(3))
                delay_limit = constraint_match.group(4)

                if delay_limit != 'INF':
                    current_delay_bwe = int(float(delay_limit))

                current_final_bwe = final

                events.append({
                    'line': line_num,
                    'type': 'bwe_constraint',
                    'timestamp': timestamp,
                    'original': original,
                    'final': final,
                    'delay_limit': delay_limit
                })

            # Extract loss-based BWE
            loss_match = re.search(loss_bwe_pattern, line)
            if loss_match:
                timestamp = float(loss_match.group(1))
                target = int(loss_match.group(2))
                loss_estimate = int(loss_match.group(3))

                current_loss_bwe = loss_estimate

                events.append({
                    'line': line_num,
                    'type': 'loss_bwe',
                    'timestamp': timestamp,
                    'target': target,
                    'loss_estimate': loss_estimate
                })

            # Extract ratio updates
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
                    'delay_bwe': current_delay_bwe,
                    'loss_bwe': current_loss_bwe,
                    'final_bwe': current_final_bwe
                })

    return events

def analyze_dual_bwe(events):
    """Analyze relationship between ratio and both BWE estimates"""

    ratio_events = [e for e in events if e['type'] == 'ratio']
    bwe_events = [e for e in events if e['type'] == 'bwe_constraint']
    loss_events = [e for e in events if e['type'] == 'loss_bwe']

    print("\n" + "="*80)
    print("双BWE系统分析: Delay-Based vs Loss-Based 与 Ratio 的关系")
    print("="*80)

    print(f"\n事件统计:")
    print(f"  Ratio更新: {len(ratio_events)}")
    print(f"  BWE约束应用: {len(bwe_events)}")
    print(f"  Loss-based BWE: {len(loss_events)}")

    # Filter ratio events with BWE data
    ratio_with_delay = [e for e in ratio_events if e['delay_bwe'] is not None]
    ratio_with_loss = [e for e in ratio_events if e['loss_bwe'] is not None]
    ratio_with_both = [e for e in ratio_events
                       if e['delay_bwe'] is not None and e['loss_bwe'] is not None]

    print(f"\nRatio事件中包含BWE数据的:")
    print(f"  有Delay-BWE: {len(ratio_with_delay)}")
    print(f"  有Loss-BWE: {len(ratio_with_loss)}")
    print(f"  两者都有: {len(ratio_with_both)}")

    if not ratio_with_both:
        print("警告: 没有同时包含两种BWE数据的ratio样本")
        return None

    # Extract data arrays
    smoothed_ratios = np.array([e['smoothed_ratio'] for e in ratio_with_both])
    raw_ratios = np.array([e['raw_ratio'] for e in ratio_with_both])
    trends = np.array([e['trend'] for e in ratio_with_both])
    delay_bwe = np.array([e['delay_bwe'] / 1e6 for e in ratio_with_both])  # Mbps
    loss_bwe = np.array([e['loss_bwe'] / 1e6 for e in ratio_with_both])    # Mbps
    final_bwe = np.array([e['final_bwe'] / 1e6 for e in ratio_with_both])  # Mbps

    # Statistics
    print(f"\n" + "-"*80)
    print("SMOOTHED RATIO 统计")
    print("-"*80)
    print(f"样本数: {len(smoothed_ratios)}")
    print(f"均值: {np.mean(smoothed_ratios):.3f}")
    print(f"标准差: {np.std(smoothed_ratios):.3f}")
    print(f"范围: [{np.min(smoothed_ratios):.3f}, {np.max(smoothed_ratios):.3f}]")
    print(f"中位数: {np.median(smoothed_ratios):.3f}")

    print(f"\n" + "-"*80)
    print("DELAY-BASED BWE 统计")
    print("-"*80)
    print(f"均值: {np.mean(delay_bwe):.3f} Mbps")
    print(f"标准差: {np.std(delay_bwe):.3f} Mbps")
    print(f"范围: [{np.min(delay_bwe):.3f}, {np.max(delay_bwe):.3f}] Mbps")
    print(f"中位数: {np.median(delay_bwe):.3f} Mbps")

    print(f"\n" + "-"*80)
    print("LOSS-BASED BWE 统计")
    print("-"*80)
    print(f"均值: {np.mean(loss_bwe):.3f} Mbps")
    print(f"标准差: {np.std(loss_bwe):.3f} Mbps")
    print(f"范围: [{np.min(loss_bwe):.3f}, {np.max(loss_bwe):.3f}] Mbps")
    print(f"中位数: {np.median(loss_bwe):.3f} Mbps")

    print(f"\n" + "-"*80)
    print("FINAL BWE (最终带宽) 统计")
    print("-"*80)
    print(f"均值: {np.mean(final_bwe):.3f} Mbps")
    print(f"标准差: {np.std(final_bwe):.3f} Mbps")
    print(f"范围: [{np.min(final_bwe):.3f}, {np.max(final_bwe):.3f}] Mbps")

    # Correlation analysis
    print(f"\n" + "="*80)
    print("相关性分析")
    print("="*80)

    # Ratio vs Delay-based BWE
    corr_delay, p_delay = stats.pearsonr(smoothed_ratios, delay_bwe)
    print(f"\n📊 Smoothed Ratio vs Delay-Based BWE:")
    print(f"   Pearson相关系数: {corr_delay:.4f} (p={p_delay:.4e})")

    # Ratio vs Loss-based BWE
    corr_loss, p_loss = stats.pearsonr(smoothed_ratios, loss_bwe)
    print(f"\n📊 Smoothed Ratio vs Loss-Based BWE:")
    print(f"   Pearson相关系数: {corr_loss:.4f} (p={p_loss:.4e})")

    # Ratio vs Final BWE
    corr_final, p_final = stats.pearsonr(smoothed_ratios, final_bwe)
    print(f"\n📊 Smoothed Ratio vs Final BWE:")
    print(f"   Pearson相关系数: {corr_final:.4f} (p={p_final:.4e})")

    # Delay vs Loss BWE
    corr_bwe, p_bwe = stats.pearsonr(delay_bwe, loss_bwe)
    print(f"\n📊 Delay-Based BWE vs Loss-Based BWE:")
    print(f"   Pearson相关系数: {corr_bwe:.4f} (p={p_bwe:.4e})")

    # Analyze which BWE is limiting
    print(f"\n" + "-"*80)
    print("BWE限制分析 (哪个估计器在起主导作用)")
    print("-"*80)

    delay_limiting = np.sum(delay_bwe <= loss_bwe)
    loss_limiting = np.sum(loss_bwe < delay_bwe)

    print(f"Delay-based限制: {delay_limiting} ({100*delay_limiting/len(delay_bwe):.1f}%)")
    print(f"Loss-based限制: {loss_limiting} ({100*loss_limiting/len(delay_bwe):.1f}%)")

    # Analyze by ratio ranges
    print(f"\n" + "-"*80)
    print("不同Ratio范围的BWE表现")
    print("-"*80)

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
            print(f"\n{label}: ({np.sum(mask)}个样本, {100*np.sum(mask)/len(smoothed_ratios):.1f}%)")
            print(f"  Delay-BWE: {np.mean(delay_bwe[mask]):.3f} ± {np.std(delay_bwe[mask]):.3f} Mbps")
            print(f"  Loss-BWE:  {np.mean(loss_bwe[mask]):.3f} ± {np.std(loss_bwe[mask]):.3f} Mbps")
            print(f"  Final-BWE: {np.mean(final_bwe[mask]):.3f} ± {np.std(final_bwe[mask]):.3f} Mbps")

    # BWE difference analysis
    bwe_diff = loss_bwe - delay_bwe
    print(f"\n" + "-"*80)
    print("Loss-BWE vs Delay-BWE 差异分析")
    print("-"*80)
    print(f"平均差异: {np.mean(bwe_diff):.3f} Mbps")
    print(f"标准差: {np.std(bwe_diff):.3f} Mbps")
    print(f"范围: [{np.min(bwe_diff):.3f}, {np.max(bwe_diff):.3f}] Mbps")

    return {
        'smoothed_ratios': smoothed_ratios,
        'raw_ratios': raw_ratios,
        'trends': trends,
        'delay_bwe': delay_bwe,
        'loss_bwe': loss_bwe,
        'final_bwe': final_bwe
    }

def plot_dual_bwe_analysis(data):
    """Create comprehensive visualization with both BWE estimates"""

    smoothed_ratios = data['smoothed_ratios']
    delay_bwe = data['delay_bwe']
    loss_bwe = data['loss_bwe']
    final_bwe = data['final_bwe']
    trends = data['trends']

    fig = plt.figure(figsize=(20, 16))
    gs = fig.add_gridspec(4, 3, hspace=0.4, wspace=0.35)

    # Plot 1: Time series comparison of all BWE
    ax1 = fig.add_subplot(gs[0, :])
    indices = range(len(delay_bwe))
    ax1.plot(indices, delay_bwe, linewidth=1.5, alpha=0.8, label='Delay-Based BWE', color='blue')
    ax1.plot(indices, loss_bwe, linewidth=1.5, alpha=0.8, label='Loss-Based BWE', color='red')
    ax1.plot(indices, final_bwe, linewidth=2, alpha=0.6, label='Final BWE', color='green')
    ax1.set_xlabel('Ratio Update Index', fontsize=11)
    ax1.set_ylabel('Bandwidth (Mbps)', fontsize=11)
    ax1.set_title('Delay-Based vs Loss-Based vs Final BWE Over Time',
                  fontsize=13, fontweight='bold')
    ax1.legend(fontsize=11, loc='best')
    ax1.grid(True, alpha=0.3)

    # Plot 2: Ratio time series
    ax2 = fig.add_subplot(gs[1, :])
    ax2.plot(smoothed_ratios, linewidth=1, alpha=0.7, color='purple')
    ax2.axhline(y=1.0, color='r', linestyle='--', linewidth=2, alpha=0.5, label='Target')
    ax2.fill_between(range(len(smoothed_ratios)), 0.9, 1.1, alpha=0.15, color='green')
    ax2.set_xlabel('Ratio Update Index', fontsize=11)
    ax2.set_ylabel('Smoothed Ratio', fontsize=11)
    ax2.set_title('Smoothed Ratio Over Time', fontsize=13, fontweight='bold')
    ax2.legend(fontsize=10)
    ax2.grid(True, alpha=0.3)

    # Plot 3: Ratio vs Delay-BWE scatter
    ax3 = fig.add_subplot(gs[2, 0])
    ax3.scatter(smoothed_ratios, delay_bwe, alpha=0.3, s=15, c='blue', edgecolors='none')

    z = np.polyfit(smoothed_ratios, delay_bwe, 1)
    p = np.poly1d(z)
    ratio_line = np.linspace(smoothed_ratios.min(), smoothed_ratios.max(), 100)
    ax3.plot(ratio_line, p(ratio_line), "r--", linewidth=2,
             label=f'y = {z[0]:.3f}x + {z[1]:.3f}')

    corr, _ = stats.pearsonr(smoothed_ratios, delay_bwe)
    ax3.text(0.05, 0.95, f'r = {corr:.4f}',
             transform=ax3.transAxes, fontsize=10, fontweight='bold',
             verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))

    ax3.set_xlabel('Smoothed Ratio', fontsize=11)
    ax3.set_ylabel('Delay-Based BWE (Mbps)', fontsize=11)
    ax3.set_title('Ratio vs Delay-Based BWE', fontsize=12, fontweight='bold')
    ax3.legend(fontsize=9)
    ax3.grid(True, alpha=0.3)

    # Plot 4: Ratio vs Loss-BWE scatter
    ax4 = fig.add_subplot(gs[2, 1])
    ax4.scatter(smoothed_ratios, loss_bwe, alpha=0.3, s=15, c='red', edgecolors='none')

    z = np.polyfit(smoothed_ratios, loss_bwe, 1)
    p = np.poly1d(z)
    ax4.plot(ratio_line, p(ratio_line), "b--", linewidth=2,
             label=f'y = {z[0]:.3f}x + {z[1]:.3f}')

    corr, _ = stats.pearsonr(smoothed_ratios, loss_bwe)
    ax4.text(0.05, 0.95, f'r = {corr:.4f}',
             transform=ax4.transAxes, fontsize=10, fontweight='bold',
             verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='lightcoral', alpha=0.8))

    ax4.set_xlabel('Smoothed Ratio', fontsize=11)
    ax4.set_ylabel('Loss-Based BWE (Mbps)', fontsize=11)
    ax4.set_title('Ratio vs Loss-Based BWE', fontsize=12, fontweight='bold')
    ax4.legend(fontsize=9)
    ax4.grid(True, alpha=0.3)

    # Plot 5: Ratio vs Final BWE
    ax5 = fig.add_subplot(gs[2, 2])
    ax5.scatter(smoothed_ratios, final_bwe, alpha=0.3, s=15, c='green', edgecolors='none')

    z = np.polyfit(smoothed_ratios, final_bwe, 1)
    p = np.poly1d(z)
    ax5.plot(ratio_line, p(ratio_line), "r--", linewidth=2,
             label=f'y = {z[0]:.3f}x + {z[1]:.3f}')

    corr, _ = stats.pearsonr(smoothed_ratios, final_bwe)
    ax5.text(0.05, 0.95, f'r = {corr:.4f}',
             transform=ax5.transAxes, fontsize=10, fontweight='bold',
             verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.8))

    ax5.set_xlabel('Smoothed Ratio', fontsize=11)
    ax5.set_ylabel('Final BWE (Mbps)', fontsize=11)
    ax5.set_title('Ratio vs Final BWE', fontsize=12, fontweight='bold')
    ax5.legend(fontsize=9)
    ax5.grid(True, alpha=0.3)

    # Plot 6: Delay vs Loss BWE
    ax6 = fig.add_subplot(gs[3, 0])
    ax6.scatter(delay_bwe, loss_bwe, alpha=0.3, s=15, c=smoothed_ratios,
                cmap='viridis', edgecolors='none')

    # Add diagonal line (where delay = loss)
    min_val = min(delay_bwe.min(), loss_bwe.min())
    max_val = max(delay_bwe.max(), loss_bwe.max())
    ax6.plot([min_val, max_val], [min_val, max_val], 'r--', linewidth=2,
             alpha=0.5, label='Equal line')

    corr, _ = stats.pearsonr(delay_bwe, loss_bwe)
    ax6.text(0.05, 0.95, f'r = {corr:.4f}',
             transform=ax6.transAxes, fontsize=10, fontweight='bold',
             verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    ax6.set_xlabel('Delay-Based BWE (Mbps)', fontsize=11)
    ax6.set_ylabel('Loss-Based BWE (Mbps)', fontsize=11)
    ax6.set_title('Delay-BWE vs Loss-BWE', fontsize=12, fontweight='bold')
    ax6.legend(fontsize=9)
    ax6.grid(True, alpha=0.3)

    cbar = plt.colorbar(ax6.collections[0], ax=ax6)
    cbar.set_label('Smoothed Ratio', fontsize=10)

    # Plot 7: BWE difference vs Ratio
    ax7 = fig.add_subplot(gs[3, 1])
    bwe_diff = loss_bwe - delay_bwe
    ax7.scatter(smoothed_ratios, bwe_diff, alpha=0.4, s=15, c='purple', edgecolors='none')
    ax7.axhline(y=0, color='r', linestyle='--', linewidth=2, alpha=0.5)
    ax7.set_xlabel('Smoothed Ratio', fontsize=11)
    ax7.set_ylabel('Loss-BWE - Delay-BWE (Mbps)', fontsize=11)
    ax7.set_title('BWE Difference vs Ratio', fontsize=12, fontweight='bold')
    ax7.grid(True, alpha=0.3)

    # Plot 8: Box plot comparison
    ax8 = fig.add_subplot(gs[3, 2])

    categories = []
    for r in smoothed_ratios:
        if r < 0.9:
            categories.append('Low\n(<0.9)')
        elif r <= 1.1:
            categories.append('Normal\n(0.9-1.1)')
        else:
            categories.append('High\n(>1.1)')

    # Organize data by category and BWE type
    data_dict = {}
    for cat in ['Low\n(<0.9)', 'Normal\n(0.9-1.1)', 'High\n(>1.1)']:
        mask = np.array([c == cat for c in categories])
        if np.sum(mask) > 0:
            data_dict[f'{cat}\nDelay'] = delay_bwe[mask]
            data_dict[f'{cat}\nLoss'] = loss_bwe[mask]

    bp = ax8.boxplot(data_dict.values(), labels=data_dict.keys(), patch_artist=True)

    # Color boxes
    colors = ['lightblue', 'lightcoral'] * 3
    for patch, color in zip(bp['boxes'], colors[:len(bp['boxes'])]):
        patch.set_facecolor(color)

    ax8.set_ylabel('Bandwidth (Mbps)', fontsize=11)
    ax8.set_title('BWE by Ratio Category', fontsize=12, fontweight='bold')
    ax8.tick_params(axis='x', rotation=45)
    ax8.grid(True, alpha=0.3, axis='y')

    # Overall title
    fig.suptitle('Complete Analysis: Smoothed Ratio vs Delay-Based & Loss-Based BWE',
                 fontsize=16, fontweight='bold', y=0.998)

    output_path = '/home/wuq/webrtc-local/webrtc_config_results/ratio_dual_bwe_analysis.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n📊 完整双BWE分析图表已保存至: {output_path}")

def main():
    log_path = '/home/wuq/webrtc-local/webrtc_config_results/sender_local.log'

    print(f"解析日志文件: {log_path}")
    events = parse_dual_bwe_log(log_path)

    print(f"总事件数: {len(events)}")

    # Analyze
    data = analyze_dual_bwe(events)

    # Plot
    if data is not None:
        plot_dual_bwe_analysis(data)

if __name__ == '__main__':
    main()

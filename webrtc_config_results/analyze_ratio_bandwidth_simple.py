#!/usr/bin/env python3
"""
Analyze the relationship between smoothed ratio and bandwidth from WebRTC logs
Uses line-based synchronization instead of timestamps
"""

import re
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

def parse_log_sequential(log_path):
    """Parse the log file sequentially to capture ratio and bandwidth changes"""

    # Patterns
    ratio_pattern = r'Resource ratio updated: ([\d.]+) \(smoothed: ([\d.]+)\), trend: ([-\d.]+)'
    aimd_update_pattern = r'\[AIMD-Update\].*Current bitrate: (\d+) bps'
    throughput_pattern = r'Estimated throughput: (\d+) bps'
    growth_pattern = r'\[AIMD-Cellular-L4\].*Ratio: ([\d.]+), Consecutive count: (\d+)'

    # Sequential data storage
    events = []
    current_bitrate = None
    current_throughput = None

    line_num = 0
    with open(log_path, 'r') as f:
        for line in f:
            line_num += 1

            # Track current bitrate
            aimd_match = re.search(aimd_update_pattern, line)
            if aimd_match:
                current_bitrate = int(aimd_match.group(1))

            # Track throughput
            throughput_match = re.search(throughput_pattern, line)
            if throughput_match:
                current_throughput = int(throughput_match.group(1))

            # Capture ratio updates with associated bitrate
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
                    'bitrate': current_bitrate,
                    'throughput': current_throughput
                })

            # Capture growth events
            growth_match = re.search(growth_pattern, line)
            if growth_match:
                ratio = float(growth_match.group(1))
                count = int(growth_match.group(2))

                events.append({
                    'line': line_num,
                    'type': 'growth',
                    'ratio': ratio,
                    'count': count,
                    'bitrate': current_bitrate
                })

    return events

def analyze_events(events):
    """Analyze the relationship between ratio and bandwidth"""

    ratio_events = [e for e in events if e['type'] == 'ratio' and e['bitrate'] is not None]
    growth_events = [e for e in events if e['type'] == 'growth']

    print("\n" + "="*70)
    print("RATIO AND BANDWIDTH ANALYSIS")
    print("="*70)

    if not ratio_events:
        print("No ratio events with bandwidth data found")
        return None

    print(f"\nTotal ratio events with bandwidth: {len(ratio_events)}")

    # Extract data arrays
    smoothed_ratios = [e['smoothed_ratio'] for e in ratio_events]
    raw_ratios = [e['raw_ratio'] for e in ratio_events]
    trends = [e['trend'] for e in ratio_events]
    bitrates = [e['bitrate'] / 1e6 for e in ratio_events]  # Convert to Mbps
    throughputs = [e['throughput'] / 1e6 if e['throughput'] else None for e in ratio_events]

    # Basic statistics
    print(f"\n" + "-"*70)
    print("SMOOTHED RATIO STATISTICS")
    print("-"*70)
    print(f"Mean: {np.mean(smoothed_ratios):.3f}")
    print(f"Std dev: {np.std(smoothed_ratios):.3f}")
    print(f"Min: {np.min(smoothed_ratios):.3f}")
    print(f"Max: {np.max(smoothed_ratios):.3f}")
    print(f"Median: {np.median(smoothed_ratios):.3f}")

    print(f"\n" + "-"*70)
    print("BANDWIDTH STATISTICS")
    print("-"*70)
    print(f"Mean: {np.mean(bitrates):.3f} Mbps")
    print(f"Std dev: {np.std(bitrates):.3f} Mbps")
    print(f"Min: {np.min(bitrates):.3f} Mbps")
    print(f"Max: {np.max(bitrates):.3f} Mbps")
    print(f"Median: {np.median(bitrates):.3f} Mbps")

    # Correlation analysis
    print(f"\n" + "-"*70)
    print("CORRELATION ANALYSIS")
    print("-"*70)

    correlation, p_value = stats.pearsonr(smoothed_ratios, bitrates)
    print(f"\nPearson correlation (Smoothed Ratio vs Bandwidth): {correlation:.4f}")
    print(f"P-value: {p_value:.4e}")
    if abs(correlation) < 0.3:
        print("→ Weak correlation")
    elif abs(correlation) < 0.7:
        print("→ Moderate correlation")
    else:
        print("→ Strong correlation")

    spearman_corr, spearman_p = stats.spearmanr(smoothed_ratios, bitrates)
    print(f"\nSpearman correlation: {spearman_corr:.4f}")
    print(f"P-value: {spearman_p:.4e}")

    # Analyze by ratio ranges
    print(f"\n" + "-"*70)
    print("BANDWIDTH BY RATIO RANGE")
    print("-"*70)

    ratio_ranges = [
        (0.0, 0.7, "Very Low (< 0.7)"),
        (0.7, 0.9, "Low (0.7-0.9)"),
        (0.9, 1.1, "Normal (0.9-1.1)"),
        (1.1, 1.3, "High (1.1-1.3)"),
        (1.3, 2.0, "Very High (> 1.3)")
    ]

    for low, high, label in ratio_ranges:
        indices = [i for i, r in enumerate(smoothed_ratios) if low <= r < high]
        if indices:
            bw_subset = [bitrates[i] for i in indices]
            print(f"\n{label}:")
            print(f"  Samples: {len(bw_subset)} ({100*len(bw_subset)/len(bitrates):.1f}%)")
            print(f"  Mean bandwidth: {np.mean(bw_subset):.3f} Mbps")
            print(f"  Std dev: {np.std(bw_subset):.3f} Mbps")
            print(f"  Range: [{np.min(bw_subset):.3f}, {np.max(bw_subset):.3f}] Mbps")

    # Analyze trend direction
    print(f"\n" + "-"*70)
    print("TREND ANALYSIS")
    print("-"*70)

    positive_trends = [i for i, t in enumerate(trends) if t > 0]
    negative_trends = [i for i, t in enumerate(trends) if t < 0]

    if positive_trends:
        pos_bw = [bitrates[i] for i in positive_trends]
        print(f"\nPositive trends ({len(positive_trends)} samples, {100*len(positive_trends)/len(trends):.1f}%):")
        print(f"  Mean bandwidth: {np.mean(pos_bw):.3f} Mbps")

    if negative_trends:
        neg_bw = [bitrates[i] for i in negative_trends]
        print(f"\nNegative trends ({len(negative_trends)} samples, {100*len(negative_trends)/len(trends):.1f}%):")
        print(f"  Mean bandwidth: {np.mean(neg_bw):.3f} Mbps")

    # Analyze growth events
    if growth_events:
        print(f"\n" + "-"*70)
        print("MULTIPLICATIVE GROWTH EVENTS")
        print("-"*70)
        print(f"\nTotal growth events: {len(growth_events)}")

        growth_ratios = [e['ratio'] for e in growth_events]
        growth_bitrates = [e['bitrate'] / 1e6 for e in growth_events if e['bitrate']]

        print(f"\nRatio at growth events:")
        print(f"  Mean: {np.mean(growth_ratios):.3f}")
        print(f"  Range: [{np.min(growth_ratios):.3f}, {np.max(growth_ratios):.3f}]")

        if growth_bitrates:
            print(f"\nBandwidth at growth events:")
            print(f"  Mean: {np.mean(growth_bitrates):.3f} Mbps")
            print(f"  Range: [{np.min(growth_bitrates):.3f}, {np.max(growth_bitrates):.3f}] Mbps")

    return {
        'smoothed_ratios': smoothed_ratios,
        'raw_ratios': raw_ratios,
        'trends': trends,
        'bitrates': bitrates,
        'throughputs': throughputs
    }

def plot_analysis(data):
    """Create comprehensive visualization"""

    if not data:
        print("No data to plot")
        return

    smoothed_ratios = data['smoothed_ratios']
    raw_ratios = data['raw_ratios']
    trends = data['trends']
    bitrates = data['bitrates']

    fig = plt.figure(figsize=(18, 12))
    gs = fig.add_gridspec(3, 3, hspace=0.35, wspace=0.35)

    # Plot 1: Time series of smoothed ratio
    ax1 = fig.add_subplot(gs[0, :2])
    ax1.plot(smoothed_ratios, linewidth=1, alpha=0.7, label='Smoothed Ratio')
    ax1.axhline(y=1.0, color='r', linestyle='--', alpha=0.5, label='Target (1.0)')
    ax1.fill_between(range(len(smoothed_ratios)), 0.9, 1.1, alpha=0.1, color='green')
    ax1.set_xlabel('Event Index')
    ax1.set_ylabel('Smoothed Ratio')
    ax1.set_title('Smoothed Ratio Over Events', fontsize=12, fontweight='bold')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Plot 2: Time series of bandwidth
    ax2 = fig.add_subplot(gs[1, :2])
    ax2.plot(bitrates, linewidth=1, alpha=0.7, color='orange', label='Bandwidth')
    ax2.set_xlabel('Event Index')
    ax2.set_ylabel('Bandwidth (Mbps)')
    ax2.set_title('Bandwidth Over Events', fontsize=12, fontweight='bold')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # Plot 3: Scatter plot with regression
    ax3 = fig.add_subplot(gs[0, 2])
    ax3.scatter(smoothed_ratios, bitrates, alpha=0.3, s=10, c='blue')

    # Add regression line
    z = np.polyfit(smoothed_ratios, bitrates, 1)
    p = np.poly1d(z)
    ratio_line = np.linspace(min(smoothed_ratios), max(smoothed_ratios), 100)
    ax3.plot(ratio_line, p(ratio_line), "r--", linewidth=2,
             label=f'y = {z[0]:.3f}x + {z[1]:.3f}')

    correlation, _ = stats.pearsonr(smoothed_ratios, bitrates)
    ax3.text(0.05, 0.95, f'r = {correlation:.3f}',
             transform=ax3.transAxes, fontsize=10,
             verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    ax3.set_xlabel('Smoothed Ratio')
    ax3.set_ylabel('Bandwidth (Mbps)')
    ax3.set_title('Correlation: Ratio vs Bandwidth', fontsize=12, fontweight='bold')
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    # Plot 4: Distribution of ratios
    ax4 = fig.add_subplot(gs[1, 2])
    ax4.hist(smoothed_ratios, bins=50, edgecolor='black', alpha=0.7, color='skyblue')
    ax4.axvline(x=1.0, color='r', linestyle='--', linewidth=2, label='Target')
    ax4.axvline(x=np.mean(smoothed_ratios), color='g', linestyle='--',
                linewidth=2, label=f'Mean ({np.mean(smoothed_ratios):.2f})')
    ax4.set_xlabel('Smoothed Ratio')
    ax4.set_ylabel('Frequency')
    ax4.set_title('Ratio Distribution', fontsize=12, fontweight='bold')
    ax4.legend()
    ax4.grid(True, alpha=0.3, axis='y')

    # Plot 5: Box plot by ratio category
    ax5 = fig.add_subplot(gs[2, 0])
    categories = []
    for r in smoothed_ratios:
        if r < 0.9:
            categories.append('Low')
        elif r <= 1.1:
            categories.append('Normal')
        else:
            categories.append('High')

    data_by_cat = {'Low': [], 'Normal': [], 'High': []}
    for cat, bw in zip(categories, bitrates):
        data_by_cat[cat].append(bw)

    # Filter out empty categories
    plot_data = [v for v in data_by_cat.values() if v]
    plot_labels = [k for k, v in data_by_cat.items() if v]

    bp = ax5.boxplot(plot_data, labels=plot_labels, patch_artist=True)
    for patch, color in zip(bp['boxes'], ['lightcoral', 'lightgreen', 'lightyellow']):
        patch.set_facecolor(color)

    ax5.set_ylabel('Bandwidth (Mbps)')
    ax5.set_title('Bandwidth by Ratio Category', fontsize=12, fontweight='bold')
    ax5.grid(True, alpha=0.3, axis='y')

    # Plot 6: Bandwidth distribution by ratio range
    ax6 = fig.add_subplot(gs[2, 1])
    low_bw = [bitrates[i] for i, r in enumerate(smoothed_ratios) if r < 0.9]
    normal_bw = [bitrates[i] for i, r in enumerate(smoothed_ratios) if 0.9 <= r <= 1.1]
    high_bw = [bitrates[i] for i, r in enumerate(smoothed_ratios) if r > 1.1]

    data_to_plot = []
    labels_to_plot = []
    if low_bw:
        data_to_plot.append(low_bw)
        labels_to_plot.append(f'Low\n(n={len(low_bw)})')
    if normal_bw:
        data_to_plot.append(normal_bw)
        labels_to_plot.append(f'Normal\n(n={len(normal_bw)})')
    if high_bw:
        data_to_plot.append(high_bw)
        labels_to_plot.append(f'High\n(n={len(high_bw)})')

    ax6.hist(data_to_plot, label=labels_to_plot, bins=20, alpha=0.7)
    ax6.set_xlabel('Bandwidth (Mbps)')
    ax6.set_ylabel('Frequency')
    ax6.set_title('Bandwidth Distribution by Range', fontsize=12, fontweight='bold')
    ax6.legend()
    ax6.grid(True, alpha=0.3, axis='y')

    # Plot 7: Raw vs Smoothed ratio (sample)
    ax7 = fig.add_subplot(gs[2, 2])
    sample_size = min(300, len(raw_ratios))
    indices = range(sample_size)
    ax7.plot(indices, raw_ratios[:sample_size], alpha=0.4, linewidth=1, label='Raw')
    ax7.plot(indices, smoothed_ratios[:sample_size], linewidth=2, label='Smoothed')
    ax7.axhline(y=1.0, color='r', linestyle='--', alpha=0.5)
    ax7.set_xlabel('Event Index')
    ax7.set_ylabel('Ratio')
    ax7.set_title(f'Raw vs Smoothed (First {sample_size} events)', fontsize=12, fontweight='bold')
    ax7.legend()
    ax7.grid(True, alpha=0.3)

    # Overall title
    fig.suptitle('WebRTC Cellular Ratio vs Bandwidth Analysis',
                 fontsize=16, fontweight='bold', y=0.995)

    output_path = '/home/wuq/webrtc-local/webrtc_config_results/ratio_bandwidth_relationship.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n📊 Analysis plot saved to: {output_path}")

def main():
    log_path = '/home/wuq/webrtc-local/webrtc_config_results/sender_local.log'

    print(f"Parsing log file: {log_path}")
    events = parse_log_sequential(log_path)

    print(f"Total events captured: {len(events)}")

    # Analyze the data
    data = analyze_events(events)

    # Create plots
    if data:
        plot_analysis(data)

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Deep analysis of the correlation between smoothed ratio and bandwidth estimation
"""

import re
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats
from datetime import datetime

def parse_log_with_timestamps(log_path):
    """Parse the log file and extract ratio, bandwidth, and AIMD update data with timestamps"""

    # Patterns
    ratio_pattern = r'\[(\d+\.\d+)\].*Resource ratio updated: ([\d.]+) \(smoothed: ([\d.]+)\), trend: ([-\d.]+)'
    aimd_update_pattern = r'\[(\d+\.\d+)\].*\[AIMD-Update\].*Current bitrate: (\d+) bps'
    probe_result_pattern = r'\[(\d+\.\d+)\].*\[ProbeBWE-Result\].*Final estimate: (\d+) bps'
    sendбwe_pattern = r'\[(\d+\.\d+)\].*\[SendBWE-Loss\].*Current target: (\d+) bps'
    increase_pattern = r'\[AIMD-Increase\].*Increase limit: (\d+) bps, Current: (\d+) bps'
    multiplicative_growth_pattern = r'\[AIMD-Cellular-L4\].*Ratio: ([\d.]+), Consecutive count: (\d+)'

    # Data storage
    ratio_data = []
    bitrate_data = []
    aimd_updates = []
    probe_results = []
    send_bwe_updates = []
    growth_events = []

    with open(log_path, 'r') as f:
        for line in f:
            # Extract ratio data
            ratio_match = re.search(ratio_pattern, line)
            if ratio_match:
                timestamp = float(ratio_match.group(1))
                raw_ratio = float(ratio_match.group(2))
                smoothed_ratio = float(ratio_match.group(3))
                trend = float(ratio_match.group(4))

                ratio_data.append({
                    'timestamp': timestamp,
                    'raw_ratio': raw_ratio,
                    'smoothed_ratio': smoothed_ratio,
                    'trend': trend
                })

            # Extract AIMD update data
            aimd_match = re.search(aimd_update_pattern, line)
            if aimd_match:
                timestamp = float(aimd_match.group(1))
                current_bitrate = int(aimd_match.group(2))

                aimd_updates.append({
                    'timestamp': timestamp,
                    'bitrate': current_bitrate
                })

            # Extract probe results
            probe_match = re.search(probe_result_pattern, line)
            if probe_match:
                timestamp = float(probe_match.group(1))
                estimate = int(probe_match.group(2))

                probe_results.append({
                    'timestamp': timestamp,
                    'estimate': estimate
                })

            # Extract SendBWE updates
            send_match = re.search(sendбwe_pattern, line)
            if send_match:
                timestamp = float(send_match.group(1))
                target = int(send_match.group(2))

                send_bwe_updates.append({
                    'timestamp': timestamp,
                    'target': target
                })

            # Extract multiplicative growth events
            growth_match = re.search(multiplicative_growth_pattern, line)
            if growth_match:
                ratio = float(growth_match.group(1))
                count = int(growth_match.group(2))

                growth_events.append({
                    'ratio': ratio,
                    'count': count
                })

    return {
        'ratio_data': ratio_data,
        'aimd_updates': aimd_updates,
        'probe_results': probe_results,
        'send_bwe_updates': send_bwe_updates,
        'growth_events': growth_events
    }

def align_data(ratio_data, bitrate_data):
    """Align ratio and bitrate data based on timestamps"""

    if not ratio_data or not bitrate_data:
        return [], []

    aligned_ratios = []
    aligned_bitrates = []

    # Use nearest neighbor matching
    for ratio_entry in ratio_data:
        ratio_ts = ratio_entry['timestamp']

        # Find nearest bitrate update
        min_diff = float('inf')
        nearest_bitrate = None

        for bitrate_entry in bitrate_data:
            bitrate_ts = bitrate_entry['timestamp']
            diff = abs(ratio_ts - bitrate_ts)

            if diff < min_diff and diff < 1.0:  # Within 1 second
                min_diff = diff
                nearest_bitrate = bitrate_entry['bitrate']

        if nearest_bitrate is not None:
            aligned_ratios.append(ratio_entry['smoothed_ratio'])
            aligned_bitrates.append(nearest_bitrate)

    return aligned_ratios, aligned_bitrates

def analyze_correlation(data):
    """Analyze correlation between ratio and bandwidth"""

    ratio_data = data['ratio_data']
    aimd_updates = data['aimd_updates']
    growth_events = data['growth_events']

    print("\n" + "="*70)
    print("CORRELATION ANALYSIS: SMOOTHED RATIO vs BANDWIDTH")
    print("="*70)

    # Align data
    aligned_ratios, aligned_bitrates = align_data(ratio_data, aimd_updates)

    if len(aligned_ratios) > 0:
        print(f"\nAligned data points: {len(aligned_ratios)}")

        # Convert to Mbps for easier interpretation
        aligned_bitrates_mbps = [b / 1e6 for b in aligned_bitrates]

        # Calculate correlation
        correlation, p_value = stats.pearsonr(aligned_ratios, aligned_bitrates_mbps)
        print(f"\nPearson correlation: {correlation:.4f} (p-value: {p_value:.4e})")

        # Spearman correlation (non-linear)
        spearman_corr, spearman_p = stats.spearmanr(aligned_ratios, aligned_bitrates_mbps)
        print(f"Spearman correlation: {spearman_corr:.4f} (p-value: {spearman_p:.4e})")

        # Analyze by ratio ranges
        print(f"\n" + "-"*70)
        print("BANDWIDTH BY RATIO RANGE")
        print("-"*70)

        ratio_ranges = [
            (0.0, 0.5, "Very Low (< 0.5)"),
            (0.5, 0.9, "Low (0.5-0.9)"),
            (0.9, 1.1, "Normal (0.9-1.1)"),
            (1.1, 1.5, "High (1.1-1.5)"),
            (1.5, 2.0, "Very High (> 1.5)")
        ]

        for low, high, label in ratio_ranges:
            indices = [i for i, r in enumerate(aligned_ratios) if low <= r < high]
            if indices:
                bw_subset = [aligned_bitrates_mbps[i] for i in indices]
                print(f"\n{label}:")
                print(f"  Samples: {len(bw_subset)}")
                print(f"  Mean bandwidth: {np.mean(bw_subset):.3f} Mbps")
                print(f"  Std dev: {np.std(bw_subset):.3f} Mbps")
                print(f"  Min: {np.min(bw_subset):.3f} Mbps")
                print(f"  Max: {np.max(bw_subset):.3f} Mbps")

    # Analyze multiplicative growth events
    if growth_events:
        print(f"\n" + "-"*70)
        print("MULTIPLICATIVE GROWTH EVENTS")
        print("-"*70)
        print(f"\nTotal growth events: {len(growth_events)}")

        ratios_at_growth = [e['ratio'] for e in growth_events]
        counts_at_growth = [e['count'] for e in growth_events]

        print(f"Ratio at growth - Mean: {np.mean(ratios_at_growth):.3f}, "
              f"Min: {np.min(ratios_at_growth):.3f}, Max: {np.max(ratios_at_growth):.3f}")
        print(f"Consecutive count - Mean: {np.mean(counts_at_growth):.1f}, "
              f"Min: {np.min(counts_at_growth)}, Max: {np.max(counts_at_growth)}")

    # Bandwidth statistics
    if aimd_updates:
        all_bitrates = [u['bitrate'] / 1e6 for u in aimd_updates]
        print(f"\n" + "-"*70)
        print("OVERALL BANDWIDTH STATISTICS")
        print("-"*70)
        print(f"\nBandwidth samples: {len(all_bitrates)}")
        print(f"Mean: {np.mean(all_bitrates):.3f} Mbps")
        print(f"Std dev: {np.std(all_bitrates):.3f} Mbps")
        print(f"Min: {np.min(all_bitrates):.3f} Mbps")
        print(f"Max: {np.max(all_bitrates):.3f} Mbps")
        print(f"Median: {np.median(all_bitrates):.3f} Mbps")

    return aligned_ratios, aligned_bitrates

def plot_correlation(data, aligned_ratios, aligned_bitrates):
    """Create comprehensive correlation plots"""

    ratio_data = data['ratio_data']
    aimd_updates = data['aimd_updates']

    if not ratio_data or not aimd_updates:
        print("Insufficient data for plotting")
        return

    fig = plt.figure(figsize=(18, 12))
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

    # Plot 1: Time series of smoothed ratio
    ax1 = fig.add_subplot(gs[0, :2])
    timestamps_ratio = [r['timestamp'] for r in ratio_data]
    smoothed_ratios = [r['smoothed_ratio'] for r in ratio_data]

    if timestamps_ratio:
        start_time = timestamps_ratio[0]
        relative_times = [(t - start_time) for t in timestamps_ratio]

        ax1.plot(relative_times, smoothed_ratios, linewidth=1, alpha=0.7, label='Smoothed Ratio')
        ax1.axhline(y=1.0, color='r', linestyle='--', alpha=0.5, label='Target (1.0)')
        ax1.fill_between(relative_times, 0.9, 1.1, alpha=0.1, color='green', label='Normal range')
        ax1.set_xlabel('Time (seconds)')
        ax1.set_ylabel('Smoothed Ratio')
        ax1.set_title('Smoothed Ratio Over Time')
        ax1.legend(loc='upper right')
        ax1.grid(True, alpha=0.3)

    # Plot 2: Time series of bandwidth
    ax2 = fig.add_subplot(gs[1, :2])
    timestamps_bw = [u['timestamp'] for u in aimd_updates]
    bitrates = [u['bitrate'] / 1e6 for u in aimd_updates]

    if timestamps_bw:
        start_time = timestamps_bw[0]
        relative_times_bw = [(t - start_time) for t in timestamps_bw]

        ax2.plot(relative_times_bw, bitrates, linewidth=1, alpha=0.7, color='orange')
        ax2.set_xlabel('Time (seconds)')
        ax2.set_ylabel('Bandwidth (Mbps)')
        ax2.set_title('Bandwidth Estimation Over Time')
        ax2.grid(True, alpha=0.3)

    # Plot 3: Scatter plot of ratio vs bandwidth
    ax3 = fig.add_subplot(gs[0:2, 2])
    if len(aligned_ratios) > 0 and len(aligned_bitrates) > 0:
        aligned_bitrates_mbps = [b / 1e6 for b in aligned_bitrates]

        ax3.scatter(aligned_ratios, aligned_bitrates_mbps, alpha=0.3, s=10)

        # Add regression line
        z = np.polyfit(aligned_ratios, aligned_bitrates_mbps, 1)
        p = np.poly1d(z)
        ratio_line = np.linspace(min(aligned_ratios), max(aligned_ratios), 100)
        ax3.plot(ratio_line, p(ratio_line), "r--", linewidth=2, label=f'Linear fit: y={z[0]:.2f}x+{z[1]:.2f}')

        ax3.set_xlabel('Smoothed Ratio')
        ax3.set_ylabel('Bandwidth (Mbps)')
        ax3.set_title('Ratio vs Bandwidth Correlation')
        ax3.legend()
        ax3.grid(True, alpha=0.3)

    # Plot 4: Histogram of bandwidth by ratio range
    ax4 = fig.add_subplot(gs[2, 0])
    if len(aligned_ratios) > 0:
        aligned_bitrates_mbps = [b / 1e6 for b in aligned_bitrates]

        low_ratio_bw = [aligned_bitrates_mbps[i] for i, r in enumerate(aligned_ratios) if r < 0.9]
        normal_ratio_bw = [aligned_bitrates_mbps[i] for i, r in enumerate(aligned_ratios) if 0.9 <= r <= 1.1]
        high_ratio_bw = [aligned_bitrates_mbps[i] for i, r in enumerate(aligned_ratios) if r > 1.1]

        ax4.hist([low_ratio_bw, normal_ratio_bw, high_ratio_bw],
                label=['Low (<0.9)', 'Normal (0.9-1.1)', 'High (>1.1)'],
                bins=20, alpha=0.7)
        ax4.set_xlabel('Bandwidth (Mbps)')
        ax4.set_ylabel('Frequency')
        ax4.set_title('Bandwidth Distribution by Ratio Range')
        ax4.legend()
        ax4.grid(True, alpha=0.3)

    # Plot 5: Box plot of bandwidth by ratio category
    ax5 = fig.add_subplot(gs[2, 1])
    if len(aligned_ratios) > 0:
        aligned_bitrates_mbps = [b / 1e6 for b in aligned_bitrates]

        categories = []
        for i, r in enumerate(aligned_ratios):
            if r < 0.9:
                categories.append('Low\n(<0.9)')
            elif r <= 1.1:
                categories.append('Normal\n(0.9-1.1)')
            else:
                categories.append('High\n(>1.1)')

        data_by_category = {}
        for cat, bw in zip(categories, aligned_bitrates_mbps):
            if cat not in data_by_category:
                data_by_category[cat] = []
            data_by_category[cat].append(bw)

        ax5.boxplot(data_by_category.values(), labels=data_by_category.keys())
        ax5.set_ylabel('Bandwidth (Mbps)')
        ax5.set_title('Bandwidth by Ratio Category')
        ax5.grid(True, alpha=0.3, axis='y')

    # Plot 6: Trend vs smoothed ratio
    ax6 = fig.add_subplot(gs[2, 2])
    if ratio_data:
        smoothed = [r['smoothed_ratio'] for r in ratio_data]
        trends = [r['trend'] for r in ratio_data]

        ax6.scatter(smoothed, trends, alpha=0.2, s=5)
        ax6.axhline(y=0, color='r', linestyle='--', alpha=0.5)
        ax6.axvline(x=1.0, color='r', linestyle='--', alpha=0.5)
        ax6.set_xlabel('Smoothed Ratio')
        ax6.set_ylabel('Trend')
        ax6.set_title('Trend vs Smoothed Ratio')
        ax6.grid(True, alpha=0.3)

    output_path = '/home/wuq/webrtc-local/webrtc_config_results/ratio_bandwidth_correlation.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n📊 Correlation plot saved to: {output_path}")

def main():
    log_path = '/home/wuq/webrtc-local/webrtc_config_results/sender_local.log'

    print(f"Parsing log file: {log_path}")
    data = parse_log_with_timestamps(log_path)

    print(f"\nExtracted data:")
    print(f"  Ratio updates: {len(data['ratio_data'])}")
    print(f"  AIMD updates: {len(data['aimd_updates'])}")
    print(f"  Probe results: {len(data['probe_results'])}")
    print(f"  SendBWE updates: {len(data['send_bwe_updates'])}")
    print(f"  Growth events: {len(data['growth_events'])}")

    # Analyze correlation
    aligned_ratios, aligned_bitrates = analyze_correlation(data)

    # Create plots
    plot_correlation(data, aligned_ratios, aligned_bitrates)

if __name__ == '__main__':
    main()

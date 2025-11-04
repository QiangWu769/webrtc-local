#!/usr/bin/env python3
"""
Analyze the relationship between smoothed ratio and bandwidth from WebRTC logs
"""

import re
import matplotlib.pyplot as plt
from collections import defaultdict
import numpy as np

def parse_log_file(log_path):
    """Parse the log file and extract ratio and bandwidth data"""

    # Pattern for cellular ratio updates
    ratio_pattern = r'\(aimd_rate_control\.cc:\d+\): \[AIMD-Cellular\] Resource ratio updated: ([\d.]+) \(smoothed: ([\d.]+)\), trend: ([-\d.]+)'

    # Patterns for bandwidth estimation
    bwe_pattern = r'estimate: (\d+) bps'
    current_bitrate_pattern = r'current_bitrate.*?(\d+)\s*(?:bps|kbps)'
    target_bitrate_pattern = r'target.*?bitrate.*?(\d+)'

    # Data storage
    ratios = []
    smoothed_ratios = []
    trends = []
    bandwidths = []
    timestamps = []

    with open(log_path, 'r') as f:
        for line in f:
            # Extract ratio data
            ratio_match = re.search(ratio_pattern, line)
            if ratio_match:
                raw_ratio = float(ratio_match.group(1))
                smoothed_ratio = float(ratio_match.group(2))
                trend = float(ratio_match.group(3))

                ratios.append(raw_ratio)
                smoothed_ratios.append(smoothed_ratio)
                trends.append(trend)

            # Extract bandwidth estimation
            bwe_match = re.search(bwe_pattern, line)
            if bwe_match:
                bw = int(bwe_match.group(1))
                bandwidths.append(bw)

    return {
        'ratios': ratios,
        'smoothed_ratios': smoothed_ratios,
        'trends': trends,
        'bandwidths': bandwidths
    }

def analyze_correlation(data):
    """Analyze the correlation between smoothed ratio and bandwidth"""

    smoothed_ratios = data['smoothed_ratios']

    # Calculate statistics
    print("\n" + "="*60)
    print("SMOOTHED RATIO ANALYSIS")
    print("="*60)

    if smoothed_ratios:
        print(f"\nTotal samples: {len(smoothed_ratios)}")
        print(f"Mean smoothed ratio: {np.mean(smoothed_ratios):.3f}")
        print(f"Std dev: {np.std(smoothed_ratios):.3f}")
        print(f"Min: {np.min(smoothed_ratios):.3f}")
        print(f"Max: {np.max(smoothed_ratios):.3f}")
        print(f"Median: {np.median(smoothed_ratios):.3f}")

        # Percentiles
        print(f"\nPercentiles:")
        print(f"  25th: {np.percentile(smoothed_ratios, 25):.3f}")
        print(f"  50th: {np.percentile(smoothed_ratios, 50):.3f}")
        print(f"  75th: {np.percentile(smoothed_ratios, 75):.3f}")
        print(f"  90th: {np.percentile(smoothed_ratios, 90):.3f}")
        print(f"  95th: {np.percentile(smoothed_ratios, 95):.3f}")

        # Categorize ratios
        underload = sum(1 for r in smoothed_ratios if r < 0.9)
        normal = sum(1 for r in smoothed_ratios if 0.9 <= r <= 1.1)
        overload = sum(1 for r in smoothed_ratios if r > 1.1)

        print(f"\nRatio distribution:")
        print(f"  Underload (< 0.9): {underload} ({100*underload/len(smoothed_ratios):.1f}%)")
        print(f"  Normal (0.9-1.1): {normal} ({100*normal/len(smoothed_ratios):.1f}%)")
        print(f"  Overload (> 1.1): {overload} ({100*overload/len(smoothed_ratios):.1f}%)")

    # Raw ratios
    ratios = data['ratios']
    if ratios:
        print(f"\n" + "-"*60)
        print("RAW RATIO ANALYSIS")
        print("-"*60)
        print(f"\nMean raw ratio: {np.mean(ratios):.3f}")
        print(f"Std dev: {np.std(ratios):.3f}")
        print(f"Min: {np.min(ratios):.3f}")
        print(f"Max: {np.max(ratios):.3f}")

    # Trends
    trends = data['trends']
    if trends:
        print(f"\n" + "-"*60)
        print("TREND ANALYSIS")
        print("-"*60)
        print(f"\nMean trend: {np.mean(trends):.3f}")
        print(f"Std dev: {np.std(trends):.3f}")
        print(f"Min: {np.min(trends):.3f}")
        print(f"Max: {np.max(trends):.3f}")

        positive_trends = sum(1 for t in trends if t > 0)
        negative_trends = sum(1 for t in trends if t < 0)
        print(f"\nPositive trends: {positive_trends} ({100*positive_trends/len(trends):.1f}%)")
        print(f"Negative trends: {negative_trends} ({100*negative_trends/len(trends):.1f}%)")

def plot_analysis(data):
    """Create visualization plots"""

    smoothed_ratios = data['smoothed_ratios']
    ratios = data['ratios']
    trends = data['trends']

    if not smoothed_ratios:
        print("No data to plot")
        return

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))

    # Plot 1: Time series of smoothed ratio
    ax1 = axes[0, 0]
    ax1.plot(smoothed_ratios, label='Smoothed Ratio', linewidth=1, alpha=0.8)
    ax1.axhline(y=1.0, color='r', linestyle='--', label='Target (1.0)')
    ax1.axhline(y=0.9, color='orange', linestyle=':', alpha=0.5, label='Underload threshold')
    ax1.axhline(y=1.1, color='orange', linestyle=':', alpha=0.5, label='Overload threshold')
    ax1.set_xlabel('Sample Index')
    ax1.set_ylabel('Smoothed Ratio')
    ax1.set_title('Smoothed Ratio Over Time')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Plot 2: Distribution histogram
    ax2 = axes[0, 1]
    ax2.hist(smoothed_ratios, bins=50, edgecolor='black', alpha=0.7)
    ax2.axvline(x=1.0, color='r', linestyle='--', label='Target (1.0)')
    ax2.axvline(x=np.mean(smoothed_ratios), color='g', linestyle='--',
                label=f'Mean ({np.mean(smoothed_ratios):.3f})')
    ax2.set_xlabel('Smoothed Ratio')
    ax2.set_ylabel('Frequency')
    ax2.set_title('Smoothed Ratio Distribution')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # Plot 3: Raw vs Smoothed ratio
    ax3 = axes[1, 0]
    if len(ratios) == len(smoothed_ratios):
        indices = range(min(500, len(ratios)))  # Plot first 500 samples
        ax3.plot(indices, [ratios[i] for i in indices],
                label='Raw Ratio', alpha=0.6, linewidth=1)
        ax3.plot(indices, [smoothed_ratios[i] for i in indices],
                label='Smoothed Ratio', linewidth=2)
        ax3.axhline(y=1.0, color='r', linestyle='--', alpha=0.5)
        ax3.set_xlabel('Sample Index')
        ax3.set_ylabel('Ratio')
        ax3.set_title('Raw vs Smoothed Ratio (First 500 samples)')
        ax3.legend()
        ax3.grid(True, alpha=0.3)

    # Plot 4: Trend analysis
    ax4 = axes[1, 1]
    if trends:
        ax4.plot(trends, linewidth=1, alpha=0.7, color='purple')
        ax4.axhline(y=0, color='r', linestyle='--', alpha=0.5)
        ax4.set_xlabel('Sample Index')
        ax4.set_ylabel('Trend')
        ax4.set_title('Ratio Trend Over Time')
        ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    output_path = '/home/wuq/webrtc-local/webrtc_config_results/ratio_bandwidth_analysis.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n📊 Plot saved to: {output_path}")

def main():
    log_path = '/home/wuq/webrtc-local/webrtc_config_results/sender_local.log'

    print(f"Parsing log file: {log_path}")
    data = parse_log_file(log_path)

    # Analyze the data
    analyze_correlation(data)

    # Create plots
    plot_analysis(data)

if __name__ == '__main__':
    main()

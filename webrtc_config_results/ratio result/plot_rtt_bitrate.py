#!/usr/bin/env python3
"""
Plot RTT vs Bitrate comparison between GCC and Ratio congestion control algorithms
"""

import matplotlib.pyplot as plt
import numpy as np
import re
import os
from pathlib import Path

def extract_metrics(log_file):
    """Extract average RTT and bitrate from log file"""
    with open(log_file, 'r') as f:
        content = f.read()

    # Extract media bitrate (convert from bps to kbps)
    media_pattern = r'MediaBitrateSentInBps.*?avg:(\d+)'
    media_match = re.search(media_pattern, content)
    media_bitrate = int(media_match.group(1)) / 1000 if media_match else 0

    # Extract all RTT values
    rtt_pattern = r'PropagationRtt:\s*(\d+)\s*ms'
    rtts = re.findall(rtt_pattern, content)
    rtts = [int(r) for r in rtts if 0 < int(r) < 1000]

    # Calculate average RTT
    avg_rtt = np.mean(rtts) if rtts else 0

    return avg_rtt, media_bitrate

def main():
    # Data directory
    data_dir = Path('/home/qwu26/webrtc-local/webrtc_config_results/ratio result')

    # Collect data
    gcc_lab_data = {'rtt': [], 'bitrate': [], 'labels': []}
    ratio_lab_data = {'rtt': [], 'bitrate': [], 'labels': []}
    gcc_home_data = {'rtt': [], 'bitrate': [], 'labels': []}
    ratio_home_data = {'rtt': [], 'bitrate': [], 'labels': []}

    # Process all log files
    for log_file in sorted(data_dir.glob('*.log')):
        filename = log_file.name

        # Extract metrics
        avg_rtt, bitrate = extract_metrics(log_file)

        # Categorize by algorithm and environment
        if 'gcclab' in filename:
            gcc_lab_data['rtt'].append(avg_rtt)
            gcc_lab_data['bitrate'].append(bitrate / 1000)  # Convert to Mbps
            gcc_lab_data['labels'].append(filename.replace('sender_local.log', ''))
        elif 'ratiolab' in filename:
            ratio_lab_data['rtt'].append(avg_rtt)
            ratio_lab_data['bitrate'].append(bitrate / 1000)  # Convert to Mbps
            ratio_lab_data['labels'].append(filename.replace('sender_local.log', ''))
        elif 'gcchome' in filename:
            gcc_home_data['rtt'].append(avg_rtt)
            gcc_home_data['bitrate'].append(bitrate / 1000)  # Convert to Mbps
            gcc_home_data['labels'].append(filename.replace('sender_local.log', ''))
        elif 'ratiohome' in filename:
            ratio_home_data['rtt'].append(avg_rtt)
            ratio_home_data['bitrate'].append(bitrate / 1000)  # Convert to Mbps
            ratio_home_data['labels'].append(filename.replace('sender_local.log', ''))

    # Create the plot
    fig, ax = plt.subplots(figsize=(10, 7))

    # Plot data points
    # Lab environment - filled markers
    if gcc_lab_data['rtt']:
        ax.scatter(gcc_lab_data['rtt'], gcc_lab_data['bitrate'],
                  marker='o', s=150, color='#FF6B6B', label='GCC (Lab)',
                  edgecolors='darkred', linewidths=1.5, alpha=0.8)

    if ratio_lab_data['rtt']:
        ax.scatter(ratio_lab_data['rtt'], ratio_lab_data['bitrate'],
                  marker='s', s=150, color='#4ECDC4', label='Ratio (Lab)',
                  edgecolors='darkgreen', linewidths=1.5, alpha=0.8)

    # Home environment - hollow markers
    if gcc_home_data['rtt']:
        ax.scatter(gcc_home_data['rtt'], gcc_home_data['bitrate'],
                  marker='o', s=150, facecolors='none', edgecolors='#FF6B6B',
                  label='GCC (Home)', linewidths=2, alpha=0.8)

    if ratio_home_data['rtt']:
        ax.scatter(ratio_home_data['rtt'], ratio_home_data['bitrate'],
                  marker='s', s=150, facecolors='none', edgecolors='#4ECDC4',
                  label='Ratio (Home)', linewidths=2, alpha=0.8)

    # Add "Better" annotation arrow
    ax.annotate('Better', xy=(0.05, 0.95), xytext=(0.15, 0.85),
                xycoords='axes fraction', fontsize=14, fontweight='bold',
                arrowprops=dict(arrowstyle='->', lw=2, color='green'),
                color='green')

    # Calculate and display average values
    if gcc_lab_data['rtt'] and ratio_lab_data['rtt']:
        gcc_avg_rtt = np.mean(gcc_lab_data['rtt'])
        gcc_avg_br = np.mean(gcc_lab_data['bitrate'])
        ratio_avg_rtt = np.mean(ratio_lab_data['rtt'])
        ratio_avg_br = np.mean(ratio_lab_data['bitrate'])

        # Plot average points with star markers
        ax.scatter([gcc_avg_rtt], [gcc_avg_br], marker='*', s=500,
                  color='#FF6B6B', edgecolors='black', linewidths=2,
                  label='GCC Avg (Lab)', zorder=10)
        ax.scatter([ratio_avg_rtt], [ratio_avg_br], marker='*', s=500,
                  color='#4ECDC4', edgecolors='black', linewidths=2,
                  label='Ratio Avg (Lab)', zorder=10)

    # Labels and title
    ax.set_xlabel('Average RTT (ms)', fontsize=14, fontweight='bold')
    ax.set_ylabel('Media Bitrate (Mbps)', fontsize=14, fontweight='bold')
    ax.set_title('WebRTC Performance: GCC vs Ratio Congestion Control',
                fontsize=16, fontweight='bold', pad=20)

    # Grid
    ax.grid(True, alpha=0.3, linestyle='--')

    # Legend
    ax.legend(loc='best', fontsize=11, framealpha=0.9)

    # Set axis limits with some padding
    all_rtts = (gcc_lab_data['rtt'] + ratio_lab_data['rtt'] +
                gcc_home_data['rtt'] + ratio_home_data['rtt'])
    all_bitrates = (gcc_lab_data['bitrate'] + ratio_lab_data['bitrate'] +
                    gcc_home_data['bitrate'] + ratio_home_data['bitrate'])

    if all_rtts and all_bitrates:
        rtt_margin = (max(all_rtts) - min(all_rtts)) * 0.1
        br_margin = (max(all_bitrates) - min(all_bitrates)) * 0.1
        ax.set_xlim(min(all_rtts) - rtt_margin, max(all_rtts) + rtt_margin)
        ax.set_ylim(min(all_bitrates) - br_margin, max(all_bitrates) + br_margin)

    # Tight layout
    plt.tight_layout()

    # Save figure
    output_file = data_dir / 'rtt_bitrate_comparison.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Plot saved to: {output_file}")

    # Also save as PDF for publications
    output_pdf = data_dir / 'rtt_bitrate_comparison.pdf'
    plt.savefig(output_pdf, bbox_inches='tight')
    print(f"PDF saved to: {output_pdf}")

    # Show the plot
    plt.show()

    # Print summary statistics
    print("\n=== Summary Statistics ===")
    if gcc_lab_data['rtt']:
        print(f"\nGCC (Lab):")
        print(f"  Avg RTT: {np.mean(gcc_lab_data['rtt']):.1f} ms")
        print(f"  Avg Bitrate: {np.mean(gcc_lab_data['bitrate']):.2f} Mbps")

    if ratio_lab_data['rtt']:
        print(f"\nRatio (Lab):")
        print(f"  Avg RTT: {np.mean(ratio_lab_data['rtt']):.1f} ms")
        print(f"  Avg Bitrate: {np.mean(ratio_lab_data['bitrate']):.2f} Mbps")

    if gcc_lab_data['rtt'] and ratio_lab_data['rtt']:
        rtt_improvement = ((np.mean(gcc_lab_data['rtt']) - np.mean(ratio_lab_data['rtt'])) /
                          np.mean(gcc_lab_data['rtt']) * 100)
        br_improvement = ((np.mean(ratio_lab_data['bitrate']) - np.mean(gcc_lab_data['bitrate'])) /
                         np.mean(gcc_lab_data['bitrate']) * 100)
        print(f"\nRatio vs GCC (Lab):")
        print(f"  RTT improvement: {rtt_improvement:+.1f}%")
        print(f"  Bitrate improvement: {br_improvement:+.1f}%")

    if gcc_home_data['rtt']:
        print(f"\nGCC (Home):")
        print(f"  Avg RTT: {np.mean(gcc_home_data['rtt']):.1f} ms")
        print(f"  Avg Bitrate: {np.mean(gcc_home_data['bitrate']):.2f} Mbps")

    if ratio_home_data['rtt']:
        print(f"\nRatio (Home):")
        print(f"  Avg RTT: {np.mean(ratio_home_data['rtt']):.1f} ms")
        print(f"  Avg Bitrate: {np.mean(ratio_home_data['bitrate']):.2f} Mbps")

    if gcc_home_data['rtt'] and ratio_home_data['rtt']:
        rtt_improvement = ((np.mean(gcc_home_data['rtt']) - np.mean(ratio_home_data['rtt'])) /
                          np.mean(gcc_home_data['rtt']) * 100)
        br_improvement = ((np.mean(ratio_home_data['bitrate']) - np.mean(gcc_home_data['bitrate'])) /
                         np.mean(gcc_home_data['bitrate']) * 100)
        print(f"\nRatio vs GCC (Home):")
        print(f"  RTT improvement: {rtt_improvement:+.1f}%")
        print(f"  Bitrate improvement: {br_improvement:+.1f}%")

if __name__ == '__main__':
    main()

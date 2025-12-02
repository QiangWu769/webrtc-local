#!/usr/bin/env python3
"""
Plot separate RTT vs Bitrate comparisons for Lab and Home environments
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

def plot_environment(gcc_data, ratio_data, env_name, output_prefix, data_dir):
    """Plot comparison for a specific environment"""
    fig, ax = plt.subplots(figsize=(10, 7))

    # Plot GCC data points
    if gcc_data['rtt']:
        ax.scatter(gcc_data['rtt'], gcc_data['bitrate'],
                  marker='o', s=200, color='#FF6B6B', label='GCC',
                  edgecolors='darkred', linewidths=2, alpha=0.8)

        # Add labels for each point
        for i, label in enumerate(gcc_data['labels']):
            ax.annotate(label, (gcc_data['rtt'][i], gcc_data['bitrate'][i]),
                       xytext=(8, 8), textcoords='offset points',
                       fontsize=9, alpha=0.7)

    # Plot Ratio data points
    if ratio_data['rtt']:
        ax.scatter(ratio_data['rtt'], ratio_data['bitrate'],
                  marker='s', s=200, color='#4ECDC4', label='Ratio',
                  edgecolors='darkgreen', linewidths=2, alpha=0.8)

        # Add labels for each point
        for i, label in enumerate(ratio_data['labels']):
            ax.annotate(label, (ratio_data['rtt'][i], ratio_data['bitrate'][i]),
                       xytext=(8, 8), textcoords='offset points',
                       fontsize=9, alpha=0.7)

    # Calculate and plot average points
    if gcc_data['rtt'] and ratio_data['rtt']:
        gcc_avg_rtt = np.mean(gcc_data['rtt'])
        gcc_avg_br = np.mean(gcc_data['bitrate'])
        ratio_avg_rtt = np.mean(ratio_data['rtt'])
        ratio_avg_br = np.mean(ratio_data['bitrate'])

        # Plot average points with star markers
        ax.scatter([gcc_avg_rtt], [gcc_avg_br], marker='*', s=600,
                  color='#FF6B6B', edgecolors='black', linewidths=2.5,
                  label='GCC Avg', zorder=10)
        ax.scatter([ratio_avg_rtt], [ratio_avg_br], marker='*', s=600,
                  color='#4ECDC4', edgecolors='black', linewidths=2.5,
                  label='Ratio Avg', zorder=10)

        # Add improvement text box
        rtt_improvement = ((gcc_avg_rtt - ratio_avg_rtt) / gcc_avg_rtt * 100)
        br_improvement = ((ratio_avg_br - gcc_avg_br) / gcc_avg_br * 100)

        textstr = f'Ratio vs GCC:\n'
        textstr += f'RTT: {rtt_improvement:+.1f}%\n'
        textstr += f'Bitrate: {br_improvement:+.1f}%'

        props = dict(boxstyle='round', facecolor='wheat', alpha=0.8)
        ax.text(0.02, 0.98, textstr, transform=ax.transAxes, fontsize=12,
                verticalalignment='top', bbox=props, fontweight='bold')

    # Add "Better" annotation arrow
    ax.annotate('Better', xy=(0.05, 0.92), xytext=(0.15, 0.82),
                xycoords='axes fraction', fontsize=14, fontweight='bold',
                arrowprops=dict(arrowstyle='->', lw=2.5, color='green'),
                color='green')

    # Labels and title
    ax.set_xlabel('Average RTT (ms)', fontsize=14, fontweight='bold')
    ax.set_ylabel('Media Bitrate (Mbps)', fontsize=14, fontweight='bold')
    ax.set_title(f'WebRTC Performance: GCC vs Ratio ({env_name} Environment)',
                fontsize=16, fontweight='bold', pad=20)

    # Grid
    ax.grid(True, alpha=0.3, linestyle='--', linewidth=1)

    # Legend
    ax.legend(loc='lower right', fontsize=12, framealpha=0.95,
             edgecolor='black', fancybox=True)

    # Set axis limits with padding
    all_rtts = gcc_data['rtt'] + ratio_data['rtt']
    all_bitrates = gcc_data['bitrate'] + ratio_data['bitrate']

    if all_rtts and all_bitrates:
        rtt_margin = (max(all_rtts) - min(all_rtts)) * 0.15
        br_margin = (max(all_bitrates) - min(all_bitrates)) * 0.15
        ax.set_xlim(min(all_rtts) - rtt_margin, max(all_rtts) + rtt_margin)
        ax.set_ylim(min(all_bitrates) - br_margin, max(all_bitrates) + br_margin)

    # Tight layout
    plt.tight_layout()

    # Save figures
    output_png = data_dir / f'{output_prefix}_comparison.png'
    plt.savefig(output_png, dpi=300, bbox_inches='tight')
    print(f"Plot saved to: {output_png}")

    output_pdf = data_dir / f'{output_prefix}_comparison.pdf'
    plt.savefig(output_pdf, bbox_inches='tight')
    print(f"PDF saved to: {output_pdf}")

    plt.close()

    # Print statistics
    if gcc_data['rtt'] and ratio_data['rtt']:
        print(f"\n=== {env_name} Environment Statistics ===")
        print(f"GCC:")
        print(f"  Avg RTT: {np.mean(gcc_data['rtt']):.1f} ms")
        print(f"  Avg Bitrate: {np.mean(gcc_data['bitrate']):.2f} Mbps")
        print(f"Ratio:")
        print(f"  Avg RTT: {np.mean(ratio_data['rtt']):.1f} ms")
        print(f"  Avg Bitrate: {np.mean(ratio_data['bitrate']):.2f} Mbps")
        print(f"Improvement:")
        print(f"  RTT: {rtt_improvement:+.1f}%")
        print(f"  Bitrate: {br_improvement:+.1f}%")

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

    # Plot Lab environment
    if gcc_lab_data['rtt'] or ratio_lab_data['rtt']:
        plot_environment(gcc_lab_data, ratio_lab_data, 'Lab', 'lab_rtt_bitrate', data_dir)

    # Plot Home environment
    if gcc_home_data['rtt'] or ratio_home_data['rtt']:
        plot_environment(gcc_home_data, ratio_home_data, 'Home', 'home_rtt_bitrate', data_dir)

    print("\n✓ All plots generated successfully!")

if __name__ == '__main__':
    main()

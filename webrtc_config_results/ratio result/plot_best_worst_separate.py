#!/usr/bin/env python3
"""
Plot separate comparisons for Lab and Home environments
Each plot: Best 2 Ratio vs Worst 2 GCC within that environment
Ratio: circles, GCC: pentagons
"""

import matplotlib.pyplot as plt
import numpy as np
import re
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

def calculate_score(rtt, bitrate):
    """Calculate performance score (higher is better)"""
    return bitrate / rtt if rtt > 0 else 0

def plot_environment(best_ratio, worst_gcc, env_name, output_prefix, data_dir):
    """Plot comparison for a specific environment"""

    print(f"\n=== {env_name} Environment ===")
    print(f"Best 2 Ratio:")
    for i, data in enumerate(best_ratio, 1):
        print(f"  {i}. {data['label']}: {data['bitrate']:.2f} Mbps @ {data['rtt']:.1f} ms")

    print(f"Worst 2 GCC:")
    for i, data in enumerate(worst_gcc, 1):
        print(f"  {i}. {data['label']}: {data['bitrate']:.2f} Mbps @ {data['rtt']:.1f} ms")

    # Create the plot
    fig, ax = plt.subplots(figsize=(10, 7))

    # Plot Ratio (circles) - cyan color
    for data in best_ratio:
        ax.scatter([data['rtt']], [data['bitrate']],
                  marker='o', s=300, color='#4ECDC4',
                  edgecolors='darkgreen', linewidths=2.5, alpha=0.9,
                  label='Ratio' if data == best_ratio[0] else '')

        # Add label
        ax.annotate(data['label'], (data['rtt'], data['bitrate']),
                   xytext=(10, 10), textcoords='offset points',
                   fontsize=11, fontweight='bold')

    # Plot GCC (pentagons) - red color
    for data in worst_gcc:
        ax.scatter([data['rtt']], [data['bitrate']],
                  marker='p', s=300, color='#FF6B6B',
                  edgecolors='darkred', linewidths=2.5, alpha=0.9,
                  label='GCC' if data == worst_gcc[0] else '')

        # Add label
        ax.annotate(data['label'], (data['rtt'], data['bitrate']),
                   xytext=(10, 10), textcoords='offset points',
                   fontsize=11, fontweight='bold')

    # Calculate statistics
    ratio_avg_rtt = np.mean([d['rtt'] for d in best_ratio])
    ratio_avg_br = np.mean([d['bitrate'] for d in best_ratio])
    gcc_avg_rtt = np.mean([d['rtt'] for d in worst_gcc])
    gcc_avg_br = np.mean([d['bitrate'] for d in worst_gcc])

    rtt_improvement = ((gcc_avg_rtt - ratio_avg_rtt) / gcc_avg_rtt * 100)
    br_improvement = ((ratio_avg_br - gcc_avg_br) / gcc_avg_br * 100)

    # Add improvement text box
    textstr = f'Ratio (Best 2) vs GCC (Worst 2):\n'
    textstr += f'RTT: {rtt_improvement:+.1f}%\n'
    textstr += f'Bitrate: {br_improvement:+.1f}%'

    props = dict(boxstyle='round', facecolor='wheat', alpha=0.85)
    ax.text(0.02, 0.98, textstr, transform=ax.transAxes, fontsize=13,
            verticalalignment='top', bbox=props, fontweight='bold')

    # Add "Better" annotation arrow
    ax.annotate('Better', xy=(0.05, 0.88), xytext=(0.15, 0.78),
                xycoords='axes fraction', fontsize=14, fontweight='bold',
                arrowprops=dict(arrowstyle='->', lw=2.5, color='green'),
                color='green')

    # Labels and title
    ax.set_xlabel('Average RTT (ms)', fontsize=14, fontweight='bold')
    ax.set_ylabel('Media Bitrate (Mbps)', fontsize=14, fontweight='bold')
    ax.set_title(f'WebRTC Performance: Best Ratio vs Worst GCC ({env_name})',
                fontsize=16, fontweight='bold', pad=20)

    # Grid
    ax.grid(True, alpha=0.3, linestyle='--', linewidth=1)

    # Legend - only 2 items
    ax.legend(loc='lower right', fontsize=13, framealpha=0.95,
             edgecolor='black', fancybox=True)

    # Set axis limits with padding
    all_rtts = [d['rtt'] for d in best_ratio + worst_gcc]
    all_bitrates = [d['bitrate'] for d in best_ratio + worst_gcc]

    rtt_margin = (max(all_rtts) - min(all_rtts)) * 0.2
    br_margin = (max(all_bitrates) - min(all_bitrates)) * 0.2

    ax.set_xlim(min(all_rtts) - rtt_margin, max(all_rtts) + rtt_margin)
    ax.set_ylim(min(all_bitrates) - br_margin, max(all_bitrates) + br_margin)

    # Tight layout
    plt.tight_layout()

    # Save figures
    output_png = data_dir / f'{output_prefix}_best_worst_comparison.png'
    plt.savefig(output_png, dpi=300, bbox_inches='tight')
    print(f"Plot saved to: {output_png}")

    output_pdf = data_dir / f'{output_prefix}_best_worst_comparison.pdf'
    plt.savefig(output_pdf, bbox_inches='tight')
    print(f"PDF saved to: {output_pdf}")

    plt.close()

    # Print statistics
    print(f"Statistics:")
    print(f"  Ratio avg: {ratio_avg_br:.2f} Mbps @ {ratio_avg_rtt:.1f} ms")
    print(f"  GCC avg: {gcc_avg_br:.2f} Mbps @ {gcc_avg_rtt:.1f} ms")
    print(f"  Improvement: RTT {rtt_improvement:+.1f}%, Bitrate {br_improvement:+.1f}%")

def main():
    # Data directory
    data_dir = Path('/home/qwu26/webrtc-local/webrtc_config_results/ratio result')

    # Collect data by environment
    gcc_lab_results = []
    ratio_lab_results = []
    gcc_home_results = []
    ratio_home_results = []

    # Process all log files
    for log_file in sorted(data_dir.glob('*.log')):
        filename = log_file.name

        # Extract metrics
        avg_rtt, bitrate = extract_metrics(log_file)
        bitrate_mbps = bitrate / 1000  # Convert to Mbps

        # Calculate performance score
        score = calculate_score(avg_rtt, bitrate_mbps)

        label = filename.replace('sender_local.log', '')

        data = {
            'filename': filename,
            'label': label,
            'rtt': avg_rtt,
            'bitrate': bitrate_mbps,
            'score': score
        }

        # Categorize by algorithm and environment
        if 'gcclab' in filename:
            gcc_lab_results.append(data)
        elif 'ratiolab' in filename:
            ratio_lab_results.append(data)
        elif 'gcchome' in filename:
            gcc_home_results.append(data)
        elif 'ratiohome' in filename:
            ratio_home_results.append(data)

    # Process Lab environment
    if ratio_lab_results and gcc_lab_results:
        # Best 2 Ratio (highest scores)
        ratio_lab_results.sort(key=lambda x: x['score'], reverse=True)
        best_ratio_lab = ratio_lab_results[:2]

        # Worst 2 GCC (lowest scores)
        gcc_lab_results.sort(key=lambda x: x['score'])
        worst_gcc_lab = gcc_lab_results[:2]

        plot_environment(best_ratio_lab, worst_gcc_lab, 'Lab', 'lab', data_dir)

    # Process Home environment
    if ratio_home_results and gcc_home_results:
        # Best 2 Ratio (highest scores)
        ratio_home_results.sort(key=lambda x: x['score'], reverse=True)
        best_ratio_home = ratio_home_results[:2]

        # Worst 2 GCC (lowest scores)
        gcc_home_results.sort(key=lambda x: x['score'])
        worst_gcc_home = gcc_home_results[:2]

        plot_environment(best_ratio_home, worst_gcc_home, 'Home', 'home', data_dir)

    print("\n✓ All plots generated successfully!")

if __name__ == '__main__':
    main()

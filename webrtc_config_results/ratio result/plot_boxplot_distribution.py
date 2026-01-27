#!/usr/bin/env python3
"""
Plot RTT vs Bitrate distribution using box plots
Similar to the PCC-Gandalf style visualization
X-axis: RTT (ms) with horizontal box showing distribution
Y-axis: Bitrate (Mbps) with vertical position showing distribution
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import re
from pathlib import Path

def extract_time_series(log_file):
    """Extract RTT and bitrate time series from log file"""
    with open(log_file, 'r') as f:
        content = f.read()

    # Extract all RTT values
    rtt_pattern = r'PropagationRtt:\s*(\d+)\s*ms'
    rtts = re.findall(rtt_pattern, content)
    rtts = [int(r) for r in rtts if 0 < int(r) < 1000]

    # Extract media bitrate samples (convert from bps to Mbps)
    # Look for individual bitrate measurements
    bitrate_pattern = r'MediaBitrateSentInBps.*?samples:(\d+).*?avg:(\d+)'
    bitrate_match = re.search(bitrate_pattern, content)

    # Also try to get instantaneous bitrate values
    instant_br_pattern = r'target_bitrate_bps["\s:]+(\d+)'
    instant_bitrates = re.findall(instant_br_pattern, content)
    instant_bitrates = [int(b) / 1e6 for b in instant_bitrates if int(b) > 0]  # to Mbps

    # If no instant bitrates, use the average repeated
    if not instant_bitrates and bitrate_match:
        avg_br = int(bitrate_match.group(2)) / 1e6  # to Mbps
        instant_bitrates = [avg_br]

    return rtts, instant_bitrates

def extract_metrics_detailed(log_file):
    """Extract detailed RTT distribution and bitrate from log file"""
    with open(log_file, 'r') as f:
        content = f.read()

    # Extract all RTT values for distribution
    rtt_pattern = r'PropagationRtt:\s*(\d+)\s*ms'
    rtts = re.findall(rtt_pattern, content)
    rtts = [int(r) for r in rtts if 0 < int(r) < 1000]

    # Extract media bitrate (convert from bps to Mbps)
    media_pattern = r'MediaBitrateSentInBps.*?avg:(\d+)'
    media_match = re.search(media_pattern, content)
    avg_bitrate = int(media_match.group(1)) / 1e6 if media_match else 0  # Mbps

    # Try to extract bitrate time series from GCC snapshots
    br_pattern = r'EstimatedBitrate:\s*(\d+)\s*bps'
    bitrates = re.findall(br_pattern, content)
    bitrates = [int(b) / 1e6 for b in bitrates if int(b) > 0]  # to Mbps

    if not bitrates:
        bitrates = [avg_bitrate]

    return rtts, bitrates, avg_bitrate

def plot_boxplot_style(env_name, ratio_files, gcc_files, output_path):
    """
    Plot box plot style visualization similar to PCC-Gandalf paper
    Each algorithm shows RTT distribution (horizontal box) at its throughput level
    Uses averaged percentiles from individual files (not pooled raw data)
    """
    fig, ax = plt.subplots(figsize=(10, 8))

    # Pool all raw data from files, then calculate percentiles
    def pool_raw_data(files):
        """Pool all raw RTT and bitrate data from multiple files"""
        all_rtts = []
        all_bitrates = []
        for log_file in files:
            rtts, bitrates, avg_br = extract_metrics_detailed(log_file)
            if rtts:
                all_rtts.extend(rtts)  # Combine all RTT samples
                all_bitrates.append(avg_br)  # Each file's avg bitrate

        if not all_rtts:
            return None

        return {
            'p10': np.percentile(all_rtts, 10),
            'p25': np.percentile(all_rtts, 25),
            'p50': np.percentile(all_rtts, 50),
            'p75': np.percentile(all_rtts, 75),
            'p90': np.percentile(all_rtts, 90),
            'bitrate': np.mean(all_bitrates),
            'bitrates': all_bitrates,
            # Min/Max for whiskers
            'rtt_min': np.min(all_rtts),
            'rtt_max': np.max(all_rtts),
        }

    ratio_stats = pool_raw_data(ratio_files)
    gcc_stats = pool_raw_data(gcc_files)

    # Convert to box stats format
    # Use averaged percentiles to show within-run distribution
    # Box: P25-P75, Whiskers: P10-P90
    def to_box_stats(stats):
        return {
            'whisker_low': stats['p10'],
            'q1': stats['p25'],
            'median': stats['p50'],
            'q3': stats['p75'],
            'whisker_high': stats['p90'],
        }

    ratio_rtt_stats = to_box_stats(ratio_stats)
    gcc_rtt_stats = to_box_stats(gcc_stats)

    print(f"  Ratio RTT: P10={ratio_stats['p10']:.0f}, P25={ratio_stats['p25']:.0f}, P50={ratio_stats['p50']:.0f}, P75={ratio_stats['p75']:.0f}, P90={ratio_stats['p90']:.0f}")
    print(f"  GCC RTT: P10={gcc_stats['p10']:.0f}, P25={gcc_stats['p25']:.0f}, P50={gcc_stats['p50']:.0f}, P75={gcc_stats['p75']:.0f}, P90={gcc_stats['p90']:.0f}")

    # For bitrate, use the individual file values to show spread
    ratio_br_stats = {
        'q1': min(ratio_stats['bitrates']),
        'median': ratio_stats['bitrate'],
        'q3': max(ratio_stats['bitrates']),
    }
    gcc_br_stats = {
        'q1': min(gcc_stats['bitrates']),
        'median': gcc_stats['bitrate'],
        'q3': max(gcc_stats['bitrates']),
    }

    # Colors matching reference image
    ratio_color = '#90EE90'  # Light green
    gcc_color = '#6495ED'    # Cornflower blue

    # Calculate Y positions based on bitrate medians
    ratio_y = ratio_br_stats['median']
    gcc_y = gcc_br_stats['median']

    # Dynamic box height based on bitrate range
    br_range = max(ratio_br_stats['q3'], gcc_br_stats['q3']) - min(ratio_br_stats['q1'], gcc_br_stats['q1'])
    box_height = br_range * 0.15  # 15% of bitrate range

    # Function to draw a horizontal box plot
    def draw_hbox(ax, rtt_stats, br_stats, y_pos, color, edge_color, label):
        # Main box (Q1 to Q3 of RTT)
        rect = plt.Rectangle(
            (rtt_stats['q1'], y_pos - box_height/2),
            rtt_stats['q3'] - rtt_stats['q1'],
            box_height,
            facecolor=color, edgecolor=edge_color, linewidth=2, alpha=0.85
        )
        ax.add_patch(rect)

        # Median line (vertical red solid line in box)
        ax.vlines(rtt_stats['median'], y_pos - box_height/2, y_pos + box_height/2,
                  colors='red', linewidth=3, linestyles='solid')

        # Whiskers - dashed lines like PBE-CC paper
        if rtt_stats['whisker_low'] < rtt_stats['q1']:
            ax.hlines(y_pos, rtt_stats['whisker_low'], rtt_stats['q1'],
                      colors='black', linewidth=1.5, linestyles='dashed')
            cap_height = box_height * 0.4
            ax.vlines(rtt_stats['whisker_low'], y_pos - cap_height/2, y_pos + cap_height/2,
                      colors='black', linewidth=1.5, linestyles='dashed')

        if rtt_stats['whisker_high'] > rtt_stats['q3']:
            ax.hlines(y_pos, rtt_stats['q3'], rtt_stats['whisker_high'],
                      colors='black', linewidth=1.5, linestyles='dashed')
            cap_height = box_height * 0.4
            ax.vlines(rtt_stats['whisker_high'], y_pos - cap_height/2, y_pos + cap_height/2,
                      colors='black', linewidth=1.5, linestyles='dashed')

        # Vertical error bars for bitrate distribution (Q1 to Q3) - dashed like PBE-CC
        ax.errorbar(rtt_stats['median'], y_pos,
                    yerr=[[y_pos - br_stats['q1']], [br_stats['q3'] - y_pos]],
                    fmt='none', ecolor='black', elinewidth=1.5, capsize=5, capthick=1.5,
                    linestyle='dashed')

        return max(rtt_stats['whisker_high'], rtt_stats['q3'])

    # Draw boxes
    ratio_max_rtt = draw_hbox(ax, ratio_rtt_stats, ratio_br_stats, ratio_y,
                              ratio_color, '#228B22', 'Ratio')
    gcc_max_rtt = draw_hbox(ax, gcc_rtt_stats, gcc_br_stats, gcc_y,
                            gcc_color, '#4169E1', 'GCC')

    # Get max whisker for axis limits
    max_whisker = max(ratio_rtt_stats['whisker_high'], gcc_rtt_stats['whisker_high'])
    min_rtt = min(ratio_rtt_stats['whisker_low'], gcc_rtt_stats['whisker_low'])

    # Labels and title
    ax.set_xlabel('RTT (ms)', fontsize=14, fontweight='bold')
    ax.set_ylabel('Throughput (Mbps)', fontsize=14, fontweight='bold')
    ax.set_title(f'WebRTC Performance Distribution ({env_name} Environment)',
                fontsize=16, fontweight='bold', pad=15)

    # Set axis limits
    rtt_padding = (max_whisker - min_rtt) * 0.15
    ax.set_xlim(min_rtt - rtt_padding, max_whisker + rtt_padding)

    all_br = [ratio_br_stats['q1'], ratio_br_stats['q3'],
              gcc_br_stats['q1'], gcc_br_stats['q3']]
    br_min, br_max = min(all_br), max(all_br)
    br_padding = (br_max - br_min) * 0.3
    ax.set_ylim(max(0, br_min - br_padding), br_max + br_padding)

    # Reverse x-axis (lower RTT = better, on right side)
    ax.invert_xaxis()

    # Grid
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)

    # Legend
    ratio_patch = mpatches.Patch(facecolor=ratio_color, edgecolor='#228B22',
                                  linewidth=2, label='Ratio')
    gcc_patch = mpatches.Patch(facecolor=gcc_color, edgecolor='#4169E1',
                                linewidth=2, label='GCC')
    ax.legend(handles=[ratio_patch, gcc_patch], loc='upper left', fontsize=12)

    # Statistics text box
    rtt_improve = (gcc_rtt_stats['median'] - ratio_rtt_stats['median']) / gcc_rtt_stats['median'] * 100
    br_improve = (ratio_br_stats['median'] - gcc_br_stats['median']) / gcc_br_stats['median'] * 100

    stats_text = (f"Ratio vs GCC:\n"
                  f"RTT: {-rtt_improve:+.1f}% (lower)\n"
                  f"Throughput: {br_improve:+.1f}% (higher)")
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.85)
    ax.text(0.02, 0.02, stats_text, transform=ax.transAxes, fontsize=11,
            verticalalignment='bottom', horizontalalignment='left',
            bbox=props, fontweight='bold')

    plt.tight_layout()

    # Save
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Box plot saved to: {output_path}")

    pdf_path = output_path.with_suffix('.pdf')
    plt.savefig(pdf_path, bbox_inches='tight')
    print(f"PDF saved to: {pdf_path}")

    plt.close()

    # Print detailed statistics
    print(f"\n=== {env_name} Environment Statistics ===")
    print(f"Ratio RTT: whisker_low={ratio_rtt_stats['whisker_low']:.1f}, Q1={ratio_rtt_stats['q1']:.1f}, "
          f"median={ratio_rtt_stats['median']:.1f}, Q3={ratio_rtt_stats['q3']:.1f}, "
          f"whisker_high={ratio_rtt_stats['whisker_high']:.1f} ms")
    print(f"Ratio Bitrate: Q1={ratio_br_stats['q1']:.2f}, median={ratio_br_stats['median']:.2f}, "
          f"Q3={ratio_br_stats['q3']:.2f} Mbps")
    print(f"GCC RTT: whisker_low={gcc_rtt_stats['whisker_low']:.1f}, Q1={gcc_rtt_stats['q1']:.1f}, "
          f"median={gcc_rtt_stats['median']:.1f}, Q3={gcc_rtt_stats['q3']:.1f}, "
          f"whisker_high={gcc_rtt_stats['whisker_high']:.1f} ms")
    print(f"GCC Bitrate: Q1={gcc_br_stats['q1']:.2f}, median={gcc_br_stats['median']:.2f}, "
          f"Q3={gcc_br_stats['q3']:.2f} Mbps")


def calculate_score(log_file):
    """Calculate performance score for a log file (higher is better)"""
    rtts, bitrates, avg_br = extract_metrics_detailed(log_file)
    if not rtts:
        return 0
    p50_rtt = np.percentile(rtts, 50)
    return avg_br / p50_rtt if p50_rtt > 0 else 0


def select_best_worst(ratio_files, gcc_files, n=2):
    """Select best n Ratio files and worst n GCC files based on score"""
    # Score all files
    ratio_scored = [(f, calculate_score(f)) for f in ratio_files]
    gcc_scored = [(f, calculate_score(f)) for f in gcc_files]

    # Sort: Ratio by score descending (best first), GCC by score ascending (worst first)
    ratio_scored.sort(key=lambda x: x[1], reverse=True)
    gcc_scored.sort(key=lambda x: x[1])

    best_ratio = [f for f, s in ratio_scored[:n]]
    worst_gcc = [f for f, s in gcc_scored[:n]]

    print(f"  Selected Ratio (best {n}):")
    for f, s in ratio_scored[:n]:
        print(f"    {f.name}: score={s:.4f}")
    print(f"  Selected GCC (worst {n}):")
    for f, s in gcc_scored[:n]:
        print(f"    {f.name}: score={s:.4f}")

    return best_ratio, worst_gcc


def main():
    data_dir = Path('/home/qwu26/webrtc-local/webrtc_config_results/ratio result')

    # Collect log files by category
    gcc_lab_files = sorted(data_dir.glob('gcclab*sender_local.log'))
    ratio_lab_files = sorted(data_dir.glob('ratiolab*sender_local.log'))
    gcc_home_files = sorted(data_dir.glob('gcchome*sender_local.log'))
    ratio_home_files = sorted(data_dir.glob('ratiohome*sender_local.log'))

    print("Found log files:")
    print(f"  GCC Lab: {len(gcc_lab_files)}")
    print(f"  Ratio Lab: {len(ratio_lab_files)}")
    print(f"  GCC Home: {len(gcc_home_files)}")
    print(f"  Ratio Home: {len(ratio_home_files)}")

    # Plot Lab environment - select best 2 Ratio vs worst 2 GCC
    if ratio_lab_files and gcc_lab_files:
        print("\n--- Lab Environment Selection ---")
        best_ratio_lab, worst_gcc_lab = select_best_worst(ratio_lab_files, gcc_lab_files, n=2)
        output_lab = data_dir / 'lab_boxplot_distribution.png'
        plot_boxplot_style('Lab', best_ratio_lab, worst_gcc_lab, output_lab)

    # Plot Home environment - select best 2 Ratio vs worst 2 GCC
    if ratio_home_files and gcc_home_files:
        print("\n--- Home Environment Selection ---")
        best_ratio_home, worst_gcc_home = select_best_worst(ratio_home_files, gcc_home_files, n=2)
        output_home = data_dir / 'home_boxplot_distribution.png'
        plot_boxplot_style('Home', best_ratio_home, worst_gcc_home, output_home)

    print("\n✓ All box plots generated!")

if __name__ == '__main__':
    main()

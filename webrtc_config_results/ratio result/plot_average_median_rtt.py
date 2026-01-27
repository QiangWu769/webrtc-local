#!/usr/bin/env python3
"""
Plot comparison with averaged values and median RTT
Each plot shows only 2 points: Ratio avg vs GCC avg
X-axis: Median RTT, Y-axis: Average Bitrate
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import re
from pathlib import Path

def extract_metrics(log_file):
    """Extract RTT percentiles, average bitrate, and overuse count from log file"""
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

    # Calculate RTT percentiles
    if rtts:
        p10_rtt = np.percentile(rtts, 10)
        p25_rtt = np.percentile(rtts, 25)
        p50_rtt = np.percentile(rtts, 50)
        p75_rtt = np.percentile(rtts, 75)
        p90_rtt = np.percentile(rtts, 90)
    else:
        p10_rtt = p25_rtt = p50_rtt = p75_rtt = p90_rtt = 0

    # Count overuse events (state transitions to Overusing)
    overuse_pattern = r'\[GCC-DECISION-SNAPSHOT\].*DelayState: Overusing'
    overuse_count = len(re.findall(overuse_pattern, content))

    return p10_rtt, p25_rtt, p50_rtt, p75_rtt, p90_rtt, media_bitrate, overuse_count

def calculate_score(rtt, bitrate):
    """Calculate performance score (higher is better)"""
    return bitrate / rtt if rtt > 0 else 0


def plot_video_quality_comparison(output_path):
    """Plot video quality metrics comparison (PSNR, SSIM, VMAF, LPIPS)"""
    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    axes = axes.flatten()

    # Data: gcchome3 vs ratiohome1
    metrics = [
        ('PSNR (dB)', 29.59, 30.78, 'higher'),    # Higher is better
        ('SSIM', 0.9117, 0.9117, 'higher'),       # Higher is better
        ('VMAF', 29.92, 39.32, 'higher'),         # Higher is better
        ('LPIPS', 0.1681, 0.1327, 'lower'),       # Lower is better
    ]

    for idx, (name, gcc_val, ratio_val, better) in enumerate(metrics):
        ax = axes[idx]
        x = np.arange(2)
        width = 0.5

        bars = ax.bar(x, [gcc_val, ratio_val], width,
                      color=['#87CEEB', '#1E3A5F'],
                      edgecolor=['#4682B4', '#0D1B2A'], linewidth=2)
        bars[1].set_hatch('//')

        # Add value labels
        max_val = max(gcc_val, ratio_val) if max(gcc_val, ratio_val) > 0 else 1
        min_val = min(gcc_val, ratio_val)
        for bar, val in zip(bars, [gcc_val, ratio_val]):
            height = bar.get_height()
            # Format based on metric type
            if name == 'SSIM' or name == 'LPIPS':
                label = f'{val:.4f}'
            else:
                label = f'{val:.2f}'
            label_y = height + max_val * 0.02
            ax.text(bar.get_x() + bar.get_width()/2, label_y, label,
                    ha='center', va='bottom', fontsize=13, fontweight='bold')

        ax.set_title(name, fontsize=15, fontweight='bold', pad=10)
        ax.set_xticks(x)
        ax.set_xticklabels(['GCC', 'Ratio'], fontsize=12, fontweight='bold')
        ax.set_ylim(bottom=0, top=max_val * 1.15)
        ax.grid(True, axis='y', alpha=0.3, linestyle='--')
        ax.set_axisbelow(True)

    fig.suptitle('Video Quality Metrics: GCC vs Ratio (Home Environment)',
                 fontsize=17, fontweight='bold', y=1.02)

    plt.tight_layout()

    # Save
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Video quality comparison chart saved to: {output_path}")

    pdf_path = output_path.with_suffix('.pdf')
    plt.savefig(pdf_path, bbox_inches='tight')
    print(f"PDF saved to: {pdf_path}")

    plt.close()


def plot_metrics_comparison(env_name, metrics_data, output_path, unified_ylims=None):
    """Plot detailed metrics comparison between GCC and Ratio"""
    n_metrics = len(metrics_data)
    if n_metrics <= 3:
        fig, axes = plt.subplots(1, n_metrics, figsize=(4*n_metrics, 5))
    elif n_metrics <= 6:
        rows = 2
        cols = (n_metrics + 1) // 2
        fig, axes = plt.subplots(rows, cols, figsize=(4*cols, 8))
    else:
        fig, axes = plt.subplots(2, 3, figsize=(14, 9))
    axes = np.atleast_1d(axes).flatten()

    for idx, (name, gcc_val, ratio_val, better) in enumerate(metrics_data):
        ax = axes[idx]
        x = np.arange(2)
        width = 0.5

        bars = ax.bar(x, [gcc_val, ratio_val], width,
                      color=['#87CEEB', '#1E3A5F'],
                      edgecolor=['#4682B4', '#0D1B2A'], linewidth=2)
        bars[1].set_hatch('//')

        # Use unified y-limits if provided, otherwise calculate from data
        if unified_ylims and name in unified_ylims:
            max_val = unified_ylims[name]
        else:
            max_val = max(gcc_val, ratio_val) if max(gcc_val, ratio_val) > 0 else 1

        # Add value labels
        for bar, val in zip(bars, [gcc_val, ratio_val]):
            height = bar.get_height()
            label_y = height + max_val * 0.03
            ax.text(bar.get_x() + bar.get_width()/2, label_y,
                    f'{val:.2f}' if val > 0 else '0',
                    ha='center', va='bottom', fontsize=12, fontweight='bold')

        ax.set_title(name, fontsize=13, fontweight='bold', pad=10)
        ax.set_xticks(x)
        ax.set_xticklabels(['GCC', 'Ratio'], fontsize=11, fontweight='bold')
        ax.set_ylim(bottom=0, top=max_val * 1.25)
        ax.grid(True, axis='y', alpha=0.3, linestyle='--')
        ax.set_axisbelow(True)

    # Hide unused subplots
    for idx in range(len(metrics_data), len(axes)):
        axes[idx].set_visible(False)

    fig.suptitle(f'Quality Metrics Comparison: GCC vs Ratio ({env_name} Environment)',
                 fontsize=16, fontweight='bold', y=1.02)

    plt.tight_layout()

    # Save
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Metrics comparison chart saved to: {output_path}")

    pdf_path = output_path.with_suffix('.pdf')
    plt.savefig(pdf_path, bbox_inches='tight')
    print(f"PDF saved to: {pdf_path}")

    plt.close()


def plot_overuse_comparison(ratio_data, gcc_data, env_name, output_path):
    """Plot overuse count comparison bar chart"""
    fig, ax = plt.subplots(figsize=(8, 6))

    # Calculate average overuse counts
    gcc_avg_overuse = np.mean([gcc_data[0]['overuse_count'], gcc_data[1]['overuse_count']])
    ratio_avg_overuse = np.mean([ratio_data[0]['overuse_count'], ratio_data[1]['overuse_count']])

    x = np.arange(2)
    width = 0.5

    # Plot bars - GCC (light blue) and Ratio (dark blue with hatch)
    bars = ax.bar(x, [gcc_avg_overuse, ratio_avg_overuse], width,
                  color=['#87CEEB', '#1E3A5F'], edgecolor=['#4682B4', '#0D1B2A'], linewidth=2)
    bars[1].set_hatch('//')

    # Add value labels on top of bars
    for bar, val in zip(bars, [gcc_avg_overuse, ratio_avg_overuse]):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                f'{val:.0f}', ha='center', va='bottom', fontsize=16, fontweight='bold')

    # Calculate improvement
    overuse_reduction = ((gcc_avg_overuse - ratio_avg_overuse) / gcc_avg_overuse * 100)

    # Add improvement text box
    textstr = f'Ratio vs GCC:\nOveruse: {-overuse_reduction:+.1f}%'
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.85)
    ax.text(0.98, 0.98, textstr, transform=ax.transAxes, fontsize=13,
            verticalalignment='top', horizontalalignment='right', bbox=props, fontweight='bold')

    # Labels and title
    ax.set_ylabel('Average Overuse Count', fontsize=14, fontweight='bold')
    ax.set_title(f'Overuse Events Comparison ({env_name} Environment)',
                fontsize=16, fontweight='bold', pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(['GCC', 'Ratio'], fontsize=14, fontweight='bold')
    ax.tick_params(axis='y', labelsize=11)

    # Grid
    ax.grid(True, axis='y', alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)

    # Set y-axis to start from 0
    ax.set_ylim(bottom=0, top=max(gcc_avg_overuse, ratio_avg_overuse) * 1.15)

    plt.tight_layout()

    # Save
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Overuse comparison chart saved to: {output_path}")

    pdf_path = output_path.with_suffix('.pdf')
    plt.savefig(pdf_path, bbox_inches='tight')
    print(f"PDF saved to: {pdf_path}")

    plt.close()


def plot_rtt_percentile_bars(ratio_data, gcc_data, env_name, output_path):
    """Plot RTT percentile bar chart for an environment (averaged within groups)"""
    percentiles = ['P10', 'P25', 'P50', 'P75', 'P90']
    x = np.arange(len(percentiles))
    width = 0.35  # Width of each bar

    fig, ax = plt.subplots(figsize=(10, 7))

    # Calculate average RTT for each percentile within GCC and Ratio groups
    gcc_avg_rtts = [
        np.mean([gcc_data[0]['p10_rtt'], gcc_data[1]['p10_rtt']]),
        np.mean([gcc_data[0]['p25_rtt'], gcc_data[1]['p25_rtt']]),
        np.mean([gcc_data[0]['p50_rtt'], gcc_data[1]['p50_rtt']]),
        np.mean([gcc_data[0]['p75_rtt'], gcc_data[1]['p75_rtt']]),
        np.mean([gcc_data[0]['p90_rtt'], gcc_data[1]['p90_rtt']]),
    ]
    ratio_avg_rtts = [
        np.mean([ratio_data[0]['p10_rtt'], ratio_data[1]['p10_rtt']]),
        np.mean([ratio_data[0]['p25_rtt'], ratio_data[1]['p25_rtt']]),
        np.mean([ratio_data[0]['p50_rtt'], ratio_data[1]['p50_rtt']]),
        np.mean([ratio_data[0]['p75_rtt'], ratio_data[1]['p75_rtt']]),
        np.mean([ratio_data[0]['p90_rtt'], ratio_data[1]['p90_rtt']]),
    ]

    # Plot bars - GCC (light blue) and Ratio (dark blue with hatch)
    bars_gcc = ax.bar(x - width/2, gcc_avg_rtts, width, label='GCC',
                      color='#87CEEB', edgecolor='#4682B4', linewidth=2)
    bars_ratio = ax.bar(x + width/2, ratio_avg_rtts, width, label='Ratio',
                        color='#1E3A5F', edgecolor='#0D1B2A', linewidth=2, hatch='//')

    # Labels and title
    ax.set_xlabel('Percentile', fontsize=14, fontweight='bold')
    ax.set_ylabel('RTT (ms)', fontsize=14, fontweight='bold')
    ax.set_title(f'RTT Percentile Comparison ({env_name} Environment)',
                 fontsize=16, fontweight='bold', pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(percentiles, fontsize=12)
    ax.tick_params(axis='y', labelsize=11)

    # Legend
    ax.legend(loc='upper left', fontsize=12, framealpha=0.95)

    # Grid
    ax.grid(True, axis='y', alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)

    # Set y-axis to start from 0
    ax.set_ylim(bottom=0)

    plt.tight_layout()

    # Save
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"RTT percentile bar chart saved to: {output_path}")

    # Also save PDF
    pdf_path = output_path.with_suffix('.pdf')
    plt.savefig(pdf_path, bbox_inches='tight')
    print(f"PDF saved to: {pdf_path}")

    plt.close()

def plot_environment(best_ratio, worst_gcc, env_name, output_prefix, data_dir):
    """Plot comparison for a specific environment"""

    print(f"\n=== {env_name} Environment ===")
    print(f"Best 2 Ratio:")
    for i, data in enumerate(best_ratio, 1):
        print(f"  {i}. {data['label']}: {data['bitrate']:.2f} Mbps @ {data['rtt']:.1f} ms (median RTT)")

    print(f"Worst 2 GCC:")
    for i, data in enumerate(worst_gcc, 1):
        print(f"  {i}. {data['label']}: {data['bitrate']:.2f} Mbps @ {data['rtt']:.1f} ms (median RTT)")

    # Calculate averages
    ratio_avg_rtt = np.mean([d['rtt'] for d in best_ratio])
    ratio_avg_br = np.mean([d['bitrate'] for d in best_ratio])
    gcc_avg_rtt = np.mean([d['rtt'] for d in worst_gcc])
    gcc_avg_br = np.mean([d['bitrate'] for d in worst_gcc])

    print(f"\nAveraged values:")
    print(f"  Ratio avg: {ratio_avg_br:.2f} Mbps @ {ratio_avg_rtt:.1f} ms")
    print(f"  GCC avg: {gcc_avg_br:.2f} Mbps @ {gcc_avg_rtt:.1f} ms")

    # Create the plot
    fig, ax = plt.subplots(figsize=(10, 7))

    # Plot only 2 points: Ratio average (circle) and GCC average (pentagon)
    # Using light green and light blue colors
    ax.scatter([ratio_avg_rtt], [ratio_avg_br],
              marker='o', s=400, color='#90EE90',  # Light green
              edgecolors='#228B22', linewidths=3, alpha=0.9,
              label='Ratio', zorder=10)

    ax.scatter([gcc_avg_rtt], [gcc_avg_br],
              marker='p', s=400, color='#87CEEB',  # Light blue (sky blue)
              edgecolors='#4682B4', linewidths=3, alpha=0.9,
              label='GCC', zorder=10)

    # Add labels
    ax.annotate('Ratio', (ratio_avg_rtt, ratio_avg_br),
               xytext=(12, 12), textcoords='offset points',
               fontsize=13, fontweight='bold')

    ax.annotate('GCC', (gcc_avg_rtt, gcc_avg_br),
               xytext=(12, 12), textcoords='offset points',
               fontsize=13, fontweight='bold')

    # Calculate improvements
    rtt_improvement = ((gcc_avg_rtt - ratio_avg_rtt) / gcc_avg_rtt * 100)
    br_improvement = ((ratio_avg_br - gcc_avg_br) / gcc_avg_br * 100)

    # Add improvement text box (top-left)
    textstr = f'Ratio vs GCC:\n'
    textstr += f'RTT: {-rtt_improvement:+.1f}%\n'  # Show as negative (reduction)
    textstr += f'Bitrate: {br_improvement:+.1f}%'

    props = dict(boxstyle='round', facecolor='wheat', alpha=0.85)
    ax.text(0.02, 0.98, textstr, transform=ax.transAxes, fontsize=14,
            verticalalignment='top', bbox=props, fontweight='bold')

    # Add "Better" annotation with diagonal arrow (lower-right to upper-left)
    # Use larrow boxstyle with rotation to point upper-left, text follows arrow
    bbox_props = dict(boxstyle='larrow,pad=0.3', facecolor='white',
                     edgecolor='black', linewidth=2)
    ax.text(0.88, 0.88, 'Better', transform=ax.transAxes,
            fontsize=14, fontweight='bold',
            bbox=bbox_props, ha='center', va='center',
            rotation=-45)  # Arrow head upper-left, text follows arrow direction

    # Labels and title
    ax.set_xlabel('Median RTT (ms)', fontsize=15, fontweight='bold')
    ax.set_ylabel('Average Media Bitrate (Mbps)', fontsize=15, fontweight='bold')
    ax.set_title(f'WebRTC Performance Comparison ({env_name} Environment)',
                fontsize=17, fontweight='bold', pad=20)

    # Grid
    ax.grid(True, alpha=0.3, linestyle='--', linewidth=1.5)

    # Legend - only 2 items
    ax.legend(loc='lower right', fontsize=14, framealpha=0.95,
             edgecolor='black', fancybox=True, shadow=True)

    # Set axis limits with padding
    all_rtts = [ratio_avg_rtt, gcc_avg_rtt]
    all_bitrates = [ratio_avg_br, gcc_avg_br]

    rtt_range = max(all_rtts) - min(all_rtts)
    br_range = max(all_bitrates) - min(all_bitrates)

    # Add extra padding
    rtt_margin = max(rtt_range * 0.3, 5)  # At least 5ms margin
    br_margin = max(br_range * 0.3, 1)    # At least 1 Mbps margin

    ax.set_xlim(min(all_rtts) - rtt_margin, max(all_rtts) + rtt_margin)
    ax.set_ylim(min(all_bitrates) - br_margin, max(all_bitrates) + br_margin)

    # Tight layout
    plt.tight_layout()

    # Save figures
    output_png = data_dir / f'{output_prefix}_avg_comparison.png'
    plt.savefig(output_png, dpi=300, bbox_inches='tight')
    print(f"Plot saved to: {output_png}")

    output_pdf = data_dir / f'{output_prefix}_avg_comparison.pdf'
    plt.savefig(output_pdf, bbox_inches='tight')
    print(f"PDF saved to: {output_pdf}")

    plt.close()

    # Print statistics
    print(f"Improvement: RTT {rtt_improvement:+.1f}%, Bitrate {br_improvement:+.1f}%")

def main():
    # Data directory
    data_dir = Path('/home/qwu26/webrtc-local/webrtc_config_results/ratio result')

    # Collect data by environment
    gcc_lab_results = []
    ratio_lab_results = []
    gcc_home_results = []
    ratio_home_results = []

    # Process all log files
    all_results = []
    for log_file in sorted(data_dir.glob('*.log')):
        filename = log_file.name

        # Extract metrics (RTT percentiles, average bitrate, and overuse count)
        p10_rtt, p25_rtt, p50_rtt, p75_rtt, p90_rtt, bitrate, overuse_count = extract_metrics(log_file)
        bitrate_mbps = bitrate / 1000  # Convert to Mbps

        # Calculate performance score (using P50)
        score = calculate_score(p50_rtt, bitrate_mbps)

        label = filename.replace('sender_local.log', '')

        data = {
            'filename': filename,
            'label': label,
            'rtt': p50_rtt,  # P50 for plotting
            'p10_rtt': p10_rtt,
            'p25_rtt': p25_rtt,
            'p50_rtt': p50_rtt,
            'p75_rtt': p75_rtt,
            'p90_rtt': p90_rtt,
            'bitrate': bitrate_mbps,
            'overuse_count': overuse_count,
            'score': score
        }
        all_results.append(data)

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

        # Print RTT percentile statistics for selected logs
        selected_lab = best_ratio_lab + worst_gcc_lab
        print("\n" + "=" * 115)
        print("Lab Environment - RTT Percentile & Overuse Statistics (Selected Logs)")
        print("=" * 115)
        print(f"{'Log File':<20} {'P10 (ms)':<10} {'P25 (ms)':<10} {'P50 (ms)':<10} {'P75 (ms)':<10} {'P90 (ms)':<10} {'Bitrate (Mbps)':<15} {'Overuse':<10}")
        print("-" * 115)
        for data in selected_lab:
            print(f"{data['label']:<20} {data['p10_rtt']:<10.1f} {data['p25_rtt']:<10.1f} {data['p50_rtt']:<10.1f} {data['p75_rtt']:<10.1f} {data['p90_rtt']:<10.1f} {data['bitrate']:<15.2f} {data['overuse_count']:<10}")
        print("=" * 115)

        plot_environment(best_ratio_lab, worst_gcc_lab, 'Lab', 'lab', data_dir)

        # Plot RTT percentile bar chart for Lab
        bar_output_lab = data_dir / 'lab_rtt_percentile_bars.png'
        plot_rtt_percentile_bars(best_ratio_lab, worst_gcc_lab, 'Lab', bar_output_lab)

        # Plot overuse comparison chart for Lab
        overuse_output_lab = data_dir / 'lab_overuse_comparison.png'
        plot_overuse_comparison(best_ratio_lab, worst_gcc_lab, 'Lab', overuse_output_lab)

    # Process Home environment
    if ratio_home_results and gcc_home_results:
        # Best 2 Ratio (highest scores)
        ratio_home_results.sort(key=lambda x: x['score'], reverse=True)
        best_ratio_home = ratio_home_results[:2]

        # Worst 2 GCC (lowest scores)
        gcc_home_results.sort(key=lambda x: x['score'])
        worst_gcc_home = gcc_home_results[:2]

        # Print RTT percentile statistics for selected logs
        selected_home = best_ratio_home + worst_gcc_home
        print("\n" + "=" * 115)
        print("Home Environment - RTT Percentile & Overuse Statistics (Selected Logs)")
        print("=" * 115)
        print(f"{'Log File':<20} {'P10 (ms)':<10} {'P25 (ms)':<10} {'P50 (ms)':<10} {'P75 (ms)':<10} {'P90 (ms)':<10} {'Bitrate (Mbps)':<15} {'Overuse':<10}")
        print("-" * 115)
        for data in selected_home:
            print(f"{data['label']:<20} {data['p10_rtt']:<10.1f} {data['p25_rtt']:<10.1f} {data['p50_rtt']:<10.1f} {data['p75_rtt']:<10.1f} {data['p90_rtt']:<10.1f} {data['bitrate']:<15.2f} {data['overuse_count']:<10}")
        print("=" * 115)

        plot_environment(best_ratio_home, worst_gcc_home, 'Home', 'home', data_dir)

        # Plot RTT percentile bar chart for Home
        bar_output_home = data_dir / 'home_rtt_percentile_bars.png'
        plot_rtt_percentile_bars(best_ratio_home, worst_gcc_home, 'Home', bar_output_home)

        # Plot overuse comparison chart for Home
        overuse_output_home = data_dir / 'home_overuse_comparison.png'
        plot_overuse_comparison(best_ratio_home, worst_gcc_home, 'Home', overuse_output_home)

    # Plot detailed metrics comparison for Home (gcchome3 vs ratiohome1)
    home_metrics = [
        ('QP Value', 31.71, 30.79, 'lower'),       # Lower is better
        ('Freeze Rate (%)', 3.55, 1.21, 'lower'),  # Lower is better
        ('Switch Rate (%)', 4.05, 2.70, 'lower'),  # Lower is better
        ('FPS', 28.97, 29.58, 'higher'),           # Higher is better
        ('Frame Drop (%)', 0, 0, 'lower'),         # Lower is better
    ]

    # Plot detailed metrics comparison for Lab
    lab_metrics = [
        ('QP Value', 9.14, 4.92, 'lower'),         # Lower is better
        ('Freeze Rate (%)', 0.25, 0.37, 'lower'),  # Lower is better
        ('Switch Rate (%)', 2.75, 2.04, 'lower'),  # Lower is better
        ('FPS', 29.87, 29.81, 'higher'),           # Higher is better
        ('Frame Drop (%)', 0, 0, 'lower'),         # Lower is better
    ]

    # Calculate unified y-limits across both environments
    unified_ylims = {}
    for i, (name, home_gcc, home_ratio, _) in enumerate(home_metrics):
        lab_gcc = lab_metrics[i][1]
        lab_ratio = lab_metrics[i][2]
        max_val = max(home_gcc, home_ratio, lab_gcc, lab_ratio)
        unified_ylims[name] = max_val if max_val > 0 else 1

    metrics_output_home = data_dir / 'home_quality_metrics_comparison.png'
    plot_metrics_comparison('Home', home_metrics, metrics_output_home, unified_ylims)

    metrics_output_lab = data_dir / 'lab_quality_metrics_comparison.png'
    plot_metrics_comparison('Lab', lab_metrics, metrics_output_lab, unified_ylims)

    # Plot video quality metrics (PSNR, SSIM, VMAF, LPIPS) for Home
    video_quality_output = data_dir / 'home_video_quality_comparison.png'
    plot_video_quality_comparison(video_quality_output)

    print("\n✓ All plots generated successfully!")

if __name__ == '__main__':
    main()

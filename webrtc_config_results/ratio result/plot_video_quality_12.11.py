#!/usr/bin/env python3
"""
Plot video quality metrics comparison: GCC 12.1 vs Ratio 12.10
Date: 12.11
"""

import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path


def plot_video_quality_comparison(output_path):
    """Plot video quality metrics comparison (PSNR, SSIM, VMAF, LPIPS)"""
    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    axes = axes.flatten()

    # Data: GCC 12.1 vs Ratio 12.10
    metrics = [
        ('PSNR (dB)', 28.42, 29.32, 'higher', '+3.2%'),    # Higher is better
        ('SSIM', 0.9156, 0.9213, 'higher', '+0.6%'),       # Higher is better
        ('VMAF', 37.35, 43.43, 'higher', '+16.3%'),        # Higher is better
        ('LPIPS', 0.1554, 0.1137, 'lower', '-26.8%'),      # Lower is better
    ]

    for idx, (name, gcc_val, ratio_val, better, pct_diff) in enumerate(metrics):
        ax = axes[idx]
        x = np.arange(2)
        width = 0.5

        bars = ax.bar(x, [gcc_val, ratio_val], width,
                      color=['#87CEEB', '#1E3A5F'],
                      edgecolor=['#4682B4', '#0D1B2A'], linewidth=2)
        bars[1].set_hatch('//')

        # Add value labels
        max_val = max(gcc_val, ratio_val) if max(gcc_val, ratio_val) > 0 else 1
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

        # Add percentage difference annotation in the middle
        # Determine color based on whether improvement is good
        if better == 'higher':
            pct_color = '#228B22' if ratio_val > gcc_val else '#DC143C'  # Green if improved, red if worse
        else:
            pct_color = '#228B22' if ratio_val < gcc_val else '#DC143C'  # Green if decreased (for LPIPS)

        ax.text(0.5, 0.5, pct_diff, transform=ax.transAxes,
                fontsize=18, fontweight='bold', color=pct_color,
                ha='center', va='center',
                bbox=dict(boxstyle='round,pad=0.4', facecolor='white', edgecolor=pct_color, alpha=0.9))

        ax.set_title(name, fontsize=15, fontweight='bold', pad=10)
        ax.set_xticks(x)
        ax.set_xticklabels(['GCC', 'Ratio'], fontsize=12, fontweight='bold')
        ax.set_ylim(bottom=0, top=max_val * 1.20)
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


def main():
    data_dir = Path('/home/qwu26/webrtc-local/webrtc_config_results/ratio result')
    output_path = data_dir / 'home_video_quality_12.11.png'
    plot_video_quality_comparison(output_path)
    print("\n✓ Plot generated successfully!")


if __name__ == '__main__':
    main()

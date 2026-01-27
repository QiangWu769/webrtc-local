#!/usr/bin/env python3
"""
Plot performance metrics comparison: GCC vs Ratio 12.10
Date: 12.11
"""

import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path


def plot_performance_comparison(output_path):
    """Plot performance metrics comparison (Switch Rate, Freeze Rate, QP, Frame Drop)"""
    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    axes = axes.flatten()

    # Data: GCC avg vs Ratio 12.10
    # All metrics: lower is better
    metrics = [
        ('Switch Rate (%)', 5.51, 5.17, 'lower', '-6.2%'),      # 0.0551 -> 5.51%
        ('Freeze Rate (%)', 1.41, 0.68, 'lower', '-51.9%'),     # Lower is better
        ('QP', 23.28, 13.68, 'lower', '-41.2%'),                # Lower is better
        ('Frame Drop (%)', 0.00, 0.00, 'lower', ''),              # Both zero
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
            if name == 'QP':
                label = f'{val:.2f}'
            else:
                label = f'{val:.2f}%'
            label_y = height + max_val * 0.02
            ax.text(bar.get_x() + bar.get_width()/2, label_y, label,
                    ha='center', va='bottom', fontsize=13, fontweight='bold')

        # Add percentage difference annotation in the middle (skip if empty)
        if pct_diff:
            # For all these metrics, lower is better, so negative change is good
            if pct_diff.startswith('-'):
                pct_color = '#228B22'  # Green for reduction (improvement)
            else:
                pct_color = '#DC143C'  # Red for increase (worse)

            ax.text(0.5, 0.5, pct_diff, transform=ax.transAxes,
                    fontsize=18, fontweight='bold', color=pct_color,
                    ha='center', va='center',
                    bbox=dict(boxstyle='round,pad=0.4', facecolor='white', edgecolor=pct_color, alpha=0.9))

        ax.set_title(name, fontsize=15, fontweight='bold', pad=10)
        ax.set_xticks(x)
        ax.set_xticklabels(['GCC', 'Ratio'], fontsize=12, fontweight='bold')
        ax.set_ylim(bottom=0, top=max_val * 1.25 if max_val > 0 else 1)
        ax.grid(True, axis='y', alpha=0.3, linestyle='--')
        ax.set_axisbelow(True)

    fig.suptitle('Performance Metrics: GCC vs Ratio (Home Environment)',
                 fontsize=17, fontweight='bold', y=1.02)

    plt.tight_layout()

    # Save
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Performance comparison chart saved to: {output_path}")

    pdf_path = output_path.with_suffix('.pdf')
    plt.savefig(pdf_path, bbox_inches='tight')
    print(f"PDF saved to: {pdf_path}")

    plt.close()


def main():
    data_dir = Path('/home/qwu26/webrtc-local/webrtc_config_results/ratio result')
    output_path = data_dir / 'home_performance_12.11.png'
    plot_performance_comparison(output_path)
    print("\n✓ Plot generated successfully!")


if __name__ == '__main__':
    main()

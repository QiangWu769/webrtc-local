#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verify Smoothed M Value Calculation

This script demonstrates the difference between using raw vs smoothed values for M calculation.
"""

import re
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

class WindowedEWMA:
    """Python implementation of WindowedEWMA to match C++ behavior"""
    def __init__(self, alpha=0.6, window_size=10):
        self.alpha = alpha
        self.window_size = window_size
        self.values = []

    def update(self, value):
        self.values.append(value)
        if len(self.values) > self.window_size:
            self.values.pop(0)

        if len(self.values) == 1:
            return value

        # Calculate EWMA over the window
        ewma = self.values[0]
        for v in self.values[1:]:
            ewma = self.alpha * v + (1 - self.alpha) * ewma
        return ewma

    def get_sample_count(self):
        return len(self.values)

def calculate_ratio_score(ratio):
    """Calculate ratio score from ratio value"""
    if ratio < 0.15:
        return 1.0
    elif ratio < 0.3:
        return 1.0 - (ratio - 0.15) / 0.15
    elif ratio < 0.5:
        return 1.0 - (ratio - 0.15) / 0.35
    else:
        return max(0.0, 1.0 - (ratio - 0.5) / 1.5)

def calculate_sat_score(saturation):
    """Calculate saturation score from saturation value"""
    if saturation >= 0.85 and saturation <= 1.5:
        return 1.0
    elif saturation >= 0.7 and saturation < 0.85:
        return (saturation - 0.7) / 0.15
    elif saturation > 1.5 and saturation <= 2.0:
        return 1.0 - (saturation - 1.5) / 0.5
    elif saturation < 0.7:
        return max(0.0, saturation / 0.7)
    else:  # saturation > 2.0
        return max(0.0, 1.0 - (saturation - 2.0) / 2.0)

def parse_old_format_logs(log_file):
    """Parse old format logs (before smoothing M)"""
    pattern = re.compile(r'\[AIMD-Cellular\] Ratio: ([0-9.]+), Saturation: ([-0-9.]+), M: ([0-9.]+)')

    data = []
    with open(log_file, 'r') as f:
        for line in f:
            match = pattern.search(line)
            if match:
                ratio = float(match.group(1))
                saturation = float(match.group(2))
                m_value = float(match.group(3))
                data.append({
                    'ratio': ratio,
                    'saturation': saturation,
                    'm_value': m_value
                })

    return pd.DataFrame(data)

def simulate_smoothed_m(df):
    """Simulate what M would be with smoothing"""
    ratio_smoother = WindowedEWMA(alpha=0.6, window_size=10)
    sat_smoother = WindowedEWMA(alpha=0.6, window_size=10)

    smoothed_data = []

    for _, row in df.iterrows():
        # Update smoothers
        smoothed_ratio = ratio_smoother.update(row['ratio'])
        smoothed_sat = sat_smoother.update(row['saturation'])

        # Calculate scores using smoothed values
        ratio_score = calculate_ratio_score(smoothed_ratio)
        sat_score = calculate_sat_score(smoothed_sat)

        # Calculate smoothed M
        smoothed_m = 0.10 * sat_score + 0.90 * ratio_score

        smoothed_data.append({
            'raw_ratio': row['ratio'],
            'raw_saturation': row['saturation'],
            'raw_m': row['m_value'],
            'smoothed_ratio': smoothed_ratio,
            'smoothed_saturation': smoothed_sat,
            'smoothed_m': smoothed_m,
            'samples': ratio_smoother.get_sample_count()
        })

    return pd.DataFrame(smoothed_data)

def plot_comparison(df):
    """Plot comparison of raw vs smoothed M values"""
    fig, axes = plt.subplots(3, 1, figsize=(16, 12))

    # Plot 1: Ratio comparison
    ax1 = axes[0]
    ax1.plot(df.index, df['raw_ratio'], color='#2E86AB', linewidth=1, alpha=0.4, label='Raw Ratio')
    ax1.plot(df.index, df['smoothed_ratio'], color='#2E86AB', linewidth=2, alpha=0.9, label='Smoothed Ratio (10-point EWMA)')
    ax1.set_ylabel('Ratio', fontsize=12)
    ax1.set_title('Ratio: Raw vs Smoothed (α=0.6, window=10)', fontsize=14, fontweight='bold')
    ax1.legend(loc='upper right')
    ax1.grid(True, alpha=0.3)

    # Plot 2: Saturation comparison
    ax2 = axes[1]
    ax2.plot(df.index, df['raw_saturation'], color='#FF6B35', linewidth=1, alpha=0.4, label='Raw Saturation')
    ax2.plot(df.index, df['smoothed_saturation'], color='#FF6B35', linewidth=2, alpha=0.9, label='Smoothed Saturation (10-point EWMA)')
    ax2.set_ylabel('Saturation', fontsize=12)
    ax2.set_title('Saturation: Raw vs Smoothed (α=0.6, window=10)', fontsize=14, fontweight='bold')
    ax2.legend(loc='upper right')
    ax2.grid(True, alpha=0.3)

    # Plot 3: M value comparison
    ax3 = axes[2]
    ax3.plot(df.index, df['raw_m'], color='#C73E1D', linewidth=1, alpha=0.4, label='Raw M Value')
    ax3.plot(df.index, df['smoothed_m'], color='#00AA00', linewidth=2, alpha=0.9, label='Smoothed M Value')
    ax3.set_ylabel('M Value', fontsize=12)
    ax3.set_xlabel('Sample Index', fontsize=12)
    ax3.set_title('M Value: Raw vs Smoothed', fontsize=14, fontweight='bold')
    ax3.legend(loc='upper right')
    ax3.grid(True, alpha=0.3)
    ax3.set_ylim(0, 1.0)

    plt.tight_layout()
    output_file = '/home/wuq/webrtc-local/webrtc_config_results/m_value_smoothing_comparison.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Plot saved to: {output_file}")

    return output_file

def print_statistics(df):
    """Print statistics comparing raw and smoothed M values"""
    print("\n" + "="*60)
    print("M VALUE SMOOTHING COMPARISON")
    print("="*60)

    print(f"\nTotal samples: {len(df)}")

    print("\nRaw M Value Statistics:")
    print(f"  Mean: {df['raw_m'].mean():.4f}")
    print(f"  Std Dev: {df['raw_m'].std():.4f}")
    print(f"  Min: {df['raw_m'].min():.4f}")
    print(f"  Max: {df['raw_m'].max():.4f}")

    print("\nSmoothed M Value Statistics:")
    print(f"  Mean: {df['smoothed_m'].mean():.4f}")
    print(f"  Std Dev: {df['smoothed_m'].std():.4f}")
    print(f"  Min: {df['smoothed_m'].min():.4f}")
    print(f"  Max: {df['smoothed_m'].max():.4f}")

    # Calculate volatility reduction
    raw_volatility = df['raw_m'].std()
    smoothed_volatility = df['smoothed_m'].std()
    reduction = (raw_volatility - smoothed_volatility) / raw_volatility * 100

    print(f"\nVolatility Reduction: {reduction:.1f}%")

    # Calculate differences
    df['m_diff'] = abs(df['raw_m'] - df['smoothed_m'])
    print(f"\nAverage M value difference: {df['m_diff'].mean():.4f}")
    print(f"Max M value difference: {df['m_diff'].max():.4f}")

def main():
    log_file = '/home/wuq/webrtc-local/webrtc_config_results/sat3sender_local.log'

    print("M Value Smoothing Verification")
    print("="*60)
    print(f"Analyzing log file: {log_file}")

    # Parse old format logs
    print("\n[*] Parsing logs with raw M values...")
    df_raw = parse_old_format_logs(log_file)

    if df_raw.empty:
        print("[!] No M value data found in log file")
        return

    print(f"[*] Found {len(df_raw)} M value entries")

    # Simulate smoothed M values
    print("[*] Simulating smoothed M value calculation...")
    df_comparison = simulate_smoothed_m(df_raw)

    # Print statistics
    print_statistics(df_comparison)

    # Generate plot
    print("\n[*] Generating comparison plot...")
    plot_comparison(df_comparison)

    print("\n[*] Analysis complete!")

if __name__ == "__main__":
    main()

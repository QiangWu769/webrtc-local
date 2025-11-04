#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M Value and Target Bitrate Correlation Analysis

This script analyzes the relationship between M value (combined metric)
and target bitrate changes in WebRTC congestion control.
"""

import re
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from scipy import stats
import argparse
import sys
import os

class MValueBitrateAnalyzer:
    def __init__(self, log_file_path):
        self.log_file_path = log_file_path

        # Regular expressions for parsing
        self.patterns = {
            'wall_clock': re.compile(r'\[([0-9]{10}\.[0-9]{3,6})\]'),
            'm_value': re.compile(r'\[AIMD-Cellular\] Ratio: ([0-9.]+), Saturation: ([-0-9.]+), M: ([0-9.]+)'),
            'bwe_decision': re.compile(r'\[BWE-DECISION\] (?:Time|MonoTime): (\d+) ms.*?AckedBitrate: (\d+) bps.*?NewTarget: (\d+) bps'),
            'overusing': re.compile(r'\[([0-9]{10}\.[0-9]{3,6})\].*State: Overusing'),
        }

    def parse_logs(self):
        """Parse logs to extract M value and target bitrate data"""
        m_value_data = []
        bwe_decision_data = []
        overusing_events = []
        current_wall_clock = None
        start_time = None

        with open(self.log_file_path, 'r', encoding='utf-8') as f:
            for line_number, line in enumerate(f):
                # Track wall-clock timestamps
                wall_clock_match = self.patterns['wall_clock'].search(line)
                if wall_clock_match:
                    current_wall_clock = float(wall_clock_match.group(1))
                    if start_time is None:
                        start_time = current_wall_clock

                # Extract M value data
                if 'AIMD-Cellular' in line:
                    m_match = self.patterns['m_value'].search(line)
                    if m_match and current_wall_clock is not None and start_time is not None:
                        ratio = float(m_match.group(1))
                        saturation = float(m_match.group(2))
                        m_value = float(m_match.group(3))
                        relative_time = current_wall_clock - start_time

                        m_value_data.append({
                            'timestamp': relative_time,
                            'ratio': ratio,
                            'saturation': saturation,
                            'm_value': m_value,
                            'line_number': line_number
                        })

                # Extract BWE decision data
                if 'BWE-DECISION' in line and current_wall_clock is not None:
                    bwe_match = self.patterns['bwe_decision'].search(line)
                    if bwe_match:
                        monotime = int(bwe_match.group(1))
                        acked_bitrate = int(bwe_match.group(2))
                        new_target = int(bwe_match.group(3))
                        relative_time = current_wall_clock - start_time if start_time else 0

                        bwe_decision_data.append({
                            'timestamp': relative_time,
                            'new_target': new_target,
                            'acked_bitrate': acked_bitrate,
                            'line_number': line_number
                        })

                # Extract overusing events
                over_match = self.patterns['overusing'].search(line)
                if over_match:
                    wall_time = float(over_match.group(1))
                    if start_time is not None:
                        relative_time = wall_time - start_time
                        overusing_events.append(relative_time)

        # Convert to DataFrames
        m_value_df = pd.DataFrame(m_value_data)
        bwe_df = pd.DataFrame(bwe_decision_data)

        print(f"[*] Found {len(m_value_df)} M value points")
        print(f"[*] Found {len(bwe_df)} BWE decision points")
        print(f"[*] Found {len(overusing_events)} overusing events")

        return m_value_df, bwe_df, overusing_events

    def align_data(self, m_value_df, bwe_df):
        """Align M value with target bitrate by matching timestamps"""
        if m_value_df.empty or bwe_df.empty:
            return pd.DataFrame()

        aligned_data = []

        # For each M value point, find the closest BWE decision
        for _, m_row in m_value_df.iterrows():
            m_time = m_row['timestamp']

            # Find closest BWE decision (within 0.5 second window)
            time_diffs = abs(bwe_df['timestamp'] - m_time)
            min_diff_idx = time_diffs.idxmin()
            min_diff = time_diffs[min_diff_idx]

            if min_diff < 0.5:  # Only match if within 0.5 second
                bwe_row = bwe_df.loc[min_diff_idx]
                aligned_data.append({
                    'timestamp': m_time,
                    'm_value': m_row['m_value'],
                    'ratio': m_row['ratio'],
                    'saturation': m_row['saturation'],
                    'target_bitrate': bwe_row['new_target'] / 1000,  # Convert to kbps
                    'acked_bitrate': bwe_row['acked_bitrate'] / 1000,
                    'time_diff': min_diff
                })

        aligned_df = pd.DataFrame(aligned_data)
        print(f"[*] Aligned {len(aligned_df)} data points")

        return aligned_df

    def analyze_correlation(self, aligned_df):
        """Analyze correlation between M value and target bitrate"""
        if aligned_df.empty:
            print("[!] No aligned data to analyze")
            return

        # Calculate correlation
        m_values = aligned_df['m_value'].values
        target_bitrates = aligned_df['target_bitrate'].values

        # Pearson correlation
        pearson_corr, pearson_p = stats.pearsonr(m_values, target_bitrates)

        # Spearman correlation (rank-based, for non-linear relationships)
        spearman_corr, spearman_p = stats.spearmanr(m_values, target_bitrates)

        print("\n" + "="*60)
        print("CORRELATION ANALYSIS: M Value vs Target Bitrate")
        print("="*60)
        print(f"Pearson Correlation:  {pearson_corr:.4f} (p-value: {pearson_p:.4e})")
        print(f"Spearman Correlation: {spearman_corr:.4f} (p-value: {spearman_p:.4e})")

        # Analyze by M value ranges
        print("\n" + "="*60)
        print("TARGET BITRATE BY M VALUE RANGES")
        print("="*60)

        m_ranges = [
            (0.0, 0.2, "Very Low (0.0-0.2)"),
            (0.2, 0.4, "Low (0.2-0.4)"),
            (0.4, 0.6, "Medium (0.4-0.6)"),
            (0.6, 0.8, "High (0.6-0.8)"),
            (0.8, 1.0, "Very High (0.8-1.0)"),
        ]

        for low, high, label in m_ranges:
            mask = (aligned_df['m_value'] >= low) & (aligned_df['m_value'] < high)
            if mask.sum() > 0:
                bitrates = aligned_df[mask]['target_bitrate']
                print(f"\n{label}:")
                print(f"  Count: {mask.sum()}")
                print(f"  Bitrate - Mean: {bitrates.mean():.1f} kbps, Median: {bitrates.median():.1f} kbps")
                print(f"  Bitrate - Min: {bitrates.min():.1f} kbps, Max: {bitrates.max():.1f} kbps")

        # Calculate bitrate change rate by M value
        print("\n" + "="*60)
        print("BITRATE CHANGE ANALYSIS")
        print("="*60)

        aligned_df['bitrate_change'] = aligned_df['target_bitrate'].diff()
        aligned_df['m_change'] = aligned_df['m_value'].diff()

        # Analyze when M value decreases significantly (potential congestion signal)
        m_decrease_mask = aligned_df['m_change'] < -0.1
        if m_decrease_mask.sum() > 0:
            print(f"\nWhen M decreases > 0.1 ({m_decrease_mask.sum()} occurrences):")
            bitrate_changes = aligned_df[m_decrease_mask]['bitrate_change']
            decrease_count = (bitrate_changes < 0).sum()
            increase_count = (bitrate_changes > 0).sum()
            print(f"  Bitrate decreased: {decrease_count} times ({decrease_count/m_decrease_mask.sum()*100:.1f}%)")
            print(f"  Bitrate increased: {increase_count} times ({increase_count/m_decrease_mask.sum()*100:.1f}%)")
            print(f"  Mean bitrate change: {bitrate_changes.mean():.1f} kbps")

        # Analyze when M value increases significantly
        m_increase_mask = aligned_df['m_change'] > 0.1
        if m_increase_mask.sum() > 0:
            print(f"\nWhen M increases > 0.1 ({m_increase_mask.sum()} occurrences):")
            bitrate_changes = aligned_df[m_increase_mask]['bitrate_change']
            decrease_count = (bitrate_changes < 0).sum()
            increase_count = (bitrate_changes > 0).sum()
            print(f"  Bitrate decreased: {decrease_count} times ({decrease_count/m_increase_mask.sum()*100:.1f}%)")
            print(f"  Bitrate increased: {increase_count} times ({increase_count/m_increase_mask.sum()*100:.1f}%)")
            print(f"  Mean bitrate change: {bitrate_changes.mean():.1f} kbps")

        return pearson_corr, spearman_corr

    def plot_analysis(self, m_value_df, bwe_df, aligned_df, overusing_events):
        """Create comprehensive visualization"""
        fig, axes = plt.subplots(3, 1, figsize=(16, 12))

        # Plot 1: Time series of M value and Target Bitrate
        ax1 = axes[0]
        ax1_twin = ax1.twinx()

        # Plot M value on left axis
        ax1.plot(m_value_df['timestamp'], m_value_df['m_value'],
                color='#FF6B35', linewidth=2, alpha=0.8, label='M Value')
        ax1.set_ylabel('M Value', fontsize=12, color='#FF6B35')
        ax1.tick_params(axis='y', labelcolor='#FF6B35')
        ax1.set_ylim(0, 1.0)

        # Plot target bitrate on right axis
        ax1_twin.plot(bwe_df['timestamp'], bwe_df['new_target'] / 1000,
                     color='#C73E1D', linewidth=2, alpha=0.8, label='Target Bitrate')
        ax1_twin.set_ylabel('Target Bitrate (kbps)', fontsize=12, color='#C73E1D')
        ax1_twin.tick_params(axis='y', labelcolor='#C73E1D')

        # Mark overusing events
        if overusing_events:
            for t in overusing_events:
                ax1.axvline(x=t, color='red', linestyle='-', alpha=0.5, linewidth=2)

        ax1.set_title('M Value and Target Bitrate Over Time', fontsize=14, fontweight='bold')
        ax1.set_xlabel('Time (seconds)', fontsize=12)
        ax1.grid(True, alpha=0.3)
        ax1.legend(loc='upper left')
        ax1_twin.legend(loc='upper right')

        # Plot 2: Scatter plot - M value vs Target Bitrate
        ax2 = axes[1]
        if not aligned_df.empty:
            scatter = ax2.scatter(aligned_df['m_value'], aligned_df['target_bitrate'],
                                 c=aligned_df['timestamp'], cmap='viridis', alpha=0.6, s=20)

            # Add trend line
            z = np.polyfit(aligned_df['m_value'], aligned_df['target_bitrate'], 1)
            p = np.poly1d(z)
            m_range = np.linspace(aligned_df['m_value'].min(), aligned_df['m_value'].max(), 100)
            ax2.plot(m_range, p(m_range), "r--", linewidth=2, alpha=0.8, label=f'Trend: y={z[0]:.1f}x+{z[1]:.1f}')

            plt.colorbar(scatter, ax=ax2, label='Time (seconds)')
            ax2.set_xlabel('M Value', fontsize=12)
            ax2.set_ylabel('Target Bitrate (kbps)', fontsize=12)
            ax2.set_title('Correlation: M Value vs Target Bitrate', fontsize=14, fontweight='bold')
            ax2.grid(True, alpha=0.3)
            ax2.legend()

        # Plot 3: M value and bitrate change analysis
        ax3 = axes[2]
        if not aligned_df.empty and 'bitrate_change' in aligned_df.columns:
            ax3_twin = ax3.twinx()

            # Plot M value changes
            ax3.plot(aligned_df['timestamp'][1:], aligned_df['m_change'][1:],
                    color='#FF6B35', linewidth=1.5, alpha=0.7, label='M Value Change')
            ax3.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
            ax3.set_ylabel('M Value Change', fontsize=12, color='#FF6B35')
            ax3.tick_params(axis='y', labelcolor='#FF6B35')

            # Plot bitrate changes
            ax3_twin.plot(aligned_df['timestamp'][1:], aligned_df['bitrate_change'][1:],
                         color='#C73E1D', linewidth=1.5, alpha=0.7, label='Bitrate Change')
            ax3_twin.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
            ax3_twin.set_ylabel('Bitrate Change (kbps)', fontsize=12, color='#C73E1D')
            ax3_twin.tick_params(axis='y', labelcolor='#C73E1D')

            ax3.set_xlabel('Time (seconds)', fontsize=12)
            ax3.set_title('M Value Change vs Bitrate Change', fontsize=14, fontweight='bold')
            ax3.grid(True, alpha=0.3)
            ax3.legend(loc='upper left')
            ax3_twin.legend(loc='upper right')

        plt.tight_layout()

        # Save the plot
        output_file = self.log_file_path.replace('.log', '_m_value_bitrate_analysis.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"\n[*] Analysis plot saved to: {output_file}")

        return output_file

def main():
    parser = argparse.ArgumentParser(description='M Value and Target Bitrate Correlation Analyzer')
    parser.add_argument('log_file', nargs='?',
                       default="/home/wuq/webrtc-local/webrtc_config_results/sat3sender_local.log",
                       help='Path to the log file to analyze')

    args = parser.parse_args()

    # Check if log file exists
    if not os.path.exists(args.log_file):
        print(f"[!] Error: Log file '{args.log_file}' not found")
        sys.exit(1)

    print("M Value and Target Bitrate Correlation Analyzer")
    print("="*60)
    print(f"Log file: {args.log_file}")
    print()

    analyzer = MValueBitrateAnalyzer(args.log_file)

    # Parse logs
    print("[*] Parsing log file...")
    m_value_df, bwe_df, overusing_events = analyzer.parse_logs()

    if m_value_df.empty or bwe_df.empty:
        print("[!] Insufficient data for analysis")
        return

    # Align data
    print("\n[*] Aligning M value and bitrate data...")
    aligned_df = analyzer.align_data(m_value_df, bwe_df)

    # Analyze correlation
    if not aligned_df.empty:
        analyzer.analyze_correlation(aligned_df)

    # Generate plot
    print("\n[*] Generating analysis plots...")
    output_file = analyzer.plot_analysis(m_value_df, bwe_df, aligned_df, overusing_events)

    print(f"\n[*] Analysis complete. Plot saved to: {output_file}")

if __name__ == "__main__":
    main()

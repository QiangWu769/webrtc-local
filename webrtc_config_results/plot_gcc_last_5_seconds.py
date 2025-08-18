#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plot last 5 seconds of GCC data with millisecond-level precision
to verify timestamp alignment between GCC and diag data
"""

import re
import os
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# Import the main analyzer class
from plot_gcc_decision_analysis_vertical import GccDecisionAnalyzer

def plot_last_5_seconds(data_dict, last_n_seconds=5):
    """
    Plot only the last N seconds of data with high precision to verify alignment
    """
    trendline_df = data_dict['trendline']
    rtt_df = data_dict['rtt'] 
    loss_df = data_dict['loss']
    probe_df = data_dict['probe']
    decision_df = data_dict['decision']
    bwe_decision_df = data_dict.get('bwe_decision', pd.DataFrame())
    
    # Set matplotlib style
    try:
        plt.style.use('seaborn-v0_8-whitegrid')
    except:
        plt.style.use('default')
    
    # Create figure with 9 subplots
    fig, axes = plt.subplots(9, 1, figsize=(20, 40), sharex=True)
    fig.suptitle(f'WebRTC GCC Last {last_n_seconds} Seconds - Millisecond Precision Alignment Check', 
                 fontsize=18, fontweight='bold')
    plt.subplots_adjust(hspace=0.35)
    
    # Determine overall time range from all data
    all_timestamps = []
    for df in [trendline_df, rtt_df, loss_df, bwe_decision_df, decision_df]:
        if not df.empty and 'timestamp' in df.columns:
            all_timestamps.extend(df['timestamp'].tolist())
    
    if not all_timestamps:
        print("[!] No timestamp data available")
        return None
    
    # Calculate time window for last N seconds
    max_time_ms = max(all_timestamps)
    min_time_ms = max_time_ms - (last_n_seconds * 1000)  # N seconds in milliseconds
    
    print(f"\n[*] Focusing on last {last_n_seconds} seconds of data:")
    print(f"    Time window: {min_time_ms/1000:.3f}s - {max_time_ms/1000:.3f}s (epoch)")
    print(f"    Window start: {min_time_ms} ms")
    print(f"    Window end: {max_time_ms} ms")
    
    # Filter all dataframes to last N seconds
    if not trendline_df.empty:
        trendline_df = trendline_df[trendline_df['timestamp'] >= min_time_ms].copy()
    if not rtt_df.empty:
        rtt_df = rtt_df[rtt_df['timestamp'] >= min_time_ms].copy()
    if not loss_df.empty:
        loss_df = loss_df[loss_df['timestamp'] >= min_time_ms].copy()
    if not bwe_decision_df.empty:
        bwe_decision_df = bwe_decision_df[bwe_decision_df['timestamp'] >= min_time_ms].copy()
    if not decision_df.empty:
        decision_df = decision_df[decision_df['timestamp'] >= min_time_ms].copy()
    if not probe_df.empty:
        probe_df = probe_df[probe_df['timestamp'] >= min_time_ms].copy()
    
    print(f"\n[*] Data points in last {last_n_seconds} seconds:")
    print(f"    Trendline: {len(trendline_df)} points")
    print(f"    RTT: {len(rtt_df)} points")
    print(f"    Loss: {len(loss_df)} points")
    print(f"    BWE Decision: {len(bwe_decision_df)} points")
    print(f"    GCC Decision: {len(decision_df)} points")
    print(f"    Probe: {len(probe_df)} points")
    
    # Load and filter diag data
    diag_path = '/home/wuq/webrtc-checkout/logcode/diag_report.txt'
    print(f"\n[*] Loading diag data from: {diag_path}")
    
    try:
        diag_df = pd.read_csv(diag_path, sep='\t', engine='python')
        
        # Convert timestamp to milliseconds
        diag_df['timestamp_ms'] = (pd.to_numeric(diag_df['Python_Recv_Timestamp'], errors='coerce') * 1000).astype('int64')
        
        # Filter to last N seconds window
        diag_filtered = diag_df[(diag_df['timestamp_ms'] >= min_time_ms) & 
                                (diag_df['timestamp_ms'] <= max_time_ms)].copy()
        
        print(f"[*] Diag data points in window: {len(diag_filtered)}")
        
        if not diag_filtered.empty:
            # Parse numeric columns
            lcg3_numeric = pd.to_numeric(diag_filtered.get('LCG_3', pd.Series(dtype=float)), errors='coerce')
            numrbs_numeric = pd.to_numeric(diag_filtered.get('Num_RBs', pd.Series(dtype=float)), errors='coerce')
            tbs_str = diag_filtered.get('TBS_Index', pd.Series(dtype=str)).astype(str)
            tbs_numeric = pd.to_numeric(tbs_str.str.extract(r'(\d+)')[0], errors='coerce')
            
            # Group by timestamp and calculate averages
            work = pd.DataFrame({
                'timestamp_ms': diag_filtered['timestamp_ms'],
                'lcg3': lcg3_numeric,
                'num_rbs': numrbs_numeric,
                'tbs': tbs_numeric,
            })
            
            grouped = work.groupby('timestamp_ms')
            lcg3_avg = grouped['lcg3'].apply(lambda x: x[x > 0].mean() if (x > 0).any() else 0)
            num_rbs_avg = grouped['num_rbs'].apply(lambda x: x[x > 0].mean() if (x > 0).any() else 0)
            tbs_avg = grouped['tbs'].apply(lambda x: x[x > 0].mean() if (x > 0).any() else 0)
            
            diag_result = pd.DataFrame({
                'timestamp_ms': lcg3_avg.index,
                'lcg3_avg': lcg3_avg.values,
                'num_rbs_avg': num_rbs_avg.values,
                'tbs_avg': tbs_avg.values,
            })
            
            # Convert to relative time (seconds from start of window)
            diag_result['time_s'] = (diag_result['timestamp_ms'] - min_time_ms) / 1000.0
            
            print(f"[*] Diag unique timestamps in window: {len(diag_result)}")
            print(f"[*] Diag time range in window: {diag_result['timestamp_ms'].min()} - {diag_result['timestamp_ms'].max()} ms")
            
            # Print first few timestamps for verification
            print(f"\n[*] First 5 diag timestamps (ms) and relative time (s):")
            for i, row in diag_result.head().iterrows():
                print(f"    {row['timestamp_ms']:.0f} ms -> {row['time_s']:.3f} s")
        else:
            diag_result = pd.DataFrame()
            print("[!] No diag data in the last 5 seconds window")
    except Exception as e:
        print(f"[!] Error loading diag data: {e}")
        diag_result = pd.DataFrame()
    
    # Convert all GCC dataframes to relative time
    base_time = min_time_ms
    
    # 1. Trendline subplot with millisecond markers
    if not trendline_df.empty:
        trendline_df['time_s'] = (trendline_df['timestamp'] - base_time) / 1000.0
        
        # Plot with markers for each point
        axes[0].plot(trendline_df['time_s'], trendline_df['modified_trend'], 'o-', 
                    color='steelblue', label='Modified Trend', markersize=4, linewidth=1, alpha=0.8)
        axes[0].plot(trendline_df['time_s'], trendline_df['threshold'], '--', 
                    color='lightcoral', label='Threshold', linewidth=1.5)
        
        # Add vertical lines every 100ms for reference
        for i in range(0, int(last_n_seconds * 10) + 1):
            axes[0].axvline(x=i/10.0, color='gray', linestyle=':', alpha=0.2, linewidth=0.5)
        
        axes[0].set_ylabel('Trend/Threshold', fontsize=11)
        axes[0].set_title('1. Trendline (Delay BWE) - Millisecond Precision', fontsize=12, fontweight='bold')
        axes[0].grid(True, alpha=0.3, which='both')
        axes[0].legend(fontsize=9)
        
        # Print sample timestamps
        print(f"\n[*] First 5 GCC trendline timestamps (ms) and relative time (s):")
        for i, row in trendline_df.head().iterrows():
            print(f"    {row['timestamp']:.0f} ms -> {row['time_s']:.3f} s")
    
    # 2. BWE Decision subplot
    if not bwe_decision_df.empty:
        bwe_decision_df['time_s'] = (bwe_decision_df['timestamp'] - base_time) / 1000.0
        
        axes[1].plot(bwe_decision_df['time_s'], bwe_decision_df['new_target']/1000, 
                    'o-', color='mediumslateblue', label='Target Bitrate (kbps)', 
                    markersize=3, linewidth=1.5, alpha=0.8)
        axes[1].plot(bwe_decision_df['time_s'], bwe_decision_df['acked_bitrate']/1000, 
                    's--', color='sandybrown', label='Acked Bitrate (kbps)', 
                    markersize=2, linewidth=1, alpha=0.7)
        
        # Add 100ms grid lines
        for i in range(0, int(last_n_seconds * 10) + 1):
            axes[1].axvline(x=i/10.0, color='gray', linestyle=':', alpha=0.2, linewidth=0.5)
        
        axes[1].set_ylabel('Bitrate (kbps)', fontsize=11)
        axes[1].set_title('2. BWE Decision - Target vs Acked Bitrate', fontsize=12, fontweight='bold')
        axes[1].grid(True, alpha=0.3, which='both')
        axes[1].legend(fontsize=9)
    
    # 3. RTT BWE subplot
    if not rtt_df.empty:
        rtt_df['time_s'] = (rtt_df['timestamp'] - base_time) / 1000.0
        
        axes[2].plot(rtt_df['time_s'], rtt_df['corrected_rtt'], 'o-', 
                    color='mediumseagreen', label='Corrected RTT (ms)', 
                    markersize=4, linewidth=1.5)
        
        # Add 100ms grid lines
        for i in range(0, int(last_n_seconds * 10) + 1):
            axes[2].axvline(x=i/10.0, color='gray', linestyle=':', alpha=0.2, linewidth=0.5)
        
        axes[2].set_ylabel('RTT (ms)', fontsize=11)
        axes[2].set_title('3. RTT BWE - Corrected RTT', fontsize=12, fontweight='bold')
        axes[2].grid(True, alpha=0.3, which='both')
        axes[2].legend(fontsize=9)
    
    # 4. Loss BWE subplot
    if not loss_df.empty:
        loss_df['time_s'] = (loss_df['timestamp'] - base_time) / 1000.0
        
        axes[3].plot(loss_df['time_s'], loss_df['bandwidth']/1000, 
                    'o-', color='mediumpurple', label='Loss BWE (kbps)', 
                    markersize=2, linewidth=1, alpha=0.8)
        
        # Add 100ms grid lines
        for i in range(0, int(last_n_seconds * 10) + 1):
            axes[3].axvline(x=i/10.0, color='gray', linestyle=':', alpha=0.2, linewidth=0.5)
        
        axes[3].set_ylabel('Bandwidth (kbps)', fontsize=11)
        axes[3].set_title('4. Loss BWE - Bandwidth Estimate', fontsize=12, fontweight='bold')
        axes[3].grid(True, alpha=0.3, which='both')
        axes[3].legend(fontsize=9)
    
    # 5. Probe BWE subplot
    if not probe_df.empty:
        probe_df['time_s'] = (probe_df['timestamp'] - base_time) / 1000.0
        
        axes[4].scatter(probe_df['time_s'], probe_df['estimate']/1000, 
                       c=probe_df['cluster_id'], cmap='viridis', 
                       s=100, alpha=0.8, edgecolors='black', linewidth=1)
        
        # Add 100ms grid lines
        for i in range(0, int(last_n_seconds * 10) + 1):
            axes[4].axvline(x=i/10.0, color='gray', linestyle=':', alpha=0.2, linewidth=0.5)
        
        axes[4].set_ylabel('Bandwidth (kbps)', fontsize=11)
        axes[4].set_title('5. Probe BWE - Bandwidth Probes', fontsize=12, fontweight='bold')
        axes[4].grid(True, alpha=0.3, which='both')
    else:
        axes[4].text(0.5, 0.5, 'No Probe Data in Last 5 Seconds', 
                    transform=axes[4].transAxes, ha='center', va='center',
                    fontsize=14, alpha=0.5)
        axes[4].set_title('5. Probe BWE - No Data', fontsize=12, fontweight='bold')
    
    # 6. Final GCC Decision subplot
    if not decision_df.empty:
        decision_df['time_s'] = (decision_df['timestamp'] - base_time) / 1000.0
        
        # Map decision reasons to numeric values
        reason_map = {'Hold': 0, 'LossEstimate': 1, 'ProbeResult': 2, 'RttBackoff': 3, 'DelayLimit': 4}
        decision_df['decision_numeric'] = decision_df['decision_reason'].map(reason_map).fillna(0)
        
        axes[5].step(decision_df['time_s'], decision_df['decision_numeric'], where='post',
                    color='mediumslateblue', linewidth=2, label='Decision Type')
        
        # Add 100ms grid lines
        for i in range(0, int(last_n_seconds * 10) + 1):
            axes[5].axvline(x=i/10.0, color='gray', linestyle=':', alpha=0.2, linewidth=0.5)
        
        axes[5].set_ylabel('Decision Type', fontsize=11)
        axes[5].set_yticks([0, 1, 2, 3, 4])
        axes[5].set_yticklabels(['Hold', 'Loss', 'Probe', 'RTT', 'Delay'])
        axes[5].set_title('6. Final GCC Decision Reason', fontsize=12, fontweight='bold')
        axes[5].grid(True, alpha=0.3, which='both')
        axes[5].legend(fontsize=9)
    
    # 7-9. Diag data subplots with millisecond precision
    if not diag_result.empty:
        # 7. LCG_3 subplot
        axes[6].plot(diag_result['time_s'], diag_result['lcg3_avg'], 'o-', 
                    color='tab:blue', label='LCG_3 Avg', markersize=3, linewidth=1, alpha=0.8)
        
        # Add 100ms grid lines
        for i in range(0, int(last_n_seconds * 10) + 1):
            axes[6].axvline(x=i/10.0, color='gray', linestyle=':', alpha=0.2, linewidth=0.5)
        
        axes[6].set_ylabel('LCG_3', fontsize=11)
        axes[6].set_title('7. Diag: LCG_3 Average (Millisecond Aligned)', fontsize=12, fontweight='bold')
        axes[6].grid(True, alpha=0.3, which='both')
        axes[6].legend(fontsize=9)
        
        # 8. TBS Index subplot
        axes[7].plot(diag_result['time_s'], diag_result['tbs_avg'], 'o-', 
                    color='tab:red', label='TBS Index Avg', markersize=3, linewidth=1, alpha=0.8)
        
        # Add 100ms grid lines
        for i in range(0, int(last_n_seconds * 10) + 1):
            axes[7].axvline(x=i/10.0, color='gray', linestyle=':', alpha=0.2, linewidth=0.5)
        
        axes[7].set_ylabel('TBS Index', fontsize=11)
        axes[7].set_title('8. Diag: TBS Index Average (Millisecond Aligned)', fontsize=12, fontweight='bold')
        axes[7].grid(True, alpha=0.3, which='both')
        axes[7].legend(fontsize=9)
        
        # 9. Num_RBs subplot
        axes[8].plot(diag_result['time_s'], diag_result['num_rbs_avg'], 'o-', 
                    color='tab:green', label='Num_RBs Avg', markersize=3, linewidth=1, alpha=0.8)
        
        # Add 100ms grid lines
        for i in range(0, int(last_n_seconds * 10) + 1):
            axes[8].axvline(x=i/10.0, color='gray', linestyle=':', alpha=0.2, linewidth=0.5)
        
        axes[8].set_ylabel('Num RBs', fontsize=11)
        axes[8].set_title('9. Diag: Num_RBs Average (Millisecond Aligned)', fontsize=12, fontweight='bold')
        axes[8].grid(True, alpha=0.3, which='both')
        axes[8].legend(fontsize=9)
    else:
        for i in range(6, 9):
            axes[i].text(0.5, 0.5, 'No Diag Data in Last 5 Seconds', 
                        transform=axes[i].transAxes, ha='center', va='center',
                        fontsize=14, alpha=0.5)
            axes[i].set_title(f'{i+1}. Diag: No Data', fontsize=12, fontweight='bold')
    
    # Set common x-axis properties
    axes[-1].set_xlabel('Time (seconds from start of window)', fontsize=12)
    for ax in axes:
        ax.set_xlim(0, last_n_seconds)
        # Add minor ticks every 50ms
        ax.xaxis.set_minor_locator(plt.MultipleLocator(0.05))
        ax.grid(True, which='minor', alpha=0.1, linestyle=':')
    
    # Add timestamp alignment info
    info_text = (f"Window: Last {last_n_seconds} seconds | "
                f"Epoch time: {min_time_ms/1000:.3f}s - {max_time_ms/1000:.3f}s | "
                f"GCC points: {len(trendline_df)} trendline, {len(bwe_decision_df)} BWE | "
                f"Diag points: {len(diag_result) if not diag_result.empty else 0}")
    
    fig.text(0.5, 0.995, info_text, ha='center', va='top', fontsize=10,
             bbox=dict(boxstyle='round,pad=0.3', facecolor='lightgreen', alpha=0.8))
    
    plt.tight_layout(rect=[0, 0, 1, 0.99])
    return fig

def main():
    # Parse GCC log file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sender_log_file = os.path.join(script_dir, 'sender_local.log')
    
    print(f"[*] Analyzing GCC log: {sender_log_file}")
    
    try:
        analyzer = GccDecisionAnalyzer(sender_log_file)
        data_dict = analyzer.parse_log_file()
        
        # Plot last 5 seconds with millisecond precision
        fig = plot_last_5_seconds(data_dict, last_n_seconds=5)
        
        if fig:
            output_dir = os.path.join(script_dir, 'analysis_results')
            os.makedirs(output_dir, exist_ok=True)
            
            output_path = os.path.join(output_dir, 'gcc_last_5_seconds_millisecond.png')
            fig.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
            print(f"\n[*] Chart saved to: {output_path}")
            plt.show()
        else:
            print("[!] Failed to generate chart")
            
    except Exception as e:
        import traceback
        print(f"[!] Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
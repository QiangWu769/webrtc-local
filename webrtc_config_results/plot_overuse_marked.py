#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plot last 5 seconds with precise overuse event markers and timestamp details
"""

import re
import os
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# Import the main analyzer class
from plot_gcc_decision_analysis_vertical import GccDecisionAnalyzer

def plot_overuse_marked(data_dict, last_n_seconds=5):
    """
    Plot last N seconds with overuse events precisely marked
    """
    # Key overuse timestamps (from analysis above)
    overuse_start = 1755003725.369000  # Trendline detects overuse
    overuse_end = 1755003726.991000    # Recovery completed
    
    print(f"\n🚨 OVERUSE EVENT ANALYSIS 🚨")
    print(f"Overuse Start: {overuse_start:.6f}s ({int(overuse_start*1000)}ms)")
    print(f"Recovery End:  {overuse_end:.6f}s ({int(overuse_end*1000)}ms)")
    print(f"Duration: {(overuse_end-overuse_start)*1000:.1f}ms")
    
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
    fig, axes = plt.subplots(9, 1, figsize=(22, 42), sharex=True)
    fig.suptitle(f'WebRTC GCC Last {last_n_seconds}s - OVERUSE Event Marked with Precise Timestamps', 
                 fontsize=20, fontweight='bold')
    plt.subplots_adjust(hspace=0.4)
    
    # Determine time window for last N seconds
    all_timestamps = []
    for df in [trendline_df, rtt_df, loss_df, bwe_decision_df, decision_df]:
        if not df.empty and 'timestamp' in df.columns:
            all_timestamps.extend(df['timestamp'].tolist())
    
    max_time_ms = max(all_timestamps)
    min_time_ms = max_time_ms - (last_n_seconds * 1000)
    base_time = min_time_ms
    
    # Convert overuse times to relative seconds
    overuse_start_rel = (overuse_start * 1000 - base_time) / 1000.0
    overuse_end_rel = (overuse_end * 1000 - base_time) / 1000.0
    
    print(f"\\nRelative times in plot:")
    print(f"Overuse Start: {overuse_start_rel:.3f}s")
    print(f"Recovery End:  {overuse_end_rel:.3f}s")
    
    # Filter data to last N seconds
    if not trendline_df.empty:
        trendline_df = trendline_df[trendline_df['timestamp'] >= min_time_ms].copy()
        trendline_df['time_s'] = (trendline_df['timestamp'] - base_time) / 1000.0
    
    if not bwe_decision_df.empty:
        bwe_decision_df = bwe_decision_df[bwe_decision_df['timestamp'] >= min_time_ms].copy()
        bwe_decision_df['time_s'] = (bwe_decision_df['timestamp'] - base_time) / 1000.0
    
    if not decision_df.empty:
        decision_df = decision_df[decision_df['timestamp'] >= min_time_ms].copy()
        decision_df['time_s'] = (decision_df['timestamp'] - base_time) / 1000.0
    
    if not loss_df.empty:
        loss_df = loss_df[loss_df['timestamp'] >= min_time_ms].copy()
        loss_df['time_s'] = (loss_df['timestamp'] - base_time) / 1000.0
    
    # Load and filter diag data
    diag_path = '/home/wuq/webrtc-checkout/logcode/diag_report.txt'
    diag_result = pd.DataFrame()
    
    try:
        diag_df = pd.read_csv(diag_path, sep='\t', engine='python')
        diag_df['timestamp_ms'] = (pd.to_numeric(diag_df['Python_Recv_Timestamp'], errors='coerce') * 1000).astype('int64')
        diag_filtered = diag_df[(diag_df['timestamp_ms'] >= min_time_ms) & 
                                (diag_df['timestamp_ms'] <= max_time_ms)].copy()
        
        if not diag_filtered.empty:
            # Check if we have SysFN and SubFN columns for cellular timing
            has_cellular_timing = 'SysFN' in diag_filtered.columns and 'SubFN' in diag_filtered.columns
            
            if has_cellular_timing:
                print("[*] Found SysFN and SubFN columns - enabling cellular network time precision")
                # Calculate cellular time in milliseconds (SysFN * 10ms + SubFN * 1ms)
                diag_filtered['cellular_time_ms'] = (
                    pd.to_numeric(diag_filtered['SysFN'], errors='coerce') * 10 + 
                    pd.to_numeric(diag_filtered['SubFN'], errors='coerce') * 1
                )
                
                # Sort by timestamp first, then by cellular time within same timestamp
                diag_filtered['Python_Recv_Timestamp_sec'] = pd.to_numeric(diag_filtered['Python_Recv_Timestamp'], errors='coerce')
                
                # Group by Unix timestamp and sort by cellular time within each group
                refined_data = []
                grouped_by_ts = diag_filtered.groupby('Python_Recv_Timestamp_sec')
                
                for timestamp_sec, group in grouped_by_ts:
                    # Sort by cellular time within same Unix timestamp
                    group_sorted = group.sort_values('cellular_time_ms').copy()
                    
                    # Add precise timestamp with cellular offset
                    for i, (_, row) in enumerate(group_sorted.iterrows()):
                        row_dict = row.to_dict()
                        # Add cellular offset to get precise timestamp
                        cellular_offset_s = (row['cellular_time_ms'] % 10240) / 1000.0  # 10.24s period
                        row_dict['precise_timestamp'] = timestamp_sec + cellular_offset_s
                        row_dict['precise_timestamp_ms'] = int((timestamp_sec + cellular_offset_s) * 1000)
                        row_dict['event_order_in_timestamp'] = i
                        refined_data.append(row_dict)
                
                diag_filtered = pd.DataFrame(refined_data)
                
                # Keep original timestamp_ms for window filtering, but store precise timestamp for sorting
                # Don't update timestamp_ms here - we'll use precise_timestamp_ms only for sorting within groups
                
                # Statistics
                print(f"[*] Cellular timing analysis:")
                print(f"    Events with same Unix timestamp: {len(diag_filtered) - len(grouped_by_ts)}")
                print(f"    Max events per timestamp: {grouped_by_ts.size().max()}")
                print(f"    SysFN range: {diag_filtered['SysFN'].min()}-{diag_filtered['SysFN'].max()}")
                print(f"    SubFN range: {diag_filtered['SubFN'].min()}-{diag_filtered['SubFN'].max()}")
            else:
                print("[!] Warning: No SysFN/SubFN columns found - using standard timestamps")
                diag_filtered['cellular_time_ms'] = 0
                diag_filtered['precise_timestamp_ms'] = diag_filtered['timestamp_ms']
            
            # Parse and group diag data
            lcg3_numeric = pd.to_numeric(diag_filtered.get('LCG_3', pd.Series(dtype=float)), errors='coerce')
            numrbs_numeric = pd.to_numeric(diag_filtered.get('Num_RBs', pd.Series(dtype=float)), errors='coerce')
            tbs_str = diag_filtered.get('TBS_Index', pd.Series(dtype=str)).astype(str)
            tbs_numeric = pd.to_numeric(tbs_str.str.extract(r'(\d+)')[0], errors='coerce')
            sysfn_numeric = pd.to_numeric(diag_filtered.get('SysFN', pd.Series(dtype=float)), errors='coerce')
            subfn_numeric = pd.to_numeric(diag_filtered.get('SubFN', pd.Series(dtype=float)), errors='coerce')
            
            work = pd.DataFrame({
                'timestamp_ms': diag_filtered['timestamp_ms'],
                'precise_timestamp_ms': diag_filtered.get('precise_timestamp_ms', diag_filtered['timestamp_ms']),
                'cellular_time_ms': diag_filtered.get('cellular_time_ms', 0),
                'lcg3': lcg3_numeric,
                'num_rbs': numrbs_numeric,
                'tbs': tbs_numeric,
                'sysfn': sysfn_numeric,
                'subfn': subfn_numeric,
            })
            
            # Group by original timestamp_ms for aggregation (don't use precise timestamp for grouping)
            grouped = work.groupby('timestamp_ms')
            lcg3_avg = grouped['lcg3'].apply(lambda x: x[x > 0].mean() if (x > 0).any() else 0)
            num_rbs_avg = grouped['num_rbs'].apply(lambda x: x[x > 0].mean() if (x > 0).any() else 0)
            tbs_avg = grouped['tbs'].apply(lambda x: x[x > 0].mean() if (x > 0).any() else 0)
            sysfn_avg = grouped['sysfn'].mean() if has_cellular_timing else pd.Series(dtype=float)
            subfn_avg = grouped['subfn'].mean() if has_cellular_timing else pd.Series(dtype=float)
            cellular_time_avg = grouped['cellular_time_ms'].mean() if has_cellular_timing else pd.Series(dtype=float)
            
            diag_result = pd.DataFrame({
                'timestamp_ms': lcg3_avg.index,
                'lcg3_avg': lcg3_avg.values,
                'num_rbs_avg': num_rbs_avg.values,
                'tbs_avg': tbs_avg.values,
                'sysfn_avg': sysfn_avg.values if has_cellular_timing else [0] * len(lcg3_avg),
                'subfn_avg': subfn_avg.values if has_cellular_timing else [0] * len(lcg3_avg),
                'cellular_time_ms': cellular_time_avg.values if has_cellular_timing else [0] * len(lcg3_avg),
            })
            # Use the same base_time as other data for consistency
            diag_result['time_s'] = (diag_result['timestamp_ms'] - base_time) / 1000.0
            
            if has_cellular_timing:
                print(f"[*] Processed {len(diag_result)} precise data points with cellular timing")
                # Show how many are in the display window
                diag_in_window = diag_result[(diag_result['time_s'] >= 0) & (diag_result['time_s'] <= last_n_seconds)]
                print(f"    {len(diag_in_window)} points in display window (0-{last_n_seconds}s)")
            
    except Exception as e:
        print(f"[!] Error loading diag data: {e}")
        import traceback
        traceback.print_exc()
    
    # Helper function to add overuse markers
    def add_overuse_markers(ax, subplot_name):
        # Overuse start marker (red)
        ax.axvline(x=overuse_start_rel, color='red', linestyle='-', linewidth=3, alpha=0.8, 
                  label=f'Overuse Start ({overuse_start_rel:.3f}s)', zorder=10)
        
        # Recovery end marker (green)
        ax.axvline(x=overuse_end_rel, color='green', linestyle='-', linewidth=3, alpha=0.8,
                  label=f'Recovery End ({overuse_end_rel:.3f}s)', zorder=10)
        
        # Overuse period shading
        ax.axvspan(overuse_start_rel, overuse_end_rel, alpha=0.15, color='orange', 
                  label=f'Overuse Period ({(overuse_end_rel-overuse_start_rel)*1000:.1f}ms)', zorder=1)
        
        # Add timestamp annotations
        y_pos = ax.get_ylim()[1] * 0.9
        ax.annotate(f'OVERUSE\\n{int(overuse_start*1000)}ms', 
                   xy=(overuse_start_rel, y_pos), xytext=(overuse_start_rel+0.2, y_pos),
                   arrowprops=dict(arrowstyle='->', color='red', lw=2),
                   fontsize=9, color='red', fontweight='bold',
                   bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.8))
        
        ax.annotate(f'RECOVERY\\n{int(overuse_end*1000)}ms', 
                   xy=(overuse_end_rel, y_pos*0.8), xytext=(overuse_end_rel-0.3, y_pos*0.8),
                   arrowprops=dict(arrowstyle='->', color='green', lw=2),
                   fontsize=9, color='green', fontweight='bold',
                   bbox=dict(boxstyle='round,pad=0.3', facecolor='lightgreen', alpha=0.8))
    
    # 1. Trendline subplot (GCC source)
    if not trendline_df.empty:
        axes[0].plot(trendline_df['time_s'], trendline_df['modified_trend'], 'o-', 
                    color='steelblue', label='Modified Trend', markersize=4, linewidth=1.5, alpha=0.8)
        axes[0].plot(trendline_df['time_s'], trendline_df['threshold'], '--', 
                    color='lightcoral', label='Threshold', linewidth=2)
        
        # Mark state changes
        for state, color, marker in [('Overusing', 'red', '^'), ('Normal', 'blue', 'o'), ('Underusing', 'green', 'v')]:
            state_data = trendline_df[trendline_df['state'] == state]
            if not state_data.empty:
                axes[0].scatter(state_data['time_s'], state_data['modified_trend'], 
                              c=color, marker=marker, s=60, alpha=0.8, label=f'{state} State', 
                              edgecolor='white', linewidth=1, zorder=5)
        
        add_overuse_markers(axes[0], "Trendline")
        axes[0].set_ylabel('Trend/Threshold', fontsize=11)
        axes[0].set_title('1. Trendline (Delay BWE) - SOURCE: sender_local.log', fontsize=12, fontweight='bold')
        axes[0].grid(True, alpha=0.3)
        axes[0].legend(fontsize=8, loc='upper right')
        
        # Print precise timestamps around overuse
        print(f"\\n📊 TRENDLINE DATA (sender_local.log):")
        around_overuse = trendline_df[
            (trendline_df['time_s'] >= overuse_start_rel - 0.1) & 
            (trendline_df['time_s'] <= overuse_start_rel + 0.1)
        ]
        for _, row in around_overuse.iterrows():
            abs_time_ms = base_time + row['time_s'] * 1000
            print(f"  {abs_time_ms:.0f}ms -> rel:{row['time_s']:.3f}s, trend:{row['modified_trend']:.3f}, state:{row['state']}")
    
    # 2. BWE Decision (GCC source)
    if not bwe_decision_df.empty:
        axes[1].plot(bwe_decision_df['time_s'], bwe_decision_df['new_target']/1000, 
                    'o-', color='mediumslateblue', label='Target Bitrate (kbps)', 
                    markersize=3, linewidth=1.5, alpha=0.8)
        
        add_overuse_markers(axes[1], "BWE Decision")
        axes[1].set_ylabel('Bitrate (kbps)', fontsize=11)
        axes[1].set_title('2. BWE Decision - SOURCE: sender_local.log', fontsize=12, fontweight='bold')
        axes[1].grid(True, alpha=0.3)
        axes[1].legend(fontsize=8)
        
        # Print BWE decision data around overuse
        print(f"\\n📊 BWE DECISION DATA (sender_local.log):")
        around_overuse = bwe_decision_df[
            (bwe_decision_df['time_s'] >= overuse_start_rel - 0.1) & 
            (bwe_decision_df['time_s'] <= overuse_start_rel + 0.1)
        ]
        for _, row in around_overuse.iterrows():
            abs_time_ms = base_time + row['time_s'] * 1000
            print(f"  {abs_time_ms:.0f}ms -> rel:{row['time_s']:.3f}s, target:{row['new_target']/1000:.0f}kbps, strategy:{row['strategy']}")
    
    # 3-6. Other GCC subplots (simplified)
    for i, (df_name, df, ylabel, title) in enumerate([
        ('Loss BWE', loss_df, 'Bandwidth (kbps)', '3. Loss BWE - SOURCE: sender_local.log'),
        ('RTT BWE', pd.DataFrame(), 'RTT (ms)', '4. RTT BWE - SOURCE: sender_local.log'),
        ('Probe BWE', pd.DataFrame(), 'Bandwidth (kbps)', '5. Probe BWE - SOURCE: sender_local.log'),
        ('GCC Decision', decision_df, 'Decision Type', '6. Final GCC Decision - SOURCE: sender_local.log')
    ], start=2):
        
        if not df.empty:
            if df_name == 'Loss BWE':
                axes[i].plot(df['time_s'], df['bandwidth']/1000, 'o-', 
                           color='mediumpurple', markersize=2, linewidth=1, alpha=0.8)
            elif df_name == 'GCC Decision':
                reason_map = {'Hold': 0, 'LossEstimate': 1, 'ProbeResult': 2, 'RttBackoff': 3, 'DelayLimit': 4}
                df['decision_numeric'] = df['decision_reason'].map(reason_map).fillna(0)
                axes[i].step(df['time_s'], df['decision_numeric'], where='post',
                           color='mediumslateblue', linewidth=2)
                axes[i].set_yticks([0, 1, 2, 3, 4])
                axes[i].set_yticklabels(['Hold', 'Loss', 'Probe', 'RTT', 'Delay'])
        else:
            axes[i].text(0.5, 0.5, f'No {df_name} Data in Last {last_n_seconds}s', 
                        transform=axes[i].transAxes, ha='center', va='center',
                        fontsize=12, alpha=0.5)
        
        add_overuse_markers(axes[i], df_name)
        axes[i].set_ylabel(ylabel, fontsize=11)
        axes[i].set_title(title, fontsize=12, fontweight='bold')
        axes[i].grid(True, alpha=0.3)
        if not df.empty:
            axes[i].legend(fontsize=8)
    
    # 7-9. Diag data subplots
    diag_titles = [
        ('LCG_3', 'lcg3_avg', 'tab:blue', '7. Diag: LCG_3 Average - SOURCE: diag_report.txt'),
        ('TBS Index', 'tbs_avg', 'tab:red', '8. Diag: TBS Index Average - SOURCE: diag_report.txt'), 
        ('Num_RBs', 'num_rbs_avg', 'tab:green', '9. Diag: Num_RBs Average - SOURCE: diag_report.txt')
    ]
    
    # Filter diag data once for all subplots
    if not diag_result.empty:
        # Filter diag data to only show points within the plot window (0 to last_n_seconds)
        diag_in_window = diag_result[(diag_result['time_s'] >= 0) & (diag_result['time_s'] <= last_n_seconds)]
    else:
        diag_in_window = pd.DataFrame()  # Empty DataFrame if no diag_result
    
    for i, (label, column, color, title) in enumerate(diag_titles, start=6):
        if not diag_in_window.empty:
            axes[i].plot(diag_in_window['time_s'], diag_in_window[column], 'o-', 
                        color=color, label=f'{label} Avg', markersize=3, linewidth=1.5, alpha=0.8)
            
            add_overuse_markers(axes[i], f"Diag {label}")
            axes[i].legend(fontsize=8)
            
            if i == 6:  # Only print for first diag subplot to avoid clutter
                print(f"\\n📊 DIAG DATA (diag_report.txt):")
                around_overuse = diag_in_window[
                    (diag_in_window['time_s'] >= overuse_start_rel - 0.1) & 
                    (diag_in_window['time_s'] <= overuse_start_rel + 0.1)
                ]
                if not around_overuse.empty:
                    for _, row in around_overuse.iterrows():
                        cellular_info = ""
                        if 'sysfn_avg' in row and row['sysfn_avg'] > 0:
                            cellular_info = f", SysFN:{row['sysfn_avg']:.0f}, SubFN:{row['subfn_avg']:.0f}"
                        print(f"  {row['timestamp_ms']:.0f}ms -> rel:{row['time_s']:.3f}s, LCG3:{row['lcg3_avg']:.1f}, RBs:{row['num_rbs_avg']:.1f}, TBS:{row['tbs_avg']:.1f}{cellular_info}")
                else:
                    print(f"  No diag data around overuse time ({overuse_start_rel:.3f}s)")
        else:
            axes[i].text(0.5, 0.5, f'No Diag Data in Window (0-{last_n_seconds}s)', 
                        transform=axes[i].transAxes, ha='center', va='center',
                        fontsize=12, alpha=0.5)
            add_overuse_markers(axes[i], f"Diag {label}")
        
        axes[i].set_ylabel(label, fontsize=11)
        axes[i].set_title(title, fontsize=12, fontweight='bold')
        axes[i].grid(True, alpha=0.3)
    
    # Set common x-axis properties
    axes[-1].set_xlabel('Time (seconds from start of window)', fontsize=12, fontweight='bold')
    for ax in axes:
        ax.set_xlim(0, last_n_seconds)
        # Add major ticks every 500ms, minor every 100ms
        ax.xaxis.set_major_locator(plt.MultipleLocator(0.5))
        ax.xaxis.set_minor_locator(plt.MultipleLocator(0.1))
        ax.grid(True, which='major', alpha=0.3)
        ax.grid(True, which='minor', alpha=0.15, linestyle=':')
    
    # Add comprehensive info box
    info_text = (f"🚨 OVERUSE EVENT ANALYSIS - PRECISE TIMESTAMP ALIGNMENT 🚨\\n"
                f"Window: {min_time_ms/1000:.3f}s - {max_time_ms/1000:.3f}s (epoch) | "
                f"Overuse: {overuse_start:.6f}s → {overuse_end:.6f}s | Duration: {(overuse_end-overuse_start)*1000:.1f}ms\\n"
                f"📁 GCC Data (subplots 1-6): sender_local.log | 📁 Diag Data (subplots 7-9): diag_report.txt\\n"
                f"🔍 Red line = Overuse start | Green line = Recovery end | Orange area = Overuse duration")
    
    fig.text(0.5, 0.995, info_text, ha='center', va='top', fontsize=11,
             bbox=dict(boxstyle='round,pad=0.5', facecolor='lightyellow', alpha=0.9),
             fontweight='bold')
    
    plt.tight_layout(rect=[0, 0, 1, 0.985])
    return fig

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sender_log_file = os.path.join(script_dir, 'sender_local.log')
    
    print(f"[*] Analyzing GCC log with overuse marking: {sender_log_file}")
    
    try:
        analyzer = GccDecisionAnalyzer(sender_log_file)
        data_dict = analyzer.parse_log_file()
        
        fig = plot_overuse_marked(data_dict, last_n_seconds=5)
        
        if fig:
            output_dir = os.path.join(script_dir, 'analysis_results')
            os.makedirs(output_dir, exist_ok=True)
            
            output_path = os.path.join(output_dir, 'gcc_overuse_marked_precise.png')
            fig.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
            print(f"\\n[*] Overuse-marked chart saved to: {output_path}")
            plt.show()
            
    except Exception as e:
        import traceback
        print(f"[!] Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
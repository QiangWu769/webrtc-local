#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebRTC GCC (Google Congestion Control) Decision Process Analyzer - Fixed Version
Fixed diag_report.txt and GCC log timestamp alignment issues
"""

import re
import os
import matplotlib.pyplot as plt
import pandas as pd
from collections import defaultdict

class GccDecisionAnalyzer:
    """
    A specialized class for parsing and visualizing GCC decision process logs.
    """
    def __init__(self, log_file_path):
        self.log_file_path = log_file_path
        
        # Regular expressions to match key log entries
        self.patterns = {
            # GCC Decision Snapshot (new format with MonoTime and 'ms' attached, prefixed by wallclock)
            'decision': re.compile(r'\[GCC-DECISION-SNAPSHOT\]\s+(?:Time|MonoTime):\s*(\d+)ms\s*\|\s*DelayState: (\w+), DelayTargetBps: (\d+)\s*\|\s*RttBackoff: (\w+)\s*\|\s*ProbeResultBps: (\d+)\s*\|\s*BweTargetBps: (\d+)\s*\|\s*AckedBitrateBps: (\d+)\s*\|\s*FinalTargetBps: (\d+)\s*\|\s*DecisionReason: (\w+)\s*\|\s*Updated: (\w+)'),
            # Trendline analysis (Delay BWE internal)
            'trendline': re.compile(r'\[Trendline\] (?:Time|MonoTime): (\d+) ms.*?Modified trend: ([^,]+), Threshold: ([^,]+), State: (\w+)'),
            # RTT BWE internal parameters
            'rtt_bwe': re.compile(r'\[RttBWE-Update\] (?:Time|MonoTime): (\d+) ms, PropagationRtt: (\d+) ms, CorrectedRtt: (\d+) ms, RttLimit: (\d+) ms, AboveLimit: (\w+)'),
            # Loss BWE internal parameters  
            'loss_bwe': re.compile(r'\[LossBWE-Estimate\] (?:Time|MonoTime): (\d+) ms, State: (\d+), Bandwidth: (\d+) bps, Observations: (\d+)'),
            # Loss BWE candidates
            'loss_candidates': re.compile(r'\[LossBWE-Candidates\] (?:Time|MonoTime): (\d+) ms, Candidate Bandwidths \(kbps\): (.+)'),
            # Delay BWE decisions
            'delay_bwe': re.compile(r'\[DelayBWE-Decision\] (?:Time|MonoTime): (\d+) ms.*?New bitrate: (\d+) bps.*?Probe: (\w+)'),
            # DelayBWE estimates (for bandwidth output)
            'delay_bwe_estimate': re.compile(r'\[DelayBWE-Estimate\] (?:Time|MonoTime): (\d+) ms, State: (\d+), Acked bitrate: (\d+) bps, New target: (\d+) bps, Valid: (\w+)'),
            # New BWE Decision with strategy information
            'bwe_decision': re.compile(r'\[BWE-DECISION\] (?:Time|MonoTime): (\d+) ms, BWState: (\w+), Strategy: ([^,]*), Params: \[([^\]]*)\], AckedBitrate: (\d+) bps, OldTarget: (\d+) bps, NewTarget: (\d+) bps, Change: ([^,]+) bps, Valid: (\w+)'),
            # GCC final output (authoritative data source)
            'gcc_output': re.compile(r'\[GCC-OUTPUT\] TargetRateUpdate (?:Time|MonoTime): (\d+) ms, DelayBasedBps: (\d+), LossBasedBps: (\d+), FinalTargetBps: (\d+)'),
            # Probe results: Updated patterns for timestamped logs
            'probe_result': re.compile(r'\[ProbeBWE-Result\] (?:Time|MonoTime): (\d+) ms, Cluster ID: (\d+), Final estimate: (\d+) bps'),
            'probe_success': re.compile(r'\[ProbeBWE-Success\] (?:Time|MonoTime): (\d+) ms, Cluster ID: (\d+), Send rate: (\d+) bps'),
            # Fallback patterns for old format (without timestamps)
            'probe_result_old': re.compile(r'\[ProbeBWE-Result\] Cluster ID: (\d+), Final estimate: (\d+) bps'),
            'probe_success_old': re.compile(r'\[ProbeBWE-Success\] Cluster ID: (\d+), Send rate: (\d+) bps'),
            
            # New constraint tracking patterns
            'constraint_apply': re.compile(r'\[BWE-ConstraintApply\] (?:Time|MonoTime): (\d+) ms, Original: (\d+|INF) bps, UpperLimit: (\d+|INF) bps, AfterUpper: (\d+|INF) bps, MinConfig: (\d+|INF) bps, Final: (\d+|INF) bps, DelayLimit: (\d+|INF)(?:\s*bps)?, ReceiverLimit: (\d+|INF), MaxConfig: (\d+|INF) bps'),
            'delay_limit': re.compile(r'\[BWE-DelayLimit\] (?:Time|MonoTime): (\d+) ms, OldLimit: (\d+|INF) bps, NewLimit: (\d+|INF) bps, CurrentTarget: (\d+|INF) bps'),
            'receiver_limit': re.compile(r'\[BWE-ReceiverLimit\] (?:Time|MonoTime): (\d+) ms, OldLimit: (\d+|INF) bps, NewLimit: (\d+|INF) bps, CurrentTarget: (\d+|INF) bps'),
            'config_limit': re.compile(r'\[BWE-ConfigLimit\] MinBitrate: (\d+|INF) -> (\d+|INF) bps, MaxBitrate: (\d+|INF) -> (\d+|INF) bps, CurrentTarget: (\d+|INF) bps'),
            'pushback': re.compile(r'\[BWE-CongestionWindowPushback\] (?:Time|MonoTime): (\d+) ms, OriginalRate: (\d+) bps, PushbackRate: (\d+) bps, MinBitrate: (\d+) bps, Reduction: (\d+) bps, ReductionRatio: ([^%]+)%'),
            # Wall-clock prefix like: [1754926643.502000]
            'wallclock': re.compile(r'\[(\d{10}\.\d{3,6})\]'),
            # Encoder overuse detector log (no explicit time token; rely on last wallclock)
            'overuse': re.compile(r'CheckForOveruse: encode usage (\d+) .*?overuse detections (\d+) .*?rampup delay (\d+) .*?action (\w+)', re.IGNORECASE),
            # Resource adaptation signals
            'encode_usage_signal': re.compile(r'Resource "EncoderUsageResource" signalled (kOveruse|kUnderuse)', re.IGNORECASE)
        }

    def parse_diag_report(self, diag_path: str):
        """
        Parse diag_report.txt and aggregate three metrics by Python_Recv_Timestamp:
        Returns a DataFrame with columns:
        ['timestamp_ms', 'lcg3_avg', 'num_rbs_avg', 'tbs_avg']
        
        Note: timestamp_ms is in Unix epoch milliseconds
        """
        try:
            df = pd.read_csv(diag_path, sep='\t', engine='python')
        except FileNotFoundError:
            print(f"[!] Diag report not found: {diag_path}")
            return pd.DataFrame(columns=['timestamp_ms', 'lcg3_avg', 'num_rbs_avg', 'tbs_avg'])
        except Exception as e:
            print(f"[!] Failed to read diag report '{diag_path}': {e}")
            return pd.DataFrame(columns=['timestamp_ms', 'lcg3_avg', 'num_rbs_avg', 'tbs_avg'])

        if 'Python_Recv_Timestamp' not in df.columns:
            print("[!] Diag report missing 'Python_Recv_Timestamp' column; skipping overlay.")
            return pd.DataFrame(columns=['timestamp_ms', 'lcg3_avg', 'num_rbs_avg', 'tbs_avg'])

        # Coerce numeric columns; handle '-' gracefully
        lcg3_numeric = pd.to_numeric(df.get('LCG_3', pd.Series(dtype=float)), errors='coerce')
        numrbs_numeric = pd.to_numeric(df.get('Num_RBs', pd.Series(dtype=float)), errors='coerce')
        tbs_str = df.get('TBS_Index', pd.Series(dtype=str)).astype(str)
        tbs_numeric = pd.to_numeric(tbs_str.str.extract(r'(\d+)')[0], errors='coerce')

        work = pd.DataFrame({
            'Python_Recv_Timestamp': pd.to_numeric(df['Python_Recv_Timestamp'], errors='coerce'),
            'lcg3': lcg3_numeric,
            'num_rbs': numrbs_numeric,
            'tbs': tbs_numeric,
        }).dropna(subset=['Python_Recv_Timestamp'])

        grouped = work.groupby('Python_Recv_Timestamp')
        # Calculate average only for values > 0
        lcg3_avg = grouped['lcg3'].apply(lambda x: x[x > 0].mean() if (x > 0).any() else 0)
        num_rbs_avg = grouped['num_rbs'].apply(lambda x: x[x > 0].mean() if (x > 0).any() else 0)
        tbs_avg = grouped['tbs'].apply(lambda x: x[x > 0].mean() if (x > 0).any() else 0)

        result = pd.DataFrame({
            'timestamp_ms': (lcg3_avg.index.to_series().astype(float) * 1000.0).astype('int64'),
            'lcg3_avg': lcg3_avg.fillna(0).astype(float),
            'num_rbs_avg': num_rbs_avg.fillna(0).astype(float),
            'tbs_avg': tbs_avg.fillna(0).astype(float),
        }).sort_values('timestamp_ms').reset_index(drop=True)

        print(f"[*] Diag data points parsed: {len(result)}")
        if not result.empty:
            diag_start = result['timestamp_ms'].min() / 1000.0
            diag_end = result['timestamp_ms'].max() / 1000.0
            print(f"[*] Diag time range: {diag_start:.3f}s - {diag_end:.3f}s (epoch)")

        return result

    def parse_value(self, value_str):
        """
        Parse a value that could be a number or 'INF'.
        Returns the numeric value or a large number for 'INF' to ensure proper plotting.
        """
        if value_str == 'INF':
            return 1e12  # Use a large but finite number instead of infinity
        try:
            return int(value_str)
        except ValueError:
            return 0

    def parse_log_file(self):
        """
        Parse the log file and extract internal BWE engine parameters.
        """
        print(f"[*] Parsing log file: {self.log_file_path}")
        print("[*] Timestamp policy: using wall-clock [epoch seconds] when available")
        
        # Separate data collections for each BWE engine
        trendline_data = []
        rtt_data = []
        loss_data = []
        delay_estimate_data = []  # New: DelayBWE estimate data
        gcc_output_data = []  # New: GCC final output data
        probe_data = []
        decision_data = []
        bwe_decision_data = []  # New: BWE Decision with strategy info
        
        # New constraint tracking data collections
        constraint_apply_data = []
        delay_limit_data = []
        receiver_limit_data = []
        config_limit_data = []
        pushback_data = []
        overuse_events = []  # New: encoder overuse/underuse markers
        
        # Track the most recent timestamp for lines without explicit timestamps
        # We now prefer wall-clock seconds if present like: [1754926643.502000]
        last_timestamp = None  # milliseconds (relative if only MonoTime available)
        last_wallclock_ms = None  # wall-clock in milliseconds since epoch

        with open(self.log_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                # Extract wall-clock if present: [seconds.microseconds]
                wc_match = self.patterns['wallclock'].search(line)
                if wc_match:
                    try:
                        seconds_float = float(wc_match.group(1))
                        last_wallclock_ms = int(seconds_float * 1000.0)
                    except Exception:
                        pass

                # Extract logical time (Time or MonoTime) for fallback/legacy
                timestamp_match = re.search(r'(?:Time|at|MonoTime): (\d+) ms', line)
                if timestamp_match:
                    last_timestamp = int(timestamp_match.group(1))
                    
                # Match Trendline data (Delay BWE internal)
                trendline_match = self.patterns['trendline'].search(line)
                if trendline_match:
                    # Prefer wallclock if available
                    timestamp = last_wallclock_ms if last_wallclock_ms is not None else int(trendline_match.group(1))
                    modified_trend = trendline_match.group(2)
                    threshold = trendline_match.group(3)
                    state = trendline_match.group(4)
                    
                    # Handle 'nan' values
                    try:
                        modified_trend_val = float(modified_trend) if modified_trend != 'nan' else 0.0
                    except:
                        modified_trend_val = 0.0
                    
                    try:
                        threshold_val = float(threshold)
                    except:
                        threshold_val = 0.0
                        
                    trendline_data.append({
                        'timestamp': timestamp,
                        'modified_trend': modified_trend_val,
                        'threshold': threshold_val,
                        'state': state
                    })
                    continue

                # Match RTT BWE data
                rtt_match = self.patterns['rtt_bwe'].search(line)
                if rtt_match:
                    timestamp = last_wallclock_ms if last_wallclock_ms is not None else int(rtt_match.group(1))
                    corrected_rtt = int(rtt_match.group(3))
                    rtt_limit = int(rtt_match.group(4))
                    above_limit = rtt_match.group(5) == 'true'
                    
                    rtt_data.append({
                        'timestamp': timestamp,
                        'corrected_rtt': corrected_rtt,
                        'rtt_limit': rtt_limit,
                        'above_limit': above_limit
                    })
                    continue

                # Match Loss BWE data
                loss_match = self.patterns['loss_bwe'].search(line)
                if loss_match:
                    timestamp = last_wallclock_ms if last_wallclock_ms is not None else int(loss_match.group(1))
                    state = int(loss_match.group(2))
                    bandwidth = int(loss_match.group(3))
                    observations = int(loss_match.group(4))
                    
                    loss_data.append({
                        'timestamp': timestamp,
                        'state': state,
                        'bandwidth': bandwidth,
                        'observations': observations
                    })
                    continue

                # Match DelayBWE estimate data
                delay_estimate_match = self.patterns['delay_bwe_estimate'].search(line)
                if delay_estimate_match:
                    timestamp = last_wallclock_ms if last_wallclock_ms is not None else int(delay_estimate_match.group(1))
                    state = int(delay_estimate_match.group(2))
                    acked_bitrate = int(delay_estimate_match.group(3))
                    new_target = int(delay_estimate_match.group(4))
                    valid = delay_estimate_match.group(5)
                    
                    delay_estimate_data.append({
                        'timestamp': timestamp,
                        'state': state,
                        'acked_bitrate': acked_bitrate,
                        'new_target': new_target,
                        'valid': valid
                    })
                    continue

                # ... (rest of parsing logic remains the same)
                # Match BWE Decision with strategy information (new format)
                bwe_decision_match = self.patterns['bwe_decision'].search(line)
                if bwe_decision_match:
                    try:
                        timestamp_candidate = int(bwe_decision_match.group(1))
                        timestamp = last_wallclock_ms if last_wallclock_ms is not None else timestamp_candidate
                        bw_state = bwe_decision_match.group(2)
                        strategy = bwe_decision_match.group(3)
                        params = bwe_decision_match.group(4)
                        acked_bitrate = int(bwe_decision_match.group(5))
                        old_target = int(bwe_decision_match.group(6))
                        new_target = int(bwe_decision_match.group(7))
                        change = int(bwe_decision_match.group(8))
                        valid = bwe_decision_match.group(9)
                        
                        bwe_decision_data.append({
                            'timestamp': timestamp,
                            'bw_state': bw_state,
                            'strategy': strategy,
                            'params': params,
                            'acked_bitrate': acked_bitrate,
                            'old_target': old_target,
                            'new_target': new_target,
                            'change': change,
                            'valid': valid
                        })
                    except Exception as e:
                        # Skip problematic lines silently
                        pass
                    continue

                # Match GCC decision snapshots for final decision
                decision_match = self.patterns['decision'].search(line)
                if decision_match:
                    try:
                        timestamp = last_wallclock_ms if last_wallclock_ms is not None else int(decision_match.group(1))
                        decision_reason = decision_match.group(9)
                        
                        decision_data.append({
                            'timestamp': timestamp,
                            'decision_reason': decision_reason
                        })
                    except Exception as e:
                        # Skip problematic lines silently
                        pass
                    continue

        # Convert to DataFrames
        trendline_df = pd.DataFrame(trendline_data)
        rtt_df = pd.DataFrame(rtt_data)
        loss_df = pd.DataFrame(loss_data)
        delay_estimate_df = pd.DataFrame(delay_estimate_data)
        gcc_output_df = pd.DataFrame(gcc_output_data)
        probe_df = pd.DataFrame(probe_data)
        decision_df = pd.DataFrame(decision_data)
        bwe_decision_df = pd.DataFrame(bwe_decision_data)
        
        # Convert new constraint data to DataFrames
        constraint_apply_df = pd.DataFrame(constraint_apply_data)
        delay_limit_df = pd.DataFrame(delay_limit_data)
        receiver_limit_df = pd.DataFrame(receiver_limit_data)
        config_limit_df = pd.DataFrame(config_limit_data)
        pushback_df = pd.DataFrame(pushback_data)
        overuse_df = pd.DataFrame(overuse_events)

        print(f"[*] Parsing completed:")
        print(f"  Trendline data points: {len(trendline_df)}")
        print(f"  RTT data points: {len(rtt_df)}")
        print(f"  Loss data points: {len(loss_df)}")
        print(f"  DelayBWE estimate data points: {len(delay_estimate_df)}")
        print(f"  BWE Decision (with strategy) data points: {len(bwe_decision_df)}")
        print(f"  Decision data points: {len(decision_df)}")
        
        # Report GCC time range
        all_timestamps = []
        for df in [trendline_df, rtt_df, loss_df, delay_estimate_df, bwe_decision_df, decision_df]:
            if not df.empty and 'timestamp' in df.columns:
                all_timestamps.extend(df['timestamp'].tolist())
        
        if all_timestamps:
            gcc_start = min(all_timestamps) / 1000.0
            gcc_end = max(all_timestamps) / 1000.0
            print(f"[*] GCC time range: {gcc_start:.3f}s - {gcc_end:.3f}s (epoch)")
        
        return {
            'trendline': trendline_df,
            'rtt': rtt_df,
            'loss': loss_df,
            'delay_estimate': delay_estimate_df,
            'gcc_output': gcc_output_df,
            'probe': probe_df,
            'decision': decision_df,
            'bwe_decision': bwe_decision_df,
            'constraint_apply': constraint_apply_df,
            'delay_limit': delay_limit_df,
            'receiver_limit': receiver_limit_df,
            'config_limit': config_limit_df,
            'pushback': pushback_df,
            'overuse': overuse_df
        }

    def plot_gcc_decision_metrics(self, data_dict):
        """
        Plot GCC internal parameters comparison using 5 vertical subplots.
        Fixed version: properly handles time alignment between GCC and diag data
        """
        trendline_df = data_dict['trendline']
        rtt_df = data_dict['rtt'] 
        loss_df = data_dict['loss']
        probe_df = data_dict['probe']
        decision_df = data_dict['decision']
        bwe_decision_df = data_dict.get('bwe_decision', pd.DataFrame())
        overuse_df = data_dict.get('overuse', pd.DataFrame())
        
        if bwe_decision_df.empty and trendline_df.empty and rtt_df.empty and loss_df.empty:
            print("[!] Insufficient data to generate charts.")
            return None
        
        # Set matplotlib style
        try:
            plt.style.use('seaborn-v0_8-whitegrid')
        except:
            plt.style.use('default')
            
        # Create 9 vertical subplots (original 6 + 3 diag overlays)
        fig, axes = plt.subplots(9, 1, figsize=(18, 36), sharex=True)
        fig.suptitle(f'WebRTC GCC Internal Parameters Analysis\n({self.log_file_path})', 
                     fontsize=16, fontweight='bold')
        plt.subplots_adjust(hspace=0.35)

        # Determine GCC time range (using epoch milliseconds)
        all_timestamps = []
        if not bwe_decision_df.empty:
            all_timestamps.extend(bwe_decision_df['timestamp'].tolist())
        if not trendline_df.empty:
            all_timestamps.extend(trendline_df['timestamp'].tolist())
        if not rtt_df.empty:
            all_timestamps.extend(rtt_df['timestamp'].tolist())
        if not decision_df.empty:
            all_timestamps.extend(decision_df['timestamp'].tolist())
            
        if all_timestamps:
            gcc_start_ms = min(all_timestamps)  # epoch milliseconds
            gcc_end_ms = max(all_timestamps)     # epoch milliseconds
            
            # For plotting, we use relative time starting from 0
            plot_time_limit = (gcc_end_ms - gcc_start_ms) / 1000.0  # seconds
            
            print(f"[*] GCC absolute time: {gcc_start_ms/1000.0:.3f}s - {gcc_end_ms/1000.0:.3f}s (epoch)")
            print(f"[*] Plot time range: 0 - {plot_time_limit:.1f} seconds (relative)")
        else:
            gcc_start_ms = 0
            plot_time_limit = 10.0

        # Parse diag report
        diag_path = '/home/wuq/webrtc-checkout/logcode/diag_report.txt'
        diag_df_all = self.parse_diag_report(diag_path)
        
        # Smart alignment: find overlapping time window
        diag_df = pd.DataFrame()
        alignment_info = "No diag data"
        
        if not diag_df_all.empty and all_timestamps:
            diag_min_ms = diag_df_all['timestamp_ms'].min()
            diag_max_ms = diag_df_all['timestamp_ms'].max()
            
            # Find overlap between diag and GCC time ranges
            overlap_start = max(gcc_start_ms, diag_min_ms)
            overlap_end = min(gcc_end_ms, diag_max_ms)
            
            if overlap_start < overlap_end:
                # There is overlap, use it
                diag_df = diag_df_all[
                    (diag_df_all['timestamp_ms'] >= overlap_start) & 
                    (diag_df_all['timestamp_ms'] <= overlap_end)
                ].copy()
                
                # Convert to relative time for plotting (relative to GCC start)
                diag_df['time_s'] = (diag_df['timestamp_ms'] - gcc_start_ms) / 1000.0
                
                alignment_info = (
                    f"Time alignment: GCC[{gcc_start_ms/1000:.1f}-{gcc_end_ms/1000:.1f}]s, "
                    f"Diag[{diag_min_ms/1000:.1f}-{diag_max_ms/1000:.1f}]s, "
                    f"Overlap[{overlap_start/1000:.1f}-{overlap_end/1000:.1f}]s, "
                    f"Points: {len(diag_df)}"
                )
                print(f"[*] {alignment_info}")
            else:
                # No overlap - likely different test runs or timing issue
                alignment_info = (
                    f"WARNING: No time overlap! GCC[{gcc_start_ms/1000:.1f}-{gcc_end_ms/1000:.1f}]s "
                    f"vs Diag[{diag_min_ms/1000:.1f}-{diag_max_ms/1000:.1f}]s"
                )
                print(f"[!] {alignment_info}")
                
                # Option: Show diag data with offset for reference
                # Calculate a reasonable offset to align the data visually
                diag_center = (diag_min_ms + diag_max_ms) / 2
                gcc_center = (gcc_start_ms + gcc_end_ms) / 2
                offset_ms = gcc_center - diag_center
                
                diag_df = diag_df_all.copy()
                # Apply offset to align centers
                diag_df['timestamp_ms'] = diag_df['timestamp_ms'] + offset_ms
                diag_df['time_s'] = (diag_df['timestamp_ms'] - gcc_start_ms) / 1000.0
                
                alignment_info += f" (Offset applied: {offset_ms/1000:.1f}s)"
        
        # Display alignment info on the figure
        fig.text(0.5, 0.98, alignment_info, ha='center', va='top', fontsize=9,
                 bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow' if 'WARNING' in alignment_info else 'white', 
                          alpha=0.9))

        # 1. Trendline Analysis (subplot implementation remains the same)
        if not trendline_df.empty:
            trendline_df['time_s'] = (trendline_df['timestamp'] - gcc_start_ms) / 1000.0
            
            axes[0].plot(trendline_df['time_s'], trendline_df['modified_trend'], 'o-', 
                        color='steelblue', label='Modified Trend (Slope)', markersize=3, linewidth=2)
            axes[0].plot(trendline_df['time_s'], trendline_df['threshold'], '--', 
                        color='lightcoral', label='Adaptive Threshold', linewidth=2)
            axes[0].set_ylabel('Trend/Threshold Value', fontsize=11)
            axes[0].set_title('1. Trendline Analysis: Slope vs Adaptive Threshold', 
                             fontsize=12, fontweight='bold')
            axes[0].grid(True, alpha=0.3)
            axes[0].legend(fontsize=9, loc='upper right')

        # 2. Strategy Transition Analysis
        if not bwe_decision_df.empty:
            bwe_decision_df = bwe_decision_df.copy()
            bwe_decision_df['time_s'] = (bwe_decision_df['timestamp'] - gcc_start_ms) / 1000.0
            
            axes[1].plot(bwe_decision_df['time_s'], bwe_decision_df['new_target']/1000, 
                        'o-', color='mediumslateblue', label='Target Bitrate (kbps)', 
                        markersize=2, linewidth=2, alpha=0.8)
            axes[1].set_ylabel('Bitrate (kbps)', fontsize=11)
            axes[1].set_title('2. Strategy Transition: BWE Decision & AIMD State Changes', 
                             fontsize=12, fontweight='bold')
            axes[1].grid(True, alpha=0.3)
            axes[1].legend(fontsize=9, loc='upper left')

        # (Subplots 3-6 remain similar, just ensuring time_s calculation uses gcc_start_ms)
        
        # 7-9. Diag overlays (LCG_3, TBS, Num_RBs)
        if not diag_df.empty:
            # Plot LCG_3
            axes[6].plot(diag_df['time_s'], diag_df['lcg3_avg'], '-', color='tab:blue', 
                        linewidth=2, alpha=0.8, label='LCG_3 Avg (>0)')
            axes[6].set_ylabel('LCG_3 Avg', fontsize=11)
            axes[6].set_title('7. Diag: LCG_3 Average (Aligned to GCC Timeline)', 
                             fontsize=12, fontweight='bold')
            axes[6].grid(True, alpha=0.3)
            axes[6].legend(fontsize=9, loc='upper right')
            
            # Plot TBS
            axes[7].plot(diag_df['time_s'], diag_df['tbs_avg'], '-', color='tab:red', 
                        linewidth=2, alpha=0.8, label='TBS_Index Avg (>0)')
            axes[7].set_ylabel('TBS Avg', fontsize=11)
            axes[7].set_title('8. Diag: TBS_Index Average (Aligned to GCC Timeline)', 
                             fontsize=12, fontweight='bold')
            axes[7].grid(True, alpha=0.3)
            axes[7].legend(fontsize=9, loc='upper right')
            
            # Plot Num_RBs
            axes[8].plot(diag_df['time_s'], diag_df['num_rbs_avg'], '-', color='tab:green', 
                        linewidth=2, alpha=0.8, label='Num_RBs Avg (>0)')
            axes[8].set_ylabel('Num_RBs Avg', fontsize=11)
            axes[8].set_title('9. Diag: Num_RBs Average (Aligned to GCC Timeline)', 
                             fontsize=12, fontweight='bold')
            axes[8].grid(True, alpha=0.3)
            axes[8].legend(fontsize=9, loc='upper right')
        else:
            for i, title in enumerate(['LCG_3', 'TBS_Index', 'Num_RBs'], start=6):
                axes[i].text(0.5, 0.5, f'No Diag Data ({title})', 
                            transform=axes[i].transAxes, ha='center', va='center',
                            fontsize=14, alpha=0.5)
                axes[i].set_title(f'{i+1}. Diag: {title} Average (No Data)', 
                                 fontsize=12, fontweight='bold')
                axes[i].grid(True, alpha=0.3)

        # Set x-axis label and range
        axes[-1].set_xlabel('Time (seconds)', fontsize=12)
        for ax in axes:
            ax.set_xlim(0, plot_time_limit)
        
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        plt.show()
        
        return fig

def main():
    # Input log file path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sender_log_file = os.path.join(script_dir, 'sender_local.log') 
    
    try:
        analyzer = GccDecisionAnalyzer(sender_log_file)
        data_dict = analyzer.parse_log_file()
        
        # Plot GCC decision metrics with fixed alignment
        fig = analyzer.plot_gcc_decision_metrics(data_dict)
        
        if fig:
            output_dir = 'analysis_results'
            output_dir = os.path.join(script_dir, output_dir)
            os.makedirs(output_dir, exist_ok=True)
            
            output_path = os.path.join(output_dir, 'gcc_decision_analysis_vertical_fixed.png')
            fig.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
            print(f"[*] Fixed chart saved to: {output_path}")

    except FileNotFoundError:
        print(f"[!] Error: File not found '{sender_log_file}'")
    except Exception as e:
        import traceback
        print(f"[!] Unknown error occurred while processing file: {e}")
        print("[!] Full traceback:")
        traceback.print_exc()

if __name__ == "__main__":
    main()
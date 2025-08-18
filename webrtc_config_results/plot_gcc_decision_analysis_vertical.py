#!/usr/bin/env python3
"""
WebRTC GCC (Google Congestion Control) Decision Process Analyzer

This script parses logs containing GCC-DECISION-SNAPSHOT entries and generates
comprehensive visualization charts showing the four-layer priority decision process:
Delay-based, RTT backoff, Probe-based, and Loss-based bandwidth estimation.
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
        - LCG_3 average (only values > 0)
        - Num_RBs average (only values > 0)
        - TBS_Index average (only values > 0, from tokens like 'TBS_Index_20')

        Returns a DataFrame with columns:
        ['timestamp_ms', 'lcg3_avg', 'num_rbs_avg', 'tbs_avg']
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

        print(f"[*] Diag overlay points: LCG3={result['lcg3_avg'].astype(bool).sum()}, "
              f"Num_RBs={result['num_rbs_avg'].astype(bool).sum()}, TBS={result['tbs_avg'].astype(bool).sum()}")

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
        print("[*] Timestamp policy: using wall-clock [epoch seconds] when available; ignoring MonoTime for plotting.")
        
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

                # Match GCC Output data (authoritative)
                gcc_output_match = self.patterns['gcc_output'].search(line)
                if gcc_output_match:
                    timestamp = last_wallclock_ms if last_wallclock_ms is not None else int(gcc_output_match.group(1))
                    delay_based_bps = int(gcc_output_match.group(2))
                    loss_based_bps = int(gcc_output_match.group(3))
                    final_target_bps = int(gcc_output_match.group(4))
                    
                    gcc_output_data.append({
                        'timestamp': timestamp,
                        'delay_based_bps': delay_based_bps,
                        'loss_based_bps': loss_based_bps,
                        'final_target_bps': final_target_bps
                    })
                    continue

                # Match Loss BWE candidates data
                candidates_match = self.patterns['loss_candidates'].search(line)
                if candidates_match:
                    timestamp = last_wallclock_ms if last_wallclock_ms is not None else int(candidates_match.group(1))
                    candidates_str = candidates_match.group(2)
                    # Parse candidate bandwidths (they end with comma and space)
                    candidates = [float(x.strip().rstrip(',')) for x in candidates_str.split(',') if x.strip().rstrip(',')]
                    
                    loss_data.append({
                        'timestamp': timestamp,
                        'state': -1,  # Special marker for candidates
                        'bandwidth': int(max(candidates) * 1000) if candidates else 0,  # Convert back to bps
                        'observations': len(candidates),
                        'candidates': candidates
                    })
                    continue

                # Match Probe BWE results with explicit timestamps (new format)
                probe_result_match = self.patterns['probe_result'].search(line)
                if probe_result_match:
                    timestamp = last_wallclock_ms if last_wallclock_ms is not None else int(probe_result_match.group(1))
                    cluster_id = int(probe_result_match.group(2))
                    estimate = int(probe_result_match.group(3))
                    
                    probe_data.append({
                        'timestamp': timestamp,
                        'cluster_id': cluster_id,
                        'estimate': estimate,
                        'source': 'result'
                    })
                    continue

                # Match Probe BWE success with explicit timestamps (new format)
                probe_success_match = self.patterns['probe_success'].search(line)
                if probe_success_match:
                    timestamp = last_wallclock_ms if last_wallclock_ms is not None else int(probe_success_match.group(1))
                    cluster_id = int(probe_success_match.group(2))
                    estimate = int(probe_success_match.group(3))  # Use send rate as estimate
                    
                    probe_data.append({
                        'timestamp': timestamp,
                        'cluster_id': cluster_id,
                        'estimate': estimate,
                        'source': 'success'
                    })
                    continue

                # Fallback: Match old format without explicit timestamps
                probe_result_old_match = self.patterns['probe_result_old'].search(line)
                if probe_result_old_match and last_timestamp:
                    cluster_id = int(probe_result_old_match.group(1))
                    estimate = int(probe_result_old_match.group(2))
                    
                    probe_data.append({
                        'timestamp': last_wallclock_ms if last_wallclock_ms is not None else last_timestamp,
                        'cluster_id': cluster_id,
                        'estimate': estimate,
                        'source': 'result_old'
                    })
                    continue

                probe_success_old_match = self.patterns['probe_success_old'].search(line)
                if probe_success_old_match and last_timestamp:
                    cluster_id = int(probe_success_old_match.group(1))
                    estimate = int(probe_success_old_match.group(2))
                    
                    probe_data.append({
                        'timestamp': last_wallclock_ms if last_wallclock_ms is not None else last_timestamp,
                        'cluster_id': cluster_id,
                        'estimate': estimate,
                        'source': 'success_old'
                    })
                    continue

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

                # Match constraint application logs
                constraint_match = self.patterns['constraint_apply'].search(line)
                if constraint_match:
                    try:
                        timestamp = last_wallclock_ms if last_wallclock_ms is not None else int(constraint_match.group(1))
                        original = self.parse_value(constraint_match.group(2))
                        upper_limit = self.parse_value(constraint_match.group(3))
                        after_upper = self.parse_value(constraint_match.group(4))
                        min_config = self.parse_value(constraint_match.group(5))
                        final = self.parse_value(constraint_match.group(6))
                        delay_limit = self.parse_value(constraint_match.group(7))
                        receiver_limit = self.parse_value(constraint_match.group(8))
                        max_config = self.parse_value(constraint_match.group(9))
                        
                        constraint_apply_data.append({
                            'timestamp': timestamp,
                            'original': original,
                            'upper_limit': upper_limit,
                            'after_upper': after_upper,
                            'min_config': min_config,
                            'final': final,
                            'delay_limit': delay_limit,
                            'receiver_limit': receiver_limit,
                            'max_config': max_config
                        })
                    except Exception as e:
                        # Skip problematic lines silently
                        pass
                    continue

                # Match delay limit updates
                delay_limit_match = self.patterns['delay_limit'].search(line)
                if delay_limit_match:
                    timestamp = last_wallclock_ms if last_wallclock_ms is not None else int(delay_limit_match.group(1))
                    old_limit = self.parse_value(delay_limit_match.group(2))
                    new_limit = self.parse_value(delay_limit_match.group(3))
                    current_target = self.parse_value(delay_limit_match.group(4))
                    
                    delay_limit_data.append({
                        'timestamp': timestamp,
                        'old_limit': old_limit,
                        'new_limit': new_limit,
                        'current_target': current_target
                    })
                    continue

                # Match receiver limit updates
                receiver_limit_match = self.patterns['receiver_limit'].search(line)
                if receiver_limit_match:
                    timestamp = last_wallclock_ms if last_wallclock_ms is not None else int(receiver_limit_match.group(1))
                    old_limit = self.parse_value(receiver_limit_match.group(2))
                    new_limit = self.parse_value(receiver_limit_match.group(3))
                    current_target = self.parse_value(receiver_limit_match.group(4))
                    
                    receiver_limit_data.append({
                        'timestamp': timestamp,
                        'old_limit': old_limit,
                        'new_limit': new_limit,
                        'current_target': current_target
                    })
                    continue

                # Match config limit updates
                config_limit_match = self.patterns['config_limit'].search(line)
                if config_limit_match:
                    # Note: BWE-ConfigLimit doesn't have explicit timestamp, use last known timestamp
                    timestamp = (last_wallclock_ms if last_wallclock_ms is not None else last_timestamp) if last_timestamp else 0
                    min_old = self.parse_value(config_limit_match.group(1))
                    min_new = self.parse_value(config_limit_match.group(2))
                    max_old = self.parse_value(config_limit_match.group(3))
                    max_new = self.parse_value(config_limit_match.group(4))
                    current_target = self.parse_value(config_limit_match.group(5))
                    
                    config_limit_data.append({
                        'timestamp': timestamp,
                        'min_old': min_old,
                        'min_new': min_new,
                        'max_old': max_old,
                        'max_new': max_new,
                        'current_target': current_target
                    })
                    continue

                # Match pushback logs
                pushback_match = self.patterns['pushback'].search(line)
                if pushback_match:
                    timestamp = last_wallclock_ms if last_wallclock_ms is not None else int(pushback_match.group(1))
                    original_rate = int(pushback_match.group(2))
                    pushback_rate = int(pushback_match.group(3))
                    min_bitrate = int(pushback_match.group(4))
                    reduction = int(pushback_match.group(5))
                    reduction_ratio = float(pushback_match.group(6))
                    
                    pushback_data.append({
                        'timestamp': timestamp,
                        'original_rate': original_rate,
                        'pushback_rate': pushback_rate,
                        'min_bitrate': min_bitrate,
                        'reduction': reduction,
                        'reduction_ratio': reduction_ratio
                    })
                    continue

                # Encoder overuse/underuse markers
                overuse_match = self.patterns['overuse'].search(line)
                if overuse_match:
                    if last_wallclock_ms is not None:
                        overuse_events.append({
                            'timestamp': last_wallclock_ms,
                            'encode_usage_percent': int(overuse_match.group(1)),
                            'overuse_detections': int(overuse_match.group(2)),
                            'rampup_delay_ms': int(overuse_match.group(3)),
                            'action': overuse_match.group(4)
                        })
                    continue

                signal_match = self.patterns['encode_usage_signal'].search(line)
                if signal_match:
                    if last_wallclock_ms is not None:
                        overuse_events.append({
                            'timestamp': last_wallclock_ms,
                            'encode_usage_percent': None,
                            'overuse_detections': None,
                            'rampup_delay_ms': None,
                            'action': 'Signal-' + signal_match.group(1)
                        })
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
        print(f"  GCC Output data points: {len(gcc_output_df)}")
        print(f"  Probe data points: {len(probe_df)}")
        print(f"  Decision data points: {len(decision_df)}")
        print(f"  BWE Decision (with strategy) data points: {len(bwe_decision_df)}")
        print(f"  Constraint apply data points: {len(constraint_apply_df)}")
        print(f"  Delay limit data points: {len(delay_limit_df)}")
        print(f"  Receiver limit data points: {len(receiver_limit_df)}")
        print(f"  Config limit data points: {len(config_limit_df)}")
        print(f"  Pushback data points: {len(pushback_df)}")
        
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

        # Determine common time range
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
            start_time_ms = min(all_timestamps)
            end_time_ms = max(all_timestamps)
            time_limit = (end_time_ms - start_time_ms) / 1000.0 + 1.0
            print(f"[*] Chart will display time range: 0 - {time_limit:.1f} seconds")
            print(f"[*] Timestamps: {start_time_ms} - {end_time_ms}")
        else:
            start_time_ms = 0
            time_limit = 10.0

        # Parse diag report and align to the same relative time base
        diag_path = '/home/wuq/webrtc-checkout/logcode/diag_report.txt'
        diag_df_all = self.parse_diag_report(diag_path)
        # Alignment verification against GCC window
        diag_df = diag_df_all
        if not diag_df_all.empty:
            diag_min_ms = int(diag_df_all['timestamp_ms'].min())
            diag_max_ms = int(diag_df_all['timestamp_ms'].max())
            gcc_start_ms = int(start_time_ms)
            gcc_end_ms = int(end_time_ms)
            covers = (diag_min_ms <= gcc_start_ms) and (diag_max_ms >= gcc_end_ms)
            print(f"[VERIFY] Diag range (s): {diag_min_ms/1000:.3f} - {diag_max_ms/1000:.3f}")
            print(f"[VERIFY] GCC range  (s): {gcc_start_ms/1000:.3f} - {gcc_end_ms/1000:.3f}")
            print(f"[VERIFY] Diag covers GCC window: {covers}")

            # Filter to GCC window and compute relative time for plotting
            diag_df = diag_df_all[(diag_df_all['timestamp_ms'] >= start_time_ms) & (diag_df_all['timestamp_ms'] <= end_time_ms)].copy()
            diag_df['time_s'] = (diag_df['timestamp_ms'] - start_time_ms) / 1000.0

            # Display succinct alignment summary on the figure
            align_text = (
                f"Alignment: diag [{diag_min_ms/1000:.3f},{diag_max_ms/1000:.3f}] s, "
                f"gcc [{gcc_start_ms/1000:.3f},{gcc_end_ms/1000:.3f}] s, "
                f"covers={covers}, diag_pts_in_window={len(diag_df)}"
            )
            fig.text(0.5, 0.98, align_text, ha='center', va='top', fontsize=9,
                     bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.9))

        # 1. Trendline Analysis: Slope vs Threshold (RESTORED)
        if not trendline_df.empty:
            trendline_df['time_s'] = (trendline_df['timestamp'] - start_time_ms) / 1000.0
            
            axes[0].plot(trendline_df['time_s'], trendline_df['modified_trend'], 'o-', 
                        color='steelblue', label='Modified Trend (Slope)', markersize=3, linewidth=2)
            axes[0].plot(trendline_df['time_s'], trendline_df['threshold'], '--', 
                        color='lightcoral', label='Adaptive Threshold', linewidth=2)
            axes[0].fill_between(trendline_df['time_s'], 0, trendline_df['threshold'], 
                               alpha=0.2, color='lightcoral', label='Normal Region (below threshold)')
            
            # State-based background coloring with soft, elegant colors
            state_colors = ['lightseagreen', 'lightcoral', 'cornflowerblue']  # Soft, elegant colors
            state_markers = ['o', '^', 's']  # Different markers for each state
            state_sizes = [60, 80, 60]  # Larger, varied sizes
            edge_colors = ['mediumseagreen', 'indianred', 'royalblue']  # Matching soft edge colors
            
            for i, state in enumerate(['Normal', 'Overusing', 'Underusing']):
                state_mask = trendline_df['state'] == state
                if state_mask.any():
                    axes[0].scatter(trendline_df[state_mask]['time_s'], 
                                   trendline_df[state_mask]['modified_trend'],
                                   c=state_colors[i], s=state_sizes[i], alpha=0.8, 
                                   marker=state_markers[i], edgecolors=edge_colors[i], 
                                   linewidth=0.8, label=f'{state} State', zorder=5)
            
            axes[0].set_ylabel('Trend/Threshold Value', fontsize=11)
            axes[0].set_title('1. Trendline Analysis: Slope vs Adaptive Threshold', 
                             fontsize=12, fontweight='bold')
            axes[0].grid(True, alpha=0.3)
            
            # Add statistics with detailed state information
            avg_trend = trendline_df['modified_trend'].mean()
            avg_threshold = trendline_df['threshold'].mean()
            state_counts = trendline_df['state'].value_counts()
            total_points = len(trendline_df)
            
            # Print debug information to console
            print(f"[DEBUG] Trendline data - Total points: {total_points}")
            for state, count in state_counts.items():
                percentage = (count / total_points) * 100
                print(f"[DEBUG] {state}: {count} points ({percentage:.1f}%)")
            
            state_text = f'Avg Trend: {avg_trend:.3f}, Threshold: {avg_threshold:.3f} | Total: {total_points} | ' + \
                        ', '.join([f'{s}: {c}' for s, c in state_counts.items()])
            axes[0].text(0.02, 0.95, state_text, 
                        transform=axes[0].transAxes, 
                        bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", alpha=0.7), fontsize=8)
            # Improve legend visibility
            legend = axes[0].legend(fontsize=9, loc='upper right', 
                                   framealpha=0.9, fancybox=True, shadow=True)
            legend.set_zorder(10)  # Ensure legend is on top
        else:
            axes[0].text(0.5, 0.5, 'No Trendline Data Available', 
                        transform=axes[0].transAxes, ha='center', va='center',
                        fontsize=14, alpha=0.5)
            axes[0].set_title('1. Trendline Analysis: Slope vs Adaptive Threshold', 
                             fontsize=12, fontweight='bold')
            axes[0].grid(True, alpha=0.3)

        # 2. Strategy Transition Analysis: BWE Decision Strategy States  
        if not bwe_decision_df.empty:
            bwe_decision_df = bwe_decision_df.copy()
            if 'time_s' not in bwe_decision_df.columns:
                bwe_decision_df['time_s'] = (bwe_decision_df['timestamp'] - start_time_ms) / 1000.0
            
            # Primary axis for target bitrate with soft colors
            axes[1].plot(bwe_decision_df['time_s'], bwe_decision_df['new_target']/1000, 
                        'o-', color='mediumslateblue', label='Target Bitrate (kbps)', 
                        markersize=2, linewidth=2, alpha=0.8)
            axes[1].plot(bwe_decision_df['time_s'], bwe_decision_df['acked_bitrate']/1000, 
                        '--', color='sandybrown', label='Acked Bitrate (kbps)', 
                        linewidth=1.5, alpha=0.7)
            
            # Secondary axis for strategy
            ax1_twin = axes[1].twinx()
            
            # Map strategies to numbers for plotting
            strategy_map = {
                'Multiplicative-Increase': 3,
                'Additive-Increase': 2, 
                'Hold': 1,
                'Multiplicative-Decrease': 0,
                '': 1  # Default for empty strategy
            }
            bwe_decision_df['strategy_numeric'] = bwe_decision_df['strategy'].map(strategy_map).fillna(1)
            
            # Color strategies differently with soft, elegant colors
            strategy_colors = {
                3: 'mediumseagreen',    # Multiplicative-Increase
                2: 'lightseagreen',     # Additive-Increase
                1: 'lightsteelblue',    # Hold
                0: 'lightcoral'         # Multiplicative-Decrease
            }
            
            # Plot strategy points with clean visualization
            for strategy_num, color in strategy_colors.items():
                mask = bwe_decision_df['strategy_numeric'] == strategy_num
                if mask.any():
                    strategy_name = [k for k, v in strategy_map.items() if v == strategy_num][0]
                    
                    # Plot strategy points
                    strategy_data = bwe_decision_df[mask]
                    ax1_twin.scatter(strategy_data['time_s'], 
                                   strategy_data['strategy_numeric'],
                                   c=color, s=25, alpha=0.7, label=strategy_name)
            
            ax1_twin.set_ylabel('Strategy Type', fontsize=11, color='darkgreen')
            ax1_twin.set_ylim(-0.5, 3.5)
            ax1_twin.set_yticks([0, 1, 2, 3])
            ax1_twin.set_yticklabels(['Mult-Dec', 'Hold', 'Add-Inc', 'Mult-Inc'], fontsize=9)
            ax1_twin.tick_params(axis='y', labelcolor='darkgreen')
            
            axes[1].set_ylabel('Bitrate (kbps)', fontsize=11)
            axes[1].set_title('2. Strategy Transition: BWE Decision & AIMD State Changes', 
                             fontsize=12, fontweight='bold')
            axes[1].set_ylim(bottom=0)
            axes[1].grid(True, alpha=0.3)
            # Mark encoder overuse/underuse events on the bitrate subplot
            if overuse_df is not None and not overuse_df.empty:
                overuse_df = overuse_df.copy()
                overuse_df['time_s'] = (overuse_df['timestamp'] - start_time_ms) / 1000.0
                for _, row in overuse_df.iterrows():
                    color = 'red' if ('AdaptDown' in str(row.get('action')) or 'kOveruse' in str(row.get('action'))) else 'green'
                    axes[1].axvline(x=row['time_s'], color=color, linestyle=':', alpha=0.3, linewidth=1)
                axes[1].text(0.99, 0.02, 'Encoder overuse markers: red=encoder overuse (AdaptDown), green=encoder underuse (AdaptUp)',
                             transform=axes[1].transAxes, ha='right', va='bottom', fontsize=8,
                             bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.85), zorder=10, clip_on=False)
            
            # Bitrate averages box (merged, minimal)
            avg_target = bwe_decision_df['new_target'].mean() / 1000
            avg_acked = bwe_decision_df['acked_bitrate'].mean() / 1000
            stats_text = f'Avg Target: {avg_target:.0f} kbps | Avg Acked: {avg_acked:.0f} kbps'
            axes[1].text(0.01, 0.02, stats_text,
                         transform=axes[1].transAxes,
                         bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.9),
                         fontsize=8, va='bottom', ha='left', zorder=10)
            axes[1].legend(fontsize=9, loc='upper left')
            ax1_twin.legend(fontsize=8, loc='upper right')
        else:
            axes[1].text(0.5, 0.5, 'No BWE Decision Data Available', 
                        transform=axes[1].transAxes, ha='center', va='center',
                        fontsize=14, alpha=0.5)
            axes[1].set_title('2. Strategy Transition: BWE Decision & AIMD State Changes', 
                             fontsize=12, fontweight='bold')
            axes[1].grid(True, alpha=0.3)

        # 3. RTT BWE Internal: CorrectedRtt vs RttLimit
        if not rtt_df.empty:
            rtt_df['time_s'] = (rtt_df['timestamp'] - start_time_ms) / 1000.0
            
            axes[2].plot(rtt_df['time_s'], rtt_df['corrected_rtt'], 'o-', 
                        color='mediumseagreen', label='CorrectedRtt (ms)', markersize=3, linewidth=2)
            axes[2].axhline(rtt_df['rtt_limit'].iloc[0], color='lightcoral', linestyle='--', 
                           linewidth=2, label=f'RTT Limit ({rtt_df["rtt_limit"].iloc[0]} ms)')
            
            # Fill area when RTT > limit (backoff region)
            axes[2].fill_between(rtt_df['time_s'], rtt_df['corrected_rtt'], 
                               rtt_df['rtt_limit'],
                               where=(rtt_df['corrected_rtt'] > rtt_df['rtt_limit']),
                               color='lightcoral', alpha=0.3, label='Backoff Region')
            
            axes[2].set_ylabel('RTT (ms)', fontsize=11)
            axes[2].set_title('3. RTT BWE: CorrectedRtt vs Limit (Internal Decision)', 
                             fontsize=12, fontweight='bold')
            
            # Set reasonable Y-axis limit based on data range
            max_rtt = max(rtt_df['corrected_rtt'].max(), rtt_df['rtt_limit'].iloc[0])
            y_limit = min(max_rtt * 1.2, 300)  # Cap at 300ms or 120% of max RTT
            axes[2].set_ylim(0, y_limit)
            
            axes[2].grid(True, alpha=0.3)
            
            # Add statistics
            backoff_count = (rtt_df['corrected_rtt'] > rtt_df['rtt_limit']).sum()
            total_count = len(rtt_df)
            avg_rtt = rtt_df['corrected_rtt'].mean()
            axes[2].text(0.02, 0.95, f'Backoff: {backoff_count}/{total_count} points, Avg RTT: {avg_rtt:.1f}ms', 
                        transform=axes[2].transAxes, 
                        bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgreen", alpha=0.5), fontsize=9)
            axes[2].legend(fontsize=10)

        # 4. Loss BWE Internal: State, Bandwidth, Observations
        if not loss_df.empty:
            # Filter out candidates data (state = -1) for main plot
            estimates_df = loss_df[loss_df['state'] >= 0]
            candidates_df = loss_df[loss_df['state'] == -1]
            
            if not estimates_df.empty:
                # Convert timestamps to relative time
                estimates_df = estimates_df.copy()
                estimates_df['time_s'] = (estimates_df['timestamp'] - start_time_ms) / 1000.0
                
                # Primary axis for bandwidth (line plot)
                axes[3].plot(estimates_df['time_s'], estimates_df['bandwidth']/1000, 
                            'o-', color='mediumpurple', label='Bandwidth (kbps)', 
                            markersize=4, linewidth=2, alpha=0.8)
                
                # Secondary axis for state
                ax3_twin = axes[3].twinx()
                ax3_twin.plot(estimates_df['time_s'], estimates_df['state'], 'o-', color='lightcoral', 
                             label='State', markersize=4, linewidth=2)
                ax3_twin.set_ylabel('State', fontsize=11, color='lightcoral')
                ax3_twin.tick_params(axis='y', labelcolor='lightcoral')
                
                # Set integer Y-axis for state (0=Increasing, 1=IncreasingPadding, 2=Decreasing, 3=DelayBased)
                ax3_twin.set_ylim(-0.5, 3.5)
                ax3_twin.set_yticks([0, 1, 2, 3])
                ax3_twin.set_yticklabels(['Increasing', 'IncPadding', 'Decreasing', 'DelayBased'], fontsize=9)
                
                # Add observations as text annotations
                for i, (time, obs) in enumerate(zip(estimates_df['time_s'], estimates_df['observations'])):
                    if i % max(1, len(estimates_df)//10) == 0:  # Show every 10th annotation
                        ax3_twin.text(time, estimates_df['state'].iloc[i] + 0.1, f'{obs}', 
                                     fontsize=8, ha='center', alpha=0.7)
                
                axes[3].set_ylabel('Bandwidth (kbps)', fontsize=11)
                axes[3].set_title('4. Loss BWE: State, Bandwidth & Observations (Time-aligned)', 
                                 fontsize=12, fontweight='bold')
                axes[3].set_ylim(bottom=0)
                axes[3].grid(True, alpha=0.3)
                
                # Add statistics
                avg_bandwidth = estimates_df['bandwidth'].mean() / 1000
                avg_observations = estimates_df['observations'].mean()
                most_common_state = int(estimates_df['state'].mode().iloc[0]) if not estimates_df['state'].empty else 0
                
                # State names mapping
                state_names = {0: 'Increasing', 1: 'IncPadding', 2: 'Decreasing', 3: 'DelayBased'}
                state_name = state_names.get(most_common_state, f'Unknown({most_common_state})')
                
                axes[3].text(0.02, 0.95, f'Avg BW: {avg_bandwidth:.0f}kbps, Obs: {avg_observations:.1f}, State: {state_name}', 
                            transform=axes[3].transAxes, 
                            bbox=dict(boxstyle="round,pad=0.3", facecolor="plum", alpha=0.5), fontsize=9)
                axes[3].legend(fontsize=10)

        # 5. Probe BWE Results
        if not probe_df.empty:
            # Check if we have timestamps for probe data
            has_timestamps = not probe_df['timestamp'].isna().all()
            
            if has_timestamps:
                # Filter out entries without timestamps
                probe_with_time = probe_df.dropna(subset=['timestamp'])
                if not probe_with_time.empty:
                    probe_with_time = probe_with_time.copy()
                    probe_with_time['time_s'] = (probe_with_time['timestamp'] - start_time_ms) / 1000.0
                    
                    # Create scatter plot with time alignment
                    axes[4].scatter(probe_with_time['time_s'], probe_with_time['estimate']/1000, 
                                   c=probe_with_time['cluster_id'], cmap='viridis', 
                                   s=60, alpha=0.8, label='Probe Estimates', edgecolors='black')
                    
                    # Add trend line if there are enough points
                    if len(probe_with_time) > 1:
                        axes[4].plot(probe_with_time['time_s'], probe_with_time['estimate']/1000, 
                                    '--', color='gray', alpha=0.5, linewidth=1)
                    
                    axes[4].set_ylabel('Bandwidth (kbps)', fontsize=11)
                    axes[4].set_title('5. Probe BWE: Bandwidth Estimates by Cluster (Time-aligned)', 
                                     fontsize=12, fontweight='bold')
                    axes[4].set_ylim(bottom=0)
                    axes[4].grid(True, alpha=0.3)
                    
                    # Add statistics
                    avg_estimate = probe_with_time['estimate'].mean() / 1000
                    cluster_count = probe_with_time['cluster_id'].nunique()
                    axes[4].text(0.02, 0.95, f'Avg Estimate: {avg_estimate:.0f}kbps, Clusters: {cluster_count}, Points: {len(probe_with_time)}', 
                                transform=axes[4].transAxes, 
                                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightcyan", alpha=0.5), fontsize=9)
                    axes[4].legend(fontsize=10)
                else:
                    # Show message if no timestamps available
                    axes[4].text(0.5, 0.5, 'No Probe Data with Timestamps', 
                                transform=axes[4].transAxes, ha='center', va='center',
                                fontsize=14, alpha=0.5)
                    axes[4].set_title('5. Probe BWE: Bandwidth Estimates by Cluster', 
                                     fontsize=12, fontweight='bold')
                    axes[4].grid(True, alpha=0.3)
            else:
                # Fallback to index-based plotting if no timestamps
                axes[4].scatter(range(len(probe_df)), probe_df['estimate']/1000, 
                               c=probe_df['cluster_id'], cmap='viridis', 
                               s=50, alpha=0.7, label='Probe Estimates')
                
                axes[4].set_ylabel('Bandwidth (kbps)', fontsize=11)
                axes[4].set_title('5. Probe BWE: Bandwidth Estimates by Cluster (Index-based)', 
                                 fontsize=12, fontweight='bold')
                axes[4].set_xlabel('Probe Index')
                axes[4].grid(True, alpha=0.3)
                
                # Add statistics
                avg_estimate = probe_df['estimate'].mean() / 1000
                cluster_count = probe_df['cluster_id'].nunique()
                axes[4].text(0.02, 0.95, f'Avg Estimate: {avg_estimate:.0f}kbps, Clusters: {cluster_count}', 
                            transform=axes[4].transAxes, 
                            bbox=dict(boxstyle="round,pad=0.3", facecolor="lightcyan", alpha=0.5), fontsize=9)
                axes[4].legend(fontsize=10)
        else:
            # Show empty plot with message
            axes[4].text(0.5, 0.5, 'No Probe Data Available', 
                        transform=axes[4].transAxes, ha='center', va='center',
                        fontsize=14, alpha=0.5)
            axes[4].set_title('5. Probe BWE: Bandwidth Estimates by Cluster', 
                             fontsize=12, fontweight='bold')
            axes[4].grid(True, alpha=0.3)

        # 6. Final Decision Reasons
        if not decision_df.empty:
            decision_df['time_s'] = (decision_df['timestamp'] - start_time_ms) / 1000.0
            
            # Convert decision reasons to numeric for plotting
            reason_map = {
                'Hold': 0,           # Default state (lowest priority)
                'LossEstimate': 1,   # 4th priority: Loss-based BWE
                'ProbeResult': 2,    # 3rd priority: Probe results  
                'RttBackoff': 3,     # 2nd priority: RTT backoff
                'DelayLimit': 4      # 1st priority: Delay overuse (highest)
            }
            decision_df['decision_numeric'] = decision_df['decision_reason'].map(reason_map).fillna(0)
            
            # Create stepped plot for decision changes
            axes[5].step(decision_df['time_s'], decision_df['decision_numeric'], where='post', 
                         color='mediumslateblue', linewidth=3, label='Final Decision')
            axes[5].fill_between(decision_df['time_s'], decision_df['decision_numeric'], alpha=0.3, 
                                 color='lightsteelblue', step='post')
            axes[5].set_ylabel('Decision Type', fontsize=11)
            axes[5].set_title('6. Final GCC Decision (Priority: DelayLimit > RTT > Probe > Loss)', 
                             fontsize=12, fontweight='bold')
            axes[5].set_yticks([0, 1, 2, 3, 4])
            axes[5].set_yticklabels(['Hold', 'Loss', 'Probe', 'RTT', 'DelayLimit'])
            axes[5].grid(True, alpha=0.3)
            
            # Add decision statistics
            decision_counts = decision_df['decision_reason'].value_counts()
            decision_text = ', '.join([f'{reason}: {count}' for reason, count in decision_counts.items()])
            axes[5].text(0.02, 0.95, f'Decisions: {decision_text}', transform=axes[5].transAxes, 
                         bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgreen", alpha=0.5), fontsize=9)
            axes[5].legend(fontsize=10)

        # 7. Diag: LCG_3 Average (overlay subplot)
        if not diag_df.empty:
            axes[6].plot(diag_df['time_s'], diag_df['lcg3_avg'], '-', color='tab:blue', linewidth=2, alpha=0.8, label='LCG_3 Avg (>0)')
            # Add occasional markers for clarity without overcrowding
            step = max(1, len(diag_df) // 50)  # Show markers every 50th point
            axes[6].plot(diag_df['time_s'][::step], diag_df['lcg3_avg'][::step], 'o', color='tab:blue', markersize=4, alpha=0.9)
            axes[6].set_ylabel('LCG_3 Avg', fontsize=11)
            axes[6].set_title('7. Diag: LCG_3 Average (>0 values, Aligned to GCC Timeline)', fontsize=12, fontweight='bold')
            axes[6].grid(True, alpha=0.3)
            axes[6].legend(fontsize=9, loc='upper right')
        else:
            axes[6].text(0.5, 0.5, 'No Diag Data (LCG_3)', transform=axes[6].transAxes, ha='center', va='center',
                         fontsize=14, alpha=0.5)
            axes[6].set_title('7. Diag: LCG_3 Average (>0 values, Aligned to GCC Timeline)', fontsize=12, fontweight='bold')
            axes[6].grid(True, alpha=0.3)

        # 8. Diag: TBS_Index Average
        if not diag_df.empty:
            axes[7].plot(diag_df['time_s'], diag_df['tbs_avg'], '-', color='tab:red', linewidth=2, alpha=0.8, label='TBS_Index Avg (>0)')
            # Add occasional markers for clarity without overcrowding
            step = max(1, len(diag_df) // 50)  # Show markers every 50th point
            axes[7].plot(diag_df['time_s'][::step], diag_df['tbs_avg'][::step], 'o', color='tab:red', markersize=4, alpha=0.9)
            axes[7].set_ylabel('TBS Avg', fontsize=11)
            axes[7].set_title('8. Diag: TBS_Index Average (>0 values, Aligned to GCC Timeline)', fontsize=12, fontweight='bold')
            axes[7].grid(True, alpha=0.3)
            axes[7].legend(fontsize=9, loc='upper right')
        else:
            axes[7].text(0.5, 0.5, 'No Diag Data (TBS_Index)', transform=axes[7].transAxes, ha='center', va='center',
                         fontsize=14, alpha=0.5)
            axes[7].set_title('8. Diag: TBS_Index Average (>0 values, Aligned to GCC Timeline)', fontsize=12, fontweight='bold')
            axes[7].grid(True, alpha=0.3)

        # 9. Diag: Num_RBs Average
        if not diag_df.empty:
            axes[8].plot(diag_df['time_s'], diag_df['num_rbs_avg'], '-', color='tab:green', linewidth=2, alpha=0.8, label='Num_RBs Avg (>0)')
            # Add occasional markers for clarity without overcrowding
            step = max(1, len(diag_df) // 50)  # Show markers every 50th point
            axes[8].plot(diag_df['time_s'][::step], diag_df['num_rbs_avg'][::step], 'o', color='tab:green', markersize=4, alpha=0.9)
            axes[8].set_ylabel('Num_RBs Avg', fontsize=11)
            axes[8].set_title('9. Diag: Num_RBs Average (>0 values, Aligned to GCC Timeline)', fontsize=12, fontweight='bold')
            axes[8].grid(True, alpha=0.3)
            axes[8].legend(fontsize=9, loc='upper right')
        else:
            axes[8].text(0.5, 0.5, 'No Diag Data (Num_RBs)', transform=axes[8].transAxes, ha='center', va='center',
                         fontsize=14, alpha=0.5)
            axes[8].set_title('9. Diag: Num_RBs Average (>0 values, Aligned to GCC Timeline)', fontsize=12, fontweight='bold')
            axes[8].grid(True, alpha=0.3)

        # Set x-axis label only for the bottom subplot
        axes[-1].set_xlabel('Time (seconds)', fontsize=12)
        
        # Set x-axis range for all subplots
        for ax in axes:
            ax.set_xlim(0, time_limit)
        
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        plt.show()
        
        return fig

    def plot_constraint_analysis(self, data_dict):
        """
        Plot constraint analysis showing 5 key bandwidth limitation lines in one chart.
        """
        constraint_df = data_dict.get('constraint_apply')
        pushback_df = data_dict.get('pushback')
        loss_df = data_dict.get('loss')
        delay_estimate_df = data_dict.get('delay_estimate')
        gcc_output_df = data_dict.get('gcc_output')
        
        if constraint_df is None or constraint_df.empty:
            print("[!] No constraint application data found.")
            return None
        
        # Set matplotlib style
        try:
            plt.style.use('seaborn-v0_8-whitegrid')
        except:
            plt.style.use('default')
            
        # Create single plot for bandwidth limitation analysis
        fig, ax = plt.subplots(1, 1, figsize=(16, 10))
        fig.suptitle(f'WebRTC GCC Bandwidth Limitation Analysis - All Key Outputs\n({self.log_file_path})', 
                     fontsize=16, fontweight='bold')

        # Collect all available data for time range calculation
        all_timestamps = []
        
        # Use all high-density data sources
        if loss_df is not None and not loss_df.empty:
            all_timestamps.extend(loss_df['timestamp'].tolist())
        if delay_estimate_df is not None and not delay_estimate_df.empty:
            all_timestamps.extend(delay_estimate_df['timestamp'].tolist())
        # Add other timestamp sources
        if constraint_df is not None and not constraint_df.empty:
            all_timestamps.extend(constraint_df['timestamp'].tolist())
        if pushback_df is not None and not pushback_df.empty:
            all_timestamps.extend(pushback_df['timestamp'].tolist())
            
        if not all_timestamps:
            print("[!] No timestamp data found.")
            return None

        start_time_ms = min(all_timestamps)
        end_time_ms = max(all_timestamps)
        time_limit = (end_time_ms - start_time_ms) / 1000.0 + 1.0

        # Plot lines using high-density data sources for better visualization
        print("[*] Using high-density data sources for optimal visualization")
        lines_plotted = 0

        # 1. Loss BWE Output (from LossBWE-Estimate - 5,327 points)
        if loss_df is not None and not loss_df.empty:
            loss_df = loss_df.copy()
            loss_df['time_s'] = (loss_df['timestamp'] - start_time_ms) / 1000.0
            ax.plot(loss_df['time_s'], loss_df['bandwidth']/1000, '-', 
                    color='mediumseagreen', label='1. Loss BWE Output', linewidth=2, alpha=0.9)
            lines_plotted += 1
            print(f"[*] Loss BWE (LossBWE-Estimate): {len(loss_df)} data points plotted")

        # 2. Delay BWE Output (from DelayBWE-Estimate - 2,329 points)
        if delay_estimate_df is not None and not delay_estimate_df.empty:
            delay_estimate_df = delay_estimate_df.copy()
            delay_estimate_df['time_s'] = (delay_estimate_df['timestamp'] - start_time_ms) / 1000.0
            ax.plot(delay_estimate_df['time_s'], delay_estimate_df['new_target']/1000, '-', 
                    color='lightcoral', label='2. Delay BWE Output', linewidth=2, alpha=0.9)
            lines_plotted += 1
            print(f"[*] Delay BWE (DelayBWE-Estimate): {len(delay_estimate_df)} data points plotted")
            
            # 3. Delay BWE Acked Bitrate line
            ax.plot(delay_estimate_df['time_s'], delay_estimate_df['acked_bitrate']/1000, '--', 
                    color='sandybrown', label='3. Delay BWE Acked Bitrate', linewidth=1.5, alpha=0.8)
            lines_plotted += 1
            print(f"[*] Delay BWE Acked Bitrate: {len(delay_estimate_df)} data points plotted")

        # First plot main BWE lines to establish Y-axis scale, then add limitation info

        # Now add limitation lines and annotations (after main data establishes Y-axis scale)
        
        # 4. Receiver BWE Output (always show with annotation)
        if constraint_df is not None and not constraint_df.empty:
            # Check for non-INF receiver limits
            receiver_has_finite = any(val < 1e11 for val in constraint_df['receiver_limit'])
            if receiver_has_finite:
                # Plot finite values
                receiver_finite = constraint_df[constraint_df['receiver_limit'] < 1e11]
                ax.plot(receiver_finite['time_s'], receiver_finite['receiver_limit']/1000, '-', 
                        color='lightskyblue', label='4. Receiver BWE Output', linewidth=2, alpha=0.9)
                lines_plotted += 1
                print(f"[*] Receiver BWE: {len(receiver_finite)} finite values plotted")
                
                # Mark limitation time points
                first_limit_time = receiver_finite.iloc[0]['time_s']
                ax.axvline(x=first_limit_time, color='lightskyblue', linestyle=':', alpha=0.7)
                ax.text(first_limit_time + time_limit*0.02, ax.get_ylim()[1]*0.9, 
                        f'Receiver Limit @{first_limit_time:.1f}s', 
                        rotation=90, fontsize=9, color='lightskyblue', alpha=0.8)
            else:
                # Show as reference line at top and add annotation
                y_max = ax.get_ylim()[1]
                ax.axhline(y=y_max*0.95, color='lightskyblue', linestyle='--', alpha=0.3, 
                          label='4. Receiver BWE Output (No Limit)', linewidth=1)
                ax.text(time_limit*0.02, y_max*0.92, 'Receiver: No Bandwidth Limit (INF)', 
                        fontsize=10, color='lightskyblue', alpha=0.8, 
                        bbox=dict(boxstyle="round,pad=0.3", facecolor="lightcyan", alpha=0.7))
                lines_plotted += 1
                print("[*] Receiver BWE: No limitation (INF), reference line plotted")

        # 5. Congestion Window Output (always show with annotation)  
        if pushback_df is not None and not pushback_df.empty:
            if 'time_s' not in pushback_df.columns:
                pushback_df = pushback_df.copy()
                pushback_df['time_s'] = (pushback_df['timestamp'] - start_time_ms) / 1000.0
            
            # Check if there's any actual pushback effect
            actual_pushback = any(pushback_df['reduction'] > 0)
            
            if actual_pushback:
                # Plot actual pushback effect
                pushback_reduced = pushback_df[pushback_df['reduction'] > 0]
                ax.plot(pushback_reduced['time_s'], pushback_reduced['pushback_rate']/1000, '-', 
                        color='mediumpurple', label='5. Congestion Window Output', linewidth=2, alpha=0.9)
                lines_plotted += 1
                print(f"[*] Congestion Window: {len(pushback_reduced)} data points with actual pushback plotted")
                
                # Mark pushback time points
                for idx, row in pushback_reduced.iterrows():
                    if idx == pushback_reduced.index[0]:  # Only mark first few
                        ax.axvline(x=row['time_s'], color='mediumpurple', linestyle=':', alpha=0.7)
                        ax.text(row['time_s'] + time_limit*0.02, ax.get_ylim()[1]*0.8, 
                                f'CWND Pushback @{row["time_s"]:.1f}s', 
                                rotation=90, fontsize=9, color='mediumpurple', alpha=0.8)
            else:
                # Show as reference line and add annotation
                ax.axhline(y=0, color='mediumpurple', linestyle='--', alpha=0.3, 
                          label='5. Congestion Window Output (No Pushback)', linewidth=1)
                ax.text(time_limit*0.7, ax.get_ylim()[1]*0.05, 'Congestion Window: No Pushback Limit', 
                        fontsize=10, color='mediumpurple', alpha=0.8, 
                        bbox=dict(boxstyle="round,pad=0.3", facecolor="plum", alpha=0.7))
                lines_plotted += 1
                print("[*] Congestion Window: No pushback occurred, reference line plotted")
        else:
            # No data available, still show reference
            ax.text(time_limit*0.7, ax.get_ylim()[1]*0.15, 'Congestion Window: Data Not Available', 
                    fontsize=10, color='mediumpurple', alpha=0.8, 
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="plum", alpha=0.7))
            print("[*] Congestion Window: No data available")

        # 6. Final BWE Output (from BWE-ConstraintApply - 7,737 points)
        if constraint_df is not None and not constraint_df.empty:
            if 'time_s' not in constraint_df.columns:
                constraint_df = constraint_df.copy()
                constraint_df['time_s'] = (constraint_df['timestamp'] - start_time_ms) / 1000.0
            ax.plot(constraint_df['time_s'], constraint_df['final']/1000, '-', 
                    color='mediumslateblue', label='6. Final BWE Output', linewidth=3, alpha=0.9)
            lines_plotted += 1
            print(f"[*] Final BWE (BWE-ConstraintApply): {len(constraint_df)} data points plotted")

        if lines_plotted == 0:
            print("[!] No lines could be plotted - no valid data found")
            return None

        # Set labels and formatting
        ax.set_ylabel('Bandwidth (kbps)', fontsize=12, fontweight='bold')
        ax.set_xlabel('Time (seconds)', fontsize=12, fontweight='bold')
        ax.set_title('WebRTC GCC Bandwidth Estimation - All Key Output Lines', 
                     fontsize=14, fontweight='bold', pad=20)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=11, loc='upper right')
        
        # Set x-axis range
        ax.set_xlim(0, time_limit)
        
        # Add statistics summary using high-density data sources
        stats_parts = []
        
        # Calculate averages from high-density sources
        if loss_df is not None and not loss_df.empty:
            avg_loss = loss_df['bandwidth'].mean() / 1000
            stats_parts.append(f'Loss BWE: {avg_loss:.0f}kbps')
        
        if delay_estimate_df is not None and not delay_estimate_df.empty:
            avg_delay = delay_estimate_df['new_target'].mean() / 1000
            avg_acked = delay_estimate_df['acked_bitrate'].mean() / 1000
            stats_parts.extend([
                f'Delay BWE: {avg_delay:.0f}kbps',
                f'Acked: {avg_acked:.0f}kbps'
            ])
        
        if constraint_df is not None and not constraint_df.empty:
            avg_final = constraint_df['final'].mean() / 1000
            stats_parts.append(f'Final BWE: {avg_final:.0f}kbps')
        
        stats_text = 'Avg ' + ' | '.join(stats_parts) if stats_parts else 'No statistics available'
        ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, fontsize=10,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", alpha=0.8),
                verticalalignment='top')
        
        plt.tight_layout(rect=[0, 0, 1, 0.94])
        plt.show()
        
        return fig

def main():
    # Input log file path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sender_log_file = os.path.join(script_dir, 'sender_local.log') 
    
    try:
        analyzer = GccDecisionAnalyzer(sender_log_file)
        data_dict = analyzer.parse_log_file()
        
        # Plot original GCC decision metrics
        fig1 = analyzer.plot_gcc_decision_metrics(data_dict)
        
        # Plot new constraint analysis
        fig2 = analyzer.plot_constraint_analysis(data_dict)
        
        output_dir = 'analysis_results'
        output_dir = os.path.join(script_dir, output_dir)
        os.makedirs(output_dir, exist_ok=True)
        
        if fig1:
            output_path1 = os.path.join(output_dir, 'gcc_decision_analysis_vertical.png')
            fig1.savefig(output_path1, dpi=150, bbox_inches='tight', facecolor='white')
            print(f"[*] Original decision chart saved to: {output_path1}")
            
        if fig2:
            output_path2 = os.path.join(output_dir, 'gcc_constraint_analysis.png')
            fig2.savefig(output_path2, dpi=150, bbox_inches='tight', facecolor='white')
            print(f"[*] Constraint analysis chart saved to: {output_path2}")

    except FileNotFoundError:
        print(f"[!] Error: File not found '{sender_log_file}'")
    except Exception as e:
        import traceback
        print(f"[!] Unknown error occurred while processing file: {e}")
        print("[!] Full traceback:")
        traceback.print_exc()

if __name__ == "__main__":
    main()
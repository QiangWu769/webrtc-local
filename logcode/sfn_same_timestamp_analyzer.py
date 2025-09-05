#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SFN Same Timestamp Gap Analyzer - Analyze SFN gaps within records that have the same RAN timestamp
Finds cases where records with identical first column timestamps have SFN gaps > 100ms
"""

import sys
import os
from collections import defaultdict

def analyze_same_timestamp_sfn_gaps(report_file, threshold_ms=100):
    """
    Analyze SFN gaps within records that have the same RAN timestamp
    
    Args:
        report_file: Path to diag_report.txt
        threshold_ms: Threshold in milliseconds to detect gaps within same timestamp (default 100ms)
    
    Returns:
        List of gap records
    """
    
    if not os.path.exists(report_file):
        print(f"Error: File {report_file} not found")
        return []
    
    # Dictionary to group records by RAN timestamp
    timestamp_groups = defaultdict(list)
    gaps_found = []
    total_records = 0
    
    print(f"Analyzing SFN gaps within same RAN timestamps in {report_file}")
    print(f"Threshold: {threshold_ms}ms")
    print("-" * 80)
    
    try:
        # First pass: Group records by RAN timestamp
        with open(report_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # Skip header line
                if line.startswith('RAN_Event_Unix_Timestamp'):
                    continue
                
                # Parse data line
                fields = line.split('\t')
                if len(fields) < 5:
                    continue
                
                try:
                    ran_timestamp = float(fields[0])  # RAN_Event_Unix_Timestamp column
                    current_sfn_sf = int(fields[4])   # Current_SFN_SF column
                    total_records += 1
                    
                    # Group by RAN timestamp
                    timestamp_groups[ran_timestamp].append({
                        'line_num': line_num,
                        'sfn_sf': current_sfn_sf,
                        'line_data': line
                    })
                    
                except (ValueError, IndexError) as e:
                    print(f"Warning: Failed to parse line {line_num}: {e}")
                    continue
        
        # Second pass: Analyze SFN gaps within each timestamp group
        same_timestamp_groups = 0
        
        for ran_timestamp, records in timestamp_groups.items():
            if len(records) > 1:  # Only analyze groups with multiple records
                same_timestamp_groups += 1
                
                # Sort records by SFN_SF value for gap analysis
                records.sort(key=lambda x: x['sfn_sf'])
                
                # Check gaps between consecutive SFN values in the same timestamp group
                for i in range(1, len(records)):
                    prev_record = records[i-1]
                    curr_record = records[i]
                    
                    # Calculate SFN difference
                    sfn_diff = curr_record['sfn_sf'] - prev_record['sfn_sf']
                    
                    # Handle SFN wraparound (SFN cycles 0-10239ms)
                    if sfn_diff < -5000:  # Likely wraparound
                        sfn_diff += 10240
                    elif sfn_diff > 5000:  # Reverse wraparound
                        sfn_diff -= 10240
                    
                    # Check if gap exceeds threshold
                    if abs(sfn_diff) > threshold_ms:
                        gap_info = {
                            'ran_timestamp': ran_timestamp,
                            'prev_record': prev_record,
                            'curr_record': curr_record,
                            'sfn_diff': sfn_diff,
                            'group_size': len(records)
                        }
                        gaps_found.append(gap_info)
                        
                        print(f"SAME-TIMESTAMP GAP FOUND:")
                        print(f"  RAN Timestamp: {ran_timestamp}")
                        print(f"  Records in group: {len(records)}")
                        print(f"  Previous SFN_SF: {prev_record['sfn_sf']} (line {prev_record['line_num']})")
                        print(f"  Current SFN_SF:  {curr_record['sfn_sf']} (line {curr_record['line_num']})")
                        print(f"  SFN difference: {sfn_diff}ms")
                        print(f"  Previous: {prev_record['line_data'][:100]}...")
                        print(f"  Current:  {curr_record['line_data'][:100]}...")
                        print()
                        
    except Exception as e:
        print(f"Error reading file: {e}")
        return gaps_found
    
    print("-" * 80)
    print(f"Analysis complete:")
    print(f"  Total records processed: {total_records}")
    print(f"  Timestamp groups with multiple records: {same_timestamp_groups}")
    print(f"  Same-timestamp gaps > {threshold_ms}ms found: {len(gaps_found)}")
    
    if gaps_found:
        print(f"\nSummary of same-timestamp gaps > {threshold_ms}ms:")
        for i, gap in enumerate(gaps_found, 1):
            print(f"  Gap #{i}: {gap['sfn_diff']}ms at timestamp {gap['ran_timestamp']}")
            print(f"    Lines: {gap['prev_record']['line_num']} -> {gap['curr_record']['line_num']}")
            print(f"    Group size: {gap['group_size']} records")
    else:
        print(f"  No same-timestamp gaps > {threshold_ms}ms detected!")
    
    return gaps_found

def analyze_timestamp_group_statistics(report_file):
    """Analyze statistics about timestamp groups"""
    
    timestamp_groups = defaultdict(list)
    
    try:
        with open(report_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#') or line.startswith('RAN_Event_Unix_Timestamp'):
                    continue
                
                fields = line.split('\t')
                if len(fields) < 5:
                    continue
                
                try:
                    ran_timestamp = float(fields[0])
                    current_sfn_sf = int(fields[4])
                    timestamp_groups[ran_timestamp].append(current_sfn_sf)
                except:
                    continue
        
        # Statistics
        single_record_groups = 0
        multi_record_groups = 0
        max_group_size = 0
        total_multi_records = 0
        
        for timestamp, sfns in timestamp_groups.items():
            if len(sfns) == 1:
                single_record_groups += 1
            else:
                multi_record_groups += 1
                total_multi_records += len(sfns)
                max_group_size = max(max_group_size, len(sfns))
        
        print("\n" + "="*50)
        print("TIMESTAMP GROUP STATISTICS")
        print("="*50)
        print(f"Total unique timestamps: {len(timestamp_groups)}")
        print(f"Single-record timestamps: {single_record_groups}")
        print(f"Multi-record timestamps: {multi_record_groups}")
        print(f"Largest group size: {max_group_size}")
        print(f"Total records in multi-record groups: {total_multi_records}")
        print(f"Average records per multi-record group: {total_multi_records/multi_record_groups if multi_record_groups > 0 else 0:.2f}")
        
        # Show some examples of large groups
        large_groups = [(ts, sfns) for ts, sfns in timestamp_groups.items() if len(sfns) > 10]
        if large_groups:
            print(f"\nLargest timestamp groups (>10 records):")
            large_groups.sort(key=lambda x: len(x[1]), reverse=True)
            for i, (ts, sfns) in enumerate(large_groups[:5]):
                print(f"  {i+1}. Timestamp {ts}: {len(sfns)} records")
                sfn_range = f"SFN range: {min(sfns)} - {max(sfns)}"
                sfn_span = max(sfns) - min(sfns)
                if sfn_span > 5000:  # Handle wraparound
                    sfn_span = min(10240 - sfn_span, sfn_span)
                print(f"     {sfn_range}, span: {sfn_span}ms")
        
    except Exception as e:
        print(f"Error analyzing timestamp groups: {e}")

def generate_same_timestamp_gap_report(gaps_found, output_file="same_timestamp_gap_report.txt"):
    """Generate detailed same-timestamp gap analysis report"""
    
    if not gaps_found:
        print("No same-timestamp gaps to report")
        return
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("Same-Timestamp SFN Gap Analysis Report\n")
            f.write("="*60 + "\n\n")
            
            f.write(f"Total same-timestamp gaps found: {len(gaps_found)}\n\n")
            
            for i, gap in enumerate(gaps_found, 1):
                f.write(f"Same-Timestamp Gap #{i}:\n")
                f.write(f"  RAN Timestamp: {gap['ran_timestamp']}\n")
                f.write(f"  SFN difference: {gap['sfn_diff']}ms\n")
                f.write(f"  Records in timestamp group: {gap['group_size']}\n")
                f.write(f"  Line range: {gap['prev_record']['line_num']} -> {gap['curr_record']['line_num']}\n")
                f.write(f"  SFN transition: {gap['prev_record']['sfn_sf']} -> {gap['curr_record']['sfn_sf']}\n")
                f.write(f"  Previous record:\n    {gap['prev_record']['line_data']}\n")
                f.write(f"  Current record:\n    {gap['curr_record']['line_data']}\n")
                f.write("\n" + "-"*50 + "\n\n")
        
        print(f"Detailed same-timestamp gap report saved to: {output_file}")
        
    except Exception as e:
        print(f"Error writing same-timestamp gap report: {e}")

def main():
    # Default file path
    report_file = "/home/wuq/webrtc-checkout/logcode/diag_report.txt"
    
    # Allow command line argument to override file path
    if len(sys.argv) > 1:
        report_file = sys.argv[1]
    
    # First, show timestamp group statistics
    analyze_timestamp_group_statistics(report_file)
    
    # Analyze same-timestamp gaps with 100ms threshold
    gaps_found = analyze_same_timestamp_sfn_gaps(report_file, threshold_ms=100)
    
    # Generate detailed report if gaps found
    if gaps_found:
        generate_same_timestamp_gap_report(gaps_found)
        
        # Also check with different thresholds for comparison
        print(f"\nComparison with other thresholds:")
        for threshold in [50, 150, 200]:
            other_gaps = analyze_same_timestamp_sfn_gaps(report_file, threshold_ms=threshold)
            print(f"  Same-timestamp gaps > {threshold}ms: {len(other_gaps)}")

if __name__ == "__main__":
    main()
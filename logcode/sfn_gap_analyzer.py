#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SFN Gap Analyzer - Analyze SFN time intervals in diag_report.txt
Finds cases where consecutive SFN values have gaps > 200ms
"""

import sys
import os

def analyze_sfn_gaps(report_file, threshold_ms=200):
    """
    Analyze SFN gaps in the diagnostic report file
    
    Args:
        report_file: Path to diag_report.txt
        threshold_ms: Threshold in milliseconds to detect gaps (default 200ms)
    
    Returns:
        List of gap records
    """
    
    if not os.path.exists(report_file):
        print(f"Error: File {report_file} not found")
        return []
    
    gaps_found = []
    prev_sfn_sf = None
    prev_line_num = 0
    total_records = 0
    
    print(f"Analyzing SFN gaps in {report_file}")
    print(f"Threshold: {threshold_ms}ms")
    print("-" * 80)
    
    try:
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
                    current_sfn_sf = int(fields[4])  # Current_SFN_SF column
                    total_records += 1
                    
                    if prev_sfn_sf is not None:
                        # Calculate time difference
                        # Note: SFN_SF wraps around every 10240ms (1024 SysFN * 10ms)
                        time_diff = current_sfn_sf - prev_sfn_sf
                        
                        # Handle SFN wraparound
                        if time_diff < -5000:  # Likely wraparound (e.g., 10200 -> 50)
                            time_diff += 10240
                        elif time_diff > 5000:  # Reverse wraparound
                            time_diff -= 10240
                        
                        # Check if gap exceeds threshold
                        if abs(time_diff) > threshold_ms:
                            gap_info = {
                                'line_num': line_num,
                                'prev_line_num': prev_line_num,
                                'prev_sfn_sf': prev_sfn_sf,
                                'current_sfn_sf': current_sfn_sf,
                                'time_diff_ms': time_diff,
                                'prev_data': prev_line,
                                'current_data': line
                            }
                            gaps_found.append(gap_info)
                            
                            print(f"GAP FOUND at line {line_num}:")
                            print(f"  Previous SFN_SF: {prev_sfn_sf} (line {prev_line_num})")
                            print(f"  Current SFN_SF:  {current_sfn_sf}")
                            print(f"  Time difference: {time_diff}ms")
                            print(f"  Previous record: {prev_line[:100]}...")
                            print(f"  Current record:  {line[:100]}...")
                            print()
                    
                    prev_sfn_sf = current_sfn_sf
                    prev_line_num = line_num
                    prev_line = line
                    
                except (ValueError, IndexError) as e:
                    print(f"Warning: Failed to parse line {line_num}: {e}")
                    continue
                    
    except Exception as e:
        print(f"Error reading file: {e}")
        return gaps_found
    
    print("-" * 80)
    print(f"Analysis complete:")
    print(f"  Total records processed: {total_records}")
    print(f"  Gaps > {threshold_ms}ms found: {len(gaps_found)}")
    
    if gaps_found:
        print(f"\nSummary of gaps > {threshold_ms}ms:")
        for i, gap in enumerate(gaps_found, 1):
            print(f"  Gap #{i}: {gap['time_diff_ms']}ms (lines {gap['prev_line_num']}->{gap['line_num']})")
    else:
        print(f"  No gaps > {threshold_ms}ms detected!")
    
    return gaps_found

def generate_gap_report(gaps_found, output_file="sfn_gap_report.txt"):
    """Generate detailed gap analysis report"""
    
    if not gaps_found:
        print("No gaps to report")
        return
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("SFN Gap Analysis Report\n")
            f.write("="*50 + "\n\n")
            
            f.write(f"Total gaps found: {len(gaps_found)}\n\n")
            
            for i, gap in enumerate(gaps_found, 1):
                f.write(f"Gap #{i}:\n")
                f.write(f"  Time difference: {gap['time_diff_ms']}ms\n")
                f.write(f"  Line range: {gap['prev_line_num']} -> {gap['line_num']}\n")
                f.write(f"  SFN_SF transition: {gap['prev_sfn_sf']} -> {gap['current_sfn_sf']}\n")
                f.write(f"  Previous record:\n    {gap['prev_data']}\n")
                f.write(f"  Current record:\n    {gap['current_data']}\n")
                f.write("\n" + "-"*50 + "\n\n")
        
        print(f"Detailed gap report saved to: {output_file}")
        
    except Exception as e:
        print(f"Error writing gap report: {e}")

def main():
    # Default file path
    report_file = "/home/wuq/webrtc-checkout/logcode/diag_report.txt"
    
    # Allow command line argument to override file path
    if len(sys.argv) > 1:
        report_file = sys.argv[1]
    
    # Analyze gaps with 200ms threshold
    gaps_found = analyze_sfn_gaps(report_file, threshold_ms=200)
    
    # Generate detailed report if gaps found
    if gaps_found:
        generate_gap_report(gaps_found)
        
        # Also check with different thresholds for comparison
        print(f"\nComparison with other thresholds:")
        for threshold in [100, 300, 500]:
            other_gaps = analyze_sfn_gaps(report_file, threshold_ms=threshold)
            print(f"  Gaps > {threshold}ms: {len(other_gaps)}")

if __name__ == "__main__":
    main()
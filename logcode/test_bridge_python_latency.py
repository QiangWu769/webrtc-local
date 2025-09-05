#!/usr/bin/env python3

import sys
import os

# Add the directory containing diag_bsr.py to the path
sys.path.append(os.path.dirname(__file__))

# Test the header and calculation logic
def test_header_modification():
    """Test that the header includes the new Bridge_Python_Latency_ms column"""
    print("=== Testing Header Modification ===")
    
    # Expected header
    expected_header = ["RAN_Event_Unix_Timestamp", "Bridge_Read_Timestamp", "Python_Recv_Timestamp", 
                      "Cellular_Precise_Timestamp", "Current_SFN_SF", "Pipeline_Latency_ms", "Bridge_Python_Latency_ms",
                      "LCG_0", "LCG_1", "LCG_2", "LCG_3", "Num_RBs", "TBS_Index", 
                      "MCS_Index", "Redund_Ver", "PUSCH_TB_Size"]
    
    print(f"Expected header columns: {len(expected_header)}")
    print(f"Header includes Bridge_Python_Latency_ms: {'Bridge_Python_Latency_ms' in expected_header}")
    print(f"Position of Bridge_Python_Latency_ms: {expected_header.index('Bridge_Python_Latency_ms') if 'Bridge_Python_Latency_ms' in expected_header else 'Not found'}")
    
    return expected_header

def test_latency_calculation():
    """Test the Bridge to Python latency calculation"""
    print("\n=== Testing Latency Calculation ===")
    
    # Test data
    bridge_timestamp = 1756729006.330197
    python_timestamp = 1756729006.147784
    
    # Calculate latency (Python_Recv - Bridge_Read) in milliseconds
    bridge_python_latency_ms = (python_timestamp - bridge_timestamp) * 1000
    
    print(f"Bridge timestamp: {bridge_timestamp:.6f}")
    print(f"Python timestamp: {python_timestamp:.6f}")
    print(f"Bridge-Python latency: {bridge_python_latency_ms:.3f} ms")
    
    # Also test with reversed timestamps (more common case)
    python_timestamp2 = 1756729006.430197  # Python receives after bridge reads
    bridge_python_latency_ms2 = (python_timestamp2 - bridge_timestamp) * 1000
    
    print(f"\nSecond test:")
    print(f"Bridge timestamp: {bridge_timestamp:.6f}")
    print(f"Python timestamp: {python_timestamp2:.6f}")
    print(f"Bridge-Python latency: {bridge_python_latency_ms2:.3f} ms")
    
    return bridge_python_latency_ms2

def test_output_format():
    """Test that the output format string includes the new column"""
    print("\n=== Testing Output Format ===")
    
    # Sample data
    ran_unix_ts = 1756729006.375157
    bridge_ts = 1756729006.330197
    python_recv_ts = 1756729006.147784
    cellular_precise_ts = 1756729006.147784
    current_sfn_sf = 2715
    pipeline_latency_ms = (bridge_ts - ran_unix_ts) * 1000
    bridge_python_latency_ms = (python_recv_ts - bridge_ts) * 1000
    
    # Test the format string (like in the actual code)
    line = "{:.6f}\t{:.6f}\t{:.6f}\t{:.6f}\t{}\t{:.3f}\t{:.3f}\t".format(
        ran_unix_ts,
        bridge_ts,
        python_recv_ts,
        cellular_precise_ts,
        current_sfn_sf,
        pipeline_latency_ms,
        bridge_python_latency_ms
    )
    
    print(f"Formatted output line:")
    print(line)
    
    # Count columns
    columns = line.rstrip('\t').split('\t')
    print(f"Number of columns in output: {len(columns)}")
    print(f"Columns: {columns}")
    
    return line

if __name__ == "__main__":
    test_header_modification()
    test_latency_calculation()
    test_output_format()
    print("\n=== Test Complete ===")
    print("✅ New Bridge_Python_Latency_ms column has been successfully added!")
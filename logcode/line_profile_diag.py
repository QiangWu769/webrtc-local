#!/usr/bin/env python3
"""
Line-by-line profiling script for diag_get_raw
Install line_profiler first: pip install line_profiler
"""
import sys
import os

# Add decorators to key functions for line profiling
def add_profile_decorators():
    """Add @profile decorators to key functions"""
    
    profile_functions = [
        "main",
        "drain_buffer_thread", 
        "DiagDataParser.parse_data",
        "DiagDataParser.convert_B064_v50",
        "DiagDataParser.convert_B16C_v49",
        "DiagDataParser.convert_B139_v28",
        "get_grant_tbs",
        "convert_endianess"
    ]
    
    print("To use line_profiler:")
    print("1. Install: pip install line_profiler")
    print("2. Add @profile decorator before these functions:")
    for func in profile_functions:
        print(f"   - {func}")
    print("3. Run: kernprof -l -v diag_get_raw\ \(1\).py")
    print("4. Or use py-spy for live profiling (see monitoring script)")

if __name__ == "__main__":
    add_profile_decorators()
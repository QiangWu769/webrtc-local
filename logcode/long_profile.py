#!/usr/bin/env python3
import cProfile
import pstats
import subprocess
import signal
import time
import os

def run_long_profile():
    """Run the diagnostic script with profiling for longer period"""
    print("[PROFILE] Starting LONG profiling session (30 seconds)...")
    
    prof_file = 'diag_long_profile.prof'
    
    # Run the command with cProfile
    profile_cmd = ['python3', '-m', 'cProfile', '-o', prof_file, 'diag_get_raw (1).py']
    
    try:
        # Start process
        process = subprocess.Popen(profile_cmd, 
                                 stdout=subprocess.PIPE, 
                                 stderr=subprocess.PIPE,
                                 text=True)
        
        # Let it run for 30 seconds to capture real data processing
        print("[PROFILE] Collecting data for 30 seconds...")
        for i in range(30):
            time.sleep(1)
            if process.poll() is not None:
                break
            print(f"\r[PROFILE] Running... {i+1}/30s", end='', flush=True)
        
        print("\n[PROFILE] Terminating process...")
        
        # Terminate the process
        process.terminate()
        time.sleep(2)
        
        # Force kill if still running
        if process.poll() is None:
            process.kill()
        
        # Wait for completion
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
        
        print("[PROFILE] Process terminated, analyzing results...")
        
        # Load and analyze the profile
        if os.path.exists(prof_file):
            stats = pstats.Stats(prof_file)
            
            print("\n" + "="*80)
            print("PERFORMANCE ANALYSIS - TOP CPU CONSUMING FUNCTIONS")
            print("="*80)
            
            # Filter out import and setup functions, focus on runtime
            print("\nTOP FUNCTIONS BY TOTAL TIME (excluding imports/setup):")
            print("-" * 60)
            stats.sort_stats('tottime')
            stats.print_stats('diag_get_raw', 30)  # Show functions from our script
            
            print("\nTOP FUNCTIONS BY CUMULATIVE TIME (excluding imports/setup):")  
            print("-" * 60)
            stats.sort_stats('cumulative') 
            stats.print_stats('diag_get_raw', 20)  # Show functions from our script
            
            # Show I/O related functions
            print("\nI/O RELATED FUNCTIONS:")
            print("-" * 60)
            stats.print_stats('socket|read|write|recv|send', 15)
            
            # Show parsing related functions 
            print("\nDATA PROCESSING FUNCTIONS:")
            print("-" * 60)
            stats.print_stats('parse|convert|process|buffer', 15)
            
            print(f"\n[PROFILE] Detailed profile saved to {prof_file}")
            print("[PROFILE] For interactive analysis run:")
            print(f"    python3 -m pstats {prof_file}")
            print("    Then use commands like: stats 10, sort tottime, etc.")
        else:
            print(f"[ERROR] Profile file {prof_file} not found")
            
    except Exception as e:
        print(f"[ERROR] Profiling failed: {e}")
        if 'process' in locals():
            try:
                process.kill()
            except:
                pass

if __name__ == "__main__":
    os.chdir('/home/wuq/webrtc-local/logcode')
    run_long_profile()
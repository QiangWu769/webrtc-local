#!/usr/bin/env python3
import pstats

def analyze_profile(prof_file):
    """Analyze the cProfile output file"""
    print(f"Analyzing profile: {prof_file}")
    print("=" * 80)
    
    # Load stats
    stats = pstats.Stats(prof_file)
    
    print("\n1. TOP FUNCTIONS BY TOTAL TIME:")
    print("-" * 50)
    stats.sort_stats('tottime')
    stats.print_stats(20)
    
    print("\n2. TOP FUNCTIONS BY CUMULATIVE TIME:")
    print("-" * 50)
    stats.sort_stats('cumulative')
    stats.print_stats(20)
    
    print("\n3. FUNCTIONS FROM diag_get_raw:")
    print("-" * 50)
    stats.print_stats('diag_get_raw')
    
    print("\n4. I/O OPERATIONS:")
    print("-" * 50)
    stats.print_stats('recv|send|read|write|socket')
    
    print("\n5. ASYNC OPERATIONS:")
    print("-" * 50)
    stats.print_stats('asyncio')
    
    # Summary
    total_calls = stats.total_calls
    total_time = stats.total_tt
    print(f"\nSUMMARY:")
    print(f"Total function calls: {total_calls:,}")
    print(f"Total time: {total_time:.3f} seconds")

if __name__ == "__main__":
    analyze_profile('diag_async_profile.prof')
#!/usr/bin/env python3

import pandas as pd
import numpy as np
from process_matched_ratio import process_ratio_data

def debug_timeline():
    """Debug the timeline data to see why only first part shows"""

    timeline_ttis, matched_ratios, smoothed_ratios, original_data = process_ratio_data()

    print(f"Timeline data points: {len(timeline_ttis)}")
    print(f"Original data points: {len(original_data)}")

    if timeline_ttis:
        print(f"\nTimeline TTI range: {min(timeline_ttis)} to {max(timeline_ttis)}")
        print(f"First 10 timeline TTIs: {timeline_ttis[:10]}")
        print(f"Last 10 timeline TTIs: {timeline_ttis[-10:]}")

        # 检查TTI分布
        tti_array = np.array(timeline_ttis)
        print(f"\nTTI statistics:")
        print(f"  Unique TTIs: {len(np.unique(tti_array))}")
        print(f"  Mean: {np.mean(tti_array):.1f}")
        print(f"  Std: {np.std(tti_array):.1f}")

        # 检查时间转换
        def convert_tti_simple(tti_values):
            continuous_tti = []
            offset = 0
            prev_tti = tti_values[0]

            for tti in tti_values:
                if tti < prev_tti - 5000:
                    offset += 10240
                continuous_tti.append(tti + offset)
                prev_tti = tti

            time_s = np.array(continuous_tti) * 0.001
            return time_s - time_s[0]

        time_values = convert_tti_simple(timeline_ttis)
        print(f"\nTime conversion:")
        print(f"  Time range: {time_values[0]:.3f} to {time_values[-1]:.3f} seconds")
        print(f"  Duration: {time_values[-1] - time_values[0]:.3f} seconds")

        # 检查数据密度
        time_bins = np.arange(0, time_values[-1] + 10, 10)  # 10秒为一个bin
        hist, _ = np.histogram(time_values, bins=time_bins)
        print(f"\nData distribution per 10-second intervals:")
        for i, count in enumerate(hist[:10]):  # 前10个bin
            print(f"  {i*10}-{(i+1)*10}s: {count} points")

if __name__ == "__main__":
    debug_timeline()
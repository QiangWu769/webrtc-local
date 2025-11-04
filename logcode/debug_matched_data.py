#!/usr/bin/env python3

import pandas as pd
import numpy as np
from process_matched_ratio import RequestAllocationMatcher

def debug_matched_data():
    """Debug the matched data to see why timeline is still short"""

    # 读取原始数据
    data = []
    with open('/home/wuq/webrtc-local/logcode/ratio_data.txt', 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                parts = line.split('\t')
                if len(parts) == 4:
                    tti = int(parts[0])
                    allocated = int(parts[1])
                    requested = int(parts[2])
                    original_ratio = float(parts[3])
                    data.append((tti, allocated, requested, original_ratio))

    print(f"Original data: {len(data)} points")
    print(f"Original TTI range: {min(d[0] for d in data)} to {max(d[0] for d in data)}")

    # 创建匹配器并处理数据
    matcher = RequestAllocationMatcher(max_delay_tti=5, timeout_tti=10)

    # 按原始时间顺序处理数据（不排序）
    for tti, allocated, requested, _ in data:
        matcher.process_tti(tti, allocated, requested)

    print(f"Generated {len(matcher.matched_ratios)} matched records")

    # 检查匹配数据的TTI分布
    grant_ttis = []
    request_ttis = []

    for record in matcher.matched_ratios:
        if record['grant_tti'] is not None:
            grant_ttis.append(record['grant_tti'])
        if record['request_tti'] is not None:
            request_ttis.append(record['request_tti'])

    print(f"\nMatched data TTI analysis:")
    print(f"Grant TTIs: {len(grant_ttis)} records")
    if grant_ttis:
        print(f"  Grant TTI range: {min(grant_ttis)} to {max(grant_ttis)}")

    print(f"Request TTIs: {len(request_ttis)} records")
    if request_ttis:
        print(f"  Request TTI range: {min(request_ttis)} to {max(request_ttis)}")

    # 创建时间轴数据
    timeline_data = []
    for record in matcher.matched_ratios:
        timeline_tti = record['grant_tti'] if record['grant_tti'] is not None else record['request_tti']
        if timeline_tti is not None:
            timeline_data.append((timeline_tti, record['ratio']))

    timeline_data.sort(key=lambda x: x[0])
    timeline_ttis, timeline_ratios = zip(*timeline_data)

    print(f"\nTimeline data:")
    print(f"Timeline TTIs: {len(timeline_ttis)} records")
    print(f"Timeline TTI range: {min(timeline_ttis)} to {max(timeline_ttis)}")

    # 检查时间转换
    def convert_tti_debug(tti_values):
        continuous_tti = []
        offset = 0
        prev_tti = tti_values[0]
        wrap_count = 0

        for i, tti in enumerate(tti_values):
            if tti < prev_tti - 5000:
                offset += 10240
                wrap_count += 1
                print(f"  Wrap {wrap_count} at index {i}: TTI {prev_tti} -> {tti}, offset: {offset}")

            continuous_tti.append(tti + offset)
            prev_tti = tti

        time_s = np.array(continuous_tti) * 0.001
        time_s = time_s - time_s[0]
        return time_s

    print(f"\nTime conversion for timeline data:")
    time_values = convert_tti_debug(timeline_ttis)
    print(f"Time range: {time_values[0]:.3f} to {time_values[-1]:.3f} seconds")
    print(f"Duration: {time_values[-1] - time_values[0]:.3f} seconds")

    # 检查匹配过程是否导致数据丢失
    print(f"\nData comparison:")
    print(f"Original data points: {len(data)}")
    print(f"Matched records: {len(matcher.matched_ratios)}")
    print(f"Timeline points: {len(timeline_ttis)}")

if __name__ == "__main__":
    debug_matched_data()
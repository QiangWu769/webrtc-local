#!/usr/bin/env python3

import re
import numpy as np
from typing import List, Tuple
import matplotlib.pyplot as plt
from dataclasses import dataclass

@dataclass
class OverusingEvent:
    timestamp: float
    context_before: List[Tuple[float, float]]  # (time, ratio) 100 points before
    context_after: List[Tuple[float, float]]   # (time, ratio) 20 points after

def parse_log_data(log_file: str):
    """解析日志数据，提取ratio和overusing事件"""
    ratio_data = []
    overusing_events = []
    
    with open(log_file, 'r') as f:
        for line in f:
            line = line.strip()
            
            # 提取ratio数据
            ratio_match = re.search(r'\[(\d+\.\d+)\].*CellularRatioReceiver.*ratio:\s*([\d.]+)', line)
            if ratio_match:
                timestamp = float(ratio_match.group(1))
                ratio = float(ratio_match.group(2))
                ratio_data.append((timestamp, ratio))
            
            # 提取overusing事件
            overusing_match = re.search(r'\[(\d+\.\d+)\].*kBwOverusing', line)
            if overusing_match:
                timestamp = float(overusing_match.group(1))
                overusing_events.append(timestamp)
    
    return ratio_data, overusing_events

def analyze_overusing_context(ratio_data: List[Tuple[float, float]], 
                            overusing_events: List[float]) -> List[OverusingEvent]:
    """分析每个overusing事件前后的ratio上下文"""
    events_with_context = []
    
    for event_time in overusing_events:
        # 找到事件前100个数据点
        before_data = []
        after_data = []
        
        for i, (timestamp, ratio) in enumerate(ratio_data):
            if timestamp < event_time:
                before_data.append((timestamp, ratio))
                # 只保留最近的100个点
                if len(before_data) > 100:
                    before_data.pop(0)
            elif timestamp >= event_time:
                after_data.append((timestamp, ratio))
                # 只要20个点就够了
                if len(after_data) >= 20:
                    break
        
        if len(before_data) >= 50:  # 至少要有50个点才分析
            events_with_context.append(OverusingEvent(
                timestamp=event_time,
                context_before=before_data,
                context_after=after_data
            ))
    
    return events_with_context

def calculate_linear_regression(data_points: List[Tuple[float, float]]) -> Tuple[float, float, float]:
    """计算线性回归的斜率、R²和置信度"""
    if len(data_points) < 10:
        return 0.0, 0.0, 0.0
    
    times = np.array([t for t, _ in data_points])
    ratios = np.array([r for _, r in data_points])
    
    # 转换为相对时间
    time_relative = times - times[0]
    
    # 线性回归
    n = len(time_relative)
    x_mean = np.mean(time_relative)
    y_mean = np.mean(ratios)
    
    numerator = np.sum((time_relative - x_mean) * (ratios - y_mean))
    denominator = np.sum((time_relative - x_mean) ** 2)
    
    if denominator < 1e-10:
        return 0.0, 0.0, 0.0
    
    slope = numerator / denominator
    intercept = y_mean - slope * x_mean
    
    # 计算R²
    y_pred = slope * time_relative + intercept
    ss_tot = np.sum((ratios - y_mean) ** 2)
    ss_res = np.sum((ratios - y_pred) ** 2)
    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-10 else 0.0
    
    return slope, r_squared, abs(slope) * np.std(time_relative)

def analyze_prediction_failure():
    """分析预测失败的具体原因"""
    log_file = "/home/wuq/webrtc-local/webrtc_config_results/6sender_local.log"
    
    print("解析日志数据...")
    ratio_data, overusing_events = parse_log_data(log_file)
    
    print(f"找到 {len(ratio_data)} 个ratio数据点")
    print(f"找到 {len(overusing_events)} 个overusing事件")
    
    print("\nOverusing事件时间戳:")
    for i, event_time in enumerate(overusing_events):
        print(f"  事件 {i+1}: {event_time:.3f}s")
    
    # 分析每个事件的上下文
    events_with_context = analyze_overusing_context(ratio_data, overusing_events)
    
    print(f"\n成功分析 {len(events_with_context)} 个事件的上下文")
    
    # 分析每个事件前的线性回归特征
    print("\n各事件前100点的线性回归分析:")
    print("事件# | 时间戳 | 斜率(/s) | R² | 平均ratio | ratio变化范围")
    print("-" * 70)
    
    for i, event in enumerate(events_with_context):
        slope, r_squared, confidence = calculate_linear_regression(event.context_before)
        
        ratios = [r for _, r in event.context_before]
        avg_ratio = np.mean(ratios)
        min_ratio = np.min(ratios)
        max_ratio = np.max(ratios)
        ratio_range = max_ratio - min_ratio
        
        # 判断是否应该预测到
        should_predict = slope < -0.1 and r_squared > 0.3  # 我们的阈值
        
        print(f"事件{i+1:2d} | {event.timestamp:7.3f} | {slope:8.4f} | {r_squared:4.2f} | {avg_ratio:8.3f} | {ratio_range:8.3f} | {'✓' if should_predict else '✗'}")
        
        # 如果是第2-4个事件（预测失败的），详细分析
        if i >= 1 and i <= 3:
            print(f"    详细分析事件{i+1}:")
            print(f"    - 事件前最后10个ratio值: {[f'{r:.3f}' for _, r in event.context_before[-10:]]}")
            print(f"    - 斜率 {slope:.4f} {'<' if slope < -0.1 else '>='} -0.1 (阈值)")
            print(f"    - R² {r_squared:.3f} {'>' if r_squared > 0.3 else '<='} 0.3 (阈值)")
            
            # 分析最后50点和最后20点的趋势差异
            if len(event.context_before) >= 50:
                slope_50, r2_50, _ = calculate_linear_regression(event.context_before[-50:])
                slope_20, r2_20, _ = calculate_linear_regression(event.context_before[-20:])
                print(f"    - 最后50点: 斜率={slope_50:.4f}, R²={r2_50:.3f}")
                print(f"    - 最后20点: 斜率={slope_20:.4f}, R²={r2_20:.3f}")
            print()

if __name__ == "__main__":
    analyze_prediction_failure()
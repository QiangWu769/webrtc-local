#!/usr/bin/env python3

import re
import numpy as np
import pandas as pd
from typing import List, Tuple

def parse_log_data(log_file: str):
    """解析日志数据 - 采用与plot_ratio_trend.py相同的方法"""
    ratio_data = []
    overusing_events = []
    start_time = None
    start_mono = None
    
    with open(log_file, 'r') as f:
        for line in f:
            line = line.strip()
            
            # 找到第一个wallclock时间戳作为基准时间
            if start_time is None:
                time_match = re.search(r'\[([0-9]{10}\.[0-9]{3,6})\]', line)
                if time_match:
                    start_time = float(time_match.group(1))
            
            # 解析ratio数据 - 使用MonoTime转换
            ratio_match = re.search(r'CellularRatio.*MonoTime:\s*(\d+).*Ratio:\s*([\d.]+)', line)
            if ratio_match:
                mono_time_ms = float(ratio_match.group(1))
                ratio = float(ratio_match.group(2))
                # 将MonoTime转换为相对时间(秒) - 基于第一个MonoTime
                if start_mono is None:  # 第一个ratio数据作为基准
                    start_mono = mono_time_ms
                relative_time = (mono_time_ms - start_mono) / 1000.0
                ratio_data.append((relative_time, ratio))
            
            # 解析overusing事件 - 使用wallclock时间戳
            overusing_match = re.search(r'\[([0-9]{10}\.[0-9]{3,6})\].*State: Overusing', line)
            if overusing_match:
                wall_time = float(overusing_match.group(1))
                if start_time is not None:
                    relative_time = wall_time - start_time  # 转换为相对时间(秒)
                    overusing_events.append(relative_time)
    
    return ratio_data, overusing_events

def calculate_cusum(ratio_series, target_ratio=0.3, k=0.1, h=5.0):
    """计算CUSUM统计量"""
    cusum_upper = []
    cusum_lower = []
    alerts_upper = []
    alerts_lower = []
    
    s_upper = 0.0
    s_lower = 0.0
    
    for ratio in ratio_series:
        # 上侧CUSUM
        s_upper = max(0, s_upper + (ratio - target_ratio - k))
        cusum_upper.append(s_upper)
        
        # 下侧CUSUM  
        s_lower = max(0, s_lower - (ratio - target_ratio - k))
        cusum_lower.append(s_lower)
        
        # 检查报警
        alerts_upper.append(s_upper > h)
        alerts_lower.append(s_lower > h)
    
    return {
        'cusum_upper': np.array(cusum_upper),
        'cusum_lower': np.array(cusum_lower), 
        'alerts_upper': np.array(alerts_upper),
        'alerts_lower': np.array(alerts_lower)
    }

def analyze_cusum_vs_overusing():
    """分析CUSUM预警与overusing事件的关系"""
    log_file = "6sender_local.log"
    ratio_data, overusing_events = parse_log_data(log_file)
    
    if not ratio_data:
        print("没有找到ratio数据")
        return
    
    # 转换数据 - ratio_data已经是(relative_time, ratio)格式
    df = pd.DataFrame(ratio_data, columns=['time_s', 'ratio'])
    
    # overusing事件时间戳已经是相对时间(秒)
    overusing_times = overusing_events
    
    print("=" * 60)
    print("CUSUM预警 vs Overusing事件分析")
    print("=" * 60)
    
    print(f"数据概述:")
    print(f"• 总ratio数据点: {len(df)}")
    print(f"• 时间范围: 0.0 - {df['time_s'].max():.1f}秒")
    print(f"• Overusing事件数: {len(overusing_times)}")
    
    if len(overusing_times) > 0:
        print(f"• 第一个overusing事件: {overusing_times[0]:.1f}秒")
        print(f"• 最后一个overusing事件: {overusing_times[-1]:.1f}秒")
    
    # 计算CUSUM
    cusum_results = calculate_cusum(df['ratio'])
    
    # 找到CUSUM报警时间点
    lower_alert_indices = np.where(cusum_results['alerts_lower'])[0]
    upper_alert_indices = np.where(cusum_results['alerts_upper'])[0]
    
    lower_alert_times = df['time_s'].iloc[lower_alert_indices].values if len(lower_alert_indices) > 0 else []
    upper_alert_times = df['time_s'].iloc[upper_alert_indices].values if len(upper_alert_indices) > 0 else []
    
    print(f"\nCUSUM预警统计:")
    print(f"• 下侧报警(低ratio)次数: {len(lower_alert_times)}")
    print(f"• 上侧报警(高ratio)次数: {len(upper_alert_times)}")
    
    if len(lower_alert_times) > 0:
        print(f"• 第一个下侧报警: {lower_alert_times[0]:.1f}秒")
        print(f"• 最后一个下侧报警: {lower_alert_times[-1]:.1f}秒")
    
    # 分析每个overusing事件的预警情况
    print("\n" + "=" * 60)
    print("详细分析: CUSUM预警 vs Overusing事件")
    print("=" * 60)
    
    for i, overusing_time in enumerate(overusing_times[:10]):  # 分析前10个事件
        print(f"\n▶ Overusing事件 #{i+1}: {overusing_time:.1f}秒")
        
        # 查找此次overusing前的CUSUM预警
        prior_lower_alerts = lower_alert_times[lower_alert_times < overusing_time]
        prior_upper_alerts = upper_alert_times[upper_alert_times < overusing_time]
        
        # 找到最近的预警
        if len(prior_lower_alerts) > 0:
            latest_lower_alert = prior_lower_alerts[-1]
            lead_time = overusing_time - latest_lower_alert
            print(f"  • 最近的下侧CUSUM预警: {latest_lower_alert:.1f}秒")
            print(f"  • 预警提前时间: {lead_time:.1f}秒")
            
            if lead_time <= 10.0:
                print(f"  ✅ 有效预警 (提前{lead_time:.1f}秒)")
            elif lead_time <= 30.0:
                print(f"  ⚠️  早期预警 (提前{lead_time:.1f}秒)")
            else:
                print(f"  ❌ 预警过早 (提前{lead_time:.1f}秒)")
        else:
            print(f"  ❌ 无CUSUM下侧预警")
        
        if len(prior_upper_alerts) > 0:
            latest_upper_alert = prior_upper_alerts[-1]
            print(f"  • 最近的上侧CUSUM预警: {latest_upper_alert:.1f}秒")
        
        # 查找此时间点前后的ratio值变化
        time_window = 5.0  # 前后5秒
        mask = (df['time_s'] >= overusing_time - time_window) & (df['time_s'] <= overusing_time + time_window)
        window_data = df[mask]
        
        if len(window_data) > 0:
            before_mask = window_data['time_s'] <= overusing_time
            after_mask = window_data['time_s'] > overusing_time
            
            before_data = window_data[before_mask]
            after_data = window_data[after_mask]
            
            if len(before_data) > 0:
                avg_ratio_before = before_data['ratio'].mean()
                min_ratio_before = before_data['ratio'].min()
                print(f"  • 事件前5s平均ratio: {avg_ratio_before:.3f}")
                print(f"  • 事件前5s最低ratio: {min_ratio_before:.3f}")
    
    # 计算总体预警效果
    print("\n" + "=" * 60)
    print("CUSUM预警效果总结")
    print("=" * 60)
    
    successful_predictions = 0
    early_warnings = 0
    missed_events = 0
    false_alarms = 0
    
    for overusing_time in overusing_times:
        prior_alerts = lower_alert_times[lower_alert_times < overusing_time]
        if len(prior_alerts) > 0:
            lead_time = overusing_time - prior_alerts[-1]
            if lead_time <= 10.0:
                successful_predictions += 1
            elif lead_time <= 30.0:
                early_warnings += 1
        else:
            missed_events += 1
    
    # 统计可能的误报（CUSUM报警后30秒内没有overusing）
    for alert_time in lower_alert_times:
        subsequent_overusing = [t for t in overusing_times if alert_time < t <= alert_time + 30.0]
        if len(subsequent_overusing) == 0:
            false_alarms += 1
    
    total_overusing = len(overusing_times)
    
    print(f"预警性能指标:")
    print(f"• 成功预警 (≤10s提前): {successful_predictions}/{total_overusing} ({successful_predictions/total_overusing*100:.1f}%)")
    print(f"• 早期预警 (10-30s提前): {early_warnings}/{total_overusing} ({early_warnings/total_overusing*100:.1f}%)")
    print(f"• 漏检事件: {missed_events}/{total_overusing} ({missed_events/total_overusing*100:.1f}%)")
    print(f"• 可能误报: {false_alarms}")
    print(f"• 总体预警率: {(successful_predictions + early_warnings)/total_overusing*100:.1f}%")
    
    # CUSUM参数建议
    print(f"\n当前CUSUM参数:")
    print(f"• 目标ratio: 0.3")
    print(f"• 参考值k: 0.1") 
    print(f"• 报警阈值h: 5.0")
    
    if successful_predictions / total_overusing < 0.5:
        print(f"\n💡 优化建议:")
        print(f"• 考虑降低报警阈值h (当前5.0 → 建议3.0-4.0)")
        print(f"• 考虑调整目标ratio (当前0.3 → 建议0.4-0.5)")
        print(f"• 考虑减小参考值k (当前0.1 → 建议0.05)")

if __name__ == "__main__":
    analyze_cusum_vs_overusing()
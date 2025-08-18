#!/usr/bin/env python3
"""
验证传输时间检测脚本
"""

import sys
sys.path.append('webrtc_config_results/analysis_code')

from analyze_congestion_control import CongestionControlAnalyzer
import matplotlib
matplotlib.use('Agg')

def analyze_transmission_timing(log_file):
    """分析传输时间"""
    print(f"分析文件: {log_file}")
    print("=" * 50)
    
    analyzer = CongestionControlAnalyzer(log_file)
    analyzer.parse_log_file()
    
    if not analyzer.gcc_output:
        print("❌ 没有GCC输出数据")
        return
    
    # 计算时间和带宽数据
    gcc_times = [analyzer._ms_to_seconds(item['timestamp']) for item in analyzer.gcc_output]
    gcc_rates = [item['final_bps'] for item in analyzer.gcc_output]
    
    print(f"📊 GCC数据点: {len(analyzer.gcc_output)} 个")
    print(f"📅 总时间跨度: {gcc_times[0]:.1f}s - {gcc_times[-1]:.1f}s ({gcc_times[-1] - gcc_times[0]:.1f}s)")
    print(f"📈 带宽范围: {min(gcc_rates)/1000:.0f} - {max(gcc_rates)/1000:.0f} kbps")
    
    # 检测传输开始时间
    transmission_start = None
    for i in range(1, len(gcc_rates)):
        if gcc_rates[i] > gcc_rates[0] * 2:
            transmission_start = gcc_times[i] - 0.5
            print(f"🟢 检测到传输开始: {transmission_start:.1f}s (带宽从 {gcc_rates[0]/1000:.0f} 增长到 {gcc_rates[i]/1000:.0f} kbps)")
            break
    
    # 检测传输结束时间
    transmission_end = None
    if transmission_start is not None:
        for i in range(len(gcc_rates)-1, 0, -1):
            if gcc_rates[i] < gcc_rates[i-1] * 0.5:
                transmission_end = gcc_times[i] + 0.5
                print(f"🔴 检测到传输结束: {transmission_end:.1f}s (带宽从 {gcc_rates[i-1]/1000:.0f} 下降到 {gcc_rates[i]/1000:.0f} kbps)")
                break
        
        if transmission_end is None:
            transmission_end = transmission_start + 5.0
            print(f"🔴 使用默认传输结束: {transmission_end:.1f}s (开始时间 + 5秒)")
    
    # 总结
    if transmission_start and transmission_end:
        detected_duration = transmission_end - transmission_start
        print(f"\n📋 传输阶段总结:")
        print(f"  ⏰ 检测的传输时间: {detected_duration:.1f}s")
        print(f"  ⚙️  配置的传输时间: 5.0s")
        print(f"  🔧 连接建立时间: ~{transmission_start:.1f}s")
        print(f"  🔚 连接关闭时间: ~{gcc_times[-1] - transmission_end:.1f}s")
    
    # 显示详细的GCC数据
    print(f"\n📈 详细GCC时间线:")
    for i, (time, rate) in enumerate(zip(gcc_times, gcc_rates)):
        print(f"  {i+1:2d}. {time:5.1f}s -> {rate/1000:6.0f} kbps")

def main():
    """主函数"""
    log_files = [
        'webrtc_config_results/sender.log',
        'webrtc_config_results/receiver.log'
    ]
    
    for log_file in log_files:
        try:
            analyze_transmission_timing(log_file)
            print("\n" + "=" * 80 + "\n")
        except Exception as e:
            print(f"❌ 分析失败: {e}")

if __name__ == "__main__":
    main()
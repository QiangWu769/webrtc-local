# -*- coding: utf-8 -*-
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import sys

def calculate_cellular_time_order(df):
    """
    基于蜂窝网络时间结构计算精确的时间顺序
    SysFN: 0-1023 (系统帧号，每10ms递增)
    SubFN: 0-9 (子帧号，每1ms递增)
    """
    # 计算相对时间偏移(ms) = SysFN * 10 + SubFN * 1
    df['cellular_time_ms'] = df['SysFN'] * 10 + df['SubFN'] * 1
    
    # 处理SysFN的循环(0-1023)
    # 如果SysFN有跳跃，说明可能有循环
    df = df.sort_values('RAN_Event_Unix_Timestamp').reset_index(drop=True)
    
    # 为了处理SysFN循环，我们基于Unix时间戳分组
    grouped = df.groupby('RAN_Event_Unix_Timestamp')
    
    refined_data = []
    for timestamp, group in grouped:
        # 在同一Unix时间戳内，按cellular_time_ms排序
        group_sorted = group.sort_values('cellular_time_ms').copy()
        
        # 添加细粒度时间戳 (基于蜂窝网络时间)
        for i, (_, row) in enumerate(group_sorted.iterrows()):
            row_dict = row.to_dict()
            # 在Unix时间戳基础上添加毫秒级偏移
            row_dict['precise_timestamp'] = timestamp + (row['cellular_time_ms'] % 10240) / 1000.0
            row_dict['event_order_in_timestamp'] = i
            refined_data.append(row_dict)
    
    return pd.DataFrame(refined_data)

def visualize_cellular_timing(report_file="diag_report.txt"):
    """
    基于蜂窝网络时间结构的可视化
    """
    try:
        # 读取数据
        df = pd.read_csv(report_file, sep='\t')
        print("原始数据: {} 个事件".format(len(df)))
        
        # 计算精确的蜂窝网络时间顺序
        df_refined = calculate_cellular_time_order(df)
        print("处理后数据: {} 个事件".format(len(df_refined)))
        
        # 创建可视化
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('蜂窝网络时间精度事件分析 (SysFN + SubFN)', fontsize=16)
        
        # 图1: 蜂窝时间轴上的事件分布
        colors = plt.cm.tab10(df_refined['SubFN'] / 9.0)  # 按SubFN着色
        scatter1 = ax1.scatter(df_refined['cellular_time_ms'], df_refined['SysFN'], 
                              c=colors, alpha=0.6, s=15)
        ax1.set_xlabel('蜂窝时间 (ms) = SysFN*10 + SubFN*1')
        ax1.set_ylabel('SysFN (系统帧号)')
        ax1.set_title('事件在蜂窝时间轴上的分布')
        ax1.grid(True, alpha=0.3)
        
        # 添加SubFN颜色说明
        for subfn in range(10):
            ax1.scatter([], [], c=plt.cm.tab10(subfn/9.0), label='SubFN {}'.format(subfn), s=30)
        ax1.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
        
        # 图2: 同一时间戳内的事件细分
        # 选择几个有多个事件的时间戳进行详细展示
        timestamp_counts = df_refined.groupby('RAN_Event_Unix_Timestamp').size()
        multi_event_timestamps = timestamp_counts[timestamp_counts > 1].head(5)
        
        colors_subfn = plt.cm.Set1(np.linspace(0, 1, 10))
        y_pos = 0
        timestamp_y_map = {}
        
        for timestamp in multi_event_timestamps.index:
            events = df_refined[df_refined['RAN_Event_Unix_Timestamp'] == timestamp].sort_values('cellular_time_ms')
            timestamp_y_map[timestamp] = y_pos
            
            for _, event in events.iterrows():
                ax2.scatter(event['cellular_time_ms'], y_pos, 
                           c=[colors_subfn[int(event['SubFN'])]], s=60, alpha=0.8)
                # 标注SysFN
                ax2.text(event['cellular_time_ms'], y_pos + 0.1, 
                        'SF{}'.format(int(event['SysFN'])), 
                        fontsize=6, ha='center')
            y_pos += 1
        
        ax2.set_xlabel('蜂窝时间 (ms)')
        ax2.set_ylabel('时间戳组')
        ax2.set_title('同一Unix时间戳内的事件细分 (前5组)')
        ax2.set_yticks(list(timestamp_y_map.values()))
        ax2.set_yticklabels(['TS{}'.format(i+1) for i in range(len(timestamp_y_map))])
        ax2.grid(True, alpha=0.3)
        
        # 图3: SubFN的时间分布模式
        subfn_time_data = []
        for subfn in range(10):
            subfn_events = df_refined[df_refined['SubFN'] == subfn]
            if len(subfn_events) > 0:
                subfn_time_data.extend([subfn] * len(subfn_events))
        
        ax3.hist(subfn_time_data, bins=10, alpha=0.7, color='lightblue', edgecolor='black')
        ax3.set_xlabel('SubFN (子帧号)')
        ax3.set_ylabel('事件计数')
        ax3.set_title('SubFN分布 (每1ms递增)')
        ax3.set_xticks(range(10))
        ax3.grid(True, alpha=0.3)
        
        # 图4: SysFN的循环模式
        ax4.hist(df_refined['SysFN'], bins=50, alpha=0.7, color='lightgreen', edgecolor='black')
        ax4.set_xlabel('SysFN (系统帧号)')
        ax4.set_ylabel('事件计数')
        ax4.set_title('SysFN分布 (0-1023循环，每10ms递增)')
        ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # 保存图表
        output_file = report_file.replace('.txt', '_cellular_timing.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print("蜂窝时间分析图保存为: {}".format(output_file))
        
        # 显示时间精度分析
        print("\n=== 蜂窝网络时间精度分析 ===")
        print("SysFN范围: {} - {} (系统帧号，每10ms递增)".format(
            df_refined['SysFN'].min(), df_refined['SysFN'].max()))
        print("SubFN范围: {} - {} (子帧号，每1ms递增)".format(
            df_refined['SubFN'].min(), df_refined['SubFN'].max()))
        
        # 分析同一时间戳内的事件数量
        same_timestamp_counts = df_refined.groupby('RAN_Event_Unix_Timestamp').size()
        print("同一Unix时间戳的最大事件数: {}".format(same_timestamp_counts.max()))
        print("有多个事件的时间戳数量: {}".format(sum(same_timestamp_counts > 1)))
        
        # 展示几个同时间戳事件的详细信息
        print("\n=== 同一时间戳内事件的蜂窝时间细分 ===")
        for i, (timestamp, events) in enumerate(df_refined.groupby('RAN_Event_Unix_Timestamp')):
            if len(events) > 1 and i < 3:  # 只显示前3组
                events_sorted = events.sort_values('cellular_time_ms')
                print("\nUnix时间戳 {:.6f}:".format(timestamp))
                for _, event in events_sorted.iterrows():
                    cellular_time = event['SysFN'] * 10 + event['SubFN']
                    print("  SysFN={:4d}, SubFN={}, 蜂窝时间={}ms, LCG=[{},{},{},{}], RBs={}".format(
                        int(event['SysFN']), int(event['SubFN']), cellular_time,
                        event['LCG_0'], event['LCG_1'], event['LCG_2'], event['LCG_3'], 
                        event['Num_RBs']))
        
        plt.close('all')
        return True
        
    except Exception as e:
        print("蜂窝时间可视化出错: {}".format(e))
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":    
    if len(sys.argv) > 1:
        report_file = sys.argv[1]
    else:
        report_file = "/home/wuq/webrtc-checkout/logcode/diag_report.txt"
    
    print("开始蜂窝网络时间精度分析: {}".format(report_file))
    success = visualize_cellular_timing(report_file)
    
    if success:
        print("\n蜂窝时间分析完成！")
        print("SysFN和SubFN提供了比Unix时间戳更精确的毫秒级时间排序")
    else:
        print("\n分析失败，请检查错误信息")
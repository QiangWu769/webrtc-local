# -*- coding: utf-8 -*-
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import sys

def visualize_events_from_report(report_file="diag_report.txt"):
    """
    从diag_report.txt文件中读取数据并创建可视化图表
    按时间戳、subfn和sysfn精确显示每一次事件
    """
    try:
        # 读取数据文件
        df = pd.read_csv(report_file, sep='\t')
        
        # 转换时间戳为datetime对象
        df['timestamp_dt'] = pd.to_datetime(df['RAN_Event_Unix_Timestamp'], unit='s')
        
        # 创建图表
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(15, 12))
        fig.suptitle('WebRTC Diagnostic Events Visualization', fontsize=16)
        
        # 图表1：时间线上的事件分布 (按SubFN着色)
        subfn_values = df['SubFN'].unique()
        colors = plt.cm.Set1(np.linspace(0, 1, len(subfn_values)))
        subfn_color_map = dict(zip(subfn_values, colors))
        
        for subfn in subfn_values:
            mask = df['SubFN'] == subfn
            ax1.scatter(df[mask]['timestamp_dt'], df[mask]['SysFN'], 
                       c=[subfn_color_map[subfn]], label='SubFN {}'.format(subfn), alpha=0.7, s=30)
        
        ax1.set_xlabel('Time')
        ax1.set_ylabel('SysFN')
        ax1.set_title('Event Timeline - Grouped by SubFN')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 格式化x轴时间显示 - 使用更合理的间隔
        time_range = (df['timestamp_dt'].max() - df['timestamp_dt'].min()).total_seconds()
        if time_range < 10:  # 小于10秒，用毫秒级间隔
            ax1.xaxis.set_major_locator(mdates.SecondLocator(interval=1))
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        else:
            ax1.xaxis.set_major_locator(mdates.MinuteLocator(interval=1))
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
        
        # 图表2：SubFN vs SysFN 热力图
        pivot_data = df.groupby(['SubFN', 'SysFN']).size().unstack(fill_value=0)
        if not pivot_data.empty:
            im = ax2.imshow(pivot_data.values, cmap='YlOrRd', aspect='auto')
            ax2.set_xticks(range(len(pivot_data.columns)))
            ax2.set_xticklabels(pivot_data.columns)
            ax2.set_yticks(range(len(pivot_data.index)))
            ax2.set_yticklabels(pivot_data.index)
            ax2.set_xlabel('SysFN')
            ax2.set_ylabel('SubFN')
            ax2.set_title('SubFN vs SysFN Event Frequency Heatmap')
            
            # 添加颜色条
            cbar = plt.colorbar(im, ax=ax2)
            cbar.set_label('Event Count')
            
            # 在每个格子中显示数值
            for i in range(len(pivot_data.index)):
                for j in range(len(pivot_data.columns)):
                    text = ax2.text(j, i, pivot_data.values[i, j],
                                   ha="center", va="center", color="black", fontsize=8)
        
        # 图表3：延迟分析
        if 'Pipeline_Latency_ms' in df.columns:
            # 按时间显示延迟
            ax3.plot(df['timestamp_dt'], df['Pipeline_Latency_ms'], 'b-', alpha=0.7, linewidth=1)
            ax3.scatter(df['timestamp_dt'], df['Pipeline_Latency_ms'], 
                       c=df['SubFN'], cmap='viridis', alpha=0.6, s=20)
            ax3.set_xlabel('Time')
            ax3.set_ylabel('Pipeline Latency (ms)')
            ax3.set_title('Pipeline Latency Over Time')
            ax3.grid(True, alpha=0.3)
            
            # 格式化x轴时间显示 - 使用更合理的间隔
            if time_range < 10:  # 小于10秒，用毫秒级间隔
                ax3.xaxis.set_major_locator(mdates.SecondLocator(interval=1))
                ax3.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
            else:
                ax3.xaxis.set_major_locator(mdates.MinuteLocator(interval=1))
                ax3.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45)
            
            # 添加延迟统计信息
            mean_latency = df['Pipeline_Latency_ms'].mean()
            ax3.axhline(y=mean_latency, color='r', linestyle='--', alpha=0.7, 
                       label='Average Latency: {:.2f}ms'.format(mean_latency))
            ax3.legend()
        
        plt.tight_layout()
        
        # 保存图表
        output_file = report_file.replace('.txt', '_visualization.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print("Visualization saved as: {}".format(output_file))
        
        # 显示统计信息
        print("\n=== Data Statistics ===")
        print("Total events: {}".format(len(df)))
        print("Time range: {} to {}".format(df['timestamp_dt'].min(), df['timestamp_dt'].max()))
        print("SubFN range: {} - {}".format(df['SubFN'].min(), df['SubFN'].max()))
        print("SysFN range: {} - {}".format(df['SysFN'].min(), df['SysFN'].max()))
        
        if 'Pipeline_Latency_ms' in df.columns:
            print("Latency statistics:")
            print("  Average: {:.3f}ms".format(df['Pipeline_Latency_ms'].mean()))
            print("  Min: {:.3f}ms".format(df['Pipeline_Latency_ms'].min())) 
            print("  Max: {:.3f}ms".format(df['Pipeline_Latency_ms'].max()))
            print("  Std dev: {:.3f}ms".format(df['Pipeline_Latency_ms'].std()))
        
        # 按时间戳分组显示详细事件
        print("\n=== Event Details by Timestamp ===")
        grouped = df.groupby('RAN_Event_Unix_Timestamp')
        count = 0
        for timestamp, group in grouped:
            if count >= 5:  # 只显示前5个时间戳组
                break
            print("\nTimestamp {:.6f} ({}):".format(timestamp, pd.to_datetime(timestamp, unit='s')))
            for _, row in group.iterrows():
                print("  SubFN={}, SysFN={}, LCG=[{},{},{},{}], RBs={}, TBS={}".format(
                    row['SubFN'], row['SysFN'], row['LCG_0'], row['LCG_1'], 
                    row['LCG_2'], row['LCG_3'], row['Num_RBs'], row['TBS_Index']))
            count += 1
        
        # plt.show()  # 注释掉显示，只保存文件
        
    except FileNotFoundError:
        print("Error: File {} not found".format(report_file))
        print("Please ensure you have run the main() function to generate the data file")
    except Exception as e:
        print("Error during visualization: {}".format(e))
        import traceback
        traceback.print_exc()

def create_interactive_timeline(report_file="diag_report.txt"):
    """
    创建交互式时间线图表，可以缩放和查看详细信息
    """
    try:
        df = pd.read_csv(report_file, sep='\t')
        df['timestamp_dt'] = pd.to_datetime(df['RAN_Event_Unix_Timestamp'], unit='s')
        
        fig, ax = plt.subplots(figsize=(16, 8))
        
        # 为每个唯一的(SubFN, SysFN)组合分配y轴位置
        unique_combinations = df[['SubFN', 'SysFN']].drop_duplicates()
        y_positions = {}
        for i, (_, row) in enumerate(unique_combinations.iterrows()):
            key = "{}-{}".format(row['SubFN'], row['SysFN'])
            y_positions[key] = i
        
        # 绘制每个事件
        for _, row in df.iterrows():
            key = "{}-{}".format(row['SubFN'], row['SysFN'])
            y_pos = y_positions[key]
            
            # 根据Pipeline_Latency_ms决定颜色
            if pd.notna(row['Pipeline_Latency_ms']) and df['Pipeline_Latency_ms'].max() > 0:
                color = plt.cm.viridis(row['Pipeline_Latency_ms'] / df['Pipeline_Latency_ms'].max())
            else:
                color = 'gray'
            
            ax.scatter(row['timestamp_dt'], y_pos, c=[color], s=50, alpha=0.7)
        
        # 设置y轴标签
        ax.set_yticks(list(y_positions.values()))
        labels = []
        for k in y_positions.keys():
            parts = k.split('-')
            labels.append("SubFN{}-SysFN{}".format(parts[0], parts[1]))
        ax.set_yticklabels(labels)
        
        ax.set_xlabel('Time')
        ax.set_ylabel('SubFN-SysFN Combinations')
        ax.set_title('Interactive Event Timeline (Color represents latency)')
        ax.grid(True, alpha=0.3)
        
        # 添加颜色条
        if 'Pipeline_Latency_ms' in df.columns and df['Pipeline_Latency_ms'].max() > 0:
            sm = plt.cm.ScalarMappable(cmap='viridis', 
                                       norm=plt.Normalize(vmin=df['Pipeline_Latency_ms'].min(),
                                                         vmax=df['Pipeline_Latency_ms'].max()))
            sm.set_array([])
            cbar = plt.colorbar(sm, ax=ax)
            cbar.set_label('Pipeline Latency (ms)')
        
        # 格式化时间轴
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        
        plt.tight_layout()
        
        # 保存交互式图表
        interactive_file = report_file.replace('.txt', '_interactive_timeline.png')
        plt.savefig(interactive_file, dpi=300, bbox_inches='tight')
        print("Interactive timeline saved as: {}".format(interactive_file))
        
        # plt.show()  # 注释掉显示，只保存文件
        
    except Exception as e:
        print("Error creating interactive timeline: {}".format(e))

if __name__ == "__main__":    
    if len(sys.argv) > 1:
        # 使用命令行参数指定的文件
        report_file = sys.argv[1]
    else:
        # 默认文件
        report_file = "/home/wuq/webrtc-checkout/logcode/diag_report.txt"
    
    print("Starting visualization from {}...".format(report_file))
    visualize_events_from_report(report_file)
    create_interactive_timeline(report_file)
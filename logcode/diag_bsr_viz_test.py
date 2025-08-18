# -*- coding: utf-8 -*-
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import sys

class DiagVisualizationTest:
    """
    专门用于测试蜂窝网络时间精度可视化功能
    """
    
    def calculate_cellular_time_order(self, df):
        """
        基于蜂窝网络时间结构计算精确的时间顺序
        SysFN: 0-1023 (系统帧号，每10ms递增)
        SubFN: 0-9 (子帧号，每1ms递增)
        """
        # 计算相对时间偏移(ms) = SysFN * 10 + SubFN * 1
        df['cellular_time_ms'] = df['SysFN'] * 10 + df['SubFN'] * 1
        
        # 处理SysFN的循环(0-1023)
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

    def visualize_cellular_timing_integrated(self, report_file):
        """
        在diag_bsr.py中集成的蜂窝网络时间结构可视化
        """
        try:
            # 读取数据
            df = pd.read_csv(report_file, sep='\t')
            print("Original data: {} events".format(len(df)))
            
            # 计算精确的蜂窝网络时间顺序
            df_refined = self.calculate_cellular_time_order(df)
            print("Processed data: {} events".format(len(df_refined)))
            
            # 创建可视化
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle('Integrated Cellular Network Time Precision Analysis (diag_bsr.py)', fontsize=16)
            
            # 图1: 蜂窝时间轴上的事件分布
            colors = plt.cm.tab10(df_refined['SubFN'] / 9.0)  # 按SubFN着色
            scatter1 = ax1.scatter(df_refined['cellular_time_ms'], df_refined['SysFN'], 
                                  c=colors, alpha=0.6, s=15)
            ax1.set_xlabel('Cellular Time (ms) = SysFN*10 + SubFN*1')
            ax1.set_ylabel('SysFN (System Frame Number)')
            ax1.set_title('Event Distribution on Cellular Timeline')
            ax1.grid(True, alpha=0.3)
            
            # 添加SubFN颜色说明
            for subfn in range(min(10, int(df_refined['SubFN'].max()) + 1)):
                color = plt.cm.tab10(subfn/9.0)
                ax1.scatter([], [], c=[color], label='SubFN {}'.format(subfn), s=30)
            ax1.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
            
            # 图2: 同一时间戳内的事件细分
            timestamp_counts = df_refined.groupby('RAN_Event_Unix_Timestamp').size()
            multi_event_timestamps = timestamp_counts[timestamp_counts > 1].head(5)
            
            colors_subfn = plt.cm.Set1(np.linspace(0, 1, 10))
            y_pos = 0
            timestamp_y_map = {}
            
            for timestamp in multi_event_timestamps.index:
                events = df_refined[df_refined['RAN_Event_Unix_Timestamp'] == timestamp].sort_values('cellular_time_ms')
                timestamp_y_map[timestamp] = y_pos
                
                for _, event in events.iterrows():
                    color_idx = int(event['SubFN']) % 10
                    ax2.scatter(event['cellular_time_ms'], y_pos, 
                               c=[colors_subfn[color_idx]], s=60, alpha=0.8)
                    # 标注SysFN
                    ax2.text(event['cellular_time_ms'], y_pos + 0.1, 
                            'SF{}'.format(int(event['SysFN'])), 
                            fontsize=6, ha='center')
                y_pos += 1
            
            ax2.set_xlabel('Cellular Time (ms)')
            ax2.set_ylabel('Timestamp Group')
            ax2.set_title('Event Subdivision within Same Unix Timestamp (Top 5 Groups)')
            ax2.set_yticks(list(timestamp_y_map.values()))
            ax2.set_yticklabels(['TS{}'.format(i+1) for i in range(len(timestamp_y_map))])
            ax2.grid(True, alpha=0.3)
            
            # 图3: SubFN的时间分布模式
            subfn_time_data = []
            for subfn in range(int(df_refined['SubFN'].max()) + 1):
                subfn_events = df_refined[df_refined['SubFN'] == subfn]
                if len(subfn_events) > 0:
                    subfn_time_data.extend([subfn] * len(subfn_events))
            
            if subfn_time_data:
                ax3.hist(subfn_time_data, bins=min(20, len(set(subfn_time_data))), 
                        alpha=0.7, color='lightblue', edgecolor='black')
            ax3.set_xlabel('SubFN (Subframe Number)')
            ax3.set_ylabel('Event Count')
            ax3.set_title('SubFN Distribution (Increments every 1ms)')
            ax3.grid(True, alpha=0.3)
            
            # 图4: SysFN的循环模式  
            ax4.hist(df_refined['SysFN'], bins=50, alpha=0.7, color='lightgreen', edgecolor='black')
            ax4.set_xlabel('SysFN (System Frame Number)')
            ax4.set_ylabel('Event Count')
            ax4.set_title('SysFN Distribution (0-1023 cycle, increments every 10ms)')
            ax4.grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            # 保存图表
            output_file = report_file.replace('.txt', '_diag_bsr_integrated.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            print("diag_bsr.py integrated cellular timing analysis saved as: {}".format(output_file))
            
            # 显示时间精度分析
            print("\n=== diag_bsr.py Integrated Cellular Time Precision Analysis ===")
            print("SysFN range: {} - {} (System frame number, increments every 10ms)".format(
                df_refined['SysFN'].min(), df_refined['SysFN'].max()))
            print("SubFN range: {} - {} (Subframe number, increments every 1ms)".format(
                df_refined['SubFN'].min(), df_refined['SubFN'].max()))
            
            # 分析同一时间戳内的事件数量
            same_timestamp_counts = df_refined.groupby('RAN_Event_Unix_Timestamp').size()
            print("Max events in same Unix timestamp: {}".format(same_timestamp_counts.max()))
            print("Number of timestamps with multiple events: {}".format(sum(same_timestamp_counts > 1)))
            
            # 展示几个同时间戳事件的详细信息
            print("\n=== Cellular Time Subdivision for Same Timestamp Events (diag_bsr.py) ===")
            count = 0
            for timestamp, events in df_refined.groupby('RAN_Event_Unix_Timestamp'):
                if len(events) > 1 and count < 3:  # 只显示前3组
                    events_sorted = events.sort_values('cellular_time_ms')
                    print("\nUnix timestamp {:.6f}:".format(timestamp))
                    for _, event in events_sorted.iterrows():
                        cellular_time = event['SysFN'] * 10 + event['SubFN']
                        print("  SysFN={:4d}, SubFN={}, CellularTime={}ms, LCG=[{},{},{},{}], RBs={}".format(
                            int(event['SysFN']), int(event['SubFN']), cellular_time,
                            event['LCG_0'], event['LCG_1'], event['LCG_2'], event['LCG_3'], 
                            event['Num_RBs']))
                    count += 1
            
            plt.close('all')
            return True
            
        except Exception as e:
            print("diag_bsr.py cellular timing visualization error: {}".format(e))
            import traceback
            traceback.print_exc()
            return False

def main():
    if len(sys.argv) > 1:
        report_file = sys.argv[1]
    else:
        report_file = "diag_report.txt"
    
    print("Testing diag_bsr.py integrated cellular timing visualization...")
    print("Report file: {}".format(report_file))
    
    viz_test = DiagVisualizationTest()
    success = viz_test.visualize_cellular_timing_integrated(report_file)
    
    if success:
        print("\n✅ diag_bsr.py integration test PASSED!")
        print("The cellular timing visualization is ready to be integrated into diag_bsr.py")
        print("SysFN and SubFN provide precise millisecond-level event timing")
    else:
        print("\n❌ diag_bsr.py integration test FAILED!")
        print("Please check the error messages above")

if __name__ == "__main__":
    main()
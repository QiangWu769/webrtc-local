# -*- coding: utf-8 -*-
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import sys

def visualize_events_simple(report_file="diag_report.txt"):
    """
    简化版本的事件可视化，专注于展示subfn和sysfn的关系
    """
    try:
        # 读取数据文件
        df = pd.read_csv(report_file, sep='\t')
        print("Data loaded successfully:")
        print("Total events: {}".format(len(df)))
        print("Columns: {}".format(list(df.columns)))
        
        # 创建简单的散点图
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('WebRTC Diagnostic Events Analysis', fontsize=16)
        
        # 图表1：SubFN vs SysFN 散点图
        colors = plt.cm.viridis(np.linspace(0, 1, len(df)))
        scatter1 = ax1.scatter(df['SubFN'], df['SysFN'], c=colors, alpha=0.6, s=20)
        ax1.set_xlabel('SubFN')
        ax1.set_ylabel('SysFN')
        ax1.set_title('SubFN vs SysFN Distribution')
        ax1.grid(True, alpha=0.3)
        
        # 图表2：事件时间索引 vs SysFN（避免时间戳问题）
        ax2.scatter(range(len(df)), df['SysFN'], c=df['SubFN'], cmap='Set1', alpha=0.6, s=20)
        ax2.set_xlabel('Event Index (Time Order)')
        ax2.set_ylabel('SysFN') 
        ax2.set_title('SysFN Over Time (by Event Index)')
        ax2.grid(True, alpha=0.3)
        
        # 图表3：SubFN分布直方图
        ax3.hist(df['SubFN'], bins=20, alpha=0.7, color='skyblue', edgecolor='black')
        ax3.set_xlabel('SubFN')
        ax3.set_ylabel('Count')
        ax3.set_title('SubFN Distribution')
        ax3.grid(True, alpha=0.3)
        
        # 图表4：延迟分析（如果有延迟列）
        if 'Pipeline_Latency_ms' in df.columns:
            latency_data = df['Pipeline_Latency_ms'].dropna()
            if len(latency_data) > 0:
                ax4.hist(latency_data, bins=20, alpha=0.7, color='orange', edgecolor='black')
                ax4.set_xlabel('Pipeline Latency (ms)')
                ax4.set_ylabel('Count')
                ax4.set_title('Latency Distribution')
                ax4.grid(True, alpha=0.3)
                
                # 添加统计信息
                mean_lat = latency_data.mean()
                ax4.axvline(mean_lat, color='red', linestyle='--', 
                           label='Mean: {:.2f}ms'.format(mean_lat))
                ax4.legend()
            else:
                ax4.text(0.5, 0.5, 'No Latency Data Available', 
                        transform=ax4.transAxes, ha='center', va='center')
        else:
            # 如果没有延迟数据，显示SysFN分布
            ax4.hist(df['SysFN'], bins=20, alpha=0.7, color='lightgreen', edgecolor='black')
            ax4.set_xlabel('SysFN')
            ax4.set_ylabel('Count')
            ax4.set_title('SysFN Distribution')
            ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # 保存图表
        output_file = report_file.replace('.txt', '_simple_viz.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print("Simple visualization saved as: {}".format(output_file))
        
        # 显示基本统计信息
        print("\n=== Basic Statistics ===")
        print("SubFN range: {} - {}".format(df['SubFN'].min(), df['SubFN'].max()))
        print("SysFN range: {} - {}".format(df['SysFN'].min(), df['SysFN'].max()))
        print("Unique SubFN values: {}".format(df['SubFN'].nunique()))
        print("Unique SysFN values: {}".format(df['SysFN'].nunique()))
        
        # 显示每个时间戳的事件详情（按索引而不是实际时间戳）
        print("\n=== Event Details by Timestamp Group ===")
        grouped = df.groupby('RAN_Event_Unix_Timestamp')
        count = 0
        for timestamp, group in grouped:
            if count >= 3:  # 只显示前3个时间戳组
                break
            print("\nTimestamp {:.6f}:".format(timestamp))
            for _, row in group.iterrows():
                print("  SubFN={}, SysFN={}, LCG=[{},{},{},{}], RBs={}, TBS={}".format(
                    row['SubFN'], row['SysFN'], row['LCG_0'], row['LCG_1'], 
                    row['LCG_2'], row['LCG_3'], row['Num_RBs'], row['TBS_Index']))
            count += 1
        
        plt.close('all')  # 关闭所有图形
        return True
        
    except FileNotFoundError:
        print("Error: File {} not found".format(report_file))
        return False
    except Exception as e:
        print("Error during visualization: {}".format(e))
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":    
    if len(sys.argv) > 1:
        report_file = sys.argv[1]
    else:
        report_file = "/home/wuq/webrtc-checkout/logcode/diag_report.txt"
    
    print("Starting simple visualization from {}...".format(report_file))
    success = visualize_events_simple(report_file)
    
    if success:
        print("\nVisualization completed successfully!")
        print("Check the generated PNG file for the charts.")
    else:
        print("\nVisualization failed. Please check the error messages above.")
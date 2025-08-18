#!/usr/bin/env python3
"""
数据可视化脚本
绘制三条线的分离图表，正确处理同一时间戳下多个子帧的数据：
1. LCG_3：同一时间戳下所有子帧的LCG_3值累加
2. TBS_Index：同一时间戳下所有子帧的TBS_Index值平均
3. Num_RBs：同一时间戳下所有子帧的Num_RBs值累加
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
from collections import defaultdict
import re
import os

def parse_data_file(filename):
    """
    解析数据文件
    
    Args:
        filename: 数据文件路径
        
    Returns:
        pandas.DataFrame: 解析后的数据
    """
    # 读取数据，跳过第一行（表头）
    df = pd.read_csv(filename, sep='\t', skiprows=0)
    
    # 确保列名正确
    expected_columns = [
        'AN_Event_Timestamp', 'Bridge_Read_Timestamp', 'Python_Recv_Timestamp',
        'SubFN', 'SysFN', 'LCG_0', 'LCG_1', 'LCG_2', 'LCG_3', 
        'Num_RBs', 'TBS_Index', 'Pipeline_Latency_ms'
    ]
    
    print(f"文件列数: {len(df.columns)}")
    print(f"实际列名: {df.columns.tolist()}")
    
    return df

def extract_tbs_index_values(df):
    """
    提取TBS_Index的数值变化（同一时间戳下的平均值）
    
    Args:
        df: DataFrame
        
    Returns:
        tuple: (timestamps, tbs_index_values)
    """
    # 按时间戳分组
    grouped = df.groupby('Python_Recv_Timestamp')
    
    timestamps = []
    tbs_values = []
    
    for timestamp, group in grouped:
        # 收集同一时间戳下所有有效TBS_Index值
        valid_tbs = []
        for _, row in group.iterrows():
            tbs_index = row['TBS_Index']
            if pd.notna(tbs_index) and tbs_index != '-' and 'TBS_Index_' in str(tbs_index):
                try:
                    # 从 "TBS_Index_20" 中提取 "20"
                    index_num = int(str(tbs_index).split('_')[-1])
                    valid_tbs.append(index_num)
                except (ValueError, IndexError):
                    pass
        
        # 计算平均值，如果没有有效值则为0
        if valid_tbs:
            avg_tbs = sum(valid_tbs) / len(valid_tbs)
        else:
            avg_tbs = 0
        
        timestamps.append(timestamp)
        tbs_values.append(avg_tbs)
    
    return timestamps, tbs_values

def extract_lcg3_values(df):
    """
    提取LCG_3在时间点的聚合值（同一时间戳下所有子帧的累加）
    
    Args:
        df: DataFrame
        
    Returns:
        tuple: (timestamps, lcg3_values)
    """
    # 按时间戳分组
    grouped = df.groupby('Python_Recv_Timestamp')
    
    timestamps = []
    lcg3_values = []
    
    for timestamp, group in grouped:
        # 累加同一时间戳下所有非零LCG_3值
        total_lcg3 = 0
        for _, row in group.iterrows():
            lcg_3 = row['LCG_3']
            if pd.notna(lcg_3) and lcg_3 != '-':
                try:
                    lcg_3_val = int(lcg_3)
                    if lcg_3_val > 0:
                        total_lcg3 += lcg_3_val
                except (ValueError, TypeError):
                    pass
        
        timestamps.append(timestamp)
        lcg3_values.append(total_lcg3)
    
    return timestamps, lcg3_values

def extract_num_rbs(df):
    """
    提取Num_RBs的数量变化（同一时间戳下所有子帧的累加）
    
    Args:
        df: DataFrame
        
    Returns:
        tuple: (timestamps, num_rbs_values)
    """
    # 按时间戳分组
    grouped = df.groupby('Python_Recv_Timestamp')
    
    timestamps = []
    num_rbs_values = []
    
    for timestamp, group in grouped:
        # 累加同一时间戳下所有非零Num_RBs值
        total_rbs = 0
        for _, row in group.iterrows():
            num_rbs = row['Num_RBs']
            if pd.notna(num_rbs) and num_rbs != '-':
                try:
                    num_rbs_val = int(num_rbs)
                    if num_rbs_val > 0:
                        total_rbs += num_rbs_val
                except (ValueError, TypeError):
                    pass
        
        timestamps.append(timestamp)
        num_rbs_values.append(total_rbs)
    
    return timestamps, num_rbs_values

def plot_data(filename):
    """
    绘制数据图表
    
    Args:
        filename: 数据文件路径
    """
    # 解析数据
    df = parse_data_file(filename)
    print(f"加载了 {len(df)} 行数据")
    
    # 提取三条线的数据
    # 1. LCG_3时间点实际值
    lcg3_timestamps, lcg3_values = extract_lcg3_values(df)
    
    # 2. TBS_Index变化
    tbs_timestamps, tbs_values = extract_tbs_index_values(df)
    
    # 3. Num_RBs数量变化
    numrbs_timestamps, numrbs_values = extract_num_rbs(df)
    
    # 解析并对齐 WebRTC 发送端日志（使用 wall-clock 时间戳对齐）
    def parse_sender_log(sender_log_path):
        gcc_times = []
        gcc_final = []
        constraint_times = []
        constraint_final = []
        bwe_decision_times = []
        bwe_new_target = []

        # 正则：提取 wall-clock 秒 和 指标
        gcc_pat = re.compile(r"\[(\d+\.\d+)\]\s+\[GCC-OUTPUT\].*?FinalTargetBps:\s*(\d+)")
        constraint_pat = re.compile(r"\[(\d+\.\d+)\]\s+\[BWE-ConstraintApply\].*?Final:\s*(\d+|INF)\s*bps")
        decision_pat = re.compile(r"\[(\d+\.\d+)\]\s+\[BWE-DECISION\].*?NewTarget:\s*(\d+)\s*bps")

        try:
            with open(sender_log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    m1 = gcc_pat.search(line)
                    if m1:
                        t = float(m1.group(1))
                        v = int(m1.group(2))
                        gcc_times.append(t)
                        gcc_final.append(v)
                        continue

                    m2 = constraint_pat.search(line)
                    if m2:
                        t = float(m2.group(1))
                        v_str = m2.group(2)
                        if v_str != 'INF':
                            constraint_times.append(t)
                            constraint_final.append(int(v_str))
                        continue

                    m3 = decision_pat.search(line)
                    if m3:
                        t = float(m3.group(1))
                        v = int(m3.group(2))
                        bwe_decision_times.append(t)
                        bwe_new_target.append(v)
                        continue
        except FileNotFoundError:
            print(f"[!] 未找到 sender 日志: {sender_log_path}")
        except Exception as e:
            print(f"[!] 解析 sender 日志失败: {e}")

        return {
            'gcc_output': pd.DataFrame({'time': gcc_times, 'final_bps': gcc_final}),
            'constraint_final': pd.DataFrame({'time': constraint_times, 'final_bps': constraint_final}),
            'bwe_decision': pd.DataFrame({'time': bwe_decision_times, 'new_target_bps': bwe_new_target}),
        }

    sender_log_path = "/home/wuq/webrtc-checkout/webrtc_config_results/sender_local.log"
    sender_series = parse_sender_log(sender_log_path)

    # 计算对齐时间范围（按 Python_Recv_Timestamp 与 sender wall-clock 的交集）
    try:
        diag_min = float(df['Python_Recv_Timestamp'].min())
        diag_max = float(df['Python_Recv_Timestamp'].max())
    except Exception:
        # 如果列名不同，尝试兼容
        if 'Python_Recv_Timestamp' not in df.columns:
            raise RuntimeError('数据文件缺少 Python_Recv_Timestamp 列，无法对齐时间。')

    def within_overlap(df_ts, tcol='time'):
        if df_ts is None or df_ts.empty:
            return df_ts
        return df_ts[(df_ts[tcol] >= diag_min) & (df_ts[tcol] <= diag_max)].copy()

    gcc_df = within_overlap(sender_series.get('gcc_output'))
    cons_df = within_overlap(sender_series.get('constraint_final'))
    deci_df = within_overlap(sender_series.get('bwe_decision'))

    # 创建图表
    plt.figure(figsize=(15, 12))
    
    # 设置中文字体
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'SimHei', 'Arial Unicode MS']
    plt.rcParams['axes.unicode_minus'] = False
    
    # 绘制三条线
    plt.subplot(4, 1, 1)
    plt.plot(lcg3_timestamps, lcg3_values, 'b-', linewidth=2, label='LCG_3 Aggregated Values')
    plt.title('LCG_3 Aggregated Values Over Time (Sum per Timestamp)')
    plt.xlabel('Python_Recv_Timestamp')
    plt.ylabel('LCG_3 Sum')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plt.subplot(4, 1, 2)
    plt.plot(tbs_timestamps, tbs_values, 'r-', linewidth=2, label='TBS_Index Average')
    plt.title('TBS_Index Average Over Time (Average per Timestamp)')
    plt.xlabel('Python_Recv_Timestamp')
    plt.ylabel('TBS_Index Average')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plt.subplot(4, 1, 3)
    plt.plot(numrbs_timestamps, numrbs_values, 'g-', linewidth=2, label='Num_RBs Aggregated')
    plt.title('Num_RBs Aggregated Over Time (Sum per Timestamp)')
    plt.xlabel('Python_Recv_Timestamp')
    plt.ylabel('Num_RBs Sum')
    plt.legend()
    plt.grid(True, alpha=0.3)

    # 第4张：叠加绘制 WebRTC 关键比特率（按对齐区间）
    plt.subplot(4, 1, 4)
    plotted_any = False
    if gcc_df is not None and not gcc_df.empty:
        plt.plot(gcc_df['time'], gcc_df['final_bps'] / 1000.0, '-', color='purple', linewidth=1.8, label='GCC FinalTarget (kbps)')
        plotted_any = True
    if cons_df is not None and not cons_df.empty:
        plt.plot(cons_df['time'], cons_df['final_bps'] / 1000.0, '--', color='orange', linewidth=1.5, label='Constraint Final (kbps)')
        plotted_any = True
    if deci_df is not None and not deci_df.empty:
        plt.plot(deci_df['time'], deci_df['new_target_bps'] / 1000.0, ':', color='teal', linewidth=1.5, label='BWE NewTarget (kbps)')
        plotted_any = True

    plt.title('Aligned WebRTC Bitrates (Overlapped with Python_Recv_Timestamp)')
    plt.xlabel('Wall-clock seconds (aligned to Python_Recv_Timestamp)')
    plt.ylabel('Bitrate (kbps)')
    if plotted_any:
        plt.legend()
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # 保存图表
    output_filename = filename.replace('.txt', '_visualization.png')
    plt.savefig(output_filename, dpi=300, bbox_inches='tight')
    print(f"图表已保存为: {output_filename}")

    # 生成合并叠加图（严格按时间戳对齐在同一张图内）
    combined_fig = plt.figure(figsize=(16, 9))
    ax_left = combined_fig.add_subplot(111)  # 左轴：带宽(kbps)
    ax_right = ax_left.twinx()               # 右轴：Diag 指标

    # 左轴：WebRTC 关键比特率（对齐区间）
    left_plotted = False
    if gcc_df is not None and not gcc_df.empty:
        ax_left.plot(gcc_df['time'], gcc_df['final_bps'] / 1000.0, '-', color='purple', linewidth=1.8, label='GCC FinalTarget (kbps)')
        left_plotted = True
    if cons_df is not None and not cons_df.empty:
        ax_left.plot(cons_df['time'], cons_df['final_bps'] / 1000.0, '--', color='orange', linewidth=1.5, label='Constraint Final (kbps)')
        left_plotted = True
    if deci_df is not None and not deci_df.empty:
        ax_left.plot(deci_df['time'], deci_df['new_target_bps'] / 1000.0, ':', color='teal', linewidth=1.5, label='BWE NewTarget (kbps)')
        left_plotted = True

    # 右轴：Diag 聚合指标（都与 Python_Recv_Timestamp 对齐）
    # 为了避免 legend 过长，对三个指标分别上色
    ax_right.plot(lcg3_timestamps, lcg3_values, '-', color='tab:blue', alpha=0.6, linewidth=1.4, label='LCG_3 Sum')
    ax_right.plot(numrbs_timestamps, numrbs_values, '-', color='tab:green', alpha=0.6, linewidth=1.4, label='Num_RBs Sum')
    ax_right.plot(tbs_timestamps, tbs_values, '-', color='tab:red', alpha=0.8, linewidth=1.6, label='TBS_Index Avg')

    # 坐标轴与标题
    ax_left.set_title('Diag + WebRTC Combined (Time-aligned by epoch seconds)', fontsize=14, fontweight='bold')
    ax_left.set_xlabel('Epoch seconds')
    ax_left.set_ylabel('Bitrate (kbps)')
    ax_right.set_ylabel('Diag metrics (LCG_3 Sum / Num_RBs Sum / TBS_Index Avg)')

    # 图例
    lines_left, labels_left = ax_left.get_legend_handles_labels()
    lines_right, labels_right = ax_right.get_legend_handles_labels()
    ax_left.legend(lines_left + lines_right, labels_left + labels_right, loc='upper left')

    # x 轴范围取两类数据交集（如果左轴有绘制）
    if left_plotted:
        x_min = max(diag_min, min([s.min() for s in [gcc_df['time']] if gcc_df is not None and not gcc_df.empty] +
                                   [s.min() for s in [cons_df['time']] if cons_df is not None and not cons_df.empty] +
                                   [s.min() for s in [deci_df['time']] if deci_df is not None and not deci_df.empty]))
        x_max = min(diag_max, max([s.max() for s in [gcc_df['time']] if gcc_df is not None and not gcc_df.empty] +
                                   [s.max() for s in [cons_df['time']] if cons_df is not None and not cons_df.empty] +
                                   [s.max() for s in [deci_df['time']] if deci_df is not None and not deci_df.empty]))
        if x_min < x_max:
            ax_left.set_xlim(x_min, x_max)

    ax_left.grid(True, alpha=0.3)

    combined_output = filename.replace('.txt', '_combined_visualization.png')
    combined_fig.savefig(combined_output, dpi=300, bbox_inches='tight')
    print(f"合并叠加图已保存为: {combined_output}")
    
    # 显示图表
    plt.show()
    
    # 打印统计信息
    print("\n数据统计（按时间戳聚合后）:")
    print(f"时间戳总数: {len(lcg3_timestamps)}")
    print(f"LCG_3最大聚合值: {max(lcg3_values) if lcg3_values else 0}")
    print(f"LCG_3平均聚合值: {np.mean([x for x in lcg3_values if x > 0]) if any(x > 0 for x in lcg3_values) else 0:.2f}")
    print(f"TBS_Index范围: {min([x for x in tbs_values if x > 0]) if any(x > 0 for x in tbs_values) else 0:.2f} - {max(tbs_values) if tbs_values else 0:.2f}")
    print(f"TBS_Index有效时间戳数: {sum(1 for x in tbs_values if x > 0)}")
    print(f"Num_RBs最大聚合值: {max(numrbs_values) if numrbs_values else 0}")
    print(f"Num_RBs平均聚合值: {np.mean([x for x in numrbs_values if x > 0]) if any(x > 0 for x in numrbs_values) else 0:.2f}")



if __name__ == "__main__":
    # 数据文件路径
    data_file = "/home/wuq/webrtc-checkout/logcode/diag_report.txt"
    
    print("开始数据可视化...")
    
    # 绘制分离的图表
    plot_data(data_file)
    
    print("数据可视化完成!")
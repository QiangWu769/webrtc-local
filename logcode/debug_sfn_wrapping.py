#!/usr/bin/env python3

import pandas as pd
import numpy as np

def debug_sfn_sequence():
    """分析SFN序列，找出回绕问题"""
    print("=== 调试SFN回绕处理 ===")
    
    # 加载原始数据
    df = pd.read_csv("diag_report.txt", sep='\t', na_values='-')
    
    # 重命名列
    df.rename(columns={
        'Current_SFN_SF': 'SFN',
        'LCG_0': 'LCG0',
        'LCG_1': 'LCG1', 
        'LCG_2': 'LCG2',
        'LCG_3': 'LCG3'
    }, inplace=True)
    
    df['SFN'] = pd.to_numeric(df['SFN'], errors='coerce')
    
    # 提取非零BSR
    lcg_cols = ['LCG0', 'LCG1', 'LCG2', 'LCG3']
    bsr_mask = df[lcg_cols].notna().any(axis=1)
    df_bsr = df[bsr_mask].copy()
    df_bsr[lcg_cols] = df_bsr[lcg_cols].fillna(0)
    df_bsr['max_bsr_index'] = df_bsr[lcg_cols].max(axis=1)
    df_bsr_nonzero = df_bsr[df_bsr['max_bsr_index'] > 0].copy()
    
    print(f"非零BSR数量: {len(df_bsr_nonzero)}")
    
    # 查看原始SFN序列
    original_sfns = df_bsr_nonzero['SFN'].tolist()
    print(f"\n原始SFN序列前20个: {original_sfns[:20]}")
    
    # 按SFN排序
    df_bsr_sorted = df_bsr_nonzero.sort_values('SFN').reset_index(drop=True)
    sorted_sfns = df_bsr_sorted['SFN'].tolist()
    print(f"排序后SFN序列前20个: {sorted_sfns[:20]}")
    
    # 查找可能的回绕点
    print(f"\n分析SFN跳跃:")
    for i in range(1, min(20, len(sorted_sfns))):
        diff = sorted_sfns[i] - sorted_sfns[i-1]
        if abs(diff) > 1000:  # 大跳跃
            print(f"第{i}位: SFN从{sorted_sfns[i-1]}跳到{sorted_sfns[i]}, 差值={diff}")
    
    # 分析整个序列的SFN范围
    print(f"\nSFN统计:")
    print(f"最小SFN: {min(sorted_sfns)}")
    print(f"最大SFN: {max(sorted_sfns)}")
    
    # 检查是否有SFN > 10240的情况
    large_sfns = [sfn for sfn in sorted_sfns if sfn > 10240]
    print(f"超过10240的SFN数量: {len(large_sfns)}")
    if large_sfns:
        print(f"超过10240的SFN示例: {large_sfns[:10]}")
    
    # 手动测试回绕逻辑
    print(f"\n=== 手动测试回绕逻辑 ===")
    
    wrap_count = 0
    last_sfn = None
    adjusted_sfns = []
    
    for i, sfn in enumerate(sorted_sfns[:10]):
        if pd.notna(sfn):
            if last_sfn is not None and sfn < last_sfn - 5000:
                wrap_count += 1
                print(f"检测到回绕: SFN从{last_sfn}降到{sfn}, wrap_count变为{wrap_count}")
            adjusted_sfn = wrap_count * 10240 + sfn
            adjusted_sfns.append(adjusted_sfn)
            print(f"第{i}个: 原始SFN={sfn}, 调整后SFN={adjusted_sfn}")
            last_sfn = sfn
        else:
            adjusted_sfns.append(np.nan)

if __name__ == "__main__":
    debug_sfn_sequence()
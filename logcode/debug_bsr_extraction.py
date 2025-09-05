#!/usr/bin/env python3

import pandas as pd
import numpy as np

def debug_bsr_extraction(file_path):
    """调试BSR提取过程，找出SFN不匹配的问题"""
    print("=== 调试BSR提取过程 ===")
    
    # 1. 加载原始数据
    df = pd.read_csv(file_path, sep='\t', na_values='-')
    
    # 重命名列
    df.rename(columns={
        'RAN_Event_Unix_Timestamp': 'RAN_TS',
        'Bridge_Read_Timestamp': 'Bridge_TS', 
        'Python_Recv_Timestamp': 'Python_TS',
        'Cellular_Precise_Timestamp': 'Cellular_TS',
        'Current_SFN_SF': 'SFN',
        'Pipeline_Latency_ms': 'Latency',
        'LCG_0': 'LCG0',
        'LCG_1': 'LCG1', 
        'LCG_2': 'LCG2',
        'LCG_3': 'LCG3'
    }, inplace=True)
    
    # 确保SFN为数值类型
    df['SFN'] = pd.to_numeric(df['SFN'], errors='coerce')
    
    print(f"原始数据总行数: {len(df)}")
    
    # 2. 提取BSR事件（在回绕处理前）
    lcg_cols = ['LCG0', 'LCG1', 'LCG2', 'LCG3']
    print(f"LCG列: {lcg_cols}")
    
    # 显示原始数据前几行
    print(f"\n原始数据前10行:")
    print(df[['SFN'] + lcg_cols].head(10))
    
    # 查找有BSR值的行
    bsr_mask = df[lcg_cols].notna().any(axis=1)
    df_bsr_raw = df[bsr_mask].copy()
    print(f"\n有LCG值(包含NaN)的行数: {len(df_bsr_raw)}")
    
    # 查找有非零BSR值的行
    df_bsr_raw[lcg_cols] = df_bsr_raw[lcg_cols].fillna(0)
    df_bsr_raw['max_bsr_index'] = df_bsr_raw[lcg_cols].max(axis=1)
    
    print(f"\n前10个BSR记录(原始SFN):")
    print(df_bsr_raw[['SFN'] + lcg_cols + ['max_bsr_index']].head(10))
    
    # 过滤掉全0的BSR
    df_bsr_nonzero = df_bsr_raw[df_bsr_raw['max_bsr_index'] > 0]
    print(f"\n非零BSR记录数: {len(df_bsr_nonzero)}")
    
    if len(df_bsr_nonzero) > 0:
        print(f"\n前5个非零BSR记录(原始SFN):")
        print(df_bsr_nonzero[['SFN'] + lcg_cols + ['max_bsr_index']].head(5))
        
        print(f"\n第一个非零BSR:")
        first_bsr = df_bsr_nonzero.iloc[0]
        print(f"SFN: {first_bsr['SFN']}")
        print(f"LCG0: {first_bsr['LCG0']}")
        print(f"LCG1: {first_bsr['LCG1']}")
        print(f"LCG2: {first_bsr['LCG2']}")  
        print(f"LCG3: {first_bsr['LCG3']}")
        print(f"max_bsr_index: {first_bsr['max_bsr_index']}")
    
    # 3. 测试SFN回绕处理
    print(f"\n=== 测试SFN回绕处理 ===")
    
    def process_sfn_wrapping(df_event):
        if len(df_event) == 0:
            return df_event
            
        # 按时间戳排序而不是按SFN排序，保持真实的时间顺序
        df_event = df_event.sort_values('RAN_TS').reset_index(drop=True)
        
        print(f"排序后前5行SFN: {df_event['SFN'].head().tolist()}")
        
        wrap_count = 0
        last_sfn = None
        adjusted_sfns = []
        
        for i, sfn in enumerate(df_event['SFN']):
            if pd.notna(sfn):
                if last_sfn is not None and sfn < last_sfn - 5000:
                    wrap_count += 1
                    print(f"检测到回绕在第{i}行: SFN从{last_sfn}降到{sfn}, wrap_count={wrap_count}")
                adjusted_sfn = wrap_count * 10240 + sfn
                adjusted_sfns.append(adjusted_sfn)
                last_sfn = sfn
            else:
                adjusted_sfns.append(np.nan)
        
        df_event['SFN'] = adjusted_sfns
        return df_event
    
    if len(df_bsr_nonzero) > 0:
        df_bsr_processed = process_sfn_wrapping(df_bsr_nonzero.copy())
        print(f"\n处理后前5个BSR记录:")
        print(df_bsr_processed[['SFN'] + lcg_cols + ['max_bsr_index']].head(5))
        
        print(f"\n第一个处理后的BSR:")
        first_processed = df_bsr_processed.iloc[0]
        print(f"调整后SFN: {first_processed['SFN']}")
        print(f"LCG values: LCG0={first_processed['LCG0']}, LCG1={first_processed['LCG1']}, LCG2={first_processed['LCG2']}, LCG3={first_processed['LCG3']}")

if __name__ == "__main__":
    debug_bsr_extraction("diag_report.txt")
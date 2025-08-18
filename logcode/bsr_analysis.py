#!/usr/bin/env python3
"""
BSR资源分配效率分析工具
分析蜂窝网络中请求资源 vs 实际分配资源的对比
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
import seaborn as sns

class BSRAnalyzer:
    def __init__(self, report_file="diag_report.txt"):
        self.report_file = report_file
        self.data = None
        
        # BSR缓冲区大小映射表 (根据3GPP TS 36.321)
        self.bsr_table = {
            0: 0, 1: 10, 2: 12, 3: 14, 4: 17, 5: 19, 6: 22, 7: 26,
            8: 31, 9: 36, 10: 42, 11: 49, 12: 57, 13: 67, 14: 78, 15: 91,
            16: 107, 17: 125, 18: 146, 19: 171, 20: 200, 21: 234, 22: 274, 23: 321,
            24: 376, 25: 440, 26: 515, 27: 603, 28: 706, 29: 826, 30: 967, 31: 1132,
            32: 1326, 33: 1552, 34: 1817, 35: 2127, 36: 2490, 37: 2915, 38: 3413, 39: 3995,
            40: 4677, 41: 5476, 42: 6411, 43: 7505, 44: 8784, 45: 10287, 46: 12043, 47: 14099,
            48: 16507, 49: 19325, 50: 22624, 51: 26487, 52: 31013, 53: 36304, 54: 42502, 55: 49759,
            56: 58255, 57: 68201, 58: 79846, 59: 93479, 60: 109439, 61: 128125, 62: 150000, 63: 150000
        }
        
        # TBS (Transport Block Size) 近似计算 (简化版本)
        self.tbs_approximate = {
            i: i * 1000 + 500 for i in range(36)  # 简化的TBS估算
        }
    
    def load_data(self):
        """加载BSR报告数据"""
        try:
            self.data = pd.read_csv(self.report_file, sep='\t')
            print(f"成功加载 {len(self.data)} 条BSR记录")
            return True
        except Exception as e:
            print(f"加载数据失败: {e}")
            return False
    
    def calculate_metrics(self):
        """计算资源分配效率指标"""
        if self.data is None:
            print("请先加载数据")
            return
        
        # 过滤有效数据
        valid_data = self.data[
            (self.data['LCG_0'] != '-') | 
            (self.data['LCG_1'] != '-') | 
            (self.data['LCG_2'] != '-') | 
            (self.data['LCG_3'] != '-')
        ].copy()
        
        print(f"有效BSR记录: {len(valid_data)} 条")
        
        # 计算请求的总缓冲区大小
        def safe_int(x):
            return int(x) if x != '-' else 0
        
        valid_data['total_buffer_request'] = (
            valid_data['LCG_0'].apply(safe_int) +
            valid_data['LCG_1'].apply(safe_int) + 
            valid_data['LCG_2'].apply(safe_int) +
            valid_data['LCG_3'].apply(safe_int)
        )
        
        # 转换为实际字节数
        valid_data['requested_bytes'] = valid_data['total_buffer_request'].apply(
            lambda x: self.bsr_table.get(x, 0)
        )
        
        # 计算实际分配的资源
        valid_data['allocated_rbs'] = valid_data['Num_RBs'].apply(
            lambda x: int(x) if x != '-' else 0
        )
        
        # 估算实际可传输字节数 (简化计算)
        valid_data['allocated_bytes'] = valid_data['allocated_rbs'] * 144  # 每RB约144字节
        
        # 计算分配效率
        valid_data['allocation_efficiency'] = np.where(
            valid_data['requested_bytes'] > 0,
            valid_data['allocated_bytes'] / valid_data['requested_bytes'],
            0
        )
        
        # 限制效率值在合理范围内
        valid_data['allocation_efficiency'] = np.clip(valid_data['allocation_efficiency'], 0, 2)
        
        self.analyzed_data = valid_data
        return valid_data
    
    def generate_statistics(self):
        """生成统计报告"""
        if not hasattr(self, 'analyzed_data'):
            print("请先执行calculate_metrics()")
            return
        
        data = self.analyzed_data
        
        print("\n" + "="*60)
        print("蜂窝网络BSR资源分配效率分析报告")
        print("="*60)
        
        # 基本统计
        print(f"\n📊 基本统计:")
        print(f"总记录数: {len(data)}")
        print(f"有请求记录数: {len(data[data['requested_bytes'] > 0])}")
        print(f"有分配记录数: {len(data[data['allocated_bytes'] > 0])}")
        
        # 资源请求统计
        print(f"\n📈 资源请求统计:")
        requested = data[data['requested_bytes'] > 0]['requested_bytes']
        if len(requested) > 0:
            print(f"平均请求: {requested.mean():.0f} 字节")
            print(f"中位数请求: {requested.median():.0f} 字节")
            print(f"最大请求: {requested.max():.0f} 字节")
        
        # 资源分配统计
        print(f"\n📉 资源分配统计:")
        allocated = data[data['allocated_bytes'] > 0]['allocated_bytes']
        if len(allocated) > 0:
            print(f"平均分配: {allocated.mean():.0f} 字节")
            print(f"中位数分配: {allocated.median():.0f} 字节")
            print(f"最大分配: {allocated.max():.0f} 字节")
        
        # 分配效率统计
        print(f"\n⚡ 分配效率统计:")
        efficiency = data[data['allocation_efficiency'] > 0]['allocation_efficiency']
        if len(efficiency) > 0:
            print(f"平均效率: {efficiency.mean():.2f} ({efficiency.mean()*100:.1f}%)")
            print(f"中位数效率: {efficiency.median():.2f} ({efficiency.median()*100:.1f}%)")
            print(f"效率 < 0.5 的比例: {(efficiency < 0.5).mean()*100:.1f}%")
            print(f"效率 < 0.7 的比例: {(efficiency < 0.7).mean()*100:.1f}%")
            print(f"效率 > 1.0 的比例: {(efficiency > 1.0).mean()*100:.1f}%")
        
        # 资源利用不足分析
        underutilized = data[
            (data['requested_bytes'] > 0) & 
            (data['allocation_efficiency'] < 0.5)
        ]
        print(f"\n🚨 资源严重不足分配 (效率<50%):")
        print(f"记录数: {len(underutilized)} ({len(underutilized)/len(data)*100:.1f}%)")
        
        if len(underutilized) > 0:
            avg_waste = underutilized['requested_bytes'].mean() - underutilized['allocated_bytes'].mean()
            print(f"平均浪费: {avg_waste:.0f} 字节/次")
        
        return data
    
    def plot_analysis(self):
        """生成分析图表"""
        if not hasattr(self, 'analyzed_data'):
            print("请先执行calculate_metrics()")
            return
        
        data = self.analyzed_data
        
        # 创建图表
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('蜂窝网络BSR资源分配效率分析', fontsize=16, y=0.95)
        
        # 1. 请求 vs 分配散点图
        valid_pairs = data[(data['requested_bytes'] > 0) & (data['allocated_bytes'] > 0)]
        axes[0, 0].scatter(valid_pairs['requested_bytes'], valid_pairs['allocated_bytes'], 
                          alpha=0.6, s=20, color='steelblue')
        axes[0, 0].plot([0, valid_pairs['requested_bytes'].max()], [0, valid_pairs['requested_bytes'].max()], 
                       'r--', label='理想分配线')
        axes[0, 0].set_xlabel('请求字节数')
        axes[0, 0].set_ylabel('分配字节数')
        axes[0, 0].set_title('请求 vs 实际分配资源')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)
        
        # 2. 分配效率分布直方图
        efficiency_data = data[data['allocation_efficiency'] > 0]['allocation_efficiency']
        axes[0, 1].hist(efficiency_data, bins=50, alpha=0.7, color='lightcoral', edgecolor='black')
        axes[0, 1].axvline(efficiency_data.mean(), color='red', linestyle='--', 
                          label=f'平均值: {efficiency_data.mean():.2f}')
        axes[0, 1].axvline(0.5, color='orange', linestyle='--', label='50%效率线')
        axes[0, 1].axvline(1.0, color='green', linestyle='--', label='100%效率线')
        axes[0, 1].set_xlabel('分配效率')
        axes[0, 1].set_ylabel('频次')
        axes[0, 1].set_title('资源分配效率分布')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)
        
        # 3. 时间序列分析
        if len(data) > 100:
            sample_data = data.iloc[::max(1, len(data)//100)]  # 采样显示
        else:
            sample_data = data
            
        axes[1, 0].plot(range(len(sample_data)), sample_data['requested_bytes'], 
                       label='请求字节', alpha=0.7, color='blue')
        axes[1, 0].plot(range(len(sample_data)), sample_data['allocated_bytes'], 
                       label='分配字节', alpha=0.7, color='red')
        axes[1, 0].set_xlabel('时间序列')
        axes[1, 0].set_ylabel('字节数')
        axes[1, 0].set_title('资源请求与分配时间趋势')
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3)
        
        # 4. LCG分布分析
        lcg_data = []
        for i in range(4):
            lcg_col = f'LCG_{i}'
            valid_lcg = data[data[lcg_col] != '-'][lcg_col].apply(int)
            if len(valid_lcg) > 0:
                lcg_data.append(valid_lcg.values)
        
        if lcg_data:
            axes[1, 1].boxplot(lcg_data, labels=[f'LCG_{i}' for i in range(len(lcg_data))])
            axes[1, 1].set_ylabel('BSR值')
            axes[1, 1].set_title('各LCG缓冲区状态分布')
            axes[1, 1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig('bsr_analysis_report.png', dpi=300, bbox_inches='tight')
        plt.show()
    
    def export_results(self, filename="bsr_efficiency_analysis.csv"):
        """导出分析结果"""
        if not hasattr(self, 'analyzed_data'):
            print("请先执行calculate_metrics()")
            return
        
        # 导出详细数据
        export_data = self.analyzed_data[[
            'Timestamp', 'SubFN', 'SysFN', 'LCG_0', 'LCG_1', 'LCG_2', 'LCG_3',
            'Num_RBs', 'TBS_Index', 'total_buffer_request', 'requested_bytes',
            'allocated_bytes', 'allocation_efficiency'
        ]].copy()
        
        export_data.to_csv(filename, index=False)
        print(f"\n分析结果已导出到: {filename}")

def main():
    print("🔍 蜂窝网络BSR资源分配效率分析工具")
    print("="*50)
    
    analyzer = BSRAnalyzer("diag_report.txt")
    
    # 加载数据
    if not analyzer.load_data():
        return
    
    # 计算指标
    print("\n📊 正在计算资源分配效率...")
    analyzer.calculate_metrics()
    
    # 生成统计报告
    analyzer.generate_statistics()
    
    # 生成图表
    print("\n📈 正在生成分析图表...")
    analyzer.plot_analysis()
    
    # 导出结果
    analyzer.export_results()
    
    print("\n✅ 分析完成!")
    print("\n💡 分析结果解读:")
    print("- 效率 < 50%: 资源严重不足，可能影响WebRTC性能")
    print("- 效率 50-70%: 资源分配保守，有优化空间")  
    print("- 效率 70-100%: 资源分配合理")
    print("- 效率 > 100%: 资源过度分配或测量误差")

if __name__ == "__main__":
    main()
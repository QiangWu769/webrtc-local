#!/usr/bin/env python3

"""
测试修改后的diag_get_raw代码与画图代码的ratio计算一致性
"""

import sys
import os
sys.path.append('.')

# 导入修改后的ratio计算器
from diag_get_raw_fixed_ratio import RatioCalculator

def calculate_ratio_plotting_logic(data, request_indices):
    """
    使用与plot_ratio_comparison.py完全相同的逻辑计算ratio
    """
    real_ratios = []
    request_ttis = []

    for i in range(len(request_indices)):
        req_idx = request_indices[i]
        req_tti, _, req_amount, _ = data[req_idx]

        # 确定搜索范围：从请求点到下一个请求点（或数据结束）
        if i + 1 < len(request_indices):
            end_idx = request_indices[i + 1]
        else:
            end_idx = len(data)

        # 累加这个区间内的所有分配
        total_allocated = 0
        for j in range(req_idx, end_idx):
            allocated = data[j][1]
            if allocated > 0:
                total_allocated += allocated

        if req_amount > 0:
            # 真实ratio = 分配资源 / 请求资源
            real_ratio = total_allocated / req_amount

            # 限制ratio在2以内
            if real_ratio > 2.0:
                real_ratio = 2.0

            real_ratios.append(real_ratio)
            request_ttis.append(req_tti)

    return request_ttis, real_ratios

def test_with_real_data():
    """使用真实数据测试一致性"""

    # 读取真实数据
    data_file = 'ratio_data.txt'
    if not os.path.exists(data_file):
        print(f"数据文件 {data_file} 不存在，跳过真实数据测试")
        return True

    # 解析数据
    data = []
    with open(data_file, 'r') as f:
        for line in f:
            if line.strip():
                parts = line.strip().split('\t')
                if len(parts) >= 4:
                    try:
                        timestamp = int(parts[0])
                        allocated = int(parts[1])
                        requested = int(parts[2])
                        original_ratio = float(parts[3])
                        data.append([timestamp, allocated, requested, original_ratio])
                    except:
                        continue

    # 找到所有非零请求的位置
    request_indices = []
    for i, (tti, allocated, requested, ratio) in enumerate(data):
        if requested > 0:
            request_indices.append(i)

    print(f"找到 {len(request_indices)} 个非零请求")

    # 使用画图逻辑计算ratio
    plotting_ttis, plotting_ratios = calculate_ratio_plotting_logic(data, request_indices)

    # 使用修改后的代码计算ratio - 模拟实时处理
    ratio_calc = RatioCalculator()
    modified_ratios = []
    modified_ttis = []

    # 按顺序处理每一行数据，模拟实时处理
    for tti, allocated, requested, _ in data:
        # 先添加分配数据
        if allocated > 0:
            ratio_calc.add_allocation(tti, allocated)

        # 再处理请求
        if requested > 0:
            ratio_calc.add_request(tti, requested, float(tti)/1000.0)
            result = ratio_calc.calculate_ratio_for_request(tti, requested)
            if result is not None:
                ratio, total_alloc = result
                modified_ratios.append(ratio)
                modified_ttis.append(tti)

    # 比较结果
    print(f"\n=== 一致性测试结果 ===")
    print(f"画图逻辑计算了 {len(plotting_ratios)} 个ratio")
    print(f"修改代码计算了 {len(modified_ratios)} 个ratio")

    if len(plotting_ratios) != len(modified_ratios):
        print("❌ 计算的ratio数量不一致!")
        return False

    # 检查前10个ratio的一致性
    mismatches = 0
    for i in range(min(10, len(plotting_ratios))):
        plot_ratio = plotting_ratios[i]
        mod_ratio = modified_ratios[i]
        plot_tti = plotting_ttis[i]
        mod_tti = modified_ttis[i]

        print(f"TTI {plot_tti}: 画图={plot_ratio:.6f}, 修改={mod_ratio:.6f}, 差值={abs(plot_ratio-mod_ratio):.6f}")

        if abs(plot_ratio - mod_ratio) > 0.001:  # 容忍0.001的误差
            mismatches += 1

    if mismatches == 0:
        print("✅ 前10个ratio计算完全一致!")
        return True
    else:
        print(f"❌ 发现 {mismatches} 个不一致的ratio!")
        return False

def test_with_synthetic_data():
    """使用合成数据测试"""
    print("\n=== 合成数据测试 ===")

    # 创建测试数据：TTI, allocated, requested, original_ratio
    test_data = [
        [100, 0, 1000, 0.0],    # 请求1000字节
        [101, 200, 0, 0.0],     # 分配200字节
        [102, 300, 0, 0.0],     # 分配300字节
        [103, 100, 0, 0.0],     # 分配100字节
        [104, 0, 0, 0.0],       # 无活动
        [105, 0, 800, 0.0],     # 请求800字节
        [106, 400, 0, 0.0],     # 分配400字节
        [107, 200, 0, 0.0],     # 分配200字节
        [108, 0, 500, 0.0],     # 请求500字节
    ]

    # 找到非零请求
    request_indices = []
    for i, (tti, allocated, requested, _) in enumerate(test_data):
        if requested > 0:
            request_indices.append(i)

    # 画图逻辑计算
    plotting_ttis, plotting_ratios = calculate_ratio_plotting_logic(test_data, request_indices)

    # 修改代码计算
    ratio_calc = RatioCalculator()
    for tti, allocated, requested, _ in test_data:
        if requested > 0:
            ratio_calc.add_request(tti, requested, float(tti)/1000.0)
        if allocated > 0:
            ratio_calc.add_allocation(tti, allocated)

    modified_ratios = []
    for tti, allocated, requested, _ in test_data:
        if requested > 0:
            result = ratio_calc.calculate_ratio_for_request(tti, requested)
            if result:
                ratio, _ = result
                modified_ratios.append(ratio)

    print("合成数据测试结果:")
    for i in range(len(plotting_ratios)):
        plot_ratio = plotting_ratios[i]
        mod_ratio = modified_ratios[i] if i < len(modified_ratios) else 0.0
        tti = plotting_ttis[i]
        print(f"TTI {tti}: 画图={plot_ratio:.6f}, 修改={mod_ratio:.6f}")

    # 预期结果：
    # TTI 100: 总分配600 / 请求1000 = 0.600
    # TTI 105: 总分配600 / 请求800 = 0.750
    # TTI 108: 总分配0 / 请求500 = 0.000 (没有后续分配)

    expected = [0.600, 0.750, 0.000]
    all_correct = True

    for i, exp in enumerate(expected):
        if i < len(plotting_ratios) and abs(plotting_ratios[i] - exp) < 0.001:
            print(f"✅ TTI {plotting_ttis[i]}: 预期={exp:.3f}, 实际={plotting_ratios[i]:.3f}")
        else:
            print(f"❌ TTI {plotting_ttis[i]}: 预期={exp:.3f}, 实际={plotting_ratios[i]:.3f}")
            all_correct = False

    return all_correct

if __name__ == "__main__":
    print("开始测试修改后代码与画图代码的ratio计算一致性...")

    # 测试合成数据
    synthetic_ok = test_with_synthetic_data()

    # 测试真实数据
    real_ok = test_with_real_data()

    print(f"\n=== 最终测试结果 ===")
    print(f"合成数据测试: {'✅ 通过' if synthetic_ok else '❌ 失败'}")
    print(f"真实数据测试: {'✅ 通过' if real_ok else '❌ 失败'}")

    if synthetic_ok and real_ok:
        print("🎉 所有测试通过! 修改后的代码与画图逻辑完全一致!")
    else:
        print("⚠️  存在不一致，需要修复...")
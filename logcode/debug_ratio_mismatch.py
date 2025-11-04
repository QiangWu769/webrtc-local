#!/usr/bin/env python3

"""
调试ratio不匹配的问题
"""

import sys
sys.path.append('.')

def debug_specific_case():
    """调试特定的不匹配案例"""

    # 读取真实数据
    data = []
    with open('ratio_data.txt', 'r') as f:
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

    # 找到TTI 9103的情况
    target_tti = 9103

    print(f"=== 调试TTI {target_tti} ===")

    # 找到这个TTI的位置
    target_index = None
    for i, (tti, allocated, requested, _) in enumerate(data):
        if tti == target_tti and requested > 0:
            target_index = i
            break

    if target_index is None:
        print("找不到目标TTI")
        return

    print(f"找到TTI {target_tti}在第{target_index}行")
    target_data = data[target_index]
    print(f"目标请求: TTI={target_data[0]}, allocated={target_data[1]}, requested={target_data[2]}")

    # 找到所有非零请求的位置
    request_indices = []
    for i, (tti, allocated, requested, ratio) in enumerate(data):
        if requested > 0:
            request_indices.append(i)

    # 找到目标请求在request_indices中的位置
    req_pos = None
    for i, idx in enumerate(request_indices):
        if idx == target_index:
            req_pos = i
            break

    print(f"这是第{req_pos}个非零请求")

    # 使用画图逻辑计算
    if req_pos + 1 < len(request_indices):
        end_idx = request_indices[req_pos + 1]
        next_request_tti = data[end_idx][0]
    else:
        end_idx = len(data)
        next_request_tti = "END"

    print(f"下一个请求在第{end_idx}行, TTI={next_request_tti}")

    # 累加区间内的分配
    total_allocated = 0
    allocation_details = []
    for j in range(target_index, end_idx):
        allocated = data[j][1]
        if allocated > 0:
            total_allocated += allocated
            allocation_details.append((data[j][0], allocated))

    plotting_ratio = total_allocated / target_data[2]
    if plotting_ratio > 2.0:
        plotting_ratio = 2.0

    print(f"画图逻辑: 总分配={total_allocated}, 请求={target_data[2]}, ratio={plotting_ratio:.6f}")
    print(f"分配详情: {allocation_details}")

    # 现在使用修改后的逻辑 - 模拟实时处理
    from diag_get_raw_fixed_ratio import RatioCalculator

    ratio_calc = RatioCalculator()
    modified_ratio = None
    modified_allocated = None

    # 模拟实时处理，按顺序添加数据
    for i in range(len(data)):
        tti, allocated, requested, _ = data[i]

        # 先添加分配
        if allocated > 0:
            ratio_calc.add_allocation(tti, allocated)

        # 再处理请求
        if requested > 0:
            ratio_calc.add_request(tti, requested, float(tti)/1000.0)
            result = ratio_calc.calculate_ratio_for_request(tti, requested)
            if result and tti == target_tti:
                modified_ratio, modified_allocated = result
                break

    if modified_ratio is not None:
        print(f"修改逻辑(实时): 总分配={modified_allocated}, ratio={modified_ratio:.6f}")
    else:
        print("修改逻辑(实时): 无法计算ratio")

    print()

if __name__ == "__main__":
    debug_specific_case()
import numpy as np

# Read and parse the data
data = []
with open('ratio_data.txt', 'r') as f:
    for line in f:
        if line.strip():
            parts = line.strip().split('\t')
            if len(parts) >= 4:
                try:
                    timestamp = int(parts[0])
                    allocated = int(parts[1])  # 分配资源
                    requested = int(parts[2])  # 请求资源
                    original_ratio = float(parts[3])
                    data.append([timestamp, allocated, requested, original_ratio])
                except:
                    continue

print("重新计算真实ratio...")

# 找到所有非零请求的位置
request_indices = []
for i, (tti, allocated, requested, ratio) in enumerate(data):
    if requested > 0:
        request_indices.append(i)

print(f"找到 {len(request_indices)} 个非零请求")

# 计算每个请求对应的真实ratio
real_ratios = []

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
    allocation_count = 0

    for j in range(req_idx, end_idx):
        allocated = data[j][1]
        if allocated > 0:
            total_allocated += allocated
            allocation_count += 1

    if req_amount > 0:
        real_ratio = total_allocated / req_amount
        real_ratios.append({
            'request_tti': req_tti,
            'request_amount': req_amount,
            'total_allocated': total_allocated,
            'allocation_count': allocation_count,
            'real_ratio': real_ratio,
            'start_idx': req_idx,
            'end_idx': end_idx
        })

# 输出统计结果
if real_ratios:
    ratios_array = [r['real_ratio'] for r in real_ratios]
    print(f"\n真实ratio统计:")
    print(f"总请求数: {len(real_ratios)}")
    print(f"平均ratio: {np.mean(ratios_array):.3f}")
    print(f"中位数ratio: {np.median(ratios_array):.3f}")
    print(f"最小ratio: {np.min(ratios_array):.3f}")
    print(f"最大ratio: {np.max(ratios_array):.3f}")
    print(f"标准差: {np.std(ratios_array):.3f}")

    print(f"\n前10个请求-分配匹配示例:")
    print("TTI\t请求\t分配总和\t分配次数\t真实ratio")
    print("-" * 55)
    for i in range(min(10, len(real_ratios))):
        r = real_ratios[i]
        print(f"{r['request_tti']}\t{r['request_amount']}\t{r['total_allocated']}\t{r['allocation_count']}\t{r['real_ratio']:.3f}")

    # 分析过度分配/不足分配情况
    over_allocated = sum(1 for r in ratios_array if r > 1.0)
    under_allocated = sum(1 for r in ratios_array if r < 1.0)
    exact_allocated = sum(1 for r in ratios_array if abs(r - 1.0) < 0.001)

    print(f"\n分配情况分析:")
    print(f"过度分配 (ratio>1): {over_allocated} ({over_allocated/len(real_ratios)*100:.1f}%)")
    print(f"不足分配 (ratio<1): {under_allocated} ({under_allocated/len(real_ratios)*100:.1f}%)")
    print(f"精确分配 (ratio≈1): {exact_allocated} ({exact_allocated/len(real_ratios)*100:.1f}%)")
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

print("分析请求-分配匹配模式...")

# 找到所有有请求的时间点
request_points = []
for i, (tti, allocated, requested, ratio) in enumerate(data):
    if requested > 0:
        request_points.append((i, tti, requested))

print(f"找到 {len(request_points)} 个请求点")

# 对每个请求点，找到后续的分配
real_ratios = []
unmatched_requests = []

for req_idx, req_tti, req_amount in request_points:
    total_allocated = 0
    allocation_count = 0

    # 在请求后的一定窗口内查找分配（比如50个TTI）
    search_window = 100
    start_search = req_idx + 1
    end_search = min(req_idx + search_window, len(data))

    for j in range(start_search, end_search):
        allocated = data[j][1]
        if allocated > 0:
            total_allocated += allocated
            allocation_count += 1

    if total_allocated > 0:
        real_ratio = total_allocated / req_amount
        real_ratios.append({
            'request_tti': req_tti,
            'request_amount': req_amount,
            'total_allocated': total_allocated,
            'allocation_count': allocation_count,
            'real_ratio': real_ratio
        })
    else:
        unmatched_requests.append({
            'request_tti': req_tti,
            'request_amount': req_amount
        })

print(f"\n成功匹配的请求-分配对: {len(real_ratios)}")
print(f"未匹配到分配的请求: {len(unmatched_requests)}")

if real_ratios:
    ratios_array = [r['real_ratio'] for r in real_ratios]
    print(f"\n真实ratio统计:")
    print(f"平均值: {np.mean(ratios_array):.3f}")
    print(f"中位数: {np.median(ratios_array):.3f}")
    print(f"最小值: {np.min(ratios_array):.3f}")
    print(f"最大值: {np.max(ratios_array):.3f}")
    print(f"标准差: {np.std(ratios_array):.3f}")

    print(f"\n前10个匹配示例:")
    for i in range(min(10, len(real_ratios))):
        r = real_ratios[i]
        print(f"TTI {r['request_tti']}: 请求{r['request_amount']} -> 分配{r['total_allocated']} (分{r['allocation_count']}次) = ratio {r['real_ratio']:.3f}")

# 分析分配延迟模式
if real_ratios:
    allocation_counts = [r['allocation_count'] for r in real_ratios]
    print(f"\n分配次数分布:")
    unique_counts, count_freq = np.unique(allocation_counts, return_counts=True)
    for count, freq in zip(unique_counts, count_freq):
        print(f"  分配{count}次: {freq}个请求 ({freq/len(real_ratios)*100:.1f}%)")
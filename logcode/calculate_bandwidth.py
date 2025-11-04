import numpy as np
import matplotlib.pyplot as plt

def analyze_bandwidth(filename, dataset_name):
    # Read and parse the data
    data = []
    with open(filename, 'r') as f:
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

    print(f"分析 {dataset_name} 的带宽特征...")

    # 找到所有非零请求的位置
    request_indices = []
    for i, (tti, allocated, requested, ratio) in enumerate(data):
        if requested > 0:
            request_indices.append(i)

    # 计算每个请求的实际带宽
    bandwidths = []
    request_ttis = []
    tti_spans = []

    for i in range(len(request_indices)):
        req_idx = request_indices[i]
        req_tti, _, req_amount, _ = data[req_idx]

        # 确定搜索范围：从请求点到下一个请求点（或数据结束）
        if i + 1 < len(request_indices):
            end_idx = request_indices[i + 1]
            next_tti = data[request_indices[i + 1]][0]
        else:
            end_idx = len(data)
            next_tti = data[-1][0]

        # 累加这个区间内的所有分配
        total_allocated = 0
        for j in range(req_idx, end_idx):
            allocated = data[j][1]
            if allocated > 0:
                total_allocated += allocated

        # 计算TTI跨度（处理循环重置）
        if next_tti >= req_tti:
            tti_span = next_tti - req_tti
        else:
            tti_span = (10240 - req_tti) + next_tti  # 处理TTI重置

        if tti_span > 0:
            # 带宽 = 分配资源 / TTI跨度 (资源单位/ms)
            bandwidth = total_allocated / tti_span
            bandwidths.append(bandwidth)
            request_ttis.append(req_tti)
            tti_spans.append(tti_span)

    bandwidths = np.array(bandwidths)
    tti_spans = np.array(tti_spans)

    print(f"数据集: {dataset_name}")
    print(f"请求数量: {len(bandwidths)}")
    print(f"带宽统计 (资源单位/ms):")
    print(f"  平均带宽: {np.mean(bandwidths):.3f}")
    print(f"  中位数带宽: {np.median(bandwidths):.3f}")
    print(f"  最小带宽: {np.min(bandwidths):.3f}")
    print(f"  最大带宽: {np.max(bandwidths):.3f}")
    print(f"  标准差: {np.std(bandwidths):.3f}")

    print(f"TTI跨度统计:")
    print(f"  平均TTI跨度: {np.mean(tti_spans):.1f} ms")
    print(f"  中位数TTI跨度: {np.median(tti_spans):.1f} ms")
    print(f"  TTI跨度范围: {np.min(tti_spans):.0f} - {np.max(tti_spans):.0f} ms")

    # 带宽分布分析
    print(f"带宽分布:")
    ranges = [
        (0, 1, '< 1'),
        (1, 5, '1-5'),
        (5, 10, '5-10'),
        (10, 20, '10-20'),
        (20, 50, '20-50'),
        (50, float('inf'), '> 50')
    ]

    for min_val, max_val, label in ranges:
        if max_val == float('inf'):
            count = np.sum(bandwidths > min_val)
        else:
            count = np.sum((bandwidths >= min_val) & (bandwidths < max_val))
        percentage = count / len(bandwidths) * 100
        print(f"  {label} 资源单位/ms: {count} ({percentage:.1f}%)")

    return bandwidths, request_ttis, dataset_name

# 分析两个数据集
print("=" * 60)
bw1, ttis1, name1 = analyze_bandwidth('ratio_data.txt', '原始数据')
print("\n" + "=" * 60)
bw2, ttis2, name2 = analyze_bandwidth('verizon——ratio_data.txt', 'Verizon数据')

# 绘制带宽对比图
plt.figure(figsize=(15, 10))

# 重构连续时间轴
def reconstruct_time(request_ttis):
    continuous_time = []
    time_offset = 0
    max_tti = 10240

    for i in range(len(request_ttis)):
        if i > 0 and request_ttis[i] < request_ttis[i-1]:
            time_offset += max_tti
        continuous_time.append(request_ttis[i] + time_offset)

    return np.array(continuous_time) / 1000.0  # 转换为秒

time1 = reconstruct_time(ttis1)
time2 = reconstruct_time(ttis2)

plt.subplot(2, 1, 1)
plt.plot(time1, bw1, linewidth=0.8, alpha=0.7, color='red', label=name1)
plt.xlabel('Time (seconds)')
plt.ylabel('Bandwidth (units/ms)')
plt.title(f'{name1} - Bandwidth vs Time')
plt.grid(True, alpha=0.3)
plt.legend()
plt.ylim(0, min(50, np.percentile(bw1, 95)))  # 限制Y轴到95%分位数或50

plt.subplot(2, 1, 2)
plt.plot(time2, bw2, linewidth=0.8, alpha=0.7, color='purple', label=name2)
plt.xlabel('Time (seconds)')
plt.ylabel('Bandwidth (units/ms)')
plt.title(f'{name2} - Bandwidth vs Time')
plt.grid(True, alpha=0.3)
plt.legend()
plt.ylim(0, min(50, np.percentile(bw2, 95)))  # 限制Y轴到95%分位数或50

plt.tight_layout()
plt.savefig('bandwidth_comparison.png', dpi=300, bbox_inches='tight')
plt.show()

print(f"\n带宽对比图已保存到: bandwidth_comparison.png")

# 总结对比
print(f"\n" + "=" * 60)
print("带宽对比总结:")
print(f"{name1} 平均带宽: {np.mean(bw1):.3f} 资源单位/ms")
print(f"{name2} 平均带宽: {np.mean(bw2):.3f} 资源单位/ms")
print(f"差异: {((np.mean(bw1) - np.mean(bw2)) / np.mean(bw2) * 100):+.1f}%")
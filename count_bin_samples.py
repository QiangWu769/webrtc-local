#!/usr/bin/env python3
import re
import numpy as np

# 解析日志
data = []
with open('/home/wuq/webrtc-local/webrtc_config_results/sender_local.log', 'r') as f:
    current_score = None
    current_bw = None

    for line in f:
        if '[AIMD-SatBoost]' in line:
            match = re.search(r'Base Score: ([\d.e+-]+)', line)
            if match:
                current_score = float(match.group(1))

        if '[GCC-OUTPUT]' in line:
            match = re.search(r'FinalTargetBps: ([\d.]+)', line)
            if match:
                current_bw = float(match.group(1)) / 1000000.0

        if current_score is not None and current_bw is not None:
            data.append({'score': current_score, 'bandwidth': current_bw})
            current_score = None
            current_bw = None

scores = np.array([d['score'] for d in data])
bandwidths = np.array([d['bandwidth'] for d in data])

print('='*80)
print('                      每个Score区间的样本分布')
print('='*80)
print(f"{'Score区间':>12} | {'样本数':>8} | {'占比':>8} | {'平均BW':>10} | {'BW范围':>20}")
print('-'*80)

bins = [(0, 10), (10, 30), (30, 50), (50, 70), (70, 90), (90, 100)]

for low, high in bins:
    mask = (scores >= low) & (scores < high)
    count = np.sum(mask)
    ratio = count / len(scores) * 100

    if count > 0:
        mean_bw = np.mean(bandwidths[mask])
        min_bw = np.min(bandwidths[mask])
        max_bw = np.max(bandwidths[mask])
        print(f'[{low:>3}, {high:>3}) | {count:>8} | {ratio:>7.1f}% | {mean_bw:>9.2f}M | [{min_bw:.2f}, {max_bw:.2f}]')
    else:
        print(f'[{low:>3}, {high:>3}) | {count:>8} | {ratio:>7.1f}% | {"N/A":>10} | {"N/A":>20}')

print('-'*80)
print(f'{"总计":>12} | {len(scores):>8} | {100.0:>7.1f}% | {np.mean(bandwidths):>9.2f}M | [{bandwidths.min():.2f}, {bandwidths.max():.2f}]')
print('='*80)

# 额外统计
print(f'\n📊 关键统计:')
print(f'   低分区间[0-10): {np.sum(scores < 10)} 样本 ({np.sum(scores < 10)/len(scores)*100:.1f}%)')
print(f'   中分区间[10-70): {np.sum((scores >= 10) & (scores < 70))} 样本 ({np.sum((scores >= 10) & (scores < 70))/len(scores)*100:.1f}%)')
print(f'   高分区间[70-100): {np.sum(scores >= 70)} 样本 ({np.sum(scores >= 70)/len(scores)*100:.1f}%)')
print(f'   峰值区间[90-100): {np.sum(scores >= 90)} 样本 ({np.sum(scores >= 90)/len(scores)*100:.1f}%)')

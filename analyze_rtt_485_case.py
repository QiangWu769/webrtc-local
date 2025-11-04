#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析RTT=485ms时为何没有触发Overuse
展示RTT、Modified Trend、Accumulated Delay的关系
"""

import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

# 数据点：从日志中提取的关键时间点
data = [
    # (相对时间秒, RTT ms, Modified Trend, Accumulated Delay ms, State)
    (51.7, 323, -0.465, 24, 'Normal'),
    (51.7, 323, -0.346, 1, 'Normal'),
    (52.1, 485, -0.197, 21, 'Normal'),  # RTT峰值
    (52.1, 485, 0.164, 53, 'Normal'),
    (52.1, 485, 0.505, 22, 'Normal'),
    (52.4, 411, 0.806, 12, 'Normal'),
    (52.4, 411, 0.944, 5, 'Normal'),
    (52.4, 411, 1.126, 19, 'Normal'),
    (52.4, 411, 1.358, 27, 'Normal'),
    (52.4, 411, 1.554, 28, 'Normal'),
    (52.4, 411, 1.584, 8, 'Normal'),
    (52.4, 411, 1.540, 18, 'Normal'),
    (52.5, 168, 1.466, 22, 'Normal'),
]

times = [d[0] for d in data]
rtts = [d[1] for d in data]
trends = [d[2] for d in data]
delays = [d[3] for d in data]
states = [d[4] for d in data]

# 创建图表
fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

# 子图1: RTT
ax1 = axes[0]
ax1.plot(times, rtts, 'o-', color='#2E86AB', linewidth=2.5, markersize=8, label='Corrected RTT')
ax1.axhline(y=485, color='red', linestyle='--', alpha=0.5, label='Peak RTT (485ms)')
ax1.set_ylabel('RTT (ms)', fontsize=12, fontweight='bold')
ax1.set_title('RTT 485ms未触发Overuse原因分析', fontsize=14, fontweight='bold')
ax1.grid(True, alpha=0.3)
ax1.legend(fontsize=10, loc='upper right')

# 标注RTT峰值
peak_idx = rtts.index(max(rtts))
ax1.annotate(f'Peak: {rtts[peak_idx]}ms\nNo Overuse!',
            xy=(times[peak_idx], rtts[peak_idx]),
            xytext=(times[peak_idx] + 0.1, rtts[peak_idx] + 50),
            fontsize=11,
            fontweight='bold',
            color='red',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.8),
            arrowprops=dict(arrowstyle='->', color='red', lw=2))

# 添加统计信息
stats_text = f"Peak RTT: {max(rtts)} ms\nMin RTT: {min(rtts)} ms\nAll states: Normal"
ax1.text(0.02, 0.95, stats_text,
        transform=ax1.transAxes,
        fontsize=10,
        verticalalignment='top',
        bbox=dict(boxstyle='round,pad=0.5', facecolor='lightblue', alpha=0.8))

# 子图2: Modified Trend (GCC判断依据)
ax2 = axes[1]
ax2.plot(times, trends, 'o-', color='#FF6B35', linewidth=2.5, markersize=8, label='Modified Trend')
ax2.axhline(y=6, color='red', linestyle='--', linewidth=2, alpha=0.8, label='Overuse Threshold (6.0)')
ax2.axhline(y=0, color='gray', linestyle=':', alpha=0.5)
ax2.fill_between(times, 0, trends, alpha=0.3, color='#FF6B35')
ax2.set_ylabel('Modified Trend', fontsize=12, fontweight='bold')
ax2.set_title('Modified Trend vs Overuse阈值 (GCC判断依据)', fontsize=13, fontweight='bold')
ax2.grid(True, alpha=0.3)
ax2.legend(fontsize=10, loc='upper left')

# 标注关键点
max_trend = max(trends)
max_trend_idx = trends.index(max_trend)
ax2.annotate(f'Max trend: {max_trend:.3f}\n(仍 << 阈值6)',
            xy=(times[max_trend_idx], max_trend),
            xytext=(times[max_trend_idx] - 0.15, 4),
            fontsize=11,
            fontweight='bold',
            color='darkred',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='lightyellow', alpha=0.9),
            arrowprops=dict(arrowstyle='->', color='darkred', lw=2))

# 关键解释文本
explanation = "Modified Trend << 6\n→ 延迟梯度很小\n→ 无持续排队延迟累积\n→ 判定为Normal"
ax2.text(0.98, 0.97, explanation,
        transform=ax2.transAxes,
        fontsize=10,
        verticalalignment='top',
        horizontalalignment='right',
        bbox=dict(boxstyle='round,pad=0.6', facecolor='#FFE5E5', alpha=0.9, edgecolor='red', linewidth=2))

# 子图3: Accumulated Delay (排队延迟)
ax3 = axes[2]
ax3.plot(times, delays, 'o-', color='#00B4D8', linewidth=2.5, markersize=8, label='Accumulated Delay')
ax3.fill_between(times, 0, delays, alpha=0.3, color='#00B4D8')
ax3.set_ylabel('Accumulated Delay (ms)', fontsize=12, fontweight='bold')
ax3.set_xlabel('Time (seconds)', fontsize=12, fontweight='bold')
ax3.set_title('排队延迟 (Accumulated Delay) - 真正的拥塞指标', fontsize=13, fontweight='bold')
ax3.grid(True, alpha=0.3)
ax3.legend(fontsize=10, loc='upper right')

# 对比说明
comparison_text = f"RTT峰值: 485ms\n排队延迟: ~22ms (仅4.5%)\n→ 高RTT主要来自传播延迟\n→ 非拥塞导致"
ax3.text(0.02, 0.97, comparison_text,
        transform=ax3.transAxes,
        fontsize=10,
        verticalalignment='top',
        bbox=dict(boxstyle='round,pad=0.6', facecolor='lightgreen', alpha=0.9, edgecolor='darkgreen', linewidth=2))

# 标注拥塞窗口推回信息
pushback_text = "发送速率已限制到30kbps\n(原始速率19.2Mbps的0.16%)\n→ 不会产生新的排队延迟"
ax3.text(0.98, 0.97, pushback_text,
        transform=ax3.transAxes,
        fontsize=10,
        verticalalignment='top',
        horizontalalignment='right',
        bbox=dict(boxstyle='round,pad=0.6', facecolor='#FFFACD', alpha=0.9, edgecolor='orange', linewidth=2))

plt.tight_layout()
plt.savefig('/home/wuq/webrtc-local/rtt_485_no_overuse_analysis.png', dpi=300, bbox_inches='tight')
print("[*] 分析图表已保存: rtt_485_no_overuse_analysis.png")
print("\n关键发现:")
print(f"1. RTT峰值: {max(rtts)}ms")
print(f"2. Modified Trend最大值: {max(trends):.3f} (远小于阈值6)")
print(f"3. 排队延迟范围: {min(delays)}-{max(delays)}ms (平均{np.mean(delays):.1f}ms)")
print(f"4. 所有状态: {set(states)}")
print("\n结论: GCC正确识别出高RTT来自传播延迟而非拥塞排队")

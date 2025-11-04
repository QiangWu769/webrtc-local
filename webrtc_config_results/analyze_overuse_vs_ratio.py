#!/usr/bin/env python3
"""
分析 Overuse 检测次数与 Cellular Ratio 的关系
"""

import re
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats
from collections import defaultdict

def parse_overuse_and_ratio(log_path):
    """解析日志中的 overuse 状态和 ratio 数据"""

    # Patterns
    # Detector state: 0=Normal, 1=Overuse, 2=Underuse
    detector_state_pattern = r'\[DelayBWE-Decision\].*Detector state: (\d+)'

    # GCC decision snapshot with state
    gcc_snapshot_pattern = r'\[GCC-DECISION-SNAPSHOT\].*DelayState: (\w+)'

    # Ratio updates
    ratio_pattern = r'Resource ratio updated: ([\d.]+) \(smoothed: ([\d.]+)\), trend: ([-\d.]+)'

    # Trendline state
    trendline_pattern = r'\[Trendline\].*State: (\w+)'

    events = []
    current_detector_state = 0  # 0=Normal, 1=Overuse, 2=Underuse
    current_gcc_state = 'Normal'

    # Counters
    state_counts = defaultdict(int)
    overuse_count = 0
    normal_count = 0
    underuse_count = 0

    line_num = 0
    with open(log_path, 'r') as f:
        for line in f:
            line_num += 1

            # Track detector state from DelayBWE-Decision
            detector_match = re.search(detector_state_pattern, line)
            if detector_match:
                state = int(detector_match.group(1))
                current_detector_state = state

                if state == 0:
                    normal_count += 1
                elif state == 1:
                    overuse_count += 1
                elif state == 2:
                    underuse_count += 1

            # Track GCC state
            gcc_match = re.search(gcc_snapshot_pattern, line)
            if gcc_match:
                state_name = gcc_match.group(1)
                current_gcc_state = state_name
                state_counts[state_name] += 1

            # Track ratio with current state
            ratio_match = re.search(ratio_pattern, line)
            if ratio_match:
                raw_ratio = float(ratio_match.group(1))
                smoothed_ratio = float(ratio_match.group(2))
                trend = float(ratio_match.group(3))

                events.append({
                    'line': line_num,
                    'type': 'ratio',
                    'raw_ratio': raw_ratio,
                    'smoothed_ratio': smoothed_ratio,
                    'trend': trend,
                    'detector_state': current_detector_state,
                    'gcc_state': current_gcc_state
                })

    return {
        'events': events,
        'overuse_count': overuse_count,
        'normal_count': normal_count,
        'underuse_count': underuse_count,
        'state_counts': state_counts
    }

def analyze_overuse_ratio_relation(data):
    """分析 overuse 检测与 ratio 的关系"""

    events = data['events']
    ratio_events = [e for e in events if e['type'] == 'ratio']

    print("\n" + "="*80)
    print("OVERUSE 检测与 CELLULAR RATIO 关系分析")
    print("="*80)

    # State statistics
    print(f"\n" + "-"*80)
    print("延迟检测器状态统计")
    print("-"*80)
    print(f"总检测次数: {data['normal_count'] + data['overuse_count'] + data['underuse_count']}")
    print(f"  Normal (0):   {data['normal_count']} ({100*data['normal_count']/(data['normal_count']+data['overuse_count']+data['underuse_count']):.1f}%)")
    print(f"  Overuse (1):  {data['overuse_count']} ({100*data['overuse_count']/(data['normal_count']+data['overuse_count']+data['underuse_count']):.1f}%)")
    print(f"  Underuse (2): {data['underuse_count']} ({100*data['underuse_count']/(data['normal_count']+data['overuse_count']+data['underuse_count']):.1f}%)")

    print(f"\n" + "-"*80)
    print("GCC 状态统计")
    print("-"*80)
    for state, count in sorted(data['state_counts'].items()):
        print(f"  {state}: {count}")

    if not ratio_events:
        print("没有找到ratio事件")
        return None

    # Group ratios by detector state
    ratios_by_state = defaultdict(list)
    for e in ratio_events:
        state = e['detector_state']
        ratios_by_state[state].append(e['smoothed_ratio'])

    print(f"\n" + "-"*80)
    print("不同检测器状态下的 Smoothed Ratio 统计")
    print("-"*80)

    state_names = {0: 'Normal', 1: 'Overuse', 2: 'Underuse'}

    for state_id in sorted(ratios_by_state.keys()):
        ratios = ratios_by_state[state_id]
        state_name = state_names.get(state_id, f'Unknown({state_id})')

        print(f"\n{state_name} (状态 {state_id}):")
        print(f"  样本数: {len(ratios)}")
        if ratios:
            print(f"  均值: {np.mean(ratios):.3f}")
            print(f"  标准差: {np.std(ratios):.3f}")
            print(f"  范围: [{np.min(ratios):.3f}, {np.max(ratios):.3f}]")
            print(f"  中位数: {np.median(ratios):.3f}")

            # Ratio distribution in ranges
            low = sum(1 for r in ratios if r < 0.9)
            normal = sum(1 for r in ratios if 0.9 <= r <= 1.1)
            high = sum(1 for r in ratios if r > 1.1)

            print(f"  Ratio分布:")
            print(f"    低 (<0.9):    {low} ({100*low/len(ratios):.1f}%)")
            print(f"    正常 (0.9-1.1): {normal} ({100*normal/len(ratios):.1f}%)")
            print(f"    高 (>1.1):    {high} ({100*high/len(ratios):.1f}%)")

    # Calculate correlation between ratio and state transitions
    print(f"\n" + "-"*80)
    print("Ratio 与状态变化的关系")
    print("-"*80)

    # Count state transitions
    prev_state = None
    transitions = []
    for e in ratio_events:
        curr_state = e['detector_state']
        if prev_state is not None and curr_state != prev_state:
            transitions.append({
                'from': prev_state,
                'to': curr_state,
                'ratio': e['smoothed_ratio']
            })
        prev_state = curr_state

    print(f"\n状态转换总数: {len(transitions)}")

    # Transitions to overuse
    to_overuse = [t for t in transitions if t['to'] == 1]
    if to_overuse:
        print(f"\n转换到 Overuse: {len(to_overuse)} 次")
        ratios_to_overuse = [t['ratio'] for t in to_overuse]
        print(f"  触发时平均 Ratio: {np.mean(ratios_to_overuse):.3f}")
        print(f"  范围: [{np.min(ratios_to_overuse):.3f}, {np.max(ratios_to_overuse):.3f}]")

    # Transitions from overuse
    from_overuse = [t for t in transitions if t['from'] == 1]
    if from_overuse:
        print(f"\n从 Overuse 恢复: {len(from_overuse)} 次")
        ratios_from_overuse = [t['ratio'] for t in from_overuse]
        print(f"  恢复时平均 Ratio: {np.mean(ratios_from_overuse):.3f}")
        print(f"  范围: [{np.min(ratios_from_overuse):.3f}, {np.max(ratios_from_overuse):.3f}]")

    return {
        'ratio_events': ratio_events,
        'ratios_by_state': ratios_by_state,
        'transitions': transitions,
        'state_names': state_names
    }

def plot_overuse_ratio_analysis(data, analysis):
    """绘制 overuse 与 ratio 的关系图"""

    if not analysis:
        print("没有数据可绘制")
        return

    ratio_events = analysis['ratio_events']
    ratios_by_state = analysis['ratios_by_state']
    state_names = analysis['state_names']

    # Extract data
    smoothed_ratios = [e['smoothed_ratio'] for e in ratio_events]
    detector_states = [e['detector_state'] for e in ratio_events]

    fig = plt.figure(figsize=(18, 12))
    gs = fig.add_gridspec(3, 3, hspace=0.35, wspace=0.35)

    # Plot 1: Ratio time series with state overlay
    ax1 = fig.add_subplot(gs[0, :])

    # Color points by state
    colors = []
    for state in detector_states:
        if state == 0:  # Normal
            colors.append('green')
        elif state == 1:  # Overuse
            colors.append('red')
        elif state == 2:  # Underuse
            colors.append('blue')
        else:
            colors.append('gray')

    ax1.scatter(range(len(smoothed_ratios)), smoothed_ratios, c=colors, alpha=0.5, s=10)
    ax1.axhline(y=1.0, color='black', linestyle='--', linewidth=2, alpha=0.7, label='Target')
    ax1.fill_between(range(len(smoothed_ratios)), 0.9, 1.1, alpha=0.1, color='green')

    # Legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='green', label='Normal'),
        Patch(facecolor='red', label='Overuse'),
        Patch(facecolor='blue', label='Underuse')
    ]
    ax1.legend(handles=legend_elements, loc='upper right', fontsize=10)

    ax1.set_xlabel('Ratio Update Index', fontsize=11)
    ax1.set_ylabel('Smoothed Ratio', fontsize=11)
    ax1.set_title('Smoothed Ratio Over Time (Colored by Detector State)',
                  fontsize=13, fontweight='bold')
    ax1.grid(True, alpha=0.3)

    # Plot 2: Box plot of ratio by state
    ax2 = fig.add_subplot(gs[1, 0])

    box_data = []
    box_labels = []
    box_colors = []

    for state_id in sorted(ratios_by_state.keys()):
        if len(ratios_by_state[state_id]) > 0:
            box_data.append(ratios_by_state[state_id])
            box_labels.append(state_names.get(state_id, f'State {state_id}'))
            if state_id == 0:
                box_colors.append('lightgreen')
            elif state_id == 1:
                box_colors.append('lightcoral')
            elif state_id == 2:
                box_colors.append('lightblue')

    bp = ax2.boxplot(box_data, labels=box_labels, patch_artist=True)
    for patch, color in zip(bp['boxes'], box_colors):
        patch.set_facecolor(color)

    ax2.axhline(y=1.0, color='r', linestyle='--', linewidth=1.5, alpha=0.5)
    ax2.set_ylabel('Smoothed Ratio', fontsize=11)
    ax2.set_title('Ratio Distribution by Detector State', fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.3, axis='y')

    # Plot 3: Histogram comparison
    ax3 = fig.add_subplot(gs[1, 1:])

    bins = np.linspace(0.3, 1.7, 50)

    for state_id in sorted(ratios_by_state.keys()):
        ratios = ratios_by_state[state_id]
        if len(ratios) > 0:
            label = f"{state_names.get(state_id, f'State {state_id}')} (n={len(ratios)})"
            alpha = 0.5
            if state_id == 0:
                color = 'green'
            elif state_id == 1:
                color = 'red'
            elif state_id == 2:
                color = 'blue'
            else:
                color = 'gray'

            ax3.hist(ratios, bins=bins, alpha=alpha, label=label, color=color)

    ax3.axvline(x=1.0, color='black', linestyle='--', linewidth=2, label='Target')
    ax3.set_xlabel('Smoothed Ratio', fontsize=11)
    ax3.set_ylabel('Frequency', fontsize=11)
    ax3.set_title('Ratio Distribution by State (Overlaid)', fontsize=12, fontweight='bold')
    ax3.legend(fontsize=10)
    ax3.grid(True, alpha=0.3, axis='y')

    # Plot 4: State distribution pie chart
    ax4 = fig.add_subplot(gs[2, 0])

    state_samples = {state_names[sid]: len(ratios_by_state[sid])
                     for sid in ratios_by_state.keys()}

    colors_pie = []
    for name in state_samples.keys():
        if 'Normal' in name:
            colors_pie.append('lightgreen')
        elif 'Overuse' in name:
            colors_pie.append('lightcoral')
        elif 'Underuse' in name:
            colors_pie.append('lightblue')

    ax4.pie(state_samples.values(), labels=state_samples.keys(), autopct='%1.1f%%',
            colors=colors_pie, startangle=90)
    ax4.set_title('Detector State Distribution', fontsize=12, fontweight='bold')

    # Plot 5: Overuse count statistics
    ax5 = fig.add_subplot(gs[2, 1:])

    total_detections = data['normal_count'] + data['overuse_count'] + data['underuse_count']

    categories = ['Normal', 'Overuse', 'Underuse']
    counts = [data['normal_count'], data['overuse_count'], data['underuse_count']]
    colors_bar = ['green', 'red', 'blue']

    bars = ax5.bar(categories, counts, color=colors_bar, alpha=0.7, edgecolor='black')

    # Add count labels on bars
    for bar, count in zip(bars, counts):
        height = bar.get_height()
        ax5.text(bar.get_x() + bar.get_width()/2., height,
                f'{count}\n({100*count/total_detections:.1f}%)',
                ha='center', va='bottom', fontsize=10, fontweight='bold')

    ax5.set_ylabel('Detection Count', fontsize=11)
    ax5.set_title(f'Detector State Counts (Total: {total_detections})',
                  fontsize=12, fontweight='bold')
    ax5.grid(True, alpha=0.3, axis='y')

    # Overall title
    fig.suptitle('Overuse Detection vs Cellular Ratio Analysis',
                 fontsize=16, fontweight='bold', y=0.998)

    output_path = '/home/wuq/webrtc-local/webrtc_config_results/overuse_ratio_analysis.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n📊 Overuse分析图表已保存至: {output_path}")

def main():
    log_path = '/home/wuq/webrtc-local/webrtc_config_results/sender_local.log'

    print(f"解析日志: {log_path}")
    data = parse_overuse_and_ratio(log_path)

    # Analyze
    analysis = analyze_overuse_ratio_relation(data)

    # Plot
    if analysis:
        plot_overuse_ratio_analysis(data, analysis)

if __name__ == '__main__':
    main()

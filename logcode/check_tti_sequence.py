#!/usr/bin/env python3

def check_tti_sequence():
    """检查原始数据的TTI序列是否被正确保持"""

    data = []
    with open('/home/wuq/webrtc-local/logcode/ratio_data.txt', 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if line:
                parts = line.split('\t')
                if len(parts) == 4:
                    tti = int(parts[0])
                    data.append((line_num, tti))

    print(f"Original data sequence analysis:")
    print(f"Total points: {len(data)}")
    print(f"First 20 points: {data[:20]}")
    print(f"Last 20 points: {data[-20:]}")

    # 检查wrap-around点
    wraps = []
    for i in range(1, len(data)):
        prev_tti = data[i-1][1]
        curr_tti = data[i][1]
        if curr_tti < prev_tti - 5000:
            wraps.append((data[i-1][0], prev_tti, data[i][0], curr_tti))
            print(f"Wrap at line {data[i][0]}: TTI {prev_tti} -> {curr_tti}")

    print(f"Found {len(wraps)} wrap-around points")

    # 转换为连续时间序列
    continuous_sequence = []
    offset = 0
    prev_tti = data[0][1]

    for line_num, tti in data:
        if tti < prev_tti - 5000:
            offset += 10240

        continuous_tti = tti + offset
        continuous_sequence.append((line_num, continuous_tti))
        prev_tti = tti

    # 检查连续序列
    first_time = continuous_sequence[0][1] * 0.001
    last_time = continuous_sequence[-1][1] * 0.001
    duration = last_time - first_time

    print(f"\nContinuous time analysis:")
    print(f"First timestamp: {first_time:.3f}s (line {continuous_sequence[0][0]})")
    print(f"Last timestamp: {last_time:.3f}s (line {continuous_sequence[-1][0]})")
    print(f"Total duration: {duration:.3f}s")

if __name__ == "__main__":
    check_tti_sequence()
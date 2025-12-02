#!/usr/bin/env python3
"""
分析帧率自适应对捕获的影响
Analyze how framerate adaptation affects frame capture
"""

import re

log_file = "webrtc_config_results/sender_local.log"

print("=" * 80)
print("帧率自适应与帧捕获关系分析")
print("=" * 80)
print()

with open(log_file, 'r') as f:
    lines = f.readlines()

# Extract all events with line numbers
events = []

for i, line in enumerate(lines, 1):
    # Framerate clamp events
    if 'Target framerate clamped' in line:
        match = re.search(r'clamped from (\d+) to (\d+)', line)
        if match:
            events.append({
                'line': i,
                'type': 'CLAMP',
                'from_fps': int(match.group(1)),
                'to_fps': int(match.group(2)),
                'text': line.strip()
            })

    # Capture events
    elif 'C2R-CAPTURE' in line:
        match = re.search(r'MonoUs=(\d+)', line)
        if match:
            events.append({
                'line': i,
                'type': 'CAPTURE',
                'mono': int(match.group(1)),
                'text': line.strip()
            })

    # Encode events
    elif 'C2R-ENC-DONE' in line:
        match = re.search(r'MonoUs=(\d+)', line)
        if match:
            events.append({
                'line': i,
                'type': 'ENCODE',
                'mono': int(match.group(1)),
                'text': line.strip()
            })

# Sort by line number
events.sort(key=lambda x: x['line'])

# Count events by type
clamp_events = [e for e in events if e['type'] == 'CLAMP']
capture_events = [e for e in events if e['type'] == 'CAPTURE']
encode_events = [e for e in events if e['type'] == 'ENCODE']

print(f"📊 事件统计:")
print(f"   帧率钳制事件: {len(clamp_events)} 次")
print(f"   捕获事件:     {len(capture_events)} 帧")
print(f"   编码事件:     {len(encode_events)} 帧")
print()

# Find timing relationship
print("⏱️  首次帧率钳制与首次捕获的关系:")
print("-" * 80)

first_clamp = None
first_capture = None

for event in events:
    if event['type'] == 'CLAMP' and first_clamp is None:
        first_clamp = event
    if event['type'] == 'CAPTURE' and first_capture is None:
        first_capture = event
    if first_clamp and first_capture:
        break

if first_clamp and first_capture:
    print(f"首次钳制: 第 {first_clamp['line']} 行")
    print(f"首次捕获: 第 {first_capture['line']} 行")

    if first_clamp['line'] < first_capture['line']:
        print(f"✅ 钳制发生在首次捕获之前 ({first_capture['line'] - first_clamp['line']} 行)")
    else:
        print(f"⚠️  首次捕获在钳制之前")

print()

# Analyze clamp frequency
print("📈 帧率钳制频率分析:")
print("-" * 80)

# Find captures between clamps
for i, clamp in enumerate(clamp_events[:10]):  # First 10 clamps
    line_num = clamp['line']

    # Count captures before next clamp
    next_clamp_line = clamp_events[i+1]['line'] if i+1 < len(clamp_events) else float('inf')

    captures_between = [c for c in capture_events if line_num < c['line'] < next_clamp_line]

    print(f"钳制 #{i+1} (行 {line_num}): 之后 {len(captures_between)} 帧被捕获")

    if i >= 9:
        print("   ...")
        break

print()

# Calculate time intervals between captures
print("⏲️  捕获帧间隔统计 (前100帧):")
print("-" * 80)

intervals = []
for i in range(min(100, len(capture_events) - 1)):
    curr_mono = capture_events[i]['mono']
    next_mono = capture_events[i+1]['mono']
    interval_us = next_mono - curr_mono
    intervals.append(interval_us)

if intervals:
    avg_interval = sum(intervals) / len(intervals)
    min_interval = min(intervals)
    max_interval = max(intervals)

    print(f"平均间隔: {avg_interval:.0f} μs ({1_000_000/avg_interval:.2f} fps)")
    print(f"最小间隔: {min_interval} μs ({1_000_000/min_interval:.2f} fps)")
    print(f"最大间隔: {max_interval} μs ({1_000_000/max_interval:.2f} fps)")
    print(f"理想间隔: 33,333 μs (30 fps)")

    # Check for anomalies
    anomalies = [iv for iv in intervals if abs(iv - 33333) > 5000]
    print(f"异常间隔 (偏差>5ms): {len(anomalies)} 个")

print()

# Check if there are any large gaps at the beginning
print("🔍 启动阶段分析 (前20帧):")
print("-" * 80)

for i in range(min(20, len(capture_events) - 1)):
    curr = capture_events[i]
    next_cap = capture_events[i+1]
    interval_us = next_cap['mono'] - curr['mono']
    interval_ms = interval_us / 1000

    status = "✅" if abs(interval_us - 33333) < 5000 else "⚠️"
    print(f"帧 {i:2d} → {i+1:2d}: {interval_ms:6.2f} ms  {status}")

print()
print("=" * 80)
print("💡 关键发现:")
print("=" * 80)
print()
print("如果帧间隔始终约为 33.33ms (30fps)，说明 FrameGeneratorCapturer")
print("按预期工作，没有跳帧。那么30帧的丢失可能来自:")
print()
print("1️⃣  视频流启动之前的帧:")
print("   - FrameGeneratorCapturer 在 Start() 之前可能已经生成了一些帧")
print("   - 这些帧被读取但未被捕获(未进入 VideoStreamEncoder)")
print()
print("2️⃣  帧率自适应的瞬时跳帧:")
print("   - 每次帧率钳制时，可能导致短暂的帧跳过")
print("   - 15次钳制事件 × 2帧 = 30帧 (假设)")
print()
print("3️⃣  编码器初始化期间的丢弃:")
print("   - 首帧编码前的缓冲区建立阶段")
print("   - 某些帧可能被标记为'不需要编码'而跳过")
print()

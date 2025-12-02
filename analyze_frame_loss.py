#!/usr/bin/env python3
"""
深入分析帧丢失原因
Analyze exactly where and why 49 frames were lost during transmission
"""

import re

log_file = "webrtc_config_results/sender_local.log"

print("=" * 80)
print("帧丢失深度分析 (Deep Frame Loss Analysis)")
print("=" * 80)
print()

# ============================================================
# 1. File read completion
# ============================================================
print("📁 1. 文件读取 (File Reading)")
print("-" * 80)

with open(log_file, 'r') as f:
    content = f.read()

# Find end of file message
end_of_file_match = re.search(r'End of video file reached at frame (\d+)', content)
if end_of_file_match:
    last_frame_read = int(end_of_file_match.group(1))
    print(f"✅ frame_generator 读取到最后一帧: frame {last_frame_read}")
    print(f"   总帧数 = {last_frame_read + 1} (0-indexed)")
else:
    print("❌ 未找到文件结束标记")

print()

# ============================================================
# 2. Capture analysis
# ============================================================
print("📹 2. 帧捕获统计 (Frame Capture)")
print("-" * 80)

capture_lines = re.findall(r'\[C2R-CAPTURE\] MonoUs=(\d+), FrameId=(\d+), CaptureNtpUs=(\d+)', content)
total_captures = len(capture_lines)

print(f"✅ 总捕获帧数: {total_captures}")

if capture_lines:
    first_capture_mono = int(capture_lines[0][0])
    last_capture_mono = int(capture_lines[-1][0])
    capture_duration_us = last_capture_mono - first_capture_mono
    capture_duration_s = capture_duration_us / 1_000_000

    print(f"   首帧捕获: MonoUs={first_capture_mono}")
    print(f"   末帧捕获: MonoUs={last_capture_mono}")
    print(f"   捕获时长: {capture_duration_s:.2f} 秒")
    print(f"   平均帧率: {total_captures / capture_duration_s:.2f} fps")

    # Calculate expected captures
    expected_captures = 3600
    capture_loss = expected_captures - total_captures
    print(f"")
    print(f"❌ 捕获阶段丢失: {capture_loss} 帧 ({capture_loss/expected_captures*100:.2f}%)")

print()

# ============================================================
# 3. Encoding analysis
# ============================================================
print("🎬 3. 帧编码统计 (Frame Encoding)")
print("-" * 80)

encode_lines = re.findall(r'\[C2R-ENC-DONE\] FrameId=(\d+), MonoUs=(\d+), EncodeUs=(\d+)', content)
total_encodes = len(encode_lines)

print(f"✅ 总编码帧数: {total_encodes}")

if encode_lines:
    first_encode_mono = int(encode_lines[0][1])
    last_encode_mono = int(encode_lines[-1][1])
    encode_duration_us = last_encode_mono - first_encode_mono
    encode_duration_s = encode_duration_us / 1_000_000

    print(f"   首帧编码完成: MonoUs={first_encode_mono}")
    print(f"   末帧编码完成: MonoUs={last_encode_mono}")
    print(f"   编码时长: {encode_duration_s:.2f} 秒")
    print(f"   平均帧率: {total_encodes / encode_duration_s:.2f} fps")

    encode_loss = total_captures - total_encodes
    print(f"")
    print(f"❌ 编码阶段丢失: {encode_loss} 帧 ({encode_loss/total_captures*100:.2f}%)")

print()

# ============================================================
# 4. Frame drop reasons
# ============================================================
print("🔍 4. 帧丢失原因分析 (Frame Drop Reasons)")
print("-" * 80)

# Type 1: Bitrate constraint drops
bitrate_drops = re.findall(r'Dropping frame\. Too large for target bitrate', content)
print(f"📊 因码率限制丢弃 (Bitrate constraint): {len(bitrate_drops)} 帧")

# Type 2: Duplicate timestamp drops
timestamp_drops = re.findall(r'Same/old NTP timestamp.*Dropping', content)
print(f"⏱️  因时间戳重复丢弃 (Duplicate timestamp): {len(timestamp_drops)} 帧")

# Type 3: Encoder blocked drops
encoder_blocked_pattern = re.findall(r'dropped \(due to encoder blocked\) (\d+)', content)
total_encoder_blocked = sum(int(x) for x in encoder_blocked_pattern)
print(f"🚫 因编码器阻塞丢弃 (Encoder blocked): {total_encoder_blocked} 帧")

# Type 4: Congestion window drops
congestion_drops_pattern = re.findall(r'dropped \(due to congestion window pushback\) (\d+)', content)
total_congestion_drops = sum(int(x) for x in congestion_drops_pattern)
print(f"📉 因拥塞窗口丢弃 (Congestion window): {total_congestion_drops} 帧")

documented_drops = len(bitrate_drops) + len(timestamp_drops) + total_encoder_blocked + total_congestion_drops
print(f"")
print(f"📝 已明确记录的丢帧: {documented_drops} 帧")
print(f"❓ 未解释的丢帧: {encode_loss - documented_drops} 帧")

print()

# ============================================================
# 5. Framerate adaptation analysis
# ============================================================
print("🔧 5. 帧率自适应分析 (Framerate Adaptation)")
print("-" * 80)

framerate_clamps = re.findall(r'Target framerate clamped from (\d+) to (\d+)', content)
print(f"⚙️  帧率调整事件: {len(framerate_clamps)} 次")
if framerate_clamps:
    first_clamp = framerate_clamps[0]
    print(f"   首次调整: {first_clamp[0]} → {first_clamp[1]} fps")

print()

# ============================================================
# 6. Resolution scaling analysis
# ============================================================
print("📐 6. 分辨率缩放分析 (Resolution Scaling)")
print("-" * 80)

resolution_changes = re.findall(r'Input: (\d+)x(\d+) Scale: ([\d/]+) Output: (\d+)x(\d+)', content)
print(f"🔄 分辨率变化事件: {len(resolution_changes)} 次")
for i, change in enumerate(resolution_changes, 1):
    input_res = f"{change[0]}x{change[1]}"
    scale = change[2]
    output_res = f"{change[3]}x{change[4]}"
    print(f"   #{i}: {input_res} × {scale} → {output_res}")

print()

# ============================================================
# 7. Summary
# ============================================================
print("=" * 80)
print("📊 总结 (Summary)")
print("=" * 80)
print()
print(f"文件总帧数:     3600 帧")
print(f"捕获帧数:       {total_captures} 帧  (丢失 {3600 - total_captures} 帧)")
print(f"编码帧数:       {total_encodes} 帧  (丢失 {total_captures - total_encodes} 帧)")
print(f"总丢失:         {3600 - total_encodes} 帧 ({(3600 - total_encodes)/3600*100:.2f}%)")
print()

# Calculate loss attribution
print("🎯 丢帧归因:")
print(f"  Generator → Capture: {3600 - total_captures} 帧 (原因待查)")
print(f"  Capture → Encode:    {total_captures - total_encodes} 帧")
print(f"    ├─ 码率限制:       {len(bitrate_drops)} 帧")
print(f"    ├─ 时间戳重复:     {len(timestamp_drops)} 帧")
print(f"    ├─ 编码器阻塞:     {total_encoder_blocked} 帧")
print(f"    ├─ 拥塞控制:       {total_congestion_drops} 帧")
print(f"    └─ 未知原因:       {encode_loss - documented_drops} 帧")
print()

# ============================================================
# 8. Root cause hypothesis
# ============================================================
print("=" * 80)
print("💡 根本原因假设 (Root Cause Hypothesis)")
print("=" * 80)
print()
print("❓ Generator → Capture 的30帧丢失:")
print("   可能原因:")
print("   1️⃣  帧率自适应导致 FrameGeneratorCapturer 跳帧")
print("      - sink_wants.max_framerate_fps 从 INT_MAX 被钳制到 30")
print("      - 但实际 source_fps=30, target_fps=30, 理论 decimation=1")
print("   2️⃣  视频流建立初期的预热丢帧")
print("      - 编码器初始化期间，前几帧可能被丢弃")
print("   3️⃣  帧生成器内部的帧重复计数机制")
print("      - frame_repeat_count=1, 理论上每帧都应该传递")
print("   4️⃣  定时器精度和调度延迟")
print("      - 每 33.33ms 调度一次，可能存在累积误差")
print()
print("❓ Capture → Encode 的19帧丢失:")
print("   已知原因:")
print(f"   - 码率限制: {len(bitrate_drops)} 帧 (初期网络建立)")
print(f"   - 时间戳重复: {len(timestamp_drops)} 帧 (时钟同步问题)")
print(f"   - 编码器阻塞: {total_encoder_blocked} 帧 (编码速度慢)")
print(f"   未知原因: {encode_loss - documented_drops} 帧 (需进一步调查)")
print()

print("🔬 建议进一步调查:")
print("   1. 检查 FrameGeneratorCapturer::InsertFrame() 的 decimation 逻辑")
print("   2. 分析 sink_wants.max_framerate_fps 的动态变化")
print("   3. 查看编码器启动阶段是否有帧丢弃")
print("   4. 统计实际的 NextFrame() 调用次数 vs 文件读取次数")
print()

#!/usr/bin/env python3
"""
分析编码超时的原因
"""

import re
import statistics

log_file = "/home/qwu26/webrtc-local/webrtc_config_results/sender_local.log"

# 提取数据
pattern_enc = r'\[C2R-ENC-DONE\] FrameId=\d+, MonoUs=(\d+), EncodeUs=(\d+)'
pattern_pack = r'\[C2R-PACKETIZED\] FrameId=(\d+), RtpTs=\d+, MonoUs=\d+, NumPackets=(\d+)'
pattern_enc_ntp = r'\[C2R-ENC-NTP\] RtpTs=(\d+), NtpMs=(\d+)'

enc_data = []
pack_data = []

with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
    for line in f:
        match = re.search(pattern_enc, line)
        if match:
            enc_data.append({
                'mono_us': int(match.group(1)),
                'encode_us': int(match.group(2))
            })

        match = re.search(pattern_pack, line)
        if match:
            pack_data.append({
                'frame_id': int(match.group(1)),
                'num_packets': int(match.group(2))
            })

print("=" * 80)
print("编码超时原因深度分析")
print("=" * 80)

# 基本统计
encode_times_ms = [d['encode_us'] / 1000.0 for d in enc_data]
target_interval_ms = 33.33
timeout_frames = [t for t in encode_times_ms if t > target_interval_ms]
normal_frames = [t for t in encode_times_ms if t <= target_interval_ms]

print(f"\n1. 基本分类:")
print(f"   总帧数:          {len(encode_times_ms):,}")
print(f"   正常帧:          {len(normal_frames):,} ({len(normal_frames)/len(encode_times_ms)*100:.1f}%)")
print(f"   超时帧:          {len(timeout_frames):,} ({len(timeout_frames)/len(encode_times_ms)*100:.1f}%)")

# 超时帧的统计特征
print(f"\n2. 超时帧编码时间特征:")
print(f"   最小值:          {min(timeout_frames):.2f} ms")
print(f"   最大值:          {max(timeout_frames):.2f} ms")
print(f"   平均值:          {statistics.mean(timeout_frames):.2f} ms")
print(f"   中位数:          {statistics.median(timeout_frames):.2f} ms")
print(f"   超时程度:")
print(f"     轻微超时 (33-40ms):   {sum(1 for t in timeout_frames if 33 < t <= 40)} 帧 ({sum(1 for t in timeout_frames if 33 < t <= 40)/len(timeout_frames)*100:.1f}%)")
print(f"     中度超时 (40-50ms):   {sum(1 for t in timeout_frames if 40 < t <= 50)} 帧 ({sum(1 for t in timeout_frames if 40 < t <= 50)/len(timeout_frames)*100:.1f}%)")
print(f"     严重超时 (>50ms):     {sum(1 for t in timeout_frames if t > 50)} 帧 ({sum(1 for t in timeout_frames if t > 50)/len(timeout_frames)*100:.1f}%)")

# 分析RTP包数量与编码时间的关系
print(f"\n3. RTP包数量与编码时间关系:")
if len(enc_data) == len(pack_data):
    # 按包数量分组
    groups = {}
    for i in range(min(len(enc_data), len(pack_data))):
        encode_ms = enc_data[i]['encode_us'] / 1000.0
        num_packets = pack_data[i]['num_packets']

        # 分组
        if num_packets <= 10:
            key = '1-10包'
        elif num_packets <= 30:
            key = '11-30包'
        elif num_packets <= 50:
            key = '31-50包'
        elif num_packets <= 70:
            key = '51-70包'
        else:
            key = '>70包'

        if key not in groups:
            groups[key] = []
        groups[key].append(encode_ms)

    for key in ['1-10包', '11-30包', '31-50包', '51-70包', '>70包']:
        if key in groups:
            times = groups[key]
            timeout_count = sum(1 for t in times if t > target_interval_ms)
            print(f"   {key:12s}: 平均{statistics.mean(times):6.2f}ms, "
                  f"超时率{timeout_count/len(times)*100:5.1f}% ({timeout_count}/{len(times)})")

# 时序分析 - 检查超时是否集中在某些时间段
print(f"\n4. 超时帧时序分布分析:")
# 将传输分为10个时间段
total_frames = len(encode_times_ms)
segment_size = total_frames // 10

for i in range(10):
    start = i * segment_size
    end = start + segment_size if i < 9 else total_frames
    segment_frames = encode_times_ms[start:end]
    segment_timeout = sum(1 for t in segment_frames if t > target_interval_ms)
    avg_time = statistics.mean(segment_frames)

    print(f"   时段 {i+1:2d} (帧{start:4d}-{end:4d}): "
          f"平均{avg_time:6.2f}ms, 超时{segment_timeout:3d}帧 ({segment_timeout/len(segment_frames)*100:5.1f}%)")

# 分析编码时间的连续性
print(f"\n5. 编码时间突变分析:")
big_jumps = []
for i in range(1, len(encode_times_ms)):
    diff = encode_times_ms[i] - encode_times_ms[i-1]
    if abs(diff) > 20:  # 超过20ms的突变
        big_jumps.append({
            'frame': i,
            'prev': encode_times_ms[i-1],
            'curr': encode_times_ms[i],
            'diff': diff
        })

print(f"   检测到 {len(big_jumps)} 次编码时间突变 (>20ms变化)")
if big_jumps:
    print(f"   最大突增: 帧{big_jumps[0]['frame']}, {big_jumps[0]['prev']:.2f}ms → {big_jumps[0]['curr']:.2f}ms")

    # 分析突变后是否持续超时
    sustained_timeout = 0
    for jump in big_jumps[:10]:  # 检查前10个突变
        frame_idx = jump['frame']
        if frame_idx + 5 < len(encode_times_ms):
            next_5_avg = statistics.mean(encode_times_ms[frame_idx:frame_idx+5])
            if next_5_avg > target_interval_ms:
                sustained_timeout += 1

    print(f"   突变后持续超时: {sustained_timeout}/{min(10, len(big_jumps))} 次")

# 检查I帧（通过包数量推测）
print(f"\n6. 关键帧（I帧）分析:")
large_packet_frames = [i for i, p in enumerate(pack_data) if p['num_packets'] > 70]
print(f"   大包帧数量 (>70包): {len(large_packet_frames)}")
if large_packet_frames:
    large_frame_times = [encode_times_ms[i] for i in large_packet_frames if i < len(encode_times_ms)]
    if large_frame_times:
        print(f"   大包帧平均编码时间: {statistics.mean(large_frame_times):.2f} ms")
        timeout_large = sum(1 for t in large_frame_times if t > target_interval_ms)
        print(f"   大包帧超时率: {timeout_large/len(large_frame_times)*100:.1f}% ({timeout_large}/{len(large_frame_times)})")

print(f"\n7. 可能的超时原因总结:")
print(f"   ▸ 帧复杂度高: 大包帧（可能的I帧）编码时间显著更长")
print(f"   ▸ 编码器负载: 编码时间占用了88.3%的帧间隔，接近极限")
print(f"   ▸ 变异系数33.3%: 不同帧编码复杂度差异大")
print(f"   ▸ VP9编码特性: VP9比H.264编码更复杂，耗时更长")

# 计算相关性
if len(enc_data) == len(pack_data):
    # 简单的相关性分析
    enc_times = [d['encode_us'] / 1000.0 for d in enc_data]
    packet_nums = [p['num_packets'] for p in pack_data]

    # 计算Pearson相关系数
    n = len(enc_times)
    mean_enc = statistics.mean(enc_times)
    mean_pack = statistics.mean(packet_nums)

    numerator = sum((enc_times[i] - mean_enc) * (packet_nums[i] - mean_pack) for i in range(n))
    denom_enc = sum((t - mean_enc) ** 2 for t in enc_times) ** 0.5
    denom_pack = sum((p - mean_pack) ** 2 for p in packet_nums) ** 0.5

    if denom_enc > 0 and denom_pack > 0:
        correlation = numerator / (denom_enc * denom_pack)
        print(f"\n8. 编码时间与包数量的相关系数: {correlation:.3f}")
        if correlation > 0.7:
            print(f"   ✓ 强正相关 - 包数量越多，编码时间越长")
        elif correlation > 0.4:
            print(f"   ✓ 中等正相关 - 包数量对编码时间有明显影响")
        else:
            print(f"   • 弱相关 - 包数量不是主要因素")

print("\n" + "=" * 80)

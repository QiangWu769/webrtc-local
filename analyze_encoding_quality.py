#!/usr/bin/env python3
"""
分析WebRTC发送端编码质量
"""

import re
import sys
from collections import defaultdict, Counter
from datetime import datetime

def parse_log_file(log_file):
    """解析日志文件，提取编码质量指标"""

    results = {
        'encoder_info': {},
        'resolutions': [],
        'bitrates': [],
        'qp_values': [],
        'encode_times': [],
        'frame_types': Counter(),
        'errors': [],
        'warnings': [],
        'resolution_changes': [],
        'bitrate_changes': [],
        'frame_stats': defaultdict(int),
    }

    current_resolution = None
    current_bitrate = None

    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line_num, line in enumerate(f, 1):
            # 编码器信息
            if 'OpenH264' in line and 'version' in line.lower():
                if 'encoder_version' not in results['encoder_info']:
                    match = re.search(r'version.*?(\d+\.\d+(?:\.\d+)?)', line, re.IGNORECASE)
                    if match:
                        results['encoder_info']['encoder_version'] = match.group(1)
                        results['encoder_info']['encoder_type'] = 'OpenH264'

            # 编码器创建
            if 'Creating H264Encoder' in line:
                results['encoder_info']['encoder_impl'] = line.strip()

            # 分辨率变化
            resolution_match = re.search(r'(?:resolution|size|dimensions?).*?(\d{3,4})\s*[x×]\s*(\d{3,4})', line, re.IGNORECASE)
            if resolution_match:
                width, height = int(resolution_match.group(1)), int(resolution_match.group(2))
                resolution = f"{width}×{height}"
                if resolution != current_resolution:
                    results['resolution_changes'].append({
                        'line': line_num,
                        'resolution': resolution,
                        'text': line.strip()[:100]
                    })
                    current_resolution = resolution
                results['resolutions'].append(resolution)

            # 码率设置
            bitrate_match = re.search(r'(?:bitrate|bps).*?(\d+)\s*k?bps', line, re.IGNORECASE)
            if bitrate_match:
                bitrate = int(bitrate_match.group(1))
                if 'kbps' in line.lower():
                    bitrate *= 1000
                if bitrate != current_bitrate:
                    results['bitrate_changes'].append({
                        'line': line_num,
                        'bitrate': bitrate,
                        'text': line.strip()[:100]
                    })
                    current_bitrate = bitrate
                results['bitrates'].append(bitrate)

            # QP值
            qp_match = re.search(r'qp[:\s=]+(\d+)', line, re.IGNORECASE)
            if qp_match:
                qp = int(qp_match.group(1))
                if 0 <= qp <= 51:  # H.264 QP范围
                    results['qp_values'].append(qp)

            # 编码时间
            encode_time_match = re.search(r'encode.*?time.*?(\d+\.?\d*)\s*ms', line, re.IGNORECASE)
            if encode_time_match:
                encode_time = float(encode_time_match.group(1))
                results['encode_times'].append(encode_time)

            # 帧类型
            if re.search(r'\bI[- ]frame\b', line, re.IGNORECASE):
                results['frame_types']['I-frame'] += 1
            elif re.search(r'\bP[- ]frame\b', line, re.IGNORECASE):
                results['frame_types']['P-frame'] += 1
            elif re.search(r'\bB[- ]frame\b', line, re.IGNORECASE):
                results['frame_types']['B-frame'] += 1

            # 编码帧统计
            if 'encoded' in line.lower() and 'frame' in line.lower():
                results['frame_stats']['encoded_frames'] += 1

            # 丢帧
            if re.search(r'drop.*?frame', line, re.IGNORECASE):
                results['frame_stats']['dropped_frames'] += 1
                results['warnings'].append(f"Line {line_num}: {line.strip()[:100]}")

            # 错误
            if re.search(r'\berror\b', line, re.IGNORECASE) and 'dsErrorFree' not in line:
                results['errors'].append(f"Line {line_num}: {line.strip()[:100]}")

            # 警告
            if re.search(r'\bwarn(?:ing)?\b', line, re.IGNORECASE):
                results['warnings'].append(f"Line {line_num}: {line.strip()[:100]}")

    return results

def analyze_quality(results):
    """分析编码质量"""
    print("=" * 80)
    print("📊 WebRTC 发送端编码质量分析报告")
    print("=" * 80)
    print()

    # 编码器信息
    print("## 🎬 编码器信息")
    print()
    if results['encoder_info']:
        for key, value in results['encoder_info'].items():
            print(f"  {key}: {value}")
    else:
        print("  ⚠️  未检测到编码器信息")
    print()

    # 分辨率分析
    print("## 📐 分辨率分析")
    print()
    if results['resolutions']:
        resolution_counter = Counter(results['resolutions'])
        total_samples = len(results['resolutions'])
        print(f"  总分辨率采样点: {total_samples}")
        print()
        print("  分辨率分布:")
        for resolution, count in resolution_counter.most_common():
            percentage = (count / total_samples) * 100
            print(f"    {resolution}: {count} 次 ({percentage:.1f}%)")
        print()

        if results['resolution_changes']:
            print(f"  分辨率变化次数: {len(results['resolution_changes'])}")
            print()
            print("  分辨率变化历史（前10次）:")
            for i, change in enumerate(results['resolution_changes'][:10], 1):
                print(f"    {i}. Line {change['line']}: {change['resolution']}")
    else:
        print("  ⚠️  未检测到分辨率信息")
    print()

    # 码率分析
    print("## 📡 码率分析")
    print()
    if results['bitrates']:
        bitrates_kbps = [b/1000 if b > 10000 else b for b in results['bitrates']]
        avg_bitrate = sum(bitrates_kbps) / len(bitrates_kbps)
        min_bitrate = min(bitrates_kbps)
        max_bitrate = max(bitrates_kbps)

        print(f"  平均码率: {avg_bitrate:.2f} kbps")
        print(f"  最小码率: {min_bitrate:.2f} kbps")
        print(f"  最大码率: {max_bitrate:.2f} kbps")
        print(f"  码率波动: {max_bitrate - min_bitrate:.2f} kbps")
        print()

        if results['bitrate_changes']:
            print(f"  码率调整次数: {len(results['bitrate_changes'])}")
            print()
            print("  码率变化历史（前10次）:")
            for i, change in enumerate(results['bitrate_changes'][:10], 1):
                print(f"    {i}. Line {change['line']}: {change['bitrate']/1000:.0f} kbps")
    else:
        print("  ⚠️  未检测到码率信息")
    print()

    # QP值分析（质量指标）
    print("## 🎯 QP值分析（量化参数 - 质量指标）")
    print()
    if results['qp_values']:
        avg_qp = sum(results['qp_values']) / len(results['qp_values'])
        min_qp = min(results['qp_values'])
        max_qp = max(results['qp_values'])

        print(f"  QP采样数: {len(results['qp_values'])}")
        print(f"  平均QP: {avg_qp:.2f}")
        print(f"  最小QP: {min_qp} (最高质量)")
        print(f"  最大QP: {max_qp} (最低质量)")
        print()

        # QP质量评级
        if avg_qp < 23:
            quality = "优秀"
            emoji = "🌟"
        elif avg_qp < 28:
            quality = "良好"
            emoji = "✅"
        elif avg_qp < 33:
            quality = "中等"
            emoji = "⚠️"
        else:
            quality = "较差"
            emoji = "❌"

        print(f"  {emoji} 整体质量评级: {quality}")
        print()
        print("  QP值说明:")
        print("    0-22:  优秀质量（接近无损）")
        print("    23-27: 良好质量（高清）")
        print("    28-32: 中等质量（标清）")
        print("    33-51: 较差质量（低清）")
    else:
        print("  ⚠️  未检测到QP信息")
    print()

    # 编码时间分析
    print("## ⏱️  编码时间分析")
    print()
    if results['encode_times']:
        avg_time = sum(results['encode_times']) / len(results['encode_times'])
        min_time = min(results['encode_times'])
        max_time = max(results['encode_times'])

        frame_interval_30fps = 33.33

        print(f"  编码时间采样数: {len(results['encode_times'])}")
        print(f"  平均编码时间: {avg_time:.2f} ms")
        print(f"  最快编码: {min_time:.2f} ms")
        print(f"  最慢编码: {max_time:.2f} ms")
        print(f"  目标帧间隔(30 FPS): {frame_interval_30fps:.2f} ms")
        print()

        if avg_time < frame_interval_30fps:
            percentage = (avg_time / frame_interval_30fps) * 100
            margin = frame_interval_30fps - avg_time
            print(f"  ✅ 编码性能: 充足")
            print(f"     平均占用帧间隔: {percentage:.1f}%")
            print(f"     性能余量: {margin:.2f} ms ({100-percentage:.1f}%)")
        else:
            print(f"  ❌ 编码性能: 不足（可能无法实时编码30 FPS）")
    else:
        print("  ⚠️  未检测到编码时间信息")
    print()

    # 帧类型统计
    print("## 🎞️  帧类型统计")
    print()
    if results['frame_types']:
        total_typed_frames = sum(results['frame_types'].values())
        for frame_type, count in results['frame_types'].most_common():
            percentage = (count / total_typed_frames) * 100
            print(f"  {frame_type}: {count} ({percentage:.1f}%)")
        print()

        if 'I-frame' in results['frame_types'] and total_typed_frames > 0:
            i_frame_ratio = results['frame_types']['I-frame'] / total_typed_frames
            print(f"  I帧比例: {i_frame_ratio*100:.2f}%")
            if i_frame_ratio < 0.05:
                print(f"  ✅ I帧比例合理（GOP较大，压缩率高）")
            elif i_frame_ratio < 0.1:
                print(f"  ✅ I帧比例正常")
            else:
                print(f"  ⚠️  I帧比例偏高（可能影响压缩效率）")
    else:
        print("  ℹ️  日志中未明确标注帧类型")
    print()

    # 帧统计
    print("## 📊 帧统计")
    print()
    if results['frame_stats']['encoded_frames'] > 0:
        print(f"  编码帧数: {results['frame_stats']['encoded_frames']}")
    if results['frame_stats']['dropped_frames'] > 0:
        print(f"  丢帧数: {results['frame_stats']['dropped_frames']}")
        drop_rate = results['frame_stats']['dropped_frames'] / max(results['frame_stats']['encoded_frames'], 1) * 100
        print(f"  丢帧率: {drop_rate:.2f}%")
        if drop_rate > 1:
            print(f"  ❌ 丢帧率偏高")
        else:
            print(f"  ⚠️  有少量丢帧")
    else:
        print("  ✅ 无丢帧")
    print()

    # 错误和警告
    print("## ⚠️  错误和警告")
    print()
    print(f"  错误数: {len(results['errors'])}")
    print(f"  警告数: {len(results['warnings'])}")
    print()

    if results['errors']:
        print("  前5条错误:")
        for error in results['errors'][:5]:
            print(f"    - {error}")
        print()

    if results['warnings']:
        print("  前5条警告:")
        for warning in results['warnings'][:5]:
            print(f"    - {warning}")
        print()

    # 总体评估
    print("=" * 80)
    print("## 🎯 总体评估")
    print("=" * 80)
    print()

    score = 0
    max_score = 5

    # QP评分
    if results['qp_values']:
        avg_qp = sum(results['qp_values']) / len(results['qp_values'])
        if avg_qp < 28:
            score += 1
            print("✅ 视频质量: 良好（QP < 28）")
        else:
            print("⚠️  视频质量: 有待提升（QP >= 28）")

    # 编码性能评分
    if results['encode_times']:
        avg_time = sum(results['encode_times']) / len(results['encode_times'])
        if avg_time < 33.33:
            score += 1
            print("✅ 编码性能: 实时编码无压力")
        else:
            print("❌ 编码性能: 可能无法实时编码")

    # 稳定性评分
    if results['frame_stats']['dropped_frames'] == 0:
        score += 1
        print("✅ 稳定性: 无丢帧")
    else:
        print("⚠️  稳定性: 有丢帧现象")

    # 分辨率评分
    if results['resolutions']:
        resolution_counter = Counter(results['resolutions'])
        most_common_res = resolution_counter.most_common(1)[0][0]
        if '1920' in most_common_res or '1280' in most_common_res:
            score += 1
            print(f"✅ 分辨率: 高清 ({most_common_res})")
        else:
            print(f"⚠️  分辨率: 中低清 ({most_common_res})")

    # 错误评分
    if len(results['errors']) == 0:
        score += 1
        print("✅ 可靠性: 无错误")
    else:
        print(f"⚠️  可靠性: 有 {len(results['errors'])} 个错误")

    print()
    print(f"总评分: {score}/{max_score} ⭐" + "⭐" * (score - 1))
    print()

if __name__ == '__main__':
    log_file = sys.argv[1] if len(sys.argv) > 1 else 'webrtc_config_results/sender_local.log'

    try:
        results = parse_log_file(log_file)
        analyze_quality(results)
    except FileNotFoundError:
        print(f"❌ 错误: 找不到日志文件 {log_file}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 分析过程中出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

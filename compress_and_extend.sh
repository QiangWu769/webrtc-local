#!/bin/bash
# 将60秒的压缩YUV扩展到120秒

INPUT_FILE="/home/wuq/webrtc-checkout/VCD_th_1920x1080_30_60s_compressed.yuv"
TEMP_MP4="/home/wuq/webrtc-checkout/temp_video_120s.mp4"
OUTPUT_MP4="/home/wuq/webrtc-checkout/VCD_th_1920x1080_30_120s.mp4"
OUTPUT_YUV="/home/wuq/webrtc-checkout/VCD_th_1920x1080_30_120s_compressed.yuv"

echo "=== 将60秒YUV扩展到120秒 ==="

# 步骤1: 60秒YUV转MP4
echo "步骤1: 60秒YUV转MP4..."
ffmpeg -f rawvideo -pix_fmt yuv420p -s 1920x1080 -r 30 -i "$INPUT_FILE" \
       -c:v libx264 -preset medium -crf 18 -y "$TEMP_MP4"

# 步骤2: 重复MP4到120秒 (循环1次，即播放2遍)
echo "步骤2: 重复到120秒..."
ffmpeg -stream_loop 1 -i "$TEMP_MP4" -c copy -y "$OUTPUT_MP4"

# 步骤3: MP4转回YUV
echo "步骤3: 转回YUV格式..."
ffmpeg -i "$OUTPUT_MP4" -f rawvideo -pix_fmt yuv420p -y "$OUTPUT_YUV"

echo ""
echo "=== 完成! ===" 
echo "原始60秒YUV: $(ls -lh "$INPUT_FILE" | awk '{print $5}') (60秒)"
echo "扩展120秒MP4: $(ls -lh "$OUTPUT_MP4" | awk '{print $5}') (120秒)"
echo "扩展120秒YUV: $(ls -lh "$OUTPUT_YUV" | awk '{print $5}') (120秒)"

# 计算扩展信息
python3 -c "
import os
original_size = os.path.getsize('$INPUT_FILE')
extended_yuv_size = os.path.getsize('$OUTPUT_YUV')
size_ratio = extended_yuv_size / original_size
print(f'时长扩展: 60秒 → 120秒 (2倍)')
print(f'文件大小比例: {size_ratio:.1f}:1')
"

# 清理临时文件
rm "$TEMP_MP4"
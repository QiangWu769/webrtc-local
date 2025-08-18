#!/bin/bash
# 创建60秒循环YUV视频

INPUT_FILE="/home/wuq/webrtc-checkout/VCD_th_1920x1080_30.yuv"
OUTPUT_FILE="/home/wuq/webrtc-checkout/VCD_th_1920x1080_30_60s.yuv"

echo "创建60秒循环YUV文件..."
echo "原文件: $INPUT_FILE (10秒)"
echo "输出文件: $OUTPUT_FILE (60秒)"

# 重复6次创建60秒视频
cp "$INPUT_FILE" "$OUTPUT_FILE"
for i in {1..5}; do
    echo "添加循环 $i/5..."
    cat "$INPUT_FILE" >> "$OUTPUT_FILE"
done

echo "完成！60秒YUV文件创建成功"
ls -lh "$OUTPUT_FILE"

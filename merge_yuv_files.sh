#!/bin/bash

# 合并12个YUV文件，保持原始fps和时间
# 使用简单的cat命令直接拼接，不改变帧率

OUTPUT_FILE="/home/wuq/webrtc-local/VCD/download/vcd1/yuv420/merged_all_1920x1080.yuv"
YUV_DIR="/home/wuq/webrtc-local/VCD/download/vcd1/yuv420"

# 要合并的12个文件（3个来自每个类别）
FILES=(
    "$YUV_DIR/th/54e9f7b6a15b07e90b4836eb6ffb58ae_1920x1080_30.yuv"
    "$YUV_DIR/th/2326ac1d3e069fbd86e2ca79082e19f9_1920x1080_30.yuv"  
    "$YUV_DIR/th/fbdfa436d72b83ff284396579bcd6da5_1920x1080_30.yuv"
    "$YUV_DIR/th-ob/1c63cf94eb2bcdfbb57dbf3727c7d695_1920x1080_30.yuv"
    "$YUV_DIR/th-ob/bff43254e9a55ecf50b9589a4317c189_1920x1080_30.yuv"
    "$YUV_DIR/th-ob/1eec2811670a1dfa0f697d099b0dfcdb_1920x1080_30.yuv"
    "$YUV_DIR/th-bb/6f05900f2375ca5a01202460975afd79_1920x1080_30.yuv"
    "$YUV_DIR/th-bb/91154c046bba79ee8b24550a8cb2870b_1920x1080_30.yuv"
    "$YUV_DIR/th-bb/c3089ec3080756f925b5b83fb66af24c_1920x1080_30.yuv"
    "$YUV_DIR/converted/0296bcc0fdd2a47380e798289dcc099f_1080x1920_30_converted.yuv"
    "$YUV_DIR/converted/3f7df79cd3338701dfce79b3ec82531c_1080x1920_30_converted.yuv"
    "$YUV_DIR/converted/6b9b28f4a7b953660e611ae4f7140dd4_1080x1920_30_converted.yuv"
)

echo "开始合并12个YUV文件..."
echo "输出文件: $OUTPUT_FILE"

# 检查文件是否存在
for file in "${FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo "错误: 文件不存在 $file"
        exit 1
    fi
done

# 删除已存在的输出文件
rm -f "$OUTPUT_FILE"

# 使用cat直接拼接，保持原始帧率和时间
echo "正在合并文件..."
cat "${FILES[@]}" > "$OUTPUT_FILE"

echo "合并完成！"
echo "输出文件大小: $(ls -lh "$OUTPUT_FILE" | awk '{print $5}')"

# 计算合并后的信息
python3 -c "
import os
file_size = os.path.getsize('$OUTPUT_FILE')
frame_size = 1920 * 1080 * 1.5  # YUV420格式每帧大小
total_frames = int(file_size / frame_size)
duration_at_30fps = total_frames / 30
print(f'合并后信息:')
print(f'  文件大小: {file_size:,} 字节')
print(f'  总帧数: {total_frames:,} 帧')
print(f'  以30fps播放时长: {duration_at_30fps:.1f} 秒')
print(f'  实际帧率: 30 fps (保持不变)')
"
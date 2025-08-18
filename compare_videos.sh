#!/bin/bash
# 视频质量比较脚本

if [ $# -ne 2 ]; then
    echo "用法: $0 <输入视频.yuv> <输出视频.yuv>"
    exit 1
fi

INPUT_VIDEO="$1"
OUTPUT_VIDEO="$2"
WIDTH=640
HEIGHT=480
FPS=30

echo "=== 使用FFmpeg进行视频质量分析 ==="

# 转换前几秒为MP4用于可视化比较
echo "转换输入视频前10秒为MP4..."
ffmpeg -f rawvideo -pixel_format yuv420p -video_size ${WIDTH}x${HEIGHT} -framerate ${FPS} \
    -i "$INPUT_VIDEO" -t 10 -c:v libx264 -preset fast -crf 18 input_sample.mp4 -y 2>/dev/null

echo "转换输出视频前10秒为MP4..."
ffmpeg -f rawvideo -pixel_format yuv420p -video_size ${WIDTH}x${HEIGHT} -framerate ${FPS} \
    -i "$OUTPUT_VIDEO" -t 10 -c:v libx264 -preset fast -crf 18 output_sample.mp4 -y 2>/dev/null

# 创建并排比较视频
echo "创建并排比较视频..."
ffmpeg -i input_sample.mp4 -i output_sample.mp4 \
    -filter_complex "[0:v][1:v]hstack=inputs=2[v]" \
    -map "[v]" -c:v libx264 -preset fast -crf 18 comparison.mp4 -y 2>/dev/null

echo "文件已生成:"
echo "  input_sample.mp4     - 输入视频样本"
echo "  output_sample.mp4    - 输出视频样本"
echo "  comparison.mp4       - 并排比较视频"

# 如果安装了ffprobe，显示详细信息
if command -v ffprobe >/dev/null 2>&1; then
    echo ""
    echo "=== 输入视频信息 ==="
    ffprobe -v quiet -print_format json -show_format -show_streams input_sample.mp4 2>/dev/null | grep -E "(width|height|r_frame_rate|bit_rate)" || echo "无法获取详细信息"
    
    echo ""
    echo "=== 输出视频信息 ==="
    ffprobe -v quiet -print_format json -show_format -show_streams output_sample.mp4 2>/dev/null | grep -E "(width|height|r_frame_rate|bit_rate)" || echo "无法获取详细信息"
fi

echo ""
echo "可以使用视频播放器打开 comparison.mp4 进行直观比较"

#!/bin/bash
# MP4实时播放到YUV管道

MP4_FILE="/home/wuq/webrtc-checkout/VCD_th_1920x1080_30_60s.mp4"
OUTPUT_PIPE="/tmp/yuv_from_mp4"

echo "=== MP4实时转YUV播放 ==="
echo "输入: $MP4_FILE (35M, 60秒)"
echo "输出: $OUTPUT_PIPE (实时YUV流)"

# 创建命名管道
mkfifo "$OUTPUT_PIPE" 2>/dev/null || true

echo "开始实时播放..."
# 实时播放MP4并转换为YUV
ffmpeg -re -stream_loop -1 -i "$MP4_FILE"        -f rawvideo -pix_fmt yuv420p "$OUTPUT_PIPE" &

FFMPEG_PID=$!

echo ""
echo "输出管道: $OUTPUT_PIPE"
echo "进程ID: $FFMPEG_PID"
echo ""
echo "在WebRTC中使用: $OUTPUT_PIPE 作为输入"
echo "按Ctrl+C停止"

trap "kill $FFMPEG_PID 2>/dev/null; rm -f $OUTPUT_PIPE; echo '播放已停止'; exit" INT
wait $FFMPEG_PID

#!/bin/bash
# 智能循环播放 - 在内存中重复播放10秒视频到60秒
# 不创建大文件，动态循环

INPUT_FILE="/home/wuq/webrtc-checkout/VCD_th_1920x1080_30.yuv"
OUTPUT_FIFO="/tmp/yuv_loop_60s"

echo "=== 智能循环播放方案 ==="
echo "原理: 创建命名管道，动态循环播放10秒视频6次"
echo "优势: 不占用额外磁盘空间，实时循环"

# 创建命名管道
mkfifo "$OUTPUT_FIFO" 2>/dev/null || true

echo "创建循环播放进程..."
(
    for i in {1..6}; do
        echo "播放循环 $i/6..."
        cat "$INPUT_FILE"
    done
) > "$OUTPUT_FIFO" &

LOOP_PID=$!

echo ""
echo "输出管道: $OUTPUT_FIFO"
echo "进程ID: $LOOP_PID"
echo ""
echo "使用方法:"
echo "ffplay -f rawvideo -pix_fmt yuv420p -s 1920x1080 -r 30 $OUTPUT_FIFO"
echo ""
echo "在WebRTC中使用这个管道作为输入源"
echo "按Ctrl+C停止循环播放"

# 等待用户中断
trap "kill $LOOP_PID 2>/dev/null; rm -f $OUTPUT_FIFO; echo '循环播放已停止'; exit" INT
wait $LOOP_PID

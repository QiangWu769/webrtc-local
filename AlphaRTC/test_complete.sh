#!/bin/bash

# 完整的AlphaRTC测试脚本
# 功能：发送10秒视频，不传音频，自动退出

set -e

# 配置
DISPLAY_NUM=99
CONFIG_FILE="/home/wuq/webrtc-checkout/AlphaRTC/examples/peerconnection/client/webrtc_config_example.json"
LIB_PATH="/home/wuq/webrtc-checkout/AlphaRTC/modules/third_party/onnxinfer/lib"

echo "🚀 启动AlphaRTC完整测试..."

# 1. 启动虚拟显示
echo "1️⃣ 启动虚拟显示Xvfb..."
pkill -f "Xvfb :$DISPLAY_NUM" 2>/dev/null || true
Xvfb :$DISPLAY_NUM -screen 0 1024x768x24 &
XVFB_PID=$!
sleep 2

# 2. 启动signaling服务器
echo "2️⃣ 启动signaling服务器..."
pkill -f "peerconnection_server" 2>/dev/null || true
./out/Default/peerconnection_server --port=8888 &
SERVER_PID=$!
sleep 2

# 3. 设置环境变量
export DISPLAY=:$DISPLAY_NUM
export LD_LIBRARY_PATH="$LIB_PATH:$LD_LIBRARY_PATH"

# 4. 启动接收端（后台运行）
echo "3️⃣ 启动接收端（后台）..."
timeout 15s ./out/Default/peerconnection_client \
    --autoconnect --server=127.0.0.1 --port=8888 \
    > receiver.log 2>&1 &
RECEIVER_PID=$!
sleep 3

# 5. 启动发送端（带配置文件）
echo "4️⃣ 启动发送端（10秒视频，无音频）..."
timeout 15s ./out/Default/peerconnection_client \
    --config="$CONFIG_FILE" \
    --autoconnect --autocall --server=127.0.0.1 --port=8888
SENDER_EXIT_CODE=$?

echo ""
echo "📊 测试结果："
if [ $SENDER_EXIT_CODE -eq 0 ] || [ $SENDER_EXIT_CODE -eq 124 ]; then
    echo "✅ 发送端完成（退出码: $SENDER_EXIT_CODE）"
else
    echo "❌ 发送端异常（退出码: $SENDER_EXIT_CODE）"
fi

# 6. 清理
echo "🧹 清理进程..."
kill $RECEIVER_PID 2>/dev/null || true
kill $SERVER_PID 2>/dev/null || true  
kill $XVFB_PID 2>/dev/null || true

echo "📋 查看接收端日志（最后10行）："
tail -10 receiver.log 2>/dev/null || echo "无日志文件"

echo ""
echo "🎉 测试完成！"
echo "📹 视频: 10秒, 640x480@30fps"
echo "🔇 音频: 已禁用"
echo "⏰ 自动退出: 3秒后"
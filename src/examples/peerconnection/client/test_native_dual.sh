#!/bin/bash

echo "🎯 启动Native WebRTC双文件测试流程（发送端 + 接收端）..."

# 清理现有进程
echo "🧹 清理现有进程..."
pkill -f "Xvfb" 2>/dev/null || true
pkill -f "peerconnection_server" 2>/dev/null || true
pkill -f "peerconnection_client" 2>/dev/null || true
rm -f /tmp/.X99-lock 2>/dev/null || true
sleep 1

# 确保在src目录下执行
cd /home/wuq/webrtc-checkout/src

# 1. 启动虚拟显示
echo "1️⃣ 启动虚拟显示Xvfb..."
Xvfb :99 -screen 0 1024x768x24 > /dev/null 2>&1 &
XVFB_PID=$!
sleep 2

# 2. 启动signaling服务器
echo "2️⃣ 启动signaling服务器..."
./out/Default/peerconnection_server --port=8888 > server.log 2>&1 &
SERVER_PID=$!
sleep 2

# 设置环境变量
export DISPLAY=:99

# 3. 启动接收端（使用接收配置文件）
echo "3️⃣ 启动接收端客户端（用于接收和保存视频）..."
./out/Default/peerconnection_client \
  --config=/home/wuq/webrtc-checkout/src/examples/peerconnection/client/receiver_config.json \
  --autoconnect \
  --server=127.0.0.1 \
  --port=8888 > receiver.log 2>&1 &
RECEIVER_PID=$!
sleep 3

# 4. 启动发送端（使用发送配置文件）
echo "4️⃣ 启动发送端客户端（使用发送配置文件）..."
./out/Default/peerconnection_client \
  --config=/home/wuq/webrtc-checkout/src/examples/peerconnection/client/sender_config.json \
  --autoconnect \
  --autocall \
  --server=127.0.0.1 \
  --port=8888 > sender.log 2>&1 &
SENDER_PID=$!

echo ""
echo "🚀 所有组件已启动："
echo "   - Xvfb (PID: $XVFB_PID)"
echo "   - Server (PID: $SERVER_PID)"  
echo "   - Receiver (PID: $RECEIVER_PID)"
echo "   - Sender (PID: $SENDER_PID)"
echo ""
echo "🎬 测试进行中... 预计25秒后自动结束"
echo "📁 输出文件："
echo "   - 发送方视频: /home/wuq/webrtc-checkout/src/output_video.yuv"
echo "   - 接收方视频: /home/wuq/webrtc-checkout/src/received_video.yuv"
echo ""

# 等待发送方自动结束
wait $SENDER_PID
echo "📤 发送方已完成"

# 等待接收方自动结束
wait $RECEIVER_PID  
echo "📥 接收方已完成"

# 清理进程
echo "🧹 清理所有进程..."
kill $XVFB_PID $SERVER_PID 2>/dev/null || true
sleep 1

echo ""
echo "✅ 测试完成！检查输出文件："
ls -lh output_video.yuv received_video.yuv 2>/dev/null || echo "文件生成中..."
echo ""
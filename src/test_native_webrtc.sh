#!/bin/bash

echo "🎯 启动原生WebRTC正确测试流程（发送端 + 接收端）..."

# 清理现有进程
echo "🧹 清理现有进程..."
pkill -f "Xvfb" 2>/dev/null || true
pkill -f "peerconnection_server" 2>/dev/null || true
pkill -f "peerconnection_client" 2>/dev/null || true
rm -f /tmp/.X99-lock 2>/dev/null || true
sleep 1

# 1. 启动虚拟显示
echo "1️⃣ 启动虚拟显示Xvfb..."
Xvfb :99 -screen 0 1024x768x24 > /dev/null 2>&1 &
XVFB_PID=$!
sleep 2

# 2. 启动signaling服务器
echo "2️⃣ 启动signaling服务器..."
./src/out/Default/peerconnection_server --port=8888 > server.log 2>&1 &
SERVER_PID=$!
sleep 2

# 设置环境变量
export DISPLAY=:99

# 3. 启动接收端（使用接收配置文件）
echo "3️⃣ 启动接收端客户端（用于接收和保存视频）..."
./src/out/Default/peerconnection_client \
  --config=/home/wuq/webrtc-checkout/results/receiver_config.json > receiver.log 2>&1 &
RECEIVER_PID=$!
sleep 3

# 4. 启动发送端（使用发送配置文件）
echo "4️⃣ 启动发送端客户端（使用发送配置文件）..."
./src/out/Default/peerconnection_client \
  --config=/home/wuq/webrtc-checkout/results/sender_config.json > sender.log 2>&1 &
SENDER_PID=$!

echo ""
echo "🚀 所有组件已启动："
echo "   - Xvfb (PID: $XVFB_PID)"
echo "   - Server (PID: $SERVER_PID)"  
echo "   - Receiver (PID: $RECEIVER_PID)"
echo "   - Sender (PID: $SENDER_PID)"
echo ""
echo "📋 监控进程状态..."
echo "📝 日志文件: server.log, receiver.log, sender.log"
echo "📁 输出文件: /home/wuq/webrtc-checkout/results/output_quick_test.yuv (发送方本地副本)"
echo "📁 输出文件: /home/wuq/webrtc-checkout/results/received_quick_test.yuv (接收方网络传输)"
echo ""

# 监控日志输出（前15秒）
echo "📊 实时监控发送端日志（15秒）..."
timeout 15s tail -f sender.log || true

echo ""
echo "🔍 检查配置文件读取和简化定时器状态..."
grep -E "(Transmission Time|Auto Close|Starting auto-close timer)" sender.log || echo "未找到定时器相关日志"

echo ""
echo "🔍 检查双文件输出状态..."
grep -E "(video writer|output.*yuv|Video output)" sender.log receiver.log || echo "未找到视频输出相关日志"

echo ""
echo "⚠️  若要停止所有进程，请运行: kill $XVFB_PID $SERVER_PID $RECEIVER_PID $SENDER_PID"
echo "📊 或者等待配置的transmission_time_seconds时间后自动结束"
#!/bin/bash

echo "🎯 启动原生WebRTC正确测试流程（发送端 + 接收端）..."
echo "📁 使用专用目录: webrtc_config_results"

# 清理现有进程
echo "🧹 清理现有进程..."
pkill -f "Xvfb" 2>/dev/null || true
pkill -f "peerconnection_server" 2>/dev/null || true
pkill -f "peerconnection_client" 2>/dev/null || true
rm -f /tmp/.X99-lock 2>/dev/null || true
sleep 1

# 检查当前目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
cd "$BASE_DIR"

echo "📂 工作目录: $(pwd)"
echo "📁 配置目录: webrtc_config_results"

# 1. 启动虚拟显示
echo "1️⃣ 启动虚拟显示Xvfb..."
Xvfb :99 -screen 0 1024x768x24 > /dev/null 2>&1 &
XVFB_PID=$!
sleep 2

# 2. 启动signaling服务器
echo "2️⃣ 启动signaling服务器..."
./src/out/Default/peerconnection_server --port=8888 > webrtc_config_results/server.log 2>&1 &
SERVER_PID=$!
sleep 2

# 设置环境变量
export DISPLAY=:99

# 3. 启动接收端（使用接收配置文件）
echo "3️⃣ 启动接收端客户端（用于接收和保存视频）..."
./src/out/Default/peerconnection_client \
  --config=$(pwd)/webrtc_config_results/receiver_config.json > webrtc_config_results/receiver.log 2>&1 &
RECEIVER_PID=$!
sleep 3

# 4. 启动发送端（使用发送配置文件）
echo "4️⃣ 启动发送端客户端（使用发送配置文件）..."
./src/out/Default/peerconnection_client \
  --config=$(pwd)/webrtc_config_results/sender_config.json > webrtc_config_results/sender.log 2>&1 &
SENDER_PID=$!

echo ""
echo "🚀 所有组件已启动："
echo "   - Xvfb (PID: $XVFB_PID)"
echo "   - Server (PID: $SERVER_PID)"  
echo "   - Receiver (PID: $RECEIVER_PID)"
echo "   - Sender (PID: $SENDER_PID)"
echo ""
echo "📋 监控进程状态..."
echo "📝 日志文件: webrtc_config_results/server.log, webrtc_config_results/receiver.log, webrtc_config_results/sender.log"
echo "📁 输出文件: webrtc_config_results/output_quick_test.yuv (发送方本地副本)"
echo "📁 输出文件: webrtc_config_results/received_quick_test.yuv (接收方网络传输)"
echo ""

# 监控日志输出（前15秒）
echo "📊 实时监控发送端日志（15秒）..."
timeout 15s tail -f webrtc_config_results/sender.log || true

echo ""
echo "🔍 检查配置文件读取和简化定时器状态..."
grep -E "(Transmission Time|Auto Close|Starting auto-close timer)" webrtc_config_results/sender.log || echo "未找到定时器相关日志"

echo ""
echo "🔍 检查双文件输出状态..."
grep -E "(VideoFrameWriter|Y4M format|Output File)" webrtc_config_results/sender.log webrtc_config_results/receiver.log || echo "未找到视频输出相关日志"

echo ""
echo "📊 检查生成的文件..."
ls -lh webrtc_config_results/*quick*yuv 2>/dev/null || echo "视频文件生成中..."

echo ""
echo "⚠️  若要停止所有进程，请运行: kill $XVFB_PID $SERVER_PID $RECEIVER_PID $SENDER_PID"
echo "📊 或者等待配置的transmission_time_seconds时间后自动结束"
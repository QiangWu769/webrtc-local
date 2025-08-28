#!/bin/bash

echo "🎯 启动简化的Native WebRTC测试..."

# 清理进程
pkill -f "peerconnection" 2>/dev/null || true
pkill -f "Xvfb" 2>/dev/null || true
sleep 1

# 启动虚拟显示
echo "1️⃣ 启动虚拟显示..."
Xvfb :99 -screen 0 1024x768x24 > /dev/null 2>&1 &
XVFB_PID=$!
export DISPLAY=:99
sleep 2

# 启动服务器
echo "2️⃣ 启动服务器..."
./out/Default/peerconnection_server --port=8888 > server.log 2>&1 &
SERVER_PID=$!
sleep 3

# 测试配置文件
echo "3️⃣ 测试发送方配置..."
./out/Default/peerconnection_client \
  --config=/home/wuq/webrtc-checkout/src/examples/peerconnection/client/sender_config.json \
  --server=127.0.0.1 \
  --port=8888 > sender_debug.log 2>&1 &
SENDER_PID=$!

echo "等待15秒..."
sleep 15

echo "4️⃣ 检查结果..."
echo "发送方日志前10行："
head -10 sender_debug.log 2>/dev/null || echo "没有日志"

echo "清理..."
kill $SENDER_PID $SERVER_PID $XVFB_PID 2>/dev/null || true
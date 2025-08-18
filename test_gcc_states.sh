#!/bin/bash

echo "🧪 GCC状态转换测试脚本"
echo "=========================="

# 清理现有的网络限制
sudo tc qdisc del dev lo root 2>/dev/null || true

echo "📡 阶段1: 正常网络条件 (Normal状态)"
./out/Default/peerconnection_client --config=sender_config.json &
SENDER_PID=$!
sleep 10

echo "📉 阶段2: 制造网络拥塞 (触发Decrease状态)"
sudo tc qdisc add dev lo root netem delay 150ms 50ms loss 3%
sleep 15

echo "🚀 阶段3: 网络改善 (触发Increase状态)" 
sudo tc qdisc change dev lo root netem delay 20ms 5ms
sleep 15

echo "🔄 阶段4: 恢复正常 (回到Normal状态)"
sudo tc qdisc del dev lo root
sleep 10

# 清理
kill $SENDER_PID 2>/dev/null || true
sudo tc qdisc del dev lo root 2>/dev/null || true

echo "✅ 测试完成！查看日志文件寻找状态转换"
echo "搜索命令: grep -E 'Detector state: [1-2]|State: (Increase|Decrease)' sender_local.log"
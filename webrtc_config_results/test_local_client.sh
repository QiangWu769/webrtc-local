#!/bin/bash

# 参数解析
ROLE="$1"
REMOTE_IP="$2"

if [ "$ROLE" != "sender" ] && [ "$ROLE" != "receiver" ]; then
    echo "🎯 智能WebRTC本地启动脚本"
    echo ""
    echo "用法: $0 <sender|receiver> <cloud_server_ip>"
    echo ""
    echo "参数说明:"
    echo "  sender           - 本地作为发送端运行（连接到云服务器信令服务器）"
    echo "  receiver         - 本地作为接收端运行（连接到云服务器信令服务器）"
    echo "  cloud_server_ip  - 云服务器IP地址（必须，因为本地是私网）"
    echo ""
    echo "网络架构:"
    echo "  - 云服务器（有公网IP）: 运行信令服务器"
    echo "  - 本地电脑（私网）: 连接到云服务器的信令服务器"
    echo ""
    echo "示例:"
    echo "  $0 sender 110.42.33.160     # 本地作为发送端，连接云服务器"
    echo "  $0 receiver 110.42.33.160   # 本地作为接收端，连接云服务器"
    echo ""
    echo "兼容性说明:"
    echo "  如果只提供一个IP参数，将默认作为接收端模式运行:"
    echo "  $0 110.42.33.160           # 等同于 $0 receiver 110.42.33.160"
    exit 1
fi

# 兼容性处理：如果第一个参数是IP地址，则认为是旧版本用法
if [[ "$ROLE" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "🔄 检测到旧版本用法，自动转换为接收端模式"
    REMOTE_IP="$ROLE"
    ROLE="receiver"
fi

echo "🎯 智能WebRTC本地启动脚本 - 运行模式: $ROLE"

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

# 获取本地IP（用于发送端模式）
LOCAL_IP=$(hostname -I | awk '{print $1}' 2>/dev/null || echo "127.0.0.1")
echo "🌐 本地IP: $LOCAL_IP"

# 1. 启动虚拟显示（如果在无GUI环境运行）
echo "1️⃣ 启动虚拟显示Xvfb..."
Xvfb :99 -screen 0 1024x768x24 > /dev/null 2>&1 &
XVFB_PID=$!
sleep 2

# 设置环境变量
export DISPLAY=:99

# 本地总是连接到云服务器的信令服务器（因为本地是私网）
if [ -z "$REMOTE_IP" ]; then
    echo "❌ 本地客户端需要提供云服务器IP地址"
    echo "用法: $0 <sender|receiver> <cloud_server_ip>"
    kill $XVFB_PID 2>/dev/null || true
    exit 1
fi

echo "2️⃣ 测试与云服务器信令服务器连接..."
if timeout 5 bash -c "echo > /dev/tcp/$REMOTE_IP/8888" 2>/dev/null; then
    echo "✅ 成功连接到云服务器 $REMOTE_IP:8888"
else
    echo "❌ 无法连接到云服务器 $REMOTE_IP:8888"
    echo "🔧 请检查云服务器是否已启动信令服务器"
    echo ""
    read -p "是否仍要继续尝试连接？(y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ 连接测试失败，退出"
        kill $XVFB_PID 2>/dev/null || true
        exit 1
    fi
fi

if [ "$ROLE" = "sender" ]; then
    # 本地作为发送端，连接到云服务器信令服务器
    echo "3️⃣ 创建发送端配置文件..."
    cat > webrtc_config_results/sender_config_local.json << EOF
{
  "video_source": {
    "camera": {"enabled": false},
    "video_file": {
      "enabled": true,
      "file_path": "$(pwd)/VCD_th_1920x1080_30_120s_compressed.yuv",
      "width": 1920, "height": 1080, "fps": 30
    },
    "video_disabled": {"enabled": false}
  },
  "video_output": {
    "enabled": false
  },
  "logging": {
    "level": "info", "save_to_file": true,
    "log_output_path": "$(pwd)/webrtc_config_results/sender_local.log"
  },
  "server": {
    "host": "$REMOTE_IP",
    "port": 8888,
    "auto_connect": true,
    "auto_call": true
  },
  "auto_close_on_completion": true,
  "transmission_time_seconds": 15
}
EOF
    
    echo "4️⃣ 启动本地发送端..."
    ./src/out/Default/peerconnection_client \
        --config=webrtc_config_results/sender_config_local.json \
        --force_fieldtrials=WebRTC-DefaultBitrateLimitsKillSwitch/Enabled/ \
        > webrtc_config_results/sender_local.log 2>&1 &
    CLIENT_PID=$!
    
    echo "✅ 本地发送端已启动:"
    echo "   - Xvfb (PID: $XVFB_PID)"
    echo "   - Sender (PID: $CLIENT_PID) - 连接到 $REMOTE_IP:8888"
    echo "   - 🔥 码率限制已解除 (Field Trial: DefaultBitrateLimitsKillSwitch)"
    echo ""
    echo "📝 日志文件: webrtc_config_results/sender_local.log"
    echo "📊 监控传输状态..."
    
    wait $CLIENT_PID
    echo "✅ 视频传输完成！"
    
elif [ "$ROLE" = "receiver" ]; then
    # 本地作为接收端，连接到云服务器信令服务器
    echo "3️⃣ 创建接收端配置文件..."
    cat > webrtc_config_results/receiver_config_local.json << EOF
{
  "video_source": {
    "camera": {"enabled": false},
    "video_file": {"enabled": false},
    "video_disabled": {"enabled": true}
  },
  "video_output": {
    "enabled": true,
    "file_path": "$(pwd)/webrtc_config_results/received_local.y4m",
    "width": 1920, "height": 1080, "fps": 30
  },
  "logging": {
    "level": "info", "save_to_file": true,
    "log_output_path": "$(pwd)/webrtc_config_results/receiver_local.log"
  },
  "server": {
    "host": "$REMOTE_IP",
    "port": 8888,
    "auto_connect": true,
    "auto_call": false
  },
  "auto_close_on_completion": true,
  "transmission_time_seconds": 15
}
EOF
    
    echo "4️⃣ 启动本地接收端..."
    ./src/out/Default/peerconnection_client \
        --config=webrtc_config_results/receiver_config_local.json \
        --force_fieldtrials=WebRTC-DefaultBitrateLimitsKillSwitch/Enabled/ \
        > webrtc_config_results/receiver_local.log 2>&1 &
    CLIENT_PID=$!
    
    echo "✅ 本地接收端已启动:"
    echo "   - Xvfb (PID: $XVFB_PID)"
    echo "   - Receiver (PID: $CLIENT_PID) - 连接到 $REMOTE_IP:8888"
    echo "   - 🔥 码率限制已解除 (Field Trial: DefaultBitrateLimitsKillSwitch)"
    echo ""
    echo "📝 日志文件: webrtc_config_results/receiver_local.log"
    echo "📁 接收视频将保存到: webrtc_config_results/received_local.y4m"
    echo "📊 监控接收状态..."
    
    # 监控日志输出
    echo "📊 实时监控接收端日志（按Ctrl+C停止）..."
    tail -f webrtc_config_results/receiver_local.log &
    TAIL_PID=$!
    
    # 等待用户中断
    trap 'echo ""; echo "🛑 正在停止所有进程..."; kill $CLIENT_PID $XVFB_PID $TAIL_PID 2>/dev/null || true; exit 0' INT
    
    wait $CLIENT_PID
    echo "✅ 视频接收完成！"
    
    echo "📊 检查接收到的视频文件..."
    ls -lh webrtc_config_results/received_local.y4m 2>/dev/null || echo "未生成视频文件"
fi

echo ""
echo "🎉 任务完成！"

# 清理函数
cleanup() {
    echo "🧹 清理进程..."
    kill $XVFB_PID $CLIENT_PID 2>/dev/null || true
    pkill -f "peerconnection_client" 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM
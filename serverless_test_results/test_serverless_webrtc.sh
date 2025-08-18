#!/bin/bash

# 🎯 启动AlphaRTC Serverless P2P测试流程（发送端 + 接收端）
echo "🎯 启动AlphaRTC Serverless P2P测试流程（发送端 + 接收端）..."

# 📁 设置工作目录
BASE_DIR="/home/wuq/webrtc-checkout"
CONFIG_DIR="${BASE_DIR}/serverless_test_results"
SERVERLESS_BIN="${BASE_DIR}/AlphaRTC/out/Default/peerconnection_serverless"

# 🔧 设置ONNX库路径
export LD_LIBRARY_PATH="${BASE_DIR}/AlphaRTC/modules/third_party/onnxinfer/lib:$LD_LIBRARY_PATH"

echo "📁 使用专用目录: serverless_test_results"
echo "🧹 清理现有进程..."

# 🧹 清理现有进程（如果有）
pkill -f "peerconnection_serverless" 2>/dev/null || true
pkill -f "Xvfb" 2>/dev/null || true

# 📂 确保在正确的工作目录
cd "${CONFIG_DIR}"
echo "📂 工作目录: $(pwd)"
echo "📁 配置目录: ${CONFIG_DIR}"

# ✅ 检查serverless二进制文件
if [[ ! -f "${SERVERLESS_BIN}" ]]; then
    echo "❌ 错误: 找不到 serverless 二进制文件: ${SERVERLESS_BIN}"
    echo "🔧 请先编译 AlphaRTC serverless:"
    echo "   cd ${BASE_DIR}/AlphaRTC && ninja -C out/Default peerconnection_serverless"
    exit 1
fi

# ✅ 检查配置文件
if [[ ! -f "serverless_sender_config.json" || ! -f "serverless_receiver_config.json" ]]; then
    echo "❌ 错误: 找不到 serverless 配置文件"
    echo "📝 需要的文件:"
    echo "   - serverless_sender_config.json"
    echo "   - serverless_receiver_config.json"
    exit 1
fi

# 🧹 清理之前的输出文件
echo "🧹 清理之前的输出文件..."
rm -f serverless_*.log serverless_*.y4m serverless_*.wav

echo "1️⃣ 启动虚拟显示Xvfb..."
# 启动虚拟显示服务器
export DISPLAY=:99
Xvfb :99 -screen 0 1024x768x24 >/dev/null 2>&1 &
XVFB_PID=$!
sleep 2

# 📁 切换到corpus目录（配置文件使用相对路径）
CORPUS_DIR="${BASE_DIR}/AlphaRTC/examples/peerconnection/serverless/corpus"
cd "${CORPUS_DIR}"

# 📋 复制配置文件到corpus目录（临时使用）
cp "${CONFIG_DIR}/serverless_receiver_config.json" .
cp "${CONFIG_DIR}/serverless_sender_config.json" .

echo "2️⃣ 启动接收端（监听模式）..."
# 启动接收端（监听模式）
"${SERVERLESS_BIN}" "serverless_receiver_config.json" >"${CONFIG_DIR}/serverless_receiver.log" 2>&1 &
RECEIVER_PID=$!

# 等待接收端启动
echo "⏳ 等待接收端启动（3秒）..."
sleep 3

echo "3️⃣ 启动发送端（连接模式）..."
# 启动发送端（连接模式）
"${SERVERLESS_BIN}" "serverless_sender_config.json" >"${CONFIG_DIR}/serverless_sender.log" 2>&1 &
SENDER_PID=$!

echo "⏳ 等待传输完成（autoclose: 15秒）..."
echo "📊 监控进程状态..."

# 监控传输进程，等待自动关闭
START_TIME=$(date +%s)
TIMEOUT=25  # 比autoclose多10秒的超时时间

while true; do
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))
    
    # 检查进程是否还在运行
    if ! kill -0 $RECEIVER_PID 2>/dev/null && ! kill -0 $SENDER_PID 2>/dev/null; then
        echo "✅ 传输完成！两个进程都已正常结束"
        break
    fi
    
    # 超时检查
    if [[ $ELAPSED -gt $TIMEOUT ]]; then
        echo "⚠️  超时！强制结束进程..."
        kill $RECEIVER_PID $SENDER_PID 2>/dev/null || true
        break
    fi
    
    # 显示进度
    echo "⏱️  运行时间: ${ELAPSED}s / ${TIMEOUT}s"
    sleep 2
done

# 🧹 清理进程
echo "🧹 清理进程..."
kill $XVFB_PID $RECEIVER_PID $SENDER_PID 2>/dev/null || true
wait 2>/dev/null || true

# 🧹 清理临时配置文件
cd "${CORPUS_DIR}"
rm -f serverless_receiver_config.json serverless_sender_config.json
cd "${CONFIG_DIR}"

echo ""
echo "📊 === AlphaRTC Serverless 测试结果分析 ==="

# 📊 检查日志文件
echo ""
echo "📄 生成的日志文件:"
ls -lh serverless_*.log 2>/dev/null || echo "❌ 没有找到日志文件"

# 📊 检查视频文件
echo ""
echo "🎥 生成的视频文件:"
if ls serverless_*video*.y4m >/dev/null 2>&1; then
    for file in serverless_*video*.y4m; do
        if [[ -f "$file" ]]; then
            SIZE=$(du -h "$file" | cut -f1)
            FRAMES=$(grep -c "FRAME" "$file" 2>/dev/null || echo "0")
            echo "  📁 $file: ${SIZE}, 帧数: ${FRAMES}"
        fi
    done
else
    echo "❌ 没有找到视频文件"
fi

# 📊 检查音频文件
echo ""
echo "🎵 生成的音频文件:"
if ls serverless_*.wav >/dev/null 2>&1; then
    for file in serverless_*.wav; do
        if [[ -f "$file" ]]; then
            SIZE=$(du -h "$file" | cut -f1)
            echo "  📁 $file: ${SIZE}"
        fi
    done
else
    echo "❌ 没有找到音频文件"
fi

# 📊 连接分析
echo ""
echo "🔗 连接状态分析:"
if [[ -f "serverless_sender.log" ]]; then
    SENDER_CONN=$(grep -i "connected\|connection\|peer" serverless_sender.log | wc -l)
    echo "  📤 发送端连接事件: ${SENDER_CONN}"
fi

if [[ -f "serverless_receiver.log" ]]; then
    RECEIVER_CONN=$(grep -i "connected\|connection\|peer" serverless_receiver.log | wc -l)
    echo "  📥 接收端连接事件: ${RECEIVER_CONN}"
fi

# 📊 错误检查
echo ""
echo "❌ 错误检查:"
if ls serverless_*.log >/dev/null 2>&1; then
    ERROR_COUNT=$(grep -i "error\|failed\|exception" serverless_*.log | wc -l)
    if [[ $ERROR_COUNT -gt 0 ]]; then
        echo "  ⚠️  发现 ${ERROR_COUNT} 个错误，检查日志文件了解详情"
        echo "  🔍 错误详情:"
        grep -i "error\|failed\|exception" serverless_*.log | head -5
    else
        echo "  ✅ 没有发现错误"
    fi
else
    echo "  ❓ 无法检查错误（没有日志文件）"
fi

echo ""
echo "🎉 AlphaRTC Serverless 测试完成！"
echo "📁 所有结果文件都保存在: $(pwd)"
echo ""

# 🔧 提供进程清理命令（以防万一）
echo "⚠️  若要手动清理进程，请运行: pkill -f 'peerconnection_serverless|Xvfb'"
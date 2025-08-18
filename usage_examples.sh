#!/bin/bash

# 🎯 WebRTC自动化测试使用示例脚本
# 展示如何使用不同的配置选项运行测试

set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$BASE_DIR/automated_webrtc_test.py"
RESULTS_DIR="$BASE_DIR/results"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_separator() {
    echo -e "${BLUE}===========================================${NC}"
}

show_usage() {
    echo -e "${BLUE}"
    echo "🎯 WebRTC自动化测试使用示例"
    echo "============================="
    echo -e "${NC}"
    echo "本脚本展示了几种不同的测试运行方式："
    echo ""
    echo "1. 🆕 生成新配置文件并运行测试"
    echo "2. 🔄 使用已有配置文件运行测试"
    echo "3. ⚙️  检查已有配置文件"
    echo "4. 📝 显示帮助信息"
    echo ""
}

check_existing_configs() {
    echo -e "${YELLOW}📂 检查已有配置文件...${NC}"
    echo ""
    
    if [[ -f "$RESULTS_DIR/sender_config.json" ]] && [[ -f "$RESULTS_DIR/receiver_config.json" ]]; then
        echo -e "${GREEN}✅ 找到已有配置文件:${NC}"
        echo "   📤 Sender: $RESULTS_DIR/sender_config.json"
        echo "   📥 Receiver: $RESULTS_DIR/receiver_config.json"
        echo ""
        
        echo -e "${BLUE}📋 Sender配置摘要:${NC}"
        echo "$(cat "$RESULTS_DIR/sender_config.json" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'   视频源: {\"文件\" if data.get(\"video_source\", {}).get(\"video_file\", {}).get(\"enabled\", False) else \"摄像头\" if data.get(\"video_source\", {}).get(\"camera\", {}).get(\"enabled\", False) else \"禁用\"}')
print(f'   服务器: {data.get(\"server\", {}).get(\"host\", \"localhost\")}:{data.get(\"server\", {}).get(\"port\", 8888)}')
print(f'   自动关闭: {\"是\" if data.get(\"auto_close_on_completion\", False) else \"否\"}')
")"
        echo ""
        
        echo -e "${BLUE}📋 Receiver配置摘要:${NC}"
        echo "$(cat "$RESULTS_DIR/receiver_config.json" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'   视频输出: {\"是\" if data.get(\"video_output\", {}).get(\"enabled\", False) else \"否\"}')
print(f'   服务器: {data.get(\"server\", {}).get(\"host\", \"localhost\")}:{data.get(\"server\", {}).get(\"port\", 8888)}')
print(f'   自动关闭: {\"是\" if data.get(\"auto_close_on_completion\", False) else \"否\"}')
")"
        echo ""
        return 0
    else
        echo -e "${RED}❌ 未找到完整的配置文件${NC}"
        echo "需要的文件:"
        echo "   📤 $RESULTS_DIR/sender_config.json"
        echo "   📥 $RESULTS_DIR/receiver_config.json"
        echo ""
        return 1
    fi
}

run_with_new_config() {
    print_separator
    echo -e "${GREEN}🆕 运行测试（生成新配置文件）${NC}"
    print_separator
    echo ""
    echo "这将会:"
    echo "• 🔧 生成新的配置文件"
    echo "• 🎥 使用test_video.yuv作为输入"
    echo "• 💾 保存接收到的视频"
    echo "• 🔄 启用自动关闭功能"
    echo "• 📊 收集视频质量指标"
    echo ""
    
    echo -e "${BLUE}执行命令:${NC}"
    echo "python3 $PYTHON_SCRIPT --non-interactive"
    echo ""
    
    python3 "$PYTHON_SCRIPT" --non-interactive
}

run_with_existing_config() {
    print_separator
    echo -e "${GREEN}🔄 运行测试（使用已有配置文件）${NC}"
    print_separator
    echo ""
    
    # 检查配置文件
    if ! check_existing_configs; then
        echo -e "${YELLOW}⚠️  将改为生成新配置文件...${NC}"
        echo ""
        run_with_new_config
        return
    fi
    
    echo "这将会:"
    echo "• 📂 使用现有的sender_config.json和receiver_config.json"
    echo "• 🔄 强制启用自动关闭功能（除非使用--no-auto-close）"
    echo "• 📝 更新日志文件路径为带时间戳的版本"
    echo "• 🎥 更新输出视频文件路径"
    echo ""
    
    echo -e "${BLUE}执行命令:${NC}"
    echo "python3 $PYTHON_SCRIPT --use-existing-config --non-interactive"
    echo ""
    
    python3 "$PYTHON_SCRIPT" --use-existing-config --non-interactive
}

show_help() {
    print_separator
    echo -e "${BLUE}📖 详细帮助信息${NC}"
    print_separator
    echo ""
    
    python3 "$PYTHON_SCRIPT" --help
    echo ""
    
    echo -e "${YELLOW}💡 常用命令示例:${NC}"
    echo ""
    echo "# 🆕 生成新配置并运行（交互模式）"
    echo "python3 automated_webrtc_test.py"
    echo ""
    echo "# 🔄 使用已有配置运行（非交互模式）"
    echo "python3 automated_webrtc_test.py --use-existing-config --non-interactive"
    echo ""
    echo "# ⚙️  使用已有配置但不强制自动关闭"
    echo "python3 automated_webrtc_test.py --use-existing-config --no-auto-close"
    echo ""
    echo "# 🚀 快速运行（生成新配置，非交互模式）"
    echo "python3 automated_webrtc_test.py --non-interactive"
    echo ""
}

# 主菜单
while true; do
    show_usage
    echo -n -e "${BLUE}请选择操作 [1-4]: ${NC}"
    read choice
    echo ""
    
    case $choice in
        1)
            run_with_new_config
            ;;
        2)
            run_with_existing_config
            ;;
        3)
            check_existing_configs
            ;;
        4)
            show_help
            ;;
        *)
            echo -e "${RED}❌ 无效选择，请输入1-4${NC}"
            ;;
    esac
    
    echo ""
    echo -n -e "${BLUE}按Enter键继续...${NC}"
    read
    clear
done
#!/bin/bash

# 快速编译 GoogCC 模块的脚本

set -e

echo "=========================================="
echo "  编译 GoogCC 模块 (增量编译)"
echo "=========================================="

cd src

# 1. 首先检查 BUILD.gn 是否包含新文件
echo "检查 BUILD.gn..."
BUILD_FILE="modules/congestion_controller/goog_cc/BUILD.gn"

if ! grep -q "cellular_ratio_receiver.cc" $BUILD_FILE; then
    echo "⚠️  需要更新 BUILD.gn"
    echo "在 rtc_library(\"goog_cc\") 的 sources 列表中添加："
    echo '    "cellular_ratio_receiver.cc",'
    echo '    "cellular_ratio_receiver.h",'
    
    # 尝试自动添加
    echo ""
    echo "尝试自动添加..."
    
    # 在 delay_based_bwe.cc 后面添加新文件
    sed -i '/delay_based_bwe.cc/a\    "cellular_ratio_receiver.cc",\n    "cellular_ratio_receiver.h",' $BUILD_FILE
    
    if grep -q "cellular_ratio_receiver.cc" $BUILD_FILE; then
        echo "✅ BUILD.gn 已自动更新"
    else
        echo "❌ 自动更新失败，请手动编辑 $BUILD_FILE"
        exit 1
    fi
fi

# 2. 生成构建文件（如果需要）
if [ ! -d "out/Default" ]; then
    echo "生成构建文件..."
    gn gen out/Default
fi

# 3. 只编译 goog_cc 相关目标
echo ""
echo "编译目标："
echo "  1. goog_cc 库"
echo "  2. delay_based_bwe 测试"
echo ""

# 编译 goog_cc 库
echo "编译 goog_cc..."
ninja -C out/Default modules/congestion_controller/goog_cc:goog_cc

# 可选：编译相关的单元测试
echo ""
echo "编译 delay_based_bwe 单元测试..."
ninja -C out/Default modules/congestion_controller/goog_cc:delay_based_bwe_unittest

echo ""
echo "✅ 编译完成！"
echo ""
echo "可以运行的测试："
echo "  ./out/Default/modules_unittests --gtest_filter='DelayBasedBweTest*'"
echo ""

cd ..
#!/bin/bash

# 在 BUILD.gn 中添加测试目标

BUILD_FILE="src/modules/congestion_controller/goog_cc/BUILD.gn"

# 检查是否已经有这个目标
if grep -q "test_cellular_pipeline" $BUILD_FILE; then
    echo "test_cellular_pipeline 目标已存在"
else
    echo "添加 test_cellular_pipeline 目标到 BUILD.gn..."
    
    # 在文件末尾添加新的可执行目标
    cat >> $BUILD_FILE << 'EOF'

rtc_executable("test_cellular_pipeline") {
  testonly = true
  sources = [ "test_cellular_pipeline.cc" ]
  deps = [
    ":goog_cc",
    "../../../api:network_state_predictor_api",
    "../../../api/environment:environment_factory",
    "../../../api/task_queue:default_task_queue_factory",
    "../../../api/transport:network_control",
    "../../../rtc_base:logging",
    "../../../rtc_base:rtc_base_approved",
  ]
}
EOF
    
    echo "✅ 已添加 test_cellular_pipeline 目标"
fi

echo ""
echo "现在可以编译测试程序："
echo "  cd src"
echo "  ninja -C out/Default modules/congestion_controller/goog_cc:test_cellular_pipeline"
echo ""
echo "运行测试："
echo "  ./out/Default/test_cellular_pipeline"
/*
 * 最小测试程序 - 验证 Cellular Ratio 数据管道
 * 
 * 编译:
 * ninja -C out/Default modules/congestion_controller/goog_cc:test_cellular_pipeline
 */

#include <iostream>
#include <thread>
#include <chrono>

#include "api/environment/environment_factory.h"
#include "api/transport/network_control.h"
#include "api/units/data_rate.h"
#include "api/units/timestamp.h"
#include "modules/congestion_controller/goog_cc/goog_cc_network_control.h"
#include "rtc_base/checks.h"
#include "rtc_base/logging.h"

using namespace webrtc;

int main() {
  // 初始化日志
  ::LogMessage::LogToDebug(::LS_INFO);
  ::LogMessage::SetLogToStderr(true);
  
  std::cout << "=================================\n";
  std::cout << " Cellular Ratio Pipeline Test\n";
  std::cout << "=================================\n\n";
  
  // 创建环境
  auto env = EnvironmentFactory().Create();
  
  // 配置 NetworkController
  NetworkControllerConfig config(env);
  
  // 设置初始约束
  config.constraints.at_time = Timestamp::Millis(0);
  config.constraints.starting_rate = DataRate::KilobitsPerSec(1000);
  config.constraints.min_data_rate = DataRate::KilobitsPerSec(100);
  config.constraints.max_data_rate = DataRate::KilobitsPerSec(10000);
  
  // 创建 GoogCcConfig
  GoogCcConfig goog_cc_config;
  
  std::cout << "创建 GoogCcNetworkController...\n";
  
  // 创建 GoogCcNetworkController
  auto controller = std::make_unique<GoogCcNetworkController>(
      config, std::move(goog_cc_config));
  
  std::cout << "✅ Controller 创建成功\n";
  std::cout << "\n检查日志输出:\n";
  std::cout << "  - 应该看到: [GoogCC] Initializing CellularRatioReceiver\n";
  std::cout << "  - 应该看到: [CellularReceiver] Socket bound to: /tmp/webrtc_cellular_ratio.sock\n";
  std::cout << "\n等待 30 秒接收数据...\n";
  std::cout << "请在另一个终端运行: python3 send_test_ratio.py\n\n";
  
  // 模拟一些网络活动 - 运行30秒
  for (int i = 0; i < 300; ++i) {
    // 触发定期处理
    ProcessInterval process_msg;
    process_msg.at_time = Timestamp::Millis(i * 100);
    controller->OnProcessInterval(process_msg);
    
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
    
    if (i % 10 == 0) {
      std::cout << "." << std::flush;
    }
  }
  
  std::cout << "\n\n测试完成!\n";
  std::cout << "如果看到 [DelayBWE-Cellular] DATA RECEIVED 日志，说明数据管道打通了!\n";
  
  return 0;
}
# CellularRatioReceiver 实现方案

## 架构决策总结

### ✅ 为什么选择 GoogCcNetworkController 作为集成点

1. **架构合理性**
   - GoogCcNetworkController 是拥塞控制的总协调器
   - 所有外部信号（网络变化、路由变化等）都在这里汇集
   - 符合 "关注点分离" 原则

2. **访问便利性**
   - 直接拥有 `delay_based_bwe_` 实例
   - 可以访问 `network_queue_` 任务队列
   - 生命周期与连接完全匹配

3. **线程安全**
   - 已有成熟的任务队列机制
   - 可以安全地将数据从接收线程转发到网络线程

### ✅ 为什么使用 SOCK_DGRAM

- **简单性**: 无需连接管理
- **容错性**: 丢包不影响后续数据
- **实时性**: 总是获取最新数据，不会积压

## 详细实现方案

### 1. 数据协议定义

```cpp
// cellular_ratio_protocol.h
#ifndef CELLULAR_RATIO_PROTOCOL_H_
#define CELLULAR_RATIO_PROTOCOL_H_

#include <cstdint>

namespace webrtc {

// Wire format for cellular ratio data (20 bytes total)
struct CellularRatioPacket {
  uint64_t timestamp_ms;    // 8 bytes: Unix timestamp in milliseconds
  double ratio;              // 8 bytes: Resource ratio (allocated/requested)
  uint32_t sequence_number;  // 4 bytes: For debugging/monitoring
} __attribute__((packed));

// Internal representation with additional metadata
struct CellularRatioData {
  double ratio;
  Timestamp receive_time;
  Timestamp sender_time;
  uint32_t sequence_number;
  
  // Computed fields
  TimeDelta latency;  // receive_time - sender_time
  bool is_fresh() const {
    return latency < TimeDelta::Millis(200);
  }
};

// Socket configuration
constexpr char kCellularRatioSocketPath[] = "/tmp/webrtc_cellular_ratio.sock";
constexpr size_t kMaxPacketSize = sizeof(CellularRatioPacket);

}  // namespace webrtc

#endif
```

### 2. CellularRatioReceiver 类实现

```cpp
// cellular_ratio_receiver.h
#ifndef CELLULAR_RATIO_RECEIVER_H_
#define CELLULAR_RATIO_RECEIVER_H_

#include <atomic>
#include <memory>
#include <thread>

#include "api/task_queue/task_queue_base.h"
#include "api/units/timestamp.h"
#include "modules/congestion_controller/goog_cc/delay_based_bwe.h"
#include "rtc_base/synchronization/mutex.h"

namespace webrtc {

class CellularRatioReceiver {
 public:
  CellularRatioReceiver(TaskQueueBase* network_queue,
                        DelayBasedBwe* delay_based_bwe);
  ~CellularRatioReceiver();
  
  // Start/stop the receiver thread
  bool Start();
  void Stop();
  
  // Statistics
  struct Stats {
    uint32_t packets_received = 0;
    uint32_t packets_dropped = 0;
    uint32_t parse_errors = 0;
    Timestamp last_receive_time = Timestamp::MinusInfinity();
  };
  Stats GetStats() const;
  
 private:
  void ReceiverThreadLoop();
  bool SetupSocket();
  void CleanupSocket();
  void ProcessPacket(const uint8_t* data, size_t len);
  void PostToNetworkQueue(const CellularRatioData& data);
  
  // Configuration
  const std::string socket_path_;
  
  // Dependencies (not owned)
  TaskQueueBase* const network_queue_;
  DelayBasedBwe* const delay_based_bwe_;
  
  // Socket
  int socket_fd_ = -1;
  
  // Thread management
  std::atomic<bool> running_{false};
  std::unique_ptr<std::thread> receiver_thread_;
  
  // Statistics (protected by mutex)
  mutable Mutex stats_mutex_;
  Stats stats_ RTC_GUARDED_BY(stats_mutex_);
};

}  // namespace webrtc

#endif
```

```cpp
// cellular_ratio_receiver.cc
#include "cellular_ratio_receiver.h"

#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <cstring>

#include "rtc_base/logging.h"
#include "rtc_base/time_utils.h"

namespace webrtc {

CellularRatioReceiver::CellularRatioReceiver(
    TaskQueueBase* network_queue,
    DelayBasedBwe* delay_based_bwe)
    : socket_path_(kCellularRatioSocketPath),
      network_queue_(network_queue),
      delay_based_bwe_(delay_based_bwe) {
  RTC_DCHECK(network_queue_);
  RTC_DCHECK(delay_based_bwe_);
}

CellularRatioReceiver::~CellularRatioReceiver() {
  Stop();
}

bool CellularRatioReceiver::Start() {
  if (running_.exchange(true)) {
    RTC_LOG(LS_WARNING) << "CellularRatioReceiver already running";
    return false;
  }
  
  receiver_thread_ = std::make_unique<std::thread>(
      [this] { ReceiverThreadLoop(); });
  
  RTC_LOG(LS_INFO) << "CellularRatioReceiver started";
  return true;
}

void CellularRatioReceiver::Stop() {
  if (!running_.exchange(false)) {
    return;
  }
  
  // Close socket to unblock recvfrom
  if (socket_fd_ >= 0) {
    shutdown(socket_fd_, SHUT_RDWR);
  }
  
  if (receiver_thread_ && receiver_thread_->joinable()) {
    receiver_thread_->join();
  }
  
  CleanupSocket();
  RTC_LOG(LS_INFO) << "CellularRatioReceiver stopped";
}

void CellularRatioReceiver::ReceiverThreadLoop() {
  RTC_LOG(LS_INFO) << "Receiver thread started";
  
  if (!SetupSocket()) {
    RTC_LOG(LS_ERROR) << "Failed to setup socket";
    return;
  }
  
  uint8_t buffer[kMaxPacketSize];
  
  while (running_) {
    // Blocking receive
    ssize_t bytes_received = recvfrom(socket_fd_, buffer, sizeof(buffer),
                                      0, nullptr, nullptr);
    
    if (bytes_received < 0) {
      if (errno == EINTR) {
        continue;  // Interrupted, retry
      }
      if (running_) {
        RTC_LOG(LS_ERROR) << "recvfrom failed: " << strerror(errno);
      }
      break;
    }
    
    if (bytes_received == sizeof(CellularRatioPacket)) {
      ProcessPacket(buffer, bytes_received);
    } else {
      MutexLock lock(&stats_mutex_);
      stats_.parse_errors++;
      RTC_LOG(LS_WARNING) << "Invalid packet size: " << bytes_received;
    }
  }
  
  CleanupSocket();
  RTC_LOG(LS_INFO) << "Receiver thread stopped";
}

bool CellularRatioReceiver::SetupSocket() {
  // Create Unix datagram socket
  socket_fd_ = socket(AF_UNIX, SOCK_DGRAM, 0);
  if (socket_fd_ < 0) {
    RTC_LOG(LS_ERROR) << "Failed to create socket: " << strerror(errno);
    return false;
  }
  
  // Prepare socket address
  struct sockaddr_un addr;
  memset(&addr, 0, sizeof(addr));
  addr.sun_family = AF_UNIX;
  strncpy(addr.sun_path, socket_path_.c_str(), sizeof(addr.sun_path) - 1);
  
  // Remove existing socket file
  unlink(socket_path_.c_str());
  
  // Bind socket
  if (bind(socket_fd_, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
    RTC_LOG(LS_ERROR) << "Failed to bind socket: " << strerror(errno);
    close(socket_fd_);
    socket_fd_ = -1;
    return false;
  }
  
  RTC_LOG(LS_INFO) << "Socket bound to: " << socket_path_;
  return true;
}

void CellularRatioReceiver::CleanupSocket() {
  if (socket_fd_ >= 0) {
    close(socket_fd_);
    socket_fd_ = -1;
  }
  unlink(socket_path_.c_str());
}

void CellularRatioReceiver::ProcessPacket(const uint8_t* data, size_t len) {
  const auto* packet = reinterpret_cast<const CellularRatioPacket*>(data);
  
  // Create internal data structure
  CellularRatioData ratio_data;
  ratio_data.ratio = packet->ratio;
  ratio_data.sender_time = Timestamp::Millis(packet->timestamp_ms);
  ratio_data.receive_time = Timestamp::Millis(rtc::TimeMillis());
  ratio_data.sequence_number = packet->sequence_number;
  ratio_data.latency = ratio_data.receive_time - ratio_data.sender_time;
  
  // Update stats
  {
    MutexLock lock(&stats_mutex_);
    stats_.packets_received++;
    stats_.last_receive_time = ratio_data.receive_time;
  }
  
  // Log every 10th packet to avoid spam
  if (packet->sequence_number % 10 == 0) {
    RTC_LOG(LS_INFO) << "[CellularRatio] Received seq=" << packet->sequence_number
                     << " ratio=" << packet->ratio
                     << " latency=" << ratio_data.latency.ms() << "ms";
  }
  
  // Post to network queue
  PostToNetworkQueue(ratio_data);
}

void CellularRatioReceiver::PostToNetworkQueue(const CellularRatioData& data) {
  // Check if data is fresh enough
  if (!data.is_fresh()) {
    RTC_LOG(LS_WARNING) << "Dropping stale packet, latency=" 
                        << data.latency.ms() << "ms";
    MutexLock lock(&stats_mutex_);
    stats_.packets_dropped++;
    return;
  }
  
  // Post task to network queue
  network_queue_->PostTask([this, data] {
    // This runs on the network thread
    if (delay_based_bwe_) {
      delay_based_bwe_->UpdateCellularResourceRatio(
          data.ratio, data.receive_time);
    }
  });
}

CellularRatioReceiver::Stats CellularRatioReceiver::GetStats() const {
  MutexLock lock(&stats_mutex_);
  return stats_;
}

}  // namespace webrtc
```

### 3. GoogCcNetworkController 集成

```cpp
// 修改 goog_cc_network_controller.h
class GoogCcNetworkController {
  // ... existing code ...
  
 private:
  // 新增成员
  std::unique_ptr<CellularRatioReceiver> cellular_ratio_receiver_;
};

// 修改 goog_cc_network_controller.cc
GoogCcNetworkController::GoogCcNetworkController(
    NetworkControllerConfig config,
    GoogCcConfig goog_cc_config)
    : ... {
  
  // ... existing initialization ...
  
  // 创建 delay_based_bwe
  delay_based_bwe_ = std::make_unique<DelayBasedBwe>(...);
  
  // 新增：创建并启动 cellular receiver
  if (config.enable_cellular_ratio) {  // 通过配置控制
    cellular_ratio_receiver_ = std::make_unique<CellularRatioReceiver>(
        config.task_queue, delay_based_bwe_.get());
    
    if (!cellular_ratio_receiver_->Start()) {
      RTC_LOG(LS_ERROR) << "Failed to start CellularRatioReceiver";
      cellular_ratio_receiver_.reset();
    }
  }
}

GoogCcNetworkController::~GoogCcNetworkController() {
  // 停止 receiver（如果存在）
  if (cellular_ratio_receiver_) {
    cellular_ratio_receiver_->Stop();
  }
}
```

### 4. DelayBasedBwe 桩函数

```cpp
// delay_based_bwe.h
void UpdateCellularResourceRatio(double ratio, Timestamp at_time);

// delay_based_bwe.cc
void DelayBasedBwe::UpdateCellularResourceRatio(double ratio, 
                                                Timestamp at_time) {
  // 第一阶段：仅打印日志验证通路
  RTC_LOG(LS_INFO) << "[DelayBWE-Cellular] ✓ Data received!"
                   << " ratio=" << ratio
                   << " time=" << at_time.ms() << "ms";
  
  // 第二阶段：传递给 rate_control_
  // rate_control_.SetCellularResourceRatio(ratio, at_time);
}
```

## 测试验证步骤

### Step 1: 编译验证
```bash
# 添加新文件到 BUILD.gn
ninja -C out/Default modules/congestion_controller:goog_cc
```

### Step 2: 创建测试发送器
```cpp
// test_ratio_sender.cc
int main() {
  int sock = socket(AF_UNIX, SOCK_DGRAM, 0);
  
  struct sockaddr_un addr;
  addr.sun_family = AF_UNIX;
  strcpy(addr.sun_path, "/tmp/webrtc_cellular_ratio.sock");
  
  for (uint32_t seq = 0; seq < 100; ++seq) {
    CellularRatioPacket packet;
    packet.timestamp_ms = rtc::TimeMillis();
    packet.ratio = 0.5 + 0.5 * sin(seq * 0.1);  // 正弦波
    packet.sequence_number = seq;
    
    sendto(sock, &packet, sizeof(packet), 0,
           (struct sockaddr*)&addr, sizeof(addr));
    
    usleep(100000);  // 100ms
  }
  
  close(sock);
  return 0;
}
```

### Step 3: 运行测试
```bash
# Terminal 1: 启动WebRTC应用
./webrtc_test --enable_cellular_ratio=true

# Terminal 2: 发送测试数据
./test_ratio_sender

# 查看日志
grep "CellularRatio\|DelayBWE-Cellular" webrtc.log
```

## 优势总结

1. **最小侵入**: 不修改核心算法逻辑
2. **线程安全**: 利用现有的TaskQueue机制
3. **易于测试**: 可以独立测试数据通路
4. **灵活扩展**: 未来可以轻松添加更多cellular信号
5. **性能优秀**: SOCK_DGRAM避免了连接开销

## 下一步

1. ✅ 验证数据通路
2. ⏳ 实现AIMD中的ratio处理逻辑
3. ⏳ 添加性能监控和统计
4. ⏳ 真实网络环境测试
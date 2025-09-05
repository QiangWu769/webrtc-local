# 数据管道实施步骤 - 从简到繁

## 实施顺序（从最简单开始）

### Step 1: 创建独立的测试发送器 ✅ 最先做
**为什么先做这个**：
- 完全独立，不需要修改WebRTC代码
- 可以立即测试
- 用于验证后续所有步骤

**文件**: `test/test_ratio_sender.cc`

```cpp
// test_ratio_sender.cc
// 一个简单的独立程序，发送测试数据
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <cstring>
#include <cstdio>
#include <cmath>
#include <chrono>

struct CellularRatioPacket {
    uint64_t timestamp_ms;
    double ratio;
    uint32_t sequence_number;
} __attribute__((packed));

int main() {
    // 1. 创建socket
    int sock = socket(AF_UNIX, SOCK_DGRAM, 0);
    if (sock < 0) {
        perror("socket");
        return 1;
    }
    
    // 2. 设置目标地址
    struct sockaddr_un dest_addr;
    memset(&dest_addr, 0, sizeof(dest_addr));
    dest_addr.sun_family = AF_UNIX;
    strcpy(dest_addr.sun_path, "/tmp/webrtc_cellular_ratio.sock");
    
    printf("Starting ratio sender...\n");
    printf("Target: %s\n", dest_addr.sun_path);
    
    // 3. 发送循环
    uint32_t seq = 0;
    while (true) {
        // 生成测试数据
        CellularRatioPacket packet;
        packet.timestamp_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::system_clock::now().time_since_epoch()).count();
        
        // 生成正弦波形的ratio (0.3 - 1.0)
        packet.ratio = 0.65 + 0.35 * sin(seq * 0.1);
        packet.sequence_number = seq;
        
        // 发送
        ssize_t sent = sendto(sock, &packet, sizeof(packet), 0,
                            (struct sockaddr*)&dest_addr, sizeof(dest_addr));
        
        if (sent < 0) {
            // 接收方可能还没准备好，这是正常的
            if (errno != ENOENT && errno != ECONNREFUSED) {
                perror("sendto");
            }
        } else {
            printf("[%u] Sent ratio=%.3f\n", seq, packet.ratio);
        }
        
        seq++;
        usleep(100000); // 100ms
        
        if (seq >= 100) break; // 测试100个包
    }
    
    close(sock);
    printf("Test complete\n");
    return 0;
}
```

**编译**:
```bash
g++ -o test_ratio_sender test_ratio_sender.cc
```

---

### Step 2: 在 DelayBasedBwe 中添加桩函数
**为什么第二步做这个**：
- 改动最小，只加一个函数
- 不影响现有逻辑
- 为后续接收数据做准备

**文件修改**: 
1. `src/modules/congestion_controller/goog_cc/delay_based_bwe.h`
2. `src/modules/congestion_controller/goog_cc/delay_based_bwe.cc`

```cpp
// delay_based_bwe.h - 在public部分添加
class DelayBasedBwe {
 public:
  // ... existing code ...
  
  // Cellular ratio support (stub for testing)
  void UpdateCellularResourceRatio(double ratio, Timestamp at_time);
  
  // ... rest of the class
};
```

```cpp
// delay_based_bwe.cc - 在文件末尾添加
void DelayBasedBwe::UpdateCellularResourceRatio(double ratio, Timestamp at_time) {
  // Step 1: 仅打印日志，验证数据到达
  RTC_LOG(LS_INFO) << "===== CELLULAR DATA RECEIVED ====="
                   << " ratio=" << ratio
                   << " time=" << at_time.ms() << "ms"
                   << " =================================";
  
  // Step 2 (后续): 传递给 rate_control_
  // rate_control_.SetCellularResourceRatio(ratio, at_time);
}
```

---

### Step 3: 创建最简单的 CellularRatioReceiver
**为什么第三步**：
- 核心接收逻辑
- 可以独立测试
- 不依赖 GoogCcNetworkController

**文件**: 
1. `src/modules/congestion_controller/goog_cc/cellular_ratio_receiver.h`
2. `src/modules/congestion_controller/goog_cc/cellular_ratio_receiver.cc`

**简化版本**（先不考虑统计等高级功能）：

```cpp
// cellular_ratio_receiver.h - 最简版本
#ifndef CELLULAR_RATIO_RECEIVER_H_
#define CELLULAR_RATIO_RECEIVER_H_

#include <atomic>
#include <thread>
#include <memory>

namespace webrtc {

// 前向声明
class TaskQueueBase;
class DelayBasedBwe;

class CellularRatioReceiver {
 public:
  CellularRatioReceiver(TaskQueueBase* task_queue, 
                       DelayBasedBwe* bwe);
  ~CellularRatioReceiver();
  
  bool Start();
  void Stop();
  
 private:
  void ReceiverLoop();
  
  TaskQueueBase* task_queue_;  // not owned
  DelayBasedBwe* bwe_;         // not owned
  
  int socket_fd_ = -1;
  std::atomic<bool> running_{false};
  std::unique_ptr<std::thread> thread_;
};

}  // namespace webrtc
#endif
```

```cpp
// cellular_ratio_receiver.cc - 最简实现
#include "modules/congestion_controller/goog_cc/cellular_ratio_receiver.h"
#include "modules/congestion_controller/goog_cc/delay_based_bwe.h"
#include "api/task_queue/task_queue_base.h"
#include "api/units/timestamp.h"
#include "rtc_base/logging.h"

#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <cstring>

namespace webrtc {

struct CellularRatioPacket {
    uint64_t timestamp_ms;
    double ratio;
    uint32_t sequence_number;
} __attribute__((packed));

CellularRatioReceiver::CellularRatioReceiver(
    TaskQueueBase* task_queue, DelayBasedBwe* bwe)
    : task_queue_(task_queue), bwe_(bwe) {
  RTC_LOG(LS_INFO) << "CellularRatioReceiver created";
}

CellularRatioReceiver::~CellularRatioReceiver() {
  Stop();
}

bool CellularRatioReceiver::Start() {
  if (running_) return false;
  
  running_ = true;
  thread_ = std::make_unique<std::thread>([this] { ReceiverLoop(); });
  
  RTC_LOG(LS_INFO) << "CellularRatioReceiver started";
  return true;
}

void CellularRatioReceiver::Stop() {
  if (!running_) return;
  
  running_ = false;
  
  // 关闭socket以解除阻塞
  if (socket_fd_ >= 0) {
    shutdown(socket_fd_, SHUT_RDWR);
    close(socket_fd_);
  }
  
  if (thread_ && thread_->joinable()) {
    thread_->join();
  }
  
  RTC_LOG(LS_INFO) << "CellularRatioReceiver stopped";
}

void CellularRatioReceiver::ReceiverLoop() {
  // 1. 创建socket
  socket_fd_ = socket(AF_UNIX, SOCK_DGRAM, 0);
  if (socket_fd_ < 0) {
    RTC_LOG(LS_ERROR) << "Failed to create socket";
    return;
  }
  
  // 2. 绑定地址
  struct sockaddr_un addr;
  memset(&addr, 0, sizeof(addr));
  addr.sun_family = AF_UNIX;
  const char* path = "/tmp/webrtc_cellular_ratio.sock";
  strcpy(addr.sun_path, path);
  
  // 删除旧文件
  unlink(path);
  
  if (bind(socket_fd_, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
    RTC_LOG(LS_ERROR) << "Failed to bind socket";
    close(socket_fd_);
    return;
  }
  
  RTC_LOG(LS_INFO) << "Socket bound to " << path;
  
  // 3. 接收循环
  uint8_t buffer[sizeof(CellularRatioPacket)];
  
  while (running_) {
    ssize_t received = recvfrom(socket_fd_, buffer, sizeof(buffer), 
                                0, nullptr, nullptr);
    
    if (received == sizeof(CellularRatioPacket)) {
      auto* packet = reinterpret_cast<CellularRatioPacket*>(buffer);
      
      // 每10个包打印一次
      if (packet->sequence_number % 10 == 0) {
        RTC_LOG(LS_INFO) << "Received: seq=" << packet->sequence_number
                         << " ratio=" << packet->ratio;
      }
      
      // 通过TaskQueue转发到网络线程
      if (task_queue_ && bwe_) {
        double ratio = packet->ratio;
        uint64_t time_ms = packet->timestamp_ms;
        
        task_queue_->PostTask([this, ratio, time_ms] {
          bwe_->UpdateCellularResourceRatio(
              ratio, Timestamp::Millis(time_ms));
        });
      }
    }
  }
  
  // 清理
  close(socket_fd_);
  unlink(path);
}

}  // namespace webrtc
```

---

### Step 4: 在 GoogCcNetworkController 中集成
**最后一步**：
- 将所有组件连接起来
- 最小修改现有代码

**修改文件**:
1. `src/modules/congestion_controller/goog_cc/goog_cc_network_controller.h`
2. `src/modules/congestion_controller/goog_cc/goog_cc_network_controller.cc`

```cpp
// goog_cc_network_controller.h - 添加成员
#include "modules/congestion_controller/goog_cc/cellular_ratio_receiver.h"

class GoogCcNetworkController {
  // ... existing code ...
 private:
  // 在成员变量最后添加
  std::unique_ptr<CellularRatioReceiver> cellular_receiver_;
};
```

```cpp
// goog_cc_network_controller.cc - 在构造函数中
GoogCcNetworkController::GoogCcNetworkController(...) {
  // ... existing initialization ...
  
  // 在创建 delay_based_bwe_ 之后添加
  if (delay_based_bwe_) {
    // 创建并启动cellular接收器
    cellular_receiver_ = std::make_unique<CellularRatioReceiver>(
        task_queue_, delay_based_bwe_.get());
    
    if (!cellular_receiver_->Start()) {
      RTC_LOG(LS_WARNING) << "Failed to start cellular receiver";
      cellular_receiver_.reset();
    } else {
      RTC_LOG(LS_INFO) << "Cellular receiver initialized";
    }
  }
}

// 在析构函数中
GoogCcNetworkController::~GoogCcNetworkController() {
  // 在最开始添加
  if (cellular_receiver_) {
    cellular_receiver_->Stop();
  }
  // ... rest of destructor
}
```

---

## 测试步骤

### 1. 编译测试发送器
```bash
cd /home/wuq/webrtc-checkout
g++ -o test_ratio_sender test/test_ratio_sender.cc
```

### 2. 编译WebRTC（假设使用ninja）
```bash
cd src
ninja -C out/Default
```

### 3. 运行测试
```bash
# Terminal 1: 启动WebRTC程序
./out/Default/webrtc_test_program

# Terminal 2: 发送测试数据
./test_ratio_sender

# 查看日志
grep "CELLULAR\|CellularRatio" /tmp/webrtc.log
```

### 期望看到的日志
```
[INFO] CellularRatioReceiver created
[INFO] CellularRatioReceiver started
[INFO] Socket bound to /tmp/webrtc_cellular_ratio.sock
[INFO] Received: seq=0 ratio=0.650
[INFO] ===== CELLULAR DATA RECEIVED ===== ratio=0.650 time=xxx =====
[INFO] Received: seq=10 ratio=0.845
[INFO] ===== CELLULAR DATA RECEIVED ===== ratio=0.845 time=xxx =====
```

## 调试技巧

1. **使用 strace 查看系统调用**
```bash
strace -e socket,bind,recvfrom,sendto ./test_ratio_sender
```

2. **检查socket文件**
```bash
ls -la /tmp/webrtc_cellular_ratio.sock
```

3. **添加更多日志**
在每个关键步骤都加上 RTC_LOG

4. **逐步验证**
- 先只运行 test_ratio_sender，看是否正常
- 再添加接收器，一步步验证
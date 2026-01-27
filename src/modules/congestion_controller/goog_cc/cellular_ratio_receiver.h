/*
 *  Cellular Ratio Receiver for WebRTC
 *  Receives BSR ratio data via Unix domain socket
 */

#ifndef MODULES_CONGESTION_CONTROLLER_GOOG_CC_CELLULAR_RATIO_RECEIVER_H_
#define MODULES_CONGESTION_CONTROLLER_GOOG_CC_CELLULAR_RATIO_RECEIVER_H_

#include <atomic>
#include <functional>
#include <memory>
#include <thread>

#include "api/task_queue/task_queue_base.h"
#include "api/units/data_rate.h"
#include "api/units/timestamp.h"

namespace webrtc {

// Forward declarations
class DelayBasedBwe;

// Callback type for notifying pacer rate updates
// Called when ratio signal triggers a rate change
using RatioRateUpdateCallback = std::function<void(DataRate pacing_rate, DataRate padding_rate)>;

// Data packet format (must match sender)
struct CellularRatioPacket {
  double ratio;       // 8 bytes
  double saturation;  // 8 bytes
} __attribute__((packed));  // Total: 16 bytes

class CellularRatioReceiver {
 public:
  // Constructor
  // task_queue: The WebRTC task queue for thread-safe callbacks
  // delay_based_bwe: The BWE instance to update with ratio data
  // on_rate_update: Callback to update pacer immediately when ratio changes
  CellularRatioReceiver(TaskQueueBase* task_queue,
                       DelayBasedBwe* delay_based_bwe,
                       RatioRateUpdateCallback on_rate_update = nullptr);
  
  // Destructor - automatically stops the receiver
  ~CellularRatioReceiver();
  
  // Start the receiver thread
  // Returns true on success, false on failure
  bool Start();
  
  // Stop the receiver thread
  void Stop();
  
  // Check if receiver is running
  bool IsRunning() const { return running_; }

  // Set callback for immediate pacer rate updates (can be set after construction)
  void SetRateUpdateCallback(RatioRateUpdateCallback callback) {
    on_rate_update_ = std::move(callback);
  }
  
 private:
  // Main receiver loop (runs in separate thread)
  void ReceiverThreadLoop();
  
  // Setup Unix domain socket
  bool SetupSocket();
  
  // Cleanup socket resources
  void CleanupSocket();
  
  // Process received packet
  void ProcessPacket(const CellularRatioPacket& packet);
  
  // Socket path
  static constexpr const char* kSocketPath = "/tmp/webrtc_cellular_ratio.sock";
  
  // Dependencies (not owned)
  TaskQueueBase* const task_queue_;
  DelayBasedBwe* const delay_based_bwe_;

  // Callback for immediate pacer update
  RatioRateUpdateCallback on_rate_update_;

  // Socket file descriptor
  int socket_fd_ = -1;
  
  // Thread management
  std::atomic<bool> running_{false};
  std::unique_ptr<std::thread> receiver_thread_;
  
  // Statistics
  uint32_t packets_received_ = 0;
};

}  // namespace webrtc

#endif  // MODULES_CONGESTION_CONTROLLER_GOOG_CC_CELLULAR_RATIO_RECEIVER_H_

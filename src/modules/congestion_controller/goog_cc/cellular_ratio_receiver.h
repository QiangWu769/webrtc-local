/*
 *  Cellular Ratio Receiver for WebRTC
 *  Receives BSR ratio data via Unix domain socket
 */

#ifndef MODULES_CONGESTION_CONTROLLER_GOOG_CC_CELLULAR_RATIO_RECEIVER_H_
#define MODULES_CONGESTION_CONTROLLER_GOOG_CC_CELLULAR_RATIO_RECEIVER_H_

#include <atomic>
#include <memory>
#include <thread>

#include "api/task_queue/task_queue_base.h"
#include "api/units/timestamp.h"

namespace webrtc {

// Forward declarations
class DelayBasedBwe;

// Data packet format (must match sender)
struct CellularRatioPacket {
  uint64_t timestamp_ms;    // 8 bytes
  double ratio;             // 8 bytes  
  uint32_t sequence_number; // 4 bytes
} __attribute__((packed));  // Total: 20 bytes

class CellularRatioReceiver {
 public:
  // Constructor
  // task_queue: The WebRTC task queue for thread-safe callbacks
  // delay_based_bwe: The BWE instance to update with ratio data
  CellularRatioReceiver(TaskQueueBase* task_queue,
                       DelayBasedBwe* delay_based_bwe);
  
  // Destructor - automatically stops the receiver
  ~CellularRatioReceiver();
  
  // Start the receiver thread
  // Returns true on success, false on failure
  bool Start();
  
  // Stop the receiver thread
  void Stop();
  
  // Check if receiver is running
  bool IsRunning() const { return running_; }
  
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
  
  // Socket file descriptor
  int socket_fd_ = -1;
  
  // Thread management
  std::atomic<bool> running_{false};
  std::unique_ptr<std::thread> receiver_thread_;
  
  // Statistics
  uint32_t packets_received_ = 0;
  uint32_t last_sequence_ = 0;
};

}  // namespace webrtc

#endif  // MODULES_CONGESTION_CONTROLLER_GOOG_CC_CELLULAR_RATIO_RECEIVER_H_
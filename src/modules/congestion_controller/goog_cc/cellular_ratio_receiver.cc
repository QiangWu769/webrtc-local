/*
 *  Cellular Ratio Receiver Implementation
 */

#include "modules/congestion_controller/goog_cc/cellular_ratio_receiver.h"

#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <cstring>
#include <errno.h>

#include "modules/congestion_controller/goog_cc/delay_based_bwe.h"
#include "rtc_base/logging.h"
#include "rtc_base/checks.h"

namespace webrtc {

CellularRatioReceiver::CellularRatioReceiver(
    TaskQueueBase* task_queue,
    DelayBasedBwe* delay_based_bwe)
    : task_queue_(task_queue),
      delay_based_bwe_(delay_based_bwe) {
  RTC_DCHECK(task_queue_);
  RTC_DCHECK(delay_based_bwe_);
  RTC_LOG(LS_INFO) << "[CellularReceiver] Created";
}

CellularRatioReceiver::~CellularRatioReceiver() {
  RTC_LOG(LS_INFO) << "[CellularReceiver] Destroying...";
  Stop();
}

bool CellularRatioReceiver::Start() {
  if (running_.exchange(true)) {
    RTC_LOG(LS_WARNING) << "[CellularReceiver] Already running";
    return false;
  }
  
  // Start receiver thread
  receiver_thread_ = std::make_unique<std::thread>(
      [this] { ReceiverThreadLoop(); });
  
  RTC_LOG(LS_INFO) << "[CellularReceiver] Started successfully";
  return true;
}

void CellularRatioReceiver::Stop() {
  if (!running_.exchange(false)) {
    return;  // Already stopped
  }
  
  RTC_LOG(LS_INFO) << "[CellularReceiver] Stopping...";
  
  // Close socket to unblock recvfrom()
  if (socket_fd_ >= 0) {
    shutdown(socket_fd_, SHUT_RDWR);
  }
  
  // Wait for thread to finish
  if (receiver_thread_ && receiver_thread_->joinable()) {
    receiver_thread_->join();
  }
  
  CleanupSocket();
  
  RTC_LOG(LS_INFO) << "[CellularReceiver] Stopped. Total packets received: " 
                   << packets_received_;
}

void CellularRatioReceiver::ReceiverThreadLoop() {
  RTC_LOG(LS_INFO) << "[CellularReceiver] Thread started";
  
  if (!SetupSocket()) {
    RTC_LOG(LS_ERROR) << "[CellularReceiver] Failed to setup socket";
    running_ = false;
    return;
  }
  
  // Receive buffer
  uint8_t buffer[sizeof(CellularRatioPacket)];
  
  while (running_) {
    // Blocking receive
    ssize_t bytes_received = recvfrom(socket_fd_, buffer, sizeof(buffer),
                                      0, nullptr, nullptr);
    
    if (bytes_received < 0) {
      if (errno == EINTR) {
        continue;  // Interrupted, retry
      }
      if (running_) {  // Only log if we're still supposed to be running
        RTC_LOG(LS_ERROR) << "[CellularReceiver] recvfrom error: " 
                         << strerror(errno);
      }
      break;
    }
    
    if (bytes_received == sizeof(CellularRatioPacket)) {
      const auto* packet = reinterpret_cast<const CellularRatioPacket*>(buffer);
      ProcessPacket(*packet);
    } else {
      RTC_LOG(LS_WARNING) << "[CellularReceiver] Invalid packet size: " 
                          << bytes_received << " (expected " 
                          << sizeof(CellularRatioPacket) << ")";
    }
  }
  
  CleanupSocket();
  RTC_LOG(LS_INFO) << "[CellularReceiver] Thread stopped";
}

bool CellularRatioReceiver::SetupSocket() {
  // Create Unix domain datagram socket
  socket_fd_ = socket(AF_UNIX, SOCK_DGRAM, 0);
  if (socket_fd_ < 0) {
    RTC_LOG(LS_ERROR) << "[CellularReceiver] socket() failed: " 
                     << strerror(errno);
    return false;
  }
  
  // Prepare socket address
  struct sockaddr_un addr;
  memset(&addr, 0, sizeof(addr));
  addr.sun_family = AF_UNIX;
  strncpy(addr.sun_path, kSocketPath, sizeof(addr.sun_path) - 1);
  
  // Remove any existing socket file
  unlink(kSocketPath);
  
  // Bind socket
  if (bind(socket_fd_, reinterpret_cast<struct sockaddr*>(&addr),
           sizeof(addr)) < 0) {
    RTC_LOG(LS_ERROR) << "[CellularReceiver] bind() failed: " 
                     << strerror(errno);
    close(socket_fd_);
    socket_fd_ = -1;
    return false;
  }
  
  RTC_LOG(LS_INFO) << "[CellularReceiver] Socket bound to: " << kSocketPath;
  return true;
}

void CellularRatioReceiver::CleanupSocket() {
  if (socket_fd_ >= 0) {
    close(socket_fd_);
    socket_fd_ = -1;
  }
  unlink(kSocketPath);
}

void CellularRatioReceiver::ProcessPacket(const CellularRatioPacket& packet) {
  packets_received_++;
  
  // Check for sequence number gaps (for debugging)
  if (packets_received_ > 1 && packet.sequence_number != last_sequence_ + 1) {
    RTC_LOG(LS_WARNING) << "[CellularReceiver] Sequence gap detected. "
                       << "Expected: " << (last_sequence_ + 1) 
                       << ", Got: " << packet.sequence_number;
  }
  last_sequence_ = packet.sequence_number;
  
  // Log every 10th packet to avoid spam
  if (packet.sequence_number % 10 == 0) {
    RTC_LOG(LS_INFO) << "[CellularReceiver] Packet received: "
                    << "seq=" << packet.sequence_number
                    << ", ratio=" << packet.ratio
                    << ", time=" << packet.timestamp_ms << "ms";
  }
  
  // Post task to WebRTC task queue for thread-safe processing
  if (task_queue_ && delay_based_bwe_) {
    // Capture values for lambda
    double ratio = packet.ratio;
    uint64_t timestamp_ms = packet.timestamp_ms;
    
    task_queue_->PostTask([this, ratio, timestamp_ms] {
      // This runs on the WebRTC network thread
      delay_based_bwe_->UpdateCellularResourceRatio(
          ratio, 
          Timestamp::Millis(timestamp_ms));
    });
  }
}

}  // namespace webrtc
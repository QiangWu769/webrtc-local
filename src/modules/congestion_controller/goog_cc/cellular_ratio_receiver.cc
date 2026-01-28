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
#include "rtc_base/time_utils.h"

namespace webrtc {

CellularRatioReceiver::CellularRatioReceiver(
    TaskQueueBase* task_queue,
    DelayBasedBwe* delay_based_bwe,
    RatioRateUpdateCallback on_rate_update)
    : task_queue_(task_queue),
      delay_based_bwe_(delay_based_bwe),
      on_rate_update_(std::move(on_rate_update)) {
  RTC_DCHECK(task_queue_);
  RTC_DCHECK(delay_based_bwe_);
  RTC_LOG(LS_INFO) << "[CellularReceiver] Created with pacer callback: "
                   << (on_rate_update_ ? "yes" : "no");
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

  if (task_queue_ && delay_based_bwe_) {
    double ratio = packet.ratio;
    double saturation = packet.saturation;
    int64_t recv_time_ms = TimeMillis();

    // Log packet arrival at receiver level
    RTC_LOG(LS_INFO) << "[CellularReceiver-Recv] PacketNum: " << packets_received_
                     << ", RecvTimeMs: " << recv_time_ms
                     << ", Ratio: " << ratio
                     << ", Saturation: " << saturation;

    task_queue_->PostTask([this, ratio, saturation, recv_time_ms] {
      Timestamp now = Timestamp::Millis(TimeMillis());
      int64_t queue_delay_ms = now.ms() - recv_time_ms;

      // Get rate before update
      DataRate rate_before = delay_based_bwe_->last_estimate();

      RTC_LOG(LS_INFO) << "[CellularReceiver-Process] QueueDelayMs: " << queue_delay_ms
                       << ", RateBefore: " << rate_before.bps() << " bps";

      // Update ratio (this may modify current_bitrate_ in AIMD)
      delay_based_bwe_->UpdateCellularResourceRatio(ratio, saturation, now);

      // Get rate after update
      DataRate rate_after = delay_based_bwe_->last_estimate();

      // If rate changed and callback is set, notify pacer immediately
      if (on_rate_update_ && rate_after != rate_before) {
        // Pacing rate is typically 2.5x the target rate (WebRTC default pacing factor)
        constexpr double kPacingFactor = 2.5;
        DataRate pacing_rate = rate_after * kPacingFactor;
        DataRate padding_rate = DataRate::Zero();  // No padding by default

        RTC_LOG(LS_INFO) << "[CellularReceiver] Immediate pacer update: "
                         << rate_before.bps() << " -> " << rate_after.bps()
                         << " bps, pacing_rate: " << pacing_rate.bps() << " bps";

        on_rate_update_(pacing_rate, padding_rate);
      }
    });
  }
}

}  // namespace webrtc

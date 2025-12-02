/*
 * Clock synchronization helper for WebRTC
 * Uses chrony to get accurate NTP offset
 */

#ifndef EXAMPLES_PEERCONNECTION_CLIENT_CLOCK_SYNC_HELPER_H_
#define EXAMPLES_PEERCONNECTION_CLIENT_CLOCK_SYNC_HELPER_H_

#include <cstdint>
#include <optional>
#include <string>

namespace webrtc {

struct ClockSyncInfo {
  double offset_ms;        // System time offset in milliseconds
  double dispersion_ms;    // Root dispersion in milliseconds
  bool valid;              // Whether the data is valid
};

class ClockSyncHelper {
 public:
  // Get current NTP offset from chronyc tracking
  static ClockSyncInfo GetLocalClockOffset();

  // Set the remote peer's clock offset (received via Data Channel)
  static void SetRemoteClockOffset(double offset_ms, double dispersion_ms);

  // Get the clock offset delta: local - remote (in milliseconds)
  // Positive means local clock is ahead of remote
  static std::optional<double> GetClockOffsetDelta();

  // Convert a timestamp from remote clock to local clock
  static int64_t RemoteToLocalTime(int64_t remote_time_ms);

  // Convert a timestamp from local clock to remote clock
  static int64_t LocalToRemoteTime(int64_t local_time_ms);

  // Check if clock sync has been initialized
  static bool IsInitialized();

  // Reset synchronization (for testing)
  static void Reset();

 private:
  static double local_offset_ms_;
  static double local_dispersion_ms_;
  static double remote_offset_ms_;
  static double remote_dispersion_ms_;
  static bool initialized_;
};

}  // namespace webrtc

#endif  // EXAMPLES_PEERCONNECTION_CLIENT_CLOCK_SYNC_HELPER_H_

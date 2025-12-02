/*
 * Clock synchronization helper implementation
 */

#include "examples/peerconnection/client/clock_sync_helper.h"

#include <array>
#include <cstdio>
#include <memory>
#include <sstream>
#include <string>

#include "rtc_base/logging.h"

namespace webrtc {

// Static member initialization
double ClockSyncHelper::local_offset_ms_ = 0.0;
double ClockSyncHelper::local_dispersion_ms_ = 0.0;
double ClockSyncHelper::remote_offset_ms_ = 0.0;
double ClockSyncHelper::remote_dispersion_ms_ = 0.0;
bool ClockSyncHelper::initialized_ = false;

ClockSyncInfo ClockSyncHelper::GetLocalClockOffset() {
  ClockSyncInfo info{0.0, 0.0, false};

  // Use chronyc tracking to get system time offset from NTP
  std::array<char, 512> buffer;
  std::unique_ptr<FILE, decltype(&pclose)> pipe(
      popen("chronyc tracking 2>/dev/null", "r"), pclose);

  if (!pipe) {
    RTC_LOG(LS_WARNING) << "[CLOCK-SYNC] Failed to execute chronyc tracking";
    return info;
  }

  // Parse chronyc tracking output
  // Looking for lines like:
  // "System time     : 0.000875643 seconds fast of NTP time"
  // "System time     : 0.000023232 seconds slow of NTP time"
  // "Root dispersion : 0.000694731 seconds"
  double offset_seconds = 0.0;
  double dispersion_seconds = 0.0;
  bool found_offset = false;
  bool found_dispersion = false;

  while (fgets(buffer.data(), buffer.size(), pipe.get()) != nullptr) {
    std::string line(buffer.data());

    // Parse "System time" line
    if (line.find("System time") != std::string::npos) {
      double temp_offset = 0.0;
      // Check if "fast" or "slow"
      if (line.find("fast of NTP time") != std::string::npos) {
        if (sscanf(line.c_str(), "System time : %lf seconds fast", &temp_offset) == 1) {
          offset_seconds = temp_offset;  // Positive = fast
          found_offset = true;
        }
      } else if (line.find("slow of NTP time") != std::string::npos) {
        if (sscanf(line.c_str(), "System time : %lf seconds slow", &temp_offset) == 1) {
          offset_seconds = -temp_offset;  // Negative = slow
          found_offset = true;
        }
      }
    }

    // Parse "Root dispersion" line
    if (line.find("Root dispersion") != std::string::npos) {
      if (sscanf(line.c_str(), "Root dispersion : %lf seconds", &dispersion_seconds) == 1) {
        found_dispersion = true;
      }
    }
  }

  if (found_offset && found_dispersion) {
    info.offset_ms = offset_seconds * 1000.0;
    info.dispersion_ms = dispersion_seconds * 1000.0;
    info.valid = true;

    // Store local values
    local_offset_ms_ = info.offset_ms;
    local_dispersion_ms_ = info.dispersion_ms;

    RTC_LOG(LS_WARNING) << "[CLOCK-SYNC] chronyc tracking - System time offset: "
                        << info.offset_ms << "ms, root dispersion: "
                        << info.dispersion_ms << "ms";
  } else {
    RTC_LOG(LS_WARNING) << "[CLOCK-SYNC] Failed to parse chronyc tracking output";
  }

  return info;
}

void ClockSyncHelper::SetRemoteClockOffset(double offset_ms,
                                           double dispersion_ms) {
  remote_offset_ms_ = offset_ms;
  remote_dispersion_ms_ = dispersion_ms;
  initialized_ = true;

  double delta = local_offset_ms_ - remote_offset_ms_;
  double error_bound = local_dispersion_ms_ + remote_dispersion_ms_;

  RTC_LOG(LS_WARNING) << "[CLOCK-SYNC] Clock offset initialized: "
                      << "Δ=" << delta << "ms "
                      << "(local=" << local_offset_ms_ << "ms, "
                      << "remote=" << remote_offset_ms_ << "ms), "
                      << "error_bound=±" << error_bound << "ms";
}

std::optional<double> ClockSyncHelper::GetClockOffsetDelta() {
  if (!initialized_) {
    return std::nullopt;
  }
  return local_offset_ms_ - remote_offset_ms_;
}

int64_t ClockSyncHelper::RemoteToLocalTime(int64_t remote_time_ms) {
  if (!initialized_) {
    return remote_time_ms;
  }

  double delta = local_offset_ms_ - remote_offset_ms_;
  return remote_time_ms - static_cast<int64_t>(delta);
}

int64_t ClockSyncHelper::LocalToRemoteTime(int64_t local_time_ms) {
  if (!initialized_) {
    return local_time_ms;
  }

  double delta = local_offset_ms_ - remote_offset_ms_;
  return local_time_ms + static_cast<int64_t>(delta);
}

bool ClockSyncHelper::IsInitialized() {
  return initialized_;
}

void ClockSyncHelper::Reset() {
  local_offset_ms_ = 0.0;
  local_dispersion_ms_ = 0.0;
  remote_offset_ms_ = 0.0;
  remote_dispersion_ms_ = 0.0;
  initialized_ = false;
}

}  // namespace webrtc

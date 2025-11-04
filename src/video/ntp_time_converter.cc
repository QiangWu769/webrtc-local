/*
 *  Copyright (c) 2024 The WebRTC project authors. All Rights Reserved.
 *
 *  Use of this source code is governed by a BSD-style license
 *  that can be found in the LICENSE file in the root of the source
 *  tree. An additional intellectual property rights grant can be found
 *  in the file PATENTS.  All contributing project authors may
 *  be found in the AUTHORS file in the root of the source tree.
 */

#include "video/ntp_time_converter.h"

#include <chrono>

#include "rtc_base/logging.h"
#include "rtc_base/time_utils.h"

namespace webrtc {

void NtpTimeConverter::Initialize() {
  // Get current system time (Unix epoch) and steady clock
  auto system_us = std::chrono::duration_cast<std::chrono::microseconds>(
      std::chrono::system_clock::now().time_since_epoch()).count();
  auto steady_us = std::chrono::duration_cast<std::chrono::microseconds>(
      std::chrono::steady_clock::now().time_since_epoch()).count();

  // Calculate offset: (system_clock_unix_us + 2208988800s) - steady_clock_us
  // Where 2208988800s is NTP(1900) vs Unix(1970) epoch difference
  ntp_offset_us_ = (system_us + kNtpUnixEpochDiffUs) - steady_us;

  initialized_.store(true);

  RTC_LOG(LS_INFO) << "[C2R-INIT] NtpOffsetUs=" << ntp_offset_us_;
}

int64_t NtpTimeConverter::MonotonicToNtpMicros(int64_t monotonic_us) const {
  if (!initialized_.load()) {
    RTC_LOG(LS_ERROR) << "[C2R-ERROR] NtpTimeConverter not initialized";
    return 0;
  }
  return monotonic_us + ntp_offset_us_;
}

uint64_t NtpTimeConverter::NtpMicrosTo64Bit(int64_t ntp_us) const {
  // Convert NTP microseconds to standard NTP 64-bit format
  uint32_t sec = static_cast<uint32_t>(ntp_us / 1000000);
  uint64_t frac_us = ntp_us % 1000000;
  uint32_t frac = static_cast<uint32_t>((frac_us << 32) / 1000000);
  return (static_cast<uint64_t>(sec) << 32) | frac;
}

}  // namespace webrtc
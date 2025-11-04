/*
 *  Copyright (c) 2024 The WebRTC project authors. All Rights Reserved.
 *
 *  Use of this source code is governed by a BSD-style license
 *  that can be found in the LICENSE file in the root of the source
 *  tree. An additional intellectual property rights grant can be found
 *  in the file PATENTS.  All contributing project authors may
 *  be found in the AUTHORS file in the root of the source tree.
 */

#ifndef VIDEO_NTP_TIME_CONVERTER_H_
#define VIDEO_NTP_TIME_CONVERTER_H_

#include <atomic>
#include <chrono>
#include <cstdint>

namespace webrtc {

// C2R (Capture to Render) time converter for accurate NTP domain conversion
class NtpTimeConverter {
 public:
  NtpTimeConverter() = default;
  ~NtpTimeConverter() = default;

  // Initialize the converter. Must be called before any conversion.
  void Initialize();

  // Convert monotonic time (rtc::TimeMicros()) to NTP domain microseconds
  int64_t MonotonicToNtpMicros(int64_t monotonic_us) const;

  // Convert NTP microseconds to standard 64-bit NTP format (sec + fractions)
  uint64_t NtpMicrosTo64Bit(int64_t ntp_us) const;

  // Check if the converter is initialized
  bool IsInitialized() const { return initialized_.load(); }

 private:
  // NTP epoch (1900) vs Unix epoch (1970) difference: 70 years in microseconds
  static constexpr int64_t kNtpUnixEpochDiffUs = 2208988800LL * 1000000;

  std::atomic<bool> initialized_{false};
  int64_t ntp_offset_us_ = 0;  // Computed once at initialization
};

}  // namespace webrtc

#endif  // VIDEO_NTP_TIME_CONVERTER_H_
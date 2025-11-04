# WebRTC接收端NTP时间统一集成指南

## 问题分析
当前接收端使用单调时间记录C2R测量点，而发送端使用NTP时间域。这导致125年的巨大时钟偏移，需要统一时间域来获得准确的端到端延迟。

## 解决方案：接收端集成NtpTimeConverter

### 第一步：复制NtpTimeConverter文件

**1. 创建 `src/video/ntp_time_converter.h`**
```cpp
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
```

**2. 创建 `src/video/ntp_time_converter.cc`**
```cpp
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
```

### 第二步：修改BUILD.gn文件

在接收端的 `src/video/BUILD.gn` 中添加:
```gn
# 在 rtc_static_library("video") 的 sources 部分添加:
sources = [
  # ... 其他文件 ...
  "ntp_time_converter.cc",
  "ntp_time_converter.h",
]
```

### 第三步：修改接收端C2R相关文件

**1. 修改 `rtp_video_stream_receiver2.cc` (或对应的接收文件)**

在类声明中添加NTP转换器:
```cpp
#include "video/ntp_time_converter.h"

class RtpVideoStreamReceiver2 {
 private:
  // C2R相关成员
  NtpTimeConverter ntp_converter_;
  // ... 其他成员
};
```

在构造函数或初始化函数中:
```cpp
void RtpVideoStreamReceiver2::Initialize() {
  // 初始化NTP转换器
  ntp_converter_.Initialize();

  // ... 其他初始化代码
}
```

修改C2R日志记录:
```cpp
// 原来的代码 (只记录单调时间):
// RTC_LOG(LS_INFO) << "[C2R-ACT-RX] RtpTs=" << rtp_timestamp
//                  << ", RxUs=" << mono_us;

// 修改为 (同时记录单调时间和NTP时间):
int64_t mono_us = rtc::TimeMicros();
int64_t ntp_us = ntp_converter_.MonotonicToNtpMicros(mono_us);

RTC_LOG(LS_INFO) << "[C2R-ACT-RX] RtpTs=" << rtp_timestamp
                 << ", Ssrc=" << ssrc
                 << ", SeqNum=" << sequence_number
                 << ", RxUs=" << mono_us
                 << ", RxNtpUs=" << ntp_us
                 << ", ActCaptureUs=" << act_capture_us
                 << ", RelativeDelayUs=" << (ntp_us - act_capture_us);
```

**2. 修改 `video_stream_decoder2.cc` (或对应的解码文件)**

同样添加NTP转换器并修改日志:
```cpp
#include "video/ntp_time_converter.h"

// 在解码完成时记录NTP时间
void VideoStreamDecoder2::OnDecodedFrame() {
  int64_t mono_us = rtc::TimeMicros();
  int64_t ntp_us = ntp_converter_.MonotonicToNtpMicros(mono_us);

  RTC_LOG(LS_INFO) << "[C2R-DECODE] MonoUs=" << mono_us
                   << ", NtpUs=" << ntp_us
                   << ", FrameId=" << frame_id
                   << ", RtpTs=" << rtp_timestamp;

  RTC_LOG(LS_INFO) << "[C2R-E2E-DECODED] RtpTs=" << rtp_timestamp
                   << ", DelayMs=" << ((ntp_us - capture_ntp_us) / 1000.0)
                   << ", CaptureUs=" << capture_ntp_us
                   << ", DECODEDUs=" << ntp_us;
}
```

### 第四步：验证修改效果

修改后的接收端日志应该显示:
```
[C2R-ACT-RX] RtpTs=3405912258, RxNtpUs=3970678719123456, RelativeDelayUs=445457
[C2R-E2E-DECODED] DelayMs=123.45, CaptureUs=3970678718677999, DECODEDUs=3970678718801454
```

时钟偏移应该从125年降低到毫秒级别。

### 第五步：重新计算E2E延迟

使用统一的NTP时间域后，E2E延迟计算变为:
```python
# 网络延迟 = 接收NTP时间 - 发送捕获NTP时间
network_delay_ms = (receiver_ntp_us - sender_capture_ntp_us) / 1000

# 解码延迟 = 解码完成NTP时间 - 接收NTP时间
decode_delay_ms = (decoded_ntp_us - received_ntp_us) / 1000

# 总E2E延迟 = 解码完成NTP时间 - 发送捕获NTP时间
total_e2e_delay_ms = (decoded_ntp_us - sender_capture_ntp_us) / 1000
```

## 关键注意事项

1. **初始化顺序**: 确保在任何C2R测量之前调用 `ntp_converter_.Initialize()`
2. **线程安全**: NtpTimeConverter是线程安全的，可以在多线程环境中使用
3. **向后兼容**: 继续记录单调时间以保持兼容性，同时添加NTP时间
4. **错误处理**: 检查 `ntp_converter_.IsInitialized()` 状态

完成这些修改后，两端将使用统一的NTP时间域，E2E延迟测量将更加精确。
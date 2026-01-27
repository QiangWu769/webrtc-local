/*
 *  Copyright (c) 2017 The WebRTC project authors. All Rights Reserved.
 *
 *  Use of this source code is governed by a BSD-style license
 *  that can be found in the LICENSE file in the root of the source
 *  tree. An additional intellectual property rights grant can be found
 *  in the file PATENTS.  All contributing project authors may
 *  be found in the AUTHORS file in the root of the source tree.
 */

#include "test/test_video_capturer.h"

#include <optional>
#include <utility>

#include "api/scoped_refptr.h"
#include "api/video/i420_buffer.h"
#include "api/video/video_frame.h"
#include "api/video/video_frame_buffer.h"
#include "api/video/video_rotation.h"
#include "api/video/video_sink_interface.h"
#include "api/video/video_source_interface.h"
#include "rtc_base/logging.h"
#include "rtc_base/synchronization/mutex.h"
#include "rtc_base/time_utils.h"

namespace webrtc {
namespace test {

TestVideoCapturer::~TestVideoCapturer() = default;

void TestVideoCapturer::OnOutputFormatRequest(
    int width,
    int height,
    const std::optional<int>& max_fps) {
  std::optional<std::pair<int, int>> target_aspect_ratio =
      std::make_pair(width, height);
  std::optional<int> max_pixel_count = width * height;
  video_adapter_.OnOutputFormatRequest(target_aspect_ratio, max_pixel_count,
                                       max_fps);
}

void TestVideoCapturer::OnFrame(const VideoFrame& original_frame) {
  int cropped_width = 0;
  int cropped_height = 0;
  int out_width = 0;
  int out_height = 0;

  VideoFrame frame = MaybePreprocess(original_frame);

  // Log OnFrame timing for jitter analysis
  static int64_t last_onframe_time_us = 0;
  int64_t onframe_mono_us = TimeMicros();
  int64_t onframe_interval_us = (last_onframe_time_us > 0) ? (onframe_mono_us - last_onframe_time_us) : 0;
  int64_t frame_timestamp_us = frame.timestamp_us();
  last_onframe_time_us = onframe_mono_us;

  bool enable_adaptation;
  {
    MutexLock lock(&lock_);
    enable_adaptation = enable_adaptation_;
  }
  if (!enable_adaptation) {
    RTC_LOG(LS_INFO) << "[FRAME-ONFRAME] timestamp_us=" << frame_timestamp_us
                     << " onframe_mono_us=" << onframe_mono_us
                     << " interval_ms=" << (onframe_interval_us / 1000.0)
                     << " result=PASS(no_adapt)";
    broadcaster_.OnFrame(frame);
    return;
  }

  if (!video_adapter_.AdaptFrameResolution(
          frame.width(), frame.height(), frame.timestamp_us() * 1000,
          &cropped_width, &cropped_height, &out_width, &out_height)) {
    // Drop frame in order to respect frame rate constraint.
    RTC_LOG(LS_INFO) << "[FRAME-ONFRAME] timestamp_us=" << frame_timestamp_us
                     << " onframe_mono_us=" << onframe_mono_us
                     << " interval_ms=" << (onframe_interval_us / 1000.0)
                     << " result=DROP(fps_constraint)";
    return;
  }

  RTC_LOG(LS_INFO) << "[FRAME-ONFRAME] timestamp_us=" << frame_timestamp_us
                   << " onframe_mono_us=" << onframe_mono_us
                   << " interval_ms=" << (onframe_interval_us / 1000.0)
                   << " result=PASS";

  if (out_height != frame.height() || out_width != frame.width()) {
    // Video adapter has requested a down-scale. Allocate a new buffer and
    // return scaled version.
    // For simplicity, only scale here without cropping.
    scoped_refptr<I420Buffer> scaled_buffer =
        I420Buffer::Create(out_width, out_height);
    scaled_buffer->ScaleFrom(*frame.video_frame_buffer()->ToI420());
    VideoFrame::Builder new_frame_builder =
        VideoFrame::Builder()
            .set_video_frame_buffer(scaled_buffer)
            .set_rotation(kVideoRotation_0)
            .set_timestamp_us(frame.timestamp_us())
            .set_ntp_time_ms(frame.ntp_time_ms())
            .set_id(frame.id());
    if (frame.has_update_rect()) {
      VideoFrame::UpdateRect new_rect = frame.update_rect().ScaleWithFrame(
          frame.width(), frame.height(), 0, 0, frame.width(), frame.height(),
          out_width, out_height);
      new_frame_builder.set_update_rect(new_rect);
    }
    broadcaster_.OnFrame(new_frame_builder.build());

  } else {
    // No adaptations needed, just return the frame as is.
    broadcaster_.OnFrame(frame);
  }
}

VideoSinkWants TestVideoCapturer::GetSinkWants() {
  return broadcaster_.wants();
}

void TestVideoCapturer::AddOrUpdateSink(VideoSinkInterface<VideoFrame>* sink,
                                        const VideoSinkWants& wants) {
  broadcaster_.AddOrUpdateSink(sink, wants);
  UpdateVideoAdapter();
}

void TestVideoCapturer::RemoveSink(VideoSinkInterface<VideoFrame>* sink) {
  broadcaster_.RemoveSink(sink);
  UpdateVideoAdapter();
}

void TestVideoCapturer::UpdateVideoAdapter() {
  video_adapter_.OnSinkWants(broadcaster_.wants());
}

VideoFrame TestVideoCapturer::MaybePreprocess(const VideoFrame& frame) {
  MutexLock lock(&lock_);
  if (preprocessor_ != nullptr) {
    return preprocessor_->Preprocess(frame);
  } else {
    return frame;
  }
}

}  // namespace test
}  // namespace webrtc

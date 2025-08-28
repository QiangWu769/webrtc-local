/*
 *  Copyright 2024 The WebRTC Project Authors. All rights reserved.
 *
 *  Use of this source code is governed by a BSD-style license
 *  that can be found in the LICENSE file in the root of the source
 *  tree. An additional intellectual property rights grant can be found
 *  in the file PATENTS.  All contributing project authors may
 *  be found in the AUTHORS file in the root of the source tree.
 */

#ifndef EXAMPLES_PEERCONNECTION_CLIENT_VIDEO_FRAME_WRITER_H_
#define EXAMPLES_PEERCONNECTION_CLIENT_VIDEO_FRAME_WRITER_H_

#include <memory>
#include <string>

#include "api/video/video_frame.h"
#include "api/video/video_sink_interface.h"
#include "test/testsupport/video_frame_writer.h"

// A video sink that writes received video frames to a Y4M file (consistent with AlphaRTC).
class VideoFrameWriter : public webrtc::VideoSinkInterface<webrtc::VideoFrame> {
 public:
  static std::unique_ptr<VideoFrameWriter> Create(
      const std::string& output_file_path,
      int output_width,
      int output_height,
      int output_fps);

  ~VideoFrameWriter() override;

  // VideoSinkInterface implementation.
  void OnFrame(const webrtc::VideoFrame& frame) override;

 private:
  VideoFrameWriter(const std::string& output_file_path,
                   int output_width,
                   int output_height,
                   int output_fps);

  bool Initialize();

  // Professional Y4M writer (consistent with AlphaRTC)
  std::unique_ptr<webrtc::test::VideoFrameWriter> y4m_writer_;
  
  const std::string output_file_path_;
  const int output_width_;
  const int output_height_;
  const int output_fps_;
  bool initialized_;
};

#endif  // EXAMPLES_PEERCONNECTION_CLIENT_VIDEO_FRAME_WRITER_H_
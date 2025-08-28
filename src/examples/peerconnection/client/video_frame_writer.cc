/*
 *  Copyright 2024 The WebRTC Project Authors. All rights reserved.
 *
 *  Use of this source code is governed by a BSD-style license
 *  that can be found in the LICENSE file in the root of the source
 *  tree. An additional intellectual property rights grant can be found
 *  in the file PATENTS.  All contributing project authors may
 *  be found in the AUTHORS file in the root of the source tree.
 */

#include "examples/peerconnection/client/video_frame_writer.h"

#include <memory>

#include "api/video/i420_buffer.h"
#include "rtc_base/logging.h"
#include "absl/memory/memory.h"

// static
std::unique_ptr<VideoFrameWriter> VideoFrameWriter::Create(
    const std::string& output_file_path,
    int output_width,
    int output_height,
    int output_fps) {
  auto writer = std::unique_ptr<VideoFrameWriter>(
      new VideoFrameWriter(output_file_path, output_width, output_height, output_fps));
  if (!writer->Initialize()) {
    RTC_LOG(LS_ERROR) << "Failed to initialize VideoFrameWriter";
    return nullptr;
  }
  return writer;
}

VideoFrameWriter::VideoFrameWriter(const std::string& output_file_path,
                                   int output_width,
                                   int output_height,
                                   int output_fps)
    : output_file_path_(output_file_path),
      output_width_(output_width),
      output_height_(output_height),
      output_fps_(output_fps),
      initialized_(false) {}

VideoFrameWriter::~VideoFrameWriter() {
  if (y4m_writer_) {
    y4m_writer_->Close();
  }
}

bool VideoFrameWriter::Initialize() {
  // Create professional Y4M writer (consistent with AlphaRTC)
  // Use the configurable output_fps parameter
  y4m_writer_ = absl::make_unique<webrtc::test::Y4mVideoFrameWriterImpl>(
      output_file_path_, output_width_, output_height_, output_fps_);
  
  if (!y4m_writer_) {
    RTC_LOG(LS_ERROR) << "Failed to create Y4M video writer for: " << output_file_path_;
    return false;
  }
  
  initialized_ = true;
  RTC_LOG(LS_INFO) << "VideoFrameWriter initialized with Y4M format. Output file: " 
                   << output_file_path_ << " (" << output_width_ << "x" 
                   << output_height_ << " @ " << output_fps_ << "fps)";
  return true;
}

void VideoFrameWriter::OnFrame(const webrtc::VideoFrame& frame) {
  if (!initialized_ || !y4m_writer_) {
    return;
  }
  
  // Use professional Y4M writer (consistent with AlphaRTC)
  if (!y4m_writer_->WriteFrame(frame)) {
    RTC_LOG(LS_ERROR) << "Failed to write frame to Y4M file";
  }
}

// WriteFrameToFile method removed - now using professional Y4M writer
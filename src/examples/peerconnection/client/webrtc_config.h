/*
 *  Copyright 2024 The WebRTC Project Authors. All rights reserved.
 *
 *  Use of this source code is governed by a BSD-style license
 *  that can be found in the LICENSE file in the root of the source
 *  tree. An additional intellectual property rights grant can be found
 *  in the file PATENTS.  All contributing project authors may
 *  be found in the AUTHORS file in the root of the source tree.
 */

#ifndef EXAMPLES_PEERCONNECTION_CLIENT_WEBRTC_CONFIG_H_
#define EXAMPLES_PEERCONNECTION_CLIENT_WEBRTC_CONFIG_H_

#include <string>

// WebRTC Client configuration class
class WebRTCConfig {
 public:
  enum VideoSourceOption {
    kCamera,     // Use camera as video source
    kVideoFile,  // Use video file as video source
    kVideoDisabled  // Disable video
  };

  enum LogLevel {
    kLogVerbose,
    kLogInfo,
    kLogWarning,
    kLogError
  };

  WebRTCConfig();
  ~WebRTCConfig() = default;

  // Parse configuration from JSON file
  bool ParseFromFile(const std::string& config_file_path);

  // Getters
  VideoSourceOption video_source_option() const { return video_source_option_; }
  const std::string& video_file_path() const { return video_file_path_; }
  int video_width() const { return video_width_; }
  int video_height() const { return video_height_; }
  int video_fps() const { return video_fps_; }
  
  bool save_to_file() const { return save_to_file_; }
  const std::string& video_output_path() const { return video_output_path_; }
  int video_output_width() const { return video_output_width_; }
  int video_output_height() const { return video_output_height_; }
  int video_output_fps() const { return video_output_fps_; }
  
  LogLevel log_level() const { return log_level_; }
  bool save_log_to_file() const { return save_log_to_file_; }
  const std::string& log_output_path() const { return log_output_path_; }
  
  bool auto_close_on_completion() const { return auto_close_on_completion_; }
  int transmission_time_seconds() const { return transmission_time_seconds_; }

  // Server configuration getters
  const std::string& server_host() const { return server_host_; }
  int server_port() const { return server_port_; }
  bool auto_connect() const { return auto_connect_; }
  bool auto_call() const { return auto_call_; }

  // Convert log level to WebRTC log severity
  std::string GetLogSeverityString() const;

  // Print current configuration
  void PrintConfig() const;

 private:
  // Video source configuration
  VideoSourceOption video_source_option_;
  std::string video_file_path_;
  int video_width_;
  int video_height_;
  int video_fps_;

  // Video output configuration
  bool save_to_file_;
  std::string video_output_path_;
  int video_output_width_;
  int video_output_height_;
  int video_output_fps_;

  // Logging configuration
  LogLevel log_level_;
  bool save_log_to_file_;
  std::string log_output_path_;

  // Auto close when video transmission completes
  bool auto_close_on_completion_;
  int transmission_time_seconds_;

  // Server connection configuration
  std::string server_host_;
  int server_port_;
  bool auto_connect_;
  bool auto_call_;
};

#endif  // EXAMPLES_PEERCONNECTION_CLIENT_WEBRTC_CONFIG_H_
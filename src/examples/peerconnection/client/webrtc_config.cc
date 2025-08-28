/*
 *  Copyright 2024 The WebRTC Project Authors. All rights reserved.
 *
 *  Use of this source code is governed by a BSD-style license
 *  that can be found in the LICENSE file in the root of the source
 *  tree. An additional intellectual property rights grant can be found
 *  in the file PATENTS.  All contributing project authors may
 *  be found in the AUTHORS file in the root of the source tree.
 */

#include "examples/peerconnection/client/webrtc_config.h"

#include <fstream>
#include <iostream>

#include "json/reader.h"
#include "json/value.h"
#include "rtc_base/logging.h"
#include "rtc_base/strings/json.h"

WebRTCConfig::WebRTCConfig()
    : video_source_option_(kCamera),
      video_file_path_(""),
      video_width_(640),
      video_height_(480),
      video_fps_(30),
      save_to_file_(false),
      video_output_path_(""),
      video_output_width_(640),
      video_output_height_(480), 
      video_output_fps_(30),
      log_level_(kLogInfo),
      save_log_to_file_(false),
      log_output_path_(""),
      auto_close_on_completion_(false),
      transmission_time_seconds_(30),  // Default 30 seconds
      server_host_("localhost"),
      server_port_(8888),
      auto_connect_(true),
      auto_call_(true) {
}

bool WebRTCConfig::ParseFromFile(const std::string& config_file_path) {
  std::ifstream config_file(config_file_path);
  if (!config_file.is_open()) {
    RTC_LOG(LS_ERROR) << "Failed to open config file: " << config_file_path;
    return false;
  }

  Json::Reader reader;
  Json::Value root;
  if (!reader.parse(config_file, root)) {
    RTC_LOG(LS_ERROR) << "Failed to parse JSON config file: " 
                      << reader.getFormattedErrorMessages();
    return false;
  }

  // Parse video source configuration
  if (root.isMember("video_source")) {
    Json::Value video_source = root["video_source"];
    
    if (video_source.isMember("camera") && 
        video_source["camera"].isMember("enabled") &&
        video_source["camera"]["enabled"].asBool()) {
      video_source_option_ = kCamera;
    } else if (video_source.isMember("video_file") &&
               video_source["video_file"].isMember("enabled") &&
               video_source["video_file"]["enabled"].asBool()) {
      video_source_option_ = kVideoFile;
      
      Json::Value video_file = video_source["video_file"];
      if (video_file.isMember("file_path")) {
        video_file_path_ = video_file["file_path"].asString();
      }
      if (video_file.isMember("width")) {
        video_width_ = video_file["width"].asInt();
      }
      if (video_file.isMember("height")) {
        video_height_ = video_file["height"].asInt();
      }
      if (video_file.isMember("fps")) {
        video_fps_ = video_file["fps"].asInt();
      }
    } else if (video_source.isMember("video_disabled") &&
               video_source["video_disabled"].isMember("enabled") &&
               video_source["video_disabled"]["enabled"].asBool()) {
      video_source_option_ = kVideoDisabled;
    }
  }

  // Parse video output configuration
  if (root.isMember("video_output")) {
    Json::Value video_output = root["video_output"];
    if (video_output.isMember("enabled")) {
      save_to_file_ = video_output["enabled"].asBool();
    }
    if (save_to_file_) {
      if (video_output.isMember("file_path")) {
        video_output_path_ = video_output["file_path"].asString();
      }
      if (video_output.isMember("width")) {
        video_output_width_ = video_output["width"].asInt();
      }
      if (video_output.isMember("height")) {
        video_output_height_ = video_output["height"].asInt();
      }
      if (video_output.isMember("fps")) {
        video_output_fps_ = video_output["fps"].asInt();
      }
    }
  }

  // Parse logging configuration
  if (root.isMember("logging")) {
    Json::Value logging = root["logging"];
    if (logging.isMember("level")) {
      std::string level_str = logging["level"].asString();
      if (level_str == "verbose") {
        log_level_ = kLogVerbose;
      } else if (level_str == "info") {
        log_level_ = kLogInfo;
      } else if (level_str == "warning") {
        log_level_ = kLogWarning;
      } else if (level_str == "error") {
        log_level_ = kLogError;
      }
    }
    
    if (logging.isMember("save_to_file")) {
      save_log_to_file_ = logging["save_to_file"].asBool();
    }
    
    if (logging.isMember("log_output_path")) {
      log_output_path_ = logging["log_output_path"].asString();
    }
  }

  // Parse auto close configuration
  if (root.isMember("auto_close_on_completion")) {
    auto_close_on_completion_ = root["auto_close_on_completion"].asBool();
  }
  
  // Parse transmission time configuration
  if (root.isMember("transmission_time_seconds")) {
    transmission_time_seconds_ = root["transmission_time_seconds"].asInt();
  }

  // Parse server connection configuration
  if (root.isMember("server")) {
    Json::Value server = root["server"];
    if (server.isMember("host")) {
      server_host_ = server["host"].asString();
    }
    if (server.isMember("port")) {
      server_port_ = server["port"].asInt();
    }
    if (server.isMember("auto_connect")) {
      auto_connect_ = server["auto_connect"].asBool();
    }
    if (server.isMember("auto_call")) {
      auto_call_ = server["auto_call"].asBool();
    }
  }

  return true;
}

std::string WebRTCConfig::GetLogSeverityString() const {
  switch (log_level_) {
    case kLogVerbose:
      return "verbose";
    case kLogInfo:
      return "info";
    case kLogWarning:
      return "warning";
    case kLogError:
      return "error";
    default:
      return "info";
  }
}

void WebRTCConfig::PrintConfig() const {
  RTC_LOG(LS_INFO) << "=== WebRTC Configuration ===";
  
  // Video source
  std::string video_source_str;
  switch (video_source_option_) {
    case kCamera:
      video_source_str = "Camera";
      break;
    case kVideoFile:
      video_source_str = "Video File";
      break;
    case kVideoDisabled:
      video_source_str = "Disabled";
      break;
  }
  RTC_LOG(LS_INFO) << "  Video Source: " << video_source_str;
  
  if (video_source_option_ == kVideoFile) {
    RTC_LOG(LS_INFO) << "  Video File: " << video_file_path_;
    RTC_LOG(LS_INFO) << "  Video Resolution: " << video_width_ << "x" << video_height_;
    RTC_LOG(LS_INFO) << "  Video FPS: " << video_fps_;
  }
  
  // Video output
  RTC_LOG(LS_INFO) << "  Save Video: " << (save_to_file_ ? "Yes" : "No");
  if (save_to_file_) {
    RTC_LOG(LS_INFO) << "  Output File: " << video_output_path_;
    RTC_LOG(LS_INFO) << "  Output Resolution: " << video_output_width_ << "x" << video_output_height_;
    RTC_LOG(LS_INFO) << "  Output FPS: " << video_output_fps_;
  }
  
  // Logging
  RTC_LOG(LS_INFO) << "  Log Level: " << GetLogSeverityString();
  RTC_LOG(LS_INFO) << "  Save Log: " << (save_log_to_file_ ? "Yes" : "No");
  if (save_log_to_file_) {
    RTC_LOG(LS_INFO) << "  Log File: " << log_output_path_;
  }
  
  // Auto close
  RTC_LOG(LS_INFO) << "  Auto Close: " << (auto_close_on_completion_ ? "Yes" : "No");
  RTC_LOG(LS_INFO) << "  Transmission Time: " << transmission_time_seconds_ << " seconds";
  
  // Server configuration
  RTC_LOG(LS_INFO) << "  Server Host: " << server_host_;
  RTC_LOG(LS_INFO) << "  Server Port: " << server_port_;
  RTC_LOG(LS_INFO) << "  Auto Connect: " << (auto_connect_ ? "Yes" : "No");
  RTC_LOG(LS_INFO) << "  Auto Call: " << (auto_call_ ? "Yes" : "No");
  
  RTC_LOG(LS_INFO) << "============================";
}
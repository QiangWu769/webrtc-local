/*
 *  Copyright 2012 The WebRTC Project Authors. All rights reserved.
 *
 *  Use of this source code is governed by a BSD-style license
 *  that can be found in the LICENSE file in the root of the source
 *  tree. An additional intellectual property rights grant can be found
 *  in the file PATENTS.  All contributing project authors may
 *  be found in the AUTHORS file in the root of the source tree.
 */

#ifndef EXAMPLES_PEERCONNECTION_CLIENT_FLAG_DEFS_H_
#define EXAMPLES_PEERCONNECTION_CLIENT_FLAG_DEFS_H_

#include <string>

#include "absl/flags/flag.h"

extern const uint16_t kDefaultServerPort;  // From defaults.[h|cc]

// Define flags for the peerconnect_client testing tool, in a separate
// header file so that they can be shared across the different main.cc's
// for each platform.

ABSL_FLAG(bool,
          autoconnect,
          false,
          "Connect to the server without user "
          "intervention.");
ABSL_FLAG(std::string, server, "localhost", "The server to connect to.");
ABSL_FLAG(int,
          port,
          kDefaultServerPort,
          "The port on which the server is listening.");
ABSL_FLAG(
    bool,
    autocall,
    false,
    "Call the first available other client on "
    "the server without user intervention.  Note: this flag should only be set "
    "to true on one of the two clients.");

ABSL_FLAG(
    std::string,
    force_fieldtrials,
    "",
    "Field trials control experimental features. This flag specifies the field "
    "trials in effect. E.g. running with "
    "--force_fieldtrials=WebRTC-FooFeature/Enabled/ "
    "will assign the group Enabled to field trial WebRTC-FooFeature. Multiple "
    "trials are separated by \"/\"");

// Video source configuration flags
ABSL_FLAG(
    bool,
    use_video_file,
    false,
    "Use video file instead of camera as video source. When enabled, requires "
    "video_file_path to be specified.");

ABSL_FLAG(
    std::string,
    video_file_path,
    "",
    "Path to the YUV video file to use as input. Only used when use_video_file "
    "is true. Supports .yuv and .y4m formats.");

ABSL_FLAG(
    int,
    video_width,
    640,
    "Width of the video file in pixels. Required for .yuv files.");

ABSL_FLAG(
    int,
    video_height,
    480,
    "Height of the video file in pixels. Required for .yuv files.");

ABSL_FLAG(
    int,
    video_fps,
    30,
    "Frame rate of the video file in frames per second.");

// Configuration file support
ABSL_FLAG(
    std::string,
    config,
    "",
    "Path to JSON configuration file. When specified, this overrides "
    "command line video settings. The config file can specify video source, "
    "logging settings, output paths, etc.");

#endif  // EXAMPLES_PEERCONNECTION_CLIENT_FLAG_DEFS_H_

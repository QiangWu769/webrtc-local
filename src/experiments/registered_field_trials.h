/*
 *  Copyright 2024 The WebRTC Project Authors. All rights reserved.
 *
 *  Use of this source code is governed by a BSD-style license
 *  that can be found in the LICENSE file in the root of the source
 *  tree. An additional intellectual property rights grant can be found
 *  in the file PATENTS.  All contributing project authors may
 *  be found in the AUTHORS file in the root of the source tree.
 */

#ifndef EXPERIMENTS_REGISTERED_FIELD_TRIALS_H_
#define EXPERIMENTS_REGISTERED_FIELD_TRIALS_H_

#include <string>

#include "absl/strings/string_view.h"

namespace webrtc {

// List of all registered field trials in WebRTC.
// This list is used to validate field trial lookups when WEBRTC_STRICT_FIELD_TRIALS is enabled.
// Keep this list sorted.
inline constexpr absl::string_view kRegisteredFieldTrials[] = {
    // Add registered field trials here
    "WebRTC-Audio-BitrateAdaptation",
    "WebRTC-Audio-OpusSetBitrate",
    "WebRTC-Video-BalancedDegradation",
    "WebRTC-Video-QualityScaling",
};

// Registers all field trials for WebRTC.
// This function should be called before any WebRTC functions are used.
void RegisterFieldTrials();

// Gets the field trial state for a given trial name.
std::string GetFieldTrialState(const std::string& trial_name);

}  // namespace webrtc

#endif  // EXPERIMENTS_REGISTERED_FIELD_TRIALS_H_ 
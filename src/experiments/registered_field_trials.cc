/*
 *  Copyright 2024 The WebRTC Project Authors. All rights reserved.
 *
 *  Use of this source code is governed by a BSD-style license
 *  that can be found in the LICENSE file in the root of the source
 *  tree. An additional intellectual property rights grant can be found
 *  in the file PATENTS.  All contributing project authors may
 *  be found in the AUTHORS file in the root of the source tree.
 */

#include "experiments/registered_field_trials.h"

#include <map>
#include <string>

#include "rtc_base/logging.h"

namespace webrtc {

namespace {
// Global map to store field trial states
std::map<std::string, std::string> g_field_trial_states;
}  // namespace

void RegisterFieldTrials() {
  // Add any default field trials here
  RTC_LOG(LS_INFO) << "Registering WebRTC field trials";
}

std::string GetFieldTrialState(const std::string& trial_name) {
  auto it = g_field_trial_states.find(trial_name);
  if (it != g_field_trial_states.end()) {
    return it->second;
  }
  return std::string();
}

}  // namespace webrtc 
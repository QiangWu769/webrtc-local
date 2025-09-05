/*
 *  Copyright (c) 2014 The WebRTC project authors. All Rights Reserved.
 *
 *  Use of this source code is governed by a BSD-style license
 *  that can be found in the LICENSE file in the root of the source
 *  tree. An additional intellectual property rights grant can be found
 *  in the file PATENTS.  All contributing project authors may
 *  be found in the AUTHORS file in the root of the source tree.
 */

#include "modules/remote_bitrate_estimator/aimd_rate_control.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <iomanip>
#include <optional>
#include <sstream>
#include <string>

#include "api/field_trials_view.h"
#include "api/transport/bandwidth_usage.h"
#include "api/transport/network_types.h"
#include "api/units/data_rate.h"
#include "api/units/data_size.h"
#include "api/units/time_delta.h"
#include "api/units/timestamp.h"
#include "modules/remote_bitrate_estimator/include/bwe_defines.h"
#include "rtc_base/checks.h"
#include "rtc_base/experiments/field_trial_parser.h"
#include "rtc_base/logging.h"
#include "rtc_base/time_utils.h"

namespace webrtc {
namespace {

constexpr TimeDelta kDefaultRtt = TimeDelta::Millis(200);
constexpr double kDefaultBackoffFactor = 0.85;

constexpr char kBweBackOffFactorExperiment[] = "WebRTC-BweBackOffFactor";

double ReadBackoffFactor(const FieldTrialsView& key_value_config) {
  std::string experiment_string =
      key_value_config.Lookup(kBweBackOffFactorExperiment);
  double backoff_factor;
  int parsed_values =
      sscanf(experiment_string.c_str(), "Enabled-%lf", &backoff_factor);
  if (parsed_values == 1) {
    if (backoff_factor >= 1.0) {
      RTC_LOG(LS_WARNING) << "Back-off factor must be less than 1.";
    } else if (backoff_factor <= 0.0) {
      RTC_LOG(LS_WARNING) << "Back-off factor must be greater than 0.";
    } else {
      return backoff_factor;
    }
  }
  RTC_LOG(LS_WARNING) << "Failed to parse parameters for AimdRateControl "
                         "experiment from field trial string. Using default.";
  return kDefaultBackoffFactor;
}

// Helper function to get wall clock timestamp as a string with 6 decimal places
std::string GetWallClockTimestampString() {
  double unix_seconds = webrtc::TimeUTCMillis() / 1000.0;
  std::stringstream ss;
  ss << std::fixed << std::setprecision(6) << unix_seconds;
  return ss.str();
}

}  // namespace

AimdRateControl::AimdRateControl(const FieldTrialsView& key_value_config)
    : AimdRateControl(key_value_config, /* send_side =*/false) {}

AimdRateControl::AimdRateControl(const FieldTrialsView& key_value_config,
                                 bool send_side)
    : min_configured_bitrate_(kCongestionControllerMinBitrate),
      max_configured_bitrate_(DataRate::KilobitsPerSec(30000)),
      current_bitrate_(max_configured_bitrate_),
      latest_estimated_throughput_(current_bitrate_),
      link_capacity_(),
      rate_control_state_(RateControlState::kRcHold),
      time_last_bitrate_change_(Timestamp::MinusInfinity()),
      time_last_bitrate_decrease_(Timestamp::MinusInfinity()),
      time_first_throughput_estimate_(Timestamp::MinusInfinity()),
      bitrate_is_initialized_(false),
      beta_(key_value_config.IsEnabled(kBweBackOffFactorExperiment)
                ? ReadBackoffFactor(key_value_config)
                : kDefaultBackoffFactor),
      in_alr_(false),
      rtt_(kDefaultRtt),
      send_side_(send_side),
      no_bitrate_increase_in_alr_(
          key_value_config.IsEnabled("WebRTC-DontIncreaseDelayBasedBweInAlr")) {
  ParseFieldTrial(
      {&disable_estimate_bounded_increase_,
       &use_current_estimate_as_min_upper_bound_},
      key_value_config.Lookup("WebRTC-Bwe-EstimateBoundedIncrease"));
  RTC_LOG(LS_INFO) << "Using aimd rate control with back off factor " << beta_;
}

AimdRateControl::~AimdRateControl() {}

void AimdRateControl::SetStartBitrate(DataRate start_bitrate) {
  current_bitrate_ = start_bitrate;
  latest_estimated_throughput_ = current_bitrate_;
  bitrate_is_initialized_ = true;
}

void AimdRateControl::SetMinBitrate(DataRate min_bitrate) {
  min_configured_bitrate_ = min_bitrate;
  current_bitrate_ = std::max(min_bitrate, current_bitrate_);
}

bool AimdRateControl::ValidEstimate() const {
  return bitrate_is_initialized_;
}

TimeDelta AimdRateControl::GetFeedbackInterval() const {
  // Estimate how often we can send RTCP if we allocate up to 5% of bandwidth
  // to feedback.
  const DataSize kRtcpSize = DataSize::Bytes(80);
  const DataRate rtcp_bitrate = current_bitrate_ * 0.05;
  const TimeDelta interval = kRtcpSize / rtcp_bitrate;
  const TimeDelta kMinFeedbackInterval = TimeDelta::Millis(200);
  const TimeDelta kMaxFeedbackInterval = TimeDelta::Millis(1000);
  return interval.Clamped(kMinFeedbackInterval, kMaxFeedbackInterval);
}

bool AimdRateControl::TimeToReduceFurther(Timestamp at_time,
                                          DataRate estimated_throughput) const {
  const TimeDelta bitrate_reduction_interval =
      rtt_.Clamped(TimeDelta::Millis(10), TimeDelta::Millis(200));
  if (at_time - time_last_bitrate_change_ >= bitrate_reduction_interval) {
    return true;
  }
  if (ValidEstimate()) {
    // TODO(terelius/holmer): Investigate consequences of increasing
    // the threshold to 0.95 * LatestEstimate().
    const DataRate threshold = 0.5 * LatestEstimate();
    return estimated_throughput < threshold;
  }
  return false;
}

bool AimdRateControl::InitialTimeToReduceFurther(Timestamp at_time) const {
  return ValidEstimate() &&
         TimeToReduceFurther(at_time,
                             LatestEstimate() / 2 - DataRate::BitsPerSec(1));
}

DataRate AimdRateControl::LatestEstimate() const {
  return current_bitrate_;
}

void AimdRateControl::SetRtt(TimeDelta rtt) {
  rtt_ = rtt;
}

DataRate AimdRateControl::Update(const RateControlInput& input,
                                 Timestamp at_time) {
  // Set the initial bit rate value to what we're receiving the first half
  // second.
  // TODO(bugs.webrtc.org/9379): The comment above doesn't match to the code.
  if (!bitrate_is_initialized_) {
    const TimeDelta kInitializationTime = TimeDelta::Seconds(5);
    RTC_DCHECK_LE(kBitrateWindow, kInitializationTime);
    if (time_first_throughput_estimate_.IsInfinite()) {
      if (input.estimated_throughput)
        time_first_throughput_estimate_ = at_time;
    } else if (at_time - time_first_throughput_estimate_ >
                   kInitializationTime &&
               input.estimated_throughput) {
      current_bitrate_ = *input.estimated_throughput;
      bitrate_is_initialized_ = true;
    }
  }

  DataRate old_bitrate = current_bitrate_;
  RateControlState old_state = rate_control_state_;
  
  RTC_LOG(LS_INFO) << "[" << GetWallClockTimestampString() << "]"
                   << " [AIMD-Update] MonoTime: " << at_time.ms() 
                   << " ms, Input state: " << static_cast<int>(input.bw_state)
                   << ", Estimated throughput: " << (input.estimated_throughput ? input.estimated_throughput->bps() : -1)
                   << " bps, Current bitrate: " << current_bitrate_.bps()
                   << " bps, Link capacity estimate: " << (link_capacity_.has_estimate() ? "yes" : "no")
                   << ", In ALR: " << (in_alr_ ? "yes" : "no");

  ChangeBitrate(input, at_time);
  
  if (current_bitrate_ != old_bitrate || rate_control_state_ != old_state) {
    const char* state_str = "Unknown";
    switch (rate_control_state_) {
      case RateControlState::kRcHold: state_str = "Hold"; break;
      case RateControlState::kRcIncrease: state_str = "Increase"; break;
      case RateControlState::kRcDecrease: state_str = "Decrease"; break;
    }
    
    RTC_LOG(LS_INFO) << "[AIMD-Result] New state: " << state_str 
                     << ", Old bitrate: " << old_bitrate.bps()
                     << " bps, New bitrate: " << current_bitrate_.bps()
                     << " bps, Change: " << (current_bitrate_.bps() - old_bitrate.bps())
                     << " bps, Beta: " << beta_;
  }
  return current_bitrate_;
}

AimdRateControl::StrategyInfo AimdRateControl::GetLastStrategyInfo() const {
  return {last_strategy_name_, last_strategy_params_};
}

void AimdRateControl::SetInApplicationLimitedRegion(bool in_alr) {
  in_alr_ = in_alr;
}

void AimdRateControl::SetEstimate(DataRate bitrate, Timestamp at_time) {
  bitrate_is_initialized_ = true;
  DataRate prev_bitrate = current_bitrate_;
  current_bitrate_ = ClampBitrate(bitrate);
  time_last_bitrate_change_ = at_time;
  if (current_bitrate_ < prev_bitrate) {
    time_last_bitrate_decrease_ = at_time;
  }
}

void AimdRateControl::SetNetworkStateEstimate(
    const std::optional<NetworkStateEstimate>& estimate) {
  network_estimate_ = estimate;
}

double AimdRateControl::GetNearMaxIncreaseRateBpsPerSecond() const {
  RTC_DCHECK(!current_bitrate_.IsZero());
  const TimeDelta kFrameInterval = TimeDelta::Seconds(1) / 30;
  DataSize frame_size = current_bitrate_ * kFrameInterval;
  const DataSize kPacketSize = DataSize::Bytes(1200);
  double packets_per_frame = std::ceil(frame_size / kPacketSize);
  DataSize avg_packet_size = frame_size / packets_per_frame;

  // Approximate the over-use estimator delay to 100 ms.
  TimeDelta response_time = rtt_ + TimeDelta::Millis(100);

  response_time = response_time * 2;
  double increase_rate_bps_per_second =
      (avg_packet_size / response_time).bps<double>();
  double kMinIncreaseRateBpsPerSecond = 4000;
  return std::max(kMinIncreaseRateBpsPerSecond, increase_rate_bps_per_second);
}

TimeDelta AimdRateControl::GetExpectedBandwidthPeriod() const {
  const TimeDelta kMinPeriod = TimeDelta::Seconds(2);
  const TimeDelta kDefaultPeriod = TimeDelta::Seconds(3);
  const TimeDelta kMaxPeriod = TimeDelta::Seconds(50);

  double increase_rate_bps_per_second = GetNearMaxIncreaseRateBpsPerSecond();
  if (!last_decrease_)
    return kDefaultPeriod;
  double time_to_recover_decrease_seconds =
      last_decrease_->bps() / increase_rate_bps_per_second;
  TimeDelta period = TimeDelta::Seconds(time_to_recover_decrease_seconds);
  return period.Clamped(kMinPeriod, kMaxPeriod);
}

void AimdRateControl::ChangeBitrate(const RateControlInput& input,
                                    Timestamp at_time) {
  std::optional<DataRate> new_bitrate;
  DataRate estimated_throughput =
      input.estimated_throughput.value_or(latest_estimated_throughput_);
  if (input.estimated_throughput)
    latest_estimated_throughput_ = *input.estimated_throughput;

  // An over-use should always trigger us to reduce the bitrate, even though
  // we have not yet established our first estimate. By acting on the over-use,
  // we will end up with a valid estimate.
  if (!bitrate_is_initialized_ &&
      input.bw_state != BandwidthUsage::kBwOverusing)
    return;

  ChangeState(input, at_time);

  switch (rate_control_state_) {
    case RateControlState::kRcHold:
      RTC_LOG(LS_INFO) << "[AIMD-Hold] Holding bitrate at " << current_bitrate_.bps() << " bps";
      last_strategy_name_ = "Hold";
      last_strategy_params_ = "Bitrate=" + std::to_string(current_bitrate_.bps());
      break;

    case RateControlState::kRcIncrease: {
      if (estimated_throughput > link_capacity_.UpperBound())
        link_capacity_.Reset();

      // We limit the new bitrate based on the troughput to avoid unlimited
      // bitrate increases. We allow a bit more lag at very low rates to not too
      // easily get stuck if the encoder produces uneven outputs.
      DataRate increase_limit =
          1.5 * estimated_throughput + DataRate::KilobitsPerSec(10);
      if (send_side_ && in_alr_ && no_bitrate_increase_in_alr_) {
        // Do not increase the delay based estimate in alr since the estimator
        // will not be able to get transport feedback necessary to detect if
        // the new estimate is correct.
        // If we have previously increased above the limit (for instance due to
        // probing), we don't allow further changes.
        increase_limit = current_bitrate_;
      }

      RTC_LOG(LS_INFO) << "[AIMD-Increase] Increase limit: " << increase_limit.bps()
                       << " bps, Current: " << current_bitrate_.bps()
                       << " bps, Link capacity: " << (link_capacity_.has_estimate() ? "yes" : "no");

      if (current_bitrate_ < increase_limit) {
        DataRate increased_bitrate = DataRate::MinusInfinity();
        
        // Check cellular ratio strategies
        bool force_additive = false;
        bool force_multiplicative = false;
        
        if (HasFreshCellularData(at_time)) {
          if (ShouldForceMultiplicativeGrowth()) {
            // Fourth layer: force multiplicative growth when ratio consistently high
            force_multiplicative = true;
            link_capacity_.Reset();  // Reset to allow multiplicative growth
            RTC_LOG(LS_INFO) << "[AIMD-Cellular-L4] ✅ FORCING MULTIPLICATIVE GROWTH! " 
                             << "Ratio: " << smoothed_cellular_ratio_ 
                             << ", Consecutive count: " << consecutive_high_ratio_count_
                             << " - Link capacity reset to trigger multiplicative increase";
          } else if (ShouldLimitIncrease()) {
            force_additive = true;
            RTC_LOG(LS_INFO) << "[AIMD-Cellular-L3] Limiting to additive increase due to ratio: " 
                             << smoothed_cellular_ratio_;
          }
        }
        
        if ((link_capacity_.has_estimate() || force_additive) && !force_multiplicative) {
          // Use additive increase when:
          // 1. We have link capacity estimate (normal case), OR
          // 2. Cellular ratio suggests conservative increase
          // BUT NOT when cellular L4 forces multiplicative growth
          DataRate additive_increase =
              AdditiveRateIncrease(at_time, time_last_bitrate_change_);
          increased_bitrate = current_bitrate_ + additive_increase;
          
          double increase_rate_bps_per_sec = GetNearMaxIncreaseRateBpsPerSecond();
          int64_t time_delta_ms = (at_time - time_last_bitrate_change_).ms();
          
          RTC_LOG(LS_INFO) << "[AIMD-Additive] Base increase: " << additive_increase.bps()
                           << " bps, Near max rate: " << increase_rate_bps_per_sec
                           << " bps/s, Time delta: " << time_delta_ms
                           << " ms, Link capacity: " << (link_capacity_.has_estimate() ? 
                              std::to_string(link_capacity_.estimate().bps()) : "N/A") 
                           << (force_additive ? " (Cellular-forced)" : "");
          
          last_strategy_name_ = "Additive-Increase";
          if (force_additive) {
            last_strategy_params_ = "Rate=" + std::to_string(static_cast<int>(increase_rate_bps_per_sec)) + 
                                    "bps/s,Delta=" + std::to_string(time_delta_ms) + 
                                    "ms,Cellular-forced";
          } else {
            last_strategy_params_ = "Rate=" + std::to_string(static_cast<int>(increase_rate_bps_per_sec)) + 
                                    "bps/s,Delta=" + std::to_string(time_delta_ms) + 
                                    "ms,LinkCap=" + std::to_string(link_capacity_.estimate().bps()) + "bps";
          }
        } else {
          // If we don't have an estimate of the link capacity, use faster ramp
          // up to discover the capacity.
          DataRate multiplicative_increase = MultiplicativeRateIncrease(
              at_time, time_last_bitrate_change_, current_bitrate_);
          increased_bitrate = current_bitrate_ + multiplicative_increase;
          
          int64_t time_delta_ms = (at_time - time_last_bitrate_change_).ms();
          double alpha_factor = multiplicative_increase.bps() / std::max(current_bitrate_.bps(), static_cast<int64_t>(1)) + 1.0;
          
          RTC_LOG(LS_INFO) << "[AIMD-Multiplicative] Base increase: " << multiplicative_increase.bps()
                           << " bps, Alpha factor: " << alpha_factor
                           << ", Time delta: " << time_delta_ms << " ms"
                           << (force_multiplicative ? " (Cellular-L4-forced)" : "");
          
          last_strategy_name_ = "Multiplicative-Increase";
          if (force_multiplicative) {
            last_strategy_params_ = "Alpha=" + std::to_string(alpha_factor) + 
                                    ",Delta=" + std::to_string(time_delta_ms) + 
                                    "ms,Cellular-L4-forced";
          } else {
            last_strategy_params_ = "Alpha=" + std::to_string(alpha_factor) + 
                                    ",Delta=" + std::to_string(time_delta_ms) + "ms";
          }
        }
        new_bitrate = std::min(increased_bitrate, increase_limit);
        
        if (new_bitrate != increased_bitrate) {
          RTC_LOG(LS_INFO) << "[AIMD-Limited] Increase capped. Desired: " << increased_bitrate.bps()
                           << " bps, Limited to: " << new_bitrate->bps() << " bps";
        }
      } else {
        RTC_LOG(LS_INFO) << "[AIMD-NoIncrease] Current bitrate at or above limit";
      }
      time_last_bitrate_change_ = at_time;
      break;
    }

    case RateControlState::kRcDecrease: {
      DataRate decreased_bitrate = DataRate::PlusInfinity();

      // Set bit rate to something slightly lower than the measured throughput
      // to get rid of any self-induced delay.
      decreased_bitrate = estimated_throughput * beta_;
      if (decreased_bitrate > DataRate::KilobitsPerSec(5)) {
        decreased_bitrate -= DataRate::KilobitsPerSec(5);
      }

      RTC_LOG(LS_INFO) << "[AIMD-Decrease] Initial calc: " << decreased_bitrate.bps()
                       << " bps (throughput " << estimated_throughput.bps()
                       << " * beta " << beta_ << " - 5kbps), Current: " << current_bitrate_.bps() << " bps";

      if (decreased_bitrate > current_bitrate_) {
        // TODO(terelius): The link_capacity estimate may be based on old
        // throughput measurements. Relying on them may lead to unnecessary
        // BWE drops.
        if (link_capacity_.has_estimate()) {
          DataRate link_based_decrease = beta_ * link_capacity_.estimate();
          RTC_LOG(LS_INFO) << "[AIMD-Decrease] Using link capacity. Original: " << decreased_bitrate.bps()
                           << " bps, Link based: " << link_based_decrease.bps()
                           << " bps (capacity " << link_capacity_.estimate().bps() << " * beta " << beta_ << ")";
          decreased_bitrate = link_based_decrease;
        }
      }
      // Avoid increasing the rate when over-using.
      if (decreased_bitrate < current_bitrate_) {
        new_bitrate = decreased_bitrate;
        int64_t reduction = current_bitrate_.bps() - new_bitrate->bps();
        
        RTC_LOG(LS_INFO) << "[AIMD-Decrease] Applied decrease: " << new_bitrate->bps()
                         << " bps, Reduction: " << reduction << " bps";
        
        last_strategy_name_ = "Multiplicative-Decrease";
        last_strategy_params_ = "Beta=" + std::to_string(beta_) + 
                                ",Throughput=" + std::to_string(estimated_throughput.bps()) + "bps" +
                                ",Reduction=" + std::to_string(reduction) + "bps";
      } else {
        RTC_LOG(LS_INFO) << "[AIMD-Decrease] No decrease applied (would increase rate)";
        last_strategy_name_ = "Hold";
        last_strategy_params_ = "Reason=NoDecrease,Bitrate=" + std::to_string(current_bitrate_.bps());
      }

      if (bitrate_is_initialized_ && estimated_throughput < current_bitrate_) {
        if (!new_bitrate.has_value()) {
          last_decrease_ = DataRate::Zero();
        } else {
          last_decrease_ = current_bitrate_ - *new_bitrate;
        }
        RTC_LOG(LS_INFO) << "[AIMD-Decrease] Recorded decrease: " << last_decrease_->bps() << " bps";
      }
      if (estimated_throughput < link_capacity_.LowerBound()) {
        // The current throughput is far from the estimated link capacity. Clear
        // the estimate to allow an immediate update in OnOveruseDetected.
        RTC_LOG(LS_INFO) << "[AIMD-Decrease] Resetting link capacity (throughput too low)";
        link_capacity_.Reset();
      }

      bitrate_is_initialized_ = true;
      link_capacity_.OnOveruseDetected(estimated_throughput);
      // Stay on hold until the pipes are cleared.
      rate_control_state_ = RateControlState::kRcHold;
      time_last_bitrate_change_ = at_time;
      time_last_bitrate_decrease_ = at_time;
      break;
    }
    default:
      RTC_DCHECK_NOTREACHED();
  }

  current_bitrate_ = ClampBitrate(new_bitrate.value_or(current_bitrate_));
}

DataRate AimdRateControl::ClampBitrate(DataRate new_bitrate) const {
  if (!disable_estimate_bounded_increase_ && network_estimate_ &&
      network_estimate_->link_capacity_upper.IsFinite()) {
    DataRate upper_bound =
        use_current_estimate_as_min_upper_bound_
            ? std::max(network_estimate_->link_capacity_upper, current_bitrate_)
            : network_estimate_->link_capacity_upper;
    new_bitrate = std::min(upper_bound, new_bitrate);
  }
  if (network_estimate_ && network_estimate_->link_capacity_lower.IsFinite() &&
      new_bitrate < current_bitrate_) {
    new_bitrate = std::min(
        current_bitrate_,
        std::max(new_bitrate, network_estimate_->link_capacity_lower * beta_));
  }
  new_bitrate = std::max(new_bitrate, min_configured_bitrate_);
  return new_bitrate;
}

DataRate AimdRateControl::MultiplicativeRateIncrease(
    Timestamp at_time,
    Timestamp last_time,
    DataRate current_bitrate) const {
  double alpha = 1.08;
  if (last_time.IsFinite()) {
    auto time_since_last_update = at_time - last_time;
    alpha = pow(alpha, std::min(time_since_last_update.seconds<double>(), 1.0));
  }
  DataRate multiplicative_increase =
      std::max(current_bitrate * (alpha - 1.0), DataRate::BitsPerSec(1000));
  return multiplicative_increase;
}

DataRate AimdRateControl::AdditiveRateIncrease(Timestamp at_time,
                                               Timestamp last_time) const {
  double time_period_seconds = (at_time - last_time).seconds<double>();
  double data_rate_increase_bps =
      GetNearMaxIncreaseRateBpsPerSecond() * time_period_seconds;
  return DataRate::BitsPerSec(data_rate_increase_bps);
}

void AimdRateControl::ChangeState(const RateControlInput& input,
                                  Timestamp at_time) {
  RateControlState old_state = rate_control_state_;
  
  // First, apply normal state transitions based on bandwidth usage
  switch (input.bw_state) {
    case BandwidthUsage::kBwNormal:
      if (rate_control_state_ == RateControlState::kRcHold) {
        time_last_bitrate_change_ = at_time;
        rate_control_state_ = RateControlState::kRcIncrease;
      }
      break;
    case BandwidthUsage::kBwOverusing:
      if (rate_control_state_ != RateControlState::kRcDecrease) {
        rate_control_state_ = RateControlState::kRcDecrease;
      }
      break;
    case BandwidthUsage::kBwUnderusing:
      rate_control_state_ = RateControlState::kRcHold;
      break;
    default:
      RTC_DCHECK_NOTREACHED();
  }
  
  // Apply cellular ratio-based preventive control if we have fresh data
  if (HasFreshCellularData(at_time)) {
    // 预防性控制策略：不主动降速，只是阻止增长或保持当前速率
    
    if (ShouldForceHold()) {
      // 当ratio < 0.7时，如果当前想增长，改为保持
      // 这样可以避免继续增加负载导致overuse
      if (rate_control_state_ == RateControlState::kRcIncrease) {
        rate_control_state_ = RateControlState::kRcHold;
        RTC_LOG(LS_INFO) << "[AIMD-Cellular] Preventive HOLD due to low ratio: " 
                         << smoothed_cellular_ratio_ 
                         << " (preventing increase to avoid overuse)";
      }
    }
    // 注意：我们不强制DECREASE，让WebRTC自己的overuse检测来处理
    // 我们的目标是预防，不是治疗
  }
  
  if (old_state != rate_control_state_) {
    const char* old_state_str = "Unknown";
    const char* new_state_str = "Unknown";
    
    switch (old_state) {
      case RateControlState::kRcHold: old_state_str = "Hold"; break;
      case RateControlState::kRcIncrease: old_state_str = "Increase"; break;
      case RateControlState::kRcDecrease: old_state_str = "Decrease"; break;
    }
    
    switch (rate_control_state_) {
      case RateControlState::kRcHold: new_state_str = "Hold"; break;
      case RateControlState::kRcIncrease: new_state_str = "Increase"; break;
      case RateControlState::kRcDecrease: new_state_str = "Decrease"; break;
    }
    
    const char* bw_state_str = "Unknown";
    switch (input.bw_state) {
      case BandwidthUsage::kBwNormal: bw_state_str = "Normal"; break;
      case BandwidthUsage::kBwOverusing: bw_state_str = "Overusing"; break;
      case BandwidthUsage::kBwUnderusing: bw_state_str = "Underusing"; break;
      default: bw_state_str = "Unknown"; break;
    }
    
    RTC_LOG(LS_INFO) << "[AIMD-StateChange] " << old_state_str << " -> " << new_state_str 
                     << " (BW state: " << bw_state_str << ")";
  }
}

// Cellular resource ratio support methods
void AimdRateControl::SetCellularResourceRatio(double ratio, Timestamp at_time) {
  // Clamp ratio to valid range [0, 2]
  ratio = std::max(0.0, std::min(2.0, ratio));
  
  // Store previous ratio for trend detection
  previous_ratio_ = smoothed_cellular_ratio_;
  
  // Apply exponential smoothing with alpha = 0.3 for faster response
  // Higher alpha means new values have more weight, allowing faster recovery
  const double kSmoothingAlpha = 0.3;
  smoothed_cellular_ratio_ = kSmoothingAlpha * ratio + 
                             (1.0 - kSmoothingAlpha) * smoothed_cellular_ratio_;
  
  cellular_resource_ratio_ = ratio;
  last_ratio_update_time_ = at_time;
  
  // Update consecutive high ratio count for fourth layer defense
  if (smoothed_cellular_ratio_ >= kMultiplicativeGrowthThreshold) {
    consecutive_high_ratio_count_++;
    RTC_LOG(LS_INFO) << "[AIMD-Cellular] High ratio detected: " 
                     << smoothed_cellular_ratio_ << " (count: " 
                     << consecutive_high_ratio_count_ << "/" 
                     << kConsecutiveHighRatioThreshold << ")";
  } else {
    consecutive_high_ratio_count_ = 0;  // Reset counter
  }
  
  // Log significant ratio changes
  if (std::abs(ratio - previous_ratio_) > 0.1) {
    RTC_LOG(LS_INFO) << "[AIMD-Cellular] Resource ratio updated: " 
                     << ratio << " (smoothed: " << smoothed_cellular_ratio_ 
                     << "), trend: " << (ratio - previous_ratio_);
  }
}

bool AimdRateControl::HasFreshCellularData(Timestamp at_time) const {
  // Consider data fresh if updated within last 1 second
  const TimeDelta kFreshnessWindow = TimeDelta::Seconds(1);
  return last_ratio_update_time_.IsFinite() && 
         (at_time - last_ratio_update_time_) < kFreshnessWindow;
}

bool AimdRateControl::ShouldForceDecrease() const {
  // 不再强制DECREASE - WebRTC自己会检测overuse
  // 我们只是提前预防，不主动降速
  return false;
}

bool AimdRateControl::ShouldForceHold() const {
  // 当ratio较低时(< 0.7)，保持当前速率，避免继续增长
  // 这是预防性措施，防止触发overuse
  const double kHoldThreshold = 0.7;
  return smoothed_cellular_ratio_ < kHoldThreshold;
}

bool AimdRateControl::ShouldLimitIncrease() const {
  // 当ratio在0.7-0.9之间时，限制为保守的加性增长
  // 避免激进增长导致overuse
  const double kLimitThreshold = 0.9;
  
  // 检测负趋势 - 如果ratio在下降，即使当前值还可以，也要保守
  double trend = smoothed_cellular_ratio_ - previous_ratio_;
  bool negative_trend = trend < -0.02;  // 检测轻微负趋势
  
  return (smoothed_cellular_ratio_ < kLimitThreshold) || 
         (smoothed_cellular_ratio_ < 1.0 && negative_trend);
}

bool AimdRateControl::ShouldForceMultiplicativeGrowth() const {
  // 第四层防御：当ratio连续高于阈值时，强制进入乘法增长
  // 目标：在网络状况持续良好时更积极利用带宽
  return consecutive_high_ratio_count_ >= kConsecutiveHighRatioThreshold;
}

}  // namespace webrtc

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

std::string FormatDataRateBps(const DataRate& rate) {
  if (!rate.IsFinite()) {
    return "inf";
  }
  return std::to_string(rate.bps()) + " bps";
}

std::string FormatOptionalDataRateBps(
    const std::optional<DataRate>& maybe_rate) {
  if (!maybe_rate) {
    return "n/a";
  }
  return FormatDataRateBps(*maybe_rate);
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
      previous_rtt_(kDefaultRtt),
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
  previous_rtt_ = rtt_;
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
  
  const std::string at_time_str =
      at_time.IsFinite() ? std::to_string(at_time.ms()) : "N/A";

  RTC_LOG(LS_INFO) << "[" << GetWallClockTimestampString() << "]"
                   << " [AIMD-Update] MonoTime: " << at_time_str
                   << " ms, Input state: " << static_cast<int>(input.bw_state)
                   << ", Estimated throughput: " << FormatOptionalDataRateBps(input.estimated_throughput)
                   << ", Current bitrate: " << FormatDataRateBps(current_bitrate_)
                   << ", Link capacity estimate: " << (link_capacity_.has_estimate() ? "yes" : "no")
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

      // We limit the new bitrate based on the throughput to avoid unlimited
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
                       << " bps, Cellular ratio influence: "
                       << (cellular_ratio_influence_enabled_ ? "enabled" : "disabled");

      if (current_bitrate_ < increase_limit) {
        DataRate target_bitrate = current_bitrate_;  // Initialize with current as fallback

        // Use cellular ratio-based gain if enabled and data is fresh
        if (cellular_ratio_influence_enabled_ && HasFreshCellularData(at_time)) {
          // Define neutral zone boundaries (must match ComputeGainFromRatio)
          const double kNeutralLower = 0.20;  // Neutral zone lower bound
          const double kNeutralUpper = 0.40;  // Neutral zone upper bound
          bool is_in_neutral_zone = (smoothed_cellular_ratio_ >= kNeutralLower &&
                                     smoothed_cellular_ratio_ <= kNeutralUpper);

          if (is_in_neutral_zone) {
            // In neutral zone (ratio 0.2-0.4, gain=1.0): use slope to decide direction
            if (trendline_slope_ <= 0) {
              // Delay trend stable or decreasing: additive bonus
              DataRate additive_bonus =
                  AdditiveRateIncrease(at_time, time_last_bitrate_change_);
              target_bitrate = current_bitrate_ + additive_bonus;

              RTC_LOG(LS_INFO) << "[AIMD-NeutralPlus] Slope: " << trendline_slope_
                               << " (not increasing), Ratio: " << smoothed_cellular_ratio_
                               << " (neutral zone), AdditiveBonus: " << additive_bonus.bps() << " bps"
                               << ", Current: " << current_bitrate_.bps() << " bps"
                               << ", Target: " << target_bitrate.bps() << " bps";

              last_strategy_name_ = "Neutral-Zone-Plus-Additive";
              last_strategy_params_ = "Slope=" + std::to_string(trendline_slope_) +
                                      ",Ratio=" + std::to_string(smoothed_cellular_ratio_) +
                                      ",Additive=" + std::to_string(additive_bonus.bps()) + "bps";
            } else {
              // Delay trend increasing: reduction
              DataRate reduction =
                  AdditiveRateIncrease(at_time, time_last_bitrate_change_);
              target_bitrate = current_bitrate_ - reduction;

              // Ensure we don't go below a minimum threshold
              DataRate min_bitrate = DataRate::KilobitsPerSec(100);
              if (target_bitrate < min_bitrate) {
                target_bitrate = min_bitrate;
              }

              RTC_LOG(LS_INFO) << "[AIMD-NeutralMinus] Slope: " << trendline_slope_
                               << " (increasing), Ratio: " << smoothed_cellular_ratio_
                               << " (neutral zone), Reduction: " << reduction.bps() << " bps"
                               << ", Current: " << current_bitrate_.bps() << " bps"
                               << ", Target: " << target_bitrate.bps() << " bps";

              last_strategy_name_ = "Neutral-Zone-Minus-Reduction";
              last_strategy_params_ = "Slope=" + std::to_string(trendline_slope_) +
                                      ",Ratio=" + std::to_string(smoothed_cellular_ratio_) +
                                      ",Reduction=" + std::to_string(reduction.bps()) + "bps";
            }
          } else if (smoothed_cellular_ratio_ > kNeutralUpper) {
            // Above neutral zone (ratio > 0.40): hold here
            // RatioImmediateIncrease already handles increase
            target_bitrate = current_bitrate_;

            RTC_LOG(LS_INFO) << "[AIMD-RatioHoldIncrease] Ratio: " << smoothed_cellular_ratio_
                             << " > " << kNeutralUpper
                             << ", holding (RatioImmediateIncrease handles)";

            last_strategy_name_ = "Ratio-Hold-Increase";
            last_strategy_params_ = "Ratio=" + std::to_string(smoothed_cellular_ratio_);
          } else {
            // Below neutral zone (ratio < 0.20): hold here
            // RatioImmediate already handles reduction, don't double-reduce
            target_bitrate = current_bitrate_;

            RTC_LOG(LS_INFO) << "[AIMD-RatioHold] Ratio: " << smoothed_cellular_ratio_
                             << " < " << kNeutralLower
                             << ", holding (RatioImmediate handles reduction)";

            last_strategy_name_ = "Ratio-Hold";
            last_strategy_params_ = "Ratio=" + std::to_string(smoothed_cellular_ratio_);
          }
        } else {
          // Fallback to standard AIMD logic when ratio influence disabled or no fresh data
          if (link_capacity_.has_estimate()) {
            // Use additive increase when we have link capacity estimate
            DataRate additive_increase =
                AdditiveRateIncrease(at_time, time_last_bitrate_change_);
            target_bitrate = current_bitrate_ + additive_increase;

            double increase_rate_bps_per_sec = GetNearMaxIncreaseRateBpsPerSecond();
            TimeDelta time_since_change = at_time - time_last_bitrate_change_;
            const bool time_initialized = time_last_bitrate_change_.IsFinite();
            std::string time_delta_value =
                time_initialized ? std::to_string(time_since_change.ms_or(0)) : "N/A";
            std::string time_delta_param =
                time_initialized ? time_delta_value + "ms" : "N/A";

            RTC_LOG(LS_INFO) << "[AIMD-Additive] Base increase: " << additive_increase.bps()
                             << " bps, Near max rate: " << increase_rate_bps_per_sec
                             << " bps/s, Time delta: " << time_delta_value
                             << " ms, Link capacity: " << link_capacity_.estimate().bps() << " bps";

            last_strategy_name_ = "Additive-Increase";
            last_strategy_params_ = "Rate=" + std::to_string(static_cast<int>(increase_rate_bps_per_sec)) +
                                    "bps/s,Delta=" + time_delta_param +
                                    ",LinkCap=" + std::to_string(link_capacity_.estimate().bps()) + "bps";
          } else {
            // Use multiplicative increase to discover the capacity
            DataRate multiplicative_increase = MultiplicativeRateIncrease(
                at_time, time_last_bitrate_change_, current_bitrate_);
            target_bitrate = current_bitrate_ + multiplicative_increase;

            TimeDelta time_since_change = at_time - time_last_bitrate_change_;
            const bool time_initialized = time_last_bitrate_change_.IsFinite();
            std::string time_delta_value =
                time_initialized ? std::to_string(time_since_change.ms_or(0)) : "N/A";
            std::string time_delta_param =
                time_initialized ? time_delta_value + "ms" : "N/A";
            double alpha_factor = multiplicative_increase.bps() / std::max(current_bitrate_.bps(), static_cast<int64_t>(1)) + 1.0;

            RTC_LOG(LS_INFO) << "[AIMD-Multiplicative] Base increase: " << multiplicative_increase.bps()
                             << " bps, Alpha factor: " << alpha_factor
                             << ", Time delta: " << time_delta_value << " ms";

            last_strategy_name_ = "Multiplicative-Increase";
            last_strategy_params_ = "Alpha=" + std::to_string(alpha_factor) +
                                    ",Delta=" + time_delta_param;
          }
        }

        // Verify target_bitrate is finite before using it
        if (!target_bitrate.IsFinite()) {
          RTC_LOG(LS_ERROR) << "[AIMD-Error] Computed target_bitrate is not finite! "
                            << "Falling back to current_bitrate: " << current_bitrate_.bps() << " bps";
          target_bitrate = current_bitrate_;
        }

        new_bitrate = std::min(target_bitrate, increase_limit);

        if (new_bitrate != target_bitrate) {
          RTC_LOG(LS_INFO) << "[AIMD-Limited] Increase capped. Desired: " << target_bitrate.bps()
                           << " bps, Limited to: " << new_bitrate->bps() << " bps";
        }
      } else {
        // Current bitrate is at or above limit - don't increase
        // But still apply ratio-based reduction if network is congested
        if (cellular_ratio_influence_enabled_ && HasFreshCellularData(at_time)) {
          double gain_ratio = ComputeGainFromRatio(smoothed_cellular_ratio_);

          if (gain_ratio < 1.0) {
            // Ratio indicates congestion, apply reduction even above limit
            DataRate target_bitrate = current_bitrate_ * gain_ratio;

            // Ensure we don't go below minimum
            DataRate min_bitrate = DataRate::KilobitsPerSec(100);
            if (target_bitrate < min_bitrate) {
              target_bitrate = min_bitrate;
            }

            new_bitrate = target_bitrate;

            RTC_LOG(LS_INFO) << "[AIMD-AboveLimitReduction] Ratio: " << smoothed_cellular_ratio_
                             << ", GainRatio: " << gain_ratio
                             << ", Current: " << current_bitrate_.bps() << " bps"
                             << ", Target: " << target_bitrate.bps() << " bps"
                             << ", Reduction: " << (current_bitrate_.bps() - target_bitrate.bps()) << " bps";

            last_strategy_name_ = "Above-Limit-Ratio-Reduction";
            last_strategy_params_ = "Ratio=" + std::to_string(smoothed_cellular_ratio_) +
                                    ",GainRatio=" + std::to_string(gain_ratio) +
                                    ",Reduction=" + std::to_string(current_bitrate_.bps() - target_bitrate.bps()) + "bps";
          } else {
            RTC_LOG(LS_INFO) << "[AIMD-NoIncrease] Current bitrate at or above limit, ratio healthy: "
                             << smoothed_cellular_ratio_;
            last_strategy_name_ = "Hold-Above-Limit";
            last_strategy_params_ = "Ratio=" + std::to_string(smoothed_cellular_ratio_) +
                                    ",GainRatio=" + std::to_string(gain_ratio);
          }
        } else {
          RTC_LOG(LS_INFO) << "[AIMD-NoIncrease] Current bitrate at or above limit";
          last_strategy_name_ = "Hold-Above-Limit";
          last_strategy_params_ = "NoFreshRatioData";
        }
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
  // Handle case where last_time hasn't been initialized yet
  if (!last_time.IsFinite()) {
    // Use a default small increase for the first update
    return DataRate::BitsPerSec(GetNearMaxIncreaseRateBpsPerSecond() * 0.1);
  }

  double time_period_seconds = (at_time - last_time).seconds<double>();

  // Validate time_period_seconds is finite and reasonable
  if (!std::isfinite(time_period_seconds) || time_period_seconds < 0 || time_period_seconds > 10.0) {
    RTC_LOG(LS_WARNING) << "[AIMD-Error] Invalid time_period_seconds: " << time_period_seconds
                        << " (at_time: " << at_time.ms() << " ms, last_time: " << last_time.ms() << " ms)";
    // Use a small default increase to avoid crash
    return DataRate::BitsPerSec(GetNearMaxIncreaseRateBpsPerSecond() * 0.1);
  }

  double data_rate_increase_bps =
      GetNearMaxIncreaseRateBpsPerSecond() * time_period_seconds;

  // Validate the result is finite
  if (!std::isfinite(data_rate_increase_bps)) {
    RTC_LOG(LS_WARNING) << "[AIMD-Error] Computed data_rate_increase_bps is not finite!";
    return DataRate::BitsPerSec(GetNearMaxIncreaseRateBpsPerSecond() * 0.1);
  }

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
      // When cellular ratio influence is enabled, skip GCC's Overuse reduction
      // All reductions are controlled by ratio-driven immediate reduction
      if (cellular_ratio_influence_enabled_) {
        RTC_LOG(LS_INFO) << "[AIMD-SkipOveruse] Ratio influence enabled, "
                         << "ignoring GCC Overuse signal (ratio controls reduction)";
        // Stay in current state, don't transition to Decrease
      } else {
        if (rate_control_state_ != RateControlState::kRcDecrease) {
          rate_control_state_ = RateControlState::kRcDecrease;
        }
      }
      break;
    case BandwidthUsage::kBwUnderusing:
      rate_control_state_ = RateControlState::kRcHold;
      break;
    default:
      RTC_DCHECK_NOTREACHED();
  }
  
  // Note: Cellular ratio influence is now applied in ChangeBitrate via gain calculation
  // We don't modify state transitions here - let GoogCC's overuse detection handle state changes
  
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
void AimdRateControl::SetCellularResourceRatio(double ratio,
                                               double saturation,
                                               Timestamp at_time) {
  // Clamp ratio to valid range [0, 2]
  ratio = std::max(0.0, std::min(2.0, ratio));

  // Skip ratio >= 1.0 as analysis shows 95.6% are single-sample noise spikes
  if (ratio >= 1.0) {
    RTC_LOG(LS_INFO) << "[AIMD-RatioSkip] Ignoring high ratio: " << ratio;
    return;
  }

  cellular_resource_saturation_ = saturation;

  // Store previous ratio for trend detection
  previous_ratio_ = smoothed_cellular_ratio_;

  // Apply exponential smoothing with fixed alpha
  // Lower alpha = more smoothing, less variance
  double alpha = 0.6;
  smoothed_cellular_ratio_ = alpha * ratio + (1.0 - alpha) * smoothed_cellular_ratio_;

  cellular_resource_ratio_ = ratio;
  last_ratio_update_time_ = at_time;

  // RatioImmediate: 当ratio低于neutral zone时立即减速，不等TransportFeedback
  // 每次ratio更新都响应（~7ms），使用小增量保持响应性
  const double kNeutralLower = 0.20;  // Neutral zone lower bound

  if (cellular_ratio_influence_enabled_ &&
      smoothed_cellular_ratio_ < kNeutralLower &&
      current_bitrate_.IsFinite() && current_bitrate_ > min_configured_bitrate_) {

    double gain = ComputeGainFromRatio(smoothed_cellular_ratio_);
    DataRate new_bitrate = current_bitrate_ * gain;
    new_bitrate = std::max(new_bitrate, min_configured_bitrate_);

    RTC_LOG(LS_INFO) << "[AIMD-RatioImmediate] Ratio: " << smoothed_cellular_ratio_
                     << " < " << kNeutralLower
                     << ", Gain: " << gain
                     << ", Bitrate: " << current_bitrate_.bps()
                     << " -> " << new_bitrate.bps() << " bps"
                     << ", Reduction: " << (current_bitrate_ - new_bitrate).bps() << " bps";

    current_bitrate_ = new_bitrate;
    time_last_bitrate_change_ = at_time;
    time_last_bitrate_decrease_ = at_time;
  }

  // RatioImmediate增速: 当ratio高于neutral zone时立即增速
  // 每次ratio更新都响应（~7ms），使用小增量保持响应性
  // 限制不超过estimated_throughput的1.5倍（与原版GCC一致）
  const double kNeutralUpper = 0.40;  // neutral zone upper bound

  if (cellular_ratio_influence_enabled_ &&
      smoothed_cellular_ratio_ > kNeutralUpper &&
      current_bitrate_.IsFinite() &&
      latest_estimated_throughput_.IsFinite()) {

    // 计算增长限制：1.5倍estimated_throughput + 10kbps（原版GCC逻辑）
    DataRate increase_limit =
        1.5 * latest_estimated_throughput_ + DataRate::KilobitsPerSec(10);

    // 只有当前比特率低于限制时才增速
    if (current_bitrate_ < increase_limit) {
      double gain = ComputeGainFromRatio(smoothed_cellular_ratio_);
      DataRate new_bitrate = current_bitrate_ * gain;

      // 确保不超过限制
      new_bitrate = std::min(new_bitrate, increase_limit);

      RTC_LOG(LS_INFO) << "[AIMD-RatioImmediateIncrease] Ratio: " << smoothed_cellular_ratio_
                       << " > " << kNeutralUpper
                       << ", Gain: " << gain
                       << ", Bitrate: " << current_bitrate_.bps()
                       << " -> " << new_bitrate.bps() << " bps"
                       << ", Limit: " << increase_limit.bps() << " bps";

      current_bitrate_ = new_bitrate;
      time_last_bitrate_change_ = at_time;
    }
  }

  // Log significant ratio changes
  if (std::abs(ratio - previous_ratio_) > 0.1 || std::abs(saturation) > 0.1) {
    RTC_LOG(LS_INFO) << "[AIMD-Cellular] Resource ratio updated: "
                     << ratio << " (smoothed: " << smoothed_cellular_ratio_
                     << ", saturation: " << saturation
                     << ", influence: " << (cellular_ratio_influence_enabled_ ? "enabled" : "disabled")
                     << "), trend: " << (ratio - previous_ratio_);
  }
}

bool AimdRateControl::HasFreshCellularData(Timestamp at_time) const {
  // Consider data fresh if updated within last 1 second
  const TimeDelta kFreshnessWindow = TimeDelta::Seconds(1);
  return last_ratio_update_time_.IsFinite() && 
         (at_time - last_ratio_update_time_) < kFreshnessWindow;
}

double AimdRateControl::ComputeGainFromRatio(double ratio) const {
  // Ratio-based gain using sigmoid for smooth transitions outside neutral zone
  //
  // 设计目标（7ms更新频率，~143次/秒）：
  //   - 最大增长：~143%/秒 → 1.01/次 (1%)
  //   - 最大减少：~143%/秒 → 0.99/次 (1%)
  //
  // Ratio → gain_ratio:
  //    - ratio < 0.20  → sigmoid从1.0平滑过渡到0.99 (减速)
  //    - ratio 0.20~0.40 → gain_ratio = 1.0 (neutral zone, 不动)
  //    - ratio > 0.40  → sigmoid从1.0平滑过渡到1.01 (增速)

  const double kNeutralLower = 0.20;  // Neutral zone lower bound
  const double kNeutralUpper = 0.40;  // Neutral zone upper bound
  const double kMinGain = 0.99;       // Max reduction: 1% per update
  const double kMaxGain = 1.01;       // Max increase: 1% per update
  const double kSteepness = 50.0;     // Sigmoid steepness

  double gain_ratio = 1.0;

  if (ratio >= kNeutralLower && ratio <= kNeutralUpper) {
    // Neutral zone: no change
    gain_ratio = 1.0;
  } else if (ratio < kNeutralLower) {
    // Below neutral zone: sigmoid减速
    // ratio=0.10 → gain=1.0, ratio=0.00 → gain≈0.992
    // sigmoid中心点在0.05，向左递减
    double x = (ratio - 0.05) * kSteepness;  // 中心点0.05
    double sigmoid = 1.0 / (1.0 + std::exp(-x));
    // sigmoid: 0→0.076, 0.05→0.5, 0.10→0.924
    // 映射: gain = 0.992 + 0.008 * sigmoid
    gain_ratio = kMinGain + (1.0 - kMinGain) * sigmoid;
  } else {
    // Above neutral zone: sigmoid增速
    // ratio=0.40 → gain=1.0, ratio=0.70+ → gain≈1.008
    // sigmoid中心点在0.55，向右递增
    double x = (ratio - 0.55) * kSteepness;  // 中心点0.55
    double sigmoid = 1.0 / (1.0 + std::exp(-x));
    // sigmoid: 0.40→0.0007, 0.55→0.5, 0.70→0.9993
    // 映射: gain = 1.0 + 0.008 * sigmoid
    gain_ratio = 1.0 + (kMaxGain - 1.0) * sigmoid;
  }

  RTC_LOG(LS_INFO) << "[AIMD-RatioGain] "
                   << "Ratio: " << ratio << " → GainRatio: " << gain_ratio;

  return gain_ratio;
}

void AimdRateControl::SetCellularRatioInfluenceEnabled(bool enabled) {
  cellular_ratio_influence_enabled_ = enabled;
  RTC_LOG(LS_INFO) << "[AIMD-Cellular] Ratio influence "
                   << (enabled ? "enabled" : "disabled");
}

void AimdRateControl::SetCUSUMInfluenceEnabled(bool enabled) {
  cusum_influence_enabled_ = enabled;
  RTC_LOG(LS_INFO) << "[AIMD-Cellular] CUSUM influence "
                   << (enabled ? "enabled" : "disabled");
}

void AimdRateControl::SetTrendlineSlope(double slope) {
  trendline_slope_ = slope;
}

double AimdRateControl::ComputeGainFromSlope(double slope) const {
  // Map trendline slope to gain using sigmoid function (asymmetric)
  // slope < 0 (delay decreasing) → gain > 1.0 (can increase bandwidth)
  // slope = 0 (delay stable)     → gain = 1.0 (maintain)
  // slope > 0 (delay increasing) → gain < 1.0 (should be conservative)
  //
  // Asymmetric design: larger increase (+5%), smaller decrease (-2%)
  // This allows more aggressive growth when network is good,
  // but conservative reduction when network shows congestion signs.

  const double kSensitivity = 100.0;   // Controls how quickly gain changes with slope
  const double kMaxIncrease = 0.05;    // Maximum increase when slope < 0 (+5%)

  double sigmoid = 1.0 / (1.0 + std::exp(slope * kSensitivity));

  // Only increase, never decrease: sigmoid ∈ [0,1] maps to gain ∈ [1.0, 1+kMaxIncrease]
  double gain = 1.0 + kMaxIncrease * sigmoid;

  // Clamp to valid range [1.0, 1.05]
  gain = std::max(1.0, std::min(1.0 + kMaxIncrease, gain));

  return gain;
}

}  // namespace webrtc

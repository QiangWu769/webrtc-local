/*
 *  Copyright (c) 2016 The WebRTC project authors. All Rights Reserved.
 *
 *  Use of this source code is governed by a BSD-style license
 *  that can be found in the LICENSE file in the root of the source
 *  tree. An additional intellectual property rights grant can be found
 *  in the file PATENTS.  All contributing project authors may
 *  be found in the AUTHORS file in the root of the source tree.
 */

#include "modules/congestion_controller/goog_cc/delay_based_bwe.h"

#include <algorithm>
#include <cstdint>
#include <iomanip>
#include <memory>
#include <optional>
#include <sstream>
#include <utility>
#include <vector>

#include "api/field_trials_view.h"
#include "api/network_state_predictor.h"
#include "api/rtc_event_log/rtc_event_log.h"
#include "api/transport/bandwidth_usage.h"
#include "api/transport/network_types.h"
#include "api/units/data_rate.h"
#include "api/units/data_size.h"
#include "api/units/time_delta.h"
#include "api/units/timestamp.h"
#include "logging/rtc_event_log/events/rtc_event_bwe_update_delay_based.h"
#include "modules/congestion_controller/goog_cc/delay_increase_detector_interface.h"
#include "modules/congestion_controller/goog_cc/inter_arrival_delta.h"
#include "modules/congestion_controller/goog_cc/trendline_estimator.h"
#include "modules/remote_bitrate_estimator/include/bwe_defines.h"
#include "rtc_base/checks.h"
#include "rtc_base/experiments/struct_parameters_parser.h"
#include "rtc_base/logging.h"
#include "rtc_base/race_checker.h"
#include "rtc_base/time_utils.h"
#include "system_wrappers/include/metrics.h"

namespace webrtc {

namespace {
constexpr TimeDelta kStreamTimeOut = TimeDelta::Seconds(2);
constexpr TimeDelta kSendTimeGroupLength = TimeDelta::Millis(5);

// This ssrc is used to fulfill the current API but will be removed
// after the API has been changed.
constexpr uint32_t kFixedSsrc = 0;

// Helper function to get wall clock timestamp as a string with 6 decimal places
std::string GetWallClockTimestampString() {
  double unix_seconds = webrtc::TimeUTCMillis() / 1000.0;
  std::stringstream ss;
  ss << std::fixed << std::setprecision(6) << unix_seconds;
  return ss.str();
}
}  // namespace

constexpr char BweSeparateAudioPacketsSettings::kKey[];

BweSeparateAudioPacketsSettings::BweSeparateAudioPacketsSettings(
    const FieldTrialsView* key_value_config) {
  Parser()->Parse(
      key_value_config->Lookup(BweSeparateAudioPacketsSettings::kKey));
}

std::unique_ptr<StructParametersParser>
BweSeparateAudioPacketsSettings::Parser() {
  return StructParametersParser::Create(      //
      "enabled", &enabled,                    //
      "packet_threshold", &packet_threshold,  //
      "time_threshold", &time_threshold);
}

DelayBasedBwe::Result::Result()
    : updated(false),
      probe(false),
      target_bitrate(DataRate::Zero()),
      recovered_from_overuse(false),
      delay_detector_state(BandwidthUsage::kBwNormal) {}

DelayBasedBwe::DelayBasedBwe(const FieldTrialsView* key_value_config,
                             RtcEventLog* event_log,
                             NetworkStatePredictor* network_state_predictor)
    : event_log_(event_log),
      key_value_config_(key_value_config),
      separate_audio_(key_value_config),
      audio_packets_since_last_video_(0),
      last_video_packet_recv_time_(Timestamp::MinusInfinity()),
      network_state_predictor_(network_state_predictor),
      video_delay_detector_(
          new TrendlineEstimator(*key_value_config_, network_state_predictor_)),
      audio_delay_detector_(
          new TrendlineEstimator(*key_value_config_, network_state_predictor_)),
      active_delay_detector_(video_delay_detector_.get()),
      last_seen_packet_(Timestamp::MinusInfinity()),
      uma_recorded_(false),
      rate_control_(*key_value_config, /*send_side=*/true),
      prev_bitrate_(DataRate::Zero()),
      prev_state_(BandwidthUsage::kBwNormal) {
  RTC_LOG(LS_INFO)
      << "Initialized DelayBasedBwe with separate audio overuse detection"
      << separate_audio_.Parser()->Encode();
}

DelayBasedBwe::~DelayBasedBwe() {}

DelayBasedBwe::Result DelayBasedBwe::IncomingPacketFeedbackVector(
    const TransportPacketsFeedback& msg,
    std::optional<DataRate> acked_bitrate,
    std::optional<DataRate> probe_bitrate,
    std::optional<NetworkStateEstimate> network_estimate,
    bool in_alr) {
  RTC_DCHECK_RUNS_SERIALIZED(&network_race_);

  auto packet_feedback_vector = msg.SortedByReceiveTime();
  // TODO(holmer): An empty feedback vector here likely means that
  // all acks were too late and that the send time history had
  // timed out. We should reduce the rate when this occurs.
  if (packet_feedback_vector.empty()) {
    RTC_LOG(LS_WARNING) << "[DelayBWE-Feedback] Very late feedback received, no packets to process.";
    return DelayBasedBwe::Result();
  }
  
  RTC_LOG(LS_VERBOSE) << "[DelayBWE-Feedback] Processing " << packet_feedback_vector.size() 
                      << " packets. Feedback time: " << msg.feedback_time.ms() 
                      << " ms, In ALR: " << (in_alr ? "yes" : "no");

  if (!uma_recorded_) {
    RTC_HISTOGRAM_ENUMERATION(kBweTypeHistogram,
                              BweNames::kSendSideTransportSeqNum,
                              BweNames::kBweNamesMax);
    uma_recorded_ = true;
  }
  bool delayed_feedback = true;
  bool recovered_from_overuse = false;
  BandwidthUsage prev_detector_state = active_delay_detector_->State();
  for (const auto& packet_feedback : packet_feedback_vector) {
    delayed_feedback = false;
    IncomingPacketFeedback(packet_feedback, msg.feedback_time);
    if (prev_detector_state == BandwidthUsage::kBwUnderusing &&
        active_delay_detector_->State() == BandwidthUsage::kBwNormal) {
      recovered_from_overuse = true;
    }
    prev_detector_state = active_delay_detector_->State();
  }

  if (delayed_feedback) {
    // TODO(bugs.webrtc.org/10125): Design a better mechanism to safe-guard
    // against building very large network queues.
    RTC_LOG(LS_WARNING) << "[DelayBWE-Feedback] All feedback was delayed, returning empty result";
    return Result();
  }
  
  RTC_LOG(LS_VERBOSE) << "[DelayBWE-Feedback] State changes detected. "
                      << "Recovered from overuse: " << (recovered_from_overuse ? "yes" : "no");
  
  rate_control_.SetInApplicationLimitedRegion(in_alr);
  rate_control_.SetNetworkStateEstimate(network_estimate);
  
  Result final_result = MaybeUpdateEstimate(acked_bitrate, probe_bitrate,
                                           std::move(network_estimate),
                                           recovered_from_overuse, in_alr, msg.feedback_time);
  
  // 只记录probe和recovery信息（其他信息在BWE-DECISION中已包含）
  if (final_result.probe || final_result.recovered_from_overuse) {
    RTC_LOG(LS_INFO) << "[" << GetWallClockTimestampString() << "]" << " [DelayBWE-Special] MonoTime: " << msg.feedback_time.ms() << " ms"
                     << ", Probe: " << (final_result.probe ? "yes" : "no")
                     << ", Recovered: " << (final_result.recovered_from_overuse ? "yes" : "no");
  }
  
  return final_result;
}

void DelayBasedBwe::IncomingPacketFeedback(const PacketResult& packet_feedback,
                                           Timestamp at_time) {
  // Reset if the stream has timed out.
  if (last_seen_packet_.IsInfinite() ||
      at_time - last_seen_packet_ > kStreamTimeOut) {
    RTC_LOG(LS_INFO) << "[DelayBWE-Reset] Stream timeout detected, resetting estimators. "
                     << "Last packet: " << last_seen_packet_.ms() 
                     << " ms, Current: " << at_time.ms() << " ms";
    
    video_inter_arrival_delta_ =
        std::make_unique<InterArrivalDelta>(kSendTimeGroupLength);
    audio_inter_arrival_delta_ =
        std::make_unique<InterArrivalDelta>(kSendTimeGroupLength);

    video_delay_detector_.reset(
        new TrendlineEstimator(*key_value_config_, network_state_predictor_));
    audio_delay_detector_.reset(
        new TrendlineEstimator(*key_value_config_, network_state_predictor_));
    active_delay_detector_ = video_delay_detector_.get();
  }
  last_seen_packet_ = at_time;

  // As an alternative to ignoring small packets, we can separate audio and
  // video packets for overuse detection.
  DelayIncreaseDetectorInterface* delay_detector_for_packet =
      video_delay_detector_.get();
  if (separate_audio_.enabled) {
    if (packet_feedback.sent_packet.audio) {
      delay_detector_for_packet = audio_delay_detector_.get();
      audio_packets_since_last_video_++;
      bool switched_to_audio = false;
      if (audio_packets_since_last_video_ > separate_audio_.packet_threshold &&
          packet_feedback.receive_time - last_video_packet_recv_time_ >
              separate_audio_.time_threshold) {
        if (active_delay_detector_ != audio_delay_detector_.get()) {
          switched_to_audio = true;
        }
        active_delay_detector_ = audio_delay_detector_.get();
      }
      
      RTC_LOG(LS_VERBOSE) << "[DelayBWE-Audio] Audio packet processed. "
                          << "Audio packets since video: " << audio_packets_since_last_video_
                          << ", Time since video: " << (packet_feedback.receive_time - last_video_packet_recv_time_).ms()
                          << " ms, Switched to audio detector: " << (switched_to_audio ? "yes" : "no");
    } else {
      bool switched_to_video = (active_delay_detector_ != video_delay_detector_.get());
      audio_packets_since_last_video_ = 0;
      last_video_packet_recv_time_ =
          std::max(last_video_packet_recv_time_, packet_feedback.receive_time);
      active_delay_detector_ = video_delay_detector_.get();
      
      if (switched_to_video) {
        RTC_LOG(LS_INFO) << "[DelayBWE-Video] Switched back to video detector";
      }
    }
  }
  DataSize packet_size = packet_feedback.sent_packet.size;

  TimeDelta send_delta = TimeDelta::Zero();
  TimeDelta recv_delta = TimeDelta::Zero();
  int size_delta = 0;

  InterArrivalDelta* inter_arrival_for_packet =
      (separate_audio_.enabled && packet_feedback.sent_packet.audio)
          ? audio_inter_arrival_delta_.get()
          : video_inter_arrival_delta_.get();
  bool calculated_deltas = inter_arrival_for_packet->ComputeDeltas(
      packet_feedback.sent_packet.send_time, packet_feedback.receive_time,
      at_time, packet_size.bytes(), &send_delta, &recv_delta, &size_delta);

  if (calculated_deltas) {
    double delta_ms = recv_delta.ms<double>() - send_delta.ms<double>();
    RTC_LOG(LS_VERBOSE) << "[DelayBWE-Packet] "
                        << "Send time: " << packet_feedback.sent_packet.send_time.ms()
                        << " ms, Recv time: " << packet_feedback.receive_time.ms()
                        << " ms, Packet size: " << packet_size.bytes()
                        << " bytes, Send delta: " << send_delta.ms()
                        << " ms, Recv delta: " << recv_delta.ms()
                        << " ms, Network delay delta: " << delta_ms
                        << " ms, Size delta: " << size_delta
                        << " bytes, Audio: " << (packet_feedback.sent_packet.audio ? "yes" : "no");
  } else {
    RTC_LOG(LS_VERBOSE) << "[DelayBWE-Packet] Deltas not calculated for packet at "
                        << packet_feedback.receive_time.ms() << " ms";
  }

  delay_detector_for_packet->Update(recv_delta.ms<double>(),
                                    send_delta.ms<double>(),
                                    packet_feedback.sent_packet.send_time.ms(),
                                    packet_feedback.receive_time.ms(),
                                    packet_size.bytes(), calculated_deltas);
}

DataRate DelayBasedBwe::TriggerOveruse(Timestamp at_time,
                                       std::optional<DataRate> link_capacity) {
  RTC_LOG(LS_INFO) << "[DelayBWE-TriggerOveruse] Manually triggering overuse. "
                   << "Time: " << at_time.ms() << " ms, Link capacity: " 
                   << (link_capacity ? link_capacity->bps() : -1) << " bps";
  
  RateControlInput input(BandwidthUsage::kBwOverusing, link_capacity);
  DataRate result = rate_control_.Update(input, at_time);
  
  RTC_LOG(LS_INFO) << "[DelayBWE-TriggerOveruse] New bitrate after manual overuse: " 
                   << result.bps() << " bps";
  
  return result;
}

DelayBasedBwe::Result DelayBasedBwe::MaybeUpdateEstimate(
    std::optional<DataRate> acked_bitrate,
    std::optional<DataRate> probe_bitrate,
    std::optional<NetworkStateEstimate> /* state_estimate */,
    bool recovered_from_overuse,
    bool /* in_alr */,
    Timestamp at_time) {
  Result result;
  
  BandwidthUsage current_state = active_delay_detector_->State();

  // Currently overusing the bandwidth.
  if (current_state == BandwidthUsage::kBwOverusing) {
    RTC_LOG(LS_INFO) << "[DelayBWE-Overusing] Handling overuse state";
    
    if (acked_bitrate &&
        rate_control_.TimeToReduceFurther(at_time, *acked_bitrate)) {
      RTC_LOG(LS_INFO) << "[DelayBWE-Overusing] Time to reduce further with acked bitrate "
                       << acked_bitrate->bps() << " bps";
      result.updated =
          UpdateEstimate(at_time, acked_bitrate, &result.target_bitrate);
    } else if (!acked_bitrate && rate_control_.ValidEstimate() &&
               rate_control_.InitialTimeToReduceFurther(at_time)) {
      // Overusing before we have a measured acknowledged bitrate. Reduce send
      // rate by 50% every 200 ms.
      // TODO(tschumim): Improve this and/or the acknowledged bitrate estimator
      // so that we (almost) always have a bitrate estimate.
      DataRate old_estimate = rate_control_.LatestEstimate();
      rate_control_.SetEstimate(old_estimate / 2, at_time);
      result.updated = true;
      result.probe = false;
      result.target_bitrate = rate_control_.LatestEstimate();
      
      RTC_LOG(LS_INFO) << "[DelayBWE-Overusing] No acked bitrate, emergency reduction. "
                       << "Old: " << old_estimate.bps() << " bps, New: " 
                       << result.target_bitrate.bps() << " bps";
    } else {
      RTC_LOG(LS_INFO) << "[DelayBWE-Overusing] No action taken. "
                       << "Has acked bitrate: " << (acked_bitrate ? "yes" : "no")
                       << ", Time to reduce: " << (acked_bitrate ? 
                          (rate_control_.TimeToReduceFurther(at_time, *acked_bitrate) ? "yes" : "no") : "N/A")
                       << ", Valid estimate: " << (rate_control_.ValidEstimate() ? "yes" : "no");
    }
  } else {
    if (probe_bitrate) {
      result.probe = true;
      result.updated = true;
      DataRate old_estimate = rate_control_.ValidEstimate() ? rate_control_.LatestEstimate() : DataRate::Zero();
      rate_control_.SetEstimate(*probe_bitrate, at_time);
      result.target_bitrate = rate_control_.LatestEstimate();
      
      RTC_LOG(LS_INFO) << "[DelayBWE-Probe] Using probe result. "
                       << "Probe bitrate: " << probe_bitrate->bps() 
                       << " bps, Old estimate: " << old_estimate.bps()
                       << " bps, New target: " << result.target_bitrate.bps() << " bps";
    } else {
      // Normal update - detailed info in BWE-DECISION log
      result.updated =
          UpdateEstimate(at_time, acked_bitrate, &result.target_bitrate);
      result.recovered_from_overuse = recovered_from_overuse;
      
      if (recovered_from_overuse) {
        RTC_LOG(LS_INFO) << "[DelayBWE-Recovery] Recovered from overuse, may trigger probing";
      }
    }
  }
  BandwidthUsage detector_state = active_delay_detector_->State();
  if ((result.updated && prev_bitrate_ != result.target_bitrate) ||
      detector_state != prev_state_) {
    DataRate bitrate = result.updated ? result.target_bitrate : prev_bitrate_;

    if (event_log_) {
      event_log_->Log(std::make_unique<RtcEventBweUpdateDelayBased>(
          bitrate.bps(), detector_state));
    }

    RTC_LOG(LS_INFO) << "[" << GetWallClockTimestampString() << "]"
                     << " [DelayBWE-Decision] MonoTime: " << at_time.ms()
                     << " ms, Detector state: " << detector_state
                     << ", Old bitrate: " << prev_bitrate_.bps()
                     << " bps, New bitrate: " << bitrate.bps()
                     << " bps, Updated: " << (result.updated ? "yes" : "no")
                     << ", Probe: " << (result.probe ? "yes" : "no");

    prev_bitrate_ = bitrate;
    prev_state_ = detector_state;
  }

  result.delay_detector_state = detector_state;
  return result;
}

bool DelayBasedBwe::UpdateEstimate(Timestamp at_time,
                                   std::optional<DataRate> acked_bitrate,
                                   DataRate* target_rate) {
  const RateControlInput input(active_delay_detector_->State(), acked_bitrate);
  DataRate old_target = *target_rate;
  *target_rate = rate_control_.Update(input, at_time);
  bool valid = rate_control_.ValidEstimate();
  
  // 确定BWE状态
  const char* bw_state_str = "Unknown";
  switch (input.bw_state) {
    case BandwidthUsage::kBwNormal: bw_state_str = "Normal"; break;
    case BandwidthUsage::kBwOverusing: bw_state_str = "Overusing"; break;
    case BandwidthUsage::kBwUnderusing: bw_state_str = "Underusing"; break;
    default: bw_state_str = "Unknown"; break;
  }
  
  // 获取AIMD策略详情
  auto strategy_info = rate_control_.GetLastStrategyInfo();
  
  // 综合BWE决策日志
  RTC_LOG(LS_INFO) << "[" << GetWallClockTimestampString() << "]" << " [BWE-DECISION] MonoTime: " << at_time.ms() << " ms"
                   << ", BWState: " << bw_state_str 
                   << ", Strategy: " << strategy_info.strategy_name
                   << ", Params: [" << strategy_info.parameters << "]"
                   << ", AckedBitrate: " << (acked_bitrate ? acked_bitrate->bps() : -1) << " bps"
                   << ", OldTarget: " << old_target.bps() << " bps"
                   << ", NewTarget: " << target_rate->bps() << " bps"
                   << ", Change: " << (target_rate->bps() - old_target.bps()) << " bps"
                   << ", Valid: " << (valid ? "yes" : "no");
  
  return valid;
}

void DelayBasedBwe::OnRttUpdate(TimeDelta avg_rtt) {
  rate_control_.SetRtt(avg_rtt);
}

bool DelayBasedBwe::LatestEstimate(std::vector<uint32_t>* ssrcs,
                                   DataRate* bitrate) const {
  // Currently accessed from both the process thread (see
  // ModuleRtpRtcpImpl::Process()) and the configuration thread (see
  // Call::GetStats()). Should in the future only be accessed from a single
  // thread.
  RTC_DCHECK(ssrcs);
  RTC_DCHECK(bitrate);
  if (!rate_control_.ValidEstimate())
    return false;

  *ssrcs = {kFixedSsrc};
  *bitrate = rate_control_.LatestEstimate();
  return true;
}

void DelayBasedBwe::SetStartBitrate(DataRate start_bitrate) {
  RTC_LOG(LS_INFO) << "BWE Setting start bitrate to: "
                   << ToString(start_bitrate);
  rate_control_.SetStartBitrate(start_bitrate);
}

void DelayBasedBwe::SetMinBitrate(DataRate min_bitrate) {
  // Called from both the configuration thread and the network thread. Shouldn't
  // be called from the network thread in the future.
  RTC_LOG(LS_INFO) << "[DelayBWE-Config] Setting minimum bitrate to: " 
                   << min_bitrate.bps() << " bps";
  rate_control_.SetMinBitrate(min_bitrate);
}

TimeDelta DelayBasedBwe::GetExpectedBwePeriod() const {
  return rate_control_.GetExpectedBandwidthPeriod();
}

void DelayBasedBwe::UpdateCellularResourceRatio(double ratio, Timestamp at_time) {
  // Log the received data
  RTC_LOG(LS_INFO) << "================================================";
  RTC_LOG(LS_INFO) << "[DelayBWE-Cellular] ✅ DATA RECEIVED!";
  RTC_LOG(LS_INFO) << "  Ratio: " << ratio;
  RTC_LOG(LS_INFO) << "  Time: " << at_time.ms() << " ms";
  RTC_LOG(LS_INFO) << "  Status: " << (ratio < 0.5 ? "⚠️ CONGESTED" : 
                                       ratio < 0.8 ? "⚡ WARNING" : 
                                       "✅ NORMAL");
  RTC_LOG(LS_INFO) << "================================================";
  
  // Pass the ratio to AIMD rate control
  rate_control_.SetCellularResourceRatio(ratio, at_time);
  
  // Log the impact on AIMD
  RTC_LOG(LS_INFO) << "[DelayBWE-Cellular] Ratio forwarded to AIMD. "
                   << "Current estimate: " << rate_control_.LatestEstimate().bps() << " bps";
}

}  // namespace webrtc

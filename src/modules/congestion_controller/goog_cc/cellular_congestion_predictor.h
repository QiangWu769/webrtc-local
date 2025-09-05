/*
 *  Cellular Network Congestion Predictor for WebRTC
 *  Uses BSR (Buffer Status Report) ratio to predict network congestion
 */

#ifndef MODULES_CONGESTION_CONTROLLER_GOOG_CC_CELLULAR_CONGESTION_PREDICTOR_H_
#define MODULES_CONGESTION_CONTROLLER_GOOG_CC_CELLULAR_CONGESTION_PREDICTOR_H_

#include <deque>
#include <optional>

#include "api/transport/bandwidth_usage.h"
#include "api/units/data_rate.h"
#include "api/units/timestamp.h"
#include "rtc_base/race_checker.h"

namespace webrtc {

// BSR ratio thresholds for congestion prediction
struct CellularPredictorConfig {
  // Ratio = allocated_bytes / requested_bytes
  double ratio_critical_low = 0.3;     // Critical congestion (< 30% allocation)
  double ratio_warning_low = 0.5;      // Warning level (< 50% allocation)
  double ratio_normal_low = 0.8;       // Normal operation lower bound
  double ratio_normal_high = 1.2;      // Normal operation upper bound
  double ratio_high = 1.5;             // Over-provisioned (> 150% allocation)
  
  // Trend detection parameters
  double trend_window_ms = 500;        // Window for trend calculation
  double trend_threshold = -0.1;       // Negative trend threshold per second
  int min_samples_for_trend = 5;       // Minimum samples for trend detection
  
  // Smoothing parameters
  double alpha_ratio = 0.1;            // EWMA factor for ratio smoothing
  double alpha_trend = 0.2;            // EWMA factor for trend smoothing
};

// Represents a single BSR measurement
struct BsrMeasurement {
  Timestamp timestamp;
  double requested_bytes;
  double allocated_bytes;
  double ratio;  // allocated / requested
  
  BsrMeasurement(Timestamp ts, double req, double alloc)
      : timestamp(ts),
        requested_bytes(req),
        allocated_bytes(alloc),
        ratio(alloc > 0 ? alloc / req : 0) {}
};

// Predicted congestion state based on cellular info
enum class CellularCongestionState {
  kNoCellularInfo,     // No cellular data available
  kCritical,           // Severe congestion detected
  kWarning,            // Early congestion warning
  kNormal,             // Normal operation
  kOverProvisioned     // More resources than needed
};

class CellularCongestionPredictor {
 public:
  explicit CellularCongestionPredictor(const CellularPredictorConfig& config);
  ~CellularCongestionPredictor();
  
  // Update with new BSR measurement
  void UpdateBsrMeasurement(Timestamp timestamp,
                           double requested_bytes,
                           double allocated_bytes);
  
  // Get current congestion prediction
  CellularCongestionState GetCongestionState() const;
  
  // Get recommended bandwidth usage based on cellular state
  BandwidthUsage GetRecommendedBandwidthUsage() const;
  
  // Check if we should override delay-based detection
  bool ShouldOverrideDelayDetection() const;
  
  // Get current BSR ratio (smoothed)
  std::optional<double> GetCurrentRatio() const;
  
  // Get ratio trend (negative = declining allocation)
  std::optional<double> GetRatioTrend() const;
  
  // Reset all measurements
  void Reset();
  
  // Get suggested rate multiplier based on cellular state
  double GetRateMultiplier() const;
  
  // Check if early hold is recommended
  bool ShouldEnterEarlyHold() const;
  
 private:
  // Calculate trend from recent measurements
  double CalculateTrend() const;
  
  // Update smoothed values
  void UpdateSmoothedValues(const BsrMeasurement& measurement);
  
  // Detect rapid congestion onset
  bool DetectRapidCongestion() const;
  
  CellularPredictorConfig config_;
  std::deque<BsrMeasurement> measurements_;
  
  // Smoothed values
  std::optional<double> smoothed_ratio_;
  std::optional<double> smoothed_trend_;
  
  // State tracking
  CellularCongestionState current_state_ = CellularCongestionState::kNoCellularInfo;
  Timestamp last_update_time_ = Timestamp::MinusInfinity();
  
  // Rapid change detection
  int consecutive_declining_samples_ = 0;
  double peak_ratio_ = 0;
  
  rtc::RaceChecker race_checker_;
};

}  // namespace webrtc

#endif  // MODULES_CONGESTION_CONTROLLER_GOOG_CC_CELLULAR_CONGESTION_PREDICTOR_H_
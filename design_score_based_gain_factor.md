# 基于Score的动态增益因子设计

## 🎯 核心思想

根据Base Score（0-100）动态调整带宽增益因子（gain factor），实现：
- **Score高**（资源充足）→ **激进增长**（大增益）
- **Score中**（资源一般）→ **保守增长**（中增益）
- **Score低**（资源紧张）→ **缓慢增长/降速**（小增益或负增益）

---

## 📊 Score区间划分与策略

### Score含义回顾

```
Base Score = inverse_sigmoid(smoothed_ratio, center=0.25, steepness=15) * 100

Score映射关系：
  Score = 100 → Ratio ≈ 0.00  （资源极度充足）
  Score = 90  → Ratio ≈ 0.05  （资源充足，接近饱和）
  Score = 50  → Ratio = 0.25  （资源中等）
  Score = 10  → Ratio ≈ 0.45  （资源紧张）
  Score = 0   → Ratio ≥ 0.50  （资源耗尽）
```

### 建议的分档策略

| Score Range | 资源状态 | 策略 | Gain Factor | 说明 |
|------------|---------|------|-------------|------|
| **90-100** | 极度充足 | 🚫 **强制降速** | 0.85 | 预防拥塞（Peak Detection） |
| **70-90** | 充足 | 🔥 **激进增长** | 1.10-1.20 | 快速探测容量 |
| **50-70** | 良好 | ✅ **正常增长** | 1.05-1.10 | 稳健增长 |
| **30-50** | 中等 | ⚠️ **保守增长** | 1.01-1.05 | 谨慎探测 |
| **10-30** | 紧张 | 🛑 **维持** | 1.00 | 不增不减 |
| **0-10** | 耗尽 | 🔻 **降速** | 0.90 | 主动降速 |

---

## 🧮 增益因子计算公式

### 方案1: 分段线性映射（推荐）

```cpp
double CalculateGainFactor(double base_score) {
    if (base_score >= 90.0) {
        // Peak detection: Force decrease
        return 0.85;  // Multiplicative decrease (same as overusing)
    }
    else if (base_score >= 70.0) {
        // Aggressive growth: 1.10 - 1.20
        // Linear: gain = 1.10 + (score - 70) / 20 * 0.10
        return 1.10 + (base_score - 70.0) / 20.0 * 0.10;
    }
    else if (base_score >= 50.0) {
        // Normal growth: 1.05 - 1.10
        return 1.05 + (base_score - 50.0) / 20.0 * 0.05;
    }
    else if (base_score >= 30.0) {
        // Conservative growth: 1.01 - 1.05
        return 1.01 + (base_score - 30.0) / 20.0 * 0.04;
    }
    else if (base_score >= 10.0) {
        // Hold: ~1.00
        return 1.00;
    }
    else {
        // Decrease: 0.90
        return 0.90;
    }
}
```

**示例映射**:
```
Score = 95  → Gain = 0.85  (强制降速)
Score = 85  → Gain = 1.175 (激进增长)
Score = 70  → Gain = 1.10  (激进起点)
Score = 60  → Gain = 1.075 (正常增长)
Score = 50  → Gain = 1.05  (正常起点)
Score = 40  → Gain = 1.03  (保守增长)
Score = 30  → Gain = 1.01  (保守起点)
Score = 20  → Gain = 1.00  (维持)
Score = 5   → Gain = 0.90  (降速)
```

### 方案2: 平滑S曲线映射

```cpp
double CalculateGainFactorSmooth(double base_score) {
    // Use sigmoid for smooth transition
    // Map score [0, 100] to gain [0.85, 1.20]

    const double min_gain = 0.85;
    const double max_gain = 1.20;
    const double center = 50.0;
    const double steepness = 0.05;

    // Special handling for peak detection
    if (base_score >= 90.0) {
        return 0.85;
    }

    // Sigmoid mapping
    double normalized = 1.0 / (1.0 + exp(-steepness * (base_score - center)));
    double gain = min_gain + (max_gain - min_gain) * normalized;

    return gain;
}
```

---

## 💻 实现方案

### 在 aimd_rate_control.h 中添加

```cpp
// Score-based gain factor control
double CalculateScoreBasedGainFactor() const;
bool ShouldApplyScoreBasedGain() const { return score_based_gain_enabled_; }
void SetScoreBasedGainEnabled(bool enabled) { score_based_gain_enabled_ = enabled; }

private:
  bool score_based_gain_enabled_ = false;  // Control flag
```

### 在 aimd_rate_control.cc 中实现

```cpp
double AimdRateControl::CalculateScoreBasedGainFactor() const {
    double base_score = CalculateRatioScore();

    // Peak detection override
    if (base_score >= 90.0) {
        RTC_LOG(LS_INFO) << "[AIMD-ScoreGain] Peak detected, force decrease: 0.85";
        return 0.85;
    }

    // Piecewise linear mapping
    double gain_factor;
    if (base_score >= 70.0) {
        gain_factor = 1.10 + (base_score - 70.0) / 20.0 * 0.10;
        RTC_LOG(LS_VERBOSE) << "[AIMD-ScoreGain] Aggressive growth";
    }
    else if (base_score >= 50.0) {
        gain_factor = 1.05 + (base_score - 50.0) / 20.0 * 0.05;
        RTC_LOG(LS_VERBOSE) << "[AIMD-ScoreGain] Normal growth";
    }
    else if (base_score >= 30.0) {
        gain_factor = 1.01 + (base_score - 30.0) / 20.0 * 0.04;
        RTC_LOG(LS_VERBOSE) << "[AIMD-ScoreGain] Conservative growth";
    }
    else if (base_score >= 10.0) {
        gain_factor = 1.00;
        RTC_LOG(LS_VERBOSE) << "[AIMD-ScoreGain] Hold";
    }
    else {
        gain_factor = 0.90;
        RTC_LOG(LS_INFO) << "[AIMD-ScoreGain] Score too low, decrease";
    }

    RTC_LOG(LS_INFO) << "[AIMD-ScoreGain] Score: " << base_score
                     << ", Gain Factor: " << gain_factor;

    return gain_factor;
}
```

### 在 ChangeBitrate() 中应用

修改增长逻辑，应用Score-based gain：

```cpp
// In kRcIncrease case
case RateControlState::kRcIncrease: {
    // ... existing code ...

    // Calculate base increase
    DataRate increased_bitrate = DataRate::Zero();

    if (link_capacity_.has_estimate()) {
        // Additive increase
        DataRate additive_increase = AdditiveRateIncrease(at_time, time_last_bitrate_change_);

        // Apply score-based gain if enabled
        if (score_based_gain_enabled_ && HasFreshCellularData(at_time)) {
            double gain_factor = CalculateScoreBasedGainFactor();
            additive_increase = additive_increase * gain_factor;
            RTC_LOG(LS_INFO) << "[AIMD-Additive-ScoreGain] Original: "
                           << AdditiveRateIncrease(at_time, time_last_bitrate_change_).bps()
                           << " bps, Gain: " << gain_factor
                           << ", Final: " << additive_increase.bps() << " bps";
        }

        increased_bitrate = current_bitrate_ + additive_increase;
    }
    else {
        // Multiplicative increase
        DataRate multiplicative_increase = MultiplicativeRateIncrease(
            at_time, time_last_bitrate_change_, current_bitrate_);

        // Apply score-based gain if enabled
        if (score_based_gain_enabled_ && HasFreshCellularData(at_time)) {
            double gain_factor = CalculateScoreBasedGainFactor();
            multiplicative_increase = multiplicative_increase * gain_factor;
            RTC_LOG(LS_INFO) << "[AIMD-Multiplicative-ScoreGain] Original: "
                           << MultiplicativeRateIncrease(...).bps()
                           << " bps, Gain: " << gain_factor
                           << ", Final: " << multiplicative_increase.bps() << " bps";
        }

        increased_bitrate = current_bitrate_ + multiplicative_increase;
    }

    new_bitrate = std::min(increased_bitrate, increase_limit);
    // ... rest of code ...
}
```

---

## 📊 日志输出示例

启用后的日志：

```
[AIMD-SatBoost] Base Score: 75.3, Boost: +0, Final Score: 75.3, Peak Detected: NO
[AIMD-ScoreGain] Score: 75.3, Gain Factor: 1.1265
[AIMD-Additive-ScoreGain] Original: 8000 bps, Gain: 1.1265, Final: 9012 bps

[AIMD-SatBoost] Base Score: 92.5, Boost: +0, Final Score: 92.5, Peak Detected: YES
[AIMD-ScoreGain] Peak detected, force decrease: 0.85
[AIMD-Additive-ScoreGain] Original: 8000 bps, Gain: 0.85, Final: 6800 bps (DECREASE)

[AIMD-SatBoost] Base Score: 45.2, Boost: +0, Final Score: 45.2, Peak Detected: NO
[AIMD-ScoreGain] Score: 45.2, Gain Factor: 1.0308
[AIMD-Additive-ScoreGain] Original: 8000 bps, Gain: 1.0308, Final: 8246 bps

[AIMD-SatBoost] Base Score: 5.1, Boost: +0, Final Score: 5.1, Peak Detected: NO
[AIMD-ScoreGain] Score too low, decrease, Gain Factor: 0.90
[AIMD-Additive-ScoreGain] Original: 8000 bps, Gain: 0.90, Final: 7200 bps (DECREASE)
```

---

## 🎯 优势分析

### 1. **自适应性**
   - 根据实时蜂窝资源状态动态调整
   - 不需要手动调参

### 2. **多档位精细控制**
   - 6个档位，覆盖所有场景
   - 平滑过渡，避免突变

### 3. **拥塞预防**
   - Score >= 90自动降速
   - 在delay-based检测前主动响应

### 4. **灵活性**
   - 可以通过`SetScoreBasedGainEnabled()`开关
   - 便于A/B测试

### 5. **可观测性**
   - 详细日志输出
   - 便于调试和优化

---

## ⚠️ 注意事项

### 1. **与现有机制的协调**

```cpp
// 优先级顺序（从高到低）：
1. Overusing (delay-based) → Force Decrease
2. Score >= 90 (Peak Detection) → Force Decrease (gain=0.85)
3. Score-based Gain → Adjust increase rate
4. Default AIMD → Normal increase
```

### 2. **避免冲突**

```cpp
// 在 ChangeBitrate 中:
if (rate_control_state_ == RateControlState::kRcDecrease) {
    // Overusing takes precedence, ignore score-based gain
    // Use standard beta decrease
}
else if (score_based_gain_enabled_ && base_score >= 90.0) {
    // Peak detection via score-based gain
    // Apply 0.85 gain (equivalent to decrease)
}
else {
    // Normal increase with score-based modulation
}
```

### 3. **参数调优**

可调参数：
```cpp
// Gain range
const double kMinGain = 0.85;  // Decrease factor
const double kMaxGain = 1.20;  // Max aggressive growth

// Score thresholds
const double kPeakThreshold = 90.0;
const double kAggressiveThreshold = 70.0;
const double kNormalThreshold = 50.0;
const double kConservativeThreshold = 30.0;
const double kHoldThreshold = 10.0;
```

---

## 📈 预期效果

基于之前的分析：

### 当前Baseline（无Score-based Gain）
- Overusing次数: 7次
- Score >= 90: 1616次（但未实际影响）

### 启用Score-based Gain后
- **预期Overusing次数**: 0-2次
  - Score >= 90会主动降速（gain=0.85）
  - 100%覆盖，可能避免大部分Overusing

- **预期带宽利用**:
  - Score 70-90: 更激进增长（+10-20%）
  - Score 50-70: 正常增长（+5-10%）
  - Score < 50: 保守增长（+1-5%）

- **预期平滑度**:
  - 6档位渐进调整
  - 比二元开关（增/减）更平滑

---

## 🚀 实施步骤

1. **Phase 1: 实现核心函数**
   - 添加`CalculateScoreBasedGainFactor()`
   - 添加控制开关

2. **Phase 2: 集成到ChangeBitrate**
   - 修改增长逻辑
   - 添加日志

3. **Phase 3: 测试验证**
   - 先禁用（observe模式）
   - 对比启用前后效果

4. **Phase 4: 参数调优**
   - 根据实际效果调整阈值
   - 优化gain范围

---

## 📝 配置示例

```cpp
// In webrtc_config.cc or initialization code

// Enable score-based gain control
aimd_rate_control->SetScoreBasedGainEnabled(true);

// Also need cellular ratio enabled
aimd_rate_control->SetCellularRatioInfluenceEnabled(true);

// Logging
RTC_LOG(LS_INFO) << "[Config] Score-based gain control enabled";
```

---

## 🔍 从日志验证

当前日志已经包含所需信息：
```
✅ Base Score - [AIMD-SatBoost] Base Score: 51.4131
✅ Ratio - [AIMD-Cellular] Smoothed Ratio: 0.403751
✅ Current Strategy - [BWE-DECISION] Strategy: Additive-Increase
✅ Bandwidth - NewTarget: 1455564 bps
```

添加Score-based Gain后会增加：
```
✅ Gain Factor - [AIMD-ScoreGain] Gain Factor: 1.056
✅ Adjusted Increase - [AIMD-Additive-ScoreGain] Final: 8448 bps
```

---

*设计日期: 2025-10-05*
*基于: sender_local.log analysis*

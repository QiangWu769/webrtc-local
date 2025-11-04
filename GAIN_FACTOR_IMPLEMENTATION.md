# Gain Factor Implementation Summary

## 概述 (Overview)

实现了基于 Cellular Resource Ratio Score 的动态增益因子策略，用于控制 WebRTC 的带宽增长速率。

Implemented a dynamic gain factor strategy based on Cellular Resource Ratio Score to control WebRTC bandwidth growth rate.

---

## 核心设计原理 (Core Design Philosophy)

### 逆向逻辑 (Inverse Logic)

```
Low Ratio (0.1)  →  High Score (100)  →  Gain = 0.0  →  STOP growth
                     (Network saturated)

High Ratio (0.9) →  Low Score (0)     →  Gain = 2.0  →  Aggressive growth
                     (Network idle)
```

**Why?**
- **Low ratio** = 分配资源 << 请求资源 = 网络繁忙/高带宽 → 应该**减速/停止**增长（避免拥塞）
- **High ratio** = 分配资源 >= 请求资源 = 网络空闲/低带宽 → 应该**加速**增长（利用容量）

---

## 五档增益策略 (5-Tier Gain Factor Strategy)

| Score Range | Network State | Gain Factor | Interpretation | Sample Count (%) |
|------------|---------------|-------------|----------------|------------------|
| **[90-100]** | 饱和/Saturated | **0.0×** | **停止增长** (STOP) | 43.3% |
| **[70-90)** | 高利用/High | **0.5×** | **保守增长** (Conservative) | 14.9% |
| **[50-70)** | 中等/Moderate | **1.0×** | **正常增长** (Normal) | 5.6% |
| **[20-50)** | 低利用/Low | **1.5×** | **激进增长** (Aggressive) | 7.0% |
| **[0-20)** | 极低/Very Low | **2.0×** | **极激进增长** (Very Aggressive) | 29.2% |

*数据基于 sender_local.log (17,404 samples)*

---

## 实现细节 (Implementation Details)

### 1. C++ 函数

#### `GetGainFactorFromScore()`
[aimd_rate_control.cc:861-878](src/modules/remote_bitrate_estimator/aimd_rate_control.cc#L861-L878)

```cpp
double AimdRateControl::GetGainFactorFromScore(double score) const {
  if (score >= 90.0) {
    return 0.0;  // [90-100]: Stop growth
  } else if (score >= 70.0) {
    return 0.5;  // [70-90): Conservative
  } else if (score >= 50.0) {
    return 1.0;  // [50-70): Normal (default)
  } else if (score >= 20.0) {
    return 1.5;  // [20-50): Aggressive
  } else {
    return 2.0;  // [0-20): Very aggressive
  }
}
```

#### `GetNearMaxIncreaseRateBpsPerSecond()` 修改
[aimd_rate_control.cc:233-266](src/modules/remote_bitrate_estimator/aimd_rate_control.cc#L233-L266)

```cpp
double AimdRateControl::GetNearMaxIncreaseRateBpsPerSecond() const {
  // ... [原有计算 base_increase_rate_bps_per_second] ...

  // Apply gain factor based on cellular ratio score
  if (cellular_ratio_influence_enabled_ && ratio_smoother_.IsInitialized()) {
    double ratio_score = CalculateRatioScore();
    double gain_factor = GetGainFactorFromScore(ratio_score);

    double adjusted_rate = base_increase_rate_bps_per_second * gain_factor;

    RTC_LOG(LS_INFO) << "[AIMD-GainFactor] Score: " << ratio_score
                     << ", Gain: " << gain_factor
                     << ", Base rate: " << base_increase_rate_bps_per_second
                     << " bps/s, Adjusted rate: " << adjusted_rate << " bps/s";

    return adjusted_rate;
  }

  return base_increase_rate_bps_per_second;
}
```

### 2. 头文件声明

[aimd_rate_control.h:199](src/modules/remote_bitrate_estimator/aimd_rate_control.h#L199)

```cpp
double GetGainFactorFromScore(double score) const;  // Get gain factor based on score range
```

---

## 示例计算 (Example Calculations)

### Scenario 1: 网络饱和 (Network Saturated)
```
Ratio: 0.1 (10%)
  ↓
Score: 99.8  (inverse sigmoid)
  ↓
Gain: 0.0×
  ↓
Base Rate: 10,000 bps/s  →  Effective Rate: 0 bps/s
```
**结果**: 停止增长，避免拥塞

---

### Scenario 2: 中等利用 (Moderate Utilization)
```
Ratio: 0.5 (50%)
  ↓
Score: 50.0  (sigmoid center)
  ↓
Gain: 1.0×
  ↓
Base Rate: 10,000 bps/s  →  Effective Rate: 10,000 bps/s
```
**结果**: 正常增长速率

---

### Scenario 3: 网络空闲 (Network Idle)
```
Ratio: 0.7 (70%)
  ↓
Score: 4.7  (very low)
  ↓
Gain: 2.0×
  ↓
Base Rate: 10,000 bps/s  →  Effective Rate: 20,000 bps/s
```
**结果**: 双倍增长速率，快速利用容量

---

## 对比原始策略 (Comparison with Original)

| Aspect | 原始策略 (Original) | 新策略 (New with Gain Factor) |
|--------|---------------------|-------------------------------|
| **增长速率** | 固定 (Fixed) | 动态调整 (Dynamic: 0-2× base) |
| **响应性** | 被动 (Reactive) | 主动 (Proactive) |
| **网络饱和处理** | 等待 Overuse 信号 | 提前停止增长 (Gain=0) |
| **网络空闲处理** | 固定慢速增长 | 双倍速度增长 (Gain=2) |
| **Ratio 利用** | 仅用于策略选择 | 直接控制增长速率 |

---

## 日志示例 (Log Example)

```
[AIMD-Cellular] Raw Ratio: 0.375, Smoothed Ratio: 0.387
[AIMD-SatBoost] Base Score: 88.9, Peak Detected: NO
[AIMD-GainFactor] Score: 88.9, Gain: 0.5, Base rate: 8500 bps/s, Adjusted rate: 4250 bps/s
[AIMD-Additive] Base increase: 1020 bps, Near max rate: 4250 bps/s, Time delta: 240 ms
```

**解读**:
- Ratio 0.387 → Score 88.9
- Score 88.9 → Gain 0.5× (保守增长)
- Base rate 8500 → Adjusted 4250 bps/s
- 最终增长: 1020 bps (240ms × 4250bps/s)

---

## 可视化 (Visualization)

运行可视化脚本:
```bash
python3 visualize_gain_factor_strategy.py
```

生成 `gain_factor_strategy_visualization.png` 包含:
1. **Ratio → Score 映射** (Inverse Sigmoid)
2. **Score → Gain Factor 策略**
3. **Ratio → Effective Increase Rate**
4. **策略总结表格**

---

## 调参建议 (Tuning Recommendations)

### 当前参数 (Current Parameters)
```cpp
// Sigmoid parameters
const double center = 0.5;      // ratio=0.5 → score=50
const double steepness = 15.0;  // Sharp transitions

// Gain factor thresholds
score >= 90.0  →  gain = 0.0
score >= 70.0  →  gain = 0.5
score >= 50.0  →  gain = 1.0
score >= 20.0  →  gain = 1.5
score <  20.0  →  gain = 2.0
```

### 调整方向 (Tuning Directions)

#### 如果带宽增长过慢 (If growth too slow):
- 降低 Score 阈值: `90 → 85`, `70 → 60`
- 提高增益因子: `0.5 → 0.7`, `1.5 → 2.0`, `2.0 → 3.0`

#### 如果带宽增长过快/拥塞 (If growth too fast/congestion):
- 提高 Score 阈值: `90 → 95`, `70 → 80`
- 降低增益因子: `2.0 → 1.5`, `1.5 → 1.2`

#### 如果想更早停止增长 (If want to stop growth earlier):
- 降低 STOP 阈值: `90 → 85` 或 `80`

---

## 与其他策略的配合 (Integration with Other Strategies)

### 1. **与 Cellular Ratio 策略配合**
- **ShouldForceMultiplicativeIncrease()**: 当 ratio > 0.8 且连续上升时
  - 强制 multiplicative growth (α=1.08)
  - Gain factor 不影响 multiplicative，仅影响 additive

### 2. **与 Saturation Boost 配合**
- **IsPeakDetected()**: 当 boosted score ≥ 90
  - Peak detection 触发时，gain factor = 0.0
  - 双重保护防止拥塞

### 3. **与 CUSUM 配合**
- **CUSUM Congestion Alert**: 独立的 5% 降速
  - Gain factor 控制增速
  - CUSUM 控制减速
  - 互补作用

---

## 测试建议 (Testing Recommendations)

### 1. **基准测试 (Baseline Test)**
```bash
# 禁用 Gain Factor 运行基准
cellular_ratio_influence_enabled_ = false
# 记录: 带宽增长速度、RTT、丢包率、吞吐量
```

### 2. **Gain Factor 测试**
```bash
# 启用 Gain Factor
cellular_ratio_influence_enabled_ = true
# 对比: 与基准测试的差异
```

### 3. **关键指标 (Key Metrics)**
- **带宽稳定性**: 减少震荡次数
- **拥塞避免**: 减少 Overuse 信号
- **利用率**: 网络空闲时增长速度
- **响应速度**: 从空闲到饱和的时间

---

## 编译与运行 (Build and Run)

```bash
# 编译
cd /home/wuq/webrtc-local
ninja -C src/out/Default peerconnection_client

# 运行测试
cd webrtc_config_results
bash test_local_client.sh

# 查看日志
grep "AIMD-GainFactor" sender_local.log
```

---

## 文件清单 (File Checklist)

- ✅ [aimd_rate_control.h](src/modules/remote_bitrate_estimator/aimd_rate_control.h) - 函数声明
- ✅ [aimd_rate_control.cc](src/modules/remote_bitrate_estimator/aimd_rate_control.cc) - 函数实现
- ✅ [visualize_gain_factor_strategy.py](visualize_gain_factor_strategy.py) - 可视化脚本
- ✅ [GAIN_FACTOR_IMPLEMENTATION.md](GAIN_FACTOR_IMPLEMENTATION.md) - 本文档

---

## 下一步 (Next Steps)

1. **运行测试**: 收集 Gain Factor 影响的实际数据
2. **分析日志**: 对比带宽增长曲线
3. **调优参数**: 根据实际效果调整阈值和增益
4. **性能对比**: 与原始策略对比延迟、吞吐量、稳定性

---

*实现完成时间: 2025-10-05*
*作者: Claude (claude-sonnet-4-5)*

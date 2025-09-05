# WebRTC Delay-Based Bandwidth Estimation (BWE) Deep Analysis

## Overview

WebRTC的Delay-Based BWE是一个基于包到达延迟的拥塞控制机制。通过监测发送端和接收端的时间差变化，系统能够检测网络拥塞状态并动态调整发送速率。

## 核心组件与流程

### 1. InterArrival Delta 计算 (inter_arrival_delta.cc)

**功能**: 计算包组之间的发送时间差和接收时间差

```cpp
bool InterArrivalDelta::ComputeDeltas() {
    // 1. 包组划分逻辑
    // - 使用5ms的时间窗口进行分组 (kSendTimeGroupLength)
    // - 同一组内的包共享时间戳
    
    // 2. 突发包检测 (BelongsToBurst)
    // - 如果传播延迟减少且到达时间差 < 5ms
    // - 且总突发时长 < 100ms
    // - 则认为属于同一突发
    
    // 3. 计算增量
    send_time_delta = current_group.send_time - prev_group.send_time
    arrival_time_delta = current_group.complete_time - prev_group.complete_time
    
    // 4. 异常检测
    // - 如果arrival_time_delta < 0: 包重排序
    // - 如果差值 > 阈值: 时钟偏移
}
```

**关键参数**:
- `kBurstDeltaThreshold`: 5ms - 突发包时间阈值
- `kMaxBurstDuration`: 100ms - 最大突发持续时间
- `kArrivalTimeOffsetThreshold`: 3000ms - 时钟偏移阈值

### 2. TrendlineEstimator (trendline_estimator.cc)

**功能**: 通过线性回归分析延迟趋势

```cpp
void TrendlineEstimator::UpdateTrendline() {
    // 1. 计算网络延迟增量
    delta_ms = recv_delta_ms - send_delta_ms;
    
    // 2. 平滑延迟 (指数加权移动平均)
    accumulated_delay_ += delta_ms;
    smoothed_delay_ = 0.9 * smoothed_delay_ + 0.1 * accumulated_delay_;
    
    // 3. 线性回归计算斜率
    // 窗口大小: 20个包 (默认)
    trend = LinearFitSlope(delay_hist_);
    // trend > 0: 队列增长
    // trend = 0: 稳定
    // trend < 0: 队列排空
}
```

**检测状态机**:
```cpp
void TrendlineEstimator::Detect() {
    // 修正趋势值
    modified_trend = min(num_deltas, 60) * trend * 4.0;
    
    if (modified_trend > threshold_) {
        // 过载检测
        time_over_using_ += ts_delta;
        overuse_counter_++;
        
        if (time_over_using_ > 10ms && 
            overuse_counter_ > 1 && 
            trend >= prev_trend_) {
            hypothesis_ = kBwOverusing;
        }
    } else if (modified_trend < -threshold_) {
        hypothesis_ = kBwUnderusing;
    } else {
        hypothesis_ = kBwNormal;
    }
}
```

**自适应阈值**:
```cpp
void UpdateThreshold() {
    // 动态调整检测阈值
    k = |modified_trend| < threshold ? k_down(0.039) : k_up(0.0087);
    threshold += k * (|modified_trend| - threshold) * time_delta;
    // 阈值范围: [6ms, 600ms]
}
```

### 3. AIMD Rate Control (aimd_rate_control.cc)

**功能**: 基于检测状态调整码率

#### 3.1 Multiplicative Decrease (乘法减少)

```cpp
case kRcDecrease: {
    // 基础计算: 测量吞吐量 × β
    decreased_bitrate = acked_bitrate * 0.85;
    
    // 安全边际
    if (decreased_bitrate > 5kbps) {
        decreased_bitrate -= 5kbps;
    }
    
    // 链路容量检查
    if (decreased_bitrate > current_bitrate) {
        // 使用链路容量估计
        decreased_bitrate = 0.85 * link_capacity.estimate();
    }
    
    // 应用降速
    if (decreased_bitrate < current_bitrate) {
        new_bitrate = decreased_bitrate;
        last_decrease = current_bitrate - new_bitrate;
        
        // 更新链路容量估计
        link_capacity.OnOveruseDetected(acked_bitrate);
    }
    
    // 进入保持状态
    rate_control_state = kRcHold;
}
```

#### 3.2 Additive Increase (加法增长)

当有链路容量估计时使用保守的加法增长:

```cpp
if (link_capacity.has_estimate()) {
    // 1. 帧分析 (30fps)
    frame_size = current_bitrate / 30;
    packets_per_frame = ceil(frame_size / 1200);
    avg_packet_size = frame_size / packets_per_frame;
    
    // 2. 响应时间计算
    response_time = 2 * (RTT + 100ms);
    
    // 3. 增长速率
    increase_rate = avg_packet_size / response_time;
    increase_rate = max(increase_rate, 4000) bps/s;
    
    // 4. 基于时间的增长
    increase = increase_rate * time_period;
    new_bitrate = current_bitrate + increase;
    
    // 5. 应用限制
    new_bitrate = min(new_bitrate, 1.5 * acked_bitrate + 10kbps);
}
```

#### 3.3 Multiplicative Increase (乘法增长)

无链路容量估计时使用激进的乘法增长:

```cpp
if (!link_capacity.has_estimate()) {
    // 指数增长因子
    alpha = 1.08;  // 每秒8%增长
    alpha = pow(alpha, min(time_delta, 1.0));
    
    // 计算增量
    increase = current_bitrate * (alpha - 1.0);
    increase = max(increase, 1000) bps;
    
    // 应用增长
    new_bitrate = current_bitrate + increase;
    
    // 限制检查
    new_bitrate = min(new_bitrate, 1.5 * acked_bitrate + 10kbps);
}
```

### 4. LinkCapacityEstimator (link_capacity_estimator.cc)

**功能**: 估计链路容量并提供上下界

```cpp
class LinkCapacityEstimator {
    // EWMA估计器
    void Update(DataRate capacity_sample, double alpha) {
        if (!estimate_kbps_.has_value()) {
            estimate_kbps_ = sample_kbps;
        } else {
            // 指数加权移动平均
            estimate_kbps_ = (1 - alpha) * estimate_kbps_ + alpha * sample_kbps;
        }
        
        // 计算方差
        error_kbps = estimate_kbps_ - sample_kbps;
        deviation_kbps_ = (1 - alpha) * deviation_kbps_ + 
                         alpha * error_kbps * error_kbps / norm;
        
        // 限制方差范围 [0.4, 2.5]
        deviation_kbps_ = clamp(deviation_kbps_, 0.4, 2.5);
    }
    
    // 上界: estimate + 3σ
    DataRate UpperBound() {
        return estimate + 3 * sqrt(deviation * estimate);
    }
    
    // 下界: estimate - 3σ
    DataRate LowerBound() {
        return max(0, estimate - 3 * sqrt(deviation * estimate));
    }
}
```

**更新触发**:
- `OnOveruseDetected`: α = 0.05 (慢速更新)
- `OnProbeRate`: α = 0.5 (快速更新)

### 5. 重置机制

系统有两个关键的重置触发点：

#### 5.1 下界检查重置
```cpp
// 在AIMD降速时
if (estimated_throughput < link_capacity_.LowerBound()) {
    // 当前吞吐量远低于链路容量估计
    // 说明网络严重恶化，模型不再可靠
    link_capacity_.Reset();
}
```

#### 5.2 上界检查重置
```cpp
// 在AIMD增速时
if (estimated_throughput > link_capacity_.UpperBound()) {
    // 当前吞吐量远高于链路容量估计
    // 说明网络条件大幅改善
    link_capacity_.Reset();
}
```

重置后的影响：
- `has_estimate()` 返回 false
- 下次增速时使用乘法增长而非加法增长
- 允许快速探测新的网络容量

## 状态转换流程

```
输入包反馈 
    ↓
InterArrival计算时间差
    ↓
TrendlineEstimator分析趋势
    ↓
检测网络状态(Normal/Underusing/Overusing)
    ↓
AIMD控制器调整码率
    ├── Overusing → Decrease (乘法减少)
    ├── Normal → Increase (加法/乘法增长)
    └── Underusing → Hold (保持)
    ↓
更新LinkCapacityEstimator
    ↓
输出新目标码率
```

## 关键参数总结

| 组件 | 参数 | 默认值 | 说明 |
|------|------|--------|------|
| InterArrival | send_time_group_length | 5ms | 包组时间窗口 |
| TrendlineEstimator | window_size | 20 | 延迟历史窗口大小 |
| | smoothing_coef | 0.9 | 延迟平滑系数 |
| | threshold_gain | 4.0 | 趋势增益因子 |
| | overusing_time_threshold | 10ms | 过载时间阈值 |
| | initial_threshold | 12.5ms | 初始检测阈值 |
| | k_up/k_down | 0.0087/0.039 | 阈值调整速率 |
| AIMD | beta | 0.85 | 降速因子 |
| | alpha | 1.08 | 增速因子(每秒) |
| | min_increase_rate | 4000 bps/s | 最小增速 |
| LinkCapacity | overuse_alpha | 0.05 | 过载时更新率 |
| | probe_alpha | 0.5 | 探测时更新率 |
| | deviation_range | [0.4, 2.5] | 方差范围 |

## 算法特点

1. **自适应性**: 通过动态阈值和链路容量估计适应不同网络条件
2. **双模式增长**: 有/无链路容量估计时分别使用加法/乘法增长
3. **安全机制**: 多重检查防止过激调整
4. **快速恢复**: 重置机制允许快速适应网络变化
5. **抗抖动**: 通过平滑和状态机减少码率震荡

## 优化建议

1. **参数调优**: 可根据具体网络环境调整阈值和增减速因子
2. **探测优化**: 在网络改善时可增加主动探测频率
3. **音视频分离**: 利用separate_audio机制优化混合流场景
4. **ALR处理**: 在应用受限区域可采用更保守的策略
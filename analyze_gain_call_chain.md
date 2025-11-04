# Gain Factor 调用链分析

## 完整调用流程

```
1. UpdateCellularResourceRatio(ratio)  [aimd_rate_control.cc:617-645]
   ├─ 接收原始 ratio
   ├─ 平滑处理: smoothed_cellular_ratio_ = α × ratio + (1-α) × old
   └─ 记录日志: [AIMD-Cellular] Resource ratio updated

2. GetAdditiveIncreaseRateBpsPerSecond(...)  [aimd_rate_control.cc:228-273]
   ├─ 计算基础增长率: base_increase_rate_bps_per_second
   ├─ if (smoothed_cellular_ratio_ > 0):
   │   ├─ gain_factor = GetGainFactorFromRatio(smoothed_cellular_ratio_)  ← 这里！
   │   ├─ adjusted_rate = base_rate × gain_factor
   │   └─ if (cellular_ratio_influence_enabled_):
   │       └─ return adjusted_rate  [应用gain]
   └─ else: return base_rate  [不应用]

3. GetGainFactorFromRatio(ratio)  [aimd_rate_control.cc:712-720]
   ├─ 输入: smoothed_cellular_ratio_
   ├─ 计算: sigmoid函数
   │   x = (ratio - 0.4) × 5.0
   │   sigmoid = 1 / (1 + e^(-x))
   │   gain = 0.5 + 1.5 × sigmoid
   └─ 输出: gain_factor ∈ [0.5, 2.0]
```

## 关键发现

### ✅ 只需修改一个函数！

**修改位置**: `GetGainFactorFromRatio()` [aimd_rate_control.cc:712-720]

**原因**:
1. 这个函数只在**一个地方**被调用 (line 252)
2. 它的输入是 `smoothed_cellular_ratio_` (已经平滑过)
3. 它的输出直接用于计算 `adjusted_rate`

### 生效条件

修改后的gain函数**只有在以下条件满足时**才会真正生效：

```cpp
if (smoothed_cellular_ratio_ > 0) {           // 条件1: ratio必须>0
    ...
    if (cellular_ratio_influence_enabled_) {  // 条件2: 开关必须打开
        return adjusted_rate;                 // 才会应用gain
    }
}
```

### 开关状态检查

需要确保 `cellular_ratio_influence_enabled_` = true

设置方法：
```cpp
SetCellularRatioInfluenceEnabled(true);
```

## 数据流

```
原始ratio (来自网络层)
    ↓
平滑处理 (smoothed_cellular_ratio_)
    ↓
GetGainFactorFromRatio(ratio) → gain ∈ [0.5, 2.0]
    ↓
adjusted_rate = base_rate × gain
    ↓
返回调整后的增长率
```

## 总结

### ✓ 修改`GetGainFactorFromRatio`就够了

- 唯一的ratio→gain映射函数
- 调用链简单清晰
- 不需要修改其他地方

### ⚠️ 但需要确保

1. `cellular_ratio_influence_enabled_` = true (开关打开)
2. `smoothed_cellular_ratio_` > 0 (有有效ratio数据)

### 验证方法

运行后查看日志：
- 看到 `[AIMD-GainFactor] ENABLED` → 生效了 ✓
- 看到 `[AIMD-GainFactor] DISABLED` → 开关未打开 ✗

当前日志显示 "DISABLED"，说明需要启用开关！

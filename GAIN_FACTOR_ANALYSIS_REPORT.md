# 增益因子策略：实际带宽 vs 策略目标对比分析报告

## 执行摘要 (Executive Summary)

基于 `/home/wuq/webrtc-local/webrtc_config_results/sender_local.log` 的分析，增益因子策略已成功集成并在 DISABLED 模式下完整记录了计算结果。

**关键发现**:
- ✅ 增益因子功能已正确实现并生成日志（3,701条）
- ✅ 当前处于 DISABLED 状态（符合配置 `influence_enabled=0`）
- ✅ 如果启用，预计将使 Additive 增长速率提升 **+60.6%**
- ⚠️ **66.5%** 的时间处于 Gain=2.0 状态（极激进增长），说明大部分时候网络较空闲

---

## 1. 数据统计

### 1.1 日志样本
- **GainFactor 日志总数**: 3,701 条
- **BWE-DECISION 日志总数**: 2,209 条
- **配对成功数据点**: 1,656 条
- **Additive 策略数据**: 1,496 条（占 68.1%）
- **Multiplicative 策略数据**: 682 条（占 30.9%）

### 1.2 增益因子分布

| Gain Factor | 样本数 | 占比 | 策略 | 网络状态 |
|------------|-------|------|------|---------|
| **0.0×** | 277 | 7.5% | 停止增长 | 饱和 (Score ≥ 90) |
| **0.5×** | 345 | 9.3% | 保守增长 | 高利用 (Score 70-90) |
| **1.0×** | 274 | 7.4% | 正常增长 | 中等 (Score 50-70) |
| **1.5×** | 342 | 9.2% | 激进增长 | 低利用 (Score 20-50) |
| **2.0×** | **2,463** | **66.5%** | 极激进增长 | 极低利用 (Score < 20) |

**关键观察**:
- 66.5% 的时间网络处于极低利用状态（ratio 高，score 低）
- 这表明大部分时候网络容量充足，有加速增长的空间

---

## 2. Additive 策略详细对比

### 2.1 按增益因子分组的实际数据

| Gain | 样本数 | 平均 Base Rate | 平均 Adjusted Rate | 差异 | 实际 BWE Change |
|------|-------|----------------|-------------------|------|----------------|
| 0.0× | 98 | 25,914 bps/s | 0 bps/s | **-25,914 bps/s** | 8,300,511 bps |
| 0.5× | 142 | 25,950 bps/s | 12,975 bps/s | **-12,975 bps/s** | 6,878,717 bps |
| 1.0× | 113 | 26,458 bps/s | 26,458 bps/s | **0 bps/s** | 6,870,463 bps |
| 1.5× | 141 | 26,550 bps/s | 39,824 bps/s | **+13,275 bps/s** | 6,954,137 bps |
| 2.0× | 1,002 | 26,289 bps/s | 52,579 bps/s | **+26,289 bps/s** | 5,945,942 bps |

**解读**:
- `Base Rate`: 当前 DISABLED 状态下使用的增长速率
- `Adjusted Rate`: 如果 ENABLED 会使用的调整后速率
- `BWE Change`: 实际带宽变化量（注意：这是总增量 bps，而 rate 是速率 bps/s）

### 2.2 总体影响估算

假设平均更新间隔为 **100ms**：

```
当前状态 (DISABLED):
  Additive 累计增长速率: 3,929,956 bps (使用 Base Rate)

启用增益因子 (ENABLED):
  Additive 累计增长速率: 6,313,116 bps (使用 Adjusted Rate)

差异: +2,383,160 bps (+60.6%)
```

**这意味着**：如果启用增益因子，Additive 策略的带宽增长速度将提升约 **60%**！

---

## 3. 分档位影响分析

### 3.1 各增益档位的累计影响

| Gain | 策略 | 次数 | 累计差异 | 影响描述 |
|------|------|------|---------|---------|
| 0.0× | 停止增长 | 98 | **-253,959 bps** | 会完全停止带宽增长（避免拥塞） |
| 0.5× | 保守增长 | 142 | **-184,244 bps** | 会减慢 50% 的增长速度 |
| 1.0× | 正常增长 | 113 | **0 bps** | 保持不变（基准） |
| 1.5× | 激进增长 | 141 | **+187,174 bps** | 会加速 50% |
| 2.0× | 极激进增长 | 1,002 | **+2,634,188 bps** | 会加速 100%（翻倍！） |

### 3.2 净影响

```
负面影响（减速）: -253,959 - 184,244 = -438,203 bps
正面影响（加速）: +187,174 + 2,634,188 = +2,821,362 bps
净影响: +2,383,159 bps
```

**结论**: 增益因子的净效果是**显著加速**带宽增长，主要由 Gain=2.0× 的大量样本贡献。

---

## 4. 实际 BWE 策略分布

| 策略 | 样本数 | 占比 | 平均增量 | 中位数增量 |
|------|-------|------|---------|-----------|
| **Additive-Increase** | 1,505 | 68.1% | 6,329,666 bps | 6,403,707 bps |
| **Multiplicative-Increase** | 682 | 30.9% | 4,331,111 bps | 3,225,098 bps |
| **Hold** | 14 | 0.6% | - | - |
| **Multiplicative-Decrease** | 8 | 0.4% | - | - |

**关键观察**:
- 大部分时间（68.1%）使用 Additive 策略增长
- Additive 平均增量约 6.3M bps
- Multiplicative 平均增量约 4.3M bps

---

## 5. 增益因子 vs 实际带宽的关系

### 5.1 当前状态（DISABLED）

增益因子**计算但不应用**：
```
Base Rate (26,000 bps/s) × 时间间隔 → 实际增长
```

日志示例：
```
[AIMD-GainFactor] DISABLED - Score: 72.6, Gain: 0.5,
Base rate: 25500 bps/s, Would adjust to: 12750 bps/s (not applied)

[BWE-DECISION] Strategy: Additive-Increase, NewTarget: 1500000 bps,
Change: 6403707 bps
```

### 5.2 如果启用（ENABLED）

增益因子**计算并应用**：
```
Adjusted Rate (根据 Gain 调整) × 时间间隔 → 实际增长
```

预期日志：
```
[AIMD-GainFactor] ENABLED - Score: 72.6, Gain: 0.5,
Base rate: 25500 bps/s, Adjusted rate: 12750 bps/s

[BWE-DECISION] Strategy: Additive-Increase, NewTarget: XXXX bps,
Change: XXXX bps (受增益影响，会减少)
```

---

## 6. 关键场景分析

### 场景1: 网络饱和（Score ≥ 90, Gain = 0.0）

**当前 (DISABLED)**:
```
Base Rate: 25,914 bps/s → 继续以正常速度增长
可能导致: 继续增长 → 拥塞 → Overuse 信号 → 被动减速
```

**如果启用 (ENABLED)**:
```
Adjusted Rate: 0 bps/s → 停止增长
效果: 主动预防拥塞，避免带宽震荡
```

### 场景2: 网络空闲（Score < 20, Gain = 2.0）

**当前 (DISABLED)**:
```
Base Rate: 26,289 bps/s → 以正常速度缓慢增长
结果: 利用率低，带宽增长慢
```

**如果启用 (ENABLED)**:
```
Adjusted Rate: 52,579 bps/s → 双倍速度增长
效果: 快速利用网络容量，提升吞吐量
```

### 场景3: 中等利用（Score 50-70, Gain = 1.0）

**当前 (DISABLED)**:
```
Base Rate: 26,458 bps/s → 正常增长
```

**如果启用 (ENABLED)**:
```
Adjusted Rate: 26,458 bps/s → 正常增长（无变化）
效果: 保持默认行为
```

---

## 7. 预期效果总结

### 7.1 优势

1. **主动拥塞避免**
   - 7.5% 的时间会停止增长（Score ≥ 90）
   - 提前预防拥塞，减少带宽震荡

2. **快速容量利用**
   - 66.5% 的时间会加速增长（Score < 20, Gain = 2.0）
   - 网络空闲时快速提升带宽

3. **动态自适应**
   - 根据网络状态自动调整增长速度
   - 5档精细控制

### 7.2 潜在风险

1. **过度激进**
   - 66.5% 时间使用 Gain=2.0 可能过于激进
   - 可能导致快速从空闲状态变为拥塞

2. **参数调优**
   - 当前阈值（90, 70, 50, 20）可能需要根据实际网络调整
   - 增益值（0, 0.5, 1.0, 1.5, 2.0）可能需要微调

### 7.3 建议

1. **启用测试**
   ```json
   "cellular_ratio": {
     "influence_enabled": 1
   }
   ```

2. **监控指标**
   - 带宽增长速度变化
   - Overuse 信号频率
   - RTT 稳定性
   - 吞吐量提升

3. **参数调优方向**
   - 如果增长过快/拥塞频繁：降低 Gain=2.0 → 1.5
   - 如果停止过早：提高阈值 90 → 95
   - 如果增长过慢：提高 Gain 值或降低阈值

---

## 8. 文件清单

- ✅ [aimd_rate_control.cc](src/modules/remote_bitrate_estimator/aimd_rate_control.cc) - 增益因子实现
- ✅ [aimd_rate_control.h](src/modules/remote_bitrate_estimator/aimd_rate_control.h) - 函数声明
- ✅ [sender_local.log](webrtc_config_results/sender_local.log) - 测试日志
- ✅ [analyze_gain_factor_vs_actual.py](analyze_gain_factor_vs_actual.py) - 对比分析脚本
- ✅ [compare_gain_strategy_impact.py](compare_gain_strategy_impact.py) - 详细影响分析
- ✅ [gain_factor_impact_analysis.png](gain_factor_impact_analysis.png) - 可视化图表
- ✅ [GAIN_FACTOR_IMPLEMENTATION.md](GAIN_FACTOR_IMPLEMENTATION.md) - 实现文档
- ✅ [GAIN_FACTOR_ANALYSIS_REPORT.md](GAIN_FACTOR_ANALYSIS_REPORT.md) - 本报告

---

## 9. 下一步行动

1. **短期**（今天-明天）
   - [ ] 启用增益因子 (`influence_enabled: 1`)
   - [ ] 运行测试收集新日志
   - [ ] 对比启用前后的带宽曲线

2. **中期**（本周）
   - [ ] 分析启用后的性能指标
   - [ ] 根据实际效果调整阈值和增益值
   - [ ] 测试不同网络条件下的表现

3. **长期**（下周+）
   - [ ] 优化增益函数（可能引入连续函数而非阶梯函数）
   - [ ] 集成到生产环境
   - [ ] 持续监控和迭代

---

*报告生成时间: 2025-10-06*
*作者: Claude (claude-sonnet-4-5)*
*数据来源: sender_local.log (3,701 samples)*

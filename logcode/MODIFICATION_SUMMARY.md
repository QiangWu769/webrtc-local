# 修改总结：发送带宽数据到WebRTC

## 修改文件
`/home/wuq/webrtc-local/logcode/diag_get_raw (1).py`

## 修改内容

### 1. 修改数据包格式（第1097-1121行）

**原格式：**
```python
# Pack data: timestamp_us (8 bytes), ratio (8 bytes), sequence (4 bytes)
packet = struct.pack('<QdI', timestamp_us, ratio_value, self._sequence_number)
```

**新格式：**
```python
# Pack data: bandwidth_bps (8 bytes), ratio (8 bytes), sequence (4 bytes)
packet = struct.pack('<QdI', bandwidth_bps_int, ratio_value, self._sequence_number)
```

**字段说明：**
- **bandwidth_bps** (8字节, uint64): 蜂窝网络带宽，单位 bits/second
- **ratio_value** (8字节, double): allocated/requested 比值
- **sequence_number** (4字节, uint32): 序列号

### 2. 带宽计算逻辑

**在 `_flush_and_send_group()` 函数（第983-1022行）：**
```python
# 计算相邻TTI之间的时间间隔
time_interval = tti - prev_tti
if time_interval < 0:  # TTI回绕处理
    time_interval += 10240

# 计算带宽 (bps)
if time_interval > 0:
    bandwidth_bps = (allocated * 8 * 1000) / time_interval
else:
    bandwidth_bps = 0
```

**在单个BSR发送处（第1311-1317行）：**
```python
# nof_grant_subframe 是时间间隔(ms)
if nof_grant_subframe > 0:
    bandwidth_bps = (allocated_resource_old * 8 * 1000) / nof_grant_subframe
else:
    bandwidth_bps = 0
```

### 3. 带宽计算公式

```
带宽 (bps) = (分配字节数 × 8 bits/byte × 1000 ms/s) / 时间间隔(ms)
```

**示例：**
- allocated = 29305 字节
- time_interval = 8 ms
- bandwidth_bps = (29305 × 8 × 1000) / 8 = 29,305,000 bps = 29.3 Mbps

### 4. 传输协议

- **方式**：Unix Domain Socket (UDP)
- **路径**：`/tmp/webrtc_cellular_ratio.sock`
- **包大小**：20字节 (8+8+4)
- **字节序**：Little-endian

## WebRTC接收端需要的修改

WebRTC端需要修改代码来解析新的数据包格式：

```cpp
// 原来解析：
uint64_t timestamp_us;
double ratio;
uint32_t sequence;

// 现在解析：
uint64_t bandwidth_bps;  // 替换 timestamp_us
double ratio;
uint32_t sequence;
```

## 测试建议

1. 验证带宽计算正确性
2. 检查TTI回绕处理
3. 确认WebRTC能正确解析带宽值
4. 对比ratio_data.txt中的数据与发送的带宽值是否一致

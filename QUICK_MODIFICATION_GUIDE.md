# 快速修改指南 - 启用 OpenH264 解码器

## ✅ 已完成的文件

已经为你创建了以下文件：

1. ✅ `src/modules/video_coding/codecs/h264/h264_decoder_openh264_impl.h`
2. ✅ `src/modules/video_coding/codecs/h264/h264_decoder_openh264_impl.cc`

## 🔧 需要手动修改的文件

### 修改 1: h264.cc

**文件**: `src/modules/video_coding/codecs/h264/h264.cc`

#### 步骤 1.1: 添加 include (在文件开头)

在第 32-35 行附近，找到：

```cpp
#if defined(WEBRTC_USE_H264)
#include "modules/video_coding/codecs/h264/h264_decoder_impl.h"
#include "modules/video_coding/codecs/h264/h264_encoder_impl.h"
#endif
```

修改为：

```cpp
#if defined(WEBRTC_USE_H264)
#include "modules/video_coding/codecs/h264/h264_decoder_impl.h"
#include "modules/video_coding/codecs/h264/h264_decoder_openh264_impl.h"  // ← 新增这一行
#include "modules/video_coding/codecs/h264/h264_encoder_impl.h"
#endif
```

#### 步骤 1.2: 修改解码器创建函数

在第 166-176 行附近，找到：

```cpp
std::unique_ptr<H264Decoder> H264Decoder::Create() {
  RTC_DCHECK(H264Decoder::IsSupported());
#if defined(WEBRTC_USE_H264)
  RTC_CHECK(g_rtc_use_h264);
  RTC_LOG(LS_INFO) << "Creating H264DecoderImpl.";
  return std::make_unique<H264DecoderImpl>();
#else
  RTC_DCHECK_NOTREACHED();
  return nullptr;
#endif
}
```

修改为：

```cpp
std::unique_ptr<H264Decoder> H264Decoder::Create() {
  RTC_DCHECK(H264Decoder::IsSupported());
#if defined(WEBRTC_USE_H264)
  RTC_CHECK(g_rtc_use_h264);
  RTC_LOG(LS_INFO) << "Creating H264DecoderOpenH264Impl.";  // ← 修改这一行
  return std::make_unique<H264DecoderOpenH264Impl>();        // ← 修改这一行
#else
  RTC_DCHECK_NOTREACHED();
  return nullptr;
#endif
}
```

---

### 修改 2: BUILD.gn

**文件**: `src/modules/video_coding/codecs/h264/BUILD.gn`

#### 步骤 2.1: 添加源文件

找到 `rtc_library("h264")` 部分（大约在第 10 行），找到 `if (rtc_use_h264)` 块，在其中添加新文件：

原来的代码：

```python
  if (rtc_use_h264) {
    sources += [
      "h264_decoder_impl.cc",
      "h264_decoder_impl.h",
      "h264_encoder_impl.cc",
      "h264_encoder_impl.h",
    ]
```

修改为：

```python
  if (rtc_use_h264) {
    sources += [
      "h264_decoder_impl.cc",
      "h264_decoder_impl.h",
      "h264_decoder_openh264_impl.cc",    # ← 新增这一行
      "h264_decoder_openh264_impl.h",     # ← 新增这一行
      "h264_encoder_impl.cc",
      "h264_encoder_impl.h",
    ]
```

---

## 🔨 编译和测试

### 1. 重新编译

```bash
cd /home/qwu26/webrtc-local

# 清理旧编译（可选，但推荐）
rm -rf src/out/Default/obj/modules/video_coding/codecs/h264

# 重新生成构建配置
gn gen src/out/Default

# 编译
ninja -C src/out/Default peerconnection_client
```

### 2. 检查编译是否成功

```bash
# 检查可执行文件
ls -lh src/out/Default/peerconnection_client

# 应该看到文件大小和修改时间更新
```

### 3. 运行发送端

```bash
cd webrtc_config_results
./test_local_client.sh sender 35.229.115.62
```

### 4. 运行接收端（在另一台机器）

```bash
./test_local_client.sh receiver 35.229.115.62
```

---

## ✅ 验证步骤

### 验证编码器（发送端）

```bash
# 查看发送端日志
grep -i "Creating H264Encoder\|OpenH264 version" webrtc_config_results/sender_local.log

# 应该看到：
# Creating H264EncoderImpl.
# OpenH264 version is 2.6
```

### 验证解码器（接收端）

```bash
# 查看接收端日志
grep -i "Creating H264Decoder\|OpenH264.*initialized" webrtc_config_results/receiver_local.log

# 应该看到：
# Creating H264DecoderOpenH264Impl.
# OpenH264 decoder initialized successfully. Version: 2.6.x
```

### 验证实现名称

```bash
# 发送端
grep "implementation_name" webrtc_config_results/sender_local.log

# 接收端 - 如果有类似日志
grep "implementation_name\|ImplementationName" webrtc_config_results/receiver_local.log
```

---

## 🐛 常见问题

### 问题 1: 编译错误 "undefined reference to WelsCreateDecoder"

**原因**: OpenH264 库没有正确链接

**解决**: 检查 BUILD.gn 中是否有：

```python
deps = [
  "//third_party/openh264:encoder",
  "//third_party/openh264:decoder",  # ← 确保这一行存在
]
```

如果没有，需要添加。

### 问题 2: 运行时崩溃 "decoder_ is nullptr"

**原因**: OpenH264 库在运行时无法加载

**解决**: 检查 OpenH264 动态库是否存在：

```bash
ldd src/out/Default/peerconnection_client | grep openh264
```

### 问题 3: 看到 "Creating H264DecoderImpl" 而不是 "Creating H264DecoderOpenH264Impl"

**原因**: h264.cc 的修改没有生效

**解决**:
1. 确认 h264.cc 修改正确
2. 重新编译: `ninja -C src/out/Default peerconnection_client`
3. 强制重新编译 h264 模块: `rm -rf src/out/Default/obj/modules/video_coding/codecs/h264 && ninja -C src/out/Default peerconnection_client`

### 问题 4: 解码失败 "DecodeFrame2 failed"

**可能原因**:
1. 接收到的码流损坏
2. OpenH264 不支持该 H.264 profile

**调试步骤**:
1. 检查发送端编码参数
2. 启用详细日志（修改 `h264_decoder_openh264_impl.cc` 中的 log_level 为 `WELS_LOG_DETAIL`）
3. 检查日志中的详细错误信息

---

## 📊 性能对比

修改完成后，你可以对比性能：

### 解码时间测试

在 `h264_decoder_openh264_impl.cc` 的 `Decode()` 函数中添加计时：

```cpp
#include "rtc_base/time_utils.h"

int32_t H264DecoderOpenH264Impl::Decode(...) {
  int64_t start_time = rtc::TimeMillis();

  // ... 解码代码 ...

  int64_t decode_time = rtc::TimeMillis() - start_time;
  RTC_LOG(LS_INFO) << "OpenH264 decode time: " << decode_time << "ms";

  return WEBRTC_VIDEO_CODEC_OK;
}
```

---

## 🔄 回滚方案

如果需要回滚到 FFmpeg 解码器：

### 快速回滚

修改 `src/modules/video_coding/codecs/h264/h264.cc`:

```cpp
std::unique_ptr<H264Decoder> H264Decoder::Create() {
  RTC_DCHECK(H264Decoder::IsSupported());
#if defined(WEBRTC_USE_H264)
  RTC_CHECK(g_rtc_use_h264);
  RTC_LOG(LS_INFO) << "Creating H264DecoderImpl.";    // 改回原来的
  return std::make_unique<H264DecoderImpl>();          // 改回原来的
#else
  RTC_DCHECK_NOTREACHED();
  return nullptr;
#endif
}
```

重新编译即可。

---

## 📝 总结

### 修改内容

| 文件 | 操作 | 难度 |
|------|------|------|
| h264_decoder_openh264_impl.h | ✅ 已创建 | - |
| h264_decoder_openh264_impl.cc | ✅ 已创建 | - |
| h264.cc | 🔧 需要修改 2 处 | 简单 |
| BUILD.gn | 🔧 需要添加 2 行 | 简单 |

### 预期结果

```
发送端                           接收端
┌──────────────┐              ┌──────────────┐
│ OpenH264     │   H.264      │  OpenH264    │
│  编码器      │─────────────→│   解码器     │
│  2.6         │   RTP流      │   2.6        │
└──────────────┘              └──────────────┘
```

---

**开始修改吧！有问题随时问我。** 🚀

# 接收端机器 - OpenH264 解码器配置指南

**目标**: 让接收端使用 OpenH264 解码器（而不是默认的 FFmpeg）

**适用对象**: 负责配置接收端机器（云服务器/远程机器）的人员

---

## 📋 前提条件

1. ✅ 接收端机器已经编译过 WebRTC
2. ✅ 接收端机器的 WebRTC 代码路径（假设为 `/path/to/webrtc-local`）
3. ✅ 有 3 个新文件需要从发送端机器复制过来

---

## 📁 第一步：获取必要的文件

### 需要从发送端机器获取的 3 个文件：

1. `h264_decoder_openh264_impl.h`（头文件）
2. `h264_decoder_openh264_impl.cc`（实现文件）
3. `RECEIVER_MACHINE_SETUP_GUIDE.md`（本指南，可选）

### 方法 1：使用 SCP 复制（推荐）

在**接收端机器**上执行：

```bash
# 设置发送端机器的信息
SENDER_IP="你的发送端机器IP"
SENDER_USER="qwu26"
SENDER_PATH="/home/qwu26/webrtc-local"

# 创建目标目录（如果不存在）
mkdir -p /path/to/webrtc-local/src/modules/video_coding/codecs/h264/

# 复制 OpenH264 解码器文件
scp ${SENDER_USER}@${SENDER_IP}:${SENDER_PATH}/src/modules/video_coding/codecs/h264/h264_decoder_openh264_impl.h \
    /path/to/webrtc-local/src/modules/video_coding/codecs/h264/

scp ${SENDER_USER}@${SENDER_IP}:${SENDER_PATH}/src/modules/video_coding/codecs/h264/h264_decoder_openh264_impl.cc \
    /path/to/webrtc-local/src/modules/video_coding/codecs/h264/
```

### 方法 2：手动创建文件

如果无法直接复制，可以手动创建这两个文件。

#### 创建 h264_decoder_openh264_impl.h

```bash
cd /path/to/webrtc-local/src/modules/video_coding/codecs/h264/
nano h264_decoder_openh264_impl.h
```

**复制以下完整内容**（从发送端机器的同名文件复制）：

<details>
<summary>点击展开 h264_decoder_openh264_impl.h 完整内容</summary>

```cpp
/*
 *  Copyright (c) 2025 WebRTC project authors. All Rights Reserved.
 *
 *  OpenH264 Decoder Implementation for WebRTC
 */

#ifndef MODULES_VIDEO_CODING_CODECS_H264_H264_DECODER_OPENH264_IMPL_H_
#define MODULES_VIDEO_CODING_CODECS_H264_H264_DECODER_OPENH264_IMPL_H_

#ifdef WEBRTC_USE_H264

#include <memory>
#include <vector>

#include "api/video/encoded_image.h"
#include "api/video_codecs/video_decoder.h"
#include "common_video/h264/h264_bitstream_parser.h"
#include "common_video/include/video_frame_buffer_pool.h"
#include "modules/video_coding/codecs/h264/include/h264.h"

class ISVCDecoder;

namespace webrtc {

class H264DecoderOpenH264Impl : public H264Decoder {
 public:
  H264DecoderOpenH264Impl();
  ~H264DecoderOpenH264Impl() override;

  bool Configure(const Settings& settings) override;
  int32_t Release() override;

  int32_t RegisterDecodeCompleteCallback(
      DecodedImageCallback* callback) override;

  int32_t Decode(const EncodedImage& input_image,
                 bool missing_frames,
                 int64_t render_time_ms = -1) override;

  const char* ImplementationName() const override;

 private:
  // OpenH264 decoder instance
  ISVCDecoder* decoder_;

  // Decode callback
  DecodedImageCallback* decode_complete_callback_;

  // Frame buffer pool
  VideoFrameBufferPool buffer_pool_;

  // H264 bitstream parser for QP extraction
  H264BitstreamParser h264_bitstream_parser_;

  // Statistics flags
  bool has_reported_init_;
  bool has_reported_error_;

  // Initialization state
  bool initialized_;

  // Helper functions
  void ReportInit();
  void ReportError();
  bool IsInitialized() const;
};

}  // namespace webrtc

#endif  // WEBRTC_USE_H264

#endif  // MODULES_VIDEO_CODING_CODECS_H264_H264_DECODER_OPENH264_IMPL_H_
```

</details>

保存：`Ctrl+O` → `Enter` → `Ctrl+X`

#### 创建 h264_decoder_openh264_impl.cc

```bash
nano h264_decoder_openh264_impl.cc
```

由于文件太长，建议使用 SCP 方式复制。如果必须手动创建，请从发送端机器复制完整内容。

---

## 🔧 第二步：修改 h264.cc

```bash
cd /path/to/webrtc-local
nano src/modules/video_coding/codecs/h264/h264.cc
```

### 修改点 1：添加 include（第 32-35 行附近）

**找到这段代码：**
```cpp
#if defined(WEBRTC_USE_H264)
#include "modules/video_coding/codecs/h264/h264_decoder_impl.h"
#include "modules/video_coding/codecs/h264/h264_encoder_impl.h"
#endif
```

**改成：**
```cpp
#if defined(WEBRTC_USE_H264)
#include "modules/video_coding/codecs/h264/h264_decoder_impl.h"
#include "modules/video_coding/codecs/h264/h264_decoder_openh264_impl.h"  // ← 新增这一行
#include "modules/video_coding/codecs/h264/h264_encoder_impl.h"
#endif
```

### 修改点 2：修改解码器创建函数（第 166-176 行附近）

**找到这段代码：**
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

**改成：**
```cpp
std::unique_ptr<H264Decoder> H264Decoder::Create() {
  RTC_DCHECK(H264Decoder::IsSupported());
#if defined(WEBRTC_USE_H264)
  RTC_CHECK(g_rtc_use_h264);
  RTC_LOG(LS_INFO) << "Creating H264DecoderOpenH264Impl.";  // ← 改这行
  return std::make_unique<H264DecoderOpenH264Impl>();        // ← 改这行
#else
  RTC_DCHECK_NOTREACHED();
  return nullptr;
#endif
}
```

**保存文件**：`Ctrl+O` → `Enter` → `Ctrl+X`

---

## 🔧 第三步：修改 BUILD.gn

```bash
nano src/modules/video_coding/codecs/h264/BUILD.gn
```

### 找到 rtc_library("h264") 部分

**找到这段代码**（大约在第 30-40 行）：
```python
  if (rtc_use_h264) {
    sources += [
      "h264_decoder_impl.cc",
      "h264_decoder_impl.h",
      "h264_encoder_impl.cc",
      "h264_encoder_impl.h",
    ]
```

**改成：**
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

**保存文件**：`Ctrl+O` → `Enter` → `Ctrl+X`

---

## 🔨 第四步：重新编译

```bash
cd /path/to/webrtc-local

# 1. 清理旧的编译产物（推荐）
rm -rf src/out/Default/obj/modules/video_coding/codecs/h264

# 2. 重新生成构建配置
gn gen src/out/Default

# 3. 编译（这可能需要几分钟）
ninja -C src/out/Default peerconnection_client

# 4. 检查编译是否成功
ls -lh src/out/Default/peerconnection_client
```

**预期输出**：
```
-rwxr-xr-x 1 user group 45M Nov 15 10:30 src/out/Default/peerconnection_client
```

如果看到新的时间戳和文件，说明编译成功。

---

## ✅ 第五步：验证配置

### 验证 1：检查编译产物

```bash
# 检查 OpenH264 解码器是否被编译
ls -la src/out/Default/obj/modules/video_coding/codecs/h264/ | grep openh264

# 应该看到：
# h264_decoder_openh264_impl.o
```

### 验证 2：运行接收端并检查日志

```bash
# 运行接收端
cd /path/to/webrtc-local/webrtc_config_results
./test_local_client.sh receiver <信令服务器IP>

# 在另一个终端查看日志
tail -f webrtc_config_results/receiver_local.log
```

### 验证 3：检查日志中的关键信息

```bash
# 检查是否创建了 OpenH264 解码器
grep -i "Creating H264Decoder" webrtc_config_results/receiver_local.log

# 检查 OpenH264 初始化信息
grep -i "OpenH264 decoder initialized" webrtc_config_results/receiver_local.log
```

**✅ 成功的标志**：
```
Creating H264DecoderOpenH264Impl.
OpenH264 decoder initialized successfully. Version: 2.6.x
```

**❌ 失败的标志（仍在使用 FFmpeg）**：
```
Creating H264DecoderImpl.
FFmpeg H.264 decoder
```

---

## 🐛 故障排除

### 问题 1：编译错误 "h264_decoder_openh264_impl.h: No such file"

**原因**：新文件没有正确复制

**解决**：
```bash
# 检查文件是否存在
ls -la src/modules/video_coding/codecs/h264/h264_decoder_openh264_impl.*

# 如果不存在，重新从发送端复制
scp sender@sender-ip:/path/to/h264_decoder_openh264_impl.* \
    src/modules/video_coding/codecs/h264/
```

### 问题 2：编译错误 "undefined reference to WelsCreateDecoder"

**原因**：OpenH264 库没有正确链接

**解决**：检查 BUILD.gn 中是否有 OpenH264 依赖

```bash
# 查看 BUILD.gn 依赖
grep -A 20 'rtc_library("h264")' src/modules/video_coding/codecs/h264/BUILD.gn | grep openh264
```

如果没有看到 openh264 相关依赖，需要添加。

### 问题 3：运行时仍然看到 "Creating H264DecoderImpl"

**原因**：h264.cc 修改没有生效

**解决**：
```bash
# 强制重新编译 h264.cc
rm -f src/out/Default/obj/modules/video_coding/codecs/h264/h264.o
ninja -C src/out/Default peerconnection_client

# 验证修改
strings src/out/Default/peerconnection_client | grep "Creating H264Decoder"
# 应该看到：Creating H264DecoderOpenH264Impl
```

### 问题 4：解码失败 "DecodeFrame2 failed"

**可能原因**：
- 接收到损坏的数据包
- OpenH264 不支持发送端的编码参数

**调试步骤**：
1. 启用详细日志
```cpp
// 在 h264_decoder_openh264_impl.cc 的 Configure() 中修改：
int log_level = WELS_LOG_DETAIL;  // 原来是 WELS_LOG_WARNING
decoder_->SetOption(DECODER_OPTION_TRACE_LEVEL, &log_level);
```

2. 重新编译并查看详细日志

---

## 📊 性能测试（可选）

### 添加解码时间统计

在 `h264_decoder_openh264_impl.cc` 的 `Decode()` 函数开头添加：

```cpp
#include "rtc_base/time_utils.h"

int32_t H264DecoderOpenH264Impl::Decode(...) {
  int64_t start_time_us = rtc::TimeMicros();

  // ... 原有解码代码 ...

  int64_t decode_time_us = rtc::TimeMicros() - start_time_us;
  RTC_LOG(LS_INFO) << "OpenH264 decode time: "
                   << (decode_time_us / 1000.0) << "ms, "
                   << "resolution: " << width << "x" << height;

  return WEBRTC_VIDEO_CODEC_OK;
}
```

重新编译后，可以在日志中看到每帧的解码时间。

---

## 📝 修改总结

### 需要的文件操作：

| 操作 | 文件 | 说明 |
|------|------|------|
| ✅ 复制 | `h264_decoder_openh264_impl.h` | 从发送端获取 |
| ✅ 复制 | `h264_decoder_openh264_impl.cc` | 从发送端获取 |
| 🔧 修改 | `h264.cc` | 2处修改 |
| 🔧 修改 | `BUILD.gn` | 2行新增 |

### 修改位置速查：

**h264.cc**：
- 第 33 行：添加 `#include "...h264_decoder_openh264_impl.h"`
- 第 169-170 行：改为创建 `H264DecoderOpenH264Impl`

**BUILD.gn**：
- 在 `if (rtc_use_h264)` 块中添加 2 个新文件

---

## 🎯 最终验证清单

完成修改后，依次检查：

- [ ] 2个新文件已复制到正确位置
- [ ] h264.cc 已修改（2处）
- [ ] BUILD.gn 已修改（2行）
- [ ] 编译成功，无错误
- [ ] peerconnection_client 可执行文件已更新
- [ ] 运行日志显示 "Creating H264DecoderOpenH264Impl"
- [ ] 运行日志显示 "OpenH264 decoder initialized successfully"
- [ ] 能够正常接收和解码视频

---

## 🔄 回滚方案

如果遇到问题需要回滚到 FFmpeg 解码器：

### 快速回滚

修改 `h264.cc` 的第 169-170 行，改回：

```cpp
RTC_LOG(LS_INFO) << "Creating H264DecoderImpl.";
return std::make_unique<H264DecoderImpl>();
```

重新编译：
```bash
ninja -C src/out/Default peerconnection_client
```

---

## 📞 需要帮助？

如果遇到问题：

1. **检查日志**：`webrtc_config_results/receiver_local.log`
2. **检查编译输出**：查看 ninja 编译过程中的错误信息
3. **验证文件**：确保所有文件都已正确复制和修改

---

**完成以上步骤后，接收端将使用 OpenH264 解码器！** 🎉

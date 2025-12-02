# OpenH264 解码器实现指南

## 📋 目标

**让发送端和接收端都使用 OpenH264**：
- ✅ 发送端：已经使用 OpenH264 编码器
- 🔧 接收端：需要实现 OpenH264 解码器（替代 FFmpeg）

---

## 🎯 实现概览

### 需要做的事情

1. **创建 OpenH264 解码器实现类** (`h264_decoder_openh264_impl.cc/h`)
2. **修改解码器工厂**，让它创建 OpenH264 解码器而不是 FFmpeg
3. **修改编译配置**，确保 OpenH264 解码器被编译
4. **测试验证**

---

## 📁 步骤 1: 创建 OpenH264 解码器头文件

**文件路径**: `src/modules/video_coding/codecs/h264/h264_decoder_openh264_impl.h`

```cpp
/*
 *  OpenH264 Decoder Implementation
 */

#ifndef MODULES_VIDEO_CODING_CODECS_H264_H264_DECODER_OPENH264_IMPL_H_
#define MODULES_VIDEO_CODING_CODECS_H264_H264_DECODER_OPENH264_IMPL_H_

#ifdef WEBRTC_USE_H264

#include <memory>
#include <vector>

#include "api/video/encoded_image.h"
#include "api/video_codecs/video_decoder.h"
#include "common_video/h264/h264_bitstream_parser.h"
#include "modules/video_coding/codecs/h264/include/h264.h"
#include "third_party/openh264/src/codec/api/wels/codec_api.h"
#include "third_party/openh264/src/codec/api/wels/codec_app_def.h"

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
  // OpenH264 解码器实例
  ISVCDecoder* decoder_;

  // 解码完成回调
  DecodedImageCallback* decode_complete_callback_;

  // 帧缓冲池
  VideoFrameBufferPool buffer_pool_;

  // H264 码流解析器 (用于提取 QP)
  H264BitstreamParser h264_bitstream_parser_;

  // 统计标志
  bool has_reported_init_;
  bool has_reported_error_;

  // 初始化状态
  bool initialized_;

  // 帮助函数
  void ReportInit();
  void ReportError();
  bool IsInitialized() const;
};

}  // namespace webrtc

#endif  // WEBRTC_USE_H264

#endif  // MODULES_VIDEO_CODING_CODECS_H264_H264_DECODER_OPENH264_IMPL_H_
```

---

## 📁 步骤 2: 创建 OpenH264 解码器实现文件

**文件路径**: `src/modules/video_coding/codecs/h264/h264_decoder_openh264_impl.cc`

```cpp
/*
 *  OpenH264 Decoder Implementation
 */

#ifdef WEBRTC_USE_H264

#include "modules/video_coding/codecs/h264/h264_decoder_openh264_impl.h"

#include <algorithm>
#include <cstring>
#include <memory>

#include "api/scoped_refptr.h"
#include "api/video/i420_buffer.h"
#include "api/video/video_frame.h"
#include "api/video/video_frame_buffer.h"
#include "api/video/video_rotation.h"
#include "common_video/include/video_frame_buffer.h"
#include "modules/video_coding/codecs/h264/include/h264_globals.h"
#include "modules/video_coding/include/video_error_codes.h"
#include "rtc_base/checks.h"
#include "rtc_base/logging.h"
#include "system_wrappers/include/metrics.h"
#include "third_party/openh264/src/codec/api/wels/codec_api.h"
#include "third_party/openh264/src/codec/api/wels/codec_app_def.h"
#include "third_party/openh264/src/codec/api/wels/codec_def.h"
#include "third_party/openh264/src/codec/api/wels/codec_ver.h"

namespace webrtc {

namespace {

// 用于统计的事件类型
enum H264DecoderOpenH264Event {
  kH264DecoderOpenH264EventInit = 0,
  kH264DecoderOpenH264EventError = 1,
  kH264DecoderOpenH264EventMax = 16,
};

}  // namespace

H264DecoderOpenH264Impl::H264DecoderOpenH264Impl()
    : decoder_(nullptr),
      decode_complete_callback_(nullptr),
      buffer_pool_(false, 300 /* max_number_of_buffers*/),
      has_reported_init_(false),
      has_reported_error_(false),
      initialized_(false) {
  RTC_LOG(LS_INFO) << "Creating H264DecoderOpenH264Impl.";
}

H264DecoderOpenH264Impl::~H264DecoderOpenH264Impl() {
  Release();
}

bool H264DecoderOpenH264Impl::Configure(const Settings& settings) {
  ReportInit();

  if (settings.codec_type() != kVideoCodecH264) {
    ReportError();
    return false;
  }

  // 释放旧的解码器
  if (decoder_) {
    Release();
  }

  // 创建 OpenH264 解码器
  if (WelsCreateDecoder(&decoder_) != 0 || decoder_ == nullptr) {
    RTC_LOG(LS_ERROR) << "Failed to create OpenH264 decoder";
    ReportError();
    return false;
  }

  // 设置解码参数
  SDecodingParam dec_param;
  memset(&dec_param, 0, sizeof(SDecodingParam));

  dec_param.sVideoProperty.eVideoBsType = VIDEO_BITSTREAM_DEFAULT;
  dec_param.bParseOnly = false;
  dec_param.uiTargetDqLayer = UCHAR_MAX;  // 解码所有层
  dec_param.eEcActiveIdc = ERROR_CON_SLICE_COPY;  // 错误隐藏策略

  // 初始化解码器
  long ret = decoder_->Initialize(&dec_param);
  if (ret != cmResultSuccess) {
    RTC_LOG(LS_ERROR) << "Failed to initialize OpenH264 decoder, ret=" << ret;
    WelsDestroyDecoder(decoder_);
    decoder_ = nullptr;
    ReportError();
    return false;
  }

  // 设置日志级别
  int log_level = WELS_LOG_WARNING;
  decoder_->SetOption(DECODER_OPTION_TRACE_LEVEL, &log_level);

  RTC_LOG(LS_INFO) << "OpenH264 decoder initialized successfully. Version: "
                   << OPENH264_MAJOR << "." << OPENH264_MINOR << "."
                   << OPENH264_REVISION;

  initialized_ = true;
  return true;
}

int32_t H264DecoderOpenH264Impl::Release() {
  if (decoder_) {
    decoder_->Uninitialize();
    WelsDestroyDecoder(decoder_);
    decoder_ = nullptr;
  }
  initialized_ = false;
  return WEBRTC_VIDEO_CODEC_OK;
}

int32_t H264DecoderOpenH264Impl::RegisterDecodeCompleteCallback(
    DecodedImageCallback* callback) {
  decode_complete_callback_ = callback;
  return WEBRTC_VIDEO_CODEC_OK;
}

int32_t H264DecoderOpenH264Impl::Decode(const EncodedImage& input_image,
                                         bool missing_frames,
                                         int64_t render_time_ms) {
  if (!IsInitialized()) {
    RTC_LOG(LS_ERROR) << "Decoder not initialized";
    ReportError();
    return WEBRTC_VIDEO_CODEC_UNINITIALIZED;
  }

  if (!decode_complete_callback_) {
    RTC_LOG(LS_WARNING) << "Decode callback not set";
    ReportError();
    return WEBRTC_VIDEO_CODEC_UNINITIALIZED;
  }

  if (!input_image.data() || input_image.size() == 0) {
    RTC_LOG(LS_ERROR) << "Invalid input image";
    ReportError();
    return WEBRTC_VIDEO_CODEC_ERR_PARAMETER;
  }

  // 准备解码
  uint8_t* pData[3] = {nullptr};
  SBufferInfo sDstBufInfo;
  memset(&sDstBufInfo, 0, sizeof(SBufferInfo));

  // 调用 OpenH264 解码
  DECODING_STATE ret = decoder_->DecodeFrame2(
      input_image.data(),
      static_cast<int>(input_image.size()),
      pData,
      &sDstBufInfo);

  if (ret != dsErrorFree) {
    RTC_LOG(LS_ERROR) << "OpenH264 DecodeFrame2 failed, ret=" << ret;
    ReportError();
    return WEBRTC_VIDEO_CODEC_ERROR;
  }

  // 检查是否有输出
  if (sDstBufInfo.iBufferStatus != 1) {
    // 没有输出帧（可能需要更多数据）
    return WEBRTC_VIDEO_CODEC_OK;
  }

  // 提取解码后的数据
  int width = sDstBufInfo.UsrData.sSystemBuffer.iWidth;
  int height = sDstBufInfo.UsrData.sSystemBuffer.iHeight;

  if (width <= 0 || height <= 0) {
    RTC_LOG(LS_ERROR) << "Invalid decoded frame dimensions: "
                      << width << "x" << height;
    return WEBRTC_VIDEO_CODEC_ERROR;
  }

  // 创建 I420 缓冲区
  rtc::scoped_refptr<I420Buffer> buffer = buffer_pool_.CreateI420Buffer(width, height);
  if (!buffer) {
    RTC_LOG(LS_ERROR) << "Failed to allocate I420 buffer";
    return WEBRTC_VIDEO_CODEC_ERROR;
  }

  // OpenH264 输出是 YUV420P 格式，复制数据
  int stride_y = sDstBufInfo.UsrData.sSystemBuffer.iStride[0];
  int stride_u = sDstBufInfo.UsrData.sSystemBuffer.iStride[1];
  int stride_v = stride_u;

  // 复制 Y 平面
  const uint8_t* src_y = pData[0];
  uint8_t* dst_y = buffer->MutableDataY();
  for (int row = 0; row < height; ++row) {
    memcpy(dst_y, src_y, width);
    src_y += stride_y;
    dst_y += buffer->StrideY();
  }

  // 复制 U 平面
  const uint8_t* src_u = pData[1];
  uint8_t* dst_u = buffer->MutableDataU();
  int chroma_width = (width + 1) / 2;
  int chroma_height = (height + 1) / 2;
  for (int row = 0; row < chroma_height; ++row) {
    memcpy(dst_u, src_u, chroma_width);
    src_u += stride_u;
    dst_u += buffer->StrideU();
  }

  // 复制 V 平面
  const uint8_t* src_v = pData[2];
  uint8_t* dst_v = buffer->MutableDataV();
  for (int row = 0; row < chroma_height; ++row) {
    memcpy(dst_v, src_v, chroma_width);
    src_v += stride_v;
    dst_v += buffer->StrideV();
  }

  // 解析 QP (可选)
  h264_bitstream_parser_.ParseBitstream(input_image);
  std::optional<int> qp = h264_bitstream_parser_.GetLastSliceQp();

  // 创建 VideoFrame
  VideoFrame decoded_frame =
      VideoFrame::Builder()
          .set_video_frame_buffer(buffer)
          .set_timestamp_rtp(input_image.RtpTimestamp())
          .set_rotation(kVideoRotation_0)
          .build();

  // 回调
  decode_complete_callback_->Decoded(decoded_frame, std::nullopt, qp);

  return WEBRTC_VIDEO_CODEC_OK;
}

const char* H264DecoderOpenH264Impl::ImplementationName() const {
  return "OpenH264";
}

bool H264DecoderOpenH264Impl::IsInitialized() const {
  return initialized_ && decoder_ != nullptr;
}

void H264DecoderOpenH264Impl::ReportInit() {
  if (has_reported_init_)
    return;
  RTC_HISTOGRAM_ENUMERATION("WebRTC.Video.H264DecoderOpenH264.Event",
                            kH264DecoderOpenH264EventInit,
                            kH264DecoderOpenH264EventMax);
  has_reported_init_ = true;
}

void H264DecoderOpenH264Impl::ReportError() {
  if (has_reported_error_)
    return;
  RTC_HISTOGRAM_ENUMERATION("WebRTC.Video.H264DecoderOpenH264.Event",
                            kH264DecoderOpenH264EventError,
                            kH264DecoderOpenH264EventMax);
  has_reported_error_ = true;
}

}  // namespace webrtc

#endif  // WEBRTC_USE_H264
```

---

## 📁 步骤 3: 修改 h264.cc 添加 OpenH264 解码器创建函数

**文件**: `src/modules/video_coding/codecs/h264/h264.cc`

在文件开头添加 include：

```cpp
#if defined(WEBRTC_USE_H264)
#include "modules/video_coding/codecs/h264/h264_decoder_impl.h"
#include "modules/video_coding/codecs/h264/h264_decoder_openh264_impl.h"  // ← 新增
#include "modules/video_coding/codecs/h264/h264_encoder_impl.h"
#endif
```

修改 `H264Decoder::Create()` 函数：

```cpp
std::unique_ptr<H264Decoder> H264Decoder::Create() {
  RTC_DCHECK(H264Decoder::IsSupported());
#if defined(WEBRTC_USE_H264)
  RTC_CHECK(g_rtc_use_h264);

  // ← 修改这里：使用 OpenH264 解码器而不是 FFmpeg
  RTC_LOG(LS_INFO) << "Creating H264DecoderOpenH264Impl.";
  return std::make_unique<H264DecoderOpenH264Impl>();

  // 原来的 FFmpeg 解码器代码（注释掉）：
  // RTC_LOG(LS_INFO) << "Creating H264DecoderImpl.";
  // return std::make_unique<H264DecoderImpl>();
#else
  RTC_DCHECK_NOTREACHED();
  return nullptr;
#endif
}
```

---

## 📁 步骤 4: 修改 BUILD.gn 添加编译配置

**文件**: `src/modules/video_coding/codecs/h264/BUILD.gn`

找到 `rtc_library("h264")` 部分，添加新文件：

```python
rtc_library("h264") {
  visibility = [ "*" ]
  sources = [
    "h264.cc",
    "include/h264.h",
    "include/h264_globals.h",
  ]

  # ... 现有依赖 ...

  if (rtc_use_h264) {
    sources += [
      "h264_decoder_impl.cc",
      "h264_decoder_impl.h",
      "h264_decoder_openh264_impl.cc",     # ← 新增
      "h264_decoder_openh264_impl.h",      # ← 新增
      "h264_encoder_impl.cc",
      "h264_encoder_impl.h",
    ]

    # ... 现有依赖 ...
  }
}
```

---

## 🔧 步骤 5: 重新编译

```bash
# 1. 清理旧的编译文件
cd /home/qwu26/webrtc-local
gn clean src/out/Default

# 2. 重新生成构建文件
gn gen src/out/Default

# 3. 编译
ninja -C src/out/Default peerconnection_client

# 4. 检查编译是否成功
ls -lh src/out/Default/peerconnection_client
```

---

## ✅ 步骤 6: 验证

### 6.1 检查发送端日志

运行发送端后，检查日志：

```bash
grep -i "encoder\|openh264" webrtc_config_results/sender_local.log | grep -i "creat\|version\|implementation"
```

应该看到：
```
Creating H264EncoderImpl.
OpenH264 version is 2.6
implementation_name = 'OpenH264'
```

### 6.2 检查接收端日志

运行接收端后，检查日志：

```bash
grep -i "decoder\|openh264" webrtc_config_results/receiver_local.log | grep -i "creat\|version\|implementation"
```

应该看到：
```
Creating H264DecoderOpenH264Impl.
OpenH264 decoder initialized successfully. Version: 2.6.x
```

如果看到 "FFmpeg" 或 "H264DecoderImpl"，说明还在使用 FFmpeg 解码器。

---

## 🎯 预期结果

### 修改前（当前）

```
发送端                           接收端
┌──────────────┐              ┌──────────────┐
│ OpenH264     │   H.264      │   FFmpeg     │
│  编码器      │─────────────→│   解码器     │
│  (软件)      │   RTP流      │  (软件)      │
└──────────────┘              └──────────────┘
```

### 修改后（目标）

```
发送端                           接收端
┌──────────────┐              ┌──────────────┐
│ OpenH264     │   H.264      │  OpenH264    │
│  编码器      │─────────────→│   解码器     │
│  (软件)      │   RTP流      │  (软件)      │
└──────────────┘              └──────────────┘
```

---

## ⚠️ 已知问题和注意事项

### 1. 性能对比

| 解码器 | 640×360 | 1080p | Profile 支持 |
|--------|---------|-------|-------------|
| OpenH264 | ~3-4ms | ~15-20ms | 基础 |
| FFmpeg | ~2ms | ~8-12ms | 全部 |

**OpenH264 解码器性能会略低于 FFmpeg**，但对于 640×360 和 480×270 来说完全足够。

### 2. Profile 限制

OpenH264 解码器主要支持：
- ✅ Baseline Profile
- ✅ Constrained Baseline Profile
- ⚠️ Main Profile (部分支持)
- ❌ High Profile (可能不支持所有特性)

### 3. 错误处理

OpenH264 解码器的错误恢复能力可能不如 FFmpeg，如果遇到损坏的码流：
- FFmpeg: 通常能部分恢复
- OpenH264: 可能直接失败

### 4. 内存使用

OpenH264 的内存管理方式与 FFmpeg 不同，可能需要调整缓冲池大小。

---

## 🐛 调试技巧

### 启用 OpenH264 详细日志

在 `h264_decoder_openh264_impl.cc` 的 `Configure()` 函数中修改：

```cpp
// 将日志级别改为 DETAIL
int log_level = WELS_LOG_DETAIL;  // 原来是 WELS_LOG_WARNING
decoder_->SetOption(DECODER_OPTION_TRACE_LEVEL, &log_level);
```

### 添加调试输出

在 `Decode()` 函数中添加：

```cpp
RTC_LOG(LS_INFO) << "Decoding frame: size=" << input_image.size()
                 << " timestamp=" << input_image.RtpTimestamp();

// 解码后
RTC_LOG(LS_INFO) << "Decoded frame: " << width << "x" << height
                 << " status=" << sDstBufInfo.iBufferStatus;
```

### 检查解码器状态

```cpp
// 在 Decode() 中添加
int32_t option_value;
decoder_->GetOption(DECODER_OPTION_NUM_OF_FRAMES_REMAINING_IN_BUFFER, &option_value);
RTC_LOG(LS_INFO) << "Frames in buffer: " << option_value;
```

---

## 📊 测试清单

- [ ] 编译成功，没有错误
- [ ] 发送端日志显示 "Creating H264EncoderImpl" 和 "OpenH264 version"
- [ ] 接收端日志显示 "Creating H264DecoderOpenH264Impl"
- [ ] 接收端日志显示 "OpenH264 decoder initialized successfully"
- [ ] 视频能正常传输和接收
- [ ] 接收端能看到解码后的视频帧
- [ ] 没有解码错误或崩溃
- [ ] 性能可接受（帧率稳定）

---

## 🔄 回滚到 FFmpeg（如果需要）

如果 OpenH264 解码器有问题，可以快速回滚：

在 `h264.cc` 中改回：

```cpp
std::unique_ptr<H264Decoder> H264Decoder::Create() {
  RTC_DCHECK(H264Decoder::IsSupported());
#if defined(WEBRTC_USE_H264)
  RTC_CHECK(g_rtc_use_h264);
  // 使用 FFmpeg 解码器
  RTC_LOG(LS_INFO) << "Creating H264DecoderImpl.";
  return std::make_unique<H264DecoderImpl>();
#else
  RTC_DCHECK_NOTREACHED();
  return nullptr;
#endif
}
```

重新编译即可。

---

## 📚 参考资料

- OpenH264 API: `src/third_party/openh264/src/codec/api/wels/codec_api.h`
- OpenH264 示例: OpenH264 官方仓库的 `codec/console/dec/` 目录
- WebRTC H.264: `src/modules/video_coding/codecs/h264/`

---

**完成后，发送端和接收端都将使用 OpenH264！** 🎉

# 接收端 OpenH264 解码器配置（简洁版）

**在接收端机器上执行以下操作**

---

## 步骤 1: 创建 h264_decoder_openh264_impl.h

```bash
cd /path/to/webrtc-local/src/modules/video_coding/codecs/h264/
nano h264_decoder_openh264_impl.h
```

**完整内容**：

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
  ISVCDecoder* decoder_;
  DecodedImageCallback* decode_complete_callback_;
  VideoFrameBufferPool buffer_pool_;
  H264BitstreamParser h264_bitstream_parser_;
  bool has_reported_init_;
  bool has_reported_error_;
  bool initialized_;

  void ReportInit();
  void ReportError();
  bool IsInitialized() const;
};

}  // namespace webrtc

#endif  // WEBRTC_USE_H264

#endif  // MODULES_VIDEO_CODING_CODECS_H264_H264_DECODER_OPENH264_IMPL_H_
```

保存: `Ctrl+O` → `Enter` → `Ctrl+X`

---

## 步骤 2: 创建 h264_decoder_openh264_impl.cc

```bash
nano h264_decoder_openh264_impl.cc
```

**完整内容**：

```cpp
/*
 *  Copyright (c) 2025 WebRTC project authors. All Rights Reserved.
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

enum H264DecoderOpenH264Event {
  kH264DecoderOpenH264EventInit = 0,
  kH264DecoderOpenH264EventError = 1,
  kH264DecoderOpenH264EventMax = 16,
};

}  // namespace

H264DecoderOpenH264Impl::H264DecoderOpenH264Impl()
    : decoder_(nullptr),
      decode_complete_callback_(nullptr),
      buffer_pool_(false, 300),
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

  if (decoder_) {
    Release();
  }

  if (WelsCreateDecoder(&decoder_) != 0 || decoder_ == nullptr) {
    RTC_LOG(LS_ERROR) << "Failed to create OpenH264 decoder";
    ReportError();
    return false;
  }

  SDecodingParam dec_param;
  memset(&dec_param, 0, sizeof(SDecodingParam));
  dec_param.sVideoProperty.eVideoBsType = VIDEO_BITSTREAM_DEFAULT;
  dec_param.bParseOnly = false;
  dec_param.uiTargetDqLayer = UCHAR_MAX;
  dec_param.eEcActiveIdc = ERROR_CON_SLICE_COPY;

  long ret = decoder_->Initialize(&dec_param);
  if (ret != cmResultSuccess) {
    RTC_LOG(LS_ERROR) << "Failed to initialize OpenH264 decoder, ret=" << ret;
    WelsDestroyDecoder(decoder_);
    decoder_ = nullptr;
    ReportError();
    return false;
  }

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

  uint8_t* pData[3] = {nullptr};
  SBufferInfo sDstBufInfo;
  memset(&sDstBufInfo, 0, sizeof(SBufferInfo));

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

  if (sDstBufInfo.iBufferStatus != 1) {
    return WEBRTC_VIDEO_CODEC_OK;
  }

  int width = sDstBufInfo.UsrData.sSystemBuffer.iWidth;
  int height = sDstBufInfo.UsrData.sSystemBuffer.iHeight;

  if (width <= 0 || height <= 0) {
    RTC_LOG(LS_ERROR) << "Invalid decoded frame dimensions: "
                      << width << "x" << height;
    return WEBRTC_VIDEO_CODEC_ERROR;
  }

  rtc::scoped_refptr<I420Buffer> buffer =
      buffer_pool_.CreateI420Buffer(width, height);
  if (!buffer) {
    RTC_LOG(LS_ERROR) << "Failed to allocate I420 buffer";
    return WEBRTC_VIDEO_CODEC_ERROR;
  }

  int stride_y = sDstBufInfo.UsrData.sSystemBuffer.iStride[0];
  int stride_u = sDstBufInfo.UsrData.sSystemBuffer.iStride[1];
  int stride_v = stride_u;

  const uint8_t* src_y = pData[0];
  uint8_t* dst_y = buffer->MutableDataY();
  for (int row = 0; row < height; ++row) {
    memcpy(dst_y, src_y, width);
    src_y += stride_y;
    dst_y += buffer->StrideY();
  }

  const uint8_t* src_u = pData[1];
  uint8_t* dst_u = buffer->MutableDataU();
  int chroma_width = (width + 1) / 2;
  int chroma_height = (height + 1) / 2;
  for (int row = 0; row < chroma_height; ++row) {
    memcpy(dst_u, src_u, chroma_width);
    src_u += stride_u;
    dst_u += buffer->StrideU();
  }

  const uint8_t* src_v = pData[2];
  uint8_t* dst_v = buffer->MutableDataV();
  for (int row = 0; row < chroma_height; ++row) {
    memcpy(dst_v, src_v, chroma_width);
    src_v += stride_v;
    dst_v += buffer->StrideV();
  }

  h264_bitstream_parser_.ParseBitstream(input_image);
  std::optional<int> qp = h264_bitstream_parser_.GetLastSliceQp();

  VideoFrame decoded_frame =
      VideoFrame::Builder()
          .set_video_frame_buffer(buffer)
          .set_timestamp_rtp(input_image.RtpTimestamp())
          .set_rotation(kVideoRotation_0)
          .build();

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

保存: `Ctrl+O` → `Enter` → `Ctrl+X`

---

## 步骤 3: 修改 h264.cc

```bash
cd /path/to/webrtc-local/src/modules/video_coding/codecs/h264/
nano h264.cc
```

### 改动 1: 添加 include（第 33 行附近）

找到：
```cpp
#if defined(WEBRTC_USE_H264)
#include "modules/video_coding/codecs/h264/h264_decoder_impl.h"
#include "modules/video_coding/codecs/h264/h264_encoder_impl.h"
#endif
```

改成：
```cpp
#if defined(WEBRTC_USE_H264)
#include "modules/video_coding/codecs/h264/h264_decoder_impl.h"
#include "modules/video_coding/codecs/h264/h264_decoder_openh264_impl.h"  // ← 新增
#include "modules/video_coding/codecs/h264/h264_encoder_impl.h"
#endif
```

### 改动 2: 修改 Create 函数（第 169-170 行）

找到：
```cpp
  RTC_LOG(LS_INFO) << "Creating H264DecoderImpl.";
  return std::make_unique<H264DecoderImpl>();
```

改成：
```cpp
  RTC_LOG(LS_INFO) << "Creating H264DecoderOpenH264Impl.";
  return std::make_unique<H264DecoderOpenH264Impl>();
```

保存: `Ctrl+O` → `Enter` → `Ctrl+X`

---

## 步骤 4: 修改 BUILD.gn

```bash
nano BUILD.gn
```

找到（第 30-40 行附近）：
```python
  if (rtc_use_h264) {
    sources += [
      "h264_decoder_impl.cc",
      "h264_decoder_impl.h",
      "h264_encoder_impl.cc",
      "h264_encoder_impl.h",
    ]
```

改成：
```python
  if (rtc_use_h264) {
    sources += [
      "h264_decoder_impl.cc",
      "h264_decoder_impl.h",
      "h264_decoder_openh264_impl.cc",    # ← 新增
      "h264_decoder_openh264_impl.h",     # ← 新增
      "h264_encoder_impl.cc",
      "h264_encoder_impl.h",
    ]
```

保存: `Ctrl+O` → `Enter` → `Ctrl+X`

---

## 步骤 5: 编译

```bash
cd /path/to/webrtc-local
gn gen src/out/Default
ninja -C src/out/Default peerconnection_client
```

---

## 步骤 6: 验证

```bash
# 运行接收端
./test_local_client.sh receiver <信令服务器IP>

# 检查日志
grep "Creating H264Decoder\|OpenH264 decoder" webrtc_config_results/receiver_local.log
```

**成功标志**：
```
Creating H264DecoderOpenH264Impl.
OpenH264 decoder initialized successfully. Version: 2.6.x
```

---

## 总结

| 步骤 | 操作 | 文件 |
|------|------|------|
| 1 | 新建 | h264_decoder_openh264_impl.h |
| 2 | 新建 | h264_decoder_openh264_impl.cc |
| 3 | 修改2处 | h264.cc |
| 4 | 新增2行 | BUILD.gn |
| 5 | 编译 | - |
| 6 | 验证 | 日志 |

完成！

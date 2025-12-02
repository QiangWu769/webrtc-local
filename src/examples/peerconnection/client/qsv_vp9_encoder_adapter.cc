/*
 * QSV VP9 Encoder Adapter Implementation
 */

#include "examples/peerconnection/client/qsv_vp9_encoder_adapter.h"
#include "examples/peerconnection/client/qsv_vp9_encoder.h"

#include "media/base/codec.h"
#include "rtc_base/logging.h"

extern "C" {
#include <libavutil/hwcontext.h>
#include <libavcodec/avcodec.h>
}

namespace webrtc {

bool QsvVp9EncoderAdapter::IsQsvAvailable() {
  static absl::optional<bool> cached;

  if (cached.has_value()) {
    return *cached;
  }

  // Check 1: QSV hardware device available
  AVBufferRef* hw_device_ctx = nullptr;
  int ret = av_hwdevice_ctx_create(&hw_device_ctx,
                                   AV_HWDEVICE_TYPE_QSV,
                                   nullptr, nullptr, 0);

  if (ret < 0) {
    char errbuf[AV_ERROR_MAX_STRING_SIZE];
    av_strerror(ret, errbuf, sizeof(errbuf));
    RTC_LOG(LS_WARNING) << "[QSV-Adapter] QSV hwdevice not available: " << errbuf;
    cached = false;
    return false;
  }

  av_buffer_unref(&hw_device_ctx);

  // Check 2: vp9_qsv encoder available
  const AVCodec* codec = avcodec_find_encoder_by_name("vp9_qsv");
  if (!codec) {
    RTC_LOG(LS_WARNING) << "[QSV-Adapter] vp9_qsv encoder not found in FFmpeg";
    cached = false;
    return false;
  }

  RTC_LOG(LS_WARNING) << "[QSV-Adapter] ✅ QSV VP9 hardware encoding available!";
  cached = true;
  return true;
}

std::vector<SdpVideoFormat> QsvVp9EncoderAdapter::SupportedFormats() {
  if (!IsQsvAvailable()) {
    RTC_LOG(LS_INFO) << "[QSV-Adapter] QSV not available, returning empty formats";
    return {};
  }

  RTC_LOG(LS_WARNING) << "[QSV-Adapter] Advertising VP9 hardware encoding support";
  return {SdpVideoFormat::VP9Profile0()};
}

std::unique_ptr<VideoEncoder> QsvVp9EncoderAdapter::CreateEncoder(
    const Environment& env,
    const SdpVideoFormat& format) {
  if (!IsQsvAvailable()) {
    RTC_LOG(LS_ERROR) << "[QSV-Adapter] Cannot create encoder, QSV not available";
    return nullptr;
  }

  RTC_LOG(LS_WARNING) << "[QSV-Adapter] Creating QSV VP9 hardware encoder";
  return std::make_unique<QsvVp9Encoder>(env);
}

bool QsvVp9EncoderAdapter::IsScalabilityModeSupported(ScalabilityMode scalability_mode) {
  // QSV VP9 encoder supports single stream only (no simulcast/SVC)
  return scalability_mode == ScalabilityMode::kL1T1 ||
         scalability_mode == ScalabilityMode::kL1T2 ||
         scalability_mode == ScalabilityMode::kL1T3;
}

}  // namespace webrtc

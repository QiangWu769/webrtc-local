/*
 * QSV VP9 Hardware Encoder Implementation
 */

#include "examples/peerconnection/client/qsv_vp9_encoder.h"

#include <string.h>
#include <algorithm>

#include "api/video/i420_buffer.h"
#include "api/scoped_refptr.h"
#include "modules/video_coding/include/video_codec_interface.h"
#include "rtc_base/time_utils.h"
#include "rtc_base/system_time.h"
#include "third_party/libyuv/include/libyuv.h"

namespace webrtc {

QsvVp9Encoder::QsvVp9Encoder(const Environment& env) : env_(env) {
  RTC_LOG(LS_INFO) << "[QSV-VP9] Encoder created";
}

QsvVp9Encoder::~QsvVp9Encoder() {
  Release();
}

int QsvVp9Encoder::RegisterEncodeCompleteCallback(
    EncodedImageCallback* callback) {
  callback_ = callback;
  return WEBRTC_VIDEO_CODEC_OK;
}

int QsvVp9Encoder::InitHwDevice() {
  int ret = av_hwdevice_ctx_create(&hw_device_ctx_,
                                   AV_HWDEVICE_TYPE_QSV,
                                   nullptr, nullptr, 0);
  if (ret < 0) {
    char errbuf[AV_ERROR_MAX_STRING_SIZE];
    av_strerror(ret, errbuf, sizeof(errbuf));
    RTC_LOG(LS_ERROR) << "[QSV-VP9] av_hwdevice_ctx_create failed: " << errbuf;
    return ret;
  }

  RTC_LOG(LS_WARNING) << "[QSV-VP9] Hardware device context created successfully";
  return 0;
}

int QsvVp9Encoder::InitHwFramesContext() {
  if (!hw_device_ctx_) {
    return -1;
  }

  hw_frames_ctx_ = av_hwframe_ctx_alloc(hw_device_ctx_);
  if (!hw_frames_ctx_) {
    RTC_LOG(LS_ERROR) << "[QSV-VP9] Failed to allocate hw frames context";
    return -1;
  }

  AVHWFramesContext* frames_ctx = (AVHWFramesContext*)hw_frames_ctx_->data;
  frames_ctx->format = AV_PIX_FMT_QSV;
  frames_ctx->sw_format = AV_PIX_FMT_NV12;
  frames_ctx->width = width_;
  frames_ctx->height = height_;
  frames_ctx->initial_pool_size = 20;

  int ret = av_hwframe_ctx_init(hw_frames_ctx_);
  if (ret < 0) {
    char errbuf[AV_ERROR_MAX_STRING_SIZE];
    av_strerror(ret, errbuf, sizeof(errbuf));
    RTC_LOG(LS_ERROR) << "[QSV-VP9] av_hwframe_ctx_init failed: " << errbuf;
    av_buffer_unref(&hw_frames_ctx_);
    return ret;
  }

  codec_ctx_->hw_frames_ctx = av_buffer_ref(hw_frames_ctx_);
  RTC_LOG(LS_INFO) << "[QSV-VP9] Hardware frames context initialized";
  return 0;
}

int QsvVp9Encoder::InitEncode(const VideoCodec* codec_settings,
                               const Settings& settings) {
  if (codec_settings == nullptr) {
    return WEBRTC_VIDEO_CODEC_ERR_PARAMETER;
  }
  if (codec_settings->width < 1 || codec_settings->height < 1) {
    return WEBRTC_VIDEO_CODEC_ERR_PARAMETER;
  }
  if (codec_settings->maxFramerate < 1) {
    return WEBRTC_VIDEO_CODEC_ERR_PARAMETER;
  }

  if (initialized_) {
    RTC_LOG(LS_WARNING) << "[QSV-VP9] Already initialized, releasing first";
    Release();
  }

  // Get dimensions from VideoCodec
  width_ = codec_settings->width;
  height_ = codec_settings->height;
  fps_ = codec_settings->maxFramerate;

  RTC_LOG(LS_WARNING) << "[QSV-VP9] InitEncode: " << width_ << "x" << height_
                      << "@" << fps_ << "fps";

  // Find vp9_qsv encoder
  codec_ = avcodec_find_encoder_by_name("vp9_qsv");
  if (!codec_) {
    RTC_LOG(LS_ERROR) << "[QSV-VP9] vp9_qsv encoder not found! "
                      << "Please check FFmpeg compilation.";
    return WEBRTC_VIDEO_CODEC_ERROR;
  }

  codec_ctx_ = avcodec_alloc_context3(codec_);
  if (!codec_ctx_) {
    RTC_LOG(LS_ERROR) << "[QSV-VP9] Failed to allocate codec context";
    return WEBRTC_VIDEO_CODEC_ERROR;
  }

  // Basic encoder settings
  codec_ctx_->width = width_;
  codec_ctx_->height = height_;
  codec_ctx_->time_base = AVRational{1, fps_};
  codec_ctx_->framerate = AVRational{fps_, 1};
  codec_ctx_->pix_fmt = AV_PIX_FMT_QSV;
  codec_ctx_->bit_rate = bitrate_kbps_ > 0 ? bitrate_kbps_ * 1000LL : 2000000;
  codec_ctx_->gop_size = fps_ * 2;  // Keyframe every 2 seconds
  codec_ctx_->max_b_frames = 0;     // Disable B-frames for low latency

  // Initialize hardware device
  if (InitHwDevice() != 0) {
    avcodec_free_context(&codec_ctx_);
    return WEBRTC_VIDEO_CODEC_ERROR;
  }

  // Set hardware device context
  codec_ctx_->hw_device_ctx = av_buffer_ref(hw_device_ctx_);

  // Initialize hardware frames context
  if (InitHwFramesContext() != 0) {
    avcodec_free_context(&codec_ctx_);
    return WEBRTC_VIDEO_CODEC_ERROR;
  }

  // Open codec
  int ret = avcodec_open2(codec_ctx_, codec_, nullptr);
  if (ret < 0) {
    char errbuf[AV_ERROR_MAX_STRING_SIZE];
    av_strerror(ret, errbuf, sizeof(errbuf));
    RTC_LOG(LS_ERROR) << "[QSV-VP9] avcodec_open2 failed: " << errbuf;
    Release();
    return WEBRTC_VIDEO_CODEC_ERROR;
  }

  initialized_ = true;
  frame_count_ = 0;

  RTC_LOG(LS_WARNING) << "[QSV-VP9] ✅ VP9 hardware encoder initialized successfully: "
                      << width_ << "x" << height_ << "@" << fps_ << "fps, "
                      << "bitrate=" << codec_ctx_->bit_rate / 1000 << "kbps";

  return WEBRTC_VIDEO_CODEC_OK;
}

AVFrame* QsvVp9Encoder::CreateHwFrame() {
  if (!hw_frames_ctx_) {
    return nullptr;
  }

  AVFrame* hw_frame = av_frame_alloc();
  if (!hw_frame) {
    return nullptr;
  }

  int ret = av_hwframe_get_buffer(hw_frames_ctx_, hw_frame, 0);
  if (ret < 0) {
    char errbuf[AV_ERROR_MAX_STRING_SIZE];
    av_strerror(ret, errbuf, sizeof(errbuf));
    RTC_LOG(LS_ERROR) << "[QSV-VP9] av_hwframe_get_buffer failed: " << errbuf;
    av_frame_free(&hw_frame);
    return nullptr;
  }

  return hw_frame;
}

int QsvVp9Encoder::UploadFrameToGpu(AVFrame* hw_frame,
                                    const VideoFrameBuffer* buffer) {
  // Convert I420 to NV12 and upload to GPU
  // ToI420() is non-const, so we need to cast away constness
  scoped_refptr<I420BufferInterface> i420 =
      const_cast<VideoFrameBuffer*>(buffer)->ToI420();

  // Create temporary software frame (NV12)
  AVFrame* sw_frame = av_frame_alloc();
  sw_frame->format = AV_PIX_FMT_NV12;
  sw_frame->width = i420->width();
  sw_frame->height = i420->height();

  int ret = av_frame_get_buffer(sw_frame, 32);
  if (ret < 0) {
    av_frame_free(&sw_frame);
    return ret;
  }

  // Convert I420 to NV12 using libyuv
  int result = libyuv::I420ToNV12(
      i420->DataY(), i420->StrideY(),
      i420->DataU(), i420->StrideU(),
      i420->DataV(), i420->StrideV(),
      sw_frame->data[0], sw_frame->linesize[0],
      sw_frame->data[1], sw_frame->linesize[1],
      i420->width(), i420->height());

  if (result != 0) {
    RTC_LOG(LS_ERROR) << "[QSV-VP9] libyuv I420ToNV12 conversion failed";
    av_frame_free(&sw_frame);
    return -1;
  }

  // Transfer to GPU
  ret = av_hwframe_transfer_data(hw_frame, sw_frame, 0);
  av_frame_free(&sw_frame);

  if (ret < 0) {
    char errbuf[AV_ERROR_MAX_STRING_SIZE];
    av_strerror(ret, errbuf, sizeof(errbuf));
    RTC_LOG(LS_ERROR) << "[QSV-VP9] av_hwframe_transfer_data failed: " << errbuf;
    return ret;
  }

  return 0;
}

int QsvVp9Encoder::Encode(
    const VideoFrame& frame,
    const std::vector<VideoFrameType>* frame_types) {
  if (!initialized_ || !callback_) {
    RTC_LOG(LS_WARNING) << "[QSV-VP9] Encoder not initialized or no callback";
    return WEBRTC_VIDEO_CODEC_ERROR;
  }

  int64_t encode_start_us = TimeMicros();

  // Create hardware frame
  AVFrame* hw_frame = CreateHwFrame();
  if (!hw_frame) {
    RTC_LOG(LS_ERROR) << "[QSV-VP9] Failed to create hardware frame";
    return WEBRTC_VIDEO_CODEC_ERROR;
  }

  // Upload frame data to GPU
  scoped_refptr<VideoFrameBuffer> buffer = frame.video_frame_buffer();
  if (UploadFrameToGpu(hw_frame, buffer.get()) != 0) {
    av_frame_free(&hw_frame);
    return WEBRTC_VIDEO_CODEC_ERROR;
  }

  hw_frame->pts = frame_count_++;

  // Check if keyframe requested
  bool force_keyframe = false;
  if (frame_types && !frame_types->empty()) {
    force_keyframe = (*frame_types)[0] == VideoFrameType::kVideoFrameKey;
  }

  if (force_keyframe) {
    hw_frame->pict_type = AV_PICTURE_TYPE_I;
  }

  // Send frame to encoder
  int ret = avcodec_send_frame(codec_ctx_, hw_frame);
  av_frame_free(&hw_frame);

  if (ret < 0) {
    char errbuf[AV_ERROR_MAX_STRING_SIZE];
    av_strerror(ret, errbuf, sizeof(errbuf));
    RTC_LOG(LS_ERROR) << "[QSV-VP9] avcodec_send_frame failed: " << errbuf;
    return WEBRTC_VIDEO_CODEC_ERROR;
  }

  // Receive encoded packets
  while (ret >= 0) {
    AVPacket* pkt = av_packet_alloc();
    ret = avcodec_receive_packet(codec_ctx_, pkt);

    if (ret == AVERROR(EAGAIN) || ret == AVERROR_EOF) {
      av_packet_free(&pkt);
      break;
    }

    if (ret < 0) {
      char errbuf[AV_ERROR_MAX_STRING_SIZE];
      av_strerror(ret, errbuf, sizeof(errbuf));
      RTC_LOG(LS_ERROR) << "[QSV-VP9] avcodec_receive_packet failed: " << errbuf;
      av_packet_free(&pkt);
      return WEBRTC_VIDEO_CODEC_ERROR;
    }

    // Create WebRTC EncodedImage
    EncodedImage encoded;
    encoded.SetEncodedData(
        EncodedImageBuffer::Create(pkt->data, pkt->size));
    encoded.set_size(pkt->size);
    encoded._encodedWidth = width_;
    encoded._encodedHeight = height_;
    encoded.SetRtpTimestamp(frame.rtp_timestamp());
    encoded.capture_time_ms_ = frame.render_time_ms();

    // Determine frame type
    bool is_keyframe = (pkt->flags & AV_PKT_FLAG_KEY) != 0;
    encoded._frameType = is_keyframe ? VideoFrameType::kVideoFrameKey
                                     : VideoFrameType::kVideoFrameDelta;

    // Codec specific info
    CodecSpecificInfo codec_info;
    codec_info.codecType = kVideoCodecVP9;
    codec_info.codecSpecific.VP9.inter_pic_predicted = !is_keyframe;
    codec_info.codecSpecific.VP9.ss_data_available = is_keyframe;

    int64_t encode_time_us = TimeMicros() - encode_start_us;

    // Log encoding time (only for keyframes or occasionally)
    if (is_keyframe || frame_count_ % 100 == 0) {
      RTC_LOG(LS_INFO) << "[QSV-VP9] Frame #" << frame_count_
                       << " encoded in " << encode_time_us / 1000.0 << "ms, "
                       << "size=" << pkt->size << " bytes, "
                       << "keyframe=" << is_keyframe;
    }

    // Deliver encoded image
    EncodedImageCallback::Result result =
        callback_->OnEncodedImage(encoded, &codec_info);

    av_packet_free(&pkt);

    if (result.error != EncodedImageCallback::Result::OK) {
      RTC_LOG(LS_WARNING) << "[QSV-VP9] Callback returned error: "
                          << result.error;
    }
  }

  return WEBRTC_VIDEO_CODEC_OK;
}

void QsvVp9Encoder::SetRates(const RateControlParameters& parameters) {
  if (!initialized_) {
    return;
  }

  bitrate_kbps_ = parameters.bitrate.get_sum_kbps();

  // Update codec bitrate
  if (codec_ctx_) {
    codec_ctx_->bit_rate = bitrate_kbps_ * 1000LL;
    RTC_LOG(LS_INFO) << "[QSV-VP9] Bitrate updated to " << bitrate_kbps_ << " kbps";
  }

  // Note: For dynamic bitrate change to take effect immediately,
  // we might need to use encoder-specific options or re-initialize
}

VideoEncoder::EncoderInfo QsvVp9Encoder::GetEncoderInfo() const {
  EncoderInfo info;
  info.supports_native_handle = false;
  info.implementation_name = "QSV-VP9";
  info.has_trusted_rate_controller = false;
  info.is_hardware_accelerated = true;
  info.supports_simulcast = false;

  return info;
}

int QsvVp9Encoder::Release() {
  RTC_LOG(LS_INFO) << "[QSV-VP9] Releasing encoder";

  if (codec_ctx_) {
    avcodec_free_context(&codec_ctx_);
    codec_ctx_ = nullptr;
  }

  if (hw_frames_ctx_) {
    av_buffer_unref(&hw_frames_ctx_);
    hw_frames_ctx_ = nullptr;
  }

  if (hw_device_ctx_) {
    av_buffer_unref(&hw_device_ctx_);
    hw_device_ctx_ = nullptr;
  }

  initialized_ = false;
  frame_count_ = 0;

  return WEBRTC_VIDEO_CODEC_OK;
}

}  // namespace webrtc

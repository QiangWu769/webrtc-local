/*
 * QSV VP9 Hardware Encoder for WebRTC
 * Uses Intel Quick Sync Video (QSV) via FFmpeg
 */

#ifndef EXAMPLES_PEERCONNECTION_CLIENT_QSV_VP9_ENCODER_H_
#define EXAMPLES_PEERCONNECTION_CLIENT_QSV_VP9_ENCODER_H_

#include "api/video_codecs/video_encoder.h"
#include "api/video_codecs/video_codec.h"
#include "api/environment/environment.h"
#include "api/video/video_frame.h"
#include "api/video/encoded_image.h"
#include "modules/video_coding/include/video_error_codes.h"
#include "rtc_base/logging.h"

extern "C" {
#include <libavcodec/avcodec.h>
#include <libavutil/hwcontext.h>
#include <libavutil/imgutils.h>
}

namespace webrtc {

class QsvVp9Encoder : public VideoEncoder {
 public:
  explicit QsvVp9Encoder(const Environment& env);
  ~QsvVp9Encoder() override;

  // VideoEncoder interface implementation
  int InitEncode(const VideoCodec* codec_settings,
                 const Settings& settings) override;

  int RegisterEncodeCompleteCallback(
      EncodedImageCallback* callback) override;

  int Release() override;

  int Encode(const VideoFrame& frame,
             const std::vector<VideoFrameType>* frame_types) override;

  void SetRates(const RateControlParameters& parameters) override;

  EncoderInfo GetEncoderInfo() const override;

 private:
  const Environment env_;
  EncodedImageCallback* callback_ = nullptr;

  // FFmpeg/QSV components
  const AVCodec* codec_ = nullptr;
  AVCodecContext* codec_ctx_ = nullptr;
  AVBufferRef* hw_device_ctx_ = nullptr;
  AVBufferRef* hw_frames_ctx_ = nullptr;

  // Encoder settings
  int width_ = 0;
  int height_ = 0;
  int bitrate_kbps_ = 0;
  int fps_ = 30;

  bool initialized_ = false;
  int64_t frame_count_ = 0;

  // Helper methods
  int InitHwDevice();
  int InitHwFramesContext();
  AVFrame* CreateHwFrame();
  int UploadFrameToGpu(AVFrame* hw_frame, const VideoFrameBuffer* buffer);
};

}  // namespace webrtc

#endif  // EXAMPLES_PEERCONNECTION_CLIENT_QSV_VP9_ENCODER_H_

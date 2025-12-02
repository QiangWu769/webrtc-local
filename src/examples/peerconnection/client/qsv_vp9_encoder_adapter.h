/*
 * QSV VP9 Encoder Adapter for VideoEncoderFactoryTemplate
 */

#ifndef EXAMPLES_PEERCONNECTION_CLIENT_QSV_VP9_ENCODER_ADAPTER_H_
#define EXAMPLES_PEERCONNECTION_CLIENT_QSV_VP9_ENCODER_ADAPTER_H_

#include <memory>
#include <vector>

#include "api/environment/environment.h"
#include "api/video_codecs/sdp_video_format.h"
#include "api/video_codecs/video_encoder.h"
#include "api/video_codecs/video_encoder_factory.h"
#include "absl/types/optional.h"

namespace webrtc {

class QsvVp9EncoderAdapter {
 public:
  // Returns list of supported formats if QSV is available
  static std::vector<SdpVideoFormat> SupportedFormats();

  // Creates QSV VP9 encoder instance
  static std::unique_ptr<VideoEncoder> CreateEncoder(
      const Environment& env,
      const SdpVideoFormat& format);

  // Check if scalability mode is supported
  static bool IsScalabilityModeSupported(ScalabilityMode scalability_mode);

 private:
  // Checks if QSV hardware is available (cached)
  static bool IsQsvAvailable();
};

}  // namespace webrtc

#endif  // EXAMPLES_PEERCONNECTION_CLIENT_QSV_VP9_ENCODER_ADAPTER_H_

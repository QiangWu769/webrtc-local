/*
 *  Copyright 2012 The WebRTC Project Authors. All rights reserved.
 *
 *  Use of this source code is governed by a BSD-style license
 *  that can be found in the LICENSE file in the root of the source
 *  tree. An additional intellectual property rights grant can be found
 *  in the file PATENTS.  All contributing project authors may
 *  be found in the AUTHORS file in the root of the source tree.
 */

#include "examples/peerconnection/client/conductor.h"

#include <stddef.h>
#include <stdint.h>

#include <chrono>
#include <fstream>
#include <functional>
#include <memory>
#include <thread>
#include <utility>
#include <vector>

#include "absl/memory/memory.h"
#include "absl/types/optional.h"
#include "api/audio/audio_mixer.h"
#include "api/audio_codecs/audio_decoder_factory.h"
#include "api/audio_codecs/audio_encoder_factory.h"
#include "api/audio_codecs/builtin_audio_decoder_factory.h"
#include "api/audio_codecs/builtin_audio_encoder_factory.h"
#include "api/audio_options.h"
#include "api/transport/bitrate_settings.h"
#include "api/create_peerconnection_factory.h"
#include "api/rtp_sender_interface.h"
#include "api/task_queue/default_task_queue_factory.h"
#include "api/task_queue/queued_task.h"
#include "api/units/time_delta.h"
#include "api/video_codecs/builtin_video_decoder_factory.h"
#include "api/video_codecs/builtin_video_encoder_factory.h"
#include "api/video_codecs/video_decoder_factory.h"
#include "api/video_codecs/video_encoder_factory.h"
#include "examples/peerconnection/client/defaults.h"
#include "modules/audio_device/include/audio_device.h"
#include "modules/audio_device/include/test_audio_device.h"
#include "modules/audio_processing/include/audio_processing.h"
#include "modules/video_capture/video_capture.h"
#include "modules/video_capture/video_capture_factory.h"
#include "p2p/base/port_allocator.h"
#include "pc/video_track_source.h"
#include "rtc_base/checks.h"
#include "rtc_base/logging.h"
#include "rtc_base/ref_counted_object.h"
#include "rtc_base/rtc_certificate_generator.h"
#include "rtc_base/strings/json.h"
#include "rtc_base/thread.h"
#include "test/frame_generator_capturer.h"
#include "api/test/create_frame_generator.h"
#include "test/vcm_capturer.h"
// Professional video frame writer (same as serverless)
#include "test/testsupport/video_frame_writer.h"

namespace {
// Names used for a IceCandidate JSON object.
const char kCandidateSdpMidName[] = "sdpMid";
const char kCandidateSdpMlineIndexName[] = "sdpMLineIndex";
const char kCandidateSdpName[] = "candidate";

// Names used for a SessionDescription JSON object.
const char kSessionDescriptionTypeName[] = "type";
const char kSessionDescriptionSdpName[] = "sdp";

class DummySetSessionDescriptionObserver
    : public webrtc::SetSessionDescriptionObserver {
 public:
  static DummySetSessionDescriptionObserver* Create() {
    return new rtc::RefCountedObject<DummySetSessionDescriptionObserver>();
  }
  virtual void OnSuccess() { RTC_LOG(INFO) << __FUNCTION__; }
  virtual void OnFailure(webrtc::RTCError error) {
    RTC_LOG(INFO) << __FUNCTION__ << " " << ToString(error.type()) << ": "
                  << error.message();
  }
};

// 完成回调类型定义
// Simplified approach like serverless version - no auto-exit

class FrameGeneratorTrackSource : public webrtc::VideoTrackSource {
 public:
  using CompletionCallback = std::function<void()>;
  
  static rtc::scoped_refptr<FrameGeneratorTrackSource> Create(
      std::shared_ptr<rtc::Event> audio_started_,
      CompletionCallback completion_callback = nullptr) {
    auto alphaCCConfig = webrtc::GetAlphaCCConfig();
    
    RTC_LOG(INFO) << "🎬 Loading video file: " << alphaCCConfig->video_file_path;
    RTC_LOG(INFO) << "📐 Video resolution: " << alphaCCConfig->video_width 
                 << "x" << alphaCCConfig->video_height << " @ " << alphaCCConfig->video_fps << "fps";
    
    // Creat an FrameGenerator, responsible for reading yuv files
    std::unique_ptr<webrtc::test::FrameGeneratorInterface> yuv_frame_generator(
        webrtc::test::CreateFromYuvFileFrameGenerator(
            std::vector<std::string>{
                alphaCCConfig->video_file_path}, /* file_path */
            alphaCCConfig->video_width,          /*video_width */
            alphaCCConfig->video_height,         /*video_height*/
            1 /*frame_repeat_count*/));
    
    if (!yuv_frame_generator) {
      RTC_LOG(LS_ERROR) << "❌ Failed to create YUV frame generator for file: " 
                       << alphaCCConfig->video_file_path;
      return nullptr;
    }
    
    RTC_LOG(INFO) << "✅ YUV frame generator created successfully";

    // Use FrameGenerator to periodically capture frames
    RTC_LOG(INFO) << "🎥 Creating frame capturer with FPS: " << alphaCCConfig->video_fps;
    std::unique_ptr<webrtc::test::FrameGeneratorCapturer> capturer(
        new webrtc::test::FrameGeneratorCapturer(
            webrtc::Clock::GetRealTimeClock(),        /* clock */
            std::move(yuv_frame_generator),           /* frame_generator */
            alphaCCConfig->video_fps,                 /* target_fps*/
            *webrtc::CreateDefaultTaskQueueFactory())); /* task_queue_factory */

    if (!capturer) {
      RTC_LOG(LS_ERROR) << "❌ Failed to create frame capturer";
      return nullptr;
    }
    
    RTC_LOG(INFO) << "✅ Frame capturer created successfully";
    auto track_source = new rtc::RefCountedObject<FrameGeneratorTrackSource>(
        std::move(capturer), audio_started_, completion_callback);
    
    return track_source;
  }

  // Simplified version - no auto-exit monitoring

 protected:
  explicit FrameGeneratorTrackSource(
      std::unique_ptr<webrtc::test::FrameGeneratorCapturer> capturer,
      std::shared_ptr<rtc::Event> audio_started_,
      CompletionCallback completion_callback)
      : VideoTrackSource(/*remote=*/false), 
        capturer_(std::move(capturer)),
        completion_callback_(completion_callback),
        completion_notified_(false) {
    // Creat a thread that waits for the audio capturer thread
    // to start
    std::thread waiting_for_audio_started_([this, audio_started_]() {
      auto alphaCCConfig = webrtc::GetAlphaCCConfig();

      // Only wait for audio to start when use audio file
      if (alphaCCConfig->audio_source_option ==
          webrtc::AlphaCCConfig::AudioSourceOption::kAudioFile) {
        audio_started_->Wait(rtc::Event::kForever);
      }
      if (capturer_ && capturer_->Init()) {
        capturer_->Start();
        // Start transmission completion monitoring like native WebRTC
        if (completion_callback_) {
          StartTransmissionMonitoring();
        }
      }
    });
    // Detach() instead of Join(), for non-blocking
    waiting_for_audio_started_.detach();
  }
  
  void StartTransmissionMonitoring() {
    // ✅ Simple fixed-time transmission like native WebRTC (consistent behavior)
    // Both AlphaRTC and native WebRTC use 30 seconds fixed transmission time
    
    class FixedTimeTransmissionTask : public webrtc::QueuedTask {
    public:
      FixedTimeTransmissionTask(FrameGeneratorTrackSource* source) : source_(source) {}
      
      bool Run() override {
        if (!source_->completion_notified_ && source_->completion_callback_) {
          source_->completion_notified_ = true;
          RTC_LOG(LS_INFO) << "✅ AlphaRTC video transmission completed after 30 seconds (fixed time)";
          source_->completion_callback_();
        }
        return true; // Delete the task after execution
      }
      
    private:
      FrameGeneratorTrackSource* source_;
    };
    
    // Use configurable transmission time from alphacc_config
    auto alphaCCConfig = webrtc::GetAlphaCCConfig();
    int transmission_time_ms = alphaCCConfig->conn_autoclose * 1000; // Convert seconds to milliseconds
    RTC_LOG(LS_INFO) << "📅 AlphaRTC configured transmission time: " << alphaCCConfig->conn_autoclose << " seconds";
    
    webrtc::TaskQueueBase::Current()->PostDelayedTask(
        std::make_unique<FixedTimeTransmissionTask>(this), transmission_time_ms);
  }


 private:
  rtc::VideoSourceInterface<webrtc::VideoFrame>* source() override {
    return capturer_.get();
  }
  


  std::unique_ptr<webrtc::test::FrameGeneratorCapturer> capturer_;
  CompletionCallback completion_callback_;
  bool completion_notified_;
};

class CapturerTrackSource : public webrtc::VideoTrackSource {
 public:
  static rtc::scoped_refptr<CapturerTrackSource> Create() {
    const size_t kWidth = 640;
    const size_t kHeight = 480;
    const size_t kFps = 30;
    std::unique_ptr<webrtc::test::VcmCapturer> capturer;
    std::unique_ptr<webrtc::VideoCaptureModule::DeviceInfo> info(
        webrtc::VideoCaptureFactory::CreateDeviceInfo());
    if (!info) {
      return nullptr;
    }
    int num_devices = info->NumberOfDevices();
    for (int i = 0; i < num_devices; ++i) {
      capturer = absl::WrapUnique(
          webrtc::test::VcmCapturer::Create(kWidth, kHeight, kFps, i));
      if (capturer) {
        return new rtc::RefCountedObject<CapturerTrackSource>(
            std::move(capturer));
      }
    }

    return nullptr;
  }

 protected:
  explicit CapturerTrackSource(
      std::unique_ptr<webrtc::test::VcmCapturer> capturer)
      : VideoTrackSource(/*remote=*/false), capturer_(std::move(capturer)) {}

 private:
  rtc::VideoSourceInterface<webrtc::VideoFrame>* source() override {
    return capturer_.get();
  }
  std::unique_ptr<webrtc::test::VcmCapturer> capturer_;
};

}  // namespace

Conductor::Conductor(PeerConnectionClient* client, MainWindow* main_wnd)
    : peer_id_(-1),
      loopback_(false),
      client_(client),
      main_wnd_(main_wnd),
      alphacc_config_(webrtc::GetAlphaCCConfig()),
      audio_started_(std::make_shared<rtc::Event>()) {
  // Initialize professional video frame writer (same as serverless)
  if (alphacc_config_->save_to_file) {
    frame_writer_ = absl::make_unique<webrtc::test::Y4mVideoFrameWriterImpl>(
        alphacc_config_->video_output_path, 
        alphacc_config_->video_output_width,
        alphacc_config_->video_output_height,
        alphacc_config_->video_output_fps);
    RTC_LOG(INFO) << "🎬 Professional video writer initialized: " 
                  << alphacc_config_->video_output_path << " ("
                  << alphacc_config_->video_output_width << "x" 
                  << alphacc_config_->video_output_height << " @ "
                  << alphacc_config_->video_output_fps << "fps)";
  } else {
    frame_writer_ = nullptr;
  }
  client_->RegisterObserver(this);
  main_wnd->RegisterObserver(this);
}

Conductor::~Conductor() {
  RTC_DCHECK(!peer_connection_);
}

bool Conductor::connection_active() const {
  return peer_connection_ != nullptr;
}

void Conductor::Close() {
  client_->SignOut();
  DeletePeerConnection();
}

bool Conductor::InitializePeerConnection() {
  RTC_DCHECK(!peer_connection_factory_);
  RTC_DCHECK(!peer_connection_);

  auto task_queue_factory = webrtc::CreateDefaultTaskQueueFactory();
  rtc::scoped_refptr<webrtc::AudioDeviceModule> audio_device_module = nullptr;

  using AudioSourceOption = webrtc::AlphaCCConfig::AudioSourceOption;
  // Use audio file for audio input
  if (alphacc_config_->audio_source_option == AudioSourceOption::kAudioFile) {
    auto capturer = webrtc::TestAudioDeviceModule::CreateWavFileReader(
        alphacc_config_->audio_file_path, true);

    std::unique_ptr<webrtc::TestAudioDeviceModule::Renderer> renderer;
    if (alphacc_config_->save_to_file) {
      renderer = webrtc::TestAudioDeviceModule::CreateWavFileWriter(
          alphacc_config_->audio_output_path,
          capturer.get()->SamplingFrequency(), capturer.get()->NumChannels());
    } else {
      renderer = webrtc::TestAudioDeviceModule::CreateDiscardRenderer(
          8000 /*sampling frequecy, unused*/, 2 /*num_channels, ununsed*/);
    }

    audio_device_module = webrtc::TestAudioDeviceModule::Create(
        task_queue_factory.get(), std::move(capturer), std::move(renderer),
        audio_started_);
  } else if (alphacc_config_->audio_source_option ==
             AudioSourceOption::kMicrophone) {
    audio_device_module = nullptr;
  }

  peer_connection_factory_ = webrtc::CreatePeerConnectionFactory(
      nullptr /* network_thread */, nullptr /* worker_thread */,
      nullptr /* signaling_thread */, audio_device_module /* default_adm */,
      webrtc::CreateBuiltinAudioEncoderFactory(),
      webrtc::CreateBuiltinAudioDecoderFactory(),
      webrtc::CreateBuiltinVideoEncoderFactory(),
      webrtc::CreateBuiltinVideoDecoderFactory(), nullptr /* audio_mixer */,
      nullptr /* audio_processing */);

  if (!peer_connection_factory_) {
    main_wnd_->MessageBox("Error", "Failed to initialize PeerConnectionFactory",
                          true);
    DeletePeerConnection();
    return false;
  }

  if (!CreatePeerConnection(/*dtls=*/true)) {
    main_wnd_->MessageBox("Error", "CreatePeerConnection failed", true);
    DeletePeerConnection();
  }

  AddTracks();

  // Start the timer for auto close (use same mechanism as native WebRTC)
  if (alphacc_config_->conn_autoclose != kAutoCloseDisableValue) {
    RTC_LOG(LS_INFO) << "📅 AlphaRTC starting auto-close timer: " << alphacc_config_->conn_autoclose << " seconds";
    
    // Create a QueuedTask for AlphaRTC's API
    class AutoCloseTask : public webrtc::QueuedTask {
    public:
      AutoCloseTask(Conductor* conductor) : conductor_(conductor) {}
      bool Run() override {
        RTC_LOG(LS_INFO) << "⏰ AlphaRTC auto-close timer triggered, exiting program";
        // Directly exit to avoid reconnection logic
        conductor_->DisconnectFromServer();
        exit(0);
        return true; // Delete the task after execution
      }
    private:
      Conductor* conductor_;
    };
    
    rtc::Thread::Current()->PostDelayedTask(
        std::unique_ptr<webrtc::QueuedTask>(new AutoCloseTask(this)),
        alphacc_config_->conn_autoclose * 1000); // milliseconds
  }

  return peer_connection_ != nullptr;
}

bool Conductor::ReinitializePeerConnectionForLoopback() {
  loopback_ = true;
  std::vector<rtc::scoped_refptr<webrtc::RtpSenderInterface>> senders =
      peer_connection_->GetSenders();
  peer_connection_ = nullptr;
  if (CreatePeerConnection(/*dtls=*/false)) {
    for (const auto& sender : senders) {
      peer_connection_->AddTrack(sender->track(), sender->stream_ids());
    }
    peer_connection_->CreateOffer(
        this, webrtc::PeerConnectionInterface::RTCOfferAnswerOptions());
  }
  return peer_connection_ != nullptr;
}

bool Conductor::CreatePeerConnection(bool dtls) {
  RTC_DCHECK(peer_connection_factory_);
  RTC_DCHECK(!peer_connection_);

  webrtc::PeerConnectionInterface::RTCConfiguration config;
  config.sdp_semantics = webrtc::SdpSemantics::kUnifiedPlan;
  config.enable_dtls_srtp = dtls;
  webrtc::PeerConnectionInterface::IceServer server;
  server.uri = GetPeerConnectionString();
  config.servers.push_back(server);

  peer_connection_ = peer_connection_factory_->CreatePeerConnection(
      config, nullptr, nullptr, this);
  return peer_connection_ != nullptr;
}

void Conductor::DeletePeerConnection() {
  main_wnd_->StopLocalRenderer();
  main_wnd_->StopRemoteRenderer();
  peer_connection_ = nullptr;
  peer_connection_factory_ = nullptr;
  peer_id_ = -1;
  loopback_ = false;
}

void Conductor::EnsureStreamingUI() {
  RTC_DCHECK(peer_connection_);
  if (main_wnd_->IsWindow()) {
    if (main_wnd_->current_ui() != MainWindow::STREAMING)
      main_wnd_->SwitchToStreamingUI();
  }
}

//
// PeerConnectionObserver implementation.
//

// Professional video frame writer integrated (using serverless approach)

void Conductor::OnAddTrack(
    rtc::scoped_refptr<webrtc::RtpReceiverInterface> receiver,
    const std::vector<rtc::scoped_refptr<webrtc::MediaStreamInterface>>&
        streams) {
  RTC_LOG(INFO) << __FUNCTION__ << " " << receiver->id();
  
  // Professional video frame handling (same as serverless)
  main_wnd_->QueueUIThreadCallback(NEW_TRACK_ADDED,
                                   receiver->track().release());
}

void Conductor::OnRemoveTrack(
    rtc::scoped_refptr<webrtc::RtpReceiverInterface> receiver) {
  RTC_LOG(INFO) << __FUNCTION__ << " " << receiver->id();
  main_wnd_->QueueUIThreadCallback(TRACK_REMOVED, receiver->track().release());
}

void Conductor::OnIceCandidate(const webrtc::IceCandidateInterface* candidate) {
  RTC_LOG(INFO) << __FUNCTION__ << " " << candidate->sdp_mline_index();
  // For loopback test. To save some connecting delay.
  if (loopback_) {
    if (!peer_connection_->AddIceCandidate(candidate)) {
      RTC_LOG(WARNING) << "Failed to apply the received candidate";
    }
    return;
  }

  Json::StyledWriter writer;
  Json::Value jmessage;

  jmessage[kCandidateSdpMidName] = candidate->sdp_mid();
  jmessage[kCandidateSdpMlineIndexName] = candidate->sdp_mline_index();
  std::string sdp;
  if (!candidate->ToString(&sdp)) {
    RTC_LOG(LS_ERROR) << "Failed to serialize candidate";
    return;
  }
  jmessage[kCandidateSdpName] = sdp;
  SendMessage(writer.write(jmessage));
}

//
// PeerConnectionClientObserver implementation.
//

void Conductor::OnSignedIn() {
  RTC_LOG(INFO) << __FUNCTION__;
  main_wnd_->SwitchToPeerList(client_->peers());
}

void Conductor::OnDisconnected() {
  RTC_LOG(INFO) << __FUNCTION__;

  DeletePeerConnection();

  if (main_wnd_->IsWindow())
    main_wnd_->SwitchToConnectUI();
}

void Conductor::OnPeerConnected(int id, const std::string& name) {
  RTC_LOG(INFO) << __FUNCTION__;

  // Refresh the list if we're showing it.
  if (main_wnd_->current_ui() == MainWindow::LIST_PEERS)
    main_wnd_->SwitchToPeerList(client_->peers());
}

void Conductor::OnPeerDisconnected(int id) {
  RTC_LOG(INFO) << __FUNCTION__;
  if (id == peer_id_) {
    RTC_LOG(INFO) << "Our peer disconnected";
    main_wnd_->QueueUIThreadCallback(PEER_CONNECTION_CLOSED, NULL);
  } else {
    // Refresh the list if we're showing it.
    if (main_wnd_->current_ui() == MainWindow::LIST_PEERS)
      main_wnd_->SwitchToPeerList(client_->peers());
  }
}

void Conductor::OnMessageFromPeer(int peer_id, const std::string& message) {
  RTC_DCHECK(peer_id_ == peer_id || peer_id_ == -1);
  RTC_DCHECK(!message.empty());

  if (!peer_connection_.get()) {
    RTC_DCHECK(peer_id_ == -1);
    peer_id_ = peer_id;

    if (!InitializePeerConnection()) {
      RTC_LOG(LS_ERROR) << "Failed to initialize our PeerConnection instance";
      client_->SignOut();
      return;
    }
  } else if (peer_id != peer_id_) {
    RTC_DCHECK(peer_id_ != -1);
    RTC_LOG(WARNING)
        << "Received a message from unknown peer while already in a "
           "conversation with a different peer.";
    return;
  }

  Json::Reader reader;
  Json::Value jmessage;
  if (!reader.parse(message, jmessage)) {
    RTC_LOG(WARNING) << "Received unknown message. " << message;
    return;
  }
  std::string type_str;
  std::string json_object;

  rtc::GetStringFromJsonObject(jmessage, kSessionDescriptionTypeName,
                               &type_str);
  if (!type_str.empty()) {
    if (type_str == "offer-loopback") {
      // This is a loopback call.
      // Recreate the peerconnection with DTLS disabled.
      if (!ReinitializePeerConnectionForLoopback()) {
        RTC_LOG(LS_ERROR) << "Failed to initialize our PeerConnection instance";
        DeletePeerConnection();
        client_->SignOut();
      }
      return;
    }
    absl::optional<webrtc::SdpType> type_maybe =
        webrtc::SdpTypeFromString(type_str);
    if (!type_maybe) {
      RTC_LOG(LS_ERROR) << "Unknown SDP type: " << type_str;
      return;
    }
    webrtc::SdpType type = *type_maybe;
    std::string sdp;
    if (!rtc::GetStringFromJsonObject(jmessage, kSessionDescriptionSdpName,
                                      &sdp)) {
      RTC_LOG(WARNING) << "Can't parse received session description message.";
      return;
    }
    webrtc::SdpParseError error;
    std::unique_ptr<webrtc::SessionDescriptionInterface> session_description =
        webrtc::CreateSessionDescription(type, sdp, &error);
    if (!session_description) {
      RTC_LOG(WARNING) << "Can't parse received session description message. "
                          "SdpParseError was: "
                       << error.description;
      return;
    }
    RTC_LOG(INFO) << " Received session description :" << message;
    peer_connection_->SetRemoteDescription(
        DummySetSessionDescriptionObserver::Create(),
        session_description.release());
    if (type == webrtc::SdpType::kOffer) {
      peer_connection_->CreateAnswer(
          this, webrtc::PeerConnectionInterface::RTCOfferAnswerOptions());
    }
  } else {
    std::string sdp_mid;
    int sdp_mlineindex = 0;
    std::string sdp;
    if (!rtc::GetStringFromJsonObject(jmessage, kCandidateSdpMidName,
                                      &sdp_mid) ||
        !rtc::GetIntFromJsonObject(jmessage, kCandidateSdpMlineIndexName,
                                   &sdp_mlineindex) ||
        !rtc::GetStringFromJsonObject(jmessage, kCandidateSdpName, &sdp)) {
      RTC_LOG(WARNING) << "Can't parse received message.";
      return;
    }
    webrtc::SdpParseError error;
    std::unique_ptr<webrtc::IceCandidateInterface> candidate(
        webrtc::CreateIceCandidate(sdp_mid, sdp_mlineindex, sdp, &error));
    if (!candidate.get()) {
      RTC_LOG(WARNING) << "Can't parse received candidate message. "
                          "SdpParseError was: "
                       << error.description;
      return;
    }
    if (!peer_connection_->AddIceCandidate(candidate.get())) {
      RTC_LOG(WARNING) << "Failed to apply the received candidate";
      return;
    }
    RTC_LOG(INFO) << " Received candidate :" << message;
  }
}

void Conductor::OnMessageSent(int err) {
  // Process the next pending message if any.
  main_wnd_->QueueUIThreadCallback(SEND_MESSAGE_TO_PEER, NULL);
}

void Conductor::OnServerConnectionFailure() {
  main_wnd_->MessageBox("Error", ("Failed to connect to " + server_).c_str(),
                        true);
}

//
// MainWndCallback implementation.
//

void Conductor::StartLogin(const std::string& server, int port) {
  if (client_->is_connected())
    return;
  server_ = server;
  client_->Connect(server, port, GetPeerName());
}

void Conductor::DisconnectFromServer() {
  if (client_->is_connected())
    client_->SignOut();
}

void Conductor::ConnectToPeer(int peer_id) {
  RTC_DCHECK(peer_id_ == -1);
  RTC_DCHECK(peer_id != -1);

  if (peer_connection_.get()) {
    main_wnd_->MessageBox(
        "Error", "We only support connecting to one peer at a time", true);
    return;
  }

  if (InitializePeerConnection()) {
    peer_id_ = peer_id;
    peer_connection_->CreateOffer(
        this, webrtc::PeerConnectionInterface::RTCOfferAnswerOptions());
  } else {
    main_wnd_->MessageBox("Error", "Failed to initialize PeerConnection", true);
  }
}

void Conductor::AddTracks() {
  if (!peer_connection_->GetSenders().empty()) {
    return;  // Already added tracks.
  }

  // Add audio track like serverless version (WebRTC may need it for proper initialization)
  rtc::scoped_refptr<webrtc::AudioTrackInterface> audio_track(
      peer_connection_factory_->CreateAudioTrack(
          kAudioLabel, peer_connection_factory_->CreateAudioSource(
                           cricket::AudioOptions())));
  auto result_or_error = peer_connection_->AddTrack(audio_track, {kStreamId});
  if (!result_or_error.ok()) {
    RTC_LOG(LS_ERROR) << "Failed to add audio track to PeerConnection: "
                      << result_or_error.error().message();
  } else {
    RTC_LOG(INFO) << "✅ Audio track added (like serverless version)";
  }

  rtc::scoped_refptr<webrtc::VideoTrackSource> video_device;
  using VideoSourceOption = webrtc::AlphaCCConfig::VideoSourceOption;

  switch (alphacc_config_->video_source_option) {
    case VideoSourceOption::kVideoDisabled:
      video_device = webrtc::FakeVideoTrackSource::Create();
      break;
    case VideoSourceOption::kWebcam:
      video_device = CapturerTrackSource::Create();
      break;
    case VideoSourceOption::kVideoFile: {
      RTC_LOG(INFO) << "🎞️ Creating video file source (serverless style)...";
      video_device = FrameGeneratorTrackSource::Create(audio_started_);
      if (video_device) {
        RTC_LOG(INFO) << "✅ Video file source created successfully";
      } else {
        RTC_LOG(LS_ERROR) << "❌ Failed to create video file source";
      }
      break;
    }
    default:
      RTC_NOTREACHED();
  }

  if (video_device) {
    RTC_LOG(INFO) << "🎬 Creating video track with source...";
    video_track_ = peer_connection_factory_->CreateVideoTrack(kVideoLabel, video_device);
    
    if (!video_track_) {
      RTC_LOG(LS_ERROR) << "❌ Failed to create video track";
      return;
    }
    
    RTC_LOG(INFO) << "✅ Video track created, starting local renderer...";
    main_wnd_->StartLocalRenderer(video_track_);
    
    // AlphaRTC uses different bitrate management than native WebRTC  
    // Let WebRTC handle bitrate automatically (like native WebRTC examples)
    RTC_LOG(INFO) << "📊 AlphaRTC config available: max=" << alphacc_config_->video_max_bitrate_kbps 
                 << "kbps, min=" << alphacc_config_->video_min_bitrate_kbps 
                 << "kbps, start=" << alphacc_config_->video_start_bitrate_kbps << "kbps";
    RTC_LOG(INFO) << "⚙️ Using AlphaRTC automatic bitrate management...";

    RTC_LOG(INFO) << "📡 Adding video track to peer connection...";
    auto result_or_error = peer_connection_->AddTrack(video_track_, {kStreamId});
    if (!result_or_error.ok()) {
      RTC_LOG(LS_ERROR) << "Failed to add video track to PeerConnection: "
                        << result_or_error.error().message();
    } else {
      RTC_LOG(INFO) << "✅ Video track added successfully";
    }
  } else {
    RTC_LOG(LS_ERROR) << "OpenVideoCaptureDevice failed";
  }

  main_wnd_->SwitchToStreamingUI();
}

void Conductor::DisconnectFromCurrentPeer() {
  RTC_LOG(INFO) << __FUNCTION__;
  if (peer_connection_.get()) {
    client_->SendHangUp(peer_id_);
    DeletePeerConnection();
  }

  if (main_wnd_->IsWindow())
    main_wnd_->SwitchToPeerList(client_->peers());
}

void Conductor::OnFrameCallback(const webrtc::VideoFrame& video_frame) {
  if (alphacc_config_->save_to_file && frame_writer_) {
    frame_writer_->WriteFrame(video_frame);
  }
}

void Conductor::UIThreadCallback(int msg_id, void* data) {
  switch (msg_id) {
    case PEER_CONNECTION_CLOSED:
      RTC_LOG(INFO) << "PEER_CONNECTION_CLOSED";
      DeletePeerConnection();

      if (main_wnd_->IsWindow()) {
        if (client_->is_connected()) {
          main_wnd_->SwitchToPeerList(client_->peers());
        } else {
          main_wnd_->SwitchToConnectUI();
        }
      } else {
        DisconnectFromServer();
      }
      break;

    case SEND_MESSAGE_TO_PEER: {
      RTC_LOG(INFO) << "SEND_MESSAGE_TO_PEER";
      std::string* msg = reinterpret_cast<std::string*>(data);
      if (msg) {
        // For convenience, we always run the message through the queue.
        // This way we can be sure that messages are sent to the server
        // in the same order they were signaled without much hassle.
        pending_messages_.push_back(msg);
      }

      if (!pending_messages_.empty() && !client_->IsSendingMessage()) {
        msg = pending_messages_.front();
        pending_messages_.pop_front();

        if (!client_->SendToPeer(peer_id_, *msg) && peer_id_ != -1) {
          RTC_LOG(LS_ERROR) << "SendToPeer failed";
          DisconnectFromServer();
        }
        delete msg;
      }

      if (!peer_connection_.get())
        peer_id_ = -1;

      break;
    }

    case NEW_TRACK_ADDED: {
      auto* track = reinterpret_cast<webrtc::MediaStreamTrackInterface*>(data);
      if (track->kind() == webrtc::MediaStreamTrackInterface::kVideoKind) {
        auto* video_track = static_cast<webrtc::VideoTrackInterface*>(track);
        main_wnd_->StartRemoteRenderer(video_track);
      }
      track->Release();
      break;
    }

    case TRACK_REMOVED: {
      // Remote peer stopped sending a track.
      auto* track = reinterpret_cast<webrtc::MediaStreamTrackInterface*>(data);
      track->Release();
      break;
    }

    default:
      RTC_NOTREACHED();
      break;
  }
}

void Conductor::OnSuccess(webrtc::SessionDescriptionInterface* desc) {
  peer_connection_->SetLocalDescription(
      DummySetSessionDescriptionObserver::Create(), desc);

  std::string sdp;
  desc->ToString(&sdp);

  // For loopback test. To save some connecting delay.
  if (loopback_) {
    // Replace message type from "offer" to "answer"
    std::unique_ptr<webrtc::SessionDescriptionInterface> session_description =
        webrtc::CreateSessionDescription(webrtc::SdpType::kAnswer, sdp);
    peer_connection_->SetRemoteDescription(
        DummySetSessionDescriptionObserver::Create(),
        session_description.release());
    return;
  }

  Json::StyledWriter writer;
  Json::Value jmessage;
  jmessage[kSessionDescriptionTypeName] =
      webrtc::SdpTypeToString(desc->GetType());
  jmessage[kSessionDescriptionSdpName] = sdp;
  SendMessage(writer.write(jmessage));
}

void Conductor::OnFailure(webrtc::RTCError error) {
  RTC_LOG(LERROR) << ToString(error.type()) << ": " << error.message();
}

void Conductor::SendMessage(const std::string& json_object) {
  std::string* msg = new std::string(json_object);
  main_wnd_->QueueUIThreadCallback(SEND_MESSAGE_TO_PEER, msg);
}



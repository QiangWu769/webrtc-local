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

 #include <cstddef>
 #include <fstream>
 #include <memory>
 #include <optional>
 #include <string>
 #include <utility>
 #include <vector>
 
 #include "absl/base/nullability.h"
 #include "absl/flags/declare.h"
 #include "absl/flags/flag.h"
 #include "absl/memory/memory.h"
 #include "api/audio_codecs/builtin_audio_decoder_factory.h"
 #include "api/units/time_delta.h"
 #include "api/audio_codecs/builtin_audio_encoder_factory.h"
 #include "api/audio_options.h"
 #include "api/create_modular_peer_connection_factory.h"
 #include "modules/audio_device/audio_device_impl.h"
 #include "modules/audio_device/dummy/audio_device_dummy.h"
 #include "api/enable_media.h"
 #include "api/environment/environment.h"
 #include "api/jsep.h"
 #include "api/make_ref_counted.h"
 #include "api/media_stream_interface.h"
 #include "api/peer_connection_interface.h"
 #include "api/rtc_error.h"
 #include "api/rtp_receiver_interface.h"
 #include "api/rtp_sender_interface.h"
 #include "api/scoped_refptr.h"
 #include "api/stats/rtc_stats_collector_callback.h"
 #include "api/stats/rtc_stats_report.h"
 #include "api/task_queue/task_queue_factory.h"
 #include "api/task_queue/default_task_queue_factory.h"
 #include "rtc_base/ref_count.h"
 #include "rtc_base/ref_counted_object.h"
 #include "api/test/create_frame_generator.h"
 #include "rtc_base/task_utils/repeating_task.h"
 #include "api/video/video_frame.h"
 #include "api/video/video_source_interface.h"
 #include "api/video_codecs/video_decoder_factory_template.h"
 #include "api/video_codecs/video_decoder_factory_template_dav1d_adapter.h"
 #include "api/video_codecs/video_decoder_factory_template_libvpx_vp8_adapter.h"
 #include "api/video_codecs/video_decoder_factory_template_libvpx_vp9_adapter.h"
 #include "api/video_codecs/video_decoder_factory_template_open_h264_adapter.h"
 #include "api/video_codecs/video_encoder_factory_template.h"
 #include "api/video_codecs/video_encoder_factory_template_libaom_av1_adapter.h"
 #include "api/video_codecs/video_encoder_factory_template_libvpx_vp8_adapter.h"
 #include "api/video_codecs/video_encoder_factory_template_libvpx_vp9_adapter.h"
 #include "api/video_codecs/video_encoder_factory_template_open_h264_adapter.h"
 #include "examples/peerconnection/client/defaults.h"
 #include "examples/peerconnection/client/main_wnd.h"
 #include "examples/peerconnection/client/peer_connection_client.h"
 #include "examples/peerconnection/client/webrtc_config.h"
 
 // Declare flags defined in flag_defs.h
 ABSL_DECLARE_FLAG(bool, use_video_file);
 ABSL_DECLARE_FLAG(std::string, video_file_path);
 ABSL_DECLARE_FLAG(int, video_width);
 ABSL_DECLARE_FLAG(int, video_height);
 ABSL_DECLARE_FLAG(int, video_fps);
 ABSL_DECLARE_FLAG(std::string, config);
 #include "json/reader.h"
 #include "json/value.h"
 #include "json/writer.h"
 #include "modules/video_capture/video_capture.h"
 #include "modules/video_capture/video_capture_factory.h"
 #include "pc/video_track_source.h"
 #include "rtc_base/checks.h"
#include "rtc_base/logging.h"
#include "rtc_base/strings/json.h"
#include "rtc_base/thread.h"
 #include "system_wrappers/include/clock.h"
 #include "test/frame_generator_capturer.h"
 #include "test/platform_video_capturer.h"
 #include "test/test_video_capturer.h"
 
 namespace {
 using webrtc::test::TestVideoCapturer;
 
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
   static webrtc::scoped_refptr<DummySetSessionDescriptionObserver> Create() {
     return webrtc::make_ref_counted<DummySetSessionDescriptionObserver>();
   }
   void OnSuccess() override { RTC_LOG(LS_INFO) << __FUNCTION__; }
   void OnFailure(webrtc::RTCError error) override {
     RTC_LOG(LS_INFO) << __FUNCTION__ << " " << ToString(error.type()) << ": "
                      << error.message();
   }
 };
 
 std::unique_ptr<TestVideoCapturer> CreateCapturer(
     webrtc::TaskQueueFactory& task_queue_factory) {
   const size_t kWidth = 640;
   const size_t kHeight = 480;
   const size_t kFps = 30;
   std::unique_ptr<webrtc::VideoCaptureModule::DeviceInfo> info(
       webrtc::VideoCaptureFactory::CreateDeviceInfo());
   if (!info) {
     return nullptr;
   }
   int num_devices = info->NumberOfDevices();
   for (int i = 0; i < num_devices; ++i) {
     std::unique_ptr<TestVideoCapturer> capturer =
         webrtc::test::CreateVideoCapturer(kWidth, kHeight, kFps, i);
     if (capturer) {
       return capturer;
     }
   }
   auto frame_generator = webrtc::test::CreateSquareFrameGenerator(
       kWidth, kHeight, std::nullopt, std::nullopt);
   return std::make_unique<webrtc::test::FrameGeneratorCapturer>(
       webrtc::Clock::GetRealTimeClock(), std::move(frame_generator), kFps,
       task_queue_factory);
 }
 class CapturerTrackSource : public webrtc::VideoTrackSource {
  public:
   static webrtc::scoped_refptr<CapturerTrackSource> Create(
       webrtc::TaskQueueFactory& task_queue_factory) {
     std::unique_ptr<TestVideoCapturer> capturer =
         CreateCapturer(task_queue_factory);
     if (capturer) {
       capturer->Start();
       return webrtc::make_ref_counted<CapturerTrackSource>(std::move(capturer));
     }
     return nullptr;
   }
 
  protected:
   explicit CapturerTrackSource(std::unique_ptr<TestVideoCapturer> capturer)
       : VideoTrackSource(/*remote=*/false), capturer_(std::move(capturer)) {}
 
  private:
   webrtc::VideoSourceInterface<webrtc::VideoFrame>* source() override {
     return capturer_.get();
   }
 
   std::unique_ptr<TestVideoCapturer> capturer_;
 };
 
 // Video file track source that reads from YUV files
 class VideoFileTrackSource : public webrtc::VideoTrackSource {
  public:
   typedef std::function<void()> CompletionCallback;
   
   static webrtc::scoped_refptr<VideoFileTrackSource> Create(
       webrtc::TaskQueueFactory& task_queue_factory,
       const std::string& file_path,
       int width,
       int height,
       int fps,
       CompletionCallback completion_callback = nullptr) {
     if (file_path.empty()) {
       RTC_LOG(LS_ERROR) << "Video file path is empty";
       return nullptr;
     }
 
     // Create frame generator from YUV file
     std::unique_ptr<webrtc::test::FrameGeneratorInterface> frame_generator(
         webrtc::test::CreateFromYuvFileFrameGenerator(
             std::vector<std::string>{file_path}, width, height, 1));
     
     if (!frame_generator) {
       RTC_LOG(LS_ERROR) << "Failed to create frame generator from file: " << file_path;
       return nullptr;
     }
 
     // Create frame capturer
     std::unique_ptr<webrtc::test::FrameGeneratorCapturer> capturer(
         new webrtc::test::FrameGeneratorCapturer(
             webrtc::Clock::GetRealTimeClock(),
             std::move(frame_generator),
             fps,
             task_queue_factory));
 
     if (!capturer->Init()) {
       RTC_LOG(LS_ERROR) << "Failed to initialize frame capturer";
       return nullptr;
     }
 
     capturer->Start();
     
     auto track_source = webrtc::make_ref_counted<VideoFileTrackSource>(
         std::move(capturer), completion_callback);
     
     return track_source;
   }
 
 
 
  protected:
   explicit VideoFileTrackSource(
       std::unique_ptr<webrtc::test::FrameGeneratorCapturer> capturer,
       CompletionCallback completion_callback)
       : VideoTrackSource(/*remote=*/false), 
         capturer_(std::move(capturer)),
         completion_callback_(completion_callback) {}
 
  private:
   webrtc::VideoSourceInterface<webrtc::VideoFrame>* source() override {
     return capturer_.get();
   }
   
 
 
   std::unique_ptr<webrtc::test::FrameGeneratorCapturer> capturer_;
   CompletionCallback completion_callback_;
 };
 
 }  // namespace
 
 Conductor::Conductor(const webrtc::Environment& env,
                      PeerConnectionClient* absl_nonnull client,
                      MainWindow* absl_nonnull main_wnd)
     : peer_id_(-1),
       loopback_(false),
       env_(env),
       client_(client),
       main_wnd_(main_wnd),
       config_(std::make_unique<WebRTCConfig>()),
       stats_timer_started_(false) {
   client_->RegisterObserver(this);
   main_wnd->RegisterObserver(this);
   
   // Load configuration
   std::string config_file = absl::GetFlag(FLAGS_config);
   if (!config_file.empty()) {
     if (config_->ParseFromFile(config_file)) {
       RTC_LOG(LS_INFO) << "Loaded configuration from: " << config_file;
       config_->PrintConfig();
     } else {
       RTC_LOG(LS_ERROR) << "Failed to load configuration from: " << config_file;
     }
   }
 }
 
 Conductor::~Conductor() {
   RTC_DCHECK(!peer_connection_);
   
   // Stop stats collection task
   if (stats_collection_task_.Running()) {
     RTC_LOG(LS_INFO) << "Stopping video quality stats collection task";
     stats_collection_task_.Stop();
   }
   
   // Clean up stats task queue
   if (stats_task_queue_) {
     RTC_LOG(LS_INFO) << "Cleaning up stats task queue";
     stats_task_queue_.reset();
   }
   
   // Clean up video frame writer
   if (video_frame_writer_) {
     RTC_LOG(LS_INFO) << "Cleaning up VideoFrameWriter";
     video_frame_writer_.reset();
   }
   
 
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

  if (!signaling_thread_.get()) {
     signaling_thread_ = webrtc::Thread::CreateWithSocketServer();
     signaling_thread_->Start();
   }
 
   webrtc::PeerConnectionFactoryDependencies deps;
   deps.signaling_thread = signaling_thread_.get();
   deps.env = env_,
   deps.audio_encoder_factory = webrtc::CreateBuiltinAudioEncoderFactory();
   deps.audio_decoder_factory = webrtc::CreateBuiltinAudioDecoderFactory();
   deps.video_encoder_factory =
       std::make_unique<webrtc::VideoEncoderFactoryTemplate<
           webrtc::LibvpxVp8EncoderTemplateAdapter,
           webrtc::LibvpxVp9EncoderTemplateAdapter,
           webrtc::OpenH264EncoderTemplateAdapter,
           webrtc::LibaomAv1EncoderTemplateAdapter>>();
   deps.video_decoder_factory =
       std::make_unique<webrtc::VideoDecoderFactoryTemplate<
           webrtc::LibvpxVp8DecoderTemplateAdapter,
           webrtc::LibvpxVp9DecoderTemplateAdapter,
           webrtc::OpenH264DecoderTemplateAdapter,
           webrtc::Dav1dDecoderTemplateAdapter>>();
 
   // =========================================================================
   // If we are not planning to send any audio, or if we are running in an
   // environment without audio devices (like a server), we can use a dummy
   // audio device module. This prevents the factory from trying to initialize
   // a real audio device, which can fail and cause a crash.
   // We use create_detached=true to avoid TaskQueue thread checking issues.
   auto adm_impl = webrtc::make_ref_counted<webrtc::AudioDeviceModuleImpl>(
       webrtc::AudioDeviceModule::kDummyAudio,
       std::make_unique<webrtc::AudioDeviceDummy>(),
       &env_.task_queue_factory(),
       /*create_detached=*/true);
   
   // Initialize the dummy audio device module
   if (adm_impl->CheckPlatform() == -1 ||
       adm_impl->CreatePlatformSpecificObjects(env_) == -1 ||
       adm_impl->AttachAudioBuffer() == -1) {
     RTC_LOG(LS_ERROR) << "Failed to initialize dummy audio device module";
   }
   
   deps.adm = adm_impl;
   // =========================================================================
 
   webrtc::EnableMedia(deps);
   peer_connection_factory_ =
       webrtc::CreateModularPeerConnectionFactory(std::move(deps));
 
   if (!peer_connection_factory_) {
     main_wnd_->MessageBox("Error", "Failed to initialize PeerConnectionFactory",
                           true);
     DeletePeerConnection();
     return false;
   }
 
   if (!CreatePeerConnection()) {
     main_wnd_->MessageBox("Error", "CreatePeerConnection failed", true);
     DeletePeerConnection();
   }
 
   AddTracks();
 
   return peer_connection_ != nullptr;
 }
 
 bool Conductor::ReinitializePeerConnectionForLoopback() {
   loopback_ = true;
   std::vector<webrtc::scoped_refptr<webrtc::RtpSenderInterface>> senders =
       peer_connection_->GetSenders();
   peer_connection_ = nullptr;
   // Loopback is only possible if encryption is disabled.
   webrtc::PeerConnectionFactoryInterface::Options options;
   options.disable_encryption = true;
   peer_connection_factory_->SetOptions(options);
   if (CreatePeerConnection()) {
     for (const auto& sender : senders) {
       peer_connection_->AddTrack(sender->track(), sender->stream_ids());
     }
     peer_connection_->CreateOffer(
         this, webrtc::PeerConnectionInterface::RTCOfferAnswerOptions());
   }
   options.disable_encryption = false;
   peer_connection_factory_->SetOptions(options);
   return peer_connection_ != nullptr;
 }
 
 bool Conductor::CreatePeerConnection() {
   RTC_DCHECK(peer_connection_factory_);
   RTC_DCHECK(!peer_connection_);
 
   webrtc::PeerConnectionInterface::RTCConfiguration config;
   config.sdp_semantics = webrtc::SdpSemantics::kUnifiedPlan;
   webrtc::PeerConnectionInterface::IceServer server;
   server.uri = GetPeerConnectionString();
   config.servers.push_back(server);
 
   webrtc::PeerConnectionDependencies pc_dependencies(this);
   auto error_or_peer_connection =
       peer_connection_factory_->CreatePeerConnectionOrError(
           config, std::move(pc_dependencies));
   if (error_or_peer_connection.ok()) {
     peer_connection_ = std::move(error_or_peer_connection.value());
   }
   return peer_connection_ != nullptr;
 }
 
 void Conductor::DeletePeerConnection() {
   main_wnd_->StopLocalRenderer();
   main_wnd_->StopRemoteRenderer();
   
   // Stop stats collection before clearing peer connection
   stats_timer_started_ = false;
   if (stats_collection_task_.Running()) {
     RTC_LOG(LS_INFO) << "Stopping video quality stats collection due to peer connection cleanup";
     stats_collection_task_.Stop();
   }
   
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
 
 void Conductor::OnAddTrack(
     webrtc::scoped_refptr<webrtc::RtpReceiverInterface> receiver,
     const std::vector<webrtc::scoped_refptr<webrtc::MediaStreamInterface>>&
         streams) {
   RTC_LOG(LS_INFO) << __FUNCTION__ << " " << receiver->id();
   
   auto track = receiver->track();
   if (track->kind() == webrtc::MediaStreamTrackInterface::kVideoKind) {
     RTC_LOG(LS_INFO) << "Received video track: " << track->id();
     
     // Check if video output is enabled in configuration
     if (config_ && config_->save_to_file()) {
       RTC_LOG(LS_INFO) << "Video output enabled, creating VideoFrameWriter";
       
       // Create VideoFrameWriter if not already created (for OnFrameCallback usage)
       if (!video_frame_writer_) {
         video_frame_writer_ = VideoFrameWriter::Create(
             config_->video_output_path(),
             config_->video_output_width(),
             config_->video_output_height(),
             config_->video_output_fps());
         
         if (!video_frame_writer_) {
           RTC_LOG(LS_ERROR) << "Failed to create VideoFrameWriter";
         } else {
           RTC_LOG(LS_INFO) << "VideoFrameWriter created successfully for OnFrameCallback: " 
                            << config_->video_output_path();
         }
       }
       
       // Note: No sink management needed - using AlphaRTC-style OnFrameCallback instead
       RTC_LOG(LS_INFO) << "Using AlphaRTC-style OnFrameCallback for video frame saving";
     } else {
       RTC_LOG(LS_INFO) << "Video output disabled in configuration";
     }
     
 
   }
   
   // **添加定期统计收集 - 每5秒收集一次视频质量统计**
   if (track->kind() == webrtc::MediaStreamTrackInterface::kVideoKind && !stats_timer_started_) {
     StartStatsCollection();
     stats_timer_started_ = true;
   }
   
   main_wnd_->QueueUIThreadCallback(NEW_TRACK_ADDED,
                                    receiver->track().release());
 }
 
 void Conductor::OnRemoveTrack(
     webrtc::scoped_refptr<webrtc::RtpReceiverInterface> receiver) {
   RTC_LOG(LS_INFO) << __FUNCTION__ << " " << receiver->id();
   main_wnd_->QueueUIThreadCallback(TRACK_REMOVED, receiver->track().release());
 }
 
 void Conductor::OnIceCandidate(const webrtc::IceCandidate* candidate) {
   RTC_LOG(LS_INFO) << __FUNCTION__ << " " << candidate->sdp_mline_index();
   // For loopback test. To save some connecting delay.
   if (loopback_) {
     if (!peer_connection_->AddIceCandidate(candidate)) {
       RTC_LOG(LS_WARNING) << "Failed to apply the received candidate";
     }
     return;
   }
 
   Json::Value jmessage;
   jmessage[kCandidateSdpMidName] = candidate->sdp_mid();
   jmessage[kCandidateSdpMlineIndexName] = candidate->sdp_mline_index();
   jmessage[kCandidateSdpName] = candidate->ToString();
 
   Json::StreamWriterBuilder factory;
   SendMessage(Json::writeString(factory, jmessage));
 }
 
 //
 // PeerConnectionClientObserver implementation.
 //
 
 void Conductor::OnSignedIn() {
   RTC_LOG(LS_INFO) << __FUNCTION__;
   main_wnd_->SwitchToPeerList(client_->peers());
 }
 
 void Conductor::OnDisconnected() {
   RTC_LOG(LS_INFO) << __FUNCTION__;
 
   DeletePeerConnection();
 
   if (main_wnd_->IsWindow())
     main_wnd_->SwitchToConnectUI();
 }
 
 void Conductor::OnPeerConnected(int id, const std::string& name) {
   RTC_LOG(LS_INFO) << __FUNCTION__;
   // Refresh the list if we're showing it.
   if (main_wnd_->current_ui() == MainWindow::LIST_PEERS)
     main_wnd_->SwitchToPeerList(client_->peers());
 }
 
 void Conductor::OnPeerDisconnected(int id) {
   RTC_LOG(LS_INFO) << __FUNCTION__;
   if (id == peer_id_) {
     RTC_LOG(LS_INFO) << "Our peer disconnected";
     main_wnd_->QueueUIThreadCallback(PEER_CONNECTION_CLOSED, nullptr);
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
     RTC_LOG(LS_WARNING)
         << "Received a message from unknown peer while already in a "
            "conversation with a different peer.";
     return;
   }
 
   Json::CharReaderBuilder factory;
   std::unique_ptr<Json::CharReader> reader =
       absl::WrapUnique(factory.newCharReader());
   Json::Value jmessage;
   if (!reader->parse(message.data(), message.data() + message.length(),
                      &jmessage, nullptr)) {
     RTC_LOG(LS_WARNING) << "Received unknown message. " << message;
     return;
   }
   std::string type_str;
   std::string json_object;
 
   webrtc::GetStringFromJsonObject(jmessage, kSessionDescriptionTypeName,
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
     std::optional<webrtc::SdpType> type_maybe =
         webrtc::SdpTypeFromString(type_str);
     if (!type_maybe) {
       RTC_LOG(LS_ERROR) << "Unknown SDP type: " << type_str;
       return;
     }
     webrtc::SdpType type = *type_maybe;
     std::string sdp;
     if (!webrtc::GetStringFromJsonObject(jmessage, kSessionDescriptionSdpName,
                                          &sdp)) {
       RTC_LOG(LS_WARNING)
           << "Can't parse received session description message.";
       return;
     }
     webrtc::SdpParseError error;
     std::unique_ptr<webrtc::SessionDescriptionInterface> session_description =
         webrtc::CreateSessionDescription(type, sdp, &error);
     if (!session_description) {
       RTC_LOG(LS_WARNING)
           << "Can't parse received session description message. "
              "SdpParseError was: "
           << error.description;
       return;
     }
     RTC_LOG(LS_INFO) << " Received session description :" << message;
     peer_connection_->SetRemoteDescription(
         DummySetSessionDescriptionObserver::Create().get(),
         session_description.release());
     if (type == webrtc::SdpType::kOffer) {
       peer_connection_->CreateAnswer(
           this, webrtc::PeerConnectionInterface::RTCOfferAnswerOptions());
     }
   } else {
     std::string sdp_mid;
     int sdp_mlineindex = 0;
     std::string sdp;
     if (!webrtc::GetStringFromJsonObject(jmessage, kCandidateSdpMidName,
                                          &sdp_mid) ||
         !webrtc::GetIntFromJsonObject(jmessage, kCandidateSdpMlineIndexName,
                                       &sdp_mlineindex) ||
         !webrtc::GetStringFromJsonObject(jmessage, kCandidateSdpName, &sdp)) {
       RTC_LOG(LS_WARNING) << "Can't parse received message.";
       return;
     }
     webrtc::SdpParseError error;
     std::unique_ptr<webrtc::IceCandidate> candidate(
         webrtc::CreateIceCandidate(sdp_mid, sdp_mlineindex, sdp, &error));
     if (!candidate.get()) {
       RTC_LOG(LS_WARNING) << "Can't parse received candidate message. "
                              "SdpParseError was: "
                           << error.description;
       return;
     }
     if (!peer_connection_->AddIceCandidate(candidate.get())) {
       RTC_LOG(LS_WARNING) << "Failed to apply the received candidate";
       return;
     }
     RTC_LOG(LS_INFO) << " Received candidate :" << message;
   }
 }
 
 void Conductor::OnMessageSent(int err) {
   // Process the next pending message if any.
   main_wnd_->QueueUIThreadCallback(SEND_MESSAGE_TO_PEER, nullptr);
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
 
   // DISABLED: Audio track transmission - only testing video
   // webrtc::scoped_refptr<webrtc::AudioTrackInterface> audio_track(
   //     peer_connection_factory_->CreateAudioTrack(
   //         kAudioLabel,
   //         peer_connection_factory_->CreateAudioSource(webrtc::AudioOptions())
   //             .get()));
   // auto result_or_error = peer_connection_->AddTrack(audio_track, {kStreamId});
   // if (!result_or_error.ok()) {
   //   RTC_LOG(LS_ERROR) << "Failed to add audio track to PeerConnection: "
   //                     << result_or_error.error().message();
   // }
   RTC_LOG(LS_INFO) << "Audio track disabled - only transmitting video for testing";
 
   // Create video source based on configuration
   webrtc::scoped_refptr<webrtc::VideoTrackSource> video_device = nullptr;
   
   // Determine video source (config file takes precedence over command line)
   bool use_video_file = false;
   bool video_disabled = false;
   std::string file_path;
   int width, height, fps;
   
   if (!absl::GetFlag(FLAGS_config).empty()) {
     // Use config file settings
     switch (config_->video_source_option()) {
       case WebRTCConfig::kVideoFile:
         use_video_file = true;
         file_path = config_->video_file_path();
         width = config_->video_width();
         height = config_->video_height();
         fps = config_->video_fps();
         break;
       case WebRTCConfig::kCamera:
         use_video_file = false;
         break;
       case WebRTCConfig::kVideoDisabled:
         video_disabled = true;
         RTC_LOG(LS_INFO) << "Video disabled in configuration";
         break;
     }
   } else {
     // Use command line settings
     use_video_file = absl::GetFlag(FLAGS_use_video_file);
     file_path = absl::GetFlag(FLAGS_video_file_path);
     width = absl::GetFlag(FLAGS_video_width);
     height = absl::GetFlag(FLAGS_video_height);
     fps = absl::GetFlag(FLAGS_video_fps);
   }
   
   // Only create video device if video is not disabled
   if (!video_disabled) {
     if (use_video_file) {
       RTC_LOG(LS_INFO) << "Using video file: " << file_path 
                        << " (" << width << "x" << height << " @ " << fps << " fps)";
       
       // Native WebRTC using simple timer (like AlphaRTC serverless style)
       video_device = VideoFileTrackSource::Create(
          env_.task_queue_factory(), file_path, width, height, fps);
    } else {
      RTC_LOG(LS_INFO) << "Using camera as video source";
      video_device = CapturerTrackSource::Create(env_.task_queue_factory());
    }
    
    if (video_device) {
      video_track_ = peer_connection_factory_->CreateVideoTrack(video_device, kVideoLabel);
      main_wnd_->StartLocalRenderer(video_track_.get());

      auto result_or_error = peer_connection_->AddTrack(video_track_, {kStreamId});
      if (!result_or_error.ok()) {
        RTC_LOG(LS_ERROR) << "Failed to add video track to PeerConnection: "
                          << result_or_error.error().message();
        return;
      }

      // =======================================================================
      // 🚀 使用BitrateConstraints默认值的推荐代码（使用SetBitrate API）
      // =======================================================================
      RTC_LOG(LS_INFO) << "Applying BitrateConstraints default values using SetBitrate...";
      
      webrtc::BitrateSettings bitrate_settings;
      // 按照 BitrateConstraints 结构体的默认值设置：
      bitrate_settings.min_bitrate_bps = 0;                           // min_bitrate_bps = 0
      bitrate_settings.start_bitrate_bps = 300000;                    // start_bitrate_bps = kDefaultStartBitrateBps (300kbps)
      // max_bitrate_bps 保持为 std::nullopt (对应 BitrateConstraints 的 -1，即无限制)
      
      webrtc::RTCError result = peer_connection_->SetBitrate(bitrate_settings);
      if (result.ok()) {
        RTC_LOG(LS_INFO) << "✅ Successfully applied BitrateConstraints default values:";
        RTC_LOG(LS_INFO) << "  - min_bitrate_bps: 0 bps";
        RTC_LOG(LS_INFO) << "  - start_bitrate_bps: 300000 bps (300 kbps)";
        RTC_LOG(LS_INFO) << "  - max_bitrate_bps: unlimited (nullopt, 对应BitrateConstraints的-1)";
      } else {
        RTC_LOG(LS_ERROR) << "❌ Failed to set bitrate: " << result.message();
      }

      // =======================================================================
      // 🚀 同时设置编码器层面的比特率限制（解决2500kbps限制问题）
      // =======================================================================
      RTC_LOG(LS_INFO) << "Setting encoder-level bitrate parameters to remove 2500kbps limit...";
      webrtc::scoped_refptr<webrtc::RtpSenderInterface> sender = result_or_error.value();
      webrtc::RtpParameters parameters = sender->GetParameters();

      if (parameters.encodings.empty()) {
        RTC_LOG(LS_WARNING) << "Sender has no encodings to modify.";
      } else {
        // 设置编码器层面的比特率限制，移除2500kbps默认限制
        // 🔥 关键修复：不能设置nullopt，要设置一个很高的正数值
        // 因为EncoderStreamFactory只认为 > 0 的值是有效的API设置
        parameters.encodings[0].max_bitrate_bps = 50000000;  // 50 Mbps，足够高的限制
        parameters.encodings[0].min_bitrate_bps = 0;         // 0 kbps 最小比特率
        // 不设置 target_bitrate_bps，让系统自动调整
        
        RTC_LOG(LS_INFO) << "  - Setting max_bitrate_bps to 50 Mbps (50000000 bps) to override 2.5Mbps default";
        RTC_LOG(LS_INFO) << "  - Setting min_bitrate_bps to 0 kbps";

        // 应用修改后的参数
        webrtc::RTCError encoder_result = sender->SetParameters(parameters);
        if (encoder_result.ok()) {
          RTC_LOG(LS_INFO) << "✅ Successfully removed encoder-level 2500kbps limit.";
        } else {
          RTC_LOG(LS_ERROR) << "❌ Failed to set encoder parameters: " << encoder_result.message();
        }
      }
      // =======================================================================
     } else {
       RTC_LOG(LS_ERROR) << "Failed to create video source";
     }
   } else {
     RTC_LOG(LS_INFO) << "No video track created - video disabled in configuration";
   }
 
   main_wnd_->SwitchToStreamingUI();
   
   // =================================================================
   // Only set an auto-close timer if we are the sender.
   // The presence of a local video track is a good indicator.
   // =================================================================
   if (video_track_) {
     RTC_LOG(LS_INFO) << "📹 This is a sender - video track created, setting up auto-close timer";
     
     int timer_duration_seconds = 0;
     
     // Prioritize calculated file duration over config value
     if (use_video_file && !file_path.empty()) {
       // Calculate video duration based on YUV file size and video parameters
       int video_duration_seconds = CalculateVideoDurationFromFile(file_path, width, height, fps);
       if (video_duration_seconds > 0) {
         // Add a small buffer time (2 seconds) to ensure complete transmission
         timer_duration_seconds = video_duration_seconds + 2;
         RTC_LOG(LS_INFO) << "📅 Calculated video duration: " << video_duration_seconds 
                          << " seconds, setting auto-close timer: " << timer_duration_seconds << " seconds";
       } else {
         RTC_LOG(LS_WARNING) << "📅 Failed to calculate video duration from file";
       }
     }
     
     // Fallback to config value if file duration couldn't be calculated or source is camera
     if (timer_duration_seconds <= 0) {
       timer_duration_seconds = config_->transmission_time_seconds();
       if (timer_duration_seconds > 0) {
         RTC_LOG(LS_INFO) << "📅 Using config-based transmission time: " << timer_duration_seconds << " seconds";
       }
     }
     
     if (timer_duration_seconds > 0) {
       webrtc::Thread::Current()->PostDelayedTask(
           [this]() {
             RTC_LOG(LS_INFO) << "⏰ Sender's auto-close timer triggered, closing connection";
             DisconnectFromCurrentPeer();
             main_wnd_->QueueUIThreadCallback(PEER_CONNECTION_CLOSED, nullptr);
           },
           webrtc::TimeDelta::Millis(timer_duration_seconds * 1000));
     } else {
       RTC_LOG(LS_INFO) << "📅 Sender auto-close timer disabled (timer_duration_seconds = " << timer_duration_seconds << ")";
     }
   } else {
     RTC_LOG(LS_INFO) << "📺 This is a receiver-only client. No auto-close timer will be set.";
   }
 }
 
 void Conductor::DisconnectFromCurrentPeer() {
   RTC_LOG(LS_INFO) << __FUNCTION__;
   if (peer_connection_.get()) {
     client_->SendHangUp(peer_id_);
     DeletePeerConnection();
   }
 
   if (main_wnd_->IsWindow())
     main_wnd_->SwitchToPeerList(client_->peers());
 }
 
 void Conductor::UIThreadCallback(int msg_id, void* data) {
   switch (msg_id) {
     case PEER_CONNECTION_CLOSED:
       RTC_LOG(LS_INFO) << "PEER_CONNECTION_CLOSED";
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
       RTC_LOG(LS_INFO) << "SEND_MESSAGE_TO_PEER";
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
       RTC_DCHECK_NOTREACHED();
       break;
   }
 }
 
 void Conductor::OnFrameCallback(const webrtc::VideoFrame& video_frame) {
   // Professional video frame saving (same approach as AlphaRTC)
   if (config_ && config_->save_to_file() && video_frame_writer_) {
     video_frame_writer_->OnFrame(video_frame);
   }
 }
 
 void Conductor::OnSuccess(webrtc::SessionDescriptionInterface* desc) {
   peer_connection_->SetLocalDescription(
       DummySetSessionDescriptionObserver::Create().get(), desc);
 
   std::string sdp;
   desc->ToString(&sdp);
 
   // For loopback test. To save some connecting delay.
   if (loopback_) {
     // Replace message type from "offer" to "answer"
     std::unique_ptr<webrtc::SessionDescriptionInterface> session_description =
         webrtc::CreateSessionDescription(webrtc::SdpType::kAnswer, sdp);
     peer_connection_->SetRemoteDescription(
         DummySetSessionDescriptionObserver::Create().get(),
         session_description.release());
     return;
   }
 
   Json::Value jmessage;
   jmessage[kSessionDescriptionTypeName] =
       webrtc::SdpTypeToString(desc->GetType());
   jmessage[kSessionDescriptionSdpName] = sdp;
 
   Json::StreamWriterBuilder factory;
   SendMessage(Json::writeString(factory, jmessage));
 }
 
 void Conductor::OnFailure(webrtc::RTCError error) {
   RTC_LOG(LS_ERROR) << ToString(error.type()) << ": " << error.message();
 }
 
 void Conductor::SendMessage(const std::string& json_object) {
   std::string* msg = new std::string(json_object);
   main_wnd_->QueueUIThreadCallback(SEND_MESSAGE_TO_PEER, msg);
 }
 
 
 
 void Conductor::StartStatsCollection() {
   RTC_LOG(LS_INFO) << "Starting video quality stats collection (every 100ms - 10 times per second)";
   
   if (!peer_connection_) {
     RTC_LOG(LS_WARNING) << "Cannot start stats collection: no peer connection";
     return;
   }
   
   // Stop any existing stats collection task
   if (stats_collection_task_.Running()) {
     stats_collection_task_.Stop();
   }
   
   // Enable stats collection timer
   stats_timer_started_ = true;
   
   // Create task queue for stats collection
   stats_task_queue_ = env_.task_queue_factory().CreateTaskQueue("StatsCollection", webrtc::TaskQueueFactory::Priority::NORMAL);
   
   // Create repeating task for continuous stats collection
   stats_collection_task_ = webrtc::RepeatingTaskHandle::DelayedStart(
     stats_task_queue_.get(),
     webrtc::TimeDelta::Millis(100),  // Start after 100ms
     [this]() {
       if (peer_connection_ && stats_timer_started_) {
         auto callback = webrtc::scoped_refptr<webrtc::RTCStatsCollectorCallback>(
             new webrtc::RefCountedObject<StatsCallback>(this));
         peer_connection_->GetStats(callback.get());
         
         RTC_LOG(LS_INFO) << "Video quality stats collection executed";
         return webrtc::TimeDelta::Millis(100);  // Repeat every 100ms (10 times per second)
       } else {
         RTC_LOG(LS_INFO) << "Stopping stats collection - no peer connection or timer stopped";
         return webrtc::TimeDelta::Zero();  // Stop the task
       }
     }
   );
   
   // Also do an immediate first collection
   auto immediate_callback = webrtc::scoped_refptr<webrtc::RTCStatsCollectorCallback>(
       new webrtc::RefCountedObject<StatsCallback>(this));
   peer_connection_->GetStats(immediate_callback.get());
 }
 
 void Conductor::OnStatsDelivered(const webrtc::scoped_refptr<const webrtc::RTCStatsReport>& report) {
   RTC_LOG(LS_INFO) << "Video quality stats collected successfully";
   // The actual logging happens in rtc_stats_collector.cc functions
   // which are called during report generation
 }
 
 int Conductor::CalculateVideoDurationFromFile(const std::string& file_path, int width, int height, int fps) {
   if (file_path.empty() || width <= 0 || height <= 0 || fps <= 0) {
     RTC_LOG(LS_ERROR) << "Invalid parameters for video duration calculation";
     return 0;
   }
   
   // Open file to get size
   std::ifstream file(file_path, std::ios::binary | std::ios::ate);
   if (!file.is_open()) {
     RTC_LOG(LS_ERROR) << "Failed to open video file: " << file_path;
     return 0;
   }
   
   // Get file size
   std::streampos file_size = file.tellg();
   file.close();
   
   if (file_size <= 0) {
     RTC_LOG(LS_ERROR) << "Invalid file size for: " << file_path;
     return 0;
   }
   
   // Calculate duration for YUV420 format
   // YUV420: Y plane (width * height) + U plane (width/2 * height/2) + V plane (width/2 * height/2)
   // = width * height * 1.5 bytes per frame
   double bytes_per_frame = width * height * 1.5;
   double total_frames = static_cast<double>(file_size) / bytes_per_frame;
   double duration_seconds = total_frames / fps;
   
   int duration_int = static_cast<int>(std::ceil(duration_seconds));
   
   RTC_LOG(LS_INFO) << "Video file analysis - File: " << file_path
                    << ", Size: " << file_size << " bytes"
                    << ", Resolution: " << width << "x" << height
                    << ", FPS: " << fps
                    << ", Calculated frames: " << static_cast<int>(total_frames)
                    << ", Duration: " << duration_int << " seconds";
   
   return duration_int;
 }
 
 
 
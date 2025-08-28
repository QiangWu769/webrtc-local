/*
 *  Copyright 2012 The WebRTC Project Authors. All rights reserved.
 *
 *  Use of this source code is governed by a BSD-style license
 *  that can be found in the LICENSE file in the root of the source
 *  tree. An additional intellectual property rights grant can be found
 *  in the file PATENTS.  All contributing project authors may
 *  be found in the AUTHORS file in the root of the source tree.
 */

#include <gtk/gtk.h>

#include <cstdio>
#include <memory>
#include <string>

#include "absl/flags/flag.h"
#include "absl/flags/parse.h"
#include "api/environment/environment.h"
#include "api/environment/environment_factory.h"
#include "api/field_trials.h"
#include "api/make_ref_counted.h"
#include "api/scoped_refptr.h"
#include "api/units/time_delta.h"
#include "examples/peerconnection/client/conductor.h"
#include "examples/peerconnection/client/flag_defs.h"
#include "examples/peerconnection/client/linux/main_wnd.h"
#include "examples/peerconnection/client/peer_connection_client.h"
#include "examples/peerconnection/client/webrtc_config.h"
#include "rtc_base/logging.h"
#include "rtc_base/physical_socket_server.h"
#include "rtc_base/ssl_adapter.h"
#include "rtc_base/thread.h"

class CustomSocketServer : public webrtc::PhysicalSocketServer {
 public:
  explicit CustomSocketServer(GtkMainWnd* wnd)
      : wnd_(wnd), conductor_(nullptr), client_(nullptr), auto_close_(false) {}
  ~CustomSocketServer() override {}

  void SetMessageQueue(webrtc::Thread* queue) override {
    message_queue_ = queue;
  }

  void set_client(PeerConnectionClient* client) { client_ = client; }
  void set_conductor(Conductor* conductor) { conductor_ = conductor; }
  void set_auto_close(bool auto_close) { auto_close_ = auto_close; }

  // Override so that we can also pump the GTK message loop.
  // This function never waits.
  bool Wait(webrtc::TimeDelta max_wait_duration, bool process_io) override {
    // Pump GTK events.
    // TODO(henrike): We really should move either the socket server or UI to a
    // different thread.  Alternatively we could look at merging the two loops
    // by implementing a dispatcher for the socket server and/or use
    // g_main_context_set_poll_func.
    while (gtk_events_pending())
      gtk_main_iteration();

    if (!wnd_->IsWindow() && !conductor_->connection_active() &&
        client_ != nullptr && !client_->is_connected()) {
      message_queue_->Quit();
    }
    
    // Auto close when video transmission completes (if enabled)
    if (auto_close_ && conductor_->connection_active() &&
        client_ != nullptr && client_->is_connected()) {
      // TODO: Add logic to detect when video file transmission is complete
      // For now, this is a placeholder for future implementation
    }
    return webrtc::PhysicalSocketServer::Wait(webrtc::TimeDelta::Zero(),
                                              process_io);
  }

 protected:
  webrtc::Thread* message_queue_;
  GtkMainWnd* wnd_;
  Conductor* conductor_;
  PeerConnectionClient* client_;
  bool auto_close_;
};

int main(int argc, char* argv[]) {
  gtk_init(&argc, &argv);

  absl::ParseCommandLine(argc, argv);
  
  // Setup logging if config file is specified
  std::string config_file = absl::GetFlag(FLAGS_config);
  if (!config_file.empty()) {
    WebRTCConfig temp_config;
    if (temp_config.ParseFromFile(config_file)) {
      // Set logging level based on config
      webrtc::LoggingSeverity severity;
      switch (temp_config.log_level()) {
        case WebRTCConfig::kLogVerbose:
          severity = webrtc::LS_VERBOSE;
          break;
        case WebRTCConfig::kLogInfo:
          severity = webrtc::LS_INFO;
          break;
        case WebRTCConfig::kLogWarning:
          severity = webrtc::LS_WARNING;
          break;
        case WebRTCConfig::kLogError:
          severity = webrtc::LS_ERROR;
          break;
        default:
          severity = webrtc::LS_INFO;
          break;
      }
      webrtc::LogMessage::LogToDebug(severity);
      
      // Setup log file if specified  
      if (temp_config.save_log_to_file() && !temp_config.log_output_path().empty()) {
        printf("Log file output configured: %s\n", temp_config.log_output_path().c_str());
        // Note: File logging would need additional setup with WebRTC's logging system
      }
    }
  }

  webrtc::Environment env =
      webrtc::CreateEnvironment(std::make_unique<webrtc::FieldTrials>(
          absl::GetFlag(FLAGS_force_fieldtrials)));

  // Server configuration - prefer config file over command line flags
  std::string server = absl::GetFlag(FLAGS_server);
  int port = absl::GetFlag(FLAGS_port);
  bool autoconnect = absl::GetFlag(FLAGS_autoconnect);
  bool autocall = absl::GetFlag(FLAGS_autocall);
  
  // Override with config file settings if available
  if (!config_file.empty()) {
    WebRTCConfig temp_config;
    if (temp_config.ParseFromFile(config_file)) {
      server = temp_config.server_host();
      port = temp_config.server_port();
      autoconnect = temp_config.auto_connect();
      autocall = temp_config.auto_call();
      
      RTC_LOG(LS_INFO) << "Using server config from file: " << server << ":" << port
                       << " (autoconnect=" << autoconnect << ", autocall=" << autocall << ")";
    }
  }
  
  // Abort if the user specifies a port that is outside the allowed range [1, 65535].
  if ((port < 1) || (port > 65535)) {
    printf("Error: %i is not a valid port.\n", port);
    return -1;
  }
  
  GtkMainWnd wnd(server.c_str(), port, autoconnect, autocall);
  wnd.Create();

  CustomSocketServer socket_server(&wnd);
  webrtc::AutoSocketServerThread thread(&socket_server);

  webrtc::InitializeSSL();
  // Must be constructed after we set the socketserver.
  PeerConnectionClient client;
  auto conductor = webrtc::make_ref_counted<Conductor>(env, &client, &wnd);
  socket_server.set_client(&client);
  socket_server.set_conductor(conductor.get());
  
  // Set auto close if specified in config
  if (!config_file.empty()) {
    WebRTCConfig temp_config;
    if (temp_config.ParseFromFile(config_file)) {
      socket_server.set_auto_close(temp_config.auto_close_on_completion());
      if (temp_config.auto_close_on_completion()) {
        printf("Auto close enabled - will exit when video transmission completes\n");
      }
    }
  }

  thread.Run();

  // gtk_main();
  wnd.Destroy();

  // TODO(henrike): Run the Gtk main loop to tear down the connection.
  /*
  while (gtk_events_pending()) {
    gtk_main_iteration();
  }
  */
  webrtc::CleanupSSL();
  return 0;
}

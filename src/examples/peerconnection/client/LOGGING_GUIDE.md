# WebRTC 原生客户端日志分析指南

## 概述

原生WebRTC客户端使用WebRTC内置的日志系统(`RTC_LOG`)生成详细的运行时日志，帮助开发者了解连接状态、调试问题和监控性能。

## 日志级别

WebRTC使用以下日志级别（按严重程度递增）：

- **LS_VERBOSE**: 详细调试信息（最低级别）
- **LS_INFO**: 一般信息日志
- **LS_WARNING**: 警告信息
- **LS_ERROR**: 错误信息（最高级别）

## 主要日志类别

### 1. 🎬 视频源相关日志

#### 新增的视频文件支持日志

```
[INFO] Using video file: /path/to/video.yuv (640x480 @ 30 fps)
[INFO] Using camera as video source
[ERROR] Video file path is empty
[ERROR] Failed to create frame generator from file: /path/to/video.yuv
[ERROR] Failed to initialize frame capturer
[ERROR] Failed to create video source
[ERROR] Failed to add video track to PeerConnection: <error_message>
```

### 2. 🔌 连接管理日志

#### PeerConnection状态
```
[INFO] OnSignedIn
[INFO] OnDisconnected  
[INFO] OnPeerConnected
[INFO] OnPeerDisconnected
[INFO] Our peer disconnected
[INFO] PEER_CONNECTION_CLOSED
[ERROR] Failed to initialize our PeerConnection instance
```

#### 网络连接
```
[INFO] Headers received
[WARNING] Connection refused; retrying in 2 seconds
[ERROR] Received error from server
[ERROR] No content length field specified by the server
```

### 3. 📡 信令交换日志

#### SDP处理
```
[INFO] Received session description: <sdp_content>
[ERROR] Unknown SDP type: <type>
[WARNING] Can't parse received session description message
[WARNING] Can't parse received session description message. <details>
```

#### ICE候选者
```
[INFO] OnIceCandidate <candidate_index>
[INFO] Received candidate: <candidate_details>
[WARNING] Failed to apply the received candidate
[WARNING] Can't parse received candidate message
```

### 4. 📨 消息传递日志

```
[INFO] SEND_MESSAGE_TO_PEER
[ERROR] SendToPeer failed
[WARNING] Received unknown message. <message>
[WARNING] Can't parse received message
```

### 5. 🎵 音频轨道日志

```
[ERROR] Failed to add audio track to PeerConnection: <error_message>
```

### 6. 🖥️ UI相关日志

```
[INFO] StartLocalRenderer
[INFO] StartRemoteRenderer  
[INFO] SwitchToStreamingUI
[INFO] SwitchToPeerList
[INFO] SwitchToConnectUI
```

## 典型日志流程

### 启动序列
```
[INFO] 应用程序启动
[INFO] 初始化PeerConnectionFactory
[INFO] Using camera as video source  (或视频文件日志)
[INFO] 创建音视频轨道
[INFO] SwitchToStreamingUI
```

### 连接建立
```
[INFO] 连接到服务器
[INFO] OnSignedIn
[INFO] OnPeerConnected
[INFO] 开始信令交换
[INFO] Received session description: ...
[INFO] OnIceCandidate ...
[INFO] 连接建立成功
```

### 视频文件模式特有日志
```
[INFO] Using video file: /home/user/test.yuv (640x480 @ 30 fps)
[INFO] Frame generator created successfully
[INFO] Video capturer started
```

### 错误场景
```
[ERROR] Video file path is empty
[ERROR] Failed to create frame generator from file: /path/to/video.yuv
[ERROR] Failed to initialize frame capturer  
[ERROR] Failed to create video source
[ERROR] Failed to add video track to PeerConnection: Track already exists
```

## 日志控制

### 运行时日志级别控制

WebRTC默认日志级别可以通过环境变量控制：

```bash
# 设置日志级别为INFO
export RTC_LOG_SEVERITY=INFO

# 设置日志级别为WARNING（减少日志输出）
export RTC_LOG_SEVERITY=WARNING

# 设置日志级别为ERROR（只显示错误）
export RTC_LOG_SEVERITY=ERROR
```

### 启动时的典型输出示例

#### 使用摄像头模式
```
[INFO] Using camera as video source
[INFO] StartLocalRenderer
[INFO] SwitchToStreamingUI
[INFO] 连接服务器: localhost:8888
[INFO] OnSignedIn
```

#### 使用视频文件模式
```
[INFO] Using video file: /home/user/test.yuv (640x480 @ 30 fps)
[INFO] StartLocalRenderer  
[INFO] SwitchToStreamingUI
[INFO] 连接服务器: localhost:8888
[INFO] OnSignedIn
```

## 调试技巧

### 1. 视频源问题诊断
查看这些关键日志：
- `Using video file:` 或 `Using camera as video source`
- `Failed to create frame generator` 
- `Failed to initialize frame capturer`

### 2. 连接问题诊断
关注：
- `OnSignedIn` / `OnDisconnected`
- `Failed to initialize our PeerConnection instance`
- `Connection refused; retrying`

### 3. 信令问题诊断
检查：
- `Received session description`
- `OnIceCandidate`
- `Can't parse received message`

## 性能监控日志

虽然当前版本没有详细的性能日志，但可以通过以下日志监控基本性能：

- 连接建立时间：从`OnSignedIn`到第一个`OnIceCandidate`
- 视频源启动时间：`Using video file/camera`到`StartLocalRenderer`
- 信令交换效率：SDP和ICE候选者的处理时间

## 日志文件输出

目前客户端将日志输出到标准输出，如需保存到文件：

```bash
# 将所有日志保存到文件
./peerconnection_client [参数] 2>&1 | tee client.log

# 只保存错误日志
./peerconnection_client [参数] 2> error.log

# 将输出重定向到日志文件
./peerconnection_client [参数] > output.log 2>&1
```

## 常见日志模式

### 正常启动模式
```
[INFO] Using camera as video source
[INFO] StartLocalRenderer
[INFO] SwitchToStreamingUI
```

### 视频文件模式
```
[INFO] Using video file: test.yuv (640x480 @ 30 fps)
[INFO] StartLocalRenderer
[INFO] SwitchToStreamingUI
```

### 连接错误模式
```
[WARNING] Connection refused; retrying in 2 seconds
[ERROR] Failed to initialize our PeerConnection instance
```

### 信令错误模式
```
[WARNING] Can't parse received message
[ERROR] Unknown SDP type: invalid
```

这些日志为开发者提供了全面的运行时信息，有助于快速定位和解决问题。
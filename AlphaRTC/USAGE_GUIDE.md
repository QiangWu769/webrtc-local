# AlphaRTC配置文件使用指南

## 概述
本项目已成功实现AlphaRTC客户端对`webrtc_config_example.json`配置文件的完全兼容支持。

## 🎯 实现的功能

### ✅ 配置文件支持
- **JSON配置解析**: 完整支持`webrtc_config_example.json`中的所有参数
- **视频源配置**: 支持视频文件路径、分辨率、帧率设置
- **音频源配置**: 支持音频文件和麦克风配置（可禁用）
- **比特率控制**: 支持max/min/start比特率设置（300-1700kbps）
- **ONNX模型**: 支持AlphaRTC拥塞控制模型路径配置

### ✅ 核心特性
- **自动退出**: 视频播放完毕后自动终止程序
- **音频禁用**: 仅传输视频，节省带宽
- **智能比特率**: 基于配置文件动态调整视频质量
- **拥塞控制**: 集成AlphaRTC智能拥塞控制算法

## 🚀 使用方法

### 1. 环境设置
```bash
cd /home/wuq/webrtc-checkout/AlphaRTC
export DISPLAY=:99
export LD_LIBRARY_PATH=/home/wuq/webrtc-checkout/AlphaRTC/modules/third_party/onnxinfer/lib:$LD_LIBRARY_PATH
```

### 2. 启动测试
```bash
# 自动化完整测试（推荐）
./test_correct.sh

# 或者手动分步启动
# 步骤1: 启动虚拟显示
Xvfb :99 -screen 0 1024x768x24 &

# 步骤2: 启动signaling服务器
./out/Default/peerconnection_server --port=8888 &

# 步骤3: 启动接收端（不使用配置）
./out/Default/peerconnection_client --autoconnect --server=127.0.0.1 --port=8888 &

# 步骤4: 启动发送端（使用配置文件）
./out/Default/peerconnection_client \
  --config=/home/wuq/webrtc-checkout/AlphaRTC/examples/peerconnection/client/webrtc_config_example.json \
  --autoconnect --autocall --server=127.0.0.1 --port=8888
```

## 📋 配置文件示例

```json
{
    "video_source": {
        "video_file": {
            "enabled": true,
            "height": 480,
            "width": 640,
            "fps": 30,
            "file_path": "/home/wuq/webrtc-checkout/test_video.yuv",
            "max_bitrate_kbps": 1700,
            "min_bitrate_kbps": 300,
            "start_bitrate_kbps": 1000
        }
    },
    "audio_source": {
        "microphone": { "enabled": false },
        "audio_file": {
            "enabled": true,
            "file_path": "/path/to/audio.wav"
        }
    },
    "onnx": {
        "onnx_model_path": "/path/to/onnx-model.onnx"
    }
}
```

## 🔧 核心修改

### 1. 配置解析 (`alphacc_config.cc`)
- 添加了比特率字段解析
- 修复了音频源配置逻辑

### 2. 比特率设置 (`conductor.cc`)
- 使用`PeerConnection::SetBitrate`方法
- 支持动态比特率调整

### 3. 自动退出机制
- 基于时间的播放监控
- 优雅的程序终止

## 📊 运行效果

成功运行时会看到如下关键日志：
```
✅ Skipping audio track addition - audio transmission disabled
✅ Video track added successfully, configuring bitrate...
✅ Successfully set video bitrate parameters: max=1700kbps, min=300kbps, start=1000kbps
✅ Video file transmission completed after X seconds, notifying
✅ Video playback finished, exiting application...
```

## 🎯 应用场景

- **视频质量测试**: 不同比特率下的视频传输质量评估
- **拥塞控制研究**: AlphaRTC算法性能分析
- **网络实验**: 受控环境下的WebRTC性能测试
- **自动化测试**: 批量视频传输质量评估

## 📝 注意事项

1. **文件路径**: 确保视频文件、音频文件、ONNX模型路径正确
2. **环境依赖**: 需要Xvfb虚拟显示和ONNX运行时库
3. **比特率设置**: 建议范围300-1700kbps，根据网络条件调整
4. **自动退出**: 默认播放时间约3.5秒后自动退出

本实现完全兼容AlphaRTC框架，为视频传输质量研究提供了强大的配置化工具。
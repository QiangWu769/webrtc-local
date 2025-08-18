# 🎯 纯视频传输测试指南

## 📋 概述

这个测试脚本专门用于测试我们刚刚编译的纯视频传输版本的WebRTC客户端。

## 🚀 快速开始

### 1. 准备环境

确保已编译好纯视频传输版本的WebRTC客户端：
```bash
cd /home/wuq/webrtc-checkout/src
ls -la out/Default/peerconnection_client  # 确认可执行文件存在
ls -la out/Default/peerconnection_server  # 确认信令服务器存在
```

### 2. 安装依赖

```bash
# 安装Python依赖
pip install pyyaml

# 安装Xvfb（虚拟显示，必需！）
sudo apt-get install xvfb

# 安装FFmpeg（用于视频格式转换）
sudo apt-get install ffmpeg
```

### 3. 准备视频文件

**⚠️ 重要：我们的客户端需要 YUV 原始格式，不是 Y4M 或 MP4！**

```bash
# 方法1：转换现有视频为YUV格式
ffmpeg -i input.mp4 -pix_fmt yuv420p -s 640x480 -r 30 test_video.yuv

# 方法2：生成测试模式视频（推荐用于测试）
ffmpeg -f lavfi -i testsrc2=size=640x480:rate=30 -t 10 -pix_fmt yuv420p test_video.yuv

# 验证文件大小（640x480，10秒，30fps ≈ 14MB）
ls -lh test_video.yuv
```

📖 **详细的视频格式转换指南请参考 `VIDEO_FORMAT_GUIDE.md`**

### 4. 配置测试参数

编辑 `real_network_config.yaml` 文件：

```yaml
# WebRTC 构建目录
webrtc_build_dir: '/home/wuq/webrtc-checkout/src/out/Default'

# 测试结果目录
results_dir: './results'

# 测试时长（秒）
duration: 60

# 视频配置（分辨率必须与YUV文件匹配！）
video:
  width: 640
  height: 480
  fps: 30
  file_path: '/home/wuq/webrtc-checkout/test_video.yuv'  # YUV格式文件
```

### 5. 运行测试

```bash
python3 run_real_network_test.py
```

## 🔧 主要修改

相比原版脚本，主要修改包括：

### ✅ **JSON配置支持**
- 自动为发送端和接收端生成JSON配置文件
- 通过 `WEBRTC_CONFIG_PATH` 环境变量传递配置文件路径
- 替代了原来的环境变量配置方式

### ✅ **纯视频模式**
- 移除所有音频相关配置
- 专注于视频传输测试
- 简化了配置复杂度

### ✅ **智能视频源选择**
- **发送端**：
  - 如果指定的视频文件存在且大小 > 1MB，使用视频文件
  - 否则使用摄像头/生成器
- **接收端**：纯接收模式，不需要视频源

### ✅ **增强的日志记录**
- 为每个客户端生成独立的WebRTC日志文件
- 保存接收的视频到Y4M文件
- 自动设置合适的日志级别

## 📁 生成的文件

测试运行后会在 `results/` 目录下生成：

```
results/
├── sender_config.json          # 发送端JSON配置
├── receiver_config.json        # 接收端JSON配置
├── sender.log                  # 发送端标准输出
├── sender.err                  # 发送端错误输出
├── receiver.log                # 接收端标准输出
├── receiver.err                # 接收端错误输出
├── sender_webrtc.log           # 发送端WebRTC内部日志
├── receiver_webrtc.log         # 接收端WebRTC内部日志
└── received_video.y4m          # 接收端保存的视频文件
```

## 🛠 配置文件结构

### 发送端配置示例：
```json
{
  "video_source": {
    "video_file": {
      "enabled": true,
      "height": 480,
      "width": 640,
      "fps": 30,
      "file_path": "/home/wuq/webrtc-checkout/test_video.yuv"
    }
  },
  "output": {
    "save_to_file": false
  },
  "connection": {
    "autoclose": true,
    "autoclose_time_s": 70
  },
  "logging": {
    "log_to_file": true,
    "log_file_path": "./results/sender_webrtc.log",
    "log_level": 2
  }
}
```

### 接收端配置示例：
```json
{
  "video_source": {
    "video_disabled": {
      "enabled": false
    }
  },
  "output": {
    "save_to_file": true,
    "file_path": "./results/received_video.y4m"
  },
  "connection": {
    "autoclose": true,
    "autoclose_time_s": 70
  }
}
```

## 🔍 故障排除

### 1. 找不到可执行文件
```bash
# 确认路径正确
ls -la /home/wuq/webrtc-checkout/src/out/Default/peerconnection_client
```

### 2. Xvfb启动失败
```bash
# 检查Xvfb是否已安装
which Xvfb

# 手动测试Xvfb
Xvfb :99 -screen 0 640x480x24 &
export DISPLAY=:99
xdpyinfo  # 应该显示显示信息
```

### 3. 权限问题
```bash
# 确保results目录可写
chmod 755 ./results
```

## 📈 性能监控

脚本会自动：
- 监控进程状态
- 提取WebRTC统计信息（RTT、带宽等）
- 检测视频播放完成标记
- 生成详细的测试报告

## 🎯 测试重点

这个纯视频传输版本专注于测试：
- ✅ 视频编码/解码性能
- ✅ 网络适应性（GCC拥塞控制）
- ✅ 视频质量和延迟
- ✅ 长时间稳定性
- ❌ 音频相关功能（已移除）

现在你可以运行 `python3 run_real_network_test.py` 来测试你的纯视频传输WebRTC客户端了！🚀
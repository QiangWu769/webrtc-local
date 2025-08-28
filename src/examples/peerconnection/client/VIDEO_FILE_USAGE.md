# WebRTC 视频文件传输功能使用说明

## 概述

原生WebRTC客户端现已支持使用视频文件作为输入源，而不仅仅是摄像头。此功能允许您使用YUV或Y4M格式的视频文件进行实时传输测试。

## 支持的格式

- **输入格式**：YUV (I420), Y4M
- **文件扩展名**：`.yuv`, `.y4m`

## 新增命令行参数

### 基本参数

- `--use_video_file`: 启用视频文件输入（默认: false）
- `--video_file_path`: 视频文件路径（必须，当use_video_file=true时）

### 视频配置参数（用于YUV文件）

- `--video_width`: 视频宽度像素（默认: 640）
- `--video_height`: 视频高度像素（默认: 480）  
- `--video_fps`: 视频帧率（默认: 30）

> **注意**: Y4M文件包含格式信息，无需指定分辨率和帧率。YUV文件需要明确指定这些参数。

## 使用示例

### 1. 使用YUV文件

```bash
# 使用640x480@30fps的YUV文件
./peerconnection_client \
  --use_video_file=true \
  --video_file_path=/path/to/video.yuv \
  --video_width=640 \
  --video_height=480 \
  --video_fps=30

# 使用1920x1080@25fps的YUV文件  
./peerconnection_client \
  --use_video_file=true \
  --video_file_path=/path/to/hd_video.yuv \
  --video_width=1920 \
  --video_height=1080 \
  --video_fps=25
```

### 2. 使用Y4M文件

```bash
# Y4M文件自动检测格式
./peerconnection_client \
  --use_video_file=true \
  --video_file_path=/path/to/video.y4m
```

### 3. 使用摄像头（默认行为）

```bash
# 默认使用摄像头，无需额外参数
./peerconnection_client
```

## 完整示例

### 服务器端（接收端）

```bash
./peerconnection_client \
  --server=localhost \
  --port=8888
```

### 客户端（发送端 - 使用视频文件）

```bash
./peerconnection_client \
  --server=localhost \
  --port=8888 \
  --autoconnect=true \
  --autocall=true \
  --use_video_file=true \
  --video_file_path=/home/user/test_video.yuv \
  --video_width=640 \
  --video_height=480 \
  --video_fps=30
```

## 技术实现

### 新增类

- **VideoFileTrackSource**: 基于YUV文件的视频轨道源
  - 使用`webrtc::test::CreateFromYuvFileFrameGenerator`读取文件
  - 使用`webrtc::test::FrameGeneratorCapturer`生成帧
  - 支持循环播放

### 修改的文件

1. **flag_defs.h**: 新增视频文件相关命令行参数
2. **conductor.cc**: 
   - 新增VideoFileTrackSource类
   - 修改AddTracks()方法支持视频源选择
   - 添加必要的include

## 注意事项

1. **文件路径**: 确保视频文件路径正确且文件存在
2. **格式要求**: YUV文件必须是I420格式
3. **分辨率**: YUV文件需要正确指定宽度和高度
4. **性能**: 大分辨率视频文件可能需要更多CPU资源
5. **循环播放**: 视频文件将自动循环播放

## 错误排除

### 常见错误

1. **"Video file path is empty"**
   - 解决：确保设置了`--video_file_path`参数

2. **"Failed to create frame generator from file"**
   - 解决：检查文件路径和格式是否正确

3. **"Failed to initialize frame capturer"**
   - 解决：检查视频参数（宽度、高度、帧率）是否正确

### 调试信息

程序会输出以下信息：
```
Using video file: /path/to/video.yuv (640x480 @ 30 fps)
```

如果看到此信息，说明视频文件源已正确初始化。

## 性能优化

- 使用较小分辨率进行测试（如640x480）
- 确保足够的磁盘I/O性能
- 考虑SSD存储以获得更好性能
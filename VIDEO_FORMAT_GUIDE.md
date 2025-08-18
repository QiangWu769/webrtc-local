# 🎬 视频文件格式转换指南

## 📋 支持的格式

我们的纯视频传输WebRTC客户端支持以下输入格式：

### ✅ **YUV 原始格式**（推荐）
- **文件扩展名**: `.yuv`
- **格式**: I420 (YUV420P) 原始数据
- **特点**: 无头部信息，纯像素数据
- **需要**: 手动指定分辨率和帧率

### ✅ **摄像头/生成器**
- 如果没有YUV文件，自动使用摄像头或帧生成器

## 🔄 视频格式转换

### 1. **MP4 → YUV**
```bash
# 转换为640x480，30fps
ffmpeg -i input.mp4 -pix_fmt yuv420p -s 640x480 -r 30 output.yuv

# 转换为1280x720，25fps
ffmpeg -i input.mp4 -pix_fmt yuv420p -s 1280x720 -r 25 output.yuv
```

### 2. **Y4M → YUV**
```bash
# Y4M文件包含头部信息，需要转换为纯YUV
ffmpeg -i input.y4m -c:v rawvideo -pix_fmt yuv420p output.yuv
```

### 3. **AVI → YUV**
```bash
ffmpeg -i input.avi -pix_fmt yuv420p -s 640x480 -r 30 output.yuv
```

### 4. **从网络摄像头创建测试视频**
```bash
# 录制10秒的摄像头视频
ffmpeg -f v4l2 -i /dev/video0 -t 10 -pix_fmt yuv420p -s 640x480 -r 30 test_video.yuv
```

### 5. **生成测试模式视频**
```bash
# 生成彩色测试模式（5秒）
ffmpeg -f lavfi -i testsrc2=size=640x480:rate=30 -t 5 -pix_fmt yuv420p test_pattern.yuv

# 生成移动方块测试模式
ffmpeg -f lavfi -i "testsrc=size=640x480:rate=30" -t 5 -pix_fmt yuv420p moving_squares.yuv
```

## 📐 **重要注意事项**

### ⚠️ **分辨率和配置必须匹配**
确保YUV文件的实际分辨率与配置文件中的设置完全一致：

```yaml
video:
  width: 640    # 必须匹配YUV文件的实际宽度
  height: 480   # 必须匹配YUV文件的实际高度
  fps: 30       # 建议的播放帧率
  file_path: '/home/wuq/webrtc-checkout/test_video.yuv'
```

### 📊 **文件大小计算**
YUV420P格式的文件大小计算：
- **每帧大小** = `width × height × 1.5` 字节
- **总文件大小** = `每帧大小 × 总帧数`

例如：640×480，30fps，10秒视频
- 每帧大小 = 640 × 480 × 1.5 = 460,800 字节
- 总帧数 = 30 × 10 = 300 帧
- 文件大小 = 460,800 × 300 = 138,240,000 字节 ≈ 132 MB

## 🎯 **测试文件准备示例**

### 创建一个短测试视频：
```bash
# 方法1：从现有视频转换（推荐）
ffmpeg -i your_video.mp4 -pix_fmt yuv420p -s 640x480 -r 30 -t 10 test_video.yuv

# 方法2：生成测试模式
ffmpeg -f lavfi -i testsrc2=size=640x480:rate=30 -t 10 -pix_fmt yuv420p test_video.yuv

# 方法3：从摄像头录制
ffmpeg -f v4l2 -i /dev/video0 -t 10 -pix_fmt yuv420p -s 640x480 -r 30 test_video.yuv
```

### 验证文件：
```bash
# 检查文件大小（应该符合计算公式）
ls -lh test_video.yuv

# 播放验证（如果安装了ffplay）
ffplay -f rawvideo -pix_fmt yuv420p -s 640x480 -r 30 test_video.yuv
```

## 🔧 **配置文件示例**

创建对应的 `real_network_config.yaml`：
```yaml
video:
  width: 640              # 与YUV文件匹配
  height: 480             # 与YUV文件匹配  
  fps: 30                 # 播放帧率
  file_path: '/home/wuq/webrtc-checkout/test_video.yuv'
```

## 🚀 **快速测试流程**

```bash
# 1. 生成测试视频（10秒，640x480）
ffmpeg -f lavfi -i testsrc2=size=640x480:rate=30 -t 10 -pix_fmt yuv420p test_video.yuv

# 2. 确认文件存在和大小
ls -lh test_video.yuv
# 应该显示约 ~14MB

# 3. 运行测试
python3 run_real_network_test.py
```

## ❌ **常见错误**

1. **文件格式错误**：使用了Y4M或MP4文件而不是YUV
2. **分辨率不匹配**：配置中的尺寸与实际YUV文件不符
3. **文件路径错误**：检查文件是否存在且可读
4. **权限问题**：确保文件有读取权限

现在你知道如何正确准备视频文件了！🎬
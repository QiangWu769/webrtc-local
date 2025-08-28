# WebRTC 客户端 JSON 配置文件使用指南

## 概述

WebRTC原生客户端现在支持通过JSON配置文件进行高级配置，类似于AlphaRTC的配置方式。这种方式提供了更灵活和集中的配置管理。

## 功能特性

✅ **视频源配置** - 支持摄像头、视频文件、禁用视频  
✅ **视频输出保存** - 将接收到的视频保存为YUV文件  
✅ **日志级别控制** - 设置详细的日志级别  
✅ **日志文件保存** - 将日志输出到指定文件  
✅ **自动关闭功能** - 视频传输完成后自动退出  

## 使用方法

### 基本语法

```bash
./peerconnection_client --config=/path/to/config.json
```

### 配置文件优先级

1. **JSON配置文件** (最高优先级)
2. **命令行参数** (如果没有配置文件)
3. **默认值** (最低优先级)

## 配置文件格式

### 完整配置示例

```json
{
  "video_source": {
    "camera": {
      "enabled": false
    },
    "video_file": {
      "enabled": true,
      "file_path": "/home/user/test_video.yuv",
      "width": 640,
      "height": 480,
      "fps": 30
    },
    "video_disabled": {
      "enabled": false
    }
  },
  
  "video_output": {
    "enabled": true,
    "file_path": "/home/user/output/received_video.yuv",
    "width": 640,
    "height": 480,
    "fps": 30
  },
  
  "logging": {
    "level": "info",
    "save_to_file": true,
    "log_output_path": "/home/user/logs/webrtc_client.log"
  },
  
  "auto_close_on_completion": true
}
```

## 配置选项详解

### 1. 视频源配置 (`video_source`)

#### 摄像头模式
```json
"video_source": {
  "camera": {
    "enabled": true
  },
  "video_file": {
    "enabled": false
  },
  "video_disabled": {
    "enabled": false
  }
}
```

#### 视频文件模式
```json
"video_source": {
  "camera": {
    "enabled": false
  },
  "video_file": {
    "enabled": true,
    "file_path": "/path/to/video.yuv",
    "width": 1920,
    "height": 1080,
    "fps": 25
  },
  "video_disabled": {
    "enabled": false
  }
}
```

**参数说明**：
- `file_path`: YUV或Y4M视频文件路径
- `width`: 视频宽度（YUV文件必需）
- `height`: 视频高度（YUV文件必需）
- `fps`: 帧率

#### 禁用视频模式
```json
"video_source": {
  "camera": {
    "enabled": false
  },
  "video_file": {
    "enabled": false
  },
  "video_disabled": {
    "enabled": true
  }
}
```

### 2. 视频输出配置 (`video_output`)

```json
"video_output": {
  "enabled": true,
  "file_path": "/path/to/output.yuv",
  "width": 640,
  "height": 480,
  "fps": 30
}
```

**参数说明**：
- `enabled`: 是否保存接收到的视频
- `file_path`: 输出文件路径
- `width`: 输出视频宽度
- `height`: 输出视频高度
- `fps`: 输出帧率

### 3. 日志配置 (`logging`)

```json
"logging": {
  "level": "info",
  "save_to_file": true,
  "log_output_path": "/path/to/client.log"
}
```

**参数说明**：
- `level`: 日志级别
  - `"verbose"`: 最详细的日志
  - `"info"`: 一般信息（推荐）
  - `"warning"`: 警告及错误
  - `"error"`: 仅错误信息
- `save_to_file`: 是否保存日志到文件
- `log_output_path`: 日志文件路径

### 4. 自动关闭配置

```json
"auto_close_on_completion": true
```

当设置为`true`时，客户端将在视频传输完成后自动退出。

## 实用场景示例

### 场景1: 发送端配置（使用视频文件）

**sender_config.json**:
```json
{
  "video_source": {
    "camera": {
      "enabled": false
    },
    "video_file": {
      "enabled": true,
      "file_path": "/home/user/videos/test_640x480.yuv",
      "width": 640,
      "height": 480,
      "fps": 30
    },
    "video_disabled": {
      "enabled": false
    }
  },
  
  "logging": {
    "level": "info",
    "save_to_file": true,
    "log_output_path": "/home/user/logs/sender.log"
  },
  
  "auto_close_on_completion": true
}
```

**启动命令**：
```bash
./peerconnection_client \
  --config=sender_config.json \
  --server=192.168.1.100 \
  --port=8888 \
  --autoconnect=true \
  --autocall=true
```

### 场景2: 接收端配置（保存接收视频）

**receiver_config.json**:
```json
{
  "video_source": {
    "camera": {
      "enabled": true
    },
    "video_file": {
      "enabled": false
    },
    "video_disabled": {
      "enabled": false
    }
  },
  
  "video_output": {
    "enabled": true,
    "file_path": "/home/user/output/received_video.yuv",
    "width": 640,
    "height": 480,
    "fps": 30
  },
  
  "logging": {
    "level": "warning",
    "save_to_file": true,
    "log_output_path": "/home/user/logs/receiver.log"
  },
  
  "auto_close_on_completion": false
}
```

**启动命令**：
```bash
./peerconnection_client \
  --config=receiver_config.json \
  --server=192.168.1.100 \
  --port=8888
```

### 场景3: 高质量视频测试

**hq_config.json**:
```json
{
  "video_source": {
    "camera": {
      "enabled": false
    },
    "video_file": {
      "enabled": true,
      "file_path": "/home/user/videos/hd_test_1920x1080.yuv",
      "width": 1920,
      "height": 1080,
      "fps": 25
    },
    "video_disabled": {
      "enabled": false
    }
  },
  
  "video_output": {
    "enabled": true,
    "file_path": "/home/user/output/hd_received.yuv",
    "width": 1920,
    "height": 1080,
    "fps": 25
  },
  
  "logging": {
    "level": "verbose",
    "save_to_file": true,
    "log_output_path": "/home/user/logs/hq_test.log"
  },
  
  "auto_close_on_completion": true
}
```

## 配置验证和调试

### 配置验证

启动时程序会输出配置信息：
```
[INFO] Loaded configuration from: /path/to/config.json
[INFO] === WebRTC Configuration ===
[INFO]   Video Source: Video File
[INFO]   Video File: /home/user/test.yuv
[INFO]   Video Resolution: 640x480
[INFO]   Video FPS: 30
[INFO]   Save Video: Yes
[INFO]   Output File: /home/user/output.yuv
[INFO]   Log Level: info
[INFO]   Auto Close: Yes
[INFO] ============================
```

### 常见错误

1. **配置文件不存在**
   ```
   [ERROR] Failed to open config file: /path/to/config.json
   ```

2. **JSON格式错误**
   ```
   [ERROR] Failed to parse JSON config file: ...
   ```

3. **视频文件不存在**
   ```
   [ERROR] Failed to create frame generator from file: /path/to/video.yuv
   ```

## 最佳实践

1. **使用绝对路径** - 避免相对路径导致的文件找不到问题
2. **设置合理的日志级别** - 开发时用`verbose`，生产时用`warning`
3. **检查磁盘空间** - 输出视频文件可能很大
4. **备份配置文件** - 为不同测试场景创建多个配置文件

## 与命令行参数的兼容性

如果同时使用配置文件和命令行参数：
- **视频相关设置**：配置文件优先
- **网络连接设置**：命令行参数有效
- **其他设置**：配置文件优先

例如：
```bash
./peerconnection_client \
  --config=my_config.json \
  --server=localhost \
  --port=8888 \
  --autoconnect=true
```

这种情况下，视频设置来自`my_config.json`，但连接设置来自命令行参数。
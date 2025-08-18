# 🎯 WebRTC客户端配置指南

## ✅ **新增功能 - 服务器配置支持**

现在WebRTC客户端完全支持在JSON配置文件中指定服务器IP、端口和连接设置！

## 📝 **完整配置文件格式**

```json
{
  "video_source": {
    "camera": {
      "enabled": false
    },
    "video_file": {
      "enabled": true,
      "file_path": "/home/wuq/webrtc-checkout/test_video.yuv",
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
    "file_path": "/home/wuq/webrtc-checkout/results/received_video.yuv",
    "width": 640,
    "height": 480,
    "fps": 30
  },
  "logging": {
    "level": "info",
    "save_to_file": true,
    "log_output_path": "/home/wuq/webrtc-checkout/results/client.log"
  },
  "server": {
    "host": "localhost",
    "port": 8888,
    "auto_connect": true,
    "auto_call": true
  },
  "auto_close_on_completion": true
}
```

## 🌐 **服务器配置选项**

### `server.host` (字符串)
- **默认值**: `"localhost"`
- **描述**: WebRTC信令服务器的IP地址或主机名
- **示例**: 
  - `"localhost"` - 本地服务器
  - `"192.168.1.100"` - 局域网服务器
  - `"webrtc.example.com"` - 远程服务器

### `server.port` (整数)
- **默认值**: `8888`
- **描述**: 服务器端口号
- **范围**: 1-65535
- **示例**: `8888`, `9999`

### `server.auto_connect` (布尔值)
- **默认值**: `true`
- **描述**: 启动后是否自动连接到服务器
- **值**: `true` | `false`

### `server.auto_call` (布尔值)
- **默认值**: `true` (sender), `false` (receiver)
- **描述**: 连接后是否自动发起通话
- **值**: `true` | `false`
- **建议配置**:
  - **Sender**: `true` - 主动发起通话
  - **Receiver**: `false` - 等待接收通话

## 🚀 **使用方法**

### 1. **命令行启动**
```bash
# 使用配置文件（推荐）
./out/Default/peerconnection_client --config=sender_config.json

# 仍然支持命令行参数（优先级低于配置文件）
./out/Default/peerconnection_client --server=192.168.1.100 --port=9999
```

### 2. **自动化脚本启动**
```bash
# 使用更新后的自动化脚本
python3 automated_webrtc_test.py

# 或使用快捷脚本
./run_webrtc_test.sh
```

## 🔧 **配置优先级**

1. **配置文件设置** (最高优先级)
2. **命令行参数** (较低优先级)
3. **默认值** (最低优先级)

如果指定了`--config`参数，客户端会：
1. 首先从配置文件读取所有设置
2. 未在配置文件中指定的设置，使用命令行参数
3. 都未指定的设置，使用默认值

## 📊 **典型使用场景**

### 🎬 **本地测试**
```json
{
  "server": {
    "host": "localhost",
    "port": 8888,
    "auto_connect": true,
    "auto_call": true
  }
}
```

### 🌐 **远程测试**
```json
{
  "server": {
    "host": "192.168.1.100",
    "port": 9999,
    "auto_connect": true,
    "auto_call": true
  }
}
```

### 🔄 **分布式测试**
**Sender配置**:
```json
{
  "server": {
    "host": "central-server.example.com",
    "port": 8888,
    "auto_connect": true,
    "auto_call": true
  }
}
```

**Receiver配置**:
```json
{
  "server": {
    "host": "central-server.example.com", 
    "port": 8888,
    "auto_connect": true,
    "auto_call": false
  }
}
```

## 🎯 **自动化测试配置**

自动化脚本(`automated_webrtc_test.py`)现在会自动生成包含服务器配置的配置文件：

- **Sender**: `auto_call: true` - 主动发起通话
- **Receiver**: `auto_call: false` - 被动接收通话
- **服务器**: 自动启动本地服务器在`localhost:8888`

## ✅ **验证配置**

启动客户端时，会在日志中看到：
```
Using server config from file: localhost:8888 (autoconnect=1, autocall=1)
=== WebRTC Configuration ===
  Video Source: Video File
  ...
  Server Host: localhost
  Server Port: 8888  
  Auto Connect: Yes
  Auto Call: Yes
============================
```

## 🛠️ **故障排除**

### ❌ **"Invalid port" 错误**
- 检查`server.port`值是否在1-65535范围内

### ❌ **连接失败**
- 确认服务器地址和端口正确
- 检查防火墙设置
- 验证服务器是否正在运行

### ❌ **配置文件解析失败**
- 检查JSON格式是否正确
- 确认文件路径存在且可读

---

🎉 **现在您可以完全通过配置文件控制WebRTC客户端的所有行为！**
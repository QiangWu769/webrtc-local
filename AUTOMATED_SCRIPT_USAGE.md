# 🎯 自动化脚本使用指南

## ✅ **如何使用results目录中的配置文件**

现在自动化脚本`automated_webrtc_test.py`完全支持使用您在`results/`目录中已有的配置文件！

## 🚀 **快速使用方法**

### 1. **使用已有配置文件运行测试**
```bash
# 使用results目录中的sender_config.json和receiver_config.json
python3 automated_webrtc_test.py --use-existing-config --non-interactive
```

### 2. **生成新配置文件运行测试**
```bash
# 生成新的配置文件（默认行为）
python3 automated_webrtc_test.py --non-interactive
```

### 3. **交互模式（默认）**
```bash
# 会询问您是否开始测试
python3 automated_webrtc_test.py --use-existing-config
```

## 📋 **命令行参数详解**

| 参数 | 描述 | 默认值 |
|------|------|--------|
| `--use-existing-config` | 使用`results/sender_config.json`和`results/receiver_config.json` | 生成新配置 |
| `--no-auto-close` | 保持配置文件中的原始`auto_close_on_completion`设置 | 强制启用自动关闭 |
| `--non-interactive` | 非交互模式，直接开始测试 | 交互模式 |
| `--help` | 显示帮助信息 | - |

## 🔧 **使用已有配置的优势**

### ✅ **保持您的自定义设置**
- 🌐 **服务器配置**: 保持您指定的IP地址和端口
- 🎥 **视频源设置**: 保持您选择的视频源类型
- 📊 **日志级别**: 保持您设置的日志详细程度
- ⚙️  **其他选项**: 保持所有自定义配置

### ✅ **自动更新必要路径**
脚本会自动更新以下路径为带时间戳的版本：
- 📝 **日志文件**: `sender_20250731_123456.log`
- 🎥 **输出视频**: `received_20250731_123456.yuv`
- ⚙️  **配置副本**: `sender_config_20250731_123456.json`

## 📂 **配置文件检查**

脚本会自动检查`results/`目录中是否存在：
- `sender_config.json`
- `receiver_config.json`

如果缺少任一文件，会自动切换到生成新配置模式。

## 💡 **实际使用示例**

### 🎬 **场景1: 本地测试**
您的`results/sender_config.json`:
```json
{
  "server": {
    "host": "localhost",
    "port": 8888,
    "auto_connect": true,
    "auto_call": true
  },
  "auto_close_on_completion": false
}
```

运行命令:
```bash
python3 automated_webrtc_test.py --use-existing-config --non-interactive
```

脚本会：
- ✅ 使用`localhost:8888`作为服务器
- ✅ 自动强制启用`auto_close_on_completion: true`
- ✅ 生成带时间戳的日志和视频文件

### 🌐 **场景2: 远程服务器测试**
您的`results/sender_config.json`:
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

运行命令:
```bash
python3 automated_webrtc_test.py --use-existing-config --no-auto-close
```

脚本会：
- ✅ 连接到`192.168.1.100:9999`
- ✅ 保持原始的`auto_close_on_completion`设置
- ✅ 使用您的所有其他自定义配置

## 🛠️ **快捷使用脚本**

为了更方便，我还创建了一个交互式使用示例脚本：

```bash
# 给脚本添加执行权限
chmod +x usage_examples.sh

# 运行交互式菜单
./usage_examples.sh
```

这个脚本提供了：
- 🔍 **配置文件检查**: 查看当前配置文件内容
- 🆕 **新配置测试**: 一键生成新配置并运行
- 🔄 **已有配置测试**: 一键使用已有配置运行
- 📖 **帮助信息**: 显示详细的命令行参数说明

## 📊 **测试结果管理**

每次测试都会生成独特的时间戳文件：
```
results/
├── sender_config_20250731_123456.json    # 本次测试的配置副本
├── receiver_config_20250731_123456.json  # 本次测试的配置副本
├── sender_20250731_123456.log            # Sender日志
├── receiver_20250731_123456.log          # Receiver日志
├── server_20250731_123456.log            # 服务器日志
├── received_20250731_123456.yuv          # 接收的视频
└── TEST_REPORT_20250731_123456.md        # 测试报告
```

## 🎯 **总结**

现在您可以：

1. **📝 编辑配置**: 修改`results/sender_config.json`和`results/receiver_config.json`
2. **🚀 一键运行**: `python3 automated_webrtc_test.py --use-existing-config --non-interactive`
3. **📊 查看结果**: 检查生成的日志和视频文件
4. **🔄 重复测试**: 保持相同配置，生成新的时间戳文件

**完美解决了您使用已有配置文件的需求！** 🎉
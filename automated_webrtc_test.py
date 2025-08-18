#!/usr/bin/env python3
"""
🚀 WebRTC视频质量测试自动化脚本（适配新的简化机制）

该脚本自动化执行完整的WebRTC视频传输测试：
1. 启动Xvfb虚拟显示
2. 启动signaling server
3. 先启动receiver，再启动sender客户端（正确的P2P连接顺序）
4. 自动收集日志和双文件视频输出
5. 生成测试报告

新机制特性：
- ✅ 简化定时器：使用transmission_time_seconds配置
- ✅ 双文件输出：发送方本地副本 + 接收方网络传输文件
- ✅ 自动关闭：无需复杂检测，配置时间到达即退出

使用方法:
    python3 automated_webrtc_test.py
    python3 automated_webrtc_test.py --use-existing-config
    python3 automated_webrtc_test.py --direct-use-config --use-existing-config

作者: WebRTC视频质量测试团队
"""

import subprocess
import time
import json
import os
import signal
import sys
from datetime import datetime
from pathlib import Path
import threading
import shutil

class WebRTCTestAutomation:
    def __init__(self, use_existing_config=False, force_auto_close=True, direct_use_config=False):
        self.base_dir = Path("/home/wuq/webrtc-checkout")
        self.src_dir = self.base_dir / "src"
        self.results_dir = self.base_dir / "results"
        self.test_video = self.base_dir / "test_video.yuv"
        
        # 配置选项
        self.use_existing_config = use_existing_config
        self.force_auto_close = force_auto_close
        self.direct_use_config = direct_use_config  # 直接使用配置文件，不生成副本
        
        # 进程管理
        self.processes = {}
        self.xvfb_display = ":99"
        
        # 测试配置
        self.test_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.test_name = f"webrtc_test_{self.test_timestamp}"
        
        # 可执行文件路径
        self.server_exe = self.src_dir / "out/Default/peerconnection_server"
        self.client_exe = self.src_dir / "out/Default/peerconnection_client"
        
        # 预定义的配置文件路径
        self.existing_sender_config = self.results_dir / "sender_config.json"
        self.existing_receiver_config = self.results_dir / "receiver_config.json"
        
        print(f"🎯 WebRTC测试自动化脚本初始化完成")
        print(f"📁 工作目录: {self.base_dir}")
        print(f"📊 测试名称: {self.test_name}")
        print(f"⚙️  使用已有配置: {'是' if use_existing_config else '否'}")
        print(f"📂 直接使用配置: {'是' if direct_use_config else '否'}")
        print(f"🔄 强制自动关闭: {'是' if force_auto_close else '否'}")

    def check_prerequisites(self):
        """检查测试前提条件"""
        print("\n🔍 检查测试前提条件...")
        
        # 检查可执行文件
        if not self.server_exe.exists():
            raise FileNotFoundError(f"❌ 服务器可执行文件不存在: {self.server_exe}")
        if not self.client_exe.exists():
            raise FileNotFoundError(f"❌ 客户端可执行文件不存在: {self.client_exe}")
            
        # 检查测试视频文件
        if not self.test_video.exists():
            raise FileNotFoundError(f"❌ 测试视频文件不存在: {self.test_video}")
            
        # 创建results目录
        self.results_dir.mkdir(exist_ok=True)
        
        # 检查Xvfb
        try:
            subprocess.run(["which", "xvfb-run"], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            raise RuntimeError("❌ Xvfb未安装，请安装: sudo apt-get install xvfb")
            
        print("✅ 所有前提条件检查通过")

    def prepare_config_files(self):
        """准备配置文件"""
        print("\n📝 准备配置文件...")
        
        if self.use_existing_config and self.existing_sender_config.exists() and self.existing_receiver_config.exists():
            if self.direct_use_config:
                print("📂 直接使用已有配置文件...")
                self.sender_config_path, self.receiver_config_path = self._direct_use_configs()
            else:
                print("🔄 使用已有配置文件...")
                self.sender_config_path, self.receiver_config_path = self._use_existing_configs()
        else:
            print("🆕 生成新的配置文件...")
            self.sender_config_path, self.receiver_config_path = self._generate_new_configs()
        
        print(f"✅ 配置文件准备完成:")
        print(f"   📤 Sender: {self.sender_config_path}")
        print(f"   📥 Receiver: {self.receiver_config_path}")

    def _use_existing_configs(self):
        """使用已有的配置文件，并根据需要修改"""
        print(f"   📂 读取已有配置: {self.existing_sender_config.name}, {self.existing_receiver_config.name}")
        
        # 读取已有的配置文件
        with open(self.existing_sender_config, 'r') as f:
            sender_config = json.load(f)
        with open(self.existing_receiver_config, 'r') as f:
            receiver_config = json.load(f)
        
        # 更新日志文件路径为带时间戳的版本
        sender_config["logging"]["log_output_path"] = str(self.results_dir / f"sender_{self.test_name}.log")
        receiver_config["logging"]["log_output_path"] = str(self.results_dir / f"receiver_{self.test_name}.log")
        
        # 更新接收端视频输出路径
        if receiver_config.get("video_output", {}).get("enabled", False):
            receiver_config["video_output"]["file_path"] = str(self.results_dir / f"received_{self.test_name}.yuv")
        
        # 更新发送端视频输出路径（双文件输出）
        if not sender_config.get("video_output", {}).get("enabled", False):
            sender_config["video_output"] = {
                "enabled": True,
                "file_path": str(self.results_dir / f"output_{self.test_name}.yuv"),
                "width": 640,
                "height": 480,
                "fps": 30
            }
            print("   📤 启用发送方视频输出（双文件机制）")
        else:
            sender_config["video_output"]["file_path"] = str(self.results_dir / f"output_{self.test_name}.yuv")
        
        # 确保包含transmission_time_seconds字段（适应新的简化定时器机制）
        if "transmission_time_seconds" not in sender_config:
            sender_config["transmission_time_seconds"] = 25
            print("   ⏱️  为发送方添加transmission_time_seconds: 25秒")
        if "transmission_time_seconds" not in receiver_config:
            receiver_config["transmission_time_seconds"] = 30
            print("   ⏱️  为接收方添加transmission_time_seconds: 30秒")
        
        # 根据force_auto_close选项决定是否覆盖auto_close_on_completion设置
        if self.force_auto_close:
            sender_config["auto_close_on_completion"] = True
            receiver_config["auto_close_on_completion"] = True
            print("   🔄 强制启用自动关闭功能")
        
        # 保存修改后的配置文件（带时间戳）
        sender_config_path = self.results_dir / f"sender_config_{self.test_name}.json"
        receiver_config_path = self.results_dir / f"receiver_config_{self.test_name}.json"
        
        with open(sender_config_path, 'w') as f:
            json.dump(sender_config, f, indent=2)
        with open(receiver_config_path, 'w') as f:
            json.dump(receiver_config, f, indent=2)
        
        return sender_config_path, receiver_config_path

    def _direct_use_configs(self):
        """直接使用已有的配置文件，确保auto_close_on_completion为true"""
        print(f"   📂 直接使用配置: {self.existing_sender_config.name}, {self.existing_receiver_config.name}")
        
        # 读取配置文件以检查和更新必要字段
        with open(self.existing_sender_config, 'r') as f:
            sender_config = json.load(f)
        with open(self.existing_receiver_config, 'r') as f:
            receiver_config = json.load(f)
        
        # 检查是否需要修改
        sender_needs_update = False
        receiver_needs_update = False
        
        # 检查auto_close_on_completion字段
        if self.force_auto_close:
            if sender_config.get("auto_close_on_completion") != True:
                sender_config["auto_close_on_completion"] = True
                sender_needs_update = True
            if receiver_config.get("auto_close_on_completion") != True:
                receiver_config["auto_close_on_completion"] = True
                receiver_needs_update = True
        
        # 检查transmission_time_seconds字段（适应新的简化定时器机制）
        if "transmission_time_seconds" not in sender_config:
            sender_config["transmission_time_seconds"] = 25
            sender_needs_update = True
            print("   ⏱️  为发送方添加transmission_time_seconds: 25秒")
        if "transmission_time_seconds" not in receiver_config:
            receiver_config["transmission_time_seconds"] = 30
            receiver_needs_update = True
            print("   ⏱️  为接收方添加transmission_time_seconds: 30秒")
        
        # 启用发送方视频输出（双文件机制）
        if not sender_config.get("video_output", {}).get("enabled", False):
            sender_config["video_output"] = {
                "enabled": True,
                "file_path": str(self.results_dir / f"output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.yuv"),
                "width": 640,
                "height": 480,
                "fps": 30
            }
            sender_needs_update = True
            print("   📤 启用发送方视频输出（双文件机制）")
        
        # 保存修改后的配置文件
        if sender_needs_update or receiver_needs_update:
            if self.force_auto_close:
                print("   🔄 更新配置文件以支持新的机制")
            
        if sender_needs_update:
            with open(self.existing_sender_config, 'w') as f:
                json.dump(sender_config, f, indent=2)
            print(f"   📤 已更新 {self.existing_sender_config.name}")
        
        if receiver_needs_update:
            with open(self.existing_receiver_config, 'w') as f:
                json.dump(receiver_config, f, indent=2)
            print(f"   📥 已更新 {self.existing_receiver_config.name}")
        
        return self.existing_sender_config, self.existing_receiver_config

    def _generate_new_configs(self):
        """生成新的配置文件"""
        # Sender配置 - 发送视频文件，输出本地副本，自动关闭
        sender_config = {
            "video_source": {
                "camera": {"enabled": False},
                "video_file": {
                    "enabled": True,
                    "file_path": str(self.test_video),
                    "width": 640,
                    "height": 480,
                    "fps": 30
                },
                "video_disabled": {"enabled": False}
            },
            "video_output": {
                "enabled": True,
                "file_path": str(self.results_dir / f"output_{self.test_name}.yuv"),
                "width": 640,
                "height": 480,
                "fps": 30
            },
            "logging": {
                "level": "info",
                "save_to_file": True,
                "log_output_path": str(self.results_dir / f"sender_{self.test_name}.log")
            },
            "auto_close_on_completion": True,
            "transmission_time_seconds": 25  # 发送方25秒后自动关闭
        }
        
        # Receiver配置 - 接收并保存视频，自动关闭
        receiver_config = {
            "video_source": {
                "camera": {"enabled": False},
                "video_file": {"enabled": False},
                "video_disabled": {"enabled": True}
            },
            "video_output": {
                "enabled": True,
                "file_path": str(self.results_dir / f"received_{self.test_name}.yuv"),
                "width": 640,
                "height": 480,
                "fps": 30
            },
            "logging": {
                "level": "info",
                "save_to_file": True,
                "log_output_path": str(self.results_dir / f"receiver_{self.test_name}.log")
            },
            "auto_close_on_completion": True,
            "transmission_time_seconds": 30  # 接收方30秒后自动关闭（留更多缓冲时间）
        }
        
        # 保存配置文件
        sender_config_path = self.results_dir / f"sender_config_{self.test_name}.json"
        receiver_config_path = self.results_dir / f"receiver_config_{self.test_name}.json"
        
        with open(sender_config_path, 'w') as f:
            json.dump(sender_config, f, indent=2)
        with open(receiver_config_path, 'w') as f:
            json.dump(receiver_config, f, indent=2)
            
        return sender_config_path, receiver_config_path

    def start_xvfb(self):
        """启动Xvfb虚拟显示"""
        print(f"\n🖥️  启动Xvfb虚拟显示 {self.xvfb_display}...")
        
        # 杀死可能存在的Xvfb进程
        try:
            subprocess.run(["pkill", "-f", f"Xvfb.*{self.xvfb_display[1:]}"], 
                         capture_output=True)
        except:
            pass
            
        time.sleep(1)
        
        # 启动Xvfb
        cmd = ["Xvfb", self.xvfb_display, "-screen", "0", "1024x768x24", "-ac"]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.processes['xvfb'] = process
        
        # 设置DISPLAY环境变量
        os.environ['DISPLAY'] = self.xvfb_display
        
        time.sleep(2)
        print(f"✅ Xvfb已启动 (PID: {process.pid})")

    def start_server(self):
        """启动signaling server"""
        print("\n🌐 启动WebRTC信令服务器...")
        
        server_log_path = self.results_dir / f"server_{self.test_name}.log"
        
        with open(server_log_path, 'w') as log_file:
            process = subprocess.Popen(
                [str(self.server_exe)],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                cwd=str(self.src_dir),
                env=os.environ.copy()
            )
        
        self.processes['server'] = process
        time.sleep(3)  # 等待服务器启动
        
        print(f"✅ 信令服务器已启动 (PID: {process.pid})")
        print(f"📝 服务器日志: {server_log_path}")

    def start_client(self, role, config_path, delay=0):
        """启动WebRTC客户端"""
        if delay > 0:
            print(f"⏱️  等待{delay}秒后启动{role}...")
            time.sleep(delay)
            
        print(f"🚀 启动{role}客户端...")
        
        console_log_path = self.results_dir / f"{role}_console_{self.test_name}.log"
        
        cmd = [
            str(self.client_exe),
            f"--config={config_path}"
        ]
        
        env = os.environ.copy()
        env['DISPLAY'] = self.xvfb_display
        
        with open(console_log_path, 'w') as log_file:
            process = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                cwd=str(self.src_dir),
                env=env
            )
        
        self.processes[role] = process
        print(f"✅ {role}客户端已启动 (PID: {process.pid})")
        print(f"📝 控制台日志: {console_log_path}")
        
        return process

    def monitor_processes(self):
        """监控进程状态"""
        print("\n👀 监控测试进程...")
        
        start_time = time.time()
        max_duration = 300  # 最大测试时间5分钟
        check_interval = 5   # 更频繁检查：每5秒一次
        no_change_timeout = 30  # 如果30秒内进程状态没变化，认为可能卡住了
        
        last_status_change = start_time
        prev_sender_running = True
        prev_receiver_running = True
        
        while True:
            current_time = time.time()
            elapsed = current_time - start_time
            
            # 检查是否超时
            if elapsed > max_duration:
                print(f"⏰ 测试超时({max_duration}秒)，强制结束")
                break
            
            # 检查客户端进程状态
            sender_running = self.processes.get('sender') and self.processes['sender'].poll() is None
            receiver_running = self.processes.get('receiver') and self.processes['receiver'].poll() is None
            
            # 检测状态变化
            status_changed = (sender_running != prev_sender_running or 
                            receiver_running != prev_receiver_running)
            
            if status_changed:
                last_status_change = current_time
                print(f"🔄 进程状态变化 [{elapsed:.0f}s]: Sender={sender_running}, Receiver={receiver_running}")
            else:
                print(f"📊 测试状态 [{elapsed:.0f}s]: Sender={sender_running}, Receiver={receiver_running}")
            
            # 如果两个客户端都停止了，测试完成
            if not sender_running and not receiver_running:
                print("🎉 两个客户端都已完成，测试结束")
                break
            
            # 如果有一个进程结束了，给另一个进程一些时间也结束
            if (not sender_running or not receiver_running) and elapsed > 60:
                print(f"⏳ 部分进程已完成，等待剩余进程结束...")
                # 如果一个进程结束超过30秒，另一个还在运行，可能有问题
                time_since_change = current_time - last_status_change
                if time_since_change > 30:
                    print(f"⚠️  部分进程超过30秒未响应，可能需要手动结束")
                    break
            
            prev_sender_running = sender_running
            prev_receiver_running = receiver_running
            
            time.sleep(check_interval)  # 每5秒检查一次
        
        print(f"✅ 测试监控完成，总耗时: {elapsed:.1f}秒")

    def cleanup_processes(self):
        """清理所有进程"""
        print("\n🧹 清理测试进程...")
        
        for name, process in self.processes.items():
            if process and process.poll() is None:
                print(f"🛑 终止{name}进程 (PID: {process.pid})")
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print(f"⚡ 强制杀死{name}进程")
                    process.kill()
                except:
                    pass
        
        # 额外清理Xvfb
        try:
            subprocess.run(["pkill", "-f", f"Xvfb.*{self.xvfb_display[1:]}"], 
                         capture_output=True)
        except:
            pass
            
        print("✅ 进程清理完成")

    def generate_report(self):
        """生成测试报告"""
        print("\n📊 生成测试报告...")
        
        report_path = self.results_dir / f"TEST_REPORT_{self.test_name}.md"
        
        # 收集文件信息
        log_files = list(self.results_dir.glob(f"*_{self.test_name}.log"))
        video_files = list(self.results_dir.glob(f"*_{self.test_name}.yuv"))
        config_files = list(self.results_dir.glob(f"*config_{self.test_name}.json"))
        
        # 分析视频文件
        output_files = [f for f in video_files if f.name.startswith('output_')]
        received_files = [f for f in video_files if f.name.startswith('received_')]
        
        report_content = f"""# 🎯 WebRTC视频质量测试报告

## 📋 测试信息
- **测试名称**: {self.test_name}
- **测试时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
- **测试视频**: {self.test_video.name}
- **测试机制**: 简化定时器 + 双文件输出

## 🔧 测试机制说明
- **定时器机制**: 使用`transmission_time_seconds`配置的简化定时器
- **双文件输出**: 发送方输出本地副本，接收方保存接收到的视频
- **自动关闭**: 配置时间到达后自动结束，无需复杂检测

## 📁 生成的文件

### 📝 日志文件
"""
        
        for log_file in sorted(log_files):
            size_mb = log_file.stat().st_size / (1024 * 1024)
            report_content += f"- `{log_file.name}` ({size_mb:.1f}MB)\n"
        
        report_content += "\n### 🎥 视频文件（双文件输出）\n"
        
        # 分别显示发送方和接收方文件
        if output_files:
            report_content += "\n#### 📤 发送方输出文件\n"
            for video_file in sorted(output_files):
                size_mb = video_file.stat().st_size / (1024 * 1024)
                report_content += f"- `{video_file.name}` ({size_mb:.1f}MB) - 发送方本地副本\n"
        
        if received_files:
            report_content += "\n#### 📥 接收方输出文件\n"
            for video_file in sorted(received_files):
                size_mb = video_file.stat().st_size / (1024 * 1024)
                report_content += f"- `{video_file.name}` ({size_mb:.1f}MB) - 网络传输后接收\n"
        
        # 如果有其他视频文件
        other_files = [f for f in video_files if not f.name.startswith(('output_', 'received_'))]
        if other_files:
            report_content += "\n#### 📹 其他视频文件\n"
            for video_file in sorted(other_files):
                size_mb = video_file.stat().st_size / (1024 * 1024)
                report_content += f"- `{video_file.name}` ({size_mb:.1f}MB)\n"
        
        report_content += "\n### ⚙️ 配置文件\n"
        for config_file in sorted(config_files):
            report_content += f"- `{config_file.name}`\n"
        
        report_content += f"""
## 🔍 关键指标日志搜索

在日志文件中搜索以下关键词来查看视频质量指标：

```bash
# 视频码率统计
grep "VideoQuality-Bitrate" {self.results_dir}/*_{self.test_name}.log

# 帧率统计  
grep "VideoQuality-FrameRate" {self.results_dir}/*_{self.test_name}.log

# 卡顿率统计
grep "VideoQuality-FreezeRate" {self.results_dir}/*_{self.test_name}.log
```

## 📈 后续分析建议

1. **视频质量分析**: 使用PSNR/SSIM工具比较输入输出视频
2. **统计数据提取**: 从日志中提取关键性能指标
3. **结果可视化**: 生成图表展示质量变化趋势

---
*报告生成时间: {datetime.now().isoformat()}*
"""
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        print(f"✅ 测试报告已生成: {report_path}")
        
        # 显示文件列表
        print(f"\n📁 本次测试生成的所有文件:")
        all_files = (list(log_files) + list(video_files) + 
                    list(config_files) + [report_path])
        for file_path in sorted(all_files):
            size_mb = file_path.stat().st_size / (1024 * 1024)
            print(f"   📄 {file_path.name} ({size_mb:.1f}MB)")

    def run_test(self):
        """运行完整测试"""
        try:
            print("🚀 开始WebRTC视频质量自动化测试")
            print("=" * 50)
            
            # 步骤1: 检查前提条件
            self.check_prerequisites()
            
            # 步骤2: 准备配置文件
            self.prepare_config_files()
            
            # 步骤3: 启动Xvfb
            self.start_xvfb()
            
            # 步骤4: 启动服务器
            self.start_server()
            
            # 步骤5: 启动客户端（正确顺序：先接收端，后发送端）
            self.start_client('receiver', self.receiver_config_path, delay=2)
            self.start_client('sender', self.sender_config_path, delay=5)
            
            # 步骤6: 监控测试进程
            self.monitor_processes()
            
            # 步骤7: 生成报告
            self.generate_report()
            
            print("\n🎉 测试完成！")
            
        except Exception as e:
            print(f"\n❌ 测试失败: {e}")
            return 1
        finally:
            # 步骤8: 清理进程
            self.cleanup_processes()
        
        return 0

def signal_handler(sig, frame):
    """处理Ctrl+C信号"""
    print('\n🛑 收到中断信号，正在清理...')
    sys.exit(0)

def main():
    """主函数"""
    import argparse
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='WebRTC视频质量测试自动化脚本')
    parser.add_argument('--use-existing-config', action='store_true', 
                       help='使用results目录中已有的配置文件（sender_config.json, receiver_config.json）')
    parser.add_argument('--direct-use-config', action='store_true',
                       help='直接使用已有配置文件，不生成带时间戳的副本（需要与--use-existing-config一起使用）')
    parser.add_argument('--no-auto-close', action='store_true',
                       help='不强制启用自动关闭功能，保持配置文件中的原始设置')
    parser.add_argument('--interactive', action='store_true', default=True,
                       help='交互模式，启动前需要确认（默认启用）')
    parser.add_argument('--non-interactive', action='store_true',
                       help='非交互模式，直接开始测试')
    
    args = parser.parse_args()
    
    # 确定是否使用交互模式
    interactive_mode = args.interactive and not args.non_interactive
    
    print("""
    🎯 WebRTC视频质量测试自动化脚本（新简化机制）
    ===============================================
    
    该脚本将自动执行：
    1. 启动Xvfb虚拟显示
    2. 启动WebRTC信令服务器  
    3. 先启动接收端，再启动发送端客户端（正确的P2P连接顺序）
    4. 监控测试进程
    5. 收集日志和双文件视频输出
    6. 生成测试报告
    
    🆕 新机制特性：
    ⏱️  简化定时器：使用transmission_time_seconds配置
    📁 双文件输出：发送方本地副本 + 接收方网络传输文件
    🔄 自动关闭：无需复杂检测，时间到即退出
    
    按Ctrl+C可随时中断测试
    """)
    
    # 显示配置选项
    print("🔧 当前配置:")
    print(f"   📂 使用已有配置文件: {'是' if args.use_existing_config else '否'}")
    print(f"   📁 直接使用配置: {'是' if args.direct_use_config else '否'}")
    print(f"   🔄 强制自动关闭: {'否' if args.no_auto_close else '是'}")
    print(f"   💬 交互模式: {'是' if interactive_mode else '否'}")
    print()
    
    # 交互确认
    if interactive_mode:
        try:
            input("按Enter键开始测试，或Ctrl+C取消...")
        except KeyboardInterrupt:
            print("\n❌ 测试已取消")
            return 1
    
    # 运行测试
    test_automation = WebRTCTestAutomation(
        use_existing_config=args.use_existing_config,
        force_auto_close=not args.no_auto_close,
        direct_use_config=args.direct_use_config
    )
    return test_automation.run_test()

if __name__ == "__main__":
    sys.exit(main())
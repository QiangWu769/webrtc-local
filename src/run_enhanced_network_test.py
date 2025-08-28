#!/usr/bin/env python3
"""
Enhanced WebRTC Client Network Test Script
适用于增强版WebRTC客户端的网络测试脚本
"""
import yaml
import subprocess
import time
import os
import signal
import shutil
import sys
import hashlib
import json

# --- 读取配置 ---
# 创建默认配置文件如果不存在
default_config = {
    'webrtc_build_dir': '/home/wuq/webrtc-checkout/src/out/Default',
    'results_dir': './test_results',
    'duration': 30,
    'signaling_server_ip': 'localhost',
    'signaling_server_port': 8888,
    'video': {
        'width': 640,
        'height': 480,
        'fps': 30,
        'file_path': '/path/to/test_video.y4m',
        'loop': False
    }
}

config_file = 'enhanced_network_config.yaml'
if not os.path.exists(config_file):
    print(f"创建默认配置文件: {config_file}")
    with open(config_file, 'w') as f:
        yaml.dump(default_config, f, default_flow_style=False)
    print("请编辑配置文件后重新运行")
    sys.exit(0)

with open(config_file, 'r') as f:
    config = yaml.safe_load(f)

# --- 定义常量和路径 ---
BUILD_DIR = config['webrtc_build_dir']
CLIENT_EXEC = os.path.join(BUILD_DIR, "peerconnection_client")
SERVER_EXEC = os.path.join(BUILD_DIR, "peerconnection_server")
RESULTS_DIR = config['results_dir']
DURATION = config['duration']
SERVER_IP = config['signaling_server_ip']
SERVER_PORT = config['signaling_server_port']

# 视频设置
VIDEO_WIDTH = config['video'].get('width', 640)
VIDEO_HEIGHT = config['video'].get('height', 480)
VIDEO_FPS = config['video'].get('fps', 30)
VIDEO_FILE_PATH = config['video'].get('file_path', '')
VIDEO_LOOP = config['video'].get('loop', False)

# --- 创建适配我们客户端的JSON配置文件 ---
def create_enhanced_webrtc_config(config_path, is_sender=True):
    """为发送端或接收端创建适配我们增强版WebRTC客户端的JSON配置文件"""
    
    if is_sender:
        if os.path.exists(VIDEO_FILE_PATH) and os.path.getsize(VIDEO_FILE_PATH) > 1000000:
            # 发送端使用视频文件
            webrtc_config = {
                "video_source": {
                    "camera": {"enabled": False},
                    "video_file": {
                        "enabled": True,
                        "file_path": VIDEO_FILE_PATH,
                        "width": VIDEO_WIDTH,
                        "height": VIDEO_HEIGHT,
                        "fps": VIDEO_FPS
                    },
                    "video_disabled": {"enabled": False}
                },
                "video_output": {
                    "enabled": False,  # 发送端不保存视频
                    "file_path": "",
                    "width": VIDEO_WIDTH,
                    "height": VIDEO_HEIGHT,
                    "fps": VIDEO_FPS
                },
                "logging": {
                    "level": "info",
                    "save_to_file": True,
                    "log_output_path": os.path.join(RESULTS_DIR, "sender_detailed.log")
                },
                "auto_close_on_completion": True
            }
            print(f"✅ 发送端配置: 使用视频文件 {VIDEO_FILE_PATH}")
        else:
            # 使用摄像头/假视频生成器
            webrtc_config = {
                "video_source": {
                    "camera": {"enabled": True},  # 使用摄像头或假视频生成器
                    "video_file": {"enabled": False},
                    "video_disabled": {"enabled": False}
                },
                "video_output": {"enabled": False},
                "logging": {
                    "level": "info",
                    "save_to_file": True,
                    "log_output_path": os.path.join(RESULTS_DIR, "sender_detailed.log")
                },
                "auto_close_on_completion": True
            }
            print("⚠️ 发送端配置: 使用摄像头/假视频生成器（视频文件不存在或太小）")
    else:
        # 接收端配置 - 不发送视频，只接收并可选保存
        webrtc_config = {
            "video_source": {
                "camera": {"enabled": False},
                "video_file": {"enabled": False},
                "video_disabled": {"enabled": True}  # 接收端禁用视频发送
            },
            "video_output": {
                "enabled": True,  # 接收端保存接收到的视频
                "file_path": os.path.join(RESULTS_DIR, "received_video.yuv"),
                "width": VIDEO_WIDTH,
                "height": VIDEO_HEIGHT,
                "fps": VIDEO_FPS
            },
            "logging": {
                "level": "info",
                "save_to_file": True,
                "log_output_path": os.path.join(RESULTS_DIR, "receiver_detailed.log")
            },
            "auto_close_on_completion": True
        }
        print("📥 接收端配置: 纯接收模式，不发送视频")
    
    # 写入配置文件
    with open(config_path, 'w') as f:
        json.dump(webrtc_config, f, indent=2)
    
    print(f"创建配置文件: {config_path}")
    return config_path

# --- 验证视频文件 ---
def verify_video_file():
    print("验证视频文件...")
    if not VIDEO_FILE_PATH or not os.path.exists(VIDEO_FILE_PATH):
        print(f"视频文件不存在: {VIDEO_FILE_PATH}")
        print("警告: 将使用摄像头或帧生成器")
        return False
    
    # 检查文件大小
    file_size = os.path.getsize(VIDEO_FILE_PATH)
    if file_size < 1000000:  # 小于1MB的文件可能有问题
        print(f"警告: 视频文件大小异常小 ({file_size} 字节)，可能只有一帧")
        return False
    else:
        print(f"视频文件大小: {file_size} 字节")
        return True

# --- 准备 ---
print("--- 增强版WebRTC客户端测试设置 ---")
print(f"客户端路径: {CLIENT_EXEC}")
print(f"服务器路径: {SERVER_EXEC}")

# 验证视频文件
verify_video_file()

if os.path.exists(RESULTS_DIR):
    shutil.rmtree(RESULTS_DIR)
os.makedirs(RESULTS_DIR, exist_ok=True)
os.chmod(RESULTS_DIR, 0o777)

# 检查必要的可执行文件是否存在
for exe in [CLIENT_EXEC, SERVER_EXEC]:
    if not os.path.exists(exe):
        print(f"错误: 找不到可执行文件 {exe}")
        print("请确保WebRTC已编译且路径正确")
        sys.exit(1)

print(f"启动信令服务器，端口 {SERVER_PORT}...")
server_proc = subprocess.Popen([SERVER_EXEC], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(2)

procs_to_kill = [server_proc]

try:
    # --- 执行测试 ---
    print("\n--- 增强版WebRTC客户端网络测试执行 ---")
    print(f"视频设置: {VIDEO_WIDTH}x{VIDEO_HEIGHT} @ {VIDEO_FPS}fps")
    print(f"视频文件: {VIDEO_FILE_PATH}")
    print(f"测试时长: {DURATION}秒")

    # 创建适配我们客户端的配置文件
    sender_config_path = os.path.join(RESULTS_DIR, "sender_config.json")
    receiver_config_path = os.path.join(RESULTS_DIR, "receiver_config.json")
    
    create_enhanced_webrtc_config(sender_config_path, is_sender=True)
    create_enhanced_webrtc_config(receiver_config_path, is_sender=False)

    # 设置优化的Xvfb参数
    xvfb_cmd = [
        'Xvfb', 
        ':99', 
        '-screen', '0', f'{VIDEO_WIDTH}x{VIDEO_HEIGHT}x24',
        '-ac',           # 禁用访问控制
        '+extension', 'GLX',  # 启用GLX扩展
        '+render',       # 启用Render扩展
        '-noreset'       # 不要在最后一个客户端断开连接时重置屏幕
    ]
    
    print(f"启动Xvfb: {' '.join(xvfb_cmd)}")
    xvfb_proc = subprocess.Popen(xvfb_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    procs_to_kill.append(xvfb_proc)
    time.sleep(3)
    
    # 确认Xvfb运行正常
    xvfb_poll = xvfb_proc.poll()
    if xvfb_poll is not None:
        print(f"错误: Xvfb进程已退出，返回码: {xvfb_poll}")
        stdout, stderr = xvfb_proc.communicate()
        print(f"Xvfb stdout: {stdout.decode()}")
        print(f"Xvfb stderr: {stderr.decode()}")
        sys.exit(1)
    else:
        print("Xvfb启动成功")

    # 设置环境变量
    sender_env = os.environ.copy()
    sender_env["DISPLAY"] = ":99"
    
    receiver_env = os.environ.copy()
    receiver_env["DISPLAY"] = ":99"
    
    # 先启动接收端
    receiver_log_path = os.path.join(RESULTS_DIR, "receiver.log")
    receiver_err_path = os.path.join(RESULTS_DIR, "receiver.err")
    
    print(f"🎯 步骤1: 启动接收端")
    receiver_cmd = [
        CLIENT_EXEC,
        f"--server={SERVER_IP}",
        f"--port={SERVER_PORT}",
        f"--config={receiver_config_path}",  # 使用我们的--config参数
        "--autoconnect",
    ]
    
    print(f"接收端命令: {' '.join(receiver_cmd)}")
    with open(receiver_log_path, "w") as log_file, open(receiver_err_path, "w") as err_file:
        receiver_proc = subprocess.Popen(
            receiver_cmd,
            env=receiver_env,
            stdout=log_file,
            stderr=err_file
        )
    procs_to_kill.append(receiver_proc)
    print(f"✅ 接收端启动，PID: {receiver_proc.pid}")
    
    # 等待接收端连接到服务器
    print("等待接收端连接到信令服务器...")
    time.sleep(3)
    
    # 启动发送端
    sender_log_path = os.path.join(RESULTS_DIR, "sender.log")
    sender_err_path = os.path.join(RESULTS_DIR, "sender.err")
    
    print(f"🎯 步骤2: 启动发送端")
    sender_cmd = [
        CLIENT_EXEC,
        f"--server={SERVER_IP}",
        f"--port={SERVER_PORT}",
        f"--config={sender_config_path}",  # 使用我们的--config参数
        "--autoconnect",
        "--autocall",  # 自动呼叫第一个可用的对等端
    ]
    
    print(f"发送端命令: {' '.join(sender_cmd)}")
    
    with open(sender_log_path, "w") as log_file, open(sender_err_path, "w") as err_file:
        sender_proc = subprocess.Popen(
            sender_cmd,
            env=sender_env,
            stdout=log_file,
            stderr=err_file
        )
    procs_to_kill.append(sender_proc)
    print(f"✅ 发送端启动，PID: {sender_proc.pid}")
    
    # 等待P2P连接建立
    print("等待P2P连接建立...")
    time.sleep(5)

    # 检查是否使用真实视频文件
    USE_REAL_VIDEO = os.path.exists(VIDEO_FILE_PATH) and os.path.getsize(VIDEO_FILE_PATH) > 1000000
    
    if USE_REAL_VIDEO and not VIDEO_LOOP:
        print(f"\n使用真实视频文件（非循环模式），等待视频播放完成或最多 {DURATION} 秒...")
    else:
        print(f"\n测试运行 {DURATION} 秒...")
    
    # 定期检查客户端进程状态
    check_interval = 5
    max_checks = DURATION // check_interval
    
    print(f"\n开始监控测试运行...")
    for i in range(max_checks):
        time.sleep(check_interval)
        sender_poll = sender_proc.poll()
        receiver_poll = receiver_proc.poll()
        
        if sender_poll is not None:
            print(f"发送端进程已退出，返回码: {sender_poll}")
        if receiver_poll is not None:
            print(f"接收端进程已退出，返回码: {receiver_poll}")
            
        # 检测WebRTC连接状态
        success_indicators = {
            "ice_connected": False,
            "peer_connected": False,
            "video_track_added": False,
            "video_frames_received": False
        }
        
        # 检查发送端日志
        if os.path.exists(sender_err_path):
            try:
                with open(sender_err_path, 'r') as f:
                    sender_content = f.read()
                    if "Connected" in sender_content:
                        success_indicators["ice_connected"] = True
                    if "OnPeerConnected" in sender_content or "Peer connected" in sender_content:
                        success_indicators["peer_connected"] = True
            except Exception as e:
                print(f"读取发送端日志时出错: {e}")
        
        # 检查接收端日志
        if os.path.exists(receiver_err_path):
            try:
                with open(receiver_err_path, 'r') as f:
                    receiver_content = f.read()
                    if "OnAddTrack" in receiver_content or "Track added" in receiver_content:
                        success_indicators["video_track_added"] = True
                    if "OnFrame" in receiver_content or "Frame received" in receiver_content:
                        success_indicators["video_frames_received"] = True
                    if "Connected" in receiver_content:
                        success_indicators["ice_connected"] = True
            except Exception as e:
                print(f"读取接收端日志时出错: {e}")
        
        # 输出成功指标
        success_count = sum(success_indicators.values())
        print(f"\n📊 WebRTC连接状态检查 ({success_count}/4 成功):")
        print(f"  🤝 对等端连接: {'✅' if success_indicators['peer_connected'] else '❌'}")
        print(f"  🧊 ICE连接建立: {'✅' if success_indicators['ice_connected'] else '❌'}")
        print(f"  🎵 视频轨道添加: {'✅' if success_indicators['video_track_added'] else '❌'}")
        print(f"  📽️ 视频帧接收: {'✅' if success_indicators['video_frames_received'] else '❌'}")
        
        # 如果所有指标都成功，可以提前结束测试
        if success_count >= 3:
            print("🎉 WebRTC连接成功！大部分功能正常工作")
            if success_indicators["video_frames_received"]:
                print("🚀 视频传输确认成功！")
                # 可以选择提前结束测试
                # break
        
        if sender_poll is not None and receiver_poll is not None:
            print("两个客户端进程都已退出，测试结束")
            break
    
    # 剩余时间等待
    remaining_time = DURATION % check_interval
    if remaining_time > 0 and (sender_proc.poll() is None or receiver_proc.poll() is None):
        time.sleep(remaining_time)

finally:
    # --- 清理 ---
    print("\n--- 清理过程 ---")
    for p in reversed(procs_to_kill):
        if p.poll() is None:
            try:
                p.terminate()
                try:
                    p.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    print(f"进程 {p.pid} 没有响应terminate命令，强制终止...")
                    p.kill()
            except Exception as e:
                print(f"终止进程时出错: {e}")
    
    # 输出结果摘要
    print(f"\n测试完成。结果保存在 '{RESULTS_DIR}' 目录中")
    
    # 列出测试结果文件
    if os.path.exists(RESULTS_DIR):
        result_files = os.listdir(RESULTS_DIR)
        print(f"\n发现 {len(result_files)} 个结果文件:")
        for file in result_files:
            file_path = os.path.join(RESULTS_DIR, file)
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            print(f"- {file} ({file_size} bytes)")
            
            # 如果是日志文件，显示重要信息
            if file.endswith('.err') or file.endswith('.log'):
                try:
                    with open(file_path, 'r') as f:
                        lines = f.readlines()
                        if lines:
                            # 显示最后几行
                            last_lines = lines[-3:] if len(lines) > 3 else lines
                            print(f"  最后{len(last_lines)}行:")
                            for line in last_lines:
                                print(f"  > {line.strip()}")
                except Exception as e:
                    print(f"  读取文件失败: {e}")
    
    print("\n📋 使用说明:")
    print("1. 检查日志文件以了解详细的连接过程")
    print("2. 如果有received_video.yuv文件，说明视频传输成功")
    print("3. 调整配置文件中的参数来改变测试设置")
    print("4. 对于长时间测试，可以增加duration参数")
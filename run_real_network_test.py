import yaml
import subprocess
import time
import os
import signal
import shutil
import sys
import hashlib  # 添加hashlib模块用于MD5校验
import json  # 添加JSON模块用于配置文件

# --- 读取配置 ---
with open('real_network_config.yaml', 'r') as f:
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
VIDEO_WIDTH = config['video'].get('width', 1280)
VIDEO_HEIGHT = config['video'].get('height', 720)
VIDEO_FPS = config['video'].get('fps', 30)
VIDEO_FILE_PATH = config['video'].get('file_path', '/home/wuq/webrtc-checkout/video_1080p60.y4m')
VIDEO_LOOP = config['video'].get('loop', False)

# 音频设置（纯视频模式，音频已移除）
AUDIO_ENABLED = False  # 新的纯视频传输版本不支持音频

# --- 创建JSON配置文件 ---
def create_webrtc_config(config_path, is_sender=True):
    """为发送端或接收端创建WebRTC JSON配置文件"""
    
    # 🔧 为发送端和接收端配置不同的视频源
    if is_sender:
        if os.path.exists(VIDEO_FILE_PATH) and os.path.getsize(VIDEO_FILE_PATH) > 1000000:
            # 发送端使用视频文件 - 保持现有复杂格式以兼容客户端
            webrtc_config = {
                "video_source": {
                    "video_disabled": {"enabled": False},
                    "webcam": {"enabled": False},
                    "video_file": {
                        "enabled": True,
                        "height": VIDEO_HEIGHT,
                        "width": VIDEO_WIDTH,
                        "fps": VIDEO_FPS,
                        "file_path": VIDEO_FILE_PATH
                    }
                },
                "output": {
                    "save_to_file": False,  # 发送端不保存
                    "file_path": "sent_video.y4m"
                },
                "connection": {
                    "autoclose": True,
                    "autoclose_time_s": DURATION + 15
                },
                "logging": {
                    "log_to_file": True,
                    "log_file_path": f"sender_detailed.log",
                    "log_level": "verbose"
                }
            }
            print(f"✅ 发送端配置: 使用视频文件 {VIDEO_FILE_PATH}")
        else:
            # 使用Fake视频生成器
            webrtc_config = {
                "video_source": {
                    "video_disabled": {"enabled": False},
                    "webcam": {"enabled": True},  # 会用FakeVideoCapturer
                    "video_file": {"enabled": False}
                },
                "output": {"save_to_file": False},
                "connection": {
                    "autoclose": True,
                    "autoclose_time_s": DURATION + 15
                },
                "logging": {
                    "log_to_file": True,
                    "log_file_path": "sender_detailed.log",
                    "log_level": "verbose"
                }
            }
            print("⚠️ 发送端配置: 使用Fake视频生成器（视频文件不存在或太小）")
    else:
        # 接收端配置 - 不发送视频，只接收并保存
        webrtc_config = {
            "video_source": {
                "video_disabled": {"enabled": True},  # 接收端禁用视频发送
                "webcam": {"enabled": False},
                "video_file": {"enabled": False}
            },
            "output": {
                "save_to_file": True,  # 接收端保存视频
                "file_path": "received_video.y4m"
            },
            "connection": {
                "autoclose": True,
                "autoclose_time_s": DURATION + 15
            },
            "logging": {
                "log_to_file": True,
                "log_file_path": "receiver_detailed.log", 
                "log_level": "verbose"
            }
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
    if not os.path.exists(VIDEO_FILE_PATH):
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
print("--- SETUP ---")
# 验证视频文件
verify_video_file()

if os.path.exists(RESULTS_DIR):
    shutil.rmtree(RESULTS_DIR)
os.makedirs(RESULTS_DIR, exist_ok=True)
os.chmod(RESULTS_DIR, 0o777)  # 确保目录可写

# 检查必要的可执行文件是否存在
for exe in [CLIENT_EXEC, SERVER_EXEC]:
    if not os.path.exists(exe):
        print(f"错误: 找不到可执行文件 {exe}")
        sys.exit(1)

print(f"Starting signaling server on port {SERVER_PORT}...")
server_proc = subprocess.Popen([SERVER_EXEC], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(2)

procs_to_kill = [server_proc]

try:
    # --- 执行 ---
    print("\n--- EXECUTION (REAL NETWORK) ---")
    print(f"视频设置: {VIDEO_WIDTH}x{VIDEO_HEIGHT} @ {VIDEO_FPS}fps")
    print(f"视频文件: {VIDEO_FILE_PATH} {'(循环播放)' if VIDEO_LOOP else '(单次播放)'}")
    print(f"音频: 禁用 (纯视频传输模式)")

    # 创建配置文件
    sender_config_path = os.path.join(RESULTS_DIR, "sender_config.json")
    receiver_config_path = os.path.join(RESULTS_DIR, "receiver_config.json")
    
    create_webrtc_config(sender_config_path, is_sender=True)
    create_webrtc_config(receiver_config_path, is_sender=False)

    # 创建一个测试文件验证工作目录权限
    test_file_path = os.path.join(RESULTS_DIR, "test_write_permission.txt")
    with open(test_file_path, 'w') as f:
        f.write("Test write permission")
    print(f"Created test file: {test_file_path}")

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
    
    print(f"Starting optimized Xvfb with command: {' '.join(xvfb_cmd)}")
    xvfb_proc = subprocess.Popen(xvfb_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    procs_to_kill.append(xvfb_proc)
    time.sleep(3)  # 给Xvfb更多启动时间
    
    # 确认Xvfb运行正常
    xvfb_poll = xvfb_proc.poll()
    if xvfb_poll is not None:
        print(f"错误: Xvfb进程已退出，返回码: {xvfb_poll}")
        stdout, stderr = xvfb_proc.communicate()
        print(f"Xvfb stdout: {stdout.decode()}")
        print(f"Xvfb stderr: {stderr.decode()}")
        sys.exit(1)
    else:
        print("Xvfb启动成功，继续测试...")

    # 设置环境变量（新版本使用JSON配置）
    sender_env = os.environ.copy()
    sender_env["DISPLAY"] = ":99"
    sender_env["WEBRTC_CONFIG_PATH"] = sender_config_path  # 指定JSON配置文件路径
    
    # 🔄 调整启动顺序：接收端先启动，发送端后启动（有助于P2P连接建立）
    
    # 先运行接收端
    receiver_env = os.environ.copy()
    receiver_env["DISPLAY"] = ":99"  # 使用同一个Xvfb实例
    receiver_env["WEBRTC_CONFIG_PATH"] = receiver_config_path  # 指定JSON配置文件路径
    
    receiver_log_path = os.path.join(RESULTS_DIR, "receiver.log")
    receiver_err_path = os.path.join(RESULTS_DIR, "receiver.err")
    
    print(f"🎯 步骤1: 启动接收端")
    print(f"Starting receiver with JSON config: {receiver_config_path}")
    receiver_cmd = [
        CLIENT_EXEC,
        f"--server={SERVER_IP}",
        f"--port={SERVER_PORT}",
        "--autoconnect",
    ]
    
    print(f"Receiver command: {' '.join(receiver_cmd)}")
    with open(receiver_log_path, "w") as log_file, open(receiver_err_path, "w") as err_file:
        receiver_proc = subprocess.Popen(
            receiver_cmd,
            env=receiver_env,
            stdout=log_file,
            stderr=err_file
        )
    procs_to_kill.append(receiver_proc)
    print(f"✅ Receiver process started with PID: {receiver_proc.pid}")
    
    # 等待接收端连接到服务器
    print("等待接收端连接到信令服务器...")
    time.sleep(3)
    
    # 再运行发送端（会自动连接到接收端）
    sender_log_path = os.path.join(RESULTS_DIR, "sender.log")
    sender_err_path = os.path.join(RESULTS_DIR, "sender.err")
    
    print(f"🎯 步骤2: 启动发送端（自动连接模式）")
    print(f"Starting sender with JSON config: {sender_config_path}")
    sender_cmd = [
        CLIENT_EXEC,
        f"--server={SERVER_IP}",
        f"--port={SERVER_PORT}",
        "--autoconnect",
        "--autocall",  # 自动呼叫第一个可用的对等端
    ]
    
    print(f"Sender command: {' '.join(sender_cmd)}")
    
    with open(sender_log_path, "w") as log_file, open(sender_err_path, "w") as err_file:
        sender_proc = subprocess.Popen(
            sender_cmd,
            env=sender_env,
            stdout=log_file,
            stderr=err_file
        )
    procs_to_kill.append(sender_proc)
    print(f"✅ Sender process started with PID: {sender_proc.pid}")
    
    # 给两个客户端额外时间建立P2P连接
    print("等待P2P连接建立...")
    time.sleep(5)

    # 检查是否使用真实视频文件
    USE_REAL_VIDEO = os.path.exists(VIDEO_FILE_PATH) and os.path.getsize(VIDEO_FILE_PATH) > 1000000
    
    if USE_REAL_VIDEO and not VIDEO_LOOP:
        print(f"\n使用真实视频文件（非循环模式），等待视频播放完成或最多 {DURATION} 秒...")
    else:
        print(f"\nTest running for {DURATION} seconds...")
    
    # 定期检查客户端进程是否还在运行
    check_interval = 5  # 更频繁地检查，以便及时发现视频结束
    max_checks = DURATION // check_interval
    
    print(f"\n开始监控测试运行...")
    for i in range(max_checks):
        time.sleep(check_interval)
        sender_poll = sender_proc.poll()
        receiver_poll = receiver_proc.poll()
        
        if sender_poll is not None:
            print(f"警告: 发送端进程已退出，返回码: {sender_poll}")
        if receiver_poll is not None:
            print(f"警告: 接收端进程已退出，返回码: {receiver_poll}")
            
        # 如果使用真实视频，检查视频是否播放完毕
        if USE_REAL_VIDEO and not VIDEO_LOOP and os.path.exists(sender_err_path):
            try:
                with open(sender_err_path, 'r') as f:
                    # 获取文件大小，只读取最后8KB内容
                    f.seek(max(0, os.path.getsize(sender_err_path) - 8192))
                    tail_content = f.read()
                    
                    # 检查是否包含视频结束标记
                    if "[VIDEO-END]" in tail_content:
                        print("\n检测到视频播放完毕标记，结束测试。")
                        break
            except Exception as e:
                print(f"读取日志文件时出错: {e}")
        
        # 📊 检测关键WebRTC事件（适配我们的纯视频传输客户端）
        success_indicators = {
            "ice_connected": False,
            "track_added": False,
            "video_received": False,
            "peer_connected": False
        }
        
        # 检查发送端日志
        if os.path.exists(sender_err_path):
            try:
                with open(sender_err_path, 'r') as f:
                    sender_content = f.read()
                    # 检查ICE连接
                    if "🎉 ICE连接已建立" in sender_content or "ICE connection state: Connected" in sender_content:
                        success_indicators["ice_connected"] = True
                    # 检查对等端连接
                    if "OnPeerConnected" in sender_content:
                        success_indicators["peer_connected"] = True
            except Exception as e:
                print(f"读取发送端日志时出错: {e}")
        
        # 检查接收端日志
        if os.path.exists(receiver_err_path):
            try:
                with open(receiver_err_path, 'r') as f:
                    receiver_content = f.read()
                    # 检查轨道添加
                    if "🎵🎵🎵 NEW_TRACK_ADDED" in receiver_content or "OnAddTrack" in receiver_content:
                        success_indicators["track_added"] = True
                    # 检查视频帧接收
                    if "📽️📽️📽️ OnFrame回调触发" in receiver_content or "OnFrame" in receiver_content:
                        success_indicators["video_received"] = True
                    # 检查ICE连接
                    if "🎉 ICE连接已建立" in receiver_content or "ICE connection state: Connected" in receiver_content:
                        success_indicators["ice_connected"] = True
            except Exception as e:
                print(f"读取接收端日志时出错: {e}")
        
        # 🎯 输出成功指标
        success_count = sum(success_indicators.values())
        print(f"\n📊 WebRTC连接状态检查 ({success_count}/4 成功):")
        print(f"  🤝 对等端连接: {'✅' if success_indicators['peer_connected'] else '❌'}")
        print(f"  🧊 ICE连接建立: {'✅' if success_indicators['ice_connected'] else '❌'}")
        print(f"  🎵 媒体轨道添加: {'✅' if success_indicators['track_added'] else '❌'}")
        print(f"  📽️ 视频帧接收: {'✅' if success_indicators['video_received'] else '❌'}")
        
        # 如果所有指标都成功，可以提前结束测试
        if success_count >= 3:  # 至少3个指标成功就认为连接正常
            print("🎉 WebRTC连接成功！大部分功能正常工作")
            if success_indicators["video_received"]:
                print("🚀 视频传输确认成功！可以提前结束测试")
                break
        
        if sender_poll is not None and receiver_poll is not None:
            print("两个客户端进程都已退出，提前结束测试。")
            break
        
        # 每30秒输出一次当前状态
        if i % 6 == 0 and i > 0:
            print(f"\n--- 检查点 {i+1} (已运行{(i+1)*check_interval}秒) ---")
    
    # 剩余时间
    remaining_time = DURATION % check_interval
    if remaining_time > 0 and (sender_proc.poll() is None or receiver_proc.poll() is None):
        time.sleep(remaining_time)

finally:
    # --- 清理 ---
    print("\n--- CLEANUP ---")
    for p in reversed(procs_to_kill):
        if p.poll() is None:  # 如果进程还在运行
            try:
                p.terminate()
                try:
                    p.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    print(f"进程 {p.pid} 没有响应 terminate 命令，强制终止...")
                    p.kill()
            except Exception as e:
                print(f"终止进程时出错: {e}")
    
    # 输出结果摘要
    print(f"\nExperiment finished. Results are in '{RESULTS_DIR}'.")
    
    # 列出测试结果目录中的所有文件
    result_files = os.listdir(RESULTS_DIR)
    print(f"\n发现 {len(result_files)} 个结果文件:")
    for file in result_files:
        file_path = os.path.join(RESULTS_DIR, file)
        print(f"- {file} ({os.path.getsize(file_path)} bytes)")
        
        # 如果是日志文件，显示最后几行和WebRTC统计信息
        if file.endswith('.err'):
            try:
                with open(file_path, 'r') as f:
                    lines = f.readlines()
                    if lines:
                        # 查找WebRTC统计信息
                        stats_lines = [line for line in lines if '[WebRTC-Stats]' in line]
                        if stats_lines:
                            print(f"  发现 {len(stats_lines)} 条WebRTC统计信息")
                            print(f"  最新统计数据: {stats_lines[-1].strip()}")
                        
                        # 显示最后几行
                        last_lines = lines[-5:] if len(lines) > 5 else lines
                        print(f"  最后{len(last_lines)}行:")
                        for line in last_lines:
                            print(f"  > {line.strip()}")
            except Exception as e:
                print(f"  读取文件失败: {e}")
        elif file.endswith('.log'):
            try:
                with open(file_path, 'r') as f:
                    lines = f.readlines()
                    if lines:
                        # 显示最后几行
                        last_lines = lines[-5:] if len(lines) > 5 else lines
                        print(f"  最后{len(last_lines)}行:")
                        for line in last_lines:
                            print(f"  > {line.strip()}")
            except Exception as e:
                print(f"  读取文件失败: {e}") 
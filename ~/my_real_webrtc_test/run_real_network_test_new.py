#!/usr/bin/env python3
import yaml
import subprocess
import time
import os
import signal
import shutil
import sys

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

# --- 准备 ---
print("--- SETUP ---")
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

    # 创建一个测试文件验证工作目录权限
    test_file_path = os.path.join(RESULTS_DIR, "test_write_permission.txt")
    with open(test_file_path, 'w') as f:
        f.write("Test write permission")
    print(f"Created test file: {test_file_path}")

    # 设置优化的Xvfb参数
    xvfb_cmd = [
        'Xvfb', 
        ':99', 
        '-screen', '0', '1280x720x24',
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

    # 运行发送端
    sender_env = os.environ.copy()
    sender_env["DISPLAY"] = ":99"
    
    # 切换到结果目录，这样统计文件就会在那里生成
    os.chdir(os.path.abspath(RESULTS_DIR))
    print(f"Changed working directory to: {os.getcwd()}")
    
    sender_log_path = os.path.join(RESULTS_DIR, "sender.log")
    sender_err_path = os.path.join(RESULTS_DIR, "sender.err")
    
    print(f"Starting sender with env DISPLAY=:99")
    sender_cmd = [
        CLIENT_EXEC,
        f"--server={SERVER_IP}",
        f"--port={SERVER_PORT}",
        "--name=sender",
        "--autoconnect",
        "--autocall"
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
    print(f"Sender process started with PID: {sender_proc.pid}")
    
    # 等待发送端连接到服务器
    time.sleep(5)
    
    # 运行接收端
    receiver_env = os.environ.copy()
    receiver_env["DISPLAY"] = ":99"  # 使用同一个Xvfb实例
    receiver_log_path = os.path.join(RESULTS_DIR, "receiver.log")
    receiver_err_path = os.path.join(RESULTS_DIR, "receiver.err")
    
    print(f"Starting receiver with env DISPLAY=:99")
    receiver_cmd = [
        CLIENT_EXEC,
        f"--server={SERVER_IP}",
        f"--port={SERVER_PORT}",
        "--name=receiver",
        "--autoconnect"
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
    print(f"Receiver process started with PID: {receiver_proc.pid}")

    print(f"\nTest running for {DURATION} seconds on real network...")
    
    # 定期检查客户端进程是否还在运行和统计文件
    for i in range(DURATION // 10):
        time.sleep(10)
        sender_poll = sender_proc.poll()
        receiver_poll = receiver_proc.poll()
        
        if sender_poll is not None:
            print(f"警告: 发送端进程已退出，返回码: {sender_poll}")
        else:
            print("发送端进程仍在运行")
            
        if receiver_poll is not None:
            print(f"警告: 接收端进程已退出，返回码: {receiver_poll}")
        else:
            print("接收端进程仍在运行")
            
        # 检查是否生成了任何文件
        all_files = os.listdir(RESULTS_DIR)
        print(f"结果目录中的文件: {all_files}")
        
        # 特别检查可能的统计文件
        stats_files = [f for f in all_files 
                     if f.endswith('.txt') or f.endswith('.csv') or
                        'stat' in f.lower() or 'webrtc' in f.lower()]
        if stats_files:
            print(f"发现可能的统计文件: {stats_files}")
        
        # 如果两个客户端都已退出，提前结束测试
        if sender_poll is not None and receiver_poll is not None:
            print("两个客户端进程都已退出，提前结束测试。")
            break
    
    # 剩余时间
    remaining_time = DURATION % 10
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
    
    # 返回原来的目录
    try:
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
    except:
        pass
    
    # 输出结果摘要
    print(f"\nExperiment finished. Results are in '{RESULTS_DIR}'.")
    
    # 列出测试结果目录中的所有文件
    if os.path.exists(RESULTS_DIR):
        result_files = os.listdir(RESULTS_DIR)
        print(f"\n发现 {len(result_files)} 个结果文件:")
        for file in result_files:
            file_path = os.path.join(RESULTS_DIR, file)
            print(f"- {file} ({os.path.getsize(file_path)} bytes)")
            
            # 如果是日志文件，显示最后几行
            if file.endswith('.log') or file.endswith('.err'):
                try:
                    with open(file_path, 'r') as f:
                        lines = f.readlines()
                        if lines:
                            last_lines = lines[-10:] if len(lines) > 10 else lines
                            print(f"  最后{len(last_lines)}行:")
                            for line in last_lines:
                                print(f"  > {line.strip()}")
                except Exception as e:
                    print(f"  读取文件失败: {e}")
    else:
        print(f"错误: 结果目录 '{RESULTS_DIR}' 不存在") 
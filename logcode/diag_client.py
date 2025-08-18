import socket
import time
import binascii
import sys
import re
import threading
import errno
import os
from hdlc import HDLC

# Connection settings
HOST = '127.0.0.1'
PORT = 43555

# Initialization messages
INIT_MESSAGES = [
    #b'\x28\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x40\x78\x7d\x01',
    #b'\x29\x00\x00\x00\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00',
    #b'\x07\x00\x00\x00\x05\x00\x00\x00\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\xb6\x78\x00\x00',
   # b'\x23\x00\x00\x00\x00\x00\x00\x00',
    b'\x1d\x1c\x3b\x7e',
    b'\x00\x78\xf0\x7e',
    b'\x7c\x93\x49\x7e',
    b'\x1c\x95\x2a\x7e',
    b'\x0c\x14\x3a\x7e',
    b'\x63\xe5\xa1\x7e',
    b'\x4b\x0f\x00\x00\xbb\x60\x7e',
    b'\x4b\x09\x00\x00\x62\xb6\x7e',
    b'\x4b\x08\x00\x00\xbe\xec\x7e',
    b'\x4b\x08\x01\x00\x66\xf5\x7e',
    b'\x4b\x04\x00\x00\x1d\x49\x7e',
    b'\x4b\x04\x0f\x00\xd5\xca\x7e',
    b'\x73\x00\x00\x00\x00\x00\x00\x00\xda\x81\x7e',
]

# Final message to send after logcode command
FINAL_MESSAGE = b'\x60\x00\x12\x6a\x7e'

# Constants
MAX_LOGCODES = 100
DEFAULT_MAX_ID = 453  # 0x1C5

# Drain buffer command
DRAIN_BUFFER_COMMAND = b'\x24\x00\x00\x00\x00\x00\x00\x00'

# Thread control flag
drain_thread_running = False
client_socket_lock = None  # Will be initialized in main()
client_socket_global = None  # Will be initialized in main()
fatal_error_occurred = False  # Flag to indicate a fatal error occurred

# Hardcoded example logcode list
DEFAULT_LOGCODES = [
   0xB064,
   0xB16C,
]

# Utility function - Display binary data in lowercase hexadecimal format
def hex_dump(data):
    """Display binary data in hexadecimal format"""
    return ' '.join(f"{b:02x}" for b in data)

# Utility function - Parse hexadecimal string to number
def parse_hex(hex_str):
    """Parse hexadecimal string to number"""
    if not hex_str:
        return 0
        
    # Skip 0x or 0X prefix
    if hex_str.lower().startswith("0x"):
        hex_str = hex_str[2:]
    
    try:
        return int(hex_str, 16)
    except ValueError:
        print(f"Warning: Unable to parse hex value '{hex_str}'")
        return 0

# Utility function - Parse user input logcodes
def parse_logcodes(input_str):
    """Parse user input logcodes, return valid logcode list"""
    logcodes = []
    
    # 检查是否为空输入
    if not input_str or input_str.strip() == "":
        print("Warning: Empty input, using default logcode list")
        return DEFAULT_LOGCODES
    
    # 处理特殊命令
    input_lower = input_str.lower().strip()
    if "全启用" in input_lower or "all" in input_lower:
        print("Enabling ALL LTE logcodes (B800-B9FF)")
        return enable_all_logcodes()
    
    # 处理范围命令
    if "-" in input_str:
        parts = input_str.split("-")
        if len(parts) == 2:
            try:
                start_id = parse_hex(parts[0]) & 0xFFF
                end_id = parse_hex(parts[1]) & 0xFFF
                if start_id <= end_id:
                    print(f"Enabling logcode range 0x{0xB000+start_id:04X}-0x{0xB000+end_id:04X}")
                    return generate_logcode_range(start_id, end_id)
            except ValueError:
                pass  # 如果解析失败，继续使用标准解析
    
    # 标准解析（空格或逗号分隔的logcodes）
    tokens = input_str.replace(",", " ").split()
    
    for token in tokens:
        if len(logcodes) >= MAX_LOGCODES:
            print(f"Warning: Maximum logcode limit reached ({MAX_LOGCODES}), ignoring remaining input")
            break
            
        # 解析十六进制值
        code = parse_hex(token)
        
        # 只添加有效的logcodes（通常以0xB开头）
        if (code & 0xF000) == 0xB000:
            logcodes.append(code)
        else:
            print(f"Warning: Ignoring invalid logcode '{token}'")
    
    # 如果没有有效的logcodes，使用默认列表
    if not logcodes:
        print("Warning: No valid logcodes, using default logcode list")
        return DEFAULT_LOGCODES
        
    return logcodes

# Core function - Generate logcode command
def generate_logcode_command(logcodes):
    """Generate HDLC encoded command based on logcode list"""
    if not logcodes:
        print("Error: Invalid logcode list")
        return None
    
    print(f"Processing {len(logcodes)} logcodes:")
    for code in logcodes:
        print(f"0x{code:04X} ", end="")
    print()
    
    # 提取所有项目ID（低12位）
    item_ids = [code & 0xFFF for code in logcodes]
    
    # 找出最大项目ID
    max_id = max(item_ids)
    
    print(f"Max item ID: 0x{max_id:04X}")
    
    # 计算掩码大小（字节）- 使用绝对偏移
    mask_size = (max_id + 8) // 8  # 确保足够大小
    
    # 创建并初始化掩码数据
    mask = bytearray(mask_size)
    
    # 设置对应位，使用绝对偏移
    for code in logcodes:
        item_id = code & 0xFFF
        byte_index = item_id // 8
        bit_index = item_id % 8
        
        # 这里不再需要范围检查，因为我们已经根据最大ID设置了足够的大小
        mask[byte_index] |= (1 << bit_index)
        print(f"Setting bit for 0x{code:04X}: byte {byte_index}, bit {bit_index}")
    
    # 创建命令头（16字节）
    # 注意：所有值都是小端序
    cmd_id = 0x73          # DIAG_LOG_CONFIG_F
    op_code = 0x03         # SET_MASK
    device_id = 0x0B       # LTE
    
    # 这里使用原始的max_id+1作为结束范围
    max_id_plus_one = max_id + 1
    
    command_header = bytearray([
        cmd_id & 0xFF, (cmd_id >> 8) & 0xFF, (cmd_id >> 16) & 0xFF, (cmd_id >> 24) & 0xFF,
        op_code & 0xFF, (op_code >> 8) & 0xFF, (op_code >> 16) & 0xFF, (op_code >> 24) & 0xFF,
        device_id & 0xFF, (device_id >> 8) & 0xFF, (device_id >> 16) & 0xFF, (device_id >> 24) & 0xFF,
        max_id_plus_one & 0xFF, (max_id_plus_one >> 8) & 0xFF, (max_id_plus_one >> 16) & 0xFF, (max_id_plus_one >> 24) & 0xFF
    ])
    
    # 命令直接由命令头和掩码组成
    full_command = command_header + mask
    
    # 输出调试信息
    print(f"Command header ({len(command_header)} bytes): {hex_dump(command_header)}")
    print(f"Mask data ({len(mask)} bytes): {hex_dump(mask)}")
    print(f"Full command ({len(full_command)} bytes): {hex_dump(full_command)}")
    
    # 计算CRC并显示
    crc = HDLC.calc_crc16(full_command)
    print(f"Calculated CRC: 0x{crc:04x} (little-endian: {crc & 0xff:02x} {(crc >> 8) & 0xff:02x})")
    
    # HDLC编码
    encoded = HDLC.encode(full_command)
    print(f"HDLC encoded length: {len(encoded)} bytes")
    print(f"HDLC encoded last 3 bytes: {encoded[-3:].hex(' ')}")
    
    return encoded

# Send single message and receive response
def send_message(sock, message):
    """Send message and receive response"""
    print(f"Sending: {hex_dump(message)} ({len(message)} bytes)")
    sock.sendall(message)
    
    # Wait for response
    time.sleep(0.1)
    
    # Receive response
    try:
        sock.settimeout(1)
        response = sock.recv(16384)
        print(f"Received: {hex_dump(response)} ({len(response)} bytes)")
        return response
    except socket.timeout:
        print("Receive timeout, no response")
        return None

# Send logcode configuration command
def send_logcode_config(sock, logcodes_str):
    """Parse logcode list, generate command and send"""
    # Parse logcodes
    logcodes = parse_logcodes(logcodes_str)
    if not logcodes:
        print("Error: No valid logcodes to send")
        return False
    
    # Generate command
    command = generate_logcode_command(logcodes)
    if not command:
        print("Error: Unable to generate logcode command")
        return False
    
    # Send command
    print("Sending HDLC encoded logcode configuration command...")
    response = send_message(sock, command)
    if not response:
        print("Warning: Logcode command received no response")
        return False
    
    # Send final command
    print("\nSending final command...")
    final_response = send_message(sock, FINAL_MESSAGE)
    if not final_response:
        print("Warning: Final command received no response")
        return False
    
    return True

# Thread function to send drain buffer command periodically
def drain_buffer_thread():
    """Thread function that sends drain buffer command 10000 times per second"""
    global drain_thread_running, client_socket_global, client_socket_lock, fatal_error_occurred
    
    print("Drain buffer thread started - sending drain command 10000 times per second")
    drain_count = 0
    start_time = time.time()
    
    while drain_thread_running:
        try:
            # 暂时注释掉drain功能
            # # Acquire lock to ensure thread-safe socket access
            # with client_socket_lock:
            #     if client_socket_global and client_socket_global.fileno() != -1:
            #         client_socket_global.sendall(DRAIN_BUFFER_COMMAND)
            #         drain_count += 1
            #         
            #         # Print stats every 10000 commands
            #         if drain_count % 10000 == 0:
            #             elapsed = time.time() - start_time
            #             rate = drain_count / elapsed if elapsed > 0 else 0
            #             print(f"Sent {drain_count} drain commands ({rate:.2f} commands/sec)")
            
            # 仍然保持线程运行，但暂时不发送drain命令
            time.sleep(0.1)
            
        except socket.error as e:
            if e.errno == errno.EPIPE or str(e).find("Broken pipe") >= 0:
                print(f"Error in drain thread: [Errno 32] Broken pipe")
                # Set fatal error flag to signal main thread to exit
                fatal_error_occurred = True
                # Break out of loop
                break
            else:
                print(f"Error in drain thread: {e}")
                # If error occurs, sleep a bit longer to avoid flooding errors
                time.sleep(0.1)
        except Exception as e:
            print(f"Error in drain thread: {e}")
            # If error occurs, sleep a bit longer to avoid flooding errors
            time.sleep(0.1)
    
    print("Drain buffer thread stopped")


def generate_logcode_range(start_id, end_id):
    """生成指定范围内的所有logcodes"""
    logcodes = []
    for item_id in range(start_id, end_id + 1):
        logcode = 0xB000 + item_id
        logcodes.append(logcode)
    return logcodes


def enable_all_logcodes(start_id=0x800, end_id=0x9FF):
    """生成广泛范围内的所有logcodes（B800-B9FF通常覆盖了大多数有用的LTE logcodes）"""
    return generate_logcode_range(start_id, end_id)


def main():
    global drain_thread_running, client_socket_global, client_socket_lock, fatal_error_occurred
    
    # Initialize lock for thread-safe socket access
    client_socket_lock = threading.Lock()
    
    # Create TCP socket
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket_global = client_socket
    
    # Thread object
    drain_thread = None
    
    try:
        # Connect to server
        print(f"Connecting to {HOST}:{PORT}...")
        client_socket.connect((HOST, PORT))
        print("Connection successful!")
        
        # Receive initial welcome message
        welcome = client_socket.recv(1024)
        print(f"Server welcome message: {welcome.decode('utf-8', errors='ignore').strip()}")
        
        # Send initialization messages
        print("\nStarting initialization messages...")
        for i, message in enumerate(INIT_MESSAGES, 1):
            print(f"\nInitialization message {i}/{len(INIT_MESSAGES)}:")
            response = send_message(client_socket, message)
            if not response:
                print(f"Warning: Message {i} received no response")
            # Pause slightly between messages
            time.sleep(0.2)
        
        print("\nInitialization sequence complete!")
        
        # Automatically send default logcode list
        print("\nSending default logcode list...")
        for code in DEFAULT_LOGCODES:
            print(f"0x{code:04X} ", end="")
        print()
        
        # Generate and send command
        command = generate_logcode_command(DEFAULT_LOGCODES)
        if command:
            print("Sending HDLC encoded default logcode configuration command...")
            response = send_message(client_socket, command)
            if not response:
                print("Warning: Auto logcode configuration received no response")
            
            # Send final command
            print("\nSending final command...")
            final_response = send_message(client_socket, FINAL_MESSAGE)
            if not final_response:
                print("Warning: Final command received no response")
        
        print("\nDrain buffer thread is temporarily disabled")
        
        print("\nStarting continuous monitoring mode...")
        print("Press Ctrl+C to exit")
        
        try:
            # 持续监听数据
            while True:
                try:
                    # 设置较短的超时以便能响应Ctrl+C
                    client_socket.settimeout(0.5)
                    data = client_socket.recv(16384)
                    if data:
                        print(f"Received data ({len(data)} bytes): {hex_dump(data)}")
                        
                        # 可以在这里添加数据解析逻辑
                        # 例如: parse_diagnostic_data(data)
                        
                except socket.timeout:
                    # 超时是正常的，继续循环
                    continue
                except socket.error as e:
                    print(f"Socket error: {e}")
                    break
                    
        except KeyboardInterrupt:
            print("\nMonitoring stopped by user")
    
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        # 关闭连接
        with client_socket_lock:
            client_socket.close()
            client_socket_global = None
        print("Connection closed")

if __name__ == "__main__":
    main()

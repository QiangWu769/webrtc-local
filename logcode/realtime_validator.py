# -*- coding: utf-8 -*-
"""
Realtime Validator for DIAG Messages
验证 DIAG 消息的实时性

原理:
1. 发送 0x1D 命令获取基准时钟偏差 (baseline_offset)
2. 对每条事件日志，计算当前偏差 (current_offset)
3. 比较: delivery_delay = |current_offset - baseline_offset|
4. 如果 delivery_delay < threshold，则消息是实时投递的
"""

import socket
import time
import struct
import sys
import os
from datetime import datetime, timedelta, timezone
from collections import deque

# 添加当前目录到路径以导入 hdlc
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hdlc import HDLC

# ==================== 配置 ====================
HOST = '127.0.0.1'
PORT = 43555
REALTIME_THRESHOLD_MS = 10.0  # 实时性判断阈值 (ms)
DRIFT_WARNING_MS = 50.0       # 时钟漂移警告阈值 (ms)

# DIAG 时间戳常量
PER_SECOND = 52428800.0  # 52.4MHz
DIAG_EPOCH = datetime(1980, 1, 6, 0, 0, 0, tzinfo=timezone.utc)

# 初始化消息
INIT_MESSAGES = [
    b'\x1d\x1c\x3b\x7e',  # 0x1D - 时间戳请求 (用于建立基准)
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
FINAL_MESSAGE = b'\x60\x00\x12\x6a\x7e'
DEFAULT_LOGCODES = [0xB16C, 0xB064, 0xB139]


class RealtimeValidator:
    """实时性验证器"""

    def __init__(self, threshold_ms=REALTIME_THRESHOLD_MS):
        self.threshold_ms = threshold_ms
        self.baseline_offset = None  # 基准偏差 (秒)
        self.baseline_time = None    # 建立基准的时间

        # 统计数据
        self.stats = {
            'total_messages': 0,
            'realtime_messages': 0,
            'delayed_messages': 0,
            'max_delay_ms': 0,
            'min_delay_ms': float('inf'),
            'delays': deque(maxlen=1000),  # 最近1000条消息的延迟
        }

        # 时钟漂移跟踪
        self.offset_history = deque(maxlen=100)

    def set_baseline(self, modem_time, phone_time):
        """设置基准偏差"""
        self.baseline_offset = modem_time - phone_time
        self.baseline_time = phone_time
        print("\n" + "="*60)
        print("BASELINE ESTABLISHED")
        print("="*60)
        print("  Modem time:     {:.6f}".format(modem_time))
        print("  Phone time:     {:.6f}".format(phone_time))
        print("  Baseline offset: {:.3f} ms".format(self.baseline_offset * 1000))
        print("  (Modem clock is {:.1f}ms {} than Phone clock)".format(
            abs(self.baseline_offset * 1000),
            "ahead" if self.baseline_offset > 0 else "behind"
        ))
        print("="*60 + "\n")

    def validate(self, modem_time, phone_time, logcode=None, extra_info=""):
        """
        验证消息是否实时投递

        Args:
            modem_time: Modem 时间戳 (Unix timestamp)
            phone_time: Phone 接收时间 (Unix timestamp)
            logcode: 日志代码 (可选)
            extra_info: 额外信息 (可选)

        Returns:
            dict: 验证结果
        """
        if self.baseline_offset is None:
            return {'status': 'NO_BASELINE', 'is_realtime': None}

        # 计算当前偏差
        current_offset = modem_time - phone_time

        # 计算投递延迟
        delivery_delay = current_offset - self.baseline_offset
        delivery_delay_ms = delivery_delay * 1000

        # 判断是否实时
        is_realtime = abs(delivery_delay_ms) < self.threshold_ms

        # 更新统计
        self.stats['total_messages'] += 1
        self.stats['delays'].append(delivery_delay_ms)

        if is_realtime:
            self.stats['realtime_messages'] += 1
        else:
            self.stats['delayed_messages'] += 1

        if abs(delivery_delay_ms) > self.stats['max_delay_ms']:
            self.stats['max_delay_ms'] = abs(delivery_delay_ms)
        if abs(delivery_delay_ms) < self.stats['min_delay_ms']:
            self.stats['min_delay_ms'] = abs(delivery_delay_ms)

        # 跟踪偏差变化（检测时钟漂移）
        self.offset_history.append(current_offset)

        # 构建结果
        result = {
            'is_realtime': is_realtime,
            'status': 'REALTIME' if is_realtime else 'DELAYED',
            'baseline_offset_ms': self.baseline_offset * 1000,
            'current_offset_ms': current_offset * 1000,
            'delivery_delay_ms': delivery_delay_ms,
            'modem_time': modem_time,
            'phone_time': phone_time,
        }

        # 打印结果
        status_symbol = "✓" if is_realtime else "✗"
        logcode_str = "0x{:04X}".format(logcode) if logcode else "----"

        # 颜色输出 (ANSI)
        if is_realtime:
            color = "\033[92m"  # 绿色
        elif abs(delivery_delay_ms) > DRIFT_WARNING_MS:
            color = "\033[91m"  # 红色
        else:
            color = "\033[93m"  # 黄色
        reset = "\033[0m"

        print("{color}[{status}] {logcode} | offset={offset:+8.2f}ms | delay={delay:+8.2f}ms | {extra}{reset}".format(
            color=color,
            status=status_symbol,
            logcode=logcode_str,
            offset=current_offset * 1000,
            delay=delivery_delay_ms,
            extra=extra_info,
            reset=reset
        ))

        return result

    def check_clock_drift(self):
        """检查时钟漂移"""
        if len(self.offset_history) < 10:
            return None

        recent = list(self.offset_history)[-10:]
        drift = (recent[-1] - recent[0]) * 1000  # ms

        if abs(drift) > DRIFT_WARNING_MS:
            print("\n\033[91m[WARNING] Clock drift detected: {:.2f}ms over last {} samples\033[0m\n".format(
                drift, len(recent)))

        return drift

    def print_stats(self):
        """打印统计信息"""
        if self.stats['total_messages'] == 0:
            print("\nNo messages received yet.")
            return

        rt_rate = self.stats['realtime_messages'] / self.stats['total_messages'] * 100

        # 计算平均延迟
        if self.stats['delays']:
            avg_delay = sum(self.stats['delays']) / len(self.stats['delays'])
        else:
            avg_delay = 0

        print("\n" + "="*60)
        print("REALTIME VALIDATION STATISTICS")
        print("="*60)
        print("  Total messages:    {}".format(self.stats['total_messages']))
        print("  Realtime messages: {} ({:.1f}%)".format(
            self.stats['realtime_messages'], rt_rate))
        print("  Delayed messages:  {} ({:.1f}%)".format(
            self.stats['delayed_messages'], 100 - rt_rate))
        print("  ─────────────────────────────")
        print("  Threshold:         {:.1f} ms".format(self.threshold_ms))
        print("  Baseline offset:   {:.2f} ms".format(
            self.baseline_offset * 1000 if self.baseline_offset else 0))
        print("  ─────────────────────────────")
        print("  Min delay:         {:.2f} ms".format(
            self.stats['min_delay_ms'] if self.stats['min_delay_ms'] != float('inf') else 0))
        print("  Max delay:         {:.2f} ms".format(self.stats['max_delay_ms']))
        print("  Avg delay:         {:.2f} ms".format(avg_delay))
        print("="*60 + "\n")


def convert_diag_timestamp_to_unix(timestamp):
    """将 DIAG 时间戳转换为 Unix 时间戳"""
    if timestamp == 0:
        return 0.0
    try:
        seconds_since_epoch = timestamp / PER_SECOND
        utc_time = DIAG_EPOCH + timedelta(seconds=seconds_since_epoch)
        return utc_time.timestamp()
    except (OverflowError, ValueError):
        return 0.0


def generate_logcode_command(logcodes):
    """生成 logcode 配置命令"""
    item_ids = [code & 0xFFF for code in logcodes]
    if not item_ids:
        return None
    max_id = max(item_ids)
    mask_size = (max_id + 8) // 8
    mask = bytearray(mask_size)
    for code in logcodes:
        item_id = code & 0xFFF
        byte_index = item_id // 8
        bit_index = item_id % 8
        mask[byte_index] |= (1 << bit_index)

    cmd_header = struct.pack('<IIII', 0x73, 3, 0x0B, max_id + 1)
    full_command = cmd_header + mask
    return HDLC.encode(full_command)


def parse_0x1d_response(response_data):
    """
    解析 0x1D 时间戳响应

    Returns:
        tuple: (modem_timestamp, success)
    """
    # 寻找 HDLC 帧
    frames = response_data.split(b'\x7e')

    for frame in frames:
        if not frame or len(frame) < 10:
            continue

        # 尝试 HDLC 解码
        decoded = HDLC.decode(frame + b'\x7e')
        if decoded is None:
            continue

        # 检查是否是 0x1D 响应
        # 格式: [0x1D] [8字节时间戳]
        if len(decoded) >= 9 and decoded[0] == 0x1D:
            timestamp_bytes = decoded[1:9]
            timestamp = struct.unpack('<Q', timestamp_bytes)[0]
            return timestamp, True

        # 检查带 DIAG header 的格式
        # 格式: [98 01 00 00 01 00 00 00] [4字节长度] [0x1D] [8字节时间戳]
        if decoded.startswith(b'\x98\x01\x00\x00\x01\x00\x00\x00'):
            data = decoded[12:]  # 跳过 header
            if len(data) >= 9 and data[0] == 0x1D:
                timestamp_bytes = data[1:9]
                timestamp = struct.unpack('<Q', timestamp_bytes)[0]
                return timestamp, True

    return 0, False


def parse_diag_log(data, validator, bridge_ts):
    """
    解析 DIAG 日志消息并验证实时性

    Args:
        data: 原始数据 (已去除 bridge timestamp header)
        validator: RealtimeValidator 实例
        bridge_ts: Bridge 读取数据的时间戳 (这是真正的 Phone 时间)
    """
    # 使用 bridge_ts 而不是 time.time()
    # 因为 bridge_ts 是消息真正到达 Phone 的时间
    # time.time() 会包含额外的 TCP 传输延迟
    phone_time = bridge_ts

    # 分割 HDLC 帧
    frames = data.split(b'\x7e')

    for frame in frames:
        if not frame or len(frame) < 10:
            continue

        # HDLC 解码
        decoded = HDLC.decode(frame + b'\x7e')
        if decoded is None:
            continue

        # 检查 DIAG 日志格式
        # [98 01 00 00 01 00 00 00] [4字节信息] [2字节长度] [2字节logcode] [8字节时间戳] [payload]
        if not decoded.startswith(b'\x98\x01\x00\x00\x01\x00\x00\x00'):
            continue

        if len(decoded) < 24:
            continue

        # 解析头部
        payload = decoded[12:]  # 跳过 DIAG header
        if len(payload) < 12:
            continue

        msg_len, logcode, timestamp = struct.unpack('<HHQ', payload[:12])

        # 转换时间戳
        modem_time = convert_diag_timestamp_to_unix(timestamp)
        if modem_time == 0:
            continue

        # 验证实时性
        extra_info = "len={}".format(msg_len)
        validator.validate(modem_time, phone_time, logcode, extra_info)


def main():
    print("\n" + "="*60)
    print("DIAG Message Realtime Validator")
    print("="*60)
    print("Threshold: {} ms".format(REALTIME_THRESHOLD_MS))
    print("Target: {}:{}".format(HOST, PORT))
    print("="*60 + "\n")

    validator = RealtimeValidator(threshold_ms=REALTIME_THRESHOLD_MS)

    # 创建 socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    try:
        print("Connecting to bridge...")
        sock.connect((HOST, PORT))
        print("Connected!\n")

        # 接收欢迎消息
        welcome = sock.recv(1024)
        print("Bridge mode: {}".format(welcome.decode('utf-8', errors='ignore').strip()))

        # ========== 阶段1: 发送初始化消息并建立基准 ==========
        print("\n--- Phase 1: Initialization & Baseline Establishment ---\n")

        for i, msg in enumerate(INIT_MESSAGES):
            # 记录发送时间
            send_time = time.time()
            sock.sendall(msg)
            time.sleep(0.1)

            try:
                sock.settimeout(1.0)
                response = sock.recv(16384)
                recv_time = time.time()

                # 第一条消息是 0x1D，用于建立基准
                if i == 0:
                    # 检查响应是否包含 bridge timestamp (8字节 double)
                    if len(response) > 8:
                        try:
                            bridge_ts = struct.unpack('<d', response[:8])[0]
                            # 验证是否是有效的 Unix 时间戳
                            if 1700000000 < bridge_ts < 1900000000:
                                phone_time = bridge_ts
                                print("[DEBUG] Using bridge timestamp: {:.6f}".format(bridge_ts))
                                response = response[8:]  # 去掉 bridge timestamp header
                            else:
                                phone_time = recv_time
                                print("[DEBUG] Using Python recv time (no valid bridge_ts)")
                        except:
                            phone_time = recv_time
                    else:
                        phone_time = recv_time

                    diag_ts, success = parse_0x1d_response(response)
                    if success:
                        modem_time = convert_diag_timestamp_to_unix(diag_ts)
                        validator.set_baseline(modem_time, phone_time)
                        print("[DEBUG] RTT: {:.2f}ms".format((recv_time - send_time) * 1000))
                    else:
                        print("[WARNING] Failed to parse 0x1D response, trying raw data...")
                        # 尝试从原始数据中查找
                        if len(response) >= 24:
                            # 查找 0x1D 字节后跟合理的时间戳
                            for j in range(len(response) - 9):
                                if response[j] == 0x1D:
                                    try:
                                        ts_bytes = response[j+1:j+9]
                                        diag_ts = struct.unpack('<Q', ts_bytes)[0]
                                        modem_time = convert_diag_timestamp_to_unix(diag_ts)
                                        if 1700000000 < modem_time < 1900000000:  # 合理范围检查
                                            validator.set_baseline(modem_time, phone_time)
                                            print("[DEBUG] Found 0x1D at offset {}".format(j))
                                            break
                                    except:
                                        continue

            except socket.timeout:
                pass

            print("Init message {}/{} sent".format(i+1, len(INIT_MESSAGES)))

        # 发送 logcode 配置
        print("\nConfiguring logcodes: {}".format(
            ", ".join("0x{:04X}".format(c) for c in DEFAULT_LOGCODES)))
        cmd = generate_logcode_command(DEFAULT_LOGCODES)
        if cmd:
            sock.sendall(cmd)
            time.sleep(0.1)

        # 发送最终消息
        sock.sendall(FINAL_MESSAGE)
        time.sleep(0.1)
        print("Configuration complete!\n")

        # ========== 阶段2: 持续接收并验证消息 ==========
        print("--- Phase 2: Realtime Validation (Press Ctrl+C to stop) ---\n")

        if validator.baseline_offset is None:
            print("\033[91m[ERROR] Baseline not established! Cannot validate realtime.\033[0m")
            print("Please check 0x1D response parsing.\n")

        message_count = 0
        last_stats_time = time.time()

        while True:
            try:
                sock.settimeout(1.0)
                data = sock.recv(65536)

                if not data:
                    print("Connection closed by server.")
                    break

                # 数据格式: [8字节 bridge timestamp] [原始 DIAG 数据]
                if len(data) > 8:
                    # 提取 bridge timestamp
                    bridge_ts = struct.unpack('<d', data[:8])[0]
                    diag_data = data[8:]

                    # 解析并验证 (使用 bridge_ts 作为 Phone 时间)
                    if len(diag_data) > 12:
                        parse_diag_log(diag_data, validator, bridge_ts)
                        message_count += 1

                # 每10秒打印一次统计
                if time.time() - last_stats_time > 10:
                    validator.check_clock_drift()
                    last_stats_time = time.time()

            except socket.timeout:
                continue

    except KeyboardInterrupt:
        print("\n\nStopped by user.")
    except Exception as e:
        print("\nError: {}".format(e))
        import traceback
        traceback.print_exc()
    finally:
        sock.close()
        validator.print_stats()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Time Client - 测量 adb forward 延迟

配合 time_server.c 使用，测量从手机到电脑的 TCP 传输延迟。

使用方法:
1. 手机上运行 time_server:
   adb shell
   su
   cd /data/local/tmp
   ./time_server

2. 设置 adb forward:
   adb forward tcp:43555 tcp:43555

3. 电脑上运行此脚本:
   python3 time_client.py

注意: 手机和电脑的时钟需要先同步，否则测量的是 时钟偏差 + 传输延迟
"""

import socket
import struct
import time
import sys
from collections import deque

HOST = '127.0.0.1'
PORT = 43555

def main():
    print("=" * 60)
    print("ADB Forward Latency Tester")
    print("=" * 60)
    print("Target: {}:{}".format(HOST, PORT))
    print("=" * 60)
    print()

    # 连接服务器
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    try:
        print("Connecting to time_server...")
        sock.connect((HOST, PORT))
        print("Connected!\n")
    except Exception as e:
        print("Connection failed: {}".format(e))
        print("\nMake sure:")
        print("  1. time_server is running on phone")
        print("  2. adb forward tcp:43555 tcp:43555")
        return

    # 统计数据
    delays = deque(maxlen=1000)
    count = 0

    # 用于校准的初始样本
    calibration_samples = []
    calibration_done = False
    clock_offset = 0.0

    print("Receiving timestamps from phone...\n")
    print("First 10 samples will be used for clock calibration.\n")

    try:
        while True:
            # 接收 8 字节的 double 时间戳
            data = sock.recv(8)
            if len(data) != 8:
                print("Connection closed")
                break

            pc_recv_time = time.time()
            phone_send_time = struct.unpack('<d', data)[0]

            # 原始差值 = 时钟偏差 + 传输延迟
            raw_diff_ms = (pc_recv_time - phone_send_time) * 1000

            # 校准阶段：收集样本计算时钟偏差
            if not calibration_done:
                calibration_samples.append(raw_diff_ms)
                print("[Calibrating {}/10] Raw diff: {:.2f} ms".format(
                    len(calibration_samples), raw_diff_ms))

                if len(calibration_samples) >= 10:
                    # 用最小值作为偏差估计（假设最小延迟时传输延迟最小）
                    clock_offset = min(calibration_samples)
                    calibration_done = True
                    print("\n" + "=" * 60)
                    print("CALIBRATION COMPLETE")
                    print("=" * 60)
                    print("  Estimated clock offset: {:.2f} ms".format(clock_offset))
                    print("  (Phone clock is {:.1f}ms {} than PC clock)".format(
                        abs(clock_offset),
                        "behind" if clock_offset > 0 else "ahead"
                    ))
                    print("=" * 60)
                    print("\nMeasuring transmission delay...\n")
                continue

            # 计算传输延迟（去除时钟偏差）
            delay_ms = raw_diff_ms - clock_offset
            delays.append(delay_ms)
            count += 1

            # 统计
            avg_delay = sum(delays) / len(delays)
            min_delay = min(delays)
            max_delay = max(delays)

            # 判断延迟状态
            if delay_ms < 5:
                status = "\033[92m✓\033[0m"  # 绿色
            elif delay_ms < 20:
                status = "\033[93m○\033[0m"  # 黄色
            else:
                status = "\033[91m✗\033[0m"  # 红色

            print("[{}] #{:4d} | delay: {:6.2f} ms | avg: {:6.2f} ms | min: {:6.2f} ms | max: {:6.2f} ms".format(
                status, count, delay_ms, avg_delay, min_delay, max_delay))

    except KeyboardInterrupt:
        print("\n\nStopped by user.")
    except Exception as e:
        print("\nError: {}".format(e))
    finally:
        sock.close()

    # 最终统计
    if delays:
        print("\n" + "=" * 60)
        print("FINAL STATISTICS")
        print("=" * 60)
        print("  Total samples:  {}".format(len(delays)))
        print("  Clock offset:   {:.2f} ms".format(clock_offset))
        print("  -" * 30)
        print("  Min delay:      {:.2f} ms".format(min(delays)))
        print("  Max delay:      {:.2f} ms".format(max(delays)))
        print("  Avg delay:      {:.2f} ms".format(sum(delays) / len(delays)))

        # 计算百分位数
        sorted_delays = sorted(delays)
        p50 = sorted_delays[len(sorted_delays) // 2]
        p90 = sorted_delays[int(len(sorted_delays) * 0.9)]
        p99 = sorted_delays[int(len(sorted_delays) * 0.99)]
        print("  P50 delay:      {:.2f} ms".format(p50))
        print("  P90 delay:      {:.2f} ms".format(p90))
        print("  P99 delay:      {:.2f} ms".format(p99))
        print("=" * 60)


if __name__ == "__main__":
    main()

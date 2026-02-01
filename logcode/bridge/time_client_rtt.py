#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RTT Client - 配合 time_server_rtt.c 使用

NTP 风格的精确 RTT 测量，可以：
1. 计算网络往返时间（排除服务器处理时间）
2. 估算时钟偏差

使用方法:
1. 手机上运行: ./time_server_rtt
2. adb forward tcp:43556 tcp:43556
3. python3 time_client_rtt.py
"""

import socket
import struct
import time

HOST = '127.0.0.1'
PORT = 43556

# 消息类型
MSG_TYPE_PING = 0x01
MSG_TYPE_PONG = 0x02

# 消息格式: type(1) + t1(8) + t2(8) + t3(8) = 25 bytes
MSG_FORMAT = '<B d d d'
MSG_SIZE = struct.calcsize(MSG_FORMAT)


def main():
    print("=" * 70)
    print("NTP-style RTT Tester (with time_server_rtt)")
    print("=" * 70)
    print("Message size: {} bytes".format(MSG_SIZE))
    print()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    try:
        print("Connecting to {}:{}...".format(HOST, PORT))
        sock.connect((HOST, PORT))
        print("Connected!\n")
    except Exception as e:
        print("Failed: {}".format(e))
        return

    rtts = []
    offsets = []

    print("Format: RTT = 网络往返时间, Offset = 时钟偏差估计\n")
    print("-" * 70)

    try:
        for i in range(100):
            # T1: 客户端发送时间
            t1 = time.time()

            # 发送 PING
            ping = struct.pack(MSG_FORMAT, MSG_TYPE_PING, t1, 0.0, 0.0)
            sock.sendall(ping)

            # 接收 PONG
            pong = sock.recv(MSG_SIZE)
            if len(pong) != MSG_SIZE:
                print("Incomplete response: {} bytes".format(len(pong)))
                continue

            # T4: 客户端接收时间
            t4 = time.time()

            # 解析响应
            msg_type, t1_echo, t2, t3 = struct.unpack(MSG_FORMAT, pong)

            if msg_type != MSG_TYPE_PONG:
                print("Invalid response type: 0x{:02x}".format(msg_type))
                continue

            # 计算 RTT (去除服务器处理时间)
            server_processing = (t3 - t2) * 1000  # ms
            rtt = ((t4 - t1) - (t3 - t2)) * 1000  # ms
            rtts.append(rtt)

            # 计算时钟偏差 (NTP 公式)
            # offset > 0 表示服务器(手机)时钟比客户端(电脑)快
            offset = ((t2 - t1) + (t3 - t4)) / 2 * 1000  # ms
            offsets.append(offset)

            # 状态指示
            if rtt < 5:
                status = "\033[92m✓\033[0m"
            elif rtt < 20:
                status = "\033[93m○\033[0m"
            else:
                status = "\033[91m✗\033[0m"

            avg_rtt = sum(rtts) / len(rtts)
            avg_offset = sum(offsets) / len(offsets)

            print("[{}] #{:3d} | RTT: {:6.2f} ms | one-way: ~{:5.2f} ms | "
                  "server proc: {:5.3f} ms | clock offset: {:+8.2f} ms".format(
                      status, i + 1, rtt, rtt / 2, server_processing, offset))

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n\nStopped.")
    finally:
        sock.close()

    if rtts:
        print("\n" + "=" * 70)
        print("RESULTS")
        print("=" * 70)

        # RTT 统计
        print("\n[RTT Statistics]")
        print("  Samples:    {}".format(len(rtts)))
        print("  Min RTT:    {:6.2f} ms  (one-way: ~{:.2f} ms)".format(
            min(rtts), min(rtts) / 2))
        print("  Max RTT:    {:6.2f} ms  (one-way: ~{:.2f} ms)".format(
            max(rtts), max(rtts) / 2))
        print("  Avg RTT:    {:6.2f} ms  (one-way: ~{:.2f} ms)".format(
            sum(rtts) / len(rtts), sum(rtts) / len(rtts) / 2))

        sorted_rtts = sorted(rtts)
        p50 = sorted_rtts[len(sorted_rtts) // 2]
        p99 = sorted_rtts[int(len(sorted_rtts) * 0.99)]
        print("  P50 RTT:    {:6.2f} ms".format(p50))
        print("  P99 RTT:    {:6.2f} ms".format(p99))

        # 时钟偏差统计
        print("\n[Clock Offset Statistics]")
        avg_offset = sum(offsets) / len(offsets)
        print("  Avg offset: {:+.2f} ms".format(avg_offset))
        print("  (Phone clock is {:.1f}ms {} than PC clock)".format(
            abs(avg_offset),
            "ahead" if avg_offset > 0 else "behind"
        ))

        print("\n" + "=" * 70)


if __name__ == "__main__":
    main()

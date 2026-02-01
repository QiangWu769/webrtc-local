#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RTT Test - 测量 adb forward 往返延迟

简单发送数据，等待 echo 返回，测量 RTT。
不需要时钟同步！

使用方法:
1. 手机上运行 echo_server (或修改 time_server 为 echo 模式)
2. adb forward tcp:43556 tcp:43556
3. python3 rtt_test.py
"""

import socket
import struct
import time
import sys

HOST = '127.0.0.1'
PORT = 43556  # 使用不同端口避免冲突

def main():
    print("=" * 60)
    print("ADB Forward RTT Tester")
    print("=" * 60)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    try:
        print("Connecting to {}:{}...".format(HOST, PORT))
        sock.connect((HOST, PORT))
        print("Connected!\n")
    except Exception as e:
        print("Failed: {}".format(e))
        print("\nMake sure echo_server is running and adb forward is set")
        return

    rtts = []
    print("Measuring RTT (Press Ctrl+C to stop)...\n")

    try:
        for i in range(100):
            # 发送 8 字节数据
            send_data = struct.pack('<Q', i)

            t1 = time.time()
            sock.sendall(send_data)

            # 等待 echo 返回
            recv_data = sock.recv(8)
            t2 = time.time()

            if len(recv_data) != 8:
                print("Incomplete response")
                continue

            rtt_ms = (t2 - t1) * 1000
            rtts.append(rtt_ms)

            # 状态
            if rtt_ms < 5:
                status = "\033[92m✓\033[0m"
            elif rtt_ms < 20:
                status = "\033[93m○\033[0m"
            else:
                status = "\033[91m✗\033[0m"

            avg = sum(rtts) / len(rtts)
            print("[{}] #{:3d} | RTT: {:6.2f} ms | avg: {:6.2f} ms | one-way: ~{:.2f} ms".format(
                status, i+1, rtt_ms, avg, rtt_ms/2))

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n\nStopped.")
    finally:
        sock.close()

    if rtts:
        print("\n" + "=" * 60)
        print("RESULTS")
        print("=" * 60)
        print("  Samples:    {}".format(len(rtts)))
        print("  Min RTT:    {:.2f} ms  (one-way: ~{:.2f} ms)".format(min(rtts), min(rtts)/2))
        print("  Max RTT:    {:.2f} ms  (one-way: ~{:.2f} ms)".format(max(rtts), max(rtts)/2))
        print("  Avg RTT:    {:.2f} ms  (one-way: ~{:.2f} ms)".format(sum(rtts)/len(rtts), sum(rtts)/len(rtts)/2))
        sorted_rtts = sorted(rtts)
        p50 = sorted_rtts[len(sorted_rtts)//2]
        p99 = sorted_rtts[int(len(sorted_rtts)*0.99)]
        print("  P50 RTT:    {:.2f} ms".format(p50))
        print("  P99 RTT:    {:.2f} ms".format(p99))
        print("=" * 60)

if __name__ == "__main__":
    main()

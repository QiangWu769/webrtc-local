#!/usr/bin/env python3

import socket
import time
import struct
import statistics

# 注意：使用 time.clock_gettime(time.CLOCK_REALTIME) 而不是 time.time()
# 确保与C代码使用相同的时钟源，消除由于不同时钟源导致的测量误差

HOST = '127.0.0.1'
PORT = 43555
MEASUREMENT_COUNT = 100

def main():
    """时间同步验证客户端 - 连接到time_server并测量时间偏移"""
    
    print(f"[+] Connecting to time server at {HOST}:{PORT}")
    
    try:
        # 创建TCP客户端
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((HOST, PORT))
        print(f"[+] Connected successfully!")
        
        # 初始化偏移量列表
        offsets = []
        
        print(f"[+] Starting {MEASUREMENT_COUNT} measurements...")
        print("=" * 70)
        
        # 进行有限次数的测量循环
        for i in range(MEASUREMENT_COUNT):
            try:
                # 接收8字节的时间戳
                data = client_socket.recv(8)
                if len(data) != 8:
                    print(f"[-] Received incomplete data: {len(data)} bytes")
                    break
                
                # 立即记录PC当前时间，明确使用CLOCK_REALTIME
                pc_time = time.clock_gettime(time.CLOCK_REALTIME)
                
                # 解析设备时间戳
                device_time = struct.unpack('<d', data)[0]
                
                # 计算偏移量（毫秒）
                offset = (pc_time - device_time) * 1000
                offsets.append(offset)
                
                # 打印单次测量结果
                print(f"[{i+1:3d}/100] Device: {device_time:.6f}, PC: {pc_time:.6f}, Offset: {offset:+8.3f} ms")
                
            except socket.error as e:
                print(f"[-] Socket error during measurement {i+1}: {e}")
                break
            except struct.error as e:
                print(f"[-] Data parsing error during measurement {i+1}: {e}")
                break
        
        print("=" * 70)
        
        # 分析和报告结果
        if len(offsets) > 0:
            mean_offset = statistics.mean(offsets)
            min_offset = min(offsets)
            max_offset = max(offsets)
            
            if len(offsets) > 1:
                std_dev = statistics.stdev(offsets)
            else:
                std_dev = 0.0
            
            print(f"[+] Measurement Summary ({len(offsets)} samples):")
            print(f"    Mean Offset:     {mean_offset:+8.3f} ms")
            print(f"    Min Offset:      {min_offset:+8.3f} ms")
            print(f"    Max Offset:      {max_offset:+8.3f} ms")
            print(f"    Std Deviation:   {std_dev:8.3f} ms")
            print(f"    Range:           {max_offset - min_offset:8.3f} ms")
            
            # 质量评估
            if abs(mean_offset) < 5.0:
                quality = "EXCELLENT"
            elif abs(mean_offset) < 20.0:
                quality = "GOOD"
            elif abs(mean_offset) < 50.0:
                quality = "FAIR"
            else:
                quality = "POOR"
            
            print(f"    Sync Quality:    {quality}")
            
        else:
            print("[-] No valid measurements collected!")
            
    except ConnectionRefusedError:
        print(f"[-] Connection refused. Make sure time_server is running on {HOST}:{PORT}")
    except socket.gaierror as e:
        print(f"[-] Network error: {e}")
    except Exception as e:
        print(f"[-] Unexpected error: {e}")
    finally:
        try:
            client_socket.close()
        except:
            pass
        print("[+] Connection closed.")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3

import socket
import time
import struct
import statistics
import sys

# 注意：使用 time.clock_gettime(time.CLOCK_REALTIME) 而不是 time.time()
# 确保与C代码使用相同的时钟源

HOST = '127.0.0.1'
PORT = 43556  # Match the RTT server port
MEASUREMENT_COUNT = 100
MEASUREMENT_INTERVAL = 0.1  # 100ms between measurements

# Message types
MSG_TYPE_PING = 0x01
MSG_TYPE_PONG = 0x02

# Message format: 1 byte type + 3 doubles (8 bytes each) = 25 bytes
MESSAGE_FORMAT = '<Bddd'  # Little-endian: byte, double, double, double
MESSAGE_SIZE = struct.calcsize(MESSAGE_FORMAT)

def get_current_time():
    """Get current time using CLOCK_REALTIME for consistency with C code"""
    return time.clock_gettime(time.CLOCK_REALTIME)

def main():
    """RTT measurement client - measures both time offset and round-trip time"""
    
    print(f"[+] Connecting to RTT time server at {HOST}:{PORT}")
    
    try:
        # Create TCP client
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((HOST, PORT))
        print(f"[+] Connected successfully!")
        
        # Initialize measurement lists
        rtts = []          # Round-trip times
        clock_deviations = []  # Clock deviations (时钟偏差)
        network_delays = [] # One-way network delays (estimated)
        
        print(f"[+] Starting {MEASUREMENT_COUNT} RTT measurements...")
        print("=" * 95)
        print(f"{'#':>3} | {'RTT (ms)':>10} | {'Clock Deviation (ms)':>20} | {'Network Delay (ms)':>18} | {'Server Proc (ms)':>16}")
        print("-" * 95)
        
        # Perform measurements
        for i in range(MEASUREMENT_COUNT):
            try:
                # T1: Client send time
                t1 = get_current_time()
                
                # Prepare PING message
                ping_msg = struct.pack(MESSAGE_FORMAT, MSG_TYPE_PING, t1, 0.0, 0.0)
                
                # Send PING
                client_socket.sendall(ping_msg)
                
                # Receive PONG response
                pong_data = client_socket.recv(MESSAGE_SIZE)
                
                # T4: Client receive time
                t4 = get_current_time()
                
                if len(pong_data) != MESSAGE_SIZE:
                    print(f"[-] Received incomplete data: {len(pong_data)} bytes")
                    continue
                
                # Parse PONG message
                msg_type, t1_echo, t2, t3 = struct.unpack(MESSAGE_FORMAT, pong_data)
                
                if msg_type != MSG_TYPE_PONG:
                    print(f"[-] Invalid message type: 0x{msg_type:02x}")
                    continue
                
                # Calculate RTT (Round-Trip Time)
                # RTT = (T4 - T1) - (T3 - T2)
                # This removes server processing time from the measurement
                rtt = (t4 - t1) - (t3 - t2)
                rtt_ms = rtt * 1000
                rtts.append(rtt_ms)
                
                # Calculate clock offset
                # Assuming symmetric network delay: network_delay = RTT / 2
                network_delay = rtt / 2
                network_delay_ms = network_delay * 1000
                network_delays.append(network_delay_ms)
                
                # Clock deviation (时钟偏差) = server_time - client_time - network_delay
                # At the moment when server sent T3, client's clock would show T1 + network_delay + (T3 - T2)
                # So deviation = T3 - (T1 + network_delay + (T3 - T2))
                # Simplifying: deviation = T2 - T1 - network_delay
                clock_deviation = t2 - t1 - network_delay
                clock_deviation_ms = clock_deviation * 1000
                clock_deviations.append(clock_deviation_ms)
                
                # Server processing time
                server_processing_ms = (t3 - t2) * 1000
                
                # Print measurement result
                print(f"{i+1:3d} | {rtt_ms:10.3f} | {clock_deviation_ms:+20.3f} | {network_delay_ms:18.3f} | {server_processing_ms:16.3f}")
                
                # Small delay between measurements
                time.sleep(MEASUREMENT_INTERVAL)
                
            except socket.error as e:
                print(f"[-] Socket error during measurement {i+1}: {e}")
                break
            except struct.error as e:
                print(f"[-] Data parsing error during measurement {i+1}: {e}")
                break
            except KeyboardInterrupt:
                print("\n[-] Measurement interrupted by user")
                break
        
        print("=" * 95)
        
        # Analyze and report results
        if len(rtts) > 0:
            # RTT statistics
            mean_rtt = statistics.mean(rtts)
            min_rtt = min(rtts)
            max_rtt = max(rtts)
            std_rtt = statistics.stdev(rtts) if len(rtts) > 1 else 0.0
            
            # Clock deviation statistics
            mean_deviation = statistics.mean(clock_deviations)
            min_deviation = min(clock_deviations)
            max_deviation = max(clock_deviations)
            std_deviation = statistics.stdev(clock_deviations) if len(clock_deviations) > 1 else 0.0
            
            # Network delay statistics
            mean_delay = statistics.mean(network_delays)
            min_delay = min(network_delays)
            max_delay = max(network_delays)
            
            print(f"\n[+] Measurement Summary ({len(rtts)} samples):")
            print("\n    RTT (Round-Trip Time):")
            print(f"      Mean:          {mean_rtt:8.3f} ms")
            print(f"      Min:           {min_rtt:8.3f} ms")
            print(f"      Max:           {max_rtt:8.3f} ms")
            print(f"      Std Dev:       {std_rtt:8.3f} ms")
            print(f"      Jitter:        {max_rtt - min_rtt:8.3f} ms")
            
            print("\n    Clock Deviation (时钟偏差 Server - Client):")
            print(f"      Mean:          {mean_deviation:+8.3f} ms")
            print(f"      Min:           {min_deviation:+8.3f} ms")
            print(f"      Max:           {max_deviation:+8.3f} ms")
            print(f"      Std Dev:       {std_deviation:8.3f} ms")
            
            print("\n    Estimated One-Way Network Delay:")
            print(f"      Mean:          {mean_delay:8.3f} ms")
            print(f"      Min:           {min_delay:8.3f} ms")
            print(f"      Max:           {max_delay:8.3f} ms")
            
            # Connection quality assessment
            if mean_rtt < 1.0:
                rtt_quality = "EXCELLENT (LAN)"
            elif mean_rtt < 10.0:
                rtt_quality = "VERY GOOD"
            elif mean_rtt < 50.0:
                rtt_quality = "GOOD"
            elif mean_rtt < 100.0:
                rtt_quality = "FAIR"
            else:
                rtt_quality = "POOR"
            
            # Clock sync quality assessment
            if abs(mean_deviation) < 1.0 and std_deviation < 1.0:
                sync_quality = "EXCELLENT"
            elif abs(mean_deviation) < 5.0 and std_deviation < 5.0:
                sync_quality = "GOOD"
            elif abs(mean_deviation) < 20.0:
                sync_quality = "FAIR"
            else:
                sync_quality = "POOR"
            
            print(f"\n    Connection Quality: {rtt_quality}")
            print(f"    Clock Sync Quality: {sync_quality}")
            
            # NTP-style time sync recommendation
            print("\n    Time Sync Recommendation:")
            print(f"      Apply clock adjustment: {-mean_deviation:+.3f} ms")
            print(f"      Expected accuracy after adjustment: ±{std_deviation:.3f} ms")
            
        else:
            print("[-] No valid measurements collected!")
            
    except ConnectionRefusedError:
        print(f"[-] Connection refused. Make sure time_server_rtt is running on {HOST}:{PORT}")
    except socket.gaierror as e:
        print(f"[-] Network error: {e}")
    except KeyboardInterrupt:
        print("\n[-] Program interrupted by user")
    except Exception as e:
        print(f"[-] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            client_socket.close()
        except:
            pass
        print("\n[+] Connection closed.")

if __name__ == "__main__":
    main()
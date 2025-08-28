#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple DIAG Raw Data Receiver
Just receives and displays raw hexadecimal data from TCP
"""

import socket
import time
import struct

# Networking configuration
HOST = '127.0.0.1'
PORT = 43555

# HDLC-encoded initialization messages (minimal set)
INIT_MESSAGES = [
    b'\x1d\x1c\x3b\x7e',  # 0x1D command
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

# Socket mode specific initialization
SOCKET_MODE_INIT = [
    b'\x28\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x40\x78\x7d\x01',
    b'\x29\x00\x00\x00\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00',
    b'\x07\x00\x00\x00\x05\x00\x00\x00\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\xb6\x78\x00\x00',
    b'\x23\x00\x00\x00\x00\x00\x00\x00',
]

FINAL_MESSAGE = b'\x60\x00\x12\x6a\x7e'

# Configure for B064 and B16C logcodes
DEFAULT_LOGCODES = [0xB064, 0xB16C]


def hex_dump(data, prefix="", width=16):
    """Display data in hex dump format"""
    result = []
    for i in range(0, len(data), width):
        chunk = data[i:i+width]
        hex_str = ' '.join(f'{b:02X}' for b in chunk)
        ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        result.append(f"{prefix}{i:04X}  {hex_str:<{width*3}}  {ascii_str}")
    return '\n'.join(result)


def generate_logcode_command(logcodes):
    """Generate HDLC-encoded logcode configuration command"""
    from hdlc import HDLC
    
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


def main():
    """Main function - Raw hex data receiver"""
    print("="*70)
    print("DIAG RAW HEX DATA RECEIVER")
    print("Displays raw hexadecimal data from TCP stream")
    print("="*70)
    
    # Create socket
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        print(f"\nConnecting to {HOST}:{PORT}...")
        client_socket.connect((HOST, PORT))
        print("Connected successfully!\n")
        
        # Receive welcome message
        welcome_bytes = client_socket.recv(1024)
        welcome_message = welcome_bytes.decode('utf-8', errors='ignore').strip()
        print(f"Server: {welcome_message}\n")
        
        # Detect mode
        is_socket_mode = "Socket mode" in welcome_message
        print(f"Mode detected: {'Socket' if is_socket_mode else 'Legacy'}\n")
        
        # Send initialization sequence
        print("Sending initialization messages...")
        
        # Send socket mode init if needed
        if is_socket_mode:
            print("  Sending socket mode init...")
            for msg in SOCKET_MODE_INIT:
                client_socket.sendall(msg)
                time.sleep(0.05)
        
        # Send standard init messages
        for i, message in enumerate(INIT_MESSAGES, 1):
            print(f"  Init message {i}/{len(INIT_MESSAGES)}")
            client_socket.sendall(message)
            time.sleep(0.1)
        
        # Configure logcodes
        print("\nConfiguring logcodes (B064, B16C)...")
        command = generate_logcode_command(DEFAULT_LOGCODES)
        if command:
            client_socket.sendall(command)
            time.sleep(0.1)
        
        # Send final message
        print("Sending final configuration...")
        client_socket.sendall(FINAL_MESSAGE)
        time.sleep(0.1)
        
        print("\n" + "="*70)
        print("RECEIVING RAW DATA (Press Ctrl+C to stop)")
        print("="*70 + "\n")
        
        # Main receive loop
        packet_count = 0
        total_bytes = 0
        
        while True:
            try:
                # Receive data
                client_socket.settimeout(5.0)
                raw_data = client_socket.recv(65536)
                
                if not raw_data:
                    print("\nConnection closed by server")
                    break
                
                packet_count += 1
                total_bytes += len(raw_data)
                
                # Display packet info
                print(f"\n--- Packet #{packet_count} | {len(raw_data)} bytes | Total: {total_bytes} bytes ---")
                
                # Check if data has timestamp header (8 bytes double)
                if len(raw_data) >= 8:
                    # Try to extract timestamp
                    try:
                        timestamp = struct.unpack('<d', raw_data[:8])[0]
                        print(f"Timestamp (if present): {timestamp:.6f}")
                    except:
                        pass
                
                # Display raw hex data
                print("\nRAW HEX DATA:")
                print(hex_dump(raw_data))
                
                # Also display as continuous hex string (first 200 bytes)
                if len(raw_data) > 200:
                    hex_str = ' '.join(f'{b:02X}' for b in raw_data[:200])
                    print(f"\nFirst 200 bytes: {hex_str} ...")
                else:
                    hex_str = ' '.join(f'{b:02X}' for b in raw_data)
                    print(f"\nComplete data: {hex_str}")
                
                print("-" * 70)
                
            except socket.timeout:
                print(".", end="", flush=True)  # Show activity
                continue
            except socket.error as e:
                print(f"\nSocket error: {e}")
                break
                
    except KeyboardInterrupt:
        print(f"\n\nStopped by user")
        print(f"Total packets received: {packet_count}")
        print(f"Total bytes received: {total_bytes}")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        client_socket.close()
        print("\nConnection closed")


if __name__ == "__main__":
    main()
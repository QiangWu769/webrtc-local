#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Specialized B16C v49 decoder for debugging and analysis
Focuses on receiving, displaying raw hex, and parsing B16C packets
"""

import socket
import time
import struct
import sys
from hdlc import HDLC

# Connection parameters
HOST = '127.0.0.1'
PORT = 43555

# Initialize messages (same as main script)
INIT_MESSAGES = [
    b'\x1d\x1c\x3b\x7e', b'\x00\x78\xf0\x7e', b'\x7c\x93\x49\x7e',
    b'\x1c\x95\x2a\x7e', b'\x0c\x14\x3a\x7e', b'\x63\xe5\xa1\x7e',
    b'\x4b\x0f\x00\x00\xbb\x60\x7e', b'\x4b\x09\x00\x00\x62\xb6\x7e',
    b'\x4b\x08\x00\x00\xbe\xec\x7e', b'\x4b\x08\x01\x00\x66\xf5\x7e',
    b'\x4b\x04\x00\x00\x1d\x49\x7e', b'\x4b\x04\x0f\x00\xd5\xca\x7e',
    b'\x73\x00\x00\x00\x00\x00\x00\x00\xda\x81\x7e',
]
FINAL_MESSAGE = b'\x60\x00\x12\x6a\x7e'

def convert_endianess(data, index, length):
    """Swaps bytes in-place for a given length at a specific index."""
    if length == 2:
        data[index], data[index+1] = data[index+1], data[index]
    elif length == 4:
        data[index], data[index+1], data[index+2], data[index+3] = \
        data[index+3], data[index+2], data[index+1], data[index]

def convert_B16C_v49_S_H_no_asn(data, index_obj):
    index_obj['i'] += 1
    convert_endianess(data, index_obj['i'], 2)
    index_obj['i'] = 4 

def convert_B16C_v49_R_H_no_asn(data, index_obj):
    convert_endianess(data, index_obj['i'], 4)
    index_obj['i'] += 4

def convert_B16C_v49_ULgrant_no_asn(data, index_obj):
    start_pos = index_obj['i']
    convert_endianess(data, start_pos + 2, 2)
    convert_endianess(data, start_pos + 4, 2)
    convert_endianess(data, start_pos + 6, 2)
    index_obj['i'] += 16

def convert_B16C_v49_DLgrant_no_asn(data, index_obj):
    index_obj['i'] += 8

def decode_b16c_v49(payload, output_file=None):
    """
    Decodes B16C v49 payload using the validated logic.
    Prints raw hex data and a summary of SFN/subfn, MCS, TBS, and RBs for each record.
    """
    data = bytearray(payload)
    index_obj = {'i': 0}
    output_lines = []
    parsed_records = []

    # Display raw hex first
    output_lines.append("\n" + "="*80)
    output_lines.append("B16C v49 PACKET ANALYSIS")
    output_lines.append("="*80)
    output_lines.append(f"\nRAW HEX DATA ({len(payload)} bytes):")
    for i in range(0, len(payload), 16):
        hex_part = ' '.join(f'{b:02X}' for b in payload[i:i+16])
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in payload[i:i+16])
        output_lines.append(f"  {i:04X}: {hex_part:<48} |{ascii_part}|")
    
    # Print hex to console and file
    for line in output_lines:
        print(line)
        if output_file:
            output_file.write(line + '\n')
    
    output_lines = []  # Reset for parsed data
    
    if len(data) < 4:
        msg = "\n[ERROR] Payload too short (< 4 bytes) for header."
        print(msg)
        if output_file:
            output_file.write(msg + '\n')
            output_file.flush()
        return []

    # --- S_H (Standard Header) ---
    start_S_H = index_obj['i']
    convert_B16C_v49_S_H_no_asn(data, index_obj)
    
    version = data[start_S_H]
    num_record = ((data[start_S_H+1] & 0x07) << 2 | (data[start_S_H+2] & 0xC0) >> 6)

    output_lines.append(f"\nPARSED DATA:")
    output_lines.append(f"Version: {version}, Number of records: {num_record}")
    output_lines.append("-" * 60)

    for i in range(num_record):
        if index_obj['i'] + 4 > len(data):
            output_lines.append(f"Record {i+1}: Error - Not enough data for Record Header.")
            break
        
        # --- Record Header ---
        start_record = index_obj['i']
        convert_B16C_v49_R_H_no_asn(data, index_obj)

        num_ul_grant = ((data[start_record+1] & 0x01) << 2) | ((data[start_record+2] & 0xC0) >> 6)
        subfn = (data[start_record+2] & 0x3C) >> 2
        sysfn = ((data[start_record+2] & 0x03) << 8) | (data[start_record+3])
        
        # --- Grant Type Decision ---
        if num_ul_grant != 0:
            if index_obj['i'] + 16 > len(data):
                output_lines.append(f"Record {i+1}: Error - Not enough data for UL Grant payload.")
                break

            start_UL = index_obj['i']
            
            # This calculation must be done BEFORE the data is modified by endianness conversion
            num_of_resource_blocks = (data[start_UL + 6] & 0xFC) >> 2
            
            # Now, perform conversions for the other fields
            convert_B16C_v49_ULgrant_no_asn(data, index_obj)
            
            tbs_index = (data[start_UL+2] & 0xFC) >> 2
            mcs_index = ((data[start_UL+2] & 0x03) << 3) | ((data[start_UL+3] & 0xE0) >> 5)
            
            # Add formatted line to output
            output_lines.append(
                f"Record {i+1:2d} (UL): SFN/subfn: {sysfn:4d}/{subfn}, "
                f"MCS: {mcs_index:2d}, TBS: {tbs_index:2d}, RBs: {num_of_resource_blocks:2d}"
            )
            
            parsed_records.append({
                'sysfn': sysfn, 'subfn': subfn, 'mcs_index': mcs_index, 
                'tbs_index': tbs_index, 'num_rbs': num_of_resource_blocks
            })

        else:  # DL grant
            if index_obj['i'] + 8 > len(data):
                output_lines.append(f"Record {i+1}: Error - Not enough data for DL Grant payload.")
                break
            
            output_lines.append(f"Record {i+1:2d} (DL): SFN/subfn: {sysfn:4d}/{subfn}")
            convert_B16C_v49_DLgrant_no_asn(data, index_obj)
    
    # Print all collected lines to console and file
    for line in output_lines:
        print(line)
        if output_file:
            output_file.write(line + '\n')
            output_file.flush()
            
    return parsed_records

def generate_logcode_command(logcodes):
    """Generate DIAG command to enable specific log codes"""
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

def send_message(sock, message):
    """Send message and get response"""
    print(f"Sending message ({len(message)} bytes)")
    sock.sendall(message)
    time.sleep(0.1)
    
    try:
        sock.settimeout(1)
        response = sock.recv(16384)
        print(f"Received response ({len(response)} bytes)")
        return response
    except socket.timeout:
        print("Receive timeout, no response")
        return None

def main():
    """Main function to connect and receive B16C packets"""
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    # Open output file
    output_file = open('b16c_v49_output.txt', 'w')
    
    try:
        print(f"Connecting to {HOST}:{PORT}...")
        client_socket.connect((HOST, PORT))
        print("Connection successful!")
        
        # Receive welcome message
        welcome = client_socket.recv(1024)
        welcome_str = welcome.decode('utf-8', errors='ignore').strip()
        print(f"Welcome: {welcome_str}")
        
        # Detect operating mode
        is_socket_mode = "Socket mode" in welcome_str
        print(f"Detected mode: {'SOCKET' if is_socket_mode else 'LEGACY'}")
        
        # Send socket mode initialization if needed
        if is_socket_mode:
            socket_mode_init_messages = [
                b'\x28\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x40\x78\x7d\x01',
                b'\x29\x00\x00\x00\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00',
                b'\x07\x00\x00\x00\x05\x00\x00\x00\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\xb6\x78\x00\x00',
                b'\x23\x00\x00\x00\x00\x00\x00\x00',
            ]
            print("\nSending socket mode initialization...")
            for msg in socket_mode_init_messages:
                print(f"  Sending {len(msg)} bytes: {msg.hex()}")
                client_socket.sendall(msg)
                time.sleep(0.1)
        
        # Send standard initialization sequence
        print("\nSending standard initialization messages...")
        for message in INIT_MESSAGES:
            send_message(client_socket, message)
            time.sleep(0.2)
        
        # Enable B16C (0xB16C) only
        print("\nEnabling B16C log code...")
        command = generate_logcode_command([0xB16C])
        if command:
            send_message(client_socket, command)
            send_message(client_socket, FINAL_MESSAGE)
        
        # Drain functionality removed - not needed for B16C monitoring
        
        print("\nStarting B16C monitoring...")
        print("Press Ctrl-C to exit\n")
        
        receive_buffer = b''
        packet_count = 0
        
        while True:
            try:
                client_socket.settimeout(1.0)
                new_data = client_socket.recv(65536)
                
                if not new_data:
                    print("Connection closed by server")
                    break
                
                receive_buffer += new_data
                
                # Process data with timestamp header
                header_size = 8  # sizeof(double)
                
                while len(receive_buffer) >= header_size:
                    # Parse timestamp
                    ts_bridge = struct.unpack('<d', receive_buffer[:header_size])[0]
                    remaining_data = receive_buffer[header_size:]
                    
                    if len(remaining_data) > 12:
                        # Skip 12-byte DIAG header
                        hdlc_stream = remaining_data[12:]
                        
                        # Process HDLC frames
                        potential_frames = hdlc_stream.split(b'\x7e')
                        for frame_data in potential_frames:
                            if not frame_data:
                                continue
                            
                            decoded_payload = HDLC.decode(frame_data + b'\x7e')
                            if decoded_payload is None:
                                continue
                            
                            # Check for standard DIAG format
                            if not decoded_payload.startswith(b'\x98\x01\x00\x00\x01\x00\x00\x00'):
                                continue
                            
                            data = decoded_payload[12:]
                            if len(data) < 12:
                                continue
                            
                            msg_len, logcode, timestamp = struct.unpack('<HHQ', data[:12])
                            payload = data[12:12 + msg_len]
                            
                            # Check if this is B16C
                            if logcode == 0xB16C:
                                packet_count += 1
                                print(f"\n{'#'*80}")
                                print(f"B16C PACKET #{packet_count} (timestamp: {ts_bridge:.6f})")
                                output_file.write(f"\n{'#'*80}\n")
                                output_file.write(f"B16C PACKET #{packet_count} (timestamp: {ts_bridge:.6f})\n")
                                
                                # Check version
                                if len(payload) > 0 and payload[0] == 49:
                                    decode_b16c_v49(payload, output_file)
                                else:
                                    msg = f"Not v49 (version={payload[0] if len(payload) > 0 else 'unknown'})"
                                    print(msg)
                                    output_file.write(msg + '\n')
                    
                    receive_buffer = b''
                    break
                    
            except socket.timeout:
                continue
            except socket.error as e:
                print(f"Socket error: {e}")
                break
                
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Cleanup
        client_socket.close()
        output_file.close()
        print("Connection closed")
        print(f"Output saved to: b16c_v49_output.txt")

if __name__ == "__main__":
    main()
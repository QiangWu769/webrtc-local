#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simplified DIAG BSR Parser - No drain, no file output
Just receives and processes DIAG data in real-time
"""

import socket
import time
from datetime import datetime, timedelta, timezone
import struct
from hdlc import HDLC

# DIAG timestamp constants
PER_SECOND = 52428800.0
EPOCH = datetime(1980, 1, 6, 0, 0, 0, tzinfo=timezone.utc)

# Networking configuration
HOST = '127.0.0.1'
PORT = 43555

# HDLC-encoded initialization messages
INIT_MESSAGES = [
    b'\x1d\x1c\x3b\x7e',  # 0x1D command for timestamp
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

# Socket mode specific initialization (if needed)
SOCKET_MODE_INIT = [
    b'\x28\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x40\x78\x7d\x01',
    b'\x29\x00\x00\x00\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00',
    b'\x07\x00\x00\x00\x05\x00\x00\x00\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\xb6\x78\x00\x00',
    b'\x23\x00\x00\x00\x00\x00\x00\x00',
]

FINAL_MESSAGE = b'\x60\x00\x12\x6a\x7e'
DEFAULT_LOGCODES = [0xB064, 0xB16C]

# BSR and TBS mapping tables
RNTI_TYPE_MAP = {1: "C-RNTI", 2: "SPS-RNTI"}
BSR_EVENT_MAP = {0: "none", 1: "periodic", 2: "high-data-arrival", 3: "robustness-bsr"}
BSR_TRIG_MAP = {0: "no-bsr", 1: "cancelled", 2: "l-bsr", 3: "s-bsr", 4: "pad-l-bsr", 5: "pad-s-bsr", 6: "pad-t-bsr"}
TBS_MAP = {
    0: "TBS_Index_0", 1: "TBS_Index_1", 2: "TBS_Index_2", 3: "TBS_Index_3",
    4: "TBS_Index_4", 5: "TBS_Index_5", 6: "TBS_Index_6", 7: "TBS_Index_7",
    8: "TBS_Index_8", 9: "TBS_Index_9", 10: "TBS_Index_10", 11: "TBS_Index_11",
    12: "TBS_Index_12", 13: "TBS_Index_13", 14: "TBS_Index_14", 15: "TBS_Index_15",
    16: "TBS_Index_16", 17: "TBS_Index_17", 18: "TBS_Index_18", 19: "TBS_Index_19",
    20: "TBS_Index_20", 21: "TBS_Index_21", 22: "TBS_Index_22", 23: "TBS_Index_23",
    24: "TBS_Index_24", 25: "TBS_Index_25", 26: "TBS_Index_26", 27: "TBS_Index_26A",
    28: "TBS_Index_27", 29: "TBS_Index_28", 30: "TBS_Index_29", 31: "TBS_Index_30",
    32: "TBS_Index_31", 33: "TBS_Index_32", 34: "TBS_Index_32A", 35: "TBS_Index_33"
}


class SimpleDiagParser:
    """Simplified DIAG data parser - real-time processing only"""
    
    def __init__(self):
        self.stats = {
            'b064_count': 0,
            'b16c_count': 0,
            'total_messages': 0,
            'last_timestamp': None
        }
    
    def convert_timestamp(self, ts):
        """Convert DIAG timestamp to readable format"""
        if ts == 0:
            return "N/A"
        try:
            seconds_since_epoch = ts / PER_SECOND
            utc_time = EPOCH + timedelta(seconds=seconds_since_epoch)
            local_time = utc_time.astimezone(None)
            return local_time.strftime('%Y-%m-%d %H:%M:%S.%f')
        except (OverflowError, ValueError):
            return str(ts)
    
    def convert_timestamp_to_unix(self, ts):
        """Convert DIAG timestamp to Unix timestamp"""
        if ts == 0:
            return 0.0
        try:
            seconds_since_epoch = ts / PER_SECOND
            utc_time = EPOCH + timedelta(seconds=seconds_since_epoch)
            return utc_time.timestamp()
        except (OverflowError, ValueError):
            return 0.0
    
    def decode_b16c_payload(self, payload, timestamp):
        """Decode 0xB16C UL grant messages"""
        if len(payload) < 4:
            return []
        
        version = payload[0]
        num_records = (payload[1] & 0xFC) >> 2
        readable_timestamp = self.convert_timestamp(timestamp)
        
        print(f"\n[0xB16C] UL Grant - {readable_timestamp}")
        print(f"  Version: {version}, Records: {num_records}")
        
        cursor = 4
        records = []
        
        for i in range(num_records):
            if cursor + 128 > len(payload):
                break
                
            h1, h2 = payload[cursor], payload[cursor + 1]
            subfn = (h2 & 0x3C) >> 2
            sysfn = ((h2 & 0x03) << 8) | h1
            num_ul_grant = (h2 & 0xC0) >> 6
            cursor += 2
            
            if num_ul_grant != 0:
                ul_grant_view = payload[cursor : cursor + 126]
                mcs_index = (ul_grant_view[5] & 0xF8) >> 3
                redundancy_version = (ul_grant_view[5] & 0x06) >> 1
                tbs_index = ul_grant_view[6] & 0x3F
                num_of_resource_blocks = ul_grant_view[8] & 0x7F
                
                tbs_string = TBS_MAP.get(tbs_index, "invalid")
                
                print(f"  [Record {i+1}] SysFN={sysfn}, SubFN={subfn}")
                print(f"    MCS={mcs_index}, RV={redundancy_version}")
                print(f"    TBS={tbs_string}, RBs={num_of_resource_blocks}")
                
                records.append({
                    'sysfn': sysfn,
                    'subfn': subfn,
                    'mcs_index': mcs_index,
                    'tbs_string': tbs_string,
                    'num_rbs': num_of_resource_blocks
                })
            
            cursor += 126
        
        return records
    
    def decode_b064_payload(self, payload, timestamp):
        """Decode 0xB064 BSR messages"""
        if len(payload) < 4:
            return []
        
        num_subpkt = payload[0]
        readable_timestamp = self.convert_timestamp(timestamp)
        
        print(f"\n[0xB064] BSR Report - {readable_timestamp}")
        print(f"  Sub-packets: {num_subpkt}")
        
        cursor = 4
        records = []
        
        for _ in range(num_subpkt):
            if cursor + 5 > len(payload):
                break
                
            num_samples = payload[cursor + 4]
            cursor += 5
            
            for j in range(num_samples):
                if cursor + 14 > len(payload):
                    break
                    
                sample_h_view = memoryview(payload[cursor:cursor+14])
                sfn_subfn_word = struct.unpack('<H', sample_h_view[4:6])[0]
                sysfn = sfn_subfn_word >> 4
                subfn = sfn_subfn_word & 0x000F
                
                grant_bytes = struct.unpack('<H', sample_h_view[6:8])[0]
                padding = struct.unpack('<H', sample_h_view[9:11])[0]
                bsr_event = sample_h_view[11] & 0x03
                bsr_trig = sample_h_view[12] & 0x07
                hdrlen = sample_h_view[13]
                
                cursor += 14
                
                # Parse BSR buffer sizes
                buffer_size = [0, 0, 0, 0]
                lcg = -1
                bsr_type = 0
                step = 0
                start_element = cursor
                
                while step < hdrlen:
                    if start_element + step >= len(payload):
                        break
                        
                    E = (payload[start_element + step] >> 5) & 1
                    LCID_data = payload[start_element + step] & 31
                    
                    if LCID_data == 29:
                        bsr_type = 1  # Short BSR
                    elif LCID_data == 30:
                        bsr_type = 2  # Long BSR
                    elif LCID_data == 31 and bsr_type == 0:
                        bsr_type = 3  # Padding
                    
                    if E == 1 and LCID_data <= 11:
                        step += 1
                        if start_element + step >= len(payload):
                            break
                        F = (payload[start_element + step] >> 7) & 1
                        if F == 0:
                            L = payload[start_element + step] & 127
                        step += 1 if F != 0 else 0
                    elif E == 0:
                        step += 1
                        if start_element + step >= len(payload):
                            break
                            
                        if bsr_type == 1:  # Short BSR
                            lcg = (payload[start_element + step] >> 6) & 3
                            buffer_size[lcg] = payload[start_element + step] & 63
                        elif bsr_type == 2:  # Long BSR
                            if start_element + step + 2 >= len(payload):
                                break
                            buffer_size[0] = (payload[start_element + step] & 0xFC) >> 2
                            buffer_size[1] = ((payload[start_element + step] & 3) << 4) | ((payload[start_element + step + 1] & 0xF0) >> 4)
                            buffer_size[2] = ((payload[start_element + step + 1] & 15) << 2) | ((payload[start_element + step + 2] & 0xC0) >> 6)
                            buffer_size[3] = payload[start_element + step + 2] & 63
                            step += 2
                        break
                    
                    step += 1
                
                cursor += hdrlen
                
                bsr_event_str = BSR_EVENT_MAP.get(bsr_event, "unknown")
                bsr_trig_str = BSR_TRIG_MAP.get(bsr_trig, "unknown")
                
                print(f"  [Sample {j+1}] SysFN={sysfn}, SubFN={subfn}")
                print(f"    BSR Event: {bsr_event_str}, Trigger: {bsr_trig_str}")
                print(f"    Buffer sizes - LCG0:{buffer_size[0]}, LCG1:{buffer_size[1]}, LCG2:{buffer_size[2]}, LCG3:{buffer_size[3]}")
                print(f"    Grant: {grant_bytes} bytes, Padding: {padding} bytes")
                
                records.append({
                    'sysfn': sysfn,
                    'subfn': subfn,
                    'buffer_size': buffer_size,
                    'grant_bytes': grant_bytes,
                    'bsr_event': bsr_event_str,
                    'bsr_trig': bsr_trig_str
                })
        
        return records
    
    def process_hdlc_stream(self, hdlc_stream, ts_bridge=None):
        """Process HDLC data stream and extract DIAG messages"""
        potential_frames = hdlc_stream.split(b'\x7e')
        
        for frame_data in potential_frames:
            if not frame_data:
                continue
            
            # Decode HDLC frame
            decoded_payload = HDLC.decode(frame_data + b'\x7e')
            if decoded_payload is None:
                continue
            
            # Check for standard DIAG format
            if not decoded_payload.startswith(b'\x98\x01\x00\x00\x01\x00\x00\x00'):
                continue
            
            # Parse DIAG message
            data = decoded_payload[12:]
            if len(data) < 12:
                continue
            
            msg_len, logcode, timestamp = struct.unpack('<HHQ', data[:12])
            payload = data[12 : 12 + msg_len]
            
            # Update statistics
            self.stats['total_messages'] += 1
            self.stats['last_timestamp'] = self.convert_timestamp(timestamp)
            
            # Calculate latency if bridge timestamp provided
            if ts_bridge:
                ts_ran_event = self.convert_timestamp_to_unix(timestamp)
                if ts_ran_event > 0:
                    latency_ms = (ts_bridge - ts_ran_event) * 1000
                    print(f"\n[LATENCY] Pipeline: {latency_ms:.3f}ms")
            
            # Process specific log codes
            if logcode == 0xB16C:
                self.stats['b16c_count'] += 1
                self.decode_b16c_payload(payload, timestamp)
            elif logcode == 0xB064:
                self.stats['b064_count'] += 1
                self.decode_b064_payload(payload, timestamp)
            else:
                print(f"\n[0x{logcode:04X}] Unknown logcode - {self.convert_timestamp(timestamp)}")
    
    def print_stats(self):
        """Print current statistics"""
        print("\n" + "="*60)
        print("STATISTICS:")
        print(f"  Total messages: {self.stats['total_messages']}")
        print(f"  B064 (BSR) messages: {self.stats['b064_count']}")
        print(f"  B16C (UL Grant) messages: {self.stats['b16c_count']}")
        print(f"  Last timestamp: {self.stats['last_timestamp']}")
        print("="*60)


def generate_logcode_command(logcodes):
    """Generate HDLC-encoded logcode configuration command"""
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


def send_message(sock, message, description=""):
    """Send message to socket and optionally wait for response"""
    if description:
        print(f"[SEND] {description}")
    else:
        print(f"[SEND] {len(message)} bytes")
    
    sock.sendall(message)
    time.sleep(0.1)
    
    # Try to get response (non-blocking)
    try:
        sock.settimeout(0.5)
        response = sock.recv(4096)
        print(f"[RECV] {len(response)} bytes response")
        return response
    except socket.timeout:
        return None


def detect_mode(welcome_message):
    """Detect operating mode from welcome message"""
    if "Socket mode" in welcome_message:
        return "socket"
    elif "Legacy mode" in welcome_message or "bridge_diag_client connected" in welcome_message:
        return "legacy"
    else:
        return "unknown"


def main():
    """Main function - simplified DIAG client"""
    print("="*60)
    print("Simplified DIAG BSR Parser")
    print("Real-time processing only - No drain, No file output")
    print("="*60)
    
    # Connect to DIAG bridge
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    parser = SimpleDiagParser()
    
    try:
        print(f"\n[CONNECT] Connecting to {HOST}:{PORT}...")
        client_socket.connect((HOST, PORT))
        print("[CONNECT] Success!")
        
        # Receive welcome message and detect mode
        welcome_bytes = client_socket.recv(1024)
        welcome_message = welcome_bytes.decode('utf-8', errors='ignore').strip()
        print(f"[SERVER] {welcome_message}")
        
        mode = detect_mode(welcome_message)
        print(f"[MODE] Detected: {mode}")
        
        # Send initialization messages
        print("\n[INIT] Starting initialization sequence...")
        
        # Send socket mode init if needed
        if mode == "socket":
            print("[INIT] Sending socket mode specific messages...")
            for msg in SOCKET_MODE_INIT:
                client_socket.sendall(msg)
                time.sleep(0.05)
        
        # Send standard init messages
        for i, message in enumerate(INIT_MESSAGES, 1):
            send_message(client_socket, message, f"Init message {i}/{len(INIT_MESSAGES)}")
            time.sleep(0.1)
        
        # Configure logcodes
        print("\n[CONFIG] Setting up logcodes (B064, B16C)...")
        command = generate_logcode_command(DEFAULT_LOGCODES)
        if command:
            send_message(client_socket, command, "Logcode configuration")
        
        # Send final configuration
        send_message(client_socket, FINAL_MESSAGE, "Final configuration")
        
        print("\n[START] Monitoring DIAG data stream...")
        print("Press Ctrl+C to stop and see statistics\n")
        
        # Main receive loop
        receive_buffer = b''
        stats_counter = 0
        
        while True:
            try:
                client_socket.settimeout(1.0)
                new_data = client_socket.recv(65536)
                
                if not new_data:
                    print("\n[DISCONNECT] Connection closed by server")
                    break
                
                # Add to buffer
                receive_buffer += new_data
                
                # Process data with timestamp header (8 bytes double)
                header_size = 8
                while len(receive_buffer) >= header_size:
                    # Extract bridge timestamp
                    ts_bridge = struct.unpack('<d', receive_buffer[:header_size])[0]
                    
                    # Get remaining data
                    remaining_data = receive_buffer[header_size:]
                    
                    if len(remaining_data) > 12:
                        # Skip TCP header (12 bytes) and process HDLC stream
                        hdlc_stream = remaining_data[12:]
                        parser.process_hdlc_stream(hdlc_stream, ts_bridge)
                    
                    # Clear buffer for next packet
                    receive_buffer = b''
                    break
                
                # Print statistics every 100 messages
                stats_counter += 1
                if stats_counter >= 100:
                    parser.print_stats()
                    stats_counter = 0
                    
            except socket.timeout:
                continue
            except socket.error as e:
                print(f"\n[ERROR] Socket error: {e}")
                break
                
    except KeyboardInterrupt:
        print("\n\n[STOP] Monitoring stopped by user")
        parser.print_stats()
    except Exception as e:
        print(f"\n[ERROR] {e}")
    finally:
        client_socket.close()
        print("\n[CLOSE] Connection closed")


if __name__ == "__main__":
    main()
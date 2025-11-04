# -*- coding: utf-8 -*-
# Simplified DIAG Parser - Outputs separate log files for B064, B16C, and B139
# Based on diag_bsr.py parsing logic, without timestamp fields

import socket
import time
import struct
import os
import threading
from hdlc import HDLC

# Operating modes
class OperatingMode:
    UNKNOWN = "unknown"
    LEGACY = "legacy"  
    SOCKET = "socket"

# Global variables
current_mode = OperatingMode.UNKNOWN
drain_thread_running = False
client_socket_lock = None
client_socket_global = None
DRAIN_BUFFER_COMMAND = b'\x24\x00\x00\x00\x00\x00\x00\x00'

def convert_endianess(data, index, length):
    """Swap bytes for endianness conversion"""
    if length == 2:
        data[index], data[index+1] = data[index+1], data[index]
    elif length == 4:
        data[index], data[index+1], data[index+2], data[index+3] = \
        data[index+3], data[index+2], data[index+1], data[index]

def convert_S_H_B064_no_asn(data, index_obj):
    """Convert S_H header for B064"""
    index_obj['i'] += 4

def convert_Subpkt_H_B064_no_asn(data, index_obj):
    """Convert Subpkt_H header for B064"""
    start_pos = index_obj['i']
    convert_endianess(data, start_pos + 2, 2)
    index_obj['i'] += 5

def convert_Sample_H_B064_no_asn(data, index_obj):
    """Convert Sample_H header for B064"""
    start_pos = index_obj['i']
    convert_endianess(data, start_pos + 4, 2)
    convert_endianess(data, start_pos + 6, 2)
    convert_endianess(data, start_pos + 9, 2)
    index_obj['i'] += 14

def convert_B16C_v49_S_H_no_asn(data, index_obj):
    """Convert header for B16C v49"""
    index_obj['i'] += 1
    convert_endianess(data, index_obj['i'], 2)
    index_obj['i'] = 4

class SimplifiedDiagParser:
    """Simplified parser that outputs to three separate log files"""
    
    def __init__(self):
        # Output files for each logcode type
        self.b064_file = "b064_bsr_data.txt"
        self.b16c_file = "b16c_grant_data.txt"
        self.b139_file = "b139_pusch_data.txt"
        
        # Initialize files with headers
        self._init_output_files()
        
        # Buffers for batch writing
        self.b064_buffer = []
        self.b16c_buffer = []
        self.b139_buffer = []
        
    def _init_output_files(self):
        """Initialize output files with headers"""
        # B064 header: BSR data fields (simplified - only SysFN, SubFN and LCG values)
        with open(self.b064_file, 'w') as f:
            header = ["SysFN", "SubFN", "LCG_0", "LCG_1", "LCG_2", "LCG_3"]
            f.write("\t".join(header) + "\n")
        
        # B16C header: UL grant data fields
        with open(self.b16c_file, 'w') as f:
            header = ["SysFN", "SubFN", "Num_RBs", "TBS_Index", "MCS_Index", "Redund_Ver"]
            f.write("\t".join(header) + "\n")
        
        # B139 header: PUSCH transmission data fields
        with open(self.b139_file, 'w') as f:
            header = ["Current_SFN_SF", "Redund_Ver", "PUSCH_TB_Size"]
            f.write("\t".join(header) + "\n")
    
    def decode_b064_payload(self, payload):
        """Decode B064 BSR payload"""
        results = []
        if len(payload) < 4:
            return results
            
        data = bytearray(payload)
        index_obj = {'i': 0}
        
        # Parse S_H header
        start_S_H = index_obj['i']
        convert_S_H_B064_no_asn(data, index_obj)
        num_subpkt = data[start_S_H]
        
        for i in range(num_subpkt):
            if index_obj['i'] + 5 > len(data): 
                break
                
            # Parse Subpacket Header
            start_Subpkt_H = index_obj['i']
            subpkt_header = bytearray(data[start_Subpkt_H : start_Subpkt_H + 5])
            convert_Subpkt_H_B064_no_asn(subpkt_header, {'i': 0})
            num_samples = subpkt_header[4]
            index_obj['i'] += 5
            
            for j in range(num_samples):
                if index_obj['i'] + 14 > len(data): 
                    break
                    
                # Parse Sample Header
                start_Sample_H = index_obj['i']
                sample_header = bytearray(data[start_Sample_H : start_Sample_H + 14])
                convert_Sample_H_B064_no_asn(sample_header, {'i': 0})
                
                # Extract fields
                sysfn = (sample_header[4] << 4) | ((sample_header[5] & 0xF0) >> 4)
                subfn = sample_header[5] & 0x0F
                grant_bytes = (sample_header[6] << 8) | sample_header[7]
                padding = (sample_header[9] << 8) | sample_header[10]
                bsr_event = sample_header[11] & 0x03
                bsr_trig = sample_header[12] & 0x07
                hdrlen = sample_header[13]
                
                index_obj['i'] += 14
                
                # Parse BSR elements
                buffer_size = [-1, -1, -1, -1]
                lcg = -1
                bsr_type = 0
                has_bsr_data = False
                
                if hdrlen > 0 and index_obj['i'] + hdrlen <= len(data):
                    start_element = index_obj['i']
                    step = 0
                    
                    while step < hdrlen:
                        if start_element + step >= len(data): 
                            break
                        element_byte = data[start_element + step]
                        E = (element_byte >> 5) & 1
                        LCID_data = element_byte & 31

                        # Determine BSR type
                        if LCID_data == 29: 
                            bsr_type = 1  # Short BSR
                            has_bsr_data = True
                            buffer_size = [0, 0, 0, 0]
                        elif LCID_data == 30: 
                            bsr_type = 2  # Long BSR
                            has_bsr_data = True
                            buffer_size = [0, 0, 0, 0]
                        elif LCID_data == 31 and bsr_type == 0: 
                            bsr_type = 3  # Padding
                        
                        if E == 1 and LCID_data <= 11:
                            step += 1
                            if start_element + step >= len(data): 
                                break
                            if (data[start_element + step] >> 7) & 1 != 0: 
                                step += 1
                        elif E == 0:
                            step += 1
                            if start_element + step >= len(data): 
                                break
                            
                            bsr_data_byte_1 = data[start_element + step]
                            if bsr_type == 1:  # Short BSR
                                lcg = (bsr_data_byte_1 >> 6) & 3
                                buffer_size[lcg] = bsr_data_byte_1 & 63
                            elif bsr_type == 2:  # Long BSR
                                if start_element + step + 2 < len(data):
                                    bsr_data_byte_2 = data[start_element + step + 1]
                                    bsr_data_byte_3 = data[start_element + step + 2]
                                    buffer_size[0] = (bsr_data_byte_1 & 0xFC) >> 2
                                    buffer_size[1] = ((bsr_data_byte_1 & 3) << 4) | ((bsr_data_byte_2 & 0xF0) >> 4)
                                    buffer_size[2] = ((bsr_data_byte_2 & 15) << 2) | ((bsr_data_byte_3 & 0xC0) >> 6)
                                    buffer_size[3] = bsr_data_byte_3 & 63
                                    step += 2
                            
                            if step + 1 > hdrlen:
                                bsr_type = 0
                            break
                        
                        step += 1
                    
                    index_obj['i'] += hdrlen
                
                # Only create record if BSR data found
                if has_bsr_data and any(val > 0 for val in buffer_size):
                    # Calculate combined current_sfn_sf (sysfn * 10 + subfn)
                    current_sfn_sf = sysfn * 10 + subfn
                    record = {
                        "current_sfn_sf": current_sfn_sf,
                        "lcg_0": buffer_size[0],
                        "lcg_1": buffer_size[1],
                        "lcg_2": buffer_size[2],
                        "lcg_3": buffer_size[3]
                    }
                    results.append(record)
                
        return results
    
    def decode_b16c_v48(self, payload):
        """Decode B16C version 48"""
        parsed_records = []
        if len(payload) < 4: 
            return []
        
        version = payload[0]
        payload_view = memoryview(payload)
        cursor = 4
        
        while cursor < len(payload_view):
            if cursor + 2 > len(payload_view):
                break
            
            h1, h2 = payload_view[cursor], payload_view[cursor + 1]
            subfn = (h2 & 0x3C) >> 2
            
            if not (0 <= subfn <= 9):
                cursor += 1
                continue
            
            if cursor + 128 > len(payload_view):
                break
                
            sysfn = ((h2 & 0x03) << 8) | h1
            num_ul_grant = (h2 & 0xC0) >> 6
            
            if num_ul_grant != 0:
                record_payload_cursor = cursor + 2
                ul_grant_view = payload_view[record_payload_cursor : record_payload_cursor + 126]
                
                mcs_index = (ul_grant_view[5] & 0xF8) >> 3
                redundancy_version = (ul_grant_view[5] & 0x06) >> 1
                tbs_index = ul_grant_view[6] & 0x3F
                num_of_resource_blocks = ul_grant_view[8] & 0x7F
                
                # Calculate combined current_sfn_sf (sysfn * 10 + subfn)
                current_sfn_sf = sysfn * 10 + subfn
                record_data = {
                    "current_sfn_sf": current_sfn_sf,
                    "num_rbs": num_of_resource_blocks,
                    "tbs_index": tbs_index,
                    "mcs_index": mcs_index,
                    "redund_ver": redundancy_version
                }
                parsed_records.append(record_data)
            
            cursor += 128
            
        return parsed_records
    
    def decode_b16c_v49(self, payload):
        """Decode B16C version 49"""
        parsed_records = []
        if len(payload) < 4:
            return []
        
        data = bytearray(payload)
        index_obj = {'i': 0}
        
        version = data[0]
        
        start_S_H = index_obj['i']
        convert_B16C_v49_S_H_no_asn(data, index_obj)
        
        num_record = ((data[start_S_H+1] & 0x07) << 2 | (data[start_S_H+2] & 0xC0) >> 6)
        
        for i in range(num_record):
            if index_obj['i'] + 4 > len(data):
                break
            
            start_record = index_obj['i']
            
            raw_record_header = data[start_record:start_record+4]
            num_dl_grant = (raw_record_header[2] & 0x06) >> 1
            
            reversed_record_header = bytearray(raw_record_header)
            convert_endianess(reversed_record_header, 0, 4)
            
            num_ul_grant = ((reversed_record_header[1] & 0x01) << 2) | ((reversed_record_header[2] & 0xC0) >> 6)
            subfn = (reversed_record_header[2] & 0x3C) >> 2
            sysfn = ((reversed_record_header[2] & 0x03) << 8) | (reversed_record_header[3])
            
            index_obj['i'] += 4
            
            if num_ul_grant > 0:
                if index_obj['i'] + 16 > len(data): 
                    break
                
                start_UL = index_obj['i']
                num_of_resource_blocks = (data[start_UL + 6] & 0xFC) >> 2
                
                ul_grant_data = bytearray(data[start_UL : start_UL+16])
                convert_endianess(ul_grant_data, 2, 2)
                convert_endianess(ul_grant_data, 4, 2)
                convert_endianess(ul_grant_data, 6, 2)
                
                tbs_index = (ul_grant_data[2] & 0xFC) >> 2
                mcs_index = ((ul_grant_data[2] & 0x03) << 3) | ((ul_grant_data[3] & 0xE0) >> 5)
                redundancy_version = (ul_grant_data[3] & 0x18) >> 3
                
                # Calculate combined current_sfn_sf (sysfn * 10 + subfn)
                current_sfn_sf = sysfn * 10 + subfn
                record_data = {
                    "current_sfn_sf": current_sfn_sf,
                    "num_rbs": num_of_resource_blocks,
                    "tbs_index": tbs_index,
                    "mcs_index": mcs_index,
                    "redund_ver": redundancy_version
                }
                parsed_records.append(record_data)
                index_obj['i'] += 16
            
            if num_dl_grant > 0:
                if index_obj['i'] + 8 > len(data): 
                    break
                index_obj['i'] += 8
        
        return parsed_records
    
    def decode_b16c_payload(self, payload):
        """Dispatcher for B16C decoding"""
        if len(payload) < 1:
            return []
        
        version = payload[0]
        
        if version == 48:
            return self.decode_b16c_v48(payload)
        elif version == 49:
            return self.decode_b16c_v49(payload)
        else:
            print("[WARNING] Unsupported B16C version: {}".format(version))
            return []
    
    def decode_b139_payload(self, payload):
        """Decode B139 PUSCH transmission data"""
        parsed_records = []
        if len(payload) < 8:
            return []
        
        # Only supporting v161 for now
        version = payload[0]
        if version != 161:
            print("[WARNING] Unsupported B139 version: {}".format(version))
            return []
        
        num_of_records = (payload[2] & 0xFE) >> 1
        cursor = 8  # Skip 8-byte header
        
        for _ in range(num_of_records):
            if cursor + 100 > len(payload):
                break
            
            record_view = memoryview(payload)[cursor : cursor + 100]
            
            # Extract required fields
            current_sfn_sf = struct.unpack('<H', record_view[0:2])[0]
            pusch_tb_size = struct.unpack('<H', record_view[8:10])[0]
            byte_for_rv = record_view[3]
            redund_ver = (byte_for_rv & 0x30) >> 4
            
            record_data = {
                "current_sfn_sf": current_sfn_sf,
                "redund_ver": redund_ver,
                "pusch_tb_size": pusch_tb_size
            }
            parsed_records.append(record_data)
            
            cursor += 100
            
        return parsed_records
    
    def buffer_b064_data(self, records):
        """Buffer B064 data for batch writing"""
        for record in records:
            line = "{}\t{}\t{}\t{}\t{}".format(
                record['current_sfn_sf'],
                record['lcg_0'],
                record['lcg_1'],
                record['lcg_2'],
                record['lcg_3']
            )
            self.b064_buffer.append(line)
    
    def buffer_b16c_data(self, records):
        """Buffer B16C data for batch writing"""
        for record in records:
            line = "{}\t{}\t{}\t{}\t{}".format(
                record['current_sfn_sf'],
                record['num_rbs'],
                record['tbs_index'],
                record['mcs_index'],
                record['redund_ver']
            )
            self.b16c_buffer.append(line)
    
    def buffer_b139_data(self, records):
        """Buffer B139 data for batch writing"""
        for record in records:
            line = "{}\t{}\t{}".format(
                record['current_sfn_sf'],
                record['redund_ver'],
                record['pusch_tb_size']
            )
            self.b139_buffer.append(line)
    
    def write_buffered_data(self):
        """Write all buffered data to files"""
        # Write B064 data
        if self.b064_buffer:
            with open(self.b064_file, 'a') as f:
                for line in self.b064_buffer:
                    f.write(line + "\n")
            print("Wrote {} B064 records".format(len(self.b064_buffer)))
            self.b064_buffer.clear()
        
        # Write B16C data
        if self.b16c_buffer:
            with open(self.b16c_file, 'a') as f:
                for line in self.b16c_buffer:
                    f.write(line + "\n")
            print("Wrote {} B16C records".format(len(self.b16c_buffer)))
            self.b16c_buffer.clear()
        
        # Write B139 data
        if self.b139_buffer:
            with open(self.b139_file, 'a') as f:
                for line in self.b139_buffer:
                    f.write(line + "\n")
            print("Wrote {} B139 records".format(len(self.b139_buffer)))
            self.b139_buffer.clear()
    
    def parse_and_log(self, hdlc_stream):
        """Parse HDLC data stream and extract log data"""
        potential_frames = hdlc_stream.split(b'\x7e')
        
        for frame_data in potential_frames:
            if not frame_data: 
                continue
            
            decoded_payload = HDLC.decode(frame_data + b'\x7e')
            if decoded_payload is None: 
                continue
            
            # Check for valid DIAG packet
            if not decoded_payload.startswith(b'\x98\x01\x00\x00\x01\x00\x00\x00'):
                continue
            
            data = decoded_payload[12:]
            if len(data) < 12: 
                continue
            
            msg_len, logcode, timestamp = struct.unpack('<HHQ', data[:12])
            payload = data[12 : 12 + msg_len]
            
            # Process based on logcode
            if logcode == 0xB064:
                records = self.decode_b064_payload(payload)
                if records:
                    self.buffer_b064_data(records)
            elif logcode == 0xB16C:
                records = self.decode_b16c_payload(payload)
                if records:
                    self.buffer_b16c_data(records)
            elif logcode == 0xB139:
                records = self.decode_b139_payload(payload)
                if records:
                    self.buffer_b139_data(records)
        
        # Write data periodically
        total_buffer_size = len(self.b064_buffer) + len(self.b16c_buffer) + len(self.b139_buffer)
        if total_buffer_size > 50:
            self.write_buffered_data()

def drain_buffer_thread():
    """Thread function for socket mode drain"""
    global drain_thread_running, client_socket_global, client_socket_lock
    
    print("Drain buffer thread started")
    drain_count = 0
    
    while drain_thread_running:
        try:
            with client_socket_lock:
                if client_socket_global and client_socket_global.fileno() != -1:
                    client_socket_global.sendall(DRAIN_BUFFER_COMMAND)
                    drain_count += 1
                    
                    if drain_count % 10000 == 0:
                        print("Sent {} drain commands".format(drain_count))
            
            time.sleep(0.0001)
            
        except Exception as e:
            print("Error in drain thread: {}".format(e))
            time.sleep(0.1)
    
    print("Drain buffer thread stopped")

# Connection parameters
HOST = '127.0.0.1'
PORT = 43555

# Initialization messages
INIT_MESSAGES = [
    b'\x1d\x1c\x3b\x7e', b'\x00\x78\xf0\x7e', b'\x7c\x93\x49\x7e',
    b'\x1c\x95\x2a\x7e', b'\x0c\x14\x3a\x7e', b'\x63\xe5\xa1\x7e',
    b'\x4b\x0f\x00\x00\xbb\x60\x7e', b'\x4b\x09\x00\x00\x62\xb6\x7e',
    b'\x4b\x08\x00\x00\xbe\xec\x7e', b'\x4b\x08\x01\x00\x66\xf5\x7e',
    b'\x4b\x04\x00\x00\x1d\x49\x7e', b'\x4b\x04\x0f\x00\xd5\xca\x7e',
    b'\x73\x00\x00\x00\x00\x00\x00\x00\xda\x81\x7e',
]
FINAL_MESSAGE = b'\x60\x00\x12\x6a\x7e'
DEFAULT_LOGCODES = [0xB16C, 0xB064, 0xB139]

def generate_logcode_command(logcodes):
    """Generate logcode subscription command"""
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
    """Send message and receive response"""
    print("Sending message ({} bytes)".format(len(message)))
    sock.sendall(message)
    time.sleep(0.1)
    try:
        sock.settimeout(1)
        response = sock.recv(16384)
        print("Received response ({} bytes)".format(len(response)))
        return response
    except socket.timeout:
        print("Receive timeout")
        return None

def main():
    global drain_thread_running, client_socket_global, client_socket_lock, current_mode
    
    # Initialize thread lock
    client_socket_lock = threading.Lock()
    
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket_global = client_socket
    parser = SimplifiedDiagParser()
    
    drain_thread = None
    
    try:
        print("Connecting to {}:{}...".format(HOST, PORT))
        client_socket.connect((HOST, PORT))
        print("Connection successful!")
        
        # Enable TCP_NODELAY
        client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        
        # Receive welcome message
        welcome_bytes = client_socket.recv(1024)
        welcome_message = welcome_bytes.decode('utf-8', errors='ignore').strip()
        print("Server: {}".format(welcome_message))
        
        # Detect mode
        if "Socket mode" in welcome_message:
            current_mode = OperatingMode.SOCKET
            print("[INFO] SOCKET mode detected")
        else:
            current_mode = OperatingMode.LEGACY
            print("[INFO] LEGACY mode detected")
        
        # Send initialization messages
        print("\nSending initialization messages...")
        
        # Socket mode specific init
        if current_mode == OperatingMode.SOCKET:
            socket_init = [
                b'\x28\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x40\x78\x7d\x01',
                b'\x29\x00\x00\x00\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00',
                b'\x07\x00\x00\x00\x05\x00\x00\x00\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\xb6\x78\x00\x00',
                b'\x23\x00\x00\x00\x00\x00\x00\x00',
            ]
            for msg in socket_init:
                client_socket.sendall(msg)
                time.sleep(0.1)
        
        # Standard init messages
        for message in INIT_MESSAGES:
            send_message(client_socket, message)
            time.sleep(0.2)
        
        # Send logcode subscription
        print("\nSubscribing to logcodes...")
        command = generate_logcode_command(DEFAULT_LOGCODES)
        if command:
            send_message(client_socket, command)
            send_message(client_socket, FINAL_MESSAGE)
        
        # Start drain thread for socket mode
        if current_mode == OperatingMode.SOCKET:
            print("\nStarting drain thread...")
            drain_thread_running = True
            drain_thread = threading.Thread(target=drain_buffer_thread, daemon=True)
            drain_thread.start()
        
        print("\nMonitoring started. Press Ctrl-C to exit.")
        print("Output files:")
        print("  - b064_bsr_data.txt: BSR buffer status data")
        print("  - b16c_grant_data.txt: UL grant information")
        print("  - b139_pusch_data.txt: PUSCH transmission data")
        print("")
        
        receive_buffer = b''
        
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
                    # Extract timestamp (not used in simplified version)
                    ts_bridge = struct.unpack('<d', receive_buffer[:header_size])[0]
                    
                    remaining_data = receive_buffer[header_size:]
                    
                    if len(remaining_data) > 12:
                        # Remove DIAG header
                        first_frame_data = remaining_data[12:]
                        hdlc_data_stream = b''
                        
                        if b'\x7e' in first_frame_data:
                            parts = first_frame_data.split(b'\x7e')
                            
                            if len(parts[0]) > 0:
                                hdlc_data_stream += parts[0] + b'\x7e'
                            
                            for i in range(1, len(parts)):
                                frame_part = parts[i]
                                if len(frame_part) > 20:
                                    frame_payload = frame_part[20:]
                                    if len(frame_payload) > 0:
                                        hdlc_data_stream += frame_payload + b'\x7e'
                                elif len(frame_part) > 0:
                                    hdlc_data_stream += frame_part + b'\x7e'
                        else:
                            hdlc_data_stream = first_frame_data + b'\x7e'
                        
                        if hdlc_data_stream:
                            parser.parse_and_log(hdlc_data_stream)
                    
                    receive_buffer = b''
                    break
                    
            except socket.timeout:
                continue
            except socket.error as e:
                print("Socket error: {}".format(e))
                break
                
    except KeyboardInterrupt:
        print("\nStopping...")
    except Exception as e:
        print("Error: {}".format(e))
    finally:
        # Write remaining buffered data
        parser.write_buffered_data()
        
        # Stop drain thread
        if drain_thread_running:
            drain_thread_running = False
            if drain_thread:
                drain_thread.join(timeout=2.0)
        
        # Close socket
        with client_socket_lock:
            client_socket.close()
            client_socket_global = None
        
        print("Disconnected")

if __name__ == "__main__":
    main()
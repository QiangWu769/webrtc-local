# -*- coding: utf-8 -*-
import socket
import time
from datetime import datetime, timedelta, timezone
import sys
import struct
import os
import threading
import errno
from hdlc import HDLC

# Note: Use time.clock_gettime(time.CLOCK_REALTIME) instead of time.time()
# Ensure using the same clock source as C code and other Python components for consistent time measurement
#
# Timestamp description:
# - RAN event timestamp: Hardware clock format (based on 1980, 52.4MHz tick frequency)
# - Bridge timestamp: Unix timestamp format (seconds since 1970)
# - Python timestamp: Unix timestamp format (CLOCK_REALTIME)
# RAN timestamps must be converted to Unix format for correct latency calculation

# Define operating mode enumeration
class OperatingMode:
    UNKNOWN = "unknown"
    LEGACY = "legacy"  # Drain handled by C bridge, has timestamp headers
    SOCKET = "socket"  # Drain handled by Python, no timestamp headers

# Global variables for mode detection and drain control
current_mode = OperatingMode.UNKNOWN
drain_thread_running = False
client_socket_lock = None  # Will be initialized in main()
client_socket_global = None  # Will be initialized in main()
fatal_error_occurred = False  # Flag to indicate a fatal error occurred

# Drain buffer command for socket mode
DRAIN_BUFFER_COMMAND = b'\x24\x00\x00\x00\x00\x00\x00\x00' 

# Global variable for raw TCP data logging
raw_tcp_file = None
raw_tcp_counter = 0

def log_all_tcp_data(data, timestamp):
    """Log ALL raw TCP data to a separate file for debugging"""
    global raw_tcp_file, raw_tcp_counter
    
    if raw_tcp_file is None:
        raw_tcp_file = open('all_tcp_raw_data.txt', 'a+')
        raw_tcp_file.write("\n\n========== NEW SESSION STARTED AT {} ==========\n".format(
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    
    try:
        raw_tcp_counter += 1
        raw_tcp_file.write("\n--- TCP Packet #{} at {} ---\n".format(raw_tcp_counter, timestamp))
        raw_tcp_file.write("Length: {} bytes\n".format(len(data)))
        
        # Write hex dump in rows of 16 bytes
        hex_lines = []
        for i in range(0, len(data), 16):
            hex_part = ' '.join('{:02X}'.format(b) for b in data[i:i+16])
            ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data[i:i+16])
            hex_lines.append("{:04X}  {:48s}  |{}|".format(i, hex_part, ascii_part))
        
        raw_tcp_file.write('\n'.join(hex_lines) + '\n')
        raw_tcp_file.flush()  # Ensure data is written immediately
        
    except Exception as e:
        print("Error writing to all_tcp_raw_data.txt: {}".format(e))

def convert_endianess(data, index, length):
    """Swaps bytes in-place for a given length at a specific index."""
    if length == 2:
        data[index], data[index+1] = data[index+1], data[index]
    elif length == 4:
        data[index], data[index+1], data[index+2], data[index+3] = \
        data[index+3], data[index+2], data[index+1], data[index]

def convert_S_H_B064_no_asn(data, index_obj):
    """Convert S_H header for B064 - skips 4 bytes"""
    index_obj['i'] += 4

def convert_Subpkt_H_B064_no_asn(data, index_obj):
    """Convert Subpkt_H header for B064 with byte swapping"""
    start_pos = index_obj['i']
    convert_endianess(data, start_pos + 2, 2)
    index_obj['i'] += 5

def convert_Sample_H_B064_no_asn(data, index_obj):
    """Convert Sample_H header for B064 with multiple byte swaps"""
    start_pos = index_obj['i']
    convert_endianess(data, start_pos + 4, 2)
    convert_endianess(data, start_pos + 6, 2)
    convert_endianess(data, start_pos + 9, 2)
    index_obj['i'] += 14

def convert_B16C_v49_S_H_no_asn(data, index_obj):
    index_obj['i'] += 1
    convert_endianess(data, index_obj['i'], 2)
    index_obj['i'] = 4 


def log_raw_tcp_data(raw_data, ts_bridge_read, ts_python_recv):
    """Log raw data after timestamp removal (but before DIAG header skip) to a file for analysis"""
    try:
        with open('raw_tcp_data.txt', 'a+') as fp:
            # Write timestamp info
            fp.write("\n--- Raw TCP Data at Bridge_TS: {}, Python_TS: {} ---\n".format(ts_bridge_read, ts_python_recv))
            fp.write("Data length: {} bytes\n".format(len(raw_data)))
            
            # Write first 32 bytes preview (includes 12-byte DIAG header)
            if len(raw_data) >= 32:
                preview_hex = ' '.join('{:02X}'.format(b) for b in raw_data[:32])
                fp.write("First 32 bytes: {}\n".format(preview_hex))
            
            # Write complete hex dump
            full_hex = ' '.join('{:02X}'.format(b) for b in raw_data)
            fp.write("Full data (including 12-byte DIAG header):\n{}\n".format(full_hex))
            
    except IOError as e:
        print("Error writing to raw_tcp_data.txt: {}".format(e))

class DiagDataParser:
    def __init__(self, report_filename="diag_report.txt"):
        self._report_filename = report_filename
        self._header_written = False
        self._data_buffer = {}  # Buffer to store data by timestamp
        self._record_counter = {}  # Counter for records with same timestamp
        self._timestamp_logged = False  # Flag to track if device timestamp is logged
        self._baseline_timestamp = None  # First row's unix timestamp for cellular time calculation
        self._baseline_sysfn = None  # First row's SysFN
        self._baseline_subfn = None  # First row's SubFN
        
        # Initialize report file with header at startup
        self._ensure_header()
        
        self.PER_SECOND = 52428800.0 
        self.EPOCH = datetime(1980, 1, 6, 0, 0, 0, tzinfo=timezone.utc)
        
        # Maps for B139 decoding
        self.CARRIER_INDEX_MAP = {0: "pcc", 1: "scc1", 2: "scc2"}
        self.RETX_INDEX_MAP = {
            0: "First", 1: "Second", 2: "Third", 3: "Fourth",
            4: "Fifth", 5: "Sixth", 6: "Seventh", 7: "Eighth"
        }
        
        # RIV Width to N_UL_RB lookup table for v49 decoding
        self.RIV_WIDTH_TO_N_UL_RB = {
            9: 25,
            11: 50,
            12: 75,
            13: 100
        }
        
    def convert_timestamp(self, ts):
        if ts == 0: return "N/A"
        try:
            seconds_since_epoch = ts / self.PER_SECOND
            utc_time = self.EPOCH + timedelta(seconds=seconds_since_epoch)
            local_time = utc_time.astimezone(None)
            return local_time.strftime('%Y-%m-%d %H:%M:%S.%f')
        except (OverflowError, ValueError):
            return str(ts)
    
    def convert_timestamp_to_unix(self, ts):
        """Convert diag timestamp to Unix timestamp"""
        if ts == 0: 
            return 0.0
        try:
            seconds_since_epoch = ts / self.PER_SECOND
            utc_time = self.EPOCH + timedelta(seconds=seconds_since_epoch)
            return utc_time.timestamp()
        except (OverflowError, ValueError):
            return 0.0
    
    def decode_riv(self, riv_value, n_ul_rb):
        """
        Decodes the RIV value to find the start RB and number of RBs.
        Based on 3GPP TS 36.213 for Uplink Resource Allocation Type 0.
        This logic has been verified against commercial log decoders.
        """
        if n_ul_rb <= 0:
            return {'num_rbs': -1, 'start_rb': -1}

        # 3GPP formula
        num_rbs = (riv_value // n_ul_rb) + 1
        start_rb = riv_value % n_ul_rb

        # Validate that allocation is valid (start RB + count cannot exceed total bandwidth)
        if start_rb + num_rbs > n_ul_rb:
            return {'num_rbs': -1, 'start_rb': -1}  # Return -1 if decoding fails

        return {'num_rbs': num_rbs, 'start_rb': start_rb}
    
    def _decode_b16c_v48(self, payload, timestamp, logcode):
        parsed_records = []
        if len(payload) < 4: return []
        version = payload[0]
        num_records = (payload[1] & 0xFC) >> 2
        readable_timestamp = self.convert_timestamp(timestamp)
        payload_view = memoryview(payload)
        cursor = 4
        for _ in range(num_records):
            if cursor + 128 > len(payload_view): break
            h1, h2 = payload_view[cursor], payload_view[cursor + 1]
            subfn = (h2 & 0x3C) >> 2
            sysfn = ((h2 & 0x03) << 8) | h1
            num_ul_grant = (h2 & 0xC0) >> 6
            cursor += 2
            if num_ul_grant != 0:
                ul_grant_view = payload_view[cursor : cursor + 126]
                mcs_index = (ul_grant_view[5] & 0xF8) >> 3
                redundancy_version = (ul_grant_view[5] & 0x06) >> 1
                tbs_index = ul_grant_view[6] & 0x3F
                num_of_resource_blocks = ul_grant_view[8] & 0x7F
                record_data = {
                    "logcode": logcode,
                    "timestamp": timestamp, 
                    "readable_timestamp": readable_timestamp,
                    "version": version,
                    "subfn": subfn, 
                    "sysfn": sysfn, 
                    "mcs_index": mcs_index,
                    "redundancy_version": redundancy_version, 
                    "tbs_index": tbs_index,
                    "num_of_resource_blocks": num_of_resource_blocks, 
                    "is_ul_grant": 1
                }
                parsed_records.append(record_data)
            cursor += 126
        return parsed_records
    
    def _decode_b16c_v49(self, payload, timestamp, logcode):
        """
        Final, robust Python implementation with correct hybrid parsing logic for Record Headers.
        This version correctly handles records with both UL and DL grants.
        """
        parsed_records = []
        if len(payload) < 4:
            return []

        data = bytearray(payload)
        index_obj = {'i': 0}
        
        version = data[0]
        readable_timestamp = self.convert_timestamp(timestamp)
        
        # --- S_H (Standard Header) ---
        start_S_H = index_obj['i']
        convert_B16C_v49_S_H_no_asn(data, index_obj)
        
        num_record = ((data[start_S_H+1] & 0x07) << 2 | (data[start_S_H+2] & 0xC0) >> 6)
        
        for i in range(num_record):
            if index_obj['i'] + 4 > len(data):
                break
            
            start_record = index_obj['i']
            
            # --- CORRECTED HYBRID LOGIC ---
            # 1. Read the raw header first
            raw_record_header = data[start_record:start_record+4]
            
            # 2. Calculate num_dl_grant from the RAW header's 3rd byte (index 2)
            num_dl_grant = (raw_record_header[2] & 0x06) >> 1
            
            # 3. Now, create a reversed copy for the other fields
            reversed_record_header = bytearray(raw_record_header)
            convert_endianess(reversed_record_header, 0, 4)
            
            # 4. Calculate remaining fields from the REVERSED header
            num_ul_grant = ((reversed_record_header[1] & 0x01) << 2) | ((reversed_record_header[2] & 0xC0) >> 6)
            subfn = (reversed_record_header[2] & 0x3C) >> 2
            sysfn = ((reversed_record_header[2] & 0x03) << 8) | (reversed_record_header[3])
            
            index_obj['i'] += 4  # Advance index past the header
            
            # --- Use two separate 'if' statements for robust parsing ---
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
                
                record_data = {
                    "logcode": logcode, 
                    "timestamp": timestamp, 
                    "readable_timestamp": readable_timestamp,
                    "version": version, 
                    "subfn": subfn, 
                    "sysfn": sysfn, 
                    "mcs_index": mcs_index,
                    "tbs_index": tbs_index,
                    "num_of_resource_blocks": num_of_resource_blocks,
                    # Add fields for data structure compatibility
                    "start_of_resource_block": -1, 
                    "riv_width": -1, 
                    "riv_value": -1,
                    "is_ul_grant": 1
                }
                parsed_records.append(record_data)
                index_obj['i'] += 16

            if num_dl_grant > 0:
                if index_obj['i'] + 8 > len(data): 
                    break
                index_obj['i'] += 8
        
        return parsed_records
    
    def decode_b16c_payload(self, payload, timestamp, logcode):
        """
        Central dispatcher for B16C decoding based on version.
        Routes to appropriate version-specific decoder.
        """
        if len(payload) < 1:
            return []
            
        # Extract version from first byte
        version = payload[0]
        
        # Route to appropriate decoder based on version
        if version == 48:
            return self._decode_b16c_v48(payload, timestamp, logcode)
        elif version == 49:
            return self._decode_b16c_v49(payload, timestamp, logcode)
        else:
            # Handle unknown versions gracefully
            print("[WARNING] Unsupported B16C version detected: {}".format(version))
            return []
    
    def _decode_b139_v161(self, payload, timestamp, logcode):
        """
        Decode B139 payload for version 161 (PUSCH transmission info)
        (CORRECTED based on reverse-engineering against ground truth log)
        """
        parsed_records = []
        if len(payload) < 8:
            return []
        
        # Parse S_H header (8 bytes) - This part is correct
        version = payload[0]
        num_of_records = (payload[2] & 0xFE) >> 1
        payload_view = memoryview(payload)
        dispatch_sfn_sf = struct.unpack('<H', payload_view[4:6])[0]
        
        readable_timestamp = self.convert_timestamp(timestamp)
        cursor = 8  # Skip S_H header
        
        for _ in range(num_of_records):
            if cursor + 100 > len(payload_view):  # Each record is 100 bytes
                break
                
            # Parse record
            record_view = payload_view[cursor : cursor + 100]
            
            # Extract fields using direct, correct logic
            current_sfn_sf = struct.unpack('<H', record_view[0:2])[0]
            redund_ver = (record_view[2] & 0x30) >> 4
            re_tx_index = ((record_view[2] & 0x0F) << 1) | ((record_view[3] & 0x80) >> 7)
            ul_carrier_index = record_view[3] & 0x03
            
            # !!!!!!!!!!! THIS IS THE CRITICAL FIX !!!!!!!!!!!
            # The C code's cross-byte logic was wrong. The correct value is simply the byte at index 11.
            num_of_rb = record_view[11]
            
            pusch_tb_size = struct.unpack('<H', record_view[8:10])[0]
            dl_carrier_index = (record_view[7] & 0x06) >> 1
            
            # Convert indices to strings
            re_tx_index_str = self.RETX_INDEX_MAP.get(re_tx_index, "invalid")
            ul_carrier_str = self.CARRIER_INDEX_MAP.get(ul_carrier_index, "invalid")
            dl_carrier_str = self.CARRIER_INDEX_MAP.get(dl_carrier_index, "invalid")
            
            record_data = {
                "logcode": logcode,
                "timestamp": timestamp,
                "readable_timestamp": readable_timestamp,
                "version": version,
                "dispatch_sfn_sf": dispatch_sfn_sf,
                "current_sfn_sf": current_sfn_sf,
                "redund_ver": redund_ver,
                "re_tx_index": re_tx_index,
                "re_tx_index_str": re_tx_index_str,
                "ul_carrier_index": ul_carrier_index,
                "ul_carrier_str": ul_carrier_str,
                "num_of_rb": num_of_rb,
                "pusch_tb_size": pusch_tb_size,
                "dl_carrier_index": dl_carrier_index,
                "dl_carrier_str": dl_carrier_str
            }
            parsed_records.append(record_data)
            cursor += 100
            
        return parsed_records
    
    def decode_b139_payload(self, payload, timestamp, logcode):
        """
        Central dispatcher for B139 decoding based on version.
        Routes to appropriate version-specific decoder.
        """
        if len(payload) < 1:
            return []
            
        # Extract version from first byte
        version = payload[0]
        
        # Route to appropriate decoder based on version
        if version == 161:
            return self._decode_b139_v161(payload, timestamp, logcode)
        else:
            # Handle unknown versions gracefully
            print("[WARNING] Unsupported B139 version detected: {}".format(version))
            return []


    def buffer_data_with_bridge_ts(self, results, logcode, ts_bridge_read, ts_python_recv):
        """Buffer data with bridge timestamp and local unix time for latency analysis"""
        if not results: 
            return
            
        for record in results:
            timestamp = self.convert_timestamp(record['timestamp'])
            ts_ran_event = self.convert_timestamp_to_unix(record['timestamp'])  # Convert to Unix timestamp
            
            # Calculate latency (RAN timestamp converted to Unix timestamp, consistent with bridge timestamp baseline)
            pipeline_latency_ms = 0.0
            if ts_ran_event > 0:
                pipeline_latency_ms = (ts_bridge_read - ts_ran_event) * 1000
            
            # For B139, use current_sfn_sf directly (already in millisecond timeline format)
            if logcode == 0xB139:
                current_sfn_sf = record['current_sfn_sf']
                unique_key = "{}_{}_{}".format(timestamp, current_sfn_sf, record.get('re_tx_index', 0))
            else:
                # For B064 and B16C, calculate millisecond timeline value
                # Formula: sysfn * 10 + subfn (each SysFN = 10ms, each SubFN = 1ms)
                subfn = record['subfn']
                sysfn = record['sysfn']
                current_sfn_sf = sysfn * 10 + subfn  # Convert to millisecond timeline
                unique_key = "{}_{}_{}".format(timestamp, current_sfn_sf, 0)
            
            if unique_key not in self._data_buffer:
                self._data_buffer[unique_key] = {
                    'timestamp': timestamp,
                    'unix_timestamp': ts_ran_event,
                    'current_sfn_sf': current_sfn_sf,
                    'lcg_0': '-', 
                    'lcg_1': '-', 
                    'lcg_2': '-', 
                    'lcg_3': '-', 
                    'num_rbs': '-',
                    'tbs_index': -1,
                    'mcs_index': '-',
                    'pusch_tb_size': '-',
                    'redund_ver': '-',
                    'bridge_timestamp': ts_bridge_read,
                    'python_recv_timestamp': ts_python_recv
                }
            else:
                # Update timestamp information
                self._data_buffer[unique_key]['unix_timestamp'] = ts_ran_event
                self._data_buffer[unique_key]['bridge_timestamp'] = ts_bridge_read
                self._data_buffer[unique_key]['python_recv_timestamp'] = ts_python_recv
            
            if logcode == 0xB064:
                # Store the buffer size values (LCG values)
                self._data_buffer[unique_key]['lcg_0'] = record['buffer_size'][0]
                self._data_buffer[unique_key]['lcg_1'] = record['buffer_size'][1]
                self._data_buffer[unique_key]['lcg_2'] = record['buffer_size'][2]
                self._data_buffer[unique_key]['lcg_3'] = record['buffer_size'][3]
            
            elif logcode == 0xB16C:
                # Store the number of resource blocks and TBS index
                self._data_buffer[unique_key]['num_rbs'] = record['num_of_resource_blocks']
                self._data_buffer[unique_key]['tbs_index'] = record['tbs_index']
                self._data_buffer[unique_key]['mcs_index'] = record.get('mcs_index', '-')
            
            elif logcode == 0xB139:
                # Store PUSCH transmission info
                self._data_buffer[unique_key]['redund_ver'] = record['redund_ver']
                self._data_buffer[unique_key]['pusch_tb_size'] = record['pusch_tb_size']
                # Store num_of_rb for B139
                self._data_buffer[unique_key]['num_rbs'] = record.get('num_of_rb', '-')
        
        # Write buffered data to file when it exceeds a certain size
        if len(self._data_buffer) > 100:
            self.write_buffered_data()

    def write_buffered_data(self):
        """Write the buffered data to the report file with latency analysis"""
        if not self._data_buffer:
            return
            
        try:
            # Check if we need to write header
            file_exists = os.path.exists(self._report_filename)
            write_header = not file_exists or (file_exists and os.path.getsize(self._report_filename) == 0)
            
            with open(self._report_filename, 'a', encoding='utf-8') as f:
                # Write header if needed
                if not self._header_written and write_header:
                    header = ["RAN_Event_Unix_Timestamp", "Bridge_Read_Timestamp", "Python_Recv_Timestamp", "Cellular_Precise_Timestamp", "Current_SFN_SF", "Pipeline_Latency_ms", "Bridge_Python_Latency_ms",
                            "LCG_0", "LCG_1", "LCG_2", "LCG_3", "Num_RBs", "TBS_Index", 
                            "MCS_Index",
                            "Redund_Ver", "PUSCH_TB_Size"]
                    f.write("\t".join(header) + "\n")
                    self._header_written = True
                
                # Group by timestamp for easier reading
                timestamp_groups = {}
                for unique_key, data in self._data_buffer.items():
                    timestamp = data['timestamp']
                    if timestamp not in timestamp_groups:
                        timestamp_groups[timestamp] = []
                    timestamp_groups[timestamp].append(data)
                
                # Write data sorted by timestamp
                for timestamp, records in sorted(timestamp_groups.items()):
                    for data in sorted(records, key=lambda x: x.get('current_sfn_sf', 0)):
                        # Calculate cellular precise timestamp based on Python_Recv_Timestamp (column 3)
                        python_recv_ts = data.get('python_recv_timestamp', 0.0)
                        # Extract subfn and sysfn from current_sfn_sf (millisecond timeline) for cellular timestamp calculation
                        current_sfn_sf = data.get('current_sfn_sf', 0)
                        if isinstance(current_sfn_sf, int):
                            # Reverse calculation: current_sfn_sf = sysfn * 10 + subfn
                            sysfn = current_sfn_sf // 10  # Integer division to get SysFN
                            subfn = current_sfn_sf % 10   # Remainder to get SubFN
                        else:
                            sysfn = 0
                            subfn = 0
                        cellular_precise_ts = self._calculate_cellular_timestamp(sysfn, subfn, python_recv_ts)
                        
                        # Calculate pipeline latency (Bridge_Read - RAN_Event)
                        ran_unix_ts = data.get('unix_timestamp', 0.0)
                        bridge_ts = data['bridge_timestamp']
                        pipeline_latency_ms = 0.0
                        if ran_unix_ts > 0 and bridge_ts > 0:
                            pipeline_latency_ms = (bridge_ts - ran_unix_ts) * 1000
                        
                        # Calculate Bridge to Python latency (Python_Recv - Bridge_Read)
                        bridge_python_latency_ms = 0.0
                        if bridge_ts > 0 and python_recv_ts > 0:
                            bridge_python_latency_ms = (python_recv_ts - bridge_ts) * 1000
                        
                        line = "{:.6f}\t{:.6f}\t{:.6f}\t{:.6f}\t{}\t{:.3f}\t{:.3f}\t".format(
                            ran_unix_ts,
                            bridge_ts,
                            python_recv_ts,
                            cellular_precise_ts,
                            data.get('current_sfn_sf', '-'),
                            pipeline_latency_ms,
                            bridge_python_latency_ms
                        )
                        line += "{}\t{}\t{}\t{}\t".format(data['lcg_0'], data['lcg_1'], data['lcg_2'], data['lcg_3'])
                        line += "{}\t{}\t".format(data.get('num_rbs', '-'), data['tbs_index'])
                        line += "{}\t".format(data.get('mcs_index', '-'))
                        line += "{}\t{}".format(data.get('redund_ver', '-'), data.get('pusch_tb_size', '-'))
                        f.write(line + "\n")
            
            print("Successfully wrote {} records to file".format(len(self._data_buffer)))
            self._data_buffer.clear()  # Clear the buffer
        except IOError as e:
            print("Error writing to file: {}".format(e))

    def _write_timestamp_header(self, timestamp_comment):
        """Write device timestamp as first line in the output file"""
        try:
            # Read existing content if file exists
            existing_content = ""
            if os.path.exists(self._report_filename):
                with open(self._report_filename, 'r') as f:
                    existing_content = f.read()
            
            # Write timestamp comment as first line, then existing content
            with open(self._report_filename, 'w') as f:
                f.write(timestamp_comment + '\n')
                if existing_content:
                    f.write(existing_content)
            
            print("[INFO] Device timestamp written to {}".format(self._report_filename))
            
        except IOError as e:
            print("Error writing timestamp header: {}".format(e))

    def decode_b064_payload(self, payload, timestamp=None, logcode=None):
        """
        Decode B064 payload by precisely simulating the C code logic,
        including all pre-processing and byte swapping.
        """
        results = []
        if len(payload) < 4:
            return results
            
        data = bytearray(payload)
        index_obj = {'i': 0}
        
        # --- S_H (Standard Header) ---
        start_S_H = index_obj['i']
        convert_S_H_B064_no_asn(data, index_obj)
        num_subpkt = data[start_S_H]
        
        for i in range(num_subpkt):
            if index_obj['i'] + 5 > len(data): 
                break
                
            # --- Subpacket Header ---
            start_Subpkt_H = index_obj['i']
            # Work on a copy of the header for parsing
            subpkt_header = bytearray(data[start_Subpkt_H : start_Subpkt_H + 5])
            convert_Subpkt_H_B064_no_asn(subpkt_header, {'i': 0})
            num_samples = subpkt_header[4]
            index_obj['i'] += 5
            
            for j in range(num_samples):
                if index_obj['i'] + 14 > len(data): 
                    break
                    
                # --- Sample Header ---
                start_Sample_H = index_obj['i']
                sample_header = bytearray(data[start_Sample_H : start_Sample_H + 14])
                convert_Sample_H_B064_no_asn(sample_header, {'i': 0})
                
                # Extract fields after byte swapping
                sysfn = (sample_header[4] << 4) | ((sample_header[5] & 0xF0) >> 4)
                subfn = sample_header[5] & 0x0F
                grant_bytes = (sample_header[6] << 8) | sample_header[7]
                padding = (sample_header[9] << 8) | sample_header[10]
                bsr_event = sample_header[11] & 0x03
                bsr_trig = sample_header[12] & 0x07
                hdrlen = sample_header[13]
                
                index_obj['i'] += 14
                
                # --- Element Parsing ---
                buffer_size = [-1, -1, -1, -1]  # Initialize as invalid
                lcg = -1
                bsr_type = 0
                has_bsr_data = False  # Track if we found actual BSR data
                
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
                            buffer_size = [0, 0, 0, 0]  # Reset to valid zeros when BSR found
                        elif LCID_data == 30: 
                            bsr_type = 2  # Long BSR
                            has_bsr_data = True
                            buffer_size = [0, 0, 0, 0]  # Reset to valid zeros when BSR found
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
                            
                            # Match C code logic for bsr_type reset
                            if step + 1 > hdrlen:
                                bsr_type = 0
                            break
                        
                        step += 1
                    
                    index_obj['i'] += hdrlen
                
                # Only create a record if we found actual BSR data
                if has_bsr_data:
                    record = {
                        "logcode": logcode,
                        "timestamp": timestamp,
                        "subfn": subfn,
                        "sysfn": sysfn,
                        "grant_bytes": grant_bytes,
                        "padding": padding,
                        "bsr_event": bsr_event,
                        "bsr_type": bsr_type,
                        "lcg": lcg,
                        "bsr_trig": bsr_trig,
                        "buffer_size": buffer_size
                    }
                    results.append(record)
                
        return results

    def parse_and_log(self, hdlc_stream, ts_bridge_read=None, ts_python_recv=None):
        """Parse HDLC data stream with timestamps, calculate latency, and record local Unix timestamp"""
        # Log data entering parse_and_log function to tcp_and_parse_data.txt
        with open("tcp_and_parse_data.txt", "a") as logfile:
            logfile.write("\n=== Data Entering parse_and_log() at Python_TS: {:.6f} ===\n".format(ts_python_recv if ts_python_recv else 0))
            logfile.write("Bridge_TS: {:.6f}\n".format(ts_bridge_read if ts_bridge_read else 0))
            logfile.write("Data length: {} bytes\n".format(len(hdlc_stream)))
            logfile.write("Hex dump:\n")
            # Write hex dump
            for i in range(0, len(hdlc_stream), 16):
                hex_part = ' '.join('{:02X}'.format(b) for b in hdlc_stream[i:i+16])
                logfile.write("{:04X}  {}\n".format(i, hex_part))
        
        # New logging file for parse_and_log data with 98 header checking
        with open("parseandlog_data.txt", "a") as parse_log:
            parse_log.write("\n========== NEW parse_and_log() CALL AT {} ==========\n".format(
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            parse_log.write("Bridge_TS: {:.6f}, Python_TS: {:.6f}\n".format(
                ts_bridge_read if ts_bridge_read else 0, 
                ts_python_recv if ts_python_recv else 0))
            parse_log.write("Total HDLC stream length: {} bytes\n\n".format(len(hdlc_stream)))
        
        potential_frames = hdlc_stream.split(b'\x7e')
        frame_counter = 0
        # Open parseandlog_data.txt for detailed logging
        with open("parseandlog_data.txt", "a") as parse_log:
            for frame_data in potential_frames:
                if not frame_data: continue
                
                frame_counter += 1
                
                # Check if raw frame starts with 98 (before HDLC decode)
                raw_starts_with_98 = frame_data.startswith(b'\x98')
                
                # Log frame info to parseandlog_data.txt
                parse_log.write("--- Frame #{} ---\n".format(frame_counter))
                parse_log.write("Raw frame length: {} bytes\n".format(len(frame_data)))
                parse_log.write("Raw frame starts with 0x98: {}\n".format(raw_starts_with_98))
                if len(frame_data) >= 16:
                    parse_log.write("Raw frame first 16 bytes: {}\n".format(
                        ' '.join('{:02X}'.format(b) for b in frame_data[:16])))
                
                decoded_payload = HDLC.decode(frame_data + b'\x7e')
                if decoded_payload is None: 
                    parse_log.write("HDLC decode failed\n\n")
                    continue
                
                # Check if decoded payload starts with 98 01
                decoded_starts_with_9801 = decoded_payload.startswith(b'\x98\01\x00\x00\x01\x00\x00\x00')
                parse_log.write("Decoded payload length: {} bytes\n".format(len(decoded_payload)))
                parse_log.write("Decoded payload starts with 0x98 0x01: {}\n".format(decoded_starts_with_9801))
                
                if len(decoded_payload) >= 16:
                    parse_log.write("Decoded payload first 16 bytes: {}\n".format(
                        ' '.join('{:02X}'.format(b) for b in decoded_payload[:16])))
                
                # Log non-98-01 packets for analysis
                if not decoded_starts_with_9801:
                    parse_log.write("*** NON-98-01 PACKET - Logging to non_9801_packets.txt ***\n\n")
                    self._log_non_9801_packet(decoded_payload, ts_bridge_read, ts_python_recv, 
                                              frame_data, raw_starts_with_98)
                    continue
                
                parse_log.write("Processing as valid DIAG packet\n")
                
                data = decoded_payload[12:]
                if len(data) < 12: 
                    parse_log.write("Data after DIAG header too short, skipping\n\n")
                    continue
                
                msg_len, logcode, timestamp = struct.unpack('<HHQ', data[:12])
                payload = data[12 : 12 + msg_len]
                
                # Log packet details
                parse_log.write("Valid DIAG packet - Logcode: 0x{:04X}, Msg_len: {}, Timestamp: {}\n\n".format(
                    logcode, msg_len, timestamp))
                
                # Convert RAN event timestamp to Unix timestamp to maintain consistency with bridge timestamp
                ts_ran_event = self.convert_timestamp_to_unix(timestamp)
                
                # Calculate latency (RAN timestamp converted to Unix timestamp, consistent with bridge timestamp baseline)
                if ts_ran_event > 0 and ts_bridge_read is not None:  # Ensure timestamp is valid
                    diag_pipeline_latency_ms = (ts_bridge_read - ts_ran_event) * 1000
                    print("--- Latency Analysis ---")
                    print("T_ran_event: {}".format(ts_ran_event))
                    print("T_bridge_read: {}".format(ts_bridge_read))
                    print("Diag Pipeline Latency: {:.3f}ms".format(diag_pipeline_latency_ms))
                
                if logcode == 0xB16C:
                    results = self.decode_b16c_payload(payload, timestamp, logcode)  # Using central dispatcher
                    if results:
                        self.buffer_data_with_bridge_ts(results, logcode, ts_bridge_read, ts_python_recv)
                elif logcode == 0xB139:
                    results = self.decode_b139_payload(payload, timestamp, logcode)  # Using central dispatcher
                    if results:
                        self.buffer_data_with_bridge_ts(results, logcode, ts_bridge_read, ts_python_recv)
                elif logcode == 0xB064:
                    # Use the new C-style parsing for B064
                    b064_records = self.decode_b064_payload(payload, timestamp, logcode)
                    if b064_records:
                        self.buffer_data_with_bridge_ts(b064_records, logcode, ts_bridge_read, ts_python_recv)
        
        # Periodically write buffered data to file
        if len(self._data_buffer) > 50:
            self.write_buffered_data()



    def _log_non_9801_packet(self, decoded_payload, ts_bridge_read, ts_python_recv, 
                              raw_frame=None, raw_starts_with_98=False):
        """Log packets that don't start with 98 01 header for analysis"""
        try:
            with open('non_9801_packets.txt', 'a+') as fp:
                # Write timestamp info
                fp.write("\n--- Packet at Bridge_TS: {}, Python_TS: {} ---\n".format(ts_bridge_read, ts_python_recv))
                
                # Show if raw frame started with 98
                if raw_frame is not None:
                    fp.write("Raw HDLC frame starts with 98: {}\n".format(raw_starts_with_98))
                    if len(raw_frame) >= 8:
                        raw_header = raw_frame[:8].hex(' ', 1).upper()
                        fp.write("Raw frame header (first 8 bytes): {}\n".format(raw_header))
                
                # Write decoded packet info
                fp.write("Decoded packet length: {} bytes\n".format(len(decoded_payload)))
                
                # If packet has at least 8 bytes, show what the header actually is
                if len(decoded_payload) >= 8:
                    header_bytes = decoded_payload[:8].hex(' ', 1).upper()
                    fp.write("Decoded 8-byte header: {}\n".format(header_bytes))
                
                # Always write full hex dump (complete content)
                full_hex = decoded_payload.hex(' ', 1).upper()
                fp.write("Full decoded packet content:\n{}\n".format(full_hex))
                
                # Optionally show raw frame for comparison (first 32 bytes)
                if raw_frame is not None and len(raw_frame) <= 64:
                    raw_hex = raw_frame.hex(' ', 1).upper()
                    fp.write("Full raw HDLC frame (before decode):\n{}\n".format(raw_hex))
                
        except IOError as e:
            print("Error writing to non_9801_packets.txt: {}".format(e))
    
    
    def _ensure_header(self):
        """Ensure the report file has a header"""
        try:
            # Create new file with header or check if existing file needs header
            file_exists = os.path.exists(self._report_filename)
            needs_header = not file_exists
            
            if file_exists:
                # Check if file is empty or doesn't have header
                with open(self._report_filename, 'r', encoding='utf-8') as f:
                    first_line = f.readline().strip()
                    # Check if first line starts with expected header
                    needs_header = not first_line.startswith("RAN_Event_Unix_Timestamp")
            
            if needs_header:
                # Write header to new file or prepend to existing
                header = ["RAN_Event_Unix_Timestamp", "Bridge_Read_Timestamp", "Python_Recv_Timestamp", 
                        "Cellular_Precise_Timestamp", "Current_SFN_SF", "Pipeline_Latency_ms", "Bridge_Python_Latency_ms",
                        "LCG_0", "LCG_1", "LCG_2", "LCG_3", "Num_RBs", "TBS_Index", 
                        "MCS_Index",
                        "Redund_Ver", "PUSCH_TB_Size"]
                
                if file_exists:
                    # Read existing content
                    with open(self._report_filename, 'r', encoding='utf-8') as f:
                        existing_content = f.read()
                    # Write header + existing content
                    with open(self._report_filename, 'w', encoding='utf-8') as f:
                        f.write("\t".join(header) + "\n")
                        f.write(existing_content)
                else:
                    # Create new file with header
                    with open(self._report_filename, 'w', encoding='utf-8') as f:
                        f.write("\t".join(header) + "\n")
                
                self._header_written = True
                print("[INFO] Report file initialized with header: {}".format(self._report_filename))
            else:
                self._header_written = True  # Header already exists
                
        except IOError as e:
            print("Error ensuring header: {}".format(e))
    
    def _calculate_cellular_timestamp(self, current_sysfn, current_subfn, python_recv_timestamp):
        """Calculate precise cellular timestamp based on Python_Recv_Timestamp baseline and SysFN/SubFN
        
        Args:
            current_sysfn: Current System Frame Number (0-1023)
            current_subfn: Current Sub-Frame Number (0-9)
            python_recv_timestamp: Python receive timestamp (Unix time) for baseline setting
        
        Returns:
            Precise cellular timestamp calculated from baseline + cellular time difference
        """
        # Set baseline from first record if not set (using Python_Recv_Timestamp)
        if self._baseline_timestamp is None:
            self._baseline_timestamp = python_recv_timestamp  # Use Python_Recv_Timestamp as baseline
            self._baseline_sysfn = current_sysfn
            self._baseline_subfn = current_subfn
            return python_recv_timestamp
        
        # Calculate cellular time difference in milliseconds
        # SysFN: 0-1023 (10ms per frame), SubFN: 0-9 (1ms per subframe)
        baseline_cellular_ms = self._baseline_sysfn * 10 + self._baseline_subfn
        current_cellular_ms = current_sysfn * 10 + current_subfn
        
        # Handle SysFN wraparound (0-1023 cycle)
        cellular_diff_ms = current_cellular_ms - baseline_cellular_ms
        
        # If difference is negative, assume SysFN wrapped around
        if cellular_diff_ms < 0:
            # Add full SysFN cycle (1024 * 10ms = 10240ms)
            cellular_diff_ms += 10240
        
        # Calculate precise timestamp
        precise_timestamp = self._baseline_timestamp + (cellular_diff_ms / 1000.0)
        
        return precise_timestamp
    
    def __del__(self):
        """Ensure all buffered data is written when the parser is destroyed"""
        self.write_buffered_data()

def drain_buffer_thread():
    """Thread function that sends drain buffer command periodically for socket mode"""
    global drain_thread_running, client_socket_global, client_socket_lock, fatal_error_occurred
    
    print("Drain buffer thread started - sending drain commands periodically")
    drain_count = 0
    start_time = time.time()
    
    while drain_thread_running:
        try:
            # Send drain command with thread-safe socket access
            with client_socket_lock:
                if client_socket_global and client_socket_global.fileno() != -1:
                    client_socket_global.sendall(DRAIN_BUFFER_COMMAND)
                    drain_count += 1
                    
                    # Print stats every 10000 commands
                    if drain_count % 10000 == 0:
                        elapsed = time.time() - start_time
                        rate = drain_count / elapsed if elapsed > 0 else 0
                        print("Sent {} drain commands ({:.2f} commands/sec)".format(drain_count, rate))
            
            # Control the rate (adjust as needed)
            time.sleep(0.0001)  # ~10000 times per second
            
        except socket.error as e:
            if e.errno == errno.EPIPE or str(e).find("Broken pipe") >= 0:
                print("Error in drain thread: [Errno 32] Broken pipe")
                fatal_error_occurred = True
                break
            else:
                print("Error in drain thread: {}".format(e))
                time.sleep(0.1)
        except Exception as e:
            print("Error in drain thread: {}".format(e))
            time.sleep(0.1)
    
    print("Drain buffer thread stopped")

HOST = '127.0.0.1'
PORT = 43555
INIT_MESSAGES = [
    b'\x1d\x1c\x3b\x7e', b'\x00\x78\xf0\x7e', b'\x7c\x93\x49\x7e',
    b'\x1c\x95\x2a\x7e', b'\x0c\x14\x3a\x7e', b'\x63\xe5\xa1\x7e',
    b'\x4b\x0f\x00\x00\xbb\x60\x7e', b'\x4b\x09\x00\x00\x62\xb6\x7e',
    b'\x4b\x08\x00\x00\xbe\xec\x7e', b'\x4b\x08\x01\x00\x66\xf5\x7e',
    b'\x4b\x04\x00\x00\x1d\x49\x7e', b'\x4b\x04\x0f\x00\xd5\xca\x7e',
    b'\x73\x00\x00\x00\x00\x00\x00\x00\xda\x81\x7e',
]
FINAL_MESSAGE = b'\x60\x00\x12\x6a\x7e'
DEFAULT_LOGCODES = [0xB16C,0xB064]  # Added B139 for PUSCH transmission info
def generate_logcode_command(logcodes):
    item_ids = [code & 0xFFF for code in logcodes]
    if not item_ids: return None
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
def send_message(sock, message, parser=None):
    """Send message and optionally parse 0x1D response during initialization"""
    print("Sending message ({} bytes)".format(len(message)))
    sock.sendall(message)
    time.sleep(0.1)
    try:
        sock.settimeout(1)
        response = sock.recv(16384)
        print("Received response ({} bytes)".format(len(response)))
        
        # Check if this is a response to the first init message (0x1D command)
        if parser and message == b'\x1d\x1c\x3b\x7e':  # First init message
            # Try to parse 0x1D response from the response
            parse_0x1d_response(response, parser)
        
        return response
    except socket.timeout:
        print("Receive timeout, no response")
        return None

def parse_0x1d_response(response_data, parser):
    """Parse 0x1D timestamp response from initialization"""
    if not response_data:
        return
    
    # Split response by HDLC frame delimiter
    potential_frames = response_data.split(b'\x7e')
    
    for frame_data in potential_frames:
        if not frame_data:
            continue
        
        # Try to decode HDLC frame
        decoded_payload = HDLC.decode(frame_data + b'\x7e')
        if decoded_payload is None:
            continue
        
        # Check for standard diag response format
        if not decoded_payload.startswith(b'\x98\x01\x00\x00\x01\x00\x00\x00'):
            continue
        
        # Parse the response
        data = decoded_payload[12:]
        if len(data) < 12:
            continue
        
        msg_len, logcode, timestamp = struct.unpack('<HHQ', data[:12])
        payload = data[12 : 12 + msg_len]
        
        # Check if this is 0x1D response
        if logcode == 0x1D:
            print("\n=== 0x1D Timestamp Response Detected in Initialization ===")
            if len(payload) >= 8:
                # First 8 bytes after 0x1D are the device internal timestamp
                device_timestamp_bytes = payload[:8]
                device_timestamp = struct.unpack('<Q', device_timestamp_bytes)[0]
                
                print("[0x1D INIT RESPONSE] Device timestamp (raw): {}".format(device_timestamp))
                print("[0x1D INIT RESPONSE] Device timestamp (hex): 0x{:016x}".format(device_timestamp))
                print("[0x1D INIT RESPONSE] Payload first 8 bytes: {}".format(payload[:8].hex()))
                
                # Convert to readable format if it's a standard timestamp
                if parser:
                    readable_ts = parser.convert_timestamp(device_timestamp)
                    print("[0x1D INIT RESPONSE] Readable timestamp: {}".format(readable_ts))
                    
                    # Write device timestamp to file header
                    timestamp_comment = "# Device_Internal_Timestamp: {} (0x{:016x}) - {}".format(device_timestamp, device_timestamp, readable_ts)
                    if not parser._timestamp_logged:
                        parser._write_timestamp_header(timestamp_comment)
                        parser._timestamp_logged = True
            else:
                print("[0x1D INIT RESPONSE] Warning: Payload too short ({} bytes)".format(len(payload)))
            return  # Found and processed 0x1D response
def main():
    global drain_thread_running, client_socket_global, client_socket_lock, current_mode, fatal_error_occurred, raw_tcp_file
    
    # Initialize lock for thread-safe socket access
    client_socket_lock = threading.Lock()
    
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket_global = client_socket
    parser = DiagDataParser()
    
    # Thread object
    drain_thread = None
    
    try:
        print("Connecting to {}:{}...".format(HOST, PORT))
        client_socket.connect((HOST, PORT))
        print("Connection successful!")
        
        # 添加TCP_NODELAY禁用Nagle算法，减少网络延迟
        client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        print("TCP_NODELAY enabled for real-time data transmission")
        
        # Receive and analyze welcome message to determine mode
        welcome_bytes = client_socket.recv(1024)
        welcome_message = welcome_bytes.decode('utf-8', errors='ignore').strip()
        print("Server welcome message: {}".format(welcome_message))
        
        # Detect operating mode from welcome message
        if "Socket mode" in welcome_message:
            current_mode = OperatingMode.SOCKET
            print("[INFO] Detected SOCKET mode. Python-side drain will be activated.")
        elif "Legacy mode" in welcome_message or "bridge_diag_client connected" in welcome_message:
            current_mode = OperatingMode.LEGACY
            print("[INFO] Detected LEGACY mode. Drain is handled by the bridge. Python will not send drain commands.")
        else:
            current_mode = OperatingMode.UNKNOWN
            print("[WARNING] Could not determine operating mode from welcome message. Assuming LEGACY mode.")
        print("\nStarting initialization messages...")
        
        # Add extra init messages for socket mode
        if current_mode == OperatingMode.SOCKET:
            socket_mode_init_messages = [
                b'\x28\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x40\x78\x7d\x01',
                b'\x29\x00\x00\x00\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00',
                b'\x07\x00\x00\x00\x05\x00\x00\x00\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\xb6\x78\x00\x00',
                b'\x23\x00\x00\x00\x00\x00\x00\x00',
            ]
            print("[INFO] Sending socket mode specific initialization messages...")
            for msg in socket_mode_init_messages:
                print("Sending socket init message ({} bytes): {}".format(len(msg), msg.hex()))
                client_socket.sendall(msg)
                time.sleep(0.1)
            print("Socket mode initialization messages sent.")
        
        for i, message in enumerate(INIT_MESSAGES, 1):
            # Pass parser for the first message to handle 0x1D response
            if i == 1:
                print("[*] Sending first init message (0x1D command)...")
                response = send_message(client_socket, message, parser)
            else:
                response = send_message(client_socket, message)
            time.sleep(0.2)
        print("\nInitialization sequence complete!")
        print("\nSending default logcode list (B064, B16C)...")
        command = generate_logcode_command(DEFAULT_LOGCODES)
        if command:
            send_message(client_socket, command)
            print("\nSending final configuration message...")
            send_message(client_socket, FINAL_MESSAGE)
            print("[+] All configuration messages sent! Bridge should start drain thread now.")
        # Start drain thread if in SOCKET mode
        if current_mode == OperatingMode.SOCKET:
            print("\nStarting Python-side drain thread for SOCKET mode...")
            drain_thread_running = True
            drain_thread = threading.Thread(target=drain_buffer_thread, daemon=True)
            drain_thread.start()
            print("Drain buffer thread started successfully.")
        else:
            print("\nDrain thread is not required for LEGACY mode (handled by C bridge).")
        
        print("\nStarting continuous monitoring and parsing mode...")
        print("Press Ctrl-C to exit.")
        print("Output files:")
        print("  1. diag_report.txt - Parsed DIAG data report")
        print("  2. tcp_and_parse_data.txt - Raw TCP data and pre-parseandlog data")
        print("  3. parseandlog_data.txt - Data during parse_and_log with 98 header checking")
        print("  4. all_tcp_raw_data.txt - ALL raw TCP data")
        print("Operating in {} mode".format(current_mode))
        
        # Buffer for processing TCP stream
        receive_buffer = b''
        
        while True:
            try:
                client_socket.settimeout(1.0)
                start_recv_time = time.clock_gettime(time.CLOCK_REALTIME)
                new_data = client_socket.recv(65536)
                end_recv_time = time.clock_gettime(time.CLOCK_REALTIME)
                
                if not new_data:
                    print("Connection closed by server.")
                    break

                # Calculate recv duration and print log
                recv_duration_ms = (end_recv_time - start_recv_time) * 1000
                print("[DEBUG] recv({} bytes) blocked for {:.3f} ms".format(len(new_data), recv_duration_ms))

                # Get Python data receive timestamp, use CLOCK_REALTIME to ensure consistency with other components
                ts_python_recv = time.clock_gettime(time.CLOCK_REALTIME)
                
                # Log ALL raw TCP data
                log_all_tcp_data(new_data, ts_python_recv)
                
                # Log raw TCP data received to tcp_and_parse_data.txt
                with open("tcp_and_parse_data.txt", "a") as tcp_log:
                    tcp_log.write("\n=== Raw TCP Data Received at {:.6f} ===\n".format(ts_python_recv))
                    tcp_log.write("Data length: {} bytes\n".format(len(new_data)))
                    # Check if starts with 98
                    tcp_starts_with_98 = new_data.startswith(b'\x98') if len(new_data) > 0 else False
                    tcp_log.write("Starts with 0x98: {}\n".format(tcp_starts_with_98))
                    tcp_log.write("Hex dump:\n")
                    # Write hex dump
                    for i in range(0, len(new_data), 16):
                        hex_part = ' '.join('{:02X}'.format(b) for b in new_data[i:i+16])
                        tcp_log.write("{:04X}  {}\n".format(i, hex_part))
                
                # Add new data to receive buffer
                receive_buffer += new_data
                
                # Process data in buffer (same format for both modes)
                header_size = 8  # sizeof(double)
                
                while len(receive_buffer) >= header_size:
                    # Parse timestamp header
                    ts_bridge_read = struct.unpack('<d', receive_buffer[:header_size])[0]
                    
                    # Extract raw diag data (remove timestamp header)
                    remaining_data = receive_buffer[header_size:]
                    
                    # If there's data, process it
                    if len(remaining_data) > 0:
                        # Calculate network forwarding latency
                        net_forward_latency_ms = (ts_python_recv - ts_bridge_read) * 1000
                        
                        print("--- New Data Block ({} mode) ---".format(current_mode))
                        print("T_bridge_read: {}".format(ts_bridge_read))
                        print("T_python_recv: {}".format(ts_python_recv))
                        print("Net Forward Latency: {:.3f}ms".format(net_forward_latency_ms))
                        
                        # Log raw data BEFORE skipping any headers (after timestamp removal only)
                        if len(remaining_data) > 0:
                            log_raw_tcp_data(remaining_data, ts_bridge_read, ts_python_recv)
                        
                        # NEW LOGIC: Process frames with individual 12-byte DIAG header removal
                        # Note: 8-byte timestamp already removed, only need to remove 12-byte DIAG header
                        if len(remaining_data) > 12:
                            # 1. Remove first 12 bytes (DIAG header only, timestamp already removed)
                            first_frame_data = remaining_data[12:]
                            hdlc_data_stream = b''
                            
                            # 2. Check if there are more frames (split by 7e)
                            if b'\x7e' in first_frame_data:
                                # Split by 7e to find additional frames
                                parts = first_frame_data.split(b'\x7e')
                                
                                # Process first frame (already had 20 bytes removed)
                                if len(parts[0]) > 0:
                                    hdlc_data_stream += parts[0] + b'\x7e'
                                
                                # 3. Process additional frames - each needs 20-byte header removal 
                                # (8-byte timestamp + 12-byte DIAG header)
                                for i in range(1, len(parts)):
                                    frame_part = parts[i]
                                    if len(frame_part) > 20:  # Has enough data for full header removal
                                        # Remove full 20-byte header from additional frames
                                        frame_payload = frame_part[20:]
                                        if len(frame_payload) > 0:
                                            hdlc_data_stream += frame_payload + b'\x7e'
                                    elif len(frame_part) > 0:
                                        # Frame too short for header, use as-is
                                        hdlc_data_stream += frame_part + b'\x7e'
                            else:
                                # Only one frame, use it directly
                                hdlc_data_stream = first_frame_data + b'\x7e'
                            
                            # Process the reconstructed HDLC data stream
                            if hdlc_data_stream:
                                parser.parse_and_log(hdlc_data_stream, ts_bridge_read, ts_python_recv)
                    
                    # Prepare buffer for next data block
                    # Note: This assumes each TCP packet contains only one complete data block
                    # A more complete implementation would need to handle data block boundaries
                    receive_buffer = b''
                    break
                    
            except socket.timeout:
                continue
            except socket.error as e:
                print("Socket error: {}".format(e))
                break
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")
    except Exception as e:
        print("An error occurred: {}".format(e))
    finally:
        # Stop drain thread if running
        if drain_thread_running:
            print("Stopping drain thread...")
            drain_thread_running = False
            if drain_thread:
                drain_thread.join(timeout=2.0)  # Wait up to 2 seconds for thread to stop
        
        # Close raw TCP log file
        if raw_tcp_file:
            raw_tcp_file.close()
            print("Raw TCP data file closed.")
        
        # Close socket with thread safety
        with client_socket_lock:
            client_socket.close()
            client_socket_global = None
        
        print("Connection closed.")

if __name__ == "__main__":
    # Run main program: decode diag data and output to txt file
    main()

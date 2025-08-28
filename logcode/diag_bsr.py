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

def get_tbs_index_string(tbs_index):
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
    return TBS_MAP.get(tbs_index, "invalid")

def format_hex(data):
    return data.hex(' ')

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
        
        self.PER_SECOND = 52428800.0 
        self.EPOCH = datetime(1980, 1, 6, 0, 0, 0, tzinfo=timezone.utc)
        self.RNTI_TYPE_MAP = {1: "C-RNTI", 2: "SPS-RNTI"}
        self.BSR_EVENT_MAP = {0: "none", 1: "periodic", 2: "high-data-arrival", 3: "robustness-bsr"}
        self.BSR_TRIG_MAP = {0: "no-bsr", 1: "cacelled", 2: "l-bsr", 3: "s-bsr", 4: "pad-l-bsr", 5: "pad-s-bsr", 6: "pad-t-bsr"}
        self.LCID_MAP = {26: "PHR", 29: "S-BSR", 30: "L-BSR", 31: "Padding"}
        
        self.CE_LENGTH_MAP = {
            26: 1,
            29: 1,
            30: 3,
            31: 0
        }
        
        # Maps for B139 decoding
        self.CARRIER_INDEX_MAP = {0: "pcc", 1: "scc1", 2: "scc2"}
        self.RETX_INDEX_MAP = {
            0: "First", 1: "Second", 2: "Third", 3: "Fourth",
            4: "Fifth", 5: "Sixth", 6: "Seventh", 7: "Eighth"
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
                    "tbs_string": get_tbs_index_string(tbs_index),
                    "num_of_resource_blocks": num_of_resource_blocks, 
                    "is_ul_grant": 1
                }
                parsed_records.append(record_data)
            cursor += 126
        return parsed_records
    
    def _decode_b16c_v49(self, payload, timestamp, logcode):
        """Decode B16C payload for version 49"""
        parsed_records = []
        if len(payload) < 4: 
            return []
        
        # Parse S_H header (4 bytes)
        version = payload[0]
        # v49: num_record spans across 2 bytes
        num_records = ((payload[1] & 0x07) << 2) | ((payload[2] & 0xC0) >> 6)
        
        readable_timestamp = self.convert_timestamp(timestamp)
        payload_view = memoryview(payload)
        cursor = 4  # Skip S_H header
        
        for _ in range(num_records):
            if cursor + 4 > len(payload_view):  # R_H is 4 bytes in v49
                break
                
            # Parse Record Header (4 bytes in v49)
            r_h = payload_view[cursor : cursor + 4]
            num_ul_grant = ((r_h[1] & 0x01) << 2) | ((r_h[2] & 0xC0) >> 6)
            subfn = (r_h[2] & 0x3C) >> 2
            sysfn = ((r_h[2] & 0x03) << 8) | r_h[3]
            cursor += 4
            
            if num_ul_grant != 0:
                # UL Grant (16 bytes in v49)
                if cursor + 16 > len(payload_view):
                    break
                    
                ul_grant_view = payload_view[cursor : cursor + 16]
                
                # Parse UL grant fields (different positions in v49)
                tbs_index = (ul_grant_view[2] & 0xFC) >> 2
                mcs_index = ((ul_grant_view[2] & 0x03) << 3) | ((ul_grant_view[3] & 0xE0) >> 5)
                redundancy_version = (ul_grant_view[3] & 0x18) >> 3
                num_of_resource_blocks = (ul_grant_view[5] & 0xFC) >> 2
                
                record_data = {
                    "logcode": logcode,
                    "timestamp": timestamp, 
                    "readable_timestamp": readable_timestamp,
                    "version": version,
                    "subfn": subfn, 
                    "sysfn": sysfn, 
                    "mcs_index": mcs_index,
                    "redundancy_version": redundancy_version, 
                    "tbs_string": get_tbs_index_string(tbs_index),
                    "num_of_resource_blocks": num_of_resource_blocks, 
                    "is_ul_grant": 1
                }
                parsed_records.append(record_data)
                cursor += 16  # UL grant is 16 bytes in v49
            else:
                # DL Grant (8 bytes in v49)
                cursor += 8
                
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
            print(f"[WARNING] Unsupported B16C version detected: {version}")
            return []
    
    def _decode_b139_v161(self, payload, timestamp, logcode):
        """Decode B139 payload for version 161 (PUSCH transmission info)"""
        parsed_records = []
        if len(payload) < 8:
            return []
        
        # Parse S_H header (8 bytes)
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
            
            # Extract fields according to C code
            current_sfn_sf = struct.unpack('<H', record_view[0:2])[0]
            redund_ver = (record_view[2] & 0x30) >> 4
            re_tx_index = ((record_view[2] & 0x0F) << 1) | ((record_view[3] & 0x80) >> 7)
            ul_carrier_index = record_view[3] & 0x03
            num_of_rb = ((record_view[5] & 0x3F) << 1) | ((record_view[6] & 0x80) >> 7)
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
            cursor += 100  # Each record is 100 bytes
            
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
            print(f"[WARNING] Unsupported B139 version detected: {version}")
            return []

    def buffer_data(self, results, logcode):
        """Buffer data by timestamp for later writing to file"""
        if not results: 
            return
            
        for record in results:
            timestamp = self.convert_timestamp(record['timestamp'])
            ts_ran_event = self.convert_timestamp_to_unix(record['timestamp'])  # Convert to Unix timestamp
            
            # Create unique key for the timestamp with subfn/sysfn to preserve multiple records
            unique_key = f"{timestamp}_{record['subfn']}_{record['sysfn']}"
            
            if unique_key not in self._data_buffer:
                self._data_buffer[unique_key] = {
                    'timestamp': timestamp,
                    'unix_timestamp': ts_ran_event,
                    'subfn': record['subfn'],
                    'sysfn': record['sysfn'],
                    'lcg_0': '-', 
                    'lcg_1': '-', 
                    'lcg_2': '-', 
                    'lcg_3': '-', 
                    'num_rbs': '-',
                    'tbs_index': '-',
                    'bridge_timestamp': 0.0,
                    'pipeline_latency_ms': 0.0
                }
            
            if logcode == 0xB064:
                # Store the buffer size values (LCG values)
                self._data_buffer[unique_key]['lcg_0'] = record['buffer_size'][0]
                self._data_buffer[unique_key]['lcg_1'] = record['buffer_size'][1]
                self._data_buffer[unique_key]['lcg_2'] = record['buffer_size'][2]
                self._data_buffer[unique_key]['lcg_3'] = record['buffer_size'][3]
            
            elif logcode == 0xB16C:
                # Store the number of resource blocks and TBS index
                self._data_buffer[unique_key]['num_rbs'] = record['num_of_resource_blocks']
                self._data_buffer[unique_key]['tbs_index'] = record['tbs_string']
        
        # Write buffered data to file when it exceeds a certain size
        if len(self._data_buffer) > 100:
            self.write_buffered_data()

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
            
            # For B139, use current_sfn_sf as part of unique key
            if logcode == 0xB139:
                sfn_sf = record.get('current_sfn_sf', 0)
                subfn = sfn_sf & 0x000F
                sysfn = (sfn_sf >> 4) & 0x3FF
                unique_key = f"{timestamp}_{subfn}_{sysfn}_{record.get('re_tx_index', 0)}"
            else:
                # For B064 and B16C, use subfn/sysfn directly
                unique_key = f"{timestamp}_{record['subfn']}_{record['sysfn']}"
                subfn = record['subfn']
                sysfn = record['sysfn']
            
            if unique_key not in self._data_buffer:
                self._data_buffer[unique_key] = {
                    'timestamp': timestamp,
                    'unix_timestamp': ts_ran_event,
                    'subfn': subfn,
                    'sysfn': sysfn,
                    'lcg_0': '-', 
                    'lcg_1': '-', 
                    'lcg_2': '-', 
                    'lcg_3': '-', 
                    'num_rbs': '-',
                    'tbs_index': '-',
                    'pusch_tb_size': '-',
                    'redund_ver': '-',
                    'bridge_timestamp': ts_bridge_read,
                    'python_recv_timestamp': ts_python_recv,
                    'pipeline_latency_ms': pipeline_latency_ms
                }
            else:
                # Update latency information
                self._data_buffer[unique_key]['unix_timestamp'] = ts_ran_event
                self._data_buffer[unique_key]['bridge_timestamp'] = ts_bridge_read
                self._data_buffer[unique_key]['python_recv_timestamp'] = ts_python_recv
                self._data_buffer[unique_key]['pipeline_latency_ms'] = pipeline_latency_ms
            
            if logcode == 0xB064:
                # Store the buffer size values (LCG values)
                self._data_buffer[unique_key]['lcg_0'] = record['buffer_size'][0]
                self._data_buffer[unique_key]['lcg_1'] = record['buffer_size'][1]
                self._data_buffer[unique_key]['lcg_2'] = record['buffer_size'][2]
                self._data_buffer[unique_key]['lcg_3'] = record['buffer_size'][3]
            
            elif logcode == 0xB16C:
                # Store the number of resource blocks and TBS index
                self._data_buffer[unique_key]['num_rbs'] = record['num_of_resource_blocks']
                self._data_buffer[unique_key]['tbs_index'] = record['tbs_string']
            
            elif logcode == 0xB139:
                # Store PUSCH transmission info (only C code output fields)
                # Note: subfn and sysfn are already extracted and stored above
                self._data_buffer[unique_key]['redund_ver'] = record['redund_ver']
                self._data_buffer[unique_key]['pusch_tb_size'] = record['pusch_tb_size']
        
        # Write buffered data to file when it exceeds a certain size
        if len(self._data_buffer) > 100:
            self.write_buffered_data()

    def write_buffered_data(self):
        """Write the buffered data to the report file with latency analysis"""
        if not self._data_buffer:
            return
            
        try:
            with open(self._report_filename, 'a', encoding='utf-8') as f:
                # Write header if needed
                if not self._header_written:
                    f.seek(0, 2)  # Go to end of file
                    if f.tell() == 0:  # If file is empty
                        header = ["RAN_Event_Unix_Timestamp", "Bridge_Read_Timestamp", "Python_Recv_Timestamp", "Cellular_Precise_Timestamp", "SubFN", "SysFN", 
                                "LCG_0", "LCG_1", "LCG_2", "LCG_3", "Num_RBs", "TBS_Index", 
                                "Redund_Ver", "PUSCH_TB_Size",
                                "Pipeline_Latency_ms"]
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
                    for data in sorted(records, key=lambda x: (x['sysfn'], x['subfn'])):
                        # Calculate cellular precise timestamp based on Python_Recv_Timestamp (column 3)
                        python_recv_ts = data.get('python_recv_timestamp', 0.0)
                        cellular_precise_ts = self._calculate_cellular_timestamp(data['sysfn'], data['subfn'], python_recv_ts)
                        
                        line = f"{data.get('unix_timestamp', 0.0):.6f}\t{data['bridge_timestamp']:.6f}\t{python_recv_ts:.6f}\t{cellular_precise_ts:.6f}\t{data['subfn']}\t{data['sysfn']}\t"
                        line += f"{data['lcg_0']}\t{data['lcg_1']}\t{data['lcg_2']}\t{data['lcg_3']}\t"
                        line += f"{data['num_rbs']}\t{data['tbs_index']}\t"
                        line += f"{data.get('redund_ver', '-')}\t{data.get('pusch_tb_size', '-')}\t"
                        line += f"{data['pipeline_latency_ms']:.3f}"
                        f.write(line + "\n")
            
            print(f"Successfully wrote {len(self._data_buffer)} records to file")
            self._data_buffer.clear()  # Clear the buffer
        except IOError as e:
            print(f"Error writing to file: {e}")

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
            
            print(f"[INFO] Device timestamp written to {self._report_filename}")
            
        except IOError as e:
            print(f"Error writing timestamp header: {e}")

    def decode_b064_payload(self, payload, timestamp=None, logcode=None):
        """
        Decode B064 payload according to C code logic
        """
        results = []
        
        if len(payload) < 4:
            return results
            
        num_subpkt = payload[0]
        cursor = 4  # Skip S_H
        
        for _ in range(num_subpkt):
            if cursor + 5 > len(payload):
                break
                
            start_subpkt_h = cursor
            num_samples = payload[start_subpkt_h + 4]
            cursor += 5  # Skip Subpkt_H
            
            for j in range(num_samples):
                if cursor + 14 > len(payload):
                    break
                    
                start_sample_h = cursor
                
                # Parse SFN and SUBFN using struct.unpack similar to detailed parser
                sample_h_view = memoryview(payload[start_sample_h:start_sample_h+14])
                sfn_subfn_word = struct.unpack('<H', sample_h_view[4:6])[0]
                sysfn = sfn_subfn_word >> 4
                subfn = sfn_subfn_word & 0x000F
                
                # Parse other fields
                grant_bytes = struct.unpack('<H', sample_h_view[6:8])[0]
                padding = struct.unpack('<H', sample_h_view[9:11])[0]
                bsr_event = sample_h_view[11] & 0x03  # Match C code mask 0x03
                bsr_trig = sample_h_view[12] & 0x07   # Match C code mask 0x07
                hdrlen = sample_h_view[13]
                
                cursor += 14  # Skip Sample_H
                
                # Parse element data
                lcg = -1
                bsr_type = 0
                step = 0
                start_element = cursor
                buffer_size = [0, 0, 0, 0]
                
                while step < hdrlen:
                    if start_element + step >= len(payload):
                        break
                        
                    E = (payload[start_element + step] >> 5) & 1
                    LCID_data = payload[start_element + step] & 31
                    
                    # Determine BSR type
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
                        elif F != 0:
                            step += 1
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
                            
                        # Match C code logic for bsr_type reset
                        if step + 1 > hdrlen:
                            bsr_type = 0
                        break
                    
                    step += 1
                
                cursor += hdrlen  # Skip the header length
                
                # Create a record with the parsed data - use raw timestamp
                record = {
                    "logcode": logcode,
                    "timestamp": timestamp,  # Keep the original timestamp value as in C code
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
        potential_frames = hdlc_stream.split(b'\x7e')
        for frame_data in potential_frames:
            if not frame_data: continue
            
            decoded_payload = HDLC.decode(frame_data + b'\x7e')
            if decoded_payload is None: continue

            if not decoded_payload.startswith(b'\x98\01\x00\x00\x01\x00\x00\x00'): continue
            
            data = decoded_payload[12:]
            if len(data) < 12: continue
            
            msg_len, logcode, timestamp = struct.unpack('<HHQ', data[:12])
            payload = data[12 : 12 + msg_len]
            
            # Convert RAN event timestamp to Unix timestamp to maintain consistency with bridge timestamp
            ts_ran_event = self.convert_timestamp_to_unix(timestamp)
            
            # Calculate latency (RAN timestamp converted to Unix timestamp, consistent with bridge timestamp baseline)
            if ts_ran_event > 0 and ts_bridge_read is not None:  # Ensure timestamp is valid
                diag_pipeline_latency_ms = (ts_bridge_read - ts_ran_event) * 1000
                print(f"--- Latency Analysis ---")
                print(f"T_ran_event: {ts_ran_event}")
                print(f"T_bridge_read: {ts_bridge_read}")
                print(f"Diag Pipeline Latency: {diag_pipeline_latency_ms:.3f}ms")
            
            if logcode == 0xB16C:
                results = self.decode_b16c_payload(payload, timestamp, logcode)  # Using central dispatcher
                if results:
                    self.buffer_data_with_bridge_ts(results, logcode, ts_bridge_read, ts_python_recv)
            elif logcode == 0xB139:
                results = self.decode_b139_payload(payload, timestamp, logcode)  # Using central dispatcher
                if results:
                    self.buffer_data_with_bridge_ts(results, logcode, ts_bridge_read, ts_python_recv)
                    # Also write to B139_report.txt to match C code output format
                    self._write_b139_report(results)
            elif logcode == 0xB064:
                # Use the new C-style parsing for B064
                b064_records = self.decode_b064_payload(payload, timestamp, logcode)
                if b064_records:
                    self.buffer_data_with_bridge_ts(b064_records, logcode, ts_bridge_read, ts_python_recv)
        
        # Periodically write buffered data to file
        if len(self._data_buffer) > 50:
            self.write_buffered_data()

    def calculate_cellular_time_order(self, df):
        """
        Calculate precise time order based on cellular network time structure
        SysFN: 0-1023 (System Frame Number, increments every 10ms)
        SubFN: 0-9 (Sub-Frame Number, increments every 1ms)
        """
        # Calculate relative time offset (ms) = SysFN * 10 + SubFN * 1
        df['cellular_time_ms'] = df['SysFN'] * 10 + df['SubFN'] * 1
        
        # Handle SysFN wrap-around (0-1023)
        df = df.sort_values('RAN_Event_Unix_Timestamp').reset_index(drop=True)
        
        # Group by Unix timestamp to handle SysFN wrap-around
        grouped = df.groupby('RAN_Event_Unix_Timestamp')
        
        refined_data = []
        for timestamp, group in grouped:
            # Sort by cellular_time_ms within same Unix timestamp
            group_sorted = group.sort_values('cellular_time_ms').copy()
            
            # Add fine-grained timestamp (based on cellular network time)
            for i, (_, row) in enumerate(group_sorted.iterrows()):
                row_dict = row.to_dict()
                # Add millisecond-level offset to Unix timestamp
                row_dict['precise_timestamp'] = timestamp + (row['cellular_time_ms'] % 10240) / 1000.0
                row_dict['event_order_in_timestamp'] = i
                refined_data.append(row_dict)
        
        return pd.DataFrame(refined_data)


    def _write_b139_report(self, results):
        """Write B139 data to separate report file matching C code format"""
        try:
            with open('B139_report.txt', 'a+') as fp:
                for record in results:
                    # Match C code format exactly: logcode, timestamp, current_sfn_sf, redund_ver, pusch_tb_size
                    fp.write(f"{record['logcode']:02X}\t{int(record['timestamp'])}\t"
                            f"{record['current_sfn_sf']}\t{record['redund_ver']}\t"
                            f"{record['pusch_tb_size']}\n")
        except IOError as e:
            print(f"Error writing to B139_report.txt: {e}")
    
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
                        print(f"Sent {drain_count} drain commands ({rate:.2f} commands/sec)")
            
            # Control the rate (adjust as needed)
            time.sleep(0.0001)  # ~10000 times per second
            
        except socket.error as e:
            if e.errno == errno.EPIPE or str(e).find("Broken pipe") >= 0:
                print(f"Error in drain thread: [Errno 32] Broken pipe")
                fatal_error_occurred = True
                break
            else:
                print(f"Error in drain thread: {e}")
                time.sleep(0.1)
        except Exception as e:
            print(f"Error in drain thread: {e}")
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
DEFAULT_LOGCODES = [0xB064, 0xB16C, 0xB139]  # Added B139 for PUSCH transmission info
def hex_dump(data):
    return ' '.join(f"{b:02x}" for b in data)
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
    print(f"Sending message ({len(message)} bytes)")
    sock.sendall(message)
    time.sleep(0.1)
    try:
        sock.settimeout(1)
        response = sock.recv(16384)
        print(f"Received response ({len(response)} bytes)")
        
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
            print(f"\n=== 0x1D Timestamp Response Detected in Initialization ===")
            if len(payload) >= 8:
                # First 8 bytes after 0x1D are the device internal timestamp
                device_timestamp_bytes = payload[:8]
                device_timestamp = struct.unpack('<Q', device_timestamp_bytes)[0]
                
                print(f"[0x1D INIT RESPONSE] Device timestamp (raw): {device_timestamp}")
                print(f"[0x1D INIT RESPONSE] Device timestamp (hex): 0x{device_timestamp:016x}")
                print(f"[0x1D INIT RESPONSE] Payload first 8 bytes: {payload[:8].hex()}")
                
                # Convert to readable format if it's a standard timestamp
                if parser:
                    readable_ts = parser.convert_timestamp(device_timestamp)
                    print(f"[0x1D INIT RESPONSE] Readable timestamp: {readable_ts}")
                    
                    # Write device timestamp to file header
                    timestamp_comment = f"# Device_Internal_Timestamp: {device_timestamp} (0x{device_timestamp:016x}) - {readable_ts}"
                    if not parser._timestamp_logged:
                        parser._write_timestamp_header(timestamp_comment)
                        parser._timestamp_logged = True
            else:
                print(f"[0x1D INIT RESPONSE] Warning: Payload too short ({len(payload)} bytes)")
            return  # Found and processed 0x1D response
def main():
    global drain_thread_running, client_socket_global, client_socket_lock, current_mode, fatal_error_occurred
    
    # Initialize lock for thread-safe socket access
    client_socket_lock = threading.Lock()
    
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket_global = client_socket
    parser = DiagDataParser()
    
    # Thread object
    drain_thread = None
    
    try:
        print(f"Connecting to {HOST}:{PORT}...")
        client_socket.connect((HOST, PORT))
        print("Connection successful!")
        
        # Receive and analyze welcome message to determine mode
        welcome_bytes = client_socket.recv(1024)
        welcome_message = welcome_bytes.decode('utf-8', errors='ignore').strip()
        print(f"Server welcome message: {welcome_message}")
        
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
                print(f"Sending socket init message ({len(msg)} bytes): {msg.hex()}")
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
        print("Press Ctrl-C to exit. Parsed data will be saved to diag_report.txt")
        print(f"Operating in {current_mode} mode")
        
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
                print(f"[DEBUG] recv({len(new_data)} bytes) blocked for {recv_duration_ms:.3f} ms")

                # Get Python data receive timestamp, use CLOCK_REALTIME to ensure consistency with other components
                ts_python_recv = time.clock_gettime(time.CLOCK_REALTIME)
                
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
                        
                        print(f"--- New Data Block ({current_mode} mode) ---")
                        print(f"T_bridge_read: {ts_bridge_read}")
                        print(f"T_python_recv: {ts_python_recv}")
                        print(f"Net Forward Latency: {net_forward_latency_ms:.3f}ms")
                        
                        # Process raw diag data, skip first 12 bytes of TCP header
                        if len(remaining_data) > 12:
                            hdlc_data_stream = remaining_data[12:]
                            parser.parse_and_log(hdlc_data_stream, ts_bridge_read, ts_python_recv)
                    
                    # Prepare buffer for next data block
                    # Note: This assumes each TCP packet contains only one complete data block
                    # A more complete implementation would need to handle data block boundaries
                    receive_buffer = b''
                    break
                    
            except socket.timeout:
                continue
            except socket.error as e:
                print(f"Socket error: {e}")
                break
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Stop drain thread if running
        if drain_thread_running:
            print("Stopping drain thread...")
            drain_thread_running = False
            if drain_thread:
                drain_thread.join(timeout=2.0)  # Wait up to 2 seconds for thread to stop
        
        # Close socket with thread safety
        with client_socket_lock:
            client_socket.close()
            client_socket_global = None
        
        print("Connection closed.")

if __name__ == "__main__":
    # Run main program: decode diag data and output to txt file
    main()

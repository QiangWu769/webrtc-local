# -*- coding: utf-8 -*-
import struct
import sys
import os
from datetime import datetime, timezone, timedelta
from hdlc import HDLC

class HexFileParser:
    def __init__(self, report_filename="hex_file_report.txt"):
        self._report_filename = report_filename
        self.PER_SECOND = 52428800.0 
        self.EPOCH = datetime(1980, 1, 6, 0, 0, 0, tzinfo=timezone.utc)
        self._data_records = []  # Store parsed records
        
        # Initialize the DiagDataParser from diag_bsr.py
        from diag_bsr import DiagDataParser
        self.parser = DiagDataParser(report_filename=report_filename)
    
    def convert_timestamp(self, ts):
        """Convert timestamp to readable format"""
        if ts == 0: 
            return "N/A"
        try:
            seconds_since_epoch = ts / self.PER_SECOND
            utc_time = self.EPOCH + timedelta(seconds=seconds_since_epoch)
            local_time = utc_time.astimezone(None)
            return local_time.strftime('%Y-%m-%d %H:%M:%S.%f')
        except (OverflowError, ValueError):
            return str(ts)
    
    def parse_hex_file(self, hex_file_path):
        """Parse hexadecimal file containing packets with 98 header and 7E trailer"""
        if not os.path.exists(hex_file_path):
            print("Error: File {} not found".format(hex_file_path))
            return
        
        print("Parsing hex file: {}".format(hex_file_path))
        
        # Read the hex file
        with open(hex_file_path, 'rb') as f:
            file_content = f.read()
        
        print("File size: {} bytes".format(len(file_content)))
        
        # Split by 7E delimiter to find frames
        frames = file_content.split(b'\x7e')
        print("Found {} potential frames".format(len(frames)))
        
        processed_frames = 0
        valid_diag_packets = 0
        
        for i, frame_data in enumerate(frames):
            if not frame_data:
                continue
            
            print("\n--- Processing Frame {} ---".format(i + 1))
            print("Frame length: {} bytes".format(len(frame_data)))
            
            # Check if frame starts with 98
            if frame_data.startswith(b'\x98'):
                print("Frame starts with 0x98 - processing as DIAG packet")
                
                # Try to decode HDLC frame
                hdlc_frame = frame_data + b'\x7e'  # Add back the delimiter
                decoded_payload = HDLC.decode(hdlc_frame)
                
                if decoded_payload is None:
                    print("HDLC decode failed for this frame")
                    continue
                
                print("HDLC decode successful, payload length: {} bytes".format(len(decoded_payload)))
                
                # Check for DIAG header (98 01 00 00 01 00 00 00)
                if decoded_payload.startswith(b'\x98\01\x00\x00\x01\x00\x00\x00'):
                    print("Valid DIAG packet detected")
                    valid_diag_packets += 1
                    
                    # Skip the 12-byte DIAG header
                    data = decoded_payload[12:]
                    
                    if len(data) < 12:
                        print("Data after DIAG header too short, skipping")
                        continue
                    
                    # Parse message length, logcode, and timestamp
                    msg_len, logcode, timestamp = struct.unpack('<HHQ', data[:12])
                    payload = data[12 : 12 + msg_len]
                    
                    print("Logcode: 0x{:04X}".format(logcode))
                    print("Message length: {} bytes".format(msg_len))
                    print("Timestamp: {} ({})".format(timestamp, self.convert_timestamp(timestamp)))
                    
                    # Process different logcode types
                    results = []
                    if logcode == 0xB16C:
                        print("Processing B16C payload...")
                        results = self.parser.decode_b16c_payload(payload, timestamp, logcode)
                    elif logcode == 0xB139:
                        print("Processing B139 payload...")
                        results = self.parser.decode_b139_payload(payload, timestamp, logcode)
                    elif logcode == 0xB064:
                        print("Processing B064 payload...")
                        results = self.parser.decode_b064_payload(payload, timestamp, logcode)
                    else:
                        print("Unsupported logcode: 0x{:04X}".format(logcode))
                    
                    if results:
                        print("Parsed {} records from this packet".format(len(results)))
                        # Store records without timestamp processing since raw file has no bridge/python timestamps
                        for record in results:
                            self._data_records.append(record)
                    else:
                        print("No valid records parsed from this packet")
                
                else:
                    print("Not a standard DIAG packet (doesn't start with 98 01 header)")
                    if len(decoded_payload) >= 8:
                        header_hex = ' '.join('{:02X}'.format(b) for b in decoded_payload[:8])
                        print("First 8 bytes: {}".format(header_hex))
            else:
                print("Frame doesn't start with 0x98, skipping")
                if len(frame_data) >= 4:
                    header_hex = ' '.join('{:02X}'.format(b) for b in frame_data[:4])
                    print("First 4 bytes: {}".format(header_hex))
            
            processed_frames += 1
        
        # Write parsed data to simplified report file (without bridge/python timestamps)
        self._write_simple_report()
        
        print("\n=== Parsing Summary ===")
        print("Total frames processed: {}".format(processed_frames))
        print("Valid DIAG packets: {}".format(valid_diag_packets))
        print("Total records parsed: {}".format(len(self._data_records)))
        print("Output written to: {}".format(self._report_filename))
    
    def _write_simple_report(self):
        """Write report matching original diag_bsr.py format but without bridge/python timestamps"""
        if not self._data_records:
            print("No records to write")
            return
        
        try:
            with open(self._report_filename, 'w', encoding='utf-8') as f:
                # Use the same header format as original diag_bsr.py, but skip bridge/python timestamp columns
                header = ["RAN_Event_Unix_Timestamp", "Current_SFN_SF", 
                         "LCG_0", "LCG_1", "LCG_2", "LCG_3", "Num_RBs", "TBS_Index", 
                         "MCS_Index", "Redund_Ver", "PUSCH_TB_Size"]
                f.write("\t".join(header) + "\n")
                
                # Group records by timestamp like original code
                timestamp_groups = {}
                for record in self._data_records:
                    timestamp_key = record.get('timestamp', 0)
                    readable_ts = self.convert_timestamp(timestamp_key)
                    if readable_ts not in timestamp_groups:
                        timestamp_groups[readable_ts] = []
                    timestamp_groups[readable_ts].append(record)
                
                # Write data records sorted by timestamp
                for readable_timestamp, records in sorted(timestamp_groups.items()):
                    for record in sorted(records, key=lambda x: x.get('sysfn', 0) * 10 + x.get('subfn', 0)):
                        logcode = record.get('logcode', 0)
                        timestamp = record.get('timestamp', 0)
                        unix_timestamp = self.parser.convert_timestamp_to_unix(timestamp)
                        
                        # Calculate current_sfn_sf
                        if logcode in [0xB16C, 0xB064]:
                            sysfn = record.get('sysfn', 0)
                            subfn = record.get('subfn', 0)
                            current_sfn_sf = sysfn * 10 + subfn
                        elif logcode == 0xB139:
                            current_sfn_sf = record.get('current_sfn_sf', 0)
                        else:
                            current_sfn_sf = 0
                        
                        # Initialize all fields with default values
                        lcg_0 = lcg_1 = lcg_2 = lcg_3 = '-'
                        num_rbs = tbs_index = mcs_index = redund_ver = pusch_tb_size = '-'
                        
                        # Fill in data based on logcode
                        if logcode == 0xB064:
                            buffer_size = record.get('buffer_size', [0, 0, 0, 0])
                            lcg_0, lcg_1, lcg_2, lcg_3 = buffer_size
                        elif logcode == 0xB16C:
                            num_rbs = record.get('num_of_resource_blocks', '-')
                            tbs_index = record.get('tbs_index', '-')
                            mcs_index = record.get('mcs_index', '-')
                        elif logcode == 0xB139:
                            redund_ver = record.get('redund_ver', '-')
                            pusch_tb_size = record.get('pusch_tb_size', '-')
                            num_rbs = record.get('num_of_rb', '-')
                        
                        # Format line exactly like original
                        line = "{:.6f}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}".format(
                            unix_timestamp,
                            current_sfn_sf,
                            lcg_0, lcg_1, lcg_2, lcg_3,
                            num_rbs, tbs_index,
                            mcs_index,
                            redund_ver, pusch_tb_size
                        )
                        f.write(line + "\n")
            
            print("Successfully wrote {} records in original format".format(len(self._data_records)))
            
        except IOError as e:
            print("Error writing to file: {}".format(e))

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 hex_file_parser.py <hex_file_path>")
        print("Example: python3 hex_file_parser.py data.hex")
        sys.exit(1)
    
    hex_file_path = sys.argv[1]
    
    # Generate output filename based on input filename
    base_name = os.path.splitext(os.path.basename(hex_file_path))[0]
    output_filename = "{}_parsed_report.txt".format(base_name)
    
    print("Hex File Parser - Based on diag_bsr.py")
    print("Input file: {}".format(hex_file_path))
    print("Output file: {}".format(output_filename))
    print("=" * 50)
    
    # Create parser and process file
    parser = HexFileParser(report_filename=output_filename)
    parser.parse_hex_file(hex_file_path)

if __name__ == "__main__":
    main()
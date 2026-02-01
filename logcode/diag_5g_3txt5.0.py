# -*- coding: utf-8 -*-
"""
5G NR DIAG Parser - Outputs separate log files for B872, B883, and B885
Based on diag_3txt.py architecture, adapted for 5G NR messages

B872: NR5G L2 UL TB (Uplink Transport Block with BSR)
B883: NR5G MAC UL Physical Channel (PUSCH/PUCCH)
B885: NR5G MAC PDCCH (Downlink Control Info with UL Grant)
"""

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

def extract_bits(data, byte_offset, bit_start, bit_length):
    """Extract bit field from data (little-endian 32-bit word)"""
    if byte_offset + 4 > len(data):
        return 0
    word = int.from_bytes(data[byte_offset:byte_offset+4], 'little')
    mask = (1 << bit_length) - 1
    return (word >> bit_start) & mask

class NR5GDiagParser:
    """5G NR DIAG parser that outputs to three separate log files"""

    def __init__(self):
        # Output files for each logcode type
        self.b872_file = "b872_ul_tb_data.txt"
        self.b883_file = "b883_phychan_data.txt"
        self.b885_file = "b885_pdcch_data.txt"
        self.raw_tcp_file = "raw_tcp_data.txt"  # Raw TCP data file

        # Initialize files with headers
        self._init_output_files()

        # Buffers for batch writing
        self.b872_buffer = []
        self.b883_buffer = []
        self.b885_buffer = []

        # Raw TCP data logging
        self.raw_tcp_counter = 0
        self._init_raw_tcp_file()

        # 5G NR Numerology to slots per frame mapping
        # μ=0 (15kHz): 10 slots/frame, μ=1 (30kHz): 20 slots/frame
        # μ=2 (60kHz): 40 slots/frame, μ=3 (120kHz): 80 slots/frame
        self.numerology_slots_per_frame = {0: 10, 1: 20, 2: 40, 3: 80}

    def calculate_tti(self, frame, slot, numerology):
        """
        Calculate TTI for 5G NR
        TTI = Frame * slots_per_frame + Slot
        """
        slots_per_frame = self.numerology_slots_per_frame.get(numerology, 10)
        return frame * slots_per_frame + slot

    def _init_raw_tcp_file(self):
        """Initialize raw TCP data file with session header"""
        with open(self.raw_tcp_file, 'w') as f:
            f.write("=" * 100 + "\n")
            f.write("5G NR Raw TCP Data Log\n")
            f.write("Session started at: {}\n".format(time.strftime('%Y-%m-%d %H:%M:%S')))
            f.write("=" * 100 + "\n\n")

    def log_raw_tcp_data(self, data, timestamp):
        """
        Log raw TCP data with hex dump format

        Args:
            data: Raw bytes received from TCP
            timestamp: Receive timestamp
        """
        self.raw_tcp_counter += 1

        try:
            with open(self.raw_tcp_file, 'a') as f:
                f.write("\n" + "-" * 100 + "\n")
                f.write("Packet #{} @ {:.6f}\n".format(self.raw_tcp_counter, timestamp))
                f.write("Length: {} bytes\n".format(len(data)))
                f.write("-" * 100 + "\n")

                # Hex dump in rows of 16 bytes
                for i in range(0, len(data), 16):
                    # Hex representation
                    hex_part = ' '.join('{:02X}'.format(b) for b in data[i:i+16])

                    # ASCII representation
                    ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data[i:i+16])

                    # Format: offset | hex (48 chars) | ascii
                    f.write("{:04X}  {:48s}  |{}|\n".format(i, hex_part, ascii_part))

                f.write("\n")

        except Exception as e:
            print("Error writing to {}: {}".format(self.raw_tcp_file, e))

    def _init_output_files(self):
        """Initialize output files with headers"""
        # B872 header: UL TB data with BSR
        with open(self.b872_file, 'w') as f:
            header = ["Timestamp_us", "TTI", "Slot", "Frame", "Numerology",
                      "Grant_Size", "Bytes_Built", "MCE_Type", "BSR_LCG",
                      "LCG_0", "LCG_1", "LCG_2", "LCG_3", "LCG_4", "LCG_5", "LCG_6", "LCG_7"]
            f.write("\t".join(header) + "\n")

        # B883 header: Physical channel data (with new PUSCH fields)
        with open(self.b883_file, 'w') as f:
            header = ["Timestamp_us", "TTI", "Slot", "Frame", "Numerology",
                      "PhyChan_Type", "RNTI", "Num_PUCCH", "Second_Hop_RB",
                      "MCS", "MCS_Table", "Num_RBs", "TB_Size", "RV_Index",
                      "HARQ_ID", "RB_Start", "Num_Symbols"]
            f.write("\t".join(header) + "\n")

        # B885 header: PDCCH UL grant data
        with open(self.b885_file, 'w') as f:
            header = ["Timestamp_us", "TTI", "Slot", "Frame", "Numerology",
                      "MCS_Index", "RV", "Symbol_Alloc_Index", "RB_Assignment"]
            f.write("\t".join(header) + "\n")

    def decode_b872_payload(self, payload, timestamp_us):
        """
        Decode B872 NR5G L2 UL TB payload
        Based on B872_v131073_no_asn.py
        """
        results = []
        if len(payload) < 8:
            return results

        data = bytearray(payload)
        index = 0

        # S_H header (8 bytes)
        version = data[index]
        num_tti = data[index + 4]
        index += 8

        for i in range(num_tti):
            if index + 8 > len(data):
                break

            # TTI Header
            slot_number = data[index]
            frame = ((data[index + 3] & 0x03) << 8) | data[index + 2]
            num_tb = data[index + 4] & 0x0F
            index += 8

            for _ in range(num_tb):
                if index + 20 > len(data):
                    break

                tb_start = index

                # TB Header - 直接使用小端序读取，无需手动转换
                numerology = data[tb_start + 1] & 0x07

                # Grant Size (4字节, 小端序)
                grant_size = struct.unpack('<I', data[tb_start+4:tb_start+8])[0]

                # Bytes Built (4字节, 小端序)
                bytes_built = struct.unpack('<I', data[tb_start+8:tb_start+12])[0]

                # MCE Length
                mce_length = data[tb_start + 16] & 0x3F

                # Advance index to MAC CE payload (if any)
                index = tb_start + 20

                # Parse MCE (MAC Control Element) for BSR
                mce_type = 0
                bsr_lcg = -1
                buffer_size = [-1, -1, -1, -1, -1, -1, -1, -1]

                if mce_length > 0 and index + mce_length <= len(data):
                    step = 0
                    mce_start = index

                    while step < mce_length:
                        mce_type = data[mce_start + step] & 0x3F
                        step += 1

                        if mce_type == 62:  # L-BSR (5G NR Long BSR)
                            # 5G NR L-BSR format (3GPP TS 38.321):
                            # - Byte 0: LCG ID bitmap (bit i=1 means LCG i has data)
                            # - Bytes 1+: BSR index (6 bits) for each LCG with bit=1
                            lcg_bitmap = data[mce_start + step]
                            step += 1
                            bsr_lcg = lcg_bitmap  # Store bitmap for reference

                            # Extract BSR values for each LCG indicated in bitmap
                            for k in range(8):
                                if lcg_bitmap & (1 << k):  # If LCG k has data
                                    if mce_start + step < len(data):
                                        # 5G NR BSR index is 6 bits (0-63)
                                        buffer_size[k] = data[mce_start + step] & 0x3F
                                        step += 1
                        elif mce_type == 61:  # S-BSR
                            bsr_lcg = (data[mce_start + step] & 0xE0) >> 5
                            buffer_size[0] = data[mce_start + step] & 0x1F
                            step += 1
                        elif mce_type == 57:  # S-PHR
                            step += 2
                        else:
                            step = mce_length

                    index += mce_length

                # Record all TB data (not just those with BSR)
                # Calculate TTI
                tti = self.calculate_tti(frame, slot_number, numerology)

                record = {
                    "timestamp_us": timestamp_us,
                    "tti": tti,
                    "slot": slot_number,
                    "frame": frame,
                    "numerology": numerology,
                    "grant_size": grant_size,
                    "bytes_built": bytes_built,
                    "mce_type": mce_type,
                    "bsr_lcg": bsr_lcg,
                    "buffer_size": buffer_size
                }
                results.append(record)

        return results

    def decode_b883_payload(self, payload, timestamp_us):
        """
        Decode B883 NR5G MAC UL Physical Channel payload
        Based on B883_v131089_final_parser.py

        Some packets have prefix bytes before the version field:
        - Normal: payload starts with 11 00 02 00 (version 131089)
        - +1 byte prefix: 01 11 00 02 00
        - +2 byte prefix: 0e 01 11 00 02 00
        We search for the version signature to find the actual start.
        """
        results = []
        if len(payload) < 28:
            return results

        data = bytearray(payload)

        # Search for version 131089 signature (11 00 02 00) in first 4 bytes
        # Some packets have 1-2 prefix bytes before the version field
        version_offset = 0
        for offset in range(min(4, len(data) - 4)):
            version_value = int.from_bytes(data[offset:offset+4], 'little')
            if version_value == 131089 or version_value == 0x00020011:
                version_offset = offset
                break

        # Adjust data to skip prefix bytes
        data = data[version_offset:]

        # Sub-Header
        version = int.from_bytes(data[0:4], 'little')
        num_record = data[15] if len(data) > 15 else 0

        index = 16  # Records start after sub-header

        # MCS Table mapping
        mcs_table_map = {0: "64QAM", 1: "256QAM", 2: "64QAM_LowSE", 3: "Reserved"}

        for _ in range(num_record):
            if index >= len(data):
                break

            rec_start = index

            # Record Header (4 bytes)
            slot = data[index]
            numerology_byte = data[index + 1]
            frame = data[index + 2] | ((data[index + 3] & 0x03) << 8)
            index += 4

            numerology_id = numerology_byte & 0x07

            # Carrier Header
            num_carrier = data[index]
            carrier_id = data[index + 1]
            index += 2

            # Skip 2 bytes reserved
            index += 2

            # Physical Channel Indicator
            phychan_indicator = data[index]
            index += 1

            # Calculate TTI
            tti = self.calculate_tti(frame, slot, numerology_id)

            record = {
                "timestamp_us": timestamp_us,
                "tti": tti,
                "slot": slot,
                "frame": frame,
                "numerology": numerology_id,
                "phychan_type": "",
                "rnti": -1,
                "num_pucch": -1,
                "second_hop_rb": -1,
                # New PUSCH fields
                "mcs": -1,
                "mcs_table": "",
                "num_rbs": -1,
                "tb_size": -1,
                "rv_index": -1,
                "harq_id": -1,
                "rb_start": -1,
                "num_symbols": -1
            }

            if phychan_indicator == 0x80:
                # PUSCH
                record["phychan_type"] = "PUSCH"

                # Skip remaining carrier header (7 bytes)
                index += 7

                # Extract RNTI at offset 42 from record start
                rnti_offset = 42
                if rec_start + rnti_offset + 1 < len(data):
                    rnti = data[rec_start + rnti_offset] | (data[rec_start + rnti_offset + 1] << 8)
                    record["rnti"] = rnti

                # Extract additional PUSCH fields using bit positions
                # pusch_base = rec_start + 8 (where PhyChan indicator 0x80 is)
                pusch_base = rec_start + 8

                # MCS: byte +5, bits [5-9], len=5
                record["mcs"] = extract_bits(data, pusch_base + 5, 5, 5)

                # MCS Table: byte +5, bits [10-11], len=2
                mcs_table_code = extract_bits(data, pusch_base + 5, 10, 2)
                record["mcs_table"] = mcs_table_map.get(mcs_table_code, "Unknown")

                # HARQ_ID: byte +5, bits [1-4], len=4
                record["harq_id"] = extract_bits(data, pusch_base + 5, 1, 4)

                # RB_Start: byte +6, bits [7-13], len=7
                record["rb_start"] = extract_bits(data, pusch_base + 6, 7, 7)

                # TB_Size: byte +9, bits [3-14], len=12
                record["tb_size"] = extract_bits(data, pusch_base + 9, 3, 12)

                # Num_RBs: byte +8, bits [0-6], len=7
                record["num_rbs"] = extract_bits(data, pusch_base + 8, 0, 7)

                # Num_Symbols: byte +4, bits [5-8], len=4
                record["num_symbols"] = extract_bits(data, pusch_base + 4, 5, 4)

                # RV_Index: typically 0
                record["rv_index"] = 0

                # PUSCH record is 52 bytes
                index = rec_start + 52

            elif phychan_indicator == 0x00:
                # PUCCH
                record["phychan_type"] = "PUCCH"

                # Skip remaining carrier header (3 bytes)
                index += 3

                # PUCCH Header
                num_pucch = data[index]
                record["num_pucch"] = num_pucch
                index += 1

                # Second hop RB at offset 31 from record start
                second_hop_offset = 31
                if rec_start + second_hop_offset < len(data):
                    second_hop_enc = data[rec_start + second_hop_offset]
                    record["second_hop_rb"] = second_hop_enc * 2

                # PUCCH record is 32 bytes
                index = rec_start + 32
            else:
                # Unknown type, skip
                index += 20

            results.append(record)

        return results

    def decode_b885_payload(self, payload, timestamp_us):
        """
        Decode B885 NR5G MAC PDCCH payload
        Supports both v196617 and v131084 formats

        Some packets have prefix bytes before the version field:
        - Normal: payload starts with 0c 00 02 00 (version 131084)
        - +1 byte prefix: 01 0c 00 02 00
        - +2 byte prefix: 0e 01 0c 00 02 00
        We search for the version signature to find the actual start.
        """
        results = []
        if len(payload) < 28:
            return results

        data = bytearray(payload)

        # Search for version 131084 signature (0c 00 02 00) in first 4 bytes
        # Some packets have 1-2 prefix bytes before the version field
        version_offset = 0
        is_v131084 = False

        for offset in range(min(4, len(data) - 4)):
            version_value = int.from_bytes(data[offset:offset+4], 'little')
            if version_value == 131084 or version_value == 0x0002000C:
                version_offset = offset
                is_v131084 = True
                break

        if is_v131084:
            # Adjust data to skip prefix bytes
            adjusted_data = data[version_offset:]
            results = self._decode_b885_v131084(adjusted_data, timestamp_us)
        else:
            # v196617: Use beacon-4 offset for TTI info
            results = self._decode_b885_v196617(data, timestamp_us)

        return results

    def _decode_b885_v131084(self, data, timestamp_us):
        """
        Decode B885 v131084 format with proper structure parsing

        B885 Structure (v131084):
        ========================
        Sub-header (16 bytes):
          +0x00  Version (4 bytes, 0x0002000C = 131084)
          +0x04  Reserved (11 bytes)
          +0x0F  Num Records (1 byte)

        Record (variable size):
          +0x00  Slot (1 byte)
          +0x01  SCS/Numerology (1 byte, bits 0-2)
          +0x02  Frame (2 bytes, 10-bit value)
          +0x04  Num DCI (1 byte)
          +0x05  Carrier/Reserved (3 bytes)
          +0x08  DCI[0] starts here

        DCI Entry:
          +0x00  PhyChan indicator = 0x80 (1 byte)
          +0x01  Format indicator (1 byte)
                 - Bit 0 set (0x01, 0x09, etc.): DL DCI, size = 16 bytes
                 - Bit 5 set (0x20, 0xA0, etc.): UL DCI, size = 32 bytes

        UL DCI (32 bytes):
          +0x0C  Raw DCI[0] (4 bytes LE) - contains MCS, HARQ, RV, etc.
          +0x14  RB Assignment (2 bytes LE)
        """
        results = []
        if len(data) < 16:
            return results

        num_record = data[15]
        if num_record == 0 or num_record > 20:  # Sanity check
            return results

        # DCI sizes based on format type
        DL_DCI_SIZE = 16
        UL_DCI_SIZE = 32
        RECORD_HEADER_SIZE = 8

        index = 16  # Records start after sub-header

        for _ in range(num_record):
            if index + RECORD_HEADER_SIZE > len(data):
                break

            # Parse Record Header
            slot = data[index]
            numerology_id = data[index + 1] & 0x07
            frame = data[index + 2] | ((data[index + 3] & 0x03) << 8)
            num_dci = data[index + 4]

            # Validate record header
            if frame >= 1024 or numerology_id > 3:
                break

            max_slot = {0: 10, 1: 20, 2: 40, 3: 80}.get(numerology_id, 10)
            if slot >= max_slot:
                break

            if num_dci < 1 or num_dci > 10:
                break

            # Move to DCI entries (skip 8-byte record header)
            dci_index = index + RECORD_HEADER_SIZE

            # Process each DCI in this record
            for _ in range(num_dci):
                if dci_index + 2 > len(data):
                    break

                # Check DCI header
                phychan = data[dci_index]
                format_ind = data[dci_index + 1]

                if phychan != 0x80:
                    # Unknown format, try to skip
                    break

                # Determine DCI type and size
                if format_ind & 0x20:
                    # UL DCI (bit 5 set: 0x20, 0xA0, 0xE0, etc.)
                    dci_size = UL_DCI_SIZE

                    if dci_index + dci_size > len(data):
                        break

                    # Extract UL DCI fields
                    # Raw DCI[0] at offset +12
                    raw_dci0 = struct.unpack('<I', data[dci_index + 12:dci_index + 16])[0]

                    # RB Assignment at offset +20
                    rb_assignment = data[dci_index + 20] | (data[dci_index + 21] << 8)

                    # Extract fields from Raw DCI[0]
                    harq_id = (raw_dci0 >> 3) & 0xF
                    rv = (raw_dci0 >> 7) & 0x3
                    mcs_index = (raw_dci0 >> 10) & 0x1F
                    symbol_alloc_index = (raw_dci0 >> 15) & 0x3

                    tti = self.calculate_tti(frame, slot, numerology_id)

                    record = {
                        "timestamp_us": timestamp_us,
                        "tti": tti,
                        "slot": slot,
                        "frame": frame,
                        "numerology": numerology_id,
                        "mcs_index": mcs_index,
                        "harq_id": harq_id,
                        "rv": rv,
                        "symbol_alloc_index": symbol_alloc_index,
                        "rb_assignment": rb_assignment
                    }
                    results.append(record)

                elif format_ind & 0x01:
                    # DL DCI (bit 0 set: 0x01, 0x09, etc.)
                    dci_size = DL_DCI_SIZE
                    # Skip DL DCI - we only extract UL grants
                else:
                    # Unknown format, skip this DCI
                    dci_size = DL_DCI_SIZE  # Assume minimum size

                dci_index += dci_size

            # Move to next record
            index = dci_index

        return results

    def _decode_b885_v196617(self, data, timestamp_us):
        """
        Decode B885 v196617 format
        Use structured parsing similar to B883, with beacon validation
        """
        results = []

        if len(data) < 16:
            return results

        # Try to use sub-header structure like B883
        # num_record should be at offset 15
        num_record = data[15]

        # Sanity check: if num_record is too large, fall back to beacon search
        if num_record > 20 or num_record == 0:
            return self._decode_b885_v196617_beacon_search(data, timestamp_us)

        index = 16  # Records start after sub-header

        for _ in range(num_record):
            if index + 8 > len(data):
                break

            # Record Header: [Slot][Numerology][Frame_L][Frame_H][...]
            slot = data[index]
            numerology_id = data[index + 1] & 0x07
            frame = data[index + 2] | ((data[index + 3] & 0x03) << 8)

            # Validate slot/frame
            if slot >= 80 or frame >= 1024:
                index += 40  # Skip invalid record
                continue

            tti = self.calculate_tti(frame, slot, numerology_id)

            # Search for 0x82 beacon within this record's range (next ~60 bytes)
            record_end = min(index + 80, len(data) - 8)

            for beacon_pos in range(index + 4, record_end):
                if data[beacon_pos:beacon_pos+4] == b'\x82\x00\x00\x00':
                    # Found beacon, extract DCI fields
                    raw_dci0 = struct.unpack('<I', data[beacon_pos+4:beacon_pos+8])[0]

                    mcs_index = (raw_dci0 >> 10) & 0x1F
                    rv = (raw_dci0 >> 7) & 0x3
                    symbol_alloc_index = (raw_dci0 >> 15) & 0x1
                    rb_assignment = (raw_dci0 >> 17) & 0x1FFF

                    record = {
                        "timestamp_us": timestamp_us,
                        "tti": tti,
                        "slot": slot,
                        "frame": frame,
                        "numerology": numerology_id,
                        "mcs_index": mcs_index,
                        "rv": rv,
                        "symbol_alloc_index": symbol_alloc_index,
                        "rb_assignment": rb_assignment
                    }
                    results.append(record)
                    break

            # Move to next record (estimate ~40-60 bytes per record)
            index += 48

        return results

    def _decode_b885_v196617_beacon_search(self, data, timestamp_us):
        """
        Fallback beacon search method with strict validation
        """
        results = []

        # Collect all potential beacons first
        beacon_positions = []
        for i in range(len(data) - 7):
            if data[i:i+4] == b'\x82\x00\x00\x00':
                beacon_positions.append(i)

        if not beacon_positions:
            return results

        # Extract records and collect valid frames first
        valid_frames = []

        for beacon_pos in beacon_positions:
            slot_info_pos = beacon_pos - 4
            if slot_info_pos < 0:
                continue

            slot = data[slot_info_pos]
            numerology_id = data[slot_info_pos + 1] & 0x07
            frame = data[slot_info_pos + 2] | ((data[slot_info_pos + 3] & 0x03) << 8)

            # Basic validation
            if slot >= 80 or frame >= 1024:
                continue

            valid_frames.append((beacon_pos, slot, frame, numerology_id))

        # If we have multiple records, check for outlier frames
        if len(valid_frames) > 2:
            frames_only = [f[2] for f in valid_frames]
            # Calculate median frame to detect outliers
            sorted_frames = sorted(frames_only)
            median_frame = sorted_frames[len(sorted_frames) // 2]

            # Filter out frames that are too far from median (likely false beacons)
            filtered_frames = []
            for beacon_pos, slot, frame, numerology_id in valid_frames:
                frame_diff = abs(frame - median_frame)
                # Allow wrap-around
                if frame_diff > 512:
                    frame_diff = 1024 - frame_diff
                # If frame is within reasonable range of median, keep it
                if frame_diff <= 100:
                    filtered_frames.append((beacon_pos, slot, frame, numerology_id))

            valid_frames = filtered_frames if filtered_frames else valid_frames

        # Now extract DCI for valid beacons
        for beacon_pos, slot, frame, numerology_id in valid_frames:
            if beacon_pos + 8 > len(data):
                continue

            tti = self.calculate_tti(frame, slot, numerology_id)

            raw_dci0 = struct.unpack('<I', data[beacon_pos+4:beacon_pos+8])[0]

            mcs_index = (raw_dci0 >> 10) & 0x1F
            rv = (raw_dci0 >> 7) & 0x3
            symbol_alloc_index = (raw_dci0 >> 15) & 0x1
            rb_assignment = (raw_dci0 >> 17) & 0x1FFF

            record = {
                "timestamp_us": timestamp_us,
                "tti": tti,
                "slot": slot,
                "frame": frame,
                "numerology": numerology_id,
                "mcs_index": mcs_index,
                "rv": rv,
                "symbol_alloc_index": symbol_alloc_index,
                "rb_assignment": rb_assignment
            }
            results.append(record)

        return results

    def _search_tti_near_beacon(self, data, beacon_pos, prev_slot, prev_frame):
        """
        Fallback search for TTI information close to a 0x82 beacon when the expected
        slot-info block (beacon-4) is zeroed out.
        """
        candidate_offsets = [16, 32, 20, 24, 28, 12, 36, 40, 44, 48, 52, 56]
        best = (0, 0, 0)
        best_score = -1

        for offset in candidate_offsets:
            tti_pos = beacon_pos - offset
            if tti_pos < 0 or tti_pos + 4 > len(data):
                continue

            slot = data[tti_pos]
            numerology_id = data[tti_pos + 1] & 0x07
            frame = data[tti_pos + 2] | ((data[tti_pos + 3] & 0x03) << 8)

            # Basic sanity checks
            if slot >= 80 or frame >= 1024:
                continue

            score = 0
            if offset in (16, 32):
                score += 5
            if prev_frame is not None:
                if frame == prev_frame:
                    score += 5
                elif abs(frame - prev_frame) <= 2:
                    score += 2
            if prev_slot is not None:
                if slot == prev_slot:
                    score += 4
                elif slot == (prev_slot + 1) % 10:
                    score += 3

            if score > best_score:
                best_score = score
                best = (slot, frame, numerology_id)

        return best

    def buffer_b872_data(self, records):
        """Buffer B872 data for batch writing"""
        for record in records:
            # Only retain TB entries that carry a BSR MAC CE
            if record['bsr_lcg'] < 0:
                continue
            line = "{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}".format(
                record['timestamp_us'],
                record['tti'],
                record['slot'],
                record['frame'],
                record['numerology'],
                record['grant_size'],
                record['bytes_built'],
                record['mce_type'],
                record['bsr_lcg'],
                record['buffer_size'][0],
                record['buffer_size'][1],
                record['buffer_size'][2],
                record['buffer_size'][3],
                record['buffer_size'][4],
                record['buffer_size'][5],
                record['buffer_size'][6],
                record['buffer_size'][7]
            )
            self.b872_buffer.append(line)

    def buffer_b883_data(self, records):
        """Buffer B883 data for batch writing"""
        for record in records:
            line = "{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}".format(
                record['timestamp_us'],
                record['tti'],
                record['slot'],
                record['frame'],
                record['numerology'],
                record['phychan_type'],
                record['rnti'],
                record['num_pucch'],
                record['second_hop_rb'],
                # New PUSCH fields
                record['mcs'],
                record['mcs_table'],
                record['num_rbs'],
                record['tb_size'],
                record['rv_index'],
                record['harq_id'],
                record['rb_start'],
                record['num_symbols']
            )
            self.b883_buffer.append(line)

    def buffer_b885_data(self, records):
        """Buffer B885 data for batch writing"""
        for record in records:
            line = "{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}".format(
                record['timestamp_us'],
                record['tti'],
                record['slot'],
                record['frame'],
                record['numerology'],
                record['mcs_index'],
                record['rv'],
                record['symbol_alloc_index'],
                record['rb_assignment']
            )
            self.b885_buffer.append(line)

    def write_buffered_data(self):
        """Write all buffered data to files"""
        # Write B872 data
        if self.b872_buffer:
            with open(self.b872_file, 'a') as f:
                for line in self.b872_buffer:
                    f.write(line + "\n")
            print("Wrote {} B872 records".format(len(self.b872_buffer)))
            self.b872_buffer.clear()

        # Write B883 data
        if self.b883_buffer:
            with open(self.b883_file, 'a') as f:
                for line in self.b883_buffer:
                    f.write(line + "\n")
            print("Wrote {} B883 records".format(len(self.b883_buffer)))
            self.b883_buffer.clear()

        # Write B885 data
        if self.b885_buffer:
            with open(self.b885_file, 'a') as f:
                for line in self.b885_buffer:
                    f.write(line + "\n")
            print("Wrote {} B885 records".format(len(self.b885_buffer)))
            self.b885_buffer.clear()

    def parse_and_log(self, hdlc_stream):
        """Parse HDLC data stream and extract 5G NR log data"""
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

            # Parse header: length(2) + logcode(2) + timestamp(8)
            msg_len = (data[1] << 8) | data[0]
            logcode = (data[3] << 8) | data[2]
            timestamp_us = int.from_bytes(data[4:12], 'little')
            payload = data[12 : 12 + msg_len]

            # Process based on logcode
            if logcode == 0xB872:
                records = self.decode_b872_payload(payload, timestamp_us)
                if records:
                    self.buffer_b872_data(records)
            elif logcode == 0xB883:
                records = self.decode_b883_payload(payload, timestamp_us)
                if records:
                    self.buffer_b883_data(records)
            elif logcode == 0xB885:
                records = self.decode_b885_payload(payload, timestamp_us)
                if records:
                    self.buffer_b885_data(records)

        # Write data periodically
        total_buffer_size = len(self.b872_buffer) + len(self.b883_buffer) + len(self.b885_buffer)
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
DEFAULT_LOGCODES = [0xB872, 0xB883, 0xB885]  # 5G NR logcodes

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
    parser = NR5GDiagParser()

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
        print("\nSubscribing to 5G NR logcodes (B872, B883, B885)...")
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

        print("\n" + "="*80)
        print("5G NR Monitoring started. Press Ctrl-C to exit.")
        print("="*80)
        print("Output files:")
        print("  1. b872_ul_tb_data.txt: UL Transport Block with BSR")
        print("  2. b883_phychan_data.txt: Physical Channel (PUSCH/PUCCH)")
        print("  3. b885_pdcch_data.txt: PDCCH UL Grant")
        print("  4. raw_tcp_data.txt: Raw TCP data (hex dump)")
        print("")

        receive_buffer = b''

        while True:
            try:
                client_socket.settimeout(1.0)
                new_data = client_socket.recv(65536)

                if not new_data:
                    print("Connection closed by server")
                    break

                # Get current timestamp for raw data logging
                ts_python_recv = time.time()

                # Log ALL raw TCP data to file
                parser.log_raw_tcp_data(new_data, ts_python_recv)

                receive_buffer += new_data

                # Process data with timestamp header
                header_size = 8  # sizeof(double)

                while len(receive_buffer) >= header_size:
                    # Skip timestamp header (not used in simplified version)
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

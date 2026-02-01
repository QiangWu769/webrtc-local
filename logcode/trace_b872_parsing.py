#!/usr/bin/env python3
"""
Trace through B872 parsing step by step with actual binary data from QXDM.
Verifies that the parsing code in diag_get_5g_ratio.py is correct.
"""

import re
import struct

def parse_hex_dump(hex_text):
    """Parse QXDM hex dump format to bytes"""
    result = bytearray()
    for line in hex_text.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        # Format: "0000  XX XX XX XX ..." (note: two spaces)
        match = re.match(r'([0-9A-Fa-f]{4})\s+(.+)', line)
        if match:
            hex_part = match.group(2)
            # Extract only the hex bytes (first 16 pairs, before ASCII)
            # Format: "XX XX XX XX XX XX XX XX  XX XX XX XX XX XX XX XX  ASCII..."
            parts = hex_part.split()
            for p in parts:
                if len(p) == 2 and all(c in '0123456789ABCDEFabcdef' for c in p):
                    result.append(int(p, 16))
                else:
                    break  # Stop at non-hex (ASCII part)
    return bytes(result)

def extract_b872_records(filepath):
    """Extract B872 records with their hex data and parsed values from QXDM text"""
    records = []

    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    # Split into individual log entries by timestamp pattern
    entries = re.split(r'\n(?=\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+)', content)

    for entry in entries:
        if 'Log Code : 0xB872' not in entry:
            continue

        # Extract timestamp
        ts_match = re.match(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+)', entry)
        timestamp = ts_match.group(1) if ts_match else "Unknown"

        # Extract hex dump (after "Binary:")
        binary_match = re.search(r'Binary:\n((?:[0-9A-Fa-f]{4}\s+.+\n)+)', entry)
        if not binary_match:
            continue

        hex_dump = binary_match.group(1)
        binary = parse_hex_dump(hex_dump)

        # Extract parsed fields from QXDM
        version_match = re.search(r'Version\s*:\s*(\d+)', entry)
        num_tti_match = re.search(r'Num TTI\s*:\s*(\d+)', entry)

        # Extract TTI entries (use FN for frame number)
        tti_entries = []
        # Pattern for slot and frame (FN)
        tti_blocks = re.findall(r'Slot Number\s*:\s*(\d+)\s*\n\s*FN\s*:\s*(\d+)\s*\n\s*Num TB\s*:\s*(\d+)', entry)
        for slot, fn, num_tb in tti_blocks:
            tti_entries.append({
                'slot': int(slot),
                'frame': int(fn),
                'num_tb': int(num_tb)
            })

        # Extract BSR info
        bsr_entries = []
        # S-BSR pattern
        sbsr_matches = re.findall(r'MCE Type\s*:\s*S-BSR.*?BSR Index\s*:\s*(\d+)\s*\n\s*BSR LCG\s*:\s*(\d+)', entry, re.DOTALL)
        for bsr_idx, lcg in sbsr_matches:
            bsr_entries.append({
                'type': 'S-BSR',
                'lcg': int(lcg),
                'bsr_index': int(bsr_idx)
            })

        # L-BSR pattern - more complex, need to handle multiple LCGs
        lbsr_blocks = re.finditer(r'MCE Type\s*:\s*L-BSR.*?(?=MCE Type|McePayload|\Z)', entry, re.DOTALL)
        for lbsr_match in lbsr_blocks:
            lbsr_text = lbsr_match.group(0)
            lcg_matches = re.findall(r'LCG\s*:\s*(\d+)\s*\n\s*Buffer Size Index\s*:\s*(\d+)', lbsr_text)
            for lcg, bsr_idx in lcg_matches:
                bsr_entries.append({
                    'type': 'L-BSR',
                    'lcg': int(lcg),
                    'bsr_index': int(bsr_idx)
                })

        records.append({
            'timestamp': timestamp,
            'binary': binary,
            'hex_dump': hex_dump,
            'qxdm_version': int(version_match.group(1)) if version_match else None,
            'qxdm_num_tti': int(num_tti_match.group(1)) if num_tti_match else None,
            'qxdm_tti_entries': tti_entries,
            'qxdm_bsr_entries': bsr_entries,
        })

    return records

def trace_b872_parsing(binary, skip_diag_header=True):
    """Trace through B872 parsing exactly as diag_get_5g_ratio.py does it"""
    DIAG_HEADER_SIZE = 12  # Length(2) + LogCode(2) + Timestamp(8)

    if skip_diag_header:
        data = bytearray(binary[DIAG_HEADER_SIZE:])
        print(f"  Skipping {DIAG_HEADER_SIZE}-byte DIAG header")
        print(f"  DIAG header: {binary[:DIAG_HEADER_SIZE].hex(' ')}")
    else:
        data = bytearray(binary)

    print(f"  Payload length: {len(data)} bytes")
    print(f"  First 16 bytes of payload: {data[:min(16, len(data))].hex(' ')}")

    if len(data) < 8:
        print("  ERROR: Payload too short")
        return None

    index = 0

    # S_H header (8 bytes) - exactly as in diag_get_5g_ratio.py
    version = data[index]  # Line 1193
    num_tti = data[index + 4]  # Line 1194
    index += 8  # Line 1195

    print(f"\n  S_H Header (8 bytes):")
    print(f"    Header bytes: {data[0:8].hex(' ')}")
    print(f"    version = data[0] = {version}")
    print(f"    num_tti = data[4] = {num_tti}")

    results = []
    tti_entries = []

    for i in range(num_tti):
        if index + 8 > len(data):
            print(f"    ERROR: Not enough data for TTI {i}")
            break

        # TTI Header - exactly as in diag_get_5g_ratio.py
        slot_number = data[index]  # Line 1202
        frame = ((data[index + 3] & 0x03) << 8) | data[index + 2]  # Line 1203
        num_tb = data[index + 4] & 0x0F  # Line 1204

        print(f"\n  TTI {i} Header (at offset {index}):")
        print(f"    Header bytes: {data[index:index+8].hex(' ')}")
        print(f"    slot_number = data[{index}] = {slot_number}")
        print(f"    frame = ((data[{index}+3] & 0x03) << 8) | data[{index}+2] = {frame}")
        print(f"    num_tb = data[{index}+4] & 0x0F = {num_tb}")

        tti_entries.append({'slot': slot_number, 'frame': frame, 'num_tb': num_tb})
        index += 8  # Line 1205

        for j in range(num_tb):
            if index + 20 > len(data):
                print(f"      ERROR: Not enough data for TB {j}")
                break

            tb_start = index

            # TB Header
            numerology = data[tb_start + 1] & 0x07  # Line 1214
            grant_size = struct.unpack('<I', data[tb_start+4:tb_start+8])[0]  # Line 1217
            bytes_built = struct.unpack('<I', data[tb_start+8:tb_start+12])[0]  # Line 1220
            mce_length = data[tb_start + 16] & 0x3F  # Line 1223

            print(f"\n    TB {j} Header (at offset {tb_start}):")
            print(f"      Header bytes: {data[tb_start:tb_start+20].hex(' ')}")
            print(f"      numerology = {numerology}")
            print(f"      grant_size = {grant_size}")
            print(f"      bytes_built = {bytes_built}")
            print(f"      mce_length = {mce_length}")

            index = tb_start + 20  # Line 1226

            # Parse MCE
            if mce_length > 0 and index + mce_length <= len(data):
                mce_raw_bytes = data[index:index + mce_length]
                print(f"      MCE raw bytes: {mce_raw_bytes.hex(' ')}")

                step = 0
                mce_start = index

                while step < mce_length:
                    mce_type_raw = data[mce_start + step]
                    mce_type = mce_type_raw & 0x3F
                    step += 1

                    if mce_type == 62:  # L-BSR
                        lcg_bitmap = data[mce_start + step]
                        step += 1
                        print(f"      L-BSR: mce_type_raw=0x{mce_type_raw:02X}, lcg_bitmap=0b{lcg_bitmap:08b}")

                        for k in range(8):
                            if lcg_bitmap & (1 << k):
                                if mce_start + step < len(data):
                                    raw_byte = data[mce_start + step]
                                    bsr_index = raw_byte & 0x3F
                                    print(f"        LCG {k}: raw=0x{raw_byte:02X}, bsr_index={bsr_index}")
                                    results.append({
                                        'type': 'L-BSR',
                                        'frame': frame,
                                        'slot': slot_number,
                                        'lcg': k,
                                        'bsr_index': bsr_index
                                    })
                                    step += 1

                    elif mce_type == 61:  # S-BSR
                        raw_byte = data[mce_start + step]
                        bsr_lcg = (raw_byte & 0xE0) >> 5
                        buffer_size = raw_byte & 0x1F
                        step += 1
                        print(f"      S-BSR: mce_type_raw=0x{mce_type_raw:02X}, raw=0x{raw_byte:02X}, lcg={bsr_lcg}, bsr_index={buffer_size}")
                        results.append({
                            'type': 'S-BSR',
                            'frame': frame,
                            'slot': slot_number,
                            'lcg': bsr_lcg,
                            'bsr_index': buffer_size
                        })

                    elif mce_type == 57:  # S-PHR
                        step += 2
                        print(f"      S-PHR: mce_type=0x{mce_type_raw:02X}")

                    else:
                        print(f"      Unknown MCE type: 0x{mce_type_raw:02X}")
                        step = mce_length

                index += mce_length

    return {'tti_entries': tti_entries, 'bsr_entries': results}

def main():
    filepath = '/home/qwu26/webrtc-local/logcode/tmobile_5g.txt'
    print("="*80)
    print("B872 Parsing Trace - Verifying diag_get_5g_ratio.py")
    print("="*80)

    records = extract_b872_records(filepath)
    print(f"\nExtracted {len(records)} B872 records from QXDM")

    # Find records with BSR data for verification
    records_with_bsr = [r for r in records if r['qxdm_bsr_entries']]
    print(f"Records with BSR data: {len(records_with_bsr)}")

    # Trace a few records
    for i, record in enumerate(records[:3]):  # First 3 records
        print(f"\n{'='*80}")
        print(f"Record {i+1}: {record['timestamp']}")
        print(f"{'='*80}")
        print(f"QXDM Version: {record['qxdm_version']}")
        print(f"QXDM Num TTI: {record['qxdm_num_tti']}")
        print(f"QXDM TTI Entries: {record['qxdm_tti_entries']}")
        print(f"QXDM BSR Entries: {record['qxdm_bsr_entries']}")
        print(f"\nBinary length: {len(record['binary'])} bytes")
        print(f"\nTracing parse:")

        parsed_results = trace_b872_parsing(record['binary'], skip_diag_header=True)

        if parsed_results:
            print(f"\n  PARSED TTI Entries: {parsed_results['tti_entries']}")
            print(f"  PARSED BSR Entries: {parsed_results['bsr_entries']}")

            # Compare
            print(f"\n  COMPARISON:")
            qxdm_tti = record['qxdm_tti_entries']
            parsed_tti = parsed_results['tti_entries']
            for j, (q, p) in enumerate(zip(qxdm_tti, parsed_tti)):
                slot_ok = "✓" if q['slot'] == p['slot'] else "✗"
                frame_ok = "✓" if q['frame'] == p['frame'] else "✗"
                print(f"    TTI {j}: QXDM slot={q['slot']}, parsed slot={p['slot']} {slot_ok}")
                print(f"            QXDM frame={q['frame']}, parsed frame={p['frame']} {frame_ok}")

    # Now verify ALL records
    print(f"\n{'='*80}")
    print("Verifying ALL B872 records")
    print("="*80)

    slot_matches = 0
    slot_total = 0
    frame_matches = 0
    frame_total = 0
    bsr_matches = 0
    bsr_total = 0
    version_matches = 0
    version_total = 0
    num_tti_matches = 0
    num_tti_total = 0

    for record in records:
        binary = record['binary']
        if len(binary) < 20:
            continue

        # Skip DIAG header
        data = bytearray(binary[12:])
        if len(data) < 8:
            continue

        # Parse header
        version = data[0]
        num_tti = data[4]

        # Verify version
        if record['qxdm_version'] is not None:
            version_total += 1
            if version == record['qxdm_version']:
                version_matches += 1

        # Verify num_tti
        if record['qxdm_num_tti'] is not None:
            num_tti_total += 1
            if num_tti == record['qxdm_num_tti']:
                num_tti_matches += 1

        index = 8
        parsed_tti = []

        for i in range(num_tti):
            if index + 8 > len(data):
                break

            slot = data[index]
            frame = ((data[index + 3] & 0x03) << 8) | data[index + 2]
            num_tb = data[index + 4] & 0x0F
            parsed_tti.append({'slot': slot, 'frame': frame, 'num_tb': num_tb})
            index += 8

            for j in range(num_tb):
                if index + 20 > len(data):
                    break
                mce_length = data[index + 16] & 0x3F
                index += 20
                if mce_length > 0:
                    index += mce_length

        # Compare with QXDM
        qxdm_tti = record['qxdm_tti_entries']
        for pi, ptti in enumerate(parsed_tti[:len(qxdm_tti)]):
            if pi < len(qxdm_tti):
                qtti = qxdm_tti[pi]
                slot_total += 1
                frame_total += 1
                if ptti['slot'] == qtti['slot']:
                    slot_matches += 1
                if ptti['frame'] == qtti['frame']:
                    frame_matches += 1

    print(f"\nVersion verification: {version_matches}/{version_total} ({100*version_matches/version_total:.2f}%)" if version_total > 0 else "No version data")
    print(f"Num TTI verification: {num_tti_matches}/{num_tti_total} ({100*num_tti_matches/num_tti_total:.2f}%)" if num_tti_total > 0 else "No num_tti data")
    print(f"Slot verification: {slot_matches}/{slot_total} ({100*slot_matches/slot_total:.2f}%)" if slot_total > 0 else "No slot data")
    print(f"Frame verification: {frame_matches}/{frame_total} ({100*frame_matches/frame_total:.2f}%)" if frame_total > 0 else "No frame data")

    print(f"\n{'='*80}")
    print("CONCLUSION")
    print("="*80)
    if slot_total > 0 and slot_matches == slot_total and frame_matches == frame_total:
        print("✓ The parsing code in diag_get_5g_ratio.py correctly parses B872 by structure offset")
        print("✓ All slot and frame values match QXDM reference")
    elif slot_total > 0:
        print(f"Some mismatches found - {slot_total - slot_matches} slot mismatches, {frame_total - frame_matches} frame mismatches")
    else:
        print("No data to verify")

if __name__ == '__main__':
    main()

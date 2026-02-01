#!/usr/bin/env python3
"""
Verify L-BSR parsing in diag_get_5g_ratio.py by comparing with QXDM output.
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
        match = re.match(r'([0-9A-Fa-f]{4})\s+(.+)', line)
        if match:
            hex_part = match.group(2)
            parts = hex_part.split()
            for p in parts:
                if len(p) == 2 and all(c in '0123456789ABCDEFabcdef' for c in p):
                    result.append(int(p, 16))
                else:
                    break
    return bytes(result)

def extract_b872_records_with_lbsr(filepath):
    """Extract B872 records that have L-BSR data"""
    records = []

    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    entries = re.split(r'\n(?=\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+)', content)

    for entry in entries:
        if 'Log Code : 0xB872' not in entry:
            continue
        if 'MCE Type : L-BSR' not in entry:
            continue

        ts_match = re.match(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+)', entry)
        timestamp = ts_match.group(1) if ts_match else "Unknown"

        binary_match = re.search(r'Binary:\n((?:[0-9A-Fa-f]{4}\s+.+\n)+)', entry)
        if not binary_match:
            continue

        hex_dump = binary_match.group(1)
        binary = parse_hex_dump(hex_dump)

        # Extract L-BSR info from QXDM text
        lbsr_entries = []

        # Split by TTI entries (marked by "[X]" followed by "TTI Info Meta")
        tti_pattern = r'\[\d+\]\s*\n\s*TTI Info Meta.*?(?=\[\d+\]\s*\n\s*TTI Info Meta|Binary:|\Z)'
        for tti_match in re.finditer(tti_pattern, entry, re.DOTALL):
            tti_text = tti_match.group(0)

            # Get slot and frame
            slot_match = re.search(r'Slot Number\s*:\s*(\d+)', tti_text)
            frame_match = re.search(r'FN\s*:\s*(\d+)', tti_text)
            if not slot_match or not frame_match:
                continue

            slot = int(slot_match.group(1))
            frame = int(frame_match.group(1))

            # Check for L-BSR in this TTI
            if 'MCE Type : L-BSR' in tti_text:
                # Extract LCG values from LongBsr section
                longbsr_match = re.search(r'LongBsr\s*(.*?)(?=\[\d+\]|Binary:|\Z)', tti_text, re.DOTALL)
                if longbsr_match:
                    longbsr_text = longbsr_match.group(1)
                    lcg_values = {}
                    for lcg_match in re.finditer(r'LCG(\d+)\s*:\s*(\d+)', longbsr_text):
                        lcg_id = int(lcg_match.group(1))
                        bsr_idx = int(lcg_match.group(2))
                        lcg_values[lcg_id] = bsr_idx

                    lbsr_entries.append({
                        'slot': slot,
                        'frame': frame,
                        'lcg_values': lcg_values
                    })

        records.append({
            'timestamp': timestamp,
            'binary': binary,
            'qxdm_lbsr': lbsr_entries,
        })

    return records

def parse_b872_for_lbsr(binary):
    """Parse B872 binary to extract L-BSR data"""
    DIAG_HEADER_SIZE = 12
    data = bytearray(binary[DIAG_HEADER_SIZE:])

    if len(data) < 8:
        return []

    num_tti = data[4]
    index = 8

    lbsr_results = []

    for i in range(num_tti):
        if index + 8 > len(data):
            break

        slot = data[index]
        frame = ((data[index + 3] & 0x03) << 8) | data[index + 2]
        num_tb = data[index + 4] & 0x0F
        index += 8

        for j in range(num_tb):
            if index + 20 > len(data):
                break

            mce_length = data[index + 16] & 0x3F
            index += 20

            if mce_length > 0 and index + mce_length <= len(data):
                step = 0
                mce_start = index

                while step < mce_length:
                    mce_type_raw = data[mce_start + step]
                    mce_type = mce_type_raw & 0x3F
                    step += 1

                    if mce_type == 62:  # L-BSR
                        lcg_bitmap = data[mce_start + step]
                        step += 1

                        lcg_values = {}
                        for k in range(8):
                            if lcg_bitmap & (1 << k):
                                if mce_start + step < len(data):
                                    raw_byte = data[mce_start + step]
                                    bsr_index = raw_byte & 0x3F
                                    lcg_values[k] = bsr_index
                                    step += 1

                        lbsr_results.append({
                            'slot': slot,
                            'frame': frame,
                            'lcg_bitmap': lcg_bitmap,
                            'lcg_values': lcg_values
                        })

                    elif mce_type == 61:  # S-BSR
                        step += 1
                    elif mce_type == 57:  # S-PHR
                        step += 2
                    else:
                        step = mce_length

                index += mce_length

    return lbsr_results

def main():
    filepath = '/home/qwu26/webrtc-local/logcode/tmobile_5g.txt'
    print("="*80)
    print("L-BSR Parsing Verification - diag_get_5g_ratio.py")
    print("="*80)

    records = extract_b872_records_with_lbsr(filepath)
    print(f"\nExtracted {len(records)} B872 records with L-BSR data")

    total_lbsr = 0
    matched_lbsr = 0
    mismatched_details = []

    for record in records:
        parsed_lbsr = parse_b872_for_lbsr(record['binary'])
        qxdm_lbsr = record['qxdm_lbsr']

        # Match by slot/frame
        for p in parsed_lbsr:
            for q in qxdm_lbsr:
                if p['slot'] == q['slot'] and p['frame'] == q['frame']:
                    total_lbsr += 1
                    # Compare LCG values
                    # Note: QXDM shows all 8 LCGs, but we only extract those in bitmap
                    all_match = True
                    for lcg_id, bsr_val in p['lcg_values'].items():
                        if lcg_id in q['lcg_values']:
                            if bsr_val != q['lcg_values'][lcg_id]:
                                all_match = False
                                mismatched_details.append({
                                    'timestamp': record['timestamp'],
                                    'slot': p['slot'],
                                    'frame': p['frame'],
                                    'parsed': p['lcg_values'],
                                    'qxdm': q['lcg_values']
                                })
                    if all_match:
                        matched_lbsr += 1
                    break

    print(f"\nL-BSR Verification Results:")
    print(f"  Total L-BSR entries found: {total_lbsr}")
    print(f"  Matched: {matched_lbsr}")
    print(f"  Mismatched: {total_lbsr - matched_lbsr}")

    if mismatched_details:
        print(f"\nMismatch details (first 5):")
        for m in mismatched_details[:5]:
            print(f"  {m['timestamp']}: slot={m['slot']}, frame={m['frame']}")
            print(f"    Parsed:  {m['parsed']}")
            print(f"    QXDM:    {m['qxdm']}")

    # Show some sample L-BSR entries
    print(f"\n{'='*80}")
    print("Sample L-BSR Trace (first 3 records with L-BSR)")
    print("="*80)

    for i, record in enumerate(records[:3]):
        print(f"\nRecord {i+1}: {record['timestamp']}")
        print(f"  QXDM L-BSR entries: {record['qxdm_lbsr']}")

        parsed = parse_b872_for_lbsr(record['binary'])
        print(f"  Parsed L-BSR entries: {parsed}")

    print(f"\n{'='*80}")
    print("CONCLUSION")
    print("="*80)
    if total_lbsr > 0:
        rate = 100.0 * matched_lbsr / total_lbsr if total_lbsr > 0 else 0
        print(f"L-BSR verification: {matched_lbsr}/{total_lbsr} ({rate:.2f}%)")
        if matched_lbsr == total_lbsr:
            print("✓ All L-BSR entries correctly parsed")
        else:
            print(f"✗ {total_lbsr - matched_lbsr} L-BSR entries have mismatches")
    else:
        print("No L-BSR data found to verify")

if __name__ == '__main__':
    main()

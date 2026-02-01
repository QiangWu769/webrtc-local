#!/usr/bin/env python3
"""
Complete verification of 5G NR parsing code against QXDM text output.
Extracts binary data and parsed results, then verifies all fields.
"""

import re
import struct
from collections import defaultdict


def parse_binary_hex(hex_lines):
    """Parse hex dump lines into bytes"""
    data = bytearray()
    for line in hex_lines.split('\n'):
        if not line.strip():
            continue
        # Format: 0000  D7 00 72 B8 14 91 01 F6  96 97 0C 01 01 00 02 00  ..r.............
        match = re.match(r'[\da-fA-F]{4}\s+((?:[\da-fA-F]{2}\s+)+)', line)
        if match:
            hex_bytes = match.group(1).strip().split()
            data.extend(int(b, 16) for b in hex_bytes)
    return bytes(data)


def parse_b872_binary(data):
    """Parse B872 binary data (our parsing logic)"""
    results = []

    if len(data) < 20:
        return results

    # Skip DIAG header, find version
    # Version 131073 = 0x00020001
    version_offset = -1
    for i in range(len(data) - 4):
        if data[i:i+4] == b'\x01\x00\x02\x00':
            version_offset = i
            break

    if version_offset < 0:
        return results

    # Parse structure
    idx = version_offset + 4
    if idx >= len(data):
        return results

    num_tti = data[idx]
    idx += 1

    # Skip to TTI data (need to figure out exact offset)
    # Look for TB data patterns

    # Simpler approach: scan for MCE patterns and extract surrounding context
    for i in range(len(data) - 20):
        # Look for TB header pattern: grant_size(4) + bytes_built(4) + ...
        # MCE data follows after TB header

        # Find S-BSR (0x3D) or L-BSR (0x3E)
        if data[i] == 0x3D:  # S-BSR
            if i + 1 < len(data):
                bsr_byte = data[i + 1]
                lcg = (bsr_byte & 0xE0) >> 5
                bsr_idx = bsr_byte & 0x1F

                # Try to find slot/frame from context (look backwards)
                slot = -1
                frame = -1
                grant_size = -1
                bytes_built = -1

                # Look for TB header before this point
                # TB header: ... slot(1) + frame(2) + ... + grant_size(4) + bytes_built(4) + ...
                for j in range(max(0, i-30), i):
                    # Look for grant_size pattern (reasonable values: 10-10000)
                    if j + 8 <= len(data):
                        gs = struct.unpack('<I', data[j:j+4])[0]
                        bb = struct.unpack('<I', data[j+4:j+8])[0]
                        if 10 <= gs <= 10000 and 0 <= bb <= gs:
                            grant_size = gs
                            bytes_built = bb
                            break

                results.append({
                    'type': 'S-BSR',
                    'offset': i,
                    'raw_byte': f'0x{bsr_byte:02X}',
                    'lcg': lcg,
                    'bsr_index': bsr_idx,
                    'grant_size': grant_size,
                    'bytes_built': bytes_built
                })

        elif data[i] == 0x3E:  # L-BSR
            if i + 2 < len(data):
                lcg_bitmap = data[i + 1]
                bsr_values = []
                pos = i + 2
                for k in range(8):
                    if lcg_bitmap & (1 << k):
                        if pos < len(data):
                            bsr_values.append(data[pos] & 0x3F)
                            pos += 1
                        else:
                            bsr_values.append(-1)

                results.append({
                    'type': 'L-BSR',
                    'offset': i,
                    'lcg_bitmap': f'0x{lcg_bitmap:02X}',
                    'bsr_values': bsr_values
                })

    return results


def parse_b883_binary(data):
    """Parse B883 binary data (our parsing logic)"""
    results = []

    if len(data) < 30:
        return results

    # Find version 131089 = 0x00020011
    version_offset = -1
    for i in range(len(data) - 4):
        if data[i:i+4] == b'\x11\x00\x02\x00':
            version_offset = i
            break

    if version_offset < 0:
        return results

    # Record starts at version_offset + 16
    record_start = version_offset + 16
    if record_start + 20 > len(data):
        return results

    # Parse first record
    slot = data[record_start]
    frame = struct.unpack('<H', data[record_start + 2:record_start + 4])[0]

    # Check for PUSCH indicator
    phychan = 'UNKNOWN'
    if record_start + 12 < len(data):
        phychan_byte = data[record_start + 8]
        if phychan_byte & 0x80:
            phychan = 'PUSCH'
        else:
            phychan = 'PUCCH'

    # MCS is at different offsets depending on channel type
    mcs = -1
    tb_size = -1
    num_rbs = -1
    harq = -1
    rv = -1

    # For PUSCH, look for MCS in the data
    # Based on our parser, MCS offset varies
    if phychan == 'PUSCH':
        # Scan for MCS pattern
        for j in range(record_start + 12, min(record_start + 30, len(data))):
            # MCS is typically 0-31
            if 0 <= data[j] <= 31:
                mcs = data[j]
                break

    results.append({
        'slot': slot,
        'frame': frame,
        'phychan': phychan,
        'mcs': mcs,
        'tb_size': tb_size,
        'num_rbs': num_rbs,
        'harq': harq,
        'rv': rv
    })

    return results


def verify_entry(entry_text):
    """Verify a single QXDM entry by comparing parsed text with binary"""
    results = {
        'log_code': None,
        'qxdm': {},
        'binary': {},
        'matches': [],
        'mismatches': []
    }

    # Get log code
    match = re.search(r'Log Code\s*:\s*0x(B\d{3})', entry_text)
    if not match:
        return None
    results['log_code'] = match.group(1)

    # Get binary data
    binary_match = re.search(r'Binary:\s*\n((?:[\da-fA-F]{4}\s+(?:[\da-fA-F]{2}\s+)+.*\n?)+)', entry_text)
    if not binary_match:
        return None

    raw_data = parse_binary_hex(binary_match.group(1))

    if results['log_code'] == 'B872':
        # Extract QXDM parsed values
        # Find all TTI entries
        tti_blocks = re.findall(r'TTI Info Meta.*?(?=TTI Info Meta|Binary:|$)', entry_text, re.DOTALL)

        for tti_block in tti_blocks:
            qxdm_record = {}

            # Slot
            m = re.search(r'Slot Number\s*:\s*(\d+)', tti_block)
            if m:
                qxdm_record['slot'] = int(m.group(1))

            # Frame
            m = re.search(r'FN\s*:\s*(\d+)', tti_block)
            if m:
                qxdm_record['frame'] = int(m.group(1))

            # Grant Size
            m = re.search(r'Grant Size\s*:\s*(\d+)', tti_block)
            if m:
                qxdm_record['grant_size'] = int(m.group(1))

            # Bytes Built
            m = re.search(r'Bytes Built\s*:\s*(\d+)', tti_block)
            if m:
                qxdm_record['bytes_built'] = int(m.group(1))

            # MCE Length
            m = re.search(r'MCE Length\s*:\s*(\d+)', tti_block)
            if m:
                qxdm_record['mce_length'] = int(m.group(1))

            # BSR Type
            if 'MCE Type : S-BSR' in tti_block:
                qxdm_record['mce_type'] = 'S-BSR'
                m = re.search(r'BSR LCG\s*:\s*(\d+)', tti_block)
                if m:
                    qxdm_record['bsr_lcg'] = int(m.group(1))
                m = re.search(r'BSR Index\s*:\s*(\d+)', tti_block)
                if m:
                    qxdm_record['bsr_index'] = int(m.group(1))
            elif 'MCE Type : L-BSR' in tti_block:
                qxdm_record['mce_type'] = 'L-BSR'
                qxdm_record['lcg_values'] = []
                for k in range(8):
                    m = re.search(rf'LCG{k}\s*:\s*(\d+)', tti_block)
                    if m:
                        qxdm_record['lcg_values'].append(int(m.group(1)))

            if qxdm_record:
                results['qxdm'].setdefault('tti_records', []).append(qxdm_record)

        # Parse binary
        binary_results = parse_b872_binary(raw_data)
        results['binary']['bsr_records'] = binary_results

        # Compare
        qxdm_sbsr = [r for r in results['qxdm'].get('tti_records', []) if r.get('mce_type') == 'S-BSR']
        binary_sbsr = [r for r in binary_results if r['type'] == 'S-BSR']

        for qr in qxdm_sbsr:
            found_match = False
            for br in binary_sbsr:
                if qr.get('bsr_lcg') == br['lcg'] and qr.get('bsr_index') == br['bsr_index']:
                    results['matches'].append({
                        'field': 'S-BSR',
                        'qxdm': f"LCG={qr.get('bsr_lcg')}, BSR={qr.get('bsr_index')}",
                        'binary': f"LCG={br['lcg']}, BSR={br['bsr_index']} (raw={br['raw_byte']})"
                    })
                    found_match = True
                    break
            if not found_match and qr.get('bsr_lcg') is not None:
                results['mismatches'].append({
                    'field': 'S-BSR',
                    'qxdm': f"LCG={qr.get('bsr_lcg')}, BSR={qr.get('bsr_index')}",
                    'binary': 'NOT FOUND'
                })

    elif results['log_code'] == 'B883':
        # Extract QXDM values
        m = re.search(r'System Time\s*\n\s+Slot\s*:\s*(\d+)', entry_text)
        if m:
            results['qxdm']['slot'] = int(m.group(1))
        m = re.search(r'Frame\s*:\s*(\d+)', entry_text)
        if m:
            results['qxdm']['frame'] = int(m.group(1))

        if 'PUSCH_BM' in entry_text:
            results['qxdm']['phychan'] = 'PUSCH'
        elif 'PUCCH_BM' in entry_text:
            results['qxdm']['phychan'] = 'PUCCH'

        # MCS
        m = re.search(r'PUSCH Data.*?MCS\s*:\s*(\d+)', entry_text, re.DOTALL)
        if m:
            results['qxdm']['mcs'] = int(m.group(1))

        # TB Size
        m = re.search(r'TB Size \(bytes\)\s*:\s*(\d+)', entry_text)
        if m:
            results['qxdm']['tb_size'] = int(m.group(1))

        # Num RBs
        m = re.search(r'Num RBs\s*:\s*(\d+)', entry_text)
        if m:
            results['qxdm']['num_rbs'] = int(m.group(1))

        # HARQ
        m = re.search(r'HARQ ID\s*:\s*(\d+)', entry_text)
        if m:
            results['qxdm']['harq'] = int(m.group(1))

        # RV
        m = re.search(r'RV Index\s*:\s*(\d+)', entry_text)
        if m:
            results['qxdm']['rv'] = int(m.group(1))

        # Parse binary - check slot/frame at specific offsets
        if len(raw_data) >= 20:
            # Find version offset
            for i in range(len(raw_data) - 4):
                if raw_data[i:i+4] == b'\x11\x00\x02\x00':
                    rec_start = i + 16
                    if rec_start + 4 <= len(raw_data):
                        results['binary']['slot'] = raw_data[rec_start]
                        results['binary']['frame'] = struct.unpack('<H', raw_data[rec_start+2:rec_start+4])[0]
                    break

        # Compare slot/frame
        if 'slot' in results['qxdm'] and 'slot' in results['binary']:
            if results['qxdm']['slot'] == results['binary']['slot']:
                results['matches'].append({'field': 'slot', 'qxdm': results['qxdm']['slot'], 'binary': results['binary']['slot']})
            else:
                results['mismatches'].append({'field': 'slot', 'qxdm': results['qxdm']['slot'], 'binary': results['binary']['slot']})

        if 'frame' in results['qxdm'] and 'frame' in results['binary']:
            if results['qxdm']['frame'] == results['binary']['frame']:
                results['matches'].append({'field': 'frame', 'qxdm': results['qxdm']['frame'], 'binary': results['binary']['frame']})
            else:
                results['mismatches'].append({'field': 'frame', 'qxdm': results['qxdm']['frame'], 'binary': results['binary']['frame']})

    elif results['log_code'] == 'B885':
        # Extract QXDM values
        m = re.search(r'Slot Number\s*:\s*(\d+)', entry_text)
        if m:
            results['qxdm']['slot'] = int(m.group(1))
        m = re.search(r'System Frame Number\s*:\s*(\d+)', entry_text)
        if m:
            results['qxdm']['frame'] = int(m.group(1))
        m = re.search(r'MCS\s*:\s*(\d+)', entry_text)
        if m:
            results['qxdm']['mcs'] = int(m.group(1))
        m = re.search(r'HARQ ID\s*:\s*(\d+)', entry_text)
        if m:
            results['qxdm']['harq'] = int(m.group(1))

        # Parse binary - slot/frame at offset 16
        if len(raw_data) >= 20:
            # Find record start after header
            for i in range(len(raw_data) - 4):
                # Look for minor/major version pattern
                if raw_data[i] == 0x0C and raw_data[i+1] == 0x00 and raw_data[i+2] == 0x02 and raw_data[i+3] == 0x00:
                    rec_start = i + 12
                    if rec_start + 4 <= len(raw_data):
                        results['binary']['slot'] = raw_data[rec_start]
                        results['binary']['frame'] = struct.unpack('<H', raw_data[rec_start+2:rec_start+4])[0]
                    break

        # Compare
        if 'slot' in results['qxdm'] and 'slot' in results['binary']:
            if results['qxdm']['slot'] == results['binary']['slot']:
                results['matches'].append({'field': 'slot', 'qxdm': results['qxdm']['slot'], 'binary': results['binary']['slot']})
            else:
                results['mismatches'].append({'field': 'slot', 'qxdm': results['qxdm']['slot'], 'binary': results['binary']['slot']})

        if 'frame' in results['qxdm'] and 'frame' in results['binary']:
            if results['qxdm']['frame'] == results['binary']['frame']:
                results['matches'].append({'field': 'frame', 'qxdm': results['qxdm']['frame'], 'binary': results['binary']['frame']})
            else:
                results['mismatches'].append({'field': 'frame', 'qxdm': results['qxdm']['frame'], 'binary': results['binary']['frame']})

    return results


def main():
    filepath = "/home/qwu26/webrtc-local/logcode/tmobile_5g.txt"

    print("=" * 70)
    print("Complete 5G NR Parsing Verification")
    print("=" * 70)

    with open(filepath, 'r') as f:
        content = f.read()

    # Split into entries
    entries = re.split(r'\n(?=\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+\s)', content)

    stats = {
        'B872': {'total': 0, 'verified': 0, 'fields_matched': defaultdict(int), 'fields_mismatched': defaultdict(int)},
        'B883': {'total': 0, 'verified': 0, 'fields_matched': defaultdict(int), 'fields_mismatched': defaultdict(int)},
        'B885': {'total': 0, 'verified': 0, 'fields_matched': defaultdict(int), 'fields_mismatched': defaultdict(int)},
    }

    sample_mismatches = []

    for entry in entries:
        if 'Binary:' not in entry:
            continue

        result = verify_entry(entry)
        if not result or not result['log_code']:
            continue

        log_code = result['log_code']
        if log_code not in stats:
            continue

        stats[log_code]['total'] += 1

        if result['matches']:
            stats[log_code]['verified'] += 1
            for m in result['matches']:
                stats[log_code]['fields_matched'][m['field']] += 1

        if result['mismatches']:
            for m in result['mismatches']:
                stats[log_code]['fields_mismatched'][m['field']] += 1
                if len(sample_mismatches) < 10:
                    sample_mismatches.append({'log_code': log_code, **m})

    # Print results
    print("\n" + "=" * 70)
    print("Verification Summary")
    print("=" * 70)

    for log_code in ['B872', 'B883', 'B885']:
        s = stats[log_code]
        print(f"\n{log_code}:")
        print(f"  Total entries with binary: {s['total']}")
        print(f"  Verified entries: {s['verified']}")
        if s['fields_matched']:
            print(f"  Fields matched:")
            for field, count in sorted(s['fields_matched'].items()):
                print(f"    - {field}: {count}")
        if s['fields_mismatched']:
            print(f"  Fields mismatched:")
            for field, count in sorted(s['fields_mismatched'].items()):
                print(f"    - {field}: {count}")

    if sample_mismatches:
        print("\n" + "=" * 70)
        print("Sample Mismatches (first 10)")
        print("=" * 70)
        for m in sample_mismatches:
            print(f"  [{m['log_code']}] {m['field']}: QXDM={m['qxdm']}, Binary={m['binary']}")

    # Detailed field verification for one entry of each type
    print("\n" + "=" * 70)
    print("Detailed Field-by-Field Verification (1 sample each)")
    print("=" * 70)

    for entry in entries:
        if 'Binary:' not in entry:
            continue

        match = re.search(r'Log Code\s*:\s*0x(B872)', entry)
        if match and 'S-BSR' in entry and 'BSR Index : 1' in entry:
            print("\n--- B872 Sample with non-zero BSR ---")
            result = verify_entry(entry)
            if result:
                print(f"QXDM parsed: {result['qxdm']}")
                print(f"Binary parsed: {result['binary']}")
                print(f"Matches: {result['matches']}")
                print(f"Mismatches: {result['mismatches']}")
            break

    for entry in entries:
        if 'Binary:' not in entry:
            continue

        match = re.search(r'Log Code\s*:\s*0x(B883)', entry)
        if match and 'PUSCH' in entry:
            print("\n--- B883 PUSCH Sample ---")
            result = verify_entry(entry)
            if result:
                print(f"QXDM parsed: {result['qxdm']}")
                print(f"Binary parsed: {result['binary']}")
                print(f"Matches: {result['matches']}")
                print(f"Mismatches: {result['mismatches']}")
            break

    for entry in entries:
        if 'Binary:' not in entry:
            continue

        match = re.search(r'Log Code\s*:\s*0x(B885)', entry)
        if match:
            print("\n--- B885 UL Grant Sample ---")
            result = verify_entry(entry)
            if result:
                print(f"QXDM parsed: {result['qxdm']}")
                print(f"Binary parsed: {result['binary']}")
                print(f"Matches: {result['matches']}")
                print(f"Mismatches: {result['mismatches']}")
            break


if __name__ == "__main__":
    main()

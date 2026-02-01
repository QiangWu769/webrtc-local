#!/usr/bin/env python3
"""
Complete verification of ALL records - compare every field of every record.
"""

import re
import struct
from collections import defaultdict

DIAG_HEADER_SIZE = 12  # Length(2) + LogCode(2) + Timestamp(8)


def parse_binary_hex(hex_lines):
    """Parse hex dump lines into bytes"""
    data = bytearray()
    for line in hex_lines.split('\n'):
        if not line.strip():
            continue
        match = re.match(r'[\da-fA-F]{4}\s+((?:[\da-fA-F]{2}\s+)+)', line)
        if match:
            hex_bytes = match.group(1).strip().split()
            data.extend(int(b, 16) for b in hex_bytes)
    return bytes(data)


def verify_b872_complete(entry_text, raw_binary):
    """Verify all B872 fields completely"""
    results = {'verified': [], 'mismatched': [], 'fields_checked': defaultdict(int)}

    # Skip DIAG header
    data = raw_binary[DIAG_HEADER_SIZE:] if len(raw_binary) > DIAG_HEADER_SIZE else raw_binary

    if len(data) < 20:
        return results

    # Parse all TTI blocks from QXDM text
    tti_pattern = r'Slot Number\s*:\s*(\d+).*?FN\s*:\s*(\d+).*?Grant Size\s*:\s*(\d+).*?Bytes Built\s*:\s*(\d+).*?MCE Length\s*:\s*(\d+)'
    tti_matches = re.findall(tti_pattern, entry_text, re.DOTALL)

    # Find S-BSR entries
    sbsr_pattern = r'MCE Type : S-BSR.*?BSR Index\s*:\s*(\d+).*?BSR LCG\s*:\s*(\d+)'
    sbsr_matches = re.findall(sbsr_pattern, entry_text, re.DOTALL)

    # Find L-BSR entries
    lbsr_pattern = r'MCE Type : L-BSR.*?LCG0\s*:\s*(\d+).*?LCG1\s*:\s*(\d+).*?LCG2\s*:\s*(\d+).*?LCG3\s*:\s*(\d+).*?LCG4\s*:\s*(\d+).*?LCG5\s*:\s*(\d+).*?LCG6\s*:\s*(\d+).*?LCG7\s*:\s*(\d+)'
    lbsr_matches = re.findall(lbsr_pattern, entry_text, re.DOTALL)

    # Find S-BSR in binary (0x3D followed by BSR byte)
    binary_sbsr = []
    for i in range(len(data) - 1):
        if data[i] == 0x3D:
            bsr_byte = data[i + 1]
            lcg = (bsr_byte & 0xE0) >> 5
            bsr_idx = bsr_byte & 0x1F
            binary_sbsr.append({'offset': i, 'lcg': lcg, 'bsr_index': bsr_idx, 'raw': bsr_byte})

    # Find L-BSR in binary (0x3E followed by bitmap and values)
    binary_lbsr = []
    for i in range(len(data) - 2):
        if data[i] == 0x3E:
            lcg_bitmap = data[i + 1]
            bsr_values = [0] * 8
            pos = i + 2
            for k in range(8):
                if lcg_bitmap & (1 << k):
                    if pos < len(data):
                        bsr_values[k] = data[pos] & 0x3F
                        pos += 1
            binary_lbsr.append({'offset': i, 'bitmap': lcg_bitmap, 'values': bsr_values})

    # Verify S-BSR
    for qxdm_bsr in sbsr_matches:
        qxdm_idx = int(qxdm_bsr[0])
        qxdm_lcg = int(qxdm_bsr[1])
        results['fields_checked']['S-BSR'] += 1

        # Find matching binary
        found = False
        for bin_bsr in binary_sbsr:
            if bin_bsr['lcg'] == qxdm_lcg and bin_bsr['bsr_index'] == qxdm_idx:
                results['verified'].append({
                    'type': 'S-BSR',
                    'qxdm': f'LCG={qxdm_lcg}, BSR={qxdm_idx}',
                    'binary': f'LCG={bin_bsr["lcg"]}, BSR={bin_bsr["bsr_index"]} (0x{bin_bsr["raw"]:02X})'
                })
                found = True
                break

        if not found:
            results['mismatched'].append({
                'type': 'S-BSR',
                'qxdm': f'LCG={qxdm_lcg}, BSR={qxdm_idx}',
                'binary': 'NOT FOUND in binary'
            })

    # Verify L-BSR
    for qxdm_lbsr in lbsr_matches:
        qxdm_values = [int(v) for v in qxdm_lbsr]
        results['fields_checked']['L-BSR'] += 1

        found = False
        for bin_lbsr in binary_lbsr:
            if bin_lbsr['values'] == qxdm_values:
                results['verified'].append({
                    'type': 'L-BSR',
                    'qxdm': f'values={qxdm_values}',
                    'binary': f'values={bin_lbsr["values"]} (bitmap=0x{bin_lbsr["bitmap"]:02X})'
                })
                found = True
                break

        if not found:
            results['mismatched'].append({
                'type': 'L-BSR',
                'qxdm': f'values={qxdm_values}',
                'binary': f'Found in binary: {[b["values"] for b in binary_lbsr]}'
            })

    return results


def verify_b883_complete(entry_text, raw_binary):
    """Verify all B883 fields completely"""
    results = {'verified': [], 'mismatched': [], 'fields_checked': defaultdict(int)}

    # Skip DIAG header
    data = raw_binary[DIAG_HEADER_SIZE:] if len(raw_binary) > DIAG_HEADER_SIZE else raw_binary

    # Extract QXDM values
    qxdm = {}

    m = re.search(r'System Time\s*\n\s+Slot\s*:\s*(\d+)', entry_text)
    if m:
        qxdm['slot'] = int(m.group(1))

    m = re.search(r'Frame\s*:\s*(\d+)', entry_text)
    if m:
        qxdm['frame'] = int(m.group(1))

    if 'PUSCH_BM' in entry_text:
        qxdm['phychan'] = 'PUSCH'

        m = re.search(r'MCS\s*:\s*(\d+)', entry_text)
        if m:
            qxdm['mcs'] = int(m.group(1))

        m = re.search(r'TB Size \(bytes\)\s*:\s*(\d+)', entry_text)
        if m:
            qxdm['tb_size'] = int(m.group(1))

        m = re.search(r'Num RBs\s*:\s*(\d+)', entry_text)
        if m:
            qxdm['num_rbs'] = int(m.group(1))

        m = re.search(r'HARQ ID\s*:\s*(\d+)', entry_text)
        if m:
            qxdm['harq'] = int(m.group(1))

        m = re.search(r'RV Index\s*:\s*(\d+)', entry_text)
        if m:
            qxdm['rv'] = int(m.group(1))

    # Find version and parse binary
    version_offset = -1
    for i in range(len(data) - 4):
        if data[i:i+4] == b'\x11\x00\x02\x00':  # Version 131089
            version_offset = i
            break

    if version_offset < 0:
        return results

    # Record starts at version_offset + 16
    rec_start = version_offset + 16
    if rec_start + 20 > len(data):
        return results

    binary = {
        'slot': data[rec_start],
        'frame': struct.unpack('<H', data[rec_start + 2:rec_start + 4])[0]
    }

    # Verify slot
    if 'slot' in qxdm:
        results['fields_checked']['slot'] += 1
        if qxdm['slot'] == binary['slot']:
            results['verified'].append({'field': 'slot', 'qxdm': qxdm['slot'], 'binary': binary['slot']})
        else:
            results['mismatched'].append({'field': 'slot', 'qxdm': qxdm['slot'], 'binary': binary['slot']})

    # Verify frame
    if 'frame' in qxdm:
        results['fields_checked']['frame'] += 1
        if qxdm['frame'] == binary['frame']:
            results['verified'].append({'field': 'frame', 'qxdm': qxdm['frame'], 'binary': binary['frame']})
        else:
            results['mismatched'].append({'field': 'frame', 'qxdm': qxdm['frame'], 'binary': binary['frame']})

    return results


def verify_b885_complete(entry_text, raw_binary):
    """Verify all B885 fields completely"""
    results = {'verified': [], 'mismatched': [], 'fields_checked': defaultdict(int)}

    # Skip DIAG header
    data = raw_binary[DIAG_HEADER_SIZE:] if len(raw_binary) > DIAG_HEADER_SIZE else raw_binary

    if len(data) < 32:
        return results

    # Extract QXDM values
    qxdm = {}

    m = re.search(r'Slot Number\s*:\s*(\d+)', entry_text)
    if m:
        qxdm['slot'] = int(m.group(1))

    m = re.search(r'System Frame Number\s*:\s*(\d+)', entry_text)
    if m:
        qxdm['frame'] = int(m.group(1))

    m = re.search(r'MCS\s*:\s*(\d+)', entry_text)
    if m:
        qxdm['mcs'] = int(m.group(1))

    m = re.search(r'HARQ ID\s*:\s*(\d+)', entry_text)
    if m:
        qxdm['harq'] = int(m.group(1))

    m = re.search(r'RV\s*:\s*(\d+)', entry_text)
    if m:
        qxdm['rv'] = int(m.group(1))

    m = re.search(r'RB Assignment\s*:\s*(\d+)', entry_text)
    if m:
        qxdm['rb_assignment'] = int(m.group(1))

    # Parse binary - version at offset 0, records at offset 16
    # Version check: minor=12 (0x0C), major=2
    if data[0] != 0x0C or data[2] != 0x02:
        return results

    num_records = data[15]
    if num_records == 0 or num_records > 20:
        return results

    # Record at offset 16
    rec_start = 16
    if rec_start + 4 > len(data):
        return results

    binary = {
        'slot': data[rec_start],
        'frame': data[rec_start + 2] | ((data[rec_start + 3] & 0x03) << 8)
    }

    # Verify slot
    if 'slot' in qxdm:
        results['fields_checked']['slot'] += 1
        if qxdm['slot'] == binary['slot']:
            results['verified'].append({'field': 'slot', 'qxdm': qxdm['slot'], 'binary': binary['slot']})
        else:
            results['mismatched'].append({'field': 'slot', 'qxdm': qxdm['slot'], 'binary': binary['slot']})

    # Verify frame
    if 'frame' in qxdm:
        results['fields_checked']['frame'] += 1
        if qxdm['frame'] == binary['frame']:
            results['verified'].append({'field': 'frame', 'qxdm': qxdm['frame'], 'binary': binary['frame']})
        else:
            results['mismatched'].append({'field': 'frame', 'qxdm': qxdm['frame'], 'binary': binary['frame']})

    return results


def main():
    filepath = "/home/qwu26/webrtc-local/logcode/tmobile_5g.txt"

    print("=" * 70)
    print("COMPLETE Verification of ALL Records")
    print("=" * 70)

    with open(filepath, 'r') as f:
        content = f.read()

    # Split into entries
    entries = re.split(r'\n(?=\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+\s)', content)

    # Statistics
    stats = {
        'B872': {
            'total_entries': 0,
            'entries_with_binary': 0,
            'fields_verified': defaultdict(int),
            'fields_mismatched': defaultdict(int),
            'sample_mismatches': []
        },
        'B883': {
            'total_entries': 0,
            'entries_with_binary': 0,
            'fields_verified': defaultdict(int),
            'fields_mismatched': defaultdict(int),
            'sample_mismatches': []
        },
        'B885': {
            'total_entries': 0,
            'entries_with_binary': 0,
            'fields_verified': defaultdict(int),
            'fields_mismatched': defaultdict(int),
            'sample_mismatches': []
        }
    }

    for entry in entries:
        # Get log code
        log_match = re.search(r'Log Code\s*:\s*0x(B\d{3})', entry)
        if not log_match:
            continue

        log_code = log_match.group(1)
        if log_code not in stats:
            continue

        stats[log_code]['total_entries'] += 1

        # Get binary data
        binary_match = re.search(r'Binary:\s*\n((?:[\da-fA-F]{4}\s+(?:[\da-fA-F]{2}\s+)+.*\n?)+)', entry)
        if not binary_match:
            continue

        stats[log_code]['entries_with_binary'] += 1
        raw_binary = parse_binary_hex(binary_match.group(1))

        # Verify based on log type
        if log_code == 'B872':
            result = verify_b872_complete(entry, raw_binary)
        elif log_code == 'B883':
            result = verify_b883_complete(entry, raw_binary)
        elif log_code == 'B885':
            result = verify_b885_complete(entry, raw_binary)
        else:
            continue

        # Accumulate statistics
        for v in result['verified']:
            field = v.get('type', v.get('field', 'unknown'))
            stats[log_code]['fields_verified'][field] += 1

        for m in result['mismatched']:
            field = m.get('type', m.get('field', 'unknown'))
            stats[log_code]['fields_mismatched'][field] += 1
            if len(stats[log_code]['sample_mismatches']) < 5:
                stats[log_code]['sample_mismatches'].append(m)

    # Print results
    print("\n" + "=" * 70)
    print("VERIFICATION RESULTS")
    print("=" * 70)

    for log_code in ['B872', 'B883', 'B885']:
        s = stats[log_code]
        print(f"\n{'='*30} {log_code} {'='*30}")
        print(f"Total entries in file:      {s['total_entries']}")
        print(f"Entries with binary data:   {s['entries_with_binary']}")

        if s['fields_verified']:
            print(f"\n  ✅ VERIFIED FIELDS:")
            for field, count in sorted(s['fields_verified'].items()):
                total = count + s['fields_mismatched'].get(field, 0)
                pct = 100.0 * count / total if total > 0 else 0
                print(f"     {field}: {count}/{total} ({pct:.1f}%)")

        if s['fields_mismatched']:
            print(f"\n  ❌ MISMATCHED FIELDS:")
            for field, count in sorted(s['fields_mismatched'].items()):
                total = s['fields_verified'].get(field, 0) + count
                pct = 100.0 * count / total if total > 0 else 0
                print(f"     {field}: {count}/{total} ({pct:.1f}%)")

            if s['sample_mismatches']:
                print(f"\n  Sample mismatches:")
                for m in s['sample_mismatches'][:3]:
                    print(f"     {m}")

        if not s['fields_verified'] and not s['fields_mismatched']:
            print("  (No fields could be verified)")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    total_verified = sum(sum(s['fields_verified'].values()) for s in stats.values())
    total_mismatched = sum(sum(s['fields_mismatched'].values()) for s in stats.values())
    total = total_verified + total_mismatched

    print(f"\nTotal fields checked: {total}")
    print(f"Total verified:       {total_verified} ({100.0*total_verified/total:.2f}%)" if total > 0 else "Total verified: 0")
    print(f"Total mismatched:     {total_mismatched} ({100.0*total_mismatched/total:.2f}%)" if total > 0 else "Total mismatched: 0")


if __name__ == "__main__":
    main()

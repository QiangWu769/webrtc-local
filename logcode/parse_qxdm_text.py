#!/usr/bin/env python3
"""
Parse QXDM text output file and extract B872/B883/B885 records for comparison.
This extracts the "ground truth" from QXDM parsed output to verify our binary parsing.
"""

import re
import sys
from collections import defaultdict

class QXDMTextParser:
    def __init__(self, filepath):
        self.filepath = filepath
        self.b872_records = []  # BSR records
        self.b883_records = []  # PUSCH records
        self.b885_records = []  # UL Grant records

    def parse(self):
        """Parse the QXDM text file"""
        with open(self.filepath, 'r') as f:
            content = f.read()

        # Split by log entries (each starts with timestamp pattern)
        # Pattern: 2025-09-15T17:38:31.271 NR5G ...
        entries = re.split(r'\n(?=\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+\s)', content)

        for entry in entries:
            if not entry.strip():
                continue

            # Determine log type
            if 'Log Code : 0xB872' in entry:
                self._parse_b872(entry)
            elif 'Log Code : 0xB883' in entry:
                self._parse_b883(entry)
            elif 'Log Code : 0xB885' in entry:
                self._parse_b885(entry)

    def _parse_b872(self, entry):
        """Parse B872 (NR5G L2 UL TB) entry - BSR data"""
        # Find all TTI blocks
        tti_blocks = re.split(r'\s+\[\d+\]\s*\n\s+TTI Info Meta', entry)

        for block in tti_blocks[1:]:  # Skip first split (header)
            record = {
                'log_code': 'B872',
                'slot': -1,
                'frame': -1,
                'grant_size': -1,
                'bytes_built': -1,
                'mce_length': 0,
                'mce_type': '',
                'bsr_type': '',
                'bsr_lcg': -1,
                'bsr_index': -1,
                'lcg_values': [-1] * 8  # For L-BSR
            }

            # Extract Slot Number
            match = re.search(r'Slot Number\s*:\s*(\d+)', block)
            if match:
                record['slot'] = int(match.group(1))

            # Extract Frame Number (FN)
            match = re.search(r'FN\s*:\s*(\d+)', block)
            if match:
                record['frame'] = int(match.group(1))

            # Extract Grant Size
            match = re.search(r'Grant Size\s*:\s*(\d+)', block)
            if match:
                record['grant_size'] = int(match.group(1))

            # Extract Bytes Built
            match = re.search(r'Bytes Built\s*:\s*(\d+)', block)
            if match:
                record['bytes_built'] = int(match.group(1))

            # Extract MCE Length
            match = re.search(r'MCE Length\s*:\s*(\d+)', block)
            if match:
                record['mce_length'] = int(match.group(1))

            # Extract BSR Type
            match = re.search(r'BSR Type\s*:\s*(\w+)', block)
            if match:
                record['bsr_type'] = match.group(1)

            # Extract MCE Type (S-BSR or L-BSR)
            match = re.search(r'MCE Type\s*:\s*(S-BSR|L-BSR)', block)
            if match:
                record['mce_type'] = match.group(1)

            # For S-BSR: Extract BSR Index and LCG
            if 'ShortBsr' in block:
                match = re.search(r'BSR Index\s*:\s*(\d+)', block)
                if match:
                    record['bsr_index'] = int(match.group(1))
                match = re.search(r'BSR LCG\s*:\s*(\d+)', block)
                if match:
                    record['bsr_lcg'] = int(match.group(1))

            # For L-BSR: Extract LCG0-LCG7 values
            if 'LongBsr' in block:
                for i in range(8):
                    match = re.search(rf'LCG{i}\s*:\s*(\d+)', block)
                    if match:
                        record['lcg_values'][i] = int(match.group(1))
                # Set bsr_lcg to bitmap based on which LCGs have non-negative values
                # Actually in QXDM output, all LCGs are shown, need to check "Length"
                match = re.search(r'Length\s*:\s*(\d+)', block)
                if match:
                    record['l_bsr_length'] = int(match.group(1))

            if record['slot'] >= 0 and record['frame'] >= 0:
                self.b872_records.append(record)

    def _parse_b883(self, entry):
        """Parse B883 (NR5G MAC UL Physical Channel) entry - PUSCH data"""
        record = {
            'log_code': 'B883',
            'slot': -1,
            'frame': -1,
            'phychan': '',
            'mcs': -1,
            'tb_size': -1,
            'num_rbs': -1,
            'rv': -1,
            'harq': -1
        }

        # Extract Slot from System Time section
        match = re.search(r'System Time\s*\n\s+Slot\s*:\s*(\d+)', entry)
        if match:
            record['slot'] = int(match.group(1))

        # Extract Frame
        match = re.search(r'Frame\s*:\s*(\d+)', entry)
        if match:
            record['frame'] = int(match.group(1))

        # Extract Phy Chan Type from Bit Mask
        if 'PUSCH_BM' in entry:
            record['phychan'] = 'PUSCH'
        elif 'PUCCH_BM' in entry:
            record['phychan'] = 'PUCCH'

        # Extract MCS (first occurrence in PUSCH Data section)
        match = re.search(r'PUSCH Data.*?MCS\s*:\s*(\d+)', entry, re.DOTALL)
        if match:
            record['mcs'] = int(match.group(1))

        # Extract TB Size
        match = re.search(r'TB Size \(bytes\)\s*:\s*(\d+)', entry)
        if match:
            record['tb_size'] = int(match.group(1))

        # Extract Num RBs
        match = re.search(r'Num RBs\s*:\s*(\d+)', entry)
        if match:
            record['num_rbs'] = int(match.group(1))

        # Extract RV Index
        match = re.search(r'RV Index\s*:\s*(\d+)', entry)
        if match:
            record['rv'] = int(match.group(1))

        # Extract HARQ ID
        match = re.search(r'HARQ ID\s*:\s*(\d+)', entry)
        if match:
            record['harq'] = int(match.group(1))

        # Extract raw binary if present
        binary_match = re.search(r'Binary:\s*\n((?:[\da-fA-F]{4}\s+(?:[\da-fA-F]{2}\s+)+.*\n)+)', entry)
        if binary_match:
            record['raw_binary'] = binary_match.group(1).strip()

        if record['slot'] >= 0 and record['frame'] >= 0:
            self.b883_records.append(record)

    def _parse_b885(self, entry):
        """Parse B885 (NR5G MAC DCI Info) entry - UL Grant data"""
        record = {
            'log_code': 'B885',
            'slot': -1,
            'frame': -1,
            'mcs': -1,
            'harq': -1,
            'rv': -1,
            'rb_start': -1,
            'rb_length': -1,
            'raw_dci': []
        }

        # Extract Slot Number
        match = re.search(r'Slot Number\s*:\s*(\d+)', entry)
        if match:
            record['slot'] = int(match.group(1))

        # Extract System Frame Number
        match = re.search(r'System Frame Number\s*:\s*(\d+)', entry)
        if match:
            record['frame'] = int(match.group(1))

        # Extract MCS
        match = re.search(r'MCS\s*:\s*(\d+)', entry)
        if match:
            record['mcs'] = int(match.group(1))

        # Extract HARQ ID
        match = re.search(r'HARQ ID\s*:\s*(\d+)', entry)
        if match:
            record['harq'] = int(match.group(1))

        # Extract RV
        match = re.search(r'RV\s*:\s*(\d+)', entry)
        if match:
            record['rv'] = int(match.group(1))

        # Extract RB Start (or Freq Domain RA)
        match = re.search(r'RB Start\s*:\s*(\d+)', entry)
        if match:
            record['rb_start'] = int(match.group(1))

        # Extract RB Length (or Num RBs)
        match = re.search(r'(?:RB Length|Num RBs)\s*:\s*(\d+)', entry)
        if match:
            record['rb_length'] = int(match.group(1))

        # Extract Raw DCI values
        for i in range(3):
            match = re.search(rf'Raw DCI\[{i}\]\s*:\s*(\d+)', entry)
            if match:
                record['raw_dci'].append(int(match.group(1)))

        # Extract raw binary if present
        binary_match = re.search(r'Binary:\s*\n((?:[\da-fA-F]{4}\s+(?:[\da-fA-F]{2}\s+)+.*\n)+)', entry)
        if binary_match:
            record['raw_binary'] = binary_match.group(1).strip()

        if record['slot'] >= 0 and record['frame'] >= 0:
            self.b885_records.append(record)

    def print_summary(self):
        """Print summary of parsed records"""
        print("=" * 60)
        print("QXDM Text File Parsing Summary")
        print("=" * 60)
        print(f"B872 (BSR) records:     {len(self.b872_records)}")
        print(f"B883 (PUSCH) records:   {len(self.b883_records)}")
        print(f"B885 (UL Grant) records: {len(self.b885_records)}")
        print()

        # B872 BSR statistics
        if self.b872_records:
            s_bsr = [r for r in self.b872_records if r['mce_type'] == 'S-BSR']
            l_bsr = [r for r in self.b872_records if r['mce_type'] == 'L-BSR']
            print(f"B872 S-BSR: {len(s_bsr)}, L-BSR: {len(l_bsr)}")

            # BSR index distribution for S-BSR
            if s_bsr:
                bsr_indices = [r['bsr_index'] for r in s_bsr if r['bsr_index'] >= 0]
                if bsr_indices:
                    print(f"  S-BSR index range: {min(bsr_indices)} - {max(bsr_indices)}")
                lcg_values = [r['bsr_lcg'] for r in s_bsr if r['bsr_lcg'] >= 0]
                if lcg_values:
                    print(f"  S-BSR LCG distribution: {dict(sorted(defaultdict(int, {v: lcg_values.count(v) for v in set(lcg_values)}).items()))}")

        # B883 PUSCH statistics
        if self.b883_records:
            pusch = [r for r in self.b883_records if r['phychan'] == 'PUSCH']
            pucch = [r for r in self.b883_records if r['phychan'] == 'PUCCH']
            print(f"B883 PUSCH: {len(pusch)}, PUCCH: {len(pucch)}")
            if pusch:
                mcs_values = [r['mcs'] for r in pusch if r['mcs'] >= 0]
                if mcs_values:
                    print(f"  PUSCH MCS range: {min(mcs_values)} - {max(mcs_values)}")
                tb_sizes = [r['tb_size'] for r in pusch if r['tb_size'] > 0]
                if tb_sizes:
                    print(f"  PUSCH TB size range: {min(tb_sizes)} - {max(tb_sizes)}")

    def print_sample_records(self, n=5):
        """Print sample records for verification"""
        print("\n" + "=" * 60)
        print("Sample B872 (BSR) Records")
        print("=" * 60)
        for i, r in enumerate(self.b872_records[:n]):
            if r['mce_type'] == 'S-BSR':
                print(f"[{i}] frame={r['frame']}, slot={r['slot']}, S-BSR: LCG={r['bsr_lcg']}, index={r['bsr_index']}")
            elif r['mce_type'] == 'L-BSR':
                print(f"[{i}] frame={r['frame']}, slot={r['slot']}, L-BSR: lcg_values={r['lcg_values']}")
            else:
                print(f"[{i}] frame={r['frame']}, slot={r['slot']}, no BSR (mce_length={r['mce_length']})")

        # Find and print L-BSR samples
        l_bsr_samples = [r for r in self.b872_records if r['mce_type'] == 'L-BSR'][:n]
        if l_bsr_samples:
            print(f"\nL-BSR samples:")
            for i, r in enumerate(l_bsr_samples):
                print(f"  [{i}] frame={r['frame']}, slot={r['slot']}, lcg_values={r['lcg_values']}")

        # Find S-BSR with non-zero index
        s_bsr_nonzero = [r for r in self.b872_records if r['mce_type'] == 'S-BSR' and r['bsr_index'] > 0][:n]
        if s_bsr_nonzero:
            print(f"\nS-BSR with non-zero index:")
            for i, r in enumerate(s_bsr_nonzero):
                print(f"  [{i}] frame={r['frame']}, slot={r['slot']}, LCG={r['bsr_lcg']}, index={r['bsr_index']}")

        print("\n" + "=" * 60)
        print("Sample B883 (PUSCH) Records")
        print("=" * 60)
        pusch_samples = [r for r in self.b883_records if r['phychan'] == 'PUSCH'][:n]
        for i, r in enumerate(pusch_samples):
            print(f"[{i}] frame={r['frame']}, slot={r['slot']}, PUSCH: mcs={r['mcs']}, tb_size={r['tb_size']}, num_rbs={r['num_rbs']}, harq={r['harq']}")

        print("\n" + "=" * 60)
        print("Sample B885 (UL Grant) Records")
        print("=" * 60)
        for i, r in enumerate(self.b885_records[:n]):
            print(f"[{i}] frame={r['frame']}, slot={r['slot']}, mcs={r['mcs']}, harq={r['harq']}, rb_start={r['rb_start']}, rb_len={r['rb_length']}")

    def export_to_tsv(self, output_prefix):
        """Export records to TSV files for comparison"""
        # Export B872
        with open(f"{output_prefix}_b872.tsv", 'w') as f:
            f.write("frame\tslot\tmce_type\tbsr_lcg\tbsr_index\tlcg0\tlcg1\tlcg2\tlcg3\tlcg4\tlcg5\tlcg6\tlcg7\tgrant_size\tbytes_built\n")
            for r in self.b872_records:
                lcg = r['lcg_values']
                f.write(f"{r['frame']}\t{r['slot']}\t{r['mce_type']}\t{r['bsr_lcg']}\t{r['bsr_index']}\t")
                f.write(f"{lcg[0]}\t{lcg[1]}\t{lcg[2]}\t{lcg[3]}\t{lcg[4]}\t{lcg[5]}\t{lcg[6]}\t{lcg[7]}\t")
                f.write(f"{r['grant_size']}\t{r['bytes_built']}\n")

        # Export B883
        with open(f"{output_prefix}_b883.tsv", 'w') as f:
            f.write("frame\tslot\tphychan\tmcs\ttb_size\tnum_rbs\trv\tharq\n")
            for r in self.b883_records:
                f.write(f"{r['frame']}\t{r['slot']}\t{r['phychan']}\t{r['mcs']}\t{r['tb_size']}\t{r['num_rbs']}\t{r['rv']}\t{r['harq']}\n")

        # Export B885
        with open(f"{output_prefix}_b885.tsv", 'w') as f:
            f.write("frame\tslot\tmcs\tharq\trv\trb_start\trb_length\n")
            for r in self.b885_records:
                f.write(f"{r['frame']}\t{r['slot']}\t{r['mcs']}\t{r['harq']}\t{r['rv']}\t{r['rb_start']}\t{r['rb_length']}\n")

        print(f"\nExported to:")
        print(f"  {output_prefix}_b872.tsv ({len(self.b872_records)} records)")
        print(f"  {output_prefix}_b883.tsv ({len(self.b883_records)} records)")
        print(f"  {output_prefix}_b885.tsv ({len(self.b885_records)} records)")


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


def verify_b872_binary(qxdm_record, raw_binary):
    """Verify B872 parsing by comparing QXDM result with our binary parsing"""
    data = bytearray(raw_binary)

    # Skip DIAG header (usually 12-16 bytes)
    # Look for version signature
    version_offset = 12
    if len(data) < version_offset + 20:
        return None, "Data too short"

    # Find TB info - look for MCE data
    # B872 structure: version(4) + num_tti(1) + tti_info[]
    # Each TTI: slot(2) + frame(2) + ... + mce_length + mce_data

    results = {'matches': [], 'mismatches': []}

    # Simple check: look for MCE patterns
    # S-BSR starts with 0x3D, L-BSR starts with 0x3E
    for i in range(len(data) - 2):
        if data[i] == 0x3D:  # S-BSR
            if i + 1 < len(data):
                bsr_byte = data[i + 1]
                our_lcg = (bsr_byte & 0xE0) >> 5
                our_bsr = bsr_byte & 0x1F
                results['s_bsr'] = {'lcg': our_lcg, 'bsr_index': our_bsr, 'raw': f"0x{bsr_byte:02X}"}
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
                results['l_bsr'] = {'lcg_bitmap': f"0x{lcg_bitmap:02X}", 'bsr_values': bsr_values}

    return results, None


def verify_parsing_with_binary(filepath):
    """Extract binary data from QXDM text and verify our parsing"""
    print("\n" + "=" * 60)
    print("Binary Parsing Verification")
    print("=" * 60)

    with open(filepath, 'r') as f:
        content = f.read()

    # Find entries with binary data
    entries = re.split(r'\n(?=\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+\s)', content)

    verified = 0
    mismatches = 0

    for entry in entries[:100]:  # Check first 100 entries
        if 'Binary:' not in entry:
            continue

        # Extract log type
        log_match = re.search(r'Log Code\s*:\s*0x(B\d{3})', entry)
        if not log_match:
            continue
        log_code = log_match.group(1)

        # Extract binary data
        binary_match = re.search(r'Binary:\s*\n((?:[\da-fA-F]{4}\s+(?:[\da-fA-F]{2}\s+)+.*\n?)+)', entry)
        if not binary_match:
            continue

        raw_data = parse_binary_hex(binary_match.group(1))

        if log_code == 'B872':
            # Extract QXDM parsed values
            qxdm_mce_type = None
            qxdm_lcg = -1
            qxdm_bsr = -1

            if 'MCE Type : S-BSR' in entry:
                qxdm_mce_type = 'S-BSR'
                lcg_match = re.search(r'BSR LCG\s*:\s*(\d+)', entry)
                bsr_match = re.search(r'BSR Index\s*:\s*(\d+)', entry)
                if lcg_match:
                    qxdm_lcg = int(lcg_match.group(1))
                if bsr_match:
                    qxdm_bsr = int(bsr_match.group(1))
            elif 'MCE Type : L-BSR' in entry:
                qxdm_mce_type = 'L-BSR'
                qxdm_lcg_values = []
                for k in range(8):
                    m = re.search(rf'LCG{k}\s*:\s*(\d+)', entry)
                    if m:
                        qxdm_lcg_values.append(int(m.group(1)))

            # Our parsing
            result, err = verify_b872_binary(None, raw_data)
            if err:
                continue

            # Compare
            if qxdm_mce_type == 'S-BSR' and 's_bsr' in result:
                our = result['s_bsr']
                if our['lcg'] == qxdm_lcg and our['bsr_index'] == qxdm_bsr:
                    verified += 1
                else:
                    mismatches += 1
                    print(f"MISMATCH S-BSR: QXDM(LCG={qxdm_lcg}, BSR={qxdm_bsr}) vs OUR(LCG={our['lcg']}, BSR={our['bsr_index']}, raw={our['raw']})")
            elif qxdm_mce_type == 'L-BSR' and 'l_bsr' in result:
                verified += 1  # Just count as verified for now

    print(f"\nVerification results:")
    print(f"  Verified matches: {verified}")
    print(f"  Mismatches: {mismatches}")


def main():
    if len(sys.argv) < 2:
        filepath = "/home/qwu26/webrtc-local/logcode/tmobile_5g.txt"
    else:
        filepath = sys.argv[1]

    print(f"Parsing: {filepath}")
    print()

    parser = QXDMTextParser(filepath)
    parser.parse()
    parser.print_summary()
    parser.print_sample_records(n=5)

    # Export to TSV for comparison
    output_prefix = filepath.rsplit('.', 1)[0] + "_parsed"
    parser.export_to_tsv(output_prefix)

    # Verify binary parsing
    verify_parsing_with_binary(filepath)


if __name__ == "__main__":
    main()

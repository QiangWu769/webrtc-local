#!/usr/bin/env python
# -*- coding: utf-8 -*-
import struct

def parse_b16c_v49_c_style(hex_data):
    """Parse B16C v49 data using C code logic (with byte reversal)"""
    results = []
    
    # Convert hex string to bytes
    data = bytearray.fromhex(hex_data.replace(' ', '').replace('\n', ''))
    
    # Skip first 12 bytes (similar to actual processing)
    index = 12
    
    # Parse S_H header (4 bytes)
    version = data[index]
    # v49: num_record spans across 2 bytes
    num_records = ((data[index+1] & 0x07) << 2) | ((data[index+2] & 0xC0) >> 6)
    
    print("=== C-style parsing (with byte reversal) ===")
    print("Version: %d" % version)
    print("Number of records: %d" % num_records)
    print("")
    
    index += 4  # Skip S_H
    
    for i in range(num_records):
        if index + 4 > len(data):
            break
            
        # Get 4-byte record header
        r_h_original = data[index:index+4]
        
        # Simulate C code byte reversal: convert_endianess for 4 bytes
        r_h_reversed = bytearray([r_h_original[3], r_h_original[2], r_h_original[1], r_h_original[0]])
        
        # Extract fields from REVERSED bytes (as C code does after reversal)
        # C: num_ul_grant = ((hex_data[start_record+1]&0x01)<<2) | ((hex_data[start_record+2]&0xC0)>>6)
        num_ul_grant = ((r_h_reversed[1] & 0x01) << 2) | ((r_h_reversed[2] & 0xC0) >> 6)
        
        # C: subfn = (hex_data[start_record+2]&0x3C)>>2
        subfn = (r_h_reversed[2] & 0x3C) >> 2
        
        # C: sysfn = ((hex_data[start_record+2]&0x03)<<8) | (hex_data[start_record+3])
        sysfn = ((r_h_reversed[2] & 0x03) << 8) | r_h_reversed[3]
        
        print("Record %d:" % (i+1))
        print("  Original bytes: [0x%02X, 0x%02X, 0x%02X, 0x%02X]" % tuple(r_h_original))
        print("  Reversed bytes: [0x%02X, 0x%02X, 0x%02X, 0x%02X]" % tuple(r_h_reversed))
        print("  num_ul_grant: %d" % num_ul_grant)
        print("  subfn: %d" % subfn)
        print("  sysfn: %d" % sysfn)
        
        results.append({
            'num_ul_grant': num_ul_grant,
            'subfn': subfn,
            'sysfn': sysfn
        })
        
        index += 4  # Move to next record or UL/DL grant
        
        # Skip grant data
        if num_ul_grant != 0:
            index += 16  # UL grant is 16 bytes in v49
        else:
            index += 8   # DL grant is 8 bytes
    
    return results

def parse_b16c_v49_python_current(hex_data):
    """Parse B16C v49 data using current Python implementation"""
    results = []
    
    # Convert hex string to bytes
    data = bytearray.fromhex(hex_data.replace(' ', '').replace('\n', ''))
    
    # Skip first 12 bytes
    payload = data[12:]
    
    # Parse S_H header
    version = payload[0]
    num_records = ((payload[1] & 0x07) << 2) | ((payload[2] & 0xC0) >> 6)
    
    print("\n=== Current Python parsing ===")
    print("Version: %d" % version)
    print("Number of records: %d" % num_records)
    print("")
    
    cursor = 4  # Skip S_H
    
    for i in range(num_records):
        if cursor + 4 > len(payload):
            break
            
        # Get record header (NO reversal in Python)
        r_h = payload[cursor:cursor+4]
        
        # Current Python implementation (after fix)
        num_ul_grant = ((r_h[2] & 0x01) << 2) | ((r_h[1] & 0xC0) >> 6)
        subfn = (r_h[1] & 0x3C) >> 2
        sysfn = ((r_h[1] & 0x03) << 8) | r_h[0]
        
        print("Record %d:" % (i+1))
        print("  Original bytes: [0x%02X, 0x%02X, 0x%02X, 0x%02X]" % tuple(r_h))
        print("  num_ul_grant: %d" % num_ul_grant)
        print("  subfn: %d" % subfn)
        print("  sysfn: %d" % sysfn)
        
        results.append({
            'num_ul_grant': num_ul_grant,
            'subfn': subfn,
            'sysfn': sysfn
        })
        
        cursor += 4
        
        # Skip grant data
        if num_ul_grant != 0:
            cursor += 16  # UL grant
        else:
            cursor += 8   # DL grant
    
    return results

def main():
    # Test data provided - clean up formatting
    test_data = """A0 01 6C B1 24 20 9A C5 AB 46 0C 01 31 3C 05 00 B1 40
00 00 E8 80 80 6B 03 18 A0 20 4B 25 00 00 00 00 00 00 B1 44 00 00 F8 80 80 6B 03 18 A0 20
4B 25 00 00 00 00 00 00 B1 48 00 00 80 80 80 6B 03 D8 50 20 1B 3D 00 00 00 00 00 00 B1 4C
00 00 98 80 80 6B 03 58 90 20 4B 31 00 00 00 00 00 00 B1 5C 00 00 D8 80 80 6B 03 48 90 20
6B 31 00 00 00 00 00 00 B1 60 00 00 E0 80 80 6B 03 40 90 20 7B 31 00 00 00 00 00 00 B1 64
00 00 F0 80 80 6B 03 18 A0 20 4B 25 00 00 00 00 00 00 B2 40 00 00 88 80 80 6B 03 18 A0 20
4B 25 00 00 00 00 00 00 B2 44 00 00 90 80 80 6B 03 18 A0 20 4B 25 00 00 00 00 00 00 B2 48
00 00 A8 80 80 6B 03 80 78 20 BB 43 00 00 00 00 00 00 B2 4C 00 00 B0 80 80 6B 03 18 A0 20
4B 25 00 00 00 00 00 00 B2 50 00 00 C0 80 80 6B 03 18 A0 20 4B 25 00 00 00 00 00 00 B2 54
00 00 D0 80 80 6B 03 18 A0 20 4B 25 00 00 00 00 00 00 B2 58 00 00 E8 80 80 6B 03 40 90 20
7B 31 00 00 00 00 00 00 B2 5C 00 00 F8 80 80 6B 03 48 90 20 6B 31 00 00 00 00 00 00 B2 60
00 00 80 80 80 6B 03 18 A0 20 4B 25 00 00 00 00 00 00 B2 64 00 00 98 80 80 6B 03 18 A0 20
4B 25 00 00 00 00 00 00 B3 40 00 00 A0 80 80 6B 03 18 A0 20 4B 25 00 00 00 00 00 00 B3 44
00 00 B8 80 80 6B 03 18 A0 20 4B 25 00 00 00 00 00 00 B3 48 00 00 C8 80 80 6B 03 20 29 20
6B 1E 00 00 00 00 00 00 75 8C"""
    
    # Remove all newlines and extra spaces
    test_data = test_data.replace('\n', ' ').strip()

    print("Test Data Analysis")
    print("=" * 50)
    
    # Parse with C-style logic
    c_results = parse_b16c_v49_c_style(test_data)
    
    # Parse with Python logic
    py_results = parse_b16c_v49_python_current(test_data)
    
    # Compare results
    print("\n" + "=" * 50)
    print("COMPARISON RESULTS")
    print("=" * 50)
    
    if len(c_results) != len(py_results):
        print("ERROR: Different number of records!")
        print("  C-style: %d records" % len(c_results))
        print("  Python:  %d records" % len(py_results))
    else:
        all_match = True
        for i, (c_rec, py_rec) in enumerate(zip(c_results, py_results)):
            print("\nRecord %d:" % (i+1))
            match = True
            
            # Compare num_ul_grant
            if c_rec['num_ul_grant'] != py_rec['num_ul_grant']:
                print("  num_ul_grant MISMATCH: C=%d, Python=%d" % (c_rec['num_ul_grant'], py_rec['num_ul_grant']))
                match = False
                all_match = False
            else:
                print("  num_ul_grant: %d ✓" % c_rec['num_ul_grant'])
            
            # Compare subfn
            if c_rec['subfn'] != py_rec['subfn']:
                print("  subfn MISMATCH: C=%d, Python=%d" % (c_rec['subfn'], py_rec['subfn']))
                match = False
                all_match = False
            else:
                print("  subfn: %d ✓" % c_rec['subfn'])
            
            # Compare sysfn
            if c_rec['sysfn'] != py_rec['sysfn']:
                print("  sysfn MISMATCH: C=%d, Python=%d" % (c_rec['sysfn'], py_rec['sysfn']))
                match = False
                all_match = False
            else:
                print("  sysfn: %d ✓" % c_rec['sysfn'])
            
            if match:
                print("  Status: ✓ ALL FIELDS MATCH")
        
        print("\n" + "=" * 50)
        if all_match:
            print("✓ SUCCESS: All records match between C and Python parsing!")
        else:
            print("✗ FAILURE: Some fields do not match!")

if __name__ == "__main__":
    main()
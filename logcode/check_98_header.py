#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re

def check_raw_data_headers(filename='raw_tcp_data.txt'):
    """Check if all raw TCP data packets start with 98"""
    
    total_packets = 0
    starts_with_98 = 0
    not_starts_with_98 = 0
    non_98_examples = []
    
    try:
        with open(filename, 'r') as f:
            lines = f.readlines()
            
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Look for "Full data:" line
            if line == "Full data:":
                i += 1
                if i < len(lines):
                    data_line = lines[i].strip()
                    if data_line:
                        total_packets += 1
                        
                        # Check if starts with 98
                        if data_line.startswith("98"):
                            starts_with_98 += 1
                        else:
                            not_starts_with_98 += 1
                            # Save first 32 bytes as example
                            first_bytes = data_line[:min(95, len(data_line))]  # ~32 bytes in hex
                            if len(non_98_examples) < 10:  # Keep first 10 examples
                                # Find the timestamp info
                                timestamp_info = ""
                                for j in range(max(0, i-10), i):
                                    if "Bridge_TS:" in lines[j]:
                                        timestamp_info = lines[j].strip()
                                        break
                                non_98_examples.append({
                                    'timestamp': timestamp_info,
                                    'header': first_bytes
                                })
            i += 1
                
    except IOError as e:
        print "Error reading file: {}".format(e)
        return
    
    # Print results
    print "=" * 60
    print "Raw TCP Data Analysis Results"
    print "=" * 60
    print "Total packets analyzed: {}".format(total_packets)
    print "Packets starting with 98: {} ({:.1f}%)".format(
        starts_with_98, 
        100.0 * starts_with_98 / total_packets if total_packets > 0 else 0
    )
    print "Packets NOT starting with 98: {} ({:.1f}%)".format(
        not_starts_with_98,
        100.0 * not_starts_with_98 / total_packets if total_packets > 0 else 0
    )
    print "=" * 60
    
    if not_starts_with_98 > 0:
        print "\nExamples of packets NOT starting with 98:"
        print "-" * 60
        for idx, example in enumerate(non_98_examples, 1):
            print "Example {}:".format(idx)
            print "  {}".format(example['timestamp'])
            print "  First 32 bytes: {}".format(example['header'])
            print
    else:
        print "\nAll packets start with 98!"
    
    # Additional analysis - check full 8-byte header
    print "\n" + "=" * 60
    print "Checking full 8-byte header (98 01 00 00 01 00 00 00):"
    print "=" * 60
    
    standard_header_count = 0
    non_standard_headers = {}
    
    with open(filename, 'r') as f:
        lines = f.readlines()
        
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line == "Full data:":
            i += 1
            if i < len(lines):
                data_line = lines[i].strip()
                if data_line:
                    # Get first 8 bytes (23 chars with spaces)
                    header_8bytes = data_line[:23] if len(data_line) >= 23 else data_line
                    
                    if header_8bytes == "98 01 00 00 01 00 00 00":
                        standard_header_count += 1
                    else:
                        if header_8bytes not in non_standard_headers:
                            non_standard_headers[header_8bytes] = 0
                        non_standard_headers[header_8bytes] += 1
        i += 1
    
    print "Standard header (98 01 00 00 01 00 00 00): {} packets".format(standard_header_count)
    
    if non_standard_headers:
        print "\nNon-standard headers found:"
        for header, count in sorted(non_standard_headers.items(), key=lambda x: -x[1]):
            print "  {}: {} packets".format(header, count)
    else:
        print "All packets have the standard header!"
    
    print "=" * 60

if __name__ == "__main__":
    check_raw_data_headers()
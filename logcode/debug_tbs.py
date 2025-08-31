#!/usr/bin/env python
# -*- coding: utf-8 -*-

def check_tbs_values():
    """Debug TBS index values from diag_report.txt"""
    
    invalid_count = 0
    valid_count = 0
    tbs_values = {}
    
    with open('/home/wuq/webrtc-checkout/logcode/diag_report.txt', 'r') as f:
        lines = f.readlines()
        
    for i, line in enumerate(lines):
        if i == 0:  # Skip header
            continue
            
        parts = line.strip().split('\t')
        if len(parts) >= 12:
            tbs_string = parts[11]
            if tbs_string and tbs_string != '-':
                if 'invalid' in tbs_string:
                    invalid_count += 1
                else:
                    valid_count += 1
                    
                if tbs_string not in tbs_values:
                    tbs_values[tbs_string] = 0
                tbs_values[tbs_string] += 1
    
    print "TBS Index Analysis:"
    print "=================="
    print "Valid TBS indices: {}".format(valid_count)
    print "Invalid TBS indices: {}".format(invalid_count)
    print "\nTBS value distribution:"
    for tbs, count in sorted(tbs_values.items()):
        print "  {}: {} occurrences".format(tbs, count)

if __name__ == "__main__":
    check_tbs_values()

#!/usr/bin/env python
# -*- coding: utf-8 -*-

# From the test data, after the record header we have UL grant data
# Let's analyze what the correct field positions should be

test_ul_grant = "E8 80 80 6B 03 18 A0 20 4B 25 00 00 00 00 00 00"
data = bytearray.fromhex(test_ul_grant.replace(' ', ''))

print "UL Grant bytes (16 bytes):"
for i, b in enumerate(data):
    print "  [{}]: 0x{:02X} = {:08b}".format(i, b, b)

print "\nCurrent v49 extraction:"
print "  tbs_index = (data[2] & 0xFC) >> 2 = (0x{:02X} & 0xFC) >> 2 = {}".format(
    data[2], (data[2] & 0xFC) >> 2)
print "  mcs_index = ((data[2] & 0x03) << 3) | ((data[3] & 0xE0) >> 5) = {}".format(
    ((data[2] & 0x03) << 3) | ((data[3] & 0xE0) >> 5))
print "  redundancy_version = (data[3] & 0x18) >> 3 = {}".format(
    (data[3] & 0x18) >> 3)
print "  num_of_resource_blocks = (data[5] & 0xFC) >> 2 = {}".format(
    (data[5] & 0xFC) >> 2)

print "\nIf we used v48 positions (but only first 16 bytes):"
print "  mcs_index = (data[5] & 0xF8) >> 3 = {}".format((data[5] & 0xF8) >> 3)
print "  redundancy_version = (data[5] & 0x06) >> 1 = {}".format((data[5] & 0x06) >> 1)
print "  tbs_index = data[6] & 0x3F = {}".format(data[6] & 0x3F)
print "  num_of_resource_blocks = data[8] & 0x7F = {}".format(data[8] & 0x7F)

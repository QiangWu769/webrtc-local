#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 使用测试数据检查v49的实际格式
test_data = """A0 01 6C B1 24 20 9A C5 AB 46 0C 01 31 3C 05 00 B1 40
00 00 E8 80 80 6B 03 18 A0 20 4B 25 00 00 00 00 00 00 B1 44 00 00 F8 80 80 6B 03 18 A0 20
4B 25 00 00 00 00 00 00 B1 48 00 00 80 80 80 6B 03 D8 50 20 1B 3D 00 00 00 00 00 00"""

# 清理数据
test_data = test_data.replace('\n', ' ').strip()
data = bytearray.fromhex(test_data.replace(' ', ''))

print "Total data length: {} bytes".format(len(data))
print "Header (12 bytes): {}".format(' '.join('{:02X}'.format(b) for b in data[:12]))

# 跳过12字节头部
payload = data[12:]
print "\nPayload length: {} bytes".format(len(payload))

# S_H header
version = payload[0]
num_records = ((payload[1] & 0x07) << 2) | ((payload[2] & 0xC0) >> 6)
print "Version: {}".format(version)
print "Number of records: {}".format(num_records)

# 分析每个记录的大小
cursor = 4
for i in range(min(3, num_records)):  # 只看前3条记录
    print "\n--- Record {} ---".format(i+1)
    
    # R_H (4 bytes)
    r_h = payload[cursor:cursor+4]
    print "R_H bytes: {}".format(' '.join('{:02X}'.format(b) for b in r_h))
    
    num_ul_grant = ((r_h[2] & 0x01) << 2) | ((r_h[1] & 0xC0) >> 6)
    print "num_ul_grant: {}".format(num_ul_grant)
    
    # 找下一个记录的开始位置
    if i < num_records - 1:
        # 搜索下一个B1/B2开头的记录
        for offset in [16, 20, 126, 130]:
            next_pos = cursor + 4 + offset
            if next_pos < len(payload) - 3:
                next_bytes = payload[next_pos:next_pos+4]
                # 检查是否是下一个记录（B1或B2开头）
                if next_bytes[0] in [0xB1, 0xB2]:
                    print "Next record found at offset {} from current R_H".format(offset+4)
                    print "Grant size appears to be: {} bytes".format(offset)
                    break
    
    cursor += 4

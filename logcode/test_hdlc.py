#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from hdlc import HDLC

def hex_to_bytes(hex_str):
    """将十六进制字符串转换为字节数组"""
    # 移除所有空格
    hex_str = hex_str.replace(" ", "")
    # 两个十六进制字符一组
    return bytearray(int(hex_str[i:i+2], 16) for i in range(0, len(hex_str), 2))

def bytes_to_hex(data):
    """将字节数组转换为十六进制字符串"""
    return ' '.join(f"{b:02x}" for b in data)

# 第一个数据 - 代码中的字符串变量
data1_hex = "73 00 00 00 03 00 00 00 0b 00 00 00 c5 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 18 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 08 00 00 00 00 00 00 00 00 00 00"
data1 = bytearray([int(x, 16) for x in data1_hex.split()])

# 第二个数据 - 用户提供的字符串
data2_hex = "73 00 00 00 03 00 00 00 0b 00 00 00 c5 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 18 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 08 00 00 00 00 00 00 00 00 00 00"
data2 = bytearray([int(x, 16) for x in data2_hex.split()])

print("=== 数据比较 ===")
print(f"数据1长度: {len(data1)} 字节")
print(f"数据2长度: {len(data2)} 字节")

if data1 == data2:
    print("两个数据完全相同!")
else:
    print("两个数据不同，差异如下:")
    for i in range(min(len(data1), len(data2))):
        if data1[i] != data2[i]:
            print(f"位置 {i}: 数据1={data1[i]:02x}, 数据2={data2[i]:02x}")

print("\n=== CRC计算 ===")
crc1 = HDLC.calc_crc16(data1)
crc2 = HDLC.calc_crc16(data2)

print(f"数据1 CRC: 0x{crc1:04x} (小端序: {crc1 & 0xFF:02x} {(crc1 >> 8) & 0xFF:02x})")
print(f"数据2 CRC: 0x{crc2:04x} (小端序: {crc2 & 0xFF:02x} {(crc2 >> 8) & 0xFF:02x})")

print("\n=== HDLC编码结果 ===")
encoded1 = HDLC.encode(data1)
encoded2 = HDLC.encode(data2)

print(f"数据1编码后长度: {len(encoded1)} 字节")
print(f"数据2编码后长度: {len(encoded2)} 字节")

print("\n数据1编码结果:")
print(bytes_to_hex(encoded1))
print(f"末尾3字节: {encoded1[-3:].hex(' ')}")

print("\n数据2编码结果:")
print(bytes_to_hex(encoded2))
print(f"末尾3字节: {encoded2[-3:].hex(' ')}")

if encoded1 == encoded2:
    print("\n两个数据的HDLC编码结果完全相同!")
else:
    print("\n两个数据的HDLC编码结果不同，差异如下:")
    for i in range(min(len(encoded1), len(encoded2))):
        if encoded1[i] != encoded2[i]:
            print(f"位置 {i}: 编码1={encoded1[i]:02x}, 编码2={encoded2[i]:02x}")

# 手动组装结果进行验证
print("\n=== 手动组装HDLC编码结果验证 ===")
manual_result = bytearray(data1)
manual_result.append(crc1 & 0xFF)  # 低字节
manual_result.append((crc1 >> 8) & 0xFF)  # 高字节
manual_result.append(0x7E)  # 帧尾

print(f"手动组装后末尾3字节: {manual_result[-3:].hex(' ')}")
print(f"预期结果末尾3字节: ee 47 7e")

if manual_result[-3:] == bytes([0xee, 0x47, 0x7e]):
    print("手动组装结果与预期一致!")
else:
    print("手动组装结果与预期不一致!")
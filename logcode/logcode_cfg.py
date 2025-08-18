#!/usr/bin/env python3
# -*- coding: utf-8 -*-

MAX_LOGCODES = 100
COMMAND_HEADER_SIZE = 16  # 命令头部16字节，没有长度字段
DEFAULT_MAX_ID = 2500     # 默认最大项目ID

# 生成掩码数据
def generate_mask(logcodes, count, max_id):
    # 计算掩码所需的字节数
    mask_size = (max_id + 7) // 8
    
    # 分配并初始化掩码内存
    mask = bytearray(mask_size)
    
    # 设置对应的位
    for i in range(count):
        # 获取项目ID (假设logcode格式为0xBxxx，项目ID为xxx)
        item_id = logcodes[i] & 0xFFF
        
        # 计算字节索引和位索引
        byte_index = item_id // 8
        bit_index = item_id % 8
        
        # 确保索引有效
        if byte_index < mask_size:
            # 设置对应位为1
            mask[byte_index] |= (1 << bit_index)
        else:
            print(f"警告: logcode 0x{logcodes[i]:04X} 超出范围，已忽略")
    
    return mask, mask_size

# 将二进制数据转换为十六进制字符串
def binary_to_hex_string(data, length):
    hex_str = ""
    for i in range(length):
        hex_str += f"\\x{data[i]:02X}"
    
    return hex_str

# 解析十六进制字符串为数字
def parse_hex(hex_str):
    # 跳过0x或0X前缀
    if hex_str.startswith("0x") or hex_str.startswith("0X"):
        hex_str = hex_str[2:]
    
    try:
        result = int(hex_str, 16)
        return result
    except ValueError:
        return 0

# 用户输入处理
def get_logcodes_from_user(max_count):
    logcodes = []
    
    print("请输入logcode列表 (用空格或逗号分隔，例如 0xB063 0xB064):")
    input_str = input()
    
    # 按空格或逗号分割输入
    tokens = input_str.replace(",", " ").split()
    
    for token in tokens:
        if len(logcodes) >= max_count:
            break
            
        # 解析十六进制值
        code = parse_hex(token)
        
        # 只添加有效的logcode (通常以0xB开头)
        if (code & 0xF000) == 0xB000:
            logcodes.append(code)
        else:
            print(f"警告: 忽略无效的logcode '{token}'")
    
    return logcodes

def main():
    # 获取用户输入的logcode
    logcodes = get_logcodes_from_user(MAX_LOGCODES)
    
    if not logcodes:
        print("未输入有效的logcode")
        return 1
    
    print(f"已输入 {len(logcodes)} 个有效的logcode:")
    for code in logcodes:
        print(f"0x{code:04X} ", end="")
    print("\n")
    
    # 找出最大的项目ID
    max_id = 0
    for code in logcodes:
        item_id = code & 0xFFF
        if item_id > max_id:
            max_id = item_id
    
    # 生成掩码数据
    mask_data, mask_size = generate_mask(logcodes, len(logcodes), max_id)
    
    # 创建命令头 - 正确格式，直接从命令ID开始
    command = bytearray(COMMAND_HEADER_SIZE)
    
    # 设置命令字段 (小端序)
    cmd_id = 0x73          # DIAG_LOG_CONFIG_F
    op_code = 0x03         # SET_MASK
    device_id = 0x0B       # LTE
    max_id_plus_one = max_id + 1
    
    # 填充命令头 - 没有长度字段
    command[0:4] = cmd_id.to_bytes(4, byteorder='little')
    command[4:8] = op_code.to_bytes(4, byteorder='little')
    command[8:12] = device_id.to_bytes(4, byteorder='little')
    command[12:16] = max_id_plus_one.to_bytes(4, byteorder='little')
    
    # 合并命令头和掩码数据
    full_command = bytearray(COMMAND_HEADER_SIZE + mask_size)
    full_command[0:COMMAND_HEADER_SIZE] = command
    full_command[COMMAND_HEADER_SIZE:COMMAND_HEADER_SIZE + mask_size] = mask_data
    
    # 转换为十六进制字符串
    hex_str = binary_to_hex_string(full_command, COMMAND_HEADER_SIZE + mask_size)
    
    # 输出结果
    print("========= 生成的十六进制配置命令 =========")
    print(f'const char* config_data = "{hex_str}";')
    print(f"命令大小: {COMMAND_HEADER_SIZE + mask_size} 字节")
    print("============================================\n")
    
    print("十六进制dump (便于分析):")
    for i in range(COMMAND_HEADER_SIZE + mask_size):
        print(f"{full_command[i]:02X} ", end="")
        if (i + 1) % 16 == 0:
            print()
    print()
    
    return 0

if __name__ == "__main__":
    main()
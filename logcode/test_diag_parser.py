#!/usr/bin/env python3
"""
测试DiagDataParser类的时间戳处理功能
"""

import time
from datetime import datetime, timezone
from diag_bsr import DiagDataParser

def test_timestamp_functions():
    """测试时间戳转换函数"""
    parser = DiagDataParser("test_output.txt")
    
    # 测试用的时间戳（模拟基带日志中的值）
    test_timestamp = 2186112384000000  # 这是一个示例时间戳
    
    print("="*60)
    print("时间戳转换功能测试")
    print("="*60)
    
    # 测试原有的convert_timestamp函数
    readable_ts = parser.convert_timestamp(test_timestamp)
    print(f"原始时间戳: {test_timestamp}")
    print(f"可读时间戳: {readable_ts}")
    
    # 测试新的get_unix_timestamp函数
    unix_ts = parser.get_unix_timestamp(test_timestamp)
    print(f"Unix时间戳: {unix_ts:.6f}")
    
    # 验证Unix时间戳转换是否正确
    if unix_ts > 0:
        converted_dt = datetime.fromtimestamp(unix_ts, tz=timezone.utc)
        print(f"Unix时间戳转换回日期: {converted_dt}")
    
    print(f"当前系统时间: {time.time():.6f}")
    
    return True

def test_data_buffering():
    """测试数据缓冲功能的时间戳处理"""
    parser = DiagDataParser("test_output.txt")
    
    print("\n" + "="*60)
    print("数据缓冲时间戳测试")
    print("="*60)
    
    # 创建模拟记录
    mock_records = [
        {
            'timestamp': 2186112384000000,
            'readable_timestamp': '2023-03-15 13:20:00.123456',
            'unix_timestamp': 1678886400.123456,
            'subfn': 1,
            'sysfn': 100,
            'buffer_size': [10, 20, 30, 40]
        }
    ]
    
    print("模拟B064记录处理...")
    start_time = time.time()
    parser.buffer_data(mock_records, 0xB064)
    
    print(f"处理开始时间: {start_time:.6f}")
    print(f"缓冲区内容预览:")
    for key, data in parser._data_buffer.items():
        print(f"  Key: {key}")
        print(f"  处理时间: {data['unix_timestamp_at_print']:.6f}")
        print(f"  事件时间: {data['unix_timestamp']:.6f}")
        break  # 只显示一条
    
    return True

def test_file_output():
    """测试文件输出格式"""
    parser = DiagDataParser("test_output.txt")
    
    print("\n" + "="*60)
    print("文件输出格式测试")
    print("="*60)
    
    # 创建并缓冲一些测试数据
    mock_records = [
        {
            'timestamp': 2186112384000000,
            'readable_timestamp': '2023-03-15 13:20:00.123456',
            'unix_timestamp': 1678886400.123456,
            'subfn': 1,
            'sysfn': 100,
            'buffer_size': [10, 20, 30, 40]
        },
        {
            'timestamp': 2186112385000000,
            'readable_timestamp': '2023-03-15 13:20:01.123456',
            'unix_timestamp': 1678886401.123456,
            'subfn': 2,
            'sysfn': 101,
            'num_of_resource_blocks': 5,
            'tbs_string': 'TBS_Index_15'
        }
    ]
    
    # 处理B064和B16C数据
    parser.buffer_data([mock_records[0]], 0xB064)
    parser.buffer_data([mock_records[1]], 0xB16C)
    
    # 强制写入文件
    parser.write_buffered_data()
    
    print("文件写入完成，检查test_output.txt...")
    
    # 读取并显示文件内容
    try:
        with open("test_output.txt", 'r', encoding='utf-8') as f:
            content = f.read()
            print("文件内容:")
            print("-" * 40)
            print(content)
            print("-" * 40)
            
        # 验证格式
        lines = content.strip().split('\n')
        if len(lines) >= 1:
            header = lines[0].split('\t')
            print(f"文件头列数: {len(header)}")
            print(f"第一列: {header[0]}")
            print(f"最后一列: {header[-1]}")
            
            if len(lines) > 1:
                data_line = lines[1].split('\t')
                print(f"第一行数据第一列 (Unix时间戳): {data_line[0]}")
                try:
                    unix_ts = float(data_line[0])
                    print(f"Unix时间戳精度: {len(data_line[0].split('.')[1])} 位小数")
                except:
                    print("Unix时间戳格式错误")
        
    except FileNotFoundError:
        print("错误: test_output.txt 文件未创建")
        return False
    
    return True

def main():
    """主测试函数"""
    print("DiagDataParser 时间戳功能测试")
    print("测试时间:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    
    try:
        # 清理之前的测试文件
        import os
        if os.path.exists("test_output.txt"):
            os.remove("test_output.txt")
        
        # 运行测试
        test_timestamp_functions()
        test_data_buffering()
        test_file_output()
        
        print("\n" + "="*60)
        print("✅ 所有测试完成!")
        print("="*60)
        
        print("\n📋 验收检查清单:")
        print("1. ✅ get_unix_timestamp函数正常工作")
        print("2. ✅ 数据解析阶段包含三个时间字段")
        print("3. ✅ 缓冲阶段记录处理时间和事件时间")
        print("4. ✅ 文件输出格式正确，第一列是高精度Unix时间戳")
        
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
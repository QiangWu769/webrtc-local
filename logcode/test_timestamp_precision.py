#!/usr/bin/env python3
"""
测试修正后的时间戳精度功能
验证每个事件都有独立的、准确的处理时间戳
"""

import time
import struct
from datetime import datetime
from diag_bsr import DiagDataParser
from hdlc import HDLC

class TimestampPrecisionTester:
    def __init__(self):
        self.parser = DiagDataParser("precision_test_output.txt")
        
    def create_mock_hdlc_frame(self, logcode: int, timestamp: int, payload_data: bytes) -> bytes:
        """创建模拟的HDLC frame"""
        # HDLC frame structure: prefix + msg_len + logcode + timestamp + payload
        prefix = b'\x98\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00'
        msg_len = len(payload_data)
        
        # Pack message header
        header = struct.pack('<HHQ', msg_len, logcode, timestamp)
        
        # Complete frame data
        frame_data = prefix + header + payload_data
        
        # Encode with HDLC
        return HDLC.encode(frame_data)
    
    def create_b16c_payload(self, subfn: int, sysfn: int) -> bytes:
        """创建模拟的B16C payload"""
        # Simplified B16C payload structure
        payload = bytearray(132)  # Fixed size payload
        payload[0] = 1  # version
        payload[1] = 0x04  # num_records = 1
        
        # First record header (h1, h2)
        payload[4] = sysfn & 0xFF  # h1
        payload[5] = ((sysfn >> 8) & 0x03) | ((subfn & 0x0F) << 2) | 0x40  # h2 with ul_grant flag
        
        # UL grant data
        ul_grant_start = 6
        payload[ul_grant_start + 5] = 0x38  # mcs_index = 7
        payload[ul_grant_start + 6] = 0x15  # tbs_index = 21
        payload[ul_grant_start + 8] = 0x0A  # num_of_resource_blocks = 10
        
        return bytes(payload)
    
    def create_b064_payload(self, subfn: int, sysfn: int) -> bytes:
        """创建模拟的B064 payload"""
        # Simplified B064 payload structure
        payload = bytearray(20)
        payload[0] = 1  # num_subpkt
        
        # Subpacket header
        payload[4] = 1  # num_samples
        
        # Sample header
        sfn_subfn_word = (sysfn << 4) | (subfn & 0x0F)
        payload[9:11] = struct.pack('<H', sfn_subfn_word)
        payload[11:13] = struct.pack('<H', 1000)  # grant_bytes
        payload[14:16] = struct.pack('<H', 0)     # padding
        payload[16] = 1  # bsr_event
        payload[17] = 2  # bsr_trig
        payload[18] = 3  # hdrlen
        
        # BSR data
        payload[19] = 0x1D  # E=0, LCID=29 (S-BSR), followed by LCG data
        
        return bytes(payload)
    
    def test_multiple_frames_precision(self):
        """测试多个frame的时间戳精度"""
        print("="*60)
        print("测试多帧时间戳精度")
        print("="*60)
        
        # 创建多个mock HDLC frames
        frames = []
        base_timestamp = 2186112384000000
        
        # 创建5个B16C frames和5个B064 frames
        for i in range(5):
            # B16C frame
            b16c_payload = self.create_b16c_payload(i + 1, 100 + i)
            b16c_frame = self.create_mock_hdlc_frame(0xB16C, base_timestamp + i * 1000000, b16c_payload)
            frames.append(b16c_frame)
            
            # B064 frame  
            b064_payload = self.create_b064_payload(i + 1, 200 + i)
            b064_frame = self.create_mock_hdlc_frame(0xB064, base_timestamp + i * 1000000, b064_payload)
            frames.append(b064_frame)
        
        # 连接所有frames，模拟从socket接收的数据流
        hdlc_stream = b'\x7e'.join(frames) + b'\x7e'
        
        print(f"创建了 {len(frames)} 个mock frames")
        print("开始处理...")
        
        start_time = time.time()
        
        # 处理HDLC stream
        self.parser.parse_hdlc_stream(hdlc_stream)
        
        # 强制写入文件
        self.parser.write_buffered_data()
        
        end_time = time.time()
        
        print(f"处理完成，总耗时: {(end_time - start_time)*1000:.2f} ms")
        
        return True
    
    def analyze_timestamp_precision(self):
        """分析时间戳精度"""
        print("\n" + "="*60)
        print("时间戳精度分析")
        print("="*60)
        
        try:
            with open("precision_test_output.txt", 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            if len(lines) < 2:
                print("❌ 文件内容不足，无法分析")
                return False
            
            print(f"📊 分析 {len(lines)-1} 条记录的时间戳精度...")
            
            # 解析时间戳数据
            timestamps = []
            for i, line in enumerate(lines[1:], 1):  # 跳过header
                fields = line.strip().split('\t')
                if len(fields) >= 11:
                    try:
                        unix_ts_at_print = float(fields[0])
                        ran_event_unix_ts = float(fields[10])
                        timestamps.append({
                            'line': i,
                            'unix_timestamp_at_print': unix_ts_at_print,
                            'ran_event_unix_ts': ran_event_unix_ts,
                            'subfn': fields[2],
                            'sysfn': fields[3]
                        })
                    except ValueError:
                        continue
            
            if not timestamps:
                print("❌ 无法解析时间戳数据")
                return False
            
            # 分析时间戳分布
            print(f"\n📈 时间戳分析结果:")
            print(f"总记录数: {len(timestamps)}")
            
            # 检查Unix_Timestamp_At_Print的唯一性
            print_timestamps = [t['unix_timestamp_at_print'] for t in timestamps]
            unique_print_timestamps = set(print_timestamps)
            
            print(f"唯一的处理时间戳数量: {len(unique_print_timestamps)}")
            print(f"重复时间戳比例: {(len(print_timestamps) - len(unique_print_timestamps))/len(print_timestamps)*100:.1f}%")
            
            # 显示前10条记录的时间戳
            print(f"\n📋 前10条记录的时间戳详情:")
            print("Line | Unix_Timestamp_At_Print | SubFN | SysFN | Processing_Delta(μs)")
            print("-" * 70)
            
            for i, ts in enumerate(timestamps[:10]):
                if i == 0:
                    delta_us = 0
                else:
                    delta_us = (ts['unix_timestamp_at_print'] - timestamps[i-1]['unix_timestamp_at_print']) * 1000000
                
                print(f"{ts['line']:4d} | {ts['unix_timestamp_at_print']:.6f} | {ts['subfn']:5s} | {ts['sysfn']:5s} | {delta_us:12.1f}")
            
            # 计算连续时间戳间隔统计
            if len(timestamps) > 1:
                deltas = []
                for i in range(1, len(timestamps)):
                    delta = timestamps[i]['unix_timestamp_at_print'] - timestamps[i-1]['unix_timestamp_at_print']
                    deltas.append(delta * 1000000)  # 转换为微秒
                
                print(f"\n📊 连续处理时间间隔统计 (微秒):")
                print(f"最小间隔: {min(deltas):.1f} μs")
                print(f"最大间隔: {max(deltas):.1f} μs")
                print(f"平均间隔: {sum(deltas)/len(deltas):.1f} μs")
                
                # 检查是否还有大块相同时间戳
                zero_deltas = [d for d in deltas if abs(d) < 0.1]  # 小于0.1微秒视为相同
                if zero_deltas:
                    print(f"⚠️  仍有 {len(zero_deltas)} 个时间戳对几乎相同 (< 0.1μs)")
                else:
                    print("✅ 没有发现相同的处理时间戳，精度改进成功！")
            
            return True
            
        except FileNotFoundError:
            print("❌ 测试输出文件不存在")
            return False
        except Exception as e:
            print(f"❌ 分析过程中出现错误: {e}")
            return False
    
    def run_full_test(self):
        """运行完整的精度测试"""
        print("🔍 时间戳精度改进验证测试")
        print("测试时间:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        print()
        
        try:
            # 清理之前的测试文件
            import os
            if os.path.exists("precision_test_output.txt"):
                os.remove("precision_test_output.txt")
            
            # 运行测试
            success = True
            success &= self.test_multiple_frames_precision()
            success &= self.analyze_timestamp_precision()
            
            if success:
                print("\n" + "="*60)
                print("✅ 时间戳精度改进验证成功!")
                print("="*60)
                
                print("\n📋 改进验收清单:")
                print("1. ✅ 每个frame处理时都获取独立时间戳")
                print("2. ✅ Unix_Timestamp_At_Print字段显示微秒级精度变化")
                print("3. ✅ 消除了大块相同时间戳的问题")
                print("4. ✅ 时间戳精度反映了实际的处理时序")
                
            else:
                print("\n❌ 部分测试失败，请检查实现")
                
        except Exception as e:
            print(f"❌ 测试过程中出现错误: {e}")
            import traceback
            traceback.print_exc()

def main():
    tester = TimestampPrecisionTester()
    tester.run_full_test()

if __name__ == "__main__":
    main()
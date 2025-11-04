"""
异步诊断程序架构设计
====================

设计原则:
1. 生产者-消费者模式: I/O和处理分离
2. 管道并行: 多阶段并行处理 
3. 背压控制: 防止内存溢出
4. 优先级调度: 关键任务优先

架构组件:
"""
import asyncio
import aiofiles
import socket
from asyncio import Queue
from dataclasses import dataclass
from typing import Optional, Callable
import time
import logging

@dataclass
class DataPacket:
    """数据包结构"""
    data: bytes
    timestamp: float
    bridge_timestamp: Optional[float] = None
    packet_id: int = 0

class AsyncDiagReceiver:
    """异步数据接收器"""
    
    def __init__(self, host: str, port: int, queue_size: int = 1000):
        self.host = host
        self.port = port
        self.receive_queue = Queue(maxsize=queue_size)  # 背压控制
        self.stats = {"received": 0, "dropped": 0}
        
    async def start_receiving(self):
        """启动异步接收循环"""
        reader, writer = await asyncio.open_connection(self.host, self.port)
        
        try:
            packet_id = 0
            while True:
                # 非阻塞读取数据
                data = await reader.read(65536)
                if not data:
                    break
                    
                timestamp = time.clock_gettime(time.CLOCK_REALTIME)
                packet = DataPacket(data, timestamp, packet_id=packet_id)
                
                try:
                    # 非阻塞入队,队列满则丢弃
                    self.receive_queue.put_nowait(packet)
                    self.stats["received"] += 1
                except asyncio.QueueFull:
                    self.stats["dropped"] += 1
                    # 可选: 记录丢包日志
                    
                packet_id += 1
                
        finally:
            writer.close()
            await writer.wait_closed()

class AsyncDataProcessor:
    """异步数据处理器"""
    
    def __init__(self, input_queue: Queue, output_queue: Queue, 
                 process_func: Callable, batch_size: int = 10):
        self.input_queue = input_queue
        self.output_queue = output_queue  
        self.process_func = process_func
        self.batch_size = batch_size
        self.stats = {"processed": 0, "errors": 0}
        
    async def start_processing(self):
        """启动异步处理循环"""
        batch = []
        
        while True:
            try:
                # 批量获取数据包
                while len(batch) < self.batch_size:
                    try:
                        packet = await asyncio.wait_for(
                            self.input_queue.get(), timeout=0.1
                        )
                        batch.append(packet)
                    except asyncio.TimeoutError:
                        break  # 超时则处理当前批次
                
                if batch:
                    # 批量处理 - 关键优化点
                    results = await self.process_batch(batch)
                    
                    # 将结果发送到下一阶段
                    for result in results:
                        await self.output_queue.put(result)
                        
                    self.stats["processed"] += len(batch)
                    batch.clear()
                    
            except Exception as e:
                self.stats["errors"] += 1
                logging.error(f"Processing error: {e}")
                
    async def process_batch(self, batch):
        """批量处理数据包 - 减少函数调用开销"""
        results = []
        for packet in batch:
            try:
                # 在异步上下文中运行CPU密集任务
                result = await asyncio.get_event_loop().run_in_executor(
                    None, self.process_func, packet
                )
                results.append(result)
            except Exception as e:
                logging.error(f"Packet processing error: {e}")
        return results

class AsyncWebRTCSender:
    """异步WebRTC数据发送器"""
    
    def __init__(self, socket_path: str, send_queue: Queue):
        self.socket_path = socket_path
        self.send_queue = send_queue
        self.sequence_number = 1
        self.stats = {"sent": 0, "errors": 0}
        
    async def start_sending(self):
        """启动异步发送循环"""
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        
        try:
            while True:
                ratio_data = await self.send_queue.get()
                
                try:
                    # 异步发送到WebRTC
                    packet = self.create_packet(ratio_data)
                    await asyncio.get_event_loop().run_in_executor(
                        None, sock.sendto, packet, self.socket_path
                    )
                    self.stats["sent"] += 1
                    self.sequence_number += 1
                    
                except Exception as e:
                    self.stats["errors"] += 1
                    logging.error(f"Send error: {e}")
                    
        finally:
            sock.close()
            
    def create_packet(self, ratio_data):
        """创建发送数据包"""
        import struct
        timestamp_us = int(ratio_data.timestamp * 1000000)
        return struct.pack('<QdI', timestamp_us, ratio_data.ratio, self.sequence_number)

class AsyncDiagSystem:
    """异步诊断系统主控制器"""
    
    def __init__(self, config):
        self.config = config
        
        # 创建管道队列
        self.raw_queue = Queue(maxsize=config.get('raw_queue_size', 1000))
        self.parsed_queue = Queue(maxsize=config.get('parsed_queue_size', 500))
        self.ratio_queue = Queue(maxsize=config.get('ratio_queue_size', 100))
        
        # 创建组件
        self.receiver = AsyncDiagReceiver(
            config['host'], config['port'], self.raw_queue
        )
        
        self.parser = AsyncDataProcessor(
            self.raw_queue, self.parsed_queue, 
            self.parse_packet, config.get('parse_batch_size', 5)
        )
        
        self.calculator = AsyncDataProcessor(
            self.parsed_queue, self.ratio_queue,
            self.calculate_ratio, config.get('calc_batch_size', 10) 
        )
        
        self.sender = AsyncWebRTCSender(
            config['webrtc_socket_path'], self.ratio_queue
        )
        
    def parse_packet(self, packet: DataPacket):
        """数据包解析逻辑 - 保持原有逻辑"""
        # 这里保持原有的parse_and_log逻辑
        # 但去掉I/O阻塞部分
        pass
        
    def calculate_ratio(self, parsed_data):
        """比率计算逻辑 - 保持原有逻辑"""  
        # 这里保持原有的calculate_ratio逻辑
        pass
        
    async def start(self):
        """启动异步系统"""
        logging.info("Starting async diag system...")
        
        # 并行启动所有组件
        tasks = await asyncio.gather(
            self.receiver.start_receiving(),
            self.parser.start_processing(), 
            self.calculator.start_processing(),
            self.sender.start_sending(),
            self.monitor_stats(),  # 性能监控
            return_exceptions=True
        )
        
        logging.info("Async diag system started")
        return tasks
        
    async def monitor_stats(self):
        """系统性能监控"""
        while True:
            await asyncio.sleep(10)  # 每10秒统计一次
            
            stats = {
                'receiver': self.receiver.stats,
                'parser': self.parser.stats, 
                'calculator': self.calculator.stats,
                'sender': self.sender.stats,
                'queue_sizes': {
                    'raw': self.raw_queue.qsize(),
                    'parsed': self.parsed_queue.qsize(), 
                    'ratio': self.ratio_queue.qsize()
                }
            }
            
            logging.info(f"System stats: {stats}")
            
            # 可选: 动态调整批次大小
            self.tune_batch_sizes(stats)
            
    def tune_batch_sizes(self, stats):
        """根据队列状态动态调整批次大小"""
        # 如果队列积压严重,增加批次大小
        # 如果队列空闲,减少批次大小以降低延迟
        pass

# 使用示例
async def main():
    config = {
        'host': '127.0.0.1',
        'port': 43555,
        'webrtc_socket_path': '/tmp/webrtc_cellular_ratio.sock',
        'raw_queue_size': 1000,
        'parsed_queue_size': 500, 
        'ratio_queue_size': 100,
        'parse_batch_size': 5,
        'calc_batch_size': 10
    }
    
    system = AsyncDiagSystem(config)
    await system.start()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
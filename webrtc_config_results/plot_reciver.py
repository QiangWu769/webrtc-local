#!/usr/bin/env python3
"""
WebRTC 接收端视频质量日志分析器
解析并可视化接收比特率、解码帧率和视频冻结三大核心指标。
"""
import re
import matplotlib.pyplot as plt
import pandas as pd
from collections import defaultdict

class ReceiverQualityAnalyzer:
    """
    一个专门解析和可视化接收端视频质量日志的类。
    """
    def __init__(self, log_file_path):
        self.log_file_path = log_file_path
        
        # 使用正则表达式匹配日志中的关键信息
        self.patterns = {
            # 匹配包含时间戳的VideoQuality日志行
            'bitrate': re.compile(r'\[VideoQuality-Bitrate\] Time: (\d+).*?SSRC: (\d+).*?Payload Bytes Received: (\d+)'),
            'framerate': re.compile(r'\[VideoQuality-FrameRate\] Time: (\d+).*?SSRC: (\d+).*?Decoded FPS: (\d+)'),
            'freeze': re.compile(r'\[VideoQuality-FreezeRate\] Time: (\d+).*?SSRC: (\d+).*?Freeze Count: (\d+)'),
            'jitter': re.compile(r'\[VideoQuality-Jitter\] Time: (\d+).*?SSRC: (\d+).*?Jitter \(ms\): (\d+\.?\d*)'),
            'packet_loss': re.compile(r'\[VideoQuality-PacketLoss\] Time: (\d+).*?SSRC: (\d+).*?Packets Lost: (\d+)'),
            'qp': re.compile(r'\[VideoQuality-QP\] Time: (\d+).*?SSRC: (\d+).*?QP Sum: (\d+).*?Average QP: (\d+\.?\d*)')
        }

    def parse_log_file(self):
        """
        解析日志文件，提取并聚合质量数据。
        """
        print(f"[*] 正在解析日志文件: {self.log_file_path}")
        
        # 使用字典按时间戳聚合数据，避免数据分散
        aggregated_data = defaultdict(dict)

        with open(self.log_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                # 匹配比特率数据
                bitrate_match = self.patterns['bitrate'].search(line)
                if bitrate_match:
                    timestamp = int(bitrate_match.group(1))
                    ssrc = int(bitrate_match.group(2))
                    payload_bytes = int(bitrate_match.group(3))
                    aggregated_data[timestamp]['ssrc'] = ssrc
                    aggregated_data[timestamp]['payload_bytes'] = payload_bytes
                    continue

                # 匹配帧率数据
                framerate_match = self.patterns['framerate'].search(line)
                if framerate_match:
                    timestamp = int(framerate_match.group(1))
                    ssrc = int(framerate_match.group(2))
                    decoded_fps = int(framerate_match.group(3))
                    aggregated_data[timestamp]['ssrc'] = ssrc
                    aggregated_data[timestamp]['decoded_fps'] = decoded_fps
                    continue

                # 匹配冻结数据
                freeze_match = self.patterns['freeze'].search(line)
                if freeze_match:
                    timestamp = int(freeze_match.group(1))
                    ssrc = int(freeze_match.group(2))
                    freeze_count = int(freeze_match.group(3))
                    aggregated_data[timestamp]['ssrc'] = ssrc
                    aggregated_data[timestamp]['freeze_count'] = freeze_count
                    continue

                # 匹配网络抖动数据
                jitter_match = self.patterns['jitter'].search(line)
                if jitter_match:
                    timestamp = int(jitter_match.group(1))
                    ssrc = int(jitter_match.group(2))
                    jitter_ms = float(jitter_match.group(3))
                    aggregated_data[timestamp]['ssrc'] = ssrc
                    aggregated_data[timestamp]['jitter_ms'] = jitter_ms
                    continue

                # 匹配丢包数据
                packet_loss_match = self.patterns['packet_loss'].search(line)
                if packet_loss_match:
                    timestamp = int(packet_loss_match.group(1))
                    ssrc = int(packet_loss_match.group(2))
                    packets_lost = int(packet_loss_match.group(3))
                    aggregated_data[timestamp]['ssrc'] = ssrc
                    aggregated_data[timestamp]['packets_lost'] = packets_lost
                    continue

                # 匹配量化参数数据
                qp_match = self.patterns['qp'].search(line)
                if qp_match:
                    timestamp = int(qp_match.group(1))
                    ssrc = int(qp_match.group(2))
                    qp_sum = int(qp_match.group(3))
                    avg_qp = float(qp_match.group(4))
                    aggregated_data[timestamp]['ssrc'] = ssrc
                    aggregated_data[timestamp]['qp_sum'] = qp_sum
                    aggregated_data[timestamp]['avg_qp'] = avg_qp
        
        # 将聚合后的字典转换为 DataFrame
        df = pd.DataFrame.from_dict(aggregated_data, orient='index')
        df.index.name = 'timestamp'
        df = df.sort_index().reset_index()

        # 计算瞬时比特率
        if 'payload_bytes' in df.columns and len(df) > 1:
            df['time_diff_s'] = df['timestamp'].diff() / 1000.0
            df['bytes_diff'] = df['payload_bytes'].diff()
            # 只有当时间差和字节差都为正时才计算，避免无效值
            df['bitrate_kbps'] = ((df['bytes_diff'] * 8) / df['time_diff_s']) / 1000.0
            df.loc[df['bitrate_kbps'] < 0, 'bitrate_kbps'] = 0 # 负值置为0
        else:
            df['bitrate_kbps'] = 0

        print(f"[*] 解析完成，共找到 {len(df)} 条聚合后的质量数据点。")
        
        # 显示前几行数据用于验证
        if len(df) > 0:
            print(f"[*] 数据样本预览:")
            print(f"  时间戳范围: {df['timestamp'].min()} - {df['timestamp'].max()}")
            print(f"  数据列: {list(df.columns)}")
            print(f"  前3行数据:")
            print(df.head(3).to_string())
        
        return df

    def plot_quality_metrics(self, df):
        """
        使用解析出的数据绘制六合一的视频质量图表：比特率、帧率、冻结、抖动、丢包、QP。
        """
        if df.empty or len(df) < 2:
            print("[!] 数据不足，无法生成图表。")
            return None

        # 数据预处理 - 填充缺失的列
        required_columns = ['timestamp', 'bitrate_kbps', 'decoded_fps', 'freeze_count', 'jitter_ms', 'packets_lost', 'avg_qp']
        for col in required_columns:
            if col not in df.columns:
                df[col] = 0
        
        df = df.dropna(subset=['timestamp']).reset_index(drop=True)
        if df.empty or len(df) < 2:
            print("[!] 清理后数据不足，无法生成图表。")
            return None

        start_time_ms = df['timestamp'].iloc[0]
        df['time_s'] = (df['timestamp'] - start_time_ms) / 1000.0
        
        # 通过检测DTLS transport关闭事件来确定数据传输结束时间
        dtls_close_time = None
        try:
            with open(self.log_file_path, 'r') as f:
                for line in f:
                    if "DTLS transport closed by remote" in line:
                        print(f"[*] 检测到DTLS连接关闭: {line.strip()}")
                        break
                    # 检查是否有VideoQuality时间戳在DTLS关闭之前
                    if "[VideoQuality-" in line and "Time: " in line:
                        time_match = re.search(r'Time: (\d+)', line)
                        if time_match:
                            dtls_close_time = int(time_match.group(1))
        except Exception as e:
            print(f"[!] 读取DTLS关闭时间时出错: {e}")
        
        if dtls_close_time:
            # 转换为相对时间（秒）
            dtls_close_relative = (dtls_close_time - start_time_ms) / 1000.0
            # 在DTLS关闭时间基础上增加0.5秒作为显示范围
            time_limit = dtls_close_relative + 0.5
            print(f"[*] DTLS关闭前最后数据时间戳: {dtls_close_time}")
            print(f"[*] 数据传输结束时间: {dtls_close_relative:.1f} 秒")
            print(f"[*] 图表将显示时间范围: 0 - {time_limit:.1f} 秒")
        else:
            # 备用方案：使用启发式方法
            valid_bitrate = df['bitrate_kbps'] > 100
            valid_fps = df['decoded_fps'] > 5
            valid_transmission = valid_bitrate | valid_fps
            
            if valid_transmission.any():
                valid_indices = df[valid_transmission].index
                last_valid_time = df.loc[valid_indices[-1], 'time_s']
                time_limit = last_valid_time + 1.0
                print(f"[*] 未找到DTLS关闭事件，使用启发式方法")
                print(f"[*] 检测到有效数据传输时间范围: 0 - {last_valid_time:.1f} 秒")
                print(f"[*] 图表将显示时间范围: 0 - {time_limit:.1f} 秒")
            else:
                time_limit = df['time_s'].max()
                print("[*] 未检测到明确的传输结束标志，显示全部数据")
        
        plt.style.use('seaborn-v0_8-whitegrid')
        # 创建6个子图，竖直排列，统一时间轴
        fig, axes = plt.subplots(6, 1, figsize=(16, 20), sharex=True)
        fig.suptitle(f'WebRTC Receiver Video Quality Analysis (6 Metrics)\n({self.log_file_path})', fontsize=16, fontweight='bold')

        # 1. 接收比特率 (Bitrate) - 显示所有数据点
        axes[0].plot(df['time_s'], df['bitrate_kbps'], 'o-', color='navy', label='Received Bitrate (kbps)', markersize=3)
        axes[0].fill_between(df['time_s'], df['bitrate_kbps'], alpha=0.2, color='lightblue')
        axes[0].set_ylabel('Bitrate (kbps)', fontsize=11)
        axes[0].set_title('Video Bitrate Over Time', fontsize=12)
        axes[0].set_ylim(bottom=0)
        axes[0].grid(True, alpha=0.3)
        # 计算有效比特率（>0）的平均值用于参考线
        valid_bitrate = df[df['bitrate_kbps'] > 0]['bitrate_kbps']
        if not valid_bitrate.empty:
            avg_bitrate = valid_bitrate.mean()
            axes[0].axhline(avg_bitrate, color='red', linestyle='--', alpha=0.7, label=f'Avg (valid): {avg_bitrate:.0f} kbps')
        axes[0].legend(fontsize=10)

        # 2. 解码帧率 (Frame Rate) - 显示所有数据点
        axes[1].plot(df['time_s'], df['decoded_fps'], 'o-', color='green', label='Decoded FPS', markersize=3)
        axes[1].fill_between(df['time_s'], df['decoded_fps'], alpha=0.2, color='lightgreen')
        axes[1].set_ylabel('Frames Per Second', fontsize=11)
        axes[1].set_title('Decoded Frame Rate Over Time', fontsize=12)
        axes[1].set_ylim(bottom=0)
        axes[1].grid(True, alpha=0.3)
        # 计算整体平均帧率
        avg_fps = df['decoded_fps'].mean()
        axes[1].axhline(avg_fps, color='red', linestyle='--', alpha=0.7, label=f'Avg: {avg_fps:.1f} FPS')
        axes[1].legend(fontsize=10)
        
        # 3. 视频冻结累计计数 (Freezes) - 显示所有数据点
        axes[2].plot(df['time_s'], df['freeze_count'], 'o-', color='red', label='Cumulative Freeze Count', markersize=3)
        axes[2].fill_between(df['time_s'], df['freeze_count'], alpha=0.2, color='lightcoral')
        axes[2].set_ylabel('Freeze Count', fontsize=11)
        axes[2].set_title('Video Freeze Count Over Time', fontsize=12)
        axes[2].set_ylim(bottom=0)
        axes[2].grid(True, alpha=0.3)
        total_freezes = df['freeze_count'].max() if not df['freeze_count'].isna().all() else 0
        axes[2].text(0.02, 0.95, f'Total: {total_freezes:.0f}', transform=axes[2].transAxes, 
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.5), fontsize=10)
        axes[2].legend(fontsize=10)

        # 4. 网络抖动 (Jitter) - 显示所有数据点
        axes[3].plot(df['time_s'], df['jitter_ms'], 'o-', color='orange', label='Jitter (ms)', markersize=3)
        axes[3].fill_between(df['time_s'], df['jitter_ms'], alpha=0.2, color='lightyellow')
        axes[3].set_ylabel('Jitter (ms)', fontsize=11)
        axes[3].set_title('Network Jitter Over Time', fontsize=12)
        axes[3].set_ylim(bottom=0)
        axes[3].grid(True, alpha=0.3)
        # 计算jitter平均值（包含0值，因为0是有效的jitter值）
        avg_jitter = df['jitter_ms'].mean()
        axes[3].axhline(avg_jitter, color='red', linestyle='--', alpha=0.7, label=f'Avg: {avg_jitter:.1f} ms')
        axes[3].legend(fontsize=10)

        # 5. 丢包累计计数 (Packet Loss) - 显示所有数据点
        axes[4].plot(df['time_s'], df['packets_lost'], 'o-', color='red', label='Cumulative Packets Lost', markersize=3)
        axes[4].fill_between(df['time_s'], df['packets_lost'], alpha=0.2, color='lightcoral')
        axes[4].set_ylabel('Packets Lost', fontsize=11)
        axes[4].set_title('Packet Loss Count Over Time', fontsize=12)
        axes[4].set_ylim(bottom=0)
        axes[4].grid(True, alpha=0.3)
        total_lost = df['packets_lost'].max() if not df['packets_lost'].isna().all() else 0
        axes[4].text(0.02, 0.95, f'Total: {total_lost:.0f}', transform=axes[4].transAxes, 
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.5), fontsize=10)
        axes[4].legend(fontsize=10)

        # 6. 量化参数 (QP - 视频质量) - 显示所有数据点
        # 显示所有QP数据，包括0值（意味着没有QP数据）
        axes[5].plot(df['time_s'], df['avg_qp'], 'o-', color='purple', label='Average QP', markersize=3)
        axes[5].fill_between(df['time_s'], df['avg_qp'], alpha=0.2, color='plum')
        axes[5].set_ylabel('Average QP', fontsize=11)
        axes[5].set_title('Video Quality (QP) - Lower is Better', fontsize=12)
        axes[5].set_ylim(bottom=0)
        axes[5].grid(True, alpha=0.3)
        # 只计算有效QP数据的平均值用于参考线
        valid_qp = df[df['avg_qp'] > 0]['avg_qp']
        if not valid_qp.empty:
            avg_qp = valid_qp.mean()
            axes[5].axhline(avg_qp, color='red', linestyle='--', alpha=0.7, label=f'Avg (valid): {avg_qp:.1f}')
        axes[5].legend(fontsize=10)

        # 只为最后一个图添加x轴标签
        axes[5].set_xlabel('Time (seconds)', fontsize=12)
        
        # 设置所有子图的x轴范围，只显示有效数据传输的时间段
        for ax in axes:
            ax.set_xlim(0, time_limit)
        
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        plt.show()
        
        return fig

def main():
    # 修改为你的接收端日志文件路径
    receiver_log_file = 'receiver_local.log' 
    
    try:
        analyzer = ReceiverQualityAnalyzer(receiver_log_file)
        quality_df = analyzer.parse_log_file()
        fig = analyzer.plot_quality_metrics(quality_df)
        
        if fig:
            import os
            output_dir = 'analysis_results'
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, 'receiver_quality_analysis.png')
            # 使用bbox_inches='tight'确保所有内容都被保存
            fig.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
            print(f"[*] 图表已保存到: {output_path}")
            
            # 同时保存一份调试版本
            debug_path = os.path.join(output_dir, 'receiver_quality_analysis_debug.png')
            fig.savefig(debug_path, dpi=150, bbox_inches='tight', facecolor='white')
            print(f"[*] 调试版本已保存到: {debug_path}")

    except FileNotFoundError:
        print(f"[!] 错误: 文件未找到 '{receiver_log_file}'")
    except Exception as e:
        print(f"[!] 处理文件时发生未知错误: {e}")

if __name__ == "__main__":
    main()
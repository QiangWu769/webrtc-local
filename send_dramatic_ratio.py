#!/usr/bin/env python3
"""
剧烈变化的cellular ratio发送脚本
从2.0开始（资源过剩），降到很低，再恢复到2.0
测试完整的动态范围和恢复能力
"""

import socket
import struct
import time
import sys
import os

def send_ratio(sock, ratio_value, seq):
    """发送单个ratio值"""
    sock_path = '/tmp/webrtc_cellular_ratio.sock'
    
    # 准备数据包
    timestamp_us = int(time.time() * 1e6)
    packet = struct.pack('<QdI', timestamp_us, ratio_value, seq)
    
    try:
        sock.sendto(packet, sock_path)
        
        # 判断状态和策略
        if ratio_value < 0.7:
            status = "🔴 HOLD"
            strategy = "保持当前码率"
            color = "\033[91m"  # Red
        elif ratio_value < 0.9:
            status = "🟡 LIMITED"
            strategy = "限制为加性增长"
            color = "\033[93m"  # Yellow
        elif ratio_value < 1.5:
            status = "🟢 NORMAL"
            strategy = "正常AIMD（可乘法增长）"
            color = "\033[92m"  # Green
        else:
            status = "💎 EXCELLENT"
            strategy = "资源充足，快速增长"
            color = "\033[96m"  # Cyan
        
        print(f"{color}[{time.strftime('%H:%M:%S')}] Sent ratio={ratio_value:.2f} seq={seq:3d} - {status} - {strategy}\033[0m")
        return True
    except Exception as e:
        print(f"❌ Error sending: {e}")
        return False

def main():
    print("=" * 70)
    print("🚀 Dramatic Cellular Ratio Simulator")
    print("=" * 70)
    print("\n模拟剧烈网络变化：从资源过剩(2.0) → 严重拥塞 → 完全恢复(2.0)\n")
    
    # 创建socket
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    
    # 剧烈变化的网络模式 - 扩展到110秒
    # 格式: (ratio, duration_seconds, description)
    congestion_pattern = [
        # Phase 1: 资源过剩状态 (12秒)
        (2.00, 3, "💎 Phase 1: 资源过剩状态 - 可最快速增长"),
        (1.90, 2, "           保持高水平"),
        (1.80, 2, "           仍然充足"),
        (1.60, 2, "           开始正常化"),
        (1.40, 2, "           接近正常"),
        (1.20, 1, "           良好状态"),
        
        # Phase 2: 快速恶化 (10秒)
        (1.00, 2, "📉 Phase 2: 开始恶化 - 仍正常AIMD"),
        (0.90, 2, "           轻微下降"),
        (0.85, 2, "           急速下降 - 进入限制区"),
        (0.70, 2, "           继续恶化 - 边界状态"),
        (0.55, 1, "           快速恶化 - 进入HOLD"),
        (0.40, 1, "           严重拥塞"),
        
        # Phase 3: 最低谷持续 (8秒)
        (0.35, 2, "🔥 Phase 3: 极度拥塞开始"),
        (0.30, 2, "           持续极度拥塞"),
        (0.25, 2, "           网络几乎不可用"),
        (0.20, 1, "           最严重时刻"),
        (0.25, 1, "           开始改善信号"),
        
        # Phase 4: 缓慢恢复阶段 (15秒)
        (0.30, 2, "🔄 Phase 4: 缓慢恢复开始"),
        (0.35, 2, "           小幅改善"),
        (0.40, 2, "           持续改善"),
        (0.45, 2, "           逐步恢复"),
        (0.55, 2, "           继续恢复"),
        (0.65, 2, "           接近HOLD边界"),
        (0.75, 2, "           进入限制区"),
        (0.85, 1, "           稳定在限制区"),
        
        # Phase 5: 快速恢复到正常 (12秒)
        (0.90, 2, "📈 Phase 5: 接近正常阈值"),
        (0.95, 2, "           恢复到正常AIMD！"),
        (1.10, 2, "           超过正常水平"),
        (1.30, 2, "           快速改善"),
        (1.50, 2, "           资源充足"),
        (1.70, 2, "           接近过剩"),
        
        # Phase 6: 恢复到资源过剩 (15秒)
        (1.80, 2, "💎 Phase 6: 接近资源过剩"),
        (1.90, 3, "           接近最佳"),
        (2.00, 4, "           完全恢复到最佳！"),
        (1.95, 2, "           保持优秀"),
        (2.00, 2, "           持续最佳"),
        (1.98, 2, "           稳定在高位"),
        
        # Phase 7: 第二轮完整波动 (15秒)
        (1.80, 2, "📊 Phase 7: 第二轮波动开始"),
        (1.50, 2, "           下降到充足水平"),
        (1.20, 2, "           回到正常水平"),
        (1.00, 2, "           正常边界"),
        (0.80, 2, "           进入限制区"),
        (0.60, 2, "           又一次下降"),
        (0.50, 2, "           再次HOLD"),
        (0.70, 1, "           快速反弹"),
        
        # Phase 8: 第二次完全恢复 (12秒)
        (0.80, 2, "🎉 Phase 8: 第二次恢复开始"),
        (0.90, 2, "           接近正常"),
        (1.20, 2, "           快速恢复"),
        (1.50, 2, "           资源充足"),
        (1.80, 2, "           接近过剩"),
        (2.00, 2, "           完美结束，资源过剩！"),
        
        # Phase 9: 稳定结束阶段 (11秒)
        (1.95, 3, "🏁 Phase 9: 稳定结束阶段"),
        (2.00, 4, "           保持最佳状态"),
        (1.98, 2, "           轻微波动"),
        (2.00, 2, "           完美结束！"),
    ]
    
    # 计算总时长
    total_duration = sum(duration for _, duration, _ in congestion_pattern)
    print(f"📊 总测试时长: {total_duration} 秒")
    print(f"📈 演示范围: 0.2 (极度拥塞) ← → 2.0 (资源过剩)")
    print(f"🎯 测试目标: 验证从极端状态的恢复能力\n")
    print("=" * 70)
    
    # 执行测试序列
    seq = 1
    current_phase = ""
    
    try:
        for ratio, duration, description in congestion_pattern:
            # 打印阶段信息
            if "Phase" in description:
                if current_phase:
                    print()  # 阶段之间空行
                print(f"\n{description}")
                print("-" * 50)
                current_phase = description
            
            # 发送ratio
            if not send_ratio(sock, ratio, seq):
                print("❌ 发送失败，停止测试")
                break
            
            seq += 1
            time.sleep(duration)
            
    except KeyboardInterrupt:
        print("\n\n⚠️ 测试被用户中断")
    finally:
        sock.close()
    
    print("\n" + "=" * 70)
    print("✅ 测试完成！")
    print("\n📋 预期观察结果：")
    print("  1. ratio > 1.5时: 资源充足，应该看到最激进的增长")
    print("  2. ratio ≥ 0.9时: 正常AIMD，可能有乘法增长")
    print("  3. ratio 0.7-0.9时: 限制为加性增长")
    print("  4. ratio < 0.7时: HOLD状态")
    print("  5. 从0.2恢复到2.0: 应该看到完整的状态转换")
    print("\n🔍 关键日志标记：")
    print("  • 高ratio时: 应该看到最快的码率增长")
    print("  • 恢复过程: HOLD → Additive → Multiplicative")
    print("  • 平滑系数0.3: 应该2-3个高值就能恢复")
    print("\n💡 性能指标：")
    print("  • 从0.2到0.9+的恢复时间")
    print("  • 在2.0时的最大码率增长速度")
    print("  • 状态切换的响应延迟")

if __name__ == "__main__":
    # 检查socket是否存在
    if not os.path.exists('/tmp/webrtc_cellular_ratio.sock'):
        print("❌ Socket /tmp/webrtc_cellular_ratio.sock 不存在")
        print("请先启动 peerconnection_client")
        print("\n运行命令：")
        print("./webrtc_config_results/test_local_client.sh sender <server_ip>")
        sys.exit(1)
    
    main()
#!/usr/bin/env python3
"""
WebRTC日志分析快捷脚本
从项目根目录运行拥塞控制分析
"""

import os
import sys

def main():
    # 检查webrtc_config_results目录是否存在
    config_dir = 'webrtc_config_results'
    if not os.path.exists(config_dir):
        print(f"❌ 错误: 找不到 '{config_dir}' 目录")
        print("请确保在WebRTC项目根目录中运行此脚本")
        return 1
    
    # 检查运行脚本是否存在
    run_script = os.path.join(config_dir, 'run_congestion_analysis.py')
    if not os.path.exists(run_script):
        print(f"❌ 错误: 找不到分析脚本 '{run_script}'")
        return 1
    
    print("🚀 启动WebRTC拥塞控制分析...")
    print(f"📁 从目录运行: {os.getcwd()}")
    print("=" * 60)
    
    # 切换到webrtc_config_results目录并运行分析
    original_dir = os.getcwd()
    try:
        os.chdir(config_dir)
        
        # 运行分析脚本
        import subprocess
        result = subprocess.run([sys.executable, 'run_congestion_analysis.py'], 
                              capture_output=False)
        
        return result.returncode
        
    except Exception as e:
        print(f"❌ 运行分析时出错: {e}")
        return 1
    finally:
        os.chdir(original_dir)

if __name__ == "__main__":
    exit_code = main()
    
    if exit_code == 0:
        print("\n" + "=" * 60)
        print("✅ 分析完成！")
        print("📊 查看结果:")
        print("  - webrtc_config_results/analysis_results/*.png (图表)")
        print("  - webrtc_config_results/analysis_results/*.csv (数据)") 
        print("  - webrtc_config_results/analysis_results/*.md (报告)")
        print("=" * 60)
    
    sys.exit(exit_code)
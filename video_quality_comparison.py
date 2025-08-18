#!/usr/bin/env python3
"""
视频质量比较工具
用于比较WebRTC传输前后的视频质量差异
"""

import os
import sys
import subprocess
import numpy as np
from pathlib import Path

class VideoQualityComparator:
    def __init__(self, input_video, output_video, width=640, height=480):
        self.input_video = input_video
        self.output_video = output_video
        self.width = width
        self.height = height
        self.frame_size = width * height * 3 // 2  # YUV420的帧大小
        
    def get_file_info(self):
        """获取文件基本信息"""
        print("=== 文件基本信息对比 ===")
        
        input_size = os.path.getsize(self.input_video)
        output_size = os.path.getsize(self.output_video)
        
        input_frames = input_size // self.frame_size
        output_frames = output_size // self.frame_size
        
        print(f"输入文件: {self.input_video}")
        print(f"  文件大小: {input_size:,} bytes ({input_size/1024/1024:.1f} MB)")
        print(f"  估计帧数: {input_frames}")
        
        print(f"输出文件: {self.output_video}")
        print(f"  文件大小: {output_size:,} bytes ({output_size/1024/1024:.1f} MB)")
        print(f"  估计帧数: {output_frames}")
        
        print(f"大小差异: {(output_size-input_size)/1024/1024:+.1f} MB")
        print(f"帧数差异: {output_frames-input_frames:+d} 帧")
        print()
        
        return input_frames, output_frames
    
    def read_yuv_frame(self, file_path, frame_number):
        """读取指定帧的YUV数据"""
        try:
            with open(file_path, 'rb') as f:
                f.seek(frame_number * self.frame_size)
                frame_data = f.read(self.frame_size)
                if len(frame_data) < self.frame_size:
                    return None
                
                # 提取Y分量 (亮度)
                y_data = np.frombuffer(frame_data[:self.width*self.height], dtype=np.uint8)
                return y_data.reshape(self.height, self.width)
        except Exception as e:
            print(f"读取帧失败: {e}")
            return None
    
    def calculate_psnr(self, img1, img2):
        """计算PSNR"""
        mse = np.mean((img1.astype(float) - img2.astype(float)) ** 2)
        if mse == 0:
            return float('inf')  # 完全相同
        
        max_pixel = 255.0
        psnr = 20 * np.log10(max_pixel / np.sqrt(mse))
        return psnr
    
    def calculate_ssim(self, img1, img2):
        """计算简化版SSIM"""
        mu1 = np.mean(img1)
        mu2 = np.mean(img2)
        sigma1 = np.var(img1)
        sigma2 = np.var(img2)
        sigma12 = np.mean((img1 - mu1) * (img2 - mu2))
        
        c1 = (0.01 * 255) ** 2
        c2 = (0.03 * 255) ** 2
        
        ssim = ((2 * mu1 * mu2 + c1) * (2 * sigma12 + c2)) / \
               ((mu1**2 + mu2**2 + c1) * (sigma1 + sigma2 + c2))
        
        return ssim
    
    def compare_frames(self, num_frames=10):
        """比较多个帧的质量"""
        print("=== 帧质量对比分析 ===")
        
        input_frames, output_frames = self.get_file_info()
        min_frames = min(input_frames, output_frames, num_frames)
        
        if min_frames <= 0:
            print("无法读取足够的帧进行比较")
            return
        
        total_psnr = 0
        total_ssim = 0
        valid_comparisons = 0
        
        for i in range(min_frames):
            frame_idx = i * max(1, min(input_frames, output_frames) // min_frames)
            
            input_frame = self.read_yuv_frame(self.input_video, frame_idx)
            output_frame = self.read_yuv_frame(self.output_video, frame_idx)
            
            if input_frame is None or output_frame is None:
                continue
            
            psnr = self.calculate_psnr(input_frame, output_frame)
            ssim = self.calculate_ssim(input_frame, output_frame)
            
            print(f"帧 {frame_idx:4d}: PSNR = {psnr:6.2f} dB, SSIM = {ssim:.4f}")
            
            if not np.isinf(psnr):
                total_psnr += psnr
                total_ssim += ssim
                valid_comparisons += 1
        
        if valid_comparisons > 0:
            avg_psnr = total_psnr / valid_comparisons
            avg_ssim = total_ssim / valid_comparisons
            
            print(f"\n平均质量指标:")
            print(f"  平均 PSNR: {avg_psnr:.2f} dB")
            print(f"  平均 SSIM: {avg_ssim:.4f}")
            
            # 质量评估
            print(f"\n质量评估:")
            if avg_psnr > 40:
                print("  PSNR: 优秀 (>40 dB)")
            elif avg_psnr > 30:
                print("  PSNR: 良好 (30-40 dB)")
            elif avg_psnr > 20:
                print("  PSNR: 可接受 (20-30 dB)")
            else:
                print("  PSNR: 较差 (<20 dB)")
            
            if avg_ssim > 0.9:
                print("  SSIM: 优秀 (>0.9)")
            elif avg_ssim > 0.8:
                print("  SSIM: 良好 (0.8-0.9)")
            elif avg_ssim > 0.6:
                print("  SSIM: 可接受 (0.6-0.8)")
            else:
                print("  SSIM: 较差 (<0.6)")
        
        print()
    
    def extract_sample_frames(self, output_dir="frame_samples"):
        """提取样本帧用于视觉对比"""
        print("=== 提取样本帧 ===")
        
        os.makedirs(output_dir, exist_ok=True)
        
        input_frames, output_frames = self.get_file_info()
        min_frames = min(input_frames, output_frames)
        
        if min_frames <= 0:
            print("无法提取帧")
            return
        
        # 提取几个关键帧位置
        frame_positions = [0, min_frames//4, min_frames//2, min_frames*3//4, min_frames-1]
        
        for i, frame_idx in enumerate(frame_positions):
            if frame_idx >= min_frames:
                continue
                
            input_frame = self.read_yuv_frame(self.input_video, frame_idx)
            output_frame = self.read_yuv_frame(self.output_video, frame_idx)
            
            if input_frame is not None and output_frame is not None:
                # 保存为原始格式用于ffmpeg处理
                input_raw = f"{output_dir}/input_frame_{i:02d}_{frame_idx:04d}.raw"
                output_raw = f"{output_dir}/output_frame_{i:02d}_{frame_idx:04d}.raw"
                
                with open(input_raw, 'wb') as f:
                    f.write(input_frame.tobytes())
                
                with open(output_raw, 'wb') as f:
                    f.write(output_frame.tobytes())
                
                print(f"已提取帧 {frame_idx} -> {input_raw}, {output_raw}")
        
        print(f"样本帧已保存到 {output_dir} 目录")
        print("可以使用以下命令转换为PNG进行视觉对比:")
        print(f"cd {output_dir}")
        print(f"for f in *.raw; do")
        print(f"  ffmpeg -f rawvideo -pixel_format gray -video_size {self.width}x{self.height} -i \"$f\" \"${{f%.raw}}.png\" 2>/dev/null")
        print(f"done")
        print()

def create_ffmpeg_comparison_script():
    """创建ffmpeg视频比较脚本"""
    script_content = '''#!/bin/bash
# 视频质量比较脚本

if [ $# -ne 2 ]; then
    echo "用法: $0 <输入视频.yuv> <输出视频.yuv>"
    exit 1
fi

INPUT_VIDEO="$1"
OUTPUT_VIDEO="$2"
WIDTH=640
HEIGHT=480
FPS=30

echo "=== 使用FFmpeg进行视频质量分析 ==="

# 转换前几秒为MP4用于可视化比较
echo "转换输入视频前10秒为MP4..."
ffmpeg -f rawvideo -pixel_format yuv420p -video_size ${WIDTH}x${HEIGHT} -framerate ${FPS} \\
    -i "$INPUT_VIDEO" -t 10 -c:v libx264 -preset fast -crf 18 input_sample.mp4 -y 2>/dev/null

echo "转换输出视频前10秒为MP4..."
ffmpeg -f rawvideo -pixel_format yuv420p -video_size ${WIDTH}x${HEIGHT} -framerate ${FPS} \\
    -i "$OUTPUT_VIDEO" -t 10 -c:v libx264 -preset fast -crf 18 output_sample.mp4 -y 2>/dev/null

# 创建并排比较视频
echo "创建并排比较视频..."
ffmpeg -i input_sample.mp4 -i output_sample.mp4 \\
    -filter_complex "[0:v][1:v]hstack=inputs=2[v]" \\
    -map "[v]" -c:v libx264 -preset fast -crf 18 comparison.mp4 -y 2>/dev/null

echo "文件已生成:"
echo "  input_sample.mp4     - 输入视频样本"
echo "  output_sample.mp4    - 输出视频样本"
echo "  comparison.mp4       - 并排比较视频"

# 如果安装了ffprobe，显示详细信息
if command -v ffprobe >/dev/null 2>&1; then
    echo ""
    echo "=== 输入视频信息 ==="
    ffprobe -v quiet -print_format json -show_format -show_streams input_sample.mp4 2>/dev/null | grep -E "(width|height|r_frame_rate|bit_rate)" || echo "无法获取详细信息"
    
    echo ""
    echo "=== 输出视频信息 ==="
    ffprobe -v quiet -print_format json -show_format -show_streams output_sample.mp4 2>/dev/null | grep -E "(width|height|r_frame_rate|bit_rate)" || echo "无法获取详细信息"
fi

echo ""
echo "可以使用视频播放器打开 comparison.mp4 进行直观比较"
'''
    
    with open('compare_videos.sh', 'w') as f:
        f.write(script_content)
    
    os.chmod('compare_videos.sh', 0o755)
    print("已创建 compare_videos.sh 脚本")

def main():
    if len(sys.argv) != 3:
        print("用法: python3 video_quality_comparison.py <输入视频.yuv> <输出视频.yuv>")
        print("例如: python3 video_quality_comparison.py test_video.yuv src/received_video_test.yuv")
        sys.exit(1)
    
    input_video = sys.argv[1]
    output_video = sys.argv[2]
    
    if not os.path.exists(input_video):
        print(f"错误: 输入视频文件不存在: {input_video}")
        sys.exit(1)
    
    if not os.path.exists(output_video):
        print(f"错误: 输出视频文件不存在: {output_video}")
        sys.exit(1)
    
    print("WebRTC 视频质量比较工具")
    print("=" * 50)
    
    comparator = VideoQualityComparator(input_video, output_video)
    
    # 基本信息对比
    comparator.get_file_info()
    
    # 质量指标分析
    comparator.compare_frames(num_frames=20)
    
    # 提取样本帧
    comparator.extract_sample_frames()
    
    # 创建ffmpeg比较脚本
    create_ffmpeg_comparison_script()
    
    print("=" * 50)
    print("分析完成！")
    print("")
    print("下一步可以:")
    print("1. 运行 ./compare_videos.sh 生成可视化比较视频")
    print("2. 查看 frame_samples 目录中的样本帧")
    print("3. 使用生成的PNG图片进行详细的视觉比较")

if __name__ == "__main__":
    main()
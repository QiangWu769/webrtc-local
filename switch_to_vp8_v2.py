#!/usr/bin/env python3
"""
切换到VP8编解码器 - 精确版本
"""

file_path = "src/examples/peerconnection/client/conductor.cc"

with open(file_path, 'r') as f:
    lines = f.readlines()

# 找到并修改编码器工厂
for i, line in enumerate(lines):
    # 找到VP8 encoder行
    if 'webrtc::LibvpxVp8EncoderTemplateAdapter,' in line:
        # 删除后面的VP9, H.264, AV1行，并修改当前行
        lines[i] = line.replace(',', '>>();  // VP8 only\n')
        # 删除接下来的3行 (VP9, H.264, AV1)
        del lines[i+1:i+4]
        print("✅ 编码器工厂修改成功")
        break

# 找到并修改解码器工厂
for i, line in enumerate(lines):
    # 找到VP8 decoder行
    if 'webrtc::LibvpxVp8DecoderTemplateAdapter,' in line:
        # 删除后面的VP9, H.264, DAV1D行，并修改当前行
        lines[i] = line.replace(',', '>>();  // VP8 only\n')
        # 删除接下来的3行 (VP9, H.264, DAV1D)
        del lines[i+1:i+4]
        print("✅ 解码器工厂修改成功")
        break

with open(file_path, 'w') as f:
    f.writelines(lines)

print()
print("=" * 70)
print("✅ VP8切换完成！")
print()
print("📝 修改内容:")
print("   - 编码器: 仅保留 VP8")
print("   - 解码器: 仅保留 VP8")
print()

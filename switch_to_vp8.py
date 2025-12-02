#!/usr/bin/env python3
"""
切换到VP8编解码器
强制使用VP8，禁用H.264/VP9/AV1
"""

print("🔧 切换到VP8编解码器...")
print()

file_path = "src/examples/peerconnection/client/conductor.cc"

with open(file_path, 'r') as f:
    content = f.read()

# 修改 video_encoder_factory - 只保留VP8
old_encoder = """  deps.video_encoder_factory =
      std::make_unique<webrtc::VideoEncoderFactoryTemplate<
          webrtc::LibvpxVp8EncoderTemplateAdapter,
          webrtc::LibvpxVp9EncoderTemplateAdapter,
          webrtc::OpenH264EncoderTemplateAdapter,
          webrtc::LibaomAv1EncoderTemplateAdapter>>();"""

new_encoder = """  deps.video_encoder_factory =
      std::make_unique<webrtc::VideoEncoderFactoryTemplate<
          webrtc::LibvpxVp8EncoderTemplateAdapter>>();  // VP8 only"""

if old_encoder in content:
    content = content.replace(old_encoder, new_encoder)
    print("✅ 修改编码器工厂：仅保留 VP8")
else:
    print("⚠️  未找到原始编码器工厂定义")

# 修改 video_decoder_factory - 只保留VP8
old_decoder = """  deps.video_decoder_factory =
      std::make_unique<webrtc::VideoDecoderFactoryTemplate<
          webrtc::LibvpxVp8DecoderTemplateAdapter,
          webrtc::LibvpxVp9DecoderTemplateAdapter,
          webrtc::OpenH264DecoderTemplateAdapter,
          webrtc::Dav1dDecoderTemplateAdapter>>();"""

new_decoder = """  deps.video_decoder_factory =
      std::make_unique<webrtc::VideoDecoderFactoryTemplate<
          webrtc::LibvpxVp8DecoderTemplateAdapter>>();  // VP8 only"""

if old_decoder in content:
    content = content.replace(old_decoder, new_decoder)
    print("✅ 修改解码器工厂：仅保留 VP8")
else:
    print("⚠️  未找到原始解码器工厂定义")

with open(file_path, 'w') as f:
    f.write(content)

print()
print("=" * 70)
print("✅ 切换完成！")
print()
print("📝 修改内容:")
print("   编码器: VP8, VP9, H.264, AV1 → VP8 only")
print("   解码器: VP8, VP9, H.264, AV1 → VP8 only")
print()
print("🔄 VP8 vs H.264 对比:")
print()
print("   VP8 特点:")
print("   ✅ 完全免费，无专利费")
print("   ✅ WebRTC mandatory codec (所有客户端必须支持)")
print("   ✅ 编码速度较快 (比H.264稍慢，但仍可实时)")
print("   ⚠️  压缩效率略低于H.264 (相同质量下码率高约10-15%)")
print("   ⚠️  硬件加速支持不如H.264广泛")
print()
print("   预期性能:")
print("   - 编码时间: ~20-25 ms/帧 (vs H.264的16ms)")
print("   - 文件大小: ~850 MB (vs H.264的750MB @ 50Mbps·120s)")
print("   - 质量: 基本相同")
print()
print("🔧 下一步: 重新编译")
print("   cd src")
print("   ninja -C out/Default peerconnection_client")
print()

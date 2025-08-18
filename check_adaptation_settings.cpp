#include <iostream>
#include "video/adaptation/overuse_frame_detector.h"
#include "video/adaptation/video_stream_encoder_resource_manager.h"
#include "rtc_base/logging.h"

// 检查当前CPU适配设置
void CheckCpuAdaptationSettings() {
    RTC_LOG(LS_INFO) << "=== CPU适配策略检查 ===";
    
    // 默认CPU过载选项
    webrtc::CpuOveruseOptions default_options;
    RTC_LOG(LS_INFO) << "默认CPU适配阈值:";
    RTC_LOG(LS_INFO) << "  高阈值(过载): " << default_options.high_encode_usage_threshold_percent << "%";
    RTC_LOG(LS_INFO) << "  低阈值(正常): " << default_options.low_encode_usage_threshold_percent << "%";
    RTC_LOG(LS_INFO) << "  帧超时间隔: " << default_options.frame_timeout_interval_ms << "ms";
    RTC_LOG(LS_INFO) << "  最小帧样本: " << default_options.min_frame_samples;
    RTC_LOG(LS_INFO) << "  连续检查次数: " << default_options.high_threshold_consecutive_count;
    
    // 检查是否有硬件加速优化
    bool is_hardware_accelerated = true; // 从编码器信息获取
    if (is_hardware_accelerated) {
        RTC_LOG(LS_WARNING) << "检测到硬件加速编码器 - 阈值会被调整到150%/200%";
        RTC_LOG(LS_WARNING) << "这可能导致CPU适配过于宽松，建议调整";
    }
}

// 优化的CPU适配选项
webrtc::CpuOveruseOptions GetOptimizedCpuOptions(bool is_hardware_accelerated) {
    webrtc::CpuOveruseOptions options;
    
    if (is_hardware_accelerated) {
        // 对硬件编码器使用更严格的阈值
        options.high_encode_usage_threshold_percent = 90;  // 降低到90%
        options.low_encode_usage_threshold_percent = 70;   // 提高到70%
        RTC_LOG(LS_INFO) << "硬件编码器优化: 高阈值=90%, 低阈值=70%";
    } else {
        // 软件编码器使用更宽松的阈值
        options.high_encode_usage_threshold_percent = 75;  // 降低到75%
        options.low_encode_usage_threshold_percent = 50;   // 提高到50%
        RTC_LOG(LS_INFO) << "软件编码器优化: 高阈值=75%, 低阈值=50%";
    }
    
    // 减少检测延迟
    options.min_frame_samples = 60;           // 减少到60帧 (默认120)
    options.high_threshold_consecutive_count = 1;  // 减少到1次 (默认2)
    options.frame_timeout_interval_ms = 1000; // 减少到1s (默认1.5s)
    
    return options;
}

// 检查质量适配设置
void CheckQualityAdaptationSettings() {
    RTC_LOG(LS_INFO) << "=== 质量适配策略检查 ===";
    
    // 检查QP阈值设置
    // 这些值通常在编码器的EncoderInfo中设置
    RTC_LOG(LS_INFO) << "检查项目:";
    RTC_LOG(LS_INFO) << "  1. is_quality_scaling_allowed: 应该为true";
    RTC_LOG(LS_INFO) << "  2. scaling_settings.qp_thresholds: 检查QP阈值";
    RTC_LOG(LS_INFO) << "  3. degradation_preference: 检查降级偏好设置";
    
    // VP8典型QP阈值: low=29, high=95
    // VP9典型QP阈值: low=35, high=205
    // H264典型QP阈值: low=24, high=37
    RTC_LOG(LS_INFO) << "典型QP阈值范围:";
    RTC_LOG(LS_INFO) << "  VP8: low=29, high=95";
    RTC_LOG(LS_INFO) << "  VP9: low=35, high=205";
    RTC_LOG(LS_INFO) << "  H.264: low=24, high=37";
}

// 禁用过度保守的适配策略
void DisableConservativeAdaptation() {
    RTC_LOG(LS_INFO) << "=== 建议的适配策略调整 ===";
    RTC_LOG(LS_INFO) << "1. 在VideoStreamEncoderResourceManager中:";
    RTC_LOG(LS_INFO) << "   - 降低CPU适配阈值";
    RTC_LOG(LS_INFO) << "   - 调整质量适配QP阈值";
    RTC_LOG(LS_INFO) << "   - 禁用过于保守的带宽质量缩放";
    
    RTC_LOG(LS_INFO) << "2. 关键参数调整:";
    RTC_LOG(LS_INFO) << "   CpuOveruseOptions.high_encode_usage_threshold_percent: 85->75";
    RTC_LOG(LS_INFO) << "   CpuOveruseOptions.low_encode_usage_threshold_percent: 42->50";
    RTC_LOG(LS_INFO) << "   降低min_frame_samples以更快响应";
}

int main() {
    // 初始化日志
    rtc::LogMessage::LogToDebug(rtc::LS_INFO);
    
    CheckCpuAdaptationSettings();
    CheckQualityAdaptationSettings();
    DisableConservativeAdaptation();
    
    // 生成优化配置
    auto optimized_options = GetOptimizedCpuOptions(true);
    RTC_LOG(LS_INFO) << "优化后配置已生成";
    
    return 0;
}
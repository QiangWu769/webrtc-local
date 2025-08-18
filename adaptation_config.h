#ifndef ADAPTATION_CONFIG_H_
#define ADAPTATION_CONFIG_H_

#include "video/adaptation/overuse_frame_detector.h"
#include "video/adaptation/video_stream_encoder_resource_manager.h"
#include "api/video/video_stream_encoder_settings.h"

namespace webrtc {

// 适配策略优化配置类
class AdaptationConfig {
public:
    // 获取优化的CPU过载选项
    static CpuOveruseOptions GetOptimizedCpuOptions(bool is_hardware_accelerated) {
        CpuOveruseOptions options;
        
        if (is_hardware_accelerated) {
            // 硬件编码器配置 - 更严格的阈值
            options.high_encode_usage_threshold_percent = 90;  // 默认200 -> 90
            options.low_encode_usage_threshold_percent = 70;   // 默认150 -> 70
        } else {
            // 软件编码器配置 - 适中的阈值  
            options.high_encode_usage_threshold_percent = 75;  // 默认85 -> 75
            options.low_encode_usage_threshold_percent = 50;   // 默认42 -> 50
        }
        
        // 加速适配响应
        options.min_frame_samples = 60;                    // 默认120 -> 60
        options.high_threshold_consecutive_count = 1;      // 默认2 -> 1
        options.frame_timeout_interval_ms = 1000;         // 默认1500 -> 1000
        options.min_process_count = 2;                     // 默认3 -> 2
        
        // 启用新的CPU负载估计器
        options.filter_time_ms = 3000;  // 3秒滤波时间
        
        return options;
    }
    
    // 质量缩放配置
    struct QualityScalingConfig {
        bool enabled = true;
        // VP8 QP阈值优化
        struct {
            int low_qp = 25;   // 默认29 -> 25 (更早触发上调)
            int high_qp = 90;  // 默认95 -> 90 (更早触发下调)
        } vp8;
        
        // VP9 QP阈值优化  
        struct {
            int low_qp = 30;   // 默认35 -> 30
            int high_qp = 180; // 默认205 -> 180
        } vp9;
        
        // H.264 QP阈值优化
        struct {
            int low_qp = 20;   // 默认24 -> 20
            int high_qp = 35;  // 默认37 -> 35
        } h264;
    };
    
    // 获取质量缩放配置
    static QualityScalingConfig GetQualityScalingConfig() {
        return QualityScalingConfig{};
    }
    
    // 带宽质量缩放配置 - 更激进的策略
    struct BandwidthQualityConfig {
        bool enabled = true;
        // 降低触发阈值，更容易在带宽充足时提升质量
        double resolution_bitrate_factor = 0.8;  // 默认1.0 -> 0.8
        double framerate_bitrate_factor = 0.7;   // 默认1.0 -> 0.7
    };
    
    // 适配优先级配置
    enum class AdaptationPriority {
        PREFER_RESOLUTION,    // 优先保持分辨率
        PREFER_FRAMERATE,     // 优先保持帧率  
        BALANCED             // 平衡策略
    };
    
    // 根据内容类型获取适配优先级
    static AdaptationPriority GetAdaptationPriority(
        VideoEncoderConfig::ContentType content_type) {
        switch (content_type) {
            case VideoEncoderConfig::ContentType::kRealtimeVideo:
                return AdaptationPriority::PREFER_FRAMERATE;  // 实时视频优先帧率
            case VideoEncoderConfig::ContentType::kScreen:
                return AdaptationPriority::PREFER_RESOLUTION; // 屏幕共享优先分辨率
            default:
                return AdaptationPriority::BALANCED;
        }
    }
    
    // 禁用过度保守的适配功能
    struct ConservativeAdaptationDisable {
        bool disable_initial_frame_drop = true;           // 禁用初始帧丢弃
        bool disable_bandwidth_limited_resolution = true; // 禁用带宽限制分辨率
        bool reduce_adaptation_hysteresis = true;         // 减少适配滞后
        bool aggressive_quality_scaling = true;           // 激进质量缩放
    };
    
    // 应用配置到ResourceManager
    static void ApplyConfig(VideoStreamEncoderResourceManager* resource_manager,
                           bool is_hardware_accelerated,
                           VideoEncoderConfig::ContentType content_type) {
        
        // 注意：以下是伪代码，实际实现需要访问ResourceManager的私有成员
        // 实际使用时需要修改ResourceManager或通过适当的API设置
        
        /*
        // 1. 设置CPU适配选项
        auto cpu_options = GetOptimizedCpuOptions(is_hardware_accelerated);
        resource_manager->SetCpuOveruseOptions(cpu_options);
        
        // 2. 配置质量缩放
        auto quality_config = GetQualityScalingConfig();
        resource_manager->SetQualityScalingConfig(quality_config);
        
        // 3. 设置适配优先级
        auto priority = GetAdaptationPriority(content_type);
        resource_manager->SetAdaptationPriority(priority);
        
        // 4. 禁用保守适配
        ConservativeAdaptationDisable disable_config;
        resource_manager->ApplyConservativeDisableConfig(disable_config);
        */
    }
    
    // 运行时动态调整配置
    static void DynamicAdjustment(VideoStreamEncoderResourceManager* resource_manager,
                                 double current_utilization,
                                 int recent_adaptation_count) {
        
        // 如果利用率持续过低且适配不频繁，放宽适配阈值
        if (current_utilization < 60.0 && recent_adaptation_count < 3) {
            // 动态调整CPU阈值，允许更高的CPU使用率
            CpuOveruseOptions relaxed_options;
            relaxed_options.high_encode_usage_threshold_percent = 90;
            relaxed_options.low_encode_usage_threshold_percent = 60;
            
            // resource_manager->UpdateCpuOptions(relaxed_options);
        }
        
        // 如果适配过于频繁，增加稳定性
        if (recent_adaptation_count > 10) {
            CpuOveruseOptions stable_options;
            stable_options.min_frame_samples = 180;  // 增加采样数
            stable_options.high_threshold_consecutive_count = 3;  // 增加确认次数
            
            // resource_manager->UpdateCpuOptions(stable_options);
        }
    }
    
    // 输出当前配置信息
    static void LogCurrentConfig(bool is_hardware_accelerated,
                               VideoEncoderConfig::ContentType content_type) {
        auto cpu_options = GetOptimizedCpuOptions(is_hardware_accelerated);
        auto quality_config = GetQualityScalingConfig();
        auto priority = GetAdaptationPriority(content_type);
        
        RTC_LOG(LS_INFO) << "=== 适配策略配置 ===";
        RTC_LOG(LS_INFO) << "编码器类型: " << 
            (is_hardware_accelerated ? "硬件加速" : "软件编码");
        RTC_LOG(LS_INFO) << "内容类型: " << 
            (content_type == VideoEncoderConfig::ContentType::kScreen ? "屏幕共享" : "实时视频");
            
        RTC_LOG(LS_INFO) << "CPU适配阈值: " << cpu_options.low_encode_usage_threshold_percent 
                        << "% ~ " << cpu_options.high_encode_usage_threshold_percent << "%";
        RTC_LOG(LS_INFO) << "最小帧样本: " << cpu_options.min_frame_samples;
        RTC_LOG(LS_INFO) << "连续检查次数: " << cpu_options.high_threshold_consecutive_count;
        
        std::string priority_str;
        switch (priority) {
            case AdaptationPriority::PREFER_RESOLUTION: priority_str = "优先分辨率"; break;
            case AdaptationPriority::PREFER_FRAMERATE: priority_str = "优先帧率"; break;
            case AdaptationPriority::BALANCED: priority_str = "平衡策略"; break;
        }
        RTC_LOG(LS_INFO) << "适配优先级: " << priority_str;
        
        RTC_LOG(LS_INFO) << "质量缩放: " << (quality_config.enabled ? "启用" : "禁用");
    }
};

// 便捷宏定义，用于快速应用配置
#define APPLY_OPTIMIZED_ADAPTATION_CONFIG(resource_manager, is_hw, content_type) \
    AdaptationConfig::ApplyConfig(resource_manager, is_hw, content_type); \
    AdaptationConfig::LogCurrentConfig(is_hw, content_type);

// 监控适配效果的辅助类
class AdaptationEffectivenessMonitor {
public:
    void RecordBitrateUtilization(double utilization) {
        utilization_history_.push_back({rtc::TimeMillis(), utilization});
        
        // 保持最近5分钟的数据
        while (!utilization_history_.empty() && 
               rtc::TimeMillis() - utilization_history_.front().timestamp > 300000) {
            utilization_history_.pop_front();
        }
        
        // 检查持续低利用率
        if (utilization < 50.0) {
            consecutive_low_utilization_++;
            if (consecutive_low_utilization_ > 30) { // 30次采样
                RTC_LOG(LS_WARNING) << "持续低码率利用率，建议调整适配策略";
            }
        } else {
            consecutive_low_utilization_ = 0;
        }
    }
    
    double GetAverageUtilization() const {
        if (utilization_history_.empty()) return 0.0;
        
        double sum = 0.0;
        for (const auto& entry : utilization_history_) {
            sum += entry.utilization;
        }
        return sum / utilization_history_.size();
    }
    
private:
    struct UtilizationEntry {
        int64_t timestamp;
        double utilization;
    };
    
    std::deque<UtilizationEntry> utilization_history_;
    int consecutive_low_utilization_ = 0;
};

} // namespace webrtc

#endif // ADAPTATION_CONFIG_H_
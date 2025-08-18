#include <iostream>
#include <memory>
#include <map>
#include "video/send_statistics_proxy.h"
#include "video/video_stream_encoder.h"
#include "video/adaptation/video_stream_encoder_resource_manager.h"
#include "rtc_base/logging.h"
#include "rtc_base/time_utils.h"
#include "api/video/video_stream_encoder_observer.h"

// 增强的发送端监控类
class EnhancedSenderMonitor : public webrtc::VideoStreamEncoderObserver {
public:
    EnhancedSenderMonitor() : 
        start_time_ms_(rtc::TimeMillis()),
        total_target_bitrate_(0),
        total_actual_bitrate_(0),
        adaptation_down_count_(0),
        adaptation_up_count_(0) {}

    // 实现VideoStreamEncoderObserver接口
    void OnIncomingFrame(int width, int height) override {
        input_resolution_ = {width, height};
        LogFrameInfo("输入帧", width, height);
    }

    void OnSendEncodedImage(const webrtc::EncodedImage& encoded_image,
                           const webrtc::CodecSpecificInfo* codec_info) override {
        // 监控编码输出
        encoded_frame_count_++;
        total_encoded_bytes_ += encoded_image.size();
        
        // 计算实际编码码率
        int64_t now_ms = rtc::TimeMillis();
        if (last_stats_time_ms_ == 0) {
            last_stats_time_ms_ = now_ms;
        }
        
        if (now_ms - last_stats_time_ms_ >= 1000) { // 每秒统计一次
            double duration_s = (now_ms - last_stats_time_ms_) / 1000.0;
            current_encode_bitrate_ = (total_encoded_bytes_ * 8) / duration_s;
            
            LogEncodingStats(encoded_image, codec_info);
            
            // 重置计数器
            total_encoded_bytes_ = 0;
            last_stats_time_ms_ = now_ms;
        }
    }

    void OnEncoderImplementationChanged(
        webrtc::EncoderImplementation implementation) override {
        RTC_LOG(LS_INFO) << "编码器实现变更: " 
                        << (implementation == webrtc::EncoderImplementation::kHardware ? 
                            "硬件加速" : "软件编码");
        encoder_implementation_ = implementation;
    }

    void OnFrameDropped(DropReason reason) override {
        dropped_frame_count_++;
        dropped_frame_reasons_[reason]++;
        
        std::string reason_str = GetDropReasonString(reason);
        RTC_LOG(LS_WARNING) << "帧丢弃 [" << reason_str << "] 总计: " << dropped_frame_count_;
        
        // 如果丢帧过多，输出警告
        if (dropped_frame_count_ % 10 == 0) {
            LogDroppedFrameStats();
        }
    }

    void OnAdaptationChanged(webrtc::VideoAdaptationReason reason,
                           const webrtc::VideoAdaptationCounters& cpu_steps,
                           const webrtc::VideoAdaptationCounters& quality_steps) override {
        
        adaptation_history_.push_back({rtc::TimeMillis(), reason, cpu_steps, quality_steps});
        
        std::string reason_str = GetAdaptationReasonString(reason);
        RTC_LOG(LS_WARNING) << "适配变更 [" << reason_str << "]";
        RTC_LOG(LS_WARNING) << "  CPU适配: 分辨率=" << cpu_steps.resolution_adaptations 
                           << ", 帧率=" << cpu_steps.framerate_adaptations;
        RTC_LOG(LS_WARNING) << "  质量适配: 分辨率=" << quality_steps.resolution_adaptations 
                           << ", 帧率=" << quality_steps.framerate_adaptations;
        
        // 检查是否适配过于频繁
        CheckAdaptationFrequency();
    }

    // 监控码率分配情况
    void OnBitrateAllocationUpdate(const webrtc::VideoBitrateAllocation& allocation,
                                 uint32_t target_bitrate_bps) {
        target_bitrate_bps_ = target_bitrate_bps;
        bitrate_allocation_ = allocation;
        
        uint32_t allocated_bitrate = allocation.get_sum_bps();
        double utilization = allocated_bitrate > 0 ? 
            (double)current_encode_bitrate_ / allocated_bitrate * 100.0 : 0.0;
        
        RTC_LOG(LS_INFO) << "码率分配更新:";
        RTC_LOG(LS_INFO) << "  目标码率: " << target_bitrate_bps / 1000 << " kbps";
        RTC_LOG(LS_INFO) << "  分配码率: " << allocated_bitrate / 1000 << " kbps";
        RTC_LOG(LS_INFO) << "  实际编码: " << current_encode_bitrate_ / 1000 << " kbps";
        RTC_LOG(LS_INFO) << "  利用率: " << std::fixed << std::setprecision(1) << utilization << "%";
        
        // 检查利用率异常
        if (utilization < 60.0 && allocated_bitrate > 1000000) { // 1Mbps以上且利用率低于60%
            RTC_LOG(LS_ERROR) << "❌ 码率利用率过低! 可能存在发送端瓶颈";
            DiagnoseSenderBottleneck();
        }
    }

    // 监控CPU和编码性能
    void OnEncodedFrameTimeMeasured(int encode_time_ms,
                                  const webrtc::CpuOveruseMetrics& metrics) override {
        total_encode_time_ms_ += encode_time_ms;
        encode_time_samples_++;
        
        if (encode_time_samples_ % 30 == 0) { // 每30帧输出一次
            double avg_encode_time = (double)total_encode_time_ms_ / encode_time_samples_;
            RTC_LOG(LS_INFO) << "编码性能统计:";
            RTC_LOG(LS_INFO) << "  平均编码时间: " << avg_encode_time << " ms";
            RTC_LOG(LS_INFO) << "  CPU使用率: " << metrics.encode_usage_percent << "%";
            
            // 检查编码性能问题
            if (avg_encode_time > 33.0) { // 超过33ms (30fps)
                RTC_LOG(LS_WARNING) << "⚠️ 编码时间过长，可能影响实时性";
            }
            if (metrics.encode_usage_percent > 80) {
                RTC_LOG(LS_WARNING) << "⚠️ CPU使用率过高，可能触发适配";
            }
        }
    }

    // 生成综合诊断报告
    void GenerateDiagnosticReport() {
        int64_t now_ms = rtc::TimeMillis();
        double duration_s = (now_ms - start_time_ms_) / 1000.0;
        
        RTC_LOG(LS_INFO) << "\n=== 发送端综合诊断报告 ===";
        RTC_LOG(LS_INFO) << "运行时间: " << duration_s << " 秒";
        
        // 帧处理统计
        RTC_LOG(LS_INFO) << "\n📊 帧处理统计:";
        RTC_LOG(LS_INFO) << "  编码帧数: " << encoded_frame_count_;
        RTC_LOG(LS_INFO) << "  丢弃帧数: " << dropped_frame_count_;
        if (encoded_frame_count_ > 0) {
            double drop_rate = (double)dropped_frame_count_ / 
                              (encoded_frame_count_ + dropped_frame_count_) * 100.0;
            RTC_LOG(LS_INFO) << "  丢帧率: " << std::fixed << std::setprecision(1) << drop_rate << "%";
        }

        // 码率统计
        RTC_LOG(LS_INFO) << "\n📈 码率统计:";
        RTC_LOG(LS_INFO) << "  当前目标: " << target_bitrate_bps_ / 1000 << " kbps";
        RTC_LOG(LS_INFO) << "  当前实际: " << current_encode_bitrate_ / 1000 << " kbps";
        if (target_bitrate_bps_ > 0) {
            double efficiency = (double)current_encode_bitrate_ / target_bitrate_bps_ * 100.0;
            RTC_LOG(LS_INFO) << "  码率效率: " << std::fixed << std::setprecision(1) << efficiency << "%";
        }

        // 适配统计
        RTC_LOG(LS_INFO) << "\n🔄 适配统计:";
        LogAdaptationSummary();

        // 编码器信息
        RTC_LOG(LS_INFO) << "\n🔧 编码器信息:";
        RTC_LOG(LS_INFO) << "  实现方式: " << 
            (encoder_implementation_ == webrtc::EncoderImplementation::kHardware ? 
             "硬件加速" : "软件编码");
        if (input_resolution_.width > 0) {
            RTC_LOG(LS_INFO) << "  输入分辨率: " << input_resolution_.width 
                           << "x" << input_resolution_.height;
        }

        // 性能建议
        GeneratePerformanceRecommendations();
    }

private:
    struct Resolution {
        int width = 0;
        int height = 0;
    };

    struct AdaptationEvent {
        int64_t timestamp_ms;
        webrtc::VideoAdaptationReason reason;
        webrtc::VideoAdaptationCounters cpu_steps;
        webrtc::VideoAdaptationCounters quality_steps;
    };

    // 成员变量
    int64_t start_time_ms_;
    int64_t last_stats_time_ms_ = 0;
    uint32_t encoded_frame_count_ = 0;
    uint32_t dropped_frame_count_ = 0;
    uint64_t total_encoded_bytes_ = 0;
    uint64_t total_encode_time_ms_ = 0;
    uint32_t encode_time_samples_ = 0;
    
    uint32_t target_bitrate_bps_ = 0;
    uint32_t current_encode_bitrate_ = 0;
    uint32_t total_target_bitrate_;
    uint32_t total_actual_bitrate_;
    
    int adaptation_down_count_;
    int adaptation_up_count_;
    
    Resolution input_resolution_;
    webrtc::EncoderImplementation encoder_implementation_ = 
        webrtc::EncoderImplementation::kSoftware;
    webrtc::VideoBitrateAllocation bitrate_allocation_;
    
    std::map<DropReason, int> dropped_frame_reasons_;
    std::vector<AdaptationEvent> adaptation_history_;

    // 辅助方法
    void LogFrameInfo(const std::string& type, int width, int height) {
        static int64_t last_log_time = 0;
        int64_t now = rtc::TimeMillis();
        if (now - last_log_time > 5000) { // 每5秒记录一次
            RTC_LOG(LS_INFO) << type << " 分辨率: " << width << "x" << height;
            last_log_time = now;
        }
    }

    void LogEncodingStats(const webrtc::EncodedImage& image,
                         const webrtc::CodecSpecificInfo* codec_info) {
        RTC_LOG(LS_INFO) << "编码统计: " 
                        << "码率=" << current_encode_bitrate_ / 1000 << "kbps, "
                        << "帧大小=" << image.size() << "bytes, "
                        << "分辨率=" << image._encodedWidth << "x" << image._encodedHeight;
    }

    void LogDroppedFrameStats() {
        RTC_LOG(LS_WARNING) << "丢帧统计详情:";
        for (auto& [reason, count] : dropped_frame_reasons_) {
            RTC_LOG(LS_WARNING) << "  " << GetDropReasonString(reason) << ": " << count;
        }
    }

    void CheckAdaptationFrequency() {
        int64_t now_ms = rtc::TimeMillis();
        // 检查最近1分钟内的适配次数
        int recent_adaptations = 0;
        for (auto it = adaptation_history_.rbegin(); 
             it != adaptation_history_.rend() && 
             (now_ms - it->timestamp_ms) < 60000; ++it) {
            recent_adaptations++;
        }
        
        if (recent_adaptations > 10) {
            RTC_LOG(LS_ERROR) << "❌ 适配过于频繁! 最近1分钟内发生了" << recent_adaptations << "次适配";
            RTC_LOG(LS_ERROR) << "建议检查网络条件或调整适配阈值";
        }
    }

    void DiagnoseSenderBottleneck() {
        RTC_LOG(LS_ERROR) << "\n🔍 发送端瓶颈诊断:";
        
        // 检查可能的瓶颈原因
        if (encoder_implementation_ == webrtc::EncoderImplementation::kSoftware) {
            RTC_LOG(LS_ERROR) << "  • 使用软件编码，可能受CPU性能限制";
        }
        
        if (dropped_frame_count_ > 0) {
            RTC_LOG(LS_ERROR) << "  • 检测到丢帧，可能存在处理瓶颈";
        }
        
        if (adaptation_history_.size() > 5) {
            RTC_LOG(LS_ERROR) << "  • 频繁的适配可能影响码率利用";
        }
        
        RTC_LOG(LS_ERROR) << "  • 建议检查: 编码器配置、CPU负载、内存使用、适配策略";
    }

    void LogAdaptationSummary() {
        int cpu_res_adaptations = 0, cpu_fps_adaptations = 0;
        int quality_res_adaptations = 0, quality_fps_adaptations = 0;
        
        for (const auto& event : adaptation_history_) {
            cpu_res_adaptations = std::max(cpu_res_adaptations, 
                                         event.cpu_steps.resolution_adaptations);
            cpu_fps_adaptations = std::max(cpu_fps_adaptations,
                                         event.cpu_steps.framerate_adaptations);
            quality_res_adaptations = std::max(quality_res_adaptations,
                                             event.quality_steps.resolution_adaptations);
            quality_fps_adaptations = std::max(quality_fps_adaptations,
                                             event.quality_steps.framerate_adaptations);
        }
        
        RTC_LOG(LS_INFO) << "  CPU适配次数: 分辨率=" << cpu_res_adaptations 
                        << ", 帧率=" << cpu_fps_adaptations;
        RTC_LOG(LS_INFO) << "  质量适配次数: 分辨率=" << quality_res_adaptations 
                        << ", 帧率=" << quality_fps_adaptations;
        RTC_LOG(LS_INFO) << "  总适配事件: " << adaptation_history_.size();
    }

    void GeneratePerformanceRecommendations() {
        RTC_LOG(LS_INFO) << "\n💡 性能优化建议:";
        
        if (current_encode_bitrate_ < target_bitrate_bps_ * 0.6) {
            RTC_LOG(LS_INFO) << "  1. 码率利用率过低，检查编码器配置和适配策略";
        }
        
        if (dropped_frame_count_ > encoded_frame_count_ * 0.05) {
            RTC_LOG(LS_INFO) << "  2. 丢帧率较高，考虑优化处理流程或降低输入帧率";
        }
        
        if (adaptation_history_.size() > 20) {
            RTC_LOG(LS_INFO) << "  3. 适配过于频繁，考虑调整适配阈值或稳定网络环境";
        }
        
        if (encoder_implementation_ == webrtc::EncoderImplementation::kSoftware) {
            RTC_LOG(LS_INFO) << "  4. 考虑启用硬件编码以提高性能";
        }
    }

    std::string GetDropReasonString(DropReason reason) {
        switch (reason) {
            case DropReason::kSource: return "输入源";
            case DropReason::kBadTimestamp: return "时间戳错误";
            case DropReason::kEncoderQueue: return "编码器队列";
            case DropReason::kEncoder: return "编码器";
            case DropReason::kMediaOptimization: return "媒体优化";
            case DropReason::kCongestionWindow: return "拥塞窗口";
            default: return "未知";
        }
    }

    std::string GetAdaptationReasonString(webrtc::VideoAdaptationReason reason) {
        switch (reason) {
            case webrtc::VideoAdaptationReason::kCpu: return "CPU负载";
            case webrtc::VideoAdaptationReason::kQuality: return "质量控制";
            default: return "未知";
        }
    }
};

// 使用示例
int main() {
    // 初始化日志
    rtc::LogMessage::LogToDebug(rtc::LS_INFO);
    
    auto monitor = std::make_unique<EnhancedSenderMonitor>();
    
    RTC_LOG(LS_INFO) << "增强发送端监控已启动";
    RTC_LOG(LS_INFO) << "将在VideoStreamEncoder中注册此observer";
    
    // 在实际使用中，需要将monitor注册到VideoStreamEncoder:
    // video_stream_encoder->AddEncoderObserver(monitor.get());
    
    return 0;
}
// test_ratio_sender.cc
// 独立的测试程序，用于发送模拟的BSR ratio数据到WebRTC
// 编译: g++ -o test_ratio_sender test_ratio_sender.cc
// 运行: ./test_ratio_sender

#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <cstring>
#include <cstdio>
#include <cstdint>
#include <cmath>
#include <chrono>
#include <errno.h>

// 数据包格式定义（必须与接收端一致）
struct CellularRatioPacket {
    uint64_t timestamp_ms;    // 8字节：时间戳（毫秒）
    double ratio;             // 8字节：资源比率
    uint32_t sequence_number; // 4字节：序列号
} __attribute__((packed));    // 总共20字节

// 不同的测试模式
enum TestPattern {
    PATTERN_SINE,       // 正弦波
    PATTERN_STEP,       // 阶梯
    PATTERN_CONGESTION, // 模拟拥塞
    PATTERN_RANDOM      // 随机
};

// 根据模式生成ratio值
double generate_ratio(TestPattern pattern, uint32_t sequence) {
    switch (pattern) {
        case PATTERN_SINE:
            // 正弦波：0.3 到 1.0 之间平滑变化
            return 0.65 + 0.35 * sin(sequence * 0.1);
            
        case PATTERN_STEP:
            // 阶梯：每20个包切换一次
            {
                int phase = (sequence / 20) % 4;
                double values[] = {1.0, 0.8, 0.5, 0.3};
                return values[phase];
            }
            
        case PATTERN_CONGESTION:
            // 模拟逐渐拥塞然后恢复
            {
                int cycle = sequence % 100;
                if (cycle < 30) {
                    return 1.0;  // 正常
                } else if (cycle < 60) {
                    // 逐渐下降
                    return 1.0 - (cycle - 30) * 0.02;
                } else if (cycle < 80) {
                    return 0.3;  // 拥塞
                } else {
                    // 恢复
                    return 0.3 + (cycle - 80) * 0.035;
                }
            }
            
        case PATTERN_RANDOM:
        default:
            // 随机波动
            return 0.5 + 0.3 * sin(sequence * 0.1) + 0.2 * sin(sequence * 0.3);
    }
}

int main(int argc, char* argv[]) {
    printf("===========================================\n");
    printf("    WebRTC Cellular Ratio Test Sender     \n");
    printf("===========================================\n\n");
    
    // 解析命令行参数
    TestPattern pattern = PATTERN_CONGESTION;
    int duration_seconds = 10;
    int interval_ms = 100;
    
    if (argc > 1) {
        if (strcmp(argv[1], "sine") == 0) pattern = PATTERN_SINE;
        else if (strcmp(argv[1], "step") == 0) pattern = PATTERN_STEP;
        else if (strcmp(argv[1], "random") == 0) pattern = PATTERN_RANDOM;
    }
    
    if (argc > 2) {
        duration_seconds = atoi(argv[2]);
    }
    
    // 1. 创建Unix域数据报socket
    int sock = socket(AF_UNIX, SOCK_DGRAM, 0);
    if (sock < 0) {
        perror("Failed to create socket");
        return 1;
    }
    
    // 2. 设置目标地址
    struct sockaddr_un dest_addr;
    memset(&dest_addr, 0, sizeof(dest_addr));
    dest_addr.sun_family = AF_UNIX;
    const char* socket_path = "/tmp/webrtc_cellular_ratio.sock";
    strncpy(dest_addr.sun_path, socket_path, sizeof(dest_addr.sun_path) - 1);
    
    printf("Configuration:\n");
    printf("  Target socket: %s\n", socket_path);
    printf("  Pattern: %s\n", 
           pattern == PATTERN_SINE ? "sine" :
           pattern == PATTERN_STEP ? "step" :
           pattern == PATTERN_CONGESTION ? "congestion" : "random");
    printf("  Duration: %d seconds\n", duration_seconds);
    printf("  Interval: %d ms\n", interval_ms);
    printf("\nStarting transmission...\n");
    printf("(Press Ctrl+C to stop)\n\n");
    
    // 3. 发送循环
    uint32_t sequence = 0;
    int total_packets = (duration_seconds * 1000) / interval_ms;
    int sent_count = 0;
    int error_count = 0;
    
    auto start_time = std::chrono::steady_clock::now();
    
    while (sequence < total_packets) {
        // 构造数据包
        CellularRatioPacket packet;
        
        // 获取当前时间戳（毫秒）
        auto now = std::chrono::system_clock::now();
        auto ms_since_epoch = std::chrono::duration_cast<std::chrono::milliseconds>(
            now.time_since_epoch()).count();
        packet.timestamp_ms = ms_since_epoch;
        
        // 生成ratio值
        packet.ratio = generate_ratio(pattern, sequence);
        packet.sequence_number = sequence;
        
        // 发送数据包
        ssize_t sent = sendto(sock, &packet, sizeof(packet), 0,
                            (struct sockaddr*)&dest_addr, sizeof(dest_addr));
        
        if (sent < 0) {
            // 如果接收方还没准备好，会返回错误，这是正常的
            if (errno == ENOENT || errno == ECONNREFUSED) {
                if (error_count == 0) {
                    printf("⚠️  Receiver not ready (socket not found)\n");
                }
                error_count++;
            } else {
                perror("sendto error");
            }
        } else if (sent == sizeof(packet)) {
            sent_count++;
            
            // 如果之前有错误，现在恢复了
            if (error_count > 0 && sent_count == 1) {
                printf("✅ Receiver connected!\n\n");
                error_count = 0;
            }
            
            // 每秒打印一次状态
            if (sequence % (1000 / interval_ms) == 0) {
                auto elapsed = std::chrono::steady_clock::now() - start_time;
                int elapsed_sec = std::chrono::duration_cast<std::chrono::seconds>(elapsed).count();
                
                const char* status = packet.ratio > 0.8 ? "📈 Good  " :
                                    packet.ratio > 0.5 ? "📊 Medium" :
                                                        "📉 Poor  ";
                
                printf("[%3ds] Seq: %5u | Ratio: %.3f | Status: %s | Sent: %d pkts\n",
                       elapsed_sec, sequence, packet.ratio, status, sent_count);
            }
        }
        
        sequence++;
        usleep(interval_ms * 1000);  // 转换为微秒
    }
    
    // 4. 打印统计
    printf("\n===========================================\n");
    printf("Transmission Complete!\n");
    printf("  Total packets: %u\n", sequence);
    printf("  Successfully sent: %d\n", sent_count);
    printf("  Errors: %d\n", error_count);
    
    if (sent_count == 0) {
        printf("\n⚠️  No packets were received!\n");
        printf("Make sure the WebRTC receiver is running.\n");
    } else {
        printf("\n✅ Success rate: %.1f%%\n", 
               (100.0 * sent_count) / sequence);
    }
    printf("===========================================\n");
    
    // 5. 清理
    close(sock);
    return 0;
}
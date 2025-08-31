#include <stdio.h>
#include <stdlib.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>
#include <sys/time.h>
#include <errno.h>
#include <string.h>

#define TIME_SERVER_PORT 43555

void error(const char* msg) {
    perror(msg);
    exit(1);
}

int main(void) {
    setvbuf(stdout, NULL, _IONBF, 0);
    
    // 创建TCP服务器
    int server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd < 0) error("socket");
    
    struct sockaddr_in server_info = {
        .sin_family = AF_INET,
        .sin_port = htons(TIME_SERVER_PORT),
        .sin_addr = {
            .s_addr = htonl(INADDR_ANY)  // 绑定到0.0.0.0
        }
    };
    
    // 设置端口重用
    const int DO_REUSE_ADDR = 1;
    if (setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &DO_REUSE_ADDR, sizeof(DO_REUSE_ADDR)) < 0) {
        error("setsockopt");
    }
    
    // 绑定和监听
    if (bind(server_fd, (struct sockaddr*)&server_info, sizeof(server_info)) < 0) {
        error("bind");
    }
    
    if (listen(server_fd, 5) < 0) {
        error("listen");
    }
    
    printf("[+] Time server listening on 0.0.0.0:%d\n", TIME_SERVER_PORT);
    
    // 主循环：接受客户端连接
    while(1) {
        struct sockaddr_in client_info = {0};
        socklen_t client_info_size = sizeof(client_info);
        
        printf("[+] Waiting for client connection...\n");
        int client_fd = accept(server_fd, (struct sockaddr*)&client_info, &client_info_size);
        if (client_fd < 0) {
            perror("accept");
            continue;
        }
        
        printf("[+] Client connected.\n");
        
        // 内部发送循环：定期发送时间戳
        while(1) {
            struct timeval tv;
            gettimeofday(&tv, NULL);
            double timestamp = (double)tv.tv_sec + (double)tv.tv_usec / 1.0e6;
            
            // 发送8字节的double时间戳
            ssize_t sent = write(client_fd, &timestamp, sizeof(double));
            if (sent != sizeof(double)) {
                if (sent < 0) {
                    printf("[-] Write error: %s\n", strerror(errno));
                } else {
                    printf("[-] Partial write: only %zd bytes sent\n", sent);
                }
                break; // 客户端断开连接
            }
            
            printf("[TIME] Sent timestamp: %.6f\n", timestamp);
            
            // 休眠100毫秒
            usleep(100000);
        }
        
        printf("[-] Client disconnected.\n");
        close(client_fd);
    }
    
    close(server_fd);
    return 0;
}
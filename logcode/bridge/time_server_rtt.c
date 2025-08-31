#include <stdio.h>
#include <stdlib.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>
#include <sys/time.h>
#include <errno.h>
#include <string.h>
#include <stdint.h>

#define TIME_SERVER_PORT 43556  // Different port to avoid conflict

// Message types
#define MSG_TYPE_PING 0x01
#define MSG_TYPE_PONG 0x02

// Message structure for RTT measurement
// Use packed attribute to avoid padding
typedef struct __attribute__((packed)) {
    uint8_t msg_type;     // Message type (PING or PONG)
    double t1;            // Client send time (from PING)
    double t2;            // Server receive time
    double t3;            // Server send time
} rtt_message_t;

void error(const char* msg) {
    perror(msg);
    exit(1);
}

double get_current_time() {
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return (double)tv.tv_sec + (double)tv.tv_usec / 1.0e6;
}

int main(void) {
    setvbuf(stdout, NULL, _IONBF, 0);
    
    // Create TCP server
    int server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd < 0) error("socket");
    
    struct sockaddr_in server_info = {
        .sin_family = AF_INET,
        .sin_port = htons(TIME_SERVER_PORT),
        .sin_addr = {
            .s_addr = htonl(INADDR_ANY)
        }
    };
    
    // Set port reuse
    const int DO_REUSE_ADDR = 1;
    if (setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &DO_REUSE_ADDR, sizeof(DO_REUSE_ADDR)) < 0) {
        error("setsockopt");
    }
    
    // Bind and listen
    if (bind(server_fd, (struct sockaddr*)&server_info, sizeof(server_info)) < 0) {
        error("bind");
    }
    
    if (listen(server_fd, 5) < 0) {
        error("listen");
    }
    
    printf("[+] RTT Time server listening on 0.0.0.0:%d\n", TIME_SERVER_PORT);
    
    // Main loop: accept client connections
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
        
        printf("[+] Message size: %zu bytes\n", sizeof(rtt_message_t));
        
        // Handle PING-PONG messages for RTT measurement
        while(1) {
            rtt_message_t request;
            
            // Receive PING message from client
            ssize_t received = read(client_fd, &request, sizeof(request));
            if (received != sizeof(request)) {
                if (received <= 0) {
                    printf("[-] Client disconnected.\n");
                } else {
                    printf("[-] Partial read: only %zd bytes received (expected %zu)\n", 
                           received, sizeof(request));
                }
                break;
            }
            
            printf("[DEBUG] Received PING: type=0x%02x, T1=%.6f\n", request.msg_type, request.t1);
            
            // Check if it's a PING message
            if (request.msg_type != MSG_TYPE_PING) {
                printf("[-] Invalid message type: 0x%02x\n", request.msg_type);
                continue;
            }
            
            // Record server receive time (T2)
            double t2 = get_current_time();
            
            // Prepare PONG response
            rtt_message_t response;
            response.msg_type = MSG_TYPE_PONG;
            response.t1 = request.t1;  // Echo back client's send time
            response.t2 = t2;           // Server receive time
            response.t3 = get_current_time(); // Server send time (T3)
            
            // Send PONG response
            ssize_t sent = write(client_fd, &response, sizeof(response));
            if (sent != sizeof(response)) {
                if (sent < 0) {
                    printf("[-] Write error: %s\n", strerror(errno));
                } else {
                    printf("[-] Partial write: only %zd bytes sent (expected %zu)\n", 
                           sent, sizeof(response));
                }
                break;
            }
            
            // Calculate server processing time
            double processing_time = (response.t3 - t2) * 1000;
            printf("[PONG] Sent response: T1=%.6f, T2=%.6f, T3=%.6f, Processing: %.3f ms\n", 
                   response.t1, response.t2, response.t3, processing_time);
        }
        
        close(client_fd);
    }
    
    close(server_fd);
    return 0;
}
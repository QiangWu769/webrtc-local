#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/socket.h>
#include <poll.h>
#include <string.h>
// #include <pthread.h> removed - single-threaded approach
#include <errno.h>
#include <sys/un.h>
#include <netinet/in.h>
#include <sys/ioctl.h>
#include <sys/system_properties.h>

#define QCSUPER_TCP_PORT 43555
#define BUFFER_LEN 1024 * 16  // 16KB buffer for higher frequency reads 
#define FDS_LEN 4096
#define USER_SPACE_DATA_TYPE 0x00000020
#define MEMORY_DEVICE_MODE 2
#define DIAG_IOCTL_SWITCH_LOGGING 7
#define DIAG_IOCTL_QUERY_CON_ALL 41
#define DIAG_IOCTL_REMOTE_DEV 32
#define DIAG_MD_LOCAL 0

// 外掩码定义
#define DIAG_CON_APSS    (0x0001)    /* Bit mask for APSS */
#define DIAG_CON_MPSS    (0x0002)    /* Bit mask for MPSS */
#define DIAG_CON_LPASS   (0x0004)    /* Bit mask for LPASS */
#define DIAG_CON_WCNSS   (0x0008)    /* Bit mask for WCNSS */
#define DIAG_CON_SENSORS (0x0010)    /* Bit mask for Sensors */
#define DIAG_CON_NONE    (0x0000)    /* Bit mask for No SS*/
#define DIAG_CON_ALL     (DIAG_CON_APSS | DIAG_CON_MPSS \
                         | DIAG_CON_LPASS | DIAG_CON_WCNSS \
                         | DIAG_CON_SENSORS)


// MSM/MDM related definitions
enum remote_procs {
    MSM = 0,
    MDM = 1,
    MDM2 = 2,
    QSC = 5,
};

// Android 10+ logging mode structure
struct diag_logging_mode_param_t {
    uint32_t req_mode;
    uint32_t peripheral_mask;
    uint32_t pd_mask;
    uint8_t mode_param;
    uint8_t diag_id;
    uint8_t pd_val;
    uint8_t reserved;
    int peripheral;
    int device_mask;
} __packed;

// Android 9 logging mode structure
struct diag_logging_mode_param_t_9 {
    int mode;
    int peripheral;
    int optional;
};

// Android 10的连接状态查询结构体
struct diag_con_all_param_t {
    uint32_t diag_con_all;
} __packed;


static uint16_t use_mdm = 0;
static int use_socket_mode = 0;
struct pollfd fds[FDS_LEN] = { 0 };
int number_fds = 0;
int diag_sock;
// pthread_mutex_t fdset_mutex removed - single-threaded approach

// Command to check device type
#define CHECK_DEVICE_CMD 0x7C


static int get_android_version(void) {
    char value[PROP_VALUE_MAX] = {0};
    int version = 10; // 默认值

    if (__system_property_get("ro.build.version.release", value) > 0) {
        version = atoi(value);
    }
    
    printf("Detected Android version: %d\n", version);
    return version;
}


static int check_system_version() {
    char value[PROP_VALUE_MAX] = {0};
    int kernel_version = 0;
    
    
    FILE* fp = fopen("/proc/version", "r");
    if (fp) {
        char version[256];
        if (fgets(version, sizeof(version), fp)) {
            sscanf(version, "Linux version %d", &kernel_version);
        }
        fclose(fp);
    }
    
    // 检查是否存在 diag socket
    int sock = socket(AF_UNIX, SOCK_SEQPACKET, 0);
    if (sock >= 0) {
        struct sockaddr_un addr = {
            .sun_family = AF_UNIX
        };
        strncpy(addr.sun_path, "\0diag", sizeof(addr.sun_path)-1);
        
        if (connect(sock, (struct sockaddr*)&addr, sizeof(addr)) == 0) {
            close(sock);
            return 1; // 使用 socket 模式
        }
        close(sock);
    }
    
    return 0; // 使用 /dev/diag 模式
}

// 配置旧版本 diag 设备
static int configure_legacy_diag() {
    int android_version = get_android_version();
    
    if (android_version >= 10) {
        struct diag_logging_mode_param_t mode_param = {0};
        struct diag_con_all_param_t con_all = {0};
        
        // 查询连接状态
        con_all.diag_con_all = 0xff;
        int ret = ioctl(diag_sock, DIAG_IOCTL_QUERY_CON_ALL, &con_all);
        
        // 配置 logging mode
        mode_param.req_mode = MEMORY_DEVICE_MODE;
        mode_param.peripheral_mask = (ret == 0) ? con_all.diag_con_all : 0x7f;
        mode_param.pd_mask = 0;
        mode_param.mode_param = 1;
        mode_param.peripheral = -EINVAL;
        mode_param.device_mask = 1 << DIAG_MD_LOCAL;
        
        if (ioctl(diag_sock, DIAG_IOCTL_SWITCH_LOGGING, &mode_param) < 0) {
            // 如果失败,尝试使用最基本的配置
            mode_param.peripheral_mask = DIAG_CON_APSS;
            mode_param.device_mask = 1;
            mode_param.mode_param = 0;
            if (ioctl(diag_sock, DIAG_IOCTL_SWITCH_LOGGING, &mode_param) < 0) {
                return -1;
            }
        }
        
        if (ret == 0 && (con_all.diag_con_all & DIAG_CON_MPSS)) {
            use_mdm = 1;
            printf("MDM support detected (Android 10+)\n");
        }
    } else {
        // Android 9 及以下版本
        struct diag_logging_mode_param_t_9 mode_param = {
            .mode = MEMORY_DEVICE_MODE,
            .peripheral = -1,
            .optional = 0
        };
        
        // 检测 MDM 支持
        int use_mdm_temp = 0;
        if (ioctl(diag_sock, DIAG_IOCTL_REMOTE_DEV, &use_mdm_temp) == 0 && use_mdm_temp) {
            use_mdm = 1;
            printf("MDM support detected (Legacy mode)\n");
        }
        
        if (ioctl(diag_sock, DIAG_IOCTL_SWITCH_LOGGING, &mode_param) < 0) {
            return -1;
        }
    }
    
    return 0;
}

void error(char* arg) {
    perror(arg);
    exit(1);
}

// Check device type (MSM/MDM)
static int check_device_type() {
    char cmd = CHECK_DEVICE_CMD;
    char response[256];
    int ret;
    
    // Send check command
    ret = write(diag_sock, &cmd, 1);
    if (ret < 0) {
        printf("[-] Failed to send device check command\n");
        return 0; // Default to MSM
    }
    
    // Read response
    ret = read(diag_sock, response, sizeof(response));
    if (ret < 0) {
        printf("[-] Failed to read device check response\n");
        return 0;
    }
    
    // Parse response to determine device type
    // Need to adjust parsing logic according to actual protocol
    int device_type = (ret > 0 && response[1] == MDM) ? 1 : 0;
    printf("[+] Device type check: %s\n", device_type ? "MDM" : "MSM");
    
    return device_type;
}

// diag_read_thread removed - now using single-threaded poll-based approach

int main(void) {
    setvbuf(stdout, NULL, _IONBF, 0);
    
    char* diag_buffer = malloc(BUFFER_LEN);
    int return_value;
    
    // 检测使用哪种通信方式
    use_socket_mode = check_system_version();
    printf("[+] Using %s mode\n", use_socket_mode ? "Socket" : "Legacy");
    
    if (use_socket_mode) {
        // Socket 模式初始化
        diag_sock = socket(AF_UNIX, SOCK_SEQPACKET, 0);
        if (diag_sock < 0) error("socket");
        
        struct sockaddr_un addr = {
            .sun_family = AF_UNIX
        };
        strncpy(addr.sun_path, "\0diag", sizeof(addr.sun_path)-1);
        
        return_value = connect(diag_sock, (struct sockaddr*)&addr, sizeof(addr));
        if (return_value < 0) error("connect to diag");
        
        // Set diag_sock to non-blocking mode
        int flags = fcntl(diag_sock, F_GETFL, 0);
        if (flags < 0) error("fcntl F_GETFL");
        if (fcntl(diag_sock, F_SETFL, flags | O_NONBLOCK) < 0) error("fcntl F_SETFL");
    } else {
        // Legacy 模式初始化
        diag_sock = open("/dev/diag", O_RDWR | O_LARGEFILE);
        if (diag_sock < 0) error("open /dev/diag");
        
        if (configure_legacy_diag() < 0) {
            error("configure legacy diag");
        }
        
        // Set diag_sock to non-blocking mode
        int flags = fcntl(diag_sock, F_GETFL, 0);
        if (flags < 0) error("fcntl F_GETFL");
        if (fcntl(diag_sock, F_SETFL, flags | O_NONBLOCK) < 0) error("fcntl F_SETFL");
    }

    // 初始化消息头
    *(unsigned int*) diag_buffer = USER_SPACE_DATA_TYPE;
    // 移除添加0xFFFFFFFF的代码

    // Initialize TCP server
    printf("[DEBUG] Starting TCP server initialization...\n");
    int server = socket(AF_INET, SOCK_STREAM, 0);
    if (server < 0) error("socket");
    printf("[DEBUG] Created server socket fd %d\n", server);

    struct sockaddr_in server_info = {
        .sin_family = AF_INET,
        .sin_port = htons(QCSUPER_TCP_PORT),
        .sin_addr = {
            .s_addr = htonl(INADDR_ANY)
        }
    };

    const int DO_REUSE_ADDR = 1;
    return_value = setsockopt(server, SOL_SOCKET, SO_REUSEADDR, &DO_REUSE_ADDR, sizeof DO_REUSE_ADDR);
    if (return_value < 0) error("setsockopt");
    
    return_value = bind(server, (struct sockaddr *) &server_info, sizeof(server_info));
    if (return_value < 0) error("bind");
    printf("[SERVER] Successfully bound to port %d\n", QCSUPER_TCP_PORT);
    
    return_value = listen(server, 16);
    if (return_value < 0) error("listen");
    printf("[SERVER] Successfully listening on fd %d\n", server);
    
    printf("Connection to Diag established (Mode: %s)\n", use_mdm ? "MDM" : "MSM");
    
    fds[0].fd = server;
    fds[0].events = POLLIN;
    fds[1].fd = diag_sock;
    fds[1].events = POLLIN;
    number_fds = 2;
    
    printf("[INIT] fds[0] = server fd %d\n", server);
    printf("[INIT] fds[1] = diag_sock fd %d\n", diag_sock);
    printf("[INIT] number_fds = %d\n", number_fds);
    
    // Verify server socket status
    struct sockaddr_in check_addr;
    socklen_t check_len = sizeof(check_addr);
    if (getsockname(server, (struct sockaddr*)&check_addr, &check_len) == 0) {
        printf("[INIT] Server socket bound to port %d\n", ntohs(check_addr.sin_port));
    } else {
        printf("[INIT] Failed to get server socket name: %s\n", strerror(errno));
    }
    
    // pthread_create removed - using single-threaded poll-based approach

    while(1) {
        printf("[POLL] Waiting for events on %d fds...\n", number_fds);
        return_value = poll(fds, number_fds, -1);
        if (return_value < 0) error("poll");
        
        printf("[POLL] Got %d events\n", return_value);
        for(int i = 0; i < number_fds; i++) {
            struct pollfd some_fd = fds[i];
            
            printf("[POLL] Checking fd %d (index %d), revents=0x%x\n", some_fd.fd, i, some_fd.revents);
            
            if(some_fd.revents & POLLIN) {
                printf("[POLL] fd %d (index %d) has POLLIN event\n", some_fd.fd, i);
            }
            
            if(!(some_fd.revents & POLLIN)) {
                continue;
            }
            
            if(some_fd.fd == server) {
                printf("[SERVER] New client connection detected\n");
                struct sockaddr_in client_info = { 0 };
                socklen_t client_info_size = sizeof(client_info);
                int client = accept(server, (struct sockaddr *) &client_info, &client_info_size);
                
                if (client < 0) error("accept");
                
                if(number_fds > FDS_LEN) {
                    fprintf(stderr, "Error: too many clients\n");
                    exit(1);
                }
        
                // 发送模式信息给新连接的客户端
                const char* mode_msg = use_socket_mode ? 
                    "[+] Using Socket mode\n" : 
                    "[+] Using Legacy mode\n";
                printf("[SERVER] Sending welcome message to client fd %d\n", client);
                write(client, mode_msg, strlen(mode_msg));

                // Set client socket to non-blocking mode
                int client_flags = fcntl(client, F_GETFL, 0);
                if (client_flags >= 0) {
                    fcntl(client, F_SETFL, client_flags | O_NONBLOCK);
                    printf("[SERVER] Set client fd %d to non-blocking mode\n", client);
                }

                printf("[SERVER] Adding client fd %d to poll list at index %d\n", client, number_fds);
                fds[number_fds].fd = client;
                fds[number_fds].events = POLLIN;
                number_fds++;
                printf("[SERVER] Total fds now: %d\n", number_fds);
            }
            else if(some_fd.fd == diag_sock) {
                printf("[DIAG] Processing diag_sock fd %d\n", diag_sock);
                // Single non-blocking read from diag_sock - let poll() handle frequency
                int bytes_read = read(diag_sock, diag_buffer, BUFFER_LEN);
                printf("[DIAG] read() returned %d bytes\n", bytes_read);
                
                if (bytes_read > 0) {
                    printf("[DIAG READ] %d bytes: ", bytes_read);
                    for(int k = 0; k < bytes_read; k++) {
                        printf("%02x ", (unsigned char)diag_buffer[k]);
                    }
                    printf("\n");
                    
                    // Forward to all connected clients (starting from index 2)
                    printf("[DIAG] Forwarding to %d clients (total_fds=%d)\n", number_fds - 2, number_fds);
                    for(int j = 2; j < number_fds; j++) {
                        printf("[DIAG] Writing to client fd %d\n", fds[j].fd);
                        write(fds[j].fd, diag_buffer, bytes_read);
                    }
                } else if (bytes_read == 0) {
                    printf("[DIAG] read() returned 0 - connection closed\n");
                } else if (bytes_read < 0) {
                    if (errno == EAGAIN || errno == EWOULDBLOCK) {
                        printf("[DIAG] read() returned EAGAIN/EWOULDBLOCK\n");
                    } else {
                        printf("[-] Error reading from diag_sock: %s\n", strerror(errno));
                    }
                }
                printf("[DIAG] Finished processing diag_sock\n");
                // For EAGAIN/EWOULDBLOCK or bytes_read==0, just continue - poll() will notify us again
            }
            else {
                // 处理客户端数据
                printf("[CLIENT] Processing client fd %d\n", some_fd.fd);
                printf("[%d] Reading data from client...\n", some_fd.fd);
                int bytes_read = read(some_fd.fd, diag_buffer, BUFFER_LEN);
                
                if(bytes_read < 1) {
                    if (bytes_read == 0) {
                        printf("[%d] Client closed connection\n", some_fd.fd);
                        goto remove_fd;
                    } else if (errno == EAGAIN || errno == EWOULDBLOCK) {
                        printf("[%d] No data available (EAGAIN), continuing...\n", some_fd.fd);
                        continue;
                    } else {
                        printf("[%d] Client read failed: %s\n", some_fd.fd, strerror(errno));
                        goto remove_fd;
                    }
                }

                printf("[%d] RX: ", some_fd.fd);
                for(int i = 0; i < bytes_read; i++) {
                    printf("%02X ", (unsigned char)diag_buffer[i]);
                }
                printf("\n");

                int write_len = bytes_read;
                char* write_buf = diag_buffer;
                
                // 检查数据是否以 7E 结尾，并且不是以 20 00 00 00 开头的
                if (bytes_read > 0 && 
                    (unsigned char)diag_buffer[bytes_read - 1] == 0x7e &&
                    !(bytes_read >= 4 && 
                      (unsigned char)diag_buffer[0] == 0x20 && 
                      (unsigned char)diag_buffer[1] == 0x00 &&
                      (unsigned char)diag_buffer[2] == 0x00 &&
                      (unsigned char)diag_buffer[3] == 0x00)) {
                    
                    // 只添加基本头部，不添加0xFFFFFFFF
                    int header_size = 4;
                    
                    char* temp_buffer = malloc(bytes_read + header_size);
                    if (temp_buffer) {
                        // 添加基本头部 20 00 00 00
                        *(unsigned int*)temp_buffer = USER_SPACE_DATA_TYPE;
                        
                        // 复制原始数据
                        memcpy(temp_buffer + header_size, diag_buffer, bytes_read);
                        write_buf = temp_buffer;
                        write_len = bytes_read + header_size;
                    }
                }
                // 移除添加0xFFFFFFFF的第二个条件分支
                
                printf("[%d] TX to diag: ", some_fd.fd);
                for(int i = 0; i < write_len; i++) {
                    printf("%02X ", (unsigned char)write_buf[i]);
                }
                printf("\n");
                
                return_value = write(diag_sock, write_buf, write_len);
                if (return_value < 0) {
                    printf("[%d] Writing to diag failed: %s\n", some_fd.fd, strerror(errno));
                    if (write_buf != diag_buffer) free(write_buf);
                    error("write to diag");
                }

                if (write_buf != diag_buffer) {
                    free(write_buf);
                }
                
                continue;

remove_fd:
                memcpy(&fds[i], &fds[i + 1], sizeof(fds[0]) * (FDS_LEN - number_fds));
                number_fds--;
            }
        }
    }
    
    return 0;
}


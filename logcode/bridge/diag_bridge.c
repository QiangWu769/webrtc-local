#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/socket.h>
#include <poll.h>
#include <string.h>
#include <pthread.h>
#include <errno.h>
#include <sys/un.h>
#include <netinet/in.h>
#include <sys/ioctl.h>
#include <sys/system_properties.h>
#include <sys/time.h>
#include <time.h>

// Timestamp parsing constants (from diag_bsr.py)
#define PER_SECOND 52428800.0  // DIAG timestamp tick frequency (52.4MHz)
#define EPOCH_YEAR 1980         // DIAG epoch start year
#define EPOCH_MONTH 1           // DIAG epoch start month
#define EPOCH_DAY 6             // DIAG epoch start day

#define QCSUPER_TCP_PORT 43555              // TCP port for client connections
#define BUFFER_LEN 1024 * 1024 * 10         // 10MB buffer for DIAG data
#define FDS_LEN 4096                        // Maximum number of file descriptors
#define USER_SPACE_DATA_TYPE 0x00000020     // Magic header for userspace DIAG messages
#define MEMORY_DEVICE_MODE 2                // Mode for memory device logging
#define DIAG_IOCTL_SWITCH_LOGGING 7         // IOCTL to switch logging mode
#define DIAG_IOCTL_QUERY_CON_ALL 41         // IOCTL to query all connections
#define DIAG_IOCTL_REMOTE_DEV 32            // IOCTL for remote device operations
#define DIAG_IOCTL_PERIPHERAL_BUF_DRAIN 36  // IOCTL to drain peripheral buffer
#define DIAG_IOCTL_PERIPHERAL_BUF_CONFIG 35 // IOCTL to configure peripheral buffer
#define DIAG_MD_LOCAL 0                     // Local memory device ID

// Buffer mode definitions
#define DIAG_BUFFERING_MODE_STREAMING 0     // Streaming mode - immediate data transfer
#define DIAG_BUFFERING_MODE_THRESHOLD 1     // Threshold mode - buffer until threshold reached
#define DIAG_BUFFERING_MODE_CIRCULAR 2      // Circular mode - circular buffer
#define DEFAULT_HIGH_WM_VAL 85              // Default high watermark value (85%)
#define DEFAULT_LOW_WM_VAL 15               // Default low watermark value (15%)

// Peripheral mask definitions
#define DIAG_CON_APSS    (0x0001)    /* Bit mask for Application Processor Subsystem */
#define DIAG_CON_MPSS    (0x0002)    /* Bit mask for Modem Processor Subsystem */
#define DIAG_CON_LPASS   (0x0004)    /* Bit mask for Low Power Audio Subsystem */
#define DIAG_CON_WCNSS   (0x0008)    /* Bit mask for Wireless Connectivity Subsystem */
#define DIAG_CON_SENSORS (0x0010)    /* Bit mask for Sensors Subsystem */
#define DIAG_CON_NONE    (0x0000)    /* Bit mask for No Subsystem*/
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

// Android 10+ connection status query structure
struct diag_con_all_param_t {
    uint32_t diag_con_all;  // Bitmask of all connected peripherals
} __packed;

// Buffer mode configuration structure
struct diag_buffering_mode_t {
    uint8_t peripheral;     // Target peripheral ID (0 for all)
    uint8_t mode;          // Buffer mode (streaming/threshold/circular)
    uint8_t high_wm_val;   // High watermark percentage
    uint8_t low_wm_val;    // Low watermark percentage
} __packed;


static uint16_t use_mdm = 0;                                // Flag for MDM device support
static int use_socket_mode = 0;                            // Flag for socket mode vs legacy /dev/diag mode
static int buffering_mode = DIAG_BUFFERING_MODE_STREAMING; // Default to streaming mode
struct pollfd fds[FDS_LEN] = { 0 };                       // File descriptor poll array
int number_fds = 0;                                        // Number of active file descriptors
int diag_sock;                                             // DIAG socket/device file descriptor
pthread_mutex_t fdset_mutex = PTHREAD_MUTEX_INITIALIZER;   // Mutex for file descriptor set protection

// Drain thread control
static pthread_t drain_thread;
static volatile int drain_thread_running = 0;
static volatile int drain_thread_started = 0;
static volatile int config_completed = 0;

// Timestamp tracking for latency calculation
static double last_send_timestamp = 0.0;
static pthread_mutex_t timestamp_mutex = PTHREAD_MUTEX_INITIALIZER;
static volatile int has_pending_command = 0;

// Command to check device type
#define CHECK_DEVICE_CMD 0x7C

// gettid function is already defined in Android NDK, can be used directly

// FINAL_MESSAGE pattern from diag_bsr.py: b'\x60\x00\x12\x6a\x7e'
static const unsigned char FINAL_MESSAGE_PATTERN[] = {0x60, 0x00, 0x12, 0x6a, 0x7e};
#define FINAL_MESSAGE_LENGTH 5

// Check if data contains the final configuration message
static int is_final_config_message(const char* data, int len) {
    if (len < FINAL_MESSAGE_LENGTH) return 0;
    
    // Look for the pattern in the data
    for (int i = 0; i <= len - FINAL_MESSAGE_LENGTH; i++) {
        if (memcmp(data + i, FINAL_MESSAGE_PATTERN, FINAL_MESSAGE_LENGTH) == 0) {
            return 1;
        }
    }
    return 0;
}

// Function prototypes
void* drain_thread_func(void* arg);
char* convert_diag_timestamp(uint64_t timestamp);
double convert_diag_timestamp_to_unix(uint64_t timestamp);
void print_hex_data(const char* prefix, const unsigned char* data, int len);
int detect_1d_response(const char* data, int len);

static int get_android_version(void) {
    char value[PROP_VALUE_MAX] = {0};
    int version = 10; // 默认值

    if (__system_property_get("ro.build.version.release", value) > 0) {
        version = atoi(value);
    }
    
    printf("Detected Android version: %d\n", version);
    return version;
}


// Configure peripheral buffer (only used in legacy mode)
static int configure_peripheral_buffer() {
    // Only configure buffer in legacy mode
    if (use_socket_mode) {
        printf("[+] Socket mode detected, skipping peripheral buffer configuration\n");
        return 0;
    }
    
    struct diag_buffering_mode_t buffer_config;
    buffer_config.peripheral = 0;  // Apply to all peripherals
    buffer_config.mode = buffering_mode;
    buffer_config.high_wm_val = DEFAULT_HIGH_WM_VAL;
    buffer_config.low_wm_val = DEFAULT_LOW_WM_VAL;
    
    int ret = ioctl(diag_sock, DIAG_IOCTL_PERIPHERAL_BUF_CONFIG, &buffer_config);
    if (ret < 0) {
        printf("[-] ioctl DIAG_IOCTL_PERIPHERAL_BUF_CONFIG failed: %s\n", strerror(errno));
        return -1;
    } else {
        printf("[+] Peripheral buffer configured successfully (mode: %s)\n", 
               buffering_mode == DIAG_BUFFERING_MODE_STREAMING ? "streaming" :
               buffering_mode == DIAG_BUFFERING_MODE_CIRCULAR ? "circular" :
               buffering_mode == DIAG_BUFFERING_MODE_THRESHOLD ? "threshold" : "unknown");
    }
    return 0;
}

// Convert DIAG timestamp to readable format (based on diag_bsr.py logic)
char* convert_diag_timestamp(uint64_t timestamp) {
    static char time_str[64];
    
    if (timestamp == 0) {
        snprintf(time_str, sizeof(time_str), "N/A");
        return time_str;
    }
    
    // Calculate seconds since DIAG epoch (1980-01-06 00:00:00 UTC)
    double seconds_since_epoch = (double)timestamp / PER_SECOND;
    
    // Use time.h library to accurately calculate Unix timestamp for Jan 6, 1980 to avoid hardcoding errors
    struct tm diag_epoch_tm;
    memset(&diag_epoch_tm, 0, sizeof(struct tm));
    diag_epoch_tm.tm_year = 1980 - 1900;
    diag_epoch_tm.tm_mon = 0;
    diag_epoch_tm.tm_mday = 6;

    time_t diag_epoch_unix_ts = timegm(&diag_epoch_tm);

    time_t unix_timestamp_sec = (time_t)(seconds_since_epoch + diag_epoch_unix_ts);
    
    struct tm *tm_info = localtime(&unix_timestamp_sec);
    if (tm_info) {
        // Get microseconds part
        double fractional_part = seconds_since_epoch - (long long)seconds_since_epoch;
        int microseconds = (int)(fractional_part * 1000000);
        
        snprintf(time_str, sizeof(time_str), "%04d-%02d-%02d %02d:%02d:%02d.%06d",
                tm_info->tm_year + 1900, tm_info->tm_mon + 1, tm_info->tm_mday,
                tm_info->tm_hour, tm_info->tm_min, tm_info->tm_sec, microseconds);
    } else {
        snprintf(time_str, sizeof(time_str), "Invalid timestamp: %llu", 
                (unsigned long long)timestamp);
    }
    
    return time_str;
}

// Convert DIAG timestamp to Unix timestamp (double)
double convert_diag_timestamp_to_unix(uint64_t timestamp) {
    if (timestamp == 0) {
        return 0.0;
    }
    
    // Calculate seconds since DIAG epoch (1980-01-06 00:00:00 UTC)
    double seconds_since_epoch = (double)timestamp / PER_SECOND;
    
    // Use time.h library to accurately calculate Unix timestamp for Jan 6, 1980 to avoid hardcoding errors
    struct tm diag_epoch_tm;
    memset(&diag_epoch_tm, 0, sizeof(struct tm));
    diag_epoch_tm.tm_year = 1980 - 1900;
    diag_epoch_tm.tm_mon = 0;
    diag_epoch_tm.tm_mday = 6;

    time_t diag_epoch_unix_ts = timegm(&diag_epoch_tm);

    double unix_timestamp = seconds_since_epoch + diag_epoch_unix_ts;
    
    return unix_timestamp;
}

// Print hex data with prefix
void print_hex_data(const char* prefix, const unsigned char* data, int len) {
    printf("%s", prefix);
    for (int i = 0; i < len; i++) {
        printf("%02X ", data[i]);
        if ((i + 1) % 16 == 0) printf("\n           "); // Align continuation lines
    }
    printf("\n");
}

// Detect 0x1D response in HDLC data
int detect_1d_response(const char* data, int len) {
    // Look for 0x1D response patterns in the data
    // Pattern 1: Direct 0x1D
    // Pattern 2: HDLC encoded 0x1D (0x9D)
    // Pattern 3: Look for response to 0x1D command which might start with specific patterns
    
    for (int i = 0; i < len - 4; i++) {
        // Look for 0x1D response pattern
        if ((unsigned char)data[i] == 0x1D) {
            return i;
        }
        
        // Look for HDLC encoded 0x1D (0x7D 0x3D)
        if ((unsigned char)data[i] == 0x7D && i + 1 < len && 
            (unsigned char)data[i + 1] == 0x3D) {
            return i;
        }
        
        // Look for response that contains 0x9D (which could be 0x1D with bit 7 set)
        if ((unsigned char)data[i] == 0x9D) {
            return i;
        }
        
        // Look for pattern that might indicate timestamp data
        // Check for sequence that looks like response header + timestamps
        if (i + 12 < len) {
            // Look for patterns that might indicate the start of timestamp data
            // This is a heuristic approach - might need adjustment based on actual data
            uint32_t possible_header = *(uint32_t*)(data + i);
            if (possible_header == 0x0000001d || possible_header == 0x1d000000) {
                return i;
            }
        }
    }
    return -1; // Not found
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
    
    // Check if DIAG socket exists
    int sock = socket(AF_UNIX, SOCK_SEQPACKET, 0);
    if (sock >= 0) {
        struct sockaddr_un addr = {
            .sun_family = AF_UNIX
        };
        strncpy(addr.sun_path, "\0diag", sizeof(addr.sun_path)-1);
        
        if (connect(sock, (struct sockaddr*)&addr, sizeof(addr)) == 0) {
            close(sock);
            return 1; // Use socket mode
        }
        close(sock);
    }
    
    return 0; // Use /dev/diag legacy mode
}

// Configure legacy DIAG device
static int configure_legacy_diag() {
    int android_version = get_android_version();
    
    if (android_version >= 10) {
        struct diag_logging_mode_param_t mode_param = {0};
        struct diag_con_all_param_t con_all = {0};
        
        // Query connection status
        con_all.diag_con_all = 0xff;
        int ret = ioctl(diag_sock, DIAG_IOCTL_QUERY_CON_ALL, &con_all);
        
        // Configure logging mode
        mode_param.req_mode = MEMORY_DEVICE_MODE;
        mode_param.peripheral_mask = (ret == 0) ? con_all.diag_con_all : 0x7f;
        mode_param.pd_mask = 0;
        mode_param.mode_param = 1;
        mode_param.peripheral = -EINVAL;
        mode_param.device_mask = 1 << DIAG_MD_LOCAL;
        
        if (ioctl(diag_sock, DIAG_IOCTL_SWITCH_LOGGING, &mode_param) < 0) {
            // If failed, try using the most basic configuration
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
        // Android 9 and below
        struct diag_logging_mode_param_t_9 mode_param = {
            .mode = MEMORY_DEVICE_MODE,
            .peripheral = -1,
            .optional = 0
        };
        
        // Detect MDM support
        int use_mdm_temp = 0;
        if (ioctl(diag_sock, DIAG_IOCTL_REMOTE_DEV, &use_mdm_temp) == 0 && use_mdm_temp) {
            use_mdm = 1;
            printf("MDM support detected (Legacy mode)\n");
        }
        
        if (ioctl(diag_sock, DIAG_IOCTL_SWITCH_LOGGING, &mode_param) < 0) {
            return -1;
        }
    }
    
    // Configure peripheral buffer
    if (configure_peripheral_buffer() < 0) {
        printf("[-] Warning: Failed to configure peripheral buffer\n");
        // Don't return error as this is not a fatal error
    }
    
    return 0;
}

// Start drain thread after configuration is complete (legacy mode only)
void start_drain_thread() {
    // Only start drain thread in legacy mode
    if (use_socket_mode) {
        printf("[+] Socket mode detected, drain thread not needed\n");
        return;
    }
    
    if (!drain_thread_started) {
        if (pthread_create(&drain_thread, NULL, drain_thread_func, NULL) == 0) {
            drain_thread_started = 1;
            printf("[+] Drain thread started after configuration completed (Legacy mode)\n");
        } else {
            printf("[-] Failed to start drain thread\n");
        }
    }
}

void cleanup_drain_thread() {
    if (drain_thread_running) {
        printf("[+] Stopping drain thread...\n");
        drain_thread_running = 0;
        if (drain_thread_started) {
            pthread_join(drain_thread, NULL);
        }
    }
    
    // Cleanup mutex resources
    pthread_mutex_destroy(&timestamp_mutex);
}

void error(char* arg) {
    cleanup_drain_thread();
    perror(arg);
    exit(1);
}

// Check device type (MSM/MDM)
static int check_device_type() {
    char cmd = CHECK_DEVICE_CMD;
    char response[256];
    int ret;
    struct timeval send_tv, recv_tv;
    
    // Record timestamp before sending command
    gettimeofday(&send_tv, NULL);
    double send_timestamp = (double)send_tv.tv_sec + (double)send_tv.tv_usec / 1.0e6;
    printf("[DEVICE CHECK SEND] Command 0x%02X at timestamp %.6f\n", cmd, send_timestamp);
    
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
    
    // Calculate and display latency
    gettimeofday(&recv_tv, NULL);
    double recv_timestamp = (double)recv_tv.tv_sec + (double)recv_tv.tv_usec / 1.0e6;
    double latency_ms = (recv_timestamp - send_timestamp) * 1000.0;
    printf("[DEVICE CHECK READ] %d bytes at timestamp %.6f (Latency: %.3f ms)\n", 
           ret, recv_timestamp, latency_ms);
    
    // Parse response to determine device type
    // Need to adjust parsing logic according to actual protocol
    int device_type = (ret > 0 && response[1] == MDM) ? 1 : 0;
    printf("[+] Device type check: %s\n", device_type ? "MDM" : "MSM");
    
    return device_type;
}

// Drain thread function - periodically drains peripheral buffers (legacy mode only)
void* drain_thread_func(void* arg) {
    uint8_t peripheral = 0;
    pid_t thread_id = gettid();
    
    printf("[+] Drain thread started (Legacy mode), TID: %d\n", thread_id);
    
    drain_thread_running = 1;
    while(drain_thread_running) {
        // Only perform drain ioctl in legacy mode
        if (!use_socket_mode) {
            ioctl(diag_sock, DIAG_IOCTL_PERIPHERAL_BUF_DRAIN, &peripheral);
        }
        usleep(100); // 0.1 milliseconds
    }
    
    printf("[+] Drain thread stopped\n");
    return NULL;
}

void* diag_read_thread(void* arg) {
    char* diag_buffer = malloc(BUFFER_LEN);
    int header_size = sizeof(double); // 8 bytes for the timestamp
    struct timeval start_write, end_write; // Timing variables
    
    while(1) {
        int bytes_read = read(diag_sock, diag_buffer, BUFFER_LEN);
        if (bytes_read <= 0) {
            if (bytes_read < 0) {
                perror("read from diag_sock");
            }
            usleep(1000); // Prevent busy loop on error
            continue;
        }
        
        // --- Core logic: Get read timestamp ---
        
        // 1. After read() returns successfully, immediately get current high-precision timestamp
        struct timeval tv;
        gettimeofday(&tv, NULL);
        double timestamp_at_read = (double)tv.tv_sec + (double)tv.tv_usec / 1.0e6;
        
        // 2. Calculate latency (if there are pending commands)
        double latency_ms = 0.0;
        pthread_mutex_lock(&timestamp_mutex);
        if (has_pending_command && last_send_timestamp > 0.0) {
            latency_ms = (timestamp_at_read - last_send_timestamp) * 1000.0;
            has_pending_command = 0;  // Mark as processed
            printf("[DIAG READ] %d bytes at timestamp %.6f (Latency: %.3f ms)\n", 
                   bytes_read, timestamp_at_read, latency_ms);
        } else {
            printf("[DIAG READ] %d bytes at timestamp %.6f\n", bytes_read, timestamp_at_read);
        }
        pthread_mutex_unlock(&timestamp_mutex);
        
        // Check for 0x1D response and process timestamps
        int frame_pos = detect_1d_response(diag_buffer, bytes_read);
        if (frame_pos >= 0) {
            printf("\n=== 0x1D Response Detected at position %d ===\n", frame_pos);
            
            // Print the first 24 bytes (or available bytes if less than 24)
            int print_len = (bytes_read >= 24) ? 24 : bytes_read;
            print_hex_data("[0x1D RESPONSE] First 24 bytes: ", 
                          (unsigned char*)diag_buffer, print_len);
            
            // Find the 0x1D byte and extract the 8 bytes after it
            for (int i = 0; i < bytes_read - 8; i++) {
                if ((unsigned char)diag_buffer[i] == 0x1D && i + 9 <= bytes_read) {
                    // Found 0x1D, extract the next 8 bytes as timestamp
                    uint64_t timestamp = 0;
                    memcpy(&timestamp, diag_buffer + i + 1, 8);
                    
                    printf("[1D TIMESTAMP] Found at offset %d+1\n", i);
                    printf("[1D TIMESTAMP] 8 bytes after 1D: ");
                    for (int j = 0; j < 8; j++) {
                        printf("%02X ", (unsigned char)diag_buffer[i + 1 + j]);
                    }
                    printf("\n");
                    
                    char* readable_time = convert_diag_timestamp(timestamp);
                    printf("[1D TIMESTAMP] Raw: 0x%016llX, Readable: %s\n", 
                           (unsigned long long)timestamp, readable_time);
                    
                    // Convert parsed timestamp to Unix timestamp and compare
                    double diag_unix_time = convert_diag_timestamp_to_unix(timestamp);
                    double time_diff = timestamp_at_read - diag_unix_time;
                    
                    printf("[TIME COMPARISON]\n");
                    printf("  DIAG timestamp (converted to Unix): %.6f\n", diag_unix_time);
                    printf("  Message read time (Unix):           %.6f\n", timestamp_at_read);
                    printf("  Time difference (read - diag):      %.6f seconds (%.3f ms)\n", 
                           time_diff, time_diff * 1000.0);
                    
                    if (time_diff > 0) {
                        printf("  → Message read %.3f ms AFTER the event timestamp\n", time_diff * 1000.0);
                    } else {
                        printf("  → Message read %.3f ms BEFORE the event timestamp (clock skew?)\n", -time_diff * 1000.0);
                    }
                    
                    break;
                }
            }
            printf("=== End 0x1D Response ===\n\n");
        }
        
        // 2. Prepare total data packet to send (timestamp + raw data)
        int total_size_to_send = header_size + bytes_read;
        char* send_buffer = malloc(total_size_to_send);
        if (!send_buffer) {
            perror("malloc send_buffer");
            continue;
        }
        
        // 3. Fill data packet: write timestamp first, then raw data
        memcpy(send_buffer, &timestamp_at_read, header_size);
        memcpy(send_buffer + header_size, diag_buffer, bytes_read);
        
        // 4. Forward this new timestamped data packet to all clients
        pthread_mutex_lock(&fdset_mutex);
        for(int j = 1; j < number_fds; j++) {
            gettimeofday(&start_write, NULL);
            int sent = write(fds[j].fd, send_buffer, total_size_to_send);
            gettimeofday(&end_write, NULL);
            
            // Calculate elapsed time and print log when threshold exceeded
            long seconds = end_write.tv_sec - start_write.tv_sec;
            long microseconds = end_write.tv_usec - start_write.tv_usec;
            double elapsed_ms = seconds * 1000 + microseconds / 1000.0;
            
            if (elapsed_ms > 10.0) {
                printf("[DEBUG] write() to fd %d blocked for %.3f ms\n", fds[j].fd, elapsed_ms);
            }
            
            if (sent < 0) {
                printf("[-] Failed to send data to client %d: %s\n", fds[j].fd, strerror(errno));
            }
        }
        pthread_mutex_unlock(&fdset_mutex);
        
        // 5. Free temporary memory
        free(send_buffer);
    }
    free(diag_buffer);
    return NULL;
}

// Set buffer mode
static void set_buffering_mode(const char* mode_str) {
    if (mode_str == NULL) {
        buffering_mode = DIAG_BUFFERING_MODE_STREAMING; // Default
        return;
    }
    
    if (strcmp(mode_str, "streaming") == 0) {
        buffering_mode = DIAG_BUFFERING_MODE_STREAMING;
    } else if (strcmp(mode_str, "circular") == 0) {
        buffering_mode = DIAG_BUFFERING_MODE_CIRCULAR;
    } else if (strcmp(mode_str, "threshold") == 0) {
        buffering_mode = DIAG_BUFFERING_MODE_THRESHOLD;
    } else {
        printf("[-] Warning: Unknown buffering mode '%s', using streaming mode\n", mode_str);
        buffering_mode = DIAG_BUFFERING_MODE_STREAMING;
    }
}

int main(int argc, char* argv[]) {
    setvbuf(stdout, NULL, _IONBF, 0);
    
    // Process command line arguments
    if (argc > 1) {
        set_buffering_mode(argv[1]);
        printf("[+] Using buffering mode: %s\n", argv[1]);
    } else {
        printf("[+] Using default buffering mode: streaming\n");
    }
    
    char* diag_buffer = malloc(BUFFER_LEN);
    int return_value;
    
    // Detect which communication method to use
    use_socket_mode = check_system_version();
    printf("[+] Using %s mode\n", use_socket_mode ? "Socket" : "Legacy");
    
    if (use_socket_mode) {
        // Socket mode initialization
        diag_sock = socket(AF_UNIX, SOCK_SEQPACKET, 0);
        if (diag_sock < 0) error("socket");
        
        struct sockaddr_un addr = {
            .sun_family = AF_UNIX
        };
        strncpy(addr.sun_path, "\0diag", sizeof(addr.sun_path)-1);
        
        return_value = connect(diag_sock, (struct sockaddr*)&addr, sizeof(addr));
        if (return_value < 0) error("connect to diag");
    } else {
        // Legacy mode initialization
        diag_sock = open("/dev/diag", O_RDWR | O_LARGEFILE);
        if (diag_sock < 0) error("open /dev/diag");
        
        if (configure_legacy_diag() < 0) {
            error("configure legacy diag");
        }
    }

    // Initialize message header
    *(unsigned int*) diag_buffer = USER_SPACE_DATA_TYPE;
    // Removed code for adding 0xFFFFFFFF

    // Initialize TCP server
    int server = socket(AF_INET, SOCK_STREAM, 0);
    if (server < 0) error("socket");

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
    
    return_value = listen(server, 16);
    if (return_value < 0) error("listen");
    
    printf("Connection to Diag established (Mode: %s)\n", use_mdm ? "MDM" : "MSM");
    if (!use_socket_mode) {
        printf("[+] Legacy mode: Waiting for configuration completion before starting drain thread...\n");
    } else {
        printf("[+] Socket mode: Drain thread not required\n");
    }
    
    fds[0].fd = server;
    fds[0].events = POLLIN;
    number_fds = 1;
    
    pthread_t diag_thread;
    pthread_create(&diag_thread, NULL, &diag_read_thread, NULL);

    while(1) {
        return_value = poll(fds, number_fds, -1);
        if (return_value < 0) error("poll");
        
        for(int i = 0; i < number_fds; i++) {
            struct pollfd some_fd = fds[i];
            
            if(!(some_fd.revents & POLLIN)) {
                continue;
            }
            
            if(some_fd.fd == server) {
                struct sockaddr_in client_info = { 0 };
                socklen_t client_info_size = sizeof(client_info);
                int client = accept(server, (struct sockaddr *) &client_info, &client_info_size);
                
                if (client < 0) error("accept");
                
                if(number_fds > FDS_LEN) {
                    fprintf(stderr, "Error: too many clients\n");
                    exit(1);
                }
        
                // Send mode information to newly connected client
                const char* mode_msg = use_socket_mode ? 
                    "[+] Using Socket mode\n" : 
                    "[+] Using Legacy mode\n";
                write(client, mode_msg, strlen(mode_msg));

                pthread_mutex_lock(&fdset_mutex);
                fds[number_fds].fd = client;
                fds[number_fds].events = POLLIN;
                number_fds++;
                pthread_mutex_unlock(&fdset_mutex);
            }
            else {
                // Process client data
                printf("[%d] Reading data from client...\n", some_fd.fd);
                int bytes_read = read(some_fd.fd, diag_buffer, BUFFER_LEN);
                
                if(bytes_read < 1) {
                    printf("[%d] Client read failed: %s\n", some_fd.fd, strerror(errno));
                    goto remove_fd;
                }

                printf("[%d] RX: ", some_fd.fd);
                for(int i = 0; i < bytes_read; i++) {
                    printf("%02X ", (unsigned char)diag_buffer[i]);
                }
                printf("\n");

                // Check if this is the final configuration message
                if (!config_completed && is_final_config_message(diag_buffer, bytes_read)) {
                    config_completed = 1;
                    if (!use_socket_mode) {
                        printf("[+] Configuration completed! Starting drain thread (Legacy mode)...\n");
                        start_drain_thread();
                    } else {
                        printf("[+] Configuration completed! (Socket mode - no drain thread needed)\n");
                    }
                }

                int write_len = bytes_read;
                char* write_buf = diag_buffer;
                
                // Check if data ends with 0x7E and doesn't start with 0x20 00 00 00
                if (bytes_read > 0 && 
                    (unsigned char)diag_buffer[bytes_read - 1] == 0x7e &&
                    !(bytes_read >= 4 && 
                      (unsigned char)diag_buffer[0] == 0x20 && 
                      (unsigned char)diag_buffer[1] == 0x00 &&
                      (unsigned char)diag_buffer[2] == 0x00 &&
                      (unsigned char)diag_buffer[3] == 0x00)) {
                    
                    // Only add basic header, don't add 0xFFFFFFFF
                    int header_size = 4;
                    
                    char* temp_buffer = malloc(bytes_read + header_size);
                    if (temp_buffer) {
                        // Add basic header 0x20 00 00 00
                        *(unsigned int*)temp_buffer = USER_SPACE_DATA_TYPE;
                        
                        // Copy original data
                        memcpy(temp_buffer + header_size, diag_buffer, bytes_read);
                        write_buf = temp_buffer;
                        write_len = bytes_read + header_size;
                    }
                }
                // Removed second conditional branch for adding 0xFFFFFFFF
                
                printf("[%d] TX to diag: ", some_fd.fd);
                for(int i = 0; i < write_len; i++) {
                    printf("%02X ", (unsigned char)write_buf[i]);
                }
                printf("\n");
                
                // Record timestamp before sending command to diag
                struct timeval send_tv;
                gettimeofday(&send_tv, NULL);
                double send_timestamp = (double)send_tv.tv_sec + (double)send_tv.tv_usec / 1.0e6;
                
                pthread_mutex_lock(&timestamp_mutex);
                last_send_timestamp = send_timestamp;
                has_pending_command = 1;
                pthread_mutex_unlock(&timestamp_mutex);
                
                printf("[DIAG SEND] %d bytes at timestamp %.6f\n", write_len, send_timestamp);
                
                return_value = write(diag_sock, write_buf, write_len);
                if (return_value < 0) {
                    printf("[%d] Writing to diag failed: %s\n", some_fd.fd, strerror(errno));
                    // Clear pending command flag on failure
                    pthread_mutex_lock(&timestamp_mutex);
                    has_pending_command = 0;
                    pthread_mutex_unlock(&timestamp_mutex);
                    if (write_buf != diag_buffer) free(write_buf);
                    error("write to diag");
                }

                if (write_buf != diag_buffer) {
                    free(write_buf);
                }
                
                continue;

remove_fd:
                pthread_mutex_lock(&fdset_mutex);
                memcpy(&fds[i], &fds[i + 1], sizeof(fds[0]) * (FDS_LEN - number_fds));
                number_fds--;
                pthread_mutex_unlock(&fdset_mutex);
            }
        }
    }
    
    return 0;
}


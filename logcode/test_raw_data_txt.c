// Test the modified raw data logging functionality (txt format)
#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>
#include <string.h>
#include <time.h>

// Mock global variables
static FILE* raw_data_file = NULL;
static pthread_mutex_t raw_data_mutex = PTHREAD_MUTEX_INITIALIZER;
static long raw_data_counter = 0;

// Modified functions for txt output
void init_raw_data_logging() {
    pthread_mutex_lock(&raw_data_mutex);
    
    // Create filename with timestamp
    time_t now = time(NULL);
    struct tm* tm_info = localtime(&now);
    char filename[256];
    strftime(filename, sizeof(filename), "diag_raw_data_%Y%m%d_%H%M%S.txt", tm_info);
    
    raw_data_file = fopen(filename, "w");
    if (raw_data_file) {
        printf("[RAW DATA] Logging initialized to file: %s\n", filename);
        
        // Write file header with metadata
        fprintf(raw_data_file, "# DIAG Raw Data Log\n");
        fprintf(raw_data_file, "# Start Time: %s", asctime(tm_info));
        fprintf(raw_data_file, "# Format: [Entry#] [Unix_Timestamp] [Data_Length] [Hex_Data]\n");
        fprintf(raw_data_file, "# Example: [1] 1733025025.123456 10 7E 12 34 56 78 9A BC DE FF 7E\n");
        fprintf(raw_data_file, "# ========================================\n");
        fflush(raw_data_file);
        
        raw_data_counter = 0;
    } else {
        printf("[RAW DATA] Failed to create raw data log file: %s\n", filename);
    }
    
    pthread_mutex_unlock(&raw_data_mutex);
}

void log_raw_data(const char* data, int len, double timestamp) {
    pthread_mutex_lock(&raw_data_mutex);
    
    if (raw_data_file && data && len > 0) {
        raw_data_counter++;
        
        // Write entry header and hex data in one line
        fprintf(raw_data_file, "[%ld] %.6f %d ", raw_data_counter, timestamp, len);
        
        // Write hex representation
        for (int i = 0; i < len; i++) {
            fprintf(raw_data_file, "%02X", (unsigned char)data[i]);
            if (i < len - 1) fprintf(raw_data_file, " ");
        }
        fprintf(raw_data_file, "\n");
        
        fflush(raw_data_file); // Ensure data is written immediately
        
        if (raw_data_counter % 1000 == 0) {
            printf("[RAW DATA] Logged %ld entries\n", raw_data_counter);
        }
    }
    
    pthread_mutex_unlock(&raw_data_mutex);
}

void cleanup_raw_data_logging() {
    pthread_mutex_lock(&raw_data_mutex);
    
    if (raw_data_file) {
        fprintf(raw_data_file, "# Log ended at entry %ld\n", raw_data_counter);
        fclose(raw_data_file);
        raw_data_file = NULL;
        printf("[RAW DATA] Logging closed. Total entries: %ld\n", raw_data_counter);
    }
    
    pthread_mutex_unlock(&raw_data_mutex);
}

// Test function
int main() {
    printf("Testing modified raw data logging (txt format)...\n");
    
    // Initialize logging
    init_raw_data_logging();
    
    // Test with various sample data
    char sample1[] = {0x7e, 0x12, 0x34, 0x56, 0x78, 0x9a, 0xbc, 0xde, 0x7e};
    log_raw_data(sample1, sizeof(sample1), 1733025025.123456);
    
    char sample2[] = {0x7e, 0xff, 0x00, 0x11, 0x22, 0x7e};
    log_raw_data(sample2, sizeof(sample2), 1733025025.654321);
    
    char sample3[] = {0xaa, 0xbb, 0xcc};
    log_raw_data(sample3, sizeof(sample3), 1733025026.987654);
    
    // Test single byte
    char single_byte[] = {0x5a};
    log_raw_data(single_byte, sizeof(single_byte), 1733025027.111111);
    
    // Cleanup
    cleanup_raw_data_logging();
    
    printf("Test completed! Check the generated .txt file.\n");
    return 0;
}
// Test file to verify syntax of the added raw data logging functions
// This file extracts only the new functions to test compilation

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <pthread.h>
#include <string.h>
#include <time.h>

// Mock global variables for testing
static FILE* raw_data_file = NULL;
static pthread_mutex_t raw_data_mutex = PTHREAD_MUTEX_INITIALIZER;
static long raw_data_counter = 0;

// Initialize raw data logging file
void init_raw_data_logging() {
    pthread_mutex_lock(&raw_data_mutex);
    
    // Create filename with timestamp
    time_t now = time(NULL);
    struct tm* tm_info = localtime(&now);
    char filename[256];
    strftime(filename, sizeof(filename), "diag_raw_data_%Y%m%d_%H%M%S.bin", tm_info);
    
    raw_data_file = fopen(filename, "wb");
    if (raw_data_file) {
        printf("[RAW DATA] Logging initialized to file: %s\n", filename);
        
        // Write file header with metadata
        fprintf(raw_data_file, "# DIAG Raw Data Log\n");
        fprintf(raw_data_file, "# Start Time: %s", asctime(tm_info));
        fprintf(raw_data_file, "# Format: [Entry#] [Unix_Timestamp] [Data_Length] [Raw_Data_Bytes]\n");
        fprintf(raw_data_file, "# ========================================\n");
        fflush(raw_data_file);
        
        raw_data_counter = 0;
    } else {
        printf("[RAW DATA] Failed to create raw data log file: %s\n", filename);
    }
    
    pthread_mutex_unlock(&raw_data_mutex);
}

// Log raw data with timestamp
void log_raw_data(const char* data, int len, double timestamp) {
    pthread_mutex_lock(&raw_data_mutex);
    
    if (raw_data_file && data && len > 0) {
        raw_data_counter++;
        
        // Write entry header
        fprintf(raw_data_file, "\n[%ld] %.6f %d\n", raw_data_counter, timestamp, len);
        
        // Write raw binary data  
        size_t written = fwrite(data, 1, len, raw_data_file);
        if (written != len) {
            printf("[RAW DATA] Warning: Only wrote %zu of %d bytes\n", written, len);
        }
        
        // Write hex representation for readability
        fprintf(raw_data_file, "\nHEX: ");
        for (int i = 0; i < len; i++) {
            fprintf(raw_data_file, "%02X ", (unsigned char)data[i]);
            if ((i + 1) % 32 == 0) fprintf(raw_data_file, "\n     ");
        }
        fprintf(raw_data_file, "\n");
        
        fflush(raw_data_file); // Ensure data is written immediately
        
        if (raw_data_counter % 100 == 0) {
            printf("[RAW DATA] Logged %ld entries\n", raw_data_counter);
        }
    }
    
    pthread_mutex_unlock(&raw_data_mutex);
}

// Clean up raw data logging
void cleanup_raw_data_logging() {
    pthread_mutex_lock(&raw_data_mutex);
    
    if (raw_data_file) {
        fprintf(raw_data_file, "\n# Log ended at entry %ld\n", raw_data_counter);
        fclose(raw_data_file);
        raw_data_file = NULL;
        printf("[RAW DATA] Logging closed. Total entries: %ld\n", raw_data_counter);
    }
    
    pthread_mutex_unlock(&raw_data_mutex);
}

// Simple test function
int main() {
    printf("Testing raw data logging functions...\n");
    
    // Test initialization
    init_raw_data_logging();
    
    // Test logging some sample data
    char sample_data[] = {0x7e, 0x12, 0x34, 0x56, 0x78, 0x9a, 0xbc, 0xde, 0x7e};
    log_raw_data(sample_data, sizeof(sample_data), 1234567890.123456);
    
    char sample_data2[] = {0x7e, 0xff, 0x00, 0x11, 0x22, 0x7e};
    log_raw_data(sample_data2, sizeof(sample_data2), 1234567891.654321);
    
    // Test cleanup
    cleanup_raw_data_logging();
    
    printf("Test completed successfully!\n");
    return 0;
}
/*
 * Echo Server - 用于测量 adb forward RTT
 *
 * 编译: gcc -o echo_server echo_server.c
 * 运行: ./echo_server
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netinet/tcp.h>

#define PORT 43556
#define BUF_SIZE 1024

int main() {
    setvbuf(stdout, NULL, _IONBF, 0);

    int server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd < 0) {
        perror("socket");
        return 1;
    }

    int opt = 1;
    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    struct sockaddr_in addr = {
        .sin_family = AF_INET,
        .sin_port = htons(PORT),
        .sin_addr.s_addr = INADDR_ANY
    };

    if (bind(server_fd, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        perror("bind");
        return 1;
    }

    listen(server_fd, 1);
    printf("[+] Echo server listening on port %d\n", PORT);

    while (1) {
        printf("[+] Waiting for connection...\n");

        int client_fd = accept(server_fd, NULL, NULL);
        if (client_fd < 0) {
            perror("accept");
            continue;
        }

        // 禁用 Nagle 算法
        int flag = 1;
        setsockopt(client_fd, IPPROTO_TCP, TCP_NODELAY, &flag, sizeof(flag));

        printf("[+] Client connected\n");

        char buf[BUF_SIZE];
        ssize_t n;
        int count = 0;

        while ((n = read(client_fd, buf, BUF_SIZE)) > 0) {
            // 立即 echo 返回
            write(client_fd, buf, n);
            count++;
            if (count % 100 == 0) {
                printf("[ECHO] %d packets\n", count);
            }
        }

        printf("[-] Client disconnected (%d packets)\n", count);
        close(client_fd);
    }

    close(server_fd);
    return 0;
}

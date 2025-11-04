#!/bin/bash
# Script to run peerconnection_client with GDB and capture crash location

cd /home/wuq/webrtc-local

# Check if executable exists
if [ ! -f "out/Default/peerconnection_client" ]; then
    echo "Error: peerconnection_client not found"
    exit 1
fi

# Run with GDB
gdb -batch \
    -ex "set pagination off" \
    -ex "set logging file crash_backtrace.txt" \
    -ex "set logging on" \
    -ex "catch signal SIGABRT" \
    -ex "run" \
    -ex "thread apply all bt full" \
    -ex "quit" \
    out/Default/peerconnection_client

echo "Crash backtrace saved to crash_backtrace.txt"
echo "Last 100 lines:"
tail -100 crash_backtrace.txt

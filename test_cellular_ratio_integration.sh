#!/bin/bash

echo "=========================================="
echo "Testing Cellular Ratio Integration"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if process is running
check_process() {
    if pgrep -f "$1" > /dev/null; then
        echo -e "${GREEN}✓ $2 is running${NC}"
        return 0
    else
        echo -e "${RED}✗ $2 is not running${NC}"
        return 1
    fi
}

# Function to send test ratio data
send_test_ratio() {
    local ratio=$1
    local desc=$2
    echo -e "${YELLOW}Sending ratio: $ratio ($desc)${NC}"
    
    # Create a simple Python script to send the ratio
    python3 -c "
import socket
import struct
import time

sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
try:
    sock.connect('/tmp/webrtc_cellular_ratio.sock')
    
    # Send test packet: timestamp(8) + ratio(8) + sequence(4)
    timestamp_us = int(time.time() * 1e6)
    ratio = $ratio
    sequence = 1
    
    packet = struct.pack('<QdI', timestamp_us, ratio, sequence)
    sock.send(packet)
    print(f'Sent: timestamp={timestamp_us}, ratio={ratio}, seq={sequence}')
    
    sock.close()
except Exception as e:
    print(f'Error: {e}')
"
    sleep 2
}

echo "1. Starting diag_bridge (if needed)..."
if ! check_process "diag_bridge" "diag_bridge"; then
    echo "Starting diag_bridge..."
    ./logcode/bridge/diag_bridge &
    DIAG_PID=$!
    sleep 2
fi

echo ""
echo "2. Starting WebRTC peerconnection_client..."
echo "Please run in another terminal:"
echo -e "${GREEN}./src/out/Default/peerconnection_client --server=localhost${NC}"
echo ""
echo "Press Enter when peerconnection_client is running..."
read

echo ""
echo "3. Testing different ratio values..."
echo "Watch the peerconnection_client logs for AIMD responses"
echo ""

# Test sequence: gradually decrease ratio to trigger different AIMD states
send_test_ratio 1.0 "Normal - should allow normal AIMD"
send_test_ratio 0.9 "Slight congestion - should limit to additive increase"
send_test_ratio 0.7 "Moderate congestion - should force HOLD"
send_test_ratio 0.4 "Severe congestion - should force DECREASE"
send_test_ratio 0.8 "Recovery - should return to HOLD"
send_test_ratio 1.0 "Full recovery - should allow normal AIMD"

echo ""
echo -e "${GREEN}Test sequence completed!${NC}"
echo "Check peerconnection_client logs for:"
echo "  - [DelayBWE-Cellular] messages showing ratio received"
echo "  - [AIMD-Cellular] messages showing state changes"
echo "  - [AIMD-Hold/Increase/Decrease] messages showing AIMD decisions"

# Cleanup
if [ ! -z "$DIAG_PID" ]; then
    echo ""
    echo "Stopping diag_bridge..."
    kill $DIAG_PID 2>/dev/null
fi

echo ""
echo "=========================================="
echo "Test Complete"
echo "=========================================="
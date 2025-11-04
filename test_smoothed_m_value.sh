#!/bin/bash

# Test script for smoothed M value calculation
# This will run a quick test and show the difference in logs

echo "=========================================="
echo "Testing Smoothed M Value Implementation"
echo "=========================================="
echo ""

# Run peerconnection_client for a short duration
echo "Running WebRTC client for 30 seconds..."
timeout 30 src/out/Default/peerconnection_client --config=/home/wuq/webrtc-local/webrtc_config_results/sender_config_local.json > /tmp/test_smoothed_m.log 2>&1 &
PID=$!

# Wait for it to finish
wait $PID 2>/dev/null

echo "Test completed. Analyzing logs..."
echo ""

# Extract and display M value logs
echo "Sample M value logs (showing raw vs smoothed):"
echo "=============================================="
grep "AIMD-Cellular" /tmp/test_smoothed_m.log | head -10

echo ""
echo "Statistics:"
echo "=============================================="
echo "Total M value calculations: $(grep -c "AIMD-Cellular" /tmp/test_smoothed_m.log)"

# Check if smoothed values are shown
if grep -q "Smoothed Ratio" /tmp/test_smoothed_m.log; then
    echo "✓ Smoothed Ratio is being logged"
else
    echo "✗ Smoothed Ratio not found in logs"
fi

if grep -q "Smoothed Saturation" /tmp/test_smoothed_m.log; then
    echo "✓ Smoothed Saturation is being logged"
else
    echo "✗ Smoothed Saturation not found in logs"
fi

echo ""
echo "Full log saved to: /tmp/test_smoothed_m.log"

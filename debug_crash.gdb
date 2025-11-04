# GDB script to catch the IsFinite() crash
set pagination off
set logging file /home/wuq/webrtc-local/crash_backtrace.txt
set logging on

# Catch the assertion
catch signal SIGABRT

# Run the program
run

# When it stops, print backtrace
bt full

# Continue and quit
quit

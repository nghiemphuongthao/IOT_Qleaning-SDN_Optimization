import os
import time

def run(cmd):
    print(f"[RUN] {cmd}")
    os.system(cmd)

print("Starting demo IoT traffic...")

# chạy trực tiếp mnexec trong mininet container
run("mnexec -a cloud iperf3 -s -p 5001 -D")
run("mnexec -a cloud iperf3 -s -p 5002 -D")

time.sleep(1)

# UDP flood từ h1
run("mnexec -a h1 iperf3 -u -c 10.0.0.254 -b 60M -t 90 -p 5001")

# TCP từ h2
run("mnexec -a h2 iperf3 -c 10.0.0.254 -t 90 -p 5002")

print("Traffic finished.")

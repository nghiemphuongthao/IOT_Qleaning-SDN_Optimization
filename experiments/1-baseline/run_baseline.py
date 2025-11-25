#!/usr/bin/env python3

import time
import subprocess

def start_docker_environment():
    # Khởi động Docker environment bằng docker-compose
    result = subprocess.run(
        ["docker-compose", "up", "-d"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"Docker-compose error: {result.stderr}")
        return False
    
    print("Docker environment started")
    time.sleep(15)  # Chờ các dịch vụ Docker khởi động
    return True


def run_baseline():
    # Chỉ chạy Docker — không chạy Mininet trong script nữa
    if not start_docker_environment():
        return

    print("Baseline simulation is running inside Docker.")
    print("Waiting for container simulation to finish...")

    # Nếu bạn muốn chờ container tự chạy xong (ví dụ dùng CMD trong Dockerfile)
    # bạn có thể sleep
    time.sleep(60)

    print("Simulation finished. Results should be in ./results inside Docker volume.")


if __name__ == '__main__':
    run_baseline()

#!/usr/bin/env python3

import os
import time
from mininet_topology import create_iot_topology
from traffic_generator import TrafficSimulator
from src.metrics_collector import MetricsCollector
import json

def run_glearning_optimized():
    # Khởi chạy Ryu controller với Q-learning
    ryu_cmd = 'ryu-manager src/ryu_controller/qlearning_controller.py &'
    os.system(ryu_cmd)
    time.sleep(5)  # Đợi controller khởi động

    # Tạo topology
    net = create_iot_topology()

    # Khởi tạo traffic simulator và metrics collector
    traffic_sim = TrafficSimulator(net)
    metrics_collector = MetricsCollector(net)

    # Bắt đầu thu thập metrics
    metrics_collector.start_collection()

    # Bắt đầu mô phỏng lưu lượng với thời gian dài hơn để training
    traffic_sim.start_background_traffic(duration=300)  # 5 phút

    # Chờ cho mô phỏng kết thúc
    time.sleep(300)

    # Dừng thu thập và mô phỏng
    traffic_sim.stop()
    metrics_collector.stop()

    # Lưu kết quả
    with open('results/glearning_optimized/metrics.json', 'w') as f:
        json.dump(metrics_collector.metrics, f)

if __name__ == '__main__':
    run_glearning_optimized()
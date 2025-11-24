#!/usr/bin/env python3

import os
import time
from mininet_topology import create_iot_topology
from traffic_generator import TrafficSimulator
from src.metrics_collector import MetricsCollector

import json

def run_ryu_sdn():
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

    # Bắt đầu mô phỏng lưu lượng
    traffic_sim.start_background_traffic(duration=60)

    # Chờ cho mô phỏng kết thúc
    time.sleep(60)

    # Dừng thu thập và mô phỏng
    traffic_sim.stop()
    metrics_collector.stop()

    # Lưu kết quả
    with open('results/ryu_sdn/metrics.json', 'w') as f:
        json.dump(metrics_collector.metrics, f)

if __name__ == '__main__':
    run_ryu_sdn()
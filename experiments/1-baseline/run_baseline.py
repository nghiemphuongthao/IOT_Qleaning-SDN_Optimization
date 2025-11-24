#!/usr/bin/env python3

from mininet_topology import create_iot_topology
from traffic_generator import TrafficSimulator
from src.metrics_collector import MetricsCollector
import time
import json

def run_baseline():
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
    with open('results/baseline/metrics.json', 'w') as f:
        json.dump(metrics_collector.metrics, f)

if __name__ == '__main__':
    run_baseline()
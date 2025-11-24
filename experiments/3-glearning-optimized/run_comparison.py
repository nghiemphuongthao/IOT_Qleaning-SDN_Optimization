#!/usr/bin/env python3

import json
from src.statistical_analyzer import StatisticalAnalyzer

def load_metrics(file_path):
    with open(file_path, 'r') as f:
        return json.load(f)

def run_comparison():
    # Load kết quả từ các experiments
    baseline_metrics = load_metrics('results/baseline/metrics.json')
    ryu_metrics = load_metrics('results/ryu_sdn/metrics.json')
    glearning_metrics = load_metrics('results/glearning_optimized/metrics.json')

    # So sánh bằng statistical analyzer
    analyzer = StatisticalAnalyzer('results/comparison')

    # So sánh throughput
    baseline_throughput = baseline_metrics['throughput']
    ryu_throughput = ryu_metrics['throughput']
    glearning_throughput = glearning_metrics['throughput']

    # Thực hiện t-test giữa baseline và Q-learning optimized
    t_stat, p_value = analyzer.perform_t_test(baseline_throughput, glearning_throughput)
    print(f"T-test between Baseline and Q-learning: t-statistic={t_stat}, p-value={p_value}")

    # Vẽ biểu đồ so sánh
    metrics_list = [baseline_throughput, ryu_throughput, glearning_throughput]
    labels = ['Baseline', 'RYU SDN', 'Q-learning Optimized']
    analyzer.plot_metrics(metrics_list, labels, 'Throughput Comparison')

if __name__ == '__main__':
    run_comparison()
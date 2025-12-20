import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

def load_scenario_data(scenario_name):
    """Load dữ liệu từ các file CSV"""
    data = []
    for i in range(1, 11):  # h1 đến h10
        file_path = f'shared/raw/{scenario_name}_h{i}.csv'
        df = pd.read_csv(file_path)
        df['host'] = f'h{i}'
        data.append(df)
    return pd.concat(data, ignore_index=True)

def calculate_metrics(df):
    """Tính toán các chỉ số đánh giá"""
    metrics = {
        'avg_latency': df['latency'].mean(),
        'max_latency': df['latency'].max(),
        'std_latency': df['latency'].std(),
        'avg_throughput': df['throughput'].mean(),
        'packet_loss_rate': (df['packets_lost'].sum() / df['packets_sent'].sum()) * 100,
        'jitter': df['latency'].std(),
        'qos_violations': len(df[df['qos_met'] == False])
    }
    return metrics

# Load dữ liệu các kịch bản
no_sdn = load_scenario_data('no_sdn')
sdn_trad = load_scenario_data('sdn_traditional')
sdn_ql = load_scenario_data('sdn_qlearning')

# Tính metrics
metrics_comparison = pd.DataFrame({
    'No SDN': calculate_metrics(no_sdn),
    'SDN Traditional': calculate_metrics(sdn_trad),
    'SDN Q-Learning': calculate_metrics(sdn_ql)
})

print(metrics_comparison)
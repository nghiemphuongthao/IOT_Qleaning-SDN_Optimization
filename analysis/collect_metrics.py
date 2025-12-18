# analysis/collect_metrics.py
import pandas as pd
import os

# Đường dẫn
raw_dir = '../shared/raw'
results_dir = '../shared/results'
os.makedirs(results_dir, exist_ok=True)

# Danh sách cases
cases = ['no_sdn', 'sdn_traditional', 'sdn_qlearning']

# Hàm tính metrics từ CSV (giả định format iperf hoặc ping)
def calculate_metrics(file_path):
    if not os.path.exists(file_path):
        return {'throughput': 0, 'packet_loss': 0, 'rtt': 0}
    
    df = pd.read_csv(file_path)
    # Điều chỉnh dựa trên format thực tế của CSV
    # Ví dụ cho iperf: columns 'Interval', 'Transfer', 'Bitrate', 'Jitter', 'Lost/Total'
    if 'Bitrate' in df.columns:
        throughput = df['Bitrate'].mean()  # Mbps, giả định đơn vị đúng
    else:
        throughput = 0
    
    if 'Lost/Total' in df.columns:
        df['packet_loss'] = df['Lost/Total'].apply(lambda x: int(x.split('/')[0]) / int(x.split('/')[1]) if '/' in x else 0)
        packet_loss = df['packet_loss'].mean() * 100  # %
    else:
        packet_loss = 0
    
    if 'Jitter' in df.columns:
        rtt = df['Jitter'].mean()  # ms, hoặc nếu là RTT từ ping
    elif 'rtt' in df.columns:
        rtt = df['rtt'].mean()
    else:
        rtt = 0
    
    return {'throughput': throughput, 'packet_loss': packet_loss, 'rtt': rtt}

# Thu thập data
summary_data = []
for case in cases:
    for host in range(1, 11):
        file_name = f'{case}_h{host}.csv'
        file_path = os.path.join(raw_dir, file_name)
        metrics = calculate_metrics(file_path)
        metrics['case'] = case
        metrics['host'] = f'h{host}'
        summary_data.append(metrics)

# Lưu summary
summary_df = pd.DataFrame(summary_data)
summary_df.to_csv(os.path.join(results_dir, 'summary.csv'), index=False)
print("Summary metrics collected and saved to summary.csv")
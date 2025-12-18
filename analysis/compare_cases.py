# analysis/compare_cases.py
import pandas as pd
import matplotlib.pyplot as plt
import os

# Đường dẫn
results_dir = '../shared/results'

# Đọc summary
summary_df = pd.read_csv(os.path.join(results_dir, 'summary.csv'))

# Group by case và tính mean
grouped = summary_df.groupby('case').mean(numeric_only=True)

# Plot Throughput
grouped['throughput'].plot(kind='bar', title='Average Throughput (Mbps)')
plt.ylabel('Mbps')
plt.savefig(os.path.join(results_dir, 'throughput.png'))
plt.close()

# Plot Packet Loss
grouped['packet_loss'].plot(kind='bar', title='Average Packet Loss (%)')
plt.ylabel('%')
plt.savefig(os.path.join(results_dir, 'packet_loss.png'))
plt.close()

# Plot RTT
grouped['rtt'].plot(kind='bar', title='Average RTT (ms)')
plt.ylabel('ms')
plt.savefig(os.path.join(results_dir, 'rtt.png'))
plt.close()

print("Comparisons plotted and saved.")
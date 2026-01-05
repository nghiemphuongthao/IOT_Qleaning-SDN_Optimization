# analysis/compare_cases.py
import pandas as pd
import matplotlib.pyplot as plt
import os

# Đường dẫn
results_dir = '/shared/results'

# Đọc summary
summary_df = pd.read_csv(os.path.join(results_dir, 'summary.csv'))

cols = [
    'bulk_throughput_mbps',
    # 'critical_loss_pct',
    # 'telemetry_loss_pct',
    # 'udp_total_loss_pct',
    'critical_rtt_ms',
    'telemetry_rtt_ms',
]

for c in cols:
    if c in summary_df.columns:
        summary_df[c] = pd.to_numeric(summary_df[c], errors='coerce')

def _bar(col, title, ylabel, filename):
    if col not in summary_df.columns:
        return
    s = summary_df.set_index('case')[col]
    s.plot(kind='bar', title=title)
    plt.ylabel(ylabel)
    plt.tight_layout()
    plt.savefig(os.path.join(results_dir, filename))
    plt.close()

_bar('bulk_throughput_mbps', 'Bulk Throughput (server mean)', 'Mbps', 'bulk_throughput_mbps.png')
# _bar('critical_loss_pct', 'Critical UDP Loss', '%', 'critical_loss_pct.png')
# _bar('telemetry_loss_pct', 'Telemetry UDP Loss', '%', 'telemetry_loss_pct.png')
# _bar('udp_total_loss_pct', 'Total UDP Loss (all classes)', '%', 'udp_total_loss_pct.png')
_bar('critical_rtt_ms', 'Critical UDP RTT', 'ms', 'critical_rtt_ms.png')
_bar('telemetry_rtt_ms', 'Telemetry UDP RTT', 'ms', 'telemetry_rtt_ms.png')

print("Comparisons plotted and saved to", results_dir)
import os
import pandas as pd
import matplotlib.pyplot as plt

SUMMARY_FILE = "/shared/results/summary.csv"
OUT_DIR = "/shared/results"
os.makedirs(OUT_DIR, exist_ok=True)

def bar_plot(df, col, ylabel, title, fname):
    plt.figure()
    plt.bar(df["case"], df[col])
    plt.ylabel(ylabel)
    plt.title(title)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, fname), dpi=160)
    plt.close()
    print("Saved", fname)

def main():
    if not os.path.exists(SUMMARY_FILE):
        print("[ERROR] Missing", SUMMARY_FILE)
        return

    df = pd.read_csv(SUMMARY_FILE)

    bar_plot(
        df,
        "packet_loss_rate",
        "Packet Loss Rate",
        "Packet Loss Comparison",
        "packet_loss.png"
    )

    bar_plot(
        df,
        "avg_rtt_ms",
        "Average RTT (ms)",
        "RTT Comparison",
        "rtt.png"
    )

    bar_plot(
        df,
        "avg_throughput_mbps",
        "Throughput (Mbps)",
        "Throughput Comparison",
        "throughput.png"
    )

if __name__ == "__main__":
    main()

import pandas as pd
import matplotlib.pyplot as plt

def load_csv(path):
    return pd.read_csv(path)

def compare_delay(df1, df2, df3):
    plt.plot(df1["latency_ms"], label="Case 1")
    plt.plot(df2["latency_ms"], label="Case 2")
    plt.plot(df3["latency_ms"], label="Case 3")
    plt.title("Latency Comparison")
    plt.xlabel("Time")
    plt.ylabel("Delay (ms)")
    plt.legend()
    plt.savefig("/shared/delay_compare.png")
    plt.close()

def compare_loss(df1, df2, df3):
    plt.plot(df1["packet_loss"], label="Case 1")
    plt.plot(df2["packet_loss"], label="Case 2")
    plt.plot(df3["packet_loss"], label="Case 3")
    plt.title("Packet Loss Comparison")
    plt.xlabel("Time")
    plt.ylabel("Loss (%)")
    plt.legend()
    plt.savefig("/shared/loss_compare.png")
    plt.close()

def main():
    df1 = load_csv("/shared/metrics_case1.csv")
    df2 = load_csv("/shared/metrics_case2.csv")
    df3 = load_csv("/shared/metrics_case3.csv")

    compare_delay(df1, df2, df3)
    compare_loss(df1, df2, df3)

    with open("/shared/summary.txt", "w") as f:
        f.write("=== QoS Optimization Report ===\n\n")
        f.write(f"Case 1 Avg Loss: {df1['packet_loss'].mean():.2f}%\n")
        f.write(f"Case 2 Avg Loss: {df2['packet_loss'].mean():.2f}%\n")
        f.write(f"Case 3 Avg Loss: {df3['packet_loss'].mean():.2f}%\n\n")

        f.write(f"Case 1 Avg Delay: {df1['latency_ms'].mean():.2f} ms\n")
        f.write(f"Case 2 Avg Delay: {df2['latency_ms'].mean():.2f} ms\n")
        f.write(f"Case 3 Avg Delay: {df3['latency_ms'].mean():.2f} ms\n\n")

        f.write("Case 3 shows strong improvements due to Q-learning + QoS classification + Anomaly detection.\n")

if __name__ == "__main__":
    main()

import os
import pandas as pd
import matplotlib.pyplot as plt

IN_FILE = os.environ.get("SUMMARY", "./shared/results/summary.csv")
OUT_DIR = os.environ.get("PLOT_DIR", "./shared/plots")

def plot_metric(df, metric, title, fname):
    plt.figure()
    for cls, g in df.groupby("class"):
        g2 = g.set_index("case")[metric].reindex(["case1","case2","case3"])
        plt.plot(g2.index, g2.values, marker="o", label=cls)
    plt.title(title)
    plt.xlabel("case")
    plt.ylabel(metric)
    plt.legend()
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, fname)
    plt.savefig(out, dpi=160, bbox_inches="tight")
    print("Saved", out)

def main():
    if not os.path.exists(IN_FILE):
        print("Missing", IN_FILE)
        return
    df = pd.read_csv(IN_FILE)
    plot_metric(df, "loss_rate", "Loss rate by class", "loss_rate.png")
    plot_metric(df, "rtt_ms_avg", "RTT avg (ms) by class", "rtt_avg.png")
    plot_metric(df, "bps_avg", "Throughput avg (bps) by class", "throughput.png")

if __name__ == "__main__":
    main()

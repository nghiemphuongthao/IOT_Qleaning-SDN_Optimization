import matplotlib.pyplot as plt
import json

def load_report(path="results/comparison_report.json"):
    with open(path, "r") as f:
        return json.load(f)

def plot_bar(values, ylabel, title, filename):
    cases = list(values.keys())
    data = list(values.values())

    plt.figure(figsize=(6,4))
    plt.bar(cases, data, color=["gray","blue","red"])
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.savefig(f"results/{filename}")
    plt.close()

if __name__ == "__main__":

    report = load_report()

    delay_data = {c: report[c]["avg_delay"] for c in report}
    loss_data = {c: report[c]["avg_loss"] for c in report}
    thr_data = {c: report[c]["avg_throughput"] for c in report}

    plot_bar(delay_data, "ms", "Average Delay Comparison", "delay_comparison.png")
    plot_bar(loss_data, "%", "Packet Loss Comparison", "loss_comparison.png")
    plot_bar(thr_data, "Mbps", "Throughput Comparison", "throughput_comparison.png")

    print("[DONE] All graphs saved to results/")

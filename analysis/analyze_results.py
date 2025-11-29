import json
import numpy as np
import matplotlib.pyplot as plt
import os

def load_traffic_log(path):
    delays = []
    losses = []
    throughput = []

    with open(path, "r") as f:
        for line in f:
            if "rtt" in line:  # ping
                try:
                    delay = float(line.split("time=")[1].split(" ms")[0])
                    delays.append(delay)
                except:
                    pass

            if "packet loss" in line:
                try:
                    loss = float(line.split("%")[0].split()[-1])
                    losses.append(loss)
                except:
                    pass

            if "iperf" in line and "bits/sec" in line:
                try:
                    value = float(line.split()[-3])  # Mbps
                    throughput.append(value)
                except:
                    pass

    return delays, losses, throughput

def summarize_case(case_name, path):
    delay, loss, thr = load_traffic_log(path)

    summary = {
        "case": case_name,
        "avg_delay": np.mean(delay) if delay else 0,
        "max_delay": np.max(delay) if delay else 0,
        "avg_loss": np.mean(loss) if loss else 0,
        "avg_throughput": np.mean(thr) if thr else 0,
    }

    return summary

def save_summary(result, output_path):
    with open(output_path, "w") as f:
        json.dump(result, f, indent=4)
    print("[OK] Saved:", output_path)

if __name__ == "__main__":

    results = {}
    base = "results"

    results["baseline"] = summarize_case(
        "baseline", f"{base}/baseline/baseline_traffic.log"
    )
    results["sdn"] = summarize_case(
        "sdn", f"{base}/sdn/sdn_traffic.log"
    )
    results["sdn_qlearn"] = summarize_case(
        "sdn_qlearn", f"{base}/sdn_qlearning/sdn-qlearning_traffic.log"
    )

    save_summary(results, "results/comparison_report.json")
    print(json.dumps(results, indent=4))

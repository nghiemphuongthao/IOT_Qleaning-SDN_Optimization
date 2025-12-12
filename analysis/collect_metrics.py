import os
import glob
import pandas as pd

RAW_DIR = "./shared/raw"
OUT_DIR = "./shared/results"
os.makedirs(OUT_DIR, exist_ok=True)

def parse_ping(file_path):
    """
    Parse ping output CSV
    Expected column: time_ms
    """
    df = pd.read_csv(file_path)
    avg_delay = df["time_ms"].mean()
    loss = 100 * (1 - len(df) / df["seq"].max())
    return avg_delay, loss

def parse_iperf(file_path):
    """
    Parse iperf CSV
    Expected column: bandwidth_mbps
    """
    df = pd.read_csv(file_path)
    return df["bandwidth_mbps"].mean()

def collect_case(case_id):
    delay_list = []
    loss_list = []
    throughput_list = []

    # ---------- CLIENT LOGS ----------
    client_files = glob.glob(
        f"{RAW_DIR}/case{case_id}_client_*.csv"
    )

    for f in client_files:
        d, l = parse_ping(f)
        delay_list.append(d)
        loss_list.append(l)

    # ---------- SERVER LOG ----------
    server_file = f"{RAW_DIR}/case{case_id}_server.csv"
    if os.path.exists(server_file):
        t = parse_iperf(server_file)
        throughput_list.append(t)

    return (
        sum(delay_list) / len(delay_list),
        sum(loss_list) / len(loss_list),
        sum(throughput_list) / len(throughput_list)
    )

def main():
    results = []

    for case_id in [0, 1, 2]:
        try:
            delay, loss, thr = collect_case(case_id)
            results.append({
                "case": case_id,
                "avg_delay_ms": round(delay, 2),
                "packet_loss_percent": round(loss, 2),
                "throughput_mbps": round(thr, 2)
            })
            print(f"[OK] Case {case_id} collected")
        except Exception as e:
            print(f"[WARN] Case {case_id} skipped:", e)

    df = pd.DataFrame(results)
    df.to_csv(f"{OUT_DIR}/summary.csv", index=False)
    print(f"\nSaved to {OUT_DIR}/summary.csv")

if __name__ == "__main__":
    main()

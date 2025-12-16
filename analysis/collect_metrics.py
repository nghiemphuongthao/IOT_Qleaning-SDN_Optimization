import os
import glob
import pandas as pd

# ====== ĐƯỜNG DẪN ĐÚNG TRONG CONTAINER ======
RAW_DIR = "/shared/raw"
OUT_DIR = "/shared/results"
os.makedirs(OUT_DIR, exist_ok=True)

def analyze_case(case_name):
    files = glob.glob(f"{RAW_DIR}/{case_name}_*.csv")
    if not files:
        print(f"[WARN] No CSV found for {case_name}")
        return None

    df_all = []
    for f in files:
        try:
            df_all.append(pd.read_csv(f))
        except Exception as e:
            print(f"[WARN] Cannot read {f}: {e}")

    if not df_all:
        return None

    df = pd.concat(df_all, ignore_index=True)

    # ===== UDP (telemetry + critical) =====
    udp_df = df[df["class"].isin(["telemetry", "critical"])]

    sent = udp_df["sent"].sum()
    lost = udp_df["lost"].sum()
    loss_rate = lost / sent if sent > 0 else None

    rtt_df = udp_df[udp_df["rtt_ms"].notna()]
    avg_rtt = rtt_df["rtt_ms"].mean() if not rtt_df.empty else None

    # ===== TCP BULK =====
    tcp_df = df[df["class"] == "bulk"]
    avg_throughput = tcp_df["bps"].mean() / 1e6 if not tcp_df.empty else None

    return {
        "case": case_name,
        "packet_loss_rate": loss_rate,
        "avg_rtt_ms": avg_rtt,
        "avg_throughput_mbps": avg_throughput
    }

def main():
    cases = ["no_sdn", "sdn_traditional", "sdn_qlearning"]
    results = []

    for c in cases:
        res = analyze_case(c)
        if res:
            results.append(res)
            print(f"[OK] Collected {c}")

    if not results:
        print("[ERROR] No data collected")
        return

    df = pd.DataFrame(results)
    df["packet_loss_rate"] = df["packet_loss_rate"].round(4)
    df["avg_rtt_ms"] = df["avg_rtt_ms"].round(2)
    df["avg_throughput_mbps"] = df["avg_throughput_mbps"].round(2)

    out = f"{OUT_DIR}/summary.csv"
    df.to_csv(out, index=False)

    print("\n=== SUMMARY ===")
    print(df)
    print(f"\nSaved to {out}")

if __name__ == "__main__":
    main()

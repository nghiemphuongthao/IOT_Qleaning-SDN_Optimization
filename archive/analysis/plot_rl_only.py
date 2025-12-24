from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

RAW_DIR = Path("/shared/raw")
OUT_DIR = Path("/shared/results")
OUT_DIR.mkdir(parents=True, exist_ok=True)

files = sorted(RAW_DIR.glob("sdn_qlearning_*.csv"))
if not files:
    raise SystemExit("Không tìm thấy file shared/raw/sdn_qlearning_*.csv")

dfs = []
for f in files:
    df = pd.read_csv(f)
    # format: ts,class,rtt_ms,lost,sent,bps
    df = df[df["class"] == "bulk"].copy()
    if df.empty:
        continue
    df["ts"] = pd.to_numeric(df["ts"], errors="coerce")
    df["bps"] = pd.to_numeric(df["bps"], errors="coerce")
    df = df.dropna(subset=["ts","bps"])
    df["mbps"] = df["bps"] / 1e6
    df["host"] = f.stem.replace("sdn_qlearning_", "")
    dfs.append(df[["ts","mbps","host"]])

if not dfs:
    raise SystemExit("Không có dòng class=bulk trong các file raw.")

all_df = pd.concat(dfs, ignore_index=True)

# gộp theo thời gian: lấy tổng bulk qua các host ở cùng thời điểm (gần đúng theo window)
bulk_ts = all_df.groupby("ts", as_index=False)["mbps"].sum().sort_values("ts")

t0 = bulk_ts["ts"].min()
bulk_ts["t"] = bulk_ts["ts"] - t0  # thời gian tương đối (giây)

plt.figure()
plt.plot(bulk_ts["t"], bulk_ts["mbps"])
plt.xlabel("Thời gian (giây)")
plt.ylabel("Thông lượng bulk (Mb/s)")
plt.title("Hình 7. Thông lượng luồng nền (bulk) theo thời gian – Case 3")
out = OUT_DIR / "H7_bulk_throughput_time.png"
plt.savefig(out, dpi=200, bbox_inches="tight")
plt.close()

print("Saved:", out)

from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ===== Xác định thư mục shared =====
# Nếu chạy trong container (mount ./shared:/shared)
if Path("/shared").exists():
    SHARED = Path("/shared")
else:
    SHARED = Path("shared")

LOG_CSV = SHARED / "logs" / "qlearning_log.csv"
QTABLE_CSV = SHARED / "logs" / "qtable.csv"
RAW_DIR = SHARED / "raw"
OUT_DIR = SHARED / "results"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ===== Kiểm tra dữ liệu =====
assert LOG_CSV.exists(), f"Không tìm thấy {LOG_CSV}"
assert QTABLE_CSV.exists(), f"Không tìm thấy {QTABLE_CSV}"
assert RAW_DIR.exists(), f"Không tìm thấy {RAW_DIR}"

# ===============================
# ĐỌC LOG Q-LEARNING
# ===============================
qlog = pd.read_csv(LOG_CSV)
for c in ["step", "state", "action", "reward", "epsilon"]:
    qlog[c] = pd.to_numeric(qlog[c], errors="coerce")
qlog = qlog.dropna(subset=["step"]).sort_values("step")

# ===============================
# HÌNH 1: ACTION THEO STEP
# ===============================
plt.figure()
plt.plot(qlog["step"], qlog["action"])
plt.xlabel("Bước học")
plt.ylabel("Hành động")
plt.title("Hình 1. Diễn biến hành động theo bước học (Case 3)")
plt.savefig(OUT_DIR / "H1_action_step.png", dpi=300, bbox_inches="tight")
plt.close()

# ===============================
# HÌNH 3: REWARD THEO STEP
# ===============================
plt.figure()
plt.plot(qlog["step"], qlog["reward"])
plt.xlabel("Bước học")
plt.ylabel("Phần thưởng")
plt.title("Hình 3. Diễn biến phần thưởng theo bước học (Case 3)")
plt.savefig(OUT_DIR / "H3_reward_step.png", dpi=300, bbox_inches="tight")
plt.close()

# ===============================
# HÌNH 4: EPSILON THEO STEP
# ===============================
plt.figure()
plt.plot(qlog["step"], qlog["epsilon"])
plt.xlabel("Bước học")
plt.ylabel("Hệ số thăm dò ε")
plt.title("Hình 4. Suy giảm hệ số thăm dò theo bước học (Case 3)")
plt.savefig(OUT_DIR / "H4_epsilon_step.png", dpi=300, bbox_inches="tight")
plt.close()

# ===============================
# HÌNH 7: THÔNG LƯỢNG BULK THEO THỜI GIAN
# ===============================
bulk_frames = []

for f in RAW_DIR.glob("sdn_qlearning_*.csv"):
    df = pd.read_csv(f)
    if "class" not in df.columns:
        continue
    bulk = df[df["class"] == "bulk"].copy()
    if bulk.empty:
        continue
    bulk["ts"] = pd.to_numeric(bulk["ts"], errors="coerce")
    bulk["bps"] = pd.to_numeric(bulk["bps"], errors="coerce")
    bulk = bulk.dropna(subset=["ts", "bps"])
    bulk["mbps"] = bulk["bps"] / 1e6
    bulk_frames.append(bulk[["ts", "mbps"]])

if bulk_frames:
    bulk_all = pd.concat(bulk_frames)
    bulk_ts = bulk_all.groupby("ts", as_index=False)["mbps"].sum()
    t0 = bulk_ts["ts"].min()
    bulk_ts["t"] = bulk_ts["ts"] - t0

    plt.figure()
    plt.plot(bulk_ts["t"], bulk_ts["mbps"])
    plt.xlabel("Thời gian (giây)")
    plt.ylabel("Thông lượng bulk (Mb/s)")
    plt.title("Hình 7. Thông lượng luồng nền (bulk) theo thời gian (Case 3)")
    plt.savefig(OUT_DIR / "H7_bulk_throughput.png", dpi=300, bbox_inches="tight")
    plt.close()

# ===============================
# HÌNH 8: HEATMAP Q-TABLE
# ===============================
qtab = pd.read_csv(QTABLE_CSV)
states = qtab.iloc[:, 0].astype(int).to_list()
values = qtab.iloc[:, 1:].apply(pd.to_numeric, errors="coerce").values

plt.figure()
plt.imshow(values)
plt.xticks(range(values.shape[1]), range(values.shape[1]))
plt.yticks(range(values.shape[0]), states)
plt.xlabel("Hành động")
plt.ylabel("Trạng thái")
plt.title("Hình 8. Bản đồ nhiệt bảng giá trị Q (Case 3)")
plt.colorbar(label="Giá trị Q")
plt.savefig(OUT_DIR / "H8_qtable_heatmap.png", dpi=300, bbox_inches="tight")
plt.close()

print("ĐÃ VẼ XONG 5 HÌNH →", OUT_DIR)

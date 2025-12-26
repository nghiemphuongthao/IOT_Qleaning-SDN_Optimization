from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

shared = Path("/shared")
outdir = shared / "results"
outdir.mkdir(parents=True, exist_ok=True)

f = shared / "logs" / "qlearning_log.csv"
df = pd.read_csv(f)

for c in ["step","state","action","reward","load","drops","epsilon","max_q"]:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")

df = df.dropna(subset=["step"]).sort_values("step")

imgs = []

def save(fig, name):
    p = outdir / name
    fig.savefig(p, dpi=200, bbox_inches="tight")
    imgs.append(p)
    plt.close(fig)

fig = plt.figure()
plt.plot(df["step"], df["epsilon"])
plt.xlabel("Step"); plt.ylabel("Epsilon"); plt.title("Epsilon decay")
save(fig, "rl_epsilon.png")

fig = plt.figure()
plt.plot(df["step"], df["reward"])
plt.xlabel("Step"); plt.ylabel("Reward"); plt.title("Reward over steps")
save(fig, "rl_reward.png")

fig = plt.figure()
plt.plot(df["step"], df["state"])
plt.xlabel("Step"); plt.ylabel("State"); plt.title("State over steps")
save(fig, "rl_state.png")

fig = plt.figure()
plt.plot(df["step"], df["action"])
plt.xlabel("Step"); plt.ylabel("Action (qid)"); plt.title("Chosen qid over steps")
save(fig, "rl_action.png")

fig = plt.figure()
plt.plot(df["step"], df["load"])
plt.xlabel("Step"); plt.ylabel("Load (bytes/s)"); plt.title("Observed load")
save(fig, "rl_load.png")

if "rtt_ms" in df.columns:
    fig = plt.figure()
    plt.plot(df["step"], df["rtt_ms"])
    plt.xlabel("Step"); plt.ylabel("RTT (ms)"); plt.title("Critical RTT observed (from raw)")
    save(fig, "rl_rtt.png")

pdf_path = outdir / "rl_figures.pdf"
with PdfPages(pdf_path) as pdf:
    for p in imgs:
        img = plt.imread(p)
        fig = plt.figure()
        plt.imshow(img); plt.axis("off")
        pdf.savefig(bbox_inches="tight")
        plt.close(fig)

print("Saved:", pdf_path)

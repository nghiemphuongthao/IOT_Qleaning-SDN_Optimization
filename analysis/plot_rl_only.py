import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

LOG = Path("qlearning_log.csv")
OUT = Path("shared/results")
OUT.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(LOG)
for c in ["step","state","action","reward","load","epsilon"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")
df = df.dropna(subset=["step"]).sort_values("step")

# 1) epsilon
plt.figure()
plt.plot(df["step"], df["epsilon"])
plt.xlabel("Step"); plt.ylabel("Epsilon"); plt.title("Epsilon decay")
plt.savefig(OUT/"rl_epsilon.png", dpi=200, bbox_inches="tight")
plt.close()

# 2) reward
plt.figure()
plt.plot(df["step"], df["reward"])
plt.xlabel("Step"); plt.ylabel("Reward"); plt.title("Reward over steps")
plt.savefig(OUT/"rl_reward.png", dpi=200, bbox_inches="tight")
plt.close()

# 3) action
plt.figure()
plt.plot(df["step"], df["action"])
plt.xlabel("Step"); plt.ylabel("Action (qid index)"); plt.title("Chosen action over steps")
plt.savefig(OUT/"rl_action.png", dpi=200, bbox_inches="tight")
plt.close()

# 4) load + state
plt.figure()
plt.plot(df["step"], df["load"])
plt.xlabel("Step"); plt.ylabel("Load (bytes/s)"); plt.title("Observed load over steps")
plt.savefig(OUT/"rl_load.png", dpi=200, bbox_inches="tight")
plt.close()

plt.figure()
plt.plot(df["step"], df["state"])
plt.xlabel("Step"); plt.ylabel("State"); plt.title("State over steps")
plt.savefig(OUT/"rl_state.png", dpi=200, bbox_inches="tight")
plt.close()

print("Saved to shared/results/*.png")

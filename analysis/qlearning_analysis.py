import os
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


def main():
    shared = Path(os.environ.get("SHARED_DIR", "/shared"))
    raw_dir = shared / "raw"
    out_dir = shared / "results"
    out_dir.mkdir(parents=True, exist_ok=True)

    log_path = raw_dir / "qlearning_agent_log.csv"
    if not log_path.exists():
        print("Q-learning log not found:", log_path)
        return

    df = pd.read_csv(log_path, engine="python", on_bad_lines="skip")
    if df.empty:
        print("Q-learning log is empty:", log_path)
        return

    for c in ["ts", "step", "state", "action", "out_port", "epsilon", "max_load_bps", "total_drops", "reward"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df.sort_values("step")

    # Save a cleaned version for reproducibility
    cleaned_path = out_dir / "qlearning_agent_log_cleaned.csv"
    df.to_csv(cleaned_path, index=False)

    # Epsilon over time
    if "epsilon" in df.columns and "step" in df.columns:
        plt.figure()
        plt.plot(df["step"], df["epsilon"], linewidth=1)
        plt.title("Q-learning Epsilon Decay")
        plt.xlabel("Step")
        plt.ylabel("Epsilon")
        plt.tight_layout()
        plt.savefig(out_dir / "qlearning_epsilon.png")
        plt.close()

    # Reward trend (reward is only present once a previous step exists for a key)
    if "reward" in df.columns and "step" in df.columns:
        plt.figure()
        r = df["reward"].dropna()
        if not r.empty:
            r2 = df[["step", "reward"]].copy()
            r2["reward"] = pd.to_numeric(r2["reward"], errors="coerce")
            r2 = r2.dropna(subset=["reward"])
            r2["reward_ma"] = r2["reward"].rolling(window=10, min_periods=1).mean()
            plt.plot(r2["step"], r2["reward"], alpha=0.35, linewidth=1, label="reward")
            plt.plot(r2["step"], r2["reward_ma"], linewidth=2, label="reward (MA10)")
            plt.title("Q-learning Reward Trend")
            plt.xlabel("Step")
            plt.ylabel("Reward")
            plt.legend()
            plt.tight_layout()
            plt.savefig(out_dir / "qlearning_reward.png")
        plt.close()

    # Action distribution overall
    if "action" in df.columns:
        plt.figure()
        df["action"].value_counts(dropna=True).sort_index().plot(kind="bar")
        plt.title("Q-learning Action Distribution")
        plt.xlabel("Action")
        plt.ylabel("Count")
        plt.tight_layout()
        plt.savefig(out_dir / "qlearning_action_distribution.png")
        plt.close()

    # Out port distribution overall
    if "out_port" in df.columns:
        plt.figure()
        df["out_port"].value_counts(dropna=True).sort_index().plot(kind="bar")
        plt.title("Chosen Output Port Distribution")
        plt.xlabel("Out port")
        plt.ylabel("Count")
        plt.tight_layout()
        plt.savefig(out_dir / "qlearning_out_port_distribution.png")
        plt.close()

    # State distribution
    if "state" in df.columns:
        plt.figure()
        df["state"].value_counts(dropna=True).sort_index().plot(kind="bar")
        plt.title("Observed Congestion State Distribution")
        plt.xlabel("State")
        plt.ylabel("Count")
        plt.tight_layout()
        plt.savefig(out_dir / "qlearning_state_distribution.png")
        plt.close()

    # Simple summary table
    summary = {
        "steps": int(df["step"].max()) if "step" in df.columns and df["step"].notna().any() else len(df),
        "epsilon_final": float(df["epsilon"].dropna().iloc[-1]) if "epsilon" in df.columns and df["epsilon"].dropna().any() else None,
        "reward_mean": float(df["reward"].dropna().mean()) if "reward" in df.columns and df["reward"].dropna().any() else None,
        "reward_min": float(df["reward"].dropna().min()) if "reward" in df.columns and df["reward"].dropna().any() else None,
        "reward_max": float(df["reward"].dropna().max()) if "reward" in df.columns and df["reward"].dropna().any() else None,
    }
    pd.DataFrame([summary]).to_csv(out_dir / "qlearning_summary.csv", index=False)

    print("Saved Q-learning analysis outputs to", out_dir)


if __name__ == "__main__":
    main()

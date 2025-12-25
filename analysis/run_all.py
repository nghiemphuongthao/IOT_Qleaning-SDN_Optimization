import subprocess
import sys
from pathlib import Path


def main():
    steps = [
        [sys.executable, "collect_metrics.py"],
        [sys.executable, "compare_cases.py"],
    ]

    shared = Path("/shared")
    qlog = shared / "raw" / "qlearning_agent_log.csv"
    if qlog.exists():
        steps.append([sys.executable, "qlearning_analysis.py"])

    for cmd in steps:
        print("Running:", " ".join(cmd))
        subprocess.check_call(cmd)


if __name__ == "__main__":
    main()

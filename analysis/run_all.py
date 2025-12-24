import subprocess
import sys


def main():
    steps = [
        [sys.executable, "collect_metrics.py"],
        [sys.executable, "compare_cases.py"],
    ]

    for cmd in steps:
        print("Running:", " ".join(cmd))
        subprocess.check_call(cmd)


if __name__ == "__main__":
    main()

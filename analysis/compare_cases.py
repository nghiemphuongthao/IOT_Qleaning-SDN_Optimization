import os, pandas as pd, matplotlib.pyplot as plt

def load_results(case):
    p = f"../shared/results/{case}.csv"
    if os.path.exists(p):
        return pd.read_csv(p)
    return None

def compare():
    for case in ["case1","case2","case3"]:
        df = load_results(case)
        if df is not None:
            plt.plot(df['time'], df['throughput'], label=case)
    plt.legend()
    plt.xlabel('time')
    plt.ylabel('throughput')
    plt.savefig('../shared/results/compare_throughput.png')

if __name__ == '__main__':
    compare()

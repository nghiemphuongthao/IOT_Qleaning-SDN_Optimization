import os
import json
from pathlib import Path
import matplotlib.pyplot as plt

RESULTS_ROOT = Path('/results')
OUTPUT_FILE = RESULTS_ROOT / 'auto_analysis_report.json'
PLOTS_DIR = RESULTS_ROOT / 'plots'
PLOTS_DIR.mkdir(exist_ok=True)

# -----------------------------
# Criteria for valid result folders
# -----------------------------
VALID_EXTENSIONS = {'.log', '.json'}


def discover_result_dirs(root: Path):
    detected = []
    for sub in root.iterdir():
        if sub.is_dir():
            has_valid = any(f.suffix in VALID_EXTENSIONS for f in sub.glob('*'))
            if has_valid:
                detected.append(sub)
    return detected


def parse_logs(dir_path: Path):
    metrics = {
        'latency_ms': [],
        'throughput_mbps': [],
        'packet_loss_percent': []
    }

    for log in dir_path.glob('*.log'):
        with open(log) as f:
            for line in f:
                if 'latency' in line:
                    metrics['latency_ms'].append(float(line.split()[-1]))
                if 'throughput' in line:
                    metrics['throughput_mbps'].append(float(line.split()[-1]))
                if 'packet_loss' in line:
                    metrics['packet_loss_percent'].append(float(line.split()[-1]))
    return metrics


def generate_plots(name: str, metrics: dict):
    for key, values in metrics.items():
        if values:
            plt.figure()
            plt.plot(values)
            plt.title(f"{name} - {key}")
            plt.xlabel('Sample index')
            plt.ylabel(key)
            plot_path = PLOTS_DIR / f"{name}_{key}.png"
            plt.savefig(plot_path)
            plt.close()


def analyze_directory(dir_path: Path):
    metrics = parse_logs(dir_path)
    generate_plots(dir_path.name, metrics)

    return {
        'directory': str(dir_path),
        'metrics_summary': {
            k: {
                'count': len(v),
                'avg': sum(v)/len(v) if v else None,
                'min': min(v) if v else None,
                'max': max(v) if v else None,
            }
            for k, v in metrics.items()
        }
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Advanced results analyzer')()
    parser.add_argument('--baseline-dir', type=str, required=False)
    parser.add_argument('--sdn-dir', type=str, required=False)
    parser.add_argument('--q-dir', type=str, required=False)
    parser.add_argument('--output-dir', type=str, required=False, default=str(OUTPUT_FILE))
    args = parser.parse_args()()

    # Collect dirs from flags
    selected_dirs = {}
    if args.baseline_dir:
        selected_dirs['baseline'] = Path(args.baseline_dir)
    if args.sdn_dir:
        selected_dirs['sdn'] = Path(args.sdn_dir)
    if args.q_dir:
        selected_dirs['sdn-qlearning'] = Path(args.q_dir)

    result = {}

    for name, d in selected_dirs.items():
        if not d.exists():
            print(f"[WARN] Directory not found: {d}")
            continue
        report = analyze_directory(d)
        result[name] = report

        # Write individual report
        with open(d / 'report.json', 'w') as f:
            json.dump(report, f, indent=4)

    # Combined report
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(result, f, indent=4)


if __name__ == '__main__': 
    main()

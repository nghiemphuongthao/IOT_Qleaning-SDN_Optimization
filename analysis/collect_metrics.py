import time
import zmq
import csv
import json
import psutil
from datetime import datetime

METRICS_FILE = "/shared/metrics_case3.csv"

def write_header():
    with open(METRICS_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp",
            "cpu_usage",
            "ram_usage",
            "qos_class_0_load",
            "qos_class_1_load",
            "qos_class_2_load",
            "latency_ms",
            "packet_loss",
            "reward",
            "selected_action",
            "anomaly_flag"
        ])

def connect_zmq():
    ctx = zmq.Context()
    sub = ctx.socket(zmq.SUB)
    sub.connect("tcp://ryu-controller:6000")
    sub.setsockopt_string(zmq.SUBSCRIBE, "")
    return sub

def main():
    write_header()
    sub = connect_zmq()

    print("[ANALYSIS] Listening for metrics...")

    while True:
        try:
            msg = sub.recv_string()
            data = json.loads(msg)

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory().percent

            row = [
                timestamp,
                cpu,
                ram,
                data.get("qos0", 0),
                data.get("qos1", 0),
                data.get("qos2", 0),
                data.get("latency", 0),
                data.get("loss", 0),
                data.get("reward", 0),
                data.get("action", -1),
                data.get("anomaly", 0)
            ]

            with open(METRICS_FILE, "a", newline="") as f:
                csv.writer(f).writerow(row)

            print("[METRIC]", row)

        except Exception as e:
            print("Error:", e)
            time.sleep(1)

if __name__ == "__main__":
    main()
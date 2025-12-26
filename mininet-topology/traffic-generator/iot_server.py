import argparse, socket, threading, time, csv, os
from threading import Lock

CRIT_UDP = int(os.environ.get("CRIT_UDP", "5001"))
TEL_UDP  = int(os.environ.get("TEL_UDP", "5002"))
BULK_TCP = int(os.environ.get("BULK_TCP", "5003"))

def udp_echo_server(bind_ip, port, label, counters, lock: Lock):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((bind_ip, port))
    while True:
        data, addr = s.recvfrom(2048)
        with lock:
            counters[label]["rx"] += 1
        try:
            s.sendto(data, addr)
            with lock:
                counters[label]["tx"] += 1
        except Exception:
            pass

def tcp_sink_server(bind_ip, port, counters, lock: Lock):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((bind_ip, port))
    s.listen(64)
    while True:
        conn, _ = s.accept()
        conn.settimeout(1.0)
        with lock:
            counters["bulk"]["conn"] += 1
        try:
            while True:
                data = conn.recv(65536)
                if not data:
                    break
                with lock:
                    counters["bulk"]["bytes"] += len(data)
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass

def writer(out_path, counters, lock: Lock):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    # previous snapshot for rate calculation
    prev = {
        "ts": time.time(),
        "critical_rx": 0, "critical_tx": 0,
        "telemetry_rx": 0, "telemetry_tx": 0,
        "bulk_conn": 0, "bulk_bytes": 0
    }

    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "ts",
            "class",
            "rx_pkts", "tx_pkts",
            "rx_pps", "tx_pps",
            "bulk_conns", "bulk_bytes",
            "bulk_mbps"
        ])

        while True:
            time.sleep(1)
            ts = time.time()

            with lock:
                c_rx = counters["critical"]["rx"]
                c_tx = counters["critical"]["tx"]
                t_rx = counters["telemetry"]["rx"]
                t_tx = counters["telemetry"]["tx"]
                b_conn = counters["bulk"]["conn"]
                b_bytes = counters["bulk"]["bytes"]

            dt = max(1e-6, ts - prev["ts"])

            c_rx_pps = (c_rx - prev["critical_rx"]) / dt
            c_tx_pps = (c_tx - prev["critical_tx"]) / dt
            t_rx_pps = (t_rx - prev["telemetry_rx"]) / dt
            t_tx_pps = (t_tx - prev["telemetry_tx"]) / dt

            bulk_bytes_delta = (b_bytes - prev["bulk_bytes"])
            bulk_mbps = (bulk_bytes_delta * 8.0) / (dt * 1e6)

            # Write rows (cumulative + per-second rate)
            w.writerow([ts, "critical",  c_rx, c_tx, round(c_rx_pps, 2), round(c_tx_pps, 2), "", "", ""])
            w.writerow([ts, "telemetry", t_rx, t_tx, round(t_rx_pps, 2), round(t_tx_pps, 2), "", "", ""])
            w.writerow([ts, "bulk", "", "", "", "", b_conn, b_bytes, round(bulk_mbps, 3)])

            f.flush()

            prev["ts"] = ts
            prev["critical_rx"] = c_rx
            prev["critical_tx"] = c_tx
            prev["telemetry_rx"] = t_rx
            prev["telemetry_tx"] = t_tx
            prev["bulk_conn"] = b_conn
            prev["bulk_bytes"] = b_bytes

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bind", default="0.0.0.0", help="IP address to bind (e.g., 10.0.100.2 or 0.0.0.0)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    counters = {
        "critical": {"rx": 0, "tx": 0},
        "telemetry": {"rx": 0, "tx": 0},
        "bulk": {"conn": 0, "bytes": 0},
    }

    lock = Lock()

    threading.Thread(target=udp_echo_server, args=(args.bind, CRIT_UDP, "critical", counters, lock), daemon=True).start()
    threading.Thread(target=udp_echo_server, args=(args.bind, TEL_UDP, "telemetry", counters, lock), daemon=True).start()
    threading.Thread(target=tcp_sink_server, args=(args.bind, BULK_TCP, counters, lock), daemon=True).start()

    print(f"[SERVER] bind={args.bind} UDP:{CRIT_UDP}/{TEL_UDP} TCP:{BULK_TCP} out={args.out}")
    writer(args.out, counters, lock)

if __name__ == "__main__":
    main()

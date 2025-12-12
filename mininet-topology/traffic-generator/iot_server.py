import argparse, socket, threading, time, csv, os

CRIT_UDP = int(os.environ.get("CRIT_UDP", "5001"))
TEL_UDP  = int(os.environ.get("TEL_UDP", "5002"))
BULK_TCP = int(os.environ.get("BULK_TCP", "5003"))

def udp_echo_server(port, label, counters):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("0.0.0.0", port))
    while True:
        data, addr = s.recvfrom(2048)
        counters[label]["rx"] += 1
        try:
            s.sendto(data, addr)
            counters[label]["tx"] += 1
        except Exception:
            pass

def tcp_sink_server(port, counters):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", port))
    s.listen(64)
    while True:
        conn, _ = s.accept()
        conn.settimeout(1.0)
        counters["bulk"]["conn"] += 1
        try:
            while True:
                data = conn.recv(65536)
                if not data:
                    break
                counters["bulk"]["bytes"] += len(data)
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass

def writer(out_path, counters):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts","class","rx_pkts","tx_pkts","bulk_conns","bulk_bytes"])
        while True:
            ts = time.time()
            w.writerow([ts,"critical",counters["critical"]["rx"],counters["critical"]["tx"],"", ""])
            w.writerow([ts,"telemetry",counters["telemetry"]["rx"],counters["telemetry"]["tx"],"", ""])
            w.writerow([ts,"bulk","", "", counters["bulk"]["conn"], counters["bulk"]["bytes"]])
            f.flush()
            time.sleep(1)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    counters = {
        "critical": {"rx":0,"tx":0},
        "telemetry": {"rx":0,"tx":0},
        "bulk": {"conn":0,"bytes":0},
    }

    threading.Thread(target=udp_echo_server, args=(CRIT_UDP,"critical",counters), daemon=True).start()
    threading.Thread(target=udp_echo_server, args=(TEL_UDP,"telemetry",counters), daemon=True).start()
    threading.Thread(target=tcp_sink_server, args=(BULK_TCP,counters), daemon=True).start()
    writer(args.out, counters)

if __name__ == "__main__":
    main()

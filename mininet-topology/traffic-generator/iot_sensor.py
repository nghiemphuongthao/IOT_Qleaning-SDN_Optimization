import argparse, socket, time, os, csv, struct

CRIT_UDP = int(os.environ.get("CRIT_UDP", "5001"))
TEL_UDP  = int(os.environ.get("TEL_UDP", "5002"))
BULK_TCP = int(os.environ.get("BULK_TCP", "5003"))

def udp_client(server_ip, port, label, rate_pps, duration_s, out_writer):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.2)

    seq = 0
    sent = 0
    lost = 0
    rtts = []
    pending = {}

    start = time.time()
    next_send = start
    interval = 1.0 / max(1e-6, rate_pps)

    while time.time() - start < duration_s:
        now = time.time()
        if now >= next_send:
            seq += 1
            tns = time.time_ns()
            payload = struct.pack("!IQ", seq, tns)
            try:
                sock.sendto(payload, (server_ip, port))
                pending[seq] = tns
                sent += 1
            except Exception:
                pass
            next_send += interval

        try:
            data, _ = sock.recvfrom(2048)
            if len(data) >= 12:
                rseq, _ = struct.unpack("!IQ", data[:12])
                if rseq in pending:
                    rtt_ms = (time.time_ns() - pending.pop(rseq)) / 1e6
                    rtts.append(rtt_ms)
        except socket.timeout:
            pass
        except Exception:
            pass

        if len(pending) > 2000:
            for k in list(pending.keys())[:500]:
                pending.pop(k, None)
                lost += 1

    lost += len(pending)
    avg_rtt = sum(rtts)/len(rtts) if rtts else None
    bps = (sent * 12 * 8) / max(1e-6, duration_s)
    out_writer.writerow([time.time(), label, avg_rtt, lost, sent, bps])

def tcp_bulk(server_ip, port, duration_s, out_writer, target_mbps=None):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2.0)
    try:
        s.connect((server_ip, port))
    except Exception:
        out_writer.writerow([time.time(), "bulk", None, 1, 0, 0])
        return

    payload = b"x" * 65536
    start = time.time()
    sent_bytes = 0
    while time.time() - start < duration_s:
        try:
            s.sendall(payload)
            sent_bytes += len(payload)
        except Exception:
            break
        if target_mbps:
            elapsed = time.time() - start
            if elapsed > 0:
                cur_mbps = (sent_bytes * 8) / (elapsed * 1e6)
                if cur_mbps > target_mbps:
                    time.sleep(0.01)

    try:
        s.close()
    except Exception:
        pass

    bps = (sent_bytes * 8) / max(1e-6, duration_s)
    out_writer.writerow([time.time(), "bulk", None, 0, sent_bytes, bps])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--server", required=True)
    ap.add_argument("--case", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    total = int(os.environ.get("RUN_SECONDS", "90"))
    window = 10
    loops = total // window

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts","class","rtt_ms","lost","sent","bps"])

        for i in range(loops):
            elapsed = i * window

            # Phase detection
            if elapsed < 30:
                phase = "normal"
            elif elapsed < 60:
                phase = "congestion"
            else:
                phase = "recovery"

            # Telemetry – luôn nhẹ
            udp_client(
                args.server,
                TEL_UDP,
                "telemetry",
                rate_pps=20,
                duration_s=window,
                out_writer=w
            )

            # Critical – luôn tồn tại
            crit_rate = 30 if phase != "congestion" else 50
            udp_client(
                args.server,
                CRIT_UDP,
                "critical",
                rate_pps=crit_rate,
                duration_s=window,
                out_writer=w
            )

            # Bulk traffic – nguồn gây congestion
            if phase == "normal":
                tcp_bulk(
                    args.server,
                    BULK_TCP,
                    duration_s=window,
                    out_writer=w,
                    target_mbps=1.0
                )
            elif phase == "congestion":
                tcp_bulk(
                    args.server,
                    BULK_TCP,
                    duration_s=window,
                    out_writer=w,
                    target_mbps=8.0
                )
            else:  # recovery
                tcp_bulk(
                    args.server,
                    BULK_TCP,
                    duration_s=window,
                    out_writer=w,
                    target_mbps=2.0
                )

            f.flush()

if __name__ == "__main__":
    main()

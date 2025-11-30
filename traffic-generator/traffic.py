#!/usr/bin/env python3
"""
traffic.py - IoT-style traffic generator for Mininet + Ryu setup.

Usage:
    python3 traffic.py <network_name>
Examples:
    python3 traffic.py baseline
    python3 traffic.py sdn

Behavior:
 - If iperf3 is available and network targets are reachable (Mininet services present),
   it will attempt to run iperf3 client commands.
 - If iperf3 not available or fails, it will FALLBACK to simulated traffic (log-only)
 - Results are stored into /shared/iot_traffic_results.json (mount ./shared:/shared)
"""

import sys
import time
import random
import json
import subprocess
from datetime import datetime
import signal

RESULT_FILE = "/shared/iot_traffic_results.json"

# Simple cleanup on SIGTERM / SIGINT
running = True
def _stop(signum, frame):
    global running
    running = False

signal.signal(signal.SIGINT, _stop)
signal.signal(signal.SIGTERM, _stop)

class IoTTrafficGenerator:
    def __init__(self, network_name):
        self.network_name = network_name
        self.results = []
        # default device addresses that correspond to your mininet topology
        self.sensors = [
            '10.0.1.10', '10.0.1.11', '10.0.2.10', '10.0.2.11',
            '10.0.3.10', '10.0.3.11', '10.0.4.10', '10.0.4.11'
        ]
        self.gateways = ['10.0.1.1', '10.0.2.1', '10.0.3.1', '10.0.4.1']
        self.actuators = ['10.0.1.20', '10.0.2.20', '10.0.3.20', '10.0.4.20']
        self.cloud_server = '10.0.100.2'  # your cloud host in topology
        self.use_iperf = self._check_iperf()

    def _check_iperf(self):
        try:
            res = subprocess.run(["iperf3", "--version"], capture_output=True, text=True, timeout=5)
            return res.returncode == 0
        except Exception:
            return False

    def _log(self, tag, output):
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "tag": tag,
            "output": output
        }
        self.results.append(entry)
        # flush periodically
        if len(self.results) % 5 == 0:
            self._save()
        return entry

    def _save(self):
        try:
            with open(RESULT_FILE, "w") as f:
                json.dump(self.results, f, indent=2)
        except Exception as e:
            print("Error saving results:", e)

    def _run_iperf(self, dst, bandwidth="1M", duration=3, port=5201):
        cmd = ["iperf3", "-c", dst, "-b", bandwidth, "-t", str(duration), "-p", str(port)]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=duration+10)
            return r.stdout.strip()
        except Exception as e:
            return f"iperf3-failed: {e}"

    def sensor_to_gateway(self):
        while running:
            for s, gw in zip(self.sensors, self.gateways * 2):
                if not running: break
                bw = random.choice(["0.05M", "0.1M", "0.5M"])
                dur = random.randint(1, 3)
                tag = f"sensor_to_gateway {s}->{gw}"
                if self.use_iperf:
                    out = self._run_iperf(gw, bandwidth=bw, duration=dur, port=4001)
                else:
                    out = f"mock {tag} bw={bw} dur={dur}s"
                print(tag, out.splitlines()[0] if out else "")
                self._log(tag, out)
                time.sleep(random.uniform(0.5, 2.0))

    def gateway_to_cloud(self):
        while running:
            for gw in self.gateways:
                if not running: break
                bw = random.choice(["5M", "10M", "20M"])
                dur = random.randint(3, 6)
                tag = f"gateway_to_cloud {gw}->{self.cloud_server}"
                if self.use_iperf:
                    out = self._run_iperf(self.cloud_server, bandwidth=bw, duration=dur, port=4002)
                else:
                    out = f"mock {tag} bw={bw} dur={dur}s"
                print(tag)
                self._log(tag, out)
                time.sleep(random.uniform(2.0, 5.0))

    def actuator_commands(self):
        while running:
            for act in self.actuators:
                if not running: break
                src = random.choice(self.gateways + [self.cloud_server])
                bw = random.choice(["0.05M", "0.1M"])
                dur = random.randint(1, 2)
                tag = f"actuator_cmd {src}->{act}"
                if self.use_iperf:
                    out = self._run_iperf(act, bandwidth=bw, duration=dur, port=4003)
                else:
                    out = f"mock {tag} bw={bw} dur={dur}s"
                print(tag)
                self._log(tag, out)
                time.sleep(random.uniform(1.0, 3.0))

    def latency_test(self):
        # Quick ping checks (non-blocking)
        pairs = [
            ("10.0.1.10", self.cloud_server),
            ("10.0.4.11", "10.0.1.20"),
            ("10.0.2.10", "10.0.3.20")
        ]
        for src, dst in pairs:
            if not running: break
            try:
                p = subprocess.run(["ping", "-c", "3", "-W", "1", dst], capture_output=True, text=True, timeout=10)
                out = p.stdout.strip()
            except Exception as e:
                out = f"ping-failed: {e}"
            self._log(f"latency {src}->{dst}", out)

    def run(self, runtime=300):
        # Start threads
        import threading
        threads = [
            threading.Thread(target=self.sensor_to_gateway, daemon=True),
            threading.Thread(target=self.gateway_to_cloud, daemon=True),
            threading.Thread(target=self.actuator_commands, daemon=True)
        ]
        for t in threads:
            t.start()

        start = time.time()
        while running and (time.time() - start) < runtime:
            # periodic latency tests
            self.latency_test()
            time.sleep(10)

        # finish
        self._save()
        print("Traffic generator exiting.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 traffic.py <network_name>")
        sys.exit(1)
    network = sys.argv[1]
    g = IoTTrafficGenerator(network)
    # default runtime 5 minutes; you can change via env var if desired
    runtime = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    g.run(runtime)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
topology.py
Hỗ trợ 3 mode: baseline | sdn | qlearning

Usage:
    python3 topology.py baseline
    python3 topology.py sdn
    python3 topology.py qlearning

Expected environment:
- chạy với quyền root (hoặc chạy trong container --privileged)
- /shared mount sẵn giữa các container để trao đổi file
- configs/network_params.yaml (tùy chọn) chứa tham số topo
"""

import sys
import os
import time
import json
import threading
import signal
from datetime import datetime

# Mininet imports
try:
    from mininet.net import Mininet
    from mininet.node import RemoteController, OVSSwitch
    from mininet.link import TCLink
    from mininet.log import setLogLevel, info, error
    from mininet.cli import CLI
except Exception as e:
    print("Mininet import error:", e)
    sys.exit(1)

# YAML may be used to load configs
try:
    import yaml
except ImportError:
    yaml = None  # will handle missing YAML gracefully


# ----------------------------
# Constants & defaults
# ----------------------------
SHARED_DIR = "/shared"
TOPOLOGY_INFO_PATH = os.path.join(SHARED_DIR, "topology_info.json")
TOPOLOGY_READY_FLAG = os.path.join(SHARED_DIR, "topology_ready")
STATE_JSON = os.path.join(SHARED_DIR, "state.json")
ACTION_JSON = os.path.join(SHARED_DIR, "action.json")

DEFAULT_CONFIG = {
    "num_switches": 5,
    "hosts_per_switch": 2,
    "link_delay": "2ms",
    "link_bw": 10,          # Mbps
    "controller_ip": "172.20.0.10",
    "controller_port": 6633,
    "state_interval": 5,    # seconds between state writes in qlearning mode
    "sample_pairs": [       # pairs of host names to sample latency
        ["h_1_1", "h_1_2"],
        ["h_2_1", "h_2_2"]
    ]
}


# ----------------------------
# Utility: load config file
# ----------------------------
def load_config(path="/configs/network_params.yaml"):
    cfg = DEFAULT_CONFIG.copy()
    if yaml is None:
        info("PyYAML not installed: using default config\n")
        return cfg

    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                user_cfg = yaml.safe_load(f) or {}
            # merge shallow
            cfg.update(user_cfg)
            info(f"Loaded config from {path}\n")
        except Exception as e:
            info(f"Warning: cannot read config {path}: {e}\n")
    else:
        info(f"No config file at {path}, using defaults\n")
    return cfg


# ----------------------------
# Topology builder (simple)
# ----------------------------
class TopologyRunner:
    def __init__(self, mode="sdn"):
        self.mode = mode
        self.net = None
        self.stop_event = threading.Event()
        self.state_thread = None
        self.config = load_config()
        # allow overriding controller IP via env
        self.controller_ip = os.getenv("RYU_CONTROLLER_IP", self.config.get("controller_ip"))
        self.controller_port = int(os.getenv("RYU_CONTROLLER_PORT", self.config.get("controller_port", 6633)))

    def create_topology(self):
        info(f"*** Khởi tạo topology, mode={self.mode}\n")
        n_sw = int(self.config.get("num_switches", 5))
        hps = int(self.config.get("hosts_per_switch", 2))
        link_delay = self.config.get("link_delay", "2ms")
        link_bw = int(self.config.get("link_bw", 10))

        # create net object differently per mode
        if self.mode == "baseline":
            # baseline: one central switch + all hosts attach to it
            topo_switches = 1
        else:
            topo_switches = n_sw

        info(f"  switches: {topo_switches}, hosts_per_switch: {hps}\n")

        # Build Mininet programmatically (not using Topo class for clarity)
        self.net = Mininet(controller=None, switch=OVSSwitch, link=TCLink)

        # create switches
        switches = []
        for si in range(1, topo_switches + 1):
            sw = self.net.addSwitch(f"s{si}")
            switches.append(sw)
            info(f"  created switch {sw.name}\n")

        # create hosts and link
        hosts = {}
        for si, sw in enumerate(switches, start=1):
            for hi in range(1, hps + 1):
                host_name = f"h_{si}_{hi}"
                # IP scheme: 10.<si>.<hi>.10/24 (simple)
                ip_octet2 = 100 + si  # avoid 0/1 collisions; fits small topo
                ip_octet3 = 10 + hi
                ip_addr = f"10.{ip_octet2}.{ip_octet3}.10/24"
                h = self.net.addHost(host_name, ip=ip_addr)
                hosts[host_name] = h
                # link with TC params
                self.net.addLink(h, sw, cls=TCLink, delay=link_delay, bw=link_bw)
                info(f"  created host {host_name} ({ip_addr}) and linked to {sw.name}\n")

        # if more complex backbone needed for non-baseline, chain switches
        if self.mode != "baseline" and len(switches) > 1:
            info("  linking switches in chain\n")
            for i in range(len(switches) - 1):
                self.net.addLink(switches[i], switches[i + 1], cls=TCLink, delay=link_delay, bw=link_bw)
                info(f"  linked {switches[i].name} <-> {switches[i+1].name}\n")

        # If SDN mode, add controller object (RemoteController)
        if self.mode in ("sdn", "qlearning"):
            info(f"  using remote controller at {self.controller_ip}:{self.controller_port}\n")
            # Add controller object for Mininet; RemoteController is instantiated on start
            # Mininet will try to connect switches to that controller
            self.net.addController("c0", controller=RemoteController, ip=self.controller_ip, port=self.controller_port)

        return True

    def start_network(self):
        if self.net is None:
            error("*** Network chưa được tạo - gọi create_topology trước\n")
            return False

        info("*** Building and starting network\n")
        self.net.build()

        # start controller(s) handled by Mininet when added as RemoteController,
        # but we still call start on switches to ensure OVS is initialized.
        if self.mode in ("sdn", "qlearning"):
            info("*** Waiting a bit for controller to be contactable...\n")
            time.sleep(2)

        for sw in self.net.switches:
            try:
                sw.start([c for c in self.net.controllers])
                info(f"  switch {sw.name} started\n")
            except Exception as e:
                info(f"  Warning: starting {sw.name} error: {e}\n")

        # save topology info to shared
        self.save_topology_info()

        # create topology ready flag
        try:
            os.makedirs(SHARED_DIR, exist_ok=True)
            with open(TOPOLOGY_READY_FLAG, "w") as f:
                f.write(datetime.utcnow().isoformat())
            info(f"*** Topology ready flag written to {TOPOLOGY_READY_FLAG}\n")
        except Exception as e:
            info(f"*** Warning: cannot write ready flag: {e}\n")

        # If qlearning, start background state writer thread
        if self.mode == "qlearning":
            self.state_thread = threading.Thread(target=self._state_writer_loop, daemon=True)
            self.state_thread.start()

        return True

    def save_topology_info(self):
        try:
            topo = {
                "timestamp": datetime.utcnow().isoformat(),
                "mode": self.mode,
                "switches": [s.name for s in self.net.switches],
                "hosts": [h.name for h in self.net.hosts],
                "ip_mapping": {h.name: h.IP() for h in self.net.hosts},
                "controller": {"ip": self.controller_ip, "port": self.controller_port}
            }
            os.makedirs(SHARED_DIR, exist_ok=True)
            with open(TOPOLOGY_INFO_PATH, "w") as f:
                json.dump(topo, f, indent=2)
            info(f"*** Topology info saved: {TOPOLOGY_INFO_PATH}\n")
        except Exception as e:
            info(f"*** Error saving topology info: {e}\n")

    # ----------------------------
    # Simple measurement functions
    # ----------------------------
    def _measure_pair_ping(self, src_host_name, dst_ip, count=1, timeout=2):
        """
        Return ping RTT in ms (average) or None on failure.
        Uses host.cmd('ping -c ...') to measure.
        """
        try:
            src = self.net.get(src_host_name)
        except Exception:
            return None
        cmd = f"ping -c {count} -W {timeout} {dst_ip}"
        out = src.cmd(cmd)
        # try to parse "rtt min/avg/max/mdev = x/x/x/x ms"
        for line in out.splitlines():
            if "rtt min/avg" in line or "rtt min/avg/max/mdev" in line:
                parts = line.split("=")[1].strip().split()[0].split("/")
                avg = float(parts[1])
                return avg
        return None

    def _collect_state_once(self):
        """
        Collect lightweight state: topology, simple pings for configured sample pairs,
        interface tx/rx bytes for switches.
        """
        state = {
            "timestamp": datetime.utcnow().isoformat(),
            "mode": self.mode,
            "switches": [s.name for s in self.net.switches],
            "hosts": [h.name for h in self.net.hosts],
            "samples": []
        }

        sample_pairs = self.config.get("sample_pairs", DEFAULT_CONFIG["sample_pairs"])
        for pair in sample_pairs:
            src_name, dst_name = None, None
            try:
                src_name = pair[0]
                dst_name = pair[1]
            except Exception:
                continue
            # if dst is a host name in net, use its IP, else treat as raw IP
            dst_ip = None
            try:
                if dst_name in [h.name for h in self.net.hosts]:
                    dst_ip = self.net.get(dst_name).IP()
                else:
                    dst_ip = dst_name
            except Exception:
                dst_ip = dst_name
            rtt = self._measure_pair_ping(src_name, dst_ip, count=1, timeout=2)
            state["samples"].append({"pair": [src_name, dst_name], "rtt_ms": rtt})

        return state

    def _state_writer_loop(self):
        interval = int(self.config.get("state_interval", DEFAULT_CONFIG["state_interval"]))
        info(f"*** Q-Learning state writer starting, interval={interval}s\n")
        while not self.stop_event.is_set():
            try:
                state = self._collect_state_once()
                # write to SHARED_DIR/state.json
                try:
                    with open(STATE_JSON, "w") as f:
                        json.dump(state, f, indent=2)
                except Exception as e:
                    info(f"*** Warning: cannot write state file: {e}\n")

                # check for action file (agent -> ryu/app may write actions)
                if os.path.exists(ACTION_JSON):
                    try:
                        with open(ACTION_JSON, "r") as f:
                            action = json.load(f)
                        info(f"*** Found action.json: {action}\n")
                        # We don't directly apply flows here; Ryu should act on REST/API.
                        # We simply remove or archive the action file to signal consumption.
                        os.remove(ACTION_JSON)
                        info("*** action.json consumed and removed\n")
                    except Exception as e:
                        info(f"*** Warning processing action.json: {e}\n")

            except Exception as e:
                info(f"*** State writer loop error: {e}\n")
            # sleep
            for _ in range(interval):
                if self.stop_event.is_set():
                    break
                time.sleep(1)
        info("*** Q-Learning state writer stopped\n")

    def stop(self):
        info("*** Stopping background tasks and Mininet\n")
        try:
            self.stop_event.set()
            if self.state_thread and self.state_thread.is_alive():
                self.state_thread.join(timeout=2)
        except Exception:
            pass
        try:
            if self.net:
                self.net.stop()
        except Exception as e:
            info(f"*** Error stopping net: {e}\n")


# ----------------------------
# Signal handling for graceful stop
# ----------------------------
_runner = None


def _graceful_exit(signum, frame):
    info(f"*** Caught signal {signum}, stopping...\n")
    global _runner
    if _runner:
        _runner.stop()
    sys.exit(0)


for s in (signal.SIGINT, signal.SIGTERM):
    signal.signal(s, _graceful_exit)


# ----------------------------
# Main entry
# ----------------------------
def main():
    setLogLevel("info")
    if len(sys.argv) < 2:
        print("Usage: python3 topology.py [baseline|sdn|qlearning]")
        sys.exit(1)

    mode = sys.argv[1].lower()
    if mode not in ("baseline", "sdn", "qlearning"):
        print("Mode must be one of: baseline | sdn | qlearning")
        sys.exit(1)

    # Root check
    if os.geteuid() != 0:
        print("*** Mininet must run as root. If running locally, use sudo; if in Docker, run --privileged.")
        sys.exit(1)

    global _runner
    _runner = TopologyRunner(mode=mode)
    created = _runner.create_topology()
    if not created:
        error("*** Failed to create topology\n")
        sys.exit(1)

    started = _runner.start_network()
    if not started:
        error("*** Failed to start network\n")
        sys.exit(1)

    # Enter CLI for debugging / interactive use
    try:
        CLI(_runner.net)
    except Exception as e:
        info(f"*** CLI ended: {e}\n")
    finally:
        _runner.stop()


if __name__ == "__main__":
    main()

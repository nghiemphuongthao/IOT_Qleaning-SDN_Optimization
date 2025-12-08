#!/usr/bin/env python3
import os
import time
from functools import partial

from mininet.topo import Topo
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info

# ==========================
# SDN IOT FLAT TOPO (Case 3)
# ==========================
class SDNIoTFlatTopo(Topo):
    def build(self):
        # --- SWITCHES (SDN) ---
        g1 = self.addSwitch("g1", dpid="0000000000000100")
        g2 = self.addSwitch("g2", dpid="0000000000000200")
        g3 = self.addSwitch("g3", dpid="0000000000000300")
        s1 = self.addSwitch("s1", dpid="0000000000000001")
        s2 = self.addSwitch("s2", dpid="0000000000000002")
        s3 = self.addSwitch("s3", dpid="0000000000000003")
        s4 = self.addSwitch("s4", dpid="0000000000000004")

        # cloud host (two uplinks to different gateways)
        cloud = self.addHost("cloud", ip="10.0.0.254/24")

        # bandwidths (Mbps)
        bw_backbone = 50
        bw_uplink = 1.5
        bw_access = 10

        # --- LINKS ---
        # connect cloud to g1 and g3 (different interfaces)
        # we set intf names to make later config predictable
        self.addLink(g1, cloud, intfName1="g1-eth100", intfName2="cloud-eth0",
                     bw=bw_uplink, max_queue_size=100)
        self.addLink(g3, cloud, intfName1="g3-eth100", intfName2="cloud-eth1",
                     bw=bw_backbone, max_queue_size=100)

        # spine-like connections
        self.addLink(g1, g2, bw=bw_backbone)
        self.addLink(g1, g3, bw=bw_backbone)

        # uplinks to access switches
        self.addLink(g1, s1, bw=bw_access)
        self.addLink(g1, s2, bw=bw_access)
        self.addLink(g2, s3, bw=bw_access)
        self.addLink(g3, s4, bw=bw_access)

        # --- HOSTS (SENSORS) ---
        # Zone 1 -> S1 (h1,h2,h3)
        for i in range(1, 4):
            self.addHost(f"h{i}", ip=f"10.0.0.{i}/24")
            self.addLink(s1, f"h{i}", bw=bw_access)

        # Zone 2 -> S2 (h4,h5)
        for i in range(4, 6):
            self.addHost(f"h{i}", ip=f"10.0.0.{i}/24")
            self.addLink(s2, f"h{i}", bw=bw_access)

        # Zone 3 -> S3 (h6,h7)
        for i in range(6, 8):
            self.addHost(f"h{i}", ip=f"10.0.0.{i}/24")
            self.addLink(s3, f"h{i}", bw=bw_access)

        # Zone 4 -> S4 (h8,h9,h10)
        for i in range(8, 11):
            self.addHost(f"h{i}", ip=f"10.0.0.{i}/24")
            self.addLink(s4, f"h{i}", bw=bw_access)


# ==========================
# MAIN: run topology and start services inside Mininet container
# ==========================
def run():
    setLogLevel("info")

    # Use environment variables if set (helps with docker-compose)
    controller_ip = os.environ.get("CONTROLLER_IP", "ryu-controller")  # docker service name
    controller_port = int(os.environ.get("RYU_OFP_PORT", os.environ.get("RYU_PORT", 6653)))

    info(f"[*] Controller target: {controller_ip}:{controller_port}\n")

    topo = SDNIoTFlatTopo()
    switch_with_protocol = partial(OVSKernelSwitch, protocols='OpenFlow13')

    net = Mininet(topo=topo,
                  controller=None,
                  switch=switch_with_protocol,
                  link=TCLink,
                  autoSetMacs=True)

    info("[*] Adding remote controller\n")
    # RemoteController will resolve service name inside docker network
    c0 = net.addController('c0', controller=RemoteController,
                           ip=controller_ip, port=controller_port)

    info("[*] Starting network...\n")
    net.start()
    time.sleep(1)
    #net.xterms = []  # keep track of xterms if needed
    net.pingAll()

    info("[*] Starting internal traffic generator...\n")

    cloud = net.get('cloud')
    h1 = net.get('h1')
    h2 = net.get('h2')

    cloud.cmd("iperf3 -s -p 5001 -D")
    cloud.cmd("iperf3 -s -p 5002 -D")

    info("[RUN] h1 -> cloud (5001 UDP)\n")
    h1.cmd("iperf3 -u -c 10.0.0.254 -b 60M -t 60 -p 5001 &")

    info("[RUN] h2 -> cloud (5002 TCP)\n")
    h2.cmd("iperf3 -c 10.0.0.254 -t 60 -p 5002 &")

    # Configure cloud additional interface names (cloud has cloud-eth0 & cloud-eth1)
    cloud = net.get('cloud')
    # ensure both interfaces exist and are up
    for intf_name, ipaddr in [("cloud-eth0", "10.0.0.254/24"), ("cloud-eth1", "10.0.0.253/24")]:
        # try to add IP only if not present
        out = cloud.cmd(f"ip addr show dev {intf_name} || echo notfound")
        # set ip address only if different
        cloud.cmd(f"ip addr add {ipaddr} dev {intf_name} 2>/dev/null || true")
        cloud.cmd(f"ip link set {intf_name} up 2>/dev/null || true")

    info("[*] Starting Background Services on cloud host...\n")
    # run iot_server.py if exists in working directory (ensure path correct)
    # server logs capture to server.log in container filesystem
    # PYTHONUNBUFFERED ensures immediate log flush
    if os.path.exists("/traffic-generator/iot_server.py"):
        cloud.cmd("PYTHONUNBUFFERED=1 python3 /traffic-generator/iot_server.py > /tmp/server.log 2>&1 &")
        info(" -> iot_server.py started on cloud (logs -> /tmp/server.log)\n")
    else:
        info(" -> iot_server.py not found at /traffic-generator/iot_server.py\n")

    # start iperf3 server as backup (use iperf3 if available)
    # if iperf3 missing, this command fails silently
    cloud.cmd("iperf3 -s -p 5001 > /tmp/iperf3_server.log 2>&1 &")

    # start a few sample sensors (adjust hosts + script path as needed)
    sensors = {'h1': 'temp', 'h2': 'motion', 'h3': 'humid'}
    for h, t in sensors.items():
        try:
            node = net.get(h)
            if os.path.exists("/traffic-generator/iot_sensor.py"):
                node.cmd(f"PYTHONUNBUFFERED=1 python3 /traffic-generator/iot_sensor.py --target 10.0.0.254 --type {t} > /tmp/{h}_{t}.log 2>&1 &")
                info(f" -> Started sensor on {h} (type={t})\n")
            else:
                info(f" -> iot_sensor.py not found; skipping {h}\n")
        except Exception as e:
            info(f" -> Failed to start sensor on {h}: {e}\n")

    info("\n------------------------------------------------\n")
    info("Network Ready!\n")
    info("Cloud Main IP: 10.0.0.254 (via g1)\n")
    info("Cloud Backup IP: 10.0.0.253 (via g3)\n")
    info("All Hosts: 10.0.0.1 -> 10.0.0.10\n")
    info("------------------------------------------------\n")

    # start CLI so you can interact; keep network running
    CLI(net)

    # on exit, cleanup
    info("[*] Stopping network and background processes...\n")
    # kill background processes started above (best-effort)
    cloud.cmd("pkill -f iot_server.py || true")
    for h in range(1, 11):
        try:
            host = net.get(f"h{h}")
            host.cmd("pkill -f iot_sensor.py || true")
        except Exception:
            pass
    cloud.cmd("pkill -f iperf3 || true")
    net.stop()


if __name__ == "__main__":
    run()

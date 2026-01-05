import os
import time
from functools import partial
from mininet.topo import Topo
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info

class SDNIoTTreeTopo(Topo):
    def build(self):
        # 1. Switches (Core & Aggregation)
        # G1: Core Router
        g1 = self.addSwitch("g1", dpid="0000000000000100")
        # G2: Aggregation cho Zone 3
        g2 = self.addSwitch("g2", dpid="0000000000000200")
        # G3: Aggregation cho Zone 4 + Backup Link
        g3 = self.addSwitch("g3", dpid="0000000000000300")

        # Access Switches
        s1 = self.addSwitch("s1", dpid="0000000000000001")
        s2 = self.addSwitch("s2", dpid="0000000000000002")
        s3 = self.addSwitch("s3", dpid="0000000000000003")
        s4 = self.addSwitch("s4", dpid="0000000000000004")

        # 2. Cloud Server (Multi-homing)
        cloud = self.addHost("cloud", ip="10.0.100.2/24", 
                             mac="00:00:00:00:00:FF",
                             defaultRoute="via 10.0.100.1")

        bw_router = 10
        bw_host = 10

        # --- LINKS ---
        
        self.addLink(g1, cloud, port1=1, port2=0, 
                     bw=1.5, max_queue_size=100) 
        # Port 2: Ra S1 (Zone 1)
        self.addLink(g1, s1, port1=2, bw=bw_router)
        # Port 3: Ra S2 (Zone 2)
        self.addLink(g1, s2, port1=3, bw=bw_router)
        # Port 4: Ra G2 (Zone 3)
        self.addLink(g1, g2, port1=4, port2=1, bw=10)
        # Port 5: Ra G3 (Zone 4 + Backup)
        self.addLink(g1, g3, port1=5, port2=1, bw=50)

        self.addLink(g2, s3, port1=2, bw=bw_router)

        self.addLink(g3, s4, port1=2, bw=bw_router)
        # Port 3: Backup ra Cloud
        self.addLink(g3, cloud, port1=3, port2=1, bw=10)

# --- HOSTS & ACCESS LINKS  ---
        # Zone 1 (10.0.1.x) -> S1
        for i in range(1, 4): 
            mac_addr = '00:00:00:00:00:%02x' % i
            self.addHost(f"h{i}", ip=f"10.0.1.{i}/24", mac=mac_addr, defaultRoute="via 10.0.1.254")
            self.addLink(s1, f"h{i}", bw=bw_host)
        
        # Zone 2 (10.0.2.x) -> S2
        for i in range(4, 6): 
            mac_addr = '00:00:00:00:00:%02x' % i
            self.addHost(f"h{i}", ip=f"10.0.2.{i}/24", mac=mac_addr, defaultRoute="via 10.0.2.254")
            self.addLink(s2, f"h{i}", bw=bw_host)

        # Zone 3 (10.0.3.x) -> S3
        for i in range(6, 8): 
            mac_addr = '00:00:00:00:00:%02x' % i
            self.addHost(f"h{i}", ip=f"10.0.3.{i}/24", mac=mac_addr, defaultRoute="via 10.0.3.254")
            self.addLink(s3, f"h{i}", bw=bw_host)

        # Zone 4 (10.0.4.x) -> S4
        for i in range(8, 11): 
            mac_addr = '00:00:00:00:00:%02x' % i
            self.addHost(f"h{i}", ip=f"10.0.4.{i}/24", mac=mac_addr, defaultRoute="via 10.0.4.254")
            self.addLink(s4, f"h{i}", bw=bw_host)

def run():
    topo = SDNIoTTreeTopo()
    switch_with_protocol = partial(OVSKernelSwitch, protocols='OpenFlow13')
    net = Mininet(topo=topo, controller=None, switch=switch_with_protocol, link=TCLink)
    
    info("[*] Connecting to Remote Controller...\n")
    c0 = net.addController('c0', controller=RemoteController, ip='ryu-controller', port=6653)

    net.start()
    net.pingAll()

    g1 = net.get('g1')
    g3 = net.get('g3')
    qos_max_bps = int(float(os.environ.get('QOS_MAX_BPS', '100000000')))
    bulk_max_bps = int(float(os.environ.get('BULK_MAX_BPS', '1200000')))
    queue_cfg = (
        "ovs-vsctl --if-exists clear Port {port} qos "
        "-- set Port {port} qos=@newqos "
        "-- --id=@newqos create QoS type=linux-htb other-config:max-rate={max_rate} queues:0=@q0 queues:1=@q1 queues:2=@q2 "
        "-- --id=@q0 create Queue other-config:min-rate={max_rate} other-config:max-rate={max_rate} "
        "-- --id=@q1 create Queue other-config:max-rate={bulk_rate} "
        "-- --id=@q2 create Queue other-config:max-rate={bulk_rate}"
    )
    g1.cmd(queue_cfg.format(port='g1-eth1', max_rate=qos_max_bps, bulk_rate=bulk_max_bps))
    g1.cmd(queue_cfg.format(port='g1-eth5', max_rate=qos_max_bps, bulk_rate=bulk_max_bps))
    g3.cmd(queue_cfg.format(port='g3-eth3', max_rate=qos_max_bps, bulk_rate=bulk_max_bps))
    
    cloud = net.get('cloud')
    info("[*] Disabling rp_filter on Cloud...\n")

    cloud.cmd("ip addr add 10.0.200.2/24 dev cloud-eth1")
    cloud.cmd("ip link set cloud-eth1 up")
    cloud.cmd("ifconfig cloud-eth1 hw ether 00:00:00:00:00:FF")
    
    cloud.cmd("sysctl -w net.ipv4.conf.all.rp_filter=0")
    cloud.cmd("sysctl -w net.ipv4.conf.default.rp_filter=0")
    cloud.cmd("sysctl -w net.ipv4.conf.cloud-eth0.rp_filter=0")
    cloud.cmd("sysctl -w net.ipv4.conf.cloud-eth1.rp_filter=0")
    
    cloud.cmd("ip route replace 10.0.0.0/16 via 10.0.100.1")

    info("\n=== SDN L3 TOPOLOGY STARTED ===\n")
    time.sleep(2)

    # Start Services
    info("[*] Starting Services...\n")
    cloud.cmd("mkdir -p /shared/raw /shared/logs")
    cloud.cmd("python3 /app/traffic-generator/iot_server.py --bind 0.0.0.0 --out /shared/raw/sdn_qlearning_server.csv > /shared/logs/iot_server.log 2>&1 &")
    # cloud.cmd("iperf -s -u -p 5001 &") 
    
    sensors = {'h1': 'temp', 'h2': 'humid', 'h3': 'motion', 'h4': 'temp', 'h10': 'humid'}
    for h, t in sensors.items():
        node = net.get(h)
        node.cmd(
  f"python3 /app/traffic-generator/iot_sensor.py "
  f"--name {h} "
  f"--server 10.0.100.2 "
  f"--case sdn_qlearning "
  f"--out /shared/raw/sdn_qlearning_{h}.csv "
  f"> /shared/logs/{h}_sensor.log 2>&1 &"
)
        info(f" -> {h} started sending {t}\n")

    if os.environ.get("INTERACTIVE", "0") == "1":
        CLI(net)
    else:
        total = int(os.environ.get("RUN_SECONDS", "300"))
        time.sleep(total + 5)
    
    os.system("pkill -f iot_server.py")
    os.system("pkill -f iot_sensor.py")
    os.system("pkill -f iperf")
    net.stop()

if __name__ == "__main__":
    setLogLevel("info") 
    run()
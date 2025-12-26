import os
import time
from mininet.topo import Topo
from mininet.node import Node, OVSController
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info

# =======================================
# LINUX ROUTER CLASS
# =======================================
class LinuxRouter(Node):
    def config(self, **params):
        super(LinuxRouter, self).config(**params)
        self.cmd("sysctl -w net.ipv4.ip_forward=1")

    def terminate(self):
        self.cmd("sysctl -w net.ipv4.ip_forward=0")
        super(LinuxRouter, self).terminate()

# =======================================
# BUILD TOPOLOGY 
# =======================================
class IoTStaticTopo(Topo):
    def build(self):
        # Routers = Gateways 
        g1 = self.addNode("g1", cls=LinuxRouter, ip=None)
        g2 = self.addNode("g2", cls=LinuxRouter, ip=None)

        # Cloud server
        cloud = self.addHost("cloud", ip="10.0.100.2/24", defaultRoute="via 10.0.100.1")

        # Switches
        s1 = self.addSwitch("s1")
        s2 = self.addSwitch("s2")
        s3 = self.addSwitch("s3")
        s4 = self.addSwitch("s4")

        # Links & IP Assignment
        bw_router = 10
        bw_host = 10

        # G1 <-> Subnets
        self.addLink(g1, s1, intfName1="g1-eth1", params1={"ip": "10.0.1.254/24"}, bw=bw_router)
        self.addLink(g1, s2, intfName1="g1-eth2", params1={"ip": "10.0.2.254/24"}, bw=bw_router)
        self.addLink(g1, s3, intfName1="g1-eth3", params1={"ip": "10.0.3.254/24"}, bw=bw_router)

        # G2 <-> Subnet
        self.addLink(g2, s4, intfName1="g2-eth1", params1={"ip": "10.0.4.254/24"}, bw=bw_router)

        # Backbone G1 <-> G2
        self.addLink(g1, g2,
                     intfName1="g1-eth10", params1={"ip": "10.0.10.1/24"},
                     intfName2="g2-eth10", params2={"ip": "10.0.10.2/24"},
                     bw=10)

        # G1 <-> Cloud
        self.addLink(g1, cloud, intfName1="g1-eth100",
                     params1={"ip": "10.0.100.1/24"}, bw=bw_router)

        # Hosts
        # S1 Hosts
        for i in range(1, 4):
            self.addHost(f"h{i}", ip=f"10.0.1.{i}/24", defaultRoute="via 10.0.1.254")
            self.addLink(s1, f"h{i}", bw=bw_host)
        
        # S2 Hosts
        for i in range(4, 6):
            self.addHost(f"h{i}", ip=f"10.0.2.{i}/24", defaultRoute="via 10.0.2.254")
            self.addLink(s2, f"h{i}", bw=bw_host)
            
        # S3 Hosts
        for i in range(6, 8):
            self.addHost(f"h{i}", ip=f"10.0.3.{i}/24", defaultRoute="via 10.0.3.254")
            self.addLink(s3, f"h{i}", bw=bw_host)
            
        # S4 Hosts
        for i in range(8, 11):
            self.addHost(f"h{i}", ip=f"10.0.4.{i}/24", defaultRoute="via 10.0.4.254")
            self.addLink(s4, f"h{i}", bw=bw_host)

# =======================================
# MAIN RUN
# =======================================
def run():
    topo = IoTStaticTopo()
    net = Mininet(topo=topo, controller=OVSController, link=TCLink)
    net.start()

    g1, g2, cloud = net.get("g1", "g2", "cloud")

    # Bật IP Forwarding
    g1.cmd("sysctl -w net.ipv4.ip_forward=1")
    g2.cmd("sysctl -w net.ipv4.ip_forward=1")

    info("\n=== CONFIGURING STATIC ROUTES ===\n")
    
    g1.cmd("ip route add 10.0.4.0/24 via 10.0.10.2")
    g2.cmd("ip route add default via 10.0.10.1")
    cloud.cmd("ip route add 10.0.0.0/16 via 10.0.100.1")

    info("Routing configured. Waiting for switches...\n")
    time.sleep(2)

    # --- START IOT SERVICES ---
    info("\n=== STARTING IOT SIMULATION ===\n")

    CLOUD_IP = cloud.IP()
    CASE = "no_sdn"

# Start Cloud Server
    info(f"[*] Starting Cloud Server on {CLOUD_IP}...\n")
    cloud.cmd("mkdir -p /shared/raw /shared/logs")
    cloud.cmd(
        "python3 -u /app/traffic-generator/iot_server.py "
        f"--bind 0.0.0.0 "
        f"--out /shared/raw/{CASE}_server.csv "
        "> /shared/logs/iot_server.log 2>&1 &"
    )
    time.sleep(2)
# Start Sensors
    sensors = {
        'h1': 'temp', 'h2': 'humid', 'h3': 'motion',
        'h4': 'temp', 'h5': 'motion',
        'h6': 'humid', 'h7': 'temp',
        'h8': 'motion', 'h9': 'temp', 'h10': 'humid'
    }

    info("[*] Starting Sensors...\n")

    for hostname, stype in sensors.items():
        h = net.get(hostname)

        cmd = (
            "python3 -u /app/traffic-generator/iot_sensor.py "
            f"--name {hostname} "
            f"--server {CLOUD_IP} "
            f"--case {CASE} "
            f"--out /shared/raw/{CASE}_{hostname}.csv "
            f"> /shared/logs/{hostname}_sensor.log 2>&1 &"
        )

        h.cmd(cmd)
        info(f" -> {hostname} started ({stype})\n")

    info("\n------------------------------------------------\n")
    info("Simulation Running!\n")
    info(f"Cloud Server CSV: /shared/raw/{CASE}_server.csv\n")
    info("Sensor CSVs: /shared/raw/no_sdn_h*.csv\n")
    info("------------------------------------------------\n")

    if os.environ.get("INTERACTIVE", "0") == "1":
        CLI(net)
    else:
        total = int(os.environ.get("RUN_SECONDS", "90"))
        time.sleep(total + 5)
    
    os.system("pkill -f iot_server.py")
    os.system("pkill -f iot_sensor.py")
    net.stop()

if __name__ == "__main__":
    setLogLevel("info")
    os.system("mn -c") 
    run()
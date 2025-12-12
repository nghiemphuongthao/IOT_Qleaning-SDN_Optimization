import os, time, subprocess
from mininet.topo import Topo
from mininet.node import RemoteController
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.log import info

def setup_qos_on_port(port_name: str):
    max_rate = int(os.environ.get("LINK_MAX_RATE", "10000000"))
    q0 = int(os.environ.get("Q0_MAX_RATE", "2000000"))
    q1 = int(os.environ.get("Q1_MAX_RATE", "5000000"))
    q2 = int(os.environ.get("Q2_MAX_RATE", "10000000"))
    cmd = [
        "ovs-vsctl",
        "--", "set", "Port", port_name, "qos=@newqos",
        "--", "--id=@newqos", "create", "QoS", "type=linux-htb",
        f"other-config:max-rate={max_rate}",
        "queues:0=@q0", "queues:1=@q1", "queues:2=@q2",
        "--", "--id=@q0", "create", "Queue", f"other-config:max-rate={q0}",
        "--", "--id=@q1", "create", "Queue", f"other-config:max-rate={q1}",
        "--", "--id=@q2", "create", "Queue", f"other-config:max-rate={q2}",
    ]
    try:
        subprocess.check_call(cmd)
        info(f"*** [QoS] Applied HTB queues on {port_name}\n")
    except subprocess.CalledProcessError:
        info(f"*** [QoS] QoS exists or failed on {port_name} (ignored)\n")

class QoSAnomalyTopo(Topo):
    def build(self):
        s0 = self.addSwitch("s0", dpid="0000000000000001", protocols="OpenFlow13")
        s1 = self.addSwitch("s1", dpid="0000000000000100", protocols="OpenFlow13")
        s2 = self.addSwitch("s2", dpid="0000000000000200", protocols="OpenFlow13")
        s3 = self.addSwitch("s3", dpid="0000000000000300", protocols="OpenFlow13")
        s4 = self.addSwitch("s4", dpid="0000000000000400", protocols="OpenFlow13")
        cloud = self.addHost("cloud", ip="10.0.100.2/24")

        bw_core = 10
        self.addLink(s0, cloud, bw=bw_core)
        self.addLink(s0, s1, bw=bw_core)
        self.addLink(s0, s2, bw=bw_core)
        self.addLink(s0, s3, bw=bw_core)
        self.addLink(s0, s4, bw=bw_core)

        bw_host = 10
        for i in range(1,4):
            h = self.addHost(f"h{i}", ip=f"10.0.1.{i}/24"); self.addLink(s1, h, bw=bw_host)
        for i in range(4,6):
            h = self.addHost(f"h{i}", ip=f"10.0.2.{i}/24"); self.addLink(s2, h, bw=bw_host)
        for i in range(6,8):
            h = self.addHost(f"h{i}", ip=f"10.0.3.{i}/24"); self.addLink(s3, h, bw=bw_host)
        for i in range(8,11):
            h = self.addHost(f"h{i}", ip=f"10.0.4.{i}/24"); self.addLink(s4, h, bw=bw_host)

def run():
    ctrl_ip = os.environ.get("CONTROLLER_IP", "ryu-controller")
    ctrl_port = int(os.environ.get("CONTROLLER_PORT", "6653"))
    run_seconds = int(os.environ.get("RUN_SECONDS", "120"))

    topo = QoSAnomalyTopo()
    net = Mininet(topo=topo, controller=None, link=TCLink, autoSetMacs=True, autoStaticArp=True)
    net.addController("c0", controller=RemoteController, ip=ctrl_ip, port=ctrl_port)
    net.start()

    setup_qos_on_port("s0-eth1")

    cloud = net.get("cloud")
    cloud.cmd("mkdir -p /shared/raw")
    cloud.cmd("python3 /traffic-generator/iot_server.py --bind 0.0.0.0 --out /shared/raw/case3_server.csv &")
    time.sleep(1)

    for i in range(1,11):
        h = net.get(f"h{i}")
        h.cmd("mkdir -p /shared/raw")
        h.cmd(f"python3 /traffic-generator/iot_sensor.py --name h{i} --server {cloud.IP()} --case case3 --out /shared/raw/case3_client_h{i}.csv &")

    h10 = net.get("h10")
    h10.cmd(f"python3 /traffic-generator/iot_sensor.py --name h10b --server {cloud.IP()} --case case3 --bulk_boost 1 --out /shared/raw/case3_client_h10b.csv &")

    time.sleep(30)
    h1 = net.get("h1")
    h1.cmd(f"python3 /traffic-generator/iot_sensor.py --name h1_alarm --server {cloud.IP()} --case case3 --alarm_burst 1 --out /shared/raw/case3_client_h1_alarm.csv &")

    time.sleep(max(0, run_seconds - 30))
    cloud.cmd("pkill -f iot_server.py || true")
    for i in range(1,11):
        net.get(f"h{i}").cmd("pkill -f iot_sensor.py || true")
    net.stop()

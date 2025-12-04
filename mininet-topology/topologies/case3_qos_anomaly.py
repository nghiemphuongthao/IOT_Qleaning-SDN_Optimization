from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
import time, os

def run():
    print(">>> Case 3: Q-learning + QoS + Anomaly Traffic")

    net = Mininet(controller=RemoteController, switch=OVSSwitch, link=TCLink)

    c0 = net.addController("c0", ip="ryu-controller", port=6633)

    from .helpers.large_topo import build_large_topology
    build_large_topology(net)

    net.build()
    for sw in net.switches:
        sw.start([c0])

    # Create queues for QoS
    os.system("ovs-vsctl ... create queue ...")

    time.sleep(3)
    net.pingAll()
    CLI(net)
    net.stop()

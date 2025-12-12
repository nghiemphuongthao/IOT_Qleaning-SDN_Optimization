import os
import time
from mininet.net import Mininet
from mininet.cli import CLI
from mininet.node import RemoteController
from mininet.link import TCLink

from topologies.case1_static import StaticTopo
from topologies.case2_dynamic import DynamicTopo
from topologies.case3_qos_anomaly import QoSAnomalyTopo


# ===== ENV =====
CASE = os.getenv("CASE", "1")   # 0,1,2
MODE = os.getenv("MODE", "run") # run | demo

def build_topology():
    if CASE == "0":
        print("*** Case 0: No SDN (learning switch)")
        return StaticTopo(), None

    if CASE == "1":
        print("*** Case 1: SDN (rule-based)")
        return StaticTopo(), "sdn"

    if CASE == "2":
        print("*** Case 2: SDN + Q-learning")
        return DynamicTopo(), "sdn"

    print("*** Case 3: QoS anomaly (SDN)")
    return QoSAnomalyTopo(), "sdn"


def run():
    print(f">>> ENTER run(): CASE={CASE}, MODE={MODE}")

    topo, mode = build_topology()
    print(">>> Topology built")

    if mode is None:
        print(">>> Starting Mininet WITHOUT controller")
        net = Mininet(topo=topo, controller=None, link=TCLink)
    else:
        print(">>> Starting Mininet WITH controller")
        net = Mininet(
            topo=topo,
            controller=lambda name: RemoteController(
                name, ip="ryu-controller", port=6653
            ),
            link=TCLink
        )

    print(">>> Calling net.start()")
    net.start()
    print(">>> net.start() DONE")

    if MODE == "demo":
        print(">>> MODE == demo → ENTER CLI")
        CLI(net)
        print(">>> EXIT CLI")
    else:
        print(">>> MODE == run → SKIP CLI")

    print(">>> Calling net.stop()")
    net.stop()
    print(">>> net.stop() DONE")

if __name__ == "__main__":
    run()

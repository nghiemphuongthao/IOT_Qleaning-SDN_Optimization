import time
from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.link import TCLink
from mininet.log import info
from topo_common import IoTAccessTopo
from qos_utils import setup_qos_on_port

def run():
    info("*** Running Modern SDN (SDN + Q-learning)\n")

    net = Mininet(
        topo=IoTAccessTopo(),
        controller=lambda name: RemoteController(
            name, ip="ryu-controller", port=6653
        ),
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=True,
    )

    net.start()
    setup_qos_on_port("s0-eth1")

    cloud = net.get("cloud")
    cloud.cmd("python3 /traffic-generator/iot_server.py &")

    time.sleep(1)
    for i in range(1, 11):
        net.get(f"h{i}").cmd(
            f"python3 /traffic-generator/iot_sensor.py "
            f"--name h{i} --server {cloud.IP()} "
            f"--out /shared/raw/sdn_qlearning_h{i}.csv &"
        )

    time.sleep(90)
    net.stop()

if __name__ == "__main__":
    run()

import time
from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.link import TCLink
from mininet.log import info
from topo_common import IoTAccessTopo
from qos_utils import setup_qos_on_port   # giữ lại QoS nếu có
from mininet.cli import CLI


def run():
    info("*** Running Traditional SDN (Rule-based Controller)\n")

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
   # đảm bảo thư mục shared tồn tại
    cloud.cmd("mkdir -p /shared/raw")

    # chạy server + log
    cloud.cmd(
        "python3 /traffic-generator/iot_server.py "
        "--bind 0.0.0.0 "
        "--out /shared/raw/sdn_traditional_server.csv "
        "> /tmp/server.log 2>&1 &"
    )

    time.sleep(2)

    for i in range(1, 11):
        h = net.get(f"h{i}")
        h.cmd("mkdir -p /shared/raw")
        h.cmd(
            f"python3 /traffic-generator/iot_sensor.py "
            f"--name h{i} "
            f"--server {cloud.IP()} "
            f"--out /shared/raw/sdn_traditional_client_h{i}.csv "
            f"> /tmp/h{i}.log 2>&1 &"
        )
    time.sleep(90)
    net.pingAll()
    CLI(net)
    net.stop()

if __name__ == "__main__":
    run()

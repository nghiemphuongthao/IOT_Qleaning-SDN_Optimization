import time
from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.link import TCLink
from mininet.log import info
from topo_common import IoTAccessTopo

def run():
    info("*** Running No SDN baseline (L2 switching)\n")

    net = Mininet(
        topo=IoTAccessTopo(),
        controller=None,                 # ❌ NO CONTROLLER
        switch=OVSSwitch,                # L2 learning switch
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=True,
        build=True
    )

    net.start()

    # Start IoT server
    cloud = net.get("cloud")
    cloud.cmd("mkdir -p /shared/raw")
    cloud.cmd(
        "python3 /traffic-generator/iot_server.py "
        "--bind 0.0.0.0 "
        "--out /shared/raw/no_sdn_server.csv &"
    )

    time.sleep(1)

    # Start IoT clients
    for i in range(1, 11):
        net.get(f"h{i}").cmd(
            f"python3 /traffic-generator/iot_sensor.py "
            f"--name h{i} "
            f"--server {cloud.IP()} "
            f"--out /shared/raw/no_sdn_client_h{i}.csv &"
        )

    info("*** Traffic running for 90 seconds\n")
    time.sleep(90)

    # Cleanup
    cloud.cmd("pkill -f iot_server.py || true")
    for i in range(1, 11):
        net.get(f"h{i}").cmd("pkill -f iot_sensor.py || true")

    net.stop()
    info("*** No SDN experiment finished\n")

if __name__ == "__main__":
    run()

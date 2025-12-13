from mininet.net import Mininet
from mininet.node import RemoteController, OVSKernelSwitch
from topo_common import SDNIoTTopo
from mininet.cli import CLI

def run():
    topo = SDNIoTTopo()
    net = Mininet(
        topo=topo,
        controller=None,
        switch=OVSKernelSwitch,
    )

    net.addController('c0',
        controller=RemoteController,
        ip='ryu-controller',
        port=6653)

    net.start()
    CLI(net)
    net.stop()

if __name__ == "__main__":
    run()

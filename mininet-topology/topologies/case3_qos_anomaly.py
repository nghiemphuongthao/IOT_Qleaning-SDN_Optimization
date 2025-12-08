from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel, info
import time, os

os.system("mn -c")

class Case3Topo(Topo):
    def build(self):

        # Backbone switches
        g1 = self.addSwitch("g1", dpid="0000000000000100")
        g2 = self.addSwitch("g2", dpid="0000000000000200")
        g3 = self.addSwitch("g3", dpid="0000000000000300")

        # Access switches
        s1 = self.addSwitch("s1")
        s2 = self.addSwitch("s2")
        s3 = self.addSwitch("s3")
        s4 = self.addSwitch("s4")

        # Cloud server
        cloud = self.addHost("cloud", ip="10.0.0.254/24")

        # Backbone links
        self.addLink(g1, g2, bw=50)
        self.addLink(g1, g3, bw=50)

        # Uplink to cloud
        self.addLink(g1, cloud, bw=10)
        self.addLink(g3, cloud, bw=10)

        # IoT zones
        zone_map = {
            "s1": [1, 2, 3],
            "s2": [4, 5],
            "s3": [6, 7],
            "s4": [8, 9, 10]
        }

        for sw, hosts in zone_map.items():
            for h in hosts:
                host = self.addHost(f"h{h}", ip=f"10.0.0.{h}/24")
                self.addLink(sw, host, bw=10)

        # Interconnect access switches
        self.addLink(g1, s1, bw=10)
        self.addLink(g1, s2, bw=10)
        self.addLink(g2, s3, bw=10)
        self.addLink(g3, s4, bw=10)


def run():
    topo = Case3Topo()
    net = Mininet(
        topo=topo,
        controller=None,
        link=TCLink,
        switch=OVSKernelSwitch
    )

    info("*** Connecting Controller…\n")
    net.addController("c0", RemoteController,
        ip="ryu-controller", port=6653)

    net.start()
    info("\n=== CASE 3 TOPO STARTED ===\n")

    net.pingAll()
    CLI(net)
    time.sleep(10)
    net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    run()

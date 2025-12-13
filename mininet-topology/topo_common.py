from mininet.topo import Topo
from mininet.node import Node

class LinuxRouter(Node):
    def config(self, **params):
        super().config(**params)
        self.cmd('sysctl -w net.ipv4.ip_forward=1')

    def terminate(self):
        self.cmd('sysctl -w net.ipv4.ip_forward=0')
        super().terminate()


class SDNIoTTopo(Topo):
    def build(self):
        # Routers / Switches
        g1 = self.addNode('g1', cls=LinuxRouter)
        g2 = self.addNode('g2', cls=LinuxRouter)
        g3 = self.addNode('g3', cls=LinuxRouter)

        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')
        s3 = self.addSwitch('s3')
        s4 = self.addSwitch('s4')

        cloud = self.addHost('cloud', ip='10.0.0.254/24')

        # Links
        self.addLink(g1, g2)
        self.addLink(g1, g3)
        self.addLink(g1, s1)
        self.addLink(g1, s2)
        self.addLink(g2, s3)
        self.addLink(g3, s4)

        self.addLink(g1, cloud)

        # Hosts
        for i in range(1, 11):
            h = self.addHost(f'h{i}', ip=f'10.0.0.{i}/24')
            sw = s1 if i <= 3 else s2 if i <= 5 else s3 if i <= 7 else s4
            self.addLink(sw, h)

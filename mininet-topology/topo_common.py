from mininet.topo import Topo

class IoTAccessTopo(Topo):
    def build(self):
        s0 = self.addSwitch("s0", dpid="0000000000000001", protocols="OpenFlow13")
        s1 = self.addSwitch("s1", dpid="0000000000000100", protocols="OpenFlow13")
        s2 = self.addSwitch("s2", dpid="0000000000000200", protocols="OpenFlow13")
        s3 = self.addSwitch("s3", dpid="0000000000000300", protocols="OpenFlow13")
        s4 = self.addSwitch("s4", dpid="0000000000000400", protocols="OpenFlow13")

        cloud = self.addHost("cloud", ip="10.0.100.2/24")

        bw = 10
        self.addLink(s0, cloud, bw=bw)
        self.addLink(s0, s1, bw=bw)
        self.addLink(s0, s2, bw=bw)
        self.addLink(s0, s3, bw=bw)
        self.addLink(s0, s4, bw=bw)

        for i in range(1, 4):
            self.addLink(s1, self.addHost(f"h{i}", ip=f"10.0.1.{i}/24"), bw=bw)
        for i in range(4, 6):
            self.addLink(s2, self.addHost(f"h{i}", ip=f"10.0.2.{i}/24"), bw=bw)
        for i in range(6, 8):
            self.addLink(s3, self.addHost(f"h{i}", ip=f"10.0.3.{i}/24"), bw=bw)
        for i in range(8, 11):
            self.addLink(s4, self.addHost(f"h{i}", ip=f"10.0.4.{i}/24"), bw=bw)

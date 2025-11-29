#!/usr/bin/env python3

from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink
import os
import time

def create_sdn_network():
    """Create SDN network with similar structure to static routing topology"""
    mode = os.getenv('MODE', 'sdn')
    controller_ip = os.getenv('CONTROLLER_IP', '127.0.0.1')

    info(f'*** Creating {mode.upper()} Network with SDN Controller\n')

    net = Mininet(switch=OVSSwitch, controller=RemoteController, link=TCLink)

    info(f'*** Adding SDN controller at {controller_ip}\n')
    c0 = net.addController('c0', controller=RemoteController,
                           ip=controller_ip, port=6633)

    info('*** Adding switches (simulating routers and switches)\n')

    # Core switches (use valid names so Mininet can generate DPID)
    gw = net.addSwitch('s100')   # was 'gw'
    r1 = net.addSwitch('s101')   # was 'r1'
    r2 = net.addSwitch('s102')   # was 'r2'
    r3 = net.addSwitch('s103')   # was 'r3'

    # Access switches
    s1 = net.addSwitch('s1')
    s2 = net.addSwitch('s2')
    s3 = net.addSwitch('s3')
    s4 = net.addSwitch('s4')

    info('*** Adding hosts\n')

    cloud = net.addHost('cloud', ip='10.0.100.2/24', defaultRoute='via 10.0.100.1')

    hosts_s1 = [net.addHost(f'h{i}', ip=f'10.0.1.{i}/24', defaultRoute='via 10.0.1.254') for i in range(1, 4)]
    hosts_s2 = [net.addHost(f'h{i}', ip=f'10.0.2.{i}/24', defaultRoute='via 10.0.2.1') for i in range(4, 6)]
    hosts_s3 = [net.addHost(f'h{i}', ip=f'10.0.3.{i}/24', defaultRoute='via 10.0.3.1') for i in range(6, 8)]
    hosts_s4 = [net.addHost(f'h{i}', ip=f'10.0.4.{i}/24', defaultRoute='via 10.0.4.1') for i in range(8, 11)]

    info('*** Creating links\n')

    # Core links
    net.addLink(gw, r1)
    net.addLink(gw, r2)
    net.addLink(gw, r3)

    # Routers → access switches
    net.addLink(r1, s1)
    net.addLink(r2, s2)
    net.addLink(r2, s3)
    net.addLink(r3, s4)

    # Gateway → cloud
    net.addLink(gw, cloud)

    # Access switch to hosts
    for h in hosts_s1: net.addLink(s1, h)
    for h in hosts_s2: net.addLink(s2, h)
    for h in hosts_s3: net.addLink(s3, h)
    for h in hosts_s4: net.addLink(s4, h)

    info('*** Starting network\n')
    net.build()
    net.start()

    info('*** Configuring switch IP addresses (simulating router interfaces)\n')

    # make sure eth index still matches original order
    gw.cmd('ifconfig s100-eth0 10.0.10.1/24')
    gw.cmd('ifconfig s100-eth1 10.0.20.1/24')
    gw.cmd('ifconfig s100-eth2 10.0.30.1/24')
    gw.cmd('ifconfig s100-eth3 10.0.100.1/24')

    r1.cmd('ifconfig s101-eth0 10.0.10.2/24')
    r1.cmd('ifconfig s101-eth1 10.0.1.254/24')

    r2.cmd('ifconfig s102-eth0 10.0.20.2/24')
    r2.cmd('ifconfig s102-eth1 10.0.2.1/24')
    r2.cmd('ifconfig s102-eth2 10.0.3.1/24')

    r3.cmd('ifconfig s103-eth0 10.0.30.2/24')
    r3.cmd('ifconfig s103-eth1 10.0.4.1/24')

    # Enable forwarding
    for sw in [gw, r1, r2, r3]:
        sw.cmd('sysctl -w net.ipv4.ip_forward=1')

    info('*** Waiting for controller connection\n')
    time.sleep(10)

    info('*** Connectivity test\n')
    net.pingAll()

    info('*** Running CLI\n')
    CLI(net)

    info('*** Stopping network\n')
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    create_sdn_network()

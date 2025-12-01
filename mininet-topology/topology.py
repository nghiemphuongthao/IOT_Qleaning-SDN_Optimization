#!/usr/bin/env python3
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink
import os, time

def create_network():
    MODE = os.getenv('TOPO_CASE', 'standalone')
    CONTROLLER_IP = os.getenv('CONTROLLER_IP', 'ryu-controller')
    info(f'*** Create network (mode={MODE})\n')

    if MODE == 'standalone':
        info('*** Standalone mode, no controller\n')
        net = Mininet(switch=OVSSwitch, link=TCLink, autoSetMacs=True)
        controller = None
    else:
        info(f'*** Controller mode ({MODE}), controller at {CONTROLLER_IP}\n')
        net = Mininet(switch=OVSSwitch, controller=RemoteController, link=TCLink)
        controller = net.addController('c0', controller=RemoteController, ip=CONTROLLER_IP, port=6633)

    # Switches
    gw = net.addSwitch('s10')
    r1 = net.addSwitch('s1')
    r2 = net.addSwitch('s2')
    r3 = net.addSwitch('s3')
    s1 = net.addSwitch('s11')
    s2 = net.addSwitch('s12')
    s3 = net.addSwitch('s13')
    s4 = net.addSwitch('s14')

    # Cloud host
    cloud = net.addHost('cloud', ip='10.0.100.2/24')

    # Hosts
    hosts_s1 = [net.addHost(f'h{i}', ip=f'10.0.1.{i}/24') for i in range(1,4)]
    hosts_s2 = [net.addHost(f'h{i}', ip=f'10.0.2.{i}/24') for i in range(4,6)]
    hosts_s3 = [net.addHost(f'h{i}', ip=f'10.0.3.{i}/24') for i in range(6,8)]
    hosts_s4 = [net.addHost(f'h{i}', ip=f'10.0.4.{i}/24') for i in range(8,11)]

    # Links
    net.addLink(gw, r1)
    net.addLink(gw, r2)
    net.addLink(gw, r3)
    net.addLink(r1, s1)
    net.addLink(r2, s2)
    net.addLink(r2, s3)
    net.addLink(r3, s4)
    net.addLink(gw, cloud)

    for h in hosts_s1: net.addLink(s1, h)
    for h in hosts_s2: net.addLink(s2, h)
    for h in hosts_s3: net.addLink(s3, h)
    for h in hosts_s4: net.addLink(s4, h)

    info('*** Starting network\n')
    net.build()

    # Chạy controller hoặc đặt switch standalone
    if controller:
        net.start()
        info('*** Wait for controller and stabilize\n')
        time.sleep(8)
    else:
        # Standalone mode: set switches to normal mode
        net.start()
        for sw in net.switches:
            sw.cmd('ovs-vsctl set-controller {} none'.format(sw.name))
            sw.cmd('ovs-vsctl set-fail-mode {} standalone'.format(sw.name))

    info('*** Pingall\n')
    net.pingAll()
    info('*** Running CLI\n')
    CLI(net)
    info('*** Stopping network\n')
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    create_network()
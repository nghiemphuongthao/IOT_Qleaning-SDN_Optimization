#!/usr/bin/env python3

from mininet.net import Mininet
from mininet.node import Controller, RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink
import os
import time

def create_network():
    net = Mininet(controller=RemoteController, link=TCLink)

    mode = os.getenv('MODE', 'baseline')
    controller_ip = os.getenv('CONTROLLER_IP', '172.20.0.10')
    controller_port = int(os.getenv('CONTROLLER_PORT', 6633))

    info(f'*** Creating network for mode: {mode}\n')
    
    if mode == 'baseline':
        info('*** Using baseline configuration (traditional networking)\n')
        # Minimal SDN features
        c0 = net.addController('c0', controller=RemoteController, 
                              ip=controller_ip, port=controller_port)
    elif mode == 'sdn':
        info('*** Using SDN configuration\n')
        # Full SDN features
        c0 = net.addController('c0', controller=RemoteController,
                              ip=controller_ip, port=controller_port)
    elif mode == 'sdn_qlearning':
        info('*** Using SDN + Q-learning configuration\n')
        # SDN with optimization hooks
        c0 = net.addController('c0', controller=RemoteController,
                              ip=controller_ip, port=controller_port)

    # Common topology for all cases
    info('*** Adding switches\n')
    s1 = net.addSwitch('s1')
    s2 = net.addSwitch('s2')
    s3 = net.addSwitch('s3')
    s4 = net.addSwitch('s4')

    info('*** Adding hosts\n')
    hosts = []
    for i in range(1, 9):
        h = net.addHost(f'h{i}', ip=f'10.0.0.{i}')
        hosts.append(h)

    info('*** Creating links\n')
    net.addLink(hosts[0], s1)
    net.addLink(hosts[1], s1)
    net.addLink(hosts[2], s2)
    net.addLink(hosts[3], s2)
    net.addLink(hosts[4], s3)
    net.addLink(hosts[5], s3)
    net.addLink(hosts[6], s4)
    net.addLink(hosts[7], s4)
    
    net.addLink(s1, s2)
    net.addLink(s2, s3)
    net.addLink(s3, s4)

    info('*** Starting network\n')
    net.build()
    c0.start()
    s1.start([c0])
    s2.start([c0])
    s3.start([c0])
    s4.start([c0])

    # Mode-specific initialization
    if mode == 'sdn_qlearning':
        info('*** Waiting for Q-learning agent initialization\n')
        time.sleep(10)

    info('*** Running CLI\n')
    CLI(net)

    info('*** Stopping network\n')
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    create_network()
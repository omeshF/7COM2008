#!/usr/bin/python3
from mininet.net import Mininet
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info

from mininet.net import Mininet
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
 
 
def onos_topo():
    net = Mininet(switch=OVSKernelSwitch)
 
    info("*** Connecting to ONOS Controller ***\n")
    c0 = net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6653)
 
    info("*** Creating Nodes ***\n")
    s1 = net.addSwitch('s1')
    s2 = net.addSwitch('s2')
    s3 = net.addSwitch('s3')
    s4 = net.addSwitch('s4')
 
    h1 = net.addHost('h1', ip='10.0.0.1/24', mac='00:00:00:00:00:01')
    h2 = net.addHost('h2', ip='10.0.0.2/24', mac='00:00:00:00:00:02')
    h3 = net.addHost('h3', ip='10.0.0.3/24', mac='00:00:00:00:00:03')
    h4 = net.addHost('h4', ip='10.0.0.4/24', mac='00:00:00:00:00:04')
 
    info("*** Creating Links ***\n")
    # Ring of switches
    net.addLink(s1, s2)
    net.addLink(s2, s3)
    net.addLink(s3, s4)
    net.addLink(s4, s1)
 
    # Hosts: two on s1's side, two on s3's side (opposite the ring)
    net.addLink(h1, s1)
    net.addLink(h2, s1)
    net.addLink(h3, s3)
    net.addLink(h4, s3)
 
    net.start()
    info("*** Network Ready! ***\n")
    CLI(net)
    net.stop()
 
 
if __name__ == '__main__':
    setLogLevel('info')
    onos_topo()
 

#!/usr/bin/python3
from mininet.net import Mininet
from mininet.node import OVSKernelSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink

def adhoc():
    # No controller needed
    net = Mininet(controller=None, link=TCLink)
    
    info("*** Adding OVS Switch in Standalone Mode ***\n")
    # failMode='standalone' makes OVS act like a dumb physical switch
    s1 = net.addSwitch('s1', cls=OVSKernelSwitch, failMode='standalone')
    
    info("*** Adding 4 Mesh Nodes ***\n")
    A = net.addHost('A', ip='10.0.0.1/24')
    B = net.addHost('B', ip='10.0.0.2/24')
    C = net.addHost('C', ip='10.0.0.3/24')
    D = net.addHost('D', ip='10.0.0.4/24')
    
    for h in [A, B, C, D]:
        net.addLink(h, s1)
        
    net.start()
    info("*** Adhoc Mesh Network Ready! ***\n")
    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    adhoc()

#!/usr/bin/env python
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Controller, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
 
 
class MyTopo(Topo):
    "Simple topology example."
 
    def __init__(self):
        "Create custom topo."
 
        # Initialize topology
        Topo.__init__(self)
 
        # Add hosts and switches
        s1 = self.addSwitch('s1')
        h1 = self.addHost('h1', ip='10.0.0.1/24')
        h2 = self.addHost('h2', ip='10.0.0.2/24')
        h3 = self.addHost('h3', ip='10.0.0.3/24')
        #Add h4

        # Add links
        self.addLink(h1, s1)
        self.addLink(h2, s1)
        self.addLink(h3, s1)
    	# Connect h4 to s1
	    
	
 
topos = {'mytopo': (lambda: MyTopo())}
 
 
def run():
    setLogLevel('info')
    topo = MyTopo()
    net = Mininet(topo=topo, controller=Controller, switch=OVSSwitch)
    net.start()
 
    info('*** Running CLI - try: h1 ping h2, or "pingall"\n')
    info('*** Type "exit" to quit\n\n')
    CLI(net)
 
    net.stop()
 
 
if __name__ == '__main__':
    run()
 

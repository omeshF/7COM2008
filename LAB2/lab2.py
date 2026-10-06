#!/usr/bin/env python

from mininet.log import setLogLevel, info
from mn_wifi.cli import CLI
from mn_wifi.net import Mininet_wifi
 
 
def topology():
    "Create a network."
    net = Mininet_wifi()
 
    info("*** Creating nodes\n")
    sta1 = net.addStation('sta1', mac='00:00:00:00:00:02', ip='10.0.0.2/8', position='10,40,0')
    sta2 = net.addStation('sta2', mac='00:00:00:00:00:03', ip='10.0.0.3/8', position='60,40,0')
    TCPS = net.addStation('TCPS', mac='00:00:00:00:00:04', ip='10.0.0.4/8', position='20,20,0')
    UDPS = net.addStation('UDPS', mac='00:00:00:00:00:05', ip='10.0.0.5/8', position='60,20,0')
    ap1 = net.addAccessPoint('ap1', mac='00:00:00:00:10:02', ssid='ssid-ap1',
                              mode='g', channel='1', position='15,30,0', band='5')
    ap2 = net.addAccessPoint('ap2', mac='00:00:00:00:10:03', ssid='ssid-ap2',
                              mode='g', channel='6', position='55,30,0', band='5')
 
    c1 = net.addController('c1')
    net.setPropagationModel(model="logDistance", exp=5)
 
    info("*** Configuring wifi nodes\n")
    net.configureWifiNodes()
 
    info("*** Bridging APs and plotting\n")
    net.addLink(ap1, ap2)
    net.plotGraph(max_x=200, max_y=200)
 
    info("*** Setting up mobility scenario\n")
    net.startMobility(time=0)
    net.mobility(sta1, 'start', time=5, position='10,40,0')
    net.mobility(sta1, 'stop', time=15, position='60,40,0')
    net.mobility(sta2, 'start', time=16, position='60,40,0')
    net.mobility(sta2, 'stop', time=25, position='10,40,0')
    net.stopMobility(time=30)
 
    info("*** Starting network\n")
    net.build()
    ap1.start([c1])
    ap2.start([c1])
 
    info("*** Running CLI\n")
    info("*** Try: sta1 ping sta2, or iperf between TCPS/UDPS and a moving station\n")
    CLI(net)
 
    info("*** Stopping network\n")
    net.stop()
 
 
if __name__ == '__main__':
    setLogLevel('info')
    topology()
 

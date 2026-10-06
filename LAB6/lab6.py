#!/usr/bin/env python
from mininet.net import Mininet
from mininet.node import Controller, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info
 
from vpn_lib import (set_ip, set_default_gateway, enable_forwarding,
                     add_vpn, remove_vpn, ping_test)
 
 
# ---------------------------------------------------------------------------
# STEP 1: build the topology
# ---------------------------------------------------------------------------
 
def create_network():
    net = Mininet(controller=Controller, link=TCLink,
                  switch=OVSSwitch, autoSetMacs=True)
    # Pinned to a non-default port so this lab is immune to ONOS (or any
    # other controller) being left running on 6653 from a different lab -
    # this lab is self-contained and needs no external controller at all.
    net.addController('c0', port=6634)
 
    s_remote = net.addSwitch('s1')
    s_main = net.addSwitch('s2')
    s_internet = net.addSwitch('s3')
 
    remote = net.addHost('remote', ip='192.168.10.10/24')
    remote_gw = net.addHost('remote_gw', ip=None)
    main = net.addHost('main', ip='10.0.0.10/24')
    main_gw = net.addHost('main_gw', ip=None)
 
    # Remote site
    net.addLink(remote, s_remote)
    net.addLink(remote_gw, s_remote, intfName1='remote_gw-lan')
    net.addLink(remote_gw, s_internet, intfName1='remote_gw-wan')
 
    # Main site
    net.addLink(main, s_main)
    net.addLink(main_gw, s_main, intfName1='main_gw-lan')
    net.addLink(main_gw, s_internet, intfName1='main_gw-wan')
 
    return net
 
 
# ---------------------------------------------------------------------------
# STEP 2: give the gateways their addresses and make them routers
# ---------------------------------------------------------------------------
 
def configure_addresses(net):
    remote, remote_gw = net['remote'], net['remote_gw']
    main, main_gw = net['main'], net['main_gw']
 
    set_ip(remote_gw, 'remote_gw-lan', '192.168.10.1/24')
    set_ip(remote_gw, 'remote_gw-wan', '203.0.113.1/24')
    set_ip(main_gw, 'main_gw-lan', '10.0.0.1/24')
    set_ip(main_gw, 'main_gw-wan', '203.0.113.2/24')
 
    set_default_gateway(remote, '192.168.10.1')
    set_default_gateway(main, '10.0.0.1')
 
    enable_forwarding(remote_gw)
    enable_forwarding(main_gw)
 
 
# ---------------------------------------------------------------------------
# STEP 3: add VPNs  <-- the part learners edit
# ---------------------------------------------------------------------------
 
def add_vpn_connections(net):
    add_vpn(net['main_gw'], net['remote_gw'],
            wan_ip1='203.0.113.2', wan_ip2='203.0.113.1',
            lan1='10.0.0.0/24', lan2='192.168.10.0/24',
            encrypt=True)
 
 
# ---------------------------------------------------------------------------
# STEP 4: test
# ---------------------------------------------------------------------------
 
def run_tests(net):
    info('*** Testing\n')
    ping_test(net['main_gw'], '10.10.10.2', 'tunnel endpoint (main_gw -> remote_gw)')
    ping_test(net['main'], '192.168.10.10', 'main -> remote (across VPN)')
    ping_test(net['remote'], '10.0.0.10', 'remote -> main (across VPN)')
 
 
# ---------------------------------------------------------------------------
 
def main():
    setLogLevel('info')
    net = create_network()
    net.start()
 
    configure_addresses(net)
    add_vpn_connections(net)
    run_tests(net)
 
    CLI(net)
 
    remove_vpn(net['main_gw'], net['remote_gw'])
    net.stop()
 
 
if __name__ == '__main__':
    main()
 

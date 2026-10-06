#!/usr/bin/env python

from mininet.net import Mininet
from mininet.node import Controller, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info

from vpn_render_lib import vpn_connect, vpn_request, vpn_disconnect, show_tls_info

RENDER_URL = 'https://ztna-gateway-a8js.onrender.com/'   # <-- set this
VPN_PSK = 'k8X#9mP2$vL7nQ4%wK1*zJ6@hF3!gD5-bC8_yT0+rE2'                    # <-- must match Render's VPN_PSK


def create_network():
    net = Mininet(controller=Controller, switch=OVSSwitch, autoSetMacs=True)
    # Pinned to a non-default port so this lab doesn't accidentally attach
    # to ONOS (or anything else) if it's still running from another lab.
    net.addController('c0', port=6634)
    h1 = net.addHost('h1')
    s1 = net.addSwitch('s1')
    net.addLink(h1, s1)
    # Real internet access (and DNS resolution) for h1, via the Ubuntu
    # host's own network - without this, h1 is isolated and can't reach
    # RENDER_URL at all (DNS lookups fail before a connection is even tried).
    net.addNAT('nat0', connect=s1)
    return net


def main():
    setLogLevel('info')
    net = create_network()
    net.start()
    net['nat0'].configDefault()
    h1 = net['h1']

    # configDefault() sets up NAT/MASQUERADE on nat0 but does not reliably
    # add a default route on h1 (confirmed: 'h1 ip route' showed only the
    # directly-connected 10.0.0.0/8 route, nothing else - every external
    # destination, DNS servers included, was ENETUNREACH as a result).
    # Add it explicitly, using nat0's actual IP rather than a hardcoded one.
    h1.cmd('ip route add default via {}'.format(net['nat0'].IP()))

    # No DNS setup needed here: h1 can't reliably resolve names itself
    # (mininet hosts share the real /etc/resolv.conf, which
    # systemd-resolved keeps rewriting back to its own loopback stub -
    # see the long comment in vpn_render_lib.py). vpn_connect() and
    # friends resolve RENDER_URL from this controller process instead,
    # where DNS is unaffected by that, and hand h1 the resulting IP
    # directly.
    info('*** --- TLS handshake evidence ---\n')
    show_tls_info(h1, RENDER_URL)
    info('*** Connecting to the VPN gateway\n')
    token = vpn_connect(h1, RENDER_URL, VPN_PSK)

    if token:
        info('*** Connected once - now reaching every resource through the same session\n')
        vpn_request(h1, RENDER_URL, token, 'finance-app')
        vpn_request(h1, RENDER_URL, token, 'hr-app')
        vpn_request(h1, RENDER_URL, token, 'devtools')

    CLI(net)
    info('*** --- manual VPN demo tests ---\n')

    info('*** Test 1: reconnect and reuse the SAME token against two more resources\n')
    demo_token = vpn_connect(h1, RENDER_URL, VPN_PSK)
    if demo_token:
        vpn_request(h1, RENDER_URL, demo_token, 'hr-app')
        vpn_request(h1, RENDER_URL, demo_token, 'devtools')

    info('*** Test 2: wrong PSK on purpose - expect a connect failure\n')
    vpn_connect(h1, RENDER_URL, 'wrong-psk-on-purpose')

    info('*** Test 3: disconnect, then try to reuse the same token - expect failure\n')
    if demo_token:
        vpn_disconnect(h1, RENDER_URL, demo_token)
        vpn_request(h1, RENDER_URL, demo_token, 'finance-app')

    if token:
        vpn_disconnect(h1, RENDER_URL, token)
    net.stop()


if __name__ == '__main__':
    main()

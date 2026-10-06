#!/usr/bin/env python


from mininet.net import Mininet
from mininet.node import Controller, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info

from ztna_lib import ztna_authorize, ztna_request, ztna_audit

ZTNA_URL = 'https://ztna-gateway-a8js.onrender.com/'   # <-- same Render app as task 3


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
    # ZTNA_URL at all.
    net.addNAT('nat0', connect=s1)
    return net


def run_experiments(net):
    h1 = net['h1']

    info('*** alice asks for finance-app (in her policy) - expect ALLOW\n')
    token = ztna_authorize(h1, ZTNA_URL, 'alice', 'compliant', 'finance-app')
    if token:
        ztna_request(h1, ZTNA_URL, token, 'finance-app')

        info('*** Reusing that SAME token against hr-app - expect a scope refusal\n')
        ztna_request(h1, ZTNA_URL, token, 'hr-app')

    info('*** alice asks for hr-app (NOT in her policy) - expect DENY\n')
    ztna_authorize(h1, ZTNA_URL, 'alice', 'compliant', 'hr-app')

    info('*** bob asks for devtools with bad posture - expect DENY\n')
    ztna_authorize(h1, ZTNA_URL, 'bob', 'jailbroken', 'devtools')

    info('*** bob asks for devtools, compliant - expect ALLOW\n')
    token = ztna_authorize(h1, ZTNA_URL, 'bob', 'compliant', 'devtools')
    if token:
        ztna_request(h1, ZTNA_URL, token, 'devtools')

    info('*** Recent gateway decisions:\n')
    for entry in ztna_audit(h1, ZTNA_URL):
        info('    {}\n'.format(entry))


def main():
    setLogLevel('info')
    net = create_network()
    net.start()
    net['nat0'].configDefault()

    # configDefault() sets up NAT/MASQUERADE on nat0 but does not reliably
    # add a default route on h1 (confirmed: 'h1 ip route' showed only the
    # directly-connected 10.0.0.0/8 route, nothing else - every external
    # destination, DNS servers included, was ENETUNREACH as a result).
    # Add it explicitly, using nat0's actual IP rather than a hardcoded one.
    net['h1'].cmd('ip route add default via {}'.format(net['nat0'].IP()))

    # No DNS setup needed here: h1 can't reliably resolve names itself
    # (mininet hosts share the real /etc/resolv.conf, which
    # systemd-resolved keeps rewriting back to its own loopback stub -
    # see the long comment in ztna_lib.py). ztna_authorize() and friends
    # resolve ZTNA_URL from this controller process instead, where DNS is
    # unaffected by that, and hand h1 the resulting IP directly.

    run_experiments(net)

    CLI(net)
    net.stop()


if __name__ == '__main__':
    main()

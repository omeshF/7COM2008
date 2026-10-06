#!/usr/bin/env python


import socket
try:
    from urllib.parse import urlparse   # Python 3
except ImportError:
    from urlparse import urlparse       # Python 2

from mininet.log import info

# Demo keys only. Never reuse hard-coded keys outside a lab.
DEFAULT_ENC_KEY = "0123456789abcdef0123456789abcdef"                                  # 128-bit AES
DEFAULT_AUTH_KEY = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # 256-bit HMAC-SHA256


# ---------------------------------------------------------------------------
# Basic node configuration
# ---------------------------------------------------------------------------

def set_ip(node, intf, cidr):
    """Assign an IP address (e.g. '10.0.0.1/24') to an interface."""
    node.cmd('ip addr add {} dev {}'.format(cidr, intf))
    node.cmd('ip link set {} up'.format(intf))


def set_default_gateway(host, gw_ip):
    """Point a host's default route at its gateway."""
    host.cmd('ip route add default via {}'.format(gw_ip))


def enable_forwarding(node):
    """Allow a node to forward packets between its interfaces (act as a router)."""
    node.cmd('sysctl -w net.ipv4.ip_forward=1 > /dev/null')


# ---------------------------------------------------------------------------
# Resolving a "LAN" that's actually a URL (e.g. a Render app)
# ---------------------------------------------------------------------------

def resolve_host(target):
    """
    Turn lan1/lan2 into something ip route understands.

    Accepts, and returns unchanged if it's already routable:
        '10.0.0.0/24'                  -> '10.0.0.0/24'         (CIDR, untouched)

    Accepts and resolves via DNS if it's a URL or bare hostname:
        'https://myapp.onrender.com'   -> '<resolved-ip>/32'
        'myapp.onrender.com'           -> '<resolved-ip>/32'

    Caveat: this resolves DNS from wherever this controller script runs, not
    from inside the gateway node's namespace. Fine for a stable Render
    hostname; if you need the node's own view of DNS, resolve inside the
    node with gw.cmd('getent hosts <host>') instead.

    Bigger caveat: resolving the address is not the same as having a VPN
    peer there. GRE/IPsec need a cooperating gateway that can run
    'ip tunnel' / 'ip xfrm' on the other end - a PaaS app (like a bare
    Render web service) can't do that. Use a URL for lan2 only when
    remote_gw is a host you control that sits in front of / forwards to
    that URL; the tunnel still terminates on remote_gw, not on Render.
    """
    if target.startswith(('http://', 'https://')):
        host = urlparse(target).hostname
    elif '/' in target:
        return target  # already CIDR, e.g. '10.0.0.0/24' - leave alone
    else:
        host = target  # bare hostname, e.g. 'myapp.onrender.com'

    ip = socket.gethostbyname(host)
    return '{}/32'.format(ip)


# ---------------------------------------------------------------------------
# VPN building blocks
# ---------------------------------------------------------------------------

def add_gre_tunnel(gw, name, local_wan, remote_wan, tunnel_ip):
    """
    Create one end of a GRE tunnel on gateway `gw`.

    name        tunnel interface name, e.g. 'gre1'
    local_wan   this gateway's public IP (no prefix), e.g. '203.0.113.2'
    remote_wan  the other gateway's public IP (no prefix)
    tunnel_ip   this end's address inside the tunnel, e.g. '10.10.10.1/30'
    """
    gw.cmd('ip tunnel add {} mode gre remote {} local {} ttl 255'.format(
        name, remote_wan, local_wan))
    gw.cmd('ip addr add {} dev {}'.format(tunnel_ip, name))
    gw.cmd('ip link set {} up'.format(name))


def add_ipsec(gw, local_wan, remote_wan, spi_out, spi_in, enc_key, auth_key):
    """
    Encrypt (ESP, transport mode) all traffic between local_wan and remote_wan
    on gateway `gw`. Run once on each gateway, with spi_out / spi_in swapped
    on the other end.

    spi_out   SPI used for packets leaving this gateway, e.g. '0x200'
    spi_in    SPI expected on packets arriving at this gateway, e.g. '0x100'
    """
    # Algorithm names are double-quoted: node.cmd() runs this through a
    # shell, and unquoted parentheses in 'hmac(sha256)' / 'cbc(aes)' are
    # shell metacharacters - bash throws a syntax error on them before 'ip'
    # ever runs, which silently leaves 'ip xfrm state add' un-executed
    # (the policy-add call has no parentheses, so it succeeds either way -
    # that mismatch, empty 'ip xfrm state' next to populated 'ip xfrm
    # policy', is exactly how this bug shows itself when debugging).
    state = ('ip xfrm state add src {src} dst {dst} proto esp spi {spi} '
             'mode transport auth "hmac(sha256)" 0x{auth} enc "cbc(aes)" 0x{enc}')
    gw.cmd(state.format(src=local_wan, dst=remote_wan, spi=spi_out,
                        auth=auth_key, enc=enc_key))
    gw.cmd(state.format(src=remote_wan, dst=local_wan, spi=spi_in,
                        auth=auth_key, enc=enc_key))

    gw.cmd('ip xfrm policy add src {l} dst {r} dir out '
           'tmpl src {l} dst {r} proto esp mode transport'.format(l=local_wan, r=remote_wan))
    gw.cmd('ip xfrm policy add src {r} dst {l} dir in '
           'tmpl src {r} dst {l} proto esp mode transport'.format(l=local_wan, r=remote_wan))


def add_tunnel_route(gw, dest_subnet, via_ip, dev):
    """Route `dest_subnet` through the tunnel interface `dev` via the far end `via_ip`."""
    gw.cmd('ip route add {} via {} dev {}'.format(dest_subnet, via_ip, dev))


# ---------------------------------------------------------------------------
# The one-call VPN
# ---------------------------------------------------------------------------

def add_vpn(gw1, gw2,
            wan_ip1, wan_ip2,
            lan1, lan2,
            name='gre1',
            tunnel_ip1='10.10.10.1/30', tunnel_ip2='10.10.10.2/30',
            encrypt=True,
            spi_1to2='0x200', spi_2to1='0x100',
            enc_key=DEFAULT_ENC_KEY, auth_key=DEFAULT_AUTH_KEY):
    """
    Build a site-to-site VPN between two gateways.

    gw1, gw2        the two gateway nodes (the tunnel ends here, not on the hosts)
    wan_ip1/2       public IPs of gw1 / gw2, no prefix, e.g. '203.0.113.2'
    lan1/2          the private subnet behind each gateway, e.g. '10.0.0.0/24' -
                    OR a URL/hostname to resolve and route as a single host,
                    e.g. 'https://myapp.onrender.com' (see resolve_host() notes
                    on what this can and can't reach)
    name            tunnel interface name (use a new one for each extra VPN)
    tunnel_ip1/2    addresses on the tunnel itself
    encrypt         True = GRE + IPsec, False = plain GRE (handy to compare in Wireshark)
    spi_1to2/2to1   IPsec identifiers; must be unique per VPN between the same gateways
    """
    info('*** Adding VPN {} <-> {} ({})\n'.format(
        gw1.name, gw2.name, 'GRE + IPsec' if encrypt else 'GRE only, NOT encrypted'))

    # 1. GRE tunnel on both ends
    add_gre_tunnel(gw1, name, wan_ip1, wan_ip2, tunnel_ip1)
    add_gre_tunnel(gw2, name, wan_ip2, wan_ip1, tunnel_ip2)

    # 2. Optional IPsec encryption on both ends
    if encrypt:
        add_ipsec(gw1, wan_ip1, wan_ip2, spi_1to2, spi_2to1, enc_key, auth_key)
        add_ipsec(gw2, wan_ip2, wan_ip1, spi_2to1, spi_1to2, enc_key, auth_key)

    # 3. Send each LAN's traffic for the other LAN through the tunnel
    #    (lan1/lan2 may be a CIDR, or a URL/hostname resolved to a /32 route)
    add_tunnel_route(gw1, resolve_host(lan2), tunnel_ip2.split('/')[0], name)
    add_tunnel_route(gw2, resolve_host(lan1), tunnel_ip1.split('/')[0], name)


def remove_vpn(gw1, gw2, name='gre1'):
    """Tear down a VPN built with add_vpn. Note: flushes ALL IPsec state on both gateways."""
    for gw in (gw1, gw2):
        gw.cmd('ip xfrm state flush 2>/dev/null')
        gw.cmd('ip xfrm policy flush 2>/dev/null')
        gw.cmd('ip tunnel del {} 2>/dev/null'.format(name))


# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

def ping_test(src, dst_ip, label=None):
    """Ping dst_ip from src, print PASS/FAIL, and return True/False."""
    out = src.cmd('ping -c 1 -W 2 {} 2>&1'.format(dst_ip))
    ok = '1 received' in out
    info('  {:<40} {}\n'.format(label or '{} -> {}'.format(src.name, dst_ip),
                               'PASS' if ok else 'FAIL'))
    return ok

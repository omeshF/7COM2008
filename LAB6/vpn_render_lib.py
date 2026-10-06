#!/usr/bin/env python
"""
vpn_render_lib.py - Task 3 helper functions: "VPN" tunnel from a mininet
host to the /vpn/* routes on render_gateway_server.py.

Learners call these from vpn_render_lab.py; this file isn't meant to be
edited. Every function runs its work INSIDE the mininet node's own network
namespace via node.cmd(), reusing whatever internet route that node already
has from task 2 - nothing new to set up on the mininet side.

Requires: pip3 install requests   (once, on the Ubuntu host - all mininet
nodes share the same installed packages, just separate network namespaces)

Quick reference
---------------
vpn_connect(node, render_url, psk)              -> session_token or None
vpn_request(node, render_url, token, resource)  -> resource dict
vpn_disconnect(node, render_url, token)
"""

import json
import shlex
import socket
import time
from urllib.parse import urlparse
from mininet.log import info

# A small inline client, written into the node's filesystem and run with
# node.cmd() so it executes with that node's own IP and routing, not the
# controller process's.
#
# The LAST CLI argument is always a pre-resolved IP for the target host
# (or "" if none was available) - see _resolve_for_node() below for why
# resolution is done OUTSIDE this snippet, in the caller's own namespace,
# rather than trusting DNS to work here. It's appended after whatever
# action-specific arguments a given action already reads, so none of the
# existing sys.argv[N] positions below need to change.
_CLIENT_SNIPPET = '''
import sys, json, socket
from urllib.parse import urlparse

resolved_ip = sys.argv[-1]
try:
    import requests
    action = sys.argv[1]
    base = sys.argv[2].rstrip("/")  # avoid a double slash if the URL was given with a trailing "/"

    if resolved_ip:
        # Force every connection to the target host onto the IP we were
        # given, without touching TLS SNI or the HTTP Host header - both
        # of those come from the URL text (via "requests"), not from this
        # patched lookup, so certificate validation still checks out.
        # This is the same trick as "curl --resolve host:port:ip".
        target_host = urlparse(sys.argv[2]).hostname
        _orig_getaddrinfo = socket.getaddrinfo
        def _patched_getaddrinfo(host, *a, **kw):
            if host == target_host:
                host = resolved_ip
            return _orig_getaddrinfo(host, *a, **kw)
        socket.getaddrinfo = _patched_getaddrinfo

    if action == "connect":
        # Longer timeout: this is usually the FIRST request to the
        # gateway, and Render's free tier puts an idle app to sleep -
        # waking one back up can take 20-50s, and that wait falls on
        # whichever request arrives first.
        r = requests.post(base + "/vpn/connect", json={"psk": sys.argv[3]}, timeout=25)
        print(json.dumps(r.json()))
    elif action == "resource":
        headers = {"Authorization": "Bearer " + sys.argv[3]}
        r = requests.get(base + "/vpn/resource/" + sys.argv[4], headers=headers, timeout=10)
        print(json.dumps(r.json()))
    elif action == "disconnect":
        headers = {"Authorization": "Bearer " + sys.argv[3]}
        requests.post(base + "/vpn/disconnect", headers=headers, timeout=10)
        print("{}")
except Exception as e:
    # Always print valid JSON, even on failure (missing "requests", DNS
    # failure from a placeholder URL, connection refused, etc.) - so the
    # real cause surfaces in vpn_connect()/vpn_request()'s output instead
    # of a confusing JSONDecodeError deep in the library. Tagged as
    # "_transport_error" (NOT "error") so the retry logic in
    # _run_client() can tell a genuine connection failure apart from the
    # gateway's own legitimate {"error": "authentication failed"} etc.
    # responses - both would otherwise look identical (a dict with an
    # "error" key) and a correct 401 would get retried unnecessarily.
    print(json.dumps({"_transport_error": "{}: {}".format(type(e).__name__, e)}))
'''

_SNIPPET_PATH = '/tmp/_vpn_render_client.py'

# A second, separate snippet just for showing the raw TLS handshake -
# kept apart from _CLIENT_SNIPPET above because it talks plain ssl/socket,
# not "requests", and prints different information.
_TLS_SNIPPET = '''
import sys, ssl, socket, json

hostname = sys.argv[1]
resolved_ip = sys.argv[2]
port = int(sys.argv[3])
connect_to = resolved_ip if resolved_ip else hostname

try:
    ctx = ssl.create_default_context()
    with socket.create_connection((connect_to, port), timeout=10) as sock:
        # server_hostname drives BOTH the TLS SNI extension and the
        # certificate-hostname check, independently of connect_to - so
        # this validates the real cert even when connect_to is a bare IP.
        with ctx.wrap_socket(sock, server_hostname=hostname) as tls:
            cert = tls.getpeercert()
            subject = dict(x[0] for x in cert.get('subject', ()))
            issuer = dict(x[0] for x in cert.get('issuer', ()))
            cipher = tls.cipher()
            print(json.dumps({
                'tls_version': tls.version(),
                'cipher_suite': cipher[0] if cipher else None,
                'subject_cn': subject.get('commonName'),
                'issuer_cn': issuer.get('commonName') or issuer.get('organizationName'),
                'not_before': cert.get('notBefore'),
                'not_after': cert.get('notAfter'),
            }))
except Exception as e:
    print(json.dumps({'error': '{}: {}'.format(type(e).__name__, e)}))
'''

_TLS_SNIPPET_PATH = '/tmp/_vpn_tls_probe.py'


def _resolve_for_node(render_url):
    """
    Resolve render_url's hostname from THIS process - the controller /
    root network namespace - instead of from inside the mininet node.

    Why: mininet only gives a host its own NETWORK namespace, not its own
    MOUNT namespace, so /etc/resolv.conf inside a node such as h1 is the
    literal same file as the real machine's - a symlink that
    systemd-resolved owns and continuously regenerates (its own header
    says so: "This file is managed by man:systemd-resolved(8). Do not
    edit."). Overwriting it from inside a node sticks only until
    systemd-resolved rewrites it back - confirmed: h1's resolv.conf
    reverted to "nameserver 127.0.0.53" moments after being overwritten,
    and DNS lookups from inside h1 kept failing with "Name or service not
    known" even though the exact same nameserver worked fine from here.

    The root namespace's own systemd-resolved stub (127.0.0.53) is local
    to it and unaffected by anything a mininet node does, so resolution
    from here is reliable. Returns '' (not None) if it fails here too, so
    the caller can still attempt a direct connection rather than crash.
    """
    host = urlparse(render_url).hostname
    if not host:
        return ''
    try:
        return socket.gethostbyname(host)
    except socket.gaierror:
        return ''


def _ensure_snippet(node):
    # Mininet node shells run on a real pty, so they're full interactive
    # bash - which means '!' in a PSK/token triggers history expansion
    # ("event not found") before the command even runs. 'set +H' turns
    # that off for this node's persistent shell, once, for good.
    node.cmd('set +H')
    node.cmd("cat > {} << 'PYEOF'\n{}\nPYEOF".format(_SNIPPET_PATH, _CLIENT_SNIPPET))


def _last_json_line(output):
    lines = [l for l in output.strip().splitlines() if l.strip()]
    return json.loads(lines[-1]) if lines else {}


def _run_client(node, cmd_args, retries=0, retry_delay=5):
    """
    Run the client snippet and parse its JSON output. Retries only on a
    genuine TRANSPORT failure (connection refused, DNS, timeout - tagged
    "_transport_error" by the snippet's except block), never on the
    gateway's own application-level decisions, which also come back as a
    dict with an "error" key (e.g. {"error": "authentication failed"} for
    a wrong PSK) but mean the server is up and answered correctly -
    retrying those would just waste 5s for no reason.

    The retry exists for Render's free-tier cold start: a sleeping app
    can take 20-50s to wake up, and the request that happens to arrive
    first pays that wait - often timing out even with a generous
    per-request timeout, especially combined with an already slow/lossy
    network. The gateway is normally awake well before a retry finishes,
    so one retry after a short pause is usually enough; it also covers
    ordinary transient network blips the same way.
    """
    attempt = 0
    while True:
        out = node.cmd('python3 {} {}'.format(_SNIPPET_PATH, ' '.join(cmd_args)))
        result = _last_json_line(out)
        transport_error = result.get('_transport_error')
        if transport_error is None or attempt >= retries:
            if transport_error is not None:
                # Retries exhausted - surface it as a normal "error" so
                # every caller (which all check for "error") still sees it.
                result = {'error': transport_error}
            return result
        attempt += 1
        info('*** {} - retrying in {}s (attempt {}/{}, gateway may be waking from a cold start)\n'.format(
            transport_error, retry_delay, attempt, retries))
        time.sleep(retry_delay)


def show_tls_info(node, render_url, port=443):
    """
    Connect to render_url over TLS (no VPN session involved - this is
    just a plain HTTPS handshake) and print out the negotiated TLS
    version, cipher suite, and the server's certificate. This is the
    "print out" evidence that task 3 really is running over encrypted,
    certificate-verified TLS - just not the ESP/IPsec protocol task 1
    uses, since Render (a PaaS) can't terminate a kernel-level VPN.
    Read-only: makes no VPN session state, safe to call any time.
    """
    resolved_ip = _resolve_for_node(render_url)
    hostname = urlparse(render_url).hostname
    node.cmd("cat > {} << 'PYEOF'\n{}\nPYEOF".format(_TLS_SNIPPET_PATH, _TLS_SNIPPET))
    out = node.cmd('python3 {} {} {} {}'.format(
        _TLS_SNIPPET_PATH, shlex.quote(hostname), shlex.quote(resolved_ip), port))
    result = _last_json_line(out)
    if 'error' in result:
        info('*** TLS probe to {} failed: {}\n'.format(hostname, result['error']))
        return result
    info('*** TLS connection {} -> {}:\n'.format(node.name, hostname))
    info('***   Protocol:    {}\n'.format(result.get('tls_version')))
    info('***   Cipher:      {}\n'.format(result.get('cipher_suite')))
    info('***   Certificate: CN={}\n'.format(result.get('subject_cn')))
    info('***   Issued by:   {}\n'.format(result.get('issuer_cn')))
    info('***   Valid:       {} -> {}\n'.format(result.get('not_before'), result.get('not_after')))
    return result


def vpn_connect(node, render_url, psk):
    """
    Authenticate to the VPN gateway once. Returns a session token (string)
    on success, or None on failure. Keep the token and reuse it in
    vpn_request() for as long as the "tunnel" should stay up.
    """
    _ensure_snippet(node)
    resolved_ip = _resolve_for_node(render_url)
    if resolved_ip:
        info('*** Resolved {} -> {} here (mininet hosts can\'t reliably do their own DNS, see vpn_render_lib.py)\n'.format(
            urlparse(render_url).hostname, resolved_ip))
    result = _run_client(node, [
        'connect', shlex.quote(render_url), shlex.quote(psk), shlex.quote(resolved_ip)
    ], retries=1)
    if 'session_token' not in result:
        info('*** VPN connect failed: {}\n'.format(result))
        return None
    info('*** {} connected to VPN gateway (session valid {}s)\n'.format(
        node.name, result.get('expires_in')))
    return result['session_token']


def vpn_request(node, render_url, session_token, resource):
    """
    Ask for a resource through the already-open VPN session. The gateway
    does NOT re-check whether this session is meant to reach this
    particular resource - once connected, every resource is reachable.
    That's the behaviour to compare against task 4's ZTNA library.
    """
    resolved_ip = _resolve_for_node(render_url)
    result = _run_client(node, [
        'resource', shlex.quote(render_url), shlex.quote(session_token),
        shlex.quote(resource), shlex.quote(resolved_ip)
    ])
    info('*** {} -> {}: {}\n'.format(node.name, resource, result))
    return result


def vpn_disconnect(node, render_url, session_token):
    """End the VPN session."""
    resolved_ip = _resolve_for_node(render_url)
    node.cmd('python3 {} disconnect {} {} {}'.format(
        _SNIPPET_PATH, shlex.quote(render_url), shlex.quote(session_token), shlex.quote(resolved_ip)))
    info('*** {} disconnected from VPN gateway\n'.format(node.name))

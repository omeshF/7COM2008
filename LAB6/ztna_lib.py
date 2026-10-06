#!/usr/bin/env python
"""
ztna_lib.py - Task 4 helper functions: a simple ZTNA (Zero Trust Network
Access) client against the /ztna/* routes on render_gateway_server.py.

Learners call these from ztna_lab.py; this file isn't meant to be edited.
Compare with vpn_render_lib.py (task 3): same transport (HTTPS to a Render
web service, no VPN protocol, no TUN device, no root needed anywhere), but
a completely different trust model:

  VPN model  (task 3): authenticate once -> reach everything.
  ZTNA model (task 4): every resource needs its own authorization check
                        (identity + device posture + policy), tokens are
                        scoped to ONE resource, and they expire quickly.

Requires: pip3 install requests   (once, on the Ubuntu host)

Quick reference
---------------
ztna_authorize(node, ztna_url, identity, device_posture, resource)
    -> access_token or None (None means the gateway denied it - check
       ztna_audit() on the server to see why)

ztna_request(node, ztna_url, token, resource)
    -> resource dict, or an error dict if the token doesn't match this
       resource or has expired

ztna_audit(node, ztna_url)
    -> the gateway's last 50 allow/deny decisions
"""

import json
import shlex
import socket
import time
from urllib.parse import urlparse
from mininet.log import info

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

    if action == "authorize":
        body = {"identity": sys.argv[3], "device_posture": sys.argv[4], "resource": sys.argv[5]}
        # Longer timeout: this is often the FIRST request to the gateway,
        # and Render's free tier puts an idle app to sleep - waking one
        # back up can take 20-50s, and that wait falls on whichever
        # request arrives first.
        r = requests.post(base + "/ztna/authorize", json=body, timeout=25)
        print(json.dumps(r.json()))
    elif action == "resource":
        headers = {"Authorization": "Bearer " + sys.argv[3]}
        r = requests.get(base + "/ztna/resource/" + sys.argv[4], headers=headers, timeout=10)
        print(json.dumps(r.json()))
    elif action == "audit":
        r = requests.get(base + "/ztna/audit", timeout=10)
        print(json.dumps(r.json()))
except Exception as e:
    # Always print valid JSON, even on failure (missing "requests", DNS
    # failure from a placeholder URL, connection refused, etc.) - so the
    # real cause surfaces instead of a confusing JSONDecodeError deep in
    # the library. Tagged as "_transport_error" (NOT "error") so the
    # retry logic in _run_client() can tell a genuine connection failure
    # apart from the gateway's own legitimate {"error": "denied: ..."}
    # responses - both would otherwise look identical (a dict with an
    # "error" key) and a correct policy denial would get retried and
    # double-logged as if it were a cold-start timeout.
    print(json.dumps({"_transport_error": "{}: {}".format(type(e).__name__, e)}))
'''

_SNIPPET_PATH = '/tmp/_ztna_client.py'


def _resolve_for_node(ztna_url):
    """
    Resolve ztna_url's hostname from THIS process - the controller / root
    network namespace - instead of from inside the mininet node.

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
    host = urlparse(ztna_url).hostname
    if not host:
        return ''
    try:
        return socket.gethostbyname(host)
    except socket.gaierror:
        return ''


def _ensure_snippet(node):
    # Mininet node shells run on a real pty, so they're full interactive
    # bash - which means '!' in an identity/token/posture value triggers
    # history expansion ("event not found") before the command even runs.
    # 'set +H' turns that off for this node's persistent shell, once, for good.
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
    dict with an "error" key (e.g. {"error": "denied: ..."} for a policy
    refusal) but mean the server is up and answered correctly - retrying
    those would just waste 5s and double-log a perfectly good denial in
    ztna_audit_log.

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


def ztna_authorize(node, ztna_url, identity, device_posture, resource):
    """
    Ask the ZTNA gateway for access to exactly one resource. Returns an
    access token scoped to that resource, or None if the gateway denied it
    (wrong identity, resource not in that identity's policy, or posture
    check failed - all logged server-side, see ztna_audit()).
    """
    _ensure_snippet(node)
    resolved_ip = _resolve_for_node(ztna_url)
    if resolved_ip:
        info('*** Resolved {} -> {} here (mininet hosts can\'t reliably do their own DNS, see ztna_lib.py)\n'.format(
            urlparse(ztna_url).hostname, resolved_ip))
    result = _run_client(node, [
        'authorize', shlex.quote(ztna_url), shlex.quote(identity),
        shlex.quote(device_posture), shlex.quote(resource), shlex.quote(resolved_ip)
    ], retries=1)
    if 'access_token' not in result:
        info('*** {} DENIED for {} on {}: {}\n'.format(
            identity, resource, node.name, result.get('error', result)))
        return None
    info('*** {} ALLOWED for {} on {} (token valid {}s)\n'.format(
        identity, resource, node.name, result.get('expires_in')))
    return result['access_token']


def ztna_request(node, ztna_url, token, resource):
    """
    Use a resource-scoped token to fetch exactly the resource it was
    issued for. Trying it against a different resource, or after it has
    expired, returns an error dict instead of the resource.
    """
    resolved_ip = _resolve_for_node(ztna_url)
    out = node.cmd('python3 {} resource {} {} {} {}'.format(
        _SNIPPET_PATH, shlex.quote(ztna_url), shlex.quote(token),
        shlex.quote(resource), shlex.quote(resolved_ip)))
    result = _last_json_line(out)
    info('*** {} -> {}: {}\n'.format(node.name, resource, result))
    return result


def ztna_audit(node, ztna_url):
    """Fetch the gateway's recent allow/deny decisions."""
    _ensure_snippet(node)
    resolved_ip = _resolve_for_node(ztna_url)
    out = node.cmd('python3 {} audit {} {}'.format(
        _SNIPPET_PATH, shlex.quote(ztna_url), shlex.quote(resolved_ip)))
    return _last_json_line(out)

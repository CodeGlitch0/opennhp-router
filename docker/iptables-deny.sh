#!/bin/sh
# Default-deny for the NHP-AC (gateway) host.
# Unauthorized packets hit the DROP policy. Authorized tuples are inserted
# into defaultset by nhp-acd. This script does not rewrite destinations;
# docker/forwarder.py dials the backend.
set -eu

iptables -P INPUT DROP
iptables -P FORWARD DROP

ipset -exist create defaultset hash:ip,port,ip counters maxelem 1000000 timeout 120

iptables -C INPUT -m state --state ESTABLISHED -j ACCEPT >/dev/null 2>&1 || \
    iptables -A INPUT -m state --state ESTABLISHED -j ACCEPT
iptables -C FORWARD -m state --state ESTABLISHED -j ACCEPT >/dev/null 2>&1 || \
    iptables -A FORWARD -m state --state ESTABLISHED -j ACCEPT

iptables -C INPUT -m set --match-set defaultset src,dst,dst -j ACCEPT >/dev/null 2>&1 || \
    iptables -A INPUT -m set --match-set defaultset src,dst,dst -j ACCEPT
iptables -C FORWARD -m set --match-set defaultset src,dst,dst -j ACCEPT >/dev/null 2>&1 || \
    iptables -A FORWARD -m set --match-set defaultset src,dst,dst -j ACCEPT

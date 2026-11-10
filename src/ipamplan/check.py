"""The fast implementation: the standard library `ipaddress`, a sweep over the sorted subnets for the overlaps, and the
free space from the merged intervals."""

from __future__ import annotations

import ipaddress
from collections import Counter

from .plan import Plan, Subnet, usable
from .rules import RULES, Allocation, Analysis, Keyed, ordered, prefix_for

R = {rule: i for i, rule in enumerate(RULES)}


def merged(plan: Plan) -> list[tuple[int, int]]:
    """The addresses of the supernet taken by the subnets, as sorted disjoint intervals."""
    sup = ipaddress.IPv4Network(plan.supernet)
    lo, hi = int(sup.network_address), int(sup.broadcast_address)
    spans = []
    for s in plan.subnets:
        net = ipaddress.IPv4Interface(s.cidr).network
        a, b = max(int(net.network_address), lo), min(int(net.broadcast_address), hi)
        if a <= b:
            spans.append((a, b))
    spans.sort()
    out: list[tuple[int, int]] = []
    for a, b in spans:
        if out and a <= out[-1][1] + 1:
            if b > out[-1][1]:
                out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
    return out


def analyze(plan: Plan) -> Analysis:
    sup = ipaddress.IPv4Network(plan.supernet)
    ifaces = [ipaddress.IPv4Interface(s.cidr) for s in plan.subnets]
    nets = [i.network for i in ifaces]
    keyed: list[Keyed] = []
    for i, (s, iface, net) in enumerate(zip(plan.subnets, ifaces, nets, strict=True)):
        if not net.subnet_of(sup):
            keyed.append((R["outside_supernet"], i, i, s.name))
        keyed.extend(_gateway_and_size(i, s, iface, net))
    keyed.extend(_overlaps(plan, nets))
    names = Counter(s.name for s in plan.subnets)
    vlans = Counter(s.vlan for s in plan.subnets if s.vlan is not None)
    seen_name: set[str] = set()
    seen_vlan: set[int] = set()
    for i, s in enumerate(plan.subnets):
        if names[s.name] > 1 and s.name not in seen_name:
            seen_name.add(s.name)
            keyed.append((R["duplicate_name"], i, i, s.name))
        if s.vlan is not None and vlans[s.vlan] > 1 and s.vlan not in seen_vlan:
            seen_vlan.add(s.vlan)
            keyed.append((R["duplicate_vlan"], i, i, str(s.vlan)))
    used_spans = merged(plan)
    used = sum(b - a + 1 for a, b in used_spans)
    free: list[str] = []
    cursor = int(sup.network_address)
    end = int(sup.broadcast_address)
    for a, b in [*used_spans, (end + 1, end + 1)]:
        if a > cursor:
            blocks = ipaddress.summarize_address_range(ipaddress.IPv4Address(cursor), ipaddress.IPv4Address(a - 1))
            free.extend(str(n) for n in blocks)
        cursor = b + 1
    return Analysis(ordered(keyed), free, used, sup.num_addresses - used)


def _gateway_and_size(i: int, s: Subnet, iface: ipaddress.IPv4Interface, net: ipaddress.IPv4Network) -> list[Keyed]:
    out: list[Keyed] = []
    if iface.ip != net.network_address:
        out.append((R["host_bits"], i, i, s.name))
    if s.gateway is not None:
        gw = ipaddress.IPv4Address(s.gateway)
        if gw not in net:
            out.append((R["gateway_outside"], i, i, s.name))
        elif net.prefixlen <= 30 and gw in (net.network_address, net.broadcast_address):
            out.append((R["gateway_reserved"], i, i, s.name))
    if s.hosts is not None and s.hosts > usable(net.prefixlen):
        out.append((R["over_capacity"], i, i, s.name))
    return out


def _overlaps(plan: Plan, nets: list[ipaddress.IPv4Network]) -> list[Keyed]:
    """Two CIDR blocks overlap only if one contains the other, so a sweep over the blocks sorted by start (larger block
    first) keeps a stack of the blocks that contain the current one."""
    order = sorted(range(len(nets)), key=lambda i: (int(nets[i].network_address), nets[i].prefixlen, i))
    stack: list[tuple[int, int]] = []  # (last address, index)
    out: list[Keyed] = []
    for i in order:
        start = int(nets[i].network_address)
        while stack and stack[-1][0] < start:
            stack.pop()
        for _end, j in stack:
            a, b = min(i, j), max(i, j)
            out.append((R["overlap"], a, b, f"{plan.subnets[a].name}|{plan.subnets[b].name}"))
        stack.append((int(nets[i].broadcast_address), i))
    return out


def allocate(supernet: str, existing: list[str], requests: list[tuple[str, int]]) -> Allocation:
    """First fit, largest request first (ties by name): each request takes the lowest aligned block that is free."""
    sup = ipaddress.IPv4Network(supernet)
    lo, hi = int(sup.network_address), int(sup.broadcast_address)
    taken = []
    for c in existing:
        net = ipaddress.IPv4Interface(c).network
        a, b = max(int(net.network_address), lo), min(int(net.broadcast_address), hi)
        if a <= b:
            taken.append((a, b))
    taken.sort()
    free: list[tuple[int, int]] = []
    cursor = lo
    for a, b in taken:
        if a > cursor:
            free.append((cursor, a - 1))
        cursor = max(cursor, b + 1)
    if cursor <= hi:
        free.append((cursor, hi))
    prefixes = [prefix_for(h) for _n, h in requests]
    order = sorted(range(len(requests)), key=lambda i: (prefixes[i], requests[i][0], i))
    placed: list[tuple[str, str]] = []
    unplaced: list[str] = []
    for i in order:
        size = 1 << (32 - prefixes[i])
        for k, (a, b) in enumerate(free):
            start = -(-a // size) * size
            if start + size - 1 <= b:
                pieces = []
                if start > a:
                    pieces.append((a, start - 1))
                if start + size <= b:
                    pieces.append((start + size, b))
                free[k : k + 1] = pieces
                placed.append((requests[i][0], str(ipaddress.IPv4Network((start, prefixes[i])))))
                break
        else:
            unplaced.append(requests[i][0])
    return Allocation(placed, unplaced)

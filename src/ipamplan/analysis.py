"""The report: what a plan allocates, what is left, what is wrong, and how well the checks find injected faults."""

from __future__ import annotations

import ipaddress
from typing import Any

from . import check
from .plan import Plan, Subnet, usable
from .rules import RULES, SUMMARY, Finding
from .score import score

MAP_BINS = 128
LISTED = 20


def describe(plan: Plan, f: Finding) -> str:
    by_name: dict[str, Subnet] = {}
    for s in plan.subnets:
        by_name.setdefault(s.name, s)
    if f.rule == "overlap":
        a, b = f.subject.split("|")
        return f"{a} ({by_name[a].cidr}) and {b} ({by_name[b].cidr}) share addresses"
    if f.rule == "duplicate_name":
        return f"{sum(1 for s in plan.subnets if s.name == f.subject)} subnets are called {f.subject}"
    if f.rule == "duplicate_vlan":
        names = ", ".join(s.name for s in plan.subnets if str(s.vlan) == f.subject)
        return f"VLAN {f.subject} is used by {names}"
    s = by_name[f.subject]
    if f.rule == "outside_supernet":
        return f"{s.cidr} is not inside {plan.supernet}"
    if f.rule in ("gateway_outside", "gateway_reserved"):
        return f"gateway {s.gateway} of {s.cidr}: {SUMMARY[f.rule]}"
    if f.rule == "over_capacity":
        prefix = ipaddress.IPv4Interface(s.cidr).network.prefixlen
        return f"{s.hosts} hosts planned in {s.cidr}, which holds {usable(prefix)}"
    return f"{s.cidr} is not the network address of {ipaddress.IPv4Interface(s.cidr).network}"


def address_map(spans: list[tuple[int, int]], first: int, size: int) -> list[float]:
    """The share of each of MAP_BINS equal parts of the supernet that the subnets take."""
    width = size / MAP_BINS
    taken = [0.0] * MAP_BINS
    for a, b in spans:
        lo, hi = a - first, b - first + 1
        for k in range(int(lo // width), min(MAP_BINS - 1, int((hi - 1) // width)) + 1):
            taken[k] += max(0.0, min(hi, (k + 1) * width) - max(lo, k * width))
    return [round(min(1.0, t / width), 4) for t in taken]


def build_report(plan: Plan, truth: list[dict[str, str]] | None, source: str) -> dict[str, Any]:
    an = check.analyze(plan)
    sup = ipaddress.IPv4Network(plan.supernet)
    nets = [ipaddress.IPv4Interface(s.cidr).network for s in plan.subnets]
    free_sizes = [ipaddress.IPv4Network(b).num_addresses for b in an.free]
    largest = max(range(len(an.free)), key=lambda i: free_sizes[i], default=None)
    sized = [(s, n) for s, n in zip(plan.subnets, nets, strict=True) if s.hosts is not None]
    hosts = sum(s.hosts or 0 for s, _ in sized)
    room = sum(usable(n.prefixlen) for _, n in sized)
    by_prefix: dict[str, int] = {}
    for n in sorted(nets, key=lambda n: n.prefixlen):
        by_prefix[str(n.prefixlen)] = by_prefix.get(str(n.prefixlen), 0) + 1
    unused = sorted(
        (
            (usable(n.prefixlen) - (s.hosts or 0), s.name, s.cidr)
            for s, n in sized
            if (s.hosts or 0) <= usable(n.prefixlen)
        ),
        key=lambda t: (-t[0], t[1]),
    )[:5]
    by_rule = {r: 0 for r in RULES}
    for f in an.findings:
        by_rule[f.rule] += 1
    report: dict[str, Any] = {
        "kind": "report",
        "source": source,
        "plan": plan.name,
        "supernet": plan.supernet,
        "addresses": sup.num_addresses,
        "subnets": len(plan.subnets),
        "used": an.used,
        "used_share": an.used / sup.num_addresses,
        "free": an.free_total,
        "free_blocks": len(an.free),
        "largest_free": None if largest is None else an.free[largest],
        "largest_free_addresses": 0 if largest is None else free_sizes[largest],
        "fragmentation": 0.0 if an.free_total == 0 else 1 - max(free_sizes, default=0) / an.free_total,
        "hosts_planned": hosts,
        "hosts_capacity": room,
        "fill": 0.0 if room == 0 else hosts / room,
        "by_prefix": by_prefix,
        "unused": [{"name": n, "cidr": c, "unused": u} for u, n, c in unused],
        "findings": {
            "total": len(an.findings),
            "by_rule": by_rule,
            "listed": [
                {"rule": f.rule, "subject": f.subject, "detail": describe(plan, f)} for f in an.findings[:LISTED]
            ],
        },
        "map": address_map(check.merged(plan), int(sup.network_address), sup.num_addresses),
        "accuracy": None if truth is None else score(an.findings, truth),
    }
    return report

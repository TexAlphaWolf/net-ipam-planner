"""The literal implementation: the same rules written as plainly as possible, with every pair of subnets compared and
every address worked out by hand from integers. It is slow on purpose; `ipam verify` compares it with `check.py`."""

from __future__ import annotations

from .plan import FULL, Plan, fmt, mask, parse_address, parse_cidr, usable
from .rules import RULES, Allocation, Analysis, Keyed, ordered, prefix_for

R = {rule: i for i, rule in enumerate(RULES)}


def block(cidr: str) -> tuple[int, int, int]:
    """(first address, last address, prefix) of the network that a CIDR with or without host bits names."""
    address, prefix = parse_cidr(cidr)
    first = address & mask(prefix)
    last = first | (~mask(prefix) & FULL)
    return first, last, prefix


def analyze(plan: Plan) -> Analysis:
    sup_first, sup_last, _ = block(plan.supernet)
    blocks = [block(s.cidr) for s in plan.subnets]
    keyed: list[Keyed] = []
    n = len(plan.subnets)
    for i in range(n):
        s = plan.subnets[i]
        first, last, prefix = blocks[i]
        if not (sup_first <= first and last <= sup_last):
            keyed.append((R["outside_supernet"], i, i, s.name))
        if parse_cidr(s.cidr)[0] != first:
            keyed.append((R["host_bits"], i, i, s.name))
        if s.gateway is not None:
            gw = parse_address(s.gateway)
            if not (first <= gw <= last):
                keyed.append((R["gateway_outside"], i, i, s.name))
            elif prefix <= 30 and gw in (first, last):
                keyed.append((R["gateway_reserved"], i, i, s.name))
        if s.hosts is not None and s.hosts > usable(prefix):
            keyed.append((R["over_capacity"], i, i, s.name))
        for j in range(i + 1, n):
            if first <= blocks[j][1] and blocks[j][0] <= last:
                keyed.append((R["overlap"], i, j, f"{s.name}|{plan.subnets[j].name}"))
    seen_names: list[str] = []
    seen_vlans: list[int] = []
    for i in range(n):
        s = plan.subnets[i]
        if s.name not in seen_names and any(plan.subnets[j].name == s.name for j in range(i + 1, n)):
            seen_names.append(s.name)
            keyed.append((R["duplicate_name"], i, i, s.name))
        if (
            s.vlan is not None
            and s.vlan not in seen_vlans
            and any(plan.subnets[j].vlan == s.vlan for j in range(i + 1, n))
        ):
            seen_vlans.append(s.vlan)
            keyed.append((R["duplicate_vlan"], i, i, str(s.vlan)))
    # Free space: walk the subnets in order of address with a cursor that is the first address not yet accounted for.
    clipped = sorted(
        (max(first, sup_first), min(last, sup_last))
        for first, last, _ in blocks
        if first <= sup_last and last >= sup_first
    )
    free: list[str] = []
    used = 0
    cursor = sup_first
    for first, last in clipped:
        if last < cursor:
            continue  # already accounted for by an earlier, larger subnet
        start = max(first, cursor)
        if start > cursor:
            free.extend(_blocks(cursor, start - 1))
        used += last - start + 1
        cursor = last + 1
    if cursor <= sup_last:
        free.extend(_blocks(cursor, sup_last))
    return Analysis(ordered(keyed), free, used, sup_last - sup_first + 1 - used)


def _blocks(first: int, last: int) -> list[str]:
    """The shortest list of CIDR blocks covering first..last: repeatedly the largest aligned block that fits."""
    out = []
    while first <= last:
        size = 1
        while first % (size * 2) == 0 and size * 2 <= last - first + 1:
            size *= 2
        out.append(f"{fmt(first)}/{32 - size.bit_length() + 1}")
        first += size
    return out


def allocate(supernet: str, existing: list[str], requests: list[tuple[str, int]]) -> Allocation:
    sup_first, sup_last, _ = block(supernet)
    taken = [block(c)[:2] for c in existing]
    prefixes = [prefix_for(h) for _n, h in requests]
    order = sorted(range(len(requests)), key=lambda i: (prefixes[i], requests[i][0], i))
    placed: list[tuple[str, str]] = []
    unplaced: list[str] = []
    for i in order:
        size = 1 << (32 - prefixes[i])
        candidate = sup_first
        found = False
        while candidate + size - 1 <= sup_last:
            if all(candidate + size - 1 < a or b < candidate for a, b in taken):
                taken.append((candidate, candidate + size - 1))
                placed.append((requests[i][0], f"{fmt(candidate)}/{prefixes[i]}"))
                found = True
                break
            candidate += size
        if not found:
            unplaced.append(requests[i][0])
    return Allocation(placed, unplaced)

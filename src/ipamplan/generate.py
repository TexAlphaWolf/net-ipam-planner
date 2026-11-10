"""Consistent plans made by construction, then given faults whose list is kept as the truth."""

from __future__ import annotations

import random
from typing import Any

from .plan import MAX_VLAN, Plan, Subnet, fmt, parse_cidr, usable
from .rules import RULES

# prefix length -> weight: many small subnets, a few large ones
PREFIX_WEIGHTS = {30: 25, 29: 20, 28: 20, 27: 15, 26: 10, 25: 5, 24: 5}
OUTSIDE_BASE = 172 << 24 | 16 << 16  # 172.16.0.0, far from the 10.0.0.0 supernets
LAST_PLANNED_VLAN = MAX_VLAN - 100  # the VLANs above are kept for the duplicate-VLAN faults
FOREIGN_GATEWAY = "203.0.113.1"

DEMO_FAULTS = {
    "outside_supernet": 1,
    "overlap": 2,
    "duplicate_name": 1,
    "duplicate_vlan": 1,
    "gateway_outside": 2,
    "gateway_reserved": 1,
    "over_capacity": 2,
    "host_bits": 1,
}


def supernet_for(total: int) -> str:
    """The smallest 10.0.0.0/p with room for twice the addresses the subnets need."""
    prefix = 24
    while prefix > 7 and (1 << (32 - prefix)) < 2 * total:
        prefix -= 1
    if (1 << (32 - prefix)) < 2 * total:
        raise ValueError("too many subnets for a 10.0.0.0 supernet")
    return f"10.0.0.0/{prefix}"


def consistent(subnets: int, seed: int) -> tuple[str, list[Subnet]]:
    """`subnets` subnets, carved largest first from one end of the supernet so that none overlaps, each with a VLAN (while
    there are VLAN numbers), its first host as gateway and a number of hosts that fits."""
    rng = random.Random(seed)
    prefixes = sorted(rng.choices(list(PREFIX_WEIGHTS), weights=list(PREFIX_WEIGHTS.values()), k=subnets))
    supernet = supernet_for(sum(1 << (32 - p) for p in prefixes))
    cursor = parse_cidr(supernet)[0]
    made: list[Subnet] = []
    for index, prefix in enumerate(prefixes):
        size = 1 << (32 - prefix)
        cursor = -(-cursor // size) * size
        vlan = index + 10 if index + 10 <= LAST_PLANNED_VLAN else None
        hosts = max(1, int(usable(prefix) * rng.uniform(0.2, 0.95)))
        made.append(Subnet(f"net-{index:05d}", f"{fmt(cursor)}/{prefix}", vlan, fmt(cursor + 1), hosts))
        cursor += size
    rng.shuffle(made)
    return supernet, made


def generate(
    subnets: int = 120, seed: int = 1, faults: dict[str, int] | None = None
) -> tuple[Plan, list[dict[str, str]]]:
    """A plan and the list of faults put into it (none when `faults` is empty or None)."""
    supernet, made = consistent(subnets, seed)
    truth: list[dict[str, str]] = []
    want = faults or {}
    if sum(want.values()) * 2 + 8 > subnets:
        raise ValueError("too many faults for the number of subnets")
    rng = random.Random(seed * 7919 + 1)
    free_idx = list(range(len(made)))
    rng.shuffle(free_idx)

    def take() -> int:
        return free_idx.pop()

    def take_wide() -> int:
        skipped: list[int] = []
        while True:
            j = free_idx.pop()
            if parse_cidr(made[j].cidr)[1] <= 29:
                free_idx.extend(skipped)
                return j
            skipped.append(j)

    def put(i: int, **changes: Any) -> None:
        s = made[i]
        made[i] = Subnet(**{**s.to_dict(), **changes})

    extra: list[Subnet] = []
    outside = 0
    for rule in RULES:
        for _ in range(want.get(rule, 0)):
            if rule == "outside_supernet":
                i, net = take(), OUTSIDE_BASE + 256 * outside
                outside += 1
                put(i, cidr=f"{fmt(net)}/24", gateway=fmt(net + 1), hosts=None)
                truth.append({"rule": rule, "subject": made[i].name})
            elif rule == "overlap":
                i = take_wide()
                address, prefix = parse_cidr(made[i].cidr)
                name = f"overlap-{len(extra):03d}"
                extra.append(Subnet(name, f"{fmt(address)}/{prefix + 1}"))
                truth.append({"rule": rule, "subject": f"{made[i].name}|{name}"})
            elif rule == "duplicate_name":
                a, b = take(), take()
                put(b, name=made[a].name)
                truth.append({"rule": rule, "subject": made[a].name})
            elif rule == "duplicate_vlan":
                a, b = take(), take()
                vlan = LAST_PLANNED_VLAN + 1 + len(truth)
                put(a, vlan=vlan)
                put(b, vlan=vlan)
                truth.append({"rule": rule, "subject": str(vlan)})
            elif rule == "gateway_outside":
                i = take()
                put(i, gateway=FOREIGN_GATEWAY)
                truth.append({"rule": rule, "subject": made[i].name})
            elif rule == "gateway_reserved":
                i = take()
                first = parse_cidr(made[i].cidr)[0]
                put(i, gateway=fmt(first))
                truth.append({"rule": rule, "subject": made[i].name})
            elif rule == "over_capacity":
                i = take()
                put(i, hosts=usable(parse_cidr(made[i].cidr)[1]) + 1)
                truth.append({"rule": rule, "subject": made[i].name})
            elif rule == "host_bits":
                i = take()
                address, prefix = parse_cidr(made[i].cidr)
                put(i, cidr=f"{fmt(address + 1)}/{prefix}")
                truth.append({"rule": rule, "subject": made[i].name})
    return Plan(f"generated-{subnets}-{seed}", supernet, (*made, *extra)), truth

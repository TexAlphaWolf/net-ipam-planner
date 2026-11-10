"""The two implementations compared on generated plans and on random messy ones."""

from __future__ import annotations

import random
from dataclasses import dataclass

from . import check, reference
from .generate import DEMO_FAULTS, generate
from .plan import Plan, Subnet, fmt, mask, parse_cidr
from .rules import Allocation, Analysis


@dataclass(frozen=True)
class Check:
    name: str
    items: int
    values: int
    ok: bool


def same(a: Analysis, b: Analysis) -> bool:
    return a == b


def random_plan(rng: random.Random, subnets: int) -> Plan:
    """A messy plan: overlaps, subnets outside the supernet, host bits, repeated names and VLANs, odd gateways."""
    base = rng.randrange(0, 256) << 24 | rng.randrange(0, 256) << 16
    sup_prefix = rng.choice([16, 18, 20])
    supernet = f"{fmt(base & mask(sup_prefix))}/{sup_prefix}"
    sup_first = parse_cidr(supernet)[0]
    pool = max(2, int(subnets * 0.9))
    made = []
    for _ in range(subnets):
        prefix = rng.choice([22, 24, 24, 25, 26, 27, 28, 29, 30, 30, 31, 32])
        where = sup_first if rng.random() < 0.9 else rng.randrange(0, 1 << 32)
        address = (where + rng.randrange(0, 1 << (32 - sup_prefix))) & 0xFFFFFFFF
        if rng.random() < 0.8:
            address &= mask(prefix)
        gateway = None
        if rng.random() < 0.7:
            first = address & mask(prefix)
            span = 1 << (32 - prefix)
            gateway = fmt((first + rng.choice([0, 1, 1, 1, span - 1, rng.randrange(span)])) & 0xFFFFFFFF)
            if rng.random() < 0.1:
                gateway = fmt(rng.randrange(0, 1 << 32))
        hosts = rng.randrange(0, (1 << (32 - prefix)) + 3) if rng.random() < 0.6 else None
        vlan = rng.randrange(1, max(3, subnets // 2)) if rng.random() < 0.7 else None
        made.append(Subnet(f"n{rng.randrange(pool)}", f"{fmt(address)}/{prefix}", vlan, gateway, hosts))
    return Plan("random", supernet, tuple(made))


def random_request(rng: random.Random, requests: int) -> tuple[str, list[str], list[tuple[str, int]]]:
    prefix = rng.choice([16, 20, 22, 24])
    base = rng.randrange(0, 1 << 32) & mask(prefix)
    supernet = f"{fmt(base)}/{prefix}"
    existing = []
    for _ in range(rng.randrange(0, 6)):
        p = rng.randrange(prefix, 31)
        existing.append(f"{fmt((base + rng.randrange(0, 1 << (32 - prefix))) & mask(p))}/{p}")
    needs = [
        (f"r{i}", rng.choice([1, 2, 5, 12, 30, 60, 120, 250, 500, 1000, rng.randrange(1, 5000)]))
        for i in range(requests)
    ]
    return supernet, existing, needs


def allocation_is_sound(supernet: str, existing: list[str], needs: list[tuple[str, int]], got: Allocation) -> bool:
    """What an allocation promises, checked without either implementation's search: every placed block is aligned, inside
    the supernet, big enough, and shares no address with an existing subnet or another placed block."""
    first, size = parse_cidr(supernet)[0], 1 << (32 - parse_cidr(supernet)[1])
    taken = []
    for c in existing:
        a, p = parse_cidr(c)
        a &= mask(p)
        taken.append((a, a + (1 << (32 - p)) - 1))
    want = dict(needs)
    if sorted([*(n for n, _ in got.placed), *got.unplaced]) != sorted(want):
        return False
    for name, cidr in got.placed:
        a, p = parse_cidr(cidr)
        if a & ~mask(p) & 0xFFFFFFFF or not (first <= a and a + (1 << (32 - p)) <= first + size):
            return False
        if (1 << (32 - p)) - 2 < want[name]:
            return False
        span = (a, a + (1 << (32 - p)) - 1)
        if any(span[0] <= y and x <= span[1] for x, y in taken):
            return False
        taken.append(span)
    return True


def run(draws: int, seed: int, generated: tuple[int, int] = (120, 1)) -> list[Check]:
    out: list[Check] = []
    for label, faults in (("generated plan, no faults", {}), ("generated plan with faults", DEMO_FAULTS)):
        plan, _ = generate(generated[0], generated[1], faults)
        a, b = check.analyze(plan), reference.analyze(plan)
        out.append(Check(label, len(plan.subnets), len(a.findings) + len(a.free) + 2, same(a, b)))
    rng = random.Random(seed)
    for k in range(draws):
        plan = random_plan(rng, rng.randrange(5, 60))
        a, b = check.analyze(plan), reference.analyze(plan)
        out.append(Check(f"random plan {k + 1}", len(plan.subnets), len(a.findings) + len(a.free) + 2, same(a, b)))
    for k in range(draws):
        supernet, existing, needs = random_request(rng, rng.randrange(1, 25))
        fast, slow = check.allocate(supernet, existing, needs), reference.allocate(supernet, existing, needs)
        ok = fast == slow and allocation_is_sound(supernet, existing, needs, fast)
        out.append(Check(f"random allocation {k + 1}", len(needs), len(fast.placed) + len(fast.unplaced), ok))
    return out

"""The rules, their order and the shapes both implementations return."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

RULES = (
    "outside_supernet",
    "overlap",
    "duplicate_name",
    "duplicate_vlan",
    "gateway_outside",
    "gateway_reserved",
    "over_capacity",
    "host_bits",
)

# One line for each rule, used by `ipam check` and in docs/method.md
SUMMARY = {
    "outside_supernet": "the subnet is not inside the supernet",
    "overlap": "two subnets share addresses",
    "duplicate_name": "two subnets have the same name",
    "duplicate_vlan": "two subnets have the same VLAN",
    "gateway_outside": "the gateway is not an address of its subnet",
    "gateway_reserved": "the gateway is the network or the broadcast address",
    "over_capacity": "more hosts are planned than the subnet can hold",
    "host_bits": "the address has bits set after the prefix (10.0.0.5/24)",
}


class Finding(NamedTuple):
    rule: str
    subject: str


@dataclass(frozen=True)
class Analysis:
    findings: list[Finding]
    free: list[str]  # the free space of the supernet as the shortest list of CIDR blocks
    used: int  # addresses of the supernet taken by at least one subnet
    free_total: int


# a finding with its sort key: (rule position, first subnet, second subnet)
Keyed = tuple[int, int, int, str]


def ordered(keyed: list[Keyed]) -> list[Finding]:
    return [Finding(RULES[r], s) for r, _i, _j, s in sorted(keyed)]


@dataclass(frozen=True)
class Allocation:
    placed: list[tuple[str, str]]  # (name, cidr) in the order they were placed
    unplaced: list[str]


MIN_PREFIX_FOR_HOSTS = 30


def prefix_for(hosts: int) -> int:
    """The longest prefix (at most /30) whose subnet holds `hosts` hosts."""
    if hosts < 1:
        raise ValueError("a request needs at least one host")
    prefix = MIN_PREFIX_FOR_HOSTS
    while prefix > 0 and (1 << (32 - prefix)) - 2 < hosts:
        prefix -= 1
    if (1 << (32 - prefix)) - 2 < hosts:
        raise ValueError(f"{hosts} hosts do not fit in any IPv4 subnet")
    return prefix

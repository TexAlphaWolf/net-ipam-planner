"""A plan is a supernet and its subnets, read strictly from JSON. Addresses are parsed here with a small parser of
our own, so that the loader does not depend on the standard library module the fast implementation is built on."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

OCTET = r"(0|[1-9]\d{0,2})"
ADDRESS = re.compile(rf"^{OCTET}\.{OCTET}\.{OCTET}\.{OCTET}$")
CIDR = re.compile(rf"^{OCTET}\.{OCTET}\.{OCTET}\.{OCTET}/(0|[1-9]\d?)$")
FULL = (1 << 32) - 1
MAX_VLAN = 4094
SUBNET_KEYS = {"name", "cidr", "vlan", "gateway", "hosts"}
PLAN_KEYS = {"name", "supernet", "subnets"}


class PlanError(ValueError):
    """The plan, a request or an option is not valid."""


def parse_address(text: str, where: str = "address") -> int:
    m = ADDRESS.match(text)
    if m is None or any(int(g) > 255 for g in m.groups()):
        raise PlanError(f"{where}: '{text}' is not an IPv4 address")
    a, b, c, d = (int(g) for g in m.groups())
    return (a << 24) | (b << 16) | (c << 8) | d


def parse_cidr(text: str, where: str = "network") -> tuple[int, int]:
    """The address (host bits are kept) and the prefix length of `a.b.c.d/p`."""
    m = CIDR.match(text)
    if m is None or any(int(g) > 255 for g in m.groups()[:4]) or int(m.group(5)) > 32:
        raise PlanError(f"{where}: '{text}' is not an IPv4 network in CIDR form")
    a, b, c, d = (int(g) for g in m.groups()[:4])
    return (a << 24) | (b << 16) | (c << 8) | d, int(m.group(5))


def fmt(address: int) -> str:
    return f"{address >> 24}.{(address >> 16) & 255}.{(address >> 8) & 255}.{address & 255}"


def mask(prefix: int) -> int:
    return (FULL << (32 - prefix)) & FULL


def usable(prefix: int) -> int:
    """Hosts a subnet can hold: all but the network and broadcast addresses; a /31 holds 2 and a /32 holds 1."""
    if prefix >= 32:
        return 1
    if prefix == 31:
        return 2
    return (1 << (32 - prefix)) - 2


@dataclass(frozen=True)
class Subnet:
    name: str
    cidr: str
    vlan: int | None = None
    gateway: str | None = None
    hosts: int | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name, "cidr": self.cidr}
        if self.vlan is not None:
            d["vlan"] = self.vlan
        if self.gateway is not None:
            d["gateway"] = self.gateway
        if self.hosts is not None:
            d["hosts"] = self.hosts
        return d


@dataclass(frozen=True)
class Plan:
    name: str
    supernet: str
    subnets: tuple[Subnet, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "supernet": self.supernet, "subnets": [s.to_dict() for s in self.subnets]}


def _int(value: Any, where: str, lo: int, hi: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < lo or (hi is not None and value > hi):
        raise PlanError(f"{where}: expected an integer from {lo}{'' if hi is None else f' to {hi}'}, found {value!r}")
    return value


def _text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 80 or "|" in value:
        raise PlanError(f"{where}: expected a name of 1 to 80 characters without '|', found {value!r}")
    return value


def from_dict(data: Any) -> Plan:
    if not isinstance(data, dict):
        raise PlanError("a plan is a JSON object")
    extra = set(data) - PLAN_KEYS
    if extra:
        raise PlanError(f"unknown keys in the plan: {sorted(extra)}")
    if "supernet" not in data or "subnets" not in data:
        raise PlanError("a plan needs a 'supernet' and a list of 'subnets'")
    supernet = data["supernet"]
    if not isinstance(supernet, str):
        raise PlanError(f"supernet: expected text, found {supernet!r}")
    address, prefix = parse_cidr(supernet, "supernet")
    if address & ~mask(prefix) & FULL:
        raise PlanError(f"supernet: '{supernet}' has host bits set")
    if not isinstance(data["subnets"], list):
        raise PlanError("'subnets' must be a list")
    subnets: list[Subnet] = []
    for i, raw in enumerate(data["subnets"]):
        where = f"subnets[{i}]"
        if not isinstance(raw, dict):
            raise PlanError(f"{where}: a subnet is a JSON object")
        extra = set(raw) - SUBNET_KEYS
        if extra:
            raise PlanError(f"{where}: unknown keys {sorted(extra)}")
        if "name" not in raw or "cidr" not in raw:
            raise PlanError(f"{where}: a subnet needs a 'name' and a 'cidr'")
        name = _text(raw["name"], f"{where}.name")
        cidr = raw["cidr"]
        if not isinstance(cidr, str):
            raise PlanError(f"{where}.cidr: expected text, found {cidr!r}")
        parse_cidr(cidr, f"{where}.cidr")
        vlan = None if raw.get("vlan") is None else _int(raw["vlan"], f"{where}.vlan", 1, MAX_VLAN)
        gateway = raw.get("gateway")
        if gateway is not None:
            if not isinstance(gateway, str):
                raise PlanError(f"{where}.gateway: expected text, found {gateway!r}")
            parse_address(gateway, f"{where}.gateway")
        hosts = None if raw.get("hosts") is None else _int(raw["hosts"], f"{where}.hosts", 0)
        subnets.append(Subnet(name, cidr, vlan, gateway, hosts))
    name = data.get("name", "plan")
    return Plan(_text(name, "name"), supernet, tuple(subnets))


def load_plan(path: str | Path) -> Plan:
    p = Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise PlanError(f"{p}: cannot be read: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise PlanError(f"{p}: not valid JSON: {exc}") from exc
    try:
        return from_dict(data)
    except PlanError as exc:
        raise PlanError(f"{p}: {exc}") from exc


def dump_plan(plan: Plan, path: str | Path) -> None:
    Path(path).write_text(json.dumps(plan.to_dict(), indent=1) + "\n", encoding="utf-8")

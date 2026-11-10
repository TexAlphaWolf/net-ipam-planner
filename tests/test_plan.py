from __future__ import annotations

import json
from pathlib import Path

import pytest

from ipamplan.plan import PlanError, dump_plan, fmt, from_dict, load_plan, mask, parse_address, parse_cidr, usable

from .conftest import plan


def test_addresses_and_networks() -> None:
    assert parse_address("10.0.0.1") == 0x0A000001 and fmt(0x0A000001) == "10.0.0.1"
    assert parse_address("255.255.255.255") == 2**32 - 1 and parse_address("0.0.0.0") == 0
    assert parse_cidr("10.0.0.5/24") == (0x0A000005, 24)  # host bits are kept
    assert parse_cidr("0.0.0.0/0") == (0, 0) and parse_cidr("1.2.3.4/32") == (0x01020304, 32)
    assert mask(24) == 0xFFFFFF00 and mask(0) == 0 and mask(32) == 0xFFFFFFFF
    for bad in ("10.0.0", "10.0.0.256", "10.0.0.01", "10.0.0.1.1", "a.b.c.d", "", " 10.0.0.1", "10.0.0.1/24"):
        with pytest.raises(PlanError):
            parse_address(bad)
    for bad in ("10.0.0.0/33", "10.0.0.0/024", "10.0.0.0", "10.0.0.0/", "10.0.0.256/8", "10.0.0.0/-1", "10.0.0.0/8 "):
        with pytest.raises(PlanError):
            parse_cidr(bad)


def test_usable_hosts() -> None:
    assert [usable(p) for p in (24, 30, 31, 32, 0)] == [254, 2, 2, 1, 2**32 - 2]


def test_a_plan_is_read_strictly() -> None:
    ok = {
        "supernet": "10.0.0.0/24",
        "subnets": [{"name": "a", "cidr": "10.0.0.0/25", "vlan": 10, "gateway": "10.0.0.1", "hosts": 5}],
    }
    p = from_dict(ok)
    assert p.name == "plan" and p.subnets[0].vlan == 10 and p.subnets[0].hosts == 5
    assert from_dict({**ok, "name": "lab"}).name == "lab"
    bad: list[tuple[object, str]] = [
        ([], "JSON object"),
        ({"supernet": "10.0.0.0/24"}, "needs"),
        ({**ok, "extra": 1}, "unknown keys"),
        ({**ok, "supernet": "10.0.0.1/24"}, "host bits"),
        ({**ok, "supernet": 5}, "expected text"),
        ({**ok, "subnets": {}}, "must be a list"),
        ({**ok, "subnets": [5]}, "JSON object"),
        ({**ok, "subnets": [{"name": "a"}]}, "needs a 'name' and a 'cidr'"),
        ({**ok, "subnets": [{"name": "a|b", "cidr": "10.0.0.0/25"}]}, "without '|'"),
        ({**ok, "subnets": [{"name": " ", "cidr": "10.0.0.0/25"}]}, "1 to 80"),
        ({**ok, "subnets": [{"name": "a", "cidr": 5}]}, "expected text"),
        ({**ok, "subnets": [{"name": "a", "cidr": "10.0.0.0/25", "vlan": 0}]}, "vlan"),
        ({**ok, "subnets": [{"name": "a", "cidr": "10.0.0.0/25", "vlan": 4095}]}, "vlan"),
        ({**ok, "subnets": [{"name": "a", "cidr": "10.0.0.0/25", "vlan": True}]}, "vlan"),
        ({**ok, "subnets": [{"name": "a", "cidr": "10.0.0.0/25", "hosts": -1}]}, "hosts"),
        ({**ok, "subnets": [{"name": "a", "cidr": "10.0.0.0/25", "gateway": 1}]}, "expected text"),
        ({**ok, "subnets": [{"name": "a", "cidr": "10.0.0.0/25", "gateway": "10.0.0"}]}, "gateway"),
        ({**ok, "subnets": [{"name": "a", "cidr": "10.0.0.0/25", "colour": "red"}]}, "unknown keys"),
        ({**ok, "name": ""}, "1 to 80"),
    ]
    for data, message in bad:
        with pytest.raises(PlanError, match=message):
            from_dict(data)


def test_files(tmp_path: Path) -> None:
    p = plan(("a", "10.0.0.0/25", 10, "10.0.0.1", 5), ("b", "10.0.0.128/25"))
    dump_plan(p, tmp_path / "p.json")
    assert load_plan(tmp_path / "p.json") == p
    (tmp_path / "bad.json").write_text("{", encoding="utf-8")
    (tmp_path / "wrong.json").write_text(json.dumps({"supernet": "x", "subnets": []}), encoding="utf-8")
    for name, message in (
        ("missing.json", "cannot be read"),
        ("bad.json", "not valid JSON"),
        ("wrong.json", "wrong.json"),
    ):
        with pytest.raises(PlanError, match=message):
            load_plan(tmp_path / name)

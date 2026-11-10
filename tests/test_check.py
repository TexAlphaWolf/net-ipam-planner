from __future__ import annotations

from collections.abc import Callable

import pytest

from ipamplan import check, reference
from ipamplan.plan import Plan, Subnet
from ipamplan.rules import RULES, Analysis, Finding

from .conftest import plan

IMPLEMENTATIONS = [check.analyze, reference.analyze]
Analyze = Callable[[Plan], Analysis]


def rules(a: Analysis) -> list[tuple[str, str]]:
    return [(f.rule, f.subject) for f in a.findings]


@pytest.fixture(params=IMPLEMENTATIONS, ids=["fast", "literal"])
def analyze(request: pytest.FixtureRequest) -> Analyze:
    return request.param  # type: ignore[no-any-return]


def test_a_clean_plan_and_its_free_space(analyze: Analyze) -> None:
    a = analyze(plan(("a", "10.0.0.0/25", 10, "10.0.0.1", 100), ("b", "10.0.0.128/26", 20, "10.0.0.129", 50)))
    assert a.findings == [] and a.used == 192 and a.free_total == 64 and a.free == ["10.0.0.192/26"]


def test_free_space_is_the_shortest_list_of_blocks(analyze: Analyze) -> None:
    a = analyze(plan(("x", "10.0.0.5/32")))
    assert a.free == [
        "10.0.0.0/30",
        "10.0.0.4/32",
        "10.0.0.6/31",
        "10.0.0.8/29",
        "10.0.0.16/28",
        "10.0.0.32/27",
        "10.0.0.64/26",
        "10.0.0.128/25",
    ]
    assert (a.used, a.free_total) == (1, 255)
    e = analyze(plan())
    assert e.free == ["10.0.0.0/24"] and e.used == 0 and e.findings == []
    full = analyze(plan(("all", "10.0.0.0/24")))
    assert full.free == [] and full.free_total == 0


def test_overlaps_nested_equal_and_adjacent(analyze: Analyze) -> None:
    a = analyze(
        plan(
            ("big", "10.0.0.0/24"),
            ("half", "10.0.0.0/25"),
            ("quarter", "10.0.0.64/26"),
            ("twin", "10.0.0.0/25"),
            ("next", "10.0.1.0/24"),
        )
    )
    assert [s for r, s in rules(a) if r == "overlap"] == [
        "big|half", "big|quarter", "big|twin", "half|quarter", "half|twin", "quarter|twin",
    ]  # fmt: skip
    assert not any(
        "next" in s for r, s in rules(a) if r == "overlap"
    )  # 10.0.1.0/24 is outside the supernet, not an overlap
    assert ("outside_supernet", "next") in rules(a)


def test_overlap_is_reported_in_input_order_whatever_the_address_order(analyze: Analyze) -> None:
    a = analyze(plan(("small", "10.0.0.64/26"), ("large", "10.0.0.0/24")))
    assert rules(a) == [("overlap", "small|large")]


def test_a_subnet_larger_than_the_supernet(analyze: Analyze) -> None:
    a = analyze(plan(("wide", "10.0.0.0/16")))
    assert rules(a) == [("outside_supernet", "wide")] and a.used == 256 and a.free == []


def test_gateways(analyze: Analyze) -> None:
    a = analyze(
        plan(
            ("ok", "10.0.0.0/28", None, "10.0.0.1"),
            ("net", "10.0.0.16/28", None, "10.0.0.16"),
            ("bcast", "10.0.0.32/28", None, "10.0.0.47"),
            ("out", "10.0.0.48/28", None, "10.0.0.64"),
            ("p2p", "10.0.0.64/31", None, "10.0.0.64"),  # on a /31 both addresses are hosts
            ("p2p2", "10.0.0.66/31", None, "10.0.0.67"),
            ("host", "10.0.0.68/32", None, "10.0.0.68"),
            ("slash30", "10.0.0.72/30", None, "10.0.0.72"),
        )
    )
    assert rules(a) == [
        ("gateway_outside", "out"),
        ("gateway_reserved", "net"),
        ("gateway_reserved", "bcast"),
        ("gateway_reserved", "slash30"),
    ]


def test_capacity(analyze: Analyze) -> None:
    a = analyze(
        plan(
            ("fits", "10.0.0.0/30", None, None, 2),
            ("over30", "10.0.0.4/30", None, None, 3),
            ("over31", "10.0.0.8/31", None, None, 3),
            ("ok31", "10.0.0.10/31", None, None, 2),
            ("ok32", "10.0.0.12/32", None, None, 1),
            ("over32", "10.0.0.13/32", None, None, 2),
            ("zero", "10.0.0.16/28", None, None, 0),
            ("full", "10.0.0.32/27", None, None, 30),
            ("over27", "10.0.0.64/27", None, None, 31),
        )
    )
    assert rules(a) == [("over_capacity", n) for n in ("over30", "over31", "over32", "over27")]


def test_host_bits(analyze: Analyze) -> None:
    a = analyze(plan(("h", "10.0.0.5/24"), ("n", "10.0.1.0/24"), ("s", "10.0.2.7/32")))
    assert [s for r, s in rules(a) if r == "host_bits"] == ["h"]
    assert a.used == 256 and a.findings[0] == Finding("outside_supernet", "n")


def test_duplicates_are_reported_once(analyze: Analyze) -> None:
    a = analyze(
        plan(
            Subnet("a", "10.0.0.0/26", 10),
            Subnet("a", "10.0.0.64/26", 10),
            Subnet("a", "10.0.0.128/26", 10),
            Subnet("b", "10.0.0.192/26", 11),
            Subnet("c", "10.0.1.0/26", None),
        )
    )
    assert [(r, s) for r, s in rules(a) if r.startswith("duplicate")] == [
        ("duplicate_name", "a"),
        ("duplicate_vlan", "10"),
    ]


def test_findings_are_ordered_by_rule_then_by_position(analyze: Analyze) -> None:
    a = analyze(
        plan(
            ("late", "10.0.1.0/24"),
            ("a", "10.0.0.0/25", 7, "10.0.0.0", 500),
            ("a", "10.0.0.64/26", 7),
            ("early", "172.16.0.0/16"),
        )
    )
    assert [r for r, _ in rules(a)] == [
        "outside_supernet", "outside_supernet", "overlap", "duplicate_name", "duplicate_vlan", "gateway_reserved", "over_capacity",
    ]  # fmt: skip
    positions = [RULES.index(r) for r, _ in rules(a)]
    assert positions == sorted(positions)


def test_the_two_implementations_agree_on_random_plans() -> None:
    from ipamplan import verify

    results = verify.run(60, 3)
    assert all(c.ok for c in results) and len(results) == 122

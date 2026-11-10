from __future__ import annotations

import random

import pytest

from ipamplan import check, generate, reference
from ipamplan.plan import parse_cidr
from ipamplan.rules import RULES
from ipamplan.score import score

from .conftest import DRAWS, SEED


def test_clean_plans_have_no_findings() -> None:
    for subnets, seed in [(10, 1), (50, 2), (300, 3), (1000, 4), (5000, 5)]:
        plan, truth = generate.generate(subnets, seed, {})
        assert truth == [] and check.analyze(plan).findings == [], (subnets, seed)
        assert len(plan.subnets) == subnets


def test_the_findings_are_exactly_the_injected_faults() -> None:
    rng = random.Random(SEED)
    for k in range(DRAWS):
        faults = {r: rng.randrange(0, 3) for r in RULES}
        plan, truth = generate.generate(200, SEED * 100 + k, faults)
        found = check.analyze(plan)
        s = score(found.findings, truth)
        assert s["missed"] == [] and s["extra"] == [] and s["found"] == s["injected"] == sum(faults.values())
        assert found == reference.analyze(plan)


def test_every_rule_can_be_injected_and_found() -> None:
    plan, truth = generate.generate(120, 1, {r: 1 for r in RULES})
    assert sorted(t["rule"] for t in truth) == sorted(RULES)
    assert {f.rule for f in check.analyze(plan).findings} == set(RULES)
    assert sum(generate.DEMO_FAULTS.values()) == 11


def test_a_plan_is_made_of_a_seed() -> None:
    assert generate.generate(80, 9, generate.DEMO_FAULTS) == generate.generate(80, 9, generate.DEMO_FAULTS)
    assert generate.generate(80, 9, {})[0] != generate.generate(80, 10, {})[0]


def test_consistent_plans_are_inside_their_supernet_with_unique_vlans() -> None:
    plan, _ = generate.generate(4500, 3, {})
    first, prefix = parse_cidr(plan.supernet)
    assert all(first <= parse_cidr(s.cidr)[0] < first + (1 << (32 - prefix)) for s in plan.subnets)
    vlans = [s.vlan for s in plan.subnets if s.vlan is not None]
    assert len(vlans) == len(set(vlans)) and 0 < len(vlans) < 4500  # there are only 4,094 VLAN numbers


def test_supernet_for_and_limits() -> None:
    assert generate.supernet_for(100) == "10.0.0.0/24"
    assert generate.supernet_for(200) == "10.0.0.0/23"
    assert generate.supernet_for(2**23) == "10.0.0.0/8"
    with pytest.raises(ValueError, match="too many subnets"):
        generate.supernet_for(2**26)
    with pytest.raises(ValueError, match="too many faults"):
        generate.generate(20, 1, generate.DEMO_FAULTS)


def test_the_score_counts_misses_and_extras() -> None:
    from ipamplan.rules import Finding

    truth = [{"rule": "overlap", "subject": "a|b"}, {"rule": "host_bits", "subject": "c"}]
    s = score([Finding("overlap", "a|b"), Finding("host_bits", "d")], truth)
    assert (s["injected"], s["found"], s["missed"], s["extra"]) == (2, 1, ["host_bits c"], ["host_bits d"])
    assert s["rules"]["overlap"] == {"injected": 1, "found": 1, "missed": 0, "extra": 0}
    assert s["rules"]["host_bits"] == {"injected": 1, "found": 0, "missed": 1, "extra": 1}

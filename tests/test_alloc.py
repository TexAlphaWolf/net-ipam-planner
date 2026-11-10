from __future__ import annotations

import random
from collections.abc import Callable

import pytest

from ipamplan import check, reference, verify
from ipamplan.rules import Allocation, prefix_for

from .conftest import DRAWS, SEED

Allocate = Callable[[str, list[str], list[tuple[str, int]]], Allocation]


@pytest.fixture(params=[check.allocate, reference.allocate], ids=["fast", "literal"])
def allocate(request: pytest.FixtureRequest) -> Allocate:
    return request.param  # type: ignore[no-any-return]


def test_prefix_for_hosts() -> None:
    assert [prefix_for(h) for h in (1, 2, 3, 6, 7, 30, 31, 254, 255, 510, 511)] == [
        30,
        30,
        29,
        29,
        28,
        27,
        26,
        24,
        23,
        23,
        22,
    ]
    assert prefix_for(2**32 - 2) == 0
    for bad in (0, -1, 2**32 - 1):
        with pytest.raises(ValueError):
            prefix_for(bad)


def test_largest_first_from_the_bottom(allocate: Allocate) -> None:
    got = allocate("10.0.0.0/24", [], [("c", 10), ("a", 100), ("b", 50)])
    assert got.placed == [("a", "10.0.0.0/25"), ("b", "10.0.0.128/26"), ("c", "10.0.0.192/28")] and got.unplaced == []


def test_ties_go_by_name(allocate: Allocate) -> None:
    got = allocate("10.0.0.0/24", [], [("z", 50), ("m", 50), ("a", 50)])
    assert got.placed == [("a", "10.0.0.0/26"), ("m", "10.0.0.64/26"), ("z", "10.0.0.128/26")]


def test_existing_subnets_are_avoided_and_blocks_stay_aligned(allocate: Allocate) -> None:
    assert allocate("10.0.0.0/24", ["10.0.0.0/26"], [("a", 100)]).placed == [("a", "10.0.0.128/25")]
    assert allocate("10.0.0.0/24", ["10.0.0.0/32"], [("a", 50)]).placed == [("a", "10.0.0.64/26")]
    assert allocate("10.0.0.0/24", ["10.0.0.5/24"], [("a", 50)]).placed == []  # host bits: the whole /24 is taken
    assert (
        allocate("10.0.0.0/24", ["192.168.0.0/24", "10.0.0.0/8"], [("a", 50)]).placed == []
    )  # a larger subnet covers it all
    assert allocate("10.0.0.0/24", ["192.168.0.0/24"], [("a", 50)]).placed == [
        ("a", "10.0.0.0/26")
    ]  # one outside is ignored


def test_what_does_not_fit(allocate: Allocate) -> None:
    got = allocate("10.0.0.0/24", [], [("big", 300), ("a", 100), ("b", 100), ("c", 10)])
    assert got.placed == [("a", "10.0.0.0/25"), ("b", "10.0.0.128/25")] and sorted(got.unplaced) == ["big", "c"]
    assert allocate("10.0.0.0/24", [], []) == Allocation([], [])


def test_the_two_implementations_agree_and_keep_their_promises() -> None:
    rng = random.Random(SEED)
    for _ in range(DRAWS):
        supernet, existing, needs = verify.random_request(rng, rng.randrange(1, 30))
        fast, slow = check.allocate(supernet, existing, needs), reference.allocate(supernet, existing, needs)
        assert fast == slow
        assert verify.allocation_is_sound(supernet, existing, needs, fast)


def test_the_soundness_check_can_fail() -> None:
    needs = [("a", 100), ("b", 100)]
    ok = Allocation([("a", "10.0.0.0/25"), ("b", "10.0.0.128/25")], [])
    assert verify.allocation_is_sound("10.0.0.0/24", [], needs, ok)
    wrong = {
        "overlap": Allocation([("a", "10.0.0.0/25"), ("b", "10.0.0.64/25")], []),
        "outside": Allocation([("a", "10.0.0.0/25"), ("b", "10.0.1.0/25")], []),
        "too small": Allocation([("a", "10.0.0.0/25"), ("b", "10.0.0.128/26")], []),
        "unaligned": Allocation([("a", "10.0.0.0/25"), ("b", "10.0.0.130/25")], []),
        "missing": Allocation([("a", "10.0.0.0/25")], []),
    }
    for what, got in wrong.items():
        assert not verify.allocation_is_sound("10.0.0.0/24", [], needs, got), what
    assert not verify.allocation_is_sound("10.0.0.0/24", ["10.0.0.0/25"], needs, ok)


def test_a_request_that_cannot_exist_is_an_error() -> None:
    with pytest.raises(ValueError):
        check.allocate("10.0.0.0/24", [], [("a", 0)])


def test_into_empty_space_everything_fits_if_the_blocks_add_up(allocate: Allocate) -> None:
    """Block sizes are powers of two and placed largest first, so nothing is lost to alignment: all of them are placed exactly
    when their sizes add up to no more than the supernet."""
    rng = random.Random(SEED)
    for _ in range(DRAWS):
        needs = [(f"r{i}", rng.choice([1, 2, 5, 12, 30, 60, 120, 250])) for i in range(rng.randrange(1, 40))]
        total = sum(1 << (32 - prefix_for(h)) for _n, h in needs)
        got = allocate("10.0.0.0/22", [], needs)
        assert (got.unplaced == []) == (total <= 1024)

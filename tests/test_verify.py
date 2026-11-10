from __future__ import annotations

import random

import pytest

from ipamplan import check, verify
from ipamplan.rules import Analysis

from .conftest import DRAWS, SEED


def test_all_comparisons_agree() -> None:
    results = verify.run(DRAWS, SEED)
    assert len(results) == 2 + 2 * DRAWS and all(c.ok for c in results)
    assert [c.name for c in results[:2]] == ["generated plan, no faults", "generated plan with faults"]


def test_the_comparison_can_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    real = check.analyze

    def lossy(plan: object) -> Analysis:
        a = real(plan)  # type: ignore[arg-type]
        return Analysis(a.findings[1:], a.free, a.used, a.free_total)

    monkeypatch.setattr(check, "analyze", lossy)
    results = verify.run(3, 1)
    assert not results[1].ok and any(not c.ok for c in results)


def test_random_plans_have_every_kind_of_mess() -> None:
    rng = random.Random(SEED)
    seen = set()
    for _ in range(40):
        seen |= {f.rule for f in check.analyze(verify.random_plan(rng, 40)).findings}
    assert len(seen) == 8

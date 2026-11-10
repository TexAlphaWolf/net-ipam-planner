"""Speed of the checks and the allocation, detection over generated plans, and agreement of the two implementations."""

from __future__ import annotations

import os
import platform
import random
import statistics
import time
from collections.abc import Callable
from typing import Any

from . import __version__, check, reference, verify
from .generate import generate
from .rules import RULES
from .score import score

LITERAL_REPEAT = 3


def timed(fn: Callable[[], object], repeat: int) -> float:
    runs = []
    for _ in range(repeat):
        t = time.perf_counter()
        fn()
        runs.append(time.perf_counter() - t)
    return statistics.median(runs)


def requests(count: int, seed: int) -> list[tuple[str, int]]:
    rng = random.Random(seed)
    return [(f"r{i:06d}", rng.choice([2, 6, 14, 30, 62, 126, 254])) for i in range(count)]


def run_bench(
    sizes: list[int],
    ref_max: int,
    alloc_sizes: list[int],
    alloc_ref_max: int,
    repeat: int,
    draws: int,
    seeds: int,
    seed: int,
    command: str,
    progress: Callable[[str], None] = lambda _m: None,
) -> dict[str, Any]:
    started = time.perf_counter()
    literal_repeat = min(repeat, LITERAL_REPEAT)
    checks = []
    progress("checking plans by number of subnets")
    for n in sizes:
        plan, _ = generate(n, seed, {})
        found = check.analyze(plan)
        row: dict[str, Any] = {
            "subnets": n,
            "fast": timed(lambda p=plan: check.analyze(p), repeat),  # type: ignore[misc]
            "literal": None,
            "findings": len(found.findings),
        }
        if n <= ref_max:
            row["literal"] = timed(lambda p=plan: reference.analyze(p), literal_repeat)  # type: ignore[misc]
        checks.append(row)
    progress("allocating subnets")
    allocs = []
    for m in alloc_sizes:
        needs = requests(m, seed)
        got = check.allocate("10.0.0.0/8", [], needs)
        row = {
            "requests": m,
            "fast": timed(lambda r=needs: check.allocate("10.0.0.0/8", [], r), repeat),  # type: ignore[misc]
            "literal": None,
            "placed": len(got.placed),
        }
        if m <= alloc_ref_max:
            row["literal"] = timed(lambda r=needs: reference.allocate("10.0.0.0/8", [], r), literal_repeat)  # type: ignore[misc]
        allocs.append(row)
    progress("detection of injected faults")
    rules = {r: {"injected": 0, "found": 0, "missed": 0, "extra": 0} for r in RULES}
    clean_findings = 0
    subnets = 200
    for s in range(1, seeds + 1):
        rng = random.Random(1000 + s)
        faults = {r: rng.randrange(0, 3) for r in RULES}
        plan, truth = generate(subnets, s, faults)
        sc = score(check.analyze(plan).findings, truth)
        for r in RULES:
            for k in rules[r]:
                rules[r][k] += sc["rules"][r][k]
        clean_findings += len(check.analyze(generate(subnets, s, {})[0]).findings)
    summary = {
        "injected": sum(r["injected"] for r in rules.values()),
        "found": sum(r["found"] for r in rules.values()),
        "missed": sum(r["missed"] for r in rules.values()),
        "extra": sum(r["extra"] for r in rules.values()),
        "clean_plans": seeds,
        "clean_findings": clean_findings,
        "rules": rules,
    }
    progress("agreement of the two implementations")
    results = verify.run(draws, seed)
    return {
        "kind": "bench",
        "environment": {
            "ipamplan": __version__,
            "python": platform.python_version(),
            "system": f"{platform.system()} {platform.machine()}",
            "cpus": os.cpu_count(),
            "seed": seed,
            "repeat": repeat,
            "literal_repeat": literal_repeat,
            "command": command,
            "seconds": round(time.perf_counter() - started, 1),
        },
        "checks": checks,
        "alloc": allocs,
        "accuracy": {"seeds": seeds, "subnets": subnets, "summary": summary},
        "verification": {
            "checks": len(results),
            "numbers": sum(c.values for c in results),
            "plans": draws,
            "allocations": draws,
            "ok": all(c.ok for c in results),
            "bad": sum(not c.ok for c in results),
        },
    }

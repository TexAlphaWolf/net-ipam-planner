"""The findings against the list of faults that were injected."""

from __future__ import annotations

from typing import Any

from .rules import RULES, Finding


def score(findings: list[Finding], truth: list[dict[str, str]]) -> dict[str, Any]:
    found = {(f.rule, f.subject) for f in findings}
    injected = {(t["rule"], t["subject"]) for t in truth}
    rules: dict[str, dict[str, int]] = {}
    for rule in RULES:
        inj = {x for x in injected if x[0] == rule}
        got = {x for x in found if x[0] == rule}
        rules[rule] = {
            "injected": len(inj),
            "found": len(inj & got),
            "missed": len(inj - got),
            "extra": len(got - inj),
        }
    return {
        "injected": len(injected),
        "found": len(injected & found),
        "missed": sorted(f"{r} {s}" for r, s in injected - found),
        "extra": sorted(f"{r} {s}" for r, s in found - injected),
        "rules": rules,
    }

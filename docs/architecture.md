# Architecture

```
            cli.py ─────────────────────────────────────────────┐
              │                                                  │
   ┌──────────┼──────────┬───────────────┬──────────┐            │
   ▼          ▼          ▼               ▼          ▼            ▼
 plan.py   check.py   reference.py   generate.py  analysis.py  verify.py, bench.py
 (reader)  (ipaddress) (integers)     (+ truth)    report.py    score.py
   │          │          │               │          │            │
   └──────────┴────┬─────┴───────────────┴──────────┴────────────┘
                   ▼
                rules.py
```

| Module | Role |
|---|---|
| `plan.py` | The strict reader of a plan, its own address parser, `usable`, `mask`, `fmt`, and `PlanError` |
| `rules.py` | The 8 rules, their order, the `Finding`, `Analysis` and `Allocation` shapes, and `prefix_for` |
| `check.py` | The fast implementation: `ipaddress`, a sweep for overlaps, merged intervals for free space, first fit over free intervals |
| `reference.py` | The literal implementation: all pairs, a cursor for free space, every candidate block against every used block |
| `generate.py` | A consistent plan by construction, then injected faults and the list of what was injected |
| `score.py` | The findings against the injected faults |
| `verify.py` | Generated and random messy plans and allocation requests, the comparison, and the soundness check of an allocation |
| `analysis.py`, `report.py`, `bench.py` | The report (JSON, Markdown, figure) and the benchmark |
| `cli.py` | The command line |

## Decisions

- **Two implementations that share nothing but the definition.** The loader, the literal code and the fast code each turn text
  into numbers in their own way (a small parser; plain integer arithmetic; `ipaddress`). A disagreement is a bug in one of them.
- **A finding is a rule and a subject, ordered.** Both implementations must return the same list in the same order, so the
  comparison is a plain equality.
- **A mistake is a finding, not an error.** The reader refuses what it cannot understand (a malformed address) but accepts what a
  checker is for: overlaps, a gateway outside its subnet, host bits.
- **Largest first, lowest first.** The allocation is deterministic, so a plan can be reviewed and reproduced; the order of the
  requests does not matter.
- **Integers and standard library only.** The only dependency is matplotlib, for the figures.
- **The report is rebuilt from its JSON.** `ipam render` produces the Markdown and the figure from `report.json` or `bench.json`
  alone, and a test checks that the files in `docs/` are exactly that render.
- **No network, no service.** The program reads files and writes files; the Docker image runs without network, with a read-only
  root and no capabilities.

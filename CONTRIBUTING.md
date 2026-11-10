# Contributing

```bash
pip install -e ".[dev]"
ruff check . && ruff format --check . && mypy && pytest --cov
```

No service is needed. `IPAM_TEST_DRAWS` and `IPAM_TEST_SEED` run the same tests with more (or different) random plans (CI also uses
150 draws with seed 11).

Rules that keep the project honest:

- **A change to a rule or to the allocation needs both implementations.** Change `check.py` (`ipaddress`) and `reference.py`
  (integers) the same way, update the definition in `docs/method.md`, add a hand-computed case to `tests/test_check.py` or
  `tests/test_alloc.py` (they run through both) and let `ipam verify` compare them.
- **A change to the generator needs the truth to stay exact.** `tests/test_generate.py` requires that clean plans have no findings
  and that the findings of faulty ones equal what was injected; keep it passing on many seeds.
- **Numbers in the README and `docs/analysis.md` come from `docs/report.json` and `docs/bench.json`**, and `tests/test_docs.py`
  checks them. After a change to the generator or the rules, regenerate them (`ipam report --out`, then `tools/run_full.ps1` for the
  benchmark) and update the text where a number moved.
- **The loader stays strict.** A new accepted deviation needs a test that says why.

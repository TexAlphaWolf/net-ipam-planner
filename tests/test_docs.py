"""The documentation must say what the measurements say."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from ipamplan import cli, generate
from ipamplan.analysis import build_report
from ipamplan.report import fmt_s, pct
from ipamplan.rules import RULES

ROOT = Path(__file__).resolve().parent.parent
REPORT = json.loads((ROOT / "docs" / "report.json").read_text(encoding="utf-8"))
BENCH = json.loads((ROOT / "docs" / "bench.json").read_text(encoding="utf-8"))
README = (ROOT / "README.md").read_text(encoding="utf-8")
ANALYSIS = (ROOT / "docs" / "analysis.md").read_text(encoding="utf-8")
METHOD = (ROOT / "docs" / "method.md").read_text(encoding="utf-8")
ACC = BENCH["accuracy"]["summary"]
CHECKS = {c["subnets"]: c for c in BENCH["checks"]}
ALLOC = {a["requests"]: a for a in BENCH["alloc"]}
ONE_LINE = re.compile(r"\s+")


def flat(text: str) -> str:
    return ONE_LINE.sub(" ", text.replace("**", ""))


def test_the_benchmark_is_what_the_text_says_it_is() -> None:
    env = BENCH["environment"]
    assert env["ipamplan"] == "1.0.0" and env["seed"] == 1 and env["repeat"] == 5 and env["literal_repeat"] == 3
    assert env["cpus"] == 12 and env["python"] == "3.14.10" and env["system"] == "Linux x86_64"
    assert sorted(CHECKS) == [1000, 10000, 100000] and sorted(ALLOC) == [100, 400, 2000, 10000]
    assert CHECKS[100000]["literal"] is None and ALLOC[400]["literal"] is None and ALLOC[100]["literal"] is not None
    assert BENCH["verification"] == {
        "checks": 102,
        "numbers": 8296,
        "plans": 50,
        "allocations": 50,
        "ok": True,
        "bad": 0,
    }
    assert BENCH["accuracy"]["seeds"] == 50 and BENCH["accuracy"]["subnets"] == 200
    assert ACC["injected"] == ACC["found"] == 375 and ACC["missed"] == ACC["extra"] == 0
    assert ACC["clean_plans"] == 50 and ACC["clean_findings"] == 0 and set(ACC["rules"]) == set(RULES)


def test_markdown_is_the_render_of_the_json(tmp_path: Path) -> None:
    for name in ("report", "bench"):
        out = tmp_path / f"{name}.md"
        assert cli.main(["render", str(ROOT / "docs" / f"{name}.json"), "-o", str(out)]) == 0
        assert out.read_text(encoding="utf-8") == (ROOT / "docs" / f"{name}.md").read_text(encoding="utf-8")


def test_the_report_is_what_the_demo_gives_today() -> None:
    plan, truth = generate.generate(cli.DEMO_SUBNETS, cli.DEMO_SEED, generate.DEMO_FAULTS)
    assert json.loads(json.dumps(build_report(plan, truth, cli.DEMO))) == REPORT


def test_figures_exist() -> None:
    for name in ("report.png", "bench.png"):
        assert (ROOT / "docs" / name).stat().st_size > 10_000


@pytest.mark.parametrize("name", ["README.md", "docs/analysis.md"])
def test_no_scaffold_left(name: str) -> None:
    text = (ROOT / name).read_text(encoding="utf-8")
    assert not re.search(
        r"work in progress|TODO|TBD|lorem|measurements pending|provisional|pre-measurement", text, re.I
    )


@pytest.mark.parametrize(
    "name", ["README.md", "docs/analysis.md", "docs/architecture.md", "docs/method.md", "docs/limitations.md"]
)
def test_local_links_resolve(name: str) -> None:
    path = ROOT / name
    for target in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", path.read_text(encoding="utf-8")):
        if target.startswith(("http://", "https://")):
            continue
        assert (path.parent / target).exists(), f"{name}: {target}"


def test_the_real_output_blocks_are_the_real_output(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    assert cli.main(["report"]) == 0
    block = re.search(r"`ipam report` \(the demo plan\):\n\n```text\n(.*?)```", README, re.S)
    assert block and block.group(1) == capsys.readouterr().out
    d = tmp_path / "dc"
    assert cli.main(["generate", str(d), "--subnets", "60", "--seed", "3"]) == 0
    capsys.readouterr()
    assert cli.main(["check", str(d / "plan.json")]) == 1
    block = re.search(r"`ipam check` on `ipam generate dc --subnets 60 --seed 3`:\n\n```text\n(.*?)```", README, re.S)
    assert block and block.group(1) == capsys.readouterr().out
    argv = [
        "alloc",
        "--supernet",
        "10.9.0.0/24",
        "--need",
        "web=100",
        "--need",
        "db=20",
        "--need",
        "lab=6",
        "--need",
        "big=1000",
    ]
    assert cli.main(argv) == 1
    block = re.search(r"`ipam alloc --supernet [^`]*` \(exit code 1[^\n]*:\n\n```text\n(.*?)```", README, re.S)
    assert block and block.group(1) == capsys.readouterr().out


def test_the_readme_numbers_are_the_measurements() -> None:
    s = REPORT
    c1, c2, c3 = CHECKS[1000], CHECKS[10000], CHECKS[100000]
    must = [
        f"{ACC['found']} faults injected into {BENCH['accuracy']['seeds']} plans",
        f"{ACC['injected']} faults, {ACC['found']} reported, {ACC['missed']} missed, {ACC['extra']} reports that are not an injected fault",
        "(50 of 50 had 0 findings before any fault went in)",
        f"{BENCH['verification']['checks']} comparisons",
        f"{BENCH['verification']['numbers']:,} values, all equal",
        f"{s['subnets']} subnets in 10.0.0.0/19 ({s['addresses']:,} addresses)",
        f"{s['used']:,} of the {s['addresses']:,} addresses ({pct(s['used_share'])})",
        f"the remaining {s['free']:,} are {s['free_blocks']} CIDR blocks, the largest a /20 ({s['largest_free_addresses']:,})",
        f"{pct(s['fragmentation'])} of the free space lies outside it",
        f"{fmt_s(ALLOC[10000]['fast'])} (237 us for 100",
        f"{fmt_s(ALLOC[100]['literal'])} for 100 requests, {ALLOC[100]['literal'] / ALLOC[100]['fast']:.0f} times longer",
        f"Checking 100,000 subnets takes {fmt_s(c3['fast'])}; 10,000 take {fmt_s(c2['fast'])}",
        f"({1e6 * c1['fast'] / 1000:.1f} us to {1e6 * c3['fast'] / 100000:.1f} us a subnet",
        f"{fmt_s(c1['literal'])} at 1,000 subnets and {fmt_s(c2['literal'])} at 10,000",
        f"{c2['literal'] / c1['literal']:.0f} times more for 10 times the subnets",
        f"{c1['literal'] / c1['fast']:.1f} times faster at 1,000 subnets and {c2['literal'] / c2['fast']:.1f} times at 10,000",
        f"{BENCH['environment']['cpus']} CPUs and Python {BENCH['environment']['python']}",
    ]
    text = flat(README)
    for m in must:
        assert flat(m) in text, m
    assert f"{1e6 * ALLOC[100]['fast'] / 100:.1f} us a request" in README or "2.4 us a request" in README


def test_the_analysis_tables_are_the_measurements() -> None:
    for rule, row in ACC["rules"].items():
        assert f"| {rule} | {row['injected']} | {row['found']} | {row['missed']} | {row['extra']} |" in ANALYSIS, rule
    for rule, row in REPORT["accuracy"]["rules"].items():
        assert f"| {rule} | {row['injected']} | {row['found']} | {row['missed']} | {row['extra']} |" in ANALYSIS, rule
    for n, c in CHECKS.items():
        lit = "-" if c["literal"] is None else fmt_s(c["literal"])
        ratio = "-" if c["literal"] is None else f"{c['literal'] / c['fast']:.1f}x"
        assert f"| {n:,} | {fmt_s(c['fast'])} | {lit} | {ratio} | {c['findings']} |" in ANALYSIS, n
    for m, a in ALLOC.items():
        lit = "-" if a["literal"] is None else fmt_s(a["literal"])
        ratio = "-" if a["literal"] is None else f"{a['literal'] / a['fast']:.1f}x"
        assert f"| {m:,} | {fmt_s(a['fast'])} | {lit} | {ratio} | {a['placed']:,} |" in ANALYSIS, m
    per = [1e6 * CHECKS[n]["fast"] / n for n in (1000, 10000, 100000)]
    assert f"{per[0]:.1f} us at 1,000 subnets to {per[1]:.1f} us at 10,000 and {per[2]:.1f} us at 100,000" in flat(
        ANALYSIS
    )
    r = REPORT
    assert f"{r['used']:,} addresses\n(48.9%)" in ANALYSIS or f"{r['used']:,} addresses (48.9%)" in flat(ANALYSIS)
    assert f"{r['free']:,} in {r['free_blocks']} CIDR blocks" in ANALYSIS


def test_the_demo_claims() -> None:
    r = REPORT
    assert r["subnets"] == 122 and r["supernet"] == "10.0.0.0/19" and r["findings"]["total"] == 11
    assert r["largest_free"] == "10.0.16.0/20" and r["by_prefix"] == {
        "24": 6,
        "25": 5,
        "26": 14,
        "27": 19,
        "28": 29,
        "29": 20,
        "30": 29,
    }
    assert (r["hosts_planned"], r["hosts_capacity"]) == (1845, 3766) and round(100 * r["fill"], 1) == 49.0
    listed = {f["subject"]: f["detail"] for f in r["findings"]["listed"]}
    assert "net-00031: 31 hosts planned in 10.0.11.128/27, which holds 30" in "net-00031: " + listed["net-00031"]
    assert "15 hosts planned in 10.0.12.192/28, which holds 14" in listed["net-00041"]
    assert "gateway 10.0.15.160 of 10.0.15.160/30" in listed["net-00115"]
    assert "10.0.15.109/30" in listed["net-00102"]
    assert "net-00002 (10.0.2.0/24) and overlap-000 (10.0.2.0/25)" in listed["net-00002|overlap-000"]


def test_the_rules_in_the_method_are_the_rules_of_the_code() -> None:
    for rule in RULES:
        assert f"| `{rule}` |" in METHOD, rule
    order = [METHOD.index(f"| `{rule}` |") for rule in RULES]
    assert order == sorted(order)

"""Command line: check, alloc, free, generate, report, verify, bench, render."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

from ipamplan import __version__, analysis, bench, check, generate, report, verify
from ipamplan.plan import Plan, PlanError, Subnet, dump_plan, fmt, load_plan, mask, parse_cidr
from ipamplan.score import score

Error = (PlanError, OSError, ValueError)
DEMO_SUBNETS, DEMO_SEED = 120, 1
DEMO = f"demo plan (synthetic, {DEMO_SUBNETS} subnets, seed {DEMO_SEED}, with injected faults)"


def summary_lines(rep: dict[str, Any]) -> list[str]:
    f = rep["findings"]
    found = ", ".join(f"{n} {rule}" for rule, n in f["by_rule"].items() if n)
    lines = [
        f"{rep['source']}: supernet {rep['supernet']}, {rep['subnets']:,} subnets, {rep['used_share'] * 100:.1f}% of the "
        f"{rep['addresses']:,} addresses allocated",
        f"{f['total']} findings: {found}" if f["total"] else "no findings",
        f"free: {rep['free']:,} addresses in {rep['free_blocks']:,} blocks, the largest is {rep['largest_free'] or 'none'}",
    ]
    if rep["accuracy"] is not None:
        a = rep["accuracy"]
        lines.append(
            f"against the injected faults: {a['found']} of {a['injected']} found, {len(a['extra'])} reports that are not an injected fault"
        )
    return lines


def _truth(path: str | None) -> list[dict[str, str]] | None:
    if path is None:
        return None
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return [{"rule": str(t["rule"]), "subject": str(t["subject"])} for t in data["faults"]]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise PlanError(f"{path}: not a truth file: {exc}") from exc


def _plan_and_truth(a: argparse.Namespace) -> tuple[Plan, list[dict[str, str]] | None, str]:
    if a.plan:
        return load_plan(a.plan), _truth(a.truth), f"plan {a.plan}"
    plan, truth = generate.generate(DEMO_SUBNETS, DEMO_SEED, generate.DEMO_FAULTS)
    return plan, truth, DEMO


def cmd_check(a: argparse.Namespace) -> int:
    plan = load_plan(a.plan)
    result = check.analyze(plan)
    shown = result.findings if a.all else result.findings[: a.limit]
    for f in shown:
        print(f"{f.rule} {f.subject}: {analysis.describe(plan, f)}")
    if len(shown) < len(result.findings):
        print(f"... and {len(result.findings) - len(shown)} more (--all shows them)")
    print(f"{len(result.findings)} findings in {len(plan.subnets)} subnets")
    truth = _truth(a.truth)
    if truth is not None:
        s = score(result.findings, truth)
        print(f"against the injected faults: {s['found']} of {s['injected']} found, {len(s['extra'])} extra")
    return 1 if result.findings else 0


def _needs(a: argparse.Namespace) -> list[tuple[str, int]]:
    needs: list[tuple[str, int]] = []
    for item in a.need or []:
        name, sep, hosts = item.rpartition("=")
        if not sep or not name or not hosts.isdigit() or int(hosts) < 1:
            raise PlanError(f"--need {item}: expected NAME=HOSTS with at least one host")
        needs.append((name, int(hosts)))
    if a.needs:
        with open(a.needs, encoding="utf-8", newline="") as fh:
            for row in csv.reader(fh):
                if not row or row[0].strip().lower() == "name":
                    continue
                if len(row) != 2 or not row[1].strip().isdigit() or int(row[1]) < 1 or "|" in row[0]:
                    raise PlanError(f"{a.needs}: expected 'name,hosts' lines, found {row}")
                needs.append((row[0].strip(), int(row[1])))
    names = [n for n, _ in needs]
    if not needs or len(set(names)) != len(names):
        raise PlanError("give at least one request, with different names (--need NAME=HOSTS or --needs FILE.csv)")
    return needs


def cmd_alloc(a: argparse.Namespace) -> int:
    if bool(a.plan) == bool(a.supernet):
        raise PlanError("give either --plan FILE or --supernet CIDR")
    if a.plan:
        plan = load_plan(a.plan)
    else:
        address, prefix = parse_cidr(a.supernet, "--supernet")
        if address != address & mask(prefix):
            raise PlanError(f"--supernet {a.supernet} has host bits set")
        plan = Plan("plan", a.supernet, ())
    needs = _needs(a)
    got = check.allocate(plan.supernet, [s.cidr for s in plan.subnets], needs)
    hosts = dict(needs)
    for name, cidr in got.placed:
        print(f"{name:<24} {cidr:<18} {hosts[name]:>7} hosts")
    if got.unplaced:
        print(f"no room for: {', '.join(sorted(got.unplaced))}")
    if a.output:
        added = []
        for name, cidr in got.placed:
            first, prefix = parse_cidr(cidr)
            added.append(Subnet(name, cidr, None, fmt(first + 1) if prefix <= 30 else None, hosts[name]))
        dump_plan(Plan(plan.name, plan.supernet, (*plan.subnets, *added)), a.output)
        print(f"written: {a.output}")
    return 1 if got.unplaced else 0


def cmd_free(a: argparse.Namespace) -> int:
    plan = load_plan(a.plan)
    result = check.analyze(plan)
    print(f"{result.free_total:,} free addresses in {len(result.free):,} blocks of {plan.supernet}")
    for block in result.free[: a.limit]:
        print(f"  {block}")
    if len(result.free) > a.limit:
        print(f"  ... and {len(result.free) - a.limit} more")
    return 0


def cmd_generate(a: argparse.Namespace) -> int:
    out = Path(a.directory)
    targets = [out / "plan.json", out / "truth.json"]
    if any(t.exists() for t in targets):
        raise PlanError(f"{out}: plan.json or truth.json exists already, nothing was overwritten")
    faults = {} if a.clean else generate.DEMO_FAULTS
    plan, truth = generate.generate(a.subnets, a.seed, faults)
    out.mkdir(parents=True, exist_ok=True)
    dump_plan(plan, targets[0])
    targets[1].write_text(json.dumps({"seed": a.seed, "faults": truth}, indent=1) + "\n", encoding="utf-8")
    print(f"written: {targets[0]}, {targets[1]} ({len(plan.subnets)} subnets, {len(truth)} injected faults)")
    return 0


def cmd_report(a: argparse.Namespace) -> int:
    plan, truth, source = _plan_and_truth(a)
    rep = analysis.build_report(plan, truth, source)
    for line in summary_lines(rep):
        print(line)
    if a.out:
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "report.json").write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
        (out / "report.md").write_text(report.render_report(rep), encoding="utf-8")
        report.report_figure(rep, out / "summary.png")
        print(f"written: {out / 'report.json'}, {out / 'report.md'}, {out / 'summary.png'}")
    return 0


def cmd_verify(a: argparse.Namespace) -> int:
    results = verify.run(a.draws, a.seed)
    bad = [c for c in results if not c.ok]
    for c in results:
        print(f"{'ok  ' if c.ok else 'FAIL'} {c.name}: {c.items} items, {c.values:,} values")
    print(f"{len(results) - len(bad)} of {len(results)} comparisons agree with the literal implementation")
    return 1 if bad else 0


def _sizes(text: str, option: str) -> list[int]:
    sizes = [int(p.replace("_", "")) for p in text.split(",") if p.strip()]
    if not sizes or any(s < 10 for s in sizes):
        raise ValueError(f"{option} needs whole numbers of 10 or more")
    return sizes


def cmd_bench(a: argparse.Namespace) -> int:
    result = bench.run_bench(
        _sizes(a.sizes, "--sizes"), a.ref_max, _sizes(a.alloc_sizes, "--alloc-sizes"), a.alloc_ref_max,
        a.repeat, a.draws, a.seeds, a.seed, a.cmdline, lambda m: print(m, flush=True),
    )  # fmt: skip
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "bench.json").write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    (out / "bench.md").write_text(report.render_bench(result), encoding="utf-8")
    report.bench_figure(result, out / "summary.png")
    print(f"written: {out / 'bench.json'}, {out / 'bench.md'}, {out / 'summary.png'}")
    return 0 if result["verification"]["ok"] else 1


def cmd_render(a: argparse.Namespace) -> int:
    try:
        data = json.loads(Path(a.file).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PlanError(f"cannot read {a.file}: {exc}") from exc
    kind = data.get("kind") if isinstance(data, dict) else None
    if kind not in ("report", "bench"):
        raise PlanError(f"{a.file} is neither a report.json nor a bench.json")
    text = report.render_report(data) if kind == "report" else report.render_bench(data)
    if a.output:
        Path(a.output).write_text(text, encoding="utf-8")
        print(f"written: {a.output}")
    else:
        print(text, end="")
    if a.figure:
        (report.report_figure if kind == "report" else report.bench_figure)(data, Path(a.figure))
        print(f"written: {a.figure}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ipam", description="Plan an IPv4 address space, with every result computed twice."
    )
    p.add_argument("--version", action="version", version=f"ipam {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    def add(name: str, func: Any, help_: str) -> argparse.ArgumentParser:
        sp = sub.add_parser(name, help=help_)
        sp.set_defaults(func=func)
        return sp

    s = add("check", cmd_check, "the findings of a plan (exit code 1 if there are any)")
    s.add_argument("plan")
    s.add_argument("--truth", help="a truth.json from `ipam generate`: score the findings against the injected faults")
    s.add_argument("--limit", type=int, default=30)
    s.add_argument("--all", action="store_true")
    s = add("alloc", cmd_alloc, "place subnets for given numbers of hosts (first fit, largest first)")
    s.add_argument("--plan", help="a plan: its supernet and subnets are the space and what is taken")
    s.add_argument("--supernet", help="an empty supernet, e.g. 10.0.0.0/16, instead of --plan")
    s.add_argument("--need", action="append", metavar="NAME=HOSTS", help="a request; repeat it")
    s.add_argument("--needs", metavar="FILE.csv", help="requests as name,hosts lines")
    s.add_argument("-o", "--output", help="write the plan with the new subnets added")
    s = add("free", cmd_free, "the free space of a plan as CIDR blocks")
    s.add_argument("plan")
    s.add_argument("--limit", type=int, default=20)
    s = add("generate", cmd_generate, "write plan.json and truth.json, a synthetic plan with injected faults")
    s.add_argument("directory")
    s.add_argument("--subnets", type=int, default=DEMO_SUBNETS)
    s.add_argument("--seed", type=int, default=DEMO_SEED)
    s.add_argument("--clean", action="store_true", help="no faults")
    s = add("report", cmd_report, "the report of a plan (the demo plan without one)")
    s.add_argument("plan", nargs="?")
    s.add_argument("--truth")
    s.add_argument("--out", help="write report.json, report.md and summary.png here")
    s = add("verify", cmd_verify, "compare the two implementations on generated and random data")
    s.add_argument("--draws", type=int, default=25)
    s.add_argument("--seed", type=int, default=1)
    s = add("bench", cmd_bench, "speed of the checks and of the allocation, detection and agreement")
    s.add_argument("--sizes", default="1000,10000,100000", help="numbers of subnets to time the check on")
    s.add_argument("--ref-max", type=int, default=10000, help="largest size on which the literal check is timed")
    s.add_argument("--alloc-sizes", default="100,400,2000,10000", help="numbers of requests to time the allocation on")
    s.add_argument(
        "--alloc-ref-max", type=int, default=200, help="largest number of requests for the literal allocation"
    )
    s.add_argument("--repeat", type=int, default=5)
    s.add_argument("--draws", type=int, default=50)
    s.add_argument("--seeds", type=int, default=50, help="generated plans for the detection score")
    s.add_argument("--seed", type=int, default=1)
    s.add_argument("--out", default="ipam-out")
    s = add("render", cmd_render, "rebuild the Markdown (and figure) from a report.json or bench.json")
    s.add_argument("file")
    s.add_argument("-o", "--output")
    s.add_argument("--figure")
    return p


def main(argv: list[str] | None = None) -> int:
    given = sys.argv[1:] if argv is None else argv
    args = build_parser().parse_args(given)
    args.cmdline = " ".join(given)
    try:
        return int(args.func(args))
    except Error as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

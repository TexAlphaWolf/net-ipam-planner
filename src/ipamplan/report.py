"""Markdown and figures from a `report.json` or a `bench.json`. The Markdown is a pure function of the JSON."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

from .rules import SUMMARY

COLORS = {"main": "#0072b2", "grey": "#666666", "accent": "#d55e00", "second": "#009e73"}


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def fmt_s(s: float) -> str:
    if s < 1e-3:
        return f"{s * 1e6:,.0f} us"
    if s < 1:
        return f"{s * 1e3:,.1f} ms"
    return f"{s:,.2f} s"


def render_report(rep: dict[str, Any]) -> str:
    f = rep["findings"]
    out = [
        f"# Report: {rep['plan']}",
        "",
        f"Source: {rep['source']}. Supernet {rep['supernet']} ({rep['addresses']:,} addresses), {rep['subnets']:,} subnets.",
        "",
        "## 1. The address space",
        "",
        "| | |",
        "|---|---|",
        f"| Allocated | {rep['used']:,} addresses ({pct(rep['used_share'])}) |",
        f"| Free | {rep['free']:,} addresses in {rep['free_blocks']:,} blocks |",
        f"| Largest free block | {rep['largest_free'] or '-'} ({rep['largest_free_addresses']:,} addresses) |",
        f"| Fragmentation | {pct(rep['fragmentation'])} of the free space is outside the largest free block |",
        f"| Hosts planned | {rep['hosts_planned']:,} of {rep['hosts_capacity']:,} usable addresses of the subnets that state them ({pct(rep['fill'])}) |",
        "",
        "## 2. Subnets by prefix",
        "",
        "| Prefix | Subnets | Addresses each |",
        "|---|---|---|",
    ]
    for prefix, count in rep["by_prefix"].items():
        out.append(f"| /{prefix} | {count:,} | {1 << (32 - int(prefix)):,} |")
    out += ["", "## 3. Findings", "", f"{f['total']:,} findings.", "", "| Rule | Count | Meaning |", "|---|---|---|"]
    for rule, count in f["by_rule"].items():
        out.append(f"| {rule} | {count} | {SUMMARY[rule]} |")
    if f["listed"]:
        out += ["", f"The first {len(f['listed'])}:", ""]
        out += [f"- `{x['rule']}` {x['subject']}: {x['detail']}" for x in f["listed"]]
    out += ["", "## 4. Most unused room", "", "| Subnet | Network | Usable addresses not planned |", "|---|---|---|"]
    out += [f"| {u['name']} | {u['cidr']} | {u['unused']:,} |" for u in rep["unused"]]
    acc = rep["accuracy"]
    if acc is not None:
        out += [
            "",
            "## 5. Against the injected faults",
            "",
            f"{acc['found']} of {acc['injected']} injected faults found; {len(acc['extra'])} reports that are not an injected fault.",
            "",
            "| Rule | Injected | Found | Missed | Extra |",
            "|---|---|---|---|---|",
        ]
        out += [
            f"| {rule} | {r['injected']} | {r['found']} | {r['missed']} | {r['extra']} |"
            for rule, r in acc["rules"].items()
            if r["injected"] or r["extra"]
        ]
    out.append("")
    return "\n".join(out)


def report_figure(rep: dict[str, Any], path: Path) -> None:
    fig = plt.figure(figsize=(19.5, 6), constrained_layout=True)
    grid = fig.add_gridspec(2, 3, height_ratios=[1, 6])
    top = fig.add_subplot(grid[0, :])
    top.imshow([rep["map"]], aspect="auto", cmap="Blues", vmin=0, vmax=1, interpolation="nearest")
    top.set_yticks([])
    top.set_xticks([0, 63.5, 127], [rep["supernet"].split("/")[0], "middle", "end"])
    top.set_title(f"Supernet {rep['supernet']}: share of each 1/128 that the subnets take (dark = allocated)")
    prefixes = rep["by_prefix"]
    ax1 = fig.add_subplot(grid[1, 0])
    ax1.bar([f"/{p}" for p in prefixes], list(prefixes.values()), color=COLORS["main"])
    ax1.set(title="Subnets by prefix", ylabel="subnets")
    rules = rep["findings"]["by_rule"]
    ax2 = fig.add_subplot(grid[1, 1])
    ax2.barh(list(rules)[::-1], list(rules.values())[::-1], color=COLORS["accent"])
    ax2.set(title="Findings by rule", xlabel="findings")
    ax2.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax3 = fig.add_subplot(grid[1, 2])
    parts = [rep["used"], rep["free"] - rep["largest_free_addresses"], rep["largest_free_addresses"]]
    ax3.bar(
        ["allocated", "free, in small blocks", "largest free block"],
        parts,
        color=[COLORS["main"], COLORS["grey"], COLORS["second"]],
    )
    ax3.set(title="Where the addresses are", ylabel="addresses")
    ax3.tick_params(axis="x", labelrotation=12)
    for a in (top, ax1, ax2, ax3):
        a.spines[["top", "right"]].set_visible(False)
    fig.savefig(path, dpi=100)
    plt.close(fig)


def render_bench(b: dict[str, Any]) -> str:
    env = b["environment"]
    out = [
        "# Benchmark",
        "",
        f"Run on {env['system']}, {env['cpus']} CPUs, Python {env['python']}; seed {env['seed']}; each time is the median of {env['repeat']} runs "
        f"(at most {env['literal_repeat']} for the literal implementation); command `{env['command']}`.",
        "",
        "## 1. Checking a plan: the standard library against the literal implementation",
        "",
        "| Subnets | Standard library | Literal | Ratio | Findings |",
        "|---|---|---|---|---|",
    ]
    for r in b["checks"]:
        lit = "-" if r["literal"] is None else fmt_s(r["literal"])
        ratio = "-" if r["literal"] is None else f"{r['literal'] / r['fast']:,.1f}x"
        out.append(f"| {r['subnets']:,} | {fmt_s(r['fast'])} | {lit} | {ratio} | {r['findings']:,} |")
    out += [
        "",
        "## 2. Allocating subnets",
        "",
        "| Requests | Standard library | Literal | Ratio | Placed |",
        "|---|---|---|---|---|",
    ]
    for r in b["alloc"]:
        lit = "-" if r["literal"] is None else fmt_s(r["literal"])
        ratio = "-" if r["literal"] is None else f"{r['literal'] / r['fast']:,.1f}x"
        out.append(f"| {r['requests']:,} | {fmt_s(r['fast'])} | {lit} | {ratio} | {r['placed']:,} |")
    a = b["accuracy"]["summary"]
    out += [
        "",
        "## 3. Detection of injected faults",
        "",
        f"{b['accuracy']['seeds']} generated plans of {b['accuracy']['subnets']} subnets, each given 0 to 2 faults of each of the {len(a['rules'])} kinds: "
        f"{a['injected']} injected, {a['found']} found, {a['missed']} missed, {a['extra']} reports that are not an injected fault; "
        f"{a['clean_plans']} plans without faults gave {a['clean_findings']} findings.",
        "",
        "| Rule | Injected | Found | Missed | Extra |",
        "|---|---|---|---|---|",
    ]
    out += [
        f"| {rule} | {r['injected']} | {r['found']} | {r['missed']} | {r['extra']} |" for rule, r in a["rules"].items()
    ]
    v = b["verification"]
    out += [
        "",
        "## 4. Agreement",
        "",
        f"{v['checks']} comparisons (2 generated plans, {v['plans']} random plans and {v['allocations']} random allocations): "
        f"{v['numbers']:,} values compared. " + ("All agree." if v["ok"] else "THEY DISAGREE."),
        "",
    ]
    return "\n".join(out)


def bench_figure(b: dict[str, Any], path: Path) -> None:
    fig, ax = plt.subplots(1, 2, figsize=(13, 5), constrained_layout=True)
    for a, rows, key, title in (
        (ax[0], b["checks"], "subnets", "Checking a plan: time by number of subnets"),
        (ax[1], b["alloc"], "requests", "Allocating: time by number of requests"),
    ):
        a.plot([r[key] for r in rows], [r["fast"] for r in rows], "o-", color=COLORS["main"], label="standard library")
        lit = [r for r in rows if r["literal"] is not None]
        a.plot([r[key] for r in lit], [r["literal"] for r in lit], "s--", color=COLORS["grey"], label="literal")
        a.set(xscale="log", yscale="log", title=title, xlabel=key, ylabel="seconds")
        a.legend(frameon=False)
        a.spines[["top", "right"]].set_visible(False)
    fig.savefig(path, dpi=100)
    plt.close(fig)

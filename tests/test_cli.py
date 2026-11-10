from __future__ import annotations

import json
from pathlib import Path

import pytest

from ipamplan import __version__, cli
from ipamplan.plan import fmt, parse_cidr


def run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    code = cli.main(list(argv))
    cap = capsys.readouterr()
    return code, cap.out, cap.err


@pytest.fixture
def made(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Path:
    assert run(capsys, "generate", str(tmp_path / "d"), "--subnets", "60", "--seed", "3")[0] == 0
    return tmp_path / "d"


def test_version_and_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0 and __version__ in capsys.readouterr().out


def test_generate_check_and_the_truth(made: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert json.loads((made / "truth.json").read_text(encoding="utf-8"))["seed"] == 3
    code, out, _ = run(capsys, "check", str(made / "plan.json"), "--truth", str(made / "truth.json"))
    assert (
        code == 1
        and "11 findings in 62 subnets" in out
        and "against the injected faults: 11 of 11 found, 0 extra" in out
    )
    assert "overlap net-00000|overlap-000: net-00000 (10.0.0.0/24) and overlap-000 (10.0.0.0/25) share addresses" in out
    code, out, _ = run(capsys, "check", str(made / "plan.json"), "--limit", "2")
    assert code == 1 and "... and 9 more (--all shows them)" in out
    code, out, _ = run(capsys, "check", str(made / "plan.json"), "--all")
    assert out.count("\n") == 12


def test_a_clean_plan_exits_zero_and_files_are_not_overwritten(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    d = tmp_path / "c"
    assert run(capsys, "generate", str(d), "--subnets", "40", "--clean")[0] == 0
    code, out, _ = run(capsys, "check", str(d / "plan.json"))
    assert code == 0 and out == "0 findings in 40 subnets\n"
    code, _, err = run(capsys, "generate", str(d))
    assert code == 2 and "nothing was overwritten" in err


def test_alloc(made: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "alloc", "--supernet", "10.9.0.0/24", "--need", "web=100", "--need", "db=20")
    assert code == 0 and out.splitlines() == [
        "web                      10.9.0.0/25            100 hosts",
        "db                       10.9.0.128/27           20 hosts",
    ]
    code, out, _ = run(capsys, "alloc", "--supernet", "10.9.0.0/24", "--need", "big=1000", "--need", "a=10")
    assert code == 1 and "no room for: big" in out
    csv = tmp_path / "needs.csv"
    csv.write_text("name,hosts\nweb,100\nlab,6\n", encoding="utf-8")
    out_plan = tmp_path / "out.json"
    code, out, _ = run(capsys, "alloc", "--plan", str(made / "plan.json"), "--needs", str(csv), "-o", str(out_plan))
    assert code == 0 and f"written: {out_plan}" in out
    new = {s["name"]: s for s in json.loads(out_plan.read_text(encoding="utf-8"))["subnets"]}
    assert (
        new["web"]["hosts"] == 100
        and new["web"]["gateway"] == fmt(parse_cidr(new["web"]["cidr"])[0] + 1)
        and len(json.loads(out_plan.read_text(encoding="utf-8"))["subnets"]) == 62 + 2
    )
    assert run(capsys, "check", str(out_plan))[1].endswith("11 findings in 64 subnets\n")  # the new ones add no finding


def test_alloc_errors(made: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text("web;100\n", encoding="utf-8")
    cases = [
        ("alloc", "--need", "a=5"),
        ("alloc", "--supernet", "10.0.0.0/24", "--plan", str(made / "plan.json"), "--need", "a=5"),
        ("alloc", "--supernet", "10.0.0.1/24", "--need", "a=5"),
        ("alloc", "--supernet", "nonsense", "--need", "a=5"),
        ("alloc", "--supernet", "10.0.0.0/24"),
        ("alloc", "--supernet", "10.0.0.0/24", "--need", "a=0"),
        ("alloc", "--supernet", "10.0.0.0/24", "--need", "a"),
        ("alloc", "--supernet", "10.0.0.0/24", "--need", "a=1", "--need", "a=2"),
        ("alloc", "--supernet", "10.0.0.0/24", "--needs", str(bad_csv)),
        ("alloc", "--supernet", "10.0.0.0/24", "--needs", str(tmp_path / "missing.csv")),
        ("alloc", "--supernet", "10.0.0.0/24", "--need", "a=4294967295"),
        ("check", str(tmp_path / "missing.json")),
        ("check", str(made / "plan.json"), "--truth", str(made / "plan.json")),
        ("render", str(tmp_path / "missing.json")),
        ("render", str(made / "plan.json")),
    ]
    for argv in cases:
        code, _, err = run(capsys, *argv)
        assert code == 2 and err.startswith("error: "), argv


def test_free(made: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "free", str(made / "plan.json"), "--limit", "3")
    assert code == 0 and out.startswith("5,436 free addresses in 9 blocks of 10.0.0.0/19\n") and "... and 6 more" in out


def test_report_and_render(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "report", "--out", str(tmp_path / "o"))
    assert code == 0 and out.startswith(cli.DEMO.split(":")[0].replace("demo plan", "demo plan"))
    rep = json.loads((tmp_path / "o" / "report.json").read_text(encoding="utf-8"))
    assert rep["accuracy"]["found"] == rep["accuracy"]["injected"] == 11
    assert (tmp_path / "o" / "summary.png").stat().st_size > 10_000
    code, out, _ = run(capsys, "render", str(tmp_path / "o" / "report.json"))
    assert out == (tmp_path / "o" / "report.md").read_text(encoding="utf-8")
    code, _, _ = run(
        capsys,
        "render",
        str(tmp_path / "o" / "report.json"),
        "-o",
        str(tmp_path / "x.md"),
        "--figure",
        str(tmp_path / "x.png"),
    )
    assert (tmp_path / "x.md").read_text(encoding="utf-8") == out and (tmp_path / "x.png").exists()


def test_report_of_a_plan(made: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "report", str(made / "plan.json"), "--truth", str(made / "truth.json"))
    assert (
        code == 0
        and "plan " in out.splitlines()[0]
        and out.splitlines()[-1].startswith("against the injected faults: 11 of 11")
    )
    code, out, _ = run(capsys, "report", str(made / "plan.json"))
    assert "against" not in out


def test_verify(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    code, out, _ = run(capsys, "verify", "--draws", "2")
    assert code == 0 and out.splitlines()[-1] == "6 of 6 comparisons agree with the literal implementation"
    from ipamplan import verify

    monkeypatch.setattr(verify, "same", lambda a, b: False)
    code, out, _ = run(capsys, "verify", "--draws", "1")
    assert code == 1 and "FAIL generated plan" in out


def test_bench_small(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    argv = [
        "bench",
        "--sizes",
        "50,100",
        "--ref-max",
        "50",
        "--alloc-sizes",
        "20,40",
        "--alloc-ref-max",
        "20",
        "--repeat",
        "1",
        "--draws",
        "2",
        "--seeds",
        "3",
        "--out",
        str(tmp_path / "b"),
    ]
    code, out, _ = run(capsys, *argv)
    assert code == 0 and "written:" in out
    b = json.loads((tmp_path / "b" / "bench.json").read_text(encoding="utf-8"))
    assert b["verification"]["ok"] and b["checks"][1]["literal"] is None and b["alloc"][0]["literal"] is not None
    assert b["accuracy"]["summary"]["missed"] == 0 and b["accuracy"]["summary"]["clean_findings"] == 0
    assert (tmp_path / "b" / "bench.md").read_text(encoding="utf-8") == cli.report.render_bench(b)
    code, _, err = run(capsys, "bench", "--sizes", "5", "--out", str(tmp_path / "c"))
    assert code == 2 and "--sizes" in err
    assert run(capsys, "render", str(tmp_path / "b" / "bench.json"), "--figure", str(tmp_path / "b.png"))[0] == 0

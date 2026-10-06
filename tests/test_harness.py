"""Flag-path tests for ruff_difftest.py, driven by fake ruff binaries.

Hermetic and offline: every "binary" is a tiny executable Python script with
its behavior baked in at creation time. Each fake accepts exactly the argv
shapes the harness uses (`check . --select S --fix --unsafe-fixes --config P`
and `format . --config P`), refuses anything else with exit 3, logs the argv
it received, and captures the config file the harness handed it -- so tests
assert the harness passed the documented flags, not just that something ran.

Flag paths covered, in both directions (fires / stays quiet), plus a
mutation-proof that each detection is load-bearing:

- CONVERGE-FAIL   (stderr "Failed to converge")   -- base side and fixed side
- NON-IDEMPOTENT  (fix pass 1 != pass 2)          -- base, fixed, and both
- DIFF            (pass-2 snapshots differ)       -- and the all-quiet case
- format attribution: patched-only vs pre-existing (both builds), and the
  None contract for non-DIFF files
- collect: --max-per-root, multiple roots, non-.py exclusion, layout
- report: summary.json + results.json schema, interesting-row filter,
  --report omitted
- run protocol: exactly two check passes per build with identical argv,
  format probe only for DIFF files, preview=true config threaded through

Run:  uv run --with pytest pytest tests/test_harness.py -v
"""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import stat
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parent.parent

import ruff_difftest as h  # noqa: E402

FAKE_RUFF_TEMPLATE = r"""#!/usr/bin/env python3
# Fake ruff binary with baked-in behavior (see tests/test_harness.py).
import pathlib
import sys

CHECK = {check!r}
CONVERGE = {converge!r}
FMT = {fmt!r}
ONLY = {only!r}
LOG = {log!r}

args = sys.argv[1:]
if LOG:
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(" ".join(args) + "\n")

shape_ok = len(args) >= 2 and args[0] in ("check", "format") and args[1] == "."
if shape_ok and args[0] == "check":
    shape_ok = all(
        flag in args for flag in ("--select", "--fix", "--unsafe-fixes", "--config")
    )
elif shape_ok:
    shape_ok = "--config" in args
if not shape_ok:
    sys.stderr.write("fake-ruff: unexpected argv: %r\n" % (args,))
    sys.exit(3)

if args[0] == "check" and LOG:
    cfg = args[args.index("--config") + 1]
    pathlib.Path(LOG).with_suffix(".configcapture").write_text(
        pathlib.Path(cfg).read_text(encoding="utf-8"), encoding="utf-8"
    )

targets = [
    p
    for p in sorted(pathlib.Path(".").glob("*.py"))
    if ONLY is None or p.match(ONLY)
]

if args[0] == "check":
    for p in targets:
        s = p.read_text(encoding="utf-8")
        if CHECK == "append-A" and "# mark-A" not in s:
            s = s.rstrip("\n") + "\n# mark-A\n"
        elif CHECK == "append-B" and "# mark-B" not in s:
            s = s.rstrip("\n") + "\n# mark-B\n"
        elif CHECK == "counter":
            s = s.rstrip("\n") + "\n# tick-%d\n" % (s.count("# tick") + 1)
        p.write_text(s, encoding="utf-8")
    if CONVERGE:
        sys.stderr.write(
            "debug: Failed to converge after 100 iterations in `case.py`\n"
        )
elif args[0] == "format":
    for p in targets:
        s = p.read_text(encoding="utf-8")
        if FMT == "rewrite" and "# formatted" not in s:
            p.write_text(s.rstrip("\n") + "\n# formatted\n", encoding="utf-8")
"""


def make_fake(
    directory: Path,
    name: str,
    *,
    check: str = "still",
    converge: bool = False,
    fmt: str = "still",
    only: str | None = None,
    log: bool = False,
) -> Path:
    """Write an executable fake ruff binary with the given baked-in behavior.

    check:   still     check leaves the file untouched (identity)
             append-A  appends "# mark-A" once (idempotent diff vs base)
             append-B  appends "# mark-B" once (idempotent, differs from A)
             counter   appends "# tick-N" every run (never idempotent)
    converge emit ruff's stderr "Failed to converge" marker
    fmt:     still     format leaves the file untouched
             rewrite   format appends "# formatted" (disagrees with check)
    only:    optional glob; the fake only touches matching *.py files
    log:     append every argv line to <name>.argv.log next to the binary,
             and capture the --config file's content next to it
    """
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(
        FAKE_RUFF_TEMPLATE.format(
            check=check,
            converge=converge,
            fmt=fmt,
            only=only,
            log=str(directory / f"{name}.argv.log") if log else "",
        ),
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def build_run(
    root: Path,
    module=None,
    *,
    base_kwargs: dict,
    fixed_kwargs: dict,
    files: tuple[str, ...] = ("case.py",),
    content: str = "x=1\n",
    select: str = "E301,I001",
    jobs: int = 1,
    report: bool = True,
) -> SimpleNamespace:
    """Create a corpus + fake pair under root, run the harness, parse reports."""
    if module is None:
        module = h
    root.mkdir(parents=True, exist_ok=True)
    corpus = root / "corpus"
    corpus.mkdir()
    for name in files:
        (corpus / name).write_text(content, encoding="utf-8")
    bindir = root / "bin"
    base = make_fake(bindir, "ruff-base", log=True, **base_kwargs)
    fixed = make_fake(bindir, "ruff-fixed", log=True, **fixed_kwargs)
    report_dir = root / "report"
    argv = [
        "run",
        "--corpus",
        str(corpus),
        "--base",
        str(base),
        "--fixed",
        str(fixed),
        "--select",
        select,
        "--jobs",
        str(jobs),
    ]
    if report:
        argv += ["--report", str(report_dir)]
    code = module.main_with_argv(argv)
    summary = results = None
    if report:
        summary = json.loads((report_dir / "summary.json").read_text(encoding="utf-8"))
        results = json.loads((report_dir / "results.json").read_text(encoding="utf-8"))
    return SimpleNamespace(
        code=code,
        summary=summary,
        results=results,
        report_dir=report_dir,
        corpus=corpus,
        base=base,
        fixed=fixed,
    )


def load_harness_variant(path: Path, module_name: str):
    """Import a (possibly mutated) copy of the harness as a fresh module."""
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec: dataclasses.resolve_lookup needs sys.modules
    # to find the module by name while its classes are being defined.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


ROW_FIELDS = {f.name for f in dataclasses.fields(h.FileResult)}


def test_identity_builds_leave_every_flag_quiet(tmp_path):
    run = build_run(
        tmp_path, base_kwargs={"check": "still"}, fixed_kwargs={"check": "still"}
    )
    assert run.code == 0
    s = run.summary
    assert s["corpus_size"] == 1
    assert s["select"] == "E301,I001"
    for key in (
        "base_converge_failures",
        "fixed_converge_failures",
        "base_non_idempotent",
        "fixed_non_idempotent",
        "differing_files",
        "diffs_formatter_disagrees_both",
        "diffs_formatter_disagrees_only_fixed",
        "errors",
    ):
        assert s[key] == 0, key
    assert run.results == []
    # Two check passes per build (fix + idempotence snapshot), no format probe.
    for who in ("ruff-base", "ruff-fixed"):
        log = (tmp_path / "bin" / f"{who}.argv.log").read_text(encoding="utf-8")
        lines = log.splitlines()
        assert len([x for x in lines if x.startswith("check")]) == 2
        assert len([x for x in lines if x.startswith("format")]) == 0


def test_appending_fixed_differs_while_staying_idempotent(tmp_path):
    """Base is identity; fixed appends '# fixed'-style marker only if absent."""
    run = build_run(
        tmp_path, base_kwargs={"check": "still"}, fixed_kwargs={"check": "append-A"}
    )
    assert run.code == 0
    s = run.summary
    assert s["differing_files"] == 1
    assert s["base_non_idempotent"] == 0
    assert s["fixed_non_idempotent"] == 0
    assert s["base_converge_failures"] == 0
    assert s["fixed_converge_failures"] == 0
    assert s["errors"] == 0
    (row,) = run.results
    assert set(row) == ROW_FIELDS
    assert row["path"] == "case.py"
    assert row["outputs_differ"] is True
    # DIFF row: format pass ran for both builds; neither fake rewrites here.
    assert row["base_format_disagrees"] is False
    assert row["fixed_format_disagrees"] is False


def test_non_idempotent_fixed_build_flagged(tmp_path):
    run = build_run(
        tmp_path, base_kwargs={"check": "still"}, fixed_kwargs={"check": "counter"}
    )
    assert run.code == 0
    s = run.summary
    assert s["fixed_non_idempotent"] == 1
    assert s["base_non_idempotent"] == 0
    (row,) = run.results
    assert row["fixed_non_idempotent"] is True
    assert row["base_non_idempotent"] is False
    assert row["outputs_differ"] is True


def test_non_idempotent_base_build_flagged(tmp_path):
    run = build_run(
        tmp_path, base_kwargs={"check": "counter"}, fixed_kwargs={"check": "still"}
    )
    assert run.code == 0
    s = run.summary
    assert s["base_non_idempotent"] == 1
    assert s["fixed_non_idempotent"] == 0
    (row,) = run.results
    assert row["base_non_idempotent"] is True
    assert row["fixed_non_idempotent"] is False


def test_non_idempotent_both_builds_without_output_diff(tmp_path):
    run = build_run(
        tmp_path, base_kwargs={"check": "counter"}, fixed_kwargs={"check": "counter"}
    )
    s = run.summary
    assert s["base_non_idempotent"] == 1
    assert s["fixed_non_idempotent"] == 1
    assert s["differing_files"] == 0  # identical tick pattern on both sides
    (row,) = run.results  # still interesting via non-idempotence alone
    assert row["outputs_differ"] is False
    assert row["base_format_disagrees"] is None  # no DIFF -> no format pass
    assert row["fixed_format_disagrees"] is None


def test_convergence_failure_flagged_for_fixed_build(tmp_path):
    run = build_run(
        tmp_path,
        base_kwargs={"check": "still"},
        fixed_kwargs={"check": "still", "converge": True},
    )
    assert run.code == 0
    s = run.summary
    assert s["fixed_converge_failures"] == 1
    assert s["base_converge_failures"] == 0
    assert s["differing_files"] == 0  # converge failure is independent of diff
    (row,) = run.results
    assert row["fixed_converge_fail"] is True
    assert row["base_converge_fail"] is False
    assert row["outputs_differ"] is False
    assert row["base_format_disagrees"] is None


def test_convergence_failure_flagged_for_base_build(tmp_path):
    run = build_run(
        tmp_path,
        base_kwargs={"check": "still", "converge": True},
        fixed_kwargs={"check": "still"},
    )
    assert run.code == 0
    s = run.summary
    assert s["base_converge_failures"] == 1
    assert s["fixed_converge_failures"] == 0
    (row,) = run.results
    assert row["base_converge_fail"] is True
    assert row["fixed_converge_fail"] is False


def test_formatter_disagreement_attributed_to_patched_only(tmp_path):
    run = build_run(
        tmp_path,
        base_kwargs={"check": "still"},
        fixed_kwargs={"check": "append-B", "fmt": "rewrite"},
    )
    assert run.code == 0
    s = run.summary
    assert s["differing_files"] == 1
    assert s["diffs_formatter_disagrees_only_fixed"] == 1
    assert s["diffs_formatter_disagrees_both"] == 0
    (row,) = run.results
    assert row["base_format_disagrees"] is False
    assert row["fixed_format_disagrees"] is True


def test_formatter_disagreement_in_both_builds_is_pre_existing(tmp_path):
    run = build_run(
        tmp_path,
        base_kwargs={"check": "append-A", "fmt": "rewrite"},
        fixed_kwargs={"check": "append-B", "fmt": "rewrite"},
    )
    assert run.code == 0
    s = run.summary
    assert s["differing_files"] == 1
    assert s["diffs_formatter_disagrees_both"] == 1
    assert s["diffs_formatter_disagrees_only_fixed"] == 0
    (row,) = run.results
    assert row["base_format_disagrees"] is True
    assert row["fixed_format_disagrees"] is True


def test_diff_rows_filtered_and_clean_file_flags_stay_none(tmp_path):
    run = build_run(
        tmp_path,
        base_kwargs={"check": "still"},
        fixed_kwargs={"check": "append-A", "only": "drift*"},
        files=("drift.py", "stable.py"),
    )
    assert run.code == 0
    assert run.summary["corpus_size"] == 2
    assert run.summary["differing_files"] == 1
    assert [r["path"] for r in run.results] == ["drift.py"]

    # Unit-level contract: a clean file never enters format attribution.
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    cfg = run.corpus / "ruff_difftest.toml"  # mode_run deleted it; recreate
    cfg.write_text("preview = true\n", encoding="utf-8")
    row = h.check_file(
        "stable.py", run.corpus, run.base, run.fixed, "E301", cfg, scratch
    )
    assert row.outputs_differ is False
    assert row.base_format_disagrees is None
    assert row.fixed_format_disagrees is None


def test_harness_invokes_fakes_with_exact_documented_argv(tmp_path):
    run = build_run(
        tmp_path,
        base_kwargs={"check": "append-A"},
        fixed_kwargs={"check": "append-B", "fmt": "rewrite"},
        select="E301,I001",
    )
    assert run.code == 0
    for who in ("ruff-base", "ruff-fixed"):
        lines = [
            line.split()
            for line in (tmp_path / "bin" / f"{who}.argv.log")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        # Classify by workdir: the DIFF format probe runs check+format in a
        # separate "<name>-fmt" workdir (visible in the --config path).
        main = [a for a in lines if "-fmt" not in a[-1]]
        probe_fmt = [a for a in lines if a[0] == "format"]
        checks = [a for a in main if a[0] == "check"]
        assert len(checks) == 2, lines  # fix pass 1 + idempotence pass 2
        assert checks[0] == checks[1]  # identical invocation in both passes
        assert len(checks[0]) == 8
        assert checks[0][:7] == [
            "check",
            ".",
            "--select",
            "E301,I001",
            "--fix",
            "--unsafe-fixes",
            "--config",
        ]
        assert checks[0][7].endswith(f"{who.split('-')[1]}/ruff.toml")
        # Format probe: one check --fix then one format, same config.
        assert len(probe_fmt) == 1, lines
        assert probe_fmt[0][:3] == ["format", ".", "--config"]
        assert probe_fmt[0][3].endswith("ruff.toml")
        probe_checks = [a for a in lines if a[0] == "check" and "-fmt" in a[-1]]
        assert len(probe_checks) == 1
        assert len(main) == 2  # nothing else ran in the main workdir
    # The harness-generated config (threaded via --config) is preview=true.
    captured = (tmp_path / "bin" / "ruff-base.argv.configcapture").read_text(
        encoding="utf-8"
    )
    assert captured == "preview = true\n"


def test_run_without_report_flag_writes_nothing(tmp_path, capsys):
    run = build_run(
        tmp_path,
        base_kwargs={"check": "still"},
        fixed_kwargs={"check": "append-A"},
        report=False,
    )
    assert run.code == 0
    assert not (tmp_path / "report").exists()
    out = capsys.readouterr().out
    assert "== summary ==" in out
    assert "differing files:   1" in out


def test_run_on_empty_corpus_exits_2(tmp_path, capsys):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    bindir = tmp_path / "bin"
    base = make_fake(bindir, "ruff-base")
    fixed = make_fake(bindir, "ruff-fixed")
    argv = [
        "run",
        "--corpus",
        str(corpus),
        "--base",
        str(base),
        "--fixed",
        str(fixed),
    ]
    assert h.main_with_argv(argv) == 2
    assert "no .py files under" in capsys.readouterr().err


def test_cli_rejects_missing_subcommand():
    with pytest.raises(SystemExit) as excinfo:
        h.main_with_argv([])
    assert excinfo.value.code == 2


def test_collect_respects_max_per_root(tmp_path, capsys):
    root = tmp_path / "root"
    root.mkdir()
    for name in ("e.py", "a.py", "c.py", "b.py", "d.py"):
        (root / name).write_text("x = 1\n", encoding="utf-8")
    out = tmp_path / "corpus"
    code = h.main_with_argv(
        ["collect", "--out", str(out), "--roots", str(root), "--max-per-root", "3"]
    )
    assert code == 0
    assert sorted(p.name for p in out.rglob("*.py")) == ["a.py", "b.py", "c.py"]
    assert "copied 3 files" in capsys.readouterr().out


def test_collect_multiple_roots_preserves_layout_and_skips_non_python(tmp_path, capsys):
    r1 = tmp_path / "r1"
    (r1 / "pkg").mkdir(parents=True)
    (r1 / "pkg" / "m1.py").write_text("a = 1\n", encoding="utf-8")
    (r1 / "pkg" / "m2.py").write_text("b = 2\n", encoding="utf-8")
    (r1 / "pkg" / "notes.txt").write_text("skip", encoding="utf-8")
    r2 = tmp_path / "r2"
    r2.mkdir()
    (r2 / "solo.py").write_text("c = 3\n", encoding="utf-8")
    out = tmp_path / "corpus"
    code = h.main_with_argv(
        [
            "collect",
            "--out",
            str(out),
            "--roots",
            str(r1),
            str(r2),
            "--max-per-root",
            "1",
        ]
    )
    assert code == 0
    assert (out / "pkg" / "m1.py").read_text(encoding="utf-8") == "a = 1\n"
    assert (out / "solo.py").exists()
    assert not (out / "pkg" / "m2.py").exists()  # capped at 1 per root
    assert not (out / "pkg" / "notes.txt").exists()
    assert "copied 2 files" in capsys.readouterr().out


def test_run_fans_out_across_worker_threads(tmp_path, capsys):
    run = build_run(
        tmp_path,
        base_kwargs={"check": "still"},
        fixed_kwargs={"check": "append-A"},
        files=("a.py", "b.py", "c.py"),
        jobs=4,
    )
    assert run.code == 0
    assert run.summary["corpus_size"] == 3
    assert run.summary["differing_files"] == 3
    assert run.summary["errors"] == 0
    assert "3/3 checked" in capsys.readouterr().out


MUTATIONS = {
    "nonidem": (
        "if first != second:",
        "if False:  # mutated: detection disabled",
        {"base_kwargs": {"check": "still"}, "fixed_kwargs": {"check": "counter"}},
        "fixed_non_idempotent",
    ),
    "converge": (
        "return read_target(file_copy), settled and FAILURES_HELP not in err, failure",
        "return read_target(file_copy), True, None  # mutated: detection disabled",
        {"base_kwargs": {"check": "still"}, "fixed_kwargs": {"converge": True}},
        "fixed_converge_failures",
    ),
    "diff": (
        'result.outputs_differ = snapshots["base"] != snapshots["fixed"]',
        "result.outputs_differ = False  # mutated: detection disabled",
        {"base_kwargs": {"check": "still"}, "fixed_kwargs": {"check": "append-A"}},
        "differing_files",
    ),
    "format": (
        "disagrees = unformatted != formatted",
        "disagrees = False  # mutated: detection disabled",
        {
            "base_kwargs": {"check": "append-A"},
            "fixed_kwargs": {"check": "append-B", "fmt": "rewrite"},
        },
        "diffs_formatter_disagrees_only_fixed",
    ),
}


@pytest.mark.parametrize("mutation", sorted(MUTATIONS))
def test_flag_paths_are_load_bearing(tmp_path, mutation):
    """Disable each detection in a mutated copy; its summary count must drop.

    A flag test that passes for the wrong reason is worse than no test, so
    every detection path is proven against a harness with that path removed.
    """
    old, new, scenario, key = MUTATIONS[mutation]
    source = (REPO / "ruff_difftest.py").read_text(encoding="utf-8")
    assert old in source, f"harness drifted; update mutation {mutation!r}"

    control = build_run(tmp_path / "control", **scenario)
    assert control.code == 0
    assert control.summary[key] == 1
    assert control.summary["errors"] == 0

    variant = tmp_path / f"harness_mut_{mutation}.py"
    variant.write_text(source.replace(old, new, 1), encoding="utf-8")
    module = load_harness_variant(variant, f"rdt_mut_{mutation.replace('-', '_')}")
    mutant = build_run(tmp_path / "mutant", module=module, **scenario)
    assert mutant.code == 0
    assert mutant.summary[key] == 0
    if mutation == "diff":
        assert mutant.results == []  # no DIFF -> row is no longer interesting

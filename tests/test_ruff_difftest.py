"""Tests for ruff_difftest.py.

Hermetic: every test drives the harness with fake ruff binaries built in
tmp_path (see fake_ruff.py). No real ruff, no network, fully offline.

Run:  python3 -m pytest tests/ -q
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import ruff_difftest as h
from tests.fake_ruff import (
    harness_argv,
    make_fake,
    write_case,
)


@pytest.fixture()
def fakes(tmp_path):
    """Common fake binaries and a one-file corpus."""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    return {
        "base": make_fake(bin_, "ruff_base", "clean"),
        "clean": make_fake(bin_, "ruff_clean", "clean"),
        "drift": make_fake(bin_, "ruff_drift", "drift"),
        "converge": make_fake(bin_, "ruff_converge", "clean+converge"),
        "nonidem": make_fake(bin_, "ruff_nonidem", "clean+nonidem"),
        "fmt": make_fake(bin_, "ruff_fmt", "drift+fmt"),
    }


def run_harness(corpus, base, fixed, tmp_path, report=True):
    report_dir = tmp_path / "report"
    argv = harness_argv("run", corpus, base, fixed, report_dir if report else None)
    code = h.main_with_argv(argv)
    return code, report_dir


def test_identical_builds_all_clean(tmp_path, fakes, capsys):
    corpus = write_case(tmp_path / "corpus")
    code, report = run_harness(corpus, fakes["base"], fakes["clean"], tmp_path)
    assert code == 0
    s = json.loads((report / "summary.json").read_text())
    assert s["corpus_size"] == 1
    assert s["base_converge_failures"] == 0
    assert s["fixed_converge_failures"] == 0
    assert s["differing_files"] == 0
    assert s["errors"] == 0
    # Nothing interesting -> empty results file
    assert json.loads((report / "results.json").read_text()) == []


def test_output_drift_detected_and_attributed(tmp_path, fakes):
    corpus = write_case(tmp_path / "corpus")
    code, report = run_harness(corpus, fakes["base"], fakes["drift"], tmp_path)
    assert code == 0
    s = json.loads((report / "summary.json").read_text())
    assert s["differing_files"] == 1
    assert s["diffs_formatter_disagrees_both"] == 0
    # drift is baked into check, not format: neither build's format disagrees
    rows = json.loads((report / "results.json").read_text())
    assert rows[0]["path"] == "case.py"
    assert rows[0]["outputs_differ"] is True
    assert rows[0]["base_format_disagrees"] is False
    assert rows[0]["fixed_format_disagrees"] is False


def test_convergence_failure_flagged(tmp_path, fakes):
    corpus = write_case(tmp_path / "corpus")
    code, report = run_harness(corpus, fakes["base"], fakes["converge"], tmp_path)
    assert code == 0
    s = json.loads((report / "summary.json").read_text())
    assert s["fixed_converge_failures"] == 1
    assert s["base_converge_failures"] == 0


def test_non_idempotence_flagged(tmp_path, fakes):
    corpus = write_case(tmp_path / "corpus")
    code, report = run_harness(corpus, fakes["base"], fakes["nonidem"], tmp_path)
    assert code == 0
    s = json.loads((report / "summary.json").read_text())
    assert s["fixed_non_idempotent"] == 1
    assert s["base_non_idempotent"] == 0


def test_formatter_disagreement_attribution(tmp_path, fakes):
    corpus = write_case(tmp_path / "corpus")
    # fixed both drifts on check AND disagrees on format; base only drifts on
    # check -> the format disagreement must be attributed to patched-only.
    code, report = run_harness(corpus, fakes["base"], fakes["fmt"], tmp_path)
    assert code == 0
    s = json.loads((report / "summary.json").read_text())
    assert s["differing_files"] == 1
    assert s["diffs_formatter_disagrees_only_fixed"] == 1
    assert s["diffs_formatter_disagrees_both"] == 0


def test_empty_corpus_errors(tmp_path, fakes):
    corpus = tmp_path / "empty"
    corpus.mkdir()
    argv = harness_argv("run", corpus, fakes["base"], fakes["clean"], None)
    assert h.main_with_argv(argv) == 2


def test_collect_copies_python_files(tmp_path, capsys):
    root = tmp_path / "root" / "pkg"
    root.mkdir(parents=True)
    (root / "mod.py").write_text("a=1\n", encoding="utf-8")
    (root / "notes.txt").write_text("nope", encoding="utf-8")
    out = tmp_path / "corpus"
    argv = [
        "collect",
        "--out",
        str(out),
        "--roots",
        str(tmp_path / "root"),
    ]
    assert h.main_with_argv(argv) == 0
    assert (out / "pkg" / "mod.py").exists()
    assert not (out / "pkg" / "notes.txt").exists()


def test_fake_binaries_are_hermetic(tmp_path, fakes):
    """The fake binaries themselves must converge and be idempotent on repeat runs."""
    for name in ("base", "clean"):
        work = tmp_path / f"work-{name}"
        work.mkdir()
        (work / "case.py").write_text("x=1\n", encoding="utf-8")
        for _ in range(2):
            proc = subprocess.run(
                [str(fakes[name]), "check", "."],
                cwd=work,
                capture_output=True,
                text=True,
                check=False,
            )
            assert proc.returncode == 0
    first = (tmp_path / "work-base" / "case.py").read_text()
    assert "x = 1" in first


def test_cli_help_exits_zero():
    proc = subprocess.run(
        [sys.executable, str(REPO / "ruff_difftest.py"), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "run" in proc.stdout
    assert "collect" in proc.stdout

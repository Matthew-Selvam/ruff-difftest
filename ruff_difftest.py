# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Differential test harness for two ruff binaries.

Runs `ruff check --fix --unsafe-fixes` over a corpus of Python files with two
builds (a base and a patched binary) and reports:

- CONVERGE-FAIL: builds that could not converge within ruff's fix iteration limit
- NON-IDEMPOTENT: builds whose `--fix` output changes when `--fix` runs a second time
- DIFF: files whose final fixed output differs between the two builds
- For each DIFF file, whether a `check --fix` -> `format` disagreement exists in
  the base build as well (pre-existing) or only in the patched build (potential
  regression introduced by the change under test)

Typical use — verifying a linter-rule change against ruff's own fixtures plus a
CPython stdlib checkout:

    uv run ruff_difftest.py collect --out /tmp/corpus \
        --roots crates/ruff_linter/resources/test/fixtures \
        --max-per-root 3000
    uv run ruff_difftest.py run --corpus /tmp/corpus \
        --base /tmp/ruff_base --fixed /tmp/ruff_fixed \
        --select E301,E302,E303,E304,E305,E306,I001 --report /tmp/difftest-report

Every worker starts from a fresh copy of the corpus file, so neither build's
output can contaminate the other's run.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

FIX_TIMEOUT_S = 120
FAILURES_HELP = "Failed to converge"


@dataclass
class FileResult:
    """Outcome of running both binaries over one corpus file."""

    path: str
    base_converge_fail: bool = False
    fixed_converge_fail: bool = False
    base_non_idempotent: bool = False
    fixed_non_idempotent: bool = False
    outputs_differ: bool = False
    # For DIFF files only: does check --fix -> format disagree in each build?
    base_format_disagrees: bool | None = None
    fixed_format_disagrees: bool | None = None
    error: str | None = None


@dataclass
class Report:
    corpus_size: int
    select: str
    results: list[FileResult] = field(default_factory=list)

    def summary(self) -> dict:
        diffs = [r for r in self.results if r.outputs_differ]
        return {
            "corpus_size": self.corpus_size,
            "select": self.select,
            "base_converge_failures": sum(1 for r in self.results if r.base_converge_fail),
            "fixed_converge_failures": sum(1 for r in self.results if r.fixed_converge_fail),
            "base_non_idempotent": sum(1 for r in self.results if r.base_non_idempotent),
            "fixed_non_idempotent": sum(1 for r in self.results if r.fixed_non_idempotent),
            "differing_files": len(diffs),
            "diffs_formatter_disagrees_both": sum(
                1 for r in diffs if r.base_format_disagrees and r.fixed_format_disagrees
            ),
            "diffs_formatter_disagrees_only_fixed": sum(
                1
                for r in diffs
                if r.fixed_format_disagrees and not r.base_format_disagrees
            ),
            "errors": sum(1 for r in self.results if r.error),
        }


def run_ruff(
    binary: Path, workdir: Path, select: str, config: Path
) -> tuple[int, str, str]:
    """Run `check --fix --unsafe-fixes` on workdir and return (code, out, err)."""
    proc = subprocess.run(
        [
            str(binary),
            "check",
            ".",
            "--select",
            select,
            "--fix",
            "--unsafe-fixes",
            "--config",
            str(config),
        ],
        cwd=workdir,
        capture_output=True,
        text=True,
        timeout=FIX_TIMEOUT_S,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def fix_snapshot(binary: Path, file_copy: Path, select: str, config: Path) -> tuple[str, bool]:
    """Fix file_copy in place; return (final content, converged)."""
    code, _out, err = run_ruff(binary, file_copy.parent, select, config)
    converged = FAILURES_HELP not in err
    return file_copy.read_text(encoding="utf-8", errors="replace"), converged


def format_output(binary: Path, workdir: Path, config: Path) -> str:
    """Run `ruff format` over workdir and return the formatted content."""
    proc = subprocess.run(
        [str(binary), "format", ".", "--config", str(config)],
        cwd=workdir,
        capture_output=True,
        text=True,
        timeout=FIX_TIMEOUT_S,
        check=False,
    )
    target = next(p for p in workdir.iterdir() if p.suffix == ".py")
    return target.read_text(encoding="utf-8", errors="replace")


def check_file(
    rel: str, corpus: Path, base: Path, fixed: Path, select: str, config_src: Path, scratch: Path
) -> FileResult:
    """Run the full base-vs-fixed comparison for one corpus file."""
    result = FileResult(path=rel)
    src = corpus / rel
    with tempfile.TemporaryDirectory(dir=scratch, prefix="difftest-") as tmp:
        tmpdir = Path(tmp)
        snapshots: dict[str, str] = {}
        for name, binary in (("base", base), ("fixed", fixed)):
            workdir = tmpdir / name
            workdir.mkdir()
            shutil.copy2(src, workdir / src.name)
            shutil.copy2(config_src, workdir / "ruff.toml")
            first, converged = fix_snapshot(binary, workdir / src.name, select, workdir / "ruff.toml")
            if not converged:
                if name == "base":
                    result.base_converge_fail = True
                else:
                    result.fixed_converge_fail = True
            second, _ = fix_snapshot(binary, workdir / src.name, select, workdir / "ruff.toml")
            if first != second:
                if name == "base":
                    result.base_non_idempotent = True
                else:
                    result.fixed_non_idempotent = True
            snapshots[name] = second
        result.outputs_differ = snapshots["base"] != snapshots["fixed"]
        if result.outputs_differ:
            for name, binary in (("base", base), ("fixed", fixed)):
                workdir = tmpdir / f"{name}-fmt"
                workdir.mkdir()
                shutil.copy2(src, workdir / src.name)
                shutil.copy2(config_src, workdir / "ruff.toml")
                fix_snapshot(binary, workdir / src.name, select, workdir / "ruff.toml")
                unformatted = (workdir / src.name).read_text(encoding="utf-8", errors="replace")
                formatted = format_output(binary, workdir, workdir / "ruff.toml")
                disagrees = unformatted != formatted
                if name == "base":
                    result.base_format_disagrees = disagrees
                else:
                    result.fixed_format_disagrees = disagrees
    return result


def mode_run(args: argparse.Namespace) -> int:
    corpus = args.corpus.resolve()
    files = sorted(p.relative_to(corpus).as_posix() for p in corpus.rglob("*.py"))
    if not files:
        print(f"no .py files under {corpus}", file=sys.stderr)
        return 2
    print(f"corpus: {len(files)} files; select={args.select}")

    config_src = corpus / "ruff_difftest.toml"
    config_src.write_text("preview = true\n", encoding="utf-8")

    report = Report(corpus_size=len(files), select=args.select)
    scratch_root = Path(tempfile.mkdtemp(prefix="difftest-scratch-"))
    try:
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = [
                pool.submit(
                    check_file, rel, corpus, args.base.resolve(), args.fixed.resolve(),
                    args.select, config_src, scratch_root,
                )
                for rel in files
            ]
            for i, fut in enumerate(futures, 1):
                res = fut.result()
                report.results.append(res)
                if i % 250 == 0 or i == len(files):
                    print(f"  {i}/{len(files)} checked")
    finally:
        shutil.rmtree(scratch_root, ignore_errors=True)
        config_src.unlink(missing_ok=True)

    if args.report:
        report_dir = args.report
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "summary.json").write_text(
            json.dumps(report.summary(), indent=2), encoding="utf-8"
        )
        (report_dir / "results.json").write_text(
            json.dumps(
                [r.__dict__ for r in report.results if _interesting(r)], indent=2
            ),
            encoding="utf-8",
        )
        print(f"report written to {report_dir}")

    s = report.summary()
    print(
        "\n".join(
            [
                "== summary ==",
                f"converge failures: base={s['base_converge_failures']} fixed={s['fixed_converge_failures']}",
                f"non-idempotent:    base={s['base_non_idempotent']} fixed={s['fixed_non_idempotent']}",
                f"differing files:   {s['differing_files']}",
                f"  formatter disagrees in both builds (pre-existing): {s['diffs_formatter_disagrees_both']}",
                f"  formatter disagrees only in patched (regression?): {s['diffs_formatter_disagrees_only_fixed']}",
                f"errors: {s['errors']}",
            ]
        )
    )
    return 0


def _interesting(r: FileResult) -> bool:
    return (
        r.outputs_differ
        or r.base_converge_fail
        or r.fixed_converge_fail
        or r.base_non_idempotent
        or r.fixed_non_idempotent
        or r.error is not None
    )


def mode_collect(args: argparse.Namespace) -> int:
    """Copy .py files from roots into a flat-ish corpus directory."""
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    copied = 0
    for root in args.roots:
        root = Path(root).resolve()
        found = sorted(root.rglob("*.py"))
        if args.max_per_root:
            found = found[: args.max_per_root]
        for src in found:
            rel = src.relative_to(root)
            dest = out / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            copied += 1
    print(f"copied {copied} files into {out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="mode", required=True)

    p_run = sub.add_parser("run", help="compare two ruff binaries over a corpus")
    p_run.add_argument("--corpus", type=Path, required=True)
    p_run.add_argument("--base", type=Path, required=True)
    p_run.add_argument("--fixed", type=Path, required=True)
    p_run.add_argument("--select", default="E301,E302,E303,E304,E305,E306,I001")
    p_run.add_argument("--jobs", type=int, default=8)
    p_run.add_argument("--report", type=Path, default=None)
    p_run.set_defaults(func=mode_run)

    p_col = sub.add_parser("collect", help="build a corpus directory from roots")
    p_col.add_argument("--out", type=Path, required=True)
    p_col.add_argument("--roots", nargs="+", type=Path, required=True)
    p_col.add_argument("--max-per-root", type=int, default=None)
    p_col.set_defaults(func=mode_collect)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

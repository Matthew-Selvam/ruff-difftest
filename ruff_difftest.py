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

A per-file `TimeoutExpired` or any other per-file exception is recorded in
that file's result (error field / converge flags) instead of crashing the run
and losing the whole report — a timeout is counted as a converge failure for
that build, which is the safe direction to err in.

CI usage: `--fail-on-regression` turns the run into a gate. It exits 1 only
for drift attributable to the patched build (outputs differ, and the
check --fix -> format disagreement appears only there); divergences both
builds share are pre-existing and never fail the build. Exit codes are 0 for
a clean run, 1 for a regression, and 2 for an empty corpus.

The corpus is not restricted to .py: `collect` and `run` both handle Jupyter
notebooks (.ipynb), which ruff lints and formats through the same code paths.
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
# ruff accepts an unknown rule selector with a warning and still exits 0, so a
# typo'd --select silently runs no rules at all and leaves both builds
# agreeing on unfixed input. Exit codes cannot catch that; the warning can.
UNKNOWN_SELECTOR_MARKER = "Unknown rule selector"
# Synthetic exit codes for runs that produced no usable verdict. ruff reserves
# 0 for "clean" and 1 for "lint violations found"; 2 or higher means ruff
# rejected the invocation itself (bad config, I/O).
TIMED_OUT_CODE = -1
RUFF_REJECTED_CODE = 2
# Corpus file types the harness knows how to drive. Ruff lints notebooks as
# well as modules, so a corpus containing .ipynb files is first-class here.
CORPUS_SUFFIXES = (".py", ".ipynb")


def is_corpus_file(path: Path) -> bool:
    """True if path is a file type the harness will feed to ruff."""
    return path.is_file() and path.suffix in CORPUS_SUFFIXES


def corpus_files(root: Path) -> list[Path]:
    """Every supported corpus file under root, sorted by path."""
    return sorted(p for suffix in CORPUS_SUFFIXES for p in root.rglob(f"*{suffix}"))


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
            "base_converge_failures": sum(
                1 for r in self.results if r.base_converge_fail
            ),
            "fixed_converge_failures": sum(
                1 for r in self.results if r.fixed_converge_fail
            ),
            "base_non_idempotent": sum(
                1 for r in self.results if r.base_non_idempotent
            ),
            "fixed_non_idempotent": sum(
                1 for r in self.results if r.fixed_non_idempotent
            ),
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
            "regressions": len(self.regressions()),
        }

    def regressions(self) -> list[FileResult]:
        """Drift attributable to the patched build rather than the baseline.

        A file counts only when its final outputs actually differ AND the
        check --fix -> format disagreement it shows up in the patched build is
        absent from the base build. Divergences both builds share are
        pre-existing behavior, not regressions, and are never counted.
        """
        return [
            r
            for r in self.results
            if r.outputs_differ
            and r.fixed_format_disagrees
            and not r.base_format_disagrees
        ]


def run_ruff(
    binary: Path, workdir: Path, select: str, config: Path
) -> tuple[int, str, str]:
    """Run `check --fix --unsafe-fixes` on workdir and return (code, out, err)."""
    try:
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
    except subprocess.TimeoutExpired:
        # TIMEOUT is its own sentinel, not a message that happens to lack the
        # convergence marker: fix_snapshot treats a timeout as a failed run for
        # this build rather than as evidence that the fix settled. A slow file
        # is not the same as a non-converging one, but conflating them errs
        # toward flagging rather than silently passing.
        return TIMED_OUT_CODE, "", f"TIMEOUT after {FIX_TIMEOUT_S}s"
    return proc.returncode, proc.stdout, proc.stderr


def read_target(path: Path) -> str:
    """Read a corpus file as text, whatever its extension.

    Notebooks are JSON but still text on disk, so the same tolerant read that
    serves .py files serves .ipynb files unchanged.
    """
    return path.read_text(encoding="utf-8", errors="replace")


def fix_snapshot(
    binary: Path, file_copy: Path, select: str, config: Path
) -> tuple[str, bool, str | None]:
    """Fix file_copy in place; return (final content, converged, failure).

    A run that timed out, or that ruff itself rejected (a bad selector or
    config exits non-zero without fixing anything), is not a settled fix, so it
    counts as not converged for this build. `failure` names that condition, or
    is None when the run simply settled or genuinely failed to converge.
    """
    code, _out, err = run_ruff(binary, file_copy.parent, select, config)
    if code == TIMED_OUT_CODE:
        failure = f"timed out after {FIX_TIMEOUT_S}s"
    elif code >= RUFF_REJECTED_CODE:
        first_line = next((ln for ln in err.splitlines() if ln.strip()), "ruff rejected the run")
        failure = f"ruff exited {code}: {first_line}"
    elif UNKNOWN_SELECTOR_MARKER in err:
        # ruff exits 0 here, so this is the only evidence the rules never ran.
        first_line = next(
            (ln for ln in err.splitlines() if UNKNOWN_SELECTOR_MARKER in ln), "unknown selector"
        )
        failure = f"no such rule: {first_line}"
    else:
        failure = None
    settled = failure is None
    return read_target(file_copy), settled and FAILURES_HELP not in err, failure


def format_output(binary: Path, workdir: Path, config: Path, target: Path) -> str:
    """Run `ruff format` over workdir and return the formatted content of target.

    `ruff format .` formats everything in workdir, so target must be named
    explicitly rather than discovered by globbing the directory afterwards:
    a workdir may hold files other than the one under test, and the
    configuration file the harness drops in alongside it.
    """
    try:
        subprocess.run(
            [str(binary), "format", ".", "--config", str(config)],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=FIX_TIMEOUT_S,
            check=False,
        )
    except subprocess.TimeoutExpired:
        pass
    return read_target(target)


def check_file(
    rel: str,
    corpus: Path,
    base: Path,
    fixed: Path,
    select: str,
    config_src: Path,
    scratch: Path,
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
            first, converged, failure = fix_snapshot(
                binary, workdir / src.name, select, workdir / "ruff.toml"
            )
            if failure:
                result.error = f"{name}: {failure}"
            if not converged:
                if name == "base":
                    result.base_converge_fail = True
                else:
                    result.fixed_converge_fail = True
            second, _, _ = fix_snapshot(
                binary, workdir / src.name, select, workdir / "ruff.toml"
            )
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
                probe = workdir / src.name
                shutil.copy2(src, probe)
                shutil.copy2(config_src, workdir / "ruff.toml")
                fix_snapshot(binary, probe, select, workdir / "ruff.toml")
                unformatted = read_target(probe)
                formatted = format_output(binary, workdir, workdir / "ruff.toml", probe)
                disagrees = unformatted != formatted
                if name == "base":
                    result.base_format_disagrees = disagrees
                else:
                    result.fixed_format_disagrees = disagrees
    return result


def mode_run(args: argparse.Namespace) -> int:
    corpus = args.corpus.resolve()
    files = sorted(p.relative_to(corpus).as_posix() for p in corpus_files(corpus))
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
                    check_file,
                    rel,
                    corpus,
                    args.base.resolve(),
                    args.fixed.resolve(),
                    args.select,
                    config_src,
                    scratch_root,
                )
                for rel in files
            ]
            for i, fut in enumerate(futures, 1):
                try:
                    res = fut.result()
                except Exception as exc:  # per-file failure must not kill the run
                    res = FileResult(path=files[i - 1], error=f"EXC: {exc!r}")
                report.results.append(res)
                if i % 250 == 0 or i == len(files):
                    print(f"  {i}/{len(files)} checked", flush=True)
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
    regressions = report.regressions()
    if args.fail_on_regression:
        # A run that could not produce a verdict for every file cannot certify
        # anything: a missing binary or a rejected rule selector leaves both
        # builds failing identically, which looks identical to a clean run.
        # Refuse to report success rather than pass a broken run.
        if s["errors"]:
            broken = sorted({r.path for r in report.results if r.error})
            print(
                "\n".join(
                    [
                        f"FAIL: {s['errors']} file(s) errored, so this run certifies nothing:",
                        *(f"  {p}" for p in broken[:20]),
                        *(
                            [f"  ... and {len(broken) - 20} more"]
                            if len(broken) > 20
                            else []
                        ),
                    ]
                ),
                file=sys.stderr,
            )
            return 3
        if regressions:
            print(
                "\n".join(
                    [
                        f"FAIL: {len(regressions)} regression(s) attributable to the patched build:"
                    ]
                    + [f"  {r.path}" for r in regressions]
                ),
                file=sys.stderr,
            )
            return 1
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
    """Copy supported files (.py, .ipynb) from roots into a corpus directory."""
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    copied = 0
    for root in args.roots:
        root = Path(root).resolve()
        found = corpus_files(root)
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


def main_with_argv(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="mode", required=True)

    p_run = sub.add_parser("run", help="compare two ruff binaries over a corpus")
    p_run.add_argument("--corpus", type=Path, required=True)
    p_run.add_argument("--base", type=Path, required=True)
    p_run.add_argument("--fixed", type=Path, required=True)
    p_run.add_argument("--select", default="E301,E302,E303,E304,E305,E306,I001")
    p_run.add_argument("--jobs", type=int, default=8)
    p_run.add_argument("--report", type=Path, default=None)
    p_run.add_argument(
        "--fail-on-regression",
        action="store_true",
        help=(
            "exit 1 when at least one file's drift is attributable to the "
            "patched build: outputs_differ is true AND the check --fix -> "
            "format disagreement appears only in the patched build. "
            "Divergences both builds share (pre-existing) never fail. "
            "Exit codes: 0 = no regression (or flag absent), "
            "1 = regression detected, "
            "2 = corpus contained no .py/.ipynb files."
        ),
    )
    p_run.set_defaults(func=mode_run)

    p_col = sub.add_parser("collect", help="build a corpus directory from roots")
    p_col.add_argument("--out", type=Path, required=True)
    p_col.add_argument("--roots", nargs="+", type=Path, required=True)
    p_col.add_argument("--max-per-root", type=int, default=None)
    p_col.set_defaults(func=mode_collect)

    args = parser.parse_args(argv)
    return args.func(args)


def main() -> int:
    return main_with_argv(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())

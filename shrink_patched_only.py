# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Line-level shrinker for a PATCHED_ONLY_FAIL fuzz case.

Repeatedly deletes line ranges and keeps the deletion whenever the candidate
still shows the property under test: the BASE build converges and the PATCHED
build does not. The result is the smallest reproduction of that property that
a deletion-only search can reach from the original file.

    python3 shrink_patched_only.py repro/fuzz/patched_only_001.py \\
        --out repro/fuzz/min_001.py
"""

from __future__ import annotations

import argparse
import ast
import shutil
import subprocess
import tempfile
from pathlib import Path

BASE = Path("/tmp/ruff_base")
FIXED = Path("/tmp/ruff_fixed")
CONFIG = "preview = true\n"
SELECT_FULL = "E301,E302,E303,E304,E305,E306,I001"
FAILURES_HELP = "Failed to converge"


def build_runs(binary: Path, src: str, select: str, scratch: Path) -> bool:
    """True if this build settled (no non-convergence message)."""
    workdir = Path(tempfile.mkdtemp(dir=scratch, prefix="shrink-"))
    try:
        target = workdir / "case.py"
        target.write_text(src, encoding="utf-8")
        cfg = workdir / "ruff.toml"
        cfg.write_text(CONFIG, encoding="utf-8")
        proc = subprocess.run(
            [str(binary), "check", str(target), "--select", select, "--fix",
             "--unsafe-fixes", "--no-cache", "--config", str(cfg)],
            cwd=workdir, capture_output=True, text=True, timeout=30, check=False,
        )
        return FAILURES_HELP not in proc.stderr
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def reproduces(src: str, select: str, scratch: Path) -> bool:
    """The property: base converges, patched does not, and the file parses."""
    try:
        ast.parse(src)
    except SyntaxError:
        return False
    return build_runs(BASE, src, select, scratch) and not build_runs(FIXED, src, select, scratch)


def shrink(src: str, select: str, scratch: Path) -> str:
    """Greedy line-window deletion until no single window helps."""
    assert reproduces(src, select, scratch), "input does not reproduce the property"
    lines = src.splitlines(keepends=True)
    granularity = 2
    while len(lines) > 1:
        window = max(1, len(lines) // granularity)
        removed = False
        i = 0
        while i < len(lines):
            candidate = "".join(lines[:i] + lines[i + window :])
            if reproduces(candidate, select, scratch):
                lines = lines[:i] + lines[i + window :]
                granularity = max(2, granularity - 1)
                removed = True
            else:
                i += window
        if not removed:
            if granularity >= len(lines):
                break
            granularity = min(len(lines), granularity * 2)
    return "".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("source", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--select", default=SELECT_FULL)
    args = ap.parse_args()

    scratch = Path(tempfile.mkdtemp(prefix="shrink-scratch-"))
    try:
        src = args.source.read_text(encoding="utf-8")
        if not reproduces(src, args.select, scratch):
            print(f"{args.source} does NOT reproduce with --select {args.select}", file=__import__("sys").stderr)
            return 1
        minimal = shrink(src, args.select, scratch)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(minimal, encoding="utf-8")
        print(f"{len(src.splitlines())} -> {len(minimal.splitlines())} lines  ->  {args.out}")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""Helpers to build fake ruff binaries for hermetic harness tests.

A fake binary is a small executable Python script whose behavior is baked in
at creation time (no environment variables), so the harness can run two
differently-behaving binaries in one invocation.

Modes (combine with '+'):
- clean     : idempotently rewrites `x=1` to `x = 1`, converges
- drift     : rewrites `x=1` to `x = 2` instead (output differs from clean)
- converge  : emits ruff's stderr non-convergence marker
- nonidem   : appends a line on every check run (never idempotent)
- fmt       : `format` subcommand appends a marker line (formatter disagrees)
"""

from __future__ import annotations

import stat
from pathlib import Path

FAKE_TEMPLATE = """\
#!/usr/bin/env python3
import pathlib, sys

MODES = {modes!r}

def _has(name):
    return name in MODES

args = sys.argv[1:]
if not args:
    sys.exit(2)

if args[0] == "check":
    for p in sorted(pathlib.Path(".").glob("*.py")):
        s = p.read_text()
        if _has("drift"):
            s = s.replace("x=1", "x = 2")
        else:
            s = s.replace("x=1", "x = 1")
        if _has("nonidem"):
            s = s.rstrip("\\n") + "\\n# extra\\n"
        p.write_text(s)
    if _has("converge"):
        sys.stderr.write(
            "debug error: Failed to converge after 100 iterations in "
            "`case.py` with rule codes E302\\n"
        )
    print("Found 1 error (1 fixed, 0 remaining).")
elif args[0] == "format":
    for p in sorted(pathlib.Path(".").glob("*.py")):
        s = p.read_text()
        if _has("fmt") or "# FMTDRIFT" in s:
            p.write_text(s.rstrip("\\n") + "\\n# formatted\\n")
"""


def make_fake(directory: Path, name: str, modes: str) -> Path:
    """Write an executable fake ruff binary with the given baked-in modes."""
    path = directory / name
    path.write_text(FAKE_TEMPLATE.format(modes=modes), encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def harness_argv(
    mode: str, corpus: Path, base: Path, fixed: Path, report: Path | None
) -> list[str]:
    """Build sys.argv for the harness `run` subcommand."""
    argv = [
        mode,
        "--corpus",
        str(corpus),
        "--base",
        str(base),
        "--fixed",
        str(fixed),
        "--jobs",
        "1",
    ]
    if report is not None:
        argv += ["--report", str(report)]
    return argv


def write_case(directory: Path, content: str = "x=1\n") -> Path:
    """Create a one-file corpus directory and return it."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "case.py").write_text(content, encoding="utf-8")
    return directory

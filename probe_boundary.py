# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Boundary matrix for the fuzz PATCHED_ONLY_FAIL mechanism.

Varies one dimension at a time around the minimal case

    view = 1
        # TODO: fix me
    def beta():
        beta = 1

to find which elements are load-bearing, and which rule in the full set is
what makes the patched build fight.
"""

from __future__ import annotations

import ast
import itertools
import shutil
import subprocess
import tempfile
from pathlib import Path

BASE = Path("/tmp/ruff_base")
FIXED = Path("/tmp/ruff_fixed")
CONFIG = "preview = true\n"
FAILURES_HELP = "Failed to converge"
RULES = ["E301", "E302", "E303", "E304", "E305", "E306", "I001"]


def settled(binary: Path, src: str, select: str, scratch: Path) -> bool | None:
    if not src.strip():
        return None
    try:
        ast.parse(src)
    except SyntaxError:
        return None
    workdir = Path(tempfile.mkdtemp(dir=scratch, prefix="bm-"))
    try:
        t = workdir / "case.py"
        t.write_text(src, encoding="utf-8")
        c = workdir / "ruff.toml"
        c.write_text(CONFIG, encoding="utf-8")
        p = subprocess.run(
            [str(binary), "check", str(t), "--select", select, "--fix",
             "--unsafe-fixes", "--no-cache", "--config", str(c)],
            cwd=workdir, capture_output=True, text=True, timeout=30, check=False)
        return FAILURES_HELP not in p.stderr
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def cell(src: str, select: str, scratch: Path) -> str:
    b = settled(BASE, src, select, scratch)
    f = settled(FIXED, src, select, scratch)
    if b is None or f is None:
        return "?"
    if b and not f:
        return "PATCHED-FAIL"
    if f and not b:
        return "base-fail"
    if not b and not f:
        return "both-fail"
    return "ok"


def main() -> int:
    scratch = Path(tempfile.mkdtemp(prefix="bm-scratch-"))
    full = ",".join(RULES)
    try:
        print("== A. comment indent (preceded by `view = 1`, bare def follows) ==")
        for ind in [0, 1, 2, 4, 8]:
            src = f"view = 1\n{' ' * ind}# c\ndef beta():\n    beta = 1\n"
            print(f"  indent={ind:<2} full={cell(src, full, scratch):<12} "
                  f"E302={cell(src, 'E302', scratch)}")

        print("\n== B. blank lines between comment and def ==")
        for n in [0, 1, 2, 3]:
            src = "view = 1\n    # c\n" + "\n" * n + "def beta():\n    beta = 1\n"
            print(f"  blanks={n} full={cell(src, full, scratch):<12} "
                  f"E302={cell(src, 'E302', scratch)}")

        print("\n== C. what precedes the comment ==")
        precedes = {
            "assignment": "view = 1\n",
            "import": "import os\n",
            "print": "print('a')\n",
            "def body (known case)": "def other():\n    pass\n",
            "class body": "class C:\n    pass\n",
            "if block": "if flag:\n    view = 1\n",
            "nothing (file start)": "",
        }
        for name, pre in precedes.items():
            src = pre + "    # c\ndef beta():\n    beta = 1\n"
            print(f"  {name:<22} full={cell(src, full, scratch):<12} "
                  f"E302={cell(src, 'E302', scratch)}")

        print("\n== D. construct following the comment ==")
        follows = {
            "def": "def beta():\n    beta = 1\n",
            "async def": "async def beta():\n    pass\n",
            "class": "class Beta:\n    beta = 1\n",
            "decorated def": "@deco\ndef beta():\n    beta = 1\n",
            "if": "if flag:\n    beta = 1\n",
            "plain stmt": "beta = 1\n",
        }
        for name, post in follows.items():
            src = "view = 1\n    # c\n" + post
            print(f"  {name:<22} full={cell(src, full, scratch):<12} "
                  f"E302={cell(src, 'E302', scratch)}")

        print("\n== E. number of comment lines (indent 4) ==")
        for n in [1, 2, 3]:
            src = "view = 1\n" + "".join("    # c\n" for _ in range(n)) + "def beta():\n    beta = 1\n"
            print(f"  n={n} full={cell(src, full, scratch):<12} "
                  f"E302={cell(src, 'E302', scratch)}")

        print("\n== F. which rules are load-bearing (indent 4, minimal case) ==")
        src = "view = 1\n    # c\ndef beta():\n    beta = 1\n"
        for k in range(1, len(RULES) + 1):
            bad = []
            for combo in itertools.combinations(RULES, k):
                sel = ",".join(combo)
                if cell(src, sel, scratch) == "PATCHED-FAIL":
                    bad.append(sel)
            print(f"  k={k}: {len(bad)}/{len(list(itertools.combinations(RULES, k)))} "
                  f"sets fail -> {bad[:6]}{' ...' if len(bad) > 6 else ''}")

        print("\n== G. base-build fight on the same minimal case (control) ==")
        print(f"  base  full={settled(BASE, src, full, scratch)}  "
              f"patched full={settled(FIXED, src, full, scratch)}")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
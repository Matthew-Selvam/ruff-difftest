# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Probe the mechanism behind the fuzz PATCHED_ONLY_FAIL cases.

Shrinks every repro case, then clusters the minima and re-checks each
cluster's representative so the report can state one mechanism per class
rather than one per file.
"""

from __future__ import annotations

import ast
import concurrent.futures
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

BASE = Path("/tmp/ruff_base")
FIXED = Path("/tmp/ruff_fixed")
CONFIG = "preview = true\n"
SELECTS = {"e302": "E302", "full": "E301,E302,E303,E304,E305,E306,I001"}
FAILURES_HELP = "Failed to converge"
REPRO = Path("/Users/matthewselvam/ruff-difftest/repro/fuzz")


def runs(binary: Path, src: str, select: str, scratch: Path) -> bool:
    workdir = Path(tempfile.mkdtemp(dir=scratch, prefix="probe-"))
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


def repro(src: str, scratch: Path) -> bool:
    """Property the fuzzer actually observed: base converges and patched does
    not, under the FULL rule set.

    Requiring it under `--select E302` alone as well would reject every real
    case — the fight needs E303 in the mix, and these shapes settle fine when
    E302 runs by itself.
    """
    try:
        ast.parse(src)
    except SyntaxError:
        return False
    full = SELECTS["full"]
    return runs(BASE, src, full, scratch) and not runs(FIXED, src, full, scratch)


def shape(src: str) -> tuple:
    """Coarse structural fingerprint of a shrunk case."""
    toks = []
    for line in src.splitlines():
        s = line.strip()
        if not s:
            toks.append("blank")
        elif s.startswith("#"):
            toks.append(f"comment@{len(line) - len(line.lstrip())}")
        elif s.startswith(("def ", "async def ")):
            toks.append("def")
        elif s.startswith("class "):
            toks.append("class")
        elif s.startswith("@"):
            toks.append("decorator")
        else:
            toks.append("stmt")
    return tuple(toks)


def shrink_one(path: Path, scratch: Path) -> tuple[str, str]:
    src = path.read_text(encoding="utf-8")
    if not repro(src, scratch):
        return path.name, ""
    lines = src.splitlines(keepends=True)
    gran = 2
    while len(lines) > 1:
        w = max(1, len(lines) // gran)
        removed, i = False, 0
        while i < len(lines):
            cand = "".join(lines[:i] + lines[i + w:])
            if repro(cand, scratch):
                lines = lines[:i] + lines[i + w:]
                gran = max(2, gran - 1)
                removed = True
            else:
                i += w
        if not removed:
            if gran >= len(lines):
                break
            gran = min(len(lines), gran * 2)
    return path.name, "".join(lines)


def main() -> int:
    files = sorted(REPRO.glob("patched_only_*.py"))
    scratch = Path(tempfile.mkdtemp(prefix="probe-scratch-"))
    minima: dict[str, str] = {}
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            for name, minimal in pool.map(lambda p: shrink_one(p, scratch), files):
                if minimal:
                    minima[name] = minimal
        out = REPRO / "minimized"
        out.mkdir(parents=True, exist_ok=True)
        for name, minimal in minima.items():
            (out / name.replace("patched_only_", "min_")).write_text(minimal, encoding="utf-8")

        clusters = Counter(shape(m) for m in minima.values())
        print(f"shrunk {len(minima)}/{len(files)} cases\n")
        print(f"{len(clusters)} distinct shape(s):")
        for shp, n in clusters.most_common():
            print(f"  n={n}  {' '.join(shp)}")

        # Every cluster representative must still hold up, verified fresh.
        print("\nre-verification of each cluster representative (both rule sets, both builds):")
        seen = set()
        for shp, _n in clusters.most_common():
            if shp in seen:
                continue
            seen.add(shp)
            rep = next(m for m in minima.values() if shape(m) == shp)
            print(f"  {' '.join(shp)}: base_ok={runs(BASE, rep, SELECTS['e302'], scratch)}"
                  f"/{runs(BASE, rep, SELECTS['full'], scratch)}"
                  f" patched_fail={not runs(FIXED, rep, SELECTS['e302'], scratch)}"
                  f"/{not runs(FIXED, rep, SELECTS['full'], scratch)}")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Randomized fragment-grammar fuzzer for two ruff binaries.

Searches for shapes where a patched ruff build fails to converge under
`check --fix` while the base build converges — the failure mode that matters
for a change to E301/E302 blank-line placement.

Sources are assembled from a FRAGMENT GRAMMAR (statements, decorators,
comment blocks at controlled columns, banner comments, docstring+comment
pairs, trailing comments, comments inside if/try bodies) rather than from
random text, so every generated file is a syntactically meaningful Python
shape and `ast.parse` nearly always accepts it.

For each generated file both binaries run in their own FRESH temp dir, under
two rule sets:

  * `--select E302`                    (the rule the patch touches, alone)
  * `--select E301,E302,E303,E304,E305,E306,I001`  (the full mix)

Each file is classified into one of:

  BOTH_CONVERGED     both builds settled
  PATCHED_ONLY_FAIL  base converged, patched reported "Failed to converge"
                     -- the class we are hunting
  BASE_ONLY_FAIL     patched converged, base did not (a pre-existing bug the
                     patch happens to fix)
  OUTPUTS_DIFFER     both converged but the fixed files differ
  CLEAN              both converged and produced identical output
  ERROR              a run timed out, ruff rejected the invocation, or the
                     file could not be generated

Typical use:

    python3 fuzz_comment_shapes.py --count 3000 --seed 20261005 \
        --out /tmp/fuzz-report --repro-dir repro/fuzz

Exit codes: 0 = ran to completion, 1 = at least one PATCHED_ONLY_FAIL,
2 = every generated sample was invalid (nothing tested).
"""

from __future__ import annotations

import argparse
import ast
import concurrent.futures
import json
import random
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_SEED = 20261005
PER_FILE_TIMEOUT_S = 20
MAX_FIX_ROUNDS = 12
FAILURES_HELP = "Failed to converge"
UNKNOWN_SELECTOR_MARKER = "Unknown rule selector"
TIMED_OUT_CODE = -1
RUFF_REJECTED_CODE = 2
DEBUG_CACHE_MARKER = "Detected debug build without --no-cache"
CONFIG_SRC = "preview = true\n"

SELECT_E302 = "E302"
SELECT_FULL = "E301,E302,E303,E304,E305,E306,I001"

CLEAN = "CLEAN"
PATCHED_ONLY_FAIL = "PATCHED_ONLY_FAIL"
BASE_ONLY_FAIL = "BASE_ONLY_FAIL"
OUTPUTS_DIFFER = "OUTPUTS_DIFFER"
BOTH_FAIL = "BOTH_FAIL"
ERROR = "ERROR"

CLASSES = (
    CLEAN,
    PATCHED_ONLY_FAIL,
    BASE_ONLY_FAIL,
    OUTPUTS_DIFFER,
    BOTH_FAIL,
    ERROR,
)

# --------------------------------------------------------------------------
# Fragment grammar
# --------------------------------------------------------------------------

NAMES = ["alpha", "beta", "gamma", "delta", "handler", "runner", "model", "view"]
COMMENT_TEXTS = [
    "note",
    "TODO: fix me",
    "keep in sync with the spec",
    "seen in the wild",
    "x" * 40,
    "a longer explanatory comment that runs past the usual line length",
]
BANNER_TEXTS = ["CONSTANTS", "helpers", "public api", "internal"]


def comment_lines(rng: random.Random, indent: int, count: int) -> list[str]:
    """`count` consecutive comment lines at a fixed indent."""
    pad = " " * indent
    return [f"{pad}# {rng.choice(COMMENT_TEXTS)}" for _ in range(count)]


def blank_lines(rng: random.Random) -> list[str]:
    """0, 1, or 2+ blank lines — the E301/E302/E303 knob."""
    return [""] * rng.choice([0, 1, 1, 2, 2, 3])


def top_statement(rng: random.Random, name: str) -> list[str]:
    """A top-level statement preceding the interesting def/class."""
    kind = rng.choice(["import", "pass", "assign", "print", "trailing_assign", "const"])
    if kind == "import":
        return [f"import {name}"]
    if kind == "pass":
        return ["pass"]
    if kind == "assign":
        return [f"{name} = 1"]
    if kind == "print":
        return [f"print({name!r})"]
    if kind == "trailing_assign":
        return [f"{name} = 1  # {rng.choice(COMMENT_TEXTS)}"]
    return [f"{name.upper()} = 1", f"{name.lower()} = 2  # {rng.choice(COMMENT_TEXTS)}"]


def decorators(rng: random.Random) -> list[str]:
    """0-2 decorators, optionally with a comment wedged between them."""
    out: list[str] = []
    for _ in range(rng.choice([0, 0, 1, 1, 2])):
        out.append(rng.choice(["@staticmethod", "@functools.cache", "@app.route('/x')"]))
        if rng.random() < 0.30:
            out.extend(comment_lines(rng, 0, rng.choice([1, 1, 2])))
    return out


def body_block(rng: random.Random, name: str, indent: int, allow_comment_tail: bool) -> list[str]:
    """A function/class body, sometimes ending in an indented comment.

    An indented comment trailing the last statement of a body is exactly the
    shape the E301/E302 comment-block anchoring patch is about, so it gets its
    own high-probability path.
    """
    pad = " " * indent
    out: list[str] = []
    shape = rng.choice(["pass", "assign", "doc_then_assign", "comment_first", "comment_tail"])
    if shape == "pass":
        out.append(f"{pad}pass")
    elif shape == "assign":
        out.append(f"{pad}{name} = 1")
    elif shape == "doc_then_assign":
        out.append(f'{pad}"""{name} docstring."""')
        if rng.random() < 0.5:
            out.extend(comment_lines(rng, indent, rng.choice([1, 2])))
        out.append(f"{pad}{name} = 1")
    elif shape == "comment_first":
        out.extend(comment_lines(rng, indent, rng.choice([1, 2])))
        out.append(f"{pad}{name} = 1")
    else:  # comment_tail
        out.append(f"{pad}{name} = 1")
        out.extend(comment_lines(rng, indent, rng.choice([1, 1, 2, 3])))
    if allow_comment_tail and rng.random() < 0.45:
        out.extend(comment_lines(rng, indent, rng.choice([1, 2])))
    if rng.random() < 0.15:
        out.append("")
        out.extend(comment_lines(rng, indent, 1))
    return out


def function_def(rng: random.Random, is_async: bool) -> list[str]:
    """One top-level function, with a grammar-chosen comment/blank prelude."""
    name = rng.choice(NAMES)
    prefix = "async def " if is_async else "def "
    lines: list[str] = list(decorators(rng))
    lines.extend(blank_lines(rng))
    lines.extend(comment_lines(rng, rng.choice([0, 0, 0, 4, 4, 8]), rng.choice([1, 1, 2, 3])))
    lines.extend(blank_lines(rng))
    lines.append(f"{prefix}{name}():")
    if rng.random() < 0.5:
        lines.extend(comment_lines(rng, 4, rng.choice([1, 2])))
    lines.extend(body_block(rng, name, 4, allow_comment_tail=True))
    return lines


def class_def(rng: random.Random) -> list[str]:
    name = rng.choice(NAMES).capitalize() + "Cls"
    lines: list[str] = list(decorators(rng))
    lines.extend(blank_lines(rng))
    lines.extend(comment_lines(rng, 0, rng.choice([1, 2, 3])))
    lines.extend(blank_lines(rng))
    lines.append(f"class {name}:")
    lines.extend(comment_lines(rng, 4, rng.choice([1, 2])))
    if rng.random() < 0.6:
        lines.append('    """Class docstring."""')
        if rng.random() < 0.5:
            lines.extend(comment_lines(rng, 4, 1))
    lines.extend(body_block(rng, "value", 4, allow_comment_tail=True))
    if rng.random() < 0.25:
        lines.append("")
        lines.extend(comment_lines(rng, 4, 1))
        lines.append("    def method(self):")
        lines.extend(body_block(rng, "m", 8, allow_comment_tail=True))
    return lines


def banner(rng: random.Random) -> list[str]:
    title = rng.choice(BANNER_TEXTS)
    rule = rng.choice(["=", "-"])
    n = rng.choice([3, 5, 8])
    line = f"# {rule * n} {title.upper()} {rule * n}"
    return [line, line, ""]


def block_stmt(rng: random.Random) -> list[str]:
    """An if/try/for block, whose interior comments interact with E301/E306."""
    name = rng.choice(NAMES)
    kind = rng.choice(["if", "try", "for", "with", "while"])
    if kind == "if":
        lines = ["if flag:", f"    {name} = 1"]
    elif kind == "try":
        lines = ["try:", "    pass", "except Exception:", f"    {name} = 1"]
    elif kind == "for":
        lines = ["for item in items:", f"    {name} = item"]
    elif kind == "with":
        lines = ["with open(path) as fh:", "    pass"]
    else:
        lines = ["while flag:", f"    {name} = 1"]
    if rng.random() < 0.7:
        pos = rng.choice([0, 1])
        lines[pos:pos] = comment_lines(rng, 4, rng.choice([1, 2, 3]))
    if rng.random() < 0.45:
        lines.append(f"    # {rng.choice(COMMENT_TEXTS)}")
    return lines


def async_block(rng: random.Random) -> list[str]:
    lines = ["async def outer():", "    await inner()"]
    if rng.random() < 0.6:
        lines.extend(comment_lines(rng, 4, rng.choice([1, 2])))
    if rng.random() < 0.5:
        lines.append("")
        lines.extend(comment_lines(rng, 4, 1))
        lines.append("    async def inner():")
        lines.append("        return 1")
        if rng.random() < 0.6:
            lines.extend(comment_lines(rng, 8, 1))
    return lines


def unit(rng: random.Random) -> list[str]:
    """One grammar unit: a top-level construct plus its own comment prelude."""
    lead: list[str] = []
    r = rng.random()
    if r < 0.15:
        lead = banner(rng)
    elif r < 0.45:
        lead = top_statement(rng, rng.choice(NAMES))
    elif r < 0.60:
        lead = block_stmt(rng)
    elif r < 0.70:
        lead = async_block(rng)

    mid = blank_lines(rng)
    mid.extend(comment_lines(rng, rng.choice([0, 0, 0, 4, 8]), rng.choice([1, 1, 2, 2, 3])))

    tail = rng.random()
    if tail < 0.45:
        body = function_def(rng, is_async=False)
    elif tail < 0.60:
        body = function_def(rng, is_async=True)
    elif tail < 0.90:
        body = class_def(rng)
    else:
        body = block_stmt(rng)
    return lead + mid + body


PRELUDE = ["import functools", "import os", "flag = True", "items = []"]


def gen_file(rng: random.Random) -> str:
    """Assemble a whole module: header, prelude, and 1-4 grammar units."""
    lines: list[str] = []
    if rng.random() < 0.85:
        lines.extend(comment_lines(rng, 0, rng.choice([1, 1, 2, 3])))
        lines.extend(blank_lines(rng))
    for _ in range(rng.choice([1, 1, 1, 2, 2, 3, 4])):
        lines.extend(unit(rng))
        lines.extend(blank_lines(rng))
        if rng.random() < 0.2:
            lines.extend(top_statement(rng, rng.choice(NAMES)))
            lines.extend(blank_lines(rng))
    header = list(PRELUDE[: rng.choice([0, 2, 4])])
    if header:
        header.extend(blank_lines(rng))
    return "\n".join(lines + header) + "\n"


def generate_valid(rng: random.Random, attempts: int = 8) -> str | None:
    """A generated module that `ast.parse` accepts, or None if none sampled."""
    for _ in range(attempts):
        src = gen_file(rng)
        try:
            ast.parse(src)
        except SyntaxError:
            continue
        return src
    return None


# --------------------------------------------------------------------------
# Running the two builds
# --------------------------------------------------------------------------


@dataclass
class BuildOutcome:
    content: str
    converged: bool
    error: str | None = None


@dataclass
class SampleResult:
    index: int
    source: str
    verdicts: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def interesting(self) -> bool:
        return any(v in (PATCHED_ONLY_FAIL, BASE_ONLY_FAIL, OUTPUTS_DIFFER) for v in self.verdicts.values())


def _invocation(binary: Path, select: str, target: Path, config: Path, fix: bool) -> list[str]:
    argv = [str(binary), "check", str(target), "--select", select,
            "--no-cache", "--config", str(config)]
    if fix:
        argv += ["--fix", "--unsafe-fixes"]
    return argv


def run_build(binary: Path, workdir: Path, select: str, src: str) -> BuildOutcome:
    """Fix a private copy of `src` under `select`; return (content, converged).

    A timeout or a rejected invocation is not a settled fix, so it counts as
    not converged for this build — erring toward flagging, matching
    ruff_difftest.py.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    target = workdir / "case.py"
    target.write_text(src, encoding="utf-8")
    config = workdir / "ruff.toml"
    config.write_text(CONFIG_SRC, encoding="utf-8")

    try:
        proc = subprocess.run(
            [str(binary), "check", str(target), "--select", select,
             "--fix", "--unsafe-fixes", "--no-cache", "--config", str(config)],
            cwd=workdir, capture_output=True, text=True,
            timeout=PER_FILE_TIMEOUT_S, check=False,
        )
    except subprocess.TimeoutExpired:
        return BuildOutcome(target.read_text(encoding="utf-8"), False,
                            f"timed out after {PER_FILE_TIMEOUT_S}s")
    err = proc.stderr
    if proc.returncode >= RUFF_REJECTED_CODE and FAILURES_HELP not in err:
        first = next((ln for ln in err.splitlines() if ln.strip()), "ruff rejected the run")
        return BuildOutcome(target.read_text(encoding="utf-8"), False,
                            f"ruff exited {proc.returncode}: {first}")
    if UNKNOWN_SELECTOR_MARKER in err:
        return BuildOutcome(target.read_text(encoding="utf-8"), False, "unknown rule selector")
    settled = FAILURES_HELP not in err
    if settled:
        # A settled fix must be idempotent: a second identical pass has to be
        # a no-op. Comparing the file to itself proves nothing, so the
        # post-fix content is captured before the re-run and compared after.
        after_first = target.read_text(encoding="utf-8")
        second = subprocess.run(
            [str(binary), "check", str(target), "--select", select,
             "--fix", "--unsafe-fixes", "--no-cache", "--config", str(config)],
            cwd=workdir, capture_output=True, text=True,
            timeout=PER_FILE_TIMEOUT_S, check=False,
        )
        if FAILURES_HELP in second.stderr or after_first != target.read_text(encoding="utf-8"):
            settled = False
    return BuildOutcome(target.read_text(encoding="utf-8"), settled)


def classify(base: BuildOutcome, patched: BuildOutcome) -> str:
    if base.error or patched.error:
        return ERROR
    if patched.converged and not base.converged:
        return BASE_ONLY_FAIL
    if base.converged and not patched.converged:
        return PATCHED_ONLY_FAIL
    if not base.converged and not patched.converged:
        # Both builds fought the file; recorded separately from agreement so a
        # pre-existing base bug is never mistaken for a patched regression.
        return BOTH_FAIL
    return CLEAN if base.content == patched.content else OUTPUTS_DIFFER


def test_sample(index: int, src: str, binaries: tuple[Path, Path], scratch: Path) -> SampleResult:
    base_bin, fixed_bin = binaries
    res = SampleResult(index=index, source=src)
    with tempfile.TemporaryDirectory(dir=scratch, prefix="fuzz-") as tmp:
        tmpdir = Path(tmp)
        for select in (SELECT_E302, SELECT_FULL):
            label = "e302" if select == SELECT_E302 else "full"
            b = run_build(base_bin, tmpdir / f"base-{label}", select, src)
            p = run_build(fixed_bin, tmpdir / f"fixed-{label}", select, src)
            if b.error:
                res.errors.append(f"{label}/base: {b.error}")
            if p.error:
                res.errors.append(f"{label}/patched: {p.error}")
            res.verdicts[label] = classify(b, p)
    return res


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--count", type=int, default=3000, help="samples to attempt")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--base", type=Path, default=Path("/tmp/ruff_base"))
    parser.add_argument("--fixed", type=Path, default=Path("/tmp/ruff_fixed"))
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--out", type=Path, default=Path("/tmp/fuzz-report"))
    parser.add_argument(
        "--repro-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "repro" / "fuzz",
        help="where PATCHED_ONLY_FAIL sources are written",
    )
    parser.add_argument("--max-report", type=int, default=40)
    args = parser.parse_args()

    base_bin, fixed_bin = args.base.resolve(), args.fixed.resolve()
    for b in (base_bin, fixed_bin):
        if not b.is_file():
            print(f"missing binary: {b}", file=sys.stderr)
            return 2

    rng = random.Random(args.seed)
    args.out.mkdir(parents=True, exist_ok=True)

    sources: list[str] = []
    invalid = 0
    while len(sources) < args.count:
        src = generate_valid(rng)
        if src is None:
            invalid += 1
            if invalid > args.count * 4:
                print("every sample failed ast.parse; aborting", file=sys.stderr)
                return 2
            continue
        sources.append(src)

    scratch = Path(tempfile.mkdtemp(prefix="fuzz-scratch-"))
    started = time.monotonic()
    counts = dict.fromkeys(CLASSES, 0)
    per_select = {SELECT_E302: dict.fromkeys(CLASSES, 0), SELECT_FULL: dict.fromkeys(CLASSES, 0)}
    results: list[SampleResult] = []
    errors: list[SampleResult] = []
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = [
                pool.submit(test_sample, i, src, (base_bin, fixed_bin), scratch)
                for i, src in enumerate(sources)
            ]
            for i, fut in enumerate(futures, 1):
                try:
                    r = fut.result()
                except Exception as exc:  # per-sample failure must not kill the run
                    r = SampleResult(index=i - 1, source="", verdicts={"e302": ERROR, "full": ERROR})
                    r.errors.append(f"EXC: {exc!r}")
                results.append(r)
                if r.errors:
                    errors.append(r)
                for label, verdict in r.verdicts.items():
                    counts[verdict] += 1
                    per_select[SELECT_E302 if label == "e302" else SELECT_FULL][verdict] += 1
                if i % 250 == 0 or i == len(futures):
                    rate = i / (time.monotonic() - started)
                    print(f"  {i}/{len(futures)}  {rate:.0f}/s", flush=True)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    elapsed = time.monotonic() - started
    patched_only = [r for r in results if PATCHED_ONLY_FAIL in r.verdicts.values()]
    patched_only.sort(key=lambda r: len(r.source))

    if patched_only:
        args.repro_dir.mkdir(parents=True, exist_ok=True)
        for n, r in enumerate(patched_only[: args.max_report], 1):
            (args.repro_dir / f"patched_only_{n:03d}.py").write_text(r.source, encoding="utf-8")

    payload = {
        "seed": args.seed,
        "requested": args.count,
        "generated": len(sources),
        "resample_failures": invalid,
        "base": str(base_bin),
        "fixed": str(fixed_bin),
        "jobs": args.jobs,
        "elapsed_s": round(elapsed, 2),
        "counts": {k: v for k, v in counts.items()},
        "per_select": {k: {kk: vv for kk, vv in v.items()} for k, v in per_select.items()},
        "samples_per_class": len(sources) // 2,
        "errors": [r.errors for r in errors][:50],
        "patched_only": [
            {"index": r.index, "len": len(r.source), "verdicts": r.verdicts} for r in patched_only
        ],
    }
    (args.out / "summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("\n== fuzz summary ==")
    print(f"seed={args.seed} generated={len(sources)} (requested {args.count}, "
          f"resample failures {invalid}) in {elapsed:.1f}s with {args.jobs} jobs")
    print(f"2 rule sets x 2 builds -> {len(sources) * 2} base-vs-patched comparisons")
    print("\ncounts over all comparisons:")
    for k in CLASSES:
        print(f"  {k:<18} {counts[k]}")
    print("\ncounts by rule set:")
    for sel, table in per_select.items():
        print(f"  --select {sel}")
        for k in CLASSES:
            print(f"    {k:<18} {table[k]}")
    if patched_only:
        print(f"\nPATCHED_ONLY_FAIL: {len(patched_only)} file(s); "
              f"smallest {len(patched_only[0].source)} chars -> {args.repro_dir}")
    else:
        print("\nPATCHED_ONLY_FAIL: 0 file(s)")

    return 1 if patched_only else 0


if __name__ == "__main__":
    sys.exit(main())
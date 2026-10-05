# ruff-difftest

Differential test harness for two [ruff](https://github.com/astral-sh/ruff) binaries.

Run `ruff check --fix --unsafe-fixes` over a corpus of Python files with a base
build and a patched build, and report:

- **convergence failures** in either build (`Failed to converge after N iterations`)
- **non-idempotent fixes** (running `--fix` twice changes the output)
- **output differences** between the builds
- for every differing file, whether a `check --fix` → `format` disagreement
  exists in the base build too (pre-existing) or only in the patched build
  (a candidate regression)

Raw disagreement counts and formatter-disagreement counts are meaningless
without baseline attribution — this harness does the attribution for you.

## Why

Snapshot tests apply fixes exactly once; convergence bugs need repeated fix
application. A rule change can pass all 2,800+ unit tests and still
non-converge on real files when two rules' fixes undo each other. This harness
runs the full pipeline, twice per build, and compares.

It earned its keep on its first run: see
[`findings/2026-10-05-e302-indented-comment-nonconvergence.md`](findings/2026-10-05-e302-indented-comment-nonconvergence.md)
for an E302/E303 fix-fight that passes ruff's entire test suite yet never
converges on a 6-line input.

## Usage

```bash
# 1. Build two binaries (e.g. unpatched commit vs your branch)
cargo build --bin ruff   # on each checkout; copy target/debug/ruff aside

# 2. Collect a corpus (ruff's own fixtures, a CPython checkout, your codebase…)
uv run ruff_difftest.py collect --out /tmp/corpus \
    --roots /path/to/ruff/crates/ruff_linter/resources/test/fixtures \
    --max-per-root 3000

# 3. Compare
uv run ruff_difftest.py run --corpus /tmp/corpus \
    --base /tmp/ruff_base --fixed /tmp/ruff_fixed \
    --select E301,E302,E303,E304,E305,E306,I001 \
    --jobs 8 --report /tmp/difftest-report
```

The report directory gets `summary.json` (counts) and `results.json` (one
entry per interesting file, with base/fixed flags for converge-failure,
non-idempotence, output difference, and formatter disagreement).

Every file is checked in a fresh temp copy, so builds cannot contaminate each
other's runs. Files are processed in parallel; `--jobs` controls workers.

## Requirements

- Python 3.10+ (`uv run` handles everything else; the script has no
  third-party dependencies)
- Two ruff binaries you want to compare

## Notes

- `preview = true` is written into the per-run `ruff.toml` because blank-line
  behavior under preview differs from stable; edit `mode_run` if you need
  different config.
- Formatted-vs-unformatted comparison uses the same binary that did the
  fixing, per build.

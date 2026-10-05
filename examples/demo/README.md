# Demo run — patched-vs-unpatched ruff 0.16.9 (E302 indented-comment case)

This directory holds the literal artifacts of the demo run documented in
[`docs/cookbook.md`](../../docs/cookbook.md). Every number below was captured
from real executions on 2026-10-05.

## What was run

- **Builds:** `/tmp/ruff_base` (unpatched ruff, commit `8b83731`) and
  `/tmp/ruff_fixed` (patched `blank_lines.rs` comment-block anchoring), both
  `ruff 0.16.9` debug builds.
- **Corpus:** the 74 `.py` pycodestyle fixtures from a local ruff checkout
  (`crates/ruff_linter/resources/test/fixtures/pycodestyle`).
- **Command:**
  `uv run ruff_difftest.py run --corpus /tmp/cb-corpus74 --base /tmp/ruff_base --fixed /tmp/ruff_fixed --select E301,E302,E303,E304,E305,E306,I001 --jobs 8 --report /tmp/cb-report74`

## Console output

```text
corpus: 74 files; select=E301,E302,E303,E304,E305,E306,I001
  74/74 checked
report written to /private/tmp/cb-report74
== summary ==
converge failures: base=1 fixed=1
non-idempotent:    base=0 fixed=0
differing files:   2
  formatter disagrees in both builds (pre-existing): 2
  formatter disagrees only in patched (regression?): 0
errors: 0
```

## Per-file attribution (`results.json`)

| file | converges? (base) | converges? (fixed) | outputs differ | formatter disagrees |
|---|---|---|---|---|
| `E30_comment_before_definition.py` | **fails** | passes | yes | both builds |
| `E30.py` | passes | **fails** | yes | both builds |

- `E30_comment_before_definition.py` failing on **base only** is the bug the
  patch exists to fix — intended.
- `E30.py` failing on **fixed only** is the regression: an indented trailing
  comment makes E302 anchor its insertion inside the previous function body,
  and E302/E303 undo each other until the 100-iteration limit. No unit test in
  the patched tree catches it (2,836 pass there).
- Both files land in the formatter-disagrees-in-both bucket, so the
  formatter-stage drift is pre-existing; the convergence asymmetry is the
  finding.

Full machine-readable copies: [`summary-74.json`](summary-74.json),
[`results-74.json`](results-74.json).

## The 3,655-file big run

The 74-file run was followed by a full-scale corpus (ruff test fixtures +
CPython `Lib/` checkout, 3,655 files) — see
[`findings/2026-10-05-big-run.md`](../../findings/2026-10-05-big-run.md).
Headline: `converge failures: base=5 fixed=2` — the patch fixes three more
non-convergence cases than it introduces — and all 13 output diffs are
pre-existing (formatter disagrees in both builds), so zero patched-only
regressions.

| attribution | files |
|---|---|
| converge-fail on **base only** (patch working as intended) | `pycodestyle/E30_comment_before_definition.py`, `isort/insert_empty_lines.py`, `Lib/test/_test_embed_structseq.py`, `Lib/test/test_inspect/inspect_fodder.py`, `flake8_return/RET503.py` |
| converge-fail on **fixed only** (known E302 repro shape) | `pycodestyle/E30.py`, `pyupgrade/UP028_0.py` |

Full machine-readable copies: [`summary-big-run.json`](summary-big-run.json),
[`results-big-run.json`](results-big-run.json).

## One-file harness run (same repro, `--select E302,E303`)

```text
== summary ==
converge failures: base=0 fixed=1
non-idempotent:    base=0 fixed=0
differing files:   1
  formatter disagrees in both builds (pre-existing): 0
  formatter disagrees only in patched (regression?): 1
errors: 0
```

Here the drift lands in the only-in-patched bucket: on this minimal input the
patched build is the sole source of both the convergence failure and the
fix-vs-format disagreement. [`summary-1file.json`](summary-1file.json) holds
the full JSON.

## Minimal A/B (no harness)

`repro/case_indented_comment.py` + `preview = true`,
`--select E302,E303 --no-cache --fix --unsafe-fixes`:

- **base:** `Found 2 errors (2 fixed, 0 remaining).` exit 0 — blank lines land
  between the comment and the next `def`.
- **fixed:** `debug error: Failed to converge after 100 iterations ... rule
  codes E302`, `Found 101 errors (100 fixed, 1 remaining).` exit 1.

With `--select E302` alone the fixed build converges (inserts the blank lines
inside the body); with `--select E303` alone there is nothing to fix. The
convergence fight requires both rules.

# Full-scale differential run: ruff fixtures + Python 3.13 framework stdlib (2026-10-05)

Largest run of the harness to date: **33,405 files** (~9× the previous big run),
base `8b83731` vs patched `5882a3d` (branch `fix/e302-comment-block-insertion`),
select `E301,E302,E303,E304,E305,E306,I001`, `preview = true`,
`--fix --unsafe-fixes`, two passes per build per file, `--jobs 8`.

Corpora (collected separately, per-corpus runs so partial results survive):

- `/tmp/corpus-fix` — ruff's full fixture tree
  (`crates/ruff_linter/resources/test/fixtures`), 1,609 files, 6.3 MB.
- `/tmp/corpus-stdlib` — the Python 3.13 framework install
  (`/Library/Frameworks/Python.framework/Versions/3.13/lib/python3.13`),
  31,796 files, 489 MB. Note: this includes `site-packages` (torch, scipy,
  sympy, grpc stubs, …), not just `Lib/` — hence ~32k files, not ~1.8k.

## Headline numbers

| corpus | files | runtime | conv-fail base | conv-fail fixed | non-idempotent | differing | errors |
|---|---|---|---|---|---|---|---|
| fixtures | 1,609 | 30 s | 3 | 2 | 0 / 0 | 6 | 0 |
| stdlib | 31,796 | 12 min 56 s | 9 | 8 | 0 / 0 | 41 | 0 |
| **total** | **33,405** | ~13.5 min | **12** | **10** | **0 / 0** | **47** | **0** |

Both runs exit 0, zero per-file errors, zero non-idempotence anywhere.

## Convergence attribution (every flag re-verified on fresh copies)

### Base-side failures — 12 files, ALL fixed by the patch (verified: patched run leaves 0 remaining, no convergence error)

Known E302-comment-before-definition bug (the thing the patch fixes):
`pycodestyle/E30_comment_before_definition.py`,
`isort/insert_empty_lines.py`, `flake8_return/RET503.py`,
`test/_test_embed_structseq.py`,
`site-packages/mpmath/calculus/approximation.py`,
`site-packages/mpmath/calculus/polynomials.py`,
`site-packages/reportlab/graphics/renderPS.py`,
`site-packages/sympy/functions/special/error_functions.py` (E302 ×5 of these; codes captured per file).

I001-interplay variant: `test/test_inspect/inspect_fodder.py`,
`site-packages/scipy/_external/array_api_compat/torch/linalg.py`,
`site-packages/sklearn/externals/array_api_compat/torch/linalg.py`,
`site-packages/sympy/integrals/trigonometry.py`.

### Patched-side failures — 10 files, base converges on all 10

Known (documented in `2026-10-05-e302-indented-comment-nonconvergence.md`
and the previous big run):

- `pycodestyle/E30.py` (E302) — the known indented-comment repro shape.
- `pyupgrade/UP028_0.py` (E302) — same shape, `yield`-bearing generator.

**NEW files (8) — same known bug class, never seen before this run. Flagged
loudly as requested, but classified as the known E302/E303 indented/trailing
comment oscillation, NOT a new regression class:**

- `site-packages/dill/source.py` (E302)
- `site-packages/dill/tests/test_source.py` (E302)
- `site-packages/opentelemetry/proto/collector/{logs,metrics,profiles,trace}/…_pb2_grpc.py` (E303 ×4)
- `site-packages/tensorboard/data/proto/data_provider_pb2_grpc.py` (E303)
- `site-packages/torch/testing/_internal/common_methods_invocations.py` (E302)

All 8 re-run on fresh copies: patched fails deterministically (twice in a
row), file content stable across runs, base converges cleanly. The signature
is identical to the known repro — a comment block sitting between a body and
the next top-level `def`/`class`; the patched build anchors E302's insertion
at the comment block and then fights E303, ending with the blank lines
stripped and one E30x error permanently unsatisfied. Example
(`dill/tests/test_source.py`): base keeps two blank lines between the
`# inspect.getsourcelines` comment and `def test_getsource():`; patched
removes both and oscillates.

Practical signal for the patch author: the 4 opentelemetry + 1 tensorboard
files are **generated gRPC stubs** with the `# This class is part of an
EXPERIMENTAL API.` comment before each service class — extremely common
shapes in real codebases, so the patched build will print `Failed to
converge` on them widely. The indentation-compatibility refinement already
sketched in the earlier finding would cover all 8.

## The 47 differing files

6 fixture + 41 stdlib; full list in
`/tmp/difftest-full-fix/results.json` and
`/tmp/difftest-full-stdlib/results.json`. **All 47 have
`base_format_disagrees` AND `fixed_format_disagrees` —
`diffs_formatter_disagrees_only_fixed = 0` in both corpora**, i.e. zero
patched-only formatter regressions. Spot-checked diffs on new files
(`antlr4/RuleContext.py`, `numba/np/math/numbers.py`,
`setuptools/_vendor/backports/tarfile/__init__.py`) all show the same
blank-line-placement-around-comment-blocks convention shift documented in the
previous run (base keeps two blanks before a `#---` banner; patched
normalizes to the comment-block anchoring).

## Verdict

- No new regression *class* beyond the two known ones.
- 8 new *files* hit the known patched-side E302/E303 oscillation; 5 are
  generated gRPC stubs, so real-world exposure is bigger than the fixture run
  suggested.
- Patch remains net-positive on convergence: 12 base failures → 10 patched
  failures, with all 12 base-side cases verified fixed and 10/10 patched-side
  cases traced to the single known anchoring heuristic gap.

## Artifacts

- Reports: `/tmp/difftest-full-fix/{summary,results}.json`,
  `/tmp/difftest-full-stdlib/{summary,results}.json`
- Run logs (checkpointed): `/tmp/difftest-full-fix-run1.log`,
  `/tmp/difftest-full-stdlib-run1.log`
- Hardened harness copy (per-file timeout/exception guard, semantics
  otherwise identical to repo script):
  `/tmp/ruff_difftest_hardened.py`
- Binaries: `/tmp/ruff_base` (8b83731), `/tmp/ruff_fixed` (5882a3d);
  both verified `ruff 0.16.9`; patched behavior confirmed via the standalone
  repro in `repro/case_indented_comment.py` before the run.

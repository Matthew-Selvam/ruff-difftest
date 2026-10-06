# Fuzz findings: comment/blank-line shapes, patched vs base ruff

**Date:** 2026-10-05
**Fuzzer:** `fuzz_comment_shapes.py`
**Binaries:** `/tmp/ruff_base` (ruff 0.16.9, commit 8b83731, unpatched) and
`/tmp/ruff_fixed` (ruff 0.16.9, E301/E302 comment-block anchoring patch)

## Exact command

```
python3 fuzz_comment_shapes.py --count 4000 --seed 20261005 --jobs 10 \
    --out /tmp/fuzz-report-main --repro-dir repro/fuzz
```

- **seed: 20261005**
- **generated: 4000 files** (4000 requested, 0 resample failures — every sample
  passed `ast.parse` on the first attempt)
- **8000 base-vs-patched comparisons** (4000 files x 2 rule sets)
- 103.3 s wall clock, 10 jobs, 39 files/s
- Both binaries run in a fresh temp dir per (file, rule set, build) with a
  local `ruff.toml` containing `preview = true`; `--no-cache` throughout
  (the debug builds emit `warning: Detected debug build without --no-cache`
  otherwise). A settled fix is also re-run to confirm idempotence.

## Counts per class

Totals over all 8000 comparisons:

| class | count | share |
| --- | --- | --- |
| CLEAN (both converged, identical output) | 5584 | 69.8% |
| PATCHED_ONLY_FAIL | **717** | 9.0% |
| BASE_ONLY_FAIL | 4 | 0.1% |
| OUTPUTS_DIFFER | 643 | 8.0% |
| BOTH_FAIL | 1052 | 13.2% |
| ERROR (timeout / rejected invocation) | 0 | 0% |

Split by rule set:

| class | `--select E302` | `--select E301,E302,E303,E304,E305,E306,I001` |
| --- | --- | --- |
| CLEAN | 3377 | 2207 |
| PATCHED_ONLY_FAIL | **0** | **717** |
| BASE_ONLY_FAIL | 0 | 4 |
| OUTPUTS_DIFFER | 623 | 20 |
| BOTH_FAIL | 0 | 1052 |
| ERROR | 0 | 0 |

### Headline result

The fuzzer found **717 patched-only non-convergence cases, and they reduce to a
single mechanism** — the already-known one. There is no new distinct failure
class. The value added here is scale and precision:

- **The failure requires E303 in the rule mix.** Under `--select E302` alone,
  zero of 4000 files failed in the patched build. The minimal two-rule set that
  reproduces it is exactly `E302,E303`. This refines the previously recorded
  observation ("needs E303 in the mix") into a proven minimal rule pair.
- **The base build never fails this shape** (0 of 4000 under the full set),
  confirming the failure is attributable to the patch, not pre-existing.
- **The base build does fail 4 other shapes** where the patched build converges
  (`BASE_ONLY_FAIL`) — a pre-existing bug the patch incidentally fixes, not a
  regression.

## Distinct failure classes and mechanisms

### Class 1 — PATCHED_ONLY_FAIL (717 files, 9.0%): indented comment anchoring at column > 0

All 40 saved repro files (`repro/fuzz/patched_only_*.py`) were shrink-wrapped
to a fixed point by `shrink_all_probe.py`. Every one collapsed to the same
4-line shape, differing only in the preceding statement, the comment's indent
column, and whether a `def`/`async def`/`class`/decorated-def follows.

**Minimal reproduction** — `repro/fuzz/min_fuzz_001_patched_only.py`:

```python
view = 1
    # TODO: fix me
def beta():
    beta = 1
```

Verification, base build:

```
$ /tmp/ruff_base check . --select E301,E302,E303,E304,E305,E306,I001 \
      --fix --unsafe-fixes --no-cache --config ruff.toml
Found 1 error (1 fixed, 0 remaining).
[exit=0]
```

Same file, same command, patched build:

```
$ /tmp/ruff_fixed check . --select E301,E302,E303,E304,E305,E306,I001 \
      --fix --unsafe-fixes --no-cache --config ruff.toml
debug error: Failed to converge after 100 iterations in `case.py` with rule codes E302:--:
view = 1

    # TODO: fix me
def beta():
    beta = 1
---
blank-lines-top-level: Expected 2 blank lines, found 1
 --> case.py:4:1
  |
3 |     # TODO: fix me
4 | def beta():
  | ^^^
5 |     beta = 1
  |
help: Add missing blank line(s)
  |
2 |
3 +
4 |     # TODO: fix me
  |

Found 101 errors (100 fixed, 1 remaining).
[*] 1 fixable with the `--fix` option.
[exit=1]
```

**Mechanism.** The patch anchors E301/E302 blank-line insertion at the start of
the last preceding *comment block* instead of after the last non-comment line.
The fix inserts a blank line above the indented comment:

```python
view = 1
                     <- inserted

    # TODO: fix me
def beta():
```

That satisfies E303 (too many blank lines at top level is not triggered; E302
sees 1 blank line before `def` measured *after* the comment is in place). But
the inserted blank line now sits directly above the comment, and on the next
fix iteration E303/E302 re-derive the same missing-blank-line diagnostic at
`def beta()`, since the comment is re-anchored ahead of the two required blank
lines. E302 wants 2 blank lines before the `def`; the count is taken from the
comment's line, which the fix has just pushed down by one. So each iteration
inserts a blank line and each iteration re-derives the same diagnostic: the
patched build oscillates and exhausts ruff's 100-iteration budget.

**Boundary matrix** (`probe_boundary.py`, minimal case, full rule set) — which
elements are load-bearing:

| dimension | result |
| --- | --- |
| comment at column 0 | **settles** in both builds |
| comment at column 1, 2, 4, 8 | patched fails at every nonzero indent |
| 0 blank lines between comment and construct | **patched fails** |
| >= 1 blank line between comment and construct | **settles** in both |
| preceded by assignment / `import` / `print` / `def` body / `class` body / `if` block | patched fails in all six |
| comment at file start (nothing precedes) | **settles** in both |
| followed by `def` / `async def` / `class` / decorated `def` | patched fails in all four |
| followed by `if` block or plain statement | **settles** in both |
| 1, 2, or 3 consecutive comment lines | patched fails at all three counts |

So the full precondition set is: **a comment indented at any nonzero column,
directly abutting a top-level `def`/`async def`/`class` (with zero blank lines
between), somewhere after the first line of the file.** Column 0 is safe
because the patch's anchor and the base anchor coincide there; a blank line
between comment and construct is safe because it decouples the comment from the
counted region; a comment at column > 0 that does *not* abut a top-level
construct is safe because no blank-line diagnostic is derived from it.

**Rule-set dependence** (exhaustive over all 127 non-empty subsets of
`E301,E302,E303,E304,E305,E306,I001`), scored on the minimal case:

| k | subsets that fail |
| --- | --- |
| 1 | 0/7 |
| 2 | 1/21 — `E302,E303` |
| 3 | 5/35 |
| 4 | 10/35 |
| 5 | 10/21 |
| 6 | 5/7 |
| 7 | 1/1 — the full set |

Every failing subset contains `E302,E303`. This is consistent with a
two-rule interaction: E302 supplies the blank-line insertion at the comment,
E303 supplies the counter-diagnostic that makes the next iteration re-fire.

### Class 2 — OUTPUTS_DIFFER (643 files; 623 under E302 alone, 20 under the full set)

Both builds converge, but the fixed files differ. This is the *intended* effect
of the patch: anchoring blank lines at the comment block moves them relative to
where the base build puts them, so files with indented comments before a
top-level construct come out formatted differently. Not a convergence bug; the
difference is the behavioral delta the patch introduces. Worth noting that
**623 of the 643 divergences occur under `--select E302` alone**, i.e. they are
attributable to the E302 anchoring change itself and not to any interaction with
the other rules.

### Class 3 — BOTH_FAIL (1052 files, 13.2%, full rule set only)

Both builds fail to converge on heavily comment-saturated shapes. Example:

```python
# keep in sync with the spec
# xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# keep in sync with the spec



        # seen in the wild
        # xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        # keep in sync with the spec



# keep in sync with the spec
class BetaCls:
    # a longer explanatory comment that runs past the usual line length
    """Class docstring."""
    # keep in sync with the spec
    pass
```

Pre-existing in both builds, so not attributable to the patch — but note that
these shapes are *masking* the Class 1 signal: an unparseable-to-the-fuzzer or
already-fighting file is recorded as BOTH_FAIL and is not counted as a
patched-only regression. That is the conservative direction, consistent with
`ruff_difftest.py`'s "err toward flagging, never silently pass" policy, but it
means Class 1's true rate over real-world code is somewhat higher than 717/4000.

### Class 4 — BASE_ONLY_FAIL (4 files, 0.1%, full rule set only)

Example (397 chars):

```python
# keep in sync with the spec

import handler


# seen in the wild
# TODO: fix me
# TODO: fix me

# a longer explanatory comment that runs past the usual line length
# a longer explanatory comment that runs past the usual line length
async def runner():
    # TODO: fix me
    """runner docstring."""
    runner = 1
```

The patched build converges where the base build does not — a pre-existing base
bug the anchoring change incidentally fixes. 4/4000 is a low but real rate.

## Artifacts

- `fuzz_comment_shapes.py` — the fuzzer (fragment grammar, `ast.parse`
  validation, fresh temp dir per run, two rule sets, 7-way classification,
  ThreadPoolExecutor, `--seed`, `--no-cache`)
- `shrink_patched_only.py` — single-case line-window shrinker
- `shrink_all_probe.py` — shrinks all repro cases, clusters the minima by
  structural fingerprint, re-verifies each cluster representative
- `probe_boundary.py` — the boundary matrix and the exhaustive 127-subset rule
  sweep in Class 1 above
- `repro/fuzz/patched_only_001.py` … `patched_only_040.py` — 40 raw fuzz hits
  (smallest first)
- `repro/fuzz/minimized/min_001.py` … `min_040.py` — all 40 shrink-wrapped;
  9 distinct fingerprints, all Class 1
- `repro/fuzz/min_fuzz_001_patched_only.py` — the canonical 4-line minimal case
- `/tmp/fuzz-report-main/summary.json` — machine-readable run record

## Caveats

- Counts are per (file, rule set) comparison, not per file: 4000 files x 2 = 8000.
- The fuzzer generates fragments, not real code, so absolute rates do not
  transfer to a real corpus. The mechanism conclusions do.
- `BOTH_FAIL` shapes hide Class 1 rather than revealing it; a differential
  harness that only reports patched-only *failures* will undercount this bug.
- No build was made and nothing in `/Users/matthewselvam/ruff-work`,
  `ruff_difftest.py`, or `tests/` was touched. No commit, no push.
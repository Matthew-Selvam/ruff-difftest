# Rule-set sweep: pycodestyle / flake8_bugbear / isort fixtures (2026-10-05)

Vary the **rule set** instead of the corpus. Same two binaries as the original
find — `/tmp/ruff_base` = unpatched ruff 0.16.9 (`8b83731`), `/tmp/ruff_fixed` =
patched (`fix/e302-comment-block-insertion`). Same harness,
`ruff_difftest.py run`, `preview = true` in the per-run `ruff.toml`, 2 fix passes
per build per file, fresh temp copy per build.

Corpus roots come straight from ruff's own tree (read-only, not modified):

```bash
F=/Users/matthewselvam/ruff-work/crates/ruff_linter/resources/test/fixtures
uv run ruff_difftest.py collect --out /tmp/c_pycode  --roots $F/pycodestyle
uv run ruff_difftest.py collect --out /tmp/c_bugbear --roots $F/flake8_bugbear
uv run ruff_difftest.py collect --out /tmp/c_isort   --roots $F/isort
```

Note on counts: the collect step also picks up `.ipynb` fixtures, so the
corpora are 82 / 57 / 119 files, not 74 / 55 / 119 `.py`. The original 74-file
`/tmp/corpus` baseline is untouched and was not used concurrently.

## Headline

**Two new patched-only non-convergence shapes, and the minimal rule set is
`E302,E303`** — the original write-up could only trigger it with the full
7-rule select. E303 is the *only* partner rule; `E301`, `E306` and `I001` are
all innocent (confirmed on minimized repros, table below).

Both new shapes come from `fixtures/pycodestyle/E30.py` and are **newly visible
because the comment is adjacent to `pass`** (no blank line), not separated from
it. The previously documented repro requires the separating blank line.

## Results table

Converge fails = `debug error: Failed to converge after 100 iterations`.

| rule set | corpus dir | files | base fail | fixed fail | differing files | errors |
|---|---|---|---|---|---|---|
| `E302` | pycodestyle | 82 | 0 | 0 | 2 (both pre-existing fmt) | 0 |
| `E301,E302` | pycodestyle | 82 | 0 | 0 | 2 (both pre-existing fmt) | 0 |
| **`E302,E303`** | **pycodestyle** | **82** | **0** | **1** | 2 (both pre-existing fmt) | 0 |
| `E302,E306` | pycodestyle | 82 | 0 | 0 | 2 (both pre-existing fmt) | 0 |
| `E302,I001` | pycodestyle | 82 | **1** | 0 | 2 (both pre-existing fmt) | 0 |
| `E301,E302,E303,E304,E305,E306,I001` | pycodestyle | 82 | 1 | 1 | 2 (both pre-existing fmt) | 0 |
| `E302` | flake8_bugbear | 57 | 0 | 0 | 0 | 0 |
| `E301,E302` | flake8_bugbear | 57 | 0 | 0 | 0 | 0 |
| `E302,E303` | flake8_bugbear | 57 | 0 | 0 | 0 | 0 |
| `E302,E306` | flake8_bugbear | 57 | 0 | 0 | 0 | 0 |
| `E302,I001` | flake8_bugbear | 57 | 0 | 0 | 0 | 0 |
| full 7 | flake8_bugbear | 57 | 0 | 0 | 0 | 0 |
| `E302` | isort | 119 | 0 | 0 | 1 (pre-existing fmt) | 0 |
| `E301,E302` | isort | 119 | 0 | 0 | 1 (pre-existing fmt) | 0 |
| `E302,E303` | isort | 119 | 0 | 0 | 1 (pre-existing fmt) | 0 |
| `E302,E306` | isort | 119 | 0 | 0 | 1 (pre-existing fmt) | 0 |
| **`E302,I001`** | **isort** | **119** | **1** | 0 | 1 (pre-existing fmt) | 0 |
| full 7 | isort | 119 | **1** | 0 | 1 (pre-existing fmt) | 0 |

18 harness runs. Zero errors anywhere — no run is uncertified.
No `formatter disagrees only in patched` (regression?) hits in any run.

## Attribution of every divergence

Diverging files are only 3 across 258 files: `E30.py`,
`E30_comment_before_definition.py` (pycodestyle) and `insert_empty_lines.py`
(isort).

### 1. `E302,E303` × pycodestyle `E30.py` — **(ii) patched-only failure. REGRESSION.**

Minimized to 5 lines, no leading `# E302` marker needed:

`repro/ruleset/case_e302_e303_adjacent_body_comment.py`

```python
def test_update():
    pass
    # comment
def test_clientmodel():
    pass
```

Real CLI output, `preview = true`, `--select E302,E303 --fix --unsafe-fixes`:

**Unpatched `8b83731`** — converges, pass 2 is clean:

```
Found 1 error (1 fixed, 0 remaining).
```

```python
def test_update():
    pass
    # comment


def test_clientmodel():
    pass
```

**Patched `fix/e302`** — never converges:

```
Found 101 errors (100 fixed, 1 remaining).
debug error: Failed to converge after 100 iterations in `case.py` with rule codes E302
```

```python
def test_update():
    pass

    # comment
def test_clientmodel():
    pass
```

101 errors = 1 real E302 × 100 internal fix iterations + the leftover. The
inserted blank lines land inside `test_update`'s body (before the comment, since
the comment is adjacent to `pass` and so is part of the same trailing comment
block), E303 then deletes them, E302 re-adds them. Identical mechanism to the
known repro, different trigger.

### 2. Same file, deeper-indented comment — **(ii) patched-only failure. REGRESSION.**

`repro/ruleset/case_e302_e303_deeper_indent_comment.py` (comment indented 8,
i.e. *past* the body level):

```python
def test_update():
    pass
        # comment
def test_clientmodel():
    pass
```

Identical verdicts: base `Found 1 error (1 fixed, 0 remaining)` then clean;
patched `Found 101 errors (100 fixed, 1 remaining)` +
`Failed to converge after 100 iterations`, final content with the blank lines
inside the body. So the refinement suggested in the original write-up
("only use `comment_block_start` when the comment's indentation is compatible
with the logical line that follows") does **not** fix this shape — the deeper
indentation case is still wrong.

### 3. Minimal-rule-set matrix on both minimized repros

| select | base | patched | note |
|---|---|---|---|
| `E302` | ok | ok | **and outputs differ** — the patch's intended change |
| `E303` | ok | ok, identical output | E303 alone is a no-op |
| `E302,E303` | ok | **FAIL** | minimal failing pair |
| `E301,E302,E303` | ok | **FAIL** | E301 not required |
| `E301,E302,E303,E304,E305,E306` | ok | **FAIL** | |

**E303 is the only partner rule.** `E301`/`E304`/`E305`/`E306`/`I001` are not
required for the fight. This refines the original write-up, which needed the
full 7-rule select.

The previously documented repro (`repro/case_indented_comment.py`, comment
*separated* by a blank line) was re-checked and behaves the same:
`E302` alone converges both builds; `E302,E303` and the full select fail on
patched only. So the two shapes are genuinely different triggers of the same
underlying bug.

### 4. `E30.py` and `E30_comment_before_definition.py` at every other select — **(iii) intended behavior change / (i) base-only failure**

Both files differ in output at every select in both builds — that is the
patch working as designed, not new information:

- `E30_comment_before_definition.py` at `E302,I001`: base fails to converge
  (`Found 102 errors (101 fixed, 1 remaining)` + `Failed to converge`), patched
  `Found 2 errors (2 fixed, 0 remaining)` then clean. **(i) the bug the patch
  fixes** — the branch's own regression fixture, same as the original find.
- `E30.py` at `E302`: base `Found 14 errors (14 fixed, 0 remaining)` then clean;
  patched same counts and clean, but the fix lands differently:

```diff
 def test_update():
     pass
+
+
     # comment
-
-
 def test_clientmodel():
```

  The two blank lines move from *after* the comment block to *before* it —
  exactly the anchoring change the patch introduces. **(iii) intended.**

- Both files: `base_format_disagrees` and `fixed_format_disagrees` are both
  true in every run. **(iv) pre-existing noise** — the fixed output isn't
  formatter-stable in either build, unrelated to the patch.

### 5. isort `insert_empty_lines.py` at `E302,I001` — **(i) base-only failure**

Base: `blank-lines-top-level: Expected 2 blank lines, found 1` at line 74,
never satisfied, `base_converge_fail`. Patched: `Found 8 errors (8 fixed, 0
remaining)`, clean on pass 2. This is a genuine instance of the class of bug
the patch exists to fix, found independently in ruff's own isort fixtures
(base-only, so no regression). Diff:

```diff
 # Comment goes here.
 
+
 # And another.
 def f():
     pass
```

This one shows up at `E302,I001` and the full 7, but **not** at `E302` alone —
so it needs a partner rule for base to fail to converge, a different mechanism
from the patched-only shapes.

## Summary of new findings

1. **`E302,E303` is the minimal failing rule set** — narrower than the full
   7-rule select the original find used. E303 is the only partner.
2. **Two new patched-only non-convergence shapes**, both 5 lines, both in
   `fixtures/pycodestyle/E30.py`: a comment *adjacent* to the body's last
   statement at body indentation, and the same with deeper indentation. Both
   newly minimize to fewer lines than the known repro in one respect (no
   separating blank line) and to a 2-rule select in the other.
3. The "indentation compatibility" refinement proposed in the original write-up
   would **not** have caught the deeper-indented case.
4. **`isort/insert_empty_lines.py` is a second independent base-only
   non-convergence**, fixed by the patch, requiring a partner rule to manifest.

Nothing committed or pushed. `ruff-work` untouched (read-only), `ruff_difftest.py`
and `tests/` unmodified.

## Files added

- `findings/2026-10-05-ruleset-sweep.md` (this file)
- `repro/ruleset/case_e302_e303_adjacent_body_comment.py`
- `repro/ruleset/case_e302_e303_deeper_indent_comment.py`
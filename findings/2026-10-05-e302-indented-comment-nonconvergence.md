# Found: E302 non-convergence on indented trailing comments (2026-10-05)

Discovered by running `ruff_difftest.py` over ruff's own pycodestyle fixtures
(74 files, `--select E301,E302,E303,E304,E305,E306,I001 --fix --unsafe-fixes`),
comparing unpatched ruff `8b83731` against a patched build carrying
`blank_lines.rs` comment-block anchoring (branch `fix/e302-comment-block-insertion`).

The fixture suite's snapshot tests apply fixes exactly once, and the new
convergence regression test only covers the `import -> comment -> def` shape.
This shape — an *indented* comment trailing a function body — slips through
both, and the patched build fails to converge on it while unpatched converges
in one pass.

(Corpus provenance: the 74-file corpus is 73 upstream pycodestyle fixtures
plus `E30_comment_before_definition.py`, which the branch itself adds — it is
not an upstream fixture, so the base build's converge-failure on it is the
patch's own regression test failing on unpatched code, exactly as designed.)

## Minimal repro

`repro/case_indented_comment.py`:

```python
def test_update():
    pass

    # comment
def test_clientmodel():
    pass
```

With `preview = true` and `--select E301,E302,E303,E304,E305,E306,I001 --fix --unsafe-fixes`:

**Unpatched (8b83731)** — converges in one pass:

```python
def test_update():
    pass

    # comment


def test_clientmodel():
    pass
```

The two blank lines land between the comment and `def test_clientmodel`, which
satisfies E302 without disturbing anything else. The indented comment stays
with the body it is written in.

**Patched (5882a3d)** — `debug error: Failed to converge after 100 iterations
in case.py with rule codes E302`, 101 errors reported, 1 remaining after 100
internal fix rounds:

```python
def test_update():
    pass


    # comment
def test_clientmodel():
    pass
```

E302 anchors its insertion at the start of the comment block, placing the two
blank lines *inside* `test_update`'s body. E303 then flags too many blank
lines there and removes them, E302 re-inserts them, and the two rules undo
each other until the iteration limit. The file content is stable across CLI
invocations (the internal loop lands in the same place every time), but E302
is never actually satisfied.

Same file with `--select E302` only: converges immediately. The fight needs
E303 in the picture. The same pattern appears twice in ruff's own
`E30.py` fixture (lines ~959 and ~969), where the full-select run leaves
2 E302 errors permanently unsatisfied.

## Why the anchoring heuristic misses this

`comment_block_start` tracks the last comment group preceding the logical
line, with no awareness of the comment's indentation. When the comment is
indented to the *previous* function's body level, it reads as a trailing
comment of that body — pycodestyle's behavior (and the unpatched binary) keeps
it there. Anchoring unconditionally at the comment start moves the insertion
into the previous body whenever a blank line separates `pass` from the
comment.

A candidate refinement (untested): only use `comment_block_start` when the
comment's indentation is compatible with the logical line that follows it,
or when the preceding line is not part of an indented suite. That is a design
call for the patch's author and upstream reviewers, not something this harness
decides.

## Harness output for the full 74-file run

```
converge failures: base=1 fixed=1
non-idempotent:    base=0 fixed=0
differing files:   2
  formatter disagrees in both builds (pre-existing): 2
  formatter disagrees only in patched (regression?): 0
errors: 0
```

- `E30_comment_before_definition.py`: converge-fail on **base** only — the bug
  the patch fixes, as intended.
- `E30.py`: converge-fail on **patched** only — the regression described here,
  caught by no unit test in the patched tree (2836 tests pass there).

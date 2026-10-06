# E302 comment-anchor: an indentation guard that actually closes the regression

Supersedes `e302-refinement-proposal.patch`. That proposal is a real improvement
over the unpatched branch, but it **does not close the regression** — it misses the
mixed-indentation case below. This document records why, and proposes the variant
that does.

All results here were produced with three debug builds of `ruff 0.16.9`:

| binary | source |
|---|---|
| `base` | `8b83731` (unpatched `main`) |
| `patched` | `5882a3d` (the branch as it stands: unconditional comment-block anchoring) |
| `refined` | `5882a3d` + `e302-refinement-proposal.patch` |
| `fixed2` | `5882a3d` + the guard in `e302-comment-anchor-indent-guard.patch` |

## The bug being fixed

`E302` wants two blank lines before a top-level definition. Anchoring the insertion at
the end of the last *non-comment* line puts them above the comment block, so `I001`
moves them back, `E302` re-inserts them, and the two rules never converge. Anchoring at
the start of the last comment group fixes that.

The regression: that anchoring is unconditional. When the comment block is written
*inside the preceding suite* — a trailing comment in the previous function's body — the
insertion lands inside that body. `E303` then deletes the blank lines as "too many" and
`E302` puts them back, forever:

```
error: Failed to converge after 100 iterations
```

## What the earlier proposal gets right, and where it stops

`e302-refinement-proposal.patch` records the indentation of the comment group and only
anchors at the block when that indentation equals the indentation of the definition
that follows. That is the right shape of fix, and it removes the common case.

It tracks the **last** comment's indentation, though. A comment group whose comments are
not all at the same column therefore reports the last column, not the column the block
*starts* at — and the start is the offset being used:

```python
async def outer():
    await inner()
    # TODO: fix me          <- indented, first comment of the group
# keep in sync with the spec  <- column 0, last comment of the group
def view():
    pass
```

Here the group's first comment is indented (it reads as trailing content of `outer`'s
body) while its last is at column 0. Keying off the last comment makes the block look
column-0-compatible, so the fix anchors at the indented first comment and reproduces the
regression.

Measured, `--select E302,E303`, `preview = true`:

| case | base | patched | refined | fixed2 |
|---|---|---|---|---|
| blank line + indented comment (original repro) | converges | **NON-CONV** | converges | converges |
| adjacent indented comment, no blank line | converges | **NON-CONV** | converges | converges |
| deeper-indented comment | converges | **NON-CONV** | converges | converges |
| mixed-indent group above | converges | **NON-CONV** | **NON-CONV** | converges |
| indented comment then column-0 comment | converges | **NON-CONV** | **NON-CONV** | converges |
| all comments column 0 | converges | converges | converges | converges |
| **original bug** (`import` → comment → `def`) | **NON-CONV** | converges | converges | converges |

Over the 44 minimized repros collected by the rule-set sweep and the fuzzer:

| build | non-converging |
|---|---|
| `patched` | **44 / 44** |
| `refined` | **1 / 44** (the mixed-indent group above) |
| `fixed2` | **0 / 44** |

## The fix

Keep the guard condition; key it off the **first** comment of the group instead of the
last, so the indentation compared against the following definition's is the indentation
the insertion offset actually sits at.

```rust
state.comment_block = match state.comment_block {
    // A comment on the line right after another comment continues the same
    // group, so it keeps the group's original start and indentation. Only a
    // comment preceded by a blank line begins a new group.
    Some(block) if logical_line.blank_lines == 0 => Some(block),
    _ => Some((comment_start, logical_line.indent_length)),
};
```

and

```rust
fn blank_line_insertion_offset(&self, following_indent_length: usize) -> TextSize {
    match self.comment_block {
        Some((start, first_comment_indent))
            if first_comment_indent == following_indent_length =>
        {
            start
        }
        _ => self.last_non_comment_line_end,
    }
}
```

Full patch (rule + the one snapshot whose expectations this intentionally changes):
[`e302-comment-anchor-indent-guard.patch`](e302-comment-anchor-indent-guard.patch).

## Verification

- `cargo test -p ruff_linter` → **2836 passed, 0 failed**, 4 ignored.
- `cargo clippy -p ruff_linter --all-targets --all-features -- -D warnings` → clean.
- `cargo fmt -p ruff_linter -- --check` → clean.
- One snapshot changes, `blank-lines-top-level_E30.py`, in the two indented-comment
  cases: the insertion now anchors after `pass`, so the blank lines land between the
  comment and the `def` instead of inside the body. That is the intended behavior
  change and matches the unpatched build on those inputs.
- Differential runs, base vs `fixed2`:

| corpus | rule set | base converge fails | patched converge fails | regressions |
|---|---|---|---|---|
| pycodestyle fixtures (82 files) | `E302,E303` | 0 | **0** | 0 |
| pycodestyle fixtures (82 files) | full 7 | 1 | **0** | 0 |
| isort fixtures (119 files) | full 7 | 1 | **0** | 0 |

The remaining `base` failure is the non-convergence this patch set exists to remove.

## Note for whoever writes the PR body

This is a behavior change to a stable rule's fixer, guarded by indentation, and the
guard's boundary is worth stating plainly: a comment block counts as documenting the
following definition only when the block's **first** line sits at the same indentation
as that definition. That is a judgement call about what a trailing comment means, and
reviewers should be able to disagree with it on the merits.

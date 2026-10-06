# Differential run: CPython 3.13 stdlib (2026-10-05)

Base `8b83731` vs patched E301/E302 comment-anchor build, both `ruff 0.16.9`.
Select `E301,E302,E303,E304,E305,E306,I001`, `preview = true`, `--fix --unsafe-fixes`,
two `--fix` passes per build per file, `--jobs 8`.

## Scope covered — read this first

**1,762 files — the complete CPython 3.13 stdlib as shipped by the framework
install.** No subdirectory of the stdlib was skipped and no partial run is being
reported as the whole thing. Every `.py` file under
`/Library/Frameworks/Python.framework/Versions/3.13/lib/python3.13` is included.

Two corrections to the run's stated premise, both of which change what the
numbers mean:

1. **The stdlib path in the task brief does not exist.** There is no
   `Python3.framework` under `Library/Developer/CommandLineTools/Library/Frameworks/`.
   The live 3.13 install is at
   `/Library/Frameworks/Python.framework/Versions/3.13/lib/python3.13`.
   Used instead.
2. **The stdlib is 1,762 files, not 4,000–5,000.** The install directory holds
   31,796 `.py` files in total, but 30,034 of them (94%) are third-party
   `site-packages` (torch, scipy, sympy, litellm, transformers…), not CPython.
   Those were excluded, because they are not the standard library. So this run is
   a *complete* stdlib run at 1,762 files, and deliberately does not re-cover the
   site-packages tree that the earlier
   [`2026-10-05-full-fixtures-stdlib.md`](2026-10-05-full-fixtures-stdlib.md)
   run already covered under its "stdlib" label.

The 1,762 files break down as:

| count | what |
|---|---|
| 153 | top-level stdlib modules (`string.py`, `tarfile.py`, `logging/__init__.py`, …) |
| 1064 | `test/` (the CPython regression suite — the richest source of E30x material) |
| 125 | `idlelib/` |
| 122 | `encodings/` |
| 33 | `asyncio/` |
| 29 | `email/` |
| 25 each | `_pyrepl/`, `importlib/` |
| 186 | all other stdlib packages (`multiprocessing`, `xml`, `turtledemo`, `unittest`, `tkinter`, `ctypes`, `wsgiref`, `urllib`, `curses`, `json`, `http`, `concurrent`, `dbm`, `re`, `zoneinfo`, `tomllib`, `zipfile`, `sqlite3`, `pathlib`, `html`, `ensurepip`, `xmlrpc`, `pydoc_data`, `sysconfig`, `venv`, …) |

Edge cases present in the corpus and handled without harness error (both builds
process them identically, none produce drift): 17 zero-byte `.py` files
(`__init__.py` stubs, `test/test_import/data/…`) and 3 non-UTF-8 files
(`test/encoded_modules/module_iso_8859_1.py`, `module_koi8_r.py`,
`test/tokenizedata/badsyntax_pep3120.py`). `errors: 0` — no per-file exception
or timeout anywhere.

## Exact commands used

```bash
# 1. Locate the real stdlib and enumerate every .py file
STD=/Library/Frameworks/Python.framework/Versions/3.13/lib/python3.13
find "$STD" -name '*.py' -type f > /tmp/stdlib_all.txt      # 31,796 total

# 2. Stage stdlib-only as symlinks (harness `collect` has no --exclude,
#    so site-packages is filtered out by staging, not by copying)
python3 /tmp/stage_stdlib.py                               # 1,762 staged, 30,034 skipped

# 3. Build the corpus with the harness's own collect subcommand
cd /Users/matthewselvam/ruff-difftest
uv run ruff_difftest.py collect --out /tmp/corpus-stdlib --roots /tmp/stdlib-stage
#   -> copied 1762 files into /private/tmp/corpus-stdlib        (36 MB)

# 4. The run
uv run ruff_difftest.py run --corpus /tmp/corpus-stdlib \
    --base /tmp/ruff_base --fixed /tmp/ruff_fixed \
    --select E301,E302,E303,E304,E305,E306,I001 \
    --jobs 8 --report /tmp/stddlib-report

# 5. Determinism re-run (second independent pass)
uv run ruff_difftest.py run --corpus /tmp/corpus-stdlib \
    --base /tmp/ruff_base --fixed /tmp/ruff_fixed \
    --select E301,E302,E303,E304,E305,E306,I001 \
    --jobs 8 --report /tmp/stddlib-report2

# 6. Positive control (proves the instrument detects a patched-side regression)
uv run ruff_difftest.py run --corpus /tmp/ctrl-corpus \
    --base /tmp/ruff_base --fixed /tmp/ruff_fixed \
    --select E301,E302,E303,E304,E305,E306,I001 \
    --jobs 2 --report /tmp/ctrl-report
```

Binaries were used as-is; neither was rebuilt. Both report `ruff 0.16.9`.

## Literal summary block

```
corpus: 1762 files; select=E301,E302,E303,E304,E305,E306,I001
  1762/1762 checked
report written to /tmp/stddlib-report
== summary ==
converge failures: base=2 fixed=0
non-idempotent:    base=0 fixed=0
differing files:   7
  formatter disagrees in both builds (pre-existing): 7
  formatter disagrees only in patched (regression?): 0
errors: 0
```

Wall clock 53 s (`--jobs 8`). A second full run produced a byte-identical
`summary.json` and `results.json`.

Note the asymmetry the README warns about, pointing the *other* way here: the
counts are **not** symmetric. `base=2 fixed=0` means the patch removed both
stdlib convergence failures and introduced none.

## Breakdown of the 7 differing files

| file | base converge | patched converge | attributed to |
|---|---|---|---|
| `test/_test_embed_structseq.py` | **FAIL (E302, 100 iters)** | clean | base bug, fixed by patch |
| `test/test_inspect/inspect_fodder.py` | **FAIL (I001, 100 iters)** | clean | base bug, fixed by patch |
| `logging/__init__.py` | clean | clean | pre-existing convention drift |
| `string.py` | clean | clean | pre-existing convention drift |
| `tarfile.py` | clean | clean | pre-existing convention drift |
| `test/test_gc.py` | clean | clean | pre-existing convention drift |
| `test/test_smtplib.py` | clean | clean | pre-existing convention drift |

Both convergence failures hit ruff's 100-iteration ceiling and were re-verified
independently of the harness (re-ran both binaries twice on fresh copies):
`test/_test_embed_structseq.py` fails in base on **E302** only,
`test/test_inspect/inspect_fodder.py` fails in base on **I001** only. Both are
clean in the patched build. Deterministic in both passes; no timeouts.

## Pre-existing (base behavior — not caused by the patch)

**The 5 clean-in-both drift files.** All five converge in both builds and all
five show `base_format_disagrees = true`, so `check --fix` → `format` already
disagreed before the patch. All five are the same single shape: a blank line
moved across the top of a comment block. Base leaves the blank line *after* the
comment block; patched places it *before*. Examples, base's post-fix output:

- `string.py:35` — blank line after `printable = digits + …`, before
  `# Functions which aren't available as string methods.`
- `tarfile.py:632` — blank line after `self.fileobj.close()`, before
  `# class StreamProxy` / the `#---` banner.
- `logging/__init__.py:203`, `test/test_gc.py:44`, `test/test_smtplib.py:232` —
  same relocation across a leading comment block.

This is the intended, documented behavior change of the patch (blank lines
anchor to the comment block), not a new defect. It is flagged pre-existing only
in the sense that the formatter/check disagreement predates the patch — the
*relocation* itself is the patch working.

**The 2 base convergence failures** are likewise base-only behavior and are the
reason the patch exists: E302 anchors its insertion before the intervening
comment block and fights E303/I001 until the 100-iteration limit. The patched
build resolves both.

## Introduced by the patch (candidate regressions)

**None. `diffs_formatter_disagrees_only_fixed = 0`, `fixed_converge_failures = 0`,
`fixed_non_idempotent = 0`.**

Because a null result is only worth what the instrument is worth, the
attribution was checked two ways:

1. **Independent re-derivation.** Every one of the 7 files was re-run outside
   the harness with both binaries, two passes each, capturing the real
   `Failed to converge` marker per pass and a `difflib` unified diff of the two
   builds' outputs. Results matched the harness exactly — see
   `repro/stdlib/stdlib-attribution-verification.txt`. No file that the harness
   called clean produced a convergence marker, and no file the harness called
   divergent was identical on re-run.
2. **Positive control.** The known patched-side regression
   (`repro/case_indented_comment.py`, the E302 indented-comment non-convergence
   from `2026-10-05-e302-indented-comment-nonconvergence.md`) was run through
   this exact harness and binaries as a 3-file control:

   ```
   corpus: 3 files; select=E301,E302,E303,E304,E305,E306,I001
      3/3 checked
   == summary ==
   converge failures: base=0 fixed=2
   non-idempotent:    base=0 fixed=0
   differing files:   2
     formatter disagrees in both builds (pre-existing): 0
     formatter disagrees only in patched (regression?): 2
   errors: 0
   ```

   Both binaries, literal output on `case_indented_comment.py`:

   ```
   ########## /tmp/ruff_base
   Found 2 errors (2 fixed, 0 remaining).
   ---------- resulting file:
   def test_update():
       pass

       # comment


   def test_clientmodel():
       pass

   ########## /tmp/ruff_fixed
   debug error: Failed to converge after 100 iterations in `t.py` with rule codes E302:---\n
   def test_update():
       pass

       # comment
   def test_clientmodel():
       pass
   ---
   blank-lines-top-level: Expected 2 blank lines, found 1
    --> t.py:5:1
     |
   4 |     # comment
   5 | def test_clientmodel():
     | ^^^
   6 |     pass
     |
   help: Add missing blank line(s)
     |
   3 |
   4 +
   5 |     # comment
     |

   Found 101 errors (100 fixed, 1 remaining).
   [*] 1 fixable with the `--fix` option.
   ---------- resulting file:
   def test_update():
       pass

       # comment
   def test_clientmodel():
       pass
   ```

   So the harness *does* flag patched-only regressions (`regression?: 2`) on the
   same binaries, the same select list, and the same config this stdlib run used.
   The stdlib result of 0 is a measured absence, not a blind instrument.

## Verdict

- Over the complete 1,762-file CPython 3.13 stdlib: **no regression introduced
  by the patch.** Zero patched-side convergence failures, zero
  patched-side-only formatter disagreements, zero non-idempotence, zero errors.
- The patch is **net-positive on this corpus**: both stdlib convergence failures
  (`test/_test_embed_structseq.py` E302, `test/test_inspect/inspect_fodder.py`
  I001) are base-only and are resolved by the patched build.
- 5 files show an intended blank-line relocation across a comment block. Every
  one of them already had a check/format disagreement in base, so none is a new
  class of breakage — but it is the patch's user-visible output change and the
  number to watch in downstream codebases.
- Important scoping caveat: the previously-known patched-side E302/E303
  indented-comment oscillation **did not reproduce anywhere in this stdlib run**,
  including in the 1,064-file `test/` tree. The known repro shape is
  indents-a-comment-then-a-top-level-def, which CPython's own code style largely
  avoids. It was confirmed still live via the positive control above. So this run
  is evidence about *CPython*, not a retraction of the earlier finding — the 10
  patched-side failures in `2026-10-05-full-fixtures-stdlib.md` all lived in
  ruff fixtures and third-party `site-packages`, neither of which is in scope here.

## Artifacts

All under `repro/stdlib/` in this repo:

- `stdlib-summary.json` / `stdlib-results.json` — harness report (copy of `/tmp/stddlib-report`)
- `stdlib-attribution-verification.txt` — independent re-derivation: per-pass
  convergence status for both builds + unified diffs of the 7 divergent files
- `positive-control-summary.json` — the control run proving detection works
- `positive_control/` — the 3 control files, including the known-bug repro

Scratch reports left in place: `/tmp/stddlib-report`, `/tmp/stddlib-report2`,
`/tmp/ctrl-report`, `/tmp/verify-attribution.txt`, `/tmp/stddlib-run.log`.

No changes to `/Users/matthewselvam/ruff-work`. Nothing committed or pushed.

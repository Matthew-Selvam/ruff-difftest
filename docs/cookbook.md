# ruff-difftest cookbook

A field guide to running the differential harness and triaging what it finds.

**Provenance:** every command in this document was executed verbatim during the
writing of this cookbook, against the pair of ruff 0.16.9 debug builds used for
the E302 investigation (`/tmp/ruff_base` = unpatched `8b83731`,
`/tmp/ruff_fixed` = patched `blank_lines.rs` comment-block anchoring). Output
blocks are the captured output of those runs, not idealized transcripts. Paths
under `/tmp` print as `/private/tmp` in tool output because macOS resolves the
symlink.

The worked example throughout is the find documented in
[`findings/2026-10-05-e302-indented-comment-nonconvergence.md`](../findings/2026-10-05-e302-indented-comment-nonconvergence.md):
the patched build fails to converge on an indented trailing comment while the
unpatched build converges in one pass.

---

## 0. Prerequisites and build identity

You need two ruff binaries and [uv](https://docs.astral.sh/uv/). Before
anything else, pin down *what* you are comparing — every report you write later
depends on these two lines:

```console
$ /tmp/ruff_base --version
ruff 0.16.9
$ /tmp/ruff_fixed --version
ruff 0.16.9
$ uv --version
uv 0.12.23 (46b84fd0b 2026-10-03 aarch64-apple-darwin)
```

Same version string on both binaries is expected and fine — you are comparing
*code changes*, not releases. Record the commits the binaries were built from
in your notes; the version string alone will not distinguish them.

---

## 1. One-file A/B sanity check (no harness)

Before touching the harness, run both binaries over the suspect file by hand.
This is the fastest way to see the raw behavior, and it is the command sequence
to reach for whenever the harness surfaces something you don't understand.

Set up two isolated directories — one per build — with the file and the config
the harness itself would use (`preview = true`, since blank-line behavior
differs under preview):

```console
$ mkdir -p /tmp/cb-demo/base /tmp/cb-demo/fixed
$ cp repro/case_indented_comment.py /tmp/cb-demo/base/case.py
$ cp repro/case_indented_comment.py /tmp/cb-demo/fixed/case.py
$ printf 'preview = true\n' > /tmp/cb-demo/base/ruff.toml
$ printf 'preview = true\n' > /tmp/cb-demo/fixed/ruff.toml
```

Run the **fixed** build first — the interesting half:

```console
$ cd /tmp/cb-demo/fixed
$ /tmp/ruff_fixed check . --select E302,E303 --no-cache --fix --unsafe-fixes --config ruff.toml; echo "exit=$?"
debug error: Failed to converge after 100 iterations in `case.py` with rule codes E302:---
def test_update():
    pass

    # comment
def test_clientmodel():
    pass

---
blank-lines-top-level: Expected 2 blank lines, found 1
 --> case.py:5:1
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
exit=1
```

Then the **base** build:

```console
$ cd /tmp/cb-demo/base
$ /tmp/ruff_base check . --select E302,E303 --no-cache --fix --unsafe-fixes --config ruff.toml; echo "exit=$?"
Found 2 errors (2 fixed, 0 remaining).
exit=0
```

Base converged (exit 0, everything fixed). The fixed build burned 100 fix
iterations, still reports `1 remaining`, and exits 1. Where did base's two
blank lines land?

```console
$ cat /tmp/cb-demo/base/case.py
def test_update():
    pass

    # comment


def test_clientmodel():
    pass
```

Between the comment and the following `def` — E302 satisfied without touching
the function body. That asymmetry (base exits 0, fixed exits 1 on the same
input, same flags) is the whole signal. Everything after this section is just
scaling it up.

Always pass `--no-cache` with debug builds; otherwise ruff prints
`warning: Detected debug build without --no-cache.` and result caching can muddy
an A/B comparison.

---

## 2. Isolate the fighting rules

Convergence failures are usually a *pairwise* problem: rule A's fix creates the
condition rule B flags. Narrow the `--select` to one rule at a time, on a fresh
copy of the input each round, to find the pair.

E302 alone — converges, but note *where* the insertion lands:

```console
$ cp repro/case_indented_comment.py /tmp/cb-demo/fixed/case.py
$ cd /tmp/cb-demo/fixed
$ /tmp/ruff_fixed check . --select E302 --no-cache --fix --unsafe-fixes --config ruff.toml; echo "exit=$?"
Found 1 error (1 fixed, 0 remaining).
exit=0
```

The file now carries two blank lines *inside* `test_update`'s body, before the
comment — E302's insertion anchored at the comment block start. That is legal
while E302 is the only rule in play.

E303 alone — nothing to do:

```console
$ cp repro/case_indented_comment.py /tmp/cb-demo/fixed/case.py
$ cd /tmp/cb-demo/fixed
$ /tmp/ruff_fixed check . --select E303 --no-cache --fix --unsafe-fixes --config ruff.toml; echo "exit=$?"
All checks passed!
exit=0
```

E302 + E303 together — the fight (see §1: 100 iterations, exit 1). E302
inserts blank lines at the comment; E303 removes them as too-many-inside-body;
repeat forever.

**Triage rule:** when the harness reports a convergence failure, bisect the
rule set like this before reading any source. A failure that needs two rules
points at an insertion/anchoring conflict between specific fixes, not at a
broken single rule.

---

## 3. Run the harness on the same file

The hand-run in §1 becomes reproducible bookkeeping with the harness. Give it a
corpus directory containing just the repro file:

```console
$ mkdir -p /tmp/cb-corpus
$ cp repro/case_indented_comment.py /tmp/cb-corpus/case_indented_comment.py
$ uv run ruff_difftest.py run --corpus /tmp/cb-corpus --base /tmp/ruff_base --fixed /tmp/ruff_fixed --select E302,E303 --jobs 1 --report /tmp/cb-report
corpus: 1 files; select=E302,E303
  1/1 checked
report written to /private/tmp/cb-report
== summary ==
converge failures: base=0 fixed=1
non-idempotent:    base=0 fixed=0
differing files:   1
  formatter disagrees in both builds (pre-existing): 0
  formatter disagrees only in patched (regression?): 1
errors: 0
```

The harness ran each build twice per file (convergence + idempotence), compared
final outputs, and — for the differing file — re-ran `check --fix` followed by
`format` per build to classify the drift. The saved summary:

```console
$ cat /tmp/cb-report/summary.json
{
  "corpus_size": 1,
  "select": "E302,E303",
  "base_converge_failures": 0,
  "fixed_converge_failures": 1,
  "base_non_idempotent": 0,
  "fixed_non_idempotent": 0,
  "differing_files": 1,
  "diffs_formatter_disagrees_both": 0,
  "diffs_formatter_disagrees_only_fixed": 1,
  "errors": 0
}
```

How to read the two formatter buckets:

- `diffs_formatter_disagrees_both` — `check --fix` output and `format` output
  disagree in *both* builds: pre-existing formatting-stage disagreement, almost
  certainly not your regression.
- `diffs_formatter_disagrees_only_fixed` — disagreement appears only under the
  patched build: candidate regression, triage it.

On this corpus the signal is clean: the patched build is the only one that
fails to converge (`fixed_converge_failures: 1`), and the drift lands in the
only-in-patched bucket. `--jobs` can stay at 1 for a one-file corpus; scale it
to core count for real corpora.

---

## 4. Corpus from ruff's own fixtures

One file proves the mechanism; a corpus proves the blast radius. `collect`
copies `.py` files from any number of roots into a flat corpus the harness can
walk. Point it at a ruff checkout's fixtures (path below is this machine's
checkout — substitute your own):

```console
$ uv run ruff_difftest.py collect --out /tmp/cb-fixtures --roots /Users/matthewselvam/ruff-work/crates/ruff_linter/resources/test/fixtures/pycodestyle --max-per-root 20
copied 20 files into /private/tmp/cb-fixtures
```

`--max-per-root 20` caps files per root for quick runs; drop it for full
coverage. Fill a corpus directory directly with one fixture tree (this is how
the 74-file run below got its corpus — a plain `cp` of the 74 `.py` fixtures,
`ls | wc -l` → `74`):

```console
$ mkdir -p /tmp/cb-corpus74
$ cp /Users/matthewselvam/ruff-work/crates/ruff_linter/resources/test/fixtures/pycodestyle/*.py /tmp/cb-corpus74/
$ ls /tmp/cb-corpus74 | wc -l
74
```

Then run the full check set over the corpus:

```console
$ uv run ruff_difftest.py run --corpus /tmp/cb-corpus74 --base /tmp/ruff_base --fixed /tmp/ruff_fixed --select E301,E302,E303,E304,E305,E306,I001 --jobs 8 --report /tmp/cb-report74
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

`converge failures: base=1 fixed=1` looks symmetric and therefore harmless. It
is not. `results.json` attributes each failure to a file *and a build*:

```console
$ cat /tmp/cb-report74/results.json
[
  {
    "path": "E30.py",
    "base_converge_fail": false,
    "fixed_converge_fail": true,
    ...
  },
  {
    "path": "E30_comment_before_definition.py",
    "base_converge_fail": true,
    "fixed_converge_fail": false,
    ...
  }
]
```

(Shown elided; full file ships in [`examples/demo/results-74.json`](../examples/demo/results-74.json).)

Read it as a two-by-two attribution:

| file | fails on base | fails on fixed | meaning |
|---|---|---|---|
| `E30_comment_before_definition.py` | ✔ | | the bug the patch *fixes* — intended |
| `E30.py` | | ✔ | the regression this harness exists to catch |

Both files land in the `disagrees_both` formatter bucket here — the formatter
stage disagrees with the fix stage in both builds on these fixtures — but the
convergence asymmetry is the load-bearing finding: no unit test in the patched
tree catches `E30.py` (2,836 tests pass there).

**Symmetric-looking summaries hide asymmetric facts. Never report a
`base=N fixed=N` count without the per-file, per-build attribution next to it.**

---

## 5. Multi-root corpora

`collect` accepts several roots in one shot; files keep their root-relative
paths, so differently-named fixture trees merge cleanly:

```console
$ uv run ruff_difftest.py collect --out /tmp/cb-multi --roots /Users/matthewselvam/ruff-work/crates/ruff_linter/resources/test/fixtures/pycodestyle /Users/matthewselvam/ruff-work/crates/ruff_linter/resources/test/fixtures/pydocstyle --max-per-root 15
copied 30 files into /private/tmp/cb-multi
$ uv run ruff_difftest.py run --corpus /tmp/cb-multi --base /tmp/ruff_base --fixed /tmp/ruff_fixed --select E302,E303 --jobs 4
corpus: 30 files; select=E302,E303
  30/30 checked
== summary ==
converge failures: base=1 fixed=1
non-idempotent:    base=0 fixed=0
differing files:   1
  formatter disagrees in both builds (pre-existing): 1
  formatter disagrees only in patched (regression?): 0
errors: 0
```

Good roots to mix: rule-specific fixture trees matching your `--select`, a
CPython stdlib checkout, and your own project's source.

---

## 6. Reading the report files

`--report DIR` writes two files:

`summary.json` — counters over the whole corpus:

| field | question it answers |
|---|---|
| `corpus_size` / `select` | what ran |
| `base_converge_failures` / `fixed_converge_failures` | which build fails to settle `--fix` |
| `base_non_idempotent` / `fixed_non_idempotent` | which build's second `--fix` pass changes output |
| `differing_files` | final outputs differ between builds |
| `diffs_formatter_disagrees_both` | drift explainable by a pre-existing fix-vs-format disagreement |
| `diffs_formatter_disagrees_only_fixed` | drift only the patched build produces — regression candidates |
| `errors` | harness-level failures (missing files, timeouts), not lint findings |

`results.json` — one record per *interesting* file (any file that converges
failing, is non-idempotent, differs, or errors), with the per-build boolean
flags (`base_converge_fail`, `fixed_converge_fail`, `base_non_idempotent`,
`fixed_non_idempotent`, `outputs_differ`, `base_format_disagrees`,
`fixed_format_disagrees`). A clean run has an empty `results.json` — no output
at all is a pass.

Run without `--report` to get only the stdout summary (handy in CI logs):

```console
$ uv run ruff_difftest.py run --corpus /tmp/cb-corpus74 --base /tmp/ruff_base --fixed /tmp/ruff_fixed --select E301,E302,E303,E304,E305,E306,I001 --jobs 8
corpus: 74 files; select=E301,E302,E303,E304,E305,E306,I001
  74/74 checked
== summary ==
converge failures: base=1 fixed=1
non-idempotent:    base=0 fixed=0
differing files:   2
  formatter disagrees in both builds (pre-existing): 2
  formatter disagrees only in patched (regression?): 0
errors: 0
```

Subcommand help, if you lose the flags:

```console
$ uv run ruff_difftest.py run --help
usage: ruff_difftest.py run [-h] --corpus CORPUS --base BASE --fixed FIXED
                            [--select SELECT] [--jobs JOBS] [--report REPORT]
...
$ uv run ruff_difftest.py collect --help
usage: ruff_difftest.py collect [-h] --out OUT --roots ROOTS [ROOTS ...]
                                [--max-per-root MAX_PER_ROOT]
...
```

---

## 7. Exit codes and failure modes

- **`run` exits 2 on an empty/missing corpus** — nothing to compare, not a
  comparison failure:

  ```console
  $ uv run ruff_difftest.py run --corpus /tmp/no-such-corpus-dir --base /tmp/ruff_base --fixed /tmp/ruff_fixed
  no .py files under /private/tmp/no-such-corpus-dir
  $ echo $?
  2
  ```

- **Ruff's own exit code surfaces through §1-style hand runs** — a
  `Failed to converge` run exits 1 even though the command "worked". In CI,
  treat any nonzero ruff exit inside the harness corpus as a finding to
  attribute, not as harness breakage.

- **Debug-build cache warning** — without `--no-cache`, debug builds print
  `warning: Detected debug build without --no-cache.`; the harness writes its
  own config and fresh temp dirs per file, so its results are unaffected, but
  add `--no-cache` to hand runs (§1–§2) for clean A/B comparisons.

- **Timeouts** — each ruff invocation gets a 120 s budget (`FIX_TIMEOUT_S`);
  pathological fixtures that hit it show up under `errors`, not as convergence
  failures.

---

## 8. Triage checklist for a new drift

1. **Attribute first.** From `results.json`, name the file and the build for
   every counter in the summary. No findings without attribution.
2. **Reproduce by hand** (§1): both builds, same flags, isolated dirs. Confirm
   the asymmetry exists outside the harness.
3. **Bisect the rule set** (§2) down to the minimal `--select` that still
   fights. Two rules fighting = insertion/anchoring conflict; note which rule's
   fix creates the other's condition.
4. **Minimize the file** to the smallest shape that still fails. Save it under
   `repro/` with a name describing the shape (see
   `repro/case_indented_comment.py`).
5. **Classify** with the formatter buckets (§3, §6): only-in-patched →
   regression candidate; both → pre-existing, note it and move on.
6. **Check the blast radius** (§4–§5): full fixture tree for the affected rule
   families, plus a broad corpus. One file is a repro; a corpus is a finding.
7. **Write it up** in `findings/` with: commits of both builds, exact command
   lines, per-file attribution table, minimized repro, and the mechanism. The
   write-up linked at the top of this cookbook is the template.

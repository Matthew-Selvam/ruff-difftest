# Scaling benchmark — ruff_difftest

Measured 2026-10-05 on Apple Silicon macOS, debug builds of ruff 0.16.9
(`8b83731` vs `5882a3d`), corpus = ruff's own test fixtures,
`--select E301,E302,E303,E304,E305,E306,I001`. Numbers are single-run wall
times from `time.monotonic()` around the full `uv run` invocation.

| Corpus | Files | Jobs | Wall (s) | Summary |
|---|---|---|---|---|
| scale100 | 100 | 4 | 2.2 | converge failures: base=0 fixed=0 | non-idempotent:    base=0 fixed=0 | differing files:   0 | errors: 0 |
| scale300 | 300 | 4 | 6.5 | converge failures: base=0 fixed=0 | non-idempotent:    base=0 fixed=0 | differing files:   0 | errors: 0 |
| scale500 | 500 | 4 | 13.5 | converge failures: base=0 fixed=0 | non-idempotent:    base=0 fixed=0 | differing files:   0 | errors: 0 |
| scale500 | 500 | 8 | 11.4 | converge failures: base=0 fixed=0 | non-idempotent:    base=0 fixed=0 | differing files:   0 | errors: 0 |

## Conclusion

Scaling from 100 to 500 files is roughly linear: 0.02 s/file at 100
vs 0.03 s/file at 500 under jobs=4 (total 2.2s -> 13.5s, 6.1x for 5x the corpus).
Doubling workers to jobs=8 on the 500-file corpus brought wall time from
13.5s to 11.4s (16% faster), so the workload is
CPU-bound in ruff subprocesses and scales with worker count until cores are
saturated. Runtime is dominated by the four `check --fix`/`format` subprocess
invocations per file per build, not harness overhead; per-file cost is
essentially flat across corpus sizes.

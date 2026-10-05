# Smoke corpus (fake-binary CI)

Hermetic inputs for the `smoke` job in `.github/workflows/ci.yml`. No real
ruff involved — CI cannot build ruff binaries, so the differential path runs
against the shell fakes in `tests/fake_bin/`:

- `base.sh`   : `check --fix` leaves files unchanged (converges, idempotent)
- `fixed.sh`  : appends `# ruff-fixed-build-fake` exactly once (converges,
  idempotent, but output differs from base)
- `nonidem.sh`: appends the marker on every run (never idempotent)

`format` is a no-op in all three, so the formatter is expected to agree with
`check --fix` output in every build.

Expected `ruff_difftest.py run` summaries (3 corpus files, one nested under
`pkg/` to prove the corpus walker descends):

- base vs fixed  : `differing_files == 3`, zero converge failures, zero
  non-idempotence, `errors == 0`
- base vs nonidem: `differing_files == 3`, `fixed_non_idempotent == 3`,
  zero converge failures, `errors == 0`

The harness never mutates corpus files (fresh temp copy per file and build),
but it does write/remove a transient `ruff_difftest.toml` in the corpus root
while running, so CI copies this directory to `$RUNNER_TEMP` instead of
running against the checkout directly.

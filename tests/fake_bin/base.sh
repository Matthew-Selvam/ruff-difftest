#!/usr/bin/env bash
# Fake "base" ruff build for the hermetic CI smoke test.
#
# Mimics just enough of the ruff surface that ruff_difftest.py exercises
# (the harness always runs with cwd = a temp workdir holding exactly one
# corpus .py file, so "the file argument" is simply every *.py in cwd):
#
#   check . --select ... --fix --unsafe-fixes --config ...
#     -> applies no fixes: every *.py stays byte-identical
#        (converges on pass 1, idempotent on pass 2)
#   format . --config ...
#     -> no-op, so the formatter always agrees with the check --fix output
#
# Unknown invocations fail loudly (exit 2) so the harness never silently
# tests the wrong thing.
set -euo pipefail

cmd="${1:-}"

case "$cmd" in
check)
    : # base build applies no fixes; corpus files remain untouched
    printf 'Found 0 errors.\n'
    ;;
format)
    : # no-op formatter
    ;;
--version)
    printf 'fake-ruff 0.0.0 (base)\n'
    ;;
*)
    printf 'fake_ruff (base): unsupported invocation: %s\n' "$*" >&2
    exit 2
    ;;
esac

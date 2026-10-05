#!/usr/bin/env bash
# Fake "fixed" ruff build, NON-IDEMPOTENT variant, for the hermetic CI smoke test.
#
#   check . --select ... --fix --unsafe-fixes --config ...
#     -> appends the marker line '# ruff-fixed-build-fake' on EVERY run, so
#        pass 2's output never equals pass 1's. ruff_difftest.py must flag
#        fixed_non_idempotent for every corpus file (and the final output
#        still differs from the base build, i.e. DIFF as well).
#   format . --config ...
#     -> no-op, so the formatter agrees with the check --fix output.
set -euo pipefail

MARKER='# ruff-fixed-build-fake'
cmd="${1:-}"

append_marker_every_run() {
    f=$1
    # Keep the marker on its own line even if the file lacks a trailing newline.
    if [ -n "$(tail -c 1 "$f")" ]; then
        printf '\n' >> "$f"
    fi
    printf '%s\n' "$MARKER" >> "$f"
}

case "$cmd" in
check)
    for f in *.py; do
        [ -e "$f" ] || break
        append_marker_every_run "$f"
    done
    printf 'Found 1 error (1 fixed, 0 remaining).\n'
    ;;
format)
    : # no-op formatter
    ;;
--version)
    printf 'fake-ruff 0.0.0 (fixed, non-idempotent)\n'
    ;;
*)
    printf 'fake_ruff (fixed, non-idempotent): unsupported invocation: %s\n' "$*" >&2
    exit 2
    ;;
esac

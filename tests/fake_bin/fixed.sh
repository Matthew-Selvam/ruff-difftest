#!/usr/bin/env bash
# Fake "fixed" ruff build (the change under test) for the hermetic CI smoke test.
#
#   check . --select ... --fix --unsafe-fixes --config ...
#     -> appends the marker line '# ruff-fixed-build-fake' to every *.py in
#        the current directory EXACTLY ONCE (guarded by a whole-line grep),
#        so the fix converges and is idempotent across a second pass, but the
#        final output differs from the base build (which never touches the
#        file). ruff_difftest.py must therefore report every corpus file as a
#        DIFF and nothing else.
#   format . --config ...
#     -> no-op, so the formatter agrees with the check --fix output.
set -euo pipefail

MARKER='# ruff-fixed-build-fake'
cmd="${1:-}"

append_marker_once() {
    f=$1
    # Ensure the file ends with a newline so the marker lands on its own line
    # (keeps the whole-line grep guard and idempotence intact even if a corpus
    # file lacks a trailing newline).
    if [ -n "$(tail -c 1 "$f")" ]; then
        printf '\n' >> "$f"
    fi
    grep -qxF "$MARKER" "$f" || printf '%s\n' "$MARKER" >> "$f"
}

case "$cmd" in
check)
    for f in *.py; do
        [ -e "$f" ] || break
        append_marker_once "$f"
    done
    printf 'Found 1 error (1 fixed, 0 remaining).\n'
    ;;
format)
    : # no-op formatter
    ;;
--version)
    printf 'fake-ruff 0.0.0 (fixed)\n'
    ;;
*)
    printf 'fake_ruff (fixed): unsupported invocation: %s\n' "$*" >&2
    exit 2
    ;;
esac

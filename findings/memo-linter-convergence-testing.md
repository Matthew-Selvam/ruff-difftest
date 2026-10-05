# Memo: How Python linters/formatters guard against fixer non-convergence — and a roadmap for ruff-difftest

*Research memo for ruff-difftest, October 2026. All facts below verified against live sources (ruff `main` source fetched 2026-10-05) except where marked guess.*

## Part 1 — How the ecosystem guards against non-convergence

**1. Ruff: a hard iteration cap with a dedicated diagnostic.** Ruff's fix loop is `MAX_ITERATIONS: usize = 100` (`crates/ruff_linter/src/linter.rs`). When fixes don't reach a fixed point within 100 rounds it bails and emits a "Failed to converge after 100 iterations" error naming the file and rule codes (`report_failed_to_converge_error`), instead of looping forever or silently emitting half-fixed output.
https://github.com/astral-sh/ruff/blob/main/crates/ruff_linter/src/linter.rs

**2. Non-convergence is a real, recurring bug class — usually rule interactions.** Five open/closed ruff issues describe fix loops: [#6754](https://github.com/astral-sh/ruff/issues/6754) (F401 ×100 loop), [#12611](https://github.com/astral-sh/ruff/issues/12611) (E302+I001 infinite loop), [#20891](https://github.com/astral-sh/ruff/issues/20891) (F401+I002+PYI025), [#25418](https://github.com/astral-sh/ruff/issues/25418) (TID254/TID255), [#26450](https://github.com/astral-sh/ruff/issues/26450) (TID254). The pattern: each fix re-creates the precondition for another rule's fix — a ping-pong between two fixers. A single-rule test suite won't catch these; only multi-rule runs over diverse files will. That is exactly what ruff-difftest's `--select` over a real corpus does.

**3. Black: two built-in oracles — equivalence and idempotence — as hard internal errors.** `format_str` runs `assert_equivalent` (AST-blit comparison that output is semantically equivalent to input) and `assert_stable` (a second formatting pass must produce identical output). Violations raise "INTERNAL ERROR" with a diff, exit code 123. Black's docs note "Return code 123 means there was an internal error."
https://github.com/psf/black/blob/main/src/black/__init__.py · https://black.readthedocs.io/en/stable/usage_and_configuration/the_basics.html

**4. Ruff ships its own differential checker — direct prior art, mostly overlapping.** `python/ruff-ecosystem` is a CLI that runs `ruff-ecosystem check|format <baseline> <comparison>` over real-world OSS checkouts and renders markdown diffs of diagnostics/outputs, with caching of project checkouts, specifically for PR review ("compare lint and format results for two different ruff versions (e.g. main and a PR) on real world projects"). It predates ruff-difftest's concept; its niche is curated big-repos, not adversarial/minimized corpora, and it doesn't do convergence or idempotence probing per file — those ruff-difftest checks are the differentiator.
https://github.com/astral-sh/ruff/blob/main/python/ruff-ecosystem/README.md

**5. Output format: ruff natively emits 12 formats including SARIF.** `--output-format` accepts `concise, full, json, json-lines, junit, grouped, github, gitlab, pylint, rdjson, azure, sarif` (verified from `ruff --help` on docs.astral.sh/ruff/configuration/). SARIF is the de-facto interchange for CI code-scanning surfaces (GitHub code scanning ingests SARIF natively), so SARIF output is the lowest-friction path to GitHub integration.
https://docs.astral.sh/ruff/configuration/

**6. Differential testing prior art: Csmith.** Csmith generates random C programs free of undefined behavior and uses *differential testing as the test oracle*: compile with two compilers, run both binaries, any output divergence is a bug in one of them. Two lessons transfer: (a) the generator must control for confounders (Csmith's "no UB" guarantee ↔ a lint corpus should be syntax-valid, non-trivial, and diverse in rule triggers) and (b) divergence attribution ("a bug in either gcc or clang") is the weak point — you need a baseline attribution step to say *which* side regressed, which ruff-difftest's pre-existing-vs-regression classification already does.
https://github.com/csmith-project/csmith

**Pylint note:** I could not verify a bounded fix-iteration loop in pylint's main linter source from my fetches; pylint's `--fix` style of behavior is comparatively recent and I did not find its iteration-limit mechanism — **unverified guess: pylint applies fixes once per message without a convergence loop.**

## Part 2 — Prioritized roadmap for ruff-difftest

Existing tool (verified by reading `ruff_difftest.py`): collect/run modes, per-file fresh scratch copies, converge-fail + non-idempotent + output-diff detection, base-vs-patched formatter-disagreement attribution, JSON summary. Gaps: no exit-code semantics, no per-rule attribution, single hardcoded output format, no corpus minimization.

1. **`--fail-on-regression` exit codes (0 clean, 1 new converge-fail/non-idempotent/diff vs base)** — turns the tool from a report generator into a CI gate; today `mode_run` always returns 0 even with regressions.
2. **Per-rule attribution of diffs** — rerun the differing file with rules bisected (halve the select set, recurse) to report "the divergence is caused by rule X interacting with Y"; directly targets the F401×I001-style loop class from issues #12611/#20891.
3. **SARIF output alongside summary.json** — reuse ruff's own SARIF serialization shape so results land in GitHub code scanning / PR annotations without a custom Action; pairs naturally with #1.
4. **Minified-repro auto-extraction** — for each failing file, shrink toward a minimal snippet (delete imports/statements while the failure signature persists) so filed issues are 5 lines, not 500; this is delta-debugging à la Csmith's controlled reduction.
5. **Corpus caching keyed by (file hash, select, ruff config)** — skip re-checking unchanged files on iterative runs against the same base binary; ruff-ecosystem already caches project checkouts for the same reason.
6. **N-version mode (base / patched / released-stable)** — three-way comparison distinguishes "patched regressed vs base" from "both regressed vs last release", fixing the attribution ambiguity Csmith's paper explicitly calls out.
7. **Adversarial corpus generation** — seed the corpus with known loop patterns (import-heavy files, mixed fixable rules, `# noqa` interactions) plus optional grammar-fuzz generated snippets, following Csmith's insight that random-but-structured inputs outperform curated fixtures for finding fixer interactions.
8. **GitHub Action wrapper + `--report-format markdown`** — a one-line workflow step that posts a table of regressions on the PR; ruff itself integrates this way (its `github` output format), so parity is expected by users.

*Guesses, explicitly: the CI-gate exit code (#1) is my inference from black's exit-code-123 precedent, not an established convention for linter differential tools; SARIF-in-code-scanning friction (#3) is from general ecosystem knowledge, not a measured integration test; #7's loop-seeding patterns are my hypotheses from the issue titles above, not validated against ruff's fixture coverage.*

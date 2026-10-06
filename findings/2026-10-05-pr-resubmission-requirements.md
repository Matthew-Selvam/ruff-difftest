# PR Resubmission Requirements — astral-sh/ruff (E301/E302 blank-line insertion)

**Prepared:** 2026-10-06 · **Scope:** procedural requirements only, for a PR opened from a fork
(`Matthew-Selvam/ruff`) against `astral-sh/ruff`.
**Resubmission target:** the previously auto-closed PR
[#29035](https://github.com/astral-sh/ruff/pull/29035) (`[pycodestyle] Insert E301/E302 blank lines before comment blocks`).

> This checklist deliberately contains **no PR prose, no summary text, and no issue comment drafts.**
> Per astral's AI policy, every public string must be written by the human author. See item 0.

---

## 0. NON-NEGOTIABLE: the AI policy governs *who writes the text*, not *what tools were used*

**Source:** [`astral-sh/.github/blob/main/AI_POLICY.md`](https://github.com/astral-sh/.github/blob/main/AI_POLICY.md)
**Policy file last commit:** `2026-03-13T16:30:46Z` — commit `88a2f5d5`, message *"Add an AI policy (#1)"*. Only commit touching the file; not stale relative to today.

### Permitted (quoted)

> "We support using AI (i.e., LLMs) as tools for coding. However, you remain
> responsible for any code you publish and we are responsible for any code we
> merge and release."

> "If you are opening a pull request, we expect you to be able to explain the
> proposed changes in your own words. This includes the pull request body and
> responses to questions."

> "Due to the foundational nature of our projects, we require a human in the loop
> who understands the work produced by AI."

> "We understand that AI is useful when communicating as a non-native English
> speaker. If you are using AI to edit your comments for this purpose, please take
> the time to ensure it reflects your own voice and ideas."

### Forbidden (quoted)

> "**AI should not be used to generate comments when communicating with
> maintainers**. We expect comments on our projects to be written by humans. We
> may hide any comments that we believe are AI generated."

> "**Do not copy responses from the AI when replying to questions from
> maintainers.**"

> "**We do not allow autonomous agents to be used for contributing to our
> projects**. We will close any pull requests that we believe were created
> autonomously."

### What the human must specifically be able to do

Per the above, the human must be able to:

1. **Explain the proposed change in their own words** — the PR body, unaided. This is the explicit
   test for the PR body.
2. **Answer maintainer questions in their own words** without copying AI output — this applies to
   every future comment thread, not just the body.
3. **Demonstrate understanding of the work the AI produced** ("a human in the loop who understands
   the work produced by AI").

### Conditional allowance for quoting AI context in comments (quoted)

> "If you wish to include context from an interaction with AI in your comments,
> it must be in a quote block (e.g., using `>`) and disclosed as such. It must be
> accompanied by human commentary explaining the relevance and implications of the
> context. Do not share long snippets."

→ **Recommendation (inferred, not documented):** do not quote any AI context in the resubmission at
all. The quote-block allowance is an escape hatch; the body needs none, and #29035's body contained no
quoted AI context. Using it would only add surface for a policy judgment call.

### Interpretation note — AI-assisted *code* vs AI-generated *text*

- The policy's **opening sentence explicitly permits AI as a coding tool**, and its closing paragraph
  explicitly anticipates AI involvement in communication for non-native speakers.
- The prohibition targets **text generation for comments/PR body** and **autonomous contribution**, not
  the existence of AI assistance in producing the diff.
- `CONTRIBUTING.md` reinforces this reading: AI assistance in the *summary* is contemplated, provided
  the human editorializes it (quoted in item 5).

> ⚠️ **This is the single highest-risk item, and it is a judgment call no document resolves.**
> The AI policy says "we expect you to be able to explain the proposed changes in your own words" —
> it does not define a mechanical test for that. `ntBre` has already indicated a perception problem
> (item 9). Whatever "own words" means, it must be demonstrably yours before you press submit.

---

## 1. Duplicate-work check — required *before starting* and *again before opening*

**Source:** [`CONTRIBUTING.md` § Avoiding duplicate work](https://github.com/astral-sh/ruff/blob/main/CONTRIBUTING.md#avoiding-duplicate-work)
**Also required by** [`AGENTS.md` § Before contributing](https://github.com/astral-sh/ruff/blob/main/AGENTS.md#before-contributing)

Quoted, in full:

> "Before starting on an issue, take a look at the discussion and any linked pull requests, including
> those in the sidebar. An issue may still be open while a fix is under review. Even if a previous
> attempt was closed, it may contain useful context or review comments that you could incorporate
> before submitting a new PR."

And from `AGENTS.md`:

> "Before starting work on an issue and again before opening a pull request, follow the
> [guidance on avoiding duplicate work](CONTRIBUTING.md#avoiding-duplicate-work). If an open pull
> request already addresses the issue, do not submit a competing one without maintainer agreement."

**Checklist:**
- [ ] Read every comment on issue **#12611** (6 comments; listed in item 9).
- [ ] Review closed attempt **#23354** *and its review comments* — `CONTRIBUTING.md` explicitly names
      closed attempts as a source of context to incorporate. Verified as satisfying this requirement:
      #23354's `CHANGES_REQUESTED` review by `ntBre` and the author's closing comment are readable at
      <https://github.com/astral-sh/ruff/pull/23354>.
- [ ] Review **#20853** and specifically the linked comment by `MichaReiser`
      (<https://github.com/astral-sh/ruff/issues/20853#issuecomment-3400349146>), which supplies the
      ASCII-only reproduction and the formatter-behaviour diagnosis.
- [ ] Confirm no *open* PR addresses #12611. **Verified 2026-10-06: none exists** (see item 8). Re-verify
      immediately before submitting.

---

## 2. Title convention — required for lint-rule PRs

**Source:** [`CONTRIBUTING.md`](https://github.com/astral-sh/ruff/blob/main/CONTRIBUTING.md) and
[`.github/PULL_REQUEST_TEMPLATE.md`](https://github.com/astral-sh/ruff/blob/main/.github/PULL_REQUEST_TEMPLATE.md)

Quoted from `CONTRIBUTING.md`:

> "If your pull request relates to a specific lint rule, include the category and rule code or name in
> the title, as in the following examples:
>
> - \[`flake8-bugbear`\] Avoid false positive for usage after `continue` (`B031`)
> - \[`flake8-simplify`\] Detect implicit `else` cases in `needless-bool` (`SIM103`)
> - \[`pycodestyle`\] Implement `redundant-backslash` (`E502`)
> - \[`pedantic`\] Implement `pytest-fixture-autouse`"

Quoted from the PR template:

> "- Does this pull request include a descriptive title? (Please prefix with `[ty]` for ty pull
>   requests.)"

- [ ] Title uses the `[pycodestyle]` bracket prefix **and** names the rule(s) `E301`/`E302`.
- [ ] Title does **not** carry a `[ty]` prefix. This is a `ruff` PR; per `AGENTS.md`, "When working on
      ty, PR titles should start with `[ty]`" — this change is in `ruff_linter`, not a `ty*` crate.
- [ ] Title is not prefixed by the repo name. `ty`'s rooster config sets `trim-title-prefixes = ["[ty]"]`;
      **ruff's** `pyproject.toml` has no `trim-title-prefixes` key. `rooster` is configured in ruff's
      `pyproject.toml` (line 70: `"rooster==0.1.1"`).
      Observed current convention in open PRs: both `[ty] …` and bare titles are used.

---

## 3. Body structure — the two template sections

**Source:** [`.github/PULL_REQUEST_TEMPLATE.md`](https://github.com/astral-sh/ruff/blob/main/.github/PULL_REQUEST_TEMPLATE.md)

Full template body:

> "## Summary
>
> \<!-- What's the purpose of the change? What does it do, and why? -->
>
> ## Test Plan
>
> \<!-- How was it tested? -->"

And its checklist preamble, verbatim:

> "Thank you for contributing to Ruff/ty! To help us out with reviewing, please consider the following:
>
> - Does this pull request include a summary of the change? (See below.)
> - Does this pull request include a descriptive title? (Please prefix with `[ty]` for ty pull
>   requests.)
> - Does this pull request include references to any relevant issues?
> - Does this PR follow our AI policy (https://github.com/astral-sh/.github/blob/main/AI_POLICY.md)?"

`CONTRIBUTING.md` § The Basics → Opening a PR:

> "After you finish your changes, the next step is to open a PR. By default, two
> sections will be filled into the PR body: the summary and the test plan."

**What the summary must contain** (`CONTRIBUTING.md` § The summary, quoted):

> "The summary is intended to give us as maintainers information about your PR.
> This should typically include a link to the relevant issue(s) you're addressing
> in your PR, as well as a summary of the issue and your approach to fixing it. If
> you have any questions about your approach or design, or if you considered
> alternative approaches, that can also be helpful to include."

**On AI use in the summary** — note this is the repo *permitting* AI-assisted drafting with a human
gate (quoted):

> "AI can be helpful in generating both the code and summary of your PR, but a
> successful contribution should still be carefully reviewed by you and the
> summary editorialized before submitting a PR. A great summary is thorough but
> also succinct and gives us the context we need to review your PR."

**What the test plan must contain** (quoted):

> "The test plan is likely to be shorter than the summary and can be as simple as
> "Added new snapshot tests for `RUF123`," at least for rule bugs. For LSP or some
> types of CLI changes, in particular, it can also be helpful to include
> screenshots or recordings of your change in action."

- [ ] Body has exactly the `## Summary` and `## Test Plan` headings the template pre-fills.
- [ ] Summary links the relevant issue(s) — #12611, and as context #20853 / #23354.
- [ ] Summary states the approach and any design questions / alternatives considered.
- [ ] Test plan is your own account of how it was tested.
- [ ] Both sections written and editorialized by you.

**"Great writeup" reference examples** (quoted from `CONTRIBUTING.md`):

> "You can find examples of excellent issues and PRs by searching for the
> [`great writeup`](https://github.com/astral-sh/ruff/issues?q=label%3A%22great+writeup%22)
> label."

---

## 4. Issue-closing syntax

- [ ] Reference #12611 using a GitHub closing keyword so the issue auto-closes on merge.

**Evidence for the exact syntax.** No documentation in ruff's repo prescribes a closing-keyword form.
What the repo does is *use* it — `gh search code --repo astral-sh/ruff "Fixes #"` returns only test
fixture files (`crates/ruff_linter/resources/test/fixtures/flake8_bugbear/B027.py`, `.pyi`), i.e. the
string is not itself a documented convention. **However**, the immediate precedent for this specific
issue and this specific bug class is unambiguous in PR bodies that reached review:

- `PR #23354` body, first line: `Fixes #12611.`
- The author's own two prior PRs on the same bug class:
  - `PR #29105` body: `Fixes #28861.`
  - `PR #29110` body: `Follow-up to #29105, from the same bug class: …`

> ⚠️ **Flagged as inferred.** `Fixes #NNNN.` (capital F, trailing period, standalone line) is the
> convention *observed in practice* on this bug's prior PRs, not a documented requirement. GitHub accepts
> `Fixes`/`Closes`/`Resolves #NNNN` case-insensitively. Nothing in ruff's docs mandates the period.

- [ ] If the change does **not** fully resolve #12611, do not use a closing keyword — link it as a plain
      reference instead. *(Inferred from GitHub semantics; not a ruff-documented rule.)*

---

## 5. Labels — required by `AGENTS.md`, configured by `[tool.rooster]`

### 5a. `AGENTS.md` § PR conventions — what you must do

Verbatim:

> "Before opening a PR, inspect the repository's available GitHub labels and the current Rooster
> configuration, including required and ignored labels, in the `[tool.rooster]` and
> `[tool.rooster.section-labels]` sections of [Ruff's `pyproject.toml`](pyproject.toml) and
> [ty's `pyproject.toml`](https://github.com/astral-sh/ty/blob/main/pyproject.toml). Labels such as
> `internal`, `testing`, and `ci` can exclude a PR from a changelog. Decide whether and how the change
> should appear in each changelog, then select appropriate labels."

> "When working on ty, PR titles should start with `[ty]`. Add the `ty` GitHub label."

> "If you have permission, apply the selected labels when creating the PR or afterward, then verify
> that the PR's actual labels include them and have the intended effect on each changelog. If the
> available labels or a Rooster configuration could not be inspected, say so when reporting the PR."

### 5b. `[tool.rooster]` — ruff `pyproject.toml` (lines 312–354), verbatim

```toml
[tool.rooster]
major_labels = []  # Ruff never uses the major version number
minor_labels = ["breaking"]   # Bump the minor version on breaking changes

ignore_labels = ["internal", "ci", "testing", "ty"]

version_files = [ … 15 entries … ]

[tool.rooster.section-labels]
"Breaking changes" = ["breaking"]
"Preview features" = ["preview"]
"Bug fixes" = ["bug"]
"Rule changes" = [
    "diagnostics",
    "docstrings",
    "rule",
    "fixes",
    "isort",
]
"Performance" = ["performance"]
"Formatter" = ["formatter"]
"Server" = ["server"]
"CLI" = ["cli"]
"Configuration" = ["configuration"]
"Documentation" = ["documentation"]
"Other changes" = ["__unknown__"]
```

**Direct answers:**

| Question | Answer | Source |
|---|---|---|
| Which labels are **required**? | **None.** ruff's `pyproject.toml` contains **no `require-labels` key** (verified by grep over the fetched file). Only *ty*'s config has `require-labels = [{ submodule = "ruff", labels = ["ty"] }]`, which does not bind ruff's own changelog. | `astral-sh/ruff` `pyproject.toml` |
| Which labels **exclude** a PR from the changelog? | `internal`, `ci`, `testing`, `ty` — verbatim `ignore_labels = ["internal", "ci", "testing", "ty"]`. | same |
| Which labels drive a **breaking** minor bump? | `breaking` (`minor_labels = ["breaking"]`). | same |
| Which section does this change belong in? | `bug` → **"Bug fixes"**; and/or `fixes` / `isort` → **"Rule changes"**. | same |

### 5c. Labels that actually exist in astral-sh/ruff (69 total, verified 2026-10-06)

Full inventory retrieved via `gh label list --repo astral-sh/ruff --limit 200`. Relevant subset:

| Label | Exists | Description (verbatim from GitHub) | In `[tool.rooster.section-labels]`? |
|---|---|---|---|
| `bug` | ✅ | "Something isn't working" | → "Bug fixes" |
| `fixes` | ✅ | "Related to suggested fixes for violations" | → "Rule changes" |
| `isort` | ✅ | "Related to import sorting" | → "Rule changes" |
| `rule` | ✅ | "Implementing or modifying a lint rule" | → "Rule changes" |
| `diagnostics` | ✅ | "Related to reporting of diagnostics." | → "Rule changes" |
| `formatter` | ✅ | "Related to the formatter" | → "Formatter" |
| `linter` | ✅ | "Related to the linter" | ❌ not in any section |
| `style` | ✅ | "How should formatted code look" | ❌ not in any section |
| `parser` | ✅ | "Related to the parser" | ❌ not in any section |
| `configuration` | ✅ | "Related to settings and configuration" | → "Configuration" |
| `documentation` | ✅ | "Improvements or additions to documentation" | → "Documentation" |
| `performance` | ✅ | "Potential performance improvement" | → "Performance" |
| `preview` | ✅ | "Related to preview mode features" | → "Preview features" |
| `breaking` | ✅ | "Breaking API change" | → "Breaking changes" + minor bump |
| `internal` | ✅ | "An internal refactor or improvement" | ⛔ **ignore** |
| `ci` | ✅ | "Related to internal CI tooling" | ⛔ **ignore** |
| `testing` | ✅ | "Related to testing Ruff itself" | ⛔ **ignore** |
| `ty` | ✅ | "Multi-file analysis & type inference" | ⛔ **ignore** |
| `docstrings` | ❌ **DOES NOT EXIST** | — | listed in rooster's "Rule changes" but no such label exists |
| `docstring` | ✅ | "Related to docstring linting or formatting" | ❌ not in any section |

**Do NOT apply:** `internal`, `ci`, `testing`, `ty` — each removes the PR from ruff's changelog.
Also avoid `do-not-merge`, `duplicate`, `no-test`, `wontfix`, `bot:*`.

**Precedent for exactly this label set.** Prior PRs on the identical bug class and the identical
changelog destination:
- `PR #23354` (closed, the earlier attempt): `['bug', 'fixes']`
- `PR #29105` (yours, bot-closed): body `Fixes #28861.` — label set not inspected before closure
- `PR #29035` (yours, bot-closed): `['bot:ai-policy-close']` — bot label overwrote the intended set
- Open, comparable external PR `PR #28919` (`[isort] Keep a line-trailing pragma on the import statement (I001)`):
  `['bug', 'isort']`
- Open external PR `PR #29084` (`` [`pyupgrade`] Suggest `typing.TypeForm` on Python 3.15 (`UP0…`) ``):
  `['rule']`
- Open external PR `PR #29076` (`` [`flake8-builtins`] Expand checks in class scopes (`A001`) ``):
  `['bug']`

- [ ] Decide the label set yourself; `bug` is the clearly-supported core, given the issue carries
      `['bug', 'fuzzer']` and both prior attempts (`#23354`, `#28919`) used `bug`.
- [ ] Apply the labels if you have permission.
- [ ] **Verify the applied labels on the live PR** (`gh pr view <n> --json labels`) — `AGENTS.md`
      requires this explicitly.
- [ ] If you *cannot* apply labels (external contributors normally cannot), **say so when reporting the
      PR** — this is a literal instruction in `AGENTS.md`, not advice.

### 5d. ⚠️ The ty-vs-ruff labeling trap — flag as ambiguous

This PR changes `ruff_linter`'s pycodestyle blank-line logic. ty vendors/depends on several `ruff_*`
crates, which is why it was framed as a "ty-vs-ruff" PR. `AGENTS.md` says "When working on ty … Add the
`ty` GitHub label."

**The trap:** `ty` is in `ignore_labels`. Adding it would **exclude this PR from ruff's changelog**,
while a ty-vs-ruff shared-crate fix arguably *should* appear in the ty changelog too.

> ⚠️ **Could not resolve from documentation.** Ruff's config has no `require-labels` and no
> cross-repo changelog routing; ty's `require-labels = [{ submodule = "ruff", labels = ["ty"] }]`
> governs *ty's* changelog, not ruff's. The decision is yours — make it deliberately, and be ready to
> justify it. If in doubt, prefer **not** applying `ty` so the fix is visible in ruff's changelog, and
> state your reasoning. This is **inference**, not a documented rule.

---

## 6. Pre-merge local validation — documented, and CI will run it anyway

**Source:** [`CONTRIBUTING.md` § Development](https://github.com/astral-sh/ruff/blob/main/CONTRIBUTING.md)

Verbatim:

> "Prior to opening a pull request, ensure that your code has been auto-formatted,
> and that it passes both the lint and test validation checks:

```shell
CARGO_BUILD_WARNINGS=deny cargo clippy --workspace --all-targets --all-features  # Rust linting
RUFF_UPDATE_SCHEMA=1 cargo test  # Rust testing and updating ruff.schema.json
uv run --only-dev --locked prek run --all-files  # Rust and Python formatting, Markdown and Python linting, etc.
```

> "These checks will run on GitHub Actions when you open your pull request, but running them locally
> will save you time and expedite the merge process."

And on snapshots:

> "Note that many code changes also require updating the snapshot tests, which is done interactively
> after running `cargo test` like so:

```shell
uv run --only-dev cargo insta review
```"

And on generated files (`AGENTS.md`):

> "Run `cargo dev generate-all` after changing configuration options, CLI arguments, lint rules, or
> environment variable definitions, as these changes require regeneration of schemas, docs, and CLI
> references."

- [ ] `CARGO_BUILD_WARNINGS=deny cargo clippy --workspace --all-targets --all-features` clean
- [ ] `RUFF_UPDATE_SCHEMA=1 cargo test` passing; snapshots reviewed via `cargo insta review`
- [ ] `uv run --only-dev --locked prek run --all-files` clean
- [ ] `cargo dev generate-all` run if the change touches lint-rule behaviour, and generated diffs
      reviewed
- [ ] Optional but documented: `uv run --only-dev --locked prek install` to wire these into commits

**Note on CI:** `gh pr checks 29035` reports *"no checks reported on the `fix/e302-comment-block-insertion`
branch"* — the PR was closed ~17 minutes after opening, before CI produced results. So the current
branch has **no verified green CI run**; treat item 6 as mandatory rather than already satisfied.

---

## 7. Regeneration / ecosystem follow-ups

**Source:** `CONTRIBUTING.md` § Ecosystem report

> "After opening the PR, an ecosystem report will be run as part of CI. This shows
> a diff of linter and formatter behavior before and after the changes in your PR.
> Going through these changes and reporting your findings in the PR summary or an
> additional comment help us to review your PR more efficiently."

- [ ] After opening, watch for the `<!-- generated-comment ecosystem -->` bot comment (observed on
      #23354) and review the reported linter/formatter diffs yourself.

---

## 8. Current upstream state — verified 2026-10-06 (re-check before submitting)

| Item | State | Detail |
|---|---|---|
| Issue **#12611** | **OPEN** | "Fixing file with rules E302, I001 cause infinite loop" · author `qarmin` · created 2024-08-01 · last updated **2026-10-01T13:20:38Z** · labels `['bug', 'fuzzer']` · **assignee: `TaKO8Ki`** |
| Competing PR for #12611 | **NONE** | `gh search issues --repo astral-sh/ruff --match title,body,comments "12611"` returns only #12611, #20853 (closed), #18274 (closed). No open PR references it. |
| Open PRs matching E301/E302/isort/blank-line/converge/12611 | **1, unrelated** | `PR #28919` `[isort] Keep a line-trailing pragma on the import statement (I001)` by `speedsharmaai`, 2026-09-26, labels `['bug','isort']`. Different rule and different bug (line-trailing pragma on import statement, not comment-block anchoring). **Worth reading before submitting to confirm no overlap.** |
| Issue **#20853** | **CLOSED / DUPLICATE**, 2025-10-14T07:23:24Z | "Fixes between E302 and I001 disagree" · author `mcdigman` · labels `['bug', 'fixes']` · closed by `MichaReiser`: "I think this is the same one as #12611" |
| PR **#23354** | **CLOSED (unmerged)** 2026-02-22T23:24:45Z | "Fix E302 autofix infinite loop with non-ASCII comments" · author `kar-ganap` · labels `['bug','fixes']`. Never merged. |
| PR **#29035** | **CLOSED (unmerged)** 2026-10-01T08:45:05Z, ~17 min after opening 08:28:17Z | Sole label: `bot:ai-policy-close`. Closed automatically; **no code review took place**. |

### ⚠️ Blocking: your fork branch has diverged from upstream `main`

`gh api repos/astral-sh/ruff/compare/main...Matthew-Selvam:fix/e302-comment-block-insertion`:

```
{ "status": "diverged", "ahead_by": 1, "behind_by": 46 }
```

- Upstream `main` head at time of research: `6dc81766`, `2026-10-06T01:25:34Z`.
- Your branch head: `5882a3dd`, `2026-10-01T07:26:40Z`, "[pycodestyle] Insert E301/E302 blank lines before comment blocks".
- Fork `default_branch`: `main`; fork `pushed_at`: `2026-10-05T13:13:44Z`; `fork: true`, parent `astral-sh/ruff`.
- Fork branches present: `fix/e302-comment-block-insertion`, `fix/plr1711-preserve-trailing-comment`,
  `fix/t201-t203-preserve-trailing-comment`, `main`.

- [ ] **Rebase or merge upstream `main` into your branch before submitting.** 46 upstream commits have
      landed since. `CONTRIBUTING.md`'s divergence guidance is generic, but `AGENTS.md` explicitly treats
      rebases as a reason to re-run hooks: "Run `uv run --only-dev --locked prek` at the end of a task
      if you changed files in the repo. This includes changes such as rebases or addressing review
      comments."
- [ ] Re-run item 6 in full **after** the rebase, and re-review any snapshot diffs the rebase changed.
- [ ] Verify the fix still reproduces/behaves identically against the new `main` before submitting.

### ⚠️ Also note — two other PRs of yours were bot-closed on 2026-10-05

`bot:ai-policy-close` has been applied to 20 PRs repo-wide in the recent window (2026-09-21 → 2026-10-05),
including two more of yours:
- `PR #29105` — `[pylint] Preserve trailing comments in the PLR1711 fix` (body: `Fixes #28861.`)
- `PR #29110` — `[flake8-print] Preserve trailing comments in the T201/T203 fix`

**Implication for sequencing (inferred):** the enforcement pattern is broad, not targeted at #29035's
particular content. Before resubmitting, make sure the policy analysis in item 0 has been applied
consistently to *every* string in the PR — and treat any simultaneously-reopened PRs as subject to the
same bar. Note also that `PR #28905` (`PLR1711: preserve trailing comments when removing useless returns`,
`2026-09-25`) was also bot-closed — that one is **not yours**, indicating the bot's behavior is
contributor-agnostic.

---

## 9. Issue-thread state and the maintainer feedback you must not repeat

Full comment list on #12611 (`gh api repos/astral-sh/ruff/issues/12611/comments`), oldest first:

| Date | Author | Content (verbatim, truncated where noted) |
|---|---|---|
| 2024-08-01T21:24:56Z | `MichaReiser` | "Huh, that's funny. Thanks for reporting!" |
| 2025-09-26T07:28:54Z | `TaKO8Ki` | "I will take this one." |
| 2025-10-14T07:24:02Z | `MichaReiser` | "See https://github.com/astral-sh/ruff/issues/20853#issuecomment-3400349146 for an ASCII-only reproduction and a fix suggestion" |
| 2026-10-01T08:29:00Z | `Matthew-Selvam` | your first comment, announcing #29035 |
| 2026-10-01T09:00:25Z | `Matthew-Selvam` | your second comment, on the auto-close |
| 2026-10-01T13:20:29Z | `ntBre` | **see below** |

**`ntBre`'s comment, verbatim and in full:**

> "@Matthew-Selvam Please take a look at the AI policy that the bot linked you to. I get the impression that your comments here are also LLM-written. You also don't need to tag us in all of your comments. We'll see the notifications."

**Two concrete, actionable instructions from a maintainer:**

1. **Stop tagging maintainers.** "You also don't need to tag us in all of your comments. We'll see the
   notifications." → No `@ntBre`, no `@MichaReiser`, no `@TaKO8Ki` in comments or the PR body.
2. **Comments on issues must be human-written.** This is the AI policy's
   "**AI should not be used to generate comments when communicating with maintainers**."

- [ ] Re-read the AI policy yourself before posting anything.
- [ ] Do not `@`-mention maintainers in the PR body or any comment.
- [ ] Do not post an issue comment before or after opening the PR unless you have something new to
      say — the last thing you posted was a correction, and a third comment restating intent repeats
      the pattern `ntBre` objected to. **(Inference: no rule forbids commenting; the risk is
      compounding the "LLM-written comments" perception.)**
- [ ] `TaKO8Ki` claimed the issue ("I will take this one.", 2025-09-26) and is still the **assignee**.
      Your own earlier comment acknowledged them. *Inferred* judgment: since you have not had a
      response, and your approach differs from #23354's, a single brief human-written comment on
      #12611 is defensible — but only one, only in your own words, with no maintainer tags.

---

## 10. What changed in `CONTRIBUTING.md` for a resubmission specifically

`CONTRIBUTING.md` § PR status — verified as applicable to any follow-up cycle:

> "To help us know when your PR is ready for review again, please either move your
> PR back to a draft while working on it (marking it ready for review afterwards
> will ping the previous reviewers) or explicitly re-request a review."

> "You can also thumbs-up or mark as resolved any comments we leave to let us know
> you addressed them."

- [ ] Mark the PR a **draft** while working on it after review comments arrive; convert to ready-for-review
      when done (this pings previous reviewers).

---

## 11. Consolidated pre-submit checklist

**Before submitting:**

1. [ ] Read the AI policy end to end; be able to explain the change in your own words unaided.
2. [ ] No `@`-tags of maintainers anywhere in the PR.
3. [ ] Every character of `## Summary` and `## Test Plan` is yours, editorialized by you.
4. [ ] Title: `[pycodestyle]` prefix + rule codes/names; no `[ty]`, no repo-name prefix.
5. [ ] Body has both template headings; summary links #12611 (plus #20853 / #23354 as context).
6. [ ] `Fixes #12611.` in a form that actually closes the issue (if the fix is complete).
7. [ ] Rebase/merge upstream `main` — **branch is currently 46 commits behind, status `diverged`**.
8. [ ] Re-run clippy + `cargo test` (with snapshot review) + `prek` + `generate-all` after the rebase.
9. [ ] Re-confirm no open PR now addresses #12611 (`AGENTS.md`: do not submit a competing PR).
10. [ ] Read `PR #28919` to confirm no overlap with the open isort PR.
11. [ ] Decide labels (core: `bug`); **do not** apply `internal` / `ci` / `testing` / `ty`.
12. [ ] Apply labels if permitted; **verify them on the live PR**; if you could not apply them, **say so
        when reporting the PR** (`AGENTS.md` instruction).

**After submitting:**

13. [ ] Watch the ecosystem report bot comment; review the linter/formatter behavior diff.
14. [ ] Respond to every maintainer comment in your own words, without copying AI output.

---

## 12. Explicit list of what I could NOT verify

| # | Item | Why unverifiable |
|---|---|---|
| 1 | **The AI-policy enforcement bot's actual trigger logic** | `astral-sh/.github` contains only `AI_POLICY.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md` — no workflow, action, or app code. ruff's `.github/` has no ai/policy workflow either (only `daily_fuzz.yaml` matched). The `bot:ai-policy-close` label exists with **empty description** (id 11740344102) and `bot:ai-policy-comment` likewise (id 11253889491). Detection is not open-source-visible. |
| 2 | **Whether the contributor has permission to apply labels** | `gh api repos/astral-sh/ruff/collaborators/Matthew-Selvam/permission` → HTTP 403 "Must have push access". Not determinable from outside. External contributors typically cannot label. |
| 3 | **Whether #29035 was *also* judged to violate the code-authorship half of the policy** | The PR body contains an extensive code-level explanation. I cannot determine whether the bot's judgment covered only the comments or the PR body/approach as well. Only a maintainer can say. |
| 4 | **`rooster`'s exact `__unknown__` ("Other changes") semantics** | `gh api repos/astral-sh/rooster/...` → HTTP 404; the rooster repo is not publicly readable, so its README/config-schema is unavailable. `pypi` package metadata was not consulted. |
| 5 | **The `docstrings` / `docstring` label mismatch** | `[tool.rooster.section-labels]` "Rule changes" lists `"docstrings"` (plural) but the repo's actual label is `docstring` (singular) — verified absent/present respectively. Whether rooster normalizes this is **not** determinable (see #4). Not relevant to this PR, but a live config inconsistency. |
| 6 | **Branch protection / required status checks on `main`** | `gh api repos/astral-sh/ruff/branches/main/protection` → HTTP 404 (no push access). Which checks gate merge is unknown. |
| 7 | **A documented rule for `Fixes #NNNN` syntax** | None exists in ruff's repo. The syntax used in item 4 is inferred from observed PR bodies. |
| 8 | **Whether maintainers want the E302/E301 comment-anchoring approach re-litigated** | #23354 was closed with the author's note: "The correct insertion point requires reworking the backward-walk logic, and I don't have bandwidth for that right now. Happy to reopen if someone wants to pick this up." No maintainer has since endorsed that specific rework. #12611 carries no `help wanted` / `good first issue` label. |
| 9 | **Label distribution on the closed PRs #29105 / #29110** | Both were bot-closed with only `bot:ai-policy-close` applied, so the intended label set cannot be recovered. |
| 10 | **The full text of the #29035 PR body** | Truncated at ~1500 chars in retrieval; the tail (test plan section) was not read. Only relevant for reference, not for this checklist. |

---

## 13. Ambiguities I had to infer — review these yourself

1. **`Fixes #NNNN.` formatting.** Observed convention, not documented requirement (item 4).
2. **Whether to apply the `ty` label.** Directly conflicts with `ignore_labels`; no documented tiebreak
   (item 5d). This is the highest-impact labeling decision.
3. **Label set beyond `bug`.** `fixes` (matching #23354, which fixed an autofix) and `isort` (matching
   #28919, and I001 is half the bug) are each defensible. `AGENTS.md` demands the decision be deliberate;
   it does not dictate the answer (item 5c).
4. **Whether to comment on #12611 at all before submitting.** Not required by any document (item 9).
5. **Whether "own words" is satisfied.** The policy states the requirement but defines no test, and
   `ntBre` has already flagged a perception issue (item 0).
6. **Whether the rebase should be a rebase or a merge.** `AGENTS.md` mentions "rebases"; no ruff doc
   prescribes the strategy for a fork PR. 46 commits behind, so pick and verify (item 8).

---

*All GitHub data in this document was retrieved read-only on 2026-10-06 via `gh` CLI, authenticated as
`Matthew-Selvam` from the macOS keyring. No files in any repository were modified, no commits pushed, no
comments posted.*

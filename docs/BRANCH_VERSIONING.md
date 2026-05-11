---
status: current
type: governance
owner: human
created: 2026-05-11
last_reviewed: 2026-05-11
expires: none
superseded_by: null
---

# Branch and Version Management

This policy defines branch, pull request, tag, and milestone conventions for the repository. It is part of the AI collaboration framework and applies to human, Claude, and Codex work.

## Principles

- Use trunk-based development.
- Keep `main` as the integration branch.
- Keep branches short-lived and scoped to one issue or PR.
- Prefer small PRs with explicit permitted and forbidden files.
- Squash merge completed PRs so `main` stays readable.
- Delete merged branches after the PR is merged.

Long-running research, design, or implementation branches should be split into smaller PRs before merge.

## Branch Naming

Use a lowercase prefix followed by a short kebab-case description.

| Prefix | Use |
|---|---|
| `docs/` | Documentation governance, runbooks, ADRs, handoff updates, and docs-only cleanup. |
| `ci/` | CI configuration, lint/test runners, dependency setup for automation. |
| `test/` | Regression tests, smoke tests, and test-only coverage. |
| `fix/` | Bug fixes for existing behavior. |
| `feature/` | New user-facing or system behavior. |
| `design/` | Design-only plans, architecture proposals, and implementation plans. |
| `hotfix/` | Urgent human-approved fixes, especially for broken `main` or deployment blockers. |

Examples:

```text
docs/add-branch-versioning-policy
ci/add-minimal-unit-gate
test/add-frontend-mime-smoke
fix/correct-swap-ctval-pnl
feature/add-backtest-comparison-view
design/replay-terminal-liquidation-plan
hotfix/restore-api-startup
```

## Standard Branch Workflow

Use this workflow for normal PRs:

```bash
git checkout main
git pull
git checkout -b <prefix>/<short-description>
```

Then make the scoped change, run the required checks, and push:

```bash
pytest tests/unit -v
ruff check src tests
git push -u origin <prefix>/<short-description>
```

Open a pull request with:

- Summary.
- Related issue.
- AI attribution.
- Explicit scope and out-of-scope lists.
- Test plan and results.
- Branch/version checklist.

After review:

1. Squash merge the PR into `main`.
2. Delete the remote branch.
3. Delete the local branch after confirming `main` is updated.
4. Update `docs/AI_HANDOFF.md` if the PR changes current state or next steps.

## Merge Policy

Use squash merge by default.

Squash commits should preserve the PR intent and include AI trailers when the work was AI-assisted:

```text
AI-Origin: Codex | Claude | Human | Mixed
AI-Role: Planning | Implementation | Review | Debugging
Reviewer: Claude | Human | None
Human-Reviewed: yes | no
```

Do not merge unrelated work into one PR to make the squash commit look cleaner. Keep the PR scope clean before review.

## Tag and Milestone Policy

Use lightweight repository milestones for planning and Git tags for meaningful checkpoints on `main`.

| Tag / milestone | Meaning |
|---|---|
| `v0.1.0-governance` | AI workflow, handoff, documentation lifecycle, branch/versioning policy, and PR/issue templates are in place. |
| `v0.2.0-ci-regression` | Minimal CI plus core regression tests for PnL, frontend MIME, artifact schema, hedge close, and funding dual-leg behavior. |
| `v0.3.0-replay-validation` | Replay terminal liquidation and validation gates are designed, implemented, tested, and ADR-0005 can move from proposed to accepted. |
| `v0.4.0-shadow-parity` | Shadow mode parity design and implementation support SimBroker primary vs OKX demo mirror comparison. |

Tags should be created only from `main` after the relevant milestone is merged and the user approves the checkpoint.

Recommended tag command:

```bash
git tag -a v0.1.0-governance -m "v0.1.0 governance checkpoint"
git push origin v0.1.0-governance
```

## AI Agent Rules

- Do not create or switch branches unless the user asks for branch operations.
- Do not force-push unless the user explicitly approves it for the exact branch.
- Do not merge PRs unless the user explicitly asks.
- If there are uncommitted changes from another task, preserve them and report the overlap.
- If branch policy conflicts with an active issue's permitted files, follow the issue scope and ask the user before expanding.

## Cleanup Checklist

Before a PR is ready for review:

- [ ] Branch name uses an approved prefix.
- [ ] PR is scoped to one issue or task.
- [ ] Permitted and forbidden files are listed.
- [ ] Required checks are run or skipped with reason.
- [ ] `docs/AI_HANDOFF.md` is updated when current state changes.
- [ ] Milestone impact is stated when relevant.

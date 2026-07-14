---
status: current
type: index
owner: human
created: 2026-06-25
last_reviewed: 2026-07-14
expires: none
superseded_by: null
---

# Human Review Index

This index lists Human Review Overviews for AI-generated planning, strategy,
governance, and harness changes. Start here when an AI says it produced "a batch
of docs" — the overview tells you what changed, what needs your decision, which
source docs are must-read, and what is still unverified.

The overview is a human entry point, **not** the source of truth. If an overview
conflicts with its source docs, the source docs win. See
[`human_overviews/README.md`](human_overviews/README.md) and
[`AI_OUTPUT_CONTRACT.md`](AI_OUTPUT_CONTRACT.md).

| Date | Topic | Overview | Status | Risk | Decision required | Human decision |
|---|---|---|---|---|---|---|
| 2026-07-14 | ADR-0011 H-014 shadow-only implementation | [docs/human_overviews/2026-07-14-adr0011-shadow-execution-overview.md](human_overviews/2026-07-14-adr0011-shadow-execution-overview.md) | current | high | yes | pending |
| 2026-07-13 | P0.4 integration + P1 governance batch + post-merge follow-up | [docs/human_overviews/2026-07-13-p0-p1-governance-overview.md](human_overviews/2026-07-13-p0-p1-governance-overview.md) | current | high | yes | PR #9 merged; follow-up pending |
| 2026-07-12 | Whole-project diagnosis and P0 closure | [docs/human_overviews/2026-07-12-project-diagnosis-overview.md](human_overviews/2026-07-12-project-diagnosis-overview.md) | current | high | no | approved |
| 2026-06-25 | Strategy Research Pipeline Stage 1 | [docs/human_overviews/2026-06-25-strategy-research-pipeline-overview.md](human_overviews/2026-06-25-strategy-research-pipeline-overview.md) | deprecated | medium | yes | superseded |
| 2026-06-25 | In-Dashboard User Manual (使用手冊) | [docs/human_overviews/2026-06-25-user-manual-overview.md](human_overviews/2026-06-25-user-manual-overview.md) | deprecated | low | no | superseded |

## Rules

- Every new overview adds a row here.
- `Human decision` starts as `pending`; update to `approved` / `rejected` /
  `superseded` when the user decides.
- When an overview is replaced, set its frontmatter `superseded_by` and mark this
  row `superseded`.
